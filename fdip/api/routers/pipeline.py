"""`POST /extract`: the pipeline call customers integrate against.

Three things distinguish it from an interactive upload.

* It runs the **requested schema version**, not the full template, and the type
  gate is enforced: a bank statement sent to an invoice schema returns
  `document_type_mismatch` rather than fourteen nulls.
* The version must have **passed a test run** (3.7), and the key must be allowed
  to use it.
* `?wait=30` runs the job inline and returns `200` with the result if it finishes
  in time, otherwise `202`. Inline rather than waiting on the worker because a
  customer who asked to wait wants the answer, not a poll loop, and a job that
  the API is already blocked on gains nothing from a queue hop.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from fdip.adapters import sandbox
from fdip.adapters.providers import build_model_stack
from fdip.adapters.repository import ProjectRepository
from fdip.adapters.storage import sha256_bytes
from fdip.api import problems, views
from fdip.api.deps import (
    AppState,
    Principal,
    db_connection,
    effective_provider_mode,
    get_state,
    key_principal,
    key_repository,
    limit_by_ip,
    release_write_lock,
)
from fdip.api.routers.schemas import require_tested_version
from fdip.domain.statuses import ErrorCode, JobState, Status
from fdip.pipeline.runner import JobContext, run_id_for, run_job, spec_from_version

router = APIRouter(tags=["pipeline"])

MAX_WAIT_SECONDS = 60


@router.post("/extract", status_code=202)
async def extract(
    request: Request,
    principal: Annotated[Principal, Depends(key_principal)],
    file: UploadFile = File(...),
    schema_id: str = Form(...),
    schema_version: int = Form(...),
    wait: int = Query(default=0, ge=0, le=MAX_WAIT_SECONDS),
    state: AppState = Depends(get_state),
    repo: ProjectRepository = Depends(key_repository),
    connection: Any = Depends(db_connection),
) -> Any:
    if not principal.may_use(schema_id, schema_version):
        raise problems.Problem(
            403, ErrorCode.SCHEMA_VERSION_NOT_ALLOWED.value,
            "this key may not use %s version %d" % (schema_id, schema_version),
        )
    stored = require_tested_version(repo, schema_id, schema_version)

    # The key already has its own per-minute allowance. This is the second
    # bound: one address cannot exhaust the service with many keys.
    limit_by_ip(request, state, "extract", state.settings.uploads_per_minute)
    data = await file.read()
    if not data:
        raise problems.unsupported(ErrorCode.EMPTY_FILE.value, "the file is empty")
    if len(data) > state.settings.max_upload_bytes:
        raise problems.too_large(
            "the file is %.1f MB and the limit is %.1f MB"
            % (len(data) / 1e6, state.settings.max_upload_bytes / 1e6)
        )
    filename = (file.filename or "upload.pdf")[:400]
    try:
        mime = sandbox.sniff_mime(data, filename)
    except sandbox.UnsupportedDocument as error:
        raise problems.unsupported(error.code, error.reason) from error

    quota = _check_quota(repo, state, principal)
    digest = sha256_bytes(data)
    _, blob_path = state.blobs.put(data)

    existing = repo.document_by_hash(digest)
    if existing is not None:
        document_id = str(existing["id"])
    else:
        document_id = repo.create_document(
            filename=filename, mime=mime, byte_size=len(data), sha256=digest,
            blob_path=blob_path, status=Status.PROCESSING.value, origin="api",
        )
    job_id = repo.create_job(
        document_id=document_id,
        run_id=run_id_for(digest, "pipeline", schema_version, schema_id),
        state=JobState.RECEIVED.value, mode="pipeline",
        schema_id=schema_id, schema_version=schema_version,
    )
    repo.audit(principal.actor, "extract_requested", "document", document_id,
               {"schema_id": schema_id, "schema_version": schema_version,
                "wait": wait, "pages_remaining": quota})

    if not wait:
        return JSONResponse(status_code=202, content={
            "document_id": document_id, "job_id": job_id,
            "status": Status.PROCESSING.value,
        })

    # Release the write lock before the slow part. SQLite has one writer, and the
    # pipeline below opens its own connections; without this the request
    # deadlocks against itself.
    release_write_lock(connection)

    # Inline. The worker would also pick this job up, but the durable run id
    # makes that harmless: whichever gets there second replays the checkpoints.
    spec = spec_from_version({**stored, "name": "Invoice",
                              "document_type": "invoice"})
    # A test key must not reach the live provider, whatever the server is
    # configured for, so the mode is narrowed for this call only.
    settings = replace(
        state.settings,
        provider_mode=effective_provider_mode(state.settings, principal),
    )
    models = build_model_stack(settings, already_spent_usd=repo.month_ai_cost())
    outcome = run_job(JobContext(
        engine=state.engine, settings=settings, models=models,
        project_id=principal.project_id, document_id=document_id, job_id=job_id,
        blob_path=blob_path, spec=spec, purpose="pipeline",
        schema_id=schema_id, schema_version=schema_version,
        expected_type=str(stored.get("document_type") or "invoice"),
        api_key_id=principal.api_key_id,
    ), digest)

    extraction_id = outcome.get("extraction_id")
    if not extraction_id:
        return JSONResponse(status_code=202, content={
            "document_id": document_id, "job_id": job_id,
            "status": outcome.get("status", Status.PROCESSING.value),
            "error_code": outcome.get("error_code"),
        })
    extraction = repo.extraction(str(extraction_id))
    if extraction is None:  # pragma: no cover - just written in this transaction
        raise problems.not_found("extraction")
    aliases, custom = views.presentation_for(repo, extraction)
    return JSONResponse(
        status_code=200,
        content=views.extraction_view(repo, extraction, aliases=aliases,
                                      custom_names=custom),
    )


def _check_quota(repo: ProjectRepository, state: AppState,
                 principal: Principal) -> int:
    """Pages used this month against the project's quota.

    Checked before the work, not after: a quota that only reports an overrun has
    not limited anything.
    """
    allowed = repo.monthly_page_quota()
    if allowed <= 0:
        return 0
    used = sum(int(row["pages"]) for row in repo.usage())
    if used >= allowed:
        raise problems.quota_exceeded(
            "the project has used %d of %d pages this month" % (used, allowed)
        )
    spent = repo.month_ai_cost()
    if spent >= state.settings.monthly_ceiling_usd:
        raise problems.quota_exceeded(
            "the monthly AI ceiling of USD %.2f has been reached"
            % state.settings.monthly_ceiling_usd
        )
    return allowed - used


__all__ = ["router"]
