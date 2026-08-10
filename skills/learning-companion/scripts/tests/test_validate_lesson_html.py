import ast
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sys
import unittest
import hashlib


SCRIPT_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_CONTRACT = SCRIPT_DIR.parent / "references" / "lesson-artifact-contract.md"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_lesson_html import (
    HUB_ACTIVE_STATUSES,
    HUB_REFRESH_BODY,
    HUB_REFRESH_BODY_SHA256,
    validate_html,
)


DOCUMENT_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 390px) {.layout { display: block; }} @media (prefers-reduced-motion: reduce) {* { animation: none; }} @media (prefers-color-scheme: dark) {body { color-scheme: dark; }}</style>
</head><body><section class="layout">模型能力</section></body></html>"""

TECHNICAL_VISUAL_HTML = DOCUMENT_HTML.replace(
    "</section>",
    "<svg role=\"img\"><title>交付关系</title><desc>模型能力通向可靠交付</desc><g data-node-id=\"model\"></g><g data-node-id=\"delivery\"></g><path data-edge-from=\"model\" data-edge-to=\"delivery\" d=\"M0 0L1 1\" /></svg>可靠交付</section>",
)

APPROVED_HUB_REFRESH_BODY_SHA256 = "c74305cd5efdf45e05e60680f948c0f58ccab9d99ac1a1d79e62e8fda57ee099"


def hub_data_script(status):
    payload = json.dumps({"status": status, "title": "企业 AI 系统分层"}, ensure_ascii=False, separators=(",", ":"))
    return '<script id="lesson-data" type="application/json">' + payload + "</script>"


def hub_html(status="studying", include_refresh=True):
    refresh = (
        f'<script id="lesson-refresh" data-contract="v1">{HUB_REFRESH_BODY}</script>'
        if include_refresh
        else ""
    )
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>@media (max-width: 390px) {.layout { display: block; }} @media (prefers-reduced-motion: reduce) {* { animation: none; }} @media (prefers-color-scheme: dark) {body { color-scheme: dark; }}</style></head>
<body><section class="layout">企业 AI 系统分层</section>
""" + hub_data_script(status) + "\n" + refresh + "</body></html>"


HUB_HTML = hub_html()


class ValidateLessonHtmlTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "lesson.html"

    def write(self, text, encoding="utf-8"):
        self.path.write_text(text, encoding=encoding, newline="\n")
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

    def test_refresh_hash_literal_is_pinned_to_the_approved_body(self):
        source = ast.parse((SCRIPT_DIR / "validate_lesson_html.py").read_text(encoding="utf-8"))
        assignments = [
            node
            for node in source.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "HUB_REFRESH_BODY_SHA256"
                for target in node.targets
            )
        ]
        self.assertEqual(1, len(assignments))
        self.assertIsInstance(assignments[0].value, ast.Constant)
        self.assertIsInstance(assignments[0].value.value, str)
        self.assertEqual(APPROVED_HUB_REFRESH_BODY_SHA256, HUB_REFRESH_BODY_SHA256)
        self.assertEqual(APPROVED_HUB_REFRESH_BODY_SHA256, hashlib.sha256(HUB_REFRESH_BODY.encode("utf-8")).hexdigest())

    def test_artifact_contract_publishes_the_pinned_refresh_constants(self):
        contract = ARTIFACT_CONTRACT.read_text(encoding="utf-8")
        self.assertIn(HUB_REFRESH_BODY, contract)
        self.assertIn(HUB_REFRESH_BODY_SHA256, contract)
        self.assertIn('<script id="lesson-data" type="application/json">', contract)
        self.assertIn('<script id="lesson-refresh" data-contract="v1">', contract)

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
        missing_data = HUB_HTML.replace(hub_data_script("studying"), "")
        self.assertIn("hub-data-script-invalid", validate_html(self.write(missing_data), (), "hub")["errors"])
        changed_refresh = HUB_HTML.replace("5000", "5001")
        self.assertIn("hub-refresh-script-invalid", validate_html(self.write(changed_refresh), (), "hub")["errors"])

    def test_hub_refresh_rejects_duplicate_and_unexpected_attributes(self):
        duplicate = HUB_HTML.replace("</body>", HUB_HTML.split('<script id="lesson-refresh"', 1)[1].join(('<script id="lesson-refresh"', "")) + "</body>")
        self.assertIn("hub-refresh-script-invalid", validate_html(self.write(duplicate), (), "hub")["errors"])
        unexpected = HUB_HTML.replace('data-contract="v1"', 'data-contract="v1" nonce="nope"')
        self.assertIn("hub-script-attributes-invalid", validate_html(self.write(unexpected), (), "hub")["errors"])
        invalid_contract = HUB_HTML.replace('data-contract="v1"', 'data-contract="v2"')
        self.assertIn("hub-script-attributes-invalid", validate_html(self.write(invalid_contract), (), "hub")["errors"])

    def test_hub_rejects_browser_differential_duplicate_script_attributes(self):
        cases = (
            ("duplicate data id", HUB_HTML.replace('id="lesson-data"', 'id="untrusted" id="lesson-data"'), "hub-script-attributes-invalid"),
            ("duplicate data type", HUB_HTML.replace('type="application/json"', 'type="text/javascript" type="application/json"'), "hub-script-attributes-invalid"),
            ("duplicate refresh id", HUB_HTML.replace('id="lesson-refresh"', 'id="untrusted" id="lesson-refresh"'), "hub-script-attributes-invalid"),
            ("duplicate refresh contract", HUB_HTML.replace('data-contract="v1"', 'data-contract="v2" data-contract="v1"'), "hub-script-attributes-invalid"),
            ("duplicate unexpected nonce", HUB_HTML.replace('data-contract="v1"', 'data-contract="v1" nonce="a" nonce="b"'), "hub-script-attributes-invalid"),
        )
        for name, markup, expected in cases:
            with self.subTest(name=name):
                errors = validate_html(self.write(markup), (), "hub")["errors"]
                self.assertIn("malformed-html", errors)
                self.assertIn(expected, errors)

    def test_hub_requires_an_explicit_allowlisted_refresh_status(self):
        self.assertEqual(
            frozenset({"preparing", "studying", "awaiting-voice"}),
            HUB_ACTIVE_STATUSES,
        )
        for status in HUB_ACTIVE_STATUSES:
            with self.subTest(status=status):
                self.assertEqual("passed", validate_html(self.write(hub_html(status)), (), "hub")["overall"])
        for status in ("closed", "error"):
            with self.subTest(status=status):
                self.assertEqual(
                    "passed",
                    validate_html(self.write(hub_html(status, include_refresh=False)), (), "hub")["overall"],
                )
                self.assertIn(
                    "hub-refresh-script-invalid",
                    validate_html(self.write(hub_html(status, include_refresh=True)), (), "hub")["errors"],
                )
        for status in ("unknown", "closed ", " studying", "studyng", "unsynced", "sync"):
            for include_refresh in (False, True):
                with self.subTest(status=status, include_refresh=include_refresh):
                    self.assertIn(
                        "hub-status-invalid",
                        validate_html(self.write(hub_html(status, include_refresh)), (), "hub")["errors"],
                    )

    def test_hub_allows_only_contained_artifact_links(self):
        contained = HUB_HTML.replace("企业 AI 系统分层</section>", '企业 AI 系统分层 <a href="visuals/001-responsibility-map.html">map</a></section>')
        self.assertEqual("passed", validate_html(self.write(contained), (), "hub")["overall"])
        escaped = contained.replace("visuals/001-responsibility-map.html", "../escape.html")
        self.assertIn("external-resource-forbidden", validate_html(self.write(escaped), (), "hub")["errors"])

    def test_allows_internal_anchors_but_rejects_meta_refresh_and_submission(self):
        internal_anchor = DOCUMENT_HTML.replace(
            "</section>", '<a href="#topic">jump</a><h2 id="topic">Topic</h2></section>'
        )
        self.assertEqual(
            "passed", validate_html(self.write(internal_anchor), (), "document")["overall"]
        )
        cases = (
            (
                "external meta refresh",
                '<meta http-equiv="refresh" content="0; url=https://example.test">',
                "meta-refresh-forbidden",
            ),
            (
                "fragment meta refresh",
                '<meta http-equiv="refresh" content="0; url=#topic">',
                "meta-refresh-forbidden",
            ),
            ("form", '<form method="post"></form>', "unsafe-element-forbidden"),
            ("action", '<div action="#topic"></div>', "submission-forbidden"),
            ("formaction", '<button formaction="#topic">go</button>', "submission-forbidden"),
        )
        for name, markup, expected in cases:
            with self.subTest(name=name):
                html = DOCUMENT_HTML.replace("</body>", markup + "</body>")
                self.assertIn(
                    expected, validate_html(self.write(html), (), "document")["errors"]
                )

    def test_rejects_high_risk_elements_after_namespace_normalization(self):
        cases = (
            ("base", '<base href="#topic">'),
            ("object", '<object data="data:image/png;base64,AA=="></object>'),
            ("embed", '<embed src="data:image/png;base64,AA==">'),
            ("link", '<link href="#topic">'),
            ("namespaced form", '<svg:form></svg:form>'),
        )
        for name, markup in cases:
            with self.subTest(name=name):
                html = DOCUMENT_HTML.replace("</body>", markup + "</body>")
                self.assertIn(
                    "unsafe-element-forbidden",
                    validate_html(self.write(html), (), "document")["errors"],
                )

    def test_rejects_namespaced_url_bearing_attribute_bypasses(self):
        cases = (
            (
                "xlink executable href",
                '<a xlink:href="javascript:alert(1)">x</a>',
                "executable-url-forbidden",
            ),
            (
                "namespaced external href",
                '<svg:a xlink:href="//example.test/x">x</svg:a>',
                "external-resource-forbidden",
            ),
            (
                "namespaced src",
                '<img svg:src="file:///C:/secret.png">',
                "external-resource-forbidden",
            ),
        )
        for name, markup, expected in cases:
            with self.subTest(name=name):
                html = DOCUMENT_HTML.replace("</body>", markup + "</body>")
                self.assertIn(
                    expected, validate_html(self.write(html), (), "document")["errors"]
                )

    def test_duplicate_security_attributes_fail_before_value_collapse(self):
        cases = (
            (
                "http equiv",
                '<meta http-equiv="other" http-equiv="refresh" content="0;url=#topic">',
                "meta-refresh-forbidden",
            ),
            (
                "content",
                '<meta http-equiv="refresh" content="0" content="0;url=#topic">',
                "meta-refresh-forbidden",
            ),
            (
                "href",
                '<a href="#topic" href="javascript:alert(1)">x</a>',
                "executable-url-forbidden",
            ),
            (
                "src",
                '<img src="data:image/png;base64,AA==" src="//example.test/x.png">',
                "external-resource-forbidden",
            ),
            (
                "action",
                '<form action="#topic" action="https://example.test"></form>',
                "submission-forbidden",
            ),
            (
                "formaction",
                '<button formaction="#topic" formaction="https://example.test">go</button>',
                "submission-forbidden",
            ),
            (
                "xlink href",
                '<a xlink:href="#topic" xlink:href="javascript:alert(1)">x</a>',
                "executable-url-forbidden",
            ),
        )
        for name, markup, expected in cases:
            with self.subTest(name=name):
                html = DOCUMENT_HTML.replace("</body>", markup + "</body>")
                errors = validate_html(self.write(html), (), "document")["errors"]
                self.assertIn("malformed-html", errors)
                self.assertIn(expected, errors)

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
            ("unclosed script", HUB_HTML.rsplit("</script>", 1)[0] + "</body></html>"),
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

    def test_allows_visible_network_words_but_rejects_resource_contexts(self):
        visible = DOCUMENT_HTML.replace(
            "模型能力",
            "https://example.test fetch( WebSocket XMLHttpRequest",
        )
        self.assertEqual(
            "passed",
            validate_html(
                self.write(visible),
                ("https://example.test", "fetch", "WebSocket", "XMLHttpRequest"),
                "document",
            )["overall"],
        )
        resource = visible.replace(
            "</body>", '<a href="https://example.test">source</a></body>'
        )
        self.assertIn(
            "external-resource-forbidden",
            validate_html(self.write(resource), (), "document")["errors"],
        )

    def test_required_terms_use_decoded_visible_text_only(self):
        citation = "https://example.test/reference?a=1&b=2"
        visible = DOCUMENT_HTML.replace(
            "模型能力", "https://example.test/reference?a=1&amp;b=2"
        )
        self.assertEqual(
            "passed", validate_html(self.write(visible), (citation,), "document")["overall"]
        )
        attribute_only = DOCUMENT_HTML.replace(
            'class="layout"', f'class="layout" data-citation="{citation}"'
        )
        self.assertIn(
            f"required-term-missing:{citation}",
            validate_html(self.write(attribute_only), (citation,), "document")["errors"],
        )
        style_only = DOCUMENT_HTML.replace(
            "</style>", " .layout::before { content: 'style-only-obligation'; }</style>"
        )
        self.assertIn(
            "required-term-missing:style-only-obligation",
            validate_html(self.write(style_only), ("style-only-obligation",), "document")["errors"],
        )

    def test_rejects_executable_and_inline_style_network_contexts(self):
        cases = (
            (
                "escaped expression fetch",
                DOCUMENT_HTML.replace(
                    "</style>", r"body { width: e/**/xpression(\66 etch()); }</style>"
                ),
                "network-reference-forbidden",
            ),
            (
                "websocket css identifier",
                DOCUMENT_HTML.replace("</style>", "body { behavior: WebSocket; }</style>"),
                "network-reference-forbidden",
            ),
            (
                "obfuscated xml http css identifier",
                DOCUMENT_HTML.replace(
                    "</style>", "body { behavior: XML/**/HttpRequest; }</style>"
                ),
                "network-reference-forbidden",
            ),
            (
                "inline css url",
                DOCUMENT_HTML.replace(
                    '<section class="layout">',
                    '<section class="layout" style="background: url(https://example.test/a.png);">',
                ),
                "external-resource-forbidden",
            ),
            (
                "inline css import",
                DOCUMENT_HTML.replace(
                    '<section class="layout">',
                    '<section class="layout" style="@import url(https://example.test/a.css);">',
                ),
                "network-reference-forbidden",
            ),
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
