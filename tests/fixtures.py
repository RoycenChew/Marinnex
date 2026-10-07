"""Synthetic documents and scripted model answers. Mock mode only.

The invoices are generated rather than committed as binaries so a test can say
what it is testing -- a Malay label, an SST line, a credit note -- instead of
pointing at an opaque file. They are real PDFs with a real text layer, built with
pypdfium2's own writer so the pipeline's parse stage does actual work.

The scripted answers are keyed to the variant, which is the part that keeps mock
mode honest: a handler that returns the same invoice whatever it is shown would
make the end-to-end test pass with the wiring broken.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

A4 = (595.0, 842.0)
NEWLINE = chr(10)


@dataclass(frozen=True)
class Variant:
    """One synthetic document and the answer the mock model gives for it."""

    name: str
    lines: tuple[str, ...]
    data: dict[str, Any]
    document_type: str = "invoice"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


_ENGLISH = Variant(
    name="invoice_digital",
    lines=(
        "SOUTHERN STEEL TRADING SDN BHD",
        "Co. No. 201901234567   Tax ID C12345678901",
        "12 Jalan Perindustrian 3, 81100 Johor Bahru",
        "",
        "TAX INVOICE",
        "Invoice No: INV-2026-0417        Date: 17/03/2026",
        "PO Number: PO-88213             Payment Due: 16/04/2026",
        "",
        "Bill To: Harapan Engineering Sdn Bhd",
        "",
        "Description                        Qty   Unit Price      Amount",
        "Hex bolt stainless M8 HBS-1000      40        12.50      500.00",
        "Flange nut zinc plated FNZ-220     120         3.20      384.00",
        "Steel plate 6mm SP-6000              5       220.00     1100.00",
        "",
        "Subtotal                                              1984.00",
        "SST 8%                                                 158.72",
        "Total Due                                             2142.72",
        "",
        "Terms: 30 days nett",
    ),
    data={
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
)

_MALAY = Variant(
    name="invoice_malay",
    lines=(
        "PERNIAGAAN LOGAM BERSATU SDN BHD",
        "No. Pendaftaran 201801112223   No. Cukai C99887766554",
        "",
        "INVOIS CUKAI",
        "No. Invois: INV-MY-0092        Tarikh: 05/02/2026",
        "",
        "Bil Kepada: Kilang Perabot Maju Sdn Bhd",
        "",
        "Keterangan                      Kuantiti  Harga Seunit    Jumlah",
        "Paip keluli 25mm PK-250              30        18.00      540.00",
        "Penyambung L PL-100                  60         7.50      450.00",
        "",
        "Jumlah Kecil                                             990.00",
        "Cukai Jualan & Perkhidmatan 6%                            59.40",
        "Jumlah Besar                                            1049.40",
    ),
    data={
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
)

_CREDIT_NOTE = Variant(
    name="credit_note",
    lines=(
        "SOUTHERN STEEL TRADING SDN BHD",
        "Tax ID C12345678901",
        "",
        "CREDIT NOTE / NOTA KREDIT",
        "Credit Note No: CN-2026-0033    Date: 02/04/2026",
        "Against Invoice: INV-2026-0417",
        "",
        "Bill To: Harapan Engineering Sdn Bhd",
        "",
        "Description                        Qty   Unit Price      Amount",
        "Hex bolt stainless M8 HBS-1000      10        12.50     (125.00)",
        "",
        "Subtotal                                              (125.00)",
        "SST 8%                                                 (10.00)",
        "Total                                                 RM(135.00)",
    ),
    data={
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
    document_type="credit_note",
)

_BANK_STATEMENT = Variant(
    name="bank_statement",
    lines=(
        "MAYBANK BERHAD",
        "",
        "BANK STATEMENT / PENYATA BANK",
        "Account 5141 2233 4455        Statement Period: 01/03/2026 - 31/03/2026",
        "",
        "Opening Balance                                        12400.55",
        "",
        "Date        Description                 Debit     Credit",
        "03/03/2026  IBG TRANSFER IN                       5000.00",
        "11/03/2026  CHEQUE 004521            2140.00",
        "",
        "Closing Balance                                        15260.55",
    ),
    data={"document_type": "other"},
    document_type="bank_statement",
)

_SST_MULTI_RATE = Variant(
    name="invoice_two_tax_lines",
    lines=(
        "KLANG SERVICES SDN BHD",
        "Tax ID C55544433322",
        "",
        "TAX INVOICE",
        "Invoice No: KS-2026-7781        Date: 22/01/2026",
        "",
        "Bill To: Pelabuhan Utara Sdn Bhd",
        "",
        "Description                        Qty   Unit Price      Amount",
        "Forklift rental monthly FR-900        1      1800.00     1800.00",
        "Operator service OS-120             20        45.00      900.00",
        "",
        "Subtotal                                              2700.00",
        "Service Tax 6% on services                             54.00",
        "Sales Tax 10% on goods                                180.00",
        "Total Payable                                         2934.00",
    ),
    data={
        "document_type": "invoice",
        "invoice_number": "KS-2026-7781",
        "invoice_date": "2026-01-22",
        "vendor_name": "KLANG SERVICES SDN BHD",
        "vendor_tax_id": "C55544433322",
        "buyer_name": "Pelabuhan Utara Sdn Bhd",
        "currency": "MYR",
        "subtotal": "2700.00",
        "tax_amount": "234.00",
        "total": "2934.00",
        "tax_lines": [
            {"rate": "6", "amount": "54.00", "label": "Service Tax"},
            {"rate": "10", "amount": "180.00", "label": "Sales Tax"},
        ],
        "line_items": [
            {"description": "Forklift rental monthly FR-900", "quantity": "1",
             "unit_price": "1800.00", "amount": "1800.00"},
            {"description": "Operator service OS-120", "quantity": "20",
             "unit_price": "45.00", "amount": "900.00"},
        ],
    },
)

_BAD_ARITHMETIC = Variant(
    name="invoice_wrong_total",
    lines=(
        "SEEDED ERROR TRADING SDN BHD",
        "",
        "TAX INVOICE",
        "Invoice No: BAD-0001            Date: 09/03/2026",
        "",
        "Bill To: Nobody Sdn Bhd",
        "",
        "Description                        Qty   Unit Price      Amount",
        "Widget W-1                          10        10.00      100.00",
        "",
        "Subtotal                                               100.00",
        "SST 8%                                                   8.00",
        "Total Due                                              999.00",
    ),
    data={
        "document_type": "invoice",
        "invoice_number": "BAD-0001",
        "invoice_date": "2026-03-09",
        "vendor_name": "SEEDED ERROR TRADING SDN BHD",
        "buyer_name": "Nobody Sdn Bhd",
        "currency": "MYR",
        "subtotal": "100.00",
        "tax_rate": "8",
        "tax_amount": "8.00",
        # 100 + 8 is not 999. The validators must catch it and the decision rule
        # must route the document to review rather than accepting it.
        "total": "999.00",
        "line_items": [
            {"description": "Widget W-1", "quantity": "10",
             "unit_price": "10.00", "amount": "100.00"},
        ],
    },
)

VARIANTS: tuple[Variant, ...] = (
    _ENGLISH, _MALAY, _CREDIT_NOTE, _BANK_STATEMENT, _SST_MULTI_RATE,
    _BAD_ARITHMETIC,
)
BY_NAME = {variant.name: variant for variant in VARIANTS}


def write_pdf(path: Path, variant: Variant) -> Path:
    """A one-page PDF with a real text layer, written by hand.

    Hand-rolled rather than via a library because the installed pypdfium2 has no
    writer API and the alternative is a new dependency for test data. The same
    approach is already used by the toolkit's stress corpus. Courier is a PDF
    base-14 font, so nothing has to be embedded and the output is byte-stable.
    """
    NL = b"\n"
    drawn = []
    y = A4[1] - 60
    for line in variant.lines:
        if line.strip():
            drawn.append(
                b"BT /F1 9 Tf 40 " + ascii_bytes(round(y, 1)) + b" Td ("
                + _escape(line) + b") Tj ET" + NL
            )
        y -= 13
    stream = b"".join(drawn)

    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")
    pages = add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    content = add(
        b"<< /Length " + ascii_bytes(len(stream)) + b" >>" + NL + b"stream" + NL
        + stream + b"endstream"
    )
    page = add(
        b"<< /Type /Page /Parent " + ascii_bytes(pages)
        + b" 0 R /MediaBox [0 0 " + ascii_bytes(int(A4[0])) + b" "
        + ascii_bytes(int(A4[1])) + b"] /Resources << /Font << /F1 "
        + ascii_bytes(font) + b" 0 R >> >> /Contents "
        + ascii_bytes(content) + b" 0 R >>"
    )
    objects[catalog - 1] = (
        b"<< /Type /Catalog /Pages " + ascii_bytes(pages) + b" 0 R >>"
    )
    objects[pages - 1] = (
        b"<< /Type /Pages /Kids [" + ascii_bytes(page) + b" 0 R] /Count 1 >>"
    )

    out = bytearray(b"%PDF-1.4" + NL)
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += ascii_bytes(number) + b" 0 obj" + NL + body + NL + b"endobj" + NL
    xref = len(out)
    out += b"xref" + NL + b"0 " + ascii_bytes(len(objects) + 1) + NL
    out += b"0000000000 65535 f " + NL
    for offset in offsets:
        out += ("%010d 00000 n " % offset).encode("ascii") + NL
    out += (
        b"trailer" + NL + b"<< /Size " + ascii_bytes(len(objects) + 1)
        + b" /Root 1 0 R >>" + NL + b"startxref" + NL + ascii_bytes(xref) + NL
        + b"%%EOF" + NL
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))
    return path


def ascii_bytes(value: object) -> bytes:
    return str(value).encode("ascii")


def _escape(text: str) -> bytes:
    r"""PDF string escaping.

    An unescaped bracket in a vendor name ends the string early and the rest of
    the page silently disappears, which looks like a parser bug rather than a
    fixture bug. Backslash first, or the escapes escape each other.
    """
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return out.encode("latin-1", "replace")


def scripted_fixtures(variant: Variant) -> dict[str, str]:
    """The two answers mock mode needs for this variant."""
    return {
        "classify": json.dumps({
            "document_type": variant.document_type, "confidence": 0.95,
        }),
        "extract": json.dumps(variant.data),
    }


def marker_for(variant: Variant) -> str:
    """The one string that identifies this variant in a prompt.

    A document's own reference, which is printed before any reference it cites.
    That ordering is what the handler relies on.
    """
    return str(variant.data.get("invoice_number") or "") or "BANK STATEMENT"


def handler_for(variants: tuple[Variant, ...] = VARIANTS) -> Any:
    """A mock handler that answers according to what it was actually shown.

    It picks the variant whose own reference appears **earliest** in the prompt.
    Two earlier rules both failed, and the reasons are worth keeping:

    * First match in declaration order answered the credit note as the invoice,
      because the credit note cites `INV-2026-0417` in its "Against Invoice" line.
    * Counting several markers tied, because the prompt also carries the schema,
      and the `invoice_number` description contains the words "Tax Invoice No".

    Earliest position is immune to both: the schema text holds no references at
    all, and a document prints its own number above the one it credits.
    """
    markers = [(variant, marker_for(variant)) for variant in variants]

    def handler(messages: Any) -> str:
        text = NEWLINE.join(str(getattr(m, "content", "")) for m in messages)
        upper = text.upper()
        best = variants[0]
        best_at = len(upper) + 1
        for variant, marker in markers:
            at = upper.find(marker.upper())
            if at >= 0 and at < best_at:
                best, best_at = variant, at
        if "classify this document" in text.lower():
            return json.dumps({
                "document_type": best.document_type, "confidence": 0.95,
            })
        return json.dumps(best.data)

    return handler


__all__ = [
    "A4",
    "BY_NAME",
    "VARIANTS",
    "Variant",
    "handler_for",
    "marker_for",
    "scripted_fixtures",
    "write_pdf",
]
