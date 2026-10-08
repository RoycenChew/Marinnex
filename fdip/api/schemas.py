"""Response models.

Every route used to be annotated `-> dict[str, Any]`, so `openapi.json` described
each 200 body as a free-form object and the generated TypeScript client typed them
all as `{[key: string]: unknown}` -- no type safety at all on the data the product
exists to display. The UI worked around it by hand-writing the shapes, which is a
stub that drifts.

These models are transcribed from `fdip/api/views.py`, which already builds every
response dict in one place, so they are a description of existing behaviour rather
than a change to it.

Two conventions carried from the contract:

* **Decimals are strings.** A JSON number is a float on the other side and
  `12611.70` does not survive the round trip (rule 2.2), so every money field is
  typed `str`, never `float`.
* **`extra="allow"` where a body is open-ended.** `data` holds whatever the
  schema version selected, and `fields` is keyed by path. Pinning those to a
  closed set here would contradict the per-version contract that
  `GET /schemas/{id}/versions/{v}/contract` publishes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Problem(BaseModel):
    """RFC 9457. `code` is the field clients branch on."""

    type: str
    title: str
    status: int
    detail: str
    code: str
    instance: str | None = None

    model_config = ConfigDict(extra="allow")


# -- auth ----------------------------------------------------------------

class SessionUser(BaseModel):
    id: str
    email: str


class ProjectRef(BaseModel):
    id: str
    name: str


class MeResponse(BaseModel):
    user: SessionUser
    projects: list[ProjectRef]


# -- documents -----------------------------------------------------------

class JobView(BaseModel):
    id: str
    document_id: str | None = None
    state: str
    stage: str | None = None
    attempts: int
    error_code: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class ClassificationView(BaseModel):
    confidence: float | None = None
    source: str


class UploadAccepted(BaseModel):
    document_id: str
    job_id: str | None = None
    status: str
    reused: bool


class DocumentListItem(BaseModel):
    id: str
    filename: str
    status: str
    document_type: str | None = None
    pages: int
    created_at: datetime | None = None
    decision: str | None = None


class DocumentList(BaseModel):
    items: list[DocumentListItem]
    next_cursor: str | None = None


class DocumentDetail(BaseModel):
    id: str
    filename: str
    mime: str
    pages: int
    page_sizes: dict[str, list[float]]
    status: str
    error_code: str | None = None
    document_type: str | None = None
    classification_confidence_source: ClassificationView | None = None
    job: JobView | None = None
    decision: str | None = None
    created_at: datetime | None = None
    page_image_dpi: int


# -- extractions ---------------------------------------------------------

class EvidenceView(BaseModel):
    page: int
    bbox: list[float] | None = None
    source: str
    ocr_confidence: float | None = None


class FieldEntry(BaseModel):
    value: Any = None
    raw_text: str | None = None
    status: str
    match: str
    evidence: list[EvidenceView]
    reasons: list[str]


class ValidationView(BaseModel):
    code: str
    severity: str
    path: str | None = None
    message: str


class SchemaRef(BaseModel):
    id: str
    version: int


class Extraction(BaseModel):
    extraction_id: str
    document_id: str
    version: int
    status: str
    document_type: str | None = None
    schema_: SchemaRef = Field(alias="schema")
    currency: str | None = None
    # Open by design: the keys are whatever the schema version selected, and the
    # per-version contract is what describes them.
    data: dict[str, Any]
    fields: dict[str, FieldEntry]
    validation: list[ValidationView]
    reasons: list[str]
    pipeline_version: str
    created_at: datetime | None = None
    suggested_fields: list[str] | None = None

    # `schema` shadows a BaseModel attribute, so it is aliased internally and
    # serialised back under its real name.
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class PendingAnalysis(BaseModel):
    """What `/analysis` returns before the worker has finished."""

    document_id: str
    status: str
    job: JobView | None = None
    data: dict[str, Any]
    fields: dict[str, FieldEntry]
    validation: list[ValidationView]
    suggested_fields: list[str]
    detail: str


class DecisionResult(BaseModel):
    extraction_id: str
    status: str


# -- templates and schemas ----------------------------------------------

class TemplateField(BaseModel):
    path: str
    label: str
    type: str
    description: str
    required_default: bool
    is_array: bool
    enum: list[str] | None = None
    money: bool | None = None
    grounding: str | None = None


class Template(BaseModel):
    id: str
    document_type: str
    version: int
    name: str
    description: str
    fields: list[TemplateField]


class SchemaVersionView(BaseModel):
    version: int
    created_at: datetime | None = None
    test_run_status: str
    fields: list[str]
    locale_hints: dict[str, str]


class SchemaView(BaseModel):
    schema_id: str
    name: str
    document_type: str
    template_id: str
    current_version: int
    created_at: datetime | None = None
    #: Set means archived: hidden from the default list and closed to new work.
    archived_at: datetime | None = None
    versions: list[SchemaVersionView] = Field(default_factory=list)


class SchemaCreated(BaseModel):
    schema_id: str
    version: int


class TestRunDocument(BaseModel):
    document_id: str
    status: str
    fields_ok: int
    fields_total: int


class TestRun(BaseModel):
    test_run_id: str
    schema_id: str
    version: int
    status: str
    passed: bool
    per_document: list[TestRunDocument]
    created_at: datetime | None = None
    finished_at: datetime | None = None


# -- keys, exports, usage, health ---------------------------------------

class ApiKeyView(BaseModel):
    id: str
    name: str
    prefix: str
    mode: Literal["live", "test"]
    schema_versions: list[dict[str, Any]]
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime | None = None
    status: Literal["active", "expired", "revoked"]


class ApiKeyCreated(BaseModel):
    """The only response that carries the key, and only once."""

    id: str
    prefix: str
    mode: Literal["live", "test"]
    key: str
    detail: str


class ExportJob(BaseModel):
    export_id: str
    status: str
    row_count: int


class UsageByKey(BaseModel):
    api_key_id: str | None = None
    pages: int
    documents: int
    ai_cost_usd: float


class Usage(BaseModel):
    month: str
    pages: int
    documents: int
    ai_cost_usd: float
    by_key: list[UsageByKey]


class Health(BaseModel):
    status: str
    database: str
    provider_mode: str
    model: str
    extract_thinking: str
    worker_last_lease: str | None = None
    pipeline_version: str


__all__ = [
    "ApiKeyCreated",
    "ApiKeyView",
    "ClassificationView",
    "DecisionResult",
    "DocumentDetail",
    "DocumentList",
    "DocumentListItem",
    "EvidenceView",
    "ExportJob",
    "Extraction",
    "FieldEntry",
    "Health",
    "JobView",
    "MeResponse",
    "PendingAnalysis",
    "Problem",
    "ProjectRef",
    "SchemaCreated",
    "SchemaRef",
    "SchemaVersionView",
    "SchemaView",
    "SessionUser",
    "Template",
    "TemplateField",
    "TestRun",
    "TestRunDocument",
    "Usage",
    "UsageByKey",
    "ValidationView",
]
