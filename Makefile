.PHONY: setup dev up down seed test api-test web-lint worker

setup:
	cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd apps/web && npm install

dev: up

up:
	docker compose -f infra/docker-compose.yml up --build

down:
	docker compose -f infra/docker-compose.yml down

seed:
	cd apps/api && .venv/bin/python -m app.scripts.seed

test: api-test

api-test:
	cd apps/api && .venv/bin/pytest

web-lint:
	cd apps/web && npm run lint

worker:
	PYTHONPATH=apps/api apps/api/.venv/bin/python apps/worker/app/main.py
