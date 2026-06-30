#!/usr/bin/env python3
"""Create a transparent subtitle overlay video for DaVinci Resolve timelines."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


SRT_TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def srt_seconds(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    seconds -= hours * 3600
    minutes = int(seconds // 60)
    seconds -= minutes * 60
    whole = int(seconds)
    centis = int(round((seconds - whole) * 100))
    if centis >= 100:
        whole += 1
        centis -= 100
    return f"{hours}:{minutes:02d}:{whole:02d}.{centis:02d}"


def parse_srt(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
    cues: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        time_index = next((idx for idx, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        match = SRT_TIME_RE.search(lines[time_index])
        if not match:
            continue
        cue_text = "\n".join(lines[time_index + 1 :]).strip()
        if not cue_text:
            continue
        start = srt_seconds(match.group("start"))
        end = srt_seconds(match.group("end"))
        if end <= start:
            continue
        cues.append({"start": start, "end": end, "text": cue_text})
    return cues


TITLE_ZONE_ROLES = {
    "opening_city_aerial_title",
    "ending_city_aerial_title",
    "chapter_title_bridge",
    "place_card",
    "title_card",
}


def title_avoid_zones(blueprint: dict[str, Any], padding: float) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for clip in blueprint.get("clips", []):
        if not isinstance(clip, dict):
            continue
        role = str(clip.get("role") or "")
        if role not in TITLE_ZONE_ROLES:
            continue
        try:
            start = float(clip.get("timelineStartSeconds"))
            end = float(
                clip.get("timelineEndSeconds")
                if clip.get("timelineEndSeconds") is not None
                else start + float(clip.get("durationSeconds"))
            )
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        zones.append(
            {
                "role": role,
                "start": round(max(0.0, start - padding), 3),
                "end": round(end + padding, 3),
                "title": clip.get("titleText") or clip.get("cityTitle") or clip.get("place"),
            }
        )
    zones.sort(key=lambda item: (float(item["start"]), float(item["end"])))
    merged: list[dict[str, Any]] = []
    for zone in zones:
        if not merged or float(zone["start"]) > float(merged[-1]["end"]):
            merged.append(zone)
            continue
        merged[-1]["end"] = round(max(float(merged[-1]["end"]), float(zone["end"])), 3)
        merged[-1]["role"] = f"{merged[-1]['role']}+{zone['role']}"
        titles = [str(merged[-1].get("title") or ""), str(zone.get("title") or "")]
        merged[-1]["title"] = " / ".join(part for part in titles if part)
    return merged


def subtract_zones(
    cues: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    min_duration: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not zones:
        return cues, {"mode": "none", "zones": [], "droppedCueCount": 0, "splitCueCount": 0}
    kept: list[dict[str, Any]] = []
    dropped = 0
    split = 0
    for cue in cues:
        pieces = [(float(cue["start"]), float(cue["end"]))]
        for zone in zones:
            z_start = float(zone["start"])
            z_end = float(zone["end"])
            next_pieces: list[tuple[float, float]] = []
            for start, end in pieces:
                if end <= z_start or start >= z_end:
                    next_pieces.append((start, end))
                    continue
                if start < z_start:
                    next_pieces.append((start, min(end, z_start)))
                if end > z_end:
                    next_pieces.append((max(start, z_end), end))
            pieces = next_pieces
            if not pieces:
                break
        valid_pieces = [(start, end) for start, end in pieces if end - start >= min_duration]
        if not valid_pieces:
            dropped += 1
            continue
        if len(valid_pieces) > 1:
            split += 1
        for start, end in valid_pieces:
            item = dict(cue)
            item["start"] = round(start, 3)
            item["end"] = round(end, 3)
            kept.append(item)
    return kept, {
        "mode": "avoid_title_zones",
        "zones": zones,
        "originalCueCount": len(cues),
        "keptCueCount": len(kept),
        "droppedCueCount": dropped,
        "splitCueCount": split,
        "minKeptCueDurationSeconds": min_duration,
    }


def ass_escape(text: str) -> str:
    text = text.replace("{", r"\{").replace("}", r"\}")
    text = text.replace("\n", r"\N")
    return text


def write_ass(path: Path, cues: list[dict[str, Any]], args: argparse.Namespace) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {args.width}
PlayResY: {args.height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{args.font},{args.font_size},&H00FFFFFF,&H000000FF,&H90000000,&H70000000,-1,0,0,0,100,100,0,0,1,{args.outline},{args.shadow},2,{args.margin_lr},{args.margin_lr},{args.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for cue in cues:
        lines.append(
            f"Dialogue: 0,{ass_time(float(cue['start']))},{ass_time(float(cue['end']))},"
            f"Default,,0,0,0,,{ass_escape(str(cue['text']))}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def ffmpeg_filter_path(path: Path) -> str:
    raw = str(path)
    raw = raw.replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")
    return f"filename='{raw}'"


def find_font_file(args: argparse.Namespace) -> Path | None:
    if args.font_file:
        path = Path(args.font_file).expanduser()
        return path if path.exists() else None
    candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def load_font(args: argparse.Namespace) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_file = find_font_file(args)
    if font_file:
        return ImageFont.truetype(str(font_file), args.font_size)
    return ImageFont.load_default(args.font_size)


def wrap_line(line: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    line = line.strip()
    if not line:
        return []
    units = line.split(" ") if " " in line else list(line)
    rows: list[str] = []
    current = ""
    for unit in units:
        separator = " " if " " in line and current else ""
        candidate = f"{current}{separator}{unit}" if current else unit
        bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=0)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
            continue
        rows.append(current)
        current = unit
    if current:
        rows.append(current)
    return rows


def draw_caption_png(path: Path, cue_text: str, args: argparse.Namespace, font: ImageFont.ImageFont) -> None:
    image = Image.new("RGBA", (args.width, args.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    max_width = args.width - 2 * args.margin_lr
    wrapped: list[str] = []
    for raw_line in cue_text.replace("\\N", "\n").splitlines():
        wrapped.extend(wrap_line(raw_line, font, draw, max_width))
    if len(wrapped) > args.max_lines:
        wrapped = wrapped[: args.max_lines]
    text = "\n".join(wrapped)
    spacing = max(8, args.font_size // 5)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, stroke_width=args.outline)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (args.width - text_w) / 2 - bbox[0]
    y = args.height - args.margin_v - text_h - bbox[1]
    pad_x = args.font_size // 2
    pad_y = args.font_size // 3
    box = (
        int((args.width - text_w) / 2 - pad_x),
        int(args.height - args.margin_v - text_h - pad_y),
        int((args.width + text_w) / 2 + pad_x),
        int(args.height - args.margin_v + pad_y),
    )
    draw.rounded_rectangle(box, radius=max(12, args.font_size // 3), fill=(0, 0, 0, args.backdrop_alpha))
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        spacing=spacing,
        align="center",
        stroke_width=args.outline,
        stroke_fill=(0, 0, 0, 220),
    )
    image.save(path)


def render_png_overlay(output_dir: Path, output_path: Path, cues: list[dict[str, Any]], duration: float, args: argparse.Namespace) -> tuple[Path, Path, list[str]]:
    frames_dir = output_dir / ("sample_frames" if args.sample_duration_seconds else "frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    font = load_font(args)
    cue_frames: list[tuple[Path, float, float]] = []
    for idx, cue in enumerate(cues, start=1):
        start = max(0.0, float(cue["start"]))
        end = min(duration, float(cue["end"]))
        if end <= 0 or start >= duration or end <= start:
            continue
        png = frames_dir / f"cue_{idx:04d}.png"
        draw_caption_png(png, str(cue["text"]), args, font)
        cue_frames.append((png, start, end))

    filter_path = output_dir / ("overlay_filter_sample.txt" if args.sample_duration_seconds else "overlay_filter.txt")
    filter_lines: list[str] = ["[0:v]format=rgba[base]"]
    last = "base"
    for input_index, (_png, start, end) in enumerate(cue_frames, start=1):
        out = f"v{input_index}"
        filter_lines.append(
            f"[{last}][{input_index}:v]overlay=0:0:format=auto:eof_action=pass:"
            f"enable='between(t,{start:.3f},{end:.3f})'[{out}]"
        )
        last = out
    if not cue_frames:
        filter_lines.append("[base]copy[vout]")
        last = "vout"
    filter_path.write_text(";\n".join(filter_lines) + "\n", encoding="utf-8")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found.")
    codec_args = (
        ["-c:v", "qtrle", "-pix_fmt", "argb"]
        if args.codec == "qtrle"
        else ["-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le"]
    )
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black@0.0:s={args.width}x{args.height}:r={args.fps}:d={duration:.3f}",
    ]
    for png, _start, _end in cue_frames:
        cmd.extend(["-loop", "1", "-i", str(png)])
    cmd.extend(
        [
        "-filter_complex_script",
        str(filter_path),
        "-map",
        f"[{last}]",
        "-r",
        args.fps,
        *codec_args,
        "-an",
        "-t",
        f"{duration:.3f}",
        str(output_path),
        ]
    )
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit((result.stderr or result.stdout).strip())
    return filter_path, frames_dir, cmd


def render_segment_overlays(output_dir: Path, cues: list[dict[str, Any]], duration: float, args: argparse.Namespace) -> tuple[Path, Path, list[dict[str, Any]]]:
    frames_dir = output_dir / ("sample_segment_frames" if args.sample_duration_seconds else "segment_frames")
    segments_dir = output_dir / ("sample_segments" if args.sample_duration_seconds else "segments")
    frames_dir.mkdir(parents=True, exist_ok=True)
    segments_dir.mkdir(parents=True, exist_ok=True)
    font = load_font(args)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found.")
    codec_args = (
        ["-c:v", "qtrle", "-pix_fmt", "argb"]
        if args.codec == "qtrle"
        else ["-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le"]
    )
    specs: list[dict[str, Any]] = []
    for idx, cue in enumerate(cues, start=1):
        start = max(0.0, float(cue["start"]))
        end = min(duration, float(cue["end"]))
        cue_duration = end - start
        if end <= 0 or start >= duration or cue_duration <= 0:
            continue
        png = frames_dir / f"cue_{idx:04d}.png"
        mov = segments_dir / f"subtitle_cue_{idx:04d}.mov"
        draw_caption_png(png, str(cue["text"]), args, font)
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-loop",
            "1",
            "-i",
            str(png),
            "-t",
            f"{cue_duration:.3f}",
            "-r",
            args.fps,
            *codec_args,
            "-an",
            str(mov),
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit((result.stderr or result.stdout).strip())
        specs.append(
            {
                "cueIndex": idx,
                "path": str(mov),
                "png": str(png),
                "timelineStart": round(start, 3),
                "duration": round(cue_duration, 3),
                "sourceEnd": round(cue_duration, 3),
                "text": str(cue["text"]),
                "command": cmd,
            }
        )
    manifest_path = output_dir / ("segment_overlay_sample_manifest.json" if args.sample_duration_seconds else "segment_overlay_manifest.json")
    return manifest_path, frames_dir, specs


def infer_duration(package_dir: Path, blueprint: dict[str, Any], cues: list[dict[str, Any]]) -> float:
    for value in (
        blueprint.get("targetDurationSeconds"),
        blueprint.get("actualVideoCoverageSeconds"),
        (blueprint.get("longFormCoverage") or {}).get("finalVideoCoverageSeconds")
        if isinstance(blueprint.get("longFormCoverage"), dict)
        else None,
    ):
        try:
            duration = float(value)
        except (TypeError, ValueError):
            continue
        if duration > 0:
            return duration
    render_report = package_dir / "render_delivery_verification.json"
    if render_report.exists():
        try:
            data = load_json(render_report)
            duration = float((data.get("probe") or {}).get("durationSeconds") or data.get("durationSeconds") or 0)
            if duration > 0:
                return duration
        except Exception:  # noqa: BLE001
            pass
    if cues:
        return max(float(cue["end"]) for cue in cues)
    return 0.0


def find_srt(package_dir: Path, blueprint: dict[str, Any], explicit: str | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    if assets.get("subtitles"):
        candidates.append(Path(str(assets["subtitles"])).expanduser())
    candidates.extend(sorted(package_dir.glob("subtitles*_dense.srt")))
    candidates.extend([package_dir / "subtitles.srt", package_dir / "subtitles_v4_dense.srt"])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def update_blueprint(path: Path, overlay_specs: list[dict[str, Any]], args: argparse.Namespace, cue_count: int) -> dict[str, Any]:
    blueprint = load_json(path)
    tracks = blueprint.setdefault("tracks", [])
    has_track = any(
        isinstance(row, dict)
        and row.get("type") == "video"
        and int(row.get("index") or 0) == int(args.track_index)
        for row in tracks
    )
    if not has_track:
        tracks.append({"type": "video", "index": int(args.track_index), "name": "V3 Burned subtitle overlay"})
    else:
        for row in tracks:
            if isinstance(row, dict) and row.get("type") == "video" and int(row.get("index") or 0) == int(args.track_index):
                row["name"] = row.get("name") or "V3 Burned subtitle overlay"

    clips = blueprint.setdefault("clips", [])
    clips[:] = [
        clip
        for clip in clips
        if not (
            isinstance(clip, dict)
            and (
                clip.get("role") == "subtitle_overlay_video"
                or str(clip.get("sourcePath") or "") in {str(spec.get("path")) for spec in overlay_specs}
            )
        )
    ]
    for spec in overlay_specs:
        duration = float(spec.get("duration") or spec.get("sourceEnd") or 0)
        clips.append(
            {
                "role": "subtitle_overlay_video",
                "purpose": "transparent Chinese subtitle overlay for DaVinci render burn-in",
                "sourcePath": str(spec["path"]),
                "sourceStartSeconds": 0,
                "sourceEndSeconds": round(duration, 3),
                "timelineStartSeconds": round(float(spec.get("timelineStart") or 0), 3),
                "durationSeconds": round(duration, 3),
                "trackIndex": int(args.track_index),
                "mediaType": 1,
                "includeSourceAudio": False,
                "subtitleCueIndex": spec.get("cueIndex"),
                "subtitleCueCount": cue_count,
            }
        )
    blueprint["subtitleDeliveryPolicy"] = {
        "mode": "resolve_overlay_video",
        "status": "prepared",
        "overlayTrack": int(args.track_index),
        "overlayMode": args.mode,
        "overlayClipCount": len(overlay_specs),
        "overlayPath": str(overlay_specs[0].get("path")) if len(overlay_specs) == 1 else None,
        "overlayDirectory": str(Path(str(overlay_specs[0].get("path"))).parent) if overlay_specs else None,
        "cueCount": cue_count,
        "renderedCueCount": len(overlay_specs),
        "titleZoneSubtitlePolicy": getattr(args, "subtitle_title_policy", None),
        "nativeSubtitleImportNote": "Resolve 21 Python API can create subtitle tracks, but direct SRT ImportIntoTimeline returned False in local smoke testing; use overlay video or explicitly accept sidecar delivery.",
    }
    blueprint["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return blueprint


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a transparent subtitle overlay video and optionally inject it into a Resolve blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--srt", help="Subtitle SRT path. Defaults to blueprint/package subtitles.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to <package>/subtitle_overlay_assets.")
    parser.add_argument("--duration-seconds", type=float, help="Overlay duration. Defaults to blueprint/render/SRT duration.")
    parser.add_argument("--sample-duration-seconds", type=float, help="Render only the first N seconds for smoke tests.")
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--fps", default="60000/1001")
    parser.add_argument("--codec", choices=["qtrle", "prores4444"], default="qtrle")
    parser.add_argument("--mode", choices=["segments", "single"], default="segments", help="segments creates one short overlay clip per cue; single creates one full-duration overlay movie.")
    parser.add_argument("--font", default="Hiragino Sans")
    parser.add_argument("--font-file", help="TrueType/OpenType/TTC font file for Pillow rendering.")
    parser.add_argument("--font-size", type=int, default=66)
    parser.add_argument("--outline", type=int, default=4)
    parser.add_argument("--shadow", type=int, default=2)
    parser.add_argument("--margin-lr", type=int, default=180)
    parser.add_argument("--margin-v", type=int, default=170)
    parser.add_argument("--max-lines", type=int, default=2)
    parser.add_argument("--backdrop-alpha", type=int, default=95)
    parser.add_argument(
        "--allow-title-zone-subtitles",
        action="store_true",
        help="Allow subtitles during opening/chapter/ending title clips. Default suppresses them for clean titles.",
    )
    parser.add_argument("--title-zone-padding-seconds", type=float, default=0.25)
    parser.add_argument("--min-trimmed-cue-duration-seconds", type=float, default=0.75)
    parser.add_argument("--track-index", type=int, default=3)
    parser.add_argument("--update-blueprint", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    blueprint = load_json(blueprint_path) if blueprint_path.exists() else {}
    srt_path = find_srt(package_dir, blueprint, args.srt)
    if not srt_path:
        raise SystemExit("No SRT file found. Pass --srt or create package subtitles first.")
    cues = parse_srt(srt_path)
    if not cues:
        raise SystemExit(f"No subtitle cues parsed from {srt_path}")

    full_duration = float(args.duration_seconds or infer_duration(package_dir, blueprint, cues))
    duration = float(args.sample_duration_seconds or full_duration)
    if duration <= 0:
        raise SystemExit("Unable to infer overlay duration.")
    selected_cues = [cue for cue in cues if float(cue["start"]) < duration]
    for cue in selected_cues:
        cue["end"] = min(float(cue["end"]), duration)
    avoid_zones = [] if args.allow_title_zone_subtitles else title_avoid_zones(blueprint, args.title_zone_padding_seconds)
    selected_cues, subtitle_title_policy = subtract_zones(
        selected_cues,
        avoid_zones,
        args.min_trimmed_cue_duration_seconds,
    )
    args.subtitle_title_policy = subtitle_title_policy

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "subtitle_overlay_assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    ass_path = output_dir / ("subtitles_overlay_sample.ass" if args.sample_duration_seconds else "subtitles_overlay.ass")
    output_path = output_dir / ("subtitles_overlay_sample.mov" if args.sample_duration_seconds else "subtitles_overlay.mov")
    manifest_path = output_dir / ("subtitles_overlay_sample_manifest.json" if args.sample_duration_seconds else "subtitles_overlay_manifest.json")
    write_ass(ass_path, selected_cues, args)
    filter_path: Path | None = None
    cmd: list[str] | None = None
    overlay_specs: list[dict[str, Any]]
    if args.mode == "single":
        filter_path, frames_dir, cmd = render_png_overlay(output_dir, output_path, selected_cues, duration, args)
        overlay_specs = [{"path": str(output_path), "timelineStart": 0, "duration": duration, "sourceEnd": duration, "cueIndex": None}]
    else:
        manifest_path, frames_dir, overlay_specs = render_segment_overlays(output_dir, selected_cues, duration, args)

    updated_blueprint = None
    if args.update_blueprint and not args.sample_duration_seconds:
        updated_blueprint = update_blueprint(blueprint_path, overlay_specs, args, len(cues))

    manifest = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed",
        "packageDir": str(package_dir),
        "srt": str(srt_path),
        "ass": str(ass_path),
        "filterGraph": str(filter_path) if filter_path else None,
        "framesDir": str(frames_dir),
        "overlayVideo": str(output_path) if args.mode == "single" else None,
        "overlayVideos": [spec["path"] for spec in overlay_specs],
        "durationSeconds": round(duration, 3),
        "fullDurationSeconds": round(full_duration, 3),
        "cueCount": len(cues),
        "selectedCueCount": len(selected_cues),
        "renderedCueCount": len(overlay_specs),
        "subtitleTitlePolicy": subtitle_title_policy,
        "width": args.width,
        "height": args.height,
        "fps": args.fps,
        "font": args.font,
        "fontFile": str(find_font_file(args)) if find_font_file(args) else None,
        "fontSize": args.font_size,
        "backend": f"pillow_png_{args.mode}_{args.codec}",
        "updatedBlueprint": bool(updated_blueprint),
        "blueprint": str(blueprint_path) if updated_blueprint else None,
        "resolveTrack": f"V{args.track_index}",
        "command": cmd,
    }
    write_json(manifest_path, manifest)
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print("Subtitle overlay asset: passed")
        print(f"Overlay: {output_path}")
        print(f"Manifest: {manifest_path}")
        if updated_blueprint:
            print(f"Updated blueprint: {blueprint_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
