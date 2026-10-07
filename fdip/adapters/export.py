"""CSV and Excel export.

Two shapes, because a spreadsheet cannot be both: a header row per document, and
a line-item row per row. The CSV is one flat file with a `record_type` column;
the workbook puts them on two sheets, which is what a finance team actually
wants.

Amounts are written as **text** in both. Excel will happily turn `1,234.50` into
a float and `C12345678901` into scientific notation, and a tax number silently
retyped is worse than an ugly column.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

HEADER_COLUMNS: tuple[str, ...] = (
    "document_id", "filename", "status", "document_type", "currency",
    "invoice_number", "invoice_date", "due_date", "po_number",
    "vendor_name", "vendor_tax_id", "buyer_name",
    "subtotal", "discount_amount", "tax_rate", "tax_amount",
    "rounding_adjustment", "total", "payment_terms",
    "extraction_id", "extraction_version", "reasons",
)

LINE_COLUMNS: tuple[str, ...] = (
    "document_id", "invoice_number", "row_number",
    "description", "quantity", "unit_price", "amount", "tax_code",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value)
    return str(value)


def header_row(document: Mapping[str, Any], extraction: Mapping[str, Any],
               data: Mapping[str, Any]) -> list[str]:
    source: dict[str, Any] = {
        "document_id": document.get("id"),
        "filename": document.get("filename"),
        "status": extraction.get("status") or document.get("status"),
        "document_type": extraction.get("document_type"),
        "currency": extraction.get("currency"),
        "extraction_id": extraction.get("id"),
        "extraction_version": extraction.get("version"),
        "reasons": extraction.get("reasons"),
    }
    return [
        _text(source.get(column, data.get(column))) for column in HEADER_COLUMNS
    ]


def line_rows(document: Mapping[str, Any],
              data: Mapping[str, Any]) -> list[list[str]]:
    rows = data.get("line_items")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    out = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        out.append([
            _text(document.get("id")),
            _text(data.get("invoice_number")),
            str(index + 1),
            _text(row.get("description")),
            _text(row.get("quantity")),
            _text(row.get("unit_price")),
            _text(row.get("amount")),
            _text(row.get("tax_code")),
        ])
    return out


def to_csv(records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> bytes:
    """One flat file. `record_type` distinguishes a header row from a line row.

    UTF-8 with a BOM, because Excel on Windows reads a BOM-less UTF-8 CSV as the
    system codepage and turns every Malay or Chinese vendor name into mojibake.
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["record_type", *HEADER_COLUMNS, *LINE_COLUMNS[2:]])
    blank_line = [""] * (len(LINE_COLUMNS) - 2)
    blank_header = [""] * len(HEADER_COLUMNS)
    for document, extraction in records:
        data = extraction.get("data") or {}
        writer.writerow(["header", *header_row(document, extraction, data),
                         *blank_line])
        for row in line_rows(document, data):
            writer.writerow(["line_item", *blank_header, *row[2:]])
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def to_xlsx(records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> bytes:
    """Two sheets: Documents and Line items."""
    from openpyxl import Workbook

    workbook = Workbook()
    headers = workbook.active
    headers.title = "Documents"
    headers.append(list(HEADER_COLUMNS))
    lines = workbook.create_sheet("Line items")
    lines.append(list(LINE_COLUMNS))

    for document, extraction in records:
        data = extraction.get("data") or {}
        headers.append(header_row(document, extraction, data))
        for row in line_rows(document, data):
            lines.append(row)

    for sheet in (headers, lines):
        for column in sheet.iter_cols(min_row=2):
            for cell in column:
                # Text, not a number. See the module docstring.
                cell.number_format = "@"
        sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render(fmt: str,
           records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> bytes:
    if fmt == "csv":
        return to_csv(records)
    if fmt == "xlsx":
        return to_xlsx(records)
    raise ValueError("format must be csv or xlsx")


MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
}


__all__ = [
    "HEADER_COLUMNS",
    "LINE_COLUMNS",
    "MEDIA_TYPES",
    "header_row",
    "line_rows",
    "render",
    "to_csv",
    "to_xlsx",
]
