#!/usr/bin/env python3
"""Prepare a first-three-minutes opening story plan for a travel edit package."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


OPENING_WINDOW_SECONDS = 180.0

DESTINATION_TERMS = (
    "aerial",
    "drone",
    "skyline",
    "establish",
    "landmark",
    "tower",
    "castle",
    "temple",
    "shrine",
    "bridge",
    "harbor",
    "coast",
    "sea",
    "ocean",
    "mountain",
    "sunset",
    "night",
    "city",
    "title",
    "航拍",
    "天际线",
    "地标",
    "城堡",
    "寺",
    "神社",
    "桥",
    "海",
    "山",
    "夜景",
    "城市",
)

ROUTE_TERMS = (
    "airport",
    "station",
    "train",
    "subway",
    "metro",
    "taxi",
    "bus",
    "car",
    "road",
    "window",
    "ferry",
    "boat",
    "plane",
    "walk",
    "walking",
    "luggage",
    "ticket",
    "arrival",
    "departure",
    "transfer",
    "route",
    "机场",
    "车站",
    "火车",
    "地铁",
    "出租",
    "巴士",
    "车窗",
    "轮渡",
    "飞机",
    "步行",
    "行李",
    "票",
    "抵达",
    "出发",
)

LIVED_IN_TERMS = (
    "street",
    "market",
    "food",
    "restaurant",
    "hotel",
    "room",
    "shop",
    "sign",
    "map",
    "weather",
    "rain",
    "crowd",
    "table",
    "coffee",
    "street_texture",
    "lived",
    "街",
    "市场",
    "饭",
    "餐",
    "酒店",
    "房间",
    "店",
    "路牌",
    "地图",
    "天气",
    "雨",
    "人群",
)

TITLE_TERMS = (
    "opening_title",
    "title_bridge",
    "chapter_title",
    "title",
    "hero title",
    "city title",
    "place title",
)

WEAK_TITLE_TERMS = (
    "title_cards",
    "black",
    "slate",
    "placeholder",
    "tokyo / osaka",
    "japan 2025",
    "route",
    "date",
    "project",
    "id",
    "占位",
    "黑屏",
)

DECISION_FIELDS = {
    "approvedBeat": "",
    "selectedClipSourcePaths": [],
    "targetTimelineStartSeconds": None,
    "targetTimelineEndSeconds": None,
    "captionOrTitleText": "",
    "bgmMoodCue": "",
    "audioPolicy": "bgm_only_no_camera_voice",
    "transitionOut": "",
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


def lower_text(value: Any) -> str:
    return clean_words(value, 1000).lower()


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


def contains_weak_title_term(text: str) -> bool:
    lower = text.lower()
    for term in WEAK_TITLE_TERMS:
        term_lower = term.lower()
        if term_lower.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(term_lower)}(?![a-z0-9])", lower):
                return True
        elif term_lower in lower:
            return True
    return False


def timeline_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds", "start"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    return 0.0


def timeline_end(clip: dict[str, Any]) -> float:
    for key in ("timelineEndSeconds", "recordEndSeconds", "endSeconds", "end"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    start = timeline_start(clip)
    duration = as_float(clip.get("durationSeconds") or clip.get("duration"))
    if duration is not None:
        return start + max(0.0, duration)
    source_start = as_float(clip.get("sourceStartSeconds"), 0.0) or 0.0
    source_end = as_float(clip.get("sourceEndSeconds"), 0.0) or 0.0
    return start + max(0.0, source_end - source_start)


def clip_duration(clip: dict[str, Any]) -> float:
    return max(0.0, timeline_end(clip) - timeline_start(clip))


def source_name(clip: dict[str, Any]) -> str:
    source = str(clip.get("sourcePath") or clip.get("path") or "")
    return Path(source).name if source else clean_words(clip.get("name") or clip.get("role") or "")


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in (
            "role",
            "purpose",
            "place",
            "city",
            "titleText",
            "subtitle",
            "name",
            "sourcePath",
            "path",
            "notes",
        )
    ).lower()


def video_clips(blueprint: dict[str, Any], window_seconds: float) -> list[dict[str, Any]]:
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
        start = timeline_start(row)
        end = timeline_end(row)
        if end <= 0 or start >= window_seconds:
            continue
        out.append(row)
    return sorted(out, key=lambda clip: (timeline_start(clip), int(as_float(clip.get("trackIndex"), 1) or 1)))


def clip_summary(clip: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourcePath": clip.get("sourcePath") or clip.get("path"),
        "sourceName": source_name(clip),
        "role": clip.get("role"),
        "purpose": clip.get("purpose"),
        "timelineStartSeconds": round(timeline_start(clip), 3),
        "timelineEndSeconds": round(timeline_end(clip), 3),
        "durationSeconds": round(clip_duration(clip), 3),
    }


def unique_clip_key(clip: dict[str, Any]) -> tuple[str, float, float, str]:
    source = str(clip.get("sourcePath") or clip.get("path") or source_name(clip))
    return (source, round(timeline_start(clip), 3), round(timeline_end(clip), 3), str(clip.get("role") or ""))


def unique_clip_list(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, float, float, str]] = set()
    out: list[dict[str, Any]] = []
    for clip in clips:
        key = unique_clip_key(clip)
        if key in seen:
            continue
        seen.add(key)
        out.append(clip)
    return out


def matching_clips(clips: list[dict[str, Any]], terms: tuple[str, ...], *, start: float = 0.0, end: float = OPENING_WINDOW_SECONDS) -> list[dict[str, Any]]:
    matched = []
    for clip in clips:
        if timeline_end(clip) <= start or timeline_start(clip) >= end:
            continue
        if contains_any(clip_text(clip), terms):
            matched.append(clip)
    return matched


def title_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [clip for clip in clips if contains_any(clip_text(clip), TITLE_TERMS)]


def weak_title_hits(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [clip for clip in title_clips(clips) if contains_weak_title_term(clip_text(clip))]


def delivery_title(delivery: dict[str, Any]) -> str:
    chapters = delivery.get("chapters") if isinstance(delivery.get("chapters"), list) else []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        for key in ("city", "place", "chapter"):
            value = clean_words(chapter.get(key))
            if value and not value.lower().startswith("unknown"):
                return value
    project = delivery.get("project") if isinstance(delivery.get("project"), dict) else {}
    return clean_words(project.get("title") or delivery.get("title") or "Travel Film")


def beat_row(
    beat_id: str,
    label: str,
    target_window: list[float],
    evidence: list[dict[str, Any]],
    required: list[str],
    recommended_action: str,
    *,
    max_evidence: int = 8,
) -> dict[str, Any]:
    evidence_rows = [clip_summary(clip) for clip in evidence[:max_evidence]]
    status = "has_opening_story_evidence" if evidence_rows else "needs_opening_story_evidence"
    return {
        "beatId": beat_id,
        "label": label,
        "targetWindowSeconds": target_window,
        "requiredEvidence": required,
        "evidenceCount": len(evidence),
        "evidenceClips": evidence_rows,
        "status": status,
        "recommendedAction": recommended_action,
        "decision": dict(DECISION_FIELDS),
    }


def first_three_minute_coverage(clips: list[dict[str, Any]], window_seconds: float) -> float:
    intervals: list[tuple[float, float]] = []
    for clip in clips:
        start = max(0.0, min(window_seconds, timeline_start(clip)))
        end = max(0.0, min(window_seconds, timeline_end(clip)))
        if end > start:
            intervals.append((start, end))
    if not intervals:
        return 0.0
    intervals.sort()
    merged: list[list[float]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start for start, end in merged)


def build_plan(package_dir: Path, opening_window_seconds: float = OPENING_WINDOW_SECONDS) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    footage_select = load_json(package_dir / "footage_select_plan" / "footage_select_plan.json") or {}
    title_plan = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    visual_plan = load_json(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json") or {}
    bgm_selection = load_json(package_dir / "bgm_selection_package" / "bgm_selection_package.json") or {}
    clips = video_clips(blueprint, opening_window_seconds)

    destination = matching_clips(clips, DESTINATION_TERMS, start=0.0, end=min(75.0, opening_window_seconds))
    route = matching_clips(clips, ROUTE_TERMS, start=20.0, end=opening_window_seconds)
    lived = matching_clips(clips, LIVED_IN_TERMS, start=35.0, end=opening_window_seconds)
    titles = title_clips(clips)
    weak_titles = weak_title_hits(clips)
    handoff = matching_clips(clips, ROUTE_TERMS + LIVED_IN_TERMS, start=max(90.0, opening_window_seconds - 60.0), end=opening_window_seconds)
    promise_evidence = unique_clip_list(destination[:3] + route[:3])

    beat_rows = [
        beat_row(
            "viewer_promise",
            "Viewer promise in the first 20-40 seconds",
            [0.0, 40.0],
            promise_evidence,
            ["destination proof", "route question or arrival energy"],
            "Open with a clear reason to watch, supported by actual destination and route footage.",
        ),
        beat_row(
            "destination_proof",
            "Destination proof before explanation",
            [0.0, 60.0],
            destination,
            ["aerial, skyline, landmark, coast, city, or other readable place identity"],
            "Use the strongest local establishing image before long captions or route explanation.",
        ),
        beat_row(
            "clean_hero_title",
            "Clean hero title on real footage",
            [0.0, 55.0],
            titles,
            ["one short city/place title", "real video background", "no route/date/internal clutter"],
            "Use one clean title over scenic footage; suppress subtitles inside the title zone.",
        ),
        beat_row(
            "practical_arrival",
            "Practical route or arrival material",
            [35.0, 150.0],
            route,
            ["airport, train, station, road, ferry, luggage, ticket, walking, or hotel arrival"],
            "Return from the hook to real travel mechanics so the film feels traveled, not only scenic.",
        ),
        beat_row(
            "lived_in_texture",
            "Lived-in travel texture before minute three",
            [45.0, 170.0],
            lived,
            ["street, food, hotel, sign, weather, crowd, room, table, shop, or waiting detail"],
            "Add small local details before the first main chapter payoff.",
        ),
        beat_row(
            "first_chapter_handoff",
            "First handoff into the route",
            [120.0, opening_window_seconds],
            handoff,
            ["movement or lived-in bridge material leading into the first chapter"],
            "Bridge out with transport, street, hotel, food, weather, or signage instead of a hard reset.",
        ),
    ]

    decision_fields = set(DECISION_FIELDS)
    rows_with_decisions = sum(1 for row in beat_rows if decision_fields.issubset(set((row.get("decision") or {}).keys())))
    rows_with_evidence = sum(1 for row in beat_rows if int(row.get("evidenceCount") or 0) > 0)
    missing_rows = [row["beatId"] for row in beat_rows if int(row.get("evidenceCount") or 0) <= 0]
    coverage = first_three_minute_coverage(clips, opening_window_seconds)
    first_clip_start = min((timeline_start(clip) for clip in clips), default=None)
    footage_summary = footage_select.get("summary") if isinstance(footage_select.get("summary"), dict) else {}
    bgm_summary = bgm_selection.get("summary") if isinstance(bgm_selection.get("summary"), dict) else {}
    title_summary = title_plan.get("summary") if isinstance(title_plan.get("summary"), dict) else {}
    visual_summary = visual_plan.get("summary") if isinstance(visual_plan.get("summary"), dict) else {}
    status = (
        "ready_with_opening_story_plan"
        if clips and rows_with_decisions == len(beat_rows) and rows_with_evidence == len(beat_rows) and not missing_rows
        else ("blocked_missing_resolve_blueprint" if not (package_dir / "resolve_timeline_blueprint.json").exists() else "needs_opening_story_inputs")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "deliveryPlan": str(package_dir / "delivery_plan.json"),
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "footageSelectPlan": str(package_dir / "footage_select_plan" / "footage_select_plan.json"),
            "titleTypographyPlan": str(package_dir / "title_typography_plan" / "title_typography_plan.json"),
            "visualEstablishingPlan": str(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json"),
            "bgmSelectionPackage": str(package_dir / "bgm_selection_package" / "bgm_selection_package.json"),
        },
        "summary": {
            "openingWindowSeconds": round(opening_window_seconds, 3),
            "openingVideoClipCount": len(clips),
            "openingCoverageSeconds": round(coverage, 3),
            "openingCoverageRatio": round(coverage / opening_window_seconds, 4) if opening_window_seconds else 0,
            "firstClipStartSeconds": round(first_clip_start, 3) if first_clip_start is not None else None,
            "beatRowCount": len(beat_rows),
            "rowsWithDecisionFields": rows_with_decisions,
            "rowsWithEvidence": rows_with_evidence,
            "missingBeatCount": len(missing_rows),
            "missingBeatIds": missing_rows,
            "destinationProofClipCount": len(destination),
            "routeArrivalClipCount": len(route),
            "livedInTextureClipCount": len(lived),
            "titleClipCount": len(titles),
            "weakTitleHitCount": len(weak_titles),
            "firstHandoffClipCount": len(handoff),
            "footageSelectStatus": footage_select.get("status"),
            "footageSelectCandidateCount": footage_summary.get("candidateVideoCount"),
            "titleTypographyStatus": title_plan.get("status"),
            "titleTypographyCleanRows": title_summary.get("cleanRowCount"),
            "visualEstablishingStatus": visual_plan.get("status"),
            "visualEstablishingRowsWithEvidence": visual_summary.get("rowsWithEvidence"),
            "bgmSelectionStatus": bgm_selection.get("status"),
            "bgmCueCount": bgm_summary.get("bgmCueCount"),
        },
        "openingTitleSuggestion": {
            "mainTitleCandidate": delivery_title(delivery).upper()[:36],
            "subtitleCandidate": clean_words(delivery_title(delivery), 80),
            "policy": "one short city/place title on real footage; no route/date/internal labels; suppress V3 subtitles in this window",
        },
        "policy": {
            "firstThreeMinutesNeedViewerPromise": True,
            "destinationProofBeforeExplanation": True,
            "practicalArrivalReturnsAfterHook": True,
            "livedInTextureBeforeMinuteThree": True,
            "cleanTitleNoStackedText": True,
            "titleZoneSubtitleSuppressionRequired": True,
            "bgmOnlyOpeningDefault": True,
            "localFootageBeforeStock": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "beatRows": beat_rows,
        "weakTitleEvidence": [clip_summary(clip) for clip in weak_titles[:12]],
        "selectionRubric": {
            "pass": [
                "The first 40 seconds give a viewer promise using real destination or route footage.",
                "The first minute proves the destination visually before long explanation.",
                "A single clean hero title sits on real footage without route/date/internal clutter or subtitle overlap.",
                "Before minute three, the edit returns to practical arrival or route material.",
                "Before minute three, the edit includes lived-in travel texture such as street, food, hotel, sign, weather, or crowd.",
                "The first handoff uses movement or lived-in bridge material rather than an abrupt reset.",
            ],
            "reject": [
                "The opening is only a black slate, generic title card, or unexplained scenic montage.",
                "The title has duplicate/stacked route/date text or visible internal labels.",
                "The first three minutes never show how the trip starts, arrives, or moves.",
                "A travel film claims reference quality while the opening has no viewer promise or practical route proof.",
            ],
        },
        "nextActions": [
            "Fill each beat row's decision fields before Resolve apply.",
            "Use footage_select_plan hero and route_movement_bridge rows to repair any missing opening beat.",
            "Run title typography, visual establishing, audio scene policy, and BGM selection again if the opening story plan changes.",
            "After Resolve apply, paste readback evidence into beat rows and rerun V14 and Skill maturity contracts.",
        ],
        "safety": {
            "writesResolve": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Opening Story Plan",
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
        "## Title Suggestion",
        "",
        f"- Main: `{plan['openingTitleSuggestion']['mainTitleCandidate']}`",
        f"- Subtitle: `{plan['openingTitleSuggestion']['subtitleCandidate']}`",
        f"- Policy: {plan['openingTitleSuggestion']['policy']}",
        "",
        "## Beat Rows",
    ]
    for row in plan["beatRows"]:
        lines.extend(
            [
                "",
                f"### {row['beatId']}",
                f"- Label: {row['label']}",
                f"- Status: `{row['status']}`",
                f"- Window: `{row['targetWindowSeconds'][0]}` to `{row['targetWindowSeconds'][1]}`",
                f"- Evidence count: `{row['evidenceCount']}`",
                f"- Required: `{', '.join(row['requiredEvidence'])}`",
                f"- Action: {row['recommendedAction']}",
                "- Decision fields to fill:",
            ]
        )
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
        if row["evidenceClips"]:
            lines.append("- Evidence clips:")
            for clip in row["evidenceClips"][:6]:
                lines.append(
                    f"  - `{clip.get('timelineStartSeconds')}`-`{clip.get('timelineEndSeconds')}` "
                    f"`{clip.get('role')}` `{clip.get('sourceName')}`"
                )
    if plan.get("weakTitleEvidence"):
        lines.extend(["", "## Weak Title Evidence"])
        for clip in plan["weakTitleEvidence"]:
            lines.append(f"- `{clip.get('sourceName')}` `{clip.get('role')}` `{clip.get('timelineStartSeconds')}`")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a first-three-minutes opening story plan for a travel package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--opening-window-seconds", type=float, default=OPENING_WINDOW_SECONDS)
    parser.add_argument("--output-dir", help="Defaults to <package>/opening_story_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "opening_story_plan"
    plan = build_plan(package_dir, args.opening_window_seconds)
    write_json(output_dir / "opening_story_plan.json", plan)
    write_markdown(output_dir / "opening_story_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 2 if plan["status"] == "blocked_missing_resolve_blueprint" else 0


if __name__ == "__main__":
    raise SystemExit(main())
