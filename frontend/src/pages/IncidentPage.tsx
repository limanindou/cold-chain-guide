import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Fingerprint,
  Loader2,
  ShieldAlert,
  Users,
  Workflow,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, evidenceUrl } from '../api';
import { Card, ProfileIcon, SectionTitle, Skeleton, StatusPill } from '../components/bits';
import { TempChart } from '../components/TempChart';
import { Timeline } from '../components/Timeline';
import { actionLabel, clock, cx, fmtDuration, fmtTemp, incidentTypeLabel, rangeText, secondsSince } from '../lib/format';
import { ACTIVE_INCIDENT } from '../lib/status';
import { useNow, usePolling } from '../lib/usePolling';
import type { IncidentDetail, IncidentEvent } from '../types';

export default function IncidentPage() {
  const { id = '' } = useParams();
  const [detail, setDetail] = useState<IncidentDetail>();
  const [error, setError] = useState<string>();
  const now = useNow(1000);

  const load = useCallback(async () => {
    try {
      setDetail(await api.incident(id));
      setError(undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    }
  }, [id]);

  const finished = !!detail && !ACTIVE_INCIDENT.has(detail.incident.status) && !!detail.incident.evidenceSha256;
  usePolling(load, 2000, !finished, id);

  if (!detail) {
    return error ? (
      <Card className="mx-auto max-w-lg p-6 text-center">
        <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-amber-500" aria-hidden />
        <p className="font-semibold">Incident not available</p>
        <p className="text-sm text-slate-500">{error}</p>
      </Card>
    ) : (
      <div className="space-y-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  const { incident: inc, events, readings, profile, responders } = detail;
  const end = inc.resolvedAt ?? inc.criticalAt;
  const duration = end ? (Date.parse(end) - Date.parse(inc.startedAt)) / 1000 : secondsSince(inc.startedAt, now);
  const markers = events
    .filter((e) => ['GRACE_EXPIRED', 'ACKED', 'RESOLVED', 'ESCALATED', 'CRITICAL'].includes(e.type))
    .map((e) => ({
      ts: e.ts,
      label: e.type === 'GRACE_EXPIRED' ? 'Alert' : e.type === 'ACKED' ? 'Ack' : e.type === 'ESCALATED' ? 'Escalate' : e.type === 'RESOLVED' ? 'Resolved' : 'Critical',
      color: e.type === 'ACKED' ? '#0ea5e9' : e.type === 'RESOLVED' ? '#10b981' : '#ef4444',
    }));

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Dashboard
      </Link>

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 dark:bg-slate-800">
              <ProfileIcon icon={profile.icon} className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-semibold">{inc.deviceName}</h1>
              <p className="text-sm text-slate-500">
                {inc.location} · {inc.profileLabel} · safe range {rangeText(inc.minC, inc.maxC)}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-500/10 px-2.5 py-1 text-xs font-semibold">{incidentTypeLabel(inc.type)}</span>
            <StatusPill status={inc.status} />
            {inc.consoleUrl && (
              <a
                href={inc.consoleUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ring-inset ring-slate-300 hover:bg-slate-100 dark:ring-slate-700 dark:hover:bg-slate-800"
              >
                <Workflow className="h-3.5 w-3.5" aria-hidden /> View workflow in AWS console <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            )}
          </div>
        </div>
        <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Started" value={clock(inc.startedAt)} />
          <Stat label={end ? 'Duration' : 'Open for'} value={fmtDuration(duration)} />
          <Stat label="First reading" value={fmtTemp(inc.firstTempC)} />
          <Stat
            label="Handled by"
            value={inc.ackedByName ? `${inc.ackedByName}` : inc.status.startsWith('CRITICAL') ? 'Nobody' : '—'}
            sub={inc.ackedAction ? actionLabel(inc.ackedAction) : undefined}
          />
        </dl>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card className="p-4">
            <SectionTitle>Temperature during the incident</SectionTitle>
            <TempChart readings={readings} minC={inc.minC} maxC={inc.maxC} height={300} markers={markers} ariaLabel="Temperature during the incident" />
          </Card>
          <EscalationLadder events={events} responders={responders} escalation={profile.escalation} />
          <EvidenceCard detail={detail} />
        </div>
        <Card className="p-4">
          <SectionTitle>Timeline</SectionTitle>
          <Timeline events={[...events].reverse()} responders={responders} />
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
      {sub && <dd className="text-xs text-slate-500">{sub}</dd>}
    </div>
  );
}

function EscalationLadder({ events, responders, escalation }: { events: IncidentEvent[]; responders: { responderId: string; name: string; role: string }[]; escalation: string[] }) {
  const byId = Object.fromEntries(responders.map((r) => [r.responderId, r]));
  return (
    <Card className="p-4">
      <SectionTitle icon={<Users className="h-4 w-4" aria-hidden />}>Escalation ladder</SectionTitle>
      <ol className="grid gap-3 sm:grid-cols-3">
        {escalation.map((rid, level) => {
          const notified = events.find((e) => e.type === 'NOTIFIED' && e.actor === rid);
          const acked = events.find((e) => e.type === 'ACKED' && e.actor === rid);
          const help = events.find((e) => e.type === 'NEED_HELP' && e.actor === rid);
          const escalated = events.find((e) => e.type === 'ESCALATED' && e.actor === rid);
          const state = acked ? 'acked' : help ? 'help' : escalated ? 'silent' : notified ? 'waiting' : 'idle';
          const tone = {
            acked: 'border-emerald-500/50 bg-emerald-500/5',
            help: 'border-orange-500/50 bg-orange-500/5',
            silent: 'border-red-500/50 bg-red-500/5',
            waiting: 'border-amber-500/50 bg-amber-500/5 animate-pulse',
            idle: 'border-slate-200 dark:border-slate-800 opacity-60',
          }[state];
          const text = {
            acked: `Acted at ${acked && clock(acked.ts)}`,
            help: `Asked for help at ${help && clock(help.ts)}`,
            silent: 'No response → escalated',
            waiting: `Alerted at ${notified && clock(notified.ts)} · waiting`,
            idle: 'Not needed',
          }[state];
          return (
            <li key={rid} className={cx('rounded-xl border p-3', tone)}>
              <p className="text-xs text-slate-500">Level {level + 1}</p>
              <p className="font-semibold">{byId[rid]?.name ?? rid}</p>
              <p className="text-xs text-slate-500">{byId[rid]?.role}</p>
              <p className="mt-1 text-xs font-medium">{text}</p>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function EvidenceCard({ detail }: { detail: IncidentDetail }) {
  const inc = detail.incident;
  const [verify, setVerify] = useState<{ state: 'idle' | 'busy' | 'match' | 'mismatch' | 'error'; hash?: string }>({ state: 'idle' });
  const jsonUrl = evidenceUrl(inc.evidencePath);
  const htmlUrl = evidenceUrl(inc.evidenceHtmlPath);

  async function runVerify() {
    if (!jsonUrl || !inc.evidenceSha256) return;
    setVerify({ state: 'busy' });
    try {
      const res = await fetch(jsonUrl, { cache: 'no-store' });
      if (!res.ok) throw new Error(String(res.status));
      const hash = await sha256Hex(await res.arrayBuffer());
      setVerify({ state: hash === inc.evidenceSha256 ? 'match' : 'mismatch', hash });
    } catch {
      setVerify({ state: 'error' });
    }
  }

  if (!inc.evidenceSha256) {
    return (
      <Card className="flex items-center gap-3 p-4 text-sm text-slate-500">
        <ShieldAlert className="h-5 w-5" aria-hidden />
        The evidence report is sealed automatically when the incident closes.
      </Card>
    );
  }

  return (
    <Card className="p-4">
      <SectionTitle icon={<Fingerprint className="h-4 w-4" aria-hidden />}>Evidence report</SectionTitle>
      <dl className="grid grid-cols-3 gap-4">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Time out of range</dt>
          <dd className="text-lg font-semibold">{fmtDuration(inc.outOfRangeSeconds ?? 0)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Min</dt>
          <dd className="text-lg font-semibold">{fmtTemp(inc.minTempC)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-500">Max</dt>
          <dd className="text-lg font-semibold">{fmtTemp(inc.maxTempC)}</dd>
        </div>
      </dl>
      <p className="mt-4 text-xs uppercase tracking-wide text-slate-500">SHA-256 fingerprint</p>
      <code className="mt-1 block break-all rounded-xl bg-slate-100 px-3 py-2 font-mono text-xs dark:bg-slate-800">{inc.evidenceSha256}</code>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {htmlUrl && (
          <a href={htmlUrl} target="_blank" rel="noreferrer" className="btn-primary">
            <FileText className="h-4 w-4" aria-hidden /> Open report
          </a>
        )}
        {jsonUrl && (
          <a href={jsonUrl} download={`${inc.incidentId}.json`} className="btn-secondary">
            <Download className="h-4 w-4" aria-hidden /> Download JSON
          </a>
        )}
        <button type="button" onClick={runVerify} className="btn-secondary" disabled={verify.state === 'busy'}>
          {verify.state === 'busy' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Fingerprint className="h-4 w-4" aria-hidden />}
          Verify
        </button>
        {verify.state === 'match' && (
          <span className="inline-flex animate-pop items-center gap-1 text-sm font-semibold text-emerald-600 dark:text-emerald-400" role="status">
            <CheckCircle2 className="h-5 w-5" aria-hidden /> Match — report is untouched
          </span>
        )}
        {verify.state === 'mismatch' && (
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-red-600" role="status">
            <XCircle className="h-5 w-5" aria-hidden /> Mismatch — report was changed
          </span>
        )}
        {verify.state === 'error' && <span className="text-sm text-amber-600">Could not download the report to verify.</span>}
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Verify downloads the report and re-hashes it in your browser (Web Crypto). Sealed{' '}
        {inc.sealedAt ? clock(inc.sealedAt) : ''}. Ranges are configurable examples — follow official guidance before using or discarding stock.
      </p>
    </Card>
  );
}
