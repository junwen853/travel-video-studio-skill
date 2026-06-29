#!/usr/bin/env python3
"""Audit whether the final candidate blueprint actually applies creator-cut decisions."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


REJECT_TIERS = {"reject_or_replace", "reject_or_review", "reject_excluded"}
UTILITY_TIERS = {"utility_only", "utility_context"}
MOTION_FUNCTIONS = {"route_movement", "transport_motion", "route_transition"}
TEXTURE_FUNCTIONS = {"lived_in_detail", "street_texture"}
PAYOFF_FUNCTIONS = {"destination_payoff", "landmark_payoff", "opening_hook", "ending_aftertaste"}
CONTEXT_FUNCTIONS = {"title_bridge", "scenic_breathing", "route_observation", "opening_hook"}
AFTERTASTE_FUNCTIONS = {"ending_aftertaste", "aftertaste"}
WEAK_TERMS = ("black", "placeholder", "slate", "generic", "test", "sample", "duplicate", "obstruct", "blur")
TITLE_TERMS = ("title", "opening_city", "chapter_title", "ending_city", "subtitle_overlay")


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


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
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


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


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


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath", "sourceName", "name", "notes")
    ).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if any(term in text for term in TITLE_TERMS) and "title" in text and "bridge" not in text and "scenic" not in text:
        # Generated title overlays are not primary creator-cut footage.
        return False
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt")):
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type not in {"", "video"}:
        return False
    return as_int(clip.get("mediaType"), 1) == 1


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


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    video = [row for row in rows if isinstance(row, dict) and is_video_clip(row)]
    return sorted(video, key=lambda item: (timeline_start(item), timeline_end(item), str(item.get("sourcePath") or "")))


def creator_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("shotRows", "selectionRows", "rows"):
        rows = plan.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def creator_lookup(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        keys = {
            str(row.get("sourcePath") or ""),
            str(row.get("sourceName") or ""),
            source_name(row.get("sourcePath") or row.get("sourceName")),
        }
        for key in keys:
            if key:
                lookup.setdefault(key, []).append(row)
    return lookup


def match_creator_row(clip: dict[str, Any], lookup: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    keys = [
        str(clip.get("sourcePath") or ""),
        str(clip.get("sourceName") or ""),
        source_name(clip.get("sourcePath") or clip.get("sourceName")),
    ]
    for key in keys:
        rows = lookup.get(key)
        if rows:
            return rows[0]
    return None


def normalize_function(clip: dict[str, Any], row: dict[str, Any] | None) -> str:
    if row and row.get("creatorFunction"):
        return str(row.get("creatorFunction"))
    text = clip_text(clip)
    if "ending" in text:
        return "ending_aftertaste"
    if "opening" in text:
        return "opening_hook"
    if any(term in text for term in ("station", "train", "metro", "airport", "road", "walk", "route", "bridge")):
        return "route_movement"
    if any(term in text for term in ("food", "hotel", "shop", "street", "market", "ticket", "sign", "weather")):
        return "lived_in_detail"
    if any(term in text for term in ("aerial", "skyline", "landmark", "temple", "tower", "castle", "coast", "harbor", "night")):
        return "destination_payoff"
    return "route_observation"


def function_groups(function: str) -> set[str]:
    groups: set[str] = set()
    if function in MOTION_FUNCTIONS:
        groups.add("movement")
    if function in TEXTURE_FUNCTIONS:
        groups.add("texture")
    if function in PAYOFF_FUNCTIONS:
        groups.add("payoff")
    if function in CONTEXT_FUNCTIONS:
        groups.add("context")
    if function in AFTERTASTE_FUNCTIONS:
        groups.add("aftertaste")
    if not groups:
        groups.add("observation")
    return groups


def tier_of(row: dict[str, Any] | None) -> str:
    return str((row or {}).get("editorialTier") or (row or {}).get("selectionTier") or "")


def approved_exception(row: dict[str, Any] | None) -> bool:
    decision = (row or {}).get("decision") if isinstance((row or {}).get("decision"), dict) else {}
    text = " ".join(str(value or "") for value in (decision.get("approvedUse"), decision.get("editorNotes"), decision.get("resolveImplementation"))).lower()
    return any(term in text for term in ("keep", "route honesty", "approved exception", "needed"))


def is_weak_clip(clip: dict[str, Any], row: dict[str, Any] | None) -> bool:
    text = clip_text(clip)
    signals = " ".join(str(item).lower() for item in ((row or {}).get("signals") or []))
    return any(term in text for term in WEAK_TERMS) or "weak_or_placeholder_signal" in signals


def run_length(values: list[str]) -> int:
    best = 0
    current = ""
    length = 0
    for value in values:
        if value == current:
            length += 1
        else:
            current = value
            length = 1
        best = max(best, length)
    return best


def clip_row(index: int, clip: dict[str, Any], match: dict[str, Any] | None) -> dict[str, Any]:
    function = normalize_function(clip, match)
    tier = tier_of(match)
    duration = clip_duration(clip)
    issues: list[str] = []
    if match is None:
        issues.append("missing_creator_cut_row_for_clip")
    if tier in REJECT_TIERS and not approved_exception(match):
        issues.append("rejected_clip_still_active_in_candidate")
    if is_weak_clip(clip, match) and tier not in {"hero", "main_story", "texture_bridge"} and not approved_exception(match):
        issues.append("weak_or_placeholder_clip_not_repaired_or_approved")
    if duration > 24.0 and function not in {"ending_aftertaste", "opening_hook"}:
        issues.append("active_clip_exceeds_long_hold_limit")
    return {
        "clipIndex": index,
        "status": "passed" if not issues else "blocked",
        "sourcePath": clip.get("sourcePath"),
        "sourceName": source_name(clip.get("sourcePath") or clip.get("sourceName")),
        "timelineStartSeconds": round3(timeline_start(clip)),
        "timelineEndSeconds": round3(timeline_end(clip)),
        "durationSeconds": round3(duration),
        "chapterIndex": clip.get("chapterIndex"),
        "role": clip.get("role"),
        "creatorFunction": function,
        "functionGroups": sorted(function_groups(function)),
        "editorialTier": tier,
        "creatorScore": (match or {}).get("creatorScore"),
        "matchedCreatorRowIndex": (match or {}).get("rowIndex"),
        "approvedException": approved_exception(match),
        "issues": issues,
    }


def chapter_rows(audited: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in audited:
        key = str(row.get("chapterIndex") if row.get("chapterIndex") is not None else "unassigned")
        grouped.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items(), key=lambda item: (9999 if item[0] == "unassigned" else int(float(item[0])), item[0])):
        groups = sorted({group for row in rows for group in row.get("functionGroups", [])})
        functions = sorted({str(row.get("creatorFunction") or "") for row in rows})
        tier_counts: dict[str, int] = {}
        for row in rows:
            tier = str(row.get("editorialTier") or "missing")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        issues: list[str] = []
        if len(rows) >= 3 and len(groups) < 3:
            issues.append("chapter_lacks_creator_function_variety")
        if len(rows) >= 3 and "movement" not in groups:
            issues.append("chapter_lacks_movement_or_route_bridge")
        if len(rows) >= 3 and not ({"texture", "payoff"} & set(groups)):
            issues.append("chapter_lacks_texture_or_payoff")
        if tier_counts.get("reject_or_replace", 0) or tier_counts.get("reject_or_review", 0):
            issues.append("chapter_contains_rejected_active_clip")
        utility_count = sum(tier_counts.get(tier, 0) for tier in UTILITY_TIERS)
        if len(rows) >= 4 and utility_count > math.ceil(len(rows) * 0.35):
            issues.append("chapter_overuses_utility_footage")
        return_status = "passed" if not issues else "blocked"
        out.append(
            {
                "chapterIndex": key,
                "status": return_status,
                "clipCount": len(rows),
                "creatorFunctions": functions,
                "functionGroups": groups,
                "tierCounts": tier_counts,
                "issues": issues,
            }
        )
    return out


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
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, args.blueprint)
    creator_plan_path = package_dir / "creator_cut_plan" / "creator_cut_plan.json"
    rhythm_plan_path = package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json"
    creator_plan = load_json(creator_plan_path) or {}
    rhythm_plan = load_json(rhythm_plan_path) or {}
    creator_summary = creator_plan.get("summary") if isinstance(creator_plan.get("summary"), dict) else {}
    rhythm_summary = rhythm_plan.get("summary") if isinstance(rhythm_plan.get("summary"), dict) else {}
    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "blueprint": str(blueprint_path),
                "blueprintExists": blueprint_path.exists(),
                "blueprintKind": blueprint_kind,
                "blueprintInsidePackage": blueprint_inside_package,
                "creatorCutPlan": str(creator_plan_path),
                "creatorCutPlanExists": creator_plan_path.exists(),
                "editRhythmPlan": str(rhythm_plan_path),
                "editRhythmPlanExists": rhythm_plan_path.exists(),
            },
            "summary": {},
            "clipRows": [],
            "chapterRows": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    clips = primary_visual_clips(blueprint)
    rows = creator_rows(creator_plan)
    lookup = creator_lookup(rows)
    audited = [clip_row(index, clip, match_creator_row(clip, lookup)) for index, clip in enumerate(clips, start=1)]
    chapters = chapter_rows(audited)
    blocked_clips = [row for row in audited if row.get("status") == "blocked"]
    blocked_chapters = [row for row in chapters if row.get("status") == "blocked"]
    source_sequence = [str(row.get("sourceName") or "") for row in audited]
    function_sequence = [str(row.get("creatorFunction") or "") for row in audited]
    same_source_run = run_length(source_sequence)
    same_function_run = run_length(function_sequence)
    durations = [float(row.get("durationSeconds") or 0.0) for row in audited if float(row.get("durationSeconds") or 0.0) > 0]
    unique_sources = len({item for item in source_sequence if item})
    blockers = [f"clip {row.get('clipIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_clips[:80]]
    blockers.extend(f"chapter {row.get('chapterIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_chapters[:80])
    warnings: list[str] = []
    if not blueprint_path.exists():
        blockers.append(f"blueprint path does not exist: {blueprint_path}")
    if not blueprint_inside_package:
        blockers.append(f"blueprint is outside package: {blueprint_path}")
    if not creator_plan_path.exists():
        blockers.append("creator_cut_plan.json is missing")
    if creator_plan.get("status") != "ready_with_creator_cut_plan":
        blockers.append(f"creator_cut_plan status is not ready: {creator_plan.get('status')}")
    if rhythm_plan_path.exists() and rhythm_plan.get("status") != "ready_with_edit_rhythm_plan":
        warnings.append(f"edit_rhythm_plan status is not ready: {rhythm_plan.get('status')}")
    if clips and not rows:
        blockers.append("creator cut plan has no shotRows/selectionRows")
    if clips and len(audited) != len(clips):
        blockers.append("not every primary visual clip was audited")
    if len(audited) >= 6 and same_source_run >= 4:
        blockers.append(f"same source repeats {same_source_run} times consecutively")
    if len(audited) >= 8 and same_function_run >= 5:
        blockers.append(f"same creator function repeats {same_function_run} times consecutively")
    utility_active = sum(1 for row in audited if row.get("editorialTier") in UTILITY_TIERS)
    if len(audited) >= 8 and utility_active > math.ceil(len(audited) * 0.25):
        blockers.append(f"too much utility footage remains active: {utility_active}/{len(audited)}")
    if len(audited) >= 6 and unique_sources < max(3, math.ceil(len(audited) * 0.35)):
        blockers.append(f"source diversity too low for creator-style edit: {unique_sources}/{len(audited)}")
    global_groups = sorted({group for row in audited for group in row.get("functionGroups", [])})
    if len(audited) >= 5 and len(global_groups) < 4:
        blockers.append(f"global creator-function variety too low: {len(global_groups)} groups")
    status = "passed" if not blockers and (not clips or rows) else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "creatorCutPlan": str(creator_plan_path),
            "creatorCutPlanExists": creator_plan_path.exists(),
            "editRhythmPlan": str(rhythm_plan_path),
            "editRhythmPlanExists": rhythm_plan_path.exists(),
            "creatorCutStatus": creator_plan.get("status"),
            "editRhythmStatus": rhythm_plan.get("status"),
        },
        "summary": {
            "visualClipCount": len(clips),
            "creatorPlanRowCount": len(rows),
            "matchedCreatorRowCount": sum(1 for row in audited if row.get("matchedCreatorRowIndex") is not None),
            "passedClipCount": sum(1 for row in audited if row.get("status") == "passed"),
            "blockedClipCount": len(blocked_clips),
            "chapterCount": len(chapters),
            "chaptersPassed": sum(1 for row in chapters if row.get("status") == "passed"),
            "chaptersBlocked": len(blocked_chapters),
            "uniqueSourceCount": unique_sources,
            "sameSourceRunMax": same_source_run,
            "sameFunctionRunMax": same_function_run,
            "utilityActiveClipCount": utility_active,
            "rejectActiveClipCount": sum(1 for row in audited if row.get("editorialTier") in REJECT_TIERS),
            "weakActiveClipCount": sum(1 for row in audited if "weak_or_placeholder_clip_not_repaired_or_approved" in (row.get("issues") or [])),
            "maxClipDurationSeconds": round3(max(durations, default=0.0)),
            "averageClipDurationSeconds": round3(sum(durations) / len(durations)) if durations else 0.0,
            "medianClipDurationSeconds": round3(statistics.median(durations)) if durations else 0.0,
            "globalFunctionGroups": global_groups,
            "globalFunctionGroupCount": len(global_groups),
            "creatorPlanRejectOrUtilityCount": creator_summary.get("rejectOrUtilityCount"),
            "creatorPlanChaptersNeedingCoverage": creator_summary.get("chaptersNeedingCreatorCoverage"),
            "editRhythmRiskCount": rhythm_summary.get("rhythmRiskCount"),
            "blockerCount": len(blockers),
        },
        "clipRows": audited,
        "chapterRows": chapters,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Creator Cut Application Contract Audit",
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
    lines.extend(["", "## Chapters"])
    for row in report.get("chapterRows") or []:
        lines.extend(
            [
                "",
                f"### Chapter {row.get('chapterIndex')}",
                f"- Status: `{row.get('status')}`",
                f"- Clips: {row.get('clipCount')}",
                f"- Function groups: `{', '.join(row.get('functionGroups') or [])}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    lines.extend(["", "## Blocked Clip Rows"])
    blocked = [row for row in report.get("clipRows") or [] if row.get("status") == "blocked"]
    if not blocked:
        lines.append("- None.")
    for row in blocked[:120]:
        lines.extend(
            [
                "",
                f"### Clip {row.get('clipIndex')}: {row.get('creatorFunction')} / {row.get('editorialTier')}",
                f"- Source: `{row.get('sourceName')}`",
                f"- Window: `{row.get('timelineStartSeconds')}` to `{row.get('timelineEndSeconds')}` ({row.get('durationSeconds')}s)",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit creator-cut application on the final candidate blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "creator_cut_application_contract_audit.json", report)
    write_markdown(package_dir / "creator_cut_application_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
