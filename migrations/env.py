"""Alembic environment.

The URL comes from `FDIP_DB_URL` rather than from `alembic.ini`, so a migration
can never be run against a different database than the application reads. That
mistake is silent and expensive, and leaving the ini value blank makes it
impossible.

`render_as_batch` is on because SQLite cannot ALTER a column: without it, any
future migration that changes a column fails at the point it is needed rather
than at the point it is written.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fdip.adapters.tables import metadata  # noqa: E402
from fdip.config import load_settings  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _url() -> str:
    url = os.environ.get("FDIP_DB_URL")
    if url:
        return url
    return load_settings().db_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(), target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _url()
    if url.startswith("sqlite") and ":memory:" not in url:
        Path(url.split("///", 1)[-1]).resolve().parent.mkdir(
            parents=True, exist_ok=True
        )
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
