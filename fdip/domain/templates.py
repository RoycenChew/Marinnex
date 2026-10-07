"""The invoice SchemaTemplate: FDIP's own field vocabulary.

This is the file the toolkit is forbidden to contain (CLAUDE.md 2.1): `tax`,
`currency` and `invoice` are financial concepts and they live here.

Every description carries its synonyms, in English and Malay, because a field
description is the cheapest accuracy lever in the system and a missing synonym
costs a repair round. The one description earned the hard way is
`line_items.description`: the benchmark's only two silent errors in 420
documents were both the model tidying a part code off the end of a cell, so the
text now demands the cell verbatim.

Money is a decimal plus a currency, never a float (rule 2.2).

Several descriptions used to end "Zero if none", and that was a mistake caught by
the live smoke test: it asks the model to invent a value for a line the document
does not have, grounding then correctly reports the invented zero as `not_found`,
and the document goes to review for a field that was simply absent. **Absence is
verifiable; an invented zero is not.** So an optional field that is not printed is
omitted, and a zero is only ever an answer where a zero is actually shown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FieldKind = Literal["string", "decimal", "integer", "date", "enum", "array"]

TEMPLATE_VERSION = 1


@dataclass(frozen=True)
class TemplateField:
    path: str
    label: str
    kind: FieldKind
    description: str
    required_default: bool = True
    is_array: bool = False
    enum: tuple[str, ...] = ()
    pattern: str = ""
    money: bool = False
    """Money fields carry the document's currency and are compared as Decimal."""
    grounding: Literal["required", "derivable", "optional"] = "required"
    children: tuple[TemplateField, ...] = field(default_factory=tuple)


_LINE_ITEM_FIELDS: tuple[TemplateField, ...] = (
    TemplateField(
        "line_items[].description", "Description", "string",
        "The whole item text of that row exactly as printed, labelled "
        "Description, Particulars, Item or Keterangan. If the cell ends in a "
        "part or item code such as HBS-1000, keep it: return the cell verbatim "
        "and do not split, shorten or tidy it.",
    ),
    TemplateField(
        "line_items[].quantity", "Qty", "decimal",
        "Units ordered on that row, labelled Qty, Quantity, Unit or Kuantiti.",
    ),
    TemplateField(
        "line_items[].unit_price", "Unit price", "decimal",
        "Price for one unit on that row, labelled Unit Price, Price, Rate or "
        "Harga Seunit. Digits only.",
        money=True,
    ),
    TemplateField(
        "line_items[].amount", "Amount", "decimal",
        "The row total, labelled Amount, Total or Jumlah. Normally quantity "
        "times unit price, but return what is printed.",
        money=True,
    ),
    TemplateField(
        "line_items[].tax_code", "Tax code", "string",
        "The per-row tax code or rate if the table has such a column, for "
        "example SR, ZRL, OS or 8 percent. Omit if there is no such column.",
        required_default=False,
    ),
)

_TAX_LINE_FIELDS: tuple[TemplateField, ...] = (
    TemplateField(
        "tax_lines[].rate", "Rate", "decimal",
        "The tax percentage on that line as a number, so 8 for 8 percent.",
    ),
    TemplateField(
        "tax_lines[].amount", "Tax amount", "decimal",
        "The tax amount in currency on that line, not the percentage.",
        money=True,
    ),
    TemplateField(
        "tax_lines[].label", "Label", "string",
        "The label printed for that tax line, for example SST, Service Tax, "
        "Cukai Jualan or GST.",
        required_default=False,
    ),
)

INVOICE_TEMPLATE_FIELDS: tuple[TemplateField, ...] = (
    TemplateField(
        "document_type", "Document type", "enum",
        "Whether the document is an invoice or a credit note. A credit note is "
        "labelled Credit Note or Nota Kredit and reduces what is owed.",
        enum=("invoice", "credit_note"),
    ),
    TemplateField(
        "invoice_number", "Invoice number", "string",
        "The invoice or credit note reference printed on the document, labelled "
        "Invoice No, Tax Invoice No, No. Invois, Credit Note No or No. Nota "
        "Kredit.",
    ),
    TemplateField(
        "invoice_date", "Invoice date", "date",
        "The date the document was issued, labelled Date, Invoice Date or "
        "Tarikh. Malaysian documents write the day first.",
    ),
    TemplateField(
        "due_date", "Due date", "date",
        "The date payment is due, labelled Payment Due, Due Date or Tarikh "
        "Bayaran.",
        required_default=False,
    ),
    TemplateField(
        "po_number", "PO number", "string",
        "The buyer's purchase order reference, labelled PO Number, P/O No or "
        "No. PO.",
        required_default=False,
    ),
    TemplateField(
        "do_number", "DO number", "string",
        "The delivery order reference, labelled DO No or No. DO.",
        required_default=False,
    ),
    TemplateField(
        "vendor_name", "Vendor name", "string",
        "The supplier issuing the document, usually the largest text at the top. "
        "Not the buyer, and not the bank named in the payment details.",
    ),
    TemplateField(
        "vendor_registration_no", "Vendor registration no", "string",
        "The supplier's company registration number, labelled Co. No, "
        "Company No, ROC or No. Pendaftaran.",
        required_default=False,
    ),
    TemplateField(
        "vendor_tax_id", "Vendor tax ID", "string",
        "The supplier's tax registration number, labelled Tax ID, TIN, SST No, "
        "GST No or No. Cukai. A Malaysian TIN is the letter C followed by "
        "eleven digits.",
        required_default=False,
    ),
    TemplateField(
        "vendor_address", "Vendor address", "string",
        "The supplier's full address as printed, newlines collapsed to spaces.",
        required_default=False,
    ),
    TemplateField(
        "vendor_contact", "Vendor contact", "string",
        "The supplier's telephone, fax or email as printed.",
        required_default=False,
    ),
    TemplateField(
        "buyer_name", "Buyer name", "string",
        "The company being billed, labelled Bill To, Sold To, Customer or "
        "Bil Kepada.",
        required_default=False,
    ),
    TemplateField(
        "buyer_tax_id", "Buyer tax ID", "string",
        "The buyer's tax registration number if printed.",
        required_default=False,
    ),
    TemplateField(
        "buyer_address", "Buyer address", "string",
        "The billing address as printed, newlines collapsed to spaces.",
        required_default=False,
    ),
    TemplateField(
        "currency", "Currency", "enum",
        "The ISO 4217 code of the amounts. RM and MYR both mean MYR; S$ means "
        "SGD. If no symbol appears anywhere, answer MYR.",
        enum=("MYR", "USD", "SGD", "EUR", "GBP", "CNY", "THB", "IDR"),
        # Derivable: an ISO code is usually not printed. `RM` on the page means
        # MYR, and bare amounts on a Malaysian invoice mean MYR by FDIP's own
        # decision. `fdip.domain.derivation` holds the rule.
        grounding="derivable",
    ),
    TemplateField(
        "subtotal", "Subtotal", "decimal",
        "The total of the line items before tax, labelled Subtotal, Total "
        "Excluding Tax or Jumlah Kecil. Digits only, no currency symbol.",
        money=True,
    ),
    TemplateField(
        "discount_amount", "Discount", "decimal",
        "Any discount deducted before tax, labelled Discount, Less or Diskaun. "
        "Omit this field entirely if the document shows no discount line: do "
        "not answer zero for a line that is not printed.",
        required_default=False, money=True,
    ),
    TemplateField(
        "tax_rate", "Tax rate", "decimal",
        "The tax percentage as a number, so 8 for 8 percent. The line is "
        "labelled SST, Cukai Jualan, Cukai Jualan & Perkhidmatan, Service Tax, "
        "Sales Tax, GST or VAT. Omit this field entirely if no tax line is "
        "printed; answer 0 only where a zero rate is actually shown.",
        required_default=False,
    ),
    TemplateField(
        "tax_amount", "Tax amount", "decimal",
        "The tax amount in currency, not the percentage. Omit this field "
        "entirely if no tax line is printed; answer 0 only where a zero amount "
        "is actually shown.",
        required_default=False, money=True, grounding="derivable",
    ),
    TemplateField(
        "tax_lines", "Tax lines", "array",
        "One entry per distinct tax line when the document shows more than one "
        "rate. Leave empty when there is a single tax line.",
        required_default=False, is_array=True, children=_TAX_LINE_FIELDS,
        grounding="optional",
    ),
    TemplateField(
        "rounding_adjustment", "Rounding", "decimal",
        "Any rounding adjustment line, labelled Rounding or Pembundaran. "
        "Malaysian invoices round to the nearest 5 sen. Omit this field "
        "entirely if no such line is printed.",
        required_default=False, money=True,
    ),
    TemplateField(
        "total", "Total", "decimal",
        "The final amount payable after tax, labelled Total Due, Grand Total, "
        "Total Payable or Jumlah Besar. Digits only, no currency symbol.",
        money=True, grounding="derivable",
    ),
    TemplateField(
        "amount_in_words", "Amount in words", "string",
        "The total written in words if printed, for example Ringgit Malaysia "
        "Twelve Thousand Only.",
        required_default=False,
    ),
    TemplateField(
        "payment_terms", "Payment terms", "string",
        "The payment terms as printed, for example 30 days nett or C.O.D.",
        required_default=False,
    ),
    TemplateField(
        "bank_account", "Bank account", "string",
        "The supplier's bank account number for payment, if printed.",
        required_default=False,
    ),
    TemplateField(
        "line_items", "Line items", "array",
        "One entry for every goods or service row in the table. Do not include "
        "a Brought forward or Jumlah dibawa ke hadapan row: that is a running "
        "total, not an item. Do not include the repeated column header on later "
        "pages, and do not include the subtotal, tax or total rows.",
        is_array=True, children=_LINE_ITEM_FIELDS,
    ),
)

INVOICE_DESCRIPTION = (
    "A Malaysian supplier invoice or credit note. Labels may be in English or "
    "Malay, often both on the same document. Amounts are usually in Malaysian "
    "Ringgit. A value in parentheses is negative."
)

DEFAULT_SELECTED_FIELDS: tuple[str, ...] = (
    "invoice_number", "invoice_date", "vendor_name", "currency",
    "subtotal", "tax_rate", "tax_amount", "total", "line_items",
)
"""What a new schema selects unless the caller says otherwise: the fields a
finance team actually integrates, not all twenty-six."""


def invoice_template_fields() -> tuple[TemplateField, ...]:
    return INVOICE_TEMPLATE_FIELDS


def flatten(
    fields: tuple[TemplateField, ...] = INVOICE_TEMPLATE_FIELDS,
) -> list[TemplateField]:
    """Template fields including array children, for the `GET /templates` list."""
    out: list[TemplateField] = []
    for spec in fields:
        out.append(spec)
        out.extend(spec.children)
    return out


def field_by_path(path: str) -> TemplateField | None:
    for spec in flatten():
        if spec.path == path:
            return spec
    return None


MONEY_PATHS: frozenset[str] = frozenset(
    spec.path for spec in flatten() if spec.money
)

__all__ = [
    "DEFAULT_SELECTED_FIELDS",
    "INVOICE_DESCRIPTION",
    "INVOICE_TEMPLATE_FIELDS",
    "MONEY_PATHS",
    "TEMPLATE_VERSION",
    "FieldKind",
    "TemplateField",
    "field_by_path",
    "flatten",
    "invoice_template_fields",
]
