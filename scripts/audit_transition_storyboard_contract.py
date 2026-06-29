#!/usr/bin/env python3
"""Audit whether important transitions have viewer-readable storyboard proof."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionGrammar": ("transition_grammar_plan/transition_grammar_plan.json", {"ready_with_transition_grammar_plan"}),
    "transitionSceneArc": ("transition_scene_arc_contract_audit.json", {"passed"}),
    "transitionEffectPalette": ("transition_effect_palette_contract_audit.json", {"passed"}),
    "transitionVisualMatch": ("transition_visual_match_contract_audit.json", {"passed"}),
    "transitionMicrostructure": ("transition_microstructure_contract_audit.json", {"passed"}),
    "transitionPreviewQuality": ("transition_preview_quality_contract_audit.json", {"passed"}),
    "transitionPairContinuity": ("transition_pair_continuity_contract_audit.json", {"passed"}),
    "transitionExecutionReadiness": ("transition_execution_readiness_contract_audit.json", {"passed"}),
    "transitionPolishApplication": ("transition_polish_application_contract_audit.json", {"passed"}),
    "bridgeSequenceApplication": ("bridge_sequence_application_contract_audit.json", {"passed"}),
    "finalBlueprintLineage": ("final_blueprint_lineage_contract_audit.json", {"passed"}),
}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "whip_pan_match", "rotation_match_cut", "speed_ramp_bridge"}
VIEWER_PURPOSES = {
    "route_move",
    "time_jump",
    "title_reveal",
    "scenic_breath",
    "texture_bridge",
    "payoff_handoff",
    "ending_aftertaste",
    "bgm_handoff",
    "same_scene_continuity",
}
STORYBOARD_DECISION_FIELDS = {
    "storyboardPurpose",
    "outgoingShotEvidence",
    "bridgeOrMotionBeatEvidence",
    "landingShotEvidence",
    "previewStripEvidence",
    "frameSampleEvidence",
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


def list_value(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [clean(item) for item in value if clean(item)]


def present(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return bool(clean(value))
    if isinstance(value, list):
        return any(present(item) for item in value)
    if isinstance(value, dict):
        return any(present(item) for item in value.values())
    return value is not None


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


def load_preview_packet(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_preview_packet" / "transition_preview_packet.json"
    data = load_json(path) or {}
    rows = data.get("previewRows") if isinstance(data.get("previewRows"), list) else []
    lookup: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = as_int(row.get("rowIndex"), -1)
        if index >= 0:
            lookup[index] = row
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "summary": summary_of(data),
        "lookup": lookup,
        "blockers": data.get("blockers") if isinstance(data, dict) else [],
        "warnings": data.get("warnings") if isinstance(data, dict) else [],
    }


def preview_packet_evidence(row: dict[str, Any], packet: dict[str, Any]) -> str:
    lookup = packet.get("lookup") if isinstance(packet.get("lookup"), dict) else {}
    preview = lookup.get(as_int(row.get("rowIndex"), -1))
    if not isinstance(preview, dict):
        return ""
    if preview.get("status") != "ready_with_transition_preview_evidence":
        return ""
    evidence = clean(preview.get("previewStripEvidence"))
    if evidence:
        return evidence
    frames = preview.get("frameSampleEvidence") if isinstance(preview.get("frameSampleEvidence"), list) else []
    return ", ".join(clean(frame) for frame in frames if clean(frame))


def transition_rows(grammar: dict[str, Any]) -> list[dict[str, Any]]:
    rows = grammar.get("transitionRows") if isinstance(grammar.get("transitionRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def normalize_style(row: dict[str, Any]) -> str:
    recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    style = clean(decision.get("approvedTransitionType") or recommendation.get("recommendedTransitionType")).lower()
    return style


def source_label(clip: Any) -> str:
    if not isinstance(clip, dict):
        return ""
    values = [
        clip.get("sourceName"),
        Path(str(clip.get("sourcePath") or "")).name,
        clip.get("role"),
        clip.get("creatorFunction"),
    ]
    return " | ".join(clean(value) for value in values if clean(value))


def default_purpose(row: dict[str, Any]) -> str:
    category = clean(row.get("boundaryCategory")).lower()
    style = normalize_style(row)
    if category == "chapter_boundary":
        return "route_move"
    if category == "timeline_gap":
        return "time_jump"
    if category == "title_boundary":
        return "title_reveal"
    if category == "ending_transition":
        return "ending_aftertaste"
    if "dissolve" in style:
        return "scenic_breath"
    if "bridge" in style:
        return "texture_bridge"
    if style in MOTION_STYLES:
        return "bgm_handoff"
    return "same_scene_continuity"


def row_decision(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("decision") if isinstance(row.get("decision"), dict) else {}


def row_signals(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("signals") if isinstance(row.get("signals"), dict) else {}


def row_recommendation(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}


def storyboard_row(row: dict[str, Any], *, require_frame_preview: bool, preview_packet: dict[str, Any]) -> dict[str, Any]:
    decision = row_decision(row)
    signals = row_signals(row)
    recommendation = row_recommendation(row)
    category = clean(row.get("boundaryCategory")).lower()
    style = normalize_style(row)
    purpose = clean(decision.get("storyboardPurpose")) or default_purpose(row)
    outgoing = clean(decision.get("outgoingShotEvidence")) or source_label(row.get("fromClip"))
    landing = clean(decision.get("landingShotEvidence")) or source_label(row.get("toClip"))
    bridge_terms = list_value(signals.get("bridgeTerms"))
    from_motion = list_value(signals.get("fromMotionTerms"))
    to_motion = list_value(signals.get("toMotionTerms"))
    bridge_or_motion = (
        clean(decision.get("bridgeOrMotionBeatEvidence"))
        or clean(decision.get("bridgeInsertSource"))
        or ", ".join(bridge_terms)
        or clean(recommendation.get("reason"))
    )
    preview = (
        clean(decision.get("previewStripEvidence"))
        or clean(decision.get("frameSampleEvidence"))
        or clean(row.get("previewStripEvidence"))
        or clean(row.get("frameSampleEvidence"))
        or preview_packet_evidence(row, preview_packet)
    )
    motion_evidence = bool(from_motion and to_motion) or bool(bridge_terms) or present(recommendation.get("physicalBridgeEvidence"))
    has_bridge_or_motion = present(bridge_or_motion) or motion_evidence
    decision_keys_present = STORYBOARD_DECISION_FIELDS.issubset(set(decision))
    important = category in IMPORTANT_CATEGORIES
    issues: list[str] = []
    if not decision_keys_present:
        issues.append("missing_storyboard_decision_fields")
    if purpose not in VIEWER_PURPOSES:
        issues.append("missing_viewer_facing_storyboard_purpose")
    if not present(outgoing):
        issues.append("missing_outgoing_shot_evidence")
    if not present(landing):
        issues.append("missing_landing_shot_evidence")
    if important and not has_bridge_or_motion:
        issues.append("important_boundary_missing_bridge_or_motion_beat")
    if important and require_frame_preview and not present(preview):
        issues.append("important_boundary_missing_preview_or_frame_sample_evidence")
    if style in MOTION_STYLES and not motion_evidence:
        issues.append("motion_transition_without_two_sided_motion_or_bridge_evidence")
    if row.get("status") == "needs_bridge_insert":
        issues.append("bridge_insert_decision_not_resolved")
    return {
        "rowIndex": row.get("rowIndex"),
        "boundaryCategory": category,
        "style": style,
        "storyboardPurpose": purpose,
        "importantBoundary": important,
        "fromSourceName": source_label(row.get("fromClip")),
        "toSourceName": source_label(row.get("toClip")),
        "outgoingShotEvidence": outgoing,
        "bridgeOrMotionBeatEvidence": bridge_or_motion,
        "landingShotEvidence": landing,
        "previewStripEvidence": preview,
        "decisionFieldsPresent": decision_keys_present,
        "motionEvidence": motion_evidence,
        "bridgeTerms": bridge_terms,
        "fromMotionTerms": from_motion,
        "toMotionTerms": to_motion,
        "status": "passed" if not issues else "blocked",
        "issues": issues,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    preview_packet = load_preview_packet(package_dir)
    grammar_data = reports["transitionGrammar"]["data"]
    rows = transition_rows(grammar_data)
    audited = [
        storyboard_row(row, require_frame_preview=not args.allow_missing_frame_preview, preview_packet=preview_packet)
        for row in rows
    ]
    blocked_rows = [row for row in audited if row["status"] == "blocked"]
    important_rows = [row for row in audited if row["importantBoundary"]]
    important_blocked = [row for row in important_rows if row["status"] == "blocked"]
    motion_rows = [row for row in audited if row["style"] in MOTION_STYLES]
    purpose_counts: dict[str, int] = {}
    for row in audited:
        purpose = str(row.get("storyboardPurpose") or "")
        purpose_counts[purpose] = purpose_counts.get(purpose, 0) + 1

    micro = reports["transitionMicrostructure"]["summary"]
    readiness = reports["transitionExecutionReadiness"]["summary"]
    pair = reports["transitionPairContinuity"]["summary"]
    scene = reports["transitionSceneArc"]["summary"]
    visual = reports["transitionVisualMatch"]["summary"]
    palette = reports["transitionEffectPalette"]["summary"]
    bridge = reports["bridgeSequenceApplication"]["summary"]
    polish = reports["transitionPolishApplication"]["summary"]
    lineage = reports["finalBlueprintLineage"]["summary"]
    visual_boundaries = max(
        len(rows),
        as_int(micro.get("visualBoundaryCount")),
        as_int(readiness.get("visualBoundaryCount")),
        as_int(pair.get("visualBoundaryCount")),
        as_int(scene.get("visualBoundaryCount")),
        as_int(visual.get("visualBoundaryCount")),
        as_int(palette.get("visualBoundaryCount")),
    )

    rows_with_preview = sum(1 for row in audited if present(row.get("previewStripEvidence")))
    important_preview = sum(1 for row in important_rows if present(row.get("previewStripEvidence")))
    rows_with_bridge_or_motion = sum(1 for row in audited if present(row.get("bridgeOrMotionBeatEvidence")) or row.get("motionEvidence"))
    important_bridge_or_motion = sum(1 for row in important_rows if present(row.get("bridgeOrMotionBeatEvidence")) or row.get("motionEvidence"))
    rows_with_decision_fields = sum(1 for row in audited if row.get("decisionFieldsPresent"))
    rows_with_purpose = sum(1 for row in audited if row.get("storyboardPurpose") in VIEWER_PURPOSES)
    rows_with_outgoing = sum(1 for row in audited if present(row.get("outgoingShotEvidence")))
    rows_with_landing = sum(1 for row in audited if present(row.get("landingShotEvidence")))
    motion_ready = sum(1 for row in motion_rows if row.get("motionEvidence"))

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required transition storyboard inputs are present and accepted",
        all(report["exists"] and report["accepted"] for report in reports.values()),
        {
            name: {
                "exists": report["exists"],
                "status": report["status"],
                "acceptedStatuses": report["acceptedStatuses"],
                "blockerCount": len(report["blockers"]),
            }
            for name, report in reports.items()
        },
    )
    add_check(
        checks,
        "Every transition row has storyboard decision fields, viewer purpose, outgoing shot, and landing shot",
        visual_boundaries >= 1
        and len(rows) >= visual_boundaries
        and rows_with_decision_fields == len(rows)
        and rows_with_purpose == len(rows)
        and rows_with_outgoing == len(rows)
        and rows_with_landing == len(rows),
        {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": len(rows),
            "rowsWithDecisionFields": rows_with_decision_fields,
            "rowsWithViewerPurpose": rows_with_purpose,
            "rowsWithOutgoingEvidence": rows_with_outgoing,
            "rowsWithLandingEvidence": rows_with_landing,
            "purposeCounts": purpose_counts,
        },
    )
    add_check(
        checks,
        "Important route, title, timeline-gap, and ending transitions have bridge or motion beats plus preview evidence",
        not important_rows
        or (
            important_bridge_or_motion == len(important_rows)
            and (args.allow_missing_frame_preview or important_preview == len(important_rows))
            and not important_blocked
        ),
        {
            "importantBoundaryCount": len(important_rows),
            "importantBridgeOrMotionBeatCount": important_bridge_or_motion,
            "importantPreviewEvidenceCount": important_preview,
            "requiresFramePreviewEvidence": not args.allow_missing_frame_preview,
            "importantBlockedRows": important_blocked[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Motion transitions are storyboarded as rare motivated route accents, not random rotations",
        motion_ready == len(motion_rows)
        and len(motion_rows) <= max(as_int(palette.get("maxMotionAllowed")), as_int(scene.get("maxMotionAllowed")), 1),
        {
            "motionTransitionCount": len(motion_rows),
            "motionReadyRowCount": motion_ready,
            "paletteMaxMotionAllowed": palette.get("maxMotionAllowed"),
            "sceneArcMaxMotionAllowed": scene.get("maxMotionAllowed"),
        },
    )
    add_check(
        checks,
        "Downstream safety agrees with the storyboard: BGM-only, title-safe, handles, pair continuity, and bridge application",
        as_int(readiness.get("bgmHitBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("titleSafeBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("bgmOnlyBoundaryCount")) == visual_boundaries
        and as_int(readiness.get("handleReadyBoundaryCount")) == visual_boundaries
        and as_int(pair.get("weakPairFitCount")) == 0
        and as_int(micro.get("blockedCheckCount")) == 0
        and as_int(bridge.get("missingBeatClipCount")) == 0
        and as_int(bridge.get("sourceAudioLeakClipCount")) == 0,
        {
            "visualBoundaryCount": visual_boundaries,
            "readinessSummary": readiness,
            "pairContinuitySummary": pair,
            "microstructureSummary": micro,
            "bridgeSequenceApplicationSummary": bridge,
        },
    )
    add_check(
        checks,
        "Storyboard proof survives into final transition-polish and final-blueprint lineage",
        reports["transitionPolishApplication"]["accepted"]
        and reports["finalBlueprintLineage"]["accepted"]
        and as_int(polish.get("blockedRowCount")) == 0
        and as_int(lineage.get("blockedReadyStageCount")) == 0,
        {
            "transitionPolishApplicationStatus": reports["transitionPolishApplication"]["status"],
            "transitionPolishApplicationSummary": polish,
            "finalBlueprintLineageStatus": reports["finalBlueprintLineage"]["status"],
            "finalBlueprintLineageSummary": lineage,
            "safety": safety(),
        },
    )

    blocked_checks = [check for check in checks if check["status"] == "blocked"]
    row_issue_labels: list[str] = []
    for row in blocked_rows[: args.max_blocked_rows_in_report]:
        row_issue_labels.append(f"row {row.get('rowIndex')} {row.get('style')}: {', '.join(row.get('issues') or [])}")

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blocked_checks and not blocked_rows else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "allowMissingFramePreview": args.allow_missing_frame_preview,
            "reports": {name: report["path"] for name, report in reports.items()},
            "transitionPreviewPacket": {
                "path": preview_packet["path"],
                "exists": preview_packet["exists"],
                "status": preview_packet["status"],
                "summary": preview_packet["summary"],
            },
        },
        "summary": {
            "visualBoundaryCount": visual_boundaries,
            "transitionRowCount": len(rows),
            "storyboardReadyRowCount": len(audited) - len(blocked_rows),
            "blockedRowCount": len(blocked_rows),
            "importantBoundaryCount": len(important_rows),
            "importantStoryboardReadyCount": len(important_rows) - len(important_blocked),
            "rowsWithDecisionFields": rows_with_decision_fields,
            "rowsWithViewerPurpose": rows_with_purpose,
            "rowsWithOutgoingEvidence": rows_with_outgoing,
            "rowsWithBridgeOrMotionBeat": rows_with_bridge_or_motion,
            "rowsWithLandingEvidence": rows_with_landing,
            "rowsWithPreviewEvidence": rows_with_preview,
            "importantPreviewEvidenceCount": important_preview,
            "importantBridgeOrMotionBeatCount": important_bridge_or_motion,
            "previewPacketStatus": preview_packet["status"],
            "previewPacketReadyRowCount": (preview_packet["summary"] or {}).get("readyPreviewRowCount"),
            "previewPacketBlockedRowCount": (preview_packet["summary"] or {}).get("blockedPreviewRowCount"),
            "motionTransitionCount": len(motion_rows),
            "motionReadyRowCount": motion_ready,
            "purposeCounts": purpose_counts,
            "passedCheckCount": len(checks) - len(blocked_checks),
            "blockedCheckCount": len(blocked_checks),
        },
        "reports": reports,
        "auditedRows": audited,
        "checks": checks,
        "blockers": [check["name"] for check in blocked_checks] + row_issue_labels,
        "warnings": [warning for row in reports.values() for warning in row["warnings"]],
        "policy": {
            "transitionStoryboardRequired": True,
            "viewerFacingPurposeRequired": True,
            "outgoingBridgeLandingRequired": True,
            "framePreviewEvidenceRequiredForImportantBoundaries": not args.allow_missing_frame_preview,
            "motionRequiresRouteMotionEvidence": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Storyboard Contract Audit",
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
                f"### Row {row.get('rowIndex')}: `{row.get('storyboardPurpose')}` / `{row.get('style')}`",
                f"- Status: `{row.get('status')}`",
                f"- Boundary: `{row.get('boundaryCategory')}`",
                f"- Outgoing: `{row.get('outgoingShotEvidence')}`",
                f"- Bridge or motion: `{row.get('bridgeOrMotionBeatEvidence')}`",
                f"- Landing: `{row.get('landingShotEvidence')}`",
                f"- Preview: `{row.get('previewStripEvidence')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Treat a travel transition as a short storyboard: viewer purpose, outgoing shot, bridge or motion beat, landing shot, and preview evidence for important boundaries.",
            "- Use rotation, whip, speed-ramp, or push only when real route motion or bridge evidence supports it.",
            "- Do not approve important day/place/title/ending transitions from metadata alone; inspect or generate frame/contact-sheet evidence first.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition storyboard proof for important travel-video boundaries.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--allow-missing-frame-preview", action="store_true")
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_storyboard_contract_audit.json", report)
    write_markdown(package_dir / "transition_storyboard_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
