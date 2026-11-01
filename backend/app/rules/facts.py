"""What the Advisor knows about a tank, and the rules-based forecast to the eyed stage. Pure functions."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time

from app.config import DEFAULT_ENGINE
from app.rules.assess import Assessment
from app.rules.series import CheckData


@dataclass(frozen=True)
class TankFacts:
    id: str
    kind: str  # larval | setting
    room_id: str
    room_name: str
    line_id: str | None
    volume_l: float
    status: str  # active | cleaning | empty
    batch_code: str | None = None
    spawn_date: date | None = None
    stocked: int = 0
    day: int | None = None
    checks: tuple[CheckData, ...] = ()
    assessment: Assessment | None = None
    level: str = "empty"
    hist: tuple[int, ...] | None = None  # the latest check's size histogram

    @property
    def active(self) -> bool:
        return self.batch_code is not None

    @property
    def latest(self) -> CheckData | None:
        return self.checks[-1] if self.checks else None

    @property
    def live(self) -> float | None:
        return self.latest.live_est if self.latest else None

    @property
    def length_um(self) -> float | None:
        return self.latest.mean_len_um if self.latest else None

    @property
    def density_per_l(self) -> float | None:
        return self.live / self.volume_l if self.live is not None and self.volume_l else None

    @property
    def pattern(self) -> str | None:
        return self.assessment.pattern if self.assessment else None


def elapsed_days(moment: datetime, spawn_date: date, cfg: Mapping) -> float:
    """Days since the spawn, in the same terms as the loss rate."""
    start = datetime.combine(spawn_date, time(cfg["spawn_hour"]))
    return max((moment - start).total_seconds() / 86400.0, 0.01)


def batch_loss_per_day(tank: TankFacts, cfg: Mapping) -> float | None:
    """The whole batch's average loss since stocking. Steadier than the latest check's rate."""
    latest = tank.latest
    if latest is None or latest.live_est is None or latest.live_est <= 0 or not tank.stocked or tank.spawn_date is None:
        return None
    return -math.log(latest.live_est / tank.stocked) / elapsed_days(latest.sampled_at, tank.spawn_date, cfg)


def size_below_share(hist: Sequence[int] | None, share: float) -> float | None:
    """The shell length under which this share of the sample falls, from the size histogram."""
    if not hist or sum(hist) == 0:
        return None
    wanted = share * sum(hist)
    running = 0.0
    for index, count in enumerate(hist):
        if count and running + count >= wanted:
            fraction = (wanted - running) / count
            return DEFAULT_ENGINE.hist_lo_um + (index + fraction) * DEFAULT_ENGINE.hist_bin_um
        running += count
    return None


def feed_cells_per_larva_day(length_um: float | None, cfg: Mapping) -> float | None:
    """FAO's ration for C. gigas at this shell length, by straight lines between the table's points."""
    if length_um is None:
        return None
    curve = cfg["feed_cells_per_larva_day"]
    if length_um <= curve[0][0]:
        return float(curve[0][1])
    for (x0, y0), (x1, y1) in zip(curve, curve[1:], strict=False):
        if length_um <= x1:
            return y0 + (y1 - y0) * (length_um - x0) / (x1 - x0)
    return float(curve[-1][1])


@dataclass(frozen=True)
class Pace:
    """The steadiest healthy batch. Other batches are compared with it, because it shares this plant's conditions."""

    tank_id: str
    loss_per_day: float


def pace_batch(tanks: Sequence[TankFacts], cfg: Mapping) -> Pace | None:
    candidates = []
    for tank in tanks:
        if not tank.active or tank.kind != "larval" or tank.level != "ok" or len(tank.checks) < cfg["pace_min_checks"]:
            continue
        loss = batch_loss_per_day(tank, cfg)
        if loss is not None and loss > 0:  # more larvae than were stocked is a counting error, not a pace to match
            candidates.append((loss, tank.id))
    if not candidates:
        return None
    loss, tank_id = min(candidates)
    return Pace(tank_id, loss)


@dataclass(frozen=True)
class Projection:
    tank_id: str
    live: float
    length_um: float
    days_to_eyed: float | None  # at the tank's current growth; None when not on course
    eyed_on_course: float  # larvae reaching the eyed stage if nothing changes; 0 when not on course
    eyed_possible: float  # if the tank grows as expected and loses larvae at the pace batch's rate

    @property
    def gain(self) -> float:
        return max(self.eyed_possible - self.eyed_on_course, 0.0)


def project(tank: TankFacts, pace: Pace | None, cfg: Mapping) -> Projection | None:
    """A straight-line forecast from the latest check's rates. Rules-based and rough, and labelled so in the UI."""
    live, length = tank.live, tank.length_um
    if tank.kind != "larval" or not tank.active or live is None or length is None or tank.assessment is None:
        return None
    eyed = cfg["eyed_um"]
    if length >= eyed:
        return Projection(tank.id, live, length, 0.0, live, live)
    expected = cfg["expected_growth_um_day"]
    growth = tank.assessment.growth_um_day if tank.assessment.growth_um_day is not None else expected
    loss = tank.assessment.loss_per_day if tank.assessment.loss_per_day is not None else (batch_loss_per_day(tank, cfg) or 0.0)
    loss = max(loss, 0.0)

    days = (eyed - length) / growth if growth > 0 else None
    on_course = days is not None and days <= cfg["project_max_days"]
    eyed_on_course = live * math.exp(-loss * days) if on_course else 0.0

    days_possible = (eyed - length) / max(growth, expected)
    loss_possible = min(loss, pace.loss_per_day) if pace is not None else loss
    eyed_possible = live * math.exp(-loss_possible * days_possible)
    return Projection(tank.id, live, length, days if on_course else None, eyed_on_course, max(eyed_possible, eyed_on_course))


@dataclass(frozen=True)
class Forecast:
    pace: Pace | None
    rows: tuple[Projection, ...]

    @property
    def on_course(self) -> float:
        return sum(p.eyed_on_course for p in self.rows)

    @property
    def possible(self) -> float:
        return sum(p.eyed_possible for p in self.rows)


def forecast_for(tanks: Sequence[TankFacts], cfg: Mapping) -> Forecast:
    pace = pace_batch(tanks, cfg)
    rows = [p for p in (project(t, pace, cfg) for t in tanks) if p is not None]
    return Forecast(pace, tuple(rows))
