"""POST /incidents/{id}/respond — a responder taps an action.

The ackCode is looked up, claimed exactly once (conditional write), and its stored task
token is handed back to Step Functions:
  MOVED_TO_BACKUP / FIXED -> SendTaskSuccess  (workflow continues to recovery checks)
  NEED_HELP               -> SendTaskFailure("NeedHelp")  (workflow escalates immediately)
"""
from __future__ import annotations

import json

import boto3
from botocore.exceptions import ClientError

from shared import ddb, http
from shared.log import Logger
from shared.timeutil import now_iso, parse_iso, utcnow
from shared.validation import ValidationError, validate_response

log = Logger("respond")
sfn = boto3.client("stepfunctions")


def handler(event, context):
    incident_id = http.path_param(event, "id")
    log.reset(incidentId=incident_id, requestId=getattr(context, "aws_request_id", None))
    try:
        code, action, note = validate_response(http.json_body(event), incident_id)
    except (ValidationError, ValueError) as exc:
        return http.error(400, str(exc))

    ack = ddb.get_item(ddb.ack_key(code), consistent=True)
    if not ack or ack.get("incidentId") != incident_id:
        return http.respond(404, {"result": "NOT_FOUND", "message": "This link is not valid."})
    if ack.get("usedAt"):
        return _already_handled(ack)
    if utcnow() > parse_iso(ack["expiresAt"]):
        return _expired()

    responder = ddb.get_responder(ack["responderId"])
    now = now_iso()
    # Claim the code exactly once and drop the token from storage.
    try:
        claimed = ddb.table.update_item(
            Key=ddb.ack_key(code),
            UpdateExpression="SET usedAt = :now, usedAction = :a, usedByName = :n REMOVE taskToken",
            ConditionExpression="attribute_not_exists(usedAt)",
            ExpressionAttributeValues={":now": now, ":a": action, ":n": responder.get("name", "")},
            ReturnValues="ALL_OLD",
        )["Attributes"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return _already_handled(ddb.get_item(ddb.ack_key(code), consistent=True) or {})
        raise

    token = claimed["taskToken"]
    try:
        if action == "NEED_HELP":
            ddb.put_event(incident_id, "NEED_HELP",
                          f"{responder.get('name')} asked for help" + (f': "{note}"' if note else ""),
                          actor=responder["responderId"], device_id=None)
            sfn.send_task_failure(taskToken=token, error="NeedHelp",
                                  cause=f"{responder.get('name')} asked for help")
        else:
            sfn.send_task_success(taskToken=token, output=json.dumps({
                "action": action,
                "responderId": responder["responderId"],
                "responderName": responder.get("name", responder["responderId"]),
                "note": note,
                "at": now,
            }))
    except (sfn.exceptions.TaskTimedOut, sfn.exceptions.InvalidToken, sfn.exceptions.TaskDoesNotExist):
        log.info("Task token no longer valid (escalated or finished)")
        return _expired()

    log.info("Responder action accepted", action=action, responderId=responder["responderId"])
    return http.respond(200, {"result": "OK", "action": action, "responderName": responder.get("name")})


def _already_handled(ack: dict):
    return http.respond(409, {
        "result": "ALREADY_HANDLED",
        "message": "This alert has already been handled.",
        "handledBy": ack.get("usedByName"),
        "handledAt": ack.get("usedAt"),
        "action": ack.get("usedAction"),
    })


def _expired():
    return http.respond(410, {
        "result": "EXPIRED",
        "message": "This alert has expired — it was escalated to the next person or the incident is closed.",
    })
