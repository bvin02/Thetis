"""The action catalog and which actions each pattern recommends (SPEC §7.7). Pure functions.

Recommendations are approved by a person. Nothing here, or anywhere else, acts on equipment.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.rules.assess import Assessment

CATALOG: dict[str, dict[str, str]] = {
    "isolate": {
        "title": "Isolate {T}. Use separate screens, buckets and hoses.",
        "cta": "Approve isolation", "done": "Isolation approved",
    },
    "sample_vibrio": {
        "title": "Plate a water and larvae sample to check for Vibrio",
        "cta": "Request sampling", "done": "Sampling requested",
    },
    "restock": {
        "title": "Drain, clean and restock in fresh water today",
        "cta": "Approve drain and restock", "done": "Drain and restock approved",
    },
    "discard": {
        "title": "Discard this batch to protect the other tanks",
        "cta": "Approve discard", "done": "Discard approved",
    },
    "buffer_line": {
        "title": "Buffer line {n} water to bring Ω aragonite to 3 or higher",
        "cta": "Approve buffering", "done": "Buffering approved",
    },
    "hold_spawn": {
        "title": "Hold the next spawn until line {n} water recovers",
        "cta": "Hold next spawn", "done": "Next spawn on hold",
    },
    "buffer_tank": {
        "title": "Buffer this tank's water to bring Ω aragonite to 3 or higher",
        "cta": "Approve buffering", "done": "Buffering approved",
    },
    "screen": {
        "title": "Screen at the next drain and cull the slowest growers",
        "cta": "Schedule screening", "done": "Screening scheduled",
    },
    "feed_check": {
        "title": "Check the algae ration and culture health",
        "cta": "Request feed check", "done": "Feed check requested",
    },
    "recount": {
        "title": "Take a second sample now to confirm the count",
        "cta": "Request recount", "done": "Recount requested",
    },
    "temp_check": {
        "title": "Check the heater or chiller setpoint",
        "cta": "Request check", "done": "Check requested",
    },
    "aerate": {
        "title": "Increase aeration in this tank",
        "cta": "Approve", "done": "Aeration increased",
    },
}


def line_number(line_id: str | None) -> str:
    """"L2" -> "2"."""
    return (line_id or "").lstrip("Ll") or ""


def action_text(action: str, tank_id: str | None, line_id: str | None) -> dict[str, str]:
    entry = CATALOG[action]
    return {
        "title": entry["title"].format(T=tank_id or "this tank", n=line_number(line_id)),
        "cta": entry["cta"],
        "done": entry["done"],
    }


@dataclass(frozen=True)
class PlannedAction:
    scope: str  # tank | line
    action: str
    tank_id: str | None
    line_id: str | None

    @property
    def key(self) -> tuple[str, str, str]:
        target = self.line_id if self.scope == "line" else self.tank_id
        return (self.scope, target or "", self.action)


def actions_for(assessment: Assessment, tank_id: str, line_id: str | None, line_alert_on: bool,
                cfg: Mapping) -> list[PlannedAction]:
    """The decisions this tank's current pattern recommends, in display order."""
    pattern = assessment.pattern
    tank = lambda action: PlannedAction("tank", action, tank_id, None)  # noqa: E731
    line = lambda action: PlannedAction("line", action, None, line_id)  # noqa: E731

    if pattern == "bacterial":
        planned = [tank("isolate"), tank("sample_vibrio"), tank("restock")]
        check = assessment.check
        if check is not None and check.pct_dead is not None and check.pct_dead >= cfg["discard_dead_pct"]:
            planned.append(tank("discard"))
        return planned
    if pattern in ("corrosive", "corrosive_early"):
        if line_id is None:
            return [tank("buffer_tank")]
        planned = [line("buffer_line")]
        if line_alert_on:
            planned.append(line("hold_spawn"))
        return planned
    single = {
        "underfed": "feed_check",
        "splitting": "screen",
        "temperature": "temp_check",
        "oxygen": "aerate",
        "unexplained_loss": "recount",
        "early_warning": "recount",
    }
    return [tank(single[pattern])] if pattern in single else []
