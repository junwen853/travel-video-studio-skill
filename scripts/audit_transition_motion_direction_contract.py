#!/usr/bin/env python3
"""Audit motion-direction consistency for visible travel transitions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionChoreographyPlan": ("transition_choreography_plan/transition_choreography_plan.json", {"ready_with_transition_choreography_plan"}),
    "transitionChoreographyContract": ("transition_choreography_contract_audit.json", {"passed"}),
    "transitionVisualMatch": ("transition_visual_match_contract_audit.json", {"passed"}),
    "transitionEffectPalette": ("transition_effect_palette_contract_audit.json", {"passed"}),
}
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide"}
ROTATION_DIRECTIONS = {"clockwise", "counterclockwise", "subtle_centered_rotation"}
SPEED_RAMP_DIRECTIONS = {"forward", "backward", "up", "down", "zoom_in", "zoom_out"}


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


def load_reports(package_dir: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for name, (rel_path, accepted) in REPORT_SPECS.items():
        path = package_dir / rel_path
        data = load_json(path) or {}
        reports[name] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(accepted),
            "accepted": data.get("status") in accepted,
            "summary": summary_of(data),
            "blockers": data.get("blockers") or [],
            "warnings": data.get("warnings") or [],
            "data": data,
        }
    return reports


def choreography_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("choreographyRows") if isinstance(plan.get("choreographyRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def motion_direction(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("motionDirectionPlan")
    return value if isinstance(value, dict) else {}


def motion_evidence(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("motionEvidence")
    return value if isinstance(value, dict) else {}


def has_bridge_support(row: dict[str, Any]) -> bool:
    evidence = motion_evidence(row)
    direction = motion_direction(row)
    return bool(
        evidence.get("physicalBridgeEvidence") is True
        or evidence.get("hasRouteBridgeTerms") is True
        or evidence.get("bridgeTerms")
        or direction.get("bridgeMotionDirections")
    )


def row_issues(row: dict[str, Any], args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    style = str(row.get("sourceTransitionStyle") or "")
    direction = motion_direction(row)
    motion_style = style in MOTION_STYLES
    if row.get("status") != "ready_with_transition_choreography":
        issues.append("choreography_row_not_ready")
    if row.get("forbiddenHits"):
        issues.append("forbidden_template_or_flash_transition_language")
    if not motion_style:
        if direction.get("required") is True:
            issues.append("non_motion_transition_marked_as_motion_direction_required")
        if as_int(row.get("intensity")) >= 3:
            issues.append("non_motion_transition_intensity_too_high")
        return issues

    if direction.get("required") is not True:
        issues.append("motion_transition_missing_required_direction_flag")
    if direction.get("status") != "ready_with_motion_direction_plan":
        issues.append("motion_direction_plan_not_ready")
    if not direction.get("effectDirection"):
        issues.append("missing_effect_direction")
    if not direction.get("landingDirection"):
        issues.append("missing_landing_direction")
    if direction.get("directionMatch") is not True:
        issues.append("effect_direction_does_not_match_source_or_bridge_motion")
    if direction.get("directionConflict") is True:
        issues.append("opposite_motion_direction_conflict")
    if as_float(direction.get("directionConfidence")) < args.min_direction_confidence:
        issues.append("direction_confidence_too_low")
    if not (direction.get("sourceMotionDirections") or direction.get("bridgeMotionDirections")):
        issues.append("missing_directional_motion_terms")
    if direction.get("bgmAligned") is not True:
        issues.append("motion_direction_not_bgm_hit_aligned")
    if direction.get("captionTitleSafe") is not True:
        issues.append("motion_direction_not_title_or_caption_safe")
    if row.get("importantBoundary") and not has_bridge_support(row):
        issues.append("important_motion_boundary_missing_bridge_direction_support")
    effect_direction = str(direction.get("effectDirection") or "")
    if style == "rotation" and effect_direction not in ROTATION_DIRECTIONS:
        issues.append("rotation_direction_not_explicit_or_subtle")
    if style == "rotation" and as_int(row.get("intensity")) > 1:
        issues.append("rotation_intensity_not_subtle")
    if style == "speed_ramp" and effect_direction and effect_direction not in SPEED_RAMP_DIRECTIONS:
        issues.append("speed_ramp_direction_not_travel_or_zoom_motion")
    if as_int(row.get("intensity")) >= 3:
        issues.append("motion_transition_intensity_too_high")
    return issues


def audited_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        direction = motion_direction(row)
        issues = row_issues(row, args)
        audited.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "boundaryCategory": row.get("boundaryCategory"),
                "importantBoundary": row.get("importantBoundary"),
                "sourceTransitionStyle": row.get("sourceTransitionStyle"),
                "choreographyFamily": row.get("choreographyFamily"),
                "intensity": row.get("intensity"),
                "required": direction.get("required") is True,
                "directionStatus": direction.get("status"),
                "effectDirection": direction.get("effectDirection"),
                "landingDirection": direction.get("landingDirection"),
                "sharedDirection": direction.get("sharedDirection"),
                "directionConfidence": direction.get("directionConfidence"),
                "directionMatch": direction.get("directionMatch"),
                "directionConflict": direction.get("directionConflict"),
                "sourceMotionDirections": direction.get("sourceMotionDirections") or [],
                "bridgeMotionDirections": direction.get("bridgeMotionDirections") or [],
                "bgmAligned": direction.get("bgmAligned"),
                "captionTitleSafe": direction.get("captionTitleSafe"),
                "hasBridgeSupport": has_bridge_support(row),
                "issues": issues,
            }
        )
    return audited


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    plan = reports["transitionChoreographyPlan"]["data"]
    rows = choreography_rows(plan)
    audited = audited_rows(rows, args)
    motion_rows = [row for row in audited if row.get("sourceTransitionStyle") in MOTION_STYLES]
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    blocked_motion_rows = [row for row in motion_rows if row.get("status") == "blocked"]
    important_motion_rows = [row for row in motion_rows if row.get("importantBoundary")]

    direction_counts: dict[str, int] = {}
    for row in motion_rows:
        direction = str(row.get("effectDirection") or "missing")
        direction_counts[direction] = direction_counts.get(direction, 0) + 1

    input_blockers = [
        f"{name} status is {report.get('status')}"
        for name, report in reports.items()
        if not (report["exists"] and report["accepted"])
    ]
    row_blockers = [
        f"row {row.get('rowIndex')} {row.get('sourceTransitionStyle')}: {', '.join(row.get('issues') or [])}"
        for row in blocked_rows[: args.max_blocked_rows_in_report]
    ]
    blockers = input_blockers + row_blockers
    summary = {
        "transitionRowCount": len(rows),
        "motionDirectionRowCount": len(motion_rows),
        "readyMotionDirectionRowCount": len(motion_rows) - len(blocked_motion_rows),
        "blockedMotionDirectionRowCount": len(blocked_motion_rows),
        "rowsWithEffectDirection": sum(1 for row in motion_rows if row.get("effectDirection")),
        "rowsWithLandingDirection": sum(1 for row in motion_rows if row.get("landingDirection")),
        "rowsWithDirectionMatch": sum(1 for row in motion_rows if row.get("directionMatch") is True),
        "rowsWithDirectionConfidence": sum(1 for row in motion_rows if as_float(row.get("directionConfidence")) >= args.min_direction_confidence),
        "bgmAlignedMotionRowCount": sum(1 for row in motion_rows if row.get("bgmAligned") is True),
        "titleSafeMotionRowCount": sum(1 for row in motion_rows if row.get("captionTitleSafe") is True),
        "importantMotionRowCount": len(important_motion_rows),
        "importantMotionRowsWithBridgeSupport": sum(1 for row in important_motion_rows if row.get("hasBridgeSupport") is True),
        "rotationRowCount": sum(1 for row in motion_rows if row.get("sourceTransitionStyle") == "rotation"),
        "speedRampRowCount": sum(1 for row in motion_rows if row.get("sourceTransitionStyle") == "speed_ramp"),
        "effectDirectionCounts": direction_counts,
        "blockedCheckCount": len(input_blockers) + len(blocked_rows),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "minDirectionConfidence": args.min_direction_confidence,
            "reports": {name: report["path"] for name, report in reports.items()},
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": [],
        "policy": {
            "motionEffectsRequireDirectionPlan": True,
            "effectDirectionMustMatchSourceOrBridgeMotion": True,
            "importantMotionBoundariesRequireBridgeDirectionSupport": True,
            "rotationMustBeExplicitOrSubtle": True,
            "speedRampMustFollowTravelOrZoomMotion": True,
            "bgmHitAndTitleSafetyRequired": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Motion Direction Contract Audit",
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
    if report["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Audited Rows"])
    for row in report["auditedRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('sourceTransitionStyle')}`",
                f"- Status: `{row.get('status')}`",
                f"- Direction: effect=`{row.get('effectDirection')}` landing=`{row.get('landingDirection')}` confidence=`{row.get('directionConfidence')}`",
                f"- Match: `{row.get('directionMatch')}` bridgeSupport=`{row.get('hasBridgeSupport')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Whip, rotation, push, and speed-ramp transitions need explicit source or bridge direction evidence.",
            "- The effect direction must match the outgoing, bridge, or landing movement direction.",
            "- Important motion boundaries must keep route/bridge support; effects cannot cover a missing bridge.",
            "- Motion accents must stay on the BGM phrase hit and avoid title/subtitle zones.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition motion-direction consistency.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-direction-confidence", type=float, default=0.65)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_motion_direction_contract_audit.json", report)
    write_markdown(package_dir / "transition_motion_direction_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
