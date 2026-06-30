#!/usr/bin/env python3
"""Prepare a film-level transition motif plan from grammar and execution rows."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


MOTION_STYLES = {"whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
SIMPLE_STYLES = {"straight_cut", "match_cut", "short_dissolve"}

DECISION_FIELDS = {
    "approvedMotif": "",
    "approvedResolveExecutionRow": "",
    "selectedBridgeOrMatchEvidence": "",
    "bgmPhraseCue": "",
    "captionTitleZoneEvidence": "",
    "styleVariationDecision": "",
    "appliedInResolve": "",
    "timelineReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

REPAIR_DECISION_FIELDS = {
    "acceptedRepair": "",
    "repairAppliedAt": "",
    "postRepairArtifact": "",
    "postRepairAudit": "",
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


def clean_words(value: Any, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def execution_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_execution_plan" / "transition_execution_plan.json") or {}
    rows = data.get("executionRows") if isinstance(data.get("executionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def grammar_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json") or {}
    rows = data.get("transitionRows") if isinstance(data.get("transitionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def summary_of(package_dir: Path, rel: str) -> dict[str, Any]:
    data = load_json(package_dir / rel) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return {"status": data.get("status"), **summary}


def source_name(clip: dict[str, Any] | None) -> str:
    clip = clip if isinstance(clip, dict) else {}
    source = str(clip.get("sourcePath") or clip.get("sourceName") or "")
    return Path(source).name if source else ""


def row_style(row: dict[str, Any]) -> str:
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    style = str(recipe.get("style") or "")
    if style:
        return style
    rec = row.get("grammarRecommendation") if isinstance(row.get("grammarRecommendation"), dict) else {}
    return str(rec.get("recommendedTransitionType") or "unknown")


def grammar_lookup(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            lookup[int(row.get("rowIndex"))] = row
        except (TypeError, ValueError):
            continue
    return lookup


def motif_for_row(row: dict[str, Any], grammar: dict[str, Any] | None) -> tuple[str, list[str]]:
    grammar = grammar if isinstance(grammar, dict) else {}
    style = row_style(row)
    category = str(row.get("boundaryCategory") or grammar.get("boundaryCategory") or "")
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    motion = row.get("motionEvidence") if isinstance(row.get("motionEvidence"), dict) else {}
    grammar_rec = grammar.get("recommendation") if isinstance(grammar.get("recommendation"), dict) else {}
    shared = grammar_rec.get("sharedMatchTerms") if isinstance(grammar_rec.get("sharedMatchTerms"), list) else []
    bridge_terms = motion.get("bridgeTerms") if isinstance(motion.get("bridgeTerms"), list) else []
    reasons: list[str] = []
    if row.get("requiresBridgeInsert") or style == "insert_bridge_first":
        return "blocked_bridge_insert", ["requires physical bridge footage before any effect"]
    if category == "title_boundary":
        reasons.append("title boundary needs clean title-zone timing")
        return "title_clean_reveal", reasons
    if style in MOTION_STYLES:
        reasons.append("motion style is only valid with route-motion evidence")
        return "motivated_motion", reasons
    if style in {"match_cut", "none_or_2_frame_soft_cut"} or shared:
        reasons.append("shared visual terms or shape/action continuity")
        return "visual_match", reasons
    if style == "short_dissolve" or "Dissolve" in str(recipe.get("resolveEffectName") or ""):
        reasons.append("mood, time, weather, title, or aftertaste dissolve")
        return "mood_dissolve", reasons
    if bridge_terms or motion.get("physicalBridgeEvidence"):
        reasons.append("physical route bridge terms exist")
        return "physical_route_bridge", reasons
    return "simple_continuity", ["same-scene or low-motion continuity"]


def repeated_runs(styles: list[str]) -> tuple[int, list[dict[str, Any]]]:
    if not styles:
        return 0, []
    runs: list[dict[str, Any]] = []
    best = 1
    current_style = styles[0]
    start = 0
    for index, style in enumerate(styles[1:], start=1):
        if style == current_style:
            best = max(best, index - start + 1)
            continue
        if index - start >= 4:
            runs.append({"style": current_style, "startRow": start + 1, "endRow": index, "length": index - start})
        current_style = style
        start = index
    if len(styles) - start >= 4:
        runs.append({"style": current_style, "startRow": start + 1, "endRow": len(styles), "length": len(styles) - start})
    return best, runs


def motif_row(row: dict[str, Any], grammar: dict[str, Any] | None) -> dict[str, Any]:
    motif, reasons = motif_for_row(row, grammar)
    style = row_style(row)
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    motion = row.get("motionEvidence") if isinstance(row.get("motionEvidence"), dict) else {}
    status = "ready_with_transition_motif"
    if motif == "blocked_bridge_insert" or row.get("status", "").startswith("blocked"):
        status = "needs_transition_motif_repair"
    if style in MOTION_STYLES and row.get("motionHasEvidence") is not True:
        status = "needs_transition_motif_repair"
        reasons.append("motion style lacks sufficient two-sided/route bridge evidence")
    if row.get("forbiddenRecipeHits"):
        status = "needs_transition_motif_repair"
        reasons.append("forbidden transition recipe term detected")
    bgm_cue = clean_words(recipe.get("bgmPhraseCue") or (row.get("decision") or {}).get("bgmPhraseCue") or "")
    if not bgm_cue:
        status = "needs_transition_motif_repair"
        reasons.append("missing BGM phrase cue")
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": row.get("boundaryCategory"),
        "fromClip": row.get("fromClip"),
        "toClip": row.get("toClip"),
        "executionStyle": style,
        "motif": motif,
        "motifReasons": reasons,
        "bgmPhraseCue": bgm_cue,
        "bridgeEvidence": {
            "physicalBridgeEvidence": motion.get("physicalBridgeEvidence"),
            "bridgeTerms": motion.get("bridgeTerms") or [],
            "hasTwoSidedMotion": motion.get("hasTwoSidedMotion"),
            "hasRouteBridgeTerms": motion.get("hasRouteBridgeTerms"),
        },
        "titleZonePolicy": recipe.get("subtitlePolicy"),
        "resolveEffectName": recipe.get("resolveEffectName"),
        "durationFrames": recipe.get("durationFrames"),
        "status": status,
        "decision": dict(DECISION_FIELDS),
    }


def repair_rows(rows: list[dict[str, Any]], style_runs: list[dict[str, Any]], dominant: tuple[str, float] | None) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != "needs_transition_motif_repair":
            continue
        motif = str(row.get("motif") or "")
        if motif == "blocked_bridge_insert":
            owner = "prepare_transition_bridge_plan.py"
            artifact = "transition_bridge_plan/transition_bridge_plan.json"
            action = "Insert or select real bridge footage before approving any effect."
        elif str(row.get("executionStyle") or "") in MOTION_STYLES:
            owner = "prepare_effect_motion_plan.py"
            artifact = "effect_motion_plan/effect_motion_plan.json"
            action = "Downgrade unmotivated motion to match_cut/short_dissolve or add real two-sided motion evidence."
        elif not row.get("bgmPhraseCue"):
            owner = "prepare_bgm_selection_package.py"
            artifact = "bgm_selection_package/bgm_selection_package.json"
            action = "Add a BGM phrase cue or section transition cue before Resolve apply."
        else:
            owner = "prepare_transition_execution_plan.py"
            artifact = "transition_execution_plan/transition_execution_plan.json"
            action = "Repair the execution recipe and rerun motif planning."
        repairs.append(
            {
                "repairId": f"transition_motif_row_{row.get('rowIndex')}",
                "priority": "P0",
                "issueType": motif or "transition_motif",
                "transitionRowIndices": [row.get("rowIndex")],
                "ownerScript": owner,
                "requiredArtifact": artifact,
                "repairAction": action,
                "acceptanceEvidence": "transition_motif_plan row returns to ready_with_transition_motif and V14/maturity gates include the repaired artifact.",
                "status": "needs_repair",
                "decision": dict(REPAIR_DECISION_FIELDS),
            }
        )
    for run in style_runs:
        repairs.append(
            {
                "repairId": f"transition_style_run_{run['startRow']}_{run['endRow']}",
                "priority": "P1",
                "issueType": "repeated_transition_style",
                "transitionRowIndices": list(range(int(run["startRow"]), int(run["endRow"]) + 1)),
                "ownerScript": "prepare_transition_grammar_plan.py",
                "requiredArtifact": "transition_grammar_plan/transition_grammar_plan.json",
                "repairAction": "Review the repeated style run and vary only where source evidence supports a match cut, route bridge, title reveal, or mood dissolve.",
                "acceptanceEvidence": "repeatedStyleRunMax drops below 4 or the run is justified by same-scene continuity notes.",
                "status": "needs_review",
                "decision": dict(REPAIR_DECISION_FIELDS),
            }
        )
    if dominant and dominant[1] > 0.7:
        repairs.append(
            {
                "repairId": "transition_dominant_motif_share",
                "priority": "P1",
                "issueType": "dominant_transition_motif",
                "transitionRowIndices": [],
                "ownerScript": "prepare_transition_grammar_plan.py",
                "requiredArtifact": "transition_grammar_plan/transition_grammar_plan.json",
                "repairAction": f"Audit why motif `{dominant[0]}` dominates the film; keep it only when source continuity proves it.",
                "acceptanceEvidence": "dominantMotifShare is justified in editor notes or reduced through real bridge/match evidence.",
                "status": "needs_review",
                "decision": dict(REPAIR_DECISION_FIELDS),
            }
        )
    return repairs


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    grammar = grammar_lookup(grammar_rows(package_dir))
    rows = [motif_row(row, grammar.get(int(row.get("rowIndex") or -1))) for row in execution_rows(package_dir)]
    decision_keys = set(DECISION_FIELDS)
    rows_with_decisions = sum(1 for row in rows if decision_keys.issubset(set((row.get("decision") or {}).keys())))
    rows_ready = sum(1 for row in rows if row.get("status") == "ready_with_transition_motif")
    rows_bgm = sum(1 for row in rows if row.get("bgmPhraseCue"))
    rows_title_safe = sum(1 for row in rows if row.get("boundaryCategory") != "title_boundary" or "title" in str(row.get("titleZonePolicy") or ""))
    rows_with_bridge = sum(1 for row in rows if (row.get("bridgeEvidence") or {}).get("physicalBridgeEvidence") or (row.get("bridgeEvidence") or {}).get("bridgeTerms"))
    styles = [str(row.get("executionStyle") or "") for row in rows]
    motifs = [str(row.get("motif") or "") for row in rows]
    style_counts: dict[str, int] = {}
    motif_counts: dict[str, int] = {}
    for style in styles:
        style_counts[style] = style_counts.get(style, 0) + 1
    for motif in motifs:
        motif_counts[motif] = motif_counts.get(motif, 0) + 1
    run_max, runs = repeated_runs(styles)
    dominant = None
    if motif_counts and rows:
        name, count = max(motif_counts.items(), key=lambda item: item[1])
        dominant = (name, round(count / len(rows), 4))
    repairs = repair_rows(rows, runs, dominant)
    status = (
        "ready_with_transition_motif_plan"
        if rows and rows_with_decisions == len(rows)
        else ("blocked_missing_transition_inputs" if not rows else "needs_transition_motif_decisions")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "transitionGrammarPlan": str(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json"),
            "transitionExecutionPlan": str(package_dir / "transition_execution_plan" / "transition_execution_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "effectMotionPlan": str(package_dir / "effect_motion_plan" / "effect_motion_plan.json"),
            "bgmSelectionPackage": str(package_dir / "bgm_selection_package" / "bgm_selection_package.json"),
            "chapterArcPlan": str(package_dir / "chapter_arc_plan" / "chapter_arc_plan.json"),
        },
        "summary": {
            "transitionRowCount": len(rows),
            "rowsReadyWithMotif": rows_ready,
            "rowsWithDecisionFields": rows_with_decisions,
            "rowsWithBgmPhraseCue": rows_bgm,
            "titleBoundaryRowsSafe": rows_title_safe,
            "rowsWithBridgeEvidence": rows_with_bridge,
            "styleCounts": style_counts,
            "motifCounts": motif_counts,
            "repeatedStyleRunMax": run_max,
            "repeatedStyleRunCount": len(runs),
            "dominantMotif": dominant[0] if dominant else None,
            "dominantMotifShare": dominant[1] if dominant else 0,
            "blockedMotifRowCount": len([row for row in rows if row.get("status") != "ready_with_transition_motif"]),
            "repairRowCount": len(repairs),
        },
        "upstreamEvidence": {
            "transitionGrammar": summary_of(package_dir, "transition_grammar_plan/transition_grammar_plan.json"),
            "transitionExecution": summary_of(package_dir, "transition_execution_plan/transition_execution_plan.json"),
            "transitionBridge": summary_of(package_dir, "transition_bridge_plan/transition_bridge_plan.json"),
            "effectMotion": summary_of(package_dir, "effect_motion_plan/effect_motion_plan.json"),
            "bgmSelection": summary_of(package_dir, "bgm_selection_package/bgm_selection_package.json"),
            "chapterArc": summary_of(package_dir, "chapter_arc_plan/chapter_arc_plan.json"),
        },
        "policy": {
            "filmLevelTransitionMotifsRequired": True,
            "avoidSingleStyleDefaultChain": True,
            "physicalBridgeBeforeMotionEffect": True,
            "motionMotifsNeedEvidence": True,
            "bgmPhraseCueRequired": True,
            "titleZoneSafetyRequired": True,
            "templateTransitionsRejected": True,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "motifRows": rows,
        "repairRows": repairs,
        "selectionRubric": {
            "pass": [
                "The transition chain uses motifs intentionally: physical bridge, visual match, mood dissolve, clean title reveal, motivated motion, or simple continuity.",
                "Repeated transition styles are reviewed instead of becoming an invisible default.",
                "Motion motifs cite route/bridge/two-sided movement evidence.",
                "Every transition has a BGM phrase cue and title-zone safety policy where relevant.",
                "Any missing bridge, BGM cue, title-zone risk, or unmotivated motion has an owner script before Resolve apply.",
            ],
            "reject": [
                "Four or more adjacent transitions repeat the same style without an explicit continuity reason.",
                "A rotation, whip, ramp, flash, glitch, or template effect hides weak footage.",
                "A route jump has no physical bridge or motif repair row.",
                "Transition rows lack BGM phrase cues or title-zone safety for title boundaries.",
            ],
        },
        "nextActions": [
            "Review motifRows before copying any transition recipe into a Resolve apply contract.",
            "Resolve P0 repair rows before final render or V14 baseline claims.",
            "Use P1 repeated-style rows to decide whether the chain needs more match cuts, real bridge inserts, or simpler straight cuts.",
            "After Resolve write, paste readback and frame-sample evidence into motif row decisions.",
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
        "# Transition Motif Plan",
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
        "## Motif Rows",
    ]
    for row in plan["motifRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('motif')}",
                f"- Status: `{row.get('status')}`",
                f"- From: `{source_name(row.get('fromClip'))}`",
                f"- To: `{source_name(row.get('toClip'))}`",
                f"- Style: `{row.get('executionStyle')}`",
                f"- BGM cue: `{row.get('bgmPhraseCue')}`",
                f"- Reasons: {', '.join(row.get('motifReasons') or [])}",
            ]
        )
    if plan["repairRows"]:
        lines.extend(["", "## Repair Rows"])
        for row in plan["repairRows"]:
            lines.extend(
                [
                    "",
                    f"### {row['repairId']}",
                    f"- Priority: `{row['priority']}`",
                    f"- Issue: `{row['issueType']}`",
                    f"- Owner: `{row['ownerScript']}`",
                    f"- Required artifact: `{row['requiredArtifact']}`",
                    f"- Action: {row['repairAction']}",
                ]
            )
    lines.extend(["", "## Pass Rubric"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "## Reject Rubric"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a film-level transition motif plan.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_motif_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_motif_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "transition_motif_plan.json", plan)
    write_markdown(output_dir / "transition_motif_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 2 if plan["status"] == "blocked_missing_transition_inputs" else 0


if __name__ == "__main__":
    raise SystemExit(main())
