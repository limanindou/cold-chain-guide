"""Step Functions task: has the device recovered? Type-specific rule:

  TEMP_EXCURSION : latest reading back in range (and the sensor is reporting)
  POWER_LOST     : back on mains AND temperature in range
  SENSOR_OFFLINE : reporting again AND temperature in range (it may have warmed while silent)
"""
from __future__ import annotations

from shared import ddb, rules
from shared.log import Logger
from shared.timeutil import parse_iso, utcnow

log = Logger("check_recovered")


def evaluate(device: dict, incident_type: str, min_c, max_c, offline_after: float, now) -> dict:
    """Pure function (unit-tested)."""
    temp = device.get("lastTempC")
    last_seen = device.get("lastSeen")
    online = bool(last_seen) and (now - parse_iso(last_seen)).total_seconds() <= offline_after
    power = device.get("powerSource", "MAINS")
    temp_ok = temp is not None and rules.in_range(temp, min_c, max_c)
    recovered = online and temp_ok and (power != "BATTERY" if incident_type == "POWER_LOST" else True)
    return {
        "recovered": bool(recovered),
        "latestTempC": float(temp) if temp is not None else None,
        "powerSource": power,
        "online": online,
        "lastSeen": last_seen,
    }


def handler(event, context):
    log.reset(incidentId=event.get("incidentId"), deviceId=event.get("deviceId"))
    device = ddb.get_item(ddb.device_key(event["deviceId"]), consistent=True) or {}
    result = evaluate(device, event.get("type", "TEMP_EXCURSION"), event.get("minC"), event.get("maxC"),
                      float(event.get("offlineAfterSeconds") or 300), utcnow())
    log.info("Checked recovery", **result)
    return result
