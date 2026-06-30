#!/usr/bin/env python3
"""Audit frame-level visual proof for transition audition MP4 clips."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def resolve_package_path(package_dir: Path, raw: Any) -> Path | None:
    value = clean(raw, 4000)
    if not value or value.startswith(("http://", "https://")):
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path.resolve()


def is_inside(child: Path | None, parent: Path) -> bool:
    if child is None:
        return False
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safe_slug(value: Any, fallback: str = "transition") -> str:
    text = clean(value, 80).lower().replace(" ", "_") or fallback
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    return slug.strip("_") or fallback


def run_command(command: list[str], *, text: bool = True) -> subprocess.CompletedProcess[Any] | None:
    try:
        return subprocess.run(command, check=False, text=text, capture_output=True)
    except Exception:
        return None


def ffprobe_media(path: Path, ffprobe_bin: str) -> dict[str, Any]:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    result = run_command(command)
    if not result:
        return {"ok": False, "error": "ffprobe failed to start", "command": command}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    video_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"]
    first_video = video_streams[0] if video_streams else {}
    duration = as_float((payload.get("format") or {}).get("duration") if isinstance(payload.get("format"), dict) else None)
    if duration <= 0 and first_video:
        duration = as_float(first_video.get("duration"))
    return {
        "ok": result.returncode == 0 and bool(video_streams),
        "returnCode": result.returncode,
        "width": as_int(first_video.get("width")),
        "height": as_int(first_video.get("height")),
        "durationSeconds": round(duration, 3),
        "videoStreamCount": len(video_streams),
        "audioStreamCount": len(audio_streams),
        "stderr": clean(result.stderr, 1200),
        "command": command,
    }


def frame_times(duration: float, count: int) -> list[float]:
    duration = max(duration, 0.1)
    count = max(1, count)
    if count == 1:
        return [max(0.05, duration / 2.0)]
    fractions = [0.08, 0.28, 0.50, 0.72, 0.92]
    if count != len(fractions):
        fractions = [(index + 1) / (count + 1) for index in range(count)]
    return [max(0.05, min(duration - 0.05, duration * fraction)) for fraction in fractions[:count]]


def raw_frame_sample(
    ffmpeg_bin: str,
    source: Path,
    time_seconds: float,
    sample_width: int,
    sample_height: int,
) -> tuple[dict[str, Any], bytes]:
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{time_seconds:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        f"scale={sample_width}:{sample_height},format=rgb24",
        "-f",
        "rawvideo",
        "-",
    ]
    result = run_command(command, text=False)
    expected = sample_width * sample_height * 3
    if not result:
        return {"ok": False, "error": "ffmpeg failed to start", "command": command}, b""
    data = result.stdout or b""
    if result.returncode != 0 or len(data) < expected:
        return {
            "ok": False,
            "returnCode": result.returncode,
            "stderr": clean((result.stderr or b"").decode("utf-8", errors="ignore"), 1200),
            "byteCount": len(data),
            "expectedByteCount": expected,
            "command": command,
        }, data
    lumas: list[float] = []
    for offset in range(0, expected, 3):
        red = data[offset]
        green = data[offset + 1]
        blue = data[offset + 2]
        lumas.append(0.2126 * red + 0.7152 * green + 0.0722 * blue)
    mean = sum(lumas) / len(lumas)
    variance = sum((value - mean) ** 2 for value in lumas) / len(lumas)
    return {
        "ok": True,
        "sampleWidth": sample_width,
        "sampleHeight": sample_height,
        "meanLuma": round(mean, 3),
        "stddevLuma": round(math.sqrt(variance), 3),
        "byteCount": len(data),
    }, data[:expected]


def mean_abs_rgb_delta(left: bytes, right: bytes) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    if length <= 0:
        return 0.0
    return round(sum(abs(left[index] - right[index]) for index in range(length)) / length, 3)


def extract_frame(ffmpeg_bin: str, source: Path, time_seconds: float, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{time_seconds:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output),
    ]
    result = run_command(command)
    return {
        "ok": bool(result and result.returncode == 0 and output.exists() and output.stat().st_size > 0),
        "returnCode": result.returncode if result else None,
        "outputPath": str(output),
        "timeSeconds": round(time_seconds, 3),
        "stderr": clean(result.stderr if result else "ffmpeg failed to start", 1200),
        "command": command,
    }


def frame_status(frame_path: Path, metrics: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    if args.extract_frames and (not frame_path.exists() or frame_path.stat().st_size <= 0):
        issues.append("frame_file_missing")
    if not metrics.get("ok"):
        issues.append("frame_metrics_missing")
    mean = as_float(metrics.get("meanLuma"))
    stddev = as_float(metrics.get("stddevLuma"))
    if mean <= args.blank_mean_luma:
        issues.append("frame_blank_or_black")
    if stddev <= args.uniform_stddev:
        issues.append("frame_too_uniform_for_transition_audition")
    if mean <= args.dark_warning_mean_luma:
        warnings.append("frame_very_dark")
    return {
        "path": str(frame_path),
        "status": "passed" if not issues else "blocked",
        "timeSeconds": metrics.get("timeSeconds"),
        "sampleWidth": metrics.get("sampleWidth"),
        "sampleHeight": metrics.get("sampleHeight"),
        "meanLuma": round(mean, 3),
        "stddevLuma": round(stddev, 3),
        "issues": issues,
        "warnings": warnings,
    }


def packet_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("auditionRows") if isinstance(packet.get("auditionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def row_output_dir(output_dir: Path, row: dict[str, Any]) -> Path:
    return output_dir / f"row_{as_int(row.get('rowIndex')):03d}_{safe_slug(row.get('boundaryCategory'))}"


def audit_row(
    row: dict[str, Any],
    package_dir: Path,
    output_dir: Path,
    args: argparse.Namespace,
    *,
    ffmpeg_available: bool,
    ffprobe_available: bool,
) -> dict[str, Any]:
    clip_path = resolve_package_path(package_dir, row.get("auditionClip"))
    motion = row.get("motionExecution") if isinstance(row.get("motionExecution"), dict) else {}
    out_dir = row_output_dir(output_dir, row)
    issues: list[str] = []
    warnings: list[str] = []
    if row.get("status") != "ready_with_transition_audition":
        issues.append("audition_row_not_ready")
    if motion.get("ready") is not True:
        issues.append("motion_execution_not_ready")
    if as_int(motion.get("threeBeatCount")) < 3:
        issues.append("motion_execution_missing_three_beat_choreography")
    if motion.get("bgmHitTarget") != "cut_or_effect_on_bgm_phrase_hit" or motion.get("bgmAllowsOffPhrase") is not False:
        issues.append("motion_execution_missing_bgm_hit_policy")
    if motion.get("captionQuietZone") is not True:
        issues.append("motion_execution_missing_caption_quiet_zone")
    if not motion.get("resolveKeyframeEffect"):
        issues.append("motion_execution_missing_resolve_keyframe_effect")
    if not clip_path:
        issues.append("audition_clip_path_missing")
        exists = False
        package_local = False
        file_size = 0
        probe = {"ok": False, "error": "missing_audition_clip_path"}
    else:
        exists = clip_path.exists()
        package_local = is_inside(clip_path, package_dir)
        file_size = clip_path.stat().st_size if exists else 0
        if not exists:
            issues.append("audition_clip_missing")
            probe = {"ok": False, "error": "audition_clip_missing"}
        elif not ffprobe_available:
            issues.append("ffprobe_missing_for_visual_proof")
            probe = {"ok": False, "error": "ffprobe_missing"}
        else:
            probe = ffprobe_media(clip_path, args.ffprobe_bin)
    if clip_path and exists and not package_local:
        issues.append("audition_clip_outside_package")
    if file_size < args.min_file_size_bytes:
        issues.append("audition_clip_too_small_on_disk")
    if not probe.get("ok"):
        issues.append("audition_clip_not_probeable_video")
    if as_float(probe.get("durationSeconds")) < args.min_duration_seconds:
        issues.append("audition_clip_too_short")
    width = as_int(probe.get("width"))
    height = as_int(probe.get("height"))
    if width < args.min_width or height < args.min_height:
        issues.append("audition_clip_below_min_resolution")
    ratio = width / height if height else 0.0
    if probe.get("ok") and not math.isclose(ratio, 16 / 9, rel_tol=0.04, abs_tol=0.04):
        issues.append("audition_clip_not_16x9")
    if as_int(probe.get("audioStreamCount")) > 0:
        issues.append("audition_clip_has_audio_stream")
    frame_reports: list[dict[str, Any]] = []
    extraction_reports: list[dict[str, Any]] = []
    frame_bytes: list[bytes] = []
    if args.extract_frames and not ffmpeg_available:
        issues.append("ffmpeg_missing_for_frame_visual_proof")
    if args.extract_frames and ffmpeg_available and clip_path and exists and probe.get("ok"):
        for index, seconds in enumerate(frame_times(as_float(probe.get("durationSeconds")), args.frame_count), start=1):
            frame_path = out_dir / f"frame_{index:02d}.jpg"
            metrics, raw = raw_frame_sample(args.ffmpeg_bin, clip_path, seconds, args.sample_width, args.sample_height)
            metrics["timeSeconds"] = round(seconds, 3)
            extraction = extract_frame(args.ffmpeg_bin, clip_path, seconds, frame_path)
            extraction["metrics"] = metrics
            extraction_reports.append(extraction)
            frame_reports.append(frame_status(frame_path, metrics, args))
            if metrics.get("ok"):
                frame_bytes.append(raw)
    elif not args.extract_frames:
        issues.append("extract_frames_required_for_visual_proof")
    passed_frames = [frame for frame in frame_reports if frame.get("status") == "passed"]
    deltas = [mean_abs_rgb_delta(frame_bytes[index - 1], frame_bytes[index]) for index in range(1, len(frame_bytes))]
    endpoint_delta = mean_abs_rgb_delta(frame_bytes[0], frame_bytes[-1]) if len(frame_bytes) >= 2 else 0.0
    max_consecutive_delta = max(deltas) if deltas else 0.0
    if len(passed_frames) < args.min_passed_frames:
        issues.append("not_enough_passed_visual_frames")
    if endpoint_delta < args.min_endpoint_delta:
        issues.append("audition_endpoint_frames_too_similar")
    if max_consecutive_delta < args.min_middle_motion_delta:
        issues.append("audition_lacks_middle_motion_or_bridge_visual_change")
    warnings.extend(warning for frame in frame_reports for warning in frame.get("warnings") or [])
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": clean(row.get("boundaryCategory")),
        "importantBoundary": bool(row.get("importantBoundary")),
        "status": "passed" if not issues else "blocked",
        "auditionClip": str(clip_path) if clip_path else "",
        "exists": exists,
        "packageLocal": package_local,
        "fileSizeBytes": file_size,
        "probe": probe,
        "motionExecution": motion,
        "outputDir": str(out_dir),
        "extractions": extraction_reports,
        "frames": frame_reports,
        "passedFrameCount": len(passed_frames),
        "frameDelta": {
            "endpointMeanAbsRgbDelta": endpoint_delta,
            "maxConsecutiveMeanAbsRgbDelta": max_consecutive_delta,
            "consecutiveMeanAbsRgbDeltas": deltas,
            "endpointDistinct": endpoint_delta >= args.min_endpoint_delta,
            "middleMotionProof": max_consecutive_delta >= args.min_middle_motion_delta,
        },
        "issues": issues,
        "warnings": warnings,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_audition_visual_proof"
    ffmpeg_path = shutil.which(args.ffmpeg_bin) if not Path(args.ffmpeg_bin).exists() else args.ffmpeg_bin
    ffprobe_path = shutil.which(args.ffprobe_bin) if not Path(args.ffprobe_bin).exists() else args.ffprobe_bin
    if ffmpeg_path:
        args.ffmpeg_bin = ffmpeg_path
    if ffprobe_path:
        args.ffprobe_bin = ffprobe_path
    packet_path = package_dir / "transition_audition_packet" / "transition_audition_packet.json"
    quality_path = package_dir / "transition_audition_quality_contract_audit.json"
    packet = load_json(packet_path) or {}
    quality = load_json(quality_path) or {}
    rows = packet_rows(packet)
    audited = [
        audit_row(
            row,
            package_dir,
            output_dir,
            args,
            ffmpeg_available=bool(ffmpeg_path),
            ffprobe_available=bool(ffprobe_path),
        )
        for row in rows
    ]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    warnings = [warning for row in audited for warning in row.get("warnings") or []]
    blockers: list[str] = []
    if not packet_path.exists():
        blockers.append("missing transition_audition_packet/transition_audition_packet.json")
    if packet.get("status") not in {"ready_with_transition_audition_packet", "ready_no_important_transitions"}:
        blockers.append(f"transition audition packet status is {packet.get('status')}")
    if quality.get("status") != "passed":
        blockers.append(f"transition audition quality status is {quality.get('status')}")
    if not ffmpeg_path and args.extract_frames:
        blockers.append("ffmpeg not found for transition audition visual proof")
    if not ffprobe_path:
        blockers.append("ffprobe not found for transition audition visual proof")
    blockers.extend(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked[: args.max_blocked_rows])
    status = "passed" if packet.get("status") == "ready_no_important_transitions" and not blockers else "passed" if audited and not blockers and not blocked else "blocked"
    summary = {
        "auditionVisualRowCount": len(audited),
        "passedAuditionVisualRowCount": len(audited) - len(blocked),
        "blockedAuditionVisualRowCount": len(blocked),
        "importantAuditionVisualRowCount": sum(1 for row in audited if row.get("importantBoundary")),
        "rowsWithPackageLocalClip": sum(1 for row in audited if row.get("packageLocal") and row.get("exists")),
        "rowsWithProbeVideo": sum(1 for row in audited if (row.get("probe") or {}).get("ok")),
        "rowsWithNoAudio": sum(1 for row in audited if as_int((row.get("probe") or {}).get("audioStreamCount")) == 0 and row.get("exists")),
        "rowsWithFrameProof": sum(1 for row in audited if as_int(row.get("passedFrameCount")) >= args.min_passed_frames),
        "rowsWithDistinctEndpointFrames": sum(1 for row in audited if ((row.get("frameDelta") or {}).get("endpointDistinct") is True)),
        "rowsWithMiddleMotionProof": sum(1 for row in audited if ((row.get("frameDelta") or {}).get("middleMotionProof") is True)),
        "rowsWithMotionExecution": sum(1 for row in audited if (row.get("motionExecution") or {}).get("ready") is True),
        "rowsWithThreeBeatMotion": sum(1 for row in audited if as_int((row.get("motionExecution") or {}).get("threeBeatCount")) >= 3),
        "rowsWithBgmHitMotion": sum(1 for row in audited if (row.get("motionExecution") or {}).get("bgmHitTarget") == "cut_or_effect_on_bgm_phrase_hit" and (row.get("motionExecution") or {}).get("bgmAllowsOffPhrase") is False),
        "rowsWithCaptionQuietMotion": sum(1 for row in audited if (row.get("motionExecution") or {}).get("captionQuietZone") is True),
        "rowsWithResolveKeyframeEffect": sum(1 for row in audited if bool((row.get("motionExecution") or {}).get("resolveKeyframeEffect"))),
        "transitionAuditionQualityStatus": quality.get("status"),
        "ffmpegAvailable": bool(ffmpeg_path),
        "ffprobeAvailable": bool(ffprobe_path),
        "extractedFrames": bool(args.extract_frames),
        "frameCountPerRow": args.frame_count,
        "minPassedFrames": args.min_passed_frames,
        "warningCount": len(warnings),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {
            "transitionAuditionPacket": str(packet_path),
            "transitionAuditionPacketStatus": packet.get("status"),
            "transitionAuditionQuality": str(quality_path),
            "transitionAuditionQualityStatus": quality.get("status"),
            "extractFrames": bool(args.extract_frames),
            "frameCount": args.frame_count,
            "minPassedFrames": args.min_passed_frames,
            "minEndpointDelta": args.min_endpoint_delta,
            "minMiddleMotionDelta": args.min_middle_motion_delta,
            "ffmpegBin": args.ffmpeg_bin,
            "ffprobeBin": args.ffprobe_bin,
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "actualFrameProofRequired": True,
            "watchableMutedAuditionRequired": True,
            "packageLocalAuditionClipRequired": True,
            "distinctEndpointFramesRequired": True,
            "middleMotionOrBridgeVisualChangeRequired": True,
            "motionExecutionRequired": True,
            "threeBeatBgmHitCaptionQuietRequired": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Audition Visual Proof Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
    ]
    if report["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"][:80])
    lines.extend(["", "## Rows"])
    for row in report.get("auditedRows") or []:
        delta = row.get("frameDelta") if isinstance(row.get("frameDelta"), dict) else {}
        probe = row.get("probe") if isinstance(row.get("probe"), dict) else {}
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- Clip: `{row.get('auditionClip')}`",
                f"- Probe: `{probe.get('width')}x{probe.get('height')}` duration `{probe.get('durationSeconds')}` audio `{probe.get('audioStreamCount')}`",
                f"- Motion execution: `{(row.get('motionExecution') or {}).get('status')}` / `{(row.get('motionExecution') or {}).get('choreographyFamily')}` / `{(row.get('motionExecution') or {}).get('resolveKeyframeEffect')}`",
                f"- Passed frames: `{row.get('passedFrameCount')}`",
                f"- Endpoint delta: `{delta.get('endpointMeanAbsRgbDelta')}`",
                f"- Max consecutive delta: `{delta.get('maxConsecutiveMeanAbsRgbDelta')}`",
            ]
        )
        for frame in row.get("frames") or []:
            lines.append(f"- Frame: `{frame.get('path')}` `{frame.get('status')}` mean `{frame.get('meanLuma')}` stddev `{frame.get('stddevLuma')}`")
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Transition audition MP4s need actual ffprobe plus extracted frame evidence, not just a path in JSON.",
            "- Each audition must be package-local, muted, 16:9, nonblank, and visually change from outgoing to landing.",
            "- The proof is pre-Resolve evidence that route/title/day-change transitions are watchable before final timeline apply.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition audition MP4s with frame-level visual proof.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--extract-frames", action="store_true")
    parser.add_argument("--frame-count", type=int, default=5)
    parser.add_argument("--min-passed-frames", type=int, default=5)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--sample-width", type=int, default=160)
    parser.add_argument("--sample-height", type=int, default=90)
    parser.add_argument("--min-width", type=int, default=120)
    parser.add_argument("--min-height", type=int, default=68)
    parser.add_argument("--min-duration-seconds", type=float, default=1.5)
    parser.add_argument("--min-file-size-bytes", type=int, default=4096)
    parser.add_argument("--blank-mean-luma", type=float, default=3.0)
    parser.add_argument("--dark-warning-mean-luma", type=float, default=10.0)
    parser.add_argument("--uniform-stddev", type=float, default=0.75)
    parser.add_argument("--min-endpoint-delta", type=float, default=3.0)
    parser.add_argument("--min-middle-motion-delta", type=float, default=1.0)
    parser.add_argument("--max-blocked-rows", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_audition_visual_proof_contract_audit.json", report)
    write_markdown(package_dir / "transition_audition_visual_proof_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
