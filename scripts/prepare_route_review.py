#!/usr/bin/env python3
"""Create a route/location review packet for unordered travel footage."""

from __future__ import annotations

import argparse
import json
import math
import textwrap
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import default_app_dir, discover_project_path


DEFAULT_APP_DIR = default_app_dir()


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


def clean(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def artifact_paths(project_dir: Path) -> dict[str, Path | None]:
    return {
        "project": latest(list(project_dir.glob("project.json"))),
        "mediaIndex": latest(list(project_dir.glob("media_index.json"))),
        "videoLocationMap": latest(list(project_dir.glob("video_location_map.json"))),
        "routeTimeline": latest(list(project_dir.glob("route_timeline.json"))),
        "confirmedRoute": latest(list(project_dir.glob("confirmed_route_timeline.json"))),
        "pipeline": latest(list(project_dir.glob("latest_location_route_pipeline.json"))),
        "latestFrameIndex": latest(list(project_dir.glob("latest_frame_index.json"))),
    }


def resolve_frame_index_path(project_dir: Path, pointer_path: Path | None) -> Path | None:
    pointer = load_json(pointer_path)
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
    candidates = sorted(project_dir.glob("analysis/light/*/frame_index.json"))
    return latest(candidates)


def media_files(media_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(media_index, dict):
        return []
    return [f for f in media_index.get("files", []) if isinstance(f, dict) and f.get("kind") == "video" and f.get("path")]


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
    frames_by_video: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not isinstance(frame_index, dict):
        return frames_by_video
    for frame in frame_index.get("frames", []) or []:
        if not isinstance(frame, dict):
            continue
        keys = {
            normalize_video_key(frame.get("sourceVideo")),
            normalize_video_key(frame.get("videoId")),
        }
        for key in keys:
            if key:
                frames_by_video[key].append(frame)
    for frames in frames_by_video.values():
        frames.sort(key=frame_score, reverse=True)
    return frames_by_video


def video_location_map(vmap: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(vmap, dict):
        return out
    for video in vmap.get("videos", []) or []:
        if not isinstance(video, dict):
            continue
        for key in (video.get("videoId"), video.get("videoPath"), video.get("videoName")):
            normalized = normalize_video_key(clean(key))
            if normalized:
                out[normalized] = video
    return out


def project_regions(project: dict[str, Any] | None) -> set[str]:
    text = " ".join(
        [
            clean((project or {}).get("title")),
            clean((project or {}).get("routeText")),
        ]
    ).lower()
    regions = set()
    if any(token in text for token in ["香港", "hong kong", "维港", "維港"]):
        regions.add("hong-kong")
    if any(token in text for token in ["澳门", "澳門", "macau", "macao"]):
        regions.add("macau")
    if any(token in text for token in ["东京", "東京", "tokyo", "japan", "日本"]):
        regions.add("tokyo-japan")
    if any(token in text for token in ["大阪", "osaka"]):
        regions.add("osaka-japan")
    return regions


def inferred_regions_from_locations(locations: list[dict[str, Any]], media_roots: list[str]) -> set[str]:
    text = " ".join(
        [clean(item.get("bestPlace")) + " " + clean(item.get("city")) + " " + clean(item.get("country")) for item in locations]
        + media_roots
    ).lower()
    regions = set()
    if any(token in text for token in ["tokyo", "东京", "東京", "japan", "日本"]):
        regions.add("tokyo-japan")
    if any(token in text for token in ["osaka", "大阪"]):
        regions.add("osaka-japan")
    if any(token in text for token in ["hong kong", "香港", "维港", "維港"]):
        regions.add("hong-kong")
    if any(token in text for token in ["macau", "macao", "澳门", "澳門"]):
        regions.add("macau")
    return regions


def freshness(paths: dict[str, Path | None]) -> dict[str, Any]:
    route_path = paths.get("routeTimeline")
    confirmed_path = paths.get("confirmedRoute")
    video_map_path = paths.get("videoLocationMap")
    frame_pointer = paths.get("latestFrameIndex")
    stale: list[str] = []
    if confirmed_path and route_path and confirmed_path.stat().st_mtime < route_path.stat().st_mtime:
        stale.append("confirmed_route_timeline.json is older than route_timeline.json")
    if route_path and video_map_path and route_path.stat().st_mtime < video_map_path.stat().st_mtime:
        stale.append("route_timeline.json is older than video_location_map.json")
    if frame_pointer and video_map_path and video_map_path.stat().st_mtime < frame_pointer.stat().st_mtime:
        stale.append("video_location_map.json is older than latest_frame_index.json pointer")
    return {
        "stale": stale,
        "artifacts": {
            name: {
                "path": str(path) if path else None,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path else None,
            }
            for name, path in paths.items()
        },
    }


def media_duration(media: dict[str, Any]) -> float:
    try:
        return float(media.get("duration") or media.get("probe", {}).get("format", {}).get("duration") or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def best_frames_for_video(video: dict[str, Any], frames_by_video: dict[str, list[dict[str, Any]]], limit: int) -> list[str]:
    candidates: list[str] = []
    for key in (video.get("path"), video.get("name"), video.get("fileId"), video.get("videoPath"), video.get("videoName"), video.get("videoId")):
        candidates.extend(frame.get("path") for frame in frames_by_video.get(normalize_video_key(clean(key)), [])[:limit] if frame.get("path"))
    for path in video.get("representativeFrames", []) or []:
        candidates.append(path)
    seen = set()
    out = []
    for path in candidates:
        if path and path not in seen and Path(path).exists():
            out.append(path)
            seen.add(path)
    return out[:limit]


def chapter_review_rows(
    route: dict[str, Any] | None,
    media: list[dict[str, Any]],
    loc_by_key: dict[str, dict[str, Any]],
    frames_by_video: dict[str, list[dict[str, Any]]],
    frame_limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_file_id = {clean(item.get("fileId")): item for item in media}
    by_path = {clean(item.get("path")): item for item in media}
    assigned_paths: set[str] = set()
    rows: list[dict[str, Any]] = []
    chapters = route.get("chapters") if isinstance(route, dict) else []
    for idx, chapter in enumerate(chapters or [], 1):
        chapter_media: list[dict[str, Any]] = []
        for video_id in chapter.get("videos", []) or []:
            item = by_file_id.get(clean(video_id))
            if item:
                chapter_media.append(item)
        for path in chapter.get("videoPaths", []) or []:
            item = by_path.get(clean(path))
            if item and item not in chapter_media:
                chapter_media.append(item)
        frames: list[str] = []
        location_samples = []
        for item in chapter_media:
            assigned_paths.add(clean(item.get("path")))
        for item in chapter_media[:12]:
            frames.extend(best_frames_for_video(item, frames_by_video, frame_limit))
            loc = loc_by_key.get(normalize_video_key(item.get("path"))) or loc_by_key.get(normalize_video_key(item.get("name"))) or loc_by_key.get(normalize_video_key(item.get("fileId")))
            if loc:
                location_samples.append(
                    {
                        "video": item.get("name") or Path(clean(item.get("path"))).name,
                        "bestPlace": loc.get("bestPlace"),
                        "city": loc.get("city"),
                        "confidence": loc.get("confidence"),
                        "needsHumanReview": loc.get("needsHumanReview"),
                    }
                )
        rows.append(
            {
                "index": idx,
                "chapterId": chapter.get("chapterId") or f"ch_{idx:03d}",
                "chapter": chapter.get("chapter") or chapter.get("place") or f"Chapter {idx}",
                "place": chapter.get("place") or chapter.get("chapter") or "unknown",
                "city": chapter.get("city") or "",
                "country": chapter.get("country") or "",
                "confidence": chapter.get("confidence"),
                "confidenceLevel": chapter.get("confidenceLevel") or "",
                "needsHumanReview": bool(chapter.get("needsHumanReview")),
                "isTransit": bool(chapter.get("isTransit")),
                "videoCount": len(chapter_media) or len(chapter.get("videos", []) or []),
                "videos": [item.get("fileId") for item in chapter_media if item.get("fileId")],
                "videoPaths": [item.get("path") for item in chapter_media if item.get("path")],
                "videoNames": [item.get("name") or Path(clean(item.get("path"))).name for item in chapter_media],
                "durationSeconds": round(sum(media_duration(item) for item in chapter_media), 2),
                "frames": list(dict.fromkeys(frames))[: frame_limit * 3],
                "evidence": chapter.get("evidence", []) or [],
                "uncertainties": chapter.get("uncertainties", []) or [],
                "locationSamples": location_samples,
                "reviewDecision": "pending",
                "suggestedAction": "confirm_or_correct_place",
            }
        )
    uncovered = [item for item in media if clean(item.get("path")) not in assigned_paths]
    uncovered_rows = []
    for item in uncovered:
        key = normalize_video_key(item.get("path"))
        loc = loc_by_key.get(key) or loc_by_key.get(normalize_video_key(item.get("name"))) or loc_by_key.get(normalize_video_key(item.get("fileId")))
        uncovered_rows.append(
            {
                "fileId": item.get("fileId"),
                "name": item.get("name") or Path(clean(item.get("path"))).name,
                "path": item.get("path"),
                "durationSeconds": media_duration(item),
                "mediaType": item.get("mediaType"),
                "bestPlace": (loc or {}).get("bestPlace"),
                "city": (loc or {}).get("city"),
                "confidence": (loc or {}).get("confidence"),
                "needsHumanReview": (loc or {}).get("needsHumanReview", True),
                "frames": best_frames_for_video(item, frames_by_video, frame_limit),
            }
        )
    return rows, uncovered_rows


def representative_location_counts(vmap: dict[str, Any] | None) -> dict[str, Any]:
    videos = vmap.get("videos", []) if isinstance(vmap, dict) else []
    places = Counter(clean(v.get("bestPlace"), "unknown") for v in videos if isinstance(v, dict))
    cities = Counter(clean(v.get("city"), "unknown") for v in videos if isinstance(v, dict))
    return {
        "videoCount": len(videos),
        "needsHumanReviewCount": sum(1 for v in videos if isinstance(v, dict) and v.get("needsHumanReview")),
        "places": places.most_common(20),
        "cities": cities.most_common(20),
    }


def build_contact_sheet(rows: list[dict[str, Any]], uncovered: list[dict[str, Any]], output_path: Path, max_images: int) -> str | None:
    frame_paths: list[tuple[str, str]] = []
    for row in rows:
        for frame in row.get("frames", [])[:4]:
            frame_paths.append((frame, f"{row['index']}. {row['place']}"))
    for row in uncovered[: max(0, max_images - len(frame_paths))]:
        for frame in row.get("frames", [])[:1]:
            frame_paths.append((frame, f"uncovered: {row['name']}"))
    frame_paths = [(path, label) for path, label in frame_paths if Path(path).exists()][:max_images]
    if not frame_paths:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:  # noqa: BLE001
        return None

    thumb_w, thumb_h = 360, 220
    label_h = 52
    cols = min(4, max(1, len(frame_paths)))
    rows_count = math.ceil(len(frame_paths) / cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows_count * (thumb_h + label_h)), "white")
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
            bg = Image.new("RGB", (thumb_w, thumb_h), (18, 18, 18))
            bg.paste(image, ((thumb_w - image.width) // 2, (thumb_h - image.height) // 2))
            sheet.paste(bg, (x, y))
        except Exception:  # noqa: BLE001
            draw.rectangle((x, y, x + thumb_w, y + thumb_h), fill=(40, 40, 40))
        wrapped = textwrap.wrap(label, width=32)[:2]
        draw.text((x + 8, y + thumb_h + 8), "\n".join(wrapped), fill=(0, 0, 0), font=font)
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


def write_markdown(path: Path, review: dict[str, Any]) -> None:
    lines = [
        "# Route Review Packet",
        "",
        f"Project: `{review['project']['title']}`",
        f"Project directory: `{review['projectDir']}`",
        f"Media roots: `{', '.join(review['project'].get('mediaRoots') or [])}`",
        f"Status: `{review['status']}`",
        f"Contact sheet: `{review.get('contactSheet') or 'not generated'}`",
        "",
        "## Summary",
        f"- Media videos: {review['coverage']['mediaVideoCount']}",
        f"- Location-map videos: {review['locationSummary']['videoCount']}",
        f"- Route chapters: {review['route']['chapterCount']}",
        f"- Uncovered media videos: {review['coverage']['uncoveredVideoCount']}",
        f"- Stale artifacts: {len(review['freshness']['stale'])}",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in review["blockers"] or ["None"])
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {item}" for item in review["warnings"] or ["None"])
    lines.append("")
    lines.append("## Route Chapters")
    for row in review["chapters"]:
        lines.extend(
            [
                "",
                f"### {row['index']}. {row['place']}",
                f"- City/country: {row['city']} / {row['country']}",
                f"- Confidence: {row['confidence']} `{row['confidenceLevel']}`",
                f"- Videos: {row['videoCount']}, duration: {row['durationSeconds']}s",
                f"- Needs review: `{row['needsHumanReview']}`",
                f"- Suggested action: `{row['suggestedAction']}`",
            ]
        )
        for sample in row.get("locationSamples", [])[:6]:
            lines.append(
                f"- Sample: `{sample['video']}` -> {sample.get('bestPlace')} / {sample.get('city')} "
                f"(confidence {sample.get('confidence')}, review {sample.get('needsHumanReview')})"
            )
        for frame in row.get("frames", [])[:3]:
            lines.append(f"![{row['place']}]({frame})")
    if review["uncoveredVideos"]:
        lines.extend(["", "## Uncovered Media"])
        for item in review["uncoveredVideos"][:40]:
            lines.append(
                f"- `{item['name']}` {item['durationSeconds']}s -> {item.get('bestPlace') or 'unknown'} "
                f"(confidence {item.get('confidence')})"
            )
    lines.extend(
        [
            "",
            "## Decision Template",
            "",
            "For each chapter, set `reviewDecision` to one of: `confirmed`, `corrected`, `split`, `merge`, `exclude`, `rerun_recognition`.",
            "Do not rename this packet to `confirmed_route_timeline.json`; use it to make a clean confirmed route only after review.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_review(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = discover_project(Path(args.project_dir), args.project_name)
    paths = artifact_paths(project_dir)
    project = load_json(paths["project"]) or {}
    media_index = load_json(paths["mediaIndex"]) or {}
    vmap = load_json(paths["videoLocationMap"]) or {}
    route_source_path = Path(args.route_source).expanduser().resolve() if args.route_source else paths["routeTimeline"]
    route = load_json(route_source_path) or {}
    route_source_kind = route.get("mode") or ("route_timeline" if route_source_path else "none")
    confirmed = load_json(paths["confirmedRoute"])
    pipeline = load_json(paths["pipeline"]) or {}
    frame_index_path = resolve_frame_index_path(project_dir, paths["latestFrameIndex"])
    frame_index = load_json(frame_index_path) or {}
    media, excluded_media = apply_exclusions(media_files(media_index), project_dir)
    frames_by_video = index_frames(frame_index)
    loc_by_key = video_location_map(vmap)
    chapters, uncovered = chapter_review_rows(route, media, loc_by_key, frames_by_video, args.frames_per_item)
    project_region_set = project_regions(project)
    inferred_region_set = inferred_regions_from_locations(vmap.get("videos", []) if isinstance(vmap, dict) else [], project.get("mediaRoots", []) or [])
    freshness_report = freshness(paths)
    if route_source_kind == "route_coverage_scaffold":
        freshness_report["stale"] = [
            item for item in freshness_report["stale"] if item != "video_location_map.json is older than latest_frame_index.json pointer"
        ]
    blockers: list[str] = []
    warnings: list[str] = []
    if freshness_report["stale"]:
        blockers.extend(freshness_report["stale"])
    if project_region_set and inferred_region_set and project_region_set.isdisjoint(inferred_region_set):
        blockers.append(
            "Project title/route region does not match inferred media/location region: "
            f"{sorted(project_region_set)} vs {sorted(inferred_region_set)}"
        )
    if any(row["needsHumanReview"] for row in chapters):
        blockers.append("At least one automatic route chapter still needs human review.")
    if len(uncovered) > 0:
        warnings.append(f"{len(uncovered)} media videos are not assigned to a route chapter.")
    if isinstance(confirmed, dict) and paths["confirmedRoute"] and paths["routeTimeline"] and paths["confirmedRoute"].stat().st_mtime < paths["routeTimeline"].stat().st_mtime:
        warnings.append("Existing confirmed_route_timeline.json is stale and should not drive final cutting.")
    if pipeline.get("allowCloudCall") is False:
        warnings.append("Pipeline did not allow cloud calls in the latest run; route evidence may be local-only or incomplete.")
    media_total = float(sum(media_duration(item) for item in media))
    assigned_total = sum(row["durationSeconds"] for row in chapters)
    review = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "projectDir": str(project_dir),
        "status": "blocked" if blockers else ("review_needed" if warnings else "ready_for_confirmed_route"),
        "project": {
            "title": project.get("title") or project_dir.name,
            "routeText": project.get("routeText"),
            "targetMinutes": project.get("targetMinutes"),
            "mediaRoots": project.get("mediaRoots", []),
            "declaredRegions": sorted(project_region_set),
            "inferredRegions": sorted(inferred_region_set),
        },
        "freshness": freshness_report,
        "pipeline": {
            "createdAt": pipeline.get("createdAt"),
            "dryRun": pipeline.get("dryRun"),
            "allowCloudCall": pipeline.get("allowCloudCall"),
            "cloudProviderUsed": pipeline.get("cloudProviderUsed"),
            "localModelUsed": pipeline.get("localModelUsed"),
            "summary": pipeline.get("summary"),
        },
        "route": {
            "sourcePath": str(route_source_path) if route_source_path else None,
            "sourceKind": route_source_kind,
            "confirmedRoutePath": str(paths["confirmedRoute"]) if paths["confirmedRoute"] else None,
            "chapterCount": len(chapters),
            "needsHumanReviewCount": sum(1 for row in chapters if row["needsHumanReview"]),
        },
        "locationSummary": representative_location_counts(vmap),
        "coverage": {
            "mediaVideoCount": len(media),
            "excludedVideoCount": len(excluded_media),
            "mediaDurationSeconds": round(media_total, 2),
            "assignedDurationSeconds": round(assigned_total, 2),
            "coverageRatio": round(assigned_total / media_total, 4) if media_total else 0,
            "uncoveredVideoCount": len(uncovered),
        },
        "frameIndex": {
            "path": str(frame_index_path) if frame_index_path else None,
            "frameCount": frame_index.get("frameCount") or len(frame_index.get("frames", []) or []),
        },
        "chapters": chapters,
        "uncoveredVideos": uncovered[: args.max_uncovered],
        "excludedMedia": [{"fileId": item.get("fileId"), "name": item.get("name"), "path": item.get("path")} for item in excluded_media],
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "nextActions": [
            {
                "priority": "P0",
                "action": "Resolve project/media region mismatch",
                "detail": "Either rename/update project route metadata to the inferred region or rerun recognition against the intended Hong Kong/Macau footage.",
            }
            if project_region_set and inferred_region_set and project_region_set.isdisjoint(inferred_region_set)
            else {
                "priority": "P0",
                "action": "Review route chapters",
                "detail": "Open route_review.md/contact_sheet.jpg and set each pending chapter to confirmed/corrected/split/merge/exclude/rerun_recognition.",
            },
            {
                "priority": "P1",
                "action": "Rebuild delivery package after route confirmation",
                "detail": "Only create or update confirmed_route_timeline.json after the review packet is resolved.",
            },
        ],
    }
    return review


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a route review packet from VideoClaw route/location artifacts.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app or project directory.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app root.")
    parser.add_argument("--route-source", help="Optional route_timeline.json or route_coverage_scaffold.json source.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to <project>/route_review/<timestamp>.")
    parser.add_argument("--frames-per-item", type=int, default=3)
    parser.add_argument("--max-contact-images", type=int, default=32)
    parser.add_argument("--max-uncovered", type=int, default=80)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = discover_project(Path(args.project_dir), args.project_name)
    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "route_review" / datetime.now().strftime("%Y%m%d_%H%M%S")
    review = build_review(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    review_path = out_dir / "route_review.json"
    markdown_path = out_dir / "route_review.md"
    contact_sheet = build_contact_sheet(review["chapters"], review["uncoveredVideos"], out_dir / "contact_sheet.jpg", args.max_contact_images)
    review["contactSheet"] = contact_sheet
    review["reviewJson"] = str(review_path)
    review["reviewMarkdown"] = str(markdown_path)
    write_json(review_path, review)
    write_markdown(markdown_path, review)
    write_json(project_dir / "latest_route_review.json", {"routeReview": str(review_path), "createdAt": review["createdAt"], "status": review["status"]})
    if args.json:
        print(json.dumps(review, ensure_ascii=False, indent=2))
    else:
        print(f"Route review status: {review['status']}")
        print(f"Review JSON: {review_path}")
        print(f"Review Markdown: {markdown_path}")
        if contact_sheet:
            print(f"Contact sheet: {contact_sheet}")
        for blocker in review["blockers"]:
            print(f"BLOCKER: {blocker}")
        for warning in review["warnings"]:
            print(f"WARNING: {warning}")
    return 2 if review["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
