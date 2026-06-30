#!/usr/bin/env python3
"""Audit transition cutpoint timing and landing rhythm."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ACCEPTED_EXECUTION_BLUEPRINT_STATUSES = {"ready_with_transition_execution_blueprint"}


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


def execution_blueprint_report(package_dir: Path) -> tuple[dict[str, Any], Path]:
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


def cutpoint(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("transitionCutpointPlan")
    return value if isinstance(value, dict) else {}


def family(row: dict[str, Any]) -> str:
    motion = row.get("transitionMotionExecution") if isinstance(row.get("transitionMotionExecution"), dict) else {}
    return str(motion.get("choreographyFamily") or row.get("selectedStyleFamily") or "")


def is_clean_cut(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(value or "").lower()
        for value in (
            row.get("approvedTransitionType"),
            row.get("resolveEffectName"),
            family(row),
            row.get("selectedCandidateType"),
        )
    )
    return "clean" in text or "cut" in text and not any(term in text for term in ("whip", "rotation", "speed", "ramp", "push", "slide", "dissolve"))


def row_issues(row: dict[str, Any], args: argparse.Namespace) -> list[str]:
    plan = cutpoint(row)
    motion = row.get("transitionMotionExecution") if isinstance(row.get("transitionMotionExecution"), dict) else {}
    safety_checks = motion.get("safetyChecks") if isinstance(motion.get("safetyChecks"), dict) else {}
    issues: list[str] = []
    if not plan:
        return ["missing_transition_cutpoint_plan"]
    important = plan.get("importantBoundary") is True
    min_landing = args.min_important_landing_frames if important else args.min_landing_frames
    if plan.get("status") != "ready_with_transition_cutpoint_plan":
        issues.append("cutpoint_plan_not_ready")
    if as_int(plan.get("outgoingTailFrames")) < args.min_outgoing_tail_frames:
        issues.append("outgoing_tail_too_short")
    if not is_clean_cut(row) and as_int(plan.get("bridgeOrEffectFrames")) < args.min_bridge_or_effect_frames:
        issues.append("bridge_or_effect_hit_too_short")
    if as_int(plan.get("landingHoldFrames")) < min_landing:
        issues.append("landing_hold_too_short")
    if plan.get("handlesReady") is not True:
        issues.append("source_handles_not_ready")
    if plan.get("bgmHitAligned") is not True:
        issues.append("bgm_hit_not_aligned")
    if abs(as_int(plan.get("bgmHitFrameOffset"))) > as_int(plan.get("bgmHitToleranceFrames")):
        issues.append("bgm_hit_offset_exceeds_tolerance")
    if plan.get("titleSubtitleQuietZoneReady") is not True:
        issues.append("title_subtitle_quiet_zone_not_ready")
    if plan.get("bgmOnlyNoSourceVoice") is not True:
        issues.append("transition_audio_not_bgm_only")
    if important and plan.get("importantBoundaryResolved") is not True:
        issues.append("important_boundary_not_resolved_by_bridge_match_or_breath")
    if safety_checks.get("forbidTemplateMotion") is not True:
        issues.append("template_motion_safety_not_declared")
    return issues


def audited_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        plan = cutpoint(row)
        issues = row_issues(row, args)
        out.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "boundaryCategory": row.get("boundaryCategory"),
                "boundarySeconds": row.get("boundarySeconds"),
                "approvedTransitionType": row.get("approvedTransitionType"),
                "resolveEffectName": row.get("resolveEffectName"),
                "choreographyFamily": family(row),
                "cutpointStatus": plan.get("status"),
                "outgoingTailFrames": plan.get("outgoingTailFrames"),
                "bridgeOrEffectFrames": plan.get("bridgeOrEffectFrames"),
                "landingHoldFrames": plan.get("landingHoldFrames"),
                "handlesReady": plan.get("handlesReady"),
                "bgmHitFrameOffset": plan.get("bgmHitFrameOffset"),
                "bgmHitToleranceFrames": plan.get("bgmHitToleranceFrames"),
                "bgmHitAligned": plan.get("bgmHitAligned"),
                "titleSubtitleQuietZoneReady": plan.get("titleSubtitleQuietZoneReady"),
                "bgmOnlyNoSourceVoice": plan.get("bgmOnlyNoSourceVoice"),
                "importantBoundary": plan.get("importantBoundary"),
                "importantBoundaryResolved": plan.get("importantBoundaryResolved"),
                "issues": issues,
            }
        )
    return out


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    execution_report, execution_report_path = execution_blueprint_report(package_dir)
    blueprint, blueprint_path = candidate_blueprint(package_dir, execution_report)
    rows = transition_rows(blueprint)
    audited = audited_rows(rows, args)
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    important_rows = [row for row in audited if row.get("importantBoundary") is True]
    execution_status = execution_report.get("status")
    execution_summary = summary_of(execution_report)

    input_blockers: list[str] = []
    if not execution_report_path.exists() or execution_status not in ACCEPTED_EXECUTION_BLUEPRINT_STATUSES:
        input_blockers.append(f"transitionExecutionBlueprint status is {execution_status}")
    if not blueprint_path.exists():
        input_blockers.append("transition execution candidate blueprint is missing")
    if not rows:
        input_blockers.append("candidate blueprint has no transition rows")
    if as_int(execution_summary.get("rowsWithCutpointReady")) < len(rows):
        input_blockers.append("transition execution blueprint summary does not show cutpoint readiness for every row")

    row_blockers = [
        f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}"
        for row in blocked_rows[: args.max_blocked_rows_in_report]
    ]
    blockers = input_blockers + row_blockers
    summary = {
        "transitionRowCount": len(rows),
        "readyCutpointRowCount": len(rows) - len(blocked_rows),
        "blockedCutpointRowCount": len(blocked_rows),
        "rowsWithOutgoingTail": sum(1 for row in audited if as_int(row.get("outgoingTailFrames")) >= args.min_outgoing_tail_frames),
        "rowsWithBridgeOrEffectHit": sum(1 for row in audited if is_clean_cut(row) or as_int(row.get("bridgeOrEffectFrames")) >= args.min_bridge_or_effect_frames),
        "rowsWithLandingHold": sum(
            1
            for row in audited
            if as_int(row.get("landingHoldFrames")) >= (args.min_important_landing_frames if row.get("importantBoundary") else args.min_landing_frames)
        ),
        "rowsWithHandles": sum(1 for row in audited if row.get("handlesReady") is True),
        "rowsWithBgmHit": sum(1 for row in audited if row.get("bgmHitAligned") is True),
        "rowsWithTitleSubtitleQuietZone": sum(1 for row in audited if row.get("titleSubtitleQuietZoneReady") is True),
        "rowsWithBgmOnlyNoSourceVoice": sum(1 for row in audited if row.get("bgmOnlyNoSourceVoice") is True),
        "importantBoundaryCount": len(important_rows),
        "importantRowsResolved": sum(1 for row in important_rows if row.get("importantBoundaryResolved") is True),
        "executionBlueprintRowsWithCutpointReady": execution_summary.get("rowsWithCutpointReady"),
        "blockedCheckCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "transitionExecutionBlueprintReport": str(execution_report_path),
            "transitionExecutionBlueprintStatus": execution_status,
            "candidateBlueprint": str(blueprint_path),
            "minOutgoingTailFrames": args.min_outgoing_tail_frames,
            "minBridgeOrEffectFrames": args.min_bridge_or_effect_frames,
            "minLandingFrames": args.min_landing_frames,
            "minImportantLandingFrames": args.min_important_landing_frames,
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": [],
        "policy": {
            "everyTransitionNeedsExplicitCutpointPlan": True,
            "outgoingTailBridgeOrEffectLandingRolesRequired": True,
            "bgmHitAlignmentRequired": True,
            "titleSubtitleQuietZoneRequired": True,
            "bgmOnlyNoSourceVoiceRequired": True,
            "importantBoundariesNeedBridgeMatchBreathResolution": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Cutpoint Contract Audit",
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
                f"- Type: `{row.get('approvedTransitionType')}` / `{row.get('resolveEffectName')}`",
                f"- Cutpoint: `{row.get('cutpointStatus')}` outgoing=`{row.get('outgoingTailFrames')}` bridge/effect=`{row.get('bridgeOrEffectFrames')}` landing=`{row.get('landingHoldFrames')}`",
                f"- BGM/title/audio: bgm=`{row.get('bgmHitAligned')}` quiet=`{row.get('titleSubtitleQuietZoneReady')}` bgm-only=`{row.get('bgmOnlyNoSourceVoice')}`",
                f"- Handles/important: handles=`{row.get('handlesReady')}` important=`{row.get('importantBoundary')}` resolved=`{row.get('importantBoundaryResolved')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition cutpoint timing and landing rhythm.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-outgoing-tail-frames", type=int, default=6)
    parser.add_argument("--min-bridge-or-effect-frames", type=int, default=6)
    parser.add_argument("--min-landing-frames", type=int, default=6)
    parser.add_argument("--min-important-landing-frames", type=int, default=10)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir)
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_cutpoint_contract_audit.json", report)
    write_markdown(package_dir / "transition_cutpoint_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
