"""Test fixtures: an isolated app, in mock mode, with the queue run by hand.

Three choices here matter.

**A temporary data directory per test.** The database, the blobs, the checkpoints
and the LLM cache all live under it, so no test can see another's rows and a
failed test leaves evidence behind in its own directory.

**Mock mode, always.** No test may contact a provider. `FDIP_PROVIDER_MODE=mock`
is set on the environment the settings are built from, and the one live test is
marked and skipped unless it is asked for explicitly.

**`FDIP_SANDBOX=0`.** Parsing runs in process. The subprocess sandbox is exercised
by its own test; spawning one per document would add about a second to every
other test on Windows for no extra coverage.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import BY_NAME, Variant, handler_for, write_pdf  # noqa: E402

from fdip.adapters.db import create_all, create_db_engine
from fdip.adapters.seed import DEV_EMAIL, DEV_PASSWORD, seed
from fdip.config import Settings, load_settings, override


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("FDIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FDIP_DB_URL", "sqlite:///" + str(tmp_path / "data" / "t.db"))
    monkeypatch.setenv("FDIP_PROVIDER_MODE", "mock")
    monkeypatch.setenv("FDIP_KEY_PEPPER", "test-pepper-0123456789abcdef")
    monkeypatch.setenv("FDIP_SESSION_SECRET", "test-secret-0123456789abcdef")
    # Deliberately not set: the per-route defaults (on for a text layer,
    # repair for a scan) are what production uses, so that is what the tests
    # should see. FDIP_EXTRACT_THINKING would override both.
    monkeypatch.delenv("FDIP_EXTRACT_THINKING", raising=False)
    monkeypatch.delenv("FDIP_EXTRACT_THINKING_DIGITAL", raising=False)
    monkeypatch.delenv("FDIP_EXTRACT_THINKING_SCAN", raising=False)
    monkeypatch.delenv("FDIP_SCAN_AUTO_ACCEPT", raising=False)
    monkeypatch.setenv("FDIP_DEV_SEED", "1")
    monkeypatch.setenv("FDIP_SANDBOX", "0")
    monkeypatch.setenv("FDIP_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    override(None)
    yield
    override(None)


@pytest.fixture
def settings() -> Settings:
    resolved = load_settings(env_file=None)
    resolved.ensure_dirs()
    return resolved


@pytest.fixture
def engine(settings: Settings) -> Iterator[Any]:
    created = create_db_engine(settings.db_url)
    create_all(created)
    seed(created, settings)
    yield created
    created.dispose()


@pytest.fixture
def app(settings: Settings) -> Iterator[Any]:
    from fdip.api.app import create_app

    yield create_app(settings, create_schema=True)


@pytest.fixture
def client(app: Any) -> Iterator[Any]:
    """A logged-in test client on the dev account.

    Logged in by the fixture because every UI route needs a session and
    repeating the login in forty tests tells the reader nothing.
    """
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://localhost") as test_client:
        response = test_client.post("/v1/auth/login", json={
            "email": DEV_EMAIL, "password": DEV_PASSWORD,
        })
        assert response.status_code == 200, response.text
        yield test_client


@pytest.fixture
def anonymous(app: Any) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture
def pdf(tmp_path: Path) -> Any:
    """`pdf("invoice_malay")` -> a real PDF of that variant."""
    def make(name: str = "invoice_digital") -> Path:
        return write_pdf(tmp_path / ("%s.pdf" % name), BY_NAME[name])

    return make


@pytest.fixture
def upload(client: Any, pdf: Any) -> Any:
    """Upload a variant and return `(document_id, job_id)`."""
    def do(name: str = "invoice_digital", **kwargs: Any) -> tuple[str, str]:
        path = pdf(name)
        with path.open("rb") as handle:
            response = client.post(
                "/v1/documents",
                files={"file": (path.name, handle, "application/pdf")},
                **kwargs,
            )
        assert response.status_code == 202, response.text
        body = response.json()
        return body["document_id"], body["job_id"]

    return do


@pytest.fixture
def run_worker(settings: Settings) -> Any:
    """Drain the job queue synchronously, with the scripted model.

    Synchronous on purpose: a test that starts the real worker thread and sleeps
    is a test that fails on a loaded machine for reasons that have nothing to do
    with the code.
    """
    from fdip.worker import drain

    def go(engine: Any, variants: tuple[Variant, ...] | None = None,
           limit: int = 20) -> list[dict[str, Any]]:
        from fdip.adapters import providers

        handler = handler_for(variants) if variants else handler_for()
        original = providers.build_model_stack

        def patched(*args: Any, **kwargs: Any) -> Any:
            kwargs["handler"] = handler
            return original(*args, **kwargs)

        providers.build_model_stack = patched  # type: ignore[assignment]
        # Also patch the name the worker imported at module load, which is a
        # separate binding and the reason a naive monkeypatch here does nothing.
        import fdip.worker as worker_module

        worker_original = worker_module.build_model_stack
        worker_module.build_model_stack = patched  # type: ignore[assignment]
        try:
            return drain(engine, settings, limit=limit)
        finally:
            providers.build_model_stack = original  # type: ignore[assignment]
            worker_module.build_model_stack = worker_original  # type: ignore[assignment]

    return go


@pytest.fixture
def app_engine(app: Any) -> Any:
    """The engine the running app is using, for a test that drains its queue."""
    def get(test_client: Any) -> Any:
        return test_client.app.state.fdip.engine

    return get


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "live: contacts the real provider and spends money; "
                   "run with -m live and FDIP_LIVE_SMOKE=1",
    )


def live_enabled() -> bool:
    return os.environ.get("FDIP_LIVE_SMOKE", "").strip() == "1"
