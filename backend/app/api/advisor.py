"""The Advisor: crash risks, yield suggestions, the plant's chemicals, and the two live Claude features (SPEC §16)."""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from app import config, models
from app.db import get_session
from app.rules.actions import ANSWER_CREATES_ROW, PlannedAction
from app.rules.text import fmt_when
from app.services import advisor as service
from app.services import claude
from app.services.decisions import all_decisions, answer_suggestion, decision_view
from app.services.world import load_world

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


def _sse(states: Iterable[dict | None]) -> Iterator[str]:
    """Server-sent events. A comment line keeps the connection open while Claude thinks."""
    for state in states:
        yield ": keep-alive\n\n" if state is None else f"data: {json.dumps(state, ensure_ascii=False)}\n\n"


def _stream(states: Iterable[dict | None]) -> StreamingResponse:
    return StreamingResponse(_sse(states), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _analysis_view(session: Session, snapshot: dict) -> dict:
    """The stored analysis for the page, with its suggestions' current answers."""
    world = load_world(session)
    row, fresh = claude.stored_analysis(session, service.analysis_key(snapshot))
    if row is None or not row.result:
        return {"analysis": None, "analysis_fresh": False}
    book = service.playbook_for(world)
    result = service.with_decisions(row.result, world, all_decisions(session), book)
    return {"analysis": {**result, "model": row.model, "when_text": fmt_when(row.created_at, world.now)}, "analysis_fresh": fresh}


@router.get("")
def get_advisor(session: Session = Depends(get_session)) -> dict:
    page = service.build_advisor(session)
    status = claude.status(session)
    running = claude.running_job()
    snapshot = service.build_snapshot(session)
    return page | _analysis_view(session, snapshot) | {
        "claude": status,
        "analysis_running": running is not None,
        "reading_text": service.reading_text(snapshot),
    }


class PlantBody(BaseModel):
    buffer: str | None = None
    disinfectant: str | None = None


@router.post("/plant")
def set_plant(body: PlantBody, session: Session = Depends(get_session)) -> dict:
    try:
        return service.set_plant(session, body.buffer, body.disinfectant)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


class AnswerBody(BaseModel):
    action: Literal["move_to_setting", "split_tank", "review_handling", "claude_suggestion"]
    tank_id: str
    verb: Literal["approve", "dismiss"]
    text: str | None = None


@router.post("/answer")
def answer(body: AnswerBody, session: Session = Depends(get_session)) -> dict:
    """A person answered a suggestion that has no decision row yet."""
    if body.action not in ANSWER_CREATES_ROW:
        raise HTTPException(422, "That isn't a suggestion.")
    if session.get(models.Tank, body.tank_id) is None:
        raise HTTPException(404, f"No tank called {body.tank_id}")
    text = (body.text or "").strip() or None
    if body.action == "claude_suggestion" and text is None:
        raise HTTPException(422, "A suggestion needs its text.")
    hatchery = session.get(models.Hatchery, 1)
    who = hatchery.user_name if hatchery else "Someone"
    plan = PlannedAction("tank", body.action, body.tank_id, None)
    status = "approved" if body.verb == "approve" else "dismissed"
    note = text if body.action == "claude_suggestion" else None
    world = load_world(session)
    row = answer_suggestion(session, plan, status, who, note, since=service.batch_start(body.tank_id, world))
    return decision_view(row, world.now, service.playbook_for(world))


class AnalyzeBody(BaseModel):
    force: bool = False


@router.post("/analyze")
def analyze(body: AnalyzeBody | None = None, session: Session = Depends(get_session)) -> StreamingResponse:
    """Start or join an analysis and stream its progress. The result is stored whether or not anyone is still watching."""
    snapshot = service.build_snapshot(session)
    try:
        job = claude.start_analysis(session, service.analysis_key(snapshot), snapshot, service.verify_analysis, bool(body and body.force))
    except claude.ClaudeOff as error:
        raise HTTPException(503, str(error)) from None
    except claude.OverDailyLimit as error:
        raise HTTPException(429, str(error)) from None
    return _stream(job.follow())


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskBody(BaseModel):
    messages: list[ChatMessage]


@router.post("/ask")
def ask(body: AskBody, session: Session = Depends(get_session)) -> StreamingResponse:
    if not claude.is_enabled():
        raise HTTPException(503, "Claude isn't set up on this computer.")
    if not body.messages or body.messages[-1].role != "user" or not body.messages[-1].content.strip():
        raise HTTPException(422, "Ask a question first.")
    if len(body.messages) > config.CLAUDE_ASK_MAX_TURNS:
        raise HTTPException(422, "This conversation is long. Start a new one.")
    too_long = len(body.messages[-1].content) > config.CLAUDE_ASK_MAX_CHARS
    if too_long or any(len(m.content) > config.CLAUDE_ASK_MAX_CHARS * 4 for m in body.messages):
        raise HTTPException(422, "That message is too long.")
    snapshot = service.build_snapshot(session)
    messages = [{"role": m.role, "content": m.content.strip()} for m in body.messages if m.content.strip()]
    return _stream(claude.stream_answer(snapshot, messages))
