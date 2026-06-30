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
    "title_typography_repair_plan": {
        "path": "title_typography_repair_plan/title_typography_repair_plan.json",
        "accepted": {"ready_no_title_typography_repairs_needed"},
        "phase": "title_establishing",
        "priority": "P0",
        "ownerScript": "prepare_title_typography_repair_plan.py",
        "requiredArtifact": "title_typography_repair_plan/title_typography_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_title_typography_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun title repair planning, owner-script repairs, cover/title/title-bridge/title-visual-proof audits, final QA, V14, and maturity until no title repair rows remain.",
        "forbiddenWorkaround": "Do not treat a title repair plan with open rows as delivery-ready, and do not hide ghosted/stacked/route/date title defects with shadows, OCR excuses, or extra text layers.",
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
    "transition_reference_candidates": {
        "path": "transition_reference_candidates/transition_reference_candidates.json",
        "accepted": {"ready_with_transition_reference_candidates"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_transition_reference_candidates.py",
        "requiredArtifact": "transition_reference_candidates/transition_reference_candidates.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_reference_candidates.py --package-dir <package> --json",
        "acceptanceEvidence": "Every adjacent boundary has non-copying A/B/C transition candidates, rare motion accents, bridge/breath coverage for important boundaries, and decision/readback fields.",
        "forbiddenWorkaround": "Do not approve generic hard cuts, random rotation, or template effects before candidate rows explain why the boundary should cut, bridge, breathe, dissolve, or use a rare motion accent.",
    },
    "transition_reference_selection": {
        "path": "transition_reference_selection/transition_reference_selection.json",
        "accepted": {"ready_with_transition_reference_selection"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_transition_reference_selection.py",
        "requiredArtifact": "transition_reference_selection/transition_reference_selection.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_reference_selection.py --package-dir <package> --json",
        "acceptanceEvidence": "Every adjacent boundary has one auto-selected default transition, zero blocked selection rows, motion within reference budget, and bridge/breath selections for important boundaries.",
        "forbiddenWorkaround": "Do not leave A/B/C choices for manual review in an unattended first draft, and do not resolve bridge-missing rows by selecting random visible effects.",
    },
    "transition_motion_accent_repair_plan": {
        "path": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "accepted": {"ready_no_motion_accent_repairs_needed"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_transition_motion_accent_repair_plan.py",
        "requiredArtifact": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_motion_accent_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun motion-accent repair planning, owner-script repairs, motion-accent audit, final QA, V14, and maturity until no motion-accent repair rows remain.",
        "forbiddenWorkaround": "Do not treat a repair plan with open rows as delivery-ready, and do not keep random rotation, flash, whip, push, or speed-ramp effects just because they render.",
    },
    "transition_flow_repair_plan": {
        "path": "transition_flow_repair_plan/transition_flow_repair_plan.json",
        "accepted": {"ready_no_transition_flow_repairs_needed"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_transition_flow_repair_plan.py",
        "requiredArtifact": "transition_flow_repair_plan/transition_flow_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_flow_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun transition-flow repair planning, close every owner-script row, then rerun transition cadence/microstructure/scene-arc/visual-match/cutpoint/action/sensory/preview/audition/breathing/smoothness/narrative/orientation/settlement audits plus final QA, V14, and maturity.",
        "forbiddenWorkaround": "Do not treat scattered transition audit failures as optional polish, and do not hide weak adjacent-shot flow with random effects, templates, marker-only visible transitions, or stronger motion.",
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
    "resolve_transition_apply_contract_audit": {
        "path": "resolve_transition_apply_contract_audit.json",
        "accepted": {"passed"},
        "phase": "transition_flow",
        "priority": "P0",
        "ownerScript": "prepare_resolve_transition_apply_plan.py",
        "requiredArtifact": "resolve_transition_apply_plan/resolve_transition_apply_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_resolve_transition_apply_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun audit_resolve_transition_apply_contract.py and prove pendingManualVisibleEffectRowCount is 0, blockedRowCount is 0, and every visible transition is an API-supported cut, a materialized bridge clip, or has completed Resolve readback plus frame-sample evidence.",
        "forbiddenWorkaround": "Do not use --allow-planned-manual-visible-effects for unattended delivery, do not treat marker customData or manual instructions as applied effects, and do not hide missing bridge evidence with rotation, whip, flash, or speed-ramp effects.",
        "allowKeywordRoutes": False,
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
        ("title", "cover_title", "ghost", "stacked", "date", "route label", "hero"),
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

FINAL_QA_META_STAGES = {
    "unattended_repair_queue",
    "unattended_first_draft_contract_audit",
    "skill_maturity_contract_audit",
    "v14_baseline_contract_audit",
}

FINAL_QA_STAGE_ROUTES: tuple[tuple[tuple[str, ...], dict[str, str]], ...] = (
    (
        ("render_delivery_verification",),
        {
            "phase": "resolve_preflight",
            "ownerScript": "prepare_resolve_render.py",
            "requiredArtifact": "render_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_resolve_render.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun render preparation, render verification, and final QA until the final output is 4K/high-FPS/high-bitrate and verified.",
            "forbiddenWorkaround": "Do not mark delivery complete from an unverified export, low-frame-rate file, stale render, or missing final output.",
        },
    ),
    (
        ("bgm_musicality", "bgm_audio", "visual_audio_style", "audio"),
        {
            "phase": "caption_audio",
            "ownerScript": "prepare_bgm_selection_package.py",
            "requiredArtifact": "bgm_selection_package/bgm_selection_package.json",
            "command": "python3 <skill-dir>/scripts/prepare_bgm_selection_package.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun BGM selection, BGM/audio, musicality, audio-scene policy, and final QA until music is local, musical, audible, and BGM-only.",
            "forbiddenWorkaround": "Do not use hum tones, silence, camera audio, generated voiceover, or untraceable music to pass BGM/style gates.",
        },
    ),
    (
        ("audience_caption", "caption", "subtitle"),
        {
            "phase": "caption_audio",
            "ownerScript": "prepare_caption_story_plan.py",
            "requiredArtifact": "caption_story_plan/caption_story_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_caption_story_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun caption planning, audience-caption audit, and final QA until TXT/SRT/burned captions are dense, title-safe, and viewer-facing.",
            "forbiddenWorkaround": "Do not expose workflow, QA, version, Resolve, or repair-status language to viewers.",
        },
    ),
    (
        ("title_typography_repair", "title repair", "ghost title", "stacked title", "title_cards", "title visual"),
        {
            "phase": "title_establishing",
            "ownerScript": "prepare_title_typography_repair_plan.py",
            "requiredArtifact": "title_typography_repair_plan/title_typography_repair_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_title_typography_repair_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun title repair planning, close every repair row, then rerun cover/title/title-bridge/title-visual-proof audits and final QA.",
            "forbiddenWorkaround": "Do not leave stacked text, route/date labels, stale title_cards media, black slates, or subtitle overlays in title windows.",
        },
    ),
    (
        ("title", "cover_title"),
        {
            "phase": "title_establishing",
            "ownerScript": "prepare_title_typography_plan.py",
            "requiredArtifact": "title_typography_plan/title_typography_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun title typography, cover/title, title visual proof, and final QA until hero titles are clean scenic titles with no ghosting or route/date clutter.",
            "forbiddenWorkaround": "Do not hide bad title composition with duplicate layers, shadows, route/date labels, or internal text.",
        },
    ),
    (
        ("location_truth", "raw_intake"),
        {
            "phase": "intake_route",
            "ownerScript": "prepare_footage_recognition_report.py",
            "requiredArtifact": "recognition_reports/latest_footage_recognition_route_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_footage_recognition_report.py --project-dir <project-dir> --json",
            "acceptanceEvidence": "Rerun full-folder recognition, location truth, route review, and final QA until route claims are evidence-backed and caveated correctly.",
            "forbiddenWorkaround": "Do not infer exact locations from filename order, stale route files, sampled folders, or unsupported GPS claims.",
        },
    ),
    (
        ("client_delivery", "orientation"),
        {
            "phase": "source_selection",
            "ownerScript": "prepare_orientation_repair_package.py",
            "requiredArtifact": "orientation_repair_package_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_orientation_repair_package.py --source-package <package> --output-dir <new-package> --json",
            "acceptanceEvidence": "Rerun client delivery/orientation audits and final QA until active blueprint source paths have no raw portrait, square, or unknown clips unless deliberately designed.",
            "forbiddenWorkaround": "Do not crop sampled final frames while leaving portrait sourcePath clips in the active Resolve blueprint.",
        },
    ),
    (
        ("stock_aerial", "visual_establishing", "route_texture"),
        {
            "phase": "title_establishing",
            "ownerScript": "prepare_visual_establishing_plan.py",
            "requiredArtifact": "visual_establishing_plan/visual_establishing_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_visual_establishing_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun establishing, stock/aerial closure, route texture, and final QA until opening/chapter/ending bridges have local footage or closed licensed-stock decisions.",
            "forbiddenWorkaround": "Do not reuse stale previous-trip aerials, black slates, generic landmarks, or stock inserts that do not fit the route.",
        },
    ),
    (
        ("reference", "director", "story_style"),
        {
            "phase": "reference_style",
            "ownerScript": "prepare_reference_style_repair_plan.py",
            "requiredArtifact": "reference_style_repair_plan/reference_style_repair_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun reference-style repair, closure, director/reference audits, and final QA until Parallel World/Malta lessons are applied through concrete artifacts.",
            "forbiddenWorkaround": "Do not write vague style prose, copy reference assets, or claim the cut is reference-like without artifacts and closure evidence.",
        },
    ),
    (
        ("chapter_story_spine", "scene_flow_arc", "narrative_adjacency", "longform_delivery", "story"),
        {
            "phase": "story_spine",
            "ownerScript": "prepare_chapter_arc_plan.py",
            "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun chapter arc, scene flow, narrative adjacency, long-form/story audits, and final QA until chapters read as travel sequences with context, movement, texture, payoff, and aftertaste.",
            "forbiddenWorkaround": "Do not hide landmark stacks or missing story beats behind transition effects, stock inserts, or title cards.",
        },
    ),
    (
        ("pacing_watchability", "timeline_variety", "rhythm_recut"),
        {
            "phase": "creator_cut",
            "ownerScript": "prepare_edit_rhythm_plan.py",
            "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun rhythm, pacing, timeline-variety, rhythm-recut, and final QA until long holds, flat AI pacing, and repetitive shot roles are repaired.",
            "forbiddenWorkaround": "Do not pass watchability by adding effects over weak shot order or leaving long raw holds untouched.",
        },
    ),
    (
        ("final_source_usage", "creator_cut", "shot_flow_continuity"),
        {
            "phase": "creator_cut",
            "ownerScript": "prepare_creator_cut_plan.py",
            "requiredArtifact": "creator_cut_plan/creator_cut_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_creator_cut_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun creator-cut/source-usage/shot-flow audits and final QA until the active blueprint uses selected hero/main/texture footage in a readable order.",
            "forbiddenWorkaround": "Do not let transitions, stock, or titles rescue weak footage; demote, replace, or reorder weak shots first.",
        },
    ),
    (
        ("bridge_sequence", "transition_bridge_visual_evidence"),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_bridge_sequence_blueprint.py",
            "requiredArtifact": "bridge_sequence_blueprint/bridge_sequence_blueprint_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_bridge_sequence_blueprint.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun bridge-sequence blueprint/application, transition-bridge visual evidence, and final QA until important boundaries use real local bridge clips with frame evidence.",
            "forbiddenWorkaround": "Do not replace missing bridge footage with marker metadata, stock-only filler, or a flashy effect.",
        },
    ),
    (
        ("transition_preview",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_preview_packet.py",
            "requiredArtifact": "transition_preview_packet/transition_preview_packet.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_preview_packet.py --package-dir <package> --extract-frames --json",
            "acceptanceEvidence": "Rerun preview packet/quality audits and final QA until important boundaries have nonblank outgoing/middle/landing frame evidence.",
            "forbiddenWorkaround": "Do not approve storyboard or Resolve apply from prose when preview frames are blank, stale, missing, or identical.",
        },
    ),
    (
        ("transition_audition",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_audition_packet.py",
            "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
            "acceptanceEvidence": "Rerun audition packet/quality/visual-proof/role-integrity audits and final QA until important transitions have playable muted MP4 previews with ordered roles.",
            "forbiddenWorkaround": "Do not claim a transition is watchable without playable local audition clips and endpoint/middle-motion frame proof.",
        },
    ),
    (
        ("resolve_transition_materialization",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_execution_blueprint.py",
            "requiredArtifact": "transition_execution_blueprint/transition_execution_blueprint_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun transition execution blueprint, Resolve materialization audit, and final QA until transition recipe payloads survive into Resolve marker/readback metadata.",
            "forbiddenWorkaround": "Do not claim Resolve transition materialization from stale blueprint metadata or marker-free timeline items.",
        },
    ),
    (
        ("resolve_transition_apply",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_resolve_transition_apply_plan.py",
            "requiredArtifact": "resolve_transition_apply_plan/resolve_transition_apply_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_resolve_transition_apply_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun Resolve transition apply planning/audit and final QA until visible transitions have API-supported cuts, materialized bridge clips, or completed Resolve readback plus frame-sample evidence.",
            "forbiddenWorkaround": "Do not treat marker customData, manual instructions, or --allow-planned-manual-visible-effects as unattended applied-transition evidence.",
        },
    ),
    (
        ("transition_polish_application", "final_blueprint_lineage"),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_polish_blueprint.py",
            "requiredArtifact": "transition_polish_blueprint/transition_polish_blueprint_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_polish_blueprint.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun transition polish, final-blueprint lineage, and final QA until the active blueprint inherits the latest BGM-hit/title-safe transition candidate chain.",
            "forbiddenWorkaround": "Do not apply or render from a stale blueprint that lost transition polish, bridge beats, BGM phrase metadata, or candidate lineage.",
        },
    ),
    (
        ("transition_motif",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_motif_plan.py",
            "requiredArtifact": "transition_motif_plan/transition_motif_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_motif_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun transition motif planning/coherence and final QA until the whole film uses one restrained motif language instead of random per-cut effects.",
            "forbiddenWorkaround": "Do not pass motif coherence by repeating one template transition or hiding weak jumps with unrelated effects.",
        },
    ),
    (
        (
            "transition_flow_repair",
            "transition_flow",
            "transition_cadence",
            "transition_microstructure",
            "transition_scene_arc",
            "transition_effect_palette",
            "transition_motif",
            "transition_visual_match",
            "transition_breathing_room",
            "final_cut_smoothness",
            "narrative_adjacency",
            "transition_scene_settlement",
            "pacing_watchability",
        ),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_flow_repair_plan.py",
            "requiredArtifact": "transition_flow_repair_plan/transition_flow_repair_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_flow_repair_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun transition-flow repair planning, close every repair row, then rerun transition flow audits and final QA until the plan returns ready_no_transition_flow_repairs_needed.",
            "forbiddenWorkaround": "Do not patch isolated transition failures with random effects; repair source coverage, bridge/match reason, BGM timing, title safety, preview/audition proof, and stable landing.",
        },
    ),
    (
        ("transition_source_coverage",),
        {
            "phase": "source_selection",
            "ownerScript": "prepare_source_selection_repair_plan.py",
            "requiredArtifact": "source_selection_repair_plan/source_selection_repair_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_source_selection_repair_plan.py --package-dir <package> --project-dir <project-dir> --json",
            "acceptanceEvidence": "Rerun source selection repair, transition source coverage, and final QA until outgoing, bridge, motion, and landing material exists before effects are trusted.",
            "forbiddenWorkaround": "Do not compensate for missing transition source footage with stock inserts, title cards, or flashier effects.",
        },
    ),
    (
        ("rendered_transition_proof",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_audition_packet.py",
            "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
            "acceptanceEvidence": "Rerun transition audition, rendered-transition proof, render verification, and final QA until final MP4 transition windows have no black/white flashes, raw vertical frames, or strobe-like luma jumps.",
            "forbiddenWorkaround": "Do not treat a transition as fixed until both preview/audition evidence and rendered final-frame proof are clean.",
        },
    ),
    (
        ("motion_accent", "random rotation", "random spin", "speed-ramp", "speed_ramp", "whip", "rotation", "visible motion"),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_motion_accent_repair_plan.py",
            "requiredArtifact": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_motion_accent_repair_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun motion-accent repair planning, then close each owner-script row before motion-accent, preview/audition, final QA, V14, and maturity pass.",
            "forbiddenWorkaround": "Do not use random rotation, whip, push, speed-ramp, flash, or stronger motion to hide a weak transition.",
        },
    ),
    (
        ("transition_choreography", "transition_motion", "transition_cutpoint", "transition_action_anchor", "transition_sensory", "transition_effect_recipe", "transition_storyboard", "transition_viewer_orientation", "transition_scene_settlement", "transition_continuity_rehearsal"),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_choreography_plan.py",
            "requiredArtifact": "transition_choreography_plan/transition_choreography_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun transition choreography/cutpoint/action/sensory/motion/storyboard/orientation audits and final QA until every important boundary has outgoing, bridge-or-motion, BGM-hit, title-safe, and stable-landing proof.",
            "forbiddenWorkaround": "Do not use random rotation, whip, push, speed-ramp, or flash effects without source motion, action anchors, BGM timing, and stable landing evidence.",
        },
    ),
    (
        ("transition_reference",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_reference_candidates.py",
            "requiredArtifact": "transition_reference_candidates/transition_reference_candidates.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_reference_candidates.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun transition reference candidates/selection/profile audits and final QA until every adjacent boundary has non-copying reference-calibrated choices and one safe unattended default.",
            "forbiddenWorkaround": "Do not leave A/B/C choices unresolved or select random visible effects to hide missing bridge/breath/match evidence.",
        },
    ),
    (
        ("transition", "shot_transition_boundary"),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_transition_grammar_plan.py",
            "requiredArtifact": "transition_grammar_plan/transition_grammar_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_transition_grammar_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun transition grammar/quality/motivation/pair-continuity/cadence/microstructure/effect-palette/visual-match/source-coverage audits and final QA until adjacent joins have motivated bridge, match, breath, and landing evidence.",
            "forbiddenWorkaround": "Do not hide rough hard joins, missing route bridges, weak adjacent shots, or effect spam behind flashier transitions.",
        },
    ),
    (
        ("effect_motion",),
        {
            "phase": "transition_flow",
            "ownerScript": "prepare_effect_motion_blueprint.py",
            "requiredArtifact": "effect_motion_blueprint/effect_motion_blueprint_report.json",
            "command": "python3 <skill-dir>/scripts/prepare_effect_motion_blueprint.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun effect-motion blueprint/application and final QA until restrained title/route-motion effects survive into the active blueprint.",
            "forbiddenWorkaround": "Do not use template motion, repeated zooms, or decorative effects that are not tied to route, title, or transition intent.",
        },
    ),
    (
        ("feedback_regression",),
        {
            "phase": "reference_style",
            "ownerScript": "prepare_feedback_regression_plan.py",
            "requiredArtifact": "feedback_regression_plan/feedback_regression_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_feedback_regression_plan.py --package-dir <package> --json",
            "acceptanceEvidence": "Rerun feedback regression planning/audit and final QA until known complaints such as ghost title, vertical clip, voice leak, and missing BGM are actively probed.",
            "forbiddenWorkaround": "Do not close feedback by editing prose; every complaint needs a probe, artifact, and post-repair audit.",
        },
    ),
    (
        ("package_integrity",),
        {
            "phase": "resolve_preflight",
            "ownerScript": "build_delivery_package.py",
            "requiredArtifact": "package_integrity_audit.json",
            "command": "python3 <skill-dir>/scripts/build_delivery_package.py --project-dir <project-dir> --output-dir <package> --json",
            "acceptanceEvidence": "Rerun package integrity, strict portable integrity, and final QA until active dependencies are package-local and no stale cross-package paths remain.",
            "forbiddenWorkaround": "Do not hand off a package with external media, stale generated paths, source-drive writes, or copied QA from another package.",
        },
    ),
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
    if spec.get("allowKeywordRoutes") is False:
        return route
    lowered = blocker.lower()
    for keywords, override in KEYWORD_ROUTES:
        if any(keyword in lowered for keyword in keywords):
            route.update(override)
            break
    return route


def final_qa_stage_report_path(package_dir: Path, stage_row: dict[str, Any]) -> Path:
    raw = stage_row.get("report")
    if raw:
        path = Path(str(raw)).expanduser()
        return path if path.is_absolute() else (package_dir / path).resolve()
    stage = str(stage_row.get("stage") or "unknown_final_qa_stage")
    return package_dir / f"{stage}.json"


def final_qa_spec_for_stage(stage: str) -> dict[str, Any]:
    route: dict[str, Any] = {
        "phase": "final_qa",
        "priority": "P0",
        "ownerScript": "run_final_qa_suite.py",
        "requiredArtifact": "final_qa_suite_report.json",
        "command": "python3 <skill-dir>/scripts/run_final_qa_suite.py --package-dir <package> --json",
        "acceptanceEvidence": "Rerun the final QA suite and prove the blocked stage now passes with a package-local report.",
        "forbiddenWorkaround": "Do not ignore final QA blocked stages, reuse stale reports, or claim delivery while final QA is blocked.",
        "allowKeywordRoutes": False,
    }
    lowered = stage.lower()
    for keywords, override in FINAL_QA_STAGE_ROUTES:
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


def final_qa_repair_rows(
    *,
    package_dir: Path,
    skill_dir: Path,
    start_index: int,
    tracked_report_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    final_qa_path = package_dir / "final_qa_suite_report.json"
    final_qa = load_json(final_qa_path)
    if not isinstance(final_qa, dict):
        return [], []
    stages = final_qa.get("stages") if isinstance(final_qa.get("stages"), list) else []
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for stage_row in stages:
        if not isinstance(stage_row, dict) or stage_row.get("passed") is True:
            continue
        stage = str(stage_row.get("stage") or "").strip()
        if not stage:
            continue
        command_return = stage_row.get("commandReturnCode")
        if stage in FINAL_QA_META_STAGES:
            warnings.append(f"Skipped final QA summary stage `{stage}`; repair underlying blocked package stages first.")
            continue
        if stage in tracked_report_ids and command_return in (None, 0):
            continue
        accepted = stage_row.get("acceptedStatuses") if isinstance(stage_row.get("acceptedStatuses"), list) else []
        report_exists = stage_row.get("reportExists")
        blocker = (
            f"Final QA stage `{stage}` failed with status `{stage_row.get('status')}`; "
            f"accepted statuses: {accepted}; report exists: {report_exists}; "
            f"command return code: {command_return}"
        )
        report_path = final_qa_stage_report_path(package_dir, stage_row)
        row = repair_row(
            row_index=start_index + len(rows),
            report_id=f"final_qa:{stage}",
            report_path=report_path,
            spec=final_qa_spec_for_stage(stage),
            issue_type="final_qa_blocked_stage",
            source_status=str(stage_row.get("status") or ""),
            blocker=blocker,
            skill_dir=skill_dir,
        )
        row["sourceFinalQaStage"] = stage
        row["finalQaStageReport"] = str(report_path)
        row["finalQaAcceptedStatuses"] = accepted
        row["finalQaCommandReturnCode"] = command_return
        rows.append(row)
    if final_qa.get("status") == "blocked" and not rows:
        warnings.append("Final QA is blocked, but all blocked stages are tracked elsewhere or are summary stages.")
    return rows, warnings


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

    final_qa_rows, final_qa_warnings = final_qa_repair_rows(
        package_dir=package_dir,
        skill_dir=skill_dir,
        start_index=len(rows) + 1,
        tracked_report_ids=set(REPORT_SPECS),
    )
    rows.extend(final_qa_rows)

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
    resolve_apply_rows = [row for row in rows if row.get("sourceReport") == "resolve_transition_apply_contract_audit"]
    pending_manual_resolve_apply_rows = [
        row
        for row in resolve_apply_rows
        if "pending_manual_visible_effect" in str(row.get("blocker") or "").lower()
        or "manual visible" in str(row.get("blocker") or "").lower()
    ]
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
        "warnings": final_qa_warnings,
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
            "resolveTransitionApplyRepairRowCount": len(resolve_apply_rows),
            "pendingManualTransitionApplyRepairRowCount": len(pending_manual_resolve_apply_rows),
            "finalQaRepairRowCount": len(final_qa_rows),
            "finalQaWarningCount": len(final_qa_warnings),
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
    if report["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
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
