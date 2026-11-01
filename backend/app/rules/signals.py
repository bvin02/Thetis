"""Measured warning signs (SPEC §7.1). Pure functions. Missing data means the signal is skipped."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from app.rules.series import CheckData, Rates

SEVERITY_RANK = {"watch": 1, "risk": 2, "critical": 3}
FLOAT_NOISE_DECIMALS = 9  # a computed rate sitting exactly on a threshold must count as on it


@dataclass(frozen=True)
class Signal:
    key: str
    severity: str  # watch | risk | critical
    value: float
    prev: float | None
    kind: str  # larvae | count | water

    def to_json(self) -> dict:
        return asdict(self)


def _high_is_bad(value: float, rungs: tuple) -> str | None:
    """≥ thresholds: (watch, risk, critical)."""
    watch, risk, critical = rungs
    if critical is not None and value >= critical:
        return "critical"
    if risk is not None and value >= risk:
        return "risk"
    if watch is not None and value >= watch:
        return "watch"
    return None


def _low_is_bad(value: float, rungs: tuple) -> str | None:
    """< thresholds: (watch, risk, critical)."""
    watch, risk, critical = rungs
    if critical is not None and value < critical:
        return "critical"
    if risk is not None and value < risk:
        return "risk"
    if watch is not None and value < watch:
        return "watch"
    return None


def _strictly_above(value: float, rungs: tuple) -> str | None:
    """> thresholds: (watch, risk, critical)."""
    watch, risk, critical = rungs
    if critical is not None and value > critical:
        return "critical"
    if risk is not None and value > risk:
        return "risk"
    if watch is not None and value > watch:
        return "watch"
    return None


def _with_rise(severity: str | None, value: float, prev: float | None, rise: float) -> str | None:
    """A jump against the previous check is at least a watch."""
    if severity is None and prev is not None and round(value - prev, FLOAT_NOISE_DECIMALS) >= rise:
        return "watch"
    return severity


def compute_signals(check: CheckData, rates: Rates, cfg: Mapping) -> list[Signal]:
    prev = rates.previous
    out: list[Signal] = []

    def add(key: str, severity: str | None, value: float, prev_value: float | None, kind: str) -> None:
        if severity is not None:
            out.append(Signal(key, severity, value, prev_value, kind))

    if check.pct_dead is not None:
        p = prev.pct_dead if prev else None
        sev = _with_rise(_high_is_bad(check.pct_dead, cfg["dead_pct"]), check.pct_dead, p, cfg["dead_rise_points"])
        add("dead", sev, check.pct_dead, p, "larvae")

    if check.pct_abnormal is not None:
        p = prev.pct_abnormal if prev else None
        sev = _with_rise(
            _high_is_bad(check.pct_abnormal, cfg["abnormal_pct"]), check.pct_abnormal, p, cfg["abnormal_rise_points"]
        )
        add("abnormal", sev, check.pct_abnormal, p, "larvae")

    if rates.growth_um_day is not None:
        ratio = round(rates.growth_um_day / cfg["expected_growth_um_day"], FLOAT_NOISE_DECIMALS)
        add("growth", _low_is_bad(ratio, cfg["growth_ratio"]), rates.growth_um_day, None, "larvae")

    if check.gut is not None:
        p = prev.gut if prev else None
        add("gut", _low_is_bad(check.gut, cfg["gut_index"]), check.gut, p, "larvae")

    if check.cv is not None:
        p = prev.cv if prev else None
        sev = _with_rise(_high_is_bad(check.cv, cfg["spread_cv"]), check.cv, p, cfg["spread_rise"])
        add("spread", sev, check.cv, p, "larvae")

    if rates.loss_per_day is not None:
        rate = round(rates.loss_per_day, FLOAT_NOISE_DECIMALS)
        add("loss", _strictly_above(rate, cfg["loss_per_day"]), rates.loss_per_day, None, "count")

    if check.omega_arag is not None:
        add("omega", _low_is_bad(check.omega_arag, cfg["omega_arag"]), check.omega_arag, None, "water")

    if check.ph is not None:
        add("ph", _low_is_bad(check.ph, cfg["ph"]), check.ph, None, "water")

    if check.temp_c is not None:
        off = round(abs(check.temp_c - cfg["target_temp_c"]), FLOAT_NOISE_DECIMALS)
        add("temp", _strictly_above(off, cfg["temp_off_c"]), check.temp_c, None, "water")

    if check.do_mgl is not None:
        add("oxygen", _low_is_bad(check.do_mgl, cfg["do_mgl"]), check.do_mgl, None, "water")

    return out
