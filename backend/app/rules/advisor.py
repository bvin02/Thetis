"""Crash risks and yield suggestions, from every tank's numbers (SPEC §16). Pure functions.

The rules find these and do the arithmetic, so the page works and can be trusted with no API key. Claude reads the
result and adds what rules can't see.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field

from app.rules.actions import PlannedAction, line_number
from app.rules.assess import LEVEL_RANK, LineAlert
from app.rules.facts import Forecast, Pace, TankFacts, batch_loss_per_day, elapsed_days, project
from app.rules.series import BatchData as _BatchData
from app.rules.series import CheckData, rates_at
from app.rules.signals import SEVERITY_RANK
from app.rules.text import FORECAST, PATTERN_TITLE, fmt_count, fmt_pct, fmt_trim, round_half_up

SOURCE_BARTON = "Barton et al. 2015, Oceanography 28(2)"
SOURCE_FAO_DISEASE = "FAO Fisheries Technical Paper 471, section 5.3.5"
SOURCE_FAO_HUSBANDRY = "FAO Fisheries Technical Paper 471, section 5.1.3"
SOURCE_FAO_SETTLEMENT = "FAO Fisheries Technical Paper 471, section 5.4.3"

WHY: dict[str, tuple[str, str | None]] = {
    "corrosive": (
        "Larvae build their shells from carbonate in the water, and low Ω makes that hard. Abnormal shells rise first, then "
        "losses follow. Research at Whiskey Creek Hatchery put the minimum for a viable batch at Ω 1.7.",
        SOURCE_BARTON,
    ),
    "corrosive_early": (
        "Larvae look normal so far, but they build their shells from carbonate in the water, and low Ω makes that hard. Fixing "
        "the water now costs far less than losing the batch later.",
        SOURCE_BARTON,
    ),
    "bacterial": (
        "Dead larvae jumped while guts emptied and growth stalled, and the water is fine. Outbreaks like this move fast in "
        "warm larval tanks: a whole tank can go in 1–3 days, and shared gear can carry it to the next tank.",
        None,
    ),
    "underfed": (
        "Slow growth with light guts means larvae aren't eating enough. It can be a feed problem or the first sign of "
        "something worse: larvae often stop grazing the day before a mass die-off.",
        SOURCE_FAO_DISEASE,
    ),
    "splitting": (
        "A widening size spread means part of the batch has stopped keeping up. Slow larvae compete for feed, and few of them "
        "reach the eyed stage.",
        SOURCE_FAO_HUSBANDRY,
    ),
    "temperature": (
        "Larvae feed and grow best near their target temperature. Drifting off it slows the batch, and warmer water also "
        "speeds up bacteria.",
        None,
    ),
    "oxygen": (
        "Low oxygen stresses larvae within hours. It usually means failing aeration or a heavy bacterial load, and either can "
        "turn into losses quickly.",
        None,
    ),
    "unexplained_loss": (
        "The count fell faster than expected with nothing else showing yet. That could be sampling noise or the start of a "
        "crash, and a second sample tells you which.",
        None,
    ),
    "early_warning": (
        "One reading moved the wrong way. Alone it may mean nothing, but crashes often start this way, so it's worth a closer "
        "look at the next drain.",
        None,
    ),
}


# ---------------------------------------------------------------- evidence


@dataclass(frozen=True)
class Tile:
    """One reading over time: a small chart with the latest value."""

    key: str
    label: str
    tank_id: str
    points: tuple[tuple[float, float], ...]
    point_texts: tuple[str, ...]
    now_text: str
    target_text: str
    severity: str | None
    guide: float | None
    summary: str  # the same thing as a sentence, for screen readers


_LABEL = {
    "dead": "Dead larvae", "abnormal": "Abnormal shells", "growth": "Growth", "gut": "Gut fullness",
    "spread": "Size spread (CV)", "omega": "Ω aragonite", "ph": "pH", "temp": "Temperature", "oxygen": "Oxygen",
    "loss": "Loss per day", "density": "Density",
}


def _reading(key: str) -> Callable[[CheckData], float | None]:
    return {
        "dead": lambda c: c.pct_dead, "abnormal": lambda c: c.pct_abnormal, "gut": lambda c: c.gut, "spread": lambda c: c.cv,
        "omega": lambda c: c.omega_arag, "ph": lambda c: c.ph, "temp": lambda c: c.temp_c, "oxygen": lambda c: c.do_mgl,
    }[key]


def _value_text(key: str, value: float) -> str:
    if key in ("dead", "abnormal"):
        return fmt_pct(value)
    if key == "growth":
        return f"{value:.1f} µm/day"
    if key in ("gut", "spread", "ph"):
        return f"{value:.2f}"
    if key == "omega":
        return f"{value:.1f}"
    if key == "temp":
        return f"{value:.1f} °C"
    if key == "oxygen":
        return f"{value:.1f} mg/L"
    if key == "loss":
        return f"{value * 100:.1f}%"
    raise KeyError(key)


def _target(key: str, cfg: Mapping) -> tuple[str, float | None]:
    if key == "dead":
        return f"under {fmt_trim(cfg['dead_pct'][0])}%", cfg["dead_pct"][0]
    if key == "abnormal":
        return f"under {fmt_trim(cfg['abnormal_pct'][0])}%", cfg["abnormal_pct"][0]
    if key == "growth":
        return f"{fmt_trim(cfg['expected_growth_um_day'])} µm/day expected", cfg["expected_growth_um_day"]
    if key == "gut":
        return f"above {fmt_trim(cfg['gut_index'][0])}", cfg["gut_index"][0]
    if key == "spread":
        return f"under {fmt_trim(cfg['spread_cv'][0])}", cfg["spread_cv"][0]
    if key == "omega":
        return f"target ≥ {fmt_trim(cfg['omega_arag'][0])}", cfg["omega_arag"][0]
    if key == "ph":
        return f"target ≥ {fmt_trim(cfg['ph'][0])}", cfg["ph"][0]
    if key == "temp":
        return f"target {fmt_trim(cfg['target_temp_c'])} °C", cfg["target_temp_c"]
    if key == "oxygen":
        return f"target ≥ {fmt_trim(cfg['do_mgl'][0])} mg/L", cfg["do_mgl"][0]
    raise KeyError(key)


def _points(tank: TankFacts, key: str, cfg: Mapping) -> list[tuple[float, float]]:
    assert tank.spawn_date is not None
    points: list[tuple[float, float]] = []
    if key == "growth":
        batch = _BatchData(tank.spawn_date, tank.stocked)
        for index, check in enumerate(tank.checks):
            growth = rates_at(tank.checks, index, batch, tank.kind, cfg).growth_um_day
            if growth is not None:
                points.append((round(elapsed_days(check.sampled_at, tank.spawn_date, cfg), 2), round(growth, 2)))
        return points
    read = _reading(key)
    for check in tank.checks:
        value = read(check)
        if value is not None:
            points.append((round(elapsed_days(check.sampled_at, tank.spawn_date, cfg), 2), round(value, 3)))
    return points


def tile_for(tank: TankFacts, key: str, cfg: Mapping) -> Tile | None:
    points = _points(tank, key, cfg)
    if not points:
        return None
    severity = tank.assessment.sev(key) if tank.assessment else None
    target_text, guide = _target(key, cfg)
    now = _value_text(key, points[-1][1])
    history = ", ".join(_value_text(key, p[1]) for p in points)
    return Tile(
        key=key, label=_LABEL[key], tank_id=tank.id, points=tuple(points), point_texts=tuple(_value_text(key, p[1]) for p in points),
        now_text=now, target_text=target_text, severity=severity, guide=guide,
        summary=f"{_LABEL[key]} on {tank.id} at each check: {history}. {target_text}.",
    )


def _signal_keys(tank: TankFacts) -> list[str]:
    """This tank's warning signs, worst first."""
    if tank.assessment is None:
        return []
    signals = [s for s in tank.assessment.signals if s.key != "loss"]
    signals.sort(key=lambda s: -SEVERITY_RANK[s.severity])
    return [s.key for s in signals]


def _tiles(tank: TankFacts, keys: Iterable[str], cfg: Mapping, limit: int = 3) -> list[Tile]:
    tiles: list[Tile] = []
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        tile = tile_for(tank, key, cfg)
        if tile is not None:
            tiles.append(tile)
        if len(tiles) == limit:
            break
    return tiles


# ---------------------------------------------------------------- crash risks


@dataclass(frozen=True)
class Risk:
    id: str
    level: str
    title: str
    tank_ids: tuple[str, ...]
    line_id: str | None
    at_stake: float
    forecast: str
    why: str
    source: str | None
    tiles: tuple[Tile, ...]
    outlook: str | None
    plans: tuple[PlannedAction, ...] = field(default=())

    def to_json(self) -> dict:
        view = asdict(self)
        view.pop("plans")
        view["at_stake_text"] = fmt_count(self.at_stake)
        return view


def _tank_has_water(tank: TankFacts) -> int:
    return sum(1 for c in tank.checks if c.ph is not None) * 2 + sum(1 for c in tank.checks if c.omega_arag is not None)


def _outlook(tanks: Sequence[TankFacts], pace: Pace | None, cfg: Mapping) -> str | None:
    """What the forecast says for these tanks, if nothing changes and if they recover."""
    projections = [p for p in (project(t, pace, cfg) for t in tanks) if p is not None]
    if not projections:
        return None
    on_course = sum(p.eyed_on_course for p in projections)
    possible = sum(p.eyed_possible for p in projections)
    if possible <= 0 or pace is None:
        return None
    many = len(projections) > 1
    if on_course <= 0:
        who = "none of these tanks reach" if many else "this tank won't reach"
        lead = f"At today's rates, {who} the eyed stage within {cfg['project_max_days']} days."
    else:
        lead = f"At today's rates, about {fmt_count(on_course)} reach the eyed stage."
    recovery = "they recover and track" if many else "it recovers and tracks"
    return f"{lead} If {recovery} {pace.tank_id}, about {fmt_count(possible)} could."


def _line_risk(line_id: str, alert: LineAlert, on_line: Sequence[TankFacts], pace: Pace | None, plans_for, cfg: Mapping) -> Risk:
    worst = max(on_line, key=lambda t: LEVEL_RANK[t.level])
    reader = max(on_line, key=lambda t: (_tank_has_water(t), t.id))
    most_abnormal = max(on_line, key=lambda t: (t.latest.pct_abnormal or 0) if t.latest else 0)
    tiles = _tiles(reader, ("ph", "omega"), cfg, limit=2) + _tiles(most_abnormal, ("abnormal",), cfg, limit=1)
    plans: list[PlannedAction] = []
    for tank in on_line:
        for plan in plans_for(tank):
            if plan.scope == "line" and plan not in plans:
                plans.append(plan)
    why, source = WHY["corrosive"]
    return Risk(
        id=f"line-{line_id}",
        level=worst.level,
        title=f"Line {line_number(line_id)} water is corrosive",
        tank_ids=tuple(t.id for t in on_line),
        line_id=line_id,
        at_stake=sum(t.live or 0 for t in on_line),
        forecast=FORECAST[worst.level],
        why=why,
        source=source,
        tiles=tuple(tiles),
        outlook=_outlook(on_line, pace, cfg),
        plans=tuple(plans),
    )


def _tank_risk(tank: TankFacts, pace: Pace | None, plans_for, cfg: Mapping) -> Risk:
    pattern = tank.pattern or "early_warning"
    why, source = WHY.get(pattern, WHY["early_warning"])
    if pattern == "underfed" and tank.assessment is not None and not tank.assessment.at_least("gut"):
        why = ("Growth has slowed even though guts still look normal, so this may be more than a feed problem. Larvae often stop "
               "grazing the day before a mass die-off, so a light gut at the next check would be a serious sign.")
    return Risk(
        id=f"tank-{tank.id}",
        level=tank.level,
        title=f"{tank.id}: {PATTERN_TITLE[pattern][0].lower()}{PATTERN_TITLE[pattern][1:]}",
        tank_ids=(tank.id,),
        line_id=tank.line_id,
        at_stake=tank.live or 0,
        forecast=FORECAST[tank.level],
        why=why,
        source=source,
        tiles=tuple(_tiles(tank, _signal_keys(tank), cfg)),
        outlook=_outlook([tank], pace, cfg),
        plans=tuple(plans_for(tank)),
    )


WATER_PATTERNS = ("corrosive", "corrosive_early")


def crash_risks(tanks: Sequence[TankFacts], alerts: Mapping[str, LineAlert], pace: Pace | None,
                plans_for: Callable[[TankFacts], Iterable[PlannedAction]], cfg: Mapping) -> list[Risk]:
    """What could turn into a crash, worst first. A line alert is one risk, whichever tanks it touches."""
    risks: list[Risk] = []
    for line_id, alert in alerts.items():
        on_line = [t for t in tanks if t.line_id == line_id and t.active]
        if on_line:
            risks.append(_line_risk(line_id, alert, on_line, pace, plans_for, cfg))
    for tank in tanks:
        if not tank.active or tank.level in ("ok", "empty"):
            continue
        if tank.line_id in alerts and tank.pattern in WATER_PATTERNS:
            continue
        if tank.pattern == "splitting" and tank.level == "watch":
            continue  # worth acting on, but it costs yield rather than threatening a crash
        risks.append(_tank_risk(tank, pace, plans_for, cfg))
    risks.sort(key=lambda r: (-LEVEL_RANK[r.level], -r.at_stake, r.id))
    return risks


def larvae_at_risk(risks: Iterable[Risk], tanks: Mapping[str, TankFacts]) -> float:
    """Each tank counts once, even if two risks touch it."""
    ids = {tank_id for risk in risks for tank_id in risk.tank_ids}
    return sum(tanks[tank_id].live or 0 for tank_id in ids if tank_id in tanks)


# ---------------------------------------------------------------- yield suggestions


@dataclass(frozen=True)
class Opportunity:
    id: str
    kind: str  # ready_to_set | density | slow_pace
    title: str
    chip: str
    tank_ids: tuple[str, ...]
    why: str
    source: str | None
    stat_text: str
    stat_label: str
    gain: float  # extra eyed larvae if it works; 0 when not estimated
    tiles: tuple[Tile, ...]
    plans: tuple[PlannedAction, ...]

    def to_json(self) -> dict:
        view = asdict(self)
        view.pop("plans")
        return view


def _ready_to_set(tank: TankFacts, free_setting: Sequence[TankFacts], cfg: Mapping) -> Opportunity | None:
    length = tank.length_um
    if length is None or length < cfg["eyed_um"] or tank.level not in ("ok", "watch"):
        return None
    loss = tank.assessment.loss_per_day if tank.assessment else None
    live = tank.live or 0
    daily = max(live * loss, 0.0) if loss else 0.0  # a count that rose is noise, not a negative loss
    opening = f"{tank.id} averages {round_half_up(length)} µm, past the {fmt_trim(cfg['eyed_um'])} µm eyed stage."
    if not free_setting:
        ready = " No setting tank is free yet."
    elif free_setting[0].status == "cleaning":
        ready = f" {free_setting[0].id} is free once it's clean."
    else:
        ready = f" {free_setting[0].id} is empty."
    cost = "Hatcheries usually start settlement once half a batch is eyed"
    cost += f", and this tank is losing about {fmt_count(daily)} a day." if daily > 0 else "."
    return Opportunity(
        id=f"yield-{tank.id}-setting",
        kind="ready_to_set",
        title=f"Move {tank.id}'s largest larvae to setting",
        chip="Move to setting",
        tank_ids=(tank.id,),
        why=f"{opening}{ready} {cost}",
        source=SOURCE_FAO_SETTLEMENT,
        stat_text=fmt_count(daily) if daily > 0 else f"{round_half_up(length)} µm",
        stat_label="larvae lost per day while waiting" if daily > 0 else "average shell length",
        gain=0.0,
        tiles=(),
        plans=(PlannedAction("tank", "move_to_setting", tank.id, None),),
    )


def _overstocked(tank: TankFacts, cfg: Mapping) -> Opportunity | None:
    density = tank.density_per_l
    limit = cfg["density_limit_per_l"]
    if density is None or density <= limit or tank.level not in ("ok", "watch"):
        return None
    return Opportunity(
        id=f"yield-{tank.id}-density",
        kind="density",
        title=f"Split {tank.id}: it's stocked too densely",
        chip="Split tank",
        tank_ids=(tank.id,),
        why=(f"{tank.id} holds {round_half_up(density):,} larvae per L. FAO's manual gives "
             f"{round_half_up(cfg['density_range_low_per_l']):,} to {round_half_up(limit):,} per L "
             "for oyster D-larvae, and growth and survival are generally better at lower densities."),
        source=SOURCE_FAO_HUSBANDRY,
        stat_text=f"{round_half_up(density):,}",
        stat_label=f"larvae per L, against {round_half_up(limit):,}",
        gain=0.0,
        tiles=(),
        plans=(PlannedAction("tank", "split_tank", tank.id, None),),
    )


def _slow_pace(tank: TankFacts, pace: Pace | None, plans_for, cfg: Mapping) -> Opportunity | None:
    """A batch losing larvae much faster than the best batch in the same plant, with no crash pattern to explain it."""
    if pace is None or tank.id == pace.tank_id or tank.level not in ("ok", "watch"):
        return None
    if tank.pattern not in (None, "splitting") or len(tank.checks) < cfg["pace_min_checks"]:
        return None
    if tank.length_um is None or tank.length_um >= cfg["eyed_um"]:
        return None
    loss = batch_loss_per_day(tank, cfg)
    if loss is None or pace.loss_per_day <= 0 or loss / pace.loss_per_day < cfg["slow_pace_ratio"]:
        return None
    projection = project(tank, pace, cfg)
    gain = projection.gain if projection else 0.0
    ratio = loss / pace.loss_per_day
    planned = [p for p in plans_for(tank) if p.action == "screen"] or [PlannedAction("tank", "review_handling", tank.id, None)]
    sentence = (f"{tank.id} has lost {loss * 100:.1f}% a day since stocking, against {pace.loss_per_day * 100:.1f}% for {pace.tank_id}. ")
    if tank.pattern == "splitting":
        why, source = WHY["splitting"]
        sentence += why
    else:
        source = None
        sentence += "Nothing in the readings explains the gap yet, so start with how the two tanks are handled."
    return Opportunity(
        id=f"yield-{tank.id}-pace",
        kind="slow_pace",
        title=f"{tank.id} is losing larvae {ratio:.1f}× as fast as {pace.tank_id}",
        chip="Screen and cull" if tank.pattern == "splitting" else "Compare handling",
        tank_ids=(tank.id,),
        why=sentence,
        source=source,
        stat_text=f"+{fmt_count(gain)}",
        stat_label=f"eyed larvae at {pace.tank_id}'s pace",
        gain=gain,
        tiles=tuple(_tiles(tank, ("spread", "gut"), cfg, limit=1)),
        plans=tuple(planned),
    )


def yield_opportunities(tanks: Sequence[TankFacts], pace: Pace | None, plans_for: Callable[[TankFacts], Iterable[PlannedAction]],
                        cfg: Mapping) -> list[Opportunity]:
    """Where this hatchery can get more larvae through. Time-critical moves first, then by size of the gain."""
    active = [t for t in tanks if t.active and t.kind == "larval"]
    free_setting = sorted((t for t in tanks if t.kind == "setting" and not t.active), key=lambda t: (t.status != "empty", t.id))
    found: list[Opportunity] = []
    for tank in active:
        for candidate in (_ready_to_set(tank, free_setting, cfg), _overstocked(tank, cfg), _slow_pace(tank, pace, plans_for, cfg)):
            if candidate is not None:
                found.append(candidate)
    rank = {"ready_to_set": 0, "slow_pace": 1, "density": 2}
    found.sort(key=lambda o: (rank[o.kind], -o.gain, o.id))
    return found


# ---------------------------------------------------------------- the forecast table


def forecast_json(forecast: Forecast, tanks: Mapping[str, TankFacts], cfg: Mapping) -> dict:
    rows = []
    for row in sorted(forecast.rows, key=lambda p: (-p.gain, p.tank_id)):
        tank = tanks[row.tank_id]
        if row.days_to_eyed == 0:
            when = "Ready now"
        elif row.days_to_eyed is None:
            when = "Not on course"
        else:
            days = round_half_up(row.days_to_eyed)
            when = f"{days} {'day' if days == 1 else 'days'}"
        rows.append({
            "tank_id": row.tank_id,
            "level": tank.level,
            "stage": tank.assessment.stage if tank.assessment else None,
            "day": tank.day,
            "live": row.live,
            "live_text": fmt_count(row.live),
            "when_text": when,
            "on_course": row.eyed_on_course,
            "on_course_text": fmt_count(row.eyed_on_course) if row.eyed_on_course > 0 else "0",
            "possible": row.eyed_possible,
            "possible_text": fmt_count(row.eyed_possible),
            "gain": row.gain,
            "gain_text": f"+{fmt_count(row.gain)}" if row.gain >= cfg["forecast_min_gain"] else "—",
        })
    pace = forecast.pace
    return {
        "pace": {"tank_id": pace.tank_id, "loss_pct_per_day": round(pace.loss_per_day * 100, 1)} if pace else None,
        "rows": rows,
        "on_course": forecast.on_course,
        "on_course_text": fmt_count(forecast.on_course),
        "possible": forecast.possible,
        "possible_text": fmt_count(forecast.possible),
        "gain_text": f"+{fmt_count(forecast.possible - forecast.on_course)}",
    }


__all__ = [
    "Forecast", "Opportunity", "Risk", "Tile", "crash_risks", "forecast_json", "larvae_at_risk", "tile_for", "yield_opportunities",
]
