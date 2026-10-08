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

from fdip.domain import display

#: Which columns are dates and which are amounts, so a schema's display formats
#: can be applied to the right ones. The API never sees any of this: it stays
#: ISO and decimal strings, and only a spreadsheet a person opens is reformatted.
_DATE_COLUMNS = frozenset({"invoice_date", "due_date"})
_AMOUNT_COLUMNS = frozenset({
    "subtotal", "discount_amount", "tax_amount", "rounding_adjustment", "total",
    "quantity", "unit_price", "amount",
})

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


def _formatted(column: str, value: Any,
               formats: Mapping[str, Any] | None) -> Any:
    config = (formats or {}).get(column)
    if not config:
        return value
    if column in _DATE_COLUMNS:
        return display.format_date(value, config.get("date_format"))
    if column in _AMOUNT_COLUMNS:
        return display.format_number(value, config.get("number_format"))
    return value


def header_row(document: Mapping[str, Any], extraction: Mapping[str, Any],
               data: Mapping[str, Any],
               formats: Mapping[str, Any] | None = None) -> list[str]:
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
        _text(_formatted(column, source.get(column, data.get(column)), formats))
        for column in HEADER_COLUMNS
    ]


def line_rows(document: Mapping[str, Any],
              data: Mapping[str, Any],
              formats: Mapping[str, Any] | None = None) -> list[list[str]]:
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
            _text(_formatted("quantity", row.get("quantity"), formats)),
            _text(_formatted("unit_price", row.get("unit_price"), formats)),
            _text(_formatted("amount", row.get("amount"), formats)),
            _text(row.get("tax_code")),
        ])
    return out


Formats = Mapping[str, Mapping[str, Any]]
"""Per extraction id, that version's `field_config`. Resolved by the caller,
because one export can span several schemas and each brings its own."""


def to_csv(records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
           formats: Formats | None = None) -> bytes:
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
        config = (formats or {}).get(str(extraction.get("id")))
        writer.writerow(["header",
                         *header_row(document, extraction, data, config),
                         *blank_line])
        for row in line_rows(document, data, config):
            writer.writerow(["line_item", *blank_header, *row[2:]])
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def to_xlsx(records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
            formats: Formats | None = None) -> bytes:
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
        config = (formats or {}).get(str(extraction.get("id")))
        headers.append(header_row(document, extraction, data, config))
        for row in line_rows(document, data, config):
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
           records: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
           formats: Formats | None = None) -> bytes:
    if fmt == "csv":
        return to_csv(records, formats)
    if fmt == "xlsx":
        return to_xlsx(records, formats)
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
