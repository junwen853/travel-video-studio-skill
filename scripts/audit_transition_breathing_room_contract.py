#!/usr/bin/env python3
"""Audit transition breathing-room and landing stability."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionMicrostructure": ("transition_microstructure_contract_audit.json", {"passed"}),
    "transitionChoreography": ("transition_choreography_contract_audit.json", {"passed"}),
    "transitionPreviewQuality": ("transition_preview_quality_contract_audit.json", {"passed"}),
    "transitionAuditionQuality": ("transition_audition_quality_contract_audit.json", {"passed"}),
    "transitionStoryboard": ("transition_storyboard_contract_audit.json", {"passed"}),
    "referenceTransitionProfile": ("reference_transition_profile_contract_audit.json", {"passed"}),
    "shotFlowContinuity": ("shot_flow_continuity_contract_audit.json", {"passed"}),
}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
HIGH_INTENSITY_STYLES = {"whip_pan", "speed_ramp", "push_slide", "whip_pan_match", "speed_ramp_bridge"}
BREATH_STYLES = {"clean_cut", "match_cut", "dissolve", "bridge_insert", "mood_dissolve_breath", "texture_bridge_cutaway"}
TITLE_TERMS = ("title", "opening_city", "chapter_title", "ending_city", "subtitle_overlay", "hero title")
UTILITY_TERMS = ("utility", "placeholder", "black", "slate", "generic", "duplicate", "test", "sample")
LANDING_TERMS = (
    "scenic",
    "street",
    "texture",
    "lived",
    "route",
    "transport",
    "station",
    "train",
    "metro",
    "airport",
    "bridge",
    "skyline",
    "aerial",
    "landmark",
    "harbor",
    "coast",
    "water",
    "food",
    "hotel",
    "window",
    "weather",
    "market",
    "sign",
    "ending",
    "aftertaste",
)


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


def round3(value: float) -> float:
    return round(float(value), 3)


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


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


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in (
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
        )
    ).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt", ".txt")):
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type not in {"", "video"}:
        return False
    return as_int(clip.get("mediaType"), 1) == 1


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


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    video = [row for row in rows if isinstance(row, dict) and is_video_clip(row)]
    return sorted(video, key=lambda item: (timeline_start(item), timeline_end(item), str(item.get("sourcePath") or "")))


def load_reports(package_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, (relative, accepted) in REPORT_SPECS.items():
        path = package_dir / relative
        data = load_json(path) or {}
        out[name] = {
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
    return out


def indexed_rows(data: dict[str, Any], keys: tuple[str, ...]) -> dict[int, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in keys:
        raw = data.get(key)
        if isinstance(raw, list):
            rows.extend(row for row in raw if isinstance(row, dict))
    out: dict[int, dict[str, Any]] = {}
    for fallback, row in enumerate(rows, start=1):
        index = as_int(row.get("rowIndex"), fallback)
        if index > 0 and index not in out:
            out[index] = row
    return out


def normalize_style(value: Any) -> str:
    text = str(value or "").lower()
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
        return "bridge_insert"
    if "breath" in text:
        return "mood_dissolve_breath"
    return "clean_cut"


def row_style(choreography: dict[str, Any], storyboard: dict[str, Any]) -> str:
    for value in (
        choreography.get("sourceTransitionStyle"),
        storyboard.get("style"),
        choreography.get("choreographyFamily"),
        storyboard.get("storyboardPurpose"),
    ):
        style = normalize_style(value)
        if style != "clean_cut" or value:
            return style
    return "clean_cut"


def has_beat(row: dict[str, Any], role: str) -> bool:
    beats = row.get("threeBeatChoreography") if isinstance(row.get("threeBeatChoreography"), list) else []
    return any(isinstance(beat, dict) and beat.get("role") == role and str(beat.get("action") or "").strip() for beat in beats)


def present(value: Any) -> bool:
    return value is not None and str(value).strip() not in {"", "[]", "{}", "none", "None", "null"}


def landing_text_ready(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if any(term in text for term in TITLE_TERMS) and not any(term in text for term in ("scenic", "bridge", "aerial", "skyline")):
        return False
    if any(term in text for term in UTILITY_TERMS):
        return False
    return bool(any(term in text for term in LANDING_TERMS) or clip.get("sourcePath") or clip.get("sourceName"))


def important_boundary(index: int, left: dict[str, Any], right: dict[str, Any], choreography: dict[str, Any], storyboard: dict[str, Any]) -> bool:
    category = str(choreography.get("boundaryCategory") or storyboard.get("boundaryCategory") or "").lower()
    if bool(choreography.get("importantBoundary")) or bool(storyboard.get("importantBoundary")) or category in IMPORTANT_CATEGORIES:
        return True
    left_chapter = str(left.get("chapterIndex") or "")
    right_chapter = str(right.get("chapterIndex") or "")
    if left_chapter and right_chapter and left_chapter != right_chapter:
        return True
    if timeline_start(right) - timeline_end(left) > 0.35:
        return True
    text = f"{clip_text(left)} {clip_text(right)}"
    return any(term in text for term in TITLE_TERMS) or index == 1


def boundary_row(
    index: int,
    left: dict[str, Any],
    right: dict[str, Any],
    choreography: dict[str, Any],
    storyboard: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    style = row_style(choreography, storyboard)
    family = str(choreography.get("choreographyFamily") or "")
    intensity = as_int(choreography.get("intensity"), 0)
    important = important_boundary(index, left, right, choreography, storyboard)
    motion = style in MOTION_STYLES or "motion" in family or "accent" in family
    high_intensity = style in HIGH_INTENSITY_STYLES or intensity >= 2
    right_duration = max(0.0, timeline_end(right) - timeline_start(right))
    threshold = args.min_important_landing_seconds if important or motion else args.min_landing_seconds
    storyboard_landing = present(storyboard.get("landingShotEvidence"))
    storyboard_bridge = present(storyboard.get("bridgeOrMotionBeatEvidence")) or bool(storyboard.get("motionEvidence"))
    plan_landing = has_beat(choreography, "landing")
    plan_bridge = has_beat(choreography, "bridge_or_motion")
    landing_ready = (
        landing_text_ready(right)
        and (
            right_duration >= threshold
            or (right_duration >= args.min_landing_seconds and storyboard_landing and plan_landing)
        )
    )
    breath_style = style in BREATH_STYLES or "breath" in family or "bridge" in family or "match" in style
    caption_policy = choreography.get("captionAndTitlePolicy") if isinstance(choreography.get("captionAndTitlePolicy"), dict) else {}
    title_collision_risk = motion and any(term in f"{clip_text(left)} {clip_text(right)}" for term in TITLE_TERMS)
    subtitle_collision_risk = motion and caption_policy.get("avoidTitleCollision") is not True
    bridge_landing_ready = (not important) or (storyboard_bridge or plan_bridge or "bridge" in family or "bridge" in style)
    issues: list[str] = []
    if not choreography:
        issues.append("missing_choreography_row")
    if not storyboard:
        issues.append("missing_storyboard_row")
    if important and not bridge_landing_ready:
        issues.append("important_boundary_lacks_bridge_or_motion_breath")
    if (important or motion) and not landing_ready:
        issues.append("landing_clip_too_short_or_unreadable")
    if high_intensity and not (landing_ready and bridge_landing_ready and storyboard_landing):
        issues.append("high_intensity_transition_without_proven_landing")
    if title_collision_risk:
        issues.append("motion_transition_touches_title_or_subtitle_zone")
    if subtitle_collision_risk:
        issues.append("motion_transition_missing_caption_quiet_policy")
    return {
        "boundaryIndex": index,
        "status": "passed" if not issues else "blocked",
        "fromSourceName": source_name(left.get("sourcePath") or left.get("sourceName")),
        "toSourceName": source_name(right.get("sourcePath") or right.get("sourceName")),
        "fromTimelineEndSeconds": round3(timeline_end(left)),
        "toTimelineStartSeconds": round3(timeline_start(right)),
        "landingDurationSeconds": round3(right_duration),
        "landingThresholdSeconds": threshold,
        "style": style,
        "choreographyFamily": family,
        "intensity": intensity,
        "importantBoundary": important,
        "motionAccentBoundary": motion,
        "highIntensityBoundary": high_intensity,
        "breathStyle": breath_style,
        "landingTextReady": landing_text_ready(right),
        "landingDurationReady": right_duration >= threshold,
        "storyboardLandingEvidence": storyboard_landing,
        "storyboardBridgeOrMotionEvidence": storyboard_bridge,
        "planLandingBeat": plan_landing,
        "planBridgeOrMotionBeat": plan_bridge,
        "bridgeLandingReady": bridge_landing_ready,
        "quietLandingReady": landing_ready and not title_collision_risk and not subtitle_collision_risk,
        "titleCollisionRisk": title_collision_risk,
        "subtitleCollisionRisk": subtitle_collision_risk,
        "issues": issues,
    }


def max_true_run(rows: list[dict[str, Any]], key: str) -> int:
    best = 0
    current = 0
    for row in rows:
        if row.get(key):
            current += 1
        else:
            current = 0
        best = max(best, current)
    return best


def spacing_violations(rows: list[dict[str, Any]], key: str, minimum_gap: int) -> list[dict[str, Any]]:
    indexes = [as_int(row.get("boundaryIndex")) for row in rows if row.get(key)]
    out: list[dict[str, Any]] = []
    for left, right in zip(indexes, indexes[1:]):
        non_motion_between = right - left - 1
        if non_motion_between < minimum_gap:
            out.append({"fromBoundary": left, "toBoundary": right, "nonMotionBoundariesBetween": non_motion_between, "minimumRequired": minimum_gap})
    return out


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
            "inputs": {
                "blueprint": str(blueprint_path),
                "blueprintExists": blueprint_path.exists(),
                "blueprintKind": blueprint_kind,
                "blueprintInsidePackage": blueprint_inside_package,
            },
            "summary": {},
            "boundaryRows": [],
            "checks": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }

    clips = primary_visual_clips(blueprint)
    visual_boundaries = max(len(clips) - 1, 0)
    choreography_plan = load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json") or {}
    storyboard_audit = reports["transitionStoryboard"]["data"] if isinstance(reports["transitionStoryboard"]["data"], dict) else {}
    choreography_rows = indexed_rows(choreography_plan, ("choreographyRows", "rows"))
    storyboard_rows = indexed_rows(storyboard_audit, ("auditedRows", "rows"))
    boundaries = [
        boundary_row(index, clips[index - 1], clips[index], choreography_rows.get(index, {}), storyboard_rows.get(index, {}), args)
        for index in range(1, visual_boundaries + 1)
    ]

    important_count = sum(1 for row in boundaries if row.get("importantBoundary"))
    motion_count = sum(1 for row in boundaries if row.get("motionAccentBoundary"))
    high_count = sum(1 for row in boundaries if row.get("highIntensityBoundary"))
    high_run = max_true_run(boundaries, "highIntensityBoundary")
    motion_run = max_true_run(boundaries, "motionAccentBoundary")
    motion_spacing = spacing_violations(boundaries, "motionAccentBoundary", args.min_non_motion_between_motion)
    landing_violations = [row for row in boundaries if ("landing_clip_too_short_or_unreadable" in (row.get("issues") or []))]
    important_landing_ready = sum(1 for row in boundaries if row.get("importantBoundary") and row.get("quietLandingReady"))
    breath_after_important_ready = sum(1 for row in boundaries if row.get("importantBoundary") and row.get("bridgeLandingReady") and row.get("quietLandingReady"))
    subtitle_risks = [row for row in boundaries if row.get("subtitleCollisionRisk")]
    title_risks = [row for row in boundaries if row.get("titleCollisionRisk")]
    bridge_landing_count = sum(1 for row in boundaries if row.get("bridgeLandingReady") and row.get("storyboardLandingEvidence"))
    max_motion_allowed = max(1, int(round(max(visual_boundaries, 1) * args.max_motion_share)))
    clean_breath_count = sum(1 for row in boundaries if row.get("breathStyle"))
    clean_breath_share = clean_breath_count / visual_boundaries if visual_boundaries else 0.0

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Final candidate blueprint is inside the package and has adjacent visual boundaries",
        blueprint_path.exists() and blueprint_inside_package and visual_boundaries >= 1,
        {
            "blueprint": str(blueprint_path),
            "blueprintKind": blueprint_kind,
            "blueprintExists": blueprint_path.exists(),
            "blueprintInsidePackage": blueprint_inside_package,
            "visualClipCount": len(clips),
            "visualBoundaryCount": visual_boundaries,
        },
    )
    add_check(
        checks,
        "Upstream transition, reference, storyboard, and shot-flow reports are accepted",
        all(row["exists"] and row["accepted"] for row in reports.values()),
        {
            name: {
                "exists": row["exists"],
                "status": row["status"],
                "acceptedStatuses": row["acceptedStatuses"],
                "blockerCount": len(row["blockers"]),
            }
            for name, row in reports.items()
        },
    )
    add_check(
        checks,
        "Transition rows cover every adjacent boundary with outgoing, bridge-or-motion, and landing proof",
        visual_boundaries >= 1
        and len(choreography_rows) >= visual_boundaries
        and len(storyboard_rows) >= visual_boundaries
        and bridge_landing_count >= visual_boundaries,
        {
            "visualBoundaryCount": visual_boundaries,
            "choreographyRowCount": len(choreography_rows),
            "storyboardRowCount": len(storyboard_rows),
            "bridgeLandingEvidenceCount": bridge_landing_count,
        },
    )
    add_check(
        checks,
        "Important and motion boundaries land on stable readable footage before the next idea",
        not landing_violations and (important_count == 0 or breath_after_important_ready >= important_count),
        {
            "importantBoundaryCount": important_count,
            "breathAfterImportantReadyCount": breath_after_important_ready,
            "landingDurationViolationCount": len(landing_violations),
            "minLandingSeconds": args.min_landing_seconds,
            "minImportantLandingSeconds": args.min_important_landing_seconds,
            "violations": landing_violations[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Motion accents are rare and separated by calm boundaries",
        motion_count <= max_motion_allowed and high_run <= 1 and motion_run <= 1 and not motion_spacing,
        {
            "motionAccentBoundaryCount": motion_count,
            "highIntensityBoundaryCount": high_count,
            "maxMotionAllowed": max_motion_allowed,
            "highIntensityRunMax": high_run,
            "motionAccentRunMax": motion_run,
            "motionSpacingViolationCount": len(motion_spacing),
            "motionSpacingViolations": motion_spacing[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Transition breathing room avoids title/subtitle collision and keeps the reference clean-breath balance",
        not title_risks
        and not subtitle_risks
        and (visual_boundaries < 3 or clean_breath_share >= args.min_clean_breath_share),
        {
            "titleCollisionRiskCount": len(title_risks),
            "subtitleCollisionRiskCount": len(subtitle_risks),
            "cleanBreathBoundaryCount": clean_breath_count,
            "cleanBreathShare": round3(clean_breath_share),
            "minimumCleanBreathShare": args.min_clean_breath_share,
        },
    )

    blocked_checks = [row for row in checks if row["status"] == "blocked"]
    row_blockers = [
        f"boundary {row.get('boundaryIndex')} {row.get('style')}: {', '.join(row.get('issues') or [])}"
        for row in boundaries
        if row.get("issues")
    ]
    blockers = [row["name"] for row in blocked_checks] + row_blockers[: args.max_blocked_rows_in_report]
    warnings = [warning for report in reports.values() for warning in report["warnings"]]
    summary = {
        "visualBoundaryCount": visual_boundaries,
        "importantBoundaryCount": important_count,
        "motionAccentBoundaryCount": motion_count,
        "highIntensityBoundaryCount": high_count,
        "highIntensityRunMax": high_run,
        "motionAccentRunMax": motion_run,
        "maxMotionAllowed": max_motion_allowed,
        "motionSpacingViolationCount": len(motion_spacing),
        "landingDurationViolationCount": len(landing_violations),
        "quietLandingReadyCount": sum(1 for row in boundaries if row.get("quietLandingReady")),
        "breathAfterImportantReadyCount": breath_after_important_ready,
        "subtitleCollisionRiskCount": len(subtitle_risks),
        "titleCollisionRiskCount": len(title_risks),
        "bridgeLandingEvidenceCount": bridge_landing_count,
        "cleanBreathBoundaryCount": clean_breath_count,
        "cleanBreathShare": round3(clean_breath_share),
        "transitionMicrostructureStatus": reports["transitionMicrostructure"]["status"],
        "transitionChoreographyStatus": reports["transitionChoreography"]["status"],
        "transitionPreviewQualityStatus": reports["transitionPreviewQuality"]["status"],
        "transitionAuditionQualityStatus": reports["transitionAuditionQuality"]["status"],
        "transitionStoryboardStatus": reports["transitionStoryboard"]["status"],
        "referenceTransitionProfileStatus": reports["referenceTransitionProfile"]["status"],
        "shotFlowContinuityStatus": reports["shotFlowContinuity"]["status"],
        "passedCheckCount": len(checks) - len(blocked_checks),
        "blockedCheckCount": len(blocked_checks),
        "blockerCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "minLandingSeconds": args.min_landing_seconds,
            "minImportantLandingSeconds": args.min_important_landing_seconds,
            "maxMotionShare": args.max_motion_share,
            "minCleanBreathShare": args.min_clean_breath_share,
            "minNonMotionBetweenMotion": args.min_non_motion_between_motion,
        },
        "summary": summary,
        "boundaryRows": boundaries,
        "checks": checks,
        "reports": {name: {key: value for key, value in row.items() if key != "data"} for name, row in reports.items()},
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "postTransitionBreathingRoomRequired": True,
            "importantBoundariesNeedStableLanding": True,
            "motionAccentsMustBeRareAndSeparated": True,
            "titleSubtitleCollisionBlocked": True,
            "referenceCleanBreathBalanceRequired": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Breathing Room Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report.get('inputs', {}).get('blueprint')}`",
        f"Blueprint kind: `{report.get('inputs', {}).get('blueprintKind')}`",
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
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(["", f"### {row.get('name')}", f"- Status: `{row.get('status')}`"])
    lines.extend(["", "## Boundaries"])
    for row in report.get("boundaryRows") or []:
        lines.extend(
            [
                "",
                f"### Boundary {row.get('boundaryIndex')}: `{row.get('style')}`",
                f"- Status: `{row.get('status')}`",
                f"- Important: `{row.get('importantBoundary')}` motion=`{row.get('motionAccentBoundary')}` high=`{row.get('highIntensityBoundary')}`",
                f"- Landing: `{row.get('toSourceName')}` duration=`{row.get('landingDurationSeconds')}` ready=`{row.get('quietLandingReady')}`",
                f"- Issues: `{', '.join(row.get('issues') or []) or 'none'}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition breathing room and landing stability on the final candidate blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--min-landing-seconds", type=float, default=1.6)
    parser.add_argument("--min-important-landing-seconds", type=float, default=2.4)
    parser.add_argument("--max-motion-share", type=float, default=0.25)
    parser.add_argument("--min-clean-breath-share", type=float, default=0.45)
    parser.add_argument("--min-non-motion-between-motion", type=int, default=2)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=16)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_breathing_room_contract_audit.json", report)
    write_markdown(package_dir / "transition_breathing_room_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
