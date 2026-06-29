#!/usr/bin/env python3
"""Audit film-level transition cadence from existing transition gates."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionMotif": {
        "path": "transition_motif_plan/transition_motif_plan.json",
        "accepted": {"ready_with_transition_motif_plan"},
    },
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


def style_counts(reports: dict[str, dict[str, Any]]) -> dict[str, int]:
    shot = reports["shotTransitionBoundary"]["summary"]
    motif = reports["transitionMotif"]["summary"]
    for source in (shot, motif):
        counts = source.get("styleCounts") if isinstance(source.get("styleCounts"), dict) else {}
        if counts:
            return {str(k): as_int(v) for k, v in counts.items()}
    return {}


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    motif = reports["transitionMotif"]["summary"]
    quality = reports["transitionQuality"]["summary"]
    shot = reports["shotTransitionBoundary"]["summary"]
    motivation = reports["transitionMotivation"]["summary"]
    pair = reports["transitionPairContinuity"]["summary"]
    readiness = reports["transitionExecutionReadiness"]["summary"]
    bridge = reports["bridgeSequenceApplication"]["summary"]
    lineage = reports["finalBlueprintLineage"]["summary"]
    apply_report = reports["resolveTransitionApply"]["summary"]

    visual_boundaries = max(
        as_int(quality.get("visualBoundaryCount")),
        as_int(shot.get("visualBoundaryCount")),
        as_int(pair.get("visualBoundaryCount")),
        as_int(readiness.get("visualBoundaryCount")),
    )
    transition_rows = max(
        as_int(motif.get("transitionRowCount")),
        as_int(quality.get("transitionRowCount")),
        as_int(shot.get("transitionRowCount")),
        as_int(pair.get("transitionRowCount")),
        as_int(readiness.get("transitionRowCount")),
    )
    motion_count = max(as_int(quality.get("motionRowCount")), as_int(shot.get("motionBoundaryCount")), as_int(readiness.get("motionBoundaryCount")))
    repeated_run = max(
        as_int(motif.get("repeatedStyleRunMax")),
        as_int(quality.get("decorativeRepeatedRunMax")),
        as_int(shot.get("decorativeRepeatedRunMax")),
        as_int(motivation.get("decorativeRepeatedRunMax")),
        as_int(readiness.get("decorativeRepeatedRunMax")),
    )
    counts = style_counts(reports)
    dominant_style = None
    dominant_style_share = 0.0
    if counts and visual_boundaries:
        dominant_style, dominant_count = max(counts.items(), key=lambda item: item[1])
        dominant_style_share = round(dominant_count / visual_boundaries, 4)
    crafted_count = as_int(quality.get("craftedTransitionCount"))
    min_crafted = as_int(quality.get("minimumCraftedTransitionCount"))
    important_boundaries = max(as_int(shot.get("importantBoundaryCount")), as_int(motivation.get("importantBoundaryCount")))
    expected_bridge_beats = as_int(bridge.get("expectedBeatClipCount"))
    applied_bridge_beats = as_int(bridge.get("appliedBeatClipCount"))
    max_motion_allowed = math.ceil(max(visual_boundaries, 1) * args.max_motion_share)

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required transition reports are present and accepted",
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
        "Final candidate has transition coverage for every visual boundary",
        visual_boundaries > 0
        and transition_rows >= visual_boundaries
        and as_float(quality.get("transitionCoverageRatio")) >= 1.0
        and as_int(shot.get("auditedBoundaryCount")) == visual_boundaries
        and as_int(pair.get("auditedBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("auditedBoundaryCount")) == visual_boundaries,
        {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": transition_rows,
            "transitionCoverageRatio": quality.get("transitionCoverageRatio"),
            "shotAuditedBoundaryCount": shot.get("auditedBoundaryCount"),
            "pairAuditedBoundaryCount": pair.get("auditedBoundaryCount"),
            "readinessAuditedBoundaryCount": readiness.get("auditedBoundaryCount"),
        },
    )
    add_check(
        checks,
        "Cadence is crafted enough without becoming effect spam",
        crafted_count >= min_crafted
        and crafted_count > 0
        and motion_count <= max_motion_allowed
        and repeated_run < 4
        and bool(counts)
        and dominant_style_share <= args.max_dominant_style_share,
        {
            "craftedTransitionCount": crafted_count,
            "minimumCraftedTransitionCount": min_crafted,
            "motionTransitionCount": motion_count,
            "maxMotionAllowed": max_motion_allowed,
            "decorativeRepeatedRunMax": repeated_run,
            "styleCountsPresent": bool(counts),
            "styleCounts": counts,
            "dominantStyle": dominant_style,
            "dominantStyleShare": dominant_style_share,
            "maxDominantStyleShare": args.max_dominant_style_share,
        },
    )
    add_check(
        checks,
        "Motion transitions are motivated by route motion, pair continuity, BGM, and title safety",
        as_int(quality.get("motionRowsWithEvidence")) == as_int(quality.get("motionRowCount"))
        and as_int(shot.get("motionSafeBoundaryCount")) == as_int(shot.get("motionBoundaryCount"))
        and as_int(readiness.get("motionReadyBoundaryCount")) == as_int(readiness.get("motionBoundaryCount"))
        and as_int(pair.get("styleAllowedBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("bgmHitBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("titleSafeBoundaryCount")) == visual_boundaries,
        {
            "qualityMotionRowsWithEvidence": quality.get("motionRowsWithEvidence"),
            "qualityMotionRowCount": quality.get("motionRowCount"),
            "shotMotionSafeBoundaryCount": shot.get("motionSafeBoundaryCount"),
            "shotMotionBoundaryCount": shot.get("motionBoundaryCount"),
            "readinessMotionReadyBoundaryCount": readiness.get("motionReadyBoundaryCount"),
            "readinessMotionBoundaryCount": readiness.get("motionBoundaryCount"),
            "styleAllowedBoundaryCount": pair.get("styleAllowedBoundaryCount"),
            "bgmHitBoundaryCount": readiness.get("bgmHitBoundaryCount"),
            "titleSafeBoundaryCount": readiness.get("titleSafeBoundaryCount"),
        },
    )
    add_check(
        checks,
        "Important route/title/timeline boundaries have materialized bridge sequence beats",
        important_boundaries == 0
        or (
            reports["bridgeSequenceApplication"]["status"] == "passed"
            and as_int(bridge.get("requiredSequenceRowCount")) >= 1
            and applied_bridge_beats >= expected_bridge_beats
            and as_int(bridge.get("sourceAudioLeakClipCount")) == 0
        ),
        {
            "importantBoundaryCount": important_boundaries,
            "bridgeApplicationStatus": reports["bridgeSequenceApplication"]["status"],
            "requiredSequenceRowCount": bridge.get("requiredSequenceRowCount"),
            "expectedBeatClipCount": expected_bridge_beats,
            "appliedBeatClipCount": applied_bridge_beats,
            "sourceAudioLeakClipCount": bridge.get("sourceAudioLeakClipCount"),
        },
    )
    add_check(
        checks,
        "Latest final blueprint preserves the cadence chain and Resolve apply path",
        reports["finalBlueprintLineage"]["status"] == "passed"
        and reports["resolveTransitionApply"]["status"] == "passed"
        and as_int(lineage.get("readyStageCount")) >= as_int(lineage.get("requiredMinimumReadyStages"))
        and as_int(lineage.get("blockedReadyStageCount")) == 0
        and as_int(apply_report.get("blockedRowCount")) == 0
        and as_int(apply_report.get("markerOnlyBlockedRowCount")) == 0,
        {
            "finalBlueprintLineageStatus": reports["finalBlueprintLineage"]["status"],
            "readyStageCount": lineage.get("readyStageCount"),
            "requiredMinimumReadyStages": lineage.get("requiredMinimumReadyStages"),
            "blockedReadyStageCount": lineage.get("blockedReadyStageCount"),
            "resolveTransitionApplyStatus": reports["resolveTransitionApply"]["status"],
            "blockedResolveApplyRowCount": apply_report.get("blockedRowCount"),
            "markerOnlyBlockedRowCount": apply_report.get("markerOnlyBlockedRowCount"),
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
            "maxDominantStyleShare": args.max_dominant_style_share,
            "reports": {name: row["path"] for name, row in reports.items()},
        },
        "summary": {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": transition_rows,
            "craftedTransitionCount": crafted_count,
            "minimumCraftedTransitionCount": min_crafted,
            "motionTransitionCount": motion_count,
            "maxMotionAllowed": max_motion_allowed,
            "decorativeRepeatedRunMax": repeated_run,
            "dominantStyle": dominant_style,
            "dominantStyleShare": dominant_style_share,
            "importantBoundaryCount": important_boundaries,
            "requiredBridgeSequenceRowCount": bridge.get("requiredSequenceRowCount"),
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
            "filmLevelTransitionCadenceRequired": True,
            "bareConcatenationRejected": True,
            "effectSpamRejected": True,
            "repeatedTemplateChainRejected": True,
            "importantBoundariesNeedBridgeSequences": True,
            "motionTransitionsNeedRouteBgmTitleSafety": True,
            "finalBlueprintCadenceLineageRequired": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Cadence Contract Audit",
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
            "- Reject a final candidate that has only hard cuts or bare concatenation where crafted transitions are expected.",
            "- Reject overuse of motion effects, repeated templates, or a single dominant transition style.",
            "- Require route/title/timeline-gap boundaries to survive as materialized bridge sequences.",
            "- Require final blueprint lineage and Resolve apply-path evidence before trusting transition polish.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit film-level transition cadence from existing transition reports.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-motion-share", type=float, default=0.35)
    parser.add_argument("--max-dominant-style-share", type=float, default=0.7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_cadence_contract_audit.json", report)
    write_markdown(package_dir / "transition_cadence_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
