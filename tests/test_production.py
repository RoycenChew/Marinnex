"""What changes when `FDIP_ENV=production`.

Development is permissive on purpose — mock provider, open registration, a
generated session secret — and every one of those is wrong in front of real
users. This file pins the differences, because a setting that only takes effect
on a server nobody has deployed yet is a setting nobody has tested.

The pattern throughout: refuse at startup rather than degrade at runtime. A
server that starts without a pepper and quietly invalidates every API key is
worse than one that will not start.
"""
from __future__ import annotations

from typing import Any

import pytest

from fdip import config


def _production_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, **overrides: str) -> None:
    base = {
        "FDIP_ENV": "production",
        "FDIP_PROVIDER_MODE": "live",
        "FDIP_KEY_PEPPER": "a-perfectly-adequate-production-pepper",
        "FDIP_SESSION_SECRET": "a-perfectly-adequate-production-secret",
        "DEEPSEEK_API_KEY": "sk-not-a-real-key",
        "FDIP_AI_MONTHLY_CEILING_USD": "20",
        "FDIP_DATA_DIR": str(tmp_path),
    }
    base.update(overrides)
    for name in ("FDIP_ENV", "FDIP_PROVIDER_MODE", "FDIP_KEY_PEPPER",
                 "FDIP_SESSION_SECRET", "DEEPSEEK_API_KEY",
                 "FDIP_AI_MONTHLY_CEILING_USD", "FDIP_ALLOW_REGISTRATION"):
        monkeypatch.delenv(name, raising=False)
    for name, value in base.items():
        monkeypatch.setenv(name, value)


# --- startup refusals --------------------------------------------------------


def test_production_refuses_to_start_without_its_required_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Three settings have no safe default in front of real users.

    A generated pepper invalidates every key already issued. A missing provider
    key means every document fails at the one stage that costs money. A missing
    ceiling means an unbounded bill. None of them should be discovered from a
    user's error report.
    """
    for missing in ("FDIP_KEY_PEPPER", "DEEPSEEK_API_KEY",
                    "FDIP_AI_MONTHLY_CEILING_USD"):
        _production_env(monkeypatch, tmp_path)
        monkeypatch.delenv(missing, raising=False)
        with pytest.raises(ValueError, match=missing):
            config.load_settings(env_file=None)

    # With all three set, it starts.
    _production_env(monkeypatch, tmp_path)
    settings = config.load_settings(env_file=None)
    assert settings.environment == "production"
    assert settings.is_production


def test_production_forbids_the_mock_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Mock mode answers from canned fixtures.

    In development that is the point. In production it would serve invented
    data that looks exactly like a real extraction, which is the single worst
    failure this product could have.
    """
    _production_env(monkeypatch, tmp_path, FDIP_PROVIDER_MODE="mock")
    with pytest.raises(ValueError, match="mock"):
        config.load_settings(env_file=None)


def test_development_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """None of the above applies off a server, or nobody could run the thing."""
    for name in ("FDIP_ENV", "DEEPSEEK_API_KEY", "FDIP_AI_MONTHLY_CEILING_USD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FDIP_PROVIDER_MODE", "mock")
    monkeypatch.setenv("FDIP_KEY_PEPPER", "a-perfectly-adequate-dev-pepper")
    monkeypatch.setenv("FDIP_DATA_DIR", str(tmp_path))

    settings = config.load_settings(env_file=None)
    assert settings.environment == "development"
    assert not settings.is_production
    assert settings.provider_mode == "mock"


# --- health ------------------------------------------------------------------


def test_health_reports_the_database_and_the_worker_and_nothing_else(
    client: Any,
) -> None:
    """A health check is read by uptime monitors and load balancers.

    It must say whether the thing works, and nothing a stranger could use: no
    secrets, no model name, no document or user counts that would leak volume.
    """
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] in ("ok", "degraded")
    assert body["database"] == "ok"
    assert "worker_heartbeat_age_seconds" in body
    assert body["pipeline_version"]

    # Nothing sensitive, and nothing countable.
    text = response.text.lower()
    for leaked in ("pepper", "secret", "sk-", "api_key", "deepseek"):
        assert leaked not in text, leaked
    for counted in ("documents", "users", "extractions", "projects"):
        assert counted not in body, counted


# --- invite-only registration ------------------------------------------------


def test_registration_can_be_closed(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invite-only is the launch posture, so the switch has to work.

    403 with a message a person can act on, not a 404 pretending the route does
    not exist: a stranger finding the sign-up page should be told it is closed,
    not left wondering.
    """
    state = client.app.state.fdip
    from dataclasses import replace

    original = state.settings
    state.settings = replace(original, allow_registration=False)
    try:
        refused = client.post("/v1/auth/register", json={
            "email": "stranger@example.com", "password": "a-long-enough-password",
        })
        assert refused.status_code == 403
        assert refused.json()["code"] == "registration_closed"
        assert "invit" in refused.json()["detail"].lower()
    finally:
        state.settings = original

    # Open by default, so development is unaffected.
    allowed = client.post("/v1/auth/register", json={
        "email": "newcomer@example.com", "password": "a-long-enough-password",
    })
    assert allowed.status_code == 201, allowed.text


def test_the_ui_is_told_whether_registration_is_open(client: Any) -> None:
    """The UI cannot hide a sign-up link it does not know is closed."""
    body = client.get("/v1/health").json()
    assert body["allow_registration"] is True


# --- rate limits -------------------------------------------------------------


def test_login_is_rate_limited_per_ip(client: Any) -> None:
    """Password guessing is the attack this stops.

    Per IP rather than per account, because an attacker trying one password
    against a thousand accounts never trips a per-account limit.
    """
    state = client.app.state.fdip
    state.rate_limiter._windows.clear()

    seen_429 = False
    for _ in range(40):
        response = client.post("/v1/auth/login", json={
            "email": "nobody@example.com", "password": "wrong",
        })
        if response.status_code == 429:
            seen_429 = True
            assert response.json()["code"] == "rate_limited"
            assert response.headers.get("retry-after")
            break
    assert seen_429, "login accepted 40 attempts from one address"


def test_upload_is_rate_limited_per_ip(client: Any, pdf: Any) -> None:
    state = client.app.state.fdip
    state.rate_limiter._windows.clear()
    path = pdf("invoice_digital")
    data = path.read_bytes()

    seen_429 = False
    for index in range(40):
        response = client.post(
            "/v1/documents",
            files={"file": ("a.pdf", data, "application/pdf")},
            headers={"Idempotency-Key": "rl-%d" % index},
        )
        if response.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "upload accepted 40 documents from one address in a minute"


def test_a_rate_limited_caller_is_not_locked_out_forever(client: Any) -> None:
    """The window is a minute, not a ban. Proved by moving the clock, because a
    test that sleeps for sixty seconds is a test nobody runs."""
    state = client.app.state.fdip
    state.rate_limiter._windows.clear()
    state.rate_limiter.check("probe", limit=1)
    from fdip.api import problems

    with pytest.raises(problems.Problem):
        state.rate_limiter.check("probe", limit=1)

    window, _count = state.rate_limiter._windows["probe"]
    state.rate_limiter._windows["probe"] = (window - 1, 99)
    assert state.rate_limiter.check("probe", limit=1) == 0


# --- logging -----------------------------------------------------------------


def test_production_logs_carry_no_document_text_or_secrets(
    client: Any, upload: Any, run_worker: Any, caplog: Any
) -> None:
    """Rule 2.13, checked with production settings rather than development.

    The existing security test covers the development path; this one runs the
    same document through with `FDIP_ENV=production` so a logger that is only
    attached on a server cannot smuggle content into a log line.
    """
    import logging
    from dataclasses import replace

    state = client.app.state.fdip
    original = state.settings
    state.settings = replace(original, environment="production")
    caplog.set_level(logging.DEBUG)
    try:
        document_id, _ = upload("invoice_digital")
        run_worker(state.engine)
        client.get("/v1/documents/%s/analysis" % document_id)
    finally:
        state.settings = original

    logged = "\n".join(record.getMessage() for record in caplog.records)
    for secret in ("INV-2026-0417", "SOUTHERN STEEL", "2142.72", "PO-88213",
                   original.key_pepper, original.session_secret):
        assert secret not in logged, secret


# --- inviting a user from the command line -----------------------------------


def test_create_user_makes_an_account_with_a_project(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """Registration is closed in production, so this is the only way in.

    An account with no project is a dead end the UI cannot escape, so the
    command creates both — the same thing `/auth/register` does.
    """
    from fdip import cli

    monkeypatch.setenv("FDIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FDIP_DB_URL", "sqlite:///%s/invite.db" % tmp_path.as_posix())
    monkeypatch.setenv("FDIP_KEY_PEPPER", "a-perfectly-adequate-test-pepper")
    monkeypatch.setenv("FDIP_PROVIDER_MODE", "mock")
    monkeypatch.delenv("FDIP_ENV", raising=False)
    config.override(None)

    assert cli.main(["migrate"]) == 0
    assert cli.main(["create-user", "--email", "Invited@Example.COM",
                     "--password", "a-long-enough-password"]) == 0

    out = capsys.readouterr().out
    assert "invited@example.com" in out
    # The password is the caller's to pass on; the command must not echo it.
    assert "a-long-enough-password" not in out

    from sqlalchemy import create_engine

    from fdip.adapters.repository import GlobalRepository

    engine = create_engine(config.settings().db_url, future=True)
    with engine.connect() as conn:
        repo = GlobalRepository(conn)
        user = repo.user_by_email("invited@example.com")
        assert user is not None, "the account was not created"
        assert str(user["password_hash"]) != "a-long-enough-password", "stored in clear"
        assert repo.projects_for(str(user["id"])), "an account with no project is a dead end"

    # Twice is an error, not a silent second account.
    assert cli.main(["create-user", "--email", "invited@example.com",
                     "--password", "another-long-password"]) == 1
    assert "already" in capsys.readouterr().err.lower()


def test_reset_password_changes_the_hash_and_nothing_else(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """Someone will lock themselves out, and there is no email to reset by.

    It changes the stored hash and leaves the account, its project and its
    documents alone — a reset that quietly created a second account would be
    worse than no reset at all.
    """
    from fdip import cli

    monkeypatch.setenv("FDIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FDIP_DB_URL", "sqlite:///%s/reset.db" % tmp_path.as_posix())
    monkeypatch.setenv("FDIP_KEY_PEPPER", "a-perfectly-adequate-test-pepper")
    monkeypatch.setenv("FDIP_PROVIDER_MODE", "mock")
    monkeypatch.delenv("FDIP_ENV", raising=False)
    config.override(None)

    assert cli.main(["migrate"]) == 0
    assert cli.main(["create-user", "--email", "locked@example.com",
                     "--password", "the-first-password"]) == 0
    capsys.readouterr()

    from sqlalchemy import create_engine

    from fdip.adapters import keys as key_tools
    from fdip.adapters.repository import GlobalRepository

    engine = create_engine(config.settings().db_url, future=True)
    with engine.connect() as conn:
        before = GlobalRepository(conn).user_by_email("locked@example.com")
        user_id, old_hash = str(before["id"]), str(before["password_hash"])

    assert cli.main(["reset-password", "--email", "LOCKED@example.com",
                     "--password", "the-second-password"]) == 0
    out = capsys.readouterr().out
    assert "locked@example.com" in out
    assert "the-second-password" not in out, "a password echoed is a password logged"

    with engine.connect() as conn:
        after = GlobalRepository(conn).user_by_email("locked@example.com")
        assert str(after["id"]) == user_id, "it created a new account instead"
        assert str(after["password_hash"]) != old_hash
        assert key_tools.verify_password("the-second-password",
                                         str(after["password_hash"]))
        assert not key_tools.verify_password("the-first-password",
                                             str(after["password_hash"]))

    # An unknown address is an error, not a silently created account.
    assert cli.main(["reset-password", "--email", "nobody@example.com",
                     "--password", "a-long-enough-password"]) == 1
    assert "no account" in capsys.readouterr().err.lower()
