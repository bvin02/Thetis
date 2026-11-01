"""Build the JSON the screens read, from loaded state and the rules' texts."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, time

from sqlmodel import Session, select

from app import models
from app.rules.actions import line_number
from app.rules.assess import LEVEL_LABEL, LEVEL_RANK
from app.rules.history import BatchHistory, history_days, tank_history
from app.rules.series import day_of
from app.rules.text import (
    FORECAST,
    TankBrief,
    chip_for,
    condition_rows,
    empty_reason,
    empty_title,
    fmt_count,
    fmt_len,
    fmt_pct,
    fmt_since,
    fmt_survival,
    fmt_time,
    fmt_when,
    headline_for,
    next_check_text,
    reason_for,
    round_half_up,
    summary_for,
    title_for,
)
from app.services.decisions import actions_for_tank, all_decisions, decision_view, pending_count, touches_tank
from app.services.world import TankState, World, load_world

# ---------------------------------------------------------------- tanks


def _stage_text(state: TankState) -> str | None:
    if state.kind == "setting":
        return "Setting"
    for check in reversed(state.checks):
        if check.stage:
            return check.stage
    return None


def _line_text(state: TankState) -> str:
    if state.line is None:
        return "No line"
    return f"{state.line.name} · corrosive" if state.alert else state.line.name


def _empty_sub(state: TankState) -> str:
    return "Cleaning" if state.tank.status == "cleaning" else "Empty"


def tank_summary(state: TankState, world: World) -> dict:
    """One tank as the Floor, the plan, the table and the tooltips show it."""
    tank = state.tank
    base = {
        "id": tank.id,
        "shape": tank.shape,
        "geom": tank.geom,
        "room_id": tank.room_id,
        "room_name": state.room.name,
        "room_kind": state.kind,
        "line_id": tank.line_id,
        "line_name": state.line.name if state.line else None,
        "line_text": _line_text(state),
        "line_alert": state.alert is not None,
        "status": tank.status,
        "volume_l": tank.volume_l,
        "level": state.level,
        "level_label": LEVEL_LABEL[state.level],
    }
    if not state.active:
        return base | {
            "pattern": None, "title": empty_title(state.kind), "chip": "", "reason": empty_reason(tank.status),
            "batch_id": None, "batch_code": None, "day": None, "stage": None, "sub_text": _empty_sub(state),
            "age_text": _empty_sub(state), "live_est": None, "live_text": "—", "survival": None, "survival_text": "—",
            "last_check_at": None, "last_check_text": "—", "latest_check_id": None, "forecast": FORECAST["empty"],
        }
    a = state.assessment
    latest = state.latest
    day = state.day(world.now)
    stage = _stage_text(state)
    return base | {
        "pattern": a.pattern,
        "title": title_for(a),
        "chip": chip_for(a.pattern, tank.line_id, state.alert is not None),
        "reason": reason_for(a, tank.line_id, state.alert is not None, len(state.checks), world.cfg),
        "batch_id": state.batch.id,
        "batch_code": state.batch.code,
        "day": day,
        "stage": stage,
        "sub_text": f"Day {day}",
        "age_text": f"Day {day} · {stage}" if stage else f"Day {day}",
        "live_est": latest.live_est if latest else None,
        "live_text": fmt_count(latest.live_est if latest else None),
        "survival": a.survival,
        "survival_text": fmt_survival(a.survival),
        "last_check_at": latest.sampled_at.isoformat() if latest else None,
        "last_check_text": fmt_when(latest.sampled_at if latest else None, world.now),
        "latest_check_id": latest.id if latest else None,
        "forecast": FORECAST[state.level],
    }


def _chip(state: TankState, world: World) -> dict:
    summary = tank_summary(state, world)
    return {k: summary[k] for k in ("id", "level", "level_label", "chip", "reason")}


# ---------------------------------------------------------------- lines


def line_water(line_id: str | None, world: World, session: Session) -> dict | None:
    """The newest reading of each water value on a line. Used by the line cards and "Use these"."""
    if line_id is None or line_id not in world.lines:
        return None
    tank_ids = [s.id for s in world.tanks.values() if s.line_id == line_id]
    if not tank_ids:
        return None
    rows = session.exec(
        select(models.Check).where(models.Check.tank_id.in_(tank_ids)).order_by(models.Check.sampled_at.desc())
    )
    values: dict[str, float | None] = dict.fromkeys(("temp_c", "salinity_ppt", "ph", "omega_arag", "do_mgl"))
    newest = None
    for check in rows:
        for key in values:
            reading = getattr(check, key)
            if values[key] is None and reading is not None:
                values[key] = reading
                newest = newest or check.sampled_at
        if all(v is not None for v in values.values()):
            break
    if newest is None:
        return None
    return values | {
        "at": newest.isoformat(),
        "when_text": f"{fmt_since(newest, world.now)} {fmt_time(newest)}",
    }


def _line_view(line: models.Line, world: World, session: Session) -> dict:
    water = line_water(line.id, world, session)
    alert = world.alerts.get(line.id)
    omega = water["omega_arag"] if water else None
    ph = water["ph"] if water else None
    parts = []
    if omega is not None:
        parts.append(f"Ω {omega:.1f}")
    if ph is not None:
        parts.append(f"pH {ph:.2f}")
    return {
        "id": line.id,
        "name": line.name,
        "number": line_number(line.id),
        "card_xy": line.card_xy,
        "omega": omega,
        "ph": ph,
        "reading_text": " · ".join(parts) or "No readings",
        "water": water,
        "alert": alert is not None,
        "since_text": fmt_since(alert.since, world.now) if alert else None,
        "tank_ids": [s.id for s in world.tanks.values() if s.line_id == line.id],
    }


# ---------------------------------------------------------------- floor


def _urgent_label(critical: int, risk: int) -> str:
    return f"{critical} critical · {risk} at risk"


def _rank(level: str) -> int:
    return LEVEL_RANK.get(level, 0)


def build_shell(world: World, decisions: Iterable[models.Decision]) -> dict:
    """What every screen's sidebar and header need."""
    hatchery = world.hatchery
    rooms = []
    for room in world.rooms.values():
        tanks = [s for s in world.tanks.values() if s.tank.room_id == room.id]
        if not tanks:
            continue
        worst = max((s.level for s in tanks), key=_rank)
        rooms.append({
            "id": room.id, "name": room.name, "kind": room.kind, "caption": room.caption, "label_xy": room.label_xy,
            "tank_count": len(tanks), "worst_level": "ok" if worst == "empty" else worst,
        })
    return {
        "seeded": hatchery is not None,
        "hatchery": {"name": hatchery.name if hatchery else "Thetis", "species": hatchery.species if hatchery else None},
        "user": {
            "name": hatchery.user_name if hatchery else "",
            "initials": hatchery.user_initials if hatchery else "",
            "role": hatchery.user_role if hatchery else "",
        },
        "is_example": world.is_example,
        "rooms": rooms,
        "decisions_waiting": pending_count(decisions),
        "settings": {"bucket_l": world.cfg["bucket_l"], "concentration": world.cfg["concentration"]},
    }


def _next_check(world: World) -> dict | None:
    candidates = []
    for state in world.tanks.values():
        if not state.active:
            continue
        last = state.latest.sampled_at if state.latest else None
        if last is None:
            last = datetime.combine(state.batch.spawn_date, time(world.cfg["spawn_hour"]))
        candidates.append((last, state.id))
    if not candidates:
        return None
    last, tank_id = min(candidates)
    text, overdue = next_check_text(last, world.cfg["check_interval_h"], world.now)
    return {"tank_id": tank_id, "text": text, "overdue": overdue}


def build_floor(session: Session) -> dict:
    world = load_world(session)
    decisions = all_decisions(session)
    states = list(world.tanks.values())
    briefs = [TankBrief(s.id, s.level, s.assessment.pattern if s.assessment else None, s.line_id, s.active) for s in states]

    act_now = sorted((s for s in states if s.level in ("critical", "risk")), key=lambda s: (-_rank(s.level), s.id))
    monitor = sorted((s for s in states if s.level == "watch"), key=lambda s: s.id)
    critical = sum(1 for s in states if s.level == "critical")
    risk = sum(1 for s in states if s.level == "risk")

    active = [s for s in states if s.active]
    with_estimate = [s for s in active if s.latest is not None and s.latest.live_est is not None]
    total = sum(s.latest.live_est for s in with_estimate)
    with_survival = [s.assessment.survival for s in active if s.assessment and s.assessment.survival is not None]
    average = sum(with_survival) / len(with_survival) if with_survival else None

    worst = max(states, key=lambda s: (_rank(s.level), -states.index(s))) if states else None

    rows = []
    for state in states:
        batches = [
            BatchHistory(
                spawn_date=b.spawn_date, closed_on=b.closed_on,
                checks=[(c.sampled_at, c.level or "ok") for c in world.checks_by_batch.get(b.id, [])],
            )
            for b in state.all_batches
        ]
        cells = tank_history(batches, world.now.date())
        rows.append({"tank_id": state.id, "level": state.level, "cells": cells})

    return build_shell(world, decisions) | {
        "now": world.now.isoformat(),
        "headline": headline_for(briefs),
        "summary": summary_for(briefs, world.alerts, world.now),
        "act_now": [_chip(s, world) for s in act_now],
        "act_label": _urgent_label(critical, risk),
        "monitor": [_chip(s, world) for s in monitor],
        "monitor_label": f"{len(monitor)} on watch",
        "metrics": {
            "larvae_total": total,
            "larvae_value": f"{total / 1e6:.1f}" if total else "0",
            "larvae_unit": "M" if total else "",
            "tanks_running": len(active),
            "tanks_total": len(states),
            "avg_survival": round_half_up(average * 100) if average is not None else None,
            "decisions_waiting": pending_count(decisions),
            "next_check": _next_check(world),
        },
        "tanks": [tank_summary(s, world) for s in states],
        "lines": [_line_view(line, world, session) for line in world.lines.values()],
        "history": {"days": history_days(world.now.date()), "rows": rows},
        "default_tank": worst.id if worst else None,
    }


# ---------------------------------------------------------------- photos and checks


def detection_view(det: models.Detection) -> dict:
    return {
        "id": det.number,
        "cx": det.cx,
        "cy": det.cy,
        "contour": det.contour,
        "length_px": det.length_px,
        "length_um": det.length_um,
        "area_px": det.area_px,
        "solidity": det.solidity,
        "defect": det.defect,
        "hollowness": det.hollowness,
        "gut": det.gut,
        "interior": det.interior,
        "cls": det.larva_cls,
        "auto_cls": det.auto_cls,
        "unsure": det.unsure,
        "unsure_reason": det.unsure_reason,
        "clump_n": det.clump_n,
        "touches_edge": det.touches_edge,
        "source": det.source,
        "claude": det.claude,
    }


def photo_url(photo: models.Photo) -> str:
    return f"/api/files/{photo.path}"


def photo_view(photo: models.Photo, session: Session, with_detections: bool = True) -> dict:
    view = {
        "id": photo.id,
        "check_id": photo.check_id,
        "url": photo_url(photo),
        "width": photo.width,
        "height": photo.height,
        "um_per_px": photo.um_per_px,
        "calibration": photo.calibration,
        "grid_spacing_px": photo.grid_spacing_px,
        "volume_ml": photo.volume_ml,
        "engine_version": photo.engine_version,
        "synthetic": photo.synthetic,
        "source_name": photo.source_name,
    }
    if with_detections:
        rows = session.exec(
            select(models.Detection).where(models.Detection.photo_id == photo.id).order_by(models.Detection.number)
        )
        view["detections"] = [detection_view(d) for d in rows]
    return view


def photos_of_check(check_id: int, session: Session) -> list[models.Photo]:
    return list(session.exec(select(models.Photo).where(models.Photo.check_id == check_id).order_by(models.Photo.id)))


def _signal_severities(check: models.Check) -> dict[str, str]:
    return {s["key"]: s["severity"] for s in (check.signals or [])}


def check_row(check: models.Check, batch: models.Batch | None, world: World, n_photos: int) -> dict:
    """One row of a checks table."""
    spawn = batch.spawn_date if batch else check.sampled_at.date()
    survival = check.survival
    return {
        "id": check.id,
        "tank_id": check.tank_id,
        "batch_id": check.batch_id,
        "batch_code": batch.code if batch else None,
        "sampled_at": check.sampled_at.isoformat(),
        "when_text": fmt_when(check.sampled_at, world.now),
        "day": day_of(check.sampled_at, spawn),
        "source": check.source,
        "n_live": check.n_live,
        "n_abnormal": check.n_abnormal,
        "n_dead": check.n_dead,
        "n_counted": check.n_live + check.n_abnormal + check.n_dead,
        "live_est": check.live_est,
        "live_text": fmt_count(check.live_est),
        "survival": survival,
        "survival_text": fmt_survival(survival),
        "mean_len_um": check.mean_len_um,
        "length_text": fmt_len(check.mean_len_um),
        "growth_um_day": check.growth_um_day,
        "growth_text": f"{check.growth_um_day:.1f}" if check.growth_um_day is not None else "—",
        "pct_dead": check.pct_dead,
        "dead_text": fmt_pct(check.pct_dead),
        "pct_abnormal": check.pct_abnormal,
        "abnormal_text": fmt_pct(check.pct_abnormal),
        "gut": check.gut,
        "gut_text": f"{check.gut:.2f}" if check.gut is not None else "—",
        "omega_arag": check.omega_arag,
        "omega_text": f"{check.omega_arag:.1f}" if check.omega_arag is not None else "—",
        "ph": check.ph,
        "ph_text": f"{check.ph:.2f}" if check.ph is not None else "—",
        "temp_c": check.temp_c,
        "temp_text": f"{check.temp_c:.1f}" if check.temp_c is not None else "—",
        "level": check.level or "ok",
        "level_label": LEVEL_LABEL.get(check.level or "ok", "Normal"),
        "pattern": check.pattern,
        "severities": _signal_severities(check),
        "n_photos": n_photos,
        "is_example": check.is_example,
    }


# ---------------------------------------------------------------- tank page and inspector


def _series(state: TankState) -> dict:
    """Points for the survival sparkline and the tank page's trend charts."""
    batch = state.batch
    if batch is None:
        return {"points": []}
    points = [{
        "day": 0.0, "day_label": "Spawn", "check_id": None, "survival": 1.0, "length_um": None, "pct_dead": None,
        "pct_abnormal": None, "omega": None, "ph": None, "temp_c": None, "level": "ok",
    }]
    spawn_at = batch.spawn_date
    for check in state.checks:
        elapsed = (check.sampled_at.date() - spawn_at).days + (check.sampled_at.hour + check.sampled_at.minute / 60 - 12) / 24
        points.append({
            "day": round(max(elapsed, 0.01), 3),
            "day_label": f"Day {day_of(check.sampled_at, spawn_at)}",
            "check_id": check.id,
            "survival": check.survival,
            "length_um": check.mean_len_um,
            "pct_dead": check.pct_dead,
            "pct_abnormal": check.pct_abnormal,
            "omega": check.omega_arag,
            "ph": check.ph,
            "temp_c": check.temp_c,
            "level": check.level or "ok",
        })
    return {"points": points}


def build_tank(tank_id: str, session: Session) -> dict | None:
    world = load_world(session)
    state = world.tanks.get(tank_id)
    if state is None:
        return None
    decisions = all_decisions(session)
    summary = tank_summary(state, world)

    latest_view = None
    if state.latest is not None:
        check = state.latest
        photos = photos_of_check(check.id, session)
        latest_view = {
            "id": check.id,
            "sampled_at": check.sampled_at.isoformat(),
            "when_text": fmt_when(check.sampled_at, world.now),
            "n_live": check.n_live,
            "n_abnormal": check.n_abnormal,
            "n_dead": check.n_dead,
            "n_counted": check.n_live + check.n_abnormal + check.n_dead,
            "photo": photo_view(photos[0], session) if photos else None,
            "n_photos": len(photos),
            "hist": check.hist,
        }

    actions = [decision_view(d, world.now) for d in actions_for_tank(state, world, decisions)]
    left = sum(1 for a in actions if a["status"] == "pending")

    batches = {b.id: b for b in state.all_batches}
    photo_counts: dict[int, int] = {}
    if state.checks:
        for photo in session.exec(
            select(models.Photo).where(models.Photo.check_id.in_([c.id for c in state.checks]))
        ):
            photo_counts[photo.check_id] = photo_counts.get(photo.check_id, 0) + 1
    check_rows = [
        check_row(c, batches.get(c.batch_id), world, photo_counts.get(c.id, 0)) for c in reversed(state.checks)
    ]

    # What this tank has been told and what was done about it, newest first
    history = [
        decision_view(d, world.now)
        for d in sorted(
            (d for d in decisions if touches_tank(d, state) and d.status != "pending"),
            key=lambda d: d.decided_at or d.created_at,
            reverse=True,
        )
    ]

    past_batches = [
        {
            "id": b.id, "code": b.code, "spawn_date": b.spawn_date.isoformat(), "stocked": b.stocked, "status": b.status,
            "outcome": b.outcome, "closed_on": b.closed_on.isoformat() if b.closed_on else None,
        }
        for b in state.all_batches if b.status != "active"
    ]

    return summary | {
        "batch": {
            "id": state.batch.id, "code": state.batch.code, "spawn_date": state.batch.spawn_date.isoformat(),
            "stocked": state.batch.stocked, "stocked_text": fmt_count(state.batch.stocked), "status": state.batch.status,
        } if state.batch else None,
        "latest_check": latest_view,
        "condition": condition_rows(state.assessment, world.cfg) if state.assessment else [],
        "signals": [s.to_json() for s in state.assessment.signals] if state.assessment else [],
        "growth_um_day": state.assessment.growth_um_day if state.assessment else None,
        "loss_per_day": state.assessment.loss_per_day if state.assessment else None,
        "rules_version": state.assessment.rules_version if state.assessment else None,
        "series": _series(state),
        "expected_growth_um_day": world.cfg["expected_growth_um_day"],
        "actions": actions,
        "actions_left": left,
        "checks": check_rows,
        "decision_history": history,
        "past_batches": past_batches,
        "line_water": line_water(state.line_id, world, session),
    }


def build_tanks_list(session: Session) -> dict:
    world = load_world(session)
    return {"tanks": [tank_summary(s, world) for s in world.tanks.values()]}
