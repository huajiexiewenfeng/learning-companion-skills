"""Safely add lesson-archive support to a version-1 learning console."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence


VERSION = "2"
FEATURES = ("nav", "style", "section", "renderer", "render-call")
UNSAFE_FEATURE_RE = re.compile(
    r"(?:\b(?:innerHTML|outerHTML|insertAdjacentHTML|eval)\b|\bnew\s+Function\b|\bdocument\s*\.\s*write\b|\.\s*on[a-z]+\s*=|\bon[a-z]+\s*=|javascript\s*:)",
    re.IGNORECASE,
)
DATA_OPEN_RE = re.compile(r"<script\b(?=[^>]*\bid\s*=\s*['\"]learning-data['\"])[^>]*>", re.IGNORECASE)
HTML_OPEN_RE = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
VERSION_RE = re.compile(r"\sdata-learning-console-version\s*=\s*(['\"])([^'\"]*)\1", re.IGNORECASE)
ARCHIVE_PATH_RE = re.compile(
    r"^learning-companion/plans/[A-Za-z0-9][A-Za-z0-9._-]*/lessons/[A-Za-z0-9][A-Za-z0-9._-]*/index\.html$"
)
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class UpgradeError(ValueError):
    """Raised when a console cannot be proven safe to modify."""


@dataclass(frozen=True)
class UpgradeReport:
    changed: bool
    previous_version: int
    current_version: int
    preserved_data_block: bool


@dataclass
class _Element:
    name: str
    attrs: tuple[tuple[str, str | None], ...]
    parents: tuple[str, ...]
    start: int
    opening_end: int
    close_start: int | None = None
    script_chunks: list[str] = field(default_factory=list)

    def attr(self, name: str) -> str | None:
        values = [value for key, value in self.attrs if key == name]
        if len(values) != 1:
            return None
        return values[0]


class _DocumentProbe(HTMLParser):
    """Small strict-enough DOM probe; comments and script strings never become tags."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_offsets = [0]
        self.line_offsets.extend(match.end() for match in re.finditer(r"\n", source))
        self.elements: list[_Element] = []
        self.stack: list[_Element] = []
        self.errors: list[str] = []
        self.feed(source)
        self.close()
        if self.stack:
            self.errors.append("unclosed element(s): " + ", ".join(element.name for element in self.stack))

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        names = [name.lower() for name, _ in attrs]
        if len(names) != len(set(names)):
            self.errors.append(f"duplicate attribute on <{tag}>")
        start = self._offset()
        raw = self.get_starttag_text() or ""
        element = _Element(tag, tuple((name.lower(), value) for name, value in attrs), tuple(item.name for item in self.stack), start, start + len(raw))
        self.elements.append(element)
        if tag not in VOID_TAGS:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self.stack or self.stack[-1].name != tag:
            self.errors.append(f"mismatched closing tag </{tag}>")
            return
        self.stack[-1].close_start = self._offset()
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1].name == "script":
            self.stack[-1].script_chunks.append(data)

    def require_clean(self) -> None:
        if self.errors:
            raise UpgradeError("malformed HTML: " + "; ".join(self.errors))

    def find(self, name: str, predicate=None) -> list[_Element]:
        return [element for element in self.elements if element.name == name and (predicate is None or predicate(element))]


def _marker(feature: str, edge: str) -> str:
    return f"<!-- learning-companion:lesson-sessions:{feature}:{edge} -->"


def _one(text: str, needle: str, description: str) -> int:
    count = text.count(needle)
    if count != 1:
        raise UpgradeError(f"expected exactly one {description}; found {count}")
    return text.index(needle)


def _learning_data_block(text: str) -> str:
    openings = list(DATA_OPEN_RE.finditer(text))
    if len(openings) != 1:
        raise UpgradeError(f"expected exactly one script#learning-data block; found {len(openings)}")
    opening = openings[0]
    close = text.find("</script>", opening.end())
    if close < 0:
        raise UpgradeError("script#learning-data is missing its closing tag")
    block = text[opening.start() : close + len("</script>")]
    if "window.learningData" not in block:
        raise UpgradeError("script#learning-data does not define window.learningData")
    return block


def _version(text: str) -> int:
    html_tags = list(HTML_OPEN_RE.finditer(text))
    if len(html_tags) != 1:
        raise UpgradeError(f"expected exactly one html opening tag; found {len(html_tags)}")
    match = VERSION_RE.search(html_tags[0].group(0))
    if not match:
        return 1
    if match.group(2) != VERSION:
        raise UpgradeError(f"unsupported learning console version {match.group(2)!r}")
    return 2


def _classes(element: _Element) -> set[str]:
    return set((element.attr("class") or "").split())


def _exactly_one(elements: list[_Element], description: str) -> _Element:
    if len(elements) != 1:
        raise UpgradeError(f"expected exactly one {description}; found {len(elements)}")
    return elements[0]


def _active_js_positions(source: str, needle: str) -> list[int]:
    """Find exact code tokens while ignoring JavaScript quotes and comments."""
    positions: list[int] = []
    index = 0
    while index < len(source):
        if source.startswith("//", index) or source.startswith("<!--", index):
            newline = source.find("\n", index)
            index = len(source) if newline < 0 else newline + 1
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end < 0 else end + 2
        elif source[index] in "'\"`":
            quote = source[index]
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index += 2
                elif source[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
        else:
            if source.startswith(needle, index):
                positions.append(index)
            index += 1
    return positions


def _script_source(element: _Element) -> str:
    return "".join(element.script_chunks)


def _probe_document(text: str) -> _DocumentProbe:
    probe = _DocumentProbe(text)
    probe.require_clean()
    html = _exactly_one(probe.find("html", lambda item: not item.parents), "root html element")
    _exactly_one(probe.find("head", lambda item: item.parents == ("html",)), "head directly under html")
    _exactly_one(probe.find("body", lambda item: item.parents == ("html",)), "body directly under html")
    if html.close_start is None:
        raise UpgradeError("html element is not closed")
    data_script = _exactly_one(probe.find("script", lambda item: item.attr("id") == "learning-data"), "script#learning-data element")
    if "body" not in data_script.parents:
        raise UpgradeError("script#learning-data is not in the body")
    return probe


def _renderer_script(probe: _DocumentProbe) -> _Element:
    candidates = []
    for script in probe.find("script", lambda item: item.attr("id") != "learning-data" and "body" in item.parents):
        source = _script_source(script)
        if _active_js_positions(source, "function render() {") or _active_js_positions(source, "renderSources(data.sourceFiles || [], data.generatedAt);"):
            candidates.append(script)
    script = _exactly_one(candidates, "renderer script")
    source = _script_source(script)
    if len(_active_js_positions(source, "function render() {")) != 1:
        raise UpgradeError("expected one active render function in renderer script")
    if len(_active_js_positions(source, "renderSources(data.sourceFiles || [], data.generatedAt);")) != 1:
        raise UpgradeError("expected one active renderSources call in renderer script")
    return script


def _validate_legacy_structure(text: str) -> _DocumentProbe:
    probe = _probe_document(text)
    style = _exactly_one(probe.find("style", lambda item: item.parents and item.parents[-1] == "head"), "style in head")
    if style.close_start is None:
        raise UpgradeError("style is not closed")
    if "<!--" in text[style.opening_end : style.close_start]:
        raise UpgradeError("style closing tag may be hidden in a comment")
    nav = _exactly_one(probe.find("nav", lambda item: "nav-group" in _classes(item) and "aside" in item.parents and "body" in item.parents), "navigation group in aside")
    if nav.close_start is None:
        raise UpgradeError("navigation group is not closed")
    _exactly_one(probe.find("main", lambda item: "body" in item.parents), "main content region")
    mastery = _exactly_one(probe.find("section", lambda item: item.attr("id") == "mastery" and "main" in item.parents and "body" in item.parents), "mastery section in main")
    if mastery.close_start is None:
        raise UpgradeError("mastery section is not closed")
    _renderer_script(probe)
    # Conservatively reject any raw duplicate: a genuine anchor plus bait is ambiguous.
    _one(text, "</style>", "legacy style closing tag")
    _one(text, "</nav>", "legacy navigation closing tag")
    _one(text, '<section class="section" id="mastery">', "legacy mastery section")
    _one(text, "    function render() {", "legacy render function")
    _one(text, "renderSources(data.sourceFiles || [], data.generatedAt);", "legacy renderSources call")
    return probe


def _feature_fragment(template: str, feature: str) -> str:
    start = _marker(feature, "start")
    end = _marker(feature, "end")
    start_at = _one(template, start, f"template {feature} start marker")
    end_at = _one(template, end, f"template {feature} end marker")
    if end_at <= start_at:
        raise UpgradeError(f"template {feature} markers are out of order")
    return template[start_at : end_at + len(end)]


def _normalize_newlines(text: str, newline: str = "\n") -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)


def _marker_bounds(text: str, feature: str) -> tuple[int, int]:
    start = _one(text, _marker(feature, "start"), f"{feature} start marker")
    end = _one(text, _marker(feature, "end"), f"{feature} end marker")
    if end <= start:
        raise UpgradeError(f"{feature} markers are out of order")
    return start, end + len(_marker(feature, "end"))


def _inside(element: _Element, start: int, end: int) -> bool:
    return element.opening_end <= start and end <= (element.close_start if element.close_start is not None else -1)


def _within_marker_payload(element: _Element, start: int, end: int) -> bool:
    return start <= element.start and element.close_start is not None and element.close_start < end


def _validate_v2(text: str, canonical_template: str | None = None) -> None:
    _learning_data_block(text)
    if _version(text) != 2:
        raise UpgradeError("console is not version 2")
    probe = _probe_document(text)
    blocks = {feature: _feature_fragment(text, feature) for feature in FEATURES}
    if canonical_template is not None:
        for feature, payload in blocks.items():
            canonical = _feature_fragment(canonical_template, feature)
            if _normalize_newlines(payload) != _normalize_newlines(canonical):
                raise UpgradeError(f"{feature} marker payload does not match the canonical template")
    for feature, payload in blocks.items():
        if UNSAFE_FEATURE_RE.search(payload):
            raise UpgradeError(f"unsafe sink in {feature} marker payload")
    nav_bounds = _marker_bounds(text, "nav")
    nav = _exactly_one(probe.find("nav", lambda item: "nav-group" in _classes(item) and "aside" in item.parents), "v2 navigation group")
    if not _inside(nav, *nav_bounds):
        raise UpgradeError("navigation markers are not inside the navigation group")
    nav_link = _exactly_one(probe.find("a", lambda item: item.attr("href") == "#lesson-sessions" and "nav-link" in _classes(item) and item.parents and item.parents[-1] == "nav"), "lesson-sessions navigation link")
    if not _within_marker_payload(nav_link, *nav_bounds):
        raise UpgradeError("lesson-sessions navigation link is outside its marker payload")

    style_bounds = _marker_bounds(text, "style")
    style = _exactly_one(probe.find("style", lambda item: item.parents and item.parents[-1] == "head"), "v2 style in head")
    if not _inside(style, *style_bounds):
        raise UpgradeError("style markers are not inside head style")
    style_payload = text[style_bounds[0] : style_bounds[1]]
    if not all(selector in style_payload for selector in (".lesson-session-list", ".lesson-session-row", ".lesson-session-link")):
        raise UpgradeError("lesson session styles are incomplete")

    section_bounds = _marker_bounds(text, "section")
    section = _exactly_one(probe.find("section", lambda item: item.attr("id") == "lesson-sessions" and item.attr("data-console-feature") == "lesson-sessions-v1" and "main" in item.parents), "lesson-sessions section")
    if not (section_bounds[0] < section.start and section.close_start is not None and section.close_start < section_bounds[1]):
        raise UpgradeError("lesson-sessions markers do not surround the section")
    _exactly_one(probe.find("div", lambda item: item.attr("id") == "lessonSessionsList" and "section" in item.parents), "lesson session list")

    renderer_bounds = _marker_bounds(text, "renderer")
    call_bounds = _marker_bounds(text, "render-call")
    renderer = _renderer_script(probe)
    if not _inside(renderer, *renderer_bounds) or not _inside(renderer, *call_bounds):
        raise UpgradeError("renderer markers are not inside the renderer script")
    source = _script_source(renderer)
    if not all(_active_js_positions(source, token) for token in ("function safeLessonPath(value) {", "function renderLessonSessions(sessions, activeLesson) {", "safeLessonPath(session.indexPath)", "list.replaceChildren(...content);")):
        raise UpgradeError("lesson renderer payload is incomplete")
    if "innerHTML" in text[renderer_bounds[0] : renderer_bounds[1]]:
        raise UpgradeError("lesson renderer must not interpolate HTML")
    renderer_start = text.index(_marker("renderer", "start"))
    render_function = text.index("function render() {", renderer_start)
    if not renderer_start < renderer_bounds[1] < render_function < call_bounds[0] < call_bounds[1]:
        raise UpgradeError("renderer feature markers are in the wrong order")
    call = "renderLessonSessions(data.lessonSessions || [], data.activeLesson || null);"
    if len(_active_js_positions(source, call)) != 1 or call not in text[call_bounds[0] : call_bounds[1]]:
        raise UpgradeError("lesson renderer call is incomplete or misplaced")


def is_safe_lesson_path(value: object) -> bool:
    """Return true only for normalized workspace-relative lesson archive indexes."""
    return isinstance(value, str) and value == value.strip() and bool(ARCHIVE_PATH_RE.fullmatch(value))


def _insert_once(text: str, anchor: str, fragment: str, *, before: bool, description: str, newline: str) -> str:
    at = _one(text, anchor, description)
    insertion = f"{fragment}{newline}" if before else f"{newline}{fragment}"
    return text[:at] + insertion + text[at:] if before else text[: at + len(anchor)] + insertion + text[at + len(anchor) :]


def _set_version_2(text: str) -> str:
    html = HTML_OPEN_RE.search(text)
    if html is None:
        raise UpgradeError("html opening tag is missing")
    tag = html.group(0)
    if tag.endswith("/>"):
        raise UpgradeError("html opening tag is malformed")
    return text[: html.start()] + tag[:-1] + f' data-learning-console-version="{VERSION}">' + text[html.end() :]


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def upgrade_console(path: Path | str, template_path: Path | str) -> UpgradeReport:
    """Upgrade a proven legacy console, or return a byte-identical valid-v2 no-op."""
    target, template_file = Path(path), Path(template_path)
    try:
        original_bytes = target.read_bytes()
        template = template_file.read_text(encoding="utf-8")
        original = original_bytes.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise UpgradeError(str(exc)) from exc

    _validate_v2(template, template)
    original_data = _learning_data_block(original)
    previous_version = _version(original)
    if previous_version == 2:
        _validate_v2(original, template)
        return UpgradeReport(False, 2, 2, True)

    _validate_legacy_structure(original)
    newline = "\r\n" if "\r\n" in original else "\n"
    fragments = {feature: _normalize_newlines(_feature_fragment(template, feature), newline) for feature in FEATURES}
    staged = original
    staged = _insert_once(staged, "</style>", fragments["style"], before=True, description="legacy style closing tag", newline=newline)
    staged = _insert_once(staged, "</nav>", fragments["nav"], before=True, description="legacy navigation closing tag", newline=newline)
    staged = _insert_once(staged, '<section class="section" id="mastery">', fragments["section"], before=True, description="legacy mastery section", newline=newline)
    staged = _insert_once(staged, "    function render() {", fragments["renderer"], before=True, description="legacy render function", newline=newline)
    staged = _insert_once(staged, "renderSources(data.sourceFiles || [], data.generatedAt);", fragments["render-call"], before=False, description="legacy renderSources call", newline=newline)
    if _learning_data_block(staged) != original_data:
        raise UpgradeError("migration would alter script#learning-data")
    staged = _set_version_2(staged)
    _validate_v2(staged, template)
    try:
        _atomic_write(target, staged.encode("utf-8"))
    except (OSError, UnicodeError) as exc:
        raise UpgradeError(str(exc)) from exc
    return UpgradeReport(True, previous_version, 2, True)


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UpgradeError(message)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _JsonArgumentParser(add_help=True, description="Safely upgrade a learning console to version 2.")
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    try:
        args = parser.parse_args(argv)
        report = upgrade_console(args.html, args.template)
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        print(json.dumps({"changed": False, "error": "argument parsing failed"}, ensure_ascii=False))
        return int(exc.code) if isinstance(exc.code, int) and exc.code else 2
    except Exception as exc:
        print(json.dumps({"changed": False, "error": str(exc) or exc.__class__.__name__}, ensure_ascii=False))
        return 2
    print(json.dumps(asdict(report), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
