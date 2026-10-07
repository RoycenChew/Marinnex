"""RFC 9457 problem details, with the `code` the UI switches on.

The `code` field is the contract, not the HTTP status and not the prose. A UI
that branches on `detail` strings breaks the first time someone improves the
wording, so every error carries a machine-readable code from the closed set in
`domain.statuses`.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from fdip.domain.statuses import ErrorCode

CONTENT_TYPE = "application/problem+json"

_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    413: "Payload Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


class Problem(HTTPException):
    """An HTTPException that carries a code and renders as problem+json."""

    def __init__(self, status_code: int, code: str, detail: str,
                 **extra: Any) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.extra = extra

    def body(self, instance: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "https://fdip.local/problems/" + self.code,
            "title": _TITLES.get(self.status_code, "Error"),
            "status": self.status_code,
            "detail": self.detail,
            "code": self.code,
        }
        if instance:
            payload["instance"] = instance
        payload.update(self.extra)
        return payload


def not_found(what: str = "resource") -> Problem:
    """Always 404, never 403, for something in another project.

    Telling an attacker that a document exists but is not theirs is itself the
    leak, so a cross-project read is indistinguishable from a wrong id.
    """
    return Problem(404, ErrorCode.NOT_FOUND.value, "no such %s" % what)


def unauthenticated(detail: str = "authentication is required") -> Problem:
    return Problem(401, ErrorCode.UNAUTHENTICATED.value, detail)


def forbidden(detail: str) -> Problem:
    return Problem(403, ErrorCode.FORBIDDEN.value, detail)


def invalid(detail: str, **extra: Any) -> Problem:
    return Problem(422, ErrorCode.INVALID_REQUEST.value, detail, **extra)


def conflict(code: str, detail: str, **extra: Any) -> Problem:
    return Problem(409, code, detail, **extra)


def rate_limited(retry_after: int = 60) -> Problem:
    return Problem(429, ErrorCode.RATE_LIMITED.value,
                   "too many requests; retry in %d seconds" % retry_after,
                   retry_after=retry_after)


def quota_exceeded(detail: str) -> Problem:
    return Problem(429, ErrorCode.QUOTA_EXCEEDED.value, detail)


def unsupported(code: str, detail: str) -> Problem:
    return Problem(415, code, detail)


def too_large(detail: str) -> Problem:
    return Problem(413, ErrorCode.FILE_TOO_LARGE.value, detail)


async def problem_handler(request: Request, exc: Exception) -> JSONResponse:
    problem = exc if isinstance(exc, Problem) else None
    if problem is None and isinstance(exc, HTTPException):
        problem = Problem(
            exc.status_code,
            _code_for_status(exc.status_code),
            str(exc.detail),
        )
    if problem is None:
        problem = Problem(500, ErrorCode.INTERNAL.value, "an internal error occurred")
    return JSONResponse(
        status_code=problem.status_code,
        content=problem.body(instance=str(request.url.path)),
        media_type=CONTENT_TYPE,
        headers=(
            {"Retry-After": str(problem.extra["retry_after"])}
            if "retry_after" in problem.extra else None
        ),
    )


def _code_for_status(status: int) -> str:
    return {
        400: ErrorCode.INVALID_REQUEST.value,
        401: ErrorCode.UNAUTHENTICATED.value,
        403: ErrorCode.FORBIDDEN.value,
        404: ErrorCode.NOT_FOUND.value,
        409: ErrorCode.IDEMPOTENCY_CONFLICT.value,
        413: ErrorCode.FILE_TOO_LARGE.value,
        415: ErrorCode.UNSUPPORTED_FILE_TYPE.value,
        422: ErrorCode.INVALID_REQUEST.value,
        429: ErrorCode.RATE_LIMITED.value,
    }.get(status, ErrorCode.INTERNAL.value)


__all__ = [
    "CONTENT_TYPE",
    "Problem",
    "conflict",
    "forbidden",
    "invalid",
    "not_found",
    "problem_handler",
    "quota_exceeded",
    "rate_limited",
    "too_large",
    "unauthenticated",
    "unsupported",
]
