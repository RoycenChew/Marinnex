"""Probe, parse and OCR, run in a child process with a wall-clock timeout.

Parsing is the one stage that runs attacker-supplied bytes through C libraries,
so it runs somewhere a crash or a hang cannot take the worker with it. A
malformed PDF that segfaults pdfium kills the child and becomes
`corrupt_file`; one that loops forever is killed at the timeout and becomes the
same.

Two Windows-specific facts shape the implementation:

* `multiprocessing` uses **spawn**, not fork, so the child re-imports this module
  and every argument must be picklable. That is why the worker function is
  top-level and takes a path and a dict rather than a closure.
* There is **no `setrlimit`**, so the memory cap is best effort. The page limit
  and the byte limit are the real defences here; a true memory sandbox needs a
  job object or a container and is deferred to Phase 4.
"""
from __future__ import annotations

import multiprocessing
import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fdip.domain.statuses import ErrorCode

PDF_MAGIC = b"%PDF-"
IMAGE_MAGICS: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
)

TEXT_COVERAGE_FOR_TEXT_LAYER = 0.10
"""Below this share of pages carrying words, a PDF is treated as a scan. Low on
purpose: a mostly-image invoice with a stray text watermark must still go to OCR,
and OCR on a page that did have text costs accuracy but not correctness."""


class UnsupportedDocument(Exception):
    """A file FDIP refuses, with the code the API will return. Never retried.

    The code is part of the message, not only an attribute. A step that raises
    this is wrapped by the durable runner into a run failure carrying a formatted
    string, so an attribute alone is lost and every refused file arrives as a
    generic `internal` error -- which is then retried and reported wrongly.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__("%s: %s" % (code, message))
        self.code = code
        self.reason = message


@dataclass
class ProbeReport:
    mime: str
    page_count: int
    encrypted: bool = False
    pages: list[dict[str, Any]] = field(default_factory=list)
    route: str = "A"

    @property
    def page_sizes(self) -> dict[str, list[float]]:
        return {
            str(page["page_number"]): [page["width"], page["height"]]
            for page in self.pages
        }


def sniff_mime(data: bytes, filename: str = "") -> str:
    """Magic bytes first, extension only as a tiebreak.

    The extension is the attacker-controlled part, so it never decides.
    """
    if data.startswith(PDF_MAGIC):
        return "application/pdf"
    for magic, mime in IMAGE_MAGICS:
        if data.startswith(magic):
            return mime
    suffix = Path(filename).suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        return "image/" + suffix.lstrip(".").replace("jpg", "jpeg").replace(
            "tif", "tiff"
        )
    raise UnsupportedDocument(
        ErrorCode.UNSUPPORTED_FILE_TYPE.value,
        "only PDF, PNG, JPEG and TIFF files are accepted",
    )


def probe(path: str, max_pages: int) -> ProbeReport:
    """Stage 2, in the parent: cheap, and its answer decides the route.

    Opening the document here means a corrupt or encrypted file is rejected
    before a child process is spawned for it.
    """
    data = Path(path).read_bytes()
    if not data:
        raise UnsupportedDocument(ErrorCode.EMPTY_FILE.value, "the file is empty")
    mime = sniff_mime(data, path)

    if mime != "application/pdf":
        try:
            import pypdfium2 as pdfium

            bitmap = pdfium.PdfBitmap  # noqa: F841  (import check only)
        except ImportError:  # pragma: no cover - dependency is declared
            pass
        return ProbeReport(mime=mime, page_count=1, route="B", pages=[{
            "page_number": 1, "width": 612.0, "height": 792.0, "rotation": 0,
            "route": "B", "text_coverage": 0.0, "word_count": 0,
        }])

    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as error:
        message = str(error).lower()
        if "password" in message or "encrypt" in message:
            raise UnsupportedDocument(
                ErrorCode.ENCRYPTED_PDF.value,
                "the PDF is password protected, so its text cannot be read",
            ) from error
        raise UnsupportedDocument(
            ErrorCode.CORRUPT_FILE.value, "the PDF could not be opened"
        ) from error
    except Exception as error:
        raise UnsupportedDocument(
            ErrorCode.CORRUPT_FILE.value, "the PDF could not be opened"
        ) from error

    try:
        count = len(document)
        if count == 0:
            raise UnsupportedDocument(
                ErrorCode.CORRUPT_FILE.value, "the PDF has no pages"
            )
        if count > max_pages:
            raise UnsupportedDocument(
                ErrorCode.PAGE_LIMIT_EXCEEDED.value,
                "the document has %d pages and the limit is %d" % (count, max_pages),
            )
        pages = []
        with_text = 0
        for index in range(count):
            page = document[index]
            width, height = page.get_size()
            try:
                characters = len(page.get_textpage().get_text_bounded().strip())
            except Exception:
                characters = 0
            if characters > 40:
                with_text += 1
            pages.append({
                "page_number": index + 1,
                "width": float(width),
                "height": float(height),
                "rotation": int(page.get_rotation() or 0),
                "text_coverage": 1.0 if characters > 40 else 0.0,
                "word_count": 0,
                "route": "A" if characters > 40 else "B",
            })
        share = with_text / count
        route = "A" if share >= TEXT_COVERAGE_FOR_TEXT_LAYER else "B"
        return ProbeReport(mime="application/pdf", page_count=count,
                           pages=pages, route=route)
    finally:
        document.close()


def _parse_in_child(path: str, route: str, queue: Any) -> None:
    """Runs in the child. Puts a serialisable dict or an error on the queue.

    It must not raise out of here: an exception in a child is a traceback on
    stderr that the parent cannot see, which is indistinguishable from a hang.
    """
    try:
        from toolkit.adapters import PdfPlumberSource, TesseractSource

        source = TesseractSource() if route == "B" else PdfPlumberSource()
        document = source.load(path)
        queue.put({
            "ok": True,
            "doc_id": document.doc_id,
            "page_count": document.page_count,
            "text": "\n".join(block.text for block in document.blocks),
            "page_sizes": {
                str(page): [float(size[0]), float(size[1])]
                for page, size in document.page_sizes.items()
            },
            "words": [
                {
                    "text": word.text,
                    "page": word.page,
                    "bbox": [float(word.bbox.x0), float(word.bbox.y0),
                             float(word.bbox.x1), float(word.bbox.y1)],
                    "confidence": word.confidence,
                    "source": word.source.value,
                }
                for word in document.words
            ],
        })
    except BaseException as error:  # noqa: BLE001 - the child must never escape
        # The type *and* the message. A bare type name turns every defect in this
        # function into an indistinguishable `corrupt_file`, which is how a
        # TypeError in the serialisation above spent an afternoon looking like a
        # bad PDF. The message reaches `jobs.error_detail`, never the log stream.
        queue.put({
            "ok": False,
            "error": type(error).__name__,
            "message": str(error)[:400],
            "traceback": traceback.format_exc()[-1500:],
        })


def parse_document(path: str, route: str, timeout: float = 60.0) -> dict[str, Any]:
    """Stage 4, in a child process. Raises `UnsupportedDocument` on a bad file."""
    context = multiprocessing.get_context("spawn")
    queue: Any = context.Queue(maxsize=1)
    child = context.Process(
        target=_parse_in_child, args=(path, route, queue), daemon=True
    )
    child.start()
    try:
        try:
            payload = queue.get(timeout=timeout)
        except Exception as error:
            # Empty queue after the timeout: the child hung or died silently.
            raise UnsupportedDocument(
                ErrorCode.CORRUPT_FILE.value,
                "parsing did not finish within %.0f seconds" % timeout,
            ) from error
    finally:
        child.join(timeout=5)
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)

    if not payload.get("ok"):
        name = str(payload.get("error", ""))
        if name == "MissingDependency":
            raise RuntimeError(
                "a parser is not installed: %s" % payload.get("message", "")
            )
        raise UnsupportedDocument(
            ErrorCode.CORRUPT_FILE.value,
            "the document could not be parsed (%s: %s)"
            % (name, payload.get("message", "")),
        )
    return payload


def parse_inline(path: str, route: str) -> dict[str, Any]:
    """The same work in-process, for tests and for `FDIP_SANDBOX=0`.

    Spawning a process per document costs about a second on Windows, which is
    noise next to a model call but not next to a test suite.
    """
    context_queue: list[dict[str, Any]] = []

    class _Sink:
        def put(self, value: dict[str, Any]) -> None:
            context_queue.append(value)

    _parse_in_child(path, route, _Sink())
    payload = context_queue[0]
    if not payload.get("ok"):
        raise UnsupportedDocument(
            ErrorCode.CORRUPT_FILE.value,
            "the document could not be parsed (%s: %s)"
            % (payload.get("error", ""), payload.get("message", "")),
        )
    return payload


def use_sandbox() -> bool:
    return os.environ.get("FDIP_SANDBOX", "1").strip().lower() not in ("0", "false")


def render_page_png(path: str, page_number: int, dpi: int = 150) -> bytes:
    """One page as a PNG, for the UI's box overlay.

    The scale factor and the DPI are the contract the UI depends on: boxes are in
    PDF points and the image is `dpi / 72` times that, so the UI multiplies by
    `image_width / page_width`. Changing the DPI here without saying so moves
    every box in the UI.
    """
    import io

    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(path)
    try:
        if page_number < 1 or page_number > len(document):
            raise UnsupportedDocument(
                ErrorCode.NOT_FOUND.value, "page %d does not exist" % page_number
            )
        page = document[page_number - 1]
        bitmap = page.render(scale=dpi / 72.0)
        buffer = io.BytesIO()
        bitmap.to_pil().save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        document.close()


__all__ = [
    "IMAGE_MAGICS",
    "PDF_MAGIC",
    "ProbeReport",
    "TEXT_COVERAGE_FOR_TEXT_LAYER",
    "UnsupportedDocument",
    "parse_document",
    "parse_inline",
    "probe",
    "render_page_png",
    "sniff_mime",
    "use_sandbox",
]
