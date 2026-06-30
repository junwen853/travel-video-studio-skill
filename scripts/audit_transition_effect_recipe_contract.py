#!/usr/bin/env python3
"""Audit that transition effect recipes have executable, restrained Resolve parameters."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionExecutionBlueprint": (
        "transition_execution_blueprint/transition_execution_blueprint_report.json",
        {"ready_with_transition_execution_blueprint"},
    ),
    "transitionCutpoint": ("transition_cutpoint_contract_audit.json", {"passed"}),
    "transitionActionAnchor": ("transition_action_anchor_contract_audit.json", {"passed"}),
    "transitionSensoryContinuity": ("transition_sensory_continuity_contract_audit.json", {"passed"}),
    "transitionMotionAccent": ("transition_motion_accent_contract_audit.json", {"passed"}),
    "transitionAuditionQuality": ("transition_audition_quality_contract_audit.json", {"passed"}),
}
FORBIDDEN_TERMS = (
    "random spin",
    "glitch",
    "flash",
    "shake",
    "strobe",
    "template",
    "particle",
    "whoosh pack",
)
VISIBLE_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide"}
VISIBLE_EFFECTS = {
    "restrained_rotation_match",
    "restrained_whip_pan",
    "short_speed_ramp",
    "soft_push_slide",
    "short_mood_dissolve",
    "opacity_scale_breath",
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


def clean(value: Any, limit: int = 600) -> str:
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


def infer_blueprint_path(package_dir: Path, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_absolute() else (package_dir / path).resolve()
    report = load_json(package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json") or {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    raw = outputs.get("candidateBlueprint")
    if raw:
        path = Path(str(raw)).expanduser()
        return path if path.is_absolute() else (package_dir / path).resolve()
    return (package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json").resolve()


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def nested(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def frame_values(keyframes: list[dict[str, Any]]) -> list[int]:
    return [as_int(row.get("frame"), -1) for row in keyframes if isinstance(row, dict)]


def style_text(row: dict[str, Any], recipe: dict[str, Any], motion: dict[str, Any]) -> str:
    return " ".join(
        clean(value).lower()
        for value in (
            row.get("approvedTransitionType"),
            row.get("resolveEffectName"),
            row.get("trackOperation"),
            row.get("selectedCandidateType"),
            row.get("selectedStyleFamily"),
            motion.get("sourceTransitionStyle"),
            motion.get("choreographyFamily"),
            recipe.get("effect"),
        )
    )


def is_visible_effect(style_blob: str, recipe: dict[str, Any]) -> bool:
    effect = str(recipe.get("effect") or "").lower()
    return bool(effect in VISIBLE_EFFECTS or any(style in style_blob for style in VISIBLE_STYLES))


def audio_keyframes_ready(rows: Any) -> bool:
    if not isinstance(rows, list) or len(rows) < 2:
        return False
    return all(isinstance(row, dict) and str(row.get("a1a2SourceAudioDb")) == "-inf" and row.get("a3BgmDb") is not None for row in rows)


def recipe_issues(row: dict[str, Any], args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    motion = nested(row, "transitionMotionExecution")
    recipe = nested(motion, "resolveKeyframeRecipe")
    envelope = nested(recipe, "parameterEnvelope")
    easing = nested(recipe, "easing")
    quality = nested(recipe, "qualityControls")
    safety_checks = nested(motion, "safetyChecks")
    cutpoint = nested(row, "transitionCutpointPlan")
    action = nested(row, "transitionActionAnchorPlan")
    sensory = nested(row, "transitionSensoryContinuityPlan")
    direction = nested(motion, "motionDirectionPlan")
    style_blob = style_text(row, recipe, motion)
    visible = is_visible_effect(style_blob, recipe)
    keyframes = recipe.get("transformKeyframes") if isinstance(recipe.get("transformKeyframes"), list) else []
    frames = frame_values(keyframes)
    duration = as_int(recipe.get("durationFrames"), -1)

    if motion.get("status") != "ready_with_transition_motion_execution":
        issues.append("transition_motion_execution_not_ready")
    if not recipe:
        issues.append("missing_resolve_keyframe_recipe")
        return issues
    if not clean(recipe.get("effect")):
        issues.append("missing_recipe_effect_name")
    if duration <= 0:
        issues.append("missing_or_invalid_recipe_duration")
    if len(keyframes) < (3 if visible and "dissolve" not in style_blob and "breath" not in style_blob else 2):
        issues.append("insufficient_transform_keyframes")
    if not frames or min(frames) < 0 or frames != sorted(frames):
        issues.append("keyframe_frames_not_monotonic")
    if frames and frames[0] != 0:
        issues.append("first_keyframe_not_zero")
    if frames and duration > 0 and frames[-1] != duration:
        issues.append("last_keyframe_does_not_match_duration")
    if not easing or not clean(easing.get("curve")):
        issues.append("missing_easing_curve")
    if as_int(easing.get("holdLandingFrames"), 0) < args.min_recipe_landing_hold_frames and visible:
        issues.append("recipe_landing_hold_too_short")
    if not envelope:
        issues.append("missing_parameter_envelope")
    if as_float(envelope.get("maxRotationDegrees")) > args.max_rotation_degrees:
        issues.append("rotation_parameter_too_large")
    if as_float(envelope.get("maxTranslatePercent")) > args.max_translate_percent:
        issues.append("translate_parameter_too_large")
    if as_float(envelope.get("maxScale"), 1.0) > args.max_scale:
        issues.append("scale_parameter_too_large")
    if as_float(envelope.get("maxMotionBlur")) > args.max_motion_blur:
        issues.append("motion_blur_parameter_too_large")
    if as_float(envelope.get("maxRetimePercent"), 100.0) > args.max_retime_percent:
        issues.append("retime_parameter_too_large")
    if not audio_keyframes_ready(recipe.get("audioKeyframes")):
        issues.append("audio_keyframes_do_not_force_bgm_only")
    if quality.get("templateMotionForbidden") is not True or safety_checks.get("forbidTemplateMotion") is not True:
        issues.append("template_motion_forbid_flag_missing")
    if quality.get("bgmOnlyNoSourceVoice") is not True or safety_checks.get("bgmOnlyNoSourceVoice") is not True:
        issues.append("bgm_only_safety_flag_missing")
    if quality.get("titleSafe") is not True or safety_checks.get("titleSafe") is not True:
        issues.append("title_safe_flag_missing")
    if quality.get("manualResolveReadbackRequired") is not True:
        issues.append("resolve_readback_requirement_missing")
    if visible:
        if cutpoint.get("status") != "ready_with_transition_cutpoint_plan" or cutpoint.get("bgmHitAligned") is not True:
            issues.append("visible_effect_not_aligned_to_bgm_cutpoint")
        if as_int(cutpoint.get("landingHoldFrames"), 0) < args.min_actual_landing_hold_frames:
            issues.append("actual_landing_hold_too_short")
        if action.get("status") != "ready_with_transition_action_anchor_plan":
            issues.append("visible_effect_missing_action_anchor")
        if sensory.get("status") != "ready_with_transition_sensory_continuity_plan" or sensory.get("bgmOnlyNoSourceVoice") is not True:
            issues.append("visible_effect_missing_sensory_or_bgm_only_proof")
        if any(style in style_blob for style in VISIBLE_STYLES):
            if direction.get("directionMatch") is not True:
                issues.append("visible_motion_direction_not_matched")
            if not clean(direction.get("effectDirection")):
                issues.append("visible_motion_effect_direction_missing")
            if quality.get("sourceMotionRequiredForVisibleEffect") is not True:
                issues.append("source_motion_requirement_missing_for_visible_effect")
    if any(term in style_blob for term in FORBIDDEN_TERMS):
        issues.append("forbidden_template_or_random_effect_language")
    return issues


def row_summary(row: dict[str, Any], issues: list[str], args: argparse.Namespace) -> dict[str, Any]:
    motion = nested(row, "transitionMotionExecution")
    recipe = nested(motion, "resolveKeyframeRecipe")
    envelope = nested(recipe, "parameterEnvelope")
    cutpoint = nested(row, "transitionCutpointPlan")
    style_blob = style_text(row, recipe, motion)
    return {
        "rowIndex": row.get("rowIndex"),
        "status": "passed" if not issues else "blocked",
        "boundaryCategory": row.get("boundaryCategory"),
        "visibleEffect": is_visible_effect(style_blob, recipe),
        "effect": recipe.get("effect"),
        "durationFrames": recipe.get("durationFrames"),
        "easingCurve": nested(recipe, "easing").get("curve"),
        "maxRotationDegrees": envelope.get("maxRotationDegrees"),
        "maxTranslatePercent": envelope.get("maxTranslatePercent"),
        "maxScale": envelope.get("maxScale"),
        "maxMotionBlur": envelope.get("maxMotionBlur"),
        "maxRetimePercent": envelope.get("maxRetimePercent"),
        "landingHoldFrames": cutpoint.get("landingHoldFrames"),
        "bgmHitAligned": cutpoint.get("bgmHitAligned"),
        "issues": issues[: args.max_row_issues_in_report],
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    blueprint_path = infer_blueprint_path(package_dir, args.blueprint)
    blueprint = load_json(blueprint_path) or {}
    rows = transition_rows(blueprint if isinstance(blueprint, dict) else {})
    audited_rows: list[dict[str, Any]] = []
    for row in rows:
        issues = recipe_issues(row, args)
        audited_rows.append(row_summary(row, issues, args))

    input_blockers = [
        f"{name} status is {report.get('status')}"
        for name, report in reports.items()
        if not (report["exists"] and report["accepted"])
    ]
    if not isinstance(blueprint, dict) or not blueprint:
        input_blockers.append("transition execution blueprint is missing")
    if not rows:
        input_blockers.append("transition execution blueprint has no transition rows")

    blocked_rows = [row for row in audited_rows if row.get("status") == "blocked"]
    row_blockers = [
        f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}"
        for row in blocked_rows[: args.max_blocked_rows_in_report]
    ]
    blockers = input_blockers + row_blockers
    visible_rows = [row for row in audited_rows if row.get("visibleEffect") is True]
    summary = {
        "transitionRowCount": len(rows),
        "recipeRowCount": len(audited_rows),
        "visibleEffectRowCount": len(visible_rows),
        "blockedRecipeRowCount": len(blocked_rows),
        "rowsWithEasing": sum(1 for row in audited_rows if clean(row.get("easingCurve"))),
        "rowsWithBgmHit": sum(1 for row in audited_rows if row.get("bgmHitAligned") is True),
        "rowsWithLandingHold": sum(1 for row in audited_rows if as_int(row.get("landingHoldFrames")) >= args.min_actual_landing_hold_frames),
        "maxRotationDegreesSeen": max([as_float(row.get("maxRotationDegrees")) for row in audited_rows] or [0.0]),
        "maxTranslatePercentSeen": max([as_float(row.get("maxTranslatePercent")) for row in audited_rows] or [0.0]),
        "maxScaleSeen": max([as_float(row.get("maxScale"), 1.0) for row in audited_rows] or [1.0]),
        "maxMotionBlurSeen": max([as_float(row.get("maxMotionBlur")) for row in audited_rows] or [0.0]),
        "maxRetimePercentSeen": max([as_float(row.get("maxRetimePercent"), 100.0) for row in audited_rows] or [100.0]),
        "blockerCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "reports": {name: report["path"] for name, report in reports.items()},
            "maxRotationDegrees": args.max_rotation_degrees,
            "maxTranslatePercent": args.max_translate_percent,
            "maxScale": args.max_scale,
            "maxMotionBlur": args.max_motion_blur,
            "maxRetimePercent": args.max_retime_percent,
        },
        "summary": summary,
        "auditedRows": audited_rows,
        "blockers": blockers,
        "warnings": [],
        "policy": {
            "requiresExecutableResolveKeyframeRecipe": True,
            "requiresEasingAndParameterEnvelope": True,
            "requiresBgmOnlyAudioKeyframes": True,
            "requiresBgmHitAndLandingHoldForVisibleEffects": True,
            "requiresRestrainedTransformLimits": True,
            "forbidsTemplateAndRandomEffects": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Effect Recipe Contract Audit",
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
                f"- Effect: `{row.get('effect')}` duration=`{row.get('durationFrames')}` easing=`{row.get('easingCurve')}` visible=`{row.get('visibleEffect')}`",
                f"- Envelope: rotation={row.get('maxRotationDegrees')} translate={row.get('maxTranslatePercent')} scale={row.get('maxScale')} blur={row.get('maxMotionBlur')} retime={row.get('maxRetimePercent')}",
                f"- Timing: bgmHitAligned=`{row.get('bgmHitAligned')}` landingHoldFrames=`{row.get('landingHoldFrames')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Every transition row must carry a Resolve keyframe recipe with frames, easing, parameter envelope, audio keyframes, and safety controls.",
            "- Visible motion effects must stay restrained, BGM-hit aligned, BGM-only, title-safe, and supported by direction/action/sensory proof.",
            "- Random spin, flash, shake, glitch, particle, and template effects block this audit.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit executable Resolve transition effect recipes.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--max-rotation-degrees", type=float, default=8.0)
    parser.add_argument("--max-translate-percent", type=float, default=24.0)
    parser.add_argument("--max-scale", type=float, default=1.08)
    parser.add_argument("--max-motion-blur", type=float, default=0.5)
    parser.add_argument("--max-retime-percent", type=float, default=240.0)
    parser.add_argument("--min-recipe-landing-hold-frames", type=int, default=12)
    parser.add_argument("--min-actual-landing-hold-frames", type=int, default=18)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=16)
    parser.add_argument("--max-row-issues-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir)
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_effect_recipe_contract_audit.json", report)
    write_markdown(package_dir / "transition_effect_recipe_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
