#!/usr/bin/env python3
"""Prepare multi-shot bridge sequences between adjacent travel-film sections."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approvedSequenceType": "",
    "selectedBeatClipPaths": [],
    "bridgeBeatTimelinePlacement": "",
    "bgmPhraseMap": "",
    "captionSuppressionWindows": "",
    "resolveBlueprintUpdate": "",
    "timelineReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

REPAIR_DECISION_FIELDS = {
    "acceptedRepair": "",
    "repairAppliedAt": "",
    "postRepairArtifact": "",
    "postRepairAudit": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

BEAT_TERMS = {
    "exit_context": ("street", "walk", "hotel", "room", "lobby", "market", "sign", "food", "night", "window", "街", "酒店", "窗"),
    "route_motion": ("airport", "station", "train", "metro", "subway", "taxi", "bus", "road", "ferry", "boat", "plane", "vehicle", "walking", "window", "机场", "车站", "地铁", "火车", "路"),
    "arrival_establishing": ("aerial", "drone", "skyline", "city", "landmark", "bridge", "coast", "water", "tower", "temple", "establish", "航拍", "城市", "海", "桥"),
    "lived_in_texture": ("food", "restaurant", "table", "shop", "market", "signage", "rain", "weather", "coffee", "street", "hotel", "menu", "饭", "店", "招牌", "雨"),
    "destination_payoff": ("landmark", "view", "scenic", "temple", "museum", "garden", "coast", "skyline", "night", "sunset", "payoff", "景", "寺", "夜"),
    "title_clean_hold": ("title", "opening", "chapter", "city", "aerial", "skyline", "bridge", "coast", "hero", "航拍", "城市"),
    "visual_match": ("window", "water", "road", "sign", "food", "table", "street", "skyline", "bridge", "walking", "窗", "水", "路", "街"),
    "aftertaste": ("ending", "night", "sunset", "quiet", "airport", "train", "road", "window", "scenic", "dusk", "夜", "安静"),
}

TITLE_CATEGORIES = {"title_boundary"}
ROUTE_CATEGORIES = {"chapter_boundary", "timeline_gap"}


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


def clean_words(value: Any, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def lower_blob(value: Any) -> str:
    if isinstance(value, dict):
        value = " ".join(str(value.get(key) or "") for key in sorted(value))
    return clean_words(value, limit=1200).lower()


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def source_name(clip: dict[str, Any] | None) -> str:
    clip = clip if isinstance(clip, dict) else {}
    source = str(clip.get("sourcePath") or clip.get("sourceName") or "")
    return Path(source).name if source else ""


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath", "name", "notes", "creatorFunction", "editorialTier")
    ).lower()


def video_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = clip_text(row)
        if "subtitle_overlay" in text:
            continue
        track_type = clean_words(row.get("trackType")).lower()
        if track_type and track_type != "video":
            continue
        out.append(row)
    return sorted(out, key=lambda item: (timeline_start(item), int(as_float(item.get("trackIndex"), 1) or 1)))


def transition_rows(package_dir: Path) -> list[dict[str, Any]]:
    motif = load_json(package_dir / "transition_motif_plan" / "transition_motif_plan.json") or {}
    rows = motif.get("motifRows") if isinstance(motif.get("motifRows"), list) else []
    if rows:
        return [row for row in rows if isinstance(row, dict)]
    execution = load_json(package_dir / "transition_execution_plan" / "transition_execution_plan.json") or {}
    rows = execution.get("executionRows") if isinstance(execution.get("executionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def upstream_summary(package_dir: Path, rel: str) -> dict[str, Any]:
    data = load_json(package_dir / rel) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {"status": data.get("status"), **summary}


def creator_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    rows = data.get("shotRows") if isinstance(data.get("shotRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def creator_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        for key in (row.get("sourcePath"), row.get("sourceName")):
            if key:
                lookup[str(key)] = row
    return lookup


def enrich_clip(clip: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row = lookup.get(str(clip.get("sourcePath") or "")) or lookup.get(source_name(clip)) or {}
    merged = dict(clip)
    for key in ("creatorFunction", "editorialTier", "recommendedUse", "selectionTier"):
        if row.get(key) and not merged.get(key):
            merged[key] = row.get(key)
    return merged


def sequence_type(row: dict[str, Any]) -> str:
    category = str(row.get("boundaryCategory") or "")
    motif = str(row.get("motif") or "")
    style = str(row.get("executionStyle") or "")
    if category in TITLE_CATEGORIES or motif == "title_clean_reveal":
        return "clean_title_bridge_sequence"
    if category in ROUTE_CATEGORIES or motif in {"physical_route_bridge", "blocked_bridge_insert"}:
        return "route_texture_bridge_sequence"
    if "ending" in category or motif == "mood_dissolve" and "ending" in lower_blob(row):
        return "ending_aftertaste_sequence"
    if motif == "visual_match" or style == "match_cut":
        return "visual_match_sequence"
    return "simple_continuity_sequence"


def required_beats(seq_type: str) -> list[dict[str, Any]]:
    if seq_type == "clean_title_bridge_sequence":
        beats = [
            ("arrival_establishing", 2.5, "Scenic or aerial pre-roll so the title sits on real place evidence."),
            ("title_clean_hold", 2.0, "One clean main title, no subtitles or route/date clutter in title safe zone."),
            ("lived_in_texture", 2.5, "Exit the title into a street/detail/arrival beat instead of a hard cut."),
        ]
    elif seq_type == "route_texture_bridge_sequence":
        beats = [
            ("exit_context", 2.0, "Leave the previous place with a grounded local cue."),
            ("route_motion", 2.5, "Show movement through train, station, vehicle, walking, water, or road texture."),
            ("arrival_establishing", 2.5, "Prove the new place with skyline, landmark, signage, or city scale."),
            ("lived_in_texture", 2.0, "Settle into human-scale street, food, hotel, weather, or daily detail."),
        ]
    elif seq_type == "ending_aftertaste_sequence":
        beats = [
            ("destination_payoff", 3.0, "Hold the last place or emotional payoff long enough to breathe."),
            ("route_motion", 2.5, "Return to movement, departure, road, station, or window if available."),
            ("aftertaste", 3.0, "Let the music tail carry a quiet final image."),
        ]
    elif seq_type == "visual_match_sequence":
        beats = [
            ("visual_match", 1.5, "Use matching shape/action/object/color before the cut."),
            ("lived_in_texture", 1.5, "Land the cut on a human-scale detail if the match is too abstract."),
        ]
    else:
        beats = [
            ("visual_match", 1.0, "Prefer direct continuity when the place already connects."),
            ("lived_in_texture", 1.5, "Add a short detail beat only if the cut feels abrupt."),
        ]
    return [
        {
            "beatIndex": index,
            "function": function,
            "idealDurationSeconds": duration,
            "purpose": purpose,
            "required": True,
        }
        for index, (function, duration, purpose) in enumerate(beats, start=1)
    ]


def row_anchor(row: dict[str, Any]) -> float | None:
    from_clip = row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}
    to_clip = row.get("toClip") if isinstance(row.get("toClip"), dict) else {}
    left_end = timeline_end(from_clip)
    right_start = timeline_start(to_clip)
    if left_end or right_start:
        return (left_end + right_start) / 2.0
    return None


def candidate_score(clip: dict[str, Any], beat_function: str, row: dict[str, Any], anchor: float | None) -> tuple[int, float, bool]:
    text = clip_text(clip)
    terms = BEAT_TERMS.get(beat_function, ())
    term_hits = sum(1 for term in terms if term.lower() in text)
    semantic_match = term_hits > 0
    score = term_hits * 3
    role = text
    if "hero" in role or "opening" in role or "payoff" in role:
        score += 2 if beat_function in {"arrival_establishing", "destination_payoff", "title_clean_hold"} else 0
    if "transition_bridge" in role or "bridge" in role:
        score += 3 if beat_function in {"route_motion", "lived_in_texture", "exit_context"} else 1
    if "texture" in role or "street" in role:
        score += 2 if beat_function in {"lived_in_texture", "exit_context", "visual_match"} else 0
    if source_name(clip) in {source_name(row.get("fromClip")), source_name(row.get("toClip"))}:
        score += 1
    distance = 999999.0
    if anchor is not None:
        start = timeline_start(clip)
        end = timeline_end(clip)
        if start <= anchor <= end:
            distance = 0.0
            score += 2
        else:
            distance = min(abs(anchor - start), abs(anchor - end))
            if distance <= 45:
                score += 1
    return score, distance, semantic_match


def candidates_for_beat(clips: list[dict[str, Any]], beat_function: str, row: dict[str, Any], anchor: float | None) -> list[dict[str, Any]]:
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for clip in clips:
        score, distance, semantic_match = candidate_score(clip, beat_function, row, anchor)
        if score <= 0 or not semantic_match:
            continue
        scored.append((score, distance, clip))
    scored.sort(key=lambda item: (-item[0], item[1], source_name(item[2])))
    out: list[dict[str, Any]] = []
    for score, distance, clip in scored[:5]:
        out.append(
            {
                "score": score,
                "distanceSeconds": None if distance >= 999998 else round(distance, 3),
                "sourcePath": clip.get("sourcePath"),
                "sourceName": source_name(clip),
                "role": clip.get("role"),
                "purpose": clip.get("purpose"),
                "creatorFunction": clip.get("creatorFunction"),
                "editorialTier": clip.get("editorialTier") or clip.get("selectionTier"),
                "timelineStartSeconds": timeline_start(clip),
                "timelineEndSeconds": timeline_end(clip),
            }
        )
    return out


def build_sequence_row(row: dict[str, Any], clips: list[dict[str, Any]]) -> dict[str, Any]:
    seq_type = sequence_type(row)
    anchor = row_anchor(row)
    beats = []
    missing_required = 0
    for beat in required_beats(seq_type):
        evidence = candidates_for_beat(clips, beat["function"], row, anchor)
        status = "ready_with_local_candidate" if evidence else "needs_bridge_beat_selection"
        if beat["required"] and not evidence:
            missing_required += 1
        beats.append({**beat, "status": status, "localCandidateEvidence": evidence})

    bgm_cue = clean_words(row.get("bgmPhraseCue") or "cut_or_effect_on_bgm_phrase_boundary")
    title_safe = row.get("boundaryCategory") not in TITLE_CATEGORIES or "title" in str(row.get("titleZonePolicy") or "")
    has_repair = row.get("status") not in {"ready_with_transition_motif", "ready_for_resolve_execution", None}
    status = "ready_with_bridge_sequence" if missing_required == 0 and bgm_cue and title_safe and not has_repair else "needs_bridge_sequence_repair"
    target_duration = round(sum(float(beat["idealDurationSeconds"]) for beat in beats), 2)
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": row.get("boundaryCategory"),
        "sequenceType": seq_type,
        "fromClip": row.get("fromClip"),
        "toClip": row.get("toClip"),
        "transitionMotif": row.get("motif"),
        "executionStyle": row.get("executionStyle"),
        "targetDurationSeconds": {"min": max(2.0, target_duration - 2.0), "ideal": target_duration, "max": target_duration + 4.0},
        "bgmPhraseCue": bgm_cue,
        "titleZonePolicy": row.get("titleZonePolicy"),
        "titleZoneSafe": title_safe,
        "requiredBeats": beats,
        "missingRequiredBeatCount": missing_required,
        "status": status,
        "decision": dict(DECISION_FIELDS),
    }


def repair_rows(rows: list[dict[str, Any]], motif_repairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    for row in rows:
        missing = int(row.get("missingRequiredBeatCount") or 0)
        if missing:
            repairs.append(
                {
                    "repairId": f"bridge_sequence_row_{row.get('rowIndex')}_missing_beats",
                    "priority": "P0",
                    "issueType": "missing_bridge_sequence_beats",
                    "transitionRowIndices": [row.get("rowIndex")],
                    "ownerScript": "prepare_footage_select_plan.py",
                    "requiredArtifact": "footage_select_plan/footage_select_plan.json",
                    "repairAction": "Select local route/street/transport/texture/establishing clips for each missing bridge beat; use stock/aerial fallback only after local footage is proven insufficient.",
                    "acceptanceEvidence": "bridge_sequence_plan row has zero missingRequiredBeatCount and selectedBeatClipPaths maps every required beat.",
                    "status": "needs_repair",
                    "decision": dict(REPAIR_DECISION_FIELDS),
                }
            )
        if not row.get("titleZoneSafe"):
            repairs.append(
                {
                    "repairId": f"bridge_sequence_row_{row.get('rowIndex')}_title_zone",
                    "priority": "P0",
                    "issueType": "title_zone_sequence_risk",
                    "transitionRowIndices": [row.get("rowIndex")],
                    "ownerScript": "prepare_title_typography_plan.py",
                    "requiredArtifact": "title_typography_plan/title_typography_plan.json",
                    "repairAction": "Suppress captions and extra route/date text during clean title bridge beats before Resolve apply.",
                    "acceptanceEvidence": "titleZoneSafe is true and title bridge contract passes after Resolve readback.",
                    "status": "needs_repair",
                    "decision": dict(REPAIR_DECISION_FIELDS),
                }
            )
    for repair in motif_repairs:
        if not isinstance(repair, dict):
            continue
        repairs.append(
            {
                "repairId": f"motif_dependency_{clean_words(repair.get('repairId') or 'unknown', 80)}",
                "priority": repair.get("priority") or "P1",
                "issueType": "upstream_transition_motif_dependency",
                "transitionRowIndices": repair.get("transitionRowIndices") or [],
                "ownerScript": repair.get("ownerScript") or "prepare_transition_motif_plan.py",
                "requiredArtifact": repair.get("requiredArtifact") or "transition_motif_plan/transition_motif_plan.json",
                "repairAction": "Resolve the upstream transition motif repair before approving the bridge sequence.",
                "acceptanceEvidence": repair.get("acceptanceEvidence") or "transition_motif_plan repair is closed and bridge_sequence_plan is regenerated.",
                "status": "needs_review",
                "decision": dict(REPAIR_DECISION_FIELDS),
            }
        )
    return repairs


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    lookup = creator_lookup(creator_rows(package_dir))
    clips = [enrich_clip(row, lookup) for row in video_clips(blueprint)]
    motif = load_json(package_dir / "transition_motif_plan" / "transition_motif_plan.json") or {}
    motif_repairs = motif.get("repairRows") if isinstance(motif.get("repairRows"), list) else []
    sequence_rows = [build_sequence_row(row, clips) for row in transition_rows(package_dir)]

    decision_keys = set(DECISION_FIELDS)
    rows_with_decisions = sum(1 for row in sequence_rows if decision_keys.issubset(set((row.get("decision") or {}).keys())))
    row_count = len(sequence_rows)
    total_beats = sum(len(row.get("requiredBeats") or []) for row in sequence_rows)
    beats_with_candidates = sum(
        1
        for row in sequence_rows
        for beat in row.get("requiredBeats") or []
        if beat.get("localCandidateEvidence")
    )
    rows_with_all_candidates = sum(1 for row in sequence_rows if int(row.get("missingRequiredBeatCount") or 0) == 0)
    rows_title_safe = sum(1 for row in sequence_rows if row.get("titleZoneSafe"))
    rows_bgm = sum(1 for row in sequence_rows if row.get("bgmPhraseCue"))
    rows_ready = sum(1 for row in sequence_rows if row.get("status") == "ready_with_bridge_sequence")
    missing_beat_rows = sum(1 for row in sequence_rows if int(row.get("missingRequiredBeatCount") or 0) > 0)
    repairs = repair_rows(sequence_rows, motif_repairs)
    status = (
        "ready_with_bridge_sequence_plan"
        if row_count
        and rows_with_decisions == row_count
        and rows_ready == row_count
        and missing_beat_rows == 0
        and len(repairs) == 0
        else ("blocked_missing_transition_inputs" if not row_count else "needs_bridge_sequence_repair")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "transitionMotifPlan": str(package_dir / "transition_motif_plan" / "transition_motif_plan.json"),
            "transitionExecutionPlan": str(package_dir / "transition_execution_plan" / "transition_execution_plan.json"),
            "transitionGrammarPlan": str(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "creatorCutPlan": str(package_dir / "creator_cut_plan" / "creator_cut_plan.json"),
            "editRhythmPlan": str(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json"),
        },
        "summary": {
            "sequenceRowCount": row_count,
            "rowsReadyWithSequence": rows_ready,
            "rowsWithDecisionFields": rows_with_decisions,
            "totalRequiredBeatCount": total_beats,
            "requiredBeatsWithLocalCandidates": beats_with_candidates,
            "rowsWithAllRequiredBeatCandidates": rows_with_all_candidates,
            "missingBeatRowCount": missing_beat_rows,
            "rowsWithBgmPhraseCue": rows_bgm,
            "titleBoundaryRowsSafe": rows_title_safe,
            "repairRowCount": len(repairs),
            "blockingBridgeSequenceIssueCount": missing_beat_rows + len(repairs),
            "sourceVideoClipCount": len(clips),
        },
        "upstreamEvidence": {
            "transitionMotif": upstream_summary(package_dir, "transition_motif_plan/transition_motif_plan.json"),
            "transitionExecution": upstream_summary(package_dir, "transition_execution_plan/transition_execution_plan.json"),
            "transitionGrammar": upstream_summary(package_dir, "transition_grammar_plan/transition_grammar_plan.json"),
            "transitionBridge": upstream_summary(package_dir, "transition_bridge_plan/transition_bridge_plan.json"),
            "creatorCut": upstream_summary(package_dir, "creator_cut_plan/creator_cut_plan.json"),
            "editRhythm": upstream_summary(package_dir, "edit_rhythm_plan/edit_rhythm_plan.json"),
        },
        "policy": {
            "multiShotBridgeSequencesRequired": True,
            "twoToFiveBeatBridgeShape": True,
            "localFootageFirst": True,
            "effectIsLastMileOnly": True,
            "bgmPhraseCueRequired": True,
            "titleZoneSafetyRequired": True,
            "noBlackCardHardJump": True,
            "noRandomTransitionEffectAsBridge": True,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "sequenceRows": sequence_rows,
        "repairRows": repairs,
        "selectionRubric": {
            "pass": [
                "Important title, route, chapter, and timeline-gap boundaries are represented as 2-5 shot bridge sequences, not just one transition effect.",
                "Every required beat has local candidate evidence or an approved verified fallback before the plan can be marked ready.",
                "Route jumps include movement, arrival, and lived-in texture when source footage supports it.",
                "Title bridge beats suppress subtitles and extra route/date text.",
                "BGM phrase cues map the bridge sequence timing instead of cutting randomly across the music.",
            ],
            "reject": [
                "A city/day/place jump relies on a single dissolve, spin, black card, or title card.",
                "A transition effect is used where a route-motion or lived-in bridge beat is missing.",
                "The bridge sequence has no selected local footage and no verified stock/aerial fallback decision.",
                "Captions or route/date labels overlap the clean title hold.",
            ],
        },
        "nextActions": [
            "Review sequenceRows before rhythm recut or Resolve apply.",
            "Fill selectedBeatClipPaths for every required beat that will enter the timeline.",
            "Use prepare_rhythm_recut_blueprint.py after this plan so selected bridge beats become candidate cutaways.",
            "After Resolve apply, paste timeline readback and frame-sample evidence into sequence row decisions.",
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
        "# Bridge Sequence Plan",
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
        "## Sequence Rows",
    ]
    for row in plan["sequenceRows"]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('sequenceType')}",
                f"- Status: `{row.get('status')}`",
                f"- From: `{source_name(row.get('fromClip'))}`",
                f"- To: `{source_name(row.get('toClip'))}`",
                f"- Target duration: `{row.get('targetDurationSeconds')}`",
                f"- BGM cue: {row.get('bgmPhraseCue')}",
                "- Required beats:",
            ]
        )
        for beat in row.get("requiredBeats") or []:
            lines.append(f"  - `{beat.get('function')}` ({beat.get('idealDurationSeconds')}s): {beat.get('purpose')}")
            evidence = beat.get("localCandidateEvidence") or []
            if evidence:
                for item in evidence[:3]:
                    lines.append(f"    - candidate `{item.get('sourceName')}` score={item.get('score')} role=`{item.get('role')}`")
            else:
                lines.append("    - missing local candidate; fill repair row before Resolve apply")
        lines.append("- Decision fields:")
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Repair Rows"])
    if not plan["repairRows"]:
        lines.append("- None.")
    for row in plan["repairRows"]:
        lines.append(f"- `{row.get('repairId')}` {row.get('priority')}: {row.get('repairAction')} Owner `{row.get('ownerScript')}`")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare multi-shot bridge sequence rows for a travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/bridge_sequence_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "bridge_sequence_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "bridge_sequence_plan.json", plan)
    write_markdown(output_dir / "bridge_sequence_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": plan["status"],
                    "outputDir": str(output_dir),
                    "sequenceRowCount": plan["summary"]["sequenceRowCount"],
                    "missingBeatRowCount": plan["summary"]["missingBeatRowCount"],
                    "repairRowCount": plan["summary"]["repairRowCount"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
