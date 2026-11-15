"""Input validation for sensor readings and responder actions. Pure, unit-tested."""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from shared.timeutil import iso, parse_iso

DEVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
ACK_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{40,128}$")
INCIDENT_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,80}$")
MIN_TEMP_C = -90.0
MAX_TEMP_C = 60.0
ACTIONS = ("MOVED_TO_BACKUP", "FIXED", "NEED_HELP")


class ValidationError(ValueError):
    pass


def validate_reading(body, now: datetime) -> Tuple[str, float, str]:
    """Returns (deviceId, tempC, isoTs) or raises ValidationError."""
    if not isinstance(body, dict):
        raise ValidationError("Body must be a JSON object")
    device_id = body.get("deviceId")
    if not isinstance(device_id, str) or not DEVICE_ID_RE.match(device_id):
        raise ValidationError("deviceId must be lowercase letters, digits and dashes")
    temp = body.get("tempC")
    if isinstance(temp, bool) or not isinstance(temp, (int, float)) or not math.isfinite(temp):
        raise ValidationError("tempC must be a number")
    if temp < MIN_TEMP_C or temp > MAX_TEMP_C:
        raise ValidationError(f"tempC must be between {MIN_TEMP_C:g} and {MAX_TEMP_C:g}")
    ts_raw = body.get("ts")
    if ts_raw is None:
        ts = now
    else:
        if not isinstance(ts_raw, str):
            raise ValidationError("ts must be an ISO-8601 string")
        try:
            ts = parse_iso(ts_raw)
        except ValueError as exc:
            raise ValidationError("ts must be an ISO-8601 string") from exc
        if ts > now + timedelta(minutes=2):
            raise ValidationError("ts is in the future")
        if ts < now - timedelta(hours=1):
            raise ValidationError("ts is more than 1 hour old")
    return device_id, round(float(temp), 2), iso(ts)


EVENT_TYPES = ("POWER_LOST", "POWER_RESTORED")


def validate_battery(value) -> Optional[float]:
    """Optional batteryPct (0–100)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValidationError("batteryPct must be a number")
    if value < 0 or value > 100:
        raise ValidationError("batteryPct must be between 0 and 100")
    return round(float(value), 1)


def _validate_ts(ts_raw, now: datetime) -> datetime:
    if ts_raw is None:
        return now
    if not isinstance(ts_raw, str):
        raise ValidationError("ts must be an ISO-8601 string")
    try:
        ts = parse_iso(ts_raw)
    except ValueError as exc:
        raise ValidationError("ts must be an ISO-8601 string") from exc
    if ts > now + timedelta(minutes=2):
        raise ValidationError("ts is in the future")
    if ts < now - timedelta(hours=1):
        raise ValidationError("ts is more than 1 hour old")
    return ts


def validate_event(body, now: datetime) -> Tuple[str, str, Optional[float], str]:
    """POST /events body -> (deviceId, type, batteryPct, isoTs) or raises ValidationError."""
    if not isinstance(body, dict):
        raise ValidationError("Body must be a JSON object")
    device_id = body.get("deviceId")
    if not isinstance(device_id, str) or not DEVICE_ID_RE.match(device_id):
        raise ValidationError("deviceId must be lowercase letters, digits and dashes")
    event_type = body.get("type")
    if event_type not in EVENT_TYPES:
        raise ValidationError(f"type must be one of {', '.join(EVENT_TYPES)}")
    return device_id, event_type, validate_battery(body.get("batteryPct")), iso(_validate_ts(body.get("ts"), now))


def validate_response(body, incident_id: str) -> Tuple[str, str, str]:
    """Returns (ackCode, action, note) or raises ValidationError."""
    if not isinstance(incident_id, str) or not INCIDENT_ID_RE.match(incident_id):
        raise ValidationError("Invalid incident id")
    if not isinstance(body, dict):
        raise ValidationError("Body must be a JSON object")
    code = body.get("ackCode")
    if not isinstance(code, str) or not ACK_CODE_RE.match(code):
        raise ValidationError("ackCode is missing or malformed")
    action = body.get("action")
    if action not in ACTIONS:
        raise ValidationError(f"action must be one of {', '.join(ACTIONS)}")
    note = body.get("note") or ""
    if not isinstance(note, str):
        raise ValidationError("note must be a string")
    note = note.strip()[:280]
    return code, action, note


def safe_int(value, default: int, lo: int, hi: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def optional_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return iso(parse_iso(value))
    except ValueError:
        return None
