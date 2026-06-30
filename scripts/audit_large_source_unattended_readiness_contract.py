#!/usr/bin/env python3
"""Audit whether a large unordered source folder can run unattended to first draft."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


READY_RECOGNITION_STATUSES = {"ready", "ready_with_warnings", "ready_with_caveats", "passed", "passed_with_caveats"}
READY_LOCATION_STATUSES = {"passed", "passed_with_caveats", "passed_with_warnings"}
READY_UNATTENDED_STATUSES = {"passed", "passed_with_warnings"}
READY_PREFLIGHT_STATUSES = {"ready", "ready_with_warnings", "passed", "passed_with_warnings"}


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


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


def infer_project_dir(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for rel in (
        "raw_intake_completeness_audit.json",
        "workflow_run_report.json",
        "delivery_plan.json",
        "client_delivery_rules_audit.json",
        "location_truth_contract_audit.json",
    ):
        data = load_json(package_dir / rel)
        if isinstance(data, dict) and data.get("projectDir"):
            return Path(str(data["projectDir"])).expanduser().resolve()
    parts = package_dir.resolve().parts
    if "delivery_packages" in parts:
        return Path(*parts[: parts.index("delivery_packages")])
    return None


def latest_recognition(project_dir: Path | None, raw: dict[str, Any]) -> tuple[Path | None, dict[str, Any]]:
    inputs = raw.get("inputs") if isinstance(raw.get("inputs"), dict) else {}
    raw_path = inputs.get("recognitionReport")
    if raw_path:
        path = Path(str(raw_path)).expanduser()
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    if project_dir:
        pointer = load_json(project_dir / "latest_footage_recognition_route_report.json") or {}
        report_path = pointer.get("report") or pointer.get("path") or pointer.get("json")
        if report_path:
            path = Path(str(report_path)).expanduser()
            data = load_json(path)
            if isinstance(data, dict):
                return path, data
        candidates = sorted(
            project_dir.glob("recognition_reports/*/footage_recognition_route_report.json"),
            key=lambda item: item.stat().st_mtime if item.exists() else 0,
        )
        if candidates:
            return candidates[-1], load_json(candidates[-1]) or {}
    return None, {}


def external_intake(package_dir: Path, project_dir: Path | None, raw: dict[str, Any], explicit: str | None) -> tuple[Path | None, dict[str, Any]]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    inputs = raw.get("inputs") if isinstance(raw.get("inputs"), dict) else {}
    if inputs.get("externalMediaIntake"):
        candidates.append(Path(str(inputs["externalMediaIntake"])).expanduser())
    for root in [package_dir, project_dir, project_dir.parent if project_dir else None, project_dir.parent.parent if project_dir else None]:
        if root and root.exists():
            candidates.extend(root.glob("external_media_intake/*/external_media_intake.json"))
            candidates.extend(root.glob("external_media_intake.json"))
    candidates = sorted(set(candidates), key=lambda item: item.stat().st_mtime if item.exists() else 0)
    for path in reversed(candidates):
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    return None, {}


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any], *, required: bool = True) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else ("blocked" if required else "warning"),
            "required": required,
            "evidence": evidence,
        }
    )


def intake_ready(data: dict[str, Any], *, large_source: bool, require_external_intake: bool) -> bool:
    if not large_source and not require_external_intake:
        return True
    if not data:
        return False
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    ready_choices = [row for row in choices if isinstance(row, dict) and row.get("status") == "ready_for_project_workflow"]
    return data.get("status") in {"ready_for_project_choice", "passed", "ready"} and bool(ready_choices)


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    raw = load_json(package_dir / "raw_intake_completeness_audit.json") or {}
    raw_summary = summary_of(raw)
    project_dir = infer_project_dir(package_dir, args.project_dir)
    intake_path, intake = external_intake(package_dir, project_dir, raw, args.external_media_intake)
    recognition_path, recognition = latest_recognition(project_dir, raw)
    recognition_summary = summary_of(recognition)
    location = load_json(package_dir / "location_truth_contract_audit.json") or {}
    location_summary = summary_of(location)
    footage = load_json(package_dir / "footage_select_plan" / "footage_select_plan.json") or {}
    footage_summary = summary_of(footage)
    repair = load_json(package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json") or {}
    repair_summary = summary_of(repair)
    coverage = load_json(package_dir / "source_selection_coverage_contract_audit.json") or {}
    coverage_summary = summary_of(coverage)
    first_assembly = load_json(package_dir / "first_assembly_source_order_contract_audit.json") or {}
    first_summary = summary_of(first_assembly)
    unattended = load_json(package_dir / "unattended_first_draft_contract_audit.json") or {}
    unattended_summary = summary_of(unattended)
    preflight = load_json(package_dir / "resolve_blueprint_preflight.json") or {}
    delivery = load_json(package_dir / "delivery_audit.json") or {}
    workflow = load_json(package_dir / "workflow_run_report.json") or {}

    active_source_count = as_int(raw_summary.get("activeSourceVideoCount"))
    source_size_gb = as_float(raw_summary.get("sourceSizeGB"))
    large_source = bool(raw_summary.get("largeSource")) or active_source_count >= args.large_source_video_count or source_size_gb >= args.large_source_gb
    recognized_count = max(as_int(recognition_summary.get("recognizedVideoCount")), as_int(location_summary.get("recognizedVideoCount")))
    recognition_coverage = max(as_float(raw_summary.get("recognitionCoverageRatio")), as_float(recognition_summary.get("recognitionCoverageRatio")), as_float(location_summary.get("recognitionCoverageRatio")))
    expected_active_count = max(active_source_count, as_int(location_summary.get("expectedActiveSourceCount")), as_int(recognition_summary.get("mediaVideoCount")))

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Large source identity and media index are accounted",
        raw.get("status") == "passed"
        and expected_active_count > 0
        and as_int(raw_summary.get("indexedVideoCount")) >= expected_active_count
        and as_int(raw_summary.get("mediaRootCount")) >= 1
        and as_int(raw_summary.get("staleArtifactCount")) == 0,
        {
            "rawIntakeStatus": raw.get("status"),
            "projectDir": str(project_dir) if project_dir else None,
            "activeSourceVideoCount": active_source_count,
            "expectedActiveSourceCount": expected_active_count,
            "indexedVideoCount": raw_summary.get("indexedVideoCount"),
            "sourceSizeGB": raw_summary.get("sourceSizeGB"),
            "largeSource": large_source,
            "mediaRootCount": raw_summary.get("mediaRootCount"),
            "staleArtifactCount": raw_summary.get("staleArtifactCount"),
        },
    )
    add_check(
        checks,
        "External media intake prevents silent wrong-trip selection for large mounted sources",
        intake_ready(intake, large_source=large_source, require_external_intake=args.require_external_intake),
        {
            "required": bool(large_source or args.require_external_intake),
            "intakePath": str(intake_path) if intake_path else None,
            "status": intake.get("status"),
            "choiceCount": len(intake.get("choices") or []) if isinstance(intake.get("choices"), list) else 0,
            "readyChoiceCount": sum(1 for row in (intake.get("choices") or []) if isinstance(row, dict) and row.get("status") == "ready_for_project_workflow"),
            "largeSource": large_source,
        },
        required=bool(large_source or args.require_external_intake),
    )
    add_check(
        checks,
        "Whole selected folder is recognized and route-accounted before cutting",
        recognition.get("status") in READY_RECOGNITION_STATUSES
        and recognition_coverage >= 1.0
        and recognized_count >= expected_active_count > 0
        and as_int(raw_summary.get("routeMissingVideoCount")) == 0
        and as_int(raw_summary.get("routeDuplicateVideoCount")) == 0,
        {
            "recognitionReport": str(recognition_path) if recognition_path else None,
            "recognitionStatus": recognition.get("status"),
            "recognizedVideoCount": recognized_count,
            "expectedActiveSourceCount": expected_active_count,
            "recognitionCoverageRatio": recognition_coverage,
            "routeMissingVideoCount": raw_summary.get("routeMissingVideoCount"),
            "routeDuplicateVideoCount": raw_summary.get("routeDuplicateVideoCount"),
        },
    )
    add_check(
        checks,
        "Location truth gate allows route-aware editing without overclaiming exact GPS truth",
        location.get("status") in READY_LOCATION_STATUSES
        and location_summary.get("routeAwareEditClaimAllowed") is True
        and location_summary.get("claimLevel") in {"visual_route_reconstruction", "verified_per_clip_location"},
        {
            "status": location.get("status"),
            "claimLevel": location_summary.get("claimLevel"),
            "routeAwareEditClaimAllowed": location_summary.get("routeAwareEditClaimAllowed"),
            "exactPerVideoLocationClaimAllowed": location_summary.get("exactPerVideoLocationClaimAllowed"),
            "caveats": location.get("caveats") or [],
        },
    )
    add_check(
        checks,
        "Footage selection covers the full source pool from media index with enough usable candidates",
        footage.get("status") in {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"}
        and as_int(footage_summary.get("sourceVideoCount")) >= expected_active_count
        and as_int(footage_summary.get("candidateVideoCount")) >= max(args.min_candidate_rows, min(3, expected_active_count))
        and as_int(raw_summary.get("footageSelectMissingVideoCount")) == 0
        and (not large_source or footage_summary.get("inputSource") == "media_index")
        and as_int(raw_summary.get("activeDerivedVideoCount")) == 0,
        {
            "status": footage.get("status"),
            "inputSource": footage_summary.get("inputSource"),
            "sourceVideoCount": footage_summary.get("sourceVideoCount"),
            "candidateVideoCount": footage_summary.get("candidateVideoCount"),
            "heroCandidateCount": footage_summary.get("heroCandidateCount"),
            "textureBridgeCandidateCount": footage_summary.get("textureBridgeCandidateCount"),
            "footageSelectMissingVideoCount": raw_summary.get("footageSelectMissingVideoCount"),
            "activeDerivedVideoCount": raw_summary.get("activeDerivedVideoCount"),
        },
    )
    add_check(
        checks,
        "Source repair and chapter coverage close before effects, stock, or rhythm recut compensate",
        repair.get("status") == "ready_no_source_selection_repairs_needed"
        and coverage.get("status") == "passed"
        and as_int(repair_summary.get("blockingRepairRowCount")) == 0
        and as_int(coverage_summary.get("blockedCheckCount")) == 0
        and as_int(coverage_summary.get("chapterRowCount")) >= 1
        and as_int(coverage_summary.get("readyChapterCount")) == as_int(coverage_summary.get("chapterRowCount"))
        and as_int(coverage_summary.get("heroCandidateCount")) >= 1
        and as_int(coverage_summary.get("movementBridgeCandidateCount")) >= max(1, as_int(coverage_summary.get("chapterRowCount")) - 1)
        and as_int(coverage_summary.get("livedInTextureCandidateCount")) >= 1
        and as_int(coverage_summary.get("destinationPayoffCandidateCount")) >= 1,
        {
            "repairStatus": repair.get("status"),
            "coverageStatus": coverage.get("status"),
            "repairSummary": repair_summary,
            "coverageSummary": coverage_summary,
        },
    )
    add_check(
        checks,
        "First assembly proves it used scored source selection instead of filename order",
        first_assembly.get("status") == "passed"
        and first_summary.get("largeSource") == large_source
        and as_int(first_summary.get("sortedChapterCount")) >= as_int(first_summary.get("deliveryChapterCount"))
        and as_int(first_summary.get("candidateRowsUsed")) >= min(as_int(first_summary.get("candidateVideoCount")), max(args.min_candidate_rows, as_int(first_summary.get("deliveryChapterCount"))))
        and as_int(first_summary.get("riskyTopSelectionRowCount")) == 0
        and as_int(first_summary.get("missingTopSelectionDataCount")) == 0,
        {
            "status": first_assembly.get("status"),
            "summary": first_summary,
            "blockers": first_assembly.get("blockers") or [],
        },
    )
    add_check(
        checks,
        "Unattended first-draft and blueprint preflight are connected before Resolve write",
        unattended.get("status") in READY_UNATTENDED_STATUSES
        and as_int(unattended_summary.get("blockedGateCount")) == 0
        and (not preflight or preflight.get("status") in READY_PREFLIGHT_STATUSES),
        {
            "unattendedStatus": unattended.get("status"),
            "unattendedSummary": unattended_summary,
            "preflightStatus": preflight.get("status"),
            "deliveryAuditStatus": delivery.get("status"),
            "workflowStatus": workflow.get("status"),
        },
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings = [row["name"] for row in checks if row["status"] == "warning"]
    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "projectDir": str(project_dir) if project_dir else None,
        "inputs": {
            "largeSourceVideoCount": args.large_source_video_count,
            "largeSourceGB": args.large_source_gb,
            "minCandidateRows": args.min_candidate_rows,
            "requireExternalIntake": args.require_external_intake,
            "externalMediaIntake": str(intake_path) if intake_path else None,
            "recognitionReport": str(recognition_path) if recognition_path else None,
        },
        "summary": {
            "largeSource": large_source,
            "activeSourceVideoCount": active_source_count,
            "expectedActiveSourceCount": expected_active_count,
            "sourceSizeGB": source_size_gb,
            "indexedVideoCount": raw_summary.get("indexedVideoCount"),
            "recognitionCoverageRatio": recognition_coverage,
            "recognizedVideoCount": recognized_count,
            "footageSelectInputSource": footage_summary.get("inputSource"),
            "candidateVideoCount": footage_summary.get("candidateVideoCount"),
            "chapterRowCount": coverage_summary.get("chapterRowCount"),
            "firstAssemblyStatus": first_assembly.get("status"),
            "unattendedFirstDraftStatus": unattended.get("status"),
            "checkCount": len(checks),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": len(blockers),
            "warningCheckCount": len(warnings),
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "largeSourceUsesMediaIndex": True,
            "wrongTripIntakeMustBeBlocked": True,
            "wholeFolderRecognitionBeforeCut": True,
            "footageSelectionBeforeFirstAssembly": True,
            "sourceCoverageBeforeEffectsOrStock": True,
            "filenameOrderRejected": True,
            "routeAwareTruthWithoutGpsOverclaim": True,
        },
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Large Source Unattended Readiness Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Project: `{report.get('projectDir')}`",
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
    lines.extend(["", "## Checks"])
    for row in report["checks"]:
        lines.extend(
            [
                "",
                f"### {row['name']}",
                f"- Status: `{row['status']}`",
                f"- Required: `{row['required']}`",
                f"- Evidence: `{json.dumps(row.get('evidence'), ensure_ascii=False)[:1800]}`",
            ]
        )
    lines.extend(["", "## Safety", "", "```json", json.dumps(report["safety"], ensure_ascii=False, indent=2), "```"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether a large unordered source folder can run unattended to first draft.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--project-dir")
    parser.add_argument("--external-media-intake")
    parser.add_argument("--large-source-video-count", type=int, default=60)
    parser.add_argument("--large-source-gb", type=float, default=100.0)
    parser.add_argument("--min-candidate-rows", type=int, default=3)
    parser.add_argument("--require-external-intake", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "large_source_unattended_readiness_contract_audit.json", report)
    write_markdown(package_dir / "large_source_unattended_readiness_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"], "warnings": report["warnings"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
