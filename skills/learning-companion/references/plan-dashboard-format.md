# Plan And Dashboard Format

Use these templates when previewing or creating learning companion files in a target workspace.

## Target Structure

```text
learning-companion/
  index.md
  plans/
    <plan-id>/
      dashboard.md
      map.md
      log.md
```

## index.md

```markdown
# Learning Companion Index

## Plans

| Plan | Status | Schedule | Plan Progress | Effective Progress | Last Study | Next Step |
|---|---|---|---|---|---|---|
| <name> | active | <schedule> | Day 0 / N | Day 0 / N | - | <next step> |
```

## dashboard.md

Keep this as the default one-screen view.

```markdown
# <Plan Name> Dashboard

## Overview

- Status: active / light / paused
- Plan progress: Day X / N
- Effective progress: Day Y / N
- Current strategy: normal / light review / rescue / reconnect / stage reorder proposed
- Current topic:
- Last studied:
- Recent continuity:
- Current risks:
- Next step:

## Today

- Day:
- Topic:
- Source material:
- Minimum completion:
- Verification direction:
- Reminder state:

## Reminder

- User schedule text:
- Resolved schedule:
- Timezone:
- Follow-up after no response: 60 minutes
- Close-out reminder after `1`: 2 hours
- Weekly review:
- Automation id:

## Quick Links

- Map: `map.md`
- Log: `log.md`
```

## map.md

```markdown
# <Plan Name> Map

## Original Plan

<preserve original user plan>

## Normalized Map

| Day | Topic | Source Material | Minimum Completion | Verification Direction | Status |
|---|---|---|---|---|---|
| 1 | <topic> | optional | <minimum completion> | <question direction> | pending |
```

## log.md

```markdown
# <Plan Name> Log

## YYYY-MM-DD Day X

- State:
- Topic:
- One-sentence understanding:
- Verification:
- Mastery:
- Plan progress change:
- Effective progress change:
- Risk:
- Next strategy:
```

## Plan Status

- `active`: fixed reminders are enabled.
- `light`: only low-frequency review or light reminders.
- `paused`: no reminders, data preserved.

## Creation Rule

Before creating these files, show a preview and wait for user confirmation.
