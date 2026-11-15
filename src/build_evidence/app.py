"""Step Functions task: build the tamper-evident evidence report for an incident.

Writes evidence/{incidentId}.json (canonical JSON — the fingerprinted artefact) and
evidence/{incidentId}.html (human-readable, quotes the fingerprint) to S3, stores the
SHA-256 on the incident and records an EVIDENCE_SEALED event. S3 independently verifies
the upload against the same SHA-256 (ChecksumSHA256).
"""
from __future__ import annotations

import base64
import hashlib
import os
from html import escape

import boto3

from shared import ddb
from shared.evidence import build_report, canonical_bytes
from shared.log import Logger
from shared.timeutil import iso, now_iso, parse_iso, plus

log = Logger("build_evidence")
s3 = boto3.client("s3")
BUCKET = os.environ.get("EVIDENCE_BUCKET", "")


def handler(event, context):
    incident_id = event["incidentId"]
    log.reset(incidentId=incident_id)
    incident = ddb.plain(ddb.get_item(ddb.incident_key(incident_id), consistent=True))
    events = sorted((ddb.plain(e) for e in ddb.incident_events(incident_id)), key=lambda e: e["ts"])
    started = parse_iso(incident["startedAt"])
    raw = ddb.readings_between(incident["deviceId"], iso(plus(started, -60)), incident.get("resolvedAt") or "~")
    readings = [{"ts": r["SK"][len("READING#"):], "tempC": float(r["tempC"])} for r in raw]

    report = build_report(incident, events, readings, now_iso())
    body = canonical_bytes(report)
    digest = hashlib.sha256(body)
    sha_hex = digest.hexdigest()
    json_key = f"evidence/{incident_id}.json"
    html_key = f"evidence/{incident_id}.html"

    s3.put_object(Bucket=BUCKET, Key=json_key, Body=body, ContentType="application/json",
                  ChecksumSHA256=base64.b64encode(digest.digest()).decode(),
                  CacheControl="public, max-age=31536000, immutable",
                  Metadata={"sha256": sha_hex})
    s3.put_object(Bucket=BUCKET, Key=html_key, Body=render_html(report, sha_hex).encode("utf-8"),
                  ContentType="text/html; charset=utf-8", CacheControl="public, max-age=31536000, immutable")

    summary = report["summary"]
    ddb.table.update_item(
        Key=ddb.incident_key(incident_id),
        UpdateExpression=("SET evidenceKey = :k, evidenceHtmlKey = :h, evidenceSha256 = :sha, sealedAt = :at, "
                          "outOfRangeSeconds = :o, minTempC = :lo, maxTempC = :hi"),
        ExpressionAttributeValues=ddb.to_decimal({
            ":k": json_key, ":h": html_key, ":sha": sha_hex, ":at": report["generatedAt"],
            ":o": summary["outOfRangeSeconds"], ":lo": summary["minTempC"], ":hi": summary["maxTempC"],
        }),
    )
    ddb.put_event(incident_id, "EVIDENCE_SEALED", f"Evidence report sealed · SHA-256 {sha_hex[:12]}…",
                  device_id=incident["deviceId"], sha256=sha_hex)
    log.info("Evidence sealed", sha256=sha_hex, outOfRangeSeconds=summary["outOfRangeSeconds"])
    return {"evidenceKey": json_key, "sha256": sha_hex}


def _fmt_temp(v):
    return "—" if v is None else f"{v:g} °C"


def _fmt_duration(seconds: float) -> str:
    s = int(round(seconds))
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h} h {m} min {s} s" if h else (f"{m} min {s} s" if m else f"{s} s")


def render_html(report: dict, sha_hex: str) -> str:
    inc, summ = report["incident"], report["summary"]
    rows = "".join(
        f"<tr><td>{escape(e['ts'][11:19])}</td><td><b>{escape(e['type'])}</b></td>"
        f"<td>{escape(e.get('detail') or '')}</td></tr>" for e in report["timeline"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Evidence report · {escape(inc['incidentId'])}</title>
<style>body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:860px;margin:32px auto;padding:0 16px;color:#0f172a}}
h1{{font-size:22px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border-bottom:1px solid #e2e8f0;padding:6px 8px;text-align:left;vertical-align:top}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}}
.card{{border:1px solid #e2e8f0;border-radius:12px;padding:12px}}.k{{color:#64748b;font-size:12px;text-transform:uppercase}}
.v{{font-size:18px;font-weight:600}}code{{word-break:break-all;background:#f1f5f9;padding:6px 8px;border-radius:8px;display:block}}
.note{{color:#64748b;font-size:13px}}</style></head><body>
<h1>ColdChain Guard — incident evidence ({escape(str(inc.get('type') or 'TEMP_EXCURSION'))})</h1>
<p><b>{escape(inc.get('deviceName') or '')}</b> · {escape(inc.get('location') or '')} · {escape(inc.get('profileLabel') or '')}
(safe range {escape(inc['safeRange']['text'])})</p>
<div class="grid">
<div class="card"><div class="k">Status</div><div class="v">{escape(str(inc.get('status')))}</div></div>
<div class="card"><div class="k">Time out of range</div><div class="v">{_fmt_duration(summ['outOfRangeSeconds'])}</div></div>
<div class="card"><div class="k">Min / max</div><div class="v">{_fmt_temp(summ['minTempC'])} / {_fmt_temp(summ['maxTempC'])}</div></div>
<div class="card"><div class="k">Acknowledged by</div><div class="v">{escape(summ.get('ackedBy') or '—')}</div></div>
</div>
<p>Started {escape(inc['startedAt'])} · ended {escape(inc['endedAt'])} · {summ['readingsCount']} readings</p>
<h2>Timeline</h2><table><tr><th>Time (UTC)</th><th>Event</th><th>Detail</th></tr>{rows}</table>
<h2>Fingerprint</h2>
<p>SHA-256 of the canonical JSON report (<code style="display:inline">{escape(inc['incidentId'])}.json</code>):</p>
<code>{sha_hex}</code>
<p class="note">Re-hash the JSON file and compare: any change to the data changes this fingerprint.</p>
<p class="note">{escape(report['disclaimer'])}</p>
</body></html>"""
