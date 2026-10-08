"""B5.1: the whole interactive path, in mock mode.

Upload, the worker processes it, the analysis has grounded fields with boxes, a
correction creates a new version, approve gives `completed`, and both exports
work. One test rather than six, because the thing worth proving is that the
stages connect -- each stage is tested on its own elsewhere.
"""
from __future__ import annotations

from typing import Any


def test_upload_to_export(client: Any, upload: Any, run_worker: Any) -> None:
    engine = client.app.state.fdip.engine
    document_id, job_id = upload("invoice_digital")

    # Before the worker runs, the document is processing and the analysis says so
    # rather than 404ing: the UI polls this endpoint from the moment of upload.
    pending = client.get("/v1/documents/%s/analysis" % document_id)
    assert pending.status_code == 200
    assert pending.json()["status"] == "processing"

    outcomes = run_worker(engine)
    assert len(outcomes) == 1, outcomes
    assert outcomes[0]["status"] in ("completed", "needs_review"), outcomes

    document = client.get("/v1/documents/%s" % document_id).json()
    assert document["document_type"] == "invoice"
    assert document["pages"] == 1
    assert document["page_sizes"]["1"] == [595.0, 842.0]
    assert document["job"]["state"] in ("completed", "needs_review")

    analysis = client.get("/v1/documents/%s/analysis" % document_id).json()
    assert analysis["data"]["invoice_number"] == "INV-2026-0417"
    assert analysis["data"]["total"] == "2142.72"
    assert len(analysis["data"]["line_items"]) == 3

    # Grounding: the value was found among the document's own words, with a box.
    entry = analysis["fields"]["invoice_number"]
    assert entry["match"] in ("exact", "normalized")
    assert entry["status"] == "accepted"
    assert entry["evidence"], "a grounded field must carry evidence"
    box = entry["evidence"][0]
    assert box["page"] == 1
    assert box["source"] == "text_layer"
    assert len(box["bbox"]) == 4
    assert box["bbox"][2] > box["bbox"][0] and box["bbox"][3] > box["bbox"][1]

    # Line-item cells are addressable individually, which is what the UI needs to
    # highlight one cell of a table.
    assert "line_items[0].amount" in analysis["fields"]
    assert analysis["suggested_fields"], "grounded paths should be suggested"
    assert "invoice_number" in analysis["suggested_fields"]

    extraction_id = analysis["extraction_id"]
    assert analysis["version"] == 1

    # A correction writes a new version and leaves the original untouched.
    corrected = client.post(
        "/v1/extractions/%s/corrections" % extraction_id,
        json={"changes": [{"path": "buyer_name", "value": "Harapan Engineering"}],
              "reason": "trailing Sdn Bhd dropped by the buyer"},
    )
    assert corrected.status_code == 201, corrected.text
    new = corrected.json()
    assert new["version"] == 2
    assert new["extraction_id"] != extraction_id
    assert new["data"]["buyer_name"] == "Harapan Engineering"
    assert new["fields"]["buyer_name"]["status"] == "corrected"
    assert new["fields"]["buyer_name"]["match"] == "derived"

    original = client.get("/v1/extractions/%s" % extraction_id).json()
    assert original["data"]["buyer_name"] == "Harapan Engineering Sdn Bhd", (
        "the original extraction must be immutable"
    )

    versions = client.get("/v1/documents/%s/extractions" % document_id).json()
    assert [row["version"] for row in versions] == [1, 2]

    approved = client.post(
        "/v1/extractions/%s/decision" % new["extraction_id"],
        json={"action": "approve"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "completed"
    assert client.get("/v1/documents/%s" % document_id).json()["status"] == "completed"

    for fmt, magic in (("csv", b"\xef\xbb\xbf"), ("xlsx", b"PK")):
        created = client.post("/v1/exports",
                              json={"format": fmt, "document_ids": [document_id]})
        assert created.status_code == 201, created.text
        assert created.json()["row_count"] == 1
        export_id = created.json()["export_id"]
        downloaded = client.get("/v1/exports/%s" % export_id)
        assert downloaded.status_code == 200
        assert downloaded.content.startswith(magic)
        if fmt == "csv":
            text = downloaded.content.decode("utf-8-sig")
            assert "INV-2026-0417" in text
            assert "Hex bolt stainless M8 HBS-1000" in text, (
                "the part code must survive the export verbatim"
            )

    assert job_id
    job = client.get("/v1/jobs/%s" % job_id).json()
    assert job["state"] in ("completed", "needs_review")

    usage = client.get("/v1/usage").json()
    assert usage["documents"] == 1
    assert usage["pages"] == 1


def test_a_page_image_renders_with_the_scaling_the_ui_needs(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """The bbox contract: points in, 150-DPI pixels out, and the ratio stated."""
    document_id, _ = upload()
    run_worker(client.app.state.fdip.engine)
    response = client.get("/v1/documents/%s/pages/1/image" % document_id)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-page-dpi"] == "150"

    import io

    from PIL import Image

    image = Image.open(io.BytesIO(response.content))
    page_width = client.get("/v1/documents/%s" % document_id).json()["page_sizes"]["1"][0]
    # 150/72 = 2.0833..., so a 595-point page is about 1240 pixels wide. The UI
    # multiplies every bbox by image_width / page_width.
    assert abs(image.width / page_width - 150 / 72) < 0.01


def test_a_malay_invoice_and_a_credit_note_both_run(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """B5.8: the Malay-label and credit-note fixtures, in mock mode only."""
    engine = client.app.state.fdip.engine
    malay, _ = upload("invoice_malay")
    credit, _ = upload("credit_note")
    run_worker(engine)

    malay_body = client.get("/v1/documents/%s/analysis" % malay).json()
    assert malay_body["data"]["invoice_number"] == "INV-MY-0092"
    assert malay_body["data"]["total"] == "1049.40"
    assert malay_body["fields"]["invoice_number"]["match"] in ("exact", "normalized")

    credit_body = client.get("/v1/documents/%s/analysis" % credit).json()
    assert credit_body["document_type"] == "credit_note"
    # Negative amounts, and the arithmetic still has to balance in magnitudes.
    assert credit_body["data"]["total"] == "-135.00"
    codes = {row["code"] for row in credit_body["validation"]}
    assert "subtotal_plus_tax_ne_total" not in codes, (
        "a credit note balances in magnitudes: 125 + 10 = 135"
    )


def test_two_tax_lines_are_kept_as_a_list(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """A document with two rates is modelled as a list, not flattened (3.4)."""
    document_id, _ = upload("invoice_two_tax_lines")
    run_worker(client.app.state.fdip.engine)
    body = client.get("/v1/documents/%s/analysis" % document_id).json()
    rates = [line["rate"] for line in body["data"]["tax_lines"]]
    assert rates == ["6", "10"]
    codes = {row["code"] for row in body["validation"]}
    assert "tax_lines_ne_tax_amount" not in codes, "54 + 180 = 234"


def test_a_seeded_arithmetic_error_routes_to_review_and_is_not_accepted(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """The case the acceptance predicate exists for.

    Every field is grounded -- 999.00 really is printed on the page -- so grounding
    alone would accept it. Only the validators catch it, which is why 3.6 requires
    them and why this document must not be `completed`.
    """
    document_id, _ = upload("invoice_wrong_total")
    run_worker(client.app.state.fdip.engine)
    body = client.get("/v1/documents/%s/analysis" % document_id).json()

    assert body["fields"]["total"]["match"] in ("exact", "normalized"), (
        "the wrong total is genuinely on the page, so it grounds"
    )
    assert body["status"] == "needs_review"
    codes = {row["code"] for row in body["validation"]}
    assert "subtotal_plus_tax_ne_total" in codes
    assert any(r.startswith("validation:") for r in body["reasons"])


def test_a_hallucinated_optional_value_routes_to_review(
    client: Any, pdf: Any, settings: Any
) -> None:
    """A value not on the page holds the document back, required or not.

    The model is scripted to return a `po_number` that the document does not
    contain. Every other field is correct, so without this rule the document would
    be `completed` carrying one invented value -- which is precisely a silent
    error, and the metric Phase 1 exists to measure.
    """
    import json

    from fdip.adapters.mock_answers import SAMPLE_ANSWERS
    from fdip.worker import drain

    answer = dict(SAMPLE_ANSWERS["INV-2026-0417"])
    answer["po_number"] = "PO-99999-NOT-ON-THIS-PAGE"

    def handler(messages: Any) -> str:
        text = "\n".join(str(getattr(m, "content", "")) for m in messages)
        if "classify this document" in text.lower():
            return json.dumps({"document_type": "invoice", "confidence": 0.95})
        return json.dumps(answer)

    path = pdf("invoice_digital")
    with path.open("rb") as handle:
        response = client.post(
            "/v1/documents",
            files={"file": (path.name, handle, "application/pdf")},
        )
    document_id = response.json()["document_id"]

    import fdip.worker as worker_module
    from fdip.adapters import providers

    original = providers.build_model_stack

    def patched(*args: Any, **kwargs: Any) -> Any:
        kwargs["handler"] = handler
        return original(*args, **kwargs)

    providers.build_model_stack = patched
    worker_module.build_model_stack = patched
    try:
        drain(client.app.state.fdip.engine, settings)
    finally:
        providers.build_model_stack = original
        worker_module.build_model_stack = original

    body = client.get("/v1/documents/%s/analysis" % document_id).json()
    assert body["data"]["po_number"] == "PO-99999-NOT-ON-THIS-PAGE"
    assert body["fields"]["po_number"]["match"] == "not_found"
    assert body["fields"]["po_number"]["status"] == "needs_review"
    assert body["fields"]["po_number"]["reasons"] == ["value_not_found_on_page"]
    assert body["status"] == "needs_review", body["reasons"]
    assert "field_not_grounded:po_number" in body["reasons"]
    # The honest grounded fields are still accepted, so a reviewer sees one
    # problem rather than a wall of them.
    assert body["fields"]["invoice_number"]["status"] == "accepted"


def test_a_document_with_no_printed_currency_routes_to_review(
    client: Any, pdf: Any, settings: Any, tmp_path: Any
) -> None:
    """Currency may only be derived from a marker on the page.

    The MYR default is gone: a document priced in another currency whose symbol
    OCR dropped would have been accepted as Ringgit, silently.
    """
    import json
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from fixtures import BY_NAME, Variant, write_pdf

    from fdip.adapters.mock_answers import SAMPLE_ANSWERS
    from fdip.worker import drain

    # The same invoice with every RM stripped: nothing currency-like is printed.
    original_variant = BY_NAME["invoice_digital"]
    bare = Variant(
        name="bare",
        lines=tuple(line.replace("RM", "") for line in original_variant.lines),
        data=original_variant.data,
    )
    path = write_pdf(tmp_path / "bare.pdf", bare)
    assert "RM" not in "\n".join(bare.lines)

    def handler(messages: Any) -> str:
        text = "\n".join(str(getattr(m, "content", "")) for m in messages)
        if "classify this document" in text.lower():
            return json.dumps({"document_type": "invoice", "confidence": 0.95})
        return json.dumps(SAMPLE_ANSWERS["INV-2026-0417"])

    with path.open("rb") as handle:
        response = client.post(
            "/v1/documents",
            files={"file": ("bare.pdf", handle, "application/pdf")},
        )
    document_id = response.json()["document_id"]

    import fdip.worker as worker_module
    from fdip.adapters import providers

    original = providers.build_model_stack

    def patched(*args: Any, **kwargs: Any) -> Any:
        kwargs["handler"] = handler
        return original(*args, **kwargs)

    providers.build_model_stack = patched
    worker_module.build_model_stack = patched
    try:
        drain(client.app.state.fdip.engine, settings)
    finally:
        providers.build_model_stack = original
        worker_module.build_model_stack = original

    body = client.get("/v1/documents/%s/analysis" % document_id).json()
    assert body["fields"]["currency"]["match"] == "not_found"
    assert body["status"] == "needs_review", body["reasons"]
    assert "field_not_grounded:currency" in body["reasons"]


def test_a_reviewer_can_record_that_a_field_was_checked(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """A field a reviewer has looked at and accepted must survive a reload.

    The workspace counts how many fields are waiting and walks them one at a
    time. Before this the count lived in browser state, so a refresh halfway
    through a forty-line invoice lost the reviewer's place. It is also an audit
    fact worth keeping: "a person looked at this value and accepted it" is
    exactly what a sampled audit of the silent error rate needs.
    """
    document_id, _ = upload("invoice_digital")
    run_worker(client.app.state.fdip.engine)
    analysis = client.get("/v1/documents/%s/analysis" % document_id).json()
    extraction_id = analysis["extraction_id"]

    assert client.get(
        "/v1/extractions/%s/field-reviews" % extraction_id
    ).json()["checked_paths"] == []

    first = client.post(
        "/v1/extractions/%s/field-reviews" % extraction_id,
        json={"path": "total"},
    )
    assert first.status_code == 200
    assert first.json()["checked_paths"] == ["total"]

    # Recording the same path twice is not an error and does not duplicate it.
    client.post("/v1/extractions/%s/field-reviews" % extraction_id,
                json={"path": "total"})
    client.post("/v1/extractions/%s/field-reviews" % extraction_id,
                json={"path": "subtotal"})
    assert client.get(
        "/v1/extractions/%s/field-reviews" % extraction_id
    ).json()["checked_paths"] == ["subtotal", "total"]

    # Unchecking is how a reviewer takes a second look.
    client.request(
        "DELETE", "/v1/extractions/%s/field-reviews" % extraction_id,
        json={"path": "total"},
    )
    assert client.get(
        "/v1/extractions/%s/field-reviews" % extraction_id
    ).json()["checked_paths"] == ["subtotal"]

    # A path that is not in this extraction is refused, so a typo in an
    # integration does not quietly accumulate meaningless rows. 422 is this
    # API's code for an invalid request, as `problems.invalid` defines it.
    bad = client.post("/v1/extractions/%s/field-reviews" % extraction_id,
                      json={"path": "not_a_field"})
    assert bad.status_code == 422
    assert bad.json()["code"] == "invalid_request"
