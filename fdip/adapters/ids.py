"""Prefixed, sortable identifiers.

A prefix on every id (`doc_`, `ext_`, `job_`) is worth the eight bytes: an id in
a log line, a support ticket or a URL says what it points at without a lookup,
and passing a document id where an extraction id belongs becomes visible instead
of returning the wrong row.

The body is time-ordered so that ids cluster by creation in an index, then
random so they cannot be guessed or counted.
"""
from __future__ import annotations

import secrets
import time

ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
"""Crockford base32: no i, l, o or u, so an id read aloud or retyped from a
screenshot does not become a different id."""


def _encode(value: int, width: int) -> str:
    out = []
    for _ in range(width):
        value, remainder = divmod(value, 32)
        out.append(ALPHABET[remainder])
    return "".join(reversed(out))


def new_id(prefix: str) -> str:
    millis = int(time.time() * 1000)
    return "%s_%s%s" % (prefix, _encode(millis, 9), _encode(secrets.randbits(40), 8))


def user_id() -> str:
    return new_id("usr")


def project_id() -> str:
    return new_id("prj")


def document_id() -> str:
    return new_id("doc")


def job_id() -> str:
    return new_id("job")


def extraction_id() -> str:
    return new_id("ext")


def schema_id() -> str:
    return new_id("sch")


def api_key_id() -> str:
    return new_id("key")


def export_id() -> str:
    return new_id("exp")


def test_run_id() -> str:
    return new_id("run")


__all__ = [
    "ALPHABET",
    "api_key_id",
    "document_id",
    "export_id",
    "extraction_id",
    "job_id",
    "new_id",
    "project_id",
    "schema_id",
    "test_run_id",
    "user_id",
]
