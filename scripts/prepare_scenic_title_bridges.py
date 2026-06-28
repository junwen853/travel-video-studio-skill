#!/usr/bin/env python3
"""Generate clean scenic title bridge clips and optionally update a Resolve blueprint."""

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


TITLE_ROLES = {
    "opening_city_aerial_title",
    "chapter_title_bridge",
    "place_card",
    "title_card",
    "ending_city_aerial_title",
}

DEFAULT_FONTS = [
    "/System/Library/Fonts/Supplemental/Didot.ttc",
    "/System/Library/Fonts/Supplemental/Bodoni 72.ttc",
    "/System/Library/Fonts/Avenir Next Condensed.ttc",
    "/System/Library/Fonts/Avenir Next.ttc",
    "/System/Library/Fonts/Optima.ttc",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_font(preferred: str | None = None) -> str | None:
    candidates = [preferred] if preferred else []
    candidates.extend(DEFAULT_FONTS)
    for item in candidates:
        if item and Path(item).exists():
            return item
    return None


def load_font(path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path and Path(path).exists():
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), text, font=font)


def draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    anchor: str = "la",
    shadow_alpha: int = 130,
) -> None:
    x, y = xy
    draw.text((x + 5, y + 6), text, font=font, fill=(0, 0, 0, shadow_alpha), anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def safe_id(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value.lower() or fallback


def clean_title_text(value: str, *, max_chars: int = 28) -> str:
    text = " ".join(value.strip().split())
    text = text.replace("→", "->")
    text = re.sub(r"\s*-\s*>\s*", " -> ", text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def title_clip_duration(clip: dict[str, Any]) -> float:
    try:
        start = float(clip.get("timelineStartSeconds"))
        end = float(clip.get("timelineEndSeconds"))
        return max(0.0, end - start)
    except (TypeError, ValueError):
        try:
            return max(0.0, float(clip.get("durationSeconds")))
        except (TypeError, ValueError):
            return 4.0


def find_manifest(package_dir: Path, explicit: str | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        [
            package_dir / "v12_visual_manifest.json",
            package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json",
            package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def manifest_segments(path: Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    data = load_json(path)
    segments = data.get("segments", []) if isinstance(data, dict) else []
    return [item for item in segments if isinstance(item, dict)]


def match_manifest_segment(segments: list[dict[str, Any]], clip: dict[str, Any]) -> dict[str, Any] | None:
    try:
        start = float(clip.get("timelineStartSeconds"))
    except (TypeError, ValueError):
        return None
    best: tuple[float, dict[str, Any]] | None = None
    for segment in segments:
        try:
            seg_start = float(segment.get("timeline_start", segment.get("timelineStartSeconds")))
        except (TypeError, ValueError):
            continue
        distance = abs(seg_start - start)
        if distance <= 0.35 and (best is None or distance < best[0]):
            best = (distance, segment)
    return best[1] if best else None


def find_companion_manifest(video: Path) -> dict[str, Any] | None:
    candidates = [
        video.with_suffix(".manifest.json"),
        video.parent / f"{video.stem}.manifest.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                data = load_json(candidate)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(data, dict):
                return data
    return None


def choose_source(clip: dict[str, Any], segment: dict[str, Any] | None) -> tuple[Path, float]:
    if segment and segment.get("source"):
        source = Path(str(segment["source"])).expanduser()
        source_start = float(segment.get("source_start") or segment.get("sourceStartSeconds") or 0.0)
        if source.exists():
            return source, source_start
    clip_source = Path(str(clip.get("sourcePath") or "")).expanduser()
    companion = find_companion_manifest(clip_source)
    if companion and companion.get("aerial"):
        aerial = Path(str(companion["aerial"])).expanduser()
        if aerial.exists():
            return aerial, 0.0
    return clip_source, float(clip.get("sourceStartSeconds") or 0.0)


def clip_mode(clip: dict[str, Any], segment: dict[str, Any] | None) -> str:
    if segment and segment.get("mode"):
        return str(segment["mode"]).lower()
    role = str(clip.get("role") or "")
    if "opening" in role:
        return "opening"
    if "ending" in role:
        return "ending"
    return "chapter"


def clip_title(clip: dict[str, Any], segment: dict[str, Any] | None, mode: str, args: argparse.Namespace) -> str:
    raw = (
        clip.get("titleText")
        or clip.get("cityTitle")
        or clip.get("place")
        or (segment or {}).get("title")
        or "TRAVEL"
    )
    title = clean_title_text(str(raw), max_chars=args.max_title_chars)
    if mode == "opening" and args.opening_title:
        title = args.opening_title.strip().upper()
    if mode == "opening" and "/" in title:
        title = title.split("/")[0].strip()
    return title.upper()


def clip_subtitle(clip: dict[str, Any], segment: dict[str, Any] | None, mode: str, args: argparse.Namespace) -> str:
    if mode == "opening" and not args.allow_opening_subtitle:
        return ""
    subtitle = str((segment or {}).get("subtitle") or clip.get("subtitle") or "").strip()
    forbidden = [item.strip().upper() for item in args.forbidden_text.split(",") if item.strip()]
    if any(term and term in subtitle.upper() for term in forbidden):
        return ""
    if len(subtitle) > args.max_subtitle_chars:
        subtitle = subtitle[: args.max_subtitle_chars].rstrip()
    return subtitle


def clip_eyebrow(clip: dict[str, Any], segment: dict[str, Any] | None, mode: str) -> str:
    if mode == "opening":
        return ""
    return str((segment or {}).get("eyebrow") or "").strip().upper()


def add_readability_gradient(image: Image.Image, mode: str) -> None:
    width, height = image.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if mode == "opening":
        center_y = height * 0.50
        radius = height * 0.48
        for y in range(height):
            strength = max(0.0, 1.0 - abs(y - center_y) / radius)
            alpha = int(72 * (strength**1.7))
            if alpha:
                draw.line((0, y, width, y), fill=(0, 0, 0, alpha))
    else:
        for x in range(int(width * 0.62)):
            strength = 1.0 - x / max(1, width * 0.62)
            alpha = int(112 * (strength**1.8))
            if alpha:
                draw.line((x, 0, x, height), fill=(0, 0, 0, alpha))
        for y in range(height):
            strength = max(0.0, 1.0 - abs(y - height * 0.62) / (height * 0.52))
            alpha = int(46 * (strength**1.6))
            if alpha:
                draw.line((0, y, width, y), fill=(0, 0, 0, alpha))
    image.alpha_composite(overlay)


def draw_opening(draw: ImageDraw.ImageDraw, width: int, height: int, title: str, font_path: str | None) -> None:
    title_font = load_font(font_path, max(140, width // 11))
    draw_text_with_shadow(
        draw,
        (width / 2, height * 0.47),
        title,
        title_font,
        (250, 247, 238, 242),
        anchor="mm",
        shadow_alpha=110,
    )


def draw_chapter(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    title: str,
    subtitle: str,
    eyebrow: str,
    font_path: str | None,
) -> None:
    title_font = load_font("/System/Library/Fonts/Avenir Next Condensed.ttc", max(104, width // 19))
    small_font = load_font("/System/Library/Fonts/Avenir Next Condensed.ttc", max(34, width // 92))
    subtitle_font = load_font(find_font("/System/Library/Fonts/PingFang.ttc"), max(36, width // 90))
    x = int(width * 0.092)
    title_y = int(height * 0.64)
    if eyebrow:
        draw_text_with_shadow(draw, (x, title_y - int(height * 0.10)), eyebrow, small_font, (224, 190, 98, 235))
    draw_text_with_shadow(draw, (x, title_y), title, title_font, (252, 249, 239, 250))
    title_box = text_bbox(draw, title, title_font)
    line_y = title_y + (title_box[3] - title_box[1]) + 8
    draw.line((x, line_y, x + min(width * 0.30, max(width * 0.14, len(title) * width * 0.012)), line_y), fill=(222, 184, 90, 210), width=4)
    if subtitle:
        draw_text_with_shadow(draw, (x, line_y + 22), subtitle, subtitle_font, (240, 238, 231, 230), shadow_alpha=120)


def make_overlay(
    path: Path,
    mode: str,
    title: str,
    subtitle: str,
    eyebrow: str,
    width: int,
    height: int,
    font_path: str | None,
) -> None:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    add_readability_gradient(image, mode)
    draw = ImageDraw.Draw(image)
    if mode == "opening":
        draw_opening(draw, width, height, title, font_path)
    elif mode == "ending":
        draw_opening(draw, width, height, title, font_path)
        if subtitle:
            subtitle_font = load_font("/System/Library/Fonts/Avenir Next Condensed.ttc", max(34, width // 96))
            draw_text_with_shadow(draw, (width / 2, height * 0.60), subtitle.upper(), subtitle_font, (238, 230, 206, 220), anchor="mm")
    else:
        draw_chapter(draw, width, height, title, subtitle, eyebrow, font_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def render_bridge(
    source: Path,
    source_start: float,
    overlay: Path,
    output: Path,
    duration: float,
    args: argparse.Namespace,
) -> tuple[int, str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return 127, "ffmpeg not found"
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_complex = (
        f"[0:v]scale={args.width}:{args.height}:force_original_aspect_ratio=increase,"
        f"crop={args.width}:{args.height},format=rgba[v0];"
        "[v0][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    )
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-ss",
        f"{max(0.0, source_start):.3f}",
        "-stream_loop",
        "-1",
        "-i",
        str(source),
        "-loop",
        "1",
        "-i",
        str(overlay),
        "-t",
        f"{duration:.3f}",
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-an",
        "-r",
        args.fps,
        "-c:v",
        "libx264",
        "-preset",
        args.preset,
        "-b:v",
        args.bitrate,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode, log[-4000:]


def extract_preview(video: Path, second: float, output: Path, args: argparse.Namespace) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(0.0, second):.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
            "-q:v",
            "2",
            str(output),
        ],
        check=False,
    )


def make_contact_sheet(frame_paths: list[Path], output: Path) -> str | None:
    if not frame_paths:
        return None
    images = [Image.open(path).convert("RGB") for path in frame_paths if path.exists()]
    if not images:
        return None
    width, height = 640, 394
    cols = min(4, len(images))
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width, rows * height), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (image, path) in enumerate(zip(images, frame_paths)):
        x = (idx % cols) * width
        y = (idx // cols) * height
        sheet.paste(image, (x, y))
        draw.text((x + 10, y + 366), path.stem, fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    return str(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare clean scenic title bridge clips for a Resolve package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint", help="Defaults to <package>/resolve_timeline_blueprint.json")
    parser.add_argument("--visual-manifest", help="Visual manifest with raw scenic sources and title metadata.")
    parser.add_argument("--output-subdir", default="clean_scenic_title_bridges")
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--fps", default="60000/1001")
    parser.add_argument("--bitrate", default="80000000")
    parser.add_argument("--preset", default="slow")
    parser.add_argument("--font")
    parser.add_argument("--opening-title", default="")
    parser.add_argument("--allow-opening-subtitle", action="store_true")
    parser.add_argument("--max-title-chars", type=int, default=28)
    parser.add_argument("--max-subtitle-chars", type=int, default=34)
    parser.add_argument("--forbidden-text", default="TOKYO / OSAKA,JAPAN 2025,OSAKA - TOKYO - OSAKA,OSAKA -> TOKYO -> OSAKA")
    parser.add_argument("--update-blueprint", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    blueprint_path = Path(args.blueprint).expanduser().resolve() if args.blueprint else package_dir / "resolve_timeline_blueprint.json"
    blueprint = load_json(blueprint_path)
    manifest_path = find_manifest(package_dir, args.visual_manifest)
    segments = manifest_segments(manifest_path)
    output_dir = package_dir / args.output_subdir
    overlay_dir = output_dir / "overlays"
    segment_dir = output_dir / "segments"
    preview_dir = output_dir / "previews"
    font_path = find_font(args.font)

    clips = blueprint.get("clips", [])
    generated: list[dict[str, Any]] = []
    preview_frames: list[Path] = []
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict) or str(clip.get("role") or "") not in TITLE_ROLES:
            continue
        role = str(clip.get("role"))
        if role == "title_card" and str(clip.get("sourcePath") or "").endswith((".srt", ".ass")):
            continue
        matched = match_manifest_segment(segments, clip)
        mode = clip_mode(clip, matched)
        duration = title_clip_duration(clip)
        if duration <= 0:
            continue
        title = clip_title(clip, matched, mode, args)
        subtitle = clip_subtitle(clip, matched, mode, args)
        eyebrow = clip_eyebrow(clip, matched, mode)
        source, source_start = choose_source(clip, matched)
        clip_id = safe_id(str((matched or {}).get("id") or f"{mode}_{index:02d}_{title}"), f"title_{index:02d}")
        overlay = overlay_dir / f"{clip_id}.png"
        output = segment_dir / f"{clip_id}.mp4"
        if not source.exists():
            generated.append(
                {
                    "id": clip_id,
                    "status": "missing_source",
                    "role": role,
                    "source": str(source),
                    "timelineStartSeconds": clip.get("timelineStartSeconds"),
                }
            )
            continue
        make_overlay(overlay, mode, title, subtitle, eyebrow, args.width, args.height, font_path)
        return_code, log = render_bridge(source, source_start, overlay, output, duration, args)
        status = "ready" if return_code == 0 and output.exists() else "failed"
        preview_start = preview_dir / f"{clip_id}_start.jpg"
        preview_mid = preview_dir / f"{clip_id}_mid.jpg"
        if status == "ready":
            extract_preview(output, 0.0, preview_start, args)
            extract_preview(output, min(2.0, duration / 2.0), preview_mid, args)
            preview_frames.extend([preview_start, preview_mid])
        if args.update_blueprint and status == "ready":
            clip["sourcePath"] = str(output)
            clip["sourceStartSeconds"] = 0.0
            clip["sourceEndSeconds"] = round(duration, 3)
            clip["timelineEndSeconds"] = round(float(clip.get("timelineStartSeconds") or 0.0) + duration, 3)
            clip["mediaType"] = 1
            clip["includeSourceAudio"] = False
            clip["titleText"] = title
            clip["subtitle"] = subtitle
            clip["cleanTitleBridgePolicy"] = {
                "status": "applied",
                "globalRouteLabel": "forbidden",
                "subtitleOverlayDuringTitleZones": "forbidden",
                "source": str(source),
                "sourceStartSeconds": source_start,
            }
        generated.append(
            {
                "id": clip_id,
                "status": status,
                "role": role,
                "mode": mode,
                "title": title,
                "subtitle": subtitle,
                "eyebrow": eyebrow,
                "source": str(source),
                "sourceStartSeconds": source_start,
                "durationSeconds": round(duration, 3),
                "timelineStartSeconds": clip.get("timelineStartSeconds"),
                "overlay": str(overlay),
                "segment": str(output),
                "ffmpegReturnCode": return_code,
                "ffmpegLog": log,
                "forbiddenVisibleText": [item.strip() for item in args.forbidden_text.split(",") if item.strip()],
            }
        )

    if args.update_blueprint:
        blueprint["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        blueprint["scenicTitleBridgePolicy"] = {
            "status": "applied",
            "script": "prepare_scenic_title_bridges.py",
            "manifest": str(output_dir / "clean_scenic_title_bridges_manifest.json"),
            "globalRouteLabel": "forbidden",
            "subtitleOverlayDuringTitleZones": "forbidden",
        }
        write_json(blueprint_path, blueprint)

    contact_sheet = make_contact_sheet(preview_frames, output_dir / "contact_sheet.jpg")
    failures = [item for item in generated if item.get("status") != "ready"]
    visual_segments = [
        {
            "id": item.get("id"),
            "mode": item.get("mode"),
            "timeline_start": item.get("timelineStartSeconds"),
            "duration": item.get("durationSeconds"),
            "source": item.get("source"),
            "source_start": item.get("sourceStartSeconds"),
            "title": item.get("title"),
            "subtitle": item.get("subtitle"),
            "eyebrow": item.get("eyebrow"),
            "segment": item.get("segment"),
            "overlay": item.get("overlay"),
            "policy": "clean scenic title bridge; no global route label or subtitle overlay in title zone",
        }
        for item in generated
        if item.get("status") == "ready"
    ]
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked" if failures else "passed",
        "version": "clean_scenic_title_bridges",
        "openingTitlePolicy": "single clean city title only; no duplicate title, route/date label, subtitle overlay, or secondary city behind the hero title",
        "cityTitle": args.opening_title or None,
        "expectedOpeningTitle": args.opening_title or None,
        "packageDir": str(package_dir),
        "blueprint": str(blueprint_path),
        "visualManifest": str(manifest_path) if manifest_path else None,
        "updatedBlueprint": bool(args.update_blueprint),
        "outputDir": str(output_dir),
        "font": font_path,
        "forbiddenVisibleText": [item.strip() for item in args.forbidden_text.split(",") if item.strip()],
        "forbiddenOpeningText": [item.strip() for item in args.forbidden_text.split(",") if item.strip()],
        "segments": visual_segments,
        "clips": generated,
        "contactSheet": contact_sheet,
        "failures": failures,
    }
    write_json(output_dir / "clean_scenic_title_bridges_manifest.json", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "generated": len(generated), "failures": len(failures)}, ensure_ascii=False, indent=2))
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
