"""POST /demo/reset — put every device back to OK and stop running workflows.

Demo only: returns 403 unless DEMO_MODE=true, and requires the device key.
Body {"clearReadings": true} also deletes stored readings for clean charts.
"""
from __future__ import annotations

import hmac
import os

import boto3
from boto3.dynamodb.conditions import Key

from shared import ddb, http
from shared.log import Logger
from shared.timeutil import now_iso

log = Logger("demo_reset")
sfn = boto3.client("stepfunctions")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
DEVICE_KEY = os.environ.get("DEVICE_KEY", "")


def handler(event, context):
    log.reset(requestId=getattr(context, "aws_request_id", None))
    if not DEMO_MODE:
        return http.error(403, "Demo reset is disabled (DEMO_MODE=false)")
    supplied = http.header(event, "x-device-key")
    if not DEVICE_KEY or not hmac.compare_digest(supplied.encode(), DEVICE_KEY.encode()):
        return http.error(401, "Missing or invalid x-device-key")
    try:
        body = http.json_body(event)
    except ValueError:
        body = {}

    stopped, cancelled = 0, 0
    for inc in ddb.recent_incidents(100):
        if inc.get("status") not in ddb.ACTIVE_INCIDENT_STATUSES:
            continue
        if inc.get("executionArn"):
            try:
                sfn.stop_execution(executionArn=inc["executionArn"], cause="Demo reset")
                stopped += 1
            except Exception as exc:  # already finished, etc.
                log.warning("StopExecution failed", incidentId=inc["incidentId"], detail=str(exc))
        ddb.table.update_item(
            Key=ddb.incident_key(inc["incidentId"]),
            UpdateExpression="SET #s = :c, resolvedAt = :now REMOVE pendingAck",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":c": "CANCELLED", ":now": now_iso()},
        )
        ddb.put_event(inc["incidentId"], "CANCELLED", "Cancelled by demo reset", device_id=inc.get("deviceId"))
        cancelled += 1

    cleared = 0
    for device in ddb.list_entities("DEVICES"):
        ddb.table.update_item(
            Key=ddb.device_key(device["deviceId"]),
            UpdateExpression="SET #s = :ok, powerSource = :mains, batteryPct = :full "
                             "REMOVE openIncidentId, incidentStartedAt, offlineSince",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":ok": "OK", ":mains": "MAINS", ":full": 100},
        )
        if body.get("clearReadings"):
            cleared += _clear_readings(device["deviceId"])

    log.info("Demo reset", stopped=stopped, cancelled=cancelled, readingsDeleted=cleared)
    return http.respond(200, {"stopped": stopped, "cancelled": cancelled, "readingsDeleted": cleared})


def _clear_readings(device_id: str) -> int:
    items = ddb.query_all(
        KeyConditionExpression=Key("PK").eq(f"DEVICE#{device_id}") & Key("SK").begins_with("READING#"),
        ProjectionExpression="PK, SK",
    )
    with ddb.table.batch_writer() as batch:
        for it in items:
            batch.delete_item(Key={"PK": it["PK"], "SK": it["SK"]})
    return len(items)
