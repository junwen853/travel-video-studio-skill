#!/usr/bin/env python3
"""Audit transition choreography rows for reference-like shot flow."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


READY_STATUSES = {"ready_with_transition_choreography_plan"}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
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


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("choreographyRows") if isinstance(plan.get("choreographyRows"), list) else []
    return [row for row in raw if isinstance(row, dict)]


def has_role(row: dict[str, Any], role: str) -> bool:
    beats = row.get("threeBeatChoreography") if isinstance(row.get("threeBeatChoreography"), list) else []
    return any(isinstance(beat, dict) and beat.get("role") == role and beat.get("action") for beat in beats)


def row_issues(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    category = str(row.get("boundaryCategory") or "")
    important = bool(row.get("importantBoundary")) or category in IMPORTANT_CATEGORIES
    style = str(row.get("sourceTransitionStyle") or "")
    evidence = row.get("motionEvidence") if isinstance(row.get("motionEvidence"), dict) else {}
    caption = row.get("captionAndTitlePolicy") if isinstance(row.get("captionAndTitlePolicy"), dict) else {}
    bgm = row.get("bgmChoreography") if isinstance(row.get("bgmChoreography"), dict) else {}
    beats = row.get("threeBeatChoreography") if isinstance(row.get("threeBeatChoreography"), list) else []
    if row.get("status") != "ready_with_transition_choreography":
        issues.append("choreography_row_not_ready")
    if len(beats) < 3:
        issues.append("missing_three_beat_choreography")
    if important and not (has_role(row, "outgoing") and has_role(row, "bridge_or_motion") and has_role(row, "landing")):
        issues.append("important_boundary_missing_outgoing_bridge_landing_beats")
    if important and row.get("choreographyFamily") == "bridge_required_before_effect":
        issues.append("important_boundary_still_waiting_for_bridge")
    if style in MOTION_STYLES:
        motion_ok = (
            evidence.get("motionEffectAllowedByGrammar") is True
            and (evidence.get("physicalBridgeEvidence") is True or evidence.get("hasRouteBridgeTerms") is True or evidence.get("hasTwoSidedMotion") is True)
        )
        if not motion_ok:
            issues.append("motion_style_without_source_motion_or_bridge_evidence")
    if style == "rotation" and as_int(row.get("intensity")) > 1:
        issues.append("rotation_not_subtle")
    if as_int(row.get("intensity")) >= 3:
        issues.append("transition_intensity_too_high_for_reference_style")
    if bgm.get("target") != "cut_or_effect_on_bgm_phrase_hit" or as_float(bgm.get("hitToleranceSeconds"), 99.0) > 0.35:
        issues.append("missing_bgm_hit_choreography")
    if caption.get("avoidTitleCollision") is not True or as_float(caption.get("quietZoneBeforeSeconds"), 0.0) < 0.25:
        issues.append("missing_caption_title_quiet_zone")
    if row.get("forbiddenHits"):
        issues.append("forbidden_template_or_flash_transition_language")
    return issues


def max_run(values: list[str]) -> int:
    best = 0
    current = 0
    previous = None
    for value in values:
        if value == previous:
            current += 1
        else:
            current = 1
            previous = value
        best = max(best, current)
    return best


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    plan_path = package_dir / "transition_choreography_plan" / "transition_choreography_plan.json"
    plan = load_json(plan_path) or {}
    plan_rows = rows(plan)
    audited: list[dict[str, Any]] = []
    for row in plan_rows:
        issues = row_issues(row)
        audited.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "boundaryCategory": row.get("boundaryCategory"),
                "choreographyFamily": row.get("choreographyFamily"),
                "sourceTransitionStyle": row.get("sourceTransitionStyle"),
                "intensity": row.get("intensity"),
                "importantBoundary": row.get("importantBoundary"),
                "issues": issues,
            }
        )
    blocked = [row for row in audited if row.get("status") == "blocked"]
    families = [str(row.get("choreographyFamily") or "") for row in plan_rows]
    family_counts: dict[str, int] = {}
    for family in families:
        family_counts[family] = family_counts.get(family, 0) + 1
    dominant_share = max(family_counts.values()) / len(families) if families else 0.0
    blockers: list[str] = []
    if not plan_path.exists():
        blockers.append("missing transition_choreography_plan/transition_choreography_plan.json")
    if plan.get("status") not in READY_STATUSES:
        blockers.append(f"transition choreography plan status is {plan.get('status')}")
    if max_run(families) > args.max_family_run:
        blockers.append(f"transition choreography family repeats too long: {max_run(families)} > {args.max_family_run}")
    if len(families) >= 4 and dominant_share > args.max_dominant_family_share:
        blockers.append(f"dominant choreography family share too high: {dominant_share:.3f} > {args.max_dominant_family_share:.3f}")
    for row in blocked[: args.max_blocked_rows_in_report]:
        blockers.append(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}")
    summary = {
        "transitionRowCount": len(plan_rows),
        "auditedRowCount": len(audited),
        "passedChoreographyRowCount": len(audited) - len(blocked),
        "blockedChoreographyRowCount": len(blocked),
        "importantBoundaryCount": sum(1 for row in plan_rows if row.get("importantBoundary")),
        "importantRowsWithThreeBeatCount": sum(
            1
            for row in plan_rows
            if row.get("importantBoundary") and has_role(row, "outgoing") and has_role(row, "bridge_or_motion") and has_role(row, "landing")
        ),
        "motionChoreographyRowCount": sum(1 for row in plan_rows if row.get("sourceTransitionStyle") in MOTION_STYLES),
        "highIntensityRowCount": sum(1 for row in plan_rows if as_int(row.get("intensity")) >= 3),
        "maxFamilyRun": max_run(families),
        "dominantFamilyShare": round(dominant_share, 3),
        "choreographyFamilyCounts": family_counts,
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers and not blocked else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "transitionChoreographyPlan": str(plan_path),
            "transitionChoreographyPlanStatus": plan.get("status"),
            "maxFamilyRun": args.max_family_run,
            "maxDominantFamilyShare": args.max_dominant_family_share,
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "policy": {
            "importantTransitionsNeedThreeBeatChoreography": True,
            "motionEffectsNeedSourceMotionOrBridge": True,
            "rotationMustStaySubtle": True,
            "familyRepetitionLimited": True,
            "bgmHitAndCaptionQuietZoneRequired": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Choreography Contract Audit",
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
                f"### Row {row.get('rowIndex')}: `{row.get('choreographyFamily')}`",
                f"- Status: `{row.get('status')}`",
                f"- Style: `{row.get('sourceTransitionStyle')}` intensity=`{row.get('intensity')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Important route/title/day/ending transitions need outgoing, bridge-or-motion, and landing beats.",
            "- Whip, rotation, push, and speed-ramp accents must cite source motion or bridge evidence.",
            "- Choreography must stay BGM-hit aligned, title-safe, caption-quiet, and restrained.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition choreography contract.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-family-run", type=int, default=4)
    parser.add_argument("--max-dominant-family-share", type=float, default=0.7)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_choreography_contract_audit.json", report)
    write_markdown(package_dir / "transition_choreography_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
