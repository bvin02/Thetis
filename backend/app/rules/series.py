"""Tank math (SPEC §6). Pure functions over plain data, no database."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time

from app.analysis.summary import stage_for_length


@dataclass(frozen=True)
class CheckData:
    """The numbers from one check that the rules read."""

    sampled_at: datetime
    live_est: float | None = None
    pct_dead: float | None = None
    pct_abnormal: float | None = None
    mean_len_um: float | None = None
    cv: float | None = None
    gut: float | None = None
    temp_c: float | None = None
    ph: float | None = None
    omega_arag: float | None = None
    do_mgl: float | None = None
    id: int | None = None


@dataclass(frozen=True)
class BatchData:
    spawn_date: date
    stocked: int


@dataclass(frozen=True)
class Rates:
    survival: float | None
    loss_per_day: float | None
    growth_um_day: float | None
    baseline: CheckData | None
    previous: CheckData | None


def stage_for(mean_len_um: float | None, tank_kind: str) -> str | None:
    if tank_kind == "setting":
        return "Setting"
    return stage_for_length(mean_len_um)


def day_of(when: date | datetime, spawn_date: date) -> int:
    """Whole days since spawn, from local dates."""
    local = when.date() if isinstance(when, datetime) else when
    return (local - spawn_date).days


def baseline_index(checks: Sequence[CheckData], i: int, cfg: Mapping) -> int | None:
    """The most recent earlier check at least `baseline_min_days` older than check i."""
    current = checks[i].sampled_at
    for j in range(i - 1, -1, -1):
        delta_days = (current - checks[j].sampled_at).total_seconds() / 86400.0
        if delta_days >= cfg["baseline_min_days"]:
            return j
    return None


def rates_at(checks: Sequence[CheckData], i: int, batch: BatchData, tank_kind: str, cfg: Mapping) -> Rates:
    """Survival, loss rate and growth of check i, reading only checks 0..i."""
    check = checks[i]
    survival = check.live_est / batch.stocked if check.live_est is not None and batch.stocked else None
    previous = checks[i - 1] if i > 0 else None
    b = baseline_index(checks, i, cfg)
    baseline = checks[b] if b is not None else None

    # Loss: against the baseline check, or against stocking at spawn when there is none
    loss = None
    if check.live_est is not None and check.live_est > 0:
        if baseline is not None:
            base_live, base_time = baseline.live_est, baseline.sampled_at
        else:
            base_live = float(batch.stocked)
            base_time = datetime.combine(batch.spawn_date, time(cfg["spawn_hour"]))
        delta_days = (check.sampled_at - base_time).total_seconds() / 86400.0
        if base_live and base_live > 0 and delta_days > 0:
            loss = -math.log(check.live_est / base_live) / delta_days

    # Growth: skipped in setting tanks, and once eyed larvae have stopped growing before they set
    growth = None
    if (
        baseline is not None
        and tank_kind != "setting"
        and check.mean_len_um is not None
        and baseline.mean_len_um is not None
        and baseline.mean_len_um < cfg["growth_skip_baseline_um"]
    ):
        delta_days = (check.sampled_at - baseline.sampled_at).total_seconds() / 86400.0
        if delta_days > 0:
            growth = (check.mean_len_um - baseline.mean_len_um) / delta_days

    return Rates(survival=survival, loss_per_day=loss, growth_um_day=growth, baseline=baseline, previous=previous)
