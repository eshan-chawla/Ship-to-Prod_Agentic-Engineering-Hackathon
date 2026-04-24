import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { ProductForm, ScanButton } from "@/components/Forms";
import { apiGet, money, Product } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ProductsPage() {
  const products = await apiGet<Product[]>("/products");
  return (
    <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
      <section>
        <p className="text-xs font-black uppercase tracking-[0.24em] text-moss">Pricing & Promo Copilot</p>
        <h2 className="text-5xl font-black">Add SKU</h2>
        <p className="mt-3 max-w-lg font-semibold text-ink/70">Track competitor prices, stock status, promotion signals, and deterministic pricing recommendations.</p>
        <div className="mt-6">
          <ProductForm />
        </div>
      </section>
      <section className="space-y-4">
        {products.length ? products.map((product) => (
          <article key={product.id} className="panel p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <Link href={`/products/${product.id}`} className="text-3xl font-black hover:text-moss">{product.name}</Link>
                <p className="mt-1 font-semibold text-ink/70">{product.brand} · {product.category}</p>
                <p className="mt-2 text-sm font-black">Target {money(product.target_price)} · Margin {(product.target_margin * 100).toFixed(0)}%</p>
              </div>
              <ScanButton path={`/products/${product.id}/scan-prices`} label="Run price scan" />
            </div>
          </article>
        )) : <EmptyState title="No products yet" body="Add a SKU, then attach competitor URLs for price scanning." />}
      </section>
    </div>
  );
}

