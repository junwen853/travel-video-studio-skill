#!/usr/bin/env python3
"""Audit role/order integrity for transition audition MP4 segment packets."""

from __future__ import annotations

import argparse
import json
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
    video_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"]
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


def parse_concat_list(path: Path | None) -> list[Path]:
    if not path or not path.exists():
        return []
    out: list[Path] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text.startswith("file "):
            continue
        raw = text[5:].strip()
        if raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        out.append(Path(raw).expanduser().resolve())
    return out


def role_order_ok(roles: list[str]) -> bool:
    if len(roles) < 3:
        return False
    if roles[0] != "outgoing" or roles[-1] != "landing":
        return False
    if roles.count("outgoing") != 1 or roles.count("landing") != 1:
        return False
    return any(role in {"bridge", "motion", "bridge_or_motion"} for role in roles[1:-1])


def source_exists(report: dict[str, Any], package_dir: Path) -> bool:
    path = resolve_package_path(package_dir, report.get("sourcePath"))
    return bool(path and path.exists())


def audit_segment(report: dict[str, Any], package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    segment = report.get("segment") if isinstance(report.get("segment"), dict) else {}
    role = clean(report.get("role")).lower() or "sample"
    segment_path = resolve_package_path(package_dir, segment.get("outputPath"))
    issues: list[str] = []
    if not segment.get("ok"):
        issues.append("segment_render_not_ok")
    if not segment_path:
        issues.append("segment_path_missing")
        exists = False
        package_local = False
        file_size = 0
        probe = {"ok": False}
    else:
        exists = segment_path.exists()
        package_local = is_inside(segment_path, package_dir)
        file_size = segment_path.stat().st_size if exists else 0
        if not exists:
            issues.append("segment_file_missing")
            probe = {"ok": False}
        else:
            probe = ffprobe_media(segment_path, args.ffprobe_bin)
    if segment_path and not package_local:
        issues.append("segment_not_package_local")
    if file_size < args.min_segment_file_size_bytes:
        issues.append("segment_file_too_small")
    if not probe.get("ok"):
        issues.append("segment_not_probeable_video")
    if as_float(probe.get("durationSeconds")) < args.min_segment_duration_seconds:
        issues.append("segment_too_short")
    if as_int(probe.get("width")) < args.min_width or as_int(probe.get("height")) < args.min_height:
        issues.append("segment_below_min_resolution")
    if as_int(probe.get("audioStreamCount")) > 0:
        issues.append("segment_has_audio_stream")
    if report.get("required") is True and not source_exists(report, package_dir):
        issues.append("required_source_missing")
    return {
        "role": role,
        "sourcePath": clean(report.get("sourcePath"), 4000),
        "sourceExists": source_exists(report, package_dir),
        "segmentPath": str(segment_path) if segment_path else "",
        "segmentOk": bool(segment.get("ok")),
        "exists": exists,
        "packageLocal": package_local,
        "fileSizeBytes": file_size,
        "probe": probe,
        "issues": issues,
        "status": "passed" if not issues else "blocked",
    }


def audit_row(row: dict[str, Any], package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    if row.get("status") != "ready_with_transition_audition":
        issues.append("audition_row_not_ready")
    motion = row.get("motionExecution") if isinstance(row.get("motionExecution"), dict) else {}
    if motion.get("ready") is not True:
        issues.append("motion_execution_not_ready")
    if as_int(motion.get("threeBeatCount")) < 3:
        issues.append("motion_execution_missing_three_beat_roles")
    beat_roles = [clean(role).lower() for role in motion.get("beatRoles") or []]
    if not {"outgoing", "bridge_or_motion", "landing"}.issubset(set(beat_roles)):
        issues.append("motion_execution_beat_roles_not_outgoing_bridge_landing")
    if not clean(motion.get("bridgeOrMotionAction")):
        issues.append("motion_execution_bridge_or_motion_action_missing")
    if motion.get("bgmHitTarget") != "cut_or_effect_on_bgm_phrase_hit" or motion.get("bgmAllowsOffPhrase") is not False:
        issues.append("motion_execution_missing_bgm_hit_policy")
    if motion.get("captionQuietZone") is not True:
        issues.append("motion_execution_missing_caption_quiet_zone")
    if not motion.get("resolveKeyframeEffect"):
        issues.append("motion_execution_missing_resolve_keyframe_effect")
    segments_raw = row.get("segmentReports") if isinstance(row.get("segmentReports"), list) else []
    segment_reports = [segment for segment in segments_raw if isinstance(segment, dict)]
    audited_segments = [audit_segment(segment, package_dir, args) for segment in segment_reports]
    roles = [segment.get("role") for segment in audited_segments]
    if len(audited_segments) != as_int(row.get("sampleCount"), len(audited_segments)):
        issues.append("sample_count_does_not_match_segment_reports")
    if not role_order_ok([str(role) for role in roles]):
        issues.append("segment_roles_not_ordered_outgoing_bridge_landing")
    if row.get("importantBoundary") and not any(role == "bridge" for role in roles[1:-1]):
        issues.append("important_transition_missing_bridge_segment")
    if any(segment.get("status") == "blocked" for segment in audited_segments):
        issues.append("one_or_more_segments_blocked")
    concat = row.get("concat") if isinstance(row.get("concat"), dict) else {}
    concat_path = resolve_package_path(package_dir, concat.get("concatList"))
    concat_paths = parse_concat_list(concat_path)
    segment_paths = [Path(str(segment.get("segmentPath"))).resolve() for segment in audited_segments if segment.get("segmentPath")]
    if not concat.get("ok"):
        issues.append("concat_not_ok")
    if not concat_path or not concat_path.exists():
        issues.append("concat_list_missing")
    if concat_paths != segment_paths:
        issues.append("concat_list_order_does_not_match_segment_reports")
    audition_path = resolve_package_path(package_dir, row.get("auditionClip"))
    concat_output = resolve_package_path(package_dir, concat.get("outputPath"))
    if not audition_path or not audition_path.exists():
        issues.append("audition_clip_missing")
    if audition_path and not is_inside(audition_path, package_dir):
        issues.append("audition_clip_not_package_local")
    if audition_path and concat_output and audition_path != concat_output:
        issues.append("concat_output_does_not_match_audition_clip")
    if len(audited_segments) > args.max_segments_per_row:
        warnings.append("audition_has_many_bridge_segments")
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": clean(row.get("boundaryCategory")),
        "importantBoundary": bool(row.get("importantBoundary")),
        "status": "passed" if not issues else "blocked",
        "auditionClip": str(audition_path) if audition_path else "",
        "roles": roles,
        "roleOrderOk": role_order_ok([str(role) for role in roles]),
        "hasOutgoingSegment": roles[:1] == ["outgoing"],
        "hasBridgeOrMotionSegment": any(role in {"bridge", "motion", "bridge_or_motion"} for role in roles[1:-1]),
        "hasBridgeSegment": any(role == "bridge" for role in roles[1:-1]),
        "hasLandingSegment": roles[-1:] == ["landing"],
        "segmentReports": audited_segments,
        "concat": {
            "ok": bool(concat.get("ok")),
            "concatList": str(concat_path) if concat_path else "",
            "concatListExists": bool(concat_path and concat_path.exists()),
            "concatPathCount": len(concat_paths),
            "segmentPathCount": len(segment_paths),
            "orderMatchesSegmentReports": concat_paths == segment_paths,
        },
        "motionExecution": motion,
        "issues": issues,
        "warnings": warnings,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    ffprobe_path = shutil.which(args.ffprobe_bin) if not Path(args.ffprobe_bin).exists() else args.ffprobe_bin
    if ffprobe_path:
        args.ffprobe_bin = ffprobe_path
    packet_path = package_dir / "transition_audition_packet" / "transition_audition_packet.json"
    quality_path = package_dir / "transition_audition_quality_contract_audit.json"
    visual_path = package_dir / "transition_audition_visual_proof_contract_audit.json"
    packet = load_json(packet_path) or {}
    quality = load_json(quality_path) or {}
    visual = load_json(visual_path) or {}
    rows = packet_rows(packet)
    audited = [audit_row(row, package_dir, args) for row in rows]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    warnings = [warning for row in audited for warning in row.get("warnings") or []]
    blockers: list[str] = []
    if not packet_path.exists():
        blockers.append("missing transition_audition_packet/transition_audition_packet.json")
    if packet.get("status") not in {"ready_with_transition_audition_packet", "ready_no_important_transitions"}:
        blockers.append(f"transition audition packet status is {packet.get('status')}")
    if quality.get("status") != "passed":
        blockers.append(f"transition audition quality status is {quality.get('status')}")
    if visual.get("status") != "passed":
        blockers.append(f"transition audition visual proof status is {visual.get('status')}")
    if not ffprobe_path:
        blockers.append("ffprobe not found for transition audition role integrity")
    blockers.extend(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked[: args.max_blocked_rows])
    status = "passed" if packet.get("status") == "ready_no_important_transitions" and not blockers else "passed" if audited and not blockers and not blocked else "blocked"
    summary = {
        "auditionRoleRowCount": len(audited),
        "passedAuditionRoleRowCount": len(audited) - len(blocked),
        "blockedAuditionRoleRowCount": len(blocked),
        "importantAuditionRoleRowCount": sum(1 for row in audited if row.get("importantBoundary")),
        "rowsWithRoleOrderedSegments": sum(1 for row in audited if row.get("roleOrderOk")),
        "rowsWithOutgoingLandingSegments": sum(1 for row in audited if row.get("hasOutgoingSegment") and row.get("hasLandingSegment")),
        "rowsWithBridgeOrMotionSegment": sum(1 for row in audited if row.get("hasBridgeOrMotionSegment")),
        "rowsWithBridgeSegment": sum(1 for row in audited if row.get("hasBridgeSegment")),
        "rowsWithAllSegmentsPassed": sum(1 for row in audited if all((segment.get("status") == "passed") for segment in row.get("segmentReports") or [])),
        "rowsWithConcatOrderEvidence": sum(1 for row in audited if (row.get("concat") or {}).get("orderMatchesSegmentReports") is True),
        "rowsWithMotionExecution": sum(1 for row in audited if (row.get("motionExecution") or {}).get("ready") is True),
        "rowsWithThreeBeatRoles": sum(1 for row in audited if {"outgoing", "bridge_or_motion", "landing"}.issubset(set(str(role).lower() for role in ((row.get("motionExecution") or {}).get("beatRoles") or [])))),
        "transitionAuditionQualityStatus": quality.get("status"),
        "transitionAuditionVisualProofStatus": visual.get("status"),
        "ffprobeAvailable": bool(ffprobe_path),
        "warningCount": len(warnings),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "transitionAuditionPacket": str(packet_path),
            "transitionAuditionPacketStatus": packet.get("status"),
            "transitionAuditionQuality": str(quality_path),
            "transitionAuditionQualityStatus": quality.get("status"),
            "transitionAuditionVisualProof": str(visual_path),
            "transitionAuditionVisualProofStatus": visual.get("status"),
            "minSegmentDurationSeconds": args.min_segment_duration_seconds,
            "ffprobeBin": args.ffprobe_bin,
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "outgoingBridgeLandingSegmentOrderRequired": True,
            "importantTransitionsNeedBridgeSegment": True,
            "concatListMustMatchSegmentReports": True,
            "segmentFilesMustBePackageLocalMutedVideos": True,
            "motionExecutionThreeBeatRolesRequired": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Audition Role Integrity Contract Audit",
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
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- Roles: `{', '.join(str(role) for role in row.get('roles') or [])}`",
                f"- Audition: `{row.get('auditionClip')}`",
                f"- Concat order matches segments: `{(row.get('concat') or {}).get('orderMatchesSegmentReports')}`",
            ]
        )
        for segment in row.get("segmentReports") or []:
            probe = segment.get("probe") if isinstance(segment.get("probe"), dict) else {}
            lines.append(
                f"- Segment `{segment.get('role')}` `{segment.get('status')}` `{segment.get('segmentPath')}` "
                f"{probe.get('durationSeconds')}s {probe.get('width')}x{probe.get('height')} audio `{probe.get('audioStreamCount')}`"
            )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Transition auditions must be assembled from ordered outgoing, bridge-or-motion, and landing segments.",
            "- The concat list must match segmentReports exactly so a random moving MP4 cannot substitute for a transition audition.",
            "- Important boundaries need an actual bridge segment, not only a direct outgoing-to-landing jump.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition audition outgoing/bridge/landing segment integrity.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--min-segment-duration-seconds", type=float, default=0.35)
    parser.add_argument("--min-width", type=int, default=120)
    parser.add_argument("--min-height", type=int, default=68)
    parser.add_argument("--min-segment-file-size-bytes", type=int, default=1024)
    parser.add_argument("--max-segments-per-row", type=int, default=6)
    parser.add_argument("--max-blocked-rows", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_audition_role_integrity_contract_audit.json", report)
    write_markdown(package_dir / "transition_audition_role_integrity_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
