#!/usr/bin/env python3
"""Build short package-local MP4 auditions for important transition rows."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}


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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
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


def resolve_path(package_dir: Path, raw: Any) -> Path | None:
    value = clean(raw, 4000)
    if not value or value.startswith(("http://", "https://")):
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path.resolve()


def safe_slug(value: Any, fallback: str = "transition") -> str:
    text = clean(value, 80).lower().replace(" ", "_") or fallback
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    return slug.strip("_") or fallback


def packet_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("previewRows") if isinstance(packet.get("previewRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def is_important(row: dict[str, Any]) -> bool:
    return bool(row.get("importantBoundary")) or clean(row.get("boundaryCategory")).lower() in IMPORTANT_CATEGORIES


def bridge_visual_clip_reports(report: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    rows = report.get("bridgeRows") if isinstance(report.get("bridgeRows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_index = as_int(row.get("rowIndex"), -1)
        clips = row.get("clipReports") if isinstance(row.get("clipReports"), list) else []
        if row_index >= 0 and clips:
            out[row_index] = [clip for clip in clips if isinstance(clip, dict)]
    return out


def transition_execution_rows(package_dir: Path) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    report_path = package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json"
    report = load_json(report_path) or {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    candidate_path = resolve_path(
        package_dir,
        outputs.get("candidateBlueprint") or package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json",
    )
    candidate = load_json(candidate_path) if candidate_path else {}
    transitions = candidate.get("transitions") if isinstance(candidate, dict) and isinstance(candidate.get("transitions"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in transitions:
        if not isinstance(row, dict):
            continue
        row_index = as_int(row.get("rowIndex"), -1)
        if row_index >= 0:
            out[row_index] = row
    return {
        "reportPath": str(report_path),
        "reportExists": report_path.exists(),
        "reportStatus": report.get("status"),
        "candidatePath": str(candidate_path) if candidate_path else "",
        "candidateExists": bool(candidate_path and candidate_path.exists()),
        "transitionCount": len(out),
    }, out


def motion_execution_for(row_index: int, transition_by_row: dict[int, dict[str, Any]]) -> dict[str, Any]:
    transition = transition_by_row.get(row_index) if isinstance(transition_by_row.get(row_index), dict) else {}
    motion = transition.get("transitionMotionExecution") if isinstance(transition.get("transitionMotionExecution"), dict) else {}
    return motion if isinstance(motion, dict) else {}


def cutpoint_for(row_index: int, transition_by_row: dict[int, dict[str, Any]]) -> dict[str, Any]:
    transition = transition_by_row.get(row_index) if isinstance(transition_by_row.get(row_index), dict) else {}
    cutpoint = transition.get("transitionCutpointPlan") if isinstance(transition.get("transitionCutpointPlan"), dict) else {}
    return cutpoint if isinstance(cutpoint, dict) else {}


def motion_execution_ready(motion: dict[str, Any]) -> bool:
    bgm = motion.get("bgmChoreography") if isinstance(motion.get("bgmChoreography"), dict) else {}
    caption = motion.get("captionAndTitlePolicy") if isinstance(motion.get("captionAndTitlePolicy"), dict) else {}
    safety_checks = motion.get("safetyChecks") if isinstance(motion.get("safetyChecks"), dict) else {}
    direction = motion.get("motionDirectionPlan") if isinstance(motion.get("motionDirectionPlan"), dict) else {}
    direction_ready = direction.get("required") is not True or (
        direction.get("status") == "ready_with_motion_direction_plan"
        and direction.get("directionMatch") is True
        and bool(direction.get("effectDirection"))
        and bool(direction.get("landingDirection"))
    )
    return (
        motion.get("status") == "ready_with_transition_motion_execution"
        and len(motion.get("threeBeatChoreography") or []) >= 3
        and bgm.get("target") == "cut_or_effect_on_bgm_phrase_hit"
        and bgm.get("allowOffPhrase") is False
        and caption.get("avoidTitleCollision") is True
        and caption.get("suppressSubtitlesDuringHeroTitleOrFastMotion") is True
        and safety_checks.get("bgmOnlyNoSourceVoice") is True
        and safety_checks.get("forbidTemplateMotion") is True
        and direction_ready
    )


def motion_execution_summary(motion: dict[str, Any]) -> dict[str, Any]:
    bgm = motion.get("bgmChoreography") if isinstance(motion.get("bgmChoreography"), dict) else {}
    caption = motion.get("captionAndTitlePolicy") if isinstance(motion.get("captionAndTitlePolicy"), dict) else {}
    keyframe = motion.get("resolveKeyframeRecipe") if isinstance(motion.get("resolveKeyframeRecipe"), dict) else {}
    direction = motion.get("motionDirectionPlan") if isinstance(motion.get("motionDirectionPlan"), dict) else {}
    beats = motion.get("threeBeatChoreography") if isinstance(motion.get("threeBeatChoreography"), list) else []
    return {
        "status": motion.get("status"),
        "source": motion.get("source"),
        "choreographyFamily": motion.get("choreographyFamily"),
        "sourceTransitionStyle": motion.get("sourceTransitionStyle"),
        "intensity": motion.get("intensity"),
        "threeBeatCount": len(beats),
        "beatRoles": [clean(beat.get("role")) for beat in beats if isinstance(beat, dict)],
        "bridgeOrMotionAction": next((clean(beat.get("action")) for beat in beats if isinstance(beat, dict) and beat.get("role") == "bridge_or_motion"), ""),
        "bgmHitTarget": bgm.get("target"),
        "bgmAllowsOffPhrase": bgm.get("allowOffPhrase"),
        "captionQuietZone": bool(caption.get("avoidTitleCollision") and caption.get("suppressSubtitlesDuringHeroTitleOrFastMotion")),
        "motionDirectionRequired": direction.get("required") is True,
        "motionDirectionStatus": direction.get("status"),
        "motionDirectionEffect": direction.get("effectDirection"),
        "motionDirectionLanding": direction.get("landingDirection"),
        "motionDirectionMatch": direction.get("directionMatch"),
        "motionDirectionConfidence": direction.get("directionConfidence"),
        "resolveKeyframeEffect": keyframe.get("effect"),
        "ready": motion_execution_ready(motion),
    }


def cutpoint_summary(cutpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": cutpoint.get("status"),
        "ready": cutpoint.get("status") == "ready_with_transition_cutpoint_plan",
        "outgoingTailFrames": cutpoint.get("outgoingTailFrames"),
        "bridgeOrEffectFrames": cutpoint.get("bridgeOrEffectFrames"),
        "landingHoldFrames": cutpoint.get("landingHoldFrames"),
        "handlesReady": cutpoint.get("handlesReady"),
        "bgmHitAligned": cutpoint.get("bgmHitAligned"),
        "bgmHitFrameOffset": cutpoint.get("bgmHitFrameOffset"),
        "titleSubtitleQuietZoneReady": cutpoint.get("titleSubtitleQuietZoneReady"),
        "bgmOnlyNoSourceVoice": cutpoint.get("bgmOnlyNoSourceVoice"),
        "importantBoundary": cutpoint.get("importantBoundary"),
        "importantBoundaryResolved": cutpoint.get("importantBoundaryResolved"),
    }


def normalized_sample(sample: dict[str, Any], package_dir: Path) -> dict[str, Any]:
    source = resolve_path(package_dir, sample.get("sourcePath"))
    return {
        "role": clean(sample.get("role")) or "sample",
        "sourcePath": str(source) if source else clean(sample.get("sourcePath"), 4000),
        "sourceName": clean(sample.get("sourceName")) or (source.name if source else ""),
        "sourceTimeSeconds": as_float(sample.get("sourceTimeSeconds"), 0.5),
        "required": bool(sample.get("required", True)),
        "sourceExists": bool(source and source.exists()),
        "from": "preview_packet",
    }


def bridge_sample_from_clip(clip: dict[str, Any], package_dir: Path) -> dict[str, Any]:
    source = resolve_path(package_dir, clip.get("sourceResolvedPath") or clip.get("sourcePath"))
    start = as_float(clip.get("sourceStartSeconds"), 0.0)
    end_raw = clip.get("sourceEndSeconds")
    end = as_float(end_raw, start + 1.0) if end_raw is not None else start + as_float(clip.get("timelineDurationSeconds"), 1.0)
    midpoint = start + max(0.1, min(max(end - start, 0.2) / 2.0, max(end - start - 0.1, 0.1)))
    return {
        "role": "bridge",
        "sourcePath": str(source) if source else clean(clip.get("sourcePath"), 4000),
        "sourceName": clean(clip.get("sourceName")) or (source.name if source else ""),
        "sourceTimeSeconds": round(midpoint, 3),
        "beatFunction": clean(clip.get("beatFunction")),
        "required": True,
        "sourceExists": bool(source and source.exists()),
        "from": "transition_bridge_visual_evidence",
    }


def ordered_samples(row: dict[str, Any], package_dir: Path, bridge_by_row: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    samples = [normalized_sample(sample, package_dir) for sample in row.get("samples", []) if isinstance(sample, dict)]
    outgoing = [sample for sample in samples if sample["role"] == "outgoing"]
    landing = [sample for sample in samples if sample["role"] == "landing"]
    preview_bridge = [sample for sample in samples if sample["role"] == "bridge"]
    bridge_samples = [bridge_sample_from_clip(clip, package_dir) for clip in bridge_by_row.get(as_int(row.get("rowIndex")), [])]
    if not bridge_samples:
        bridge_samples = preview_bridge
    return outgoing[:1] + bridge_samples[:4] + landing[:1]


def segment_start(sample: dict[str, Any], role_seconds: float) -> float:
    time_value = as_float(sample.get("sourceTimeSeconds"), 0.5)
    if sample.get("role") == "outgoing":
        return max(0.0, time_value - max(0.2, role_seconds * 0.75))
    return max(0.0, time_value - 0.1)


def run_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, check=False, text=True, capture_output=True)
    except Exception:
        return None


def render_segment(
    *,
    sample: dict[str, Any],
    output_path: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    duration = args.bridge_seconds if sample.get("role") == "bridge" else args.edge_seconds
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
        "-ss",
        str(round(segment_start(sample, duration), 3)),
        "-t",
        str(round(duration, 3)),
        "-i",
        str(sample["sourcePath"]),
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(command)
    ok = bool(result and result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0)
    return {
        "ok": ok,
        "outputPath": str(output_path),
        "durationSeconds": duration,
        "command": command,
        "returnCode": result.returncode if result else None,
        "stderr": clean(result.stderr if result else "ffmpeg failed to start", 1200),
    }


def concat_segments(segment_paths: list[Path], output_path: Path, ffmpeg_bin: str) -> dict[str, Any]:
    concat_file = output_path.with_suffix(".concat.txt")
    concat_file.parent.mkdir(parents=True, exist_ok=True)
    concat_file.write_text("".join(f"file '{path.as_posix()}'\n" for path in segment_paths), encoding="utf-8")
    command = [
        ffmpeg_bin,
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
        "-c",
        "copy",
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
        "stderr": clean(result.stderr if result else "ffmpeg failed to start", 1200),
    }


def row_dir(output_dir: Path, row_index: int, category: str) -> Path:
    return output_dir / f"row_{row_index:03d}_{safe_slug(category)}"


def build_row(
    row: dict[str, Any],
    *,
    package_dir: Path,
    output_dir: Path,
    bridge_by_row: dict[int, list[dict[str, Any]]],
    transition_by_row: dict[int, dict[str, Any]],
    args: argparse.Namespace,
    ffmpeg_available: bool,
) -> dict[str, Any]:
    row_index = as_int(row.get("rowIndex"))
    category = clean(row.get("boundaryCategory")).lower()
    samples = ordered_samples(row, package_dir, bridge_by_row)
    motion_execution = motion_execution_for(row_index, transition_by_row)
    motion_summary = motion_execution_summary(motion_execution)
    cutpoint = cutpoint_for(row_index, transition_by_row)
    cutpoint_row_summary = cutpoint_summary(cutpoint)
    out_dir = row_dir(output_dir, row_index, category)
    issues: list[str] = []
    warnings: list[str] = []
    if not motion_execution:
        issues.append("missing_transition_motion_execution")
    elif not motion_execution_ready(motion_execution):
        issues.append("transition_motion_execution_not_ready_for_audition")
    if not cutpoint:
        issues.append("missing_transition_cutpoint_plan")
    elif cutpoint.get("status") != "ready_with_transition_cutpoint_plan":
        issues.append("transition_cutpoint_plan_not_ready_for_audition")
    if not any(sample["role"] == "outgoing" for sample in samples):
        issues.append("missing_outgoing_sample")
    if not any(sample["role"] == "landing" for sample in samples):
        issues.append("missing_landing_sample")
    for sample in samples:
        if sample.get("required") and not sample.get("sourceExists"):
            issues.append(f"{sample.get('role')}_source_missing:{sample.get('sourcePath')}")
    if not any(sample["role"] == "bridge" for sample in samples) and is_important(row):
        warnings.append("important_transition_has_no_bridge_sample_in_audition")
    segment_reports: list[dict[str, Any]] = []
    segment_paths: list[Path] = []
    audition_path = out_dir / "transition_audition.mp4"
    if args.build_clips and not ffmpeg_available:
        issues.append("ffmpeg_missing_for_audition_build")
    if args.build_clips and ffmpeg_available and not issues:
        for index, sample in enumerate(samples, start=1):
            segment_path = out_dir / f"segment_{index:02d}_{safe_slug(sample.get('role'), 'sample')}.mp4"
            report = render_segment(sample=sample, output_path=segment_path, args=args)
            segment_reports.append({**sample, "segment": report})
            if report.get("ok"):
                segment_paths.append(segment_path)
            else:
                issues.append(f"{sample.get('role')}_segment_render_failed")
        if not issues and segment_paths:
            concat_report = concat_segments(segment_paths, audition_path, args.ffmpeg_bin)
            if not concat_report.get("ok"):
                issues.append("audition_concat_failed")
        else:
            concat_report = {"ok": False, "skipped": True, "outputPath": str(audition_path)}
    else:
        for sample in samples:
            segment_reports.append({**sample, "segment": {"ok": False, "plannedOnly": True}})
        concat_report = {"ok": False, "plannedOnly": True, "outputPath": str(audition_path)}
    md_path = out_dir / "transition_audition.md"
    if not args.build_clips and not issues:
        status = "needs_audition_build"
    elif issues:
        status = "blocked"
    else:
        status = "ready_with_transition_audition"
    row_report = {
        "rowIndex": row_index,
        "boundaryCategory": category,
        "importantBoundary": is_important(row),
        "status": status,
        "storyboardPurpose": clean(row.get("storyboardPurpose")),
        "fromSourceName": clean(row.get("fromSourceName")),
        "toSourceName": clean(row.get("toSourceName")),
        "motionExecution": motion_summary,
        "cutpoint": cutpoint_row_summary,
        "auditionClip": str(audition_path),
        "auditionMarkdown": str(md_path),
        "sampleCount": len(samples),
        "bridgeSampleCount": sum(1 for sample in samples if sample.get("role") == "bridge"),
        "segmentReports": segment_reports,
        "concat": concat_report,
        "issues": issues,
        "warnings": warnings,
    }
    write_row_markdown(md_path, row_report)
    return row_report


def write_row_markdown(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# Transition Audition Row {row['rowIndex']}",
        "",
        f"Status: `{row['status']}`",
        f"Boundary: `{row['boundaryCategory']}`",
        f"Purpose: `{row.get('storyboardPurpose')}`",
        f"From: `{row.get('fromSourceName')}`",
        f"To: `{row.get('toSourceName')}`",
        f"Motion execution: `{(row.get('motionExecution') or {}).get('status')}` / `{(row.get('motionExecution') or {}).get('choreographyFamily')}` / `{(row.get('motionExecution') or {}).get('resolveKeyframeEffect')}`",
        f"Bridge/motion action: {(row.get('motionExecution') or {}).get('bridgeOrMotionAction')}",
        f"Audition: `{row.get('auditionClip')}`",
        "",
        "## Samples",
    ]
    for sample in row.get("segmentReports") or []:
        segment = sample.get("segment") if isinstance(sample.get("segment"), dict) else {}
        lines.extend(
            [
                "",
                f"- Role: `{sample.get('role')}`",
                f"  Source: `{sample.get('sourcePath')}`",
                f"  Source time: `{sample.get('sourceTimeSeconds')}`",
                f"  Segment: `{segment.get('outputPath')}`",
            ]
        )
    if row.get("issues"):
        lines.extend(["", "## Issues"])
        lines.extend(f"- {item}" for item in row["issues"])
    if row.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in row["warnings"])
    lines.extend(
        [
            "",
            "## Contract",
            "- Watch this short MP4 before storyboard or Resolve apply approval.",
            "- It is muted by design; source-camera audio must not leak into transition auditions.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_audition_packet"
    packet_path = package_dir / "transition_preview_packet" / "transition_preview_packet.json"
    preview_quality_path = package_dir / "transition_preview_quality_contract_audit.json"
    bridge_visual_path = package_dir / "transition_bridge_visual_evidence_contract_audit.json"
    packet = load_json(packet_path) or {}
    preview_quality = load_json(preview_quality_path) or {}
    bridge_visual = load_json(bridge_visual_path) or {}
    execution_input, transition_by_row = transition_execution_rows(package_dir)
    ffmpeg_path = shutil.which(args.ffmpeg_bin) if not Path(args.ffmpeg_bin).exists() else args.ffmpeg_bin
    ffmpeg_available = bool(ffmpeg_path)
    if ffmpeg_path:
        args.ffmpeg_bin = ffmpeg_path
    rows = packet_rows(packet)
    selected = [row for row in rows if args.include_all_rows or is_important(row)]
    if args.max_rows:
        selected = selected[: args.max_rows]
    bridge_by_row = bridge_visual_clip_reports(bridge_visual)
    audition_rows = [
        build_row(
            row,
            package_dir=package_dir,
            output_dir=output_dir,
            bridge_by_row=bridge_by_row,
            transition_by_row=transition_by_row,
            args=args,
            ffmpeg_available=ffmpeg_available,
        )
        for row in selected
    ]
    ready_rows = [row for row in audition_rows if row.get("status") == "ready_with_transition_audition"]
    blocked_rows = [row for row in audition_rows if row.get("status") == "blocked"]
    needs_rows = [row for row in audition_rows if row.get("status") == "needs_audition_build"]
    blockers: list[str] = []
    warnings: list[str] = []
    if not packet_path.exists():
        blockers.append("missing transition_preview_packet/transition_preview_packet.json")
    if packet.get("status") not in {"ready_with_transition_preview_packet", "ready_no_important_transitions"}:
        blockers.append(f"transition preview packet status is {packet.get('status')}")
    if preview_quality_path.exists() and preview_quality.get("status") != "passed":
        blockers.append(f"transition preview quality status is {preview_quality.get('status')}")
    if execution_input.get("reportStatus") != "ready_with_transition_execution_blueprint":
        blockers.append(f"transition execution blueprint status is {execution_input.get('reportStatus')}")
    if not execution_input.get("candidateExists"):
        blockers.append("missing transition execution candidate blueprint for motion-aware auditions")
    if selected and args.build_clips and not ffmpeg_available:
        blockers.append("ffmpeg was not found; cannot build transition auditions")
    blockers.extend(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[: args.max_blocked_rows_in_report])
    warnings.extend(warning for row in audition_rows for warning in row.get("warnings") or [])
    if needs_rows:
        warnings.append("Run with --build-clips to render package-local transition audition MP4 files.")
    if rows and not selected:
        status = "ready_no_important_transitions"
    elif blockers or blocked_rows:
        status = "blocked_transition_audition_packet"
    elif needs_rows:
        status = "needs_audition_build"
    elif ready_rows and len(ready_rows) == len(audition_rows):
        status = "ready_with_transition_audition_packet"
    else:
        status = "needs_audition_build"
    summary = {
        "transitionPreviewRowCount": len(rows),
        "auditionRowCount": len(audition_rows),
        "importantAuditionRowCount": sum(1 for row in audition_rows if row.get("importantBoundary")),
        "readyAuditionRowCount": len(ready_rows),
        "blockedAuditionRowCount": len(blocked_rows),
        "needsBuildAuditionRowCount": len(needs_rows),
        "auditionClipCount": sum(1 for row in ready_rows if Path(str(row.get("auditionClip"))).exists()),
        "rowsWithBridgeSamples": sum(1 for row in audition_rows if as_int(row.get("bridgeSampleCount")) > 0),
        "rowsWithMotionExecution": sum(1 for row in audition_rows if ((row.get("motionExecution") or {}).get("ready") is True)),
        "rowsWithThreeBeatMotion": sum(1 for row in audition_rows if as_int((row.get("motionExecution") or {}).get("threeBeatCount")) >= 3),
        "rowsWithBgmHitMotion": sum(1 for row in audition_rows if (row.get("motionExecution") or {}).get("bgmHitTarget") == "cut_or_effect_on_bgm_phrase_hit" and (row.get("motionExecution") or {}).get("bgmAllowsOffPhrase") is False),
        "rowsWithCaptionQuietMotion": sum(1 for row in audition_rows if (row.get("motionExecution") or {}).get("captionQuietZone") is True),
        "rowsWithMotionDirection": sum(1 for row in audition_rows if (row.get("motionExecution") or {}).get("motionDirectionRequired") is not True or (row.get("motionExecution") or {}).get("motionDirectionStatus") == "ready_with_motion_direction_plan"),
        "rowsWithMotionDirectionMatch": sum(1 for row in audition_rows if (row.get("motionExecution") or {}).get("motionDirectionRequired") is not True or (row.get("motionExecution") or {}).get("motionDirectionMatch") is True),
        "rowsWithCutpoint": sum(1 for row in audition_rows if (row.get("cutpoint") or {}).get("ready") is True),
        "rowsWithCutpointBgm": sum(1 for row in audition_rows if (row.get("cutpoint") or {}).get("bgmHitAligned") is True),
        "rowsWithCutpointLanding": sum(1 for row in audition_rows if as_int((row.get("cutpoint") or {}).get("landingHoldFrames")) >= (10 if (row.get("cutpoint") or {}).get("importantBoundary") else 6)),
        "rowsWithCutpointHandles": sum(1 for row in audition_rows if (row.get("cutpoint") or {}).get("handlesReady") is True),
        "motionExecutionChoreographyFamilyCounts": {
            family: sum(1 for row in audition_rows if (row.get("motionExecution") or {}).get("choreographyFamily") == family)
            for family in sorted({str((row.get("motionExecution") or {}).get("choreographyFamily") or "") for row in audition_rows if (row.get("motionExecution") or {}).get("choreographyFamily")})
        },
        "ffmpegAvailable": ffmpeg_available,
        "buildClips": bool(args.build_clips),
        "builtClips": bool(args.build_clips),
        "edgeSeconds": args.edge_seconds,
        "bridgeSeconds": args.bridge_seconds,
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {
            "transitionPreviewPacket": str(packet_path),
            "transitionPreviewPacketStatus": packet.get("status"),
            "transitionPreviewQuality": str(preview_quality_path),
            "transitionPreviewQualityStatus": preview_quality.get("status"),
            "transitionBridgeVisualEvidence": str(bridge_visual_path),
            "transitionBridgeVisualEvidenceStatus": bridge_visual.get("status"),
            "transitionExecutionBlueprint": execution_input,
            "includeAllRows": bool(args.include_all_rows),
            "buildClips": bool(args.build_clips),
            "ffmpegBin": args.ffmpeg_bin,
        },
        "summary": summary,
        "auditionRows": audition_rows,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "importantTransitionsNeedWatchableAuditions": True,
            "auditionsMustCarryTransitionMotionExecution": True,
            "auditionsAreMuted": True,
            "sourceFootageReadOnly": True,
            "packageLocalEvidence": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Audition Packet",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Output: `{report['outputDir']}`",
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
    for row in report["auditionRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- Motion execution: `{(row.get('motionExecution') or {}).get('status')}` / `{(row.get('motionExecution') or {}).get('choreographyFamily')}`",
                f"- Audition: `{row.get('auditionClip')}`",
                f"- Bridge samples: `{row.get('bridgeSampleCount')}`",
                f"- Review: `{row.get('auditionMarkdown')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Safety",
            "- Writes only package-local muted MP4 audition files and markdown.",
            "- Does not write Resolve, queue renders, download assets, modify source footage, or modify source drives.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build transition audition MP4 packets for important boundaries.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--include-all-rows", action="store_true")
    parser.add_argument("--build-clips", action="store_true")
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--edge-seconds", type=float, default=0.9)
    parser.add_argument("--bridge-seconds", type=float, default=0.8)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--crf", type=int, default=23)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    output_dir = Path(report["outputDir"])
    write_json(output_dir / "transition_audition_packet.json", report)
    write_markdown(output_dir / "transition_audition_packet.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"ready_with_transition_audition_packet", "ready_no_important_transitions"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
