#!/usr/bin/env python3
"""Prepare repair rows for blocked transition flow and adjacent-shot polish gates."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = {"passed", "passed_with_warnings", "passed_with_caveats"}

REPORT_SPECS: dict[str, dict[str, Any]] = {
    "transition_cadence_contract_audit": {
        "path": "transition_cadence_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_reference_selection.py",
        "requiredArtifact": "transition_reference_selection/transition_reference_selection.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_reference_selection.py --package-dir <package> --json",
    },
    "transition_microstructure_contract_audit": {
        "path": "transition_microstructure_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_execution_blueprint.py",
        "requiredArtifact": "transition_execution_blueprint/transition_execution_blueprint_report.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package> --json",
    },
    "transition_scene_arc_contract_audit": {
        "path": "transition_scene_arc_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "transition_effect_palette_contract_audit": {
        "path": "transition_effect_palette_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_reference_selection.py",
        "requiredArtifact": "transition_reference_selection/transition_reference_selection.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_reference_selection.py --package-dir <package> --json",
    },
    "transition_motif_coherence_contract_audit": {
        "path": "transition_motif_coherence_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_motif_plan.py",
        "requiredArtifact": "transition_motif_plan/transition_motif_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_motif_plan.py --package-dir <package> --json",
    },
    "transition_visual_match_contract_audit": {
        "path": "transition_visual_match_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "transition_source_coverage_contract_audit": {
        "path": "transition_source_coverage_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_bridge_plan.py",
        "requiredArtifact": "transition_bridge_plan/transition_bridge_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_bridge_plan.py --package-dir <package> --json",
    },
    "transition_choreography_contract_audit": {
        "path": "transition_choreography_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "transition_motion_direction_contract_audit": {
        "path": "transition_motion_direction_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_motion_accent_repair_plan.py",
        "requiredArtifact": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_motion_accent_repair_plan.py --package-dir <package> --json",
    },
    "transition_motion_accent_repair_plan": {
        "path": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "accepted": {"ready_no_motion_accent_repairs_needed"},
        "ownerScript": "prepare_transition_motion_accent_repair_plan.py",
        "requiredArtifact": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_motion_accent_repair_plan.py --package-dir <package> --json",
    },
    "transition_effect_recipe_contract_audit": {
        "path": "transition_effect_recipe_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "rendered_transition_proof_contract_audit": {
        "path": "rendered_transition_proof_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_audition_packet.py",
        "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
    },
    "transition_cutpoint_contract_audit": {
        "path": "transition_cutpoint_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_execution_blueprint.py",
        "requiredArtifact": "transition_execution_blueprint/transition_execution_blueprint_report.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package> --json",
    },
    "transition_action_anchor_contract_audit": {
        "path": "transition_action_anchor_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "transition_sensory_continuity_contract_audit": {
        "path": "transition_sensory_continuity_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "transition_preview_quality_contract_audit": {
        "path": "transition_preview_quality_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_preview_packet.py",
        "requiredArtifact": "transition_preview_packet/transition_preview_packet.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_preview_packet.py --package-dir <package> --json",
    },
    "transition_audition_quality_contract_audit": {
        "path": "transition_audition_quality_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_audition_packet.py",
        "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
    },
    "transition_audition_visual_proof_contract_audit": {
        "path": "transition_audition_visual_proof_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_audition_packet.py",
        "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
    },
    "transition_audition_role_integrity_contract_audit": {
        "path": "transition_audition_role_integrity_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_audition_packet.py",
        "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
    },
    "transition_storyboard_contract_audit": {
        "path": "transition_storyboard_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "transition_breathing_room_contract_audit": {
        "path": "transition_breathing_room_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_bridge_sequence_plan.py",
        "requiredArtifact": "bridge_sequence_plan/bridge_sequence_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package> --json",
    },
    "scene_flow_arc_contract_audit": {
        "path": "scene_flow_arc_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_bridge_sequence_plan.py",
        "requiredArtifact": "bridge_sequence_plan/bridge_sequence_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package> --json",
    },
    "final_cut_smoothness_contract_audit": {
        "path": "final_cut_smoothness_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_rhythm_recut_blueprint.py",
        "requiredArtifact": "rhythm_recut_blueprint/rhythm_recut_blueprint_report.json",
        "command": "python3 <skill-dir>/scripts/prepare_rhythm_recut_blueprint.py --package-dir <package> --json",
    },
    "transition_continuity_rehearsal_contract_audit": {
        "path": "transition_continuity_rehearsal_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "pacing_watchability_contract_audit": {
        "path": "pacing_watchability_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
    },
    "narrative_adjacency_contract_audit": {
        "path": "narrative_adjacency_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
    },
    "transition_viewer_orientation_contract_audit": {
        "path": "transition_viewer_orientation_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    },
    "transition_scene_settlement_contract_audit": {
        "path": "transition_scene_settlement_contract_audit.json",
        "accepted": {"passed"},
        "ownerScript": "prepare_bridge_sequence_plan.py",
        "requiredArtifact": "bridge_sequence_plan/bridge_sequence_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package> --json",
    },
}

DECISION_FIELDS = {
    "repairAccepted": False,
    "ownerScriptExecuted": "",
    "replacementTransitionLanguage": "",
    "bridgeOrMatchEvidence": "",
    "bgmHitEvidence": "",
    "landingHoldEvidence": "",
    "titleCaptionQuietZoneEvidence": "",
    "updatedBlueprintEvidence": "",
    "previewOrAuditionEvidence": "",
    "postRepairAudit": "",
    "editorNotes": "",
}

DEFAULT_ACTION = {
    "priority": "P0",
    "ownerScript": "prepare_transition_choreography_plan.py",
    "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
    "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    "repairType": "rebuild_transition_flow",
    "requiredAction": "Rebuild the boundary as an outgoing action, bridge-or-match reason, BGM-hit or quiet cutpoint, and stable landing instead of an isolated effect.",
    "acceptanceEvidence": "Rerun transition flow repair planning and all transition flow audits until no repair rows remain.",
}

ISSUE_ACTIONS: list[tuple[tuple[str, ...], dict[str, str]]] = [
    (
        ("source coverage", "bridge", "local video", "probe", "frame", "missing footage", "bridge clip"),
        {
            "ownerScript": "prepare_transition_bridge_plan.py",
            "requiredArtifact": "transition_bridge_plan/transition_bridge_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_bridge_plan.py --package-dir <package> --json",
            "repairType": "add_source_backed_bridge",
            "requiredAction": "Select or insert local route, transport, street, signage, texture, pan, or landmark bridge footage before trusting the transition.",
            "acceptanceEvidence": "Transition source coverage and bridge visual evidence audits pass with package-local video probe and frame evidence.",
        },
    ),
    (
        ("cadence", "repeated", "template", "effect palette", "motif", "random", "effect spam", "hard cut"),
        {
            "ownerScript": "prepare_transition_reference_selection.py",
            "requiredArtifact": "transition_reference_selection/transition_reference_selection.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_reference_selection.py --package-dir <package> --json",
            "repairType": "rebalance_transition_language",
            "requiredAction": "Re-select the transition language so cuts, match cuts, dissolves, bridge beats, and rare motion accents form one restrained reference-like rhythm.",
            "acceptanceEvidence": "Cadence, effect-palette, motif-coherence, reference-transition-profile, and final-cut smoothness audits pass.",
        },
    ),
    (
        ("cutpoint", "bgm hit", "landing hold", "handle", "title-safe", "quiet zone", "microstructure"),
        {
            "ownerScript": "prepare_transition_execution_blueprint.py",
            "requiredArtifact": "transition_execution_blueprint/transition_execution_blueprint_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package> --json",
            "repairType": "retime_cutpoint_and_landing",
            "requiredAction": "Retiming must preserve outgoing tail, BGM hit or quiet cut, title/subtitle safety, handles, and a readable landing hold.",
            "acceptanceEvidence": "Transition microstructure, cutpoint, action-anchor, sensory-continuity, breathing-room, and preview/audition audits pass.",
        },
    ),
    (
        ("motion", "rotation", "whip", "push", "zoom", "slide", "speed", "accent", "direction"),
        {
            "ownerScript": "prepare_transition_motion_accent_repair_plan.py",
            "requiredArtifact": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_motion_accent_repair_plan.py --package-dir <package> --json",
            "repairType": "repair_or_downgrade_motion_accent",
            "requiredAction": "Keep motion only when source direction, bridge anchor, BGM hit, title safety, and landing hold all pass; otherwise downgrade to a match cut, clean cut, dissolve, or bridge beat.",
            "acceptanceEvidence": "Motion-direction, motion-accent repair, effect-recipe, audition visual proof, rendered-transition proof, and final QA pass.",
        },
    ),
    (
        ("recipe", "keyframe", "easing", "envelope", "resolve", "readback", "materialization", "apply path", "marker-only"),
        {
            "ownerScript": "prepare_resolve_transition_apply_plan.py",
            "requiredArtifact": "resolve_transition_apply_plan/resolve_transition_apply_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_resolve_transition_apply_plan.py --package-dir <package> --json",
            "repairType": "materialize_visible_transition",
            "requiredAction": "Turn marker-only or prose-only transition intent into API-supported cuts, materialized bridge clips, or Resolve readback plus frame-sample evidence.",
            "acceptanceEvidence": "Resolve transition materialization, apply-path, rendered proof, and final QA pass.",
        },
    ),
    (
        ("preview", "audition", "storyboard", "nonblank", "frame proof", "visual proof", "role integrity"),
        {
            "ownerScript": "prepare_transition_audition_packet.py",
            "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
            "repairType": "refresh_transition_preview_or_audition",
            "requiredAction": "Regenerate nonblank preview/audition/storyboard evidence after the repaired transition candidate exists.",
            "acceptanceEvidence": "Preview quality, audition quality, audition visual proof, role integrity, storyboard, and rendered-transition proof audits pass.",
        },
    ),
    (
        ("breathing", "settlement", "scene flow", "viewer orientation", "narrative", "adjacency", "smoothness", "pacing", "random stack", "energy", "cooldown", "aftercare", "calm buffer"),
        {
            "ownerScript": "prepare_bridge_sequence_plan.py",
            "requiredArtifact": "bridge_sequence_plan/bridge_sequence_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package> --json",
            "repairType": "add_breathing_room_or_scene_settlement",
            "requiredAction": "Add or select 2-5 shot bridge/settlement/breathing-room beats so the viewer understands the route, scene purpose, and landing before the next idea.",
            "acceptanceEvidence": "Breathing-room, scene-flow arc, final-cut smoothness, narrative-adjacency, viewer-orientation, scene-settlement, and pacing audits pass.",
        },
    ),
]

ROW_KEYS = (
    "auditedRows",
    "boundaryRows",
    "transitionRows",
    "choreographyRows",
    "cutpointRows",
    "anchorRows",
    "sensoryRows",
    "storyboardRows",
    "smoothnessRows",
    "adjacencyRows",
    "rehearsalRows",
    "settlementRows",
    "watchabilityRows",
)


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


def clean(value: Any, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def safe_report_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_")[:80]


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def compact_evidence(data: dict[str, Any]) -> dict[str, Any]:
    summary = summary_of(data)
    return {
        "status": data.get("status"),
        "summary": {key: summary.get(key) for key in sorted(summary)[:30]},
    }


def row_identity(row: dict[str, Any]) -> str:
    for key in ("rowIndex", "boundaryIndex", "transitionIndex", "pairIndex", "shotIndex", "id", "boundaryId"):
        if row.get(key) not in (None, ""):
            return str(row.get(key))
    return ""


def row_issue(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("issues", "blockers", "warnings"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(clean(item, 160) for item in value if clean(item, 160))
    for key in ("reason", "issue", "failure", "message", "statusReason", "repairReason"):
        if clean(row.get(key), 220):
            parts.append(clean(row.get(key), 220))
    status = clean(row.get("status"), 80)
    identity = row_identity(row)
    prefix = f"row {identity} " if identity else "row "
    if parts:
        return prefix + "; ".join(parts)[:650]
    if status and status not in PASSED and not status.startswith("ready"):
        return f"{prefix}status is {status}"
    return ""


def row_issues(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for key in ROW_KEYS:
        value = data.get(key)
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, dict):
                continue
            status = clean(row.get("status"), 80)
            has_issue = status and status not in PASSED and not status.startswith("ready")
            has_issue = has_issue or bool(row.get("issues")) or bool(row.get("blockers"))
            if has_issue:
                issue = row_issue(row)
                if issue:
                    out.append((issue, row))
    return out


def check_issues(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for check in data.get("checks") or []:
        if not isinstance(check, dict):
            continue
        status = clean(check.get("status"), 80)
        if status in PASSED:
            continue
        name = clean(check.get("name"), 180)
        evidence = check.get("evidence") if isinstance(check.get("evidence"), dict) else {}
        detail = clean(json.dumps(evidence, ensure_ascii=False), 360) if evidence else ""
        if name or detail:
            out.append(f"{name}: {detail}" if detail else name)
    return out


def report_issues(report_id: str, path: Path, spec: dict[str, Any], data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if not path.exists():
        return [(f"{report_id} is missing", {})]
    accepted = set(spec["accepted"])
    status = clean(data.get("status"), 120)
    issues: list[tuple[str, dict[str, Any]]] = []
    if status not in accepted:
        issues.append((f"{report_id} status is {status or 'unknown'}", {}))
    issues.extend((clean(item), {}) for item in data.get("blockers") or [] if clean(item))
    issues.extend((issue, {}) for issue in check_issues(data))
    issues.extend(row_issues(data))
    return issues[:120]


def issue_action(issue_text: str, spec: dict[str, Any]) -> dict[str, str]:
    lowered = issue_text.lower()
    if " is missing" in lowered or "status is unknown" in lowered:
        return {
            "priority": "P0",
            "ownerScript": str(spec["ownerScript"]),
            "requiredArtifact": str(spec["requiredArtifact"]),
            "command": str(spec["command"]),
            "repairType": "refresh_missing_or_stale_transition_report",
            "requiredAction": "Generate or refresh the missing/stale transition flow report before deciding the boundary is ready.",
            "acceptanceEvidence": "The report exists, has an accepted status, and the transition flow repair plan returns no rows.",
        }
    for keywords, action in ISSUE_ACTIONS:
        if any(keyword in lowered for keyword in keywords):
            merged = dict(DEFAULT_ACTION)
            merged.update(action)
            return merged
    merged = dict(DEFAULT_ACTION)
    merged.update({key: str(spec[key]) for key in ("ownerScript", "requiredArtifact", "command")})
    return merged


def make_repair_row(
    *,
    ordinal: int,
    report_id: str,
    report_path: Path,
    spec: dict[str, Any],
    data: dict[str, Any],
    issue_text: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    action = issue_action(issue_text, spec)
    return {
        "repairId": f"transition_flow_{safe_report_id(report_id)}_{ordinal}",
        "priority": action["priority"],
        "phase": "transition_flow",
        "issueType": action["repairType"],
        "sourceReport": report_id,
        "sourceReportPath": str(report_path),
        "sourceReportExists": report_path.exists(),
        "sourceStatus": data.get("status"),
        "rowIndex": row_identity(row),
        "issue": issue_text,
        "ownerScript": action["ownerScript"],
        "requiredArtifact": action["requiredArtifact"],
        "command": action["command"],
        "requiredAction": action["requiredAction"],
        "allowedFixes": [
            "replace bare hard cut with motivated clean continuity cut",
            "add local 2-5 shot route or texture bridge",
            "downgrade random visible motion to match cut, clean cut, or short mood dissolve",
            "retime outgoing tail, BGM hit, and landing hold",
            "materialize visible transitions with Resolve readback or bridge clips",
            "regenerate nonblank preview/audition/storyboard evidence after repair",
        ],
        "forbiddenFixes": [
            "random rotation, whip, push, zoom, slide, speed-ramp, flash, or glitch",
            "template effect chains",
            "marker-only visible effects",
            "effects hiding weak source selection",
            "title/subtitle collisions during transitions",
            "source-camera voice under scenic/title/transition windows",
            "immediate second jump before the viewer lands",
        ],
        "acceptanceEvidence": action["acceptanceEvidence"],
        "forbiddenWorkaround": "Do not call a transition fixed because an effect was added; prove source coverage, story motivation, BGM timing, title safety, preview/audition evidence, and a stable landing.",
        "affectedEvidence": {
            "report": compact_evidence(data),
            "row": row,
        },
        "decision": dict(DECISION_FIELDS),
    }


def build_plan(package_dir: Path, output_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports: dict[str, dict[str, Any]] = {}
    repair_rows: list[dict[str, Any]] = []
    ordinal = 0
    for report_id, spec in REPORT_SPECS.items():
        path = package_dir / str(spec["path"])
        data = load_json(path) or {}
        reports[report_id] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(spec["accepted"]),
            "summary": summary_of(data),
        }
        for issue, row in report_issues(report_id, path, spec, data):
            ordinal += 1
            repair_rows.append(
                make_repair_row(
                    ordinal=ordinal,
                    report_id=report_id,
                    report_path=path,
                    spec=spec,
                    data=data,
                    issue_text=issue,
                    row=row,
                )
            )

    status = "ready_no_transition_flow_repairs_needed" if not repair_rows else "ready_with_transition_flow_repair_plan"
    summary = {
        "repairRowCount": len(repair_rows),
        "reportsChecked": len(reports),
        "blockedReportCount": sum(
            1
            for report_id, report in reports.items()
            if report.get("status") not in REPORT_SPECS[report_id]["accepted"]
        ),
        "missingReportCount": sum(1 for report in reports.values() if report.get("exists") is not True),
        "ownerScripts": sorted({str(row.get("ownerScript")) for row in repair_rows if row.get("ownerScript")}),
        "sourceReportsWithRepairs": sorted({str(row.get("sourceReport")) for row in repair_rows if row.get("sourceReport")}),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {"reports": reports},
        "summary": summary,
        "repairRows": repair_rows,
        "nextActions": [
            "Run each transition-flow ownerScript in priority order.",
            "Rerun transition flow repair planning after the owner scripts complete.",
            "Rerun transition cadence, microstructure, scene-arc, visual-match, source-coverage, choreography, cutpoint, action-anchor, sensory-continuity, preview/audition, breathing-room, final-cut smoothness, narrative-adjacency, viewer-orientation, scene-settlement, final QA, V14, and maturity checks.",
            "Do not write Resolve, render, or claim handoff while this plan has open P0 repair rows.",
        ],
        "safety": safety(),
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Flow Repair Plan",
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
        "## Repair Rows",
    ]
    if not plan.get("repairRows"):
        lines.append("- None.")
    for row in plan.get("repairRows", [])[:250]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Source report: `{row.get('sourceReport')}`",
                f"- Row: `{row.get('rowIndex')}`",
                f"- Issue type: `{row.get('issueType')}`",
                f"- Issue: {row.get('issue')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Required artifact: `{row.get('requiredArtifact')}`",
                f"- Required action: {row.get('requiredAction')}",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Contract",
            "- A transition repair plan with repair rows is not a delivery pass.",
            "- Repair weak joins with source selection, bridge footage, timing, BGM phrasing, and landing holds before adding visible effects.",
            "- Visible effects must be rare, motivated, title-safe, BGM-led, materialized, previewed, and proven in the final render.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare repair rows for blocked transition flow checks.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_flow_repair_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_flow_repair_plan"
    plan = build_plan(package_dir, output_dir)
    write_json(output_dir / "transition_flow_repair_plan.json", plan)
    write_markdown(output_dir / "transition_flow_repair_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
