# Learning Companion Skills

AI skills for long-term learning plans, reminders, dashboards, and progress tracking.

[中文说明](README.zh.md)

![Learning Companion Skills workflow](assets/learning-companion-flow-en.svg)

This project helps AI agents support self-directed learning for any subject: technology, literature, philosophy, language learning, professional skills, and more.

The core idea is simple:

> A learning plan should not disappear into scattered chat sessions.

The skills in this repository support a two-step learning workflow:

```text
course-designer
-> turn a goal into a personalized course

learning-companion
-> track, teach, review, and record the course
```

## Skills

```text
skills/
  course-designer/
  learning-companion/
```

### `course-designer`

Use this skill before tracking starts.

It helps turn a vague learning intention into a personalized course package by clarifying the learner's North Star, identifying constraints, designing stages or sprints, defining visible outputs and verification standards, and producing a `learning-companion` import preview.

Typical requests:

- "I want to learn AI. Help me design a course."
- "Help me confirm my North Star."
- "Design a 90-day / 150-day learning plan."
- "Turn this goal into a course I can import into learning-companion."

### `learning-companion`

Use this skill after a course or learning plan exists.

It supports:

- one dashboard per learning plan
- plan import preview before writing files
- daily reminders with the current learning topic
- lightweight tutor mode for prompts like `teach me`, `continue learning`, `I don't understand`, `give me another example`, or `teacher mode`
- `1 / 0 / low-power / 下课` interaction protocol
- lightweight review with one-sentence understanding and small verification questions
- plan progress and effective progress tracking
- daily rescue tasks and weekly review
- static HTML learning dashboard generated from Markdown files after plan import

It does not design a full curriculum from scratch by default. The user provides the learning plan or imports one designed by `course-designer`; the skill normalizes, tracks, reminds, reviews, and adjusts pacing.

## Recommended Workflow

```text
1. Use course-designer to clarify the North Star.
2. Preview the personalized course package.
3. Confirm the course.
4. Import it with learning-companion.
5. Use learning-companion for daily study, tutor mode, close-out review, scoring, and progress tracking.
6. After import, learning-companion creates learning-console.html by default.
7. Refresh learning-console.html when learning records change and the learner wants to update the view.
```

## Static Learning Dashboard

`learning-companion` creates a standalone `learning-console.html` file in the learner's workspace after a plan is imported. It is a static view, not a separate app.

The dashboard focuses on five sections:

- learning cockpit
- course roadmap
- learning log
- course content preview
- progress and mastery

Typical requests:

- "import this plan into learning-companion"
- "create learning dashboard"
- "refresh learning dashboard"
- "show my learning progress"
- "看下学习进度"
- "创建学习面板"
- "刷新学习面板"

The HTML file is not the source of truth. The skill reads Markdown files, builds `window.learningData`, and updates the dashboard view.

## Tutor Mode

`learning-companion` can act as a lightweight teacher for the current learning item, not only as a tracker. When the learner asks to continue learning, asks for teaching, says they do not understand, or asks for another example, the skill reads the active dashboard and teaches the current topic in small steps.

Tutor mode follows a compact pattern:

1. explain the core idea in plain language
2. connect it to the learner's plan, project, or source material
3. give one concrete example
4. point out one common misconception or boundary
5. ask exactly one check question

Tutor mode does not advance effective progress by itself. The learner still finishes with `下课`, and the normal close-out review scores mastery and updates the dashboard and log.

## Data Model

Generated learning data belongs to the user's workspace, not this skill repository.

Recommended structure in the target workspace:

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

## Examples

```text
examples/
  technical-learning/
    dashboard.md
    learning-console.html
  philosophy-reading/
    dashboard.md
```

## Install

After this repository is published, install with a skills-compatible CLI:

```bash
npx skills add huajiexiewenfeng/learning-companion-skills
```

For local development:

```bash
npx skills add .
```

Restart Codex or your agent runtime after installation so the skill can be rediscovered.

## Status

Early draft. The current focus is a reliable two-skill flow for personalized course design, long-term learning tracking, and a simple static dashboard for progress visibility.
