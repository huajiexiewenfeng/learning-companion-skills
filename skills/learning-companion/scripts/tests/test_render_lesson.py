import copy
import tempfile
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from lesson_model import load_lesson_model
from validate_lesson_html import validate_html

try:
    from render_lesson import render_section
except ModuleNotFoundError:
    render_section = None

try:
    from render_lesson import required_terms_for_section
except ImportError:
    required_terms_for_section = None


FIXTURES = Path(__file__).parent / "fixtures"
ASSETS = SCRIPT_DIR.parent / "assets"
THEME = ASSETS / "lesson-theme.css"
BASE_MODEL = load_lesson_model(FIXTURES / "valid-lesson-model.json")


class RenderLessonTest(unittest.TestCase):
    def theme_css(self):
        self.assertTrue(THEME.is_file(), "the deterministic lesson theme must exist")
        return THEME.read_text(encoding="utf-8")

    def render(self, model, section):
        self.assertIsNotNone(render_section, "the lesson renderer must exist")
        return render_section(model, section, self.theme_css())

    def assert_valid(self, artifact):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.html"
            path.write_text(artifact.html, encoding="utf-8", newline="\n")
            report = validate_html(path, artifact.required_terms, artifact.profile)
        self.assertEqual("passed", report["overall"], report["errors"])

    def test_same_model_is_byte_identical(self):
        model = load_lesson_model(FIXTURES / "valid-lesson-model.json")
        section = next(item for item in model["sections"] if item["type"] == "concept")
        first = self.render(model, section)
        second = self.render(model, section)
        self.assertEqual(first.html.encode("utf-8"), second.html.encode("utf-8"))
        self.assertEqual("document", first.profile)
        self.assertEqual("cards/core-concept.html", first.relative_path)
        self.assert_valid(first)

    def test_agent_text_is_escaped(self):
        section = {
            "id": "unsafe-id",
            "type": "concept",
            "title": "<script>alert(1)</script>",
            "summary": "safe & <b>sound</b>",
            "sourceRefs": ["notes <unsafe>"],
        }
        artifact = self.render(BASE_MODEL, section)
        self.assertNotIn("<script>alert(1)</script>", artifact.html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", artifact.html)
        self.assertIn("safe &amp; &lt;b&gt;sound&lt;/b&gt;", artifact.html)
        self.assertEqual("cards/unsafe-id.html", artifact.relative_path)
        self.assert_valid(artifact)

    def test_relational_section_is_a_valid_technical_visual(self):
        section = next(item for item in BASE_MODEL["sections"] if item["type"] == "flow")
        artifact = self.render(BASE_MODEL, section)
        self.assertEqual("technical-visual", artifact.profile)
        self.assertIn('<svg role="img"', artifact.html)
        self.assertIn('data-node-id="node-0"', artifact.html)
        self.assertIn('data-edge-from="node-0" data-edge-to="node-1"', artifact.html)
        self.assertIn('d="M 200 72 L 230 72"', artifact.html)
        self.assert_valid(artifact)

    def test_network_like_model_text_is_visible_without_failing_validation(self):
        section = {
            "id": "safe-network-text",
            "type": "concept",
            "title": "fetch() is a word here",
            "summary": "WebSocket and XMLHttpRequest are names, not executable code.",
            "sourceRefs": ["https://example.test/reference"],
        }
        artifact = self.render(BASE_MODEL, section)
        self.assertIn("https:\u200b//example.test/reference", artifact.html)
        self.assertIn("fe\u200btch()", artifact.html)
        self.assert_valid(artifact)

    def test_source_required_term_survives_an_accidental_rendering_omission(self):
        model = copy.deepcopy(BASE_MODEL)
        model["requiredTerms"] = ["source obligation"]
        section = {
            "id": "source-term",
            "type": "concept",
            "title": "Term evidence",
            "summary": "This source obligation must remain visible.",
            "sourceRefs": ["guide.md#Section"],
        }
        self.assertIsNotNone(required_terms_for_section)
        self.assertEqual(
            ("source obligation",), required_terms_for_section(model, section)
        )
        artifact = self.render(model, section)
        self.assertEqual(("source obligation",), artifact.required_terms)
        omitted_html = artifact.html.replace("source obligation", "rendering omission")
        self.assertNotIn("source obligation", omitted_html)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "omitted.html"
            path.write_text(omitted_html, encoding="utf-8", newline="\n")
            report = validate_html(path, artifact.required_terms, artifact.profile)
        self.assertIn("required-term-missing:source obligation", report["errors"])

    def test_sparse_relation_fails_closed_without_a_declared_edge(self):
        section = {
            "id": "sparse-map",
            "type": "layer-map",
            "title": "Sparse relationship",
            "summary": "One declared layer still needs a readable relation frame.",
            "nodes": [{"id": "only", "label": "Only layer", "kind": "neutral"}],
            "edges": [],
            "sourceRefs": ["guide.md#Section"],
        }
        with self.assertRaisesRegex(ValueError, "relational section requires a declared edge"):
            self.render(BASE_MODEL, section)

    def test_all_document_component_types_pass_the_document_profile(self):
        for section_type in ("hero", "concept", "case-study", "misconception", "check-question", "sources"):
            with self.subTest(section_type=section_type):
                section = {
                    "id": f"{section_type}-card",
                    "type": section_type,
                    "title": f"{section_type} title",
                    "summary": f"{section_type} summary",
                    "sourceRefs": ["guide.md#Section"],
                }
                artifact = self.render(copy.deepcopy(BASE_MODEL), section)
                self.assertEqual("document", artifact.profile)
                self.assert_valid(artifact)

    def test_unsupported_section_type_is_rejected(self):
        section = {
            "id": "unknown",
            "type": "raw-html",
            "title": "Unsupported",
            "summary": "No raw HTML is rendered.",
            "sourceRefs": ["guide.md#Section"],
        }
        self.assertIsNotNone(render_section, "the lesson renderer must exist")
        with self.assertRaisesRegex(ValueError, "unsupported section type: raw-html"):
            render_section(BASE_MODEL, section, self.theme_css())


if __name__ == "__main__":
    unittest.main()
