import { useEffect, useRef, useState } from 'react';

/**
 * Calls `fn` every `intervalMs` (after the previous call settles). Pauses while the tab is
 * hidden and fires immediately when it becomes visible again. Pass `enabled=false` to stop.
 */
export function usePolling(fn: () => Promise<unknown> | unknown, intervalMs: number, enabled = true, key: unknown = null) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    let inFlight = false;

    const tick = async () => {
      if (stopped || inFlight) return;
      if (document.hidden) {
        timer = setTimeout(tick, intervalMs);
        return;
      }
      inFlight = true;
      try {
        await fnRef.current();
      } catch {
        /* errors are surfaced by the caller's own state */
      } finally {
        inFlight = false;
        if (!stopped) timer = setTimeout(tick, intervalMs);
      }
    };
    const onVisible = () => {
      if (!document.hidden && !inFlight) {
        clearTimeout(timer);
        tick();
      }
    };
    tick();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [intervalMs, enabled, key]);
}

/** Current time, re-rendering every `intervalMs`. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
