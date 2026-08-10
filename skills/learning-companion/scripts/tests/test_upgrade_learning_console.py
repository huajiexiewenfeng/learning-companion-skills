import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "upgrade_learning_console.py"
TEMPLATE = ROOT / "references" / "learning-console-template.html"
FIXTURE = Path(__file__).with_name("fixtures") / "existing-console-v1.html"


def load_module():
    spec = importlib.util.spec_from_file_location("upgrade_learning_console", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def extract_learning_data_block(text):
    start = text.index('<script id="learning-data">')
    end = text.index("</script>", start) + len("</script>")
    return text[start:end]


class UpgradeLearningConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.target = Path(self.tempdir.name) / "learning-console.html"
        # Exercise newline preservation independently of the repository checkout policy.
        self.target.write_bytes(FIXTURE.read_bytes().replace(b"\n", b"\r\n"))
        self.module = load_module()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_upgrade_preserves_data_custom_css_and_crlf(self):
        before_bytes = self.target.read_bytes()
        before = extract_learning_data_block(before_bytes.decode("utf-8"))

        report = self.module.upgrade_console(self.target, TEMPLATE)
        after_bytes = self.target.read_bytes()
        after = after_bytes.decode("utf-8")

        self.assertTrue(report.changed and report.preserved_data_block)
        self.assertEqual(before, extract_learning_data_block(after))
        self.assertIn("/* user-custom-css */", after)
        self.assertIn('id="lesson-sessions"', after)
        self.assertIn(b"\r\n", after_bytes)
        self.assertFalse(after_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertNotEqual(before_bytes, after_bytes)

    def test_second_upgrade_is_byte_identical_noop(self):
        self.module.upgrade_console(self.target, TEMPLATE)
        first = self.target.read_bytes()

        report = self.module.upgrade_console(self.target, TEMPLATE)

        self.assertFalse(report.changed)
        self.assertEqual(first, self.target.read_bytes())
        self.assertEqual(2, report.current_version)

    def test_malformed_or_ambiguous_target_fails_without_write(self):
        original = self.target.read_bytes()
        self.target.write_bytes(original.replace(b"</nav>", b"</nav></nav>"))
        before = self.target.read_bytes()

        with self.assertRaises(self.module.UpgradeError):
            self.module.upgrade_console(self.target, TEMPLATE)

        self.assertEqual(before, self.target.read_bytes())

    def test_renderer_uses_safe_dom_text_and_relative_links(self):
        self.module.upgrade_console(self.target, TEMPLATE)
        html = self.target.read_text(encoding="utf-8")

        self.assertIn("function renderLessonSessions", html)
        self.assertIn("textContent", html)
        self.assertIn("replaceChildren", html)
        self.assertIn("safeLessonPath", html)
        self.assertNotIn("innerHTML = (sessions", html)

    def test_cli_reports_portable_json_on_failure(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.module.main(["--html", str(self.target), "--template", str(self.target)])
        self.assertEqual(2, result)
        self.assertFalse(json.loads(output.getvalue())["changed"])

    def assert_refuses_without_write(self, mutate):
        mutate()
        before = self.target.read_bytes()
        with self.assertRaises(self.module.UpgradeError):
            self.module.upgrade_console(self.target, TEMPLATE)
        self.assertEqual(before, self.target.read_bytes())

    def test_spoofed_or_partial_v2_is_never_a_noop(self):
        self.module.upgrade_console(self.target, TEMPLATE)
        valid = self.target.read_text(encoding="utf-8")
        cases = (
            ("missing required section id", lambda: self.target.write_text(valid.replace('id="lesson-sessions"', 'id="spoofed-sessions"'), encoding="utf-8")),
            ("empty renderer marker payload", lambda: self.target.write_text(
                valid.replace(
                    'function safeLessonPath(value) {',
                    'function fakeLessonPath(value) {',
                ), encoding="utf-8")),
            ("wrong navigation href", lambda: self.target.write_text(valid.replace('href="#lesson-sessions"', 'href="#dashboard"'), encoding="utf-8")),
            ("navigation link outside its marker payload", lambda: self.target.write_text(
                valid.replace(
                    '<!-- learning-companion:lesson-sessions:nav:start -->\n        <a class="nav-link" href="#lesson-sessions"><span class="nav-dot"></span>课程存档</a>',
                    '<!-- learning-companion:lesson-sessions:nav:start -->',
                ).replace(
                    '<!-- learning-companion:lesson-sessions:nav:end -->',
                    '<!-- learning-companion:lesson-sessions:nav:end -->\n        <a class="nav-link" href="#lesson-sessions"><span class="nav-dot"></span>课程存档</a>',
                    1,
                ), encoding="utf-8")),
            ("empty section marker payload", lambda: self.target.write_text(
                valid.replace(
                    '<!-- learning-companion:lesson-sessions:section:start -->\n        <section class="section" id="lesson-sessions" data-console-feature="lesson-sessions-v1">',
                    '<!-- learning-companion:lesson-sessions:section:start -->',
                ).replace(
                    '        </section>\n        <!-- learning-companion:lesson-sessions:section:end -->',
                    '<!-- learning-companion:lesson-sessions:section:end -->',
                    1,
                ), encoding="utf-8")),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                self.target.write_text(valid, encoding="utf-8")
                self.assert_refuses_without_write(mutate)

    def test_legacy_anchor_text_in_comments_or_scripts_is_not_trusted(self):
        original = self.target.read_text(encoding="utf-8")
        cases = (
            ("style comment", lambda: original.replace("</style>", "", 1).replace("</head>", "<!-- </style> --></head>", 1)),
            ("nav comment", lambda: original.replace("</nav>", "", 1).replace("</aside>", "<!-- </nav> --></aside>", 1)),
            ("mastery script string", lambda: original.replace('<section class="section" id="mastery">', "", 1).replace("</body>", "<script>const bait = '<section class=\\\"section\\\" id=\\\"mastery\\\">';</script></body>", 1)),
            ("renderer script string", lambda: original.replace("function render() {", "function paint() {", 1).replace("</body>", "<script>const bait = '    function render() {';</script></body>", 1)),
            ("render call comment", lambda: original.replace("renderSources(data.sourceFiles || [], data.generatedAt);", "renderOther();", 1).replace("</body>", "<script>// renderSources(data.sourceFiles || [], data.generatedAt);</script></body>", 1)),
        )
        for name, mutation in cases:
            with self.subTest(name=name):
                self.target.write_text(mutation(), encoding="utf-8")
                self.assert_refuses_without_write(lambda: None)

    def test_legacy_duplicate_or_misplaced_anchors_fail_without_write(self):
        original = self.target.read_text(encoding="utf-8")
        cases = (
            original.replace("</nav>", "</nav></nav>", 1),
            original.replace('<section class="section" id="mastery">', '<head><section class="section" id="mastery">', 1),
            original.replace("function render() {", "function render() {", 1).replace("</body>", "<script>function render() {}</script></body>", 1),
        )
        for corrupted in cases:
            with self.subTest(corrupted=corrupted[-80:]):
                self.target.write_text(corrupted, encoding="utf-8")
                self.assert_refuses_without_write(lambda: None)

    def test_only_normalized_lesson_archive_paths_are_safe(self):
        valid = "learning-companion/plans/demo/lessons/2026-08-09-day-001-session-01/index.html"
        self.assertTrue(self.module.is_safe_lesson_path(valid))
        for unsafe in (
            "../learning-companion/plans/demo/lessons/a/index.html",
            "/learning-companion/plans/demo/lessons/a/index.html",
            "https://example.test/learning-companion/plans/demo/lessons/a/index.html",
            "//example.test/learning-companion/plans/demo/lessons/a/index.html",
            "learning-companion\\plans\\demo\\lessons\\a\\index.html",
            "learning-companion/plans/demo/lessons/%2e%2e/index.html",
            "learning-companion/plans/demo/lessons/%2findex.html",
            "learning-companion/plans/demo/lessons/a/other.html",
            "learning-companion/plans/demo/index.html",
            "learning-companion/plans/demo/lessons/a/index.html\x00",
        ):
            with self.subTest(path=unsafe):
                self.assertFalse(self.module.is_safe_lesson_path(unsafe))

    def test_cli_wraps_argument_and_unexpected_failures_as_json(self):
        for argv in ([], ["--html", str(self.target), "--template", str(TEMPLATE), "--unknown"]):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                result = self.module.main(argv)
            self.assertNotEqual(0, result)
            payload = json.loads(output.getvalue())
            self.assertFalse(payload["changed"])

        output = io.StringIO()
        original = self.module.upgrade_console
        self.module.upgrade_console = lambda *_: (_ for _ in ()).throw(OSError("replace failed"))
        try:
            with redirect_stdout(output):
                result = self.module.main(["--html", str(self.target), "--template", str(TEMPLATE)])
        finally:
            self.module.upgrade_console = original
        self.assertNotEqual(0, result)
        self.assertEqual("replace failed", json.loads(output.getvalue())["error"])

    def test_unicode_and_atomic_replace_failures_preserve_target_bytes(self):
        self.target.write_bytes(b"\xff\xfe not utf8")
        before = self.target.read_bytes()
        with self.assertRaises(self.module.UpgradeError):
            self.module.upgrade_console(self.target, TEMPLATE)
        self.assertEqual(before, self.target.read_bytes())

        self.target.write_bytes(FIXTURE.read_bytes())
        before = self.target.read_bytes()
        with mock.patch.object(self.module.os, "replace", side_effect=OSError("replace denied")):
            with self.assertRaises(self.module.UpgradeError):
                self.module.upgrade_console(self.target, TEMPLATE)
        self.assertEqual(before, self.target.read_bytes())


if __name__ == "__main__":
    unittest.main()
