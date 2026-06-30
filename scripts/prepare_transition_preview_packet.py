#!/usr/bin/env python3
"""Prepare package-local preview/frame evidence for important transition rows."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
SOURCE_START_KEYS = ("sourceStartSeconds", "sourceInSeconds", "sourceIn", "inPointSeconds", "sourceRecordStartSeconds")
SOURCE_END_KEYS = ("sourceEndSeconds", "sourceOutSeconds", "sourceOut", "outPointSeconds", "sourceRecordEndSeconds")
TIMELINE_START_KEYS = ("timelineStartSeconds", "recordStartSeconds", "startSeconds")
TIMELINE_END_KEYS = ("timelineEndSeconds", "recordEndSeconds", "endSeconds")


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


def clean(value: Any, limit: int = 280) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(clean(value))
    if isinstance(value, list):
        return any(present(item) for item in value)
    if isinstance(value, dict):
        return any(present(item) for item in value.values())
    return value is not None


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def transition_rows(grammar: dict[str, Any]) -> list[dict[str, Any]]:
    rows = grammar.get("transitionRows") if isinstance(grammar.get("transitionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def is_important(row: dict[str, Any]) -> bool:
    return clean(row.get("boundaryCategory")).lower() in IMPORTANT_CATEGORIES


def clip_text(clip: dict[str, Any]) -> str:
    keys = ("sourcePath", "sourceName", "name", "role", "purpose", "titleText", "creatorFunction", "notes")
    return " ".join(clean(clip.get(key)) for key in keys if clean(clip.get(key))).lower()


def pick_first_float(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = as_float(row.get(key))
        if value is not None:
            return value
    return None


def timeline_start(clip: dict[str, Any]) -> float:
    return pick_first_float(clip, TIMELINE_START_KEYS) or 0.0


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = pick_first_float(clip, TIMELINE_END_KEYS)
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


def source_duration(clip: dict[str, Any]) -> float | None:
    start = source_start(clip)
    end = source_end(clip)
    if end is not None and end > start:
        return end - start
    duration = as_float(clip.get("sourceDurationSeconds") or clip.get("durationSeconds"))
    return duration if duration and duration > 0 else None


def source_path(clip: dict[str, Any]) -> str:
    return clean(clip.get("sourcePath") or clip.get("path") or clip.get("mediaPath"), limit=2000)


def source_name(clip: dict[str, Any]) -> str:
    explicit = clean(clip.get("sourceName") or clip.get("name"))
    if explicit:
        return explicit
    path = source_path(clip)
    return Path(path).name if path else ""


def video_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = clip_text(row)
        if "subtitle_overlay" in text:
            continue
        track_type = clean(row.get("trackType")).lower()
        if track_type and track_type != "video":
            continue
        out.append(row)
    return sorted(out, key=lambda item: (timeline_start(item), int(as_float(item.get("trackIndex"), 1) or 1)))


def clip_lookup(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for clip in video_clips(blueprint):
        for key in (source_path(clip), source_name(clip), Path(source_path(clip)).name if source_path(clip) else ""):
            if key and key not in lookup:
                lookup[key] = clip
    return lookup


def full_clip(row_clip: Any, lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(row_clip, dict):
        return {}
    for key in (source_path(row_clip), source_name(row_clip), Path(source_path(row_clip)).name if source_path(row_clip) else ""):
        if key and key in lookup:
            merged = dict(lookup[key])
            merged.update({k: v for k, v in row_clip.items() if present(v)})
            return merged
    return dict(row_clip)


def sample_time(clip: dict[str, Any], role: str) -> float:
    start = source_start(clip)
    duration = source_duration(clip)
    if not duration:
        return max(0.0, start + 0.5)
    if role == "outgoing":
        offset = max(0.1, min(duration - 0.1, duration - 0.45))
    elif role == "landing":
        offset = max(0.1, min(duration - 0.1, 0.45))
    else:
        offset = max(0.1, min(duration - 0.1, duration / 2.0))
    return round(max(0.0, start + offset), 3)


def ffmpeg_command(ffmpeg_bin: str, sample: dict[str, Any], output_path: Path) -> list[str]:
    return [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(sample["sourceTimeSeconds"]),
        "-i",
        sample["sourcePath"],
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]


def command_text(command: list[str]) -> str:
    return " ".join(json.dumps(part) if " " in part else part for part in command)


def existing_preview_paths(decision: dict[str, Any], row: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("previewStripEvidence", "frameSampleEvidence"):
        for source in (decision, row):
            value = source.get(key) if isinstance(source, dict) else None
            if isinstance(value, list):
                paths.extend(clean(item, 2000) for item in value if clean(item))
            elif clean(value):
                paths.extend(part.strip() for part in clean(value, 4000).split(",") if part.strip())
    return list(dict.fromkeys(paths))


def bridge_source_from_decision(decision: dict[str, Any]) -> str:
    for key in ("bridgeInsertSource", "bridgeSourcePath", "bridgeClipPath"):
        value = clean(decision.get(key), 2000)
        if value and ("/" in value or "." in Path(value).name):
            return value
    return ""


def row_samples(row: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    from_clip = full_clip(row.get("fromClip"), lookup)
    to_clip = full_clip(row.get("toClip"), lookup)
    samples: list[dict[str, Any]] = []
    for role, clip in (("outgoing", from_clip), ("landing", to_clip)):
        path = source_path(clip)
        samples.append(
            {
                "role": role,
                "sourcePath": path,
                "sourceName": source_name(clip),
                "sourceTimeSeconds": sample_time(clip, role),
                "timelineHintSeconds": timeline_end(clip) if role == "outgoing" else timeline_start(clip),
                "required": True,
            }
        )
    bridge_path = bridge_source_from_decision(decision)
    if bridge_path:
        samples.insert(
            1,
            {
                "role": "bridge",
                "sourcePath": bridge_path,
                "sourceName": Path(bridge_path).name,
                "sourceTimeSeconds": 0.5,
                "timelineHintSeconds": row.get("timelineStartSeconds"),
                "required": False,
            },
        )
    return samples


def extract_sample(command: list[str], output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "outputPath": str(output_path), "error": str(exc)}
    return {
        "ok": result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0,
        "returnCode": result.returncode,
        "outputPath": str(output_path),
        "stderr": clean(result.stderr, 1200),
    }


def row_markdown_path(output_dir: Path, index: int) -> Path:
    return output_dir / f"row_{index:03d}" / "preview.md"


def row_frame_path(output_dir: Path, index: int, sample: dict[str, Any]) -> Path:
    role = clean(sample.get("role")) or "sample"
    return output_dir / f"row_{index:03d}" / f"{role}.jpg"


def build_preview_row(
    row: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
    output_dir: Path,
    args: argparse.Namespace,
    ffmpeg_available: bool,
) -> dict[str, Any]:
    index = int(row.get("rowIndex") or 0)
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    samples = row_samples(row, lookup)
    sample_rows: list[dict[str, Any]] = []
    generated_frames: list[str] = []
    missing_sources: list[str] = []
    extraction_errors: list[str] = []
    planned_commands: list[dict[str, Any]] = []
    for sample in samples:
        output_path = row_frame_path(output_dir, index, sample)
        command = ffmpeg_command(args.ffmpeg_bin, sample, output_path)
        source = Path(str(sample.get("sourcePath") or "")).expanduser()
        sample_report = dict(sample)
        sample_report["outputPath"] = str(output_path)
        sample_report["sourceExists"] = source.exists() if sample.get("sourcePath") else False
        sample_report["ffmpegCommand"] = command
        sample_report["ffmpegCommandText"] = command_text(command)
        planned_commands.append(
            {
                "role": sample_report["role"],
                "sourcePath": sample_report["sourcePath"],
                "sourceTimeSeconds": sample_report["sourceTimeSeconds"],
                "outputPath": str(output_path),
                "command": command,
                "commandText": sample_report["ffmpegCommandText"],
            }
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            generated_frames.append(str(output_path))
            sample_report["existingFrame"] = True
        elif not sample.get("sourcePath"):
            if sample.get("required"):
                missing_sources.append(f"{sample.get('role')}: no sourcePath")
        elif not source.exists():
            if sample.get("required"):
                missing_sources.append(f"{sample.get('role')}: {sample.get('sourcePath')}")
        elif args.extract_frames and ffmpeg_available:
            extracted = extract_sample(command, output_path)
            sample_report["extraction"] = extracted
            if extracted["ok"]:
                generated_frames.append(str(output_path))
            else:
                extraction_errors.append(f"{sample.get('role')}: {extracted.get('stderr') or extracted.get('error') or 'ffmpeg failed'}")
        sample_rows.append(sample_report)

    existing_evidence = existing_preview_paths(decision, row)
    md_path = row_markdown_path(output_dir, index)
    ready_evidence = bool(generated_frames) or bool(existing_evidence)
    if extraction_errors:
        status = "blocked_frame_extraction_failed"
    elif ready_evidence:
        status = "ready_with_transition_preview_evidence"
    elif missing_sources:
        status = "blocked_missing_source_file"
    elif not args.extract_frames:
        status = "needs_frame_extraction"
    elif not ffmpeg_available:
        status = "needs_ffmpeg"
    else:
        status = "needs_frame_extraction"

    preview_row = {
        "rowIndex": index,
        "boundaryCategory": clean(row.get("boundaryCategory")).lower(),
        "importantBoundary": is_important(row),
        "timelineBoundarySeconds": row.get("timelineStartSeconds"),
        "storyboardPurpose": clean(decision.get("storyboardPurpose")),
        "fromSourceName": source_name(full_clip(row.get("fromClip"), lookup)),
        "toSourceName": source_name(full_clip(row.get("toClip"), lookup)),
        "status": status,
        "previewMarkdown": str(md_path),
        "previewStripEvidence": str(md_path) if ready_evidence else "",
        "frameSampleEvidence": generated_frames or existing_evidence,
        "samples": sample_rows,
        "plannedCommands": planned_commands,
        "missingSources": missing_sources,
        "extractionErrors": extraction_errors,
    }
    write_row_markdown(md_path, preview_row)
    return preview_row


def write_row_markdown(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# Transition Preview Row {row['rowIndex']}",
        "",
        f"Status: `{row['status']}`",
        f"Boundary: `{row['boundaryCategory']}`",
        f"Purpose: `{row.get('storyboardPurpose')}`",
        f"From: `{row.get('fromSourceName')}`",
        f"To: `{row.get('toSourceName')}`",
        "",
        "## Samples",
    ]
    for sample in row["samples"]:
        lines.extend(
            [
                "",
                f"- Role: `{sample.get('role')}`",
                f"  Source: `{sample.get('sourcePath')}`",
                f"  Time: `{sample.get('sourceTimeSeconds')}`",
                f"  Output: `{sample.get('outputPath')}`",
            ]
        )
        if Path(str(sample.get("outputPath") or "")).exists():
            lines.append(f"  Frame: ![]({sample.get('outputPath')})")
    lines.extend(["", "## Commands"])
    for command in row["plannedCommands"]:
        lines.extend(["", "```bash", command["commandText"], "```"])
    if row["missingSources"]:
        lines.extend(["", "## Missing Sources"])
        lines.extend(f"- {item}" for item in row["missingSources"])
    if row["extractionErrors"]:
        lines.extend(["", "## Extraction Errors"])
        lines.extend(f"- {item}" for item in row["extractionErrors"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_transition_grammar(grammar_path: Path, preview_rows: list[dict[str, Any]]) -> bool:
    grammar = load_json(grammar_path)
    if not isinstance(grammar, dict):
        return False
    rows = transition_rows(grammar)
    by_index = {int(row.get("rowIndex") or 0): row for row in preview_rows}
    changed = False
    for row in rows:
        index = int(row.get("rowIndex") or 0)
        preview = by_index.get(index)
        if not preview or preview.get("status") != "ready_with_transition_preview_evidence":
            continue
        decision = row.setdefault("decision", {})
        if not isinstance(decision, dict):
            continue
        if preview.get("previewStripEvidence") and decision.get("previewStripEvidence") != preview["previewStripEvidence"]:
            decision["previewStripEvidence"] = preview["previewStripEvidence"]
            changed = True
        frames = preview.get("frameSampleEvidence") if isinstance(preview.get("frameSampleEvidence"), list) else []
        frame_text = ", ".join(clean(frame, 2000) for frame in frames if clean(frame))
        if frame_text and decision.get("frameSampleEvidence") != frame_text:
            decision["frameSampleEvidence"] = frame_text
            changed = True
    if changed:
        write_json(grammar_path, grammar)
    return changed


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_preview_packet"
    grammar_path = package_dir / "transition_grammar_plan" / "transition_grammar_plan.json"
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    grammar = load_json(grammar_path)
    blueprint = load_json(blueprint_path) or {}
    ffmpeg_path = shutil.which(args.ffmpeg_bin) if not Path(args.ffmpeg_bin).exists() else args.ffmpeg_bin
    ffmpeg_available = bool(ffmpeg_path)
    if ffmpeg_path:
        args.ffmpeg_bin = ffmpeg_path

    if not isinstance(grammar, dict):
        rows: list[dict[str, Any]] = []
        preview_rows: list[dict[str, Any]] = []
        status = "blocked_missing_transition_grammar_plan"
    else:
        rows = transition_rows(grammar)
        selected = [row for row in rows if args.include_all_rows or is_important(row)]
        if args.max_rows:
            selected = selected[: args.max_rows]
        lookup = clip_lookup(blueprint if isinstance(blueprint, dict) else {})
        preview_rows = [build_preview_row(row, lookup, output_dir, args, ffmpeg_available) for row in selected]
        ready_rows = sum(1 for row in preview_rows if row.get("status") == "ready_with_transition_preview_evidence")
        missing_rows = sum(1 for row in preview_rows if str(row.get("status", "")).startswith("blocked_missing_source"))
        failed_rows = sum(1 for row in preview_rows if str(row.get("status", "")).startswith("blocked_frame"))
        needs_rows = sum(1 for row in preview_rows if str(row.get("status", "")).startswith("needs_"))
        if not rows:
            status = "blocked_no_transition_rows"
        elif not preview_rows:
            status = "ready_no_important_transitions"
        elif ready_rows == len(preview_rows):
            status = "ready_with_transition_preview_packet"
        elif missing_rows or failed_rows:
            status = "blocked_transition_preview_packet"
        elif needs_rows:
            status = "needs_frame_extraction"
        else:
            status = "needs_frame_extraction"

    updated_grammar = False
    if args.update_transition_grammar and status in {"ready_with_transition_preview_packet", "needs_frame_extraction", "blocked_transition_preview_packet"}:
        updated_grammar = update_transition_grammar(grammar_path, preview_rows)

    summary = {
        "transitionRowCount": len(rows),
        "previewRowCount": len(preview_rows),
        "importantPreviewRowCount": sum(1 for row in preview_rows if row.get("importantBoundary")),
        "readyPreviewRowCount": sum(1 for row in preview_rows if row.get("status") == "ready_with_transition_preview_evidence"),
        "needsFrameExtractionRowCount": sum(1 for row in preview_rows if str(row.get("status", "")).startswith("needs_")),
        "blockedPreviewRowCount": sum(1 for row in preview_rows if str(row.get("status", "")).startswith("blocked")),
        "generatedFrameCount": sum(len(row.get("frameSampleEvidence") or []) for row in preview_rows if row.get("status") == "ready_with_transition_preview_evidence"),
        "ffmpegAvailable": ffmpeg_available,
        "extractedFrames": bool(args.extract_frames),
        "updatedTransitionGrammar": updated_grammar,
    }
    blockers: list[str] = []
    if status == "blocked_missing_transition_grammar_plan":
        blockers.append("missing transition_grammar_plan/transition_grammar_plan.json")
    if status == "blocked_no_transition_rows":
        blockers.append("transition grammar has no transitionRows")
    for row in preview_rows:
        if str(row.get("status", "")).startswith("blocked"):
            blockers.append(f"row {row.get('rowIndex')} {row.get('status')}: {', '.join(row.get('missingSources') or row.get('extractionErrors') or [])}")
    warnings: list[str] = []
    if status == "needs_frame_extraction":
        warnings.append("Run with --extract-frames after source paths are available, or fill preview/frame evidence manually.")
    if args.extract_frames and not ffmpeg_available:
        warnings.append("ffmpeg was not found; frame extraction could not run.")

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {
            "transitionGrammar": str(grammar_path),
            "resolveBlueprint": str(blueprint_path),
            "includeAllRows": bool(args.include_all_rows),
            "extractFrames": bool(args.extract_frames),
            "updateTransitionGrammar": bool(args.update_transition_grammar),
            "ffmpegBin": args.ffmpeg_bin,
        },
        "summary": summary,
        "previewRows": preview_rows,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "packageLocalPreviewEvidence": True,
            "importantBoundaryPreviewRequired": True,
            "sourceFootageReadOnly": True,
            "canUpdateTransitionGrammarDecisionFields": bool(args.update_transition_grammar),
        },
        "safety": safety(),
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Preview Packet",
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
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Rows"])
    for row in report["previewRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}`",
                f"- Status: `{row.get('status')}`",
                f"- Purpose: `{row.get('storyboardPurpose')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Preview: `{row.get('previewStripEvidence')}`",
                f"- Frames: `{', '.join(row.get('frameSampleEvidence') or [])}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Safety",
            "- Writes only package-local preview evidence and optional transition grammar decision fields.",
            "- Does not write Resolve, queue renders, download assets, modify source footage, or modify source drives.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare transition preview/frame evidence packet for important boundaries.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--include-all-rows", action="store_true")
    parser.add_argument("--extract-frames", action="store_true")
    parser.add_argument("--update-transition-grammar", action="store_true")
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    output_dir = Path(report["outputDir"])
    write_json(output_dir / "transition_preview_packet.json", report)
    write_markdown(output_dir / "transition_preview_packet.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"ready_with_transition_preview_packet", "ready_no_important_transitions"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
