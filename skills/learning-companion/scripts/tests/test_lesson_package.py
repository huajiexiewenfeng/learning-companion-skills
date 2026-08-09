import copy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from lesson_package import (
        allocate_session,
        close_session,
        prepare_session,
        sync_session,
        validate_session,
    )
except ModuleNotFoundError:
    allocate_session = close_session = prepare_session = sync_session = validate_session = None


FIXTURES = Path(__file__).parent / "fixtures"
PYTHON = Path(r"C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


class LessonPackageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan = self.root / "plan"
        self.plan.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def require_package(self):
        self.assertIsNotNone(allocate_session, "lesson_package.py must exist")

    def allocate(self, *, mode="text"):
        self.require_package()
        return allocate_session(
            self.plan, 1, "企业 AI 系统分层", mode, "medium", date(2026, 8, 9)
        )

    def valid_session(self, *, mode="text", decks=1):
        session = self.allocate(mode=mode)
        model = json.loads((FIXTURES / "valid-lesson-model.json").read_text(encoding="utf-8"))
        model["session"]["id"] = session.name
        model["session"]["planId"] = self.plan.name
        model["session"]["mode"] = mode
        if decks == 2:
            model["decks"].append(
                {
                    "id": "diagnostic-evidence",
                    "title": "诊断证据",
                    "sectionIds": ["core-concept", "runtime-flow"],
                }
            )
        (session / "lesson-model.json").write_text(
            json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return session

    def ledger(self, session):
        return (session / "artifacts.md").read_text(encoding="utf-8")

    def test_allocate_never_overwrites_history(self):
        first = self.allocate()
        second = self.allocate(mode="voice")
        self.assertTrue(first.name.endswith("session-01"))
        self.assertTrue(second.name.endswith("session-02"))
        self.assertEqual("preparing", self.lesson_status(first))
        self.assertEqual("preparing", self.lesson_status(second))

    def test_prepare_failure_leaves_no_final_artifacts_or_status_promotion(self):
        session = self.allocate()
        (session / "lesson-model.json").write_text("{}\n", encoding="utf-8")

        report = prepare_session(session)

        self.assertEqual(("failed", "preparing"), (report.overall, report.status))
        self.assertFalse((session / "index.html").exists())
        self.assertFalse((session / "cards").exists())
        self.assertFalse(list(session.glob(".lesson-stage-*")))
        self.assertEqual("preparing", self.lesson_status(session))

    def test_prepare_requires_lesson_markdown_before_promotion(self):
        session = self.valid_session()
        (session / "lesson.md").unlink()

        report = prepare_session(session)

        self.assertEqual(("failed", "preparing"), (report.overall, report.status))
        self.assertIn("lesson-markdown-missing", report.errors)
        self.assertFalse((session / "index.html").exists())

    def test_prepare_promotes_complete_package_and_records_every_deck_and_slide(self):
        session = self.valid_session(decks=2)

        report = prepare_session(session)

        self.assertEqual("passed", report.overall, report.errors)
        self.assertEqual("studying", report.status)
        self.assertTrue((session / "index.html").is_file())
        self.assertTrue((session / "decks" / "001-system-layers" / "index.html").is_file())
        self.assertTrue((session / "decks" / "002-diagnostic-evidence" / "index.html").is_file())
        self.assertGreaterEqual(len(list((session / "decks").glob("*/slides/*.html"))), 7)
        ledger = self.ledger(session)
        self.assertIn("type: hub", ledger)
        self.assertIn("type: deck", ledger)
        self.assertIn("type: slide", ledger)
        self.assertIn("profile: technical-visual", ledger)
        self.assertIn("sha256:", ledger)
        self.assertIn("createdAt: 1970-01-01T00:00:00Z", ledger)
        self.assertEqual("studying", self.lesson_status(session))

    def test_voice_prepare_waits_for_voice_handoff(self):
        session = self.valid_session(mode="voice")

        report = prepare_session(session)

        self.assertEqual(("passed", "awaiting-voice"), (report.overall, report.status))
        self.assertEqual("awaiting-voice", self.lesson_status(session))

    def test_global_required_term_union_is_a_prepare_gate(self):
        session = self.valid_session()
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        model["requiredTerms"].append("从未渲染的全局术语")
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")

        report = prepare_session(session)

        self.assertEqual(("failed", "preparing"), (report.overall, report.status))
        self.assertIn("global-required-term-missing:从未渲染的全局术语", report.errors)
        self.assertFalse((session / "index.html").exists())

    def test_changed_artifact_creates_immutable_v2_and_supersedes_record(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        model["sections"][0]["summary"] = "修订后的概念"
        model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")

        report = sync_session(session)

        self.assertEqual("passed", report.overall, report.errors)
        self.assertTrue((session / "cards" / "core-concept.html").is_file())
        self.assertTrue((session / "cards" / "core-concept-v2.html").is_file())
        self.assertIn("supersedes: core-concept", self.ledger(session))

    def test_validation_rejects_unlisted_artifact_source_reference(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        ledger_path = session / "artifacts.md"
        ledger_path.write_text(
            self.ledger(session).replace("sourceRefs: dashboard.md#Today", "sourceRefs: secret.md#Hidden", 1),
            encoding="utf-8",
        )

        report = validate_session(session)

        self.assertEqual("failed", report.overall)
        self.assertIn("source-reference-unauthorized:secret.md#Hidden", report.errors)

    def test_close_freezes_artifacts_removes_refresh_and_preserves_progress_files(self):
        session = self.valid_session()
        dashboard = self.plan / "dashboard.md"
        roadmap = self.plan / "plan.md"
        dashboard.write_text("mastery: 0.5\n", encoding="utf-8")
        roadmap.write_text("Effective progress: 12%\n", encoding="utf-8")
        self.assertEqual("passed", prepare_session(session).overall)
        before_dashboard = dashboard.read_bytes()
        before_roadmap = roadmap.read_bytes()

        report = close_session(session)

        self.assertEqual(("passed", "closed"), (report.overall, report.status))
        self.assertEqual("closed", self.lesson_status(session))
        self.assertNotIn('id="lesson-refresh"', (session / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(before_dashboard, dashboard.read_bytes())
        self.assertEqual(before_roadmap, roadmap.read_bytes())
        self.assertTrue((session / ".artifacts-frozen").is_file())

    def test_cli_validate_writes_utf8_json(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)

        result = subprocess.run(
            [str(PYTHON), str(SCRIPT_DIR / "lesson_package.py"), "validate", str(session)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual("passed", parsed["overall"])
        self.assertIn("企业 AI 系统分层", result.stdout)

    @staticmethod
    def lesson_status(session):
        for line in (session / "lesson.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("status: "):
                return line.partition(": ")[2]
        raise AssertionError("lesson.md is missing frontmatter status")


if __name__ == "__main__":
    unittest.main()
