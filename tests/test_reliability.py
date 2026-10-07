"""B5.4 and B5.5: crash resume, and the files FDIP refuses.

The resume test is the one that justifies `durable_steps` being in the design at
all. It counts AI calls: a replayed run that re-called the model would still
produce the right answer and would still be a serious defect, because the cost
and the latency are the reason the checkpoints exist.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fdip.adapters import providers
from fdip.adapters.db import transaction
from fdip.adapters.repository import ProjectRepository
from fdip.adapters.sandbox import UnsupportedDocument, probe, sniff_mime
from fdip.domain.statuses import ErrorCode
from fdip.pipeline.runner import JobContext, run_job
from fdip.worker import full_template_spec


class _Counting:
    """Wraps the scripted model and counts what actually reached it."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.calls = 0

    @property
    def model_version(self) -> str:
        return str(self._inner.model_version)

    def start_document(self) -> None:
        start = getattr(self._inner, "start_document", None)
        if callable(start):
            start()

    def complete(self, messages: Any, temperature: float = 0.0,
                 max_tokens: int | None = None) -> Any:
        self.calls += 1
        return self._inner.complete(messages, temperature, max_tokens)


def _context(engine: Any, settings: Any, blob: Path, digest: str,
             project_id: str, document_id: str, job_id: str,
             counter: _Counting, fail_after_extract: bool) -> JobContext:
    from fixtures import handler_for

    stack = providers.build_model_stack(settings, handler=handler_for())
    counter._inner = stack.llm  # noqa: SLF001 - the test owns both objects
    stack.llm = counter
    return JobContext(
        engine=engine, settings=settings, models=stack, project_id=project_id,
        document_id=document_id, job_id=job_id, blob_path=str(blob),
        spec=full_template_spec(), purpose="analysis",
        fail_after_extract=fail_after_extract,
    )


def test_a_crash_after_extract_resumes_without_a_second_ai_call(
    engine: Any, settings: Any, pdf: Any
) -> None:
    """B5.4. The run id is the document hash plus the pipeline version (3.9)."""
    from fdip.adapters.seed import seed
    from fdip.adapters.storage import BlobStore, sha256_bytes

    result = seed(engine, settings)
    project_id = str(result.project_id)
    path = pdf("invoice_digital")
    data = path.read_bytes()
    digest = sha256_bytes(data)
    _, blob = BlobStore(settings.blob_dir).put(data)

    with transaction(engine) as connection:
        repo = ProjectRepository(connection, project_id)
        document_id = repo.create_document(
            filename=path.name, mime="application/pdf", byte_size=len(data),
            sha256=digest, blob_path=blob, status="processing", origin="test",
        )
        job_id = repo.create_job(document_id=document_id, run_id=digest[:32],
                                 state="received", mode="test")

    counter = _Counting(None)
    crashed = run_job(_context(engine, settings, Path(blob), digest, project_id,
                               document_id, job_id, counter, True), digest)
    assert crashed["status"] == "failed"
    assert crashed["failed_step"] == "decide"
    assert counter.calls == 1, (
        "exactly one model call: mock mode classifies with the keyword rule, so"
        " extract is the only call that reaches the model"
    )

    # Same run id, fresh objects: this is what a worker restart looks like.
    resumed_counter = _Counting(None)
    resumed = run_job(_context(engine, settings, Path(blob), digest, project_id,
                               document_id, job_id, resumed_counter, False),
                      digest)
    assert resumed["status"] in ("completed", "needs_review"), resumed
    assert resumed.get("extraction_id")
    assert resumed_counter.calls == 0, (
        "the resumed run must replay the classify and extract checkpoints, not "
        "call the model again; it made %d call(s)" % resumed_counter.calls
    )


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("empty.pdf", b"", ErrorCode.EMPTY_FILE.value),
        ("corrupt.pdf", b"%PDF-1.4\nnot a pdf at all\n%%EOF",
         ErrorCode.CORRUPT_FILE.value),
        ("text.txt", b"just some text", ErrorCode.UNSUPPORTED_FILE_TYPE.value),
        ("sheet.xlsx", b"PK\x03\x04rubbish", ErrorCode.UNSUPPORTED_FILE_TYPE.value),
    ],
)
def test_a_bad_file_is_refused_with_a_code(
    client: Any, tmp_path: Path, name: str, content: bytes, code: str
) -> None:
    """B5.5. Each refusal carries an RFC 9457 `code` the UI can switch on."""
    path = tmp_path / name
    path.write_bytes(content)
    with path.open("rb") as handle:
        response = client.post(
            "/v1/documents",
            files={"file": (name, handle, "application/octet-stream")},
        )
    if response.status_code == 202:
        # Accepted at upload because the magic bytes looked right; the worker must
        # then refuse it. A corrupt PDF is only detectable by opening it.
        from fdip.worker import drain

        document_id = response.json()["document_id"]
        drain(client.app.state.fdip.engine, client.app.state.fdip.settings)
        document = client.get("/v1/documents/%s" % document_id).json()
        assert document["status"] == "unsupported", document
        assert document["error_code"] == code, document
        return
    assert response.status_code in (413, 415), response.text
    assert response.json()["code"] == code, response.text


def test_an_over_limit_file_is_refused_before_it_is_stored(
    client: Any, tmp_path: Path, settings: Any
) -> None:
    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-1.4\n" + b"0" * (settings.max_upload_bytes + 1))
    with big.open("rb") as handle:
        response = client.post("/v1/documents",
                               files={"file": ("big.pdf", handle, "application/pdf")})
    assert response.status_code == 413
    assert response.json()["code"] == ErrorCode.FILE_TOO_LARGE.value


def test_an_encrypted_pdf_is_poison_and_never_retried() -> None:
    """The code, and that it is in the poison set: a retry cannot help."""
    from fdip.domain.statuses import POISON_CODES

    assert ErrorCode.ENCRYPTED_PDF.value in POISON_CODES
    assert ErrorCode.CORRUPT_FILE.value in POISON_CODES
    assert ErrorCode.PAGE_LIMIT_EXCEEDED.value in POISON_CODES
    # A timeout and a 429 are not poison: those are worth retrying.
    assert ErrorCode.PROVIDER_UNAVAILABLE.value not in POISON_CODES


def test_a_document_over_the_page_limit_is_refused(tmp_path: Path) -> None:
    """Probed in the parent, before a child process is spawned for it."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fixtures import BY_NAME, write_pdf

    path = write_pdf(tmp_path / "one.pdf", BY_NAME["invoice_digital"])
    report = probe(str(path), max_pages=25)
    assert report.page_count == 1
    assert report.route == "A", "a PDF with a text layer is route A"

    with pytest.raises(UnsupportedDocument) as caught:
        probe(str(path), max_pages=0)
    assert caught.value.code == ErrorCode.PAGE_LIMIT_EXCEEDED.value


def test_magic_bytes_decide_the_type_not_the_extension() -> None:
    """The extension is the attacker-controlled part, so it never decides."""
    assert sniff_mime(b"%PDF-1.4\n", "invoice.png") == "application/pdf"
    assert sniff_mime(b"\x89PNG\r\n\x1a\n", "invoice.pdf") == "image/png"
    with pytest.raises(UnsupportedDocument):
        sniff_mime(b"MZ\x90\x00", "invoice.pdf")


def test_the_sandbox_really_runs_in_another_process(tmp_path: Path) -> None:
    """The subprocess path, exercised once; the rest of the suite runs inline."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fixtures import BY_NAME, write_pdf

    from fdip.adapters.sandbox import parse_document

    path = write_pdf(tmp_path / "sandboxed.pdf", BY_NAME["invoice_digital"])
    payload = parse_document(str(path), "A", timeout=120.0)
    assert payload["ok"] is True
    assert len(payload["words"]) > 50
    assert payload["page_sizes"]["1"] == [595.0, 842.0]
