import {
  Activity,
  BatteryWarning,
  Plug,
  Wifi,
  WifiOff,
  AlertOctagon,
  Ban,
  BellRing,
  CheckCircle2,
  Fingerprint,
  HelpCircle,
  Megaphone,
  PlayCircle,
  ShieldCheck,
  ThermometerSnowflake,
  ThermometerSun,
  Timer,
  TrendingUp,
  UserCheck,
  type LucideIcon,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { clock, cx } from '../lib/format';
import type { IncidentEvent, Responder } from '../types';

const EVENT_META: Record<string, { Icon: LucideIcon; tone: string; label: string }> = {
  STARTED: { Icon: PlayCircle, tone: 'text-amber-500 bg-amber-500/10', label: 'Out of range' },
  GRACE: { Icon: Timer, tone: 'text-amber-500 bg-amber-500/10', label: 'Grace period' },
  BACK_IN_RANGE: { Icon: ThermometerSnowflake, tone: 'text-emerald-500 bg-emerald-500/10', label: 'Back in range' },
  OUT_OF_RANGE: { Icon: ThermometerSun, tone: 'text-red-500 bg-red-500/10', label: 'Out of range' },
  POWER_LOST: { Icon: BatteryWarning, tone: 'text-amber-500 bg-amber-500/10', label: 'Power lost · on battery' },
  POWER_RESTORED: { Icon: Plug, tone: 'text-emerald-500 bg-emerald-500/10', label: 'Power restored' },
  SENSOR_OFFLINE: { Icon: WifiOff, tone: 'text-red-500 bg-red-500/10', label: 'Sensor silent' },
  SENSOR_BACK: { Icon: Wifi, tone: 'text-emerald-500 bg-emerald-500/10', label: 'Sensor back online' },
  OUT_OF_RANGE_AGAIN: { Icon: ThermometerSun, tone: 'text-amber-500 bg-amber-500/10', label: 'Out of range again' },
  GRACE_EXPIRED: { Icon: Activity, tone: 'text-red-500 bg-red-500/10', label: 'Grace expired' },
  NOTIFIED: { Icon: BellRing, tone: 'text-red-500 bg-red-500/10', label: 'Alert sent' },
  ESCALATED: { Icon: TrendingUp, tone: 'text-orange-500 bg-orange-500/10', label: 'Escalated' },
  NEED_HELP: { Icon: HelpCircle, tone: 'text-orange-500 bg-orange-500/10', label: 'Help requested' },
  ACKED: { Icon: UserCheck, tone: 'text-sky-500 bg-sky-500/10', label: 'Acknowledged' },
  RECOVERED: { Icon: CheckCircle2, tone: 'text-emerald-500 bg-emerald-500/10', label: 'Recovered · no alarm' },
  RESOLVED: { Icon: ShieldCheck, tone: 'text-emerald-500 bg-emerald-500/10', label: 'Resolved' },
  CRITICAL: { Icon: AlertOctagon, tone: 'text-red-700 bg-red-700/15', label: 'Critical' },
  ALL_NOTIFIED: { Icon: Megaphone, tone: 'text-red-700 bg-red-700/15', label: 'Everyone alerted' },
  EVIDENCE_SEALED: { Icon: Fingerprint, tone: 'text-violet-500 bg-violet-500/10', label: 'Evidence sealed' },
  TEMP_RESTORED: { Icon: ThermometerSnowflake, tone: 'text-emerald-500 bg-emerald-500/10', label: 'Back to normal' },
  CANCELLED: { Icon: Ban, tone: 'text-slate-500 bg-slate-500/10', label: 'Cancelled' },
};

export function eventMeta(type: string) {
  return EVENT_META[type] ?? { Icon: Activity, tone: 'text-slate-500 bg-slate-500/10', label: type };
}

interface Props {
  events: IncidentEvent[];
  responders?: Responder[];
  showDevice?: boolean;
  linkIncidents?: boolean;
  emptyText?: string;
}

export function Timeline({ events, responders, showDevice, linkIncidents, emptyText = 'No events yet.' }: Props) {
  const names = Object.fromEntries((responders ?? []).map((r) => [r.responderId, r.name]));
  if (!events.length) {
    return <p className="py-6 text-center text-sm text-slate-500">{emptyText}</p>;
  }
  return (
    <ol className="relative space-y-3" aria-live="polite">
      {events.map((e) => {
        const m = eventMeta(e.type);
        const actor = e.actor && e.actor !== 'system' ? names[e.actor] ?? e.actor : undefined;
        const body = (
          <div className="flex gap-3">
            <div className={cx('grid h-8 w-8 shrink-0 place-items-center rounded-full', m.tone)}>
              <m.Icon className="h-4 w-4" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-sm font-semibold">
                  {m.label}
                  {showDevice && e.deviceName && (
                    <span className="font-normal text-slate-500 dark:text-slate-400"> · {e.deviceName}</span>
                  )}
                </p>
                <time className="shrink-0 text-xs tabular-nums text-slate-400" dateTime={e.ts}>
                  {clock(e.ts)}
                </time>
              </div>
              {e.detail && <p className="text-xs leading-snug text-slate-600 dark:text-slate-300">{e.detail}</p>}
              {actor && e.type !== 'ACKED' && <p className="text-xs text-slate-400">{actor}</p>}
            </div>
          </div>
        );
        return (
          <li key={`${e.incidentId}-${e.ts}-${e.type}`} className="animate-fadein">
            {linkIncidents ? (
              <Link
                to={`/incidents/${e.incidentId}`}
                className="block rounded-xl p-1 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800/60"
              >
                {body}
              </Link>
            ) : (
              <div className="p-1">{body}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
