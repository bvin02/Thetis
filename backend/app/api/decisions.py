"""List and decide recommended actions. A person decides; nothing acts on equipment."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app import models
from app.db import get_session
from app.rules.actions import ANSWER_CREATES_ROW, line_number
from app.rules.assess import LEVEL_LABEL
from app.rules.text import title_for
from app.services import decisions as service
from app.services.advisor import playbook_for
from app.services.world import load_world

router = APIRouter(prefix="/api", tags=["decisions"])


class DecisionNote(BaseModel):
    note: str | None = None


def _load(decision_id: int, session: Session) -> models.Decision:
    decision = session.get(models.Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "No such decision")
    return decision


def _user_name(session: Session) -> str:
    hatchery = session.get(models.Hatchery, 1)
    return hatchery.user_name if hatchery else "Someone"


@router.get("/decisions")
def list_decisions(
    status: Literal["pending", "decided", "all"] = Query(default="all"),
    session: Session = Depends(get_session),
) -> dict:
    """Decisions grouped by target, worst target first. Counts are always for every status."""
    world = load_world(session)
    book = playbook_for(world)
    rows = service.all_decisions(session)
    n_pending = sum(1 for d in rows if d.status == "pending")
    n_decided = len(rows) - n_pending

    def wanted(decision: models.Decision) -> bool:
        if status == "pending":
            return decision.status == "pending"
        if status == "decided":
            return decision.status != "pending"
        return True

    groups: dict[str, dict] = {}
    for decision in rows:
        if not wanted(decision):
            continue
        if decision.scope == "line":
            key = f"line:{decision.line_id}"
            alert = world.alerts.get(decision.line_id or "")
            group = groups.setdefault(key, {
                "key": key, "kind": "line", "line_id": decision.line_id, "tank_id": None,
                "title": f"Line {line_number(decision.line_id)}",
                "level": "risk" if alert else "ok",
                "level_label": None,
                "subtitle": "corrosive water" if alert else "water",
                "items": [], "rank": 3 if alert else 1,
            })
        else:
            key = f"tank:{decision.tank_id}"
            state = world.tanks.get(decision.tank_id or "")
            level = state.level if state else "empty"
            subtitle = ""
            if state is not None and state.assessment is not None:
                subtitle = title_for(state.assessment)
            elif state is not None:
                subtitle = "Empty"
            group = groups.setdefault(key, {
                "key": key, "kind": "tank", "line_id": None, "tank_id": decision.tank_id,
                "title": decision.tank_id, "level": level, "level_label": LEVEL_LABEL.get(level, "Normal"),
                "subtitle": subtitle, "items": [],
                "rank": {"critical": 4, "risk": 3, "watch": 2, "ok": 1, "empty": 0}.get(level, 0),
            })
        group["items"].append(service.decision_view(decision, world.now, book))

    ordered = sorted(groups.values(), key=lambda g: (-g["rank"], g["title"] or ""))
    for group in ordered:
        group.pop("rank", None)
        group["items"].sort(key=lambda item: (item["status"] != "pending", item["decided_at"] or item["created_at"]))
    return {"groups": ordered, "counts": {"pending": n_pending, "decided": n_decided, "all": len(rows)}}


@router.post("/decisions/{decision_id}/approve")
def approve(decision_id: int, body: DecisionNote | None = None, session: Session = Depends(get_session)) -> dict:
    decision = service.decide(session, _load(decision_id, session), "approved", _user_name(session),
                              body.note if body else None)
    return service.decision_view(decision, datetime.now())


@router.post("/decisions/{decision_id}/dismiss")
def dismiss(decision_id: int, body: DecisionNote | None = None, session: Session = Depends(get_session)) -> dict:
    decision = service.decide(session, _load(decision_id, session), "dismissed", _user_name(session),
                              body.note if body else None)
    return service.decision_view(decision, datetime.now())


@router.post("/decisions/{decision_id}/undo")
def undo(decision_id: int, session: Session = Depends(get_session)) -> dict:
    row = _load(decision_id, session)
    if row.action in ANSWER_CREATES_ROW:
        view = service.decision_view(row, datetime.now()) | {"id": None, "status": "pending", "decided_at": None, "decided_by": None,
                                                              "decided_text": None}
        try:
            service.forget_answer(session, row)
        except service.CannotUndo as error:
            raise HTTPException(409, str(error)) from None
        return view
    try:
        decision = service.undo(session, row)
    except service.CannotUndo as error:
        raise HTTPException(409, str(error)) from None
    return service.decision_view(decision, datetime.now())
