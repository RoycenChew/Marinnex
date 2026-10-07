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

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from fdip.domain.money import (
    CURRENCY_SYNONYMS,
    close_enough,
    quantise,
    to_decimal,
)

DERIVABLE_PATHS: frozenset[str] = frozenset({"currency", "total", "tax_amount"})
"""The only three fields a derivation may rescue, and what justifies each:

* **`currency`** -- a marker for that same currency is printed on the page (`RM`,
  `MYR`, `S$`, `EUR`). Never a locale default; see `_currency_is_derivable`.
* **`total`** -- equals subtotal + tax (+ rounding) within two sen, in magnitudes
  so a credit note balances.
* **`tax_amount`** -- equals the stated rate applied to the subtotal.

Deliberately short. Every addition is a field that can be accepted without
appearing on the page, and the template must also mark it `grounding="derivable"`
for any of this to apply.
"""


def _marker_pattern() -> re.Pattern[str]:
    """Currency markers, matched on a letter boundary rather than as substrings.

    A plain `in` test is wrong in a way that is easy to miss and was caught by a
    test: **`TERMS` contains `RM`**, so "Terms: 30 days nett" counted as evidence
    of Ringgit on a document with no currency printed anywhere. `WARM`, `FORM` and
    `PERMIT` do the same.

    The boundary is "not a letter" rather than ``, because `RM1,984.00` has no
    word break between the marker and the digits and is the commonest way a
    Malaysian invoice prints an amount. Longest first, so `MYR` wins over a
    hypothetical `MY`.
    """
    symbols = sorted(
        (s for s in CURRENCY_SYNONYMS if len(s) >= 2), key=len, reverse=True
    )
    body = "|".join(re.escape(symbol) for symbol in symbols)
    return re.compile(r"(?<![A-Z])(?:%s)(?![A-Z])" % body)


_MARKERS = _marker_pattern()


def currencies_printed(text: str) -> set[str]:
    """Every ISO code evidenced by a marker on the page.

    Two characters or more, so a bare `$` does not make every page USD.
    """
    return {
        CURRENCY_SYNONYMS[match] for match in _MARKERS.findall(text.upper())
        if match in CURRENCY_SYNONYMS
    }


def _currency_is_derivable(value: Any, text: str) -> bool:
    """A currency not printed as an ISO code, but evidenced by what *is* printed.

    One way only: a marker for that same currency appears on the page. `RM1,234.50`
    means MYR, and answering `MYR` is reading the document rather than guessing.

    **There is no default.** An earlier version accepted MYR when no marker
    appeared at all, on the reasoning that a Malaysian invoice with bare amounts is
    in Ringgit. That looked harmless on a Malaysian corpus and is not: a document
    priced in Singapore dollars whose `S$` the OCR dropped would have been accepted
    as Ringgit, silently, at roughly 3.2x the real amount. A currency nobody
    printed now goes to a human.

    A *different* currency's marker fails for the same reason: a page showing `S$`
    and an answer of `MYR` is a real disagreement, not a gap.
    """
    code = str(value or "").strip().upper()
    if not code:
        return False
    present = currencies_printed(text)
    return code in present


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


__all__ = ["DERIVABLE_PATHS", "currencies_printed", "is_derivable"]
