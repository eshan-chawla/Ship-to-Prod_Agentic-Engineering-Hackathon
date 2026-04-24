import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { ScanButton } from "@/components/Forms";
import { RiskGauge } from "@/components/RiskGauge";
import { apiGet, dateTime, Evidence, Supplier, SupplierRisk } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SupplierDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supplier = await apiGet<Supplier>(`/suppliers/${id}`);
  const risk = await apiGet<SupplierRisk | null>(`/suppliers/${id}/risk`);
  const evidence = await apiGet<Evidence[]>(`/suppliers/${id}/evidence`);

  return (
    <div className="space-y-7">
      <Link href="/suppliers" className="text-sm font-black underline">Back to suppliers</Link>
      <section className="panel p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-clay">{supplier.category}</p>
            <h2 className="text-5xl font-black">{supplier.name}</h2>
            <p className="mt-2 font-semibold text-ink/70">{supplier.country} · {supplier.criticality} criticality</p>
          </div>
          <ScanButton path={`/suppliers/${supplier.id}/scan`} label="Run new scan" />
        </div>
      </section>

      {risk ? <RiskGauge risk={risk} /> : <EmptyState title="No risk score yet" body="Run a supplier scan and keep the worker online to generate evidence-backed scoring." />}

      <section className="panel p-6">
        <h3 className="text-4xl font-black">Evidence ledger</h3>
        <div className="mt-5 space-y-3">
          {evidence.length ? evidence.map((item) => (
            <article key={item.id} className="border-2 border-ink bg-[#fffaf0] p-4">
              <div className="flex flex-col gap-2 md:flex-row md:justify-between">
                <a href={item.source_url} className="font-black underline">{item.source_title}</a>
                <span className="text-xs font-black uppercase text-ink/55">{dateTime(item.captured_at)}</span>
              </div>
              <p className="mt-2 text-sm font-semibold text-ink/75">{truncateEvidence(item.content)}</p>
              {item.risk_factor ? <p className="mt-2 inline-block bg-brass px-2 py-1 text-xs font-black uppercase">{item.risk_factor.replaceAll("_", " ")}</p> : null}
            </article>
          )) : <EmptyState title="No evidence captured" body="Evidence items are stored raw from TinyFish search, fetch, and browser extraction calls." />}
        </div>
      </section>
    </div>
  );
}

function truncateEvidence(value: string) {
  if (value.length <= 760) {
    return value;
  }
  return `${value.slice(0, 740).trim()}...`;
}
