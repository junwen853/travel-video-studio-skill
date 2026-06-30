#!/usr/bin/env python3
"""Prepare repair rows for blocked or overused transition motion accents."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "repairAccepted": False,
    "ownerScriptExecuted": "",
    "replacementTransitionType": "",
    "bridgeSourceEvidence": "",
    "bgmPhraseEvidence": "",
    "titleCaptionQuietZoneEvidence": "",
    "resolveBlueprintEvidence": "",
    "resolveReadbackEvidence": "",
    "postRepairAudit": "",
    "editorNotes": "",
}

DEFAULT_ACTION = {
    "priority": "P0",
    "ownerScript": "prepare_transition_choreography_plan.py",
    "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
    "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
    "repairType": "rebuild_motion_accent_choreography",
    "requiredAction": "Rebuild the boundary as a readable outgoing, bridge-or-motion, and stable landing transition; downgrade to match cut, clean cut, or mood dissolve when motion evidence is weak.",
    "acceptanceEvidence": "Rerun choreography, motion-direction, cutpoint, action-anchor, sensory-continuity, motion-accent, preview/audition, final QA, and V14 checks until the row passes.",
}

ISSUE_ACTIONS: list[tuple[tuple[str, ...], dict[str, str]]] = [
    (
        ("overused", "back_to_back_motion_accents_without_breath", "motion accents appear back-to-back"),
        {
            "ownerScript": "prepare_transition_reference_selection.py",
            "requiredArtifact": "transition_reference_selection/transition_reference_selection.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_reference_selection.py --package-dir <package> --json",
            "repairType": "reduce_motion_accent_density",
            "requiredAction": "Keep only the strongest motivated motion accent in this local run; downgrade neighboring motion accents to visual match, clean continuity cut, route bridge, or short mood dissolve.",
            "acceptanceEvidence": "Motion accent share is within budget, max run is 1, and reference-transition-profile plus final-cut smoothness audits pass.",
        },
    ),
    (
        ("motion_accent_without_source_motion_or_bridge_anchor", "motion_direction_not_matched", "direction_confidence", "directional_action_anchor"),
        {
            "ownerScript": "prepare_transition_bridge_plan.py",
            "requiredArtifact": "transition_bridge_plan/transition_bridge_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_bridge_plan.py --package-dir <package> --json",
            "repairType": "add_source_motion_or_bridge_anchor",
            "requiredAction": "Insert or select local transport, walking, signage, pan, push, route, or object-motion bridge evidence before allowing a whip, rotation, push, or speed-ramp accent.",
            "acceptanceEvidence": "Bridge/source evidence exists, motion direction is matched, directional action anchor is ready, and bridge visual evidence audit passes.",
        },
    ),
    (
        ("motion_accent_not_on_bgm_phrase_hit", "cutpoint_or_bgm_hit_not_ready", "bgm"),
        {
            "ownerScript": "prepare_bgm_phrase_blueprint.py",
            "requiredArtifact": "bgm_phrase_blueprint/bgm_phrase_blueprint_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_bgm_phrase_blueprint.py --package-dir <package> --json",
            "repairType": "retime_motion_to_bgm_phrase",
            "requiredAction": "Move the visible motion accent to an approved BGM phrase hit or downgrade it to a non-motion transition when the music cannot support it.",
            "acceptanceEvidence": "Cutpoint BGM hit, BGM phrase transition cue, and motion-accent audit all pass with no source-voice leakage.",
        },
    ),
    (
        ("landing_hold_too_short", "sensory_motion_continuity", "title_subtitle_quiet", "caption_title"),
        {
            "ownerScript": "prepare_transition_execution_blueprint.py",
            "requiredArtifact": "transition_execution_blueprint/transition_execution_blueprint_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package> --json",
            "repairType": "repair_landing_and_quiet_zone",
            "requiredAction": "Extend or replace the landing shot, preserve title/subtitle quiet zones, and keep scenic/title/transition windows BGM-only before any visible motion.",
            "acceptanceEvidence": "Cutpoint, action-anchor, sensory-continuity, breathing-room, and motion-accent audits pass with a readable landing hold.",
        },
    ),
    (
        ("forbidden_template", "random", "rotation_accent_not_subtle", "intensity_too_high", "spin", "flash", "glitch"),
        {
            "ownerScript": "prepare_transition_choreography_plan.py",
            "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
            "repairType": "remove_template_or_excessive_motion",
            "requiredAction": "Remove random/template/flash/spin language; keep rotation only as a subtle motivated match, otherwise downgrade to match cut, clean cut, short dissolve, or route bridge.",
            "acceptanceEvidence": "Motion accent intensity, effect recipe, choreography, audition visual proof, and final rendered-transition proof all pass.",
        },
    ),
]


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


def clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def rows_by_index(rows: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, dict):
            out[str(row.get("rowIndex"))] = row
    return out


def load_choreography_rows(package_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json") or {}
    return rows_by_index(data.get("choreographyRows"))


def load_transition_rows(package_dir: Path) -> dict[str, dict[str, Any]]:
    report = load_json(package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json") or {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    raw = outputs.get("candidateBlueprint") or package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json"
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    blueprint = load_json(path) or {}
    return rows_by_index(blueprint.get("transitions"))


def issue_action(issue_text: str) -> dict[str, str]:
    lowered = issue_text.lower()
    for keywords, action in ISSUE_ACTIONS:
        if any(keyword in lowered for keyword in keywords):
            merged = dict(DEFAULT_ACTION)
            merged.update(action)
            return merged
    return dict(DEFAULT_ACTION)


def row_issue_text(row: dict[str, Any]) -> str:
    issues = row.get("issues") if isinstance(row.get("issues"), list) else []
    return ", ".join(clean(issue, 120) for issue in issues if clean(issue, 120))


def global_blocker_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    blockers = [clean(item) for item in audit.get("blockers") or [] if clean(item)]
    for blocker in blockers:
        lowered = blocker.lower()
        if lowered.startswith("row "):
            continue
        action = issue_action(blocker)
        rows.append(
            {
                "repairId": f"motion_accent_global_{len(rows) + 1}",
                "priority": "P0",
                "scope": "whole_film_motion_accent_balance",
                "rowIndex": "",
                "issueType": action["repairType"],
                "sourceBlocker": blocker,
                "sourceTransitionStyle": "",
                "boundaryCategory": "",
                "ownerScript": action["ownerScript"],
                "requiredArtifact": action["requiredArtifact"],
                "command": action["command"],
                "requiredAction": action["requiredAction"],
                "acceptanceEvidence": action["acceptanceEvidence"],
                "forbiddenWorkaround": "Do not keep every visible motion accent and call it reference style; the reference language uses rare, motivated motion with breathing boundaries.",
                "affectedEvidence": {"audit": "transition_motion_accent_contract_audit.json"},
                "decision": dict(DECISION_FIELDS),
            }
        )
    return rows


def row_repair(
    audited_row: dict[str, Any],
    choreography_row: dict[str, Any],
    transition_row: dict[str, Any],
    ordinal: int,
) -> dict[str, Any]:
    issue_text = row_issue_text(audited_row)
    action = issue_action(issue_text)
    row_index = audited_row.get("rowIndex")
    direction = choreography_row.get("motionDirectionPlan") if isinstance(choreography_row.get("motionDirectionPlan"), dict) else {}
    cutpoint = transition_row.get("transitionCutpointPlan") if isinstance(transition_row.get("transitionCutpointPlan"), dict) else {}
    anchor = transition_row.get("transitionActionAnchorPlan") if isinstance(transition_row.get("transitionActionAnchorPlan"), dict) else {}
    sensory = transition_row.get("transitionSensoryContinuityPlan") if isinstance(transition_row.get("transitionSensoryContinuityPlan"), dict) else {}
    return {
        "repairId": f"motion_accent_row_{row_index}_{ordinal}",
        "priority": action["priority"],
        "scope": "transition_boundary",
        "rowIndex": row_index,
        "issueType": action["repairType"],
        "sourceIssues": audited_row.get("issues") or [],
        "sourceTransitionStyle": audited_row.get("sourceTransitionStyle") or choreography_row.get("sourceTransitionStyle"),
        "boundaryCategory": audited_row.get("boundaryCategory") or choreography_row.get("boundaryCategory"),
        "importantBoundary": audited_row.get("importantBoundary") or choreography_row.get("importantBoundary"),
        "ownerScript": action["ownerScript"],
        "requiredArtifact": action["requiredArtifact"],
        "command": action["command"],
        "requiredAction": action["requiredAction"],
        "allowedFixes": [
            "downgrade to clean continuity cut",
            "downgrade to visual match cut",
            "downgrade to short mood dissolve",
            "insert local route or texture bridge footage",
            "keep one subtle motion accent only when source motion, BGM hit, quiet titles, and landing hold all pass",
        ],
        "forbiddenFixes": [
            "random rotation",
            "flash/glitch/strobe/template transition",
            "stronger spin to hide a weak cut",
            "back-to-back motion accents",
            "motion under title/subtitle text",
            "motion with source-camera voice in scenic/title/transition windows",
        ],
        "acceptanceEvidence": action["acceptanceEvidence"],
        "forbiddenWorkaround": "Do not solve this by making the effect stronger; repair the outgoing action, bridge or match reason, BGM hit, title-safe quiet zone, and stable landing first.",
        "affectedEvidence": {
            "audit": "transition_motion_accent_contract_audit.json",
            "directionStatus": direction.get("status"),
            "directionMatch": direction.get("directionMatch"),
            "directionConfidence": direction.get("directionConfidence"),
            "cutpointStatus": cutpoint.get("status"),
            "landingHoldFrames": cutpoint.get("landingHoldFrames"),
            "actionAnchorStatus": anchor.get("status"),
            "sensoryStatus": sensory.get("status"),
        },
        "decision": dict(DECISION_FIELDS),
    }


def build_plan(package_dir: Path, output_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    audit_path = package_dir / "transition_motion_accent_contract_audit.json"
    audit = load_json(audit_path) or {}
    if not audit_path.exists():
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked_missing_transition_motion_accent_audit",
            "packageDir": str(package_dir),
            "outputDir": str(output_dir),
            "inputs": {"motionAccentAudit": str(audit_path), "motionAccentAuditExists": False},
            "summary": {"repairRowCount": 0, "blockedMotionAccentRowCount": 0},
            "repairRows": [],
            "nextActions": ["Run audit_transition_motion_accent_contract.py before preparing motion-accent repairs."],
            "safety": safety(),
        }

    choreography_rows = load_choreography_rows(package_dir)
    transition_rows = load_transition_rows(package_dir)
    audited_rows = [row for row in audit.get("auditedRows") or [] if isinstance(row, dict)]
    blocked_rows = [row for row in audited_rows if row.get("status") == "blocked"]
    repair_rows = global_blocker_rows(audit)
    ordinal = len(repair_rows)
    for row in blocked_rows:
        ordinal += 1
        index = str(row.get("rowIndex"))
        repair_rows.append(row_repair(row, choreography_rows.get(index, {}), transition_rows.get(index, {}), ordinal))

    status = "ready_no_motion_accent_repairs_needed"
    if repair_rows:
        status = "ready_with_transition_motion_accent_repair_plan"
    elif audit.get("status") == "blocked":
        status = "needs_transition_motion_accent_upstream_repair"
    elif audit.get("status") != "passed":
        status = "needs_transition_motion_accent_audit_refresh"

    summary = {
        "motionAccentAuditStatus": audit.get("status"),
        "repairRowCount": len(repair_rows),
        "globalRepairRowCount": len([row for row in repair_rows if row.get("scope") == "whole_film_motion_accent_balance"]),
        "blockedMotionAccentRowCount": len(blocked_rows),
        "motionAccentRowCount": (audit.get("summary") or {}).get("motionAccentRowCount"),
        "readyMotionAccentRowCount": (audit.get("summary") or {}).get("readyMotionAccentRowCount"),
        "motionAccentRunMax": (audit.get("summary") or {}).get("motionAccentRunMax"),
        "maxMotionAccentAllowed": (audit.get("summary") or {}).get("maxMotionAccentAllowed"),
        "ownerScripts": sorted({str(row.get("ownerScript")) for row in repair_rows if row.get("ownerScript")}),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {
            "motionAccentAudit": str(audit_path),
            "motionAccentAuditStatus": audit.get("status"),
            "choreographyPlan": str(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json"),
            "transitionExecutionBlueprintReport": str(package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json"),
        },
        "summary": summary,
        "repairRows": repair_rows,
        "nextActions": [
            "Run each ownerScript in priority order.",
            "Rerun transition choreography, motion-direction, cutpoint, action-anchor, sensory-continuity, preview, audition, storyboard, motion-accent, final QA, V14, and maturity checks.",
            "Do not write Resolve or claim delivery while this plan has open P0 repair rows.",
        ],
        "safety": safety(),
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Motion Accent Repair Plan",
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
    for row in plan.get("repairRows", [])[:200]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Row: `{row.get('rowIndex')}`",
                f"- Issue type: `{row.get('issueType')}`",
                f"- Style/category: `{row.get('sourceTransitionStyle')}` / `{row.get('boundaryCategory')}`",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Required artifact: `{row.get('requiredArtifact')}`",
                f"- Required action: {row.get('requiredAction')}",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
            ]
        )
        if row.get("sourceIssues"):
            lines.append(f"- Source issues: `{', '.join(row.get('sourceIssues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Motion accents are optional. Use them only when source movement, bridge evidence, BGM phrase timing, title safety, and stable landing proof all exist.",
            "- Repair weak joins with footage, timing, or downgrade decisions before adding visible effects.",
            "- A plan with repair rows is not a delivery pass.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare repair rows for blocked transition motion accents.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_motion_accent_repair_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_motion_accent_repair_plan"
    plan = build_plan(package_dir, output_dir)
    write_json(output_dir / "transition_motion_accent_repair_plan.json", plan)
    write_markdown(output_dir / "transition_motion_accent_repair_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if str(plan.get("status") or "").startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
