"""Render validated learning-companion lesson sections as offline HTML."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template
from typing import Any, Callable, Mapping

from lesson_model import RELATIONAL_TYPES, slugify


TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@dataclass(frozen=True)
class RenderedArtifact:
    id: str
    title: str
    profile: str
    relative_path: str
    html: str
    required_terms: tuple[str, ...]


def _text(value: object) -> str:
    """Return a model value safely for a text node."""
    return escape(str(value), quote=False)


def _source_list(section: Mapping[str, Any]) -> str:
    sources = section.get("sourceRefs", ())
    items = "".join(f"<li>{_text(source)}</li>" for source in sources)
    return f'<section class="panel"><h2>Sources</h2><ol class="source-list">{items}</ol></section>'


def required_terms_for_section(
    model: Mapping[str, Any], section: Mapping[str, Any]
) -> tuple[str, ...]:
    """Return declared terms evidenced by the section model, before rendering."""
    source_values: list[object] = [section["title"], section["summary"]]
    source_values.extend(section.get("sourceRefs", ()))
    source_values.extend(node["label"] for node in section.get("nodes", ()))
    source_values.extend(edge.get("label", "") for edge in section.get("edges", ()))
    source_text = "\n".join(str(value) for value in source_values)
    return tuple(term for term in model["requiredTerms"] if term in source_text)


def _section_shell(section: Mapping[str, Any], eyebrow: str, details: str = "") -> str:
    return (
        '<article class="lesson-card">'
        '<section class="panel" aria-labelledby="lesson-title">'
        f'<p class="eyebrow">{eyebrow}</p>'
        f'<h1 id="lesson-title">{_text(section["title"])}</h1>'
        f'<p class="summary">{_text(section["summary"])}</p>'
        f"{details}</section>{_source_list(section)}</article>"
    )


def render_hero(section: Mapping[str, Any]) -> str:
    return _section_shell(section, "Lesson briefing")


def render_concept(section: Mapping[str, Any]) -> str:
    details = '<div class="detail-grid"><section class="detail-panel detail-panel--active"><h2>Core concept</h2><p>Use this idea to distinguish a capable model from a dependable system.</p></section><section class="detail-panel detail-panel--success"><h2>Operational signal</h2><p>Look for evidence, accountable state, and a verifiable result.</p></section></div>'
    return _section_shell(section, "Concept", details)


def render_case_study(section: Mapping[str, Any]) -> str:
    details = '<div class="detail-grid"><section class="detail-panel detail-panel--active"><h2>Situation</h2><p>Frame the operating context before selecting an intervention.</p></section><section class="detail-panel detail-panel--success"><h2>Learning</h2><p>Connect the result to a repeatable systems decision.</p></section></div>'
    return _section_shell(section, "Case study", details)


def render_misconception(section: Mapping[str, Any]) -> str:
    details = '<div class="detail-grid"><section class="detail-panel"><h2>Common shortcut</h2><p>Treating a plausible answer as a completed outcome bypasses system controls.</p></section><section class="detail-panel detail-panel--gate"><h2>Better check</h2><p>Confirm the evidence, state transition, and approval path.</p></section></div>'
    return _section_shell(section, "Misconception", details)


def render_check_question(section: Mapping[str, Any]) -> str:
    details = '<section class="detail-panel detail-panel--gate"><h2>Reflection prompt</h2><p>Answer using an observable control or state transition.</p></section>'
    return _section_shell(section, "Check question", details)


def render_sources(section: Mapping[str, Any]) -> str:
    return _section_shell(section, "Source guide")


def _diagram(section: Mapping[str, Any]) -> str:
    nodes = tuple(section.get("nodes", ()))
    node_ids = {node["id"]: f"node-{index}" for index, node in enumerate(nodes)}
    node_labels = {node["id"]: node["label"] for node in nodes}
    positions = {
        node["id"]: (20 + (index % 3) * 210, 45 + (index // 3) * 95)
        for index, node in enumerate(nodes)
    }
    node_markup = "".join(
        '<g class="diagram-node" data-node-id="{identifier}" transform="translate({x} {y})">'
        '<rect width="180" height="54" rx="10"></rect>'
        '<text x="90" y="32" text-anchor="middle">{label}</text></g>'.format(
            identifier=node_ids[node["id"]],
            x=positions[node["id"]][0],
            y=positions[node["id"]][1],
            label=_text(node["label"]),
        )
        for index, node in enumerate(nodes)
    )
    declared_edges = tuple(
        edge
        for edge in section.get("edges", ())
        if edge["from"] in node_ids
        and edge["to"] in node_ids
        and edge["from"] != edge["to"]
    )
    if not declared_edges:
        raise ValueError("relational section requires a declared edge between distinct nodes")
    edge_markup = "".join(
        '<path class="diagram-edge" data-edge-from="{source}" data-edge-to="{target}" d="M {start_x} {start_y} L {end_x} {end_y}"></path>'
        '<text class="diagram-edge-label" x="{label_x}" y="{label_y}">{label}</text>'.format(
            source=node_ids[edge["from"]],
            target=node_ids[edge["to"]],
            start_x=positions[edge["from"]][0] + 180,
            start_y=positions[edge["from"]][1] + 27,
            end_x=positions[edge["to"]][0],
            end_y=positions[edge["to"]][1] + 27,
            label_x=(positions[edge["from"]][0] + 180 + positions[edge["to"]][0]) // 2,
            label_y=(positions[edge["from"]][1] + positions[edge["to"]][1] + 54) // 2,
            label=_text(edge.get("label", "")),
        )
        for edge in declared_edges
    )
    description = "; ".join(
        "{} {} {}".format(
            node_labels[edge["from"]],
            edge.get("label") or "connects to",
            node_labels[edge["to"]],
        )
        for edge in declared_edges
    )
    return (
        '<article class="lesson-card"><section class="panel technical-visual" aria-labelledby="lesson-title">'
        '<p class="eyebrow">Systems relationship</p>'
        f'<h1 id="lesson-title">{_text(section["title"])}</h1>'
        f'<p class="summary">{_text(section["summary"])}</p>'
        '<svg role="img" viewBox="0 0 660 360" aria-labelledby="diagram-title diagram-description">'
        f'<title id="diagram-title">{_text(section["title"])}</title>'
        f'<desc id="diagram-description">{_text(description)}</desc>'
        f"{edge_markup}{node_markup}</svg></section>{_source_list(section)}</article>"
    )


ALL_RENDERERS: dict[str, Callable[[Mapping[str, Any]], str]] = {
    "hero": render_hero,
    "concept": render_concept,
    "layer-map": _diagram,
    "boundary-map": _diagram,
    "flow": _diagram,
    "timeline": _diagram,
    "case-study": render_case_study,
    "misconception": render_misconception,
    "check-question": render_check_question,
    "sources": render_sources,
}


def render_template(name: str, **values: str) -> str:
    """Fill a fixed renderer-owned template without evaluating model markup."""
    return Template((TEMPLATES / name).read_text(encoding="utf-8")).substitute(values)


def render_section(
    model: Mapping[str, Any], section: Mapping[str, Any], theme_css: str
) -> RenderedArtifact:
    """Render one already-validated lesson section into a stable offline artifact."""
    section_type = section["type"]
    renderer = ALL_RENDERERS.get(section_type)
    if renderer is None:
        raise ValueError(f"unsupported section type: {section_type}")

    body = renderer(section)
    profile = "technical-visual" if section_type in RELATIONAL_TYPES else "document"
    footer = _text(f"{model['session']['topic']} · Day {model['session']['day']:02d}")
    html = render_template(
        "lesson-technical-visual.html" if profile == "technical-visual" else "lesson-document.html",
        title=_text(section["title"]),
        theme_css=theme_css,
        body=body,
        footer=footer,
    )
    return RenderedArtifact(
        id=section["id"],
        title=section["title"],
        profile=profile,
        relative_path=f"cards/{slugify(section['id'])}.html",
        html=html,
        required_terms=required_terms_for_section(model, section),
    )
