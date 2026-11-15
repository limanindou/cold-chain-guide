"""Step Functions task: alert a responder.

mode=ACK (invoked via lambda:invoke.waitForTaskToken)
    Stores the task token under a random one-time ackCode (the token itself never leaves
    the backend), records a NOTIFIED event and emails a one-tap link. The workflow then
    pauses — for free — until the responder taps, or TimeoutSeconds turns silence into
    escalation.
mode=CRITICAL
    Final alert to everyone on the escalation chain.
"""
from __future__ import annotations

import os
import secrets
from decimal import Decimal
from html import escape

import boto3

from shared import ddb
from shared.log import Logger
from shared.timeutil import epoch, iso, plus, utcnow

log = Logger("notify_responder")
ses = boto3.client("sesv2")

SENDER = os.environ.get("SENDER_EMAIL", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
ACTION_LABELS = {
    "MOVED_TO_BACKUP": "Moved to backup cooler",
    "FIXED": "Fixed (door closed / power restored)",
    "NEED_HELP": "Need help — escalate",
}


def handler(event, context):
    incident_id = event["incidentId"]
    log.reset(incidentId=incident_id, deviceId=event.get("deviceId"), mode=event.get("mode"))
    if event.get("mode") == "CRITICAL":
        return _notify_everyone(event)
    return _notify_one(event)


def _context(incident_id: str, device_id: str):
    incident = ddb.get_item(ddb.incident_key(incident_id), consistent=True) or {}
    device = ddb.get_item(ddb.device_key(device_id)) or {}
    temp = device.get("lastTempC")
    return incident, device, (float(temp) if temp is not None else None)


def _notify_one(event):
    incident_id, device_id = event["incidentId"], event["deviceId"]
    level = int(event.get("level", 0))
    responder = ddb.get_responder(event["responderId"])
    timeout_s = int(event.get("ackTimeoutSeconds", 600))
    now = utcnow()
    expires = plus(now, timeout_s)
    code = secrets.token_urlsafe(32)  # 43 chars, 256 bits — the only thing that goes in links

    ddb.table.put_item(Item={
        **ddb.ack_key(code),
        "incidentId": incident_id,
        "level": level,
        "responderId": responder["responderId"],
        "taskToken": event["taskToken"],
        "createdAt": iso(now),
        "expiresAt": iso(expires),
        "ttl": epoch(expires) + 7 * 24 * 3600,
    })
    pending = {
        "code": code,
        "responderId": responder["responderId"],
        "responderName": responder.get("name", responder["responderId"]),
        "responderRole": responder.get("role", ""),
        "level": level,
        "notifiedAt": iso(now),
        "expiresAt": iso(expires),
    }
    ddb.table.update_item(
        Key=ddb.incident_key(incident_id),
        UpdateExpression="SET pendingAck = :p, #l = :l, #s = :alerting",
        ExpressionAttributeNames={"#l": "level", "#s": "status"},
        ExpressionAttributeValues={":p": pending, ":l": level, ":alerting": "ALERTING"},
    )
    incident, device, temp = _context(incident_id, device_id)
    emailed = _send_ack_email(responder, incident, device, temp, incident_id, code, timeout_s)
    ddb.put_event(
        incident_id, "NOTIFIED",
        f"Alert sent to {pending['responderName']} ({pending['responderRole'] or 'responder'}), "
        f"level {level + 1}" + (" — email sent" if emailed else " — in-app alert"),
        actor=responder["responderId"], device_id=device_id, level=level,
        ackTimeoutSeconds=timeout_s,
    )
    log.info("Responder notified", responderId=responder["responderId"], escalationLevel=level, emailed=emailed)
    return {"notified": responder["responderId"], "level": level}


def _notify_everyone(event):
    incident_id, device_id = event["incidentId"], event["deviceId"]
    incident, device, temp = _context(incident_id, device_id)
    sent = []
    for rid in event.get("escalation", []):
        responder = ddb.get_responder(rid)
        if _send(responder.get("email"), *_critical_email(incident, device, temp, incident_id)):
            sent.append(rid)
    ddb.put_event(
        incident_id, "ALL_NOTIFIED",
        "Critical alert sent to everyone on the escalation chain"
        + (f" ({len(sent)} emails)" if sent else ""),
        device_id=device_id,
    )
    return {"notified": sent}


# ---------------- email ----------------
def _link(incident_id: str, code: str | None = None) -> str:
    base = FRONTEND_URL or ""
    if code:
        return f"{base}/respond/{incident_id}?code={code}"
    return f"{base}/incidents/{incident_id}"


def _what(incident, device, temp) -> str:
    """Plain words: what is wrong, where."""
    name = device.get("name") or incident.get("deviceName", "A fridge")
    where = f"{name} ({device.get('location', '')})"
    t = f"{temp:g} °C" if temp is not None else "unknown temperature"
    kind = incident.get("type", "TEMP_EXCURSION")
    if kind == "POWER_LOST":
        return f"{where} has lost mains power and is on battery (last reading {t})"
    if kind == "SENSOR_OFFLINE":
        return f"{where} sensor has gone silent (last reading {t})"
    return f"{where} is at {t}"


def _send_ack_email(responder, incident, device, temp, incident_id, code, timeout_s) -> bool:
    what = _what(incident, device, temp)
    link = _link(incident_id, code)
    subject = f"[ColdChain Guard] Action needed: {what}"
    text = (
        f"{what}. It has not recovered within the grace period.\n\n"
        f"Please act now and tap one option:\n{link}\n\n"
        f"  • {ACTION_LABELS['MOVED_TO_BACKUP']}\n  • {ACTION_LABELS['FIXED']}\n  • {ACTION_LABELS['NEED_HELP']}\n\n"
        f"If nobody responds within {timeout_s} seconds the alert escalates automatically.\n"
    )
    html = f"""<div style="font-family:Arial,sans-serif;max-width:520px">
<h2 style="color:#b91c1c;margin:0 0 8px">Action needed</h2>
<p style="font-size:16px">{escape(what)}. It has not recovered within the grace period.</p>
<p><a href="{escape(link)}" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 18px;
border-radius:10px;text-decoration:none;font-weight:bold">Open and respond</a></p>
<p style="color:#475569">Options: {escape(ACTION_LABELS['MOVED_TO_BACKUP'])} · {escape(ACTION_LABELS['FIXED'])} ·
{escape(ACTION_LABELS['NEED_HELP'])}</p>
<p style="color:#64748b;font-size:13px">No response within {timeout_s} s escalates to the next person.
This link works once.</p></div>"""
    return _send(responder.get("email"), subject, text, html)


def _critical_email(incident, device, temp, incident_id):
    what = _what(incident, device, temp)
    link = _link(incident_id)
    subject = f"[ColdChain Guard] CRITICAL: {what}"
    text = (f"CRITICAL: {what}. Nobody has resolved this incident.\n"
            f"Check the stock before it is used. Incident details and evidence:\n{link}\n")
    html = (f"<div style='font-family:Arial,sans-serif'><h2 style='color:#7f1d1d'>CRITICAL</h2>"
            f"<p>{escape(what)}. Nobody has resolved this incident.</p>"
            f"<p>Check the stock before it is used.</p><p><a href='{escape(link)}'>Incident details and evidence</a></p></div>")
    return subject, text, html


def _send(to: str | None, subject: str, text: str, html: str) -> bool:
    if not SENDER or not to:
        return False
    try:
        ses.send_email(
            FromEmailAddress=SENDER,
            Destination={"ToAddresses": [to]},
            Content={"Simple": {
                "Subject": {"Data": subject[:200], "Charset": "UTF-8"},
                "Body": {"Text": {"Data": text, "Charset": "UTF-8"}, "Html": {"Data": html, "Charset": "UTF-8"}},
            }},
        )
        return True
    except Exception as exc:  # email is best effort; the in-app alert still works
        log.exception("SES send failed", exc)
        return False
