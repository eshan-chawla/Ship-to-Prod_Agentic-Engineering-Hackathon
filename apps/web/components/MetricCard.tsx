export function MetricCard({ label, value, tone = "moss" }: { label: string; value: string | number; tone?: "moss" | "clay" | "brass" }) {
  const toneClass = tone === "clay" ? "bg-clay" : tone === "brass" ? "bg-brass" : "bg-moss";
  return (
    <section className="panel reveal relative overflow-hidden p-5">
      <div className={`absolute right-0 top-0 h-full w-3 ${toneClass}`} />
      <p className="text-xs font-black uppercase tracking-[0.22em] text-ink/60">{label}</p>
      <p className="mt-3 text-5xl font-black leading-none">{value}</p>
    </section>
  );
}

