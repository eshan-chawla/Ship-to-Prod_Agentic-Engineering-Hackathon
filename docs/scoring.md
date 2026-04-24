# Scoring & Recommendation Engine

Both engines live in [apps/api/app/services/scoring.py](../apps/api/app/services/scoring.py) as pure functions.
They're deterministic, unit-tested, and evidence-backed — no LLM in the critical path.

## Supplier Risk Radar

### Inputs

`score_risk_evidence(evidence, criticality)` takes:

- `evidence` — list of dicts, each with:
  - `title`, `content`, `snippet` — free text scanned for factor keywords
  - `risk_factor` — optional hinted primary factor (adds an 8-point boost)
  - `id` — optional `EvidenceItem.id` (recorded in per-factor `evidence_ids`)
- `criticality` — `"low" | "medium" | "high" | "critical"` (applies a multiplier)

### Factors

Six weighted factors. Each has a keyword→weight map (see `FACTOR_KEYWORD_WEIGHTS`):

| Factor                 | Example keywords                                         |
| ---------------------- | -------------------------------------------------------- |
| `financial_stress`     | debt, cash flow, downgrade, bankruptcy, insolvency       |
| `legal_regulatory`     | regulatory, compliance, lawsuit, sanction, consent order |
| `delivery_disruption`  | delay, shortage, slowdown, strike, shutdown, port        |
| `sentiment`            | complaint, negative, boycott, controversy, labor dispute |
| `cybersecurity`        | ransomware, breach, data exposure, cyber, security patch |
| `geopolitical`         | tariff, border, war, instability, export control         |

### Scoring algorithm

For each evidence item:

1. Concatenate title + content + snippet and lowercase.
2. For each factor, sum the weight of every matching keyword. Add **+8** if the item's `risk_factor` hint matches this factor.
3. Per-item contribution to a factor is capped at **35** to prevent a single hot piece of evidence from saturating one factor.
4. Factor scores accumulate across items, capped at **100**.

After all items are processed:

- **Total score** = `round((mean(non_zero_factors) * 0.65 + max(factors) * 0.35) * criticality_multiplier)`, clamped to `[0, 100]`.
- **Criticality multipliers**: low 0.85, medium 1.0, high 1.15, critical 1.3.

### Per-factor detail

Each factor exposes:

```python
factor_details[factor] = {
    "score": int,            # 0..100
    "confidence": float,     # 0..1 — min(1.0, hits / 3.0)
    "evidence_ids": list[int],
}
```

Confidence is hit-count based: **1 hit → 0.33, 2 → 0.67, 3+ → 1.0**. A factor scored once off a single lucky keyword is explicitly marked as low confidence.

Evidence IDs are recorded only when the caller passes `id` on each evidence dict — the [supplier scanner](../apps/api/app/services/supplier_scanner.py) flushes each `EvidenceItem` to get its primary key before calling the scorer.

### Explainability

`explanation` names the top factor and lists the top three ranked contributors. Example:

> Risk score 82/100 is driven primarily by delivery disruption. Top contributing factors: delivery disruption 53, cybersecurity 42, financial stress 29.

The frontend [RiskGauge](../apps/web/components/RiskGauge.tsx) renders the total score, per-factor bars, and per-factor confidence + evidence count underneath.

## Pricing & Promo Copilot

### Inputs

`recommend_price(target_price, target_margin, observations, trend=None)` takes:

- `target_price` — our list price
- `target_margin` — our target margin (0–1)
- `observations` — list of competitor observations with `price`, `stock_status`, `promo_signal`
- `trend` — optional chronological list of our recent prices (used for conflict detection)

### Actions

Exactly five enum values live in `PRICING_ACTIONS`:

| Action          | When it fires                                                          |
| --------------- | ---------------------------------------------------------------------- |
| `HOLD_PRICE`    | Gap is small (within ±8–10%) or no stronger signal wins                |
| `LOWER_PRICE`   | Target is ≥8% above avg competitor price *and* no competitor is promo-ing |
| `LAUNCH_PROMO`  | Target is ≥8% above avg *and* at least one competitor shows a promo    |
| `RAISE_PRICE`   | Target is ≥10% below avg *and* our `target_margin` ≥ 0.25              |
| `INVESTIGATE`   | No observations, or data is too thin, or trend conflicts with the gap signal |

### Decision algorithm

1. If `observations` is empty → `INVESTIGATE` with confidence 0.3.
2. Compute `comparison_set` = in-stock observations (fall back to all if none in-stock).
3. `avg_competitor = mean(comparison_set.price)`; `gap = (target_price - avg_competitor) / target_price`.
4. `promo_count` = non-"none" promo signals in the comparison set.
5. Apply the gap/promo/margin rules above to pick an action.
6. **Trend override**: if historical trend is rising but action is `LOWER_PRICE`, or trend is falling but action is `RAISE_PRICE`, downgrade to `INVESTIGATE` (the signals disagree, so a human should look).
7. **Thin-data override**: fewer than 2 usable observations *and* action isn't already `HOLD_PRICE` → `INVESTIGATE`.

Trend direction is computed as:
- `up` if last / first > +5%
- `down` if last / first < −5%
- `flat` otherwise

### Output

```python
{
    "action": str,            # one of PRICING_ACTIONS
    "confidence": float,      # 0.55 + 0.08*len(comparison_set), capped at 0.92; capped at 0.5 for INVESTIGATE
    "expected_impact": str,   # action-specific one-liner
    "explanation": str,       # includes target, avg, promo count, optional trend
}
```

Expected-impact examples:

| Action         | Impact line                                                                 |
| -------------- | --------------------------------------------------------------------------- |
| `HOLD_PRICE`   | Preserve current margin ~30%; no action needed.                             |
| `LOWER_PRICE`  | Close the $12.00 gap to stabilize conversion and protect share.             |
| `RAISE_PRICE`  | Capture $18.50 premium; monitor unit velocity for softness.                 |
| `LAUNCH_PROMO` | Match 2 competitor promo signal(s); expect short-term volume lift.          |
| `INVESTIGATE`  | Data insufficient or signals conflict; human review recommended before acting. |

The [pricing scanner](../apps/api/app/services/pricing_scanner.py) passes historical price observations as `trend` so the engine can detect conflicts automatically.

## API response shape

`GET /suppliers/{id}/risk` returns `SupplierRiskRead` ([dto.py](../apps/api/app/schemas/dto.py)):

```json
{
  "score": 82,
  "financial_stress": 29,
  "...": "...",
  "factor_details": {
    "financial_stress": {"score": 29, "confidence": 0.33, "evidence_ids": [101]},
    "delivery_disruption": {"score": 53, "confidence": 0.67, "evidence_ids": [102, 103]},
    "...": "..."
  },
  "explanation": "Risk score 82/100 is driven primarily by delivery disruption..."
}
```

`GET /products/{id}/recommendations` returns `PriceRecommendationRead` list:

```json
[
  {
    "action": "LAUNCH_PROMO",
    "confidence": 0.82,
    "expected_impact": "Match 1 competitor promo signal(s); expect short-term volume lift.",
    "explanation": "Target price $129.00 vs average competitor price $122.25..."
  }
]
```

## Tests

[apps/api/app/tests/test_scoring.py](../apps/api/app/tests/test_scoring.py) covers:

- Supplier: determinism + bounds, multi-factor extraction, per-factor confidence + evidence IDs, empty-evidence zero-score.
- Pricing: each of the five actions, INVESTIGATE on empty obs, INVESTIGATE on trend/gap conflict, all outputs carry required keys, action always ∈ `PRICING_ACTIONS`.

Run:

```bash
cd apps/api && .venv/bin/pytest app/tests/test_scoring.py -v
```
