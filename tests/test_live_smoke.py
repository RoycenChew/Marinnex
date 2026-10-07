"""The one test that spends money. Skipped unless explicitly asked for.

    $env:FDIP_LIVE_SMOKE = "1"
    python -m pytest tests/test_live_smoke.py -q -s -m live

It runs one real DeepSeek call on `samples/invoice_digital.pdf` with its own cost
ceiling, and asserts on what a smoke test should: that a real provider answers,
that grounding finds the values among the document's own words, and that the spend
is what the benchmark predicted. It is marked `live` and gated on an environment
variable so it cannot run by accident in CI or in a full-suite run.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from fdip.adapters.db import create_all, create_db_engine, transaction
from fdip.adapters.keys import hash_password
from fdip.adapters.providers import build_model_stack
from fdip.adapters.repository import GlobalRepository, ProjectRepository
from fdip.adapters.seed import seed
from fdip.adapters.storage import BlobStore, sha256_bytes
from fdip.config import load_settings
from fdip.pipeline.runner import JobContext, run_job
from fdip.worker import full_template_spec

CEILING_USD = 0.05
"""Part B's budget for this is USD 1 in total; one document needs a fiftieth of
that, and the ceiling is passed to the governor so it is enforced rather than
hoped for."""

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "invoice_digital.pdf"

pytestmark = pytest.mark.live


@pytest.fixture
def live_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    if os.environ.get("FDIP_LIVE_SMOKE", "").strip() != "1":
        pytest.skip("set FDIP_LIVE_SMOKE=1 to run the live smoke test")
    # Read the real key from the toolkit's env file, the same way the benchmark
    # does, rather than requiring it to be exported.
    for candidate in (
        Path(__file__).resolve().parent.parent.parent / "Toolkits_Management"
        / ".toolkit.env",
        Path(__file__).resolve().parent.parent / ".env",
    ):
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DEEPSEEK_API_KEY=") and "=" in line:
                    os.environ.setdefault(
                        "DEEPSEEK_API_KEY", line.split("=", 1)[1].strip()
                    )
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured")

    monkeypatch.setenv("FDIP_PROVIDER_MODE", "live")
    monkeypatch.setenv("FDIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FDIP_DB_URL",
                       "sqlite:///" + str(tmp_path / "data" / "live.db"))
    monkeypatch.setenv("FDIP_KEY_PEPPER", "live-smoke-pepper-0123456789abcdef")
    monkeypatch.setenv("FDIP_SESSION_SECRET", "live-smoke-secret-0123456789abcd")
    monkeypatch.setenv("FDIP_EXTRACT_THINKING", "repair")
    monkeypatch.setenv("FDIP_DEV_SEED", "1")
    monkeypatch.setenv("FDIP_SANDBOX", "0")
    monkeypatch.setenv("FDIP_AI_MONTHLY_CEILING_USD", str(CEILING_USD))
    settings = load_settings(env_file=None)
    settings.ensure_dirs()
    return settings


def test_one_real_deepseek_call(live_settings: Any) -> None:
    settings = live_settings
    assert SAMPLE.is_file(), SAMPLE
    engine = create_db_engine(settings.db_url)
    create_all(engine)
    seed(engine, settings)
    # The dev account is deliberately never seeded in live mode, so this test
    # makes its own project rather than weakening that guard.
    with transaction(engine) as connection:
        globals_repo = GlobalRepository(connection)
        user_id = globals_repo.create_user(
            email="smoke@fdip.local",
            password_hash=hash_password("smoke-password"), is_active=True,
        )
        project_id = globals_repo.create_project(
            owner_id=user_id, name="Smoke",
            allowed_providers=["deepseek"], monthly_page_quota=100,
        )

    data = SAMPLE.read_bytes()
    digest = sha256_bytes(data)
    _, blob = BlobStore(settings.blob_dir).put(data)

    with transaction(engine) as connection:
        repo = ProjectRepository(connection, project_id)
        document_id = repo.create_document(
            filename=SAMPLE.name, mime="application/pdf", byte_size=len(data),
            sha256=digest, blob_path=blob, status="processing", origin="smoke",
        )
        job_id = repo.create_job(document_id=document_id, run_id=digest[:32],
                                 state="received", mode="smoke")

    models = build_model_stack(settings, ceiling_usd=CEILING_USD)
    assert models.mode == "live"
    assert models.provider_name != "mock"

    outcome = run_job(JobContext(
        engine=engine, settings=settings, models=models, project_id=project_id,
        document_id=document_id, job_id=job_id, blob_path=blob,
        spec=full_template_spec(), purpose="analysis",
    ), digest)

    assert outcome.get("extraction_id"), outcome
    with transaction(engine) as connection:
        repo = ProjectRepository(connection, project_id)
        extraction = repo.extraction(str(outcome["extraction_id"]))
        fields = {str(row["path"]): row for row in repo.fields(str(extraction["id"]))}
        calls = repo.provider_calls(document_id)

    assert extraction is not None
    print()
    print("LIVE SMOKE  status=%s  type=%s" % (extraction["status"],
                                              extraction["document_type"]))
    print("  tokens in=%d out=%d  cost=$%.5f  %.1fs  attempts=%d"
          % (extraction["input_tokens"], extraction["output_tokens"],
             extraction["cost_usd"], extraction["seconds"],
             extraction["attempts"]))
    print("  provider=%s model=%s" % (extraction["provider"], extraction["model"]))
    grounded = sum(
        1 for row in fields.values()
        if str(row["match"]) in ("exact", "normalized", "derived")
    )
    print("  fields=%d grounded=%d" % (len(fields), grounded))

    # A real call happened and was priced. An unpriced call would leave the
    # ceiling unenforceable, which the governor refuses rather than pretending.
    assert extraction["input_tokens"] > 0
    assert extraction["output_tokens"] > 0
    assert 0 < float(extraction["cost_usd"]) < CEILING_USD
    assert any(str(row["provider"]) != "mock" for row in calls)

    # The model read the document, and deterministic code found the values on the
    # page. Both halves matter: the second is what makes the first trustworthy.
    assert fields["invoice_number"]["value_json"] == "INV-2026-0417"
    assert str(fields["invoice_number"]["match"]) in ("exact", "normalized")
    assert fields["total"]["value_json"] == "2142.72"
    assert str(fields["total"]["match"]) in ("exact", "normalized", "derived")
    assert fields["vendor_name"]["value_json"] == "SOUTHERN STEEL TRADING SDN BHD"
    # The part code the Phase 1 prompt fix was written for.
    assert fields["line_items[0].description"]["value_json"] == (
        "Hex bolt stainless M8 HBS-1000"
    )
    assert grounded >= 10, {
        path: str(row["match"]) for path, row in fields.items()
    }
    assert extraction["status"] in ("completed", "needs_review")
    engine.dispose()
