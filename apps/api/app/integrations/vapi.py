"""Vapi webhook envelope parsing + mock-mode helper.

Vapi sends tool-calls inside a `message.toolCalls` array. This module
normalizes that into a uniform list of `(tool_call_id, name, arguments)`
tuples and formats responses into the shape Vapi expects:

    {"results": [{"toolCallId": "...", "result": "<text>"}]}

When `vapi_mock_mode` is True (the default), unsigned requests are accepted.
In production set `VAPI_WEBHOOK_SECRET` and mock_mode to False to require
header-based verification.
"""
from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings


@dataclass
class VapiToolCall:
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


def parse_tool_calls(payload: dict[str, Any]) -> list[VapiToolCall]:
    """Extract tool calls from either the top-level or nested `message` envelope."""
    message = payload.get("message", payload)
    raw_calls = message.get("toolCalls") or message.get("tool_calls") or []
    calls: list[VapiToolCall] = []
    for raw in raw_calls:
        function = raw.get("function") or {}
        name = function.get("name") or raw.get("name")
        if not name:
            continue
        raw_args = function.get("arguments") if function else raw.get("arguments")
        arguments: dict[str, Any]
        if isinstance(raw_args, str):
            try:
                arguments = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                arguments = {}
        elif isinstance(raw_args, dict):
            arguments = raw_args
        else:
            arguments = {}
        calls.append(VapiToolCall(tool_call_id=raw.get("id", ""), name=name, arguments=arguments))
    return calls


def verify_signature(signature_header: str | None, body: bytes, settings: Settings | None = None) -> bool:
    """Verify an HMAC-SHA256 signature header against the raw body.

    Mock mode (no secret configured, or `vapi_mock_mode=True`): always accept.
    """
    cfg = settings or get_settings()
    if cfg.vapi_mock_mode or not cfg.vapi_webhook_secret:
        return True
    if not signature_header:
        return False
    expected = hmac.new(cfg.vapi_webhook_secret.encode(), body, "sha256").hexdigest()
    # Accept both raw hex and `sha256=<hex>` formats.
    candidate = signature_header.split("=", 1)[1] if "=" in signature_header else signature_header
    return hmac.compare_digest(expected, candidate)


def tool_response(tool_call_id: str, result: str) -> dict[str, Any]:
    """Single tool response envelope (Vapi expects a list under `results`)."""
    return {"toolCallId": tool_call_id, "result": result}


def wrap_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {"results": results}
