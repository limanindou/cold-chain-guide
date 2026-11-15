"""Evidence report assembly. Pure functions (no AWS), unit-tested."""
from __future__ import annotations

import json

from shared import rules
from shared.timeutil import iso, parse_iso

SCHEMA = "coldchain-guard/evidence@1"
DISCLAIMER = ("Temperature ranges are configurable examples. Decide whether to use or discard stock "
              "according to official guidance (WHO, national health department, blood service, manufacturer).")


def build_report(incident: dict, events: list, readings: list, generated_at: str) -> dict:
    """Pure function: assemble the evidence document (unit-testable)."""
    min_c, max_c = incident.get("minC"), incident.get("maxC")
    started = parse_iso(incident["startedAt"])
    end_iso = incident.get("resolvedAt") or generated_at
    end = parse_iso(end_iso)
    series = [(parse_iso(r["ts"]), float(r["tempC"])) for r in readings]
    during = [(t, v) for t, v in series if started <= t <= end]
    lo, hi = rules.min_max(v for _, v in during)
    out_s = rules.out_of_range_seconds(during, min_c, max_c, end=end)
    alerted = [e for e in events if e["type"] == "NOTIFIED"]
    acted = [e for e in events if e["type"] in ("ACKED", "NEED_HELP")]
    return {
        "schema": SCHEMA,
        "generatedAt": generated_at,
        "incident": {
            "incidentId": incident["incidentId"],
            "status": incident.get("status"),
            "deviceId": incident.get("deviceId"),
            "deviceName": incident.get("deviceName"),
            "location": incident.get("location"),
            "profileId": incident.get("profileId"),
            "profileLabel": incident.get("profileLabel"),
            "type": incident.get("type", "TEMP_EXCURSION"),
            "powerRestoredAt": incident.get("powerRestoredAt"),
            "safeRange": {"minC": min_c, "maxC": max_c, "text": rules.describe_range(min_c, max_c)},
            "startedAt": incident["startedAt"],
            "endedAt": end_iso,
            "executionArn": incident.get("executionArn"),
        },
        "summary": {
            "outOfRangeSeconds": round(out_s, 1),
            "minTempC": lo,
            "maxTempC": hi,
            "readingsCount": len(during),
            "responders": [{"responderId": e.get("actor"), "at": e["ts"], "level": e.get("level")} for e in alerted],
            "actions": [{"responderId": e.get("actor"), "type": e["type"], "at": e["ts"], "detail": e.get("detail")}
                        for e in acted],
            "ackedBy": incident.get("ackedByName"),
            "ackedAction": incident.get("ackedAction"),
        },
        "timeline": [{"ts": e["ts"], "type": e["type"], "actor": e.get("actor"), "detail": e.get("detail")}
                     for e in events],
        "readings": [{"ts": iso(t), "tempC": v} for t, v in during],
        "disclaimer": DISCLAIMER,
    }


def canonical_bytes(report: dict) -> bytes:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
