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

import re
from collections.abc import Mapping
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
from fdip.domain.user_text import (
    CUSTOM_BLOCK_LIMIT,
    CUSTOM_FIELD_PREAMBLE,
    DESCRIPTION_LIMIT,
    HINT_LIMIT,
    MAX_CUSTOM_FIELDS,
    MAX_HINTS,
    block_size,
    describe_custom_field,
    sanitise,
)

DateOrder = Literal["DMY", "MDY", "YMD"]

#: A snake_case identifier: what an output key and a custom field name may be.
#: Enforced in both directions, because this is what a customer's code indexes.
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

CustomKind = Literal["text", "number", "money", "date"]

#: The four user-facing types, and what each compiles to. `money` is a decimal
#: like any other amount: the currency comes from the document's own currency
#: field, because a document has one currency and a second place to state it is
#: a second place for it to be wrong.
_CUSTOM_KINDS: dict[str, str] = {
    "text": "string",
    "number": "decimal",
    "money": "decimal",
    "date": "date",
}

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
class FieldConfig:
    """How one selected field is presented. Level 1.

    None of this changes what is extracted or how a value is judged. `alias` is
    the key the customer receives; `order` sorts the output; `required`
    overrides the template's default for the decision rule. The two formats are
    **display only** — they reach CSV, Excel and the screen, never the API,
    which stays ISO dates and decimal strings so an integrator can parse what
    arrives without knowing a locale.
    """

    alias: str | None = None
    order: int | None = None
    required: bool | None = None
    date_format: str | None = None
    number_format: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in {
            "alias": self.alias, "order": self.order, "required": self.required,
            "date_format": self.date_format, "number_format": self.number_format,
        }.items() if v is not None}


@dataclass(frozen=True)
class CustomField:
    """A field the template does not have. Level 2.

    It is sent to the existing extract task as one more field with a
    description — there is no second AI call and no new kind of task. It is
    grounded like any other scalar, and it can never be `derived`: derivation is
    a deterministic claim, and there is no arithmetic behind a field this system
    has never seen.
    """

    name: str
    kind: CustomKind
    description: str
    hints: tuple[str, ...] = ()
    required: bool = False

    def __post_init__(self) -> None:
        if "[]" in self.name or "." in self.name:
            raise ValueError(
                "custom line-item columns are coming later; a custom field is "
                "a header-level value for now"
            )
        if not _NAME.match(self.name):
            raise ValueError(
                "a custom field name must be snake_case, start with a letter "
                "and be at most 64 characters: %r" % self.name
            )
        if self.kind not in _CUSTOM_KINDS:
            raise ValueError("unknown custom field type: %r" % self.kind)
        if not sanitise(self.description, DESCRIPTION_LIMIT):
            raise ValueError(
                "a custom field needs a description, or the model has nothing "
                "to go on"
            )
        if len(self.hints) > MAX_HINTS:
            raise ValueError("at most %d label hints" % MAX_HINTS)

    @property
    def rendered_description(self) -> str:
        """The description as it reaches the prompt: sanitised and delimited."""
        return describe_custom_field(self.description, self.hints)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": sanitise(self.description, DESCRIPTION_LIMIT),
            "hints": [sanitise(h, HINT_LIMIT) for h in self.hints[:MAX_HINTS]],
            "required": self.required,
        }


@dataclass(frozen=True)
class SchemaSpec:
    """A chosen subset of a template, plus how to read its dates."""

    name: str
    document_type: str
    fields: tuple[str, ...]
    locale_hints: LocaleHints = field(default_factory=LocaleHints)
    template_fields: tuple[TemplateField, ...] = INVOICE_TEMPLATE_FIELDS
    description: str = INVOICE_DESCRIPTION
    field_config: Mapping[str, FieldConfig] = field(default_factory=dict)
    custom_fields: tuple[CustomField, ...] = ()

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("a schema must select at least one field")
        known = {spec.path for spec in flatten(self.template_fields)}
        unknown = [path for path in self.fields if path not in known]
        if unknown:
            raise ValueError(
                "not fields of this template: " + ", ".join(sorted(unknown))
            )
        self._validate_custom_fields(known)
        self._validate_aliases(known)

    def _validate_custom_fields(self, known: set[str]) -> None:
        if len(self.custom_fields) > MAX_CUSTOM_FIELDS:
            raise ValueError(
                "at most %d custom fields per version" % MAX_CUSTOM_FIELDS
            )
        seen: set[str] = set()
        for custom in self.custom_fields:
            if custom.name in known:
                raise ValueError(
                    "custom field name %r is already a field of this template"
                    % custom.name
                )
            if custom.name in seen:
                raise ValueError("duplicate custom field name %r" % custom.name)
            seen.add(custom.name)
        # The whole block has a ceiling: ten verbose fields would otherwise add
        # thousands of characters to every document processed against this
        # schema, and the customer would see it only on the bill.
        size = block_size([c.rendered_description for c in self.custom_fields])
        if self.custom_fields and size > CUSTOM_BLOCK_LIMIT:
            raise ValueError(
                "the custom field descriptions are too long together: %d "
                "characters, limit %d" % (size, CUSTOM_BLOCK_LIMIT)
            )

    def _validate_aliases(self, known: set[str]) -> None:
        """An alias is what a customer's code indexes, so a collision is not a
        cosmetic problem: one of the two fields would simply disappear."""
        custom_names = {c.name for c in self.custom_fields}
        output_keys: dict[str, str] = {}
        for path in [*self.fields, *custom_names]:
            output_keys[self.output_key(path)] = path

        for path, config in self.field_config.items():
            if config.alias is None:
                continue
            if not _NAME.match(config.alias):
                raise ValueError(
                    "an alias must be snake_case, start with a letter and be "
                    "at most 64 characters: %r" % config.alias
                )
            # Taking the name of a different field, template or custom, is the
            # collision that loses data.
            if config.alias in known and config.alias != path:
                raise ValueError(
                    "alias %r is the name of another template field"
                    % config.alias
                )

        aliases = [c.alias for c in self.field_config.values() if c.alias]
        if len(aliases) != len(set(aliases)):
            raise ValueError("two fields share one alias")
        if len(output_keys) != len(self.fields) + len(custom_names):
            raise ValueError("an alias collides with another output key")

    def output_key(self, path: str) -> str:
        """The key this field arrives under. The path is what everything
        internal keys on; this is only ever applied on the way out."""
        config = self.field_config.get(path)
        return config.alias if config and config.alias else path

    @property
    def custom_names(self) -> frozenset[str]:
        return frozenset(c.name for c in self.custom_fields)

    def _order_of(self, path: str) -> tuple[int, int]:
        """Explicit order first, then the template's own order."""
        config = self.field_config.get(path)
        if config and config.order is not None:
            return (0, config.order)
        return (1, 0)

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
            config = self.field_config.get(spec.path)
            required = (config.required if config and config.required is not None
                        else spec.required_default)
            if required:
                out.append(spec.path)
        # A required custom field is judged exactly like a template one: not
        # found on the page means the document waits for a person.
        out.extend(c.name for c in self.custom_fields if c.required)
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
    """Compile to what the model is asked for.

    Aliases are deliberately absent here. The model is asked for the real field
    names, and renaming happens on the way out, so two schemas differing only by
    alias produce the same prompt — and the same cache entry.
    """
    fields: list[FieldSpec] = []
    for template_field in spec.selected:
        children = (
            [_to_field_spec(c, []) for c in spec.selected_children(template_field)]
            if template_field.is_array else []
        )
        fields.append(_to_field_spec(template_field, children))

    for custom in spec.custom_fields:
        fields.append(FieldSpec(
            name=custom.name,
            type=_TOOLKIT_TYPES[_CUSTOM_KINDS[custom.kind]],
            description=custom.rendered_description,
            required=custom.required,
        ))

    description = spec.description
    if spec.custom_fields:
        description = description + chr(10) * 2 + CUSTOM_FIELD_PREAMBLE

    return ExtractionSchema(
        name=spec.name or "Document",
        description=description,
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


def _custom_property(custom: CustomField) -> dict[str, Any]:
    """A custom field's node in the published contract.

    `money` is a decimal string with no currency of its own: the document's
    `currency` field is the one answer, and a second one is a second thing to
    disagree about.
    """
    kind = _CUSTOM_KINDS[custom.kind]
    node: dict[str, Any] = {
        "type": [_JSON_TYPES[kind], "null"],
        "description": sanitise(custom.description, DESCRIPTION_LIMIT),
        "x-custom": True,
    }
    if custom.kind == "date":
        node["format"] = "date"
        node["description"] += " ISO 8601, YYYY-MM-DD."
    if custom.kind in ("money", "number"):
        node["description"] += " A decimal as a string, never a JSON number."
    if custom.kind == "money":
        node["description"] += " In the document's own currency."
    return node


def to_response_contract(spec: SchemaSpec, version: int) -> dict[str, Any]:
    """The published JSON Schema of `GET /extractions/{id}`.

    Written by hand rather than derived from the Pydantic models because this is
    the thing a customer pins their integration to: it has to be stable and
    readable, and generated output is neither.
    """
    data_properties: dict[str, Any] = {}
    field_paths: list[str] = []

    # Output order: anything the user placed explicitly, then the template's own
    # order, then custom fields. Sorting here rather than at render time means
    # the published contract and the response cannot disagree about it.
    ordered: list[tuple[tuple[int, int], str, Any]] = []
    for template_field in spec.selected:
        ordered.append((spec._order_of(template_field.path), "t", template_field))
    for custom in spec.custom_fields:
        ordered.append((spec._order_of(custom.name), "c", custom))
    ordered.sort(key=lambda item: item[0])

    for _rank, kind, entry in ordered:
        if kind == "c":
            data_properties[spec.output_key(entry.name)] = _custom_property(entry)
            field_paths.append(spec.output_key(entry.name))
            continue
        template_field = entry
        key = spec.output_key(template_field.path)
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
        # Named so an integrator can tell at a glance which keys came from a
        # template this system validates, and which the customer defined. A
        # custom field is grounded but has no arithmetic behind it.
        "x-custom-fields": [spec.output_key(c.name) for c in spec.custom_fields],
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
