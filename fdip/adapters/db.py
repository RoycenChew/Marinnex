"""Engine construction: SQLite in WAL mode, which is not the default.

WAL matters because the API and the worker are two processes against one file.
Without it a write in the worker blocks every read in the API, and the UI
polling `GET /documents/{id}` every two seconds would collide with the job it is
polling about. `busy_timeout` is the other half: without it a collision is an
immediate `database is locked` rather than a short wait.

`foreign_keys` is off by default in SQLite, so the `ondelete="CASCADE"` in
`tables.py` would silently do nothing. Turning it on per connection is the only
place it can be done.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection

from fdip.adapters.tables import metadata

_PRAGMAS = (
    ("journal_mode", "WAL"),
    ("synchronous", "NORMAL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
)


def _configure(dbapi_connection: Any, _record: Any) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        for name, value in _PRAGMAS:
            cursor.execute("PRAGMA %s=%s" % (name, value))
    finally:
        cursor.close()


def create_db_engine(url: str) -> Engine:
    if url.startswith("sqlite") and ":memory:" not in url:
        # Create the directory rather than failing on "unable to open database
        # file", which says nothing about the cause.
        path = url.split("///", 1)[-1]
        if path:
            Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, future=True, pool_pre_ping=True)
    event.listen(engine, "connect", _configure)
    return engine


def create_all(engine: Engine) -> None:
    """Create the schema directly, for tests and for a first local run.

    Alembic owns migrations; this exists so a test does not need a migration
    subprocess. `tests/test_migration.py` asserts the two agree.
    """
    metadata.create_all(engine)


@contextmanager
def transaction(engine: Engine) -> Iterator[Connection]:
    """One unit of work. Commits on success, rolls back on any exception."""
    with engine.begin() as connection:
        yield connection


__all__ = ["create_all", "create_db_engine", "transaction"]
