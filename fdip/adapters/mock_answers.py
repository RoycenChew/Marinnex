"""Answers mock mode gives for the documents in `samples/`.

Mock mode exists so the pipeline can be run and demonstrated with no provider and
no spend. For that to be worth anything it has to produce a real answer for the
documents shipped alongside it: `fdip run samples/invoice_digital.pdf` returning
fourteen nulls teaches the reader nothing and makes `README_RUN.md` wrong.

These are **fixtures, not extraction**. They are selected by the reference printed
on the document, and a document that is not one of the samples falls through to an
empty answer -- which is the honest outcome, because nothing here read it. Mock
mode is for wiring, never for accuracy: an accuracy number from this module would
be a number about this file.

Matching is by **earliest** reference in the prompt, because a credit note cites
the invoice it credits and first-match answers the wrong one.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

SAMPLE_ANSWERS: dict[str, dict[str, Any]] = {
    "INV-2026-0417": {
        "document_type": "invoice",
        "invoice_number": "INV-2026-0417",
        "invoice_date": "2026-03-17",
        "due_date": "2026-04-16",
        "po_number": "PO-88213",
        "vendor_name": "SOUTHERN STEEL TRADING SDN BHD",
        "vendor_registration_no": "201901234567",
        "vendor_tax_id": "C12345678901",
        "buyer_name": "Harapan Engineering Sdn Bhd",
        "currency": "MYR",
        "subtotal": "1984.00",
        "tax_rate": "8",
        "tax_amount": "158.72",
        "total": "2142.72",
        "payment_terms": "30 days nett",
        "line_items": [
            {"description": "Hex bolt stainless M8 HBS-1000", "quantity": "40",
             "unit_price": "12.50", "amount": "500.00"},
            {"description": "Flange nut zinc plated FNZ-220", "quantity": "120",
             "unit_price": "3.20", "amount": "384.00"},
            {"description": "Steel plate 6mm SP-6000", "quantity": "5",
             "unit_price": "220.00", "amount": "1100.00"},
        ],
    },
    "INV-MY-0092": {
        "document_type": "invoice",
        "invoice_number": "INV-MY-0092",
        "invoice_date": "2026-02-05",
        "vendor_name": "PERNIAGAAN LOGAM BERSATU SDN BHD",
        "vendor_registration_no": "201801112223",
        "vendor_tax_id": "C99887766554",
        "buyer_name": "Kilang Perabot Maju Sdn Bhd",
        "currency": "MYR",
        "subtotal": "990.00",
        "tax_rate": "6",
        "tax_amount": "59.40",
        "total": "1049.40",
        "line_items": [
            {"description": "Paip keluli 25mm PK-250", "quantity": "30",
             "unit_price": "18.00", "amount": "540.00"},
            {"description": "Penyambung L PL-100", "quantity": "60",
             "unit_price": "7.50", "amount": "450.00"},
        ],
    },
    "CN-2026-0033": {
        "document_type": "credit_note",
        "invoice_number": "CN-2026-0033",
        "invoice_date": "2026-04-02",
        "vendor_name": "SOUTHERN STEEL TRADING SDN BHD",
        "vendor_tax_id": "C12345678901",
        "buyer_name": "Harapan Engineering Sdn Bhd",
        "currency": "MYR",
        "subtotal": "-125.00",
        "tax_rate": "8",
        "tax_amount": "-10.00",
        "total": "-135.00",
        "line_items": [
            {"description": "Hex bolt stainless M8 HBS-1000", "quantity": "10",
             "unit_price": "12.50", "amount": "-125.00"},
        ],
    },
    "BANK STATEMENT": {"document_type": "other"},
}

DOCUMENT_TYPES: dict[str, str] = {
    "INV-2026-0417": "invoice",
    "INV-MY-0092": "invoice",
    "CN-2026-0033": "credit_note",
    "BANK STATEMENT": "bank_statement",
}


def best_match(text: str) -> str | None:
    """The reference that appears earliest in the prompt, or None."""
    upper = text.upper()
    best: str | None = None
    best_at = len(upper) + 1
    for marker in SAMPLE_ANSWERS:
        at = upper.find(marker)
        if 0 <= at < best_at:
            best, best_at = marker, at
    return best


def answer_for(messages: Sequence[Any],
               overrides: Mapping[str, str] | None = None) -> str:
    """The mock reply: a classification or an extraction, as JSON text."""
    text = "\n".join(str(getattr(message, "content", "")) for message in messages)
    classifying = "classify this document" in text.lower()
    if overrides:
        key = "classify" if classifying else "extract"
        if key in overrides:
            return overrides[key]

    marker = best_match(text)
    if classifying:
        return json.dumps({
            "document_type": DOCUMENT_TYPES.get(marker or "", "unknown"),
            "confidence": 0.95 if marker else 0.0,
        })
    if marker is None:
        # Not a shipped sample. An empty object is the truthful answer: nothing
        # here read the document, and inventing fields would be worse than null.
        return "{}"
    return json.dumps(SAMPLE_ANSWERS[marker])


__all__ = ["DOCUMENT_TYPES", "SAMPLE_ANSWERS", "answer_for", "best_match"]
