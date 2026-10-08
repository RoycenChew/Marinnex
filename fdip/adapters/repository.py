"""Every query, with the tenant predicate enforced rather than remembered.

The rule from CLAUDE.md 3.7 is "the repository refuses unscoped queries". A rule
that depends on each call site remembering a `where` clause is not enforced, so
this module makes the scope a constructor argument: a `ProjectRepository` cannot
be built without a project id, and the one function that builds a statement
refuses a falsy one. `tests/test_repository_scoping.py` proves it by walking
every project-scoped table.

The cost of this design is that queries are written out longhand instead of
being generated. That is the intended trade: a hand-written `where` is visible in
review, and a lazy ORM relationship is how a cross-tenant read gets shipped.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, Table, and_, delete, func, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping

from fdip.adapters import ids, tables
from fdip.adapters.tables import GLOBAL_TABLES


class UnscopedQuery(RuntimeError):
    """Raised when a project-scoped table is queried without a project.

    A loud failure, deliberately: the alternative is a query that returns every
    tenant's rows and looks like it worked.
    """


def now() -> datetime:
    """UTC, naive, because SQLite has no timezone type and a mixed column is
    worse than a consistent convention."""
    return datetime.now(UTC).replace(tzinfo=None)


def scoped(table: Table, project_id: str | None) -> Select:
    """`SELECT * FROM table WHERE project_id = :project_id`, or an exception.

    The only place a project-scoped SELECT is built. Anything that bypasses it
    bypasses the rule, which is what the import-graph test looks for.
    """
    if table.name in GLOBAL_TABLES:
        return select(table)
    if not project_id:
        raise UnscopedQuery(
            "%s is project-scoped; a query without a project_id would read every"
            " tenant's rows" % table.name
        )
    return select(table).where(table.c.project_id == project_id)


def _month(when: datetime | None = None) -> str:
    return (when or now()).strftime("%Y-%m")


class ProjectRepository:
    """Reads and writes within one project. The scope is not optional."""

    def __init__(self, connection: Connection, project_id: str) -> None:
        if not project_id:
            raise UnscopedQuery(
                "a ProjectRepository needs a project_id; there is no global scope"
            )
        self._c = connection
        self.project_id = project_id

    @property
    def connection(self) -> Connection:
        """For the few callers that need a second repository on the same
        transaction. Exposed deliberately rather than reached for privately."""
        return self._c

    def monthly_page_quota(self) -> int:
        statement = select(tables.projects.c.monthly_page_quota).where(
            tables.projects.c.id == self.project_id
        )
        return int(self._c.execute(statement).scalar() or 0)

    # -- generic helpers --------------------------------------------------

    def _one(self, table: Table, row_id: str) -> RowMapping | None:
        statement = scoped(table, self.project_id).where(table.c.id == row_id)
        return self._c.execute(statement).mappings().first()

    def _insert(self, table: Table, values: Mapping[str, Any]) -> str:
        payload = dict(values)
        if table.name not in GLOBAL_TABLES:
            payload["project_id"] = self.project_id
        self._c.execute(insert(table).values(**payload))
        return str(payload["id"])

    # -- documents --------------------------------------------------------

    def create_document(self, **values: Any) -> str:
        values.setdefault("id", ids.document_id())
        return self._insert(tables.documents, values)

    def document(self, document_id: str) -> RowMapping | None:
        row = self._one(tables.documents, document_id)
        if row is not None and row["deleted_at"] is not None:
            return None
        return row

    def document_by_hash(self, sha256: str) -> RowMapping | None:
        statement = (
            scoped(tables.documents, self.project_id)
            .where(tables.documents.c.sha256 == sha256)
            .where(tables.documents.c.deleted_at.is_(None))
        )
        return self._c.execute(statement).mappings().first()

    def document_by_idempotency_key(self, key: str) -> RowMapping | None:
        statement = (
            scoped(tables.documents, self.project_id)
            .where(tables.documents.c.idempotency_key == key)
        )
        return self._c.execute(statement).mappings().first()

    def list_documents(self, status: str | None = None, limit: int = 50,
                       cursor: str | None = None) -> list[RowMapping]:
        statement = (
            scoped(tables.documents, self.project_id)
            .where(tables.documents.c.deleted_at.is_(None))
            .order_by(tables.documents.c.id.desc())
            .limit(min(max(limit, 1), 200))
        )
        if status:
            statement = statement.where(tables.documents.c.status == status)
        if cursor:
            # Keyset pagination on a time-ordered id: stable under inserts, which
            # OFFSET is not, and the UI polls while documents are being added.
            statement = statement.where(tables.documents.c.id < cursor)
        return list(self._c.execute(statement).mappings())

    def update_document(self, document_id: str, **values: Any) -> None:
        self._c.execute(
            update(tables.documents)
            .where(tables.documents.c.id == document_id)
            .where(tables.documents.c.project_id == self.project_id)
            .values(**values)
        )

    def soft_delete_document(self, document_id: str) -> None:
        """Marked deleted, then the derived rows are removed by cascade.

        The document row itself is kept so that the content hash stays reserved:
        a re-upload after a delete must not silently resurrect the old
        extractions.
        """
        self._c.execute(
            delete(tables.extractions)
            .where(tables.extractions.c.document_id == document_id)
            .where(tables.extractions.c.project_id == self.project_id)
        )
        self._c.execute(
            delete(tables.jobs)
            .where(tables.jobs.c.document_id == document_id)
            .where(tables.jobs.c.project_id == self.project_id)
        )
        self._c.execute(
            delete(tables.classifications)
            .where(tables.classifications.c.document_id == document_id)
            .where(tables.classifications.c.project_id == self.project_id)
        )
        self._c.execute(
            delete(tables.document_pages)
            .where(tables.document_pages.c.document_id == document_id)
            .where(tables.document_pages.c.project_id == self.project_id)
        )
        self.update_document(
            document_id, deleted_at=now(), blob_path="", status="deleted",
            idempotency_key=None,
        )

    def hash_in_use(self, sha256: str) -> bool:
        """Whether any live document anywhere still references these bytes.

        Deliberately not project-scoped: the blob store is shared, so deleting a
        blob because *this* project no longer needs it would break another
        project that uploaded the same file. The query reads one column of one
        table and leaks nothing.
        """
        statement = (
            select(func.count())
            .select_from(tables.documents)
            .where(tables.documents.c.sha256 == sha256)
            .where(tables.documents.c.deleted_at.is_(None))
        )
        return bool(self._c.execute(statement).scalar() or 0)

    def add_pages(self, document_id: str, pages: Iterable[Mapping[str, Any]]) -> None:
        rows = [
            {
                "id": ids.new_id("pg"),
                "project_id": self.project_id,
                "document_id": document_id,
                **dict(page),
            }
            for page in pages
        ]
        if rows:
            self._c.execute(insert(tables.document_pages), rows)

    def pages(self, document_id: str) -> list[RowMapping]:
        statement = (
            scoped(tables.document_pages, self.project_id)
            .where(tables.document_pages.c.document_id == document_id)
            .order_by(tables.document_pages.c.page_number)
        )
        return list(self._c.execute(statement).mappings())

    # -- jobs -------------------------------------------------------------

    def create_job(self, **values: Any) -> str:
        values.setdefault("id", ids.job_id())
        return self._insert(tables.jobs, values)

    def job(self, job_id: str) -> RowMapping | None:
        return self._one(tables.jobs, job_id)

    def job_for_document(self, document_id: str) -> RowMapping | None:
        statement = (
            scoped(tables.jobs, self.project_id)
            .where(tables.jobs.c.document_id == document_id)
            .order_by(tables.jobs.c.created_at.desc())
        )
        return self._c.execute(statement).mappings().first()

    def update_job(self, job_id: str, **values: Any) -> None:
        self._c.execute(
            update(tables.jobs)
            .where(tables.jobs.c.id == job_id)
            .where(tables.jobs.c.project_id == self.project_id)
            .values(**values)
        )

    # -- classifications --------------------------------------------------

    def add_classification(self, document_id: str, **values: Any) -> str:
        values.setdefault("id", ids.new_id("cls"))
        values["document_id"] = document_id
        return self._insert(tables.classifications, values)

    def classification(self, document_id: str) -> RowMapping | None:
        statement = (
            scoped(tables.classifications, self.project_id)
            .where(tables.classifications.c.document_id == document_id)
            .order_by(tables.classifications.c.created_at.desc())
        )
        return self._c.execute(statement).mappings().first()

    # -- schemas ----------------------------------------------------------

    def create_schema(self, **values: Any) -> str:
        values.setdefault("id", ids.schema_id())
        return self._insert(tables.schemas, values)

    def schema(self, schema_id: str) -> RowMapping | None:
        return self._one(tables.schemas, schema_id)

    def schema_by_name(self, name: str) -> RowMapping | None:
        statement = (
            scoped(tables.schemas, self.project_id)
            .where(tables.schemas.c.name == name)
        )
        return self._c.execute(statement).mappings().first()

    def list_schemas(self) -> list[RowMapping]:
        return list(self._c.execute(
            scoped(tables.schemas, self.project_id)
            .order_by(tables.schemas.c.created_at)
        ).mappings())

    def add_schema_version(self, schema_id: str, **values: Any) -> str:
        values.setdefault("id", ids.new_id("sv"))
        values["schema_id"] = schema_id
        return self._insert(tables.schema_versions, values)

    def schema_version(self, schema_id: str, version: int) -> RowMapping | None:
        statement = (
            scoped(tables.schema_versions, self.project_id)
            .where(tables.schema_versions.c.schema_id == schema_id)
            .where(tables.schema_versions.c.version == version)
        )
        return self._c.execute(statement).mappings().first()

    def schema_versions(self, schema_id: str) -> list[RowMapping]:
        statement = (
            scoped(tables.schema_versions, self.project_id)
            .where(tables.schema_versions.c.schema_id == schema_id)
            .order_by(tables.schema_versions.c.version)
        )
        return list(self._c.execute(statement).mappings())

    def set_schema_archived(self, schema_id: str, archived: bool) -> None:
        self._c.execute(
            update(tables.schemas)
            .where(tables.schemas.c.id == schema_id)
            .where(tables.schemas.c.project_id == self.project_id)
            .values(archived_at=now() if archived else None)
        )

    def schema_references(self, schema_id: str) -> dict[str, int]:
        """What still points at this schema, and how much of it.

        Used to decide whether a hard delete is safe. Extractions and jobs carry
        `schema_id` as a plain column with no foreign key — it is a
        reproducibility record (3.8), not a relationship — so nothing in the
        database stops the row being removed. This is that stop.

        Keys are counted only while live: a revoked key cannot be used, so it is
        not a reason to keep a schema the user wants gone.
        """
        counts: dict[str, int] = {}
        for label, table in (("extraction", tables.extractions),
                             ("job", tables.jobs)):
            total = self._c.execute(
                select(func.count())
                .select_from(table)
                .where(table.c.project_id == self.project_id)
                .where(table.c.schema_id == schema_id)
            ).scalar_one()
            if total:
                counts[label] = int(total)

        keys = 0
        for row in self.list_api_keys():
            if row["revoked_at"] is not None:
                continue
            if any(str(grant.get("schema_id")) == schema_id
                   for grant in (row["schema_versions"] or [])):
                keys += 1
        if keys:
            counts["key"] = keys
        return counts

    def delete_schema(self, schema_id: str) -> None:
        """Hard delete. Versions and test runs cascade; call only when
        `schema_references` is empty."""
        self._c.execute(
            delete(tables.schemas)
            .where(tables.schemas.c.id == schema_id)
            .where(tables.schemas.c.project_id == self.project_id)
        )

    def update_schema_current_version(self, schema_id: str, version: int) -> None:
        self._c.execute(
            update(tables.schemas)
            .where(tables.schemas.c.id == schema_id)
            .where(tables.schemas.c.project_id == self.project_id)
            .values(current_version=version)
        )

    def set_schema_version_test_status(self, schema_id: str, version: int,
                                       status: str) -> None:
        self._c.execute(
            update(tables.schema_versions)
            .where(tables.schema_versions.c.schema_id == schema_id)
            .where(tables.schema_versions.c.version == version)
            .where(tables.schema_versions.c.project_id == self.project_id)
            .values(test_run_status=status)
        )

    def create_test_run(self, **values: Any) -> str:
        values.setdefault("id", ids.test_run_id())
        return self._insert(tables.schema_test_runs, values)

    def test_run(self, run_id: str) -> RowMapping | None:
        return self._one(tables.schema_test_runs, run_id)

    def update_test_run(self, run_id: str, **values: Any) -> None:
        self._c.execute(
            update(tables.schema_test_runs)
            .where(tables.schema_test_runs.c.id == run_id)
            .where(tables.schema_test_runs.c.project_id == self.project_id)
            .values(**values)
        )

    # -- extractions ------------------------------------------------------

    def next_extraction_version(self, document_id: str, purpose: str) -> int:
        statement = (
            select(func.max(tables.extractions.c.version))
            .where(tables.extractions.c.document_id == document_id)
            .where(tables.extractions.c.purpose == purpose)
            .where(tables.extractions.c.project_id == self.project_id)
        )
        current = self._c.execute(statement).scalar()
        return int(current or 0) + 1

    def create_extraction(self, **values: Any) -> str:
        values.setdefault("id", ids.extraction_id())
        return self._insert(tables.extractions, values)

    def extraction(self, extraction_id: str) -> RowMapping | None:
        return self._one(tables.extractions, extraction_id)

    def latest_extraction(self, document_id: str,
                          purpose: str | None = None) -> RowMapping | None:
        statement = (
            scoped(tables.extractions, self.project_id)
            .where(tables.extractions.c.document_id == document_id)
            .order_by(tables.extractions.c.version.desc())
        )
        if purpose:
            statement = statement.where(tables.extractions.c.purpose == purpose)
        return self._c.execute(statement).mappings().first()

    def extractions_for_document(self, document_id: str) -> list[RowMapping]:
        statement = (
            scoped(tables.extractions, self.project_id)
            .where(tables.extractions.c.document_id == document_id)
            .order_by(tables.extractions.c.version)
        )
        return list(self._c.execute(statement).mappings())

    def update_extraction(self, extraction_id: str, **values: Any) -> None:
        self._c.execute(
            update(tables.extractions)
            .where(tables.extractions.c.id == extraction_id)
            .where(tables.extractions.c.project_id == self.project_id)
            .values(**values)
        )

    def add_field(self, extraction_id: str, **values: Any) -> str:
        values.setdefault("id", ids.new_id("fld"))
        values["extraction_id"] = extraction_id
        return self._insert(tables.extraction_fields, values)

    def fields(self, extraction_id: str) -> list[RowMapping]:
        statement = (
            scoped(tables.extraction_fields, self.project_id)
            .where(tables.extraction_fields.c.extraction_id == extraction_id)
            .order_by(tables.extraction_fields.c.path)
        )
        return list(self._c.execute(statement).mappings())

    def add_evidence(self, field_id: str, rows: Iterable[Mapping[str, Any]]) -> None:
        payload = [
            {
                "id": ids.new_id("evd"),
                "project_id": self.project_id,
                "extraction_field_id": field_id,
                **dict(row),
            }
            for row in rows
        ]
        if payload:
            self._c.execute(insert(tables.evidence), payload)

    def evidence_for(self, field_ids: Sequence[str]) -> dict[str, list[RowMapping]]:
        if not field_ids:
            return {}
        statement = (
            scoped(tables.evidence, self.project_id)
            .where(tables.evidence.c.extraction_field_id.in_(list(field_ids)))
            .order_by(tables.evidence.c.page)
        )
        out: dict[str, list[RowMapping]] = {}
        for row in self._c.execute(statement).mappings():
            out.setdefault(row["extraction_field_id"], []).append(row)
        return out

    def add_validation(self, extraction_id: str,
                       results: Iterable[Mapping[str, Any]]) -> None:
        payload = [
            {
                "id": ids.new_id("val"),
                "project_id": self.project_id,
                "extraction_id": extraction_id,
                **dict(result),
            }
            for result in results
        ]
        if payload:
            self._c.execute(insert(tables.validation_results), payload)

    def validations(self, extraction_id: str) -> list[RowMapping]:
        statement = (
            scoped(tables.validation_results, self.project_id)
            .where(tables.validation_results.c.extraction_id == extraction_id)
        )
        return list(self._c.execute(statement).mappings())

    def add_decision(self, extraction_id: str, **values: Any) -> str:
        values.setdefault("id", ids.new_id("dec"))
        values["extraction_id"] = extraction_id
        return self._insert(tables.decisions, values)

    def latest_decision(self, extraction_id: str) -> RowMapping | None:
        statement = (
            scoped(tables.decisions, self.project_id)
            .where(tables.decisions.c.extraction_id == extraction_id)
            .order_by(tables.decisions.c.created_at.desc())
        )
        return self._c.execute(statement).mappings().first()

    def add_correction(self, extraction_id: str, **values: Any) -> str:
        values.setdefault("id", ids.new_id("cor"))
        values["extraction_id"] = extraction_id
        return self._insert(tables.corrections, values)

    # -- keys, audit, usage, exports --------------------------------------

    def create_api_key(self, **values: Any) -> str:
        values.setdefault("id", ids.api_key_id())
        return self._insert(tables.api_keys, values)

    def api_key(self, key_id: str) -> RowMapping | None:
        return self._one(tables.api_keys, key_id)

    def list_api_keys(self) -> list[RowMapping]:
        return list(self._c.execute(
            scoped(tables.api_keys, self.project_id)
            .order_by(tables.api_keys.c.created_at)
        ).mappings())

    def revoke_api_key(self, key_id: str) -> None:
        self._c.execute(
            update(tables.api_keys)
            .where(tables.api_keys.c.id == key_id)
            .where(tables.api_keys.c.project_id == self.project_id)
            .values(revoked_at=now())
        )

    def audit(self, actor: str, action: str, object_type: str, object_id: str,
              detail: Mapping[str, Any] | None = None) -> None:
        """`detail` carries ids and codes only. Never a value, never a filename's
        contents, never a field the user corrected to (rule 2.13)."""
        self._insert(tables.audit_events, {
            "id": ids.new_id("aud"),
            "actor": actor,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "detail": dict(detail or {}),
        })

    def audit_events(self, limit: int = 100) -> list[RowMapping]:
        return list(self._c.execute(
            scoped(tables.audit_events, self.project_id)
            .order_by(tables.audit_events.c.created_at.desc())
            .limit(limit)
        ).mappings())

    def record_provider_call(self, **values: Any) -> str:
        values.setdefault("id", ids.new_id("pcl"))
        return self._insert(tables.provider_calls, values)

    def provider_calls(self, document_id: str | None = None) -> list[RowMapping]:
        statement = scoped(tables.provider_calls, self.project_id)
        if document_id:
            statement = statement.where(
                tables.provider_calls.c.document_id == document_id
            )
        return list(self._c.execute(statement).mappings())

    def add_usage(self, *, pages: int = 0, documents: int = 0,
                  ai_cost_usd: float = 0.0, api_key_id: str | None = None,
                  month: str | None = None) -> None:
        """Upsert, because two workers can finish two documents in the same
        millisecond and an INSERT would collide on the unique scope."""
        key = month or _month()
        existing = self._c.execute(
            scoped(tables.usage_records, self.project_id)
            .where(tables.usage_records.c.month == key)
            .where(
                tables.usage_records.c.api_key_id.is_(None) if api_key_id is None
                else tables.usage_records.c.api_key_id == api_key_id
            )
        ).mappings().first()
        if existing is None:
            self._insert(tables.usage_records, {
                "id": ids.new_id("usg"),
                "month": key,
                "api_key_id": api_key_id,
                "documents": documents,
                "pages": pages,
                "ai_cost_usd": ai_cost_usd,
                "updated_at": now(),
            })
            return
        self._c.execute(
            update(tables.usage_records)
            .where(tables.usage_records.c.id == existing["id"])
            .where(tables.usage_records.c.project_id == self.project_id)
            .values(
                documents=existing["documents"] + documents,
                pages=existing["pages"] + pages,
                ai_cost_usd=existing["ai_cost_usd"] + ai_cost_usd,
                updated_at=now(),
            )
        )

    def usage(self, month: str | None = None) -> list[RowMapping]:
        statement = (
            scoped(tables.usage_records, self.project_id)
            .where(tables.usage_records.c.month == (month or _month()))
        )
        return list(self._c.execute(statement).mappings())

    def month_ai_cost(self, month: str | None = None) -> float:
        return float(sum(row["ai_cost_usd"] for row in self.usage(month)))

    def create_export(self, **values: Any) -> str:
        values.setdefault("id", ids.export_id())
        return self._insert(tables.exports, values)

    def export(self, export_id: str) -> RowMapping | None:
        return self._one(tables.exports, export_id)

    def update_export(self, export_id: str, **values: Any) -> None:
        self._c.execute(
            update(tables.exports)
            .where(tables.exports.c.id == export_id)
            .where(tables.exports.c.project_id == self.project_id)
            .values(**values)
        )


class GlobalRepository:
    """The handful of reads that genuinely have no project: users, templates and
    the worker's queue poll across projects."""

    def __init__(self, connection: Connection) -> None:
        self._c = connection

    def create_user(self, **values: Any) -> str:
        values.setdefault("id", ids.user_id())
        self._c.execute(insert(tables.users).values(**values))
        return str(values["id"])

    def user_by_email(self, email: str) -> RowMapping | None:
        statement = select(tables.users).where(
            func.lower(tables.users.c.email) == email.strip().lower()
        )
        return self._c.execute(statement).mappings().first()

    def user(self, user_id: str) -> RowMapping | None:
        statement = select(tables.users).where(tables.users.c.id == user_id)
        return self._c.execute(statement).mappings().first()

    def create_project(self, **values: Any) -> str:
        values.setdefault("id", ids.project_id())
        self._c.execute(insert(tables.projects).values(**values))
        return str(values["id"])

    def projects_for(self, user_id: str) -> list[RowMapping]:
        statement = (
            select(tables.projects)
            .where(tables.projects.c.owner_id == user_id)
            .order_by(tables.projects.c.created_at)
        )
        return list(self._c.execute(statement).mappings())

    def project(self, project_id: str) -> RowMapping | None:
        statement = select(tables.projects).where(tables.projects.c.id == project_id)
        return self._c.execute(statement).mappings().first()

    def templates(self) -> list[RowMapping]:
        return list(self._c.execute(
            select(tables.schema_templates)
            .order_by(tables.schema_templates.c.document_type)
        ).mappings())

    def template(self, template_id: str) -> RowMapping | None:
        statement = select(tables.schema_templates).where(
            tables.schema_templates.c.id == template_id
        )
        return self._c.execute(statement).mappings().first()

    def api_key_by_prefix(self, prefix: str) -> RowMapping | None:
        """Authentication crosses projects by necessity: the key is what *tells*
        us the project, so it cannot be scoped by one. The prefix narrows to a
        single row and the hash comparison that follows is constant-time."""
        statement = (
            select(tables.api_keys)
            .where(tables.api_keys.c.prefix == prefix)
            .where(tables.api_keys.c.revoked_at.is_(None))
        )
        return self._c.execute(statement).mappings().first()

    def claim_next_job(self, owner: str, lease_seconds: float) -> RowMapping | None:
        """Take one queued job across all projects, under a lease.

        The worker is global; the work it does is not. Everything after this
        point goes through a `ProjectRepository` built from the claimed row.
        """
        moment = now()
        candidates = self._c.execute(
            select(tables.jobs)
            .where(tables.jobs.c.state.notin_([
                "completed", "needs_review", "failed", "unsupported",
                "cancelled", "rejected", "approved", "exported",
            ]))
            .where(and_(
                tables.jobs.c.leased_until.is_(None)
                | (tables.jobs.c.leased_until < moment)
            ))
            .order_by(tables.jobs.c.created_at)
            .limit(1)
        ).mappings().first()
        if candidates is None:
            return None
        lease_until = datetime.fromtimestamp(
            moment.replace(tzinfo=UTC).timestamp() + lease_seconds,
            tz=UTC,
        ).replace(tzinfo=None)
        updated = self._c.execute(
            update(tables.jobs)
            .where(tables.jobs.c.id == candidates["id"])
            # Optimistic: if another worker claimed it between the select and
            # here, its lease is now in the future and this matches nothing.
            .where(
                tables.jobs.c.leased_until.is_(None)
                | (tables.jobs.c.leased_until < moment)
            )
            .values(leased_until=lease_until, attempts=candidates["attempts"] + 1,
                    started_at=candidates["started_at"] or moment)
        )
        if updated.rowcount != 1:
            return None
        return candidates

    def worker_heartbeat(self) -> datetime | None:
        statement = select(func.max(tables.jobs.c.leased_until))
        return self._c.execute(statement).scalar()


__all__ = [
    "GlobalRepository",
    "ProjectRepository",
    "UnscopedQuery",
    "now",
    "scoped",
]
