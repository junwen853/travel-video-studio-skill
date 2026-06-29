#!/usr/bin/env python3
"""Audit whether every transition has pair-level visual match evidence."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionGrammar": ("transition_grammar_plan/transition_grammar_plan.json", {"ready_with_transition_grammar_plan"}),
    "transitionPairContinuity": ("transition_pair_continuity_contract_audit.json", {"passed"}),
    "transitionExecutionReadiness": ("transition_execution_readiness_contract_audit.json", {"passed"}),
    "transitionMicrostructure": ("transition_microstructure_contract_audit.json", {"passed"}),
    "transitionSceneArc": ("transition_scene_arc_contract_audit.json", {"passed"}),
    "transitionEffectPalette": ("transition_effect_palette_contract_audit.json", {"passed"}),
}
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
MATCH_STYLES = {"match_cut", "whip_pan_match", "rotation_match_cut"}
DISSOLVE_STYLES = {"short_dissolve", "short_dissolve_after_bridge", "mood_dissolve"}
BRIDGE_STYLES = {"insert_bridge_first", "speed_ramp_bridge"}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
REJECT_TIERS = {"reject", "rejected", "repair", "needs_repair", "weak_reject"}


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


def normalize_style(value: Any) -> str:
    return str(value or "").strip().lower()


def list_value(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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


def transition_rows(grammar: dict[str, Any]) -> list[dict[str, Any]]:
    rows = grammar.get("transitionRows") if isinstance(grammar.get("transitionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def clip_tier(row: dict[str, Any], key: str) -> str:
    clip = row.get(key) if isinstance(row.get(key), dict) else {}
    return str(clip.get("editorialTier") or "").strip().lower()


def evidence_families(row: dict[str, Any]) -> set[str]:
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    category = str(row.get("boundaryCategory") or "")
    families: set[str] = set()
    if list_value(recommendation.get("sharedMatchTerms")):
        families.add("visual_match")
    if recommendation.get("physicalBridgeEvidence") is True or list_value(signals.get("bridgeTerms")):
        families.add("physical_bridge")
    if list_value(signals.get("fromMotionTerms")) and list_value(signals.get("toMotionTerms")):
        families.add("two_sided_motion")
    if list_value(signals.get("moodTerms")) or category in {"title_boundary", "ending_transition"}:
        families.add("mood_or_title")
    if category == "same_chapter_cut":
        families.add("local_continuity")
    if str(decision.get("bgmPhraseCue") or "").strip():
        families.add("bgm_phrase")
    return families


def row_issues(row: dict[str, Any]) -> list[str]:
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    category = str(row.get("boundaryCategory") or "")
    style = normalize_style(recommendation.get("recommendedTransitionType"))
    families = evidence_families(row)
    issues: list[str] = []

    if not style:
        issues.append("missing_recommended_transition_type")
    if row.get("status") == "needs_bridge_insert" or style == "insert_bridge_first":
        issues.append("bridge_insert_unresolved")
    if not families:
        issues.append("missing_visual_match_or_bridge_evidence")
    if style in MOTION_STYLES:
        if "two_sided_motion" not in families:
            issues.append("motion_transition_without_two_sided_motion_evidence")
        if "physical_bridge" not in families:
            issues.append("motion_transition_without_physical_route_bridge_evidence")
    if style in MATCH_STYLES and not ({"visual_match", "two_sided_motion", "physical_bridge"} & families):
        issues.append("match_cut_without_visual_motion_or_bridge_match")
    if style in DISSOLVE_STYLES and not ({"mood_or_title", "visual_match", "physical_bridge"} & families):
        issues.append("dissolve_without_mood_title_visual_or_bridge_reason")
    if style == "straight_cut" and category in IMPORTANT_CATEGORIES and not ({"visual_match", "physical_bridge", "mood_or_title"} & families):
        issues.append("important_boundary_straight_cut_without_match_or_bridge")
    if category in {"chapter_boundary", "timeline_gap"} and "physical_bridge" not in families:
        issues.append("route_or_timeline_boundary_without_physical_bridge")
    if clip_tier(row, "fromClip") in REJECT_TIERS or clip_tier(row, "toClip") in REJECT_TIERS:
        issues.append("transition_uses_reject_or_repair_tier_clip")
    return issues


def audited_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
        style = normalize_style(recommendation.get("recommendedTransitionType"))
        families = sorted(evidence_families(row))
        issues = row_issues(row)
        audited.append(
            {
                "rowIndex": row.get("rowIndex"),
                "boundaryCategory": row.get("boundaryCategory"),
                "style": style,
                "fromSourceName": (row.get("fromClip") or {}).get("sourceName") if isinstance(row.get("fromClip"), dict) else None,
                "toSourceName": (row.get("toClip") or {}).get("sourceName") if isinstance(row.get("toClip"), dict) else None,
                "evidenceFamilies": families,
                "sharedMatchTerms": list_value(recommendation.get("sharedMatchTerms")),
                "fromMotionTerms": list_value((row.get("signals") or {}).get("fromMotionTerms")) if isinstance(row.get("signals"), dict) else [],
                "toMotionTerms": list_value((row.get("signals") or {}).get("toMotionTerms")) if isinstance(row.get("signals"), dict) else [],
                "bridgeTerms": list_value((row.get("signals") or {}).get("bridgeTerms")) if isinstance(row.get("signals"), dict) else [],
                "moodTerms": list_value((row.get("signals") or {}).get("moodTerms")) if isinstance(row.get("signals"), dict) else [],
                "status": "passed" if not issues else "blocked",
                "issues": issues,
            }
        )
    return audited


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    grammar_data = reports["transitionGrammar"]["data"]
    rows = transition_rows(grammar_data)
    audited = audited_rows(rows)

    pair_summary = reports["transitionPairContinuity"]["summary"]
    readiness_summary = reports["transitionExecutionReadiness"]["summary"]
    micro_summary = reports["transitionMicrostructure"]["summary"]
    scene_arc_summary = reports["transitionSceneArc"]["summary"]
    palette_summary = reports["transitionEffectPalette"]["summary"]
    visual_boundaries = max(
        len(rows),
        as_int(pair_summary.get("visualBoundaryCount")),
        as_int(readiness_summary.get("visualBoundaryCount")),
        as_int(micro_summary.get("visualBoundaryCount")),
        as_int(scene_arc_summary.get("visualBoundaryCount")),
        as_int(palette_summary.get("visualBoundaryCount")),
    )

    blocked_rows = [row for row in audited if row["status"] == "blocked"]
    motion_rows = [row for row in audited if row.get("style") in MOTION_STYLES]
    important_rows = [row for row in audited if row.get("boundaryCategory") in IMPORTANT_CATEGORIES]
    bridge_or_scene_rows = [
        row for row in important_rows if "physical_bridge" in row.get("evidenceFamilies", []) or row.get("boundaryCategory") in {"title_boundary", "ending_transition"}
    ]
    max_motion_allowed = min(
        max(as_int(palette_summary.get("maxMotionAllowed")), math.ceil(max(visual_boundaries, 1) * args.max_motion_share)),
        math.ceil(max(visual_boundaries, 1) * args.max_motion_share),
    )

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required visual-match inputs are present and accepted",
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
        "Every adjacent transition row has visual, bridge, motion, mood, title, local, or BGM evidence",
        visual_boundaries >= 1 and len(rows) >= visual_boundaries and len(blocked_rows) == 0,
        {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": len(rows),
            "passedRowCount": len(audited) - len(blocked_rows),
            "blockedRowCount": len(blocked_rows),
            "blockedRows": blocked_rows[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Motion transitions are rare and carry two-sided movement plus route bridge evidence",
        len(motion_rows) <= max_motion_allowed
        and all("two_sided_motion" in row.get("evidenceFamilies", []) and "physical_bridge" in row.get("evidenceFamilies", []) for row in motion_rows),
        {
            "motionTransitionCount": len(motion_rows),
            "maxMotionAllowed": max_motion_allowed,
            "motionRows": motion_rows[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Important chapter, timeline, title, and ending boundaries have bridge or scene-hand-off logic",
        not important_rows or len(bridge_or_scene_rows) == len(important_rows),
        {
            "importantBoundaryCount": len(important_rows),
            "importantBridgeOrSceneHandoffCount": len(bridge_or_scene_rows),
            "sceneArcStatus": reports["transitionSceneArc"]["status"],
            "sceneArcStrategyCount": scene_arc_summary.get("sceneArcStrategyCount"),
        },
    )
    add_check(
        checks,
        "Downstream transition contracts agree with the visual-match decisions",
        as_int(pair_summary.get("blockedBoundaryCount")) == 0
        and as_int(pair_summary.get("weakPairFitCount")) == 0
        and as_int(readiness_summary.get("pairReadyBoundaryCount")) == as_int(readiness_summary.get("visualBoundaryCount"))
        and as_int(micro_summary.get("pairReadyBoundaryCount")) == as_int(micro_summary.get("visualBoundaryCount"))
        and as_int(palette_summary.get("blockedCheckCount")) == 0,
        {
            "pairContinuitySummary": pair_summary,
            "executionReadinessSummary": readiness_summary,
            "microstructureSummary": micro_summary,
            "effectPaletteSummary": palette_summary,
        },
    )

    blocked_checks = [check for check in checks if check["status"] == "blocked"]
    row_issue_labels: list[str] = []
    for row in blocked_rows[: args.max_blocked_rows_in_report]:
        row_issue_labels.append(f"row {row.get('rowIndex')} {row.get('style')}: {', '.join(row.get('issues') or [])}")

    family_counts: dict[str, int] = {}
    style_counts: dict[str, int] = {}
    for row in audited:
        style = str(row.get("style") or "")
        style_counts[style] = style_counts.get(style, 0) + 1
        for family in row.get("evidenceFamilies") or []:
            family_counts[family] = family_counts.get(family, 0) + 1

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blocked_checks else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "maxMotionShare": args.max_motion_share,
            "reports": {name: report["path"] for name, report in reports.items()},
        },
        "summary": {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": len(rows),
            "visualMatchReadyRowCount": len(audited) - len(blocked_rows),
            "blockedRowCount": len(blocked_rows),
            "motionTransitionCount": len(motion_rows),
            "maxMotionAllowed": max_motion_allowed,
            "importantBoundaryCount": len(important_rows),
            "importantBridgeOrSceneHandoffCount": len(bridge_or_scene_rows),
            "evidenceFamilyCounts": family_counts,
            "styleCounts": style_counts,
            "passedCheckCount": len(checks) - len(blocked_checks),
            "blockedCheckCount": len(blocked_checks),
        },
        "checks": checks,
        "auditedRows": audited,
        "blockers": [check["name"] for check in blocked_checks] + row_issue_labels,
        "warnings": [],
        "policy": {
            "pairLevelVisualMatchRequired": True,
            "motionRequiresTwoSidedMotionAndBridge": True,
            "importantBoundariesRequireBridgeOrSceneHandoff": True,
            "matchCutsRequireConcreteSharedVisualTerms": True,
            "effectsCannotHideRejectOrRepairClips": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Visual Match Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Checks",
    ]
    for check in report["checks"]:
        lines.extend(["", f"- `{check['status']}` {check['name']}"])
    if report["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Audited Rows"])
    for row in report["auditedRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('style')}`",
                f"- Status: `{row.get('status')}`",
                f"- Boundary: `{row.get('boundaryCategory')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Evidence: `{', '.join(row.get('evidenceFamilies') or [])}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit visual match evidence for every transition row.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-motion-share", type=float, default=0.3)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_visual_match_contract_audit.json", report)
    write_markdown(package_dir / "transition_visual_match_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
