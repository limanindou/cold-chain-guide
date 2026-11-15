"""POST /events — sensor power events (signal #2).

{deviceId, type: POWER_LOST | POWER_RESTORED, batteryPct?, ts?}

POWER_LOST is an EARLY WARNING: the sensor is on its backup battery, and the fridge has
stopped cooling, but the temperature is probably still fine. Opening the incident now buys
the responders the time it takes the fridge to warm up.
"""
from __future__ import annotations

from decimal import Decimal

from botocore.exceptions import ClientError

from shared import ddb, http, incidents
from shared.log import Logger
from shared.timeutil import utcnow
from shared.validation import ValidationError, validate_event
from ingest_reading.app import authorised

log = Logger("ingest_event")


def handler(event, context):
    log.reset(requestId=getattr(context, "aws_request_id", None))
    if not authorised(event):
        return http.error(401, "Missing or invalid x-device-key")
    try:
        device_id, event_type, battery, ts = validate_event(http.json_body(event), utcnow())
    except (ValidationError, ValueError) as exc:
        return http.error(400, str(exc))
    log.bind(deviceId=device_id, eventType=event_type)

    source = "BATTERY" if event_type == "POWER_LOST" else "MAINS"
    update = "SET powerSource = :p, powerChangedAt = :ts, lastSeen = :ts"
    values = {":p": source, ":ts": ts}
    if battery is not None:
        update += ", batteryPct = :b"
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

    name = old.get("name", device_id)
    open_id = old.get("openIncidentId")
    was = old.get("powerSource", "MAINS")
    result = {"deviceId": device_id, "type": event_type, "powerSource": source}
    temp = old.get("lastTempC")
    temp_txt = f" ({float(temp):g} °C)" if temp is not None else ""

    if event_type == "POWER_LOST":
        if was == "BATTERY":
            return http.respond(202, {**result, "duplicate": True})
        detail = f"{name} lost mains power — sensor on battery" + (f" {battery:g}%" if battery is not None else "") + temp_txt
        if open_id:
            log.bind(incidentId=open_id)
            ddb.put_event(open_id, "POWER_LOST", detail, device_id=device_id, ts=ts)
            result["incidentId"] = open_id
        else:
            profile = ddb.get_profile(old["profileId"])
            incident_id = incidents.open_incident(
                old, profile, incidents.POWER_LOST, ts, detail + " — early warning before it warms up",
                log, temp_c=float(temp) if temp is not None else None,
            )
            if incident_id:
                result.update(incidentId=incident_id, opened=True)
    else:  # POWER_RESTORED
        if open_id and was == "BATTERY":
            log.bind(incidentId=open_id)
            ddb.table.update_item(Key=ddb.incident_key(open_id), UpdateExpression="SET powerRestoredAt = :ts",
                                  ExpressionAttributeValues={":ts": ts})
            ddb.put_event(open_id, "POWER_RESTORED", f"Mains power restored{temp_txt}", device_id=device_id, ts=ts)
            result["incidentId"] = open_id

    log.info("Power event processed", **result)
    return http.respond(202, result)
