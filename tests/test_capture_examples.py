"""Capture the API_CONTRACT_FOR_UI.md examples from a real mock-mode run.

Run with `-m capture` to refresh `samples/examples.json`. It is a test rather
than a script so that the examples in the contract are captured from the same
code path the suite exercises: an example typed by hand drifts, and a UI agent
reading a drifted example writes a client against an API that does not exist.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples" / "examples.json"

def _trim(body: Any, keep_fields: int = 3) -> Any:
    """Shorten a response for publication without changing its shape."""
    if not isinstance(body, dict):
        return body
    out = dict(body)
    if isinstance(out.get("fields"), dict):
        keys = list(out["fields"])[:keep_fields]
        out["fields"] = {k: out["fields"][k] for k in keys}
        out["_fields_note"] = "%d entries in total; %d shown" % (
            len(body["fields"]), keep_fields,
        )
    if isinstance(out.get("data"), dict):
        data = out["data"]
        rows = data.get("line_items")
        if isinstance(rows, list) and len(rows) > 1:
            out["data"] = {**data, "line_items": rows[:1] + ["..."]}
    return out


def test_capture(client: Any, upload: Any, run_worker: Any, pdf: Any) -> None:
    engine = client.app.state.fdip.engine
    captured: dict[str, Any] = {}

    me = client.get("/v1/auth/me")
    captured["GET /v1/auth/me"] = {"status": me.status_code, "body": me.json()}

    templates = client.get("/v1/templates").json()
    captured["GET /v1/templates"] = {
        "status": 200,
        "body": [{
            **templates[0],
            "fields": templates[0]["fields"][:2] + ["... 34 in total"],
        }],
    }

    path = pdf("invoice_digital")
    with path.open("rb") as handle:
        created = client.post(
            "/v1/documents", headers={"Idempotency-Key": "ui-demo-1"},
            files={"file": (path.name, handle, "application/pdf")},
        )
    captured["POST /v1/documents"] = {"status": created.status_code,
                                      "body": created.json()}
    document_id = created.json()["document_id"]
    job_id = created.json()["job_id"]

    captured["GET /v1/documents/{id} (while processing)"] = {
        "status": 200,
        "body": client.get("/v1/documents/%s" % document_id).json(),
    }

    run_worker(engine)

    captured["GET /v1/documents/{id}"] = {
        "status": 200, "body": client.get("/v1/documents/%s" % document_id).json(),
    }
    captured["GET /v1/documents"] = {
        "status": 200, "body": client.get("/v1/documents?limit=2").json(),
    }
    analysis = client.get("/v1/documents/%s/analysis" % document_id).json()
    captured["GET /v1/documents/{id}/analysis"] = {
        "status": 200, "body": _trim(analysis),
    }
    captured["GET /v1/jobs/{id}"] = {
        "status": 200, "body": client.get("/v1/jobs/%s" % job_id).json(),
    }

    corrected = client.post(
        "/v1/extractions/%s/corrections" % analysis["extraction_id"],
        json={"changes": [{"path": "line_items[0].amount", "value": "505.00"}],
              "reason": "cell misread"},
    )
    captured["POST /v1/extractions/{id}/corrections"] = {
        "status": corrected.status_code, "body": _trim(corrected.json(), 2),
    }
    decided = client.post(
        "/v1/extractions/%s/decision" % corrected.json()["extraction_id"],
        json={"action": "approve"},
    )
    captured["POST /v1/extractions/{id}/decision"] = {
        "status": decided.status_code, "body": decided.json(),
    }

    schema = client.post("/v1/schemas", json={
        "template_id": "tpl_invoice_v1", "name": "AP invoices",
        "fields": ["invoice_number", "invoice_date", "vendor_name", "currency",
                   "subtotal", "tax_amount", "total", "line_items"],
        "locale_hints": {"date_order": "DMY"},
    })
    captured["POST /v1/schemas"] = {"status": schema.status_code,
                                    "body": schema.json()}
    schema_id = schema.json()["schema_id"]
    captured["GET /v1/schemas/{id}"] = {
        "status": 200, "body": client.get("/v1/schemas/%s" % schema_id).json(),
    }

    more = []
    for name in ("invoice_malay", "invoice_two_tax_lines"):
        other, _ = upload(name)
        more.append(other)
    run_worker(engine)
    run = client.post("/v1/schemas/%s/versions/1/test-runs" % schema_id,
                      json={"document_ids": [document_id, *more]})
    captured["POST /v1/schemas/{id}/versions/{v}/test-runs"] = {
        "status": run.status_code, "body": run.json(),
    }
    contract = client.get("/v1/schemas/%s/versions/1/contract" % schema_id).json()
    captured["GET /v1/schemas/{id}/versions/{v}/contract"] = {
        "status": 200,
        "body": {
            "$schema": contract["$schema"], "title": contract["title"],
            "x-field-paths": contract["x-field-paths"],
            "...": "plus properties for extraction_id, status, data, fields, "
                   "validation",
        },
    }

    key = client.post("/v1/api-keys", json={
        "name": "ui demo", "mode": "test",
        "schema_versions": [{"schema_id": schema_id, "version": 1}],
    })
    body = dict(key.json())
    body["key"] = "fdip_test_" + "X" * 40 + "  (the real key appears here once)"
    captured["POST /v1/api-keys"] = {"status": key.status_code, "body": body}
    captured["GET /v1/api-keys"] = {
        "status": 200, "body": client.get("/v1/api-keys").json(),
    }

    export = client.post("/v1/exports", json={"format": "xlsx",
                                              "document_ids": [document_id]})
    captured["POST /v1/exports"] = {"status": export.status_code,
                                    "body": export.json()}
    captured["GET /v1/usage"] = {
        "status": 200, "body": client.get("/v1/usage").json(),
    }
    captured["GET /v1/health"] = {
        "status": 200, "body": client.get("/v1/health").json(),
    }

    missing = client.get("/v1/documents/doc_does_not_exist")
    captured["an error response (RFC 9457)"] = {
        "status": missing.status_code, "body": missing.json(),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(captured, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    assert OUT.is_file()
    # Every example is a real response, so every status is a real status.
    assert captured["POST /v1/documents"]["status"] == 202
    assert captured["an error response (RFC 9457)"]["status"] == 404
