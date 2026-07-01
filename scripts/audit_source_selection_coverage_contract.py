#!/usr/bin/env python3
"""Audit that source-selection coverage repairs are closed before first draft trust."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_POLICY = {
    "blocksFilenameOrderAssembly": True,
    "blocksWeakChapterCoverageBeforeEffects": True,
    "localFootageBeforeStockOrAerialFallback": True,
    "orientationRepairClosedBeforeFinalUse": True,
    "repairRowsMustCloseBeforeResolveApply": True,
    "doesNotModifySourceFootage": True,
    "writesResolve": False,
    "downloadsExternalAssets": False,
}
REQUIRED_DECISION_FIELDS = {
    "acceptedRepair",
    "ownerScriptExecuted",
    "replacementRowIndexes",
    "approvedFallback",
    "resolveBlueprintUpdate",
    "postRepairAudit",
    "readbackEvidence",
    "approvedBy",
    "approvedAt",
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


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def plan_path(package_dir: Path, explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_absolute() else (package_dir / path).resolve()
    return package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json"


def build_report(package_dir: Path, explicit_plan: str | None = None) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    path = plan_path(package_dir, explicit_plan)
    plan = load_json(path) or {}
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    policy = plan.get("policy") if isinstance(plan.get("policy"), dict) else {}
    repair_rows = [row for row in plan.get("repairRows") or [] if isinstance(row, dict)]
    chapter_rows = [row for row in plan.get("chapterCoverageRows") or [] if isinstance(row, dict)]
    blocking_rows = [row for row in repair_rows if row.get("severity") == "blocker"]
    warning_rows = [row for row in repair_rows if row.get("severity") != "blocker"]
    missing_policy = {
        key: {"expected": expected, "actual": policy.get(key)}
        for key, expected in REQUIRED_POLICY.items()
        if policy.get(key) is not expected
    }
    repair_rows_with_decision = 0
    for row in repair_rows:
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if REQUIRED_DECISION_FIELDS.issubset(set(decision)):
            repair_rows_with_decision += 1
    open_repair_row_count = as_int(summary.get("openRepairRowCount"), len(repair_rows))
    decision_issue_count = as_int(summary.get("decisionIssueCount"))
    rows_with_decision_issues = as_int(summary.get("rowsWithDecisionIssues"))
    ready_chapters = [row for row in chapter_rows if row.get("status") == "ready_with_chapter_selection_coverage"]

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Source selection repair plan exists and is in the package",
        path.exists() and bool(plan),
        {"path": str(path), "exists": path.exists()},
    )
    add_check(
        checks,
        "Source selection coverage has no blocking repair rows",
        plan.get("status") == "ready_no_source_selection_repairs_needed"
        and as_int(summary.get("blockingRepairRowCount")) == 0
        and as_int(summary.get("warningRepairRowCount")) == 0
        and open_repair_row_count == 0
        and decision_issue_count == 0
        and rows_with_decision_issues == 0
        and not blocking_rows,
        {
            "status": plan.get("status"),
            "blockingRepairRowCount": summary.get("blockingRepairRowCount"),
            "warningRepairRowCount": summary.get("warningRepairRowCount"),
            "openRepairRowCount": summary.get("openRepairRowCount"),
            "decisionIssueCount": summary.get("decisionIssueCount"),
            "rowsWithDecisionIssues": summary.get("rowsWithDecisionIssues"),
            "blockingRepairIds": [row.get("repairId") for row in blocking_rows],
        },
    )
    add_check(
        checks,
        "Every chapter has ready local source coverage before effects or stock fallback",
        bool(chapter_rows)
        and len(ready_chapters) == len(chapter_rows)
        and as_int(summary.get("chapterRowCount")) == len(chapter_rows)
        and as_int(summary.get("candidateVideoCount")) > 0,
        {
            "chapterRowCount": len(chapter_rows),
            "readyChapterCount": len(ready_chapters),
            "candidateVideoCount": summary.get("candidateVideoCount"),
            "blockedChapters": [row.get("chapterKey") for row in chapter_rows if row.get("status") != "ready_with_chapter_selection_coverage"],
        },
    )
    add_check(
        checks,
        "Opening/ending hero, route movement, texture, and payoff pools exist",
        as_int(summary.get("heroCandidateCount")) >= 1
        and as_int(summary.get("movementBridgeCandidateCount")) >= max(1, as_int(summary.get("chapterRowCount")) - 1)
        and as_int(summary.get("livedInTextureCandidateCount")) >= 1
        and as_int(summary.get("destinationPayoffCandidateCount")) >= 1,
        {
            "heroCandidateCount": summary.get("heroCandidateCount"),
            "movementBridgeCandidateCount": summary.get("movementBridgeCandidateCount"),
            "livedInTextureCandidateCount": summary.get("livedInTextureCandidateCount"),
            "destinationPayoffCandidateCount": summary.get("destinationPayoffCandidateCount"),
            "chapterRowCount": summary.get("chapterRowCount"),
        },
    )
    add_check(
        checks,
        "Repair rows are machine-actionable when warnings remain",
        len(repair_rows) == repair_rows_with_decision and open_repair_row_count == 0 and decision_issue_count == 0,
        {
            "repairRowCount": len(repair_rows),
            "warningRepairRowCount": len(warning_rows),
            "openRepairRowCount": summary.get("openRepairRowCount"),
            "closedRepairRowCount": summary.get("closedRepairRowCount"),
            "decisionIssueCount": summary.get("decisionIssueCount"),
            "rowsWithDecisionIssues": summary.get("rowsWithDecisionIssues"),
            "rowsWithDecisionFields": repair_rows_with_decision,
        },
    )
    add_check(
        checks,
        "Source selection coverage policy is portable and non-destructive",
        not missing_policy,
        {"missingOrWrongPolicy": missing_policy},
    )

    blockers = [row for row in checks if row["status"] == "blocked"]
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "sourceSelectionRepairPlan": str(path),
            "planStatus": plan.get("status"),
        },
        "summary": {
            "sourceVideoCount": summary.get("sourceVideoCount"),
            "chapterRowCount": summary.get("chapterRowCount"),
            "readyChapterCount": summary.get("readyChapterCount"),
            "candidateVideoCount": summary.get("candidateVideoCount"),
            "heroCandidateCount": summary.get("heroCandidateCount"),
            "movementBridgeCandidateCount": summary.get("movementBridgeCandidateCount"),
            "livedInTextureCandidateCount": summary.get("livedInTextureCandidateCount"),
            "destinationPayoffCandidateCount": summary.get("destinationPayoffCandidateCount"),
            "blockingRepairRowCount": summary.get("blockingRepairRowCount"),
            "warningRepairRowCount": summary.get("warningRepairRowCount"),
            "openRepairRowCount": summary.get("openRepairRowCount"),
            "closedRepairRowCount": summary.get("closedRepairRowCount"),
            "totalRepairRowCount": summary.get("totalRepairRowCount"),
            "decisionArchiveCount": summary.get("decisionArchiveCount"),
            "decisionIssueCount": summary.get("decisionIssueCount"),
            "rowsWithDecisionIssues": summary.get("rowsWithDecisionIssues"),
            "rowsWithClosureDecision": summary.get("rowsWithClosureDecision"),
            "checkCount": len(checks),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": len(blockers),
        },
        "checks": checks,
        "blockers": [row["name"] for row in blockers],
        "warnings": [row.get("repairId") for row in warning_rows if row.get("repairId")],
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Source Selection Coverage Contract Audit",
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
    if report.get("warnings"):
        lines.extend(["", "## Warning Repair Rows"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(
            [
                "",
                f"### {row.get('name')}",
                f"- Status: `{row.get('status')}`",
                f"- Evidence: `{json.dumps(row.get('evidence'), ensure_ascii=False)[:1400]}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit source-selection coverage repair closure.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--source-selection-repair-plan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args.source_selection_repair_plan)
    write_json(package_dir / "source_selection_coverage_contract_audit.json", report)
    write_markdown(package_dir / "source_selection_coverage_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
