#!/usr/bin/env python3
"""Audit whether important transitions settle into readable scenes after the cut."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionViewerOrientation": ("transition_viewer_orientation_contract_audit.json", {"passed"}),
    "transitionBreathingRoom": ("transition_breathing_room_contract_audit.json", {"passed"}),
    "transitionStoryboard": ("transition_storyboard_contract_audit.json", {"passed"}),
    "sceneFlowArc": ("scene_flow_arc_contract_audit.json", {"passed"}),
    "shotFlowContinuity": ("shot_flow_continuity_contract_audit.json", {"passed"}),
    "pacingWatchability": ("pacing_watchability_contract_audit.json", {"passed"}),
    "narrativeAdjacency": ("narrative_adjacency_contract_audit.json", {"passed"}),
    "finalBlueprintLineage": ("final_blueprint_lineage_contract_audit.json", {"passed"}),
}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition", "ending_or_aftertaste_boundary"}
SETTLEMENT_TERMS = (
    "texture",
    "lived",
    "street",
    "walk",
    "walking",
    "market",
    "food",
    "station",
    "train",
    "hotel",
    "room",
    "window",
    "sign",
    "aerial",
    "scenic",
    "landmark",
    "harbor",
    "coast",
    "water",
    "people",
    "arrival",
    "aftertaste",
    "payoff",
    "bridge",
    "route",
    "movement",
    "街",
    "路",
    "车站",
    "火车",
    "市场",
    "吃",
    "酒店",
    "到达",
    "风景",
    "航拍",
)
UTILITY_TERMS = ("utility", "placeholder", "black", "slate", "generic", "duplicate", "test", "sample", "unknown")
TITLE_TERMS = ("title", "subtitle_overlay", "chapter_title", "opening_city", "ending_city")


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


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def summary_of(data: Any) -> dict[str, Any]:
    return data.get("summary") if isinstance(data, dict) and isinstance(data.get("summary"), dict) else {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def load_reports(package_dir: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for name, (relative, accepted) in REPORT_SPECS.items():
        path = package_dir / relative
        data = load_json(path) or {}
        reports[name] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(accepted),
            "accepted": data.get("status") in accepted,
            "summary": summary_of(data),
            "blockers": data.get("blockers") or [],
            "warnings": data.get("warnings") or [],
            "data": data,
        }
    return reports


def choose_blueprint(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path, str, bool]:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
        return load_json(path), path, "explicit_blueprint", is_inside(path, package_dir)
    candidates = [
        (package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json", "candidateBlueprint", "transition_polish_candidate"),
        (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json", "candidateBlueprint", "rhythm_recut_candidate"),
        (package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json", "candidateBlueprint", "bgm_phrase_candidate"),
        (package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json", "candidateBlueprint", "effect_motion_candidate"),
        (package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json", "candidateBlueprint", "transition_execution_candidate"),
        (package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json", "candidateBlueprint", "bridge_sequence_candidate"),
    ]
    for report_path, output_key, kind in candidates:
        report = load_json(report_path) or {}
        outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
        raw = outputs.get(output_key)
        if not raw or not str(report.get("status") or "").startswith("ready"):
            continue
        path = Path(str(raw)).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
        data = load_json(path)
        if isinstance(data, dict):
            return data, path, kind, is_inside(path, package_dir)
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint", is_inside(active, package_dir)


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def clip_duration(clip: dict[str, Any]) -> float:
    return max(0.0, timeline_end(clip) - timeline_start(clip))


def clip_text(clip: dict[str, Any]) -> str:
    fields = (
        "role",
        "purpose",
        "place",
        "titleText",
        "subtitle",
        "sourcePath",
        "sourceName",
        "name",
        "notes",
        "creatorFunction",
        "chapterRole",
        "sceneFunction",
    )
    return " ".join(str(clip.get(field) or "") for field in fields).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt", ".txt")):
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type not in {"", "video"}:
        return False
    return as_int(clip.get("mediaType"), 1) == 1


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    video = [row for row in rows if isinstance(row, dict) and is_video_clip(row)]
    return sorted(video, key=lambda item: (timeline_start(item), timeline_end(item), str(item.get("sourcePath") or "")))


def indexed_rows(data: dict[str, Any], keys: tuple[str, ...]) -> dict[int, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in keys:
        raw = data.get(key)
        if isinstance(raw, list):
            rows.extend(row for row in raw if isinstance(row, dict))
    out: dict[int, dict[str, Any]] = {}
    for fallback, row in enumerate(rows, start=1):
        index = as_int(row.get("rowIndex") or row.get("boundaryIndex"), fallback)
        if index > 0 and index not in out:
            out[index] = row
    return out


def storyboard_important(row: dict[str, Any]) -> bool:
    category = clean(row.get("boundaryCategory")).lower()
    return bool(row.get("importantBoundary")) or category in IMPORTANT_CATEGORIES


def orientation_important(row: dict[str, Any]) -> bool:
    category = clean(row.get("boundaryCategory")).lower()
    return bool(row.get("importantBoundary")) or category in IMPORTANT_CATEGORIES


def important_boundary_indexes(storyboard: dict[str, Any], orientation: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for index, row in indexed_rows(storyboard, ("auditedRows", "rows")).items():
        if storyboard_important(row):
            out.add(index)
    for index, row in indexed_rows(orientation, ("orientationRows", "rows")).items():
        if orientation_important(row):
            out.add(index)
    return out


def clip_has_settlement_texture(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    return any(term in text for term in SETTLEMENT_TERMS)


def clip_is_utility(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if any(term in text for term in UTILITY_TERMS):
        return True
    if any(term in text for term in TITLE_TERMS) and not any(term in text for term in ("scenic", "aerial", "skyline", "bridge", "street")):
        return True
    return False


def source_label(clip: dict[str, Any]) -> str:
    return clean(clip.get("sourceName") or Path(str(clip.get("sourcePath") or "")).name or clip.get("name"))


def settlement_window(
    clips: list[dict[str, Any]],
    boundary_index: int,
    important_indexes: set[int],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], float | None]:
    landing_position = boundary_index
    if landing_position >= len(clips):
        return [], None
    start_time = timeline_start(clips[landing_position])
    rows: list[dict[str, Any]] = []
    next_important_time: float | None = None
    for position in range(landing_position, len(clips)):
        boundary_before_clip = position
        if position > landing_position and boundary_before_clip in important_indexes:
            next_important_time = timeline_start(clips[position])
            break
        if timeline_start(clips[position]) - start_time > args.max_settlement_window_seconds:
            break
        if len(rows) >= args.max_settlement_clips:
            break
        rows.append(clips[position])
    if next_important_time is None:
        for next_index in sorted(index for index in important_indexes if index > boundary_index):
            if next_index < len(clips):
                next_important_time = timeline_start(clips[next_index])
                break
    return rows, next_important_time


def audit_boundary(
    boundary_index: int,
    clips: list[dict[str, Any]],
    storyboard: dict[int, dict[str, Any]],
    orientation: dict[int, dict[str, Any]],
    important_indexes: set[int],
    args: argparse.Namespace,
) -> dict[str, Any]:
    left = clips[boundary_index - 1] if 0 <= boundary_index - 1 < len(clips) else {}
    right = clips[boundary_index] if 0 <= boundary_index < len(clips) else {}
    window, next_important_time = settlement_window(clips, boundary_index, important_indexes, args)
    category = clean((storyboard.get(boundary_index) or orientation.get(boundary_index) or {}).get("boundaryCategory")).lower()
    ending = category in {"ending_transition", "ending_or_aftertaste_boundary"} or boundary_index >= len(clips) - 1
    min_duration = args.min_ending_settlement_seconds if ending else args.min_settlement_seconds
    min_clips = 1 if ending else args.min_settlement_clips
    duration = sum(clip_duration(clip) for clip in window)
    texture_count = sum(1 for clip in window if clip_has_settlement_texture(clip))
    utility_count = sum(1 for clip in window if clip_is_utility(clip))
    landing_duration = clip_duration(right) if right else 0.0
    time_to_next_important = None if next_important_time is None or not right else max(0.0, next_important_time - timeline_start(right))
    issues: list[str] = []
    if not right:
        issues.append("landing_clip_missing")
    if right and landing_duration < args.min_landing_seconds:
        issues.append("landing_clip_too_short_for_scene_settlement")
    if right and clip_is_utility(right):
        issues.append("landing_clip_is_title_utility_or_placeholder")
    if len(window) < min_clips:
        issues.append("settlement_window_has_too_few_clips")
    if duration < min_duration:
        issues.append("settlement_window_too_short")
    if texture_count < args.min_texture_clips:
        issues.append("settlement_window_lacks_lived_texture_or_payoff")
    if utility_count > 0:
        issues.append("settlement_window_contains_utility_or_placeholder_clip")
    if not ending and time_to_next_important is not None and time_to_next_important < args.min_seconds_before_next_important:
        issues.append("next_important_transition_arrives_too_fast")
    return {
        "boundaryIndex": boundary_index,
        "boundaryCategory": category,
        "status": "passed" if not issues else "blocked",
        "fromSourceName": source_label(left),
        "toSourceName": source_label(right),
        "landingDurationSeconds": round(landing_duration, 3),
        "settlementClipCount": len(window),
        "settlementDurationSeconds": round(duration, 3),
        "textureClipCount": texture_count,
        "utilityClipCount": utility_count,
        "timeToNextImportantSeconds": round(time_to_next_important, 3) if time_to_next_important is not None else None,
        "minSettlementClips": min_clips,
        "minSettlementSeconds": min_duration,
        "minSecondsBeforeNextImportant": args.min_seconds_before_next_important,
        "settlementSources": [source_label(clip) for clip in window],
        "issues": issues,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, args.blueprint)
    reports = load_reports(package_dir)
    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {"blueprint": str(blueprint_path), "blueprintKind": blueprint_kind, "blueprintInsidePackage": blueprint_inside_package},
            "summary": {},
            "settlementRows": [],
            "checks": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    clips = primary_visual_clips(blueprint)
    storyboard_data = reports["transitionStoryboard"]["data"] if isinstance(reports["transitionStoryboard"]["data"], dict) else {}
    orientation_data = reports["transitionViewerOrientation"]["data"] if isinstance(reports["transitionViewerOrientation"]["data"], dict) else {}
    storyboard_rows = indexed_rows(storyboard_data, ("auditedRows", "rows"))
    orientation_rows = indexed_rows(orientation_data, ("orientationRows", "rows"))
    important_indexes = {index for index in important_boundary_indexes(storyboard_data, orientation_data) if 1 <= index < len(clips)}
    settlement_rows = [
        audit_boundary(index, clips, storyboard_rows, orientation_rows, important_indexes, args)
        for index in sorted(important_indexes)
    ]
    blocked_rows = [row for row in settlement_rows if row["status"] == "blocked"]
    short_rows = [row for row in settlement_rows if "settlement_window_too_short" in row["issues"] or "settlement_window_has_too_few_clips" in row["issues"]]
    fast_rows = [row for row in settlement_rows if "next_important_transition_arrives_too_fast" in row["issues"]]
    generic_rows = [row for row in settlement_rows if "landing_clip_is_title_utility_or_placeholder" in row["issues"] or "settlement_window_contains_utility_or_placeholder_clip" in row["issues"]]
    texture_rows = [row for row in settlement_rows if row.get("textureClipCount", 0) >= args.min_texture_clips]

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required orientation, breathing-room, storyboard, scene-flow, shot-flow, pacing, narrative, and lineage reports are accepted",
        all(report["exists"] and report["accepted"] for report in reports.values()),
        {
            name: {
                "exists": report["exists"],
                "status": report["status"],
                "acceptedStatuses": report["acceptedStatuses"],
                "blockerCount": len(report["blockers"]),
            }
            for name, report in reports.items()
        },
    )
    add_check(
        checks,
        "Final candidate blueprint is package-local and has important transition boundaries to audit",
        blueprint_path.exists() and blueprint_inside_package and len(clips) >= 2 and len(important_indexes) >= args.min_important_boundaries,
        {
            "blueprint": str(blueprint_path),
            "blueprintKind": blueprint_kind,
            "blueprintExists": blueprint_path.exists(),
            "blueprintInsidePackage": blueprint_inside_package,
            "visualClipCount": len(clips),
            "importantBoundaryCount": len(important_indexes),
            "minImportantBoundaries": args.min_important_boundaries,
        },
    )
    add_check(
        checks,
        "Important transitions settle into enough local footage before the next idea",
        len(settlement_rows) >= args.min_important_boundaries and not short_rows and not fast_rows,
        {
            "settlementRowCount": len(settlement_rows),
            "shortSettlementCount": len(short_rows),
            "tooFastNextJumpCount": len(fast_rows),
            "minSettlementSeconds": args.min_settlement_seconds,
            "minSettlementClips": args.min_settlement_clips,
            "minSecondsBeforeNextImportant": args.min_seconds_before_next_important,
            "violations": (short_rows + fast_rows)[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Important transition landings are real scene footage with lived texture or payoff",
        not generic_rows and len(texture_rows) == len(settlement_rows),
        {
            "settlementRowCount": len(settlement_rows),
            "textureReadyCount": len(texture_rows),
            "genericLandingOrUtilityCount": len(generic_rows),
            "minTextureClips": args.min_texture_clips,
            "violations": generic_rows[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Upstream pacing and scene-flow summaries have no blocked checks while settlement rows are clean",
        not blocked_rows
        and as_int(reports["sceneFlowArc"]["summary"].get("blockedCheckCount")) == 0
        and as_int(reports["shotFlowContinuity"]["summary"].get("blockedCheckCount")) == 0
        and as_int(reports["pacingWatchability"]["summary"].get("blockedCheckCount")) == 0,
        {
            "blockedSettlementRowCount": len(blocked_rows),
            "sceneFlowArcSummary": reports["sceneFlowArc"]["summary"],
            "shotFlowContinuitySummary": reports["shotFlowContinuity"]["summary"],
            "pacingWatchabilitySummary": reports["pacingWatchability"]["summary"],
            "blockedRows": blocked_rows[: args.max_blocked_rows_in_report],
        },
    )

    blocked_checks = [check for check in checks if check["status"] == "blocked"]
    blockers = [check["name"] for check in blocked_checks]
    blockers.extend(f"boundary {row['boundaryIndex']}: {', '.join(row['issues'])}" for row in blocked_rows[: args.max_blocked_rows_in_report])
    warnings = [warning for report in reports.values() for warning in report["warnings"]]
    summary = {
        "visualClipCount": len(clips),
        "importantBoundaryCount": len(important_indexes),
        "settlementRowCount": len(settlement_rows),
        "readySettlementCount": len(settlement_rows) - len(blocked_rows),
        "blockedSettlementCount": len(blocked_rows),
        "shortSettlementCount": len(short_rows),
        "tooFastNextJumpCount": len(fast_rows),
        "genericLandingOrUtilityCount": len(generic_rows),
        "textureReadyCount": len(texture_rows),
        "blockedCheckCount": len(blocked_checks),
        "blockerCount": len(blockers),
        "blueprintKind": blueprint_kind,
        "blueprintInsidePackage": blueprint_inside_package,
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blocked_checks and not blocked_rows else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "reports": {name: report["path"] for name, report in reports.items()},
        },
        "summary": summary,
        "settlementRows": settlement_rows,
        "checks": checks,
        "reports": {name: {key: value for key, value in report.items() if key != "data"} for name, report in reports.items()},
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "importantTransitionsMustSettleIntoScene": True,
            "landingClipMustBeReadableSceneFootage": True,
            "settlementWindowMustContainTextureOrPayoff": True,
            "nextImportantTransitionCannotArriveImmediately": True,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Scene Settlement Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
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
    lines.extend(["", "## Settlement Rows"])
    for row in report.get("settlementRows", [])[:120]:
        lines.extend(
            [
                "",
                f"### Boundary {row.get('boundaryIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Landing duration: `{row.get('landingDurationSeconds')}`",
                f"- Settlement: `{row.get('settlementClipCount')}` clips / `{row.get('settlementDurationSeconds')}` seconds",
                f"- Texture clips: `{row.get('textureClipCount')}`",
                f"- Next important transition: `{row.get('timeToNextImportantSeconds')}` seconds",
                f"- Sources: `{', '.join(row.get('settlementSources') or [])}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Important transitions must land into a scene, not a single placeholder/title/card or an immediate second jump.",
            "- The post-transition window needs enough local footage and at least one lived texture, movement, payoff, route, or aftertaste cue.",
            "- This gate catches drafts that technically have transition effects but still feel like an AI slideshow instead of a reference-style vlog scene.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit post-transition scene settlement for important travel-film transitions.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--min-important-boundaries", type=int, default=1)
    parser.add_argument("--min-landing-seconds", type=float, default=2.0)
    parser.add_argument("--min-settlement-seconds", type=float, default=8.0)
    parser.add_argument("--min-ending-settlement-seconds", type=float, default=4.0)
    parser.add_argument("--min-settlement-clips", type=int, default=2)
    parser.add_argument("--min-texture-clips", type=int, default=1)
    parser.add_argument("--max-settlement-window-seconds", type=float, default=22.0)
    parser.add_argument("--max-settlement-clips", type=int, default=5)
    parser.add_argument("--min-seconds-before-next-important", type=float, default=6.0)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_scene_settlement_contract_audit.json", report)
    write_markdown(package_dir / "transition_scene_settlement_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
