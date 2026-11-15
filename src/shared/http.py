"""API Gateway HTTP API (payload v2) helpers."""
from __future__ import annotations

import base64
import json
from decimal import Decimal


def _default(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"Not JSON serialisable: {type(o).__name__}")


def respond(status: int, body, headers: dict | None = None) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store", **(headers or {})},
        "body": json.dumps(body, default=_default),
    }


def error(status: int, message: str, **extra) -> dict:
    return respond(status, {"error": message, **extra})


def json_body(event: dict):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    if not raw:
        return {}
    return json.loads(raw)


def header(event: dict, name: str) -> str:
    headers = event.get("headers") or {}
    return headers.get(name.lower()) or headers.get(name) or ""


def query(event: dict, name: str, default=None):
    return (event.get("queryStringParameters") or {}).get(name, default)


def path_param(event: dict, name: str):
    return (event.get("pathParameters") or {}).get(name)
