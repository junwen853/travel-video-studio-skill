#!/usr/bin/env python3
"""Audit the ordered transition watch reel for sequence-level review quality."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = "passed"
PASSED_NO_IMPORTANT = "passed_no_important_transitions"
BLOCKED = "blocked_transition_watch_reel_review"

READY_REEL_STATUSES = {"ready_with_transition_watch_reel", "ready_no_important_transitions"}
HIGH_INTENSITY_WORDS = {
    "crash",
    "flash",
    "spin",
    "speed",
    "ramp",
    "whip",
    "rotation",
    "rotate",
    "zoom",
    "shake",
    "push",
}
LOW_INTENSITY_WORDS = {"cut", "match", "bridge", "breath", "fade", "dissolve", "none", "straight"}


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


def probe_media(path: Path, ffprobe_bin: str) -> dict[str, Any]:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height,duration:format=duration,size",
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
    fmt = data.get("format") if isinstance(data.get("format"), dict) else {}
    duration = as_float(fmt.get("duration"), 0.0) or as_float(first_video.get("duration"), 0.0)
    return {
        "ok": bool(video_streams),
        "width": as_int(first_video.get("width")),
        "height": as_int(first_video.get("height")),
        "durationSeconds": round(duration, 3),
        "sizeBytes": as_int(fmt.get("size")),
        "videoStreamCount": len(video_streams),
        "audioStreamCount": len(audio_streams),
        "returnCode": result.returncode,
        "command": command,
    }


def normalize_family(value: Any) -> str:
    raw = clean(value, 160).lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return raw or "unknown"


def motion_family(row: dict[str, Any]) -> str:
    motion = row.get("motionExecution") if isinstance(row.get("motionExecution"), dict) else {}
    family = normalize_family(motion.get("choreographyFamily"))
    effect = normalize_family(motion.get("resolveKeyframeEffect"))
    if family and family != "unknown":
        return family
    return effect


def is_high_intensity(row: dict[str, Any]) -> bool:
    motion = row.get("motionExecution") if isinstance(row.get("motionExecution"), dict) else {}
    text = " ".join(
        [
            motion_family(row),
            normalize_family(motion.get("resolveKeyframeEffect")),
            normalize_family(row.get("boundaryCategory")),
        ]
    )
    if any(word in text for word in LOW_INTENSITY_WORDS) and not any(word in text for word in HIGH_INTENSITY_WORDS):
        return False
    return any(word in text for word in HIGH_INTENSITY_WORDS)


def max_run(values: list[Any]) -> int:
    best = 0
    current = 0
    previous = object()
    for value in values:
        if value == previous:
            current += 1
        else:
            current = 1
            previous = value
        best = max(best, current)
    return best


def max_true_run(values: list[bool]) -> int:
    best = 0
    current = 0
    for value in values:
        if value:
            current += 1
        else:
            current = 0
        best = max(best, current)
    return best


def review_row(row: dict[str, Any], previous_end: float | None, args: argparse.Namespace) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    start = as_float(row.get("reelStartSeconds"), -1.0)
    end = as_float(row.get("reelEndSeconds"), -1.0)
    duration = as_float(row.get("durationSeconds"), 0.0)
    probe = row.get("probe") if isinstance(row.get("probe"), dict) else {}
    motion = row.get("motionExecution") if isinstance(row.get("motionExecution"), dict) else {}
    sensory = row.get("sensoryContinuity") if isinstance(row.get("sensoryContinuity"), dict) else {}
    has_bridge = as_int(row.get("bridgeSampleCount")) > 0
    motion_ready = motion.get("ready") is True
    sensory_ready = sensory.get("ready") is True
    family = motion_family(row)
    high_intensity = is_high_intensity(row)

    if row.get("status") != "ready_for_reel":
        issues.append("watch_reel_row_not_ready")
    if not row.get("packageLocal"):
        issues.append("clip_not_package_local")
    if not row.get("exists"):
        issues.append("clip_missing")
    if as_int(probe.get("audioStreamCount")) > 0:
        issues.append("clip_has_audio_stream")
    if duration < args.min_clip_duration_seconds:
        issues.append("clip_too_short_for_sequence_review")
    if start < 0 or end <= start:
        issues.append("invalid_reel_time_range")
    if previous_end is not None and start + args.time_tolerance_seconds < previous_end:
        issues.append("reel_time_order_regressed")
    if not clean(row.get("storyboardPurpose")):
        issues.append("missing_storyboard_purpose")
    if not (has_bridge or motion_ready or sensory_ready):
        issues.append("missing_bridge_motion_or_sensory_reason")
    if row.get("importantBoundary") and not has_bridge and high_intensity:
        warnings.append("important_high_intensity_transition_without_bridge_sample")

    return {
        "rowIndex": row.get("rowIndex"),
        "status": "blocked" if issues else "passed",
        "family": family,
        "highIntensity": high_intensity,
        "startSeconds": start,
        "endSeconds": end,
        "durationSeconds": duration,
        "hasBridgeSample": has_bridge,
        "motionReady": motion_ready,
        "sensoryReady": sensory_ready,
        "storyboardPurpose": clean(row.get("storyboardPurpose")),
        "issues": issues,
        "warnings": warnings,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    watch_path = package_dir / "transition_watch_reel" / "transition_watch_reel.json"
    watch = load_json(watch_path) or {}
    watch_summary = watch.get("summary") if isinstance(watch.get("summary"), dict) else {}
    watch_inputs = watch.get("inputs") if isinstance(watch.get("inputs"), dict) else {}
    watch_policy = watch.get("policy") if isinstance(watch.get("policy"), dict) else {}
    watch_rows = watch.get("reelRows") if isinstance(watch.get("reelRows"), list) else []
    watch_rows = [row for row in watch_rows if isinstance(row, dict)]
    blockers: list[str] = []
    warnings: list[str] = []
    summary_require_muted = watch_summary.get("requireMuted")
    input_require_muted = watch_inputs.get("requireMuted")
    policy_watch_reel_mute_required = watch_policy.get("watchReelMuteRequired")

    if not watch_path.exists():
        blockers.append("missing transition_watch_reel/transition_watch_reel.json")
    if watch.get("status") not in READY_REEL_STATUSES:
        blockers.append(f"transition watch reel status is {watch.get('status')}")
    if watch.get("blockers"):
        blockers.extend(f"transition_watch_reel blocker: {item}" for item in watch.get("blockers") or [])
    if summary_require_muted is not True:
        blockers.append("transition watch reel summary.requireMuted is not true; rerun prepare_transition_watch_reel.py with --require-muted")
    if input_require_muted is not True:
        blockers.append("transition watch reel inputs.requireMuted is not true; rerun prepare_transition_watch_reel.py with --require-muted")
    if policy_watch_reel_mute_required is not True:
        blockers.append("transition watch reel policy.watchReelMuteRequired is not true; rerun prepare_transition_watch_reel.py with --require-muted")

    if watch.get("status") == "ready_no_important_transitions":
        status = PASSED_NO_IMPORTANT if not blockers and not watch_rows else BLOCKED
        if watch_rows:
            blockers.append("ready_no_important_transitions report still contains reel rows")
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "packageDir": str(package_dir),
            "inputs": {
                "transitionWatchReel": str(watch_path),
                "transitionWatchReelStatus": watch.get("status"),
                "watchReelInputRequireMuted": input_require_muted,
            },
            "summary": {
                "transitionWatchReelStatus": watch.get("status"),
                "watchReelRequireMuted": summary_require_muted,
                "watchReelInputRequireMuted": input_require_muted,
                "watchReelPolicyMuteRequired": policy_watch_reel_mute_required,
                "reelRowCount": len(watch_rows),
                "importantReelRowCount": as_int(watch_summary.get("importantReelRowCount")),
                "passedReviewRowCount": 0,
                "blockedReviewRowCount": len(watch_rows),
                "blockedCheckCount": len(blockers),
                "warningCount": len(warnings),
            },
            "reviewRows": [],
            "blockers": blockers,
            "warnings": warnings,
            "safety": safety(),
        }

    reel_output = Path(str(watch_summary.get("reelOutput") or "")).expanduser() if watch_summary.get("reelOutput") else None
    if reel_output and not reel_output.is_absolute():
        reel_output = package_dir / reel_output
    reel_probe = probe_media(reel_output, args.ffprobe_bin) if reel_output and reel_output.exists() else {"ok": False}
    if not reel_output:
        blockers.append("transition watch reel output path is missing")
    elif not reel_output.exists():
        blockers.append(f"transition watch reel mp4 is missing: {reel_output}")
    elif not reel_probe.get("ok"):
        blockers.append("transition watch reel mp4 is not probeable video")
    elif as_int(reel_probe.get("audioStreamCount")) > 0:
        blockers.append("transition watch reel mp4 contains audio")

    previous_end: float | None = None
    review_rows: list[dict[str, Any]] = []
    for row in sorted(watch_rows, key=lambda item: as_float(item.get("reelStartSeconds"), 0.0)):
        reviewed = review_row(row, previous_end, args)
        review_rows.append(reviewed)
        previous_end = as_float(row.get("reelEndSeconds"), previous_end or 0.0)

    blocked_rows = [row for row in review_rows if row.get("status") == "blocked"]
    for row in blocked_rows[: args.max_blocked_rows_in_report]:
        blockers.append(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}")
    warnings.extend(warning for row in review_rows for warning in row.get("warnings") or [])

    families = [row.get("family") for row in review_rows]
    high_flags = [bool(row.get("highIntensity")) for row in review_rows]
    row_count = len(review_rows)
    family_counts = {family: families.count(family) for family in sorted(set(families))}
    dominant_family_count = max(family_counts.values(), default=0)
    dominant_family_share = dominant_family_count / row_count if row_count else 0.0
    high_count = sum(1 for flag in high_flags if flag)
    high_share = high_count / row_count if row_count else 0.0
    high_run = max_true_run(high_flags) if high_flags else 0
    family_run = max_run(families) if families else 0
    expected_duration = as_float(watch_summary.get("totalReelDurationSeconds"))
    actual_duration = as_float(reel_probe.get("durationSeconds")) if isinstance(reel_probe, dict) else 0.0
    duration_delta = abs(actual_duration - expected_duration) if actual_duration and expected_duration else 0.0

    if row_count == 0:
        blockers.append("transition watch reel has no review rows")
    if as_int(watch_summary.get("blockedReelRowCount")) > 0:
        blockers.append("transition watch reel summary still has blocked reel rows")
    if row_count and as_int(watch_summary.get("readyReelRowCount")) < row_count:
        blockers.append("not all watch reel rows are ready")
    if row_count >= args.family_run_min_rows and family_run > args.max_family_run:
        blockers.append(f"same transition family repeats {family_run} times in a row")
    if row_count >= args.family_share_min_rows and dominant_family_share > args.max_dominant_family_share:
        blockers.append(f"dominant transition family share {dominant_family_share:.2f} exceeds {args.max_dominant_family_share:.2f}")
    if row_count >= args.high_intensity_min_rows and high_run > args.max_high_intensity_run:
        blockers.append(f"high-intensity transition run {high_run} exceeds {args.max_high_intensity_run}")
    if row_count >= args.high_intensity_min_rows and high_share > args.max_high_intensity_share:
        blockers.append(f"high-intensity transition share {high_share:.2f} exceeds {args.max_high_intensity_share:.2f}")
    if actual_duration and expected_duration and duration_delta > args.duration_tolerance_seconds:
        blockers.append(f"watch reel duration delta {duration_delta:.2f}s exceeds {args.duration_tolerance_seconds:.2f}s")

    summary = {
        "transitionWatchReelStatus": watch.get("status"),
        "watchReelRequireMuted": summary_require_muted,
        "watchReelInputRequireMuted": input_require_muted,
        "watchReelPolicyMuteRequired": policy_watch_reel_mute_required,
        "reelRowCount": row_count,
        "importantReelRowCount": as_int(watch_summary.get("importantReelRowCount")),
        "passedReviewRowCount": sum(1 for row in review_rows if row.get("status") == "passed"),
        "blockedReviewRowCount": len(blocked_rows),
        "rowsWithBridgeSamples": sum(1 for row in review_rows if row.get("hasBridgeSample")),
        "rowsWithMotionReady": sum(1 for row in review_rows if row.get("motionReady")),
        "rowsWithSensoryReady": sum(1 for row in review_rows if row.get("sensoryReady")),
        "uniqueFamilyCount": len(family_counts),
        "familyCounts": family_counts,
        "familyRunMax": family_run,
        "dominantFamilyShare": round(dominant_family_share, 3),
        "highIntensityRowCount": high_count,
        "highIntensityShare": round(high_share, 3),
        "highIntensityRunMax": high_run,
        "expectedReelDurationSeconds": expected_duration,
        "actualReelDurationSeconds": actual_duration,
        "durationDeltaSeconds": round(duration_delta, 3),
        "reelProbeReady": bool(reel_probe.get("ok")) if isinstance(reel_probe, dict) else False,
        "reelHasAudio": as_int(reel_probe.get("audioStreamCount")) > 0 if isinstance(reel_probe, dict) else None,
        "blockedCheckCount": len(blockers),
        "warningCount": len(warnings),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": PASSED if not blockers else BLOCKED,
        "packageDir": str(package_dir),
        "inputs": {
            "transitionWatchReel": str(watch_path),
            "transitionWatchReelStatus": watch.get("status"),
            "watchReelOutput": str(reel_output) if reel_output else None,
            "watchReelInputRequireMuted": input_require_muted,
        },
        "summary": summary,
        "reelProbe": reel_probe,
        "reviewRows": review_rows,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "reviewWholeTransitionSequence": True,
            "blockRepeatedTemplateMotion": True,
            "blockOverusedHighIntensityMotion": True,
            "requireMutedPackageLocalReview": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Watch Reel Review Contract",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report.get("blockers") or [])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in (report.get("warnings") or [])[:80])
    lines.extend(["", "## Review Rows"])
    for row in (report.get("reviewRows") or [])[:160]:
        lines.append(
            f"- Row `{row.get('rowIndex')}`: `{row.get('status')}`, family `{row.get('family')}`, highIntensity `{row.get('highIntensity')}`, issues `{', '.join(row.get('issues') or [])}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition watch reel sequence quality.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--min-clip-duration-seconds", type=float, default=0.8)
    parser.add_argument("--time-tolerance-seconds", type=float, default=0.25)
    parser.add_argument("--duration-tolerance-seconds", type=float, default=1.25)
    parser.add_argument("--family-run-min-rows", type=int, default=4)
    parser.add_argument("--max-family-run", type=int, default=2)
    parser.add_argument("--family-share-min-rows", type=int, default=4)
    parser.add_argument("--max-dominant-family-share", type=float, default=0.7)
    parser.add_argument("--high-intensity-min-rows", type=int, default=3)
    parser.add_argument("--max-high-intensity-run", type=int, default=1)
    parser.add_argument("--max-high-intensity-share", type=float, default=0.35)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    output_json = package_dir / "transition_watch_reel_review_contract_audit.json"
    output_md = package_dir / "transition_watch_reel_review_contract_audit.md"
    write_json(output_json, report)
    write_markdown(output_md, report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {PASSED, PASSED_NO_IMPORTANT} else 2


if __name__ == "__main__":
    raise SystemExit(main())
