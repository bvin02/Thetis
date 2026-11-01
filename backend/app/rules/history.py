"""The Last 14 days grid (SPEC §7.8). Pure functions."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.rules.assess import LEVEL_LABEL, LEVEL_RANK
from app.rules.text import fmt_day_month


@dataclass(frozen=True)
class BatchHistory:
    spawn_date: date
    closed_on: date | None
    checks: Sequence[tuple[datetime, str]]  # (sampled_at, level), oldest first


def _active_on(batch: BatchHistory, day: date) -> bool:
    return batch.spawn_date <= day and (batch.closed_on is None or day <= batch.closed_on)


def _level_on(batch: BatchHistory, day: date) -> str:
    """The level of the batch's most recent check on or before the end of `day`."""
    level = "ok"
    for sampled_at, check_level in batch.checks:
        if sampled_at.date() <= day:
            level = check_level or "ok"
    return level


def _change(level: str | None, prev: str | None, first: bool, emptied: bool) -> str:
    if level is None:
        return "Tank emptied" if emptied else "No batch in this tank"
    if first:
        return "Start of this view"
    if prev is None:
        return "First day of a new batch"
    if prev == level:
        return "No change from the day before"
    worse = LEVEL_RANK[level] > LEVEL_RANK[prev]
    return f"{'Worsened' if worse else 'Improved'} from {LEVEL_LABEL[prev]}"


def tank_history(batches: Sequence[BatchHistory], today: date, days: int = 14) -> list[dict]:
    """One cell per day, oldest first. `level` is None when no batch was in the tank."""
    cells: list[dict] = []
    prev: str | None = None
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        active = [b for b in batches if _active_on(b, day)]
        level: str | None = None
        if active:
            level = _level_on(max(active, key=lambda b: b.spawn_date), day)
        emptied = level is None and any(b.closed_on is not None and b.closed_on < day for b in batches)
        cells.append({
            "date": day.isoformat(),
            "date_text": f"{day.strftime('%a')}, {fmt_day_month(day)}" + (" (today)" if day == today else ""),
            "level": level,
            "label": LEVEL_LABEL[level] if level else ("Empty" if emptied else "No batch"),
            "change": _change(level, prev, offset == days - 1, emptied),
        })
        prev = level
    return cells


def history_days(today: date, days: int = 14) -> list[dict]:
    """The axis labels under the grid: "18 / Oct", "19 / M", ... "Today / S"."""
    out = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        is_first = offset == days - 1
        is_today = offset == 0
        out.append({
            "date": day.isoformat(),
            "num": "Today" if is_today else str(day.day),
            "sub": day.strftime("%b") if is_first else day.strftime("%a")[0],
            "is_today": is_today,
        })
    return out
