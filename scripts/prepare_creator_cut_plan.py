#!/usr/bin/env python3
"""Prepare a creator-style shot selection, transition, and rejection plan."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


HERO_TERMS = (
    "aerial",
    "drone",
    "skyline",
    "coast",
    "mountain",
    "landmark",
    "tower",
    "castle",
    "temple",
    "shrine",
    "bridge",
    "harbor",
    "sea",
    "ocean",
    "sunset",
    "night",
    "establish",
    "title",
    "航拍",
    "天际线",
    "海",
    "山",
    "地标",
    "城堡",
    "寺",
    "神社",
    "桥",
    "夜景",
)

MOVEMENT_TERMS = (
    "airport",
    "station",
    "train",
    "subway",
    "metro",
    "taxi",
    "car",
    "bus",
    "ferry",
    "boat",
    "plane",
    "road",
    "window",
    "walking",
    "walk",
    "pan",
    "tilt",
    "turn",
    "tracking",
    "escalator",
    "elevator",
    "route",
    "transfer",
    "机场",
    "车站",
    "火车",
    "地铁",
    "出租",
    "车窗",
    "步行",
    "路",
    "渡轮",
    "飞机",
)

LIVED_IN_TERMS = (
    "food",
    "restaurant",
    "hotel",
    "room",
    "shop",
    "street",
    "market",
    "ticket",
    "sign",
    "map",
    "weather",
    "rain",
    "crowd",
    "waiting",
    "luggage",
    "table",
    "店",
    "饭",
    "酒店",
    "房间",
    "街",
    "市场",
    "票",
    "路牌",
    "地图",
    "天气",
    "雨",
    "人群",
    "行李",
)

WEAK_TERMS = (
    "black",
    "placeholder",
    "title_cards",
    "slate",
    "test",
    "sample",
    "blur",
    "obstruct",
    "shaky",
    "duplicate",
    "generic",
    "dark",
    "黑屏",
    "占位",
    "模糊",
    "遮挡",
    "重复",
)

DECISION_FIELDS = {
    "approvedUse": "",
    "targetDurationSeconds": None,
    "trimStartSeconds": None,
    "trimEndSeconds": None,
    "bridgeBefore": "",
    "bridgeAfter": "",
    "selectedTransitionEffect": "",
    "bgmPhraseCue": "",
    "captionFunction": "",
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


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


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
            "name",
            "notes",
        )
    ).lower()


def clip_duration(clip: dict[str, Any]) -> float:
    start = as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"))
    end = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if start is not None and end is not None and end > start:
        return end - start
    for key in ("durationSeconds", "sourceDurationSeconds"):
        duration = as_float(clip.get(key))
        if duration and duration > 0:
            return duration
    source_start = as_float(clip.get("sourceStartSeconds"), 0.0) or 0.0
    source_end = as_float(clip.get("sourceEndSeconds"), 0.0) or 0.0
    return max(0.0, source_end - source_start)


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    start = timeline_start(clip)
    if explicit is not None and explicit > start:
        return explicit
    return start + clip_duration(clip)


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


def rhythm_risk_lookup(package_dir: Path) -> dict[str, list[str]]:
    data = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
    rows = data.get("shotRows") if isinstance(data.get("shotRows"), list) else []
    lookup: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("sourcePath") or row.get("sourceName") or "")
        risks = [str(item) for item in row.get("riskReasons") or []]
        if key and risks:
            lookup[key] = risks
    return lookup


def score_clip(text: str, duration: float, rhythm_risks: list[str]) -> tuple[int, list[str]]:
    score = 45
    signals: list[str] = []
    if contains_any(text, HERO_TERMS):
        score += 25
        signals.append("high_recognition_or_payoff")
    if contains_any(text, MOVEMENT_TERMS):
        score += 18
        signals.append("route_movement")
    if contains_any(text, LIVED_IN_TERMS):
        score += 16
        signals.append("lived_in_texture")
    if "opening" in text or "ending" in text:
        score += 10
        signals.append("structure_anchor")
    if duration < 1.0:
        score -= 20
        signals.append("too_short_to_register")
    if duration > 18:
        score -= 14
        signals.append("long_hold_needs_cutaway")
    if duration > 30:
        score -= 12
        signals.append("very_long_raw_hold")
    if contains_any(text, WEAK_TERMS):
        score -= 30
        signals.append("weak_or_placeholder_signal")
    if rhythm_risks:
        score -= min(18, 6 * len(rhythm_risks))
        signals.extend(f"rhythm_{risk}" for risk in rhythm_risks[:3])
    return max(0, min(100, score)), signals


def creator_function(text: str, score: int) -> str:
    if "opening" in text:
        return "opening_hook"
    if "ending" in text:
        return "ending_aftertaste"
    if "title" in text:
        return "title_bridge"
    if contains_any(text, MOVEMENT_TERMS):
        return "route_movement"
    if contains_any(text, LIVED_IN_TERMS):
        return "lived_in_detail"
    if contains_any(text, HERO_TERMS):
        return "destination_payoff"
    if score < 35:
        return "reject_review"
    return "route_observation"


def editorial_tier(score: int, function: str) -> str:
    if function == "reject_review" or score < 35:
        return "reject_or_replace"
    if score >= 78 or function in {"opening_hook", "ending_aftertaste", "destination_payoff"}:
        return "hero"
    if score >= 62:
        return "main_story"
    if function in {"route_movement", "lived_in_detail", "title_bridge"}:
        return "texture_bridge"
    return "utility_only"


def recommended_use(tier: str, function: str, duration: float) -> dict[str, Any]:
    if tier == "reject_or_replace":
        return {"use": "exclude_or_replace", "targetDurationRangeSeconds": [0, 0], "reason": "Weak or redundant source should not lead the film."}
    if function == "title_bridge":
        return {"use": "use_for_title_background", "targetDurationRangeSeconds": [3, 6], "reason": "Title should read, then leave before it feels like a card."}
    if function == "route_movement":
        return {"use": "use_as_transition_bridge", "targetDurationRangeSeconds": [3, 9], "reason": "Route evidence should connect chapters without overstaying."}
    if function == "ending_aftertaste":
        return {"use": "keep_as_ending_aftertaste", "targetDurationRangeSeconds": [6, 14], "reason": "Let the ending breathe with BGM and quiet route residue."}
    if duration > 18:
        return {"use": "trim_or_split_with_cutaways", "targetDurationRangeSeconds": [4, 9], "reason": "Long raw holds need creator-style selection."}
    if tier == "hero":
        return {"use": "keep_primary_payoff", "targetDurationRangeSeconds": [5, 12], "reason": "Strong image can carry a chapter beat or title."}
    if tier == "main_story":
        return {"use": "keep_or_fine_trim", "targetDurationRangeSeconds": [3, 8], "reason": "Story clip is useful but should stay concise."}
    return {"use": "use_as_cutaway_or_texture", "targetDurationRangeSeconds": [1.5, 5], "reason": "Texture clip should support, not dominate, the chapter."}


def transition_recipe(function: str, text: str, tier: str) -> dict[str, Any]:
    has_motion = contains_any(text, MOVEMENT_TERMS)
    if tier == "reject_or_replace":
        style = "none"
        allowed = False
        reason = "Rejected clips should not be rescued with effects."
    elif has_motion and function in {"route_movement", "opening_hook", "ending_aftertaste"}:
        style = "motivated whip-pan or rotation match cut"
        allowed = True
        reason = "Use only when adjacent clips share camera/vehicle/walking direction or route energy."
    elif function in {"destination_payoff", "lived_in_detail"}:
        style = "match cut or short dissolve"
        allowed = True
        reason = "Use visual association, color, shape, weather, food, water, or skyline continuity."
    else:
        style = "straight cut or gentle dissolve"
        allowed = True
        reason = "Keep motion subtle unless real movement motivates it."
    return {
        "style": style,
        "effectAllowed": allowed,
        "reason": reason,
        "mustAvoid": [
            "random spin",
            "flash/glitch/shake template",
            "transition masking missing bridge footage",
            "effect during unreadable title text",
        ],
    }


def build_shot_rows(package_dir: Path, clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rhythm_lookup = rhythm_risk_lookup(package_dir)
    rows: list[dict[str, Any]] = []
    for index, clip in enumerate(clips, start=1):
        text = clip_text(clip)
        duration = clip_duration(clip)
        key = str(clip.get("sourcePath") or source_name(clip))
        risks = rhythm_lookup.get(key) or rhythm_lookup.get(source_name(clip)) or []
        score, signals = score_clip(text, duration, risks)
        function = creator_function(text, score)
        tier = editorial_tier(score, function)
        use = recommended_use(tier, function, duration)
        recipe = transition_recipe(function, text, tier)
        row = {
            "rowIndex": index,
            "creatorFunction": function,
            "editorialTier": tier,
            "creatorScore": score,
            "timelineStartSeconds": round(timeline_start(clip), 3),
            "timelineEndSeconds": round(timeline_end(clip), 3),
            "durationSeconds": round(duration, 3),
            "chapterIndex": clip.get("chapterIndex"),
            "trackIndex": clip.get("trackIndex"),
            "sourcePath": clip.get("sourcePath"),
            "sourceName": source_name(clip),
            "blueprintRole": clip.get("role"),
            "purpose": clip.get("purpose"),
            "place": clip.get("place"),
            "signals": signals,
            "rhythmRisks": risks,
            "recommendedUse": use,
            "transitionRecipe": recipe,
            "status": "needs_creator_decision" if tier in {"reject_or_replace", "utility_only"} or risks else "has_creator_function",
            "decision": dict(DECISION_FIELDS),
        }
        rows.append(row)
    return rows


def chapter_rows(shot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in shot_rows:
        key = str(row.get("chapterIndex") if row.get("chapterIndex") is not None else "unassigned")
        grouped.setdefault(key, []).append(row)
    chapters: list[dict[str, Any]] = []
    required = {"route_movement", "lived_in_detail", "destination_payoff"}
    for key, rows in sorted(grouped.items(), key=lambda item: (9999 if item[0] == "unassigned" else int(float(item[0])), item[0])):
        functions = sorted({str(row.get("creatorFunction")) for row in rows})
        tiers: dict[str, int] = {}
        for row in rows:
            tier = str(row.get("editorialTier") or "")
            tiers[tier] = tiers.get(tier, 0) + 1
        missing = sorted(required - set(functions))
        chapters.append(
            {
                "chapterIndex": key,
                "shotCount": len(rows),
                "functionCount": len(functions),
                "creatorFunctions": functions,
                "tierCounts": tiers,
                "missingCreatorFunctions": missing,
                "rejectOrUtilityCount": tiers.get("reject_or_replace", 0) + tiers.get("utility_only", 0),
                "recommendedPattern": [
                    "open with place identity",
                    "show route or movement",
                    "insert lived-in texture",
                    "pay off with the strongest place/experience shot",
                    "leave with aftertaste or bridge footage",
                ],
                "status": "needs_creator_coverage" if missing or len(functions) < 3 else "has_creator_chapter_shape",
                "decision": {
                    "approvedChapterShape": "",
                    "replaceOrDropRows": [],
                    "requiredBridgeInsert": "",
                    "requiredTextureInsert": "",
                    "endingOrAftertasteNote": "",
                    "resolveImplementation": "",
                    "readbackEvidence": "",
                    "approvedBy": "",
                    "approvedAt": "",
                    "editorNotes": "",
                },
            }
        )
    return chapters


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    blueprint = load_json(blueprint_path) or {}
    clips = video_clips(blueprint)
    rows = build_shot_rows(package_dir, clips)
    chapters = chapter_rows(rows)
    durations = [float(row.get("durationSeconds") or 0) for row in rows if float(row.get("durationSeconds") or 0) > 0]
    tier_counts: dict[str, int] = {}
    function_counts: dict[str, int] = {}
    for row in rows:
        tier = str(row.get("editorialTier") or "")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        function = str(row.get("creatorFunction") or "")
        function_counts[function] = function_counts.get(function, 0) + 1
    rows_with_decisions = sum(1 for row in rows if isinstance(row.get("decision"), dict) and set(DECISION_FIELDS).issubset(set(row["decision"])))
    rotation_candidates = sum(1 for row in rows if "rotation" in str((row.get("transitionRecipe") or {}).get("style") or ""))
    bridge_candidates = sum(1 for row in rows if row.get("creatorFunction") == "route_movement")
    reject_or_utility = tier_counts.get("reject_or_replace", 0) + tier_counts.get("utility_only", 0)
    status = (
        "ready_with_creator_cut_plan"
        if blueprint_path.exists() and rows and rows_with_decisions == len(rows)
        else ("needs_creator_cut_inputs" if blueprint_path.exists() else "blocked_missing_resolve_blueprint")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(blueprint_path),
            "editRhythmPlan": str(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "effectMotionPlan": str(package_dir / "effect_motion_plan" / "effect_motion_plan.json"),
        },
        "summary": {
            "primaryVisualShotCount": len(rows),
            "chapterRowCount": len(chapters),
            "averageShotSeconds": round(sum(durations) / len(durations), 3) if durations else 0.0,
            "medianShotSeconds": round(statistics.median(durations), 3) if durations else 0.0,
            "tierCounts": tier_counts,
            "functionCounts": function_counts,
            "creatorDecisionRowCount": rows_with_decisions,
            "rejectOrUtilityCount": reject_or_utility,
            "routeBridgeCandidateCount": bridge_candidates,
            "motivatedRotationCandidateCount": rotation_candidates,
            "chaptersNeedingCreatorCoverage": sum(1 for row in chapters if row.get("status") == "needs_creator_coverage"),
        },
        "policy": {
            "selectiveShotChoiceRequired": True,
            "weakClipsCanBeRejected": True,
            "everyKeptShotNeedsCreatorFunction": True,
            "physicalBridgeBeforeEffect": True,
            "motivatedWhipOrRotationAllowed": True,
            "templateEffectsRejected": True,
            "referenceAnchoredButNonCopying": True,
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
        "chapterRows": chapters,
        "shotRows": rows,
        "selectionRubric": {
            "pass": [
                "Every kept clip has a creator function such as opening, route movement, lived-in detail, payoff, or ending aftertaste.",
                "Weak, duplicate, placeholder, or long raw clips are demoted, trimmed, or rejected instead of being kept by default.",
                "Every chapter has at least three creator functions and does not rely only on landmarks or title cards.",
                "Whip-pan or rotation transitions are only recommended when real movement or route energy motivates them.",
                "BGM, captions, route bridges, and shot choice work together instead of hiding weak footage with effects.",
            ],
            "reject": [
                "A flat timeline where most clips are kept at source length without a creator function.",
                "A transition effect added because the boundary is weak rather than because motion/route evidence supports it.",
                "A chapter with only scenery and no transport, street, lived-in detail, or aftertaste.",
                "Creator-style claims based on reference names while the shot selection plan is missing.",
            ],
        },
        "nextActions": [
            "Drop or shorten reject_or_replace and utility_only rows before Resolve apply unless they are needed for route honesty.",
            "Use route_movement rows as first-choice transition bridges before adding stock or effects.",
            "Use motivated rotation/whip transitions only for rows marked as rotation candidates and only after adjacent footage is reviewed.",
            "After Resolve apply, paste timeline readback evidence into decision fields and rerun reference-style, route-texture, director-intent, and director-polish audits.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Creator Cut Plan",
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
        "## Chapter Rows",
    ]
    for row in plan["chapterRows"]:
        lines.extend(
            [
                "",
                f"### Chapter {row['chapterIndex']}",
                f"- Status: `{row['status']}`",
                f"- Functions: `{', '.join(row['creatorFunctions'])}`",
                f"- Missing: `{', '.join(row['missingCreatorFunctions']) if row['missingCreatorFunctions'] else 'none'}`",
                f"- Reject/utility count: `{row['rejectOrUtilityCount']}`",
            ]
        )
    lines.extend(["", "## Rows Needing Editor Decision"])
    decision_rows = [row for row in plan["shotRows"] if row.get("status") == "needs_creator_decision"]
    if not decision_rows:
        lines.append("- None.")
    for row in decision_rows[:100]:
        recipe = row.get("transitionRecipe") if isinstance(row.get("transitionRecipe"), dict) else {}
        use = row.get("recommendedUse") if isinstance(row.get("recommendedUse"), dict) else {}
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['creatorFunction']} / {row['editorialTier']}",
                f"- Window: `{row['timelineStartSeconds']}` to `{row['timelineEndSeconds']}` ({row['durationSeconds']}s)",
                f"- Source: `{row.get('sourceName')}`",
                f"- Score: `{row['creatorScore']}`",
                f"- Signals: `{', '.join(row.get('signals') or [])}`",
                f"- Recommended use: `{use.get('use')}`",
                f"- Transition recipe: `{recipe.get('style')}`",
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
    parser = argparse.ArgumentParser(description="Prepare a creator-style cut plan for a travel package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/creator_cut_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "creator_cut_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "creator_cut_plan.json", plan)
    write_markdown(output_dir / "creator_cut_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
