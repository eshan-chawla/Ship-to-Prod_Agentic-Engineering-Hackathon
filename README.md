# AI Market Intelligence OS

Production-ready MVP for B2B supplier risk and pricing intelligence. It runs locally without paid APIs by using `MockTinyFishProvider` when `TINYFISH_API_KEY` is absent.

## Stack

- Frontend: Next.js, TypeScript, Tailwind
- Backend: FastAPI, Python, SQLModel
- Database: Postgres-compatible Ghost.build connection via `DATABASE_URL`
- Cache, queue, memory: Redis
- Worker: Python Redis queue consumer
- Governance: local `agent_runs` and `audit_logs` with Guild.ai integration TODOs

## Quick Start

1. Copy env values:

```bash
cp .env.example .env
```

2. Start the local stack:

```bash
make up
```

3. Seed demo data in another shell:

```bash
docker compose -f infra/docker-compose.yml exec api python -m app.scripts.seed
```

4. Open:

- Web: `http://localhost:3000/dashboard`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Local Development Without Docker

```bash
make setup
cd apps/api && DATABASE_URL=sqlite:///./market_os.db REDIS_URL=redis://localhost:6379/0 .venv/bin/python -m app.scripts.seed
cd apps/api && .venv/bin/uvicorn app.main:app --reload
PYTHONPATH=apps/api apps/api/.venv/bin/python apps/worker/app/main.py
cd apps/web && npm run dev
```

## Core Flows

- Add suppliers and enqueue scans from `/suppliers`.
- Worker consumes `scan_jobs` from Redis and writes evidence, risk scores, alerts, audit logs, and agent runs.
- Add products and competitor URLs from `/products`.
- Worker extracts mock competitor price signals and writes observations plus recommendations.
- Redis stores TinyFish fetch/search cache entries, short-term agent memory, and a semantic-cache placeholder.

## Tests

```bash
make api-test
```

## Integration Notes

- TinyFish integration is isolated in `apps/api/app/integrations/tinyfish.py`.
- Ghost.build/Postgres is configured through `DATABASE_URL`.
- Redis queue/context logic is isolated in `apps/api/app/integrations/redis_context.py` and `apps/api/app/services/queues.py`.
- Guild.ai is represented by `apps/api/app/integrations/governance.py`; it currently records to local DB tables and includes TODOs for real run tracking.

## TinyFish Configuration

Local mock mode is the default. If `TINYFISH_API_KEY` is empty, API and worker processes use `MockTinyFishProvider` and never call paid external APIs.

Set these variables to enable real TinyFish calls:

```bash
TINYFISH_API_KEY=your_key_here
TINYFISH_SEARCH_URL=https://api.search.tinyfish.ai
TINYFISH_FETCH_URL=https://api.fetch.tinyfish.ai
TINYFISH_AGENT_URL=https://agent.tinyfish.ai/v1/automation/run
TINYFISH_TIMEOUT_SECONDS=20
TINYFISH_MAX_RETRIES=2
```

Provider behavior:

- `search_web(query)` calls TinyFish Search with `GET TINYFISH_SEARCH_URL?query=...`.
- `fetch_url(url)` calls TinyFish Fetch with `POST TINYFISH_FETCH_URL` and `{"urls": [url], "format": "markdown"}`.
- `browser_extract(url, task)` calls TinyFish Agent sync run with `POST TINYFISH_AGENT_URL`, `url`, `goal`, `browser_profile: lite`, and a structured output schema for price, stock, promo, and raw text.
- All real calls use the `X-API-Key` header, retry `429` and `5xx` responses, retry transport timeouts, and emit structured logs.
- Supplier and product scans store normalized TinyFish raw payloads in `evidence_items.raw_payload`.

To test real mode locally:

```bash
cp .env.example .env
# edit .env and set TINYFISH_API_KEY
make up
docker compose -f infra/docker-compose.yml exec api python -m app.scripts.seed
```
