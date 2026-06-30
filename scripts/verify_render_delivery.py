#!/usr/bin/env python3
"""Verify a rendered long-form travel video before claiming delivery."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def ffprobe(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    result = run_capture(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"Unable to parse ffprobe JSON: {exc}"


def infer_output(package_dir: Path, output_arg: str | None) -> Path | None:
    if output_arg:
        return Path(output_arg).expanduser().resolve()
    report_path = package_dir / "FINAL_DELIVERY_REPORT.json"
    if report_path.exists():
        try:
            report = load_json(report_path)
            if report.get("finalOutput"):
                return Path(report["finalOutput"]).expanduser().resolve()
        except Exception:  # noqa: BLE001
            pass
    render_plan_path = package_dir / "render_plan.json"
    if render_plan_path.exists():
        try:
            plan = load_json(render_plan_path)
            for key in ("finalOutput", "output"):
                if plan.get(key):
                    return Path(plan[key]).expanduser().resolve()
            target_dir = plan.get("targetDir")
            custom_name = plan.get("customName")
            if target_dir and custom_name:
                candidate = Path(target_dir).expanduser() / f"{custom_name}.mp4"
                if candidate.exists():
                    return candidate.resolve()
        except Exception:  # noqa: BLE001
            pass
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return renders[0].resolve() if renders else None


def parse_samples(value: str | None, duration: float) -> list[float]:
    if value:
        raw = [float(item.strip()) for item in value.split(",") if item.strip()]
    else:
        raw = [5.0, 75.0, 300.0, 700.0, max(1.0, duration - 10.0)]
    samples = []
    for item in raw:
        if 0 <= item < max(duration, 1.0) and item not in samples:
            samples.append(item)
    return samples


def extract_sample_frames(video: Path, package_dir: Path, samples: list[float]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    metrics: list[dict[str, Any]] = []
    qa_dir = package_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageStat  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        Image = None  # type: ignore[assignment]
        ImageStat = None  # type: ignore[assignment]
        warnings.append(f"PIL unavailable; sample frames will be extracted without luma metrics: {exc}")
    for seconds in samples:
        out = qa_dir / f"verify_render_{int(round(seconds)):04d}s.jpg"
        result = run_capture(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{seconds:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(out),
            ]
        )
        row: dict[str, Any] = {"seconds": seconds, "file": str(out), "extracted": result.returncode == 0 and out.exists()}
        if result.returncode != 0:
            row["error"] = (result.stderr or result.stdout).strip()
            metrics.append(row)
            continue
        if Image is not None and ImageStat is not None:
            try:
                image = Image.open(out).convert("L")
                stat = ImageStat.Stat(image)
                row.update(
                    {
                        "meanLuma": round(float(stat.mean[0]), 2),
                        "stddevLuma": round(float(stat.stddev[0]), 2),
                        "minMaxLuma": list(image.getextrema()),
                        "likelyBlank": bool(stat.mean[0] < 3 or stat.stddev[0] < 1),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                row["metricError"] = str(exc)
        metrics.append(row)
    return metrics, warnings


def run_blackdetect(video: Path, package_dir: Path, min_duration: float, pic_threshold: float, pixel_threshold: float) -> dict[str, Any]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video),
        "-vf",
        f"blackdetect=d={min_duration}:pic_th={pic_threshold}:pix_th={pixel_threshold}",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = run_capture(cmd)
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    log_path = package_dir / "blackdetect_verification.log"
    log_path.write_text(text, encoding="utf-8")
    segments = []
    for match in re.finditer(r"black_start:([0-9.]+) black_end:([0-9.]+) black_duration:([0-9.]+)", text):
        segments.append(
            {
                "start": float(match.group(1)),
                "end": float(match.group(2)),
                "duration": float(match.group(3)),
            }
        )
    return {
        "returnCode": result.returncode,
        "log": str(log_path),
        "blackSegmentCount": len(segments),
        "maxBlackDuration": max([row["duration"] for row in segments], default=0),
        "segments": segments,
    }


def subtitle_evidence(package_dir: Path, probe: dict[str, Any]) -> dict[str, Any]:
    subtitle_streams = [stream for stream in probe.get("streams", []) if stream.get("codec_type") == "subtitle"]
    sidecar = package_dir / "subtitles.srt"
    overlay_manifests = sorted(package_dir.glob("subtitle_overlays_*/manifest.json"))
    overlay_manifest = overlay_manifests[-1] if overlay_manifests else package_dir / "subtitle_overlays_v3" / "manifest.json"
    return {
        "subtitleStreamCount": len(subtitle_streams),
        "subtitleStreams": [
            {
                "codec": stream.get("codec_name"),
                "duration": stream.get("duration"),
                "tags": stream.get("tags") or {},
            }
            for stream in subtitle_streams
        ],
        "sidecar": str(sidecar) if sidecar.exists() else None,
        "burnedInOverlayManifest": str(overlay_manifest) if overlay_manifest.exists() else None,
    }


def frame_rate_value(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            denominator = float(den)
            return float(num) / denominator if denominator else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    output = infer_output(package_dir, args.output)
    blockers: list[str] = []
    warnings: list[str] = []
    if not output:
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "output": None,
            "blockers": ["No render output could be inferred. Pass --output explicitly."],
            "warnings": [],
        }
    output = output.resolve()
    if not output.exists():
        blockers.append(f"Render output does not exist: {output}")
        size_bytes = 0
    else:
        size_bytes = output.stat().st_size
        if size_bytes < int(args.min_size_mb * 1024 * 1024):
            blockers.append(f"Render output is too small: {size_bytes} bytes.")

    probe, probe_error = ffprobe(output) if output.exists() else (None, "Output missing.")
    video_stream = None
    audio_stream = None
    duration = 0.0
    if not probe:
        blockers.append(probe_error or "ffprobe failed.")
        probe = {}
    else:
        duration = float((probe.get("format") or {}).get("duration") or 0)
        video_stream = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), None)
        audio_stream = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"), None)
        if not video_stream:
            blockers.append("No video stream found.")
        if not audio_stream and not args.allow_no_audio:
            blockers.append("No audio stream found.")
        if duration < args.min_duration_seconds:
            blockers.append(f"Duration {duration:.3f}s is below required {args.min_duration_seconds:.3f}s.")
        if video_stream:
            if args.width and int(video_stream.get("width") or 0) != args.width:
                blockers.append(f"Video width mismatch: {video_stream.get('width')} != {args.width}.")
            if args.height and int(video_stream.get("height") or 0) != args.height:
                blockers.append(f"Video height mismatch: {video_stream.get('height')} != {args.height}.")
            fps = frame_rate_value(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
            if args.min_fps and (fps is None or fps < args.min_fps):
                blockers.append(f"Video frame rate {fps} is below required {args.min_fps}.")
            bitrate_mbps = float(video_stream.get("bit_rate") or 0) / 1_000_000
            if args.min_video_bitrate_mbps and bitrate_mbps < args.min_video_bitrate_mbps:
                blockers.append(
                    f"Video bitrate {bitrate_mbps:.2f} Mbps is below required {args.min_video_bitrate_mbps:.2f} Mbps."
                )

    blackdetect = None
    if output.exists():
        if args.skip_blackdetect:
            blockers.append("blackdetect was skipped; final delivery verification requires a full black-frame scan.")
        else:
            blackdetect = run_blackdetect(output, package_dir, args.black_min_duration, args.black_pic_threshold, args.black_pixel_threshold)
            if blackdetect["returnCode"] != 0:
                blockers.append("blackdetect ffmpeg command failed.")
            bad_segments = [row for row in blackdetect["segments"] if row["duration"] > args.allowed_black_seconds]
            if bad_segments:
                blockers.append(
                    f"{len(bad_segments)} black segments exceed allowed {args.allowed_black_seconds:.3f}s; "
                    f"max={blackdetect['maxBlackDuration']:.3f}s."
                )

    samples = parse_samples(args.samples, duration)
    sample_frames: list[dict[str, Any]] = []
    if output.exists() and samples:
        sample_frames, sample_warnings = extract_sample_frames(output, package_dir, samples)
        warnings.extend(sample_warnings)
        blank_samples = [row for row in sample_frames if row.get("likelyBlank")]
        failed_samples = [row for row in sample_frames if not row.get("extracted")]
        if blank_samples:
            blockers.append(f"{len(blank_samples)} sampled frames look blank.")
        if failed_samples:
            blockers.append(f"{len(failed_samples)} sampled frames could not be extracted.")

    subtitles = subtitle_evidence(package_dir, probe)
    if args.expect_subtitles == "sidecar" and not subtitles["sidecar"]:
        blockers.append("Expected subtitle sidecar, but subtitles.srt is missing.")
    elif args.expect_subtitles == "embedded" and subtitles["subtitleStreamCount"] <= 0:
        blockers.append("Expected embedded subtitle stream, but none was found.")
    elif args.expect_subtitles == "burned-in" and not subtitles["burnedInOverlayManifest"]:
        warnings.append("Burned-in subtitles cannot be OCR-verified; overlay manifest is missing.")
    elif args.expect_subtitles == "any" and not (
        subtitles["sidecar"] or subtitles["subtitleStreamCount"] or subtitles["burnedInOverlayManifest"]
    ):
        warnings.append("No subtitle sidecar, embedded stream, or burned-in overlay manifest found.")

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "output": str(output),
        "sizeBytes": size_bytes,
        "durationSeconds": duration,
        "video": {
            "codec": video_stream.get("codec_name") if video_stream else None,
            "width": video_stream.get("width") if video_stream else None,
            "height": video_stream.get("height") if video_stream else None,
            "avgFrameRate": video_stream.get("avg_frame_rate") if video_stream else None,
            "frameRateValue": frame_rate_value(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")) if video_stream else None,
            "bitrateMbps": round(float(video_stream.get("bit_rate") or 0) / 1_000_000, 3) if video_stream else None,
            "frames": video_stream.get("nb_frames") if video_stream else None,
        },
        "audio": {
            "codec": audio_stream.get("codec_name") if audio_stream else None,
            "channels": audio_stream.get("channels") if audio_stream else None,
            "sampleRate": audio_stream.get("sample_rate") if audio_stream else None,
            "durationSeconds": float(audio_stream.get("duration") or 0) if audio_stream else None,
        },
        "blackdetect": blackdetect,
        "sampleFrames": sample_frames,
        "subtitles": subtitles,
        "blockers": blockers,
        "warnings": warnings,
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Render Delivery Verification",
        "",
        f"Status: `{report['status']}`",
        f"Output: `{report.get('output')}`",
        f"Duration: `{report.get('durationSeconds')}` seconds",
        f"Size: `{report.get('sizeBytes')}` bytes",
        "",
        "## Video",
        f"- Codec: `{(report.get('video') or {}).get('codec')}`",
        f"- Resolution: `{(report.get('video') or {}).get('width')}x{(report.get('video') or {}).get('height')}`",
        f"- Frame rate: `{(report.get('video') or {}).get('avgFrameRate')}`",
        "",
        "## Audio",
        f"- Codec: `{(report.get('audio') or {}).get('codec')}`",
        f"- Channels: `{(report.get('audio') or {}).get('channels')}`",
        f"- Sample rate: `{(report.get('audio') or {}).get('sampleRate')}`",
        "",
        "## Blackdetect",
    ]
    blackdetect = report.get("blackdetect") or {}
    lines.append(f"- Segments: `{blackdetect.get('blackSegmentCount')}`")
    lines.append(f"- Max duration: `{blackdetect.get('maxBlackDuration')}`")
    lines.append("")
    lines.append("## Blockers")
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {item}" for item in report.get("warnings") or ["None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a rendered long-form travel video output.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output", help="Render output path. Defaults to FINAL_DELIVERY_REPORT/render_plan/latest mp4.")
    parser.add_argument("--min-duration-seconds", type=float, default=1190.0)
    parser.add_argument("--min-size-mb", type=float, default=100.0)
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--min-fps", type=float, default=0.0)
    parser.add_argument("--min-video-bitrate-mbps", type=float, default=0.0)
    parser.add_argument("--allow-no-audio", action="store_true")
    parser.add_argument("--samples", help="Comma-separated sample seconds. Defaults to several positions across the film.")
    parser.add_argument("--skip-blackdetect", action="store_true")
    parser.add_argument("--black-min-duration", type=float, default=0.4)
    parser.add_argument("--black-pic-threshold", type=float, default=0.98)
    parser.add_argument("--black-pixel-threshold", type=float, default=0.03)
    parser.add_argument("--allowed-black-seconds", type=float, default=0.0)
    parser.add_argument("--expect-subtitles", choices=["none", "any", "sidecar", "embedded", "burned-in"], default="any")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(args)
    json_path = package_dir / "render_delivery_verification.json"
    md_path = package_dir / "render_delivery_verification.md"
    write_json(json_path, report)
    write_markdown(md_path, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Render delivery verification: {report['status']}")
        print(f"Output: {report.get('output')}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
        for warning in report.get("warnings") or []:
            print(f"WARNING: {warning}")
        print(f"Report: {json_path}")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
