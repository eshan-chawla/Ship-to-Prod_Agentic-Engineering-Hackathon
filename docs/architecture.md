# Architecture

```mermaid
flowchart LR
  Web[Next.js Web App] --> API[FastAPI API]
  API --> PG[(Ghost.build / Postgres)]
  API --> Redis[(Redis)]
  API --> Queue[Redis scan_jobs list]
  Worker[Python Worker] --> Queue
  Worker --> Redis
  Worker --> TinyFish[TinyFish Provider]
  TinyFish --> Mock[MockTinyFish local fallback]
  Worker --> PG
  Worker --> Gov[Governance Adapter]
  Gov --> PG
```

## Modules

- Supplier Risk Radar manages suppliers, evidence, deterministic risk scoring, explanations, and threshold alerts.
- Pricing & Promo Copilot manages products, competitor URLs, price observations, recommendation logic, and evidence-backed explanations.
- Redis context engineering provides web result caching, short-term memory, semantic-cache placeholder methods, and queueing.
- Governance records agent runs, steps, and tool use locally. TODO: forward run metadata to Guild.ai once credentials and API contracts are finalized.

## Data Boundary

All external systems are accessed through interfaces:

- `TinyFishProviderInterface` for search, fetch, browser extraction, and agent runs.
- `RedisContext` for cache, memory, semantic placeholder, and queue primitives.
- `GovernanceRecorder` for Guild.ai-ready run tracking.

Local development does not require paid APIs.

