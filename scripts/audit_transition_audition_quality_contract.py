#!/usr/bin/env python3
"""Audit transition audition MP4 clips for playable visual transition evidence."""

from __future__ import annotations

import argparse
import json
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


def run_probe(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, check=False, text=True, capture_output=True)
    except Exception:
        return None


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
    result = run_probe(command)
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


def packet_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("auditionRows") if isinstance(packet.get("auditionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def audit_row(row: dict[str, Any], package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    clip_path = resolve_package_path(package_dir, row.get("auditionClip"))
    issues: list[str] = []
    warnings: list[str] = []
    motion = row.get("motionExecution") if isinstance(row.get("motionExecution"), dict) else {}
    cutpoint = row.get("cutpoint") if isinstance(row.get("cutpoint"), dict) else {}
    action_anchor = row.get("actionAnchor") if isinstance(row.get("actionAnchor"), dict) else {}
    sensory = row.get("sensoryContinuity") if isinstance(row.get("sensoryContinuity"), dict) else {}
    if row.get("status") != "ready_with_transition_audition":
        issues.append("audition_row_not_ready")
    if motion.get("ready") is not True:
        issues.append("motion_execution_not_ready")
    if as_int(motion.get("threeBeatCount")) < 3:
        issues.append("motion_execution_missing_three_beat_choreography")
    if motion.get("bgmHitTarget") != "cut_or_effect_on_bgm_phrase_hit" or motion.get("bgmAllowsOffPhrase") is not False:
        issues.append("motion_execution_missing_bgm_hit_policy")
    if motion.get("captionQuietZone") is not True:
        issues.append("motion_execution_missing_caption_title_quiet_zone")
    if motion.get("motionDirectionRequired") is True:
        if motion.get("motionDirectionStatus") != "ready_with_motion_direction_plan":
            issues.append("motion_execution_missing_motion_direction_plan")
        if motion.get("motionDirectionMatch") is not True:
            issues.append("motion_execution_direction_not_matched")
        if not motion.get("motionDirectionEffect") or not motion.get("motionDirectionLanding"):
            issues.append("motion_execution_missing_effect_or_landing_direction")
    if not motion.get("resolveKeyframeEffect"):
        issues.append("motion_execution_missing_resolve_keyframe_effect")
    if cutpoint.get("ready") is not True:
        issues.append("cutpoint_plan_not_ready")
    if cutpoint.get("bgmHitAligned") is not True:
        issues.append("cutpoint_missing_bgm_hit_alignment")
    if as_int(cutpoint.get("landingHoldFrames")) < (10 if cutpoint.get("importantBoundary") else 6):
        issues.append("cutpoint_landing_hold_too_short")
    if cutpoint.get("handlesReady") is not True:
        issues.append("cutpoint_source_handles_not_ready")
    if cutpoint.get("titleSubtitleQuietZoneReady") is not True:
        issues.append("cutpoint_title_subtitle_quiet_zone_not_ready")
    if cutpoint.get("bgmOnlyNoSourceVoice") is not True:
        issues.append("cutpoint_audio_not_bgm_only")
    if action_anchor.get("ready") is not True:
        issues.append("action_anchor_plan_not_ready")
    if action_anchor.get("outgoingReady") is not True:
        issues.append("action_anchor_missing_outgoing")
    if action_anchor.get("bridgeOrMatchReady") is not True:
        issues.append("action_anchor_missing_bridge_or_match")
    if action_anchor.get("landingReady") is not True:
        issues.append("action_anchor_missing_landing")
    if action_anchor.get("directionalMotionAnchorReady") is not True:
        issues.append("action_anchor_missing_directional_motion")
    if action_anchor.get("importantBoundary") is True and action_anchor.get("importantBoundaryResolved") is not True:
        issues.append("action_anchor_important_boundary_not_resolved")
    if sensory.get("ready") is not True:
        issues.append("sensory_continuity_not_ready")
    if sensory.get("visualReady") is not True:
        issues.append("sensory_continuity_missing_visual_channel")
    if sensory.get("audioReady") is not True:
        issues.append("sensory_continuity_missing_audio_channel")
    if sensory.get("captionQuietReady") is not True:
        issues.append("sensory_continuity_missing_caption_quiet_channel")
    if sensory.get("landingReady") is not True:
        issues.append("sensory_continuity_missing_landing_channel")
    if sensory.get("importantBoundary") is True and sensory.get("routeOrMoodReady") is not True:
        issues.append("sensory_continuity_missing_important_route_or_mood_channel")
    if motion.get("motionDirectionRequired") is True and sensory.get("motionReady") is not True:
        issues.append("sensory_continuity_missing_motion_channel")
    if sensory.get("bgmOnlyNoSourceVoice") is not True:
        issues.append("sensory_continuity_audio_not_bgm_only")
    if sensory.get("actionAnchorReady") is not True:
        issues.append("sensory_continuity_action_anchor_not_ready")
    if sensory.get("cutpointReady") is not True:
        issues.append("sensory_continuity_cutpoint_not_ready")
    if not clip_path:
        issues.append("audition_clip_path_missing")
        probe = {"ok": False}
        exists = False
        package_local = False
        file_size = 0
    else:
        exists = clip_path.exists()
        package_local = is_inside(clip_path, package_dir)
        file_size = clip_path.stat().st_size if exists else 0
        if not exists:
            issues.append("audition_clip_missing")
            probe = {"ok": False}
        else:
            probe = ffprobe_media(clip_path, args.ffprobe_bin)
            if not probe.get("ok"):
                issues.append("audition_clip_not_probeable_video")
            if as_float(probe.get("durationSeconds")) < args.min_duration_seconds:
                issues.append("audition_clip_too_short")
            if as_int(probe.get("width")) < args.min_width or as_int(probe.get("height")) < args.min_height:
                issues.append("audition_clip_too_small")
            if args.require_no_audio and as_int(probe.get("audioStreamCount")) > 0:
                issues.append("audition_clip_has_audio_stream")
            if not package_local:
                issues.append("audition_clip_outside_package")
    if as_int(row.get("bridgeSampleCount")) == 0 and row.get("importantBoundary"):
        warnings.append("important_transition_audition_has_no_bridge_sample")
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": clean(row.get("boundaryCategory")),
        "importantBoundary": bool(row.get("importantBoundary")),
        "status": "blocked" if issues else "passed",
        "auditionClip": str(clip_path) if clip_path else None,
        "exists": exists,
        "packageLocal": package_local,
        "fileSizeBytes": file_size,
        "bridgeSampleCount": row.get("bridgeSampleCount"),
        "motionExecution": motion,
        "cutpoint": cutpoint,
        "actionAnchor": action_anchor,
        "sensoryContinuity": sensory,
        "probe": probe,
        "issues": issues,
        "warnings": warnings,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    packet_path = package_dir / "transition_audition_packet" / "transition_audition_packet.json"
    packet = load_json(packet_path) or {}
    packet_summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    packet_inputs = packet.get("inputs") if isinstance(packet.get("inputs"), dict) else {}
    packet_policy = packet.get("policy") if isinstance(packet.get("policy"), dict) else {}
    rows = packet_rows(packet)
    audited = [audit_row(row, package_dir, args) for row in rows]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    warnings = [warning for row in audited for warning in row.get("warnings") or []]
    blockers: list[str] = []
    if not packet_path.exists():
        blockers.append("missing transition_audition_packet/transition_audition_packet.json")
    if packet.get("status") not in {"ready_with_transition_audition_packet", "ready_no_important_transitions"}:
        blockers.append(f"transition audition packet status is {packet.get('status')}")
    if packet_summary.get("buildClips") is not True:
        blockers.append("transition audition packet summary.buildClips is not true; rerun prepare_transition_audition_packet.py --build-clips")
    if packet_summary.get("builtClips") is not True:
        blockers.append("transition audition packet summary.builtClips is not true; rerun prepare_transition_audition_packet.py --build-clips")
    if packet_inputs.get("buildClips") is not True:
        blockers.append("transition audition packet inputs.buildClips is not true; rerun prepare_transition_audition_packet.py --build-clips")
    if args.require_no_audio:
        if packet_summary.get("auditionsAreMuted") is not True:
            blockers.append("transition audition packet summary.auditionsAreMuted is not true; rerun prepare_transition_audition_packet.py --build-clips")
        if packet_summary.get("sourceAudioStripped") is not True:
            blockers.append("transition audition packet summary.sourceAudioStripped is not true; rerun prepare_transition_audition_packet.py --build-clips")
        if packet_inputs.get("auditionsAreMuted") is not True:
            blockers.append("transition audition packet inputs.auditionsAreMuted is not true; rerun prepare_transition_audition_packet.py --build-clips")
        if packet_policy.get("auditionsAreMuted") is not True:
            blockers.append("transition audition packet policy.auditionsAreMuted is not true; rerun prepare_transition_audition_packet.py --build-clips")
        if packet_policy.get("sourceAudioStrippedWithFfmpegAn") is not True:
            blockers.append("transition audition packet policy.sourceAudioStrippedWithFfmpegAn is not true; rerun prepare_transition_audition_packet.py --build-clips")
    for row in blocked[: args.max_blocked_rows_in_report]:
        blockers.append(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}")
    summary = {
        "transitionAuditionPacketStatus": packet.get("status"),
        "packetAuditionsAreMuted": packet_summary.get("auditionsAreMuted"),
        "packetSourceAudioStripped": packet_summary.get("sourceAudioStripped"),
        "packetSummaryBuildClips": packet_summary.get("buildClips"),
        "packetSummaryBuiltClips": packet_summary.get("builtClips"),
        "packetInputBuildClips": packet_inputs.get("buildClips"),
        "packetInputAuditionsAreMuted": packet_inputs.get("auditionsAreMuted"),
        "packetPolicyAuditionsAreMuted": packet_policy.get("auditionsAreMuted"),
        "packetPolicySourceAudioStrippedWithFfmpegAn": packet_policy.get("sourceAudioStrippedWithFfmpegAn"),
        "auditionRowCount": len(audited),
        "importantAuditionRowCount": sum(1 for row in audited if row.get("importantBoundary")),
        "auditionQualityReadyRowCount": len(audited) - len(blocked),
        "blockedAuditionQualityRowCount": len(blocked),
        "auditionClipCount": sum(1 for row in audited if row.get("exists")),
        "probeReadyClipCount": sum(1 for row in audited if (row.get("probe") or {}).get("ok")),
        "noAudioClipCount": sum(1 for row in audited if as_int((row.get("probe") or {}).get("audioStreamCount")) == 0 and row.get("exists")),
        "rowsWithBridgeSamples": sum(1 for row in audited if as_int(row.get("bridgeSampleCount")) > 0),
        "rowsWithMotionExecution": sum(1 for row in audited if (row.get("motionExecution") or {}).get("ready") is True),
        "rowsWithThreeBeatMotion": sum(1 for row in audited if as_int((row.get("motionExecution") or {}).get("threeBeatCount")) >= 3),
        "rowsWithBgmHitMotion": sum(1 for row in audited if (row.get("motionExecution") or {}).get("bgmHitTarget") == "cut_or_effect_on_bgm_phrase_hit" and (row.get("motionExecution") or {}).get("bgmAllowsOffPhrase") is False),
        "rowsWithCaptionQuietMotion": sum(1 for row in audited if (row.get("motionExecution") or {}).get("captionQuietZone") is True),
        "rowsWithMotionDirection": sum(1 for row in audited if (row.get("motionExecution") or {}).get("motionDirectionRequired") is not True or (row.get("motionExecution") or {}).get("motionDirectionStatus") == "ready_with_motion_direction_plan"),
        "rowsWithMotionDirectionMatch": sum(1 for row in audited if (row.get("motionExecution") or {}).get("motionDirectionRequired") is not True or (row.get("motionExecution") or {}).get("motionDirectionMatch") is True),
        "rowsWithCutpoint": sum(1 for row in audited if (row.get("cutpoint") or {}).get("ready") is True),
        "rowsWithCutpointBgm": sum(1 for row in audited if (row.get("cutpoint") or {}).get("bgmHitAligned") is True),
        "rowsWithCutpointLanding": sum(1 for row in audited if as_int((row.get("cutpoint") or {}).get("landingHoldFrames")) >= (10 if (row.get("cutpoint") or {}).get("importantBoundary") else 6)),
        "rowsWithCutpointHandles": sum(1 for row in audited if (row.get("cutpoint") or {}).get("handlesReady") is True),
        "rowsWithActionAnchor": sum(1 for row in audited if (row.get("actionAnchor") or {}).get("ready") is True),
        "rowsWithOutgoingActionAnchor": sum(1 for row in audited if (row.get("actionAnchor") or {}).get("outgoingReady") is True),
        "rowsWithBridgeOrMatchActionAnchor": sum(1 for row in audited if (row.get("actionAnchor") or {}).get("bridgeOrMatchReady") is True),
        "rowsWithLandingActionAnchor": sum(1 for row in audited if (row.get("actionAnchor") or {}).get("landingReady") is True),
        "rowsWithDirectionalActionAnchor": sum(1 for row in audited if (row.get("actionAnchor") or {}).get("directionalMotionAnchorReady") is True),
        "rowsWithSensoryContinuity": sum(1 for row in audited if (row.get("sensoryContinuity") or {}).get("ready") is True),
        "rowsWithVisualSensoryContinuity": sum(1 for row in audited if (row.get("sensoryContinuity") or {}).get("visualReady") is True),
        "rowsWithAudioSensoryContinuity": sum(1 for row in audited if (row.get("sensoryContinuity") or {}).get("audioReady") is True),
        "rowsWithCaptionSensoryContinuity": sum(1 for row in audited if (row.get("sensoryContinuity") or {}).get("captionQuietReady") is True),
        "rowsWithRouteOrMoodSensoryContinuity": sum(1 for row in audited if (row.get("sensoryContinuity") or {}).get("routeOrMoodReady") is True),
        "rowsWithLandingSensoryContinuity": sum(1 for row in audited if (row.get("sensoryContinuity") or {}).get("landingReady") is True),
        "rowsWithMotionSensoryContinuity": sum(1 for row in audited if (row.get("sensoryContinuity") or {}).get("motionReady") is True),
        "rowsWithResolveKeyframeEffect": sum(1 for row in audited if bool((row.get("motionExecution") or {}).get("resolveKeyframeEffect"))),
        "warningCount": len(warnings),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers and not blocked else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "transitionAuditionPacket": str(packet_path),
            "transitionAuditionPacketStatus": packet.get("status"),
            "packetInputAuditionsAreMuted": packet_inputs.get("auditionsAreMuted"),
            "minDurationSeconds": args.min_duration_seconds,
            "minWidth": args.min_width,
            "minHeight": args.min_height,
            "requireNoAudio": bool(args.require_no_audio),
            "ffprobeBin": args.ffprobe_bin,
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "watchableAuditionClipsRequired": True,
            "motionExecutionRequired": True,
            "sensoryContinuityRequired": True,
            "threeBeatBgmHitCaptionQuietRequired": True,
            "auditionClipsMustBePackageLocal": True,
            "auditionClipsMustBeMuted": bool(args.require_no_audio),
            "ffprobeEvidenceRequired": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Audition Quality Contract Audit",
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
    for row in report["auditedRows"][:160]:
        probe = row.get("probe") if isinstance(row.get("probe"), dict) else {}
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- Clip: `{row.get('auditionClip')}`",
                f"- Motion execution: `{(row.get('motionExecution') or {}).get('status')}` / `{(row.get('motionExecution') or {}).get('choreographyFamily')}` / `{(row.get('motionExecution') or {}).get('resolveKeyframeEffect')}`",
                f"- Sensory continuity: `{(row.get('sensoryContinuity') or {}).get('status')}` / channels `{(row.get('sensoryContinuity') or {}).get('cueChannelCount')}` of `{(row.get('sensoryContinuity') or {}).get('requiredCueChannelCount')}`",
                f"- Duration: `{probe.get('durationSeconds')}`",
                f"- Size: `{probe.get('width')}x{probe.get('height')}`",
                f"- Audio streams: `{probe.get('audioStreamCount')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Important transition auditions must be playable package-local MP4s.",
            "- Auditions are muted visual proof; source-camera audio in audition files is blocked.",
            "- Passing this contract does not replace final Resolve render QA; it proves pre-Resolve transition flow is inspectable.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition audition MP4 quality.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--min-duration-seconds", type=float, default=1.5)
    parser.add_argument("--min-width", type=int, default=120)
    parser.add_argument("--min-height", type=int, default=68)
    parser.add_argument("--require-no-audio", action="store_true", default=True)
    parser.add_argument("--allow-audio", dest="require_no_audio", action="store_false")
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_audition_quality_contract_audit.json", report)
    write_markdown(package_dir / "transition_audition_quality_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
