#!/usr/bin/env python3
"""Aggregate whole-film viewer satisfaction gates before handoff."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = "passed"
BLOCKED = "blocked_whole_film_satisfaction"


WHOLE_FILM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "reportId": "render_delivery_verification",
        "path": "render_delivery_verification.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "final_output",
        "viewerSymptom": "The candidate being judged is stale, missing, or not the verified final MP4.",
        "ownerScript": "verify_render_delivery.py",
        "requiredArtifact": "render_delivery_verification.json",
        "command": "python3 <skill-dir>/scripts/verify_render_delivery.py --package-dir <package> --output <final-mp4> --json",
        "acceptanceEvidence": "Current final MP4 render verification passes with valid video/audio, black-frame scan, frame samples, and subtitle evidence.",
        "forbiddenWorkaround": "Do not judge whole-film quality from stale renders, screenshots, contact sheets, or unverified exports.",
    },
    {
        "reportId": "opening_story_plan",
        "path": "opening_story_plan/opening_story_plan.json",
        "accepted": {"ready_with_opening_story_plan"},
        "priority": "P0",
        "phase": "opening",
        "viewerSymptom": "The first three minutes do not prove a viewer promise, destination signal, clean title, arrival, texture, and handoff.",
        "ownerScript": "prepare_opening_story_plan.py",
        "requiredArtifact": "opening_story_plan/opening_story_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Opening plan and downstream audits prove the first three minutes work as a travel-film opening.",
        "forbiddenWorkaround": "Do not use a generic scenic clip, black slate, route label, or montage intro as a reference-level opening.",
    },
    {
        "reportId": "title_visual_proof_contract_audit",
        "path": "title_visual_proof_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "opening",
        "viewerSymptom": "The opening/chapter title may still be ghosted, stacked, route/date cluttered, subtitle-overlapped, or unproven in frames.",
        "ownerScript": "audit_title_visual_proof_contract.py",
        "requiredArtifact": "title_visual_proof_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_title_visual_proof_contract.py --package-dir <package> --extract-frames --json",
        "acceptanceEvidence": "Actual extracted title frames prove clean scenic 16:9 title composition with title-zone subtitle suppression.",
        "forbiddenWorkaround": "Do not close title quality from manifest prose, OCR excuses, or old screenshots.",
    },
    {
        "reportId": "chapter_story_spine_contract_audit",
        "path": "chapter_story_spine_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "chapters",
        "viewerSymptom": "Chapters may still feel like landmark stacks rather than context, movement, texture, payoff, and aftertaste.",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Chapter story-spine proof shows each chapter executes the required travel-film beats.",
        "forbiddenWorkaround": "Do not hide missing chapter structure with titles, stock inserts, or transition effects.",
    },
    {
        "reportId": "shot_flow_continuity_contract_audit",
        "path": "shot_flow_continuity_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "chapters",
        "viewerSymptom": "Shot order may still feel random, filename-order, or clip-dump-like.",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Shot-flow proof shows chapters move through readable setup, movement, texture, payoff, and handoff beats.",
        "forbiddenWorkaround": "Do not rely on BGM or transitions to imply continuity between unrelated shots.",
    },
    {
        "reportId": "timeline_variety_contract_audit",
        "path": "timeline_variety_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "rhythm",
        "viewerSymptom": "The whole film may repeat the same shot role instead of varying movement, lived-in detail, payoff, and ending aftertaste.",
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Timeline-variety proof shows route movement, texture, destination payoff, and aftertaste vary across the film.",
        "forbiddenWorkaround": "Do not hide weak shot variety behind faster cuts or stronger effects.",
    },
    {
        "reportId": "pacing_watchability_contract_audit",
        "path": "pacing_watchability_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "rhythm",
        "viewerSymptom": "The film may still feel AI-made because of long raw holds, flickery short runs, or flat pacing.",
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Pacing watchability proves reference-calibrated shot lengths, chapter breath, and readable cutaway rhythm.",
        "forbiddenWorkaround": "Do not fix flat pacing by adding decorative effects over weak shot order.",
    },
    {
        "reportId": "bgm_audio_contract_audit",
        "path": "bgm_audio_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "Scenic/title/transition moments may leak source-camera or voiceover audio instead of BGM-only travel-film sound.",
        "ownerScript": "prepare_audio_scene_policy_plan.py",
        "requiredArtifact": "audio_scene_policy_plan/audio_scene_policy_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_audio_scene_policy_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Audio policy, BGM/audio contract, and Resolve readback prove A3 BGM-only scenic/title/transition delivery.",
        "forbiddenWorkaround": "Do not leave camera/user voice under scenic openings, title bridges, transition bridges, or aerial/landmark sequences.",
    },
    {
        "reportId": "bgm_musicality_contract_audit",
        "path": "bgm_musicality_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "The soundtrack may still sound like hum, tone, silence, one-band placeholder audio, or mismatched scenic music.",
        "ownerScript": "prepare_bgm_selection_package.py",
        "requiredArtifact": "bgm_selection_package/bgm_selection_package.json",
        "command": "python3 <skill-dir>/scripts/prepare_bgm_selection_package.py --package-dir <package> --json",
        "acceptanceEvidence": "BGM musicality proves named local music, phrase coverage, dynamics, and multi-band energy.",
        "forbiddenWorkaround": "Do not pass with sine pads, hum tones, silence, camera audio, generated voiceover, or untraceable music.",
    },
    {
        "reportId": "audience_caption_contract_audit",
        "path": "audience_caption_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "Captions may still describe editing work, QA, tools, versions, or delivery status instead of speaking to the viewer.",
        "ownerScript": "prepare_caption_story_plan.py",
        "requiredArtifact": "caption_story_plan/caption_story_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_caption_story_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Audience-caption audit proves TXT/SRT/burned captions are dense, title-safe, and viewer-facing.",
        "forbiddenWorkaround": "Do not expose workflow, repair, Resolve, export, version, or delivery-state language to viewers.",
    },
    {
        "reportId": "transition_sequence_satisfaction_contract_audit",
        "path": "transition_sequence_satisfaction_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "transitions",
        "viewerSymptom": "The ordered transition experience may still feel random, flashy, audio-leaky, template-like, or unlanded.",
        "ownerScript": "audit_transition_sequence_satisfaction_contract.py",
        "requiredArtifact": "transition_sequence_satisfaction_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_transition_sequence_satisfaction_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Transition sequence satisfaction passes with zero open rows, zero metric issues, muted watch-reel proof, bridge/breath/landing proof, and Resolve/rendered proof.",
        "forbiddenWorkaround": "Do not approve the whole film while transitions pass isolated checks but fail as one viewer sequence.",
    },
    {
        "reportId": "rendered_transition_proof_contract_audit",
        "path": "rendered_transition_proof_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "transitions",
        "viewerSymptom": "The final render may hide black/white flashes, raw portrait frames, or unstable landing frames at transitions.",
        "ownerScript": "audit_rendered_transition_proof_contract.py",
        "requiredArtifact": "rendered_transition_proof_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_rendered_transition_proof_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Rendered transition proof passes on current final-MP4 transition windows.",
        "forbiddenWorkaround": "Do not treat transition recipes as fixed until rendered final-frame proof is clean.",
    },
    {
        "reportId": "reference_profile_application_contract_audit",
        "path": "reference_profile_application_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "reference_fit",
        "viewerSymptom": "The four reference videos or Malta final may be analyzed but not applied to opening, rhythm, transitions, captions, audio, and ending.",
        "ownerScript": "prepare_reference_style_repair_plan.py",
        "requiredArtifact": "reference_style_repair_plan/reference_style_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Reference-profile application proves learned non-copying targets reach concrete package artifacts.",
        "forbiddenWorkaround": "Do not claim reference fit from vague adjectives, sampled-frame impressions, or unused analysis.",
    },
    {
        "reportId": "reference_style_alignment_audit",
        "path": "reference_style_alignment_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "reference_fit",
        "viewerSymptom": "The edit may technically pass but still not feel like the requested Bilibili/Malta travel-film direction.",
        "ownerScript": "audit_reference_style_alignment.py",
        "requiredArtifact": "reference_style_alignment_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_reference_style_alignment.py --package-dir <package> --json",
        "acceptanceEvidence": "Reference alignment proves route chapters, transport connective tissue, lived-in detail, landmarks, variety, scenic titles, captions, and BGM support.",
        "forbiddenWorkaround": "Do not claim reference-level quality from technical checks alone.",
    },
    {
        "reportId": "director_intent_contract_audit",
        "path": "director_intent_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "director",
        "viewerSymptom": "The film may lack a clear opening mission, route arc, caption story, pacing intent, or ending aftertaste.",
        "ownerScript": "audit_director_intent_contract.py",
        "requiredArtifact": "director_intent_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_director_intent_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Director intent proves the film has mission, route arc, chapter intent, pacing intent, captions, BGM/no-voiceover support, and aftertaste.",
        "forbiddenWorkaround": "Do not call a montage polished when it has no director intent.",
    },
    {
        "reportId": "route_texture_contract_audit",
        "path": "route_texture_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "director",
        "viewerSymptom": "The film may lack travel texture: transport, street life, food, waiting, weather, hotel/window detail, or physical route bridges.",
        "ownerScript": "audit_route_texture_contract.py",
        "requiredArtifact": "route_texture_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_route_texture_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Route texture proves planned day/place transitions and chapters are backed by real route/lived-in footage.",
        "forbiddenWorkaround": "Do not build a landmark-only montage and hide missing lived-in detail with title cards or effects.",
    },
    {
        "reportId": "director_polish_contract_audit",
        "path": "director_polish_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P1",
        "phase": "director",
        "viewerSymptom": "The film may still lack premium finish across aerial/title typography, BGM mood/license, restrained effects, subtitles, Resolve readback, and export quality.",
        "ownerScript": "audit_director_polish_contract.py",
        "requiredArtifact": "director_polish_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_director_polish_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Director polish passes after title, BGM, route, reference, stock/aerial, Resolve, subtitle, and export audits.",
        "forbiddenWorkaround": "Do not hide polish gaps behind package integrity or render success.",
    },
    {
        "reportId": "editorial_watchdown_repair_plan",
        "path": "editorial_watchdown_repair_plan/editorial_watchdown_repair_plan.json",
        "accepted": {"ready_no_editorial_watchdown_repairs_needed"},
        "priority": "P0",
        "phase": "watchdown",
        "viewerSymptom": "The current final MP4 has not been watched and signed off as a full viewer-facing film.",
        "ownerScript": "prepare_editorial_watchdown_repair_plan.py",
        "requiredArtifact": "editorial_watchdown_repair_plan/editorial_watchdown_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_editorial_watchdown_repair_plan.py --package-dir <package> --final-output <final-mp4> --json",
        "acceptanceEvidence": "Watchdown closes current-output rows for final output, opening, chapters, transitions, BGM/captions, ending, and reference fit.",
        "forbiddenWorkaround": "Do not hand off from technical QA, sampled frames, screenshots, or stale watch notes alone.",
    },
    {
        "reportId": "final_viewer_friction_contract_audit",
        "path": "final_viewer_friction_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "watchdown",
        "viewerSymptom": "Viewer-facing title, BGM, caption, source, story, transition, reference, route, or watchdown friction remains.",
        "ownerScript": "audit_final_viewer_friction_contract.py",
        "requiredArtifact": "final_viewer_friction_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_final_viewer_friction_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Final viewer friction passes with zero P0/P1 viewer-friction rows and all required evidence reports passing.",
        "forbiddenWorkaround": "Do not treat a technically passing render as viewer-ready while any friction rows remain open.",
    },
    {
        "reportId": "first_draft_satisfaction_contract_audit",
        "path": "first_draft_satisfaction_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "watchdown",
        "viewerSymptom": "The first serious draft still has source, opening, BGM, caption, story, rhythm, transition, reference, route, or watchdown rows.",
        "ownerScript": "audit_first_draft_satisfaction_contract.py",
        "requiredArtifact": "first_draft_satisfaction_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_first_draft_satisfaction_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "First-draft satisfaction passes with zero satisfaction rows and every required report accepted.",
        "forbiddenWorkaround": "Do not claim a first serious draft is reference-level while this aggregate gate still has rows.",
    },
    {
        "reportId": "unattended_repair_queue",
        "path": "unattended_repair_queue/unattended_repair_queue.json",
        "accepted": {"ready_no_unattended_repairs_needed"},
        "priority": "P0",
        "phase": "handoff",
        "viewerSymptom": "Open owner-script repair rows remain, so another AI would still need manual interpretation.",
        "ownerScript": "prepare_unattended_repair_queue.py",
        "requiredArtifact": "unattended_repair_queue/unattended_repair_queue.json",
        "command": "python3 <skill-dir>/scripts/prepare_unattended_repair_queue.py --package-dir <package> --json",
        "acceptanceEvidence": "Unattended repair queue has zero repair rows and no unactionable rows.",
        "forbiddenWorkaround": "Do not hand off while open QA issues are still prose instead of closed artifacts.",
    },
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


def clean(value: Any, limit: int = 900) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


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


def metric_issues(report_id: str, summary: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if report_id == "editorial_watchdown_repair_plan":
        if int(summary.get("repairRowCount") or 0) != 0:
            issues.append(f"repairRowCount is {summary.get('repairRowCount')}")
        if int(summary.get("supportingReportIssueCount") or 0) != 0:
            issues.append(f"supportingReportIssueCount is {summary.get('supportingReportIssueCount')}")
        if summary.get("finalOutputExists") is not True:
            issues.append("finalOutputExists is not true")
        if int(summary.get("watchRowCount") or 0) < 6:
            issues.append(f"watchRowCount is {summary.get('watchRowCount')}; expected at least 6")
        if int(summary.get("closedWatchRowCount") or 0) != int(summary.get("watchRowCount") or 0):
            issues.append("closedWatchRowCount does not equal watchRowCount")
    if report_id == "final_viewer_friction_contract_audit":
        if int(summary.get("viewerFrictionRowCount") or 0) != 0:
            issues.append(f"viewerFrictionRowCount is {summary.get('viewerFrictionRowCount')}")
        if int(summary.get("p0ViewerFrictionRowCount") or 0) != 0:
            issues.append(f"p0ViewerFrictionRowCount is {summary.get('p0ViewerFrictionRowCount')}")
        if int(summary.get("p1ViewerFrictionRowCount") or 0) != 0:
            issues.append(f"p1ViewerFrictionRowCount is {summary.get('p1ViewerFrictionRowCount')}")
        if int(summary.get("evidenceReportCount") or 0) < 20:
            issues.append(f"evidenceReportCount is {summary.get('evidenceReportCount')}; expected at least 20")
        if int(summary.get("passedEvidenceReportCount") or 0) != int(summary.get("evidenceReportCount") or 0):
            issues.append("passedEvidenceReportCount does not equal evidenceReportCount")
    if report_id == "first_draft_satisfaction_contract_audit":
        if int(summary.get("satisfactionRowCount") or 0) != 0:
            issues.append(f"satisfactionRowCount is {summary.get('satisfactionRowCount')}")
        if int(summary.get("p0SatisfactionRowCount") or 0) != 0:
            issues.append(f"p0SatisfactionRowCount is {summary.get('p0SatisfactionRowCount')}")
        if int(summary.get("p1SatisfactionRowCount") or 0) != 0:
            issues.append(f"p1SatisfactionRowCount is {summary.get('p1SatisfactionRowCount')}")
        if int(summary.get("requiredReportCount") or 0) < 40:
            issues.append(f"requiredReportCount is {summary.get('requiredReportCount')}; expected at least 40")
        if int(summary.get("passedReportCount") or 0) != int(summary.get("requiredReportCount") or 0):
            issues.append("passedReportCount does not equal requiredReportCount")
    if report_id == "transition_sequence_satisfaction_contract_audit":
        if int(summary.get("transitionSequenceRowCount") or 0) != 0:
            issues.append(f"transitionSequenceRowCount is {summary.get('transitionSequenceRowCount')}")
        if int(summary.get("p0TransitionSequenceRowCount") or 0) != 0:
            issues.append(f"p0TransitionSequenceRowCount is {summary.get('p0TransitionSequenceRowCount')}")
        if int(summary.get("p1TransitionSequenceRowCount") or 0) != 0:
            issues.append(f"p1TransitionSequenceRowCount is {summary.get('p1TransitionSequenceRowCount')}")
        if int(summary.get("metricIssueCount") or 0) != 0:
            issues.append(f"metricIssueCount is {summary.get('metricIssueCount')}")
        if int(summary.get("requiredSequenceReportCount") or 0) < 30:
            issues.append(f"requiredSequenceReportCount is {summary.get('requiredSequenceReportCount')}; expected at least 30")
        if int(summary.get("passedSequenceReportCount") or 0) != int(summary.get("requiredSequenceReportCount") or 0):
            issues.append("passedSequenceReportCount does not equal requiredSequenceReportCount")
    if report_id == "unattended_repair_queue":
        if int(summary.get("repairRowCount") or 0) != 0:
            issues.append(f"repairRowCount is {summary.get('repairRowCount')}")
        if int(summary.get("unactionableRepairRowCount") or 0) != 0:
            issues.append(f"unactionableRepairRowCount is {summary.get('unactionableRepairRowCount')}")
    return issues


def row_from_spec(package_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = package_dir / spec["path"]
    data = load_json(path) or {}
    status = data.get("status") if isinstance(data, dict) else None
    blockers = data.get("blockers") if isinstance(data, dict) and isinstance(data.get("blockers"), list) else []
    warnings = data.get("warnings") if isinstance(data, dict) and isinstance(data.get("warnings"), list) else []
    summary = summary_of(data)
    accepted = set(spec["accepted"])
    metric_blockers = metric_issues(str(spec["reportId"]), summary)
    passed = bool(path.exists() and status in accepted and not blockers and not metric_blockers)
    issue = ""
    if not path.exists():
        issue = f"{spec['reportId']} is missing"
    elif status not in accepted:
        issue = f"{spec['reportId']} status is {status!r}; expected one of {sorted(accepted)}"
    elif blockers:
        issue = f"{spec['reportId']} still has blockers"
    elif metric_blockers:
        issue = "; ".join(metric_blockers)
    return {
        "repairId": f"whole_film_satisfaction_{spec['reportId']}",
        "reportId": spec["reportId"],
        "sourceReport": "whole_film_satisfaction_contract_audit",
        "sourceReportPath": str(path),
        "reportExists": path.exists(),
        "reportStatus": status,
        "acceptedStatuses": sorted(accepted),
        "passed": passed,
        "priority": spec["priority"],
        "phase": spec["phase"],
        "viewerSymptom": spec["viewerSymptom"],
        "issue": issue,
        "metricIssues": metric_blockers,
        "ownerScript": spec["ownerScript"],
        "requiredArtifact": spec["requiredArtifact"],
        "command": spec["command"],
        "acceptanceEvidence": spec["acceptanceEvidence"],
        "forbiddenWorkaround": spec["forbiddenWorkaround"],
        "summary": summary,
        "blockers": [clean(item) for item in blockers[:12]],
        "warnings": [clean(item) for item in warnings[:12]],
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    evidence_rows = [row_from_spec(package_dir, spec) for spec in WHOLE_FILM_SPECS]
    satisfaction_rows = [row for row in evidence_rows if not row["passed"]]
    phase_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    for row in satisfaction_rows:
        phase_counts[str(row.get("phase"))] = phase_counts.get(str(row.get("phase")), 0) + 1
        priority_counts[str(row.get("priority"))] = priority_counts.get(str(row.get("priority")), 0) + 1
    summary_payload = {
        "requiredWholeFilmReportCount": len(evidence_rows),
        "passedWholeFilmReportCount": len([row for row in evidence_rows if row["passed"]]),
        "wholeFilmSatisfactionRowCount": len(satisfaction_rows),
        "p0WholeFilmSatisfactionRowCount": len([row for row in satisfaction_rows if row.get("priority") == "P0"]),
        "p1WholeFilmSatisfactionRowCount": len([row for row in satisfaction_rows if row.get("priority") == "P1"]),
        "missingReportCount": len([row for row in satisfaction_rows if not row.get("reportExists")]),
        "blockedReportCount": len([row for row in satisfaction_rows if row.get("reportExists")]),
        "metricIssueCount": sum(len(row.get("metricIssues") or []) for row in satisfaction_rows),
        "phaseCounts": phase_counts,
        "priorityCounts": priority_counts,
        "ownerScripts": sorted({row["ownerScript"] for row in satisfaction_rows}),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": PASSED if not satisfaction_rows else BLOCKED,
        "contract": "whole_film_satisfaction",
        "packageDir": str(package_dir),
        "summary": summary_payload,
        "evidenceRows": evidence_rows,
        "wholeFilmSatisfactionRows": satisfaction_rows,
        "repairRows": satisfaction_rows,
        "policy": {
            "blocksFinalQaV14SkillMaturityAndHandoffWhenOpen": True,
            "requiresCurrentFinalOutputWatchdown": True,
            "aggregatesOpeningChapterRhythmAudioTransitionReferenceDirectorWatchdown": True,
            "requiresNoOpenUnattendedRepairRows": True,
            "routeEveryOpenRowToOwnerScript": True,
            "noResolveWrites": True,
        },
        "nextActions": [
            "Run owner scripts for P0 whole-film rows in final-output, opening, chapters, rhythm, audio/caption, transitions, reference, director, and watchdown order.",
            "Rerun each source report after repair, then rerun this contract before final QA, V14 baseline, Skill maturity, or handoff.",
            "Do not call the Skill capable of a reference-level unattended first cut while this contract has rows or metric issues.",
        ],
        "safety": safety(),
    }
    if args.max_rows and len(report["wholeFilmSatisfactionRows"]) > args.max_rows:
        report["wholeFilmSatisfactionRows"] = report["wholeFilmSatisfactionRows"][: args.max_rows]
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Whole Film Satisfaction Contract",
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
        "## Whole-Film Satisfaction Rows",
    ]
    if not report.get("wholeFilmSatisfactionRows"):
        lines.append("- None.")
    for row in report.get("wholeFilmSatisfactionRows", [])[:200]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Phase: `{row.get('phase')}`",
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
        if row.get("metricIssues"):
            lines.append(f"- Metric blockers: `{'; '.join(row.get('metricIssues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- This is a final aggregation gate for viewer satisfaction across the whole film.",
            "- It does not replace watching the current final MP4; it requires the editorial watchdown plan to be closed.",
            "- The gate is read-only: no Resolve writes, no render queue, no downloads, no source-drive mutation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whole-film viewer satisfaction before final handoff.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "whole_film_satisfaction_contract_audit.json", report)
    write_markdown(package_dir / "whole_film_satisfaction_contract_audit.md", report)
    payload = (
        report
        if args.json
        else {
            "status": report["status"],
            "summary": report["summary"],
            "blockers": [row["repairId"] for row in report["wholeFilmSatisfactionRows"]],
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
