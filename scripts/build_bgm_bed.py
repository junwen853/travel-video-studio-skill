#!/usr/bin/env python3
"""Build a traceable BGM-only audio bed from approved local music tracks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ffprobe_json(path: Path) -> dict[str, Any]:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,bit_rate",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    return json.loads(proc.stdout.decode("utf-8"))


def audio_duration(path: Path) -> float:
    probe = ffprobe_json(path)
    return float(probe.get("format", {}).get("duration", 0.0))


def load_track_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tracks = data.get("tracks", data if isinstance(data, list) else [])
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("Track manifest must contain a non-empty tracks list.")
    normalized: list[dict[str, Any]] = []
    for idx, track in enumerate(tracks):
        if not isinstance(track, dict):
            raise ValueError(f"Track {idx} must be an object.")
        media_path = Path(str(track.get("path", ""))).expanduser()
        if not media_path.exists():
            raise FileNotFoundError(media_path)
        license_url = str(track.get("license", ""))
        if not license_url.startswith(("http://", "https://")):
            raise ValueError(f"Track {idx} is missing a traceable license URL.")
        normalized.append({**track, "path": str(media_path), "duration": audio_duration(media_path)})
    return normalized


def choose_repeated_tracks(tracks: list[dict[str, Any]], duration: float, crossfade: float) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    effective = 0.0
    idx = 0
    while effective < duration + 2.0:
        item = dict(tracks[idx % len(tracks)])
        selected.append(item)
        effective += float(item["duration"])
        if len(selected) > 1:
            effective -= crossfade
        idx += 1
        if idx > 200:
            raise RuntimeError("Too many repeated tracks needed for the requested duration.")
    return selected


def build_ffmpeg_command(
    selected: list[dict[str, Any]],
    output: Path,
    duration: float,
    crossfade: float,
    volume: float,
    integrated_loudness: float,
) -> list[str]:
    cmd = ["ffmpeg", "-hide_banner", "-y"]
    for track in selected:
        cmd.extend(["-i", str(track["path"])])

    filters: list[str] = []
    for idx, track in enumerate(selected):
        trim = max(0.1, float(track["duration"]))
        filters.append(
            f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"atrim=0:{trim:.3f},asetpts=N/SR/TB,volume={volume:.4f}[a{idx}]"
        )
    if len(selected) == 1:
        last = "a0"
    else:
        last = "x1"
        filters.append(f"[a0][a1]acrossfade=d={crossfade:.3f}:c1=tri:c2=tri[{last}]")
        for idx in range(2, len(selected)):
            next_label = f"x{idx}"
            filters.append(f"[{last}][a{idx}]acrossfade=d={crossfade:.3f}:c1=tri:c2=tri[{next_label}]")
            last = next_label
    filters.append(
        f"[{last}]atrim=0:{duration:.3f},"
        f"loudnorm=I={integrated_loudness:.1f}:TP=-1.5:LRA=11,"
        "aresample=48000[out]"
    )
    cmd.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--manifest-output")
    parser.add_argument("--crossfade", type=float, default=2.0)
    parser.add_argument("--volume", type=float, default=0.82)
    parser.add_argument("--integrated-loudness", type=float, default=-18.0)
    parser.add_argument("--mode", default="bgm_only_no_camera_voice")
    args = parser.parse_args()

    try:
        track_manifest = Path(args.track_manifest)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        tracks = load_track_manifest(track_manifest)
        selected = choose_repeated_tracks(tracks, args.duration, args.crossfade)
        cmd = build_ffmpeg_command(
            selected,
            output,
            args.duration,
            args.crossfade,
            args.volume,
            args.integrated_loudness,
        )
        proc = run(cmd)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
        probe = ffprobe_json(output)
        manifest = {
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "mode": args.mode,
            "output": str(output),
            "durationTargetSeconds": args.duration,
            "crossfadeSeconds": args.crossfade,
            "volume": args.volume,
            "integratedLoudnessTarget": args.integrated_loudness,
            "tracks": selected,
            "probe": probe,
        }
        manifest_output = Path(args.manifest_output) if args.manifest_output else output.with_suffix(".manifest.json")
        manifest_output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "passed", "output": str(output), "manifest": str(manifest_output)}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"build_bgm_bed failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

