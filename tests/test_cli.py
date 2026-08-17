from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pymupdf as fitz

from cv_builder.cli import main, parser
from cv_builder.config import AppConfig, ConfigError, application_name, load_config, slugify, write_config
from cv_builder.pipeline import BuildError, _ApplicantParser, _configure_private_browser, _open_document, _snapshot, build
from cv_builder.verification import verify_pdf


def make_pdf(
    path: Path,
    *,
    applicant: str = "Applicant Example",
    phrase: str = "Operations profile",
    include_phone: bool = True,
    tiny: bool = False,
) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((50, 50), applicant, fontsize=11)
    page.insert_text((50, 80), phrase, fontsize=4 if tiny else 10)
    page.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(50, 90, 180, 105), "uri": "mailto:applicant@example.com"})
    if include_phone:
        page.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(50, 110, 180, 125), "uri": "tel:+10000000000"})
    document.save(path)
    document.close()


def complete_html(applicant: str = "Applicant Example") -> str:
    return f'''<!doctype html>
<html><head><link rel="stylesheet" href="cv.css"></head>
<body><main class="page"><h1 data-cv-applicant>{applicant}</h1>
<a href="mailto:applicant@example.com">applicant@example.com</a>
<a href="tel:+10000000000">+1 000 000 0000</a>
<p>Operations profile</p></main></body></html>'''


def make_app(root: Path, *, applicant: str = "Applicant Example") -> Path:
    app = root / "Example-Company-Operations-Assistant"
    app.mkdir()
    (app / "iterations").mkdir()
    (app / "offer.md").write_text("# Offer\n\nExample vacancy\n", encoding="utf-8")
    (app / "cv.html").write_text(complete_html(applicant), encoding="utf-8")
    (app / "cv.css").write_text("@page { size: A4; margin: 0; }", encoding="utf-8")
    write_config(app, AppConfig("Example Company", "Operations Assistant"))
    return app


class ConfigTests(unittest.TestCase):
    def test_slugify_and_application_name(self):
        self.assertEqual(slugify("Example & Partners — Łódź"), "Example-Partners-Lodz")
        self.assertEqual(application_name("Example Company", "Operations Assistant"), "Example-Company-Operations-Assistant")

    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp)
            expected = AppConfig("Example Company", "Operations Assistant")
            write_config(app, expected)
            self.assertEqual(load_config(app), expected)

    def test_config_rejects_empty_values_and_overwrite(self):
        with self.assertRaises(ConfigError):
            AppConfig.from_dict({"employer": "", "role": "Role"})
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp)
            write_config(app, AppConfig("Company", "Role"))
            with self.assertRaises(ConfigError):
                write_config(app, AppConfig("Other", "Role"))


class VerificationTests(unittest.TestCase):
    def test_good_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "good.pdf"
            make_pdf(pdf)
            report = verify_pdf(pdf, applicant_name="Applicant Example")
            self.assertTrue(report["ok"], report["failures"])

    def test_missing_phone_link_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "bad.pdf"
            make_pdf(pdf, include_phone=False)
            report = verify_pdf(pdf, applicant_name="Applicant Example")
            self.assertFalse(report["ok"])
            self.assertTrue(any("tel:" in failure for failure in report["failures"]))

    def test_microscopic_text_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "tiny.pdf"
            make_pdf(pdf, tiny=True)
            report = verify_pdf(pdf, applicant_name="Applicant Example")
            self.assertFalse(report["ok"])
            self.assertTrue(report["suspicious_spans"])


class SnapshotTests(unittest.TestCase):
    def test_snapshot_is_exact_and_increments(self):
        with tempfile.TemporaryDirectory() as temp:
            app = make_app(Path(temp))
            html = app / "cv.html"
            first_number, first = _snapshot(html, app / "iterations")
            self.assertEqual(first_number, 1)
            self.assertEqual(first.read_bytes(), html.read_bytes())
            html.write_text(complete_html().replace("Operations profile", "Revised profile"), encoding="utf-8")
            second_number, second = _snapshot(html, app / "iterations")
            self.assertEqual(second_number, 2)
            self.assertIn("Revised profile", second.read_text(encoding="utf-8"))

    def test_snapshot_rejects_symlinked_iterations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            app.mkdir()
            html = app / "cv.html"
            html.write_text(complete_html(), encoding="utf-8")
            outside = root / "outside"
            outside.mkdir()
            (app / "iterations").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(BuildError, "unsafe iterations"):
                _snapshot(html, app / "iterations")


class PipelineTests(unittest.TestCase):
    def test_build_snapshots_overwrites_stable_outputs_and_opens(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_app(root)
            downloads = root / "Downloads"

            with mock.patch("cv_builder.pipeline._render", side_effect=lambda _html, pdf: make_pdf(pdf)), mock.patch("cv_builder.pipeline._open_document", return_value=None) as opened:
                first = build(app, downloads_dir=downloads)
                (app / "cv.html").write_text(complete_html().replace("Operations profile", "Revised profile"), encoding="utf-8")
                second = build(app, downloads_dir=downloads)

            self.assertEqual(first["iteration"], 1)
            self.assertEqual(second["iteration"], 2)
            self.assertTrue((app / "iterations/cv-001.html").is_file())
            self.assertTrue((app / "iterations/cv-002.html").is_file())
            self.assertTrue((app / "cv-preview.png").is_file())
            self.assertEqual(Path(second["pdf"]).name, "Applicant Example CV.pdf")
            self.assertEqual(opened.call_count, 2)

    def test_unresolved_placeholders_block_snapshot_and_render(self):
        with tempfile.TemporaryDirectory() as temp:
            app = make_app(Path(temp))
            (app / "cv.html").write_text(complete_html().replace("Operations profile", "[[PROFILE]]"), encoding="utf-8")
            with mock.patch("cv_builder.pipeline._render") as render:
                with self.assertRaisesRegex(BuildError, "unresolved CV placeholders"):
                    build(app, downloads_dir=Path(temp) / "Downloads", open_document=False)
            render.assert_not_called()
            self.assertEqual(list((app / "iterations").iterdir()), [])

    def test_offer_placeholder_blocks_build(self):
        with tempfile.TemporaryDirectory() as temp:
            app = make_app(Path(temp))
            (app / "offer.md").write_text("[[PASTE_JOB_DESCRIPTION_HERE]]", encoding="utf-8")
            with mock.patch("cv_builder.pipeline._render") as render:
                with self.assertRaisesRegex(BuildError, "offer.md"):
                    build(app, downloads_dir=Path(temp) / "Downloads", open_document=False)
            render.assert_not_called()

    def test_active_html_and_remote_css_are_rejected(self):
        cases = (
            complete_html().replace("</main>", "<script>alert(1)</script></main>"),
            complete_html().replace("<p>Operations profile</p>", '<p onclick="alert(1)">Operations profile</p>'),
        )
        for source in cases:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temp:
                app = make_app(Path(temp))
                (app / "cv.html").write_text(source, encoding="utf-8")
                with self.assertRaises(BuildError):
                    build(app, downloads_dir=Path(temp) / "Downloads", open_document=False)
        with tempfile.TemporaryDirectory() as temp:
            app = make_app(Path(temp))
            (app / "cv.css").write_text('@import url("https://example.com/tracker.css");', encoding="utf-8")
            with self.assertRaisesRegex(BuildError, "remote resource"):
                build(app, downloads_dir=Path(temp) / "Downloads", open_document=False)

    def test_applicant_parser_handles_void_elements(self):
        parser = _ApplicantParser()
        parser.feed("<h1 data-cv-applicant>Applicant<br>Example</h1><p>Outside</p>")
        self.assertEqual(parser.applicant, "Applicant Example")

    def test_verification_failure_preserves_existing_download(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_app(root)
            downloads = root / "Downloads"
            downloads.mkdir()
            destination = downloads / "Applicant Example CV.pdf"
            destination.write_bytes(b"previous verified PDF")
            with mock.patch("cv_builder.pipeline._render", side_effect=lambda _html, pdf: make_pdf(pdf, include_phone=False)):
                with self.assertRaisesRegex(BuildError, "verification failed"):
                    build(app, downloads_dir=downloads, open_document=False)
            self.assertEqual(destination.read_bytes(), b"previous verified PDF")
            self.assertTrue((app / "iterations/cv-001.html").is_file())

    def test_unsafe_applicant_filename_characters_are_sanitized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_app(root, applicant="Applicant: Example")
            with mock.patch("cv_builder.pipeline._render", side_effect=lambda _html, pdf: make_pdf(pdf, applicant="Applicant: Example")):
                result = build(app, downloads_dir=root / "Downloads", open_document=False)
            self.assertEqual(Path(result["pdf"]).name, "Applicant- Example CV.pdf")

    def test_private_browser_path_overrides_ambient_shared_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "browsers"
            private.mkdir()
            with mock.patch("cv_builder.pipeline.data_root", return_value=root), mock.patch.dict(
                os.environ, {"PLAYWRIGHT_BROWSERS_PATH": "/shared/browser/cache"}
            ):
                _configure_private_browser()
                self.assertEqual(os.environ["PLAYWRIGHT_BROWSERS_PATH"], str(private))

    def test_viewer_failure_returns_warning_without_failing_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_app(root)
            warning = "PDF was built successfully but could not be opened automatically."
            with mock.patch("cv_builder.pipeline._render", side_effect=lambda _html, pdf: make_pdf(pdf)), mock.patch("cv_builder.pipeline._open_document", return_value=warning):
                result = build(app, downloads_dir=root / "Downloads")
            self.assertTrue(result["ok"])
            self.assertEqual(result["warning"], warning)
            self.assertTrue(Path(result["pdf"]).is_file())

    def test_linux_viewer_warning_suggests_probable_causes(self):
        with mock.patch("cv_builder.pipeline.sys.platform", "linux"), mock.patch(
            "cv_builder.pipeline.subprocess.run", side_effect=FileNotFoundError("xdg-open")
        ):
            warning = _open_document(Path("/tmp/Applicant CV.pdf"))
        self.assertIn("xdg-open is unavailable", warning or "")
        self.assertIn("no default PDF viewer", warning or "")
        self.assertIn("no graphical session", warning or "")

    def test_windows_viewer_warning_suggests_file_association(self):
        pdf = Path("Applicant CV.pdf")
        with mock.patch("cv_builder.pipeline.sys.platform", "win32"), mock.patch(
            "cv_builder.pipeline.os.name", "nt"
        ), mock.patch.object(os, "startfile", create=True, side_effect=OSError("no association")):
            warning = _open_document(pdf)
        self.assertIn("no default PDF application association", warning or "")
        self.assertIn("Open it manually", warning or "")


class CLITests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_public_parser_has_only_new_and_build(self):
        root = parser()
        subparsers = next(action for action in root._actions if isinstance(action, __import__("argparse")._SubParsersAction))
        self.assertEqual(set(subparsers.choices), {"new", "build"})

    def test_new_creates_complete_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            previous = Path.cwd()
            os.chdir(temp)
            try:
                code, output, error = self.run_cli(["new", "Example Company", "Operations Assistant"])
            finally:
                os.chdir(previous)
            self.assertEqual(code, 0, error)
            app = Path(temp) / "Example-Company-Operations-Assistant"
            self.assertIn("NEW", output)
            for relative in ("offer.md", "cv.html", "cv.css", ".cv-builder.json", "iterations"):
                self.assertTrue((app / relative).exists(), relative)
            self.assertFalse((app / "requirements-matrix.md").exists())

    def test_build_uses_current_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            app = make_app(Path(temp))
            previous = Path.cwd()
            os.chdir(app)
            try:
                with mock.patch("cv_builder.cli.build", return_value={"ok": True, "pdf": "/tmp/CV.pdf"}) as called:
                    code, _, error = self.run_cli(["build"])
            finally:
                os.chdir(previous)
            self.assertEqual(code, 0, error)
            called.assert_called_once_with(app.resolve())


if __name__ == "__main__":
    unittest.main()
