from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from sqlmodel import Session
from app.models.entities import AgentRun, AuditLog


class GovernanceRecorder:
    """Local Guild.ai-ready governance recorder.

    TODO: forward these lifecycle events to Guild.ai once the production run
    tracking API and credentials are finalized.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_agent_run_start(self, run_type: str, entity_type: str, entity_id: int, metadata: dict[str, Any] | None = None) -> AgentRun:
        run = AgentRun(run_type=run_type, entity_type=entity_type, entity_id=entity_id, run_metadata=metadata or {})
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        self.record_agent_step(run.id, "run_started", f"Started {run_type}", metadata or {})
        return run

    def record_agent_step(self, agent_run_id: int | None, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self.session.add(
            AuditLog(agent_run_id=agent_run_id, event_type=event_type, message=message, payload=payload or {})
        )
        self.session.commit()

    def record_tool_use(self, agent_run_id: int | None, tool_name: str, payload: dict[str, Any] | None = None) -> None:
        self.record_agent_step(agent_run_id, "tool_use", f"Used {tool_name}", payload or {})

    def record_agent_run_end(self, agent_run_id: int, status: str, summary: str | None = None) -> None:
        run = self.session.get(AgentRun, agent_run_id)
        if not run:
            return
        run.status = status
        run.summary = summary
        run.ended_at = datetime.now(timezone.utc)
        self.session.add(run)
        self.session.commit()
        self.record_agent_step(agent_run_id, "run_ended", f"Ended with status {status}", {"summary": summary})
