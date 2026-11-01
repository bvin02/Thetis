"""The Advisor: rules output with its decisions attached, the plant's settings, and what Claude is given to read."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlmodel import Session

from app import config, models
from app.rules.actions import ANSWER_CREATES_ROW, PlannedAction
from app.rules.advisor import crash_risks, forecast_json, larvae_at_risk, yield_opportunities
from app.rules.assess import LEVEL_LABEL
from app.rules.facts import Forecast, TankFacts, batch_loss_per_day, forecast_for, project
from app.rules.playbook import Playbook, plant_options
from app.rules.text import fmt_count, fmt_pct, title_for
from app.rules.water import BUFFERS, DISINFECTANTS, WaterReading
from app.services.decisions import (
    actions_for_tank,
    all_decisions,
    decision_view,
    latest_row,
    pending_count,
    planned_for,
    step_view,
    unanswered_view,
)
from app.services.world import TankState, World, load_world

# ---------------------------------------------------------------- from the database to plain facts


def tank_facts(state: TankState, world: World) -> TankFacts:
    latest = state.latest
    return TankFacts(
        id=state.id,
        kind=state.kind,
        room_id=state.tank.room_id,
        room_name=state.room.name,
        line_id=state.line_id,
        volume_l=state.tank.volume_l,
        status=state.tank.status,
        batch_code=state.batch.code if state.batch else None,
        spawn_date=state.batch.spawn_date if state.batch else None,
        stocked=state.batch.stocked if state.batch else 0,
        day=state.day(world.now),
        checks=tuple(state.data),
        assessment=state.assessment,
        level=state.level,
        hist=tuple(latest.hist) if latest is not None and latest.hist else None,
    )


def all_facts(world: World) -> dict[str, TankFacts]:
    return {state.id: tank_facts(state, world) for state in world.tanks.values()}


def _newest_water(checks: list[models.Check], window: timedelta) -> WaterReading | None:
    """The newest reading of each value, filling gaps only from checks close to the newest one."""
    values: dict[str, float | None] = dict.fromkeys(("temp_c", "salinity_ppt", "ph", "omega_arag"))
    newest = None
    for check in sorted(checks, key=lambda c: c.sampled_at, reverse=True):
        if newest is not None and newest - check.sampled_at > window:
            break
        for key in values:
            reading = getattr(check, key)
            if values[key] is None and reading is not None:
                values[key] = reading
                newest = newest or check.sampled_at
    return WaterReading(**values) if newest is not None else None


def water_by_scope(world: World) -> dict[str, WaterReading]:
    window = timedelta(hours=world.cfg["line_reading_window_h"])
    water: dict[str, WaterReading] = {}
    for line_id in world.lines:
        checks = [c for s in world.tanks.values() if s.line_id == line_id for c in s.checks]
        reading = _newest_water(checks, window)
        if reading is not None:
            water[line_id] = reading
    for state in world.tanks.values():
        if state.line_id is None and state.checks:
            reading = _newest_water(state.checks, window)
            if reading is not None:
                water[state.id] = reading
    return water


def playbook_for(world: World, facts: dict[str, TankFacts] | None = None) -> Playbook:
    return Playbook(plant=world.cfg["plant"], tanks=facts or all_facts(world), water=water_by_scope(world), cfg=world.cfg)


def _plans_for(world: World):
    return lambda tank: planned_for(world.tanks[tank.id], world)


# ---------------------------------------------------------------- the page


def _tile_json(tile) -> dict:
    return {
        "key": tile.key, "label": tile.label, "tank_id": tile.tank_id, "points": [list(p) for p in tile.points],
        "point_texts": list(tile.point_texts),
        "now_text": tile.now_text, "target_text": tile.target_text, "severity": tile.severity, "guide": tile.guide,
        "summary": tile.summary,
    }


def batch_start(tank_id: str | None, world: World) -> datetime | None:
    """When the tank's current batch began: an answer given before this was about a different batch."""
    state = world.tanks.get(tank_id or "")
    if state is None or state.batch is None:
        return None
    return datetime.combine(state.batch.spawn_date, time.min)


def _steps_for_tanks(plans, tank_ids, world: World, decisions, book: Playbook, other_pending: bool = True) -> list[dict]:
    """A card's steps: the planned ones and, on a risk card, anything else still pending for its tanks, each shown once."""
    steps: list[dict] = []
    seen: set[tuple] = set()
    for plan in plans:
        if plan.key in seen:
            continue
        seen.add(plan.key)
        suggestion = plan.action in ANSWER_CREATES_ROW
        since = batch_start(plan.tank_id, world) if suggestion else None
        if not suggestion and latest_row(decisions, plan) is None:
            continue  # a recommendation gets its row when a check is saved
        steps.append(step_view(plan, decisions, world.now, book, since))
    if not other_pending:
        return steps
    for tank_id in tank_ids:
        state = world.tanks.get(tank_id)
        if state is None:
            continue
        for decision in actions_for_tank(state, world, decisions):
            key = (decision.scope, decision.line_id if decision.scope == "line" else decision.tank_id, decision.action)
            if decision.status == "pending" and key not in seen and (decision.scope == "tank" or len(tank_ids) == 1):
                seen.add(key)
                steps.append(decision_view(decision, world.now, book))
    return steps


def _plain_view(item, world: World, decisions, book: Playbook, other_pending: bool = True) -> dict:
    view = item.to_json()
    view["tiles"] = [_tile_json(t) for t in item.tiles]
    view["tank_ids"] = list(item.tank_ids)
    view["steps"] = _steps_for_tanks(item.plans, list(item.tank_ids), world, decisions, book, other_pending)
    view["steps_left"] = sum(1 for s in view["steps"] if s["status"] == "pending")
    return view


def _views(risks, opportunities, world: World, decisions, book: Playbook) -> tuple[list[dict], list[dict]]:
    """A yield card lists only its own steps: another tank problem belongs on that problem's card."""
    return (
        [_plain_view(r, world, decisions, book) for r in risks],
        [_plain_view(o, world, decisions, book, other_pending=False) for o in opportunities],
    )


def _steps_waiting(views: list[dict]) -> int:
    """Each step counts once, even when two cards show it."""
    steps = (step for view in views for step in view["steps"] if step["status"] == "pending")
    return len({(s["scope"], s["tank_id"], s["line_id"], s["action"], s["title"]) for s in steps})


def _suggested_questions(risks, opportunities, book: Playbook) -> list[str]:
    questions = ["What should I do first today?", "What could crash next, and why?"]
    line_risk = next((r for r in risks if r.line_id and r.id.startswith("line-")), None)
    if line_risk is not None:
        number = line_risk.line_id.lstrip("Ll")
        questions.append(f"How do I bring line {number} back up with {BUFFERS[book.buffer].short}?")
    bacterial = next((r for r in risks if "bacterial" in r.title), None)
    if bacterial is not None:
        questions.append(f"How do I keep {bacterial.tank_ids[0]} from spreading to other tanks?")
    pace = next((o for o in opportunities if o.kind == "slow_pace"), None)
    if pace is not None:
        questions.append(f"Why is {pace.tank_ids[0]} losing more larvae than our best batch?")
    questions.append("Where am I losing the most yield this week?")
    return questions[:5]


def _plant_view(world: World, book: Playbook) -> dict:
    return {
        "buffer": book.buffer,
        "disinfectant": book.plant.get("disinfectant") if book.plant.get("disinfectant") in DISINFECTANTS else "sodium_hypochlorite",
        **plant_options(),
    }


def _headline(n_risks: int, n_yield: int) -> str:
    risks = "1 risk could turn into a crash" if n_risks == 1 else f"{n_risks} risks could turn into a crash"
    ways = "1 way to raise yield" if n_yield == 1 else f"{n_yield} ways to raise yield"
    if n_risks == 0 and n_yield == 0:
        return "Nothing to act on right now"
    if n_risks == 0:
        return f"No crash risks. {ways[0].upper()}{ways[1:]}."
    if n_yield == 0:
        return f"{risks}."
    return f"{risks}. {ways[0].upper()}{ways[1:]}."


def compute(world: World) -> tuple[dict[str, TankFacts], list, list, Forecast, Playbook]:
    """The rules' view of the hatchery, shared by the page, the Floor, the tank page and Claude's snapshot."""
    facts = all_facts(world)
    ordered = list(facts.values())
    plans = _plans_for(world)
    forecast = forecast_for(ordered, world.cfg)
    risks = crash_risks(ordered, world.alerts, forecast.pace, plans, world.cfg)
    opportunities = yield_opportunities(ordered, forecast.pace, plans, world.cfg)
    return facts, risks, opportunities, forecast, playbook_for(world, facts)


def build_advisor(session: Session) -> dict:
    world = load_world(session)
    decisions = all_decisions(session)
    facts, risks, opportunities, forecast, book = compute(world)
    at_risk = larvae_at_risk(risks, facts)
    total_live = sum(t.live or 0 for t in facts.values())
    risk_views, yield_views = _views(risks, opportunities, world, decisions, book)
    forecast_view = forecast_json(forecast, facts, world.cfg)
    return {
        "seeded": world.hatchery is not None,
        "now": world.now.isoformat(),
        "headline": _headline(len(risks), len(opportunities)),
        "totals": {
            "at_risk": at_risk,
            "at_risk_text": fmt_count(at_risk),
            "total_live_text": fmt_count(total_live),
            "on_course_text": forecast_view["on_course_text"],
            "possible_text": forecast_view["possible_text"],
            "gain_text": forecast_view["gain_text"],
            "steps_waiting": _steps_waiting(risk_views + yield_views),
        },
        "risks": risk_views,
        "opportunities": yield_views,
        "forecast": forecast_view,
        "plant": _plant_view(world, book),
        "questions": _suggested_questions(risks, opportunities, book),
        "pending_decisions": pending_count(decisions),
    }


def _next_step(risks, decisions, world: World, book: Playbook) -> dict | None:
    """The first step still waiting on the worst risk, for the top of the Floor."""
    for risk in risks:
        for step in _steps_for_tanks(risk.plans, list(risk.tank_ids), world, decisions, book):
            if step["status"] == "pending":
                return {"title": step["title"], "card_id": risk.id}
    return None


def floor_summary(world: World, decisions: list[models.Decision]) -> dict:
    """The Floor's next step and "Raise yield" row."""
    _facts, risks, opportunities, _forecast, book = compute(world)
    return {
        "n_risks": len(risks),
        "n_yield": len(opportunities),
        "next_step": _next_step(risks, decisions, world, book),
        "yield_label": "1 suggestion" if len(opportunities) == 1 else f"{len(opportunities)} suggestions",
        "yield_chips": [
            {"id": o.tank_ids[0], "chip": o.chip, "title": o.title} for o in opportunities
        ],
    }


def suggestions_for_tank(state: TankState, world: World, decisions, book: Playbook) -> list[dict]:
    """Yield suggestions for one tank that aren't already among its recommended actions."""
    facts = book.tanks
    forecast = forecast_for(list(facts.values()), world.cfg)
    opportunities = yield_opportunities(list(facts.values()), forecast.pace, _plans_for(world), world.cfg)
    steps = []
    for item in opportunities:
        if state.id not in item.tank_ids:
            continue
        for plan in item.plans:
            # Anything else, like a screen step, is already among the tank's recommended actions
            if plan.action in ANSWER_CREATES_ROW:
                steps.append(step_view(plan, decisions, world.now, book, batch_start(plan.tank_id, world)))
    return steps


# ---------------------------------------------------------------- plant settings


def set_plant(session: Session, buffer: str | None, disinfectant: str | None) -> dict:
    hatchery = session.get(models.Hatchery, 1)
    if hatchery is None:
        raise ValueError("No hatchery set up yet.")
    if buffer is not None and buffer not in BUFFERS:
        raise ValueError(f"Unknown buffer: {buffer}")
    if disinfectant is not None and disinfectant not in DISINFECTANTS:
        raise ValueError(f"Unknown disinfectant: {disinfectant}")
    settings = dict(hatchery.settings or {})
    plant = dict(settings.get("plant") or {})
    if buffer is not None:
        plant["buffer"] = buffer
    if disinfectant is not None:
        plant["disinfectant"] = disinfectant
    settings["plant"] = plant
    hatchery.settings = settings  # a new object, so the JSON column notices the change
    session.add(hatchery)
    session.commit()
    return plant


# ---------------------------------------------------------------- what Claude reads


def _rounded(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _check_row(spawn_date, row: models.Check, world: World) -> dict:
    return {
        "days_ago": (world.now.date() - row.sampled_at.date()).days,
        "day": (row.sampled_at.date() - spawn_date).days,
        "live_est": _rounded(row.live_est, 0),
        "pct_dead": _rounded(row.pct_dead, 1),
        "pct_abnormal": _rounded(row.pct_abnormal, 1),
        "length_um": _rounded(row.mean_len_um, 1),
        "cv": _rounded(row.cv, 3),
        "gut": _rounded(row.gut, 2),
        "growth_um_day": _rounded(row.growth_um_day, 1),
        "loss_pct_per_day": _rounded(row.loss_per_day * 100 if row.loss_per_day is not None else None, 1),
        "survival_pct": _rounded(row.survival * 100 if row.survival is not None else None, 1),
        "ph": _rounded(row.ph, 2),
        "omega_arag": _rounded(row.omega_arag, 2),
        "temp_c": _rounded(row.temp_c, 1),
        "do_mgl": _rounded(row.do_mgl, 1),
        "salinity_ppt": _rounded(row.salinity_ppt, 1),
        "level": row.level,
        "pattern": row.pattern,
    }


def _clean(row: dict) -> dict:
    """Leave out what wasn't measured: shorter, and Claude can't mistake a gap for a zero."""
    return {k: v for k, v in row.items() if v is not None}


def _past_batches(world: World) -> list[dict]:
    past = []
    for state in world.tanks.values():
        for batch in state.all_batches:
            if batch.status == "active":
                continue
            checks = world.checks_by_batch.get(batch.id, [])
            last = checks[-1] if checks else None
            past.append(_clean({
                "code": batch.code,
                "tank": state.id,
                "stocked": batch.stocked,
                "outcome": batch.outcome,
                "closed_days_ago": (world.now.date() - batch.closed_on).days if batch.closed_on else None,
                "days_run": (batch.closed_on - batch.spawn_date).days if batch.closed_on else None,
                "final_survival_pct": _rounded(last.survival * 100 if last and last.survival is not None else None, 1),
                "final_length_um": _rounded(last.mean_len_um if last else None, 1),
                "note": batch.note,
            }))
    return past


def _decision_row(decision: models.Decision, world: World) -> dict:
    view = decision_view(decision, world.now)
    return _clean({
        "step": view["title"],
        "target": decision.tank_id or decision.line_id,
        "status": decision.status,
        "raised_days_ago": (world.now.date() - decision.created_at.date()).days,
        "decided_days_ago": (world.now.date() - decision.decided_at.date()).days if decision.decided_at else None,
        "note": view["note"],
    })


def _dose_text(step: dict) -> str | None:
    dose = step.get("dose")
    if not dose:
        return None
    parts = [dose["label"], dose["per_1000l_text"]]
    if dose.get("total_text"):
        parts.append(dose["total_text"])
    parts.append(dose["effect_text"])
    return ", ".join(parts)


def _card_row(view: dict, kind: str) -> dict:
    row = {
        "id": view["id"],
        "title": view["title"],
        "tanks": view["tank_ids"],
        "steps": [
            _clean({"step": s["title"], "status": s["status"], "how": s["how"], "dose": _dose_text(s)}) for s in view["steps"]
        ],
    }
    if kind == "risk":
        row |= {"level": LEVEL_LABEL[view["level"]], "larvae_at_stake": view["at_stake"], "forecast": view["forecast"]}
        if view.get("outlook"):
            row["outlook"] = view["outlook"]
    else:
        row["expected"] = f"{view['stat_text']} {view['stat_label']}"
    return row


def build_snapshot(session: Session) -> dict:
    """Everything Claude reads. Days are relative to today, so a re-seed gives the same snapshot and hits the cache."""
    world = load_world(session)
    decisions = all_decisions(session)
    facts, risks, opportunities, forecast, book = compute(world)
    risk_views, yield_views = _views(risks, opportunities, world, decisions, book)
    pace = forecast.pace

    tanks = []
    empty = []
    for state in world.tanks.values():
        tank = facts[state.id]
        if not state.active:
            empty.append({"id": state.id, "kind": state.kind, "room": state.room.name, "line": state.line_id,
                          "volume_l": state.tank.volume_l, "status": state.tank.status})
            continue
        assessment = state.assessment
        projection = project(tank, pace, world.cfg)
        tanks.append(_clean({
            "id": state.id,
            "kind": state.kind,
            "room": state.room.name,
            "line": state.line_id,
            "volume_l": state.tank.volume_l,
            "batch": state.batch.code,
            "day": state.day(world.now),
            "stocked": state.batch.stocked,
            "stage": assessment.stage if assessment else None,
            "level": LEVEL_LABEL[state.level],
            "status_title": title_for(assessment) if assessment and state.latest else None,
            "live_est": _rounded(tank.live, 0),
            "density_per_l": _rounded(tank.density_per_l, 0),
            "avg_loss_pct_per_day_since_stocking": _rounded((batch_loss_per_day(tank, world.cfg) or 0) * 100, 1),
            "days_to_eyed_at_current_growth": _rounded(projection.days_to_eyed, 1) if projection else None,
            "checks": [_clean(_check_row(state.batch.spawn_date, row, world)) for row in state.checks],
        }))

    return {
        "hatchery": world.hatchery.name if world.hatchery else None,
        "species": world.hatchery.species if world.hatchery else None,
        "plant_chemicals": {
            "buffer": BUFFERS[book.buffer].label,
            "disinfectant": book.disinfectant,
        },
        "thresholds": {
            "dead_pct": {"watch": world.cfg["dead_pct"][0], "risk": world.cfg["dead_pct"][1], "critical": world.cfg["dead_pct"][2]},
            "abnormal_pct": {"watch": world.cfg["abnormal_pct"][0], "risk": world.cfg["abnormal_pct"][1],
                             "critical": world.cfg["abnormal_pct"][2]},
            "expected_growth_um_day": world.cfg["expected_growth_um_day"],
            "gut_index_watch_below": world.cfg["gut_index"][0],
            "cv_watch_above": world.cfg["spread_cv"][0],
            "omega_arag_watch_below": world.cfg["omega_arag"][0],
            "ph_watch_below": world.cfg["ph"][0],
            "target_temp_c": world.cfg["target_temp_c"],
            "do_mgl_watch_below": world.cfg["do_mgl"][0],
            "eyed_um": world.cfg["eyed_um"],
            "density_limit_per_l": world.cfg["density_limit_per_l"],
        },
        "lines": [
            {
                "id": line.id,
                "alert": line.id in world.alerts,
                "since_days_ago": (world.now.date() - world.alerts[line.id].since.date()).days if line.id in world.alerts else None,
                "tanks": [s.id for s in world.tanks.values() if s.line_id == line.id and s.active],
            }
            for line in world.lines.values()
        ],
        "running_tanks": tanks,
        "free_tanks": empty,
        "past_batches": _past_batches(world),
        "rules_found": {
            "crash_risks": [_card_row(v, "risk") for v in risk_views],
            "yield_suggestions": [_card_row(v, "yield") for v in yield_views],
            "forecast": {
                "pace_batch": {"tank": pace.tank_id, "loss_pct_per_day": round(pace.loss_per_day * 100, 1)} if pace else None,
                "larvae_on_course_to_eyed": round(forecast.on_course),
                "larvae_possible_at_pace": round(forecast.possible),
            },
        },
        "decisions_log": [_decision_row(d, world) for d in decisions],
    }


def reading_text(snapshot: dict) -> str:
    """What Claude is given to read, in a few words."""
    tanks = snapshot["running_tanks"]
    checks = sum(len(t["checks"]) for t in tanks)
    past = len(snapshot["past_batches"])
    parts = f"{checks} checks across {len(tanks)} running tanks"
    if past:
        parts += f", {past} past {'batch' if past == 1 else 'batches'}"
    return f"{parts} and the decision log"


def analysis_key(snapshot: dict) -> dict:
    """What makes an analysis out of date. Answering a suggestion doesn't: that would re-run Claude on every click."""
    return {key: snapshot[key] for key in ("running_tanks", "free_tanks", "past_batches", "lines", "plant_chemicals", "thresholds")}


# ---------------------------------------------------------------- checking Claude's work


_EVIDENCE_LABEL = {
    "live_est": "live larvae", "pct_dead": "dead", "pct_abnormal": "abnormal", "length_um": "shell length", "cv": "size spread (CV)",
    "gut": "gut fullness", "growth_um_day": "growth", "loss_pct_per_day": "loss", "survival_pct": "survival", "ph": "pH",
    "omega_arag": "Ω", "temp_c": "temperature", "do_mgl": "oxygen", "density_per_l": "density",
}


def _evidence_value(metric: str, value: float) -> str:
    if metric == "live_est":
        return fmt_count(value)
    if metric in ("pct_dead", "pct_abnormal", "survival_pct"):
        return fmt_pct(value)
    if metric == "length_um":
        return f"{value:.0f} µm"
    if metric in ("cv", "gut", "ph"):
        return f"{value:.2f}"
    if metric == "growth_um_day":
        return f"{value:.1f} µm/day"
    if metric == "loss_pct_per_day":
        return f"{value:.1f}% a day"
    if metric == "omega_arag":
        return f"{value:.1f}"
    if metric == "temp_c":
        return f"{value:.1f} °C"
    if metric == "do_mgl":
        return f"{value:.1f} mg/L"
    return f"{value:,.0f} per L"  # density_per_l


def _when_text(days_ago: int) -> str:
    if days_ago <= 0:
        return "today"
    return "yesterday" if days_ago == 1 else f"{days_ago} days ago"


def _matches(metric: str, cited: float, actual: float) -> bool:
    if metric in config.CLAUDE_EVIDENCE_TOLERANCE:
        return abs(cited - actual) <= config.CLAUDE_EVIDENCE_TOLERANCE[metric]
    return abs(cited - actual) <= abs(actual) * config.CLAUDE_EVIDENCE_COUNT_TOLERANCE


def _verified_evidence(item: dict, tanks: dict[str, dict]) -> dict | None:
    """Look the cited reading up in the records. What's shown is the record's value, never the model's."""
    tank = tanks.get(item["tank_id"])
    metric, cited = item["metric"], item["value"]
    if tank is None:
        return None
    if metric == "density_per_l":
        actual = tank.get("density_per_l")
        if actual is None or not _matches(metric, cited, actual):
            return None
        return {"tank_id": tank["id"], "label": _EVIDENCE_LABEL[metric], "value_text": _evidence_value(metric, actual), "when_text": "now"}
    for check in reversed(tank.get("checks", [])):
        actual = check.get(metric)
        if actual is not None and _matches(metric, cited, actual):
            return {
                "tank_id": tank["id"], "label": _EVIDENCE_LABEL[metric], "value_text": _evidence_value(metric, actual),
                "when_text": _when_text(check["days_ago"]),
            }
    return None


def verify_analysis(raw: dict, snapshot: dict) -> dict:
    """Keep what the records back up. One reading that doesn't check out, or a tank that doesn't exist, and the whole
    insight goes: its text may lean on the same wrong number, and that text can't be checked."""
    tanks = {t["id"]: t for t in snapshot["running_tanks"]}
    known = set(tanks) | {t["id"] for t in snapshot["free_tanks"]}
    cards = {c["id"] for group in ("crash_risks", "yield_suggestions") for c in snapshot["rules_found"][group]}
    insights = []
    dropped = 0
    for insight in raw["insights"][: config.CLAUDE_MAX_INSIGHTS]:
        evidence = [_verified_evidence(item, tanks) for item in insight["evidence"]]
        tank_ids = insight["tank_ids"]
        if not evidence or None in evidence or not tank_ids or any(tank_id not in known for tank_id in tank_ids):
            dropped += 1
            continue
        insights.append({**insight, "evidence": evidence})
    priorities = [
        {**item, "ref": item["ref"] if item["ref"] in cards else ""} for item in raw["do_first"][: config.CLAUDE_MAX_PRIORITIES]
    ]
    return {"headline": raw["headline"], "brief": raw["brief"], "do_first": priorities, "insights": insights, "dropped": dropped}


def with_decisions(result: dict, world: World, decisions: list[models.Decision], book: Playbook) -> dict:
    """Each insight's suggestion, as a step a person can approve."""
    insights = []
    for insight in result.get("insights", []):
        text = insight["suggestion"]
        tank_id = insight["tank_ids"][0]
        since = batch_start(tank_id, world)
        row = next(
            (d for d in decisions if d.action == "claude_suggestion" and d.note == text and d.tank_id == tank_id
             and (since is None or d.created_at >= since)),
            None,
        )
        if row is not None:
            step = decision_view(row, world.now, book)
        else:
            step = unanswered_view(PlannedAction("tank", "claude_suggestion", tank_id, None), book) | {"title": text}
        insights.append({**insight, "step": step})
    return {**result, "insights": insights}
