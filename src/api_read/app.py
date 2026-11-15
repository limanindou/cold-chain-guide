"""Read-only API: GET /config, /dashboard, /devices, /devices/{id}/readings, /incidents,
/incidents/{id}, /profiles, /responders.

/dashboard bundles everything the live dashboard needs into ONE request per poll
(devices, incremental readings, recent incidents and events), keeping the UI cheap.
Responder emails are never returned. Pending ack codes are only returned in DEMO_MODE so
the on-screen "responder phones" can act; in production they only travel by email/SMS.
"""
from __future__ import annotations

import os
from datetime import timedelta

from shared import ddb, http
from shared.log import Logger
from shared.timeutil import iso, now_iso, parse_iso, plus, utcnow
from shared.timescale import get_time_scale
from shared.validation import INCIDENT_ID_RE, DEVICE_ID_RE, optional_iso, safe_int

log = Logger("api_read")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
REGION = os.environ.get("AWS_REGION", "us-east-1")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
EVENT_INCIDENTS = 6


def handler(event, context):
    route = event.get("routeKey", "")
    log.reset(route=route, requestId=getattr(context, "aws_request_id", None))
    try:
        if route == "GET /config":
            return http.respond(200, _config())
        if route == "GET /dashboard":
            return http.respond(200, _dashboard(event))
        if route == "GET /devices":
            return http.respond(200, {"devices": _devices()})
        if route == "GET /devices/{id}/readings":
            device_id = http.path_param(event, "id")
            if not DEVICE_ID_RE.match(device_id or ""):
                return http.error(400, "Invalid device id")
            minutes = safe_int(http.query(event, "minutes"), 10, 1, 24 * 60)
            since = optional_iso(http.query(event, "since")) or iso(utcnow() - timedelta(minutes=minutes))
            return http.respond(200, {"deviceId": device_id, "readings": _readings(device_id, since)})
        if route == "GET /incidents":
            limit = safe_int(http.query(event, "limit"), 20, 1, 100)
            return http.respond(200, {"incidents": [_incident_view(i) for i in ddb.recent_incidents(limit)]})
        if route == "GET /incidents/{id}":
            incident_id = http.path_param(event, "id")
            if not INCIDENT_ID_RE.match(incident_id or ""):
                return http.error(400, "Invalid incident id")
            detail = _incident_detail(incident_id)
            return http.respond(200, detail) if detail else http.error(404, "Incident not found")
        if route == "GET /profiles":
            return http.respond(200, {"profiles": _profiles()})
        if route == "GET /responders":
            return http.respond(200, {"responders": _responders()})
    except Exception as exc:
        log.exception("Read failed", exc)
        return http.error(500, "Internal error")
    return http.error(404, "Not found")


def _config():
    return {
        "timeScale": get_time_scale(),
        "demoMode": DEMO_MODE,
        "region": REGION,
        "stateMachineArn": STATE_MACHINE_ARN,
    }


def _devices():
    devices = [ddb.plain(d) for d in ddb.list_entities("DEVICES")]
    return sorted(devices, key=lambda d: d.get("order", 99))


def _profiles():
    return sorted((ddb.plain(p) for p in ddb.profiles_by_id().values()), key=lambda p: p.get("order", 99))


def _responders():
    return [{k: v for k, v in ddb.plain(r).items() if k != "email"} for r in ddb.responders_by_id().values()]


def _readings(device_id: str, since_iso: str, until_iso: str = "~"):
    items = ddb.readings_between(device_id, since_iso, until_iso)
    out = []
    for r in items:
        ts = r["SK"][len("READING#"):]
        if ts > since_iso:  # strictly newer, so incremental polls never duplicate
            out.append({"ts": ts, "tempC": float(r["tempC"])})
    return out


def _console_url(execution_arn: str | None) -> str | None:
    if not execution_arn:
        return None
    return (f"https://{REGION}.console.aws.amazon.com/states/home?region={REGION}"
            f"#/v2/executions/details/{execution_arn}")


def _incident_view(item: dict) -> dict:
    inc = ddb.plain(item)
    pending = inc.get("pendingAck")
    if pending and not DEMO_MODE:
        inc["pendingAck"] = {k: v for k, v in pending.items() if k != "code"}
    if inc.get("evidenceKey"):
        inc["evidencePath"] = "/" + inc["evidenceKey"]
        inc["evidenceHtmlPath"] = "/" + inc.get("evidenceHtmlKey", "")
    inc["consoleUrl"] = _console_url(inc.get("executionArn"))
    return inc


def _dashboard(event):
    server_time = now_iso()
    since = optional_iso(http.query(event, "since"))
    window_start = iso(utcnow() - timedelta(minutes=safe_int(http.query(event, "minutes"), 10, 1, 60)))
    if not since or since < window_start:
        since = window_start
    devices = _devices()
    readings = {d["deviceId"]: _readings(d["deviceId"], since) for d in devices}
    incidents = [_incident_view(i) for i in ddb.recent_incidents(12)]
    events = []
    for inc in incidents[:EVENT_INCIDENTS]:
        for e in ddb.incident_events(inc["incidentId"]):
            e = ddb.plain(e)
            e.setdefault("deviceId", inc.get("deviceId"))
            e["deviceName"] = inc.get("deviceName")
            events.append(e)
    events.sort(key=lambda e: e["ts"], reverse=True)
    return {
        "serverTime": server_time,
        "since": since,
        "devices": devices,
        "readings": readings,
        "incidents": incidents,
        "events": events[:60],
        "profiles": _profiles(),
        "responders": _responders(),
        "config": _config(),
    }


def _incident_detail(incident_id: str):
    item = ddb.get_item(ddb.incident_key(incident_id), consistent=True)
    if not item:
        return None
    inc = _incident_view(item)
    events = sorted((ddb.plain(e) for e in ddb.incident_events(incident_id)), key=lambda e: e["ts"])
    started = parse_iso(inc["startedAt"])
    end = inc.get("resolvedAt") or inc.get("tempRestoredAt")
    until = iso(plus(parse_iso(end), 60)) if end else "~"
    device = ddb.plain(ddb.get_item(ddb.device_key(inc["deviceId"])) or {})
    return {
        "incident": inc,
        "events": events,
        "readings": _readings(inc["deviceId"], iso(plus(started, -90)), until),
        "device": device,
        "profile": ddb.plain(ddb.get_profile(inc["profileId"]) or {}),
        "responders": _responders(),
        "config": _config(),
    }
