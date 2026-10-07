"""Reading extractions, correcting them, and approving or rejecting them.

A correction does not update a row. It writes version n+1, re-runs validation and
the decision rule on the corrected data, and records what changed (3.3 stage 11).
That is what makes the audit trail real: the original extraction stays exactly as
the model produced it, which is the only version that can ever be used to measure
the silent error rate.

A correction costs **no AI call**. The reviewer supplies the value; validation and
the decision rule are deterministic. A correction that re-extracted would both
cost money and risk overwriting the human's answer.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from fdip import PIPELINE_VERSION
from fdip.adapters.repository import ProjectRepository
from fdip.api import problems, views
from fdip.api.deps import (
    Principal,
    any_principal,
    repository,
    session_principal,
)
from fdip.api.schemas import DecisionResult, Extraction
from fdip.domain.decision import FieldSignal, decide
from fdip.domain.money import normalise_currency
from fdip.domain.schema_lang import LocaleHints, SchemaSpec
from fdip.domain.statuses import ErrorCode, FieldStatus, MatchClass, Status
from fdip.domain.templates import DEFAULT_SELECTED_FIELDS, flatten
from fdip.domain.validators import validate

router = APIRouter(tags=["extractions"])


class Change(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    value: Any = None


class CorrectionRequest(BaseModel):
    changes: list[Change] = Field(min_length=1)
    reason: str | None = None


class DecisionRequest(BaseModel):
    action: str
    reason: str | None = None


def _spec_for(extraction: Any, repo: ProjectRepository) -> SchemaSpec:
    """The spec the extraction was produced with, or the full template.

    An analysis run has no schema version, so it falls back to every template
    field: that is what it actually ran against.
    """
    schema_id = extraction["schema_id"]
    version = extraction["schema_version"]
    if schema_id and version:
        stored = repo.schema_version(str(schema_id), int(version))
        if stored is not None:
            hints = stored["locale_hints"] or {}
            return SchemaSpec(
                name="Invoice", document_type="invoice",
                fields=tuple(stored["fields"] or DEFAULT_SELECTED_FIELDS),
                locale_hints=LocaleHints(
                    date_order=hints.get("date_order", "DMY")
                ),
            )
    return SchemaSpec(
        name="Invoice", document_type="invoice",
        fields=tuple(spec.path for spec in flatten()),
    )


def _apply(data: dict[str, Any], path: str, value: Any) -> None:
    """Write one value at a `line_items[2].amount`-style path.

    Hand-rolled rather than a library: the grammar is two forms, and a general
    JSONPath implementation would accept expressions this API does not support
    and then behave in ways the contract does not describe.
    """
    if "[" not in path:
        data[path] = value
        return
    head, _, rest = path.partition("[")
    index_text, _, tail = rest.partition("]")
    try:
        index = int(index_text)
    except ValueError as error:
        raise problems.invalid("%s is not a valid path" % path) from error
    rows = data.get(head)
    if not isinstance(rows, list) or index >= len(rows) or index < 0:
        raise problems.invalid("%s does not exist in this extraction" % path)
    column = tail.lstrip(".")
    if not column:
        rows[index] = value
        return
    if not isinstance(rows[index], dict):
        raise problems.invalid("%s is not an object" % path)
    rows[index][column] = value


@router.get("/extractions/{extraction_id}", response_model=Extraction)
def get_extraction(
    extraction_id: str,
    _: Annotated[Principal, Depends(any_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    extraction = repo.extraction(extraction_id)
    if extraction is None:
        raise problems.not_found("extraction")
    return views.extraction_view(repo, extraction)


@router.get("/documents/{document_id}/extractions", response_model=list[Extraction])
def list_extractions(
    document_id: str,
    _: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> list[dict[str, Any]]:
    if repo.document(document_id) is None:
        raise problems.not_found("document")
    return [
        views.extraction_view(repo, row)
        for row in repo.extractions_for_document(document_id)
    ]


@router.post(
    "/extractions/{extraction_id}/corrections",
    status_code=201,
    response_model=Extraction,
)
def correct(
    extraction_id: str,
    payload: CorrectionRequest,
    principal: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    previous = repo.extraction(extraction_id)
    if previous is None:
        raise problems.not_found("extraction")
    if str(previous["status"]) == Status.REJECTED.value:
        raise problems.Problem(
            409, ErrorCode.ALREADY_DECIDED.value,
            "a rejected extraction cannot be corrected; re-upload the document",
        )

    spec = _spec_for(previous, repo)
    data = dict(previous["data"] or {})
    corrected_paths = []
    for change in payload.changes:
        _apply(data, change.path, change.value)
        corrected_paths.append(change.path)

    existing = {str(row["path"]): row for row in repo.fields(extraction_id)}
    required = set(spec.required_paths())
    results = validate(data, sorted(required))

    signals = []
    for path in sorted(set(existing) | required | set(corrected_paths)):
        if path in corrected_paths:
            # A human-supplied value is `derived`, not `exact`: it is correct by
            # authority rather than by being found on the page, and calling it
            # `exact` would make a correction indistinguishable from a grounded
            # read in every later measurement.
            signals.append(FieldSignal(path, True, MatchClass.DERIVED.value,
                                       path in required))
            continue
        row = existing.get(path)
        signals.append(FieldSignal(
            path=path,
            present=row is not None and row["value_json"] not in (None, ""),
            match=str(row["match"]) if row is not None else "not_checked",
            required=path in required,
        ))
    decision = decide(signals, validation=results,
                      schema_valid=bool(previous["schema_valid"]),
                      truncated=bool(previous["truncated"]))

    version = repo.next_extraction_version(
        str(previous["document_id"]), str(previous["purpose"])
    )
    new_id = repo.create_extraction(
        document_id=str(previous["document_id"]),
        version=version,
        schema_id=previous["schema_id"],
        schema_version=previous["schema_version"],
        template_version=int(previous["template_version"]),
        purpose=str(previous["purpose"]),
        status=decision.status,
        document_type=previous["document_type"],
        currency=normalise_currency(str(data.get("currency") or ""))
        or previous["currency"],
        data=data,
        reasons=list(decision.reasons),
        suggested_fields=list(previous["suggested_fields"] or []),
        schema_valid=bool(previous["schema_valid"]),
        truncated=bool(previous["truncated"]),
        warnings=list(previous["warnings"] or []),
        attempts=int(previous["attempts"]),
        provider=str(previous["provider"]),
        model=str(previous["model"]),
        model_version=str(previous["model_version"]),
        prompt_version=str(previous["prompt_version"]),
        classifier_version=str(previous["classifier_version"]),
        pipeline_version=PIPELINE_VERSION,
        document_hash=str(previous["document_hash"]),
        decision_rule_version=decision.rule_version,
        # Zero: a correction makes no model call. Carrying the previous run's
        # tokens forward would double-count the spend on every correction.
        input_tokens=0, output_tokens=0, cost_usd=0.0, seconds=0.0,
    )

    evidence = repo.evidence_for([str(row["id"]) for row in existing.values()])
    for path, row in existing.items():
        if path in corrected_paths:
            continue
        new_field = repo.add_field(
            new_id, path=path, value_json=row["value_json"],
            value_text=row["value_text"], raw_text=row["raw_text"],
            status=str(row["status"]), match=str(row["match"]),
            required=path in required,
            reasons=list(decision.field_reasons.get(path, [])),
        )
        repo.add_evidence(new_field, [
            {
                "page": item["page"], "x0": item["x0"], "y0": item["y0"],
                "x1": item["x1"], "y1": item["y1"], "source": item["source"],
                "ocr_confidence": item["ocr_confidence"],
                "word_count": item["word_count"],
            }
            for item in evidence.get(str(row["id"]), [])
        ])
    for change in payload.changes:
        repo.add_field(
            new_id, path=change.path, value_json=change.value,
            value_text=None if change.value is None else str(change.value)[:200],
            raw_text=None, status=FieldStatus.CORRECTED.value,
            match=MatchClass.DERIVED.value, required=change.path in required,
            reasons=[],
        )

    repo.add_validation(new_id, [result.as_json() for result in results])
    repo.add_decision(new_id, status=decision.status,
                      reasons=list(decision.reasons),
                      rule_version=decision.rule_version,
                      actor=principal.actor, reason_text=payload.reason)
    repo.add_correction(extraction_id, new_extraction_id=new_id,
                        user_id=principal.user_id,
                        changes=[c.model_dump() for c in payload.changes],
                        reason=payload.reason)
    repo.update_document(str(previous["document_id"]), status=decision.status)
    # Paths only, never values: a corrected value is document content (2.13).
    repo.audit(principal.actor, "corrected", "extraction", new_id,
               {"from": extraction_id, "paths": corrected_paths,
                "status": decision.status})

    created = repo.extraction(new_id)
    return views.extraction_view(repo, created)  # type: ignore[arg-type]


@router.post("/extractions/{extraction_id}/decision", response_model=DecisionResult)
def decide_extraction(
    extraction_id: str,
    payload: DecisionRequest,
    principal: Annotated[Principal, Depends(session_principal)],
    repo: ProjectRepository = Depends(repository),
) -> dict[str, Any]:
    """A reviewer's approve or reject. The final word on this extraction."""
    if payload.action not in ("approve", "reject"):
        raise problems.invalid('action must be "approve" or "reject"')
    extraction = repo.extraction(extraction_id)
    if extraction is None:
        raise problems.not_found("extraction")
    if str(extraction["status"]) == Status.REJECTED.value:
        raise problems.Problem(
            409, ErrorCode.ALREADY_DECIDED.value,
            "this extraction has already been rejected",
        )
    if payload.action == "reject" and not payload.reason:
        # A rejection without a reason tells the next reviewer nothing and makes
        # the rejection rate unanalysable.
        raise problems.invalid("a reason is required when rejecting")

    status = (Status.COMPLETED.value if payload.action == "approve"
              else Status.REJECTED.value)
    repo.update_extraction(extraction_id, status=status)
    repo.update_document(str(extraction["document_id"]), status=status)
    repo.add_decision(extraction_id, status=status,
                      reasons=["reviewer_" + payload.action],
                      rule_version="manual", actor=principal.actor,
                      reason_text=payload.reason)
    repo.audit(principal.actor, payload.action + "d", "extraction", extraction_id,
               {"status": status})
    return {"extraction_id": extraction_id, "status": status}


__all__ = ["router"]
