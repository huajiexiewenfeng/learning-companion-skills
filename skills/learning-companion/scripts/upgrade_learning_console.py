"""Safely add lesson-archive support to a version-1 learning console.

The upgrader deliberately does not parse or regenerate ``window.learningData``.
It makes five marker-delimited insertions around uniquely validated legacy anchors,
then atomically writes a UTF-8 (without BOM) replacement.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


VERSION = "2"
FEATURES = ("nav", "style", "section", "renderer", "render-call")
DATA_OPEN_RE = re.compile(
    r"<script\b(?=[^>]*\bid\s*=\s*['\"]learning-data['\"])[^>]*>", re.IGNORECASE
)
HTML_OPEN_RE = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
VERSION_RE = re.compile(r"\sdata-learning-console-version\s*=\s*(['\"])([^'\"]*)\1", re.IGNORECASE)


class UpgradeError(ValueError):
    """Raised when a console cannot be proven safe to modify."""


@dataclass(frozen=True)
class UpgradeReport:
    changed: bool
    previous_version: int
    current_version: int
    preserved_data_block: bool


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
    return int(match.group(2))


def _feature_fragment(template: str, feature: str) -> str:
    start = _marker(feature, "start")
    end = _marker(feature, "end")
    start_at = _one(template, start, f"template {feature} start marker")
    end_at = _one(template, end, f"template {feature} end marker")
    if end_at <= start_at:
        raise UpgradeError(f"template {feature} markers are out of order")
    return template[start_at : end_at + len(end)]


def _validate_v2(text: str) -> None:
    _learning_data_block(text)
    if _version(text) != 2:
        raise UpgradeError("console is not version 2")
    for feature in FEATURES:
        start_at = _one(text, _marker(feature, "start"), f"{feature} start marker")
        end_at = _one(text, _marker(feature, "end"), f"{feature} end marker")
        if end_at <= start_at:
            raise UpgradeError(f"{feature} markers are out of order")


def _insert_once(text: str, anchor: str, fragment: str, *, before: bool, description: str, newline: str) -> str:
    at = _one(text, anchor, description)
    insertion = f"{fragment}{newline}" if before else f"{newline}{fragment}"
    return text[:at] + insertion + text[at:] if before else text[: at + len(anchor)] + insertion + text[at + len(anchor) :]


def _set_version_2(text: str) -> str:
    html = HTML_OPEN_RE.search(text)
    if html is None:  # _version has already verified this, kept for type safety.
        raise UpgradeError("html opening tag is missing")
    tag = html.group(0)
    if tag.endswith("/>"):
        raise UpgradeError("html opening tag is malformed")
    updated = tag[:-1] + f' data-learning-console-version="{VERSION}">'
    return text[: html.start()] + updated + text[html.end() :]


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
    """Upgrade one legacy console, or return a byte-identical v2 no-op report."""
    target = Path(path)
    template_file = Path(template_path)
    try:
        original_bytes = target.read_bytes()
        template = template_file.read_text(encoding="utf-8")
        original = original_bytes.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise UpgradeError(str(exc)) from exc

    # A valid template is the sole source of inserted v2 fragments.
    _validate_v2(template)
    original_data = _learning_data_block(original)
    previous_version = _version(original)
    if previous_version == 2:
        _validate_v2(original)
        return UpgradeReport(False, 2, 2, True)

    newline = "\r\n" if "\r\n" in original else "\n"
    fragments = {feature: _feature_fragment(template, feature) for feature in FEATURES}
    staged = original
    staged = _insert_once(staged, "</style>", fragments["style"], before=True, description="legacy style closing tag", newline=newline)
    staged = _insert_once(staged, "</nav>", fragments["nav"], before=True, description="legacy navigation closing tag", newline=newline)
    staged = _insert_once(staged, '<section class="section" id="mastery">', fragments["section"], before=True, description="legacy mastery section", newline=newline)
    staged = _insert_once(staged, "    function render() {", fragments["renderer"], before=True, description="legacy render function", newline=newline)
    staged = _insert_once(staged, "renderSources(data.sourceFiles || [], data.generatedAt);", fragments["render-call"], before=False, description="legacy renderSources call", newline=newline)

    # Every fragment must be present and ordered before the version is changed.
    for feature in FEATURES:
        _one(staged, _marker(feature, "start"), f"inserted {feature} start marker")
        _one(staged, _marker(feature, "end"), f"inserted {feature} end marker")
    if _learning_data_block(staged) != original_data:
        raise UpgradeError("migration would alter script#learning-data")
    staged = _set_version_2(staged)
    _validate_v2(staged)
    _atomic_write(target, staged.encode("utf-8"))
    return UpgradeReport(True, previous_version, 2, True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely upgrade a learning console to version 2.")
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = upgrade_console(args.html, args.template)
    except UpgradeError as exc:
        print(json.dumps({"changed": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(asdict(report), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
