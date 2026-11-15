import { BellRing, Gauge, Layers, Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { cx } from '../lib/format';
import { ACTIVE_INCIDENT } from '../lib/status';
import { useNow } from '../lib/usePolling';
import { useDashboard } from '../state/DashboardContext';
import { Logo } from './bits';

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    try {
      localStorage.setItem('ccg-theme', dark ? 'dark' : 'light');
    } catch {
      /* storage unavailable */
    }
  }, [dark]);
  return [dark, setDark] as const;
}

export function Header() {
  const now = useNow(1000);
  const { data } = useDashboard();
  const [dark, setDark] = useTheme();
  const open = data?.incidents.filter((i) => ACTIVE_INCIDENT.has(i.status)).length ?? 0;
  const scale = data?.config.timeScale ?? 1;

  const link = ({ isActive }: { isActive: boolean }) =>
    cx(
      'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
      isActive ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-slate-600 hover:bg-slate-200/70 dark:text-slate-300 dark:hover:bg-slate-800',
    );

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <NavLink to="/" className="flex items-center gap-2.5" aria-label="ColdChain Guard home">
          <Logo className="h-8 w-8" />
          <span className="text-lg font-semibold tracking-tight">ColdChain Guard</span>
        </NavLink>

        <nav className="flex items-center gap-1" aria-label="Main">
          <NavLink to="/" end className={link}>
            <Gauge className="h-4 w-4" aria-hidden /> Dashboard
          </NavLink>
          <NavLink to="/profiles" className={link}>
            <Layers className="h-4 w-4" aria-hidden /> Profiles
          </NavLink>
        </nav>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          {scale > 1 && (
            <span
              className="rounded-full bg-violet-500/15 px-2.5 py-1 text-xs font-semibold text-violet-700 ring-1 ring-inset ring-violet-500/30 dark:text-violet-300"
              title={`All grace and response timers are divided by ${scale} for the demo`}
            >
              Demo mode · time ×{scale}
            </span>
          )}
          <span
            className={cx(
              'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset',
              open ? 'bg-red-500/15 text-red-700 ring-red-500/40 dark:text-red-300' : 'bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300',
            )}
            aria-live="polite"
          >
            <BellRing className={cx('h-3.5 w-3.5', open > 0 && 'animate-shake')} aria-hidden />
            {open} open incident{open === 1 ? '' : 's'}
          </span>
          <time className="hidden font-mono text-sm tabular-nums text-slate-500 sm:block" aria-label="Current time">
            {new Date(now).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </time>
          <button
            type="button"
            onClick={() => setDark(!dark)}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-200/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 dark:hover:bg-slate-800"
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
}
