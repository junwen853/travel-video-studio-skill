#!/usr/bin/env python3
"""Audit whether visible motion accents stay restrained, motivated, and readable."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionChoreographyPlan": ("transition_choreography_plan/transition_choreography_plan.json", {"ready_with_transition_choreography_plan"}),
    "transitionChoreographyContract": ("transition_choreography_contract_audit.json", {"passed"}),
    "transitionMotionDirection": ("transition_motion_direction_contract_audit.json", {"passed"}),
    "transitionCutpoint": ("transition_cutpoint_contract_audit.json", {"passed"}),
    "transitionActionAnchor": ("transition_action_anchor_contract_audit.json", {"passed"}),
    "transitionSensoryContinuity": ("transition_sensory_continuity_contract_audit.json", {"passed"}),
    "transitionBreathingRoom": ("transition_breathing_room_contract_audit.json", {"passed"}),
    "transitionAuditionQuality": ("transition_audition_quality_contract_audit.json", {"passed"}),
    "transitionAuditionVisualProof": ("transition_audition_visual_proof_contract_audit.json", {"passed"}),
    "effectMotionApplication": ("effect_motion_application_contract_audit.json", {"passed"}),
    "finalCutSmoothness": ("final_cut_smoothness_contract_audit.json", {"passed"}),
}
MOTION_STYLE_TERMS = ("whip", "rotation", "rotate", "speed_ramp", "speed ramp", "push", "slide", "zoom", "spin")
ROTATION_DIRECTIONS = {"clockwise", "counterclockwise", "subtle_centered_rotation"}
FORBIDDEN_TERMS = ("random", "glitch", "flash", "shake", "strobe", "template", "particle", "spin")


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


def clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


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
    for name, (relative, accepted) in REPORT_SPECS.items():
        path = package_dir / relative
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


def plan_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json") or {}
    rows = data.get("choreographyRows") if isinstance(data.get("choreographyRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def execution_blueprint(package_dir: Path) -> dict[str, Any]:
    report = load_json(package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json") or {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    raw = outputs.get("candidateBlueprint") or package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json"
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return load_json(path) or {}


def transition_rows_by_index(package_dir: Path) -> dict[str, dict[str, Any]]:
    rows = execution_blueprint(package_dir).get("transitions")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            out[str(row.get("rowIndex"))] = row
    return out


def nested(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def role_ready(beats: Any, role: str) -> bool:
    if not isinstance(beats, list):
        return False
    return any(isinstance(beat, dict) and beat.get("role") == role and clean(beat.get("action")) for beat in beats)


def style_of(plan_row: dict[str, Any], transition_row: dict[str, Any]) -> str:
    motion = nested(transition_row, "transitionMotionExecution")
    values = (
        plan_row.get("sourceTransitionStyle"),
        motion.get("sourceTransitionStyle"),
        transition_row.get("selectedCandidateType"),
        transition_row.get("approvedTransitionType"),
        transition_row.get("transitionStyle"),
        transition_row.get("resolveEffectName"),
        motion.get("resolveKeyframeEffect"),
        motion.get("effectName"),
        motion.get("effectFamily"),
        plan_row.get("choreographyFamily"),
    )
    return " ".join(str(value or "").lower() for value in values)


def is_motion_accent(plan_row: dict[str, Any], transition_row: dict[str, Any]) -> bool:
    direction = nested(plan_row, "motionDirectionPlan")
    motion = nested(transition_row, "transitionMotionExecution")
    text = style_of(plan_row, transition_row)
    return bool(
        direction.get("required") is True
        or motion.get("ready") is True
        or motion.get("resolveKeyframeEffect")
        or any(term in text for term in MOTION_STYLE_TERMS)
    )


def evidence_support(plan_row: dict[str, Any], action: dict[str, Any]) -> bool:
    evidence = nested(plan_row, "motionEvidence")
    return bool(
        evidence.get("physicalBridgeEvidence") is True
        or evidence.get("hasRouteBridgeTerms") is True
        or evidence.get("hasTwoSidedMotion") is True
        or evidence.get("bridgeTerms")
        or action.get("directionalMotionAnchorReady") is True
    )


def forbidden_text(plan_row: dict[str, Any], transition_row: dict[str, Any]) -> bool:
    motion = nested(transition_row, "transitionMotionExecution")
    text = " ".join(
        [
            style_of(plan_row, transition_row),
            clean(plan_row.get("forbiddenHits")).lower(),
            clean(transition_row.get("forbiddenHits")).lower(),
            clean(motion.get("forbiddenHits")).lower(),
            clean(motion.get("unsafeStyleLanguage")).lower(),
            clean(motion.get("notes")).lower(),
            clean(motion.get("safetyNotes")).lower(),
            clean(motion.get("sourceEffectName")).lower(),
            clean(motion.get("templateName")).lower(),
        ]
    )
    return any(term in text for term in FORBIDDEN_TERMS)


def row_issues(plan_row: dict[str, Any], transition_row: dict[str, Any], index_in_order: int, motion_indexes: set[int], args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    direction = nested(plan_row, "motionDirectionPlan")
    cutpoint = nested(transition_row, "transitionCutpointPlan")
    action = nested(transition_row, "transitionActionAnchorPlan")
    sensory = nested(transition_row, "transitionSensoryContinuityPlan")
    motion = nested(transition_row, "transitionMotionExecution")
    bgm = nested(plan_row, "bgmChoreography")
    caption = nested(plan_row, "captionAndTitlePolicy")
    channels = nested(sensory, "cueChannels")
    style_text = style_of(plan_row, transition_row)
    intensity = max(as_int(plan_row.get("intensity")), as_int(motion.get("intensity")))
    motion_accent = is_motion_accent(plan_row, transition_row)

    if not motion_accent:
        if intensity >= args.max_non_motion_intensity + 1:
            issues.append("non_motion_transition_intensity_too_high")
        return issues

    if plan_row.get("status") != "ready_with_transition_choreography":
        issues.append("choreography_row_not_ready")
    if intensity > args.max_motion_intensity:
        issues.append("motion_accent_intensity_too_high")
    if "rotation" in style_text and intensity > args.max_rotation_intensity:
        issues.append("rotation_accent_not_subtle")
    if forbidden_text(plan_row, transition_row):
        issues.append("forbidden_template_or_random_motion_language")
    if not (role_ready(plan_row.get("threeBeatChoreography"), "outgoing") and role_ready(plan_row.get("threeBeatChoreography"), "bridge_or_motion") and role_ready(plan_row.get("threeBeatChoreography"), "landing")):
        issues.append("motion_accent_missing_outgoing_bridge_landing_choreography")
    if not evidence_support(plan_row, action):
        issues.append("motion_accent_without_source_motion_or_bridge_anchor")
    if direction.get("required") is not True or direction.get("status") != "ready_with_motion_direction_plan":
        issues.append("motion_direction_plan_not_ready")
    if direction.get("directionMatch") is not True or direction.get("directionConflict") is True:
        issues.append("motion_direction_not_matched_or_conflicts")
    if as_float(direction.get("directionConfidence")) < args.min_direction_confidence:
        issues.append("motion_direction_confidence_too_low")
    if "rotation" in style_text and direction.get("effectDirection") not in ROTATION_DIRECTIONS:
        issues.append("rotation_direction_not_explicit_or_subtle")
    if bgm.get("target") != "cut_or_effect_on_bgm_phrase_hit" or as_float(bgm.get("hitToleranceSeconds"), 99.0) > args.max_bgm_hit_tolerance_seconds:
        issues.append("motion_accent_not_on_bgm_phrase_hit")
    if cutpoint.get("status") != "ready_with_transition_cutpoint_plan" or cutpoint.get("bgmHitAligned") is not True:
        issues.append("cutpoint_or_bgm_hit_not_ready")
    if as_int(cutpoint.get("landingHoldFrames")) < args.min_landing_hold_frames:
        issues.append("landing_hold_too_short_after_motion_accent")
    if cutpoint.get("titleSubtitleQuietZoneReady") is not True:
        issues.append("title_subtitle_quiet_zone_not_ready")
    if caption.get("avoidTitleCollision") is not True or as_float(caption.get("quietZoneBeforeSeconds")) < args.min_caption_quiet_seconds:
        issues.append("caption_title_policy_not_quiet_enough")
    if action.get("status") != "ready_with_transition_action_anchor_plan" or action.get("directionalMotionAnchorReady") is not True:
        issues.append("directional_action_anchor_not_ready")
    if sensory.get("status") != "ready_with_transition_sensory_continuity_plan" or channels.get("motionContinuityReady") is not True:
        issues.append("sensory_motion_continuity_not_ready")
    if sensory.get("bgmOnlyNoSourceVoice") is not True:
        issues.append("motion_accent_audio_not_bgm_only")
    if motion and motion.get("ready") is not True:
        issues.append("transition_motion_execution_not_ready")
    safety_checks = nested(motion, "safetyChecks")
    if safety_checks.get("forbidTemplateMotion") is not True:
        issues.append("template_motion_safety_not_declared")
    if index_in_order - 1 in motion_indexes or index_in_order + 1 in motion_indexes:
        issues.append("back_to_back_motion_accents_without_breath")
    return issues


def max_run(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        if flag:
            current += 1
        else:
            current = 0
        best = max(best, current)
    return best


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    rows = plan_rows(package_dir)
    transition_by_index = transition_rows_by_index(package_dir)
    visual_boundaries = max(
        len(rows),
        as_int(reports["transitionBreathingRoom"]["summary"].get("visualBoundaryCount")),
        as_int(reports["finalCutSmoothness"]["summary"].get("visualBoundaryCount")),
    )
    merged: list[tuple[dict[str, Any], dict[str, Any]]] = [(row, transition_by_index.get(str(row.get("rowIndex")), {})) for row in rows]
    motion_flags = [is_motion_accent(plan_row, transition_row) for plan_row, transition_row in merged]
    motion_indexes = {index for index, flag in enumerate(motion_flags) if flag}
    audited: list[dict[str, Any]] = []
    for index, (plan_row, transition_row) in enumerate(merged):
        direction = nested(plan_row, "motionDirectionPlan")
        cutpoint = nested(transition_row, "transitionCutpointPlan")
        action = nested(transition_row, "transitionActionAnchorPlan")
        sensory = nested(transition_row, "transitionSensoryContinuityPlan")
        channels = nested(sensory, "cueChannels")
        motion_accent = index in motion_indexes
        issues = row_issues(plan_row, transition_row, index, motion_indexes, args)
        audited.append(
            {
                "rowIndex": plan_row.get("rowIndex"),
                "status": "passed" if not issues else "blocked",
                "motionAccent": motion_accent,
                "boundaryCategory": plan_row.get("boundaryCategory"),
                "importantBoundary": plan_row.get("importantBoundary"),
                "sourceTransitionStyle": plan_row.get("sourceTransitionStyle"),
                "choreographyFamily": plan_row.get("choreographyFamily"),
                "intensity": max(as_int(plan_row.get("intensity")), as_int(nested(transition_row, "transitionMotionExecution").get("intensity"))),
                "effectDirection": direction.get("effectDirection"),
                "landingDirection": direction.get("landingDirection"),
                "directionConfidence": direction.get("directionConfidence"),
                "directionMatch": direction.get("directionMatch"),
                "evidenceSupport": evidence_support(plan_row, action),
                "bgmTarget": nested(plan_row, "bgmChoreography").get("target"),
                "bgmHitToleranceSeconds": nested(plan_row, "bgmChoreography").get("hitToleranceSeconds"),
                "landingHoldFrames": cutpoint.get("landingHoldFrames"),
                "titleSubtitleQuietZoneReady": cutpoint.get("titleSubtitleQuietZoneReady"),
                "directionalMotionAnchorReady": action.get("directionalMotionAnchorReady"),
                "motionContinuityReady": channels.get("motionContinuityReady"),
                "bgmOnlyNoSourceVoice": sensory.get("bgmOnlyNoSourceVoice"),
                "issues": issues,
            }
        )

    input_blockers = [
        f"{name} status is {report.get('status')}"
        for name, report in reports.items()
        if not (report["exists"] and report["accepted"])
    ]
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    blocked_motion = [row for row in blocked_rows if row.get("motionAccent") is True]
    motion_rows = [row for row in audited if row.get("motionAccent") is True]
    max_allowed = max(args.min_motion_accent_allowance, math.ceil(max(visual_boundaries, 1) * args.max_motion_share))
    row_blockers = [
        f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}"
        for row in blocked_rows[: args.max_blocked_rows_in_report]
    ]
    blockers = input_blockers + row_blockers
    if len(motion_rows) > max_allowed:
        blockers.append(f"motion accents are overused: {len(motion_rows)}/{max_allowed} allowed")
    if max_run(motion_flags) > 1:
        blockers.append("motion accents appear back-to-back without a breathing transition")

    style_counts: dict[str, int] = {}
    for row in motion_rows:
        style = clean(row.get("sourceTransitionStyle") or row.get("choreographyFamily") or "unknown")
        style_counts[style] = style_counts.get(style, 0) + 1
    summary = {
        "transitionRowCount": len(rows),
        "visualBoundaryCount": visual_boundaries,
        "motionAccentRowCount": len(motion_rows),
        "readyMotionAccentRowCount": len(motion_rows) - len(blocked_motion),
        "blockedMotionAccentRowCount": len(blocked_motion),
        "maxMotionAccentAllowed": max_allowed,
        "motionAccentShare": round(len(motion_rows) / visual_boundaries, 4) if visual_boundaries else 0.0,
        "motionAccentRunMax": max_run(motion_flags),
        "highIntensityMotionCount": sum(1 for row in motion_rows if as_int(row.get("intensity")) > args.max_motion_intensity),
        "rotationTooStrongCount": sum(1 for row in motion_rows if "rotation" in clean(row.get("sourceTransitionStyle")).lower() and as_int(row.get("intensity")) > args.max_rotation_intensity),
        "unsupportedMotionAccentCount": sum(1 for row in motion_rows if row.get("evidenceSupport") is not True),
        "directionMismatchMotionCount": sum(1 for row in motion_rows if row.get("directionMatch") is not True),
        "bgmMisalignedMotionCount": sum(1 for row in motion_rows if row.get("bgmTarget") != "cut_or_effect_on_bgm_phrase_hit"),
        "titleOrCaptionRiskMotionCount": sum(1 for row in motion_rows if row.get("titleSubtitleQuietZoneReady") is not True),
        "missingAnchorMotionCount": sum(1 for row in motion_rows if row.get("directionalMotionAnchorReady") is not True),
        "missingSensoryMotionCount": sum(1 for row in motion_rows if row.get("motionContinuityReady") is not True),
        "motionStyleCounts": style_counts,
        "blockedCheckCount": len(blockers),
        "blockerCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "reports": {name: report["path"] for name, report in reports.items()},
            "maxMotionShare": args.max_motion_share,
            "maxMotionIntensity": args.max_motion_intensity,
            "maxRotationIntensity": args.max_rotation_intensity,
            "minDirectionConfidence": args.min_direction_confidence,
        },
        "summary": summary,
        "auditedRows": audited,
        "blockers": blockers,
        "warnings": [],
        "policy": {
            "motionAccentsMustBeRare": True,
            "motionAccentsMustNotBeBackToBack": True,
            "motionAccentsNeedSourceOrBridgeEvidence": True,
            "motionAccentsNeedMatchedDirection": True,
            "rotationMustStaySubtle": True,
            "motionAccentsNeedBgmHitAndQuietTitleCaptionZone": True,
            "motionAccentsNeedReadableLandingAnchorAndSensoryContinuity": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Motion Accent Contract Audit",
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
                f"- Motion accent: `{row.get('motionAccent')}` style=`{row.get('sourceTransitionStyle')}` family=`{row.get('choreographyFamily')}` intensity=`{row.get('intensity')}`",
                f"- Direction: effect=`{row.get('effectDirection')}` landing=`{row.get('landingDirection')}` confidence=`{row.get('directionConfidence')}` match=`{row.get('directionMatch')}`",
                f"- Landing/safety: holdFrames=`{row.get('landingHoldFrames')}` quiet=`{row.get('titleSubtitleQuietZoneReady')}` anchor=`{row.get('directionalMotionAnchorReady')}` sensory=`{row.get('motionContinuityReady')}` bgmOnly=`{row.get('bgmOnlyNoSourceVoice')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Whip, rotation, push, slide, zoom, and speed-ramp accents must be rare, motivated by source or bridge movement, and never back-to-back.",
            "- Rotation must stay subtle; random spin, template motion, flash, shake, or glitch language blocks the audit.",
            "- Every motion accent needs BGM-hit timing, title/subtitle quiet zone, directional action anchor, sensory continuity, and a readable landing hold.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit restrained transition motion accents.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-motion-share", type=float, default=0.18)
    parser.add_argument("--min-motion-accent-allowance", type=int, default=2)
    parser.add_argument("--max-motion-intensity", type=int, default=2)
    parser.add_argument("--max-rotation-intensity", type=int, default=1)
    parser.add_argument("--min-direction-confidence", type=float, default=0.65)
    parser.add_argument("--max-bgm-hit-tolerance-seconds", type=float, default=0.35)
    parser.add_argument("--min-caption-quiet-seconds", type=float, default=0.25)
    parser.add_argument("--min-landing-hold-frames", type=int, default=18)
    parser.add_argument("--max-non-motion-intensity", type=int, default=2)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=16)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir)
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_motion_accent_contract_audit.json", report)
    write_markdown(package_dir / "transition_motion_accent_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
