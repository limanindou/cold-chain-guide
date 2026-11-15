import hashlib

from shared.evidence import build_report, canonical_bytes

INCIDENT = {
    "incidentId": "bloodbank-01-20261115T020000-abc123", "deviceId": "bloodbank-01", "deviceName": "Blood bank",
    "status": "RESOLVED", "startedAt": "2026-11-15T02:00:00.000Z", "resolvedAt": "2026-11-15T02:01:00.000Z",
    "minC": 2, "maxC": 6, "ackedByName": "Manager Pieter", "ackedAction": "MOVED_TO_BACKUP",
}
EVENTS = [
    {"ts": "2026-11-15T02:00:00.000Z", "type": "STARTED", "actor": "system", "detail": "start"},
    {"ts": "2026-11-15T02:00:20.000Z", "type": "NOTIFIED", "actor": "nurse-on-duty", "level": 0},
    {"ts": "2026-11-15T02:00:40.000Z", "type": "ACKED", "actor": "facility-manager", "detail": "moved"},
]
READINGS = [
    {"ts": "2026-11-15T01:59:50.000Z", "tempC": 4.0},  # before the incident -> excluded
    {"ts": "2026-11-15T02:00:00.000Z", "tempC": 7.0},
    {"ts": "2026-11-15T02:00:30.000Z", "tempC": 9.5},
    {"ts": "2026-11-15T02:00:50.000Z", "tempC": 5.0},
]
GENERATED = "2026-11-15T02:01:05.000Z"


def test_summary():
    r = build_report(INCIDENT, EVENTS, READINGS, GENERATED)
    s = r["summary"]
    assert s["outOfRangeSeconds"] == 50.0
    assert (s["minTempC"], s["maxTempC"]) == (5.0, 9.5)
    assert s["readingsCount"] == 3
    assert s["responders"][0]["responderId"] == "nurse-on-duty"
    assert r["incident"]["safeRange"]["text"] == "2 to 6 °C"


def test_fingerprint_is_deterministic_and_tamper_evident():
    a = canonical_bytes(build_report(INCIDENT, EVENTS, READINGS, GENERATED))
    b = canonical_bytes(build_report(INCIDENT, EVENTS, READINGS, GENERATED))
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()
    tampered = a.replace(b'"maxTempC":9.5', b'"maxTempC":6.0')
    assert tampered != a
    assert hashlib.sha256(tampered).hexdigest() != hashlib.sha256(a).hexdigest()
