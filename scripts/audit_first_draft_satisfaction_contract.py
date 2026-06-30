#!/usr/bin/env python3
"""Aggregate first-draft satisfaction gates into executable repair rows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from audit_final_viewer_friction_contract import REPORT_SPECS as VIEWER_REPORT_SPECS
    from prepare_unattended_repair_queue import REPORT_SPECS as REPAIR_REPORT_SPECS
except ModuleNotFoundError:
    from scripts.audit_final_viewer_friction_contract import REPORT_SPECS as VIEWER_REPORT_SPECS
    from scripts.prepare_unattended_repair_queue import REPORT_SPECS as REPAIR_REPORT_SPECS


PASSED = "passed"
BLOCKED = "blocked_first_draft_satisfaction"


FIRST_DRAFT_GATES: tuple[tuple[str, str, str], ...] = (
    ("raw_intake_completeness_audit", "source_route", "The draft may be cut from samples, stale derived clips, or filename order."),
    ("large_source_unattended_readiness_contract_audit", "source_route", "A 100GB-class unordered folder is not yet safe for unattended first draft."),
    ("source_selection_coverage_contract_audit", "source_selection", "Chapters may lack movement, lived-in texture, payoff, or orientation-repaired source coverage."),
    ("first_assembly_source_order_contract_audit", "source_selection", "The first assembly does not prove full-source selected order."),
    ("final_source_usage_contract_audit", "source_selection", "The final candidate may still use unmatched, repair, reject, or utility-dominant clips."),
    ("creator_cut_application_contract_audit", "creator_cut", "Weak or rejected source choices may remain active in the final candidate."),
    ("opening_story_plan", "opening", "The first three minutes do not yet have promise, destination proof, arrival, texture, and handoff."),
    ("cover_title_contract_audit", "opening_title", "Opening or cover title may be ghosted, stacked, generic, or cluttered."),
    ("title_visual_proof_contract_audit", "opening_title", "No extracted local frames prove the title is clean in the actual viewer frame."),
    ("title_typography_repair_plan", "opening_title", "Known title typography repairs are still open."),
    ("visual_establishing_plan", "establishing", "Opening, chapter, or ending establishing material is missing or unproven."),
    ("bgm_selection_package", "audio_caption", "BGM is missing, untraceable, silent, hum-like, or not materialized into the package."),
    ("audio_scene_policy_plan", "audio_caption", "Scenic, title, or transition sections may leak source-camera or voice audio."),
    ("bgm_audio_contract_audit", "audio_caption", "BGM-only/no-voiceover delivery is not proven."),
    ("bgm_musicality_contract_audit", "audio_caption", "The music bed may still sound like hum, tone, silence, or placeholder audio."),
    ("audience_caption_contract_audit", "audio_caption", "Captions may speak to the editor instead of the viewer."),
    ("chapter_arc_plan", "story_spine", "Chapter arcs are not planned as context, movement, texture, payoff, and aftertaste."),
    ("chapter_story_spine_contract_audit", "story_spine", "Chapter story spine may not survive into the final candidate."),
    ("shot_flow_continuity_contract_audit", "story_spine", "Shot order may still feel random or landmark-stacked."),
    ("reference_scene_grammar_contract_audit", "story_spine", "Opening, chapters, transitions, or ending may ignore the learned reference scene grammar."),
    ("timeline_variety_contract_audit", "rhythm", "The film may lack movement, texture, payoff, and aftertaste variety."),
    ("pacing_watchability_contract_audit", "rhythm", "The cut may still have AI-like pacing, long holds, or unreadable short runs."),
    ("narrative_adjacency_contract_audit", "rhythm", "Adjacent shots may lack viewer-readable route, place, story, bridge, BGM, or title reasons."),
    ("scene_flow_arc_contract_audit", "rhythm", "Scenes may not form setup, movement, lived-in texture, payoff, and handoff arcs."),
    ("final_cut_smoothness_contract_audit", "transition_flow", "Adjacent joins may still feel rough, effect-hidden, or unlanded."),
    ("transition_flow_repair_plan", "transition_flow", "Transition-flow repair rows are still open."),
    ("transition_reference_readiness_contract_audit", "transition_flow", "The whole transition chain is not reference-ready."),
    ("transition_watch_reel", "transition_flow", "Important transitions have not been reviewed as one ordered muted reel."),
    ("transition_watch_reel_review_contract_audit", "transition_flow", "The transition reel may repeat template motion, leak audio, or overuse high-intensity effects."),
    ("rendered_transition_proof_contract_audit", "transition_flow", "The final render may hide black/white flashes, portrait frames, or unstable transition landings."),
    ("resolve_transition_apply_contract_audit", "transition_flow", "Visible transitions may be marker-only or pending manual instructions."),
    ("reference_review_repair_plan", "reference_fit", "Supplied reference videos have not been closed as full-film reviews."),
    ("reference_repair_closure_audit", "reference_fit", "Reference/style repair rows are not closed by artifacts and post-repair evidence."),
    ("reference_profile_application_contract_audit", "reference_fit", "Reference learning may remain unused analysis rather than applied edit behavior."),
    ("reference_transition_profile_contract_audit", "reference_fit", "Transition language may not match the learned bridge, breath, match, and restrained-motion profile."),
    ("director_intent_contract_audit", "reference_fit", "The edit may lack clear mission, chapter intent, pacing intent, captions, or ending aftertaste."),
    ("route_texture_contract_audit", "route_texture", "The film may lack route texture such as transport, street life, food, waiting, weather, or detail."),
    ("director_polish_contract_audit", "final_watchdown", "Director polish may still have hidden warnings or blockers."),
    ("editorial_watchdown_repair_plan", "final_watchdown", "The current final MP4 has not been closed by an end-to-end viewer watchdown."),
    ("final_viewer_friction_contract_audit", "final_watchdown", "Viewer-facing title, BGM, caption, source, story, transition, reference, route, or watchdown friction remains."),
)


CUSTOM_SPECS: dict[str, dict[str, Any]] = {
    "bgm_musicality_contract_audit": {
        "path": "bgm_musicality_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_bgm_selection_package.py",
        "requiredArtifact": "bgm_selection_package/bgm_selection_package.json",
        "command": "python3 <skill-dir>/scripts/prepare_bgm_selection_package.py --package-dir <package> --json",
        "acceptanceEvidence": "BGM musicality passes with named local music, phrase coverage, dynamics, and multi-band energy.",
        "forbiddenWorkaround": "Do not pass with hum tones, silence, source-camera audio, or placeholder generated pads.",
    },
    "title_visual_proof_contract_audit": {
        "path": "title_visual_proof_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "audit_title_visual_proof_contract.py",
        "requiredArtifact": "title_visual_proof_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_title_visual_proof_contract.py --package-dir <package> --extract-frames --json",
        "acceptanceEvidence": "Extracted title frames prove clean scenic 16:9 title composition with no stacked text or subtitle collision.",
        "forbiddenWorkaround": "Do not close title quality from manifest prose, OCR excuses, or stale screenshots.",
    },
    "final_source_usage_contract_audit": {
        "path": "final_source_usage_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_footage_select_plan.py",
        "requiredArtifact": "footage_select_plan/footage_select_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_footage_select_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Final source usage proves active raw clips come from selected hero/main/texture choices.",
        "forbiddenWorkaround": "Do not rescue weak source selection with stock, titles, or stronger effects.",
    },
    "chapter_story_spine_contract_audit": {
        "path": "chapter_story_spine_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Each chapter executes context, movement, lived-in texture, payoff, and aftertaste.",
        "forbiddenWorkaround": "Do not hide missing story beats behind title cards, stock inserts, or transition effects.",
    },
    "shot_flow_continuity_contract_audit": {
        "path": "shot_flow_continuity_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Final shot order reads as setup, movement, texture, payoff, and aftertaste.",
        "forbiddenWorkaround": "Do not use transitions to hide random clip stacking.",
    },
    "reference_scene_grammar_contract_audit": {
        "path": "reference_scene_grammar_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_reference_style_repair_plan.py",
        "requiredArtifact": "reference_style_repair_plan/reference_style_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Reference scene grammar reaches opening, chapters, transitions, and ending.",
        "forbiddenWorkaround": "Do not claim reference fit from unused analysis or vague adjectives.",
    },
    "timeline_variety_contract_audit": {
        "path": "timeline_variety_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Movement, lived-in texture, destination payoff, and ending aftertaste vary across the film.",
        "forbiddenWorkaround": "Do not hide weak shot variety behind transitions.",
    },
    "pacing_watchability_contract_audit": {
        "path": "pacing_watchability_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Reference-calibrated shot lengths, chapter breathing, long-hold reduction, and short-clip readability are proven.",
        "forbiddenWorkaround": "Do not add effects over flat pacing.",
    },
    "narrative_adjacency_contract_audit": {
        "path": "narrative_adjacency_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Every adjacent visual shot has a viewer-readable route, place, story, bridge, BGM, title, or transition reason.",
        "forbiddenWorkaround": "Do not stack unrelated scenic clips and depend on effects to imply story.",
    },
    "reference_transition_profile_contract_audit": {
        "path": "reference_transition_profile_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "ownerScript": "prepare_transition_reference_candidates.py",
        "requiredArtifact": "transition_reference_candidates/transition_reference_candidates.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_reference_candidates.py --package-dir <package> --json",
        "acceptanceEvidence": "Current transitions match the learned non-copying bridge, breath, match, and restrained-motion profile.",
        "forbiddenWorkaround": "Do not imitate reference quality with random visible effects or copied assets.",
    },
    "director_intent_contract_audit": {
        "path": "director_intent_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "ownerScript": "prepare_reference_style_repair_plan.py",
        "requiredArtifact": "reference_style_repair_plan/reference_style_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Opening mission, chapter arcs, pacing, captions, BGM/no-voiceover support, and ending intent are proven.",
        "forbiddenWorkaround": "Do not call a montage polished when it has no director intent.",
    },
    "director_polish_contract_audit": {
        "path": "director_polish_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P1",
        "ownerScript": "prepare_reference_style_repair_plan.py",
        "requiredArtifact": "reference_style_repair_plan/reference_style_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Director polish passes after title, BGM, route, reference, stock/aerial, and style audits.",
        "forbiddenWorkaround": "Do not hide polish gaps behind package integrity or render success.",
    },
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


def clean(value: Any, limit: int = 900) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def spec_index() -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for report_id, spec in REPAIR_REPORT_SPECS.items():
        if report_id == "first_draft_satisfaction_contract_audit":
            continue
        indexed[report_id] = dict(spec)
    for spec in VIEWER_REPORT_SPECS:
        report_id = str(spec.get("reportId") or "")
        if report_id and report_id not in indexed:
            indexed[report_id] = dict(spec)
    indexed.update(CUSTOM_SPECS)
    return indexed


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def row_from_gate(package_dir: Path, spec: dict[str, Any], report_id: str, category: str, symptom: str) -> dict[str, Any]:
    path = package_dir / spec["path"]
    data = load_json(path) or {}
    status = data.get("status") if isinstance(data, dict) else None
    blockers = data.get("blockers") if isinstance(data, dict) and isinstance(data.get("blockers"), list) else []
    warnings = data.get("warnings") if isinstance(data, dict) and isinstance(data.get("warnings"), list) else []
    accepted = set(spec["accepted"])
    passed = bool(path.exists() and status in accepted and not blockers)
    if not path.exists():
        issue = f"{report_id} is missing"
    elif status not in accepted:
        issue = f"{report_id} status is {status!r}; expected one of {sorted(accepted)}"
    elif blockers:
        issue = f"{report_id} still has blockers"
    else:
        issue = ""
    return {
        "repairId": f"first_draft_satisfaction_{report_id}",
        "reportId": report_id,
        "sourceReport": "first_draft_satisfaction_contract_audit",
        "sourceReportPath": str(path),
        "reportExists": path.exists(),
        "reportStatus": status,
        "acceptedStatuses": sorted(accepted),
        "passed": passed,
        "priority": spec.get("priority", "P0"),
        "category": category,
        "phase": spec.get("phase", category),
        "viewerSymptom": spec.get("viewerSymptom") or symptom,
        "issue": issue,
        "ownerScript": spec["ownerScript"],
        "requiredArtifact": spec["requiredArtifact"],
        "command": spec["command"],
        "acceptanceEvidence": spec["acceptanceEvidence"],
        "forbiddenWorkaround": spec["forbiddenWorkaround"],
        "summary": summary_of(data),
        "blockers": [clean(item) for item in blockers[:12]],
        "warnings": [clean(item) for item in warnings[:12]],
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    specs = spec_index()
    evidence_rows: list[dict[str, Any]] = []
    missing_spec_ids: list[str] = []
    for report_id, category, symptom in FIRST_DRAFT_GATES:
        spec = specs.get(report_id)
        if not spec:
            missing_spec_ids.append(report_id)
            continue
        evidence_rows.append(row_from_gate(package_dir, spec, report_id, category, symptom))
    missing_spec_rows = [
        {
            "repairId": f"first_draft_satisfaction_missing_spec_{report_id}",
            "reportId": report_id,
            "sourceReport": "first_draft_satisfaction_contract_audit",
            "sourceReportPath": "",
            "reportExists": False,
            "reportStatus": None,
            "acceptedStatuses": [],
            "passed": False,
            "priority": "P0",
            "category": "skill_integration",
            "phase": "skill_integration",
            "viewerSymptom": "The satisfaction gate itself is missing an owner-script route.",
            "issue": f"No report spec is registered for {report_id}",
            "ownerScript": "audit_first_draft_satisfaction_contract.py",
            "requiredArtifact": "first_draft_satisfaction_contract_audit.json",
            "command": "python3 <skill-dir>/scripts/audit_first_draft_satisfaction_contract.py --package-dir <package> --json",
            "acceptanceEvidence": "The script contains a spec for the report and reruns cleanly.",
            "forbiddenWorkaround": "Do not remove the gate from FIRST_DRAFT_GATES to make the aggregate pass.",
            "summary": {},
            "blockers": [],
            "warnings": [],
        }
        for report_id in missing_spec_ids
    ]
    evidence_rows.extend(missing_spec_rows)
    satisfaction_rows = [row for row in evidence_rows if not row["passed"]]
    category_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    for row in satisfaction_rows:
        category_counts[str(row.get("category"))] = category_counts.get(str(row.get("category")), 0) + 1
        priority_counts[str(row.get("priority"))] = priority_counts.get(str(row.get("priority")), 0) + 1
    summary_payload = {
        "requiredReportCount": len(evidence_rows),
        "passedReportCount": len([row for row in evidence_rows if row["passed"]]),
        "satisfactionRowCount": len(satisfaction_rows),
        "p0SatisfactionRowCount": len([row for row in satisfaction_rows if row.get("priority") == "P0"]),
        "p1SatisfactionRowCount": len([row for row in satisfaction_rows if row.get("priority") == "P1"]),
        "missingReportCount": len([row for row in satisfaction_rows if not row.get("reportExists")]),
        "blockedReportCount": len([row for row in satisfaction_rows if row.get("reportExists")]),
        "categoryCounts": category_counts,
        "priorityCounts": priority_counts,
        "ownerScripts": sorted({row["ownerScript"] for row in satisfaction_rows}),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": PASSED if not satisfaction_rows else BLOCKED,
        "contract": "first_draft_satisfaction",
        "packageDir": str(package_dir),
        "summary": summary_payload,
        "evidenceRows": evidence_rows,
        "satisfactionRows": satisfaction_rows,
        "repairRows": satisfaction_rows,
        "policy": {
            "blocksFirstDraftHandoffWhenOpen": True,
            "aggregatesSourceStoryAudioTitleRhythmTransitionReferenceWatchdown": True,
            "excludesFinalQaV14AndSkillMaturityToAvoidDependencyCycles": True,
            "routeEveryOpenRowToOwnerScript": True,
            "noResolveWrites": True,
        },
        "nextActions": [
            "Run owner scripts for P0 satisfaction rows in source, opening, audio, story, rhythm, transition, reference, route, then watchdown order.",
            "Rerun each source report after repair, then rerun this contract before final QA, V14 baseline, or handoff.",
            "Do not call a draft reference-level while this contract has satisfaction rows.",
        ],
        "safety": safety(),
    }
    if args.max_rows and len(report["satisfactionRows"]) > args.max_rows:
        report["satisfactionRows"] = report["satisfactionRows"][: args.max_rows]
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# First Draft Satisfaction Contract",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Satisfaction Rows",
    ]
    if not report.get("satisfactionRows"):
        lines.append("- None.")
    for row in report.get("satisfactionRows", [])[:200]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Category: `{row.get('category')}`",
                f"- Report: `{row.get('reportId')}` status=`{row.get('reportStatus')}`",
                f"- Viewer symptom: {row.get('viewerSymptom')}",
                f"- Issue: {row.get('issue')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Command: `{row.get('command')}`",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
            ]
        )
        if row.get("blockers"):
            lines.append(f"- Source blockers: `{'; '.join(row.get('blockers') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- This is a first-draft satisfaction aggregation gate, not a replacement for full-film watching.",
            "- It intentionally excludes final QA, V14 baseline, and Skill maturity so those gates can depend on it without cycles.",
            "- The gate is read-only: no Resolve writes, no render queue, no downloads, no source-drive mutation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether the first serious draft is ready to satisfy a viewer.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "first_draft_satisfaction_contract_audit.json", report)
    write_markdown(package_dir / "first_draft_satisfaction_contract_audit.md", report)
    payload = (
        report
        if args.json
        else {
            "status": report["status"],
            "summary": report["summary"],
            "blockers": [row["repairId"] for row in report["satisfactionRows"]],
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
