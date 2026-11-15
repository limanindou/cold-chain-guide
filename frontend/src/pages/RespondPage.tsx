import { AlertTriangle, BellRing, Clock4, MapPin, ShieldCheck } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Logo, ProfileIcon, Skeleton } from '../components/bits';
import { RespondActions } from '../components/RespondActions';
import { TempChart } from '../components/TempChart';
import { cx, fmtDuration, fmtTemp, incidentTypeLabel, rangeText, secondsSince } from '../lib/format';
import { ACTIVE_INCIDENT } from '../lib/status';
import { useNow, usePolling } from '../lib/usePolling';
import type { IncidentDetail } from '../types';

/** What the responder sees after tapping the link in their alert. Designed for a 390 px phone. */
export default function RespondPage() {
  const { incidentId = '' } = useParams();
  const [params] = useSearchParams();
  const code = params.get('code') ?? '';
  const [detail, setDetail] = useState<IncidentDetail>();
  const [error, setError] = useState<string>();
  const [done, setDone] = useState(false);
  const now = useNow(1000);

  const load = useCallback(async () => {
    try {
      setDetail(await api.incident(incidentId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the alert');
    }
  }, [incidentId]);
  usePolling(load, 3000, !done, incidentId);

  const inc = detail?.incident;
  const temp = detail?.device.lastTempC;
  const outFor = inc ? secondsSince(inc.startedAt, now) : 0;
  const closed = inc && !ACTIVE_INCIDENT.has(inc.status);

  return (
    <div className="flex min-h-screen justify-center bg-slate-100 dark:bg-slate-950 sm:py-8">
      <main className="w-full max-w-[420px] bg-white px-5 pb-10 pt-5 dark:bg-slate-900 sm:rounded-[2.5rem] sm:shadow-2xl sm:ring-8 sm:ring-slate-800">
        <div className="mb-5 flex items-center gap-2">
          <Logo className="h-7 w-7" />
          <span className="font-semibold">ColdChain Guard</span>
        </div>

        {!detail && !error && (
          <div className="space-y-3">
            <Skeleton className="h-28" />
            <Skeleton className="h-40" />
            <Skeleton className="h-48" />
          </div>
        )}
        {error && !detail && (
          <div className="py-10 text-center">
            <AlertTriangle className="mx-auto mb-2 h-10 w-10 text-amber-500" aria-hidden />
            <p className="font-semibold">We couldn't open this alert</p>
            <p className="text-sm text-slate-500">{error}</p>
          </div>
        )}

        {detail && inc && (
          <div className="space-y-5">
            <section
              className={cx(
                'rounded-3xl p-5 text-white',
                closed ? 'bg-emerald-600' : inc.status === 'ACKNOWLEDGED' ? 'bg-sky-600' : 'bg-red-600',
              )}
            >
              <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide opacity-90">
                {closed ? <ShieldCheck className="h-4 w-4" aria-hidden /> : <BellRing className="h-4 w-4 animate-shake" aria-hidden />}
                {closed ? 'Incident closed' : inc.status === 'ACKNOWLEDGED' ? 'Being handled' : `Action needed · ${incidentTypeLabel(inc.type)}`}
              </p>
              <h1 className="mt-2 text-2xl font-bold leading-tight">
                {inc.deviceName} at {fmtTemp(temp)}
              </h1>
              <p className="mt-1 text-sm opacity-90">
                {closed
                  ? 'Back under control.'
                  : inc.type === 'POWER_LOST'
                    ? `Mains power lost ${fmtDuration(outFor)} ago. The sensor is on battery. Safe range ${rangeText(inc.minC, inc.maxC)}.`
                    : inc.type === 'SENSOR_OFFLINE'
                      ? `The sensor has been silent for ${fmtDuration(outFor)}, so nobody knows the temperature. Please check the fridge.`
                      : `Out of its safe range (${rangeText(inc.minC, inc.maxC)}) for ${fmtDuration(outFor)}.`}
              </p>
              <p className="mt-2 flex items-center gap-1 text-xs opacity-80">
                <MapPin className="h-3 w-3" aria-hidden /> {inc.location}
              </p>
            </section>

            <section className="rounded-2xl bg-slate-50 p-3 dark:bg-slate-800/60">
              <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  <ProfileIcon icon={detail.profile.icon} className="h-3.5 w-3.5" /> {detail.profile.label}
                </span>
                <span>Green band = safe range</span>
              </div>
              <TempChart readings={detail.readings} minC={inc.minC} maxC={inc.maxC} height={130} compact ariaLabel="Temperature since the incident started" />
            </section>

            {!code ? (
              <p className="rounded-xl bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
                This page needs the personal link from your alert to record an action.
              </p>
            ) : closed && !done ? (
              <div className="flex items-center gap-2 rounded-xl bg-slate-100 p-3 text-sm dark:bg-slate-800">
                <Clock4 className="h-4 w-4" aria-hidden /> This alert is no longer active — no action needed.
              </div>
            ) : (
              <section aria-label="Respond">
                <h2 className="mb-3 text-sm font-semibold text-slate-500">What have you done?</h2>
                <RespondActions incidentId={incidentId} ackCode={code} onDone={() => setDone(true)} />
              </section>
            )}
            <p className="text-center text-xs text-slate-400">If nobody responds in time, the next person is alerted automatically.</p>
          </div>
        )}
      </main>
    </div>
  );
}
