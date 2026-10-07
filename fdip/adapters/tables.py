"""SQLAlchemy Core table definitions: the 21 tables of CLAUDE.md 3.8.

Core rather than the ORM on purpose. Every query in this backend is written by
hand in `repository.py` so that the `project_id` predicate is visible in the
source; a lazy-loading ORM relationship is exactly how an unscoped query gets
written by accident.

Three rules are structural here rather than conventional:

* **Every business row carries `project_id`.** Not just the top-level ones. An
  `evidence` row is reachable only through an extraction, but it still carries
  the project, because the test that proves scoping has to be able to ask the
  question of any table.
* **Extractions are immutable and versioned.** A correction never updates a row;
  it writes version n+1. `(document_id, version)` is unique.
* **Money is TEXT.** A Decimal in SQLite REAL is a float, and 12611.70 does not
  survive the round trip.
"""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()

_ID = String(40)
_MONEY = Text
"""A decimal as text. See the module docstring."""


def _created() -> Column:
    return Column("created_at", DateTime, nullable=False, server_default=func.now())


users = Table(
    "users", metadata,
    Column("id", _ID, primary_key=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
    _created(),
)

projects = Table(
    "projects", metadata,
    Column("id", _ID, primary_key=True),
    Column("owner_id", _ID, ForeignKey("users.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("name", String(200), nullable=False),
    Column("allowed_providers", JSON, nullable=False, default=list),
    Column("monthly_page_quota", Integer, nullable=False, default=10000),
    _created(),
    UniqueConstraint("owner_id", "name", name="uq_projects_owner_name"),
)

api_keys = Table(
    "api_keys", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, ForeignKey("projects.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("name", String(200), nullable=False),
    Column("prefix", String(32), nullable=False, index=True),
    Column("key_hash", String(64), nullable=False),
    # HMAC-SHA256(server pepper, secret), hex. The key itself is never stored,
    # so a database dump cannot be replayed against the API (rule 2.12).
    Column("mode", String(8), nullable=False),
    Column("schema_versions", JSON, nullable=False, default=list),
    Column("rate_limit_per_minute", Integer, nullable=False, default=60),
    Column("expires_at", DateTime, nullable=True),
    Column("revoked_at", DateTime, nullable=True),
    Column("last_used_at", DateTime, nullable=True),
    _created(),
    CheckConstraint("mode in ('live','test')", name="ck_api_keys_mode"),
)

documents = Table(
    "documents", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, ForeignKey("projects.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("filename", String(400), nullable=False),
    Column("mime", String(120), nullable=False, default="application/pdf"),
    Column("byte_size", Integer, nullable=False, default=0),
    Column("sha256", String(64), nullable=False),
    Column("blob_path", Text, nullable=False),
    Column("page_count", Integer, nullable=False, default=0),
    Column("page_sizes", JSON, nullable=False, default=dict),
    Column("status", String(32), nullable=False, default="processing"),
    Column("error_code", String(64), nullable=True),
    Column("document_type", String(32), nullable=True),
    Column("origin", String(16), nullable=False, default="interactive"),
    Column("idempotency_key", String(200), nullable=True),
    Column("request_fingerprint", String(64), nullable=True),
    Column("deleted_at", DateTime, nullable=True),
    _created(),
    # The same bytes uploaded twice in one project is one document (stage 1),
    # which is what makes re-upload free rather than a second AI call.
    UniqueConstraint("project_id", "sha256", name="uq_documents_project_hash"),
    UniqueConstraint("project_id", "idempotency_key",
                     name="uq_documents_project_idempotency"),
)

document_pages = Table(
    "document_pages", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("document_id", _ID, ForeignKey("documents.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("page_number", Integer, nullable=False),
    Column("width", Float, nullable=False),
    Column("height", Float, nullable=False),
    Column("rotation", Integer, nullable=False, default=0),
    Column("route", String(8), nullable=False, default="A"),
    Column("text_coverage", Float, nullable=False, default=0.0),
    Column("word_count", Integer, nullable=False, default=0),
    Column("min_ocr_confidence", Float, nullable=True),
    UniqueConstraint("document_id", "page_number", name="uq_pages_document_number"),
)

jobs = Table(
    "jobs", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("document_id", _ID, ForeignKey("documents.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("run_id", String(120), nullable=False, index=True),
    # document_hash + pipeline_version (3.9): the key that makes a restart
    # resume rather than start over.
    Column("state", String(32), nullable=False, default="received"),
    Column("stage", String(32), nullable=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("error_code", String(64), nullable=True),
    Column("error_detail", Text, nullable=True),
    Column("schema_id", _ID, nullable=True),
    Column("schema_version", Integer, nullable=True),
    Column("mode", String(16), nullable=False, default="interactive"),
    Column("leased_until", DateTime, nullable=True),
    Column("started_at", DateTime, nullable=True),
    Column("finished_at", DateTime, nullable=True),
    _created(),
    Index("ix_jobs_queue", "state", "created_at"),
)

classifications = Table(
    "classifications", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("document_id", _ID, ForeignKey("documents.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("label", String(32), nullable=False),
    Column("confidence", Float, nullable=True),
    Column("source", String(16), nullable=False, default="llm"),
    Column("classifier_version", String(40), nullable=False),
    _created(),
)

schema_templates = Table(
    "schema_templates", metadata,
    Column("id", _ID, primary_key=True),
    Column("document_type", String(32), nullable=False),
    Column("version", Integer, nullable=False, default=1),
    Column("name", String(200), nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("fields", JSON, nullable=False),
    _created(),
    UniqueConstraint("document_type", "version", name="uq_templates_type_version"),
)
"""The one global table without `project_id`: a template is FDIP's catalogue,
not a tenant's data."""

schemas = Table(
    "schemas", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, ForeignKey("projects.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("template_id", _ID, ForeignKey("schema_templates.id"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("document_type", String(32), nullable=False),
    Column("current_version", Integer, nullable=False, default=1),
    _created(),
    UniqueConstraint("project_id", "name", name="uq_schemas_project_name"),
)

schema_versions = Table(
    "schema_versions", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("schema_id", _ID, ForeignKey("schemas.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("fields", JSON, nullable=False),
    Column("locale_hints", JSON, nullable=False, default=dict),
    Column("template_version", Integer, nullable=False, default=1),
    Column("contract", JSON, nullable=False),
    Column("test_run_status", String(16), nullable=False, default="none"),
    _created(),
    UniqueConstraint("schema_id", "version", name="uq_schema_versions"),
)
"""Immutable. A change is a new row, because a customer's integration is pinned
to a version and must not change under them."""

schema_test_runs = Table(
    "schema_test_runs", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("schema_id", _ID, ForeignKey("schemas.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("status", String(16), nullable=False, default="running"),
    Column("passed", Boolean, nullable=False, default=False),
    Column("document_ids", JSON, nullable=False, default=list),
    Column("per_document", JSON, nullable=False, default=list),
    _created(),
    Column("finished_at", DateTime, nullable=True),
)

extractions = Table(
    "extractions", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("document_id", _ID, ForeignKey("documents.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("version", Integer, nullable=False),
    Column("schema_id", _ID, nullable=True),
    Column("schema_version", Integer, nullable=True),
    Column("template_version", Integer, nullable=False, default=1),
    Column("purpose", String(16), nullable=False, default="pipeline"),
    # "analysis" is the full-template run behind an interactive upload;
    # "pipeline" is a customer call against a chosen schema version.
    Column("status", String(32), nullable=False, default="processing"),
    Column("document_type", String(32), nullable=True),
    Column("currency", String(8), nullable=True),
    Column("data", JSON, nullable=False, default=dict),
    Column("reasons", JSON, nullable=False, default=list),
    Column("suggested_fields", JSON, nullable=False, default=list),
    Column("schema_valid", Boolean, nullable=False, default=True),
    Column("truncated", Boolean, nullable=False, default=False),
    Column("warnings", JSON, nullable=False, default=list),
    Column("attempts", Integer, nullable=False, default=1),
    # The reproducibility record (3.8). Without these an extraction cannot be
    # explained six months later, which is the whole point of storing it.
    Column("provider", String(40), nullable=False, default=""),
    Column("model", String(80), nullable=False, default=""),
    Column("model_version", String(120), nullable=False, default=""),
    Column("prompt_version", String(40), nullable=False, default=""),
    Column("classifier_version", String(40), nullable=False, default=""),
    Column("pipeline_version", String(40), nullable=False, default=""),
    Column("document_hash", String(64), nullable=False, default=""),
    Column("decision_rule_version", String(16), nullable=False, default=""),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("cost_usd", Float, nullable=False, default=0.0),
    Column("seconds", Float, nullable=False, default=0.0),
    _created(),
    UniqueConstraint("document_id", "version", "purpose",
                     name="uq_extractions_document_version"),
)

extraction_fields = Table(
    "extraction_fields", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("extraction_id", _ID, ForeignKey("extractions.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("path", String(200), nullable=False),
    Column("value_json", JSON, nullable=True),
    Column("value_text", _MONEY, nullable=True),
    Column("raw_text", Text, nullable=True),
    Column("status", String(16), nullable=False, default="accepted"),
    Column("match", String(16), nullable=False, default="not_checked"),
    Column("required", Boolean, nullable=False, default=False),
    Column("reasons", JSON, nullable=False, default=list),
    UniqueConstraint("extraction_id", "path", name="uq_fields_extraction_path"),
)

evidence = Table(
    "evidence", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("extraction_field_id", _ID,
           ForeignKey("extraction_fields.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("page", Integer, nullable=False),
    Column("x0", Float, nullable=True),
    Column("y0", Float, nullable=True),
    Column("x1", Float, nullable=True),
    Column("y1", Float, nullable=True),
    Column("source", String(16), nullable=False, default="text_layer"),
    Column("ocr_confidence", Float, nullable=True),
    Column("word_count", Integer, nullable=False, default=0),
)
"""Boxes only, never the words themselves: storing the matched text here would
put document content in a table the logs join against (rule 2.13)."""

validation_results = Table(
    "validation_results", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("extraction_id", _ID, ForeignKey("extractions.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("code", String(64), nullable=False),
    Column("severity", String(16), nullable=False),
    Column("path", String(200), nullable=True),
    Column("message", Text, nullable=False),
)

decisions = Table(
    "decisions", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("extraction_id", _ID, ForeignKey("extractions.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("reasons", JSON, nullable=False, default=list),
    Column("rule_version", String(16), nullable=False),
    Column("actor", String(40), nullable=False, default="system"),
    Column("reason_text", Text, nullable=True),
    _created(),
)

corrections = Table(
    "corrections", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("extraction_id", _ID, ForeignKey("extractions.id", ondelete="CASCADE"),
           nullable=False, index=True),
    Column("new_extraction_id", _ID, nullable=False),
    Column("user_id", _ID, nullable=True),
    Column("changes", JSON, nullable=False, default=list),
    Column("reason", Text, nullable=True),
    _created(),
)
"""`changes` holds the paths and the new values, which is document content, and
is why corrections are never written to the log stream."""

audit_events = Table(
    "audit_events", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("actor", String(80), nullable=False),
    Column("action", String(40), nullable=False),
    Column("object_type", String(40), nullable=False),
    Column("object_id", String(80), nullable=False),
    Column("detail", JSON, nullable=False, default=dict),
    _created(),
    Index("ix_audit_project_created", "project_id", "created_at"),
)

exports = Table(
    "exports", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("format", String(8), nullable=False),
    Column("status", String(16), nullable=False, default="pending"),
    Column("document_ids", JSON, nullable=False, default=list),
    Column("filter_status", String(32), nullable=True),
    Column("row_count", Integer, nullable=False, default=0),
    Column("blob_path", Text, nullable=True),
    Column("error_code", String(64), nullable=True),
    _created(),
    Column("finished_at", DateTime, nullable=True),
    CheckConstraint("format in ('csv','xlsx')", name="ck_exports_format"),
)

provider_calls = Table(
    "provider_calls", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("document_id", _ID, nullable=True, index=True),
    Column("extraction_id", _ID, nullable=True, index=True),
    Column("api_key_id", _ID, nullable=True),
    Column("purpose", String(16), nullable=False),
    Column("provider", String(40), nullable=False),
    Column("model", String(80), nullable=False),
    Column("model_version", String(120), nullable=False, default=""),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("cost_usd", Float, nullable=False, default=0.0),
    Column("cached", Boolean, nullable=False, default=False),
    Column("seconds", Float, nullable=False, default=0.0),
    Column("outcome", String(16), nullable=False, default="ok"),
    Column("error_code", String(64), nullable=True),
    _created(),
)
"""No prompt, no response, no document text: IDs, counts and codes only."""

usage_records = Table(
    "usage_records", metadata,
    Column("id", _ID, primary_key=True),
    Column("project_id", _ID, nullable=False, index=True),
    Column("month", String(7), nullable=False, index=True),
    Column("api_key_id", _ID, nullable=True),
    Column("documents", Integer, nullable=False, default=0),
    Column("pages", Integer, nullable=False, default=0),
    Column("ai_cost_usd", Float, nullable=False, default=0.0),
    Column("updated_at", DateTime, nullable=False, server_default=func.now()),
    UniqueConstraint("project_id", "month", "api_key_id", name="uq_usage_scope"),
)

ALL_TABLES = (
    users, projects, api_keys, documents, document_pages, jobs, classifications,
    schema_templates, schemas, schema_versions, schema_test_runs, extractions,
    extraction_fields, evidence, validation_results, decisions, corrections,
    audit_events, exports, provider_calls, usage_records,
)

GLOBAL_TABLES = frozenset({"users", "projects", "schema_templates"})
"""The tables without a `project_id` column, and the reason for each: `users`
and `schema_templates` are global, and `projects` *is* the scope."""

PROJECT_SCOPED = tuple(
    table for table in ALL_TABLES if table.name not in GLOBAL_TABLES
)

__all__ = [
    "ALL_TABLES",
    "GLOBAL_TABLES",
    "PROJECT_SCOPED",
    "api_keys",
    "audit_events",
    "classifications",
    "corrections",
    "decisions",
    "document_pages",
    "documents",
    "evidence",
    "exports",
    "extraction_fields",
    "extractions",
    "jobs",
    "metadata",
    "projects",
    "provider_calls",
    "schema_templates",
    "schema_test_runs",
    "schema_versions",
    "schemas",
    "usage_records",
    "users",
    "validation_results",
]
