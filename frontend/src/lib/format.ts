export function inRange(t: number, minC?: number | null, maxC?: number | null): boolean {
  if (minC !== undefined && minC !== null && t < minC) return false;
  if (maxC !== undefined && maxC !== null && t > maxC) return false;
  return true;
}

export function rangeText(minC?: number | null, maxC?: number | null): string {
  const hasMin = minC !== undefined && minC !== null;
  const hasMax = maxC !== undefined && maxC !== null;
  if (hasMin && hasMax) return `${minC} to ${maxC} °C`;
  if (hasMax) return `≤ ${maxC} °C`;
  if (hasMin) return `≥ ${minC} °C`;
  return 'any';
}

export function fmtTemp(t?: number | null, digits = 1): string {
  if (t === undefined || t === null || Number.isNaN(t)) return '—';
  return `${t.toFixed(digits)} °C`;
}

export function fmtDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h} h ${m} min`;
  if (m) return `${m} min ${sec.toString().padStart(2, '0')} s`;
  return `${sec} s`;
}

/** Real-world duration for a value configured in real seconds (profiles). */
export function fmtReal(seconds: number): string {
  if (seconds >= 3600) return `${+(seconds / 3600).toFixed(1)} h`;
  if (seconds >= 60) return `${Math.round(seconds / 60)} min`;
  return `${seconds} s`;
}

export function secondsSince(iso?: string, now = Date.now()): number {
  if (!iso) return Infinity;
  return (now - Date.parse(iso)) / 1000;
}

export function ago(iso?: string, now = Date.now()): string {
  const s = secondsSince(iso, now);
  if (!Number.isFinite(s)) return 'never';
  if (s < 5) return 'just now';
  if (s < 60) return `${Math.floor(s)} s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso!).toLocaleDateString();
}

export function clock(iso: string | number): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function shortTime(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function actionLabel(action?: string): string {
  switch (action) {
    case 'MOVED_TO_BACKUP':
      return 'Moved to backup cooler';
    case 'FIXED':
      return 'Fixed (door / power)';
    case 'NEED_HELP':
      return 'Asked for help';
    default:
      return action ?? '';
  }
}

export function incidentTypeLabel(type?: string): string {
  switch (type) {
    case 'POWER_LOST':
      return 'Power lost';
    case 'SENSOR_OFFLINE':
      return 'Sensor silent';
    default:
      return 'Out of range';
  }
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}
