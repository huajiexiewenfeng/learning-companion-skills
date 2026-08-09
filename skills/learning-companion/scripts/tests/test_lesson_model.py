from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from lesson_model import load_lesson_model, required_terms, slugify, validate_lesson_model


FIXTURES = Path(__file__).parent / "fixtures"


class LessonModelTest(unittest.TestCase):
    def test_valid_model(self):
        model = load_lesson_model(FIXTURES / "valid-lesson-model.json")
        self.assertEqual((), validate_lesson_model(model))
        self.assertEqual(
            ("企业 AI 系统分层", "模型能力", "系统能力", "Authoritative State"),
            required_terms(model),
        )

    def test_unknown_component_is_rejected(self):
        issues = validate_lesson_model(
            load_lesson_model(FIXTURES / "invalid-component-model.json")
        )
        self.assertIn("unknown-component", {issue.code for issue in issues})

    def test_missing_edge_target_is_rejected(self):
        issues = validate_lesson_model(
            load_lesson_model(FIXTURES / "invalid-relation-model.json")
        )
        self.assertIn("edge-target-missing", {issue.code for issue in issues})

    def test_slug_is_stable(self):
        self.assertEqual("day-01-ai-systems", slugify("Day 01: AI Systems"))


if __name__ == "__main__":
    unittest.main()
