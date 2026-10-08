"""One job as a durable workflow, and the persistence around it.

`run_id = document_hash + pipeline_version` (3.9). That key is the whole
resumption guarantee: a crash after the extract stage replays the checkpoint
instead of calling the model again, and a pipeline version bump deliberately
invalidates the checkpoints because the stages no longer mean the same thing.

The stage ordering matters for cost, not just for correctness. `extract` is the
expensive step, so everything that can reject a document -- probe, parse, the
type gate -- runs before it. A bank statement sent to an invoice schema costs one
classify call, not two calls and a wasted extraction.

`persist` is marked non-idempotent. It writes rows, and a crash halfway through
it must surface rather than be replayed silently.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Engine
from toolkit.durable_steps import (
    DurableStepsComponent,
    RetryPolicy,
    RunStatus,
    SqliteCheckpointStore,
    Step,
    WorkflowRequest,
)

from fdip import CLASSIFIER_VERSION, PIPELINE_VERSION, PROMPT_VERSION
from fdip.adapters import sandbox
from fdip.adapters.db import transaction
from fdip.adapters.providers import ModelStack
from fdip.adapters.repository import ProjectRepository, now
from fdip.adapters.sandbox import UnsupportedDocument
from fdip.config import Settings
from fdip.domain.schema_lang import (
    CustomField,
    FieldConfig,
    LocaleHints,
    SchemaSpec,
)
from fdip.domain.statuses import POISON_CODES, ErrorCode, JobState, Status
from fdip.domain.templates import TEMPLATE_VERSION
from fdip.pipeline import stages

NO_RETRY = RetryPolicy(max_attempts=1)
"""For the deterministic stages. Retrying a parse that failed on the same bytes
produces the same failure and costs a minute."""


@dataclass
class JobContext:
    """Everything one job needs, resolved before the workflow starts."""

    engine: Engine
    settings: Settings
    models: ModelStack
    project_id: str
    document_id: str
    job_id: str
    blob_path: str
    spec: SchemaSpec
    purpose: str = "analysis"
    schema_id: str | None = None
    schema_version: int | None = None
    expected_type: str = "invoice"
    api_key_id: str | None = None
    fail_after_extract: bool = False
    """Test hook for the crash-resume case. The injected exception has to land
    *after* the extract checkpoint is written, which is the only way to prove the
    model is not called twice."""


def run_id_for(document_hash: str, purpose: str,
               schema_version: int | None = None) -> str:
    parts = [document_hash[:32], PIPELINE_VERSION, purpose]
    if schema_version is not None:
        parts.append(str(schema_version))
    return ":".join(parts)


def _apply_thinking(context: JobContext, ctx: Mapping[str, Any]) -> None:
    """Set the reasoning mode from the route the probe stage chose.

    Per route because the two were measured differently: route A has a
    420-document result behind reasoning on, and option (c) was never actually
    measured at all. See PHASE1_DECISION.md.
    """
    route = str((ctx.get("probe") or {}).get("route") or "A")
    context.models.set_thinking(context.settings.thinking_for_route(route))


class _Injected(RuntimeError):
    """The simulated crash. Not a NonRetryableError, so the job stays resumable."""


def build_steps(context: JobContext) -> list[Step]:
    def probe(_: Mapping[str, Any]) -> dict[str, Any]:
        report = sandbox.probe(context.blob_path, context.settings.max_pages)
        return {
            "mime": report.mime,
            "page_count": report.page_count,
            "route": report.route,
            "pages": report.pages,
            "page_sizes": report.page_sizes,
        }

    def parse(ctx: Mapping[str, Any]) -> dict[str, Any]:
        route = str(ctx["probe"]["route"])
        if sandbox.use_sandbox():
            return sandbox.parse_document(
                context.blob_path, route, context.settings.sandbox_timeout_seconds
            )
        return sandbox.parse_inline(context.blob_path, route)

    def classify(ctx: Mapping[str, Any]) -> dict[str, Any]:
        document = stages.rebuild_document(ctx["parse"])
        _apply_thinking(context, ctx)
        context.models.start_document()
        return stages.classify(document, context.models.llm, context.models.mode)

    def gate(ctx: Mapping[str, Any]) -> dict[str, Any]:
        label = str(ctx["classify"]["label"])
        passed = stages.type_gate(label, context.expected_type)
        # Only the pipeline enforces the gate (3.3 stage 6). An interactive
        # upload runs the full template whatever the document turns out to be,
        # because the user is looking at it and wants to see what was found.
        enforced = context.purpose == "pipeline"
        return {"label": label, "passed": passed or not enforced, "enforced": enforced}

    def extract(ctx: Mapping[str, Any]) -> dict[str, Any]:
        if not ctx["gate"]["passed"]:
            return stages.mismatch_result(
                str(ctx["gate"]["label"]), context.expected_type
            )
        document = stages.rebuild_document(ctx["parse"])
        _apply_thinking(context, ctx)
        context.models.start_document()
        return stages.extract(
            document, context.spec, context.models.llm,
            max_tokens=context.settings.extract_max_tokens,
        )

    def decide(ctx: Mapping[str, Any]) -> dict[str, Any]:
        extracted = ctx["extract"]
        if extracted.get("status") == Status.DOCUMENT_TYPE_MISMATCH.value:
            return dict(extracted)
        if context.fail_after_extract:
            # Raised here rather than inside extract so the extract checkpoint is
            # already written: that is what makes "no second AI call" provable.
            raise _Injected("injected crash after the extract stage")
        # The document text is needed for the currency derivation, which has
        # to see whether a different currency's symbol is on the page.
        return stages.validate_and_decide(
            extracted, context.spec,
            document_text=str(ctx["parse"].get("text", "")),
            allow_ocr_auto_accept=context.settings.scan_auto_accept,
            # Stage 6 now runs for every purpose. The pipeline still refuses
            # outright above; an interactive upload shows what was found and
            # carries `document_type_mismatch` as a reason instead.
            classification=ctx["classify"],
            expected_type=context.expected_type,
        )

    def persist(ctx: Mapping[str, Any]) -> dict[str, Any]:
        return _persist(context, ctx)

    return [
        Step("probe", probe, retry=NO_RETRY),
        Step("parse", parse, retry=NO_RETRY),
        Step("classify", classify, retry=RetryPolicy(max_attempts=3)),
        Step("gate", gate, retry=NO_RETRY),
        Step("extract", extract, retry=RetryPolicy(max_attempts=3)),
        Step("decide", decide, retry=NO_RETRY),
        Step("persist", persist, retry=NO_RETRY, idempotent=False),
    ]


def _persist(context: JobContext, ctx: Mapping[str, Any]) -> dict[str, Any]:
    """Write the extraction, its fields, evidence, validation and decision.

    One transaction, because a document whose fields were written but whose
    decision was not would show as completed with nothing in it.
    """
    probe = ctx["probe"]
    classification = ctx["classify"]
    extracted = ctx["extract"]
    decided = ctx["decide"]
    mismatch = decided.get("status") == Status.DOCUMENT_TYPE_MISMATCH.value

    with transaction(context.engine) as connection:
        repo = ProjectRepository(connection, context.project_id)
        repo.update_document(
            context.document_id,
            page_count=probe["page_count"],
            page_sizes=probe["page_sizes"],
            mime=probe["mime"],
            document_type=classification["label"],
            status=decided["status"],
        )
        if not repo.pages(context.document_id):
            repo.add_pages(context.document_id, probe["pages"])
        repo.add_classification(
            context.document_id,
            label=classification["label"],
            confidence=classification.get("confidence"),
            source=str(classification.get("source", "llm")),
            classifier_version=str(
                classification.get("classifier_version", CLASSIFIER_VERSION)
            ),
        )

        version = repo.next_extraction_version(context.document_id, context.purpose)
        extraction_id = repo.create_extraction(
            document_id=context.document_id,
            version=version,
            schema_id=context.schema_id,
            schema_version=context.schema_version,
            template_version=TEMPLATE_VERSION,
            purpose=context.purpose,
            status=decided["status"],
            document_type=classification["label"],
            currency=decided.get("currency"),
            # The decided data, not the raw extraction: `document_type` is
            # overwritten there with the classifier's answer.
            data=decided.get("data") or extracted.get("data") or {},
            reasons=decided.get("reasons") or [],
            suggested_fields=decided.get("suggested_fields") or [],
            schema_valid=bool(extracted.get("schema_valid", True)),
            truncated=bool(extracted.get("truncated", False)),
            warnings=list(extracted.get("warnings") or []),
            attempts=int(extracted.get("attempts", 1) or 1),
            provider=context.models.provider_name,
            model=context.models.model,
            model_version=str(
                getattr(context.models.llm, "model_version", "") or ""
            )[:120],
            prompt_version=PROMPT_VERSION,
            classifier_version=CLASSIFIER_VERSION,
            pipeline_version=PIPELINE_VERSION,
            document_hash=_document_hash(context, connection),
            decision_rule_version=str(decided.get("rule_version", "")),
            input_tokens=int(extracted.get("input_tokens", 0) or 0),
            output_tokens=int(extracted.get("output_tokens", 0) or 0),
            cost_usd=float(extracted.get("cost_usd", 0.0) or 0.0),
            seconds=float(extracted.get("seconds", 0.0) or 0.0),
        )

        field_reasons = decided.get("field_reasons") or {}
        required = set(context.spec.required_paths())
        upgraded = decided.get("matches") or {}
        for entry in extracted.get("fields", []):
            path = str(entry["path"])
            reasons = list(field_reasons.get(path, []))
            entry = {**entry, "match": upgraded.get(path, entry.get("match"))}
            field_id = repo.add_field(
                extraction_id,
                path=path,
                value_json=entry.get("value"),
                value_text=(
                    None if entry.get("value") is None else str(entry["value"])[:200]
                ),
                raw_text=entry.get("raw_text"),
                status=_field_status(entry, reasons),
                match=str(entry.get("match", "not_checked")),
                required=path in required,
                reasons=reasons,
            )
            repo.add_evidence(field_id, [
                {
                    "page": item["page"],
                    "x0": (item.get("bbox") or [None] * 4)[0],
                    "y0": (item.get("bbox") or [None] * 4)[1],
                    "x1": (item.get("bbox") or [None] * 4)[2],
                    "y1": (item.get("bbox") or [None] * 4)[3],
                    "source": item.get("source", "text_layer"),
                    "ocr_confidence": item.get("ocr_confidence"),
                    "word_count": int(item.get("word_count", 0) or 0),
                }
                for item in entry.get("evidence", [])
            ])

        repo.add_validation(extraction_id, [
            {
                "code": item["code"], "severity": item["severity"],
                "path": item.get("path"), "message": item["message"],
            }
            for item in decided.get("validation", [])
        ])
        repo.add_decision(
            extraction_id,
            status=decided["status"],
            reasons=decided.get("reasons") or [],
            rule_version=str(decided.get("rule_version", "")),
            actor="system",
        )

        for purpose, payload in (("classify", classification), ("extract", extracted)):
            if not payload.get("input_tokens") and not payload.get("output_tokens"):
                continue
            repo.record_provider_call(
                document_id=context.document_id,
                extraction_id=extraction_id,
                api_key_id=context.api_key_id,
                purpose=purpose,
                provider=context.models.provider_name,
                model=context.models.model,
                model_version=str(
                    getattr(context.models.llm, "model_version", "") or ""
                )[:120],
                input_tokens=int(payload.get("input_tokens", 0) or 0),
                output_tokens=int(payload.get("output_tokens", 0) or 0),
                cost_usd=float(payload.get("cost_usd", 0.0) or 0.0),
                cached=bool(payload.get("cached", False)),
                seconds=float(payload.get("seconds", 0.0) or 0.0),
                outcome="ok",
            )

        repo.add_usage(
            documents=1,
            pages=int(probe["page_count"]),
            ai_cost_usd=float(extracted.get("cost_usd", 0.0) or 0.0)
            + float(classification.get("cost_usd", 0.0) or 0.0),
            api_key_id=context.api_key_id,
        )
        repo.update_job(
            context.job_id,
            state=(JobState.NEEDS_REVIEW.value
                   if decided["status"] == Status.NEEDS_REVIEW.value
                   else JobState.COMPLETED.value),
            stage="persist",
            finished_at=now(),
            leased_until=None,
        )
        repo.audit("system", "extracted", "extraction", extraction_id, {
            "document_id": context.document_id,
            "status": decided["status"],
            "reason_count": len(decided.get("reasons") or []),
        })
    return {
        "extraction_id": extraction_id,
        "status": decided["status"],
        "mismatch": mismatch,
        "version": version,
    }


def _document_hash(context: JobContext, connection: Any) -> str:
    row = ProjectRepository(connection, context.project_id).document(
        context.document_id
    )
    return str(row["sha256"]) if row else ""


def _field_status(entry: Mapping[str, Any], reasons: list[str]) -> str:
    from fdip.domain.statuses import GROUNDED_MATCHES, FieldStatus

    if entry.get("value") in (None, ""):
        return FieldStatus.MISSING.value
    if reasons:
        return FieldStatus.NEEDS_REVIEW.value
    if str(entry.get("match", "")) in GROUNDED_MATCHES:
        return FieldStatus.ACCEPTED.value
    return FieldStatus.NEEDS_REVIEW.value


def run_job(context: JobContext, document_hash: str) -> dict[str, Any]:
    """Execute or resume one job. Returns the persist step's result.

    A refused file is recorded as `unsupported` and never retried: the same bytes
    will fail the same way, and the point of the poison class (3.9) is that the
    queue does not spin on it.
    """
    Path(context.settings.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
    store = SqliteCheckpointStore(str(context.settings.checkpoint_path))
    component = DurableStepsComponent(store=store, owner=context.job_id)
    run_id = run_id_for(document_hash, context.purpose, context.schema_version)
    try:
        result = component.execute(WorkflowRequest(
            run_id=run_id,
            steps=build_steps(context),
            lease_seconds=context.settings.job_lease_seconds,
        ))
    except UnsupportedDocument as error:
        _record_failure(context, error.code, error.reason,
                        JobState.UNSUPPORTED.value)
        return {"status": Status.UNSUPPORTED.value, "error_code": error.code}
    finally:
        store.close()

    if result.status is not RunStatus.COMPLETED:
        detail = str(result.error or "")
        code, state = _classify_failure(detail)
        _record_failure(context, code, detail, state)
        return {"status": Status.FAILED.value, "error_code": code,
                "failed_step": result.failed_step}
    return dict(result.context.get("persist") or {})


def _classify_failure(detail: str) -> tuple[str, str]:
    lowered = detail.lower()
    for code in sorted(ErrorCode, key=lambda c: -len(c.value)):
        if code.value in lowered:
            state = (JobState.UNSUPPORTED.value
                     if code.value in POISON_CODES else JobState.FAILED.value)
            return code.value, state
    if "insufficient balance" in lowered or "permanentfailure" in lowered:
        return ErrorCode.PROVIDER_UNAVAILABLE.value, JobState.FAILED.value
    return ErrorCode.INTERNAL.value, JobState.FAILED.value



def _record_failure(context: JobContext, code: str, detail: str, state: str) -> None:
    """The code and the step, never the document. `detail` is an exception
    message, which can quote a value, so it is truncated and kept out of the
    log stream (rule 2.13)."""
    status = (Status.UNSUPPORTED.value if state == JobState.UNSUPPORTED.value
              else Status.FAILED.value)
    with transaction(context.engine) as connection:
        repo = ProjectRepository(connection, context.project_id)
        repo.update_document(context.document_id, status=status, error_code=code)
        repo.update_job(
            context.job_id, state=state, error_code=code,
            error_detail=detail[:500], finished_at=now(), leased_until=None,
        )
        repo.audit("system", "job_failed", "job", context.job_id,
                   {"error_code": code, "state": state})


def spec_from_version(row: Mapping[str, Any]) -> SchemaSpec:
    """A stored schema version back into the spec the pipeline runs.

    Reading the stored field list rather than the current template is what makes
    a version immutable in practice: adding a field to the template must not
    change what a pinned version extracts.
    """
    hints = row["locale_hints"] or {}
    if isinstance(hints, str):
        hints = json.loads(hints)
    fields = row["fields"]
    if isinstance(fields, str):
        fields = json.loads(fields)

    def _json(key: str, fallback: Any) -> Any:
        value = row.get(key) or fallback
        return json.loads(value) if isinstance(value, str) else value

    config = {
        path: FieldConfig(**values)
        for path, values in _json("field_config", {}).items()
    }
    custom = tuple(
        CustomField(
            name=entry["name"], kind=entry["kind"],
            description=entry["description"],
            hints=tuple(entry.get("hints") or ()),
            required=bool(entry.get("required", False)),
        )
        for entry in _json("custom_fields", [])
    )
    return SchemaSpec(
        name=str(row.get("name") or "Invoice"),
        document_type=str(row.get("document_type") or "invoice"),
        fields=tuple(fields),
        locale_hints=LocaleHints(date_order=hints.get("date_order", "DMY")),
        field_config=config,
        custom_fields=custom,
    )


__all__ = [
    "JobContext",
    "build_steps",
    "run_id_for",
    "run_job",
    "spec_from_version",
]
