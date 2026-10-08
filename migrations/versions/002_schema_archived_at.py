"""Archiving for schemas.

A schema that has produced extractions cannot be destroyed: `schema_id` and
`schema_version` are stamped on every extraction as the reproducibility record
(CLAUDE.md 3.8), and removing the row would leave finished results citing a
schema nobody can look up. But a customer who makes one by mistake has to be
able to get rid of it, or the product looks broken on the first afternoon.

So there are two operations, and this column is what separates them: `archived_at`
hides a schema and closes it to new work while keeping it resolvable, and a hard
purge stays available only while nothing references it at all.

Revision ID: 002
Revises: 001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("schemas", schema=None) as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("schemas", schema=None) as batch_op:
        batch_op.drop_column("archived_at")
