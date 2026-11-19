from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from backend.app.config import get_settings
from backend.app.db import models  # noqa: F401  (registers tables)


def make_engine(database_url: str) -> Engine:
    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        path = database_url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        else:  # one shared connection, so every thread sees the same in-memory database
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(database_url, **kwargs)


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    _add_missing_columns(engine)


def _add_missing_columns(engine: Engine) -> None:
    """Tiny forward-only migration: add columns that newer code expects (SQLite and Postgres)."""

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl_type = column.type.compile(dialect=engine.dialect)
                default = column.default.arg if column.default is not None and not callable(column.default.arg) else None
                literal = "''" if isinstance(default, str) else ("0" if isinstance(default, (int, bool)) else "NULL")
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type} DEFAULT {literal}'))


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = make_engine(get_settings().database_url)
    init_db(engine)
    return engine


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
