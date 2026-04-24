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
