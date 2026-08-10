import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
