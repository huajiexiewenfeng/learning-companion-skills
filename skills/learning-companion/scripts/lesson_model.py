"""Canonical, dependency-free validation for learning companion lesson models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "learning-companion.lesson-model.v1"
COMPONENT_TYPES = frozenset(
    {
        "hero",
        "concept",
        "layer-map",
        "boundary-map",
        "flow",
        "timeline",
        "case-study",
        "misconception",
        "check-question",
        "sources",
    }
)
RELATIONAL_TYPES = frozenset({"layer-map", "boundary-map", "flow", "timeline"})
SESSION_MODES = frozenset({"text", "voice", "hybrid"})
SESSION_DEPTHS = frozenset({"shallow", "medium", "deep"})
SESSION_STATUSES = frozenset(
    {"preparing", "ready", "in-progress", "completed", "archived"}
)
MODEL_KEYS = frozenset(
    {"schemaVersion", "session", "theme", "question", "requiredTerms", "decks", "sections"}
)
SESSION_KEYS = frozenset({"id", "planId", "day", "topic", "mode", "depth", "status"})
DECK_KEYS = frozenset({"id", "title", "sectionIds"})
SECTION_KEYS = frozenset({"id", "type", "title", "summary", "nodes", "edges", "sourceRefs"})
NODE_KEYS = frozenset({"id", "label", "kind"})
EDGE_KEYS = frozenset({"from", "to", "label"})


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def load_lesson_model(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON lesson model, requiring an object at its root."""
    with path.open(encoding="utf-8") as source:
        data = json.load(source)
    if not isinstance(data, dict):
        raise ValueError("lesson model root must be a JSON object")
    return data


def required_terms(data: Mapping[str, Any]) -> tuple[str, ...]:
    """Return declared required terms in author-provided order."""
    terms = data.get("requiredTerms", ())
    if not isinstance(terms, (list, tuple)):
        return ()
    return tuple(term for term in terms if isinstance(term, str))


def slugify(value: str) -> str:
    """Produce a stable ASCII identifier suitable for lesson and deck IDs."""
    normalized = value.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def validate_lesson_model(data: Mapping[str, Any]) -> tuple[ValidationIssue, ...]:
    """Validate deterministic rendering inputs without accepting raw fallbacks."""
    issues: list[ValidationIssue] = []

    if not isinstance(data, Mapping):
        return (ValidationIssue("model-type", "$", "expected an object"),)

    _validate_extra_properties(data, MODEL_KEYS, "$", "model", issues)
    if data.get("schemaVersion") != SCHEMA_VERSION:
        issues.append(ValidationIssue("schema-version", "schemaVersion", "expected v1"))

    _validate_session(data.get("session"), issues)
    _validate_nonempty_string(data.get("theme"), "theme", "theme-required", issues)
    _validate_nonempty_string(data.get("question"), "question", "question-required", issues)
    _validate_required_terms(data.get("requiredTerms"), issues)

    section_ids = _validate_sections(data.get("sections"), issues)
    if "decks" in data:
        _validate_decks(data["decks"], section_ids, issues)
    return tuple(issues)


def _validate_session(session: Any, issues: list[ValidationIssue]) -> None:
    if not isinstance(session, Mapping):
        issues.append(ValidationIssue("session-required", "session", "expected an object"))
        return

    _validate_extra_properties(session, SESSION_KEYS, "session", "session", issues)
    for field in ("id", "planId", "topic"):
        _validate_nonempty_string(
            session.get(field), f"session.{field}", "session-field-required", issues
        )

    day = session.get("day")
    if not isinstance(day, int) or isinstance(day, bool) or day < 1:
        issues.append(ValidationIssue("session-day", "session.day", "expected a positive integer"))

    _validate_enum(session.get("mode"), "session.mode", SESSION_MODES, "session-mode", issues)
    _validate_enum(session.get("depth"), "session.depth", SESSION_DEPTHS, "session-depth", issues)
    _validate_enum(
        session.get("status"), "session.status", SESSION_STATUSES, "session-status", issues
    )


def _validate_required_terms(terms: Any, issues: list[ValidationIssue]) -> None:
    if not isinstance(terms, list) or not terms:
        issues.append(
            ValidationIssue("required-terms-empty", "requiredTerms", "expected a nonempty list")
        )
        return

    seen: set[str] = set()
    for index, term in enumerate(terms):
        path = f"requiredTerms[{index}]"
        if not isinstance(term, str) or not term.strip():
            issues.append(ValidationIssue("required-term-invalid", path, "expected a nonempty string"))
        elif term in seen:
            issues.append(ValidationIssue("required-term-duplicate", path, "duplicate term"))
        else:
            seen.add(term)


def _validate_sections(sections: Any, issues: list[ValidationIssue]) -> set[str]:
    if not isinstance(sections, list) or not sections:
        issues.append(ValidationIssue("sections-empty", "sections", "expected a nonempty list"))
        return set()

    section_ids: set[str] = set()
    for index, section in enumerate(sections):
        path = f"sections[{index}]"
        if not isinstance(section, Mapping):
            issues.append(ValidationIssue("section-invalid", path, "expected an object"))
            continue

        _validate_extra_properties(section, SECTION_KEYS, path, "section", issues)
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id.strip():
            issues.append(ValidationIssue("section-id-invalid", f"{path}.id", "expected an ID"))
        elif section_id in section_ids:
            issues.append(ValidationIssue("section-id-duplicate", f"{path}.id", "duplicate ID"))
        else:
            section_ids.add(section_id)

        component_type = section.get("type")
        if not isinstance(component_type, str) or component_type not in COMPONENT_TYPES:
            issues.append(
                ValidationIssue("unknown-component", f"{path}.type", str(component_type))
            )
            continue

        _validate_nonempty_string(section.get("title"), f"{path}.title", "section-title", issues)
        _validate_nonempty_string(
            section.get("summary"), f"{path}.summary", "section-summary", issues
        )
        _validate_source_refs(section.get("sourceRefs"), f"{path}.sourceRefs", issues)

        _validate_relations(section, path, component_type in RELATIONAL_TYPES, issues)

    return section_ids


def _validate_source_refs(source_refs: Any, path: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(source_refs, list) or not source_refs:
        issues.append(ValidationIssue("sources-empty", path, "expected at least one source reference"))
        return
    for index, source_ref in enumerate(source_refs):
        if not isinstance(source_ref, str) or not source_ref.strip():
            issues.append(
                ValidationIssue("source-ref-invalid", f"{path}[{index}]", "expected a source reference")
            )


def _validate_relations(
    section: Mapping[str, Any], path: str, relational: bool, issues: list[ValidationIssue]
) -> None:
    if "nodes" not in section:
        if relational:
            issues.append(ValidationIssue("nodes-empty", f"{path}.nodes", "expected at least one node"))
        node_ids: set[str] = set()
    elif not isinstance(section["nodes"], list):
        issues.append(ValidationIssue("nodes-invalid", f"{path}.nodes", "expected a list"))
        node_ids = set()
    elif relational and not section["nodes"]:
        issues.append(ValidationIssue("nodes-empty", f"{path}.nodes", "expected at least one node"))
        node_ids = set()
    else:
        node_ids = set()
        for node_index, node in enumerate(section["nodes"]):
            node_path = f"{path}.nodes[{node_index}]"
            if not isinstance(node, Mapping):
                issues.append(ValidationIssue("node-invalid", node_path, "expected an object"))
                continue
            _validate_extra_properties(node, NODE_KEYS, node_path, "node", issues)
            node_id = node.get("id")
            if not isinstance(node_id, str) or not node_id.strip():
                issues.append(ValidationIssue("node-id-invalid", f"{node_path}.id", "expected an ID"))
            elif node_id in node_ids:
                issues.append(ValidationIssue("node-id-duplicate", f"{node_path}.id", "duplicate ID"))
            else:
                node_ids.add(node_id)
            _validate_nonempty_string(
                node.get("label"), f"{node_path}.label", "node-label-required", issues
            )
            _validate_nonempty_string(
                node.get("kind"), f"{node_path}.kind", "node-kind-required", issues
            )

    if "edges" not in section:
        if relational:
            issues.append(ValidationIssue("edges-invalid", f"{path}.edges", "expected a list"))
        return
    if not isinstance(section["edges"], list):
        issues.append(ValidationIssue("edges-invalid", f"{path}.edges", "expected a list"))
        return
    for edge_index, edge in enumerate(section["edges"]):
        edge_path = f"{path}.edges[{edge_index}]"
        if not isinstance(edge, Mapping):
            issues.append(ValidationIssue("edge-invalid", edge_path, "expected an object"))
            continue
        _validate_extra_properties(edge, EDGE_KEYS, edge_path, "edge", issues)
        source = edge.get("from")
        target = edge.get("to")
        if not isinstance(source, str) or not source.strip():
            issues.append(ValidationIssue("edge-source-invalid", edge_path, "expected a source ID"))
        elif source not in node_ids:
            issues.append(
                ValidationIssue("edge-source-missing", edge_path, "missing source")
            )
        if not isinstance(target, str) or not target.strip():
            issues.append(ValidationIssue("edge-target-invalid", edge_path, "expected a target ID"))
        elif target not in node_ids:
            issues.append(
                ValidationIssue("edge-target-missing", edge_path, "missing target")
            )
        if "label" in edge and not isinstance(edge["label"], str):
            issues.append(ValidationIssue("edge-label-invalid", f"{edge_path}.label", "expected a string"))


def _validate_decks(
    decks: Any, section_ids: set[str], issues: list[ValidationIssue]
) -> None:
    if not isinstance(decks, list):
        issues.append(ValidationIssue("decks-invalid", "decks", "expected a list"))
        return

    deck_ids: set[str] = set()
    titles: set[str] = set()
    for index, deck in enumerate(decks):
        path = f"decks[{index}]"
        if not isinstance(deck, Mapping):
            issues.append(ValidationIssue("deck-invalid", path, "expected an object"))
            continue
        _validate_extra_properties(deck, DECK_KEYS, path, "deck", issues)
        _validate_unique_value(deck.get("id"), f"{path}.id", deck_ids, "deck-id", issues)
        _validate_unique_value(deck.get("title"), f"{path}.title", titles, "deck-title", issues)

        section_ids_value = deck.get("sectionIds")
        if not isinstance(section_ids_value, list) or not section_ids_value:
            issues.append(
                ValidationIssue("deck-section-ids", f"{path}.sectionIds", "expected an ordered list")
            )
            continue
        for section_index, section_id in enumerate(section_ids_value):
            section_path = f"{path}.sectionIds[{section_index}]"
            if not isinstance(section_id, str) or not section_id.strip():
                issues.append(
                    ValidationIssue("deck-section-id-invalid", section_path, "expected a section ID")
                )
            elif section_id not in section_ids:
                issues.append(
                    ValidationIssue("deck-section-missing", section_path, "section does not exist")
                )


def _validate_nonempty_string(
    value: Any, path: str, code: str, issues: list[ValidationIssue]
) -> None:
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(code, path, "expected a nonempty string"))


def _validate_enum(
    value: Any,
    path: str,
    allowed: frozenset[str],
    code: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(value, str) or value not in allowed:
        issues.append(ValidationIssue(code, path, f"expected one of {', '.join(sorted(allowed))}"))


def _validate_unique_value(
    value: Any, path: str, seen: set[str], code: str, issues: list[ValidationIssue]
) -> None:
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(f"{code}-invalid", path, "expected a nonempty string"))
    elif value in seen:
        issues.append(ValidationIssue(f"{code}-duplicate", path, "duplicate value"))
    else:
        seen.add(value)


def _validate_extra_properties(
    value: Mapping[str, Any], allowed: frozenset[str], path: str, kind: str, issues: list[ValidationIssue]
) -> None:
    for property_name in value:
        if property_name not in allowed:
            issues.append(
                ValidationIssue(
                    f"{kind}-extra-property",
                    f"{path}.{property_name}" if path != "$" else property_name,
                    "unexpected property",
                )
            )
