---
name: course-designer
description: >-
  Use when the user wants to design a personalized learning course before tracking it: clarify a learning goal or North Star, turn a vague study intention into a staged curriculum, create a sprint/day learning map, define outputs and verification standards, or produce a course package that can later be imported into learning-companion. Trigger on requests like "帮我定制课程", "我想学 X 该怎么规划", "帮我确认 North Star", "设计一个 90 天/150 天学习计划", "生成可导入 learning-companion 的课程", or similar course-design and self-learning planning requests.
---

# Course Designer

## Purpose

Turn a learner's goal into a personalized, executable course package.

This skill is the upstream companion to `learning-companion`:

```text
course-designer
-> designs the course

learning-companion
-> tracks and teaches the course
```

Use this skill before `learning-companion` when the user does not yet have a clear course, North Star, staged roadmap, or day-by-day/sprint-by-sprint plan.

## Boundary

This skill may:

- clarify the user's North Star
- identify learner background, constraints, available time, and desired outputs
- decompose a broad goal into stages, sprints, or learning days
- design a course around visible outputs and verification standards
- connect learning topics to real projects, portfolios, role workflows, or career goals
- produce a course package and a `learning-companion` import preview

This skill must not:

- start daily tracking or mark progress
- score mastery after a lesson
- maintain dashboards or logs
- silently create `learning-companion` files
- pretend the user has learned something just because a plan was designed
- generate a giant curriculum without checking whether it serves the user's North Star

## Required References

Read the relevant reference before acting:

- `references/north-star-workflow.md` when the user's goal is vague, overly broad, or mixed with multiple possible directions.
- `references/course-package-format.md` when producing a course preview, staged roadmap, sprint map, or `learning-companion` import preview.
- `references/curriculum-quality-check.md` before presenting a final course design.

## Workflow

### 1. Identify The Learning Request

Decide whether the user is asking for:

- goal clarification
- course design from scratch
- redesign of an existing course
- conversion of an existing plan into a trackable course
- a `learning-companion` import preview

If the user already has a concrete plan, skip heavy discovery and move toward course packaging.

### 2. Clarify The North Star

A course should be designed around a concrete future capability, not a topic list.

Good North Stars look like:

```text
Build an enterprise AI transformation architecture from RAG to governed autonomous operations.
Become a Java backend engineer who can build Agent Knowledge Runtime systems.
Publish a portfolio of Role Copilot skills for HR, DevOps, and Project workflows.
```

Weak North Stars look like:

```text
Learn AI.
Learn Java.
Learn English.
Get better at writing.
```

When the North Star is weak, ask one high-leverage question at a time. Do not interrogate the user with a long form.

### 3. Capture Constraints

Capture only constraints that change the course design:

- current background
- target outcome
- time horizon
- weekly rhythm
- daily study time
- preferred output type
- existing materials
- real projects or work scenarios
- deadline or external pressure

If the user does not know the time horizon, propose a reasonable one and explain the trade-off.

### 4. Design The Course Shape

Prefer output-driven course design:

```text
North Star
-> capability layers
-> stages or sprints
-> visible outputs
-> verification standards
-> daily or sprint map
```

For long courses, prefer a spiral structure over a strictly linear one when topics are interdependent.

Example:

```text
RAG / Knowledge Runtime
-> Role Agent Copilot
-> Agentic Workflow
-> AI Native App
-> Governance
```

The learner may revisit all layers in every sprint, while one layer has the main focus.

### 5. Preview Before Import

Always present the course package as a preview before asking `learning-companion` to create files.

The preview should include:

- course name
- North Star
- total duration
- learning rhythm
- stage or sprint map
- first learning item
- visible outputs
- verification standards
- risks and pacing suggestions
- `learning-companion` import preview

### 6. Handoff To Learning Companion

When the user confirms the course preview, tell them the next step is to import it with `learning-companion`.

Do not create the learning dashboard yourself unless the user explicitly asks and `learning-companion` is available in the current context.

## Course Design Principles

- Design around the learner's own goal, not a generic online course syllabus.
- Preserve the user's original wording of the goal and North Star.
- Prefer visible outputs over passive reading.
- Track both plan progress and effective progress after handoff.
- Keep daily tasks light enough to repeat.
- Add review buffers for long courses.
- Make verification concrete: explain, compare, apply, build, critique, or publish.
- Use existing projects and materials whenever they make learning more real.
- Avoid overloading the first version; a course can evolve after review.

## Common Patterns

### From Vague Goal To Course

```text
User: 我想学 AI
Course Designer:
1. clarify why the user wants AI
2. choose a North Star
3. propose 2-3 course shapes
4. design a staged course
5. output a learning-companion import preview
```

### From Existing Plan To Trackable Course

```text
User: 这是我的 12 周计划，帮我变成可跟踪课程
Course Designer:
1. preserve the original plan
2. check quality and risks
3. normalize into stages/days/sprints
4. define completion and verification standards
5. output import preview
```

### From Real Project To Course

```text
User: 我想围绕 role-copilot-skills 学 Agent
Course Designer:
1. identify the project as the learning anchor
2. map concepts to project outputs
3. create project-linked sprints
4. define portfolio deliverables
5. output import preview
```

## Handoff Phrase

Use this when the course is ready:

```text
这个课程包已经可以交给 learning-companion 导入。
导入后，learning-companion 会维护 dashboard、map、log、每日学习项、下课复盘和掌握度评分。
```
