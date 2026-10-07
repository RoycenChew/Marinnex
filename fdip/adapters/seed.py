"""Seeding: the invoice template always, the dev account only outside live mode.

The template is data the product needs to work at all, so it is seeded on every
start and updated in place when its fields change. The dev user is a
convenience that must never exist in production, so it is gated on
`FDIP_DEV_SEED` and refused outright when the provider mode is live -- a known
password in a deployed system is not a convenience, it is the incident.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, insert, select, update

from fdip.adapters import ids, tables
from fdip.adapters.db import transaction
from fdip.adapters.keys import hash_password
from fdip.config import Settings
from fdip.domain.templates import (
    INVOICE_DESCRIPTION,
    TEMPLATE_VERSION,
    flatten,
)

INVOICE_TEMPLATE_ID = "tpl_invoice_v1"
"""Fixed rather than generated: the UI and the samples reference it by id, and a
fresh id on every seed would break both."""

DEV_EMAIL = "dev@fdip.local"
DEV_PASSWORD = "devpass"
DEV_PROJECT = "Default"


@dataclass(frozen=True)
class SeedResult:
    template_id: str
    user_id: str | None = None
    project_id: str | None = None


def template_payload() -> list[dict[str, object]]:
    """The template's fields as the API publishes them."""
    return [
        {
            "path": spec.path,
            "label": spec.label,
            "type": spec.kind,
            "description": spec.description,
            "required_default": spec.required_default,
            "is_array": spec.is_array,
            "enum": list(spec.enum),
            "money": spec.money,
            "grounding": spec.grounding,
        }
        for spec in flatten()
    ]


def seed(engine: Engine, settings: Settings) -> SeedResult:
    fields = template_payload()
    with transaction(engine) as connection:
        existing = connection.execute(
            select(tables.schema_templates).where(
                tables.schema_templates.c.id == INVOICE_TEMPLATE_ID
            )
        ).mappings().first()
        if existing is None:
            connection.execute(insert(tables.schema_templates).values(
                id=INVOICE_TEMPLATE_ID,
                document_type="invoice",
                version=TEMPLATE_VERSION,
                name="Malaysian supplier invoice",
                description=INVOICE_DESCRIPTION,
                fields=fields,
            ))
        else:
            # Updated in place: the template is FDIP's catalogue, and a schema
            # version has already copied the field list it depends on, so
            # changing the template cannot change a pinned extraction.
            connection.execute(
                update(tables.schema_templates)
                .where(tables.schema_templates.c.id == INVOICE_TEMPLATE_ID)
                .values(fields=fields, description=INVOICE_DESCRIPTION,
                        version=TEMPLATE_VERSION)
            )

        if not settings.dev_seed or settings.provider_mode == "live":
            return SeedResult(template_id=INVOICE_TEMPLATE_ID)

        user = connection.execute(
            select(tables.users).where(tables.users.c.email == DEV_EMAIL)
        ).mappings().first()
        if user is not None:
            project = connection.execute(
                select(tables.projects).where(
                    tables.projects.c.owner_id == user["id"]
                )
            ).mappings().first()
            return SeedResult(
                INVOICE_TEMPLATE_ID, str(user["id"]),
                str(project["id"]) if project else None,
            )

        user_id = ids.user_id()
        connection.execute(insert(tables.users).values(
            id=user_id, email=DEV_EMAIL,
            # The brief fixes this password; it is below the registration
            # minimum, and this is the only caller allowed past it.
            password_hash=hash_password(DEV_PASSWORD, enforce_policy=False),
            is_active=True,
        ))
        project_id = ids.project_id()
        connection.execute(insert(tables.projects).values(
            id=project_id, owner_id=user_id, name=DEV_PROJECT,
            allowed_providers=["deepseek", "mock"], monthly_page_quota=10000,
        ))
        return SeedResult(INVOICE_TEMPLATE_ID, user_id, project_id)


__all__ = [
    "DEV_EMAIL",
    "DEV_PASSWORD",
    "DEV_PROJECT",
    "INVOICE_TEMPLATE_ID",
    "SeedResult",
    "seed",
    "template_payload",
]
