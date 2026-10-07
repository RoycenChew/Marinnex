"""The FDIP schema language and its two compilers.

A `SchemaSpec` is what a user builds: a template, a chosen subset of its fields,
and locale hints. It compiles two ways, and both directions matter:

* to the toolkit's `ExtractionSchema`, which is what the model is actually asked
  for (CLAUDE.md 3.5);
* to a JSON Schema describing the **response**, which is the published API
  contract the customer validates against.

Keeping both in this module is deliberate. They must not drift, and the only way
to be sure of that is for one file to produce both from one source.

This module imports the toolkit but no framework: no FastAPI, no SQLAlchemy. The
import-graph test enforces that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from toolkit.extraction import ExtractionSchema, FieldSpec, FieldType

from fdip.domain.statuses import FieldStatus, MatchClass
from fdip.domain.templates import (
    INVOICE_DESCRIPTION,
    INVOICE_TEMPLATE_FIELDS,
    TemplateField,
    flatten,
)

DateOrder = Literal["DMY", "MDY", "YMD"]

_TOOLKIT_TYPES: dict[str, FieldType] = {
    "string": FieldType.STRING,
    "decimal": FieldType.DECIMAL,
    "integer": FieldType.INTEGER,
    "date": FieldType.DATE,
    "enum": FieldType.STRING,
    "array": FieldType.ARRAY,
}

_JSON_TYPES: dict[str, str] = {
    "string": "string",
    "decimal": "string",
    "integer": "integer",
    "date": "string",
    "enum": "string",
    "array": "array",
}
"""A decimal crosses the wire as a **string**. Rule 2.2: a JSON number is a
float on the other side, and 12611.70 does not survive that round trip."""


@dataclass(frozen=True)
class LocaleHints:
    date_order: DateOrder = "DMY"

    def as_dict(self) -> dict[str, str]:
        return {"date_order": self.date_order}


@dataclass(frozen=True)
class SchemaSpec:
    """A chosen subset of a template, plus how to read its dates."""

    name: str
    document_type: str
    fields: tuple[str, ...]
    locale_hints: LocaleHints = field(default_factory=LocaleHints)
    template_fields: tuple[TemplateField, ...] = INVOICE_TEMPLATE_FIELDS
    description: str = INVOICE_DESCRIPTION

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("a schema must select at least one field")
        known = {spec.path for spec in flatten(self.template_fields)}
        unknown = [path for path in self.fields if path not in known]
        if unknown:
            raise ValueError(
                "not fields of this template: " + ", ".join(sorted(unknown))
            )

    @property
    def selected(self) -> list[TemplateField]:
        """The selected top-level fields, in template order rather than request
        order, so two schemas with the same fields compile identically."""
        chosen = set(self.fields)
        out = []
        for spec in self.template_fields:
            if spec.path in chosen:
                out.append(spec)
            elif spec.children and any(c.path in chosen for c in spec.children):
                # Selecting a column implies the array that holds it.
                out.append(spec)
        return out

    def selected_children(self, parent: TemplateField) -> list[TemplateField]:
        chosen = set(self.fields)
        picked = [c for c in parent.children if c.path in chosen]
        # Selecting the array alone means every column of it.
        return picked or list(parent.children)

    def required_paths(self) -> tuple[str, ...]:
        """Required *scalar* leaves, which is what 3.6 judges completeness on.

        An array is not itself required-checkable: an invoice with no line items
        is a validation question, not a grounding one.
        """
        out = []
        for spec in self.selected:
            if spec.is_array:
                continue
            if spec.required_default:
                out.append(spec.path)
        return tuple(out)


def _to_field_spec(spec: TemplateField, children: list[FieldSpec]) -> FieldSpec:
    return FieldSpec(
        name=spec.path.split(".")[-1].replace("[]", ""),
        type=_TOOLKIT_TYPES[spec.kind],
        description=spec.description,
        required=spec.required_default,
        enum=list(spec.enum),
        pattern=spec.pattern,
        fields=children,
    )


def to_extraction_schema(spec: SchemaSpec) -> ExtractionSchema:
    """Compile to what the model is asked for."""
    fields: list[FieldSpec] = []
    for template_field in spec.selected:
        children = (
            [_to_field_spec(c, []) for c in spec.selected_children(template_field)]
            if template_field.is_array else []
        )
        fields.append(_to_field_spec(template_field, children))
    return ExtractionSchema(
        name=spec.name or "Document",
        description=spec.description,
        fields=fields,
    )


_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page": {"type": "integer", "minimum": 1},
        "bbox": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 4,
            "maxItems": 4,
            "description": "x0, y0, x1, y1 in PDF points, origin top-left, y down.",
        },
        "source": {"type": "string", "enum": ["text_layer", "ocr", "vision"]},
        "ocr_confidence": {"type": ["number", "null"]},
    },
    "required": ["page", "source"],
    "additionalProperties": False,
}

_FIELD_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {},
        "raw_text": {"type": ["string", "null"]},
        "status": {"type": "string", "enum": [s.value for s in FieldStatus]},
        "match": {"type": "string", "enum": [m.value for m in MatchClass]},
        "evidence": {"type": "array", "items": _EVIDENCE_SCHEMA},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["value", "status", "match", "evidence", "reasons"],
    "additionalProperties": False,
}


def _data_property(spec: TemplateField, children: list[TemplateField]) -> dict:
    if spec.is_array:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    c.path.split(".")[-1]: _scalar_property(c) for c in children
                },
                "additionalProperties": False,
            },
        }
    return _scalar_property(spec)


def _scalar_property(spec: TemplateField) -> dict:
    node: dict[str, Any] = {
        "type": [_JSON_TYPES[spec.kind], "null"],
        "description": spec.description,
    }
    if spec.enum:
        node["enum"] = [*spec.enum, None]
    if spec.kind == "date":
        node["format"] = "date"
        node["description"] += " ISO 8601, YYYY-MM-DD."
    if spec.kind == "decimal":
        node["description"] += " A decimal as a string, never a JSON number."
    return node


def to_response_contract(spec: SchemaSpec, version: int) -> dict[str, Any]:
    """The published JSON Schema of `GET /extractions/{id}`.

    Written by hand rather than derived from the Pydantic models because this is
    the thing a customer pins their integration to: it has to be stable and
    readable, and generated output is neither.
    """
    data_properties: dict[str, Any] = {}
    field_paths: list[str] = []
    for template_field in spec.selected:
        key = template_field.path
        children = spec.selected_children(template_field)
        data_properties[key] = _data_property(template_field, children)
        if template_field.is_array:
            field_paths.extend(
                "%s[i].%s" % (key, c.path.split(".")[-1]) for c in children
            )
        else:
            field_paths.append(key)

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "%s extraction, version %d" % (spec.name, version),
        "description": (
            "The response of GET /v1/extractions/{id} for this schema version. "
            "Money and other decimals are strings. Every field in `fields` is "
            "keyed by the path shown in `x-field-paths`; line-item entries use "
            "line_items[i].<column> with i the zero-based row index."
        ),
        "type": "object",
        "properties": {
            "extraction_id": {"type": "string"},
            "document_id": {"type": "string"},
            "version": {"type": "integer", "minimum": 1},
            "status": {
                "type": "string",
                "enum": [
                    "processing", "completed", "needs_review",
                    "document_type_mismatch", "rejected", "failed", "unsupported",
                ],
            },
            "document_type": {"type": ["string", "null"]},
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "version": {"type": "integer"},
                },
                "required": ["id", "version"],
            },
            "currency": {"type": ["string", "null"]},
            "data": {
                "type": "object",
                "properties": data_properties,
                "additionalProperties": False,
            },
            "fields": {
                "type": "object",
                "additionalProperties": _FIELD_ENTRY_SCHEMA,
            },
            "validation": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["info", "warning", "critical"],
                        },
                        "path": {"type": ["string", "null"]},
                        "message": {"type": "string"},
                    },
                    "required": ["code", "severity", "message"],
                },
            },
            "reasons": {"type": "array", "items": {"type": "string"}},
            "pipeline_version": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
        },
        "required": [
            "extraction_id", "document_id", "version", "status", "schema",
            "data", "fields", "validation", "pipeline_version",
        ],
        "additionalProperties": True,
        "x-field-paths": field_paths,
        "x-locale-hints": spec.locale_hints.as_dict(),
    }


__all__ = [
    "DateOrder",
    "LocaleHints",
    "SchemaSpec",
    "to_extraction_schema",
    "to_response_contract",
]
