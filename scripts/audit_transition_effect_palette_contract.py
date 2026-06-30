#!/usr/bin/env python3
"""Audit whether transition effects form a reference-like palette, not spam."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionMotif": ("transition_motif_plan/transition_motif_plan.json", {"ready_with_transition_motif_plan"}),
    "transitionCadence": ("transition_cadence_contract_audit.json", {"passed"}),
    "transitionMicrostructure": ("transition_microstructure_contract_audit.json", {"passed"}),
    "transitionSceneArc": ("transition_scene_arc_contract_audit.json", {"passed"}),
    "transitionQuality": ("transition_quality_contract_audit.json", {"passed"}),
    "transitionPairContinuity": ("transition_pair_continuity_contract_audit.json", {"passed"}),
    "transitionExecutionReadiness": ("transition_execution_readiness_contract_audit.json", {"passed"}),
    "timelineVariety": ("timeline_variety_contract_audit.json", {"passed"}),
    "finalSourceUsage": ("final_source_usage_contract_audit.json", {"passed"}),
    "creatorCutApplication": ("creator_cut_application_contract_audit.json", {"passed"}),
}
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
REFERENCE_MOTIFS = {"simple_continuity", "visual_match", "mood_dissolve", "physical_route_bridge", "title_clean_reveal", "motivated_motion"}


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


def dict_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): as_int(count) for key, count in value.items() if as_int(count) > 0}


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    motif = reports["transitionMotif"]["summary"]
    cadence = reports["transitionCadence"]["summary"]
    micro = reports["transitionMicrostructure"]["summary"]
    scene_arc = reports["transitionSceneArc"]["summary"]
    quality = reports["transitionQuality"]["summary"]
    pair = reports["transitionPairContinuity"]["summary"]
    readiness = reports["transitionExecutionReadiness"]["summary"]
    variety = reports["timelineVariety"]["summary"]
    source = reports["finalSourceUsage"]["summary"]
    creator = reports["creatorCutApplication"]["summary"]

    visual_boundaries = max(
        as_int(cadence.get("visualBoundaryCount")),
        as_int(micro.get("visualBoundaryCount")),
        as_int(scene_arc.get("visualBoundaryCount")),
        as_int(quality.get("visualBoundaryCount")),
        as_int(pair.get("visualBoundaryCount")),
        as_int(readiness.get("visualBoundaryCount")),
    )
    transition_rows = max(
        as_int(motif.get("transitionRowCount")),
        as_int(cadence.get("transitionRowCount")),
        as_int(micro.get("transitionRowCount")),
        as_int(quality.get("transitionRowCount")),
        as_int(pair.get("transitionRowCount")),
        as_int(readiness.get("transitionRowCount")),
    )
    motif_counts = dict_counts(motif.get("motifCounts"))
    style_counts = dict_counts(motif.get("styleCounts")) or dict_counts(cadence.get("styleCounts"))
    motif_family_count = len([name for name, count in motif_counts.items() if count > 0 and name in REFERENCE_MOTIFS])
    min_palette_family_count = 1 if visual_boundaries <= 1 else (2 if visual_boundaries <= 4 else args.min_palette_family_count)
    dominant_motif = motif.get("dominantMotif")
    dominant_motif_share = as_float(motif.get("dominantMotifShare"))
    if motif_counts and visual_boundaries and (not dominant_motif or dominant_motif_share == 0.0):
        dominant_motif, dominant_count = max(motif_counts.items(), key=lambda item: item[1])
        dominant_motif_share = round(dominant_count / visual_boundaries, 4)
    motion_count = max(
        as_int(cadence.get("motionTransitionCount")),
        as_int(micro.get("motionBoundaryCount")),
        as_int(scene_arc.get("motionTransitionCount")),
        as_int(quality.get("motionRowCount")),
        as_int(readiness.get("motionBoundaryCount")),
        sum(count for style, count in style_counts.items() if style in MOTION_STYLES),
    )
    max_motion_allowed = min(
        max(as_int(cadence.get("maxMotionAllowed")), as_int(scene_arc.get("maxMotionAllowed")), math.ceil(max(visual_boundaries, 1) * args.max_motion_share)),
        math.ceil(max(visual_boundaries, 1) * args.max_motion_share),
    )
    decorative_run = max(
        as_int(motif.get("repeatedStyleRunMax")),
        as_int(cadence.get("decorativeRepeatedRunMax")),
        as_int(micro.get("decorativeRepeatedRunMax")),
        as_int(scene_arc.get("decorativeRepeatedRunMax")),
        as_int(readiness.get("decorativeRepeatedRunMax")),
    )
    important_boundaries = max(as_int(cadence.get("importantBoundaryCount")), as_int(scene_arc.get("importantBoundaryCount")))
    physical_bridge_count = as_int(motif_counts.get("physical_route_bridge")) + as_int(scene_arc.get("sceneArcStrategyCount"))
    clean_or_match_count = as_int(motif_counts.get("simple_continuity")) + as_int(motif_counts.get("visual_match"))

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required transition palette inputs are present and accepted",
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
        "Reference-style palette has enough motif families for the number of boundaries",
        visual_boundaries >= 1
        and transition_rows >= visual_boundaries
        and motif_family_count >= min_palette_family_count
        and clean_or_match_count >= 1
        and (important_boundaries == 0 or physical_bridge_count >= 1),
        {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": transition_rows,
            "motifCounts": motif_counts,
            "styleCounts": style_counts,
            "motifFamilyCount": motif_family_count,
            "minimumPaletteFamilyCount": min_palette_family_count,
            "cleanOrMatchCount": clean_or_match_count,
            "importantBoundaryCount": important_boundaries,
            "physicalBridgeOrSceneArcCount": physical_bridge_count,
        },
    )
    add_check(
        checks,
        "Effect palette is restrained instead of dominant, repeated, or template-like",
        dominant_motif_share <= args.max_dominant_motif_share
        and as_float(cadence.get("dominantStyleShare")) <= args.max_dominant_style_share
        and decorative_run < args.max_repeated_style_run
        and as_int(motif.get("blockedMotifRowCount")) == 0
        and as_int(motif.get("repairRowCount")) == 0
        and as_int(quality.get("forbiddenHitCount")) == 0,
        {
            "dominantMotif": dominant_motif,
            "dominantMotifShare": dominant_motif_share,
            "maxDominantMotifShare": args.max_dominant_motif_share,
            "dominantStyle": cadence.get("dominantStyle"),
            "dominantStyleShare": cadence.get("dominantStyleShare"),
            "maxDominantStyleShare": args.max_dominant_style_share,
            "decorativeRepeatedRunMax": decorative_run,
            "maxRepeatedStyleRun": args.max_repeated_style_run,
            "blockedMotifRowCount": motif.get("blockedMotifRowCount"),
            "repairRowCount": motif.get("repairRowCount"),
            "forbiddenHitCount": quality.get("forbiddenHitCount"),
        },
    )
    add_check(
        checks,
        "Motion effects are rare motivated accents with BGM, title safety, handles, and apply proof",
        motion_count <= max_motion_allowed
        and as_int(micro.get("motionReadyBoundaryCount")) == as_int(micro.get("motionBoundaryCount"))
        and as_int(readiness.get("motionReadyBoundaryCount")) == as_int(readiness.get("motionBoundaryCount"))
        and as_int(pair.get("styleAllowedBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("bgmHitBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("titleSafeBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("handleReadyBoundaryCount")) == visual_boundaries
        and as_int(micro.get("markerOnlyBlockedRowCount")) == 0
        and as_float(micro.get("maxTransitionDurationSeconds")) <= args.max_transition_duration_seconds,
        {
            "motionTransitionCount": motion_count,
            "maxMotionAllowed": max_motion_allowed,
            "maxMotionShare": args.max_motion_share,
            "microMotionReadyBoundaryCount": micro.get("motionReadyBoundaryCount"),
            "microMotionBoundaryCount": micro.get("motionBoundaryCount"),
            "readinessMotionReadyBoundaryCount": readiness.get("motionReadyBoundaryCount"),
            "readinessMotionBoundaryCount": readiness.get("motionBoundaryCount"),
            "styleAllowedBoundaryCount": pair.get("styleAllowedBoundaryCount"),
            "bgmHitBoundaryCount": readiness.get("bgmHitBoundaryCount"),
            "titleSafeBoundaryCount": readiness.get("titleSafeBoundaryCount"),
            "handleReadyBoundaryCount": readiness.get("handleReadyBoundaryCount"),
            "markerOnlyBlockedRowCount": micro.get("markerOnlyBlockedRowCount"),
            "maxTransitionDurationSeconds": micro.get("maxTransitionDurationSeconds"),
            "allowedMaxTransitionDurationSeconds": args.max_transition_duration_seconds,
        },
    )
    add_check(
        checks,
        "Palette supports shot choice, creator cut, and whole-film variety instead of rescuing weak footage",
        reports["finalSourceUsage"]["accepted"]
        and reports["creatorCutApplication"]["accepted"]
        and reports["timelineVariety"]["accepted"]
        and as_int(source.get("blockerCount")) == 0
        and as_int(source.get("rejectOrRepairActiveClipCount")) == 0
        and as_int(creator.get("blockedCheckCount")) == 0
        and as_int(variety.get("blockedCheckCount")) == 0
        and variety.get("movementReady") is True
        and variety.get("textureReady") is True
        and variety.get("payoffReady") is True
        and variety.get("aftertasteReady") is True,
        {
            "finalSourceUsageStatus": reports["finalSourceUsage"]["status"],
            "sourceBlockerCount": source.get("blockerCount"),
            "rejectOrRepairActiveClipCount": source.get("rejectOrRepairActiveClipCount"),
            "creatorCutApplicationStatus": reports["creatorCutApplication"]["status"],
            "creatorBlockedCheckCount": creator.get("blockedCheckCount"),
            "timelineVarietyStatus": reports["timelineVariety"]["status"],
            "timelineBlockedCheckCount": variety.get("blockedCheckCount"),
            "movementReady": variety.get("movementReady"),
            "textureReady": variety.get("textureReady"),
            "payoffReady": variety.get("payoffReady"),
            "aftertasteReady": variety.get("aftertasteReady"),
        },
    )
    add_check(
        checks,
        "Scene-arc and microstructure gates prove the palette lands musically and safely",
        reports["transitionSceneArc"]["accepted"]
        and reports["transitionMicrostructure"]["accepted"]
        and as_int(scene_arc.get("blockedCheckCount")) == 0
        and as_int(micro.get("blockedCheckCount")) == 0
        and as_int(scene_arc.get("appliedBridgeBeatClipCount")) >= as_int(scene_arc.get("expectedBridgeBeatClipCount"))
        and as_int(micro.get("appliedBridgeBeatClipCount")) >= as_int(micro.get("expectedBridgeBeatClipCount")),
        {
            "transitionSceneArcStatus": reports["transitionSceneArc"]["status"],
            "sceneArcBlockedCheckCount": scene_arc.get("blockedCheckCount"),
            "sceneArcExpectedBridgeBeatClipCount": scene_arc.get("expectedBridgeBeatClipCount"),
            "sceneArcAppliedBridgeBeatClipCount": scene_arc.get("appliedBridgeBeatClipCount"),
            "transitionMicrostructureStatus": reports["transitionMicrostructure"]["status"],
            "microBlockedCheckCount": micro.get("blockedCheckCount"),
            "microExpectedBridgeBeatClipCount": micro.get("expectedBridgeBeatClipCount"),
            "microAppliedBridgeBeatClipCount": micro.get("appliedBridgeBeatClipCount"),
        },
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "maxMotionShare": args.max_motion_share,
            "maxDominantMotifShare": args.max_dominant_motif_share,
            "maxDominantStyleShare": args.max_dominant_style_share,
            "maxRepeatedStyleRun": args.max_repeated_style_run,
            "maxTransitionDurationSeconds": args.max_transition_duration_seconds,
            "minPaletteFamilyCount": args.min_palette_family_count,
            "reports": {name: row["path"] for name, row in reports.items()},
        },
        "summary": {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": transition_rows,
            "motifFamilyCount": motif_family_count,
            "minimumPaletteFamilyCount": min_palette_family_count,
            "motifCounts": motif_counts,
            "styleCounts": style_counts,
            "dominantMotif": dominant_motif,
            "dominantMotifShare": dominant_motif_share,
            "dominantStyle": cadence.get("dominantStyle"),
            "dominantStyleShare": cadence.get("dominantStyleShare"),
            "motionTransitionCount": motion_count,
            "maxMotionAllowed": max_motion_allowed,
            "decorativeRepeatedRunMax": decorative_run,
            "importantBoundaryCount": important_boundaries,
            "physicalBridgeOrSceneArcCount": physical_bridge_count,
            "cleanOrMatchCount": clean_or_match_count,
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
        "warnings": [warning for report in reports.values() for warning in report["warnings"]],
        "policy": {
            "referenceTransitionEffectPaletteRequired": True,
            "motionEffectsAreAccentsOnly": True,
            "dominantMotifChainRejected": True,
            "repeatedTemplateEffectsRejected": True,
            "cleanCutsAndMatchCutsRemainPartOfPalette": True,
            "bridgeOrSceneArcRequiredForImportantBoundaries": True,
            "weakFootageCannotBeHiddenByEffects": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Effect Palette Contract Audit",
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
            "- Keep motion effects such as rotation, whip, push, and speed ramp as rare motivated accents.",
            "- Preserve clean cuts, visual match cuts, mood dissolves, physical bridge inserts, and title reveals as part of the film palette.",
            "- Reject a dominant motif chain, repeated template effects, or flashy transitions that hide weak footage.",
            "- Important route, title, timeline-gap, and ending boundaries need bridge or scene-arc evidence before Resolve apply.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit reference-like transition effect palette from existing reports.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-motion-share", type=float, default=0.3)
    parser.add_argument("--max-dominant-motif-share", type=float, default=0.65)
    parser.add_argument("--max-dominant-style-share", type=float, default=0.7)
    parser.add_argument("--max-repeated-style-run", type=int, default=4)
    parser.add_argument("--max-transition-duration-seconds", type=float, default=0.9)
    parser.add_argument("--min-palette-family-count", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_effect_palette_contract_audit.json", report)
    write_markdown(package_dir / "transition_effect_palette_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
