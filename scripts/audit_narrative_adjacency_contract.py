#!/usr/bin/env python3
"""Audit whether adjacent visual shots have viewer-readable narrative motivation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "shotFlowContinuity": ("shot_flow_continuity_contract_audit.json", {"passed"}),
    "sceneFlowArc": ("scene_flow_arc_contract_audit.json", {"passed"}),
    "finalCutSmoothness": ("final_cut_smoothness_contract_audit.json", {"passed"}),
    "transitionBreathingRoom": ("transition_breathing_room_contract_audit.json", {"passed"}),
    "transitionPairContinuity": ("transition_pair_continuity_contract_audit.json", {"passed"}),
    "transitionMotivation": ("transition_motivation_contract_audit.json", {"passed"}),
    "transitionStoryboard": ("transition_storyboard_contract_audit.json", {"passed"}),
    "transitionContinuityRehearsal": ("transition_continuity_rehearsal_contract_audit.json", {"passed"}),
    "pacingWatchability": ("pacing_watchability_contract_audit.json", {"passed"}),
    "finalBlueprintLineage": ("final_blueprint_lineage_contract_audit.json", {"passed"}),
}

FUNCTION_BEATS = {
    "opening_hook": "context",
    "route_observation": "context",
    "title_bridge": "title",
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

TERM_GROUPS = {
    "title": (
        "title",
        "opening_city",
        "chapter_title",
        "ending_city",
        "cover",
        "hero title",
    ),
    "context": (
        "context",
        "person",
        "people",
        "face",
        "reaction",
        "companion",
        "intro",
        "vlog",
        "family",
        "promise",
        "route observation",
    ),
    "movement": (
        "movement",
        "route",
        "train",
        "station",
        "airport",
        "ferry",
        "taxi",
        "car",
        "bus",
        "metro",
        "subway",
        "road",
        "walking",
        "walk",
        "arrival",
        "departure",
        "transit",
        "luggage",
        "escalator",
        "ticket",
        "bridge",
        "motion",
    ),
    "texture": (
        "texture",
        "street",
        "food",
        "hotel",
        "room",
        "shop",
        "sign",
        "signage",
        "weather",
        "interior",
        "alley",
        "market",
        "crowd",
        "table",
        "waiting",
        "daily",
        "lived",
        "detail",
        "coffee",
    ),
    "payoff": (
        "payoff",
        "landmark",
        "museum",
        "temple",
        "tower",
        "skyline",
        "aerial",
        "drone",
        "scenic",
        "coast",
        "mountain",
        "castle",
        "shrine",
        "bridge view",
        "destination",
        "viewpoint",
        "panorama",
        "harbor",
    ),
    "aftertaste": (
        "aftertaste",
        "quiet",
        "sunset",
        "dusk",
        "night",
        "ending",
        "reflection",
        "calm",
        "breathing",
        "farewell",
        "leaving",
        "callback",
        "final",
    ),
}

ALLOWED_PROGRESSIONS = {
    ("title", "context"),
    ("title", "movement"),
    ("title", "payoff"),
    ("context", "context"),
    ("context", "movement"),
    ("context", "texture"),
    ("context", "payoff"),
    ("movement", "context"),
    ("movement", "movement"),
    ("movement", "texture"),
    ("movement", "payoff"),
    ("texture", "context"),
    ("texture", "movement"),
    ("texture", "texture"),
    ("texture", "payoff"),
    ("texture", "aftertaste"),
    ("payoff", "movement"),
    ("payoff", "texture"),
    ("payoff", "aftertaste"),
    ("aftertaste", "title"),
    ("aftertaste", "context"),
    ("aftertaste", "movement"),
    ("aftertaste", "aftertaste"),
}

BRIDGE_TERMS = (
    "transition",
    "bridge",
    "match",
    "dissolve",
    "whip",
    "rotation",
    "speed",
    "ramp",
    "bgm",
    "phrase",
    "hit",
    "marker",
    "storyboard",
    "route",
    "scenearc",
    "scene arc",
    "sensory",
    "actionanchor",
    "action anchor",
    "landing",
    "handoff",
)
GENERIC_TERMS = ("generic", "placeholder", "black", "slate", "test", "sample", "duplicate", "weak", "utility")


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


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def compact_json(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def clip_text(clip: dict[str, Any]) -> str:
    keys = (
        "role",
        "purpose",
        "place",
        "city",
        "country",
        "chapter",
        "titleText",
        "subtitle",
        "sourcePath",
        "sourceName",
        "name",
        "notes",
        "creatorFunction",
        "editorialTier",
        "selectionTier",
    )
    return " ".join(str(clip.get(key) or "") for key in keys).lower()


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


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    out = [row for row in rows if isinstance(row, dict)]
    if out:
        return out
    candidates = blueprint.get("transitionPolishCandidates") if isinstance(blueprint.get("transitionPolishCandidates"), list) else []
    return [
        {
            "rowIndex": item.get("rowIndex"),
            "boundarySeconds": item.get("boundarySeconds"),
            "fromSourcePath": item.get("fromSourcePath"),
            "toSourcePath": item.get("toSourcePath"),
            "transitionPolishCandidate": item,
        }
        for item in candidates
        if isinstance(item, dict)
    ]


def transition_boundary(row: dict[str, Any]) -> float | None:
    candidate = row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds"):
        value = as_float(row.get(key))
        if value is not None:
            return value
    return as_float(candidate.get("boundarySeconds"))


def pair_matches(boundary: dict[str, Any], transition: dict[str, Any]) -> bool:
    candidate = transition.get("transitionPolishCandidate") if isinstance(transition.get("transitionPolishCandidate"), dict) else {}
    payload = candidate.get("pairContinuity") if isinstance(candidate.get("pairContinuity"), dict) else {}
    from_transition = source_name(transition.get("fromSourcePath") or payload.get("fromSourcePath"))
    to_transition = source_name(transition.get("toSourcePath") or payload.get("toSourcePath"))
    return bool(
        (not from_transition or from_transition == boundary.get("fromSourceName"))
        and (not to_transition or to_transition == boundary.get("toSourceName"))
    )


def nearest_transition(boundary: dict[str, Any], rows: list[dict[str, Any]], *, tolerance: float) -> dict[str, Any] | None:
    exact = [row for row in rows if row.get("rowIndex") == boundary.get("boundaryIndex")]
    if exact:
        return exact[0]
    candidates: list[tuple[float, dict[str, Any]]] = []
    boundary_seconds = float(boundary.get("boundarySeconds") or 0.0)
    for row in rows:
        if not pair_matches(boundary, row):
            continue
        value = transition_boundary(row)
        if value is None:
            candidates.append((0.0, row))
            continue
        distance = abs(value - boundary_seconds)
        if distance <= tolerance:
            candidates.append((distance, row))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def classify_function(clip: dict[str, Any]) -> tuple[str, list[str]]:
    text = clip_text(clip)
    groups: set[str] = set()
    function = str(clip.get("creatorFunction") or "")
    if function in FUNCTION_BEATS:
        groups.add(FUNCTION_BEATS[function])
    for group, terms in TERM_GROUPS.items():
        if any(term in text for term in terms):
            groups.add(group)
    if "title" in groups and not ({"movement", "texture", "payoff", "aftertaste"} & groups):
        return "title", sorted(groups)
    if not groups:
        return "unknown", []
    for group in ("aftertaste", "movement", "texture", "payoff", "context", "title"):
        if group in groups:
            return group, sorted(groups)
    return "unknown", sorted(groups)


def normalize_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text or text in {"none", "null", "unassigned", "unknown", "n/a"}:
        return ""
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except ValueError:
        pass
    return text


def transition_text(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    candidate = row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}
    pieces: list[str] = []
    for payload in (row, candidate):
        if not isinstance(payload, dict):
            continue
        for key in (
            "approvedTransitionType",
            "resolveEffectName",
            "trackOperation",
            "motionStyle",
            "audioPolicy",
            "subtitlePolicy",
            "titleZonePolicy",
            "pairContinuity",
            "transitionMotivation",
            "selectedRecipe",
            "bgmSync",
            "storyboard",
            "choreography",
            "sceneArc",
            "visualMatch",
            "sensoryContinuity",
            "actionAnchor",
        ):
            pieces.append(compact_json(payload.get(key)))
    return " ".join(pieces).lower()


def boundary_category(left: dict[str, Any], right: dict[str, Any]) -> str:
    text = f"{clip_text(left)} {clip_text(right)}"
    if "title" in text or "opening_city" in text or "chapter_title" in text:
        return "title_boundary"
    if "ending" in text or "aftertaste" in text:
        return "ending_or_aftertaste_boundary"
    if normalize_value(left.get("chapterIndex")) and normalize_value(right.get("chapterIndex")) and normalize_value(left.get("chapterIndex")) != normalize_value(right.get("chapterIndex")):
        return "chapter_boundary"
    if timeline_start(right) - timeline_end(left) > 0.2:
        return "timeline_gap"
    return "same_chapter_cut"


def annotate_clip(index: int, clip: dict[str, Any]) -> dict[str, Any]:
    function, groups = classify_function(clip)
    text = clip_text(clip)
    return {
        "clipIndex": index,
        "sourcePath": clip.get("sourcePath"),
        "sourceName": source_name(clip.get("sourcePath") or clip.get("sourceName")),
        "timelineStartSeconds": round3(timeline_start(clip)),
        "timelineEndSeconds": round3(timeline_end(clip)),
        "durationSeconds": round3(max(0.0, timeline_end(clip) - timeline_start(clip))),
        "chapterIndex": normalize_value(clip.get("chapterIndex")),
        "city": normalize_value(clip.get("city")),
        "place": normalize_value(clip.get("place")),
        "role": clip.get("role"),
        "purpose": clip.get("purpose"),
        "creatorFunction": clip.get("creatorFunction"),
        "narrativeFunction": function,
        "functionGroups": groups,
        "isGenericOrWeak": any(term in text for term in GENERIC_TERMS),
    }


def run_length(values: list[str]) -> int:
    best = 0
    current = ""
    length = 0
    for value in values:
        if value == current:
            length += 1
        else:
            current = value
            length = 1
        best = max(best, length)
    return best


def pair_reasons(left: dict[str, Any], right: dict[str, Any], transition: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    t_text = transition_text(transition)
    left_function = str(left.get("narrativeFunction") or "unknown")
    right_function = str(right.get("narrativeFunction") or "unknown")
    if (left_function, right_function) in ALLOWED_PROGRESSIONS:
        reasons.append("story_function_progression")
    if left.get("chapterIndex") and left.get("chapterIndex") == right.get("chapterIndex") and (
        (left.get("place") and left.get("place") == right.get("place")) or (left.get("city") and left.get("city") == right.get("city"))
    ):
        reasons.append("same_chapter_place_continuity")
    if left.get("sourceName") and left.get("sourceName") == right.get("sourceName"):
        reasons.append("same_source_trim_continuity")
    if left_function == "movement" or right_function == "movement":
        reasons.append("route_or_movement_handoff")
    if left_function == "aftertaste" or right_function == "aftertaste":
        reasons.append("aftertaste_or_breathing_handoff")
    if left_function == "title" or right_function == "title":
        reasons.append("title_handoff")
    if any(term in t_text for term in BRIDGE_TERMS):
        reasons.append("explicit_transition_bridge_or_bgm_metadata")
    if transition and pair_matches(
        {
            "fromSourceName": left.get("sourceName"),
            "toSourceName": right.get("sourceName"),
        },
        transition,
    ):
        reasons.append("transition_pair_matches_actual_adjacent_shots")
    return sorted(set(reasons))


def audit_pair(index: int, left: dict[str, Any], right: dict[str, Any], transition: dict[str, Any] | None) -> dict[str, Any]:
    reasons = pair_reasons(left, right, transition)
    left_function = str(left.get("narrativeFunction") or "unknown")
    right_function = str(right.get("narrativeFunction") or "unknown")
    category = boundary_category(left, right)
    issues: list[str] = []
    if not reasons:
        issues.append("adjacent_pair_has_no_viewer_readable_reason")
    if left_function == "unknown" or right_function == "unknown":
        issues.append("adjacent_pair_contains_unknown_story_function")
    if left.get("isGenericOrWeak") or right.get("isGenericOrWeak"):
        issues.append("adjacent_pair_contains_generic_or_weak_clip")
    if left_function == "payoff" and right_function == "payoff" and not (
        {"route_or_movement_handoff", "aftertaste_or_breathing_handoff", "explicit_transition_bridge_or_bgm_metadata"} & set(reasons)
    ):
        issues.append("payoff_to_payoff_jump_without_bridge_movement_or_breath")
    if category in {"chapter_boundary", "timeline_gap"} and not (
        {"route_or_movement_handoff", "aftertaste_or_breathing_handoff", "title_handoff", "explicit_transition_bridge_or_bgm_metadata"} & set(reasons)
    ):
        issues.append("chapter_or_timeline_handoff_lacks_route_title_bridge_or_aftertaste")
    return {
        "pairIndex": index,
        "status": "passed" if not issues else "blocked",
        "category": category,
        "boundarySeconds": round3(float(left.get("timelineEndSeconds") or 0.0)),
        "fromSourceName": left.get("sourceName"),
        "toSourceName": right.get("sourceName"),
        "fromFunction": left_function,
        "toFunction": right_function,
        "fromChapterIndex": left.get("chapterIndex"),
        "toChapterIndex": right.get("chapterIndex"),
        "transitionRowIndex": transition.get("rowIndex") if transition else None,
        "reasons": reasons,
        "issues": issues,
    }


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
            "inputs": {
                "blueprint": str(blueprint_path),
                "blueprintExists": blueprint_path.exists(),
                "blueprintKind": blueprint_kind,
                "blueprintInsidePackage": blueprint_inside_package,
            },
            "summary": {},
            "clipRows": [],
            "adjacencyRows": [],
            "checks": [],
            "reports": reports,
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "policy": {},
            "safety": safety(),
        }

    clips = primary_visual_clips(blueprint)
    annotated = [annotate_clip(index, clip) for index, clip in enumerate(clips, start=1)]
    transitions = transition_rows(blueprint)
    boundaries = []
    for index, (left, right) in enumerate(zip(annotated, annotated[1:]), start=1):
        boundary = {
            "boundaryIndex": index,
            "boundarySeconds": left.get("timelineEndSeconds"),
            "fromSourceName": left.get("sourceName"),
            "toSourceName": right.get("sourceName"),
        }
        boundaries.append(audit_pair(index, left, right, nearest_transition(boundary, transitions, tolerance=args.tolerance_seconds)))

    blocked_rows = [row for row in boundaries if row.get("status") == "blocked"]
    unknown_count = sum(1 for row in annotated if row.get("narrativeFunction") == "unknown")
    unknown_ratio = round3(unknown_count / len(annotated)) if annotated else 1.0
    unmotivated_count = sum(1 for row in boundaries if "adjacent_pair_has_no_viewer_readable_reason" in (row.get("issues") or []))
    unmotivated_ratio = round3(unmotivated_count / len(boundaries)) if boundaries else 0.0
    chapter_handoffs = [row for row in boundaries if row.get("category") in {"chapter_boundary", "timeline_gap"}]
    blocked_chapter_handoffs = [
        row for row in chapter_handoffs if "chapter_or_timeline_handoff_lacks_route_title_bridge_or_aftertaste" in (row.get("issues") or [])
    ]
    payoff_jump_count = sum(
        1 for row in boundaries if "payoff_to_payoff_jump_without_bridge_movement_or_breath" in (row.get("issues") or [])
    )
    generic_pair_count = sum(1 for row in boundaries if "adjacent_pair_contains_generic_or_weak_clip" in (row.get("issues") or []))
    function_run_max = run_length([str(row.get("narrativeFunction") or "unknown") for row in annotated])

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Final candidate blueprint is inside the package and has enough adjacent visual shots",
        blueprint_path.exists() and blueprint_inside_package and len(annotated) >= args.min_visual_clips and len(boundaries) >= 1,
        {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "visualClipCount": len(annotated),
            "adjacentPairCount": len(boundaries),
            "minVisualClips": args.min_visual_clips,
        },
    )
    add_check(
        checks,
        "Upstream shot-flow, scene-flow, smoothness, transition, pacing, and lineage reports are accepted",
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
        "Every adjacent visual pair has a viewer-readable narrative reason",
        unmotivated_count <= args.max_unmotivated_pairs and unmotivated_ratio <= args.max_unmotivated_ratio and not blocked_rows,
        {
            "adjacentPairCount": len(boundaries),
            "blockedPairCount": len(blocked_rows),
            "unmotivatedPairCount": unmotivated_count,
            "unmotivatedRatio": unmotivated_ratio,
            "maxUnmotivatedPairs": args.max_unmotivated_pairs,
            "maxUnmotivatedRatio": args.max_unmotivated_ratio,
            "blockedRows": blocked_rows[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Chapter and timeline handoffs carry route, title, bridge, or aftertaste context",
        not blocked_chapter_handoffs,
        {
            "chapterHandoffCount": len(chapter_handoffs),
            "blockedChapterHandoffCount": len(blocked_chapter_handoffs),
            "blockedChapterHandoffs": blocked_chapter_handoffs[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "The final sequence avoids payoff stacks, weak generic adjacency, and opaque clip functions",
        payoff_jump_count == 0
        and generic_pair_count == 0
        and unknown_ratio <= args.max_unknown_function_ratio
        and function_run_max <= args.max_function_run,
        {
            "payoffJumpWithoutBridgeCount": payoff_jump_count,
            "genericPairCount": generic_pair_count,
            "unknownFunctionClipCount": unknown_count,
            "unknownFunctionRatio": unknown_ratio,
            "maxUnknownFunctionRatio": args.max_unknown_function_ratio,
            "functionRunMax": function_run_max,
            "maxFunctionRun": args.max_function_run,
        },
    )

    blocked_checks = [row for row in checks if row["status"] == "blocked"]
    blockers = [row["name"] for row in blocked_checks]
    blockers.extend(f"pair {row.get('pairIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[: args.max_blocked_rows_in_report])
    warnings = [warning for report in reports.values() for warning in report["warnings"]]
    summary = {
        "visualClipCount": len(annotated),
        "adjacentPairCount": len(boundaries),
        "motivatedPairCount": len(boundaries) - unmotivated_count,
        "unmotivatedPairCount": unmotivated_count,
        "unmotivatedRatio": unmotivated_ratio,
        "blockedPairCount": len(blocked_rows),
        "chapterHandoffCount": len(chapter_handoffs),
        "blockedChapterHandoffCount": len(blocked_chapter_handoffs),
        "payoffJumpWithoutBridgeCount": payoff_jump_count,
        "genericPairCount": generic_pair_count,
        "unknownFunctionClipCount": unknown_count,
        "unknownFunctionRatio": unknown_ratio,
        "functionRunMax": function_run_max,
        "shotFlowContinuityStatus": reports["shotFlowContinuity"]["status"],
        "sceneFlowArcStatus": reports["sceneFlowArc"]["status"],
        "finalCutSmoothnessStatus": reports["finalCutSmoothness"]["status"],
        "transitionBreathingRoomStatus": reports["transitionBreathingRoom"]["status"],
        "transitionPairContinuityStatus": reports["transitionPairContinuity"]["status"],
        "transitionMotivationStatus": reports["transitionMotivation"]["status"],
        "transitionStoryboardStatus": reports["transitionStoryboard"]["status"],
        "transitionContinuityRehearsalStatus": reports["transitionContinuityRehearsal"]["status"],
        "pacingWatchabilityStatus": reports["pacingWatchability"]["status"],
        "finalBlueprintLineageStatus": reports["finalBlueprintLineage"]["status"],
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
            "toleranceSeconds": args.tolerance_seconds,
        },
        "summary": summary,
        "clipRows": annotated,
        "adjacencyRows": boundaries,
        "checks": checks,
        "reports": reports,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "requiresNarrativeReasonForEveryAdjacentPair": True,
            "blocksRandomShotStacking": True,
            "blocksPayoffToPayoffWithoutBridge": True,
            "blocksChapterHandoffWithoutRouteTitleBridgeOrAftertaste": True,
            "allowsMotionOnlyWhenPairContinuityAndTransitionMotivationAlreadyPassed": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Narrative Adjacency Contract Audit",
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
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Adjacency Rows"])
    for row in (report.get("adjacencyRows") or [])[:160]:
        lines.extend(
            [
                "",
                f"### Pair {row.get('pairIndex')}: {row.get('fromFunction')} -> {row.get('toFunction')}",
                f"- Status: `{row.get('status')}`",
                f"- Category: `{row.get('category')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Reasons: `{', '.join(row.get('reasons') or [])}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(["", f"### {row.get('name')}", f"- Status: `{row.get('status')}`"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit narrative motivation for adjacent final-candidate visual shots.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--tolerance-seconds", type=float, default=0.75)
    parser.add_argument("--min-visual-clips", type=int, default=3)
    parser.add_argument("--max-unmotivated-pairs", type=int, default=0)
    parser.add_argument("--max-unmotivated-ratio", type=float, default=0.08)
    parser.add_argument("--max-unknown-function-ratio", type=float, default=0.25)
    parser.add_argument("--max-function-run", type=int, default=4)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "narrative_adjacency_contract_audit.json", report)
    write_markdown(package_dir / "narrative_adjacency_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
