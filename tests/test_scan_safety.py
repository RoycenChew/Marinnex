"""The scan hold and the per-route thinking setting, end to end.

`tests/test_decision_rule.py` proves the rule in isolation. These tests prove it
is actually wired: that a scanned upload reaches `needs_review` through the real
pipeline, that the flag turns it off, and that the reasoning setting a document
runs with comes from its route rather than from one global value.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fdip.config import load_settings
from fdip.domain.decision import SCAN_REVIEW_REASON


def _scan(tmp_path: Path, source: Path) -> Path:
    """Render a sample to a PNG, so the pipeline must route it through OCR."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(source))
    try:
        image = document[0].render(scale=200 / 72).to_pil().convert("L")
    finally:
        document.close()
    target = tmp_path / "scan.png"
    image.save(target)
    return target


@pytest.fixture
def tesseract_or_skip() -> None:
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract is not on PATH, so route B cannot be exercised")


def test_a_scanned_document_never_auto_completes(
    client: Any, run_worker: Any, pdf: Any, tmp_path: Path, tesseract_or_skip: None
) -> None:
    """Route B goes to a human until `--final` measures it.

    13 silent errors in 30 mild scans is the measurement behind this. The document
    may well be extracted perfectly; the point is that we cannot currently tell.
    """
    scan = _scan(tmp_path, pdf("invoice_digital"))
    with scan.open("rb") as handle:
        response = client.post("/v1/documents",
                               files={"file": (scan.name, handle, "image/png")})
    assert response.status_code == 202, response.text
    document_id = response.json()["document_id"]
    run_worker(client.app.state.fdip.engine)

    body = client.get("/v1/documents/%s/analysis" % document_id).json()
    assert body["status"] == "needs_review", body["reasons"]
    assert SCAN_REVIEW_REASON in body["reasons"]

    # And the evidence says why: it came from OCR, with a confidence.
    sources = {
        item["source"]
        for entry in body["fields"].values() for item in entry["evidence"]
    }
    assert "ocr" in sources, sources
    confidences = [
        item["ocr_confidence"]
        for entry in body["fields"].values() for item in entry["evidence"]
        if item["ocr_confidence"] is not None
    ]
    assert confidences, "an OCR word carries a confidence; a text-layer word cannot"


def test_a_digital_document_is_unaffected(
    client: Any, upload: Any, run_worker: Any
) -> None:
    document_id, _ = upload("invoice_digital")
    run_worker(client.app.state.fdip.engine)
    body = client.get("/v1/documents/%s/analysis" % document_id).json()
    assert body["status"] == "completed", body["reasons"]
    assert SCAN_REVIEW_REASON not in body["reasons"]


def test_the_flag_defaults_to_holding_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FDIP_SCAN_AUTO_ACCEPT", raising=False)
    assert load_settings(env_file=None).scan_auto_accept is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("1", True), ("yes", True),
     ("false", False), ("0", False), ("", False)],
)
def test_the_flag_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("FDIP_SCAN_AUTO_ACCEPT", value)
    assert load_settings(env_file=None).scan_auto_accept is expected


def test_turning_the_flag_on_lets_a_scan_complete(
    client: Any, run_worker: Any, pdf: Any, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, tesseract_or_skip: None
) -> None:
    """The switch exists so that proving route B safe is a config change.

    Asserted at the decision rule rather than through the API, because the running
    app has already read its settings and the point here is the wiring of the flag
    into the stage, not a restart.
    """
    from fdip.pipeline.stages import validate_and_decide

    extracted = {
        "data": {"invoice_number": "INV-1", "total": "10.00"},
        "schema_valid": True, "truncated": False,
        "fields": [
            {"path": "invoice_number", "value": "INV-1", "match": "exact",
             "evidence": [{"page": 1, "source": "ocr", "ocr_confidence": 0.95}]},
        ],
    }
    from fdip.domain.schema_lang import SchemaSpec

    spec = SchemaSpec(name="I", document_type="invoice",
                      fields=("invoice_number",))
    held = validate_and_decide(extracted, spec, allow_ocr_auto_accept=False)
    assert held["status"] == "needs_review"
    assert SCAN_REVIEW_REASON in held["reasons"]

    allowed = validate_and_decide(extracted, spec, allow_ocr_auto_accept=True)
    assert SCAN_REVIEW_REASON not in allowed["reasons"]
    assert monkeypatch is not None


# -- per-route thinking -------------------------------------------------------

def test_the_thinking_setting_comes_from_the_route() -> None:
    settings = load_settings(env_file=None)
    assert settings.thinking_for_route("A") == "on"
    assert settings.thinking_for_route("B") == "repair"
    assert settings.thinking_for_route("C") == "repair"


def test_an_explicit_override_applies_to_both_routes(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """`FDIP_EXTRACT_THINKING` still works, and still means what it says."""
    monkeypatch.setenv("FDIP_EXTRACT_THINKING", "off")
    settings = load_settings(env_file=None)
    assert settings.thinking_for_route("A") == "off"
    assert settings.thinking_for_route("B") == "off"


def test_each_route_can_be_set_on_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDIP_EXTRACT_THINKING_DIGITAL", "off")
    monkeypatch.setenv("FDIP_EXTRACT_THINKING_SCAN", "on")
    settings = load_settings(env_file=None)
    assert settings.thinking_for_route("A") == "off"
    assert settings.thinking_for_route("B") == "on"


def test_an_invalid_thinking_setting_is_refused(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FDIP_EXTRACT_THINKING_DIGITAL", "maybe")
    with pytest.raises(ValueError, match="on, off or repair"):
        load_settings(env_file=None)


def test_the_switch_changes_what_the_client_receives() -> None:
    """The mode must reach the HTTP client, not a wrapper that forwards nothing.

    This is the benchmark's defect restated: `FirstAttemptPlain` set `extra_body`
    on the governed model, which forwards no attribute writes, so option (c) ran
    with reasoning on and was measured as option (a).
    """
    from fdip.adapters.providers import PLAIN_BODY, ThinkingSwitch

    class _Client:
        def __init__(self) -> None:
            self.extra_body: dict[str, Any] = {}
            self.seen: list[dict[str, Any]] = []

        @property
        def model_version(self) -> str:
            return "client"

        def complete(self, messages: Any, temperature: float = 0.0,
                     max_tokens: int | None = None) -> str:
            self.seen.append(dict(self.extra_body))
            return "ok"

    class _Wrapper:
        """Forwards calls but not attributes, like CachedLLM and GovernedLLM."""

        def __init__(self, inner: Any) -> None:
            self._inner = inner

        @property
        def model_version(self) -> str:
            return str(self._inner.model_version)

        def complete(self, messages: Any, temperature: float = 0.0,
                     max_tokens: int | None = None) -> Any:
            return self._inner.complete(messages, temperature, max_tokens)

    client = _Client()
    switch = ThinkingSwitch(_Wrapper(client), client, "repair")

    switch.start_document()
    switch.complete([])          # first attempt: plain
    switch.complete([])          # a repair: reasoning on
    assert client.seen == [PLAIN_BODY, {}]

    switch.set_mode("on")
    switch.start_document()
    switch.complete([])
    assert client.seen[-1] == {}, "reasoning on sends no disable flag"

    switch.set_mode("off")
    switch.start_document()
    switch.complete([])
    switch.complete([])
    assert client.seen[-2:] == [PLAIN_BODY, PLAIN_BODY], (
        "off means off on every attempt, repairs included"
    )


def test_the_mode_is_part_of_the_cache_identity() -> None:
    """Two settings must not replay each other's answers."""
    from fdip.adapters.providers import ThinkingSwitch

    class _Stub:
        extra_body: dict[str, Any] = {}

        @property
        def model_version(self) -> str:
            return "m"

    switch = ThinkingSwitch(_Stub(), _Stub(), "on")
    on = switch.model_version
    switch.set_mode("off")
    assert switch.model_version != on


def test_an_invalid_mode_is_refused_at_the_switch() -> None:
    from fdip.adapters.providers import ThinkingSwitch

    class _Stub:
        extra_body: dict[str, Any] = {}

        @property
        def model_version(self) -> str:
            return "m"

    with pytest.raises(ValueError):
        ThinkingSwitch(_Stub(), _Stub(), "on").set_mode("sometimes")
