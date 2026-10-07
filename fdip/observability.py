"""Logging setup, and the one thing it has to prevent.

Rule 2.13 says never log document text or extracted values. Keeping FDIP's own
log lines to ids and codes is the easy half. The hard half is that
**SQLAlchemy's engine logger emits every statement with its bound parameters**,
and those parameters are the extracted data. So an operator who sets the root
logger to DEBUG to chase a bug turns on full-content logging of every invoice,
without doing anything wrong.

That is not something a convention can prevent, so it is pinned here: the noisy
loggers are set to WARNING and detached from the root handler, which holds even
when the root level is lowered. `tests/test_security.py` asserts it by capturing
the stream at DEBUG and searching for the fixture's actual values.
"""
from __future__ import annotations

import logging

JSON_FORMAT = (
    '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
    '"message":"%(message)s"}'
)

CONTENT_BEARING_LOGGERS: tuple[str, ...] = (
    "sqlalchemy.engine",
    "sqlalchemy.engine.Engine",
    # Emits "cached since ...s ago" lines carrying the full statement.
    "sqlalchemy.pool",
    "sqlalchemy.orm",
    # The HTTP client logs request bodies at DEBUG, which is the prompt.
    "httpcore",
    "httpx",
    "urllib3",
    "openai",
    "pdfminer",
    "PIL",
)
"""Loggers that will print document content or a prompt if they are turned up.

Each one is a real channel, not a precaution: `sqlalchemy.engine` prints bound
parameters, `httpx` prints request bodies, and `pdfminer` prints page text.
"""


def silence_content_loggers() -> None:
    """Hold the content-bearing loggers at WARNING, whatever the root does."""
    for name in CONTENT_BEARING_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        # Detached as well as raised: a handler attached to the root would
        # otherwise still receive anything these emit at WARNING or above, and a
        # SQLAlchemy warning quotes the statement.
        logger.propagate = False
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """FDIP's logger, as structured JSON, with the content channels silenced."""
    logger = logging.getLogger("fdip")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(JSON_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(level)
    silence_content_loggers()
    return logger


__all__ = [
    "CONTENT_BEARING_LOGGERS",
    "JSON_FORMAT",
    "configure_logging",
    "silence_content_loggers",
]
