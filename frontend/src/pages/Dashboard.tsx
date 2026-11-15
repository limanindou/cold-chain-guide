import { AlertTriangle, ListChecks, Moon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, SectionTitle, Skeleton, StatusPill } from '../components/bits';
import { DeviceCard } from '../components/DeviceCard';
import { ResponderPhones } from '../components/ResponderPhones';
import { SimulatorDrawer } from '../components/SimulatorDrawer';
import { Timeline } from '../components/Timeline';
import { ago, incidentTypeLabel } from '../lib/format';
import { ACTIVE_INCIDENT } from '../lib/status';
import { useNow } from '../lib/usePolling';
import { useDashboard } from '../state/DashboardContext';

export default function Dashboard() {
  const { data, readings, error, loading } = useDashboard();
  const now = useNow(1000);

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    );
  }
  if (!data) {
    return (
      <Card className="mx-auto max-w-lg p-6 text-center">
        <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-amber-500" aria-hidden />
        <p className="font-semibold">Can't reach the ColdChain Guard API</p>
        <p className="mt-1 text-sm text-slate-500">{error}</p>
      </Card>
    );
  }

  const profiles = Object.fromEntries(data.profiles.map((p) => [p.profileId, p]));
  const incidentsById = Object.fromEntries(data.incidents.map((i) => [i.incidentId, i]));
  const allOk = data.devices.every((d) => d.status === 'OK');
  const recent = data.incidents.slice(0, 6);

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-xl bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-300" role="alert">
          Connection problem — showing the last known state. ({error})
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          {allOk && (
            <div className="flex items-center gap-3 rounded-2xl bg-emerald-500/10 px-4 py-3 text-sm text-emerald-800 dark:text-emerald-200">
              <Moon className="h-4 w-4 shrink-0" aria-hidden />
              <span>
                All fridges are in range. <b>No workflow is running</b> — while everything is fine, ColdChain Guard
                only runs a tiny once-a-minute check for silent sensors (free tier).
              </span>
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {data.devices.map((d) => (
              <DeviceCard
                key={d.deviceId}
                device={d}
                profile={profiles[d.profileId]}
                readings={readings[d.deviceId] ?? []}
                incident={d.openIncidentId ? incidentsById[d.openIncidentId] : undefined}
                now={now}
                timeScale={data.config.timeScale}
              />
            ))}
          </div>
          <ResponderPhones responders={data.responders} incidents={data.incidents} devices={data.devices} now={now} />
          <SimulatorDrawer />
        </div>

        <aside className="space-y-6">
          <Card className="p-4">
            <SectionTitle icon={<ListChecks className="h-4 w-4" aria-hidden />}>Incident timeline</SectionTitle>
            <div className="max-h-[560px] overflow-y-auto pr-1">
              <Timeline
                events={data.events.slice(0, 40)}
                responders={data.responders}
                showDevice
                linkIncidents
                emptyText="Quiet. Nothing has gone out of range."
              />
            </div>
          </Card>
          <Card className="p-4">
            <SectionTitle>Recent incidents</SectionTitle>
            {recent.length ? (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {recent.map((i) => (
                  <li key={i.incidentId}>
                    <Link
                      to={`/incidents/${i.incidentId}`}
                      className="flex items-center justify-between gap-2 rounded-lg px-1 py-2 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{i.deviceName}</span>
                        <span className="text-xs text-slate-500">
                          {incidentTypeLabel(i.type)} · {ago(i.startedAt, now)}
                          {ACTIVE_INCIDENT.has(i.status) ? ' · in progress' : ''}
                        </span>
                      </span>
                      <StatusPill status={i.status} className="shrink-0" />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-4 text-center text-sm text-slate-500">No incidents yet.</p>
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}
