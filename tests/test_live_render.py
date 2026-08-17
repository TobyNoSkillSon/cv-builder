from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from cv_builder.cli import _new
from cv_builder.pipeline import build


@unittest.skipUnless(os.environ.get("CV_BUILDER_LIVE_RENDER") == "1", "live Chromium test disabled")
class LiveRenderTests(unittest.TestCase):
    def test_new_edit_build_with_real_chromium(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            created = _new("Example Company", "Operations Assistant", root)
            app = Path(created["app"])
            (app / "offer.md").write_text("# Offer\n\nExample vacancy text.\n", encoding="utf-8")
            (app / "cv.html").write_text(
                '''<!doctype html>
<html><head><meta charset="utf-8"><link rel="stylesheet" href="cv.css"></head>
<body><main class="page"><header><h1 data-cv-applicant>Applicant Example</h1>
<address><a href="mailto:applicant@example.com">applicant@example.com</a>
<a href="tel:+10000000000">+1 000 000 0000</a></address></header>
<section><h2>Profile</h2><p>Operations support profile with verified example content.</p></section>
<footer>Recruitment consent text.</footer></main></body></html>''',
                encoding="utf-8",
            )
            result = build(app, downloads_dir=root / "Downloads", open_document=False)
            self.assertEqual(result["iteration"], 1)
            self.assertTrue(Path(result["pdf"]).is_file())
            self.assertTrue(Path(result["preview"]).is_file())
            self.assertTrue((app / "iterations/cv-001.html").is_file())
            self.assertEqual(len(result["pages"]), 1)


if __name__ == "__main__":
    unittest.main()
