"""`document_type` is decided by the classifier, and the gate applies everywhere.

Two defects found while building the UI, both of which made the system look wrong
to a reviewer for reasons that had nothing to do with the document.

**`document_type` was grounded against the page.** No invoice prints the word
"invoice" as a value -- the Malay sample says INVOIS CUKAI -- so the field came
back `not_found`, and the rule that an ungrounded value holds a document back then
sent every Malay invoice to review over a field the classifier already knew. It is
a *derived* field: the classify stage is its source, not the page text.

**The type gate only applied to pipeline calls.** A bank statement uploaded
interactively against the invoice template reached `completed` with an empty
extraction, which is the one status it must never reach.
"""
from __future__ import annotations

from typing import Any

import pytest

from fdip.domain.schema_lang import SchemaSpec
from fdip.domain.statuses import MatchClass, Status
from fdip.pipeline.stages import CLASSIFY_CONFIDENCE_FLOOR, validate_and_decide

SPEC = SchemaSpec(
    name="Invoice",
    document_type="invoice",
    fields=("document_type", "invoice_number", "total"),
)


def _extracted(**overrides: Any) -> dict[str, Any]:
    """A clean extraction where `document_type` did not ground, as in real life."""
    base: dict[str, Any] = {
        "data": {
            "document_type": "invoice",
            "invoice_number": "INV-2026-0417",
            "total": "2142.72",
        },
        "schema_valid": True,
        "truncated": False,
        "fields": [
            {
                "path": "document_type",
                "value": "invoice",
                "match": "not_found",
                "evidence": [],
            },
            {
                "path": "invoice_number",
                "value": "INV-2026-0417",
                "match": "exact",
                "evidence": [{"page": 1, "source": "text_layer", "bbox": [1, 2, 3, 4]}],
            },
            {
                "path": "total",
                "value": "2142.72",
                "match": "exact",
                "evidence": [{"page": 1, "source": "text_layer", "bbox": [1, 2, 3, 4]}],
            },
        ],
    }
    base.update(overrides)
    return base


# -- 1. document_type is derived from the classification ----------------------

def test_document_type_is_derived_from_the_classifier_not_the_page() -> None:
    decided = validate_and_decide(
        _extracted(),
        SPEC,
        classification={"label": "invoice", "confidence": 0.95},
    )
    assert decided["matches"]["document_type"] == MatchClass.DERIVED.value
    assert decided["status"] == Status.COMPLETED.value, decided["reasons"]
    assert not any("document_type" in reason for reason in decided["reasons"])


def test_the_classifier_wins_over_what_the_model_typed() -> None:
    """The classifier is the dedicated task for this; the extractor is guessing.

    A credit note whose extraction said "invoice" takes the classifier's answer,
    so the stored `document_type` and the `Classification` row cannot disagree.
    """
    extracted = _extracted()
    decided = validate_and_decide(
        extracted,
        SPEC,
        classification={"label": "credit_note", "confidence": 0.9},
    )
    assert decided["data"]["document_type"] == "credit_note"
    assert decided["matches"]["document_type"] == MatchClass.DERIVED.value


def test_without_a_classification_the_field_is_left_alone() -> None:
    """A correction re-runs this stage with no classify step in front of it."""
    decided = validate_and_decide(_extracted(), SPEC)
    assert decided["matches"].get("document_type") == "not_found"
    assert "field_not_grounded:document_type" in decided["reasons"]


# -- 2. the type gate applies to interactive uploads too ----------------------

def test_a_bank_statement_never_completes_under_the_invoice_template() -> None:
    decided = validate_and_decide(
        _extracted(),
        SPEC,
        classification={"label": "bank_statement", "confidence": 0.95},
        expected_type="invoice",
    )
    assert decided["status"] == Status.NEEDS_REVIEW.value
    assert "document_type_mismatch" in decided["reasons"]


def test_a_credit_note_is_accepted_under_the_invoice_template() -> None:
    """Credit notes run the invoice template: same fields, signs handled by the
    validators (`INVOICE_LIKE` in domain.statuses)."""
    decided = validate_and_decide(
        _extracted(),
        SPEC,
        classification={"label": "credit_note", "confidence": 0.95},
        expected_type="invoice",
    )
    assert decided["status"] == Status.COMPLETED.value, decided["reasons"]
    assert "document_type_mismatch" not in decided["reasons"]


def test_a_low_confidence_classification_routes_to_review() -> None:
    decided = validate_and_decide(
        _extracted(),
        SPEC,
        classification={
            "label": "invoice",
            "confidence": CLASSIFY_CONFIDENCE_FLOOR - 0.01,
        },
        expected_type="invoice",
    )
    assert decided["status"] == Status.NEEDS_REVIEW.value
    assert "document_type_mismatch" in decided["reasons"]


def test_an_unknown_label_routes_to_review_rather_than_passing() -> None:
    """`unknown` passes the *pipeline* gate, because a classifier that could not
    tell is not evidence of the wrong type. On an interactive upload it still
    deserves a person's eye, so it is flagged rather than silently accepted."""
    decided = validate_and_decide(
        _extracted(),
        SPEC,
        classification={"label": "unknown", "confidence": 0.0},
        expected_type="invoice",
    )
    assert decided["status"] == Status.NEEDS_REVIEW.value
    assert "document_type_mismatch" in decided["reasons"]


@pytest.mark.parametrize("label", ["receipt", "purchase_order", "other"])
def test_every_other_label_is_a_mismatch(label: str) -> None:
    decided = validate_and_decide(
        _extracted(),
        SPEC,
        classification={"label": label, "confidence": 0.95},
        expected_type="invoice",
    )
    assert "document_type_mismatch" in decided["reasons"], label
