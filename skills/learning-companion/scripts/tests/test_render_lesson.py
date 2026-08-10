import copy
import re
import tempfile
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from lesson_model import load_lesson_model, validate_lesson_model
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

try:
    from render_lesson import render_hub
except ImportError:
    render_hub = None

try:
    from validate_lesson_html import HUB_ACTIVE_STATUSES
except ImportError:
    HUB_ACTIVE_STATUSES = ()

FIXTURES = Path(__file__).parent / "fixtures"
ASSETS = SCRIPT_DIR.parent / "assets"
THEME = ASSETS / "lesson-theme.css"
REPOSITORY_ROOT = SCRIPT_DIR.parents[2]
GOLDEN_MODEL = REPOSITORY_ROOT / "examples" / "technical-learning" / "lessons" / "day-01-system-layers" / "lesson-model.json"
BASE_MODEL = load_lesson_model(FIXTURES / "valid-lesson-model.json")
HUB_ARTIFACTS = (
    {"id": "answer", "type": "answer", "title": "Answer", "summary": "State the answer.", "path": "cards/007-answer.html", "order": 7},
    {"id": "conclusion", "type": "conclusion", "title": "Conclusion", "summary": "State the outcome.", "path": "cards/001-conclusion.html", "order": 1},
    {"id": "visual", "type": "visual", "title": "Responsibility map", "summary": "Show the boundaries.", "path": "visuals/001-responsibility-map.html", "order": 5},
    {"id": "explanation", "type": "explanation", "title": "Explanation", "summary": "Explain the evidence.", "path": "cards/002-explanation.html", "order": 2},
    {"id": "case", "type": "case", "title": "Case", "summary": "Apply the rule.", "path": "cards/003-case.html", "order": 3},
    {"id": "misconception", "type": "misconception", "title": "Misconception", "summary": "Avoid the shortcut.", "path": "cards/004-misconception.html", "order": 4},
    {"id": "check", "type": "check", "title": "Check", "summary": "Confirm the transition.", "path": "cards/006-check.html", "order": 6},
    {"id": "correction", "type": "correction", "title": "Correction", "summary": "Correct the record.", "path": "cards/008-correction.html", "order": 8},
)


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

    def render_hub_html(
        self, status, model=BASE_MODEL, artifacts=HUB_ARTIFACTS, sync_status="synced"
    ):
        self.assertIsNotNone(render_hub, "the lesson hub renderer must exist")
        return render_hub(model, artifacts, status, self.theme_css(), sync_status)

    def test_active_hub_uses_allowlisted_refresh_and_timeline_layout(self):
        html = self.render_hub_html("studying")
        self.assertIsInstance(html, str)
        self.assertIn('id="lesson-data" type="application/json"', html)
        self.assertIn('id="lesson-refresh" data-contract="v1"', html)
        self.assertIn("5000", html)
        for token in ("Day 01", "text", "medium", "studying", "Turn outline", "Unsynced changes"):
            self.assertIn(token, html)
        for artifact in HUB_ARTIFACTS:
            self.assertIn(artifact["path"], html)
            self.assertIn(f'card--{artifact["type"]}', html)
        self.assertLess(html.index("cards/001-conclusion.html"), html.index("cards/008-correction.html"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text(html, encoding="utf-8", newline="\n")
            report = validate_html(path, ("企业 AI 系统分层",), "hub")
        self.assertEqual("passed", report["overall"], report["errors"])

    def test_lifecycle_and_sync_status_are_independent_hub_fields(self):
        for status in ("awaiting-voice", "studying"):
            with self.subTest(status=status):
                self.assertIn('id="lesson-refresh"', self.render_hub_html(status))
        closed = self.render_hub_html("closed")
        self.assertNotIn('id="lesson-refresh"', closed)
        self.assertIn("visuals/001-responsibility-map.html", closed)

        unsynced = self.render_hub_html("studying", sync_status="unsynced")
        self.assertIn('"status":"studying"', unsynced)
        self.assertIn('"syncStatus":"unsynced"', unsynced)
        self.assertIn("Unsynced changes: sync required", unsynced)
        self.assertNotIn("Unsynced changes: none", unsynced)
        with self.assertRaisesRegex(ValueError, "hub status"):
            self.render_hub_html("unsynced")

    def test_hub_renderer_rejects_unknown_or_whitespace_variant_statuses(self):
        for status in ("unknown", "closed ", " studying"):
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, "hub status"):
                    self.render_hub_html(status)

    def test_hub_data_json_cannot_break_out_of_its_script_element(self):
        model = copy.deepcopy(BASE_MODEL)
        model["session"]["topic"] = "</script><script>alert(1)</script>\u2028\u2029"
        html = self.render_hub_html("studying", model)
        payload = html.split('<script id="lesson-data" type="application/json">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("</script", payload.lower())
        self.assertNotIn("\u2028", payload)
        self.assertNotIn("\u2029", payload)
        self.assertIn("&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;", html.split('<script id="lesson-data"', 1)[0])

    def test_hub_rendering_is_deterministic_and_rejects_unsafe_artifact_paths(self):
        first = self.render_hub_html("studying")
        second = self.render_hub_html("studying")
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))
        unsafe = HUB_ARTIFACTS + ({"id": "escape", "type": "answer", "title": "Bad", "summary": "Bad", "path": "../escape.html", "order": 9},)
        with self.assertRaisesRegex(ValueError, "contained artifact path"):
            self.render_hub_html("studying", artifacts=unsafe)

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
                desktop = artifact.html.split("<svg", 1)[1].split("</svg>", 1)[0]
                mobile = artifact.html.split('<ol class="mobile-semantic-flow">', 1)[1]
                for node in section["nodes"]:
                    self.assertIn(node["label"], mobile)
                    if "detail" in node:
                        self.assertIn(node["detail"], desktop)
                        self.assertIn(node["detail"], mobile)
                for edge in section["edges"]:
                    self.assertIn(edge["label"], mobile)
                self.assert_valid(artifact)

    def test_relation_edges_keep_declared_order(self):
        section = next(item for item in BASE_MODEL["sections"] if item["type"] == "flow")
        html = self.render(BASE_MODEL, section).html
        self.assertLess(html.index("核对"), html.index("执行"))
        self.assertLess(html.index("执行"), html.index("验收"))

    def test_theme_gives_boundary_diagrams_semantic_visible_paint_in_each_color_scheme(self):
        css = self.theme_css()
        self.assertIn(
            ".diagram-boundary { fill: var(--color-panel); stroke: var(--color-line); stroke-width: 1.5; }",
            css,
        )
        self.assertIn(
            ".diagram-boundary-label { fill: var(--color-ink); font-family: system-ui, sans-serif; font-size: 14px; font-weight: 750; }",
            css,
        )
        dark_mode = css.split("@media (prefers-color-scheme: dark)", 1)[1]
        self.assertIn(
            ".diagram-boundary { fill: var(--color-panel); stroke: var(--color-line); }",
            dark_mode,
        )
        self.assertIn(".diagram-boundary-label { fill: var(--color-ink); }", dark_mode)

    def test_theme_uses_one_relationship_representation_per_viewport_and_restores_svg_for_print(self):
        css = self.theme_css()
        self.assertIn(".desktop-diagram { display: block; }", css)
        self.assertIn(".mobile-semantic-flow { display: none; }", css)
        narrow = css.split("@media (max-width: 720px)", 1)[1].split("@media (prefers-color-scheme: dark)", 1)[0]
        self.assertIn(".desktop-diagram { display: none; }", narrow)
        self.assertIn(".technical-visual .desktop-diagram { display: none; }", narrow)
        self.assertIn(".mobile-semantic-flow { display: grid; }", narrow)
        printed = css.split("@media print", 1)[1]
        self.assertIn(".desktop-diagram { display: block; }", printed)
        self.assertIn(".technical-visual .desktop-diagram { display: block; }", printed)
        self.assertIn(".mobile-semantic-flow { display: none; }", printed)

    def test_theme_uses_a_panel_backplate_and_centered_edge_labels(self):
        css = self.theme_css()
        self.assertIn(
            ".diagram-edge-label-backplate { fill: var(--color-panel); stroke: none; }",
            css,
        )
        self.assertIn(
            ".diagram-edge-label { fill: var(--color-ink); font-family: system-ui, sans-serif; font-size: 14px; font-weight: 750; text-anchor: middle; paint-order: stroke fill; stroke: var(--color-panel); stroke-width: 6px; stroke-linejoin: round; }",
            css,
        )

    def test_golden_responsibility_map_and_delivery_flow_keep_label_backplates_outside_nodes(self):
        self.assertTrue(GOLDEN_MODEL.is_file(), "the Day 1 golden model must be available")
        model = load_lesson_model(GOLDEN_MODEL)
        for section_id in ("responsibility-map", "reliable-delivery-flow"):
            with self.subTest(section_id=section_id):
                section = next(item for item in model["sections"] if item["id"] == section_id)
                html = render_relation(section)
                nodes = [
                    tuple(map(int, position))
                    for position in re.findall(
                        r'<g class="diagram-node [^"]+" data-node-id="node-\d+" '
                        r'transform="translate\((\d+) (\d+)\)">',
                        html,
                    )
                ]
                labels = [
                    tuple(map(int, geometry))
                    for geometry in re.findall(
                        r'<g class="diagram-edge-label-group" transform="translate\((\d+) (\d+)\)">'
                        r'<rect class="diagram-edge-label-backplate" x="(-?\d+)" y="(-?\d+)" '
                        r'width="(\d+)" height="(\d+)" rx="8"></rect>',
                        html,
                    )
                ]
                self.assertEqual(len(section["edges"]), len(labels))
                for center_x, center_y, offset_x, offset_y, width, height in labels:
                    label_left = center_x + offset_x
                    label_top = center_y + offset_y
                    for node_left, node_top in nodes:
                        overlaps = (
                            label_left < node_left + 200
                            and label_left + width > node_left
                            and label_top < node_top + 96
                            and label_top + height > node_top
                        )
                        self.assertFalse(
                            overlaps,
                            (section_id, (label_left, label_top, width, height), (node_left, node_top)),
                        )

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

    def test_canonical_validator_and_renderer_reject_the_same_relation_failures(self):
        flow = next(item for item in BASE_MODEL["sections"] if item["type"] == "flow")
        cases = (
            ("empty edges", lambda section: section.update(edges=[])),
            (
                "self loop",
                lambda section: section["edges"].append(
                    {"from": "model", "to": "model", "label": "loop"}
                ),
            ),
            (
                "duplicate",
                lambda section: section["edges"].append(copy.deepcopy(section["edges"][0])),
            ),
            (
                "disconnected",
                lambda section: section["nodes"].append(
                    {"id": "orphan", "label": "Orphan", "kind": "risk"}
                ),
            ),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                model = copy.deepcopy(BASE_MODEL)
                section = next(item for item in model["sections"] if item["id"] == flow["id"])
                mutate(section)
                self.assertTrue(validate_lesson_model(model))
                with self.assertRaises(ValueError):
                    render_relation(section)

    def test_nonadjacent_flow_connector_routes_around_intermediate_node(self):
        section = {
            "id": "routed-flow",
            "type": "flow",
            "title": "Routed flow",
            "summary": "A nonadjacent connector must not cross the middle node.",
            "nodes": [
                {"id": "first", "label": "First", "kind": "neutral"},
                {"id": "middle", "label": "Middle", "kind": "active"},
                {"id": "last", "label": "Last", "kind": "gate"},
            ],
            "edges": [
                {"from": "first", "to": "middle", "label": "Adjacent"},
                {"from": "first", "to": "last", "label": "Skip"},
            ],
        }

        html = render_relation(section)

        routed = re.search(
            r'data-edge-from="node-0" data-edge-to="node-2"[^>]+d="([^"]+)"', html
        )
        self.assertIsNotNone(routed)
        points = [
            tuple(map(int, point))
            for point in re.findall(r"(?:M|L) (-?\d+) (-?\d+)", routed.group(1))
        ]
        self.assertGreaterEqual(len(points), 4, routed.group(1))
        middle_left, middle_top = map(
            int,
            re.search(
                r'data-node-id="node-1" transform="translate\((\d+) (\d+)\)"', html
            ).groups(),
        )
        for (start_x, start_y), (end_x, end_y) in zip(points, points[1:]):
            if start_x == end_x:
                crosses = (
                    middle_left < start_x < middle_left + 200
                    and min(start_y, end_y) < middle_top + 96
                    and max(start_y, end_y) > middle_top
                )
            elif start_y == end_y:
                crosses = (
                    middle_top < start_y < middle_top + 96
                    and min(start_x, end_x) < middle_left + 200
                    and max(start_x, end_x) > middle_left
                )
            else:
                self.fail(f"connector segment is not orthogonal: {routed.group(1)}")
            self.assertFalse(crosses, (routed.group(1), (middle_left, middle_top)))

    def test_relation_geometry_never_overlaps_for_supported_node_counts(self):
        for section_type in ("flow", "timeline", "layer-map", "boundary-map"):
            for node_count in range(2, 11):
                with self.subTest(section_type=section_type, node_count=node_count):
                    nodes = [
                        {
                            "id": f"node-{index}",
                            "label": f"Node {index}",
                            "kind": ("neutral", "gate", "risk")[index % 3],
                            **(
                                {"group": f"Group {index % 2}"}
                                if section_type == "boundary-map"
                                else {}
                            ),
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
            self.assertEqual(
                sum(node["group"] == group for node in boundary["nodes"]),
                mobile.count(f'<span class="mobile-flow-group">{group}</span>'),
            )
        group_bounds = {
            label: tuple(map(int, (left, top, width, height)))
            for left, top, width, height, label in re.findall(
                r'<g class="diagram-boundary-group"><rect class="diagram-boundary" '
                r'x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)" rx="20"></rect>'
                r'<text class="diagram-boundary-label" x="\d+" y="72">([^<]+)</text></g>',
                html,
            )
        }
        for node_index, node in enumerate(boundary["nodes"]):
            left, top, width, height = group_bounds[node["group"]]
            position = re.search(
                rf'data-node-id="node-{node_index}" transform="translate\((\d+) (\d+)\)"',
                html,
            )
            self.assertIsNotNone(position)
            node_left, node_top = map(int, position.groups())
            self.assertGreaterEqual(node_left, left)
            self.assertGreaterEqual(node_top, top)
            self.assertLessEqual(node_left + 200, left + width)
            self.assertLessEqual(node_top + 96, top + height)

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

        non_boundary_group = next(
            section for section in BASE_MODEL["sections"] if section["type"] == "flow"
        )
        non_boundary_group = copy.deepcopy(non_boundary_group)
        non_boundary_group["nodes"][0]["group"] = "not-a-boundary"
        with self.assertRaisesRegex(ValueError, "only boundary-map"):
            render_relation(non_boundary_group)

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
