from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path

import pymupdf as fitz

from .config import load_config
from .paths import data_root
from .verification import verify_pdf

_PLACEHOLDER = re.compile(r"\[\[[^\[\]\n]+\]\]")
_ITERATION = re.compile(r"^cv-(\d+)\.html$")


class BuildError(RuntimeError):
    pass


class _ApplicantParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_applicant = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        folded = tag.casefold()
        if self.in_applicant and folded == "br":
            self.parts.append(" ")
        elif folded == "h1" and any(name == "data-cv-applicant" for name, _ in attrs):
            self.in_applicant = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "h1":
            self.in_applicant = False

    def handle_data(self, data: str) -> None:
        if self.in_applicant:
            self.parts.append(data)

    @property
    def applicant(self) -> str:
        return " ".join("".join(self.parts).split())


def _reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise BuildError(f"refusing symlink for {label}: {path}")


def _atomic_write(path: Path, data: bytes) -> None:
    _reject_symlink(path, "output")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _build_lock(app: Path):
    lock = app / ".cv-builder.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise BuildError(f"application is already being built, or has a stale lock: {lock}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.close(descriptor)
        yield
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        lock.unlink(missing_ok=True)


def _validate_source(app: Path) -> tuple[Path, Path, str]:
    offer = app / "offer.md"
    html = app / "cv.html"
    css = app / "cv.css"
    for path in (offer, html, css):
        if not path.is_file() or path.is_symlink():
            raise BuildError(f"missing or unsafe source file: {path}")
    offer_text = offer.read_text(encoding="utf-8")
    if "[[PASTE_JOB_DESCRIPTION_HERE]]" in offer_text or not offer_text.strip():
        raise BuildError("offer.md must contain the vacancy text before build")
    text = html.read_text(encoding="utf-8")
    css_text = css.read_text(encoding="utf-8")
    placeholders = sorted(set(_PLACEHOLDER.findall(text)))
    if placeholders:
        sample = ", ".join(placeholders[:8])
        suffix = " ..." if len(placeholders) > 8 else ""
        raise BuildError(f"unresolved CV placeholders: {sample}{suffix}")
    expected_link = '<link rel="stylesheet" href="cv.css">'
    if text.count(expected_link) != 1:
        raise BuildError(f"cv.html must contain exactly one {expected_link!r}")
    if re.search(r"<\s*(script|iframe|object|embed|base)\b", text, re.IGNORECASE):
        raise BuildError("cv.html contains active or embeddable content")
    if re.search(r"\son[a-z]+\s*=", text, re.IGNORECASE):
        raise BuildError("cv.html contains an inline event handler")
    if re.search(r"<\s*(img|audio|video|source)\b[^>]*\bsrc\s*=\s*['\"]\s*(?:https?:)?//", text, re.IGNORECASE):
        raise BuildError("cv.html contains a remote media resource")
    if re.search(r"@import\b|url\(\s*['\"]?\s*(?:https?:)?//", css_text, re.IGNORECASE):
        raise BuildError("cv.css contains a remote resource")
    parser = _ApplicantParser()
    parser.feed(text)
    applicant = parser.applicant
    if not applicant:
        raise BuildError("cv.html must contain the applicant name inside <h1 data-cv-applicant>")
    return html, css, applicant


def _safe_filename_name(applicant: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", applicant)
    cleaned = " ".join(cleaned.split()).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        raise BuildError("applicant name cannot produce a safe PDF filename")
    return cleaned


def _next_iteration(iterations: Path) -> tuple[int, Path]:
    if not iterations.is_dir() or iterations.is_symlink():
        raise BuildError(f"missing or unsafe iterations directory: {iterations}")
    numbers = [int(match.group(1)) for path in iterations.iterdir() if (match := _ITERATION.fullmatch(path.name))]
    number = max(numbers, default=0) + 1
    path = iterations / f"cv-{number:03d}.html"
    _reject_symlink(path, "iteration")
    if path.exists():
        raise BuildError(f"refusing to overwrite iteration: {path}")
    return number, path


def _snapshot(html: Path, iterations: Path) -> tuple[int, Path]:
    number, destination = _next_iteration(iterations)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(html.read_bytes())
        handle.flush()
        os.fsync(handle.fileno())
    return number, destination


def _configure_private_browser() -> None:
    private_browsers = data_root() / "browsers"
    if private_browsers.is_dir():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(private_browsers)


def _render(html: Path, pdf: Path) -> None:
    _configure_private_browser()
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BuildError("Playwright is not installed; install the project dependencies first") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(java_script_enabled=False)
                context.set_offline(True)
                page = context.new_page()
                page.goto(f"{html.as_uri()}?build={uuid.uuid4().hex}", wait_until="load")
                page.pdf(
                    path=str(pdf),
                    print_background=True,
                    prefer_css_page_size=True,
                    display_header_footer=False,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise BuildError(
            "Chromium rendering failed. Install it with: python -m playwright install chromium\n"
            f"{exc}"
        ) from exc
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise BuildError("Chromium did not produce a PDF")


def _preview_png(pdf: Path) -> bytes:
    with fitz.open(pdf) as document:
        if not document:
            raise BuildError("rendered PDF contains no pages")
        return document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")


def _open_document(path: Path) -> str | None:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Preview", str(path)], check=True)
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        if os.name == "nt":
            probable_cause = "Windows has no default PDF application association, or the viewer launch was blocked"
        elif sys.platform == "darwin":
            probable_cause = "Preview is unavailable, or macOS refused the open request"
        else:
            probable_cause = "xdg-open is unavailable, no default PDF viewer is configured, or there is no graphical session"
        return (
            f"PDF was built successfully but could not be opened automatically. "
            f"Most probable cause: {probable_cause}. Open it manually: {path}. Error: {exc}"
        )
    return None


def build(
    app: Path | None = None,
    *,
    downloads_dir: Path | None = None,
    open_document: bool = True,
) -> dict[str, object]:
    app = (app or Path.cwd()).resolve()
    if not app.is_dir():
        raise BuildError(f"application directory does not exist: {app}")
    load_config(app)
    html, _css, applicant = _validate_source(app)
    iterations = app / "iterations"

    with _build_lock(app):
        iteration, snapshot = _snapshot(html, iterations)
        temporary_pdf = app / f".cv-builder-render-{uuid.uuid4().hex}.pdf"
        try:
            _render(html, temporary_pdf)
            report = verify_pdf(temporary_pdf, applicant_name=applicant)
            if not report["ok"]:
                failures = "; ".join(str(item) for item in report["failures"])
                raise BuildError(f"PDF verification failed: {failures}")
            preview = app / "cv-preview.png"
            _atomic_write(preview, _preview_png(temporary_pdf))
            destination_dir = (downloads_dir or (Path.home() / "Downloads")).expanduser().resolve()
            destination = destination_dir / f"{_safe_filename_name(applicant)} CV.pdf"
            _atomic_write(destination, temporary_pdf.read_bytes())
        finally:
            temporary_pdf.unlink(missing_ok=True)

    warning = _open_document(destination) if open_document else None
    result: dict[str, object] = {
        "ok": True,
        "iteration": iteration,
        "snapshot": str(snapshot),
        "pdf": str(destination),
        "preview": str(preview),
        "sha256": report["sha256"],
        "pages": report["pages"],
        "links": report["links"],
    }
    if warning:
        result["warning"] = warning
    return result
