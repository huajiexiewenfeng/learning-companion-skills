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
`<body>`, with balanced non-void tags and no duplicate attributes. It also
requires at least one `<section>`, no iframe, no event-handler attributes,
no executable URL scheme, no external or local file resource dependency, no
network reference, parsed CSS rules for narrow screens, reduced motion, and
dark mode, and all required terms. Fragment links and safe embedded `data:`
assets are the only URL exceptions. SVG is optional for `document` and `hub`,
but every SVG that is present needs `role="img"`, a `<title>`, and a `<desc>`.

The validator uses these Technical Visual Companion-compatible error codes:

- `utf8-bom`, `invalid-utf8`, `malformed-html`, `doctype-count`,
  `html-root-count`, and `section-missing`
- `svg-missing`, `svg-accessibility-incomplete`, and
  `svg-relational-semantics-missing`
- `script-forbidden`, `iframe-forbidden`, `external-resource-forbidden`, and
  `network-reference-forbidden`, `event-handler-forbidden`, and
  `executable-url-forbidden`
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

Offline, responsive, dark, and reduced-motion. Script is permitted only as
one JSON data script and zero or one refresh script:

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
`hub-refresh-script-invalid`. The only permitted script attributes are `id`
and `type`; `src`, event handlers, and every other unexpected attribute
produce `hub-script-attributes-invalid`.

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
