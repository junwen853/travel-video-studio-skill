#!/usr/bin/env python3
"""Audit whether transition decisions are backed by source-level edit evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionGrammar": (
        "transition_grammar_plan/transition_grammar_plan.json",
        {"ready_with_transition_grammar_plan"},
    ),
    "footageSelect": (
        "footage_select_plan/footage_select_plan.json",
        {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"},
    ),
    "creatorCut": ("creator_cut_plan/creator_cut_plan.json", {"ready_with_creator_cut_plan"}),
    "editRhythm": ("edit_rhythm_plan/edit_rhythm_plan.json", {"ready_with_edit_rhythm_plan"}),
    "transitionBridge": (
        "transition_bridge_plan/transition_bridge_plan.json",
        {"ready_with_bridge_evidence", "ready_no_interchapter_boundaries"},
    ),
}

IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
MOTION_STYLES = {
    "whip_pan",
    "rotation",
    "speed_ramp",
    "push_slide",
    "whip_pan_match",
    "rotation_match_cut",
    "speed_ramp_bridge",
}
MATCH_STYLES = {"match_cut", "whip_pan_match", "rotation_match_cut"}
BRIDGE_STYLES = {"insert_bridge_first", "speed_ramp_bridge", "short_dissolve_after_bridge"}
WEAK_TIERS = {"reject", "rejected", "reject_or_replace", "repair", "needs_repair", "weak_reject", "utility_only"}
GOOD_SOURCE_TIERS = {"hero_candidate", "main_story_candidate", "texture_bridge_candidate", "utility_context"}
BRIDGE_FUNCTIONS = {
    "route_movement",
    "lived_in_texture",
    "transition_bridge",
    "opening_hook",
    "ending_aftertaste",
    "title_background",
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


def clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


def normalize_style(value: Any) -> str:
    return clean(value).lower()


def list_value(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [clean(item) for item in value if clean(item)]


def source_name(value: Any) -> str:
    text = clean(value, 4000)
    return Path(text).name if text else ""


def source_keys(*values: Any) -> set[str]:
    out: set[str] = set()
    for value in values:
        text = clean(value, 4000)
        if not text:
            continue
        out.add(text)
        out.add(Path(text).name)
    return {item for item in out if item}


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
            "data": data,
        }
    return reports


def transition_rows(grammar: dict[str, Any]) -> list[dict[str, Any]]:
    rows = grammar.get("transitionRows") if isinstance(grammar.get("transitionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def map_rows(rows: list[dict[str, Any]], path_keys: tuple[str, ...], name_keys: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        keys: set[str] = set()
        for key in path_keys:
            keys |= source_keys(row.get(key))
        for key in name_keys:
            keys |= source_keys(row.get(key))
        for key in keys:
            lookup[key] = row
    return lookup


def source_lookups(reports: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    footage = reports["footageSelect"]["data"]
    creator = reports["creatorCut"]["data"]
    rhythm = reports["editRhythm"]["data"]
    footage_rows = footage.get("selectionRows") if isinstance(footage.get("selectionRows"), list) else []
    creator_rows = creator.get("shotRows") if isinstance(creator.get("shotRows"), list) else []
    rhythm_rows = rhythm.get("shotRows") if isinstance(rhythm.get("shotRows"), list) else []
    return {
        "footageSelect": map_rows(footage_rows, ("sourcePath", "path", "mediaPath"), ("sourceName", "name", "videoName")),
        "creatorCut": map_rows(creator_rows, ("sourcePath", "path", "mediaPath"), ("sourceName", "name", "videoName")),
        "editRhythm": map_rows(rhythm_rows, ("sourcePath", "path", "mediaPath"), ("sourceName", "name", "videoName")),
    }


def find_source_evidence(clip: dict[str, Any], lookups: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    keys = source_keys(clip.get("sourcePath"), clip.get("sourceName"), clip.get("name"))
    evidence: dict[str, Any] = {
        "sourceName": clean(clip.get("sourceName") or source_name(clip.get("sourcePath"))),
        "matchedInputs": [],
        "footageTier": None,
        "footageFunction": None,
        "creatorTier": clean(clip.get("editorialTier")),
        "creatorFunction": clean(clip.get("creatorFunction")),
        "rhythmRole": None,
        "riskReasons": [],
    }
    for source, lookup in lookups.items():
        match = next((lookup[key] for key in keys if key in lookup), None)
        if not match:
            continue
        evidence["matchedInputs"].append(source)
        if source == "footageSelect":
            evidence["footageTier"] = clean(match.get("selectionTier") or match.get("editorialTier") or match.get("tier"))
            evidence["footageFunction"] = clean(match.get("footageFunction") or match.get("function") or match.get("recommendedUse"))
        elif source == "creatorCut":
            evidence["creatorTier"] = clean(match.get("editorialTier") or evidence.get("creatorTier"))
            evidence["creatorFunction"] = clean(match.get("creatorFunction") or evidence.get("creatorFunction"))
            recipe = match.get("transitionRecipe") if isinstance(match.get("transitionRecipe"), dict) else {}
            evidence["creatorTransitionStyle"] = clean(recipe.get("style"))
        elif source == "editRhythm":
            evidence["rhythmRole"] = clean(match.get("rhythmRole") or match.get("shotFunction"))
            evidence["riskReasons"] = list_value(match.get("riskReasons"))
    return evidence


def bridge_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("boundaryRows") if isinstance(data.get("boundaryRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def bridge_plan_support(row: dict[str, Any], bridge_data: dict[str, Any]) -> dict[str, Any]:
    rows = bridge_rows(bridge_data)
    category = clean(row.get("boundaryCategory")).lower()
    timeline = as_float(row.get("timelineStartSeconds"), -1.0)
    matching_rows: list[dict[str, Any]] = []
    for bridge in rows:
        bridge_text = json.dumps(bridge, ensure_ascii=False).lower()
        bridge_time = as_float(
            bridge.get("timelineStartSeconds")
            or bridge.get("boundaryTimeSeconds")
            or bridge.get("afterChapterTimelineEndSeconds"),
            -9999.0,
        )
        if category and category.replace("_", " ") in bridge_text:
            matching_rows.append(bridge)
            continue
        if timeline >= 0 and bridge_time >= 0 and abs(timeline - bridge_time) <= 4.0:
            matching_rows.append(bridge)
    evidence_rows = [bridge for bridge in matching_rows if bridge.get("existingBridgeEvidence") or bridge.get("decision", {}).get("selectedLocalClips")]
    return {
        "bridgePlanStatus": bridge_data.get("status"),
        "candidateBoundaryRows": len(matching_rows),
        "rowsWithBridgeEvidence": len(evidence_rows),
        "hasBridgePlanEvidence": bool(evidence_rows),
        "fallbackAnyBridgeEvidence": any(bridge.get("existingBridgeEvidence") for bridge in rows),
    }


def grammar_bridge_signal(row: dict[str, Any]) -> bool:
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    return bool(
        recommendation.get("physicalBridgeEvidence") is True
        or list_value(signals.get("bridgeTerms"))
        or clean(decision.get("bridgeInsertSource"))
        or clean(decision.get("bridgeOrMotionBeatEvidence"))
    )


def has_motion_terms(row: dict[str, Any]) -> bool:
    signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
    return bool(list_value(signals.get("fromMotionTerms")) and list_value(signals.get("toMotionTerms")))


def has_match_terms(row: dict[str, Any]) -> bool:
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    return bool(list_value(recommendation.get("sharedMatchTerms")))


def good_source(evidence: dict[str, Any]) -> bool:
    tier = normalize_style(evidence.get("footageTier") or evidence.get("creatorTier"))
    function = normalize_style(evidence.get("creatorFunction") or evidence.get("footageFunction") or evidence.get("rhythmRole"))
    if tier in WEAK_TIERS:
        return False
    return bool(evidence.get("matchedInputs")) and (tier in GOOD_SOURCE_TIERS or function or evidence.get("rhythmRole"))


def bridge_source(evidence: dict[str, Any]) -> bool:
    text = " ".join(
        clean(evidence.get(key)).lower()
        for key in ("footageTier", "footageFunction", "creatorFunction", "rhythmRole", "creatorTransitionStyle")
    )
    return any(term in text for term in BRIDGE_FUNCTIONS) or "bridge" in text or "movement" in text or "texture" in text


def row_issues(
    row: dict[str, Any],
    from_evidence: dict[str, Any],
    to_evidence: dict[str, Any],
    bridge_support: dict[str, Any],
    reports: dict[str, dict[str, Any]],
) -> list[str]:
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    style = normalize_style(recommendation.get("recommendedTransitionType"))
    category = clean(row.get("boundaryCategory")).lower()
    issues: list[str] = []
    if row.get("status") == "needs_bridge_insert" or style == "insert_bridge_first":
        issues.append("unresolved_bridge_insert_transition")
    if not good_source(from_evidence):
        issues.append("outgoing_clip_missing_good_source_selection_or_creator_evidence")
    if not good_source(to_evidence):
        issues.append("landing_clip_missing_good_source_selection_or_creator_evidence")
    if normalize_style(from_evidence.get("creatorTier") or from_evidence.get("footageTier")) in WEAK_TIERS:
        issues.append("outgoing_clip_weak_or_rejected_tier")
    if normalize_style(to_evidence.get("creatorTier") or to_evidence.get("footageTier")) in WEAK_TIERS:
        issues.append("landing_clip_weak_or_rejected_tier")
    has_bridge = grammar_bridge_signal(row) or bridge_support.get("hasBridgePlanEvidence") or bridge_support.get("fallbackAnyBridgeEvidence")
    if category in IMPORTANT_CATEGORIES and not has_bridge:
        issues.append("important_boundary_missing_source_bridge_coverage")
    if style in MOTION_STYLES:
        if not has_motion_terms(row):
            issues.append("motion_transition_missing_two_sided_source_motion_terms")
        if not (has_bridge or bridge_source(from_evidence) or bridge_source(to_evidence)):
            issues.append("motion_transition_missing_bridge_or_route_movement_source")
        if from_evidence.get("riskReasons") or to_evidence.get("riskReasons"):
            issues.append("motion_transition_uses_rhythm_risk_clip")
    if style in MATCH_STYLES and not (has_match_terms(row) or bridge_source(from_evidence) or bridge_source(to_evidence)):
        issues.append("match_transition_missing_shared_visual_or_source_function")
    if style in BRIDGE_STYLES and not has_bridge:
        issues.append("bridge_style_missing_bridge_plan_or_grammar_evidence")
    if category in {"chapter_boundary", "timeline_gap"} and reports["transitionBridge"]["status"] == "needs_bridge_selection":
        issues.append("transition_bridge_plan_still_needs_selection")
    return issues


def audited_rows(
    rows: list[dict[str, Any]],
    lookups: dict[str, dict[str, dict[str, Any]]],
    bridge_data: dict[str, Any],
    reports: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
        style = normalize_style(recommendation.get("recommendedTransitionType"))
        from_clip = row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}
        to_clip = row.get("toClip") if isinstance(row.get("toClip"), dict) else {}
        from_evidence = find_source_evidence(from_clip, lookups)
        to_evidence = find_source_evidence(to_clip, lookups)
        bridge_support = bridge_plan_support(row, bridge_data)
        issues = row_issues(row, from_evidence, to_evidence, bridge_support, reports)
        audited.append(
            {
                "rowIndex": row.get("rowIndex"),
                "boundaryCategory": row.get("boundaryCategory"),
                "timelineStartSeconds": row.get("timelineStartSeconds"),
                "style": style,
                "fromSourceName": from_evidence.get("sourceName"),
                "toSourceName": to_evidence.get("sourceName"),
                "fromEvidence": from_evidence,
                "toEvidence": to_evidence,
                "bridgeSupport": bridge_support,
                "hasGrammarBridgeSignal": grammar_bridge_signal(row),
                "hasTwoSidedMotionTerms": has_motion_terms(row),
                "hasSharedMatchTerms": has_match_terms(row),
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
    rows = transition_rows(reports["transitionGrammar"]["data"])
    lookups = source_lookups(reports)
    audited = audited_rows(rows, lookups, reports["transitionBridge"]["data"], reports)
    blocked_rows = [row for row in audited if row["status"] == "blocked"]
    important_rows = [row for row in audited if row.get("boundaryCategory") in IMPORTANT_CATEGORIES]
    motion_rows = [row for row in audited if row.get("style") in MOTION_STYLES]
    bridge_ready_rows = [
        row
        for row in audited
        if row.get("hasGrammarBridgeSignal")
        or row.get("bridgeSupport", {}).get("hasBridgePlanEvidence")
        or row.get("bridgeSupport", {}).get("fallbackAnyBridgeEvidence")
    ]
    motion_source_ready_rows = [
        row
        for row in audited
        if row in bridge_ready_rows
        or bridge_source(row.get("fromEvidence") or {})
        or bridge_source(row.get("toEvidence") or {})
    ]

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required source-coverage inputs are present and accepted",
        all(report["exists"] and report["accepted"] for report in reports.values()),
        {
            name: {
                "exists": report["exists"],
                "status": report["status"],
                "acceptedStatuses": report["acceptedStatuses"],
            }
            for name, report in reports.items()
        },
    )
    add_check(
        checks,
        "Every transition row has outgoing and landing source evidence from footage, creator, or rhythm planning",
        bool(rows) and len(blocked_rows) == 0,
        {
            "transitionRowCount": len(rows),
            "blockedRowCount": len(blocked_rows),
            "blockedRows": blocked_rows[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Important boundaries have bridge-source coverage before effects are approved",
        not important_rows
        or all(
            row.get("hasGrammarBridgeSignal")
            or row.get("bridgeSupport", {}).get("hasBridgePlanEvidence")
            or row.get("bridgeSupport", {}).get("fallbackAnyBridgeEvidence")
            for row in important_rows
        ),
        {
            "importantBoundaryCount": len(important_rows),
            "importantRowsWithBridgeCoverage": sum(1 for row in important_rows if row in bridge_ready_rows),
            "transitionBridgeStatus": reports["transitionBridge"]["status"],
        },
    )
    add_check(
        checks,
        "Motion transitions have two-sided movement and usable route/bridge source material",
        all(row.get("hasTwoSidedMotionTerms") and row in motion_source_ready_rows for row in motion_rows),
        {
            "motionTransitionCount": len(motion_rows),
            "motionRowsWithBridgeCoverage": sum(1 for row in motion_rows if row in motion_source_ready_rows),
        },
    )

    blocked_checks = [check for check in checks if check["status"] == "blocked"]
    issue_counts: dict[str, int] = {}
    style_counts: dict[str, int] = {}
    for row in audited:
        style = clean(row.get("style"))
        style_counts[style] = style_counts.get(style, 0) + 1
        for issue in row.get("issues") or []:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blocked_checks and not blocked_rows else "blocked",
        "packageDir": str(package_dir),
        "inputs": {"reports": {name: report["path"] for name, report in reports.items()}},
        "summary": {
            "transitionRowCount": len(rows),
            "readySourceCoverageRowCount": len(audited) - len(blocked_rows),
            "blockedSourceCoverageRowCount": len(blocked_rows),
            "importantBoundaryCount": len(important_rows),
            "motionTransitionCount": len(motion_rows),
            "bridgeReadyRowCount": len(bridge_ready_rows),
            "motionSourceReadyRowCount": len(motion_source_ready_rows),
            "issueCounts": issue_counts,
            "styleCounts": style_counts,
            "passedCheckCount": len(checks) - len(blocked_checks),
            "blockedCheckCount": len(blocked_checks),
        },
        "checks": checks,
        "auditedRows": audited,
        "blockers": [check["name"] for check in blocked_checks]
        + [
            f"row {row.get('rowIndex')} {row.get('style')}: {', '.join(row.get('issues') or [])}"
            for row in blocked_rows[: args.max_blocked_rows_in_report]
        ],
        "warnings": [],
        "policy": {
            "sourceCoverageBeforeTransitionEffects": True,
            "importantBoundariesRequireBridgeSourceCoverage": True,
            "motionEffectsRequireTwoSidedMotionAndBridgeSource": True,
            "matchCutsRequireSharedVisualOrSourceFunction": True,
            "weakOrRejectedClipsCannotBeHiddenByTransitions": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Source Coverage Contract Audit",
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
                f"- From: `{row.get('fromSourceName')}` evidence=`{', '.join(row.get('fromEvidence', {}).get('matchedInputs') or [])}`",
                f"- To: `{row.get('toSourceName')}` evidence=`{', '.join(row.get('toEvidence', {}).get('matchedInputs') or [])}`",
                f"- Bridge ready: `{row.get('hasGrammarBridgeSignal') or row.get('bridgeSupport', {}).get('hasBridgePlanEvidence') or row.get('bridgeSupport', {}).get('fallbackAnyBridgeEvidence')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition source coverage before effects are trusted.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_source_coverage_contract_audit.json", report)
    write_markdown(package_dir / "transition_source_coverage_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
