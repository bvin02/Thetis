"""Load every tank's current state from the database and run the rules over it."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, select

from app import config, models
from app.rules.assess import Assessment, LineAlert, assess, line_alert
from app.rules.series import BatchData, CheckData, day_of


def settings_for(hatchery: models.Hatchery | None) -> dict:
    """DEFAULTS, overridden by the hatchery's own settings."""
    cfg = dict(config.DEFAULTS)
    if hatchery is not None and hatchery.settings:
        cfg.update(hatchery.settings)
    return cfg


def check_data(check: models.Check) -> CheckData:
    return CheckData(
        id=check.id,
        sampled_at=check.sampled_at,
        live_est=check.live_est,
        pct_dead=check.pct_dead,
        pct_abnormal=check.pct_abnormal,
        mean_len_um=check.mean_len_um,
        cv=check.cv,
        gut=check.gut,
        temp_c=check.temp_c,
        ph=check.ph,
        omega_arag=check.omega_arag,
        do_mgl=check.do_mgl,
    )


def batch_data(batch: models.Batch) -> BatchData:
    return BatchData(spawn_date=batch.spawn_date, stocked=batch.stocked)


@dataclass
class TankState:
    tank: models.Tank
    room: models.Room
    line: models.Line | None
    batch: models.Batch | None = None  # the active batch, if any
    checks: list[models.Check] = field(default_factory=list)  # the active batch's, oldest first
    data: list[CheckData] = field(default_factory=list)
    assessment: Assessment | None = None
    level: str = "empty"
    alert: LineAlert | None = None
    all_batches: list[models.Batch] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.tank.id

    @property
    def line_id(self) -> str | None:
        return self.tank.line_id

    @property
    def active(self) -> bool:
        return self.batch is not None

    @property
    def kind(self) -> str:
        return self.room.kind

    @property
    def latest(self) -> models.Check | None:
        return self.checks[-1] if self.checks else None

    def day(self, now: datetime) -> int | None:
        return day_of(now, self.batch.spawn_date) if self.batch else None


@dataclass
class World:
    now: datetime
    hatchery: models.Hatchery | None
    cfg: dict
    rooms: dict[str, models.Room]
    lines: dict[str, models.Line]
    tanks: dict[str, TankState]
    alerts: dict[str, LineAlert]
    checks_by_batch: dict[int, list[models.Check]]

    @property
    def is_example(self) -> bool:
        return bool(self.hatchery and self.hatchery.is_example) or any(t.tank.is_example for t in self.tanks.values())


def load_world(session: Session, now: datetime | None = None) -> World:
    now = now or datetime.now()
    hatchery = session.get(models.Hatchery, 1)
    cfg = settings_for(hatchery)
    rooms = {r.id: r for r in session.exec(select(models.Room))}
    lines = {x.id: x for x in session.exec(select(models.Line))}
    tanks = sorted(session.exec(select(models.Tank)), key=lambda t: (rooms[t.room_id].kind == "setting", t.id))
    batches = list(session.exec(select(models.Batch).order_by(models.Batch.spawn_date)))

    checks_by_batch: dict[int, list[models.Check]] = defaultdict(list)
    for check in session.exec(select(models.Check).order_by(models.Check.sampled_at, models.Check.id)):
        checks_by_batch[check.batch_id].append(check)

    states: dict[str, TankState] = {}
    for tank in tanks:
        states[tank.id] = TankState(tank=tank, room=rooms[tank.room_id], line=lines.get(tank.line_id or ""))
    for batch in batches:
        state = states.get(batch.tank_id)
        if state is None:
            continue
        state.all_batches.append(batch)
        if batch.status == "active":
            state.batch = batch

    for state in states.values():
        if state.batch is None:
            continue
        state.checks = checks_by_batch.get(state.batch.id, [])
        state.data = [check_data(c) for c in state.checks]
        state.assessment = assess(state.data, batch_data(state.batch), state.kind, cfg)
        state.level = state.assessment.level

    alerts: dict[str, LineAlert] = {}
    for line_id in lines:
        on_line = {s.id: s.data for s in states.values() if s.line_id == line_id and s.active}
        alert = line_alert(line_id, on_line, now, cfg)
        if alert is not None:
            alerts[line_id] = alert
    for state in states.values():
        state.alert = alerts.get(state.line_id or "")

    return World(now=now, hatchery=hatchery, cfg=cfg, rooms=rooms, lines=lines, tanks=states, alerts=alerts,
                 checks_by_batch=checks_by_batch)
