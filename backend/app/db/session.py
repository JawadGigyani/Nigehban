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
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(database_url, **kwargs)


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = make_engine(get_settings().database_url)
    init_db(engine)
    return engine


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
