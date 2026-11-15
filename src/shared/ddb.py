"""DynamoDB single-table helpers (ColdChainTable)."""
from __future__ import annotations

import os
import time
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from shared.timeutil import now_iso

TABLE_NAME = os.environ.get("TABLE_NAME", "ColdChainTable")

_resource = boto3.resource("dynamodb")
table = _resource.Table(TABLE_NAME)
client = boto3.client("dynamodb")

_ser = TypeSerializer()
_deser = TypeDeserializer()

ACTIVE_INCIDENT_STATUSES = {"GRACE", "ALERTING", "ACKNOWLEDGED"}


# ---------- keys ----------
def device_key(device_id: str) -> dict:
    return {"PK": f"DEVICE#{device_id}", "SK": "META"}


def incident_key(incident_id: str) -> dict:
    return {"PK": f"INCIDENT#{incident_id}", "SK": "META"}


def profile_key(profile_id: str) -> dict:
    return {"PK": f"PROFILE#{profile_id}", "SK": "META"}


def responder_key(responder_id: str) -> dict:
    return {"PK": f"RESPONDER#{responder_id}", "SK": "META"}


def ack_key(code: str) -> dict:
    return {"PK": f"ACK#{code}", "SK": "META"}


# ---------- (de)serialisation ----------
def to_decimal(value):
    if value is None:
        return None
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_decimal(v) for v in value]
    return value


def plain(value):
    """Decimal -> int/float, recursively; strips table key attributes from dicts."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items() if k not in ("PK", "SK", "GSI1PK", "GSI1SK", "ttl")}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def ser(item: dict) -> dict:
    """Python dict -> low-level DynamoDB attribute map (for transact_write_items)."""
    return {k: _ser.serialize(to_decimal(v)) for k, v in item.items() if v is not None}


def ser_values(values: dict) -> dict:
    return {k: _ser.serialize(to_decimal(v)) for k, v in values.items()}


def deser(item: dict) -> dict:
    return {k: _deser.deserialize(v) for k, v in item.items()}


# ---------- events ----------
def event_item(incident_id: str, event_type: str, detail: str, actor: str = "system",
               device_id: str | None = None, ts: str | None = None, **extra) -> dict:
    ts = ts or now_iso()
    item = {
        "PK": f"INCIDENT#{incident_id}",
        "SK": f"EVENT#{ts}#{event_type}",
        "incidentId": incident_id,
        "type": event_type,
        "ts": ts,
        "actor": actor,
        "detail": detail,
    }
    if device_id:
        item["deviceId"] = device_id
    item.update({k: v for k, v in extra.items() if v is not None})
    return item


def put_event(incident_id: str, event_type: str, detail: str, **kwargs) -> dict:
    item = event_item(incident_id, event_type, detail, **kwargs)
    table.put_item(Item=to_decimal(item))
    return item


# ---------- reads ----------
def get_item(key: dict, consistent: bool = False) -> dict | None:
    return table.get_item(Key=key, ConsistentRead=consistent).get("Item")


def query_all(**kwargs) -> list:
    items, start = [], None
    while True:
        if start:
            kwargs["ExclusiveStartKey"] = start
        page = table.query(**kwargs)
        items.extend(page.get("Items", []))
        start = page.get("LastEvaluatedKey")
        if not start or ("Limit" in kwargs and len(items) >= kwargs["Limit"]):
            return items


def list_entities(kind: str) -> list:
    """All items of a kind via GSI1 (GSI1PK = DEVICES | PROFILES | RESPONDERS)."""
    return query_all(IndexName="GSI1", KeyConditionExpression=Key("GSI1PK").eq(kind))


def recent_incidents(limit: int = 20) -> list:
    page = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq("INCIDENTS"),
        ScanIndexForward=False,
        Limit=limit,
    )
    return page.get("Items", [])


def incident_events(incident_id: str) -> list:
    return query_all(
        KeyConditionExpression=Key("PK").eq(f"INCIDENT#{incident_id}") & Key("SK").begins_with("EVENT#"),
    )


def readings_between(device_id: str, start_iso: str, end_iso: str = "~") -> list:
    return query_all(
        KeyConditionExpression=Key("PK").eq(f"DEVICE#{device_id}")
        & Key("SK").between(f"READING#{start_iso}", f"READING#{end_iso}"),
    )


# ---------- small TTL cache for rarely-changing config (profiles, responders) ----------
_cache: dict = {}


def _cached(name: str, loader, ttl: float = 30.0):
    hit = _cache.get(name)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    value = loader()
    _cache[name] = (time.monotonic(), value)
    return value


def profiles_by_id() -> dict:
    return _cached("profiles", lambda: {p["profileId"]: p for p in list_entities("PROFILES")})


def responders_by_id() -> dict:
    return _cached("responders", lambda: {r["responderId"]: r for r in list_entities("RESPONDERS")})


def get_profile(profile_id: str) -> dict | None:
    profile = profiles_by_id().get(profile_id)
    if profile is None:
        profile = get_item(profile_key(profile_id))
    return profile


def get_responder(responder_id: str) -> dict:
    r = responders_by_id().get(responder_id) or get_item(responder_key(responder_id))
    return r or {"responderId": responder_id, "name": responder_id, "role": "", "email": ""}
