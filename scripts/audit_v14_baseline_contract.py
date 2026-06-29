#!/usr/bin/env python3
"""Audit that a delivery package and Skill satisfy the V14 baseline lessons."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SKILL_PATTERNS = {
    "davinci_default": "DaVinci Resolve API editing",
    "regression_testing": "Treat every live edit as Skill regression testing",
    "clean_title": "duplicate/ghosted text",
    "cover_title_contract": "audit_cover_title_contract.py",
    "feedback_plan": "prepare_feedback_regression_plan.py",
    "bgm_only": "bgm_only_no_camera_voice",
    "caption_overlay": "prepare_subtitle_overlay_asset.py",
    "orientation_repair": "prepare_orientation_repair_package.py",
    "visual_establishing": "prepare_visual_establishing_plan.py",
    "effect_motion_blueprint": "prepare_effect_motion_blueprint.py",
    "effect_motion_application": "audit_effect_motion_application_contract.py",
    "bgm_phrase_blueprint": "prepare_bgm_phrase_blueprint.py",
    "bilibili_malta": "bilibili-travel-style.md",
    "reference_batch_profile": "prepare_reference_batch_profile.py",
    "reference_profile_application": "audit_reference_profile_application_contract.py",
    "footage_select": "prepare_footage_select_plan.py",
    "source_selection_repair": "prepare_source_selection_repair_plan.py",
    "source_selection_coverage": "audit_source_selection_coverage_contract.py",
    "first_assembly_source_order": "audit_first_assembly_source_order_contract.py",
    "large_source_unattended_readiness": "audit_large_source_unattended_readiness_contract.py",
    "raw_intake_completeness": "audit_raw_intake_completeness.py",
    "opening_story": "prepare_opening_story_plan.py",
    "chapter_arc": "prepare_chapter_arc_plan.py",
    "creator_cut": "prepare_creator_cut_plan.py",
    "creator_cut_application": "audit_creator_cut_application_contract.py",
    "final_source_usage": "audit_final_source_usage_contract.py",
    "transition_grammar": "prepare_transition_grammar_plan.py",
    "transition_execution": "prepare_transition_execution_plan.py",
    "transition_execution_blueprint": "prepare_transition_execution_blueprint.py",
    "transition_motif": "prepare_transition_motif_plan.py",
    "bridge_sequence": "prepare_bridge_sequence_plan.py",
    "bridge_sequence_blueprint": "prepare_bridge_sequence_blueprint.py",
    "bridge_sequence_application": "audit_bridge_sequence_application_contract.py",
    "rhythm_recut_blueprint": "prepare_rhythm_recut_blueprint.py",
    "rhythm_recut_application": "audit_rhythm_recut_application_contract.py",
    "transition_polish_blueprint": "prepare_transition_polish_blueprint.py",
    "transition_polish_application": "audit_transition_polish_application_contract.py",
    "resolve_transition_materialization": "audit_resolve_transition_materialization_contract.py",
    "resolve_transition_apply": "audit_resolve_transition_apply_contract.py",
    "final_blueprint_lineage": "audit_final_blueprint_lineage_contract.py",
    "transition_cadence": "audit_transition_cadence_contract.py",
    "transition_microstructure": "audit_transition_microstructure_contract.py",
    "transition_scene_arc": "audit_transition_scene_arc_contract.py",
    "transition_effect_palette": "audit_transition_effect_palette_contract.py",
    "transition_visual_match": "audit_transition_visual_match_contract.py",
    "transition_preview_packet": "prepare_transition_preview_packet.py",
    "transition_preview_quality": "audit_transition_preview_quality_contract.py",
    "transition_quality_contract": "audit_transition_quality_contract.py",
    "shot_transition_boundary_contract": "audit_shot_transition_boundary_contract.py",
    "transition_motivation_contract": "audit_transition_motivation_contract.py",
    "transition_pair_continuity_contract": "audit_transition_pair_continuity_contract.py",
    "transition_execution_readiness_contract": "audit_transition_execution_readiness_contract.py",
    "reference_scene_grammar_contract": "audit_reference_scene_grammar_contract.py",
    "timeline_variety_contract": "audit_timeline_variety_contract.py",
    "unattended_first_draft_contract": "audit_unattended_first_draft_contract.py",
    "reference_style_repair": "prepare_reference_style_repair_plan.py",
    "reference_repair_closure": "audit_reference_repair_closure.py",
    "route_texture": "audit_route_texture_contract.py",
    "final_qa": "run_final_qa_suite.py",
    "maturity": "audit_skill_maturity_contract.py",
    "v14_baseline": "audit_v14_baseline_contract.py",
}

REQUIRED_SCRIPTS = [
    "check_resolve_api.py",
    "build_resolve_timeline.py",
    "audit_resolve_timeline.py",
    "prepare_scenic_title_bridges.py",
    "audit_cover_title_contract.py",
    "prepare_feedback_regression_plan.py",
    "audit_feedback_regressions.py",
    "prepare_bgm_sourcing_brief.py",
    "prepare_bgm_selection_package.py",
    "prepare_bgm_phrase_blueprint.py",
    "build_bgm_bed.py",
    "audit_bgm_audio_contract.py",
    "prepare_caption_story_plan.py",
    "prepare_subtitle_overlay_asset.py",
    "prepare_orientation_repair_package.py",
    "prepare_visual_establishing_plan.py",
    "prepare_transition_bridge_plan.py",
    "prepare_effect_motion_plan.py",
    "prepare_effect_motion_blueprint.py",
    "audit_effect_motion_application_contract.py",
    "prepare_reference_batch_profile.py",
    "audit_reference_profile_application_contract.py",
    "prepare_footage_select_plan.py",
    "prepare_source_selection_repair_plan.py",
    "audit_source_selection_coverage_contract.py",
    "audit_first_assembly_source_order_contract.py",
    "audit_large_source_unattended_readiness_contract.py",
    "audit_raw_intake_completeness.py",
    "prepare_opening_story_plan.py",
    "prepare_chapter_arc_plan.py",
    "prepare_edit_rhythm_plan.py",
    "prepare_creator_cut_plan.py",
    "audit_creator_cut_application_contract.py",
    "audit_final_source_usage_contract.py",
    "prepare_transition_grammar_plan.py",
    "prepare_transition_execution_plan.py",
    "prepare_transition_execution_blueprint.py",
    "prepare_transition_motif_plan.py",
    "prepare_bridge_sequence_plan.py",
    "prepare_bridge_sequence_blueprint.py",
    "audit_bridge_sequence_application_contract.py",
    "prepare_rhythm_recut_blueprint.py",
    "audit_rhythm_recut_application_contract.py",
    "prepare_transition_polish_blueprint.py",
    "audit_transition_polish_application_contract.py",
    "audit_resolve_transition_materialization_contract.py",
    "prepare_resolve_transition_apply_plan.py",
    "audit_resolve_transition_apply_contract.py",
    "audit_final_blueprint_lineage_contract.py",
    "audit_transition_cadence_contract.py",
    "audit_transition_microstructure_contract.py",
    "audit_transition_scene_arc_contract.py",
    "audit_transition_effect_palette_contract.py",
    "audit_transition_visual_match_contract.py",
    "prepare_transition_preview_packet.py",
    "audit_transition_preview_quality_contract.py",
    "audit_transition_quality_contract.py",
    "audit_shot_transition_boundary_contract.py",
    "audit_transition_motivation_contract.py",
    "audit_transition_pair_continuity_contract.py",
    "audit_transition_execution_readiness_contract.py",
    "audit_reference_scene_grammar_contract.py",
    "audit_timeline_variety_contract.py",
    "audit_unattended_first_draft_contract.py",
    "prepare_reference_style_repair_plan.py",
    "audit_reference_repair_closure.py",
    "audit_reference_style_alignment.py",
    "audit_route_texture_contract.py",
    "audit_director_polish_contract.py",
    "run_final_qa_suite.py",
    "audit_skill_maturity_contract.py",
    "audit_v14_baseline_contract.py",
]


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def skill_dir_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def get_summary(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def track_count(track_summary: dict[str, Any], kind: str, index: int) -> int:
    rows = track_summary.get(kind) if isinstance(track_summary.get(kind), list) else []
    for row in rows:
        if isinstance(row, dict) and int(row.get("index") or -1) == index:
            return int(row.get("itemCount") or 0)
    return 0


def checks_with_text(data: Any, needle: str) -> list[dict[str, Any]]:
    rows = data.get("checks") if isinstance(data, dict) and isinstance(data.get("checks"), list) else []
    out: list[dict[str, Any]] = []
    needle_lower = needle.lower()
    for row in rows:
        text = json.dumps(row, ensure_ascii=False).lower()
        if needle_lower in text:
            out.append(row)
    return out


def passed_status(data: Any, accepted: set[str] | None = None) -> bool:
    if not isinstance(data, dict):
        return False
    accepted = accepted or {"passed"}
    return data.get("status") in accepted and not data.get("blockers")


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else "blocked",
            "evidence": evidence,
        }
    )


def build_report(package_dir: Path, skill_dir: Path) -> dict[str, Any]:
    skill_md = skill_dir / "SKILL.md"
    skill_text = skill_md.read_text(encoding="utf-8", errors="ignore") if skill_md.exists() else ""
    scripts_dir = skill_dir / "scripts"

    final_report = load_json(package_dir / "FINAL_DELIVERY_REPORT.json") or {}
    final_qa = load_json(package_dir / "final_qa_suite_report.json") or {}
    maturity = load_json(package_dir / "skill_maturity_contract_audit.json") or {}
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    client = load_json(package_dir / "client_delivery_rules_audit.json") or {}
    title = load_json(package_dir / "title_bridge_contract_audit.json") or {}
    cover_title = load_json(package_dir / "cover_title_contract_audit.json") or {}
    title_plan = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    feedback_plan = load_json(package_dir / "feedback_regression_plan" / "feedback_regression_plan.json") or {}
    feedback = load_json(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json") or {}
    audio_policy = load_json(package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json") or {}
    bgm = load_json(package_dir / "bgm_audio_contract_audit.json") or {}
    caption = load_json(package_dir / "caption_story_plan" / "caption_story_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    orientation_repair = load_json(package_dir / "orientation_repair_package_report.json") or {}
    visual_establishing = load_json(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json") or {}
    transition = load_json(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json") or {}
    effect = load_json(package_dir / "effect_motion_plan" / "effect_motion_plan.json") or {}
    effect_motion_blueprint = load_json(package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json") or {}
    effect_motion_application = load_json(package_dir / "effect_motion_application_contract_audit.json") or {}
    bgm_phrase_blueprint = load_json(package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json") or {}
    reference_batch = load_json(package_dir / "reference" / "reference_batch_profile.json") or {}
    reference_profile_application = load_json(package_dir / "reference_profile_application_contract_audit.json") or {}
    footage_select = load_json(package_dir / "footage_select_plan" / "footage_select_plan.json") or {}
    raw_intake = load_json(package_dir / "raw_intake_completeness_audit.json") or {}
    source_selection_repair = load_json(package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json") or {}
    source_selection_coverage = load_json(package_dir / "source_selection_coverage_contract_audit.json") or {}
    first_assembly_source_order = load_json(package_dir / "first_assembly_source_order_contract_audit.json") or {}
    large_source_unattended = load_json(package_dir / "large_source_unattended_readiness_contract_audit.json") or {}
    opening_story = load_json(package_dir / "opening_story_plan" / "opening_story_plan.json") or {}
    chapter_arc = load_json(package_dir / "chapter_arc_plan" / "chapter_arc_plan.json") or {}
    rhythm = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
    creator_cut = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    creator_cut_application = load_json(package_dir / "creator_cut_application_contract_audit.json") or {}
    final_source_usage = load_json(package_dir / "final_source_usage_contract_audit.json") or {}
    transition_grammar = load_json(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json") or {}
    transition_execution = load_json(package_dir / "transition_execution_plan" / "transition_execution_plan.json") or {}
    transition_execution_blueprint = load_json(package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json") or {}
    transition_motif = load_json(package_dir / "transition_motif_plan" / "transition_motif_plan.json") or {}
    bridge_sequence = load_json(package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json") or {}
    bridge_sequence_blueprint = load_json(package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json") or {}
    bridge_sequence_application = load_json(package_dir / "bridge_sequence_application_contract_audit.json") or {}
    rhythm_recut_blueprint = load_json(package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json") or {}
    rhythm_recut_application = load_json(package_dir / "rhythm_recut_application_contract_audit.json") or {}
    transition_polish_blueprint = load_json(package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json") or {}
    transition_polish_application = load_json(package_dir / "transition_polish_application_contract_audit.json") or {}
    resolve_transition_materialization = load_json(package_dir / "resolve_transition_materialization_contract_audit.json") or {}
    resolve_transition_apply = load_json(package_dir / "resolve_transition_apply_contract_audit.json") or {}
    final_blueprint_lineage = load_json(package_dir / "final_blueprint_lineage_contract_audit.json") or {}
    transition_cadence = load_json(package_dir / "transition_cadence_contract_audit.json") or {}
    transition_microstructure = load_json(package_dir / "transition_microstructure_contract_audit.json") or {}
    transition_scene_arc = load_json(package_dir / "transition_scene_arc_contract_audit.json") or {}
    transition_effect_palette = load_json(package_dir / "transition_effect_palette_contract_audit.json") or {}
    transition_visual_match = load_json(package_dir / "transition_visual_match_contract_audit.json") or {}
    transition_preview_packet = load_json(package_dir / "transition_preview_packet" / "transition_preview_packet.json") or {}
    transition_preview_quality = load_json(package_dir / "transition_preview_quality_contract_audit.json") or {}
    transition_storyboard = load_json(package_dir / "transition_storyboard_contract_audit.json") or {}
    transition_quality = load_json(package_dir / "transition_quality_contract_audit.json") or {}
    shot_transition_boundary = load_json(package_dir / "shot_transition_boundary_contract_audit.json") or {}
    transition_motivation = load_json(package_dir / "transition_motivation_contract_audit.json") or {}
    transition_pair_continuity = load_json(package_dir / "transition_pair_continuity_contract_audit.json") or {}
    transition_execution_readiness = load_json(package_dir / "transition_execution_readiness_contract_audit.json") or {}
    reference_scene_grammar = load_json(package_dir / "reference_scene_grammar_contract_audit.json") or {}
    timeline_variety = load_json(package_dir / "timeline_variety_contract_audit.json") or {}
    unattended_first_draft = load_json(package_dir / "unattended_first_draft_contract_audit.json") or {}
    reference_repair = load_json(package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json") or {}
    reference_repair_closure = load_json(package_dir / "reference_repair_closure_audit.json") or {}
    reference = load_json(package_dir / "reference_style_alignment_audit.json") or {}
    route_texture = load_json(package_dir / "route_texture_contract_audit.json") or {}
    director_intent = load_json(package_dir / "director_intent_contract_audit.json") or {}
    stock = load_json(package_dir / "stock_aerial_closure_audit.json") or {}
    director_polish = load_json(package_dir / "director_polish_contract_audit.json") or {}
    integrity = load_json(package_dir / "package_integrity_audit_strict_portable.json") or load_json(package_dir / "package_integrity_audit.json") or {}

    checks: list[dict[str, Any]] = []

    missing_patterns = [name for name, pattern in SKILL_PATTERNS.items() if pattern not in skill_text]
    missing_scripts = [name for name in REQUIRED_SCRIPTS if not (scripts_dir / name).exists()]
    add_check(
        checks,
        "Skill root contains the V14 baseline workflow, scripts, and gates",
        not missing_patterns and not missing_scripts,
        {
            "skillDir": str(skill_dir),
            "missingSkillPatterns": missing_patterns,
            "missingScripts": missing_scripts,
            "scriptCount": len(REQUIRED_SCRIPTS),
        },
    )

    raw_intake_summary = get_summary(raw_intake)
    add_check(
        checks,
        "Raw intake completeness gate proves the full source pool survived into recognition, route, and footage select",
        raw_intake.get("status") == "passed"
        and int(raw_intake_summary.get("indexedVideoCount") or 0) > 0
        and int(raw_intake_summary.get("activeSourceVideoCount") or 0) > 0
        and float(raw_intake_summary.get("recognitionCoverageRatio") or 0) >= 1.0
        and int(raw_intake_summary.get("routeMissingVideoCount") or 0) == 0
        and int(raw_intake_summary.get("routeDuplicateVideoCount") or 0) == 0
        and int(raw_intake_summary.get("footageSelectMissingVideoCount") or 0) == 0
        and int(raw_intake_summary.get("activeDerivedVideoCount") or 0) == 0
        and int(raw_intake_summary.get("staleArtifactCount") or 0) == 0,
        {"status": raw_intake.get("status"), "summary": raw_intake_summary, "blockers": raw_intake.get("blockers")},
    )

    source_selection_summary = get_summary(source_selection_repair)
    source_selection_audit_summary = get_summary(source_selection_coverage)
    source_chapters = int(source_selection_summary.get("chapterRowCount") or 0)
    add_check(
        checks,
        "Source selection repair gate proves V14 raw coverage is ready before effects, stock, or transition polish",
        source_selection_repair.get("status") == "ready_no_source_selection_repairs_needed"
        and source_selection_coverage.get("status") == "passed"
        and source_chapters >= 1
        and int(source_selection_summary.get("readyChapterCount") or 0) == source_chapters
        and int(source_selection_summary.get("blockingRepairRowCount") or 0) == 0
        and int(source_selection_summary.get("heroCandidateCount") or 0) >= 1
        and int(source_selection_summary.get("movementBridgeCandidateCount") or 0) >= max(1, source_chapters - 1)
        and int(source_selection_summary.get("livedInTextureCandidateCount") or 0) >= 1
        and int(source_selection_summary.get("destinationPayoffCandidateCount") or 0) >= 1
        and int(source_selection_audit_summary.get("blockedCheckCount") or 0) == 0,
        {
            "sourceSelectionRepairStatus": source_selection_repair.get("status"),
            "sourceSelectionSummary": source_selection_summary,
            "sourceSelectionCoverageStatus": source_selection_coverage.get("status"),
            "sourceSelectionCoverageSummary": source_selection_audit_summary,
            "blockers": source_selection_coverage.get("blockers"),
        },
    )

    first_assembly_summary = get_summary(first_assembly_source_order)
    first_assembly_chapters = int(first_assembly_summary.get("deliveryChapterCount") or 0)
    first_assembly_candidates = int(first_assembly_summary.get("candidateVideoCount") or 0)
    add_check(
        checks,
        "First assembly source-order gate proves V14 starts from full-source selection, not filename order or blueprint fallback samples",
        first_assembly_source_order.get("status") == "passed"
        and int(first_assembly_summary.get("blockedCheckCount") or 0) == 0
        and int(first_assembly_summary.get("activeSourceVideoCount") or 0) > 0
        and int(first_assembly_summary.get("footageSelectSourceVideoCount") or 0) >= int(first_assembly_summary.get("activeSourceVideoCount") or 0)
        and first_assembly_chapters >= 1
        and int(first_assembly_summary.get("sortedChapterCount") or 0) >= first_assembly_chapters
        and first_assembly_candidates >= 3
        and int(first_assembly_summary.get("candidateRowsUsed") or 0) >= min(first_assembly_candidates, max(3, first_assembly_chapters))
        and int(first_assembly_summary.get("riskyTopSelectionRowCount") or 0) == 0
        and int(first_assembly_summary.get("missingTopSelectionDataCount") or 0) == 0
        and (not first_assembly_summary.get("largeSource") or first_assembly_summary.get("footageSelectInputSource") == "media_index"),
        {
            "status": first_assembly_source_order.get("status"),
            "summary": first_assembly_summary,
            "blockers": first_assembly_source_order.get("blockers"),
        },
    )

    large_source_summary = get_summary(large_source_unattended)
    add_check(
        checks,
        "Large-source unattended readiness gate proves 100GB unordered folders can reach a safe first draft without filename-order fallback",
        large_source_unattended.get("status") in {"passed", "passed_with_warnings"}
        and int(large_source_summary.get("blockedCheckCount") or 0) == 0
        and int(large_source_summary.get("activeSourceVideoCount") or 0) > 0
        and int(large_source_summary.get("expectedActiveSourceCount") or 0) > 0
        and float(large_source_summary.get("recognitionCoverageRatio") or 0) >= 1.0
        and (not large_source_summary.get("largeSource") or large_source_summary.get("footageSelectInputSource") == "media_index")
        and int(large_source_summary.get("candidateVideoCount") or 0) >= 3
        and large_source_summary.get("firstAssemblyStatus") == "passed"
        and large_source_summary.get("unattendedFirstDraftStatus") in {"passed", "passed_with_warnings"},
        {
            "status": large_source_unattended.get("status"),
            "summary": large_source_summary,
            "blockers": large_source_unattended.get("blockers"),
            "warnings": large_source_unattended.get("warnings"),
        },
    )

    final_video = final_report.get("video") if isinstance(final_report.get("video"), dict) else {}
    render_video = render.get("video") if isinstance(render.get("video"), dict) else {}
    track_summary = final_report.get("resolveTrackSummary") if isinstance(final_report.get("resolveTrackSummary"), dict) else {}
    add_check(
        checks,
        "DaVinci Resolve is the finishing path with readback and final report",
        passed_status(final_report)
        and bool(resolve_audit.get("projectName"))
        and bool(resolve_audit.get("timelineName"))
        and bool(track_summary),
        {
            "finalReportStatus": final_report.get("status"),
            "resolveProject": resolve_audit.get("projectName"),
            "resolveTimeline": resolve_audit.get("timelineName"),
            "resolveTrackSummary": track_summary,
        },
    )

    title_summary = get_summary(title_plan)
    title_clean_rows = checks_with_text(title, "Opening has exactly one clean city title segment")
    add_check(
        checks,
        "Opening and chapter titles are clean scenic bridges with no ghost text",
        passed_status(title)
        and title_summary.get("status", title_plan.get("status")) != "blocked"
        and title_plan.get("status") == "ready_with_clean_title_typography_plan"
        and int(title_summary.get("stackExtraTextLayerCount") or 0) == 0
        and int(title_summary.get("stackSubtitleOverlayCount") or 0) == 0
        and bool(title_clean_rows and title_clean_rows[0].get("status") == "passed"),
        {
            "titleContractStatus": title.get("status"),
            "titlePlanStatus": title_plan.get("status"),
            "titlePlanSummary": title_summary,
            "titleClipCount": title.get("titleClipCount"),
            "segmentCount": title.get("segmentCount"),
        },
    )
    cover_title_summary = get_summary(cover_title)
    add_check(
        checks,
        "Cover hero title matches the Parallel World-style formula without route/date clutter",
        cover_title.get("status") == "passed"
        and bool(str(cover_title_summary.get("mainTitle") or "").strip())
        and 1 <= int(cover_title_summary.get("mainTitleUnitCount") or 0) <= 8
        and cover_title_summary.get("secondaryTitlePresent") is True
        and cover_title_summary.get("backgroundVideoReady") is True
        and cover_title_summary.get("backgroundRecognitionHint") is True
        and cover_title_summary.get("clean16x9Deliverable") is True
        and int(cover_title_summary.get("forbiddenHitCount") or 0) == 0
        and not cover_title.get("blockers"),
        {
            "coverTitleStatus": cover_title.get("status"),
            "coverTitleSummary": cover_title_summary,
        },
    )

    opening_summary = get_summary(opening_story)
    add_check(
        checks,
        "First three minutes have V14-level opening story structure before polish",
        opening_story.get("status") == "ready_with_opening_story_plan"
        and int(opening_summary.get("beatRowCount") or 0) >= 6
        and int(opening_summary.get("rowsWithEvidence") or 0) == int(opening_summary.get("beatRowCount") or -1)
        and int(opening_summary.get("missingBeatCount") or 0) == 0
        and int(opening_summary.get("destinationProofClipCount") or 0) >= 1
        and int(opening_summary.get("routeArrivalClipCount") or 0) >= 1
        and int(opening_summary.get("livedInTextureClipCount") or 0) >= 1
        and int(opening_summary.get("titleClipCount") or 0) >= 1
        and int(opening_summary.get("weakTitleHitCount") or 0) == 0
        and int(opening_summary.get("firstHandoffClipCount") or 0) >= 1,
        {
            "openingStoryStatus": opening_story.get("status"),
            "openingStorySummary": opening_summary,
        },
    )

    chapter_arc_summary = get_summary(chapter_arc)
    chapter_count = int(chapter_arc_summary.get("chapterRowCount") or 0)
    add_check(
        checks,
        "Every route chapter has V14-level arc planning or assigned repair owners before polish",
        chapter_arc.get("status") == "ready_with_chapter_arc_plan"
        and chapter_count >= 1
        and int(chapter_arc_summary.get("rowsWithDecisionFields") or 0) == chapter_count
        and int(chapter_arc_summary.get("chaptersMissingRequiredBeatCount") or 0) == int(chapter_arc_summary.get("p0RepairRowCount") or 0)
        and int(chapter_arc_summary.get("blueprintVideoClipCount") or 0) >= 1,
        {
            "chapterArcStatus": chapter_arc.get("status"),
            "chapterArcSummary": chapter_arc_summary,
        },
    )

    feedback_summary = get_summary(feedback_plan)
    timestamps = str(feedback_summary.get("feedbackTimestampsCsv") or "")
    required_timestamps = [
        "opening_title=0",
        "reported_vertical_clip=7:04",
        "reported_voice_at_7_04=7:04",
        "opening_bgm_no_voice=0",
    ]
    add_check(
        checks,
        "Known user complaints are reusable feedback regression probes",
        feedback_plan.get("status") == "ready_with_feedback_regression_plan"
        and all(item in timestamps for item in required_timestamps)
        and passed_status(feedback),
        {
            "feedbackPlanStatus": feedback_plan.get("status"),
            "feedbackAuditStatus": feedback.get("status"),
            "feedbackTimestampsCsv": timestamps,
            "requiredTimestamps": required_timestamps,
        },
    )

    audio_summary = get_summary(audio_policy)
    add_check(
        checks,
        "BGM-only delivery disables voiceover/source-camera audio and keeps TXT/SRT narration",
        audio_policy.get("status") == "ready_with_bgm_only_scene_policy"
        and audio_summary.get("policyMode") == "bgm_only_no_camera_voice"
        and audio_summary.get("voiceoverDisabled") is True
        and audio_summary.get("sourceAudioDisabled") is True
        and passed_status(bgm)
        and track_count(track_summary, "audio", 1) == 0
        and track_count(track_summary, "audio", 2) == 0
        and track_count(track_summary, "audio", 3) >= 1
        and bool((package_dir / "caption_story_plan" / "text_only_narration_export.txt").exists()),
        {
            "audioScenePolicyStatus": audio_policy.get("status"),
            "audioSceneSummary": audio_summary,
            "bgmAudioStatus": bgm.get("status"),
            "a1Items": track_count(track_summary, "audio", 1),
            "a2Items": track_count(track_summary, "audio", 2),
            "a3Items": track_count(track_summary, "audio", 3),
            "textOnlyNarrationExportExists": (package_dir / "caption_story_plan" / "text_only_narration_export.txt").exists(),
        },
    )

    caption_summary = get_summary(caption)
    subtitle_policy = blueprint.get("subtitleDeliveryPolicy") if isinstance(blueprint.get("subtitleDeliveryPolicy"), dict) else {}
    add_check(
        checks,
        "Dense subtitles are rendered through a V3/title-safe overlay policy",
        caption.get("status") == "ready_with_dense_caption_plan"
        and float(caption_summary.get("cuesPerMinute") or 0) >= 4.0
        and int(caption_summary.get("subtitleCueCount") or 0) >= 80
        and int(caption_summary.get("gapCountOver75Seconds") or 0) == 0
        and subtitle_policy.get("mode") == "resolve_overlay_video"
        and int(subtitle_policy.get("overlayTrack") or 0) == 3
        and int(subtitle_policy.get("overlayClipCount") or 0) >= 80
        and (subtitle_policy.get("titleZoneSubtitlePolicy") or {}).get("mode") == "avoid_title_zones",
        {
            "captionPlanStatus": caption.get("status"),
            "captionSummary": caption_summary,
            "subtitleDeliveryPolicy": subtitle_policy,
            "v3Items": track_count(track_summary, "video", 3),
        },
    )

    orientation_summary = get_summary(client)
    orientation_rows = checks_with_text(client, "raw portrait/square/unknown")
    orientation_row = next(
        (
            row
            for row in orientation_rows
            if isinstance(row.get("evidence"), dict)
            and int(row["evidence"].get("checkedVideoClipCount") or 0) > 0
        ),
        orientation_rows[0] if orientation_rows else {},
    )
    orientation_evidence = orientation_row.get("evidence") if isinstance(orientation_row, dict) else {}
    add_check(
        checks,
        "Source orientation is scanned and V14-style repair replaces raw portrait clips",
        orientation_repair.get("status") == "prepared"
        and int(orientation_repair.get("orientationFixCount") or 0) >= 1
        and passed_status(client)
        and bool(orientation_row and orientation_row.get("status") == "passed")
        and int(orientation_evidence.get("checkedVideoClipCount") or 0) > 0
        and int(orientation_evidence.get("blockedNonLandscapeCount") or 0) == 0,
        {
            "orientationRepairStatus": orientation_repair.get("status"),
            "orientationFixCount": orientation_repair.get("orientationFixCount"),
            "clientStatus": client.get("status"),
            "clientSummary": orientation_summary,
            "orientationEvidence": orientation_evidence,
        },
    )

    visual_summary = get_summary(visual_establishing)
    stock_summary = get_summary(stock)
    transition_summary = get_summary(transition)
    add_check(
        checks,
        "Opening, chapters, ending, aerials, and day transitions use scenic/route-aware bridge material",
        visual_establishing.get("status") == "ready_with_establishing_evidence"
        and int(visual_summary.get("missingEstablishingCount") or 0) == 0
        and int(visual_summary.get("verifiedAerialCount") or 0) >= 1
        and passed_status(stock)
        and int(stock_summary.get("unresolvedPlaceholderCount") or 0) == 0
        and transition.get("status") in {"ready_with_bridge_evidence", "ready_no_interchapter_boundaries"}
        and int(transition_summary.get("boundaryRowCount") or 0) >= 1,
        {
            "visualEstablishingStatus": visual_establishing.get("status"),
            "visualEstablishingSummary": visual_summary,
            "stockAerialStatus": stock.get("status"),
            "stockAerialSummary": stock_summary,
            "transitionBridgeStatus": transition.get("status"),
            "transitionBridgeSummary": transition_summary,
        },
    )

    effect_motion_blueprint_summary = get_summary(effect_motion_blueprint)
    effect_motion_blueprint_rows = int(effect_motion_blueprint_summary.get("effectRowCount") or 0)
    effect_motion_blueprint_outputs = effect_motion_blueprint.get("outputs") if isinstance(effect_motion_blueprint.get("outputs"), dict) else {}
    effect_candidate_path = Path(str(effect_motion_blueprint_outputs.get("candidateBlueprint") or package_dir / "effect_motion_blueprint" / "resolve_timeline_blueprint_effect_motion.json"))
    effect_candidate = load_json(effect_candidate_path) or {}
    effect_candidates = effect_candidate.get("effectMotionCandidates") if isinstance(effect_candidate.get("effectMotionCandidates"), list) else []
    effect_markers = [
        marker for marker in effect_candidate.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "effect_motion_candidate_marker"
    ] if isinstance(effect_candidate.get("timelineMarkers"), list) else []
    effect_clip_annotations = sum(len(clip.get("effectMotionCandidates") or []) for clip in effect_candidate.get("clips", []) if isinstance(clip, dict) and isinstance(clip.get("effectMotionCandidates"), list))
    add_check(
        checks,
        "Effect motion blueprint materializes restrained title and transition effects into candidate metadata",
        effect_motion_blueprint.get("status") == "ready_with_effect_motion_blueprint"
        and effect_motion_blueprint_rows >= 3
        and int(effect_motion_blueprint_summary.get("materializedEffectCount") or 0) == effect_motion_blueprint_rows
        and int(effect_motion_blueprint_summary.get("candidateEffectMotionCount") or 0) == len(effect_candidates)
        and int(effect_motion_blueprint_summary.get("candidateEffectMotionCount") or 0) == effect_motion_blueprint_rows
        and int(effect_motion_blueprint_summary.get("rowsWithDecisionFields") or 0) == effect_motion_blueprint_rows
        and int(effect_motion_blueprint_summary.get("rowsWithClipMatch") or 0) == effect_motion_blueprint_rows
        and int(effect_motion_blueprint_summary.get("blockedRowCount") or 0) == 0
        and int(effect_motion_blueprint_summary.get("titleMotionRowCount") or 0) >= 3
        and int(effect_motion_blueprint_summary.get("transitionMotionRowCount") or 0) >= 1
        and int(effect_motion_blueprint_summary.get("motionEffectRowsWithEvidence") or 0) == int(effect_motion_blueprint_summary.get("motionEffectRowCount") or 0)
        and int(effect_motion_blueprint_summary.get("forbiddenEffectHitCount") or 0) == 0
        and effect_candidate_path.exists()
        and isinstance(effect_candidate.get("effectMotionBlueprintPlan"), dict)
        and len(effect_markers) == effect_motion_blueprint_rows
        and effect_clip_annotations >= effect_motion_blueprint_rows,
        {
            "effectMotionBlueprintStatus": effect_motion_blueprint.get("status"),
            "effectMotionBlueprintSummary": effect_motion_blueprint_summary,
            "candidateBlueprint": str(effect_candidate_path),
            "candidateEffectMotionCount": len(effect_candidates),
            "markerCount": len(effect_markers),
            "clipAnnotationCount": effect_clip_annotations,
        },
    )

    transition_motif_summary = get_summary(transition_motif)
    transition_motif_rows = int(transition_motif_summary.get("transitionRowCount") or 0)
    add_check(
        checks,
        "Transition motif plan prevents repeated/template transition chains before Resolve apply",
        transition_motif.get("status") == "ready_with_transition_motif_plan"
        and transition_motif_rows >= 3
        and int(transition_motif_summary.get("rowsWithDecisionFields") or 0) == transition_motif_rows
        and int(transition_motif_summary.get("rowsWithBgmPhraseCue") or 0) == transition_motif_rows
        and int(transition_motif_summary.get("titleBoundaryRowsSafe") or 0) == transition_motif_rows
        and int(transition_motif_summary.get("repairRowCount") or 0) >= int(transition_motif_summary.get("blockedMotifRowCount") or 0),
        {
            "transitionMotifStatus": transition_motif.get("status"),
            "transitionMotifSummary": transition_motif_summary,
        },
    )

    bridge_sequence_summary = get_summary(bridge_sequence)
    bridge_sequence_rows = int(bridge_sequence_summary.get("sequenceRowCount") or 0)
    add_check(
        checks,
        "Bridge sequence plan turns important transitions into 2-5 shot route/title bridge sequences",
        bridge_sequence.get("status") == "ready_with_bridge_sequence_plan"
        and bridge_sequence_rows >= 3
        and int(bridge_sequence_summary.get("rowsWithDecisionFields") or 0) == bridge_sequence_rows
        and int(bridge_sequence_summary.get("totalRequiredBeatCount") or 0) >= bridge_sequence_rows * 2
        and int(bridge_sequence_summary.get("rowsWithBgmPhraseCue") or 0) == bridge_sequence_rows
        and int(bridge_sequence_summary.get("titleBoundaryRowsSafe") or 0) == bridge_sequence_rows
        and int(bridge_sequence_summary.get("repairRowCount") or 0) >= int(bridge_sequence_summary.get("missingBeatRowCount") or 0),
        {
            "bridgeSequenceStatus": bridge_sequence.get("status"),
            "bridgeSequenceSummary": bridge_sequence_summary,
        },
    )

    bridge_sequence_blueprint_summary = get_summary(bridge_sequence_blueprint)
    bridge_sequence_blueprint_rows = int(bridge_sequence_blueprint_summary.get("sequenceRowCount") or 0)
    bridge_sequence_blueprint_outputs = bridge_sequence_blueprint.get("outputs") if isinstance(bridge_sequence_blueprint.get("outputs"), dict) else {}
    candidate_path = Path(str(bridge_sequence_blueprint_outputs.get("candidateBlueprint") or package_dir / "bridge_sequence_blueprint" / "resolve_timeline_blueprint_bridge_sequence.json"))
    candidate_blueprint = load_json(candidate_path) or {}
    candidate_clips = candidate_blueprint.get("clips") if isinstance(candidate_blueprint.get("clips"), list) else []
    bridge_insert_clips = [clip for clip in candidate_clips if isinstance(clip, dict) and clip.get("role") == "bridge_sequence_insert"]
    add_check(
        checks,
        "Bridge sequence blueprint materializes planned bridge beats into a Resolve candidate",
        bridge_sequence_blueprint.get("status") == "ready_with_bridge_sequence_blueprint"
        and bridge_sequence_blueprint_rows >= 3
        and int(bridge_sequence_blueprint_summary.get("materializedRowCount") or 0) == bridge_sequence_blueprint_rows
        and int(bridge_sequence_blueprint_summary.get("rowsWithDecisionFields") or 0) == bridge_sequence_blueprint_rows
        and int(bridge_sequence_blueprint_summary.get("insertedBeatClipCount") or 0) == len(bridge_insert_clips)
        and int(bridge_sequence_blueprint_summary.get("insertedBeatClipCount") or 0) > 0
        and int(bridge_sequence_blueprint_summary.get("missingBeatCount") or 0) == 0
        and int(bridge_sequence_blueprint_summary.get("incompleteRowCount") or 0) == 0
        and candidate_path.exists()
        and isinstance(candidate_blueprint.get("bridgeSequenceBlueprintPlan"), dict)
        and all(clip.get("includeSourceAudio") is False for clip in bridge_insert_clips),
        {
            "bridgeSequenceBlueprintStatus": bridge_sequence_blueprint.get("status"),
            "bridgeSequenceBlueprintSummary": bridge_sequence_blueprint_summary,
            "candidateBlueprint": str(candidate_path),
            "bridgeInsertClipCount": len(bridge_insert_clips),
        },
    )

    bridge_sequence_application_summary = get_summary(bridge_sequence_application)
    bridge_sequence_application_inputs = bridge_sequence_application.get("inputs") if isinstance(bridge_sequence_application.get("inputs"), dict) else {}
    bridge_sequence_application_rows = int(bridge_sequence_application_summary.get("requiredSequenceRowCount") or 0)
    bridge_sequence_application_expected = int(bridge_sequence_application_summary.get("expectedBeatClipCount") or 0)
    add_check(
        checks,
        "Bridge sequence application contract proves planned bridge beats survive into the final candidate blueprint",
        bridge_sequence_application.get("status") == "passed"
        and bridge_sequence_application_inputs.get("blueprintExists") is True
        and bridge_sequence_application_inputs.get("blueprintInsidePackage") is True
        and bridge_sequence_application_inputs.get("bridgeSequencePlanStatus") == "ready_with_bridge_sequence_plan"
        and bridge_sequence_application_inputs.get("bridgeSequenceBlueprintStatus") == "ready_with_bridge_sequence_blueprint"
        and bridge_sequence_application_rows >= 3
        and int(bridge_sequence_application_summary.get("auditedSequenceRowCount") or 0) == bridge_sequence_application_rows
        and int(bridge_sequence_application_summary.get("passedSequenceRowCount") or 0) == bridge_sequence_application_rows
        and int(bridge_sequence_application_summary.get("blockedSequenceRowCount") or 0) == 0
        and bridge_sequence_application_expected > 0
        and int(bridge_sequence_application_summary.get("appliedBeatClipCount") or 0) >= bridge_sequence_application_expected
        and int(bridge_sequence_application_summary.get("missingBeatClipCount") or 0) == 0
        and int(bridge_sequence_application_summary.get("sourceAudioLeakClipCount") or 0) == 0
        and int(bridge_sequence_application_summary.get("blockerCount") or 0) == 0
        and not bridge_sequence_application.get("blockers"),
        {
            "bridgeSequenceApplicationStatus": bridge_sequence_application.get("status"),
            "bridgeSequenceApplicationSummary": bridge_sequence_application_summary,
            "blueprintKind": bridge_sequence_application_inputs.get("blueprintKind"),
            "blueprint": bridge_sequence_application_inputs.get("blueprint"),
        },
    )

    rhythm_summary = get_summary(rhythm)
    footage_select_summary = get_summary(footage_select)
    chapter_arc_summary = get_summary(chapter_arc)
    creator_cut_summary = get_summary(creator_cut)
    creator_cut_application_summary = get_summary(creator_cut_application)
    creator_cut_application_inputs = creator_cut_application.get("inputs") if isinstance(creator_cut_application.get("inputs"), dict) else {}
    creator_cut_application_clip_count = int(creator_cut_application_summary.get("visualClipCount") or 0)
    add_check(
        checks,
        "Creator cut application contract proves final candidate clips follow selective shot choices",
        creator_cut_application.get("status") == "passed"
        and creator_cut_application_inputs.get("blueprintExists") is True
        and creator_cut_application_inputs.get("blueprintInsidePackage") is True
        and creator_cut_application_clip_count >= 3
        and int(creator_cut_application_summary.get("matchedCreatorRowCount") or 0) == creator_cut_application_clip_count
        and int(creator_cut_application_summary.get("passedClipCount") or 0) == creator_cut_application_clip_count
        and int(creator_cut_application_summary.get("blockedClipCount") or 0) == 0
        and int(creator_cut_application_summary.get("chaptersBlocked") or 0) == 0
        and int(creator_cut_application_summary.get("rejectActiveClipCount") or 0) == 0
        and int(creator_cut_application_summary.get("weakActiveClipCount") or 0) == 0
        and int(creator_cut_application_summary.get("globalFunctionGroupCount") or 0) >= 3
        and int(creator_cut_application_summary.get("blockerCount") or 0) == 0
        and not creator_cut_application.get("blockers"),
        {
            "creatorCutApplicationStatus": creator_cut_application.get("status"),
            "creatorCutApplicationSummary": creator_cut_application_summary,
            "blueprintKind": creator_cut_application_inputs.get("blueprintKind"),
            "blueprint": creator_cut_application_inputs.get("blueprint"),
        },
    )

    final_source_summary = get_summary(final_source_usage)
    final_source_inputs = final_source_usage.get("inputs") if isinstance(final_source_usage.get("inputs"), dict) else {}
    final_source_raw_count = int(final_source_summary.get("rawSourceClipCount") or 0)
    add_check(
        checks,
        "Final source usage proves V14-level raw footage selection survives into the active blueprint",
        final_source_usage.get("status") == "passed"
        and final_source_inputs.get("blueprintExists") is True
        and final_source_inputs.get("blueprintInsidePackage") is True
        and final_source_inputs.get("footageSelectPlanExists") is True
        and final_source_raw_count >= 1
        and int(final_source_summary.get("matchedRawSourceClipCount") or 0) == final_source_raw_count
        and int(final_source_summary.get("unmatchedRawSourceClipCount") or 0) == 0
        and int(final_source_summary.get("selectedCandidateClipCount") or 0) >= 1
        and int(final_source_summary.get("rejectOrRepairActiveClipCount") or 0) == 0
        and int(final_source_summary.get("chaptersBlocked") or 0) == 0
        and int(final_source_summary.get("blockerCount") or 0) == 0
        and not final_source_usage.get("blockers"),
        {
            "finalSourceUsageStatus": final_source_usage.get("status"),
            "finalSourceUsageSummary": final_source_summary,
            "blueprintKind": final_source_inputs.get("blueprintKind"),
            "blueprint": final_source_inputs.get("blueprint"),
        },
    )
    transition_grammar_summary = get_summary(transition_grammar)
    transition_execution_summary = get_summary(transition_execution)
    transition_execution_blueprint_summary = get_summary(transition_execution_blueprint)
    transition_execution_blueprint_rows = int(transition_execution_blueprint_summary.get("executionRowCount") or 0)
    transition_execution_blueprint_outputs = transition_execution_blueprint.get("outputs") if isinstance(transition_execution_blueprint.get("outputs"), dict) else {}
    transition_candidate_path = Path(str(transition_execution_blueprint_outputs.get("candidateBlueprint") or package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json"))
    transition_candidate = load_json(transition_candidate_path) or {}
    transition_candidates = transition_candidate.get("transitions") if isinstance(transition_candidate.get("transitions"), list) else []
    transition_markers = [
        marker for marker in transition_candidate.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "transition_execution_candidate_marker"
    ] if isinstance(transition_candidate.get("timelineMarkers"), list) else []
    annotated_out = sum(len(clip.get("transitionExecutionOut") or []) for clip in transition_candidate.get("clips", []) if isinstance(clip, dict) and isinstance(clip.get("transitionExecutionOut"), list))
    annotated_in = sum(len(clip.get("transitionExecutionIn") or []) for clip in transition_candidate.get("clips", []) if isinstance(clip, dict) and isinstance(clip.get("transitionExecutionIn"), list))
    add_check(
        checks,
        "Transition execution blueprint materializes adjacent-pair recipes into candidate transition metadata",
        transition_execution_blueprint.get("status") == "ready_with_transition_execution_blueprint"
        and transition_execution_blueprint_rows >= 3
        and int(transition_execution_blueprint_summary.get("materializedTransitionCount") or 0) == transition_execution_blueprint_rows
        and int(transition_execution_blueprint_summary.get("candidateTransitionCount") or 0) == len(transition_candidates)
        and int(transition_execution_blueprint_summary.get("candidateTransitionCount") or 0) == transition_execution_blueprint_rows
        and int(transition_execution_blueprint_summary.get("rowsWithDecisionFields") or 0) == transition_execution_blueprint_rows
        and int(transition_execution_blueprint_summary.get("blockedRowCount") or 0) == 0
        and int(transition_execution_blueprint_summary.get("rowsMissingClipMatch") or 0) == 0
        and int(transition_execution_blueprint_summary.get("motionEffectRowsWithEvidence") or 0) == int(transition_execution_blueprint_summary.get("motionEffectRowCount") or 0)
        and int(transition_execution_blueprint_summary.get("bridgeSatisfiedRowCount") or 0) == int(transition_execution_blueprint_summary.get("bridgeRequiredRowCount") or 0)
        and transition_candidate_path.exists()
        and isinstance(transition_candidate.get("transitionExecutionBlueprintPlan"), dict)
        and len(transition_markers) == transition_execution_blueprint_rows
        and annotated_out >= transition_execution_blueprint_rows
        and annotated_in >= transition_execution_blueprint_rows,
        {
            "transitionExecutionBlueprintStatus": transition_execution_blueprint.get("status"),
            "transitionExecutionBlueprintSummary": transition_execution_blueprint_summary,
            "candidateBlueprint": str(transition_candidate_path),
            "candidateTransitionCount": len(transition_candidates),
            "markerCount": len(transition_markers),
            "annotatedOutClipCount": annotated_out,
            "annotatedInClipCount": annotated_in,
        },
    )
    bgm_phrase_blueprint_summary = get_summary(bgm_phrase_blueprint)
    bgm_phrase_blueprint_rows = int(bgm_phrase_blueprint_summary.get("phraseRowCount") or 0)
    bgm_phrase_blueprint_outputs = bgm_phrase_blueprint.get("outputs") if isinstance(bgm_phrase_blueprint.get("outputs"), dict) else {}
    bgm_phrase_candidate_path = Path(str(bgm_phrase_blueprint_outputs.get("candidateBlueprint") or package_dir / "bgm_phrase_blueprint" / "resolve_timeline_blueprint_bgm_phrase.json"))
    bgm_phrase_candidate = load_json(bgm_phrase_candidate_path) or {}
    bgm_phrase_candidates = bgm_phrase_candidate.get("bgmPhraseCandidates") if isinstance(bgm_phrase_candidate.get("bgmPhraseCandidates"), list) else []
    bgm_phrase_markers = [
        marker for marker in bgm_phrase_candidate.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "bgm_phrase_candidate_marker"
    ] if isinstance(bgm_phrase_candidate.get("timelineMarkers"), list) else []
    bgm_phrase_clip_annotations = sum(len(clip.get("bgmPhraseCandidates") or []) for clip in bgm_phrase_candidate.get("clips", []) if isinstance(clip, dict) and isinstance(clip.get("bgmPhraseCandidates"), list))
    bgm_phrase_transition_cues = sum(1 for transition in bgm_phrase_candidate.get("transitions", []) if isinstance(transition, dict) and isinstance(transition.get("bgmPhraseCandidate"), dict))
    bgm_phrase_audio_plan = bgm_phrase_candidate.get("audioPlan") if isinstance(bgm_phrase_candidate.get("audioPlan"), dict) else {}
    add_check(
        checks,
        "BGM phrase blueprint materializes selected music into candidate phrase and transition-cue metadata",
        bgm_phrase_blueprint.get("status") == "ready_with_bgm_phrase_blueprint"
        and bgm_phrase_blueprint_rows >= 4
        and int(bgm_phrase_blueprint_summary.get("selectedBgmBedCount") or 0) >= 1
        and int(bgm_phrase_blueprint_summary.get("sectionRowCount") or 0) >= 3
        and int(bgm_phrase_blueprint_summary.get("materializedPhraseCount") or 0) == bgm_phrase_blueprint_rows
        and int(bgm_phrase_blueprint_summary.get("rowsWithDecisionFields") or 0) == bgm_phrase_blueprint_rows
        and int(bgm_phrase_blueprint_summary.get("blockedRowCount") or 0) == 0
        and int(bgm_phrase_blueprint_summary.get("sourceAudioRiskCount") or 0) == 0
        and int(bgm_phrase_blueprint_summary.get("transitionCueCount") or 0) == bgm_phrase_transition_cues
        and int(bgm_phrase_blueprint_summary.get("transitionsWithPhraseCue") or 0) == bgm_phrase_transition_cues
        and int(bgm_phrase_blueprint_summary.get("candidateTransitionCount") or 0) == bgm_phrase_transition_cues
        and bgm_phrase_candidate_path.exists()
        and isinstance(bgm_phrase_candidate.get("bgmPhraseBlueprintPlan"), dict)
        and isinstance(bgm_phrase_audio_plan.get("bgmPhraseMap"), dict)
        and len(bgm_phrase_candidates) == bgm_phrase_blueprint_rows
        and len(bgm_phrase_markers) == bgm_phrase_blueprint_rows
        and bgm_phrase_clip_annotations >= bgm_phrase_blueprint_rows,
        {
            "bgmPhraseBlueprintStatus": bgm_phrase_blueprint.get("status"),
            "bgmPhraseBlueprintSummary": bgm_phrase_blueprint_summary,
            "candidateBlueprint": str(bgm_phrase_candidate_path),
            "candidatePhraseCount": len(bgm_phrase_candidates),
            "markerCount": len(bgm_phrase_markers),
            "clipAnnotationCount": bgm_phrase_clip_annotations,
            "transitionCueCount": bgm_phrase_transition_cues,
        },
    )
    rhythm_recut_blueprint_summary = get_summary(rhythm_recut_blueprint)
    rhythm_recut_outputs = rhythm_recut_blueprint.get("outputs") if isinstance(rhythm_recut_blueprint.get("outputs"), dict) else {}
    rhythm_recut_inputs = rhythm_recut_blueprint.get("inputs") if isinstance(rhythm_recut_blueprint.get("inputs"), dict) else {}
    rhythm_recut_candidate_path = Path(str(rhythm_recut_outputs.get("candidateBlueprint") or package_dir / "rhythm_recut_blueprint" / "resolve_timeline_blueprint_rhythm_recut.json"))
    rhythm_recut_candidate = load_json(rhythm_recut_candidate_path) or {}
    rhythm_recut_plan = rhythm_recut_candidate.get("rhythmRecutPlan") if isinstance(rhythm_recut_candidate.get("rhythmRecutPlan"), dict) else {}
    rhythm_recut_bgm_rows = rhythm_recut_candidate.get("bgmPhraseCandidates") if isinstance(rhythm_recut_candidate.get("bgmPhraseCandidates"), list) else []
    rhythm_recut_clip_annotations = sum(len(clip.get("bgmPhraseCandidates") or []) for clip in rhythm_recut_candidate.get("clips", []) if isinstance(clip, dict) and isinstance(clip.get("bgmPhraseCandidates"), list))
    rhythm_recut_transition_cues = sum(1 for transition in rhythm_recut_candidate.get("transitions", []) if isinstance(transition, dict) and isinstance(transition.get("bgmPhraseCandidate"), dict))
    rhythm_recut_status = rhythm_recut_blueprint.get("status")
    rhythm_recut_ready = rhythm_recut_status == "ready_no_recut_needed" or (
        rhythm_recut_status == "ready_with_rhythm_recut_blueprint"
        and int(rhythm_recut_blueprint_summary.get("splitSourceClipCount") or 0) > 0
        and int(rhythm_recut_blueprint_summary.get("cutawayInsertCount") or 0) > 0
        and float(rhythm_recut_blueprint_summary.get("averagePrimaryShotAfterSeconds") or 0) < float(rhythm_recut_blueprint_summary.get("averagePrimaryShotBeforeSeconds") or 0)
    )
    add_check(
        checks,
        "Rhythm recut blueprint preserves transition, effect, and BGM phrase candidate metadata",
        rhythm_recut_ready
        and rhythm_recut_candidate_path.exists()
        and rhythm_recut_inputs.get("baseBlueprintKind") == "bgm_phrase_candidate"
        and rhythm_recut_plan.get("sourceBlueprintKind") == "bgm_phrase_candidate"
        and isinstance(rhythm_recut_candidate.get("rhythmRecutPlan"), dict)
        and isinstance(rhythm_recut_candidate.get("bgmPhraseBlueprintPlan"), dict)
        and rhythm_recut_blueprint_summary.get("bgmPhrasePlanPreserved") is True
        and int(rhythm_recut_blueprint_summary.get("bgmPhraseCandidateCount") or 0) == len(rhythm_recut_bgm_rows)
        and len(rhythm_recut_bgm_rows) >= 4
        and int(rhythm_recut_blueprint_summary.get("bgmPhraseClipAnnotationCount") or 0) == rhythm_recut_clip_annotations
        and rhythm_recut_clip_annotations >= len(rhythm_recut_bgm_rows)
        and int(rhythm_recut_blueprint_summary.get("bgmPhraseTransitionCueCount") or 0) == rhythm_recut_transition_cues
        and rhythm_recut_transition_cues >= 1
        and abs(float(rhythm_recut_blueprint_summary.get("durationDeltaSeconds") or 0.0)) <= 0.5,
        {
            "rhythmRecutStatus": rhythm_recut_blueprint.get("status"),
            "rhythmRecutSummary": rhythm_recut_blueprint_summary,
            "candidateBlueprint": str(rhythm_recut_candidate_path),
            "baseBlueprintKind": rhythm_recut_inputs.get("baseBlueprintKind"),
            "candidateSourceBlueprintKind": rhythm_recut_plan.get("sourceBlueprintKind"),
            "candidateBgmPhraseCount": len(rhythm_recut_bgm_rows),
            "clipAnnotationCount": rhythm_recut_clip_annotations,
            "transitionCueCount": rhythm_recut_transition_cues,
        },
    )
    rhythm_recut_application_summary = get_summary(rhythm_recut_application)
    add_check(
        checks,
        "Rhythm recut application contract proves recut main segments and cutaways survive into the final candidate",
        rhythm_recut_application.get("status") == "passed"
        and int(rhythm_recut_application_summary.get("blockedRecutRowCount") or 0) == 0
        and (
            rhythm_recut_application_summary.get("recutStatus") == "ready_no_recut_needed"
            or int(rhythm_recut_application_summary.get("finalRhythmRecutCutawayCount") or 0) >= 1
        )
        and int(rhythm_recut_application_summary.get("blockerCount") or 0) == 0
        and not rhythm_recut_application.get("blockers"),
        {
            "rhythmRecutApplicationStatus": rhythm_recut_application.get("status"),
            "rhythmRecutApplicationSummary": rhythm_recut_application_summary,
            "blockers": rhythm_recut_application.get("blockers"),
        },
    )
    transition_polish_summary = get_summary(transition_polish_blueprint)
    transition_polish_outputs = transition_polish_blueprint.get("outputs") if isinstance(transition_polish_blueprint.get("outputs"), dict) else {}
    transition_polish_inputs = transition_polish_blueprint.get("inputs") if isinstance(transition_polish_blueprint.get("inputs"), dict) else {}
    transition_polish_candidate_path = Path(str(transition_polish_outputs.get("candidateBlueprint") or package_dir / "transition_polish_blueprint" / "resolve_timeline_blueprint_transition_polish.json"))
    transition_polish_candidate = load_json(transition_polish_candidate_path) or {}
    transition_polish_plan = transition_polish_candidate.get("transitionPolishBlueprintPlan") if isinstance(transition_polish_candidate.get("transitionPolishBlueprintPlan"), dict) else {}
    transition_polish_rows = transition_polish_blueprint.get("polishRows") if isinstance(transition_polish_blueprint.get("polishRows"), list) else []
    transition_polish_candidates = transition_polish_candidate.get("transitionPolishCandidates") if isinstance(transition_polish_candidate.get("transitionPolishCandidates"), list) else []
    transition_polish_transitions = transition_polish_candidate.get("transitions") if isinstance(transition_polish_candidate.get("transitions"), list) else []
    transition_polish_markers = [
        marker for marker in transition_polish_candidate.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "transition_polish_candidate_marker"
    ] if isinstance(transition_polish_candidate.get("timelineMarkers"), list) else []
    transition_polish_clip_annotations = sum(
        len(clip.get("transitionPolishOut") or []) + len(clip.get("transitionPolishIn") or [])
        for clip in transition_polish_candidate.get("clips", [])
        if isinstance(clip, dict)
    )
    transition_polish_transition_annotations = sum(
        1 for transition in transition_polish_transitions
        if isinstance(transition, dict) and isinstance(transition.get("transitionPolishCandidate"), dict)
    )
    add_check(
        checks,
        "Transition polish blueprint gives final transitions BGM-hit timing, title safety, and motion-proof keyframes",
        transition_polish_blueprint.get("status") == "ready_with_transition_polish_blueprint"
        and transition_polish_candidate_path.exists()
        and transition_polish_inputs.get("baseBlueprintKind") in {"rhythm_recut_candidate", "bgm_phrase_candidate"}
        and transition_polish_plan.get("baseBlueprintKind") == transition_polish_inputs.get("baseBlueprintKind")
        and isinstance(transition_polish_candidate.get("transitionPolishBlueprintPlan"), dict)
        and int(transition_polish_summary.get("transitionRowCount") or 0) >= 1
        and int(transition_polish_summary.get("polishedTransitionCount") or 0) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and len(transition_polish_rows) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and len(transition_polish_candidates) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and transition_polish_transition_annotations == int(transition_polish_summary.get("transitionRowCount") or 0)
        and int(transition_polish_summary.get("rowsWithDecisionFields") or 0) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and int(transition_polish_summary.get("rowsWithBgmPhraseCue") or 0) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and int(transition_polish_summary.get("rowsWithBgmHit") or 0) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and int(transition_polish_summary.get("rowsWithTitleSubtitleAvoidance") or 0) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and int(transition_polish_summary.get("motionPolishRowsWithEvidence") or 0) == int(transition_polish_summary.get("motionPolishRowCount") or 0)
        and int(transition_polish_summary.get("blockedRowCount") or 0) == 0
        and transition_polish_clip_annotations >= int(transition_polish_summary.get("transitionRowCount") or 0)
        and len(transition_polish_markers) == int(transition_polish_summary.get("transitionRowCount") or 0)
        and int(transition_polish_summary.get("candidateBgmPhraseCount") or 0) >= 4,
        {
            "transitionPolishStatus": transition_polish_blueprint.get("status"),
            "transitionPolishSummary": transition_polish_summary,
            "candidateBlueprint": str(transition_polish_candidate_path),
            "baseBlueprintKind": transition_polish_inputs.get("baseBlueprintKind"),
            "candidateSourceBlueprintKind": transition_polish_plan.get("baseBlueprintKind"),
            "candidatePolishCount": len(transition_polish_candidates),
            "transitionAnnotationCount": transition_polish_transition_annotations,
            "clipAnnotationCount": transition_polish_clip_annotations,
            "markerCount": len(transition_polish_markers),
        },
    )
    transition_polish_application_summary = get_summary(transition_polish_application)
    transition_polish_application_inputs = transition_polish_application.get("inputs") if isinstance(transition_polish_application.get("inputs"), dict) else {}
    transition_polish_application_rows = int(transition_polish_application_summary.get("sourcePolishRowCount") or 0)
    transition_polish_application_motion = int(transition_polish_application_summary.get("motionRowCount") or 0)
    add_check(
        checks,
        "Transition polish application contract proves final active blueprints preserve BGM-hit title-safe transition metadata",
        transition_polish_application.get("status") == "passed"
        and transition_polish_application_inputs.get("transitionPolishStatus") == "ready_with_transition_polish_blueprint"
        and transition_polish_application_inputs.get("sourceCandidateExists") is True
        and transition_polish_application_inputs.get("sourceCandidateInsidePackage") is True
        and transition_polish_application_inputs.get("finalBlueprintExists") is True
        and transition_polish_application_inputs.get("finalBlueprintInsidePackage") is True
        and transition_polish_application_inputs.get("finalHasTransitionPolishBlueprintPlan") is True
        and transition_polish_application_rows >= 1
        and int(transition_polish_application_summary.get("finalTransitionPolishCandidateCount") or 0) >= transition_polish_application_rows
        and int(transition_polish_application_summary.get("finalTransitionRowCount") or 0) >= transition_polish_application_rows
        and int(transition_polish_application_summary.get("auditedPolishRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("passedPolishRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("blockedPolishRowCount") or 0) == 0
        and int(transition_polish_application_summary.get("recipeReadyRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("bgmHitRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("bgmOnlyRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("titleSafeRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("pairReadyRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("clipAnnotationRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("markerRowCount") or 0) == transition_polish_application_rows
        and int(transition_polish_application_summary.get("motionReadyRowCount") or 0) == transition_polish_application_motion
        and int(transition_polish_application_summary.get("blockerCount") or 0) == 0
        and not transition_polish_application.get("blockers"),
        {
            "transitionPolishApplicationStatus": transition_polish_application.get("status"),
            "transitionPolishApplicationSummary": transition_polish_application_summary,
            "finalBlueprintKind": transition_polish_application_inputs.get("finalBlueprintKind"),
            "finalBlueprint": transition_polish_application_inputs.get("finalBlueprint"),
        },
    )
    resolve_transition_materialization_summary = get_summary(resolve_transition_materialization)
    resolve_transition_materialization_inputs = resolve_transition_materialization.get("inputs") if isinstance(resolve_transition_materialization.get("inputs"), dict) else {}
    resolve_transition_materialization_rows = int(resolve_transition_materialization_summary.get("transitionCandidateCount") or 0)
    add_check(
        checks,
        "Resolve transition materialization contract proves final transition recipes are present in Resolve marker payload/readback metadata",
        resolve_transition_materialization.get("status") == "passed"
        and resolve_transition_materialization_inputs.get("blueprintExists") is True
        and resolve_transition_materialization_inputs.get("blueprintInsidePackage") is True
        and resolve_transition_materialization_inputs.get("buildResolveTimelinePreservesMarkerPayload") is True
        and resolve_transition_materialization_rows >= 1
        and int(resolve_transition_materialization_summary.get("transitionRowsWithMarkerPayload") or 0) == resolve_transition_materialization_rows
        and int(resolve_transition_materialization_summary.get("transitionRowsWithClipAnnotation") or 0) == resolve_transition_materialization_rows
        and int(resolve_transition_materialization_summary.get("blockedTransitionRowCount") or 0) == 0
        and int(resolve_transition_materialization_summary.get("blockerCount") or 0) == 0
        and not resolve_transition_materialization.get("blockers"),
        {
            "resolveTransitionMaterializationStatus": resolve_transition_materialization.get("status"),
            "resolveTransitionMaterializationSummary": resolve_transition_materialization_summary,
            "blueprintKind": resolve_transition_materialization_inputs.get("blueprintKind"),
            "resolveReadbackChecked": resolve_transition_materialization_inputs.get("resolveReadbackChecked"),
        },
    )
    resolve_transition_apply_summary = get_summary(resolve_transition_apply)
    resolve_transition_apply_inputs = resolve_transition_apply.get("inputs") if isinstance(resolve_transition_apply.get("inputs"), dict) else {}
    resolve_transition_apply_rows = int(resolve_transition_apply_summary.get("transitionApplyRowCount") or 0)
    add_check(
        checks,
        "Resolve transition apply contract proves visible transitions have a real apply path instead of marker-only metadata",
        resolve_transition_apply.get("status") == "passed"
        and resolve_transition_apply_inputs.get("applyPlanExists") is True
        and resolve_transition_apply_inputs.get("applyPlanStatus") == "ready_with_resolve_transition_apply_plan"
        and resolve_transition_apply_inputs.get("materializationStatus") == "passed"
        and resolve_transition_apply_rows >= 1
        and int(resolve_transition_apply_summary.get("passedRowCount") or 0) == resolve_transition_apply_rows
        and int(resolve_transition_apply_summary.get("blockedRowCount") or 0) == 0
        and int(resolve_transition_apply_summary.get("visibleEffectRowsWithApplyPath") or 0) == int(resolve_transition_apply_summary.get("visibleEffectRowCount") or 0)
        and int(resolve_transition_apply_summary.get("readbackEvidenceRequiredRowCount") or 0) == resolve_transition_apply_rows
        and int(resolve_transition_apply_summary.get("decisionFieldRowCount") or 0) == resolve_transition_apply_rows
        and int(resolve_transition_apply_summary.get("markerOnlyBlockedRowCount") or 0) == 0
        and int(resolve_transition_apply_summary.get("blockerCount") or 0) == 0
        and not resolve_transition_apply.get("blockers"),
        {
            "resolveTransitionApplyStatus": resolve_transition_apply.get("status"),
            "resolveTransitionApplySummary": resolve_transition_apply_summary,
            "applyPlanStatus": resolve_transition_apply_inputs.get("applyPlanStatus"),
            "materializationStatus": resolve_transition_apply_inputs.get("materializationStatus"),
        },
    )
    final_blueprint_lineage_summary = get_summary(final_blueprint_lineage)
    final_blueprint_lineage_inputs = final_blueprint_lineage.get("inputs") if isinstance(final_blueprint_lineage.get("inputs"), dict) else {}
    final_blueprint_lineage_required = int(final_blueprint_lineage_summary.get("requiredMinimumReadyStages") or final_blueprint_lineage_inputs.get("minimumReadyStages") or 5)
    add_check(
        checks,
        "Final blueprint lineage contract proves the active blueprint inherited the latest ready candidate chain",
        final_blueprint_lineage.get("status") == "passed"
        and final_blueprint_lineage_inputs.get("finalBlueprintExists") is True
        and final_blueprint_lineage_inputs.get("finalBlueprintInsidePackage") is True
        and int(final_blueprint_lineage_summary.get("readyStageCount") or 0) >= final_blueprint_lineage_required
        and int(final_blueprint_lineage_summary.get("passedStageCount") or 0) >= final_blueprint_lineage_required
        and int(final_blueprint_lineage_summary.get("blockedReadyStageCount") or 0) == 0
        and int(final_blueprint_lineage_summary.get("finalPlanKeyCount") or 0) >= final_blueprint_lineage_required
        and int(final_blueprint_lineage_summary.get("blockerCount") or 0) == 0
        and not final_blueprint_lineage.get("blockers"),
        {
            "finalBlueprintLineageStatus": final_blueprint_lineage.get("status"),
            "finalBlueprintLineageSummary": final_blueprint_lineage_summary,
            "finalBlueprintKind": final_blueprint_lineage_inputs.get("finalBlueprintKind"),
            "finalBlueprint": final_blueprint_lineage_inputs.get("finalBlueprint"),
        },
    )
    effect_motion_application_summary = get_summary(effect_motion_application)
    add_check(
        checks,
        "Effect motion application contract proves restrained title and route-motion effects survived into the final blueprint",
        effect_motion_application.get("status") == "passed"
        and int(effect_motion_application_summary.get("sourceEffectRowCount") or 0) >= 3
        and int(effect_motion_application_summary.get("passedEffectRowCount") or 0) == int(effect_motion_application_summary.get("sourceEffectRowCount") or 0)
        and int(effect_motion_application_summary.get("blockedEffectRowCount") or 0) == 0
        and int(effect_motion_application_summary.get("motionEffectRowCount") or 0) <= int(effect_motion_application_summary.get("maxMotionAllowed") or 0)
        and int(effect_motion_application_summary.get("bgmOnlyRowCount") or 0) == int(effect_motion_application_summary.get("sourceEffectRowCount") or 0)
        and int(effect_motion_application_summary.get("titleSafeRowCount") or 0) == int(effect_motion_application_summary.get("sourceEffectRowCount") or 0)
        and int(effect_motion_application_summary.get("sourceEvidenceRowCount") or 0) == int(effect_motion_application_summary.get("sourceEffectRowCount") or 0)
        and int(effect_motion_application_summary.get("motionEvidenceRowCount") or 0) == int(effect_motion_application_summary.get("sourceEffectRowCount") or 0)
        and int(effect_motion_application_summary.get("clipAnnotationRowCount") or 0) == int(effect_motion_application_summary.get("sourceEffectRowCount") or 0)
        and int(effect_motion_application_summary.get("markerRowCount") or 0) == int(effect_motion_application_summary.get("sourceEffectRowCount") or 0)
        and int(effect_motion_application_summary.get("forbiddenEffectHitCount") or 0) == 0
        and int(effect_motion_application_summary.get("blockerCount") or 0) == 0
        and not effect_motion_application.get("blockers"),
        {
            "effectMotionApplicationStatus": effect_motion_application.get("status"),
            "effectMotionApplicationSummary": effect_motion_application_summary,
            "blockers": effect_motion_application.get("blockers"),
        },
    )
    transition_cadence_summary = get_summary(transition_cadence)
    add_check(
        checks,
        "Transition cadence contract proves V14 transition polish survives as film-level rhythm instead of bare cuts or effect spam",
        transition_cadence.get("status") == "passed"
        and int(transition_cadence_summary.get("visualBoundaryCount") or 0) >= 1
        and int(transition_cadence_summary.get("transitionRowCount") or 0) >= int(transition_cadence_summary.get("visualBoundaryCount") or 0)
        and int(transition_cadence_summary.get("craftedTransitionCount") or 0) >= int(transition_cadence_summary.get("minimumCraftedTransitionCount") or 0)
        and int(transition_cadence_summary.get("motionTransitionCount") or 0) <= int(transition_cadence_summary.get("maxMotionAllowed") or 0)
        and int(transition_cadence_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and float(transition_cadence_summary.get("dominantStyleShare") or 0.0) <= 0.7
        and int(transition_cadence_summary.get("appliedBridgeBeatClipCount") or 0) >= int(transition_cadence_summary.get("expectedBridgeBeatClipCount") or 0)
        and int(transition_cadence_summary.get("blockedCheckCount") or 0) == 0
        and not transition_cadence.get("blockers"),
        {
            "transitionCadenceStatus": transition_cadence.get("status"),
            "transitionCadenceSummary": transition_cadence_summary,
        },
    )
    transition_microstructure_summary = get_summary(transition_microstructure)
    transition_microstructure_boundaries = int(transition_microstructure_summary.get("visualBoundaryCount") or 0)
    add_check(
        checks,
        "Transition microstructure contract proves each adjacent V14 shot has a landed BGM/title-safe/BGM-only transition beat",
        transition_microstructure.get("status") == "passed"
        and transition_microstructure_boundaries >= 1
        and int(transition_microstructure_summary.get("transitionRowCount") or 0) >= transition_microstructure_boundaries
        and int(transition_microstructure_summary.get("bgmHitBoundaryCount") or 0) == transition_microstructure_boundaries
        and int(transition_microstructure_summary.get("titleSafeBoundaryCount") or 0) == transition_microstructure_boundaries
        and int(transition_microstructure_summary.get("bgmOnlyBoundaryCount") or 0) == transition_microstructure_boundaries
        and int(transition_microstructure_summary.get("handleReadyBoundaryCount") or 0) == transition_microstructure_boundaries
        and int(transition_microstructure_summary.get("pairReadyBoundaryCount") or 0) == transition_microstructure_boundaries
        and int(transition_microstructure_summary.get("weakPairFitCount") or 0) == 0
        and int(transition_microstructure_summary.get("motionBoundaryCount") or 0) <= int(transition_microstructure_summary.get("maxMotionAllowed") or 0)
        and int(transition_microstructure_summary.get("motionReadyBoundaryCount") or 0) == int(transition_microstructure_summary.get("motionBoundaryCount") or 0)
        and float(transition_microstructure_summary.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and int(transition_microstructure_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and int(transition_microstructure_summary.get("markerOnlyBlockedRowCount") or 0) == 0
        and int(transition_microstructure_summary.get("appliedBridgeBeatClipCount") or 0) >= int(transition_microstructure_summary.get("expectedBridgeBeatClipCount") or 0)
        and int(transition_microstructure_summary.get("blockedCheckCount") or 0) == 0
        and not transition_microstructure.get("blockers"),
        {
            "transitionMicrostructureStatus": transition_microstructure.get("status"),
            "transitionMicrostructureSummary": transition_microstructure_summary,
        },
    )
    transition_quality_summary = get_summary(transition_quality)
    transition_quality_inputs = transition_quality.get("inputs") if isinstance(transition_quality.get("inputs"), dict) else {}
    transition_quality_rows = int(transition_quality_summary.get("transitionRowCount") or 0)
    transition_quality_boundaries = int(transition_quality_summary.get("visualBoundaryCount") or 0)
    transition_quality_motion = int(transition_quality_summary.get("motionRowCount") or 0)
    transition_quality_bridge = int(transition_quality_summary.get("bridgeRequiredRows") or 0)
    add_check(
        checks,
        "Transition quality contract covers every visual boundary with BGM-hit, title-safe, non-template transitions",
        transition_quality.get("status") == "passed"
        and transition_quality_inputs.get("blueprintKind") == "transition_polish_candidate"
        and transition_quality_inputs.get("blueprintExists") is True
        and transition_quality_rows >= transition_quality_boundaries
        and transition_quality_rows >= 1
        and float(transition_quality_summary.get("transitionCoverageRatio") or 0) >= 1.0
        and int(transition_quality_summary.get("rowsWithBgmHit") or 0) == transition_quality_rows
        and int(transition_quality_summary.get("rowsTitleSafe") or 0) == transition_quality_rows
        and int(transition_quality_summary.get("rowsWithKeyframesOrCleanCut") or 0) == transition_quality_rows
        and int(transition_quality_summary.get("bgmOnlyAudioRows") or 0) == transition_quality_rows
        and int(transition_quality_summary.get("motionRowsWithEvidence") or 0) == transition_quality_motion
        and int(transition_quality_summary.get("craftedTransitionCount") or 0) >= int(transition_quality_summary.get("minimumCraftedTransitionCount") or 0)
        and int(transition_quality_summary.get("bridgeSatisfiedRows") or 0) == transition_quality_bridge
        and int(transition_quality_summary.get("forbiddenHitCount") or 0) == 0
        and int(transition_quality_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and int(transition_quality_summary.get("blockedRowCount") or 0) == 0
        and not transition_quality.get("blockers"),
        {
            "transitionQualityStatus": transition_quality.get("status"),
            "transitionQualitySummary": transition_quality_summary,
            "blueprintKind": transition_quality_inputs.get("blueprintKind"),
            "blueprint": transition_quality_inputs.get("blueprint"),
        },
    )
    shot_boundary_summary = get_summary(shot_transition_boundary)
    shot_boundary_inputs = shot_transition_boundary.get("inputs") if isinstance(shot_transition_boundary.get("inputs"), dict) else {}
    shot_boundary_count = int(shot_boundary_summary.get("visualBoundaryCount") or 0)
    shot_boundary_motion = int(shot_boundary_summary.get("motionBoundaryCount") or 0)
    add_check(
        checks,
        "Shot transition boundary contract matches every adjacent from/to pair to BGM-hit title-safe transition metadata",
        shot_transition_boundary.get("status") == "passed"
        and shot_boundary_inputs.get("blueprintKind") == "transition_polish_candidate"
        and shot_boundary_inputs.get("blueprintExists") is True
        and shot_boundary_count >= 1
        and int(shot_boundary_summary.get("transitionRowCount") or 0) >= shot_boundary_count
        and int(shot_boundary_summary.get("auditedBoundaryCount") or 0) == shot_boundary_count
        and int(shot_boundary_summary.get("passedBoundaryCount") or 0) == shot_boundary_count
        and int(shot_boundary_summary.get("blockedBoundaryCount") or 0) == 0
        and int(shot_boundary_summary.get("pairMatchedBoundaryCount") or 0) == shot_boundary_count
        and int(shot_boundary_summary.get("bgmHitBoundaryCount") or 0) == shot_boundary_count
        and int(shot_boundary_summary.get("titleSafeBoundaryCount") or 0) == shot_boundary_count
        and int(shot_boundary_summary.get("bgmOnlyBoundaryCount") or 0) == shot_boundary_count
        and int(shot_boundary_summary.get("motionSafeBoundaryCount") or 0) == shot_boundary_motion
        and int(shot_boundary_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and not shot_transition_boundary.get("blockers"),
        {
            "shotTransitionBoundaryStatus": shot_transition_boundary.get("status"),
            "shotTransitionBoundarySummary": shot_boundary_summary,
            "blueprintKind": shot_boundary_inputs.get("blueprintKind"),
            "blueprint": shot_boundary_inputs.get("blueprint"),
        },
    )
    transition_motivation_summary = get_summary(transition_motivation)
    transition_motivation_inputs = transition_motivation.get("inputs") if isinstance(transition_motivation.get("inputs"), dict) else {}
    transition_motivation_count = int(transition_motivation_summary.get("visualBoundaryCount") or 0)
    add_check(
        checks,
        "Transition motivation contract proves each transition has route, bridge, motion, title, or BGM reasoning",
        transition_motivation.get("status") == "passed"
        and transition_motivation_inputs.get("blueprintKind") == "transition_polish_candidate"
        and transition_motivation_inputs.get("blueprintExists") is True
        and transition_motivation_count >= 1
        and int(transition_motivation_summary.get("transitionRowCount") or 0) >= transition_motivation_count
        and float(transition_motivation_summary.get("transitionCoverageRatio") or 0) >= 1.0
        and int(transition_motivation_summary.get("auditedBoundaryCount") or 0) == transition_motivation_count
        and int(transition_motivation_summary.get("passedBoundaryCount") or 0) == transition_motivation_count
        and int(transition_motivation_summary.get("blockedBoundaryCount") or 0) == 0
        and int(transition_motivation_summary.get("motivatedBoundaryCount") or 0) == transition_motivation_count
        and int(transition_motivation_summary.get("pairMatchedBoundaryCount") or 0) == transition_motivation_count
        and int(transition_motivation_summary.get("bgmMotivatedBoundaryCount") or 0) == transition_motivation_count
        and int(transition_motivation_summary.get("titleSafeMotivatedBoundaryCount") or 0) == transition_motivation_count
        and int(transition_motivation_summary.get("forbiddenHitCount") or 0) == 0
        and int(transition_motivation_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and not transition_motivation.get("blockers"),
        {
            "transitionMotivationStatus": transition_motivation.get("status"),
            "transitionMotivationSummary": transition_motivation_summary,
            "blueprintKind": transition_motivation_inputs.get("blueprintKind"),
            "blueprint": transition_motivation_inputs.get("blueprint"),
        },
    )
    transition_pair_continuity_summary = get_summary(transition_pair_continuity)
    transition_pair_continuity_inputs = transition_pair_continuity.get("inputs") if isinstance(transition_pair_continuity.get("inputs"), dict) else {}
    transition_pair_continuity_count = int(transition_pair_continuity_summary.get("visualBoundaryCount") or 0)
    add_check(
        checks,
        "Transition pair continuity contract proves each adjacent from/to shot has visual, route, motion, BGM, or title continuity evidence",
        transition_pair_continuity.get("status") == "passed"
        and transition_pair_continuity_inputs.get("blueprintKind") == "transition_polish_candidate"
        and transition_pair_continuity_inputs.get("blueprintExists") is True
        and transition_pair_continuity_count >= 1
        and int(transition_pair_continuity_summary.get("transitionRowCount") or 0) >= transition_pair_continuity_count
        and float(transition_pair_continuity_summary.get("transitionCoverageRatio") or 0) >= 1.0
        and int(transition_pair_continuity_summary.get("auditedBoundaryCount") or 0) == transition_pair_continuity_count
        and int(transition_pair_continuity_summary.get("passedBoundaryCount") or 0) == transition_pair_continuity_count
        and int(transition_pair_continuity_summary.get("blockedBoundaryCount") or 0) == 0
        and int(transition_pair_continuity_summary.get("pairContinuityPayloadCount") or 0) == transition_pair_continuity_count
        and int(transition_pair_continuity_summary.get("pairMatchedBoundaryCount") or 0) == transition_pair_continuity_count
        and int(transition_pair_continuity_summary.get("styleAllowedBoundaryCount") or 0) == transition_pair_continuity_count
        and int(transition_pair_continuity_summary.get("weakPairFitCount") or 0) == 0
        and int(transition_pair_continuity_summary.get("strongPairFitCount") or 0) + int(transition_pair_continuity_summary.get("acceptablePairFitCount") or 0) == transition_pair_continuity_count
        and not transition_pair_continuity.get("blockers"),
        {
            "transitionPairContinuityStatus": transition_pair_continuity.get("status"),
            "transitionPairContinuitySummary": transition_pair_continuity_summary,
            "blueprintKind": transition_pair_continuity_inputs.get("blueprintKind"),
            "blueprint": transition_pair_continuity_inputs.get("blueprint"),
        },
    )
    transition_execution_readiness_summary = get_summary(transition_execution_readiness)
    transition_execution_readiness_inputs = transition_execution_readiness.get("inputs") if isinstance(transition_execution_readiness.get("inputs"), dict) else {}
    transition_execution_readiness_count = int(transition_execution_readiness_summary.get("visualBoundaryCount") or 0)
    transition_execution_readiness_motion = int(transition_execution_readiness_summary.get("motionBoundaryCount") or 0)
    add_check(
        checks,
        "Transition execution readiness contract proves final transitions have package-local Resolve recipes, BGM hits, title-safe windows, pair readiness, and handles",
        transition_execution_readiness.get("status") == "passed"
        and transition_execution_readiness_inputs.get("blueprintKind") == "transition_polish_candidate"
        and transition_execution_readiness_inputs.get("blueprintExists") is True
        and transition_execution_readiness_inputs.get("blueprintInsidePackage") is True
        and transition_execution_readiness_count >= 1
        and int(transition_execution_readiness_summary.get("transitionRowCount") or 0) >= transition_execution_readiness_count
        and float(transition_execution_readiness_summary.get("transitionCoverageRatio") or 0) >= 1.0
        and int(transition_execution_readiness_summary.get("auditedBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("passedBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("blockedBoundaryCount") or 0) == 0
        and int(transition_execution_readiness_summary.get("recipeReadyBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("bgmHitBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("bgmOnlyBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("titleSafeBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("decisionFieldBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("pairReadyBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("handleReadyBoundaryCount") or 0) == transition_execution_readiness_count
        and int(transition_execution_readiness_summary.get("motionReadyBoundaryCount") or 0) == transition_execution_readiness_motion
        and int(transition_execution_readiness_summary.get("forbiddenHitCount") or 0) == 0
        and int(transition_execution_readiness_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and float(transition_execution_readiness_summary.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and int(transition_execution_readiness_summary.get("blockerCount") or 0) == 0
        and not transition_execution_readiness.get("blockers"),
        {
            "transitionExecutionReadinessStatus": transition_execution_readiness.get("status"),
            "transitionExecutionReadinessSummary": transition_execution_readiness_summary,
            "blueprintKind": transition_execution_readiness_inputs.get("blueprintKind"),
            "blueprint": transition_execution_readiness_inputs.get("blueprint"),
        },
    )
    transition_scene_arc_summary = get_summary(transition_scene_arc)
    add_check(
        checks,
        "Transition scene arc contract proves V14-level transitions read as outgoing, bridge or motion reason, BGM hit, title-safe window, and landing shot",
        transition_scene_arc.get("status") == "passed"
        and int(transition_scene_arc_summary.get("visualBoundaryCount") or 0) >= 1
        and (
            int(transition_scene_arc_summary.get("importantBoundaryCount") or 0) == 0
            or int(transition_scene_arc_summary.get("sceneArcStrategyCount") or 0) >= 1
        )
        and int(transition_scene_arc_summary.get("appliedBridgeBeatClipCount") or 0) >= int(transition_scene_arc_summary.get("expectedBridgeBeatClipCount") or 0)
        and int(transition_scene_arc_summary.get("motionTransitionCount") or 0) <= int(transition_scene_arc_summary.get("maxMotionAllowed") or 0)
        and int(transition_scene_arc_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and float(transition_scene_arc_summary.get("dominantStyleShare") or 0.0) <= 0.7
        and float(transition_scene_arc_summary.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and transition_scene_arc_summary.get("movementReady") is True
        and transition_scene_arc_summary.get("textureReady") is True
        and transition_scene_arc_summary.get("payoffReady") is True
        and transition_scene_arc_summary.get("aftertasteReady") is True
        and int(transition_scene_arc_summary.get("blockedCheckCount") or 0) == 0
        and not transition_scene_arc.get("blockers"),
        {
            "transitionSceneArcStatus": transition_scene_arc.get("status"),
            "transitionSceneArcSummary": transition_scene_arc_summary,
        },
    )
    transition_effect_palette_summary = get_summary(transition_effect_palette)
    add_check(
        checks,
        "Transition effect palette contract proves V14-level transitions balance clean cuts, match cuts, bridges, dissolves, title reveals, and rare motivated motion",
        transition_effect_palette.get("status") == "passed"
        and int(transition_effect_palette_summary.get("visualBoundaryCount") or 0) >= 1
        and int(transition_effect_palette_summary.get("transitionRowCount") or 0) >= int(transition_effect_palette_summary.get("visualBoundaryCount") or 0)
        and int(transition_effect_palette_summary.get("motifFamilyCount") or 0) >= int(transition_effect_palette_summary.get("minimumPaletteFamilyCount") or 0)
        and int(transition_effect_palette_summary.get("cleanOrMatchCount") or 0) >= 1
        and (
            int(transition_effect_palette_summary.get("importantBoundaryCount") or 0) == 0
            or int(transition_effect_palette_summary.get("physicalBridgeOrSceneArcCount") or 0) >= 1
        )
        and int(transition_effect_palette_summary.get("motionTransitionCount") or 0) <= int(transition_effect_palette_summary.get("maxMotionAllowed") or 0)
        and int(transition_effect_palette_summary.get("decorativeRepeatedRunMax") or 0) < 4
        and float(transition_effect_palette_summary.get("dominantMotifShare") or 0.0) <= 0.65
        and float(transition_effect_palette_summary.get("dominantStyleShare") or 0.0) <= 0.7
        and float(transition_effect_palette_summary.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and int(transition_effect_palette_summary.get("blockedCheckCount") or 0) == 0
        and not transition_effect_palette.get("blockers"),
        {
            "transitionEffectPaletteStatus": transition_effect_palette.get("status"),
            "transitionEffectPaletteSummary": transition_effect_palette_summary,
        },
    )
    transition_visual_match_summary = get_summary(transition_visual_match)
    add_check(
        checks,
        "Transition visual match contract proves every adjacent pair has concrete visual, bridge, motion, mood, title, local, or BGM continuity evidence",
        transition_visual_match.get("status") == "passed"
        and int(transition_visual_match_summary.get("visualBoundaryCount") or 0) >= 1
        and int(transition_visual_match_summary.get("transitionRowCount") or 0) >= int(transition_visual_match_summary.get("visualBoundaryCount") or 0)
        and int(transition_visual_match_summary.get("visualMatchReadyRowCount") or 0) == int(transition_visual_match_summary.get("transitionRowCount") or 0)
        and int(transition_visual_match_summary.get("blockedRowCount") or 0) == 0
        and int(transition_visual_match_summary.get("motionTransitionCount") or 0) <= int(transition_visual_match_summary.get("maxMotionAllowed") or 0)
        and (
            int(transition_visual_match_summary.get("importantBoundaryCount") or 0) == 0
            or int(transition_visual_match_summary.get("importantBridgeOrSceneHandoffCount") or 0) >= int(transition_visual_match_summary.get("importantBoundaryCount") or 0)
        )
        and int(transition_visual_match_summary.get("blockedCheckCount") or 0) == 0
        and not transition_visual_match.get("blockers"),
        {
            "transitionVisualMatchStatus": transition_visual_match.get("status"),
            "transitionVisualMatchSummary": transition_visual_match_summary,
        },
    )
    transition_preview_summary = get_summary(transition_preview_packet)
    transition_preview_quality_summary = get_summary(transition_preview_quality)
    transition_storyboard_summary = get_summary(transition_storyboard)
    add_check(
        checks,
        "Transition storyboard contract proves important V14 transitions have viewer purpose, outgoing/bridge/landing proof, and nonblank generated preview evidence",
        transition_preview_packet.get("status") in {"ready_with_transition_preview_packet", "ready_no_important_transitions"}
        and transition_preview_quality.get("status") == "passed"
        and transition_storyboard.get("status") == "passed"
        and int(transition_storyboard_summary.get("visualBoundaryCount") or 0) >= 1
        and int(transition_storyboard_summary.get("transitionRowCount") or 0) >= int(transition_storyboard_summary.get("visualBoundaryCount") or 0)
        and int(transition_storyboard_summary.get("storyboardReadyRowCount") or 0) == int(transition_storyboard_summary.get("transitionRowCount") or 0)
        and int(transition_storyboard_summary.get("blockedRowCount") or 0) == 0
        and int(transition_storyboard_summary.get("rowsWithViewerPurpose") or 0) == int(transition_storyboard_summary.get("transitionRowCount") or 0)
        and int(transition_storyboard_summary.get("rowsWithOutgoingEvidence") or 0) == int(transition_storyboard_summary.get("transitionRowCount") or 0)
        and int(transition_storyboard_summary.get("rowsWithLandingEvidence") or 0) == int(transition_storyboard_summary.get("transitionRowCount") or 0)
        and (
            int(transition_storyboard_summary.get("importantBoundaryCount") or 0) == 0
            or int(transition_storyboard_summary.get("importantStoryboardReadyCount") or 0) >= int(transition_storyboard_summary.get("importantBoundaryCount") or 0)
        )
        and (
            int(transition_storyboard_summary.get("importantBoundaryCount") or 0) == 0
            or int(transition_storyboard_summary.get("importantPreviewEvidenceCount") or 0) >= int(transition_storyboard_summary.get("importantBoundaryCount") or 0)
        )
        and (
            int(transition_storyboard_summary.get("importantBoundaryCount") or 0) == 0
            or int(transition_preview_summary.get("readyPreviewRowCount") or 0) >= int(transition_storyboard_summary.get("importantBoundaryCount") or 0)
        )
        and (
            int(transition_storyboard_summary.get("importantBoundaryCount") or 0) == 0
            or int(transition_preview_quality_summary.get("previewQualityReadyRowCount") or 0) >= int(transition_storyboard_summary.get("importantBoundaryCount") or 0)
        )
        and int(transition_preview_quality_summary.get("blockedPreviewQualityRowCount") or 0) == 0
        and int(transition_storyboard_summary.get("motionReadyRowCount") or 0) == int(transition_storyboard_summary.get("motionTransitionCount") or 0)
        and int(transition_storyboard_summary.get("blockedCheckCount") or 0) == 0
        and not transition_preview_packet.get("blockers")
        and not transition_preview_quality.get("blockers")
        and not transition_storyboard.get("blockers"),
        {
            "transitionPreviewPacketStatus": transition_preview_packet.get("status"),
            "transitionPreviewPacketSummary": transition_preview_summary,
            "transitionPreviewQualityStatus": transition_preview_quality.get("status"),
            "transitionPreviewQualitySummary": transition_preview_quality_summary,
            "transitionStoryboardStatus": transition_storyboard.get("status"),
            "transitionStoryboardSummary": transition_storyboard_summary,
        },
    )
    reference_scene_grammar_summary = get_summary(reference_scene_grammar)
    reference_scene_grammar_inputs = reference_scene_grammar.get("inputs") if isinstance(reference_scene_grammar.get("inputs"), dict) else {}
    reference_scene_chapter_count = int(reference_scene_grammar_summary.get("chapterCount") or 0)
    add_check(
        checks,
        "Reference scene grammar contract proves opening, chapters, transitions, and ending follow Parallel World/Malta structure",
        reference_scene_grammar.get("status") == "passed"
        and reference_scene_grammar_inputs.get("blueprintExists") is True
        and int(reference_scene_grammar_summary.get("visualClipCount") or 0) >= 3
        and int(reference_scene_grammar_summary.get("openingFunctionCount") or 0) >= 2
        and reference_scene_chapter_count >= 1
        and int(reference_scene_grammar_summary.get("chaptersPassed") or 0) == reference_scene_chapter_count
        and int(reference_scene_grammar_summary.get("chaptersBlocked") or 0) == 0
        and int(reference_scene_grammar_summary.get("endingClipCount") or 0) >= 1
        and reference_scene_grammar_summary.get("pairContinuityStatus") == "passed"
        and int(reference_scene_grammar_summary.get("weakPairFitCount") or 0) == 0
        and reference_scene_grammar_summary.get("openingStoryPlanExists") is True
        and reference_scene_grammar_summary.get("chapterArcPlanExists") is True
        and reference_scene_grammar_summary.get("creatorCutPlanExists") is True
        and int(reference_scene_grammar_summary.get("blockerCount") or 0) == 0
        and not reference_scene_grammar.get("blockers"),
        {
            "referenceSceneGrammarStatus": reference_scene_grammar.get("status"),
            "referenceSceneGrammarSummary": reference_scene_grammar_summary,
            "blueprintKind": reference_scene_grammar_inputs.get("blueprintKind"),
            "blueprint": reference_scene_grammar_inputs.get("blueprint"),
        },
    )
    timeline_variety_summary = get_summary(timeline_variety)
    add_check(
        checks,
        "Timeline variety contract proves V14-level movement, texture, payoff, and aftertaste survive into the final candidate",
        timeline_variety.get("status") == "passed"
        and int(timeline_variety_summary.get("visualClipCount") or 0) >= 3
        and int(timeline_variety_summary.get("rawSourceClipCount") or 0) >= 1
        and int(timeline_variety_summary.get("globalFunctionGroupCount") or 0) >= 4
        and int(timeline_variety_summary.get("sameSourceRunMax") or 0) <= 3
        and int(timeline_variety_summary.get("sameFunctionRunMax") or 0) <= 4
        and timeline_variety_summary.get("movementReady") is True
        and timeline_variety_summary.get("textureReady") is True
        and timeline_variety_summary.get("payoffReady") is True
        and timeline_variety_summary.get("aftertasteReady") is True
        and int(timeline_variety_summary.get("chaptersNeedingVarietyOrRetime") or 0) == 0
        and int(timeline_variety_summary.get("referenceSceneChaptersBlocked") or 0) == 0
        and timeline_variety_summary.get("transitionCadenceStatus") == "passed"
        and timeline_variety_summary.get("finalBlueprintLineageStatus") == "passed"
        and int(timeline_variety_summary.get("blockedCheckCount") or 0) == 0
        and not timeline_variety.get("blockers"),
        {
            "timelineVarietyStatus": timeline_variety.get("status"),
            "timelineVarietySummary": timeline_variety_summary,
        },
    )
    unattended_summary = get_summary(unattended_first_draft)
    add_check(
        checks,
        "Unattended first-draft contract proves the V14 lessons are connected before Resolve apply",
        unattended_first_draft.get("status") in {"passed", "passed_with_warnings"}
        and int(unattended_summary.get("requiredGateCount") or 0) >= 14
        and int(unattended_summary.get("blockedGateCount") or 0) == 0
        and int(unattended_summary.get("passedGateCount") or 0) >= int(unattended_summary.get("requiredGateCount") or 0)
        and not unattended_first_draft.get("blockers"),
        {
            "unattendedFirstDraftStatus": unattended_first_draft.get("status"),
            "unattendedFirstDraftSummary": unattended_summary,
            "warnings": unattended_first_draft.get("warnings"),
        },
    )
    reference_repair_summary = get_summary(reference_repair)
    reference_repair_closure_summary = get_summary(reference_repair_closure)
    reference_repair_closure_rows = reference_repair_closure.get("closureRows") if isinstance(reference_repair_closure.get("closureRows"), list) else []
    reference_repair_closure_p0 = [row for row in reference_repair_closure_rows if isinstance(row, dict) and row.get("priority") == "P0"]
    reference_repair_closure_p0_closed = [row for row in reference_repair_closure_p0 if row.get("status") == "closed"]
    reference_repair_needs_repairs = reference_repair.get("status") == "ready_with_reference_style_repair_plan"
    reference_repair_no_repairs = reference_repair.get("status") == "ready_no_reference_style_repairs_needed"
    add_check(
        checks,
        "Reference repair closure audit proves P0 style fixes are closed by artifacts and post-repair evidence",
        reference_repair_closure.get("status") in {"passed", "passed_with_evidence_warnings"}
        and (
            (
                reference_repair_no_repairs
                and int(reference_repair_closure_summary.get("repairRowCount") or 0) == 0
            )
            or (
                reference_repair_needs_repairs
                and int(reference_repair_closure_summary.get("repairRowCount") or 0) == int(reference_repair_summary.get("repairRowCount") or 0)
                and int(reference_repair_closure_summary.get("p0ClosedRowCount") or 0) == int(reference_repair_closure_summary.get("p0RepairRowCount") or 0)
                and len(reference_repair_closure_p0_closed) == len(reference_repair_closure_p0)
                and int(reference_repair_closure_summary.get("blockedRowCount") or 0) == 0
                and not reference_repair_closure.get("blockers")
            )
        ),
        {
            "referenceStyleRepairStatus": reference_repair.get("status"),
            "referenceStyleRepairSummary": reference_repair_summary,
            "referenceRepairClosureStatus": reference_repair_closure.get("status"),
            "referenceRepairClosureSummary": reference_repair_closure_summary,
            "p0ClosureRows": reference_repair_closure_p0,
        },
    )
    reference_batch_summary = get_summary(reference_batch)
    reference_profile_application_summary = get_summary(reference_profile_application)
    route_summary = get_summary(route_texture)
    director_summary = get_summary(director_intent)
    add_check(
        checks,
        "Bilibili/Malta style, reference-profile application, raw footage selection, creator cut, route texture, rhythm, and director polish gates pass",
        passed_status(reference)
        and passed_status(route_texture)
        and director_intent.get("status") in {"passed", "passed_with_warnings"}
        and passed_status(director_polish)
        and cover_title.get("status") == "passed"
        and reference_batch.get("status") in {"ready_with_reference_batch_profile", "ready_with_single_reference_profile"}
        and reference_profile_application.get("status") == "passed"
        and raw_intake.get("status") == "passed"
        and large_source_unattended.get("status") in {"passed", "passed_with_warnings"}
        and footage_select.get("status") in {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"}
        and source_selection_repair.get("status") == "ready_no_source_selection_repairs_needed"
        and source_selection_coverage.get("status") == "passed"
        and chapter_arc.get("status") == "ready_with_chapter_arc_plan"
        and rhythm.get("status") == "ready_with_edit_rhythm_plan"
        and creator_cut.get("status") == "ready_with_creator_cut_plan"
        and creator_cut_application.get("status") == "passed"
        and final_source_usage.get("status") == "passed"
        and transition_grammar.get("status") == "ready_with_transition_grammar_plan"
        and transition_execution.get("status") == "ready_with_transition_execution_plan"
        and transition_execution_blueprint.get("status") == "ready_with_transition_execution_blueprint"
        and transition_motif.get("status") == "ready_with_transition_motif_plan"
        and bridge_sequence.get("status") == "ready_with_bridge_sequence_plan"
        and bridge_sequence_blueprint.get("status") == "ready_with_bridge_sequence_blueprint"
        and effect_motion_blueprint.get("status") == "ready_with_effect_motion_blueprint"
        and bgm_phrase_blueprint.get("status") == "ready_with_bgm_phrase_blueprint"
        and rhythm_recut_blueprint.get("status") in {"ready_with_rhythm_recut_blueprint", "ready_no_recut_needed"}
        and rhythm_recut_application.get("status") == "passed"
        and transition_polish_blueprint.get("status") == "ready_with_transition_polish_blueprint"
        and transition_polish_application.get("status") == "passed"
        and resolve_transition_materialization.get("status") == "passed"
        and resolve_transition_apply.get("status") == "passed"
        and final_blueprint_lineage.get("status") == "passed"
        and effect_motion_application.get("status") == "passed"
        and transition_cadence.get("status") == "passed"
        and transition_quality.get("status") == "passed"
        and shot_transition_boundary.get("status") == "passed"
        and transition_motivation.get("status") == "passed"
        and transition_pair_continuity.get("status") == "passed"
        and transition_execution_readiness.get("status") == "passed"
        and transition_storyboard.get("status") == "passed"
        and reference_scene_grammar.get("status") == "passed"
        and unattended_first_draft.get("status") in {"passed", "passed_with_warnings"}
        and reference_repair.get("status") in {"ready_with_reference_style_repair_plan", "ready_no_reference_style_repairs_needed"}
        and reference_repair_closure.get("status") in {"passed", "passed_with_evidence_warnings"}
        and int(reference_repair_summary.get("rowsWithDecisionFields") or 0) == int(reference_repair_summary.get("repairRowCount") or 0)
        and int(route_summary.get("matchedTransitions") or 0) >= 1
        and int(rhythm_summary.get("primaryVisualShotCount") or 0) >= 40,
        {
            "referenceStyleStatus": reference.get("status"),
            "routeTextureStatus": route_texture.get("status"),
            "routeTextureSummary": route_summary,
            "directorIntentStatus": director_intent.get("status"),
            "directorIntentSummary": director_summary,
            "directorPolishStatus": director_polish.get("status"),
            "coverTitleStatus": cover_title.get("status"),
            "coverTitleSummary": cover_title_summary,
            "referenceBatchStatus": reference_batch.get("status"),
            "referenceBatchSummary": reference_batch_summary,
            "referenceProfileApplicationStatus": reference_profile_application.get("status"),
            "referenceProfileApplicationSummary": reference_profile_application_summary,
            "rawIntakeStatus": raw_intake.get("status"),
            "rawIntakeSummary": raw_intake_summary,
            "largeSourceUnattendedReadinessStatus": large_source_unattended.get("status"),
            "largeSourceUnattendedReadinessSummary": large_source_summary,
            "footageSelectStatus": footage_select.get("status"),
            "footageSelectSummary": footage_select_summary,
            "sourceSelectionRepairStatus": source_selection_repair.get("status"),
            "sourceSelectionRepairSummary": source_selection_summary,
            "sourceSelectionCoverageStatus": source_selection_coverage.get("status"),
            "sourceSelectionCoverageSummary": source_selection_audit_summary,
            "chapterArcStatus": chapter_arc.get("status"),
            "chapterArcSummary": chapter_arc_summary,
            "editRhythmStatus": rhythm.get("status"),
            "editRhythmSummary": rhythm_summary,
            "creatorCutStatus": creator_cut.get("status"),
            "creatorCutSummary": creator_cut_summary,
            "creatorCutApplicationStatus": creator_cut_application.get("status"),
            "creatorCutApplicationSummary": creator_cut_application_summary,
            "finalSourceUsageStatus": final_source_usage.get("status"),
            "finalSourceUsageSummary": final_source_summary,
            "transitionGrammarStatus": transition_grammar.get("status"),
            "transitionGrammarSummary": transition_grammar_summary,
            "transitionExecutionStatus": transition_execution.get("status"),
            "transitionExecutionSummary": transition_execution_summary,
            "transitionExecutionBlueprintStatus": transition_execution_blueprint.get("status"),
            "transitionExecutionBlueprintSummary": transition_execution_blueprint_summary,
            "transitionMotifStatus": transition_motif.get("status"),
            "transitionMotifSummary": transition_motif_summary,
            "bridgeSequenceStatus": bridge_sequence.get("status"),
            "bridgeSequenceSummary": bridge_sequence_summary,
            "bridgeSequenceBlueprintStatus": bridge_sequence_blueprint.get("status"),
            "bridgeSequenceBlueprintSummary": bridge_sequence_blueprint_summary,
            "effectMotionBlueprintStatus": effect_motion_blueprint.get("status"),
            "effectMotionBlueprintSummary": effect_motion_blueprint_summary,
            "bgmPhraseBlueprintStatus": bgm_phrase_blueprint.get("status"),
            "bgmPhraseBlueprintSummary": bgm_phrase_blueprint_summary,
            "rhythmRecutBlueprintStatus": rhythm_recut_blueprint.get("status"),
            "rhythmRecutBlueprintSummary": rhythm_recut_blueprint_summary,
            "rhythmRecutApplicationStatus": rhythm_recut_application.get("status"),
            "rhythmRecutApplicationSummary": rhythm_recut_application_summary,
            "transitionPolishBlueprintStatus": transition_polish_blueprint.get("status"),
            "transitionPolishBlueprintSummary": transition_polish_summary,
            "transitionPolishApplicationStatus": transition_polish_application.get("status"),
            "transitionPolishApplicationSummary": transition_polish_application_summary,
            "resolveTransitionMaterializationStatus": resolve_transition_materialization.get("status"),
            "resolveTransitionMaterializationSummary": resolve_transition_materialization_summary,
            "resolveTransitionApplyStatus": resolve_transition_apply.get("status"),
            "resolveTransitionApplySummary": resolve_transition_apply_summary,
            "finalBlueprintLineageStatus": final_blueprint_lineage.get("status"),
            "finalBlueprintLineageSummary": final_blueprint_lineage_summary,
            "effectMotionApplicationStatus": effect_motion_application.get("status"),
            "effectMotionApplicationSummary": effect_motion_application_summary,
            "transitionCadenceStatus": transition_cadence.get("status"),
            "transitionCadenceSummary": transition_cadence_summary,
            "transitionQualityStatus": transition_quality.get("status"),
            "transitionQualitySummary": transition_quality_summary,
            "shotTransitionBoundaryStatus": shot_transition_boundary.get("status"),
            "shotTransitionBoundarySummary": shot_boundary_summary,
            "transitionMotivationStatus": transition_motivation.get("status"),
            "transitionMotivationSummary": transition_motivation_summary,
            "transitionPairContinuityStatus": transition_pair_continuity.get("status"),
            "transitionPairContinuitySummary": transition_pair_continuity_summary,
            "transitionExecutionReadinessStatus": transition_execution_readiness.get("status"),
            "transitionExecutionReadinessSummary": transition_execution_readiness_summary,
            "transitionStoryboardStatus": transition_storyboard.get("status"),
            "transitionStoryboardSummary": transition_storyboard_summary,
            "referenceSceneGrammarStatus": reference_scene_grammar.get("status"),
            "referenceSceneGrammarSummary": reference_scene_grammar_summary,
            "unattendedFirstDraftStatus": unattended_first_draft.get("status"),
            "unattendedFirstDraftSummary": unattended_summary,
            "referenceStyleRepairStatus": reference_repair.get("status"),
            "referenceStyleRepairSummary": reference_repair_summary,
            "referenceRepairClosureStatus": reference_repair_closure.get("status"),
            "referenceRepairClosureSummary": reference_repair_closure_summary,
        },
    )

    video = render_video or final_video
    add_check(
        checks,
        "Final output quality matches the V14 4K high-frame-rate high-bitrate floor",
        passed_status(render)
        and int(video.get("width") or 0) >= 3840
        and int(video.get("height") or 0) >= 2160
        and float(video.get("frameRateValue") or 0) >= 50.0
        and float(video.get("bitrateMbps") or 0) >= 60.0
        and 1100.0 <= float(render.get("durationSeconds") or final_report.get("durationSeconds") or 0) <= 1300.0,
        {
            "renderStatus": render.get("status"),
            "video": video,
            "durationSeconds": render.get("durationSeconds") or final_report.get("durationSeconds"),
        },
    )

    final_qa_summary = get_summary(final_qa)
    add_check(
        checks,
        "Final QA suite preserves the V14 17+ stage handoff floor",
        final_qa.get("status") == "passed"
        and int(final_qa_summary.get("totalStages") or 0) >= 17
        and int(final_qa_summary.get("blockedStages") or 0) == 0
        and int(final_qa_summary.get("passedStages") or 0) == int(final_qa_summary.get("totalStages") or -1)
        and passed_status(integrity),
        {
            "finalQaStatus": final_qa.get("status"),
            "finalQaSummary": final_qa_summary,
            "strictPackageIntegrityStatus": integrity.get("status"),
            "strictPackageIntegritySummary": get_summary(integrity),
        },
    )

    maturity_summary = get_summary(maturity)
    add_check(
        checks,
        "Skill maturity preserves the V14 29+ check reusable-skill floor",
        maturity.get("status") == "passed"
        and int(maturity_summary.get("total") or 0) >= 29
        and int(maturity_summary.get("blocked") or 0) == 0
        and int(maturity_summary.get("passed") or 0) == int(maturity_summary.get("total") or -1),
        {
            "skillMaturityStatus": maturity.get("status"),
            "skillMaturitySummary": maturity_summary,
        },
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    status = "blocked" if blockers else "passed"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "contract": "v14_baseline_contract",
        "status": status,
        "packageDir": str(package_dir),
        "skillDir": str(skill_dir),
        "checks": checks,
        "blockers": blockers,
        "summary": {
            "passed": len([row for row in checks if row["status"] == "passed"]),
            "blocked": len(blockers),
            "total": len(checks),
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# V14 Baseline Contract Audit",
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
        "## Checks",
    ]
    for row in report["checks"]:
        lines.extend(
            [
                "",
                f"### {row['name']}",
                f"- Status: `{row['status']}`",
                "- Evidence:",
                "```json",
                json.dumps(row["evidence"], ensure_ascii=False, indent=2)[:6000],
                "```",
            ]
        )
    if report["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a package against the V14 baseline Skill lessons.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--skill-dir", default=str(skill_dir_from_script()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    report = build_report(package_dir, skill_dir)
    write_json(package_dir / "v14_baseline_contract_audit.json", report)
    write_markdown(package_dir / "v14_baseline_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
