#!/usr/bin/env python3
"""Audit transition sensory continuity for reference-style travel cuts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


READY_EXECUTION_BLUEPRINT_STATUSES = {"ready_with_transition_execution_blueprint"}
READY_SENSORY_STATUS = "ready_with_transition_sensory_continuity_plan"
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


def sensory_plan(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("transitionSensoryContinuityPlan")
    return value if isinstance(value, dict) else {}


def motion_style(row: dict[str, Any], plan: dict[str, Any]) -> str:
    motion = row.get("transitionMotionExecution") if isinstance(row.get("transitionMotionExecution"), dict) else {}
    return str(plan.get("sourceTransitionStyle") or motion.get("sourceTransitionStyle") or row.get("selectedCandidateType") or "")


def row_issues(row: dict[str, Any]) -> list[str]:
    plan = sensory_plan(row)
    if not plan:
        return ["missing_transition_sensory_continuity_plan"]
    channels = plan.get("cueChannels") if isinstance(plan.get("cueChannels"), dict) else {}
    issues: list[str] = []
    if plan.get("status") != READY_SENSORY_STATUS:
        issues.append("sensory_continuity_plan_not_ready")
    if channels.get("visualContinuityReady") is not True:
        issues.append("missing_visual_continuity")
    if channels.get("audioContinuityReady") is not True:
        issues.append("missing_bgm_audio_continuity")
    if channels.get("captionQuietReady") is not True:
        issues.append("missing_caption_or_title_quiet_zone")
    if channels.get("landingContinuityReady") is not True:
        issues.append("missing_stable_landing_continuity")
    if plan.get("importantBoundary") is True and channels.get("routeOrMoodContinuityReady") is not True:
        issues.append("important_boundary_missing_route_or_mood_continuity")
    if motion_style(row, plan) in MOTION_STYLES and channels.get("motionContinuityReady") is not True:
        issues.append("motion_effect_missing_sensory_direction_continuity")
    if as_int(plan.get("cueChannelCount")) < as_int(plan.get("requiredCueChannelCount")):
        issues.append("insufficient_sensory_cue_channels")
    if plan.get("bgmOnlyNoSourceVoice") is not True:
        issues.append("source_audio_or_voice_may_leak_into_transition")
    if plan.get("actionAnchorReady") is not True:
        issues.append("action_anchor_not_ready_for_sensory_continuity")
    if plan.get("cutpointReady") is not True:
        issues.append("cutpoint_not_ready_for_sensory_continuity")
    return issues


def audited_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        plan = sensory_plan(row)
        channels = plan.get("cueChannels") if isinstance(plan.get("cueChannels"), dict) else {}
        issues = row_issues(row)
        audited.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "boundaryCategory": row.get("boundaryCategory"),
                "approvedTransitionType": row.get("approvedTransitionType"),
                "sourceTransitionStyle": motion_style(row, plan),
                "sensoryStatus": plan.get("status"),
                "importantBoundary": plan.get("importantBoundary"),
                "cueChannelCount": plan.get("cueChannelCount"),
                "requiredCueChannelCount": plan.get("requiredCueChannelCount"),
                "visualReady": channels.get("visualContinuityReady"),
                "audioReady": channels.get("audioContinuityReady"),
                "captionQuietReady": channels.get("captionQuietReady"),
                "routeOrMoodReady": channels.get("routeOrMoodContinuityReady"),
                "landingReady": channels.get("landingContinuityReady"),
                "motionReady": channels.get("motionContinuityReady"),
                "bgmOnlyNoSourceVoice": plan.get("bgmOnlyNoSourceVoice"),
                "actionAnchorReady": plan.get("actionAnchorReady"),
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
    if as_int(execution_summary.get("rowsWithSensoryContinuityReady")) < len(rows):
        blockers.append("transition execution blueprint summary does not show sensory-continuity readiness for every row")
    blockers.extend(
        f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}"
        for row in blocked[: args.max_blocked_rows_in_report]
    )
    summary = {
        "transitionRowCount": len(rows),
        "readySensoryContinuityRowCount": len(rows) - len(blocked),
        "blockedSensoryContinuityRowCount": len(blocked),
        "rowsWithVisualSensoryContinuity": sum(1 for row in audited if row.get("visualReady") is True),
        "rowsWithAudioSensoryContinuity": sum(1 for row in audited if row.get("audioReady") is True),
        "rowsWithCaptionSensoryContinuity": sum(1 for row in audited if row.get("captionQuietReady") is True),
        "rowsWithRouteOrMoodSensoryContinuity": sum(1 for row in audited if row.get("routeOrMoodReady") is True),
        "rowsWithLandingSensoryContinuity": sum(1 for row in audited if row.get("landingReady") is True),
        "motionSensoryRowCount": len(motion_rows),
        "rowsWithMotionSensoryContinuity": sum(1 for row in motion_rows if row.get("motionReady") is True),
        "importantBoundaryCount": len(important_rows),
        "importantRowsWithRouteOrMoodContinuity": sum(1 for row in important_rows if row.get("routeOrMoodReady") is True),
        "rowsWithBgmOnlyNoSourceVoice": sum(1 for row in audited if row.get("bgmOnlyNoSourceVoice") is True),
        "rowsWithActionAnchorReady": sum(1 for row in audited if row.get("actionAnchorReady") is True),
        "rowsWithCutpointReady": sum(1 for row in audited if row.get("cutpointReady") is True),
        "executionBlueprintRowsWithSensoryContinuityReady": execution_summary.get("rowsWithSensoryContinuityReady"),
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
            "visualContinuityRequired": True,
            "bgmPhraseAndBgmOnlyAudioRequired": True,
            "captionQuietZoneRequired": True,
            "importantBoundariesNeedRouteOrMoodContinuity": True,
            "stableLandingContinuityRequired": True,
            "motionEffectsNeedSensoryDirectionContinuity": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Sensory Continuity Contract Audit",
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
                f"- Cues: {row.get('cueChannelCount')} / {row.get('requiredCueChannelCount')}",
                f"- Visual/audio/caption: `{row.get('visualReady')}` / `{row.get('audioReady')}` / `{row.get('captionQuietReady')}`",
                f"- Route-or-mood/landing/motion: `{row.get('routeOrMoodReady')}` / `{row.get('landingReady')}` / `{row.get('motionReady')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition sensory continuity.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir)
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_sensory_continuity_contract_audit.json", report)
    write_markdown(package_dir / "transition_sensory_continuity_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
