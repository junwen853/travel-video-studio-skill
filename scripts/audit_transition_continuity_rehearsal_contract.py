#!/usr/bin/env python3
"""Audit whether approved transitions rehearse as one continuous film language."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionStoryboard": ("transition_storyboard_contract_audit.json", {"passed"}),
    "transitionSensoryContinuity": ("transition_sensory_continuity_contract_audit.json", {"passed"}),
    "transitionAuditionQuality": ("transition_audition_quality_contract_audit.json", {"passed"}),
    "transitionAuditionVisualProof": ("transition_audition_visual_proof_contract_audit.json", {"passed"}),
    "transitionAuditionRoleIntegrity": ("transition_audition_role_integrity_contract_audit.json", {"passed"}),
    "transitionBreathingRoom": ("transition_breathing_room_contract_audit.json", {"passed"}),
    "transitionEffectPalette": ("transition_effect_palette_contract_audit.json", {"passed"}),
    "transitionCadence": ("transition_cadence_contract_audit.json", {"passed"}),
    "referenceTransitionProfile": ("reference_transition_profile_contract_audit.json", {"passed"}),
    "sceneFlowArc": ("scene_flow_arc_contract_audit.json", {"passed"}),
    "finalCutSmoothness": ("final_cut_smoothness_contract_audit.json", {"passed"}),
}
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
HIGH_IMPACT_PURPOSES = {"route_move", "time_jump", "title_reveal", "scenic_breath", "payoff_handoff", "ending_aftertaste", "bgm_handoff"}
CALM_BUFFER_PURPOSES = {"texture_bridge", "scenic_breath", "same_scene_continuity"}
STOPWORDS = {
    "the",
    "and",
    "with",
    "from",
    "into",
    "onto",
    "shot",
    "clip",
    "video",
    "source",
    "landing",
    "outgoing",
    "bridge",
    "scene",
    "motion",
    "beat",
    "stable",
    "readable",
    "transition",
    "mp4",
    "mov",
    "m4v",
    "avi",
    "mxf",
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


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


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


def storyboard_rows(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    data = storyboard.get("data") if isinstance(storyboard.get("data"), dict) else {}
    rows = data.get("auditedRows") if isinstance(data.get("auditedRows"), list) else []
    return sorted([row for row in rows if isinstance(row, dict)], key=lambda row: as_int(row.get("rowIndex"), -1))


def tokens(value: Any) -> set[str]:
    text = clean(value).lower()
    raw = re.findall(r"[\w\u4e00-\u9fff]{2,}", text)
    return {word for word in raw if word not in STOPWORDS and not word.isdigit()}


def has_anchor_overlap(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, list[str]]:
    left_text = " ".join(
        clean(left.get(key))
        for key in ("toSourceName", "landingShotEvidence", "bridgeOrMotionBeatEvidence")
        if clean(left.get(key))
    )
    right_text = " ".join(
        clean(right.get(key))
        for key in ("fromSourceName", "outgoingShotEvidence", "bridgeOrMotionBeatEvidence")
        if clean(right.get(key))
    )
    left_source = clean(left.get("toSourceName"))
    right_source = clean(right.get("fromSourceName"))
    if left_source and right_source and left_source == right_source:
        return True, [left_source]
    overlap = sorted(tokens(left_text) & tokens(right_text))
    return len(overlap) >= 1, overlap[:8]


def purpose_run(rows: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    if not rows:
        return 0, []
    runs: list[dict[str, Any]] = []
    best = 1
    current = clean(rows[0].get("storyboardPurpose"))
    start = 0
    for index, row in enumerate(rows[1:], start=1):
        purpose = clean(row.get("storyboardPurpose"))
        if purpose == current:
            best = max(best, index - start + 1)
            continue
        runs.append({"purpose": current, "startRowIndex": rows[start].get("rowIndex"), "endRowIndex": rows[index - 1].get("rowIndex"), "length": index - start})
        current = purpose
        start = index
    runs.append({"purpose": current, "startRowIndex": rows[start].get("rowIndex"), "endRowIndex": rows[-1].get("rowIndex"), "length": len(rows) - start})
    return best, runs


def motion_style(row: dict[str, Any]) -> bool:
    style = clean(row.get("style")).lower()
    purpose = clean(row.get("storyboardPurpose")).lower()
    return style in MOTION_STYLES or purpose == "bgm_handoff"


def high_energy_row(row: dict[str, Any]) -> bool:
    purpose = clean(row.get("storyboardPurpose")).lower()
    if purpose in CALM_BUFFER_PURPOSES and not bool(row.get("motionStyle")):
        return False
    return bool(row.get("motionStyle")) or bool(row.get("importantBoundary")) or purpose in HIGH_IMPACT_PURPOSES


def calm_buffer_row(row: dict[str, Any]) -> bool:
    purpose = clean(row.get("storyboardPurpose")).lower()
    return not bool(row.get("motionStyle")) and purpose in CALM_BUFFER_PURPOSES


def rehearsed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        issues: list[str] = []
        if row.get("status") != "passed":
            issues.append("storyboard_row_not_passed")
        if not clean(row.get("storyboardPurpose")):
            issues.append("missing_storyboard_purpose")
        if not clean(row.get("outgoingShotEvidence")):
            issues.append("missing_outgoing_evidence")
        if not clean(row.get("landingShotEvidence")):
            issues.append("missing_landing_evidence")
        if row.get("importantBoundary") is True and not clean(row.get("transitionAuditionEvidence")):
            issues.append("important_boundary_missing_audition")
        audited.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "storyboardStatus": row.get("status"),
                "storyboardPurpose": row.get("storyboardPurpose"),
                "style": row.get("style"),
                "importantBoundary": row.get("importantBoundary"),
                "fromSourceName": row.get("fromSourceName"),
                "toSourceName": row.get("toSourceName"),
                "outgoingShotEvidence": row.get("outgoingShotEvidence"),
                "bridgeOrMotionBeatEvidence": row.get("bridgeOrMotionBeatEvidence"),
                "landingShotEvidence": row.get("landingShotEvidence"),
                "transitionAuditionEvidence": row.get("transitionAuditionEvidence"),
                "motionStyle": motion_style(row),
                "highEnergy": False,
                "calmBuffer": False,
                "issues": issues,
            }
        )
    for row in audited:
        row["highEnergy"] = high_energy_row(row)
        row["calmBuffer"] = calm_buffer_row(row)
    return audited


def rehearsed_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left, right in zip(rows, rows[1:]):
        anchor_ready, overlap = has_anchor_overlap(left, right)
        issues: list[str] = []
        if not anchor_ready:
            issues.append("landing_to_next_outgoing_anchor_missing")
        if left.get("motionStyle") and right.get("motionStyle"):
            issues.append("adjacent_motion_or_bgm_handoff_without_stable_buffer")
        if left.get("importantBoundary") and right.get("importantBoundary"):
            issues.append("back_to_back_important_boundaries_without_scene_breath")
        pairs.append(
            {
                "fromRowIndex": left.get("rowIndex"),
                "toRowIndex": right.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "leftPurpose": left.get("storyboardPurpose"),
                "rightPurpose": right.get("storyboardPurpose"),
                "leftStyle": left.get("style"),
                "rightStyle": right.get("style"),
                "anchorOverlap": overlap,
                "leftLanding": left.get("landingShotEvidence"),
                "rightOutgoing": right.get("outgoingShotEvidence"),
                "issues": issues,
            }
        )
    return pairs


def energy_windows(rows: list[dict[str, Any]], window_size: int) -> list[dict[str, Any]]:
    if window_size <= 1:
        return []
    windows: list[dict[str, Any]] = []
    for start in range(0, max(0, len(rows) - window_size + 1)):
        window = rows[start : start + window_size]
        high_rows = [row.get("rowIndex") for row in window if row.get("highEnergy")]
        calm_rows = [row.get("rowIndex") for row in window if row.get("calmBuffer")]
        issues: list[str] = []
        if len(high_rows) > 1 and not calm_rows:
            issues.append("high_energy_window_without_calm_buffer")
        windows.append(
            {
                "startRowIndex": window[0].get("rowIndex"),
                "endRowIndex": window[-1].get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "highEnergyRowIndices": high_rows,
                "calmBufferRowIndices": calm_rows,
                "issues": issues,
            }
        )
    return windows


def energy_aftercare(rows: list[dict[str, Any]], window_size: int) -> list[dict[str, Any]]:
    if window_size <= 0:
        return []
    checks: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not row.get("highEnergy"):
            continue
        following = rows[index + 1 : index + 1 + window_size]
        if not following:
            continue
        calm_rows = [next_row.get("rowIndex") for next_row in following if next_row.get("calmBuffer")]
        issues: list[str] = []
        if not calm_rows:
            issues.append("high_energy_transition_missing_calm_buffer_aftercare")
        checks.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "storyboardPurpose": row.get("storyboardPurpose"),
                "style": row.get("style"),
                "lookaheadRowIndices": [next_row.get("rowIndex") for next_row in following],
                "calmBufferRowIndices": calm_rows,
                "issues": issues,
            }
        )
    return checks


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    rows = rehearsed_rows(storyboard_rows(reports["transitionStoryboard"]))
    pairs = rehearsed_pairs(rows)
    windows = energy_windows(rows, args.energy_cooldown_window)
    aftercare = energy_aftercare(rows, args.energy_cooldown_window)
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    blocked_pairs = [pair for pair in pairs if pair["status"] == "blocked"]
    blocked_windows = [window for window in windows if window["status"] == "blocked"]
    blocked_aftercare = [check for check in aftercare if check["status"] == "blocked"]
    run_max, runs = purpose_run(rows)
    repeated_high_impact_runs = [
        row
        for row in runs
        if row.get("purpose") in HIGH_IMPACT_PURPOSES and as_int(row.get("length")) > args.max_high_impact_purpose_run
    ]
    storyboard_summary = reports["transitionStoryboard"]["summary"]
    sensory_summary = reports["transitionSensoryContinuity"]["summary"]
    breathing_summary = reports["transitionBreathingRoom"]["summary"]
    scene_summary = reports["sceneFlowArc"]["summary"]
    smooth_summary = reports["finalCutSmoothness"]["summary"]
    palette_summary = reports["transitionEffectPalette"]["summary"]
    cadence_summary = reports["transitionCadence"]["summary"]

    blockers: list[str] = []
    if not rows:
        blockers.append("transition storyboard has no rehearsable rows")
    if not all(report["exists"] and report["accepted"] for report in reports.values()):
        blockers.append("required upstream transition rehearsal reports are missing or blocked")
    blockers.extend(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[: args.max_blocked_rows_in_report])
    blockers.extend(
        f"pair {pair.get('fromRowIndex')}->{pair.get('toRowIndex')}: {', '.join(pair.get('issues') or [])}"
        for pair in blocked_pairs[: args.max_blocked_rows_in_report]
    )
    if repeated_high_impact_runs:
        blockers.append("high-impact storyboard purpose repeats too long without a quieter continuity beat")
    if blocked_windows:
        blockers.append("transition energy curve stacks high-energy rows without a calm buffer")
    if blocked_aftercare:
        blockers.append("high-energy transitions lack a calm buffer within the cooldown window")
    if as_int(storyboard_summary.get("storyboardReadyRowCount")) < len(rows):
        blockers.append("storyboard summary does not show every row ready")
    if as_int(sensory_summary.get("readySensoryContinuityRowCount")) < len(rows):
        blockers.append("sensory-continuity summary does not show every row ready")
    if as_int(breathing_summary.get("motionSpacingViolationCount")) > 0:
        blockers.append("transition breathing-room audit still reports motion spacing violations")
    if as_int(scene_summary.get("blockedCheckCount")) > 0 or as_int(smooth_summary.get("blockedCheckCount")) > 0:
        blockers.append("scene-flow or final-cut smoothness still has blocked checks")
    if as_int(palette_summary.get("decorativeRepeatedRunMax")) >= args.max_decorative_repeated_run:
        blockers.append("transition effect palette still has repeated decorative runs")

    summary = {
        "transitionRowCount": len(rows),
        "rehearsalReadyRowCount": len(rows) - len(blocked_rows),
        "blockedRehearsalRowCount": len(blocked_rows),
        "adjacentPairCount": len(pairs),
        "rehearsalReadyPairCount": len(pairs) - len(blocked_pairs),
        "blockedAdjacentPairCount": len(blocked_pairs),
        "rowsWithMotionStyle": sum(1 for row in rows if row.get("motionStyle")),
        "highEnergyRowCount": sum(1 for row in rows if row.get("highEnergy")),
        "calmBufferRowCount": sum(1 for row in rows if row.get("calmBuffer")),
        "adjacentMotionPairCount": sum(1 for pair in pairs if "adjacent_motion_or_bgm_handoff_without_stable_buffer" in (pair.get("issues") or [])),
        "backToBackImportantPairCount": sum(1 for pair in pairs if "back_to_back_important_boundaries_without_scene_breath" in (pair.get("issues") or [])),
        "landingToNextOutgoingAnchorReadyPairCount": sum(1 for pair in pairs if "landing_to_next_outgoing_anchor_missing" not in (pair.get("issues") or [])),
        "energyCooldownWindowSize": args.energy_cooldown_window,
        "energyWindowCount": len(windows),
        "highEnergyWindowViolationCount": len(blocked_windows),
        "motionAftercareViolationCount": len(blocked_aftercare),
        "purposeRunMax": run_max,
        "highImpactPurposeRunViolationCount": len(repeated_high_impact_runs),
        "storyboardReadyRowCount": storyboard_summary.get("storyboardReadyRowCount"),
        "readySensoryContinuityRowCount": sensory_summary.get("readySensoryContinuityRowCount"),
        "transitionBreathingRoomStatus": reports["transitionBreathingRoom"]["status"],
        "motionSpacingViolationCount": breathing_summary.get("motionSpacingViolationCount"),
        "transitionEffectPaletteStatus": reports["transitionEffectPalette"]["status"],
        "decorativeRepeatedRunMax": palette_summary.get("decorativeRepeatedRunMax"),
        "transitionCadenceStatus": reports["transitionCadence"]["status"],
        "motionTransitionCount": cadence_summary.get("motionTransitionCount"),
        "sceneFlowArcStatus": reports["sceneFlowArc"]["status"],
        "sceneFlowBlockedCheckCount": scene_summary.get("blockedCheckCount"),
        "finalCutSmoothnessStatus": reports["finalCutSmoothness"]["status"],
        "finalCutBlockedCheckCount": smooth_summary.get("blockedCheckCount"),
        "blockedCheckCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "maxHighImpactPurposeRun": args.max_high_impact_purpose_run,
            "maxDecorativeRepeatedRun": args.max_decorative_repeated_run,
            "energyCooldownWindow": args.energy_cooldown_window,
            "reports": {name: report["path"] for name, report in reports.items()},
        },
        "summary": summary,
        "reports": reports,
        "auditedRows": rows,
        "auditedPairs": pairs,
        "energyWindows": windows,
        "energyAftercare": aftercare,
        "purposeRuns": runs,
        "blockers": blockers,
        "warnings": [warning for report in reports.values() for warning in report["warnings"]],
        "policy": {
            "wholeFilmTransitionRehearsalRequired": True,
            "landingMustCarryIntoNextOutgoing": True,
            "motionEffectsNeedStableBuffer": True,
            "highEnergyWindowsNeedCalmBuffer": True,
            "highEnergyTransitionsNeedAftercare": True,
            "backToBackImportantBoundariesRejected": True,
            "highImpactPurposeRunsRejected": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Continuity Rehearsal Contract Audit",
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
    lines.extend(["", "## Adjacent Pair Rehearsal"])
    for pair in report.get("auditedPairs", [])[:160]:
        lines.extend(
            [
                "",
                f"### Pair {pair.get('fromRowIndex')} -> {pair.get('toRowIndex')} - `{pair.get('status')}`",
                f"- Purposes: `{pair.get('leftPurpose')}` -> `{pair.get('rightPurpose')}`",
                f"- Styles: `{pair.get('leftStyle')}` -> `{pair.get('rightStyle')}`",
                f"- Anchor overlap: `{', '.join(pair.get('anchorOverlap') or [])}`",
                f"- Landing -> outgoing: `{pair.get('leftLanding')}` -> `{pair.get('rightOutgoing')}`",
            ]
        )
        if pair.get("issues"):
            lines.append(f"- Issues: `{', '.join(pair.get('issues') or [])}`")
    lines.extend(["", "## Energy Cooldown"])
    for window in report.get("energyWindows", [])[:80]:
        if window.get("status") == "passed":
            continue
        lines.extend(
            [
                "",
                f"### Rows {window.get('startRowIndex')} -> {window.get('endRowIndex')} - `{window.get('status')}`",
                f"- High-energy rows: `{', '.join(str(item) for item in window.get('highEnergyRowIndices') or [])}`",
                f"- Calm buffers: `{', '.join(str(item) for item in window.get('calmBufferRowIndices') or [])}`",
                f"- Issues: `{', '.join(window.get('issues') or [])}`",
            ]
        )
    for check in report.get("energyAftercare", [])[:80]:
        if check.get("status") == "passed":
            continue
        lines.extend(
            [
                "",
                f"### Aftercare Row {check.get('rowIndex')} - `{check.get('status')}`",
                f"- Purpose/style: `{check.get('storyboardPurpose')}` / `{check.get('style')}`",
                f"- Lookahead rows: `{', '.join(str(item) for item in check.get('lookaheadRowIndices') or [])}`",
                f"- Calm buffers: `{', '.join(str(item) for item in check.get('calmBufferRowIndices') or [])}`",
                f"- Issues: `{', '.join(check.get('issues') or [])}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Contract",
            "- Rehearse transition rows as a continuous film, not isolated approved boundaries.",
            "- The landing shot of one boundary must carry into the outgoing evidence of the next boundary.",
            "- Motion accents, rotations, whip pans, speed ramps, and BGM handoffs need stable visual buffer rows.",
            "- High-energy transition windows need texture, scenic breath, or same-scene continuity before another high-energy beat.",
            "- Important route/title/time-jump boundaries cannot stack back-to-back without scene breath.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition continuity rehearsal across adjacent approved storyboard rows.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-high-impact-purpose-run", type=int, default=3)
    parser.add_argument("--max-decorative-repeated-run", type=int, default=4)
    parser.add_argument("--energy-cooldown-window", type=int, default=3)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(Path(args.package_dir), args)
    package_dir = Path(args.package_dir).expanduser().resolve()
    write_json(package_dir / "transition_continuity_rehearsal_contract_audit.json", report)
    write_markdown(package_dir / "transition_continuity_rehearsal_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
