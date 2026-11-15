"""POST /readings — store a sensor reading and evaluate the device's rule (signal #1).

* Out of range and no open incident -> open a TEMP_EXCURSION incident (atomic conditional
  write: one open incident per device) and start ONE Step Functions execution.
* Out of range while another incident is open (e.g. POWER_LOST) -> record it as an event
  on that incident; never a second incident.
* Back in range while an incident is open -> record recoveredAt (the workflow decides).
* First reading after silence -> clear offlineSince and note it on the open incident.
* Back in range (and on mains) after a CRITICAL incident -> release the device.
"""
from __future__ import annotations

import hmac
import os
from decimal import Decimal

from botocore.exceptions import ClientError

from shared import ddb, http, incidents, rules
from shared.log import Logger
from shared.timeutil import epoch, utcnow
from shared.validation import ValidationError, validate_battery, validate_reading

log = Logger("ingest_reading")
DEVICE_KEY = os.environ.get("DEVICE_KEY", "")
READING_TTL_SECONDS = 24 * 3600


def authorised(event) -> bool:
    supplied = http.header(event, "x-device-key")
    return bool(DEVICE_KEY) and hmac.compare_digest(supplied.encode(), DEVICE_KEY.encode())


def handler(event, context):
    log.reset(requestId=getattr(context, "aws_request_id", None))
    if not authorised(event):
        return http.error(401, "Missing or invalid x-device-key")
    try:
        body = http.json_body(event)
        device_id, temp_c, ts = validate_reading(body, utcnow())
        battery = validate_battery(body.get("batteryPct"))
    except (ValidationError, ValueError) as exc:
        return http.error(400, str(exc))
    log.bind(deviceId=device_id)

    # 1. Update the device's live state (this reading proves it is online), returning the old state.
    update = "SET lastTempC = :t, lastSeen = :ts" + (", batteryPct = :b" if battery is not None else "")
    values = {":t": Decimal(str(temp_c)), ":ts": ts}
    if battery is not None:
        values[":b"] = Decimal(str(battery))
    try:
        old = ddb.table.update_item(
            Key=ddb.device_key(device_id),
            UpdateExpression=update + " REMOVE offlineSince",
            ConditionExpression="attribute_exists(PK)",
            ExpressionAttributeValues=values,
            ReturnValues="ALL_OLD",
        )["Attributes"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return http.error(404, f"Unknown device '{device_id}'")
        raise

    # 2. Store the reading (auto-expires after 24 h via DynamoDB TTL).
    ddb.table.put_item(Item={
        "PK": f"DEVICE#{device_id}",
        "SK": f"READING#{ts}",
        "tempC": Decimal(str(temp_c)),
        "ttl": epoch(utcnow()) + READING_TTL_SECONDS,
    })

    # 3. Evaluate the rule.
    profile = ddb.get_profile(old["profileId"])
    if profile is None:
        log.error("Device has unknown profile", profileId=old.get("profileId"))
        return http.error(500, "Device profile missing")
    min_c, max_c = profile.get("minC"), profile.get("maxC")
    now_in = rules.in_range(temp_c, min_c, max_c)
    prev_in = rules.in_range(old["lastTempC"], min_c, max_c) if "lastTempC" in old else True
    status = old.get("status", "OK")
    open_id = old.get("openIncidentId")
    on_battery = old.get("powerSource") == "BATTERY"
    result = {"deviceId": device_id, "tempC": temp_c, "ts": ts, "inRange": now_in, "status": status}

    if open_id:
        log.bind(incidentId=open_id)
        result["incidentId"] = open_id
        if old.get("offlineSince"):
            ddb.put_event(open_id, "SENSOR_BACK",
                          f"Sensor reporting again: {temp_c:g} °C ({'in' if now_in else 'OUT OF'} safe range)",
                          device_id=device_id, ts=ts, tempC=temp_c)
        if status == "CRITICAL":
            if now_in and not on_battery:
                _release_after_critical(device_id, open_id, temp_c, ts)
                result["status"] = "OK"
        elif now_in and not prev_in:
            _mark_back_in_range(device_id, open_id, temp_c, ts)
        elif not now_in and prev_in:
            _mark_out_of_range(device_id, open_id, temp_c, ts, min_c, max_c)
    elif not now_in:
        incident_id = incidents.open_incident(
            old, profile, incidents.TEMP_EXCURSION, ts,
            f"{old.get('name', device_id)} read {temp_c:g} °C — outside its safe range "
            f"({rules.describe_range(min_c, max_c)})",
            log, temp_c=temp_c,
        )
        if incident_id:
            result.update(status="GRACE", incidentId=incident_id, opened=True)

    return http.respond(202, result)


def _mark_back_in_range(device_id, incident_id, temp_c, ts):
    try:
        ddb.table.update_item(
            Key=ddb.incident_key(incident_id),
            UpdateExpression="SET recoveredAt = :ts",
            ConditionExpression="attribute_not_exists(recoveredAt)",
            ExpressionAttributeValues={":ts": ts},
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return
        raise
    ddb.put_event(incident_id, "BACK_IN_RANGE", f"Temperature back in range at {temp_c:g} °C",
                  device_id=device_id, ts=ts, tempC=temp_c)
    log.info("Back in range", tempC=temp_c)


def _mark_out_of_range(device_id, incident_id, temp_c, ts, min_c, max_c):
    ddb.table.update_item(Key=ddb.incident_key(incident_id), UpdateExpression="REMOVE recoveredAt")
    ddb.put_event(incident_id, "OUT_OF_RANGE",
                  f"Temperature out of the safe range at {temp_c:g} °C ({rules.describe_range(min_c, max_c)})",
                  device_id=device_id, ts=ts, tempC=temp_c)


def _release_after_critical(device_id, incident_id, temp_c, ts):
    """The workflow has finished as CRITICAL; once the fridge is normal again, free the device."""
    try:
        ddb.client.transact_write_items(TransactItems=[
            {"Update": {
                "TableName": ddb.TABLE_NAME,
                "Key": ddb.ser(ddb.device_key(device_id)),
                "UpdateExpression": "SET #s = :ok REMOVE openIncidentId, incidentStartedAt",
                "ConditionExpression": "openIncidentId = :id",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": ddb.ser_values({":ok": "OK", ":id": incident_id}),
            }},
            {"Update": {
                "TableName": ddb.TABLE_NAME,
                "Key": ddb.ser(ddb.incident_key(incident_id)),
                "UpdateExpression": "SET tempRestoredAt = :ts",
                "ExpressionAttributeValues": ddb.ser_values({":ts": ts}),
            }},
            {"Put": {"TableName": ddb.TABLE_NAME, "Item": ddb.ser(ddb.event_item(
                incident_id, "TEMP_RESTORED",
                f"Back to normal at {temp_c:g} °C after a critical incident — device released",
                device_id=device_id, ts=ts, tempC=temp_c))}},
        ])
        log.info("Device released after critical incident")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "TransactionCanceledException":
            raise
