import Link from "next/link";
import { CompetitorForm, ScanButton } from "@/components/Forms";
import { EmptyState } from "@/components/EmptyState";
import { apiGet, CompetitorUrl, dateTime, Evidence, money, PriceObservation, PriceRecommendation, Product } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = await apiGet<Product>(`/products/${id}`);
  const competitors = await apiGet<CompetitorUrl[]>(`/products/${id}/competitors`);
  const observations = await apiGet<PriceObservation[]>(`/products/${id}/observations`);
  const recommendations = await apiGet<PriceRecommendation[]>(`/products/${id}/recommendations`);
  const evidence = await apiGet<Evidence[]>(`/products/${id}/evidence`);

  return (
    <div className="space-y-7">
      <Link href="/products" className="text-sm font-black underline">Back to products</Link>
      <section className="panel p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-moss">{product.brand} · {product.category}</p>
            <h2 className="text-5xl font-black">{product.name}</h2>
            <p className="mt-2 font-semibold text-ink/70">Target {money(product.target_price)} · Margin {(product.target_margin * 100).toFixed(0)}%</p>
          </div>
          <ScanButton path={`/products/${product.id}/scan-prices`} label="Run price scan" />
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <h3 className="mb-3 text-3xl font-black">Add competitor</h3>
          <CompetitorForm productId={product.id} />
        </div>
        <div className="panel p-6">
          <h3 className="text-3xl font-black">Competitor URLs</h3>
          <div className="mt-4 space-y-3">
            {competitors.length ? competitors.map((competitor) => (
              <a key={competitor.id} href={competitor.url} className="block border-2 border-ink bg-[#fffaf0] p-3 font-black underline">
                {competitor.competitor_name}
              </a>
            )) : <EmptyState title="No competitors" body="Add URLs to enable browser extraction for price and promo signals." />}
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="panel p-6">
          <h3 className="text-3xl font-black">Recommendations</h3>
          <div className="mt-4 space-y-3">
            {recommendations.length ? recommendations.map((rec) => (
              <article key={rec.id} className="border-2 border-ink bg-brass/25 p-4">
                <p className="text-2xl font-black capitalize">{rec.action}</p>
                <p className="mt-2 text-sm font-semibold text-ink/75">{rec.explanation}</p>
                <p className="mt-2 text-xs font-black uppercase">Confidence {(rec.confidence * 100).toFixed(0)}%</p>
              </article>
            )) : <EmptyState title="No recommendation yet" body="Run a price scan after adding competitor URLs." />}
          </div>
        </div>
        <div className="panel p-6">
          <h3 className="text-3xl font-black">Price observations</h3>
          <div className="mt-4 space-y-3">
            {observations.length ? observations.map((obs) => (
              <article key={obs.id} className="border-2 border-ink bg-[#fffaf0] p-4">
                <div className="flex justify-between gap-4">
                  <p className="font-black">{obs.competitor_name}</p>
                  <p className="text-xl font-black">{money(obs.price)}</p>
                </div>
                <p className="mt-1 text-sm font-semibold text-ink/70">{obs.stock_status} · {obs.promo_signal} · {dateTime(obs.observed_at)}</p>
              </article>
            )) : <EmptyState title="No observations" body="The worker stores every extracted price point with a timestamp." />}
          </div>
        </div>
      </section>

      <section className="panel p-6">
        <h3 className="text-3xl font-black">Evidence</h3>
        <div className="mt-4 space-y-3">
          {evidence.length ? evidence.map((item) => (
            <article key={item.id} className="border-2 border-ink bg-[#fffaf0] p-4">
              <a href={item.source_url} className="font-black underline">{item.source_title}</a>
              <p className="mt-2 text-sm font-semibold text-ink/75">{item.content}</p>
            </article>
          )) : <EmptyState title="No evidence captured" body="Price evidence is recorded from TinyFish browser extraction output." />}
        </div>
      </section>
    </div>
  );
}

