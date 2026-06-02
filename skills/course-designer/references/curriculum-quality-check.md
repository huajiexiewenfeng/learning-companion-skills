# Curriculum Quality Check

Run this check before presenting a final course design.

## Core Checks

### 1. North Star Clarity

Check:

- Is the course anchored to a future capability?
- Can the North Star exclude irrelevant topics?
- Is the North Star written in language the learner recognizes?

Risk:

- If the North Star is only a topic, the course becomes a generic syllabus.

### 2. Scope Fit

Check:

- Is the duration realistic for the requested outcome?
- Does the plan match the learner's available time?
- Are there too many topics in the first version?

Risk:

- A course that is too large becomes motivational fiction.

### 3. Output Orientation

Check:

- Does each stage or sprint produce something visible?
- Are outputs connected to the user's goal, project, portfolio, or work?

Risk:

- Passive reading creates plan progress but not effective progress.

### 4. Verification Quality

Check:

- Can mastery be checked with a concrete explanation, application, comparison, build, critique, or review?
- Does the verification direction avoid long exams?

Risk:

- Vague completion standards make it impossible for `learning-companion` to score effective progress.

### 5. Review And Buffer

Check:

- Does a long course include review points?
- Are there buffer days or rescue space?

Risk:

- Without review buffers, the learner accumulates weak topics and the plan drifts.

### 6. Interdependency Handling

Check:

- Are interdependent topics connected instead of isolated?
- Would a spiral structure be better than a linear structure?

Use spiral structure when:

- the learner is building an architecture
- topics reinforce each other
- real projects should appear early
- governance or application context should not be delayed until the end

### 7. Handoff Readiness

Check:

- Does the course include a `learning-companion` import preview?
- Does the first learning item have topic, minimum completion, and verification direction?
- Is the user asked for confirmation before files are created?

## Red Flags

- "Learn everything about X"
- no visible outputs
- no verification standards
- no relation to the user's real context
- too many tools/frameworks listed without a reason
- daily tasks that are too large to repeat
- no review cadence
- course begins with theory but never reaches application

## Final Response Shape

When the course is ready, present:

1. brief diagnosis of the learner's goal
2. recommended course shape
3. course preview
4. quality check summary
5. `learning-companion` import preview
6. confirmation question

Keep the confirmation question simple:

```text
如果这个课程方向确认，我可以下一步把它交给 learning-companion 导入为正式学习计划。
```
