#!/usr/bin/env python3
"""Prepare a chapter-level story arc plan for a travel edit package."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


BEAT_DEFINITIONS = {
    "context": {
        "label": "person/context",
        "terms": (
            "person",
            "people",
            "face",
            "reaction",
            "talk",
            "vlog",
            "companion",
            "family",
            "friend",
            "interview",
            "selfie",
            "context",
            "promise",
            "人",
            "朋友",
            "家人",
            "反应",
            "口播",
            "说话",
            "同行",
        ),
        "requiredEvidence": "human context, reaction, route purpose, or a clear viewer-facing reason this chapter matters",
    },
    "movement": {
        "label": "route movement",
        "terms": (
            "airport",
            "station",
            "train",
            "subway",
            "metro",
            "road",
            "car",
            "taxi",
            "bus",
            "ferry",
            "boat",
            "plane",
            "walk",
            "walking",
            "bridge",
            "luggage",
            "ticket",
            "window",
            "escalator",
            "transfer",
            "arrival",
            "departure",
            "route",
            "map",
            "机场",
            "车站",
            "火车",
            "地铁",
            "路",
            "车",
            "船",
            "飞机",
            "步行",
            "桥",
            "行李",
            "票",
            "车窗",
            "扶梯",
            "抵达",
            "出发",
        ),
        "requiredEvidence": "transport, walking, road, route, map, luggage, ticket, or other practical travel movement",
    },
    "texture": {
        "label": "lived-in texture",
        "terms": (
            "street",
            "shop",
            "market",
            "food",
            "restaurant",
            "hotel",
            "room",
            "interior",
            "sign",
            "weather",
            "rain",
            "night",
            "table",
            "coffee",
            "waiting",
            "crowd",
            "convenience",
            "街",
            "店",
            "市场",
            "饭",
            "餐",
            "酒店",
            "房间",
            "室内",
            "路牌",
            "天气",
            "雨",
            "夜",
            "桌",
            "等待",
            "人群",
            "便利店",
        ),
        "requiredEvidence": "street, food, hotel, shop, sign, weather, waiting, crowd, room, or other small trip detail",
    },
    "payoff": {
        "label": "destination payoff",
        "terms": (
            "aerial",
            "drone",
            "skyline",
            "landmark",
            "tower",
            "castle",
            "temple",
            "shrine",
            "museum",
            "coast",
            "sea",
            "ocean",
            "mountain",
            "park",
            "activity",
            "show",
            "view",
            "panorama",
            "harbor",
            "tokyo tower",
            "osaka castle",
            "航拍",
            "天际线",
            "地标",
            "塔",
            "城",
            "寺",
            "神社",
            "博物馆",
            "海",
            "山",
            "公园",
            "景点",
            "活动",
            "大阪城",
            "东京塔",
        ),
        "requiredEvidence": "landmark, skyline, coast, mountain, site, activity, aerial, or other destination reward",
    },
    "aftertaste": {
        "label": "aftertaste/handoff",
        "terms": (
            "sunset",
            "dusk",
            "night",
            "quiet",
            "departure",
            "leaving",
            "ending",
            "final",
            "window",
            "road",
            "train",
            "airport",
            "callback",
            "bridge",
            "fade",
            "夕阳",
            "黄昏",
            "夜景",
            "安静",
            "离开",
            "回程",
            "结尾",
            "车窗",
            "路",
            "火车",
            "机场",
            "回望",
            "过渡",
        ),
        "requiredEvidence": "quiet observation, departure, night/dusk, route callback, or bridge material to the next chapter",
    },
}

REQUIRED_BEATS = tuple(BEAT_DEFINITIONS)

DECISION_FIELDS = {
    "approvedChapterArc": "",
    "selectedContextClip": "",
    "selectedMovementClip": "",
    "selectedTextureClip": "",
    "selectedPayoffClip": "",
    "selectedAftertasteClip": "",
    "captionArcEvidence": "",
    "bgmArcEvidence": "",
    "transitionHandoffEvidence": "",
    "resolveBlueprintEvidence": "",
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


def timeline_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds", "start"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    return 0.0


def clip_duration(clip: dict[str, Any]) -> float:
    for key in ("durationSeconds", "sourceDurationSeconds", "duration"):
        value = as_float(clip.get(key))
        if value and value > 0:
            return value
    start = timeline_start(clip)
    for key in ("timelineEndSeconds", "recordEndSeconds", "endSeconds", "end"):
        end = as_float(clip.get(key))
        if end is not None and end > start:
            return end - start
    source_start = as_float(clip.get("sourceStartSeconds"), 0.0) or 0.0
    source_end = as_float(clip.get("sourceEndSeconds"), 0.0) or 0.0
    return max(0.0, source_end - source_start)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    for key in ("timelineEndSeconds", "recordEndSeconds", "endSeconds", "end"):
        end = as_float(clip.get(key))
        if end is not None and end > start:
            return end
    return start + clip_duration(clip)


def source_name(clip: dict[str, Any]) -> str:
    source = str(clip.get("sourcePath") or clip.get("path") or "")
    if source:
        return Path(source).name
    return clean_words(clip.get("name") or clip.get("role") or clip.get("purpose") or "")


def natural_sort_key(value: str) -> tuple[int, float, str]:
    try:
        return (0, float(value), value)
    except ValueError:
        return (1, 0.0, value)


def clip_text(clip: dict[str, Any]) -> str:
    keys = (
        "role",
        "purpose",
        "place",
        "city",
        "chapterTitle",
        "titleText",
        "subtitle",
        "caption",
        "name",
        "sourcePath",
        "path",
        "notes",
        "narrationIntent",
        "creatorFunction",
    )
    return " ".join(str(clip.get(key) or "") for key in keys).lower()


def video_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = clip_text(row)
        if "subtitle_overlay" in text:
            continue
        track_type = clean_words(row.get("trackType") or "video").lower()
        if track_type != "video":
            continue
        out.append(row)
    return sorted(out, key=lambda item: (timeline_start(item), int(as_float(item.get("trackIndex"), 1) or 1)))


def clip_summary(clip: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourcePath": clip.get("sourcePath") or clip.get("path"),
        "sourceName": source_name(clip),
        "role": clip.get("role"),
        "purpose": clip.get("purpose"),
        "place": clip.get("place") or clip.get("city"),
        "timelineStartSeconds": round(timeline_start(clip), 3),
        "timelineEndSeconds": round(timeline_end(clip), 3),
        "durationSeconds": round(clip_duration(clip), 3),
    }


def chapter_title(chapter: dict[str, Any], index: int) -> str:
    for key in ("title", "chapterTitle", "chapter", "place", "city", "name"):
        value = clean_words(chapter.get(key))
        if value:
            return value
    return f"Chapter {index + 1}"


def chapter_text(chapter: dict[str, Any]) -> str:
    keys = (
        "title",
        "chapterTitle",
        "chapter",
        "place",
        "city",
        "route",
        "narrationIntent",
        "subtitleStyle",
        "bgmMood",
        "transitionIn",
        "transitionOut",
        "representativeFootageType",
        "notes",
    )
    return " ".join(str(chapter.get(key) or "") for key in keys).lower()


def delivery_chapters(delivery: dict[str, Any], clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = delivery.get("chapters") if isinstance(delivery.get("chapters"), list) else []
    chapters = [row for row in rows if isinstance(row, dict)]
    if chapters:
        return chapters
    grouped: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        key = str(clip.get("chapterIndex") if clip.get("chapterIndex") is not None else "unassigned")
        grouped.setdefault(key, []).append(clip)
    inferred: list[dict[str, Any]] = []
    for idx, key in enumerate(sorted(grouped, key=natural_sort_key)):
        group = grouped[key]
        inferred.append(
            {
                "chapterIndex": key,
                "title": clean_words(group[0].get("place") or group[0].get("city") or f"Chapter {idx + 1}"),
                "startSeconds": min(timeline_start(clip) for clip in group),
                "endSeconds": max(timeline_end(clip) for clip in group),
                "notes": "Inferred from Resolve blueprint clip chapterIndex.",
            }
        )
    return inferred


def chapter_window(chapter: dict[str, Any], index: int, chapters: list[dict[str, Any]], clips: list[dict[str, Any]]) -> tuple[float, float]:
    for start_key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds", "start"):
        start = as_float(chapter.get(start_key))
        if start is not None:
            end = None
            for end_key in ("timelineEndSeconds", "recordEndSeconds", "endSeconds", "end"):
                end = as_float(chapter.get(end_key))
                if end is not None:
                    break
            duration = as_float(chapter.get("durationSeconds") or chapter.get("duration"))
            if end is None and duration:
                end = start + duration
            if end is not None and end > start:
                return start, end
    grouped = [
        clip
        for clip in clips
        if str(clip.get("chapterIndex") if clip.get("chapterIndex") is not None else "") in {str(index), str(chapter.get("chapterIndex") or "")}
    ]
    if grouped:
        return min(timeline_start(clip) for clip in grouped), max(timeline_end(clip) for clip in grouped)
    if not clips:
        return float(index * 180), float((index + 1) * 180)
    total_start = min(timeline_start(clip) for clip in clips)
    total_end = max(timeline_end(clip) for clip in clips)
    width = max(1.0, (total_end - total_start) / max(1, len(chapters)))
    return total_start + index * width, min(total_end, total_start + (index + 1) * width)


def clips_in_window(clips: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    return [clip for clip in clips if timeline_end(clip) > start and timeline_start(clip) < end]


def beat_matches(texts: list[str], clips: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    joined = " ".join(texts)
    matches: dict[str, dict[str, Any]] = {}
    for beat_id, definition in BEAT_DEFINITIONS.items():
        terms = definition["terms"]
        matching_clips = [clip for clip in clips if contains_any(clip_text(clip), terms)]
        text_hit = contains_any(joined, terms)
        examples = [clip_summary(clip) for clip in matching_clips[:8]]
        matches[beat_id] = {
            "label": definition["label"],
            "requiredEvidence": definition["requiredEvidence"],
            "textHit": text_hit,
            "clipCount": len(matching_clips),
            "evidenceCount": len(matching_clips) + (1 if text_hit else 0),
            "exampleClips": examples,
        }
    return matches


def owner_scripts_for_missing(missing: list[str]) -> list[dict[str, str]]:
    owners = {
        "context": ("prepare_caption_story_plan.py", "Rewrite audience-facing chapter captions or human-context beat."),
        "movement": ("prepare_footage_select_plan.py", "Find transport, road, station, walking, map, or route bridge footage."),
        "texture": ("prepare_creator_cut_plan.py", "Insert lived-in street, food, hotel, sign, weather, room, or waiting details."),
        "payoff": ("prepare_visual_establishing_plan.py", "Find local/aerial/landmark/activity payoff footage or approved stock."),
        "aftertaste": ("prepare_transition_bridge_plan.py", "Add departure, night, quiet, route callback, or bridge handoff material."),
    }
    return [
        {"beatId": beat_id, "ownerScript": owners[beat_id][0], "repairIntent": owners[beat_id][1]}
        for beat_id in missing
    ]


def reference_rule(reference_batch: dict[str, Any]) -> dict[str, Any]:
    summary = reference_batch.get("summary") if isinstance(reference_batch.get("summary"), dict) else {}
    pacing = reference_batch.get("pacingProfile") if isinstance(reference_batch.get("pacingProfile"), dict) else {}
    return {
        "source": "Parallel World/Malta non-copying chapter grammar",
        "referenceBatchStatus": reference_batch.get("status"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "targetMedianShotLengthSeconds": pacing.get("medianShotLengthSeconds"),
        "rule": "Each chapter should move through context, route movement, lived-in texture, destination payoff, and aftertaste/handoff when source footage supports it.",
    }


def build_chapter_row(
    chapter: dict[str, Any],
    index: int,
    chapters: list[dict[str, Any]],
    clips: list[dict[str, Any]],
    reference_batch: dict[str, Any],
) -> dict[str, Any]:
    start, end = chapter_window(chapter, index, chapters, clips)
    chapter_clips = clips_in_window(clips, start, end)
    texts = [chapter_text(chapter)] + [clip_text(clip) for clip in chapter_clips]
    detected = beat_matches(texts, chapter_clips)
    missing = [beat_id for beat_id in REQUIRED_BEATS if int(detected[beat_id]["evidenceCount"] or 0) <= 0]
    status = "has_reference_chapter_arc" if not missing else "needs_chapter_arc_repair"
    return {
        "chapterIndex": chapter.get("chapterIndex", index),
        "chapterTitle": chapter_title(chapter, index),
        "targetWindowSeconds": [round(start, 3), round(end, 3)],
        "sourceChapter": {
            "place": chapter.get("place") or chapter.get("city"),
            "narrationIntent": chapter.get("narrationIntent"),
            "representativeFootageType": chapter.get("representativeFootageType"),
            "bgmMood": chapter.get("bgmMood"),
            "transitionIn": chapter.get("transitionIn"),
            "transitionOut": chapter.get("transitionOut"),
        },
        "chapterClipCount": len(chapter_clips),
        "detectedBeats": detected,
        "missingBeatIds": missing,
        "recommendedBeatOrder": [
            "context",
            "movement",
            "texture",
            "payoff",
            "aftertaste",
        ],
        "localSearchHints": [
            f"{chapter_title(chapter, index)} transport station road walking map luggage",
            f"{chapter_title(chapter, index)} street food hotel sign weather room",
            f"{chapter_title(chapter, index)} landmark skyline aerial coast activity",
            f"{chapter_title(chapter, index)} sunset night departure window quiet",
        ],
        "ownerScriptsForMissingBeats": owner_scripts_for_missing(missing),
        "referenceRule": reference_rule(reference_batch),
        "status": status,
        "decision": dict(DECISION_FIELDS),
    }


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    reference_batch = load_json(package_dir / "reference" / "reference_batch_profile.json") or {}
    opening_story = load_json(package_dir / "opening_story_plan" / "opening_story_plan.json") or {}
    edit_rhythm = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
    creator_cut = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    transition_bridge = load_json(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json") or {}
    clips = video_clips(blueprint)
    chapters = delivery_chapters(delivery, clips)
    chapter_rows = [
        build_chapter_row(chapter, index, chapters, clips, reference_batch)
        for index, chapter in enumerate(chapters)
    ]
    decision_fields = set(DECISION_FIELDS)
    rows_with_decisions = sum(
        1 for row in chapter_rows if decision_fields.issubset(set((row.get("decision") or {}).keys()))
    )
    beat_coverage = {
        beat_id: sum(1 for row in chapter_rows if int((row["detectedBeats"][beat_id]).get("evidenceCount") or 0) > 0)
        for beat_id in REQUIRED_BEATS
    }
    missing_required = sum(1 for row in chapter_rows if row.get("missingBeatIds"))
    safety = {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
    }
    if not chapter_rows:
        status = "blocked_missing_chapter_inputs"
    elif rows_with_decisions == len(chapter_rows):
        status = "ready_with_chapter_arc_plan"
    else:
        status = "needs_chapter_arc_decisions"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "deliveryPlan": str(package_dir / "delivery_plan.json"),
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "openingStoryPlan": str(package_dir / "opening_story_plan" / "opening_story_plan.json"),
            "editRhythmPlan": str(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json"),
            "creatorCutPlan": str(package_dir / "creator_cut_plan" / "creator_cut_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "referenceBatchProfile": str(package_dir / "reference" / "reference_batch_profile.json"),
        },
        "summary": {
            "chapterRowCount": len(chapter_rows),
            "blueprintVideoClipCount": len(clips),
            "rowsWithDecisionFields": rows_with_decisions,
            "chaptersWithContextBeat": beat_coverage["context"],
            "chaptersWithMovementBeat": beat_coverage["movement"],
            "chaptersWithTextureBeat": beat_coverage["texture"],
            "chaptersWithPayoffBeat": beat_coverage["payoff"],
            "chaptersWithAftertasteBeat": beat_coverage["aftertaste"],
            "chaptersMissingRequiredBeatCount": missing_required,
            "p0RepairRowCount": missing_required,
            "openingStoryStatus": opening_story.get("status"),
            "editRhythmStatus": edit_rhythm.get("status"),
            "creatorCutStatus": creator_cut.get("status"),
            "transitionBridgeStatus": transition_bridge.get("status"),
            "referenceBatchProfileStatus": reference_batch.get("status"),
        },
        "policy": {
            "chapterArcRequiredBeforeRhythmOrResolveTrust": True,
            "contextMovementTexturePayoffAftertasteGrammar": True,
            "physicalBridgeBeforeTransitionEffect": True,
            "audienceFacingCaptionArcOnly": True,
            "bgmOnlyNoCameraVoiceDefault": True,
            "referenceAnchoredButNonCopying": True,
            **safety,
        },
        "chapterRows": chapter_rows,
        "selectionRubric": {
            "pass": [
                "Each chapter has an explicit context, movement, texture, payoff, and aftertaste/handoff decision row.",
                "Missing beats are assigned to concrete owner scripts before Resolve apply.",
                "Captions and BGM support the chapter arc for viewers rather than reporting editor workflow state.",
                "Transition effects are allowed only after real bridge or route-motion evidence exists.",
                "The plan is reference-anchored but does not copy reference footage, music, titles, or narration.",
            ],
            "reject": [
                "A chapter is only a pile of scenic clips with no route movement, lived-in texture, or aftertaste.",
                "A weak chapter boundary is hidden behind a spin/flash/glitch effect instead of real bridge footage.",
                "Captions say what the editor fixed or delivered instead of what the viewer should feel or understand.",
                "The plan claims Parallel World/Malta style without chapter-level beat rows.",
            ],
        },
        "nextActions": [
            "Fill each chapter decision field before rhythm recut, Resolve apply, or final readiness claims.",
            "Repair missing movement/texture/payoff/aftertaste beats through footage select, creator cut, visual establishing, and transition bridge plans.",
            "Use chapter arc rows to guide subtitle density, BGM mood changes, and transition execution.",
            "After Resolve write, paste readback evidence into each chapter row and rerun Skill maturity and V14 baseline contracts.",
        ],
        "safety": safety,
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Chapter Arc Plan",
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
                f"### {row['chapterIndex']}: {row['chapterTitle']}",
                f"- Status: `{row['status']}`",
                f"- Window: `{row['targetWindowSeconds'][0]}-{row['targetWindowSeconds'][1]}` seconds",
                f"- Clips: `{row['chapterClipCount']}`",
                f"- Missing beats: `{', '.join(row['missingBeatIds']) if row['missingBeatIds'] else 'none'}`",
                "- Beat coverage:",
            ]
        )
        for beat_id in REQUIRED_BEATS:
            beat = row["detectedBeats"][beat_id]
            lines.append(
                f"  - `{beat_id}` {beat['label']}: evidence `{beat['evidenceCount']}` clips `{beat['clipCount']}`"
            )
        if row["ownerScriptsForMissingBeats"]:
            lines.extend(["- Repair owners:"])
            for owner in row["ownerScriptsForMissingBeats"]:
                lines.append(f"  - `{owner['beatId']}` -> `{owner['ownerScript']}`: {owner['repairIntent']}")
    lines.extend(["", "## Pass Rubric"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "## Reject Rubric"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a chapter-level story arc plan for a travel edit package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    plan = build_plan(package_dir)
    output_dir = package_dir / "chapter_arc_plan"
    write_json(output_dir / "chapter_arc_plan.json", plan)
    write_markdown(output_dir / "chapter_arc_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 2 if plan["status"] == "blocked_missing_chapter_inputs" else 0


if __name__ == "__main__":
    raise SystemExit(main())
