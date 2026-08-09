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

Every profile requires exactly one `<!doctype html>`, one `<html>` root, at
least one `<section>`, no iframe, no HTTP(S) or protocol-relative resource
attribute, no network reference, a `max-width` narrow-screen media rule, and
all required terms. SVG is optional for `document` and `hub`, but every SVG
that is present needs `role="img"`, a `<title>`, and a `<desc>`.

The validator uses these Technical Visual Companion-compatible error codes:

- `utf8-bom`, `invalid-utf8`, `doctype-count`, `html-root-count`, and
  `section-missing`
- `svg-missing` and `svg-accessibility-incomplete`
- `script-forbidden`, `iframe-forbidden`, `external-resource-forbidden`, and
  `network-reference-forbidden`
- `responsive-rule-missing`, `reduced-motion-rule-missing`,
  `color-scheme-rule-missing`, `size-limit-exceeded`, and
  `required-term-missing:<term>`

## Profiles

### `document`

Offline, responsive, dark, reduced-motion, and script-free. Inline SVG is
optional, and any SVG must be accessible.

### `technical-visual`

The `document` contract plus at least one accessible relational inline SVG.
No script is allowed.

### `hub`

Offline and responsive. Script is permitted only as one JSON data script and
zero or one refresh script:

```html
<script id="lesson-data" type="application/json">{"key":"value"}</script>
<script id="lesson-refresh">window.dispatchEvent(new Event("lesson-refresh"));</script>
```

`lesson-data` must appear exactly once, use `type="application/json"`, and
contain valid JSON. `lesson-refresh` is optional, may appear at most once, and
its body must be byte-for-byte `window.dispatchEvent(new Event("lesson-refresh"));`.
Its UTF-8 SHA-256 is
`e8b44f8325dc81d0261961d7e465546dcd5eaee2facf01425a92268a99bcd520`.
Any other script ID produces `hub-script-not-allowlisted`; invalid data or
refresh scripts produce `hub-data-script-invalid` or
`hub-refresh-script-invalid`.

## Visual review gate

Deterministic validation does not replace visual review. Review each artifact
in a desktop browser and at an explicit 390px viewport. If a browser is
unavailable, the artifact status must literally be `visual verification pending`
and state that desktop and 390px reviews remain.
