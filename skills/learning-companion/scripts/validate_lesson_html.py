"""Validate self-contained lesson HTML against three deterministic profiles."""

from __future__ import annotations

import argparse
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import unquote


DEFAULT_MAX_BYTES = 2_000_000
PROFILES = frozenset({"document", "technical-visual", "hub"})
ALLOWED_HUB_SCRIPTS = frozenset({"lesson-data", "lesson-refresh"})
HUB_REFRESH_BODY_SHA256 = "e8b44f8325dc81d0261961d7e465546dcd5eaee2facf01425a92268a99bcd520"
RESOURCE_ATTRIBUTES = frozenset({"src", "srcset", "href", "poster", "action", "data"})
VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
EXECUTABLE_SCHEMES = frozenset({"javascript", "vbscript"})
NETWORK_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bfetch\s*\(", re.IGNORECASE),
    re.compile(r"\bXMLHttpRequest\b", re.IGNORECASE),
    re.compile(r"\bWebSocket\b", re.IGNORECASE),
)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_STRING = re.compile(r"(['\"])(?:\\.|(?!\1).)*\1", re.DOTALL)
CSS_URL = re.compile(r"url\s*\(\s*(?:(['\"])(.*?)\1|([^\s)]+))\s*\)", re.IGNORECASE | re.DOTALL)


def append_once(errors: list[str], error: str) -> None:
    if error not in errors:
        errors.append(error)


def normalize_url(value: str) -> str:
    normalized = unescape(value)
    for _ in range(2):
        normalized = unquote(normalized)
    return re.sub(r"[\s\x00-\x20\x7f]+", "", normalized).casefold()


def url_violation(value: str) -> str | None:
    """Classify an attribute or CSS URL without resolving or opening it."""
    normalized = normalize_url(value)
    if not normalized or normalized.startswith("#"):
        return None
    match = re.match(r"([a-z][a-z0-9+.-]*):", normalized)
    scheme = match.group(1) if match else ""
    if scheme in EXECUTABLE_SCHEMES:
        return "executable-url-forbidden"
    if scheme == "data":
        media_type = normalized[5:].split(";", 1)[0].split(",", 1)[0]
        if media_type in {"text/html", "text/javascript", "application/javascript", "image/svg+xml"}:
            return "executable-url-forbidden"
        return None
    if normalized.startswith("//") or scheme:
        return "external-resource-forbidden"
    # A relative or root-local file is still an external dependency in a
    # self-contained artifact; fragment-only navigation is the sole exception.
    return "external-resource-forbidden"


def css_unescape(value: str) -> str:
    def decode_hex(match: re.Match[str]) -> str:
        codepoint = int(match.group(1), 16)
        return chr(codepoint) if codepoint else "\ufffd"

    value = re.sub(r"\\([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?", decode_hex, value)
    return re.sub(r"\\(.)", lambda match: match.group(1), value, flags=re.DOTALL)


def effective_css(style_records: list[str]) -> str:
    return css_unescape(CSS_COMMENT.sub("", "\n".join(style_records)))


def css_has_media(css: str, feature: str, value: str | None = None) -> bool:
    without_strings = CSS_STRING.sub("", css)
    expected = re.escape(feature)
    expected_value = (
        r"\s*:\s*" + re.escape(value) + r"\b"
        if value
        else r"\s*:\s*[^)\s]+"
    )
    return bool(
        re.search(
            rf"@media\s+[^{{}}]*\(\s*{expected}\b{expected_value}[^)]*\)[^{{}}]*\{{",
            without_strings,
            re.IGNORECASE,
        )
    )


class ContractParser(HTMLParser):
    """Collect contract-relevant tokens and reject non-well-formed input."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doctypes = 0
        self.html_roots = 0
        self.sections = 0
        self.svgs = 0
        self.scripts = 0
        self.iframes = 0
        self.external_resources: list[str] = []
        self.executable_urls: list[str] = []
        self.event_handlers: list[str] = []
        self.svg_records: list[dict[str, Any]] = []
        self.script_records: list[dict[str, Any]] = []
        self.style_records: list[list[str]] = []
        self.content_chunks: list[str] = []
        self._tag_stack: list[str] = []
        self._svg_stack: list[dict[str, Any]] = []
        self._script_stack: list[dict[str, Any]] = []
        self._style_stack: list[list[str]] = []
        self._html_seen = False
        self._head_count = 0
        self._body_count = 0
        self.malformed = False

    def mark_malformed(self) -> None:
        self.malformed = True

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() != "doctype html":
            self.mark_malformed()
            return
        self.doctypes += 1
        if self._tag_stack or self._html_seen or self.doctypes != 1:
            self.mark_malformed()

    def unknown_decl(self, data: str) -> None:
        self.mark_malformed()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        self._validate_start(normalized_tag, attrs)
        attributes = {name.lower(): value for name, value in attrs}
        self._record_attributes(attrs)

        if normalized_tag == "html":
            self.html_roots += 1
        elif normalized_tag == "section":
            self.sections += 1
        elif normalized_tag == "script":
            self.scripts += 1
            record = {"attrs": attributes, "body": []}
            self.script_records.append(record)
            self._script_stack.append(record)
        elif normalized_tag == "style":
            record: list[str] = []
            self.style_records.append(record)
            self._style_stack.append(record)
        elif normalized_tag == "iframe":
            self.iframes += 1

        if normalized_tag == "svg":
            record = {
                "role": (attributes.get("role") or "").lower() == "img",
                "title": False,
                "desc": False,
                "node_ids": set(),
                "edges": [],
            }
            self.svgs += 1
            self.svg_records.append(record)
            self._svg_stack.append(record)
        elif self._svg_stack:
            current_svg = self._svg_stack[-1]
            if normalized_tag == "title":
                current_svg["title"] = True
            elif normalized_tag == "desc":
                current_svg["desc"] = True
            node_id = attributes.get("data-node-id")
            if node_id:
                current_svg["node_ids"].add(node_id)
            edge_from = attributes.get("data-edge-from")
            edge_to = attributes.get("data-edge-to")
            if edge_from and edge_to:
                current_svg["edges"].append((edge_from, edge_to))

        if normalized_tag not in VOID_TAGS:
            self._tag_stack.append(normalized_tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in VOID_TAGS or not self._tag_stack or self._tag_stack[-1] != normalized_tag:
            self.mark_malformed()
            return
        self._tag_stack.pop()
        if normalized_tag == "svg" and self._svg_stack:
            self._svg_stack.pop()
        elif normalized_tag == "script" and self._script_stack:
            self._script_stack.pop()
        elif normalized_tag == "style" and self._style_stack:
            self._style_stack.pop()
        if normalized_tag == "html" and (self._head_count != 1 or self._body_count != 1):
            self.mark_malformed()

    def handle_data(self, data: str) -> None:
        if not self._tag_stack and data.strip():
            self.mark_malformed()
        self.content_chunks.append(data)
        if self._script_stack:
            self._script_stack[-1]["body"].append(data)
        if self._style_stack:
            self._style_stack[-1].append(data)

    def finish(self) -> None:
        if self._tag_stack or self._svg_stack or self._script_stack or self._style_stack:
            self.mark_malformed()
        if not self._html_seen or self._head_count != 1 or self._body_count != 1:
            self.mark_malformed()

    def _validate_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        seen_attributes: set[str] = set()
        for name, _ in attrs:
            normalized_name = name.lower()
            if normalized_name in seen_attributes:
                self.mark_malformed()
            seen_attributes.add(normalized_name)

        if tag == "html":
            if self._html_seen or self._tag_stack:
                self.mark_malformed()
            self._html_seen = True
            return
        if not self._tag_stack:
            self.mark_malformed()
            return
        parent = self._tag_stack[-1]
        if parent == "html":
            if tag == "head":
                if self._head_count or self._body_count:
                    self.mark_malformed()
                self._head_count += 1
            elif tag == "body":
                if self._head_count != 1 or self._body_count:
                    self.mark_malformed()
                self._body_count += 1
            else:
                self.mark_malformed()
        elif tag in {"head", "body"}:
            self.mark_malformed()
        if tag == "section" and "body" not in self._tag_stack:
            self.mark_malformed()

    def _record_attributes(self, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            normalized_name = name.lower()
            if normalized_name.startswith("on"):
                self.event_handlers.append(normalized_name)
            if normalized_name in RESOURCE_ATTRIBUTES and value is not None:
                violation = url_violation(value)
                if violation == "external-resource-forbidden":
                    self.external_resources.append(value)
                elif violation == "executable-url-forbidden":
                    self.executable_urls.append(value)

    def metrics(self) -> dict[str, int]:
        return {
            "sizeBytes": 0,
            "sectionCount": self.sections,
            "svgCount": self.svgs,
            "scriptCount": self.scripts,
            "iframeCount": self.iframes,
            "externalResourceCount": len(self.external_resources),
        }


def decode_utf8_without_bom(raw: bytes) -> tuple[str, list[str]]:
    errors: list[str] = []
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    if has_bom:
        errors.append("utf8-bom")
    try:
        return (raw[3:] if has_bom else raw).decode("utf-8"), errors
    except UnicodeDecodeError:
        errors.append("invalid-utf8")
        return (raw[3:] if has_bom else raw).decode("utf-8", errors="replace"), errors


def enforce_shared_contract(
    parser: ContractParser,
    text: str,
    raw: bytes,
    required_terms: tuple[str, ...],
    max_bytes: int,
    errors: list[str],
) -> None:
    if parser.malformed:
        append_once(errors, "malformed-html")
    if parser.doctypes != 1:
        append_once(errors, "doctype-count")
    if parser.html_roots != 1:
        append_once(errors, "html-root-count")
    if parser.sections < 1:
        append_once(errors, "section-missing")
    if parser.iframes:
        append_once(errors, "iframe-forbidden")
    if parser.event_handlers:
        append_once(errors, "event-handler-forbidden")
    if parser.executable_urls:
        append_once(errors, "executable-url-forbidden")
    if parser.external_resources:
        append_once(errors, "external-resource-forbidden")
    if parser.svg_records and any(
        not (record["role"] and record["title"] and record["desc"])
        for record in parser.svg_records
    ):
        append_once(errors, "svg-accessibility-incomplete")

    css = effective_css(["".join(record) for record in parser.style_records])
    for match in CSS_URL.finditer(css):
        value = match.group(2) if match.group(1) is not None else match.group(3)
        violation = url_violation(value)
        if violation:
            append_once(errors, violation)
    if re.search(r"@import\b", CSS_STRING.sub("", css), re.IGNORECASE):
        append_once(errors, "network-reference-forbidden")
    executable_script_text = "\n".join(
        "".join(record["body"])
        for record in parser.script_records
        if (record["attrs"].get("type") or "").strip().lower() != "application/json"
    )
    if any(pattern.search(executable_script_text) for pattern in NETWORK_PATTERNS):
        append_once(errors, "network-reference-forbidden")
    if not css_has_media(css, "max-width"):
        append_once(errors, "responsive-rule-missing")
    if not css_has_media(css, "prefers-reduced-motion", "reduce"):
        append_once(errors, "reduced-motion-rule-missing")
    if not css_has_media(css, "prefers-color-scheme", "dark"):
        append_once(errors, "color-scheme-rule-missing")
    if len(raw) > max_bytes:
        append_once(errors, "size-limit-exceeded")
    for term in required_terms:
        if term not in text:
            append_once(errors, f"required-term-missing:{term}")


def has_relational_svg(parser: ContractParser) -> bool:
    for record in parser.svg_records:
        nodes = record["node_ids"]
        if len(nodes) >= 2 and any(
            source in nodes and target in nodes and source != target
            for source, target in record["edges"]
        ):
            return True
    return False


def enforce_hub_scripts(parser: ContractParser, errors: list[str]) -> None:
    data_scripts: list[dict[str, Any]] = []
    refresh_scripts: list[dict[str, Any]] = []
    for record in parser.script_records:
        attrs = record["attrs"]
        script_id = attrs.get("id")
        if script_id not in ALLOWED_HUB_SCRIPTS:
            append_once(errors, "hub-script-not-allowlisted")
            continue
        allowed_attributes = {"id", "type"}
        if set(attrs) - allowed_attributes:
            append_once(errors, "hub-script-attributes-invalid")
        if script_id == "lesson-data":
            data_scripts.append(record)
        else:
            refresh_scripts.append(record)

    if len(data_scripts) != 1:
        append_once(errors, "hub-data-script-invalid")
    else:
        data_script = data_scripts[0]
        data_type = (data_script["attrs"].get("type") or "").strip().lower()
        try:
            json.loads("".join(data_script["body"]))
        except (json.JSONDecodeError, ValueError):
            valid_json = False
        else:
            valid_json = True
        if data_type != "application/json" or not valid_json:
            append_once(errors, "hub-data-script-invalid")

    if len(refresh_scripts) > 1:
        append_once(errors, "hub-refresh-script-invalid")
    elif refresh_scripts:
        refresh_script = refresh_scripts[0]
        body = "".join(refresh_script["body"])
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        script_type = (refresh_script["attrs"].get("type") or "").strip().lower()
        if script_type not in {"", "text/javascript"} or digest != HUB_REFRESH_BODY_SHA256:
            append_once(errors, "hub-refresh-script-invalid")


def validate_html(
    path: Path,
    required_terms: tuple[str, ...],
    profile: str,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Return a deterministic validation report for one lesson HTML artifact."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    raw = Path(path).read_bytes()
    text, errors = decode_utf8_without_bom(raw)
    parser = ContractParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        parser.mark_malformed()
    parser.finish()

    enforce_shared_contract(parser, text, raw, required_terms, max_bytes, errors)
    if profile == "technical-visual":
        if parser.svgs == 0:
            append_once(errors, "svg-missing")
        elif not has_relational_svg(parser):
            append_once(errors, "svg-relational-semantics-missing")
    if profile in {"document", "technical-visual"} and parser.scripts:
        append_once(errors, "script-forbidden")
    if profile == "hub":
        enforce_hub_scripts(parser, errors)

    metrics = parser.metrics()
    metrics["sizeBytes"] = len(raw)
    return {"overall": "passed" if not errors else "failed", "errors": errors, "metrics": metrics}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an offline lesson HTML artifact.")
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument("--required-term", action="append", default=[])
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    return parser


def configure_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    except (AttributeError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdout()
    args = build_parser().parse_args(argv)
    try:
        report = validate_html(args.html, tuple(args.required_term), args.profile, args.max_bytes)
    except OSError as exc:
        report = {"overall": "failed", "errors": [f"file-read-failed:{exc}"], "metrics": {}}
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["overall"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
