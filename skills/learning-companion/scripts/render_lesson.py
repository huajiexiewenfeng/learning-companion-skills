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
    source_values.extend(node.get("detail", "") for node in section.get("nodes", ()))
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


NODE_WIDTH = 200
NODE_HEIGHT = 96
NODE_GAP = 40
SEMANTIC_KINDS = frozenset({"active", "success", "gate", "risk", "neutral"})
NODE_COLOR_VARIABLES = {
    "active": "--color-active",
    "success": "--color-success",
    "gate": "--color-gate",
    "risk": "--color-risk",
    "neutral": "--color-neutral",
}


def relation_positions(section_type: str, node_count: int) -> tuple[tuple[int, int], ...]:
    """Return stable, type-specific positions within the fixed SVG view box."""
    if node_count < 1:
        raise ValueError("relational section requires at least one declared node")

    if section_type in {"flow", "timeline"}:
        return tuple((40 + index * (NODE_WIDTH + NODE_GAP), 170) for index in range(node_count))
    if section_type == "layer-map":
        return tuple((330, 40 + index * (NODE_HEIGHT + NODE_GAP)) for index in range(node_count))
    if section_type == "boundary-map":
        return tuple((40, 100 + index * (NODE_HEIGHT + NODE_GAP)) for index in range(node_count))
    raise ValueError(f"unsupported relational section type: {section_type}")


def _relation_nodes(section: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    nodes = section.get("nodes")
    if not isinstance(nodes, (list, tuple)) or len(nodes) < 2:
        raise ValueError("relational section requires a declared edge between distinct nodes")
    if not all(isinstance(node, Mapping) for node in nodes):
        raise ValueError("relational section requires declared nodes")
    if any(
        not isinstance(node.get("id"), str)
        or not node["id"]
        or not isinstance(node.get("label"), str)
        or not node["label"]
        or ("detail" in node and not isinstance(node["detail"], str))
        or ("group" in node and not isinstance(node["group"], str))
        for node in nodes
    ):
        raise ValueError("relational section requires declared nodes")
    if len({node["id"] for node in nodes}) != len(nodes):
        raise ValueError("relational section requires unique node IDs")
    return tuple(nodes)


def _relation_edges(
    section: Mapping[str, Any], node_ids: set[str]
) -> tuple[Mapping[str, Any], ...]:
    edges = section.get("edges")
    if not isinstance(edges, (list, tuple)) or not edges:
        raise ValueError("relational section requires a declared edge between distinct nodes")
    if not all(isinstance(edge, Mapping) for edge in edges):
        raise ValueError("relational section requires declared edges")
    declared_edges = tuple(edges)
    pairs: set[tuple[str, str]] = set()
    adjacency = {node_id: set() for node_id in node_ids}
    for edge in declared_edges:
        source = edge.get("from")
        target = edge.get("to")
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or source not in node_ids
            or target not in node_ids
            or source == target
            or ("label" in edge and not isinstance(edge["label"], str))
        ):
            raise ValueError("relational section requires a declared edge between distinct nodes")
        pair = (source, target)
        if pair in pairs:
            raise ValueError("relational section rejects duplicate declared edges")
        pairs.add(pair)
        adjacency[source].add(target)
        adjacency[target].add(source)

    pending = [min(node_ids)]
    reachable: set[str] = set()
    while pending:
        node_id = pending.pop()
        if node_id not in reachable:
            reachable.add(node_id)
            pending.extend(adjacency[node_id] - reachable)
    if reachable != node_ids:
        raise ValueError("relational section requires one connected graph using every declared node")
    return declared_edges


def _node_kind(node: Mapping[str, Any]) -> str:
    kind = node.get("kind")
    return kind if isinstance(kind, str) and kind in SEMANTIC_KINDS else "neutral"


def _node_detail(node: Mapping[str, Any]) -> str:
    detail = node.get("detail", "")
    return detail if isinstance(detail, str) else ""


def _boundary_layout(
    nodes: tuple[Mapping[str, Any], ...]
) -> tuple[dict[str, tuple[int, int]], str]:
    """Lay out factual declared groups without inferring a group from node index."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for node in nodes:
        group = node.get("group")
        if not isinstance(group, str) or not group.strip():
            raise ValueError("boundary-map requires declared groups")
        groups.setdefault(group, []).append(node)
    if len(groups) < 2:
        raise ValueError("boundary-map requires at least two declared groups")

    positions: dict[str, tuple[int, int]] = {}
    markup: list[str] = ['<g class="diagram-boundaries">']
    for group_index, (group, group_nodes) in enumerate(groups.items()):
        left = 20 + group_index * (NODE_WIDTH + NODE_GAP * 2)
        first_y = 100
        height = len(group_nodes) * NODE_HEIGHT + (len(group_nodes) - 1) * NODE_GAP + 100
        markup.append(
            f'<g class="diagram-boundary-group"><rect class="diagram-boundary" x="{left}" y="40" '
            f'width="{NODE_WIDTH + NODE_GAP}" height="{height}" rx="20"></rect>'
            f'<text class="diagram-boundary-label" x="{left + 20}" y="72">{_text(group)}</text></g>'
        )
        for node_index, node in enumerate(group_nodes):
            positions[node["id"]] = (left + 20, first_y + node_index * (NODE_HEIGHT + NODE_GAP))
    markup.append("</g>")
    return positions, "".join(markup)


def _relation_viewbox(positions: Mapping[str, tuple[int, int]]) -> tuple[int, int]:
    right = max(x + NODE_WIDTH for x, _ in positions.values()) + 40
    bottom = max(y + NODE_HEIGHT for _, y in positions.values()) + 40
    return max(1040, right), max(480, bottom)


def _edge_points(source: tuple[int, int], target: tuple[int, int]) -> tuple[int, int, int, int]:
    source_x, source_y = source
    target_x, target_y = target
    horizontal = abs(target_x - source_x) >= abs(target_y - source_y)
    if horizontal:
        if target_x >= source_x:
            return source_x + NODE_WIDTH, source_y + NODE_HEIGHT // 2, target_x, target_y + NODE_HEIGHT // 2
        return source_x, source_y + NODE_HEIGHT // 2, target_x + NODE_WIDTH, target_y + NODE_HEIGHT // 2
    if target_y >= source_y:
        return source_x + NODE_WIDTH // 2, source_y + NODE_HEIGHT, target_x + NODE_WIDTH // 2, target_y
    return source_x + NODE_WIDTH // 2, source_y, target_x + NODE_WIDTH // 2, target_y + NODE_HEIGHT


def _render_svg_node(node: Mapping[str, Any], identifier: str, position: tuple[int, int]) -> str:
    x, y = position
    kind = _node_kind(node)
    color = NODE_COLOR_VARIABLES[kind]
    detail = _node_detail(node)
    label_y = 29 if detail else 39
    detail_markup = (
        f'<text class="diagram-node-detail" x="{NODE_WIDTH // 2}" y="55" text-anchor="middle">{_text(detail)}</text>'
        if detail
        else ""
    )
    kind_y = 79 if detail else 70
    kind_markup = (
        f'<text class="diagram-node-kind" x="{NODE_WIDTH // 2}" y="{kind_y}" text-anchor="middle">{kind}</text>'
    )
    return (
        f'<g class="diagram-node diagram-node--{kind}" data-node-id="{identifier}" '
        f'transform="translate({x} {y})"><rect width="{NODE_WIDTH}" height="{NODE_HEIGHT}" '
        f'rx="12" style="stroke:var({color})"></rect><text x="{NODE_WIDTH // 2}" y="{label_y}" text-anchor="middle">'
        f'{_text(node["label"])}</text>{detail_markup}{kind_markup}</g>'
    )


def _render_svg_edge(
    edge: Mapping[str, Any],
    positions: Mapping[str, tuple[int, int]],
    node_identifiers: Mapping[str, str],
    marker_id: str,
) -> str:
    start_x, start_y, end_x, end_y = _edge_points(positions[edge["from"]], positions[edge["to"]])
    label = edge.get("label", "")
    return (
        f'<path class="diagram-edge" data-edge-from="{node_identifiers[edge["from"]]}" '
        f'data-edge-to="{node_identifiers[edge["to"]]}" marker-end="url(#{marker_id})" '
        f'd="M {start_x} {start_y} L {end_x} {end_y}"></path>'
        f'<text class="diagram-edge-label" x="{(start_x + end_x) // 2}" '
        f'y="{(start_y + end_y) // 2 - 10}">{_text(label)}</text>'
    )


def _render_mobile_relation(
    nodes: tuple[Mapping[str, Any], ...], edges: tuple[Mapping[str, Any], ...]
) -> str:
    labels = {node["id"]: node["label"] for node in nodes}
    node_items = "".join(
        _render_mobile_node(node)
        for node in nodes
    )
    edge_items = "".join(
        f'<li class="mobile-flow-relation"><strong>{_text(labels[edge["from"]])}</strong> '
        f'<span>{_text(edge.get("label", ""))}</span> '
        f'<strong>{_text(labels[edge["to"]])}</strong></li>'
        for edge in edges
    )
    return f'<ol class="mobile-semantic-flow">{node_items}{edge_items}</ol>'


def _render_mobile_node(node: Mapping[str, Any]) -> str:
    detail = _node_detail(node)
    detail_markup = (
        f'<span class="mobile-flow-detail">{_text(detail)}</span>' if detail else ""
    )
    kind_markup = f'<span class="mobile-flow-kind">{_node_kind(node)}</span>'
    group = node.get("group", "")
    group_markup = (
        f'<span class="mobile-flow-group">{_text(group)}</span>'
        if isinstance(group, str) and group
        else ""
    )
    return (
        f'<li class="mobile-flow-node mobile-flow-node--{_node_kind(node)}">'
        f'<strong>{_text(node["label"])}</strong>{detail_markup}{kind_markup}{group_markup}</li>'
    )


def render_relation(section: Mapping[str, Any]) -> str:
    """Render only declared relation facts as an accessible desktop/mobile diagram."""
    section_type = section.get("type")
    if section_type not in RELATIONAL_TYPES:
        raise ValueError(f"unsupported relational section type: {section_type}")
    if not isinstance(section.get("id"), str) or not isinstance(section.get("title"), str) or not isinstance(section.get("summary"), str):
        raise ValueError("relational section requires an ID, title, and summary")

    nodes = _relation_nodes(section)
    if section_type != "boundary-map" and any("group" in node for node in nodes):
        raise ValueError("node group is only boundary-map metadata")
    node_identifiers = {node["id"]: f"node-{index}" for index, node in enumerate(nodes)}
    edges = _relation_edges(section, set(node_identifiers))
    if section_type == "boundary-map":
        positions, boundaries = _boundary_layout(nodes)
    else:
        positions = {
            node["id"]: position
            for node, position in zip(nodes, relation_positions(section_type, len(nodes)))
        }
        boundaries = ""
    identifier = slugify(section["id"]) or "relation"
    title_id = f"{identifier}-title"
    description_id = f"{identifier}-desc"
    marker_id = f"{identifier}-arrow"
    view_width, view_height = _relation_viewbox(positions)
    marker = (
        f'<defs><marker id="{marker_id}" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"></path>'
        '</marker></defs>'
    )
    svg_edges = "".join(
        _render_svg_edge(edge, positions, node_identifiers, marker_id) for edge in edges
    )
    svg_nodes = "".join(
        _render_svg_node(node, node_identifiers[node["id"]], positions[node["id"]])
        for node in nodes
    )
    desktop = (
        f'<svg class="desktop-diagram diagram--{section_type}" viewBox="0 0 {view_width} {view_height}" role="img" '
        f'aria-labelledby="{title_id} {description_id}"><title id="{title_id}">{_text(section["title"])}</title>'
        f'<desc id="{description_id}">{_text(section["summary"])}</desc>{marker}{boundaries}{svg_edges}{svg_nodes}</svg>'
    )
    return desktop + _render_mobile_relation(nodes, edges)


def _diagram(section: Mapping[str, Any]) -> str:
    return (
        '<article class="lesson-card"><section class="panel technical-visual" aria-labelledby="lesson-title">'
        '<p class="eyebrow">Systems relationship</p>'
        f'<h1 id="lesson-title">{_text(section["title"])}</h1>'
        f'<p class="summary">{_text(section["summary"])}</p>'
        f'{render_relation(section)}</section>{_source_list(section)}</article>'
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
