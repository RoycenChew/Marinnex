"""Keys, exports, usage, jobs and health.

Grouped because they are small and share one theme: they are the operational
surface rather than the document pipeline.

The one rule worth repeating is in `create_api_key`: the full key appears in that
response and nowhere else, ever. There is no endpoint that returns it again,
because there is nothing stored that could produce it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from fdip.adapters import export as export_tools
from fdip.adapters import keys as key_tools
from fdip.adapters.ids import api_key_id as new_api_key_id
from fdip.adapters.repository import GlobalRepository, ProjectRepository, now
from fdip.api import problems, views
from fdip.api.deps import (
    AppState,
    Principal,
    db_connection,
    get_state,
    repository,
    session_principal,
)
from fdip.api.schemas import (
    ApiKeyCreated,
    ApiKeyView,
    ExportJob,
    Health,
    JobView,
    Usage,
)
from fdip.domain.statuses import ErrorCode, Status

router = APIRouter(tags=["admin"])

EXPORTABLE_STATUSES = (Status.COMPLETED.value, Status.NEEDS_REVIEW.value)


class SchemaVersionRef(BaseModel):
    schema_id: str
    version: int


class CreateKey(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mode: str = "test"
    schema_versions: list[SchemaVersionRef] = Field(default_factory=list)
    expires_at: datetime | None = None


class CreateExport(BaseModel):
    format: str = "csv"
    document_ids: list[str] | None = None
    status: str | None = None


@router.post("/api-keys", status_code=201, response_model=ApiKeyCreated)
def create_api_key(
    payload: CreateKey,
    principal: Annotated[Principal, Depends(session_principal)],
    state: AppState = Depends(get_state),
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """Issue a key. The `key` field in this response is the only copy.

    What is stored is `HMAC-SHA256(server_pepper, key)`. So a lost key cannot be
    recovered -- only revoked and replaced -- and a stolen database cannot be
    replayed against the API.
    """
    if payload.mode not in ("live", "test"):
        raise problems.invalid('mode must be "live" or "test"')
    for ref in payload.schema_versions:
        if repo.schema_version(ref.schema_id, ref.version) is None:
            raise problems.not_found("schema version %s@%d"
                                     % (ref.schema_id, ref.version))
    key_id = new_api_key_id()
    issued = key_tools.generate_key(payload.mode, state.settings.key_pepper, key_id)
    repo.create_api_key(
        id=key_id, name=payload.name, prefix=issued.prefix,
        key_hash=issued.key_hash, mode=payload.mode,
        schema_versions=[ref.model_dump() for ref in payload.schema_versions],
        rate_limit_per_minute=state.settings.rate_limit_per_minute,
        expires_at=payload.expires_at,
    )
    # The prefix, never the key: an audit row is read by people who should not be
    # able to use what they are reading.
    repo.audit(principal.actor, "key_created", "api_key", key_id,
               {"mode": payload.mode, "prefix": issued.prefix})
    return {"id": key_id, "prefix": issued.prefix, "mode": payload.mode,
            "key": issued.secret,
            "detail": "store this key now; it is not retrievable"}


@router.get("/api-keys", response_model=list[ApiKeyView])
def list_api_keys(
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> list[dict[str, Any]]:
    return [views.api_key_view(row) for row in repo.list_api_keys()]


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: str,
    principal: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> Response:
    if repo.api_key(key_id) is None:
        raise problems.not_found("api key")
    repo.revoke_api_key(key_id)
    repo.audit(principal.actor, "key_revoked", "api_key", key_id, {})
    return Response(status_code=204)


@router.post("/exports", status_code=201, response_model=ExportJob)
def create_export(
    payload: CreateExport,
    principal: Annotated[Principal, Depends(session_principal)],
    state: AppState = Depends(get_state),
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """Build the file now, synchronously.

    An export of a few thousand rows takes well under a second, and a background
    job for it would need its own state machine for no gain. `GET /exports/{id}`
    exists anyway so the UI does not have to care which it is.
    """
    if payload.format not in ("csv", "xlsx"):
        raise problems.invalid('format must be "csv" or "xlsx"')

    if payload.document_ids:
        documents = []
        for document_id in payload.document_ids:
            row = repo.document(document_id)
            if row is None:
                raise problems.not_found("document " + document_id)
            documents.append(row)
    else:
        wanted = payload.status
        if wanted and wanted not in EXPORTABLE_STATUSES:
            raise problems.invalid(
                "status must be one of " + ", ".join(EXPORTABLE_STATUSES)
            )
        documents = [
            row for row in repo.list_documents(status=wanted, limit=200)
            if str(row["status"]) in EXPORTABLE_STATUSES
        ]

    records = []
    for document in documents:
        extraction = repo.latest_extraction(str(document["id"]))
        if extraction is None:
            continue
        records.append((dict(document), dict(extraction)))

    export_id = repo.create_export(
        format=payload.format, status="pending",
        document_ids=[str(row["id"]) for row in documents],
        filter_status=payload.status,
    )
    try:
        # One export can span several schemas, so the display formats are
        # resolved per extraction. They reach the spreadsheet only: the API
        # stays ISO dates and decimal strings whatever a schema asks for.
        display_formats: dict[str, Any] = {}
        for _doc, record in records:
            record_schema = record.get("schema_id")
            record_version = record.get("schema_version")
            if not record_schema or not record_version:
                continue
            version_row = repo.schema_version(str(record_schema),
                                              int(record_version))
            if version_row and version_row["field_config"]:
                display_formats[str(record.get("id"))] = version_row["field_config"]
        content = export_tools.render(payload.format, records,
                                      display_formats)
    except Exception as error:
        repo.update_export(export_id, status="failed",
                           error_code=ErrorCode.INTERNAL.value, finished_at=now())
        raise problems.Problem(500, ErrorCode.INTERNAL.value,
                               "the export could not be built") from error
    path = state.settings.export_dir / ("%s.%s" % (export_id, payload.format))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    repo.update_export(export_id, status="ready", row_count=len(records),
                       blob_path=str(path), finished_at=now())
    repo.audit(principal.actor, "exported", "export", export_id,
               {"format": payload.format, "documents": len(records)})
    return {"export_id": export_id, "status": "ready", "row_count": len(records)}


@router.get("/exports/{export_id}")
def get_export(
    export_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> Response:
    row = repo.export(export_id)
    if row is None:
        raise problems.not_found("export")
    if str(row["status"]) != "ready" or not row["blob_path"]:
        raise problems.Problem(
            409, ErrorCode.EXPORT_NOT_READY.value,
            "the export is %s" % str(row["status"]),
        )
    fmt = str(row["format"])
    from pathlib import Path

    path = Path(str(row["blob_path"]))
    if not path.is_file():
        raise problems.not_found("export file")
    return Response(
        content=path.read_bytes(),
        media_type=export_tools.MEDIA_TYPES[fmt],
        headers={
            "Content-Disposition": 'attachment; filename="fdip-%s.%s"'
                                   % (export_id, fmt),
        },
    )


@router.get("/usage", response_model=Usage)
def usage(
    _: Annotated[Principal, Depends(session_principal)],
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    key = month or now().strftime("%Y-%m")
    return views.usage_view(key, repo.usage(key))


@router.get("/jobs/{job_id}", response_model=JobView)
def get_job(
    job_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    row = repo.job(job_id)
    if row is None:
        raise problems.not_found("job")
    return views.job_view(row)


@router.get("/health", response_model=Health)
def health(state: AppState = Depends(get_state),
           connection: Any = Depends(db_connection)) -> dict[str, Any]:
    """Unauthenticated on purpose: a health check behind a login is not one.

    Which means a stranger reads this, so it answers two questions and no
    others: is the database reachable, and is the worker alive. The provider
    name and model are gone — operationally interesting, but they tell an
    outsider what to attack and the operator can read them from the
    environment. No counts, which would leak volume.

    The worker is reported as the **age** of its last lease rather than a
    timestamp, because "47 seconds ago" is what an alert threshold compares
    against, and a clock-skewed timestamp is not.
    """
    from datetime import UTC, datetime

    from sqlalchemy import text

    database_ok = True
    try:
        connection.execute(text("select 1"))
    except Exception:
        database_ok = False

    heartbeat = None
    age_seconds = None
    if database_ok:
        heartbeat = GlobalRepository(connection).worker_heartbeat()
        if heartbeat is not None:
            now = datetime.now(UTC).replace(tzinfo=None)
            age_seconds = max(0.0, (now - heartbeat).total_seconds())

    return {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "worker_heartbeat_age_seconds": age_seconds,
        "pipeline_version": _pipeline_version(),
        # The UI needs this before anyone has signed in, to decide whether to
        # offer a sign-up link at all.
        "allow_registration": state.settings.allow_registration,
    }


def _pipeline_version() -> str:
    from fdip import PIPELINE_VERSION

    return PIPELINE_VERSION


__all__ = ["router"]
