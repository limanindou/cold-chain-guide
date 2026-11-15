"""Opening incidents — shared by the three detectors:
  ingest_reading   -> TEMP_EXCURSION  (reading outside the safe range)
  ingest_event     -> POWER_LOST      (sensor reports it is running on battery)
  check_heartbeats -> SENSOR_OFFLINE  (no reading for offlineAfterSeconds)

Whatever the signal, a device has at most ONE open incident: a conditional write on
the device (attribute_not_exists(openIncidentId)) opens it atomically; later signals
are recorded as events on the open incident instead of starting a second workflow.
"""
from __future__ import annotations

import json
import os
import secrets

import boto3
from botocore.exceptions import ClientError

from shared import ddb, rules

sfn = boto3.client("stepfunctions")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")

TEMP_EXCURSION = "TEMP_EXCURSION"
POWER_LOST = "POWER_LOST"
SENSOR_OFFLINE = "SENSOR_OFFLINE"
TYPES = (TEMP_EXCURSION, POWER_LOST, SENSOR_OFFLINE)

DEFAULTS = {
    "recoveryWindowSeconds": 3600,  # real seconds to wait for recovery after someone acts
    "recheckSeconds": 300,          # real seconds between recovery checks
    "powerGraceSeconds": 300,
    "offlineAfterSeconds": 300,
}


def profile_value(profile: dict, name: str):
    return ddb.plain(profile.get(name, DEFAULTS.get(name)))


def new_incident_id(device_id: str, ts: str) -> str:
    return f"{device_id}-{ts[:19].replace('-', '').replace(':', '')}-{secrets.token_hex(3)}"


def open_incident(device: dict, profile: dict, incident_type: str, ts: str, detail: str,
                  log, temp_c: float | None = None) -> str | None:
    """Open an incident and start its workflow. Returns the incidentId, or None if the
    device already has an open incident (the conditional write lost the race)."""
    device_id = device["deviceId"]
    incident_id = new_incident_id(device_id, ts)
    log.bind(incidentId=incident_id, incidentType=incident_type)
    min_c, max_c = profile.get("minC"), profile.get("maxC")
    incident = {
        "PK": f"INCIDENT#{incident_id}", "SK": "META",
        "GSI1PK": "INCIDENTS", "GSI1SK": ts,
        "incidentId": incident_id,
        "type": incident_type,
        "deviceId": device_id,
        "deviceName": device.get("name", device_id),
        "location": device.get("location", ""),
        "profileId": profile["profileId"],
        "profileLabel": profile.get("label", profile["profileId"]),
        "status": "GRACE",
        "startedAt": ts,
        "firstTempC": temp_c,
        "direction": rules.excursion_direction(temp_c, min_c, max_c) if temp_c is not None else None,
        "minC": min_c,
        "maxC": max_c,
        "level": 0,
    }
    started = ddb.event_item(incident_id, "STARTED", detail, device_id=device_id, ts=ts,
                             tempC=temp_c, incidentType=incident_type)
    try:
        ddb.client.transact_write_items(TransactItems=[
            {"Update": {
                "TableName": ddb.TABLE_NAME,
                "Key": ddb.ser(ddb.device_key(device_id)),
                "UpdateExpression": "SET openIncidentId = :id, #s = :grace, incidentStartedAt = :ts",
                "ConditionExpression": "attribute_exists(PK) AND attribute_not_exists(openIncidentId)",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": ddb.ser_values({":id": incident_id, ":grace": "GRACE", ":ts": ts}),
            }},
            {"Put": {"TableName": ddb.TABLE_NAME, "Item": ddb.ser(incident),
                     "ConditionExpression": "attribute_not_exists(PK)"}},
            {"Put": {"TableName": ddb.TABLE_NAME, "Item": ddb.ser(started)}},
        ])
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "TransactionCanceledException":
            log.info("Device already has an open incident; not opening another")
            return None
        raise

    execution_input = {
        "incidentId": incident_id,
        "type": incident_type,
        "deviceId": device_id,
        "deviceName": device.get("name", device_id),
        "profileId": profile["profileId"],
        "minC": ddb.plain(min_c),
        "maxC": ddb.plain(max_c),
        "graceSeconds": ddb.plain(profile["graceSeconds"]),
        "powerGraceSeconds": profile_value(profile, "powerGraceSeconds"),
        "offlineAfterSeconds": profile_value(profile, "offlineAfterSeconds"),
        "ackTimeoutSeconds": ddb.plain(profile["ackTimeoutSeconds"]),
        "recoveryWindowSeconds": profile_value(profile, "recoveryWindowSeconds"),
        "recheckSeconds": profile_value(profile, "recheckSeconds"),
        "escalation": list(profile.get("escalation", [])),
        "startedAt": ts,
    }
    try:
        sfn.start_execution(stateMachineArn=STATE_MACHINE_ARN, name=incident_id,
                            input=json.dumps(execution_input))
        log.info("Incident opened, workflow started", tempC=temp_c)
    except sfn.exceptions.ExecutionAlreadyExists:
        log.info("Execution already exists (idempotent retry)")
    except Exception as exc:  # compensate so the device is not stuck with a phantom incident
        log.exception("StartExecution failed; rolling back incident", exc)
        ddb.table.update_item(
            Key=ddb.device_key(device_id),
            UpdateExpression="SET #s = :ok REMOVE openIncidentId, incidentStartedAt",
            ConditionExpression="openIncidentId = :id",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":ok": "OK", ":id": incident_id},
        )
        ddb.table.update_item(
            Key=ddb.incident_key(incident_id), UpdateExpression="SET #s = :f",
            ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues={":f": "FAILED_TO_START"},
        )
        raise
    return incident_id
