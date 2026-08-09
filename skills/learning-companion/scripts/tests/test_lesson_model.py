import copy
import json
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from lesson_model import load_lesson_model, required_terms, slugify, validate_lesson_model


FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA = SCRIPT_DIR.parent / "references" / "lesson-model.schema.json"


class LessonModelTest(unittest.TestCase):
    def valid_model(self):
        return load_lesson_model(FIXTURES / "valid-lesson-model.json")

    def issue_codes(self, model):
        return {issue.code for issue in validate_lesson_model(model)}

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

    def test_schema_declares_optional_node_detail_and_group(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        node = schema["$defs"]["node"]
        self.assertEqual({"type": "string"}, node["properties"]["detail"])
        self.assertEqual({"type": "string"}, node["properties"]["group"])
        self.assertNotIn("detail", node["required"])
        self.assertNotIn("group", node["required"])

    def test_node_detail_and_group_validator_contract(self):
        valid_without_optional_node_facts = self.valid_model()
        valid_without_optional_node_facts["sections"][1]["nodes"][0].pop("detail")
        self.assertNotIn(
            "node-detail-invalid", self.issue_codes(valid_without_optional_node_facts)
        )

        cases = (
            ("detail non-string", "detail", 1, "node-detail-invalid"),
            ("group non-string", "group", 1, "node-group-invalid"),
        )
        for name, field, value, expected_code in cases:
            with self.subTest(name=name):
                model = self.valid_model()
                model["sections"][1]["nodes"][0][field] = value
                self.assertIn(expected_code, self.issue_codes(model))

    def test_boundary_groups_are_required_and_distinct(self):
        boundary_index = next(
            index
            for index, section in enumerate(self.valid_model()["sections"])
            if section["type"] == "boundary-map"
        )
        missing_group = self.valid_model()
        missing_group["sections"][boundary_index]["nodes"][0].pop("group")
        self.assertIn("boundary-group-required", self.issue_codes(missing_group))

        one_group = self.valid_model()
        for node in one_group["sections"][boundary_index]["nodes"]:
            node["group"] = "same-boundary"
        self.assertIn("boundary-groups-insufficient", self.issue_codes(one_group))

    def test_malformed_values_return_issues_without_raising(self):
        cases = (
            ("component mapping", lambda model: model["sections"][0].update(type={}), "unknown-component"),
            ("mode list", lambda model: model["session"].update(mode=[]), "session-mode"),
            ("term mapping", lambda model: model.update(requiredTerms=[{}]), "required-term-invalid"),
            ("edge mapping", lambda model: model["sections"][1]["edges"][0].update(**{"from": {}}), "edge-source-invalid"),
            ("deck reference list", lambda model: model["decks"][0]["sectionIds"].append([]), "deck-section-id-invalid"),
        )
        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                model = self.valid_model()
                mutate(model)
                self.assertIn(expected_code, self.issue_codes(model))

    def test_validator_enforces_schema_object_constraints(self):
        cases = (
            ("top level raw html", lambda model: model.update(rawHtml="<script>"), "model-extra-property"),
            ("section raw html", lambda model: model["sections"][0].update(rawHtml="<div>"), "section-extra-property"),
            ("session extra", lambda model: model["session"].update(rawHtml="<div>"), "session-extra-property"),
            ("node missing label", lambda model: model["sections"][1]["nodes"][0].pop("label"), "node-label-required"),
            ("node missing kind", lambda model: model["sections"][1]["nodes"][0].pop("kind"), "node-kind-required"),
            ("concept null nodes", lambda model: model["sections"][0].update(nodes=None), "nodes-invalid"),
            ("concept null edges", lambda model: model["sections"][0].update(edges=None), "edges-invalid"),
            ("edge missing from", lambda model: model["sections"][1]["edges"][0].pop("from"), "edge-source-invalid"),
            ("edge missing to", lambda model: model["sections"][1]["edges"][0].pop("to"), "edge-target-invalid"),
        )
        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                model = self.valid_model()
                mutate(model)
                self.assertIn(expected_code, self.issue_codes(model))

    def test_required_terms_and_session_enum_constraints(self):
        cases = (
            ("no terms", lambda model: model.update(requiredTerms=[]), "required-terms-empty"),
            ("duplicate term", lambda model: model.update(requiredTerms=["one", "one"]), "required-term-duplicate"),
            ("bad mode", lambda model: model["session"].update(mode="video"), "session-mode"),
            ("bad depth", lambda model: model["session"].update(depth="brief"), "session-depth"),
            ("bad status", lambda model: model["session"].update(status="draft"), "session-status"),
        )
        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                model = self.valid_model()
                mutate(model)
                self.assertIn(expected_code, self.issue_codes(model))

    def test_decks_are_optional_but_not_nullable(self):
        model_without_decks = self.valid_model()
        model_without_decks.pop("decks")
        self.assertEqual(set(), self.issue_codes(model_without_decks))

        model_with_null_decks = self.valid_model()
        model_with_null_decks["decks"] = None
        self.assertIn("decks-invalid", self.issue_codes(model_with_null_decks))

    def test_source_id_and_deck_reference_constraints(self):
        cases = (
            ("empty source refs", lambda model: model["sections"][0].update(sourceRefs=[]), "sources-empty"),
            ("duplicate section id", lambda model: model["sections"][1].update(id="core-concept"), "section-id-duplicate"),
            ("duplicate node id", lambda model: model["sections"][1]["nodes"][1].update(id="model"), "node-id-duplicate"),
            ("duplicate deck id", lambda model: model["decks"].append(copy.deepcopy(model["decks"][0])), "deck-id-duplicate"),
            ("duplicate deck title", lambda model: model["decks"].append({"id": "other-deck", "title": model["decks"][0]["title"], "sectionIds": ["core-concept"]}), "deck-title-duplicate"),
            ("missing deck section", lambda model: model["decks"][0].update(sectionIds=["missing"]), "deck-section-missing"),
        )
        for name, mutate, expected_code in cases:
            with self.subTest(name=name):
                model = self.valid_model()
                mutate(model)
                self.assertIn(expected_code, self.issue_codes(model))


if __name__ == "__main__":
    unittest.main()
