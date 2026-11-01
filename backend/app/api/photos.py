"""The Photo library's tree: rooms → tanks → checks (SPEC §4.6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import models
from app.db import get_session
from app.rules.text import fmt_count, fmt_day_month, fmt_len, fmt_pct, fmt_when, round_half_up
from app.services.views import photo_url
from app.services.world import TankState, World, load_world

router = APIRouter(prefix="/api", tags=["photos"])


def _tank_note(state: TankState, world: World) -> str:
    """The short note beside a tank: "Day 9 · 24% dead", "Day 6 · Ω 1.4", "Day 14 · 231 µm"."""
    if not state.active:
        return "Empty" if state.tank.status != "cleaning" else "Cleaning"
    day = state.day(world.now)
    latest = state.latest
    if latest is None:
        return f"Day {day}"
    pattern = state.assessment.pattern if state.assessment else None
    if pattern == "bacterial" or (latest.pct_dead or 0) >= world.cfg["dead_pct"][0]:
        return f"Day {day} · {fmt_pct(latest.pct_dead)} dead"
    if pattern == "corrosive_early" and state.alert is not None:
        return f"Day {day} · line {(state.line_id or '').lstrip('L')}"
    if pattern in ("corrosive", "corrosive_early") and latest.omega_arag is not None:
        return f"Day {day} · Ω {latest.omega_arag:.1f}"
    if pattern == "splitting":
        return f"Day {day} · size spread"
    if pattern == "underfed":
        return f"Day {day} · slow growth"
    return f"Day {day} · {fmt_len(latest.mean_len_um)}"


def _check_summary(check: models.Check) -> str:
    parts = []
    if check.pct_dead is not None:
        parts.append(f"{round_half_up(check.pct_dead)}% dead")
    if check.mean_len_um is not None:
        parts.append(fmt_len(check.mean_len_um))
    return " · ".join(parts) or "No counts"


@router.get("/photos/tree")
def photo_tree(session: Session = Depends(get_session)) -> dict:
    world = load_world(session)
    first_photo: dict[int, models.Photo] = {}
    photo_count: dict[int, int] = {}
    for photo in session.exec(select(models.Photo).order_by(models.Photo.id)):
        first_photo.setdefault(photo.check_id, photo)
        photo_count[photo.check_id] = photo_count.get(photo.check_id, 0) + 1

    checks_by_tank: dict[str, list[models.Check]] = {}
    for check in session.exec(select(models.Check).order_by(models.Check.sampled_at.desc(), models.Check.id.desc())):
        checks_by_tank.setdefault(check.tank_id, []).append(check)
    batches = {b.id: b for b in session.exec(select(models.Batch))}

    rooms = []
    for room in world.rooms.values():
        tanks = []
        for state in world.tanks.values():
            if state.tank.room_id != room.id:
                continue
            rows = checks_by_tank.get(state.id, [])
            checks = []
            for check in rows:
                photo = first_photo.get(check.id)
                checks.append({
                    "id": check.id,
                    "when_text": fmt_when(check.sampled_at, world.now),
                    "summary": _check_summary(check),
                    "level": check.level or "ok",
                    "thumb_url": photo_url(photo) if photo else None,
                    "n_photos": photo_count.get(check.id, 0),
                    "batch_code": batches[check.batch_id].code if check.batch_id in batches else None,
                })
            batch = state.batch
            footer = None
            if batch is not None:
                footer = f"Spawned {fmt_day_month(batch.spawn_date)} · stocked {fmt_count(batch.stocked)} larvae"
            tanks.append({
                "id": state.id,
                "level": state.level,
                "note": _tank_note(state, world),
                "n_photos": sum(photo_count.get(c.id, 0) for c in rows),
                "n_checks": len(rows),
                "footer": footer,
                "checks": checks,
            })
        if tanks:
            rooms.append({
                "id": room.id,
                "name": room.name,
                "n_photos": sum(t["n_photos"] for t in tanks),
                "tanks": tanks,
            })
    return {"rooms": rooms}
