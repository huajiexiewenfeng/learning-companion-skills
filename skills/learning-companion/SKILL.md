---
name: learning-companion
description: Use when the user wants to manage a long-term learning plan, create or update a learning dashboard, track study progress across sessions, receive study reminders, record "下课", review learning status, continue a study plan, view learning progress or refresh a static learning dashboard, or asks the assistant to teach or explain today's learning content.
---

# Learning Companion

## Purpose

Act as a lightweight learning manager for long-term study plans across sessions.

The skill is subject-agnostic. It can track technology, literature, philosophy, language learning, professional skills, and other structured learning plans.

## Core Boundary

The user provides the learning plan. Do not design a full curriculum from scratch unless the user explicitly asks for that.

This skill may:

- normalize a provided plan into a trackable map
- check whether the plan is too vague or too heavy
- maintain one dashboard per plan
- remind the user with today's learning content
- teach today's learning content in a lightweight tutor mode when requested
- lightly verify understanding after "下课"
- update progress and suggest pacing changes
- summarize learning progress from local learning files
- create the static HTML learning dashboard by default after a plan is imported
- refresh the static HTML learning dashboard when requested

This skill should not:

- silently write files before preview and confirmation
- mix all plans into one large dashboard
- replace the user's source material
- add large external teaching content by default
- turn tutor mode into a full curriculum generator unless explicitly asked
- turn tracking into homework
- treat the HTML learning dashboard as the source of truth
- turn the static dashboard into a complex app

## Required References

Read the relevant reference before acting:

- `references/plan-dashboard-format.md` when creating, previewing, or updating learning files.
- `references/reminder-workflow.md` when handling reminders, `1`, `0`, low-power mode, or "下课".
- `references/scoring-and-review.md` when judging completion, effective progress, low-score review tasks, or weekly review.
- `references/learning-console.md` when the user asks to view, create, refresh, or summarize the learning dashboard, learning panel, progress, stats, mastery, route map, course preview, or recent logs.
- `references/learning-console-data-contract.md` when creating or refreshing `learning-console.html`.

## Default Data Location

In the target workspace:

```text
learning-companion/
  index.md
  learning-console.html              # static view created by default after import
  plans/
    <plan-id>/
      dashboard.md
      map.md
      log.md
```

One learning plan gets one dashboard.

The Markdown files are the source of truth. `learning-console.html` is a generated static view created by default after a plan is imported.

## Hard Rules

1. Preview before writing new plan files. Create files only after the user confirms.
2. Preserve the original learning plan text.
3. Use the local system date, time, and timezone for reminders, logs, and relative dates.
4. If the user gives natural language time, store both the original text and resolved schedule.
5. Ask at most one question at a time.
6. Keep daily interaction low-friction.
7. Track both plan progress and effective progress.
8. Do not update effective progress from tutor mode alone.
9. Do not make `learning-console.html` the source of truth.
10. Do not add tutor-mode controls to the static HTML dashboard.

## Plan Creation Flow

When the user provides a learning plan:

1. Identify the plan name and subject.
2. Run a quality check:
   - unclear topic
   - missing learning range
   - overly heavy day
   - missing review buffer
   - missing completion standard
3. Produce a preview:
   - dashboard preview
   - map preview
   - reminder configuration preview
4. Ask for confirmation before writing files or creating automations.

When the user confirms plan import, include `learning-companion/learning-console.html` in the created files by default. Preview that the file will be created from `references/learning-console-template.html`.

## Static Dashboard Protocol

Use dashboard-query mode when the user asks to view current learning status. Trigger examples:

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

In dashboard-query mode:

1. Read `learning-companion/index.md`.
2. Resolve the active plan.
3. Read `dashboard.md`, `map.md`, and `log.md`.
4. Return a concise status summary.
5. Mention `learning-companion/learning-console.html` if it exists.

Do not update progress, map status, mastery, or logs in dashboard-query mode.

Use dashboard-refresh mode when the user explicitly asks to refresh the learning panel or dashboard. Trigger examples:

```text
刷新学习面板
更新学习面板
更新学习看板
刷新学习仪表盘
refresh learning console
update learning dashboard
refresh dashboard
```

In dashboard-refresh mode:

1. Read `references/learning-console.md`.
2. Read `references/learning-console-data-contract.md`.
3. Read the source Markdown files.
4. Refresh only the `window.learningData` section in `learning-console.html` when possible.
5. Preserve the HTML layout and render logic.
6. Report the refreshed path and source files used.

Use console-create mode when a plan import is confirmed or when the user explicitly asks to create the learning panel. Create `learning-companion/learning-console.html` from `references/learning-console-template.html` as part of the confirmed import flow.

If `learning-console.html` already exists during import, do not overwrite the user's customized layout without confirmation. Prefer refreshing only the `window.learningData` section.

The static dashboard layout is intentionally limited to:

```text
学习仪表盘
学习路线图
学习日志
课程内容预览
进度与掌握
```

Do not add tutor-mode controls or complex app interactions to the static dashboard.

## Daily Protocol

Use low-friction replies:

```text
1 = 今天会学，先记为学习中
0 = 今天跳过
低配 = 给我 10/20/30 分钟保底任务
下课 = 学完了，开始收口记录
```

When the user replies `1`, mark the plan as studying for today and schedule a close-out reminder 2 hours later. Do not ask for more input.

When the user replies `下课`, run a short review:

1. Ask for one-sentence understanding.
2. Ask 1-3 verification questions, staying within 5 minutes.
3. Score mastery.
4. Update dashboard and log.
5. Decide tomorrow's strategy.

## Teaching Protocol

Use tutor mode when the user asks for teaching, not just tracking. Trigger examples:

- `你来教我学习`
- `继续学习`
- `我不明白`
- `换个例子`
- `老师模式`
- any request that asks the assistant to explain, teach, clarify, or continue today's learning topic

Tutor mode should stay lightweight and tied to the current plan item. It is a teaching layer on top of the learning manager, not a replacement for the source material.

When tutor mode starts:

1. Identify the active plan and today's item from `dashboard.md`.
2. If today's item is not started, mark it as studying before teaching.
3. Teach the current topic in small steps:
   - state the core idea in plain language
   - connect it to the user's plan, project, or source material
   - give one concrete example
   - name one common misconception or boundary
   - ask exactly one check question
4. If the user says they do not understand, change the explanation style:
   - use a simpler analogy
   - use a smaller example
   - contrast two nearby concepts
   - avoid repeating the same wording
5. If the user asks for another example, give one focused example and then ask one check question.

Tutor mode must not:

- advance effective progress without a close-out review
- overwhelm the user with a long lecture
- introduce large external material unless the user asks
- ask multiple questions at once
- turn the session into homework
- change the static HTML dashboard layout

At the end of a tutor-mode response, invite the user to continue with one low-friction next step. If the user appears ready to finish, ask them to reply `下课` so the normal close-out review can score mastery and update progress.

## Progress Rule

`plan progress` means the user has reached that planned day or item.

`effective progress` means the item reached at least 3/5 mastery.

If mastery is below 3/5, pause effective progress and assign a focused review task that returns to the user's original material.

## Reminder Style

Use gentle supervision:

- warm
- brief
- honest
- not shaming
- not overly motivational

The system should help the user keep continuity without making the tracking system itself heavy.
