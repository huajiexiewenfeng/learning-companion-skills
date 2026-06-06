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
  studyTimeStats: {}
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
| `studyTimeStats` | object | yes | Study-time summary. |

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
rescue
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
studying
completed
rescue
blocked
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
  studyTime: "",
  planProgressChange: "",
  effectiveProgressChange: "",
  risk: "",
  nextStrategy: "",
  evidence: ""
}
```

`studyTime` is optional for legacy logs. New logs should include it when available.

Recommended format:

```text
60 min
1h 20m
unknown
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
  rescueCount: 0,
  weakPoints: ["context pollution", "API error model"],
  reviewSuggestions: ["复盘 Day 3 的 context window"],
  recentScores: [
    { day: "1", topic: "RAG 完整链路", mastery: 4 },
    { day: "10", topic: "第一阶段复盘", mastery: 5 }
  ]
}
```

## studyTimeStats

```javascript
{
  totalMinutes: null,
  averageMinutes: null,
  entriesWithTime: 0,
  entriesMissingTime: 10,
  note: "Legacy logs may not include Study time."
}
```

Use `null` when time cannot be calculated.

## Data Update Rules

When refreshing the console:

1. Parse `index.md` into `plans`.
2. Parse active `dashboard.md` into `dashboard` and `today`.
3. Parse active `map.md` into `mapItems` and `contentPreview.upcoming`.
4. Parse active `log.md` into `logEntries`.
5. Derive `masteryStats` and `studyTimeStats`.
6. Update `generatedAt` and `sourceFiles`.
7. Preserve HTML, CSS, and render logic.

Do not infer mastery or study time when the log does not contain evidence.

## Backward Compatibility

Legacy logs may not include:

- `Study time`
- `Evidence`
- `contentPreview`

The console should show these as:

```text
unknown
```

or derive a conservative display from `today` and `mapItems`.
