"""End-to-end Lambda flow against mocked AWS (moto). Skipped unless moto + boto3 are installed:
    pip install boto3 "moto[dynamodb,s3,stepfunctions]" pytest
The Step Functions workflow itself is not executed here; its tasks are called directly.
"""
import hashlib
import importlib
import json
import os
import sys

import pytest

moto = pytest.importorskip("moto")
boto3 = pytest.importorskip("boto3")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = "test-device-key-123456"


class Ctx:
    aws_request_id = "req-1"


def http_event(route, body=None, path=None, query=None, headers=None):
    return {
        "routeKey": route,
        "headers": headers or {},
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": path or {},
        "queryStringParameters": query or {},
    }


@pytest.fixture()
def env(monkeypatch):
    for k, v in {
        "AWS_DEFAULT_REGION": "us-east-1", "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "x", "AWS_SECRET_ACCESS_KEY": "x",
        "TABLE_NAME": "ColdChainTable", "EVIDENCE_BUCKET": "evidence-bucket",
        "DEVICE_KEY": KEY, "DEMO_MODE": "true", "TIME_SCALE": "45",
    }.items():
        monkeypatch.setenv(k, v)
    with moto.mock_aws():
        ddb = boto3.client("dynamodb")
        ddb.create_table(
            TableName="ColdChainTable", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("PK", "SK", "GSI1PK", "GSI1SK")],
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[{
                "IndexName": "GSI1",
                "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"}, {"AttributeName": "GSI1SK", "KeyType": "RANGE"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
        )
        boto3.client("s3").create_bucket(Bucket="evidence-bucket")
        sm = boto3.client("stepfunctions").create_state_machine(
            name="test-incident", roleArn="arn:aws:iam::123456789012:role/x",
            definition=json.dumps({"StartAt": "A", "States": {"A": {"Type": "Pass", "End": True}}}),
        )
        monkeypatch.setenv("STATE_MACHINE_ARN", sm["stateMachineArn"])

        # seed
        sys.argv = ["seed.py", "--table", "ColdChainTable", "--region", "us-east-1"]
        sys.path.insert(0, os.path.join(ROOT, "seed"))
        import seed as seed_mod
        importlib.reload(seed_mod).main()

        # (re)import Lambda modules inside the mock so their clients are mocked
        for name in list(sys.modules):
            if name.startswith(("shared", "ingest_reading", "ingest_event", "check_heartbeats", "respond",
                                "notify_responder", "build_evidence", "api_read", "check_recovered", "demo_reset")):
                del sys.modules[name]
        mods = {n: importlib.import_module(f"{n}.app") for n in (
            "ingest_reading", "ingest_event", "check_heartbeats", "respond", "notify_responder", "build_evidence",
            "api_read", "check_recovered", "demo_reset")}
        mods["ddb"] = importlib.import_module("shared.ddb")
        yield mods


def reading(mods, device, temp, key=KEY):
    res = mods["ingest_reading"].handler(
        http_event("POST /readings", {"deviceId": device, "tempC": temp}, headers={"x-device-key": key}), Ctx())
    return res["statusCode"], json.loads(res["body"])


def test_full_incident_flow(env):
    m = env
    ddb = m["ddb"]

    # auth + validation
    assert reading(m, "bloodbank-01", 4, key="wrong")[0] == 401
    assert reading(m, "nope-device", 4)[0] == 404

    # in range -> nothing happens
    code, body = reading(m, "bloodbank-01", 4.1)
    assert code == 202 and body["inRange"] and "incidentId" not in body

    # out of range -> exactly one incident
    code, body = reading(m, "bloodbank-01", 7.2)
    assert body.get("opened") is True
    incident_id = body["incidentId"]
    code, body2 = reading(m, "bloodbank-01", 7.9)
    assert body2["incidentId"] == incident_id and not body2.get("opened")

    # a racing second open is rejected by the conditional write
    device = ddb.get_item(ddb.device_key("bloodbank-01"))
    profile = ddb.get_profile("blood-bank")
    from shared import incidents
    from shared.log import Logger
    assert incidents.open_incident(device, profile, incidents.POWER_LOST, "2026-11-15T02:00:00.000Z",
                                   "racing signal", Logger("test"), temp_c=9.0) is None

    # workflow check: not recovered
    chk = m["check_recovered"].handler({"incidentId": incident_id, "deviceId": "bloodbank-01", "type": "TEMP_EXCURSION", "minC": 2, "maxC": 6, "offlineAfterSeconds": 60}, Ctx())
    assert chk["recovered"] is False and chk["latestTempC"] == 7.9

    # notify level 0 (no SES sender configured -> in-app only)
    m["notify_responder"].handler({"mode": "ACK", "taskToken": "TOKEN-1", "incidentId": incident_id,
                                   "deviceId": "bloodbank-01", "level": 0, "responderId": "nurse-on-duty",
                                   "ackTimeoutSeconds": 13}, Ctx())
    inc = ddb.get_item(ddb.incident_key(incident_id))
    ack_code = inc["pendingAck"]["code"]
    assert len(ack_code) >= 43 and inc["status"] == "ALERTING"
    assert "TOKEN-1" not in json.dumps(ddb.plain(inc))  # token never on the incident

    # dashboard exposes the pending code in demo mode, never the token or emails
    dash = json.loads(m["api_read"].handler(http_event("GET /dashboard"), Ctx())["body"])
    assert dash["config"]["timeScale"] == 45
    assert any(i.get("pendingAck", {}).get("code") == ack_code for i in dash["incidents"])
    assert "TOKEN-1" not in json.dumps(dash) and "email" not in json.dumps(dash["responders"])
    assert len(dash["readings"]["bloodbank-01"]) == 3
    assert {e["type"] for e in dash["events"]} >= {"STARTED", "NOTIFIED"}

    # respond: first tap succeeds, second says already handled
    sent = {}
    m["respond"].sfn.send_task_success = lambda **kw: sent.update(kw)
    ev = http_event("POST /incidents/{id}/respond", {"ackCode": ack_code, "action": "MOVED_TO_BACKUP"}, path={"id": incident_id})
    r1 = m["respond"].handler(ev, Ctx())
    assert r1["statusCode"] == 200 and sent["taskToken"] == "TOKEN-1"
    assert json.loads(sent["output"])["responderName"] == "Nurse Thandi"
    r2 = m["respond"].handler(ev, Ctx())
    assert r2["statusCode"] == 409 and json.loads(r2["body"])["result"] == "ALREADY_HANDLED"
    bad = http_event("POST /incidents/{id}/respond", {"ackCode": "Z" * 43, "action": "FIXED"}, path={"id": incident_id})
    assert m["respond"].handler(bad, Ctx())["statusCode"] == 404

    # back in range -> BACK_IN_RANGE event; check reports recovered
    reading(m, "bloodbank-01", 4.5)
    chk = m["check_recovered"].handler({"incidentId": incident_id, "deviceId": "bloodbank-01", "type": "TEMP_EXCURSION", "minC": 2, "maxC": 6, "offlineAfterSeconds": 60}, Ctx())
    assert chk["recovered"] is True
    types = [e["type"] for e in ddb.incident_events(incident_id)]
    assert "BACK_IN_RANGE" in types

    # evidence: S3 object hash == stored hash
    ddb.table.update_item(Key=ddb.incident_key(incident_id), UpdateExpression="SET #s = :s",
                          ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues={":s": "RESOLVED"})
    out = m["build_evidence"].handler({"incidentId": incident_id}, Ctx())
    body = boto3.client("s3").get_object(Bucket="evidence-bucket", Key=out["evidenceKey"])["Body"].read()
    assert hashlib.sha256(body).hexdigest() == out["sha256"]
    report = json.loads(body)
    assert report["summary"]["maxTempC"] == 7.9 and report["summary"]["outOfRangeSeconds"] >= 0
    detail = json.loads(m["api_read"].handler(http_event("GET /incidents/{id}", path={"id": incident_id}), Ctx())["body"])
    assert detail["incident"]["evidenceSha256"] == out["sha256"]
    assert detail["incident"]["evidencePath"] == f"/evidence/{incident_id}.json"

    # demo reset frees the device
    m["demo_reset"].handler(http_event("POST /demo/reset", {"clearReadings": True}, headers={"x-device-key": KEY}), Ctx())
    dev = ddb.get_item(ddb.device_key("bloodbank-01"))
    assert dev["status"] == "OK" and "openIncidentId" not in dev


def test_critical_device_released_when_cold_again(env):
    m = env
    ddb = m["ddb"]
    _, body = reading(m, "clinic-vaccine-01", 12)
    incident_id = body["incidentId"]
    ddb.table.update_item(Key=ddb.device_key("clinic-vaccine-01"), UpdateExpression="SET #s = :c",
                          ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues={":c": "CRITICAL"})
    _, body = reading(m, "clinic-vaccine-01", 5)
    assert body["status"] == "OK"
    dev = ddb.get_item(ddb.device_key("clinic-vaccine-01"))
    assert dev["status"] == "OK" and "openIncidentId" not in dev
    assert "TEMP_RESTORED" in [e["type"] for e in ddb.incident_events(incident_id)]


def test_max_only_profile(env):
    _, body = reading(env, "plasma-01", -30)
    assert body["inRange"] is True
    _, body = reading(env, "plasma-01", -22)
    assert body["inRange"] is False and body.get("opened")


def power_event(mods, device, type_, battery=None):
    body = {"deviceId": device, "type": type_}
    if battery is not None:
        body["batteryPct"] = battery
    res = mods["ingest_event"].handler(http_event("POST /events", body, headers={"x-device-key": KEY}), Ctx())
    return res["statusCode"], json.loads(res["body"])


def test_power_lost_is_early_warning_and_single_incident(env):
    m, ddb = env, env["ddb"]
    reading(m, "bloodbank-01", 4.0)
    code, body = power_event(m, "bloodbank-01", "POWER_LOST", 98)
    assert code == 202 and body["opened"]
    incident_id = body["incidentId"]
    inc = ddb.get_item(ddb.incident_key(incident_id))
    assert inc["type"] == "POWER_LOST" and inc["status"] == "GRACE"
    assert ddb.get_item(ddb.device_key("bloodbank-01"))["powerSource"] == "BATTERY"
    # duplicate POWER_LOST is ignored; a temperature excursion joins the same incident
    assert power_event(m, "bloodbank-01", "POWER_LOST")[1].get("duplicate")
    _, r = reading(m, "bloodbank-01", 7.5)
    assert r["incidentId"] == incident_id and not r.get("opened")
    # recovery needs mains AND in range
    dev = ddb.get_item(ddb.device_key("bloodbank-01"))
    from check_recovered.app import evaluate
    from shared.timeutil import utcnow
    assert evaluate(dev, "POWER_LOST", 2, 6, 60, utcnow())["recovered"] is False
    power_event(m, "bloodbank-01", "POWER_RESTORED")
    assert evaluate(ddb.get_item(ddb.device_key("bloodbank-01")), "POWER_LOST", 2, 6, 60, utcnow())["recovered"] is False
    reading(m, "bloodbank-01", 4.2)
    assert evaluate(ddb.get_item(ddb.device_key("bloodbank-01")), "POWER_LOST", 2, 6, 60, utcnow())["recovered"] is True
    types = [e["type"] for e in ddb.incident_events(incident_id)]
    assert {"STARTED", "OUT_OF_RANGE", "POWER_RESTORED", "BACK_IN_RANGE"} <= set(types)


def _age_device(ddb, device_id, seconds):
    from shared.timeutil import iso, utcnow
    from datetime import timedelta
    ddb.table.update_item(Key=ddb.device_key(device_id), UpdateExpression="SET lastSeen = :t",
                          ExpressionAttributeValues={":t": iso(utcnow() - timedelta(seconds=seconds))})


def test_sensor_silence_opens_offline_incident_once(env):
    m, ddb = env, env["ddb"]
    for d in ("clinic-vaccine-01", "bloodbank-01", "insulin-home-01", "plasma-01"):
        reading(m, d, -30 if d == "plasma-01" else 5)
    _age_device(ddb, "clinic-vaccine-01", 120)  # scaled offline threshold = max(5, 300/45) = 6 s
    out = m["check_heartbeats"].handler({}, Ctx())
    assert out["opened"] == 1
    dev = ddb.get_item(ddb.device_key("clinic-vaccine-01"))
    inc = ddb.get_item(ddb.incident_key(dev["openIncidentId"]))
    assert inc["type"] == "SENSOR_OFFLINE" and dev.get("offlineSince")
    assert m["check_heartbeats"].handler({}, Ctx())["opened"] == 0  # flagged once
    # readings resume: offlineSince cleared, SENSOR_BACK recorded
    reading(m, "clinic-vaccine-01", 5.1)
    dev = ddb.get_item(ddb.device_key("clinic-vaccine-01"))
    assert "offlineSince" not in dev
    assert "SENSOR_BACK" in [e["type"] for e in ddb.incident_events(inc["incidentId"])]


def test_demo_guard_skips_when_every_sensor_is_silent(env):
    m, ddb = env, env["ddb"]
    for d in ("clinic-vaccine-01", "bloodbank-01", "insulin-home-01", "plasma-01"):
        reading(m, d, -30 if d == "plasma-01" else 5)
        _age_device(ddb, d, 600)
    out = m["check_heartbeats"].handler({}, Ctx())
    assert out.get("skipped") and out["opened"] == 0
