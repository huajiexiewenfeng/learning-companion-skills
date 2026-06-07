# Learning Console

## Purpose

Learning Console is a single-file static HTML learning dashboard maintained by `learning-companion`.

It is intentionally simple: one HTML file, several vertical sections, no build step, no local server, no product-style backend.

The console helps the learner quickly see:

- 学习仪表盘
- 学习路线图
- 学习日志
- 课程内容预览
- 进度与掌握

The console is only a view layer. Markdown remains the source of truth.

## Source Of Truth

The source of truth remains the Markdown files in the user's current workspace:

```text
learning-companion/
  index.md
  plans/
    <plan-id>/
      dashboard.md
      map.md
      log.md
```

The HTML console must only summarize evidence-backed state from these files.

Do not write dashboard-only facts.

Bad:

```text
Effective progress: Day 20 / 60
```

when `dashboard.md`, `map.md`, or `log.md` does not support that state.

Good:

```text
Effective progress: Day 10 / 60
Source: learning-companion/plans/agent-rag-knowledge-runtime/dashboard.md
```

## Default Path

Recommended path inside the target workspace:

```text
learning-companion/learning-console.html
```

The template is:

```text
references/learning-console-template.html
```

## Modes

### dashboard-query

Use when the user asks to view learning progress or learning state.

Trigger examples:

```text
看下学习进度
我的学习情况
看一下学习面板
看下 dashboard
看今天学什么
看下掌握度
最近学了什么
学习统计
show my learning progress
show today's learning item
show mastery scores
show recent study log
```

Behavior:

1. Read `learning-companion/index.md`.
2. Resolve the active plan.
3. Read the active plan's `dashboard.md`, `map.md`, and `log.md`.
4. Return a concise status summary.
5. If `learning-companion/learning-console.html` exists, mention its path.

Do not update plan progress, effective progress, map status, or log entries.

### dashboard-refresh

Use when the user explicitly asks to refresh or update the learning console.

Trigger examples:

```text
刷新学习面板
更新学习面板
更新学习看板
刷新学习仪表盘
refresh learning console
update learning dashboard
refresh dashboard
```

Behavior:

1. Read `index.md`, `dashboard.md`, `map.md`, and `log.md`.
2. Build `window.learningData` according to `learning-console-data-contract.md`.
3. Update only the data section in `learning-console.html` when possible.
4. Preserve existing HTML, CSS, and render logic.
5. Report the refreshed console path and source files used.

Do not create learning progress that is not backed by Markdown evidence.

### console-create

Use when a learning plan import is confirmed, or when the user asks to create a learning console.

Trigger examples:

```text
创建学习面板
生成学习看板
创建 learning console
create learning dashboard
```

Behavior:

1. Confirm the target workspace if ambiguous.
2. Create `learning-companion/learning-console.html` from `learning-console-template.html` by default after plan import.
3. Fill the starter `window.learningData` from the imported Markdown files.
4. Keep starter values conservative when evidence is incomplete.
5. If `learning-console.html` already exists, preserve its layout and refresh only `window.learningData` unless the user confirms replacement.

Do not silently create the console during ordinary study or close-out review. The default creation rule applies to confirmed plan import.

## Layout Contract

Keep one standalone static HTML page with vertical scrolling sections.

The required sections are:

```text
学习仪表盘
学习路线图
学习日志
课程内容预览
进度与掌握
```

### 学习仪表盘

Shows the active plan state:

- plan name
- status
- plan progress
- effective progress
- current topic
- last studied
- next step

### 学习路线图

Shows course items grouped by simple learning status:

- completed
- current
- pending

### 学习日志

Shows recent learning records:

- date
- day
- topic
- mastery
- one-sentence understanding
- risk
- next strategy

### 课程内容预览

Shows the learner what is coming next:

- current day or module
- current topic
- source material
- minimum completion
- verification direction
- next 3-5 course items

### 进度与掌握

Shows lightweight statistics:

- completed days
- effective days
- average mastery
- highest mastery
- lowest mastery
- weak points and review suggestions when evidence exists

## Update Rules

Update the console only when one of these happens:

- user explicitly asks to create or refresh the learning console
- a plan is imported or created after user confirmation
- a close-out review changes dashboard/log state and the user asks to refresh the console
- weekly review changes dashboard/log state and the user asks to refresh the console

Do not update the console during:

- ordinary lightweight discussion
- unanswered study sessions
- speculative planning

## Static HTML Constraints

- Keep the page standalone.
- Do not require a build step.
- Do not fetch remote assets.
- Do not require a local server.
- Keep visible text in the user's language.
- Keep status data easy for LLMs to update.
- Prefer updating `window.learningData` over rewriting layout.
- Keep Markdown source paths visible.
- Do not include teacher-mode controls in the dashboard template.

## Common Mistakes

- Treating HTML as the source of truth.
- Marking effective progress without close-out evidence.
- Updating mastery score without a scored review/log entry.
- Rewriting the full page when a data-section update is enough.
- Creating a complex app when a static evidence-backed page is enough.
