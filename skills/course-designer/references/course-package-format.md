# Course Package Format

Use this format when presenting a course preview or producing a handoff package for `learning-companion`.

## Course Package

```markdown
# <Course Name>

## North Star

<The future capability this course should create. Preserve the user's own wording when useful.>

## Learner Context

- Background:
- Existing materials:
- Real projects:
- Constraints:
- Preferred rhythm:

## Duration And Rhythm

- Total effective learning days:
- Calendar estimate:
- Weekly rhythm:
- Daily study time:
- Review cadence:

## Course Shape

Explain whether the course is linear, staged, spiral, project-based, or mixed.

## Stage / Sprint Map

| Unit | Focus | Connected Application | Output | Verification |
|---|---|---|---|---|
| Sprint 1 | <focus> | <role/project/workflow> | <visible output> | <how to check mastery> |

## First Learning Item

- Day:
- Topic:
- Source material:
- Minimum completion:
- Verification direction:

## Visible Outputs

- <output 1>
- <output 2>

## Risks And Pacing

- Risk:
- Mitigation:

## learning-companion Import Preview

- Plan name:
- Status:
- Schedule:
- Plan progress:
- Effective progress:
- Current strategy:
- Current topic:
- Next step:
```

## Daily Item Format

Use this when designing day-by-day plans:

| Day | Topic | Source Material | Minimum Completion | Verification Direction | Status |
|---|---|---|---|---|---|
| 1 | <topic> | <source> | <small output> | <check question or task> | pending |

## Sprint Item Format

Use this when the course is long and should not be over-specified day by day:

| Sprint | Days | Main Focus | Application Thread | Output | Verification |
|---|---:|---|---|---|---|
| 1 | 1-10 | <focus> | <role/project/workflow> | <output> | <standard> |

## Handoff To learning-companion

End with:

```text
This is a preview. If the user confirms, learning-companion can create:

learning-companion/
  index.md
  plans/
    <plan-id>/
      dashboard.md
      map.md
      log.md
```

Do not write these files without confirmation.

## Example Import Preview

```markdown
## learning-companion Import Preview

- Plan name: Enterprise AI Transformation Runtime 学习计划
- Status: active
- Schedule: 每周 5 天，每天 60-90 分钟
- Plan progress: Day 0 / 150
- Effective progress: Day 0 / 150
- Current strategy: restart with prior knowledge
- Current topic: North Star 与企业 AI 主链路
- Next step: Day 1：说明 RAG、Role Copilot、Agentic Workflow、AI Native App、Autonomous Operation 在同一条企业 AI 转型链路中的角色
```
