#!/usr/bin/env python3
"""Prepare Resolve-ready transition execution recipes from transition grammar rows."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


MOTION_STYLES = {"whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
FORBIDDEN_TERMS = (
    "random spin",
    "glitch",
    "flash",
    "shake",
    "strobe",
    "template pack",
    "particle",
    "logo reveal",
    "whoosh pack",
)

DECISION_FIELDS = {
    "approvedTransitionType": "",
    "approvedResolveEffectName": "",
    "durationFrames": None,
    "bridgeInsertSource": "",
    "bgmPhraseCue": "",
    "subtitleSuppressionConfirmed": False,
    "audioPolicyConfirmed": False,
    "resolveImplementation": "",
    "timelineReadbackEvidence": "",
    "renderFrameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
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


def clean_words(value: Any, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def grammar_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json") or {}
    rows = data.get("transitionRows") if isinstance(data.get("transitionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def transition_bridge_summary(package_dir: Path) -> dict[str, Any]:
    data = load_json(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json") or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "status": data.get("status"),
        "boundaryRowCount": summary.get("boundaryRowCount"),
        "boundariesWithEvidence": summary.get("boundariesWithEvidence"),
        "missingBoundaryCount": summary.get("missingBoundaryCount"),
        "existingBridgeClipCount": summary.get("existingBridgeClipCount"),
    }


def effect_motion_summary(package_dir: Path) -> dict[str, Any]:
    data = load_json(package_dir / "effect_motion_plan" / "effect_motion_plan.json") or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "status": data.get("status"),
        "effectRowCount": summary.get("effectRowCount"),
        "rowsWithSourceEvidence": summary.get("rowsWithSourceEvidence"),
        "forbiddenEffectHitCount": summary.get("forbiddenEffectHitCount"),
        "transitionMotionRowCount": summary.get("transitionMotionRowCount"),
    }


def bgm_summary(package_dir: Path) -> dict[str, Any]:
    data = load_json(package_dir / "bgm_selection_package" / "bgm_selection_package.json") or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {
        "status": data.get("status"),
        "bgmCueCount": summary.get("bgmCueCount"),
        "verifiedMaterializedBedCount": summary.get("verifiedMaterializedBedCount"),
        "blueprintBgmAssetCount": summary.get("blueprintBgmAssetCount"),
    }


def source_name(clip: dict[str, Any] | None) -> str:
    clip = clip if isinstance(clip, dict) else {}
    source = str(clip.get("sourcePath") or clip.get("sourceName") or "")
    return Path(source).name if source else ""


def motion_evidence(row: dict[str, Any], rec: dict[str, Any]) -> dict[str, Any]:
    signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
    from_motion = signals.get("fromMotionTerms") if isinstance(signals.get("fromMotionTerms"), list) else []
    to_motion = signals.get("toMotionTerms") if isinstance(signals.get("toMotionTerms"), list) else []
    bridge_terms = signals.get("bridgeTerms") if isinstance(signals.get("bridgeTerms"), list) else []
    return {
        "physicalBridgeEvidence": rec.get("physicalBridgeEvidence") is True,
        "motionEffectAllowedByGrammar": rec.get("motionEffectAllowed") is True,
        "fromMotionTerms": from_motion,
        "toMotionTerms": to_motion,
        "bridgeTerms": bridge_terms,
        "hasTwoSidedMotion": bool(from_motion and to_motion),
        "hasRouteBridgeTerms": bool(bridge_terms),
    }


def recipe_for_transition(style: str, rec: dict[str, Any], category: str, evidence: dict[str, Any]) -> dict[str, Any]:
    duration = as_int(rec.get("durationFrames"), 0)
    title_boundary = category == "title_boundary"
    if style == "straight_cut":
        return {
            "resolveEffectName": "none_straight_cut",
            "durationFrames": 0,
            "preRollFrames": 0,
            "postRollFrames": 0,
            "trackOperation": "butt_cut_on_action_or_visual_continuity",
            "keyframePlan": [],
            "implementationSteps": [
                "Place clips adjacent on V1/V2 with no generated transition.",
                "Trim to action, gaze, motion, or shape continuity.",
                "Keep A1/A2 muted in scenic/title transition windows unless intentional ambient is approved.",
            ],
        }
    if style == "match_cut":
        return {
            "resolveEffectName": "none_or_2_frame_soft_cut",
            "durationFrames": max(duration, 2),
            "preRollFrames": 2,
            "postRollFrames": 2,
            "trackOperation": "cut_on_shared_shape_motion_color_or_object",
            "keyframePlan": [],
            "implementationSteps": [
                "Align the shared visual term at the cut point.",
                "Use no visible effect unless a 2-frame soft cut is needed for compression or exposure shift.",
                "Sample frames before and after the cut for visual match evidence.",
            ],
        }
    if style == "short_dissolve":
        return {
            "resolveEffectName": "Cross Dissolve",
            "durationFrames": duration or 12,
            "preRollFrames": max((duration or 12) // 2, 4),
            "postRollFrames": max((duration or 12) // 2, 4),
            "trackOperation": "apply_short_cross_dissolve_with_handles",
            "keyframePlan": [],
            "implementationSteps": [
                "Use a short dissolve for time, mood, weather, title, or ending aftertaste.",
                "Do not use it as a default patch for missing bridge footage.",
                "Check title-zone subtitle suppression when the dissolve touches a title bridge.",
            ],
        }
    if style == "whip_pan_match":
        return {
            "resolveEffectName": "Transform whip-pan match cut",
            "durationFrames": duration or 10,
            "preRollFrames": 5,
            "postRollFrames": 5,
            "trackOperation": "overlap_or_cut_with_directional_transform_keyframes",
            "keyframePlan": [
                {"frame": -5, "positionX": 0, "motionBlur": 0.0},
                {"frame": 0, "positionX": "directional_push", "motionBlur": 0.35},
                {"frame": 5, "positionX": 0, "motionBlur": 0.0},
            ],
            "implementationSteps": [
                "Use only when grammar shows route-motion energy on both sides.",
                "Match pan/walking/vehicle direction; otherwise fall back to match_cut.",
                "Keep intensity subtle and verify no title text becomes unreadable.",
            ],
        }
    if style == "rotation_match_cut":
        return {
            "resolveEffectName": "Transform rotation match cut",
            "durationFrames": min(duration or 10, 10),
            "preRollFrames": 5,
            "postRollFrames": 5,
            "trackOperation": "cut_or_overlap_with_subtle_rotation_keyframes",
            "keyframePlan": [
                {"frame": -5, "rotationDegrees": 0, "scale": 1.0},
                {"frame": 0, "rotationDegrees": "3_to_8_degrees_matching_motion", "scale": 1.03},
                {"frame": 5, "rotationDegrees": 0, "scale": 1.0},
            ],
            "implementationSteps": [
                "Use rarely, only for turning, walking, vehicle, water, aerial, or route-motion evidence.",
                "Cap rotation at a subtle amount; do not use random spin.",
                "Fall back to match_cut or short_dissolve if motion evidence is weak.",
            ],
        }
    if style == "speed_ramp_bridge":
        return {
            "resolveEffectName": "Speed ramp on real route bridge",
            "durationFrames": duration or 8,
            "preRollFrames": 8,
            "postRollFrames": 8,
            "trackOperation": "retime_real_motion_clip_or_bridge_insert",
            "keyframePlan": [
                {"segment": "pre", "speedPercent": 100},
                {"segment": "middle", "speedPercent": "180_to_240_if_motion_supports"},
                {"segment": "post", "speedPercent": 100},
            ],
            "implementationSteps": [
                "Apply only to vehicle, aerial, water, crowd, walking, or camera-motion footage.",
                "Keep the ramp short and phrase it with BGM.",
                "Never ramp static scenic footage to fake energy.",
            ],
        }
    return {
        "resolveEffectName": "none_until_bridge_inserted",
        "durationFrames": 0,
        "preRollFrames": 0,
        "postRollFrames": 0,
        "trackOperation": "insert_physical_bridge_before_effect",
        "keyframePlan": [],
        "implementationSteps": [
            "Add route bridge footage before choosing an effect.",
            "Use transport, street, sign, weather, hotel, food, water, skyline, or aerial material.",
            "Rerun transition grammar and this execution plan after the bridge insert exists.",
        ],
    }


def forbidden_recipe_hits(recipe: dict[str, Any]) -> list[str]:
    text = clean_words(json.dumps(recipe, ensure_ascii=False), 4000).lower()
    return [term for term in FORBIDDEN_TERMS if term in text]


def build_execution_row(row: dict[str, Any]) -> dict[str, Any]:
    rec = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    category = str(row.get("boundaryCategory") or "")
    style = str(rec.get("recommendedTransitionType") or "straight_cut")
    evidence = motion_evidence(row, rec)
    recipe = recipe_for_transition(style, rec, category, evidence)
    forbidden_hits = forbidden_recipe_hits(recipe)
    requires_bridge = style == "insert_bridge_first" or row.get("status") == "needs_bridge_insert"
    motion_style = style in MOTION_STYLES
    motion_has_evidence = (
        not motion_style
        or (
            evidence.get("motionEffectAllowedByGrammar") is True
            and (evidence.get("physicalBridgeEvidence") or evidence.get("hasRouteBridgeTerms") or evidence.get("hasTwoSidedMotion"))
        )
    )
    decision = dict(DECISION_FIELDS)
    decision.update(
        {
            "approvedTransitionType": style,
            "approvedResolveEffectName": recipe["resolveEffectName"],
            "durationFrames": recipe["durationFrames"],
            "subtitleSuppressionConfirmed": category == "title_boundary",
            "audioPolicyConfirmed": True,
        }
    )
    status = "blocked_needs_bridge_insert" if requires_bridge else "ready_with_transition_execution_recipe"
    if forbidden_hits or not motion_has_evidence:
        status = "blocked_transition_execution_recipe"
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": category,
        "timelineStartSeconds": row.get("timelineStartSeconds"),
        "fromClip": row.get("fromClip"),
        "toClip": row.get("toClip"),
        "grammarStatus": row.get("status"),
        "grammarRecommendation": rec,
        "motionEvidence": evidence,
        "executionRecipe": {
            **recipe,
            "style": style,
            "audioPolicy": "bgm_only_no_camera_voice",
            "subtitlePolicy": "suppress_or_trim_when_touching_title_zone" if category == "title_boundary" else "normal_caption_safe_zone",
            "bgmPhraseCue": "cut_or_effect_on_bgm_phrase_boundary",
            "verificationTargets": [
                "Resolve timeline item/effect readback",
                "sampled frames before/during/after transition",
                "A1/A2/A3 readback for BGM-only scenic/title windows",
            ],
            "mustAvoid": [
                "random spin",
                "flash/glitch/shake template",
                "route jump with no bridge footage",
                "effect covering unreadable title",
                "source-camera voice under scenic transition",
            ],
        },
        "requiresBridgeInsert": requires_bridge,
        "motionStyle": motion_style,
        "motionHasEvidence": motion_has_evidence,
        "forbiddenRecipeHits": forbidden_hits,
        "status": status,
        "decision": decision,
    }


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    rows = [build_execution_row(row) for row in grammar_rows(package_dir)]
    decision_keys = set(DECISION_FIELDS)
    rows_with_decisions = sum(1 for row in rows if decision_keys.issubset(set((row.get("decision") or {}).keys())))
    rows_with_recipes = sum(1 for row in rows if (row.get("executionRecipe") or {}).get("resolveEffectName"))
    rows_ready = sum(1 for row in rows if row.get("status") == "ready_with_transition_execution_recipe")
    bridge_blocked = sum(1 for row in rows if row.get("requiresBridgeInsert"))
    motion_rows = sum(1 for row in rows if row.get("motionStyle"))
    motion_rows_with_evidence = sum(1 for row in rows if row.get("motionStyle") and row.get("motionHasEvidence"))
    forbidden_count = sum(len(row.get("forbiddenRecipeHits") or []) for row in rows)
    status = (
        "ready_with_transition_execution_plan"
        if rows and rows_ready == len(rows) and rows_with_decisions == len(rows) and rows_with_recipes == len(rows)
        else ("needs_transition_execution_repair" if rows else "blocked_missing_transition_grammar_plan")
    )
    style_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in rows:
        style = str((row.get("executionRecipe") or {}).get("style") or "")
        category = str(row.get("boundaryCategory") or "")
        style_counts[style] = style_counts.get(style, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "transitionGrammarPlan": str(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json"),
            "effectMotionPlan": str(package_dir / "effect_motion_plan" / "effect_motion_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "bgmSelectionPackage": str(package_dir / "bgm_selection_package" / "bgm_selection_package.json"),
        },
        "summary": {
            "transitionRowCount": len(rows),
            "rowsReadyForResolveExecution": rows_ready,
            "rowsWithDecisionFields": rows_with_decisions,
            "rowsWithExecutionRecipe": rows_with_recipes,
            "bridgeInsertBlockedRowCount": bridge_blocked,
            "motionStyleRowCount": motion_rows,
            "motionStyleRowsWithEvidence": motion_rows_with_evidence,
            "forbiddenRecipeHitCount": forbidden_count,
            "executionStyleCounts": style_counts,
            "boundaryCategoryCounts": category_counts,
        },
        "upstreamEvidence": {
            "transitionBridge": transition_bridge_summary(package_dir),
            "effectMotion": effect_motion_summary(package_dir),
            "bgmSelection": bgm_summary(package_dir),
        },
        "policy": {
            "resolveExecutionRecipeRequired": True,
            "motionEffectsNeedGrammarEvidence": True,
            "insertBridgeFirstIsNotEffectReady": True,
            "subtitleTitleZoneSafetyRequired": True,
            "bgmOnlyTransitionAudio": True,
            "templateEffectsRejected": True,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "executionRows": rows,
        "selectionRubric": {
            "pass": [
                "Every transition grammar row has a concrete Resolve execution recipe.",
                "Rows marked insert_bridge_first stay blocked until physical bridge footage is selected.",
                "Whip, rotation, and speed-ramp recipes cite grammar motion/bridge evidence.",
                "Title-boundary recipes suppress or trim subtitles in the title zone.",
                "Scenic/title/transition recipes stay BGM-only with no source-camera voice leakage.",
            ],
            "reject": [
                "Random spin, flash, glitch, shake, particle, or template-pack effects.",
                "Motion effect approved for static footage with no route/bridge evidence.",
                "Effect recipe used to hide weak footage, missing bridge material, or bad title design.",
                "Transition recipe that cannot be read back in Resolve or sampled after render.",
            ],
        },
        "nextActions": [
            "Fill row decisions for the exact transitions that will be implemented.",
            "If bridgeInsertBlockedRowCount is nonzero, add real route bridge clips before Resolve apply.",
            "Copy approved recipes into resolve_timeline_blueprint.json effectPlan only after title/audio safety passes.",
            "After Resolve apply, paste readback and frame-sample evidence into execution rows and rerun director polish plus feedback audits.",
        ],
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Execution Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Execution Rows",
    ]
    for row in plan["executionRows"][:160]:
        recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('boundaryCategory')}",
                f"- Status: `{row.get('status')}`",
                f"- From: `{source_name(row.get('fromClip'))}`",
                f"- To: `{source_name(row.get('toClip'))}`",
                f"- Style: `{recipe.get('style')}`",
                f"- Resolve effect: `{recipe.get('resolveEffectName')}`",
                f"- Duration frames: `{recipe.get('durationFrames')}`",
                f"- Operation: {recipe.get('trackOperation')}",
                "- Decision fields to fill:",
            ]
        )
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Resolve-ready transition execution recipes.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_execution_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_execution_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "transition_execution_plan.json", plan)
    write_markdown(output_dir / "transition_execution_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 2 if plan["status"] == "blocked_missing_transition_grammar_plan" else 0


if __name__ == "__main__":
    raise SystemExit(main())
