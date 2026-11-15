from datetime import datetime, timedelta, timezone

import pytest

from shared.validation import ValidationError, validate_reading, validate_response

NOW = datetime(2026, 11, 15, 20, 0, tzinfo=timezone.utc)
CODE = "A" * 43


def test_valid_reading_defaults_ts_to_now():
    device, temp, ts = validate_reading({"deviceId": "bloodbank-01", "tempC": 4.123}, NOW)
    assert device == "bloodbank-01" and temp == 4.12 and ts == "2026-11-15T20:00:00.000Z"


def test_explicit_ts_normalised():
    _, _, ts = validate_reading({"deviceId": "ab", "tempC": 1, "ts": "2026-11-15T19:59:00+00:00"}, NOW)
    assert ts == "2026-11-15T19:59:00.000Z"


@pytest.mark.parametrize("body", [
    None, [], {}, {"deviceId": "x"}, {"deviceId": "Bad Id", "tempC": 1},
    {"deviceId": "ab", "tempC": "5"}, {"deviceId": "ab", "tempC": True},
    {"deviceId": "ab", "tempC": 61}, {"deviceId": "ab", "tempC": -91},
    {"deviceId": "ab", "tempC": float("nan")},
    {"deviceId": "ab", "tempC": 5, "ts": "yesterday"},
    {"deviceId": "ab", "tempC": 5, "ts": (NOW + timedelta(minutes=10)).isoformat()},
    {"deviceId": "ab", "tempC": 5, "ts": (NOW - timedelta(hours=2)).isoformat()},
])
def test_invalid_readings(body):
    with pytest.raises(ValidationError):
        validate_reading(body, NOW)


def test_valid_response():
    body = {"ackCode": CODE, "action": "FIXED", "note": "  door shut "}
    assert validate_response(body, "inc-1") == (CODE, "FIXED", "door shut")


@pytest.mark.parametrize("body,incident", [
    ({"ackCode": CODE, "action": "PANIC"}, "inc-1"),
    ({"ackCode": "short", "action": "FIXED"}, "inc-1"),
    ({"ackCode": CODE, "action": "FIXED"}, "../etc"),
    ({"action": "FIXED"}, "inc-1"),
])
def test_invalid_responses(body, incident):
    with pytest.raises(ValidationError):
        validate_response(body, incident)


def test_valid_power_event():
    from shared.validation import ValidationError, validate_event
    assert validate_event({"deviceId": "bloodbank-01", "type": "POWER_LOST", "batteryPct": 97}, NOW) == (
        "bloodbank-01", "POWER_LOST", 97.0, "2026-11-15T20:00:00.000Z")
    assert validate_event({"deviceId": "ab", "type": "POWER_RESTORED"}, NOW)[2] is None


@pytest.mark.parametrize("body", [
    {"deviceId": "ab", "type": "EXPLODED"}, {"deviceId": "ab"}, {"type": "POWER_LOST"},
    {"deviceId": "ab", "type": "POWER_LOST", "batteryPct": 120},
    {"deviceId": "ab", "type": "POWER_LOST", "batteryPct": "full"},
])
def test_invalid_power_events(body):
    from shared.validation import ValidationError, validate_event
    with pytest.raises(ValidationError):
        validate_event(body, NOW)
