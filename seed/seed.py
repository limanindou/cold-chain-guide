"""Load profiles, devices and responders into the ColdChain Guard table.

Usage:
  python seed/seed.py --stack coldchain-guard                       # table name from stack outputs
  python seed/seed.py --table <TableName> --region us-east-1
  python seed/seed.py --stack coldchain-guard --default-email you@example.com
  python seed/seed.py --stack coldchain-guard \
      --email nurse-on-duty=you+nurse@example.com --email facility-manager=you+manager@example.com

Emails must be SES-verified while your account is in the SES sandbox.
Re-running is safe: items are overwritten, device live state (status, last reading) is reset.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from decimal import Decimal

import boto3

HERE = pathlib.Path(__file__).parent


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"), parse_float=Decimal)


def table_from_stack(stack: str, region: str | None) -> str:
    cfn = boto3.client("cloudformation", region_name=region)
    outputs = cfn.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    return next(o["OutputValue"] for o in outputs if o["OutputKey"] == "TableName")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table")
    ap.add_argument("--stack", default=None)
    ap.add_argument("--region", default=None)
    ap.add_argument("--default-email", default="", help="Email for every responder without one")
    ap.add_argument("--email", action="append", default=[], help="responderId=address (repeatable)")
    args = ap.parse_args()

    table_name = args.table or table_from_stack(args.stack or "coldchain-guard", args.region)
    table = boto3.resource("dynamodb", region_name=args.region).Table(table_name)
    emails = dict(e.split("=", 1) for e in args.email)

    with table.batch_writer() as batch:
        for p in load("profiles.json"):
            item = {k: v for k, v in p.items() if v is not None}
            batch.put_item(Item={"PK": f"PROFILE#{p['profileId']}", "SK": "META",
                                 "GSI1PK": "PROFILES", "GSI1SK": p["profileId"], **item})
        for r in load("responders.json"):
            r["email"] = emails.get(r["responderId"]) or r.get("email") or args.default_email
            batch.put_item(Item={"PK": f"RESPONDER#{r['responderId']}", "SK": "META",
                                 "GSI1PK": "RESPONDERS", "GSI1SK": r["responderId"], **r})
        for d in load("devices.json"):
            batch.put_item(Item={"PK": f"DEVICE#{d['deviceId']}", "SK": "META",
                                 "GSI1PK": "DEVICES", "GSI1SK": d["deviceId"], "status": "OK",
                                 "powerSource": "MAINS", "batteryPct": 100, **d})
    print(f"Seeded {table_name}: 6 profiles, 6 responders, 4 devices.")
    missing = [r["responderId"] for r in load("responders.json")
               if not (emails.get(r["responderId"]) or args.default_email)]
    if missing:
        print("Note: no email for", ", ".join(missing), "— they get in-app alerts only.")


if __name__ == "__main__":
    main()
