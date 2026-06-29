#!/usr/bin/env python3
"""Audit that important transition bridge beats have concrete visual evidence."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
IMPORTANT_SEQUENCE_TYPES = {
    "clean_title_bridge_sequence",
    "route_texture_bridge_sequence",
    "ending_aftertaste_sequence",
}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts", ".m2ts", ".webm"}
SOURCE_START_KEYS = ("sourceStartSeconds", "sourceInSeconds", "sourceIn", "inPointSeconds")
SOURCE_END_KEYS = ("sourceEndSeconds", "sourceOutSeconds", "sourceOut", "outPointSeconds")


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


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


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


def pick_first_float(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = as_float(row.get(key))
        if value is not None:
            return value
    return None


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def source_start(clip: dict[str, Any]) -> float:
    return pick_first_float(clip, SOURCE_START_KEYS) or 0.0


def source_end(clip: dict[str, Any]) -> float | None:
    explicit = pick_first_float(clip, SOURCE_END_KEYS)
    if explicit is not None and explicit > source_start(clip):
        return explicit
    duration = as_float(clip.get("sourceDurationSeconds") or clip.get("durationSeconds"))
    if duration is not None and duration > 0:
        return source_start(clip) + duration
    return None


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def source_path_text(clip: dict[str, Any]) -> str:
    return clean(clip.get("sourcePath") or clip.get("path") or clip.get("mediaPath"), 4000)


def choose_blueprint(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path, str, bool]:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = package_dir / path
        path = path.resolve()
        return load_json(path), path, "explicit_blueprint", is_inside(path, package_dir)
    candidates = [
        (package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json", "candidateBlueprint", "transition_polish_candidate"),
        (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json", "candidateBlueprint", "rhythm_recut_candidate"),
        (package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json", "candidateBlueprint", "bgm_phrase_candidate"),
        (package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json", "candidateBlueprint", "effect_motion_candidate"),
        (package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json", "candidateBlueprint", "transition_execution_candidate"),
        (package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json", "candidateBlueprint", "bridge_sequence_candidate"),
    ]
    for report_path, output_key, kind in candidates:
        report = load_json(report_path) or {}
        outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
        raw = outputs.get(output_key)
        if not raw or not str(report.get("status") or "").startswith("ready"):
            continue
        path = Path(str(raw)).expanduser()
        if not path.is_absolute():
            path = package_dir / path
        path = path.resolve()
        data = load_json(path)
        if isinstance(data, dict):
            return data, path, kind, is_inside(path, package_dir)
    active = (package_dir / "resolve_timeline_blueprint.json").resolve()
    return load_json(active), active, "active_blueprint", is_inside(active, package_dir)


def bridge_sequence_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("sequenceRows") if isinstance(plan.get("sequenceRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def is_required_sequence_row(row: dict[str, Any]) -> bool:
    if row.get("status") not in {"ready_with_bridge_sequence", "materialized", "passed", "ready"}:
        return False
    if row.get("boundaryCategory") in IMPORTANT_CATEGORIES:
        return True
    if row.get("sequenceType") in IMPORTANT_SEQUENCE_TYPES:
        return True
    beats = row.get("requiredBeats") if isinstance(row.get("requiredBeats"), list) else []
    return len(beats) >= 3


def expected_functions(row: dict[str, Any]) -> list[str]:
    beats = row.get("requiredBeats") if isinstance(row.get("requiredBeats"), list) else []
    return [clean(beat.get("function")) for beat in beats if isinstance(beat, dict) and clean(beat.get("function"))]


def bridge_insert_payload(clip: dict[str, Any]) -> dict[str, Any]:
    payload = clip.get("bridgeSequence") if isinstance(clip.get("bridgeSequence"), dict) else {}
    if payload:
        return payload
    return {
        "sourceSequenceRowIndex": clip.get("sourceSequenceRowIndex") or clip.get("bridgeSequenceRowIndex"),
        "beatFunction": clip.get("beatFunction") or clip.get("bridgeBeatFunction"),
        "beatIndex": clip.get("beatIndex") or clip.get("bridgeBeatIndex"),
    }


def bridge_insert_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: list[dict[str, Any]] = []
    for clip in rows:
        if not isinstance(clip, dict):
            continue
        payload = bridge_insert_payload(clip)
        text = " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "sourcePath", "sourceName")).lower()
        if clip.get("role") == "bridge_sequence_insert" or payload.get("kind") == "bridge_sequence_insert" or "bridge sequence beat" in text:
            out.append(clip)
    return sorted(out, key=lambda item: (timeline_start(item), as_int(item.get("trackIndex"), 1), source_name(source_path_text(item))))


def run_probe(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(command, check=False, text=True, capture_output=True)
    except Exception:
        return None


def ffprobe_video(path: Path, ffprobe_bin: str) -> dict[str, Any]:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration",
        "-of",
        "json",
        str(path),
    ]
    result = run_probe(command)
    if not result:
        return {"ok": False, "error": "ffprobe failed to start", "command": command}
    if result.returncode != 0:
        return {"ok": False, "error": clean(result.stderr or result.stdout), "returnCode": result.returncode, "command": command}
    try:
        stream = (json.loads(result.stdout).get("streams") or [{}])[0]
    except Exception as exc:
        return {"ok": False, "error": str(exc), "returnCode": result.returncode, "command": command}
    width = as_int(stream.get("width"))
    height = as_int(stream.get("height"))
    duration = as_float(stream.get("duration"))
    return {
        "ok": width > 0 and height > 0,
        "width": width,
        "height": height,
        "durationSeconds": duration,
        "returnCode": result.returncode,
        "command": command,
    }


def sample_time(clip: dict[str, Any]) -> float:
    start = source_start(clip)
    end = source_end(clip)
    if end and end > start:
        return round3(start + min(max((end - start) / 2.0, 0.2), max(end - start - 0.1, 0.1)))
    return round3(start + 0.5)


def extract_frame(clip: dict[str, Any], source_path: Path, output_path: Path, ffmpeg_bin: str) -> dict[str, Any]:
    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(sample_time(clip)),
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_probe(command)
    ok = bool(result and result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0)
    return {
        "ok": ok,
        "outputPath": str(output_path),
        "returnCode": result.returncode if result else None,
        "stderr": clean(result.stderr if result else "ffmpeg failed to start", 1200),
        "command": command,
    }


def frame_output_path(output_dir: Path, row_index: int, clip_index: int, function: str) -> Path:
    safe_function = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in function or "bridge")
    return output_dir / f"row_{row_index:03d}" / f"beat_{clip_index:02d}_{safe_function}.jpg"


def clip_has_source_audio_leak(clip: dict[str, Any]) -> bool:
    if clip.get("includeSourceAudio") is False:
        return False
    policy = " ".join(str(clip.get(key) or "") for key in ("audioPolicy", "purpose", "notes")).lower()
    return not ("bgm" in policy and "no" in policy and "voice" in policy)


def audit_clip(
    clip: dict[str, Any],
    *,
    package_dir: Path,
    output_dir: Path,
    row_index: int,
    clip_index: int,
    args: argparse.Namespace,
    ffprobe_available: bool,
    ffmpeg_available: bool,
) -> dict[str, Any]:
    payload = bridge_insert_payload(clip)
    beat_function = clean(payload.get("beatFunction"))
    raw_source = source_path_text(clip)
    source = resolve_path(package_dir, raw_source)
    timeline_duration = max(0.0, timeline_end(clip) - timeline_start(clip))
    issues: list[str] = []
    warnings: list[str] = []
    if not beat_function:
        issues.append("missing_bridge_beat_function")
    if not raw_source:
        issues.append("missing_source_path")
    if raw_source and not source:
        issues.append("source_path_is_not_local_file")
    source_exists = bool(source and source.exists())
    if source and not source_exists:
        issues.append("source_file_missing")
    if source and source.suffix.lower() and source.suffix.lower() not in VIDEO_SUFFIXES:
        warnings.append("source_suffix_not_common_video_extension")
    if timeline_duration < args.min_beat_duration_seconds:
        issues.append("bridge_beat_timeline_duration_too_short")
    if clip_has_source_audio_leak(clip):
        issues.append("bridge_beat_source_audio_enabled")

    video_probe: dict[str, Any] = {"ok": False, "skipped": True}
    if source_exists:
        if ffprobe_available:
            video_probe = ffprobe_video(source, args.ffprobe_bin)
            if not video_probe.get("ok"):
                issues.append("source_not_probeable_video")
        elif args.require_video_probe:
            issues.append("ffprobe_missing_for_video_evidence")

    frame_report: dict[str, Any] = {"ok": False, "skipped": True}
    frame_path = frame_output_path(output_dir, row_index, clip_index, beat_function)
    if frame_path.exists() and frame_path.stat().st_size > 0:
        frame_report = {"ok": True, "outputPath": str(frame_path), "existingFrame": True}
    elif args.extract_frames and source_exists and ffmpeg_available:
        frame_report = extract_frame(clip, source, frame_path, args.ffmpeg_bin)
    elif args.require_frame_evidence and not args.extract_frames:
        issues.append("frame_evidence_not_extracted")
    elif args.require_frame_evidence and args.extract_frames and not ffmpeg_available:
        issues.append("ffmpeg_missing_for_frame_evidence")
    if args.require_frame_evidence and not frame_report.get("ok"):
        if "frame_evidence_not_extracted" not in issues and "ffmpeg_missing_for_frame_evidence" not in issues:
            issues.append("bridge_frame_evidence_missing")

    return {
        "status": "passed" if not issues else "blocked",
        "rowIndex": row_index,
        "clipIndex": clip_index,
        "beatIndex": payload.get("beatIndex"),
        "beatFunction": beat_function,
        "sourcePath": raw_source,
        "sourceResolvedPath": str(source) if source else None,
        "sourceExists": source_exists,
        "sourceName": source_name(raw_source or clip.get("sourceName")),
        "timelineStartSeconds": round3(timeline_start(clip)),
        "timelineEndSeconds": round3(timeline_end(clip)),
        "timelineDurationSeconds": round3(timeline_duration),
        "sourceStartSeconds": source_start(clip),
        "sourceEndSeconds": source_end(clip),
        "includeSourceAudio": clip.get("includeSourceAudio"),
        "trackIndex": clip.get("trackIndex"),
        "role": clip.get("role"),
        "purpose": clean(clip.get("purpose"), 1000),
        "videoProbe": video_probe,
        "frameEvidence": frame_report,
        "issues": issues,
        "warnings": warnings,
    }


def row_audit(
    row: dict[str, Any],
    clips: list[dict[str, Any]],
    *,
    package_dir: Path,
    output_dir: Path,
    args: argparse.Namespace,
    ffprobe_available: bool,
    ffmpeg_available: bool,
) -> dict[str, Any]:
    row_index = as_int(row.get("rowIndex"), -1)
    expected = expected_functions(row)
    matched: list[dict[str, Any]] = []
    for clip in clips:
        payload = bridge_insert_payload(clip)
        if as_int(payload.get("sourceSequenceRowIndex"), -9999) == row_index:
            matched.append(clip)
    clip_reports = [
        audit_clip(
            clip,
            package_dir=package_dir,
            output_dir=output_dir,
            row_index=row_index,
            clip_index=index,
            args=args,
            ffprobe_available=ffprobe_available,
            ffmpeg_available=ffmpeg_available,
        )
        for index, clip in enumerate(matched, start=1)
    ]
    matched_functions = [clean(report.get("beatFunction")) for report in clip_reports if clean(report.get("beatFunction"))]
    missing_functions = sorted(set(expected) - set(matched_functions))
    blocked_clips = [report for report in clip_reports if report.get("status") == "blocked"]
    source_names = sorted({clean(report.get("sourceName")) for report in clip_reports if clean(report.get("sourceName"))})
    frame_count = sum(1 for report in clip_reports if (report.get("frameEvidence") or {}).get("ok"))
    probe_ready = sum(1 for report in clip_reports if (report.get("videoProbe") or {}).get("ok"))
    issues: list[str] = []
    warnings: list[str] = []
    if not matched:
        issues.append("important_bridge_sequence_has_no_applied_bridge_clips")
    if expected and len(matched) < len(expected):
        issues.append("important_bridge_sequence_has_too_few_applied_beats")
    if missing_functions:
        issues.append("important_bridge_sequence_missing_expected_beat_functions")
    if blocked_clips:
        issues.append("one_or_more_bridge_visual_beats_blocked")
    if args.require_frame_evidence and frame_count < len(matched):
        issues.append("not_all_bridge_beats_have_frame_evidence")
    if args.require_video_probe and probe_ready < len(matched):
        issues.append("not_all_bridge_beats_have_video_probe_evidence")
    if len(source_names) == 1 and len(matched) >= 3:
        warnings.append("all bridge beats use one source clip; review whether this is a true multi-shot bridge")
    warnings.extend(
        f"beat {report.get('clipIndex')} {report.get('beatFunction')}: {', '.join(report.get('warnings') or [])}"
        for report in clip_reports
        if report.get("warnings")
    )
    return {
        "rowIndex": row_index,
        "status": "passed" if not issues else "blocked",
        "boundaryCategory": row.get("boundaryCategory"),
        "sequenceType": row.get("sequenceType"),
        "expectedBeatCount": len(expected),
        "expectedBeatFunctions": expected,
        "appliedBeatClipCount": len(matched),
        "appliedBeatFunctions": matched_functions,
        "missingBeatFunctions": missing_functions,
        "passedBridgeVisualClipCount": len(clip_reports) - len(blocked_clips),
        "blockedBridgeVisualClipCount": len(blocked_clips),
        "frameEvidenceCount": frame_count,
        "videoProbeReadyCount": probe_ready,
        "distinctSourceCount": len(source_names),
        "sourceNames": source_names,
        "timelineStartSeconds": round3(min((timeline_start(clip) for clip in matched), default=0.0)),
        "timelineEndSeconds": round3(max((timeline_end(clip) for clip in matched), default=0.0)),
        "clipReports": clip_reports,
        "issues": issues,
        "warnings": warnings,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_bridge_visual_evidence"
    blueprint, blueprint_path, blueprint_kind, blueprint_inside = choose_blueprint(package_dir, args.blueprint)
    plan_path = package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json"
    blueprint_report_path = package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json"
    application_path = package_dir / "bridge_sequence_application_contract_audit.json"
    plan = load_json(plan_path) or {}
    blueprint_report = load_json(blueprint_report_path) or {}
    application = load_json(application_path) or {}
    ffprobe_path = shutil.which(args.ffprobe_bin) if not Path(args.ffprobe_bin).exists() else args.ffprobe_bin
    ffmpeg_path = shutil.which(args.ffmpeg_bin) if not Path(args.ffmpeg_bin).exists() else args.ffmpeg_bin
    if ffprobe_path:
        args.ffprobe_bin = ffprobe_path
    if ffmpeg_path:
        args.ffmpeg_bin = ffmpeg_path
    ffprobe_available = bool(ffprobe_path)
    ffmpeg_available = bool(ffmpeg_path)

    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(blueprint, dict):
        blockers.append(f"missing or unreadable blueprint: {blueprint_path}")
        inserts: list[dict[str, Any]] = []
    else:
        inserts = bridge_insert_clips(blueprint)
    if plan.get("status") != "ready_with_bridge_sequence_plan":
        blockers.append(f"bridge_sequence_plan status is not ready: {plan.get('status')}")
    if blueprint_report.get("status") != "ready_with_bridge_sequence_blueprint":
        blockers.append(f"bridge_sequence_blueprint_report status is not ready: {blueprint_report.get('status')}")
    if application.get("status") != "passed":
        blockers.append(f"bridge_sequence_application_contract_audit status is not passed: {application.get('status')}")
    if not blueprint_path.exists():
        blockers.append(f"blueprint path does not exist: {blueprint_path}")
    if not blueprint_inside:
        blockers.append(f"blueprint is outside package: {blueprint_path}")
    if args.require_video_probe and not ffprobe_available:
        blockers.append("ffprobe is required for bridge visual evidence but was not found")
    if args.require_frame_evidence and args.extract_frames and not ffmpeg_available:
        blockers.append("ffmpeg is required for bridge frame evidence but was not found")

    rows = bridge_sequence_rows(plan)
    required_rows = [row for row in rows if is_required_sequence_row(row)]
    audited = [
        row_audit(
            row,
            inserts,
            package_dir=package_dir,
            output_dir=output_dir,
            args=args,
            ffprobe_available=ffprobe_available,
            ffmpeg_available=ffmpeg_available,
        )
        for row in required_rows
    ]
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    if rows and not required_rows:
        blockers.append("bridge_sequence_plan has no ready important sequence rows")
    if required_rows and not inserts:
        blockers.append("final candidate contains no bridge_sequence_insert clips")
    for row in blocked_rows[: args.max_blocked_rows_in_report]:
        blockers.append(f"bridge visual evidence row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}")
    warnings.extend(warning for row in audited for warning in row.get("warnings") or [])

    expected_total = sum(as_int(row.get("expectedBeatCount")) for row in audited)
    applied_total = sum(as_int(row.get("appliedBeatClipCount")) for row in audited)
    passed_visual_total = sum(as_int(row.get("passedBridgeVisualClipCount")) for row in audited)
    blocked_visual_total = sum(as_int(row.get("blockedBridgeVisualClipCount")) for row in audited)
    frame_total = sum(as_int(row.get("frameEvidenceCount")) for row in audited)
    probe_total = sum(as_int(row.get("videoProbeReadyCount")) for row in audited)
    source_names = sorted({source for row in audited for source in row.get("sourceNames") or [] if source})
    summary = {
        "plannedSequenceRowCount": len(rows),
        "requiredBridgeRowCount": len(required_rows),
        "auditedBridgeRowCount": len(audited),
        "passedBridgeRowCount": len(audited) - len(blocked_rows),
        "blockedBridgeRowCount": len(blocked_rows),
        "expectedBeatClipCount": expected_total,
        "appliedBeatClipCount": applied_total,
        "passedBridgeVisualClipCount": passed_visual_total,
        "blockedBridgeVisualClipCount": blocked_visual_total,
        "missingBeatClipCount": max(0, expected_total - applied_total),
        "frameEvidenceCount": frame_total,
        "videoProbeReadyCount": probe_total,
        "distinctBridgeSourceCount": len(source_names),
        "sourceAudioLeakClipCount": sum(
            1
            for row in audited
            for clip in row.get("clipReports") or []
            if "bridge_beat_source_audio_enabled" in (clip.get("issues") or [])
        ),
        "warningCount": len(warnings),
        "blockerCount": len(blockers),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers and not blocked_rows and bool(required_rows) else "blocked",
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside,
            "bridgeSequencePlan": str(plan_path),
            "bridgeSequencePlanExists": plan_path.exists(),
            "bridgeSequencePlanStatus": plan.get("status"),
            "bridgeSequenceBlueprintReport": str(blueprint_report_path),
            "bridgeSequenceBlueprintReportExists": blueprint_report_path.exists(),
            "bridgeSequenceBlueprintStatus": blueprint_report.get("status"),
            "bridgeSequenceApplicationContract": str(application_path),
            "bridgeSequenceApplicationStatus": application.get("status"),
            "extractFrames": bool(args.extract_frames),
            "requireFrameEvidence": bool(args.require_frame_evidence),
            "requireVideoProbe": bool(args.require_video_probe),
            "ffmpegAvailable": ffmpeg_available,
            "ffprobeAvailable": ffprobe_available,
        },
        "summary": summary,
        "bridgeRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "importantBoundariesNeedConcreteBridgeVideo": True,
            "proseOnlyBridgeEvidenceBlocked": True,
            "bridgeBeatMetadataRequired": True,
            "sourceVideoProbeRequired": bool(args.require_video_probe),
            "bridgeFrameEvidenceRequired": bool(args.require_frame_evidence),
            "sourceAudioLeakBlocked": True,
            "localFootageFirst": True,
        },
        "safety": safety(),
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Bridge Visual Evidence Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report['inputs'].get('blueprint')}`",
        f"Output: `{report['outputDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"][:80])
    lines.extend(["", "## Bridge Rows"])
    for row in report.get("bridgeRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('sequenceType')}`",
                f"- Status: `{row.get('status')}`",
                f"- Boundary: `{row.get('boundaryCategory')}`",
                f"- Applied beats: `{row.get('appliedBeatClipCount')}/{row.get('expectedBeatCount')}`",
                f"- Visual beats passed: `{row.get('passedBridgeVisualClipCount')}/{row.get('appliedBeatClipCount')}`",
                f"- Frames: `{row.get('frameEvidenceCount')}`",
                f"- Sources: `{', '.join(row.get('sourceNames') or [])}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
        for clip in row.get("clipReports") or []:
            frame = clip.get("frameEvidence") if isinstance(clip.get("frameEvidence"), dict) else {}
            frame_path = frame.get("outputPath")
            lines.extend(
                [
                    f"  - Beat `{clip.get('beatFunction')}`: status=`{clip.get('status')}`, source=`{clip.get('sourceName')}`, frame=`{frame_path}`",
                ]
            )
            if frame_path and Path(str(frame_path)).exists():
                lines.append(f"    Frame: ![]({frame_path})")
    lines.extend(
        [
            "",
            "## Contract",
            "- Important route, title, timeline-gap, and ending boundaries must have actual bridge_sequence_insert video clips.",
            "- Each bridge beat needs beat metadata, a local source file, video probe evidence, and frame evidence when required.",
            "- Source-camera audio is blocked for bridge beats; transition moments remain BGM-led.",
            "- Effects can polish a boundary only after concrete route/title/texture bridge footage exists.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit concrete visual evidence for transition bridge sequence inserts.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--output-dir")
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--extract-frames", action="store_true")
    parser.add_argument("--no-require-frame-evidence", dest="require_frame_evidence", action="store_false")
    parser.add_argument("--no-require-video-probe", dest="require_video_probe", action="store_false")
    parser.add_argument("--min-beat-duration-seconds", type=float, default=0.75)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(require_frame_evidence=True, require_video_probe=True)
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_bridge_visual_evidence_contract_audit.json", report)
    write_markdown(package_dir / "transition_bridge_visual_evidence_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
