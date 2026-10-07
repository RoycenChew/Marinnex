"""The `derived` match class: values FDIP may accept without finding them.

CLAUDE.md 3.4 defines `derived` as "not on the page but equals a deterministic
computation the schema allows", accepted only where the field is marked
`x-grounding: derivable`. The toolkit cannot decide this -- that subtotal plus tax
makes a total, or that a Malaysian invoice with no symbol is in Ringgit, are
financial facts (rule 2.1) -- so the rules live here.

Each rule must be **deterministic and checkable**. That is the whole difference
between `derived` and a hallucination: a derived total is one that arithmetic
confirms, not one that looks about right. A rule that cannot justify the value
returns False, and the field goes to review.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from fdip.domain.money import (
    CURRENCY_SYNONYMS,
    DEFAULT_CURRENCY,
    close_enough,
    quantise,
    to_decimal,
)

DERIVABLE_PATHS: frozenset[str] = frozenset({"currency", "total", "tax_amount"})
"""The only fields a derivation may rescue. Deliberately short: every addition
is a field that can be accepted without appearing on the page."""


def _currency_is_derivable(value: Any, text: str) -> bool:
    """A currency not printed as a code, but implied by what is printed.

    Two ways it is derivable, and no others:

    * a symbol for that same currency appears -- `RM1,234.50` means MYR, and
      answering `MYR` is reading the document rather than guessing;
    * **no** currency marker appears anywhere, and the answer is the template's
      default. A Malaysian invoice that prints bare amounts is in Ringgit, and
      this is FDIP's documented decision rather than the model's inference.

    If a *different* currency's marker appears, the derivation fails: a document
    showing `S$` and an answer of `MYR` is a real disagreement and belongs in
    review.
    """
    code = str(value or "").strip().upper()
    if not code:
        return False
    upper = text.upper()
    present = {
        iso for symbol, iso in CURRENCY_SYNONYMS.items()
        if symbol in upper and len(symbol) >= 2
    }
    if code in present:
        return True
    return not present and code == DEFAULT_CURRENCY


def _total_is_derivable(value: Any, data: Mapping[str, Any]) -> bool:
    """A total that arithmetic confirms from the subtotal and the tax.

    Magnitudes, because a credit note prints its figures negative or bracketed and
    still balances.
    """
    total = to_decimal(value)
    subtotal = to_decimal(data.get("subtotal"))
    if total is None or subtotal is None:
        return False
    tax = to_decimal(data.get("tax_amount")) or Decimal(0)
    rounding = to_decimal(data.get("rounding_adjustment")) or Decimal(0)
    for candidate in (
        quantise(abs(subtotal) + abs(tax) + rounding),
        quantise(abs(subtotal) + abs(tax)),
    ):
        if close_enough(candidate, abs(total)):
            return True
    return False


def _tax_amount_is_derivable(value: Any, data: Mapping[str, Any]) -> bool:
    """A tax amount that the stated rate confirms against the subtotal."""
    tax = to_decimal(value)
    rate = to_decimal(data.get("tax_rate"))
    subtotal = to_decimal(data.get("subtotal"))
    if tax is None or rate is None or subtotal is None:
        return False
    if rate == 0:
        return tax == 0
    expected = quantise(abs(subtotal) * rate / Decimal(100))
    return close_enough(expected, abs(tax))


def is_derivable(path: str, value: Any, data: Mapping[str, Any],
                 text: str = "") -> bool:
    """Whether FDIP may accept this ungrounded value as `derived`."""
    if path == "currency":
        return _currency_is_derivable(value, text)
    if path == "total":
        return _total_is_derivable(value, data)
    if path == "tax_amount":
        return _tax_amount_is_derivable(value, data)
    return False


__all__ = ["DERIVABLE_PATHS", "is_derivable"]
