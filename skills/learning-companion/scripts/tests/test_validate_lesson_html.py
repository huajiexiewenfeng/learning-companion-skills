import tempfile
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from validate_lesson_html import validate_html


DOCUMENT_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 390px) {.layout { display: block; }} @media (prefers-reduced-motion: reduce) {* { animation: none; }} @media (prefers-color-scheme: dark) {body { color-scheme: dark; }}</style>
</head><body><section class="layout">模型能力</section></body></html>"""

TECHNICAL_VISUAL_HTML = DOCUMENT_HTML.replace(
    "</section>",
    "<svg role=\"img\"><title>交付关系</title><desc>模型能力通向可靠交付</desc><path d=\"M0 0L1 1\" /></svg>可靠交付</section>",
)

HUB_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 390px) {.layout { display: block; }}</style></head>
<body><section class="layout">企业 AI 系统分层</section>
<script id="lesson-data" type="application/json">{"title":"企业 AI 系统分层"}</script>
<script id="lesson-refresh">window.dispatchEvent(new Event("lesson-refresh"));</script>
</body></html>"""


class ValidateLessonHtmlTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "lesson.html"

    def write(self, text, encoding="utf-8"):
        self.path.write_text(text, encoding=encoding)
        return self.path

    def test_document_allows_no_svg_but_rejects_script(self):
        self.assertEqual("passed", validate_html(self.write(DOCUMENT_HTML), (), "document")["overall"])
        bad = DOCUMENT_HTML.replace("</body>", "<script></script></body>")
        self.assertIn("script-forbidden", validate_html(self.write(bad), (), "document")["errors"])

    def test_technical_visual_requires_accessible_svg(self):
        self.assertIn("svg-missing", validate_html(self.write(DOCUMENT_HTML), (), "technical-visual")["errors"])
        self.assertEqual("passed", validate_html(self.write(TECHNICAL_VISUAL_HTML), ("可靠交付",), "technical-visual")["overall"])

    def test_hub_allows_only_exact_scripts(self):
        self.assertEqual("passed", validate_html(self.write(HUB_HTML), ("企业 AI 系统分层",), "hub")["overall"])
        injected = HUB_HTML.replace("</body>", "<script>alert(1)</script></body>")
        self.assertIn("hub-script-not-allowlisted", validate_html(self.write(injected), (), "hub")["errors"])

    def test_document_applies_the_visual_companion_shared_contract(self):
        cases = (
            ("utf8 bom", DOCUMENT_HTML.encode("utf-8-sig"), "utf8-bom"),
            ("iframe", DOCUMENT_HTML.replace("</body>", "<iframe></iframe></body>").encode(), "iframe-forbidden"),
            ("network reference", DOCUMENT_HTML.replace("</body>", "<a href=\"https://example.test\">x</a></body>").encode(), "external-resource-forbidden"),
            ("network code", DOCUMENT_HTML.replace("</body>", "<style>@import url(https://example.test/a.css);</style></body>").encode(), "network-reference-forbidden"),
            ("required term", DOCUMENT_HTML.encode(), "required-term-missing:可靠交付"),
        )
        for name, raw, expected in cases:
            with self.subTest(name=name):
                self.path.write_bytes(raw)
                terms = ("可靠交付",) if name == "required term" else ()
                self.assertIn(expected, validate_html(self.path, terms, "document")["errors"])

    def test_document_checks_svg_accessibility_when_svg_is_present(self):
        incomplete = DOCUMENT_HTML.replace("</section>", "<svg role=\"img\"><title>x</title></svg></section>")
        self.assertIn("svg-accessibility-incomplete", validate_html(self.write(incomplete), (), "document")["errors"])

    def test_hub_requires_one_json_data_script_and_exact_refresh_body(self):
        missing_data = HUB_HTML.replace('<script id="lesson-data" type="application/json">{"title":"企业 AI 系统分层"}</script>', "")
        self.assertIn("hub-data-script-invalid", validate_html(self.write(missing_data), (), "hub")["errors"])
        changed_refresh = HUB_HTML.replace("lesson-refresh\"));", "unexpected\"));")
        self.assertIn("hub-refresh-script-invalid", validate_html(self.write(changed_refresh), (), "hub")["errors"])

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown profile: unknown"):
            validate_html(self.write(DOCUMENT_HTML), (), "unknown")


if __name__ == "__main__":
    unittest.main()
