import { ArrowRight, BatteryWarning, Clock, Hourglass, Puzzle, Thermometer, WifiOff } from 'lucide-react';
import { Card, ProfileIcon, Skeleton } from '../components/bits';
import { fmtReal, rangeText } from '../lib/format';
import { useDashboard } from '../state/DashboardContext';

export default function ProfilesPage() {
  const { data } = useDashboard();
  const names = Object.fromEntries((data?.responders ?? []).map((r) => [r.responderId, r]));

  return (
    <div className="space-y-6">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">One engine, many cold chains</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-300">
          A profile is just data: a safe range, a grace period, a response timeout and an escalation chain. Adding a new use
          case needs <b>no new code</b>. The same pattern (threshold → grace → human acknowledgement → escalate on silence →
          evidence) watches three failure signals (temperature, power loss and a silent sensor) and also fits server rooms, food storage, incubators and greenhouses.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {!data &&
          [0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-56" />)}
        {data?.profiles.map((p) => (
          <Card key={p.profileId} className="flex flex-col gap-4 p-5">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
                <ProfileIcon icon={p.icon} className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-semibold">{p.label}</h2>
                <p className="font-mono text-xs text-slate-500">{p.profileId}</p>
              </div>
            </div>
            {p.description && <p className="text-sm text-slate-600 dark:text-slate-300">{p.description}</p>}
            <dl className="grid grid-cols-3 gap-2 text-sm">
              <div className="rounded-xl bg-emerald-500/10 p-2">
                <dt className="flex items-center gap-1 text-[11px] text-slate-500">
                  <Thermometer className="h-3 w-3" aria-hidden /> Safe range
                </dt>
                <dd className="font-semibold text-emerald-700 dark:text-emerald-300">{rangeText(p.minC, p.maxC)}</dd>
              </div>
              <div className="rounded-xl bg-amber-500/10 p-2">
                <dt className="flex items-center gap-1 text-[11px] text-slate-500">
                  <Hourglass className="h-3 w-3" aria-hidden /> Grace
                </dt>
                <dd className="font-semibold">{fmtReal(p.graceSeconds)}</dd>
              </div>
              <div className="rounded-xl bg-red-500/10 p-2">
                <dt className="flex items-center gap-1 text-[11px] text-slate-500">
                  <Clock className="h-3 w-3" aria-hidden /> Ack timeout
                </dt>
                <dd className="font-semibold">{fmtReal(p.ackTimeoutSeconds)}</dd>
              </div>
              <div className="rounded-xl bg-slate-500/10 p-2">
                <dt className="flex items-center gap-1 text-[11px] text-slate-500">
                  <BatteryWarning className="h-3 w-3" aria-hidden /> Power grace
                </dt>
                <dd className="font-semibold">{fmtReal(p.powerGraceSeconds ?? 300)}</dd>
              </div>
              <div className="col-span-2 rounded-xl bg-slate-500/10 p-2">
                <dt className="flex items-center gap-1 text-[11px] text-slate-500">
                  <WifiOff className="h-3 w-3" aria-hidden /> Silent-sensor alarm after
                </dt>
                <dd className="font-semibold">{fmtReal(p.offlineAfterSeconds ?? 300)}</dd>
              </div>
            </dl>
            <div>
              <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Escalation chain</p>
              <ol className="flex flex-wrap items-center gap-1 text-xs">
                {p.escalation.map((rid, i) => (
                  <li key={rid} className="flex items-center gap-1">
                    {i > 0 && <ArrowRight className="h-3 w-3 text-slate-400" aria-hidden />}
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium dark:bg-slate-800">
                      {names[rid]?.role ?? rid}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </Card>
        ))}
      </div>
      <Card className="flex items-start gap-3 p-4 text-sm text-slate-600 dark:text-slate-300">
        <Puzzle className="mt-0.5 h-5 w-5 shrink-0 text-violet-500" aria-hidden />
        <p>
          Temperature ranges shown are configurable examples, not medical advice. Check them against official guidance (WHO,
          your national health department, blood service or the manufacturer) before relying on them.
        </p>
      </Card>
    </div>
  );
}
