"""Pure domain logic: no FastAPI, no SQLAlchemy, no HTTP.

The import-graph test in `tests/` enforces that, because the moment a
validator imports a request object the rule stops being testable without a
server.
"""
from __future__ import annotations

from fdip.domain.decision import Decision, FieldSignal, decide, field_status
from fdip.domain.money import Money, close_enough, quantise, to_decimal
from fdip.domain.schema_lang import (
    LocaleHints,
    SchemaSpec,
    to_extraction_schema,
    to_response_contract,
)
from fdip.domain.statuses import (
    DocumentType,
    ErrorCode,
    FieldStatus,
    JobState,
    MatchClass,
    Status,
)
from fdip.domain.templates import INVOICE_TEMPLATE_FIELDS, TemplateField, flatten
from fdip.domain.validators import ValidationResult, validate

__all__ = [
    "INVOICE_TEMPLATE_FIELDS",
    "Decision",
    "DocumentType",
    "ErrorCode",
    "FieldSignal",
    "FieldStatus",
    "JobState",
    "LocaleHints",
    "MatchClass",
    "Money",
    "SchemaSpec",
    "Status",
    "TemplateField",
    "ValidationResult",
    "close_enough",
    "decide",
    "field_status",
    "flatten",
    "quantise",
    "to_decimal",
    "to_extraction_schema",
    "to_response_contract",
    "validate",
]
