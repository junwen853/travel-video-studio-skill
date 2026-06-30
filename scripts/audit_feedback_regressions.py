#!/usr/bin/env python3
"""Audit concrete user feedback as reusable travel-video regressions."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any


FRAME_W = 640
FRAME_H = 360
DEFAULT_FEEDBACK = "opening_title=0"
TITLE_ROLE_TOKENS = ("opening", "title", "chapter", "ending")
SCENIC_AUDIO_ROLE_TOKENS = ("opening", "title", "chapter", "transition", "bridge", "establish", "aerial")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=False)


def load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_time(value: str) -> float:
    raw = value.strip()
    if not raw:
        raise ValueError("empty time value")
    if ":" not in raw:
        return float(raw)
    parts = [float(part) for part in raw.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"unsupported time value: {value}")


def slug(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return out.strip("_") or "feedback"


def parse_feedback(raw: str | None) -> list[dict[str, Any]]:
    text = raw or DEFAULT_FEEDBACK
    points: list[dict[str, Any]] = []
    for index, part in enumerate(text.split(","), start=1):
        item = part.strip()
        if not item:
            continue
        if "=" in item:
            label, value = item.split("=", 1)
        elif "@" in item:
            label, value = item.split("@", 1)
        else:
            label, value = f"feedback_{index}", item
        second = parse_time(value)
        points.append(
            {
                "id": slug(label),
                "label": label.strip() or f"feedback_{index}",
                "second": round(max(0.0, second), 3),
                "source": "user_feedback",
            }
        )
    return points


def unique_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for point in points:
        key = round(float(point["second"]) * 1000)
        if key in seen:
            continue
        seen.add(key)
        out.append(point)
    return out


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


def ffprobe_json(path: Path) -> dict[str, Any]:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    return json.loads(proc.stdout.decode("utf-8"))


def probe_summary(probe: dict[str, Any]) -> dict[str, Any]:
    video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {
        "durationSeconds": float((probe.get("format") or {}).get("duration") or 0),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "frameRate": frame_rate_value(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "videoBitrateMbps": round(float(video.get("bit_rate") or 0) / 1_000_000, 3) if video else 0,
        "audioCodec": audio.get("codec_name"),
        "audioChannels": audio.get("channels"),
    }


def ffmpeg_precise_seek_args(second: float, preroll_seconds: float = 2.0) -> tuple[list[str], list[str]]:
    target = max(second, 0.0)
    pre_seek = max(0.0, target - preroll_seconds)
    post_seek = max(0.0, target - pre_seek)
    return ["-ss", f"{pre_seek:.3f}", "-accurate_seek"], ["-ss", f"{post_seek:.3f}"]


def extract_jpeg(video: Path, second: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pre_seek, post_seek = ffmpeg_precise_seek_args(second)
    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *pre_seek,
            "-i",
            str(video),
            *post_seek,
            "-frames:v",
            "1",
            "-vf",
            f"scale={FRAME_W}:{FRAME_H}:force_original_aspect_ratio=decrease,"
            f"pad={FRAME_W}:{FRAME_H}:(ow-iw)/2:(oh-ih)/2:black",
            "-q:v",
            "2",
            str(out_path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())


def gray_frame(video: Path, second: float) -> bytes:
    pre_seek, post_seek = ffmpeg_precise_seek_args(second)
    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            *pre_seek,
            "-i",
            str(video),
            *post_seek,
            "-frames:v",
            "1",
            "-vf",
            f"scale={FRAME_W}:{FRAME_H}:force_original_aspect_ratio=decrease,"
            f"pad={FRAME_W}:{FRAME_H}:(ow-iw)/2:(oh-ih)/2:black,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    expected = FRAME_W * FRAME_H
    if len(proc.stdout) != expected:
        raise RuntimeError(f"Expected {expected} gray bytes, got {len(proc.stdout)}")
    return proc.stdout


def crop_values(data: bytes, x0: int, x1: int, y0: int = 0, y1: int = FRAME_H) -> list[int]:
    values: list[int] = []
    for y in range(y0, y1):
        start = y * FRAME_W + x0
        values.extend(data[start : y * FRAME_W + x1])
    return values


def frame_metrics(video: Path, second: float) -> dict[str, Any]:
    data = gray_frame(video, second)
    side_w = int(FRAME_W * 0.115)
    center_margin = int(FRAME_W * 0.28)
    left = crop_values(data, 0, side_w)
    right = crop_values(data, FRAME_W - side_w, FRAME_W)
    center = crop_values(data, center_margin, FRAME_W - center_margin, int(FRAME_H * 0.15), int(FRAME_H * 0.85))

    def mean(values: list[int]) -> float:
        return statistics.fmean(values) if values else 0.0

    def stdev(values: list[int]) -> float:
        return statistics.pstdev(values) if len(values) > 1 else 0.0

    def dark_ratio(values: list[int], threshold: int = 12) -> float:
        return sum(1 for value in values if value <= threshold) / max(1, len(values))

    left_mean = mean(left)
    right_mean = mean(right)
    center_mean = mean(center)
    side_mean = (left_mean + right_mean) / 2.0
    left_dark = dark_ratio(left)
    right_dark = dark_ratio(right)
    side_dark = min(left_dark, right_dark)
    side_std = (stdev(left) + stdev(right)) / 2.0
    contrast = max(0.0, center_mean - side_mean) / 255.0
    pillarbox_score = side_dark * contrast
    suspected = (
        left_dark >= 0.72
        and right_dark >= 0.72
        and side_mean <= 24
        and side_std <= 28
        and center_mean >= 35
        and pillarbox_score >= 0.12
    )
    return {
        "second": round(second, 3),
        "leftMean": round(left_mean, 3),
        "rightMean": round(right_mean, 3),
        "centerMean": round(center_mean, 3),
        "sideDarkRatio": round(side_dark, 4),
        "sideStd": round(side_std, 3),
        "pillarboxScore": round(pillarbox_score, 4),
        "pillarboxSuspected": suspected,
    }


def make_contact_sheet(frame_paths: list[Path], output: Path) -> str | None:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    if not frame_paths:
        return None
    images = [Image.open(path).convert("RGB") for path in frame_paths]
    cols = min(4, len(images))
    rows = math.ceil(len(images) / cols)
    label_h = 34
    sheet = Image.new("RGB", (cols * FRAME_W, rows * (FRAME_H + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (path, image) in enumerate(zip(frame_paths, images)):
        x = (index % cols) * FRAME_W
        y = (index // cols) * (FRAME_H + label_h)
        sheet.paste(image, (x, y))
        draw.text((x + 10, y + FRAME_H + 8), path.stem[:90], fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    return str(output)


def resolve_video(package_dir: Path, raw: str | None) -> Path | None:
    if raw:
        return Path(raw).expanduser().resolve()
    render_verification = load_json(package_dir / "render_delivery_verification.json") or {}
    if render_verification.get("output"):
        return Path(str(render_verification["output"])).expanduser().resolve()
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    return renders[0].resolve() if renders else None


def find_bgm_manifest(package_dir: Path, blueprint: dict[str, Any]) -> Path | None:
    cues = (blueprint.get("audioPlan") or {}).get("bgmCues") or []
    for cue in cues:
        if isinstance(cue, dict) and cue.get("manifest"):
            path = Path(str(cue["manifest"])).expanduser()
            if path.exists():
                return path
    candidates = sorted((package_dir / "bgm").glob("*manifest*.json"))
    return candidates[-1] if candidates else None


def find_subtitle_manifest(package_dir: Path) -> Path | None:
    candidates = [
        package_dir / "subtitle_overlays_title_safe" / "segment_overlay_manifest.json",
        package_dir / "subtitle_overlay_assets" / "segment_overlay_manifest.json",
        package_dir / "overlay_video_burnin" / "manifest.json",
        package_dir / "subtitle_overlays_burned_in" / "manifest.json",
    ]
    return next((path for path in candidates if path.exists()), None)


def find_title_manifest(package_dir: Path) -> Path | None:
    candidates = [
        package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json",
        package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
        package_dir / "visual_polish" / "visual_polish_manifest.json",
    ]
    return next((path for path in candidates if path.exists()), None)


def title_points(manifest: dict[str, Any] | None, max_points: int = 16) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not manifest:
        return out
    for item in manifest.get("segments") or []:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "").lower()
        if mode not in {"opening", "chapter", "ending", "transition"}:
            continue
        try:
            start = float(item.get("timeline_start", item.get("timelineStartSeconds")))
        except (TypeError, ValueError):
            continue
        title = str(item.get("title") or item.get("titleText") or item.get("cityTitle") or mode)
        out.append(
            {
                "id": slug(f"{mode}_{title}_{start:.2f}"),
                "label": f"{mode}: {title}",
                "second": round(max(0.0, start), 3),
                "source": "title_manifest",
            }
        )
        if len(out) >= max_points:
            break
    return out


def track_count(resolve_audit: dict[str, Any], kind: str, index: int) -> int | None:
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        if int(row.get("index") or -1) == index:
            return int(row.get("itemCount") or 0)
    return None


def clip_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds"):
        try:
            return float(clip.get(key))
        except (TypeError, ValueError):
            continue
    return 0.0


def clip_duration(clip: dict[str, Any]) -> float:
    for key in ("durationSeconds", "sourceDurationSeconds"):
        try:
            value = float(clip.get(key))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    try:
        return max(0.0, float(clip.get("sourceEndSeconds")) - float(clip.get("sourceStartSeconds")))
    except (TypeError, ValueError):
        return 0.0


def overlapping_clips(blueprint: dict[str, Any], second: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for clip in blueprint.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        start = clip_start(clip)
        duration = clip_duration(clip)
        if start <= second <= start + max(0.0, duration):
            out.append(clip)
    return out


def clip_summary(clip: dict[str, Any]) -> dict[str, Any]:
    source = str(clip.get("sourcePath") or "")
    return {
        "role": clip.get("role") or clip.get("purpose"),
        "trackIndex": clip.get("trackIndex"),
        "start": round(clip_start(clip), 3),
        "duration": round(clip_duration(clip), 3),
        "sourceName": Path(source).name if source else None,
        "includeSourceAudio": clip.get("includeSourceAudio"),
        "preserveSourceAudio": clip.get("preserveSourceAudio"),
    }


def scenic_source_audio_flags(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    flagged: list[dict[str, Any]] = []
    for clip in blueprint.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        role = str(clip.get("role") or clip.get("purpose") or "").lower()
        if not any(token in role for token in SCENIC_AUDIO_ROLE_TOKENS):
            continue
        include = clip.get("includeSourceAudio")
        preserve = clip.get("preserveSourceAudio")
        source_audio = clip.get("sourceAudio")
        if include is True or preserve is True or source_audio is True:
            flagged.append(clip_summary(clip))
    return flagged


def volume_window(video: Path, second: float, duration: float) -> dict[str, Any]:
    start = max(0.0, second - duration / 2.0)
    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(video),
            "-vn",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ]
    )
    text = proc.stderr.decode("utf-8", "replace")
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", text)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", text)
    return {
        "second": round(second, 3),
        "windowStart": round(start, 3),
        "windowDuration": duration,
        "returnCode": proc.returncode,
        "meanVolumeDb": float(mean_match.group(1)) if mean_match else None,
        "maxVolumeDb": float(max_match.group(1)) if max_match else None,
    }


def normalize_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).upper()


def audit(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "feedback_regression_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    shutil.rmtree(frames_dir, ignore_errors=True)

    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    render_verification = load_json(package_dir / "render_delivery_verification.json") or {}
    visual_audio_audit = load_json(package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json") or {}
    video = resolve_video(package_dir, args.video)
    if not video or not video.exists():
        raise FileNotFoundError(f"Final render not found: {video}")

    probe = ffprobe_json(video)
    probe_info = probe_summary(probe)
    title_manifest_path = Path(args.title_manifest).expanduser() if args.title_manifest else find_title_manifest(package_dir)
    title_manifest = load_json(title_manifest_path) or {}
    subtitle_manifest_path = (
        Path(args.subtitle_manifest).expanduser() if args.subtitle_manifest else find_subtitle_manifest(package_dir)
    )
    subtitle_manifest = load_json(subtitle_manifest_path) or {}
    bgm_manifest_path = Path(args.bgm_manifest).expanduser() if args.bgm_manifest else find_bgm_manifest(package_dir, blueprint)
    bgm_manifest = load_json(bgm_manifest_path) or {}

    points = parse_feedback(args.feedback_timestamps)
    if args.include_title_points:
        points.extend(title_points(title_manifest))
    points = [p for p in unique_points(points) if p["second"] <= probe_info["durationSeconds"] + 0.25]

    checks: list[dict[str, Any]] = []

    def add(requirement: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
        checks.append(
            {
                "requirement": requirement,
                "status": "passed" if passed else ("warning" if warning else "blocked"),
                "evidence": evidence,
            }
        )

    add(
        "Final Resolve render exists and render verification passed",
        video.exists() and render_verification.get("status") == "passed" and not render_verification.get("blockers"),
        {"video": str(video), "probe": probe_info, "renderVerificationStatus": render_verification.get("status")},
    )

    add(
        "Resolve readback matches the current blueprint timeline",
        bool(resolve_audit)
        and resolve_audit.get("projectName") == blueprint.get("projectName")
        and resolve_audit.get("timelineName") == blueprint.get("timelineName"),
        {
            "blueprintProject": blueprint.get("projectName"),
            "readbackProject": resolve_audit.get("projectName"),
            "blueprintTimeline": blueprint.get("timelineName"),
            "readbackTimeline": resolve_audit.get("timelineName"),
        },
    )

    opening_segments = [
        item for item in title_manifest.get("segments") or [] if isinstance(item, dict) and str(item.get("mode")) == "opening"
    ]
    forbidden_terms = [str(item) for item in title_manifest.get("forbiddenOpeningText") or title_manifest.get("forbiddenVisibleText") or []]
    expected_title = str(title_manifest.get("expectedOpeningTitle") or title_manifest.get("cityTitle") or "").strip()
    opening_title_text = " ".join(str(item.get("title") or item.get("titleText") or item.get("cityTitle") or "") for item in opening_segments)
    forbidden_hits = [
        term
        for term in forbidden_terms
        if normalize_text(term) and normalize_text(term) in normalize_text(opening_title_text)
    ]
    add(
        "Opening title is a single clean city title with no ghosted route/date text",
        bool(title_manifest)
        and title_manifest.get("status") in {"passed", "ready", "ready_with_warnings", None}
        and bool(opening_segments)
        and bool(expected_title)
        and normalize_text(expected_title) in normalize_text(opening_title_text)
        and not forbidden_hits
        and all(not str(item.get("subtitle") or "").strip() for item in opening_segments),
        {
            "titleManifest": str(title_manifest_path) if title_manifest_path else None,
            "expectedTitle": expected_title,
            "openingTitleText": opening_title_text,
            "openingSegmentCount": len(opening_segments),
            "forbiddenTerms": forbidden_terms,
            "forbiddenHits": forbidden_hits,
            "openingSubtitles": [item.get("subtitle") for item in opening_segments],
        },
    )

    visual_failures = visual_audio_audit.get("failures") or []
    title_ocr = visual_audio_audit.get("titleOcr") or {}
    forbidden_ocr_hits = [
        failure
        for failure in visual_failures
        if "Forbidden title" in str(failure) or "Forbidden title/opening text" in str(failure)
    ]
    add(
        "Visual/audio audit has clean-title evidence and no forbidden title OCR hits",
        visual_audio_audit.get("status") == "passed" and not forbidden_ocr_hits,
        {
            "visualAudioAuditStatus": visual_audio_audit.get("status"),
            "titleOcrMode": title_ocr.get("mode"),
            "titleOcrExpectedFound": title_ocr.get("expectedTitleFound"),
            "warnings": visual_audio_audit.get("warnings") or [],
            "forbiddenOcrHits": forbidden_ocr_hits,
        },
        warning=bool(visual_audio_audit.get("warnings")),
    )

    frame_reports: list[dict[str, Any]] = []
    frame_paths: list[Path] = []
    for point in points:
        second = float(point["second"])
        safe_name = f"{point['id']}_{second:09.3f}".replace(".", "_")
        frame_path = frames_dir / f"{safe_name}.jpg"
        extract_jpeg(video, second, frame_path)
        frame_paths.append(frame_path)
        metrics = frame_metrics(video, second)
        overlaps = [clip_summary(clip) for clip in overlapping_clips(blueprint, second)]
        frame_reports.append({**point, "metrics": metrics, "overlappingClips": overlaps})
    contact_sheet = make_contact_sheet(frame_paths, output_dir / "contact_sheet.jpg")
    pillarbox_hits = [item for item in frame_reports if (item.get("metrics") or {}).get("pillarboxSuspected")]
    add(
        "User feedback timestamps and title moments have no portrait/pillarbox regression",
        not pillarbox_hits,
        {"points": frame_reports, "contactSheet": contact_sheet},
    )

    audio_windows = [volume_window(video, float(point["second"]), args.audio_window_seconds) for point in points]
    quiet_windows = []
    for item in audio_windows:
        mean_volume = item.get("meanVolumeDb")
        max_volume = item.get("maxVolumeDb")
        if mean_volume is None:
            quiet_windows.append(item)
            continue
        mean_too_low = float(mean_volume) < args.min_audio_mean_db
        peak_too_low = max_volume is None or float(max_volume) < args.min_audio_peak_db
        if mean_too_low and peak_too_low:
            quiet_windows.append(item)
    a1_count = track_count(resolve_audit, "audio", 1)
    a2_count = track_count(resolve_audit, "audio", 2)
    a3_count = track_count(resolve_audit, "audio", 3)
    audio_plan = blueprint.get("audioPlan") or {}
    source_audio = audio_plan.get("sourceAudio") or {}
    scenic_flags = scenic_source_audio_flags(blueprint)
    bgm_tracks = bgm_manifest.get("tracks") if isinstance(bgm_manifest.get("tracks"), list) else []
    bad_bgm_tracks = [
        track
        for track in bgm_tracks
        if not isinstance(track, dict)
        or not Path(str(track.get("path") or "")).expanduser().exists()
        or not str(track.get("license") or "").startswith(("http://", "https://"))
    ]
    add(
        "BGM-only mix is audible at feedback/title moments and no camera or voiceover audio is on Resolve",
        not quiet_windows
        and str(audio_plan.get("mode") or "").lower().find("bgm") >= 0
        and str(audio_plan.get("mode") or "").lower().find("no_camera_voice") >= 0
        and str(source_audio.get("status") or "").lower().find("disabled") >= 0
        and (a1_count in {0, None})
        and (a2_count in {0, None})
        and (a3_count or 0) > 0
        and bool(bgm_manifest)
        and not bad_bgm_tracks
        and not scenic_flags,
        {
            "audioPlanMode": audio_plan.get("mode"),
            "sourceAudioPolicy": source_audio,
            "resolveAudioTrackCounts": {"A1": a1_count, "A2": a2_count, "A3": a3_count},
            "bgmManifest": str(bgm_manifest_path) if bgm_manifest_path else None,
            "bgmManifestMode": bgm_manifest.get("mode"),
            "bgmTrackCount": len(bgm_tracks),
            "badBgmTracks": bad_bgm_tracks[:10],
            "audioWindows": audio_windows,
            "quietWindows": quiet_windows,
            "scenicSourceAudioFlags": scenic_flags[:20],
        },
    )

    subtitle_policy = subtitle_manifest.get("subtitleTitlePolicy") or {}
    rendered_cues = int(subtitle_manifest.get("renderedCueCount") or subtitle_manifest.get("selectedCueCount") or 0)
    original_cues = int(subtitle_manifest.get("cueCount") or subtitle_policy.get("originalCueCount") or rendered_cues)
    add(
        "Visible subtitle overlay is dense and intentionally suppressed during title zones",
        subtitle_manifest.get("status") == "passed"
        and rendered_cues >= args.min_rendered_subtitles
        and original_cues >= args.min_original_subtitles
        and str(subtitle_policy.get("mode") or "").lower() == "avoid_title_zones"
        and (track_count(resolve_audit, "video", 3) or 0) >= min(rendered_cues, args.min_rendered_subtitles),
        {
            "subtitleManifest": str(subtitle_manifest_path) if subtitle_manifest_path else None,
            "status": subtitle_manifest.get("status"),
            "originalCueCount": original_cues,
            "renderedCueCount": rendered_cues,
            "subtitleTitlePolicy": subtitle_policy,
            "resolveV3Items": track_count(resolve_audit, "video", 3),
        },
    )

    blocked = [row for row in checks if row["status"] == "blocked"]
    warnings = [row for row in checks if row["status"] == "warning"]
    status = "blocked" if blocked else ("passed_with_warnings" if warnings else "passed")
    report = {
        "status": status,
        "packageDir": str(package_dir),
        "video": str(video),
        "feedbackTimestamps": points,
        "checks": checks,
        "blockers": [row["requirement"] for row in blocked],
        "warnings": [row["requirement"] for row in warnings],
        "contactSheet": contact_sheet,
    }
    write_json(output_dir / "feedback_regression_audit.json", report)
    md = [
        "# Feedback Regression Audit",
        "",
        f"Status: `{status}`",
        f"Package: `{package_dir}`",
        f"Video: `{video}`",
        "",
        "## Checks",
    ]
    for row in checks:
        md.append(f"- `{row['status']}` {row['requirement']}")
    if contact_sheet:
        md.extend(["", f"Contact sheet: `{contact_sheet}`"])
    (output_dir / "feedback_regression_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--video")
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--feedback-timestamps",
        help="Comma-separated labels and times, e.g. opening_title=0,reported_vertical_clip=7:04.",
    )
    parser.add_argument("--include-title-points", action="store_true")
    parser.add_argument("--title-manifest")
    parser.add_argument("--subtitle-manifest")
    parser.add_argument("--bgm-manifest")
    parser.add_argument("--audio-window-seconds", type=float, default=8.0)
    parser.add_argument("--min-audio-mean-db", type=float, default=-45.0)
    parser.add_argument("--min-audio-peak-db", type=float, default=-35.0)
    parser.add_argument("--min-rendered-subtitles", type=int, default=80)
    parser.add_argument("--min-original-subtitles", type=int, default=90)
    args = parser.parse_args()
    try:
        report = audit(args)
    except Exception as exc:
        print(f"audit_feedback_regressions failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
