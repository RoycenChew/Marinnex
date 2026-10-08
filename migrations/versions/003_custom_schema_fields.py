"""Per-version output configuration and user-defined fields.

Both columns are additive and default to empty, so every version already stored
compiles to exactly the prompt and contract it did before: a customer's pinned
integration cannot shift under them because this migration ran.

`field_config` is presentation only — alias, order, required, and the display
formats that reach exports and the screen but never the API. `custom_fields` is
the list a customer defined, each one sent to the existing extract task as one
more field with a description.

Revision ID: 003
Revises: 002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("schema_versions", schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            "field_config", sa.JSON(), nullable=False, server_default="{}",
        ))
        batch_op.add_column(sa.Column(
            "custom_fields", sa.JSON(), nullable=False, server_default="[]",
        ))


def downgrade() -> None:
    with op.batch_alter_table("schema_versions", schema=None) as batch_op:
        batch_op.drop_column("custom_fields")
        batch_op.drop_column("field_config")
