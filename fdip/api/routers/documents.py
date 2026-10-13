"""Interactive documents: upload, poll, page images, analysis, delete.

Upload is the one route with real subtlety, and it is all about doing the same
work twice.

* **Content hash.** The same bytes in the same project are one document (3.3
  stage 1), so a re-upload returns the existing document and its job rather than
  paying for a second extraction.
* **Idempotency key.** The same key with the same body returns the original job;
  the same key with a *different* body is `409` (3.7). The body is fingerprinted
  by content hash plus filename, so a retried upload after a dropped connection
  is free and a mistake is loud.

Upload does not extract. It stores the bytes, creates the job and returns `202`;
the worker does the work. That is what keeps a 25-page scan from holding an HTTP
connection open for a minute.
"""
from __future__ import annotations

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import Response

from fdip.adapters import sandbox
from fdip.adapters.repository import ProjectRepository
from fdip.adapters.storage import sha256_bytes
from fdip.api import problems, views
from fdip.api.deps import (
    AppState,
    Principal,
    get_state,
    limit_by_ip,
    repository,
    session_principal,
)
from fdip.api.schemas import (
    DocumentDetail,
    DocumentList,
    Extraction,
    PendingAnalysis,
    UploadAccepted,
)
from fdip.domain.statuses import ErrorCode, JobState, Status
from fdip.pipeline.runner import run_id_for

router = APIRouter(tags=["documents"])


def _fingerprint(digest: str, filename: str) -> str:
    return hashlib.sha256(("%s|%s" % (digest, filename)).encode("utf-8")).hexdigest()


@router.post("/documents", status_code=202, response_model=UploadAccepted)
async def upload(
    request: Request,
    principal: Annotated[Principal, Depends(session_principal)],
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    state: AppState = Depends(get_state),
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    # Before the body is read: a flood of 20 MB uploads should be refused
    # before it is buffered, not after.
    limit_by_ip(request, state, "upload", state.settings.uploads_per_minute)
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
        # Refused here rather than in the worker: there is no point storing bytes
        # and creating a job for a file we already know will not parse.
        raise problems.unsupported(error.code, error.reason) from error

    digest = sha256_bytes(data)
    fingerprint = _fingerprint(digest, filename)

    if idempotency_key:
        existing = repo.document_by_idempotency_key(idempotency_key)
        if existing is not None:
            if str(existing["request_fingerprint"] or "") != fingerprint:
                raise problems.conflict(
                    ErrorCode.IDEMPOTENCY_CONFLICT.value,
                    "that Idempotency-Key was used for a different file",
                )
            job = repo.job_for_document(str(existing["id"]))
            return {
                "document_id": str(existing["id"]),
                "job_id": None if job is None else str(job["id"]),
                "status": str(existing["status"]),
                "reused": True,
            }

    duplicate = repo.document_by_hash(digest)
    if duplicate is not None:
        # Same bytes, already in this project. Return it instead of extracting
        # again; the client gets the job it can poll either way.
        job = repo.job_for_document(str(duplicate["id"]))
        if idempotency_key and not duplicate["idempotency_key"]:
            repo.update_document(
                str(duplicate["id"]), idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
        return {
            "document_id": str(duplicate["id"]),
            "job_id": None if job is None else str(job["id"]),
            "status": str(duplicate["status"]),
            "reused": True,
        }

    _, blob_path = state.blobs.put(data)
    document_id = repo.create_document(
        filename=filename, mime=mime, byte_size=len(data), sha256=digest,
        blob_path=blob_path, status=Status.PROCESSING.value,
        origin="interactive", idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    job_id = repo.create_job(
        document_id=document_id,
        run_id=run_id_for(digest, "analysis"),
        state=JobState.RECEIVED.value, mode="interactive",
    )
    repo.audit(principal.actor, "uploaded", "document", document_id,
               {"byte_size": len(data), "mime": mime})
    return {"document_id": document_id, "job_id": job_id,
            "status": Status.PROCESSING.value, "reused": False}


@router.get("/documents", response_model=DocumentList)
def list_documents(
    _: Annotated[Principal, Depends(session_principal)],
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    rows = repo.list_documents(status=status, limit=limit + 1, cursor=cursor)
    has_more = len(rows) > limit
    page = rows[:limit]
    return {
        "items": [views.document_list_item(row) for row in page],
        "next_cursor": str(page[-1]["id"]) if has_more and page else None,
    }


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    document = repo.document(document_id)
    if document is None:
        raise problems.not_found("document")
    return views.document_view(
        document,
        job=repo.job_for_document(document_id),
        classification=repo.classification(document_id),
        decision=str(document["status"]),
    )


@router.get("/documents/{document_id}/pages/{page_number}/image")
def page_image(
    document_id: str,
    page_number: int,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> Response:
    """One page as a PNG at 150 DPI.

    Cached for a day by content: the bytes for a page of an immutable document
    never change, and the UI requests the same page on every box hover.
    """
    document = repo.document(document_id)
    if document is None:
        raise problems.not_found("document")
    try:
        png = sandbox.render_page_png(
            str(document["blob_path"]), page_number, views.PAGE_IMAGE_DPI
        )
    except sandbox.UnsupportedDocument as error:
        raise problems.not_found("page") from error
    except Exception as error:
        raise problems.Problem(
            415, ErrorCode.UNSUPPORTED_FILE_TYPE.value,
            "this document cannot be rendered as an image",
        ) from error
    return Response(
        content=png, media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=86400, immutable",
            "X-Page-Dpi": str(views.PAGE_IMAGE_DPI),
        },
    )


@router.get("/documents/{document_id}/file")
def original_file(
    document_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    state: AppState = Depends(get_state),
    repo: ProjectRepository = Depends(repository),
) -> Response:
    document = repo.document(document_id)
    if document is None:
        raise problems.not_found("document")
    try:
        data = state.blobs.get(str(document["blob_path"]))
    except OSError as error:
        raise problems.not_found("file") from error
    return Response(
        content=data, media_type=str(document["mime"]),
        headers={
            # `inline` so the UI can preview it; the filename is quoted because
            # an uploaded name can contain a space or a comma.
            "Content-Disposition": 'inline; filename="%s"'
                                   % str(document["filename"]).replace('"', ""),
        },
    )


@router.get(
    "/documents/{document_id}/analysis",
    # Either a finished extraction or the pending placeholder, which is
    # why this is a union rather than one model.
    response_model=Extraction | PendingAnalysis,
)
def analysis(
    document_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """The full-template extraction behind an interactive upload.

    `suggested_fields` is the grounded subset: the paths the model found *and*
    deterministic code located on the page. That is the list the UI pre-ticks
    when the user turns this document into a schema.
    """
    document = repo.document(document_id)
    if document is None:
        raise problems.not_found("document")
    extraction = repo.latest_extraction(document_id, purpose="analysis")
    if extraction is None:
        job = repo.job_for_document(document_id)
        return {
            "document_id": document_id,
            "status": str(document["status"]),
            "job": None if job is None else views.job_view(job),
            "data": {}, "fields": {}, "validation": [],
            "suggested_fields": [],
            "detail": "the analysis has not finished; poll this endpoint",
        }
    labels, custom = views.presentation_for(repo, extraction)
    return views.extraction_view(repo, extraction, include_suggested=True,
                                 labels=labels, custom_names=custom)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    principal: Annotated[Principal, Depends(session_principal)],
    state: AppState = Depends(get_state),
    repo: ProjectRepository = Depends(repository),
) -> Response:
    """Cascades to every derived row, and removes the stored bytes.

    The blob is deleted only if no other document in any project references the
    same hash, which content addressing makes possible to check.
    """
    document = repo.document(document_id)
    if document is None:
        raise problems.not_found("document")
    digest = str(document["sha256"])
    repo.soft_delete_document(document_id)
    if not repo.hash_in_use(digest):
        state.blobs.delete(digest)
    repo.audit(principal.actor, "deleted", "document", document_id, {})
    return Response(status_code=204)


__all__ = ["router"]
