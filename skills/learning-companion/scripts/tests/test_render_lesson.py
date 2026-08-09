import copy
import re
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

try:
    from render_lesson import render_relation
except ImportError:
    render_relation = None

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

    def test_all_relation_types_have_accessible_svg_and_mobile_equivalent(self):
        relation_types = ("layer-map", "boundary-map", "flow", "timeline")
        for section_type in relation_types:
            with self.subTest(section_type=section_type):
                section = next(
                    item for item in BASE_MODEL["sections"] if item["type"] == section_type
                )
                artifact = self.render(BASE_MODEL, section)
                self.assertEqual("technical-visual", artifact.profile)
                self.assertIn('class="desktop-diagram', artifact.html)
                self.assertIn('role="img"', artifact.html)
                self.assertIn(
                    f'<title id="{section["id"]}-title">{section["title"]}</title>',
                    artifact.html,
                )
                self.assertIn(
                    f'<desc id="{section["id"]}-desc">{section["summary"]}</desc>',
                    artifact.html,
                )
                mobile = artifact.html.split('<ol class="mobile-semantic-flow">', 1)[1]
                for node in section["nodes"]:
                    self.assertIn(node["label"], mobile)
                for edge in section["edges"]:
                    self.assertIn(edge["label"], mobile)
                self.assert_valid(artifact)

    def test_relation_edges_keep_declared_order(self):
        section = next(item for item in BASE_MODEL["sections"] if item["type"] == "flow")
        html = self.render(BASE_MODEL, section).html
        self.assertLess(html.index("核对"), html.index("执行"))
        self.assertLess(html.index("执行"), html.index("验收"))

    def test_relation_geometry_is_type_specific_and_stable(self):
        expected = {
            "flow": ('class="desktop-diagram diagram--flow"', 'translate(40 170)'),
            "timeline": ('class="desktop-diagram diagram--timeline"', 'translate(40 170)'),
            "layer-map": ('class="desktop-diagram diagram--layer-map"', 'translate(330 40)'),
            "boundary-map": ('class="desktop-diagram diagram--boundary-map"', 'class="diagram-boundary"'),
        }
        for section_type, tokens in expected.items():
            with self.subTest(section_type=section_type):
                section = next(
                    item for item in BASE_MODEL["sections"] if item["type"] == section_type
                )
                html = self.render(BASE_MODEL, section).html
                for token in tokens:
                    self.assertIn(token, html)

    def test_relation_nodes_use_fixed_semantic_kind_classes(self):
        html = "\n".join(
            self.render(BASE_MODEL, section).html
            for section in BASE_MODEL["sections"]
            if section["type"] in {"layer-map", "boundary-map", "flow", "timeline"}
        )
        colors = {
            "active": "--color-active",
            "success": "--color-success",
            "gate": "--color-gate",
            "risk": "--color-risk",
            "neutral": "--color-neutral",
        }
        for kind, color in colors.items():
            self.assertIn(f'diagram-node--{kind}', html)
            self.assertIn(f'stroke:var({color})', html)

    def test_relation_renderer_fails_closed_for_invalid_relationships(self):
        self.assertIsNotNone(render_relation, "the relationship renderer must exist")
        invalid = {
            "id": "broken-flow",
            "type": "flow",
            "title": "Broken relationship",
            "summary": "An undeclared endpoint must not be rendered.",
            "nodes": [{"id": "known", "label": "Known", "kind": "neutral"}],
            "edges": [{"from": "known", "to": "missing", "label": "Cannot continue"}],
        }
        with self.assertRaisesRegex(ValueError, "declared edge"):
            render_relation(invalid)

    def test_relation_rejects_disconnected_and_duplicate_graphs(self):
        self.assertIsNotNone(render_relation, "the relationship renderer must exist")
        section = {
            "id": "disconnected-flow",
            "type": "flow",
            "title": "Disconnected flow",
            "summary": "Every declared node must participate in one graph.",
            "nodes": [
                {"id": "first", "label": "First", "kind": "neutral"},
                {"id": "second", "label": "Second", "kind": "active"},
                {"id": "orphan", "label": "Orphan", "kind": "risk"},
            ],
            "edges": [{"from": "first", "to": "second", "label": "Connect"}],
        }
        with self.assertRaisesRegex(ValueError, "connected graph"):
            render_relation(section)

        duplicate = copy.deepcopy(section)
        duplicate["nodes"] = duplicate["nodes"][:2]
        duplicate["edges"].append({"from": "first", "to": "second", "label": "Repeat"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            render_relation(duplicate)

    def test_relation_geometry_never_overlaps_for_supported_node_counts(self):
        for section_type in ("flow", "timeline", "layer-map", "boundary-map"):
            for node_count in range(2, 11):
                with self.subTest(section_type=section_type, node_count=node_count):
                    nodes = [
                        {
                            "id": f"node-{index}",
                            "label": f"Node {index}",
                            "kind": ("neutral", "gate", "risk")[index % 3],
                            "group": f"Group {index % 2}",
                        }
                        for index in range(node_count)
                    ]
                    section = {
                        "id": f"{section_type}-{node_count}",
                        "type": section_type,
                        "title": f"{section_type} {node_count}",
                        "summary": "Deterministic node spacing.",
                        "nodes": nodes,
                        "edges": [
                            {
                                "from": nodes[index]["id"],
                                "to": nodes[index + 1]["id"],
                                "label": f"Step {index}",
                            }
                            for index in range(node_count - 1)
                        ],
                    }
                    html = render_relation(section)
                    positions = [
                        (int(x), int(y))
                        for x, y in re.findall(
                            r'<g class="diagram-node [^"]+" data-node-id="node-\d+" '
                            r'transform="translate\((\d+) (\d+)\)">',
                            html,
                        )
                    ]
                    self.assertEqual(node_count, len(positions))
                    for index, (left_x, top_y) in enumerate(positions):
                        for right_x, bottom_y in positions[index + 1 :]:
                            separated = (
                                left_x + 200 <= right_x
                                or right_x + 200 <= left_x
                                or top_y + 96 <= bottom_y
                                or bottom_y + 96 <= top_y
                            )
                            self.assertTrue(separated, (section_type, node_count, positions))
                    viewbox = re.search(r'viewBox="0 0 (\d+) (\d+)"', html)
                    self.assertIsNotNone(viewbox)
                    self.assertGreaterEqual(int(viewbox.group(1)), max(x + 200 for x, _ in positions))
                    self.assertGreaterEqual(int(viewbox.group(2)), max(y + 96 for _, y in positions))

    def test_relation_preserves_details_and_declared_edge_order_in_both_alternatives(self):
        self.assertIsNotNone(render_relation, "the relationship renderer must exist")
        section = {
            "id": "detail-flow",
            "type": "flow",
            "title": "Detailed flow",
            "summary": "Desktop and mobile retain every declared fact.",
            "nodes": [
                {"id": "one", "label": "One", "detail": "<detail & one>", "kind": "neutral"},
                {"id": "two", "label": "Two", "detail": "Second detail", "kind": "active"},
                {"id": "three", "label": "Three", "detail": "Third detail", "kind": "gate"},
            ],
            "edges": [
                {"from": "one", "to": "two", "label": "First edge"},
                {"from": "two", "to": "three", "label": "Second edge"},
            ],
        }
        html = render_relation(section)
        mobile = html.split('<ol class="mobile-semantic-flow">', 1)[1]
        for node in section["nodes"]:
            expected_detail = node["detail"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            self.assertEqual(2, html.count(expected_detail))
            self.assertIn(expected_detail, mobile)
            self.assertIn('class="diagram-node-kind"', html)
            self.assertIn(f'>{node["kind"]}</text>', html)
            self.assertIn(
                f'<span class="mobile-flow-kind">{node["kind"]}</span>', mobile
            )
        self.assertLess(mobile.index("First edge"), mobile.index("Second edge"))

    def test_boundary_map_uses_explicit_groups_and_kind_changes_do_not_regroup_nodes(self):
        self.assertIsNotNone(render_relation, "the relationship renderer must exist")
        boundary = next(
            section for section in BASE_MODEL["sections"] if section["type"] == "boundary-map"
        )
        html = render_relation(boundary)
        mobile = html.split('<ol class="mobile-semantic-flow">', 1)[1]
        groups = tuple(dict.fromkeys(node["group"] for node in boundary["nodes"]))
        for group in groups:
            self.assertIn('class="diagram-boundary-label"', html)
            self.assertIn(f'>{group}</text>', html)
            self.assertIn(f'<span class="mobile-flow-group">{group}</span>', mobile)

        changed_kinds = copy.deepcopy(boundary)
        for node in changed_kinds["nodes"]:
            node["kind"] = "success"
        changed_html = render_relation(changed_kinds)
        for group in groups:
            self.assertIn(f'>{group}</text>', changed_html)

        missing_group = copy.deepcopy(boundary)
        missing_group["nodes"][0].pop("group")
        with self.assertRaisesRegex(ValueError, "declared groups"):
            render_relation(missing_group)

    def test_relation_node_and_edge_labels_are_escaped(self):
        self.assertIsNotNone(render_relation, "the relationship renderer must exist")
        section = {
            "id": "escaped-flow",
            "type": "flow",
            "title": "Escaped labels",
            "summary": "Renderer output remains text-only.",
            "nodes": [
                {"id": "first", "label": "<first & node>", "kind": "neutral"},
                {"id": "second", "label": "<second & node>", "kind": "success"},
            ],
            "edges": [{"from": "first", "to": "second", "label": "<edge & label>"}],
        }
        html = render_relation(section)
        self.assertNotIn("<first & node>", html)
        self.assertNotIn("<edge & label>", html)
        self.assertIn("&lt;first &amp; node&gt;", html)
        self.assertIn("&lt;edge &amp; label&gt;", html)

    def test_relation_output_is_byte_identical_and_uses_slugged_accessibility_ids(self):
        self.assertIsNotNone(render_relation, "the relationship renderer must exist")
        section = {
            "id": "Day 01: Diagram!",
            "type": "timeline",
            "title": "<Safe title>",
            "summary": "Summary & evidence",
            "nodes": [
                {"id": "start", "label": "Start", "detail": "Evidence", "kind": "success"},
                {"id": "finish", "label": "Finish", "detail": "Result", "kind": "gate"},
            ],
            "edges": [{"from": "start", "to": "finish", "label": "Advance"}],
        }
        first = render_relation(section)
        second = render_relation(section)
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))
        self.assertIn('aria-labelledby="day-01-diagram-title day-01-diagram-desc"', first)
        self.assertIn('&lt;Safe title&gt;', first)
        self.assertIn('Summary &amp; evidence', first)

    def test_network_like_model_text_is_visible_without_failing_validation(self):
        model = copy.deepcopy(BASE_MODEL)
        model["requiredTerms"] = [
            "https://example.test/reference",
            "fetch",
            "WebSocket",
            "XMLHttpRequest",
        ]
        section = {
            "id": "safe-network-text",
            "type": "concept",
            "title": "fetch() is a word here",
            "summary": "WebSocket and XMLHttpRequest are names, not executable code.",
            "sourceRefs": ["https://example.test/reference"],
        }
        artifact = self.render(model, section)
        self.assertIn("https://example.test/reference", artifact.html)
        self.assertIn("fetch()", artifact.html)
        self.assertIn("WebSocket", artifact.html)
        self.assertIn("XMLHttpRequest", artifact.html)
        self.assertEqual(tuple(model["requiredTerms"]), artifact.required_terms)
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
