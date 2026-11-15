import { Battery, BatteryLow, Clock, MapPin, Plug, Wifi, WifiOff } from 'lucide-react';
import { memo } from 'react';
import { Link } from 'react-router-dom';
import { ago, cx, fmtDuration, fmtTemp, incidentTypeLabel, inRange, rangeText, secondsSince } from '../lib/format';
import { statusMeta } from '../lib/status';
import type { Device, Incident, Profile, Reading } from '../types';
import { Card, ProfileIcon, StatusPill } from './bits';
import { TempChart } from './TempChart';

interface Props {
  device: Device;
  profile?: Profile;
  readings: Reading[];
  incident?: Incident;
  now: number;
  timeScale: number;
}

function DeviceCardImpl({ device, profile, readings, incident, now, timeScale }: Props) {
  const meta = statusMeta(device.status);
  const temp = device.lastTempC;
  const ok = temp === undefined || inRange(temp, profile?.minC, profile?.maxC);
  const silentFor = secondsSince(device.lastSeen, now);
  const offlineAfter = Math.max(20, Math.floor((profile?.offlineAfterSeconds ?? 300) / Math.max(1, timeScale)));
  const offline = !!device.lastSeen && silentFor > offlineAfter;
  const onBattery = device.powerSource === 'BATTERY';
  const battery = device.batteryPct ?? 100;
  const openFor = incident && device.status !== 'OK' ? secondsSince(incident.startedAt, now) : 0;

  return (
    <Card className={cx('flex flex-col gap-3 p-4 sm:p-5', meta.card)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className={cx('grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-100 dark:bg-slate-800', meta.text)}>
            <ProfileIcon icon={profile?.icon} className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h3 className="truncate font-semibold">{device.name}</h3>
            <p className="flex items-center gap-1 truncate text-xs text-slate-500 dark:text-slate-400">
              <MapPin className="h-3 w-3 shrink-0" aria-hidden />
              {device.location}
            </p>
          </div>
        </div>
        <StatusPill status={device.status} />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs font-medium">
        {onBattery ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-amber-700 dark:text-amber-300" title="Mains power lost — sensor running on its backup battery">
            {battery < 30 ? <BatteryLow className="h-3.5 w-3.5" aria-hidden /> : <Battery className="h-3.5 w-3.5" aria-hidden />}
            On battery · {Math.round(battery)}%
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/10 px-2 py-0.5 text-slate-600 dark:text-slate-300" title="Mains power">
            <Plug className="h-3.5 w-3.5" aria-hidden /> Mains
          </span>
        )}
        {offline ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2 py-0.5 text-red-700 dark:text-red-300">
            <WifiOff className="h-3.5 w-3.5" aria-hidden /> Silent for {fmtDuration(silentFor)}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-700 dark:text-emerald-300">
            <Wifi className="h-3.5 w-3.5" aria-hidden /> {device.lastSeen ? 'Online' : 'Waiting for sensor'}
          </span>
        )}
      </div>

      <div className="flex items-end justify-between gap-2">
        <div className={cx(offline && 'opacity-50')}>
          <div
            className={cx('text-4xl font-semibold tabular-nums tracking-tight', ok ? '' : 'text-red-600 dark:text-red-400')}
            aria-label={`${offline ? 'Last known' : 'Current'} temperature ${fmtTemp(temp)}`}
          >
            {temp === undefined ? '—' : temp.toFixed(1)}
            <span className="ml-1 text-lg font-normal text-slate-400">°C</span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {offline ? 'Last known · ' : ''}Safe range{' '}
            <span className="font-medium text-emerald-600 dark:text-emerald-400">{rangeText(profile?.minC, profile?.maxC)}</span>
          </p>
        </div>
        {incident && device.status !== 'OK' && (
          <Link
            to={`/incidents/${incident.incidentId}`}
            className={cx('rounded-lg px-2 py-1 text-right text-xs font-medium hover:underline', meta.text)}
          >
            {device.status === 'CRITICAL' ? 'Critical · ' : ''}
            {incidentTypeLabel(incident.type)}
            <br />
            <span className="tabular-nums">for {fmtDuration(openFor)}</span> →
          </Link>
        )}
      </div>

      <div className={cx('relative transition-opacity', offline && 'opacity-40 grayscale')}>
        <TempChart
          readings={readings}
          minC={profile?.minC}
          maxC={profile?.maxC}
          height={90}
          compact
          windowMs={10 * 60 * 1000}
          now={now}
          ariaLabel={`${device.name}: last 10 minutes of temperature`}
        />
        {offline && (
          <div className="pointer-events-none absolute inset-y-0 right-0 flex w-1/4 items-center justify-center rounded-lg border-2 border-dashed border-slate-400/70 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            No data
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" aria-hidden />
          Last seen {ago(device.lastSeen, now)}
        </span>
        <span>{profile?.label}</span>
      </div>
    </Card>
  );
}

export const DeviceCard = memo(DeviceCardImpl);
