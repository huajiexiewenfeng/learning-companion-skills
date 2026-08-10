---
id: 2026-08-10-day-001-session-01
planId: enterprise-ai-transformation-runtime
day: 1
topic: "企业 AI 系统分层：从模型能力到可靠交付"
mode: voice
depth: deep
status: closed
sources:
  - evidence.md#E1-COURSE-DEFINED-FIVE-LAYER-FRAMEWORK
  - evidence.md#E2-USER-CONFIRMED-LONG-CONTEXT-SYMPTOMS
  - evidence.md#E3-LIFECYCLE-AND-ARTIFACT-CONTROLS
---

# Day 1：企业 AI 系统分层

## 本课结论

模型能力只能产出候选判断；系统能力才把候选判断变成可验证、可追溯、可恢复的结果。可靠的企业 AI 不把聊天记录当作事实，也不把计划当作已经发生的状态。

## 五层责任

| 层 | 负责什么 | 不负责什么 | 可观察控制 |
| --- | --- | --- | --- |
| 体验与意图层 | 把用户目标、约束和可接受结果表达为请求 | 不保存业务真相 | 明确的任务边界与验收条件 |
| 模型与代理运行时层 | 推理、提出候选 Plan、选择受控工具调用 | 不单独决定权限或事实 | 输入、工具请求和输出都可记录 |
| 知识与记忆层 | Archive 保存可回看的原始证据；Memory 保存可复用但可能过期的压缩上下文 | 不替代当前业务状态 | 来源、版本、更新时间和适用范围 |
| 工作流与治理层 | 将 Plan 变成受控步骤；用 Checkpoint 在高风险转换前核验、批准或停止 | 不伪造执行结果 | 明确的前置条件、审批和失败路径 |
| 权威状态与可观测层 | Authoritative State 保存当前事实；Trace 连接输入、决策、工具、状态变化和结果 | 不把旧档案误说成当前事实 | 可查询状态、事件链和可复现证据 |

Archive 是历史证据的保管处，Memory 是帮助下一轮工作的信息压缩；二者都不能越过 Authoritative State。Plan 描述打算做什么，Checkpoint 决定是否允许转换，Trace 证明实际发生了什么。

## 责任图

人和业务操作方拥有目标、约束与验收；模型运行时拥有建议和受控请求；系统记录与治理拥有权限、Authoritative State、Checkpoint 和 Trace。跨边界时，建议必须被证据、权限和状态检查约束，不能直接写入结果。

## 可靠交付流

1. 从 Archive 和当前来源读取可核验输入，并明确哪些只是 Memory。
2. 代理形成 Plan；它仍是意图，不是状态变化。
3. 在 Checkpoint 核对权限、前置条件和审批证据。
4. 执行受控操作，把结果写入 Authoritative State。
5. 追加 Trace，并由负责人依据状态和证据验收可靠交付。

## Project Develop Copilot 说明性复合案例（非观测事故）

这个 Project Develop Copilot 叙事是基于用户确认的长上下文症状所作的说明性复合案例，不是一次已观测事故。它用来讨论一种可能的失败序列：为节省上下文，代理把长对话压缩为一段 Memory；若压缩遗漏 active scope、candidate scope 或最近 Checkpoint 的条件，恢复后的代理就可能把摘要误当作 Authoritative State，并发生执行漂移（execution drift）。

对应的控制不是让 Memory 更长，而是回到 Archive 中的原始决策与来源，重新读取当前 Plan、active scope 和 Checkpoint，确认 Authoritative State 后再执行。每次范围选择、批准和写入都要进入 Trace，下一次恢复才能区分“已证实”与“只是被压缩过”。

## 常见误区

“只要模型能总结完整聊天记录，Memory 就等于事实库。”错误：完整的总结仍是 Memory；Archive 提供历史证据，Authoritative State 提供当前事实，Plan 仅表示意图，Checkpoint 允许或拒绝转换，Trace 记录实际结果。

## 检查问题

当一个代理从压缩的长对话恢复后，准备修改候选模块时，它必须先检查哪三类信息，才能避免把 Memory 当成 Authoritative State 并造成执行漂移？

## 来源说明

- `evidence.md#E1-COURSE-DEFINED-FIVE-LAYER-FRAMEWORK`：课程定义的五层责任和 Archive / Memory / Authoritative State / Plan / Checkpoint / Trace 边界。
- `evidence.md#E2-USER-CONFIRMED-LONG-CONTEXT-SYMPTOMS`：用户确认的长上下文压缩与执行漂移症状；Project Develop Copilot 仅作说明性复合案例。
- `evidence.md#E3-LIFECYCLE-AND-ARTIFACT-CONTROLS`：会话包、离线 HTML 存档、确定性验证和独立视觉复核门禁。

## 教学回合索引

<!-- lesson-turn-id: turn-001 -->
## 企业 AI 系统分层：模型能力不等于系统能力

<!-- lesson-turn-id: turn-002 -->
## 五层企业 AI 系统分层

<!-- lesson-turn-id: turn-003 -->
## 责任图：建议、控制与事实不能混在一起

<!-- lesson-turn-id: turn-004 -->
## 可靠交付流：证据到验收的受控路径

<!-- lesson-turn-id: turn-005 -->
## Archive、Memory 与 Authoritative State 的三种记录

<!-- lesson-turn-id: turn-006 -->
## Project Develop Copilot：长对话压缩症状的说明性复合案例

<!-- lesson-turn-id: turn-007 -->
## 误区：完整的 Memory 就是当前事实

<!-- lesson-turn-id: turn-008 -->
## 检查问题：恢复后先核对什么？

<!-- lesson-turn-id: turn-009 -->
## 来源与发布门禁
