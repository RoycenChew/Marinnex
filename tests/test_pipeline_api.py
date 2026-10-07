"""B5.2 and B5.3: the pipeline call, its published contract, and the type gate.

The contract test is the one that matters most to a customer: the response is
validated against the JSON Schema that `GET .../contract` publishes, with
`jsonschema`, so the document and the behaviour cannot drift apart. A contract
nobody validates is a comment.
"""
from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator


def _schema_with_passing_test_run(client: Any, run_worker: Any,
                                  upload: Any) -> tuple[str, int, list[str]]:
    """A schema version that has passed a test run, which a key requires."""
    engine = client.app.state.fdip.engine
    document_ids = []
    for name in ("invoice_digital", "invoice_malay", "invoice_two_tax_lines"):
        document_id, _ = upload(name)
        document_ids.append(document_id)
    run_worker(engine)

    created = client.post("/v1/schemas", json={
        "template_id": "tpl_invoice_v1",
        "name": "AP invoices",
        "fields": ["invoice_number", "invoice_date", "vendor_name", "currency",
                   "subtotal", "tax_amount", "total", "line_items"],
        "locale_hints": {"date_order": "DMY"},
    })
    assert created.status_code == 201, created.text
    schema_id = created.json()["schema_id"]
    version = created.json()["version"]

    run = client.post(
        "/v1/schemas/%s/versions/%d/test-runs" % (schema_id, version),
        json={"document_ids": document_ids},
    )
    assert run.status_code == 202, run.text
    assert run.json()["passed"] is True, run.json()["per_document"]
    return schema_id, version, document_ids


def test_a_key_cannot_use_an_untested_version(client: Any) -> None:
    """The gate from 3.7, which is the point of requiring a test run at all."""
    created = client.post("/v1/schemas", json={
        "template_id": "tpl_invoice_v1", "name": "Untested",
        "fields": ["invoice_number", "total"],
    }).json()
    key = client.post("/v1/api-keys", json={
        "name": "untested", "mode": "test",
        "schema_versions": [{"schema_id": created["schema_id"], "version": 1}],
    }).json()["key"]

    import io

    response = client.post(
        "/v1/extract",
        headers={"Authorization": "Bearer " + key},
        files={"file": ("x.pdf", io.BytesIO(b"%PDF-1.4\nnot really"),
                        "application/pdf")},
        data={"schema_id": created["schema_id"], "schema_version": "1"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "schema_test_run_required"


def test_extract_with_wait_matches_the_published_contract(
    client: Any, run_worker: Any, upload: Any, pdf: Any
) -> None:
    schema_id, version, _ = _schema_with_passing_test_run(client, run_worker, upload)

    contract = client.get(
        "/v1/schemas/%s/versions/%d/contract" % (schema_id, version)
    )
    assert contract.status_code == 200, contract.text
    document = contract.json()
    Draft202012Validator.check_schema(document)
    assert "line_items[i].amount" in document["x-field-paths"]
    assert document["properties"]["data"]["properties"]["total"]["type"] == [
        "string", "null",
    ], "a decimal crosses the wire as a string, never a JSON number"

    key = client.post("/v1/api-keys", json={
        "name": "integration", "mode": "test",
        "schema_versions": [{"schema_id": schema_id, "version": version}],
    }).json()["key"]
    assert key.startswith("fdip_test_")

    # The handler has to be in place for the inline run, which happens inside the
    # request rather than in the worker.
    from fixtures import handler_for

    from fdip.adapters import providers

    original = providers.build_model_stack

    def patched(*args: Any, **kwargs: Any) -> Any:
        kwargs["handler"] = handler_for()
        return original(*args, **kwargs)

    providers.build_model_stack = patched
    import fdip.api.routers.pipeline as pipeline_module

    pipeline_module.build_model_stack = patched
    try:
        path = pdf("invoice_digital")
        with path.open("rb") as handle:
            response = client.post(
                "/v1/extract?wait=30",
                headers={"Authorization": "Bearer " + key},
                files={"file": (path.name, handle, "application/pdf")},
                data={"schema_id": schema_id, "schema_version": str(version)},
            )
    finally:
        providers.build_model_stack = original
        pipeline_module.build_model_stack = original

    assert response.status_code == 200, response.text
    body = response.json()
    Draft202012Validator(document).validate(body)
    assert body["data"]["invoice_number"] == "INV-2026-0417"
    assert body["schema"]["version"] == version
    assert body["status"] in ("completed", "needs_review")
    # The selected subset only: a pipeline call must not return fields the
    # customer did not ask for and is not paying to have validated.
    assert "vendor_address" not in body["data"]


def test_a_bank_statement_sent_to_an_invoice_schema_is_a_type_mismatch(
    client: Any, run_worker: Any, upload: Any, pdf: Any
) -> None:
    """B5.3. No data is returned, which is the part that protects the customer."""
    schema_id, version, _ = _schema_with_passing_test_run(client, run_worker, upload)
    key = client.post("/v1/api-keys", json={
        "name": "gate", "mode": "test",
        "schema_versions": [{"schema_id": schema_id, "version": version}],
    }).json()["key"]

    from fixtures import handler_for

    from fdip.adapters import providers

    original = providers.build_model_stack

    def patched(*args: Any, **kwargs: Any) -> Any:
        kwargs["handler"] = handler_for()
        return original(*args, **kwargs)

    providers.build_model_stack = patched
    import fdip.api.routers.pipeline as pipeline_module

    pipeline_module.build_model_stack = patched
    try:
        path = pdf("bank_statement")
        with path.open("rb") as handle:
            response = client.post(
                "/v1/extract?wait=30",
                headers={"Authorization": "Bearer " + key},
                files={"file": (path.name, handle, "application/pdf")},
                data={"schema_id": schema_id, "schema_version": str(version)},
            )
    finally:
        providers.build_model_stack = original
        pipeline_module.build_model_stack = original

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "document_type_mismatch"
    assert body["data"] == {}, "a mismatch must return no data"
    assert any("document_type_mismatch" in r for r in body["reasons"])


def test_an_interactive_upload_is_not_gated_on_type(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """The gate is a pipeline rule only (3.3 stage 6).

    A user who uploads a bank statement by hand is looking at the screen and
    wants to see what was found, not a refusal.
    """
    document_id, _ = upload("bank_statement")
    run_worker(client.app.state.fdip.engine)
    body = client.get("/v1/documents/%s/analysis" % document_id).json()
    assert body["status"] != "document_type_mismatch"
    assert body["document_type"] == "bank_statement"


def test_a_schema_version_is_immutable(client: Any) -> None:
    """Adding a version must not change the one a customer has pinned."""
    created = client.post("/v1/schemas", json={
        "template_id": "tpl_invoice_v1", "name": "Pinned",
        "fields": ["invoice_number", "total"],
    }).json()
    schema_id = created["schema_id"]
    first = client.get("/v1/schemas/%s/versions/1/contract" % schema_id).json()

    added = client.post("/v1/schemas/%s/versions" % schema_id, json={
        "fields": ["invoice_number", "total", "vendor_name", "line_items"],
    })
    assert added.status_code == 201
    assert added.json()["version"] == 2

    again = client.get("/v1/schemas/%s/versions/1/contract" % schema_id).json()
    assert again == first, "version 1's contract changed when version 2 was added"
    second = client.get("/v1/schemas/%s/versions/2/contract" % schema_id).json()
    assert "vendor_name" in second["properties"]["data"]["properties"]
    assert "vendor_name" not in first["properties"]["data"]["properties"]


def test_a_test_run_needs_three_to_five_documents(client: Any) -> None:
    created = client.post("/v1/schemas", json={
        "template_id": "tpl_invoice_v1", "name": "Few",
        "fields": ["invoice_number", "total"],
    }).json()
    response = client.post(
        "/v1/schemas/%s/versions/1/test-runs" % created["schema_id"],
        json={"document_ids": ["doc_1", "doc_2"]},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["nonexistent_field", "line_items[].nope"])
def test_a_schema_cannot_select_a_field_the_template_does_not_have(
    client: Any, field: str
) -> None:
    response = client.post("/v1/schemas", json={
        "template_id": "tpl_invoice_v1", "name": "Bad " + field,
        "fields": ["invoice_number", field],
    })
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
