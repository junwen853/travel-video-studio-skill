#!/usr/bin/env python3
"""Audit that first assembly uses full-source footage selection, not filename order."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SAFE_TIERS = {"hero_candidate", "main_story_candidate", "texture_bridge_candidate", "utility_context"}
RISK_TIERS = {"repair_before_use", "reject_or_review", "reject_excluded"}


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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summary_of(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("summary") if isinstance(data.get("summary"), dict) else {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def top_selection_rows(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    chapters = delivery.get("chapters") if isinstance(delivery.get("chapters"), list) else []
    for chapter_index, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            continue
        selection = chapter.get("footageSelection") if isinstance(chapter.get("footageSelection"), dict) else {}
        for row in selection.get("topSelectionRows") or []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["chapterIndex"] = chapter.get("chapterIndex") or chapter_index
            rows.append(item)
    return rows


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    raw = load_json(package_dir / "raw_intake_completeness_audit.json") or {}
    select = load_json(package_dir / "footage_select_plan" / "footage_select_plan.json") or {}
    repair = load_json(package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json") or {}
    coverage = load_json(package_dir / "source_selection_coverage_contract_audit.json") or {}
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}

    raw_summary = summary_of(raw)
    select_summary = summary_of(select)
    repair_summary = summary_of(repair)
    coverage_summary = summary_of(coverage)
    delivery_selection = delivery.get("footageSelection") if isinstance(delivery.get("footageSelection"), dict) else {}
    blueprint_selection = blueprint.get("footageSelection") if isinstance(blueprint.get("footageSelection"), dict) else {}
    delivery_chapters = delivery.get("chapters") if isinstance(delivery.get("chapters"), list) else []
    top_rows = top_selection_rows(delivery)
    risky_top_rows = [row for row in top_rows if str(row.get("selectionTier") or "") in RISK_TIERS]
    missing_top_data = [
        row
        for row in top_rows
        if str(row.get("selectionTier") or "") not in SAFE_TIERS or row.get("selectionScore") is None
    ]

    active_source_count = as_int(raw_summary.get("activeSourceVideoCount"))
    select_source_count = as_int(select_summary.get("sourceVideoCount"))
    source_size_gb = as_float(raw_summary.get("sourceSizeGB"))
    large_source = bool(raw_summary.get("largeSource")) or active_source_count >= args.large_source_video_count or source_size_gb >= args.large_source_gb
    delivery_sorted = as_int(delivery_selection.get("sortedChapterCount"))
    blueprint_sorted = as_int(blueprint_selection.get("sortedChapterCount"))
    sorted_count = max(delivery_sorted, blueprint_sorted)
    chapter_count = len(delivery_chapters)
    candidate_count = as_int(select_summary.get("candidateVideoCount"))
    candidate_rows_used = max(as_int(delivery_selection.get("candidateRowsUsed")), as_int(blueprint_selection.get("candidateRowsUsed")))

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required first-assembly source reports exist and are accepted",
        raw.get("status") == "passed"
        and select.get("status") in {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"}
        and repair.get("status") == "ready_no_source_selection_repairs_needed"
        and coverage.get("status") == "passed"
        and bool(delivery)
        and bool(blueprint),
        {
            "rawIntakeStatus": raw.get("status"),
            "footageSelectStatus": select.get("status"),
            "sourceSelectionRepairStatus": repair.get("status"),
            "sourceSelectionCoverageStatus": coverage.get("status"),
            "deliveryPlanExists": bool(delivery),
            "resolveBlueprintExists": bool(blueprint),
        },
    )
    add_check(
        checks,
        "Large or unordered source pools are selected from the media index, not blueprint fallback or samples",
        active_source_count > 0
        and select_source_count >= active_source_count
        and as_int(raw_summary.get("footageSelectMissingVideoCount")) == 0
        and (not large_source or select_summary.get("inputSource") == "media_index")
        and as_int(raw_summary.get("activeDerivedVideoCount")) == 0
        and as_int(raw_summary.get("staleArtifactCount")) == 0,
        {
            "activeSourceVideoCount": active_source_count,
            "footageSelectSourceVideoCount": select_source_count,
            "footageSelectMissingVideoCount": raw_summary.get("footageSelectMissingVideoCount"),
            "sourceSizeGB": raw_summary.get("sourceSizeGB"),
            "largeSource": large_source,
            "footageSelectInputSource": select_summary.get("inputSource"),
            "activeDerivedVideoCount": raw_summary.get("activeDerivedVideoCount"),
            "staleArtifactCount": raw_summary.get("staleArtifactCount"),
        },
    )
    add_check(
        checks,
        "First assembly records that footage selection sorted every delivery chapter",
        chapter_count >= 1
        and delivery_selection.get("status") == "used_for_first_assembly_sort"
        and delivery_selection.get("usedForSorting") is True
        and blueprint_selection.get("status") == "used_for_first_assembly_sort"
        and blueprint_selection.get("usedForSorting") is True
        and sorted_count >= chapter_count,
        {
            "deliveryChapterCount": chapter_count,
            "deliveryFootageSelection": delivery_selection,
            "blueprintFootageSelection": blueprint_selection,
            "sortedChapterCount": sorted_count,
        },
    )
    add_check(
        checks,
        "First assembly uses scored hero/main/texture candidates instead of filename order",
        candidate_count >= args.min_candidate_rows
        and candidate_rows_used >= min(candidate_count, max(args.min_candidate_rows, chapter_count))
        and bool(top_rows)
        and not missing_top_data,
        {
            "candidateVideoCount": candidate_count,
            "candidateRowsUsed": candidate_rows_used,
            "topSelectionRowCount": len(top_rows),
            "missingTopSelectionDataCount": len(missing_top_data),
            "sampleMissingTopSelectionData": missing_top_data[:10],
            "minCandidateRows": args.min_candidate_rows,
        },
    )
    add_check(
        checks,
        "Repair, reject, derived, and risky orientation rows do not lead the first assembly",
        as_int(repair_summary.get("blockingRepairRowCount")) == 0
        and as_int(coverage_summary.get("blockedCheckCount")) == 0
        and as_int(select_summary.get("repairOrRejectCount")) >= 0
        and not risky_top_rows,
        {
            "blockingRepairRowCount": repair_summary.get("blockingRepairRowCount"),
            "coverageBlockedCheckCount": coverage_summary.get("blockedCheckCount"),
            "repairOrRejectCount": select_summary.get("repairOrRejectCount"),
            "orientationRepairCandidateCount": select_summary.get("orientationRepairCandidateCount"),
            "riskyTopSelectionRowCount": len(risky_top_rows),
            "riskyTopSelectionRows": risky_top_rows[:10],
        },
    )
    add_check(
        checks,
        "Chapter pools have local movement, texture, and payoff coverage before effects or stock fallback",
        as_int(coverage_summary.get("chapterRowCount")) >= 1
        and as_int(coverage_summary.get("readyChapterCount")) == as_int(coverage_summary.get("chapterRowCount"))
        and as_int(coverage_summary.get("heroCandidateCount")) >= 1
        and as_int(coverage_summary.get("movementBridgeCandidateCount")) >= max(1, as_int(coverage_summary.get("chapterRowCount")) - 1)
        and as_int(coverage_summary.get("livedInTextureCandidateCount")) >= 1
        and as_int(coverage_summary.get("destinationPayoffCandidateCount")) >= 1,
        {
            "chapterRowCount": coverage_summary.get("chapterRowCount"),
            "readyChapterCount": coverage_summary.get("readyChapterCount"),
            "heroCandidateCount": coverage_summary.get("heroCandidateCount"),
            "movementBridgeCandidateCount": coverage_summary.get("movementBridgeCandidateCount"),
            "livedInTextureCandidateCount": coverage_summary.get("livedInTextureCandidateCount"),
            "destinationPayoffCandidateCount": coverage_summary.get("destinationPayoffCandidateCount"),
        },
    )

    blockers = [row for row in checks if row["status"] == "blocked"]
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "largeSourceVideoCount": args.large_source_video_count,
            "largeSourceGB": args.large_source_gb,
            "minCandidateRows": args.min_candidate_rows,
        },
        "summary": {
            "activeSourceVideoCount": active_source_count,
            "sourceSizeGB": raw_summary.get("sourceSizeGB"),
            "largeSource": large_source,
            "footageSelectInputSource": select_summary.get("inputSource"),
            "footageSelectSourceVideoCount": select_source_count,
            "candidateVideoCount": candidate_count,
            "candidateRowsUsed": candidate_rows_used,
            "deliveryChapterCount": chapter_count,
            "sortedChapterCount": sorted_count,
            "droppedFromFirstChoice": max(as_int(delivery_selection.get("droppedFromFirstChoice")), as_int(blueprint_selection.get("droppedFromFirstChoice"))),
            "topSelectionRowCount": len(top_rows),
            "riskyTopSelectionRowCount": len(risky_top_rows),
            "missingTopSelectionDataCount": len(missing_top_data),
            "repairOrRejectCount": select_summary.get("repairOrRejectCount"),
            "orientationRepairCandidateCount": select_summary.get("orientationRepairCandidateCount"),
            "checkCount": len(checks),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": len(blockers),
        },
        "checks": checks,
        "blockers": [row["name"] for row in blockers],
        "warnings": [],
        "policy": {
            "fullMediaIndexRequiredForLargeSources": True,
            "firstAssemblyMustUseFootageSelection": True,
            "filenameOrderRejected": True,
            "repairRejectDerivedRowsCannotLeadAssembly": True,
            "localCoverageBeforeEffectsOrStock": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# First Assembly Source Order Contract Audit",
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
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(
            [
                "",
                f"### {row.get('name')}",
                f"- Status: `{row.get('status')}`",
                f"- Evidence: `{json.dumps(row.get('evidence'), ensure_ascii=False)[:1800]}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Contract",
            "- Reject first assemblies that cut large unordered folders by filename order or blueprint fallback sampling.",
            "- Require footage select plan, raw intake completeness, source-selection repair, and source-selection coverage evidence before trusting the cut.",
            "- Require delivery and Resolve blueprints to record `used_for_first_assembly_sort` and safe top selection rows.",
            "- Prevent repair, reject, derived, portrait/square/unknown, or weak rows from leading the first assembly.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit that first assembly uses full-source footage selection.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--large-source-video-count", type=int, default=60)
    parser.add_argument("--large-source-gb", type=float, default=100.0)
    parser.add_argument("--min-candidate-rows", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "first_assembly_source_order_contract_audit.json", report)
    write_markdown(package_dir / "first_assembly_source_order_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
