import { memo, useMemo } from 'react';
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { clock, inRange, shortTime } from '../lib/format';
import type { Reading } from '../types';

interface Props {
  readings: Reading[];
  minC?: number | null;
  maxC?: number | null;
  height?: number;
  compact?: boolean;
  /** fixed x-window ending "now" (ms); otherwise fit to data */
  windowMs?: number;
  now?: number;
  markers?: { ts: string; label: string; color: string }[];
  ariaLabel?: string;
  /** a gap between readings longer than this is drawn as a break (sensor silent) */
  gapMs?: number;
}

const SAFE = '#10b981';
const HOT = '#ef4444';

/**
 * The key visual: the safe range is a shaded green band, and any segment of the line
 * outside it turns red.
 */
function TempChartImpl({ readings, minC, maxC, height = 120, compact, windowMs, now, markers, ariaLabel, gapMs = 10000 }: Props) {
  const { data, yDomain, band } = useMemo(() => {
    const pts = readings.map((r) => ({ t: Date.parse(r.ts), v: r.tempC }));
    const out = pts.map((p) => !inRange(p.v, minC, maxC));
    const data: { t: number; v: number | null; hot: number | null }[] = [];
    pts.forEach((p, i) => {
      // silence: break the line instead of joining across the missing data
      if (i > 0 && p.t - pts[i - 1].t > gapMs) data.push({ t: (p.t + pts[i - 1].t) / 2, v: null, hot: null });
      // red series includes neighbours so the red segment joins the line seamlessly
      data.push({ t: p.t, v: p.v, hot: out[i] || out[i - 1] || out[i + 1] ? p.v : null });
    });
    const values = pts.map((p) => p.v);
    const bounds = [minC, maxC].filter((b): b is number => b !== null && b !== undefined);
    const all = values.length || bounds.length ? [...values, ...bounds] : [0, 10];
    const lo = Math.min(...all);
    const hi = Math.max(...all);
    const pad = Math.max(1, (hi - lo) * 0.12);
    const yDomain: [number, number] = [Math.floor(lo - pad), Math.ceil(hi + pad)];
    const band: [number, number] = [minC ?? yDomain[0], maxC ?? yDomain[1]];
    return { data, yDomain, band };
  }, [readings, minC, maxC, gapMs]);

  const xDomain: [number | string, number | string] =
    windowMs && now ? [now - windowMs, now] : ['dataMin', 'dataMax'];

  return (
    <div style={{ height }} role="img" aria-label={ariaLabel ?? 'Temperature chart'}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={compact ? { top: 4, right: 4, bottom: 0, left: 4 } : { top: 10, right: 16, bottom: 4, left: 0 }}>
          {!compact && <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.08} />}
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={xDomain}
            allowDataOverflow
            hide={compact}
            tickFormatter={(t) => shortTime(t)}
            stroke="currentColor"
            strokeOpacity={0.4}
            fontSize={11}
            tickMargin={6}
          />
          <YAxis
            domain={yDomain}
            hide={compact}
            width={38}
            stroke="currentColor"
            strokeOpacity={0.4}
            fontSize={11}
            tickFormatter={(v) => `${v}°`}
            allowDataOverflow
          />
          <ReferenceArea y1={band[0]} y2={band[1]} fill={SAFE} fillOpacity={0.12} stroke="none" ifOverflow="hidden" />
          {minC !== null && minC !== undefined && (
            <ReferenceLine y={minC} stroke={SAFE} strokeOpacity={0.6} strokeDasharray="4 4" />
          )}
          {maxC !== null && maxC !== undefined && (
            <ReferenceLine y={maxC} stroke={SAFE} strokeOpacity={0.6} strokeDasharray="4 4" />
          )}
          {markers?.map((m) => (
            <ReferenceLine
              key={m.ts + m.label}
              x={Date.parse(m.ts)}
              stroke={m.color}
              strokeDasharray="2 3"
              label={compact ? undefined : { value: m.label, position: 'insideTopLeft', fontSize: 10, fill: m.color }}
            />
          ))}
          {!compact && (
            <Tooltip
              labelFormatter={(t) => clock(Number(t))}
              formatter={(v: number, name) => (name === 'v' ? [`${v.toFixed(2)} °C`, 'Temperature'] : [null, null])}
              contentStyle={{ borderRadius: 12, fontSize: 12, background: 'rgba(15,23,42,0.92)', border: 'none', color: '#fff' }}
            />
          )}
          <Line type="monotone" dataKey="v" stroke="#64748b" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line
            type="monotone"
            dataKey="hot"
            stroke={HOT}
            strokeWidth={compact ? 2.5 : 3}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
            legendType="none"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export const TempChart = memo(TempChartImpl);
