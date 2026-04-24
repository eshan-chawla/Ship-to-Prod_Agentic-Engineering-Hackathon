import { FactorDetail } from "@/lib/api";

type RiskGaugeValue = {
  score: number;
  explanation: string;
  financial_stress: number;
  legal_regulatory: number;
  delivery_disruption: number;
  sentiment: number;
  cybersecurity: number;
  geopolitical: number;
  factor_details?: Record<string, FactorDetail>;
};

const factors = [
  ["financial_stress", "Financial"],
  ["legal_regulatory", "Legal"],
  ["delivery_disruption", "Delivery"],
  ["sentiment", "Sentiment"],
  ["cybersecurity", "Cyber"],
  ["geopolitical", "Geo"],
] as const;

export function RiskGauge({ risk }: { risk: RiskGaugeValue }) {
  const details = risk.factor_details ?? {};
  return (
    <section className="panel p-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-clay">Risk score</p>
          <h2 className="text-6xl font-black">{risk.score}/100</h2>
        </div>
        <p className="max-w-2xl text-sm font-semibold text-ink/75">{risk.explanation}</p>
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {factors.map(([key, label]) => {
          const score = risk[key];
          const detail = details[key];
          const confidencePct = detail ? Math.round(detail.confidence * 100) : null;
          const evidenceCount = detail?.evidence_ids?.length ?? 0;
          return (
            <div key={key}>
              <div className="flex justify-between text-xs font-black uppercase tracking-[0.16em]">
                <span>{label}</span>
                <span>{score}</span>
              </div>
              <div className="mt-1 h-3 border-2 border-ink bg-[#fffaf0]">
                <div className="h-full bg-clay" style={{ width: `${Math.min(100, score)}%` }} />
              </div>
              {detail ? (
                <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink/55">
                  Confidence {confidencePct}% · {evidenceCount} evidence
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
