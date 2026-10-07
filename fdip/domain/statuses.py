"""The closed vocabularies the API and the UI share.

These are strings on the wire, so they live in one module and nowhere else. A
status invented at a call site is the failure this prevents: the UI switches on
these values and an unknown one renders as nothing at all.

`StrEnum` rather than `(str, Enum)`, which is what the toolkit uses on its 3.10
target: under 3.11 an f-string of a `(str, Enum)` member renders as
`Status.COMPLETED` instead of `completed`, and that reaches a response body the
first time someone interpolates one. `.value` is still used explicitly wherever
the string is the payload.
"""
from __future__ import annotations

from enum import StrEnum


class DocumentType(StrEnum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    RECEIPT = "receipt"
    PURCHASE_ORDER = "purchase_order"
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"
    UNKNOWN = "unknown"


CLASSIFIER_LABELS: tuple[str, ...] = tuple(t.value for t in DocumentType)

INVOICE_LIKE: frozenset[str] = frozenset(
    {DocumentType.INVOICE.value, DocumentType.CREDIT_NOTE.value}
)
"""Credit notes run the invoice template: the fields are the same and the signs
are handled by the validators, not by a second template."""


class Status(StrEnum):
    """The status the UI polls on. `processing` is the only non-terminal one."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    DOCUMENT_TYPE_MISMATCH = "document_type_mismatch"
    REJECTED = "rejected"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


TERMINAL_STATUSES: frozenset[str] = frozenset(
    s.value for s in Status if s is not Status.PROCESSING
)


class JobState(StrEnum):
    RECEIVED = "received"
    PROBED = "probed"
    PARSED = "parsed"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    DECIDED = "decided"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    CANCELLED = "cancelled"


class FieldStatus(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    MISSING = "missing"
    CORRECTED = "corrected"


class MatchClass(StrEnum):
    """Mirrors the toolkit's own class plus `derived`, which is FDIP's call.

    The toolkit cannot know that `total` may be computed from subtotal and tax:
    that is a financial rule, so `derived` is decided here (CLAUDE.md 2.1).
    """

    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY_OCR = "fuzzy_ocr"
    DERIVED = "derived"
    NOT_FOUND = "not_found"
    NOT_CHECKED = "not_checked"


GROUNDED_MATCHES: frozenset[str] = frozenset(
    {MatchClass.EXACT.value, MatchClass.NORMALIZED.value, MatchClass.DERIVED.value}
)
"""The classes 3.6 counts as grounded. `fuzzy_ocr` is deliberately absent: a
possible OCR misread goes to review rather than straight through."""


class ErrorCode(StrEnum):
    """RFC 9457 `code` values. The UI must handle every one of these."""

    UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
    ENCRYPTED_PDF = "encrypted_pdf"
    EMPTY_FILE = "empty_file"
    CORRUPT_FILE = "corrupt_file"
    FILE_TOO_LARGE = "file_too_large"
    PAGE_LIMIT_EXCEEDED = "page_limit_exceeded"
    SCHEMA_VERSION_NOT_ALLOWED = "schema_version_not_allowed"
    SCHEMA_TEST_RUN_REQUIRED = "schema_test_run_required"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    INVALID_REQUEST = "invalid_request"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_DECIDED = "already_decided"
    EXPORT_NOT_READY = "export_not_ready"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INTERNAL = "internal"


POISON_CODES: frozenset[str] = frozenset({
    ErrorCode.EMPTY_FILE.value,
    ErrorCode.CORRUPT_FILE.value,
    ErrorCode.ENCRYPTED_PDF.value,
    ErrorCode.FILE_TOO_LARGE.value,
    ErrorCode.PAGE_LIMIT_EXCEEDED.value,
    ErrorCode.UNSUPPORTED_FILE_TYPE.value,
})
"""Never retried (3.9). Retrying a corrupt file just burns the budget."""


__all__ = [
    "CLASSIFIER_LABELS",
    "DocumentType",
    "ErrorCode",
    "FieldStatus",
    "GROUNDED_MATCHES",
    "INVOICE_LIKE",
    "JobState",
    "MatchClass",
    "POISON_CODES",
    "Status",
    "TERMINAL_STATUSES",
]
