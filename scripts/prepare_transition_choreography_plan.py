#!/usr/bin/env python3
"""Prepare director-style transition choreography rows from execution evidence."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
MOTION_STYLES = {"whip_pan_match", "rotation_match_cut", "speed_ramp_bridge", "whip_pan", "rotation", "speed_ramp", "push_slide"}
FORBIDDEN_TERMS = ("random spin", "glitch", "flash", "shake", "strobe", "template", "particle", "whoosh")
DECISION_FIELDS = {
    "approvedChoreographyFamily": "",
    "approvedMiddleBeatSource": "",
    "approvedBgmHit": "",
    "approvedCaptionQuietZone": "",
    "approvedIntensity": "",
    "resolveImplementation": "",
    "auditionEvidence": "",
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


def rows_from_execution(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_execution_plan" / "transition_execution_plan.json") or {}
    rows = data.get("executionRows") if isinstance(data.get("executionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def rows_from_grammar(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json") or {}
    rows = data.get("transitionRows") if isinstance(data.get("transitionRows"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rec = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
        out.append(
            {
                "rowIndex": row.get("rowIndex"),
                "boundaryCategory": row.get("boundaryCategory"),
                "fromClip": row.get("fromClip"),
                "toClip": row.get("toClip"),
                "grammarStatus": row.get("status"),
                "grammarRecommendation": rec,
                "executionRecipe": {
                    "style": rec.get("recommendedTransitionType"),
                    "resolveEffectName": rec.get("recommendedTransitionType"),
                    "durationFrames": rec.get("durationFrames"),
                    "trackOperation": "grammar_only_pending_execution_recipe",
                },
                "motionEvidence": {
                    "physicalBridgeEvidence": rec.get("physicalBridgeEvidence") is True,
                    "motionEffectAllowedByGrammar": rec.get("motionEffectAllowed") is True,
                    "bridgeTerms": (row.get("signals") or {}).get("bridgeTerms") if isinstance(row.get("signals"), dict) else [],
                    "fromMotionTerms": (row.get("signals") or {}).get("fromMotionTerms") if isinstance(row.get("signals"), dict) else [],
                    "toMotionTerms": (row.get("signals") or {}).get("toMotionTerms") if isinstance(row.get("signals"), dict) else [],
                    "hasTwoSidedMotion": bool((row.get("signals") or {}).get("fromMotionTerms") and (row.get("signals") or {}).get("toMotionTerms")) if isinstance(row.get("signals"), dict) else False,
                    "hasRouteBridgeTerms": bool((row.get("signals") or {}).get("bridgeTerms")) if isinstance(row.get("signals"), dict) else False,
                },
                "status": "ready_with_transition_execution_recipe" if row.get("status") == "ready_with_transition_grammar" else row.get("status"),
            }
        )
    return out


def source_name(clip: Any) -> str:
    clip = clip if isinstance(clip, dict) else {}
    source = clean(clip.get("sourcePath") or clip.get("sourceName") or clip.get("name"))
    return Path(source).name if source else ""


def row_style(row: dict[str, Any]) -> str:
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    rec = row.get("grammarRecommendation") if isinstance(row.get("grammarRecommendation"), dict) else {}
    text = " ".join(
        clean(value).lower()
        for value in (
            recipe.get("style"),
            recipe.get("resolveEffectName"),
            recipe.get("trackOperation"),
            decision.get("approvedTransitionType"),
            rec.get("recommendedTransitionType"),
        )
    )
    if "whip" in text:
        return "whip_pan"
    if "rotation" in text:
        return "rotation"
    if "speed" in text or "ramp" in text:
        return "speed_ramp"
    if "push" in text or "slide" in text:
        return "push_slide"
    if "dissolve" in text or "cross" in text:
        return "dissolve"
    if "match" in text:
        return "match_cut"
    if "bridge" in text:
        return "bridge_insert"
    return "clean_cut"


def has_forbidden_text(row: dict[str, Any]) -> list[str]:
    text = json.dumps(row, ensure_ascii=False).lower()
    return sorted({term for term in FORBIDDEN_TERMS if term in text})


def motion_evidence(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("motionEvidence") if isinstance(row.get("motionEvidence"), dict) else {}
    return {
        "physicalBridgeEvidence": evidence.get("physicalBridgeEvidence") is True,
        "motionEffectAllowedByGrammar": evidence.get("motionEffectAllowedByGrammar") is True,
        "hasTwoSidedMotion": evidence.get("hasTwoSidedMotion") is True,
        "hasRouteBridgeTerms": evidence.get("hasRouteBridgeTerms") is True,
        "fromMotionTerms": evidence.get("fromMotionTerms") if isinstance(evidence.get("fromMotionTerms"), list) else [],
        "toMotionTerms": evidence.get("toMotionTerms") if isinstance(evidence.get("toMotionTerms"), list) else [],
        "bridgeTerms": evidence.get("bridgeTerms") if isinstance(evidence.get("bridgeTerms"), list) else [],
    }


def bridge_supported(row: dict[str, Any], evidence: dict[str, Any]) -> bool:
    return bool(
        row.get("bridgeSequenceSatisfied")
        or evidence.get("physicalBridgeEvidence")
        or evidence.get("hasRouteBridgeTerms")
        or evidence.get("bridgeTerms")
    )


def family_for(row: dict[str, Any], style: str, evidence: dict[str, Any]) -> str:
    category = clean(row.get("boundaryCategory")).lower()
    if category == "ending_transition":
        return "ending_aftertaste_hold"
    if category == "title_boundary":
        return "scenic_title_breath"
    if category in {"chapter_boundary", "timeline_gap"}:
        return "route_bridge_triptych" if bridge_supported(row, evidence) else "bridge_required_before_effect"
    if style in {"whip_pan", "rotation", "speed_ramp", "push_slide"}:
        return "motivated_motion_accent"
    if style == "match_cut":
        return "visual_match_cut"
    if style == "dissolve":
        return "mood_dissolve_breath"
    if bridge_supported(row, evidence):
        return "texture_bridge_cutaway"
    return "clean_continuity_cut"


def intensity_for(style: str, family: str, evidence: dict[str, Any]) -> int:
    if family in {"ending_aftertaste_hold", "scenic_title_breath", "mood_dissolve_breath"}:
        return 1
    if style == "speed_ramp":
        return 2 if bridge_supported({}, evidence) else 1
    if style in {"whip_pan", "push_slide"}:
        return 2
    if style == "rotation":
        return 1
    return 0


def choreography_beats(row: dict[str, Any], family: str, style: str, intensity: int, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    outgoing = source_name(row.get("fromClip"))
    landing = source_name(row.get("toClip"))
    beats = [
        {
            "role": "outgoing",
            "durationFrames": 10 if intensity else 6,
            "action": f"leave on a readable last action or scenic edge from {outgoing or 'the outgoing shot'}",
        }
    ]
    if family == "route_bridge_triptych":
        middle = "insert 1-3 short route texture shots: transport, street, signage, weather, hotel, food, water, skyline, or aerial"
    elif family == "bridge_required_before_effect":
        middle = "block visible effect until real route bridge footage or a verified bridge sequence exists"
    elif family == "motivated_motion_accent":
        terms = ", ".join((evidence.get("fromMotionTerms") or [])[:3] + (evidence.get("toMotionTerms") or [])[:3])
        middle = f"use a restrained {style} only on the BGM hit and only matching source motion ({terms or 'motion evidence required'})"
    elif family == "visual_match_cut":
        middle = "cut on shared shape, object, color, skyline, water, road, food, sign, or camera direction"
    elif family == "scenic_title_breath":
        middle = "hold the title-safe scenic frame, suppress subtitles, then hand off on a clean BGM phrase"
    elif family == "ending_aftertaste_hold":
        middle = "slow down into an aftertaste hold; avoid new information or decorative motion"
    elif family == "mood_dissolve_breath":
        middle = "use a short dissolve for mood, time, weather, or evening breath"
    elif family == "texture_bridge_cutaway":
        middle = "insert one lived-in texture beat before landing"
    else:
        middle = "keep the cut invisible; do not add a visible effect without stronger evidence"
    beats.append({"role": "bridge_or_motion", "durationFrames": 12 + intensity * 4, "action": middle})
    beats.append(
        {
            "role": "landing",
            "durationFrames": 10 if family in {"scenic_title_breath", "ending_aftertaste_hold"} else 6,
            "action": f"land on a stable first readable moment from {landing or 'the landing shot'} and hold long enough for orientation",
        }
    )
    return beats


def build_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    style = row_style(row)
    evidence = motion_evidence(row)
    family = family_for(row, style, evidence)
    intensity = intensity_for(style, family, evidence)
    category = clean(row.get("boundaryCategory")).lower() or "adjacent_clip_boundary"
    important = category in IMPORTANT_CATEGORIES
    motion_style = style in {"whip_pan", "rotation", "speed_ramp", "push_slide"}
    issues: list[str] = []
    if family == "bridge_required_before_effect":
        issues.append("important_route_boundary_missing_bridge_before_effect")
    if important and family in {"clean_continuity_cut", "mood_dissolve_breath"} and not bridge_supported(row, evidence):
        issues.append("important_boundary_lacks_middle_bridge_or_motion_beat")
    if motion_style and not (evidence.get("motionEffectAllowedByGrammar") and (bridge_supported(row, evidence) or evidence.get("hasTwoSidedMotion"))):
        issues.append("motion_transition_lacks_source_motion_or_bridge_evidence")
    if style == "rotation" and intensity > 1:
        issues.append("rotation_intensity_too_high")
    forbidden = has_forbidden_text(row)
    if forbidden:
        issues.append("forbidden_template_or_flash_transition_language")
    beats = choreography_beats(row, family, style, intensity, evidence)
    return {
        "rowIndex": as_int(row.get("rowIndex"), index),
        "status": "ready_with_transition_choreography" if not issues else "needs_transition_choreography_repair",
        "boundaryCategory": category,
        "importantBoundary": important,
        "fromSourceName": source_name(row.get("fromClip")),
        "toSourceName": source_name(row.get("toClip")),
        "sourceExecutionStatus": row.get("status"),
        "choreographyFamily": family,
        "sourceTransitionStyle": style,
        "intensity": intensity,
        "threeBeatChoreography": beats,
        "bgmChoreography": {
            "target": "cut_or_effect_on_bgm_phrase_hit",
            "hitToleranceSeconds": 0.35,
            "allowOffPhrase": False,
        },
        "captionAndTitlePolicy": {
            "quietZoneBeforeSeconds": 0.35,
            "quietZoneAfterSeconds": 0.35,
            "avoidTitleCollision": True,
            "suppressSubtitlesDuringHeroTitleOrFastMotion": True,
        },
        "motionEvidence": evidence,
        "forbiddenHits": forbidden,
        "issues": issues,
        "decision": dict(DECISION_FIELDS),
    }


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


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    rows = rows_from_execution(package_dir)
    input_kind = "transition_execution_plan"
    if not rows:
        rows = rows_from_grammar(package_dir)
        input_kind = "transition_grammar_plan"
    choreography_rows = [build_row(row, index) for index, row in enumerate(rows, start=1)]
    blocked_rows = [row for row in choreography_rows if row.get("status") != "ready_with_transition_choreography"]
    families = [clean(row.get("choreographyFamily")) for row in choreography_rows]
    family_counts: dict[str, int] = {}
    for family in families:
        family_counts[family] = family_counts.get(family, 0) + 1
    dominant_share = max(family_counts.values()) / len(families) if families else 0.0
    dominant_share_ok = len(families) < 4 or dominant_share <= 0.7
    status = (
        "ready_with_transition_choreography_plan"
        if choreography_rows and not blocked_rows and max_run(families) <= 4 and dominant_share_ok
        else ("blocked_missing_transition_inputs" if not choreography_rows else "needs_transition_choreography_repair")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "inputKind": input_kind,
            "transitionExecutionPlan": str(package_dir / "transition_execution_plan" / "transition_execution_plan.json"),
            "transitionGrammarPlan": str(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json"),
            "referenceBatchProfile": str(package_dir / "reference" / "reference_batch_profile.json"),
        },
        "summary": {
            "transitionRowCount": len(choreography_rows),
            "readyChoreographyRowCount": len(choreography_rows) - len(blocked_rows),
            "blockedChoreographyRowCount": len(blocked_rows),
            "importantBoundaryCount": sum(1 for row in choreography_rows if row.get("importantBoundary")),
            "importantRowsWithThreeBeatCount": sum(1 for row in choreography_rows if row.get("importantBoundary") and len(row.get("threeBeatChoreography") or []) >= 3),
            "motionChoreographyRowCount": sum(1 for row in choreography_rows if row.get("sourceTransitionStyle") in {"whip_pan", "rotation", "speed_ramp", "push_slide"}),
            "highIntensityRowCount": sum(1 for row in choreography_rows if as_int(row.get("intensity")) >= 3),
            "rotationRowCount": sum(1 for row in choreography_rows if row.get("sourceTransitionStyle") == "rotation"),
            "maxFamilyRun": max_run(families),
            "dominantFamilyShare": round(dominant_share, 3),
            "choreographyFamilyCounts": family_counts,
        },
        "choreographyRows": choreography_rows,
        "blockers": [f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[:12]],
        "policy": {
            "threeBeatFlowForImportantBoundaries": True,
            "motionNeedsSourceMotionOrBridgeEvidence": True,
            "rotationMustStaySubtle": True,
            "bgmHitRequired": True,
            "captionQuietZoneRequired": True,
            "templateEffectsRejected": True,
        },
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Choreography Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan["summary"], ensure_ascii=False, indent=2),
        "```",
    ]
    if plan.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in plan["blockers"])
    lines.extend(["", "## Choreography Rows"])
    for row in plan["choreographyRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('choreographyFamily')}`",
                f"- Status: `{row.get('status')}`",
                f"- Style: `{row.get('sourceTransitionStyle')}` intensity=`{row.get('intensity')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
            ]
        )
        for beat in row.get("threeBeatChoreography") or []:
            lines.append(f"- {beat.get('role')}: {beat.get('action')}")
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare director-style transition choreography rows.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_choreography_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "transition_choreography_plan.json", plan)
    write_markdown(output_dir / "transition_choreography_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "summary": plan["summary"], "blockers": plan["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if plan["status"] == "ready_with_transition_choreography_plan" else 2


if __name__ == "__main__":
    raise SystemExit(main())
