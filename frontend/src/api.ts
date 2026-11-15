import { getConfig } from './config';
import type { DashboardData, IncidentDetail, Profile, RespondResult, ResponderAction } from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { apiUrl } = getConfig();
  if (!apiUrl) throw new ApiError(0, 'API URL is not configured (config.json / VITE_API_URL)');
  const res = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : {};
  if (!res.ok) throw new ApiError(res.status, body?.error ?? body?.message ?? res.statusText, body);
  return body as T;
}

export const api = {
  dashboard: (since?: string) =>
    request<DashboardData>(`/dashboard${since ? `?since=${encodeURIComponent(since)}` : ''}`),
  incident: (id: string) => request<IncidentDetail>(`/incidents/${encodeURIComponent(id)}`),
  profiles: () => request<{ profiles: Profile[] }>('/profiles'),

  postReading: (deviceId: string, tempC: number, batteryPct?: number) =>
    request<unknown>('/readings', {
      method: 'POST',
      headers: { 'x-device-key': getConfig().deviceKey },
      body: JSON.stringify({ deviceId, tempC, batteryPct }),
    }),

  postEvent: (deviceId: string, type: 'POWER_LOST' | 'POWER_RESTORED', batteryPct?: number) =>
    request<unknown>('/events', {
      method: 'POST',
      headers: { 'x-device-key': getConfig().deviceKey },
      body: JSON.stringify({ deviceId, type, batteryPct }),
    }),

  async respond(incidentId: string, ackCode: string, action: ResponderAction, note = ''): Promise<RespondResult> {
    try {
      return await request<RespondResult>(`/incidents/${encodeURIComponent(incidentId)}/respond`, {
        method: 'POST',
        body: JSON.stringify({ ackCode, action, note }),
      });
    } catch (err) {
      if (err instanceof ApiError && err.body && typeof err.body === 'object' && 'result' in err.body) {
        return err.body as RespondResult;
      }
      return { result: 'ERROR', message: err instanceof Error ? err.message : 'Something went wrong' };
    }
  },

  resetDemo: () =>
    request<{ stopped: number; cancelled: number }>('/demo/reset', {
      method: 'POST',
      headers: { 'x-device-key': getConfig().deviceKey },
      body: JSON.stringify({ clearReadings: true }),
    }),
};

export function evidenceUrl(path?: string): string | undefined {
  if (!path) return undefined;
  return `${getConfig().siteUrl}${path}`;
}
