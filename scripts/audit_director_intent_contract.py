#!/usr/bin/env python3
"""Audit the director intent, pacing arc, and non-template travel-film structure."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


TRANSPORT_TERMS = (
    "airport",
    "terminal",
    "arrival",
    "departure",
    "train",
    "rail",
    "shinkansen",
    "station",
    "platform",
    "metro",
    "subway",
    "taxi",
    "vehicle",
    "window",
    "bridge",
    "transfer",
    "机场",
    "抵达",
    "出发",
    "车站",
    "站台",
    "车窗",
    "铁路",
    "新干线",
    "地铁",
    "路",
    "移动",
)
STREET_TERMS = (
    "street",
    "city",
    "walking",
    "district",
    "canal",
    "river",
    "night",
    "signage",
    "shop",
    "retail",
    "skyline",
    "街",
    "城市",
    "街区",
    "路口",
    "招牌",
    "河",
    "夜",
    "商店",
)
LIVED_IN_TERMS = (
    "hotel",
    "food",
    "dinner",
    "breakfast",
    "interior",
    "convenience",
    "waiting",
    "restaurant",
    "table",
    "酒店",
    "便利店",
    "餐",
    "室内",
    "等待",
    "行李",
    "生活",
)
LANDMARK_TERMS = (
    "tower",
    "castle",
    "temple",
    "shrine",
    "dotonbori",
    "namba",
    "ginza",
    "akihabara",
    "asakusa",
    "senso",
    "park",
    "塔",
    "城",
    "寺",
    "神社",
    "道顿堀",
    "难波",
    "银座",
    "秋叶原",
    "浅草",
    "公园",
)
OPENING_HOOK_TERMS = ("不是一分钟", "路线", "移动", "GPS", "线索", "呼吸", "开场", "进入")
ENDING_TERMS = ("最后", "回看", "回到", "记忆", "停在", "结束", "余味", "带走")
EMOTION_TERMS = ("记忆", "温度", "呼吸", "真实", "慢", "安静", "进入", "气口", "空气", "余味")
HONESTY_TERMS = ("GPS", "线索", "确认", "证据", "识别", "画面支持")


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


def as_seconds(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clip_start(clip: dict[str, Any]) -> float:
    return as_seconds(clip.get("timelineStartSeconds", clip.get("startSeconds")))


def clip_end(clip: dict[str, Any]) -> float:
    end = clip.get("timelineEndSeconds", clip.get("endSeconds"))
    if end is not None:
        return as_seconds(end)
    return clip_start(clip) + clip_duration(clip)


def clip_duration(clip: dict[str, Any]) -> float:
    duration = clip.get("durationSeconds")
    if duration is not None:
        return as_seconds(duration)
    return max(0.0, clip_end(clip) - clip_start(clip))


def role_text(clip: dict[str, Any]) -> str:
    return str(clip.get("role") or clip.get("type") or "").lower()


def categories_for_text(text: str) -> dict[str, bool]:
    lower = text.lower()
    return {
        "transport": any(term.lower() in lower for term in TRANSPORT_TERMS),
        "street": any(term.lower() in lower for term in STREET_TERMS),
        "livedIn": any(term.lower() in lower for term in LIVED_IN_TERMS),
        "landmark": any(term.lower() in lower for term in LANDMARK_TERMS),
    }


def chapter_text(chapter: dict[str, Any]) -> str:
    return " ".join(
        str(chapter.get(key) or "")
        for key in ("chapter", "title", "place", "city", "country", "confidenceLevel", "targetRole")
    )


def cue_time(line: str) -> float:
    h, m, rest = line.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    cues: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_line = next((line for line in lines if "-->" in line), "")
        if not time_line:
            continue
        try:
            start_raw, end_raw = [part.strip() for part in time_line.split("-->", 1)]
            body = " ".join(line for line in lines if "-->" not in line and not line.isdigit())
            cues.append({"start": cue_time(start_raw), "end": cue_time(end_raw), "text": body})
        except Exception:
            continue
    return cues


def find_subtitle_path(package_dir: Path, blueprint: dict[str, Any]) -> Path | None:
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    candidates = []
    if assets.get("subtitles"):
        candidates.append(Path(str(assets["subtitles"])).expanduser())
    candidates.extend(sorted(package_dir.glob("subtitles*_dense.srt")))
    candidates.extend([package_dir / "subtitles.srt", package_dir / "subtitles_v4_dense.srt"])
    return next((path for path in candidates if path.exists()), None)


def cues_in_window(cues: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    return [cue for cue in cues if cue["start"] < end and cue["end"] > start]


def cue_text_contains(cues: list[dict[str, Any]], terms: tuple[str, ...]) -> bool:
    text = " ".join(str(cue.get("text") or "") for cue in cues)
    return any(term in text for term in terms)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else ("warning" if warning else "blocked"),
            "evidence": evidence,
        }
    )


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    reference = load_json(package_dir / "reference_style_alignment_audit.json") or {}
    route_texture = load_json(package_dir / "route_texture_contract_audit.json") or {}
    bgm = load_json(package_dir / "bgm_audio_contract_audit.json") or {}
    story = load_json(package_dir / "story_style_contract_audit.json") or {}
    location_truth = load_json(package_dir / "location_truth_contract_audit.json") or {}
    final_qa = load_json(package_dir / "final_qa_suite_report.json") or {}

    clips = [clip for clip in blueprint.get("clips") or [] if isinstance(clip, dict)]
    video_clips = [clip for clip in clips if str(clip.get("trackType") or "video").lower() == "video"]
    main_clips = [clip for clip in video_clips if clip.get("trackIndex") == 1 and "subtitle" not in role_text(clip)]
    title_clips = [clip for clip in video_clips if "title" in role_text(clip) or "opening_city" in role_text(clip) or "ending_city" in role_text(clip)]
    transition_clips = [clip for clip in video_clips if "transition_bridge" in role_text(clip)]
    subtitle_path = find_subtitle_path(package_dir, blueprint)
    cues = parse_srt(subtitle_path)

    chapters = [row for row in delivery.get("chapters") or [] if isinstance(row, dict)]
    sections = [row for row in delivery.get("longFormSections") or [] if isinstance(row, dict)]
    opening_section = next((row for row in sections if row.get("chapterIndex") == 0 or "opening" in str(row.get("targetRole") or "").lower()), {})
    ending_section = next((row for row in sections if "ending" in str(row.get("targetRole") or "").lower() or str(row.get("place") or "").lower() == "ending"), {})

    checks: list[dict[str, Any]] = []

    style_reference = Path(__file__).resolve().parents[1] / "references" / "bilibili-travel-style.md"
    style_text = style_reference.read_text(encoding="utf-8", errors="ignore") if style_reference.exists() else ""
    add_check(
        checks,
        "Reference sources are treated as non-copying style anchors",
        reference.get("status") == "passed"
        and "space.bilibili.com/946974" in style_text
        and "space.bilibili.com/405004967" in style_text
        and "not as assets to copy" in style_text,
        {"referenceStatus": reference.get("status"), "styleReference": str(style_reference)},
    )

    opening_start = as_seconds(opening_section.get("startSeconds"))
    opening_end = opening_start + as_seconds(opening_section.get("durationSeconds"), 0.0)
    opening_cues = cues_in_window(cues, opening_start, max(opening_end, 45.0))
    opening_title_clips = [clip for clip in title_clips if clip_start(clip) <= 12.0]
    add_check(
        checks,
        "Opening establishes a clear mission, city signal, and breathing room",
        bool(opening_section)
        and as_seconds(opening_section.get("durationSeconds")) >= args.min_opening_seconds
        and bool(opening_title_clips)
        and len(opening_cues) >= args.min_opening_cues
        and cue_text_contains(opening_cues, OPENING_HOOK_TERMS),
        {
            "openingSection": opening_section,
            "openingTitleClipCount": len(opening_title_clips),
            "openingCueCount": len(opening_cues),
            "sampleOpeningCues": [cue["text"] for cue in opening_cues[:8]],
        },
    )

    chapter_evidence = []
    category_totals = {"transport": 0, "street": 0, "livedIn": 0, "landmark": 0}
    for chapter in chapters:
        text = chapter_text(chapter)
        cats = categories_for_text(text)
        for key, value in cats.items():
            if value:
                category_totals[key] += 1
        chapter_evidence.append(
            {
                "index": chapter.get("index"),
                "chapter": chapter.get("chapter"),
                "place": chapter.get("place"),
                "categories": cats,
                "categoryCount": sum(1 for value in cats.values() if value),
            }
        )
    enough_chapter_detail = sum(1 for row in chapter_evidence if row["categoryCount"] >= 2) >= max(1, len(chapters) - 1)
    add_check(
        checks,
        "Chapter beats cover movement, city texture, lived-in detail, and payoff",
        len(chapters) >= args.min_chapters
        and enough_chapter_detail
        and all(value > 0 for value in category_totals.values()),
        {"chapterCount": len(chapters), "categoryTotals": category_totals, "perChapter": chapter_evidence},
    )

    first_text = chapter_text(chapters[0]) if chapters else ""
    last_text = chapter_text(chapters[-1]) if chapters else ""
    middle_text = " ".join(chapter_text(row) for row in chapters[1:-1])
    route_arc_ok = (
        any(term in first_text.lower() for term in ("arrival", "airport", "terminal", "抵达", "机场"))
        and any(term in middle_text.lower() for term in ("osaka", "tokyo", "shinkansen", "大阪", "东京", "新干线"))
        and any(term in last_text.lower() for term in ("departure", "airport", "flight", "kansai", "出发", "机场", "航班"))
    )
    add_check(
        checks,
        "Route arc has arrival, intercity movement, exploration, and closure",
        route_arc_ok,
        {"firstChapter": first_text, "middleText": middle_text[:1200], "lastChapter": last_text},
    )

    durations = [clip_duration(clip) for clip in main_clips if clip_duration(clip) > 0.2]
    median_duration = median(durations) if durations else 0.0
    too_long = [duration for duration in durations if duration > args.max_main_clip_seconds]
    too_short_ratio = len([duration for duration in durations if duration < args.min_main_clip_seconds]) / len(durations) if durations else 1.0
    add_check(
        checks,
        "Shot pacing reads as long-form travel rhythm rather than slideshow or dump",
        bool(durations)
        and args.min_median_clip_seconds <= median_duration <= args.max_median_clip_seconds
        and len(too_long) <= args.max_overlong_main_clips
        and too_short_ratio <= 0.35
        and len(transition_clips) >= max(1, len(chapters) - 1),
        {
            "mainClipCount": len(durations),
            "medianMainClipSeconds": round(median_duration, 3),
            "overlongMainClipCount": len(too_long),
            "shortMainClipRatio": round(too_short_ratio, 3),
            "transitionBridgeClipCount": len(transition_clips),
        },
    )

    full_text = " ".join(cue["text"] for cue in cues)
    cue_count = len(cues)
    cues_per_minute = cue_count / (max((clip_end(clip) for clip in video_clips), default=0.0) / 60.0) if video_clips else 0.0
    subtitle_arc_ok = (
        cue_count >= args.min_subtitle_cues
        and cues_per_minute >= args.min_cues_per_minute
        and any(term in full_text for term in EMOTION_TERMS)
        and any(term in full_text for term in HONESTY_TERMS)
    )
    add_check(
        checks,
        "Captions carry story, route honesty, and emotional texture without voiceover",
        subtitle_arc_ok
        and bgm.get("status") == "passed"
        and story.get("status") == "passed",
        {
            "subtitlePath": str(subtitle_path) if subtitle_path else None,
            "cueCount": cue_count,
            "cuesPerMinute": round(cues_per_minute, 3),
            "hasEmotionTerms": any(term in full_text for term in EMOTION_TERMS),
            "hasRouteHonestyTerms": any(term in full_text for term in HONESTY_TERMS),
            "bgmStatus": bgm.get("status"),
            "storyStatus": story.get("status"),
        },
    )

    ending_end = as_seconds(ending_section.get("startSeconds")) + as_seconds(ending_section.get("durationSeconds"), 0.0)
    final_end = max((clip_end(clip) for clip in video_clips), default=0.0)
    ending_start = as_seconds(ending_section.get("startSeconds"), max(0.0, final_end - 60.0))
    ending_cues = cues_in_window(cues, max(0.0, ending_start - 8.0), final_end + 1.0)
    ending_title_clips = [clip for clip in title_clips if clip_start(clip) >= max(0.0, final_end - 90.0)]
    add_check(
        checks,
        "Ending closes the journey with scenic aftertaste, not an abrupt stop",
        bool(ending_section)
        and ending_end > ending_start
        and bool(ending_title_clips)
        and len(ending_cues) >= args.min_ending_cues
        and cue_text_contains(ending_cues, ENDING_TERMS),
        {
            "endingSection": ending_section,
            "endingTitleClipCount": len(ending_title_clips),
            "endingCueCount": len(ending_cues),
            "sampleEndingCues": [cue["text"] for cue in ending_cues[-8:]],
        },
    )

    upstream_ok = (
        reference.get("status") == "passed"
        and route_texture.get("status") == "passed"
        and bgm.get("status") == "passed"
        and story.get("status") == "passed"
        and location_truth.get("status") in {"passed", "passed_with_caveats"}
    )
    add_check(
        checks,
        "Existing technical/style gates support the director-intent claim",
        upstream_ok,
        {
            "referenceStyle": reference.get("status"),
            "routeTexture": route_texture.get("status"),
            "bgmAudio": bgm.get("status"),
            "storyStyle": story.get("status"),
            "locationTruth": location_truth.get("status"),
            "finalQa": final_qa.get("status"),
        },
    )
    if final_qa:
        add_check(
            checks,
            "Final QA suite status is informational for director intent",
            final_qa.get("status") == "passed",
            {"finalQa": final_qa.get("status"), "blockers": final_qa.get("blockers")},
            warning=True,
        )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings = [row["name"] for row in checks if row["status"] == "warning"]
    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    manifest = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "purpose": "Make the intended travel-film arc explicit before claiming Bilibili/Malta-like quality.",
        "openingIntent": {
            "role": opening_section.get("targetRole"),
            "durationSeconds": opening_section.get("durationSeconds"),
            "missionTermsFound": [term for term in OPENING_HOOK_TERMS if cue_text_contains(opening_cues, (term,))],
        },
        "routeArc": {
            "first": first_text,
            "last": last_text,
            "categoryTotals": category_totals,
            "chapters": chapter_evidence,
        },
        "pacing": {
            "mainClipCount": len(durations),
            "medianMainClipSeconds": round(median_duration, 3),
            "transitionBridgeClipCount": len(transition_clips),
        },
        "captionArc": {
            "cueCount": cue_count,
            "cuesPerMinute": round(cues_per_minute, 3),
            "hasEmotionTerms": any(term in full_text for term in EMOTION_TERMS),
            "hasRouteHonestyTerms": any(term in full_text for term in HONESTY_TERMS),
        },
        "endingIntent": {
            "role": ending_section.get("targetRole"),
            "durationSeconds": ending_section.get("durationSeconds"),
            "endingTermsFound": [term for term in ENDING_TERMS if cue_text_contains(ending_cues, (term,))],
        },
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "passed": len([row for row in checks if row["status"] == "passed"]),
            "blocked": len(blockers),
            "warnings": len(warnings),
            "total": len(checks),
            "mainClipCount": len(durations),
            "medianMainClipSeconds": round(median_duration, 3),
            "subtitleCueCount": cue_count,
            "cuesPerMinute": round(cues_per_minute, 3),
            "chapterCount": len(chapters),
        },
        "directorIntentManifest": manifest,
        "contract": {
            "styleAnchors": [
                "影视飓风: production discipline, B-roll intention, visible craft",
                "叽叽歪歪的平行世界: long-route lived-in travel rhythm",
                "Local Malta reference: breathing room, transport texture, food/interior/human details, aftertaste",
            ],
            "nonCopying": "Use the references as structure and craft targets only; do not copy titles, footage, narration, or music.",
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Director Intent Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Checks",
    ]
    for row in report["checks"]:
        evidence = json.dumps(row["evidence"], ensure_ascii=False)[:2400]
        lines.extend(["", f"### {row['name']}", f"- Status: `{row['status']}`", f"- Evidence: `{evidence}`"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Contract", "", "```json", json.dumps(report["contract"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit director intent and long-form travel-film pacing.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-chapters", type=int, default=5)
    parser.add_argument("--min-opening-seconds", type=float, default=45.0)
    parser.add_argument("--min-opening-cues", type=int, default=4)
    parser.add_argument("--min-ending-cues", type=int, default=3)
    parser.add_argument("--min-subtitle-cues", type=int, default=80)
    parser.add_argument("--min-cues-per-minute", type=float, default=3.0)
    parser.add_argument("--min-main-clip-seconds", type=float, default=3.0)
    parser.add_argument("--max-main-clip-seconds", type=float, default=75.0)
    parser.add_argument("--min-median-clip-seconds", type=float, default=8.0)
    parser.add_argument("--max-median-clip-seconds", type=float, default=45.0)
    parser.add_argument("--max-overlong-main-clips", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "director_intent_contract_audit.json", report)
    write_json(package_dir / "director_intent_manifest.json", report["directorIntentManifest"])
    write_markdown(package_dir / "director_intent_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "warnings": report["warnings"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
