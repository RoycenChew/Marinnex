"""The job pipeline: CLAUDE.md 3.3 stages, composed as a durable workflow."""
from fdip.pipeline.runner import JobContext, run_id_for, run_job, spec_from_version
from fdip.pipeline.stages import (
    classify,
    classify_keyword,
    extract,
    rebuild_document,
    type_gate,
    validate_and_decide,
)

__all__ = [
    "JobContext",
    "classify",
    "classify_keyword",
    "extract",
    "rebuild_document",
    "run_id_for",
    "run_job",
    "spec_from_version",
    "type_gate",
    "validate_and_decide",
]
