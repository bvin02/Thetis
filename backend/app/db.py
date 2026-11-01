"""SQLite engine and sessions. The database lives in the data folder."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app import config

_engine: Engine | None = None
_engine_path: str | None = None


def get_engine() -> Engine:
    """One engine per database path, created on first use."""
    global _engine, _engine_path
    path = str(config.db_path())
    if _engine is None or _engine_path != path:
        config.data_dir().mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30})
        _engine_path = path
    return _engine


def init_db() -> None:
    from app import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(get_engine())


def drop_all() -> None:
    from app import models  # noqa: F401

    SQLModel.metadata.drop_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
