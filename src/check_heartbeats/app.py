"""Scheduled every minute (EventBridge Scheduler) — signal #3: the sensor went silent.

This is the ONLY thing that runs while every fridge is healthy: one small Lambda per
minute and one query (~43,000 invocations a month, inside the Lambda free tier). Silence
can only be detected by something that checks, so this is the minimum possible cost.

A device is silent when lastSeen is older than its profile's offlineAfterSeconds (scaled
by TIME_SCALE). Each silence is flagged once (offlineSince); the next reading clears it.

DEMO_MODE guard: if EVERY sensor is silent at once, the browser simulator has simply been
closed or paused, so nothing is opened (in production a site-wide silence is a real event).
"""
from __future__ import annotations

import os

from botocore.exceptions import ClientError

from shared import ddb, incidents
from shared.log import Logger
from shared.timescale import get_time_scale, scale_seconds
from shared.timeutil import now_iso, parse_iso, utcnow

log = Logger("check_heartbeats")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
# Never call a sensor silent after less than this (scaled thresholds get tiny at TIME_SCALE=45,
# and real networks jitter by several seconds). Keep in sync with the state machine Init and the UI.
OFFLINE_MIN_SECONDS = 20


def silent_devices(devices: list, profiles: dict, now, time_scale: int) -> list:
    """Pure helper: devices whose last reading is older than their (scaled) offline threshold."""
    out = []
    for d in devices:
        if not d.get("lastSeen"):
            continue  # never reported: not commissioned yet
        p = profiles.get(d.get("profileId"), {})
        after = scale_seconds(p.get("offlineAfterSeconds", incidents.DEFAULTS["offlineAfterSeconds"]), time_scale, minimum=OFFLINE_MIN_SECONDS)
        if (now - parse_iso(d["lastSeen"])).total_seconds() > after:
            out.append(d)
    return out


def handler(event, context):
    log.reset(requestId=getattr(context, "aws_request_id", None))
    now = utcnow()
    devices = ddb.list_entities("DEVICES")
    profiles = ddb.profiles_by_id()
    reporting = [d for d in devices if d.get("lastSeen")]
    silent = silent_devices(devices, profiles, now, get_time_scale())

    if DEMO_MODE and reporting and len(silent) == len(reporting):
        log.info("All sensors silent — demo simulator is closed or paused; skipping", devices=len(silent))
        return {"silent": len(silent), "opened": 0, "skipped": True}

    opened = 0
    for d in silent:
        if d.get("offlineSince"):
            continue  # this silence was already handled
        device_id = d["deviceId"]
        log.bind(deviceId=device_id)
        try:  # flag once, even if two scheduler runs overlap
            ddb.table.update_item(
                Key=ddb.device_key(device_id),
                UpdateExpression="SET offlineSince = :since",
                ConditionExpression="attribute_not_exists(offlineSince) AND lastSeen = :since",
                ExpressionAttributeValues={":since": d["lastSeen"]},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                continue  # a reading arrived meanwhile, or already flagged
            raise
        last = d["lastSeen"][11:19]
        detail = f"No reading from {d.get('name', device_id)} since {last} UTC — sensor silent"
        if d.get("openIncidentId"):
            ddb.put_event(d["openIncidentId"], "SENSOR_OFFLINE", detail, device_id=device_id)
        else:
            profile = profiles.get(d["profileId"]) or ddb.get_profile(d["profileId"])
            if incidents.open_incident(d, profile, incidents.SENSOR_OFFLINE, now_iso(), detail, log,
                                       temp_c=float(d["lastTempC"]) if d.get("lastTempC") is not None else None):
                opened += 1
    log.info("Heartbeat check done", devices=len(devices), silent=len(silent), opened=opened)
    return {"silent": len(silent), "opened": opened}
