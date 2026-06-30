#!/usr/bin/env python3
"""Build a full-media route scaffold from ordered media and chapter/map filename cues."""

from __future__ import annotations

import argparse
import json
import math
import re
import textwrap
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import default_app_dir, discover_project_path


DEFAULT_APP_DIR = default_app_dir()


PLACE_HINTS = {
    "arrival": ("抵达关西", "Kansai Airport / Arrival", "大阪", "Japan", "arrival"),
    "osaka": ("大阪：塔、城和晚风", "Osaka", "大阪", "Japan", "main_chapter"),
    "tokyo": ("东京：城市展开", "Tokyo", "东京", "Japan", "main_chapter"),
    "asakusa": ("浅草：寺町和人流", "Asakusa / Senso-ji", "东京", "Japan", "main_chapter"),
    "akiba": ("秋叶原：街区和电光", "Akihabara", "东京", "Japan", "main_chapter"),
    "return": ("回程：把路收回来", "Return route", "东京", "Japan", "return"),
    "end": ("结尾", "Ending", "", "", "ending"),
}


MAP_HINTS = {
    "pvg_kix": ("上海浦东 -> 关西机场", "Shanghai Pudong to Kansai Airport", "大阪", "Japan"),
    "osaka_tokyo": ("大阪 -> 东京", "Osaka to Tokyo", "东京", "Japan"),
    "return": ("回程地图", "Return map", "", ""),
}


def load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def discover_project(path: Path, project_name: str | None) -> Path:
    return discover_project_path(path, project_name)


def media_files(media_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(media_index, dict):
        return []
    files = [f for f in media_index.get("files", []) if isinstance(f, dict) and f.get("kind") == "video" and f.get("path")]
    return sorted(files, key=media_sort_key)


def active_exclusions(project_dir: Path) -> tuple[set[str], set[str]]:
    payload = load_json(project_dir / "source_exclusions.json") or {}
    items = [item for item in payload.get("items") or [] if item.get("active", True)]
    return (
        {str(item.get("path")) for item in items if item.get("path")},
        {str(item.get("fileId")) for item in items if item.get("fileId")},
    )


def apply_exclusions(media: list[dict[str, Any]], project_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    excluded_paths, excluded_ids = active_exclusions(project_dir)
    kept = []
    excluded = []
    for item in media:
        if str(item.get("path")) in excluded_paths or str(item.get("fileId")) in excluded_ids:
            excluded.append(item)
        else:
            kept.append(item)
    return kept, excluded


def media_sort_key(media: dict[str, Any]) -> tuple[int, str]:
    name = str(media.get("name") or Path(str(media.get("path"))).name)
    match = re.match(r"^(\d+)", name)
    return (int(match.group(1)) if match else 999999, name)


def media_duration(media: dict[str, Any]) -> float:
    try:
        return float(media.get("duration") or media.get("probe", {}).get("format", {}).get("duration") or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def resolve_frame_index_path(project_dir: Path) -> Path | None:
    pointer = load_json(project_dir / "latest_frame_index.json")
    if isinstance(pointer, dict):
        for key in ("frameIndex", "path"):
            value = pointer.get(key)
            if value and Path(value).exists():
                return Path(value)
        files = pointer.get("files")
        if isinstance(files, dict):
            value = files.get("frameIndex")
            if value and Path(value).exists():
                return Path(value)
    return latest(sorted(project_dir.glob("analysis/light/*/frame_index.json")))


def normalize_video_key(value: str | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.suffix:
        return path.name
    return value


def frame_score(frame: dict[str, Any]) -> float:
    return (
        float(frame.get("clarity") or 0) * 1.2
        + float(frame.get("edgeDetail") or 0) * 3.0
        + float(frame.get("contrast") or 0) * 0.6
        + (20.0 if frame.get("isLocationCandidate") else 0.0)
        + (10.0 if frame.get("isOcrCandidate") else 0.0)
    )


def index_frames(frame_index: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not isinstance(frame_index, dict):
        return out
    for frame in frame_index.get("frames", []) or []:
        if not isinstance(frame, dict):
            continue
        for key in {normalize_video_key(frame.get("sourceVideo")), normalize_video_key(frame.get("videoId"))}:
            if key:
                out[key].append(frame)
    for frames in out.values():
        frames.sort(key=frame_score, reverse=True)
    return out


def best_frames(media: dict[str, Any], frames_by_video: dict[str, list[dict[str, Any]]], limit: int) -> list[str]:
    paths: list[str] = []
    for key in (media.get("path"), media.get("name"), media.get("fileId")):
        paths.extend(frame.get("path") for frame in frames_by_video.get(normalize_video_key(str(key)), [])[:limit] if frame.get("path"))
    seen = set()
    out = []
    for path in paths:
        if path and path not in seen and Path(path).exists():
            out.append(path)
            seen.add(path)
    return out[:limit]


def marker_for_media(media: dict[str, Any]) -> dict[str, Any] | None:
    name = str(media.get("name") or Path(str(media.get("path"))).name).lower()
    stem = Path(name).stem
    if "end" in stem:
        title, place, city, country, role = PLACE_HINTS["end"]
        return {"type": "end", "chapter": title, "place": place, "city": city, "country": country, "storyRole": role}
    if "map_" in stem:
        for key, (title, place, city, country) in MAP_HINTS.items():
            if key in stem:
                return {"type": "map", "chapter": title, "place": place, "city": city, "country": country, "storyRole": "transit"}
        return {"type": "map", "chapter": "路线地图", "place": "Transit map", "city": "", "country": "", "storyRole": "transit"}
    if "chapter_" in stem:
        for key, (title, place, city, country, role) in PLACE_HINTS.items():
            if key in stem:
                return {"type": "chapter", "chapter": title, "place": place, "city": city, "country": country, "storyRole": role}
        suffix = stem.split("chapter_", 1)[-1].replace("_", " ").strip()
        return {"type": "chapter", "chapter": suffix.title(), "place": suffix.title(), "city": "", "country": "", "storyRole": "main_chapter"}
    return None


def build_groups(media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def start_group(marker: dict[str, Any], item: dict[str, Any]) -> None:
        nonlocal current
        if current and current["media"]:
            groups.append(current)
        current = {
            "marker": marker,
            "media": [item],
            "source": "filename_marker",
        }

    for item in media:
        marker = marker_for_media(item)
        if marker:
            start_group(marker, item)
        else:
            if current is None:
                current = {
                    "marker": {
                        "type": "opening",
                        "chapter": "开场：日本旅程建立",
                        "place": "Japan opening",
                        "city": "",
                        "country": "Japan",
                        "storyRole": "opening",
                    },
                    "media": [],
                    "source": "sequence_before_first_marker",
                }
            current["media"].append(item)
    if current and current["media"]:
        groups.append(current)
    if len(groups) <= 1:
        date_groups = build_date_groups(media)
        if len(date_groups) > 1:
            return date_groups
    return groups


def media_day(media: dict[str, Any]) -> str:
    value = str(media.get("metadataTime") or media.get("created") or media.get("modified") or "")
    return value[:10] if value else "unknown-date"


def infer_place_from_media(items: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    text = " ".join(str(item.get("name") or "") + " " + str(item.get("folder") or "") for item in items).lower()
    if "osaka" in text or "大阪" in text:
        return "大阪", "Osaka", "大阪", "Japan"
    if "tokyo" in text or "东京" in text or "東京" in text:
        return "东京", "Tokyo", "东京", "Japan"
    if "hong" in text or "香港" in text:
        return "香港", "Hong Kong", "香港", ""
    if "macau" in text or "macao" in text or "澳门" in text:
        return "澳门", "Macau", "澳门", ""
    return "旅途", "Travel day", "", ""


def build_date_groups(media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in media:
        by_day[media_day(item)].append(item)
    groups = []
    for idx, day in enumerate(sorted(by_day), 1):
        items = by_day[day]
        place_cn, place_en, city, country = infer_place_from_media(items)
        groups.append(
            {
                "marker": {
                    "type": "date",
                    "chapter": f"Day {idx}: {day} {place_cn}",
                    "place": place_en,
                    "city": city,
                    "country": country,
                    "storyRole": "travel_day",
                },
                "media": items,
                "source": "metadata_date_grouping",
            }
        )
    return groups


def scaffold_chapters(groups: list[dict[str, Any]], frames_by_video: dict[str, list[dict[str, Any]]], frame_limit: int) -> list[dict[str, Any]]:
    chapters = []
    for idx, group in enumerate(groups, 1):
        media = group["media"]
        marker = group["marker"]
        frames: list[str] = []
        for item in media[:10]:
            frames.extend(best_frames(item, frames_by_video, frame_limit))
        chapters.append(
            {
                "chapterId": f"scaffold_{idx:03d}",
                "chapter": marker["chapter"],
                "place": marker["place"],
                "city": marker["city"],
                "country": marker["country"],
                "timeRange": time_range(media),
                "confidence": 0.55 if marker["type"] in {"chapter", "map", "end"} else 0.35,
                "confidenceLevel": "scaffold",
                "videos": [item.get("fileId") for item in media if item.get("fileId")],
                "videoPaths": [item.get("path") for item in media if item.get("path")],
                "videoNames": [item.get("name") for item in media if item.get("name")],
                "durationSeconds": round(sum(media_duration(item) for item in media), 2),
                "representativeFrames": list(dict.fromkeys(frames))[: frame_limit * 3],
                "evidence": [
                    {
                        "type": "filename_sequence_scaffold",
                        "source": group["source"],
                        "detail": f"chapter started from {marker['type']} cue in ordered media",
                    }
                ],
                "isTransit": marker["type"] == "map",
                "storyRole": marker["storyRole"],
                "uncertainties": ["needs human route review", "filename/order scaffold is not location recognition"],
                "needsHumanReview": True,
            }
        )
    return chapters


def time_range(media: list[dict[str, Any]]) -> str:
    values = [str(item.get("created") or item.get("modified") or "") for item in media if item.get("created") or item.get("modified")]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return f"{values[0]} - {values[-1]}"


def build_contact_sheet(chapters: list[dict[str, Any]], output_path: Path, max_images: int) -> str | None:
    frame_paths: list[tuple[str, str]] = []
    for chapter in chapters:
        for frame in chapter.get("representativeFrames", [])[:3]:
            frame_paths.append((frame, f"{chapter['chapter']} ({chapter['videoNames'][0] if chapter.get('videoNames') else ''})"))
    frame_paths = [(path, label) for path, label in frame_paths if Path(path).exists()][:max_images]
    if not frame_paths:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # noqa: BLE001
        return None
    thumb_w, thumb_h = 360, 220
    label_h = 54
    cols = min(4, max(1, len(frame_paths)))
    rows = math.ceil(len(frame_paths) / cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = load_label_font(ImageFont, 16)
    for idx, (path, label) in enumerate(frame_paths):
        col = idx % cols
        row = idx // cols
        x = col * thumb_w
        y = row * (thumb_h + label_h)
        try:
            image = Image.open(path).convert("RGB")
            image.thumbnail((thumb_w, thumb_h))
            bg = Image.new("RGB", (thumb_w, thumb_h), (20, 20, 20))
            bg.paste(image, ((thumb_w - image.width) // 2, (thumb_h - image.height) // 2))
            sheet.paste(bg, (x, y))
        except Exception:  # noqa: BLE001
            draw.rectangle((x, y, x + thumb_w, y + thumb_h), fill=(40, 40, 40))
        draw.text((x + 8, y + thumb_h + 8), "\n".join(textwrap.wrap(label, width=32)[:2]), fill=(0, 0, 0), font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92)
    return str(output_path)


def load_label_font(image_font: Any, size: int) -> Any:
    candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for path in candidates:
        try:
            if Path(path).exists():
                return image_font.truetype(path, size)
        except Exception:  # noqa: BLE001
            continue
    return image_font.load_default()


def write_markdown(path: Path, scaffold: dict[str, Any]) -> None:
    lines = [
        "# Route Coverage Scaffold",
        "",
        f"Status: `{scaffold['status']}`",
        f"Project directory: `{scaffold['projectDir']}`",
        f"Media videos: {scaffold['coverage']['mediaVideoCount']}",
        f"Covered videos: {scaffold['coverage']['coveredVideoCount']}",
        f"Coverage ratio: {scaffold['coverage']['coverageRatio']}",
        f"Contact sheet: `{scaffold.get('contactSheet') or 'not generated'}`",
        "",
        "## Warnings",
    ]
    lines.extend(f"- {item}" for item in scaffold["warnings"] or ["None"])
    lines.append("")
    lines.append("## Chapters")
    for chapter in scaffold["chapters"]:
        lines.append(
            f"- {chapter['chapterId']} `{chapter['chapter']}` -> {chapter['place']} "
            f"videos={len(chapter['videos'])} duration={chapter['durationSeconds']}s review={chapter['needsHumanReview']}"
        )
    lines.extend(
        [
            "",
            "## Usage",
            "",
            "This scaffold is not a confirmed route. Use it as a full-coverage review source, then confirm/correct chapters before final cutting.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_scaffold(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = discover_project(Path(args.project_dir), args.project_name)
    media_index = load_json(project_dir / "media_index.json") or {}
    frame_index_path = resolve_frame_index_path(project_dir)
    frame_index = load_json(frame_index_path) or {}
    media, excluded_media = apply_exclusions(media_files(media_index), project_dir)
    frames_by_video = index_frames(frame_index)
    groups = build_groups(media)
    chapters = scaffold_chapters(groups, frames_by_video, args.frames_per_chapter)
    covered = sum(len(ch.get("videos") or []) for ch in chapters)
    total = len(media)
    media_duration_total = float((media_index.get("summary") or {}).get("totalDuration") or sum(media_duration(item) for item in media))
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "projectDir": str(project_dir),
        "status": "review_needed",
        "mode": "route_coverage_scaffold",
        "source": {
            "mediaIndex": str(project_dir / "media_index.json"),
            "frameIndex": str(frame_index_path) if frame_index_path else None,
            "method": "ordered_media_plus_filename_chapter_markers",
        },
        "coverage": {
            "mediaVideoCount": total,
            "excludedVideoCount": len(excluded_media),
            "coveredVideoCount": covered,
            "coverageRatio": round(covered / total, 4) if total else 0,
            "mediaDurationSeconds": round(media_duration_total, 2),
            "coveredDurationSeconds": round(sum(ch.get("durationSeconds") or 0 for ch in chapters), 2),
        },
        "chapterCount": len(chapters),
        "chapters": chapters,
        "warnings": [
            "This is a route scaffold, not confirmed location recognition.",
            "All chapters require human review before confirmed_route_timeline.json can be written.",
        ]
        + ([f"{len(excluded_media)} source videos were excluded by source_exclusions.json."] if excluded_media else []),
        "excludedMedia": [{"fileId": item.get("fileId"), "name": item.get("name"), "path": item.get("path")} for item in excluded_media],
        "nextActions": [
            {
                "priority": "P0",
                "action": "Review scaffold chapters",
                "detail": "Open the scaffold markdown/contact sheet and correct chapter names, places, splits, and exclusions.",
            },
            {
                "priority": "P0",
                "action": "Generate route review from scaffold",
                "detail": "Use this scaffold as a full-coverage route source for route review, then prepare a confirmed route candidate.",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a full-media route coverage scaffold from ordered media.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app or project directory.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app root.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to <project>/route_scaffold/<timestamp>.")
    parser.add_argument("--frames-per-chapter", type=int, default=3)
    parser.add_argument("--max-contact-images", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = discover_project(Path(args.project_dir), args.project_name)
    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "route_scaffold" / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    scaffold = build_scaffold(args)
    contact_sheet = build_contact_sheet(scaffold["chapters"], out_dir / "contact_sheet.jpg", args.max_contact_images)
    scaffold["contactSheet"] = contact_sheet
    scaffold_path = out_dir / "route_coverage_scaffold.json"
    markdown_path = out_dir / "route_coverage_scaffold.md"
    scaffold["scaffoldJson"] = str(scaffold_path)
    scaffold["scaffoldMarkdown"] = str(markdown_path)
    write_json(scaffold_path, scaffold)
    write_markdown(markdown_path, scaffold)
    write_json(project_dir / "latest_route_coverage_scaffold.json", {"scaffold": str(scaffold_path), "createdAt": scaffold["createdAt"], "status": scaffold["status"]})
    if args.json:
        print(json.dumps(scaffold, ensure_ascii=False, indent=2))
    else:
        print(f"Route coverage scaffold status: {scaffold['status']}")
        print(f"Scaffold JSON: {scaffold_path}")
        print(f"Scaffold Markdown: {markdown_path}")
        if contact_sheet:
            print(f"Contact sheet: {contact_sheet}")
        print(f"Coverage: {scaffold['coverage']['coveredVideoCount']}/{scaffold['coverage']['mediaVideoCount']} ({scaffold['coverage']['coverageRatio']})")
        print(f"Chapters: {scaffold['chapterCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
