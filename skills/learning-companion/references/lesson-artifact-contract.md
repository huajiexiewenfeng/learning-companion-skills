# Lesson HTML Artifact Contract

`validate_lesson_html.py` validates one self-contained UTF-8 HTML artifact. The
report always has `overall`, `errors`, and `metrics`; `overall` is literally
`passed` or `failed`.

```text
python skills/learning-companion/scripts/validate_lesson_html.py \
  --html PATH --profile document --required-term TERM
```

`--required-term` may be repeated. The default size ceiling is 2,000,000 bytes.
The profiles are exactly `document`, `technical-visual`, and `hub`.

## Shared offline requirements

Every profile requires well-formed, explicitly ordered HTML: one
`<!doctype html>` before one `<html>` root, followed by one `<head>` and one
`<body>`, with balanced non-void tags and no duplicate attributes. Element and
attribute names are case-folded and reduced to their namespace-local names
before policy checks. Duplicate normalized names therefore fail before any
attribute dictionary can collapse values; this includes security-critical
`id`, `type`, `data-contract`, `http-equiv`, `content`, `href`, `src`, `action`,
`formaction`, and `xlink:href` inputs.

Every profile also requires at least one `<section>`, no iframe, no
event-handler attributes, no meta refresh, no form submission through `action`
or `formaction`, and no unsafe active/navigation element. `area`, `base`,
`embed`, `form`, `link`, and `object` are forbidden, including namespace-prefixed
spellings. All normalized URL-bearing attributes, including `xlink:href`, are
checked for executable schemes and external or local file dependencies. An
internal fragment such as `href="#turn-1"` remains valid. The `hub` profile also
permits renderer-owned relative `<a href>` paths below `cards/`, `decks/`, or
`visuals/`; arbitrary relative paths remain invalid. Safe embedded `data:`
assets remain the other URL exception.

The artifact must contain no network reference, must include parsed CSS rules
for narrow screens, reduced motion, and dark mode, and must contain every
required term. SVG is optional for `document` and `hub`, but every SVG that is
present needs `role="img"`, a `<title>`, and a `<desc>`.

The validator uses these Technical Visual Companion-compatible error codes:

- `utf8-bom`, `invalid-utf8`, `malformed-html`, `doctype-count`,
  `html-root-count`, and `section-missing`
- `svg-missing`, `svg-accessibility-incomplete`, and
  `svg-relational-semantics-missing`
- `script-forbidden`, `iframe-forbidden`, `external-resource-forbidden`, and
  `network-reference-forbidden`, `event-handler-forbidden`, and
  `executable-url-forbidden`
- `unsafe-element-forbidden`, `meta-refresh-forbidden`, and
  `submission-forbidden`
- `responsive-rule-missing`, `reduced-motion-rule-missing`,
  `color-scheme-rule-missing`, `size-limit-exceeded`, and
  `required-term-missing:<term>`

## Profiles

### `document`

Offline, responsive, dark, reduced-motion, and script-free. Inline SVG is
optional, and any SVG must be accessible.

### `technical-visual`

The `document` contract plus at least one accessible relational inline SVG.
A relational SVG declares at least two `data-node-id` values and an edge with
matching `data-edge-from` and `data-edge-to` values. No script is allowed.

### `hub`

Offline, responsive, dark, and reduced-motion. Script is permitted only as one
JSON data script and the lifecycle-controlled refresh script below:

```html
<script id="lesson-data" type="application/json">{"status":"studying"}</script>
<script id="lesson-refresh" data-contract="v1">(() => {
  const key = `learning-companion-scroll:${location.pathname}`;
  addEventListener("beforeunload", () => sessionStorage.setItem(key, String(scrollY)));
  addEventListener("load", () => {
    const saved = Number(sessionStorage.getItem(key) || "0");
    if (Number.isFinite(saved)) scrollTo(0, saved);
  });
  setTimeout(() => location.reload(), 5000);
})();</script>
```

`lesson-data` must appear exactly once, use `type="application/json"`, and
contain a valid JSON object. Its only attributes are the required
`id="lesson-data"` and `type="application/json"`.

`lesson-refresh` uses the required `id="lesson-refresh"` and
`data-contract="v1"` attributes and no others. Its body is pinned byte for byte
to `HUB_REFRESH_BODY`: it saves the current scroll position under a
pathname-scoped `sessionStorage` key, restores that position on load, and
reloads after exactly 5000 milliseconds. The published UTF-8 SHA-256 literal
`HUB_REFRESH_BODY_SHA256` is
`c74305cd5efdf45e05e60680f948c0f58ccab9d99ac1a1d79e62e8fda57ee099`.
The validator tests derive the fixture and documentation check from these
implementation constants so a body or hash change cannot silently stale this
contract.

The `lesson-data.status` lifecycle value is exact and fail-closed:

- `preparing`, `studying`, and `awaiting-voice` require exactly one pinned
  refresh controller.
- `closed` and `error` forbid the refresh controller.
- Every other value, including `unknown`, whitespace/case/spelling variants,
  `sync`, and `unsynced`, produces `hub-status-invalid`. A separate sync marker
  may report `synced` or `unsynced`, but it is not a lifecycle value and never
  expands the refresh allowlist.

Any other script ID produces `hub-script-not-allowlisted`; invalid data or
refresh scripts produce `hub-data-script-invalid` or
`hub-refresh-script-invalid`. Duplicate or unexpected script attributes,
including `src` and event handlers, produce `hub-script-attributes-invalid`.

## Visual review gate

Deterministic validation does not replace visual review. Review each artifact
in a desktop browser and at an explicit 390px viewport. If a browser is
unavailable, the artifact status must literally be `visual verification pending`
and state that desktop and 390px reviews remain.

## Teaching package gate

The teaching protocol may open/link a package or begin teaching only after the
session runtime reports a passed package and every declared artifact passes its
declared profile. A minimum teaching package has `lesson.md`,
`lesson-model.json`, `artifacts.md`, an `index.html` hub, one main deck, and at
least one `technical-visual`. A package that is visually pending may be linked
with that literal status; it must not be described as visually reviewed.

Package identity is session-specific. An abandoned `awaiting-voice` package may
remain as history, but a later fresh text request must validate a newly
allocated text-mode package before it can enter `studying`; it cannot repurpose
the Voice package as its text courseware.
