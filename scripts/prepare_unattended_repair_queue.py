#!/usr/bin/env python3
"""Build an actionable repair queue from package QA blockers."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ACCEPTED_COMMON = {"passed", "passed_with_warnings", "passed_with_caveats", "ready", "ready_with_warnings"}

REPORT_SPECS: dict[str, dict[str, Any]] = {
    "raw_intake_completeness_audit": {
        "path": "raw_intake_completeness_audit.json",
        "accepted": {"passed"},
        "phase": "intake_route",
        "priority": "P0",
        "ownerScript": "prepare_footage_recognition_report.py",
        "requiredArtifact": "recognition_reports/latest_footage_recognition_route_report.json",
        "command": "python3 <skill-dir>/scripts/prepare_footage_recognition_report.py --project-dir <project-dir> --json",
        "acceptanceEvidence": "Rerun audit_raw_intake_completeness.py and prove every active source video is indexed, recognized, routed exactly once, non-derived, and fresh.",
        "forbiddenWorkaround": "Do not cut from a sample folder, derived export, stale media index, or filename order when full-source intake is blocked.",
    },
    "source_selection_coverage_contract_audit": {
        "path": "source_selection_coverage_contract_audit.json",
        "accepted": {"passed"},
        "phase": "source_selection",
        "priority": "P0",
        "ownerScript": "prepare_source_selection_repair_plan.py",
        "requiredArtifact": "source_selection_repair_plan/source_selection_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_source_selection_repair_plan.py --package-dir <package> --project-dir <project-dir> --json",
        "acceptanceEvidence": "Rerun audit_source_selection_coverage_contract.py and prove all chapter movement, texture, payoff, and orientation repair gaps are closed.",
        "forbiddenWorkaround": "Do not compensate for weak source selection with stock inserts, flashy effects, or title cards.",
    },
    "first_assembly_source_order_contract_audit": {
        "path": "first_assembly_source_order_contract_audit.json",
        "accepted": {"passed"},
        "phase": "source_selection",
        "priority": "P0",
        "ownerScript": "prepare_footage_select_plan.py",
        "requiredArtifact": "footage_select_plan/footage_select_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_footage_select_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_first_assembly_source_order_contract.py and prove first assembly uses scored hero/main/texture candidates rather than raw filename order.",
        "forbiddenWorkaround": "Do not keep a filename-order montage and try to hide it with transitions.",
    },
    "large_source_unattended_readiness_contract_audit": {
        "path": "large_source_unattended_readiness_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "phase": "source_selection",
        "priority": "P0",
        "ownerScript": "audit_large_source_unattended_readiness_contract.py",
        "requiredArtifact": "large_source_unattended_readiness_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_large_source_unattended_readiness_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Report proves media-root intake, whole-folder recognition, source selection, first assembly, unattended first draft, and blueprint preflight are connected.",
        "forbiddenWorkaround": "Do not hand off a 100GB unordered folder until the chain is connected end to end.",
    },
    "opening_story_plan": {
        "path": "opening_story_plan/opening_story_plan.json",
        "accepted": {"ready_with_opening_story_plan"},
        "phase": "story_spine",
        "priority": "P0",
        "ownerScript": "prepare_opening_story_plan.py",
        "requiredArtifact": "opening_story_plan/opening_story_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Opening plan contains viewer promise, destination proof, clean title, practical arrival, lived-in texture, and first chapter handoff.",
        "forbiddenWorkaround": "Do not start with a black slate, generic title, duplicate text, or random scenic clip without an opening promise.",
    },
    "chapter_arc_plan": {
        "path": "chapter_arc_plan/chapter_arc_plan.json",
        "accepted": {"ready_with_chapter_arc_plan"},
        "phase": "story_spine",
        "priority": "P0",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Every chapter has context, movement, lived-in texture, payoff, aftertaste, and owner rows for missing beats.",
        "forbiddenWorkaround": "Do not treat a chapter as a landmark stack or leftover clip dump.",
    },
    "audience_caption_contract_audit": {
        "path": "audience_caption_contract_audit.json",
        "accepted": {"passed"},
        "phase": "caption_audio",
        "priority": "P0",
        "ownerScript": "prepare_caption_story_plan.py",
        "requiredArtifact": "caption_story_plan/caption_story_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_caption_story_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_audience_caption_contract.py and prove final TXT/SRT/burned captions are viewer-facing travel-film lines, not workflow reports.",
        "forbiddenWorkaround": "Do not put QA, version, export, fix, skill, Resolve, SRT/TXT, or delivery status language into viewer captions.",
    },
    "bgm_selection_package": {
        "path": "bgm_selection_package/bgm_selection_package.json",
        "accepted": {"ready_with_materialized_bgm_selection_package"},
        "phase": "caption_audio",
        "priority": "P0",
        "ownerScript": "prepare_bgm_selection_package.py",
        "requiredArtifact": "bgm_selection_package/bgm_selection_package.json",
        "command": "python3 <skill-dir>/scripts/prepare_bgm_selection_package.py --package-dir <package> --json",
        "acceptanceEvidence": "BGM selection package proves local, license-traceable, duration-covering, blueprint-referenced, rebuildable music bed or source tracks.",
        "forbiddenWorkaround": "Do not use silence, hum tones, untraceable music, or source-camera audio as the scenic BGM bed.",
    },
    "audio_scene_policy_plan": {
        "path": "audio_scene_policy_plan/audio_scene_policy_plan.json",
        "accepted": {"ready_with_bgm_only_scene_policy"},
        "phase": "caption_audio",
        "priority": "P0",
        "ownerScript": "prepare_audio_scene_policy_plan.py",
        "requiredArtifact": "audio_scene_policy_plan/audio_scene_policy_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_audio_scene_policy_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Audio policy proves scenic, title, transition, effect, and feedback windows are A3 BGM-led with no A1/A2 voice leakage.",
        "forbiddenWorkaround": "Do not leave camera/user voice under scenic openings, city hooks, or transition bridges.",
    },
    "cover_title_contract_audit": {
        "path": "cover_title_contract_audit.json",
        "accepted": {"passed"},
        "phase": "title_establishing",
        "priority": "P0",
        "ownerScript": "prepare_title_typography_plan.py",
        "requiredArtifact": "title_typography_plan/title_typography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Cover/title audit proves a clean scenic 16:9 hero title with no route/date/internal labels, ghosting, or stacked text.",
        "forbiddenWorkaround": "Do not cover bad title composition with shadows, extra labels, or duplicate text layers.",
    },
    "visual_establishing_plan": {
        "path": "visual_establishing_plan/visual_establishing_plan.json",
        "accepted": {"ready_with_establishing_evidence"},
        "phase": "title_establishing",
        "priority": "P1",
        "ownerScript": "prepare_visual_establishing_plan.py",
        "requiredArtifact": "visual_establishing_plan/visual_establishing_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_visual_establishing_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Opening, chapter, and ending establishing rows have local-footage evidence or licensed stock/aerial decisions.",
        "forbiddenWorkaround": "Do not reuse stale previous-trip aerial/title defaults or black title slates.",
    },
    "edit_rhythm_plan": {
        "path": "edit_rhythm_plan/edit_rhythm_plan.json",
        "accepted": {"ready_with_edit_rhythm_plan"},
        "phase": "creator_cut",
        "priority": "P0",
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Each primary visual shot has a function, pacing diagnosis, trim/split/cutaway decision, and chapter variety evidence.",
        "forbiddenWorkaround": "Do not accept long raw holds or flat AI-looking pacing just because the export technically renders.",
    },
    "creator_cut_application_contract_audit": {
        "path": "creator_cut_application_contract_audit.json",
        "accepted": {"passed"},
        "phase": "creator_cut",
        "priority": "P0",
        "ownerScript": "prepare_creator_cut_plan.py",
        "requiredArtifact": "creator_cut_plan/creator_cut_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_creator_cut_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_creator_cut_application_contract.py and prove final clips match creator rows with no reject/weak clips active.",
        "forbiddenWorkaround": "Do not let effects rescue weak footage; demote or replace weak shots first.",
    },
    "transition_execution_readiness_contract_audit": {
        "path": "transition_execution_readiness_contract_audit.json",
        "accepted": {"passed"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_transition_execution_plan.py",
        "requiredArtifact": "transition_execution_plan/transition_execution_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_execution_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Every final boundary has package-local Resolve recipe, BGM hit, title-safe window, pair readiness, and handles.",
        "forbiddenWorkaround": "Do not mark transitions ready when they are marker-only metadata or missing handles/pair evidence.",
    },
    "transition_breathing_room_contract_audit": {
        "path": "transition_breathing_room_contract_audit.json",
        "accepted": {"passed"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_transition_choreography_plan.py",
        "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_transition_breathing_room_contract.py and prove important boundaries have stable, quiet landing footage.",
        "forbiddenWorkaround": "Do not stack rotation, whip, speed-ramp, or flash motion without stable post-transition breathing room.",
    },
    "scene_flow_arc_contract_audit": {
        "path": "scene_flow_arc_contract_audit.json",
        "accepted": {"passed"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_scene_flow_arc_contract.py and prove each chapter reads as a sequence with movement, texture, payoff, and handoff.",
        "forbiddenWorkaround": "Do not hide a landmark stack behind transition effects.",
    },
    "final_cut_smoothness_contract_audit": {
        "path": "final_cut_smoothness_contract_audit.json",
        "accepted": {"passed"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_transition_grammar_plan.py",
        "requiredArtifact": "transition_grammar_plan/transition_grammar_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_grammar_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_final_cut_smoothness_contract.py and prove final adjacent joins have bridge, match, breathing, stable landing, and rare motion-effect proof.",
        "forbiddenWorkaround": "Do not cover rough hard joins, payoff-to-payoff jumps, or weak boundary clips with flashier effects.",
    },
    "reference_repair_closure_audit": {
        "path": "reference_repair_closure_audit.json",
        "accepted": {"passed", "passed_with_evidence_warnings"},
        "phase": "reference_style",
        "priority": "P0",
        "ownerScript": "prepare_reference_style_repair_plan.py",
        "requiredArtifact": "reference_style_repair_plan/reference_style_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_reference_repair_closure.py and prove P0 reference/style rows are closed by artifacts plus post-repair evidence.",
        "forbiddenWorkaround": "Do not leave 'make it closer to the reference' as prose without owner script, artifact, evidence, and closure audit.",
    },
    "resolve_blueprint_preflight": {
        "path": "resolve_blueprint_preflight.json",
        "accepted": {"ready", "ready_with_warnings"},
        "phase": "resolve_preflight",
        "priority": "P0",
        "ownerScript": "audit_resolve_blueprint.py",
        "requiredArtifact": "resolve_blueprint_preflight.json",
        "command": "python3 <skill-dir>/scripts/audit_resolve_blueprint.py --blueprint <package>/resolve_timeline_blueprint.json --package-dir <package> --json",
        "acceptanceEvidence": "Preflight proves media exists, ranges are valid, no V1 gaps/overlaps, title/subtitle/BGM/transition markers are package-local and safe before apply.",
        "forbiddenWorkaround": "Do not write Resolve or render while blueprint preflight is blocked.",
    },
}

KEYWORD_ROUTES: tuple[tuple[tuple[str, ...], dict[str, str]], ...] = (
    (
        ("portrait", "vertical", "orientation", "pillarbox", "square"),
        {
            "phase": "source_selection",
            "ownerScript": "prepare_orientation_repair_package.py",
            "requiredArtifact": "orientation_repair_package_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_orientation_repair_package.py --source-package <package> --output-dir <new-package> --json",
            "acceptanceEvidence": "Actual blueprint source paths ffprobe as landscape or explicitly designed phone/PiP inserts, then client and V14 audits pass.",
            "forbiddenWorkaround": "Do not crop only sampled final frames while leaving portrait sourcePath clips in the active Resolve blueprint.",
        },
    ),
    (
        ("bgm", "a3", "music", "audio", "voice", "camera voice", "source audio"),
        {
            "phase": "caption_audio",
            "ownerScript": "prepare_audio_scene_policy_plan.py",
            "requiredArtifact": "audio_scene_policy_plan/audio_scene_policy_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_audio_scene_policy_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "BGM selection, audio policy, BGM/audio contract, and story style prove A3 BGM-only delivery with no A1/A2 scenic voice leakage.",
            "forbiddenWorkaround": "Do not use hum tones, silence, source-camera audio, or generated voiceover when the delivery is BGM-only.",
        },
    ),
    (
        ("caption", "subtitle", "srt", "txt", "audience", "viewer"),
        {
            "phase": "caption_audio",
            "ownerScript": "prepare_caption_story_plan.py",
            "requiredArtifact": "caption_story_plan/caption_story_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_caption_story_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Audience caption audit passes and captions are natural viewer-facing travel lines with adequate density and title-zone suppression.",
            "forbiddenWorkaround": "Do not expose workflow, QA, version, Resolve, or repair-status language to viewers.",
        },
    ),
    (
        ("title", "cover", "ghost", "stacked", "date", "route label", "hero"),
        {
            "phase": "title_establishing",
            "ownerScript": "prepare_title_typography_plan.py",
            "requiredArtifact": "title_typography_plan/title_typography_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Title bridge and cover-title audits prove one clean scenic hero title with no duplicate, stacked, route/date, or subtitle-zone clutter.",
            "forbiddenWorkaround": "Do not add shadows, extra layers, or route/date labels to hide a weak title.",
        },
    ),
    (
        ("transition", "bridge", "hard cut", "rough", "join", "motion", "whip", "rotation", "speed"),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_grammar_plan.py",
            "requiredArtifact": "transition_grammar_plan/transition_grammar_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_grammar_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Transition grammar/execution/choreography/final-cut smoothness audits prove each boundary has motivated bridge, match, breath, and stable landing evidence.",
            "forbiddenWorkaround": "Do not hide missing route bridge footage or weak adjacent shots behind flashier transition effects.",
        },
    ),
)

ACTION_FIELDS = ("ownerScript", "requiredArtifact", "command", "acceptanceEvidence", "forbiddenWorkaround")


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


def clean_text(value: Any, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def accepted_status(report_id: str, spec: dict[str, Any], data: dict[str, Any]) -> bool:
    accepted = set(spec.get("accepted") or ACCEPTED_COMMON)
    return data.get("status") in accepted and not data.get("blockers")


def route_for(spec: dict[str, Any], blocker: str) -> dict[str, Any]:
    route = {
        "phase": spec["phase"],
        "priority": spec["priority"],
        "ownerScript": spec["ownerScript"],
        "requiredArtifact": spec["requiredArtifact"],
        "command": spec["command"],
        "acceptanceEvidence": spec["acceptanceEvidence"],
        "forbiddenWorkaround": spec["forbiddenWorkaround"],
    }
    lowered = blocker.lower()
    for keywords, override in KEYWORD_ROUTES:
        if any(keyword in lowered for keyword in keywords):
            route.update(override)
            break
    return route


def repair_row(
    *,
    row_index: int,
    report_id: str,
    report_path: Path,
    spec: dict[str, Any],
    issue_type: str,
    source_status: str | None,
    blocker: str,
    skill_dir: Path,
) -> dict[str, Any]:
    route = route_for(spec, blocker)
    owner_script = route["ownerScript"]
    owner_script_path = skill_dir / "scripts" / owner_script
    row = {
        "rowIndex": row_index,
        "priority": route["priority"],
        "phase": route["phase"],
        "issueType": issue_type,
        "sourceReport": report_id,
        "sourceReportPath": str(report_path),
        "sourceReportExists": report_path.exists(),
        "sourceStatus": source_status,
        "blocker": clean_text(blocker),
        "ownerScript": owner_script,
        "ownerScriptExists": owner_script_path.exists(),
        "requiredArtifact": route["requiredArtifact"],
        "command": route["command"],
        "acceptanceEvidence": route["acceptanceEvidence"],
        "blockedUntil": route["acceptanceEvidence"],
        "forbiddenWorkaround": route["forbiddenWorkaround"],
        "decision": {
            "acceptedRepair": False,
            "repairOwner": "",
            "repairStartedAt": "",
            "repairAppliedAt": "",
            "artifactEvidence": "",
            "postRepairAudit": "",
            "resolveReadbackEvidence": "",
            "renderFrameEvidence": "",
            "editorNotes": "",
        },
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    }
    row["actionable"] = row_actionable(row)
    return row


def row_actionable(row: dict[str, Any]) -> bool:
    safety = row.get("safety") if isinstance(row.get("safety"), dict) else {}
    return (
        all(str(row.get(field) or "").strip() for field in ACTION_FIELDS)
        and row.get("ownerScriptExists") is True
        and safety.get("writesResolve") is False
        and safety.get("queuesRender") is False
        and safety.get("downloadsExternalAssets") is False
        and safety.get("modifiesSourceFootage") is False
        and safety.get("modifiesSourceDrive") is False
    )


def build_report(package_dir: Path, skill_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    skill_dir = skill_dir.expanduser().resolve()
    rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []

    for report_id, spec in REPORT_SPECS.items():
        rel_path = Path(spec["path"])
        report_path = package_dir / rel_path
        data = load_json(report_path)
        status = data.get("status") if isinstance(data, dict) else None
        summary = summary_of(data)
        accepted = isinstance(data, dict) and accepted_status(report_id, spec, data)
        report_rows.append(
            {
                "report": report_id,
                "path": str(report_path),
                "exists": report_path.exists(),
                "status": status,
                "accepted": accepted,
                "acceptedStatuses": sorted(spec.get("accepted") or ACCEPTED_COMMON),
                "summary": summary,
            }
        )
        if data is None:
            rows.append(
                repair_row(
                    row_index=len(rows) + 1,
                    report_id=report_id,
                    report_path=report_path,
                    spec=spec,
                    issue_type="missing_required_report",
                    source_status=None,
                    blocker=f"Required report is missing: {spec['path']}",
                    skill_dir=skill_dir,
                )
            )
            continue
        if accepted:
            continue
        blockers = data.get("blockers") if isinstance(data.get("blockers"), list) else []
        if not blockers:
            blockers = [f"Report status `{status}` is not in accepted statuses {sorted(spec.get('accepted') or ACCEPTED_COMMON)}"]
        for blocker in blockers:
            rows.append(
                repair_row(
                    row_index=len(rows) + 1,
                    report_id=report_id,
                    report_path=report_path,
                    spec=spec,
                    issue_type="blocked_or_unaccepted_report",
                    source_status=status,
                    blocker=str(blocker),
                    skill_dir=skill_dir,
                )
            )

    phase_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    for row in rows:
        phase_counts[str(row.get("phase"))] = phase_counts.get(str(row.get("phase")), 0) + 1
        priority_counts[str(row.get("priority"))] = priority_counts.get(str(row.get("priority")), 0) + 1

    actionable_count = len([row for row in rows if row.get("actionable") is True])
    p0_count = len([row for row in rows if row.get("priority") == "P0"])
    unactionable = [row for row in rows if row.get("actionable") is not True]
    missing_reports = [row for row in report_rows if not row["exists"]]
    blocked_reports = [row for row in report_rows if row["exists"] and not row["accepted"]]
    if not rows:
        status = "ready_no_unattended_repairs_needed"
    elif not unactionable:
        status = "ready_with_unattended_repair_queue"
    else:
        status = "blocked_unactionable_repair_queue"

    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "contract": "unattended_repair_queue",
        "packageDir": str(package_dir),
        "skillDir": str(skill_dir),
        "reports": report_rows,
        "repairRows": rows,
        "blockers": [
            f"Repair row {row.get('rowIndex')} is not actionable: {row.get('sourceReport')}"
            for row in unactionable
        ],
        "warnings": [],
        "summary": {
            "requiredReportCount": len(REPORT_SPECS),
            "missingRequiredReportCount": len(missing_reports),
            "blockedReportCount": len(blocked_reports),
            "acceptedReportCount": len([row for row in report_rows if row["accepted"]]),
            "repairRowCount": len(rows),
            "p0RepairRowCount": p0_count,
            "p1RepairRowCount": len([row for row in rows if row.get("priority") == "P1"]),
            "actionableRepairRowCount": actionable_count,
            "unactionableRepairRowCount": len(unactionable),
            "rowsWithOwnerScript": len([row for row in rows if row.get("ownerScript")]),
            "rowsWithRequiredArtifact": len([row for row in rows if row.get("requiredArtifact")]),
            "rowsWithCommand": len([row for row in rows if row.get("command")]),
            "rowsWithAcceptanceEvidence": len([row for row in rows if row.get("acceptanceEvidence")]),
            "rowsWithForbiddenWorkaround": len([row for row in rows if row.get("forbiddenWorkaround")]),
            "phaseCounts": phase_counts,
            "priorityCounts": priority_counts,
        },
        "selectionRubric": {
            "pass": [
                "If repairRowCount is zero, continue with unattended/Resolve handoff gates.",
                "If repair rows exist, complete P0 rows in phase order before another Resolve apply or render claim.",
                "After each repair, rerun the owner script, its acceptance audit, this repair queue, unattended first-draft, V14 baseline, and final QA as applicable.",
            ],
            "reject": [
                "Reject any queue row missing ownerScript, command, requiredArtifact, acceptanceEvidence, or forbiddenWorkaround.",
                "Reject any attempt to bypass source/story/audio/transition blockers with stock, titles, effects, or stale QA evidence.",
            ],
        },
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Unattended Repair Queue",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Skill: `{report['skillDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Repair Rows",
    ]
    for row in report["repairRows"]:
        lines.extend(
            [
                "",
                f"### {row['rowIndex']}. {row['priority']} {row['phase']} - {row['sourceReport']}",
                f"- Actionable: `{row['actionable']}`",
                f"- Issue: `{row['issueType']}`",
                f"- Blocker: {row['blocker']}",
                f"- Owner script: `{row['ownerScript']}`",
                f"- Required artifact: `{row['requiredArtifact']}`",
                f"- Command: `{row['command']}`",
                f"- Acceptance: {row['acceptanceEvidence']}",
                f"- Forbidden workaround: {row['forbiddenWorkaround']}",
            ]
        )
    if not report["repairRows"]:
        lines.append("")
        lines.append("No unattended repairs are needed.")
    if report["blockers"]:
        lines.extend(["", "## Queue Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Safety", "", "```json", json.dumps(report["safety"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an actionable repair queue from unattended travel-video QA reports.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    report = build_report(package_dir, skill_dir)
    out_dir = package_dir / "unattended_repair_queue"
    write_json(out_dir / "unattended_repair_queue.json", report)
    write_markdown(out_dir / "unattended_repair_queue.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked_unactionable_repair_queue" else 0


if __name__ == "__main__":
    raise SystemExit(main())
