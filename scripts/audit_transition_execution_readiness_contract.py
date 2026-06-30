#!/usr/bin/env python3
"""Audit whether final transition metadata is executable enough for Resolve apply."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


FORBIDDEN_TERMS = (
    "glitch",
    "flash",
    "shake",
    "strobe",
    "template",
    "particle",
    "random spin",
    "whoosh pack",
)
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide"}
DECORATIVE_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "dissolve"}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
PAIR_TAGS_FOR_IMPORTANT = {"route_bridge_context", "bridge_sequence", "motion_match", "title_or_ending_handoff"}
DECISION_FIELDS = {
    "approveCandidateBlueprint",
    "approvedPolishRows",
    "resolveImplementation",
    "preflightEvidence",
    "timelineReadbackEvidence",
    "frameSampleEvidence",
    "approvedBy",
    "approvedAt",
    "editorNotes",
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


def clip_duration(clip: dict[str, Any] | None) -> float:
    if not clip:
        return 0.0
    return max(0.0, timeline_end(clip) - timeline_start(clip))


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


def boundary_category(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_text = clip_text(left)
    right_text = clip_text(right)
    left_chapter = left.get("chapterIndex")
    right_chapter = right.get("chapterIndex")
    if "title" in left_text or "title" in right_text or "opening_city" in left_text or "ending_city" in right_text:
        return "title_boundary"
    if "ending" in left_text or "ending" in right_text:
        return "ending_transition"
    if left_chapter is not None and right_chapter is not None and str(left_chapter) != str(right_chapter):
        return "chapter_boundary"
    if timeline_start(right) - timeline_end(left) > 0.2:
        return "timeline_gap"
    return "same_chapter_cut"


def visual_boundaries(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(clips, clips[1:]), start=1):
        rows.append(
            {
                "boundaryIndex": index,
                "boundarySeconds": round3(timeline_end(left)),
                "timelineGapSeconds": round3(timeline_start(right) - timeline_end(left)),
                "category": boundary_category(left, right),
                "fromSourcePath": left.get("sourcePath") or left.get("sourceName"),
                "toSourcePath": right.get("sourcePath") or right.get("sourceName"),
                "fromSourceName": source_name(left.get("sourcePath") or left.get("sourceName")),
                "toSourceName": source_name(right.get("sourcePath") or right.get("sourceName")),
                "fromRole": left.get("role"),
                "toRole": right.get("role"),
                "fromChapterIndex": left.get("chapterIndex"),
                "toChapterIndex": right.get("chapterIndex"),
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


def pair_continuity(row: dict[str, Any]) -> dict[str, Any]:
    candidate = transition_candidate(row)
    payload = candidate.get("pairContinuity") if isinstance(candidate.get("pairContinuity"), dict) else {}
    if payload:
        return payload
    return row.get("pairContinuity") if isinstance(row.get("pairContinuity"), dict) else {}


def transition_boundary(row: dict[str, Any]) -> float | None:
    candidate = transition_candidate(row)
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds"):
        value = as_float(row.get(key))
        if value is not None:
            return value
    return as_float(candidate.get("boundarySeconds"))


def style_blob(row: dict[str, Any]) -> str:
    candidate = transition_candidate(row)
    recipe = selected_recipe(row)
    values = [
        row.get("approvedTransitionType"),
        row.get("resolveEffectName"),
        row.get("trackOperation"),
        row.get("motionStyle"),
        candidate.get("sourceTransitionType"),
        candidate.get("sourceResolveEffectName"),
        candidate.get("motionStyle"),
        recipe.get("recipeId"),
        recipe.get("resolveEffectName"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def normalize_style(row: dict[str, Any]) -> str:
    text = style_blob(row)
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


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    out = [row for row in rows if isinstance(row, dict)]
    if out:
        return out
    candidates = blueprint.get("transitionPolishCandidates") if isinstance(blueprint.get("transitionPolishCandidates"), list) else []
    return [{"transitionPolishCandidate": item, **item} for item in candidates if isinstance(item, dict)]


def pair_matches(boundary: dict[str, Any], transition: dict[str, Any]) -> bool:
    candidate = transition_candidate(transition)
    continuity = pair_continuity(transition)
    from_transition = source_name(transition.get("fromSourcePath") or candidate.get("fromSourcePath") or continuity.get("fromSourcePath"))
    to_transition = source_name(transition.get("toSourcePath") or candidate.get("toSourcePath") or continuity.get("toSourcePath"))
    if not from_transition and not to_transition:
        return False
    left = boundary.get("fromSourceName")
    right = boundary.get("toSourceName")
    return bool((not from_transition or from_transition == left) and (not to_transition or to_transition == right))


def nearest_transition(boundary: dict[str, Any], rows: list[dict[str, Any]], *, tolerance: float) -> dict[str, Any] | None:
    exact = [row for row in rows if row.get("rowIndex") == boundary.get("boundaryIndex")]
    if exact:
        return exact[0]
    candidates: list[tuple[float, dict[str, Any]]] = []
    boundary_seconds = float(boundary.get("boundarySeconds") or 0.0)
    for row in rows:
        value = transition_boundary(row)
        if value is None:
            continue
        distance = abs(value - boundary_seconds)
        if distance <= tolerance:
            candidates.append((distance, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def forbidden_hits(row: dict[str, Any]) -> list[str]:
    text = style_blob(row)
    hits = [term for term in FORBIDDEN_TERMS if term in text]
    if "spin" in text and not any(term in text for term in ("whip", "rotation match", "motivated", "route")):
        hits.append("unmotivated spin")
    return sorted(set(hits))


def repeated_decorative_run(styles: list[str]) -> int:
    best = 0
    current = ""
    length = 0
    for style in styles:
        if style == current:
            length += 1
        else:
            current = style
            length = 1
        if style in DECORATIVE_STYLES:
            best = max(best, length)
    return best


def bgm_ready(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    recipe = selected_recipe(row)
    bgm = candidate.get("bgmSync") if isinstance(candidate.get("bgmSync"), dict) else {}
    return bool(
        recipe.get("bgmHitSeconds") is not None
        or bgm.get("hitSeconds") is not None
        or bgm.get("phraseIndex") is not None
        or row.get("bgmHitSeconds") is not None
        or row.get("bgmPhraseCue")
    )


def audio_bgm_only(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    bgm = candidate.get("bgmSync") if isinstance(candidate.get("bgmSync"), dict) else {}
    text = " ".join(str(value or "") for value in (row.get("audioPolicy"), candidate.get("audioPolicy"), bgm.get("audioTreatment"))).lower()
    return "bgm" in text and "voice" in text


def title_safe(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    title = candidate.get("titleSubtitleAvoidance") if isinstance(candidate.get("titleSubtitleAvoidance"), dict) else {}
    policy = " ".join(str(row.get(key) or "") for key in ("subtitlePolicy", "titleZonePolicy")).lower()
    return bool(title.get("avoidTitleOverlayCollision") is True or title.get("suppressSubtitleSecondsBefore") is not None or "suppress" in policy)


def decision_fields_ready(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    decision = candidate.get("decision") if isinstance(candidate.get("decision"), dict) else {}
    return DECISION_FIELDS.issubset(set(decision))


def recipe_duration(row: dict[str, Any], fps: float) -> float:
    recipe = selected_recipe(row)
    duration = as_float(recipe.get("durationSeconds"))
    if duration is not None and duration > 0:
        return duration
    frames = as_float(recipe.get("durationFrames"))
    if frames is not None and frames > 0:
        return frames / max(fps, 1.0)
    return 0.0


def recipe_ready(row: dict[str, Any], fps: float) -> bool:
    recipe = selected_recipe(row)
    duration = recipe_duration(row, fps)
    keyframes = recipe.get("keyframePlan") if isinstance(recipe.get("keyframePlan"), list) else []
    return bool(recipe.get("recipeId") and recipe.get("resolveEffectName") and duration > 0 and duration <= 0.9 and keyframes)


def motion_ready(row: dict[str, Any], style: str) -> bool:
    if style not in MOTION_STYLES:
        return True
    candidate = transition_candidate(row)
    continuity = pair_continuity(row)
    return bool(
        candidate.get("motionEvidenceSatisfied") is True
        or candidate.get("bridgeSequenceSatisfied") is True
        or row.get("motionHasEvidence") is True
        or row.get("bridgeSequenceSatisfied") is True
        or "motion_match" in (continuity.get("evidenceTags") or [])
        or "bridge_sequence" in (continuity.get("evidenceTags") or [])
    )


def pair_ready(row: dict[str, Any], style: str, category: str) -> bool:
    continuity = pair_continuity(row)
    pair_fit = str(continuity.get("pairFit") or "")
    tags = set(continuity.get("evidenceTags") or [])
    style_allowed = continuity.get("styleAllowed") is True
    if pair_fit not in {"strong", "acceptable"} or not style_allowed or not tags:
        return False
    if style in {"whip_pan", "rotation", "speed_ramp"} and pair_fit != "strong":
        return False
    if category in IMPORTANT_CATEGORIES and not (tags & PAIR_TAGS_FOR_IMPORTANT):
        return False
    return True


def clip_by_source(clips: list[dict[str, Any]], source: str, *, prefer_end: bool) -> dict[str, Any] | None:
    name = source_name(source)
    candidates = [clip for clip in clips if source_name(clip.get("sourcePath") or clip.get("sourceName")) == name]
    if not candidates:
        return None
    key = timeline_end if prefer_end else timeline_start
    return sorted(candidates, key=key, reverse=prefer_end)[0]


def handle_ready(row: dict[str, Any], clips: list[dict[str, Any]], boundary: dict[str, Any], fps: float) -> tuple[bool, dict[str, Any]]:
    style = normalize_style(row)
    duration = recipe_duration(row, fps)
    if style == "clean_cut" or duration <= 0.16:
        return True, {"mode": "clean_or_short_cut", "requiredSeconds": duration}
    from_clip = clip_by_source(clips, str(boundary.get("fromSourcePath") or ""), prefer_end=True)
    to_clip = clip_by_source(clips, str(boundary.get("toSourcePath") or ""), prefer_end=False)
    required = max(0.5, duration * 2.0)
    from_duration = clip_duration(from_clip)
    to_duration = clip_duration(to_clip)
    ok = bool(from_clip and to_clip and from_duration >= required and to_duration >= required)
    return ok, {
        "mode": "timeline_duration_proxy",
        "requiredSeconds": round3(required),
        "fromDurationSeconds": round3(from_duration),
        "toDurationSeconds": round3(to_duration),
        "note": "Uses timeline duration as a conservative proxy when source in/out handles are unavailable.",
    }


def audited_boundary(
    boundary: dict[str, Any],
    transition: dict[str, Any] | None,
    clips: list[dict[str, Any]],
    *,
    fps: float,
) -> dict[str, Any]:
    if not transition:
        return {**boundary, "status": "blocked", "style": None, "issues": ["missing_transition_execution_candidate"]}
    candidate = transition_candidate(transition)
    recipe = selected_recipe(transition)
    continuity = pair_continuity(transition)
    style = normalize_style(transition)
    duration = recipe_duration(transition, fps)
    handle_ok, handle_evidence = handle_ready(transition, clips, boundary, fps)
    hits = forbidden_hits(transition)
    issues: list[str] = []
    if candidate.get("status") not in {"materialized", "ready", "passed", None}:
        issues.append("transition_polish_candidate_not_materialized")
    if not pair_matches(boundary, transition):
        issues.append("transition_candidate_not_matched_to_actual_boundary")
    if not recipe_ready(transition, fps):
        issues.append("missing_or_invalid_resolve_recipe_keyframes_or_duration")
    if not bgm_ready(transition):
        issues.append("missing_bgm_hit_or_phrase_for_execution")
    if not audio_bgm_only(transition):
        issues.append("missing_bgm_only_no_voice_audio_treatment")
    if not title_safe(transition):
        issues.append("missing_title_subtitle_collision_avoidance")
    if not decision_fields_ready(transition):
        issues.append("missing_resolve_apply_decision_fields")
    if not motion_ready(transition, style):
        issues.append("motion_transition_without_motion_or_bridge_evidence")
    if not pair_ready(transition, style, str(boundary.get("category") or "")):
        issues.append("pair_continuity_not_strong_enough_for_execution")
    if not handle_ok:
        issues.append("insufficient_adjacent_clip_duration_for_transition_handles")
    if hits:
        issues.append("forbidden_or_template_transition_style")
    if duration > 0.9:
        issues.append("transition_recipe_too_long_for_reference_like_pacing")
    return {
        **boundary,
        "status": "passed" if not issues else "blocked",
        "transitionRowIndex": transition.get("rowIndex") or candidate.get("rowIndex"),
        "transitionBoundarySeconds": transition_boundary(transition),
        "style": style,
        "recipeId": recipe.get("recipeId"),
        "resolveEffectName": recipe.get("resolveEffectName"),
        "durationSeconds": round3(duration),
        "hasKeyframes": isinstance(recipe.get("keyframePlan"), list) and bool(recipe.get("keyframePlan")),
        "hasBgmHit": bgm_ready(transition),
        "bgmOnlyAudio": audio_bgm_only(transition),
        "titleSafe": title_safe(transition),
        "decisionFieldsReady": decision_fields_ready(transition),
        "pairFit": continuity.get("pairFit"),
        "pairContinuityTags": continuity.get("evidenceTags") or [],
        "pairReady": pair_ready(transition, style, str(boundary.get("category") or "")),
        "motionReady": motion_ready(transition, style),
        "handleReady": handle_ok,
        "handleEvidence": handle_evidence,
        "forbiddenHits": hits,
        "issues": issues,
    }


def counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "missing")
        out[key] = out.get(key, 0) + 1
    return out


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
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, args.blueprint)
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
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    clips = primary_visual_clips(blueprint)
    boundaries = visual_boundaries(clips)
    rows = transition_rows(blueprint)
    audited = [
        audited_boundary(boundary, nearest_transition(boundary, rows, tolerance=args.tolerance_seconds), clips, fps=args.fps)
        for boundary in boundaries
    ]
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    styles = [str(row.get("style")) for row in audited if row.get("style")]
    decorative_run = repeated_decorative_run(styles)
    motion_count = sum(1 for row in audited if row.get("style") in MOTION_STYLES)
    blockers = [f"boundary {row.get('boundaryIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[:80]]
    warnings: list[str] = []
    if boundaries and not rows:
        blockers.append("visual boundaries exist but no transition rows found")
    if boundaries and blueprint_kind != "transition_polish_candidate":
        blockers.append(f"transition execution readiness must audit transition_polish_candidate, not {blueprint_kind}")
    if not blueprint_inside_package:
        blockers.append("selected transition candidate blueprint is outside the package and is not portable")
    if decorative_run >= 4:
        blockers.append(f"decorative transition style repeats {decorative_run} times consecutively")
    if len(audited) >= 8 and motion_count > math.ceil(len(audited) * 0.30):
        blockers.append(f"too many motion/effect-driven transitions for restrained travel pacing: {motion_count}/{len(audited)}")
    if not audited and len(clips) > 1:
        blockers.append("visual boundaries exist but no boundary rows were audited")
    if not boundaries:
        warnings.append("no adjacent visual boundaries found; transition execution readiness is trivially satisfied")
    status = "passed" if not blockers and (not boundaries or rows) else "blocked"
    max_duration = max((float(row.get("durationSeconds") or 0.0) for row in audited), default=0.0)
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "toleranceSeconds": args.tolerance_seconds,
            "fps": args.fps,
        },
        "summary": {
            "visualClipCount": len(clips),
            "visualBoundaryCount": len(boundaries),
            "transitionRowCount": len(rows),
            "transitionCoverageRatio": round3(len(rows) / len(boundaries)) if boundaries else 1.0,
            "auditedBoundaryCount": len(audited),
            "passedBoundaryCount": sum(1 for row in audited if row.get("status") == "passed"),
            "blockedBoundaryCount": len(blocked_rows),
            "recipeReadyBoundaryCount": sum(1 for row in audited if row.get("recipeId") and row.get("hasKeyframes")),
            "bgmHitBoundaryCount": sum(1 for row in audited if row.get("hasBgmHit") is True),
            "bgmOnlyBoundaryCount": sum(1 for row in audited if row.get("bgmOnlyAudio") is True),
            "titleSafeBoundaryCount": sum(1 for row in audited if row.get("titleSafe") is True),
            "decisionFieldBoundaryCount": sum(1 for row in audited if row.get("decisionFieldsReady") is True),
            "pairReadyBoundaryCount": sum(1 for row in audited if row.get("pairReady") is True),
            "handleReadyBoundaryCount": sum(1 for row in audited if row.get("handleReady") is True),
            "motionBoundaryCount": motion_count,
            "motionReadyBoundaryCount": sum(1 for row in audited if row.get("style") in MOTION_STYLES and row.get("motionReady") is True),
            "importantBoundaryCount": sum(1 for row in audited if row.get("category") in IMPORTANT_CATEGORIES),
            "forbiddenHitCount": sum(len(row.get("forbiddenHits") or []) for row in audited),
            "decorativeRepeatedRunMax": decorative_run,
            "maxTransitionDurationSeconds": round3(max_duration),
            "styleCounts": counts(audited, "style"),
            "categoryCounts": counts(audited, "category"),
            "blockerCount": len(blockers),
        },
        "boundaryRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Execution Readiness Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report['inputs'].get('blueprint')}`",
        f"Blueprint kind: `{report['inputs'].get('blueprintKind')}`",
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
    lines.extend(["", "## Boundary Rows"])
    for row in (report.get("boundaryRows") or [])[:160]:
        lines.extend(
            [
                "",
                f"### Boundary {row.get('boundaryIndex')}: {row.get('category')} / {row.get('style')}",
                f"- Status: `{row.get('status')}`",
                f"- Recipe: `{row.get('recipeId')}` / `{row.get('resolveEffectName')}` / `{row.get('durationSeconds')}`s",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Ready: recipe `{row.get('hasKeyframes')}`, BGM `{row.get('hasBgmHit')}`, title `{row.get('titleSafe')}`, pair `{row.get('pairReady')}`, handles `{row.get('handleReady')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether transition polish metadata is executable for Resolve apply.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--tolerance-seconds", type=float, default=0.75)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_execution_readiness_contract_audit.json", report)
    write_markdown(package_dir / "transition_execution_readiness_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
