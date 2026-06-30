#!/usr/bin/env python3
"""Audit actual visual proof for opening/chapter/ending title bridge media."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


TITLE_MODES = {"opening", "chapter", "ending"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts", ".m2ts"}
IMAGE_SLATE_SUFFIXES = {".png", ".jpg", ".jpeg"}
BAD_SOURCE_PARTS = {"title_cards"}
ROUTE_DATE_TOKENS = ("/", "->", "→", " - ", " TO ", "20")
INTERNAL_TOKENS = (
    "CODEX",
    "DAVINCI",
    "RESOLVE",
    "SKILL",
    "V14",
    "QA",
    "SRT",
    "TXT",
    "交付",
    "时间线",
    "修复",
    "本次剪辑",
    "已经完成",
)


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


def inside(parent: Path, child: Path | None) -> bool:
    if child is None:
        return False
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def resolve_path(package_dir: Path, raw: Any) -> Path | None:
    text = clean(raw, 4000)
    if not text or text.startswith(("http://", "https://")):
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path.resolve()


def is_video_path(path: Path | None) -> bool:
    if not path or not path.exists():
        return False
    parts = {part.lower() for part in path.parts}
    if path.suffix.lower() in IMAGE_SLATE_SUFFIXES or parts & BAD_SOURCE_PARTS:
        return False
    return path.suffix.lower() in VIDEO_SUFFIXES or path.suffix.lower() == ""


def find_manifest(package_dir: Path, explicit: str | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        [
            package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json",
            package_dir / "v12_visual_manifest.json",
            package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
            package_dir / "visual_polish_manifest.json",
        ]
    )
    return next((path.resolve() for path in candidates if path.exists()), None)


def manifest_title_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("segments") if isinstance(manifest.get("segments"), list) else []
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        mode = clean(row.get("mode")).lower()
        if mode in TITLE_MODES:
            item = dict(row)
            item["_sourceIndex"] = index
            out.append(item)
    return sorted(out, key=lambda row: (as_float(row.get("timeline_start") or row.get("timelineStartSeconds")), row.get("_sourceIndex") or 0))


def words_or_cjk_count(value: str) -> int:
    text = clean(value)
    if not text:
        return 0
    words = [item for item in text.split() if item]
    if len(words) > 1:
        return len(words)
    cjk = [ch for ch in text if "\u3400" <= ch <= "\u9fff"]
    return len(cjk) if cjk else 1


def forbidden_hits(values: list[str], forbidden: list[str]) -> list[str]:
    text = "\n".join(values).upper()
    hits = [token for token in ROUTE_DATE_TOKENS if token in text]
    hits.extend(token for token in INTERNAL_TOKENS if token in text)
    hits.extend(str(token) for token in forbidden if token and str(token).upper() in text)
    return sorted(set(hits))


def ffprobe(path: Path, ffprobe_bin: str) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "error": "file_missing"}
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    video = next((stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"), {})
    width = as_int(video.get("width"))
    height = as_int(video.get("height"))
    duration = as_float((payload.get("format") or {}).get("duration") if isinstance(payload.get("format"), dict) else video.get("duration"))
    return {
        "ok": result.returncode == 0 and bool(video),
        "returnCode": result.returncode,
        "width": width,
        "height": height,
        "durationSeconds": round(duration, 3),
        "videoStreamCount": sum(1 for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        "audioStreamCount": sum(1 for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"),
        "stderr": clean(result.stderr, 1200),
    }


def frame_times(duration: float, count: int) -> list[float]:
    duration = max(0.1, duration)
    if count <= 1:
        return [duration / 2.0]
    return [max(0.05, min(duration - 0.05, duration * fraction)) for fraction in (0.25, 0.5, 0.75)[:count]]


def raw_frame_metrics(ffmpeg_bin: str, source: Path, time_seconds: float, sample_width: int = 160, sample_height: int = 90) -> dict[str, Any]:
    cmd = [
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
    try:
        result = subprocess.run(cmd, check=False, capture_output=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "command": cmd}
    data = result.stdout or b""
    expected = sample_width * sample_height * 3
    if result.returncode != 0 or len(data) < expected:
        return {
            "ok": False,
            "returnCode": result.returncode,
            "stderr": clean(result.stderr.decode("utf-8", errors="ignore"), 1200),
            "byteCount": len(data),
            "expectedByteCount": expected,
            "command": cmd,
        }
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
    }


def extract_frame(ffmpeg_bin: str, source: Path, time_seconds: float, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
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
    try:
        result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "outputPath": str(output), "error": str(exc), "command": cmd}
    return {
        "ok": result.returncode == 0 and output.exists() and output.stat().st_size > 0,
        "returnCode": result.returncode,
        "outputPath": str(output),
        "timeSeconds": round(time_seconds, 3),
        "stderr": clean(result.stderr, 1200),
        "command": cmd,
    }


def frame_quality(path: Path, metrics: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        issues.append("frame_missing")
    if not metrics.get("ok"):
        issues.append("frame_metrics_missing")
    mean = as_float(metrics.get("meanLuma"))
    stddev = as_float(metrics.get("stddevLuma"))
    if mean <= args.blank_mean_luma:
        issues.append("frame_blank_or_black")
    if stddev <= args.uniform_stddev:
        issues.append("frame_too_uniform_for_scenic_title_proof")
    if mean <= args.dark_warning_mean_luma:
        warnings.append("frame_very_dark")
    return {
        "path": str(path),
        "status": "passed" if not issues else "blocked",
        "sampleWidth": metrics.get("sampleWidth"),
        "sampleHeight": metrics.get("sampleHeight"),
        "meanLuma": round(mean, 3),
        "stddevLuma": round(stddev, 3),
        "issues": issues,
        "warnings": warnings,
    }


def overlay_quality(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {"exists": False, "fileSizeBytes": 0}
    return {
        "exists": True,
        "fileSizeBytes": path.stat().st_size,
        "suffix": path.suffix.lower(),
    }


def row_output_dir(output_dir: Path, index: int, mode: str) -> Path:
    return output_dir / f"row_{index:03d}_{mode}"


def audit_segment(
    package_dir: Path,
    output_dir: Path,
    manifest: dict[str, Any],
    segment: dict[str, Any],
    index: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    mode = clean(segment.get("mode")).lower()
    title = clean(segment.get("title") or segment.get("cityTitle") or manifest.get("cityTitle") or manifest.get("expectedOpeningTitle"))
    subtitle = clean(segment.get("subtitle") or manifest.get("coverSubtitle") or manifest.get("englishSubtitle"))
    forbidden = [str(item) for item in manifest.get("forbiddenOpeningText") or manifest.get("forbiddenVisibleText") or []]
    values = [title, subtitle]
    segment_path = resolve_path(package_dir, segment.get("segment") or segment.get("source"))
    source_path = resolve_path(package_dir, segment.get("source"))
    overlay_path = resolve_path(package_dir, segment.get("overlay"))
    out_dir = row_output_dir(output_dir, index, mode)
    probe = ffprobe(segment_path, args.ffprobe_bin) if segment_path else {"ok": False, "error": "missing_segment_path"}
    frames: list[dict[str, Any]] = []
    extraction_reports: list[dict[str, Any]] = []
    if args.extract_frames and segment_path and probe.get("ok"):
        for frame_index, seconds in enumerate(frame_times(as_float(probe.get("durationSeconds"), 1.0), args.frame_count), start=1):
            frame_path = out_dir / f"frame_{frame_index:02d}.jpg"
            extracted = extract_frame(args.ffmpeg_bin, segment_path, seconds, frame_path)
            metrics = raw_frame_metrics(args.ffmpeg_bin, segment_path, seconds)
            extracted["metrics"] = metrics
            extraction_reports.append(extracted)
            frames.append(frame_quality(frame_path, metrics, args))
    if not args.extract_frames:
        for frame_path in sorted(out_dir.glob("frame_*.jpg")):
            frames.append(
                {
                    "path": str(frame_path),
                    "status": "blocked",
                    "issues": ["existing_frame_cannot_be_measured_without_extract_frames"],
                    "warnings": [],
                }
            )
    passed_frames = [frame for frame in frames if frame.get("status") == "passed"]
    hits = forbidden_hits(values, forbidden)
    overlay = overlay_quality(overlay_path)
    issues: list[str] = []
    warnings: list[str] = []
    if not segment_path:
        issues.append("missing_title_segment_path")
    elif not segment_path.exists():
        issues.append("title_segment_file_missing")
    elif not is_video_path(segment_path):
        issues.append("title_segment_not_video_or_is_slate")
    if segment_path and not inside(package_dir, segment_path):
        issues.append("title_segment_not_package_local")
    if not probe.get("ok"):
        issues.append("ffprobe_video_stream_missing")
    if as_int(probe.get("width")) < args.min_width or as_int(probe.get("height")) < args.min_height:
        issues.append("video_below_min_resolution")
    ratio = as_int(probe.get("width")) / as_int(probe.get("height")) if as_int(probe.get("height")) else 0.0
    if probe.get("ok") and not math.isclose(ratio, 16 / 9, rel_tol=0.03, abs_tol=0.03):
        issues.append("video_not_16x9")
    if as_float(probe.get("durationSeconds")) < args.min_duration:
        issues.append("title_segment_too_short")
    if len(passed_frames) < args.frame_count:
        issues.append("not_enough_passed_visual_frames")
    if mode == "opening" and (not title or not (1 <= words_or_cjk_count(title) <= 8)):
        issues.append("opening_title_not_oversized_destination_text")
    if mode == "opening" and hits:
        issues.append("opening_title_contains_route_date_or_internal_text")
    if subtitle and len(subtitle) > 34:
        issues.append("subtitle_too_long_for_reference_cover_formula")
    if not overlay.get("exists"):
        warnings.append("overlay_png_missing_or_not_recorded")
    if source_path and not is_video_path(source_path):
        warnings.append("source_background_is_not_video")
    warnings.extend(warning for frame in frames for warning in frame.get("warnings") or [])
    return {
        "index": index,
        "mode": mode,
        "segmentId": segment.get("id"),
        "title": title,
        "subtitle": subtitle,
        "titleUnitCount": words_or_cjk_count(title),
        "forbiddenHits": hits,
        "segmentPath": str(segment_path) if segment_path else "",
        "sourcePath": str(source_path) if source_path else "",
        "overlayPath": str(overlay_path) if overlay_path else "",
        "segmentPackageLocal": bool(segment_path and inside(package_dir, segment_path)),
        "segmentIsVideo": bool(is_video_path(segment_path)),
        "probe": probe,
        "overlay": overlay,
        "extractions": extraction_reports,
        "frames": frames,
        "passedFrameCount": len(passed_frames),
        "issues": issues,
        "warnings": warnings,
        "status": "passed" if not issues else "blocked",
    }


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "title_visual_proof"
    ffmpeg_path = shutil.which(args.ffmpeg_bin) if not Path(args.ffmpeg_bin).exists() else args.ffmpeg_bin
    ffprobe_path = shutil.which(args.ffprobe_bin) if not Path(args.ffprobe_bin).exists() else args.ffprobe_bin
    if ffmpeg_path:
        args.ffmpeg_bin = ffmpeg_path
    if ffprobe_path:
        args.ffprobe_bin = ffprobe_path
    manifest_path = find_manifest(package_dir, args.visual_manifest)
    manifest = load_json(manifest_path) or {}
    title_bridge = load_json(package_dir / "title_bridge_contract_audit.json") or {}
    cover_title = load_json(package_dir / "cover_title_contract_audit.json") or {}
    if not isinstance(manifest, dict) or not manifest_path:
        rows: list[dict[str, Any]] = []
        blockers = ["title visual manifest missing"]
    else:
        rows = [
            audit_segment(package_dir, output_dir, manifest, segment, index, args)
            for index, segment in enumerate(manifest_title_segments(manifest), start=1)
        ]
        blockers = []
    opening_rows = [row for row in rows if row.get("mode") == "opening"]
    chapter_rows = [row for row in rows if row.get("mode") == "chapter"]
    ending_rows = [row for row in rows if row.get("mode") == "ending"]
    blocked_rows = [row for row in rows if row.get("status") == "blocked"]
    warnings = [warning for row in rows for warning in row.get("warnings") or []]
    if not ffmpeg_path and args.extract_frames:
        blockers.append("ffmpeg not found for title visual proof frame extraction")
    if not ffprobe_path:
        blockers.append("ffprobe not found for title visual proof probing")
    if title_bridge.get("status") != "passed":
        blockers.append(f"title bridge contract status is {title_bridge.get('status')}")
    if cover_title.get("status") != "passed":
        blockers.append(f"cover title contract status is {cover_title.get('status')}")
    if len(opening_rows) != 1:
        blockers.append("expected exactly one opening title visual proof row")
    if not chapter_rows:
        blockers.append("missing chapter title visual proof rows")
    if not ending_rows:
        blockers.append("missing ending title visual proof row")
    blockers.extend(f"row {row.get('index')} {row.get('mode')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[: args.max_blocked_rows])
    status = "passed" if rows and not blockers and not blocked_rows else "blocked"
    summary = {
        "titleVisualRowCount": len(rows),
        "passedTitleVisualRowCount": len(rows) - len(blocked_rows),
        "blockedTitleVisualRowCount": len(blocked_rows),
        "openingRowCount": len(opening_rows),
        "chapterRowCount": len(chapter_rows),
        "endingRowCount": len(ending_rows),
        "rowsWithPackageLocalVideo": sum(1 for row in rows if row.get("segmentPackageLocal") and row.get("segmentIsVideo")),
        "rowsWithProbeVideo": sum(1 for row in rows if (row.get("probe") or {}).get("ok")),
        "rowsWithThreePassedFrames": sum(1 for row in rows if as_int(row.get("passedFrameCount")) >= args.frame_count),
        "rowsWithOverlayEvidence": sum(1 for row in rows if (row.get("overlay") or {}).get("exists")),
        "openingForbiddenHitCount": sum(len(row.get("forbiddenHits") or []) for row in opening_rows),
        "titleBridgeStatus": title_bridge.get("status"),
        "coverTitleStatus": cover_title.get("status"),
        "ffmpegAvailable": bool(ffmpeg_path),
        "ffprobeAvailable": bool(ffprobe_path),
        "extractedFrames": bool(args.extract_frames),
        "frameCountPerRow": args.frame_count,
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {
            "visualManifest": str(manifest_path) if manifest_path else "",
            "visualManifestExists": bool(manifest_path and manifest_path.exists()),
            "titleBridgeContractAudit": str(package_dir / "title_bridge_contract_audit.json"),
            "coverTitleContractAudit": str(package_dir / "cover_title_contract_audit.json"),
            "extractFrames": bool(args.extract_frames),
            "minWidth": args.min_width,
            "minHeight": args.min_height,
            "minDuration": args.min_duration,
        },
        "summary": summary,
        "rows": rows,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "actualVisualProofRequired": True,
            "openingTitleMustBeDestinationOnly": True,
            "packageLocalTitleSegmentRequired": True,
            "threeFrameProofRequired": True,
            "titleBridgeAndCoverContractsRequired": True,
            "noScreenshotSlateOrTitleCards": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Title Visual Proof Contract Audit",
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
    for row in report.get("rows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('index')}: `{row.get('mode')}`",
                f"- Status: `{row.get('status')}`",
                f"- Title: `{row.get('title')}` / `{row.get('subtitle')}`",
                f"- Segment: `{row.get('segmentPath')}`",
                f"- Probe: `{json.dumps(row.get('probe'), ensure_ascii=False)[:1000]}`",
                f"- Passed frames: `{row.get('passedFrameCount')}`",
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
            "- Opening/chapter/ending title media need actual video probe plus local frame evidence.",
            "- Opening title text must be destination-only and free of route/date/internal workflow labels.",
            "- Title bridge and cover title structural contracts must pass before this proof can pass.",
            "- Screenshot chrome, PNG/JPG slates, stale title_cards assets, blank frames, and uniform frames block approval.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit actual visual proof for clean scenic title bridge media.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--visual-manifest")
    parser.add_argument("--output-dir")
    parser.add_argument("--extract-frames", action="store_true")
    parser.add_argument("--frame-count", type=int, default=3)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--ffprobe-bin", default="ffprobe")
    parser.add_argument("--min-width", type=int, default=640)
    parser.add_argument("--min-height", type=int, default=360)
    parser.add_argument("--min-duration", type=float, default=1.5)
    parser.add_argument("--blank-mean-luma", type=float, default=3.0)
    parser.add_argument("--dark-warning-mean-luma", type=float, default=10.0)
    parser.add_argument("--uniform-stddev", type=float, default=0.75)
    parser.add_argument("--max-blocked-rows", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "title_visual_proof_contract_audit.json", report)
    write_markdown(package_dir / "title_visual_proof_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
