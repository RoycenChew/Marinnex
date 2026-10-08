"""Display formats: for people, never for the API.

A schema version may say it wants dates as `DD/MM/YYYY` and numbers with a comma
thousands separator. That is a preference about reading, and it stops at the
edge of anything a machine parses.

**The API never applies these.** `/v1/extract`, the contract and every stored
value stay ISO dates and decimal strings, because an integrator parses what
arrives without knowing which locale a colleague picked in a form last week.
Sending `1.234,50` to someone expecting a decimal string is how an invoice
becomes a thousand times too small.

So these functions are used in exactly two places: the CSV and Excel exports a
person opens, and the screen. Both are read by humans who chose the format.

Formatting never raises. A value that does not parse is passed through
unchanged — an export with one oddly formatted cell is a nuisance; an export
that fails because one date was unreadable is a lost afternoon.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

#: What a schema version may ask for. Deliberately a short list: each one has to
#: be unambiguous to a reader, and "MM/DD" alongside "DD/MM" already is not.
DATE_FORMATS: dict[str, str] = {
    "iso": "%Y-%m-%d",
    "dmy_slash": "%d/%m/%Y",
    "dmy_dash": "%d-%m-%Y",
    "dmy_space": "%d %b %Y",
    "mdy_slash": "%m/%d/%Y",
}

#: `plain` is what the API uses. The others are for a spreadsheet.
NUMBER_FORMATS = ("plain", "thousands", "thousands_2dp", "accounting")


def format_date(value: Any, style: str | None) -> Any:
    """An ISO date string in the requested style, or the value untouched."""
    if not style or style == "iso" or not isinstance(value, str):
        return value
    pattern = DATE_FORMATS.get(style)
    if pattern is None:
        return value
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime(pattern)


def format_number(value: Any, style: str | None) -> Any:
    """A decimal string, grouped for reading.

    The value stays a string throughout: parsing to float to add commas would
    reintroduce exactly the error rule 2.9 exists to prevent.
    """
    if not style or style == "plain" or not isinstance(value, str):
        return value
    if style not in NUMBER_FORMATS:
        return value
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        return value

    if style in ("thousands_2dp", "accounting"):
        places = 2
    else:
        # `exponent` is an int for a finite Decimal and a marker string for NaN
        # or infinity, neither of which belongs in an amount column.
        exponent = amount.as_tuple().exponent
        places = -exponent if isinstance(exponent, int) and exponent < 0 else 2
    rendered = f"{amount:,.{places}f}"
    if style == "accounting" and amount < 0:
        # Finance reads a bracket faster than a minus sign, and never misses it.
        rendered = "(%s)" % rendered.lstrip("-")
    return rendered


def apply(value: Any, kind: str, config: dict[str, Any] | None) -> Any:
    """Format one value for a human, given its field's stored config."""
    if not config:
        return value
    if kind == "date":
        return format_date(value, config.get("date_format"))
    if kind in ("decimal", "number", "money"):
        return format_number(value, config.get("number_format"))
    return value
