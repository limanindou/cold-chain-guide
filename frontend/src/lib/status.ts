import {
  AlertOctagon,
  Ban,
  BellRing,
  CheckCircle2,
  ShieldCheck,
  Timer,
  UserCheck,
  XCircle,
  type LucideIcon,
} from 'lucide-react';

export interface StatusMeta {
  label: string;
  Icon: LucideIcon;
  /** pill classes */
  pill: string;
  /** accent text colour */
  text: string;
  /** chart / dot colour */
  color: string;
  /** extra card emphasis */
  card: string;
  pulse?: boolean;
  ring?: boolean;
}

const OK: StatusMeta = {
  label: 'In range',
  Icon: CheckCircle2,
  pill: 'bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:text-emerald-300',
  text: 'text-emerald-600 dark:text-emerald-400',
  color: '#10b981',
  card: '',
};

export const STATUS: Record<string, StatusMeta> = {
  OK,
  GRACE: {
    label: 'Grace period',
    Icon: Timer,
    pill: 'bg-amber-500/15 text-amber-700 ring-amber-500/40 dark:text-amber-300',
    text: 'text-amber-600 dark:text-amber-400',
    color: '#f59e0b',
    card: 'ring-2 ring-amber-400/50',
    pulse: true,
  },
  ALERTING: {
    label: 'Alerting',
    Icon: BellRing,
    pill: 'bg-red-500/15 text-red-700 ring-red-500/40 dark:text-red-300',
    text: 'text-red-600 dark:text-red-400',
    color: '#ef4444',
    card: 'ring-2 ring-red-500/60 animate-ring',
    ring: true,
  },
  ACKNOWLEDGED: {
    label: 'Being handled',
    Icon: UserCheck,
    pill: 'bg-sky-500/15 text-sky-700 ring-sky-500/40 dark:text-sky-300',
    text: 'text-sky-600 dark:text-sky-400',
    color: '#0ea5e9',
    card: 'ring-2 ring-sky-500/40',
  },
  CRITICAL: {
    label: 'Critical',
    Icon: AlertOctagon,
    pill: 'bg-red-900/90 text-white ring-red-700',
    text: 'text-red-700 dark:text-red-400',
    color: '#991b1b',
    card: 'ring-2 ring-red-800',
  },
  RECOVERED: { ...OK, label: 'Recovered · no alarm', Icon: CheckCircle2 },
  RESOLVED: { ...OK, label: 'Resolved', Icon: ShieldCheck },
  CRITICAL_UNACKNOWLEDGED: {
    label: 'Critical · nobody answered',
    Icon: AlertOctagon,
    pill: 'bg-red-900/90 text-white ring-red-700',
    text: 'text-red-700 dark:text-red-400',
    color: '#991b1b',
    card: '',
  },
  CRITICAL_NOT_RECOVERED: {
    label: 'Critical · not recovered',
    Icon: AlertOctagon,
    pill: 'bg-red-900/90 text-white ring-red-700',
    text: 'text-red-700 dark:text-red-400',
    color: '#991b1b',
    card: '',
  },
  CANCELLED: {
    label: 'Cancelled',
    Icon: Ban,
    pill: 'bg-slate-500/10 text-slate-600 ring-slate-500/30 dark:text-slate-300',
    text: 'text-slate-500',
    color: '#64748b',
    card: '',
  },
  FAILED_TO_START: {
    label: 'Failed to start',
    Icon: XCircle,
    pill: 'bg-slate-500/10 text-slate-600 ring-slate-500/30 dark:text-slate-300',
    text: 'text-slate-500',
    color: '#64748b',
    card: '',
  },
};

export function statusMeta(status?: string): StatusMeta {
  return (status && STATUS[status]) || OK;
}

export const ACTIVE_INCIDENT = new Set(['GRACE', 'ALERTING', 'ACKNOWLEDGED']);
