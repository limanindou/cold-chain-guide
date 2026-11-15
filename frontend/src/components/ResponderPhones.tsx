import { BellRing, ExternalLink, Smartphone, Wifi } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cx, fmtDuration, fmtTemp, incidentTypeLabel, secondsSince } from '../lib/format';
import type { Device, Incident, Responder } from '../types';
import { RespondActions } from './RespondActions';
import { SectionTitle } from './bits';

const CORE = ['nurse-on-duty', 'facility-manager', 'district-pharmacist'];

interface Props {
  responders: Responder[];
  incidents: Incident[];
  devices: Device[];
  now: number;
}

/** Demo aid: the responders' phones on one screen, so escalation is visible without email. */
export function ResponderPhones({ responders, incidents, devices, now }: Props) {
  const pending = incidents.filter((i) => i.pendingAck?.code);
  const ids = [...CORE];
  for (const i of pending) if (!ids.includes(i.pendingAck!.responderId)) ids.push(i.pendingAck!.responderId);
  const byId = Object.fromEntries(responders.map((r) => [r.responderId, r]));

  return (
    <section aria-label="Responder phones">
      <SectionTitle icon={<Smartphone className="h-4 w-4" aria-hidden />}>Responder phones</SectionTitle>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {ids.map((id) => {
          const r = byId[id] ?? { responderId: id, name: id, role: '' };
          const inc = pending.find((i) => i.pendingAck?.responderId === id);
          const dev = inc && devices.find((d) => d.deviceId === inc.deviceId);
          return <MiniPhone key={id} responder={r} incident={inc} device={dev} now={now} />;
        })}
      </div>
    </section>
  );
}

function MiniPhone({ responder, incident, device, now }: { responder: Responder; incident?: Incident; device?: Device; now: number }) {
  const ringing = !!incident;
  const left = incident?.pendingAck ? Math.max(0, -secondsSince(incident.pendingAck.expiresAt, now)) : 0;
  return (
    <div
      className={cx(
        'relative w-[188px] shrink-0 rounded-[28px] border-[6px] bg-white p-3 shadow-lg transition-all dark:bg-slate-900',
        ringing ? 'border-red-500 animate-ring' : 'border-slate-800 dark:border-slate-700',
      )}
    >
      <div className="mx-auto mb-2 h-1.5 w-12 rounded-full bg-slate-300 dark:bg-slate-700" aria-hidden />
      <div className="mb-2 flex items-center justify-between text-[10px] text-slate-400">
        <span>{new Date(now).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        <Wifi className="h-3 w-3" aria-hidden />
      </div>
      <p className="text-sm font-semibold leading-tight">{responder.name}</p>
      <p className="mb-2 text-[11px] text-slate-500">{responder.role}</p>

      {ringing && incident?.pendingAck?.code ? (
        <div className="space-y-2">
          <div className="rounded-xl bg-red-500/10 p-2">
            <p className="flex items-center gap-1 text-xs font-semibold text-red-600 dark:text-red-400">
              <BellRing className="h-3.5 w-3.5 animate-shake" aria-hidden /> Action needed
            </p>
            <p className="text-[11px] leading-snug">
              <b>{incidentTypeLabel(incident.type)}</b>: {incident.deviceName} at <b>{fmtTemp(device?.lastTempC)}</b>, for{' '}
              {fmtDuration(secondsSince(incident.startedAt, now))}
            </p>
            <p className="mt-1 text-[10px] tabular-nums text-slate-500">Escalates in {Math.ceil(left)} s</p>
          </div>
          <RespondActions key={incident.pendingAck.code} incidentId={incident.incidentId} ackCode={incident.pendingAck.code} size="sm" />
          <Link
            to={`/respond/${incident.incidentId}?code=${incident.pendingAck.code}`}
            target="_blank"
            className="flex items-center justify-center gap-1 text-[10px] text-slate-500 hover:underline"
          >
            Open phone view <ExternalLink className="h-3 w-3" aria-hidden />
          </Link>
        </div>
      ) : (
        <div className="grid h-[150px] place-items-center rounded-xl bg-slate-50 text-center text-xs text-slate-400 dark:bg-slate-800/50">
          <div>
            <Smartphone className="mx-auto mb-1 h-5 w-5 opacity-50" aria-hidden />
            No alerts
          </div>
        </div>
      )}
    </div>
  );
}
