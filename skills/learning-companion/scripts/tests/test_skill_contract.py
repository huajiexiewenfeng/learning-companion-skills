"""Semantic guardrails for the learning-companion teaching protocol."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL = SKILL_ROOT / "SKILL.md"
VOICE = SKILL_ROOT / "references" / "voice-teaching.md"
SESSION = SKILL_ROOT / "references" / "lesson-session-contract.md"
ARTIFACT = SKILL_ROOT / "references" / "lesson-artifact-contract.md"


class LearningCompanionTeachingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.voice = VOICE.read_text(encoding="utf-8") if VOICE.exists() else ""
        cls.session = SESSION.read_text(encoding="utf-8")
        cls.artifact = ARTIFACT.read_text(encoding="utf-8")

    def test_required_runtime_and_references_are_named(self) -> None:
        for name in (
            "voice-teaching.md",
            "lesson-session-contract.md",
            "lesson-model-authoring.md",
            "lesson-artifact-contract.md",
            "lesson_package.py",
        ):
            self.assertIn(name, self.skill)

    def test_route_table_keeps_text_and_voice_requests_separate(self) -> None:
        route = self._section(self.skill, "Teaching Routes", "Prepare And Validate Courseware")
        text_row = next(line for line in route.splitlines() if "`上课`" in line)
        self.assertIn("continue learning", text_row)
        self.assertIn("| text |", text_row)
        self.assertNotIn("Voice", text_row)
        for voice_phrase in ("语音上课", "用语音教我", "实时语音老师", "Voice teacher"):
            self.assertRegex(route, rf"(?is){re.escape(voice_phrase)}.*?Voice")

    def test_courseware_gate_precedes_teaching_and_handoff(self) -> None:
        prepare = self.skill.index("Prepare And Validate Courseware")
        teaching = self.skill.index("Teaching Protocol")
        self.assertLess(prepare, teaching)
        package = self._section(self.skill, "Prepare And Validate Courseware", "Teaching Protocol")
        ordered = (
            "source read",
            "allocate",
            "lesson.md + lesson-model.json",
            "model validation",
            "render",
            "per-artifact validation",
            "open/link hub",
            "teach/handoff",
        )
        positions = [package.index(item) for item in ordered]
        self.assertEqual(positions, sorted(positions))
        for artifact in (
            "lesson.md",
            "lesson-model.json",
            "artifacts.md",
            "index.html",
            "main deck",
            "technical-visual",
        ):
            self.assertIn(artifact, package)
        self.assertIn("both text and Voice", package)
        self.assertIn("preparing", package)
        self.assertIn("awaiting-voice", package)

    def test_voice_handoff_is_truthful_and_requires_observable_host_state(self) -> None:
        self.assertTrue(self.voice, "Voice protocol reference must exist")
        for phrase in (
            "new empty Voice task",
            "使用 learning-companion 继续当前 active plan",
            "Never claim",
            "observable host state",
            "Do not use UI automation",
            "Do not guess buttons",
            "local TTS",
            "prerecorded",
        ):
            self.assertIn(phrase, self.voice)
        self.assertRegex(
            self.voice,
            r"(?is)new empty Voice task.*?first message.*?使用 learning-companion 继续当前 active plan",
        )
        self.assertRegex(self.voice, r"(?is)existing text task.*?(?:cannot|must not).*?(?:switch|become).*?Voice")

    def test_voice_speech_turn_contract_is_bounded_and_interruption_first(self) -> None:
        self.assertRegex(self.voice, r"(?is)45.?90 second.*?concept chunk")
        self.assertRegex(self.voice, r"(?is)interruption-first")
        self.assertRegex(self.voice, r"(?is)exactly\s+one\s+check question")

    def test_per_turn_persistence_orders_markdown_html_then_response(self) -> None:
        protocol = self._section(self.skill, "Teaching Protocol", "Progress Rule")
        ordered = ("Markdown first", "versioned HTML sync", "then respond")
        positions = [protocol.index(item) for item in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertRegex(protocol, r"(?is)write failure.*?(?:must not|cannot).*?(?:sync HTML|claim persistence)")

    def test_recovery_does_not_invent_session_state(self) -> None:
        protocol = self._section(self.skill, "Teaching Protocol", "Progress Rule")
        self.assertRegex(protocol, r"(?is)newest\s+open session")
        self.assertRegex(protocol, r"(?is)(?:do not|never).*?invent.*?state")

    def test_recovery_validates_newest_open_session_without_older_fallback(self) -> None:
        protocol = self._section(self.skill, "Teaching Protocol", "Progress Rule")
        normalized = protocol.lower()
        ordered = (
            "select the single newest open session first",
            "validate that exact session",
            "if invalid, never fall back to older sessions",
            "restart from source-read/preparing",
        )
        positions = [normalized.index(item) for item in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertRegex(protocol, r"(?is)validate that exact session.*?(?:model|package|source)")
        self.assertRegex(protocol, r"(?is)(?:repair|allocate).*?documented lifecycle")

    def test_recovery_invariant_is_consistent_across_skill_voice_and_lifecycle(self) -> None:
        protocol = self._section(self.skill, "Teaching Protocol", "Progress Rule")
        documents = {
            "skill": protocol,
            "voice": self.voice,
            "lifecycle": self.session,
        }
        for name, document in documents.items():
            with self.subTest(document=name):
                self.assertRegex(document, r"(?is)single newest open\s+session first")
                self.assertRegex(document, r"(?is)validate\s+that exact session")
                self.assertRegex(document, r"(?is)(?:if invalid|failed newest session).*?never.*?fall back.*?older")
                self.assertRegex(document, r"(?is)(?:repair|restart from source-read|allocate).*?(?:lifecycle|preparing)")
                self.assertNotRegex(document, r"(?is)(?:fall back|fallback)[^.]{0,80}older[^.]{0,80}valid")
                self.assertNotRegex(document, r"(?is)older[^.]{0,80}valid[^.]{0,80}(?:fall back|fallback)")

    def test_fresh_text_after_abandoned_voice_allocates_new_text_session(self) -> None:
        self.assertRegex(self.voice, r"(?is)fresh\s+text-teaching request")
        self.assertRegex(self.voice, r"(?is)(?:must not|do not).*?(?:reuse|promote).*?awaiting-voice")
        self.assertRegex(self.voice, r"(?is)allocate and prepare.*?new text-mode session/package")
        self.assertRegex(self.voice, r"(?is)awaiting-voice history intact")
        self.assertRegex(self.voice, r"(?is)studying.*?after.*?gates pass")

    def test_one_check_question_has_only_the_close_out_review_exception(self) -> None:
        protocol = self._section(self.skill, "Teaching Protocol", "Progress Rule")
        daily = self._section(self.skill, "Daily Protocol", "Teaching Routes")
        self.assertRegex(protocol, r"(?is)exactly one check question.*?ordinary teaching chunks")
        self.assertRegex(protocol, r"(?is)only exception.*?下课.*?mastery review")
        self.assertIn("1-3 verification questions", daily)
        self.assertEqual(self.skill.count("1-3 verification questions"), 1)
        self.assertRegex(daily, r"(?is)only path.*?Effective progress")

    def test_close_is_the_only_effective_progress_path(self) -> None:
        daily = self._section(self.skill, "Daily Protocol", "Teaching Routes")
        self.assertRegex(daily, r"(?is)下课.*?normal mastery review.*?(?:close|freeze).*?artifacts")
        self.assertRegex(daily, r"(?is)only path.*?(?:may|can).*?Effective progress")
        self.assertRegex(self.session, r"(?is)close.*?\.artifacts-frozen")
        self.assertRegex(self.session, r"(?is)never updates.*?Effective-progress")
        self.assertRegex(self.artifact, r"(?is)visual verification")

    def test_current_product_claims_delegate_to_openai_docs(self) -> None:
        self.assertRegex(self.voice, r"(?is)current product claims.*?openai-docs")

    @staticmethod
    def _section(text: str, start: str, end: str) -> str:
        pattern = rf"(?s)## {re.escape(start)}\n(.*?)(?=\n## {re.escape(end)}\n)"
        match = re.search(pattern, text)
        if match is None:
            raise AssertionError(f"missing section: {start} -> {end}")
        return match.group(1)


if __name__ == "__main__":
    unittest.main()
