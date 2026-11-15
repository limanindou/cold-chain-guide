"""End-to-end smoke test against a DEPLOYED stack (TimeScale=45, DemoMode=true). No dependencies.

  python scripts/smoke_test.py --api https://xxxx.execute-api.us-east-1.amazonaws.com \
      --site https://dxxxx.cloudfront.net --key <DeviceApiKey>

Plays the sensors itself (posts baseline readings for every device every 2 s) and checks:
  1. door spike on insulin-home-01 -> RECOVERED, never NOTIFIED            (grace period)
  2. power cut on bloodbank-01 -> POWER_LOST incident before temp leaves range,
     nurse NOTIFIED, no answer -> ESCALATED to manager, manager acks once,
     second tap -> ALREADY_HANDLED, restore -> RESOLVED + evidence hash matches (CloudFront)
  3. clinic-vaccine-01 goes silent -> SENSOR_OFFLINE incident; resumes -> SENSOR_BACK
Finishes with a demo reset. Sends real SES emails if the stack has a sender configured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = {"clinic-vaccine-01": 5.0, "bloodbank-01": 4.0, "insulin-home-01": 5.0, "plasma-01": -30.0}


class Api:
    def __init__(self, api, key):
        self.api, self.key = api.rstrip("/"), key

    def call(self, method, path, body=None, auth=False):
        headers = {"content-type": "application/json"}
        if auth:
            headers["x-device-key"] = self.key
        req = urllib.request.Request(self.api + path, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


class Sensors(threading.Thread):
    """Background 'browser simulator': one reading per device every 2 s."""

    def __init__(self, api):
        super().__init__(daemon=True)
        self.api, self.temp, self.silent, self.mode, self.stop = api, dict(BASE), set(), {}, False

    def run(self):
        while not self.stop:
            for dev, base in BASE.items():
                mode = self.mode.get(dev, "normal")
                t = self.temp[dev]
                if mode == "warm":
                    t += 0.6
                elif isinstance(mode, list):
                    t = mode.pop(0) if mode else base
                    if not mode:
                        self.mode[dev] = "normal"
                else:
                    t += (base - t) * 0.5 + random.uniform(-0.05, 0.05)
                self.temp[dev] = t
                if dev not in self.silent:  # in parallel, like the browser simulator
                    threading.Thread(target=self.api.call, daemon=True,
                                     args=("POST", "/readings", {"deviceId": dev, "tempC": round(t, 2)}, True)).start()
            time.sleep(2)


def incident_events(api, incident_id):
    _, d = api.call("GET", f"/incidents/{incident_id}")
    return d.get("incident", {}), [e["type"] for e in d.get("events", [])]


def wait_for(desc, fn, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = fn()
        if v:
            print(f"   ✓ {desc} ({time.time() - t0:.0f}s)")
            return v
        time.sleep(2)
    raise AssertionError(f"timed out waiting for: {desc}")


def open_incident(api, device):
    _, d = api.call("GET", "/dashboard")
    dev = next(x for x in d["devices"] if x["deviceId"] == device)
    return dev.get("openIncidentId")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--key", required=True)
    a = ap.parse_args()
    api = Api(a.api, a.key)
    results = []

    def check(name, fn):
        print(f"\n▶ {name}")
        try:
            fn()
            results.append((name, "PASS"))
        except Exception as exc:  # noqa: BLE001
            print(f"   ✗ {exc}")
            results.append((name, f"FAIL: {exc}"))

    print("Resetting demo…")
    assert api.call("POST", "/demo/reset", {"clearReadings": True}, auth=True)[0] == 200
    sensors = Sensors(api)
    sensors.start()
    time.sleep(8)

    def door():
        sensors.mode["insulin-home-01"] = [7.0, 9.6, 9.0]
        inc = wait_for("door spike opens a grace incident", lambda: open_incident(api, "insulin-home-01"), 30)
        wait_for("closes as RECOVERED", lambda: incident_events(api, inc)[0].get("status") == "RECOVERED", 90)
        types = incident_events(api, inc)[1]
        assert "NOTIFIED" not in types, f"door spike alerted someone: {types}"
        print("   ✓ nobody was alerted")

    def power_and_escalation():
        s, body = api.call("POST", "/events", {"deviceId": "bloodbank-01", "type": "POWER_LOST", "batteryPct": 97}, auth=True)
        assert s == 202 and body.get("opened"), body
        inc = body["incidentId"]
        inc_meta, _ = incident_events(api, inc)
        assert inc_meta["type"] == "POWER_LOST"
        assert sensors.temp["bloodbank-01"] <= 6, "temperature already out of range"
        print("   ✓ POWER_LOST incident opened while temperature still in range")
        sensors.mode["bloodbank-01"] = "warm"
        wait_for("nurse alerted", lambda: (incident_events(api, inc)[0].get("pendingAck") or {}).get("responderId") == "nurse-on-duty", 60)
        wait_for("silence escalates to the manager",
                 lambda: (incident_events(api, inc)[0].get("pendingAck") or {}).get("responderId") == "facility-manager", 60)
        code = incident_events(api, inc)[0]["pendingAck"]["code"]
        s, r = api.call("POST", f"/incidents/{inc}/respond", {"ackCode": code, "action": "MOVED_TO_BACKUP"})
        assert s == 200 and r["result"] == "OK", r
        print("   ✓ manager acknowledged (Moved to backup cooler)")
        s, r = api.call("POST", f"/incidents/{inc}/respond", {"ackCode": code, "action": "FIXED"})
        assert s == 409 and r["result"] == "ALREADY_HANDLED", r
        print("   ✓ second tap -> ALREADY_HANDLED")
        api.call("POST", "/events", {"deviceId": "bloodbank-01", "type": "POWER_RESTORED"}, auth=True)
        sensors.mode["bloodbank-01"] = "normal"
        wait_for("RESOLVED after power + temperature are back",
                 lambda: incident_events(api, inc)[0].get("status") == "RESOLVED", 150)
        meta = wait_for("evidence sealed", lambda: (lambda m: m if m.get("evidenceSha256") else None)(incident_events(api, inc)[0]), 60)
        with urllib.request.urlopen(a.site.rstrip("/") + meta["evidencePath"], timeout=15) as r:
            digest = hashlib.sha256(r.read()).hexdigest()
        assert digest == meta["evidenceSha256"], "evidence hash mismatch"
        print("   ✓ evidence downloaded via CloudFront, SHA-256 matches")
        types = incident_events(api, inc)[1]
        for t in ("STARTED", "NOTIFIED", "ESCALATED", "ACKED", "POWER_RESTORED", "RESOLVED", "EVIDENCE_SEALED"):
            assert t in types, f"missing {t} in {types}"
        print("   ✓ timeline complete")

    def silence():
        sensors.silent.add("clinic-vaccine-01")
        inc = wait_for("silent sensor detected by the 1-minute heartbeat",
                       lambda: open_incident(api, "clinic-vaccine-01"), 150)
        assert incident_events(api, inc)[0]["type"] == "SENSOR_OFFLINE"
        print("   ✓ SENSOR_OFFLINE incident")
        sensors.silent.discard("clinic-vaccine-01")
        wait_for("readings resume -> SENSOR_BACK", lambda: "SENSOR_BACK" in incident_events(api, inc)[1], 30)

    check("1. Door spike never alarms (grace period)", door)
    check("2. Power cut -> early warning -> escalation -> ack once -> resolved -> evidence", power_and_escalation)
    check("3. Silent sensor detected", silence)

    sensors.stop = True
    api.call("POST", "/demo/reset", {"clearReadings": False}, auth=True)
    print("\n" + "\n".join(f"{r:<5} {n}" if r == "PASS" else f"FAIL  {n}: {r}" for n, r in results))
    sys.exit(0 if all(r == "PASS" for _, r in results) else 1)


if __name__ == "__main__":
    main()
