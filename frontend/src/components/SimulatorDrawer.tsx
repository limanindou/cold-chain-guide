import { Battery, ChevronDown, ChevronUp, DoorOpen, FlaskRound, Pause, Play, RadioTower, RotateCcw, ShieldCheck, WifiOff, Zap } from 'lucide-react';
import { useState, useSyncExternalStore, type ReactNode } from 'react';
import { api } from '../api';
import { cx, inRange } from '../lib/format';
import { simulator, type SimMode } from '../sim/simulator';
import { useDashboard } from '../state/DashboardContext';

const MODE_LABEL: Record<SimMode, string> = {
  normal: 'Normal',
  powercut: 'Power cut',
  door: 'Door open',
  manual: 'Manual',
};

export function SimulatorDrawer() {
  const sim = useSyncExternalStore(simulator.subscribe, simulator.getState);
  const { clearLocal, refresh } = useDashboard();
  const [open, setOpen] = useState(true);
  const [resetting, setResetting] = useState(false);
  const devices = Object.values(sim.devices);

  async function reset() {
    setResetting(true);
    try {
      simulator.resetAll();
      await api.resetDemo();
      clearLocal();
      await refresh();
    } finally {
      setResetting(false);
    }
  }

  return (
    <section
      aria-label="Sensor simulator, for demo"
      className="rounded-2xl border border-dashed border-violet-400/60 bg-violet-50/60 p-4 dark:border-violet-500/40 dark:bg-violet-950/20"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 text-sm font-semibold text-violet-700 dark:text-violet-300"
          aria-expanded={open}
        >
          <FlaskRound className="h-4 w-4" aria-hidden />
          Sensor simulator — for demo
          {open ? <ChevronUp className="h-4 w-4" aria-hidden /> : <ChevronDown className="h-4 w-4" aria-hidden />}
        </button>
        <div className="flex items-center gap-2 text-xs">
          <span className={cx('flex items-center gap-1', sim.lastError ? 'text-red-500' : 'text-slate-500')}>
            <span className={cx('h-2 w-2 rounded-full', sim.running ? (sim.lastError ? 'bg-red-500' : 'bg-emerald-500 animate-pulse') : 'bg-slate-400')} />
            {sim.running ? (sim.lastError ? `Error: ${sim.lastError}` : 'Streaming every 2 s') : 'Paused'}
          </span>
          <button type="button" onClick={() => simulator.setRunning(!sim.running)} className="btn-ghost">
            {sim.running ? <Pause className="h-3.5 w-3.5" aria-hidden /> : <Play className="h-3.5 w-3.5" aria-hidden />}
            {sim.running ? 'Pause' : 'Resume'}
          </button>
          <button type="button" onClick={reset} disabled={resetting} className="btn-ghost">
            <RotateCcw className={cx('h-3.5 w-3.5', resetting && 'animate-spin')} aria-hidden />
            Reset demo
          </button>
        </div>
      </div>

      <p className="mt-1 flex items-center gap-1.5 text-xs text-violet-700/80 dark:text-violet-300/80">
        <RadioTower className="h-3.5 w-3.5 shrink-0" aria-hidden />
        Simulated sensors. In production: battery-backed sensors via AWS IoT Core (MQTT, X.509 certificates) feeding the same Lambdas.
      </p>
      {open && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {devices.map((d) => {
            const lo = Math.floor(Math.min(d.baseline - 8, d.minC ?? d.baseline - 8));
            const hi = Math.ceil(Math.max(d.baseline + 14, (d.maxC ?? d.baseline) + 8));
            return (
              <div key={d.deviceId} className="rounded-xl bg-white/80 p-3 dark:bg-slate-900/70">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-medium">{d.name}</span>
                  <span className="text-xs text-slate-500">
                    <span className={cx('font-semibold tabular-nums', inRange(d.temp, d.minC, d.maxC) ? '' : 'text-red-500')}>
                      {d.temp.toFixed(1)} °C
                    </span>{' '}
                    · {d.silent ? 'Silent' : MODE_LABEL[d.mode]}
                    {d.onBattery && (
                      <span className="ml-1 inline-flex items-center gap-0.5 text-amber-600">
                        <Battery className="h-3 w-3" aria-hidden />
                        {Math.round(d.battery)}%
                      </span>
                    )}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <SimButton active={d.mode === 'powercut'} onClick={() => simulator.powerCut(d.deviceId)} tone="red">
                    <Zap className="h-3.5 w-3.5" aria-hidden /> Power cut
                  </SimButton>
                  <SimButton active={d.mode === 'door'} onClick={() => simulator.setMode(d.deviceId, 'door')} tone="amber">
                    <DoorOpen className="h-3.5 w-3.5" aria-hidden /> Door open (brief)
                  </SimButton>
                  <SimButton active={d.silent} onClick={() => simulator.silence(d.deviceId)} tone="red">
                    <WifiOff className="h-3.5 w-3.5" aria-hidden /> Sensor goes silent
                  </SimButton>
                  <SimButton active={false} onClick={() => simulator.restore(d.deviceId)} tone="emerald">
                    <ShieldCheck className="h-3.5 w-3.5" aria-hidden /> Restore
                  </SimButton>
                </div>
                <label className="mt-2 flex items-center gap-2 text-xs text-slate-500">
                  Manual
                  <input
                    type="range"
                    min={lo}
                    max={hi}
                    step={0.5}
                    value={d.mode === 'manual' ? d.manualTarget : d.temp}
                    onChange={(e) => simulator.setMode(d.deviceId, 'manual', Number(e.target.value))}
                    className="flex-1 accent-violet-600"
                    aria-label={`Manual temperature for ${d.name}`}
                  />
                </label>
              </div>
            );
          })}
          {!devices.length && <p className="text-sm text-slate-500">Waiting for devices…</p>}
        </div>
      )}
    </section>
  );
}

function SimButton({ children, onClick, active, tone }: { children: ReactNode; onClick: () => void; active: boolean; tone: 'red' | 'amber' | 'emerald' }) {
  const tones = {
    red: 'hover:bg-red-500/10 text-red-700 dark:text-red-300 ring-red-500/40',
    amber: 'hover:bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-amber-500/40',
    emerald: 'hover:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-emerald-500/40',
  };
  const activeTones = { red: 'bg-red-500/15', amber: 'bg-amber-500/15', emerald: 'bg-emerald-500/15' };
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cx(
        'inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold ring-1 ring-inset transition focus:outline-none focus-visible:ring-2',
        tones[tone],
        active && activeTones[tone],
      )}
    >
      {children}
    </button>
  );
}
