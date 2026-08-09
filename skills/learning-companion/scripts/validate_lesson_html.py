"""Validate offline lesson HTML against document, visual, and hub contracts."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_MAX_BYTES = 2_000_000
PROFILES = frozenset({"document", "technical-visual", "hub"})
ALLOWED_HUB_SCRIPTS = frozenset({"lesson-data", "lesson-refresh"})
HUB_REFRESH_BODY_SHA256 = "e8b44f8325dc81d0261961d7e465546dcd5eaee2facf01425a92268a99bcd520"
RESOURCE_ATTRIBUTES = frozenset({"src", "srcset", "href", "poster", "action", "data"})
NETWORK_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"@import\s+url\s*\(", re.IGNORECASE),
    re.compile(r"\bfetch\s*\(", re.IGNORECASE),
    re.compile(r"\bXMLHttpRequest\b", re.IGNORECASE),
    re.compile(r"\bWebSocket\b", re.IGNORECASE),
)


class ContractParser(HTMLParser):
    """Collect contract-relevant markup without executing or fetching anything."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doctypes = 0
        self.html_roots = 0
        self.sections = 0
        self.svgs = 0
        self.scripts = 0
        self.iframes = 0
        self.external_resources: list[str] = []
        self.svg_records: list[dict[str, bool]] = []
        self.script_records: list[dict[str, Any]] = []
        self._svg_stack: list[dict[str, bool]] = []
        self._script_stack: list[dict[str, Any]] = []

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() == "doctype html":
            self.doctypes += 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {name.lower(): value for name, value in attrs}
        if tag == "html":
            self.html_roots += 1
        elif tag == "section":
            self.sections += 1
        elif tag == "script":
            self.scripts += 1
            record = {"attrs": attributes, "body": []}
            self.script_records.append(record)
            self._script_stack.append(record)
        elif tag == "iframe":
            self.iframes += 1

        if tag == "svg":
            record = {
                "role": (attributes.get("role") or "").lower() == "img",
                "title": False,
                "desc": False,
            }
            self.svgs += 1
            self.svg_records.append(record)
            self._svg_stack.append(record)
        elif self._svg_stack and tag == "title":
            self._svg_stack[-1]["title"] = True
        elif self._svg_stack and tag == "desc":
            self._svg_stack[-1]["desc"] = True

        for name, value in attrs:
            if name.lower() in RESOURCE_ATTRIBUTES and value is not None:
                if re.search(r"(?:https?:)?//", value, re.IGNORECASE):
                    self.external_resources.append(value)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized == "svg" and self._svg_stack:
            self._svg_stack.pop()
        elif normalized == "script" and self._script_stack:
            self._script_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._script_stack:
            self._script_stack[-1]["body"].append(data)

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
    *,
    require_motion_and_dark_mode: bool,
) -> None:
    if parser.doctypes != 1:
        errors.append("doctype-count")
    if parser.html_roots != 1:
        errors.append("html-root-count")
    if parser.sections < 1:
        errors.append("section-missing")
    if parser.iframes:
        errors.append("iframe-forbidden")
    if parser.external_resources:
        errors.append("external-resource-forbidden")
    if any(pattern.search(text) for pattern in NETWORK_PATTERNS):
        errors.append("network-reference-forbidden")
    if parser.svg_records and any(not all(record.values()) for record in parser.svg_records):
        errors.append("svg-accessibility-incomplete")
    if not re.search(r"@media\s*\([^)]*max-width\s*:", text, re.IGNORECASE):
        errors.append("responsive-rule-missing")
    if require_motion_and_dark_mode:
        lowered = text.lower()
        if "prefers-reduced-motion" not in lowered:
            errors.append("reduced-motion-rule-missing")
        if "prefers-color-scheme" not in lowered:
            errors.append("color-scheme-rule-missing")
    if len(raw) > max_bytes:
        errors.append("size-limit-exceeded")
    for term in required_terms:
        if term not in text:
            errors.append(f"required-term-missing:{term}")


def enforce_hub_scripts(parser: ContractParser, errors: list[str]) -> None:
    data_scripts = []
    refresh_scripts = []
    for record in parser.script_records:
        attrs = record["attrs"]
        script_id = attrs.get("id")
        if script_id not in ALLOWED_HUB_SCRIPTS:
            errors.append("hub-script-not-allowlisted")
            continue
        if script_id == "lesson-data":
            data_scripts.append(record)
        else:
            refresh_scripts.append(record)

    if len(data_scripts) != 1:
        errors.append("hub-data-script-invalid")
    else:
        data_script = data_scripts[0]
        data_type = (data_script["attrs"].get("type") or "").strip().lower()
        try:
            json.loads("".join(data_script["body"]))
        except json.JSONDecodeError:
            valid_json = False
        else:
            valid_json = True
        if data_type != "application/json" or not valid_json:
            errors.append("hub-data-script-invalid")

    if len(refresh_scripts) > 1:
        errors.append("hub-refresh-script-invalid")
    elif refresh_scripts:
        refresh_script = refresh_scripts[0]
        body = "".join(refresh_script["body"])
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        script_type = (refresh_script["attrs"].get("type") or "").strip().lower()
        if script_type not in {"", "text/javascript"} or digest != HUB_REFRESH_BODY_SHA256:
            errors.append("hub-refresh-script-invalid")


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
    parser.feed(text)
    parser.close()

    enforce_shared_contract(
        parser,
        text,
        raw,
        required_terms,
        max_bytes,
        errors,
        require_motion_and_dark_mode=profile in {"document", "technical-visual"},
    )
    if profile == "technical-visual" and parser.svgs == 0:
        errors.append("svg-missing")
    if profile in {"document", "technical-visual"} and parser.scripts:
        errors.append("script-forbidden")
    if profile == "hub":
        enforce_hub_scripts(parser, errors)

    metrics = parser.metrics()
    metrics["sizeBytes"] = len(raw)
    return {
        "overall": "passed" if not errors else "failed",
        "errors": errors,
        "metrics": metrics,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an offline lesson HTML artifact.")
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument("--required-term", action="append", default=[])
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_html(
            args.html,
            tuple(args.required_term),
            args.profile,
            max_bytes=args.max_bytes,
        )
    except OSError as exc:
        report = {"overall": "failed", "errors": [f"file-read-failed:{exc}"], "metrics": {}}
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["overall"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
