# Lesson model authoring

Author a lesson as JSON with `schemaVersion` set to `learning-companion.lesson-model.v1`. Keep the top-level fields in this exact order: `schemaVersion`, `session`, `theme`, `question`, `requiredTerms`, `decks`, `sections`. Omit `decks` when no curated deck is needed; do not reorder a deck's `sectionIds`.

`session` fields are ordered as `id`, `planId`, `day`, `topic`, `mode`, `depth`, `status`. Modes are exactly `text` or `voice`; depths are exactly `light`, `medium`, or `deep`; lifecycle statuses are exactly `preparing`, `awaiting-voice`, `studying`, `closed`, or `error`. The stored lifecycle status is authoritative and is validated as written; a caller must never rewrite or normalize it merely to pass validation.

The only permitted section components are:

- `hero`
- `concept`
- `layer-map`
- `boundary-map`
- `flow`
- `timeline`
- `case-study`
- `misconception`
- `check-question`
- `sources`

Each section uses the ordered fields `id`, `type`, `title`, `summary`, `nodes`, `edges`, `sourceRefs`; omit `nodes` and `edges` for non-relational components. `layer-map`, `boundary-map`, `flow`, and `timeline` are relational: they require at least two nodes and one edge; node IDs are unique; both endpoints resolve; self-loops and duplicate directed edges are forbidden; every node participates; and the underlying undirected graph is connected. Every section needs at least one real `sourceRefs` entry. Deck IDs and titles must be unique, and every ordered `sectionIds` entry must resolve to an existing section.

Logical artifact identity is global across hub, cards, decks, and slides. `hub` is reserved for the renderer-owned index. Authored IDs must produce nonempty ASCII slugs, and no two generated artifacts may share a logical ID or output path, even when their artifact types differ.

Each node uses `id`, `label`, optional `detail`, `kind`, and boundary-only `group`. `detail`, when present, is a string rendered in both desktop and mobile relationship alternatives. `group` is legal only for declared `boundary-map` membership: every boundary node must provide a nonempty `group`, and a boundary map must contain at least two distinct group values. Boundary boxes and labels are derived only from these declared `group` values; `kind` controls the fixed semantic color/class and never determines grouping. All non-boundary component nodes must omit `group`.

## Complete valid example

```json
{
  "schemaVersion": "learning-companion.lesson-model.v1",
  "session": {"id": "2026-08-09-day-001-session-01", "planId": "enterprise-ai-transformation-runtime", "day": 1, "topic": "企业 AI 系统分层", "mode": "text", "depth": "medium", "status": "preparing"},
  "theme": "systems-engineering",
  "question": "模型很强，为什么系统仍然可能不可靠？",
  "requiredTerms": ["企业 AI 系统分层", "模型能力", "系统能力", "Authoritative State"],
  "decks": [{"id": "system-layers", "title": "企业 AI 系统分层主课件", "sectionIds": ["core-concept", "runtime-flow"]}],
  "sections": [
    {"id": "core-concept", "type": "concept", "title": "模型能力不等于系统能力", "summary": "模型负责推理，系统负责事实、状态、流程、风险和结果。", "sourceRefs": ["dashboard.md#Today"]},
    {"id": "runtime-flow", "type": "flow", "title": "可靠交付保障链", "summary": "建议经过证据、流程和治理后成为可靠交付。", "nodes": [{"id": "model", "label": "模型建议", "detail": "生成候选方案", "kind": "neutral"}, {"id": "evidence", "label": "知识与证据", "detail": "检索权威依据", "kind": "success"}], "edges": [{"from": "model", "to": "evidence", "label": "核对"}], "sourceRefs": ["learning-plan.md#Day-1"]}
  ]
}
```

## Invalid example

```json
{"sections": [{"id": "unsafe", "type": "raw-html", "sourceRefs": []}]}
```

This is invalid because `raw-html` is not a component and the section has no source. Do not use raw HTML, CSS, or JavaScript; unknown components, invented sources, and broken edge endpoints are forbidden.

## Repair loop

```text
author lesson.md → project lesson-model.json → validate → repair exact issue paths → render
```
