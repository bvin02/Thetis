"""Create and decide recommended actions (SPEC §7.7). Nothing here ever acts on equipment."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, time

from sqlmodel import Session, select

from app import models
from app.rules.actions import ANSWER_CREATES_ROW, PlannedAction, action_text, actions_for
from app.rules.playbook import Playbook, advice_for
from app.rules.text import fmt_when
from app.services.world import TankState, World


def _key(decision: models.Decision) -> tuple[str, str, str]:
    target = decision.line_id if decision.scope == "line" else decision.tank_id
    return (decision.scope, target or "", decision.action)


def planned_for(state: TankState, world: World) -> list[PlannedAction]:
    if state.assessment is None:
        return []
    return actions_for(state.assessment, state.id, state.line_id, state.alert is not None, world.cfg)


def create_missing(session: Session, state: TankState, world: World, check_id: int | None,
                   now: datetime | None = None, is_example: bool = False,
                   decided_since: datetime | None = None) -> list[models.Decision]:
    """Create every recommended decision whose (scope, target, action) is not already pending.

    With `decided_since`, an action decided after that time also stays closed: a person already answered it for
    this evidence, so correcting an outline must not ask again.
    """
    now = now or world.now
    rows = list(session.exec(select(models.Decision)))
    pending = {_key(d) for d in rows if d.status == "pending"}
    answered = set()
    if decided_since is not None:
        answered = {_key(d) for d in rows if d.status != "pending" and d.created_at >= decided_since}
    created: list[models.Decision] = []
    for plan in planned_for(state, world):
        if plan.key in pending or plan.key in answered:
            continue
        decision = models.Decision(
            scope=plan.scope,
            tank_id=plan.tank_id,
            line_id=plan.line_id,
            check_id=check_id if plan.scope == "tank" else None,
            action=plan.action,
            status="pending",
            created_at=now,
            is_example=is_example,
        )
        session.add(decision)
        created.append(decision)
    session.flush()
    return created


def decide(session: Session, decision: models.Decision, status: str, user_name: str, note: str | None,
           now: datetime | None = None) -> models.Decision:
    """Approve or dismiss, recording who, when and an optional note."""
    decision.status = status
    decision.decided_by = user_name
    decision.decided_at = now or datetime.now()
    decision.note = (note or "").strip() or None
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


class CannotUndo(ValueError):
    """Undoing would leave a decision that makes no sense. The message is safe to show."""


def _batch_is_over(session: Session, decision: models.Decision) -> bool:
    if decision.scope != "tank":
        return False
    if decision.check_id is not None:
        check = session.get(models.Check, decision.check_id)
        batch = session.get(models.Batch, check.batch_id) if check else None
        return batch is not None and batch.status != "active"
    return session.exec(
        select(models.Batch).where(models.Batch.tank_id == decision.tank_id, models.Batch.status == "active")
    ).first() is None


def undo(session: Session, decision: models.Decision) -> models.Decision:
    if decision.status == "pending":
        return decision
    if _batch_is_over(session, decision):
        raise CannotUndo("That batch is closed, so this decision can't be reopened.")
    twin = session.exec(
        select(models.Decision).where(
            models.Decision.status == "pending", models.Decision.action == decision.action,
            models.Decision.scope == decision.scope, models.Decision.tank_id == decision.tank_id,
            models.Decision.line_id == decision.line_id,
        )
    ).first()
    if twin is not None:
        raise CannotUndo("This action is already waiting for a decision.")
    decision.status = "pending"
    decision.decided_by = None
    decision.decided_at = None
    decision.note = None
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


def decision_view(decision: models.Decision, now: datetime, book: Playbook | None = None) -> dict:
    """One decision as the screens show it. With a playbook, it also says how to carry it out in this plant."""
    text = action_text(decision.action, decision.tank_id, decision.line_id)
    decided_text = None
    if decision.decided_at is not None:
        decided_text = f"{decision.decided_by or 'Someone'} · {fmt_when(decision.decided_at, now)}"
    how, dose = advice_for(decision.action, decision.tank_id, decision.line_id, book)
    suggested_by_claude = decision.action == "claude_suggestion"
    return {
        "id": decision.id,
        "scope": decision.scope,
        "tank_id": decision.tank_id,
        "line_id": decision.line_id,
        "check_id": decision.check_id,
        "action": decision.action,
        "title": decision.note if suggested_by_claude and decision.note else text["title"],
        "cta": text["cta"],
        "done_text": text["done"],
        "status": decision.status,
        "created_at": decision.created_at.isoformat(),
        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
        "decided_by": decision.decided_by,
        "decided_text": decided_text,
        "note": None if suggested_by_claude else decision.note,
        "is_example": decision.is_example,
        "how": how,
        "dose": dose,
    }


def unanswered_view(plan: PlannedAction, book: Playbook | None) -> dict:
    """A suggestion nobody has answered yet. It has no row, so its id is None."""
    text = action_text(plan.action, plan.tank_id, plan.line_id)
    how, dose = advice_for(plan.action, plan.tank_id, plan.line_id, book)
    return {
        "id": None,
        "scope": plan.scope,
        "tank_id": plan.tank_id,
        "line_id": plan.line_id,
        "check_id": None,
        "action": plan.action,
        "title": text["title"],
        "cta": text["cta"],
        "done_text": text["done"],
        "status": "pending",
        "created_at": None,
        "decided_at": None,
        "decided_by": None,
        "decided_text": None,
        "note": None,
        "is_example": False,
        "how": how,
        "dose": dose,
    }


def latest_row(decisions: Iterable[models.Decision], plan: PlannedAction, since: datetime | None = None) -> models.Decision | None:
    """The newest decision for this action. `since` ignores answers given for an earlier batch in the same tank."""
    rows = [d for d in decisions if _key(d) == plan.key and (since is None or d.created_at >= since)]
    return max(rows, key=lambda d: (d.created_at, d.id or 0)) if rows else None


def step_view(plan: PlannedAction, decisions: Iterable[models.Decision], now: datetime, book: Playbook | None,
              since: datetime | None = None) -> dict:
    """One step on an Advisor card: its latest decision, or the unanswered suggestion."""
    row = latest_row(decisions, plan, since)
    return decision_view(row, now, book) if row is not None else unanswered_view(plan, book)


def answer_suggestion(session: Session, plan: PlannedAction, status: str, user_name: str, text: str | None,
                      now: datetime | None = None, since: datetime | None = None) -> models.Decision:
    """A person answered a suggestion that has no row yet. Answering twice returns the first answer."""
    if plan.action not in ANSWER_CREATES_ROW:
        raise ValueError(f"{plan.action} isn't a suggestion")
    rows = session.exec(select(models.Decision).where(models.Decision.action == plan.action))
    for row in rows:
        same_target = _key(row) == plan.key
        same_text = plan.action != "claude_suggestion" or row.note == text
        same_batch = since is None or row.created_at >= since
        if same_target and same_text and same_batch:
            return row
    now = now or datetime.now()
    decision = models.Decision(
        scope=plan.scope, tank_id=plan.tank_id, line_id=plan.line_id, action=plan.action, status=status, created_at=now,
        decided_at=now, decided_by=user_name, note=text,
    )
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


def forget_answer(session: Session, decision: models.Decision) -> None:
    """Undo on a suggestion takes it back to being only a suggestion, not to the waiting list. An answer given for a batch
    that has since ended is part of the record, and stays."""
    batch = session.exec(
        select(models.Batch).where(models.Batch.tank_id == decision.tank_id, models.Batch.status == "active")
    ).first()
    if batch is None or decision.created_at < datetime.combine(batch.spawn_date, time.min):
        raise CannotUndo("That batch is closed, so this decision can't be reopened.")
    session.delete(decision)
    session.commit()


def all_decisions(session: Session) -> list[models.Decision]:
    return list(session.exec(select(models.Decision).order_by(models.Decision.created_at, models.Decision.id)))


def pending_count(decisions: Iterable[models.Decision]) -> int:
    """Line-scoped decisions count once, because they are one row."""
    return sum(1 for d in decisions if d.status == "pending")


def touches_tank(decision: models.Decision, state: TankState) -> bool:
    if decision.scope == "line":
        return decision.line_id is not None and decision.line_id == state.line_id
    return decision.tank_id == state.id


def actions_for_tank(state: TankState, world: World, decisions: Iterable[models.Decision]) -> list[models.Decision]:
    """The inspector's Recommended actions: for each action the current pattern recommends, its latest
    decision (pending or already decided), followed by anything else still pending for this tank."""
    mine = [d for d in decisions if touches_tank(d, state)]
    latest: dict[tuple[str, str, str], models.Decision] = {}
    for decision in sorted(mine, key=lambda d: (d.created_at, d.id or 0)):
        latest[_key(decision)] = decision

    shown: list[models.Decision] = []
    seen: set[tuple[str, str, str]] = set()
    for plan in planned_for(state, world):
        decision = latest.get(plan.key)
        if decision is not None:
            shown.append(decision)
            seen.add(plan.key)
    for key, decision in latest.items():
        if key not in seen and decision.status == "pending":
            shown.append(decision)
    return shown
