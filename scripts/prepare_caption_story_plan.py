#!/usr/bin/env python3
"""Prepare proactive dense-caption and text-only narration planning rows."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SRT_TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)

TITLE_ROLE_TERMS = ("opening_city", "chapter_title", "ending_city", "title_bridge", "city_aerial_title")

DECISION_FIELDS = {
    "approvedSubtitleSource": "",
    "approvedTextOnlyNarrationPath": "",
    "approvedSrtPath": "",
    "renderMode": "resolve_overlay_video",
    "titleZoneSuppressionVerified": False,
    "requiresRewrite": False,
    "rewriteNotes": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

CAPTION_FUNCTIONS = [
    "route_honesty",
    "visual_observation",
    "movement_or_transition",
    "lived_in_texture",
    "emotional_aftertaste",
]


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_words(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def srt_time_to_seconds(value: str) -> float:
    value = value.replace(",", ".")
    hh, mm, rest = value.split(":")
    ss = float(rest)
    return int(hh) * 3600 + int(mm) * 60 + ss


def seconds_to_srt_time(value: float) -> str:
    value = max(0.0, float(value))
    ms_total = int(round(value * 1000))
    hh, rem = divmod(ms_total, 3600 * 1000)
    mm, rem = divmod(rem, 60 * 1000)
    ss, ms = divmod(rem, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def parse_srt(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    cues: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="ignore").strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        time_index = 1 if lines[0].isdigit() and len(lines) > 1 else 0
        if time_index >= len(lines):
            continue
        match = SRT_TIME_RE.search(lines[time_index])
        if not match:
            continue
        text = " ".join(lines[time_index + 1 :]).strip()
        if not text:
            continue
        cues.append(
            {
                "start": srt_time_to_seconds(match.group("start")),
                "end": srt_time_to_seconds(match.group("end")),
                "text": text,
            }
        )
    return cues


def find_subtitle_path(package_dir: Path, blueprint: dict[str, Any]) -> Path | None:
    candidates: list[Path] = []
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    if assets.get("subtitles"):
        candidates.append(Path(str(assets["subtitles"])).expanduser())
    candidates.extend(sorted(package_dir.glob("subtitles*_dense.srt")))
    candidates.extend([package_dir / "subtitles_v4_dense.srt", package_dir / "subtitles.srt"])
    return next((path for path in candidates if path.exists()), None)


def target_duration(package_dir: Path, blueprint: dict[str, Any], cues: list[dict[str, Any]]) -> float:
    for path in (package_dir / "render_delivery_verification.json", package_dir / "FINAL_DELIVERY_REPORT.json"):
        data = load_json(path) or {}
        for key in ("durationSeconds", "duration"):
            value = as_float(data.get(key))
            if value:
                return value
    for key in ("targetDurationSeconds", "actualVideoCoverageSeconds"):
        value = as_float(blueprint.get(key))
        if value:
            return value
    if cues:
        return max(float(cue["end"]) for cue in cues)
    return 20 * 60.0


def clip_start(clip: dict[str, Any]) -> float | None:
    for key in ("timelineStartSeconds", "startSeconds", "start", "timelineStart"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    return None


def clip_end(clip: dict[str, Any]) -> float | None:
    for key in ("timelineEndSeconds", "endSeconds", "end", "timelineEnd"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    start = clip_start(clip)
    duration = as_float(clip.get("durationSeconds") or clip.get("duration"))
    if start is not None and duration is not None:
        return start + duration
    return None


def active_chapters(delivery: dict[str, Any], blueprint: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    source = [
        row
        for row in delivery.get("chapters") or []
        if isinstance(row, dict) and not row.get("markedDoNotCut")
    ]
    chapters: list[dict[str, Any]] = []
    for fallback_index, row in enumerate(source, start=1):
        chapters.append(
            {
                "index": int(row.get("index") or fallback_index),
                "chapter": clean_words(row.get("chapter") or row.get("title") or f"Chapter {fallback_index}"),
                "place": clean_words(row.get("place") or row.get("routeStop") or row.get("city") or ""),
                "city": clean_words(row.get("city") or ""),
                "country": clean_words(row.get("country") or ""),
            }
        )
    if not chapters:
        return []

    clips = [row for row in blueprint.get("clips") or [] if isinstance(row, dict)]
    grouped: dict[int, list[dict[str, Any]]] = {}
    for clip in clips:
        try:
            chapter_index = int(clip.get("chapterIndex"))
        except (TypeError, ValueError):
            continue
        role = str(clip.get("role") or "").lower()
        if "subtitle" in role:
            continue
        grouped.setdefault(chapter_index, []).append(clip)

    default_step = duration / max(len(chapters), 1)
    for fallback_index, chapter in enumerate(chapters, start=1):
        group = grouped.get(chapter["index"]) or []
        starts = [clip_start(clip) for clip in group]
        ends = [clip_end(clip) for clip in group]
        starts = [value for value in starts if value is not None]
        ends = [value for value in ends if value is not None]
        chapter["timelineStartSeconds"] = round(min(starts), 3) if starts else round((fallback_index - 1) * default_step, 3)
        chapter["timelineEndSeconds"] = round(max(ends), 3) if ends else round(fallback_index * default_step, 3)
    chapters.sort(key=lambda row: float(row.get("timelineStartSeconds") or 0))
    for idx, chapter in enumerate(chapters):
        if idx + 1 < len(chapters):
            chapter["timelineEndSeconds"] = min(
                float(chapter["timelineEndSeconds"]),
                float(chapters[idx + 1]["timelineStartSeconds"]),
            )
    return chapters


def cues_in_window(cues: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    return [cue for cue in cues if float(cue["start"]) < end and float(cue["end"]) > start]


def cue_gap_stats(cues: list[dict[str, Any]], duration: float) -> dict[str, Any]:
    if not cues:
        return {"maxGapSeconds": None, "gapCountOver75Seconds": 0, "longestGap": None}
    sorted_cues = sorted(cues, key=lambda cue: float(cue["start"]))
    gaps: list[dict[str, float]] = []
    prev_end = 0.0
    for cue in sorted_cues:
        start = float(cue["start"])
        if start > prev_end:
            gaps.append({"start": prev_end, "end": start, "duration": start - prev_end})
        prev_end = max(prev_end, float(cue["end"]))
    if duration > prev_end:
        gaps.append({"start": prev_end, "end": duration, "duration": duration - prev_end})
    longest = max(gaps, key=lambda row: row["duration"]) if gaps else None
    return {
        "maxGapSeconds": round(longest["duration"], 3) if longest else 0.0,
        "gapCountOver75Seconds": sum(1 for row in gaps if row["duration"] > 75),
        "longestGap": {key: round(value, 3) for key, value in longest.items()} if longest else None,
    }


def title_zones(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    policy = blueprint.get("subtitleDeliveryPolicy") if isinstance(blueprint.get("subtitleDeliveryPolicy"), dict) else {}
    title_policy = policy.get("titleZoneSubtitlePolicy") if isinstance(policy.get("titleZoneSubtitlePolicy"), dict) else {}
    for row in title_policy.get("zones") or []:
        if not isinstance(row, dict):
            continue
        start = as_float(row.get("start"))
        end = as_float(row.get("end"))
        if start is None or end is None:
            continue
        zones.append(
            {
                "role": row.get("role"),
                "start": start,
                "end": end,
                "title": row.get("title"),
                "source": "subtitleDeliveryPolicy",
            }
        )
    clips = [row for row in blueprint.get("clips") or [] if isinstance(row, dict)]
    for clip in clips:
        role = str(clip.get("role") or "").lower()
        if not any(term in role for term in TITLE_ROLE_TERMS):
            continue
        start = clip_start(clip)
        end = clip_end(clip)
        if start is None or end is None:
            continue
        zones.append(
            {
                "role": clip.get("role"),
                "start": start,
                "end": end,
                "title": clip.get("titleText") or clip.get("title") or clip.get("cityTitle"),
                "source": "resolveBlueprintClip",
            }
        )
    unique_zones: dict[tuple[float, float, str], dict[str, Any]] = {}
    for zone in zones:
        key = (round(float(zone["start"]), 2), round(float(zone["end"]), 2), str(zone.get("role") or ""))
        unique_zones[key] = zone
    return sorted(unique_zones.values(), key=lambda row: float(row["start"]))


def text_functions(text: str) -> list[str]:
    lower = text.lower()
    functions: list[str] = []
    if any(term in lower for term in ("gps", "确认", "线索", "画面支持", "不确定", "route", "location")):
        functions.append("route_honesty")
    if any(term in lower for term in ("车站", "机场", "地铁", "扶梯", "train", "station", "airport", "移动", "转向", "路线")):
        functions.append("movement_or_transition")
    if any(term in lower for term in ("街", "店", "餐", "便利店", "酒店", "灯光", "水边", "路口")):
        functions.append("lived_in_texture")
    if any(term in lower for term in ("慢", "安静", "呼吸", "留下", "回到", "结束", "aftertaste")):
        functions.append("emotional_aftertaste")
    if not functions:
        functions.append("visual_observation")
    return functions


def function_coverage(cues: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in CAPTION_FUNCTIONS}
    for cue in cues:
        for key in text_functions(str(cue.get("text") or "")):
            counts[key] = counts.get(key, 0) + 1
    return counts


def title_zone_policy(blueprint: dict[str, Any], cues: list[dict[str, Any]]) -> dict[str, Any]:
    zones = title_zones(blueprint)
    overlaps = []
    for zone in zones:
        matches = cues_in_window(cues, float(zone["start"]), float(zone["end"]))
        if matches:
            overlaps.append(
                {
                    "role": zone.get("role"),
                    "title": zone.get("title"),
                    "start": zone.get("start"),
                    "end": zone.get("end"),
                    "overlapCueCount": len(matches),
                    "sampleTexts": [cue["text"] for cue in matches[:3]],
                }
            )
    policy = blueprint.get("subtitleDeliveryPolicy") if isinstance(blueprint.get("subtitleDeliveryPolicy"), dict) else {}
    source_policy = policy.get("titleZoneSubtitlePolicy") if isinstance(policy.get("titleZoneSubtitlePolicy"), dict) else {}
    return {
        "mode": source_policy.get("mode") or "avoid_title_zones",
        "zoneCount": len(zones),
        "overlapCueCount": sum(row["overlapCueCount"] for row in overlaps),
        "overlapsBeforeSuppression": overlaps[:10],
        "renderedCueCount": policy.get("renderedCueCount"),
        "sourcePolicy": source_policy,
        "requireSuppressionWhenRendering": True,
    }


def write_text_export(path: Path, plan: dict[str, Any], cues: list[dict[str, Any]], source_text: str) -> None:
    lines = [
        "Travel Video Text-Only Narration And Caption Export",
        "",
        f"Package: {plan['packageDir']}",
        f"Created: {plan['createdAt']}",
        "",
        "Policy:",
        "- No generated voiceover audio unless the user explicitly approves it.",
        "- Use this TXT with the SRT as the narration/caption source for a no-voiceover travel cut.",
        "- Scenic, title, and transition sections remain BGM-led; subtitles stay out of title zones when rendered.",
        "",
    ]
    if source_text.strip():
        lines.extend(["Source narration text:", "", source_text.strip(), ""])
    lines.extend(["Caption cues:", ""])
    for idx, cue in enumerate(cues, start=1):
        lines.append(f"{idx:03d} [{seconds_to_srt_time(cue['start'])} -> {seconds_to_srt_time(cue['end'])}] {cue['text']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def source_narration_text(package_dir: Path) -> tuple[Path | None, str]:
    candidates = [package_dir / "narration.txt", package_dir / "voiceover_script.txt", package_dir / "script.txt"]
    for path in candidates:
        if path.exists():
            return path, path.read_text(encoding="utf-8", errors="ignore")
    return None, ""


def build_plan(package_dir: Path, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    subtitle_path = find_subtitle_path(package_dir, blueprint)
    cues = parse_srt(subtitle_path)
    duration = target_duration(package_dir, blueprint, cues)
    chapters = active_chapters(delivery, blueprint, duration)
    cues_per_minute = len(cues) / (duration / 60.0) if duration else 0.0
    target_cue_count = max(args.min_total_cues, math.ceil((duration / 60.0) * args.min_cues_per_minute))
    gap_stats = cue_gap_stats(cues, duration)
    title_policy = title_zone_policy(blueprint, cues)
    source_text_path, source_text = source_narration_text(package_dir)
    text_export_path = output_dir / "text_only_narration_export.txt"

    chapter_rows: list[dict[str, Any]] = []
    for chapter in chapters:
        start = float(chapter.get("timelineStartSeconds") or 0.0)
        end = float(chapter.get("timelineEndSeconds") or start)
        window_cues = cues_in_window(cues, start, end)
        target = max(args.min_chapter_cues, math.ceil(max(1.0, (end - start) / 60.0) * args.min_cues_per_minute))
        counts = function_coverage(window_cues)
        chapter_rows.append(
            {
                "chapterIndex": chapter["index"],
                "chapter": chapter.get("chapter"),
                "place": chapter.get("place"),
                "timelineStartSeconds": round(start, 3),
                "timelineEndSeconds": round(end, 3),
                "targetCueCount": target,
                "existingCueCount": len(window_cues),
                "meetsTarget": len(window_cues) >= target,
                "captionFunctions": CAPTION_FUNCTIONS,
                "existingFunctionCoverage": counts,
                "sampleCueTexts": [cue["text"] for cue in window_cues[:8]],
                "writingPrompts": [
                    "Anchor what the viewer can actually see; do not pretend GPS-grade certainty.",
                    "Use route movement, street detail, food/hotel/weather, and small observations to replace voiceover.",
                    "Keep lines short enough for mobile reading and avoid title-safe zones.",
                ],
                "decision": dict(DECISION_FIELDS),
            }
        )

    rows_meeting_target = sum(1 for row in chapter_rows if row["meetsTarget"])
    rendered_policy = blueprint.get("subtitleDeliveryPolicy") if isinstance(blueprint.get("subtitleDeliveryPolicy"), dict) else {}
    status = (
        "ready_with_dense_caption_plan"
        if subtitle_path
        and len(cues) >= target_cue_count
        and cues_per_minute >= args.min_cues_per_minute
        and (gap_stats["maxGapSeconds"] is None or float(gap_stats["maxGapSeconds"]) <= args.max_gap_seconds)
        and rows_meeting_target == len(chapter_rows)
        and title_policy["zoneCount"] >= 1
        else "needs_caption_expansion"
    )

    plan = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "deliveryPlan": str(package_dir / "delivery_plan.json"),
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "subtitleSrt": str(subtitle_path) if subtitle_path else None,
            "sourceNarrationText": str(source_text_path) if source_text_path else None,
        },
        "outputs": {
            "textOnlyNarrationExport": str(text_export_path),
            "captionStoryPlanJson": str(output_dir / "caption_story_plan.json"),
            "captionStoryPlanMarkdown": str(output_dir / "caption_story_plan.md"),
        },
        "summary": {
            "durationSeconds": round(duration, 3),
            "chapterCount": len(chapters),
            "chapterRowCount": len(chapter_rows),
            "rowsMeetingTarget": rows_meeting_target,
            "subtitleCueCount": len(cues),
            "targetCueCount": target_cue_count,
            "cuesPerMinute": round(cues_per_minute, 3),
            "minCuesPerMinute": args.min_cues_per_minute,
            "maxGapSeconds": gap_stats["maxGapSeconds"],
            "gapCountOver75Seconds": gap_stats["gapCountOver75Seconds"],
            "titleZoneCount": title_policy["zoneCount"],
            "titleZoneOverlapCueCount": title_policy["overlapCueCount"],
            "renderedCueCount": rendered_policy.get("renderedCueCount"),
            "subtitleMode": rendered_policy.get("mode"),
            "textOnlyNarrationExport": str(text_export_path),
        },
        "policy": {
            "voiceoverAudioAllowedByDefault": False,
            "ttsRequiresExplicitApproval": True,
            "outputTxtRequired": True,
            "srtRequired": True,
            "renderedSubtitlePreferred": True,
            "titleZoneSuppressionRequired": True,
            "audioMode": "bgm_only_no_camera_voice",
            "captionRole": "Captions carry route, emotion, honesty, and lived-in detail when voiceover is rejected.",
        },
        "titleZonePolicy": title_policy,
        "gapStats": gap_stats,
        "functionCoverage": function_coverage(cues),
        "chapterRows": chapter_rows,
        "writingRubric": {
            "pass": [
                "At least the target number of cues exists for the full runtime and each chapter.",
                "Captions explain route movement, visual evidence, daily texture, and emotion without pretending exact GPS truth.",
                "A text-only narration export exists so no generated voiceover is needed by default.",
                "Rendered subtitles are delivered through verified overlay/native/burned-in mode, with title-zone suppression.",
                "Lines remain concise enough for mobile reading and do not fight BGM-led scenic sections.",
            ],
            "reject": [
                "The package depends on voiceover audio after the user rejected voiceover.",
                "Subtitle density falls below the target or leaves long empty stretches in a no-voiceover cut.",
                "Opening/chapter/ending title zones are covered by subtitle overlays.",
                "Captions claim GPS-grade certainty from visual-only recognition.",
                "Only an SRT exists when a TXT narration/caption handoff was requested.",
            ],
        },
        "nextActions": [
            "If status is needs_caption_expansion, add chapter-level cues until target counts and gap limits pass.",
            "Use text_only_narration_export.txt as the script handoff when voiceover is rejected.",
            "Run prepare_subtitle_overlay_asset.py after the dense SRT is approved, keeping title-zone suppression enabled.",
            "Rerun audit_story_style_contract.py and audit_director_intent_contract.py after subtitle edits.",
        ],
        "safety": {
            "generatesVoiceoverAudio": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
            "downloadsExternalAssets": False,
        },
    }
    write_text_export(text_export_path, plan, cues, source_text)
    return plan


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Caption Story Plan",
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
        "## Policy",
    ]
    for key, value in plan["policy"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Chapter Rows"])
    for row in plan["chapterRows"]:
        lines.extend(
            [
                "",
                f"### Chapter {row['chapterIndex']}: {row.get('chapter')}",
                f"- Window: `{row['timelineStartSeconds']}`s to `{row['timelineEndSeconds']}`s",
                f"- Cue count: `{row['existingCueCount']}` / target `{row['targetCueCount']}`",
                f"- Meets target: `{row['meetsTarget']}`",
                f"- Caption functions: {', '.join(row['captionFunctions'])}",
                "- Sample cues:",
            ]
        )
        if row["sampleCueTexts"]:
            lines.extend(f"  - {text}" for text in row["sampleCueTexts"][:6])
        else:
            lines.append("  - None yet.")
        lines.append("- Decision fields to fill:")
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Title-Zone Policy", "", "```json", json.dumps(plan["titleZonePolicy"], ensure_ascii=False, indent=2)[:5000], "```"])
    lines.extend(["", "## Writing Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["writingRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["writingRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a dense caption and text-only narration plan for a travel package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/caption_story_plan.")
    parser.add_argument("--min-total-cues", type=int, default=80)
    parser.add_argument("--min-cues-per-minute", type=float, default=4.0)
    parser.add_argument("--min-chapter-cues", type=int, default=6)
    parser.add_argument("--max-gap-seconds", type=float, default=75.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "caption_story_plan"
    plan = build_plan(package_dir, args, output_dir)
    write_json(output_dir / "caption_story_plan.json", plan)
    write_markdown(output_dir / "caption_story_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": plan["status"],
                    "outputDir": str(output_dir),
                    "subtitleCueCount": plan["summary"]["subtitleCueCount"],
                    "targetCueCount": plan["summary"]["targetCueCount"],
                    "cuesPerMinute": plan["summary"]["cuesPerMinute"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
