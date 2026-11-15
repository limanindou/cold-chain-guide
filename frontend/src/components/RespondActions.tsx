import { CheckCircle2, Clock4, HelpCircle, Loader2, PackageCheck, Wrench, XCircle } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api';
import { actionLabel, cx } from '../lib/format';
import type { RespondResult, ResponderAction } from '../types';

const ACTIONS: { action: ResponderAction; label: string; sub: string; Icon: typeof Wrench; cls: string }[] = [
  {
    action: 'MOVED_TO_BACKUP',
    label: 'Moved to backup cooler',
    sub: 'Stock is safe in another fridge',
    Icon: PackageCheck,
    cls: 'bg-sky-600 hover:bg-sky-500 text-white',
  },
  {
    action: 'FIXED',
    label: 'Fixed',
    sub: 'Door closed / power restored',
    Icon: Wrench,
    cls: 'bg-emerald-600 hover:bg-emerald-500 text-white',
  },
  {
    action: 'NEED_HELP',
    label: 'Need help',
    sub: 'Escalate to the next person now',
    Icon: HelpCircle,
    cls: 'bg-slate-200 hover:bg-slate-300 text-slate-900 dark:bg-slate-700 dark:hover:bg-slate-600 dark:text-white',
  },
];

interface Props {
  incidentId: string;
  ackCode: string;
  size?: 'sm' | 'lg';
  onDone?: (r: RespondResult) => void;
}

export function RespondActions({ incidentId, ackCode, size = 'lg', onDone }: Props) {
  const [busy, setBusy] = useState<ResponderAction>();
  const [result, setResult] = useState<RespondResult & { tapped?: ResponderAction }>();

  async function tap(action: ResponderAction) {
    setBusy(action);
    const r = await api.respond(incidentId, ackCode, action);
    setBusy(undefined);
    setResult({ ...r, tapped: action });
    onDone?.(r);
  }

  if (result) return <RespondOutcome result={result} size={size} />;

  return (
    <div className={cx('grid', size === 'lg' ? 'gap-3' : 'gap-1.5')}>
      {ACTIONS.map(({ action, label, sub, Icon, cls }) => (
        <button
          key={action}
          type="button"
          disabled={!!busy}
          onClick={() => tap(action)}
          className={cx(
            'flex w-full items-center gap-3 rounded-2xl text-left font-semibold shadow-sm transition active:scale-[0.98] disabled:opacity-60',
            'focus:outline-none focus-visible:ring-4 focus-visible:ring-sky-400/60',
            size === 'lg' ? 'px-5 py-4 text-base' : 'rounded-xl px-2.5 py-1.5 text-xs',
            cls,
          )}
        >
          {busy === action ? (
            <Loader2 className={cx('shrink-0 animate-spin', size === 'lg' ? 'h-6 w-6' : 'h-3.5 w-3.5')} aria-hidden />
          ) : (
            <Icon className={cx('shrink-0', size === 'lg' ? 'h-6 w-6' : 'h-3.5 w-3.5')} aria-hidden />
          )}
          <span className="min-w-0">
            <span className="block">{label}</span>
            {size === 'lg' && <span className="block text-sm font-normal opacity-80">{sub}</span>}
          </span>
        </button>
      ))}
    </div>
  );
}

export function RespondOutcome({ result, size = 'lg' }: { result: RespondResult & { tapped?: ResponderAction }; size?: 'sm' | 'lg' }) {
  const big = size === 'lg';
  if (result.result === 'OK') {
    const escalating = result.action === 'NEED_HELP' || result.tapped === 'NEED_HELP';
    return (
      <div className={cx('flex flex-col items-center text-center', big ? 'gap-3 py-6' : 'gap-1 py-2')} role="status">
        <div className={cx('grid animate-pop place-items-center rounded-full bg-emerald-500 text-white', big ? 'h-20 w-20' : 'h-10 w-10')}>
          <CheckCircle2 className={big ? 'h-12 w-12' : 'h-6 w-6'} aria-hidden />
        </div>
        <p className={cx('font-semibold', big ? 'text-xl' : 'text-xs')}>
          {escalating ? 'Help is on the way' : 'Thank you — recorded'}
        </p>
        <p className={cx('text-slate-500 dark:text-slate-400', big ? 'text-sm' : 'text-[10px] leading-tight')}>
          {escalating ? 'The next person has been alerted.' : `${actionLabel(result.tapped)}. We keep watching until it is back in range.`}
        </p>
      </div>
    );
  }
  const handled = result.result === 'ALREADY_HANDLED';
  return (
    <div className={cx('flex flex-col items-center text-center', big ? 'gap-3 py-6' : 'gap-1 py-2')} role="status">
      <div className={cx('grid place-items-center rounded-full', handled ? 'bg-sky-500/15 text-sky-500' : 'bg-slate-500/15 text-slate-500', big ? 'h-16 w-16' : 'h-9 w-9')}>
        {handled ? <CheckCircle2 className={big ? 'h-9 w-9' : 'h-5 w-5'} aria-hidden /> : result.result === 'EXPIRED' ? <Clock4 className={big ? 'h-9 w-9' : 'h-5 w-5'} aria-hidden /> : <XCircle className={big ? 'h-9 w-9' : 'h-5 w-5'} aria-hidden />}
      </div>
      <p className={cx('font-semibold', big ? 'text-lg' : 'text-xs')}>
        {handled ? 'Already handled' : result.result === 'EXPIRED' ? 'This alert has expired' : 'Link not valid'}
      </p>
      <p className={cx('text-slate-500 dark:text-slate-400', big ? 'text-sm' : 'text-[10px] leading-tight')}>
        {handled
          ? `${result.handledBy ?? 'Someone'} already responded${result.action ? ` (${actionLabel(result.action)})` : ''}.`
          : result.message ?? 'Please check the dashboard.'}
      </p>
    </div>
  );
}
