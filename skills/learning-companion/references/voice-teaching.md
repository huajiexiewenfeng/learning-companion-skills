# Native Voice Teaching Protocol

Use this reference only after the courseware gate in `SKILL.md` has produced a
validated package and opened or linked its hub. It governs a truthful handoff
to native Voice; it does not provide a way to make Voice work inside an
existing text task.

## Route And Host Boundary

Only explicit requests (`语音上课`, `用语音教我`, `实时语音老师`, or `Voice
teacher`) take this route. An existing text task cannot switch into or become
native Voice. Prepare the courseware exactly as for text, leave the voice
session in `awaiting-voice`, and provide the hub link before the handoff.

Never claim that Voice is enabled, active, started, connected, or successful
without observable host state. Do not guess buttons, controls, product names,
or host capabilities. Do not use UI automation, browser-driving, local TTS,
prerecorded audio, audio-file generation, or an imitation of a native Voice
session.

If the host exposes a way for the user to create a native Voice task, direct
them to create a **new empty Voice task before the first message**. Its first
message must be exactly:

```text
使用 learning-companion 继续当前 active plan
```

The prepared hub must be open or linked in the same handoff. State only what
is observable: for example, that the validated courseware link is ready, or
that the host has displayed a new native Voice task. Do not claim takeover
until the host state visibly shows it; then and only then may the session move
from `awaiting-voice` to `studying`.

If the host has no observable native Voice creation path, say that native Voice
cannot be started from this task, keep the session `awaiting-voice`, and do not
represent the handoff as a success.

## Abandoned Voice Handoff

If the user abandons an awaiting-voice handoff and later makes a fresh
text-teaching request, do not reuse or promote the awaiting-voice session.
Allocate and prepare a new text-mode session/package through the normal
source-read, author, validation, render, and hub gates, leaving the
awaiting-voice history intact. Enter `studying` only after the new text
session/package's gates pass; the earlier Voice session remains historical
evidence and never becomes a text session.

## Teaching Turns

Use the same durable source and package for both modes. Each spoken turn is
one 45–90 second concept chunk, interruption-first, and ends with exactly one
check question for an ordinary teaching chunk. The only exception is the
parent `下课` mastery review, which may use its established 1–3 verification
questions before freeze or any Effective progress update. Answer an
interruption before returning to the planned chunk; never add a second check
question to compensate.

Persist each turn under the main protocol: Markdown first, versioned HTML sync
second, then respond. A failed write or failed sync means no persistence claim
and no claim that courseware is current.

## Recovery And Product Claims

Recover only the latest open session whose source, package report, and state
can be read and validated. Never invent session state, a Voice connection, or
a completed handoff.

Route current product claims, availability, UI labels, and native Voice
capabilities through `openai-docs`. If current documentation or observable
host state does not support a claim, do not make it.

## Close

`下课` remains the normal close path: run the mastery review first, then close
and freeze the package. Only this parent close-out path may advance Effective
progress; a native Voice handoff or spoken explanation never does.
