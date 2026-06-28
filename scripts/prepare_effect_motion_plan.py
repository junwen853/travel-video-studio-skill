#!/usr/bin/env python3
"""Prepare restrained title, transition, and route-motion effect planning rows."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "selectedEffectType": "",
    "durationFrames": None,
    "resolveImplementation": "",
    "motionDirection": "",
    "intensity": "subtle",
    "audioTreatment": "bgm_only_no_camera_voice",
    "titleZoneChecked": False,
    "appliedInResolve": False,
    "readbackEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

FORBIDDEN_EFFECT_TERMS = (
    "glitch",
    "shake",
    "random spin",
    "spin template",
    "unmotivated spin",
    "flash",
    "particle",
    "strobe",
    "template pack",
    "logo reveal",
    "neon wipe",
)


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_words(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def lower_text(value: Any) -> str:
    return clean_words(value, limit=1000).lower()


def active_title_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    rows = data.get("titleRows") if isinstance(data.get("titleRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def transition_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json") or {}
    rows = data.get("boundaryRows") if isinstance(data.get("boundaryRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def visual_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json") or {}
    rows = data.get("establishingRows") if isinstance(data.get("establishingRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def effect_plan_items(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("effectPlan") if isinstance(blueprint.get("effectPlan"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def effect_plan_evidence(items: list[dict[str, Any]], needle: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        text = lower_text(" ".join(str(item.get(key) or "") for key in ("name", "style", "status", "role")))
        if needle in text:
            out.append(
                {
                    "name": item.get("name"),
                    "style": item.get("style"),
                    "intensity": item.get("intensity"),
                    "status": item.get("status"),
                }
            )
    return out


def forbidden_effect_hits(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in items:
        text = lower_text(" ".join(str(item.get(key) or "") for key in ("name", "style", "status", "notes")))
        matched = [term for term in FORBIDDEN_EFFECT_TERMS if term in text]
        if "spin" in text and not any(term in text for term in ("whip", "rotation match", "motivated", "route motion")):
            matched.append("unmotivated spin")
        if matched:
            hits.append({"item": item, "forbiddenTerms": matched})
    return hits


def visual_evidence_for_role(rows: list[dict[str, Any]], role: str, chapter_index: Any = None) -> dict[str, Any] | None:
    for row in rows:
        if row.get("role") != role:
            continue
        if chapter_index is not None and str(row.get("chapterIndex") or "") != str(chapter_index):
            continue
        return {
            "status": row.get("status"),
            "chapterIndex": row.get("chapterIndex"),
            "title": row.get("title"),
            "evidenceCount": len(row.get("existingEstablishingEvidence") or []),
        }
    return None


def title_motion_row(row: dict[str, Any], effect_items: list[dict[str, Any]], visual_plan_rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode = clean_words(row.get("mode") or "")
    chapter_index = row.get("chapterIndex")
    role = "opening_title_reveal" if mode == "opening" else ("ending_title_reveal" if mode == "ending" else "chapter_title_reveal")
    visual_role = "opening_city_establishing" if mode == "opening" else ("ending_city_establishing" if mode == "ending" else "chapter_establishing")
    style = "slow opacity fade plus tiny scale settle" if mode == "opening" else "short fade/cross-dissolve, no template reveal"
    effect_needle = "opening" if mode == "opening" else ("ending" if mode == "ending" else "chapter")
    return {
        "rowType": role,
        "chapterIndex": chapter_index,
        "timelineStartSeconds": row.get("timelineStartSeconds"),
        "timelineEndSeconds": row.get("timelineEndSeconds"),
        "targetTitle": row.get("targetTitle") or row.get("titleText"),
        "sourceEvidence": {
            "titleTypography": {
                "mode": mode,
                "role": row.get("role"),
                "cleanTitlePass": row.get("cleanTitlePass"),
                "subtitlePolicyPass": row.get("subtitlePolicyPass"),
                "segmentExists": row.get("segmentExists"),
            },
            "visualEstablishing": visual_evidence_for_role(visual_plan_rows, visual_role, chapter_index if mode == "chapter" else None),
            "blueprintEffectPlan": effect_plan_evidence(effect_items, effect_needle),
        },
        "recommendedMotion": {
            "style": style,
            "durationFrames": 18 if mode == "opening" else 12,
            "intensity": "subtle",
            "mustAvoid": ["duplicate text", "drop shadow clutter", "route/date labels behind hero title", "glitch/spin/flash template reveal"],
        },
        "decision": dict(DECISION_FIELDS),
    }


def transition_motion_row(row: dict[str, Any], effect_items: list[dict[str, Any]]) -> dict[str, Any]:
    required_categories = row.get("requiredVisualCategories") or []
    category_text = lower_text(" ".join(str(item) for item in required_categories))
    route_motion_evidence = any(
        term in category_text
        for term in ("transport", "vehicle", "road", "train", "station", "walking", "window", "aerial", "water", "bridge")
    )
    recommended_style = (
        "motivated dissolve, match cut, or whip-pan/rotation match cut when adjacent bridge clips share route motion"
        if route_motion_evidence
        else "motivated dissolve, match cut by direction/color, or very light route marker; no black-card jump"
    )
    return {
        "rowType": "transition_motion_bridge",
        "boundaryIndex": row.get("boundaryIndex"),
        "afterChapter": row.get("afterChapter"),
        "beforeChapter": row.get("beforeChapter"),
        "routeIntent": row.get("routeIntent"),
        "sourceEvidence": {
            "transitionBridgeStatus": row.get("status"),
            "existingBridgeEvidenceCount": len(row.get("existingBridgeEvidence") or []),
            "requiredVisualCategories": row.get("requiredVisualCategories") or [],
            "blueprintEffectPlan": effect_plan_evidence(effect_items, "bridge") + effect_plan_evidence(effect_items, "transition"),
        },
        "recommendedMotion": {
            "style": recommended_style,
            "durationFrames": 12,
            "intensity": "subtle",
            "routeMotionEvidence": route_motion_evidence,
            "mustAvoid": ["generic wipe", "flash transition", "hard cut between days", "random spin", "motion graphic with no route evidence"],
        },
        "decision": dict(DECISION_FIELDS),
    }


def build_rows(package_dir: Path, blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    effects = effect_plan_items(blueprint)
    visual = visual_rows(package_dir)
    rows: list[dict[str, Any]] = []
    for title in active_title_rows(package_dir):
        rows.append(title_motion_row(title, effects, visual))
    for transition in transition_rows(package_dir):
        rows.append(transition_motion_row(transition, effects))
    for index, row in enumerate(rows, start=1):
        row["rowIndex"] = index
        source = row.get("sourceEvidence") if isinstance(row.get("sourceEvidence"), dict) else {}
        has_title = bool((source.get("titleTypography") or {}).get("segmentExists"))
        has_visual = bool((source.get("visualEstablishing") or {}).get("evidenceCount"))
        has_bridge = int((source.get("existingBridgeEvidenceCount") or 0)) > 0
        row["status"] = "has_source_evidence" if (has_title or has_visual or has_bridge) else "needs_source_evidence"
    return rows


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    effects = effect_plan_items(blueprint)
    rows = build_rows(package_dir, blueprint)
    rows_with_source = sum(1 for row in rows if row.get("status") == "has_source_evidence")
    rows_with_decision_fields = sum(
        1
        for row in rows
        if isinstance(row.get("decision"), dict) and set(DECISION_FIELDS).issubset(set(row["decision"]))
    )
    forbidden_hits = forbidden_effect_hits(effects)
    status = (
        "ready_with_restrained_effect_plan"
        if rows and rows_with_source == len(rows) and len(effects) >= 2 and not forbidden_hits
        else ("needs_effect_motion_decisions" if rows else "blocked_missing_title_or_transition_rows")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "titleTypographyPlan": str(package_dir / "title_typography_plan" / "title_typography_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "visualEstablishingPlan": str(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json"),
        },
        "summary": {
            "effectPlanCount": len(effects),
            "effectRowCount": len(rows),
            "rowsWithSourceEvidence": rows_with_source,
            "rowsWithDecisionFields": rows_with_decision_fields,
            "forbiddenEffectHitCount": len(forbidden_hits),
            "titleMotionRowCount": sum(1 for row in rows if "title_reveal" in str(row.get("rowType"))),
            "transitionMotionRowCount": sum(1 for row in rows if row.get("rowType") == "transition_motion_bridge"),
        },
        "policy": {
            "restrainedEffectsOnly": True,
            "motivatedWhipOrRotationAllowed": True,
            "noTemplateHeavyTransitions": True,
            "noBlackCardFallback": True,
            "titleZoneCheckedBeforeMotion": True,
            "audioMode": "bgm_only_no_camera_voice",
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
        "blueprintEffectPlan": effects,
        "forbiddenEffectHits": forbidden_hits,
        "effectRows": rows,
        "selectionRubric": {
            "pass": [
                "Every opening/chapter/ending title reveal is restrained, readable, and backed by clean title/source evidence.",
                "Every transition motion row is motivated by bridge footage, route motion, color, direction, or BGM phrasing.",
                "Effects remain subtle: fades, short dissolves, tiny scale settles, match cuts, motivated whip-pan/rotation match cuts, or simple route markers.",
                "No effect hides duplicate titles, black cards, sparse subtitles, missing BGM, or wrong route evidence.",
            ],
            "reject": [
                "Glitch, random spin, flash, shake, particle, logo-reveal, or generic template-pack effects.",
                "Motion graphics that replace real route/bridge footage instead of supporting it.",
                "Any title reveal that causes stacked/ghosted text or subtitle overlap in title zones.",
                "Transitions that feel like a short-video template instead of observed travel.",
            ],
        },
        "nextActions": [
            "Fill decision fields for any row that will be implemented in Resolve.",
            "Update resolve_timeline_blueprint.json effectPlan when effect choices become concrete.",
            "After Resolve apply, confirm readback evidence and rerun audit_director_polish_contract.py.",
            "Use whip/rotation only as a route-motion match cut; fix missing BGM, title, or bridge evidence instead of masking it with effects.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Effect Motion Plan",
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
        "## Blueprint Effect Plan",
    ]
    if plan["blueprintEffectPlan"]:
        for item in plan["blueprintEffectPlan"]:
            lines.append(f"- {item.get('name')}: {item.get('style')} (`{item.get('status')}`)")
    else:
        lines.append("- None yet.")
    lines.extend(["", "## Effect Rows"])
    for row in plan["effectRows"]:
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['rowType']}",
                f"- Status: `{row['status']}`",
                f"- Recommended motion: {row['recommendedMotion']['style']}",
                f"- Intensity: `{row['recommendedMotion']['intensity']}`",
                f"- Duration frames: `{row['recommendedMotion']['durationFrames']}`",
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
    parser = argparse.ArgumentParser(description="Prepare a restrained effect/motion plan for a travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/effect_motion_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "effect_motion_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "effect_motion_plan.json", plan)
    write_markdown(output_dir / "effect_motion_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
