"""Safely allocate, render, validate, version, and close lesson packages.

The module deliberately keeps final lesson artifacts immutable.  Rendering occurs
in a session-local staging directory; only a package that clears every contract
gate is promoted into the plan's ``lessons`` directory.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Iterable, Mapping
from uuid import uuid4

from lesson_model import (
    SESSION_DEPTHS,
    SESSION_MODES,
    load_lesson_model,
    slugify,
    validate_lesson_model,
)
from render_lesson import RenderedArtifact, render_deck, render_hub, render_section
from validate_lesson_html import PROFILES, validate_html


ASSETS = Path(__file__).resolve().parent.parent / "assets"
THEME = ASSETS / "lesson-theme.css"
LEDGER = "artifacts.md"
FROZEN_MARKER = ".artifacts-frozen"
LIFECYCLE_STATUSES = frozenset(
    {
        "preparing",
        "ready",
        "in-progress",
        "completed",
        "archived",
        "studying",
        "awaiting-voice",
        "closed",
    }
)
LEDGER_FIELDS = (
    "id",
    "logicalId",
    "path",
    "type",
    "title",
    "profile",
    "sourceTurn",
    "sourceRefs",
    "version",
    "status",
    "sha256",
    "createdAt",
    "updatedAt",
    "supersedes",
)


@dataclass(frozen=True)
class PackageReport:
    """Deterministic result shared by API and CLI callers."""

    overall: str
    status: str
    errors: tuple[str, ...] = ()
    artifacts: tuple[dict[str, str], ...] = ()
    topic: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "status": self.status,
            "errors": list(self.errors),
            "artifacts": list(self.artifacts),
            "topic": self.topic,
        }


@dataclass(frozen=True)
class ArtifactSpec:
    logical_id: str
    title: str
    artifact_type: str
    profile: str
    relative_path: str
    html: str
    source_refs: tuple[str, ...]
    required_terms: tuple[str, ...]
    mutable_index: bool = False


@dataclass(frozen=True)
class LedgerRecord:
    artifact_id: str
    logical_id: str
    relative_path: str
    artifact_type: str
    title: str
    profile: str
    source_turn: str
    source_refs: tuple[str, ...]
    version: int
    status: str
    sha256: str
    created_at: str
    updated_at: str
    supersedes: str

    def summary(self) -> dict[str, str]:
        return {
            "id": self.artifact_id,
            "path": self.relative_path,
            "type": self.artifact_type,
            "profile": self.profile,
            "sha256": self.sha256,
        }


def assert_within(target: Path, root: Path) -> Path:
    """Resolve a target and prove it cannot escape its lesson root.

    ``Path.resolve`` intentionally follows existing symlinks, so a malicious
    symlink under a session is rejected before it can receive a write or move.
    """
    resolved_target = Path(target).resolve(strict=False)
    resolved_root = Path(root).resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path escapes lesson root: {target}") from exc
    return resolved_target


def allocate_session(
    plan_dir: Path, day: int, topic: str, mode: str, depth: str, local_date: date
) -> Path:
    """Atomically reserve the next historical session directory for a plan."""
    if not isinstance(day, int) or isinstance(day, bool) or day < 1:
        raise ValueError("day must be a positive integer")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("topic must be a nonempty string")
    if mode not in SESSION_MODES:
        raise ValueError(f"unsupported lesson mode: {mode}")
    if depth not in SESSION_DEPTHS:
        raise ValueError(f"unsupported lesson depth: {depth}")
    if not isinstance(local_date, date):
        raise ValueError("local_date must be a date")

    plan_root = Path(plan_dir).resolve()
    if not plan_root.is_dir():
        raise ValueError(f"plan directory does not exist: {plan_dir}")
    lessons_root = assert_within(plan_root / "lessons", plan_root)
    lessons_root.mkdir(parents=True, exist_ok=True)
    lessons_root = lessons_root.resolve()
    prefix = f"{local_date.isoformat()}-day-{day:03d}-session-"
    sequence = _next_session_number(lessons_root, prefix)

    while True:
        session_dir = assert_within(lessons_root / f"{prefix}{sequence:02d}", lessons_root)
        try:
            # mkdir is the reservation.  Unlike exists()+mkdir(), it cannot
            # overwrite a concurrent allocation.
            session_dir.mkdir()
            break
        except FileExistsError:
            sequence += 1

    _write_lesson_skeleton(session_dir, plan_root.name, day, topic, mode, depth)
    _atomic_write_text(assert_within(session_dir / LEDGER, lessons_root), _serialize_ledger(()), lessons_root)
    return session_dir


def prepare_session(session_dir: Path) -> PackageReport:
    """Render a new lesson package, promoting it only after all gates pass."""
    return _package_session(Path(session_dir), action="prepare")


def sync_session(session_dir: Path) -> PackageReport:
    """Refresh a mutable lesson index and append immutable changed artifacts."""
    session = Path(session_dir)
    try:
        session, lessons_root = _session_roots(session)
    except ValueError as exc:
        return _failed("preparing", str(exc))
    if assert_within(session / FROZEN_MARKER, lessons_root).exists():
        return _failed(_lesson_status(session), "artifacts-frozen")
    return _package_session(session, action="sync")


def close_session(session_dir: Path) -> PackageReport:
    """Freeze a package and remove the hub refresh script without touching progress."""
    session = Path(session_dir)
    try:
        session, lessons_root = _session_roots(session)
    except ValueError as exc:
        return _failed("preparing", str(exc))
    marker = assert_within(session / FROZEN_MARKER, lessons_root)
    if marker.exists():
        return validate_session(session)

    report = _package_session(session, action="close")
    if report.overall != "passed":
        return report
    model_path = assert_within(session / "lesson-model.json", lessons_root)
    model = load_lesson_model(model_path)
    model["session"]["status"] = "closed"
    atomic_write_json(model_path, model, lessons_root)
    set_lesson_frontmatter_status(assert_within(session / "lesson.md", lessons_root), "closed", lessons_root)
    _atomic_write_text(marker, "frozen\n", lessons_root)
    return replace(report, status="closed")


def validate_session(session_dir: Path) -> PackageReport:
    """Validate every ledger artifact, global term evidence, and source authority."""
    try:
        session, lessons_root = _session_roots(Path(session_dir))
    except ValueError as exc:
        return _failed("preparing", str(exc))
    status = _lesson_status(session)
    if not assert_within(session / "lesson.md", lessons_root).is_file():
        return _failed(status, "lesson-markdown-missing")
    model, model_errors = _load_valid_model(session, lessons_root)
    if model_errors:
        return _failed(status, *model_errors)
    records, ledger_errors = _read_ledger(assert_within(session / LEDGER, lessons_root))
    errors = list(ledger_errors)
    if not records:
        errors.append("artifact-ledger-empty")
    errors.extend(_minimum_package_errors(records, model))
    allowed_sources = _authorized_sources(session, model)
    artifact_text: list[str] = []
    for record in records:
        if record.profile not in PROFILES:
            errors.append(f"artifact-profile-invalid:{record.artifact_id}")
            continue
        try:
            artifact_path = assert_within(session / record.relative_path, lessons_root)
        except ValueError:
            errors.append(f"artifact-path-escapes:{record.artifact_id}")
            continue
        if not artifact_path.is_file():
            errors.append(f"artifact-missing:{record.relative_path}")
            continue
        actual_hash = _sha256(artifact_path.read_bytes())
        if actual_hash != record.sha256:
            errors.append(f"artifact-hash-mismatch:{record.artifact_id}")
        validation = validate_html(artifact_path, (), record.profile)
        errors.extend(
            f"artifact-invalid:{record.artifact_id}:{error}" for error in validation["errors"]
        )
        artifact_text.append(artifact_path.read_text(encoding="utf-8"))
        for source_ref in record.source_refs:
            if source_ref not in allowed_sources:
                errors.append(f"source-reference-unauthorized:{source_ref}")
    errors.extend(_global_term_errors(model, artifact_text))
    return _report("failed" if errors else "passed", status, errors, records, model)


def atomic_write_json(path: Path, value: Mapping[str, Any], lessons_root: Path | None = None) -> None:
    """Write deterministic UTF-8 JSON without exposing a partial model file."""
    root = lessons_root or Path(path).parent
    _atomic_write_text(
        Path(path), json.dumps(value, ensure_ascii=False, indent=2) + "\n", Path(root)
    )


def set_lesson_frontmatter_status(
    lesson_path: Path, status: str, lessons_root: Path | None = None
) -> None:
    """Set only the lesson session status in its deliberately small front matter."""
    root = lessons_root or Path(lesson_path).parent
    target = assert_within(lesson_path, root)
    text = target.read_text(encoding="utf-8")
    updated, count = re.subn(r"(?m)^status: .*$", f"status: {status}", text, count=1)
    if count != 1:
        raise ValueError("lesson.md is missing frontmatter status")
    _atomic_write_text(target, updated, Path(root))


def _package_session(session_dir: Path, action: str) -> PackageReport:
    try:
        session, lessons_root = _session_roots(session_dir)
    except ValueError as exc:
        return _failed("preparing", str(exc))
    prior_status = _lesson_status(session)
    if not assert_within(session / "lesson.md", lessons_root).is_file():
        return _failed(prior_status, "lesson-markdown-missing")
    model, model_errors = _load_valid_model(session, lessons_root)
    if model_errors:
        return _failed(prior_status, *model_errors)
    if action == "prepare" and prior_status != "preparing":
        return _failed(prior_status, "prepare-requires-preparing-status")
    if action not in {"prepare", "sync", "close"}:
        return _failed(prior_status, f"unknown-package-action:{action}")

    records, ledger_errors = _read_ledger(assert_within(session / LEDGER, lessons_root))
    if ledger_errors:
        return _failed(prior_status, *ledger_errors)
    desired_status = "closed" if action == "close" else _active_status(model)
    refresh = action != "close"
    stage = assert_within(session / f".lesson-stage-{uuid4().hex}", lessons_root)
    try:
        stage.mkdir()
        specs, build_errors = _build_artifacts(model, refresh)
        if build_errors:
            return _failed(prior_status, *build_errors)
        staged = _write_and_validate_stage(stage, specs, lessons_root)
        gate_errors = _package_gate_errors(model, specs, staged, session)
        if gate_errors:
            return _failed(prior_status, *gate_errors)
        promoted = _promote_artifacts(session, lessons_root, specs, staged, records)
        _atomic_write_text(
            assert_within(session / LEDGER, lessons_root), _serialize_ledger(promoted), lessons_root
        )
        if action != "close":
            _write_lifecycle_status(session, lessons_root, model, desired_status)
        return _report("passed", desired_status, (), promoted, model)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _failed(prior_status, f"package-error:{exc}")
    finally:
        if stage.exists():
            # Stage contents are never evidence or history.  It is safe to
            # remove only this UUID-named directory after the gated operation.
            shutil.rmtree(stage, ignore_errors=True)


def _session_roots(session_dir: Path) -> tuple[Path, Path]:
    candidate = Path(session_dir)
    lessons_root = candidate.parent.resolve(strict=False)
    if lessons_root.name != "lessons":
        raise ValueError("session directory must be directly inside a lessons directory")
    session = candidate.resolve(strict=False)
    assert_within(session, lessons_root)
    if session.parent != lessons_root:
        raise ValueError("session directory must be directly inside a lessons directory")
    if not session.is_dir():
        raise ValueError(f"session directory does not exist: {session_dir}")
    return session, lessons_root


def _next_session_number(lessons_root: Path, prefix: str) -> int:
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    used = (
        int(match.group(1))
        for path in lessons_root.iterdir()
        if path.is_dir() and (match := pattern.match(path.name))
    )
    return max(used, default=0) + 1


def _write_lesson_skeleton(
    session: Path, plan_id: str, day: int, topic: str, mode: str, depth: str
) -> None:
    lessons_root = session.parent
    lesson = (
        "---\n"
        f"id: {session.name}\n"
        f"planId: {plan_id}\n"
        f"day: {day}\n"
        f"topic: {json.dumps(topic, ensure_ascii=False)}\n"
        f"mode: {mode}\n"
        f"depth: {depth}\n"
        "status: preparing\n"
        "sources:\n"
        "---\n\n"
        f"# {topic}\n"
    )
    _atomic_write_text(assert_within(session / "lesson.md", lessons_root), lesson, lessons_root)


def _load_valid_model(session: Path, lessons_root: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    model_path = assert_within(session / "lesson-model.json", lessons_root)
    if not model_path.is_file():
        return {}, ("lesson-model-missing",)
    try:
        model = load_lesson_model(model_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, (f"lesson-model-load-failed:{exc}",)
    normalized = copy.deepcopy(model)
    session_model = normalized.get("session")
    if isinstance(session_model, dict) and session_model.get("status") in LIFECYCLE_STATUSES:
        session_model["status"] = "preparing"
    issues = validate_lesson_model(normalized)
    return model, tuple(f"model-invalid:{issue.code}:{issue.path}" for issue in issues)


def _active_status(model: Mapping[str, Any]) -> str:
    return "awaiting-voice" if model["session"]["mode"] == "voice" else "studying"


def _theme_css() -> str:
    if not THEME.is_file():
        raise ValueError("lesson-theme-missing")
    return THEME.read_text(encoding="utf-8")


def _build_artifacts(
    model: Mapping[str, Any], refresh: bool
) -> tuple[tuple[ArtifactSpec, ...], tuple[str, ...]]:
    try:
        theme_css = _theme_css()
        sections = tuple(model["sections"])
        by_id = {section["id"]: section for section in sections}
        decks = _deck_definitions(model, sections)
        specs: list[ArtifactSpec] = []
        all_sources = _unique_sources(
            source for section in sections for source in section.get("sourceRefs", ())
        )
        hub = render_hub(model, decks, theme_css, refresh)
        specs.append(_artifact_spec(hub, "hub", all_sources, mutable_index=True))
        for section in sections:
            card = render_section(model, section, theme_css)
            specs.append(_artifact_spec(card, "card", tuple(section["sourceRefs"])))
        for deck_number, deck in enumerate(decks, start=1):
            deck_id = slugify(str(deck["id"])) or f"deck-{deck_number}"
            deck_root = f"decks/{deck_number:03d}-{deck_id}"
            deck_sections = tuple(by_id[section_id] for section_id in deck["sectionIds"])
            deck_artifact = render_deck(
                model, deck, deck_sections, theme_css, f"{deck_root}/index.html"
            )
            deck_sources = _unique_sources(
                source for section in deck_sections for source in section.get("sourceRefs", ())
            )
            specs.append(
                _artifact_spec(
                    deck_artifact,
                    "deck",
                    deck_sources,
                    logical_id=f"deck-{deck_number:03d}-{deck_id}",
                    mutable_index=True,
                )
            )
            for slide_number, section in enumerate(deck_sections, start=1):
                slide = render_section(model, section, theme_css)
                slide = replace(
                    slide,
                    id=f"slide-{deck_number:03d}-{deck_id}-{slide_number:03d}-{slugify(section['id'])}",
                    relative_path=(
                        f"{deck_root}/slides/{slide_number:03d}-{slugify(section['id'])}.html"
                    ),
                )
                specs.append(
                    _artifact_spec(slide, "slide", tuple(section["sourceRefs"]))
                )
        return tuple(specs), ()
    except (KeyError, TypeError, ValueError) as exc:
        return (), (f"render-build-failed:{exc}",)


def _deck_definitions(
    model: Mapping[str, Any], sections: tuple[Mapping[str, Any], ...]
) -> tuple[Mapping[str, Any], ...]:
    declared = model.get("decks")
    if isinstance(declared, list) and declared:
        return tuple(declared)
    return (
        {
            "id": "main",
            "title": f"{model['session']['topic']} main deck",
            "sectionIds": [section["id"] for section in sections],
        },
    )


def _artifact_spec(
    artifact: RenderedArtifact,
    artifact_type: str,
    source_refs: tuple[str, ...],
    logical_id: str | None = None,
    mutable_index: bool = False,
) -> ArtifactSpec:
    return ArtifactSpec(
        logical_id=logical_id or artifact.id,
        title=artifact.title,
        artifact_type=artifact_type,
        profile=artifact.profile,
        relative_path=artifact.relative_path,
        html=artifact.html,
        source_refs=source_refs,
        required_terms=artifact.required_terms,
        mutable_index=mutable_index,
    )


def _write_and_validate_stage(
    stage: Path, specs: Iterable[ArtifactSpec], lessons_root: Path
) -> dict[str, Path]:
    staged: dict[str, Path] = {}
    for spec in specs:
        target = assert_within(stage / spec.relative_path, lessons_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(target, spec.html, lessons_root)
        validation = validate_html(target, spec.required_terms, spec.profile)
        if validation["overall"] != "passed":
            rendered = ",".join(validation["errors"])
            raise ValueError(f"artifact-invalid:{spec.logical_id}:{rendered}")
        staged[spec.logical_id] = target
    return staged


def _package_gate_errors(
    model: Mapping[str, Any],
    specs: tuple[ArtifactSpec, ...],
    staged: Mapping[str, Path],
    session: Path,
) -> tuple[str, ...]:
    errors = list(_minimum_package_errors_from_specs(specs, model))
    errors.extend(_global_term_errors(model, [path.read_text(encoding="utf-8") for path in staged.values()]))
    allowed_sources = _authorized_sources(session, model)
    for spec in specs:
        for source_ref in spec.source_refs:
            if source_ref not in allowed_sources:
                errors.append(f"source-reference-unauthorized:{source_ref}")
    return tuple(errors)


def _minimum_package_errors_from_specs(
    specs: Iterable[ArtifactSpec], model: Mapping[str, Any]
) -> tuple[str, ...]:
    items = tuple(specs)
    errors: list[str] = []
    if not any(item.artifact_type == "hub" and item.relative_path == "index.html" for item in items):
        errors.append("minimum-hub-missing")
    decks = _deck_definitions(model, tuple(model["sections"]))
    deck_items = [item for item in items if item.artifact_type == "deck"]
    if not deck_items:
        errors.append("minimum-main-deck-missing")
    # The ledger retains superseded deck/slide history, so validation requires
    # the current minimum without treating retained versions as duplicates.
    if len(deck_items) < len(decks):
        errors.append("minimum-declared-deck-missing")
    expected_slides = sum(len(deck["sectionIds"]) for deck in decks)
    slide_items = [item for item in items if item.artifact_type == "slide"]
    if len(slide_items) < expected_slides:
        errors.append("minimum-deck-slide-missing")
    if not any(item.profile == "technical-visual" for item in items):
        errors.append("minimum-technical-visual-missing")
    return tuple(errors)


def _minimum_package_errors(records: Iterable[LedgerRecord], model: Mapping[str, Any]) -> tuple[str, ...]:
    record_specs = tuple(
        ArtifactSpec(
            logical_id=record.logical_id,
            title=record.title,
            artifact_type=record.artifact_type,
            profile=record.profile,
            relative_path=record.relative_path,
            html="",
            source_refs=record.source_refs,
            required_terms=(),
            mutable_index=record.artifact_type in {"hub", "deck"},
        )
        for record in records
    )
    return _minimum_package_errors_from_specs(record_specs, model)


def _global_term_errors(model: Mapping[str, Any], texts: Iterable[str]) -> tuple[str, ...]:
    union = "\n".join(texts)
    return tuple(
        f"global-required-term-missing:{term}"
        for term in model["requiredTerms"]
        if term not in union
    )


def _authorized_sources(session: Path, model: Mapping[str, Any]) -> frozenset[str]:
    model_sources = {
        source
        for section in model["sections"]
        for source in section.get("sourceRefs", ())
        if isinstance(source, str)
    }
    return frozenset(model_sources | set(_lesson_sources(session / "lesson.md")))


def _lesson_sources(lesson_path: Path) -> tuple[str, ...]:
    """Read simple ``sources:`` frontmatter lists without a YAML dependency."""
    if not lesson_path.is_file():
        return ()
    lines = lesson_path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("sources:") + 1
    except ValueError:
        return ()
    sources: list[str] = []
    for line in lines[start:]:
        if line == "---" or (line and not line.startswith((" ", "-"))):
            break
        match = re.match(r"\s*-\s*(.+)$", line)
        if match:
            sources.append(match.group(1).strip().strip('"'))
    return tuple(sources)


def _promote_artifacts(
    session: Path,
    lessons_root: Path,
    specs: tuple[ArtifactSpec, ...],
    staged: Mapping[str, Path],
    existing: tuple[LedgerRecord, ...],
) -> tuple[LedgerRecord, ...]:
    records = list(existing)
    timestamp = _deterministic_timestamp()
    for spec in specs:
        raw = staged[spec.logical_id].read_bytes()
        digest = _sha256(raw)
        matches = [record for record in records if record.logical_id == spec.logical_id]
        same = next((record for record in matches if record.sha256 == digest), None)
        if same is not None:
            continue
        if spec.mutable_index:
            current = max(matches, key=lambda record: record.version, default=None)
            target = assert_within(session / spec.relative_path, lessons_root)
            _atomic_write_bytes(target, raw, lessons_root)
            replacement = _new_record(
                spec,
                artifact_id=current.artifact_id if current else spec.logical_id,
                relative_path=spec.relative_path,
                version=current.version if current else 1,
                digest=digest,
                created_at=current.created_at if current else timestamp,
                supersedes=current.supersedes if current else "",
                updated_at=timestamp,
            )
            if current is None:
                records.append(replacement)
            else:
                records[records.index(current)] = replacement
            continue

        next_version = max((record.version for record in matches), default=0) + 1
        while True:
            artifact_id = spec.logical_id if next_version == 1 else f"{spec.logical_id}-v{next_version}"
            relative_path = _versioned_path(spec.relative_path, next_version)
            target = assert_within(session / relative_path, lessons_root)
            try:
                _write_new_bytes(target, raw, lessons_root)
                break
            except FileExistsError:
                next_version += 1
        previous = max(matches, key=lambda record: record.version, default=None)
        records.append(
            _new_record(
                spec,
                artifact_id=artifact_id,
                relative_path=relative_path,
                version=next_version,
                digest=digest,
                created_at=timestamp,
                supersedes=previous.artifact_id if previous else "",
                updated_at=timestamp,
            )
        )
    return tuple(records)


def _new_record(
    spec: ArtifactSpec,
    artifact_id: str,
    relative_path: str,
    version: int,
    digest: str,
    created_at: str,
    supersedes: str,
    updated_at: str,
) -> LedgerRecord:
    return LedgerRecord(
        artifact_id=artifact_id,
        logical_id=spec.logical_id,
        relative_path=relative_path,
        artifact_type=spec.artifact_type,
        title=spec.title,
        profile=spec.profile,
        source_turn="lesson-model.json",
        source_refs=spec.source_refs,
        version=version,
        status="visual verification pending",
        sha256=digest,
        created_at=created_at,
        updated_at=updated_at,
        supersedes=supersedes,
    )


def _versioned_path(relative_path: str, version: int) -> str:
    if version == 1:
        return relative_path
    path = Path(relative_path)
    return str(path.with_name(f"{path.stem}-v{version}{path.suffix}")).replace("\\", "/")


def _write_lifecycle_status(
    session: Path, lessons_root: Path, model: Mapping[str, Any], status: str
) -> None:
    mutable_model = copy.deepcopy(model)
    mutable_model["session"]["status"] = status
    atomic_write_json(assert_within(session / "lesson-model.json", lessons_root), mutable_model, lessons_root)
    set_lesson_frontmatter_status(assert_within(session / "lesson.md", lessons_root), status, lessons_root)


def _read_ledger(path: Path) -> tuple[tuple[LedgerRecord, ...], tuple[str, ...]]:
    if not path.is_file():
        return (), ("artifact-ledger-missing",)
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- id: "):
            if current is not None:
                blocks.append(current)
            current = {"id": line.removeprefix("- id: ")}
        elif current is not None and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            current[key] = value.lstrip()
    if current is not None:
        blocks.append(current)
    errors: list[str] = []
    records: list[LedgerRecord] = []
    for index, block in enumerate(blocks):
        missing = [field for field in LEDGER_FIELDS if field not in block]
        if missing:
            errors.append(f"artifact-ledger-fields-missing:{index}:{','.join(missing)}")
            continue
        try:
            records.append(
                LedgerRecord(
                    artifact_id=block["id"],
                    logical_id=block["logicalId"],
                    relative_path=block["path"],
                    artifact_type=block["type"],
                    title=block["title"],
                    profile=block["profile"],
                    source_turn=block["sourceTurn"],
                    source_refs=tuple(
                        item for item in block["sourceRefs"].split(" | ") if item
                    ),
                    version=int(block["version"]),
                    status=block["status"],
                    sha256=block["sha256"],
                    created_at=block["createdAt"],
                    updated_at=block["updatedAt"],
                    supersedes=block["supersedes"],
                )
            )
        except ValueError:
            errors.append(f"artifact-ledger-invalid:{index}")
    return tuple(records), tuple(errors)


def _serialize_ledger(records: Iterable[LedgerRecord]) -> str:
    lines = ["# Lesson artifact ledger", ""]
    for record in records:
        values = {
            "id": record.artifact_id,
            "logicalId": record.logical_id,
            "path": record.relative_path,
            "type": record.artifact_type,
            "title": record.title,
            "profile": record.profile,
            "sourceTurn": record.source_turn,
            "sourceRefs": " | ".join(record.source_refs),
            "version": str(record.version),
            "status": record.status,
            "sha256": record.sha256,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
            "supersedes": record.supersedes,
        }
        lines.append(f"- id: {values['id']}")
        lines.extend(f"  {field}: {values[field]}" for field in LEDGER_FIELDS if field != "id")
        lines.append("")
    return "\n".join(lines)


def _deterministic_timestamp() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        return "1970-01-01T00:00:00Z"
    try:
        value = int(epoch)
    except ValueError as exc:
        raise ValueError("SOURCE_DATE_EPOCH must be an integer") from exc
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def _unique_sources(sources: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(source for source in sources if isinstance(source, str)))


def _write_new_bytes(path: Path, raw: bytes, lessons_root: Path) -> None:
    target = assert_within(path, lessons_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    assert_within(target.parent, lessons_root)
    with target.open("xb") as output:
        output.write(raw)


def _atomic_write_bytes(path: Path, raw: bytes, lessons_root: Path) -> None:
    target = assert_within(path, lessons_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    assert_within(target.parent, lessons_root)
    handle, temporary_name = tempfile.mkstemp(prefix=".lesson-write-", dir=target.parent)
    temporary = assert_within(Path(temporary_name), lessons_root)
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(raw)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_text(path: Path, text: str, lessons_root: Path) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"), lessons_root)


def _lesson_status(session: Path) -> str:
    lesson = session / "lesson.md"
    if not lesson.is_file():
        return "preparing"
    match = re.search(r"(?m)^status: (.+)$", lesson.read_text(encoding="utf-8"))
    return match.group(1).strip() if match else "preparing"


def _failed(status: str, *errors: str) -> PackageReport:
    return PackageReport("failed", status, tuple(errors))


def _report(
    overall: str,
    status: str,
    errors: Iterable[str],
    records: Iterable[LedgerRecord],
    model: Mapping[str, Any],
) -> PackageReport:
    return PackageReport(
        overall,
        status,
        tuple(dict.fromkeys(errors)),
        tuple(record.summary() for record in records),
        str(model["session"]["topic"]),
    )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _configure_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    except (AttributeError, OSError):
        pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage offline learning-companion lesson packages.")
    commands = parser.add_subparsers(dest="command", required=True)
    allocate = commands.add_parser("allocate")
    allocate.add_argument("plan_dir", type=Path)
    allocate.add_argument("--day", required=True, type=int)
    allocate.add_argument("--topic", required=True)
    allocate.add_argument("--mode", required=True, choices=sorted(SESSION_MODES))
    allocate.add_argument("--depth", required=True, choices=sorted(SESSION_DEPTHS))
    allocate.add_argument("--date", required=True, type=_parse_date)
    for command in ("prepare", "sync", "validate", "close"):
        child = commands.add_parser(command)
        child.add_argument("session_dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdout()
    args = _parser().parse_args(argv)
    try:
        if args.command == "allocate":
            session = allocate_session(
                args.plan_dir, args.day, args.topic, args.mode, args.depth, args.date
            )
            report = PackageReport("passed", "preparing", (), (), args.topic)
            payload = report.to_dict() | {"sessionDir": str(session)}
        else:
            operation = {
                "prepare": prepare_session,
                "sync": sync_session,
                "validate": validate_session,
                "close": close_session,
            }[args.command]
            report = operation(args.session_dir)
            payload = report.to_dict()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = PackageReport("failed", "preparing", (str(exc),)).to_dict()
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if payload["overall"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
