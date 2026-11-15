import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { api } from '../api';
import { simulator } from '../sim/simulator';
import { usePolling } from '../lib/usePolling';
import type { DashboardData, Reading } from '../types';

const WINDOW_MS = 10 * 60 * 1000;

interface DashboardState {
  data?: DashboardData;
  readings: Record<string, Reading[]>;
  error?: string;
  loading: boolean;
  refresh: () => Promise<void>;
  clearLocal: () => void;
}

const Ctx = createContext<DashboardState | null>(null);

/** One poll every 2 s feeds the whole operator UI (header, dashboard, phones, simulator). */
export function DashboardProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const [data, setData] = useState<DashboardData>();
  const [readings, setReadings] = useState<Record<string, Reading[]>>({});
  const [error, setError] = useState<string>();
  const lastServerTime = useRef<string>();

  const refresh = useCallback(async () => {
    try {
      // overlap a few seconds so late writes are not missed; duplicates are filtered below
      const since = lastServerTime.current
        ? new Date(Date.parse(lastServerTime.current) - 6000).toISOString()
        : undefined;
      const next = await api.dashboard(since);
      lastServerTime.current = next.serverTime;
      const cutoff = Date.parse(next.serverTime) - WINDOW_MS;
      setReadings((prev) => {
        const merged: Record<string, Reading[]> = {};
        for (const dev of next.devices) {
          const old = (prev[dev.deviceId] ?? []).filter((r) => Date.parse(r.ts) >= cutoff);
          const lastTs = old.length ? old[old.length - 1].ts : '';
          const fresh = (next.readings[dev.deviceId] ?? []).filter((r) => r.ts > lastTs);
          merged[dev.deviceId] = [...old, ...fresh];
        }
        return merged;
      });
      setData(next);
      setError(undefined);
      simulator.sync(next.devices, next.profiles);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reach the API');
    }
  }, []);

  usePolling(refresh, 2000, enabled);

  const clearLocal = useCallback(() => {
    lastServerTime.current = undefined;
    setReadings({});
  }, []);

  const value = useMemo(
    () => ({ data, readings, error, loading: !data && !error, refresh, clearLocal }),
    [data, readings, error, refresh, clearLocal],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDashboard(): DashboardState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useDashboard outside DashboardProvider');
  return v;
}
