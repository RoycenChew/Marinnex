"""Business validation: stage 9, deterministic, no model involved.

These are the checks that catch the failure grounding cannot. A hallucinated
total is usually *not* on the page, so grounding catches it; a total that is on
the page but belongs to the wrong column is grounded perfectly and only
arithmetic catches it. That is why both run.

Credit notes are the reason every amount comparison is on **magnitudes**: a
credit note prints its figures positive and means them negative, or prints them
in brackets, and either way subtotal plus tax still equals total in absolute
terms. One separate check reports a row whose sign disagrees with the document,
so the information is not simply discarded.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from fdip.domain.money import TOLERANCE, close_enough, quantise, to_decimal

Severity = Literal["info", "warning", "critical"]


@dataclass(frozen=True)
class ValidationResult:
    code: str
    severity: Severity
    message: str
    path: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


def _rows(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = data.get("line_items")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    return [r for r in rows if isinstance(r, Mapping)]


def check_required(data: Mapping[str, Any],
                   required: Sequence[str]) -> list[ValidationResult]:
    out = []
    for path in required:
        value = data.get(path)
        if value is None or (isinstance(value, str) and not value.strip()):
            out.append(ValidationResult(
                "required_field_missing", "critical",
                "%s is required by this schema version but was not found" % path,
                path,
            ))
    return out


def check_line_amounts(data: Mapping[str, Any]) -> list[ValidationResult]:
    """quantity x unit_price should equal the row amount, compared as magnitudes."""
    out = []
    for index, row in enumerate(_rows(data)):
        quantity = to_decimal(row.get("quantity"))
        price = to_decimal(row.get("unit_price"))
        amount = to_decimal(row.get("amount"))
        if quantity is None or price is None or amount is None:
            continue
        expected = quantise(quantity * price)
        if not close_enough(abs(expected), abs(amount)):
            out.append(ValidationResult(
                "line_amount_mismatch", "warning",
                "row %d: quantity times unit price is %s but the amount reads %s"
                % (index + 1, expected, quantise(amount)),
                "line_items[%d].amount" % index,
            ))
    return out


def check_line_signs(data: Mapping[str, Any]) -> list[ValidationResult]:
    """A row whose sign disagrees with the rest of the document.

    Reported rather than corrected: on a credit note the sign is the whole
    meaning of the row, and guessing it is how a refund becomes a charge.
    """
    amounts = [
        to_decimal(row.get("amount")) for row in _rows(data)
    ]
    present = [a for a in amounts if a is not None and a != 0]
    if len(present) < 2:
        return []
    negatives = sum(1 for a in present if a < 0)
    if negatives in (0, len(present)):
        return []
    return [ValidationResult(
        "line_signs_disagree", "warning",
        "%d of %d line amounts are negative, so the document mixes charges and "
        "credits" % (negatives, len(present)),
        "line_items",
    )]


def check_subtotal(data: Mapping[str, Any]) -> list[ValidationResult]:
    rows = _rows(data)
    subtotal = to_decimal(data.get("subtotal"))
    if subtotal is None or not rows:
        return []
    amounts = [to_decimal(row.get("amount")) for row in rows]
    if any(a is None for a in amounts):
        return []
    summed = quantise(sum((abs(a) for a in amounts if a is not None), Decimal(0)))
    discount = to_decimal(data.get("discount_amount")) or Decimal(0)
    for candidate in (summed, quantise(summed - abs(discount))):
        if close_enough(candidate, abs(subtotal)):
            return []
    return [ValidationResult(
        "line_sum_ne_subtotal", "warning",
        "the line amounts sum to %s but the subtotal reads %s"
        % (summed, quantise(subtotal)),
        "subtotal",
    )]


def check_total(data: Mapping[str, Any]) -> list[ValidationResult]:
    subtotal = to_decimal(data.get("subtotal"))
    tax = to_decimal(data.get("tax_amount")) or Decimal(0)
    total = to_decimal(data.get("total"))
    if subtotal is None or total is None:
        return []
    rounding = to_decimal(data.get("rounding_adjustment")) or Decimal(0)
    expected = quantise(abs(subtotal) + abs(tax) + rounding)
    if close_enough(expected, abs(total)):
        return []
    # Try it without the rounding line too, since some documents fold the
    # adjustment into the total they print.
    if close_enough(quantise(abs(subtotal) + abs(tax)), abs(total)):
        return []
    return [ValidationResult(
        "subtotal_plus_tax_ne_total", "critical",
        "subtotal plus tax is %s but the total reads %s"
        % (expected, quantise(total)),
        "total",
    )]


def check_tax_rate(data: Mapping[str, Any]) -> list[ValidationResult]:
    rate = to_decimal(data.get("tax_rate"))
    tax = to_decimal(data.get("tax_amount"))
    subtotal = to_decimal(data.get("subtotal"))
    if rate is None or tax is None or subtotal is None:
        return []
    if rate == 0 and tax == 0:
        return []
    if rate == 0 or subtotal == 0:
        return []
    expected = quantise(abs(subtotal) * rate / Decimal(100))
    # The tolerance widens with the base: a rate applied per line and then summed
    # legitimately differs from the rate applied to the subtotal by a sen a line.
    allowance = max(TOLERANCE, quantise(abs(subtotal) / Decimal(1000)))
    if close_enough(expected, abs(tax), allowance):
        return []
    return [ValidationResult(
        "tax_rate_amount_mismatch", "warning",
        "%s%% of %s is %s but the tax amount reads %s"
        % (rate, quantise(abs(subtotal)), expected, quantise(tax)),
        "tax_amount",
    )]


def check_tax_lines(data: Mapping[str, Any]) -> list[ValidationResult]:
    lines = data.get("tax_lines")
    tax = to_decimal(data.get("tax_amount"))
    if not isinstance(lines, Sequence) or isinstance(lines, (str, bytes)):
        return []
    amounts = [
        to_decimal(line.get("amount")) for line in lines
        if isinstance(line, Mapping)
    ]
    present = [a for a in amounts if a is not None]
    if tax is None or not present:
        return []
    summed = quantise(sum((abs(a) for a in present), Decimal(0)))
    if close_enough(summed, abs(tax)):
        return []
    return [ValidationResult(
        "tax_lines_ne_tax_amount", "warning",
        "the tax lines sum to %s but the tax amount reads %s" % (summed, quantise(tax)),
        "tax_amount",
    )]


def check_dates(data: Mapping[str, Any]) -> list[ValidationResult]:
    invoice_date = data.get("invoice_date")
    due_date = data.get("due_date")
    if not isinstance(invoice_date, str) or not isinstance(due_date, str):
        return []
    if invoice_date and due_date and due_date < invoice_date:
        return [ValidationResult(
            "due_date_before_invoice_date", "warning",
            "the due date %s falls before the invoice date %s"
            % (due_date, invoice_date),
            "due_date",
        )]
    return []


def check_credit_note_signs(data: Mapping[str, Any]) -> list[ValidationResult]:
    """A credit note whose total is printed positive is normal, not an error.

    This check exists for the opposite case: an ordinary invoice with a negative
    total, which usually means a credit note was misclassified.
    """
    total = to_decimal(data.get("total"))
    document_type = data.get("document_type")
    if total is None or total >= 0:
        return []
    if document_type == "credit_note":
        return []
    return [ValidationResult(
        "negative_total_on_invoice", "warning",
        "the total is negative on a document classified as an invoice, which "
        "usually means it is a credit note",
        "total",
    )]


CHECKS = (
    check_line_amounts,
    check_line_signs,
    check_subtotal,
    check_total,
    check_tax_rate,
    check_tax_lines,
    check_dates,
    check_credit_note_signs,
)


def validate(data: Mapping[str, Any],
             required: Sequence[str] = ()) -> list[ValidationResult]:
    """Every check, every issue. Nothing short-circuits.

    A caller that only sees the first failure cannot tell a document with one
    problem from a document with nine, and the review queue needs that
    difference.
    """
    out: list[ValidationResult] = list(check_required(data, required))
    for check in CHECKS:
        out.extend(check(data))
    return out


__all__ = [
    "CHECKS",
    "Severity",
    "ValidationResult",
    "check_credit_note_signs",
    "check_dates",
    "check_line_amounts",
    "check_line_signs",
    "check_required",
    "check_subtotal",
    "check_tax_lines",
    "check_tax_rate",
    "check_total",
    "validate",
]
