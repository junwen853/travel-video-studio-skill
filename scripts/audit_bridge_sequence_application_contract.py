#!/usr/bin/env python3
"""Audit whether planned bridge sequences survive into the final candidate blueprint."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
IMPORTANT_SEQUENCE_TYPES = {
    "clean_title_bridge_sequence",
    "route_texture_bridge_sequence",
    "ending_aftertaste_sequence",
}


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


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def source_key(value: Any) -> str:
    text = str(value or "")
    return text or source_name(value)


def min_unique_sources_for_row(row: dict[str, Any], expected_count: int) -> int:
    sequence_type = str(row.get("sequenceType") or "")
    if expected_count <= 1:
        return expected_count
    if sequence_type == "route_texture_bridge_sequence":
        return min(3, expected_count)
    if sequence_type in {"clean_title_bridge_sequence", "ending_aftertaste_sequence", "visual_match_sequence"}:
        return min(2, expected_count)
    return min(2, expected_count)


def adjacent_repeat_count(values: list[str]) -> int:
    return sum(1 for left, right in zip(values, values[1:]) if left and left == right)


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def choose_blueprint(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path, str, bool]:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
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
            path = (package_dir / path).resolve()
        data = load_json(path)
        if isinstance(data, dict):
            return data, path, kind, is_inside(path, package_dir)
    active = package_dir / "resolve_timeline_blueprint.json"
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
    required = row.get("requiredBeats") if isinstance(row.get("requiredBeats"), list) else []
    return len(required) >= 3


def expected_functions(row: dict[str, Any]) -> list[str]:
    beats = row.get("requiredBeats") if isinstance(row.get("requiredBeats"), list) else []
    return [str(beat.get("function") or "") for beat in beats if isinstance(beat, dict) and beat.get("function")]


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
    return sorted(out, key=lambda item: (timeline_start(item), as_int(item.get("trackIndex"), 1), source_name(item.get("sourcePath") or item.get("sourceName"))))


def materialized_row_lookup(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = report.get("materializedRows") if isinstance(report.get("materializedRows"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = as_int(row.get("rowIndex"), -1)
        if index >= 0:
            out[index] = row
    return out


def source_audio_leaks(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leaks: list[dict[str, Any]] = []
    for clip in clips:
        if clip.get("includeSourceAudio") is False:
            continue
        policy = " ".join(str(clip.get(key) or "") for key in ("audioPolicy", "purpose", "notes")).lower()
        if "bgm" in policy and "no" in policy and "voice" in policy:
            continue
        leaks.append(clip)
    return leaks


def row_audit(row: dict[str, Any], clips: list[dict[str, Any]], materialized: dict[int, dict[str, Any]] | None) -> dict[str, Any]:
    row_index = as_int(row.get("rowIndex"), -1)
    expected = expected_functions(row)
    matched: list[dict[str, Any]] = []
    for clip in clips:
        payload = bridge_insert_payload(clip)
        if as_int(payload.get("sourceSequenceRowIndex"), -9999) == row_index:
            matched.append(clip)
    matched_functions = [str(bridge_insert_payload(clip).get("beatFunction") or "") for clip in matched]
    expected_set = {item for item in expected if item}
    matched_set = {item for item in matched_functions if item}
    missing_functions = sorted(expected_set - matched_set)
    leaks = source_audio_leaks(matched)
    source_sequence = [source_key(clip.get("sourcePath") or clip.get("sourceName")) for clip in matched]
    unique_source_count = len({item for item in source_sequence if item})
    minimum_unique_source_count = min_unique_sources_for_row(row, len(expected))
    adjacent_repeats = adjacent_repeat_count(source_sequence)
    issues: list[str] = []
    if not matched:
        issues.append("planned_bridge_sequence_row_missing_from_final_candidate")
    if expected and len(matched) < len(expected):
        issues.append("final_candidate_has_fewer_bridge_beats_than_plan")
    if missing_functions:
        issues.append("final_candidate_missing_required_bridge_beat_functions")
    if leaks:
        issues.append("bridge_sequence_insert_has_source_audio_enabled")
    if len(matched) >= len(expected) and unique_source_count < minimum_unique_source_count:
        issues.append("bridge_sequence_uses_too_few_distinct_sources")
    if len(expected) >= 3 and adjacent_repeats > 0:
        issues.append("bridge_sequence_repeats_same_source_on_adjacent_beats")
    mat = (materialized or {}).get(row_index) or {}
    if materialized is not None:
        if not mat:
            issues.append("bridge_sequence_blueprint_report_has_no_materialized_row")
        elif as_int(mat.get("insertedBeatCount")) < len(expected):
            issues.append("bridge_sequence_blueprint_materialized_too_few_beats")
        if mat and mat.get("sourceDiversityStatus") != "passed":
            issues.append("bridge_sequence_blueprint_source_diversity_not_passed")
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
        "sourceAudioLeakCount": len(leaks),
        "uniqueSourceCount": unique_source_count,
        "minimumUniqueSourceCount": minimum_unique_source_count,
        "adjacentRepeatedSourceCount": adjacent_repeats,
        "sourceDiversityStatus": "passed" if unique_source_count >= minimum_unique_source_count and adjacent_repeats == 0 else "blocked",
        "timelineStartSeconds": round3(min((timeline_start(clip) for clip in matched), default=0.0)),
        "timelineEndSeconds": round3(max((timeline_end(clip) for clip in matched), default=0.0)),
        "sourceNames": [source_name(clip.get("sourcePath") or clip.get("sourceName")) for clip in matched],
        "materializedRowStatus": mat.get("status"),
        "materializedInsertedBeatCount": mat.get("insertedBeatCount"),
        "issues": issues,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint, blueprint_path, blueprint_kind, blueprint_inside = choose_blueprint(package_dir, args.blueprint)
    plan_path = package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json"
    blueprint_report_path = package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json"
    plan = load_json(plan_path) or {}
    blueprint_report = load_json(blueprint_report_path) or {}
    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "blueprint": str(blueprint_path),
                "blueprintExists": blueprint_path.exists(),
                "blueprintKind": blueprint_kind,
                "blueprintInsidePackage": blueprint_inside,
                "bridgeSequencePlan": str(plan_path),
                "bridgeSequencePlanExists": plan_path.exists(),
                "bridgeSequenceBlueprintReport": str(blueprint_report_path),
                "bridgeSequenceBlueprintReportExists": blueprint_report_path.exists(),
            },
            "summary": {},
            "sequenceRows": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    rows = bridge_sequence_rows(plan)
    required_rows = [row for row in rows if is_required_sequence_row(row)]
    inserts = bridge_insert_clips(blueprint)
    materialized = materialized_row_lookup(blueprint_report) if isinstance(blueprint_report, dict) else {}
    audited = [row_audit(row, inserts, materialized) for row in required_rows]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    leaks = source_audio_leaks(inserts)
    expected_total = sum(as_int(row.get("expectedBeatCount")) for row in audited)
    applied_total = sum(as_int(row.get("appliedBeatClipCount")) for row in audited)
    blockers = [f"bridge sequence row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked[:80]]
    diversity_issue_rows = [row for row in audited if row.get("sourceDiversityStatus") != "passed"]
    adjacent_repeat_rows = [row for row in audited if as_int(row.get("adjacentRepeatedSourceCount")) > 0]
    warnings: list[str] = []
    if plan.get("status") != "ready_with_bridge_sequence_plan":
        blockers.append(f"bridge_sequence_plan status is not ready: {plan.get('status')}")
    if blueprint_report.get("status") != "ready_with_bridge_sequence_blueprint":
        blockers.append(f"bridge_sequence_blueprint_report status is not ready: {blueprint_report.get('status')}")
    if not blueprint_path.exists():
        blockers.append(f"blueprint path does not exist: {blueprint_path}")
    if not blueprint_inside:
        blockers.append(f"blueprint is outside package: {blueprint_path}")
    if rows and not required_rows:
        blockers.append("bridge_sequence_plan has no ready important sequence rows to apply")
    if required_rows and not inserts:
        blockers.append("final candidate contains no bridge_sequence_insert clips")
    if leaks:
        blockers.append(f"bridge sequence inserts with source audio enabled: {len(leaks)}")
    if expected_total and applied_total < expected_total:
        blockers.append(f"final candidate dropped planned bridge beats: {applied_total}/{expected_total}")
    if not rows:
        warnings.append("bridge_sequence_plan has no sequence rows")
    status = "passed" if not blockers and bool(required_rows) else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
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
        },
        "summary": {
            "plannedSequenceRowCount": len(rows),
            "requiredSequenceRowCount": len(required_rows),
            "auditedSequenceRowCount": len(audited),
            "passedSequenceRowCount": sum(1 for row in audited if row.get("status") == "passed"),
            "blockedSequenceRowCount": len(blocked),
            "expectedBeatClipCount": expected_total,
            "appliedBeatClipCount": applied_total,
            "missingBeatClipCount": max(0, expected_total - applied_total),
            "finalBridgeInsertClipCount": len(inserts),
            "sourceAudioLeakClipCount": len(leaks),
            "rowsWithSourceDiversity": sum(1 for row in audited if row.get("sourceDiversityStatus") == "passed"),
            "sourceDiversityIssueRowCount": len(diversity_issue_rows),
            "adjacentRepeatedSourceRowCount": len(adjacent_repeat_rows),
            "minimumUniqueSourceTotal": sum(as_int(row.get("minimumUniqueSourceCount")) for row in audited),
            "actualUniqueSourceTotal": sum(as_int(row.get("uniqueSourceCount")) for row in audited),
            "blockerCount": len(blockers),
        },
        "sequenceRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Bridge Sequence Application Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report['inputs'].get('blueprint')}`",
        f"Blueprint kind: `{report['inputs'].get('blueprintKind')}`",
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
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Sequence Rows"])
    for row in report.get("sequenceRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('sequenceType')}",
                f"- Status: `{row.get('status')}`",
                f"- Expected beats: {row.get('expectedBeatCount')} `{', '.join(row.get('expectedBeatFunctions') or [])}`",
                f"- Applied beats: {row.get('appliedBeatClipCount')} `{', '.join(row.get('appliedBeatFunctions') or [])}`",
                f"- Source audio leaks: {row.get('sourceAudioLeakCount')}",
                f"- Source diversity: `{row.get('sourceDiversityStatus')}` {row.get('uniqueSourceCount')}/{row.get('minimumUniqueSourceCount')} unique, adjacent repeats `{row.get('adjacentRepeatedSourceCount')}`",
                f"- Sources: `{', '.join(row.get('sourceNames') or [])}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether bridge sequences survive into the final candidate blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "bridge_sequence_application_contract_audit.json", report)
    write_markdown(package_dir / "bridge_sequence_application_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
