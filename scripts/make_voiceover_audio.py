#!/usr/bin/env python3
"""Create local macOS TTS voiceover audio and an estimated SRT file."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def srt_time(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def split_lines(text: str) -> list[str]:
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


def make_srt(lines: list[str], duration: float | None) -> str:
    weights = [max(1, len(line)) for line in lines]
    total_weight = sum(weights) or 1
    total_duration = duration or max(8.0, total_weight / 4.8)
    cursor = 0.0
    entries = []
    for idx, (line, weight) in enumerate(zip(lines, weights, strict=False), 1):
        item_duration = max(2.0, total_duration * weight / total_weight)
        entries.append(f"{idx}\n{srt_time(cursor)} --> {srt_time(cursor + item_duration)}\n{line}\n")
        cursor += item_duration
    return "\n".join(entries).strip() + "\n"


def run_tts(args: argparse.Namespace) -> dict[str, str | bool | None]:
    script = Path(args.script).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    text = script.read_text(encoding="utf-8")
    tts_input = output_dir / "voiceover_tts_input.txt"
    tts_input.write_text(text, encoding="utf-8")

    say = shutil.which("say")
    if not say:
        raise SystemExit("macOS 'say' command not found. Use a cloud TTS provider or install a local TTS tool.")

    aiff = output_dir / "voiceover.aiff"
    cmd = [say, "-r", str(args.rate), "-f", str(tts_input), "-o", str(aiff)]
    if args.voice:
        cmd[1:1] = ["-v", args.voice]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "say failed")

    m4a = output_dir / "voiceover.m4a"
    ffmpeg = shutil.which("ffmpeg")
    converted = False
    if ffmpeg:
        result = subprocess.run(
            [ffmpeg, "-y", "-i", str(aiff), "-c:a", "aac", "-b:a", "192k", str(m4a)],
            check=False,
            capture_output=True,
            text=True,
        )
        converted = result.returncode == 0

    audio_for_duration = m4a if converted else aiff
    duration = probe_duration(audio_for_duration)
    subtitle_path = output_dir / "subtitles.srt"
    subtitle_path.write_text(make_srt(split_lines(text), duration), encoding="utf-8")

    return {
        "script": str(script),
        "outputDir": str(output_dir),
        "aiff": str(aiff),
        "m4a": str(m4a) if converted else None,
        "subtitles": str(subtitle_path),
        "durationSeconds": duration,
        "voice": args.voice,
        "rate": args.rate,
        "ffmpegConverted": converted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create local macOS TTS voiceover audio.")
    parser.add_argument("--script", required=True, help="Plain-text voiceover script.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--voice", help="macOS voice name. Omit to use the system default.")
    parser.add_argument("--rate", type=int, default=175, help="Speech rate for macOS say.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    result = run_tts(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Voiceover created")
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
