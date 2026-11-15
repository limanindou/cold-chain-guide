export type DeviceStatus = 'OK' | 'GRACE' | 'ALERTING' | 'ACKNOWLEDGED' | 'CRITICAL';
export type IncidentStatus =
  | 'GRACE'
  | 'ALERTING'
  | 'ACKNOWLEDGED'
  | 'RECOVERED'
  | 'RESOLVED'
  | 'CRITICAL_UNACKNOWLEDGED'
  | 'CRITICAL_NOT_RECOVERED'
  | 'CANCELLED'
  | 'FAILED_TO_START';
export type IncidentType = 'TEMP_EXCURSION' | 'POWER_LOST' | 'SENSOR_OFFLINE';
export type ResponderAction = 'MOVED_TO_BACKUP' | 'FIXED' | 'NEED_HELP';

export interface Profile {
  profileId: string;
  label: string;
  icon: string;
  description?: string;
  minC?: number | null;
  maxC?: number | null;
  graceSeconds: number;
  ackTimeoutSeconds: number;
  powerGraceSeconds?: number;
  offlineAfterSeconds?: number;
  recoveryWindowSeconds?: number;
  recheckSeconds?: number;
  escalation: string[];
  baselineC?: number;
}

export interface Device {
  deviceId: string;
  name: string;
  location: string;
  profileId: string;
  status: DeviceStatus;
  lastTempC?: number;
  lastSeen?: string;
  openIncidentId?: string;
  incidentStartedAt?: string;
  powerSource?: 'MAINS' | 'BATTERY';
  batteryPct?: number;
  offlineSince?: string;
}

export interface Reading {
  ts: string;
  tempC: number;
}

export interface IncidentEvent {
  incidentId: string;
  deviceId?: string;
  deviceName?: string;
  ts: string;
  type: string;
  actor?: string;
  detail?: string;
  toResponder?: string;
  action?: ResponderAction;
  level?: number;
  sha256?: string;
}

export interface PendingAck {
  code?: string;
  responderId: string;
  responderName: string;
  responderRole?: string;
  level: number;
  notifiedAt: string;
  expiresAt: string;
}

export interface Incident {
  incidentId: string;
  deviceId: string;
  deviceName: string;
  location?: string;
  profileId: string;
  profileLabel?: string;
  type?: IncidentType;
  powerRestoredAt?: string;
  status: IncidentStatus;
  startedAt: string;
  recoveredAt?: string;
  resolvedAt?: string;
  criticalAt?: string;
  tempRestoredAt?: string;
  firstTempC?: number;
  direction?: 'HIGH' | 'LOW';
  minC?: number | null;
  maxC?: number | null;
  level: number;
  executionArn?: string;
  consoleUrl?: string;
  graceEndsAt?: string;
  pendingAck?: PendingAck;
  ackedBy?: string;
  ackedByName?: string;
  ackedAction?: ResponderAction;
  ackedAt?: string;
  evidenceKey?: string;
  evidencePath?: string;
  evidenceHtmlPath?: string;
  evidenceSha256?: string;
  sealedAt?: string;
  outOfRangeSeconds?: number;
  minTempC?: number;
  maxTempC?: number;
}

export interface Responder {
  responderId: string;
  name: string;
  role: string;
}

export interface AppConfig {
  timeScale: number;
  demoMode: boolean;
  region: string;
  stateMachineArn: string;
}

export interface DashboardData {
  serverTime: string;
  since: string;
  devices: Device[];
  readings: Record<string, Reading[]>;
  incidents: Incident[];
  events: IncidentEvent[];
  profiles: Profile[];
  responders: Responder[];
  config: AppConfig;
}

export interface IncidentDetail {
  incident: Incident;
  events: IncidentEvent[];
  readings: Reading[];
  device: Device;
  profile: Profile;
  responders: Responder[];
  config: AppConfig;
}

export interface RespondResult {
  result: 'OK' | 'ALREADY_HANDLED' | 'EXPIRED' | 'NOT_FOUND' | 'ERROR';
  message?: string;
  action?: ResponderAction;
  handledBy?: string;
  handledAt?: string;
  responderName?: string;
}
