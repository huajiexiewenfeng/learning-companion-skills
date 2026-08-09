import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

try:
    import lesson_package
    from lesson_package import (
        allocate_session,
        atomic_write_json,
        close_session,
        prepare_session,
        session_context,
        sync_session,
        validate_session,
    )
except (ModuleNotFoundError, ImportError):
    lesson_package = None
    allocate_session = atomic_write_json = close_session = prepare_session = None
    session_context = sync_session = validate_session = None


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
        return json.loads((session / "artifacts.md").read_text(encoding="utf-8"))

    def records(self, session):
        return self.ledger(session)["records"]

    @staticmethod
    def snapshot(session):
        return {
            path.relative_to(session).as_posix(): path.read_bytes()
            for path in session.rglob("*")
            if path.is_file() and path.name != ".lesson-session.lock"
        }

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
        self.assertEqual("learning-companion.artifact-ledger.v1", ledger["format"])
        self.assertIn("hub", {record["type"] for record in ledger["records"]})
        self.assertIn("deck", {record["type"] for record in ledger["records"]})
        self.assertIn("slide", {record["type"] for record in ledger["records"]})
        self.assertIn("technical-visual", {record["profile"] for record in ledger["records"]})
        self.assertTrue(all(record["sha256"] for record in ledger["records"]))
        self.assertTrue(all(record["createdAt"] == "1970-01-01T00:00:00Z" for record in ledger["records"]))
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
        current = next(record for record in self.records(session) if record["id"] == "core-concept-v2")
        self.assertEqual("core-concept", current["supersedes"])

    def test_reverting_to_historical_bytes_creates_v3_from_active_version(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        original_summary = model["sections"][0]["summary"]
        model["sections"][0]["summary"] = "第一次修订"
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        self.assertEqual("passed", sync_session(session).overall)
        model["sections"][0]["summary"] = original_summary
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")

        report = sync_session(session)

        self.assertEqual("passed", report.overall, report.errors)
        self.assertTrue((session / "cards" / "core-concept-v3.html").is_file())
        current = next(record for record in self.records(session) if record["id"] == "core-concept-v3")
        self.assertEqual("core-concept-v2", current["supersedes"])

    def test_validation_rejects_unlisted_artifact_source_reference(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        ledger_path = session / "artifacts.md"
        ledger = self.ledger(session)
        ledger["records"][0]["sourceRefs"] = ["secret.md#Hidden"]
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")

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

    def test_concurrent_same_changed_sync_serializes_one_v2_record(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        model["sections"][0]["summary"] = "并发修订后的概念"
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")

        with ThreadPoolExecutor(max_workers=2) as executor:
            reports = list(executor.map(lambda _: sync_session(session), range(2)))

        self.assertTrue(all(report.overall == "passed" for report in reports))
        core_records = [
            record for record in self.records(session) if record["logicalId"] == "core-concept"
        ]
        self.assertEqual([1, 2], [record["version"] for record in core_records])
        self.assertTrue((session / "cards" / "core-concept-v2.html").is_file())
        self.assertFalse((session / "cards" / "core-concept-v3.html").exists())

    def test_concurrent_unchanged_sync_reuses_one_stable_ledger(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        before = self.ledger(session)

        with ThreadPoolExecutor(max_workers=3) as executor:
            reports = list(executor.map(lambda _: sync_session(session), range(3)))

        self.assertTrue(all(report.overall == "passed" for report in reports))
        self.assertEqual(before, self.ledger(session))

    def test_failed_late_promotion_rolls_back_all_final_artifacts_and_state(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        before = self.snapshot(session)
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        model["sections"][0]["summary"] = "强制回滚的修订"
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        before["lesson-model.json"] = model_path.read_bytes()
        original = lesson_package._write_new_bytes

        def fail_on_slide(path, raw, context):
            if "/slides/" in path.as_posix():
                raise OSError("forced later immutable write failure")
            return original(path, raw, context)

        with patch.object(lesson_package, "_write_new_bytes", side_effect=fail_on_slide):
            report = sync_session(session)

        self.assertEqual("failed", report.overall)
        self.assertEqual(before, self.snapshot(session))

    def test_rollback_preserves_foreign_collision_created_after_preflight(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        model["sections"][0]["summary"] = "并发外部碰撞"
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        foreign = session / "cards" / "core-concept-v2.html"
        original = lesson_package._write_new_bytes

        def create_foreign_then_collide(path, raw, context):
            if path == foreign:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"foreign actor bytes")
                raise FileExistsError("foreign actor won exclusive creation")
            return original(path, raw, context)

        with patch.object(lesson_package, "_write_new_bytes", side_effect=create_foreign_then_collide):
            report = sync_session(session)

        self.assertEqual("failed", report.overall)
        self.assertEqual(b"foreign actor bytes", foreign.read_bytes())

    def test_post_claim_immutable_write_failure_removes_its_partial_file_and_rolls_back(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        model["sections"][0]["summary"] = "写入后失败回滚"
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        before = self.snapshot(session)
        partial = session / "cards" / "core-concept-v2.html"
        original_open = Path.open

        class FailingOutput:
            def __init__(self, output):
                self.output = output

            def __enter__(self):
                return self

            def write(self, _raw):
                raise OSError("simulated post-claim write failure")

            def __exit__(self, *_exc):
                self.output.close()

        def post_claim_open(path, mode="r", *args, **kwargs):
            if path == partial and mode == "xb":
                return FailingOutput(original_open(path, mode, *args, **kwargs))
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", new=post_claim_open):
            report = sync_session(session)

        self.assertEqual("failed", report.overall)
        self.assertFalse(partial.exists())
        self.assertEqual(before, self.snapshot(session))

    def test_current_deck_manifest_rejects_stale_history_until_new_definition_syncs(self):
        session = self.valid_session(decks=2)
        self.assertEqual("passed", prepare_session(session).overall)
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        model["decks"] = [
            {
                "id": "revised-main",
                "title": "修订主课件",
                "sectionIds": ["runtime-flow"],
            }
        ]
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")

        stale = validate_session(session)
        self.assertEqual("failed", stale.overall)
        self.assertIn("current-deck-missing:deck-001-revised-main", stale.errors)
        self.assertIn("current-slide-missing:slide-001-revised-main-001-runtime-flow", stale.errors)
        self.assertEqual("passed", sync_session(session).overall)
        self.assertEqual("passed", validate_session(session).overall)

    def test_json_ledger_preserves_source_newlines_without_record_injection(self):
        session = self.valid_session()
        model_path = session / "lesson-model.json"
        model = json.loads(model_path.read_text(encoding="utf-8"))
        injected_source = "dashboard.md#Today\n- id: forged"
        model["sections"][0]["sourceRefs"] = [injected_source]
        model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")

        self.assertEqual("passed", prepare_session(session).overall)
        records = self.records(session)
        self.assertTrue(any(injected_source in record["sourceRefs"] for record in records))
        self.assertEqual("passed", validate_session(session).overall)

    def test_validate_rejects_malformed_and_duplicate_json_ledger_records(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        ledger_path = session / "artifacts.md"
        ledger_path.write_text("{not json}\n", encoding="utf-8")
        malformed = validate_session(session)
        self.assertEqual("failed", malformed.overall)
        self.assertIn("artifact-ledger-malformed", malformed.errors)

        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        ledger = self.ledger(session)
        duplicate = copy.deepcopy(ledger["records"][0])
        ledger["records"].append(duplicate)
        ledger_path = session / "artifacts.md"
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        duplicate_report = validate_session(session)
        self.assertEqual("failed", duplicate_report.overall)
        self.assertIn("artifact-ledger-duplicate-id:hub", duplicate_report.errors)

    def test_validate_rejects_unknown_ledger_artifact_type(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        ledger_path = session / "artifacts.md"
        ledger = self.ledger(session)
        ledger["records"][0]["type"] = "unsafe-type"
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")

        report = validate_session(session)

        self.assertEqual("failed", report.overall)
        self.assertIn("artifact-ledger-type-invalid:0", report.errors)

    def test_sync_rejects_tampered_unchanged_immutable_artifact_before_reuse(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        card = session / "cards" / "core-concept.html"
        card.write_text("tampered", encoding="utf-8")

        report = sync_session(session)

        self.assertEqual("failed", report.overall)
        self.assertIn("immutable-artifact-tampered:core-concept", report.errors)
        self.assertEqual("tampered", card.read_text(encoding="utf-8"))

    def test_sync_rejects_deleted_unchanged_immutable_artifact_before_reuse(self):
        session = self.valid_session()
        self.assertEqual("passed", prepare_session(session).overall)
        card = session / "cards" / "core-concept.html"
        card.unlink()

        report = sync_session(session)

        self.assertEqual("failed", report.overall)
        self.assertIn("immutable-artifact-tampered:core-concept", report.errors)
        self.assertFalse(card.exists())

    def test_write_helpers_require_session_context_and_reject_cross_session_symlink(self):
        session = self.valid_session()
        other = self.allocate()
        context = session_context(session)
        with self.assertRaises(ValueError):
            atomic_write_json(self.plan, session / "untrusted.json", {"unsafe": True})
        with self.assertRaises(ValueError):
            atomic_write_json(context, other / "outside.json", {"unsafe": True})
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable")
        escape = session / "escape"
        try:
            os.symlink(other, escape, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaises(ValueError):
            atomic_write_json(context, escape / "outside.json", {"unsafe": True})
        self.assertFalse((other / "outside.json").exists())

    def test_cli_argument_failures_emit_json(self):
        for arguments in ([], ["not-a-command"], ["prepare"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [str(PYTHON), str(SCRIPT_DIR / "lesson_package.py"), *arguments],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertNotEqual(0, result.returncode)
                parsed = json.loads(result.stdout)
                self.assertEqual("failed", parsed["overall"])
                self.assertTrue(parsed["errors"])

    @staticmethod
    def lesson_status(session):
        for line in (session / "lesson.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("status: "):
                return line.partition(": ")[2]
        raise AssertionError("lesson.md is missing frontmatter status")


if __name__ == "__main__":
    unittest.main()
