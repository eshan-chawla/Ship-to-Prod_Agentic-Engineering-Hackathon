import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { SupplierForm, ScanButton } from "@/components/Forms";
import { apiGet, Supplier } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SuppliersPage() {
  const suppliers = await apiGet<Supplier[]>("/suppliers");
  return (
    <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
      <section>
        <p className="text-xs font-black uppercase tracking-[0.24em] text-clay">Supplier Risk Radar</p>
        <h2 className="text-5xl font-black">Add supplier</h2>
        <p className="mt-3 max-w-lg font-semibold text-ink/70">Track source-backed operational, legal, cyber, and geopolitical risk with deterministic MVP scoring.</p>
        <div className="mt-6">
          <SupplierForm />
        </div>
      </section>
      <section className="space-y-4">
        {suppliers.length ? suppliers.map((supplier) => (
          <article key={supplier.id} className="panel p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <Link href={`/suppliers/${supplier.id}`} className="text-3xl font-black hover:text-clay">{supplier.name}</Link>
                <p className="mt-1 font-semibold text-ink/70">{supplier.category} · {supplier.country} · {supplier.criticality}</p>
                <a href={supplier.website} className="mt-2 inline-block text-sm font-black underline">{supplier.website}</a>
              </div>
              <ScanButton path={`/suppliers/${supplier.id}/scan`} label="Run supplier scan" />
            </div>
          </article>
        )) : <EmptyState title="No suppliers yet" body="Add a critical supplier to start building a risk evidence trail." />}
      </section>
    </div>
  );
}

