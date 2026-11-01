"""Database tables (SPEC §9). Datetimes are naive local time, as everywhere in the app."""
from __future__ import annotations

from datetime import date

from pydantic import NaiveDatetime
from sqlalchemy import JSON, Column, String
from sqlmodel import Field, SQLModel


def _json_field(default=None):
    return Field(default=default, sa_column=Column(JSON, nullable=True))


class Hatchery(SQLModel, table=True):
    __tablename__ = "hatchery"
    id: int | None = Field(default=1, primary_key=True)
    name: str
    species: str = "pacific_oyster"
    user_name: str
    user_initials: str
    user_role: str
    settings: dict | None = _json_field()
    is_example: bool = False


class Room(SQLModel, table=True):
    __tablename__ = "room"
    id: str = Field(primary_key=True)
    name: str
    kind: str = "larval"  # larval | setting
    label_xy: list | None = _json_field()
    caption: str | None = None


class Line(SQLModel, table=True):
    __tablename__ = "line"
    id: str = Field(primary_key=True)
    name: str
    card_xy: list | None = _json_field()


class Tank(SQLModel, table=True):
    __tablename__ = "tank"
    id: str = Field(primary_key=True)
    room_id: str = Field(foreign_key="room.id", index=True)
    line_id: str | None = Field(default=None, foreign_key="line.id", index=True)
    shape: str = "circle"  # circle | rect
    geom: dict | None = _json_field()  # {cx, cy, r} or {x, y, w, h}
    volume_l: float = 0
    status: str = "empty"  # active | cleaning | empty
    is_example: bool = False


class Batch(SQLModel, table=True):
    __tablename__ = "batch"
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True)
    tank_id: str = Field(foreign_key="tank.id", index=True)
    species: str = "pacific_oyster"
    spawn_date: date
    stocked: int
    status: str = "active"  # active | closed
    outcome: str | None = None  # moved_to_setting | harvested | crashed | discarded
    closed_on: date | None = None
    note: str | None = None
    is_example: bool = False


class Check(SQLModel, table=True):
    __tablename__ = "checks"
    id: int | None = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    tank_id: str = Field(foreign_key="tank.id", index=True)
    sampled_at: NaiveDatetime = Field(index=True)
    source: str = "photo"  # photo | manual

    n_live: int = 0
    n_abnormal: int = 0
    n_dead: int = 0
    n_unsure: int = 0
    pct_dead: float | None = None
    pct_abnormal: float | None = None
    mean_len_um: float | None = None
    sd_len_um: float | None = None
    cv: float | None = None
    gut: float | None = None
    stage: str | None = None
    hist: list | None = _json_field()
    live_est: float | None = None
    bucket_l: float | None = None
    concentration: float | None = None
    photo_volume_ml: float | None = None

    temp_c: float | None = None
    salinity_ppt: float | None = None
    ph: float | None = None
    omega_arag: float | None = None
    do_mgl: float | None = None
    notes: str | None = None

    # Risk snapshot at save time: proves later what the system said before a crash
    level: str | None = None
    pattern: str | None = None
    signals: list | None = _json_field()
    growth_um_day: float | None = None
    loss_per_day: float | None = None
    survival: float | None = None

    engine_version: str | None = None
    rules_version: str | None = None
    created_by: str | None = None
    is_example: bool = False


class Photo(SQLModel, table=True):
    __tablename__ = "photo"
    id: int | None = Field(default=None, primary_key=True)
    check_id: int = Field(foreign_key="checks.id", index=True)
    path: str = ""  # relative to the data folder
    width: int = 0
    height: int = 0
    um_per_px: float | None = None
    calibration: str = "none"  # grid | preset | manual | none
    grid_spacing_px: float | None = None
    volume_ml: float | None = None
    engine_version: str | None = None
    synthetic: bool = False
    source_name: str | None = None
    upload_token: str | None = Field(default=None, index=True)  # saving the same upload twice must not duplicate


class Detection(SQLModel, table=True):
    __tablename__ = "detection"
    id: int | None = Field(default=None, primary_key=True)
    photo_id: int = Field(foreign_key="photo.id", index=True)
    number: int = 0  # the id shown in the UI ("Larva 12"), unique within a photo
    cx: float = 0
    cy: float = 0
    contour: list | None = _json_field()
    length_px: float = 0
    length_um: float | None = None
    area_px: float = 0
    solidity: float = 1.0
    defect: float = 0.0
    hollowness: float = 1.5
    gut: float | None = None
    interior: float = 0.0
    # Column "cls" (SPEC §9). The attribute has another name because SQLModel's constructor reserves `cls`.
    larva_cls: str = Field(default="live", sa_column=Column("cls", String, nullable=False))
    auto_cls: str = "live"
    unsure: bool = False
    unsure_reason: str | None = None
    clump_n: int = 1
    touches_edge: bool = False
    source: str = "auto"  # auto | corrected | manual
    claude: dict | None = _json_field()


class Decision(SQLModel, table=True):
    __tablename__ = "decision"
    id: int | None = Field(default=None, primary_key=True)
    scope: str = "tank"  # tank | line
    tank_id: str | None = Field(default=None, foreign_key="tank.id", index=True)
    line_id: str | None = Field(default=None, foreign_key="line.id", index=True)
    check_id: int | None = Field(default=None, foreign_key="checks.id")
    action: str
    status: str = Field(default="pending", index=True)  # pending | approved | dismissed
    created_at: NaiveDatetime
    decided_at: NaiveDatetime | None = None
    decided_by: str | None = None
    note: str | None = None
    is_example: bool = False


class ClaudeCall(SQLModel, table=True):
    __tablename__ = "claude_call"
    id: int | None = Field(default=None, primary_key=True)
    kind: str  # opinion | explain | analysis | ask
    input_hash: str = Field(index=True)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: NaiveDatetime
    result: dict | None = _json_field()
    error: str | None = None
