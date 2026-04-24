# Vapi Voice Assistant Integration

The backend ships four voice tools plus a Vapi webhook. Each tool returns a
short spoken-text response suitable for a phone call. Configure your Vapi
assistant either by:

- pointing individual tools at the REST endpoints (one HTTPS call per tool), or
- pointing a single "server URL" at `POST /voice/webhook` and registering tools
  that dispatch by name.

## REST endpoints

All endpoints return `{"spoken": "<text>", "data": <structured>}`.

### GET `/voice/high-risk-suppliers`

Supplier scores above `RISK_ALERT_THRESHOLD` (default 70), top 3, ordered by
score descending. Answers: *"What suppliers are high risk today?"*

**Example response:**
```json
{
  "spoken": "2 suppliers are above threshold. Top is Nippon Precision Components at 82 out of 100, driven by delivery disruption. Next: Atlas Cold Chain at 75.",
  "data": {"count": 2, "suppliers": [{"supplier_id": 1, "name": "Nippon Precision Components", "score": 82, "top_factor": "delivery_disruption"}, ...]}
}
```

### GET `/voice/supplier/{id}/summary`

Latest risk score, delta from previous scan, top factor, and open-alert count
for one supplier. Answers: *"Why did Supplier X risk score increase?"*

**Example response:**
```json
{
  "spoken": "Nippon Precision Components scored 82 out of 100. That's up 4 points from the previous scan. Top driver: delivery disruption. 1 open alert.",
  "data": {"supplier_id": 1, "score": 82, "previous_score": 78, "top_factor": "delivery_disruption", "open_alerts": 1}
}
```

Returns `404` if the supplier does not exist.

### GET `/voice/pricing/recommendations`

Latest recommendation per product, top 3, with `LAUNCH_PROMO`, `LOWER_PRICE`,
`RAISE_PRICE` prioritized over `INVESTIGATE` and `HOLD_PRICE`. Answers:
*"What pricing changes do you recommend today?"*

**Example response:**
```json
{
  "spoken": "3 pricing calls today. Smart Thermostat Pro: launch a promo. TrailBlend 12 Pack: hold price. AirSeal Bin: investigate further.",
  "data": {"count": 3, "recommendations": [...]}
}
```

### POST `/voice/subscribe-alert`

Persists a subscription in Redis (`voice:subscriptions` list, cap 200 entries).
Answers: *"Alert me if a competitor undercuts us."*

**Request body:**
```json
{
  "entity_type": "supplier",   // "supplier" | "product" | "any"
  "entity_id": 7,              // optional — null means "any"
  "condition": "risk score above 80",
  "channel": "sms",            // "voice" | "sms" | "email"
  "contact": "+14151234567"
}
```

**Response** (`201 Created`):
```json
{
  "spoken": "Got it. I'll notify +14151234567 by sms when supplier 7 matches: risk score above 80.",
  "data": {"subscription_id": "sub_9238...", ...},
  "subscription_id": "sub_9238..."
}
```

The subscription list is ephemeral Redis state — migrate to a durable table
when alerting moves beyond hackathon scope.

## Webhook endpoint — `POST /voice/webhook`

Accepts Vapi's tool-call envelope. Both shapes are understood:

```json
// Top-level shape
{"toolCalls": [{"id": "c1", "function": {"name": "<tool>", "arguments": "{...}"}}]}

// Nested shape (more common in recent Vapi versions)
{"message": {"toolCalls": [{"id": "c1", "function": {"name": "<tool>", "arguments": "{...}"}}]}}
```

Returns the Vapi-standard result envelope:

```json
{"results": [{"toolCallId": "c1", "result": "<spoken text>"}]}
```

### Tool names the webhook dispatches

| Name                     | Arguments                           | Returns                      |
| ------------------------ | ----------------------------------- | ---------------------------- |
| `high_risk_suppliers`    | *(none)*                            | Spoken top-3 summary         |
| `supplier_summary`       | `{"supplier_id": int}`              | Spoken per-supplier summary  |
| `pricing_recommendations`| *(none)*                            | Spoken top-3 recommendations |
| `subscribe_alert`        | Same body as the REST endpoint       | Confirmation sentence        |

Unknown tool names return `"Unknown tool: <name>."` so the assistant can say so
cleanly instead of erroring.

### Signature verification

Set `VAPI_WEBHOOK_SECRET` and flip `VAPI_MOCK_MODE=false` in production. The
webhook then requires an `X-Vapi-Signature` header set to
`sha256=<hmac-hex>` (or just the raw hex), computed over the raw request body
with the shared secret. Mismatches return `401`.

In the default **mock mode** (`VAPI_MOCK_MODE=true`) the signature header is
ignored — useful for local testing and CI.

## Vapi tool schema — paste into the Vapi dashboard

Copy each block into a Vapi assistant's "Tools" section. Replace
`https://your-api` with your public API URL.

### `high_risk_suppliers`

```json
{
  "type": "function",
  "function": {
    "name": "high_risk_suppliers",
    "description": "Returns suppliers whose latest risk score is above the alert threshold, top 3 by score.",
    "parameters": {"type": "object", "properties": {}, "required": []}
  },
  "server": {"url": "https://your-api/voice/webhook"}
}
```

### `supplier_summary`

```json
{
  "type": "function",
  "function": {
    "name": "supplier_summary",
    "description": "Concise summary of one supplier's latest risk score, trend, top driving factor, and open alerts.",
    "parameters": {
      "type": "object",
      "properties": {
        "supplier_id": {"type": "integer", "description": "Numeric supplier id."}
      },
      "required": ["supplier_id"]
    }
  },
  "server": {"url": "https://your-api/voice/webhook"}
}
```

### `pricing_recommendations`

```json
{
  "type": "function",
  "function": {
    "name": "pricing_recommendations",
    "description": "Top 3 pricing actions across tracked products, prioritizing promos and price changes over holds.",
    "parameters": {"type": "object", "properties": {}, "required": []}
  },
  "server": {"url": "https://your-api/voice/webhook"}
}
```

### `subscribe_alert`

```json
{
  "type": "function",
  "function": {
    "name": "subscribe_alert",
    "description": "Subscribe the caller to alerts on a supplier, product, or any entity matching a free-text condition.",
    "parameters": {
      "type": "object",
      "properties": {
        "entity_type": {"type": "string", "enum": ["supplier", "product", "any"]},
        "entity_id":   {"type": ["integer", "null"], "description": "Numeric id, or null for any."},
        "condition":   {"type": "string", "description": "Plain-language condition, e.g. 'risk above 80' or 'competitor undercuts 10%'."},
        "channel":     {"type": "string", "enum": ["voice", "sms", "email"]},
        "contact":     {"type": "string", "description": "Phone number or email."}
      },
      "required": ["entity_type", "condition", "channel", "contact"]
    }
  },
  "server": {"url": "https://your-api/voice/webhook"}
}
```

## Exposing the API to Vapi (port 8000, not 3000)

Vapi's servers can't reach `http://localhost:*` — you need a public HTTPS URL.
The **API** runs on port **8000** (FastAPI). Port **3000** is the Next.js
dashboard you view in your browser; Vapi does not call it. Expose port 8000.

The simplest way during a hackathon is [ngrok](https://ngrok.com):

```bash
# In a separate terminal, while uvicorn is running on :8000
ngrok http 8000
```

ngrok prints a Forwarding line like:

```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8000
```

Paste that HTTPS URL into each tool schema's `server.url`, appending
`/voice/webhook`:

```json
"server": {"url": "https://abc123.ngrok-free.app/voice/webhook"}
```

Verify it reaches your machine before configuring Vapi:

```bash
curl https://abc123.ngrok-free.app/voice/high-risk-suppliers
```

You should see the same JSON you get from `curl http://localhost:8000/voice/high-risk-suppliers`.

Notes:

- Free-tier ngrok gives a **random subdomain that changes** every time you
  restart the tunnel. Update Vapi's `server.url` whenever the subdomain
  rotates, or pay for a static subdomain.
- Alternatives: `cloudflared tunnel --url http://localhost:8000` (free, also
  random subdomain), Tailscale Funnel, or deploy to a real host.
- If Vapi returns a timeout or 5xx, test the tunnel with `curl` first — 90% of
  the time the tunnel, not the handler, is the problem.

## Local testing

No Vapi credentials required in mock mode. Use curl to exercise the endpoints:

```bash
curl http://localhost:8000/voice/high-risk-suppliers
curl http://localhost:8000/voice/supplier/1/summary
curl http://localhost:8000/voice/pricing/recommendations
curl -X POST http://localhost:8000/voice/subscribe-alert \
  -H 'Content-Type: application/json' \
  -d '{"entity_type":"supplier","entity_id":1,"condition":"risk above 80","channel":"sms","contact":"+14151234567"}'

# Webhook — simulate a Vapi tool-call envelope
curl -X POST http://localhost:8000/voice/webhook \
  -H 'Content-Type: application/json' \
  -d '{"message":{"toolCalls":[{"id":"c1","function":{"name":"supplier_summary","arguments":"{\"supplier_id\":1}"}}]}}'
```

## Environment

```
VAPI_API_KEY=              # optional — set when calling Vapi outbound (future use)
VAPI_WEBHOOK_SECRET=       # optional — enables HMAC signature verification
VAPI_MOCK_MODE=true        # accept unsigned webhook requests (default)
```

## Tests

[apps/api/app/tests/test_voice.py](../apps/api/app/tests/test_voice.py) covers:

- Pure formatter output (spoken text shape, top-N selection, all-clear message, describe subscription)
- REST endpoints (200 + 404 + validation)
- Redis persistence on `/voice/subscribe-alert`
- Webhook envelope parsing (both shapes, JSON-string and dict args)
- HMAC signature verification (mock mode vs. production)
- Webhook dispatch to each tool + unknown-tool fallback

Run with:
```bash
cd apps/api && .venv/bin/pytest app/tests/test_voice.py -v
```
