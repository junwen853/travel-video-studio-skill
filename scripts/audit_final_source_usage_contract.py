#!/usr/bin/env python3
"""Audit whether the final blueprint really uses the footage selection plan."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


SELECTED_TIERS = {"hero_candidate", "main_story_candidate", "texture_bridge_candidate"}
UTILITY_TIERS = {"utility_context", "utility_only"}
REPAIR_TIERS = {"repair_before_use", "orientation_repair_review"}
REJECT_TIERS = {"reject_or_review", "reject_excluded", "reject_or_replace", "reject_or_manual_review"}
MOVEMENT_OR_TEXTURE = {"route_movement_bridge", "lived_in_texture"}
GENERATED_TERMS = (
    "title",
    "chapter_card",
    "opening_city",
    "ending_city",
    "subtitle_overlay",
    "caption",
    "srt",
    "ass",
    "vtt",
    "overlay",
    "typography",
    "map",
    "route_card",
    "generated",
    "asset",
    "stock",
    "aerial",
    "scenic_title",
    "title_bridge",
    "generated_bridge",
    "materialized_bridge",
    "clean_scenic_title_bridges",
    "v8_visual_polish",
    "v9_fix_inputs",
    "bgm",
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


def path_from_package(package_dir: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path


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


def key_variants(value: Any) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    values = {text, source_name(text)}
    try:
        path = Path(text).expanduser()
        values.add(str(path))
        values.add(path.name)
    except Exception:
        pass
    return {item.lower() for item in values if item}


def selection_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("selectionRows") if isinstance(plan.get("selectionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def selection_lookup(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        keys = set()
        keys.update(key_variants(row.get("sourcePath")))
        keys.update(key_variants(row.get("sourceName")))
        keys.update(key_variants(row.get("fileId")))
        for key in keys:
            lookup.setdefault(key, []).append(row)
    return lookup


def match_selection_row(clip: dict[str, Any], lookup: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    keys: set[str] = set()
    keys.update(key_variants(clip.get("sourcePath")))
    keys.update(key_variants(clip.get("sourceName")))
    keys.update(key_variants(clip.get("name")))
    for key in keys:
        rows = lookup.get(key)
        if rows:
            return rows[0]
    return None


def approved_exception(row: dict[str, Any] | None) -> bool:
    decision = (row or {}).get("decision") if isinstance((row or {}).get("decision"), dict) else {}
    text = " ".join(
        str(value or "")
        for value in (
            decision.get("approvedUse"),
            decision.get("approvedChapterPool"),
            decision.get("editorNotes"),
            decision.get("resolveImplementation"),
            decision.get("readbackEvidence"),
        )
    ).lower()
    return any(term in text for term in ("keep", "approved", "exception", "route honesty", "needed", "repaired", "phone insert"))


def generated_asset_clip(package_dir: Path, clip: dict[str, Any], match: dict[str, Any] | None) -> bool:
    if match is not None:
        return False
    text = clip_text(clip)
    if not str(clip.get("sourcePath") or clip.get("sourceName") or clip.get("name") or "").strip():
        return any(term in text for term in GENERATED_TERMS)
    path = path_from_package(package_dir, clip.get("sourcePath") or clip.get("sourceName") or clip.get("name"))
    if not path:
        return False
    path_text = str(path).lower()
    if str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt", ".txt", ".json")):
        return True
    return is_inside(path, package_dir) and any(term in f"{text} {path_text}" for term in GENERATED_TERMS)


def plan_chapter_index(plan: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = plan.get("chapterRows") if isinstance(plan.get("chapterRows"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = as_int(row.get("chapterIndex"), 0)
        if index > 0:
            out[index] = row
    return out


def infer_chapter_index(clip: dict[str, Any]) -> int | None:
    raw = clip.get("chapterIndex")
    if raw is None:
        raw = clip.get("chapter")
    value = as_int(raw, -1)
    return value if value >= 0 else None


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


def clip_row(index: int, package_dir: Path, clip: dict[str, Any], match: dict[str, Any] | None) -> dict[str, Any]:
    tier = str((match or {}).get("selectionTier") or "")
    function = str((match or {}).get("creatorFunction") or "")
    status = str((match or {}).get("status") or "")
    duration = clip_duration(clip)
    exempt_generated = generated_asset_clip(package_dir, clip, match)
    issues: list[str] = []
    if match is None and not exempt_generated:
        issues.append("raw_source_missing_from_footage_select_plan")
    if match is not None and tier in REJECT_TIERS and not approved_exception(match):
        issues.append("rejected_source_still_active_in_final_blueprint")
    if match is not None and (tier in REPAIR_TIERS or status == "needs_editor_or_repair_decision") and not approved_exception(match):
        issues.append("repair_required_source_used_without_approved_repair_or_design_exception")
    if match is not None and status == "excluded_from_first_cut" and not approved_exception(match):
        issues.append("excluded_source_used_in_final_blueprint")
    return {
        "clipIndex": index,
        "status": "exempt_generated_asset" if exempt_generated else ("passed" if not issues else "blocked"),
        "sourcePath": clip.get("sourcePath"),
        "sourceName": source_name(clip.get("sourcePath") or clip.get("sourceName") or clip.get("name")),
        "timelineStartSeconds": round3(timeline_start(clip)),
        "timelineEndSeconds": round3(timeline_end(clip)),
        "durationSeconds": round3(duration),
        "chapterIndex": infer_chapter_index(clip),
        "role": clip.get("role"),
        "purpose": clip.get("purpose"),
        "matchedSelectionRowIndex": (match or {}).get("rowIndex"),
        "selectionTier": tier,
        "creatorFunction": function,
        "selectionScore": (match or {}).get("selectionScore"),
        "selectionStatus": status,
        "selectedCandidate": tier in SELECTED_TIERS,
        "utilityContext": tier in UTILITY_TIERS,
        "approvedException": approved_exception(match),
        "generatedAssetExempt": exempt_generated,
        "issues": issues,
    }


def chapter_rows(audited: list[dict[str, Any]], plan_chapters: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in audited:
        if row.get("generatedAssetExempt"):
            continue
        key = str(row.get("chapterIndex") if row.get("chapterIndex") is not None else "unassigned")
        grouped.setdefault(key, []).append(row)
    out: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items(), key=lambda item: (9999 if item[0] == "unassigned" else int(float(item[0])), item[0])):
        issues: list[str] = []
        plan_row = plan_chapters.get(as_int(key, -1)) if key != "unassigned" else None
        candidate_count = as_int((plan_row or {}).get("candidateVideoCount"), 0)
        function_counts = (plan_row or {}).get("functionCounts") if isinstance((plan_row or {}).get("functionCounts"), dict) else {}
        tiers = [str(row.get("selectionTier") or "") for row in rows]
        functions = [str(row.get("creatorFunction") or "") for row in rows]
        if rows and str(rows[0].get("selectionTier") or "") in UTILITY_TIERS:
            issues.append("chapter_leads_with_utility_source")
        if candidate_count > 0 and not any(row.get("selectedCandidate") for row in rows):
            issues.append("chapter_has_selectable_pool_but_no_hero_main_or_texture_source")
        has_pool_movement = any(as_int(function_counts.get(fn), 0) > 0 for fn in MOVEMENT_OR_TEXTURE)
        if has_pool_movement and len(rows) >= 2 and not any(fn in MOVEMENT_OR_TEXTURE for fn in functions):
            issues.append("chapter_skips_available_route_movement_or_lived_texture_source")
        if len(rows) >= 4 and sum(1 for tier in tiers if tier in UTILITY_TIERS) > math.ceil(len(rows) * 0.35):
            issues.append("chapter_overuses_utility_sources")
        out.append(
            {
                "chapterIndex": key,
                "status": "passed" if not issues else "blocked",
                "clipCount": len(rows),
                "planChapterKey": (plan_row or {}).get("chapterKey"),
                "planCandidateVideoCount": candidate_count,
                "selectedCandidateClipCount": sum(1 for row in rows if row.get("selectedCandidate")),
                "utilityClipCount": sum(1 for tier in tiers if tier in UTILITY_TIERS),
                "selectionTiers": sorted({tier for tier in tiers if tier}),
                "creatorFunctions": sorted({fn for fn in functions if fn}),
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
    plan_path = Path(args.footage_select_plan).expanduser().resolve() if args.footage_select_plan else package_dir / "footage_select_plan" / "footage_select_plan.json"
    plan = load_json(plan_path) or {}
    plan_summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    rows = selection_rows(plan)
    lookup = selection_lookup(rows)
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
                "footageSelectPlan": str(plan_path),
                "footageSelectPlanExists": plan_path.exists(),
                "footageSelectStatus": plan.get("status"),
            },
            "summary": {},
            "clipRows": [],
            "chapterRows": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    clips = primary_visual_clips(blueprint)
    audited = [clip_row(index, package_dir, clip, match_selection_row(clip, lookup)) for index, clip in enumerate(clips, start=1)]
    raw_rows = [row for row in audited if not row.get("generatedAssetExempt")]
    matched_rows = [row for row in raw_rows if row.get("matchedSelectionRowIndex") is not None]
    selected_rows = [row for row in raw_rows if row.get("selectedCandidate")]
    utility_rows = [row for row in raw_rows if row.get("utilityContext")]
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    chapters = chapter_rows(audited, plan_chapter_index(plan))
    blocked_chapters = [row for row in chapters if row.get("status") == "blocked"]
    raw_sources = [str(row.get("sourceName") or "") for row in raw_rows]
    durations = [float(row.get("durationSeconds") or 0.0) for row in raw_rows if float(row.get("durationSeconds") or 0.0) > 0]
    utility_duration = sum(float(row.get("durationSeconds") or 0.0) for row in utility_rows)
    total_duration = sum(durations)
    same_source_run = run_length(raw_sources)
    unique_sources = len({item for item in raw_sources if item})
    blockers = [f"clip {row.get('clipIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[:80]]
    blockers.extend(f"chapter {row.get('chapterIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_chapters[:80])
    warnings: list[str] = []
    accepted_plan_statuses = {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"}
    if not blueprint_path.exists():
        blockers.append(f"blueprint path does not exist: {blueprint_path}")
    if not blueprint_inside_package:
        blockers.append(f"blueprint is outside package: {blueprint_path}")
    if not plan_path.exists():
        blockers.append("footage_select_plan.json is missing")
    if plan.get("status") not in accepted_plan_statuses:
        blockers.append(f"footage_select_plan status is not ready: {plan.get('status')}")
    if clips and not rows:
        blockers.append("footage_select_plan has no selectionRows")
    if raw_rows and len(matched_rows) != len(raw_rows):
        blockers.append(f"not every final raw source matched the footage select plan: {len(matched_rows)}/{len(raw_rows)}")
    if len(raw_rows) >= 3 and not selected_rows:
        blockers.append("final raw source set has no hero/main/texture selected candidate")
    if len(raw_rows) >= 3 and len(selected_rows) < max(1, math.ceil(len(raw_rows) * 0.4)):
        blockers.append(f"selected hero/main/texture usage too low: {len(selected_rows)}/{len(raw_rows)}")
    if len(raw_rows) >= 6 and same_source_run > args.max_same_source_run:
        blockers.append(f"same raw source repeats {same_source_run} times consecutively")
    if len(raw_rows) >= 8 and unique_sources < max(3, math.ceil(len(raw_rows) * 0.35)):
        blockers.append(f"source diversity too low for final creator-style edit: {unique_sources}/{len(raw_rows)}")
    if len(raw_rows) >= 8 and len(utility_rows) > math.ceil(len(raw_rows) * args.max_utility_ratio):
        blockers.append(f"too much utility footage remains active: {len(utility_rows)}/{len(raw_rows)}")
    if total_duration > 0 and utility_duration / total_duration > args.max_utility_ratio:
        blockers.append(f"utility footage duration ratio too high: {utility_duration / total_duration:.3f}")
    if not raw_rows and clips:
        warnings.append("no final raw source clips were detected; only generated/exempt visual assets were present")
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
            "footageSelectPlan": str(plan_path),
            "footageSelectPlanExists": plan_path.exists(),
            "footageSelectStatus": plan.get("status"),
            "footageSelectInputSource": plan_summary.get("inputSource"),
            "maxUtilityRatio": args.max_utility_ratio,
            "maxSameSourceRun": args.max_same_source_run,
        },
        "summary": {
            "visualClipCount": len(clips),
            "rawSourceClipCount": len(raw_rows),
            "generatedAssetExemptClipCount": sum(1 for row in audited if row.get("generatedAssetExempt")),
            "footageSelectRowCount": len(rows),
            "matchedRawSourceClipCount": len(matched_rows),
            "unmatchedRawSourceClipCount": len(raw_rows) - len(matched_rows),
            "selectedCandidateClipCount": len(selected_rows),
            "utilityClipCount": len(utility_rows),
            "rejectOrRepairActiveClipCount": sum(1 for row in raw_rows if row.get("selectionTier") in (REJECT_TIERS | REPAIR_TIERS)),
            "uniqueSourceCount": unique_sources,
            "sameSourceRunMax": same_source_run,
            "utilityDurationRatio": round3(utility_duration / total_duration) if total_duration > 0 else 0.0,
            "chapterCount": len(chapters),
            "chaptersBlocked": len(blocked_chapters),
            "averageRawClipDurationSeconds": round3(sum(durations) / len(durations)) if durations else 0.0,
            "medianRawClipDurationSeconds": round3(statistics.median(durations)) if durations else 0.0,
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
        "# Final Source Usage Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report['inputs'].get('blueprint')}`",
        f"Blueprint kind: `{report['inputs'].get('blueprintKind')}`",
        f"Footage select plan: `{report['inputs'].get('footageSelectPlan')}`",
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
                f"- Selected candidates: {row.get('selectedCandidateClipCount')}",
                f"- Utility clips: {row.get('utilityClipCount')}",
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
                f"### Clip {row.get('clipIndex')}: {row.get('selectionTier')} / {row.get('creatorFunction')}",
                f"- Source: `{row.get('sourceName')}`",
                f"- Window: `{row.get('timelineStartSeconds')}` to `{row.get('timelineEndSeconds')}` ({row.get('durationSeconds')}s)",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final raw source usage against the footage selection plan.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--footage-select-plan")
    parser.add_argument("--max-utility-ratio", type=float, default=0.25)
    parser.add_argument("--max-same-source-run", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "final_source_usage_contract_audit.json", report)
    write_markdown(package_dir / "final_source_usage_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
