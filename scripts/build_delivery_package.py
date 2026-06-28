#!/usr/bin/env python3
"""Create a long-form travel-video delivery package from VideoClaw artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from build_asset_ledger import aerial_items, bgm_items, font_items, write_markdown as write_ledger_markdown
from enrich_resolve_blueprint import apply_enrichment_to_blueprint, build_enrichment
from prepare_asset_sourcing_packet import build_packet as build_asset_sourcing_packet
from prepare_asset_sourcing_packet import write_packet_outputs as write_asset_sourcing_packet_outputs
from project_discovery import discover_project_path


DEFAULT_APP_DIR = Path("/Users/pengyang/Pictures/Video-make/video-claw-studio")
DEFAULT_TARGET_MINUTES = 20.0


def load_json(path: Path | None) -> Any:
    if not path:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


def latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def discover_project(path: Path, project_name: str | None) -> Path:
    return discover_project_path(path, project_name)


def clean_text(text: Any, fallback: str = "unknown") -> str:
    if text is None:
        return fallback
    value = str(text).strip()
    return value or fallback


def artifact_paths(project_dir: Path) -> dict[str, Path | None]:
    return {
        "project": latest(list(project_dir.glob("project.json"))),
        "mediaIndex": latest(list(project_dir.glob("media_index.json"))),
        "videoLocationMap": latest(list(project_dir.glob("video_location_map.json"))),
        "routeTimeline": latest(list(project_dir.glob("route_timeline.json"))),
        "confirmedRoute": latest(list(project_dir.glob("confirmed_route_timeline.json"))),
        "pipeline": latest(list(project_dir.glob("latest_location_route_pipeline.json"))),
    }


def choose_route(paths: dict[str, Path | None]) -> tuple[str, dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    route_path = paths.get("routeTimeline")
    confirmed_path = paths.get("confirmedRoute")
    route = load_json(route_path)
    confirmed = load_json(confirmed_path)
    if isinstance(confirmed, dict) and confirmed_path and route_path:
        if confirmed_path.stat().st_mtime >= route_path.stat().st_mtime:
            return "confirmed_route_timeline.json", confirmed, warnings
        warnings.append("confirmed_route_timeline.json is older than route_timeline.json; using automatic route for draft package.")
    if isinstance(confirmed, dict) and confirmed_path and not route_path:
        return "confirmed_route_timeline.json", confirmed, warnings
    if isinstance(route, dict):
        return "route_timeline.json", route, warnings
    warnings.append("No route timeline found; creating a placeholder package.")
    return "none", None, warnings


def media_files(media_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(media_index, dict):
        return []
    files = media_index.get("files", [])
    return [f for f in files if isinstance(f, dict) and f.get("kind") == "video" and f.get("path")]


def apply_source_exclusions(project_dir: Path, media_index: dict[str, Any] | None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not isinstance(media_index, dict):
        return media_index, []
    payload = load_json(project_dir / "source_exclusions.json")
    if not isinstance(payload, dict):
        return media_index, []
    active = [item for item in payload.get("items") or [] if item.get("active", True)]
    excluded_paths = {str(item.get("path")) for item in active if item.get("path")}
    excluded_ids = {str(item.get("fileId")) for item in active if item.get("fileId")}
    excluded = []
    kept = []
    for item in media_index.get("files") or []:
        if str(item.get("path")) in excluded_paths or str(item.get("fileId")) in excluded_ids:
            excluded.append(item)
        else:
            kept.append(item)
    filtered = dict(media_index)
    filtered["files"] = kept
    summary = dict(filtered.get("summary") or {})
    summary["videoCount"] = sum(1 for item in kept if item.get("kind") == "video")
    summary["excludedVideoCount"] = len(excluded)
    filtered["summary"] = summary
    return filtered, excluded


def route_chapters(route: dict[str, Any] | None, media_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    id_to_media = {f.get("fileId"): f for f in media_files(media_index)}
    path_to_media = {f.get("path"): f for f in media_files(media_index)}
    chapters = route.get("chapters") if isinstance(route, dict) else []
    out = []
    for idx, ch in enumerate(chapters or [], 1):
        if not isinstance(ch, dict):
            continue
        place = clean_text(ch.get("place") or ch.get("chapter"), f"Chapter {idx}")
        chapter_media = []
        for vid in ch.get("videos", []) or []:
            media = id_to_media.get(vid)
            if media:
                chapter_media.append(media)
        for path in ch.get("videoPaths", []) or []:
            media = path_to_media.get(path)
            if media and media not in chapter_media:
                chapter_media.append(media)
        out.append(
            {
                "index": idx,
                "chapter": clean_text(ch.get("chapter"), place),
                "place": place,
                "city": clean_text(ch.get("city"), ""),
                "country": clean_text(ch.get("country"), ""),
                "confidence": ch.get("confidence"),
                "confidenceLevel": clean_text(ch.get("confidenceLevel"), ""),
                "videoCount": len(ch.get("videos", []) or chapter_media),
                "isTransit": bool(ch.get("isTransit")),
                "needsHumanReview": bool(ch.get("needsHumanReview")) or clean_text(place).lower().startswith("unknown"),
                "markedDoNotCut": bool(ch.get("markedDoNotCut")),
                "media": chapter_media,
            }
        )
    if not out and media_index:
        videos = media_files(media_index)
        if videos:
            out.append(
                {
                    "index": 1,
                    "chapter": "素材整理",
                    "place": "unknown",
                    "city": "",
                    "country": "",
                    "confidence": None,
                    "confidenceLevel": "",
                    "videoCount": len(videos),
                    "isTransit": False,
                    "needsHumanReview": True,
                    "markedDoNotCut": False,
                    "media": videos,
                }
            )
    return out


def enrich_chapter_media(chapters: list[dict[str, Any]], media_index: dict[str, Any] | None) -> None:
    all_media = media_files(media_index)
    if not chapters or not all_media:
        return
    assigned = {m.get("path") for ch in chapters for m in ch.get("media", []) if m.get("path")}
    remaining = [m for m in all_media if m.get("path") not in assigned]
    if not remaining:
        return
    chapter_count = len(chapters)
    for idx, media in enumerate(remaining):
        chapters[idx % chapter_count].setdefault("media", []).append(media)
    for chapter in chapters:
        chapter["videoCount"] = max(chapter.get("videoCount") or 0, len(chapter.get("media", [])))


def region_for_text(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ["tokyo", "东京", "東京", "japan", "日本"]):
        return "tokyo"
    if any(k in lower for k in ["osaka", "大阪"]):
        return "osaka"
    if any(k in lower for k in ["hong kong", "香港", "维港", "維港"]):
        return "hong-kong"
    if any(k in lower for k in ["macao", "macau", "澳门", "澳門"]):
        return "macao"
    return "generic"


def aerial_targets(place: str) -> list[str]:
    targets = {
        "tokyo": ["Tokyo Tower", "Shibuya crossing", "Shinjuku skyline", "Tokyo Skytree", "Sumida River"],
        "osaka": ["Dotonbori", "Osaka Castle", "Umeda skyline", "Namba street", "Tsutenkaku"],
        "hong-kong": ["Victoria Harbour", "Central skyline", "Star Ferry", "Tsim Sha Tsui", "Peak skyline"],
        "macao": ["Ruins of St. Paul's", "Macau Tower", "Cotai skyline", "Senado Square", "Taipa streets"],
        "generic": [place, f"{place} skyline", f"{place} street establishing shot"],
    }
    return targets.get(region_for_text(place), targets["generic"])


def bgm_mood(place: str, idx: int) -> str:
    region = region_for_text(place)
    if region in {"tokyo", "osaka"}:
        return "calm long-form Japan travel documentary: piano, soft synth, light strings, restrained city pulse"
    if region in {"hong-kong", "macao"}:
        return "harbor travel documentary: warm piano, airy pads, restrained percussion"
    if idx == 1:
        return "opening long-form travel documentary: warm piano and ambient texture"
    return "gentle long-form travel transition: light pulse, soft pads, restrained melody"


def allocate_chapter_durations(chapters: list[dict[str, Any]], target_seconds: float) -> list[dict[str, Any]]:
    if not chapters:
        return []
    opening = min(60.0, max(35.0, target_seconds * 0.05))
    ending = min(75.0, max(45.0, target_seconds * 0.055))
    transition_total = min(180.0, max(45.0, target_seconds * 0.08))
    available = max(60.0, target_seconds - opening - ending - transition_total)
    weights = [max(1.0, float(ch.get("videoCount") or len(ch.get("media") or []) or 1)) for ch in chapters]
    total_weight = sum(weights)
    cursor = opening
    sections = []
    for chapter, weight in zip(chapters, weights, strict=False):
        duration = available * weight / total_weight
        duration = max(90.0 if target_seconds >= 900 else 35.0, duration)
        sections.append(
            {
                "chapterIndex": chapter["index"],
                "place": chapter["place"],
                "startSeconds": round(cursor, 2),
                "durationSeconds": round(duration, 2),
                "targetRole": "main_chapter",
                "voiceoverPolicy": "sparse observational narration; leave room for natural sound and music",
            }
        )
        cursor += duration + transition_total / max(1, len(chapters))
    return [
        {
            "chapterIndex": 0,
            "place": "Opening",
            "startSeconds": 0,
            "durationSeconds": round(opening, 2),
            "targetRole": "opening_hook_and_route_setup",
            "voiceoverPolicy": "one concise setup, then visual breathing room",
        },
        *sections,
        {
            "chapterIndex": 999,
            "place": "Ending",
            "startSeconds": round(max(0.0, target_seconds - ending), 2),
            "durationSeconds": round(ending, 2),
            "targetRole": "emotional_close",
            "voiceoverPolicy": "short callback and aftertaste, not a slogan",
        },
    ]


def narration_lines(project: dict[str, Any] | None, chapters: list[dict[str, Any]], target_minutes: float) -> list[str]:
    title = clean_text((project or {}).get("title"), "这趟旅行")
    if chapters:
        first = chapters[0]["place"]
        last = chapters[-1]["place"]
        lines = [
            f"{title}不是一分钟的打卡视频，而是一条接近{int(target_minutes)}分钟的旅行长片。",
            f"我们从{first}开始，把零散素材重新排成一条能被看懂、也能被感受到的路线。",
        ]
    else:
        lines = [f"{title}，先把素材整理清楚，再从画面线索里找回这趟旅行的路线。"]
    for idx, chapter in enumerate(chapters, 1):
        place = chapter["place"]
        if chapter.get("needsHumanReview"):
            lines.append(f"第{idx}站，画面线索暂时指向{place}。这里不要急着下结论，先把招牌、街景和路线关系留给观众判断。")
        elif chapter.get("isTransit"):
            lines.append(f"从上一站到{place}，交通和等待不是废镜头，它们负责把时间真正带过去。")
        else:
            lines.append(f"来到{place}，节奏可以慢下来。不要只拍地标，也要保留街角、声音、路人的方向和同行人的反应。")
        if idx < len(chapters):
            next_place = chapters[idx]["place"]
            lines.append(f"转向{next_place}之前，用一段街头风景、车站、车窗或者地图线条，让第一天和下一段自然接上。")
    if chapters:
        lines.append(f"最后回看这条路线，重要的不是证明去过多少地方，而是这些镜头为什么最后停在了{last}。")
    return lines


def split_subtitle_text(line: str, max_len: int = 24) -> list[str]:
    line = re.sub(r"\s+", "", line.strip())
    if not line:
        return []
    parts = re.split(r"([，。！？；、])", line)
    merged: list[str] = []
    current = ""
    for part in parts:
        if not part:
            continue
        if len(current) + len(part) <= max_len:
            current += part
        else:
            if current:
                merged.append(current)
            current = part
    if current:
        merged.append(current)
    final: list[str] = []
    for item in merged:
        while len(item) > max_len:
            final.append(item[:max_len])
            item = item[max_len:]
        if item:
            final.append(item)
    return final


def srt_time(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_srt(lines: list[str]) -> str:
    entries = []
    cursor = 0.0
    idx = 1
    for line in lines:
        for part in split_subtitle_text(line):
            duration = max(2.2, min(6.5, len(part) / 5.2 + 0.8))
            entries.append(f"{idx}\n{srt_time(cursor)} --> {srt_time(cursor + duration)}\n{part}\n")
            cursor += duration + 0.15
            idx += 1
    return "\n".join(entries).strip() + "\n"


def build_asset_queries(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for chapter in chapters or [{"index": 1, "place": "Travel"}]:
        place = chapter["place"]
        targets = aerial_targets(place)
        items.append(
            {
                "chapterIndex": chapter["index"],
                "place": place,
                "aerialTargets": targets,
                "queries": [f"licensed {target} aerial 4K stock footage" for target in targets[:3]]
                + [
                    f"royalty free {place} long-form travel documentary establishing shot",
                    f"licensed {place} street ambience stock video",
                ],
                "licenseStatus": "needs web search and approval",
            }
        )
    return items


def build_bgm_cues(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cues = []
    for chapter in chapters or [{"index": 1, "place": "Travel"}]:
        place = chapter["place"]
        cues.append(
            {
                "chapterIndex": chapter["index"],
                "place": place,
                "mood": bgm_mood(place, chapter["index"]),
                "queries": [
                    f"licensed {place} calm long-form travel documentary BGM",
                    f"royalty free {place} cinematic piano ambient music",
                    "licensed travel documentary ambient piano soft strings 20 minute edit",
                ],
                "licenseStatus": "needs web search and approval",
            }
        )
    return cues


def typography_plan(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    combined = " ".join(ch["place"] for ch in chapters)
    if region_for_text(combined) in {"tokyo", "osaka"}:
        title_fonts = ["Hiragino Mincho ProN", "Yu Mincho", "Noto Serif CJK JP", "Shippori Mincho"]
    else:
        title_fonts = ["Hiragino Sans", "Noto Sans CJK", "Source Han Sans", "system sans-serif"]
    return {
        "titleCards": title_fonts,
        "subtitles": ["Hiragino Sans", "Noto Sans CJK", "Source Han Sans"],
        "mapLabels": ["Noto Sans CJK", "Hiragino Sans"],
        "licenseStatus": "use installed system fonts or verify font license before bundling",
    }


def transition_plan(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for i, chapter in enumerate(chapters):
        next_chapter = chapters[i + 1] if i + 1 < len(chapters) else None
        if next_chapter:
            bridge = f"{chapter['place']} -> {next_chapter['place']}"
            suggestion = "street ambience, station/vehicle detail, hotel window, food prep, or route map line animation"
        else:
            bridge = f"{chapter['place']} -> ending"
            suggestion = "hold on ambient detail, fade music tail, then closing title"
        plan.append(
            {
                "afterChapter": chapter["index"],
                "bridge": bridge,
                "suggestion": suggestion,
                "fallbackAssetNeed": "search local footage first; use licensed stock only if missing",
            }
        )
    return plan


def media_duration(media: dict[str, Any]) -> float:
    probe = media.get("probe") if isinstance(media.get("probe"), dict) else {}
    duration = media.get("duration") or probe.get("duration")
    if not duration and isinstance(probe.get("format"), dict):
        duration = probe["format"].get("duration")
    try:
        return float(duration)
    except Exception:  # noqa: BLE001
        return 8.0


def pick_clip_duration(media: dict[str, Any]) -> float:
    duration = max(0.1, media_duration(media))
    if duration <= 4.0:
        return max(1.5, duration * 0.9)
    target = duration * 0.78
    return max(4.0, min(28.0, target, duration - 0.25))


def make_blueprint_clip(
    role: str,
    chapter: dict[str, Any],
    media: dict[str, Any],
    source_start: float,
    duration: float,
    timeline_start: float,
    purpose: str,
) -> dict[str, Any] | None:
    source_path = media.get("path")
    if not source_path:
        return None
    source_duration = media_duration(media)
    source_start = max(0.0, min(source_start, max(0.0, source_duration - 1.0)))
    source_end = min(source_duration, source_start + max(0.1, duration))
    actual_duration = source_end - source_start
    if actual_duration < 1.0:
        return None
    return {
        "role": role,
        "chapterIndex": chapter.get("index"),
        "place": chapter.get("place"),
        "sourcePath": source_path,
        "sourceStartSeconds": round(source_start, 2),
        "sourceEndSeconds": round(source_end, 2),
        "timelineStartSeconds": round(timeline_start, 2),
        "timelineEndSeconds": round(timeline_start + actual_duration, 2),
        "trackType": "video",
        "trackIndex": 1,
        "mediaType": 1,
        "includeSourceAudio": True,
        "sourceAudioTrackIndex": 1,
        "purpose": purpose,
    }


def media_pool(chapters: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pool = []
    seen = set()
    for chapter in chapters:
        for media in chapter.get("media", []):
            path = media.get("path")
            if not path or path in seen:
                continue
            seen.add(path)
            if media_duration(media) >= 1.5:
                pool.append((chapter, media))
    return pool


def clip_coverage(clips: list[dict[str, Any]]) -> float:
    return sum(max(0.0, float(c["timelineEndSeconds"]) - float(c["timelineStartSeconds"])) for c in clips if c.get("trackIndex") == 1)


def coverage_gaps(clips: list[dict[str, Any]], target_seconds: float) -> list[tuple[float, float]]:
    intervals = sorted(
        (
            (max(0.0, float(c["timelineStartSeconds"])), min(target_seconds, float(c["timelineEndSeconds"])))
            for c in clips
            if c.get("trackIndex") == 1 and float(c.get("timelineEndSeconds") or 0) > 0
        ),
        key=lambda item: item[0],
    )
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in intervals:
        if start > cursor + 1.0:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < target_seconds - 1.0:
        gaps.append((cursor, target_seconds))
    return gaps


def fill_long_form_gaps(
    clips: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    target_seconds: float,
) -> dict[str, Any]:
    pool = media_pool(chapters)
    if not pool:
        return {"addedClipCount": 0, "addedSeconds": 0.0, "gapsFilled": [], "reason": "no media pool"}
    usage: dict[str, float] = {}
    for clip in clips:
        path = clip.get("sourcePath")
        if path:
            usage[path] = max(usage.get(path, 0.0), float(clip.get("sourceEndSeconds") or 0))
    section_roles = {section.get("chapterIndex"): section for section in sections}
    ending_start = float(section_roles.get(999, {}).get("startSeconds") or max(0.0, target_seconds - 75.0))
    added = []
    pool_index = 0
    for gap_start, gap_end in coverage_gaps(clips, target_seconds):
        cursor = gap_start
        while cursor < gap_end - 1.0 and pool:
            chapter, media = pool[pool_index % len(pool)]
            pool_index += 1
            path = media.get("path")
            if not path:
                continue
            source_duration = media_duration(media)
            source_start = usage.get(path, 0.0) + 0.25
            if source_start > source_duration - 1.25:
                source_start = 0.0
            remaining_source = max(0.0, source_duration - source_start)
            remaining_gap = gap_end - cursor
            wanted = min(remaining_gap, remaining_source, 16.0)
            if remaining_gap > 20.0:
                wanted = min(remaining_gap, remaining_source, max(6.0, wanted))
            if wanted < 1.0:
                continue
            if cursor < 60.0:
                role = "opening_visual_bed"
                purpose = "opening route promise and visual atmosphere"
            elif cursor >= ending_start:
                role = "ending_visual_bed"
                purpose = "closing callback and emotional aftertaste"
            else:
                role = "transition_bridge_footage"
                purpose = "long-form chapter bridge, transport, map, or street texture"
            clip = make_blueprint_clip(role, chapter, media, source_start, wanted, cursor, purpose)
            if not clip:
                continue
            clips.append(clip)
            added.append(
                {
                    "role": role,
                    "timelineStartSeconds": clip["timelineStartSeconds"],
                    "timelineEndSeconds": clip["timelineEndSeconds"],
                    "sourcePath": clip["sourcePath"],
                }
            )
            usage[path] = max(usage.get(path, 0.0), float(clip["sourceEndSeconds"]))
            cursor = float(clip["timelineEndSeconds"])
    return {
        "addedClipCount": len(added),
        "addedSeconds": round(sum(float(item["timelineEndSeconds"]) - float(item["timelineStartSeconds"]) for item in added), 2),
        "gapsFilled": added,
    }


def make_resolve_blueprint(
    project: dict[str, Any] | None,
    chapters: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    output_dir: Path,
    fps: float,
    target_seconds: float,
) -> dict[str, Any]:
    title = clean_text((project or {}).get("title"), "Travel Video")
    clips = []
    for section in sections:
        if section["chapterIndex"] in {0, 999}:
            continue
        chapter = next((ch for ch in chapters if ch["index"] == section["chapterIndex"]), None)
        if not chapter:
            continue
        chapter_start = section["startSeconds"]
        chapter_end = chapter_start + section["durationSeconds"]
        cursor = chapter_start
        for media in chapter.get("media", []):
            duration = pick_clip_duration(media)
            remaining = chapter_end - cursor
            if remaining < 2.0:
                break
            if duration > remaining:
                duration = remaining
            clip = make_blueprint_clip("main_footage", chapter, media, 0.0, duration, cursor, "route-grounded long-form footage")
            if not clip:
                continue
            clips.append(clip)
            cursor = float(clip["timelineEndSeconds"])
            if cursor >= chapter_end - 3:
                break
    initial_coverage = clip_coverage(clips)
    fill_summary = fill_long_form_gaps(clips, chapters, sections, target_seconds)
    clips = sorted(clips, key=lambda c: (float(c.get("timelineStartSeconds") or 0), int(c.get("trackIndex") or 1), str(c.get("role") or "")))
    coverage = clip_coverage(clips)
    return {
        "version": 1,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "projectName": f"{title} Resolve Longform",
        "timelineName": f"{title} 20min Master",
        "fps": fps,
        "resolution": {"width": 3840, "height": 2160},
        "targetDurationSeconds": round(target_seconds, 2),
        "actualVideoCoverageSeconds": round(coverage, 2),
        "coverageRatio": round(coverage / target_seconds, 4) if target_seconds else 0,
        "longFormCoverage": {
            "initialVideoCoverageSeconds": round(initial_coverage, 2),
            "coverageFillAddedSeconds": fill_summary.get("addedSeconds", 0.0),
            "coverageFillAddedClipCount": fill_summary.get("addedClipCount", 0),
            "finalVideoCoverageSeconds": round(coverage, 2),
            "targetDurationSeconds": round(target_seconds, 2),
        },
        "outputDir": str(output_dir),
        "tracks": [
            {"type": "video", "index": 1, "name": "V1 Main travel footage"},
            {"type": "video", "index": 2, "name": "V2 Titles maps aerial inserts"},
            {"type": "subtitle", "index": 1, "name": "S1 Chinese subtitles"},
            {"type": "audio", "index": 1, "name": "A1 Source audio"},
            {"type": "audio", "index": 2, "name": "A2 Voiceover"},
            {"type": "audio", "index": 3, "name": "A3 BGM"},
            {"type": "audio", "index": 4, "name": "A4 Ambience"},
        ],
        "clips": clips,
        "assets": {
            "voiceover": str(output_dir / "voiceover" / "voiceover.m4a"),
            "subtitles": str(output_dir / "subtitles.srt"),
            "bgm": [],
            "aerials": [],
        },
        "notes": [
            "This blueprint is a first assembly skeleton, not the final creative pass.",
            "Resolve write script creates a new project/timeline and imports only referenced source files.",
            "BGM, stock aerials, typography, subtitles, and titles require approved assets before final render.",
        ],
    }


def markdown_asset_plan(asset_queries: list[dict[str, Any]], typography: dict[str, Any]) -> str:
    lines = ["# Asset Search Plan", ""]
    for item in asset_queries:
        lines.append(f"## Chapter {item['chapterIndex']}: {item['place']}")
        lines.append("")
        lines.append("Aerial/establishing targets:")
        for target in item["aerialTargets"]:
            lines.append(f"- {target}")
        lines.append("")
        lines.append("Search queries:")
        for query in item["queries"]:
            lines.append(f"- {query}")
        lines.append(f"- License status: {item['licenseStatus']}")
        lines.append("")
    lines.append("## Typography")
    for key, fonts in typography.items():
        if isinstance(fonts, list):
            lines.append(f"- {key}: {', '.join(fonts)}")
    lines.append(f"- License status: {typography['licenseStatus']}")
    return "\n".join(lines) + "\n"


def markdown_bgm(cues: list[dict[str, Any]]) -> str:
    lines = ["# BGM Cues", ""]
    for cue in cues:
        lines.append(f"## Chapter {cue['chapterIndex']}: {cue['place']}")
        lines.append(f"- Mood: {cue['mood']}")
        lines.append("- Search queries:")
        for query in cue["queries"]:
            lines.append(f"  - {query}")
        lines.append(f"- License status: {cue['licenseStatus']}")
        lines.append("")
    return "\n".join(lines)


def markdown_long_form(sections: list[dict[str, Any]], target_minutes: float) -> str:
    lines = [
        "# Long-Form Structure",
        "",
        f"Target duration: {target_minutes:.1f} minutes",
        "Reference: local Malta final is about 39m54s, so this workflow must scale beyond short clips.",
        "",
        "This is a long-form travel film structure. It must breathe, carry geography, preserve observed details, and avoid short-video compression.",
        "",
        "## Sections",
    ]
    for section in sections:
        lines.append(
            f"- {section['place']}: start {srt_time(section['startSeconds']).replace(',', ':')}, "
            f"duration {section['durationSeconds']:.1f}s, role `{section['targetRole']}`"
        )
    lines.extend(
        [
            "",
            "## Style Guardrails",
            "- Treat Bilibili long travel vlogs as a reference for patience and chapter breathing, not as a copy target.",
            "- Use narration sparingly; let street sound, BGM, and visual continuity carry long sections.",
            "- Keep day-to-day transitions understandable with maps, transport, street inserts, or hotel/window details.",
            "- A 20-minute film needs story progression, callbacks, and downtime; do not cut it like a one-minute recap.",
        ]
    )
    return "\n".join(lines) + "\n"


def markdown_edit_plan(chapters: list[dict[str, Any]], transitions: list[dict[str, Any]], route_source: str) -> str:
    lines = ["# Edit Decision Plan", "", f"Route source: `{route_source}`", ""]
    lines.append("## Chapters")
    for chapter in chapters:
        flags = []
        if chapter["needsHumanReview"]:
            flags.append("needs review")
        if chapter["isTransit"]:
            flags.append("transit")
        if chapter["markedDoNotCut"]:
            flags.append("do not cut")
        flag_text = f" ({', '.join(flags)})" if flags else ""
        lines.append(f"- {chapter['index']:02d}. {chapter['place']}: {chapter['videoCount']} videos{flag_text}")
    lines.append("")
    lines.append("## Transitions")
    for item in transitions:
        lines.append(f"- After chapter {item['afterChapter']}: {item['bridge']} - {item['suggestion']}")
    lines.append("")
    lines.append("## Editor Handoff")
    lines.append("- Preferred: DaVinci Resolve Python API for the actual 20-minute timeline.")
    lines.append("- Use `check_resolve_api.py` before writing.")
    lines.append("- Use `build_resolve_timeline.py --blueprint resolve_timeline_blueprint.json --apply` only after approval.")
    lines.append("- FCPXML/EDL remains a backup; Computer Use remains a GUI-only fallback.")
    return "\n".join(lines) + "\n"


def davinci_notes() -> str:
    return """# DaVinci Build Notes

Preferred delivery route:

1. Open DaVinci Resolve Studio.
2. Confirm scripting access is enabled for Local scripts.
3. Run `check_resolve_api.py`.
4. Generate or review `resolve_timeline_blueprint.json`.
5. Run `prepare_delivery_assets.py --package-dir <package>` to generate title/place cards and refresh Resolve enrichment.
6. Add `--generate-local-voiceover` only after approving local macOS TTS for the draft narration.
7. Run `build_resolve_timeline.py --blueprint resolve_timeline_blueprint.json` for dry-run.
8. After approval, run the same command with `--apply`.

The script creates a new project and timeline. It does not modify existing timelines.

Manual/next automated passes still required for final polish:

- licensed BGM import and mix
- voiceover import and exact subtitle retiming
- title cards, map graphics, and typography
- aerial/stock inserts after license approval
- color correction and final render settings
"""


def qa_checklist() -> str:
    return """# QA Checklist

- [ ] Target is a long-form film, not a 1-2 minute short.
- [ ] Route matches the intended trip.
- [ ] No stale confirmed route is used.
- [ ] Voiceover script approved.
- [ ] Voiceover audio created and checked for clipping.
- [ ] Subtitles generated and retimed after final audio.
- [ ] BGM source URL, license, and attribution recorded.
- [ ] Aerial/stock source URL, license, and attribution recorded.
- [ ] Font license or system-font status recorded.
- [ ] Day/chapter transitions checked for flow.
- [ ] DaVinci API connection verified.
- [ ] Resolve timeline readback/audit completed.
- [ ] Black frames, shaky clips, and accidental private info reviewed.
- [ ] Final timeline export/render settings confirmed.
"""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_asset_ledger(output_dir: Path, delivery: dict[str, Any]) -> None:
    ledger_dir = output_dir / "asset_ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "sourceDeliveryPlan": str(output_dir / "delivery_plan.json"),
        "status": "draft",
        "items": bgm_items(delivery) + aerial_items(delivery) + font_items(delivery),
        "finalReady": False,
        "readyRule": "All BGM and aerial/stock rows must have selectedAssetUrl/localPath plus verified licenseStatus before final render.",
    }
    write_text(ledger_dir / "asset_license_ledger.json", json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    write_ledger_markdown(ledger_dir / "asset_license_ledger.md", ledger)
    packet = build_asset_sourcing_packet(output_dir, delivery, ledger, ledger_dir / "asset_license_ledger.json")
    write_asset_sourcing_packet_outputs(output_dir / "asset_sourcing", packet)


def build_package(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = discover_project(Path(args.project_dir), args.project_name)
    paths = artifact_paths(project_dir)
    project = load_json(paths["project"]) if paths["project"] else {}
    media_index = load_json(paths["mediaIndex"]) if paths["mediaIndex"] else {}
    media_index, excluded_media = apply_source_exclusions(project_dir, media_index if isinstance(media_index, dict) else None)
    pipeline = load_json(paths["pipeline"]) if paths["pipeline"] else {}
    route_source, route, warnings = choose_route(paths)
    chapters = route_chapters(route, media_index if isinstance(media_index, dict) else None)
    enrich_chapter_media(chapters, media_index if isinstance(media_index, dict) else None)
    target_seconds = args.target_duration_minutes * 60.0
    sections = allocate_chapter_durations(chapters, target_seconds)

    lines = narration_lines(project if isinstance(project, dict) else {}, chapters, args.target_duration_minutes)
    subtitles = make_srt(lines)
    asset_queries = build_asset_queries(chapters)
    bgm_cues = build_bgm_cues(chapters)
    typography = typography_plan(chapters)
    transitions = transition_plan(chapters)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "delivery_packages" / timestamp
    resolve_blueprint = make_resolve_blueprint(
        project if isinstance(project, dict) else {},
        chapters,
        sections,
        output_dir,
        args.fps,
        target_seconds,
    )
    status = "draft"
    if warnings or any(ch["needsHumanReview"] for ch in chapters):
        status = "blocked" if args.strict else "draft"
    if not chapters:
        status = "blocked"
    if resolve_blueprint["coverageRatio"] < 0.65:
        warnings.append(
            f"Resolve blueprint currently covers only {resolve_blueprint['actualVideoCoverageSeconds']:.1f}s "
            f"of {target_seconds:.1f}s target; more source selection, repeats, stock, or slower pacing is required."
        )
        if args.strict:
            status = "blocked"

    public_chapters = [{k: v for k, v in ch.items() if k != "media"} for ch in chapters]
    delivery = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "projectDir": str(project_dir),
        "outputDir": str(output_dir),
        "routeSource": route_source,
        "warnings": warnings,
        "sourceExclusions": {
            "excludedVideoCount": len(excluded_media),
            "excludedVideos": [{"fileId": item.get("fileId"), "name": item.get("name"), "path": item.get("path")} for item in excluded_media],
        },
        "target": {
            "durationMinutes": args.target_duration_minutes,
            "format": "long-form travel film, scalable to 20-40 minutes",
            "referenceStyle": "Bilibili long-form travel documentary/vlog pacing, not a short recap",
            "localReference": "/Users/pengyang/Downloads/马耳他终稿5.16.mp4 (~39m54s)",
            "fps": args.fps,
        },
        "pipeline": {
            "dryRun": pipeline.get("dryRun") if isinstance(pipeline, dict) else None,
            "allowCloudCall": pipeline.get("allowCloudCall") if isinstance(pipeline, dict) else None,
            "cloudProviderUsed": pipeline.get("cloudProviderUsed") if isinstance(pipeline, dict) else None,
            "localModelUsed": pipeline.get("localModelUsed") if isinstance(pipeline, dict) else None,
        },
        "chapters": public_chapters,
        "longFormSections": sections,
        "voiceover": {
            "scriptFile": str(output_dir / "voiceover_script.txt"),
            "lineCount": len(lines),
            "policy": "sparse narration for a 20-minute film; natural sound and music carry long stretches",
            "ttsNextStep": "python3 <skill-dir>/scripts/make_voiceover_audio.py --script voiceover_script.txt --output-dir voiceover",
        },
        "subtitles": {"srtFile": str(output_dir / "subtitles.srt"), "timing": "estimated"},
        "bgmCues": bgm_cues,
        "assetSearch": asset_queries,
        "typography": typography,
        "transitions": transitions,
        "editorHandoff": {
            "preferred": "DaVinci Resolve Python API",
            "resolveBlueprint": str(output_dir / "resolve_timeline_blueprint.json"),
            "blueprintCoverageRatio": resolve_blueprint["coverageRatio"],
            "dryRunCommand": "python3 <skill-dir>/scripts/build_resolve_timeline.py --blueprint resolve_timeline_blueprint.json",
            "applyCommand": "python3 <skill-dir>/scripts/build_resolve_timeline.py --blueprint resolve_timeline_blueprint.json --apply",
            "computerUse": "Fallback only for GUI-only flows.",
        },
        "requiredFiles": [
            "delivery_plan.json",
            "long_form_structure.md",
            "voiceover_script.txt",
            "subtitles.srt",
            "delivery_assets_report.json",
            "asset_search_plan.md",
            "asset_ledger/asset_license_ledger.json",
            "asset_sourcing/asset_sourcing_packet.json",
            "bgm_cues.md",
            "edit_decision_plan.md",
            "resolve_timeline_enrichment.json",
            "resolve_timeline_blueprint.json",
            "davinci_build_notes.md",
            "qa_checklist.md",
            "delivery_audit.json",
        ],
    }
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_text(output_dir / "voiceover_script.txt", "\n\n".join(lines) + "\n")
        write_text(output_dir / "subtitles.srt", subtitles)
        write_text(output_dir / "asset_search_plan.md", markdown_asset_plan(asset_queries, typography))
        write_text(output_dir / "bgm_cues.md", markdown_bgm(bgm_cues))
        write_text(output_dir / "long_form_structure.md", markdown_long_form(sections, args.target_duration_minutes))
        write_text(output_dir / "edit_decision_plan.md", markdown_edit_plan(chapters, transitions, route_source))
        write_text(output_dir / "davinci_build_notes.md", davinci_notes())
        write_text(output_dir / "qa_checklist.md", qa_checklist())
        write_text(output_dir / "delivery_plan.json", json.dumps(delivery, ensure_ascii=False, indent=2) + "\n")
        enrichment = build_enrichment(delivery, resolve_blueprint, output_dir)
        resolve_blueprint = apply_enrichment_to_blueprint(resolve_blueprint, enrichment)
        write_text(output_dir / "resolve_timeline_enrichment.json", json.dumps(enrichment, ensure_ascii=False, indent=2) + "\n")
        write_text(output_dir / "resolve_timeline_blueprint.json", json.dumps(resolve_blueprint, ensure_ascii=False, indent=2) + "\n")
        write_asset_ledger(output_dir, delivery)
    return delivery


def print_human(delivery: dict[str, Any], dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "WROTE"
    print(f"{mode} long-form travel video delivery package")
    print(f"Status: {delivery['status']}")
    print(f"Project: {delivery['projectDir']}")
    print(f"Output: {delivery['outputDir']}")
    print(f"Target: {delivery['target']['durationMinutes']} minutes")
    print(f"Route source: {delivery['routeSource']}")
    print(f"Chapters: {len(delivery['chapters'])}")
    if delivery["warnings"]:
        print("Warnings:")
        for warning in delivery["warnings"]:
            print(f"  - {warning}")
    print("Required files:")
    for name in delivery["requiredFiles"]:
        print(f"  - {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a long-form travel-video delivery package.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app root or project directory.")
    parser.add_argument("--project-name", help="Project folder name under app_root/projects.")
    parser.add_argument("--output-dir", help="Override output directory.")
    parser.add_argument("--target-duration-minutes", type=float, default=DEFAULT_TARGET_MINUTES)
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--strict", action="store_true", help="Mark package blocked when any chapter needs review.")
    parser.add_argument("--dry-run", action="store_true", help="Print package plan without writing files.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    delivery = build_package(args)
    if args.json:
        print(json.dumps(delivery, ensure_ascii=False, indent=2))
    else:
        print_human(delivery, args.dry_run)
    return 2 if delivery["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
