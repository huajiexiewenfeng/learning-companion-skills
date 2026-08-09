import json
import os
import subprocess
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
    "<svg role=\"img\"><title>交付关系</title><desc>模型能力通向可靠交付</desc><g data-node-id=\"model\"></g><g data-node-id=\"delivery\"></g><path data-edge-from=\"model\" data-edge-to=\"delivery\" d=\"M0 0L1 1\" /></svg>可靠交付</section>",
)

HUB_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 390px) {.layout { display: block; }} @media (prefers-reduced-motion: reduce) {* { animation: none; }} @media (prefers-color-scheme: dark) {body { color-scheme: dark; }}</style></head>
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

    def test_document_accepts_html_void_tag_syntax(self):
        xhtml_void = DOCUMENT_HTML.replace('<meta charset="utf-8">', '<meta charset="utf-8" />')
        self.assertEqual("passed", validate_html(self.write(xhtml_void), (), "document")["overall"])

    def test_hub_requires_one_json_data_script_and_exact_refresh_body(self):
        missing_data = HUB_HTML.replace('<script id="lesson-data" type="application/json">{"title":"企业 AI 系统分层"}</script>', "")
        self.assertIn("hub-data-script-invalid", validate_html(self.write(missing_data), (), "hub")["errors"])
        changed_refresh = HUB_HTML.replace("lesson-refresh\"));", "unexpected\"));")
        self.assertIn("hub-refresh-script-invalid", validate_html(self.write(changed_refresh), (), "hub")["errors"])

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown profile: unknown"):
            validate_html(self.write(DOCUMENT_HTML), (), "unknown")

    def test_hub_requires_dark_mode_and_reduced_motion(self):
        missing_preferences = HUB_HTML.replace(
            " @media (prefers-reduced-motion: reduce) {* { animation: none; }} @media (prefers-color-scheme: dark) {body { color-scheme: dark; }}",
            "",
        )
        errors = validate_html(self.write(missing_preferences), (), "hub")["errors"]
        self.assertIn("reduced-motion-rule-missing", errors)
        self.assertIn("color-scheme-rule-missing", errors)

    def test_malformed_html_fails_closed(self):
        cases = (
            ("unclosed root", DOCUMENT_HTML.replace("</body></html>", "</body>")),
            ("misnested tag", DOCUMENT_HTML.replace("模型能力", "<b>模型能力</i>")),
            ("unclosed svg", TECHNICAL_VISUAL_HTML.replace("</svg>", "")),
            ("unclosed script", HUB_HTML.replace("</script>\n</body>", "\n</body>", 1)),
            ("bad ordering", DOCUMENT_HTML.replace("</head><body>", "</head></html><body>")),
            ("duplicate attribute", DOCUMENT_HTML.replace('class="layout"', 'class="layout" class="again"')),
        )
        for name, markup in cases:
            with self.subTest(name=name):
                self.assertIn("malformed-html", validate_html(self.write(markup), (), "hub" if name == "unclosed script" else "document")["errors"])

    def test_rejects_events_and_executable_or_nonlocal_resource_urls(self):
        cases = (
            ("event handler", DOCUMENT_HTML.replace("<body>", "<body onload=\"alert(1)\">"), "event-handler-forbidden"),
            ("javascript url", DOCUMENT_HTML.replace("</body>", '<a href="java&#x0a;script:alert(1)">x</a></body>'), "executable-url-forbidden"),
            ("file url", DOCUMENT_HTML.replace("</body>", '<img src="file:///C:/secret.png"></body>'), "external-resource-forbidden"),
            ("protocol relative", DOCUMENT_HTML.replace("</body>", '<img src="//example.test/x.png"></body>'), "external-resource-forbidden"),
        )
        for name, markup, expected in cases:
            with self.subTest(name=name):
                self.assertIn(expected, validate_html(self.write(markup), (), "document")["errors"])

    def test_rejects_css_imports_and_urls_after_css_escape_normalization(self):
        cases = (
            ("local import", "@import url(local.css);", "network-reference-forbidden"),
            ("protocol relative css", "body { background: url(//example.test/a.png); }", "external-resource-forbidden"),
            ("file css", "body { background: url(file:///C:/secret.png); }", "external-resource-forbidden"),
            ("escaped import", r"@import url(\68 ttp://example.test/a.css);", "network-reference-forbidden"),
        )
        for name, rule, expected in cases:
            with self.subTest(name=name):
                markup = DOCUMENT_HTML.replace("</style>", f" {rule}</style>")
                self.assertIn(expected, validate_html(self.write(markup), (), "document")["errors"])

    def test_css_words_in_comments_or_body_text_do_not_satisfy_rules(self):
        spoof = """<!doctype html><html><head><style>
        /* @media (max-width: 390px) {} @media (prefers-reduced-motion: reduce) {} @media (prefers-color-scheme: dark) {} */
        body { color: black; }
        </style></head><body><section>@media (max-width: 390px) @media (prefers-reduced-motion: reduce) @media (prefers-color-scheme: dark)</section></body></html>"""
        errors = validate_html(self.write(spoof), (), "document")["errors"]
        self.assertIn("responsive-rule-missing", errors)
        self.assertIn("reduced-motion-rule-missing", errors)
        self.assertIn("color-scheme-rule-missing", errors)

    def test_technical_visual_requires_explicit_relational_svg_semantics(self):
        non_relational = DOCUMENT_HTML.replace(
            "</section>",
            '<svg role="img"><title>图标</title><desc>一个图标</desc><circle cx="1" cy="1" r="1" /></svg></section>',
        )
        self.assertIn(
            "svg-relational-semantics-missing",
            validate_html(self.write(non_relational), (), "technical-visual")["errors"],
        )

    def test_hub_scripts_reject_unexpected_attributes(self):
        unexpected = HUB_HTML.replace('id="lesson-data" type="application/json"', 'id="lesson-data" type="application/json" src="local.js"')
        self.assertIn("hub-script-attributes-invalid", validate_html(self.write(unexpected), (), "hub")["errors"])

    def test_cli_writes_utf8_json_when_console_encoding_is_not_utf8(self):
        env = os.environ | {"PYTHONIOENCODING": "cp1252"}
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "validate_lesson_html.py"),
                "--html",
                str(self.write(DOCUMENT_HTML)),
                "--profile",
                "document",
                "--required-term",
                "模型能力缺失",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            check=False,
        )
        self.assertEqual(1, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("required-term-missing:模型能力缺失", report["errors"])


if __name__ == "__main__":
    unittest.main()
