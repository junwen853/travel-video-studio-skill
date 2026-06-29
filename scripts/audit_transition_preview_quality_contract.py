#!/usr/bin/env python3
"""Audit transition preview packets for inspectable, non-blank frame evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def clean(value: Any, limit: int = 400) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


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


def resolve_package_path(package_dir: Path, raw: Any) -> Path | None:
    value = clean(raw, 4000)
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_metrics_with_pil(path: Path) -> dict[str, Any] | None:
    try:
        from PIL import Image, ImageStat  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        image = Image.open(path)
        width, height = image.size
        gray = image.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        return {
            "width": width,
            "height": height,
            "meanLuma": round(float(stat.mean[0]), 3),
            "stddevLuma": round(float(stat.stddev[0]), 3),
            "minLuma": int(extrema[0]),
            "maxLuma": int(extrema[1]),
            "decoder": "PIL",
        }
    except Exception as exc:  # noqa: BLE001
        return {"metricError": str(exc), "decoder": "PIL"}


def image_metrics_with_ffmpeg(path: Path, ffmpeg_bin: str) -> dict[str, Any] | None:
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if probe.returncode != 0:
            return {"metricError": clean(probe.stderr or probe.stdout), "decoder": "ffprobe"}
        stream = (json.loads(probe.stdout).get("streams") or [{}])[0]
        width = as_int(stream.get("width"))
        height = as_int(stream.get("height"))
        sample_w = min(max(width, 1), 320)
        sample_h = min(max(height, 1), 180)
        raw = subprocess.run(
            [
                ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={sample_w}:{sample_h}:force_original_aspect_ratio=decrease,pad={sample_w}:{sample_h}:(ow-iw)/2:(oh-ih)/2:black,format=gray",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            check=False,
            capture_output=True,
        )
        if raw.returncode != 0:
            return {"width": width, "height": height, "metricError": clean(raw.stderr), "decoder": "ffmpeg"}
        values = list(raw.stdout)
        if not values:
            return {"width": width, "height": height, "metricError": "no gray bytes", "decoder": "ffmpeg"}
        mean = sum(values) / len(values)
        variance = sum((item - mean) ** 2 for item in values) / len(values)
        return {
            "width": width,
            "height": height,
            "meanLuma": round(mean, 3),
            "stddevLuma": round(variance ** 0.5, 3),
            "minLuma": min(values),
            "maxLuma": max(values),
            "decoder": "ffmpeg",
        }
    except Exception as exc:  # noqa: BLE001
        return {"metricError": str(exc), "decoder": "ffmpeg"}


def image_metrics(path: Path, ffmpeg_bin: str) -> dict[str, Any]:
    metrics = image_metrics_with_pil(path)
    if metrics and not metrics.get("metricError"):
        return metrics
    fallback = image_metrics_with_ffmpeg(path, ffmpeg_bin)
    if fallback:
        if metrics and metrics.get("metricError"):
            fallback["pilMetricError"] = metrics.get("metricError")
        return fallback
    return metrics or {"metricError": "unable to decode image"}


def frame_quality(path: Path, package_dir: Path, ffmpeg_bin: str, args: argparse.Namespace) -> dict[str, Any]:
    exists = path.exists()
    row: dict[str, Any] = {
        "path": str(path),
        "exists": exists,
        "packageLocal": str(path).startswith(str(package_dir)),
        "fileSizeBytes": path.stat().st_size if exists else 0,
    }
    issues: list[str] = []
    warnings: list[str] = []
    if not exists:
        issues.append("frame_missing")
        row["status"] = "blocked"
        row["issues"] = issues
        row["warnings"] = warnings
        return row
    row["sha256"] = sha256_file(path)
    metrics = image_metrics(path, ffmpeg_bin)
    row["metrics"] = metrics
    width = as_int(metrics.get("width"))
    height = as_int(metrics.get("height"))
    mean = float(metrics.get("meanLuma") or 0.0)
    stddev = float(metrics.get("stddevLuma") or 0.0)
    if metrics.get("metricError"):
        issues.append("frame_not_decodeable")
    if width < args.min_width or height < args.min_height:
        issues.append("frame_too_small")
    if mean < args.blank_mean_luma:
        issues.append("frame_likely_blank_or_black")
    elif mean < args.dark_warning_mean_luma:
        warnings.append("frame_very_dark_review_manually")
    if stddev < args.uniform_warning_stddev:
        warnings.append("frame_low_detail_or_uniform_review_manually")
    row["status"] = "blocked" if issues else "passed"
    row["issues"] = issues
    row["warnings"] = warnings
    return row


def preview_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("previewRows") if isinstance(packet.get("previewRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def role_outputs(row: dict[str, Any], package_dir: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    samples = row.get("samples") if isinstance(row.get("samples"), list) else []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        role = clean(sample.get("role"))
        path = resolve_package_path(package_dir, sample.get("outputPath"))
        if role and path:
            out[role] = path
    return out


def frame_paths(row: dict[str, Any], package_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for raw in row.get("frameSampleEvidence") if isinstance(row.get("frameSampleEvidence"), list) else []:
        path = resolve_package_path(package_dir, raw)
        if path:
            paths.append(path)
    for path in role_outputs(row, package_dir).values():
        if path not in paths:
            paths.append(path)
    return paths


def audit_preview_row(row: dict[str, Any], package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    index = row.get("rowIndex")
    important = bool(row.get("importantBoundary")) or clean(row.get("boundaryCategory")).lower() in IMPORTANT_CATEGORIES
    outputs = role_outputs(row, package_dir)
    frames = frame_paths(row, package_dir)
    frame_reports = [frame_quality(path, package_dir, args.ffmpeg_bin, args) for path in frames]
    issues: list[str] = []
    warnings: list[str] = []
    if row.get("status") != "ready_with_transition_preview_evidence":
        issues.append("preview_row_not_ready")
    preview_md = resolve_package_path(package_dir, row.get("previewMarkdown") or row.get("previewStripEvidence"))
    if not preview_md or not preview_md.exists():
        issues.append("preview_markdown_missing")
    if important and "outgoing" not in outputs:
        issues.append("important_row_missing_outgoing_output")
    if important and "landing" not in outputs:
        issues.append("important_row_missing_landing_output")
    passed_frames = [frame for frame in frame_reports if frame.get("status") == "passed"]
    if important and len(passed_frames) < args.min_important_frames:
        issues.append("important_row_has_too_few_passed_frames")
    blocked_frames = [frame for frame in frame_reports if frame.get("status") == "blocked"]
    issues.extend(f"frame {Path(frame['path']).name}: {', '.join(frame.get('issues') or [])}" for frame in blocked_frames)
    warnings.extend(f"frame {Path(frame['path']).name}: {', '.join(frame.get('warnings') or [])}" for frame in frame_reports if frame.get("warnings"))
    outgoing = frame_quality(outputs["outgoing"], package_dir, args.ffmpeg_bin, args) if "outgoing" in outputs else None
    landing = frame_quality(outputs["landing"], package_dir, args.ffmpeg_bin, args) if "landing" in outputs else None
    if outgoing and landing and outgoing.get("sha256") and outgoing.get("sha256") == landing.get("sha256"):
        issues.append("outgoing_and_landing_frames_are_identical")
    return {
        "rowIndex": index,
        "boundaryCategory": clean(row.get("boundaryCategory")).lower(),
        "importantBoundary": important,
        "previewMarkdown": str(preview_md) if preview_md else None,
        "status": "blocked" if issues else "passed",
        "frameCount": len(frames),
        "passedFrameCount": len(passed_frames),
        "blockedFrameCount": len(blocked_frames),
        "roleOutputs": {role: str(path) for role, path in outputs.items()},
        "frames": frame_reports,
        "issues": issues,
        "warnings": warnings,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    packet_path = package_dir / "transition_preview_packet" / "transition_preview_packet.json"
    packet = load_json(packet_path) or {}
    rows = preview_rows(packet)
    audited_rows = [audit_preview_row(row, package_dir, args) for row in rows]
    important_rows = [row for row in audited_rows if row.get("importantBoundary")]
    blocked_rows = [row for row in audited_rows if row.get("status") == "blocked"]
    warnings = [warning for row in audited_rows for warning in row.get("warnings") or []]
    blockers: list[str] = []
    if not packet_path.exists():
        blockers.append("missing transition_preview_packet/transition_preview_packet.json")
    if packet.get("status") not in {"ready_with_transition_preview_packet", "ready_no_important_transitions"}:
        blockers.append(f"transition preview packet status is {packet.get('status')}")
    for row in blocked_rows[: args.max_blocked_rows_in_report]:
        blockers.append(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}")

    summary = {
        "previewRowCount": len(audited_rows),
        "importantPreviewRowCount": len(important_rows),
        "previewQualityReadyRowCount": len(audited_rows) - len(blocked_rows),
        "blockedPreviewQualityRowCount": len(blocked_rows),
        "passedFrameCount": sum(as_int(row.get("passedFrameCount")) for row in audited_rows),
        "blockedFrameCount": sum(as_int(row.get("blockedFrameCount")) for row in audited_rows),
        "importantRowsWithOutgoingLanding": sum(
            1
            for row in important_rows
            if "outgoing" in (row.get("roleOutputs") or {}) and "landing" in (row.get("roleOutputs") or {})
        ),
        "warningCount": len(warnings),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers and not blocked_rows else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "transitionPreviewPacket": str(packet_path),
            "transitionPreviewPacketStatus": packet.get("status"),
            "minImportantFrames": args.min_important_frames,
            "minWidth": args.min_width,
            "minHeight": args.min_height,
            "blankMeanLuma": args.blank_mean_luma,
        },
        "summary": summary,
        "auditedRows": audited_rows,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "importantBoundariesNeedOutgoingAndLandingFrames": True,
            "blankFramesBlocked": True,
            "identicalOutgoingLandingBlocked": True,
            "packageLocalEvidencePreferred": True,
        },
        "safety": safety(),
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Preview Quality Contract Audit",
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
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- Frames: `{row.get('passedFrameCount')}/{row.get('frameCount')}` passed",
                f"- Preview: `{row.get('previewMarkdown')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Important transition previews need outgoing and landing frame evidence.",
            "- Blank, missing, undecodable, or identical outgoing/landing frames block approval.",
            "- Warnings for very dark or low-detail frames require manual review, but do not block night scenes by themselves.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition preview packet frame quality.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--min-important-frames", type=int, default=2)
    parser.add_argument("--min-width", type=int, default=120)
    parser.add_argument("--min-height", type=int, default=68)
    parser.add_argument("--blank-mean-luma", type=float, default=3.0)
    parser.add_argument("--dark-warning-mean-luma", type=float, default=10.0)
    parser.add_argument("--uniform-warning-stddev", type=float, default=1.0)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_preview_quality_contract_audit.json", report)
    write_markdown(package_dir / "transition_preview_quality_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
