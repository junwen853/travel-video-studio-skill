#!/usr/bin/env python3
"""Render a city aerial/establishing title clip with clean typography."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FONTS = [
    "/System/Library/Fonts/Supplemental/Didot.ttc",
    "/System/Library/Fonts/Supplemental/Bodoni 72.ttc",
    "/System/Library/Fonts/Avenir Next Condensed.ttc",
    "/System/Library/Fonts/Avenir Next.ttc",
    "/System/Library/Fonts/Optima.ttc",
]


def find_font(preferred: str | None = None) -> str | None:
    candidates = [preferred] if preferred else []
    candidates.extend(DEFAULT_FONTS)
    for item in candidates:
        if item and Path(item).exists():
            return item
    return None


def load_font(path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, tracking: int) -> tuple[int, int]:
    if not text:
        return 0, 0
    width = 0
    height = 0
    for index, char in enumerate(text):
        bbox = draw.textbbox((0, 0), char, font=font)
        width += bbox[2] - bbox[0]
        if index < len(text) - 1:
            width += tracking
        height = max(height, bbox[3] - bbox[1])
    return width, height


def draw_tracked(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    tracking: int,
    fill: tuple[int, int, int, int],
    shadow: bool = True,
) -> None:
    width, height = text_size(draw, text, font, tracking)
    x = center[0] - width / 2
    y = center[1] - height / 2
    for char in text:
        bbox = draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        if shadow:
            draw.text((x + 5, y + 7), char, font=font, fill=(0, 0, 0, 150))
        draw.text((x, y), char, font=font, fill=fill)
        x += char_width + tracking


def make_overlay(path: Path, city_title: str, subtitle: str, width: int, height: int, font_path: str | None) -> dict[str, Any]:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    title_font = load_font(font_path, max(140, width // 11))
    subtitle_font = load_font("/System/Library/Fonts/Avenir Next Condensed.ttc", max(38, width // 78))
    title = city_title.strip().upper()
    subtitle = subtitle.strip()
    # Soft vertical readability gradient; avoid visible black title-card bands.
    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vignette_draw = ImageDraw.Draw(vignette)
    center_y = height * 0.52
    radius = height * 0.46
    for y in range(height):
        strength = max(0.0, 1.0 - abs(y - center_y) / radius)
        alpha = int(86 * (strength**1.8))
        if alpha:
            vignette_draw.line((0, y, width, y), fill=(0, 0, 0, alpha))
    image.alpha_composite(vignette)
    draw_tracked(draw, (width // 2, int(height * 0.47)), title, title_font, max(8, width // 250), (250, 247, 238, 242))
    if subtitle:
        draw_tracked(draw, (width // 2, int(height * 0.62)), subtitle.upper(), subtitle_font, max(6, width // 420), (238, 230, 206, 218))
    line_width = int(width * 0.42)
    y = int(height * 0.69)
    draw.line((width // 2 - line_width // 2, y, width // 2 + line_width // 2, y), fill=(230, 206, 155, 180), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {"overlay": str(path), "font": font_path, "cityTitle": title, "subtitle": subtitle}


def run_ffmpeg(aerial: Path, overlay: Path, output: Path, width: int, height: int, fps: float, duration: float, bitrate: str) -> tuple[bool, str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found"
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},format=rgba[v0];"
        f"[v0][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    )
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(aerial),
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
        f"{fps:.6f}",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-b:v",
        bitrate,
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode == 0 and output.exists(), log.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Make a city aerial title clip with clean English typography.")
    parser.add_argument("--aerial", required=True)
    parser.add_argument("--city-title", required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--overlay")
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--fps", type=float, default=59.94)
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--bitrate", default="50M")
    parser.add_argument("--font")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    aerial = Path(args.aerial).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    overlay = Path(args.overlay).expanduser().resolve() if args.overlay else output.with_suffix(".title_overlay.png")
    font_path = find_font(args.font)
    overlay_info = make_overlay(overlay, args.city_title, args.subtitle, args.width, args.height, font_path)
    ok, log = run_ffmpeg(aerial, overlay, output, args.width, args.height, args.fps, args.duration, args.bitrate)
    manifest = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "ready" if ok else "failed",
        "aerial": str(aerial),
        "output": str(output),
        "width": args.width,
        "height": args.height,
        "fps": args.fps,
        "durationSeconds": args.duration,
        "bitrate": args.bitrate,
        **overlay_info,
        "log": log[-4000:],
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"City aerial title: {manifest['status']}")
        print(f"Output: {output}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
