"""Money as a Decimal plus a currency, never a float (rule 2.2).

The parsing itself is the toolkit's `normalise_number_text`, which already knows
that the rightmost separator is the decimal point, that brackets mean negative
and that `RM(4,094.28)` is a real way to write minus four thousand. This module
adds only what is financial and therefore cannot live in the toolkit: a currency
beside the amount, two-place quantisation, and the comparison tolerance.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from toolkit.extraction import parse_decimal

CENTS = Decimal("0.01")
TOLERANCE = Decimal("0.02")
"""Two sen. Wide enough for per-line rounding on a long invoice, narrow enough
that a transposed digit still fails."""

DEFAULT_CURRENCY = "MYR"

CURRENCY_SYNONYMS: dict[str, str] = {
    "RM": "MYR", "MYR": "MYR", "RINGGIT": "MYR",
    "S$": "SGD", "SGD": "SGD",
    "US$": "USD", "USD": "USD", "$": "USD",
    "EUR": "EUR", "GBP": "GBP", "CNY": "CNY", "RMB": "CNY",
    "THB": "THB", "IDR": "IDR",
}


def to_decimal(value: Any) -> Decimal | None:
    """Any printed amount to a Decimal, or None if it is not a number.

    None rather than an exception: a value the model returned as prose is a
    review signal, not a crash.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # Reached only through a JSON number we did not ask for; go via str so
        # the float's binary tail does not become part of the amount.
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return None
    try:
        return parse_decimal(text)
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def quantise(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def normalise_currency(text: str | None) -> str | None:
    if not text:
        return None
    key = text.strip().upper()
    return CURRENCY_SYNONYMS.get(key, key if len(key) == 3 else None)


def close_enough(left: Decimal | None, right: Decimal | None,
                 tolerance: Decimal = TOLERANCE) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = DEFAULT_CURRENCY

    def as_json(self) -> dict[str, str]:
        """A string amount, because a JSON number would be a float downstream."""
        return {"amount": str(quantise(self.amount)), "currency": self.currency}

    @staticmethod
    def parse(value: Any, currency: str | None = None) -> Money | None:
        amount = to_decimal(value)
        if amount is None:
            return None
        return Money(amount, normalise_currency(currency) or DEFAULT_CURRENCY)


__all__ = [
    "CENTS",
    "CURRENCY_SYNONYMS",
    "DEFAULT_CURRENCY",
    "Money",
    "TOLERANCE",
    "close_enough",
    "normalise_currency",
    "quantise",
    "to_decimal",
]
