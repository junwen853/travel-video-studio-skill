#!/usr/bin/env python3
"""Audit whether rhythm-recut decisions survived into the final candidate blueprint."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_UPSTREAM_REPORTS = {
    "edit_rhythm_plan/edit_rhythm_plan.json": {"ready_with_edit_rhythm_plan"},
    "rhythm_recut_blueprint/rhythm_recut_blueprint_report.json": {
        "ready_with_rhythm_recut_blueprint",
        "ready_no_recut_needed",
    },
    "final_blueprint_lineage_contract_audit.json": {"passed"},
    "creator_cut_application_contract_audit.json": {"passed"},
    "final_source_usage_contract_audit.json": {"passed"},
    "timeline_variety_contract_audit.json": {"passed"},
}
TITLE_OR_OVERLAY_TOKENS = (
    "subtitle",
    "title_card",
    "chapter_title",
    "city_aerial_title",
    "opening_city_aerial_title",
    "ending_city_aerial_title",
)
REPAIR_SOURCE_KINDS = {
    "rhythm_recut_candidate",
    "transition_polish_candidate",
    "explicit_blueprint",
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


def round3(value: float) -> float:
    return round(float(value), 3)


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def source_key(value: Any) -> str:
    return source_name(value).lower() or str(value or "").lower()


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def timeline_start(clip: dict[str, Any]) -> float:
    return as_float(first_present(clip.get("timelineStartSeconds"), clip.get("recordStartSeconds"), clip.get("startSeconds")))


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(first_present(clip.get("timelineEndSeconds"), clip.get("recordEndSeconds"), clip.get("endSeconds")), -1.0)
    if explicit > start:
        return explicit
    duration = clip_duration(clip)
    return start + duration


def clip_duration(clip: dict[str, Any]) -> float:
    start = as_float(first_present(clip.get("timelineStartSeconds"), clip.get("recordStartSeconds"), clip.get("startSeconds")), -1.0)
    end = as_float(first_present(clip.get("timelineEndSeconds"), clip.get("recordEndSeconds"), clip.get("endSeconds")), -1.0)
    if start >= 0 and end > start:
        return end - start
    for key in ("durationSeconds", "sourceDurationSeconds"):
        value = as_float(clip.get(key), -1.0)
        if value > 0:
            return value
    source_start = as_float(clip.get("sourceStartSeconds"))
    source_end = as_float(clip.get("sourceEndSeconds"))
    return max(0.0, source_end - source_start)


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath", "sourceName", "name", "notes")
    ).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt")):
        return False
    if any(token in text for token in TITLE_OR_OVERLAY_TOKENS) and "bridge" not in text and "scenic" not in text:
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    return track_type in {"", "video"} and as_int(clip.get("mediaType"), 1) == 1


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    clips = [row for row in rows if isinstance(row, dict) and is_video_clip(row)]
    return sorted(clips, key=lambda item: (timeline_start(item), timeline_end(item), str(item.get("sourcePath") or "")))


def choose_blueprint(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path, str, bool]:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
        return load_json(path), path, "explicit_blueprint", is_inside(path, package_dir)
    candidates = [
        (package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json", "candidateBlueprint", "transition_polish_candidate"),
        (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json", "candidateBlueprint", "rhythm_recut_candidate"),
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


def report_status(data: Any) -> str | None:
    return data.get("status") if isinstance(data, dict) else None


def audit_upstream(package_dir: Path) -> tuple[dict[str, Any], list[str]]:
    evidence: dict[str, Any] = {}
    blockers: list[str] = []
    for rel, accepted in REQUIRED_UPSTREAM_REPORTS.items():
        path = package_dir / rel
        data = load_json(path) or {}
        status = report_status(data)
        evidence[rel] = {
            "exists": path.exists(),
            "status": status,
            "acceptedStatuses": sorted(accepted),
        }
        if not path.exists():
            blockers.append(f"missing upstream report: {rel}")
        elif status not in accepted:
            blockers.append(f"{rel} status is {status!r}, expected one of {sorted(accepted)}")
    return evidence, blockers


def expected_recut_sources(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = report.get("recutRows") if isinstance(report.get("recutRows"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = source_key(row.get("sourcePath") or row.get("sourceName"))
        if not key:
            continue
        out[key] = row
    return out


def clip_has_recut_kind(clip: dict[str, Any], kind: str | None = None) -> bool:
    payload = clip.get("rhythmRecut") if isinstance(clip.get("rhythmRecut"), dict) else {}
    if not payload:
        return False
    return kind is None or payload.get("kind") == kind


def matching_recut_clips(clips: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    key = source_key(source)
    return [
        clip
        for clip in clips
        if source_key(clip.get("sourcePath") or clip.get("sourceName")) == key and clip_has_recut_kind(clip)
    ]


def audit_recut_application(
    package_dir: Path,
    blueprint: dict[str, Any],
    blueprint_path: Path,
    blueprint_kind: str,
    blueprint_inside_package: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str]]:
    rhythm = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
    rhythm_summary = summary_of(rhythm)
    recut_report = load_json(package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json") or {}
    recut_summary = summary_of(recut_report)
    clips = primary_visual_clips(blueprint)
    durations = [clip_duration(clip) for clip in clips if clip_duration(clip) > 0]
    recut_source_rows = expected_recut_sources(recut_report)
    row_reports: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if not isinstance(blueprint, dict):
        blockers.append(f"missing or unreadable blueprint: {blueprint_path}")
    if not blueprint_path.exists():
        blockers.append(f"blueprint path does not exist: {blueprint_path}")
    if not blueprint_inside_package:
        blockers.append(f"blueprint is outside package: {blueprint_path}")
    if recut_report.get("status") == "ready_with_rhythm_recut_blueprint" and blueprint_kind not in REPAIR_SOURCE_KINDS:
        blockers.append(f"final blueprint kind {blueprint_kind!r} does not use rhythm/transition-polish recut candidate chain")

    for key, row in recut_source_rows.items():
        source = str(row.get("sourcePath") or row.get("sourceName") or key)
        final_matches = matching_recut_clips(clips, source)
        main_segments = [clip for clip in final_matches if clip_has_recut_kind(clip, "main_segment")]
        cutaways = [
            clip
            for clip in clips
            if clip_has_recut_kind(clip, "cutaway_insert")
            and as_int((clip.get("rhythmRecut") or {}).get("replacementForRowIndex"), -1) == as_int(row.get("rowIndex"), -2)
        ]
        source_cutaway_count = as_int(row.get("cutawayInsertCount"))
        issues: list[str] = []
        if len(main_segments) < as_int(row.get("mainSegmentCount"), 1):
            issues.append("missing_recut_main_segments_in_final_blueprint")
        if len(cutaways) < source_cutaway_count:
            issues.append("missing_recut_cutaway_inserts_in_final_blueprint")
        if any(clip.get("includeSourceAudio") is not False for clip in cutaways):
            issues.append("recut_cutaway_leaks_source_audio")
        max_segment = max([clip_duration(clip) for clip in main_segments], default=0.0)
        soft_limit = as_float(recut_summary.get("longShotSoftLimitSeconds"), as_float(rhythm.get("targetRhythmProfile", {}).get("longShotSoftLimitSeconds"), 12.0))
        if max_segment > max(soft_limit, 12.0):
            issues.append("recut_main_segment_still_too_long")
        row_reports.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "sourcePath": row.get("sourcePath"),
                "sourceName": row.get("sourceName"),
                "originalDurationSeconds": row.get("originalDurationSeconds"),
                "expectedMainSegmentCount": row.get("mainSegmentCount"),
                "actualMainSegmentCount": len(main_segments),
                "expectedCutawayInsertCount": source_cutaway_count,
                "actualCutawayInsertCount": len(cutaways),
                "maxFinalMainSegmentSeconds": round3(max_segment),
                "issues": issues,
            }
        )
        blockers.extend(f"row {row.get('rowIndex')}: {issue}" for issue in issues)

    recut_clip_count = sum(1 for clip in clips if clip_has_recut_kind(clip))
    recut_cutaway_count = sum(1 for clip in clips if clip_has_recut_kind(clip, "cutaway_insert"))
    recut_main_count = sum(1 for clip in clips if clip_has_recut_kind(clip, "main_segment"))
    long_soft_limit = as_float(recut_summary.get("longShotSoftLimitSeconds"), 12.0)
    long_final_count = sum(1 for value in durations if value > long_soft_limit)
    if recut_report.get("status") == "ready_with_rhythm_recut_blueprint":
        if recut_clip_count <= 0:
            blockers.append("final blueprint has no rhythmRecut clip annotations")
        if recut_main_count <= 0:
            blockers.append("final blueprint has no rhythmRecut main segments")
        if recut_cutaway_count <= 0:
            blockers.append("final blueprint has no rhythmRecut cutaway inserts")
        if as_int(recut_summary.get("longShotRiskAfter")) >= as_int(recut_summary.get("longShotRiskBefore")):
            blockers.append("rhythm recut report does not reduce long-shot risk")
        if as_float(recut_summary.get("averagePrimaryShotAfterSeconds")) >= as_float(recut_summary.get("averagePrimaryShotBeforeSeconds")):
            blockers.append("rhythm recut report does not reduce average primary shot length")
    elif recut_report.get("status") == "ready_no_recut_needed":
        if as_int(rhythm_summary.get("rhythmRiskCount")) > 0:
            blockers.append("edit rhythm plan has risk rows but recut report says no recut is needed")
        if long_final_count > 0:
            warnings.append(f"final blueprint has {long_final_count} clips over the recut soft limit despite no recut-needed status")

    summary = {
        "blueprintKind": blueprint_kind,
        "visualClipCount": len(clips),
        "rhythmPlanRiskCount": rhythm_summary.get("rhythmRiskCount"),
        "rhythmPlanPrimaryVisualShotCount": rhythm_summary.get("primaryVisualShotCount"),
        "recutStatus": recut_report.get("status"),
        "recutSourceRowCount": len(recut_source_rows),
        "passedRecutRowCount": sum(1 for row in row_reports if row.get("status") == "passed"),
        "blockedRecutRowCount": sum(1 for row in row_reports if row.get("status") == "blocked"),
        "finalRhythmRecutClipCount": recut_clip_count,
        "finalRhythmRecutMainSegmentCount": recut_main_count,
        "finalRhythmRecutCutawayCount": recut_cutaway_count,
        "finalAverageVisualShotSeconds": round3(sum(durations) / len(durations)) if durations else 0.0,
        "finalMedianVisualShotSeconds": round3(statistics.median(durations)) if durations else 0.0,
        "finalMaxVisualShotSeconds": round3(max(durations, default=0.0)),
        "finalLongShotRiskCount": long_final_count,
        "recutAverageBeforeSeconds": recut_summary.get("averagePrimaryShotBeforeSeconds"),
        "recutAverageAfterSeconds": recut_summary.get("averagePrimaryShotAfterSeconds"),
        "recutLongRiskBefore": recut_summary.get("longShotRiskBefore"),
        "recutLongRiskAfter": recut_summary.get("longShotRiskAfter"),
        "recutDurationDeltaSeconds": recut_summary.get("durationDeltaSeconds"),
        "bgmPhrasePlanPreserved": recut_summary.get("bgmPhrasePlanPreserved"),
        "blockerCount": len(blockers),
        "warningCount": len(warnings),
    }
    return summary, row_reports, blockers, warnings


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def build_report(package_dir: Path, explicit_blueprint: str | None = None) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    upstream, upstream_blockers = audit_upstream(package_dir)
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, explicit_blueprint)
    summary: dict[str, Any] = {}
    row_reports: list[dict[str, Any]] = []
    blockers = list(upstream_blockers)
    warnings: list[str] = []
    if isinstance(blueprint, dict):
        summary, row_reports, application_blockers, warnings = audit_recut_application(
            package_dir,
            blueprint,
            blueprint_path,
            blueprint_kind,
            blueprint_inside_package,
        )
        blockers.extend(application_blockers)
    else:
        blockers.append(f"missing or unreadable blueprint: {blueprint_path}")

    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "explicitBlueprint": explicit_blueprint,
            "upstreamReports": upstream,
        },
        "summary": summary,
        "recutRows": row_reports,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Rhythm Recut Application Contract Audit",
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
    lines.extend(["", "## Recut Rows"])
    rows = report.get("recutRows") if isinstance(report.get("recutRows"), list) else []
    if not rows:
        lines.append("- None.")
    for row in rows[:120]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('sourceName')}",
                f"- Status: `{row.get('status')}`",
                f"- Expected/actual main segments: `{row.get('expectedMainSegmentCount')}` / `{row.get('actualMainSegmentCount')}`",
                f"- Expected/actual cutaways: `{row.get('expectedCutawayInsertCount')}` / `{row.get('actualCutawayInsertCount')}`",
                f"- Max final main segment: `{row.get('maxFinalMainSegmentSeconds')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Repair Route",
            "",
            "- If this blocks, do not add more transition effects to hide long raw holds.",
            "- Rebuild `rhythm_recut_blueprint`, run `prepare_transition_polish_blueprint`, and rerun lineage/application audits.",
            "- If the recut is approved, fork with `prepare_rhythm_recut_apply_package.py` before Resolve apply.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit rhythm recut application on the final candidate blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args.blueprint)
    write_json(package_dir / "rhythm_recut_application_contract_audit.json", report)
    write_markdown(package_dir / "rhythm_recut_application_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
