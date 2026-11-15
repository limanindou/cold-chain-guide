"""Optional CLI sensor simulator (no dependencies). The browser simulator does the same thing.

  python scripts/simulate.py --api https://xxxx.execute-api.us-east-1.amazonaws.com --key <DeviceApiKey> \
      --device bloodbank-01 --baseline 4 --mode powercut

Modes: normal (hover around baseline), powercut (warm steadily), door (brief spike, then recover).
Ctrl+C to stop.
"""
from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request


def post(api: str, key: str, device: str, temp: float) -> str:
    req = urllib.request.Request(
        f"{api.rstrip('/')}/readings",
        data=json.dumps({"deviceId": device, "tempC": round(temp, 2)}).encode(),
        headers={"content-type": "application/json", "x-device-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read()).get("status", "?")
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}: {exc.read().decode()[:120]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--baseline", type=float, default=5.0)
    ap.add_argument("--max", type=float, default=8.0, help="profile maxC (for the door spike)")
    ap.add_argument("--mode", choices=["normal", "powercut", "door"], default="normal")
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()

    temp, step = args.baseline, 0
    door = [args.baseline + (args.max - args.baseline) * 0.8, args.max + 1.6, args.max + 1.0]
    while True:
        if args.mode == "powercut":
            temp = min(24.0, temp + 0.45)
        elif args.mode == "door" and step < len(door):
            temp = door[step]
        else:
            temp += (args.baseline - temp) * 0.35 + random.uniform(-0.06, 0.06)
        step += 1
        status = post(args.api, args.key, args.device, temp)
        print(f"{time.strftime('%H:%M:%S')}  {args.device:<20} {temp:6.2f} °C  -> {status}")
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
