# Lesson Session Lifecycle Contract

`lesson_package.py` owns the session-local package lifecycle. It never updates
a learning dashboard, plan-progress field, or Effective-progress field.

## Session allocation

```python
allocate_session(plan_dir, day, topic, mode, depth, local_date) -> Path
```

Allocation creates one direct child of `PLAN/lessons` named
`YYYY-MM-DD-day-NNN-session-NN`. The directory reservation uses `mkdir()` as
the collision check, so concurrent allocators cannot overwrite an earlier
session. Every write, staging path, promotion target, and version target is
resolved and proven to remain under its current session directory (not merely
somewhere under the plan's `lessons` directory). Existing symlink parents are
resolved before use and cannot redirect a write into another session.

Allocation creates `lesson.md` in `preparing` state and an empty
`artifacts.md` ledger. Add a valid `lesson-model.json` before preparing.

## Lifecycle

```python
prepare_session(session_dir) -> PackageReport
sync_session(session_dir) -> PackageReport
validate_session(session_dir) -> PackageReport
close_session(session_dir) -> PackageReport
```

`prepare` requires both `lesson.md` and `lesson-model.json`. It renders into a
UUID-named session-local staging directory and promotes nothing until every
gate passes. A text or hybrid session becomes `studying`; a voice session
becomes `awaiting-voice`. The teaching layer may transition `awaiting-voice` to
`studying` only after observable host evidence that a new native Voice task has
taken over the prepared session. A failed prepare remains `preparing` and has
no final artifact promotion.

An `awaiting-voice` session is immutable mode history for later routing. A
fresh text request after an abandoned Voice handoff allocates and prepares a
new text-mode session; it must not reuse, reclassify, or promote the Voice
session into `studying`.

`prepare`, `sync`, `validate`, and `close` hold an exclusive per-session lock.
They re-read the model, lifecycle state, and ledger only after acquiring that
lock. This serializes concurrent callers, preventing lost records, orphaned
versions, and incorrect `supersedes` links.

The package minimum is:

- one `index.html` hub;
- a main deck and every declared deck;
- one independently addressable slide for every section referenced by each
  deck;
- at least one `technical-visual` artifact.

Each staged artifact passes its exact `document`, `technical-visual`, or `hub`
HTML profile. The union of rendered artifact text must contain every
`requiredTerms` value. Every artifact source reference must be present in the
lesson model's declared section sources or the `sources:` list in `lesson.md`.

`sync` re-renders and validates the same gates. It compares SHA-256 bytes:
unchanged records are reused, changed immutable artifacts become `-v2`, `-v3`,
and so on, and name the replaced record in `supersedes`. Hub and deck index
navigation are mutable indexes and may update their original paths in place.
Before reuse, the final file must exist, match the ledger SHA-256, and still
pass its declared HTML profile; a tampered immutable artifact fails closed.

Promotion preflights every version destination before final writes. The ledger,
lifecycle files, and mutable indexes are snapshotted before commit. Any later
write, collision, ledger, or status failure restores those snapshots and
removes every newly created immutable artifact. Immutable publication claims
its final path exclusively, flushes and fsyncs its bytes, and records the
claimed file identity; a post-claim failure removes only that same partial
file, never a foreign collision file that won the path.

`close` performs the final render with hub refresh disabled, sets both lesson
metadata files to `closed`, and writes `.artifacts-frozen`. Frozen packages
reject later `sync` calls; existing progress-related files are outside this
module's write scope. Closing/freezing is a package action, not evidence of
mastery: the parent learning protocol performs it only after its normal `下课`
mastery review and is solely responsible for any Effective-progress decision.

Recovery is a teaching-layer selection rule: select the single newest open
session first by its allocated directory's date/day/session sequence. Validate
that exact session's source, model, and package. If invalid, never fall back to
older sessions; repair it only when its lifecycle permits, restart from
source-read/preparing, or allocate under the normal lifecycle instead.

## Ledger and timestamps

`artifacts.md` is a UTF-8 JSON document, not a Markdown parser surface:

```json
{"format":"learning-companion.artifact-ledger.v1","records":[...]}
```

Its root has exactly `format` and `records`. Each record is independently
addressable and has `id`, `logicalId`, `path`, `type`, `title`,
`profile`, `sourceTurn`, `sourceRefs`, `version`, `status`, `sha256`,
`createdAt`, `updatedAt`, and `supersedes`. Artifact status remains `visual
verification pending` until a separate browser review records otherwise.
Record IDs, paths, and `(logicalId, version)` pairs must be unique; record
types are checked and JSON arrays preserve source references (including
newlines) without line-oriented record injection. Current validation computes
the exact declared deck IDs, paths, and section-to-slide logical IDs from the
model, so preserved historical deck records never satisfy a changed definition.
The only valid record types are `hub`, `card`, `deck`, and `slide`; unknown
types are a malformed ledger, never an extensibility fallback.

Timestamps are deterministic: the default is `1970-01-01T00:00:00Z`; setting
an integer `SOURCE_DATE_EPOCH` uses that UTC instant instead. This makes
package fixtures and byte-level checks reproducible.

## CLI

```text
lesson_package.py allocate PLAN --day N --topic TEXT --mode text --depth medium --date YYYY-MM-DD
lesson_package.py prepare SESSION
lesson_package.py sync SESSION
lesson_package.py validate SESSION
lesson_package.py close SESSION
```

All commands—including missing arguments and unknown subcommands—emit UTF-8
JSON with `ensure_ascii=False`; exit status is zero only when the reported
`overall` value is `passed`.
