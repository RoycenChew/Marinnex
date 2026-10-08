"""Templates, schemas, immutable schema versions, and schema test runs.

The rule that shapes this router is that a **version is immutable**. A customer
pins `invoice@1`; changing what that extracts would change their integration
without their knowing. So `POST /schemas/{id}/versions` always inserts, never
updates, and the stored version keeps its own copy of the field list rather than
referring to the live template.

A test run is required before a key may use a version (3.7). That gate is what
stops a schema with a typo in a field path from reaching production and returning
nulls for a week.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping

from fdip.adapters.providers import build_model_stack
from fdip.adapters.repository import GlobalRepository, ProjectRepository, now
from fdip.adapters.seed import INVOICE_TEMPLATE_ID
from fdip.api import problems, views
from fdip.api.deps import (
    AppState,
    Principal,
    db_connection,
    get_state,
    release_write_lock,
    repository,
    session_principal,
)
from fdip.api.schemas import (
    SchemaCreated,
    SchemaVersionView,
    SchemaView,
    Template,
    TestRun,
)
from fdip.domain.schema_lang import (
    CustomField,
    FieldConfig,
    LocaleHints,
    SchemaSpec,
    to_response_contract,
)
from fdip.domain.statuses import ErrorCode, JobState
from fdip.domain.templates import DEFAULT_SELECTED_FIELDS, TEMPLATE_VERSION
from fdip.domain.user_text import DESCRIPTION_LIMIT, MAX_CUSTOM_FIELDS, MAX_HINTS
from fdip.pipeline.runner import JobContext, run_id_for, run_job

router = APIRouter(tags=["schemas"])

MIN_TEST_DOCUMENTS = 3
MAX_TEST_DOCUMENTS = 5


class LocaleHintsIn(BaseModel):
    date_order: str = "DMY"


class FieldConfigIn(BaseModel):
    """How one field is presented. Nothing here changes what is extracted."""

    alias: str | None = Field(default=None, max_length=64)
    order: int | None = Field(default=None, ge=0, le=999)
    required: bool | None = None
    #: Display only. Exports and the screen honour these; the API never does.
    date_format: str | None = Field(default=None, max_length=32)
    number_format: str | None = Field(default=None, max_length=32)


class CustomFieldIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: Literal["text", "number", "money", "date"] = "text"
    description: str = Field(min_length=1, max_length=DESCRIPTION_LIMIT)
    hints: list[str] = Field(default_factory=list, max_length=MAX_HINTS)
    required: bool = False


class CreateSchema(BaseModel):
    template_id: str = INVOICE_TEMPLATE_ID
    name: str = Field(min_length=1, max_length=200)
    fields: list[str] = Field(default_factory=lambda: list(DEFAULT_SELECTED_FIELDS))
    locale_hints: LocaleHintsIn = Field(default_factory=LocaleHintsIn)
    field_config: dict[str, FieldConfigIn] = Field(default_factory=dict)
    custom_fields: list[CustomFieldIn] = Field(
        default_factory=list, max_length=MAX_CUSTOM_FIELDS,
    )


class NewVersion(BaseModel):
    fields: list[str]
    locale_hints: LocaleHintsIn = Field(default_factory=LocaleHintsIn)
    field_config: dict[str, FieldConfigIn] = Field(default_factory=dict)
    custom_fields: list[CustomFieldIn] = Field(
        default_factory=list, max_length=MAX_CUSTOM_FIELDS,
    )


class PatchVersion(BaseModel):
    """Level 1 edits to a draft version. Fields and custom fields are replaced
    wholesale, because a partial merge of a field map is ambiguous."""

    field_config: dict[str, FieldConfigIn] | None = None
    custom_fields: list[CustomFieldIn] | None = Field(
        default=None, max_length=MAX_CUSTOM_FIELDS,
    )


class TestRunRequest(BaseModel):
    document_ids: list[str] = Field(min_length=MIN_TEST_DOCUMENTS,
                                    max_length=MAX_TEST_DOCUMENTS)


def _stored_config(spec: SchemaSpec) -> dict[str, Any]:
    return {path: config.as_dict() for path, config in spec.field_config.items()
            if config.as_dict()}


def _stored_custom(spec: SchemaSpec) -> list[dict[str, Any]]:
    """Persist the *sanitised* text, so what is stored is what reaches the
    prompt. Doing it once here beats doing it on every document."""
    return [custom.as_dict() for custom in spec.custom_fields]


def _spec(name: str, document_type: str, fields: list[str],
          hints: LocaleHintsIn,
          field_config: Mapping[str, FieldConfigIn] | None = None,
          custom_fields: Sequence[CustomFieldIn] = ()) -> SchemaSpec:
    """Build the spec, turning every domain complaint into a 422.

    The domain owns the rules — snake_case, uniqueness, the field cap, the
    prompt-size ceiling — because the worker rebuilds the same spec from storage
    and must reach the same verdict as the request that created it.
    """
    if hints.date_order not in ("DMY", "MDY", "YMD"):
        raise problems.invalid("date_order must be DMY, MDY or YMD")
    try:
        return SchemaSpec(
            name=name, document_type=document_type, fields=tuple(fields),
            locale_hints=LocaleHints(date_order=hints.date_order),  # type: ignore[arg-type]
            field_config={
                path: FieldConfig(**config.model_dump(exclude_none=True))
                for path, config in (field_config or {}).items()
            },
            custom_fields=tuple(
                CustomField(
                    name=entry.name, kind=entry.kind,
                    description=entry.description,
                    hints=tuple(entry.hints), required=entry.required,
                )
                for entry in custom_fields
            ),
        )
    except ValueError as error:
        raise problems.invalid(str(error)) from error


@router.get("/templates", response_model=list[Template])
def list_templates(
    _: Annotated[Principal, Depends(session_principal)],
    connection: Connection = Depends(db_connection),
) -> list[dict[str, Any]]:
    return [views.template_view(row) for row in GlobalRepository(connection).templates()]


@router.post("/schemas", status_code=201, response_model=SchemaCreated)
def create_schema(
    payload: CreateSchema,
    principal: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
    connection: Connection = Depends(db_connection),
) -> dict[str, Any]:
    template = GlobalRepository(connection).template(payload.template_id)
    if template is None:
        raise problems.not_found("template")
    if repo.schema_by_name(payload.name) is not None:
        raise problems.conflict("schema_name_taken",
                                "a schema with that name already exists")
    spec = _spec(payload.name, str(template["document_type"]), payload.fields,
                 payload.locale_hints, payload.field_config,
                 payload.custom_fields)
    schema_id = repo.create_schema(
        template_id=payload.template_id, name=payload.name,
        document_type=str(template["document_type"]), current_version=1,
    )
    repo.add_schema_version(
        schema_id, version=1, fields=list(payload.fields),
        locale_hints=spec.locale_hints.as_dict(),
        template_version=int(template["version"] or TEMPLATE_VERSION),
        contract=to_response_contract(spec, 1), test_run_status="none",
        field_config=_stored_config(spec), custom_fields=_stored_custom(spec),
    )
    # Names and counts only. A description is customer text and a hint can name
    # their supplier's paperwork, so neither goes anywhere near a log (2.13).
    repo.audit(principal.actor, "schema_created", "schema", schema_id,
               {"version": 1, "field_count": len(payload.fields),
                "custom_fields": len(payload.custom_fields)})
    return {"schema_id": schema_id, "version": 1}


@router.get("/schemas", response_model=list[SchemaView])
def list_schemas(
    _: Annotated[Principal, Depends(session_principal)],
    include_archived: bool = False,
    repo: ProjectRepository = Depends(repository),
) -> list[dict[str, Any]]:
    """Archived schemas are hidden by default; `?include_archived=true` shows
    them, which is how a user finds one again to restore it."""
    return [views.schema_view(row) for row in repo.list_schemas()
            if include_archived or row["archived_at"] is None]


@router.get("/schemas/{schema_id}", response_model=SchemaView)
def get_schema(
    schema_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    schema = repo.schema(schema_id)
    if schema is None:
        raise problems.not_found("schema")
    return views.schema_view(schema, repo.schema_versions(schema_id))


@router.post(
    "/schemas/{schema_id}/versions",
    status_code=201,
    response_model=SchemaCreated,
)
def add_version(
    schema_id: str,
    payload: NewVersion,
    principal: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    schema = repo.schema(schema_id)
    if schema is None:
        raise problems.not_found("schema")
    _require_active(schema)
    spec = _spec(str(schema["name"]), str(schema["document_type"]),
                 payload.fields, payload.locale_hints, payload.field_config,
                 payload.custom_fields)
    version = int(schema["current_version"]) + 1
    repo.add_schema_version(
        schema_id, version=version, fields=list(payload.fields),
        locale_hints=spec.locale_hints.as_dict(),
        template_version=TEMPLATE_VERSION,
        contract=to_response_contract(spec, version), test_run_status="none",
        field_config=_stored_config(spec), custom_fields=_stored_custom(spec),
    )
    repo.update_schema_current_version(schema_id, version)
    repo.audit(principal.actor, "schema_version_created", "schema", schema_id,
               {"version": version, "field_count": len(payload.fields),
                "custom_fields": len(payload.custom_fields)})
    return {"schema_id": schema_id, "version": version}


@router.get("/schemas/{schema_id}/versions/{version}/contract")
def get_contract(
    schema_id: str,
    version: int,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """The published JSON Schema of the extraction response for this version.

    Served from the stored copy rather than recompiled, so that a template change
    cannot alter a contract a customer has already integrated against.
    """
    row = repo.schema_version(schema_id, version)
    if row is None:
        raise problems.not_found("schema version")
    return dict(row["contract"] or {})


@router.post(
    "/schemas/{schema_id}/versions/{version}/test-runs",
    status_code=202,
    response_model=TestRun,
)
def create_test_run(
    schema_id: str,
    version: int,
    payload: TestRunRequest,
    principal: Annotated[Principal, Depends(session_principal)],
    state: AppState = Depends(get_state),
    repo: ProjectRepository = Depends(repository),
    connection: Connection = Depends(db_connection),
) -> dict[str, Any]:
    """Score this version against documents already in the project.

    For a template-only version this reuses the analysis extraction and costs
    nothing: the analysis ran the whole template, so it already knows whether
    each selected field was found.

    A version with **custom fields** cannot be answered that way. The analysis
    never looked for `site_ref`, so reporting "not found" would be reporting
    that nobody asked — which is exactly the false reassurance a test run exists
    to prevent. Those versions are therefore extracted for real, once per
    document, and that does cost a model call. It is the honest price of the
    question being asked.
    """
    schema = repo.schema(schema_id)
    if schema is None:
        raise problems.not_found("schema")
    stored = repo.schema_version(schema_id, version)
    if stored is None:
        raise problems.not_found("schema version")
    fields = list(stored["fields"] or [])
    spec = _spec(
        str(schema["name"]), str(stored.get("document_type") or "invoice"), fields,
        LocaleHintsIn(**(stored["locale_hints"] or {})),
        {path: FieldConfigIn(**values)
         for path, values in (stored["field_config"] or {}).items()},
        [CustomFieldIn(**entry) for entry in (stored["custom_fields"] or [])],
    )
    required = set(spec.required_paths())
    #  Reported per document whether required or not: a customer who adds an
    #  optional custom field still needs to know whether it was found before
    #  they build on it.
    reported = sorted(set(required) | spec.custom_names)

    per_document: list[dict[str, Any]] = []
    for document_id in payload.document_ids:
        document = repo.document(document_id)
        if document is None:
            raise problems.not_found("document " + document_id)
        extraction = _extraction_for_test(
            state, repo, connection, document, spec, schema_id, version,
        )
        if extraction is None:
            per_document.append({
                "document_id": document_id, "status": "no_analysis",
                "fields_ok": 0, "fields_total": len(required),
                "fields": dict.fromkeys(reported, "not_found"),
            })
            continue
        rows = {str(row["path"]): row for row in repo.fields(str(extraction["id"]))}
        ok = sum(
            1 for path in required
            if path in rows and rows[path]["status"] == "accepted"
        )
        per_document.append({
            "document_id": document_id,
            "status": "ok" if ok == len(required) else "incomplete",
            "fields_ok": ok, "fields_total": len(required),
            "fields": {
                path: ("found"
                       if path in rows and rows[path]["status"] == "accepted"
                       else "not_found")
                for path in reported
            },
        })

    passed = bool(per_document) and all(
        entry["status"] == "ok" for entry in per_document
    )
    run_id = repo.create_test_run(
        schema_id=schema_id, version=version, status="completed", passed=passed,
        document_ids=list(payload.document_ids), per_document=per_document,
        finished_at=now(),
    )
    repo.set_schema_version_test_status(
        schema_id, version, "passed" if passed else "failed"
    )
    repo.audit(principal.actor, "schema_test_run", "schema", schema_id,
               {"version": version, "passed": passed,
                "documents": len(payload.document_ids)})
    return views.test_run_view(repo.test_run(run_id))  # type: ignore[arg-type]


@router.get("/test-runs/{run_id}", response_model=TestRun)
def get_test_run(
    run_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    row = repo.test_run(run_id)
    if row is None:
        raise problems.not_found("test run")
    return views.test_run_view(row)


def require_tested_version(repo: ProjectRepository, schema_id: str,
                           version: int) -> dict[str, Any]:
    """The gate a pipeline call passes before it may use a version."""
    row = repo.schema_version(schema_id, version)
    if row is None:
        raise problems.not_found("schema version")
    if str(row["test_run_status"]) != "passed":
        raise problems.Problem(
            409, ErrorCode.SCHEMA_TEST_RUN_REQUIRED.value,
            "schema version %d has not passed a test run, so a key may not use it"
            % version,
        )
    return dict(row)


__all__ = ["router", "require_tested_version"]


# --- archive, restore, purge -------------------------------------------------
#
# Deleting a schema means two different things and only one of them is safe.
#
# A schema that has produced extractions is a reproducibility record: every
# extraction is stamped with `schema_id` and `schema_version` (3.8), and there is
# no foreign key to stop the row going, which is exactly why there has to be a
# check here. Destroying it would leave finished results citing a schema nobody
# can look up — the same reason corrections write a new version instead of
# overwriting one.
#
# But a schema somebody created by mistake is just clutter, and a product that
# will not let you remove your own mistake looks broken on the first afternoon.
#
# So: `DELETE` archives, always available, reversible. `DELETE ?purge=true`
# destroys, and only while nothing points at the schema. The refusal names what
# is holding it, because "no" without a reason leaves the user with no next step.


def _require_active(schema: RowMapping) -> None:
    if schema["archived_at"] is not None:
        raise problems.Problem(
            409, ErrorCode.SCHEMA_ARCHIVED.value,
            "this schema is archived; restore it before making changes",
        )


@router.delete("/schemas/{schema_id}", status_code=204)
def archive_or_purge_schema(
    schema_id: str,
    principal: Annotated[Principal, Depends(session_principal)],
    purge: bool = False,
    repo: ProjectRepository = Depends(repository),
) -> None:
    """Archive a schema, or destroy it outright with `?purge=true`."""
    schema = repo.schema(schema_id)
    if schema is None:
        raise problems.not_found("schema")

    if not purge:
        repo.set_schema_archived(schema_id, True)
        repo.audit(principal.actor, "schema_archived", "schema", schema_id, {})
        return

    references = repo.schema_references(schema_id)
    if references:
        held = ", ".join(
            "%d %s%s" % (count, label, "" if count == 1 else "s")
            for label, count in sorted(references.items())
        )
        # The remedy depends on what is holding it. A key can be revoked; an
        # extraction cannot be un-run, and telling someone to revoke a key that
        # is not the problem sends them off to do something useless.
        remedy = ("Archive it instead, or revoke the keys that grant it."
                  if "key" in references and len(references) == 1
                  else "Archive it instead — past results have to keep "
                       "resolving the version they were produced against.")
        raise problems.Problem(
            409, ErrorCode.SCHEMA_IN_USE.value,
            "this schema is still referenced by %s, so it cannot be deleted. %s"
            % (held, remedy),
            references=references,
        )
    repo.delete_schema(schema_id)
    repo.audit(principal.actor, "schema_deleted", "schema", schema_id, {})


@router.post("/schemas/{schema_id}/restore", response_model=SchemaView)
def restore_schema(
    schema_id: str,
    principal: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """Bring an archived schema back. Archiving is not a decision a user has to
    get right first time."""
    schema = repo.schema(schema_id)
    if schema is None:
        raise problems.not_found("schema")
    repo.set_schema_archived(schema_id, False)
    repo.audit(principal.actor, "schema_restored", "schema", schema_id, {})
    restored = repo.schema(schema_id)
    return views.schema_view(restored, repo.schema_versions(schema_id))  # type: ignore[arg-type]


@router.patch(
    "/schemas/{schema_id}/versions/{version}",
    response_model=SchemaVersionView,
)
def patch_version(
    schema_id: str,
    version: int,
    payload: PatchVersion,
    principal: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """Adjust a draft version's presentation and custom fields.

    Allowed only while the version is still a draft. Once it has passed a test
    run, or a live key is pinned to it, a customer may be relying on the key
    names it publishes — changing them would break their integration with no
    signal — so from that point a change is a new version, and this returns
    `409 schema_version_frozen` saying so.
    """
    schema = repo.schema(schema_id)
    if schema is None:
        raise problems.not_found("schema")
    _require_active(schema)
    stored = repo.schema_version(schema_id, version)
    if stored is None:
        raise problems.not_found("schema version")

    reasons = []
    if str(stored["test_run_status"]) == "passed":
        reasons.append("it has passed a test run")
    bound = repo.keys_binding_version(schema_id, version)
    if bound:
        reasons.append("%d live API key%s use%s it"
                       % (bound, "" if bound == 1 else "s", "s" if bound == 1 else ""))
    if reasons:
        raise problems.Problem(
            409, ErrorCode.SCHEMA_VERSION_FROZEN.value,
            "this version cannot be changed because %s. Add a new version "
            "instead — the one your integrations use stays as it is."
            % " and ".join(reasons),
        )

    fields = list(stored["fields"] or [])
    hints = LocaleHintsIn(**(stored["locale_hints"] or {}))
    config = (payload.field_config if payload.field_config is not None
              else {path: FieldConfigIn(**values)
                    for path, values in (stored["field_config"] or {}).items()})
    custom = (payload.custom_fields if payload.custom_fields is not None
              else [CustomFieldIn(**entry)
                    for entry in (stored["custom_fields"] or [])])

    spec = _spec(str(schema["name"]), str(schema["document_type"]), fields,
                 hints, config, custom)
    repo.update_schema_version(
        schema_id, version,
        field_config=_stored_config(spec), custom_fields=_stored_custom(spec),
        contract=to_response_contract(spec, version),
    )
    repo.audit(principal.actor, "schema_version_updated", "schema", schema_id,
               {"version": version, "custom_fields": len(custom)})
    updated = repo.schema_version(schema_id, version)
    return views.schema_version_view(updated)  # type: ignore[arg-type]


def _extraction_for_test(
    state: AppState,
    repo: ProjectRepository,
    connection: Connection,
    document: RowMapping,
    spec: SchemaSpec,
    schema_id: str,
    version: int,
) -> RowMapping | None:
    """The extraction a test run scores against.

    Template-only: the analysis run already answered the question, for free.
    With custom fields: run the version for real, because nothing on file has
    ever looked for them. The durable run id carries the purpose and the
    version, so a repeated test run replays its checkpoints instead of paying
    twice.
    """
    document_id = str(document["id"])
    if not spec.custom_fields:
        return repo.latest_extraction(document_id, purpose="analysis")

    existing = repo.latest_extraction(document_id, purpose="test")
    if existing is not None and int(existing["schema_version"] or 0) == version:
        return existing

    digest = str(document["sha256"])
    job_id = repo.create_job(
        document_id=document_id,
        run_id=run_id_for(digest, "test", version),
        state=JobState.RECEIVED.value, mode="test",
        schema_id=schema_id, schema_version=version,
    )
    # SQLite has one writer and the pipeline opens its own connections; without
    # this the request deadlocks against itself.
    release_write_lock(connection)
    models = build_model_stack(state.settings,
                               already_spent_usd=repo.month_ai_cost())
    run_job(JobContext(
        engine=state.engine, settings=state.settings, models=models,
        project_id=repo.project_id, document_id=document_id, job_id=job_id,
        blob_path=str(document["blob_path"]), spec=spec, purpose="test",
        schema_id=schema_id, schema_version=version,
        expected_type=spec.document_type,
    ), digest)
    return repo.latest_extraction(document_id, purpose="test")
