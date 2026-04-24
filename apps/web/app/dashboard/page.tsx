import Link from "next/link";
import { MetricCard } from "@/components/MetricCard";
import { apiGet, Dashboard, dateTime, pricingActionLabel } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const data = await apiGet<Dashboard>("/dashboard");
  return (
    <div className="space-y-8">
      <section className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Suppliers watched" value={data.suppliers} tone="moss" />
        <MetricCard label="Products tracked" value={data.products} tone="brass" />
        <MetricCard label="Open alerts" value={data.open_alerts} tone="clay" />
        <MetricCard label="Agent runs" value={data.agent_runs} tone="moss" />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="panel p-6">
          <p className="text-xs font-black uppercase tracking-[0.24em] text-clay">Supplier Risk Radar</p>
          <h2 className="text-4xl font-black">Latest risk signals</h2>
          <div className="mt-5 space-y-3">
            {data.latest_risks.map((risk) => (
              <Link key={risk.id} href={`/suppliers/${risk.supplier_id}`} className="block border-2 border-ink bg-[#fffaf0] p-4 hover:bg-brass/30">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-black">Supplier #{risk.supplier_id}</span>
                  <span className="text-2xl font-black">{risk.score}/100</span>
                </div>
                <p className="mt-2 text-sm font-semibold text-ink/70">{risk.explanation}</p>
              </Link>
            ))}
          </div>
        </div>

        <div className="panel p-6">
          <p className="text-xs font-black uppercase tracking-[0.24em] text-moss">Pricing Copilot</p>
          <h2 className="text-4xl font-black">Current calls</h2>
          <div className="mt-5 space-y-3">
            {data.latest_recommendations.map((rec) => (
              <Link key={rec.id} href={`/products/${rec.product_id}`} className="block border-2 border-ink bg-[#fffaf0] p-4 hover:bg-moss/20">
                <p className="text-lg font-black">{pricingActionLabel(rec.action)}</p>
                <p className="mt-1 text-sm font-semibold text-ink/70">{rec.explanation}</p>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="panel p-6">
          <h2 className="text-3xl font-black">Recent alerts</h2>
          <div className="mt-4 space-y-3">
            {data.recent_alerts.map((alert) => (
              <div key={alert.id} className="border-l-8 border-clay bg-[#fffaf0] p-4">
                <p className="font-black">{alert.title}</p>
                <p className="text-sm font-semibold text-ink/70">{alert.message}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="panel p-6">
          <h2 className="text-3xl font-black">Agent run history</h2>
          <div className="mt-4 space-y-3">
            {data.recent_agent_runs.map((run) => (
              <div key={run.id} className="flex justify-between gap-4 border-2 border-ink bg-[#fffaf0] p-4">
                <div>
                  <p className="font-black">{run.run_type}</p>
                  <p className="text-sm font-semibold text-ink/65">{run.summary || "No summary yet"}</p>
                </div>
                <p className="text-right text-xs font-black uppercase text-ink/60">{dateTime(run.started_at)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

