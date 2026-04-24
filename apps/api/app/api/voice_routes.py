from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.db.session import get_session
from app.integrations.redis_context import RedisContext
from app.integrations.vapi import (
    parse_tool_calls,
    tool_response,
    verify_signature,
    wrap_results,
)
from app.services.voice import (
    describe_subscription,
    high_risk_suppliers,
    pricing_recommendations,
    supplier_summary,
)

router = APIRouter(prefix="/voice", tags=["voice"])

VOICE_SUBSCRIPTIONS_KEY = "voice:subscriptions"
VOICE_SUBSCRIPTIONS_CAP = 200


class VoiceResponse(BaseModel):
    spoken: str
    data: dict[str, Any] | None = None


class SubscribeAlertRequest(BaseModel):
    entity_type: str = Field(pattern="^(supplier|product|any)$")
    entity_id: int | None = None
    condition: str = Field(min_length=3, max_length=120)
    channel: str = Field(default="voice", pattern="^(voice|sms|email)$")
    contact: str = Field(min_length=3, max_length=120)


class SubscribeAlertResponse(VoiceResponse):
    subscription_id: str


def _redis() -> RedisContext:
    return RedisContext()


@router.get("/high-risk-suppliers", response_model=VoiceResponse)
def voice_high_risk_suppliers(session: Session = Depends(get_session)) -> VoiceResponse:
    result = high_risk_suppliers(session)
    return VoiceResponse(spoken=result["spoken"], data={"count": result["count"], "suppliers": result["suppliers"]})


@router.get("/supplier/{supplier_id}/summary", response_model=VoiceResponse)
def voice_supplier_summary(supplier_id: int, session: Session = Depends(get_session)) -> VoiceResponse:
    result = supplier_summary(session, supplier_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
    return VoiceResponse(spoken=result["spoken"], data={k: v for k, v in result.items() if k != "spoken"})


@router.get("/pricing/recommendations", response_model=VoiceResponse)
def voice_pricing_recommendations(session: Session = Depends(get_session)) -> VoiceResponse:
    result = pricing_recommendations(session)
    return VoiceResponse(spoken=result["spoken"], data={"count": result["count"], "recommendations": result["recommendations"]})


@router.post("/subscribe-alert", response_model=SubscribeAlertResponse, status_code=status.HTTP_201_CREATED)
def voice_subscribe_alert(
    payload: SubscribeAlertRequest,
    ctx: RedisContext = Depends(_redis),
) -> SubscribeAlertResponse:
    entry = {
        **payload.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entry["subscription_id"] = f"sub_{abs(hash(json.dumps(entry, sort_keys=True)))}"
    ctx.memory._push(VOICE_SUBSCRIPTIONS_KEY, entry, VOICE_SUBSCRIPTIONS_CAP)
    return SubscribeAlertResponse(
        spoken=describe_subscription(entry),
        data=entry,
        subscription_id=entry["subscription_id"],
    )


# Internal dispatch table — shared between REST endpoints and webhook handler.
def _dispatch(name: str, arguments: dict[str, Any], session: Session, ctx: RedisContext) -> str:
    if name == "high_risk_suppliers":
        return high_risk_suppliers(session)["spoken"]
    if name == "supplier_summary":
        sid = arguments.get("supplier_id")
        if not isinstance(sid, int):
            return "Missing or invalid supplier_id argument."
        result = supplier_summary(session, sid)
        return result["spoken"] if result else f"Supplier {sid} not found."
    if name == "pricing_recommendations":
        return pricing_recommendations(session)["spoken"]
    if name == "subscribe_alert":
        try:
            subscription = SubscribeAlertRequest(**arguments).model_dump()
        except Exception as exc:
            return f"Could not subscribe: {exc}"
        subscription["created_at"] = datetime.now(timezone.utc).isoformat()
        ctx.memory._push(VOICE_SUBSCRIPTIONS_KEY, subscription, VOICE_SUBSCRIPTIONS_CAP)
        return describe_subscription(subscription)
    return f"Unknown tool: {name}."


@router.post("/webhook")
async def voice_webhook(
    request: Request,
    x_vapi_signature: str | None = Header(default=None, alias="X-Vapi-Signature"),
    session: Session = Depends(get_session),
    ctx: RedisContext = Depends(_redis),
) -> dict[str, Any]:
    body = await request.body()
    if not verify_signature(x_vapi_signature, body):
        raise HTTPException(status_code=401, detail="Invalid Vapi signature")
    payload = json.loads(body) if body else {}
    calls = parse_tool_calls(payload)
    if not calls:
        return wrap_results([])
    results = []
    for call in calls:
        spoken = _dispatch(call.name, call.arguments, session, ctx)
        results.append(tool_response(call.tool_call_id, spoken))
    return wrap_results(results)
