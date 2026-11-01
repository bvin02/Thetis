"""Tanks and batches."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import models
from app.db import get_session
from app.services.views import build_tank, build_tanks_list

router = APIRouter(prefix="/api", tags=["tanks"])


@router.get("/tanks")
def list_tanks(session: Session = Depends(get_session)) -> dict:
    return build_tanks_list(session)


@router.get("/tanks/{tank_id}")
def get_tank(tank_id: str, session: Session = Depends(get_session)) -> dict:
    view = build_tank(tank_id, session)
    if view is None:
        raise HTTPException(404, f"No tank called {tank_id}")
    return view


class StartBatch(BaseModel):
    tank_id: str
    code: str = Field(min_length=1, max_length=40)
    spawn_date: date
    stocked: int = Field(gt=0)


class CloseBatch(BaseModel):
    outcome: Literal["moved_to_setting", "harvested", "crashed", "discarded"]
    closed_on: date | None = None
    note: str | None = None


@router.post("/batches", status_code=201)
def start_batch(body: StartBatch, session: Session = Depends(get_session)) -> dict:
    tank = session.get(models.Tank, body.tank_id)
    if tank is None:
        raise HTTPException(404, f"No tank called {body.tank_id}")
    running = session.exec(
        select(models.Batch).where(models.Batch.tank_id == tank.id, models.Batch.status == "active")
    ).first()
    if running is not None:
        raise HTTPException(409, f"{tank.id} already has batch {running.code}. Close it first.")
    if body.spawn_date > date.today():
        raise HTTPException(422, "Spawn date can't be in the future.")
    batch = models.Batch(code=body.code.strip(), tank_id=tank.id, spawn_date=body.spawn_date, stocked=body.stocked)
    tank.status = "active"
    session.add(batch)
    session.add(tank)
    session.commit()
    session.refresh(batch)
    return {"id": batch.id, "code": batch.code, "tank_id": batch.tank_id}


@router.post("/batches/{batch_id}/close")
def close_batch(batch_id: int, body: CloseBatch, session: Session = Depends(get_session)) -> dict:
    batch = session.get(models.Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "No such batch")
    if batch.status != "active":
        raise HTTPException(409, f"Batch {batch.code} is already closed.")
    closed_on = body.closed_on or date.today()
    if closed_on < batch.spawn_date:
        raise HTTPException(422, "A batch can't close before it was spawned.")
    batch.status = "closed"
    batch.outcome = body.outcome
    batch.closed_on = closed_on
    batch.note = (body.note or "").strip() or None
    tank = session.get(models.Tank, batch.tank_id)
    if tank is not None:
        tank.status = "empty"
        session.add(tank)
    session.add(batch)

    # A tank's open decisions end with its batch. Line decisions still apply to the other tanks.
    hatchery = session.get(models.Hatchery, 1)
    who = hatchery.user_name if hatchery else "Someone"
    open_rows = session.exec(
        select(models.Decision).where(
            models.Decision.scope == "tank", models.Decision.tank_id == batch.tank_id, models.Decision.status == "pending"
        )
    )
    for decision in open_rows:
        decision.status = "dismissed"
        decision.decided_by = who
        decision.decided_at = datetime.now()
        decision.note = f"Batch {batch.code} closed."
        session.add(decision)
    session.commit()
    return {"id": batch.id, "status": batch.status, "outcome": batch.outcome}
