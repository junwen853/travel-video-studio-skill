#!/usr/bin/env python3
"""Audit whether transition-polish metadata survives into the final blueprint."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint",
    "approvedPolishRows",
    "resolveImplementation",
    "preflightEvidence",
    "timelineReadbackEvidence",
    "frameSampleEvidence",
    "approvedBy",
    "approvedAt",
}
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide"}


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


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


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
    return " ".join(
        str(clip.get(key) or "")
        for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath", "sourceName", "name", "notes")
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
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(clips, clips[1:]), start=1):
        rows.append(
            {
                "boundaryIndex": index,
                "boundarySeconds": round3(timeline_end(left)),
                "fromSourceName": source_name(left.get("sourcePath") or left.get("sourceName")),
                "toSourceName": source_name(right.get("sourcePath") or right.get("sourceName")),
            }
        )
    return rows


def transition_candidate(row: dict[str, Any]) -> dict[str, Any]:
    if isinstance(row.get("transitionPolishCandidate"), dict):
        return row["transitionPolishCandidate"]
    if isinstance(row.get("selectedRecipe"), dict) or row.get("role") == "transition_polish_candidate":
        return row
    return {}


def selected_recipe(row: dict[str, Any]) -> dict[str, Any]:
    candidate = transition_candidate(row)
    recipe = candidate.get("selectedRecipe") if isinstance(candidate.get("selectedRecipe"), dict) else {}
    if recipe:
        return recipe
    return row.get("selectedRecipe") if isinstance(row.get("selectedRecipe"), dict) else {}


def row_index(row: dict[str, Any]) -> int:
    candidate = transition_candidate(row)
    return as_int(row.get("rowIndex") or candidate.get("rowIndex"), -1)


def boundary_seconds(row: dict[str, Any]) -> float | None:
    candidate = transition_candidate(row)
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds"):
        value = as_float(row.get(key))
        if value is not None:
            return value
    return as_float(candidate.get("boundarySeconds"))


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    out = [row for row in rows if isinstance(row, dict)]
    candidates = blueprint.get("transitionPolishCandidates") if isinstance(blueprint.get("transitionPolishCandidates"), list) else []
    for candidate in candidates:
        if isinstance(candidate, dict):
            out.append({"transitionPolishCandidate": candidate, **candidate})
    return out


def candidate_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitionPolishCandidates") if isinstance(blueprint.get("transitionPolishCandidates"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def markers_by_row(blueprint: dict[str, Any]) -> set[int]:
    markers = blueprint.get("timelineMarkers") if isinstance(blueprint.get("timelineMarkers"), list) else []
    out: set[int] = set()
    for marker in markers:
        if not isinstance(marker, dict) or marker.get("role") != "transition_polish_candidate_marker":
            continue
        payload = marker.get("payload") if isinstance(marker.get("payload"), dict) else {}
        index = as_int(payload.get("rowIndex"), -1)
        if index >= 0:
            out.add(index)
    return out


def clip_annotation_rows(blueprint: dict[str, Any]) -> set[int]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: set[int] = set()
    for clip in rows:
        if not isinstance(clip, dict):
            continue
        for key in ("transitionPolishOut", "transitionPolishIn"):
            annotations = clip.get(key) if isinstance(clip.get(key), list) else []
            for annotation in annotations:
                if isinstance(annotation, dict):
                    index = as_int(annotation.get("rowIndex"), -1)
                    if index >= 0:
                        out.add(index)
    return out


def rows_by_index(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        index = row_index(row)
        if index >= 0:
            out.setdefault(index, []).append(row)
    return out


def pair_key(row: dict[str, Any]) -> tuple[str, str]:
    candidate = transition_candidate(row)
    return (
        source_name(row.get("fromSourcePath") or candidate.get("fromSourcePath")),
        source_name(row.get("toSourcePath") or candidate.get("toSourcePath")),
    )


def match_row(expected: dict[str, Any], final_rows: list[dict[str, Any]], by_index: dict[int, list[dict[str, Any]]], *, tolerance: float) -> dict[str, Any] | None:
    expected_index = row_index(expected)
    indexed = by_index.get(expected_index) or []
    if indexed:
        return indexed[0]
    expected_pair = pair_key(expected)
    expected_boundary = boundary_seconds(expected)
    matches: list[tuple[float, dict[str, Any]]] = []
    for row in final_rows:
        if expected_pair != ("", "") and pair_key(row) != expected_pair:
            continue
        row_boundary = boundary_seconds(row)
        if expected_boundary is None or row_boundary is None:
            matches.append((0.0, row))
            continue
        distance = abs(expected_boundary - row_boundary)
        if distance <= tolerance:
            matches.append((distance, row))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def recipe_duration(row: dict[str, Any], fps: float) -> float:
    recipe = selected_recipe(row)
    duration = as_float(recipe.get("durationSeconds"))
    if duration is not None and duration > 0:
        return duration
    frames = as_float(recipe.get("durationFrames"))
    if frames is not None and frames > 0:
        return frames / max(fps, 1.0)
    return 0.0


def normalize_style(row: dict[str, Any]) -> str:
    candidate = transition_candidate(row)
    recipe = selected_recipe(row)
    text = " ".join(
        str(value or "")
        for value in (
            row.get("approvedTransitionType"),
            row.get("motionStyle"),
            candidate.get("motionStyle"),
            candidate.get("sourceTransitionType"),
            recipe.get("recipeId"),
            recipe.get("resolveEffectName"),
        )
    ).lower()
    if "whip" in text:
        return "whip_pan"
    if "rotation" in text:
        return "rotation"
    if "speed" in text or "ramp" in text:
        return "speed_ramp"
    if "push" in text or "slide" in text:
        return "push_slide"
    if "dissolve" in text or "cross" in text:
        return "dissolve"
    if "match" in text:
        return "match_cut"
    if "bridge" in text:
        return "bridge"
    return "clean_cut"


def bgm_ready(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    recipe = selected_recipe(row)
    bgm = candidate.get("bgmSync") if isinstance(candidate.get("bgmSync"), dict) else {}
    return bool(recipe.get("bgmHitSeconds") is not None or bgm.get("hitSeconds") is not None or bgm.get("phraseIndex") is not None)


def audio_bgm_only(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    bgm = candidate.get("bgmSync") if isinstance(candidate.get("bgmSync"), dict) else {}
    text = " ".join(str(value or "") for value in (row.get("audioPolicy"), candidate.get("audioPolicy"), bgm.get("audioTreatment"))).lower()
    return "bgm" in text and "voice" in text


def title_safe(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    title = candidate.get("titleSubtitleAvoidance") if isinstance(candidate.get("titleSubtitleAvoidance"), dict) else {}
    return bool(title.get("avoidTitleOverlayCollision") is True and as_float(title.get("suppressSubtitleSecondsBefore"), 0.0) > 0)


def decision_fields_ready(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    decision = candidate.get("decision") if isinstance(candidate.get("decision"), dict) else {}
    return DECISION_FIELDS.issubset(set(decision))


def pair_ready(row: dict[str, Any], style: str) -> bool:
    candidate = transition_candidate(row)
    continuity = candidate.get("pairContinuity") if isinstance(candidate.get("pairContinuity"), dict) else {}
    pair_fit = str(continuity.get("pairFit") or "")
    tags = continuity.get("evidenceTags") if isinstance(continuity.get("evidenceTags"), list) else []
    if pair_fit not in {"strong", "acceptable"} or continuity.get("styleAllowed") is not True or not tags:
        return False
    if style in MOTION_STYLES and pair_fit != "strong":
        return False
    return True


def motion_ready(row: dict[str, Any], style: str) -> bool:
    if style not in MOTION_STYLES:
        return True
    candidate = transition_candidate(row)
    continuity = candidate.get("pairContinuity") if isinstance(candidate.get("pairContinuity"), dict) else {}
    tags = continuity.get("evidenceTags") if isinstance(continuity.get("evidenceTags"), list) else []
    return bool(
        candidate.get("motionEvidenceSatisfied") is True
        or candidate.get("bridgeSequenceSatisfied") is True
        or "motion_match" in tags
        or "bridge_sequence" in tags
    )


def recipe_ready(row: dict[str, Any], fps: float) -> bool:
    recipe = selected_recipe(row)
    duration = recipe_duration(row, fps)
    keyframes = recipe.get("keyframePlan") if isinstance(recipe.get("keyframePlan"), list) else []
    return bool(recipe.get("recipeId") and recipe.get("resolveEffectName") and duration > 0 and duration <= 0.9 and keyframes)


def audited_row(expected: dict[str, Any], matched: dict[str, Any] | None, clip_rows: set[int], marker_rows: set[int], *, fps: float, tolerance: float) -> dict[str, Any]:
    expected_index = row_index(expected)
    issues: list[str] = []
    if not matched:
        return {
            "rowIndex": expected_index,
            "status": "blocked",
            "fromSourceName": pair_key(expected)[0],
            "toSourceName": pair_key(expected)[1],
            "boundarySeconds": boundary_seconds(expected),
            "recipeId": None,
            "issues": ["transition_polish_row_missing_from_final_blueprint"],
        }
    expected_recipe = selected_recipe(expected)
    recipe = selected_recipe(matched)
    style = normalize_style(matched)
    expected_boundary = boundary_seconds(expected)
    matched_boundary = boundary_seconds(matched)
    if expected.get("status") != "materialized":
        issues.append("source_transition_polish_row_not_materialized")
    if transition_candidate(matched).get("status") != "materialized":
        issues.append("final_transition_polish_row_not_materialized")
    if expected_recipe.get("recipeId") and recipe.get("recipeId") != expected_recipe.get("recipeId"):
        issues.append("final_recipe_id_changed_or_missing")
    if expected_boundary is not None and matched_boundary is not None and abs(expected_boundary - matched_boundary) > tolerance:
        issues.append("final_boundary_seconds_drifted")
    if pair_key(expected) != ("", "") and pair_key(matched) != pair_key(expected):
        issues.append("final_from_to_pair_changed")
    if not recipe_ready(matched, fps):
        issues.append("final_missing_or_invalid_recipe_keyframes_or_duration")
    if not bgm_ready(matched):
        issues.append("final_missing_bgm_hit_or_phrase")
    if not audio_bgm_only(matched):
        issues.append("final_missing_bgm_only_no_voice_policy")
    if not title_safe(matched):
        issues.append("final_missing_title_subtitle_avoidance")
    if not decision_fields_ready(matched):
        issues.append("final_missing_resolve_apply_decision_fields")
    if not pair_ready(matched, style):
        issues.append("final_pair_continuity_not_ready")
    if not motion_ready(matched, style):
        issues.append("final_motion_transition_lacks_motion_or_bridge_evidence")
    if expected_index not in clip_rows:
        issues.append("final_clip_transition_polish_annotations_missing")
    if expected_index not in marker_rows:
        issues.append("final_transition_polish_marker_missing")
    return {
        "rowIndex": expected_index,
        "status": "passed" if not issues else "blocked",
        "fromSourceName": pair_key(matched)[0],
        "toSourceName": pair_key(matched)[1],
        "boundarySeconds": round3(matched_boundary or 0.0),
        "expectedBoundarySeconds": round3(expected_boundary or 0.0),
        "style": style,
        "recipeId": recipe.get("recipeId"),
        "durationSeconds": round3(recipe_duration(matched, fps)),
        "hasBgmHit": bgm_ready(matched),
        "bgmOnlyAudio": audio_bgm_only(matched),
        "titleSafe": title_safe(matched),
        "decisionFieldsReady": decision_fields_ready(matched),
        "pairReady": pair_ready(matched, style),
        "motionReady": motion_ready(matched, style),
        "clipAnnotationPresent": expected_index in clip_rows,
        "markerPresent": expected_index in marker_rows,
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


def resolve_path(package_dir: Path, raw: Any) -> Path:
    path = Path(str(raw or "")).expanduser()
    if not path.is_absolute():
        path = (package_dir / path).resolve()
    return path


def final_blueprint_path(package_dir: Path, explicit: str | None) -> tuple[Path, str]:
    if explicit:
        return resolve_path(package_dir, explicit), "explicit_blueprint"
    return package_dir / "resolve_timeline_blueprint.json", "active_blueprint"


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    report_path = package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json"
    polish_report = load_json(report_path) or {}
    outputs = polish_report.get("outputs") if isinstance(polish_report.get("outputs"), dict) else {}
    candidate_path = resolve_path(package_dir, outputs.get("candidateBlueprint"))
    candidate = load_json(candidate_path) or {}
    final_path, final_kind = final_blueprint_path(package_dir, args.blueprint)
    final = load_json(final_path)
    if not isinstance(final, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "transitionPolishReport": str(report_path),
                "transitionPolishReportExists": report_path.exists(),
                "transitionPolishStatus": polish_report.get("status"),
                "sourceCandidateBlueprint": str(candidate_path),
                "sourceCandidateExists": candidate_path.exists(),
                "finalBlueprint": str(final_path),
                "finalBlueprintExists": final_path.exists(),
                "finalBlueprintKind": final_kind,
                "finalBlueprintInsidePackage": is_inside(final_path, package_dir),
            },
            "summary": {},
            "polishRows": [],
            "blockers": [f"missing or unreadable final blueprint: {final_path}"],
            "warnings": [],
            "safety": safety(),
        }
    expected_rows = [
        row for row in (polish_report.get("polishRows") if isinstance(polish_report.get("polishRows"), list) else [])
        if isinstance(row, dict)
    ]
    if not expected_rows and isinstance(candidate, dict):
        expected_rows = candidate_rows(candidate)
    final_rows = transition_rows(final)
    final_candidates = candidate_rows(final)
    by_index = rows_by_index(final_rows)
    clip_rows = clip_annotation_rows(final)
    marker_rows = markers_by_row(final)
    audited = [
        audited_row(row, match_row(row, final_rows, by_index, tolerance=args.tolerance_seconds), clip_rows, marker_rows, fps=args.fps, tolerance=args.tolerance_seconds)
        for row in expected_rows
    ]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    blockers = [f"transition polish row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked[:80]]
    warnings: list[str] = []
    final_plan = final.get("transitionPolishBlueprintPlan") if isinstance(final.get("transitionPolishBlueprintPlan"), dict) else {}
    visual_boundary_count = len(visual_boundaries(primary_visual_clips(final)))
    if polish_report.get("status") != "ready_with_transition_polish_blueprint":
        blockers.append(f"transition_polish_blueprint_report status is not ready: {polish_report.get('status')}")
    if not report_path.exists():
        blockers.append("transition_polish_blueprint_report.json is missing")
    if not candidate_path.exists():
        blockers.append(f"source transition polish candidate missing: {candidate_path}")
    if not is_inside(candidate_path, package_dir):
        blockers.append(f"source transition polish candidate is outside package: {candidate_path}")
    if not is_inside(final_path, package_dir):
        blockers.append(f"final blueprint is outside package: {final_path}")
    if not isinstance(final.get("transitionPolishBlueprintPlan"), dict):
        blockers.append("final blueprint is missing transitionPolishBlueprintPlan")
    if final_plan.get("candidateBlueprint") and source_name(final_plan.get("candidateBlueprint")) != source_name(candidate_path):
        warnings.append("final transitionPolishBlueprintPlan candidate path name differs from source candidate")
    if expected_rows and len(final_candidates) < len(expected_rows):
        blockers.append(f"final blueprint dropped transitionPolishCandidates: {len(final_candidates)}/{len(expected_rows)}")
    if expected_rows and len(final_rows) < len(expected_rows):
        blockers.append(f"final blueprint has too few transition rows: {len(final_rows)}/{len(expected_rows)}")
    if expected_rows and visual_boundary_count and len(final_candidates) < visual_boundary_count:
        blockers.append(f"final transition polish candidate count is below visual boundary count: {len(final_candidates)}/{visual_boundary_count}")
    if not expected_rows:
        blockers.append("transition polish report has no polishRows to apply")
    status = "passed" if not blockers and bool(expected_rows) else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "transitionPolishReport": str(report_path),
            "transitionPolishReportExists": report_path.exists(),
            "transitionPolishStatus": polish_report.get("status"),
            "sourceCandidateBlueprint": str(candidate_path),
            "sourceCandidateExists": candidate_path.exists(),
            "sourceCandidateInsidePackage": is_inside(candidate_path, package_dir),
            "finalBlueprint": str(final_path),
            "finalBlueprintExists": final_path.exists(),
            "finalBlueprintKind": final_kind,
            "finalBlueprintInsidePackage": is_inside(final_path, package_dir),
            "finalHasTransitionPolishBlueprintPlan": isinstance(final.get("transitionPolishBlueprintPlan"), dict),
        },
        "summary": {
            "sourcePolishRowCount": len(expected_rows),
            "finalTransitionPolishCandidateCount": len(final_candidates),
            "finalTransitionRowCount": len(final_rows),
            "finalVisualBoundaryCount": visual_boundary_count,
            "auditedPolishRowCount": len(audited),
            "passedPolishRowCount": sum(1 for row in audited if row.get("status") == "passed"),
            "blockedPolishRowCount": len(blocked),
            "recipeReadyRowCount": sum(1 for row in audited if row.get("recipeId") and not any("recipe" in issue for issue in row.get("issues", []))),
            "bgmHitRowCount": sum(1 for row in audited if row.get("hasBgmHit") is True),
            "bgmOnlyRowCount": sum(1 for row in audited if row.get("bgmOnlyAudio") is True),
            "titleSafeRowCount": sum(1 for row in audited if row.get("titleSafe") is True),
            "pairReadyRowCount": sum(1 for row in audited if row.get("pairReady") is True),
            "clipAnnotationRowCount": sum(1 for row in audited if row.get("clipAnnotationPresent") is True),
            "markerRowCount": sum(1 for row in audited if row.get("markerPresent") is True),
            "motionRowCount": sum(1 for row in audited if row.get("style") in MOTION_STYLES),
            "motionReadyRowCount": sum(1 for row in audited if row.get("style") in MOTION_STYLES and row.get("motionReady") is True),
            "blockerCount": len(blockers),
        },
        "polishRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Polish Application Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Final blueprint: `{report['inputs'].get('finalBlueprint')}`",
        f"Final blueprint kind: `{report['inputs'].get('finalBlueprintKind')}`",
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
    lines.extend(["", "## Polish Rows"])
    for row in report.get("polishRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('recipeId')}",
                f"- Status: `{row.get('status')}`",
                f"- Pair: `{row.get('fromSourceName')}` -> `{row.get('toSourceName')}`",
                f"- Boundary: `{row.get('boundarySeconds')}`s",
                f"- Ready: BGM `{row.get('hasBgmHit')}`, title `{row.get('titleSafe')}`, pair `{row.get('pairReady')}`, marker `{row.get('markerPresent')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether transition-polish rows survive into the final blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--tolerance-seconds", type=float, default=0.75)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_polish_application_contract_audit.json", report)
    write_markdown(package_dir / "transition_polish_application_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
