"""RowMapping sets to API responses: the §3.7 shape, assembled in exactly one place.

Every route that returns an extraction goes through `extraction_view`. The
alternative -- each router building its own dict -- is how `GET /extractions/{id}`
and `GET /documents/{id}/analysis` end up subtly different, and the UI agent is
reading one contract for both.

The bbox convention is stated here because it is the thing a UI gets wrong:
coordinates are in **PDF points**, origin top-left, y increasing downwards, and
the page image is rendered at 150 DPI. So the UI scales by
`image_width / page_width`.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine.row import RowMapping

from fdip.adapters.repository import ProjectRepository

PAGE_IMAGE_DPI = 150


def _iso(value: Any) -> str | None:
    return None if value is None else str(value.isoformat() if hasattr(
        value, "isoformat") else value)


def evidence_view(row: RowMapping) -> dict[str, Any]:
    bbox = [row["x0"], row["y0"], row["x1"], row["y1"]]
    return {
        "page": int(row["page"]),
        "bbox": None if any(v is None for v in bbox) else [float(v) for v in bbox],
        "source": str(row["source"]),
        "ocr_confidence": row["ocr_confidence"],
    }


def presentation_for(repo: ProjectRepository,
                     extraction: RowMapping) -> tuple[dict[str, str], frozenset[str]]:
    """The alias map and the custom field names of the version that produced
    this extraction, or empty if it was produced against the bare template."""
    schema_id = extraction["schema_id"]
    version = extraction["schema_version"]
    if not schema_id or not version:
        return {}, frozenset()
    stored = repo.schema_version(str(schema_id), int(version))
    if stored is None:
        return {}, frozenset()
    aliases = {
        path: str(config["alias"])
        for path, config in (stored["field_config"] or {}).items()
        if config.get("alias")
    }
    custom = frozenset(
        str(entry["name"]) for entry in (stored["custom_fields"] or [])
    )
    return aliases, custom


def field_view(row: RowMapping, evidence: Sequence[RowMapping],
               alias: str | None = None,
               custom: bool = False) -> dict[str, Any]:
    entry = {
        "value": row["value_json"],
        "raw_text": row["raw_text"],
        "status": str(row["status"]),
        "match": str(row["match"]),
        "evidence": [evidence_view(item) for item in evidence],
        "reasons": list(row["reasons"] or []),
    }
    # Only on the reviewer surface, which keeps real paths: the alias is the
    # label to show, and `custom` marks a field the customer defined, which has
    # no template validation behind it and is worth a second look.
    if alias:
        entry["alias"] = alias
    if custom:
        entry["custom"] = True
    return entry


def extraction_view(repo: ProjectRepository, extraction: RowMapping,
                    include_suggested: bool = False,
                    aliases: Mapping[str, str] | None = None,
                    labels: Mapping[str, str] | None = None,
                    custom_names: frozenset[str] = frozenset(),
                    ) -> dict[str, Any]:
    """One extraction, rendered for one of two audiences.

    **An integrator** asked for `bill_no` and must receive `bill_no`, so the
    pipeline surface passes the version's aliases and both `data` and `fields`
    are keyed by them.

    **A reviewer** keeps real paths. Corrections are posted back by path, and
    `extraction_fields.path` is what evidence and version history key on; if an
    alias reached them, renaming a field would orphan the history of every value
    already extracted under the old name. The alias rides along on each entry as
    a label instead.
    """
    field_rows = repo.fields(str(extraction["id"]))
    evidence = repo.evidence_for([str(row["id"]) for row in field_rows])
    alias_of = dict(aliases or {})

    def key(path: str) -> str:
        return alias_of.get(path, path)

    stored_data = extraction["data"] or {}
    body: dict[str, Any] = {
        "extraction_id": str(extraction["id"]),
        "document_id": str(extraction["document_id"]),
        "version": int(extraction["version"]),
        "status": str(extraction["status"]),
        "document_type": extraction["document_type"],
        "schema": {
            "id": extraction["schema_id"] or "invoice",
            "version": int(extraction["schema_version"] or 1),
        },
        "currency": extraction["currency"],
        "data": ({key(path): value for path, value in stored_data.items()}
                 if alias_of else stored_data),
        "fields": {
            key(str(row["path"])): field_view(
                row, evidence.get(str(row["id"]), []),
                alias=(labels or {}).get(str(row["path"])),
                custom=str(row["path"]) in custom_names,
            )
            for row in field_rows
        },
        "validation": [
            {
                "code": str(row["code"]),
                "severity": str(row["severity"]),
                "path": row["path"],
                "message": str(row["message"]),
            }
            for row in repo.validations(str(extraction["id"]))
        ],
        "reasons": list(extraction["reasons"] or []),
        "pipeline_version": str(extraction["pipeline_version"]),
        "created_at": _iso(extraction["created_at"]),
    }
    if include_suggested:
        # The interactive path only: these are the grounded paths the UI
        # pre-selects when the user turns an analysis into a schema.
        body["suggested_fields"] = list(extraction["suggested_fields"] or [])
    return body


def document_view(document: RowMapping, job: RowMapping | None = None,
                  classification: RowMapping | None = None,
                  decision: str | None = None) -> dict[str, Any]:
    return {
        "id": str(document["id"]),
        "filename": str(document["filename"]),
        "mime": str(document["mime"]),
        "pages": int(document["page_count"]),
        "page_sizes": document["page_sizes"] or {},
        "status": str(document["status"]),
        "error_code": document["error_code"],
        "document_type": document["document_type"],
        "classification_confidence_source": (
            None if classification is None else {
                "confidence": classification["confidence"],
                "source": str(classification["source"]),
            }
        ),
        "job": None if job is None else {
            "id": str(job["id"]),
            "state": str(job["state"]),
            "stage": job["stage"],
            "attempts": int(job["attempts"]),
            "error_code": job["error_code"],
        },
        "decision": decision,
        "created_at": _iso(document["created_at"]),
        "page_image_dpi": PAGE_IMAGE_DPI,
    }


def document_list_item(document: RowMapping) -> dict[str, Any]:
    """The list is deliberately thinner than the detail view.

    A list of 200 documents does not need every page size, and sending them makes
    the first paint slower for no gain.
    """
    return {
        "id": str(document["id"]),
        "filename": str(document["filename"]),
        "status": str(document["status"]),
        "document_type": document["document_type"],
        "pages": int(document["page_count"]),
        "created_at": _iso(document["created_at"]),
        "decision": str(document["status"]),
    }


def schema_version_view(row: RowMapping) -> dict[str, Any]:
    """One stored version, rendered the same way wherever it appears."""
    return {
        "version": int(row["version"]),
        "created_at": _iso(row["created_at"]),
        "test_run_status": str(row["test_run_status"]),
        "fields": list(row["fields"] or []),
        "locale_hints": row["locale_hints"] or {},
        "field_config": row["field_config"] or {},
        "custom_fields": list(row["custom_fields"] or []),
    }


def schema_view(schema: RowMapping, versions: Sequence[RowMapping] = ()) -> dict[str, Any]:
    return {
        "schema_id": str(schema["id"]),
        "name": str(schema["name"]),
        "document_type": str(schema["document_type"]),
        "template_id": str(schema["template_id"]),
        "current_version": int(schema["current_version"]),
        "created_at": _iso(schema["created_at"]),
        "archived_at": _iso(schema["archived_at"]),
        "versions": [schema_version_view(row) for row in versions],
    }


def job_view(job: RowMapping) -> dict[str, Any]:
    return {
        "id": str(job["id"]),
        "document_id": str(job["document_id"]),
        "state": str(job["state"]),
        "stage": job["stage"],
        "attempts": int(job["attempts"]),
        "error_code": job["error_code"],
        "created_at": _iso(job["created_at"]),
        "finished_at": _iso(job["finished_at"]),
    }


def api_key_status(row: RowMapping, now: datetime | None = None) -> str:
    """`active`, `expired` or `revoked`.

    Derived here rather than left to each client. Three timestamps and no state
    meant every consumer re-implemented this comparison, and they would not all
    have agreed on what "expires at exactly now" means.
    """
    if row["revoked_at"] is not None:
        return "revoked"
    expires = row["expires_at"]
    if expires is not None and expires <= (now or datetime.now(UTC).replace(tzinfo=None)):
        return "expired"
    return "active"


def api_key_view(row: RowMapping) -> dict[str, Any]:
    """Never the key, and never the hash. The prefix is what identifies it."""
    return {
        "status": api_key_status(row),
        "id": str(row["id"]),
        "name": str(row["name"]),
        "prefix": str(row["prefix"]),
        "mode": str(row["mode"]),
        "schema_versions": list(row["schema_versions"] or []),
        "expires_at": _iso(row["expires_at"]),
        "revoked_at": _iso(row["revoked_at"]),
        "last_used_at": _iso(row["last_used_at"]),
        "created_at": _iso(row["created_at"]),
    }


def template_view(row: RowMapping) -> dict[str, Any]:
    fields = row["fields"]
    return {
        "id": str(row["id"]),
        "document_type": str(row["document_type"]),
        "version": int(row["version"]),
        "name": str(row["name"]),
        "description": str(row["description"]),
        "fields": fields if isinstance(fields, list) else [],
    }


def test_run_view(row: RowMapping) -> dict[str, Any]:
    return {
        "test_run_id": str(row["id"]),
        "schema_id": str(row["schema_id"]),
        "version": int(row["version"]),
        "status": str(row["status"]),
        "passed": bool(row["passed"]),
        "per_document": list(row["per_document"] or []),
        "created_at": _iso(row["created_at"]),
        "finished_at": _iso(row["finished_at"]),
    }


def usage_view(month: str, rows: Sequence[RowMapping]) -> dict[str, Any]:
    return {
        "month": month,
        "pages": sum(int(row["pages"]) for row in rows),
        "documents": sum(int(row["documents"]) for row in rows),
        "ai_cost_usd": round(sum(float(row["ai_cost_usd"]) for row in rows), 6),
        "by_key": [
            {
                "api_key_id": row["api_key_id"],
                "pages": int(row["pages"]),
                "documents": int(row["documents"]),
                "ai_cost_usd": round(float(row["ai_cost_usd"]), 6),
            }
            for row in rows
        ],
    }


def export_view(row: RowMapping) -> dict[str, Any]:
    return {
        "export_id": str(row["id"]),
        "format": str(row["format"]),
        "status": str(row["status"]),
        "row_count": int(row["row_count"]),
        "error_code": row["error_code"],
        "created_at": _iso(row["created_at"]),
        "finished_at": _iso(row["finished_at"]),
    }


def flatten_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    """`{"line_items": [{...}]}` to `{"line_items[0].amount": ...}`.

    The same path grammar the `fields` map uses, so a UI can look up the entry
    for a cell it is displaying without a second convention.
    """
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    for column, cell in item.items():
                        out["%s[%d].%s" % (key, index, column)] = cell
                else:
                    out["%s[%d]" % (key, index)] = item
        else:
            out[key] = value
    return out


__all__ = [
    "PAGE_IMAGE_DPI",
    "api_key_view",
    "document_list_item",
    "document_view",
    "evidence_view",
    "export_view",
    "extraction_view",
    "field_view",
    "flatten_fields",
    "job_view",
    "schema_view",
    "template_view",
    "test_run_view",
    "usage_view",
]
