#!/usr/bin/env python3
"""Materialize transition execution rows into a non-destructive Resolve blueprint candidate."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint": "",
    "approvedTransitionRows": "",
    "resolveImplementation": "",
    "preflightEvidence": "",
    "timelineReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

FORBIDDEN_TERMS = (
    "random spin",
    "glitch",
    "flash",
    "shake",
    "strobe",
    "template",
    "particle",
    "whoosh pack",
)


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: Any) -> None:
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


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def is_video_clip(clip: dict[str, Any]) -> bool:
    track_type = str(clip.get("trackType") or "video").lower()
    return track_type in {"", "video"} and int(as_float(clip.get("mediaType"), 1) or 1) == 1


def blueprint_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def row_source_keys(clip: dict[str, Any]) -> set[str]:
    keys = set()
    for value in (clip.get("sourcePath"), clip.get("sourceName")):
        text = str(value or "")
        if text:
            keys.add(text)
            keys.add(source_name(text))
    return {key for key in keys if key}


def boundary_seconds(row: dict[str, Any]) -> float:
    explicit = as_float(row.get("timelineStartSeconds"))
    if explicit is not None:
        return explicit
    from_clip = row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}
    to_clip = row.get("toClip") if isinstance(row.get("toClip"), dict) else {}
    left = timeline_end(from_clip)
    right = timeline_start(to_clip)
    if left or right:
        return (left + right) / 2.0
    return 0.0


def candidate_source_path(row_clip: dict[str, Any]) -> str:
    return str(row_clip.get("sourcePath") or row_clip.get("sourceName") or "")


def select_clip_index(clips: list[dict[str, Any]], row_clip: dict[str, Any], boundary: float, *, side: str) -> int | None:
    keys = row_source_keys(row_clip)
    scored: list[tuple[tuple[float, float, int], int]] = []
    for index, clip in enumerate(clips):
        if not is_video_clip(clip):
            continue
        clip_keys = row_source_keys(clip)
        if keys and not (keys & clip_keys):
            continue
        if side == "from":
            edge = timeline_end(clip)
            side_penalty = 0.0 if edge <= boundary + 0.75 else 10_000.0
        else:
            edge = timeline_start(clip)
            side_penalty = 0.0 if edge >= boundary - 0.75 else 10_000.0
        scored.append(((side_penalty, abs(edge - boundary), float(index)), index))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    return scored[0][1]


def reference_selection_plan(package_dir: Path) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    path = package_dir / "transition_reference_selection" / "transition_reference_selection.json"
    data = load_json(path) or {}
    rows = data.get("selectionRows") if isinstance(data.get("selectionRows"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = as_int(row.get("rowIndex"), -1)
        if index >= 0:
            out[index] = row
    return data, out


def transition_choreography_plan(package_dir: Path) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    path = package_dir / "transition_choreography_plan" / "transition_choreography_plan.json"
    data = load_json(path) or {}
    rows = data.get("choreographyRows") if isinstance(data.get("choreographyRows"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = as_int(row.get("rowIndex"), -1)
        if index >= 0:
            out[index] = row
    return data, out


def selected_candidate(selection_row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(selection_row, dict):
        return {}
    candidate = selection_row.get("selectedCandidate")
    return candidate if isinstance(candidate, dict) else {}


def selection_decision(selection_row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(selection_row, dict):
        return {}
    decision = selection_row.get("autoDecision")
    return decision if isinstance(decision, dict) else {}


def resolve_effect_from_selection(candidate: dict[str, Any], fallback: Any) -> str:
    family = str(candidate.get("styleFamily") or "").lower()
    candidate_type = str(candidate.get("candidateType") or "").lower()
    if family in {"clean_cut", "visual_match", "physical_bridge"}:
        return "Cut"
    if family == "title_breath":
        return "Opacity/Scale Title Breath"
    if family == "mood_dissolve" or "dissolve" in candidate_type:
        return "Cross Dissolve"
    if family == "motion_accent":
        if "rotation" in candidate_type:
            return "Transform Rotation Match"
        if "whip" in candidate_type:
            return "Transform Whip Pan"
        if "speed" in candidate_type or "ramp" in candidate_type:
            return "Speed Ramp"
        return "Restrained Transform Motion"
    return str(fallback or "")


def derived_choreography_family(row: dict[str, Any], selected: dict[str, Any]) -> str:
    category = str(row.get("boundaryCategory") or "")
    family = str(selected.get("styleFamily") or "")
    candidate_type = str(selected.get("candidateType") or "").lower()
    if category == "title_boundary" or family == "title_breath":
        return "scenic_title_breath"
    if category == "ending_transition":
        return "ending_aftertaste_hold"
    if family == "physical_bridge":
        return "route_bridge_triptych"
    if family == "visual_match":
        return "visual_match_cut"
    if family == "mood_dissolve":
        return "mood_dissolve_breath"
    if family == "motion_accent" or any(term in candidate_type for term in ("whip", "rotation", "speed", "ramp", "push")):
        return "motivated_motion_accent"
    if category in {"chapter_boundary", "timeline_gap"}:
        return "texture_bridge_cutaway"
    return "clean_continuity_cut"


def derived_source_style(selected: dict[str, Any]) -> str:
    text = " ".join(str(selected.get(key) or "").lower() for key in ("candidateType", "resolveRecipe", "ffmpegPreviewHint"))
    if "whip" in text:
        return "whip_pan"
    if "rotation" in text or "rotate" in text:
        return "rotation"
    if "speed" in text or "ramp" in text:
        return "speed_ramp"
    if "push" in text or "slide" in text:
        return "push_slide"
    if "dissolve" in text:
        return "dissolve"
    if "match" in text:
        return "match_cut"
    if "bridge" in text:
        return "bridge_insert"
    return "clean_cut"


def default_three_beats(row: dict[str, Any], family: str, intensity: int) -> list[dict[str, Any]]:
    outgoing = source_name(candidate_source_path(row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}))
    landing = source_name(candidate_source_path(row.get("toClip") if isinstance(row.get("toClip"), dict) else {}))
    bridge_action = {
        "route_bridge_triptych": "insert 1-3 short route texture shots before the location/day handoff",
        "scenic_title_breath": "hold the title-safe scenic frame, suppress subtitles, then hand off on a clean BGM phrase",
        "ending_aftertaste_hold": "slow down into an aftertaste hold without new route information or decorative motion",
        "visual_match_cut": "cut on shared shape, direction, color, object, water, road, skyline, sign, food, or gesture",
        "mood_dissolve_breath": "use a short mood/time/weather dissolve that breathes with the BGM phrase",
        "motivated_motion_accent": "use one restrained motion accent only on real source motion or verified bridge footage",
        "texture_bridge_cutaway": "insert one lived-in texture beat before landing",
    }.get(family, "keep the cut invisible unless stronger bridge or motion evidence exists")
    return [
        {
            "role": "outgoing",
            "durationFrames": 10 if intensity else 6,
            "action": f"leave on a readable last action or scenic edge from {outgoing or 'the outgoing shot'}",
        },
        {
            "role": "bridge_or_motion",
            "durationFrames": 12 + max(0, intensity) * 4,
            "action": bridge_action,
        },
        {
            "role": "landing",
            "durationFrames": 10 if family in {"scenic_title_breath", "ending_aftertaste_hold"} else 6,
            "action": f"land on a stable first readable moment from {landing or 'the landing shot'} and hold long enough for orientation",
        },
    ]


def resolve_keyframe_recipe(family: str, style: str, intensity: int, duration_frames: int) -> dict[str, Any]:
    duration = max(as_int(duration_frames, 0), 1)
    half = max(1, duration // 2)
    subtle = max(1, min(3, intensity + 1))
    if family in {"scenic_title_breath", "ending_aftertaste_hold"}:
        transform = [
            {"frame": 0, "opacity": 0.92, "scale": 1.0},
            {"frame": duration, "opacity": 1.0, "scale": 1.015},
        ]
        effect = "opacity_scale_breath"
    elif style == "rotation":
        transform = [
            {"frame": 0, "rotationDegrees": -subtle, "scale": 1.02, "motionBlur": "low"},
            {"frame": half, "rotationDegrees": 0, "scale": 1.04, "motionBlur": "low"},
            {"frame": duration, "rotationDegrees": subtle, "scale": 1.02, "motionBlur": "low"},
        ]
        effect = "restrained_rotation_match"
    elif style == "whip_pan":
        transform = [
            {"frame": 0, "translateXPercent": -8 * subtle, "scale": 1.04, "directionalBlur": "medium"},
            {"frame": half, "translateXPercent": 0, "scale": 1.06, "directionalBlur": "medium"},
            {"frame": duration, "translateXPercent": 8 * subtle, "scale": 1.04, "directionalBlur": "medium"},
        ]
        effect = "restrained_whip_pan"
    elif style == "speed_ramp":
        transform = [
            {"frame": 0, "retime": "100%"},
            {"frame": max(1, half - 2), "retime": "135%"},
            {"frame": duration, "retime": "100%"},
        ]
        effect = "short_speed_ramp"
    elif style == "push_slide":
        transform = [
            {"frame": 0, "translateXPercent": -5 * subtle, "scale": 1.02},
            {"frame": duration, "translateXPercent": 0, "scale": 1.0},
        ]
        effect = "soft_push_slide"
    elif family == "mood_dissolve_breath":
        transform = [
            {"frame": 0, "opacity": 0.0},
            {"frame": duration, "opacity": 1.0},
        ]
        effect = "short_mood_dissolve"
    else:
        transform = [{"frame": 0, "cut": True}, {"frame": duration, "holdLandingFrames": 6}]
        effect = "clean_cut_or_match"
    return {
        "effect": effect,
        "durationFrames": duration,
        "transformKeyframes": transform,
        "retimePolicy": "short_phrase_only" if style == "speed_ramp" else "none",
        "audioKeyframes": [
            {"frame": 0, "a1a2SourceAudioDb": "-inf", "a3BgmDb": -18},
            {"frame": half, "a1a2SourceAudioDb": "-inf", "a3BgmDb": -15},
            {"frame": duration, "a1a2SourceAudioDb": "-inf", "a3BgmDb": -18},
        ],
    }


def beat_frames(beats: list[dict[str, Any]], role: str, fallback: int) -> int:
    for beat in beats:
        if isinstance(beat, dict) and beat.get("role") == role:
            return max(0, as_int(beat.get("durationFrames"), fallback))
    return fallback


def cutpoint_plan(
    row: dict[str, Any],
    *,
    fps: float,
    boundary: float,
    duration_frames: int,
    recipe: dict[str, Any],
    motion_execution: dict[str, Any],
    bridge_satisfied: bool,
) -> dict[str, Any]:
    family = str(motion_execution.get("choreographyFamily") or "")
    style = str(motion_execution.get("sourceTransitionStyle") or "")
    category = str(row.get("boundaryCategory") or "")
    important = category in {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
    beats = motion_execution.get("threeBeatChoreography") if isinstance(motion_execution.get("threeBeatChoreography"), list) else []
    bgm = motion_execution.get("bgmChoreography") if isinstance(motion_execution.get("bgmChoreography"), dict) else {}
    caption = motion_execution.get("captionAndTitlePolicy") if isinstance(motion_execution.get("captionAndTitlePolicy"), dict) else {}
    outgoing_tail = beat_frames(beats, "outgoing", 10 if important else 6)
    bridge_or_effect = beat_frames(beats, "bridge_or_motion", max(8, duration_frames))
    landing_hold = beat_frames(beats, "landing", 10 if important else 6)
    needed_handles = 0 if duration_frames <= 0 else max(2, duration_frames // 2)
    pre_roll = as_int(recipe.get("preRollFrames"), 0)
    post_roll = as_int(recipe.get("postRollFrames"), 0)
    quiet_before = round(as_float(caption.get("quietZoneBeforeSeconds"), 0.0) * fps)
    quiet_after = round(as_float(caption.get("quietZoneAfterSeconds"), 0.0) * fps)
    tolerance_frames = round(as_float(bgm.get("hitToleranceSeconds"), 0.35) * fps)
    bgm_offset = 0 if bgm.get("target") == "cut_or_effect_on_bgm_phrase_hit" and bgm.get("allowOffPhrase") is False else tolerance_frames + 1
    clean_family = family in {"clean_continuity_cut", "visual_match_cut", "mood_dissolve_breath"}
    important_resolved = (not important) or bridge_satisfied or family in {"route_bridge_triptych", "scenic_title_breath", "ending_aftertaste_hold", "visual_match_cut", "texture_bridge_cutaway"}
    issues: list[str] = []
    if outgoing_tail < 6:
        issues.append("outgoing_tail_too_short")
    if not clean_family and bridge_or_effect < max(6, min(duration_frames, 8)):
        issues.append("bridge_or_effect_hit_too_short")
    if landing_hold < (10 if important else 6):
        issues.append("landing_hold_too_short")
    if needed_handles and (pre_roll < needed_handles or post_roll < needed_handles):
        issues.append("insufficient_pre_post_roll_for_cutpoint")
    if abs(bgm_offset) > max(0, tolerance_frames):
        issues.append("bgm_hit_offset_outside_tolerance")
    if quiet_before < round(0.25 * fps) or quiet_after < round(0.25 * fps):
        issues.append("subtitle_quiet_zone_too_short")
    if caption.get("avoidTitleCollision") is not True:
        issues.append("title_collision_policy_missing")
    if not motion_execution.get("safetyChecks", {}).get("bgmOnlyNoSourceVoice", False):
        issues.append("source_audio_not_muted_for_transition")
    if not important_resolved:
        issues.append("important_boundary_has_no_bridge_match_or_breath_resolution")
    return {
        "status": "ready_with_transition_cutpoint_plan" if not issues else "needs_transition_cutpoint_repair",
        "boundarySeconds": round3(boundary),
        "boundaryFrame": round(boundary * fps),
        "durationFrames": duration_frames,
        "fps": fps,
        "outgoingTailFrames": outgoing_tail,
        "bridgeOrEffectFrames": bridge_or_effect,
        "landingHoldFrames": landing_hold,
        "preRollFramesAvailable": pre_roll,
        "postRollFramesAvailable": post_roll,
        "sourceHandleFramesNeeded": needed_handles,
        "handlesReady": needed_handles == 0 or (pre_roll >= needed_handles and post_roll >= needed_handles),
        "bgmHitFrameOffset": bgm_offset,
        "bgmHitToleranceFrames": tolerance_frames,
        "bgmHitAligned": abs(bgm_offset) <= max(0, tolerance_frames),
        "subtitleQuietBeforeFrames": quiet_before,
        "subtitleQuietAfterFrames": quiet_after,
        "titleSubtitleQuietZoneReady": quiet_before >= round(0.25 * fps) and quiet_after >= round(0.25 * fps) and caption.get("avoidTitleCollision") is True,
        "bgmOnlyNoSourceVoice": motion_execution.get("safetyChecks", {}).get("bgmOnlyNoSourceVoice", False),
        "importantBoundary": important,
        "importantBoundaryResolved": important_resolved,
        "cutpointRoles": {
            "outgoing": "exit on readable action, scenic edge, gesture, or route cue before the effect",
            "bridgeOrEffect": "place the bridge, match, dissolve, or restrained motion exactly on the BGM phrase hit",
            "landing": "hold the first readable landing moment before the next idea, title, or subtitle",
        },
        "issues": issues,
    }


def motion_execution_payload(
    row: dict[str, Any],
    *,
    selected: dict[str, Any],
    choreography_row: dict[str, Any] | None,
    duration_frames: int,
) -> dict[str, Any]:
    if isinstance(choreography_row, dict) and choreography_row:
        family = str(choreography_row.get("choreographyFamily") or derived_choreography_family(row, selected))
        style = str(choreography_row.get("sourceTransitionStyle") or derived_source_style(selected))
        intensity = as_int(choreography_row.get("intensity"), as_int(selected.get("intensity"), 0))
        beats = choreography_row.get("threeBeatChoreography") if isinstance(choreography_row.get("threeBeatChoreography"), list) else []
        bgm = choreography_row.get("bgmChoreography") if isinstance(choreography_row.get("bgmChoreography"), dict) else {}
        caption = choreography_row.get("captionAndTitlePolicy") if isinstance(choreography_row.get("captionAndTitlePolicy"), dict) else {}
        direction = choreography_row.get("motionDirectionPlan") if isinstance(choreography_row.get("motionDirectionPlan"), dict) else {}
        source = "transition_choreography_plan"
        status = str(choreography_row.get("status") or "")
    else:
        family = derived_choreography_family(row, selected)
        style = derived_source_style(selected)
        intensity = as_int(selected.get("intensity"), 0)
        beats = default_three_beats(row, family, intensity)
        bgm = {"target": "cut_or_effect_on_bgm_phrase_hit", "hitToleranceSeconds": 0.35, "allowOffPhrase": False}
        caption = {
            "quietZoneBeforeSeconds": 0.35,
            "quietZoneAfterSeconds": 0.35,
            "avoidTitleCollision": True,
            "suppressSubtitlesDuringHeroTitleOrFastMotion": True,
        }
        direction = {
            "required": style in {"whip_pan", "rotation", "speed_ramp", "push_slide"},
            "status": "needs_motion_direction_repair" if style in {"whip_pan", "rotation", "speed_ramp", "push_slide"} else "ready_with_motion_direction_plan",
            "effectDirection": "",
            "landingDirection": "",
            "directionMatch": style not in {"whip_pan", "rotation", "speed_ramp", "push_slide"},
            "directionConfidence": 0.0,
        }
        source = "derived_from_reference_selection"
        status = "ready_with_derived_transition_motion_execution"
    return {
        "status": "ready_with_transition_motion_execution" if status in {"ready_with_transition_choreography", "ready_with_derived_transition_motion_execution"} else "needs_transition_motion_execution_repair",
        "source": source,
        "choreographyFamily": family,
        "sourceTransitionStyle": style,
        "intensity": intensity,
        "threeBeatChoreography": beats,
        "bgmChoreography": bgm,
        "captionAndTitlePolicy": caption,
        "motionDirectionPlan": direction,
        "resolveKeyframeRecipe": resolve_keyframe_recipe(family, style, intensity, duration_frames),
        "safetyChecks": {
            "requiresBgmHit": True,
            "requiresCaptionQuietZone": True,
            "titleSafe": bool(caption.get("avoidTitleCollision", True)),
            "bgmOnlyNoSourceVoice": True,
            "forbidTemplateMotion": True,
            "rotationSubtleOnly": style != "rotation" or intensity <= 1,
            "directionMatched": direction.get("directionMatch") is True,
        },
    }


def forbidden_hits(row: dict[str, Any], selection_row: dict[str, Any] | None = None) -> list[str]:
    upstream = row.get("forbiddenRecipeHits") if isinstance(row.get("forbiddenRecipeHits"), list) else []
    if upstream:
        return [str(item) for item in upstream if str(item).strip()]
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    candidate = selected_candidate(selection_row)
    auto_decision = selection_decision(selection_row)
    selected_fields = {
        "resolveEffectName": recipe.get("resolveEffectName"),
        "trackOperation": recipe.get("trackOperation"),
        "style": recipe.get("style"),
        "approvedTransitionType": decision.get("approvedTransitionType"),
        "approvedResolveEffectName": decision.get("approvedResolveEffectName"),
        "selectedCandidateType": candidate.get("candidateType"),
        "selectedStyleFamily": candidate.get("styleFamily"),
        "selectedResolveRecipe": candidate.get("resolveRecipe"),
        "selectedResolveImplementation": auto_decision.get("resolveImplementation"),
    }
    text = json.dumps(selected_fields, ensure_ascii=False).lower()
    return [term for term in FORBIDDEN_TERMS if term in text]


def bridge_row_indices(package_dir: Path) -> set[int]:
    report = load_json(package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json") or {}
    rows = report.get("materializedRows") if isinstance(report.get("materializedRows"), list) else []
    out: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "materialized" and int(row.get("insertedBeatCount") or 0) > 0:
            out.add(as_int(row.get("rowIndex"), -1))
    return {value for value in out if value >= 0}


def choose_base_blueprint(package_dir: Path) -> tuple[dict[str, Any] | None, Path, str]:
    bridge_report = load_json(package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json") or {}
    outputs = bridge_report.get("outputs") if isinstance(bridge_report.get("outputs"), dict) else {}
    bridge_candidate = Path(str(outputs.get("candidateBlueprint") or package_dir / "bridge_sequence_blueprint" / "resolve_timeline_blueprint_bridge_sequence.json"))
    if bridge_report.get("status") == "ready_with_bridge_sequence_blueprint" and bridge_candidate.exists():
        return load_json(bridge_candidate), bridge_candidate, "bridge_sequence_candidate"
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint"


def safety_policy() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "mutatesActiveBlueprintByDefault": False,
    }


def transition_payload(
    row: dict[str, Any],
    *,
    fps: float,
    boundary: float,
    bridge_satisfied: bool,
    selection_row: dict[str, Any] | None,
    choreography_row: dict[str, Any] | None,
) -> dict[str, Any]:
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    selected = selected_candidate(selection_row)
    auto_decision = selection_decision(selection_row)
    selection_status = str((selection_row or {}).get("selectionStatus") or "")
    selection_applied = selection_status == "auto_selected" and bool(selected)
    duration_frames = as_int(
        selected.get("durationFrames") if selection_applied else recipe.get("durationFrames") or decision.get("durationFrames"),
        0,
    )
    duration_seconds = duration_frames / fps if fps > 0 else 0.0
    fallback_effect = decision.get("approvedResolveEffectName") or recipe.get("resolveEffectName")
    selected_effect = resolve_effect_from_selection(selected, fallback_effect) if selection_applied else str(fallback_effect or "")
    approved_type = (
        selected.get("candidateType")
        if selection_applied
        else decision.get("approvedTransitionType") or recipe.get("style") or (row.get("grammarRecommendation") or {}).get("recommendedTransitionType")
    )
    motion_execution = motion_execution_payload(row, selected=selected, choreography_row=choreography_row, duration_frames=duration_frames)
    cutpoint = cutpoint_plan(
        row,
        fps=fps,
        boundary=boundary,
        duration_frames=duration_frames,
        recipe=recipe,
        motion_execution=motion_execution,
        bridge_satisfied=bridge_satisfied,
    )
    return {
        "role": "transition_execution_candidate",
        "rowIndex": row.get("rowIndex"),
        "status": row.get("status"),
        "boundaryCategory": row.get("boundaryCategory"),
        "boundarySeconds": round3(boundary),
        "fromSourcePath": candidate_source_path(row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}),
        "toSourcePath": candidate_source_path(row.get("toClip") if isinstance(row.get("toClip"), dict) else {}),
        "approvedTransitionType": approved_type,
        "resolveEffectName": selected_effect,
        "durationFrames": duration_frames,
        "durationSeconds": round3(duration_seconds),
        "preRollFrames": as_int(recipe.get("preRollFrames"), 0),
        "postRollFrames": as_int(recipe.get("postRollFrames"), 0),
        "trackOperation": recipe.get("trackOperation"),
        "keyframePlan": recipe.get("keyframePlan") if isinstance(recipe.get("keyframePlan"), list) else [],
        "implementationSteps": recipe.get("implementationSteps") if isinstance(recipe.get("implementationSteps"), list) else [],
        "audioPolicy": recipe.get("audioPolicy"),
        "subtitlePolicy": recipe.get("subtitlePolicy"),
        "bgmPhraseCue": recipe.get("bgmPhraseCue") or decision.get("bgmPhraseCue"),
        "requiresBridgeInsert": row.get("requiresBridgeInsert") is True,
        "bridgeSequenceSatisfied": bridge_satisfied,
        "motionStyle": row.get("motionStyle") is True,
        "motionHasEvidence": row.get("motionHasEvidence") is True,
        "forbiddenRecipeHits": forbidden_hits(row, selection_row),
        "referenceSelectionStatus": selection_status,
        "referenceSelectionApplied": selection_applied,
        "selectedCandidateRank": selected.get("rank") if selection_applied else "",
        "selectedCandidateType": selected.get("candidateType") if selection_applied else "",
        "selectedStyleFamily": selected.get("styleFamily") if selection_applied else "",
        "selectedIntensity": selected.get("intensity") if selection_applied else "",
        "selectedResolveRecipe": selected.get("resolveRecipe") if selection_applied else "",
        "selectedPreviewHint": selected.get("ffmpegPreviewHint") if selection_applied else "",
        "referenceSelectionDecision": auto_decision if selection_applied else {},
        "transitionMotionExecution": motion_execution,
        "transitionCutpointPlan": cutpoint,
        "decision": dict(DECISION_FIELDS),
    }


def build_candidate(package_dir: Path, *, fps: float, update_blueprint: bool) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    plan_path = package_dir / "transition_execution_plan" / "transition_execution_plan.json"
    output_dir = package_dir / "transition_execution_blueprint"
    candidate_path = output_dir / "resolve_timeline_blueprint_transition_execution.json"
    report_path = output_dir / "transition_execution_blueprint_report.json"
    markdown_path = output_dir / "transition_execution_blueprint_report.md"
    base_blueprint, base_path, base_kind = choose_base_blueprint(package_dir)
    plan = load_json(plan_path)
    selection_plan, selection_rows = reference_selection_plan(package_dir)
    selection_plan_path = package_dir / "transition_reference_selection" / "transition_reference_selection.json"
    selection_ready = selection_plan.get("status") == "ready_with_transition_reference_selection"
    choreography_plan, choreography_rows = transition_choreography_plan(package_dir)
    choreography_plan_path = package_dir / "transition_choreography_plan" / "transition_choreography_plan.json"
    choreography_ready = choreography_plan.get("status") == "ready_with_transition_choreography_plan"

    if not isinstance(base_blueprint, dict) or not isinstance(plan, dict):
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "needs_transition_execution_blueprint_inputs",
            "packageDir": str(package_dir),
            "inputs": {
                "baseBlueprint": str(base_path),
                "baseBlueprintExists": base_path.exists(),
                "transitionExecutionPlan": str(plan_path),
                "transitionExecutionPlanExists": plan_path.exists(),
            },
            "outputs": {
                "candidateBlueprint": str(candidate_path),
                "reportJson": str(report_path),
                "reportMarkdown": str(markdown_path),
            },
            "summary": {},
            "materializedRows": [],
            "safety": safety_policy(),
            "nextActions": ["Run prepare_transition_execution_plan.py after transition grammar planning, then rerun this script."],
        }
        write_json(report_path, report)
        write_markdown(markdown_path, report)
        return report

    rows = plan.get("executionRows") if isinstance(plan.get("executionRows"), list) else []
    rows = [row for row in rows if isinstance(row, dict)]
    candidate = copy.deepcopy(base_blueprint)
    clips = blueprint_clips(candidate)
    satisfied_bridge_rows = bridge_row_indices(package_dir)
    transitions: list[dict[str, Any]] = []
    materialized_rows: list[dict[str, Any]] = []
    rows_with_decisions = 0
    blocked_rows = 0
    motion_rows = 0
    motion_rows_with_evidence = 0
    bridge_required_rows = 0
    bridge_satisfied_rows = 0
    rows_with_reference_selection = 0
    rows_with_applied_reference_selection = 0
    blocked_reference_selection_rows = 0
    selected_family_counts: dict[str, int] = {}
    rows_with_choreography_plan = 0
    rows_with_motion_execution = 0
    rows_with_three_beat_motion = 0
    rows_with_bgm_hit_motion = 0
    rows_with_caption_quiet_motion = 0
    rows_with_motion_direction_plan = 0
    rows_with_motion_direction_match = 0
    rows_with_cutpoint_plan = 0
    rows_with_cutpoint_ready = 0
    rows_with_cutpoint_bgm_hit = 0
    rows_with_cutpoint_landing_hold = 0
    rows_with_cutpoint_handles = 0
    blocked_cutpoint_rows = 0
    motion_execution_from_choreography = 0
    motion_execution_derived = 0
    blocked_motion_execution_rows = 0
    choreography_family_counts: dict[str, int] = {}

    for row in sorted(rows, key=boundary_seconds):
        boundary = boundary_seconds(row)
        row_index = as_int(row.get("rowIndex"), -1)
        requires_bridge = row.get("requiresBridgeInsert") is True
        bridge_satisfied = (not requires_bridge) or row_index in satisfied_bridge_rows
        selection_row = selection_rows.get(row_index)
        choreography_row = choreography_rows.get(row_index)
        selected = selected_candidate(selection_row)
        selection_status = str((selection_row or {}).get("selectionStatus") or "")
        choreography_status = str((choreography_row or {}).get("status") or "")
        if selection_row:
            rows_with_reference_selection += 1
        if selection_ready and selection_status == "auto_selected" and selected:
            rows_with_applied_reference_selection += 1
            family = str(selected.get("styleFamily") or "")
            if family:
                selected_family_counts[family] = selected_family_counts.get(family, 0) + 1
        else:
            blocked_reference_selection_rows += 1
        if choreography_row:
            rows_with_choreography_plan += 1
        payload = transition_payload(
            row,
            fps=fps,
            boundary=boundary,
            bridge_satisfied=bridge_satisfied,
            selection_row=selection_row,
            choreography_row=choreography_row,
        )
        motion_execution = payload.get("transitionMotionExecution") if isinstance(payload.get("transitionMotionExecution"), dict) else {}
        if motion_execution.get("status") == "ready_with_transition_motion_execution":
            rows_with_motion_execution += 1
        else:
            blocked_motion_execution_rows += 1
        if len(motion_execution.get("threeBeatChoreography") or []) >= 3:
            rows_with_three_beat_motion += 1
        bgm_choreography = motion_execution.get("bgmChoreography") if isinstance(motion_execution.get("bgmChoreography"), dict) else {}
        if bgm_choreography.get("target") == "cut_or_effect_on_bgm_phrase_hit" and bgm_choreography.get("allowOffPhrase") is False:
            rows_with_bgm_hit_motion += 1
        caption_policy = motion_execution.get("captionAndTitlePolicy") if isinstance(motion_execution.get("captionAndTitlePolicy"), dict) else {}
        if caption_policy.get("avoidTitleCollision") is True and caption_policy.get("suppressSubtitlesDuringHeroTitleOrFastMotion") is True:
            rows_with_caption_quiet_motion += 1
        direction_plan = motion_execution.get("motionDirectionPlan") if isinstance(motion_execution.get("motionDirectionPlan"), dict) else {}
        cutpoint = payload.get("transitionCutpointPlan") if isinstance(payload.get("transitionCutpointPlan"), dict) else {}
        if direction_plan:
            rows_with_motion_direction_plan += 1
        if direction_plan.get("required") is not True or direction_plan.get("directionMatch") is True:
            rows_with_motion_direction_match += 1
        if cutpoint:
            rows_with_cutpoint_plan += 1
        if cutpoint.get("status") == "ready_with_transition_cutpoint_plan":
            rows_with_cutpoint_ready += 1
        else:
            blocked_cutpoint_rows += 1
        if cutpoint.get("bgmHitAligned") is True:
            rows_with_cutpoint_bgm_hit += 1
        if as_int(cutpoint.get("landingHoldFrames"), 0) >= (10 if cutpoint.get("importantBoundary") else 6):
            rows_with_cutpoint_landing_hold += 1
        if cutpoint.get("handlesReady") is True:
            rows_with_cutpoint_handles += 1
        if motion_execution.get("source") == "transition_choreography_plan":
            motion_execution_from_choreography += 1
        if motion_execution.get("source") == "derived_from_reference_selection":
            motion_execution_derived += 1
        choreography_family = str(motion_execution.get("choreographyFamily") or "")
        if choreography_family:
            choreography_family_counts[choreography_family] = choreography_family_counts.get(choreography_family, 0) + 1
        transitions.append(payload)

        from_index = select_clip_index(clips, row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}, boundary, side="from")
        to_index = select_clip_index(clips, row.get("toClip") if isinstance(row.get("toClip"), dict) else {}, boundary, side="to")
        clip_refs = {"fromClipIndex": from_index, "toClipIndex": to_index}
        if from_index is not None:
            clips[from_index].setdefault("transitionExecutionOut", []).append({**payload, **clip_refs})
        if to_index is not None:
            clips[to_index].setdefault("transitionExecutionIn", []).append({**payload, **clip_refs})

        decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
        if set(DECISION_FIELDS).issubset(set(decision)):
            rows_with_decisions += 1
        if payload.get("motionStyle"):
            motion_rows += 1
            if payload.get("motionHasEvidence"):
                motion_rows_with_evidence += 1
        if requires_bridge:
            bridge_required_rows += 1
            if bridge_satisfied:
                bridge_satisfied_rows += 1
        row_blocked = (
            row.get("status") != "ready_with_transition_execution_recipe"
            or not selection_ready
            or selection_status != "auto_selected"
            or not choreography_ready
            or choreography_status != "ready_with_transition_choreography"
            or motion_execution.get("status") != "ready_with_transition_motion_execution"
            or cutpoint.get("status") != "ready_with_transition_cutpoint_plan"
            or not bridge_satisfied
            or bool(payload.get("forbiddenRecipeHits"))
            or (payload.get("motionStyle") and not payload.get("motionHasEvidence"))
        )
        if row_blocked:
            blocked_rows += 1
        materialized_rows.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "materialized" if not row_blocked else "needs_transition_execution_blueprint_repair",
                "boundarySeconds": round3(boundary),
                "resolveEffectName": payload.get("resolveEffectName"),
                "approvedTransitionType": payload.get("approvedTransitionType"),
                "durationFrames": payload.get("durationFrames"),
                "referenceSelectionStatus": payload.get("referenceSelectionStatus"),
                "referenceSelectionApplied": payload.get("referenceSelectionApplied"),
                "selectedCandidateRank": payload.get("selectedCandidateRank"),
                "selectedCandidateType": payload.get("selectedCandidateType"),
                "selectedStyleFamily": payload.get("selectedStyleFamily"),
                "transitionMotionExecutionStatus": motion_execution.get("status"),
                "motionExecutionSource": motion_execution.get("source"),
                "choreographyFamily": motion_execution.get("choreographyFamily"),
                "choreographyIntensity": motion_execution.get("intensity"),
                "threeBeatChoreographyCount": len(motion_execution.get("threeBeatChoreography") or []),
                "motionDirectionPlanStatus": direction_plan.get("status"),
                "motionDirectionEffect": direction_plan.get("effectDirection"),
                "motionDirectionLanding": direction_plan.get("landingDirection"),
                "motionDirectionMatched": direction_plan.get("directionMatch"),
                "transitionCutpointPlanStatus": cutpoint.get("status"),
                "cutpointOutgoingTailFrames": cutpoint.get("outgoingTailFrames"),
                "cutpointBridgeOrEffectFrames": cutpoint.get("bridgeOrEffectFrames"),
                "cutpointLandingHoldFrames": cutpoint.get("landingHoldFrames"),
                "cutpointBgmHitAligned": cutpoint.get("bgmHitAligned"),
                "cutpointHandlesReady": cutpoint.get("handlesReady"),
                "cutpointTitleSubtitleQuietZoneReady": cutpoint.get("titleSubtitleQuietZoneReady"),
                "bgmHitChoreographyReady": bgm_choreography.get("target") == "cut_or_effect_on_bgm_phrase_hit"
                and bgm_choreography.get("allowOffPhrase") is False,
                "captionQuietZoneReady": caption_policy.get("avoidTitleCollision") is True
                and caption_policy.get("suppressSubtitlesDuringHeroTitleOrFastMotion") is True,
                "fromClipMatched": from_index is not None,
                "toClipMatched": to_index is not None,
                "requiresBridgeInsert": requires_bridge,
                "bridgeSequenceSatisfied": bridge_satisfied,
                "motionStyle": payload.get("motionStyle"),
                "motionHasEvidence": payload.get("motionHasEvidence"),
                "forbiddenRecipeHits": payload.get("forbiddenRecipeHits"),
                "decision": dict(DECISION_FIELDS),
            }
        )

    candidate["clips"] = clips
    candidate["transitions"] = transitions
    candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    candidate["transitionExecutionBlueprintPlan"] = {
        "status": "candidate_not_applied_to_resolve",
        "createdAt": candidate["updatedAt"],
        "baseBlueprint": str(base_path),
        "baseBlueprintKind": base_kind,
        "sourceTransitionExecutionPlan": str(plan_path),
        "sourceTransitionReferenceSelection": str(selection_plan_path),
        "sourceTransitionChoreographyPlan": str(choreography_plan_path),
        "report": str(report_path),
        "candidateBlueprint": str(candidate_path),
        "fps": fps,
        "defaultBehavior": "writes a separate candidate blueprint and leaves the active blueprint untouched",
    }
    candidate.setdefault("timelineMarkers", [])
    if isinstance(candidate["timelineMarkers"], list):
        for transition in transitions:
            candidate["timelineMarkers"].append(
                {
                    "startSeconds": transition["boundarySeconds"],
                    "durationSeconds": max(0.25, transition["durationSeconds"]),
                    "color": "Purple",
                    "name": f"Transition Execution {transition.get('rowIndex')}",
                    "note": f"{transition.get('approvedTransitionType')} -> {transition.get('resolveEffectName')}",
                    "role": "transition_execution_candidate_marker",
                    "payload": {
                        "rowIndex": transition.get("rowIndex"),
                        "resolveEffectName": transition.get("resolveEffectName"),
                        "durationFrames": transition.get("durationFrames"),
                        "referenceSelectionApplied": transition.get("referenceSelectionApplied"),
                        "selectedCandidateType": transition.get("selectedCandidateType"),
                        "selectedStyleFamily": transition.get("selectedStyleFamily"),
                        "transitionMotionExecutionStatus": (transition.get("transitionMotionExecution") or {}).get("status")
                        if isinstance(transition.get("transitionMotionExecution"), dict)
                        else "",
                        "choreographyFamily": (transition.get("transitionMotionExecution") or {}).get("choreographyFamily")
                        if isinstance(transition.get("transitionMotionExecution"), dict)
                        else "",
                        "choreographyIntensity": (transition.get("transitionMotionExecution") or {}).get("intensity")
                        if isinstance(transition.get("transitionMotionExecution"), dict)
                        else "",
                    },
                }
            )
        candidate["timelineMarkers"] = sorted(candidate["timelineMarkers"], key=lambda item: (float(item.get("startSeconds") or 0.0), str(item.get("role") or "")))

    rows_missing_clip_match = sum(1 for row in materialized_rows if not row.get("fromClipMatched") or not row.get("toClipMatched"))
    status = "ready_with_transition_execution_blueprint" if rows and not blocked_rows and not rows_missing_clip_match else "needs_transition_execution_blueprint_repair"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "baseBlueprint": str(base_path),
            "baseBlueprintKind": base_kind,
            "transitionExecutionPlan": str(plan_path),
            "transitionReferenceSelectionPlan": str(selection_plan_path),
            "transitionReferenceSelectionStatus": selection_plan.get("status"),
            "transitionChoreographyPlan": str(choreography_plan_path),
            "transitionChoreographyStatus": choreography_plan.get("status"),
            "bridgeSequenceBlueprintRowsSatisfied": sorted(satisfied_bridge_rows),
        },
        "outputs": {
            "candidateBlueprint": str(candidate_path),
            "reportJson": str(report_path),
            "reportMarkdown": str(markdown_path),
            "activeBlueprintUpdated": bool(update_blueprint),
        },
        "summary": {
            "executionRowCount": len(rows),
            "materializedTransitionCount": len(transitions),
            "rowsWithDecisionFields": rows_with_decisions,
            "blockedRowCount": blocked_rows,
            "rowsMissingClipMatch": rows_missing_clip_match,
            "motionEffectRowCount": motion_rows,
            "motionEffectRowsWithEvidence": motion_rows_with_evidence,
            "bridgeRequiredRowCount": bridge_required_rows,
            "bridgeSatisfiedRowCount": bridge_satisfied_rows,
            "referenceSelectionRowCount": len(selection_rows),
            "rowsWithReferenceSelection": rows_with_reference_selection,
            "rowsWithAppliedReferenceSelection": rows_with_applied_reference_selection,
            "blockedReferenceSelectionRowCount": blocked_reference_selection_rows,
            "selectedStyleFamilyCounts": selected_family_counts,
            "choreographyRowCount": len(choreography_rows),
            "rowsWithChoreographyPlan": rows_with_choreography_plan,
            "rowsWithMotionExecution": rows_with_motion_execution,
            "rowsWithThreeBeatMotion": rows_with_three_beat_motion,
            "rowsWithBgmHitMotion": rows_with_bgm_hit_motion,
            "rowsWithCaptionQuietMotion": rows_with_caption_quiet_motion,
            "rowsWithMotionDirectionPlan": rows_with_motion_direction_plan,
            "rowsWithMotionDirectionMatch": rows_with_motion_direction_match,
            "rowsWithCutpointPlan": rows_with_cutpoint_plan,
            "rowsWithCutpointReady": rows_with_cutpoint_ready,
            "rowsWithCutpointBgmHit": rows_with_cutpoint_bgm_hit,
            "rowsWithCutpointLandingHold": rows_with_cutpoint_landing_hold,
            "rowsWithCutpointHandles": rows_with_cutpoint_handles,
            "blockedCutpointRowCount": blocked_cutpoint_rows,
            "motionExecutionFromChoreographyCount": motion_execution_from_choreography,
            "motionExecutionDerivedCount": motion_execution_derived,
            "blockedMotionExecutionRowCount": blocked_motion_execution_rows,
            "choreographyFamilyCounts": choreography_family_counts,
            "candidateClipCount": len(clips),
            "candidateTransitionCount": len(transitions),
        },
        "materializedRows": materialized_rows,
        "selectionRubric": {
            "pass": [
                "Every transition execution row becomes a candidate transition object in the blueprint.",
                "Every transition execution row consumes the auto-selected reference candidate when transition reference selection is ready.",
                "Every transition execution row consumes a ready choreography row and carries transitionMotionExecution metadata.",
                "Every transition execution row carries a transitionCutpointPlan with outgoing tail, BGM-hit bridge/effect, landing hold, handles, and title/subtitle quiet-zone proof.",
                "Adjacent source clips are annotated with in/out transition execution metadata.",
                "Motion effects are present only when the execution plan recorded route or two-sided motion evidence.",
                "Bridge-required transitions are not marked ready until bridge sequence rows are materialized.",
            ],
            "reject": [
                "Transition recipes remain prose-only and do not appear in the candidate blueprint.",
                "Reference selection exists but selected candidates are not present in transitions, clip annotations, or markers.",
                "Choreography exists but three-beat/BGM-hit/title-safe motion execution is not present in transitions, clip annotations, or markers.",
                "Cutpoint timing remains implicit, so an effect can hide a hard or unlanded boundary.",
                "A random spin, flash, glitch, shake, or template effect appears in a candidate row.",
                "A bridge-required row is marked ready without a materialized bridge sequence.",
                "The script writes Resolve, queues render, downloads assets, or mutates source footage.",
            ],
        },
        "safety": safety_policy(),
        "nextActions": [
            f"Run audit_resolve_blueprint.py --blueprint {candidate_path} --package-dir {package_dir} before using this candidate.",
            "Run or repair prepare_transition_choreography_plan.py first if motion execution coverage is below executionRowCount.",
            "Review transition_execution_blueprint_report.json and fill decision.approveCandidateBlueprint before Resolve apply.",
            "If approved, use a package fork or explicit --update-blueprint path so stale final QA is not reused.",
        ],
    }

    write_json(candidate_path, candidate)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    if update_blueprint:
        active_path = package_dir / "resolve_timeline_blueprint.json"
        active_blueprint = load_json(active_path) or {}
        backup = package_dir / f"resolve_timeline_blueprint.before_transition_execution_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        write_json(backup, active_blueprint)
        write_json(active_path, candidate)
        report["outputs"]["activeBlueprintBackup"] = str(backup)
        write_json(report_path, report)
        write_markdown(markdown_path, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Execution Blueprint Report",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Materialized Rows",
    ]
    for row in report.get("materializedRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('approvedTransitionType')}",
                f"- Status: `{row.get('status')}`",
                f"- Boundary: {row.get('boundarySeconds')}s",
                f"- Resolve effect: `{row.get('resolveEffectName')}`",
                f"- Duration: {row.get('durationFrames')} frames",
                f"- Reference selection: {row.get('referenceSelectionStatus')} / {row.get('selectedCandidateType')} / {row.get('selectedStyleFamily')}",
                f"- Motion execution: {row.get('transitionMotionExecutionStatus')} / {row.get('choreographyFamily')} / intensity={row.get('choreographyIntensity')}",
                f"- Three-beat/BGM/title-safe: {row.get('threeBeatChoreographyCount')} / {row.get('bgmHitChoreographyReady')} / {row.get('captionQuietZoneReady')}",
                f"- Clip match: from={row.get('fromClipMatched')} to={row.get('toClipMatched')}",
                f"- Bridge satisfied: {row.get('bridgeSequenceSatisfied')}",
                f"- Motion evidence: {row.get('motionStyle')} / {row.get('motionHasEvidence')}",
            ]
        )
        if row.get("forbiddenRecipeHits"):
            lines.append(f"- Forbidden hits: `{', '.join(row.get('forbiddenRecipeHits') or [])}`")
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a transition-execution Resolve blueprint candidate.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--fps", type=float, default=30.0, help="Timeline frame rate used to convert duration frames. Default: 30.")
    parser.add_argument("--update-blueprint", action="store_true", help="Replace the active blueprint after writing a backup. Default is non-destructive.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_candidate(Path(args.package_dir), fps=max(args.fps, 1.0), update_blueprint=args.update_blueprint)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report.get("status"), **(report.get("summary") or {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
