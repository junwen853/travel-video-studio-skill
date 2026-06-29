#!/usr/bin/env python3
"""Prepare pair-level transition grammar rows for adjacent timeline clips."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


MOTION_TERMS = (
    "pan",
    "tilt",
    "turn",
    "rotate",
    "walk",
    "walking",
    "tracking",
    "window",
    "vehicle",
    "car",
    "taxi",
    "bus",
    "train",
    "ferry",
    "boat",
    "plane",
    "road",
    "water",
    "aerial",
    "drone",
    "crowd",
    "escalator",
    "elevator",
    "车",
    "车窗",
    "走",
    "路",
    "水",
    "航拍",
)

BRIDGE_TERMS = (
    "airport",
    "station",
    "terminal",
    "train",
    "metro",
    "subway",
    "taxi",
    "road",
    "window",
    "ferry",
    "boat",
    "bridge",
    "walking",
    "sign",
    "map",
    "ticket",
    "hotel",
    "weather",
    "rain",
    "night",
    "sunset",
    "food",
    "street",
    "skyline",
    "water",
    "机场",
    "车站",
    "地铁",
    "桥",
    "路牌",
    "地图",
    "酒店",
    "天气",
    "夜",
    "街",
)

MATCH_TERMS = (
    "window",
    "skyline",
    "sky",
    "cloud",
    "mountain",
    "coast",
    "sea",
    "water",
    "road",
    "bridge",
    "sign",
    "food",
    "table",
    "street",
    "night",
    "neon",
    "color",
    "shape",
    "reflection",
    "crowd",
    "camera",
    "aerial",
    "walking",
    "station",
    "hotel",
    "map",
    "窗",
    "天空",
    "云",
    "山",
    "海",
    "水",
    "路",
    "桥",
    "招牌",
    "街",
    "人群",
    "颜色",
    "形状",
    "反光",
    "夜景",
)

MOOD_TERMS = (
    "night",
    "sunset",
    "rain",
    "weather",
    "quiet",
    "ending",
    "aftertaste",
    "scenic",
    "dusk",
    "夜",
    "雨",
    "安静",
)

TITLE_TERMS = ("title", "opening_city", "chapter_title", "ending_city", "title_bridge")

DECISION_FIELDS = {
    "approvedTransitionType": "",
    "fallbackTransitionType": "",
    "durationFrames": None,
    "requiresBridgeInsert": False,
    "bridgeInsertSource": "",
    "storyboardPurpose": "",
    "outgoingShotEvidence": "",
    "bridgeOrMotionBeatEvidence": "",
    "landingShotEvidence": "",
    "previewStripEvidence": "",
    "frameSampleEvidence": "",
    "motionDirection": "",
    "bgmPhraseCue": "",
    "captionSuppressionNeeded": False,
    "resolveImplementation": "",
    "readbackEvidence": "",
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


def clean_words(value: Any, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath", "name", "notes")
    ).lower()


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def source_name(clip: dict[str, Any]) -> str:
    source = str(clip.get("sourcePath") or "")
    return Path(source).name if source else ""


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


def creator_lookup(package_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    rows = data.get("shotRows") if isinstance(data.get("shotRows"), list) else []
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in (row.get("sourcePath"), row.get("sourceName")):
            if key:
                lookup[str(key)] = row
    return lookup


def bridge_plan_evidence(package_dir: Path) -> dict[str, Any]:
    data = load_json(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json") or {}
    rows = data.get("boundaryRows") if isinstance(data.get("boundaryRows"), list) else []
    return {
        "exists": bool(data),
        "status": data.get("status"),
        "boundaryRowCount": len(rows),
        "readyRows": sum(1 for row in rows if isinstance(row, dict) and row.get("status") in {"has_bridge_evidence", "ready_with_bridge_evidence"}),
    }


def pair_category(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_chapter = left.get("chapterIndex")
    right_chapter = right.get("chapterIndex")
    left_text = clip_text(left)
    right_text = clip_text(right)
    if contains_any(left_text + " " + right_text, TITLE_TERMS):
        return "title_boundary"
    if left_chapter is not None and right_chapter is not None and str(left_chapter) != str(right_chapter):
        return "chapter_boundary"
    gap = timeline_start(right) - timeline_end(left)
    if gap > 0.2:
        return "timeline_gap"
    if "ending" in right_text or "ending" in left_text:
        return "ending_transition"
    return "same_chapter_cut"


def recommend_transition(category: str, left_text: str, right_text: str) -> dict[str, Any]:
    combined = f"{left_text} {right_text}"
    left_motion = contains_any(left_text, MOTION_TERMS)
    right_motion = contains_any(right_text, MOTION_TERMS)
    bridge_evidence = contains_any(combined, BRIDGE_TERMS)
    mood_shift = contains_any(combined, MOOD_TERMS)
    shared_matches = sorted(set(matched_terms(left_text, MATCH_TERMS)).intersection(matched_terms(right_text, MATCH_TERMS)))

    if category in {"chapter_boundary", "timeline_gap"} and not bridge_evidence:
        transition = "insert_bridge_first"
        fallback = "short_dissolve_after_bridge"
        duration = 0
        allowed_motion = False
        reason = "Chapter/place boundary lacks physical route evidence."
    elif left_motion and right_motion and bridge_evidence:
        transition = "whip_pan_match" if "pan" in combined or "walk" in combined or "车" in combined else "rotation_match_cut"
        fallback = "match_cut"
        duration = 10
        allowed_motion = True
        reason = "Both sides have route-motion energy and physical bridge evidence."
    elif shared_matches:
        transition = "match_cut"
        fallback = "straight_cut"
        duration = 4
        allowed_motion = False
        reason = f"Shared visual terms: {', '.join(shared_matches[:5])}."
    elif mood_shift or category in {"ending_transition", "title_boundary"}:
        transition = "short_dissolve"
        fallback = "straight_cut"
        duration = 12
        allowed_motion = False
        reason = "Mood, title, ending, weather, or time shift supports a dissolve."
    elif contains_any(combined, ("vehicle", "train", "ferry", "water", "aerial", "walking", "crowd", "road")):
        transition = "speed_ramp_bridge"
        fallback = "match_cut"
        duration = 8
        allowed_motion = True
        reason = "Real movement supports a short ramp if BGM phrasing fits."
    else:
        transition = "straight_cut"
        fallback = "short_dissolve"
        duration = 0
        allowed_motion = False
        reason = "Same-scene or low-motion pair should stay simple."

    return {
        "recommendedTransitionType": transition,
        "fallbackTransitionType": fallback,
        "durationFrames": duration,
        "motionEffectAllowed": allowed_motion,
        "physicalBridgeEvidence": bridge_evidence,
        "sharedMatchTerms": shared_matches,
        "reason": reason,
        "mustAvoid": [
            "random spin",
            "flash/glitch/shake template",
            "route jump without bridge footage",
            "effect over unreadable title",
            "source-camera voice under scenic transition",
        ],
    }


def transition_status(category: str, recommendation: dict[str, Any]) -> str:
    if recommendation.get("recommendedTransitionType") == "insert_bridge_first":
        return "needs_bridge_insert"
    if category in {"chapter_boundary", "timeline_gap"} and not recommendation.get("physicalBridgeEvidence"):
        return "needs_bridge_insert"
    return "ready_with_transition_grammar"


def storyboard_purpose(category: str, recommendation: dict[str, Any]) -> str:
    transition = str(recommendation.get("recommendedTransitionType") or "")
    if category == "chapter_boundary":
        return "route_move"
    if category == "timeline_gap":
        return "time_jump"
    if category == "title_boundary":
        return "title_reveal"
    if category == "ending_transition":
        return "ending_aftertaste"
    if "dissolve" in transition:
        return "scenic_breath"
    if "bridge" in transition:
        return "texture_bridge"
    if transition in {"whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}:
        return "bgm_handoff"
    return "same_scene_continuity"


def build_rows(package_dir: Path, clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = creator_lookup(package_dir)
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(clips, clips[1:]), start=1):
        left_text = clip_text(left)
        right_text = clip_text(right)
        category = pair_category(left, right)
        recommendation = recommend_transition(category, left_text, right_text)
        left_creator = lookup.get(str(left.get("sourcePath") or "")) or lookup.get(source_name(left)) or {}
        right_creator = lookup.get(str(right.get("sourcePath") or "")) or lookup.get(source_name(right)) or {}
        row = {
            "rowIndex": index,
            "boundaryCategory": category,
            "timelineStartSeconds": round(timeline_end(left), 3),
            "timelineGapSeconds": round(timeline_start(right) - timeline_end(left), 3),
            "fromClip": {
                "sourcePath": left.get("sourcePath"),
                "sourceName": source_name(left),
                "chapterIndex": left.get("chapterIndex"),
                "role": left.get("role"),
                "creatorFunction": left_creator.get("creatorFunction"),
                "editorialTier": left_creator.get("editorialTier"),
            },
            "toClip": {
                "sourcePath": right.get("sourcePath"),
                "sourceName": source_name(right),
                "chapterIndex": right.get("chapterIndex"),
                "role": right.get("role"),
                "creatorFunction": right_creator.get("creatorFunction"),
                "editorialTier": right_creator.get("editorialTier"),
            },
            "signals": {
                "fromMotionTerms": matched_terms(left_text, MOTION_TERMS),
                "toMotionTerms": matched_terms(right_text, MOTION_TERMS),
                "bridgeTerms": matched_terms(f"{left_text} {right_text}", BRIDGE_TERMS),
                "moodTerms": matched_terms(f"{left_text} {right_text}", MOOD_TERMS),
            },
            "recommendation": recommendation,
            "status": transition_status(category, recommendation),
            "decision": dict(DECISION_FIELDS),
        }
        row["decision"]["storyboardPurpose"] = storyboard_purpose(category, recommendation)
        row["decision"]["outgoingShotEvidence"] = " | ".join(
            item
            for item in (
                source_name(left),
                clean_words(left.get("role")),
                clean_words(left_creator.get("creatorFunction")),
            )
            if item
        )
        row["decision"]["bridgeOrMotionBeatEvidence"] = ", ".join(row["signals"]["bridgeTerms"]) or recommendation.get("reason") or ""
        row["decision"]["landingShotEvidence"] = " | ".join(
            item
            for item in (
                source_name(right),
                clean_words(right.get("role")),
                clean_words(right_creator.get("creatorFunction")),
            )
            if item
        )
        if recommendation.get("recommendedTransitionType") == "insert_bridge_first":
            row["decision"]["requiresBridgeInsert"] = True
        rows.append(row)
    return rows


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    blueprint = load_json(blueprint_path) or {}
    clips = video_clips(blueprint)
    rows = build_rows(package_dir, clips)
    decision_keys = set(DECISION_FIELDS)
    rows_with_decisions = sum(1 for row in rows if isinstance(row.get("decision"), dict) and decision_keys.issubset(set(row["decision"])))
    rows_needing_bridge = sum(1 for row in rows if row.get("status") == "needs_bridge_insert")
    motion_candidates = sum(1 for row in rows if (row.get("recommendation") or {}).get("motionEffectAllowed") is True)
    bridge_evidence_count = sum(1 for row in rows if (row.get("recommendation") or {}).get("physicalBridgeEvidence") is True)
    style_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in rows:
        style = str((row.get("recommendation") or {}).get("recommendedTransitionType") or "")
        style_counts[style] = style_counts.get(style, 0) + 1
        category = str(row.get("boundaryCategory") or "")
        category_counts[category] = category_counts.get(category, 0) + 1
    status = (
        "ready_with_transition_grammar_plan"
        if blueprint_path.exists() and rows and rows_with_decisions == len(rows) and rows_needing_bridge == 0
        else ("needs_bridge_insert_decisions" if blueprint_path.exists() and rows else "blocked_missing_resolve_blueprint")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(blueprint_path),
            "creatorCutPlan": str(package_dir / "creator_cut_plan" / "creator_cut_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "effectMotionPlan": str(package_dir / "effect_motion_plan" / "effect_motion_plan.json"),
        },
        "summary": {
            "visualClipCount": len(clips),
            "transitionRowCount": len(rows),
            "chapterBoundaryCount": category_counts.get("chapter_boundary", 0),
            "titleBoundaryCount": category_counts.get("title_boundary", 0),
            "timelineGapCount": category_counts.get("timeline_gap", 0),
            "rowsWithDecisionFields": rows_with_decisions,
            "rowsNeedingBridgeInsert": rows_needing_bridge,
            "physicalBridgeEvidenceCount": bridge_evidence_count,
            "motivatedMotionEffectCandidateCount": motion_candidates,
            "recommendedStyleCounts": style_counts,
            "boundaryCategoryCounts": category_counts,
        },
        "bridgePlanEvidence": bridge_plan_evidence(package_dir),
        "policy": {
            "pairLevelTransitionDecisionsRequired": True,
            "physicalBridgeBeforeMotionEffect": True,
            "motivatedWhipOrRotationOnly": True,
            "templateTransitionsRejected": True,
            "titleZoneSafetyRequired": True,
            "bgmPhraseAwarenessRequired": True,
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
        "transitionRows": rows,
        "selectionRubric": {
            "pass": [
                "Every adjacent visual pair has an explicit transition recommendation and fallback.",
                "Chapter/day/place boundaries use physical bridge evidence before motion effects.",
                "Whip-pan, rotation, and speed-ramp rows cite real movement or route energy.",
                "Rows without bridge evidence require insert_bridge_first rather than an effect.",
                "Transition decisions align with creator-cut tiers and do not hide weak footage.",
            ],
            "reject": [
                "Random spin, flash, glitch, shake, or template transition as a default fix.",
                "Hard jump across places with only a title card and no route bridge.",
                "Whip/rotation across two static scenic shots.",
                "Transition effect covering unreadable title or leaking source-camera voice.",
            ],
        },
        "nextActions": [
            "Fill decision fields for rows that will be implemented in Resolve.",
            "For rows marked needs_bridge_insert, add transport/street/signage/weather/food/hotel/aerial bridge footage before choosing an effect.",
            "Map approved transition types into resolve_timeline_blueprint.json effectPlan only after bridge/title/audio safety checks pass.",
            "After Resolve apply, paste readback evidence and rerun route texture, director intent, director polish, and feedback regression audits.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Grammar Plan",
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
        "## Transition Rows",
    ]
    for row in plan["transitionRows"][:120]:
        rec = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['boundaryCategory']}",
                f"- Status: `{row['status']}`",
                f"- From: `{row['fromClip'].get('sourceName')}`",
                f"- To: `{row['toClip'].get('sourceName')}`",
                f"- Recommended: `{rec.get('recommendedTransitionType')}`",
                f"- Fallback: `{rec.get('fallbackTransitionType')}`",
                f"- Reason: {rec.get('reason')}",
                "- Decision fields to fill:",
            ]
        )
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare pair-level transition grammar for a travel package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_grammar_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_grammar_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "transition_grammar_plan.json", plan)
    write_markdown(output_dir / "transition_grammar_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
