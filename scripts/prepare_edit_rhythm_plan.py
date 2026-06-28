#!/usr/bin/env python3
"""Prepare a reference-anchored edit rhythm and shot-purpose plan."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


TRANSPORT_TERMS = (
    "airport",
    "terminal",
    "boarding",
    "flight",
    "train",
    "rail",
    "shinkansen",
    "station",
    "metro",
    "subway",
    "taxi",
    "road",
    "window",
    "bridge",
    "transfer",
    "机场",
    "列车",
    "新干线",
    "地铁",
    "车站",
    "航班",
)
STREET_TERMS = (
    "street",
    "walking",
    "city",
    "skyline",
    "shopping",
    "retail",
    "district",
    "canal",
    "river",
    "night",
    "crowd",
    "街",
    "城市",
    "街区",
    "人潮",
    "夜",
)
LIVED_IN_TERMS = (
    "hotel",
    "food",
    "dinner",
    "shop",
    "interior",
    "convenience",
    "waiting",
    "table",
    "restaurant",
    "drink",
    "酒店",
    "便利店",
    "餐",
    "店",
    "室内",
    "等待",
)
LANDMARK_TERMS = (
    "castle",
    "tower",
    "temple",
    "shrine",
    "dotonbori",
    "akihabara",
    "ginza",
    "asakusa",
    "senso",
    "skytree",
    "大阪城",
    "东京塔",
    "寺",
    "神社",
    "道顿堀",
    "秋叶原",
    "银座",
)
PLACEHOLDER_TERMS = ("title_cards", "black slate", "placeholder", "slideshow", "generic")

DECISION_FIELDS = {
    "keepOrRetimingDecision": "",
    "approvedRhythmRole": "",
    "targetDurationSeconds": None,
    "trimStartSeconds": None,
    "trimEndSeconds": None,
    "cutawayBefore": "",
    "cutawayAfter": "",
    "replacementOrInsertSource": "",
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


def clean_words(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(first_present(clip.get("timelineStartSeconds"), clip.get("recordStartSeconds"), clip.get("startSeconds")), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(first_present(clip.get("timelineEndSeconds"), clip.get("recordEndSeconds"), clip.get("endSeconds")))
    if explicit is not None and explicit > start:
        return explicit
    duration = clip_duration(clip)
    return start + duration


def clip_duration(clip: dict[str, Any]) -> float:
    start = as_float(first_present(clip.get("timelineStartSeconds"), clip.get("recordStartSeconds"), clip.get("startSeconds")))
    end = as_float(first_present(clip.get("timelineEndSeconds"), clip.get("recordEndSeconds"), clip.get("endSeconds")))
    if start is not None and end is not None and end > start:
        return end - start
    for key in ("durationSeconds", "sourceDurationSeconds"):
        value = as_float(clip.get(key))
        if value and value > 0:
            return value
    source_start = as_float(clip.get("sourceStartSeconds"), 0.0) or 0.0
    source_end = as_float(clip.get("sourceEndSeconds"), 0.0) or 0.0
    return max(0.0, source_end - source_start)


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath")).lower()


def source_name(clip: dict[str, Any]) -> str:
    value = str(clip.get("sourcePath") or "")
    return Path(value).name if value else ""


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
    return sorted(out, key=lambda clip: (timeline_start(clip), int(as_float(clip.get("trackIndex"), 1) or 1)))


def find_reference_analysis(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_reference = os.environ.get("TRAVEL_VIDEO_REFERENCE_ANALYSIS")
    candidates = [
        package_dir / "reference" / "reference_analysis.json",
    ]
    if env_reference:
        candidates.insert(0, Path(env_reference).expanduser())
    return next((path.resolve() for path in candidates if path.exists()), None)


def reference_profile(path: Path | None) -> dict[str, Any]:
    data = load_json(path) or {}
    pacing = data.get("pacingProfile") if isinstance(data.get("pacingProfile"), dict) else {}
    audio = data.get("audioProfile") if isinstance(data.get("audioProfile"), dict) else {}
    samples = data.get("sampleFrames") if isinstance(data.get("sampleFrames"), list) else []
    return {
        "referenceAnalysis": str(path) if path else None,
        "exists": bool(path and path.exists()),
        "profileAvailable": bool(pacing),
        "pacingStatus": pacing.get("status"),
        "estimatedShotCount": pacing.get("estimatedShotCount"),
        "averageShotLengthSeconds": pacing.get("averageShotLengthSeconds"),
        "medianShotLengthSeconds": pacing.get("medianShotLengthSeconds"),
        "p10ShotLengthSeconds": pacing.get("p10ShotLengthSeconds"),
        "p90ShotLengthSeconds": pacing.get("p90ShotLengthSeconds"),
        "longShotCountOver20s": pacing.get("longShotCountOver20s"),
        "shortShotCountUnder3s": pacing.get("shortShotCountUnder3s"),
        "audioStatus": audio.get("status"),
        "meanVolumeDb": audio.get("meanVolumeDb"),
        "sampleFrameCount": len(samples),
    }


def reference_ready(profile: dict[str, Any]) -> bool:
    return (
        profile.get("exists") is True
        and profile.get("pacingStatus") == "analyzed"
        and profile.get("audioStatus") == "analyzed"
        and float(profile.get("averageShotLengthSeconds") or 0) > 0
        and int(profile.get("sampleFrameCount") or 0) >= 12
    )


def target_profile(reference: dict[str, Any]) -> dict[str, Any]:
    ref_avg = float(reference.get("averageShotLengthSeconds") or 6.0)
    ref_median = float(reference.get("medianShotLengthSeconds") or 3.0)
    ref_p90 = float(reference.get("p90ShotLengthSeconds") or 12.0)
    return {
        "referenceAverageShotLengthSeconds": round(ref_avg, 3),
        "referenceMedianShotLengthSeconds": round(ref_median, 3),
        "referenceP90ShotLengthSeconds": round(ref_p90, 3),
        "targetAverageRangeSeconds": [round(max(4.0, ref_avg * 0.85), 3), round(min(12.0, max(7.5, ref_avg * 1.8)), 3)],
        "targetMedianRangeSeconds": [round(max(2.0, ref_median * 0.75), 3), round(min(8.0, max(4.5, ref_median * 2.0)), 3)],
        "longShotSoftLimitSeconds": round(min(18.0, max(10.0, ref_p90)), 3),
        "breathingShotLimitSeconds": 24.0,
    }


def infer_rhythm_role(clip: dict[str, Any]) -> str:
    text = clip_text(clip)
    if "opening" in text:
        return "opening_hook"
    if "ending" in text:
        return "ending_aftertaste"
    if "title" in text:
        return "title_bridge"
    if "transition" in text or "bridge" in text:
        return "route_transition"
    if contains_any(text, TRANSPORT_TERMS):
        return "transport_motion"
    if contains_any(text, LIVED_IN_TERMS):
        return "lived_in_detail"
    if contains_any(text, LANDMARK_TERMS):
        return "landmark_payoff"
    if contains_any(text, STREET_TERMS):
        return "street_texture"
    if "aerial" in text or "establish" in text or "visual_bed" in text:
        return "scenic_breathing"
    return "route_observation"


def treatment_for(role: str, duration: float, target: dict[str, Any]) -> dict[str, Any]:
    soft_limit = float(target["longShotSoftLimitSeconds"])
    breathing_limit = float(target["breathingShotLimitSeconds"])
    if role in {"title_bridge"}:
        desired = [3.0, 6.0]
        advice = "keep title readable, then leave the image before it turns into a card"
    elif role in {"opening_hook", "ending_aftertaste", "scenic_breathing"}:
        desired = [5.0, 12.0]
        advice = "let the scene breathe with BGM, but break long holds with detail or motion cutaways"
    elif role == "route_transition":
        desired = [6.0, 16.0]
        advice = "shape as movement or match-cut bridge; avoid black-card or unexplained day jump"
    else:
        desired = target["targetAverageRangeSeconds"]
        advice = "trim or split into route, detail, reaction, and payoff beats instead of one flat hold"

    risks: list[str] = []
    if duration > breathing_limit:
        risks.append("very_long_flat_shot")
    elif duration > max(float(desired[1]), soft_limit):
        risks.append("long_shot_needs_cutaway_or_trim")
    if duration < 1.0:
        risks.append("too_short_to_register")
    return {
        "targetDurationRangeSeconds": desired,
        "recommendedAction": "review" if risks else "keep_or_fine_trim",
        "editorGuidance": advice,
        "riskReasons": risks,
    }


def category_flags(rows: list[dict[str, Any]]) -> dict[str, bool]:
    roles = {row.get("rhythmRole") for row in rows}
    return {
        "transport": "transport_motion" in roles or "route_transition" in roles,
        "streetTexture": "street_texture" in roles,
        "livedInDetail": "lived_in_detail" in roles,
        "landmarkPayoff": "landmark_payoff" in roles,
        "scenicBreathing": "scenic_breathing" in roles or "opening_hook" in roles or "ending_aftertaste" in roles,
        "titleBridge": "title_bridge" in roles,
    }


def build_shot_rows(clips: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, clip in enumerate(clips, start=1):
        start = timeline_start(clip)
        end = timeline_end(clip)
        duration = max(0.0, end - start)
        role = infer_rhythm_role(clip)
        treatment = treatment_for(role, duration, target)
        placeholder_risks = []
        if contains_any(clip_text(clip), PLACEHOLDER_TERMS):
            placeholder_risks.append("placeholder_or_slideshow_source")
        risks = treatment["riskReasons"] + placeholder_risks
        row = {
            "rowIndex": index,
            "rhythmRole": role,
            "timelineStartSeconds": round(start, 3),
            "timelineEndSeconds": round(end, 3),
            "durationSeconds": round(duration, 3),
            "chapterIndex": clip.get("chapterIndex"),
            "sourcePath": clip.get("sourcePath"),
            "sourceName": source_name(clip),
            "blueprintRole": clip.get("role"),
            "purpose": clip.get("purpose"),
            "place": clip.get("place"),
            "trackIndex": clip.get("trackIndex"),
            "categoryTextEvidence": clean_words(clip_text(clip), 260),
            "recommendedTreatment": treatment,
            "riskReasons": risks,
            "status": "needs_rhythm_decision" if risks else "has_rhythm_intent",
            "decision": dict(DECISION_FIELDS),
        }
        rows.append(row)
    return rows


def build_chapter_rows(shot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in shot_rows:
        key = str(row.get("chapterIndex") if row.get("chapterIndex") is not None else "unassigned")
        grouped.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items(), key=lambda item: (9999 if item[0] == "unassigned" else int(float(item[0])), item[0])):
        durations = [float(row.get("durationSeconds") or 0) for row in rows if float(row.get("durationSeconds") or 0) > 0]
        categories = category_flags(rows)
        risk_count = sum(1 for row in rows if row.get("riskReasons"))
        out.append(
            {
                "chapterIndex": key,
                "shotCount": len(rows),
                "durationSeconds": round(sum(durations), 3),
                "averageShotSeconds": round(sum(durations) / len(durations), 3) if durations else 0.0,
                "medianShotSeconds": round(statistics.median(durations), 3) if durations else 0.0,
                "rhythmRiskCount": risk_count,
                "categoryCoverage": categories,
                "coveredCategoryCount": sum(1 for value in categories.values() if value),
                "recommendedPattern": [
                    "establish place",
                    "enter street or transport motion",
                    "cut to lived-in detail",
                    "pay off landmark or chapter intent",
                    "bridge out with route movement or quiet texture",
                ],
                "status": "needs_variety_or_retime" if risk_count or sum(1 for value in categories.values() if value) < 3 else "has_chapter_rhythm_plan",
                "decision": {
                    "approvedChapterRhythm": "",
                    "addCutaways": [],
                    "retimeRows": [],
                    "captionOrBgmNote": "",
                    "resolveImplementation": "",
                    "readbackEvidence": "",
                    "approvedBy": "",
                    "approvedAt": "",
                    "editorNotes": "",
                },
            }
        )
    return out


def build_plan(package_dir: Path, reference_analysis: str | None = None) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    blueprint = load_json(blueprint_path) or {}
    reference_path = find_reference_analysis(package_dir, reference_analysis)
    reference = reference_profile(reference_path)
    target = target_profile(reference)
    clips = video_clips(blueprint)
    shot_rows = build_shot_rows(clips, target)
    chapter_rows = build_chapter_rows(shot_rows)
    durations = [float(row.get("durationSeconds") or 0) for row in shot_rows if float(row.get("durationSeconds") or 0) > 0]
    total_duration = max(
        [float(as_float(blueprint.get("targetDurationSeconds"), 0) or 0), *[float(row["timelineEndSeconds"]) for row in shot_rows]],
        default=0.0,
    )
    shot_count = len(shot_rows)
    avg = sum(durations) / len(durations) if durations else 0.0
    median = statistics.median(durations) if durations else 0.0
    target_max = float(target["targetAverageRangeSeconds"][1])
    recommended_min_shots = math.ceil(total_duration / target_max) if target_max and total_duration else 0
    rhythm_risk_count = sum(1 for row in shot_rows if row.get("riskReasons"))
    rows_with_decisions = sum(1 for row in shot_rows if isinstance(row.get("decision"), dict) and set(DECISION_FIELDS).issubset(row["decision"]))
    category_counts: dict[str, int] = {}
    for row in shot_rows:
        role = str(row.get("rhythmRole") or "")
        category_counts[role] = category_counts.get(role, 0) + 1
    status = (
        "ready_with_edit_rhythm_plan"
        if blueprint_path.exists()
        and reference_ready(reference)
        and shot_rows
        and rows_with_decisions == len(shot_rows)
        and chapter_rows
        else ("needs_edit_rhythm_inputs" if blueprint_path.exists() else "blocked_missing_resolve_blueprint")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(blueprint_path),
            "referenceAnalysis": str(reference_path) if reference_path else None,
            "deliveryPlan": str(package_dir / "delivery_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "captionStoryPlan": str(package_dir / "caption_story_plan" / "caption_story_plan.json"),
            "audioScenePolicyPlan": str(package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json"),
        },
        "summary": {
            "timelineDurationSeconds": round(total_duration, 3),
            "primaryVisualShotCount": shot_count,
            "recommendedMinimumShotCount": recommended_min_shots,
            "estimatedAdditionalCutawayBeats": max(0, recommended_min_shots - shot_count),
            "averageShotSeconds": round(avg, 3),
            "medianShotSeconds": round(median, 3),
            "rhythmRiskCount": rhythm_risk_count,
            "rowsWithDecisionFields": rows_with_decisions,
            "chapterRowCount": len(chapter_rows),
            "chaptersNeedingVarietyOrRetime": sum(1 for row in chapter_rows if row.get("status") == "needs_variety_or_retime"),
            "categoryCounts": category_counts,
            "referenceReady": reference_ready(reference),
        },
        "referenceProfile": reference,
        "targetRhythmProfile": target,
        "policy": {
            "referenceAnchoredButNonCopying": True,
            "avoidBareConcatenation": True,
            "realFootageFunctionRequired": True,
            "livedInRouteTextureRequired": True,
            "bgmAndCaptionsCarryNoVoiceoverSections": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "chapterRows": chapter_rows,
        "shotRows": shot_rows,
        "selectionRubric": {
            "pass": [
                "Every primary visual shot has a story/rhythm function instead of being kept only because it exists.",
                "Long raw footage holds are trimmed, split, or interrupted with motivated transport, street, lived-in, landmark, or scenic cutaways.",
                "Each chapter has at least three visible beat categories, such as movement, street texture, lived-in detail, landmark payoff, title bridge, or scenic breathing.",
                "Shot pacing is calibrated against the non-copying Malta reference profile while preserving long-form travel breathing room.",
            ],
            "reject": [
                "A chapter made mostly of 20-30 second raw clips with no cutaway, caption function, or route purpose.",
                "A montage that jumps landmark-to-landmark without transport, street, food, hotel, weather, waiting, or human travel texture.",
                "Template effects, title cards, or stock placeholders used to hide weak shot selection.",
                "A style claim based only on final QA scores while no pre-Resolve rhythm/shot-purpose decisions exist.",
            ],
        },
        "nextActions": [
            "Use risk rows to decide which long shots should be split, trimmed, or supported by cutaways before Resolve apply.",
            "Prioritize extra cutaways from the user's real footage before considering stock or aerial fallbacks.",
            "After Resolve apply, paste timeline readback evidence into decision fields and rerun reference-style, route-texture, and director-polish audits.",
            "Do not mark a future package as Bilibili/Malta-like if this plan is missing or all decisions remain blank.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Edit Rhythm Plan",
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
        "## Target Rhythm Profile",
        "",
        "```json",
        json.dumps(plan["targetRhythmProfile"], ensure_ascii=False, indent=2),
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
                f"- Shots: {row['shotCount']}",
                f"- Average shot seconds: {row['averageShotSeconds']}",
                f"- Rhythm risks: {row['rhythmRiskCount']}",
                f"- Covered categories: {row['coveredCategoryCount']}",
            ]
        )
    lines.extend(["", "## Risk Shot Rows"])
    risk_rows = [row for row in plan["shotRows"] if row.get("riskReasons")]
    if not risk_rows:
        lines.append("- None.")
    for row in risk_rows[:80]:
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['rhythmRole']}",
                f"- Window: `{row['timelineStartSeconds']}` to `{row['timelineEndSeconds']}` ({row['durationSeconds']}s)",
                f"- Source: `{row.get('sourceName')}`",
                f"- Risks: `{', '.join(row.get('riskReasons') or [])}`",
                f"- Guidance: {row['recommendedTreatment']['editorGuidance']}",
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
    parser = argparse.ArgumentParser(description="Prepare a reference-anchored edit rhythm plan for a travel package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--reference-analysis")
    parser.add_argument("--output-dir", help="Defaults to <package>/edit_rhythm_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "edit_rhythm_plan"
    plan = build_plan(package_dir, args.reference_analysis)
    write_json(output_dir / "edit_rhythm_plan.json", plan)
    write_markdown(output_dir / "edit_rhythm_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
