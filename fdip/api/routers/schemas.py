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

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from fdip.adapters.repository import GlobalRepository, ProjectRepository, now
from fdip.adapters.seed import INVOICE_TEMPLATE_ID
from fdip.api import problems, views
from fdip.api.deps import Principal, db_connection, repository, session_principal
from fdip.api.schemas import SchemaCreated, SchemaView, Template, TestRun
from fdip.domain.schema_lang import (
    LocaleHints,
    SchemaSpec,
    to_response_contract,
)
from fdip.domain.statuses import ErrorCode
from fdip.domain.templates import DEFAULT_SELECTED_FIELDS, TEMPLATE_VERSION

router = APIRouter(tags=["schemas"])

MIN_TEST_DOCUMENTS = 3
MAX_TEST_DOCUMENTS = 5


class LocaleHintsIn(BaseModel):
    date_order: str = "DMY"


class CreateSchema(BaseModel):
    template_id: str = INVOICE_TEMPLATE_ID
    name: str = Field(min_length=1, max_length=200)
    fields: list[str] = Field(default_factory=lambda: list(DEFAULT_SELECTED_FIELDS))
    locale_hints: LocaleHintsIn = Field(default_factory=LocaleHintsIn)


class NewVersion(BaseModel):
    fields: list[str]
    locale_hints: LocaleHintsIn = Field(default_factory=LocaleHintsIn)


class TestRunRequest(BaseModel):
    document_ids: list[str] = Field(min_length=MIN_TEST_DOCUMENTS,
                                    max_length=MAX_TEST_DOCUMENTS)


def _spec(name: str, document_type: str, fields: list[str],
          hints: LocaleHintsIn) -> SchemaSpec:
    if hints.date_order not in ("DMY", "MDY", "YMD"):
        raise problems.invalid("date_order must be DMY, MDY or YMD")
    try:
        return SchemaSpec(
            name=name, document_type=document_type, fields=tuple(fields),
            locale_hints=LocaleHints(date_order=hints.date_order),  # type: ignore[arg-type]
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
                 payload.locale_hints)
    schema_id = repo.create_schema(
        template_id=payload.template_id, name=payload.name,
        document_type=str(template["document_type"]), current_version=1,
    )
    repo.add_schema_version(
        schema_id, version=1, fields=list(payload.fields),
        locale_hints=spec.locale_hints.as_dict(),
        template_version=int(template["version"] or TEMPLATE_VERSION),
        contract=to_response_contract(spec, 1), test_run_status="none",
    )
    repo.audit(principal.actor, "schema_created", "schema", schema_id,
               {"version": 1, "field_count": len(payload.fields)})
    return {"schema_id": schema_id, "version": 1}


@router.get("/schemas", response_model=list[SchemaView])
def list_schemas(
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> list[dict[str, Any]]:
    return [views.schema_view(row) for row in repo.list_schemas()]


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
    spec = _spec(str(schema["name"]), str(schema["document_type"]),
                 payload.fields, payload.locale_hints)
    version = int(schema["current_version"]) + 1
    repo.add_schema_version(
        schema_id, version=version, fields=list(payload.fields),
        locale_hints=spec.locale_hints.as_dict(),
        template_version=TEMPLATE_VERSION,
        contract=to_response_contract(spec, version), test_run_status="none",
    )
    repo.update_schema_current_version(schema_id, version)
    repo.audit(principal.actor, "schema_version_created", "schema", schema_id,
               {"version": version, "field_count": len(payload.fields)})
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
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """Score this version against documents already in the project.

    It reuses existing extractions rather than calling the model again: the
    question a test run answers is "does this field selection find values on my
    documents", and the analysis run already has that answer. So a test run costs
    nothing and can be repeated.
    """
    stored = repo.schema_version(schema_id, version)
    if stored is None:
        raise problems.not_found("schema version")
    fields = list(stored["fields"] or [])
    required = set(_spec(
        "Invoice", str(stored.get("document_type") or "invoice"), fields,
        LocaleHintsIn(**(stored["locale_hints"] or {})),
    ).required_paths())

    per_document: list[dict[str, Any]] = []
    for document_id in payload.document_ids:
        document = repo.document(document_id)
        if document is None:
            raise problems.not_found("document " + document_id)
        extraction = repo.latest_extraction(document_id, purpose="analysis")
        if extraction is None:
            per_document.append({
                "document_id": document_id, "status": "no_analysis",
                "fields_ok": 0, "fields_total": len(required),
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
