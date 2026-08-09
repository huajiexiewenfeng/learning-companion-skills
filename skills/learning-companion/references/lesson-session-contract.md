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
resolved and proven to remain under that plan's `lessons` directory.

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
becomes `awaiting-voice`. A failed prepare remains `preparing` and has no final
artifact promotion.

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

`close` performs the final render with hub refresh disabled, sets both lesson
metadata files to `closed`, and writes `.artifacts-frozen`. Frozen packages
reject later `sync` calls; existing progress-related files are outside this
module's write scope.

## Ledger and timestamps

`artifacts.md` appends or preserves independently addressable card, deck, and
slide records. Every record has `id`, `logicalId`, `path`, `type`, `title`,
`profile`, `sourceTurn`, `sourceRefs`, `version`, `status`, `sha256`,
`createdAt`, `updatedAt`, and `supersedes`. Artifact status remains `visual
verification pending` until a separate browser review records otherwise.

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

All commands emit UTF-8 JSON with `ensure_ascii=False`; exit status is zero
only when the reported `overall` value is `passed`.
