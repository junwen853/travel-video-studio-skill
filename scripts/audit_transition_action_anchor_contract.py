#!/usr/bin/env python3
"""Audit transition action anchors for readable outgoing, bridge, and landing moments."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


READY_EXECUTION_BLUEPRINT_STATUSES = {"ready_with_transition_execution_blueprint"}
READY_ACTION_ANCHOR_STATUS = "ready_with_transition_action_anchor_plan"
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide"}


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


def summary_of(data: Any) -> dict[str, Any]:
    return data.get("summary") if isinstance(data, dict) and isinstance(data.get("summary"), dict) else {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def execution_report(package_dir: Path) -> tuple[dict[str, Any], Path]:
    path = package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json"
    return load_json(path) or {}, path


def candidate_blueprint(package_dir: Path, report: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    path = Path(str(outputs.get("candidateBlueprint") or package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json"))
    if not path.is_absolute():
        path = package_dir / path
    return load_json(path) or {}, path


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def action_anchor(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("transitionActionAnchorPlan")
    return value if isinstance(value, dict) else {}


def nested_ready(plan: dict[str, Any], key: str) -> bool:
    value = plan.get(key)
    return isinstance(value, dict) and value.get("ready") is True


def transition_style(row: dict[str, Any], plan: dict[str, Any]) -> str:
    motion = row.get("transitionMotionExecution") if isinstance(row.get("transitionMotionExecution"), dict) else {}
    return str(plan.get("sourceTransitionStyle") or motion.get("sourceTransitionStyle") or row.get("selectedCandidateType") or "")


def row_issues(row: dict[str, Any]) -> list[str]:
    plan = action_anchor(row)
    issues: list[str] = []
    if not plan:
        return ["missing_transition_action_anchor_plan"]
    style = transition_style(row, plan)
    important = plan.get("importantBoundary") is True
    if plan.get("status") != READY_ACTION_ANCHOR_STATUS:
        issues.append("action_anchor_plan_not_ready")
    if not nested_ready(plan, "outgoingAnchor"):
        issues.append("missing_outgoing_action_anchor")
    if plan.get("bridgeOrMatchReady") is not True:
        issues.append("missing_bridge_or_match_action_anchor")
    if not nested_ready(plan, "landingAnchor"):
        issues.append("missing_landing_action_anchor")
    if style in MOTION_STYLES and plan.get("directionalMotionAnchorReady") is not True:
        issues.append("motion_accent_missing_directional_action_anchor")
    if important and plan.get("importantBoundaryResolved") is not True:
        issues.append("important_boundary_not_resolved_by_action_anchor")
    for key in ("outgoingAnchor", "bridgeOrMatchAnchor", "landingAnchor"):
        value = plan.get(key)
        if isinstance(value, dict) and value.get("weakOrPlaceholder") is True:
            issues.append(f"{key}_weak_or_placeholder")
    if plan.get("cutpointReady") is not True:
        issues.append("cutpoint_not_ready_for_action_anchor")
    return issues


def audited_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        plan = action_anchor(row)
        issues = row_issues(row)
        audited.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "boundaryCategory": row.get("boundaryCategory"),
                "approvedTransitionType": row.get("approvedTransitionType"),
                "sourceTransitionStyle": transition_style(row, plan),
                "actionAnchorStatus": plan.get("status"),
                "importantBoundary": plan.get("importantBoundary"),
                "outgoingReady": nested_ready(plan, "outgoingAnchor"),
                "bridgeOrMatchReady": plan.get("bridgeOrMatchReady"),
                "landingReady": nested_ready(plan, "landingAnchor"),
                "directionalMotionAnchorReady": plan.get("directionalMotionAnchorReady"),
                "importantBoundaryResolved": plan.get("importantBoundaryResolved"),
                "cutpointReady": plan.get("cutpointReady"),
                "issues": issues,
            }
        )
    return audited


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    report, report_path = execution_report(package_dir)
    blueprint, blueprint_path = candidate_blueprint(package_dir, report)
    rows = transition_rows(blueprint)
    audited = audited_rows(rows)
    blocked = [row for row in audited if row.get("status") == "blocked"]
    important_rows = [row for row in audited if row.get("importantBoundary") is True]
    motion_rows = [row for row in audited if row.get("sourceTransitionStyle") in MOTION_STYLES]
    execution_summary = summary_of(report)
    blockers: list[str] = []
    if not report_path.exists() or report.get("status") not in READY_EXECUTION_BLUEPRINT_STATUSES:
        blockers.append(f"transitionExecutionBlueprint status is {report.get('status')}")
    if not blueprint_path.exists():
        blockers.append("transition execution candidate blueprint is missing")
    if not rows:
        blockers.append("candidate blueprint has no transition rows")
    if as_int(execution_summary.get("rowsWithActionAnchorReady")) < len(rows):
        blockers.append("transition execution blueprint summary does not show action-anchor readiness for every row")
    blockers.extend(
        f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}"
        for row in blocked[: args.max_blocked_rows_in_report]
    )
    summary = {
        "transitionRowCount": len(rows),
        "readyActionAnchorRowCount": len(rows) - len(blocked),
        "blockedActionAnchorRowCount": len(blocked),
        "rowsWithOutgoingActionAnchor": sum(1 for row in audited if row.get("outgoingReady") is True),
        "rowsWithBridgeOrMatchActionAnchor": sum(1 for row in audited if row.get("bridgeOrMatchReady") is True),
        "rowsWithLandingActionAnchor": sum(1 for row in audited if row.get("landingReady") is True),
        "motionAnchorRowCount": len(motion_rows),
        "rowsWithDirectionalMotionAnchor": sum(1 for row in motion_rows if row.get("directionalMotionAnchorReady") is True),
        "importantBoundaryCount": len(important_rows),
        "importantRowsResolved": sum(1 for row in important_rows if row.get("importantBoundaryResolved") is True),
        "rowsWithCutpointReady": sum(1 for row in audited if row.get("cutpointReady") is True),
        "executionBlueprintRowsWithActionAnchorReady": execution_summary.get("rowsWithActionAnchorReady"),
        "blockedCheckCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "transitionExecutionBlueprintReport": str(report_path),
            "transitionExecutionBlueprintStatus": report.get("status"),
            "candidateBlueprint": str(blueprint_path),
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": [],
        "policy": {
            "outgoingActionAnchorRequired": True,
            "bridgeOrMatchActionAnchorRequired": True,
            "landingActionAnchorRequired": True,
            "motionEffectsNeedDirectionalActionAnchor": True,
            "importantBoundariesNeedActionAnchorResolution": True,
            "actionAnchorsDependOnReadyCutpoint": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Action Anchor Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Audited Rows"])
    for row in report.get("auditedRows", [])[:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')} - `{row.get('status')}`",
                f"- Type/style: `{row.get('approvedTransitionType')}` / `{row.get('sourceTransitionStyle')}`",
                f"- Anchors: outgoing=`{row.get('outgoingReady')}` bridge-or-match=`{row.get('bridgeOrMatchReady')}` landing=`{row.get('landingReady')}` directional=`{row.get('directionalMotionAnchorReady')}`",
                f"- Important/cutpoint: important=`{row.get('importantBoundary')}` resolved=`{row.get('importantBoundaryResolved')}` cutpoint=`{row.get('cutpointReady')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition action anchors.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir)
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_action_anchor_contract_audit.json", report)
    write_markdown(package_dir / "transition_action_anchor_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
