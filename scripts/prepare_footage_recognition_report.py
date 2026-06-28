#!/usr/bin/env python3
"""Write a client-facing footage recognition and route-readiness report."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def first_video_stream(row: dict[str, Any]) -> dict[str, Any]:
    streams = ((row.get("probe") or {}).get("streams") or []) if isinstance(row.get("probe"), dict) else []
    for stream in streams:
        if stream.get("codec_type") == "video" and stream.get("codec_name") != "mjpeg":
            return stream
    for stream in streams:
        if stream.get("codec_type") == "video":
            return stream
    return {}


def frame_rate_value(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def media_date(row: dict[str, Any]) -> str:
    name = str(row.get("name") or "")
    match = re.search(r"(20\d{6})", name)
    if match:
        value = match.group(1)
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    value = row.get("metadataTime") or row.get("created") or row.get("modified") or ""
    return str(value)[:10] if value else "unknown"


def display_orientation(row: dict[str, Any]) -> dict[str, Any]:
    stream = first_video_stream(row)
    width = int(row.get("width") or stream.get("width") or 0)
    height = int(row.get("height") or stream.get("height") or 0)
    tags = stream.get("tags") or {}
    side_data = stream.get("side_data_list") or []
    rotate = tags.get("rotate")
    if rotate is None:
        for item in side_data:
            if "rotation" in item:
                rotate = item.get("rotation")
                break
    try:
        rotation = int(float(rotate or 0)) % 360
    except ValueError:
        rotation = 0
    display_width, display_height = width, height
    if rotation in {90, 270}:
        display_width, display_height = height, width
    if not display_width or not display_height:
        kind = "unknown"
    elif abs(display_width - display_height) <= 8:
        kind = "square"
    elif display_width > display_height:
        kind = "landscape"
    else:
        kind = "vertical"
    return {
        "width": width,
        "height": height,
        "displayWidth": display_width,
        "displayHeight": display_height,
        "rotation": rotation,
        "orientation": kind,
    }


def confidence_token(value: Any) -> str:
    text = str(value or "unknown").strip().lower().replace("-", "_")
    if text.startswith("high"):
        return "high"
    if text.startswith("medium_high"):
        return "medium_high"
    if text.startswith("medium"):
        return "medium"
    if text.startswith("low"):
        return "low"
    return "unknown"


def location_by_video(media: dict[str, Any], location_map: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id = {row.get("videoId"): row for row in (location_map.get("videos") or []) if row.get("videoId")}
    by_path = {str(row.get("videoPath")): row for row in (location_map.get("videos") or []) if row.get("videoPath")}
    result_by_id: dict[str, dict[str, Any]] = {}
    result_by_path: dict[str, dict[str, Any]] = {}
    for row in media.get("files") or []:
        if row.get("kind") != "video":
            continue
        loc = by_id.get(row.get("fileId")) or by_path.get(str(row.get("path")))
        if loc:
            result_by_id[str(row.get("fileId"))] = loc
            result_by_path[str(row.get("path"))] = loc
    return result_by_id, result_by_path


def summarize_route(route: dict[str, Any] | None) -> dict[str, Any]:
    route = route or {}
    chapters = route.get("chapters") or []
    confidence_counts = Counter(str(chapter.get("confidenceLevel") or "unknown") for chapter in chapters)
    broad_scaffold = False
    if len(chapters) == 1:
        chapter = chapters[0]
        text = " ".join(str(chapter.get(key) or "") for key in ("chapter", "place", "city", "confidenceLevel"))
        broad_scaffold = "全路线" in text or "scaffold" in text.lower()
    return {
        "chapterCount": int(route.get("chapterCount") or len(chapters)),
        "needsHumanReviewCount": int(route.get("needsHumanReviewCount") or 0),
        "confidenceCounts": dict(confidence_counts),
        "broadScaffoldOnly": broad_scaffold,
        "chapters": chapters,
    }


def load_frame_index(project_dir: Path) -> dict[str, Any]:
    latest = load_json(project_dir / "latest_frame_index.json") or {}
    frame_path = ((latest.get("files") or {}).get("frameIndex") if isinstance(latest.get("files"), dict) else None) or latest.get("frameIndex")
    if frame_path:
        return load_json(Path(frame_path).expanduser()) or latest
    return latest


def active_exclusions(project_dir: Path) -> tuple[set[str], set[str], list[dict[str, Any]]]:
    payload = load_json(project_dir / "source_exclusions.json") or {}
    items = [item for item in payload.get("items") or [] if item.get("active", True)]
    paths = {str(item.get("path")) for item in items if item.get("path")}
    ids = {str(item.get("fileId")) for item in items if item.get("fileId")}
    return paths, ids, items


def latest_pointer_report(project_dir: Path, pointer_name: str, report_key: str = "report") -> dict[str, Any]:
    pointer = load_json(project_dir / pointer_name) or {}
    report_path = pointer.get(report_key)
    if report_path:
        return load_json(Path(report_path).expanduser()) or {}
    return {}


def latest_codex_visual_report(project_dir: Path) -> dict[str, Any]:
    for pointer_name in ("latest_codex_visual_route_review.json", "latest_codex_visual_review.json"):
        pointer = load_json(project_dir / pointer_name) or {}
        for key in ("path", "report", "json"):
            if pointer.get(key):
                report = load_json(Path(str(pointer[key])).expanduser())
                if report:
                    return report
    candidates = sorted(project_dir.glob("codex_visual_review/*/codex_visual_review.json"))
    if candidates:
        return load_json(candidates[-1]) or {}
    return {}


def build_report(project_dir: Path, output_dir: Path) -> dict[str, Any]:
    media = load_json(project_dir / "media_index.json") or {}
    frame_index = load_frame_index(project_dir)
    location_map = load_json(project_dir / "video_location_map.json") or {}
    location_recognition = load_json(project_dir / "latest_location_recognition.json") or {}
    pipeline = load_json(project_dir / "latest_location_route_pipeline.json") or {}
    route_timeline = load_json(project_dir / "route_timeline.json") or {}
    confirmed_route = load_json(project_dir / "confirmed_route_timeline.json") or {}
    route_review_pointer = load_json(project_dir / "latest_route_review.json") or {}
    route_review = load_json(Path(route_review_pointer.get("routeReview") or "")) if route_review_pointer.get("routeReview") else None
    local_ocr = latest_pointer_report(project_dir, "latest_local_tesseract_ocr_recognition.json")
    local_vision = latest_pointer_report(project_dir, "latest_local_ollama_vision_recognition.json")
    codex_visual = latest_codex_visual_report(project_dir)
    codex_route = codex_visual.get("codexVisualRoute") or {}
    codex_days_by_date = {str(day.get("date")): day for day in codex_route.get("days") or [] if day.get("date")}
    excluded_paths, excluded_ids, exclusion_items = active_exclusions(project_dir)

    files = [row for row in media.get("files") or [] if row.get("kind") == "video"]
    loc_by_id, loc_by_path = location_by_video(media, location_map)
    rows: list[dict[str, Any]] = []
    orientation_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    day_counts: dict[str, Counter[str]] = defaultdict(Counter)
    uncovered: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []
    derived_sources: list[dict[str, Any]] = []
    excluded_derived_sources: list[dict[str, Any]] = []

    for item in sorted(files, key=lambda row: (media_date(row), str(row.get("name") or ""))):
        loc = loc_by_id.get(str(item.get("fileId"))) or loc_by_path.get(str(item.get("path"))) or {}
        is_excluded = str(item.get("path")) in excluded_paths or str(item.get("fileId")) in excluded_ids
        orient = display_orientation(item)
        if not is_excluded:
            orientation_counts[orient["orientation"]] += 1
        confidence = str(loc.get("confidenceLevel") or ("missing" if not loc else "unknown"))
        day = media_date(item)
        codex_day = codex_days_by_date.get(day) or {}
        display_place = codex_day.get("chapterTitle") or loc.get("bestPlace") or loc.get("place") or "unrecognized"
        display_city = codex_day.get("city") or loc.get("city") or ""
        display_confidence = (
            f"codex_visual_{confidence_token(codex_day.get('confidence'))}"
            if codex_day.get("confidence")
            else confidence
        )
        display_confidence_value = None if codex_day else loc.get("confidence")
        if is_excluded:
            display_place = "EXCLUDED prior rendered export"
            display_city = ""
            display_confidence = "excluded"
            display_confidence_value = None
        confidence_counts[display_confidence] += 1
        day_counts[day][display_place] += 1
        if not loc and not codex_day and not is_excluded:
            uncovered.append({"fileId": item.get("fileId"), "name": item.get("name"), "path": item.get("path")})
        row_needs_review = not codex_day and (bool(loc.get("needsHumanReview")) or confidence in {"missing", "low", "unknown"})
        if not is_excluded and row_needs_review:
            needs_review.append(
                {
                    "fileId": item.get("fileId"),
                    "name": item.get("name"),
                    "place": display_place,
                    "confidenceLevel": display_confidence,
                    "confidence": display_confidence_value,
                }
            )
        name = str(item.get("name") or "").lower()
        if any(token in name for token in ("vlog", "render", "master", "highbitrate", "final", "成片", "终稿")):
            row = {"fileId": item.get("fileId"), "name": item.get("name"), "path": item.get("path")}
            if str(item.get("path")) in excluded_paths or str(item.get("fileId")) in excluded_ids:
                excluded_derived_sources.append(row)
            else:
                derived_sources.append(row)
        rows.append(
            {
                "fileId": item.get("fileId"),
                "date": day,
                "name": item.get("name"),
                "durationSeconds": round(float(item.get("duration") or 0), 3),
                "fps": item.get("fps") or (first_video_stream(item).get("avg_frame_rate")),
                "orientation": orient,
                "mediaType": item.get("mediaType"),
                "hasGPS": bool(item.get("hasGPS")),
                "place": display_place,
                "city": display_city,
                "confidence": display_confidence_value,
                "confidenceLevel": display_confidence,
                "needsHumanReview": not is_excluded and row_needs_review,
                "representativeFrames": loc.get("representativeFrames") or [],
                "excludedFromCut": is_excluded,
                "path": item.get("path"),
            }
        )

    total_media_count = int((media.get("summary") or {}).get("videoCount") or len(files))
    media_count = max(0, total_media_count - len(exclusion_items))
    recognized_count = sum(1 for row in rows if not row.get("excludedFromCut") and row.get("place") != "unrecognized")
    frame_count = int(frame_index.get("frameCount") or len(frame_index.get("frames") or []))
    confirmed_summary = summarize_route(confirmed_route)
    route_summary = summarize_route(route_timeline)
    codex_source_count = int(codex_route.get("sourceVideoCoverage") or codex_visual.get("sourceVideoCount") or 0)
    codex_visual_ready = (
        bool(codex_visual)
        and codex_visual.get("status") in {"ready", "ready_with_warnings", "ready_with_caveats"}
        and codex_source_count >= media_count > 0
        and codex_route.get("provider") == "codex_visual_inspection"
        and codex_route.get("localModelUsed") is False
    )
    codex_visual_counts = {str(day.get("date")): int(day.get("videoCount") or 0) for day in codex_visual.get("days", []) if day.get("date")}
    codex_day_summary = {
        date: {str(day.get("chapterTitle") or day.get("routeNode") or "codex_visual_day"): codex_visual_counts.get(date, 0)}
        for date, day in codex_days_by_date.items()
    }

    blockers: list[str] = []
    warnings: list[str] = []
    if not media:
        blockers.append("media_index.json is missing; source footage has not been scanned.")
    if recognized_count < media_count and not codex_visual_ready:
        blockers.append(f"Only {recognized_count}/{media_count} videos have location rows; full-folder recognition is incomplete.")
    elif recognized_count < media_count and codex_visual_ready:
        warnings.append(
            "video_location_map rows are incomplete or stale, but the latest Codex visual review covers "
            f"{codex_source_count}/{media_count} active source videos."
        )
    recognition_summary = location_recognition.get("summary") or {}
    recognition_errors = recognition_summary.get("errors") or []
    cloud_frames_sent = int(recognition_summary.get("cloudFramesSent") or 0)
    if codex_visual_ready:
        warnings.append("Cloud vision was not required for the latest pass; Codex visual inspection is the primary recognition provider.")
    elif location_recognition.get("dryRun") is True or pipeline.get("allowCloudCall") is False:
        blockers.append("Cloud vision recognition did not actually run for this latest pass; route/location rows are not Mimo-verified.")
    elif recognition_errors or cloud_frames_sent <= 0:
        blockers.append(
            "Cloud vision recognition was requested but did not send frames successfully; "
            f"errors={recognition_errors or 'none'} cloudFramesSent={cloud_frames_sent}."
        )
    if frame_count and frame_count < media_count:
        warnings.append(f"Frame index has {frame_count} frames for {media_count} videos; this may be too sparse for reliable location recognition.")
    if confirmed_summary["chapterCount"] < 2 or confirmed_summary["broadScaffoldOnly"]:
        if codex_visual_ready:
            warnings.append("confirmed_route_timeline.json is still broad/stale; use the Codex visual route as the candidate route before final render.")
        else:
            blockers.append("confirmed_route_timeline.json is still a broad scaffold instead of day/place chapters.")
    if confirmed_summary["needsHumanReviewCount"] > 0 or (route_review or {}).get("blockers"):
        if codex_visual_ready:
            warnings.append("Route review still needs decisions, but Codex visual evidence is ready for an automatic route candidate.")
        else:
            blockers.append("Route review still needs human decisions before a client-deliverable route-aware cut.")
    if orientation_counts.get("vertical") or orientation_counts.get("unknown") or orientation_counts.get("square"):
        warnings.append(f"Non-landscape or unknown-orientation media found: {dict(orientation_counts)}.")
    if derived_sources:
        blockers.append("Rendered/derived video files appear in the source set; final editing should use original clips, not prior exports.")

    status = "blocked" if blockers else ("ready_with_caveats" if codex_visual_ready and warnings else ("ready_with_warnings" if warnings or needs_review else "ready"))
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "projectDir": str(project_dir),
        "outputDir": str(output_dir),
        "summary": {
            "mediaVideoCount": media_count,
            "totalIndexedVideoCount": total_media_count,
            "recognizedVideoCount": recognized_count,
            "recognitionCoverageRatio": round(recognized_count / media_count, 4) if media_count else 0,
            "codexVisualProviderUsed": codex_route.get("provider"),
            "codexVisualStatus": codex_visual.get("status"),
            "codexVisualSourceCoverage": codex_source_count,
            "primaryRecognitionProvider": "codex_visual_inspection" if codex_visual_ready else (recognition_summary.get("cloudProviderUsed") or location_recognition.get("cloudProviderModel")),
            "frameCount": frame_count,
            "locationMapVideoCount": int(location_map.get("videoCount") or len(location_map.get("videos") or [])),
            "confidenceCounts": dict(confidence_counts),
            "orientationCounts": dict(orientation_counts),
            "confirmedRouteChapterCount": confirmed_summary["chapterCount"],
            "automaticRouteChapterCount": route_summary["chapterCount"],
            "needsHumanReviewCount": len(needs_review),
            "derivedSourceCount": len(derived_sources),
            "excludedDerivedSourceCount": len(excluded_derived_sources),
            "activeSourceExclusionCount": len(exclusion_items),
            "cloudProviderUsed": (location_recognition.get("summary") or {}).get("cloudProviderUsed")
            or location_recognition.get("cloudProviderModel"),
            "cloudCallsAllowed": bool(pipeline.get("allowCloudCall")),
            "cloudRecognitionDryRun": bool(location_recognition.get("dryRun")),
            "cloudFramesSent": cloud_frames_sent,
            "cloudRecognitionErrors": recognition_errors,
            "localModelUsed": pipeline.get("localModelUsed"),
            "localOcrStatus": local_ocr.get("status"),
            "localOcrPlaceHitVideoCount": ((local_ocr.get("summary") or {}).get("placeHitVideoCount")),
            "localOcrReport": local_ocr.get("json") or local_ocr.get("markdown"),
            "localVisionStatus": local_vision.get("status"),
            "localVisionRecognizedVideoCount": ((local_vision.get("summary") or {}).get("recognizedVideoCount")),
            "localVisionReport": local_vision.get("json") or local_vision.get("markdown"),
        },
        "codexVisualEvidence": {
            "status": codex_visual.get("status"),
            "sourceVideoCoverage": codex_source_count,
            "sampledFrameCoverage": codex_route.get("sampledFrameCoverage") or codex_visual.get("frameCount"),
            "routeSummary": codex_route.get("routeSummary"),
            "routeConfidence": codex_route.get("routeConfidence"),
            "provider": codex_route.get("provider"),
            "localModelUsed": codex_route.get("localModelUsed"),
            "cloudApiUsed": codex_route.get("cloudApiUsed"),
            "report": str((project_dir / "latest_codex_visual_route_review.json").resolve()),
            "reviewJson": str((project_dir / "latest_codex_visual_review.json").resolve()),
        },
        "localEvidence": {
            "tesseractOcr": {
                "status": local_ocr.get("status"),
                "summary": local_ocr.get("summary"),
                "report": local_ocr.get("json") or local_ocr.get("markdown"),
            },
            "ollamaVision": {
                "status": local_vision.get("status"),
                "summary": local_vision.get("summary"),
                "report": local_vision.get("json") or local_vision.get("markdown"),
            },
        },
        "dayPlaceSummary": codex_day_summary if codex_visual_ready else {day: dict(counter) for day, counter in sorted(day_counts.items())},
        "legacyLocationMapDayPlaceSummary": {day: dict(counter) for day, counter in sorted(day_counts.items())},
        "confirmedRoute": confirmed_summary,
        "automaticRoute": route_summary,
        "rows": rows,
        "unrecognizedVideos": uncovered,
        "needsHumanReview": needs_review,
        "derivedSources": derived_sources,
        "excludedDerivedSources": excluded_derived_sources,
        "sourceExclusions": exclusion_items,
        "blockers": blockers,
        "warnings": warnings,
        "nextActions": [
            "Use the Codex visual route candidate to replace stale broad confirmed_route_timeline.json chapters.",
            "Keep exact place labels conservative unless signage, OCR, landmark, or user confirmation supports them.",
            "Keep rendered/derived exports excluded from source media.",
            "Build the next DaVinci timeline from the corrected route structure, then read it back before render.",
        ],
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    if summary.get("primaryRecognitionProvider") == "codex_visual_inspection":
        local_model_line = "- Local model for current pass: `not used`"
    else:
        local_model_line = f"- Local model: `{summary.get('localModelUsed')}`"
    lines = [
        "# Footage Recognition And Route Report",
        "",
        f"Status: `{report['status']}`",
        f"Project: `{report['projectDir']}`",
        "",
        "## Summary",
        f"- Videos scanned: `{summary['mediaVideoCount']}`",
        f"- Total indexed videos before exclusions: `{summary.get('totalIndexedVideoCount')}`",
        f"- Videos with location rows: `{summary['recognizedVideoCount']}`",
        f"- Primary recognition provider: `{summary.get('primaryRecognitionProvider')}`",
        f"- Codex visual status: `{summary.get('codexVisualStatus')}`; source coverage: `{summary.get('codexVisualSourceCoverage')}`",
        f"- Recognition coverage: `{summary['recognitionCoverageRatio']}`",
        f"- Frame count used for recognition: `{summary['frameCount']}`",
        f"- Confirmed route chapters: `{summary['confirmedRouteChapterCount']}`",
        f"- Orientation counts: `{summary['orientationCounts']}`",
        f"- Confidence counts: `{summary['confidenceCounts']}`",
        f"- Cloud provider: `{summary.get('cloudProviderUsed')}`",
        local_model_line,
        f"- Local OCR status: `{summary.get('localOcrStatus')}`; place-hit videos: `{summary.get('localOcrPlaceHitVideoCount')}`",
        f"- Local vision status: `{summary.get('localVisionStatus')}`; recognized videos: `{summary.get('localVisionRecognizedVideoCount')}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in report.get("warnings") or ["None"])
    lines.extend(["", "## Day And Place Summary"])
    for day, places in report.get("dayPlaceSummary", {}).items():
        place_text = ", ".join(f"{place}: {count}" for place, count in places.items())
        lines.append(f"- `{day}`: {place_text}")
    lines.extend(["", "## Confirmed Route"])
    for idx, chapter in enumerate(report.get("confirmedRoute", {}).get("chapters") or [], start=1):
        lines.append(
            f"- {idx}. `{chapter.get('place') or chapter.get('chapter')}` | city `{chapter.get('city')}` | "
            f"confidence `{chapter.get('confidenceLevel')}` | videos `{len(chapter.get('videos') or chapter.get('videoPaths') or [])}`"
        )
    lines.extend(["", "## Video Rows"])
    lines.append("| Date | File | Place | Confidence | Orientation | Duration | Review |")
    lines.append("| --- | --- | --- | --- | --- | ---: | --- |")
    for row in report.get("rows") or []:
        orient = row.get("orientation") or {}
        name = str(row.get("name") or "").replace("|", "\\|")
        place = str(row.get("place") or "").replace("|", "\\|")
        lines.append(
            f"| {row.get('date')} | `{name}` | {place} | {row.get('confidenceLevel')} "
            f"({row.get('confidence')}) | {orient.get('orientation')} {orient.get('displayWidth')}x{orient.get('displayHeight')} "
            f"rot{orient.get('rotation')} | {row.get('durationSeconds')} | {row.get('needsHumanReview')} |"
        )
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a footage recognition and route-readiness MD report.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "recognition_reports" / timestamp
    report = build_report(project_dir, output_dir)
    json_path = output_dir / "footage_recognition_route_report.json"
    md_path = output_dir / "footage_recognition_route_report.md"
    write_json(json_path, report)
    write_markdown(md_path, report)
    write_json(
        project_dir / "latest_footage_recognition_route_report.json",
        {"createdAt": report["createdAt"], "status": report["status"], "report": str(json_path), "markdown": str(md_path)},
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Recognition report: {report['status']}")
        print(f"Markdown: {md_path}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if report["status"] in {"ready", "ready_with_warnings", "ready_with_caveats"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
