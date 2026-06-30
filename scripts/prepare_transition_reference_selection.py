#!/usr/bin/env python3
"""Auto-select one reference-calibrated transition candidate per boundary."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any


IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
MOTION_FAMILIES = {"motion_accent"}
BRIDGE_OR_BREATH_FAMILIES = {"physical_bridge", "title_breath", "mood_dissolve"}
FORBIDDEN_TERMS = ("random spin", "flash", "glitch", "shake", "strobe", "particle", "template", "whoosh pack")


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


def clean(value: Any, limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


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


def load_candidate_plan(package_dir: Path) -> dict[str, Any]:
    return load_json(package_dir / "transition_reference_candidates" / "transition_reference_candidates.json") or {}


def row_text(row: dict[str, Any], candidate: dict[str, Any] | None = None) -> str:
    payload = {"row": row}
    if candidate:
        payload["candidate"] = candidate
    return json.dumps(payload, ensure_ascii=False).lower()


def forbidden_hits(row: dict[str, Any], candidate: dict[str, Any] | None = None) -> list[str]:
    text = row_text(row, candidate)
    return sorted({term for term in FORBIDDEN_TERMS if term in text})


def rank_bonus(candidate: dict[str, Any]) -> int:
    rank = str(candidate.get("rank") or "").upper()
    return {"A": 30, "B": 18, "C": 8}.get(rank, 0)


def family_priority(category: str, family: str, candidate_type: str) -> int:
    if category == "title_boundary":
        return {
            "title_breath": 70,
            "mood_dissolve": 36,
            "clean_cut": 28,
            "visual_match": 22,
            "physical_bridge": 18,
            "motion_accent": -90,
        }.get(family, 0)
    if category == "ending_transition":
        return {
            "mood_dissolve": 58,
            "visual_match": 46,
            "clean_cut": 38,
            "title_breath": 12,
            "physical_bridge": 10,
            "motion_accent": -70,
        }.get(family, 0)
    if category in {"chapter_boundary", "timeline_gap"}:
        return {
            "physical_bridge": 78,
            "title_breath": 44,
            "mood_dissolve": 34,
            "visual_match": 26,
            "clean_cut": 18,
            "motion_accent": 6,
        }.get(family, 0)
    if "visual" in candidate_type or family == "visual_match":
        return 54
    if family == "clean_cut":
        return 46
    if family == "physical_bridge":
        return 40
    if family == "mood_dissolve":
        return 24
    if family == "motion_accent":
        return 18
    return 0


def evidence_bonus(row: dict[str, Any], candidate: dict[str, Any]) -> int:
    family = str(candidate.get("styleFamily") or "")
    motion = row.get("motionEvidence") if isinstance(row.get("motionEvidence"), dict) else {}
    required = " ".join(clean(item, 120).lower() for item in candidate.get("requiredEvidence") or [])
    bonus = 0
    if family == "physical_bridge" and (
        motion.get("physicalBridgeEvidence") is True or motion.get("bridgeTerms") or "bridge" in required
    ):
        bonus += 16
    if family == "visual_match" and ("shared terms" in required or "visual" in required or "match" in required):
        bonus += 12
    if family == "motion_accent" and (
        motion.get("physicalBridgeEvidence") is True
        or motion.get("hasTwoSidedMotion") is True
        or motion.get("bridgeTerms")
        or motion.get("fromMotionTerms")
        or motion.get("toMotionTerms")
    ):
        bonus += 10
    if family in {"mood_dissolve", "title_breath"} and ("bgm" in required or "quiet" in required or "title" in required):
        bonus += 8
    return bonus


def risk_penalty(row: dict[str, Any], candidate: dict[str, Any]) -> int:
    penalty = 0
    category = str(row.get("boundaryCategory") or "")
    family = str(candidate.get("styleFamily") or "")
    candidate_type = str(candidate.get("candidateType") or "")
    reject_text = " ".join(clean(item, 140).lower() for item in candidate.get("rejectIf") or [])
    warnings = " ".join(clean(item, 160).lower() for item in row.get("warnings") or [])
    if forbidden_hits(row, candidate):
        penalty += 120
    if family == "motion_accent" and category in {"title_boundary", "ending_transition"}:
        penalty += 100
    if family == "motion_accent" and "static scenic pair" in reject_text:
        penalty += 8
    if "missing route bridge" in reject_text and category in {"chapter_boundary", "timeline_gap"}:
        penalty += 25
    if "duplicate/ghosted title" in reject_text or "subtitles overlap" in reject_text:
        penalty += 20
    if "forbidden effect" in warnings:
        penalty += 25
    if "random" in candidate_type or "template" in candidate_type or "flash" in candidate_type:
        penalty += 200
    return penalty


def score_candidate(row: dict[str, Any], candidate: dict[str, Any]) -> int:
    category = str(row.get("boundaryCategory") or "")
    family = str(candidate.get("styleFamily") or "")
    candidate_type = str(candidate.get("candidateType") or "")
    return (
        rank_bonus(candidate)
        + family_priority(category, family, candidate_type)
        + evidence_bonus(row, candidate)
        - risk_penalty(row, candidate)
    )


def motion_allowed(row_index: int, selected_motion_rows: list[int], max_motion_rows: int) -> bool:
    if len(selected_motion_rows) >= max_motion_rows:
        return False
    return all(abs(row_index - previous) >= 5 for previous in selected_motion_rows)


def choose_candidate(
    row: dict[str, Any],
    *,
    selected_motion_rows: list[int],
    max_motion_rows: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str]]:
    row_index = as_int(row.get("rowIndex"), 0)
    scored: list[dict[str, Any]] = []
    warnings: list[str] = []
    for candidate in row.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        item = dict(candidate)
        family = str(item.get("styleFamily") or "")
        score = score_candidate(row, item)
        reasons: list[str] = [
            f"rank={item.get('rank') or ''}",
            f"family={family}",
            f"baseScore={score}",
        ]
        if family in MOTION_FAMILIES and not motion_allowed(row_index, selected_motion_rows, max_motion_rows):
            score -= 80
            reasons.append("motion quota or spacing penalty")
        if row.get("referenceCandidateStatus") == "needs_bridge_insert_before_effect" and family != "physical_bridge":
            score -= 90
            reasons.append("bridge-required row cannot default to a visible effect")
        if forbidden_hits(row, item):
            reasons.append("forbidden-effect-language penalty")
        item["_selectionScore"] = score
        item["_selectionReasons"] = reasons
        scored.append(item)
    scored.sort(key=lambda item: (as_int(item.get("_selectionScore")), rank_sort(item)), reverse=True)
    selected = scored[0] if scored else None
    if selected and selected.get("styleFamily") in MOTION_FAMILIES:
        if motion_allowed(row_index, selected_motion_rows, max_motion_rows):
            selected_motion_rows.append(row_index)
        else:
            non_motion = next((item for item in scored if item.get("styleFamily") not in MOTION_FAMILIES), None)
            if non_motion:
                warnings.append("Motion candidate was demoted to preserve reference-style spacing and restraint.")
                selected = non_motion
    return selected, scored, warnings


def rank_sort(candidate: dict[str, Any]) -> int:
    return {"A": 3, "B": 2, "C": 1}.get(str(candidate.get("rank") or "").upper(), 0)


def selected_status(row: dict[str, Any], selected: dict[str, Any] | None) -> str:
    if not selected:
        return "blocked_missing_selectable_candidate"
    if row.get("referenceCandidateStatus") == "needs_bridge_insert_before_effect":
        return "blocked_requires_bridge_material"
    if selected.get("styleFamily") == "motion_accent" and forbidden_hits(row, selected):
        return "blocked_forbidden_motion_language"
    return "auto_selected"


def decision_payload(row: dict[str, Any], selected: dict[str, Any], status: str, reasons: list[str]) -> dict[str, Any]:
    evidence = selected.get("requiredEvidence") if isinstance(selected.get("requiredEvidence"), list) else []
    return {
        "rowIndex": row.get("rowIndex"),
        "selectionStatus": status,
        "selectedCandidateRank": selected.get("rank"),
        "selectedCandidateType": selected.get("candidateType"),
        "selectedStyleFamily": selected.get("styleFamily"),
        "selectedIntensity": selected.get("intensity"),
        "durationFrames": selected.get("durationFrames"),
        "selectionScore": selected.get("_selectionScore"),
        "selectionReasons": reasons,
        "approvedBgmHit": next((item for item in evidence if "BGM" in str(item) or "bgm" in str(item)), ""),
        "approvedBridgeOrMotionSource": next((item for item in evidence if "bridge" in str(item).lower() or "motion" in str(item).lower()), ""),
        "approvedTitleQuietZone": next((item for item in evidence if "title" in str(item).lower() or "quiet" in str(item).lower()), ""),
        "resolveImplementation": selected.get("resolveRecipe"),
        "previewOrAuditionEvidence": selected.get("ffmpegPreviewHint"),
        "timelineReadbackEvidence": "pending Resolve readback after apply",
        "renderFrameEvidence": "pending render-frame QA after apply",
        "approvedBy": "auto_reference_selection",
        "approvedAt": datetime.now().isoformat(timespec="seconds"),
        "editorNotes": "Auto-selected from non-copying reference candidates; repair blocked rows before final delivery.",
    }


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    candidate_plan = load_candidate_plan(package_dir)
    candidate_rows = candidate_plan.get("candidateRows") if isinstance(candidate_plan.get("candidateRows"), list) else []
    candidate_summary = candidate_plan.get("summary") if isinstance(candidate_plan.get("summary"), dict) else {}
    transition_count = as_int(candidate_summary.get("transitionRowCount"), len(candidate_rows))
    max_motion_rows = as_int(candidate_summary.get("maxMotionCandidateRows"), 0)
    if transition_count and max_motion_rows <= 0:
        max_motion_rows = max(1, math.floor(transition_count * 0.18))
    selected_motion_rows: list[int] = []
    selection_rows: list[dict[str, Any]] = []
    for row in candidate_rows:
        if not isinstance(row, dict):
            continue
        selected, scored, warnings = choose_candidate(row, selected_motion_rows=selected_motion_rows, max_motion_rows=max_motion_rows)
        status = selected_status(row, selected)
        reasons = list(selected.get("_selectionReasons") or []) if selected else []
        reasons.extend(warnings)
        clean_selected = None
        if selected:
            clean_selected = {key: value for key, value in selected.items() if not key.startswith("_")}
        selection_rows.append(
            {
                "rowIndex": row.get("rowIndex"),
                "boundaryCategory": row.get("boundaryCategory"),
                "timelineStartSeconds": row.get("timelineStartSeconds"),
                "fromSourceName": row.get("fromSourceName"),
                "toSourceName": row.get("toSourceName"),
                "sourceCandidateStatus": row.get("referenceCandidateStatus"),
                "selectionStatus": status,
                "selectedCandidate": clean_selected,
                "candidateScores": [
                    {
                        "rank": item.get("rank"),
                        "candidateType": item.get("candidateType"),
                        "styleFamily": item.get("styleFamily"),
                        "score": item.get("_selectionScore"),
                        "reasons": item.get("_selectionReasons"),
                    }
                    for item in scored
                ],
                "autoDecision": decision_payload(row, selected, status, reasons) if selected else {},
                "warnings": warnings,
            }
        )
    blocked = [row for row in selection_rows if str(row.get("selectionStatus") or "").startswith("blocked")]
    selected_count = sum(1 for row in selection_rows if row.get("selectedCandidate"))
    auto_selected = sum(1 for row in selection_rows if row.get("selectionStatus") == "auto_selected")
    motion_selected = sum(1 for row in selection_rows if (row.get("selectedCandidate") or {}).get("styleFamily") in MOTION_FAMILIES)
    important = sum(1 for row in selection_rows if row.get("boundaryCategory") in IMPORTANT_CATEGORIES)
    important_bridge_breath = sum(
        1
        for row in selection_rows
        if row.get("boundaryCategory") in IMPORTANT_CATEGORIES
        and (row.get("selectedCandidate") or {}).get("styleFamily") in BRIDGE_OR_BREATH_FAMILIES
    )
    style_counts: dict[str, int] = {}
    for row in selection_rows:
        family = str((row.get("selectedCandidate") or {}).get("styleFamily") or "")
        if family:
            style_counts[family] = style_counts.get(family, 0) + 1
    if not candidate_rows:
        status = "blocked_missing_transition_reference_candidates"
    elif blocked:
        status = "blocked_transition_reference_selection_needs_repair"
    else:
        status = "ready_with_transition_reference_selection"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "transitionReferenceCandidates": str(package_dir / "transition_reference_candidates" / "transition_reference_candidates.json"),
            "candidatePlanStatus": candidate_plan.get("status"),
        },
        "summary": {
            "candidateRowCount": len(candidate_rows),
            "selectionRowCount": len(selection_rows),
            "selectedRowCount": selected_count,
            "autoSelectedRowCount": auto_selected,
            "blockedSelectionRowCount": len(blocked),
            "motionSelectedRowCount": motion_selected,
            "maxMotionRows": max_motion_rows,
            "motionSelectedShare": round(motion_selected / selected_count, 3) if selected_count else 0.0,
            "importantBoundaryCount": important,
            "importantRowsWithBridgeOrBreathSelection": important_bridge_breath,
            "importantBridgeOrBreathSelectionCoverage": round(important_bridge_breath / important, 3) if important else 1.0,
            "selectedStyleFamilyCounts": style_counts,
        },
        "selectionPolicy": {
            "nonCopyingReferenceUse": True,
            "autoSelectsDefaultCandidate": True,
            "bridgeRequiredRowsStayBlocked": True,
            "motionAccentsRareAndSpaced": True,
            "forbiddenTemplateEffectsRejected": True,
            "titleAndSubtitleQuietZonePreferred": True,
            "bgmPhraseEvidencePreferred": True,
        },
        "selectionRows": selection_rows,
        "blockers": [
            {
                "rowIndex": row.get("rowIndex"),
                "boundaryCategory": row.get("boundaryCategory"),
                "selectionStatus": row.get("selectionStatus"),
                "requiredRepair": "Add or verify physical bridge/title-breath material before approving a visible transition effect.",
            }
            for row in blocked
        ],
        "nextActions": [
            "Use transition_reference_selection.json as the default transition decision source for unattended first drafts.",
            "Repair blocked rows with bridge_sequence_plan, scenic title bridge, source selection, or visual establishing material before Resolve apply.",
            "Feed selected rows into preview, audition, storyboard, transition polish, Resolve markers, and final QA readback.",
            "Rerun transition profile, final smoothness, V14 baseline, skill maturity, and final QA after Resolve apply.",
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
        "# Transition Reference Selection",
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
        "## Selected Defaults",
    ]
    for row in plan["selectionRows"][:160]:
        selected = row.get("selectedCandidate") or {}
        decision = row.get("autoDecision") or {}
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('boundaryCategory')}",
                f"- Status: `{row.get('selectionStatus')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Selected: `{selected.get('rank')}` `{selected.get('candidateType')}` / `{selected.get('styleFamily')}` / {selected.get('durationFrames')} frames",
                f"- Resolve: {selected.get('resolveRecipe') or ''}",
                f"- Reason: {'; '.join(decision.get('selectionReasons') or [])}",
            ]
        )
    if plan.get("blockers"):
        lines.extend(["", "## Blockers"])
        for blocker in plan["blockers"]:
            lines.append(
                f"- Row {blocker.get('rowIndex')} `{blocker.get('boundaryCategory')}`: {blocker.get('requiredRepair')}"
            )
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-select default transition reference candidates.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_reference_selection.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_reference_selection"
    plan = build_plan(package_dir)
    write_json(output_dir / "transition_reference_selection.json", plan)
    write_markdown(output_dir / "transition_reference_selection.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 2 if str(plan["status"]).startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
