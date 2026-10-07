"""The decision rule, and the four gaps Checkpoint 2 review found in it.

Each test here pins a way a document could reach `completed` when it should not
have. Three of the four were real: an ungrounded optional value passed silently,
OCR evidence auto-completed, and a currency nobody printed was accepted as MYR.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from fdip.domain.decision import DERIVABLE_PATHS, FieldSignal, decide
from fdip.domain.derivation import is_derivable
from fdip.domain.statuses import FieldStatus, Status


def _grounded(path: str, required: bool = True, **kwargs: object) -> FieldSignal:
    return FieldSignal(path=path, present=True, match="exact", required=required,
                       **kwargs)  # type: ignore[arg-type]


def test_a_fully_grounded_document_completes() -> None:
    """The control. Without it the other tests could pass by always failing."""
    decision = decide([_grounded("invoice_number"), _grounded("total")])
    assert decision.status == Status.COMPLETED.value
    assert decision.reasons == ()


# -- 3. a non-null value that was not found on the page -----------------------

def test_an_ungrounded_value_on_an_OPTIONAL_field_routes_to_review() -> None:
    """The gap: `not_found` on an optional field added no document reason.

    This is the strongest hallucination signal there is (3.4). The field being
    optional means the schema tolerates its *absence*, not that it tolerates a
    value nobody can find on the page.
    """
    decision = decide([
        _grounded("invoice_number"),
        FieldSignal(path="po_number", present=True, match="not_found",
                    required=False),
    ])
    assert decision.status == Status.NEEDS_REVIEW.value
    assert "field_not_grounded:po_number" in decision.reasons
    assert decision.field_reasons["po_number"] == ("value_not_found_on_page",)


def test_an_absent_optional_field_still_completes() -> None:
    """The other side of it: null is fine, and must stay fine.

    All eleven ungrounded fields in the live smoke test were this case -- absent,
    not wrong -- so a rule that reviewed them would review every document.
    """
    decision = decide([
        _grounded("invoice_number"),
        FieldSignal(path="po_number", present=False, match="not_checked",
                    required=False),
        FieldSignal(path="bank_account", present=False, match="not_found",
                    required=False),
    ])
    assert decision.status == Status.COMPLETED.value
    assert decision.reasons == ()


@pytest.mark.parametrize("match", ["not_found", "fuzzy_ocr", "not_checked"])
def test_any_ungrounded_present_value_routes_to_review(match: str) -> None:
    decision = decide([
        FieldSignal(path="vendor_contact", present=True, match=match,
                    required=False),
    ])
    assert decision.status == Status.NEEDS_REVIEW.value, match


# -- 1. scanned documents must not auto-complete ------------------------------

def test_ocr_evidence_does_not_auto_complete() -> None:
    """Route B produced 13 silent errors in 30 mild scans.

    The suspected mechanism is that an OCR misread is grounded against the same
    misread words, so grounding agrees with itself and the error is invisible.
    Until `--final` measures route B, OCR evidence cannot auto-complete.
    """
    signals = [_grounded("invoice_number", sources=("ocr",)),
               _grounded("total", sources=("ocr",))]
    decision = decide(signals, allow_ocr_auto_accept=False)
    assert decision.status == Status.NEEDS_REVIEW.value
    assert "scanned_document_review" in decision.reasons


def test_the_text_layer_is_unaffected_by_the_scan_rule() -> None:
    signals = [_grounded("invoice_number", sources=("text_layer",)),
               _grounded("total", sources=("text_layer",))]
    assert decide(signals, allow_ocr_auto_accept=False).status == (
        Status.COMPLETED.value
    )


def test_one_ocr_field_is_enough_to_hold_the_whole_document() -> None:
    """A mixed document is a scan for this purpose.

    A PDF with a text-layer header and a scanned table is exactly the case where
    the table is the part that matters and the part OCR gets wrong.
    """
    signals = [_grounded("invoice_number", sources=("text_layer",)),
               _grounded("line_items[0].amount", sources=("ocr",))]
    decision = decide(signals, allow_ocr_auto_accept=False)
    assert decision.status == Status.NEEDS_REVIEW.value
    assert "scanned_document_review" in decision.reasons


def test_the_scan_rule_can_be_turned_off_once_route_b_is_proven() -> None:
    """`FDIP_SCAN_AUTO_ACCEPT=true` is the switch, and it defaults to off."""
    signals = [_grounded("invoice_number", sources=("ocr",))]
    assert decide(signals, allow_ocr_auto_accept=True).status == (
        Status.COMPLETED.value
    )


def test_the_default_is_to_hold_scans() -> None:
    """Called without the argument, the safe behaviour is the one you get."""
    signals = [_grounded("total", sources=("ocr",))]
    assert decide(signals).status == Status.NEEDS_REVIEW.value


# -- 4. currency may only be derived from evidence on the page ----------------

def test_currency_is_derivable_from_a_symbol_on_the_page() -> None:
    assert is_derivable("currency", "MYR", {}, "Total Due RM2,142.72")
    assert is_derivable("currency", "MYR", {}, "Jumlah Besar MYR 2,142.72")
    assert is_derivable("currency", "EUR", {}, "Total EUR 1.234,50")
    assert is_derivable("currency", "SGD", {}, "Total S$1,234.50")


def test_currency_is_not_derivable_when_nothing_currency_like_is_printed() -> None:
    """The MYR default is gone.

    Defaulting looked harmless on a Malaysian corpus and is not: a document whose
    amounts are in Singapore dollars and whose symbol OCR dropped would have been
    accepted as Ringgit, silently, at a 3.2x error in the amount.
    """
    assert not is_derivable("currency", "MYR", {}, "Subtotal 1984.00 Total 2142.72")
    assert not is_derivable("currency", "MYR", {}, "")


def test_a_different_currency_on_the_page_is_a_disagreement() -> None:
    assert not is_derivable("currency", "MYR", {}, "Total S$1,234.50")


def test_the_derivable_fields_are_exactly_three() -> None:
    """Each addition is a field that can be accepted without being on the page,
    so the set is pinned rather than documented."""
    assert frozenset({"currency", "total", "tax_amount"}) == DERIVABLE_PATHS


def test_total_is_derivable_only_when_the_arithmetic_confirms_it() -> None:
    data = {"subtotal": "1984.00", "tax_amount": "158.72"}
    assert is_derivable("total", "2142.72", data)
    assert not is_derivable("total", "9999.00", data)
    # Magnitudes, so a credit note still balances.
    credit = {"subtotal": "-125.00", "tax_amount": "-10.00"}
    assert is_derivable("total", "-135.00", credit)


def test_tax_amount_is_derivable_only_from_the_stated_rate() -> None:
    data = {"subtotal": "1984.00", "tax_rate": "8"}
    assert is_derivable("tax_amount", "158.72", data)
    assert not is_derivable("tax_amount", "200.00", data)
    assert is_derivable("tax_amount", Decimal("0"),
                        {"subtotal": "100", "tax_rate": "0"})


def test_nothing_else_is_derivable() -> None:
    for path in ("invoice_number", "vendor_name", "invoice_date", "subtotal",
                 "line_items[0].amount"):
        assert not is_derivable(path, "anything", {}, "anything"), path


# -- the rule still reports everything it used --------------------------------

def test_reasons_name_the_field_and_the_cause() -> None:
    decision = decide(
        [FieldSignal(path="total", present=True, match="fuzzy_ocr",
                     required=True, sources=("ocr",), min_ocr_confidence=0.4)],
        allow_ocr_auto_accept=False,
    )
    assert decision.status == Status.NEEDS_REVIEW.value
    assert "field_not_grounded:total" in decision.reasons
    assert "scanned_document_review" in decision.reasons
    assert decision.field_reasons["total"] == ("possible_ocr_misread",)
    assert decision.rule_version


def test_a_missing_required_field_is_reported_as_missing_not_ungrounded() -> None:
    decision = decide([FieldSignal(path="total", present=False,
                                   match="not_checked", required=True)])
    assert decision.status == Status.NEEDS_REVIEW.value
    assert "required_field_missing:total" in decision.reasons
    assert decision.field_reasons["total"] == ("required_field_missing",)
    from fdip.domain.decision import field_status

    assert field_status(
        FieldSignal(path="total", present=False, match="not_checked",
                    required=True)
    )[0] == FieldStatus.MISSING.value


# -- the substring trap in the currency markers --------------------------------

@pytest.mark.parametrize(
    "text",
    ["Terms: 30 days nett", "WARM", "FORM 1040", "PERMIT NO 12",
     "PERFORMANCE BOND", "Charge"],
)
def test_an_ordinary_word_containing_a_currency_code_is_not_evidence(
    text: str,
) -> None:
    """`TERMS` contains `RM`.

    A plain substring test made "Terms: 30 days nett" evidence of Ringgit on a
    document with no currency printed anywhere -- the exact silent default the
    review asked to remove, arriving by a different route. Found by a test, not by
    reading.
    """
    from fdip.domain.derivation import currencies_printed

    assert currencies_printed(text) == set(), text
    assert not is_derivable("currency", "MYR", {}, text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Subtotal RM1,984.00", {"MYR"}),          # no space before the digits
        ("Jumlah RM 1,984.00", {"MYR"}),
        ("Total MYR 2,142.72", {"MYR"}),
        ("Total S$1,234.50", {"SGD"}),
        ("Total USD 99.00", {"USD"}),
        ("Amount EUR 1.234,50", {"EUR"}),
        ("Ringgit Malaysia Two Thousand", {"MYR"}),
        ("Total 2142.72", set()),                   # nothing printed
        ("Total $99.00", set()),                    # a bare symbol is ambiguous
    ],
)
def test_markers_are_read_at_a_letter_boundary(
    text: str, expected: set[str]
) -> None:
    from fdip.domain.derivation import currencies_printed

    assert currencies_printed(text) == expected, text
