#!/usr/bin/env python3
"""Audit whether final transition polish can survive into Resolve markers and readback."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TRANSITION_MARKER_ROLES = {"transition_polish_candidate_marker", "transition_execution_candidate_marker"}
TRANSITION_CLIP_KEYS = ("transitionPolishOut", "transitionPolishIn", "transitionExecutionOut", "transitionExecutionIn")
VISIBLE_EFFECT_TERMS = ("dissolve", "blur", "push", "slide", "rotation", "speed", "ramp", "transform", "whip")


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in ("role", "purpose", "titleText", "subtitle", "sourcePath", "sourceName", "name")
    ).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt")):
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type not in {"", "video"}:
        return False
    return as_int(clip.get("mediaType"), 1) == 1


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    video = [row for row in rows if isinstance(row, dict) and is_video_clip(row)]
    return sorted(video, key=lambda item: (timeline_start(item), timeline_end(item), str(item.get("sourcePath") or "")))


def visual_boundaries(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(clips, clips[1:]), start=1):
        boundary = max(timeline_end(left), timeline_start(right))
        out.append(
            {
                "boundaryIndex": index,
                "boundarySeconds": round3(boundary),
                "fromSourceName": source_name(left.get("sourcePath") or left.get("sourceName")),
                "toSourceName": source_name(right.get("sourcePath") or right.get("sourceName")),
            }
        )
    return out


def resolve_path(package_dir: Path, raw: Any) -> Path:
    path = Path(str(raw or "")).expanduser()
    if not path.is_absolute():
        path = (package_dir / path).resolve()
    return path


def choose_blueprint(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path, str, bool]:
    if explicit:
        path = resolve_path(package_dir, explicit)
        return load_json(path), path, "explicit_blueprint", is_inside(path, package_dir)
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint", is_inside(active, package_dir)


def transition_candidate(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("transitionPolishCandidate")
    return nested if isinstance(nested, dict) else row


def selected_recipe(row: dict[str, Any]) -> dict[str, Any]:
    candidate = transition_candidate(row)
    recipe = candidate.get("selectedRecipe") if isinstance(candidate.get("selectedRecipe"), dict) else {}
    return recipe


def row_index(row: dict[str, Any]) -> int:
    candidate = transition_candidate(row)
    return as_int(candidate.get("rowIndex") if candidate.get("rowIndex") is not None else row.get("rowIndex"), -1)


def transition_candidates(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = blueprint.get("transitionPolishCandidates") if isinstance(blueprint.get("transitionPolishCandidates"), list) else []
    out = [row for row in candidates if isinstance(row, dict)]
    if out:
        return out
    transitions = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    return [row for row in transitions if isinstance(row, dict) and isinstance(row.get("transitionPolishCandidate"), dict)]


def parse_json_string(value: Any) -> Any | None:
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except Exception:
            return None
    return None


def marker_payload(marker: dict[str, Any]) -> dict[str, Any]:
    payload = marker.get("payload") if isinstance(marker.get("payload"), dict) else {}
    custom = marker.get("customData")
    if isinstance(custom, str):
        parsed = parse_json_string(custom)
        custom = parsed if isinstance(parsed, dict) else {}
    if isinstance(custom, dict):
        nested = custom.get("payload") if isinstance(custom.get("payload"), dict) else {}
        merged = {**custom, **nested, **payload}
        if payload:
            merged["payload"] = payload
        return merged
    return dict(payload)


def transition_markers(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    markers = blueprint.get("timelineMarkers") if isinstance(blueprint.get("timelineMarkers"), list) else []
    out: list[dict[str, Any]] = []
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        role = str(marker.get("role") or marker_payload(marker).get("role") or "")
        name = str(marker.get("name") or "")
        if role in TRANSITION_MARKER_ROLES or "transition polish" in name.lower() or "transition execution" in name.lower():
            out.append(marker)
    return out


def markers_by_row(markers: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for marker in markers:
        payload = marker_payload(marker)
        index = as_int(payload.get("rowIndex"), -1)
        if index >= 0:
            out.setdefault(index, []).append(marker)
    return out


def clip_annotation_rows(blueprint: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for clip in blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []:
        if not isinstance(clip, dict):
            continue
        for key in TRANSITION_CLIP_KEYS:
            rows = clip.get(key) if isinstance(clip.get(key), list) else []
            for row in rows:
                if isinstance(row, dict):
                    index = as_int(row.get("rowIndex"), -1)
                    if index >= 0:
                        out.add(index)
    return out


def visible_effect(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    recipe = selected_recipe(row)
    text = " ".join(
        str(value or "")
        for value in (
            recipe.get("recipeId"),
            recipe.get("resolveEffectName"),
            candidate.get("sourceTransitionType"),
            candidate.get("sourceResolveEffectName"),
        )
    ).lower()
    if "clean_cut" in text or "cut" == str(recipe.get("resolveEffectName") or "").strip().lower():
        return False
    return any(term in text for term in VISIBLE_EFFECT_TERMS)


def recipe_ready(row: dict[str, Any]) -> bool:
    recipe = selected_recipe(row)
    keyframes = recipe.get("keyframePlan") if isinstance(recipe.get("keyframePlan"), list) else []
    duration = as_float(recipe.get("durationSeconds"), 0.0) or 0.0
    return bool(recipe.get("recipeId") and recipe.get("resolveEffectName") and duration > 0 and keyframes)


def build_timeline_preserves_marker_payload(skill_dir: Path) -> bool:
    script = skill_dir / "scripts" / "build_resolve_timeline.py"
    text = script.read_text(encoding="utf-8", errors="ignore") if script.exists() else ""
    return "item.get(\"payload\")" in text and "custom_payload.setdefault(\"payload\"" in text


def resolve_audit_path(package_dir: Path, explicit: str | None = None) -> Path:
    return resolve_path(package_dir, explicit) if explicit else package_dir / "resolve_audit.json"


def normalize_resolve_markers(markers: Any) -> list[dict[str, Any]]:
    if isinstance(markers, dict):
        values = markers.values()
    elif isinstance(markers, list):
        values = markers
    else:
        values = []
    return [value for value in values if isinstance(value, dict)]


def resolve_marker_payloads(resolve_audit: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for marker in normalize_resolve_markers(resolve_audit.get("markers")):
        direct = marker_payload(marker)
        if direct:
            out.append(direct)
            continue
        for value in marker.values():
            parsed = parse_json_string(value)
            if isinstance(parsed, dict):
                nested = parsed.get("payload") if isinstance(parsed.get("payload"), dict) else {}
                out.append({**parsed, **nested})
                break
    return out


def resolve_rows_with_payload(resolve_audit: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for payload in resolve_marker_payloads(resolve_audit):
        index = as_int(payload.get("rowIndex"), -1)
        if index >= 0:
            out.add(index)
    return out


def audited_candidate(row: dict[str, Any], marker_lookup: dict[int, list[dict[str, Any]]], clip_rows: set[int], resolve_rows: set[int] | None) -> dict[str, Any]:
    candidate = transition_candidate(row)
    recipe = selected_recipe(row)
    index = row_index(row)
    markers = marker_lookup.get(index) or []
    payloads = [marker_payload(marker) for marker in markers]
    marker_payload_ready = any(as_int(payload.get("rowIndex"), -1) == index and (payload.get("recipeId") or payload.get("resolveEffectName")) for payload in payloads)
    issues: list[str] = []
    if index < 0:
        issues.append("missing_transition_row_index")
    if not recipe_ready(row):
        issues.append("missing_selected_recipe_keyframes_or_duration")
    if not isinstance(candidate.get("transitionMotivation"), dict):
        issues.append("missing_transition_motivation")
    if not markers:
        issues.append("missing_transition_marker")
    if markers and not marker_payload_ready:
        issues.append("transition_marker_missing_row_or_recipe_payload")
    if index not in clip_rows:
        issues.append("missing_clip_transition_annotation")
    if visible_effect(row) and not recipe.get("keyframePlan"):
        issues.append("visible_transition_effect_missing_keyframes")
    if resolve_rows is not None and index not in resolve_rows:
        issues.append("resolve_readback_missing_transition_marker_payload")
    return {
        "rowIndex": index,
        "status": "passed" if not issues else "blocked",
        "boundarySeconds": round3(as_float(candidate.get("boundarySeconds"), 0.0) or 0.0),
        "fromSourceName": source_name(candidate.get("fromSourcePath")),
        "toSourceName": source_name(candidate.get("toSourcePath")),
        "recipeId": recipe.get("recipeId"),
        "resolveEffectName": recipe.get("resolveEffectName"),
        "durationSeconds": recipe.get("durationSeconds"),
        "visibleEffect": visible_effect(row),
        "markerCount": len(markers),
        "markerPayloadReady": marker_payload_ready,
        "clipAnnotationPresent": index in clip_rows,
        "resolveReadbackPayloadPresent": None if resolve_rows is None else index in resolve_rows,
        "issues": issues,
    }


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve() if args.skill_dir else Path(__file__).resolve().parents[1]
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, args.blueprint)
    resolve_path_arg = resolve_audit_path(package_dir, args.resolve_audit)
    resolve_audit = load_json(resolve_path_arg) or {}
    resolve_available = bool(resolve_path_arg.exists() and isinstance(resolve_audit, dict))
    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "blueprint": str(blueprint_path),
                "blueprintExists": blueprint_path.exists(),
                "blueprintKind": blueprint_kind,
                "blueprintInsidePackage": blueprint_inside_package,
                "resolveAudit": str(resolve_path_arg),
                "resolveAuditExists": resolve_path_arg.exists(),
            },
            "summary": {},
            "transitionRows": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    candidates = transition_candidates(blueprint)
    markers = transition_markers(blueprint)
    marker_lookup = markers_by_row(markers)
    clip_rows = clip_annotation_rows(blueprint)
    resolve_rows = resolve_rows_with_payload(resolve_audit) if resolve_available else None
    audited = [audited_candidate(row, marker_lookup, clip_rows, resolve_rows) for row in candidates]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    blockers = [f"transition row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked[:80]]
    warnings: list[str] = []
    clips = primary_visual_clips(blueprint)
    boundaries = visual_boundaries(clips)
    adapter_ready = build_timeline_preserves_marker_payload(skill_dir)
    if not blueprint_path.exists():
        blockers.append(f"blueprint path does not exist: {blueprint_path}")
    if not blueprint_inside_package:
        blockers.append(f"blueprint is outside package: {blueprint_path}")
    if boundaries and not candidates:
        blockers.append("visual boundaries exist but final blueprint has no transitionPolishCandidates")
    if candidates and len(markers) < len(candidates):
        blockers.append(f"not every transition candidate has a timeline marker: {len(markers)}/{len(candidates)}")
    if candidates and len(clip_rows) < len({row_index(row) for row in candidates if row_index(row) >= 0}):
        blockers.append("not every transition candidate has clip in/out annotations")
    if candidates and not adapter_ready:
        blockers.append("build_resolve_timeline.py does not preserve marker payload into Resolve customData")
    if resolve_available and candidates and len(resolve_rows or set()) < len({row_index(row) for row in candidates if row_index(row) >= 0}):
        blockers.append(f"Resolve readback transition marker payload coverage is incomplete: {len(resolve_rows or set())}/{len(candidates)}")
    if not resolve_available:
        warnings.append("resolve_audit.json is missing; marker payload readiness was checked in the blueprint and build adapter only")
    status = "passed" if not blockers and bool(candidates) else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "skillDir": str(skill_dir),
            "buildResolveTimelinePreservesMarkerPayload": adapter_ready,
            "resolveAudit": str(resolve_path_arg),
            "resolveAuditExists": resolve_path_arg.exists(),
            "resolveReadbackChecked": resolve_available,
        },
        "summary": {
            "visualClipCount": len(clips),
            "visualBoundaryCount": len(boundaries),
            "transitionCandidateCount": len(candidates),
            "transitionMarkerCount": len(markers),
            "transitionRowsWithMarkerPayload": sum(1 for row in audited if row.get("markerPayloadReady")),
            "transitionRowsWithClipAnnotation": sum(1 for row in audited if row.get("clipAnnotationPresent")),
            "visibleEffectRowCount": sum(1 for row in audited if row.get("visibleEffect")),
            "resolveRowsWithPayload": len(resolve_rows or set()),
            "blockedTransitionRowCount": len(blocked),
            "blockerCount": len(blockers),
        },
        "transitionRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Resolve Transition Materialization Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report['inputs'].get('blueprint')}`",
        f"Resolve readback checked: `{report['inputs'].get('resolveReadbackChecked')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Blocked Transition Rows"])
    blocked = [row for row in report.get("transitionRows") or [] if row.get("status") == "blocked"]
    if not blocked:
        lines.append("- None.")
    for row in blocked[:120]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('recipeId')}",
                f"- Boundary: `{row.get('boundarySeconds')}`",
                f"- Effect: `{row.get('resolveEffectName')}`",
                f"- Marker payload ready: `{row.get('markerPayloadReady')}`",
                f"- Clip annotation present: `{row.get('clipAnnotationPresent')}`",
                f"- Resolve readback payload present: `{row.get('resolveReadbackPayloadPresent')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final transition materialization for Resolve marker payload/readback.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--resolve-audit")
    parser.add_argument("--skill-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "resolve_transition_materialization_contract_audit.json", report)
    write_markdown(package_dir / "resolve_transition_materialization_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
