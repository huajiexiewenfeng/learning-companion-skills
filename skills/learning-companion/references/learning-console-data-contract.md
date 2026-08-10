# Learning Console Data Contract

This contract defines the structured data block embedded in `learning-console.html`.

The HTML template renders `window.learningData`. The `learning-companion` skill should update this object from Markdown source files.

## Data Block

```html
<script id="learning-data">
window.learningData = {
  generatedAt: "",
  workspace: "",
  sourceFiles: [],
  plans: [],
  activePlanId: "",
  dashboard: {},
  today: {},
  mapItems: [],
  logEntries: [],
  contentPreview: {},
  masteryStats: {},
  // Legacy consoles use these conservative values until lesson archives exist.
  activeLesson: null,
  lessonSessions: []
};
</script>
```

## Top-Level Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `generatedAt` | string | yes | Refresh timestamp in local timezone. |
| `workspace` | string | no | Human-readable workspace path or name. |
| `sourceFiles` | array | yes | Markdown files used to build the console. |
| `plans` | array | yes | Plans from `learning-companion/index.md`. |
| `activePlanId` | string | yes | Active plan id. |
| `dashboard` | object | yes | Active plan overview state. |
| `today` | object | yes | Current learning item. |
| `mapItems` | array | yes | Course map rows. |
| `logEntries` | array | yes | Learning log entries. |
| `contentPreview` | object | yes | Current and upcoming course content. |
| `masteryStats` | object | yes | Mastery summary. |
| `activeLesson` | object or `null` | yes | Current generated lesson archive, if one exists. |
| `lessonSessions` | array | yes | Generated lesson archives for the active plan. |

## activeLesson and lessonSessions

For legacy data, use exactly `activeLesson: null` and `lessonSessions: []`. A populated
active lesson uses this shape:

```javascript
activeLesson: {
  sessionId:"2026-08-09-day-001-session-01", day:"1", topic:"企业 AI 系统分层",
  mode:"voice", depth:"medium", status:"studying", updatedAt:"2026-08-09 15:30",
  indexPath:"learning-companion/plans/enterprise-ai-transformation-runtime/lessons/2026-08-09-day-001-session-01/index.html",
  artifactCount:8
}
```

Each archived session uses this shape:

```javascript
lessonSessions: [{
  sessionId:"2026-08-09-day-001-session-01", day:"1", topic:"企业 AI 系统分层",
  status:"studying", indexPath:"learning-companion/plans/enterprise-ai-transformation-runtime/lessons/2026-08-09-day-001-session-01/index.html",
  documentCount:3, deckCount:1, visualCount:2
}]
```

`indexPath` must be the normalized workspace-relative lesson archive shape
`learning-companion/plans/<plan-id>/lessons/<session-id>/index.html`. The console renders
session fields as text and rejects traversal (`..`, including encoded forms), absolute or
protocol/network paths, backslashes, control characters, whitespace, and non-lesson paths.

## sourceFiles

```javascript
{
  label: "dashboard.md",
  path: "learning-companion/plans/<plan-id>/dashboard.md",
  role: "dashboard",
  lastRead: "2026-06-06 12:00"
}
```

## plans

```javascript
{
  id: "agent-rag-knowledge-runtime",
  name: "Agent/RAG Knowledge Runtime 转行计划",
  status: "active",
  schedule: "每周 5 天，每天 60-90 分钟",
  planProgress: "Day 10 / 60",
  effectiveProgress: "Day 10 / 60",
  lastStudy: "2026-05-23",
  nextStep: "Day 11：设计 chunk 表或文档结构"
}
```

## dashboard

```javascript
{
  planName: "",
  status: "active",
  planProgress: "Day 0 / 0",
  effectiveProgress: "Day 0 / 0",
  currentStrategy: "normal",
  currentTopic: "",
  lastStudied: "",
  recentContinuity: "",
  currentRisks: "",
  nextStep: ""
}
```

Allowed `currentStrategy` values:

```text
normal
light review
reconnect
paused
stage reorder proposed
unknown
```

## today

```javascript
{
  day: "1",
  topic: "",
  sourceMaterial: "",
  minimumCompletion: "",
  verificationDirection: "",
  reminderState: "ready"
}
```

Allowed `reminderState` values:

```text
ready
studying
pending
skipped
closed
unknown
```

## mapItems

```javascript
{
  day: "1",
  stage: "阶段一",
  topic: "",
  sourceMaterial: "",
  minimumCompletion: "",
  verificationDirection: "",
  status: "pending"
}
```

Allowed `status` values:

```text
pending
current
completed
skipped
unknown
```

## logEntries

```javascript
{
  date: "2026-05-23",
  day: "10",
  state: "completed",
  topic: "",
  oneSentenceUnderstanding: "",
  verification: "",
  mastery: "5/5",
  planProgressChange: "",
  effectiveProgressChange: "",
  risk: "",
  nextStrategy: "",
  evidence: ""
}
```

## contentPreview

```javascript
{
  current: {
    day: "11",
    title: "Java RAG 服务：chunk 存储",
    sourceMaterial: "主计划第 3-4 周",
    minimumCompletion: "设计 chunk 表或文档结构",
    verificationDirection: "说明 chunk 与原文如何追溯"
  },
  upcoming: [
    { day: "12", title: "top-k 检索 API", status: "pending" },
    { day: "13", title: "引用和证据返回", status: "pending" }
  ]
}
```

## masteryStats

```javascript
{
  completedDays: 10,
  effectiveDays: 10,
  scoredEntries: 10,
  averageMastery: 4.15,
  highestMastery: 5,
  lowestMastery: 3.5,
  weakPoints: ["context pollution", "API error model"],
  reviewSuggestions: ["复盘 Day 3 的 context window"],
  recentScores: [
    { day: "1", topic: "RAG 完整链路", mastery: 4 },
    { day: "10", topic: "第一阶段复盘", mastery: 5 }
  ]
}
```

## Data Update Rules

When refreshing the console:

1. Parse `index.md` into `plans`.
2. Parse active `dashboard.md` into `dashboard` and `today`.
3. Parse active `map.md` into `mapItems` and `contentPreview.upcoming`.
4. Parse active `log.md` into `logEntries`.
5. Derive `masteryStats` only from scored learning logs.
6. Update `generatedAt` and `sourceFiles`.
7. Preserve HTML, CSS, and render logic.
8. Preserve the `script#learning-data` block byte-for-byte when upgrading console layout.

Do not infer mastery when the log does not contain evidence.

## Backward Compatibility

Legacy logs may not include:

- `Evidence`
- `contentPreview`

The console should show these as:

```text
unknown
```

or derive a conservative display from `today` and `mapItems`.
