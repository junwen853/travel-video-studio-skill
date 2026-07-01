#!/usr/bin/env python3
"""Prepare a single review reel from all important transition audition clips."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


CLOSED_STATUS = "ready_with_transition_watch_reel"
NO_TRANSITIONS_STATUS = "ready_no_important_transitions"
NEEDS_BUILD_STATUS = "needs_transition_watch_reel_build"
BLOCKED_STATUS = "blocked_transition_watch_reel"


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


def clean(value: Any, limit: int = 800) -> str:
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


def resolve_package_path(package_dir: Path, raw: Any) -> Path | None:
    value = clean(raw, 4000)
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path.resolve()


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, check=False, text=True, capture_output=True)
    except Exception:
        return None


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def ffprobe_media(path: Path, ffprobe_bin: str) -> dict[str, Any]:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = run_command(command)
    if not result:
        return {"ok": False, "error": "ffprobe failed to start", "command": command}
    if result.returncode != 0:
        return {"ok": False, "error": clean(result.stderr or result.stdout, 1200), "returnCode": result.returncode, "command": command}
    try:
        data = json.loads(result.stdout)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "returnCode": result.returncode, "command": command}
    streams = data.get("streams") if isinstance(data.get("streams"), list) else []
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    first_video = video_streams[0] if video_streams else {}
    duration = as_float(data.get("format", {}).get("duration"), 0.0) if isinstance(data.get("format"), dict) else 0.0
    if duration <= 0 and first_video:
        duration = as_float(first_video.get("duration"), 0.0)
    return {
        "ok": bool(video_streams),
        "width": as_int(first_video.get("width")),
        "height": as_int(first_video.get("height")),
        "durationSeconds": round(duration, 3),
        "videoStreamCount": len(video_streams),
        "audioStreamCount": len(audio_streams),
        "returnCode": result.returncode,
        "command": command,
    }


def audition_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("auditionRows") if isinstance(packet.get("auditionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def should_include(row: dict[str, Any], include_all: bool) -> bool:
    return include_all or bool(row.get("importantBoundary"))


def build_reel_row(row: dict[str, Any], package_dir: Path, args: argparse.Namespace, cursor: float) -> dict[str, Any]:
    clip_path = resolve_package_path(package_dir, row.get("auditionClip"))
    issues: list[str] = []
    warnings: list[str] = []
    exists = bool(clip_path and clip_path.exists())
    package_local = bool(clip_path and is_inside(clip_path, package_dir))
    if row.get("status") != "ready_with_transition_audition":
        issues.append("audition_row_not_ready")
    if not clip_path:
        issues.append("audition_clip_path_missing")
        probe = {"ok": False}
    elif not exists:
        issues.append("audition_clip_missing")
        probe = {"ok": False}
    else:
        probe = ffprobe_media(clip_path, args.ffprobe_bin)
        if not probe.get("ok"):
            issues.append("audition_clip_not_probeable_video")
        if as_float(probe.get("durationSeconds")) < args.min_clip_duration_seconds:
            issues.append("audition_clip_too_short_for_reel")
        if as_int(probe.get("width")) < args.min_width or as_int(probe.get("height")) < args.min_height:
            issues.append("audition_clip_too_small_for_reel")
        if args.require_muted and as_int(probe.get("audioStreamCount")) > 0:
            issues.append("audition_clip_has_audio_stream")
    if clip_path and not package_local:
        issues.append("audition_clip_outside_package")
    if as_int(row.get("bridgeSampleCount")) == 0 and row.get("importantBoundary"):
        warnings.append("important_transition_has_no_bridge_sample")
    duration = as_float(probe.get("durationSeconds"), 0.0) if isinstance(probe, dict) else 0.0
    motion = row.get("motionExecution") if isinstance(row.get("motionExecution"), dict) else {}
    sensory = row.get("sensoryContinuity") if isinstance(row.get("sensoryContinuity"), dict) else {}
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": clean(row.get("boundaryCategory")),
        "importantBoundary": bool(row.get("importantBoundary")),
        "status": "blocked" if issues else "ready_for_reel",
        "auditionClip": str(clip_path) if clip_path else None,
        "exists": exists,
        "packageLocal": package_local,
        "durationSeconds": duration,
        "reelStartSeconds": round(cursor, 3),
        "reelEndSeconds": round(cursor + duration, 3),
        "fromSourceName": clean(row.get("fromSourceName")),
        "toSourceName": clean(row.get("toSourceName")),
        "storyboardPurpose": clean(row.get("storyboardPurpose")),
        "bridgeSampleCount": row.get("bridgeSampleCount"),
        "motionExecution": {
            "ready": motion.get("ready"),
            "choreographyFamily": motion.get("choreographyFamily"),
            "resolveKeyframeEffect": motion.get("resolveKeyframeEffect"),
            "bgmHitTarget": motion.get("bgmHitTarget"),
            "captionQuietZone": motion.get("captionQuietZone"),
            "motionDirectionMatch": motion.get("motionDirectionMatch"),
        },
        "sensoryContinuity": {
            "ready": sensory.get("ready"),
            "visualReady": sensory.get("visualReady"),
            "audioReady": sensory.get("audioReady"),
            "routeOrMoodReady": sensory.get("routeOrMoodReady"),
            "landingReady": sensory.get("landingReady"),
        },
        "probe": probe,
        "issues": issues,
        "warnings": warnings,
    }


def concat_reel(rows: list[dict[str, Any]], output_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    concat_file = output_path.with_suffix(".concat.txt")
    concat_file.parent.mkdir(parents=True, exist_ok=True)
    concat_file.write_text(
        "".join(f"file '{Path(str(row['auditionClip'])).as_posix()}'\n" for row in rows),
        encoding="utf-8",
    )
    vf = (
        f"scale={args.width}:{args.height}:force_original_aspect_ratio=decrease,"
        f"pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={args.fps},format=yuv420p"
    )
    command = [
        args.ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-an",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(args.crf),
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = run_command(command)
    ok = bool(result and result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0)
    return {
        "ok": ok,
        "outputPath": str(output_path),
        "concatList": str(concat_file),
        "command": command,
        "returnCode": result.returncode if result else None,
        "stderr": clean(result.stderr if result else "ffmpeg failed to start", 1600),
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_watch_reel"
    packet_path = package_dir / "transition_audition_packet" / "transition_audition_packet.json"
    quality_path = package_dir / "transition_audition_quality_contract_audit.json"
    storyboard_path = package_dir / "transition_storyboard_contract_audit.json"
    packet = load_json(packet_path) or {}
    quality = load_json(quality_path) or {}
    storyboard = load_json(storyboard_path) or {}
    all_rows = audition_rows(packet)
    selected = [row for row in all_rows if should_include(row, args.include_all_rows)]
    if args.max_rows:
        selected = selected[: args.max_rows]

    cursor = 0.0
    reel_rows: list[dict[str, Any]] = []
    for row in sorted(selected, key=lambda item: as_int(item.get("rowIndex"))):
        reel_row = build_reel_row(row, package_dir, args, cursor)
        reel_rows.append(reel_row)
        cursor += as_float(reel_row.get("durationSeconds"), 0.0)

    ready_rows = [row for row in reel_rows if row.get("status") == "ready_for_reel"]
    blocked_rows = [row for row in reel_rows if row.get("status") == "blocked"]
    blockers: list[str] = []
    warnings = [warning for row in reel_rows for warning in row.get("warnings") or []]
    if not args.require_muted:
        warnings.append("Transition watch reel was run with --allow-audio; BGM-only travel review should keep --require-muted.")

    if not packet_path.exists():
        blockers.append("missing transition_audition_packet/transition_audition_packet.json")
    if packet.get("status") not in {"ready_with_transition_audition_packet", "ready_no_important_transitions"}:
        blockers.append(f"transition audition packet status is {packet.get('status')}")
    if quality_path.exists() and quality.get("status") != "passed":
        blockers.append(f"transition audition quality status is {quality.get('status')}")
    if storyboard_path.exists() and storyboard.get("status") != "passed":
        blockers.append(f"transition storyboard status is {storyboard.get('status')}")
    blockers.extend(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[: args.max_blocked_rows_in_report])

    ffmpeg_path = shutil.which(args.ffmpeg_bin) if not Path(args.ffmpeg_bin).exists() else args.ffmpeg_bin
    if ffmpeg_path:
        args.ffmpeg_bin = ffmpeg_path
    reel_output = output_dir / "transition_watch_reel.mp4"
    if not reel_rows and packet.get("status") == "ready_no_important_transitions":
        reel = {"ok": True, "skipped": True, "reason": "ready_no_important_transitions", "outputPath": None}
        status = NO_TRANSITIONS_STATUS
    elif blockers or blocked_rows:
        reel = {"ok": False, "skipped": True, "reason": "blocked_rows", "outputPath": str(reel_output)}
        status = BLOCKED_STATUS
    elif not args.build_reel:
        reel = {"ok": False, "skipped": True, "reason": "run with --build-reel", "outputPath": str(reel_output)}
        status = NEEDS_BUILD_STATUS
        warnings.append("Run with --build-reel to generate transition_watch_reel/transition_watch_reel.mp4.")
    elif not ffmpeg_path:
        reel = {"ok": False, "skipped": True, "reason": "ffmpeg missing", "outputPath": str(reel_output)}
        blockers.append("ffmpeg was not found; cannot build transition watch reel")
        status = BLOCKED_STATUS
    else:
        reel = concat_reel(ready_rows, reel_output, args)
        if reel.get("ok"):
            status = CLOSED_STATUS
        else:
            blockers.append("transition watch reel concat failed")
            status = BLOCKED_STATUS

    summary = {
        "sourceAuditionRowCount": len(all_rows),
        "reelRowCount": len(reel_rows),
        "importantReelRowCount": sum(1 for row in reel_rows if row.get("importantBoundary")),
        "readyReelRowCount": len(ready_rows),
        "blockedReelRowCount": len(blocked_rows),
        "clipCount": sum(1 for row in reel_rows if row.get("exists")),
        "packageLocalClipCount": sum(1 for row in reel_rows if row.get("packageLocal")),
        "mutedClipCount": sum(1 for row in reel_rows if as_int((row.get("probe") or {}).get("audioStreamCount")) == 0 and row.get("exists")),
        "rowsWithBridgeSamples": sum(1 for row in reel_rows if as_int(row.get("bridgeSampleCount")) > 0),
        "rowsWithMotionExecution": sum(1 for row in reel_rows if (row.get("motionExecution") or {}).get("ready") is True),
        "rowsWithSensoryContinuity": sum(1 for row in reel_rows if (row.get("sensoryContinuity") or {}).get("ready") is True),
        "totalReelDurationSeconds": round(sum(as_float(row.get("durationSeconds")) for row in reel_rows), 3),
        "reelBuilt": bool(reel.get("ok") and not reel.get("skipped")),
        "reelOutput": reel.get("outputPath"),
        "qualityStatus": quality.get("status"),
        "storyboardStatus": storyboard.get("status"),
        "buildReel": bool(args.build_reel),
        "requireMuted": bool(args.require_muted),
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
            "transitionStoryboard": str(storyboard_path),
            "transitionStoryboardStatus": storyboard.get("status"),
            "includeAllRows": bool(args.include_all_rows),
            "buildReel": bool(args.build_reel),
            "requireMuted": bool(args.require_muted),
            "ffmpegBin": args.ffmpeg_bin,
            "ffprobeBin": args.ffprobe_bin,
        },
        "summary": summary,
        "reelRows": reel_rows,
        "reel": reel,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "importantTransitionsNeedSingleWatchReel": True,
            "watchReelBuiltFromPackageLocalAuditionClips": True,
            "watchReelMuteRequired": bool(args.require_muted),
            "watchReelIsMuted": bool(args.require_muted),
            "sourceFootageReadOnly": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Watch Reel",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Output: `{report['outputDir']}`",
        f"Reel: `{(report.get('reel') or {}).get('outputPath')}`",
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
    lines.extend(["", "## Watch Order"])
    if not report.get("reelRows"):
        lines.append("- No important transitions.")
    for row in report.get("reelRows", [])[:240]:
        lines.extend(
            [
                "",
                f"### {row.get('reelStartSeconds')}s - Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- Clip: `{row.get('auditionClip')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Purpose: `{row.get('storyboardPurpose')}`",
                f"- Motion: `{(row.get('motionExecution') or {}).get('choreographyFamily')}` / `{(row.get('motionExecution') or {}).get('resolveKeyframeEffect')}`",
                f"- Sensory ready: `{(row.get('sensoryContinuity') or {}).get('ready')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Watch this reel before approving storyboard, Resolve apply, final QA, or V14 handoff.",
            "- The reel is a package-local muted visual review surface for all important transition auditions.",
            "- It does not replace the full final MP4 watchdown; it makes rough adjacent-shot flow visible before handoff.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a package-local transition watch reel from audition clips.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--include-all-rows", action="store_true")
    parser.add_argument("--build-reel", action="store_true")
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--crf", type=int, default=23)
    parser.add_argument("--min-width", type=int, default=120)
    parser.add_argument("--min-height", type=int, default=68)
    parser.add_argument("--min-clip-duration-seconds", type=float, default=1.0)
    parser.add_argument("--require-muted", action="store_true", default=True)
    parser.add_argument("--allow-audio", dest="require_muted", action="store_false")
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    output_dir = Path(report["outputDir"])
    write_json(output_dir / "transition_watch_reel.json", report)
    write_markdown(output_dir / "transition_watch_reel.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {CLOSED_STATUS, NO_TRANSITIONS_STATUS} else 2


if __name__ == "__main__":
    raise SystemExit(main())
