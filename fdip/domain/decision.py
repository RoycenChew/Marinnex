"""The decision rule, CLAUDE.md 3.6, implemented once and versioned.

```
completed     if every required field is grounded (exact | normalized | derivable)
              AND schema valid AND all validators pass
              AND no critical warning (truncation, OCR page quality below threshold)
needs_review  otherwise, with per-field reasons
```

Two things about it are easy to get wrong and are therefore spelled out here.

`fuzzy_ocr` does **not** count as grounded. A single-edit match against a
low-confidence OCR word is exactly the case where the value is plausible and
wrong, so it goes to a human.

The rule returns reasons, not just a verdict. A `needs_review` with no reason is
useless to a reviewer and indistinguishable from a bug, so the reason list is
part of the return type rather than logged somewhere.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fdip.domain.statuses import GROUNDED_MATCHES, FieldStatus, Status
from fdip.domain.validators import ValidationResult

DECISION_RULE_VERSION = "3.6.1"

OCR_CONFIDENCE_THRESHOLD = 0.75
"""Below this, a page is a critical warning rather than a usable source."""


@dataclass(frozen=True)
class FieldSignal:
    """What the decision needs to know about one field. Nothing more."""

    path: str
    present: bool
    match: str
    required: bool
    min_ocr_confidence: float | None = None


@dataclass(frozen=True)
class Decision:
    status: str
    reasons: tuple[str, ...] = ()
    field_reasons: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    rule_version: str = DECISION_RULE_VERSION

    @property
    def completed(self) -> bool:
        return self.status == Status.COMPLETED.value


def field_status(signal: FieldSignal) -> tuple[str, tuple[str, ...]]:
    """One field's own verdict and why, independent of the document's."""
    if not signal.present:
        if signal.required:
            return FieldStatus.MISSING.value, ("required_field_missing",)
        return FieldStatus.ACCEPTED.value, ()
    if signal.match in GROUNDED_MATCHES:
        if (signal.min_ocr_confidence is not None
                and signal.min_ocr_confidence < OCR_CONFIDENCE_THRESHOLD):
            return FieldStatus.NEEDS_REVIEW.value, ("low_ocr_confidence",)
        return FieldStatus.ACCEPTED.value, ()
    if signal.match == "fuzzy_ocr":
        return FieldStatus.NEEDS_REVIEW.value, ("possible_ocr_misread",)
    if signal.match == "not_checked":
        return FieldStatus.NEEDS_REVIEW.value, ("not_grounded",)
    return FieldStatus.NEEDS_REVIEW.value, ("value_not_found_on_page",)


def decide(
    signals: Sequence[FieldSignal],
    validation: Sequence[ValidationResult] = (),
    schema_valid: bool = True,
    truncated: bool = False,
    warnings: Sequence[str] = (),
) -> Decision:
    reasons: list[str] = []
    field_reasons: dict[str, tuple[str, ...]] = {}

    for signal in signals:
        status, why = field_status(signal)
        if why:
            field_reasons[signal.path] = why
        if status != FieldStatus.ACCEPTED.value and signal.required:
            reasons.append("field_not_grounded:" + signal.path)
        elif status == FieldStatus.MISSING.value:
            reasons.append("required_field_missing:" + signal.path)

    if not schema_valid:
        reasons.append("schema_invalid")
    if truncated:
        # A truncated document is never completed: the model was not shown the
        # page the value might be on, so "not found" means nothing here.
        reasons.append("document_truncated")
    reasons.extend("warning:" + w for w in warnings)
    reasons.extend(
        "validation:" + result.code for result in validation
        if result.severity in ("critical", "warning")
    )

    # Dedupe while keeping order: the same field can fail two ways and a
    # reviewer should see each reason once. `dict.fromkeys` rather than a `seen`
    # set with a side effect in the comprehension, which reads as a trick.
    ordered = tuple(dict.fromkeys(reasons))
    status = Status.COMPLETED.value if not ordered else Status.NEEDS_REVIEW.value
    return Decision(status=status, reasons=ordered, field_reasons=field_reasons)


__all__ = [
    "DECISION_RULE_VERSION",
    "Decision",
    "FieldSignal",
    "OCR_CONFIDENCE_THRESHOLD",
    "decide",
    "field_status",
]
