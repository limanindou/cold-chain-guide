import {
  Baby,
  Droplet,
  FlaskConical,
  Home,
  Milk,
  Snowflake,
  Syringe,
  Thermometer,
  type LucideIcon,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { cx } from '../lib/format';
import { statusMeta } from '../lib/status';

const PROFILE_ICONS: Record<string, LucideIcon> = {
  syringe: Syringe,
  droplet: Droplet,
  snowflake: Snowflake,
  home: Home,
  flask: FlaskConical,
  milk: Milk,
  baby: Baby,
};

export function ProfileIcon({ icon, className }: { icon?: string; className?: string }) {
  const Icon = (icon && PROFILE_ICONS[icon]) || Thermometer;
  return <Icon className={className} aria-hidden />;
}

export function StatusPill({ status, className }: { status?: string; className?: string }) {
  const m = statusMeta(status);
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset',
        m.pill,
        className,
      )}
    >
      <m.Icon className={cx('h-3.5 w-3.5', m.pulse && 'animate-pulse')} aria-hidden />
      {m.label}
    </span>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cx(
        'rounded-2xl border border-slate-200 bg-white shadow-sm transition-shadow dark:border-slate-800 dark:bg-slate-900/70',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800', className)} />;
}

export function Logo({ className }: { className?: string }) {
  // Original mark: a shield holding a snowflake.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <defs>
        <linearGradient id="ccg-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#38bdf8" />
          <stop offset="1" stopColor="#0284c7" />
        </linearGradient>
      </defs>
      <path d="M16 2 4 6.5v8.6c0 7.3 5 13.3 12 14.9 7-1.6 12-7.6 12-14.9V6.5L16 2z" fill="url(#ccg-g)" />
      <g stroke="#fff" strokeWidth="2" strokeLinecap="round">
        <path d="M16 9v14M10 12.5l12 7M22 12.5l-12 7" />
      </g>
    </svg>
  );
}

export function SectionTitle({ icon, children, right }: { icon?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {icon}
        {children}
      </h2>
      {right}
    </div>
  );
}
