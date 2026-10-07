"""FDIP: Financial Document Intelligent Processing.

`PIPELINE_VERSION` is part of every durable run id and every extraction's
reproducibility record, so changing a stage's behaviour means bumping it: a
resumed job must not replay a checkpoint written by different code.
"""
from __future__ import annotations

__version__ = "0.1.0"
PIPELINE_VERSION = "2026.10.1"
PROMPT_VERSION = "verbatim-cell-1"
CLASSIFIER_VERSION = "keyword-or-llm-1"

__all__ = [
    "__version__",
    "PIPELINE_VERSION",
    "PROMPT_VERSION",
    "CLASSIFIER_VERSION",
]
