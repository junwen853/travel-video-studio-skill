#!/usr/bin/env python3
"""Prepare a Resolve transition apply plan from final transition metadata."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from audit_resolve_transition_materialization_contract import (
    as_float,
    as_int,
    build_timeline_preserves_marker_payload,
    choose_blueprint,
    clip_annotation_rows,
    load_json,
    marker_payload,
    markers_by_row,
    recipe_ready,
    row_index,
    selected_recipe,
    source_name,
    transition_candidate,
    transition_candidates,
    transition_markers,
    visible_effect,
    write_json,
)


DECISION_FIELDS = {
    "approveApplyPath": "",
    "resolveStepCompleted": "",
    "resolveReadbackEvidence": "",
    "frameSampleEvidence": "",
    "fallbackBridgeInserted": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

DIRECT_TRANSITION_API_STATUS = {
    "directTransitionAddApiDocumented": False,
    "timelineItemSetPropertyDocumented": True,
    "timelineItemSetPropertyScope": "static item properties only; no documented adjacent-clip transition/keyframe API",
    "timelineMarkerCustomDataDocumented": True,
    "fusionCompDocumented": True,
    "safeDefault": "do not claim Resolve-native transition application unless readback/frame evidence proves it",
}

MANUAL_EFFECT_TERMS = (
    "dissolve",
    "blur",
    "push",
    "slide",
    "rotation",
    "speed",
    "ramp",
    "transform",
    "whip",
)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Resolve Transition Apply Plan",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report['inputs'].get('blueprint')}`",
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
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Rows"])
    for row in report.get("transitionApplyRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('recipeId')}",
                f"- Status: `{row.get('status')}`",
                f"- Apply method: `{row.get('applyMethod')}`",
                f"- Effect: `{row.get('resolveEffectName')}`",
                f"- Boundary: `{row.get('boundarySeconds')}`",
                f"- Manual Resolve step required: `{row.get('manualResolveStepRequired')}`",
                f"- Fallback bridge insert required: `{row.get('fallbackBridgeInsertRequired')}`",
                f"- Acceptance evidence: `{'; '.join(row.get('acceptanceEvidence') or [])}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
        if row.get("manualInstruction"):
            lines.append(f"- Manual instruction: {row.get('manualInstruction')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def style_text(candidate: dict[str, Any], recipe: dict[str, Any]) -> str:
    values = [
        recipe.get("recipeId"),
        recipe.get("resolveEffectName"),
        candidate.get("sourceTransitionType"),
        candidate.get("sourceResolveEffectName"),
        candidate.get("approvedTransitionType"),
        candidate.get("motionStyle"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def is_clean_cut(candidate: dict[str, Any], recipe: dict[str, Any]) -> bool:
    text = style_text(candidate, recipe)
    effect = str(recipe.get("resolveEffectName") or "").strip().lower()
    return effect in {"cut", "straight cut"} or "clean_cut" in text or "straight_cut" in text


def has_bridge_path(candidate: dict[str, Any]) -> bool:
    motivation = candidate.get("transitionMotivation") if isinstance(candidate.get("transitionMotivation"), dict) else {}
    continuity = candidate.get("pairContinuity") if isinstance(candidate.get("pairContinuity"), dict) else {}
    tags = continuity.get("evidenceTags") if isinstance(continuity.get("evidenceTags"), list) else []
    return (
        candidate.get("bridgeSequenceSatisfied") is True
        or motivation.get("strategy") == "route_bridge_sequence"
        or "bridge_sequence" in tags
    )


def manual_effect_kind(candidate: dict[str, Any], recipe: dict[str, Any]) -> str:
    text = style_text(candidate, recipe)
    for term in MANUAL_EFFECT_TERMS:
        if term in text:
            return term
    return "visible_transition"


def marker_payload_ready(markers: list[dict[str, Any]], index: int) -> bool:
    for marker in markers:
        payload = marker_payload(marker)
        if as_int(payload.get("rowIndex"), -1) == index and (payload.get("recipeId") or payload.get("resolveEffectName")):
            return True
    return False


def classify_row(
    row: dict[str, Any],
    *,
    marker_lookup: dict[int, list[dict[str, Any]]],
    clip_rows: set[int],
) -> dict[str, Any]:
    candidate = transition_candidate(row)
    recipe = selected_recipe(row)
    index = row_index(row)
    markers = marker_lookup.get(index) or []
    issues: list[str] = []
    if index < 0:
        issues.append("missing_transition_row_index")
    if not recipe_ready(row):
        issues.append("missing_selected_recipe_duration_keyframes_or_effect")
    if not marker_payload_ready(markers, index):
        issues.append("missing_marker_payload_for_apply_handoff")
    if index not in clip_rows:
        issues.append("missing_clip_transition_annotation_for_apply_handoff")

    clean_cut = is_clean_cut(candidate, recipe)
    bridge = has_bridge_path(candidate)
    visible = visible_effect(row)
    manual_kind = manual_effect_kind(candidate, recipe)

    if bridge:
        apply_method = "blueprint_bridge_sequence_video_clips"
        owner = "build_resolve_timeline.py plus bridge_sequence_application_contract_audit.py"
        manual_required = False
        fallback_required = False
        instruction = "Apply the final blueprint that contains materialized bridge clips; verify the bridge clips in Resolve readback and frame samples around the boundary."
        status = "ready_bridge_apply_path"
        evidence = [
            "bridge_sequence_application_contract_audit.json passed",
            "resolve_audit.json shows bridge clips on the expected video track",
            "frame samples around the boundary show real bridge footage, not a marker-only effect",
        ]
    elif clean_cut:
        apply_method = "append_adjacent_clips_cut_on_bgm_hit"
        owner = "build_resolve_timeline.py"
        manual_required = False
        fallback_required = False
        instruction = "Append the adjacent clips at the planned record frames and verify the cut location against BGM/title-safe marker payloads."
        status = "ready_api_cut_apply_path"
        evidence = [
            "resolve_audit.json shows adjacent source items at the expected boundary",
            "timeline marker customData preserves the row recipe payload",
            "frame samples around the boundary show the intended cut",
        ]
    else:
        apply_method = "manual_resolve_effect_or_fusion_step_required"
        owner = "Resolve editor guided by marker customData; no direct transition-add API is documented"
        manual_required = True
        fallback_required = True
        instruction = (
            "Use the transition marker customData as the Resolve edit note, apply the named restrained effect "
            f"({recipe.get('resolveEffectName')}) or an equivalent Fusion/keyframe treatment manually, then save "
            "Resolve readback and frame samples. If the manual step is not completed, replace the boundary with "
            "a real local/stock bridge sequence instead of leaving marker-only metadata."
        )
        status = "ready_manual_resolve_apply_path" if visible else "ready_manual_handoff_apply_path"
        evidence = [
            "resolve_audit.json preserves the transition marker payload",
            "editor confirmation or screenshot/frame samples prove the effect exists on the timeline",
            "if manual effect is skipped, bridge_sequence_application_contract_audit.json proves a real bridge replacement",
        ]

    if visible and apply_method == "timeline_marker_handoff_only":
        issues.append("visible_effect_has_only_marker_handoff")
    if manual_required and not instruction:
        issues.append("manual_resolve_effect_missing_instruction")
    if issues:
        status = "blocked"

    return {
        "rowIndex": index,
        "status": status,
        "boundarySeconds": round(as_float(candidate.get("boundarySeconds"), 0.0) or 0.0, 3),
        "fromSourceName": source_name(candidate.get("fromSourcePath")),
        "toSourceName": source_name(candidate.get("toSourcePath")),
        "recipeId": recipe.get("recipeId"),
        "resolveEffectName": recipe.get("resolveEffectName"),
        "visibleEffect": visible,
        "manualEffectKind": manual_kind if visible else None,
        "applyMethod": apply_method,
        "ownerScript": owner,
        "manualResolveStepRequired": manual_required,
        "fallbackBridgeInsertRequired": fallback_required,
        "readbackEvidenceRequired": True,
        "markerPayloadReady": marker_payload_ready(markers, index),
        "clipAnnotationPresent": index in clip_rows,
        "manualInstruction": instruction,
        "acceptanceEvidence": evidence,
        "decisionFields": dict(DECISION_FIELDS),
        "issues": issues,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve() if args.skill_dir else Path(__file__).resolve().parents[1]
    output_dir = package_dir / "resolve_transition_apply_plan"
    plan_path = output_dir / "resolve_transition_apply_plan.json"
    md_path = output_dir / "resolve_transition_apply_plan.md"
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, args.blueprint)
    materialization_path = package_dir / "resolve_transition_materialization_contract_audit.json"
    materialization = load_json(materialization_path) or {}
    if not isinstance(blueprint, dict):
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked_resolve_transition_apply_plan",
            "packageDir": str(package_dir),
            "inputs": {
                "blueprint": str(blueprint_path),
                "blueprintExists": blueprint_path.exists(),
                "blueprintKind": blueprint_kind,
                "blueprintInsidePackage": blueprint_inside_package,
                "skillDir": str(skill_dir),
                "resolveApiSupport": DIRECT_TRANSITION_API_STATUS,
            },
            "outputs": {"planJson": str(plan_path), "planMarkdown": str(md_path)},
            "summary": {},
            "transitionApplyRows": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
        write_json(plan_path, report)
        write_markdown(md_path, report)
        return report

    candidates = transition_candidates(blueprint)
    markers = transition_markers(blueprint)
    marker_lookup = markers_by_row(markers)
    clip_rows = clip_annotation_rows(blueprint)
    rows = [classify_row(row, marker_lookup=marker_lookup, clip_rows=clip_rows) for row in candidates]
    blocked_rows = [row for row in rows if row.get("status") == "blocked"]
    manual_rows = [row for row in rows if row.get("manualResolveStepRequired")]
    visible_rows = [row for row in rows if row.get("visibleEffect")]
    marker_only_rows = [row for row in rows if row.get("applyMethod") == "timeline_marker_handoff_only"]
    decision_field_rows = [
        row for row in rows if set(DECISION_FIELDS).issubset(set((row.get("decisionFields") or {}).keys()))
    ]

    blockers: list[str] = []
    warnings: list[str] = []
    if not candidates:
        blockers.append("final blueprint has no transition candidates to apply")
    if not blueprint_inside_package:
        blockers.append(f"blueprint is outside package: {blueprint_path}")
    if not build_timeline_preserves_marker_payload(skill_dir):
        blockers.append("build_resolve_timeline.py does not preserve transition marker payload customData")
    if materialization_path.exists() and materialization.get("status") != "passed":
        blockers.append("resolve_transition_materialization_contract_audit.json is not passed")
    if not materialization_path.exists():
        warnings.append("resolve_transition_materialization_contract_audit.json is missing; run it before Resolve apply approval")
    if manual_rows and not args.allow_planned_manual_visible_effects:
        blockers.append(
            "visible manual Resolve/Fusion transition rows are pending; replace them with clean cuts or materialized bridge clips, "
            "or rerun with --allow-planned-manual-visible-effects only for an explicitly supervised Resolve handoff"
        )
    blockers.extend(f"transition row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[:80])
    if marker_only_rows:
        blockers.append("one or more visible transitions are marker-only with no apply path")
    if manual_rows:
        warnings.append(
            "Resolve Python API has no documented direct adjacent-transition add method; manual Resolve/Fusion/effect steps or bridge clips are required for visible effects"
        )

    summary = {
        "transitionApplyRowCount": len(rows),
        "readyRowCount": len([row for row in rows if str(row.get("status") or "").startswith("ready_")]),
        "blockedRowCount": len(blocked_rows),
        "visibleEffectRowCount": len(visible_rows),
        "visibleEffectRowsWithApplyPath": len([row for row in visible_rows if row.get("applyMethod") != "timeline_marker_handoff_only"]),
        "manualResolveRowCount": len(manual_rows),
        "pendingManualVisibleEffectRowCount": 0 if args.allow_planned_manual_visible_effects else len(manual_rows),
        "plannedManualVisibleEffectsAllowed": bool(args.allow_planned_manual_visible_effects),
        "apiSupportedRowCount": len([row for row in rows if row.get("applyMethod") in {"append_adjacent_clips_cut_on_bgm_hit", "blueprint_bridge_sequence_video_clips"}]),
        "fallbackBridgeRequiredRowCount": len([row for row in rows if row.get("fallbackBridgeInsertRequired")]),
        "markerOnlyBlockedRowCount": len(marker_only_rows),
        "readbackEvidenceRequiredRowCount": len([row for row in rows if row.get("readbackEvidenceRequired")]),
        "decisionFieldRowCount": len(decision_field_rows),
        "blockerCount": len(blockers),
    }
    status = "ready_with_resolve_transition_apply_plan" if not blockers and rows else "blocked_resolve_transition_apply_plan"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "skillDir": str(skill_dir),
            "resolveApiSupport": DIRECT_TRANSITION_API_STATUS,
            "materializationAudit": str(materialization_path),
            "materializationStatus": materialization.get("status"),
        },
        "outputs": {"planJson": str(plan_path), "planMarkdown": str(md_path)},
        "summary": summary,
        "transitionApplyRows": rows,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
        "nextActions": [
            "Run audit_resolve_transition_apply_contract.py before Resolve apply approval.",
            "For unattended first drafts, do not leave manual visible effects pending; use API-supported clean cuts, materialized bridge clips, or completed Resolve readback/frame evidence.",
            "After Resolve apply, run audit_resolve_timeline.py and sample frames around manual/bridge transitions.",
            "Do not call a visible transition applied when only marker customData exists.",
        ],
    }
    write_json(plan_path, report)
    write_markdown(md_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a Resolve transition apply plan.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--skill-dir")
    parser.add_argument(
        "--allow-planned-manual-visible-effects",
        action="store_true",
        help="Allow supervised manual Resolve/Fusion visible-effect rows in the apply plan; default blocks them for unattended delivery.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(Path(args.package_dir), args)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if str(report["status"]).startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
