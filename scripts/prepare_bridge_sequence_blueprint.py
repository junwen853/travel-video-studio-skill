#!/usr/bin/env python3
"""Materialize bridge sequence rows into a non-destructive Resolve blueprint candidate."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint": "",
    "selectedBridgeBeatRows": "",
    "resolveImplementation": "",
    "preflightEvidence": "",
    "timelineReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def clip_duration(clip: dict[str, Any]) -> float:
    return max(0.0, timeline_end(clip) - timeline_start(clip))


def source_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("sourceStartSeconds"), 0.0) or 0.0)


def source_end(clip: dict[str, Any]) -> float:
    explicit = as_float(clip.get("sourceEndSeconds"))
    if explicit is not None and explicit > source_start(clip):
        return explicit
    return source_start(clip) + max(clip_duration(clip), float(as_float(clip.get("sourceDurationSeconds"), 0.0) or 0.0))


def is_video_clip(clip: dict[str, Any]) -> bool:
    track_type = str(clip.get("trackType") or "video").lower()
    return track_type in {"", "video"} and int(as_float(clip.get("mediaType"), 1) or 1) == 1


def blueprint_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def clip_lookup(clips: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        if not is_video_clip(clip):
            continue
        for key in (str(clip.get("sourcePath") or ""), source_name(clip.get("sourcePath"))):
            if key:
                lookup.setdefault(key, []).append(clip)
    return lookup


def select_source_clip(candidate: dict[str, Any], lookup: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    keys = [str(candidate.get("sourcePath") or ""), str(candidate.get("sourceName") or "")]
    for key in keys:
        rows = lookup.get(key) or []
        if not rows:
            continue
        start = as_float(candidate.get("timelineStartSeconds"))
        if start is None:
            return rows[0]
        rows = sorted(rows, key=lambda clip: abs(timeline_start(clip) - start))
        return rows[0]
    return None


def row_anchor(row: dict[str, Any]) -> float:
    from_clip = row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}
    to_clip = row.get("toClip") if isinstance(row.get("toClip"), dict) else {}
    left_end = timeline_end(from_clip)
    right_start = timeline_start(to_clip)
    if left_end or right_start:
        return (left_end + right_start) / 2.0
    return float(as_float(row.get("timelineStartSeconds"), 0.0) or 0.0)


def target_duration(row: dict[str, Any]) -> float:
    target = row.get("targetDurationSeconds") if isinstance(row.get("targetDurationSeconds"), dict) else {}
    explicit = as_float(target.get("ideal"))
    if explicit and explicit > 0:
        return explicit
    beats = row.get("requiredBeats") if isinstance(row.get("requiredBeats"), list) else []
    return sum(float(as_float(beat.get("idealDurationSeconds"), 1.5) or 1.5) for beat in beats)


def beat_duration(beat: dict[str, Any]) -> float:
    return max(0.75, float(as_float(beat.get("idealDurationSeconds"), 1.5) or 1.5))


def choose_candidate(beat: dict[str, Any], used_sources: dict[str, int], lookup: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidates = beat.get("localCandidateEvidence") if isinstance(beat.get("localCandidateEvidence"), list) else []
    if not candidates:
        return None, None
    scored: list[tuple[tuple[int, int, str], dict[str, Any], dict[str, Any]]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        source_path = str(candidate.get("sourcePath") or "")
        source_clip = select_source_clip(candidate, lookup)
        if not source_clip:
            continue
        use_count = used_sources.get(source_path, 0)
        score = int(as_float(candidate.get("score"), 0) or 0)
        scored.append(((score, -use_count, source_name(source_path)), candidate, source_clip))
    if not scored:
        return None, None
    scored.sort(key=lambda item: item[0], reverse=True)
    candidate, source_clip = scored[0][1], scored[0][2]
    used_sources[str(candidate.get("sourcePath") or "")] = used_sources.get(str(candidate.get("sourcePath") or ""), 0) + 1
    return candidate, source_clip


def source_window(source_clip: dict[str, Any], duration: float, use_index: int) -> tuple[float, float]:
    start = source_start(source_clip)
    end = source_end(source_clip)
    available = max(0.0, end - start)
    if available <= duration:
        return round3(start), round3(max(end, start + duration))
    max_offset = max(0.0, available - duration)
    offset = min(max_offset, (use_index * (duration + 0.5)) % (max_offset + 0.001))
    out_start = start + offset
    return round3(out_start), round3(out_start + duration)


def materialize_row(
    row: dict[str, Any],
    lookup: dict[str, list[dict[str, Any]]],
    *,
    overlay_track: int,
    track_cursor: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], float]:
    beats = row.get("requiredBeats") if isinstance(row.get("requiredBeats"), list) else []
    ideal_duration = target_duration(row)
    start = max(0.0, row_anchor(row) - ideal_duration / 2.0)
    if start < track_cursor:
        start = track_cursor + 0.25
    cursor = start
    used_sources: dict[str, int] = {}
    inserted: list[dict[str, Any]] = []
    beat_rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for beat in beats:
        duration = beat_duration(beat)
        candidate, source_clip = choose_candidate(beat, used_sources, lookup)
        if not candidate or not source_clip:
            missing.append({"beatIndex": beat.get("beatIndex"), "function": beat.get("function"), "reason": "no local candidate resolved to blueprint source clip"})
            cursor += duration
            continue
        use_index = used_sources.get(str(candidate.get("sourcePath") or ""), 1) - 1
        src_start, src_end = source_window(source_clip, duration, use_index)
        clip = copy.deepcopy(source_clip)
        clip.update(
            {
                "role": "bridge_sequence_insert",
                "trackType": "video",
                "trackIndex": overlay_track,
                "mediaType": 1,
                "timelineStartSeconds": round3(cursor),
                "timelineEndSeconds": round3(cursor + duration),
                "durationSeconds": round3(duration),
                "sourceStartSeconds": src_start,
                "sourceEndSeconds": src_end,
                "includeSourceAudio": False,
                "purpose": f"bridge sequence beat: {beat.get('function')} for transition row {row.get('rowIndex')}",
                "bridgeSequence": {
                    "kind": "bridge_sequence_insert",
                    "sourceSequenceRowIndex": row.get("rowIndex"),
                    "sequenceType": row.get("sequenceType"),
                    "beatIndex": beat.get("beatIndex"),
                    "beatFunction": beat.get("function"),
                    "bgmPhraseCue": row.get("bgmPhraseCue"),
                    "titleZonePolicy": row.get("titleZonePolicy"),
                    "originalCandidateScore": candidate.get("score"),
                },
            }
        )
        inserted.append(clip)
        beat_rows.append(
            {
                "beatIndex": beat.get("beatIndex"),
                "function": beat.get("function"),
                "sourcePath": clip.get("sourcePath"),
                "sourceName": source_name(clip.get("sourcePath")),
                "timelineStartSeconds": round3(cursor),
                "timelineEndSeconds": round3(cursor + duration),
                "sourceStartSeconds": src_start,
                "sourceEndSeconds": src_end,
                "candidateScore": candidate.get("score"),
            }
        )
        cursor += duration
    row_report = {
        "rowIndex": row.get("rowIndex"),
        "sequenceType": row.get("sequenceType"),
        "status": "materialized" if not missing and inserted else "needs_bridge_sequence_blueprint_repair",
        "overlayTrackIndex": overlay_track,
        "targetStartSeconds": round3(start),
        "targetEndSeconds": round3(cursor),
        "insertedBeatCount": len(inserted),
        "requiredBeatCount": len(beats),
        "missingBeatCount": len(missing),
        "insertedBeats": beat_rows,
        "missingBeats": missing,
        "bgmPhraseCue": row.get("bgmPhraseCue"),
        "titleZoneSafe": row.get("titleZoneSafe"),
        "decision": dict(DECISION_FIELDS),
    }
    return inserted, row_report, cursor


def sort_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        clips,
        key=lambda clip: (
            round3(timeline_start(clip)),
            int(as_float(clip.get("trackIndex"), 1) or 1),
            str(clip.get("role") or ""),
            str(clip.get("sourcePath") or ""),
        ),
    )


def safety_policy() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "mutatesActiveBlueprintByDefault": False,
    }


def build_candidate(package_dir: Path, *, overlay_track: int, update_blueprint: bool) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    plan_path = package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json"
    output_dir = package_dir / "bridge_sequence_blueprint"
    candidate_path = output_dir / "resolve_timeline_blueprint_bridge_sequence.json"
    report_path = output_dir / "bridge_sequence_blueprint_report.json"
    markdown_path = output_dir / "bridge_sequence_blueprint_report.md"

    blueprint = load_json(blueprint_path)
    plan = load_json(plan_path)
    if not isinstance(blueprint, dict) or not isinstance(plan, dict):
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "needs_bridge_sequence_blueprint_inputs",
            "packageDir": str(package_dir),
            "inputs": {
                "resolveBlueprint": str(blueprint_path),
                "resolveBlueprintExists": blueprint_path.exists(),
                "bridgeSequencePlan": str(plan_path),
                "bridgeSequencePlanExists": plan_path.exists(),
            },
            "outputs": {
                "candidateBlueprint": str(candidate_path),
                "reportJson": str(report_path),
                "reportMarkdown": str(markdown_path),
            },
            "summary": {},
            "materializedRows": [],
            "safety": safety_policy(),
            "nextActions": ["Run prepare_bridge_sequence_plan.py after transition motif planning, then rerun this script."],
        }
        write_json(report_path, report)
        write_markdown(markdown_path, report)
        return report

    sequence_rows = plan.get("sequenceRows") if isinstance(plan.get("sequenceRows"), list) else []
    clips = blueprint_clips(blueprint)
    lookup = clip_lookup(clips)
    inserted_clips: list[dict[str, Any]] = []
    materialized_rows: list[dict[str, Any]] = []
    track_cursor = 0.0
    for row in sorted([row for row in sequence_rows if isinstance(row, dict)], key=row_anchor):
        row_inserted, row_report, track_cursor = materialize_row(row, lookup, overlay_track=overlay_track, track_cursor=track_cursor)
        inserted_clips.extend(row_inserted)
        materialized_rows.append(row_report)

    candidate = copy.deepcopy(blueprint)
    candidate["clips"] = sort_clips(clips + inserted_clips)
    candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    candidate["bridgeSequenceBlueprintPlan"] = {
        "status": "candidate_not_applied_to_resolve",
        "createdAt": candidate["updatedAt"],
        "sourceBlueprint": str(blueprint_path),
        "sourceBridgeSequencePlan": str(plan_path),
        "report": str(report_path),
        "candidateBlueprint": str(candidate_path),
        "overlayTrackIndex": overlay_track,
        "defaultBehavior": "writes a separate candidate blueprint and leaves the active blueprint untouched",
    }
    candidate.setdefault("timelineMarkers", [])
    if isinstance(candidate["timelineMarkers"], list):
        for row in materialized_rows:
            candidate["timelineMarkers"].append(
                {
                    "startSeconds": row["targetStartSeconds"],
                    "durationSeconds": max(1.0, row["targetEndSeconds"] - row["targetStartSeconds"]),
                    "color": "Blue",
                    "name": f"Bridge Sequence {row.get('rowIndex')}",
                    "note": f"{row.get('sequenceType')} materialized on V{overlay_track}",
                    "role": "bridge_sequence_candidate_marker",
                    "payload": {"rowIndex": row.get("rowIndex"), "insertedBeatCount": row.get("insertedBeatCount")},
                }
            )
        candidate["timelineMarkers"] = sorted(candidate["timelineMarkers"], key=lambda item: (float(item.get("startSeconds") or 0.0), str(item.get("role") or "")))

    missing_rows = [row for row in materialized_rows if int(row.get("missingBeatCount") or 0) > 0]
    incomplete_rows = [
        row
        for row in materialized_rows
        if int(row.get("insertedBeatCount") or 0) <= 0
        or int(row.get("insertedBeatCount") or 0) < int(row.get("requiredBeatCount") or 0)
    ]
    decision_keys = set(DECISION_FIELDS)
    rows_with_decisions = sum(1 for row in materialized_rows if decision_keys.issubset(set((row.get("decision") or {}).keys())))
    status = "ready_with_bridge_sequence_blueprint" if materialized_rows and inserted_clips and not missing_rows and not incomplete_rows else "needs_bridge_sequence_blueprint_repair"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(blueprint_path),
            "bridgeSequencePlan": str(plan_path),
        },
        "outputs": {
            "candidateBlueprint": str(candidate_path),
            "reportJson": str(report_path),
            "reportMarkdown": str(markdown_path),
            "activeBlueprintUpdated": bool(update_blueprint),
        },
        "summary": {
            "sequenceRowCount": len(sequence_rows),
            "materializedRowCount": len(materialized_rows),
            "rowsWithDecisionFields": rows_with_decisions,
            "insertedBeatClipCount": len(inserted_clips),
            "missingBeatRowCount": len(missing_rows),
            "missingBeatCount": sum(int(row.get("missingBeatCount") or 0) for row in materialized_rows),
            "incompleteRowCount": len(incomplete_rows),
            "overlayTrackIndex": overlay_track,
            "candidateClipCount": len(candidate.get("clips") or []),
            "sourceClipCount": len(clips),
        },
        "materializedRows": materialized_rows,
        "selectionRubric": {
            "pass": [
                "The candidate blueprint contains actual bridge_sequence_insert clips for each required beat.",
                "Bridge inserts are video-only and placed on a dedicated overlay track without mutating the active blueprint by default.",
                "Every row has decision fields for approval, preflight, Resolve readback, and frame-sample evidence.",
                "The candidate can be preflighted before any Resolve apply or package fork.",
            ],
            "reject": [
                "The report only describes bridge beats but adds no candidate blueprint clips.",
                "A required bridge beat cannot resolve to a local source clip.",
                "The script writes Resolve, queues render, downloads assets, or mutates source footage.",
                "Inserted bridge clips carry source-camera audio into BGM-only transition windows.",
            ],
        },
        "safety": safety_policy(),
        "nextActions": [
            f"Run audit_resolve_blueprint.py --blueprint {candidate_path} --package-dir {package_dir} before using this candidate.",
            "Review bridge_sequence_blueprint_report.json and fill decision.approveCandidateBlueprint before Resolve apply.",
            "If approved, use a package fork or explicit --update-blueprint path so stale final QA is not reused.",
        ],
    }

    write_json(candidate_path, candidate)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    if update_blueprint:
        backup = package_dir / f"resolve_timeline_blueprint.before_bridge_sequence_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        write_json(backup, blueprint)
        write_json(blueprint_path, candidate)
        report["outputs"]["activeBlueprintBackup"] = str(backup)
        write_json(report_path, report)
        write_markdown(markdown_path, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Bridge Sequence Blueprint Report",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Materialized Rows",
    ]
    for row in report.get("materializedRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('sequenceType')}",
                f"- Status: `{row.get('status')}`",
                f"- Overlay track: V{row.get('overlayTrackIndex')}",
                f"- Timeline: {row.get('targetStartSeconds')}s-{row.get('targetEndSeconds')}s",
                f"- Inserted beats: {row.get('insertedBeatCount')}/{row.get('requiredBeatCount')}",
            ]
        )
        for beat in row.get("insertedBeats") or []:
            lines.append(f"  - `{beat.get('function')}` {beat.get('timelineStartSeconds')}s-{beat.get('timelineEndSeconds')}s: `{beat.get('sourceName')}`")
        for beat in row.get("missingBeats") or []:
            lines.append(f"  - missing `{beat.get('function')}`: {beat.get('reason')}")
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a bridge-sequence Resolve blueprint candidate.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--overlay-track", type=int, default=4, help="Video track used for candidate bridge inserts. Default: 4.")
    parser.add_argument("--update-blueprint", action="store_true", help="Replace the active blueprint after writing a backup. Default is non-destructive.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_candidate(Path(args.package_dir), overlay_track=max(2, args.overlay_track), update_blueprint=args.update_blueprint)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report.get("status"), **(report.get("summary") or {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
