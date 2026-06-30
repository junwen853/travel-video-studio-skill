#!/usr/bin/env python3
"""Audit whether transitions form reference-like scene arcs, not isolated effects."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionMotivation": ("transition_motivation_contract_audit.json", {"passed"}),
    "transitionPairContinuity": ("transition_pair_continuity_contract_audit.json", {"passed"}),
    "transitionExecutionReadiness": ("transition_execution_readiness_contract_audit.json", {"passed"}),
    "bridgeSequenceApplication": ("bridge_sequence_application_contract_audit.json", {"passed"}),
    "transitionCadence": ("transition_cadence_contract_audit.json", {"passed"}),
    "transitionMicrostructure": ("transition_microstructure_contract_audit.json", {"passed"}),
    "referenceSceneGrammar": ("reference_scene_grammar_contract_audit.json", {"passed"}),
    "timelineVariety": ("timeline_variety_contract_audit.json", {"passed"}),
}
SCENE_ARC_STRATEGIES = {"route_bridge_sequence", "motion_match_on_bgm_hit", "title_or_ending_handoff"}


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
        }
    return reports


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    motivation = reports["transitionMotivation"]["summary"]
    pair = reports["transitionPairContinuity"]["summary"]
    readiness = reports["transitionExecutionReadiness"]["summary"]
    bridge = reports["bridgeSequenceApplication"]["summary"]
    cadence = reports["transitionCadence"]["summary"]
    micro = reports["transitionMicrostructure"]["summary"]
    scene = reports["referenceSceneGrammar"]["summary"]
    variety = reports["timelineVariety"]["summary"]

    visual_boundaries = max(
        as_int(motivation.get("visualBoundaryCount")),
        as_int(pair.get("visualBoundaryCount")),
        as_int(readiness.get("visualBoundaryCount")),
        as_int(cadence.get("visualBoundaryCount")),
        as_int(micro.get("visualBoundaryCount")),
    )
    important_boundaries = max(as_int(motivation.get("importantBoundaryCount")), as_int(micro.get("importantBoundaryCount")), as_int(cadence.get("importantBoundaryCount")))
    bridge_required = as_int(bridge.get("requiredSequenceRowCount"))
    bridge_expected_beats = as_int(bridge.get("expectedBeatClipCount"))
    bridge_applied_beats = as_int(bridge.get("appliedBeatClipCount"))
    strategy_counts = motivation.get("motivationStrategyCounts") if isinstance(motivation.get("motivationStrategyCounts"), dict) else {}
    scene_arc_strategy_count = sum(as_int(strategy_counts.get(name)) for name in SCENE_ARC_STRATEGIES)
    motion_count = max(as_int(cadence.get("motionTransitionCount")), as_int(micro.get("motionBoundaryCount")))
    max_motion_allowed = max(as_int(cadence.get("maxMotionAllowed")), as_int(micro.get("maxMotionAllowed")))
    style_share = as_float(cadence.get("dominantStyleShare"))

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required transition scene-arc inputs are present and accepted",
        all(report["exists"] and report["accepted"] for report in reports.values()),
        {
            name: {
                "exists": report["exists"],
                "status": report["status"],
                "acceptedStatuses": report["acceptedStatuses"],
                "blockerCount": len(report["blockers"]),
            }
            for name, report in reports.items()
        },
    )
    add_check(
        checks,
        "Every shot boundary has pair continuity, motivation, BGM hit, title safety, and handles",
        visual_boundaries >= 1
        and as_int(pair.get("auditedBoundaryCount")) == visual_boundaries
        and as_int(pair.get("weakPairFitCount")) == 0
        and as_int(motivation.get("motivatedBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("bgmHitBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("titleSafeBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("handleReadyBoundaryCount")) == visual_boundaries
        and as_int(micro.get("blockedCheckCount")) == 0,
        {
            "visualBoundaryCount": visual_boundaries,
            "pairAuditedBoundaryCount": pair.get("auditedBoundaryCount"),
            "weakPairFitCount": pair.get("weakPairFitCount"),
            "motivatedBoundaryCount": motivation.get("motivatedBoundaryCount"),
            "bgmHitBoundaryCount": readiness.get("bgmHitBoundaryCount"),
            "titleSafeBoundaryCount": readiness.get("titleSafeBoundaryCount"),
            "handleReadyBoundaryCount": readiness.get("handleReadyBoundaryCount"),
            "microstructureBlockedCheckCount": micro.get("blockedCheckCount"),
        },
    )
    add_check(
        checks,
        "Important route, title, or timeline jumps become transition scene arcs with materialized bridge beats",
        important_boundaries == 0
        or (
            bridge_required >= 1
            and bridge_applied_beats >= max(bridge_expected_beats, args.min_bridge_beats)
            and as_int(bridge.get("missingBeatClipCount")) == 0
            and as_int(bridge.get("sourceAudioLeakClipCount")) == 0
            and scene_arc_strategy_count >= 1
        ),
        {
            "importantBoundaryCount": important_boundaries,
            "requiredBridgeSequenceRowCount": bridge_required,
            "expectedBridgeBeatClipCount": bridge_expected_beats,
            "appliedBridgeBeatClipCount": bridge_applied_beats,
            "minBridgeBeats": args.min_bridge_beats,
            "missingBeatClipCount": bridge.get("missingBeatClipCount"),
            "sourceAudioLeakClipCount": bridge.get("sourceAudioLeakClipCount"),
            "motivationStrategyCounts": strategy_counts,
            "sceneArcStrategyCount": scene_arc_strategy_count,
        },
    )
    add_check(
        checks,
        "Motion effects such as rotation or whip are allowed only as restrained motivated accents",
        motion_count <= max_motion_allowed
        and as_int(micro.get("motionReadyBoundaryCount")) == as_int(micro.get("motionBoundaryCount"))
        and as_int(cadence.get("decorativeRepeatedRunMax")) < args.max_repeated_style_run
        and as_int(micro.get("decorativeRepeatedRunMax")) < args.max_repeated_style_run
        and style_share <= args.max_dominant_style_share
        and as_float(micro.get("maxTransitionDurationSeconds")) <= args.max_transition_duration_seconds,
        {
            "motionTransitionCount": motion_count,
            "maxMotionAllowed": max_motion_allowed,
            "microMotionReadyBoundaryCount": micro.get("motionReadyBoundaryCount"),
            "microMotionBoundaryCount": micro.get("motionBoundaryCount"),
            "cadenceDecorativeRepeatedRunMax": cadence.get("decorativeRepeatedRunMax"),
            "microDecorativeRepeatedRunMax": micro.get("decorativeRepeatedRunMax"),
            "maxRepeatedStyleRun": args.max_repeated_style_run,
            "dominantStyle": cadence.get("dominantStyle"),
            "dominantStyleShare": style_share,
            "maxDominantStyleShare": args.max_dominant_style_share,
            "maxTransitionDurationSeconds": micro.get("maxTransitionDurationSeconds"),
            "allowedMaxTransitionDurationSeconds": args.max_transition_duration_seconds,
        },
    )
    add_check(
        checks,
        "Transition arcs support the film grammar instead of hiding weak shot choice",
        reports["referenceSceneGrammar"]["accepted"]
        and reports["timelineVariety"]["accepted"]
        and as_int(scene.get("chaptersBlocked")) == 0
        and as_int(variety.get("blockedCheckCount")) == 0
        and variety.get("movementReady") is True
        and variety.get("textureReady") is True
        and variety.get("payoffReady") is True
        and variety.get("aftertasteReady") is True,
        {
            "referenceSceneGrammarStatus": reports["referenceSceneGrammar"]["status"],
            "referenceSceneChaptersBlocked": scene.get("chaptersBlocked"),
            "timelineVarietyStatus": reports["timelineVariety"]["status"],
            "timelineVarietyBlockedCheckCount": variety.get("blockedCheckCount"),
            "movementReady": variety.get("movementReady"),
            "textureReady": variety.get("textureReady"),
            "payoffReady": variety.get("payoffReady"),
            "aftertasteReady": variety.get("aftertasteReady"),
        },
    )
    add_check(
        checks,
        "Scene-arc transition proof is non-destructive and downstream of final candidate lineage",
        reports["transitionCadence"]["accepted"]
        and reports["transitionMicrostructure"]["accepted"]
        and as_int(cadence.get("blockedCheckCount")) == 0
        and as_int(micro.get("markerOnlyBlockedRowCount")) == 0
        and as_int(micro.get("appliedBridgeBeatClipCount")) >= as_int(micro.get("expectedBridgeBeatClipCount")),
        {
            "transitionCadenceStatus": reports["transitionCadence"]["status"],
            "transitionMicrostructureStatus": reports["transitionMicrostructure"]["status"],
            "cadenceBlockedCheckCount": cadence.get("blockedCheckCount"),
            "markerOnlyBlockedRowCount": micro.get("markerOnlyBlockedRowCount"),
            "microExpectedBridgeBeatClipCount": micro.get("expectedBridgeBeatClipCount"),
            "microAppliedBridgeBeatClipCount": micro.get("appliedBridgeBeatClipCount"),
            "safety": safety(),
        },
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "minBridgeBeats": args.min_bridge_beats,
            "maxDominantStyleShare": args.max_dominant_style_share,
            "maxRepeatedStyleRun": args.max_repeated_style_run,
            "maxTransitionDurationSeconds": args.max_transition_duration_seconds,
            "reports": {name: row["path"] for name, row in reports.items()},
        },
        "summary": {
            "visualBoundaryCount": visual_boundaries,
            "importantBoundaryCount": important_boundaries,
            "sceneArcStrategyCount": scene_arc_strategy_count,
            "requiredBridgeSequenceRowCount": bridge_required,
            "expectedBridgeBeatClipCount": bridge_expected_beats,
            "appliedBridgeBeatClipCount": bridge_applied_beats,
            "motionTransitionCount": motion_count,
            "maxMotionAllowed": max_motion_allowed,
            "dominantStyle": cadence.get("dominantStyle"),
            "dominantStyleShare": style_share,
            "decorativeRepeatedRunMax": max(as_int(cadence.get("decorativeRepeatedRunMax")), as_int(micro.get("decorativeRepeatedRunMax"))),
            "maxTransitionDurationSeconds": micro.get("maxTransitionDurationSeconds"),
            "movementReady": variety.get("movementReady"),
            "textureReady": variety.get("textureReady"),
            "payoffReady": variety.get("payoffReady"),
            "aftertasteReady": variety.get("aftertasteReady"),
            "checkCount": len(checks),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": len(blockers),
        },
        "reports": reports,
        "checks": checks,
        "blockers": blockers,
        "warnings": [warning for row in reports.values() for warning in row["warnings"]],
        "policy": {
            "transitionSceneArcRequired": True,
            "singleEffectRouteJumpRejected": True,
            "rotationWhipRequiresMotionEvidence": True,
            "bridgeBeatsRequiredForImportantBoundaries": True,
            "bgmOnlyTitleSafeLandingRequired": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Scene Arc Contract Audit",
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
            "- Treat a polished travel transition as a scene arc: outgoing shot, bridge or motion reason, BGM hit, title/subtitle safety, and landing shot.",
            "- Allow rotation, whip, speed-ramp, or push only when route motion or bridge evidence supports it.",
            "- Require materialized 2-5 shot bridge beats for important route, title, timeline-gap, or ending transitions.",
            "- Reject isolated effects that hide weak shot choice or break reference-like travel grammar.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit reference-like transition scene arcs from existing transition reports.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-bridge-beats", type=int, default=2)
    parser.add_argument("--max-dominant-style-share", type=float, default=0.7)
    parser.add_argument("--max-repeated-style-run", type=int, default=4)
    parser.add_argument("--max-transition-duration-seconds", type=float, default=0.9)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_scene_arc_contract_audit.json", report)
    write_markdown(package_dir / "transition_scene_arc_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
