# Demo Script

1. Start the stack with `make up`.
2. Seed data with `docker compose -f infra/docker-compose.yml exec api python -m app.scripts.seed`.
3. Open `http://localhost:3000/dashboard`.
4. Show overview KPIs, recent alerts, and agent run history.
5. Open `/suppliers`, add a supplier, and click scan.
6. Explain that the API enqueues a Redis job and the worker uses TinyFish through a provider abstraction.
7. Open the supplier detail page and review risk factors plus evidence.
8. Open `/products`, add a product and competitor URL, then run price scan.
9. Open the product detail page and review observations plus the recommendation.
10. Open `/agent-runs` and show tool use/step tracking placeholders for Guild.ai governance.

## Talk Track

The MVP is intentionally deterministic. Real LLM synthesis, TinyFish extraction, and Guild.ai tracking can be plugged in without changing API or UI contracts.

