#!/usr/bin/env python3
"""Prepare a final micro-transition polish Resolve blueprint candidate."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint": "",
    "approvedPolishRows": "",
    "resolveImplementation": "",
    "preflightEvidence": "",
    "timelineReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

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


def choose_base_blueprint(package_dir: Path) -> tuple[dict[str, Any] | None, Path, str]:
    candidates = [
        (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json", "candidateBlueprint", "rhythm_recut_candidate"),
        (package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json", "candidateBlueprint", "bgm_phrase_candidate"),
        (package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json", "candidateBlueprint", "effect_motion_candidate"),
        (package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json", "candidateBlueprint", "transition_execution_candidate"),
        (package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json", "candidateBlueprint", "bridge_sequence_candidate"),
    ]
    for report_path, output_key, kind in candidates:
        report = load_json(report_path) or {}
        outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
        raw_candidate_path = outputs.get(output_key)
        if not raw_candidate_path or not str(report.get("status") or "").startswith("ready"):
            continue
        candidate_path = Path(str(raw_candidate_path)).expanduser()
        if not candidate_path.is_absolute():
            candidate_path = (package_dir / candidate_path).resolve()
        candidate = load_json(candidate_path)
        if isinstance(candidate, dict) and candidate_path.is_file():
            return candidate, candidate_path, kind
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint"


def transition_boundary(transition: dict[str, Any]) -> float | None:
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds"):
        value = as_float(transition.get(key))
        if value is not None:
            return value
    return None


def infer_transitions_from_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    video = sorted([clip for clip in clips if is_video_clip(clip)], key=lambda item: (timeline_start(item), timeline_end(item)))
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(video, video[1:]), start=1):
        boundary = max(timeline_end(left), timeline_start(right))
        rows.append(
            {
                "role": "transition_polish_inferred_boundary",
                "rowIndex": index,
                "boundarySeconds": round3(boundary),
                "boundaryCategory": "adjacent_clip_boundary",
                "approvedTransitionType": "straight_cut",
                "durationFrames": 2,
                "fromSourcePath": left.get("sourcePath") or left.get("sourceName"),
                "toSourcePath": right.get("sourcePath") or right.get("sourceName"),
                "audioPolicy": "bgm_only_no_camera_voice",
            }
        )
    return rows


def phrase_rows(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    rows = candidate.get("bgmPhraseCandidates") if isinstance(candidate.get("bgmPhraseCandidates"), list) else []
    if rows:
        return [row for row in rows if isinstance(row, dict)]
    audio_plan = candidate.get("audioPlan") if isinstance(candidate.get("audioPlan"), dict) else {}
    bgm_map = audio_plan.get("bgmPhraseMap") if isinstance(audio_plan.get("bgmPhraseMap"), dict) else {}
    rows = bgm_map.get("phraseRows") if isinstance(bgm_map.get("phraseRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def phrase_for_transition(transition: dict[str, Any], phrases: list[dict[str, Any]], boundary: float) -> dict[str, Any] | None:
    cue = transition.get("bgmPhraseCandidate") if isinstance(transition.get("bgmPhraseCandidate"), dict) else {}
    cue_index = cue.get("phraseIndex")
    for row in phrases:
        if cue_index is not None and row.get("phraseIndex") == cue_index:
            return row
    if not phrases:
        return None
    return min(
        phrases,
        key=lambda row: min(
            abs(float(as_float(row.get("timelineStartSeconds"), 0.0) or 0.0) - boundary),
            abs(float(as_float(row.get("timelineEndSeconds"), 0.0) or 0.0) - boundary),
        ),
    )


def nearest_beat(phrase: dict[str, Any] | None, boundary: float) -> float | None:
    if not phrase:
        return None
    cues = phrase.get("beatCueSeconds") if isinstance(phrase.get("beatCueSeconds"), list) else []
    values = [float(value) for value in cues if as_float(value) is not None]
    if not values:
        return boundary
    return min(values, key=lambda value: abs(value - boundary))


def forbidden_hits(transition: dict[str, Any]) -> list[str]:
    text = json.dumps(
        {
            "approvedTransitionType": transition.get("approvedTransitionType"),
            "resolveEffectName": transition.get("resolveEffectName"),
            "motionStyle": transition.get("motionStyle"),
            "trackOperation": transition.get("trackOperation"),
        },
        ensure_ascii=False,
    ).lower()
    hits = [term for term in FORBIDDEN_TERMS if term in text]
    if "spin" in text and not any(term in text for term in ("whip", "rotation match", "motivated", "route")):
        hits.append("unmotivated spin")
    return sorted(set(hits))


def style_text(transition: dict[str, Any]) -> str:
    return " ".join(
        str(transition.get(key) or "")
        for key in ("approvedTransitionType", "resolveEffectName", "trackOperation")
    ).lower()


def has_motion_style(transition: dict[str, Any]) -> bool:
    text = style_text(transition)
    return bool(transition.get("motionStyle")) or any(term in text for term in ("whip", "rotation", "speed", "ramp", "push", "slide"))


def motion_is_safe(transition: dict[str, Any]) -> bool:
    if not has_motion_style(transition):
        return True
    return transition.get("motionHasEvidence") is True or bool(transition.get("bridgeSequenceSatisfied"))


def selected_recipe(transition: dict[str, Any], boundary: float, phrase: dict[str, Any] | None, fps: float, *, allow_motion: bool) -> dict[str, Any]:
    text = style_text(transition)
    duration_frames = as_int(transition.get("durationFrames"), 0)
    if duration_frames <= 0:
        duration_frames = 14
    duration_frames = max(2, min(duration_frames, 24))
    if has_motion_style(transition) and not allow_motion:
        recipe_id = "downgraded_clean_bgm_cut"
        effect = "Cut"
        duration_frames = min(duration_frames, 4)
        keyframes = [{"frame": 0, "operation": "cut_on_bgm_hit_after_motion_evidence_failed"}]
    elif "whip" in text:
        recipe_id = "motivated_whip_pan_on_bgm_hit"
        effect = "Directional Blur + Push"
        keyframes = [
            {"frame": 0, "positionX": 0, "motionBlur": 0.0},
            {"frame": max(1, duration_frames // 2), "positionX": "source_motion_direction", "motionBlur": 0.28},
            {"frame": duration_frames, "positionX": 0, "motionBlur": 0.0},
        ]
    elif "rotation" in text:
        recipe_id = "rotation_match_cut_on_bgm_hit"
        effect = "Transform rotation match"
        keyframes = [
            {"frame": 0, "rotationDegrees": 0, "scale": 1.0},
            {"frame": max(1, duration_frames // 2), "rotationDegrees": "3_to_6_degrees_matching_source_motion", "scale": 1.025},
            {"frame": duration_frames, "rotationDegrees": 0, "scale": 1.0},
        ]
    elif "speed" in text or "ramp" in text:
        recipe_id = "speed_ramp_bridge_on_bgm_hit"
        effect = "Speed ramp"
        keyframes = [
            {"segment": "pre", "speedPercent": 100},
            {"segment": "hit", "speedPercent": "160_to_220_if_motion_supports"},
            {"segment": "post", "speedPercent": 100},
        ]
    elif "dissolve" in text or "cross" in text:
        recipe_id = "short_bgm_phrase_dissolve"
        effect = transition.get("resolveEffectName") or "Cross Dissolve"
        duration_frames = min(duration_frames, 18)
        keyframes = [
            {"frame": 0, "opacityOut": 1.0, "opacityIn": 0.0},
            {"frame": duration_frames, "opacityOut": 0.0, "opacityIn": 1.0},
        ]
    else:
        recipe_id = "clean_cut_on_bgm_hit"
        effect = transition.get("resolveEffectName") or "Cut"
        duration_frames = min(duration_frames, 4)
        keyframes = [{"frame": 0, "operation": "cut_on_hit"}]
    hit = nearest_beat(phrase, boundary)
    return {
        "recipeId": recipe_id,
        "resolveEffectName": effect,
        "durationFrames": duration_frames,
        "durationSeconds": round3(duration_frames / max(fps, 1.0)),
        "keyframePlan": keyframes,
        "bgmHitSeconds": round3(hit) if hit is not None else None,
        "hitToleranceSeconds": 0.35,
    }


def clip_indices_near_boundary(clips: list[dict[str, Any]], boundary: float) -> tuple[int | None, int | None]:
    from_scored: list[tuple[float, int]] = []
    to_scored: list[tuple[float, int]] = []
    for index, clip in enumerate(clips):
        if not is_video_clip(clip):
            continue
        from_scored.append((abs(timeline_end(clip) - boundary), index))
        to_scored.append((abs(timeline_start(clip) - boundary), index))
    from_index = min(from_scored)[1] if from_scored else None
    to_index = min(to_scored)[1] if to_scored else None
    return from_index, to_index


def safety_policy() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "mutatesActiveBlueprintByDefault": False,
        "requiresResolvePreflightBeforeApply": True,
    }


def build_candidate(package_dir: Path, *, fps: float, update_blueprint: bool) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = package_dir / "transition_polish_blueprint"
    candidate_path = output_dir / "resolve_timeline_blueprint_transition_polish.json"
    report_path = output_dir / "transition_polish_blueprint_report.json"
    markdown_path = output_dir / "transition_polish_blueprint_report.md"
    base_blueprint, base_path, base_kind = choose_base_blueprint(package_dir)
    if not isinstance(base_blueprint, dict):
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "needs_transition_polish_inputs",
            "packageDir": str(package_dir),
            "inputs": {"baseBlueprint": str(base_path), "baseBlueprintExists": base_path.exists()},
            "outputs": {"candidateBlueprint": str(candidate_path), "reportJson": str(report_path), "reportMarkdown": str(markdown_path)},
            "summary": {},
            "polishRows": [],
            "safety": safety_policy(),
            "nextActions": ["Run transition/effect/BGM phrase/rhythm recut candidate blueprints, then rerun this script."],
        }
        write_json(report_path, report)
        write_markdown(markdown_path, report)
        return report

    candidate = copy.deepcopy(base_blueprint)
    clips = candidate.get("clips") if isinstance(candidate.get("clips"), list) else []
    transitions = candidate.get("transitions") if isinstance(candidate.get("transitions"), list) else []
    if not transitions:
        transitions = infer_transitions_from_clips([clip for clip in clips if isinstance(clip, dict)])
    phrases = phrase_rows(candidate)
    polished: list[dict[str, Any]] = []
    rows_with_decisions = 0
    rows_with_bgm = 0
    rows_with_hit = 0
    rows_with_title_avoid = 0
    motion_rows = 0
    motion_rows_safe = 0
    downgraded_motion_rows = 0
    blocked_rows = 0
    clip_annotation_count = 0
    marker_count = 0

    for index, transition in enumerate(transitions, start=1):
        if not isinstance(transition, dict):
            continue
        boundary = transition_boundary(transition)
        if boundary is None:
            continue
        phrase = phrase_for_transition(transition, phrases, boundary)
        recipe = selected_recipe(transition, boundary, phrase, fps, allow_motion=motion_is_safe(transition))
        source_motion_row = has_motion_style(transition)
        motion_row = source_motion_row and motion_is_safe(transition)
        if source_motion_row:
            if motion_is_safe(transition):
                motion_rows += 1
                motion_rows_safe += 1
            else:
                downgraded_motion_rows += 1
        bgm_present = bool(phrase) or isinstance(transition.get("bgmPhraseCandidate"), dict)
        if bgm_present:
            rows_with_bgm += 1
        if recipe.get("bgmHitSeconds") is not None:
            rows_with_hit += 1
        title_avoidance = {
            "suppressSubtitleSecondsBefore": 0.35,
            "suppressSubtitleSecondsAfter": 0.35,
            "avoidTitleOverlayCollision": True,
            "captionPolicy": "no subtitle/title overlay covering the transition hit or hero title zone",
        }
        rows_with_title_avoid += 1
        hits = forbidden_hits(transition)
        blocked = bool(hits) or not bgm_present
        if blocked:
            blocked_rows += 1
        decision = dict(DECISION_FIELDS)
        if set(DECISION_FIELDS).issubset(set(decision)):
            rows_with_decisions += 1
        payload = {
            "role": "transition_polish_candidate",
            "rowIndex": transition.get("rowIndex") or index,
            "status": "materialized" if not blocked else "needs_transition_polish_repair",
            "boundarySeconds": round3(boundary),
            "boundaryCategory": transition.get("boundaryCategory") or "adjacent_clip_boundary",
            "fromSourcePath": transition.get("fromSourcePath"),
            "toSourcePath": transition.get("toSourcePath"),
            "sourceTransitionType": transition.get("approvedTransitionType"),
            "sourceResolveEffectName": transition.get("resolveEffectName"),
            "selectedRecipe": recipe,
            "bgmSync": {
                "phraseIndex": phrase.get("phraseIndex") if phrase else None,
                "section": phrase.get("section") if phrase else None,
                "hitSeconds": recipe.get("bgmHitSeconds"),
                "hitToleranceSeconds": recipe.get("hitToleranceSeconds"),
                "audioTreatment": "bgm_only_no_camera_voice",
            },
            "titleSubtitleAvoidance": title_avoidance,
            "motionEvidenceSatisfied": motion_is_safe(transition),
            "motionStyle": motion_row,
            "sourceMotionStyleDowngraded": source_motion_row and not motion_is_safe(transition),
            "bridgeSequenceSatisfied": transition.get("bridgeSequenceSatisfied"),
            "forbiddenPolishHits": hits,
            "decision": decision,
        }
        transition["transitionPolishCandidate"] = payload
        from_index, to_index = clip_indices_near_boundary([clip for clip in clips if isinstance(clip, dict)], boundary)
        if from_index is not None and 0 <= from_index < len(clips) and isinstance(clips[from_index], dict):
            clips[from_index].setdefault("transitionPolishOut", []).append(payload)
            clip_annotation_count += 1
        if to_index is not None and 0 <= to_index < len(clips) and isinstance(clips[to_index], dict):
            clips[to_index].setdefault("transitionPolishIn", []).append(payload)
            clip_annotation_count += 1
        polished.append(payload)

    candidate["clips"] = clips
    candidate["transitions"] = transitions
    candidate["transitionPolishCandidates"] = polished
    updated_at = datetime.now().isoformat(timespec="seconds")
    candidate["updatedAt"] = updated_at
    candidate["transitionPolishBlueprintPlan"] = {
        "status": "candidate_not_applied_to_resolve",
        "createdAt": updated_at,
        "baseBlueprint": str(base_path),
        "baseBlueprintKind": base_kind,
        "report": str(report_path),
        "candidateBlueprint": str(candidate_path),
        "fps": fps,
        "defaultBehavior": "writes a separate candidate blueprint and leaves the active blueprint untouched",
    }
    candidate.setdefault("timelineMarkers", [])
    if isinstance(candidate["timelineMarkers"], list):
        for row in polished:
            marker_count += 1
            candidate["timelineMarkers"].append(
                {
                    "startSeconds": row["boundarySeconds"],
                    "durationSeconds": max(0.25, float(row["selectedRecipe"]["durationSeconds"])),
                    "color": "Blue",
                    "name": f"Transition Polish {row.get('rowIndex')}",
                    "note": f"{row['selectedRecipe']['recipeId']} @ {row['bgmSync']['hitSeconds']}",
                    "role": "transition_polish_candidate_marker",
                    "payload": {"rowIndex": row.get("rowIndex"), "recipeId": row["selectedRecipe"]["recipeId"]},
                }
            )
        candidate["timelineMarkers"] = sorted(candidate["timelineMarkers"], key=lambda item: (float(item.get("startSeconds") or 0.0), str(item.get("role") or "")))

    status = "ready_with_transition_polish_blueprint" if polished and not blocked_rows else ("ready_no_transition_polish_needed" if not polished else "needs_transition_polish_repair")
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "baseBlueprint": str(base_path),
            "baseBlueprintKind": base_kind,
        },
        "outputs": {
            "candidateBlueprint": str(candidate_path),
            "reportJson": str(report_path),
            "reportMarkdown": str(markdown_path),
            "activeBlueprintUpdated": bool(update_blueprint),
        },
        "summary": {
            "transitionRowCount": len(polished),
            "polishedTransitionCount": len(polished),
            "rowsWithDecisionFields": rows_with_decisions,
            "rowsWithBgmPhraseCue": rows_with_bgm,
            "rowsWithBgmHit": rows_with_hit,
            "rowsWithTitleSubtitleAvoidance": rows_with_title_avoid,
            "motionPolishRowCount": motion_rows,
            "motionPolishRowsWithEvidence": motion_rows_safe,
            "downgradedMotionRowCount": downgraded_motion_rows,
            "blockedRowCount": blocked_rows,
            "clipAnnotationCount": clip_annotation_count,
            "markerCount": marker_count,
            "candidateTransitionCount": len(transitions),
            "candidateBgmPhraseCount": len(phrases),
        },
        "polishRows": polished,
        "selectionRubric": {
            "pass": [
                "Every candidate transition gets a micro-polish recipe tied to a BGM phrase hit.",
                "Every transition hit carries subtitle/title avoidance metadata.",
                "Whip, rotation, speed, push, or slide transitions require motion or bridge evidence.",
                "The script writes only a candidate blueprint and never mutates Resolve or source footage by default.",
            ],
            "reject": [
                "Transitions are only generic labels without BGM hit timing or Resolve keyframes.",
                "Template, glitch, flash, shake, random-spin, strobe, or particle effects are selected.",
                "Motion effects are used to hide weak route continuity or missing bridge footage.",
                "Scenic/title/transition windows can leak source voice or subtitle overlap.",
            ],
        },
        "safety": safety_policy(),
        "nextActions": [
            f"Run audit_resolve_blueprint.py --blueprint {candidate_path} --package-dir {package_dir} before using this candidate.",
            "Review transition_polish_blueprint_report.json and fill decision.approveCandidateBlueprint before Resolve apply.",
            "After Resolve readback, verify frame samples at each transition hit and rerun V14/maturity audits.",
        ],
    }
    write_json(candidate_path, candidate)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    if update_blueprint:
        active_path = package_dir / "resolve_timeline_blueprint.json"
        backup = package_dir / f"resolve_timeline_blueprint.before_transition_polish_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        write_json(backup, load_json(active_path) or {})
        write_json(active_path, candidate)
        report["outputs"]["activeBlueprintBackup"] = str(backup)
        write_json(report_path, report)
        write_markdown(markdown_path, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Polish Blueprint Report",
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
        "## Polish Rows",
    ]
    for row in report.get("polishRows") or []:
        recipe = row.get("selectedRecipe") if isinstance(row.get("selectedRecipe"), dict) else {}
        bgm = row.get("bgmSync") if isinstance(row.get("bgmSync"), dict) else {}
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {recipe.get('recipeId')}",
                f"- Status: `{row.get('status')}`",
                f"- Boundary: {row.get('boundarySeconds')}s",
                f"- BGM hit: {bgm.get('hitSeconds')}s",
                f"- Duration: {recipe.get('durationFrames')} frames",
                f"- Motion safe: {row.get('motionEvidenceSatisfied')}",
            ]
        )
        if row.get("forbiddenPolishHits"):
            lines.append(f"- Forbidden hits: `{', '.join(row.get('forbiddenPolishHits') or [])}`")
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a final transition-polish Resolve blueprint candidate.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--update-blueprint", action="store_true")
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
