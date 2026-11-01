"""Level ladder, patterns and line alerts (SPEC §7.2, §7.3, §7.6). Pure functions.

`assess` reads only checks[:upto+1], so history replays exactly: a later crash can never change
what the system said before it.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.config import RULES_VERSION
from app.rules.series import BatchData, CheckData, Rates, rates_at, stage_for
from app.rules.signals import SEVERITY_RANK, Signal, compute_signals

LEVEL_RANK = {"empty": 0, "ok": 1, "watch": 2, "risk": 3, "critical": 4}
LEVEL_LABEL = {"critical": "Critical", "risk": "At risk", "watch": "Watch", "ok": "Normal", "empty": "Empty"}


@dataclass(frozen=True)
class Assessment:
    level: str
    pattern: str | None
    signals: list[Signal]
    growth_um_day: float | None
    loss_per_day: float | None
    survival: float | None
    stage: str | None
    rules_version: str = RULES_VERSION
    check: CheckData | None = None
    previous: CheckData | None = None
    tank_kind: str = "larval"
    stocked: int = 0
    _by_key: dict = field(default_factory=dict, repr=False)

    def sev(self, key: str) -> str | None:
        return self._by_key.get(key)

    def at_least(self, key: str, severity: str = "watch") -> bool:
        current = self.sev(key)
        return current is not None and SEVERITY_RANK[current] >= SEVERITY_RANK[severity]


def _at_least(by_key: Mapping[str, str], keys: Iterable[str], severity: str = "watch") -> bool:
    wanted = SEVERITY_RANK[severity]
    return any(key in by_key and SEVERITY_RANK[by_key[key]] >= wanted for key in keys)


LARVAE_KEYS = ("dead", "abnormal", "growth", "gut", "spread")
WATER_KEYS = ("omega", "ph", "temp", "oxygen")


def level_for(signals: Sequence[Signal]) -> str:
    """First match of the ladder in SPEC §7.2. Water alone, or loss alone, never goes above Watch."""
    by_key = {s.key: s.severity for s in signals}
    larvae_critical = _at_least(by_key, LARVAE_KEYS, "critical")
    if larvae_critical or (_at_least(by_key, ["dead"], "risk") and _at_least(by_key, ["loss"], "risk")):
        return "critical"
    larvae_watch = _at_least(by_key, LARVAE_KEYS, "watch")
    if (
        _at_least(by_key, LARVAE_KEYS, "risk")
        or (_at_least(by_key, WATER_KEYS, "risk") and larvae_watch)
        or (_at_least(by_key, ["loss"], "risk") and larvae_watch)
    ):
        return "risk"
    if signals:
        return "watch"
    return "ok"


def pattern_for(signals: Sequence[Signal], level: str) -> str | None:
    """First match of the table in SPEC §7.3. A missing reading counts as OK."""
    if level in ("ok", "empty"):
        return None
    by_key = {s.key: s.severity for s in signals}
    watch = lambda *keys: _at_least(by_key, keys)  # noqa: E731
    water_bad = watch("omega", "ph")
    larvae_any = watch(*LARVAE_KEYS)
    if watch("dead", "loss") and watch("gut", "growth") and not water_bad:
        return "bacterial"
    if water_bad and watch("abnormal", "growth", "dead"):
        return "corrosive"
    if water_bad and not larvae_any:
        return "corrosive_early"
    if watch("gut", "growth") and not watch("dead", "loss"):
        return "underfed"
    if watch("spread"):
        return "splitting"
    if watch("temp"):
        return "temperature"
    if watch("oxygen"):
        return "oxygen"
    if watch("loss") and not larvae_any:
        return "unexplained_loss"
    return "early_warning"


def assess(checks: Sequence[CheckData], batch: BatchData, tank_kind: str, cfg: Mapping,
           upto: int | None = None) -> Assessment:
    """Assess a batch at check `upto` (default: the last check), reading nothing after it."""
    visible = list(checks[: upto + 1]) if upto is not None else list(checks)
    if not visible:
        return Assessment(level="ok", pattern=None, signals=[], growth_um_day=None, loss_per_day=None,
                          survival=None, stage=None, tank_kind=tank_kind, stocked=batch.stocked)
    i = len(visible) - 1
    check = visible[i]
    rates: Rates = rates_at(visible, i, batch, tank_kind, cfg)
    signals = compute_signals(check, rates, cfg)
    level = level_for(signals)
    return Assessment(
        level=level,
        pattern=pattern_for(signals, level),
        signals=signals,
        growth_um_day=rates.growth_um_day,
        loss_per_day=rates.loss_per_day,
        survival=rates.survival,
        stage=stage_for(check.mean_len_um, tank_kind),
        check=check,
        previous=rates.previous,
        tank_kind=tank_kind,
        stocked=batch.stocked,
        _by_key={s.key: s.severity for s in signals},
    )


@dataclass(frozen=True)
class LineAlert:
    line_id: str
    since: datetime
    tank_ids: tuple[str, ...]  # tanks whose latest check has corrosive water


def _water_is_corrosive(check: CheckData, cfg: Mapping) -> bool:
    if check.omega_arag is not None and check.omega_arag < cfg["omega_arag"][0]:
        return True
    return check.ph is not None and check.ph < cfg["ph"][0]


def _has_water(check: CheckData) -> bool:
    return check.omega_arag is not None or check.ph is not None


def line_alert(line_id: str, tank_checks: Mapping[str, Sequence[CheckData]], now: datetime,
               cfg: Mapping) -> LineAlert | None:
    """On when ≥ 2 active tanks on the line have corrosive water on a latest check within 3 days.

    `tank_checks` holds the active batch's checks (oldest first) for each active tank on the line.
    `since` is the first alerting check of the current run across the line.
    """
    window = timedelta(days=cfg["line_alert_window_days"])
    alerting = [
        tank_id for tank_id, checks in sorted(tank_checks.items())
        if checks and now - checks[-1].sampled_at <= window and _water_is_corrosive(checks[-1], cfg)
    ]
    if len(alerting) < cfg["line_alert_min_tanks"]:
        return None
    every_check = sorted((c for checks in tank_checks.values() for c in checks), key=lambda c: c.sampled_at, reverse=True)
    since = None
    for check in every_check:
        if not _has_water(check):
            continue
        if not _water_is_corrosive(check, cfg):
            break
        since = check.sampled_at
    return LineAlert(line_id=line_id, since=since or now, tank_ids=tuple(alerting))
