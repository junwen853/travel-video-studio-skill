#!/usr/bin/env python3
"""Audit the Resolve transition apply plan before Resolve write or handoff."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_DECISION_FIELDS = {
    "approveApplyPath",
    "resolveStepCompleted",
    "resolveReadbackEvidence",
    "frameSampleEvidence",
    "fallbackBridgeInserted",
    "approvedBy",
    "approvedAt",
    "editorNotes",
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


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def plan_path(package_dir: Path, explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_absolute() else (package_dir / path).resolve()
    return package_dir / "resolve_transition_apply_plan" / "resolve_transition_apply_plan.json"


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Resolve Transition Apply Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Apply plan: `{report['inputs'].get('applyPlan')}`",
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
    blocked = [row for row in report.get("auditedRows") or [] if row.get("status") == "blocked"]
    lines.extend(["", "## Blocked Rows"])
    if not blocked:
        lines.append("- None.")
    for row in blocked[:120]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}",
                f"- Apply method: `{row.get('applyMethod')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    method = str(row.get("applyMethod") or "")
    decision_fields = row.get("decisionFields") if isinstance(row.get("decisionFields"), dict) else {}
    acceptance = row.get("acceptanceEvidence") if isinstance(row.get("acceptanceEvidence"), list) else []
    if not method:
        issues.append("missing_apply_method")
    if method == "timeline_marker_handoff_only":
        issues.append("marker_only_apply_method_is_not_allowed")
    if row.get("visibleEffect") and not method:
        issues.append("visible_effect_missing_apply_path")
    if row.get("visibleEffect") and method == "timeline_marker_handoff_only":
        issues.append("visible_effect_marker_only")
    if row.get("manualResolveStepRequired") and not row.get("manualInstruction"):
        issues.append("manual_resolve_step_missing_instruction")
    if row.get("fallbackBridgeInsertRequired") and not row.get("manualInstruction"):
        issues.append("fallback_bridge_requirement_missing_instruction")
    if row.get("readbackEvidenceRequired") is not True:
        issues.append("readback_evidence_not_required")
    if not REQUIRED_DECISION_FIELDS.issubset(set(decision_fields.keys())):
        issues.append("missing_apply_decision_fields")
    if len(acceptance) < 2:
        issues.append("missing_acceptance_evidence")
    if row.get("markerPayloadReady") is not True:
        issues.append("marker_payload_not_ready")
    if row.get("clipAnnotationPresent") is not True:
        issues.append("clip_annotation_not_present")
    return {
        "rowIndex": row.get("rowIndex"),
        "status": "passed" if not issues else "blocked",
        "applyMethod": method,
        "visibleEffect": bool(row.get("visibleEffect")),
        "manualResolveStepRequired": bool(row.get("manualResolveStepRequired")),
        "fallbackBridgeInsertRequired": bool(row.get("fallbackBridgeInsertRequired")),
        "decisionFieldCount": len(decision_fields),
        "acceptanceEvidenceCount": len(acceptance),
        "issues": issues,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    apply_plan_path = plan_path(package_dir, args.apply_plan)
    apply_plan = load_json(apply_plan_path) or {}
    materialization_path = package_dir / "resolve_transition_materialization_contract_audit.json"
    materialization = load_json(materialization_path) or {}
    if not isinstance(apply_plan, dict) or not apply_plan:
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "applyPlan": str(apply_plan_path),
                "applyPlanExists": apply_plan_path.exists(),
                "materializationAudit": str(materialization_path),
                "materializationStatus": materialization.get("status"),
            },
            "summary": {},
            "auditedRows": [],
            "blockers": [f"missing or unreadable apply plan: {apply_plan_path}"],
            "warnings": [],
            "safety": safety(),
        }
    rows = apply_plan.get("transitionApplyRows") if isinstance(apply_plan.get("transitionApplyRows"), list) else []
    audited = [audit_row(row) for row in rows if isinstance(row, dict)]
    blocked = [row for row in audited if row.get("status") == "blocked"]
    blockers: list[str] = []
    warnings: list[str] = []
    if apply_plan.get("status") != "ready_with_resolve_transition_apply_plan":
        blockers.append(f"apply plan status is not ready: {apply_plan.get('status')}")
    if not rows:
        blockers.append("apply plan has no transition rows")
    if materialization_path.exists() and materialization.get("status") != "passed":
        blockers.append("resolve transition materialization audit is not passed")
    if not materialization_path.exists():
        warnings.append("resolve transition materialization audit is missing; run it before Resolve apply approval")
    for row in blocked[:80]:
        blockers.append(f"transition row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}")
    summary = {
        "transitionApplyRowCount": len(rows),
        "auditedRowCount": len(audited),
        "passedRowCount": len([row for row in audited if row.get("status") == "passed"]),
        "blockedRowCount": len(blocked),
        "visibleEffectRowCount": len([row for row in audited if row.get("visibleEffect")]),
        "visibleEffectRowsWithApplyPath": len(
            [row for row in audited if row.get("visibleEffect") and row.get("applyMethod") != "timeline_marker_handoff_only"]
        ),
        "manualResolveRowCount": len([row for row in audited if row.get("manualResolveStepRequired")]),
        "fallbackBridgeRequiredRowCount": len([row for row in audited if row.get("fallbackBridgeInsertRequired")]),
        "readbackEvidenceRequiredRowCount": len([row for row in rows if isinstance(row, dict) and row.get("readbackEvidenceRequired") is True]),
        "decisionFieldRowCount": len(
            [
                row
                for row in rows
                if isinstance(row, dict)
                and REQUIRED_DECISION_FIELDS.issubset(set(((row.get("decisionFields") if isinstance(row.get("decisionFields"), dict) else {}) or {}).keys()))
            ]
        ),
        "markerOnlyBlockedRowCount": len([row for row in rows if isinstance(row, dict) and row.get("applyMethod") == "timeline_marker_handoff_only"]),
        "blockerCount": len(blockers),
    }
    status = "passed" if not blockers and rows else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "applyPlan": str(apply_plan_path),
            "applyPlanExists": apply_plan_path.exists(),
            "applyPlanStatus": apply_plan.get("status"),
            "materializationAudit": str(materialization_path),
            "materializationStatus": materialization.get("status"),
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Resolve transition apply plan readiness.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--apply-plan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "resolve_transition_apply_contract_audit.json", report)
    write_markdown(package_dir / "resolve_transition_apply_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
