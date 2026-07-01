#!/usr/bin/env python3
"""Audit whether a raw-folder-to-final-film package is ready for one-shot handoff."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = "passed"
BLOCKED = "blocked_one_shot_autonomy"


REPORT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "reportId": "raw_intake_completeness_audit",
        "path": "raw_intake_completeness_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "intake",
        "viewerSymptom": "The package may be a sample, stale project, derived export, or filename-order cut instead of the supplied raw folder.",
        "ownerScript": "audit_raw_intake_completeness.py",
        "requiredArtifact": "raw_intake_completeness_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_raw_intake_completeness.py --project-dir <project> --package-dir <package> --json",
        "acceptanceEvidence": "Every active source video is indexed, recognized, routed exactly once, non-derived, footage-selected, and fresh.",
        "forbiddenWorkaround": "Do not cut from a small sample, old package, exported draft, or filename order when raw intake is incomplete.",
    },
    {
        "reportId": "source_selection_coverage_contract_audit",
        "path": "source_selection_coverage_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "source_selection",
        "viewerSymptom": "The cut may hide weak source choice behind titles, stock aerials, BGM, or effects.",
        "ownerScript": "prepare_source_selection_repair_plan.py",
        "requiredArtifact": "source_selection_repair_plan/source_selection_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_source_selection_repair_plan.py --package-dir <package> --project-dir <project> --json",
        "acceptanceEvidence": "Source-selection coverage proves hero, movement, lived-in texture, payoff, and orientation risks are closed before assembly.",
        "forbiddenWorkaround": "Do not compensate for weak local footage with generic stock, flashy transitions, or title cards.",
    },
    {
        "reportId": "first_assembly_source_order_contract_audit",
        "path": "first_assembly_source_order_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "source_selection",
        "viewerSymptom": "The first assembly may still be raw filename order.",
        "ownerScript": "prepare_footage_select_plan.py",
        "requiredArtifact": "footage_select_plan/footage_select_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_footage_select_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "First assembly uses scored hero/main/texture footage selection rather than raw file order.",
        "forbiddenWorkaround": "Do not keep filename-order assembly and try to rescue it with BGM or transitions.",
    },
    {
        "reportId": "large_source_unattended_readiness_contract_audit",
        "path": "large_source_unattended_readiness_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "source_selection",
        "viewerSymptom": "A 100GB unordered folder may not connect to source selection, first assembly, first draft, and preflight.",
        "ownerScript": "audit_large_source_unattended_readiness_contract.py",
        "requiredArtifact": "large_source_unattended_readiness_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_large_source_unattended_readiness_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Large-source readiness proves media-root intake, whole-folder recognition, source selection, first assembly, unattended first draft, and preflight are connected.",
        "forbiddenWorkaround": "Do not hand a large unordered folder to another AI until this chain is connected end to end.",
    },
    {
        "reportId": "opening_story_plan",
        "path": "opening_story_plan/opening_story_plan.json",
        "accepted": {"ready_with_opening_story_plan"},
        "priority": "P0",
        "phase": "story",
        "viewerSymptom": "The first three minutes may lack a promise, destination proof, clean title, arrival, texture, or handoff.",
        "ownerScript": "prepare_opening_story_plan.py",
        "requiredArtifact": "opening_story_plan/opening_story_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Opening story plan proves the viewer promise, destination proof, clean title, arrival, texture, and chapter handoff.",
        "forbiddenWorkaround": "Do not start with a black slate, generic scenic clip, route/date clutter, or duplicate title layers.",
    },
    {
        "reportId": "chapter_arc_plan",
        "path": "chapter_arc_plan/chapter_arc_plan.json",
        "accepted": {"ready_with_chapter_arc_plan"},
        "priority": "P0",
        "phase": "story",
        "viewerSymptom": "Chapters may be landmark stacks rather than context, movement, texture, payoff, and aftertaste.",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Every chapter has context, movement, lived-in texture, destination payoff, and aftertaste decisions.",
        "forbiddenWorkaround": "Do not call a chapter finished because it has a title card or a famous-place shot.",
    },
    {
        "reportId": "edit_rhythm_plan",
        "path": "edit_rhythm_plan/edit_rhythm_plan.json",
        "accepted": {"ready_with_edit_rhythm_plan"},
        "priority": "P0",
        "phase": "rhythm",
        "viewerSymptom": "The film may still feel AI-made because shot roles, long holds, and cutaway decisions were not planned.",
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Edit rhythm plan gives every primary shot a function and decision fields for trims, splits, cutaways, and chapter variety.",
        "forbiddenWorkaround": "Do not fix flat pacing only by speeding up clips or adding decorative effects.",
    },
    {
        "reportId": "creator_cut_plan",
        "path": "creator_cut_plan/creator_cut_plan.json",
        "accepted": {"ready_with_creator_cut_plan"},
        "priority": "P0",
        "phase": "rhythm",
        "viewerSymptom": "Weak clips may remain active because no creator-style shot selection was applied.",
        "ownerScript": "prepare_creator_cut_plan.py",
        "requiredArtifact": "creator_cut_plan/creator_cut_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_creator_cut_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Creator cut plan classifies shots into hero/main/texture/utility/reject and assigns route, texture, payoff, and aftertaste functions.",
        "forbiddenWorkaround": "Do not let rotation, whip, zoom, or speed ramp effects rescue weak selected footage.",
    },
    {
        "reportId": "title_typography_plan",
        "path": "title_typography_plan/title_typography_plan.json",
        "accepted": {"ready_with_clean_title_typography_plan"},
        "priority": "P0",
        "phase": "title",
        "viewerSymptom": "Opening/chapter/ending titles may still show ghosting, stacked text, route/date clutter, or subtitle collision.",
        "ownerScript": "prepare_title_typography_plan.py",
        "requiredArtifact": "title_typography_plan/title_typography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Title typography plan proves clean title text, font evidence, scenic background evidence, and title-zone subtitle suppression.",
        "forbiddenWorkaround": "Do not hide duplicate text with shadows, outlines, or extra overlays.",
    },
    {
        "reportId": "title_visual_proof_contract_audit",
        "path": "title_visual_proof_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "title",
        "viewerSymptom": "Title cleanliness may be asserted from manifests rather than actual sampled frames.",
        "ownerScript": "audit_title_visual_proof_contract.py",
        "requiredArtifact": "title_visual_proof_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_title_visual_proof_contract.py --package-dir <package> --extract-frames --json",
        "acceptanceEvidence": "Extracted frames prove clean scenic title composition and no forbidden text/subtitle collisions.",
        "forbiddenWorkaround": "Do not trust title manifests, OCR excuses, or old screenshots without current frame proof.",
    },
    {
        "reportId": "caption_story_plan",
        "path": "caption_story_plan/caption_story_plan.json",
        "accepted": {"ready_with_dense_caption_plan"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "Subtitles may be sparse, editor-facing, missing TXT narration export, or unsafe over titles.",
        "ownerScript": "prepare_caption_story_plan.py",
        "requiredArtifact": "caption_story_plan/caption_story_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_caption_story_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Caption plan proves dense viewer-facing TXT/SRT narration with title-zone suppression and no voiceover requirement.",
        "forbiddenWorkaround": "Do not put QA/version/export/tool/status language into captions shown to viewers.",
    },
    {
        "reportId": "audience_caption_contract_audit",
        "path": "audience_caption_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "Captions may speak to the editor instead of the audience.",
        "ownerScript": "audit_audience_caption_contract.py",
        "requiredArtifact": "audience_caption_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_audience_caption_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Audience-caption audit proves captions and TXT are viewer-facing travel-film lines.",
        "forbiddenWorkaround": "Do not leave internal edit reports, Skill notes, or delivery status in the viewer text.",
    },
    {
        "reportId": "bgm_selection_package",
        "path": "bgm_selection_package/bgm_selection_package.json",
        "accepted": {"ready_with_materialized_bgm_selection_package"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "BGM may still be missing, untraceable, not local, not buildable, or not referenced by the active blueprint.",
        "ownerScript": "prepare_bgm_selection_package.py",
        "requiredArtifact": "bgm_selection_package/bgm_selection_package.json",
        "command": "python3 <skill-dir>/scripts/prepare_bgm_selection_package.py --package-dir <package> --json",
        "acceptanceEvidence": "BGM package proves local music/source tracks, license trace, duration coverage, build command, and blueprint reference.",
        "forbiddenWorkaround": "Do not use hum tones, silence, camera audio, generated voiceover, or untraceable music as BGM.",
    },
    {
        "reportId": "bgm_musicality_contract_audit",
        "path": "bgm_musicality_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "The soundtrack may still sound like hum, tone, silence, one-band placeholder audio, or mismatched scenic music.",
        "ownerScript": "audit_bgm_musicality_contract.py",
        "requiredArtifact": "bgm_musicality_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_bgm_musicality_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "BGM musicality proves named music, license trace, phrase coverage, dynamics, and multi-band energy.",
        "forbiddenWorkaround": "Do not pass sine pads, hum tones, silence, or placeholder beds because they are merely audible.",
    },
    {
        "reportId": "audio_scene_policy_plan",
        "path": "audio_scene_policy_plan/audio_scene_policy_plan.json",
        "accepted": {"ready_with_bgm_only_scene_policy"},
        "priority": "P0",
        "phase": "audio_caption",
        "viewerSymptom": "Opening/title/scenic/transition moments may leak source-camera speech or voiceover.",
        "ownerScript": "prepare_audio_scene_policy_plan.py",
        "requiredArtifact": "audio_scene_policy_plan/audio_scene_policy_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_audio_scene_policy_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Audio scene policy proves A3 BGM-led scenic/title/transition windows with A1/A2 voice muted or absent.",
        "forbiddenWorkaround": "Do not leave source/user voice under scenic openings, covers, aerials, or transition bridges.",
    },
    {
        "reportId": "transition_reference_selection",
        "path": "transition_reference_selection/transition_reference_selection.json",
        "accepted": {"ready_with_transition_reference_selection"},
        "priority": "P0",
        "phase": "transitions",
        "viewerSymptom": "Another AI may still need to manually choose transitions, or may choose random flashy motion.",
        "ownerScript": "prepare_transition_reference_selection.py",
        "requiredArtifact": "transition_reference_selection/transition_reference_selection.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_reference_selection.py --package-dir <package> --json",
        "acceptanceEvidence": "Every transition boundary has one safe selected default, blocked rows stay blocked, and motion effects stay restrained.",
        "forbiddenWorkaround": "Do not make unattended drafts depend on manual A/B/C choice after handoff.",
    },
    {
        "reportId": "transition_sequence_satisfaction_contract_audit",
        "path": "transition_sequence_satisfaction_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "transitions",
        "viewerSymptom": "The ordered transition sequence may still feel random, flashy, audio-leaky, template-like, or unlanded.",
        "ownerScript": "audit_transition_sequence_satisfaction_contract.py",
        "requiredArtifact": "transition_sequence_satisfaction_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_transition_sequence_satisfaction_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Transition sequence satisfaction passes with no open transition rows, metric issues, or sequence-level viewer blockers.",
        "forbiddenWorkaround": "Do not claim transitions are ready because isolated transition scripts passed.",
    },
    {
        "reportId": "final_viewer_friction_contract_audit",
        "path": "final_viewer_friction_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "aggregate",
        "viewerSymptom": "Viewer-facing roughness may remain across title, BGM, captions, source, story, transitions, reference fit, or route texture.",
        "ownerScript": "audit_final_viewer_friction_contract.py",
        "requiredArtifact": "final_viewer_friction_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_final_viewer_friction_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Final viewer friction contract has zero P0/P1 viewer-facing repair rows.",
        "forbiddenWorkaround": "Do not hide viewer-facing issues behind technical QA or package integrity.",
    },
    {
        "reportId": "first_draft_satisfaction_contract_audit",
        "path": "first_draft_satisfaction_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "aggregate",
        "viewerSymptom": "The first serious draft may still have open source, opening, BGM, caption, story, rhythm, transition, reference, route, or watchdown rows.",
        "ownerScript": "audit_first_draft_satisfaction_contract.py",
        "requiredArtifact": "first_draft_satisfaction_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_first_draft_satisfaction_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "First-draft satisfaction passes with zero open satisfaction rows and all required source reports passed.",
        "forbiddenWorkaround": "Do not claim V14-level first draft while this aggregate still has open rows.",
    },
    {
        "reportId": "unattended_repair_queue",
        "path": "unattended_repair_queue/unattended_repair_queue.json",
        "accepted": {"ready_no_unattended_repairs_needed"},
        "priority": "P0",
        "phase": "aggregate",
        "viewerSymptom": "The handoff may still require manual diagnosis because actionable repair rows remain.",
        "ownerScript": "prepare_unattended_repair_queue.py",
        "requiredArtifact": "unattended_repair_queue/unattended_repair_queue.json",
        "command": "python3 <skill-dir>/scripts/prepare_unattended_repair_queue.py --package-dir <package> --json",
        "acceptanceEvidence": "Unattended repair queue has zero missing, blocked, P0/P1, or unactionable repair rows.",
        "forbiddenWorkaround": "Do not ask the next user/AI to infer repairs from prose or incomplete QA summaries.",
    },
    {
        "reportId": "whole_film_satisfaction_contract_audit",
        "path": "whole_film_satisfaction_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "aggregate",
        "viewerSymptom": "The package may pass isolated gates but fail as one full viewer experience.",
        "ownerScript": "audit_whole_film_satisfaction_contract.py",
        "requiredArtifact": "whole_film_satisfaction_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_whole_film_satisfaction_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Whole-film satisfaction passes with zero open whole-film rows, zero metric issues, and closed repair queue.",
        "forbiddenWorkaround": "Do not claim reference-level delivery from isolated technical passes.",
    },
    {
        "reportId": "unattended_first_draft_contract_audit",
        "path": "unattended_first_draft_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "aggregate",
        "viewerSymptom": "Raw intake, story, BGM, captions, titles, rhythm, transitions, repair closure, and blueprint preflight may not be connected.",
        "ownerScript": "audit_unattended_first_draft_contract.py",
        "requiredArtifact": "unattended_first_draft_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_unattended_first_draft_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Unattended first-draft contract has zero blocked required gates and confirms the full first-draft chain is connected.",
        "forbiddenWorkaround": "Do not hand off a package where the next AI must manually connect raw intake, style, transitions, BGM, and preflight.",
    },
    {
        "reportId": "resolve_blueprint_preflight",
        "path": "resolve_blueprint_preflight.json",
        "accepted": {"ready", "ready_with_warnings", "passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "preflight",
        "viewerSymptom": "The final blueprint may still have missing media, invalid ranges, gaps, unsafe titles/subtitles, or unresolved transition payloads.",
        "ownerScript": "audit_resolve_blueprint.py",
        "requiredArtifact": "resolve_blueprint_preflight.json",
        "command": "python3 <skill-dir>/scripts/audit_resolve_blueprint.py --blueprint <package>/resolve_timeline_blueprint.json --package-dir <package> --json",
        "acceptanceEvidence": "Resolve blueprint preflight is ready with media, ranges, tracks, title/subtitle/BGM/transition payloads, and source-audio policy safe.",
        "forbiddenWorkaround": "Do not write Resolve, render, or hand off while blueprint preflight is blocked.",
    },
)


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


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
    if report_id == "raw_intake_completeness_audit":
        if as_int(summary.get("activeSourceVideoCount")) <= 0:
            issues.append("activeSourceVideoCount is 0")
        if as_float(summary.get("recognitionCoverageRatio")) < 1.0:
            issues.append(f"recognitionCoverageRatio is {summary.get('recognitionCoverageRatio')}")
        for key in ("routeMissingVideoCount", "routeDuplicateVideoCount", "footageSelectMissingVideoCount", "activeDerivedVideoCount", "staleArtifactCount"):
            if as_int(summary.get(key)) != 0:
                issues.append(f"{key} is {summary.get(key)}")
    if report_id == "large_source_unattended_readiness_contract_audit":
        if as_int(summary.get("blockedCheckCount")) != 0:
            issues.append(f"blockedCheckCount is {summary.get('blockedCheckCount')}")
        if summary.get("unattendedFirstDraftStatus") not in {"passed", "passed_with_warnings"}:
            issues.append(f"unattendedFirstDraftStatus is {summary.get('unattendedFirstDraftStatus')}")
    if report_id == "opening_story_plan":
        if as_int(summary.get("beatRowCount")) < 6:
            issues.append(f"beatRowCount is {summary.get('beatRowCount')}; expected at least 6")
        if as_int(summary.get("missingBeatCount")) != 0:
            issues.append(f"missingBeatCount is {summary.get('missingBeatCount')}")
    if report_id == "edit_rhythm_plan":
        shots = as_int(summary.get("primaryVisualShotCount"))
        if shots <= 0:
            issues.append("primaryVisualShotCount is 0")
        if as_int(summary.get("rowsWithDecisionFields")) < shots:
            issues.append("not every primary visual shot has decision fields")
    if report_id == "creator_cut_plan":
        if as_int(summary.get("creatorDecisionRowCount")) <= 0:
            issues.append("creatorDecisionRowCount is 0")
    if report_id == "title_typography_plan":
        title_rows = as_int(summary.get("titleRowCount"))
        if title_rows <= 0:
            issues.append("titleRowCount is 0")
        if as_int(summary.get("cleanRowCount")) < title_rows:
            issues.append("not every title row is clean")
    if report_id == "caption_story_plan":
        if as_int(summary.get("subtitleCueCount")) <= 0:
            issues.append("subtitleCueCount is 0")
        if as_float(summary.get("cuesPerMinute")) < 3.0:
            issues.append(f"cuesPerMinute is {summary.get('cuesPerMinute')}; expected at least 3.0")
        if not summary.get("textOnlyNarrationExport"):
            issues.append("textOnlyNarrationExport is missing")
    if report_id == "audience_caption_contract_audit":
        if as_int(summary.get("violationCount")) != 0:
            issues.append(f"violationCount is {summary.get('violationCount')}")
    if report_id == "bgm_selection_package":
        if as_int(summary.get("candidateCount")) <= 0:
            issues.append("candidateCount is 0")
        if not summary.get("buildCommandAvailable"):
            issues.append("buildCommandAvailable is false")
        if as_int(summary.get("blueprintBgmAssetCount")) <= 0:
            issues.append("blueprintBgmAssetCount is 0")
    if report_id == "bgm_musicality_contract_audit":
        audio = summary.get("audio") if isinstance(summary.get("audio"), dict) else {}
        if as_int(summary.get("namedTrackCount")) <= 0:
            issues.append("namedTrackCount is 0")
        if as_int(summary.get("phraseRowCount")) < 3:
            issues.append(f"phraseRowCount is {summary.get('phraseRowCount')}; expected at least 3")
        if as_int(audio.get("activeBandCount")) < 4:
            issues.append(f"activeBandCount is {audio.get('activeBandCount')}; expected at least 4")
        if as_float(audio.get("singleBandDominance"), 1.0) > 0.7:
            issues.append(f"singleBandDominance is {audio.get('singleBandDominance')}; expected <= 0.7")
    if report_id == "audio_scene_policy_plan":
        if summary.get("policyMode") != "bgm_only_no_camera_voice":
            issues.append(f"policyMode is {summary.get('policyMode')}")
        if summary.get("voiceoverDisabled") is not True:
            issues.append("voiceoverDisabled is not true")
        if summary.get("sourceAudioDisabled") is not True:
            issues.append("sourceAudioDisabled is not true")
        if as_int(summary.get("sourceAudioRiskCount")) != 0:
            issues.append(f"sourceAudioRiskCount is {summary.get('sourceAudioRiskCount')}")
    if report_id == "transition_reference_selection":
        candidate_count = as_int(summary.get("candidateRowCount"))
        if candidate_count <= 0:
            issues.append("candidateRowCount is 0")
        if as_int(summary.get("selectedRowCount")) < candidate_count:
            issues.append("not every transition candidate row has a selected default")
        if as_int(summary.get("blockedSelectionRowCount")) != 0:
            issues.append(f"blockedSelectionRowCount is {summary.get('blockedSelectionRowCount')}")
    if report_id == "transition_sequence_satisfaction_contract_audit":
        if as_int(summary.get("requiredSequenceReportCount")) < 30:
            issues.append(f"requiredSequenceReportCount is {summary.get('requiredSequenceReportCount')}; expected at least 30")
        for key in ("transitionSequenceRowCount", "p0TransitionSequenceRowCount", "metricIssueCount"):
            if as_int(summary.get(key)) != 0:
                issues.append(f"{key} is {summary.get(key)}")
    if report_id == "final_viewer_friction_contract_audit":
        if as_int(summary.get("evidenceReportCount")) < 20:
            issues.append(f"evidenceReportCount is {summary.get('evidenceReportCount')}; expected at least 20")
        if as_int(summary.get("passedEvidenceReportCount")) != as_int(summary.get("evidenceReportCount")):
            issues.append("passedEvidenceReportCount does not match evidenceReportCount")
        for key in ("viewerFrictionRowCount", "p0ViewerFrictionRowCount", "p1ViewerFrictionRowCount"):
            if as_int(summary.get(key)) != 0:
                issues.append(f"{key} is {summary.get(key)}")
    if report_id == "first_draft_satisfaction_contract_audit":
        if as_int(summary.get("requiredReportCount")) < 40:
            issues.append(f"requiredReportCount is {summary.get('requiredReportCount')}; expected at least 40")
        if as_int(summary.get("passedReportCount")) != as_int(summary.get("requiredReportCount")):
            issues.append("passedReportCount does not match requiredReportCount")
        for key in ("satisfactionRowCount", "p0SatisfactionRowCount", "p1SatisfactionRowCount"):
            if as_int(summary.get(key)) != 0:
                issues.append(f"{key} is {summary.get(key)}")
    if report_id == "unattended_repair_queue":
        for key in ("repairRowCount", "p0RepairRowCount", "p1RepairRowCount", "missingRequiredReportCount", "blockedReportCount", "unactionableRepairRowCount"):
            if as_int(summary.get(key)) != 0:
                issues.append(f"{key} is {summary.get(key)}")
    if report_id == "whole_film_satisfaction_contract_audit":
        if as_int(summary.get("requiredWholeFilmReportCount")) < 20:
            issues.append(f"requiredWholeFilmReportCount is {summary.get('requiredWholeFilmReportCount')}; expected at least 20")
        if as_int(summary.get("passedWholeFilmReportCount")) != as_int(summary.get("requiredWholeFilmReportCount")):
            issues.append("passedWholeFilmReportCount does not match requiredWholeFilmReportCount")
        for key in ("wholeFilmSatisfactionRowCount", "p0WholeFilmSatisfactionRowCount", "p1WholeFilmSatisfactionRowCount", "metricIssueCount"):
            if as_int(summary.get(key)) != 0:
                issues.append(f"{key} is {summary.get(key)}")
    if report_id == "unattended_first_draft_contract_audit":
        if as_int(summary.get("requiredGateCount")) < 14:
            issues.append(f"requiredGateCount is {summary.get('requiredGateCount')}; expected at least 14")
        if as_int(summary.get("blockedGateCount")) != 0:
            issues.append(f"blockedGateCount is {summary.get('blockedGateCount')}")
        if as_int(summary.get("passedGateCount")) < as_int(summary.get("requiredGateCount")):
            issues.append("passedGateCount is below requiredGateCount")
    return issues


def repair_row(
    *,
    row_index: int,
    spec: dict[str, Any],
    report_path: Path,
    status: str | None,
    issue: str,
    blockers: list[str],
    metric_issues: list[str],
) -> dict[str, Any]:
    return {
        "rowIndex": row_index,
        "repairId": f"one_shot_autonomy_{spec['reportId']}",
        "sourceReport": "one_shot_autonomy_contract_audit",
        "reportId": spec["reportId"],
        "reportPath": str(report_path),
        "reportExists": report_path.exists(),
        "reportStatus": status,
        "issue": issue,
        "blockers": blockers,
        "metricIssues": metric_issues,
        "priority": spec["priority"],
        "phase": spec["phase"],
        "viewerSymptom": spec["viewerSymptom"],
        "ownerScript": spec["ownerScript"],
        "requiredArtifact": spec["requiredArtifact"],
        "command": spec["command"],
        "acceptanceEvidence": spec["acceptanceEvidence"],
        "forbiddenWorkaround": spec["forbiddenWorkaround"],
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    evidence_rows: list[dict[str, Any]] = []
    autonomy_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for spec in REPORT_SPECS:
        report_path = package_dir / spec["path"]
        data = load_json(report_path)
        status = data.get("status") if isinstance(data, dict) else None
        summary = summary_of(data)
        accepted = isinstance(data, dict) and status in spec["accepted"]
        issues = metric_issues(str(spec["reportId"]), summary) if accepted else []
        passed = accepted and not issues
        blockers = data.get("blockers") if isinstance(data, dict) and isinstance(data.get("blockers"), list) else []
        if accepted and status and "warning" in str(status):
            warnings.append(f"{spec['reportId']} returned {status}; verify warnings are intentional caveats, not hidden user-facing defects.")
        evidence_rows.append(
            {
                "reportId": spec["reportId"],
                "path": str(report_path),
                "exists": report_path.exists(),
                "status": status,
                "acceptedStatuses": sorted(spec["accepted"]),
                "passed": passed,
                "summary": summary,
                "metricIssues": issues,
                "blockers": blockers,
            }
        )
        if passed:
            continue
        if data is None:
            issue = f"Required report is missing: {spec['path']}"
            row_blockers = [issue]
        elif not accepted:
            issue = f"Report status `{status}` is not in accepted statuses {sorted(spec['accepted'])}"
            row_blockers = [str(item) for item in blockers] or [issue]
        else:
            issue = "Accepted report has one-shot autonomy metric blockers"
            row_blockers = []
        autonomy_rows.append(
            repair_row(
                row_index=len(autonomy_rows) + 1,
                spec=spec,
                report_path=report_path,
                status=status,
                issue=issue,
                blockers=row_blockers,
                metric_issues=issues,
            )
        )

    phase_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    for row in autonomy_rows:
        phase_counts[str(row.get("phase"))] = phase_counts.get(str(row.get("phase")), 0) + 1
        priority_counts[str(row.get("priority"))] = priority_counts.get(str(row.get("priority")), 0) + 1

    summary_payload = {
        "requiredReportCount": len(REPORT_SPECS),
        "passedReportCount": len([row for row in evidence_rows if row["passed"]]),
        "oneShotAutonomyRowCount": len(autonomy_rows),
        "p0OneShotAutonomyRowCount": len([row for row in autonomy_rows if row.get("priority") == "P0"]),
        "p1OneShotAutonomyRowCount": len([row for row in autonomy_rows if row.get("priority") == "P1"]),
        "missingReportCount": len([row for row in autonomy_rows if not row.get("reportExists")]),
        "blockedReportCount": len([row for row in autonomy_rows if row.get("reportExists")]),
        "metricIssueCount": sum(len(row.get("metricIssues") or []) for row in autonomy_rows),
        "warningCount": len(warnings),
        "phaseCounts": phase_counts,
        "priorityCounts": priority_counts,
        "ownerScripts": sorted({row["ownerScript"] for row in autonomy_rows}),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": PASSED if not autonomy_rows else BLOCKED,
        "contract": "one_shot_autonomy",
        "packageDir": str(package_dir),
        "summary": summary_payload,
        "evidenceRows": evidence_rows,
        "oneShotAutonomyRows": autonomy_rows,
        "repairRows": autonomy_rows,
        "warnings": warnings,
        "policy": {
            "blocksFinalQaV14SkillMaturityAndHandoffWhenOpen": True,
            "provesRawFolderToReferenceLevelFirstDraftChain": True,
            "requiresNoOpenUnattendedRepairRows": True,
            "requiresWholeFilmSatisfactionClosure": True,
            "routeEveryOpenRowToOwnerScript": True,
            "noResolveWrites": True,
        },
        "nextActions": [
            "Repair P0 one-shot autonomy rows in intake, source selection, story, rhythm, title, audio/caption, transition, aggregate, and preflight order.",
            "Rerun each owner script after repair, then rerun this contract before final QA, V14 baseline, Skill maturity, release, or handoff.",
            "Do not claim that another AI can produce a V14-level first draft from a raw unordered folder while this contract is blocked.",
        ],
        "safety": safety(),
    }
    if args.max_rows and len(report["oneShotAutonomyRows"]) > args.max_rows:
        report["oneShotAutonomyRows"] = report["oneShotAutonomyRows"][: args.max_rows]
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# One-Shot Autonomy Contract",
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
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## One-Shot Autonomy Rows"])
    if not report.get("oneShotAutonomyRows"):
        lines.append("- None.")
    for row in report.get("oneShotAutonomyRows", [])[:200]:
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
            "- This is a read-only aggregation gate for raw-folder-to-final-film autonomy.",
            "- It proves another agent can start from a large unordered source folder and reach the reference-level first-draft chain without extra user diagnosis.",
            "- It does not replace watching the current final MP4; it requires whole-film satisfaction and the unattended repair queue to be closed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit one-shot autonomy before final handoff.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "one_shot_autonomy_contract_audit.json", report)
    write_markdown(package_dir / "one_shot_autonomy_contract_audit.md", report)
    payload = (
        report
        if args.json
        else {
            "status": report["status"],
            "summary": report["summary"],
            "blockers": [row["repairId"] for row in report["oneShotAutonomyRows"]],
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
