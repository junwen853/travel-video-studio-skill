#!/usr/bin/env python3
"""Audit shot-to-shot transition microstructure from existing transition gates."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionQuality": {
        "path": "transition_quality_contract_audit.json",
        "accepted": {"passed"},
    },
    "shotTransitionBoundary": {
        "path": "shot_transition_boundary_contract_audit.json",
        "accepted": {"passed"},
    },
    "transitionMotivation": {
        "path": "transition_motivation_contract_audit.json",
        "accepted": {"passed"},
    },
    "transitionPairContinuity": {
        "path": "transition_pair_continuity_contract_audit.json",
        "accepted": {"passed"},
    },
    "transitionExecutionReadiness": {
        "path": "transition_execution_readiness_contract_audit.json",
        "accepted": {"passed"},
    },
    "transitionPolishApplication": {
        "path": "transition_polish_application_contract_audit.json",
        "accepted": {"passed"},
    },
    "resolveTransitionApply": {
        "path": "resolve_transition_apply_contract_audit.json",
        "accepted": {"passed"},
    },
    "bridgeSequenceApplication": {
        "path": "bridge_sequence_application_contract_audit.json",
        "accepted": {"passed"},
    },
    "finalBlueprintLineage": {
        "path": "final_blueprint_lineage_contract_audit.json",
        "accepted": {"passed"},
    },
    "transitionCadence": {
        "path": "transition_cadence_contract_audit.json",
        "accepted": {"passed"},
    },
    "transitionCutpoint": {
        "path": "transition_cutpoint_contract_audit.json",
        "accepted": {"passed"},
    },
}
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


def load_reports(package_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, spec in REPORT_SPECS.items():
        path = package_dir / str(spec["path"])
        data = load_json(path) or {}
        out[name] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(spec["accepted"]),
            "accepted": data.get("status") in spec["accepted"],
            "summary": summary_of(data),
            "blockers": data.get("blockers") or [],
            "warnings": data.get("warnings") or [],
        }
    return out


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def max_summary_int(reports: dict[str, dict[str, Any]], field: str, names: tuple[str, ...]) -> int:
    return max(as_int(reports[name]["summary"].get(field)) for name in names)


def max_decorative_run(reports: dict[str, dict[str, Any]]) -> int:
    return max(
        as_int(reports["transitionQuality"]["summary"].get("decorativeRepeatedRunMax")),
        as_int(reports["shotTransitionBoundary"]["summary"].get("decorativeRepeatedRunMax")),
        as_int(reports["transitionExecutionReadiness"]["summary"].get("decorativeRepeatedRunMax")),
        as_int(reports["transitionCadence"]["summary"].get("decorativeRepeatedRunMax")),
    )


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    quality = reports["transitionQuality"]["summary"]
    shot = reports["shotTransitionBoundary"]["summary"]
    motivation = reports["transitionMotivation"]["summary"]
    pair = reports["transitionPairContinuity"]["summary"]
    readiness = reports["transitionExecutionReadiness"]["summary"]
    polish = reports["transitionPolishApplication"]["summary"]
    apply_report = reports["resolveTransitionApply"]["summary"]
    bridge = reports["bridgeSequenceApplication"]["summary"]
    lineage = reports["finalBlueprintLineage"]["summary"]
    cadence = reports["transitionCadence"]["summary"]
    cutpoint = reports["transitionCutpoint"]["summary"]

    boundary_names = (
        "transitionQuality",
        "shotTransitionBoundary",
        "transitionPairContinuity",
        "transitionExecutionReadiness",
        "transitionCadence",
    )
    visual_boundaries = max_summary_int(reports, "visualBoundaryCount", boundary_names)
    transition_rows = max_summary_int(reports, "transitionRowCount", boundary_names)
    motion_boundaries = max(
        as_int(quality.get("motionRowCount")),
        as_int(shot.get("motionBoundaryCount")),
        as_int(readiness.get("motionBoundaryCount")),
    )
    max_motion_allowed = as_int(cadence.get("maxMotionAllowed"), math.ceil(max(visual_boundaries, 1) * args.max_motion_share))
    max_transition_duration = as_float(readiness.get("maxTransitionDurationSeconds"))
    source_polish_rows = as_int(polish.get("sourcePolishRowCount"))
    important_boundaries = max(as_int(shot.get("importantBoundaryCount")), as_int(motivation.get("importantBoundaryCount")))
    expected_bridge_beats = as_int(bridge.get("expectedBeatClipCount"))
    applied_bridge_beats = as_int(bridge.get("appliedBeatClipCount"))
    repeated_run = max_decorative_run(reports)
    cutpoint_rows = as_int(cutpoint.get("transitionRowCount"))

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required transition microstructure reports are present and accepted",
        all(row["exists"] and row["accepted"] for row in reports.values()),
        {
            name: {
                "exists": row["exists"],
                "status": row["status"],
                "acceptedStatuses": row["acceptedStatuses"],
                "blockerCount": len(row["blockers"]),
            }
            for name, row in reports.items()
        },
    )
    add_check(
        checks,
        "Every adjacent visual boundary is audited as a real transition beat",
        visual_boundaries >= 1
        and transition_rows >= visual_boundaries
        and as_float(quality.get("transitionCoverageRatio")) >= 1.0
        and as_int(shot.get("auditedBoundaryCount")) == visual_boundaries
        and as_int(pair.get("auditedBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("auditedBoundaryCount")) == visual_boundaries
        and as_int(shot.get("blockedBoundaryCount")) == 0
        and as_int(pair.get("blockedBoundaryCount")) == 0
        and as_int(readiness.get("blockedBoundaryCount")) == 0,
        {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": transition_rows,
            "transitionCoverageRatio": quality.get("transitionCoverageRatio"),
            "shotAuditedBoundaryCount": shot.get("auditedBoundaryCount"),
            "pairAuditedBoundaryCount": pair.get("auditedBoundaryCount"),
            "readinessAuditedBoundaryCount": readiness.get("auditedBoundaryCount"),
            "shotBlockedBoundaryCount": shot.get("blockedBoundaryCount"),
            "pairBlockedBoundaryCount": pair.get("blockedBoundaryCount"),
            "readinessBlockedBoundaryCount": readiness.get("blockedBoundaryCount"),
        },
    )
    add_check(
        checks,
        "Each boundary has a landing point, BGM-only audio, title safety, handles, and pair continuity",
        as_int(readiness.get("recipeReadyBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("bgmHitBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("bgmOnlyBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("titleSafeBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("pairReadyBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("handleReadyBoundaryCount")) == visual_boundaries
        and as_int(motivation.get("motivatedBoundaryCount")) == as_int(motivation.get("visualBoundaryCount"))
        and as_int(pair.get("pairContinuityPayloadCount")) == visual_boundaries
        and as_int(pair.get("weakPairFitCount")) == 0
        and cutpoint_rows >= 1
        and as_int(cutpoint.get("readyCutpointRowCount")) == cutpoint_rows
        and as_int(cutpoint.get("blockedCutpointRowCount")) == 0
        and as_int(cutpoint.get("rowsWithLandingHold")) == cutpoint_rows
        and as_int(cutpoint.get("rowsWithHandles")) == cutpoint_rows
        and as_int(cutpoint.get("rowsWithBgmHit")) == cutpoint_rows
        and as_int(cutpoint.get("rowsWithTitleSubtitleQuietZone")) == cutpoint_rows
        and as_int(cutpoint.get("rowsWithBgmOnlyNoSourceVoice")) == cutpoint_rows,
        {
            "recipeReadyBoundaryCount": readiness.get("recipeReadyBoundaryCount"),
            "bgmHitBoundaryCount": readiness.get("bgmHitBoundaryCount"),
            "bgmOnlyBoundaryCount": readiness.get("bgmOnlyBoundaryCount"),
            "titleSafeBoundaryCount": readiness.get("titleSafeBoundaryCount"),
            "pairReadyBoundaryCount": readiness.get("pairReadyBoundaryCount"),
            "handleReadyBoundaryCount": readiness.get("handleReadyBoundaryCount"),
            "motivatedBoundaryCount": motivation.get("motivatedBoundaryCount"),
            "motivationVisualBoundaryCount": motivation.get("visualBoundaryCount"),
            "pairContinuityPayloadCount": pair.get("pairContinuityPayloadCount"),
            "weakPairFitCount": pair.get("weakPairFitCount"),
            "cutpointTransitionRowCount": cutpoint.get("transitionRowCount"),
            "readyCutpointRowCount": cutpoint.get("readyCutpointRowCount"),
            "blockedCutpointRowCount": cutpoint.get("blockedCutpointRowCount"),
            "cutpointRowsWithLandingHold": cutpoint.get("rowsWithLandingHold"),
            "cutpointRowsWithHandles": cutpoint.get("rowsWithHandles"),
            "cutpointRowsWithBgmHit": cutpoint.get("rowsWithBgmHit"),
            "cutpointRowsWithTitleSubtitleQuietZone": cutpoint.get("rowsWithTitleSubtitleQuietZone"),
            "cutpointRowsWithBgmOnlyNoSourceVoice": cutpoint.get("rowsWithBgmOnlyNoSourceVoice"),
        },
    )
    add_check(
        checks,
        "Motion and effect transitions are motivated and do not become a local crutch",
        as_int(quality.get("motionRowsWithEvidence")) == as_int(quality.get("motionRowCount"))
        and as_int(shot.get("motionSafeBoundaryCount")) == as_int(shot.get("motionBoundaryCount"))
        and as_int(readiness.get("motionReadyBoundaryCount")) == as_int(readiness.get("motionBoundaryCount"))
        and motion_boundaries <= max_motion_allowed
        and repeated_run < args.max_repeated_transition_run
        and max_transition_duration <= args.max_transition_duration_seconds,
        {
            "motionBoundaryCount": motion_boundaries,
            "maxMotionAllowed": max_motion_allowed,
            "qualityMotionRowsWithEvidence": quality.get("motionRowsWithEvidence"),
            "qualityMotionRowCount": quality.get("motionRowCount"),
            "shotMotionSafeBoundaryCount": shot.get("motionSafeBoundaryCount"),
            "shotMotionBoundaryCount": shot.get("motionBoundaryCount"),
            "readinessMotionReadyBoundaryCount": readiness.get("motionReadyBoundaryCount"),
            "readinessMotionBoundaryCount": readiness.get("motionBoundaryCount"),
            "decorativeRepeatedRunMax": repeated_run,
            "maxAllowedRepeatedTransitionRun": args.max_repeated_transition_run,
            "maxTransitionDurationSeconds": max_transition_duration,
            "maxAllowedTransitionDurationSeconds": args.max_transition_duration_seconds,
        },
    )
    add_check(
        checks,
        "Polish metadata survives onto the final candidate instead of staying as planning text",
        source_polish_rows >= visual_boundaries
        and as_int(polish.get("passedPolishRowCount")) == source_polish_rows
        and as_int(polish.get("blockedPolishRowCount")) == 0
        and as_int(polish.get("recipeReadyRowCount")) == source_polish_rows
        and as_int(polish.get("bgmHitRowCount")) == source_polish_rows
        and as_int(polish.get("bgmOnlyRowCount")) == source_polish_rows
        and as_int(polish.get("titleSafeRowCount")) == source_polish_rows
        and as_int(polish.get("pairReadyRowCount")) == source_polish_rows
        and as_int(polish.get("clipAnnotationRowCount")) == source_polish_rows
        and as_int(polish.get("markerRowCount")) == source_polish_rows,
        {
            "sourcePolishRowCount": source_polish_rows,
            "passedPolishRowCount": polish.get("passedPolishRowCount"),
            "blockedPolishRowCount": polish.get("blockedPolishRowCount"),
            "recipeReadyRowCount": polish.get("recipeReadyRowCount"),
            "bgmHitRowCount": polish.get("bgmHitRowCount"),
            "bgmOnlyRowCount": polish.get("bgmOnlyRowCount"),
            "titleSafeRowCount": polish.get("titleSafeRowCount"),
            "pairReadyRowCount": polish.get("pairReadyRowCount"),
            "clipAnnotationRowCount": polish.get("clipAnnotationRowCount"),
            "markerRowCount": polish.get("markerRowCount"),
        },
    )
    add_check(
        checks,
        "Important route or title jumps use materialized bridge beats and source audio stays out",
        important_boundaries == 0
        or (
            as_int(bridge.get("requiredSequenceRowCount")) >= 1
            and as_int(bridge.get("blockedSequenceRowCount")) == 0
            and as_int(bridge.get("missingBeatClipCount")) == 0
            and applied_bridge_beats >= expected_bridge_beats
            and as_int(bridge.get("sourceAudioLeakClipCount")) == 0
        ),
        {
            "importantBoundaryCount": important_boundaries,
            "requiredSequenceRowCount": bridge.get("requiredSequenceRowCount"),
            "blockedSequenceRowCount": bridge.get("blockedSequenceRowCount"),
            "expectedBeatClipCount": expected_bridge_beats,
            "appliedBeatClipCount": applied_bridge_beats,
            "missingBeatClipCount": bridge.get("missingBeatClipCount"),
            "sourceAudioLeakClipCount": bridge.get("sourceAudioLeakClipCount"),
        },
    )
    add_check(
        checks,
        "Resolve apply and final blueprint lineage prove visible effects are deliverable",
        as_int(apply_report.get("transitionApplyRowCount")) >= 1
        and as_int(apply_report.get("passedRowCount")) == as_int(apply_report.get("transitionApplyRowCount"))
        and as_int(apply_report.get("blockedRowCount")) == 0
        and as_int(apply_report.get("visibleEffectRowsWithApplyPath")) == as_int(apply_report.get("visibleEffectRowCount"))
        and as_int(apply_report.get("markerOnlyBlockedRowCount")) == 0
        and as_int(apply_report.get("decisionFieldRowCount")) == as_int(apply_report.get("transitionApplyRowCount"))
        and as_int(lineage.get("readyStageCount")) >= as_int(lineage.get("requiredMinimumReadyStages"), 5)
        and as_int(lineage.get("blockedReadyStageCount")) == 0
        and as_int(cadence.get("blockedCheckCount")) == 0,
        {
            "transitionApplyRowCount": apply_report.get("transitionApplyRowCount"),
            "passedApplyRowCount": apply_report.get("passedRowCount"),
            "blockedApplyRowCount": apply_report.get("blockedRowCount"),
            "visibleEffectRowsWithApplyPath": apply_report.get("visibleEffectRowsWithApplyPath"),
            "visibleEffectRowCount": apply_report.get("visibleEffectRowCount"),
            "markerOnlyBlockedRowCount": apply_report.get("markerOnlyBlockedRowCount"),
            "decisionFieldRowCount": apply_report.get("decisionFieldRowCount"),
            "readyStageCount": lineage.get("readyStageCount"),
            "requiredMinimumReadyStages": lineage.get("requiredMinimumReadyStages"),
            "blockedReadyStageCount": lineage.get("blockedReadyStageCount"),
            "cadenceBlockedCheckCount": cadence.get("blockedCheckCount"),
        },
    )

    blockers = [row for row in checks if row["status"] == "blocked"]
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "maxMotionShare": args.max_motion_share,
            "maxTransitionDurationSeconds": args.max_transition_duration_seconds,
            "maxRepeatedTransitionRun": args.max_repeated_transition_run,
            "reports": {name: row["path"] for name, row in reports.items()},
        },
        "summary": {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": transition_rows,
            "bgmHitBoundaryCount": readiness.get("bgmHitBoundaryCount"),
            "titleSafeBoundaryCount": readiness.get("titleSafeBoundaryCount"),
            "bgmOnlyBoundaryCount": readiness.get("bgmOnlyBoundaryCount"),
            "readyCutpointRowCount": cutpoint.get("readyCutpointRowCount"),
            "blockedCutpointRowCount": cutpoint.get("blockedCutpointRowCount"),
            "handleReadyBoundaryCount": readiness.get("handleReadyBoundaryCount"),
            "pairReadyBoundaryCount": readiness.get("pairReadyBoundaryCount"),
            "weakPairFitCount": pair.get("weakPairFitCount"),
            "motionBoundaryCount": motion_boundaries,
            "motionReadyBoundaryCount": readiness.get("motionReadyBoundaryCount"),
            "maxMotionAllowed": max_motion_allowed,
            "maxTransitionDurationSeconds": max_transition_duration,
            "decorativeRepeatedRunMax": repeated_run,
            "sourcePolishRowCount": source_polish_rows,
            "markerOnlyBlockedRowCount": apply_report.get("markerOnlyBlockedRowCount"),
            "visibleEffectRowsWithApplyPath": apply_report.get("visibleEffectRowsWithApplyPath"),
            "visibleEffectRowCount": apply_report.get("visibleEffectRowCount"),
            "importantBoundaryCount": important_boundaries,
            "expectedBridgeBeatClipCount": expected_bridge_beats,
            "appliedBridgeBeatClipCount": applied_bridge_beats,
            "checkCount": len(checks),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": len(blockers),
        },
        "reports": reports,
        "checks": checks,
        "blockers": [row["name"] for row in blockers],
        "warnings": [warning for row in reports.values() for warning in row["warnings"]],
        "policy": {
            "shotToShotLandingRequired": True,
            "bgmHitRequiredAtEveryBoundary": True,
            "bgmOnlyTransitionAudioRequired": True,
            "titleSafeTransitionWindowRequired": True,
            "weakPairFitRejected": True,
            "markerOnlyEffectsRejected": True,
            "importantJumpsNeedBridgeBeats": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Microstructure Contract Audit",
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
        lines.extend(["", "## Upstream Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"][:80])
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
            "- Reject a final candidate where adjacent clips have transition rows but no practical landing point.",
            "- Require BGM hits, BGM-only audio, title-safe windows, pair readiness, handles, and motivated continuity on every boundary.",
            "- Reject weak adjacent-pair fit and repeated or overlong motion effects used to hide bad shot choice.",
            "- Require bridge beats, Resolve apply evidence, and final blueprint lineage before trusting the cut.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit shot-to-shot transition microstructure from existing reports.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-motion-share", type=float, default=0.35)
    parser.add_argument("--max-transition-duration-seconds", type=float, default=0.9)
    parser.add_argument("--max-repeated-transition-run", type=int, default=4)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_microstructure_contract_audit.json", report)
    write_markdown(package_dir / "transition_microstructure_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
