#!/usr/bin/env python3
"""Audit a travel film package against client-deliverable editorial rules."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


BAD_TITLE_PATTERNS = [
    re.compile(r"-[0-9a-f]{6,}\b", re.IGNORECASE),
    re.compile(r"\b[0-9a-f]{8,}\b", re.IGNORECASE),
]
BAD_TITLE_TEXT = {"图片开图", "长片开场", "路线章节", "travel film"}
VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".hevc",
    ".insv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mts",
    ".webm",
}
AUDIO_EXTENSIONS = {".aac", ".aiff", ".aif", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
IMAGE_TEXT_EXTENSIONS = {".ass", ".jpeg", ".jpg", ".png", ".srt", ".txt", ".vtt"}
NORMALIZATION_POLICY_READY = {"ready", "applied", "applied_v10"}
DESIGNED_VERTICAL_INSERT_TOKENS = {
    "designed_phone_insert",
    "phone_insert",
    "portrait_insert",
    "vertical_insert",
    "split_screen",
    "picture_in_picture",
    "pip",
}
NORMALIZATION_TREATMENT_TOKENS = {"crop", "matte", "blur", "pillar", "fill", "reframe", "safe_area"}


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


def file_size(path: Path | None) -> int:
    return path.stat().st_size if path and path.exists() else 0


def cue_count(path: Path | None) -> int:
    if not path or not path.exists():
        return 0
    total = 0
    for block in path.read_text(encoding="utf-8", errors="ignore").strip().split("\n\n"):
        if "-->" in block:
            total += 1
    return total


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


def ffprobe_video(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"error": (result.stderr or result.stdout).strip()}
    try:
        probe = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"error": str(exc)}
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"), {})
    return {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "frameRate": frame_rate_value(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "videoBitrateMbps": round(float(video.get("bit_rate") or 0) / 1_000_000, 3) if video else 0,
        "durationSeconds": float((probe.get("format") or {}).get("duration") or 0),
        "audioCodec": audio.get("codec_name"),
        "audioChannels": audio.get("channels"),
        "formatBitrateMbps": round(float((probe.get("format") or {}).get("bit_rate") or 0) / 1_000_000, 3),
    }


def stream_rotation(stream: dict[str, Any]) -> int:
    tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
    values: list[Any] = []
    if tags.get("rotate") is not None:
        values.append(tags.get("rotate"))
    for side_data in stream.get("side_data_list") or []:
        if isinstance(side_data, dict) and side_data.get("rotation") is not None:
            values.append(side_data.get("rotation"))
    for value in values:
        try:
            return int(round(float(value))) % 360
        except (TypeError, ValueError):
            continue
    return 0


def ffprobe_source_geometry(path: Path, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = str(path)
    if key in cache:
        return cache[key]
    if not path.exists():
        cache[key] = {"orientation": "unknown", "error": "source missing"}
        return cache[key]
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        cache[key] = {"orientation": "unknown", "error": (result.stderr or result.stdout).strip()}
        return cache[key]
    try:
        probe = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        cache[key] = {"orientation": "unknown", "error": str(exc)}
        return cache[key]
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), {})
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    rotation = stream_rotation(video)
    display_width, display_height = (height, width) if rotation in {90, 270} else (width, height)
    if display_width <= 0 or display_height <= 0:
        orientation = "unknown"
    elif display_width > display_height:
        orientation = "landscape"
    elif display_height > display_width:
        orientation = "portrait"
    else:
        orientation = "square"
    cache[key] = {
        "rawWidth": width,
        "rawHeight": height,
        "rotationDegrees": rotation,
        "displayWidth": display_width,
        "displayHeight": display_height,
        "orientation": orientation,
    }
    return cache[key]


def clip_role_text(clip: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "role",
        "purpose",
        "name",
        "title",
        "visualTreatment",
        "normalization",
        "orientationPolicy",
        "customData",
    ):
        value = clip.get(key)
        if value:
            values.append(json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value))
    return " ".join(values).lower()


def is_blueprint_video_source_clip(clip: dict[str, Any]) -> bool:
    source_raw = str(clip.get("sourcePath") or "").strip()
    if not source_raw:
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type == "audio":
        return False
    suffix = Path(source_raw).suffix.lower()
    if suffix in AUDIO_EXTENSIONS or suffix in IMAGE_TEXT_EXTENSIONS:
        return False
    return suffix in VIDEO_EXTENSIONS or track_type == "video"


def has_declared_vertical_design_exception(clip: dict[str, Any], visual_policy: dict[str, Any]) -> bool:
    text = clip_role_text(clip)
    has_insert_declaration = any(token in text for token in DESIGNED_VERTICAL_INSERT_TOKENS)
    has_normalization_treatment = any(token in text for token in NORMALIZATION_TREATMENT_TOKENS) or any(
        clip.get(key)
        for key in (
            "crop",
            "cropMode",
            "matte",
            "blurBackground",
            "scaleMode",
            "transform",
            "visualTreatment",
            "normalization",
            "orientationPolicy",
        )
    )
    return (
        visual_policy.get("status") in NORMALIZATION_POLICY_READY
        and has_insert_declaration
        and bool(has_normalization_treatment)
    )


def blueprint_source_orientation_evidence(blueprint: dict[str, Any]) -> dict[str, Any]:
    visual_policy = blueprint.get("visualNormalizationPolicy") if isinstance(blueprint.get("visualNormalizationPolicy"), dict) else {}
    cache: dict[str, dict[str, Any]] = {}
    checked_count = 0
    landscape_count = 0
    allowed_non_landscape: list[dict[str, Any]] = []
    blocked_non_landscape: list[dict[str, Any]] = []
    probe_errors: list[dict[str, Any]] = []
    for index, clip in enumerate(blueprint.get("clips") or []):
        if not isinstance(clip, dict) or not is_blueprint_video_source_clip(clip):
            continue
        checked_count += 1
        source_path = Path(str(clip.get("sourcePath"))).expanduser()
        geometry = ffprobe_source_geometry(source_path, cache)
        item = {
            "clipIndex": index,
            "role": clip.get("role") or clip.get("purpose"),
            "trackIndex": clip.get("trackIndex"),
            "timelineStartSeconds": timeline_start(clip),
            "sourcePath": str(source_path),
            "geometry": geometry,
        }
        if geometry.get("error"):
            probe_errors.append(item)
        if geometry.get("orientation") == "landscape":
            landscape_count += 1
            continue
        if has_declared_vertical_design_exception(clip, visual_policy):
            allowed_non_landscape.append(item)
        else:
            blocked_non_landscape.append(item)
    return {
        "passed": checked_count > 0 and not blocked_non_landscape,
        "checkedVideoClipCount": checked_count,
        "uniqueVideoSourceCount": len(cache),
        "landscapeClipCount": landscape_count,
        "allowedDesignedNonLandscapeCount": len(allowed_non_landscape),
        "blockedNonLandscapeCount": len(blocked_non_landscape),
        "visualNormalizationPolicy": visual_policy,
        "blockedNonLandscapeClips": blocked_non_landscape[:20],
        "allowedDesignedNonLandscapeClips": allowed_non_landscape[:20],
        "probeErrors": probe_errors[:20],
    }


def latest_recognition_report(project_dir: Path) -> dict[str, Any]:
    pointer = load_json(project_dir / "latest_footage_recognition_route_report.json") or {}
    report_path = Path(pointer.get("report") or "") if pointer.get("report") else None
    report = load_json(report_path) if report_path else None
    if report:
        return report
    candidates = sorted(project_dir.glob("recognition_reports/*/footage_recognition_route_report.json"))
    if candidates:
        return load_json(candidates[-1]) or {}
    return {}


def latest_codex_visual_review(project_dir: Path) -> dict[str, Any]:
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


def track_count(resolve_audit: dict[str, Any], kind: str, index: int) -> int | None:
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        if int(row.get("index") or -1) == index:
            return int(row.get("itemCount") or 0)
    return None


def timeline_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds"):
        value = clip.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def title_texts(package_dir: Path, blueprint: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for clip in blueprint.get("clips") or []:
        for key in ("title", "titleText", "cityTitle", "text", "place", "subtitle"):
            if clip.get(key):
                texts.append(str(clip[key]))
    for manifest_path in sorted(package_dir.glob("title_cards*/**/*manifest*.json")) + sorted((package_dir / "title_cards").glob("*manifest*.json")):
        manifest = load_json(manifest_path) or {}
        for card in manifest.get("cards") or manifest.get("items") or []:
            for key in ("title", "subtitle", "cityTitle", "text"):
                if card.get(key):
                    texts.append(str(card[key]))
    return texts


def derived_blueprint_sources(blueprint: dict[str, Any]) -> list[str]:
    tokens = ("vlog", "render", "master", "highbitrate", "final", "成片", "终稿")
    paths = []
    for clip in blueprint.get("clips") or []:
        source = str(clip.get("sourcePath") or "")
        name = Path(source).name.lower()
        if source and any(token in name for token in tokens):
            paths.append(source)
    return sorted(set(paths))


def has_bad_title_text(texts: list[str]) -> tuple[bool, list[str]]:
    bad: list[str] = []
    for text in texts:
        normalized = text.strip().lower()
        if not normalized:
            continue
        if any(pattern.search(text) for pattern in BAD_TITLE_PATTERNS):
            bad.append(text)
            continue
        if normalized in BAD_TITLE_TEXT or any(item in text for item in BAD_TITLE_TEXT):
            bad.append(text)
    return bool(bad), bad


def opening_hook_evidence(blueprint: dict[str, Any]) -> dict[str, Any]:
    early = [clip for clip in blueprint.get("clips") or [] if timeline_start(clip) <= 1.0]
    aerial = [
        clip
        for clip in early
        if any(token in str(clip.get("role") or clip.get("purpose") or "").lower() for token in ("aerial", "establish", "opening_city"))
    ]
    title = [
        clip
        for clip in early
        if clip.get("cityTitle") or clip.get("titleText") or "city_title" in str(clip.get("role") or "").lower()
    ]
    return {
        "earlyClipCount": len(early),
        "earlyRoles": [clip.get("role") or clip.get("purpose") for clip in early[:8]],
        "hasOpeningAerialAtStart": bool(aerial),
        "hasOpeningCityTitleAtStart": bool(title),
        "openingAerialPaths": [clip.get("sourcePath") for clip in aerial if clip.get("sourcePath")],
    }


def ending_hook_evidence(blueprint: dict[str, Any]) -> dict[str, Any]:
    clips = blueprint.get("clips") or []
    target_duration = float(blueprint.get("targetDurationSeconds") or 0)
    if target_duration <= 0:
        for clip in clips:
            start = timeline_start(clip)
            duration = float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds") or 0)
            target_duration = max(target_duration, start + duration)
    tail_start = max(0.0, target_duration - 12.0)
    tail = [clip for clip in clips if timeline_start(clip) >= tail_start]
    aerial = [
        clip
        for clip in tail
        if any(token in str(clip.get("role") or clip.get("purpose") or "").lower() for token in ("ending_city", "aerial", "establish"))
    ]
    title = [
        clip
        for clip in tail
        if clip.get("cityTitle") or clip.get("titleText") or "ending_city" in str(clip.get("role") or "").lower()
    ]
    return {
        "targetDurationSeconds": target_duration,
        "tailStartSeconds": tail_start,
        "tailClipCount": len(tail),
        "tailRoles": [clip.get("role") or clip.get("purpose") for clip in tail[:8]],
        "hasEndingAerialAtTail": bool(aerial),
        "hasEndingTitleAtTail": bool(title),
        "endingAerialPaths": [clip.get("sourcePath") for clip in aerial if clip.get("sourcePath")],
        "endingHook": blueprint.get("endingHook"),
    }


def visual_bridge_source_ok(source_raw: str) -> bool:
    if not source_raw:
        return False
    source_path = Path(source_raw).expanduser()
    source_parts = {part.lower() for part in source_path.parts}
    return (
        source_path.exists()
        and "title_cards" not in source_parts
        and source_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}
    )


def blueprint_title_bridge_evidence(blueprint: dict[str, Any], min_route_chapters: int) -> dict[str, Any]:
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    title_clips = [
        clip
        for clip in clips
        if isinstance(clip, dict)
        and "subtitle" not in str(clip.get("role") or clip.get("purpose") or "").lower()
        and any(
            token in str(clip.get("role") or clip.get("purpose") or "").lower()
            for token in ("title", "place_card", "opening_city", "ending_city")
        )
    ]
    slate_sources: list[str] = []
    missing_sources: list[str] = []
    long_texts: list[str] = []
    opening_count = 0
    ending_count = 0
    chapter_count = 0
    for clip in title_clips:
        role = str(clip.get("role") or clip.get("purpose") or "").lower()
        source_raw = str(clip.get("sourcePath") or "")
        if not source_raw or not Path(source_raw).expanduser().exists():
            missing_sources.append(source_raw)
        if not visual_bridge_source_ok(source_raw):
            slate_sources.append(source_raw)
        if "opening" in role:
            if visual_bridge_source_ok(source_raw):
                opening_count += 1
        elif "ending" in role:
            if visual_bridge_source_ok(source_raw):
                ending_count += 1
        elif "place_card" in role or "chapter" in role or "title" in role:
            if visual_bridge_source_ok(source_raw):
                chapter_count += 1
        for key in ("title", "titleText", "cityTitle", "place", "subtitle", "text"):
            text = str(clip.get(key) or "").strip()
            if len(text) > 46:
                long_texts.append(text)
    passed = (
        bool(title_clips)
        and opening_count >= 1
        and ending_count >= 1
        and chapter_count >= min_route_chapters
        and not missing_sources
        and not slate_sources
        and not long_texts
    )
    return {
        "passed": passed,
        "titleClipCount": len(title_clips),
        "openingCount": opening_count,
        "endingCount": ending_count,
        "chapterCount": chapter_count,
        "missingSources": missing_sources[:20],
        "slateSources": slate_sources[:20],
        "longTexts": long_texts[:20],
        "titleClipRoles": [clip.get("role") or clip.get("purpose") for clip in title_clips[:20]],
    }


def visual_polish_evidence(package_dir: Path, min_route_chapters: int, blueprint: dict[str, Any] | None = None) -> dict[str, Any]:
    candidates = [
        package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
        package_dir / "visual_polish" / "visual_polish_manifest.json",
        package_dir / "visual_polish_manifest.json",
    ]
    manifest_path = next((path for path in candidates if path.exists()), None)
    manifest = load_json(manifest_path) if manifest_path else None
    segments = manifest.get("segments") if isinstance(manifest, dict) else []
    if not isinstance(segments, list):
        segments = []

    missing_segment_files: list[str] = []
    missing_source_files: list[str] = []
    slate_sources: list[str] = []
    generic_titles: list[str] = []
    opening_count = 0
    ending_count = 0
    chapter_count = 0
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        segment_id = str(segment.get("id") or "")
        mode = str(segment.get("mode") or "")
        title = str(segment.get("title") or "").strip()
        timeline_start = float(segment.get("timeline_start") or segment.get("timelineStartSeconds") or 0)
        source_raw = str(segment.get("source") or segment.get("sourcePath") or "")
        segment_raw = str(segment.get("segment") or segment.get("segmentPath") or "")
        source_path = Path(source_raw).expanduser() if source_raw else None
        segment_path = Path(segment_raw).expanduser() if segment_raw else None

        is_opening = mode == "opening" or segment_id.startswith("opening") or timeline_start <= 1.0
        is_ending = mode == "ending" or segment_id.startswith("ending") or timeline_start >= 1180.0
        if is_opening:
            opening_count += 1
        elif is_ending:
            ending_count += 1
        else:
            chapter_count += 1

        if segment_path and not segment_path.exists():
            missing_segment_files.append(segment_raw)
        if source_path and not source_path.exists():
            missing_source_files.append(source_raw)
        if not visual_bridge_source_ok(source_raw):
            slate_sources.append(source_raw)
        if (is_opening or is_ending) and title.lower() in {"japan", "travel film", "route", "arrival"}:
            generic_titles.append(title)

    blueprint_evidence = blueprint_title_bridge_evidence(blueprint or {}, min_route_chapters)

    passed = (
        manifest_path is not None
        and opening_count >= 1
        and ending_count >= 1
        and chapter_count >= min_route_chapters
        and not missing_segment_files
        and not missing_source_files
        and not slate_sources
        and not generic_titles
        and blueprint_evidence["passed"]
    )
    return {
        "passed": passed,
        "manifest": str(manifest_path) if manifest_path else None,
        "segmentCount": len(segments),
        "openingCount": opening_count,
        "endingCount": ending_count,
        "chapterCount": chapter_count,
        "missingSegmentFiles": missing_segment_files[:20],
        "missingSourceFiles": missing_source_files[:20],
        "slateSources": slate_sources[:20],
        "genericOpeningOrEndingTitles": generic_titles[:20],
        "blueprintTitleBridgeEvidence": blueprint_evidence,
    }


def find_subtitle_path(package_dir: Path, blueprint: dict[str, Any]) -> Path | None:
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    candidates = []
    if assets.get("subtitles"):
        candidates.append(Path(str(assets["subtitles"])))
    candidates.extend(sorted(package_dir.glob("subtitles*_dense.srt")))
    candidates.append(package_dir / "subtitles.srt")
    for path in candidates:
        path = path.expanduser()
        if path.exists():
            return path
    return None


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery_plan = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    render_verification = load_json(package_dir / "render_delivery_verification.json") or {}
    asset_ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    quality_report = load_json(package_dir / "quality_recut_report.json") or {}
    project_dir = Path(delivery_plan.get("projectDir") or package_dir.parents[1]).expanduser().resolve()
    recognition = latest_recognition_report(project_dir)
    recognition_blockers = recognition.get("blockers") or []
    codex_visual = latest_codex_visual_review(project_dir)
    codex_route = codex_visual.get("codexVisualRoute") or {}
    final_output = Path(args.output).expanduser().resolve() if args.output else None
    if not final_output and render_verification.get("output"):
        final_output = Path(render_verification["output"]).expanduser().resolve()
    if not final_output:
        renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        final_output = renders[0].resolve() if renders else None
    probe = ffprobe_video(final_output)
    checks: list[dict[str, Any]] = []

    def add(requirement: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
        checks.append(
            {
                "requirement": requirement,
                "status": "passed" if passed else ("warning" if warning else "blocked"),
                "evidence": evidence,
            }
        )

    rec_summary = recognition.get("summary") or {}
    media_video_count = int(rec_summary.get("mediaVideoCount") or codex_route.get("sourceVideoCoverage") or 0)
    excluded_source_count = int(rec_summary.get("activeSourceExclusionCount") or rec_summary.get("excludedDerivedSourceCount") or 0)
    if rec_summary.get("totalIndexedVideoCount"):
        expected_source_count = media_video_count
    else:
        expected_source_count = max(0, media_video_count - excluded_source_count)
    expected_source_count = expected_source_count or int(codex_route.get("sourceVideoCoverage") or codex_visual.get("sourceVideoCount") or 0)
    codex_source_count = int(codex_route.get("sourceVideoCoverage") or codex_visual.get("sourceVideoCount") or 0)
    codex_visual_ok = (
        bool(codex_visual)
        and codex_visual.get("status") in {"ready", "ready_with_warnings", "ready_with_caveats"}
        and codex_source_count >= expected_source_count > 0
        and codex_route.get("provider") == "codex_visual_inspection"
        and codex_route.get("localModelUsed") is False
    )
    cloud_recognition_ok = (
        bool(recognition)
        and not rec_summary.get("cloudRecognitionDryRun")
        and bool(rec_summary.get("cloudCallsAllowed"))
        and int(rec_summary.get("cloudFramesSent") or 0) > 0
        and not rec_summary.get("cloudRecognitionErrors")
    )
    add(
        "Full-folder recognition report exists before editing",
        (
            bool(recognition)
            and file_size(project_dir / "latest_footage_recognition_route_report.json") > 0
            and recognition.get("status") in {"ready", "ready_with_warnings", "ready_with_caveats"}
        )
        or codex_visual_ok,
        {
            "recognitionStatus": recognition.get("status"),
            "summary": rec_summary,
            "blockers": recognition_blockers,
            "codexVisualStatus": codex_visual.get("status"),
            "codexVisualSourceCoverage": codex_source_count,
            "expectedSourceCount": expected_source_count,
        },
    )
    add(
        "Location recognition evidence completed by approved provider",
        cloud_recognition_ok or codex_visual_ok,
        {
            "approvedProviders": ["codex_visual_inspection", "cloud_vision_api"],
            "codexVisualStatus": codex_visual.get("status"),
            "codexVisualProvider": codex_route.get("provider"),
            "codexVisualSourceCoverage": codex_source_count,
            "codexVisualLocalModelUsed": codex_route.get("localModelUsed"),
            "cloudCallsAllowed": rec_summary.get("cloudCallsAllowed"),
            "cloudRecognitionDryRun": rec_summary.get("cloudRecognitionDryRun"),
            "cloudFramesSent": rec_summary.get("cloudFramesSent"),
            "cloudRecognitionErrors": rec_summary.get("cloudRecognitionErrors"),
            "cloudProviderUsed": rec_summary.get("cloudProviderUsed"),
        },
    )
    add(
        "Every source video has a location row or Codex visual coverage",
        expected_source_count > 0
        and (
            int(rec_summary.get("recognizedVideoCount") or 0) >= expected_source_count
            or codex_source_count >= expected_source_count
        ),
        {
            **rec_summary,
            "expectedSourceCount": expected_source_count,
            "codexVisualSourceCoverage": codex_source_count,
        },
    )
    add(
        "Confirmed route is broken into real day/place chapters, not one broad scaffold",
        int(rec_summary.get("confirmedRouteChapterCount") or 0) >= args.min_route_chapters
        and not (recognition.get("confirmedRoute") or {}).get("broadScaffoldOnly"),
        recognition.get("confirmedRoute") or {},
    )
    add(
        "Derived prior exports are not used as raw source material",
        int(rec_summary.get("derivedSourceCount") or 0) == 0,
        recognition.get("derivedSources") or [],
    )
    blueprint_derived_sources = derived_blueprint_sources(blueprint)
    add(
        "Resolve blueprint does not use prior rendered exports as source clips",
        not blueprint_derived_sources,
        {"derivedBlueprintSources": blueprint_derived_sources[:20]},
    )

    orientation_counts = rec_summary.get("orientationCounts") or {}
    bad_orientation = sum(int(orientation_counts.get(key) or 0) for key in ("vertical", "square", "unknown"))
    add(
        "Source orientation is landscape-consistent or has an explicit normalization policy",
        bad_orientation == 0 or (blueprint.get("visualNormalizationPolicy") or {}).get("status") in NORMALIZATION_POLICY_READY,
        {"orientationCounts": orientation_counts, "visualNormalizationPolicy": blueprint.get("visualNormalizationPolicy")},
    )
    source_orientation = blueprint_source_orientation_evidence(blueprint)
    add(
        "Resolve blueprint contains no raw portrait/square/unknown video clips in the 16:9 master",
        source_orientation["passed"],
        source_orientation,
    )

    hook = opening_hook_evidence(blueprint)
    add(
        "Opening starts with city aerial/establishing footage plus a city title overlay",
        hook["hasOpeningAerialAtStart"] and hook["hasOpeningCityTitleAtStart"],
        hook,
    )
    ending_hook = ending_hook_evidence(blueprint)
    add(
        "Ending closes with aerial/establishing footage plus clean title typography",
        ending_hook["hasEndingAerialAtTail"] and ending_hook["hasEndingTitleAtTail"],
        ending_hook,
    )
    visual_polish = visual_polish_evidence(package_dir, args.min_route_chapters, blueprint)
    add(
        "Opening, chapter, and ending title moments are scenic video bridges, not black slates",
        visual_polish["passed"],
        visual_polish,
    )
    bad_title, bad_texts = has_bad_title_text(title_texts(package_dir, blueprint))
    add(
        "Title text contains no internal IDs, placeholder Chinese, or generic slate copy",
        not bad_title,
        {"badTexts": bad_texts[:20]},
    )

    subtitle_path = find_subtitle_path(package_dir, blueprint)
    subtitles = cue_count(subtitle_path)
    add(
        "No voiceover audio is imported; SRT captions are delivered for external TTS/Jianying",
        (track_count(resolve_audit, "audio", 2) in {0, None})
        and not ((blueprint.get("assets") or {}).get("voiceover"))
        and subtitle_path is not None
        and subtitles >= args.min_subtitle_cues,
        {
            "a2VoiceoverItems": track_count(resolve_audit, "audio", 2),
            "voiceoverAsset": (blueprint.get("assets") or {}).get("voiceover"),
            "subtitlePath": str(subtitle_path) if subtitle_path else None,
            "cueCount": subtitles,
        },
    )

    bgm_assets = (blueprint.get("assets") or {}).get("bgm") if isinstance(blueprint.get("assets"), dict) else []
    add(
        "BGM is a real local asset and is present on the Resolve timeline",
        bool(bgm_assets)
        and all(Path(str(path)).expanduser().exists() for path in bgm_assets)
        and (track_count(resolve_audit, "audio", 3) or 0) > 0,
        {"bgmAssets": bgm_assets, "a3BgmItems": track_count(resolve_audit, "audio", 3)},
    )

    transition_plan = blueprint.get("transitionPlan") or []
    bridge_clips = [
        clip
        for clip in blueprint.get("clips") or []
        if any(token in str(clip.get("role") or clip.get("purpose") or "").lower() for token in ("transition", "bridge", "establish", "aerial"))
    ]
    add(
        "Chapter/day transitions use visual bridge or establishing footage, not abrupt concatenation",
        len(transition_plan) >= args.min_transitions and len(bridge_clips) >= args.min_transitions,
        {"transitionPlanCount": len(transition_plan), "bridgeClipCount": len(bridge_clips)},
    )
    add(
        "A restrained effect plan exists for title reveals, transitions, or route motion",
        bool(blueprint.get("effectPlan") or quality_report.get("effectPlan")),
        {"effectPlan": blueprint.get("effectPlan") or quality_report.get("effectPlan")},
        warning=args.effects_warning_only,
    )

    ledger_items = asset_ledger.get("items") or []
    unresolved_assets = [
        item
        for item in ledger_items
        if item.get("type") in {"bgm", "aerial_or_stock", "font"}
        and item.get("licenseStatus") not in {"verified", "verified_original_generated_local", "system-font-render-only"}
    ]
    add(
        "BGM, aerial/stock, and font assets have verified license evidence",
        bool(ledger_items) and not unresolved_assets and asset_ledger.get("finalReady") is True,
        {"ledgerItems": len(ledger_items), "unresolvedAssets": unresolved_assets[:10], "finalReady": asset_ledger.get("finalReady")},
    )

    add(
        "Final render file is valid and client-quality 4K high-frame-rate/high-bitrate",
        bool(final_output)
        and final_output.exists()
        and not probe.get("error")
        and probe.get("width") == args.width
        and probe.get("height") == args.height
        and float(probe.get("frameRate") or 0) >= args.min_fps
        and float(probe.get("videoBitrateMbps") or probe.get("formatBitrateMbps") or 0) >= args.min_video_bitrate_mbps,
        {"output": str(final_output) if final_output else None, "probe": probe},
    )
    add(
        "Render verification report passed after export",
        render_verification.get("status") == "passed" and not render_verification.get("blockers"),
        {"status": render_verification.get("status"), "blockers": render_verification.get("blockers")},
    )

    blocked = [row for row in checks if row["status"] == "blocked"]
    warnings = [row for row in checks if row["status"] == "warning"]
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked" if blocked else ("passed_with_warnings" if warnings else "passed"),
        "packageDir": str(package_dir),
        "projectDir": str(project_dir),
        "finalOutput": str(final_output) if final_output else None,
        "checks": checks,
        "blockers": [row["requirement"] for row in blocked],
        "warnings": [row["requirement"] for row in warnings],
        "summary": {"passed": len([row for row in checks if row["status"] == "passed"]), "blocked": len(blocked), "warnings": len(warnings)},
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Client Delivery Rules Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Final output: `{report.get('finalOutput')}`",
        "",
        "## Summary",
        f"- Passed: `{report['summary']['passed']}`",
        f"- Blocked: `{report['summary']['blocked']}`",
        f"- Warnings: `{report['summary']['warnings']}`",
        "",
        "## Checks",
    ]
    for row in report["checks"]:
        lines.extend(
            [
                "",
                f"### {row['requirement']}",
                f"- Status: `{row['status']}`",
                f"- Evidence: `{json.dumps(row['evidence'], ensure_ascii=False)[:2000]}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit package against client-deliverable travel video rules.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output", help="Final render path to probe.")
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--min-fps", type=float, default=50.0)
    parser.add_argument("--min-video-bitrate-mbps", type=float, default=60.0)
    parser.add_argument("--min-subtitle-cues", type=int, default=40)
    parser.add_argument("--min-route-chapters", type=int, default=3)
    parser.add_argument("--min-transitions", type=int, default=2)
    parser.add_argument("--effects-warning-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    json_path = package_dir / "client_delivery_rules_audit.json"
    md_path = package_dir / "client_delivery_rules_audit.md"
    write_json(json_path, report)
    write_markdown(md_path, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Client delivery rules audit: {report['status']}")
        print(f"Report: {md_path}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if report["status"] in {"passed", "passed_with_warnings"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
