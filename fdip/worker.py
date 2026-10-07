"""The worker: one process, polling the `jobs` table.

A table rather than a broker, because 8.1 says not to build Redis or Celery yet
and because the durable run id already gives the property a broker would be
bought for: a job can be picked up twice without being done twice.

`drain_once` exists so tests can run the queue synchronously instead of starting
a thread and sleeping. A test that sleeps is a test that is flaky on a loaded
machine.

Run it with `python -m fdip.worker`.
"""
from __future__ import annotations

import logging
import signal
import time
from types import FrameType
from typing import Any

from sqlalchemy import Engine

from fdip.adapters.db import create_db_engine, transaction
from fdip.adapters.providers import build_model_stack
from fdip.adapters.repository import GlobalRepository, ProjectRepository
from fdip.config import Settings
from fdip.config import settings as load_settings
from fdip.domain.schema_lang import SchemaSpec
from fdip.domain.statuses import JobState
from fdip.domain.templates import flatten
from fdip.observability import (
    JSON_FORMAT,
    configure_logging,
    silence_content_loggers,
)
from fdip.pipeline.runner import JobContext, run_job, spec_from_version

logger = logging.getLogger("fdip.worker")

POLL_SECONDS = 1.0
IDLE_POLL_SECONDS = 2.0


def full_template_spec() -> SchemaSpec:
    """What an interactive upload runs: every template field.

    The whole template rather than a selection, because the user has not chosen a
    schema yet -- the point of the analysis is to show them what is findable so
    they can choose.
    """
    return SchemaSpec(
        name="Invoice", document_type="invoice",
        fields=tuple(spec.path for spec in flatten()),
    )


def _context_for(engine: Engine, settings: Settings, job: Any,
                 fixtures: dict[str, str] | None = None
                 ) -> tuple[JobContext, str] | None:
    with transaction(engine) as connection:
        repo = ProjectRepository(connection, str(job["project_id"]))
        document = repo.document(str(job["document_id"]))
        if document is None:
            # Deleted while queued. Finish the job rather than retrying forever.
            repo.update_job(str(job["id"]), state=JobState.CANCELLED.value,
                            leased_until=None)
            return None
        spent = repo.month_ai_cost()
        if job["schema_id"] and job["schema_version"]:
            stored = repo.schema_version(
                str(job["schema_id"]), int(job["schema_version"])
            )
            if stored is None:
                repo.update_job(str(job["id"]), state=JobState.FAILED.value,
                                error_code="schema_version_not_allowed",
                                leased_until=None)
                return None
            spec = spec_from_version({**dict(stored), "name": "Invoice",
                                      "document_type": "invoice"})
            purpose = "pipeline"
        else:
            spec = full_template_spec()
            purpose = "analysis"
        blob_path = str(document["blob_path"])
        document_hash = str(document["sha256"])

    models = build_model_stack(settings, fixtures=fixtures, already_spent_usd=spent)
    context = JobContext(
        engine=engine, settings=settings, models=models,
        project_id=str(job["project_id"]),
        document_id=str(job["document_id"]), job_id=str(job["id"]),
        blob_path=blob_path, spec=spec, purpose=purpose,
        schema_id=job["schema_id"], schema_version=job["schema_version"],
    )
    return context, document_hash


def drain_once(engine: Engine, settings: Settings,
               fixtures: dict[str, str] | None = None,
               owner: str = "worker") -> dict[str, Any] | None:
    """Claim and run one job. Returns its outcome, or None if the queue is empty.

    Silences the content-bearing loggers on every call rather than only in
    `main`, because a test and an embedded caller reach this function without
    going through it, and that is exactly where a DEBUG root logger would start
    printing invoices.
    """
    silence_content_loggers()
    with transaction(engine) as connection:
        job = GlobalRepository(connection).claim_next_job(
            owner, settings.job_lease_seconds
        )
    if job is None:
        return None

    prepared = _context_for(engine, settings, job, fixtures)
    if prepared is None:
        return {"status": "cancelled", "job_id": str(job["id"])}
    context, document_hash = prepared
    logger.info("job=%s document=%s purpose=%s", context.job_id,
                context.document_id, context.purpose)
    outcome = run_job(context, document_hash)
    return {**outcome, "job_id": context.job_id}


def drain(engine: Engine, settings: Settings, limit: int = 100,
          fixtures: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Run the queue to empty. Tests use this instead of sleeping."""
    out = []
    for _ in range(limit):
        result = drain_once(engine, settings, fixtures)
        if result is None:
            break
        out.append(result)
    return out


class _Stopper:
    """Ctrl-C and SIGTERM finish the current job, then exit.

    Killing a worker mid-job is safe -- that is what the checkpoints are for --
    but finishing cleanly avoids leaving a lease to expire, which would delay the
    next pickup by five minutes.
    """

    def __init__(self) -> None:
        self.stop = False

    def __call__(self, _signum: int, _frame: FrameType | None) -> None:
        logger.info("stopping after the current job")
        self.stop = True


def main() -> int:
    logging.basicConfig(level=logging.INFO, format=JSON_FORMAT)
    configure_logging()
    settings = load_settings()
    settings.ensure_dirs()
    engine = create_db_engine(settings.db_url)
    stopper = _Stopper()
    for name in ("SIGINT", "SIGTERM"):
        handler = getattr(signal, name, None)
        if handler is not None:
            signal.signal(handler, stopper)

    logger.info("worker up mode=%s model=%s thinking=%s ceiling=%.2f",
                settings.provider_mode, settings.model,
                settings.extract_thinking, settings.monthly_ceiling_usd)
    while not stopper.stop:
        try:
            result = drain_once(engine, settings)
        except Exception:
            # The worker must outlive one bad job. The job itself is already
            # marked failed by `run_job`; anything reaching here is a defect in
            # the worker, so it is logged with a traceback and the loop goes on.
            logger.exception("worker loop error")
            time.sleep(IDLE_POLL_SECONDS)
            continue
        time.sleep(POLL_SECONDS if result else IDLE_POLL_SECONDS)
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["drain", "drain_once", "full_template_spec", "main"]
