import { AgentRun, apiGet, dateTime } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";

export const dynamic = "force-dynamic";

export default async function AgentRunsPage() {
  const runs = await apiGet<AgentRun[]>("/agent-runs");
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-black uppercase tracking-[0.24em] text-moss">Governance ledger</p>
        <h2 className="text-5xl font-black">Agent runs</h2>
        <p className="mt-2 max-w-2xl font-semibold text-ink/70">Local run tracking backs the Guild.ai integration placeholder. Every worker scan records lifecycle and tool-use audit events.</p>
      </div>
      {runs.length ? runs.map((run) => (
        <article key={run.id} className="panel p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="inline-block bg-moss px-2 py-1 text-xs font-black uppercase text-paper">{run.status}</p>
              <h3 className="mt-3 text-3xl font-black">{run.run_type}</h3>
              <p className="mt-1 font-semibold text-ink/70">{run.entity_type} #{run.entity_id}</p>
              <p className="mt-2 text-sm font-semibold text-ink/75">{run.summary || "Run is still collecting steps."}</p>
            </div>
            <p className="text-sm font-black text-ink/60">{dateTime(run.started_at)}</p>
          </div>
        </article>
      )) : <EmptyState title="No runs yet" body="Queue supplier or price scans to populate the governance ledger." />}
    </div>
  );
}

