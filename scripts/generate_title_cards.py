#!/usr/bin/env python3
"""Generate title/place cards as MP4 assets and optionally inject them into a Resolve blueprint."""

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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_font(preferred: str = "Hiragino Mincho ProN") -> str | None:
    fc_match = shutil.which("fc-match")
    if fc_match:
        result = subprocess.run([fc_match, "-f", "%{file}\n", preferred], check=False, capture_output=True, text=True)
        candidate = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if candidate and Path(candidate).exists():
            return candidate
    for path in [
        "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]:
        if Path(path).exists():
            return path
    return None


def font(size: int, preferred: str = "Hiragino Mincho ProN") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = find_font(preferred)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_center(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font_obj: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    bbox = draw.textbbox((0, 0), text, font=font_obj)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text((xy[0] - width / 2, xy[1] - height / 2), text, font=font_obj, fill=fill)


def make_card_png(path: Path, title: str, subtitle: str, width: int, height: int) -> None:
    img = Image.new("RGB", (width, height), (17, 22, 24))
    draw = ImageDraw.Draw(img)
    title_font = font(max(92, width // 24), "Hiragino Mincho ProN")
    sub_font = font(max(34, width // 70), "Hiragino Sans")
    small_font = font(max(24, width // 96), "Hiragino Sans")
    draw.rectangle((0, 0, width, height), fill=(17, 22, 24))
    draw.line((width * 0.18, height * 0.43, width * 0.82, height * 0.43), fill=(186, 164, 118), width=3)
    draw_center(draw, (width // 2, int(height * 0.50)), title, title_font, (238, 232, 216))
    if subtitle:
        draw_center(draw, (width // 2, int(height * 0.60)), subtitle, sub_font, (198, 205, 199))
    draw_center(draw, (width // 2, int(height * 0.78)), "TRAVEL FILM", small_font, (151, 139, 113))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def make_mp4(png: Path, mp4: Path, duration: float, fps: float) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(png),
            "-t",
            str(duration),
            "-r",
            str(fps),
            "-vf",
            "format=yuv420p",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(mp4),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and mp4.exists()


def clean_display_title(value: str) -> str:
    title = re.sub(r"-[0-9a-f]{6,}$", "", value.strip(), flags=re.IGNORECASE)
    if "东京" in title and "大阪" in title:
        return "TOKYO TO OSAKA"
    if "香港" in title and "澳门" in title:
        return "HONG KONG TO MACAU"
    replacements = {
        "东京": "TOKYO",
        "大阪": "OSAKA",
        "京都": "KYOTO",
        "巴黎": "PARIS",
        "洛杉矶": "LOS ANGELES",
        "香港": "HONG KONG",
        "澳门": "MACAU",
        "日本": "JAPAN",
    }
    for needle, replacement in replacements.items():
        if needle in title:
            return replacement
    return title or "TRAVEL NOTES"


def card_specs(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    title = clean_display_title(str(delivery.get("title") or Path(delivery.get("projectDir", "Travel")).name))
    specs = [
        {
            "id": "opening",
            "title": title,
            "subtitle": "OPENING ROUTE",
            "timelineStartSeconds": 0.0,
            "durationSeconds": 4.0,
            "chapterIndex": 0,
        }
    ]
    for section in delivery.get("longFormSections", []):
        idx = section.get("chapterIndex")
        if idx in {0, 999}:
            continue
        specs.append(
            {
                "id": f"chapter_{idx}",
                "title": clean_display_title(str(section.get("place") or f"Chapter {idx}")),
                "subtitle": f"DAY / CHAPTER {idx}",
                "timelineStartSeconds": float(section.get("startSeconds") or 0),
                "durationSeconds": 4.0,
                "chapterIndex": idx,
            }
        )
    specs.append(
        {
            "id": "ending",
            "title": "THE ROUTE CONTINUES",
            "subtitle": "TRAVEL NOTES",
            "timelineStartSeconds": max(0.0, float(delivery.get("target", {}).get("durationMinutes", 20)) * 60 - 8),
            "durationSeconds": 5.0,
            "chapterIndex": 999,
        }
    )
    return specs


def update_blueprint(blueprint_path: Path, manifest: dict[str, Any], fps: float) -> None:
    blueprint = load_json(blueprint_path)
    clips = [c for c in blueprint.get("clips", []) if c.get("role") not in {"title_card", "place_card"}]
    for card in manifest["cards"]:
        clips.append(
            {
                "role": "title_card" if card["chapterIndex"] in {0, 999} else "place_card",
                "chapterIndex": card["chapterIndex"],
                "place": card["title"],
                "sourcePath": card["mp4"],
                "sourceStartSeconds": 0.0,
                "sourceEndSeconds": card["durationSeconds"],
                "timelineStartSeconds": card["timelineStartSeconds"],
                "timelineEndSeconds": card["timelineStartSeconds"] + card["durationSeconds"],
                "trackType": "video",
                "trackIndex": 2,
                "mediaType": 1,
                "purpose": "cinematic title/place card",
            }
        )
    blueprint["clips"] = sorted(clips, key=lambda c: (float(c.get("timelineStartSeconds") or 0), int(c.get("trackIndex") or 1)))
    blueprint.setdefault("assets", {})["titleCards"] = [card["mp4"] for card in manifest["cards"]]
    blueprint["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    blueprint_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate title/place cards for a Travel Video Studio package.")
    parser.add_argument("--delivery-plan", required=True)
    parser.add_argument("--blueprint", help="Resolve blueprint to update.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--update-blueprint", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    delivery = load_json(Path(args.delivery_plan).expanduser().resolve())
    output = Path(args.output_dir).expanduser().resolve()
    cards = []
    for spec in card_specs(delivery):
        stem = spec["id"]
        png = output / f"{stem}.png"
        mp4 = output / f"{stem}.mp4"
        make_card_png(png, spec["title"], spec["subtitle"], args.width, args.height)
        ok = make_mp4(png, mp4, spec["durationSeconds"], args.fps)
        cards.append({**spec, "png": str(png), "mp4": str(mp4) if ok else None, "videoCreated": ok})
    manifest = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "cards": cards,
        "font": find_font(),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "title_cards_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.update_blueprint and args.blueprint:
        update_blueprint(Path(args.blueprint).expanduser().resolve(), manifest, args.fps)
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"Generated {len(cards)} title/place cards in {output}")
    return 0 if all(card["videoCreated"] for card in cards) else 2


if __name__ == "__main__":
    raise SystemExit(main())
