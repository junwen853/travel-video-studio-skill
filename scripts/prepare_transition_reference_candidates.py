#!/usr/bin/env python3
"""Prepare reference-calibrated A/B/C transition candidates for every adjacent boundary."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any


IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
MOTION_STYLES = {
    "whip_pan_match",
    "rotation_match_cut",
    "speed_ramp_bridge",
    "whip_pan",
    "rotation",
    "speed_ramp",
    "push_slide",
}
FORBIDDEN_EFFECTS = ("random spin", "flash", "glitch", "shake", "strobe", "particle", "template", "whoosh pack")

DECISION_FIELDS = {
    "selectedCandidateRank": "",
    "selectedCandidateType": "",
    "approvedBgmHit": "",
    "approvedBridgeOrMotionSource": "",
    "approvedTitleQuietZone": "",
    "resolveImplementation": "",
    "previewOrAuditionEvidence": "",
    "timelineReadbackEvidence": "",
    "renderFrameEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
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


def clean(value: Any, limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def source_name(clip: Any) -> str:
    clip = clip if isinstance(clip, dict) else {}
    source = clean(clip.get("sourcePath") or clip.get("sourceName") or clip.get("name"))
    return Path(source).name if source else ""


def reference_profile(package_dir: Path) -> dict[str, Any]:
    for path in (
        package_dir / "reference" / "reference_batch_profile.json",
        package_dir / "reference" / "reference_analysis.json",
    ):
        data = load_json(path)
        if isinstance(data, dict):
            targets = data.get("styleTargets") if isinstance(data.get("styleTargets"), dict) else {}
            transition_targets = (
                targets.get("transitionStyleTargets") if isinstance(targets.get("transitionStyleTargets"), dict) else {}
            )
            return {
                "path": str(path),
                "status": data.get("status"),
                "referenceVideoCount": (data.get("summary") or {}).get("referenceVideoCount")
                if isinstance(data.get("summary"), dict)
                else None,
                "transitionStyleTargets": transition_targets,
                "nonCopyingContract": data.get("referenceUsageContract"),
            }
    return {
        "path": None,
        "status": "missing_reference_profile",
        "referenceVideoCount": 0,
        "transitionStyleTargets": {
            "maxMotionShare": 0.18,
            "minCleanMatchBreathShare": 0.5,
            "minBridgeBreathImportantCoverage": 1.0,
            "maxDominantFamilyShare": 0.65,
            "maxFamilyRun": 4,
            "requireBgmHit": True,
            "requireCaptionQuietZone": True,
            "forbidHighIntensity": True,
        },
        "nonCopyingContract": {
            "allowed": "Use aggregate transition grammar and pacing as non-copying guidance.",
            "forbidden": "Do not copy exact creator transitions, music, branding, subtitles, or footage.",
        },
    }


def phrase_summary(package_dir: Path) -> dict[str, Any]:
    data = load_json(package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json") or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "status": data.get("status"),
        "phraseRowCount": summary.get("phraseRowCount") or summary.get("bgmPhraseRowCount"),
        "transitionCueCount": summary.get("transitionCueCount"),
        "candidateBlueprint": (data.get("outputs") or {}).get("candidateBlueprint") if isinstance(data.get("outputs"), dict) else None,
    }


def choreography_lookup(package_dir: Path) -> dict[int, dict[str, Any]]:
    data = load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json") or {}
    rows = data.get("choreographyRows") if isinstance(data.get("choreographyRows"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = as_int(row.get("rowIndex"), -1)
        if index >= 0:
            out[index] = row
    return out


def rows_from_execution(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_execution_plan" / "transition_execution_plan.json") or {}
    rows = data.get("executionRows") if isinstance(data.get("executionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def rows_from_grammar(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json") or {}
    rows = data.get("transitionRows") if isinstance(data.get("transitionRows"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rec = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
        out.append(
            {
                "rowIndex": row.get("rowIndex"),
                "boundaryCategory": row.get("boundaryCategory"),
                "timelineStartSeconds": row.get("timelineStartSeconds"),
                "fromClip": row.get("fromClip"),
                "toClip": row.get("toClip"),
                "grammarStatus": row.get("status"),
                "grammarRecommendation": rec,
                "motionEvidence": {
                    "physicalBridgeEvidence": rec.get("physicalBridgeEvidence") is True,
                    "motionEffectAllowedByGrammar": rec.get("motionEffectAllowed") is True,
                    "bridgeTerms": (row.get("signals") or {}).get("bridgeTerms") if isinstance(row.get("signals"), dict) else [],
                    "fromMotionTerms": (row.get("signals") or {}).get("fromMotionTerms") if isinstance(row.get("signals"), dict) else [],
                    "toMotionTerms": (row.get("signals") or {}).get("toMotionTerms") if isinstance(row.get("signals"), dict) else [],
                },
                "executionRecipe": {
                    "style": rec.get("recommendedTransitionType"),
                    "resolveEffectName": rec.get("recommendedTransitionType"),
                    "durationFrames": rec.get("durationFrames"),
                    "trackOperation": "grammar_only_pending_execution_recipe",
                },
                "status": "ready_with_transition_execution_recipe"
                if row.get("status") == "ready_with_transition_grammar"
                else row.get("status"),
            }
        )
    return out


def transition_rows(package_dir: Path) -> tuple[list[dict[str, Any]], str]:
    execution = rows_from_execution(package_dir)
    if execution:
        return execution, "transition_execution_plan"
    grammar = rows_from_grammar(package_dir)
    if grammar:
        return grammar, "transition_grammar_plan"
    return [], "missing_transition_rows"


def row_style(row: dict[str, Any]) -> str:
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    rec = row.get("grammarRecommendation") if isinstance(row.get("grammarRecommendation"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    text = " ".join(
        clean(value).lower()
        for value in (
            recipe.get("style"),
            recipe.get("resolveEffectName"),
            recipe.get("trackOperation"),
            rec.get("recommendedTransitionType"),
            decision.get("approvedTransitionType"),
        )
    )
    if "insert_bridge" in text or "bridge_insert" in text or "until_bridge" in text:
        return "insert_bridge_first"
    if "whip" in text:
        return "whip_pan_match"
    if "rotation" in text:
        return "rotation_match_cut"
    if "speed" in text or "ramp" in text:
        return "speed_ramp_bridge"
    if "dissolve" in text or "cross" in text:
        return "short_dissolve"
    if "match" in text:
        return "match_cut"
    return "straight_cut"


def motion_evidence(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("motionEvidence") if isinstance(row.get("motionEvidence"), dict) else {}
    bridge_terms = evidence.get("bridgeTerms") if isinstance(evidence.get("bridgeTerms"), list) else []
    from_motion = evidence.get("fromMotionTerms") if isinstance(evidence.get("fromMotionTerms"), list) else []
    to_motion = evidence.get("toMotionTerms") if isinstance(evidence.get("toMotionTerms"), list) else []
    return {
        "physicalBridgeEvidence": evidence.get("physicalBridgeEvidence") is True,
        "motionEffectAllowedByGrammar": evidence.get("motionEffectAllowedByGrammar") is True,
        "hasTwoSidedMotion": bool(from_motion and to_motion),
        "bridgeTerms": bridge_terms,
        "fromMotionTerms": from_motion,
        "toMotionTerms": to_motion,
    }


def visual_match_terms(row: dict[str, Any]) -> list[str]:
    rec = row.get("grammarRecommendation") if isinstance(row.get("grammarRecommendation"), dict) else {}
    terms = rec.get("sharedMatchTerms") if isinstance(rec.get("sharedMatchTerms"), list) else []
    return [clean(term, 40) for term in terms if clean(term, 40)]


def candidate(
    rank: str,
    candidate_type: str,
    family: str,
    *,
    intensity: str,
    duration_frames: int,
    when_to_use: str,
    resolve_recipe: str,
    preview_hint: str,
    required_evidence: list[str],
    reject_if: list[str],
) -> dict[str, Any]:
    return {
        "rank": rank,
        "candidateType": candidate_type,
        "styleFamily": family,
        "intensity": intensity,
        "durationFrames": duration_frames,
        "whenToUse": when_to_use,
        "resolveRecipe": resolve_recipe,
        "ffmpegPreviewHint": preview_hint,
        "requiredEvidence": required_evidence,
        "acceptanceEvidence": [
            "transition_preview_packet or transition_audition_packet sample is nonblank and watchable",
            "A1/A2 source voice is muted in scenic/title/transition windows and A3/BGM cue is audible when required",
            "title and subtitle quiet zones remain readable before, during, and after the boundary",
            "Resolve readback or manual apply notes record the actual effect/bridge implementation before final claim",
        ],
        "rejectIf": reject_if + [
            "used to hide missing route bridge footage",
            "used over weak/rejected/utility footage instead of improving source selection",
            "creates unreadable title/subtitle text",
            "adds source-camera voice under scenic/title/transition material",
        ],
    }


def candidate_ladder(
    row: dict[str, Any],
    *,
    allow_motion: bool,
    reference_requires_bgm_hit: bool,
    choreography: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str], str]:
    category = str(row.get("boundaryCategory") or "")
    style = row_style(row)
    motion = motion_evidence(row)
    match_terms = visual_match_terms(row)
    important = category in IMPORTANT_CATEGORIES
    has_bridge = motion["physicalBridgeEvidence"] or bool(motion["bridgeTerms"])
    bgm_phrase = "BGM phrase hit required" if reference_requires_bgm_hit else "BGM phrase preferred"
    choreography_note = clean((choreography or {}).get("approvedBgmHit") or (choreography or {}).get("bgmHit") or bgm_phrase)
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    row_status = "ready_with_reference_candidates"

    if style == "insert_bridge_first" or (important and not has_bridge and category not in {"title_boundary", "ending_transition"}):
        row_status = "needs_bridge_insert_before_effect"
        warnings.append("Important route/timeline boundary needs physical bridge footage before any visible effect.")
        candidates.append(
            candidate(
                "A",
                "physical_bridge_sequence",
                "physical_bridge",
                intensity="natural",
                duration_frames=0,
                when_to_use="Use 2-5 real transport/street/sign/weather/hotel/food/aerial bridge shots before the landing clip.",
                resolve_recipe="Insert video-only bridge beats on V1/V2, keep A1/A2 muted, align landing to a BGM phrase boundary.",
                preview_hint="Build a muted outgoing-edge + bridge-beats + landing-edge audition clip.",
                required_evidence=[
                    "transition_bridge_plan or bridge_sequence_plan row with local source/video-probe/frame evidence",
                    choreography_note,
                    "landing shot frame sample",
                ],
                reject_if=["no local or approved stock bridge source exists"],
            )
        )
        candidates.append(
            candidate(
                "B",
                "short_dissolve_after_bridge",
                "mood_dissolve",
                intensity="subtle",
                duration_frames=12,
                when_to_use="Use only after a real bridge beat establishes the route/time shift.",
                resolve_recipe="Apply a 8-12 frame Cross Dissolve from the bridge beat into the landing shot.",
                preview_hint="Sample frames before/during/after dissolve; verify no black/title clutter.",
                required_evidence=["bridge beat exists before dissolve", choreography_note],
                reject_if=["used directly between two places with no bridge beat"],
            )
        )
        candidates.append(
            candidate(
                "C",
                "clean_cut_after_bridge",
                "clean_cut",
                intensity="invisible",
                duration_frames=0,
                when_to_use="Use when the bridge shot already carries the route change and a visible effect would feel artificial.",
                resolve_recipe="Butt-cut on motion, soundless scenic beat, or BGM phrase boundary.",
                preview_hint="Generate still frames around outgoing, bridge, and landing edge.",
                required_evidence=["bridge beat exists", "landing frame is stable/readable"],
                reject_if=["the cut leaves a confusing place/time jump"],
            )
        )
        return candidates, warnings, row_status

    if category == "title_boundary":
        candidates.append(
            candidate(
                "A",
                "scenic_title_breath",
                "title_breath",
                intensity="subtle",
                duration_frames=0,
                when_to_use="Hold clean scenic title footage long enough for the viewer to read the place without extra route/date clutter.",
                resolve_recipe="Use scenic bridge/title video, video-only import, no subtitle overlay in title zone, optional 6-10 frame opacity/scale reveal.",
                preview_hint="Sample title start/mid/end frames and run title bridge contract.",
                required_evidence=["title_bridge_contract_audit", "clean scenic title bridge manifest", choreography_note],
                reject_if=["duplicate/ghosted title text", "subtitles overlap the hero title"],
            )
        )
        candidates.append(
            candidate(
                "B",
                "short_mood_dissolve",
                "mood_dissolve",
                intensity="subtle",
                duration_frames=10,
                when_to_use="Use when moving out of a readable title into lived-in route texture.",
                resolve_recipe="8-10 frame dissolve after the title has already been readable.",
                preview_hint="Sample during dissolve to prove title remains clean.",
                required_evidence=["title quiet zone confirmed", "landing shot is not black/generic"],
                reject_if=["dissolve starts before title is readable"],
            )
        )
        candidates.append(
            candidate(
                "C",
                "clean_cut_to_texture",
                "clean_cut",
                intensity="invisible",
                duration_frames=0,
                when_to_use="Use when the title background and next shot already share place/texture continuity.",
                resolve_recipe="Cut after the title hold on a BGM phrase or natural motion edge.",
                preview_hint="Sample title exit and first landing frame.",
                required_evidence=["title has stable hold", "landing shot continues route texture"],
                reject_if=["landing is an unrelated static landmark with no context"],
            )
        )
        return candidates, warnings, row_status

    if category == "ending_transition":
        candidates.append(
            candidate(
                "A",
                "ending_aftertaste_hold",
                "mood_dissolve",
                intensity="quiet",
                duration_frames=12,
                when_to_use="Use for the final scenic aftertaste or return-home breath.",
                resolve_recipe="Short dissolve or clean cut into stable scenic ending; hold long enough for BGM tail.",
                preview_hint="Build ending audition and sample final frames for black-frame/title cleanliness.",
                required_evidence=["ending scenic/route aftertaste shot", choreography_note],
                reject_if=["ends on a leftover clip with no route aftertaste"],
            )
        )
        candidates.append(
            candidate(
                "B",
                "visual_match_exit",
                "visual_match",
                intensity="invisible",
                duration_frames=2,
                when_to_use="Use if outgoing and ending share sky/water/window/road/light shape.",
                resolve_recipe="0-2 frame soft cut aligned to shared shape or motion.",
                preview_hint="Sample outgoing and landing frames side by side.",
                required_evidence=["shared visual term or frame match"],
                reject_if=["no visual match or emotional landing exists"],
            )
        )
        candidates.append(
            candidate(
                "C",
                "clean_bgm_cut",
                "clean_cut",
                intensity="invisible",
                duration_frames=0,
                when_to_use="Use when the final BGM phrase and scenic frame are strong enough without a visible effect.",
                resolve_recipe="Cut on BGM phrase boundary and hold ending shot.",
                preview_hint="Check audio continuity and last-frame luma.",
                required_evidence=["BGM tail/audibility proof", "nonblack ending frame"],
                reject_if=["music cuts abruptly or ending frame is generic"],
            )
        )
        return candidates, warnings, row_status

    if style in MOTION_STYLES and allow_motion and motion["motionEffectAllowedByGrammar"]:
        motion_type = "speed_ramp_bridge" if "speed" in style else ("rotation_match_cut" if "rotation" in style else "whip_pan_match")
        candidates.append(
            candidate(
                "A",
                motion_type,
                "motion_accent",
                intensity="restrained",
                duration_frames=8 if motion_type == "speed_ramp_bridge" else 10,
                when_to_use="Use as a rare accent only when route-motion evidence exists on both sides or in the bridge beat.",
                resolve_recipe="Apply subtle Transform/retime keyframes; cap rotation/push strength and land on stable footage.",
                preview_hint="Build a muted audition MP4 to verify the motion lands cleanly.",
                required_evidence=[
                    "two-sided motion or physical bridge terms",
                    choreography_note,
                    "post-transition breathing-room proof",
                ],
                reject_if=["static scenic pair", "previous nearby boundary already used motion accent"],
            )
        )
    elif style in MOTION_STYLES:
        warnings.append("Motion style was downgraded because budget, spacing, or evidence is insufficient.")

    if match_terms or style == "match_cut":
        candidates.append(
            candidate(
                "A" if not candidates else "B",
                "visual_match_cut",
                "visual_match",
                intensity="invisible",
                duration_frames=2,
                when_to_use="Use when outgoing and landing share shape, color, object, movement direction, or route texture.",
                resolve_recipe="Align the shared visual term at the cut; use no visible effect or a 2-frame soft cut only.",
                preview_hint="Export before/after frame strip for visual-match audit.",
                required_evidence=[f"shared terms: {', '.join(match_terms[:5])}" if match_terms else "visual match frame evidence"],
                reject_if=["match is only semantic but frames do not visually connect"],
            )
        )

    if has_bridge and not candidates:
        candidates.append(
            candidate(
                "A",
                "physical_bridge_cut",
                "physical_bridge",
                intensity="natural",
                duration_frames=0,
                when_to_use="Use the bridge footage itself as the transition language.",
                resolve_recipe="Cut through transport/street/sign/weather/hotel/food/aerial bridge beat, then land on the next scene.",
                preview_hint="Build outgoing + bridge + landing preview frames.",
                required_evidence=["bridge terms or bridge sequence row", choreography_note],
                reject_if=["bridge shot is unrelated stock filler"],
            )
        )

    if style == "short_dissolve" or not candidates:
        candidates.append(
            candidate(
                "A" if not candidates else "B",
                "short_mood_dissolve",
                "mood_dissolve",
                intensity="subtle",
                duration_frames=10,
                when_to_use="Use for mood, weather, time, scenic breath, or exposure transition.",
                resolve_recipe="8-12 frame Cross Dissolve with enough handles; keep it rare enough not to become the whole film.",
                preview_hint="Sample during dissolve for luma/title/subtitle cleanliness.",
                required_evidence=[choreography_note, "handle readiness"],
                reject_if=["used as default filler for missing bridge footage"],
            )
        )

    candidates.append(
        candidate(
            "C" if len(candidates) >= 2 else ("B" if candidates else "A"),
            "clean_continuity_cut",
            "clean_cut",
            intensity="invisible",
            duration_frames=0,
            when_to_use="Use when shot choice and BGM phrasing are stronger than a visible effect.",
            resolve_recipe="Butt-cut on action, gaze, motion edge, route texture, or BGM phrase boundary.",
            preview_hint="Sample two frames around the cut and verify the landing breath.",
            required_evidence=["pair-continuity or final-cut-smoothness evidence"],
            reject_if=["hard cut produces a confusing place/time jump"],
        )
    )
    families = {str(item.get("styleFamily") or "") for item in candidates}
    if len(candidates) < 3 and "visual_match" not in families:
        candidates.append(
            candidate(
                "C",
                "visual_context_match",
                "visual_match",
                intensity="invisible",
                duration_frames=2,
                when_to_use="Use when the editor can align color, object, skyline, road, water, crowd, or camera direction at the boundary.",
                resolve_recipe="0-2 frame soft cut after choosing matching edge frames; no decorative effect.",
                preview_hint="Make a side-by-side outgoing/landing frame strip before approval.",
                required_evidence=["explicit visual-match frame note"],
                reject_if=["no visible frame-level match can be found"],
            )
        )
    families = {str(item.get("styleFamily") or "") for item in candidates}
    if len(candidates) < 3 and "mood_dissolve" not in families:
        candidates.append(
            candidate(
                "C",
                "short_breath_dissolve",
                "mood_dissolve",
                intensity="subtle",
                duration_frames=8,
                when_to_use="Use as a quiet fallback for exposure, weather, time, or scenic breath when a match cut is not readable.",
                resolve_recipe="6-8 frame dissolve with handles; do not use as a bridge substitute.",
                preview_hint="Sample the dissolve midpoint for black frames and title/subtitle overlap.",
                required_evidence=["handle readiness", "no title/subtitle conflict"],
                reject_if=["the dissolve hides a missing route bridge"],
            )
        )
    for index, item in enumerate(candidates[:3], start=1):
        item["rank"] = "ABC"[index - 1]
    return candidates[:3], warnings, row_status


def has_forbidden_effect(row: dict[str, Any]) -> list[str]:
    text = clean(json.dumps(row, ensure_ascii=False), 6000).lower()
    return [term for term in FORBIDDEN_EFFECTS if term in text]


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    rows, row_source = transition_rows(package_dir)
    reference = reference_profile(package_dir)
    targets = reference.get("transitionStyleTargets") if isinstance(reference.get("transitionStyleTargets"), dict) else {}
    max_motion_share = min(as_float(targets.get("maxMotionShare"), 0.18) or 0.18, 0.25)
    max_motion_rows = max(1, math.floor(len(rows) * max_motion_share)) if rows else 0
    require_bgm_hit = targets.get("requireBgmHit") is not False
    choreography = choreography_lookup(package_dir)
    last_motion_index = -999
    motion_used = 0
    candidate_rows: list[dict[str, Any]] = []
    for row in rows:
        row_index = as_int(row.get("rowIndex"), len(candidate_rows) + 1)
        style = row_style(row)
        motion = motion_evidence(row)
        allow_motion = (
            style in MOTION_STYLES
            and motion_used < max_motion_rows
            and row_index - last_motion_index >= 5
            and (motion["physicalBridgeEvidence"] or motion["hasTwoSidedMotion"] or bool(motion["bridgeTerms"]))
        )
        candidates, warnings, row_status = candidate_ladder(
            row,
            allow_motion=allow_motion,
            reference_requires_bgm_hit=require_bgm_hit,
            choreography=choreography.get(row_index),
        )
        if candidates and candidates[0]["styleFamily"] == "motion_accent":
            motion_used += 1
            last_motion_index = row_index
        forbidden_hits = has_forbidden_effect(row)
        if forbidden_hits:
            warnings.append(f"Forbidden effect words appear upstream: {', '.join(forbidden_hits)}")
        candidate_rows.append(
            {
                "rowIndex": row_index,
                "boundaryCategory": row.get("boundaryCategory"),
                "timelineStartSeconds": row.get("timelineStartSeconds"),
                "fromClip": row.get("fromClip"),
                "toClip": row.get("toClip"),
                "fromSourceName": source_name(row.get("fromClip")),
                "toSourceName": source_name(row.get("toClip")),
                "sourcePlan": row_source,
                "upstreamStyle": style,
                "upstreamStatus": row.get("status") or row.get("grammarStatus"),
                "motionEvidence": motion,
                "referenceCandidateStatus": row_status,
                "candidateCount": len(candidates),
                "candidates": candidates,
                "warnings": warnings,
                "decision": dict(DECISION_FIELDS),
            }
        )
    important_count = sum(1 for row in candidate_rows if row.get("boundaryCategory") in IMPORTANT_CATEGORIES)
    important_covered = sum(
        1
        for row in candidate_rows
        if row.get("boundaryCategory") in IMPORTANT_CATEGORIES
        and any((item.get("styleFamily") in {"physical_bridge", "title_breath", "mood_dissolve"}) for item in row.get("candidates") or [])
    )
    rows_need_bridge = sum(1 for row in candidate_rows if row.get("referenceCandidateStatus") == "needs_bridge_insert_before_effect")
    three_candidate_rows = sum(1 for row in candidate_rows if int(row.get("candidateCount") or 0) >= 3)
    style_counts: dict[str, int] = {}
    for row in candidate_rows:
        first = (row.get("candidates") or [{}])[0]
        family = str(first.get("styleFamily") or "")
        if family:
            style_counts[family] = style_counts.get(family, 0) + 1
    status = (
        "ready_with_transition_reference_candidates"
        if candidate_rows
        else ("blocked_missing_transition_inputs" if row_source == "missing_transition_rows" else "blocked_missing_transition_candidates")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "rowSource": row_source,
            "transitionGrammarPlan": str(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json"),
            "transitionExecutionPlan": str(package_dir / "transition_execution_plan" / "transition_execution_plan.json"),
            "transitionChoreographyPlan": str(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json"),
            "bgmPhraseBlueprint": str(package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json"),
            "referenceProfile": reference.get("path"),
        },
        "summary": {
            "transitionRowCount": len(rows),
            "candidateRowCount": len(candidate_rows),
            "rowsWithAtLeastThreeCandidates": three_candidate_rows,
            "motionCandidateRowCount": motion_used,
            "maxMotionCandidateRows": max_motion_rows,
            "motionCandidateShare": round(motion_used / len(candidate_rows), 3) if candidate_rows else 0.0,
            "rowsNeedingBridgeBeforeEffect": rows_need_bridge,
            "importantBoundaryCount": important_count,
            "importantRowsWithBridgeOrBreathCandidate": important_covered,
            "importantBridgeOrBreathCoverage": round(important_covered / important_count, 3) if important_count else 1.0,
            "primaryStyleFamilyCounts": style_counts,
            "referenceStatus": reference.get("status"),
            "referenceVideoCount": reference.get("referenceVideoCount"),
        },
        "upstreamEvidence": {
            "reference": reference,
            "bgmPhrase": phrase_summary(package_dir),
        },
        "policy": {
            "abcCandidatesPerBoundary": True,
            "nonCopyingReferenceUse": True,
            "motionAccentsRareAndSpaced": True,
            "bridgeBeforeEffectForRouteJumps": True,
            "bgmHitAndTitleQuietZoneRequired": require_bgm_hit,
            "forbiddenTemplateEffectsRejected": True,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "candidateRows": candidate_rows,
        "nextActions": [
            "Review candidateRows and choose one candidate per boundary before Resolve apply.",
            "For rowsNeedingBridgeBeforeEffect, add real route/street/transport/title-breath footage before using a visible effect.",
            "Use transition_preview_packet and transition_audition_packet to prove important candidates are watchable before render.",
            "After Resolve apply, record readback/render-frame evidence and rerun transition profile, final smoothness, V14, maturity, and final QA.",
        ],
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Reference Candidates",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Rows",
    ]
    for row in plan["candidateRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row.get('boundaryCategory')}",
                f"- Status: `{row.get('referenceCandidateStatus')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Upstream style: `{row.get('upstreamStyle')}`",
                "- Candidates:",
            ]
        )
        for item in row.get("candidates") or []:
            lines.append(
                f"  - {item.get('rank')}. `{item.get('candidateType')}` / `{item.get('styleFamily')}` / "
                f"{item.get('intensity')} / {item.get('durationFrames')} frames"
            )
            lines.append(f"    - Use: {item.get('whenToUse')}")
            lines.append(f"    - Resolve: {item.get('resolveRecipe')}")
        if row.get("warnings"):
            lines.append("- Warnings:")
            lines.extend(f"  - {warning}" for warning in row["warnings"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare reference-calibrated transition A/B/C candidates.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_reference_candidates.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_reference_candidates"
    plan = build_plan(package_dir)
    write_json(output_dir / "transition_reference_candidates.json", plan)
    write_markdown(output_dir / "transition_reference_candidates.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 2 if str(plan["status"]).startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
