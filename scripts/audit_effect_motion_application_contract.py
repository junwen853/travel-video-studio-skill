#!/usr/bin/env python3
"""Audit whether effect-motion candidates survive into the final blueprint."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint",
    "approvedEffectRows",
    "resolveImplementation",
    "preflightEvidence",
    "timelineReadbackEvidence",
    "frameSampleEvidence",
    "approvedBy",
    "approvedAt",
    "editorNotes",
}
MOTION_TERMS = ("whip", "rotation", "speed", "ramp", "push", "slide")
ALLOWED_INTENSITIES = {"subtle", "low", "restrained"}


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def resolve_path(package_dir: Path, raw: Any) -> Path:
    path = Path(str(raw or "")).expanduser()
    if not path.is_absolute():
        path = (package_dir / path).resolve()
    return path


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


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
    return " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "sourcePath", "sourceName", "name")).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt")):
        return False
    return str(clip.get("trackType") or "video").lower() in {"", "video"} and as_int(clip.get("mediaType"), 1) == 1


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return sorted([row for row in rows if isinstance(row, dict) and is_video_clip(row)], key=lambda item: (timeline_start(item), timeline_end(item)))


def effect_rows_from_report(report: dict[str, Any], source_candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("materializedRows") if isinstance(report.get("materializedRows"), list) else []
    out = [row for row in rows if isinstance(row, dict)]
    if out:
        return out
    candidates = source_candidate.get("effectMotionCandidates") if isinstance(source_candidate.get("effectMotionCandidates"), list) else []
    return [row for row in candidates if isinstance(row, dict)]


def effect_candidates(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("effectMotionCandidates") if isinstance(blueprint.get("effectMotionCandidates"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def clip_annotation_map(blueprint: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    for clip in clips:
        if not isinstance(clip, dict):
            continue
        annotations = clip.get("effectMotionCandidates") if isinstance(clip.get("effectMotionCandidates"), list) else []
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            index = as_int(annotation.get("rowIndex"), -1)
            if index >= 0:
                out.setdefault(index, []).append(annotation)
    return out


def marker_rows(blueprint: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    markers = blueprint.get("timelineMarkers") if isinstance(blueprint.get("timelineMarkers"), list) else []
    for marker in markers:
        if not isinstance(marker, dict) or marker.get("role") != "effect_motion_candidate_marker":
            continue
        payload = marker.get("payload") if isinstance(marker.get("payload"), dict) else {}
        index = as_int(payload.get("rowIndex"), -1)
        if index >= 0:
            out.add(index)
    return out


def effect_index(row: dict[str, Any]) -> int:
    return as_int(row.get("rowIndex"), -1)


def row_type(row: dict[str, Any]) -> str:
    return str(row.get("rowType") or "")


def effect_style(row: dict[str, Any]) -> str:
    return str(row.get("effectStyle") or row.get("selectedEffectType") or "")


def is_motion_effect(row: dict[str, Any]) -> bool:
    text = f"{row_type(row)} {effect_style(row)}".lower()
    return any(term in text for term in MOTION_TERMS)


def is_title_effect(row: dict[str, Any]) -> bool:
    return "title" in row_type(row).lower()


def decision_fields_ready(row: dict[str, Any]) -> bool:
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    return DECISION_FIELDS.issubset(set(decision))


def final_row_lookup(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        index = effect_index(row)
        if index >= 0 and index not in out:
            out[index] = row
    return out


def match_final_row(expected: dict[str, Any], final_rows: dict[int, dict[str, Any]], annotations: dict[int, list[dict[str, Any]]]) -> dict[str, Any] | None:
    index = effect_index(expected)
    if index in final_rows:
        return final_rows[index]
    annotated = annotations.get(index) or []
    return annotated[0] if annotated else None


def max_duration_frames(row: dict[str, Any]) -> int:
    return 48 if is_title_effect(row) else 30


def audited_row(expected: dict[str, Any], matched: dict[str, Any] | None, annotations: dict[int, list[dict[str, Any]]], markers: set[int]) -> dict[str, Any]:
    index = effect_index(expected)
    issues: list[str] = []
    if not matched:
        return {
            "rowIndex": index,
            "status": "blocked",
            "rowType": row_type(expected),
            "effectStyle": effect_style(expected),
            "issues": ["effect_motion_row_missing_from_final_blueprint"],
        }

    if expected.get("status") not in {"materialized", "ready", "passed", "effect_motion_candidate"}:
        issues.append("source_effect_motion_row_not_materialized")
    if matched.get("status") not in {"materialized", "ready", "passed", "effect_motion_candidate"}:
        issues.append("final_effect_motion_row_not_materialized")
    if effect_style(expected) and effect_style(matched) and effect_style(expected) != effect_style(matched):
        issues.append("final_effect_style_changed_or_missing")
    duration = as_int(matched.get("durationFrames"), 0)
    if duration <= 0 or duration > max_duration_frames(matched):
        issues.append("final_effect_duration_missing_or_too_long")
    if str(matched.get("intensity") or "").lower() not in ALLOWED_INTENSITIES:
        issues.append("final_effect_intensity_not_restrained")
    if matched.get("audioTreatment") != "bgm_only_no_camera_voice":
        issues.append("final_effect_missing_bgm_only_no_voice_policy")
    if matched.get("titleZoneSafe") is not True:
        issues.append("final_effect_not_title_zone_safe")
    if matched.get("sourceEvidenceSatisfied") is not True:
        issues.append("final_effect_lacks_source_evidence")
    if matched.get("motionEvidenceSatisfied") is not True:
        issues.append("final_effect_lacks_motion_evidence")
    if matched.get("forbiddenEffectHits"):
        issues.append("final_effect_contains_forbidden_style")
    if not decision_fields_ready(matched):
        issues.append("final_effect_missing_resolve_decision_fields")
    if index not in annotations:
        issues.append("final_clip_effect_motion_annotation_missing")
    if index not in markers:
        issues.append("final_effect_motion_marker_missing")

    return {
        "rowIndex": index,
        "status": "passed" if not issues else "blocked",
        "rowType": row_type(matched),
        "effectStyle": effect_style(matched),
        "durationFrames": duration,
        "maxDurationFrames": max_duration_frames(matched),
        "intensity": matched.get("intensity"),
        "motionEffect": is_motion_effect(matched),
        "titleEffect": is_title_effect(matched),
        "bgmOnlyAudio": matched.get("audioTreatment") == "bgm_only_no_camera_voice",
        "titleZoneSafe": matched.get("titleZoneSafe") is True,
        "sourceEvidenceSatisfied": matched.get("sourceEvidenceSatisfied") is True,
        "motionEvidenceSatisfied": matched.get("motionEvidenceSatisfied") is True,
        "decisionFieldsReady": decision_fields_ready(matched),
        "clipAnnotationPresent": index in annotations,
        "markerPresent": index in markers,
        "forbiddenEffectHits": matched.get("forbiddenEffectHits") or [],
        "issues": issues,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    report_path = package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json"
    effect_report = load_json(report_path) or {}
    outputs = effect_report.get("outputs") if isinstance(effect_report.get("outputs"), dict) else {}
    source_candidate_raw = outputs.get("candidateBlueprint") or package_dir / "effect_motion_blueprint" / "resolve_timeline_blueprint_effect_motion.json"
    source_candidate_path = resolve_path(package_dir, source_candidate_raw)
    source_candidate = load_json(source_candidate_path) or {}
    final_path = resolve_path(package_dir, args.blueprint) if args.blueprint else package_dir / "resolve_timeline_blueprint.json"
    final = load_json(final_path)
    lineage_path = package_dir / "final_blueprint_lineage_contract_audit.json"
    lineage = load_json(lineage_path) or {}

    if not isinstance(final, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "effectMotionReport": str(report_path),
                "effectMotionReportExists": report_path.exists(),
                "effectMotionStatus": effect_report.get("status"),
                "sourceCandidateBlueprint": str(source_candidate_path),
                "sourceCandidateExists": source_candidate_path.exists(),
                "finalBlueprint": str(final_path),
                "finalBlueprintExists": final_path.exists(),
                "finalBlueprintInsidePackage": is_inside(final_path, package_dir),
                "finalBlueprintLineageAudit": str(lineage_path),
                "finalBlueprintLineageStatus": lineage.get("status"),
            },
            "summary": {},
            "effectRows": [],
            "blockers": [f"missing or unreadable final blueprint: {final_path}"],
            "warnings": [],
            "safety": safety(),
        }

    expected_rows = effect_rows_from_report(effect_report, source_candidate if isinstance(source_candidate, dict) else {})
    final_candidates = effect_candidates(final)
    final_lookup = final_row_lookup(final_candidates)
    annotations = clip_annotation_map(final)
    markers = marker_rows(final)
    audited = [audited_row(row, match_final_row(row, final_lookup, annotations), annotations, markers) for row in expected_rows]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    visual_boundary_count = max(0, len(primary_visual_clips(final)) - 1)
    motion_count = sum(1 for row in audited if row.get("motionEffect") is True)
    max_motion_allowed = max(2, math.ceil(visual_boundary_count * args.max_motion_share)) if visual_boundary_count else max(2, motion_count)
    final_plan = final.get("effectMotionBlueprintPlan") if isinstance(final.get("effectMotionBlueprintPlan"), dict) else {}

    blockers = [f"effect motion row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked[:80]]
    warnings: list[str] = []
    if effect_report.get("status") != "ready_with_effect_motion_blueprint":
        blockers.append(f"effect_motion_blueprint_report status is not ready: {effect_report.get('status')}")
    if not report_path.exists():
        blockers.append("effect_motion_blueprint_report.json is missing")
    if not source_candidate_path.exists():
        blockers.append(f"source effect-motion candidate missing: {source_candidate_path}")
    if not is_inside(source_candidate_path, package_dir):
        blockers.append(f"source effect-motion candidate is outside package: {source_candidate_path}")
    if not is_inside(final_path, package_dir):
        blockers.append(f"final blueprint is outside package: {final_path}")
    if not expected_rows:
        blockers.append("effect-motion report has no materialized rows to apply")
    if not final_plan:
        blockers.append("final blueprint is missing effectMotionBlueprintPlan")
    if final_plan.get("candidateBlueprint") and source_name(final_plan.get("candidateBlueprint")) != source_name(source_candidate_path):
        warnings.append("final effectMotionBlueprintPlan candidate path name differs from source candidate")
    if final_candidates and len(final_candidates) < len(expected_rows):
        blockers.append(f"final blueprint dropped effectMotionCandidates: {len(final_candidates)}/{len(expected_rows)}")
    if motion_count > max_motion_allowed:
        blockers.append(f"motion effects are overused: {motion_count}/{max_motion_allowed} allowed for {visual_boundary_count} visual boundaries")
    if lineage.get("status") != "passed":
        blockers.append(f"final_blueprint_lineage_contract_audit is not passed: {lineage.get('status')}")

    status = "passed" if not blockers and bool(expected_rows) else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "effectMotionReport": str(report_path),
            "effectMotionReportExists": report_path.exists(),
            "effectMotionStatus": effect_report.get("status"),
            "sourceCandidateBlueprint": str(source_candidate_path),
            "sourceCandidateExists": source_candidate_path.exists(),
            "sourceCandidateInsidePackage": is_inside(source_candidate_path, package_dir),
            "finalBlueprint": str(final_path),
            "finalBlueprintExists": final_path.exists(),
            "finalBlueprintKind": "explicit_blueprint" if args.blueprint else "active_blueprint",
            "finalBlueprintInsidePackage": is_inside(final_path, package_dir),
            "finalHasEffectMotionBlueprintPlan": bool(final_plan),
            "finalBlueprintLineageAudit": str(lineage_path),
            "finalBlueprintLineageStatus": lineage.get("status"),
        },
        "summary": {
            "sourceEffectRowCount": len(expected_rows),
            "finalEffectMotionCandidateCount": len(final_candidates),
            "finalVisualBoundaryCount": visual_boundary_count,
            "maxMotionAllowed": max_motion_allowed,
            "auditedEffectRowCount": len(audited),
            "passedEffectRowCount": sum(1 for row in audited if row.get("status") == "passed"),
            "blockedEffectRowCount": len(blocked),
            "motionEffectRowCount": motion_count,
            "titleEffectRowCount": sum(1 for row in audited if row.get("titleEffect") is True),
            "bgmOnlyRowCount": sum(1 for row in audited if row.get("bgmOnlyAudio") is True),
            "titleSafeRowCount": sum(1 for row in audited if row.get("titleZoneSafe") is True),
            "sourceEvidenceRowCount": sum(1 for row in audited if row.get("sourceEvidenceSatisfied") is True),
            "motionEvidenceRowCount": sum(1 for row in audited if row.get("motionEvidenceSatisfied") is True),
            "decisionFieldsRowCount": sum(1 for row in audited if row.get("decisionFieldsReady") is True),
            "clipAnnotationRowCount": sum(1 for row in audited if row.get("clipAnnotationPresent") is True),
            "markerRowCount": sum(1 for row in audited if row.get("markerPresent") is True),
            "forbiddenEffectHitCount": sum(len(row.get("forbiddenEffectHits") or []) for row in audited),
            "blockerCount": len(blockers),
        },
        "effectRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Effect Motion Application Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Final blueprint: `{report['inputs'].get('finalBlueprint')}`",
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
    lines.extend(["", "## Effect Rows"])
    for row in report.get("effectRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('rowType')}",
                f"- Status: `{row.get('status')}`",
                f"- Style: `{row.get('effectStyle')}`",
                f"- Duration frames: `{row.get('durationFrames')}`",
                f"- Ready: BGM `{row.get('bgmOnlyAudio')}`, title `{row.get('titleZoneSafe')}`, motion `{row.get('motionEvidenceSatisfied')}`, marker `{row.get('markerPresent')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether effect-motion rows survive into the final Resolve blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--max-motion-share", type=float, default=0.18, help="Maximum share of visual boundaries that may use motion effects. Default: 0.18.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "effect_motion_application_contract_audit.json", report)
    write_markdown(package_dir / "effect_motion_application_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
