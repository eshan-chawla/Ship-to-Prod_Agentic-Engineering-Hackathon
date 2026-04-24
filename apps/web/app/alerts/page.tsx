import { EmptyState } from "@/components/EmptyState";
import { Alert, apiGet, dateTime } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AlertsPage() {
  const alerts = await apiGet<Alert[]>("/alerts");
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-black uppercase tracking-[0.24em] text-clay">Exception queue</p>
        <h2 className="text-5xl font-black">Alerts</h2>
      </div>
      {alerts.length ? alerts.map((alert) => (
        <article key={alert.id} className="panel p-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="inline-block bg-clay px-2 py-1 text-xs font-black uppercase text-paper">{alert.severity}</p>
              <h3 className="mt-3 text-3xl font-black">{alert.title}</h3>
              <p className="mt-2 font-semibold text-ink/75">{alert.message}</p>
            </div>
            <p className="text-sm font-black text-ink/60">{dateTime(alert.created_at)}</p>
          </div>
        </article>
      )) : <EmptyState title="No alerts" body="Risk and pricing alerts will appear here when thresholds are crossed." />}
    </div>
  );
}

