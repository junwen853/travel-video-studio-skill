#!/usr/bin/env python3
"""Audit whether the final candidate cut has smooth, motivated joins."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "finalBlueprintLineage": ("final_blueprint_lineage_contract_audit.json", {"passed"}),
    "transitionBreathingRoom": ("transition_breathing_room_contract_audit.json", {"passed"}),
    "sceneFlowArc": ("scene_flow_arc_contract_audit.json", {"passed"}),
    "shotFlowContinuity": ("shot_flow_continuity_contract_audit.json", {"passed"}),
    "transitionVisualMatch": ("transition_visual_match_contract_audit.json", {"passed"}),
    "transitionChoreography": ("transition_choreography_contract_audit.json", {"passed"}),
    "transitionStoryboard": ("transition_storyboard_contract_audit.json", {"passed"}),
}
PRIMARY_BEATS = ("context", "movement", "texture", "payoff", "aftertaste")
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
HIGH_INTENSITY_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
BRIDGE_STYLES = {"bridge_insert", "insert_bridge_first", "speed_ramp_bridge", "texture_bridge_cutaway", "short_dissolve_after_bridge"}
MATCH_STYLES = {"match_cut", "whip_pan_match", "rotation_match_cut", "mood_dissolve", "mood_dissolve_breath", "short_dissolve"}
TITLE_TERMS = ("title", "opening_city", "chapter_title", "ending_city", "hero title", "subtitle_overlay")
WEAK_TERMS = ("black", "placeholder", "slate", "generic", "test", "sample", "duplicate", "obstruct", "blur")
BRIDGE_TERMS = (
    "bridge",
    "route",
    "transport",
    "station",
    "train",
    "metro",
    "subway",
    "airport",
    "road",
    "walk",
    "arrival",
    "departure",
    "street",
    "sign",
    "food",
    "hotel",
    "window",
    "weather",
    "market",
    "ferry",
    "bus",
    "car",
    "luggage",
)
MOTION_TERMS = ("pan", "tilt", "walk", "drive", "train", "metro", "subway", "ferry", "bus", "car", "motion", "moving", "route")
FUNCTION_BEATS = {
    "opening_hook": "context",
    "route_observation": "context",
    "title_bridge": "context",
    "route_movement": "movement",
    "transport_motion": "movement",
    "route_transition": "movement",
    "lived_in_detail": "texture",
    "street_texture": "texture",
    "destination_payoff": "payoff",
    "landmark_payoff": "payoff",
    "scenic_breathing": "payoff",
    "ending_aftertaste": "aftertaste",
    "aftertaste": "aftertaste",
}
TERM_BEATS = {
    "context": ("context", "opening", "chapter", "city", "place", "promise", "people", "face", "reaction", "vlog", "title_bridge"),
    "movement": BRIDGE_TERMS + ("movement", "ticket", "bridge footage"),
    "texture": (
        "texture",
        "lived",
        "street",
        "food",
        "hotel",
        "market",
        "shop",
        "detail",
        "daily",
        "interior",
        "sign",
        "weather",
        "coffee",
        "room",
        "crowd",
        "night",
    ),
    "payoff": (
        "payoff",
        "landmark",
        "destination",
        "scenic",
        "aerial",
        "drone",
        "skyline",
        "hero",
        "viewpoint",
        "coast",
        "temple",
        "tower",
        "castle",
        "harbor",
        "mountain",
        "panorama",
    ),
    "aftertaste": ("aftertaste", "ending", "callback", "final", "sunset", "dusk", "quiet", "departure", "leaving", "night window"),
}


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


def normalize_chapter(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return "unassigned"
    text = str(value).strip()
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except ValueError:
        pass
    return text


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in (
            "role",
            "purpose",
            "place",
            "city",
            "chapter",
            "titleText",
            "subtitle",
            "sourcePath",
            "sourceName",
            "name",
            "notes",
            "creatorFunction",
            "editorialTier",
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


def classify_beat(clip: dict[str, Any]) -> tuple[str, list[str]]:
    text = clip_text(clip)
    groups: set[str] = set()
    function = str(clip.get("creatorFunction") or "")
    if function in FUNCTION_BEATS:
        groups.add(FUNCTION_BEATS[function])
    if any(term in text for term in TITLE_TERMS) and "scenic" not in text and "bridge" not in text:
        return "title", sorted(groups or {"context"})
    if "transition" in text or "bridge" in text or "motion" in text:
        groups.add("movement")
    for beat, terms in TERM_BEATS.items():
        if any(term in text for term in terms):
            groups.add(beat)
    if not groups:
        return "unclassified", []
    for beat in ("aftertaste", "movement", "texture", "payoff", "context"):
        if beat in groups:
            return beat, sorted(groups)
    return "unclassified", sorted(groups)


def annotate_clip(index: int, clip: dict[str, Any]) -> dict[str, Any]:
    beat, groups = classify_beat(clip)
    text = clip_text(clip)
    issues: list[str] = []
    if beat == "unclassified":
        issues.append("clip_has_no_final_cut_role")
    if any(term in text for term in WEAK_TERMS):
        issues.append("weak_or_placeholder_clip")
    return {
        "clipIndex": index,
        "chapterIndex": normalize_chapter(clip.get("chapterIndex")),
        "sourcePath": clip.get("sourcePath"),
        "sourceName": source_name(clip.get("sourcePath") or clip.get("sourceName")),
        "timelineStartSeconds": round3(timeline_start(clip)),
        "timelineEndSeconds": round3(timeline_end(clip)),
        "durationSeconds": round3(max(0.0, timeline_end(clip) - timeline_start(clip))),
        "role": clip.get("role"),
        "purpose": clip.get("purpose"),
        "beat": beat,
        "beatGroups": groups,
        "text": text,
        "issues": issues,
    }


def normalize_style(value: Any) -> str:
    text = str(value or "").lower()
    if "whip" in text:
        return "whip_pan"
    if "rotation" in text or "rotate" in text:
        return "rotation"
    if "speed" in text or "ramp" in text:
        return "speed_ramp"
    if "push" in text or "slide" in text:
        return "push_slide"
    if "bridge" in text:
        return "bridge_insert"
    if "dissolve" in text or "cross" in text:
        return "short_dissolve"
    if "match" in text:
        return "match_cut"
    if "cut" in text:
        return "clean_cut"
    return ""


def row_text(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True).lower()


def row_style(row: dict[str, Any] | None) -> str:
    if not row:
        return "clean_cut"
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    for value in (
        row.get("recommendedTransitionType"),
        row.get("transitionType"),
        row.get("transitionStyle"),
        row.get("sourceTransitionStyle"),
        row.get("style"),
        row.get("choreographyFamily"),
        recommendation.get("recommendedTransitionType"),
        recommendation.get("style"),
    ):
        style = normalize_style(value)
        if style:
            return style
    return "clean_cut"


def row_boundary(row: dict[str, Any]) -> float | None:
    for key in ("boundarySeconds", "timelineSeconds", "timeSeconds", "recordStartSeconds", "timelineStartSeconds"):
        number = as_float(row.get(key), None)
        if number is not None:
            return float(number)
    for key in ("fromClip", "outgoingClip"):
        clip = row.get(key) if isinstance(row.get(key), dict) else {}
        number = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds"), None)
        if number is not None:
            return float(number)
    return None


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("transitions", "transitionPlan", "transitionPolishCandidates", "transitionCandidates"):
        rows = blueprint.get(key) if isinstance(blueprint.get(key), list) else []
        for fallback, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            copy = dict(row)
            copy.setdefault("rowIndex", fallback)
            copy.setdefault("_sourceList", key)
            out.append(copy)
    return out


def match_transition(row_index: int, boundary: float, transitions: list[dict[str, Any]], tolerance: float) -> dict[str, Any] | None:
    for row in transitions:
        if as_int(row.get("rowIndex"), -1) == row_index:
            return row
    best: tuple[float, dict[str, Any]] | None = None
    for row in transitions:
        row_time = row_boundary(row)
        if row_time is None:
            continue
        distance = abs(float(row_time) - boundary)
        if distance <= tolerance and (best is None or distance < best[0]):
            best = (distance, row)
    return best[1] if best else None


def has_bridge_evidence(row: dict[str, Any] | None, *clips: dict[str, Any]) -> bool:
    if row:
        text = row_text(row)
        if any(term in text for term in BRIDGE_TERMS):
            return True
        if "physicalbridgeevidence" in text and "true" in text:
            return True
    for clip in clips:
        text = str(clip.get("text") or "")
        if clip.get("beat") in {"movement", "texture"}:
            return True
        if any(term in text for term in BRIDGE_TERMS):
            return True
    return False


def has_two_sided_motion(row: dict[str, Any] | None, left: dict[str, Any], right: dict[str, Any]) -> bool:
    if row:
        text = row_text(row)
        if "twosidedmotion" in text and "true" in text:
            return True
        if "frommotionterms" in text and "tomotionterms" in text and "[]" not in text:
            return True
    left_text = str(left.get("text") or "")
    right_text = str(right.get("text") or "")
    left_motion = left.get("beat") == "movement" or any(term in left_text for term in MOTION_TERMS)
    right_motion = right.get("beat") == "movement" or any(term in right_text for term in MOTION_TERMS)
    return bool(left_motion and right_motion)


def is_title(row: dict[str, Any]) -> bool:
    return row.get("beat") == "title" or any(term in str(row.get("text") or "") for term in TITLE_TERMS)


def high_intensity_run(styles: list[str]) -> int:
    best = 0
    current = 0
    for style in styles:
        if style in HIGH_INTENSITY_STYLES:
            current += 1
        else:
            current = 0
        best = max(best, current)
    return best


def boundary_rows(annotated: list[dict[str, Any]], transitions: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(annotated, annotated[1:]), start=1):
        boundary = float(left.get("timelineEndSeconds") or 0.0)
        transition = match_transition(index, boundary, transitions, args.transition_match_tolerance_seconds)
        style = row_style(transition)
        gap = float(right.get("timelineStartSeconds") or 0.0) - float(left.get("timelineEndSeconds") or 0.0)
        chapter_change = left.get("chapterIndex") != right.get("chapterIndex")
        important = chapter_change or gap > args.max_unexplained_gap_seconds or is_title(left) or is_title(right)
        bridge = has_bridge_evidence(transition, left, right)
        two_sided_motion = has_two_sided_motion(transition, left, right)
        landing_duration = float(right.get("durationSeconds") or 0.0)
        issues: list[str] = []

        if important and not transition:
            issues.append("important_boundary_missing_final_transition_metadata")
        if important and not bridge and style not in (BRIDGE_STYLES | MATCH_STYLES):
            issues.append("important_boundary_lacks_bridge_match_or_breath_reason")
        if gap > args.max_unexplained_gap_seconds and not bridge:
            issues.append("timeline_gap_without_bridge_or_route_texture")
        if left.get("beat") == "payoff" and right.get("beat") == "payoff" and not bridge and style not in MATCH_STYLES:
            issues.append("payoff_to_payoff_jump_without_bridge_or_match")
        if left.get("beat") in {"title", "unclassified"} or right.get("beat") in {"title", "unclassified"}:
            if important or style in HIGH_INTENSITY_STYLES:
                issues.append("title_or_unclassified_clip_used_as_transition_landing")
        if left.get("issues") or right.get("issues"):
            issues.append("weak_or_unclassified_clip_at_boundary")
        if style in MOTION_STYLES and not (two_sided_motion or bridge):
            issues.append("motion_effect_without_two_sided_motion_or_bridge_evidence")
        if style in HIGH_INTENSITY_STYLES and landing_duration < args.min_landing_seconds:
            issues.append("high_intensity_transition_without_stable_landing_duration")
        if style in HIGH_INTENSITY_STYLES and right.get("beat") not in PRIMARY_BEATS:
            issues.append("high_intensity_transition_lands_on_non_primary_clip")
        if source_name(left.get("sourcePath")) == source_name(right.get("sourcePath")) and landing_duration < args.min_landing_seconds:
            issues.append("same_source_stutter_without_stable_landing")

        rows.append(
            {
                "boundaryIndex": index,
                "status": "passed" if not issues else "blocked",
                "boundarySeconds": round3(boundary),
                "gapSeconds": round3(gap),
                "chapterChange": chapter_change,
                "importantBoundary": important,
                "style": style,
                "hasTransitionMetadata": bool(transition),
                "hasBridgeEvidence": bridge,
                "hasTwoSidedMotion": two_sided_motion,
                "landingDurationSeconds": round3(landing_duration),
                "fromClipIndex": left.get("clipIndex"),
                "toClipIndex": right.get("clipIndex"),
                "fromBeat": left.get("beat"),
                "toBeat": right.get("beat"),
                "fromSourceName": left.get("sourceName"),
                "toSourceName": right.get("sourceName"),
                "issues": issues,
            }
        )
    return rows


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
        }
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
            "inputs": {"blueprint": str(blueprint_path), "blueprintExists": blueprint_path.exists(), "blueprintKind": blueprint_kind},
            "summary": {},
            "clipRows": [],
            "boundaryRows": [],
            "checks": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }

    clips = primary_visual_clips(blueprint)
    annotated = [annotate_clip(index, clip) for index, clip in enumerate(clips, start=1)]
    transitions = transition_rows(blueprint)
    boundaries = boundary_rows(annotated, transitions, args)
    blocked = [row for row in boundaries if row.get("status") == "blocked"]
    important = [row for row in boundaries if row.get("importantBoundary")]
    blocked_important = [row for row in important if row.get("status") == "blocked"]
    motion_rows = [row for row in boundaries if row.get("style") in MOTION_STYLES]
    unsupported_motion = [row for row in motion_rows if "motion_effect_without_two_sided_motion_or_bridge_evidence" in row.get("issues", [])]
    unstable_landing = [row for row in boundaries if "high_intensity_transition_without_stable_landing_duration" in row.get("issues", [])]
    payoff_jumps = [row for row in boundaries if "payoff_to_payoff_jump_without_bridge_or_match" in row.get("issues", [])]
    weak_boundaries = [row for row in boundaries if "weak_or_unclassified_clip_at_boundary" in row.get("issues", [])]
    hard_jump = [
        row
        for row in boundaries
        if "important_boundary_lacks_bridge_match_or_breath_reason" in row.get("issues", [])
        or "timeline_gap_without_bridge_or_route_texture" in row.get("issues", [])
    ]
    high_run = high_intensity_run([str(row.get("style") or "") for row in boundaries])
    max_motion_allowed = max(args.max_motion_effects, int(max(len(boundaries), 1) * args.max_motion_share))

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Final candidate blueprint is package-local and has enough adjacent visual boundaries for smoothness proof",
        blueprint_path.exists() and blueprint_inside_package and len(clips) >= args.min_visual_clips and len(boundaries) >= args.min_visual_boundaries,
        {
            "blueprint": str(blueprint_path),
            "blueprintKind": blueprint_kind,
            "blueprintExists": blueprint_path.exists(),
            "blueprintInsidePackage": blueprint_inside_package,
            "visualClipCount": len(clips),
            "visualBoundaryCount": len(boundaries),
        },
    )
    add_check(
        checks,
        "Upstream final-blueprint, transition, scene-flow, and shot-flow reports are accepted",
        all(row["exists"] and row["accepted"] for row in reports.values()),
        {
            name: {"exists": row["exists"], "status": row["status"], "acceptedStatuses": row["acceptedStatuses"], "blockerCount": len(row["blockers"])}
            for name, row in reports.items()
        },
    )
    add_check(
        checks,
        "Important chapter, title, and gap boundaries have final transition metadata plus bridge, match, or breathing reason",
        bool(boundaries) and len(blocked_important) == 0,
        {
            "importantBoundaryCount": len(important),
            "blockedImportantBoundaryCount": len(blocked_important),
            "blockedImportantBoundaries": blocked_important[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Motion accents are rare, evidence-backed, and land on stable primary clips",
        len(motion_rows) <= max_motion_allowed and len(unsupported_motion) == 0 and len(unstable_landing) == 0 and high_run <= 1,
        {
            "motionEffectBoundaryCount": len(motion_rows),
            "maxMotionAllowed": max_motion_allowed,
            "unsupportedMotionEffectCount": len(unsupported_motion),
            "unstableLandingCount": len(unstable_landing),
            "highIntensityRunMax": high_run,
        },
    )
    add_check(
        checks,
        "Final cut has no payoff/title/unknown hard jumps hidden by effects",
        len(payoff_jumps) == 0 and len(hard_jump) == 0 and len(weak_boundaries) == 0,
        {
            "payoffJumpCount": len(payoff_jumps),
            "hardCutJumpCount": len(hard_jump),
            "weakBoundaryClipCount": len(weak_boundaries),
            "examples": (payoff_jumps + hard_jump + weak_boundaries)[: args.max_blocked_rows_in_report],
        },
    )

    blocked_checks = [row for row in checks if row["status"] == "blocked"]
    blockers = [row["name"] for row in blocked_checks]
    blockers.extend(f"boundary {row.get('boundaryIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked[: args.max_blocked_rows_in_report])
    warnings = [warning for report in reports.values() for warning in report["warnings"]]
    summary = {
        "visualClipCount": len(clips),
        "visualBoundaryCount": len(boundaries),
        "importantBoundaryCount": len(important),
        "blockedBoundaryCount": len(blocked),
        "blockedImportantBoundaryCount": len(blocked_important),
        "motionEffectBoundaryCount": len(motion_rows),
        "unsupportedMotionEffectCount": len(unsupported_motion),
        "unstableLandingCount": len(unstable_landing),
        "highIntensityRunMax": high_run,
        "payoffJumpCount": len(payoff_jumps),
        "hardCutJumpCount": len(hard_jump),
        "weakBoundaryClipCount": len(weak_boundaries),
        "transitionMetadataBoundaryCount": sum(1 for row in boundaries if row.get("hasTransitionMetadata")),
        "bridgeEvidenceBoundaryCount": sum(1 for row in boundaries if row.get("hasBridgeEvidence")),
        "finalBlueprintLineageStatus": reports["finalBlueprintLineage"]["status"],
        "transitionBreathingRoomStatus": reports["transitionBreathingRoom"]["status"],
        "sceneFlowArcStatus": reports["sceneFlowArc"]["status"],
        "shotFlowContinuityStatus": reports["shotFlowContinuity"]["status"],
        "transitionVisualMatchStatus": reports["transitionVisualMatch"]["status"],
        "transitionChoreographyStatus": reports["transitionChoreography"]["status"],
        "transitionStoryboardStatus": reports["transitionStoryboard"]["status"],
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
            "maxMotionShare": args.max_motion_share,
        },
        "summary": summary,
        "clipRows": [{k: v for k, v in row.items() if k != "text"} for row in annotated],
        "boundaryRows": boundaries,
        "checks": checks,
        "reports": reports,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "auditsFinalCandidateNotOnlyPlans": True,
            "importantBoundariesNeedBridgeMatchOrBreath": True,
            "motionEffectsNeedEvidenceAndStableLanding": True,
            "blocksPayoffToPayoffHardJumps": True,
            "blocksWeakOrUnknownTransitionLandings": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Final Cut Smoothness Contract Audit",
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
    lines.extend(["", "## Boundaries"])
    for row in (report.get("boundaryRows") or [])[:160]:
        lines.extend(
            [
                "",
                f"### Boundary {row.get('boundaryIndex')}: `{row.get('fromBeat')}` -> `{row.get('toBeat')}`",
                f"- Status: `{row.get('status')}`",
                f"- Style: `{row.get('style')}` metadata=`{row.get('hasTransitionMetadata')}` bridge=`{row.get('hasBridgeEvidence')}`",
                f"- From/To: `{row.get('fromSourceName')}` -> `{row.get('toSourceName')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Check the final candidate blueprint, not only transition plans.",
            "- Important chapter/title/gap boundaries need bridge, match, or breathing-room proof.",
            "- Whip, rotation, speed-ramp, and push/slide accents must be rare and motivated by route motion or bridge evidence.",
            "- Payoff-to-payoff jumps, weak clips, and title/unknown landings are blocked before Resolve apply.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final candidate cut smoothness.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--min-visual-clips", type=int, default=4)
    parser.add_argument("--min-visual-boundaries", type=int, default=3)
    parser.add_argument("--min-landing-seconds", type=float, default=1.8)
    parser.add_argument("--max-motion-share", type=float, default=0.25)
    parser.add_argument("--max-motion-effects", type=int, default=2)
    parser.add_argument("--max-unexplained-gap-seconds", type=float, default=1.0)
    parser.add_argument("--transition-match-tolerance-seconds", type=float, default=1.0)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "final_cut_smoothness_contract_audit.json", report)
    write_markdown(package_dir / "final_cut_smoothness_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
