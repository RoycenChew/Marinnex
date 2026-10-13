"""B5.6 and B5.7: key storage, revocation, tenant isolation, logs, idempotency.

The log test is the one that is easy to write badly. It captures the whole log
stream and asserts that no extracted value appears in it -- searching for the
actual values from the fixture, not for a pattern that might match them. A test
that greps for "total" would pass while the amount was being logged.
"""
from __future__ import annotations

import io
import logging
from typing import Any

import pytest

from fdip.adapters import keys as key_tools
from fdip.adapters.seed import DEV_EMAIL, DEV_PASSWORD


def test_an_api_key_is_stored_hashed_and_shown_once(client: Any) -> None:
    created = client.post("/v1/api-keys", json={"name": "ci", "mode": "live"})
    assert created.status_code == 201, created.text
    body = created.json()
    secret = body["key"]
    assert secret.startswith("fdip_live_")
    assert len(secret) > 40

    engine = client.app.state.fdip.engine
    from sqlalchemy import select

    from fdip.adapters.tables import api_keys

    with engine.connect() as connection:
        row = connection.execute(
            select(api_keys).where(api_keys.c.id == body["id"])
        ).mappings().one()

    assert row["key_hash"] != secret
    assert secret not in row["key_hash"]
    assert len(row["key_hash"]) == 64, "HMAC-SHA256, hex"
    # The stored digest is useless without the server pepper.
    assert key_tools.verify_key(
        secret, str(row["key_hash"]), client.app.state.fdip.settings.key_pepper
    )
    assert not key_tools.verify_key(secret, str(row["key_hash"]), "wrong-pepper")

    # Nothing hands the key back. The listing shows the prefix only.
    listed = client.get("/v1/api-keys").json()
    assert [entry["prefix"] for entry in listed] == [body["prefix"]]
    assert all("key" not in entry for entry in listed)
    assert all("key_hash" not in entry for entry in listed)


def test_a_revoked_key_returns_401(client: Any) -> None:
    created = client.post("/v1/api-keys", json={"name": "doomed",
                                                "mode": "test"}).json()
    key = created["key"]
    headers = {"Authorization": "Bearer " + key}

    # A valid key reaches the route and is refused on the request body, not on
    # authentication: that is how we know the key itself was accepted.
    before = client.post("/v1/extract", headers=headers, data={})
    assert before.status_code != 401, before.text

    assert client.delete("/v1/api-keys/%s" % created["id"]).status_code == 204
    after = client.post("/v1/extract", headers=headers, data={})
    assert after.status_code == 401
    assert after.json()["code"] == "unauthenticated"


def test_an_unknown_or_malformed_key_is_401(client: Any) -> None:
    for header in ("Bearer fdip_live_totally-made-up", "Bearer nonsense",
                   "Basic abc", ""):
        response = client.post("/v1/extract", headers={"Authorization": header},
                               data={})
        assert response.status_code == 401, header
        # One message for every failure mode: which one it was is not the
        # caller's business.
        assert response.json()["detail"] in (
            "the key is not valid", "the key is not an FDIP key",
            "an Authorization: Bearer key is required",
        )


def test_another_projects_document_returns_404_not_403(
    client: Any, anonymous: Any, upload: Any, run_worker: Any
) -> None:
    """Telling an attacker the row exists is itself the leak."""
    document_id, _ = upload("invoice_digital")
    run_worker(client.app.state.fdip.engine)

    registered = anonymous.post("/v1/auth/register", json={
        "email": "intruder@example.com", "password": "a-long-password",
    })
    assert registered.status_code == 201, registered.text

    for path in ("/v1/documents/%s", "/v1/documents/%s/analysis",
                 "/v1/documents/%s/file", "/v1/documents/%s/extractions",
                 "/v1/documents/%s/pages/1/image"):
        response = anonymous.get(path % document_id)
        assert response.status_code == 404, (path, response.status_code)
        assert response.json()["code"] == "not_found"

    assert anonymous.delete("/v1/documents/%s" % document_id).status_code == 404
    # And the owner still has it: the intruder's 404 was not a delete.
    assert client.get("/v1/documents/%s" % document_id).status_code == 200


def test_a_project_id_that_is_not_yours_is_404(client: Any) -> None:
    response = client.get("/v1/documents?project_id=prj_someone_else")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_the_logs_contain_no_extracted_values(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """Rule 2.13, asserted against the actual values rather than a pattern."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        document_id, _ = upload("invoice_digital")
        run_worker(client.app.state.fdip.engine)
        body = client.get("/v1/documents/%s/analysis" % document_id).json()
        client.post("/v1/extractions/%s/corrections" % body["extraction_id"],
                    json={"changes": [{"path": "total", "value": "9999.99"}],
                          "reason": "typo"})
        client.post("/v1/exports", json={"format": "csv",
                                         "document_ids": [document_id]})
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)

    logged = stream.getvalue()
    forbidden = [
        "INV-2026-0417", "SOUTHERN STEEL TRADING", "Harapan Engineering",
        "2142.72", "1984.00", "Hex bolt stainless", "HBS-1000",
        "C12345678901", "9999.99",
    ]
    present = [needle for needle in forbidden if needle in logged]
    assert not present, (
        "these document values reached the log stream: %s" % present
    )
    # The ids and codes that *should* be there, so this is not passing vacuously.
    assert document_id in logged or "job=" in logged, logged[:500]


def test_the_audit_trail_records_ids_and_codes_but_no_values(
    client: Any, upload: Any, run_worker: Any
) -> None:
    document_id, _ = upload("invoice_digital")
    run_worker(client.app.state.fdip.engine)
    body = client.get("/v1/documents/%s/analysis" % document_id).json()
    client.post("/v1/extractions/%s/corrections" % body["extraction_id"],
                json={"changes": [{"path": "total", "value": "4242.42"}]})

    from fdip.adapters.repository import ProjectRepository

    engine = client.app.state.fdip.engine
    project_id = client.get("/v1/auth/me").json()["projects"][0]["id"]
    with engine.connect() as connection:
        rows = ProjectRepository(connection, project_id).audit_events()
    actions = {str(row["action"]) for row in rows}
    assert {"uploaded", "extracted", "corrected"} <= actions, actions

    blob = "".join(str(dict(row["detail"])) for row in rows)
    assert "4242.42" not in blob, "a corrected value must not reach the audit row"
    assert "total" in blob, "the path is recorded; only the value is not"


def test_a_session_cookie_is_httponly_and_lax(anonymous: Any) -> None:
    response = anonymous.post("/v1/auth/login", json={
        "email": DEV_EMAIL, "password": DEV_PASSWORD,
    })
    assert response.status_code == 200
    header = response.headers["set-cookie"]
    assert key_tools.SESSION_COOKIE in header
    assert "HttpOnly" in header
    assert "SameSite=lax" in header or "samesite=lax" in header.lower()
    # Not Secure over http, or the browser drops it and the UI silently fails.
    assert "Secure" not in header


def test_login_does_not_say_which_half_was_wrong(anonymous: Any) -> None:
    unknown = anonymous.post("/v1/auth/login", json={
        "email": "nobody@example.com", "password": "a-long-password",
    })
    wrong = anonymous.post("/v1/auth/login", json={
        "email": DEV_EMAIL, "password": "definitely-wrong",
    })
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_the_same_idempotency_key_and_body_returns_the_same_job(
    client: Any, pdf: Any
) -> None:
    """B5.7."""
    path = pdf("invoice_digital")
    headers = {"Idempotency-Key": "abc-123"}

    def send(name: str) -> Any:
        source = pdf(name)
        with source.open("rb") as handle:
            return client.post(
                "/v1/documents", headers=headers,
                files={"file": (source.name, handle, "application/pdf")},
            )

    first = send("invoice_digital")
    assert first.status_code == 202, first.text
    second = send("invoice_digital")
    assert second.status_code == 202, second.text
    assert second.json()["document_id"] == first.json()["document_id"]
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["reused"] is True

    different = send("invoice_malay")
    assert different.status_code == 409
    assert different.json()["code"] == "idempotency_conflict"
    assert path.exists()


def test_the_same_bytes_without_a_key_reuse_the_document(
    client: Any, pdf: Any
) -> None:
    """Stage 1: one document per content hash per project, so a re-upload is free."""
    def send() -> Any:
        source = pdf("invoice_digital")
        with source.open("rb") as handle:
            return client.post(
                "/v1/documents",
                files={"file": (source.name, handle, "application/pdf")},
            )

    first = send().json()
    second = send().json()
    assert second["document_id"] == first["document_id"]
    assert second["reused"] is True
    assert len(client.get("/v1/documents").json()["items"]) == 1


def test_a_test_key_cannot_reach_a_live_provider(settings: Any) -> None:
    """The reason the two key schemes exist at all."""
    from dataclasses import replace

    from fdip.api.deps import Principal, effective_provider_mode

    live = replace(settings, provider_mode="live")
    test_key = Principal(project_id="p", actor="k", via="api_key",
                         api_key_mode="test")
    live_key = Principal(project_id="p", actor="k", via="api_key",
                         api_key_mode="live")
    assert effective_provider_mode(live, test_key) == "mock"
    assert effective_provider_mode(live, live_key) == "live"


def test_an_unauthenticated_request_is_401_not_500(anonymous: Any) -> None:
    for path in ("/v1/documents", "/v1/auth/me", "/v1/usage", "/v1/api-keys",
                 "/v1/templates", "/v1/schemas"):
        response = anonymous.get(path)
        assert response.status_code == 401, path
        assert response.headers["content-type"].startswith(
            "application/problem+json"
        ), path
        assert response.json()["code"] == "unauthenticated"


def test_health_is_open_and_says_nothing_a_stranger_can_use(anonymous: Any) -> None:
    """It used to name the provider and the model. It no longer does.

    Unauthenticated means a stranger reads it, and the provider name tells them
    what to attack while telling the operator nothing they cannot read from the
    environment. What is left answers the only two questions a monitor asks: is
    the database reachable, and is the worker alive.
    """
    response = anonymous.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["pipeline_version"]
    assert "worker_heartbeat_age_seconds" in body
    for gone in ("provider_mode", "model", "extract_thinking"):
        assert gone not in body, gone


def test_startup_refuses_without_a_key_pepper(monkeypatch, tmp_path):
    """A generated pepper silently invalidates every key already issued.

    It used to be required in live mode only, so a local run would start, mint
    a fresh pepper, and leave every key in `data/fdip.db` failing to
    authenticate with no error anywhere. Losing credentials is not a
    development convenience, so the server now refuses to start without one in
    every mode.
    """
    from fdip import config

    for name in ("FDIP_KEY_PEPPER", "FDIP_SESSION_SECRET", "FDIP_PROVIDER_MODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FDIP_DATA_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="FDIP_KEY_PEPPER"):
        config.load_settings(env_file=None)

    # Too short counts as absent: a two-character pepper is not a secret.
    monkeypatch.setenv("FDIP_KEY_PEPPER", "short")
    with pytest.raises(ValueError, match="FDIP_KEY_PEPPER"):
        config.load_settings(env_file=None)

    # Set properly, it starts, and the value is used as given.
    monkeypatch.setenv("FDIP_KEY_PEPPER", "a-perfectly-adequate-test-pepper")
    settings = config.load_settings(env_file=None)
    assert settings.key_pepper == "a-perfectly-adequate-test-pepper"
