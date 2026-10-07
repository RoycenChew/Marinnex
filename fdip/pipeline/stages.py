"""The pipeline stages of CLAUDE.md 3.3, as plain functions.

Each stage takes what it needs and returns a JSON-serialisable result, because
the durable runner checkpoints every return value and a checkpoint that cannot
be written is a stage that cannot be resumed. That constraint is why the parsed
document crosses between stages as a dict and is rebuilt into a toolkit
`Document` where it is needed, rather than being passed as an object.

Only two stages call a model: `classify` and `extract`. Everything else is
deterministic, which is the property that makes the silent error rate measurable
at all.
"""
from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from typing import Any

from toolkit.core.models import (
    BBox,
    Block,
    BlockType,
    Document,
    Message,
    Provenance,
    Word,
    WordSource,
)
from toolkit.extraction import (
    ExtractionComponent,
    ExtractionConfig,
    ExtractionRequest,
    extract_json_object,
)

from fdip import CLASSIFIER_VERSION
from fdip.domain.decision import FieldSignal, decide
from fdip.domain.derivation import is_derivable
from fdip.domain.money import normalise_currency
from fdip.domain.schema_lang import SchemaSpec, to_extraction_schema
from fdip.domain.statuses import (
    CLASSIFIER_LABELS,
    GROUNDED_MATCHES,
    DocumentType,
    MatchClass,
    Status,
)
from fdip.domain.templates import field_by_path
from fdip.domain.validators import validate

CLASSIFY_CONFIDENCE_FLOOR = 0.5
"""Below this the classification is not trusted on its own (ASSUMED).

The keyword rule reports 0.6 and the model reports around 0.95, so this separates
"it had a reason" from "it was guessing". A document below the floor is still
extracted and shown; it is just not auto-accepted.
"""

MISMATCH_REASON = "document_type_mismatch"

CLASSIFY_PAGES = 2
CLASSIFY_CHAR_LIMIT = 4000
"""First two pages only (3.3 stage 5). A classifier shown the whole document
costs as much as the extraction and answers no better: the type is on page one."""

_CLASSIFY_SYSTEM = (
    "You label business documents. Answer with one JSON object and nothing else."
)

_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (DocumentType.CREDIT_NOTE.value, ("credit note", "nota kredit", "credit memo")),
    (DocumentType.BANK_STATEMENT.value,
     ("bank statement", "penyata bank", "statement of account", "opening balance",
      "closing balance")),
    (DocumentType.PURCHASE_ORDER.value,
     ("purchase order", "pesanan belian", "p.o. number")),
    (DocumentType.INVOICE.value,
     ("invoice", "invois", "tax invoice", "bill to", "bil kepada")),
    (DocumentType.RECEIPT.value, ("receipt", "resit", "cash sale", "thank you")),
)
"""Mock-mode rule. Ordered most specific first: a credit note also says
"invoice", so whichever matches first wins and invoice must not be first."""


def _bbox_list(box: BBox | None) -> list[float] | None:
    """A `BBox` to the four-number list the API publishes, in the documented
    order: x0, y0, x1, y1, origin top-left, y down."""
    if box is None:
        return None
    return [float(box.x0), float(box.y0), float(box.x1), float(box.y1)]


def _bbox(values: Any) -> BBox:
    """`BBox` is a dataclass with named fields, not a 4-tuple.

    Treating it as a tuple raises `TypeError: not iterable`, which the sandbox
    then reports as `corrupt_file` -- a parse failure that looks like a bad PDF
    and is not.
    """
    x0, y0, x1, y1 = (float(v) for v in values)
    return BBox(x0, y0, x1, y1)


def rebuild_document(parsed: Mapping[str, Any]) -> Document:
    """A parsed payload back into a toolkit `Document`, words and all.

    The words are the reason this round trip exists. Grounding works on words,
    not on block text, so dropping them here would turn every field into
    `not_checked` and the decision rule would send every document to review.
    """
    words = [
        Word(
            text=word["text"],
            page=int(word["page"]),
            bbox=_bbox(word["bbox"]),
            confidence=word.get("confidence"),
            source=WordSource(word.get("source", "text_layer")),
        )
        for word in parsed.get("words", [])
    ]
    page_sizes = {
        int(page): (float(size[0]), float(size[1]))
        for page, size in (parsed.get("page_sizes") or {}).items()
    }
    blocks = _blocks_from_words(words, parsed.get("text", ""))
    return Document(
        doc_id=str(parsed.get("doc_id", "doc")),
        blocks=blocks,
        page_count=int(parsed.get("page_count", len(page_sizes) or 1)),
        words=words,
        page_sizes=page_sizes,
    )


def _blocks_from_words(words: Sequence[Word], fallback_text: str) -> list[Block]:
    """One block per page, built from the words so text and evidence agree.

    Using the parser's own block text instead would let the prompt contain a
    string that the words cannot support, and grounding would then fail on values
    the model read correctly.
    """
    if not words:
        return [Block(text=fallback_text, type=BlockType.PARAGRAPH)] if fallback_text \
            else []
    by_page: dict[int, list[Word]] = {}
    for word in words:
        by_page.setdefault(word.page, []).append(word)
    blocks = []
    for page in sorted(by_page):
        page_words = by_page[page]
        lines: list[list[Word]] = []
        for word in page_words:
            # Same line if the vertical centres overlap: a tolerant test, because
            # OCR baselines wobble and a table row must stay one line.
            if lines and _same_line(lines[-1][-1], word):
                lines[-1].append(word)
            else:
                lines.append([word])
        text = "\n".join(" ".join(w.text for w in line) for line in lines)
        boxes = [w.bbox for w in page_words]
        bbox = BBox(
            min(b.x0 for b in boxes), min(b.y0 for b in boxes),
            max(b.x1 for b in boxes), max(b.y1 for b in boxes),
        )
        blocks.append(Block(
            text=text, type=BlockType.PARAGRAPH,
            provenance=Provenance(page=page, bbox=bbox),
        ))
    return blocks


def _same_line(previous: Word, current: Word) -> bool:
    if previous.page != current.page:
        return False
    height = max(previous.bbox.height, 1.0)
    previous_centre = (previous.bbox.y0 + previous.bbox.y1) / 2
    current_centre = (current.bbox.y0 + current.bbox.y1) / 2
    return abs(previous_centre - current_centre) <= height * 0.6


def classify_keyword(text: str) -> tuple[str, float]:
    """The deterministic classifier used in mock mode and as the fallback."""
    lowered = text.lower()
    for label, needles in _KEYWORDS:
        if any(needle in lowered for needle in needles):
            return label, 0.6
    return DocumentType.UNKNOWN.value, 0.0


def classify(document: Document, llm: Any, mode: str) -> dict[str, Any]:
    """Stage 5. One AI call on the first two pages, or a keyword rule in mock mode.

    A model that answers with a label outside the closed set is treated as
    `unknown`, not as a new label: the type gate compares against a fixed
    vocabulary and an invented one would pass through it unchecked.
    """
    pages = [
        block.text for block in document.content_blocks()
        if block.provenance is None or block.provenance.page <= CLASSIFY_PAGES
    ]
    text = "\n".join(pages)[:CLASSIFY_CHAR_LIMIT]

    if mode == "mock":
        label, confidence = classify_keyword(text)
        return {
            "label": label, "confidence": confidence, "source": "keyword",
            "classifier_version": CLASSIFIER_VERSION,
        }

    prompt = (
        "Classify this document. Answer with "
        '{"document_type": "<label>", "confidence": <0..1>} and nothing else.\n'
        "The label must be exactly one of: " + ", ".join(CLASSIFIER_LABELS) + ".\n"
        'Use "unknown" if the first pages do not make the type clear.\n\n'
        "--- document ---\n" + text
    )
    completion = llm.complete(
        [Message("system", _CLASSIFY_SYSTEM), Message("user", prompt)],
        temperature=0.0, max_tokens=200,
    )
    usage = getattr(completion, "usage", None)
    label = DocumentType.UNKNOWN.value
    confidence = 0.0
    try:
        payload = extract_json_object(str(getattr(completion, "text", "")))
        candidate = str(payload.get("document_type", "")).strip().lower()
        if candidate in CLASSIFIER_LABELS:
            label = candidate
            confidence = float(payload.get("confidence") or 0.0)
    except Exception:
        # An unparseable classification is `unknown`, which routes to review
        # rather than failing the job: the document is still worth extracting.
        pass
    if label == DocumentType.UNKNOWN.value:
        keyword_label, keyword_confidence = classify_keyword(text)
        if keyword_label != DocumentType.UNKNOWN.value:
            # The keywords are weaker evidence, so the confidence stays low and
            # the source records which one answered.
            return {
                "label": keyword_label, "confidence": keyword_confidence,
                "source": "keyword_fallback",
                "classifier_version": CLASSIFIER_VERSION,
                "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(usage, "output_tokens", 0) or 0,
                "cost_usd": float(getattr(usage, "cost_usd", 0.0) or 0.0),
                "cached": bool(getattr(usage, "cached", False)),
            }
    return {
        "label": label, "confidence": confidence, "source": "llm",
        "classifier_version": CLASSIFIER_VERSION,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        "cost_usd": float(getattr(usage, "cost_usd", 0.0) or 0.0),
        "cached": bool(getattr(usage, "cached", False)),
    }


def type_gate(label: str, expected: str) -> bool:
    """Stage 6. True when the document may be extracted against this schema.

    `unknown` passes. A classifier that could not tell is not evidence that the
    document is the wrong type, and refusing on it would reject scans whose first
    page is a cover sheet.
    """
    if label in (expected, DocumentType.UNKNOWN.value):
        return True
    if expected == DocumentType.INVOICE.value:
        return label == DocumentType.CREDIT_NOTE.value
    return False


def extract(document: Document, spec: SchemaSpec, llm: Any,
            max_tokens: int = 16000) -> dict[str, Any]:
    """Stages 7 and 8: the model call, then grounding, both from the toolkit.

    Grounding is not a separate stage here because the toolkit does it inside
    `ExtractionComponent`: the model names a value and deterministic code finds
    it among the document's words. The important consequence is that a value the
    model invented comes back `not_found` rather than accepted.
    """
    started = time.monotonic()
    component = ExtractionComponent(llm)
    result = component.execute(ExtractionRequest(
        schema=to_extraction_schema(spec),
        source=document,
        config=ExtractionConfig(
            max_tokens=max_tokens,
            date_order=spec.locale_hints.date_order,
            coerce=True,
            require_grounding=False,
            # False on purpose: an ungrounded value is a review signal that the
            # decision rule weighs, not a reason to discard the extraction and
            # lose the other thirteen fields.
        ),
    ))
    leaves = list(result.leaves) or list(result.fields)
    return {
        "data": json.loads(json.dumps(result.data, default=str)),
        "attempts": result.attempts,
        # An issue still present after the repair rounds means the output never
        # validated against the schema, which 3.6 treats as not completable.
        "schema_valid": not result.issues,
        "truncated": result.truncated,
        "warnings": list(result.warnings),
        "issues": [
            {"path": issue.path, "message": issue.message}
            for issue in result.issues
        ],
        "fields": [
            {
                "path": leaf.path or leaf.name,
                "value": leaf.value if _jsonable(leaf.value) else str(leaf.value),
                "raw_text": leaf.matched_text or None,
                "match": leaf.match.value,
                "grounded": leaf.grounded,
                "evidence": [
                    {
                        "page": item.page,
                        "bbox": _bbox_list(item.bbox),
                        "source": item.source.value,
                        "ocr_confidence": item.min_confidence,
                        "word_count": len(item.words),
                    }
                    for item in leaf.evidence
                ],
            }
            for leaf in leaves
        ],
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cost_usd": float(result.usage.cost_usd or 0.0),
        "cached": bool(result.usage.cached),
        "seconds": time.monotonic() - started,
        "raw_response_count": len(result.raw_responses),
    }


def _jsonable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_and_decide(extracted: Mapping[str, Any], spec: SchemaSpec,
                        document_text: str = "",
                        allow_ocr_auto_accept: bool = False,
                        classification: Mapping[str, Any] | None = None,
                        expected_type: str | None = None) -> dict[str, Any]:
    """Stages 6, 9 and 10. No model, no network, no randomness.

    Separate from `extract` so a correction can re-run exactly this part: a
    reviewer who fixes a total must get the arithmetic re-checked and the
    decision re-made, without a second AI call. `classification` is therefore
    optional: a correction has no classify step in front of it, and the field is
    left exactly as the original run decided it.
    """
    data = dict(extracted.get("data") or {})
    label = str((classification or {}).get("label") or "")

    # `document_type` is **derived**, not grounded. No invoice prints the word
    # "invoice" as a value -- the Malay sample says INVOIS CUKAI -- so grounding
    # it against page text returned `not_found` and held every such document back
    # over a field the classifier already knew. The classifier is the dedicated
    # task for this, so its answer is the one stored, and the extractor's guess is
    # overwritten rather than reconciled.
    # Only when the schema selected it. `data` is validated against the published
    # contract, whose `additionalProperties` is false, so writing a field the
    # customer did not pin would break their integration.
    selects_document_type = "document_type" in {f.path for f in spec.selected}
    if label and selects_document_type:
        data["document_type"] = label
    required = set(spec.required_paths())
    results = validate(data, sorted(required))

    by_path = {entry["path"]: entry for entry in extracted.get("fields", [])}
    signals = []
    derived_matches: dict[str, str] = {}
    for path in sorted(required | set(by_path)):
        entry = by_path.get(path)
        present = entry is not None and entry.get("value") not in (None, "")
        confidences = [
            item.get("ocr_confidence") for item in (entry or {}).get("evidence", [])
            if item.get("ocr_confidence") is not None
        ]
        match = str((entry or {}).get("match", "not_checked"))
        if present and match == MatchClass.NOT_FOUND.value:
            # 3.4: a value not on the page may still be `derived`, but only where
            # the template allows it and a deterministic rule confirms it. An ISO
            # currency code is almost never printed; a total often is not either.
            spec_field = field_by_path(path)
            if (spec_field is not None and spec_field.grounding == "derivable"
                    and is_derivable(path, (entry or {}).get("value"), data,
                                     document_text)):
                match = MatchClass.DERIVED.value
        signals.append(FieldSignal(
            path=path,
            present=present,
            match=match,
            required=path in required,
            min_ocr_confidence=min(confidences) if confidences else None,
            sources=tuple(sorted({
                str(item.get("source", "")) for item in (entry or {}).get(
                    "evidence", []
                ) if item.get("source")
            })),
        ))
        derived_matches[path] = match

    if label and selects_document_type:
        derived_matches["document_type"] = MatchClass.DERIVED.value
        signals = [
            FieldSignal(
                path=signal.path,
                present=True,
                match=MatchClass.DERIVED.value,
                required=signal.required,
                min_ocr_confidence=None,
                sources=(),
            )
            if signal.path == "document_type" else signal
            for signal in signals
        ]

    # Stage 6, now on every route rather than only the pipeline. A document the
    # classifier calls something else must never reach `completed` under this
    # template; an interactive upload still shows what was extracted, so the
    # mismatch is a reason on a `needs_review` rather than an empty result.
    gate_reasons: list[str] = []
    if label and expected_type and not type_gate(label, expected_type):
        gate_reasons.append(MISMATCH_REASON)
    elif label and expected_type:
        confidence = float((classification or {}).get("confidence") or 0.0)
        # `unknown` passes the pipeline gate -- a classifier that could not tell is
        # not evidence of the wrong type -- but it is exactly the case a person
        # should look at, and so is anything the classifier was unsure of.
        if label == DocumentType.UNKNOWN.value or confidence < CLASSIFY_CONFIDENCE_FLOOR:
            gate_reasons.append(MISMATCH_REASON)

    decision = decide(
        signals,
        validation=results,
        schema_valid=bool(extracted.get("schema_valid", True)),
        truncated=bool(extracted.get("truncated", False)),
        warnings=[],
        allow_ocr_auto_accept=allow_ocr_auto_accept,
        extra_reasons=gate_reasons,
        # The toolkit's own warnings are already reflected in `truncated`;
        # repeating them here would double-count one problem as two reasons.
    )
    return {
        "status": decision.status,
        "data": data,
        "reasons": list(decision.reasons),
        "field_reasons": {k: list(v) for k, v in decision.field_reasons.items()},
        "rule_version": decision.rule_version,
        "validation": [result.as_json() for result in results],
        "currency": normalise_currency(str(data.get("currency") or "")) or None,
        "suggested_fields": sorted(
            signal.path for signal in signals
            if signal.present and signal.match in GROUNDED_MATCHES
        ),
        # The stage records any match it upgraded, so `persist` writes the class
        # the decision was actually made on rather than the raw one.
        "matches": derived_matches,
    }


def mismatch_result(label: str, expected: str) -> dict[str, Any]:
    """What the gate returns instead of an extraction. No data (3.7)."""
    return {
        "status": Status.DOCUMENT_TYPE_MISMATCH.value,
        "reasons": ["document_type_mismatch:%s_expected_%s" % (label, expected)],
        "document_type": label,
        "data": {},
        "fields": [],
        "validation": [],
    }


__all__ = [
    "CLASSIFY_CHAR_LIMIT",
    "CLASSIFY_PAGES",
    "classify",
    "classify_keyword",
    "extract",
    "mismatch_result",
    "rebuild_document",
    "type_gate",
    "validate_and_decide",
]
