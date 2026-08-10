# Day 1 source and evidence note

This note is the session-local evidence register for the Day 1 golden lesson.
It separates the course's teaching framework from user-confirmed workflow
symptoms. It does not claim an external research source or a production
incident that was not supplied.

## E1-COURSE-DEFINED-FIVE-LAYER-FRAMEWORK

**Provenance:** Course-defined Day 1 framework confirmed for this lesson by
the learning-package requirement. It is a teaching taxonomy, not a claim that
all enterprise AI systems have one universal architecture.

**Framework and responsibility boundary:**

1. Experience and intent express a goal, constraints, and acceptance criteria.
2. Model and agent runtime produce candidate reasoning and controlled tool
   requests; they do not own permissions or business truth.
3. Knowledge and memory distinguish `Archive` (reviewable historical evidence)
   from `Memory` (reusable, potentially stale compressed context).
4. Workflow and governance express a `Plan` and enforce a `Checkpoint` before
   a controlled state transition.
5. Authoritative state and observability retain current facts in
   `Authoritative State` and connect inputs, decisions, actions, and results in
   a `Trace`.

The course rule is therefore: an Archive, a Memory, and a Plan do not by
themselves establish current truth; a Checkpoint controls a transition, and a
Trace makes the actual transition reviewable.

## E2-USER-CONFIRMED-LONG-CONTEXT-SYMPTOMS

**Provenance:** User-confirmed long-context symptoms supplied for this lesson's
scenario requirement. They are design symptoms, not a log of one observed
incident.

**Symptoms to reason about:**

- Long conversations may be compressed into Memory to preserve usable context.
- A compression may omit scope classification, approval context, or the last
  Checkpoint condition.
- A resumed agent can mistake compressed Memory for current authority and
  drift from the active execution scope.

The lesson's Project Develop Copilot narrative is an **illustrative composite**
of these symptoms. It must not be read as an observed Project Develop Copilot
incident, as a claim about an unobserved module, or as a statement that a
specific write occurred.

## E3-LIFECYCLE-AND-ARTIFACT-CONTROLS

**Provenance:** `skills/learning-companion/references/lesson-session-contract.md`
and `skills/learning-companion/references/lesson-artifact-contract.md`.

**Relevant controls:** lesson Markdown and the structured model are sources;
the committed runtime renders the offline HTML archive; the ledger records
artifact identity and validation state; deterministic validation precedes
publication; visual verification remains a distinct desktop and 390px review
gate. Closing a lesson archive does not change Effective progress.
