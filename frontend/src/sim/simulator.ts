/**
 * Browser-side sensor simulator (clearly labelled "for demo" in the UI).
 * Every 2 s it POSTs one reading per device to /readings, exactly like a real sensor would,
 * and sends POWER_LOST / POWER_RESTORED events to /events.
 * In production: battery-backed sensors -> AWS IoT Core -> the same Lambdas.
 */
import { api } from '../api';
import type { Device, Profile } from '../types';

export type SimMode = 'normal' | 'powercut' | 'door' | 'manual';

export interface SimDevice {
  deviceId: string;
  name: string;
  temp: number;
  baseline: number;
  minC: number | null;
  maxC: number | null;
  mode: SimMode;
  step: number;
  manualTarget: number;
  onBattery: boolean;
  battery: number;
  silent: boolean;
}

export interface SimState {
  running: boolean;
  devices: Record<string, SimDevice>;
  lastError?: string;
  lastSentAt?: number;
}

const TICK_MS = 2000;
const AMBIENT = 24;

function noise(scale = 0.06) {
  return (Math.random() * 2 - 1) * scale;
}

function nextTemp(d: SimDevice): { temp: number; mode: SimMode; step: number } {
  const high = d.maxC ?? d.baseline + 5;
  switch (d.mode) {
    case 'powercut': {
      // compressor off: a few seconds of thermal inertia, then warms steadily towards room temperature
      const rate = d.step < 3 ? 0.05 : d.baseline < -10 ? 1.1 : 0.45;
      return { temp: Math.min(AMBIENT, d.temp + rate + noise(0.05)), mode: 'powercut', step: d.step + 1 };
    }
    case 'door': {
      // brief spike that recovers well inside any grace period (~6 s out of range)
      const seq = [d.baseline + (high - d.baseline) * 0.8, high + 1.6, high + 1.0];
      if (d.step < seq.length) return { temp: seq[d.step] + noise(0.05), mode: 'door', step: d.step + 1 };
      return { temp: d.temp + (d.baseline - d.temp) * 0.6, mode: 'normal', step: 0 };
    }
    case 'manual':
      return { temp: d.manualTarget + noise(0.03), mode: 'manual', step: 0 };
    default: {
      // thermostat pulls back to baseline (gradually after a power cut is restored)
      const pull = Math.abs(d.temp - d.baseline) > 3 ? 0.18 : 0.35;
      return { temp: d.temp + (d.baseline - d.temp) * pull + noise(), mode: 'normal', step: 0 };
    }
  }
}

type Listener = () => void;

export class Simulator {
  private state: SimState = { running: true, devices: {} };
  private listeners = new Set<Listener>();
  private timer?: ReturnType<typeof setInterval>;
  private active = false;

  getState = (): SimState => this.state;

  subscribe = (l: Listener) => {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  };

  private set(next: Partial<SimState>) {
    this.state = { ...this.state, ...next };
    this.listeners.forEach((l) => l());
  }

  private patch(deviceId: string, p: Partial<SimDevice>) {
    const d = this.state.devices[deviceId];
    if (!d) return undefined;
    const next = { ...d, ...p };
    this.set({ devices: { ...this.state.devices, [deviceId]: next } });
    return next;
  }

  /** Register devices from the API (keeps existing simulated state). */
  sync(devices: Device[], profiles: Profile[]) {
    const byId = Object.fromEntries(profiles.map((p) => [p.profileId, p]));
    let changed = false;
    const next = { ...this.state.devices };
    for (const dev of devices) {
      if (next[dev.deviceId]) continue;
      const p = byId[dev.profileId];
      if (!p) continue;
      const baseline = p.baselineC ?? ((p.minC ?? (p.maxC ?? 5) - 5) + (p.maxC ?? (p.minC ?? 0) + 5)) / 2;
      const start = dev.lastTempC ?? baseline;
      next[dev.deviceId] = {
        deviceId: dev.deviceId,
        name: dev.name,
        temp: start,
        baseline,
        minC: p.minC ?? null,
        maxC: p.maxC ?? null,
        mode: 'normal',
        step: 0,
        manualTarget: start,
        onBattery: false,
        battery: 100,
        silent: false,
      };
      changed = true;
    }
    if (changed) this.set({ devices: next });
  }

  setMode(deviceId: string, mode: SimMode, manualTarget?: number) {
    const d = this.state.devices[deviceId];
    if (!d) return;
    this.patch(deviceId, { mode, step: 0, manualTarget: manualTarget ?? d.manualTarget });
  }

  /** ⚡ Power cut: the sensor reports POWER_LOST at once (early warning), runs on battery, fridge warms. */
  powerCut(deviceId: string) {
    const d = this.patch(deviceId, { mode: 'powercut', step: 0, onBattery: true, silent: false });
    if (d) this.send(() => api.postEvent(deviceId, 'POWER_LOST', Math.round(d.battery)));
  }

  /** ✅ Restore: power back (POWER_RESTORED), sensor reporting, temperature returns to baseline. */
  restore(deviceId: string) {
    const d = this.state.devices[deviceId];
    if (!d) return;
    const wasOnBattery = d.onBattery;
    const next = this.patch(deviceId, { mode: 'normal', step: 0, onBattery: false, silent: false });
    if (wasOnBattery && next) this.send(() => api.postEvent(deviceId, 'POWER_RESTORED', Math.round(next.battery)));
  }

  /** 📡 Sensor goes silent: stop sending anything for this device. */
  silence(deviceId: string) {
    this.patch(deviceId, { silent: true });
  }

  resetAll() {
    const devices = Object.fromEntries(
      Object.values(this.state.devices).map((d) => [
        d.deviceId,
        { ...d, mode: 'normal' as SimMode, temp: d.baseline, step: 0, onBattery: false, battery: 100, silent: false },
      ]),
    );
    this.set({ devices });
  }

  setRunning(running: boolean) {
    this.set({ running });
    this.reconcile();
  }

  /** The simulator only streams on operator pages (never on a responder's phone view). */
  setActive(active: boolean) {
    this.active = active;
    this.reconcile();
  }

  private reconcile() {
    const shouldRun = this.active && this.state.running;
    if (shouldRun && !this.timer) {
      this.timer = setInterval(() => void this.tick(), TICK_MS);
    } else if (!shouldRun && this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
  }

  private async send(fn: () => Promise<unknown>) {
    try {
      await fn();
      this.set({ lastError: undefined });
    } catch (err) {
      this.set({ lastError: err instanceof Error ? err.message : String(err) });
    }
  }

  private async tick() {
    const devices = { ...this.state.devices };
    for (const id of Object.keys(devices)) {
      const d = devices[id];
      const n = nextTemp(d);
      // battery drains while on battery, recharges on mains
      const battery = d.onBattery ? Math.max(5, d.battery - 0.6) : Math.min(100, d.battery + 1.5);
      devices[id] = { ...d, temp: Math.round(n.temp * 100) / 100, mode: n.mode, step: n.step, battery };
    }
    this.set({ devices });
    const live = Object.values(devices).filter((d) => !d.silent);
    const results = await Promise.allSettled(
      live.map((d) => api.postReading(d.deviceId, d.temp, Math.round(d.battery))),
    );
    const failed = results.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined;
    this.set({ lastSentAt: Date.now(), lastError: failed ? String(failed.reason?.message ?? failed.reason) : undefined });
  }
}

export const simulator = new Simulator();
