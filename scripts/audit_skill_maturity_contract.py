#!/usr/bin/env python3
"""Audit whether the Skill and a package cover the user's unattended-delivery pain points."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_SCRIPTS = {
    "route_recognition": [
        "discover_external_media.py",
        "prepare_external_media_intake.py",
        "run_videoclaw_media_index.py",
        "run_videoclaw_route_pipeline.py",
        "prepare_footage_recognition_report.py",
        "audit_location_truth_contract.py",
        "audit_raw_intake_completeness.py",
        "prepare_blocked_project_recovery_plan.py",
        "prepare_codex_visual_confirmed_route.py",
        "audit_confirmed_route_candidate.py",
        "audit_trip_generalization_contract.py",
    ],
    "davinci_delivery": [
        "check_resolve_api.py",
        "build_resolve_timeline.py",
        "audit_resolve_timeline.py",
        "verify_render_delivery.py",
        "run_final_qa_suite.py",
        "audit_skill_forward_test_contract.py",
    ],
    "user_regression_gates": [
        "analyze_reference_video.py",
        "prepare_reference_batch_profile.py",
        "audit_reference_profile_application_contract.py",
        "audit_reference_transition_profile_contract.py",
        "prepare_bgm_sourcing_brief.py",
        "prepare_bgm_selection_package.py",
        "prepare_bgm_phrase_blueprint.py",
        "prepare_transition_polish_blueprint.py",
        "audit_transition_quality_contract.py",
        "audit_shot_transition_boundary_contract.py",
        "audit_transition_motivation_contract.py",
        "audit_transition_pair_continuity_contract.py",
        "audit_transition_execution_readiness_contract.py",
        "audit_transition_polish_application_contract.py",
        "audit_resolve_transition_materialization_contract.py",
        "prepare_resolve_transition_apply_plan.py",
        "audit_resolve_transition_apply_contract.py",
        "audit_bridge_sequence_application_contract.py",
        "audit_transition_bridge_visual_evidence_contract.py",
        "audit_final_blueprint_lineage_contract.py",
        "audit_transition_cadence_contract.py",
        "audit_transition_microstructure_contract.py",
        "audit_transition_scene_arc_contract.py",
        "audit_transition_effect_palette_contract.py",
        "audit_transition_visual_match_contract.py",
        "prepare_transition_choreography_plan.py",
        "audit_transition_choreography_contract.py",
        "audit_transition_motion_direction_contract.py",
        "audit_transition_cutpoint_contract.py",
        "audit_transition_action_anchor_contract.py",
        "audit_transition_sensory_continuity_contract.py",
        "prepare_transition_preview_packet.py",
        "audit_transition_preview_quality_contract.py",
        "prepare_transition_audition_packet.py",
        "audit_transition_audition_quality_contract.py",
        "audit_transition_audition_visual_proof_contract.py",
        "audit_transition_audition_role_integrity_contract.py",
        "audit_transition_storyboard_contract.py",
        "audit_final_source_usage_contract.py",
        "audit_reference_scene_grammar_contract.py",
        "audit_chapter_story_spine_contract.py",
        "audit_shot_flow_continuity_contract.py",
        "audit_transition_breathing_room_contract.py",
        "audit_scene_flow_arc_contract.py",
        "audit_final_cut_smoothness_contract.py",
        "audit_transition_continuity_rehearsal_contract.py",
        "audit_pacing_watchability_contract.py",
        "audit_narrative_adjacency_contract.py",
        "audit_transition_viewer_orientation_contract.py",
        "audit_transition_scene_settlement_contract.py",
        "audit_timeline_variety_contract.py",
        "prepare_unattended_repair_queue.py",
        "audit_unattended_first_draft_contract.py",
        "prepare_transition_bridge_plan.py",
        "prepare_caption_story_plan.py",
        "audit_audience_caption_contract.py",
        "prepare_title_typography_plan.py",
        "audit_title_visual_proof_contract.py",
        "prepare_visual_establishing_plan.py",
        "prepare_effect_motion_plan.py",
        "prepare_effect_motion_blueprint.py",
        "audit_effect_motion_application_contract.py",
        "prepare_feedback_regression_plan.py",
        "prepare_audio_scene_policy_plan.py",
        "prepare_footage_select_plan.py",
        "prepare_source_selection_repair_plan.py",
        "audit_source_selection_coverage_contract.py",
        "audit_first_assembly_source_order_contract.py",
        "audit_large_source_unattended_readiness_contract.py",
        "prepare_opening_story_plan.py",
        "prepare_chapter_arc_plan.py",
        "prepare_edit_rhythm_plan.py",
        "prepare_creator_cut_plan.py",
        "audit_creator_cut_application_contract.py",
        "prepare_transition_grammar_plan.py",
        "prepare_transition_execution_plan.py",
        "prepare_transition_reference_candidates.py",
        "prepare_transition_reference_selection.py",
        "prepare_transition_execution_blueprint.py",
        "prepare_transition_motif_plan.py",
        "audit_transition_motif_coherence_contract.py",
        "prepare_bridge_sequence_plan.py",
        "prepare_bridge_sequence_blueprint.py",
        "prepare_reference_style_repair_plan.py",
        "audit_reference_repair_closure.py",
        "prepare_rhythm_recut_blueprint.py",
        "audit_rhythm_recut_application_contract.py",
        "prepare_rhythm_recut_apply_package.py",
        "audit_feedback_regressions.py",
        "audit_title_bridge_contract.py",
        "audit_bgm_audio_contract.py",
        "audit_story_style_contract.py",
        "audit_cover_title_contract.py",
        "audit_reference_style_alignment.py",
        "audit_director_intent_contract.py",
        "audit_route_texture_contract.py",
        "audit_stock_aerial_closure.py",
        "audit_director_polish_contract.py",
        "audit_package_integrity.py",
        "make_davinci_stylefix_blueprint.py",
        "prepare_orientation_repair_package.py",
        "audit_v14_baseline_contract.py",
    ],
}

REQUIRED_SKILL_PATTERNS = {
    "regression_first": "Treat every live edit as Skill regression testing",
    "davinci_api_default": "DaVinci Resolve API editing",
    "no_default_ollama": "Do not pull, install, or depend on local Ollama",
    "clean_title_rule": "TOKYO TOKYO",
    "title_stack_rule": "no stacked text or subtitle overlay layers",
    "blueprint_orientation_source_scan": "Resolve blueprint contains no raw portrait/square/unknown video clips",
    "bgm_no_voiceover_rule": "bgm_only_no_camera_voice",
    "bgm_sourcing_brief_rule": "prepare_bgm_sourcing_brief.py",
    "bgm_selection_package_rule": "prepare_bgm_selection_package.py",
    "bgm_phrase_blueprint_rule": "prepare_bgm_phrase_blueprint.py",
    "transition_polish_blueprint_rule": "prepare_transition_polish_blueprint.py",
    "transition_quality_contract_rule": "audit_transition_quality_contract.py",
    "shot_transition_boundary_contract_rule": "audit_shot_transition_boundary_contract.py",
    "transition_motivation_contract_rule": "audit_transition_motivation_contract.py",
    "transition_pair_continuity_contract_rule": "audit_transition_pair_continuity_contract.py",
    "transition_execution_readiness_contract_rule": "audit_transition_execution_readiness_contract.py",
    "transition_polish_application_contract_rule": "audit_transition_polish_application_contract.py",
    "resolve_transition_materialization_contract_rule": "audit_resolve_transition_materialization_contract.py",
    "resolve_transition_apply_contract_rule": "audit_resolve_transition_apply_contract.py",
    "bridge_sequence_application_contract_rule": "audit_bridge_sequence_application_contract.py",
    "transition_bridge_visual_evidence_contract_rule": "audit_transition_bridge_visual_evidence_contract.py",
    "final_blueprint_lineage_contract_rule": "audit_final_blueprint_lineage_contract.py",
    "transition_cadence_contract_rule": "audit_transition_cadence_contract.py",
    "transition_microstructure_contract_rule": "audit_transition_microstructure_contract.py",
    "transition_scene_arc_contract_rule": "audit_transition_scene_arc_contract.py",
    "transition_effect_palette_contract_rule": "audit_transition_effect_palette_contract.py",
    "transition_visual_match_contract_rule": "audit_transition_visual_match_contract.py",
    "transition_choreography_plan_rule": "prepare_transition_choreography_plan.py",
    "transition_choreography_contract_rule": "audit_transition_choreography_contract.py",
    "transition_motion_direction_contract_rule": "audit_transition_motion_direction_contract.py",
    "transition_cutpoint_contract_rule": "audit_transition_cutpoint_contract.py",
    "transition_action_anchor_contract_rule": "audit_transition_action_anchor_contract.py",
    "transition_sensory_continuity_contract_rule": "audit_transition_sensory_continuity_contract.py",
    "transition_preview_packet_rule": "prepare_transition_preview_packet.py",
    "transition_preview_quality_contract_rule": "audit_transition_preview_quality_contract.py",
    "transition_audition_packet_rule": "prepare_transition_audition_packet.py",
    "transition_audition_quality_contract_rule": "audit_transition_audition_quality_contract.py",
    "transition_audition_visual_proof_contract_rule": "audit_transition_audition_visual_proof_contract.py",
    "transition_audition_role_integrity_contract_rule": "audit_transition_audition_role_integrity_contract.py",
    "transition_storyboard_contract_rule": "audit_transition_storyboard_contract.py",
    "final_source_usage_contract_rule": "audit_final_source_usage_contract.py",
    "reference_scene_grammar_contract_rule": "audit_reference_scene_grammar_contract.py",
    "chapter_story_spine_contract_rule": "audit_chapter_story_spine_contract.py",
    "shot_flow_continuity_contract_rule": "audit_shot_flow_continuity_contract.py",
    "transition_breathing_room_contract_rule": "audit_transition_breathing_room_contract.py",
    "scene_flow_arc_contract_rule": "audit_scene_flow_arc_contract.py",
    "final_cut_smoothness_contract_rule": "audit_final_cut_smoothness_contract.py",
    "transition_continuity_rehearsal_contract_rule": "audit_transition_continuity_rehearsal_contract.py",
    "pacing_watchability_contract_rule": "audit_pacing_watchability_contract.py",
    "narrative_adjacency_contract_rule": "audit_narrative_adjacency_contract.py",
    "transition_viewer_orientation_contract_rule": "audit_transition_viewer_orientation_contract.py",
    "transition_scene_settlement_contract_rule": "audit_transition_scene_settlement_contract.py",
    "unattended_repair_queue_rule": "prepare_unattended_repair_queue.py",
    "reference_profile_application_contract_rule": "audit_reference_profile_application_contract.py",
    "reference_transition_profile_contract_rule": "audit_reference_transition_profile_contract.py",
    "timeline_variety_contract_rule": "audit_timeline_variety_contract.py",
    "unattended_first_draft_contract_rule": "audit_unattended_first_draft_contract.py",
    "transition_bridge_plan_rule": "prepare_transition_bridge_plan.py",
    "caption_story_plan_rule": "prepare_caption_story_plan.py",
    "audience_caption_contract_rule": "audience-facing travel-film text",
    "title_typography_plan_rule": "prepare_title_typography_plan.py",
    "cover_title_contract_rule": "audit_cover_title_contract.py",
    "title_visual_proof_contract_rule": "audit_title_visual_proof_contract.py",
    "visual_establishing_plan_rule": "prepare_visual_establishing_plan.py",
    "effect_motion_plan_rule": "prepare_effect_motion_plan.py",
    "effect_motion_blueprint_rule": "prepare_effect_motion_blueprint.py",
    "effect_motion_application_contract_rule": "audit_effect_motion_application_contract.py",
    "feedback_regression_plan_rule": "prepare_feedback_regression_plan.py",
    "audio_scene_policy_plan_rule": "prepare_audio_scene_policy_plan.py",
    "footage_select_plan_rule": "prepare_footage_select_plan.py",
    "source_selection_repair_plan_rule": "prepare_source_selection_repair_plan.py",
    "source_selection_coverage_contract_rule": "audit_source_selection_coverage_contract.py",
    "first_assembly_source_order_contract_rule": "audit_first_assembly_source_order_contract.py",
    "large_source_unattended_readiness_contract_rule": "audit_large_source_unattended_readiness_contract.py",
    "raw_intake_completeness_rule": "audit_raw_intake_completeness.py",
    "opening_story_plan_rule": "prepare_opening_story_plan.py",
    "opening_story_engine_rule": "opening-story-engine.md",
    "chapter_arc_plan_rule": "prepare_chapter_arc_plan.py",
    "chapter_arc_engine_rule": "chapter-arc-engine.md",
    "edit_rhythm_plan_rule": "prepare_edit_rhythm_plan.py",
    "creator_cut_plan_rule": "prepare_creator_cut_plan.py",
    "creator_cut_application_contract_rule": "audit_creator_cut_application_contract.py",
    "transition_grammar_plan_rule": "prepare_transition_grammar_plan.py",
    "transition_execution_plan_rule": "prepare_transition_execution_plan.py",
    "transition_reference_candidates_rule": "prepare_transition_reference_candidates.py",
    "transition_reference_selection_rule": "prepare_transition_reference_selection.py",
    "transition_execution_blueprint_rule": "prepare_transition_execution_blueprint.py",
    "transition_motif_plan_rule": "prepare_transition_motif_plan.py",
    "transition_motif_coherence_contract_rule": "audit_transition_motif_coherence_contract.py",
    "bridge_sequence_plan_rule": "prepare_bridge_sequence_plan.py",
    "bridge_sequence_blueprint_rule": "prepare_bridge_sequence_blueprint.py",
    "reference_style_repair_plan_rule": "prepare_reference_style_repair_plan.py",
    "reference_repair_closure_rule": "audit_reference_repair_closure.py",
    "rhythm_recut_blueprint_rule": "prepare_rhythm_recut_blueprint.py",
    "rhythm_recut_application_contract_rule": "audit_rhythm_recut_application_contract.py",
    "rhythm_recut_apply_package_rule": "prepare_rhythm_recut_apply_package.py",
    "scenic_audio_overlap_rule": "no A1/A2 voice or source-audio clips overlapping scenic/title/transition windows",
    "strict_package_handoff": "strict portable",
    "location_truth_rule": "Never claim GPS-grade",
    "confirmed_route_candidate_audit_rule": "audit_confirmed_route_candidate.py",
    "trip_generalization_rule": "audit_trip_generalization_contract.py",
    "director_intent_rule": "director intent",
    "forward_test_rule": "forward-test",
    "blocked_recovery_rule": "blocked-project recovery",
    "v14_baseline_rule": "audit_v14_baseline_contract.py",
    "parallel_world_reference_rule": "parallel-world-vlog-style.md",
    "parallel_world_cover_rule": "high-recognition aerial/skyline/coast/landmark/route background",
    "reference_batch_profile_rule": "prepare_reference_batch_profile.py",
    "reference_transition_profile_contract_reference_rule": "reference-transition-profile-contract.md",
    "chapter_story_spine_contract_reference_rule": "chapter-story-spine-contract.md",
    "shot_flow_continuity_contract_reference_rule": "shot-flow-continuity-contract.md",
    "transition_breathing_room_contract_reference_rule": "transition-breathing-room-contract.md",
    "scene_flow_arc_contract_reference_rule": "scene-flow-arc-contract.md",
    "final_cut_smoothness_contract_reference_rule": "final-cut-smoothness-contract.md",
    "transition_continuity_rehearsal_contract_reference_rule": "transition-continuity-rehearsal-contract.md",
    "pacing_watchability_contract_reference_rule": "pacing-watchability-contract.md",
    "narrative_adjacency_contract_reference_rule": "narrative-adjacency-contract.md",
    "transition_viewer_orientation_contract_reference_rule": "transition-viewer-orientation-contract.md",
    "transition_scene_settlement_contract_reference_rule": "transition-scene-settlement-contract.md",
    "footage_select_engine_rule": "footage-select-engine.md",
    "source_selection_repair_reference_rule": "source-selection-repair-contract.md",
    "first_assembly_source_order_contract_reference_rule": "first-assembly-source-order-contract.md",
    "large_source_unattended_readiness_contract_reference_rule": "large-source-unattended-readiness-contract.md",
    "creator_cut_engine_rule": "creator-cut-engine.md",
    "transition_grammar_engine_rule": "transition-grammar-engine.md",
    "transition_execution_engine_rule": "transition-execution-engine.md",
    "transition_reference_candidate_engine_rule": "transition-reference-candidate-engine.md",
    "transition_reference_selection_engine_rule": "transition-reference-selection-engine.md",
    "transition_execution_blueprint_engine_rule": "transition-execution-blueprint-engine.md",
    "transition_motif_engine_rule": "transition-motif-engine.md",
    "transition_motif_coherence_contract_reference_rule": "transition-motif-coherence-contract.md",
    "bridge_sequence_engine_rule": "bridge-sequence-engine.md",
    "bridge_sequence_blueprint_engine_rule": "bridge-sequence-blueprint-engine.md",
    "bridge_sequence_application_contract_reference_rule": "bridge-sequence-application-contract.md",
    "transition_bridge_visual_evidence_contract_reference_rule": "transition-bridge-visual-evidence-contract.md",
    "transition_polish_application_contract_reference_rule": "transition-polish-application-contract.md",
    "resolve_transition_materialization_contract_reference_rule": "resolve-transition-materialization-contract.md",
    "resolve_transition_apply_contract_reference_rule": "resolve-transition-apply-contract.md",
    "final_blueprint_lineage_contract_reference_rule": "final-blueprint-lineage-contract.md",
    "transition_cadence_contract_reference_rule": "transition-cadence-contract.md",
    "transition_microstructure_contract_reference_rule": "transition-microstructure-contract.md",
    "transition_scene_arc_contract_reference_rule": "transition-scene-arc-contract.md",
    "transition_effect_palette_contract_reference_rule": "transition-effect-palette-contract.md",
    "transition_visual_match_contract_reference_rule": "transition-visual-match-contract.md",
    "transition_choreography_engine_reference_rule": "transition-choreography-engine.md",
    "transition_choreography_contract_reference_rule": "transition-choreography-contract.md",
    "transition_motion_direction_contract_reference_rule": "transition-motion-direction-contract.md",
    "transition_cutpoint_contract_reference_rule": "transition-cutpoint-contract.md",
    "transition_action_anchor_contract_reference_rule": "transition-action-anchor-contract.md",
    "transition_sensory_continuity_contract_reference_rule": "transition-sensory-continuity-contract.md",
    "transition_preview_packet_reference_rule": "transition-preview-packet-engine.md",
    "transition_preview_quality_contract_reference_rule": "transition-preview-quality-contract.md",
    "transition_audition_packet_reference_rule": "transition-audition-packet-engine.md",
    "transition_audition_quality_contract_reference_rule": "transition-audition-quality-contract.md",
    "transition_audition_visual_proof_contract_reference_rule": "transition-audition-visual-proof-contract.md",
    "transition_audition_role_integrity_contract_reference_rule": "transition-audition-role-integrity-contract.md",
    "transition_storyboard_contract_reference_rule": "transition-storyboard-contract.md",
    "timeline_variety_contract_reference_rule": "timeline-variety-contract.md",
    "final_source_usage_contract_reference_rule": "final-source-usage-contract.md",
    "rhythm_recut_application_contract_reference_rule": "rhythm-recut-application-contract.md",
    "bgm_phrase_blueprint_engine_rule": "bgm-phrase-blueprint-engine.md",
    "transition_polish_blueprint_engine_rule": "transition-polish-blueprint-engine.md",
    "transition_execution_readiness_engine_rule": "transition-execution-readiness-engine.md",
    "effect_motion_blueprint_engine_rule": "effect-motion-blueprint-engine.md",
    "effect_motion_application_contract_reference_rule": "effect-motion-application-contract.md",
    "reference_style_repair_engine_rule": "reference-style-repair-engine.md",
    "unattended_repair_queue_engine_rule": "unattended-repair-queue-engine.md",
}

REQUIRED_STYLE_PATTERNS = {
    "ysjf_anchor": "space.bilibili.com/946974",
    "parallel_world_anchor": "space.bilibili.com/405004967",
    "parallel_world_profile": "parallel-world-vlog-style.md",
    "reference_batch_profile": "reference-batch-profile-engine.md",
    "reference_profile_application_contract": "reference-profile-application-contract.md",
    "reference_transition_profile_contract": "reference-transition-profile-contract.md",
    "footage_select_engine": "footage-select-engine.md",
    "source_selection_repair_contract": "source-selection-repair-contract.md",
    "creator_cut_engine": "creator-cut-engine.md",
    "chapter_arc_engine": "chapter-arc-engine.md",
    "transition_grammar_engine": "transition-grammar-engine.md",
    "transition_execution_engine": "transition-execution-engine.md",
    "transition_reference_candidate_engine": "transition-reference-candidate-engine.md",
    "transition_reference_selection_engine": "transition-reference-selection-engine.md",
    "transition_execution_blueprint_engine": "transition-execution-blueprint-engine.md",
    "transition_motif_engine": "transition-motif-engine.md",
    "transition_motif_coherence_contract": "transition-motif-coherence-contract.md",
    "bridge_sequence_engine": "bridge-sequence-engine.md",
    "bridge_sequence_blueprint_engine": "bridge-sequence-blueprint-engine.md",
    "bridge_sequence_application_contract": "bridge-sequence-application-contract.md",
    "transition_bridge_visual_evidence_contract": "transition-bridge-visual-evidence-contract.md",
    "transition_polish_application_contract": "transition-polish-application-contract.md",
    "resolve_transition_materialization_contract": "resolve-transition-materialization-contract.md",
    "resolve_transition_apply_contract": "resolve-transition-apply-contract.md",
    "final_blueprint_lineage_contract": "final-blueprint-lineage-contract.md",
    "transition_cadence_contract": "transition-cadence-contract.md",
    "transition_storyboard_contract": "transition-storyboard-contract.md",
    "transition_breathing_room_contract": "transition-breathing-room-contract.md",
    "scene_flow_arc_contract": "scene-flow-arc-contract.md",
    "final_cut_smoothness_contract": "final-cut-smoothness-contract.md",
    "transition_continuity_rehearsal_contract": "transition-continuity-rehearsal-contract.md",
    "pacing_watchability_contract": "pacing-watchability-contract.md",
    "narrative_adjacency_contract": "narrative-adjacency-contract.md",
    "transition_viewer_orientation_contract": "transition-viewer-orientation-contract.md",
    "transition_scene_settlement_contract": "transition-scene-settlement-contract.md",
    "transition_choreography_engine": "transition-choreography-engine.md",
    "transition_choreography_contract": "transition-choreography-contract.md",
    "transition_motion_direction_contract": "transition-motion-direction-contract.md",
    "transition_cutpoint_contract": "transition-cutpoint-contract.md",
    "transition_action_anchor_contract": "transition-action-anchor-contract.md",
    "transition_sensory_continuity_contract": "transition-sensory-continuity-contract.md",
    "transition_preview_packet_engine": "transition-preview-packet-engine.md",
    "transition_preview_quality_contract": "transition-preview-quality-contract.md",
    "transition_audition_packet_engine": "transition-audition-packet-engine.md",
    "transition_audition_quality_contract": "transition-audition-quality-contract.md",
    "transition_audition_visual_proof_contract": "transition-audition-visual-proof-contract.md",
    "transition_audition_role_integrity_contract": "transition-audition-role-integrity-contract.md",
    "final_source_usage_contract": "final-source-usage-contract.md",
    "bgm_phrase_blueprint_engine": "bgm-phrase-blueprint-engine.md",
    "transition_polish_blueprint_engine": "transition-polish-blueprint-engine.md",
    "transition_execution_readiness_engine": "transition-execution-readiness-engine.md",
    "effect_motion_blueprint_engine": "effect-motion-blueprint-engine.md",
    "effect_motion_application_contract": "effect-motion-application-contract.md",
    "reference_style_repair_engine": "reference-style-repair-engine.md",
    "unattended_repair_queue_engine": "unattended-repair-queue-engine.md",
    "opening_story_engine": "opening-story-engine.md",
    "full_timeline_review": "full-film timeline strips",
    "cover_title_review": "cover/title card construction",
    "local_reference_profile": "local reference film",
    "mixkit_music": "mixkit.co/free-stock-music",
    "non_copying": "not as assets to copy",
}

REQUIRED_PARALLEL_WORLD_PATTERNS = {
    "full_review_method": "full-film timeline strips every 10 seconds",
    "batch_reference_profile": "reference batch profile",
    "cover_title_formula": "Cover And Hero Title Style",
    "cover_title_contract": "cover title contract",
    "oversized_destination_title": "oversized 1-5 word Chinese destination title",
    "raw_footage_selection": "footage select plan",
    "source_selection_repair": "source selection repair plan",
    "opening_story_plan": "opening_story_plan/opening_story_plan.json",
    "chapter_arc_plan": "chapter_arc_plan/chapter_arc_plan.json",
    "opening_route_promise": "viewer promise, destination proof",
    "transition_execution_plan": "transition execution plan",
    "transition_reference_candidates": "transition reference candidates",
    "transition_reference_selection": "transition reference selection",
    "transition_execution_blueprint": "transition execution blueprint",
    "bgm_phrase_blueprint": "BGM phrase blueprint",
    "transition_polish_blueprint": "transition polish blueprint",
    "transition_execution_readiness_contract": "transition execution readiness contract",
    "transition_polish_application_contract": "transition polish application contract",
    "resolve_transition_materialization_contract": "Resolve transition materialization contract",
    "resolve_transition_apply_contract": "Resolve transition apply contract",
    "transition_cadence_contract": "transition cadence contract",
    "transition_quality_contract": "transition quality contract",
    "reference_transition_profile_contract": "reference transition profile contract",
    "shot_transition_boundary_contract": "shot transition boundary contract",
    "transition_storyboard_contract": "transition storyboard contract",
    "transition_sensory_continuity_contract": "transition sensory-continuity contract",
    "transition_breathing_room_contract": "transition breathing-room contract",
    "scene_flow_arc_contract": "scene flow arc contract",
    "final_cut_smoothness_contract": "final cut smoothness contract",
    "transition_continuity_rehearsal_contract": "transition continuity rehearsal contract",
    "pacing_watchability_contract": "pacing watchability contract",
    "narrative_adjacency_contract": "narrative adjacency contract",
    "transition_viewer_orientation_contract": "transition viewer orientation",
    "transition_scene_settlement_contract": "transition scene settlement",
    "transition_preview_packet": "transition preview packet",
    "transition_preview_quality_contract": "transition preview quality contract",
    "transition_audition_packet": "transition audition packet",
    "transition_audition_quality_contract": "transition audition quality contract",
    "transition_audition_visual_proof_contract": "transition audition visual proof contract",
    "transition_audition_role_integrity_contract": "transition audition role integrity contract",
    "transition_motif_plan": "transition motif plan",
    "transition_motif_coherence_contract": "transition motif coherence",
    "bridge_sequence_plan": "bridge sequence plan",
    "bridge_sequence_blueprint": "bridge sequence blueprint",
    "bridge_sequence_application_contract": "bridge sequence application contract",
    "transition_bridge_visual_evidence_contract": "transition bridge visual evidence contract",
    "transition_polish_application_contract": "transition polish application contract",
    "final_blueprint_lineage_contract": "final-blueprint lineage",
    "final_source_usage_contract": "final source usage",
    "reference_style_repair_plan": "reference style repair plan",
    "unattended_repair_queue": "unattended repair queue",
    "talking_segment_broll": "Long talking segments should be supported by the place",
    "ending_aftertaste": "End with aftertaste after the main experience",
}


def load_json(path: Path) -> Any | None:
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


def text_contains(path: Path, patterns: dict[str, str]) -> tuple[dict[str, bool], str]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    return {name: value in text for name, value in patterns.items()}, text


def find_reference_analysis(package_dir: Path) -> Path | None:
    env_reference = os.environ.get("TRAVEL_VIDEO_REFERENCE_ANALYSIS")
    candidates = [
        package_dir / "reference" / "reference_batch_profile.json",
        package_dir / "reference" / "reference_analysis.json",
        package_dir / "reference" / "reference_analysis.md",
    ]
    if env_reference:
        candidates.insert(0, Path(env_reference).expanduser())
    return next((path for path in candidates if path.exists()), None)


def reference_profile_evidence(path: Path | None) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "referenceAnalysis": str(path) if path else None,
        "exists": bool(path and path.exists()),
        "profileAvailable": False,
    }
    if not path or not path.exists() or path.suffix.lower() != ".json":
        return evidence
    data = load_json(path) or {}
    pacing = data.get("pacingProfile") if isinstance(data.get("pacingProfile"), dict) else {}
    audio = data.get("audioProfile") if isinstance(data.get("audioProfile"), dict) else {}
    samples = data.get("sampleFrames") if isinstance(data.get("sampleFrames"), list) else []
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    evidence.update(
        {
            "profileAvailable": True,
            "durationMinutes": summary.get("durationMinutes") or summary.get("totalDurationMinutes") or data.get("durationMinutes"),
            "pacingStatus": pacing.get("status"),
            "estimatedShotCount": pacing.get("estimatedShotCount"),
            "averageShotLengthSeconds": pacing.get("averageShotLengthSeconds"),
            "medianShotLengthSeconds": pacing.get("medianShotLengthSeconds"),
            "audioStatus": audio.get("status"),
            "meanVolumeDb": audio.get("meanVolumeDb"),
            "sampleFrameCount": len(samples),
            "contactSheet": data.get("contactSheet"),
        }
    )
    return evidence


def reference_profile_ready(evidence: dict[str, Any]) -> bool:
    if not evidence.get("exists"):
        return False
    if not evidence.get("profileAvailable"):
        return False
    return (
        evidence.get("pacingStatus") == "analyzed"
        and evidence.get("audioStatus") == "analyzed"
        and int(evidence.get("estimatedShotCount") or 0) >= 50
        and float(evidence.get("averageShotLengthSeconds") or 0) > 0
        and int(evidence.get("sampleFrameCount") or 0) >= 12
    )


def reference_batch_profile_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "reference" / "reference_batch_profile.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    pacing = data.get("pacingProfile") if isinstance(data.get("pacingProfile"), dict) else {}
    audio = data.get("audioProfile") if isinstance(data.get("audioProfile"), dict) else {}
    samples = data.get("sampleFrames") if isinstance(data.get("sampleFrames"), list) else []
    reports = data.get("referenceReports") if isinstance(data.get("referenceReports"), list) else []
    contract = data.get("referenceUsageContract") if isinstance(data.get("referenceUsageContract"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("acceptanceRubric") if isinstance(data.get("acceptanceRubric"), dict) else {}
    reports_with_analysis = sum(1 for row in reports if isinstance(row, dict) and row.get("analysisPath"))
    reports_with_pacing = sum(1 for row in reports if isinstance(row, dict) and row.get("pacingStatus") == "analyzed")
    reports_with_audio = sum(1 for row in reports if isinstance(row, dict) and row.get("audioStatus") == "analyzed")
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "failedReferenceCount": summary.get("failedReferenceCount"),
        "totalDurationMinutes": summary.get("totalDurationMinutes"),
        "estimatedShotCount": pacing.get("estimatedShotCount"),
        "averageShotLengthSeconds": pacing.get("averageShotLengthSeconds"),
        "medianShotLengthSeconds": pacing.get("medianShotLengthSeconds"),
        "pacingStatus": pacing.get("status"),
        "audioStatus": audio.get("status"),
        "audioMeanVolumeDb": audio.get("meanVolumeDb"),
        "sampleFrameCount": summary.get("sampleFrameCount") or len(samples),
        "referenceReportCount": len(reports),
        "reportsWithAnalysisPath": reports_with_analysis,
        "reportsWithPacing": reports_with_pacing,
        "reportsWithAudio": reports_with_audio,
        "usageAllowed": contract.get("allowed"),
        "usageForbidden": contract.get("forbidden"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def reference_batch_profile_ready(evidence: dict[str, Any]) -> bool:
    count = int(evidence.get("referenceVideoCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_reference_batch_profile"
        and count >= 2
        and int(evidence.get("failedReferenceCount") or 0) == 0
        and int(evidence.get("referenceReportCount") or 0) == count
        and int(evidence.get("reportsWithAnalysisPath") or 0) == count
        and int(evidence.get("reportsWithPacing") or 0) == count
        and int(evidence.get("reportsWithAudio") or 0) == count
        and evidence.get("pacingStatus") == "analyzed"
        and evidence.get("audioStatus") == "analyzed"
        and int(evidence.get("estimatedShotCount") or 0) > 0
        and float(evidence.get("averageShotLengthSeconds") or 0) > 0
        and int(evidence.get("sampleFrameCount") or 0) >= count
        and "non-copying" in str(evidence.get("usageAllowed") or "").lower()
        and "copy" in str(evidence.get("usageForbidden") or "").lower()
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def bgm_sourcing_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "bgm_sourcing" / "bgm_sourcing_brief.json"
    data = load_json(path) or {}
    providers = data.get("providerDirectory") if isinstance(data.get("providerDirectory"), dict) else {}
    rows = data.get("chapterBgmRows") if isinstance(data.get("chapterBgmRows"), list) else []
    sections = data.get("sectionPlan") if isinstance(data.get("sectionPlan"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "verifiedBgmCount": len(data.get("verifiedBgmItems") or []),
        "chapterRows": len(rows),
        "sectionPlanCount": len(sections),
        "providerKeys": sorted(providers),
        "hasMixkit": "Mixkit Music" in providers,
        "hasPixabay": "Pixabay Music" in providers,
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def bgm_sourcing_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") in {"ready_with_verified_bgm", "needs_bgm_selection"}
        and int(evidence.get("chapterRows") or 0) >= 1
        and int(evidence.get("sectionPlanCount") or 0) >= 4
        and evidence.get("hasMixkit") is True
        and evidence.get("hasPixabay") is True
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def bgm_selection_package_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "bgm_selection_package" / "bgm_selection_package.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    selected = data.get("selectedMaterializedBeds") if isinstance(data.get("selectedMaterializedBeds"), list) else []
    candidates = data.get("candidateRows") if isinstance(data.get("candidateRows"), list) else []
    commands = data.get("commands") if isinstance(data.get("commands"), dict) else {}
    verified_selected = 0
    selected_referenced = 0
    selected_covering = 0
    for row in selected:
        if not isinstance(row, dict):
            continue
        if row.get("localPathExists") and row.get("licenseUrlPresent"):
            verified_selected += 1
        if row.get("referencedByBlueprint"):
            selected_referenced += 1
        if row.get("coversTargetDuration"):
            selected_covering += 1
    candidate_decision_fields = {
        "selectedForFinalBed",
        "selectionRole",
        "approvedAssetTitle",
        "approvedAssetUrl",
        "approvedLicenseUrl",
        "approvedLocalPath",
        "durationSeconds",
        "loopOrCrossfadePlan",
        "attributionRequired",
        "attributionText",
        "contentIdRiskChecked",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    candidates_with_decision_fields = 0
    for row in candidates:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if candidate_decision_fields.issubset(set(decision)):
            candidates_with_decision_fields += 1
    build_command = commands.get("buildBgmBed") if isinstance(commands.get("buildBgmBed"), list) else []
    next_audit = commands.get("nextAudit") if isinstance(commands.get("nextAudit"), list) else []
    track_manifest = Path(str(summary.get("trackManifestForBuildBed") or ""))
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "targetDurationSeconds": summary.get("targetDurationSeconds"),
        "candidateCount": summary.get("candidateCount"),
        "materializedBedCount": summary.get("materializedBedCount"),
        "verifiedMaterializedBedCount": summary.get("verifiedMaterializedBedCount"),
        "readySourceTrackCount": summary.get("readySourceTrackCount"),
        "blueprintBgmAssetCount": summary.get("blueprintBgmAssetCount"),
        "bgmCueCount": summary.get("bgmCueCount"),
        "sectionPlanCount": summary.get("sectionPlanCount"),
        "chapterBgmRowCount": summary.get("chapterBgmRowCount"),
        "trackManifestForBuildBed": summary.get("trackManifestForBuildBed"),
        "trackManifestForBuildBedExists": track_manifest.exists() if summary.get("trackManifestForBuildBed") else False,
        "buildCommandAvailable": summary.get("buildCommandAvailable"),
        "verifiedSelectedCount": verified_selected,
        "selectedReferencedCount": selected_referenced,
        "selectedCoveringCount": selected_covering,
        "candidatesWithDecisionFields": candidates_with_decision_fields,
        "buildCommandUsesBuildBgmBed": any("build_bgm_bed.py" in str(item) for item in build_command),
        "nextAuditUsesBgmContract": any("audit_bgm_audio_contract.py" in str(item) for item in next_audit),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "writesResolve": policy.get("writesResolve"),
        "queuesRender": policy.get("queuesRender"),
        "modifiesSourceFootage": policy.get("modifiesSourceFootage"),
        "requiresExactTrackUrlBeforeDownload": policy.get("requiresExactTrackUrlBeforeDownload"),
        "requiresLicenseUrlBeforeUse": policy.get("requiresLicenseUrlBeforeUse"),
        "requiresLocalPathBeforeBuild": policy.get("requiresLocalPathBeforeBuild"),
        "requiresAudibleBgmAuditAfterRender": policy.get("requiresAudibleBgmAuditAfterRender"),
        "blockers": data.get("blockers") or [],
    }


def bgm_selection_package_ready(evidence: dict[str, Any]) -> bool:
    candidates = int(evidence.get("candidateCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_materialized_bgm_selection_package"
        and candidates >= 1
        and int(evidence.get("materializedBedCount") or 0) >= 1
        and int(evidence.get("verifiedMaterializedBedCount") or 0) >= 1
        and int(evidence.get("readySourceTrackCount") or 0) >= 1
        and int(evidence.get("blueprintBgmAssetCount") or 0) >= 1
        and int(evidence.get("bgmCueCount") or 0) >= 1
        and int(evidence.get("sectionPlanCount") or 0) >= 4
        and int(evidence.get("chapterBgmRowCount") or 0) >= 1
        and evidence.get("trackManifestForBuildBedExists") is True
        and evidence.get("buildCommandAvailable") is True
        and int(evidence.get("verifiedSelectedCount") or 0) >= 1
        and int(evidence.get("selectedReferencedCount") or 0) >= 1
        and int(evidence.get("selectedCoveringCount") or 0) >= 1
        and int(evidence.get("candidatesWithDecisionFields") or 0) == candidates
        and evidence.get("buildCommandUsesBuildBgmBed") is True
        and evidence.get("nextAuditUsesBgmContract") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("requiresExactTrackUrlBeforeDownload") is True
        and evidence.get("requiresLicenseUrlBeforeUse") is True
        and evidence.get("requiresLocalPathBeforeBuild") is True
        and evidence.get("requiresAudibleBgmAuditAfterRender") is True
        and not evidence.get("blockers")
    )


def bgm_phrase_blueprint_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    rows = data.get("materializedRows") if isinstance(data.get("materializedRows"), list) else []
    candidate_path = Path(str(outputs.get("candidateBlueprint") or package_dir / "bgm_phrase_blueprint" / "resolve_timeline_blueprint_bgm_phrase.json"))
    candidate = load_json(candidate_path) or {}
    phrase_candidates = candidate.get("bgmPhraseCandidates") if isinstance(candidate.get("bgmPhraseCandidates"), list) else []
    clips = candidate.get("clips") if isinstance(candidate.get("clips"), list) else []
    transitions = candidate.get("transitions") if isinstance(candidate.get("transitions"), list) else []
    markers = [
        marker for marker in candidate.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "bgm_phrase_candidate_marker"
    ] if isinstance(candidate.get("timelineMarkers"), list) else []
    decision_fields = {
        "approveCandidateBlueprint",
        "approvedBgmPhraseRows",
        "selectedBgmBed",
        "resolveImplementation",
        "preflightEvidence",
        "timelineReadbackEvidence",
        "audioReadbackEvidence",
        "frameSampleEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    rows_materialized = 0
    rows_with_decisions = 0
    rows_bgm_only = 0
    rows_with_bed = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "materialized":
            rows_materialized += 1
        if row.get("audioTreatment") == "bgm_only_no_camera_voice":
            rows_bgm_only += 1
        if row.get("selectedBgmBedLocal") and row.get("selectedBgmBedLicense"):
            rows_with_bed += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decisions += 1
    candidate_rows_with_decisions = 0
    candidate_rows_bgm_only = 0
    candidate_rows_with_bed = 0
    for row in phrase_candidates:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            candidate_rows_with_decisions += 1
        if row.get("audioTreatment") == "bgm_only_no_camera_voice":
            candidate_rows_bgm_only += 1
        bed = row.get("selectedBgmBed") if isinstance(row.get("selectedBgmBed"), dict) else {}
        if bed.get("localPath") and bed.get("licenseUrl"):
            candidate_rows_with_bed += 1
    clip_annotation_count = sum(len(clip.get("bgmPhraseCandidates") or []) for clip in clips if isinstance(clip, dict) and isinstance(clip.get("bgmPhraseCandidates"), list))
    transition_cue_count = sum(1 for transition in transitions if isinstance(transition, dict) and isinstance(transition.get("bgmPhraseCandidate"), dict))
    audio_plan = candidate.get("audioPlan") if isinstance(candidate.get("audioPlan"), dict) else {}
    bgm_map = audio_plan.get("bgmPhraseMap") if isinstance(audio_plan.get("bgmPhraseMap"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "candidateBlueprint": str(candidate_path),
        "candidateBlueprintExists": candidate_path.exists(),
        "candidateHasBgmPhrasePlan": isinstance(candidate.get("bgmPhraseBlueprintPlan"), dict),
        "candidateHasBgmPhraseMap": isinstance(bgm_map, dict) and isinstance(bgm_map.get("phraseRows"), list),
        "selectedBgmBedCount": summary.get("selectedBgmBedCount"),
        "phraseRowCount": summary.get("phraseRowCount"),
        "sectionRowCount": summary.get("sectionRowCount"),
        "materializedPhraseCount": summary.get("materializedPhraseCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "candidateTransitionCount": summary.get("candidateTransitionCount"),
        "transitionCueCount": summary.get("transitionCueCount"),
        "transitionsWithPhraseCue": summary.get("transitionsWithPhraseCue"),
        "clipAnnotationCount": summary.get("clipAnnotationCount"),
        "markerCount": summary.get("markerCount"),
        "sourceAudioRiskCount": summary.get("sourceAudioRiskCount"),
        "audioScenePolicyStatus": summary.get("audioScenePolicyStatus"),
        "rowCount": len(rows),
        "candidatePhraseRows": len(phrase_candidates),
        "rowsMaterializedByRow": rows_materialized,
        "rowsWithDecisionFieldsByRow": rows_with_decisions,
        "rowsBgmOnly": rows_bgm_only,
        "rowsWithSelectedBed": rows_with_bed,
        "candidateRowsWithDecisionFields": candidate_rows_with_decisions,
        "candidateRowsBgmOnly": candidate_rows_bgm_only,
        "candidateRowsWithSelectedBed": candidate_rows_with_bed,
        "candidateMarkers": len(markers),
        "candidateClipAnnotationCount": clip_annotation_count,
        "candidateTransitionCueCount": transition_cue_count,
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "mutatesActiveBlueprintByDefault": safety.get("mutatesActiveBlueprintByDefault"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def bgm_phrase_blueprint_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("phraseRowCount") or 0)
    transition_count = int(evidence.get("candidateTransitionCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_bgm_phrase_blueprint"
        and evidence.get("candidateBlueprintExists")
        and evidence.get("candidateHasBgmPhrasePlan")
        and evidence.get("candidateHasBgmPhraseMap")
        and int(evidence.get("selectedBgmBedCount") or 0) >= 1
        and row_count >= 4
        and int(evidence.get("sectionRowCount") or 0) >= 3
        and int(evidence.get("materializedPhraseCount") or 0) == row_count
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("candidatePhraseRows") or 0) == row_count
        and int(evidence.get("rowsMaterializedByRow") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsBgmOnly") or 0) == row_count
        and int(evidence.get("rowsWithSelectedBed") or 0) == row_count
        and int(evidence.get("candidateRowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("candidateRowsBgmOnly") or 0) == row_count
        and int(evidence.get("candidateRowsWithSelectedBed") or 0) == row_count
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("sourceAudioRiskCount") or 0) == 0
        and int(evidence.get("transitionCueCount") or 0) == int(evidence.get("candidateTransitionCueCount") or 0)
        and int(evidence.get("transitionsWithPhraseCue") or 0) == int(evidence.get("candidateTransitionCueCount") or 0)
        and (transition_count == 0 or int(evidence.get("candidateTransitionCueCount") or 0) == transition_count)
        and int(evidence.get("markerCount") or 0) == row_count
        and int(evidence.get("candidateMarkers") or 0) == row_count
        and int(evidence.get("clipAnnotationCount") or 0) >= row_count
        and int(evidence.get("candidateClipAnnotationCount") or 0) >= row_count
        and evidence.get("activeBlueprintUpdated") is False
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("mutatesActiveBlueprintByDefault") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def transition_bridge_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("boundaryRows") if isinstance(data.get("boundaryRows"), list) else []
    sections = data.get("sectionPlan") if isinstance(data.get("sectionPlan"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    decision_fields = {"selectedLocalClips", "selectedStockAssets", "licenseUrls", "resolveRole", "audioTreatment", "approvedBy", "approvedAt"}
    rows_with_search = 0
    rows_with_decision_fields = 0
    rows_with_evidence = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("localFootageSearchHints") and row.get("stockFallbackQueries"):
            rows_with_search += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        if row.get("existingBridgeEvidence"):
            rows_with_evidence += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "chapterCount": summary.get("chapterCount"),
        "boundaryRowCount": summary.get("boundaryRowCount"),
        "boundariesWithEvidence": summary.get("boundariesWithEvidence"),
        "missingBoundaryCount": summary.get("missingBoundaryCount"),
        "existingTransitionPlanCount": summary.get("existingTransitionPlanCount"),
        "existingBridgeClipCount": summary.get("existingBridgeClipCount"),
        "sectionPlanCount": len(sections),
        "rowsWithSearch": rows_with_search,
        "rowsWithDecisionFields": rows_with_decision_fields,
        "rowsWithEvidence": rows_with_evidence,
        "localFootageFirst": policy.get("localFootageFirst"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "audioMode": policy.get("audioMode"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def transition_bridge_plan_ready(evidence: dict[str, Any]) -> bool:
    boundary_rows = int(evidence.get("boundaryRowCount") or 0)
    chapter_count = int(evidence.get("chapterCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") in {"ready_with_bridge_evidence", "ready_no_interchapter_boundaries"}
        and chapter_count >= 1
        and boundary_rows >= max(0, chapter_count - 1)
        and int(evidence.get("missingBoundaryCount") or 0) == 0
        and int(evidence.get("rowsWithSearch") or 0) == boundary_rows
        and int(evidence.get("rowsWithDecisionFields") or 0) == boundary_rows
        and int(evidence.get("rowsWithEvidence") or 0) == boundary_rows
        and int(evidence.get("sectionPlanCount") or 0) >= 3
        and evidence.get("localFootageFirst") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("audioMode") == "bgm_only_no_camera_voice"
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def caption_story_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "caption_story_plan" / "caption_story_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    rows = data.get("chapterRows") if isinstance(data.get("chapterRows"), list) else []
    rubric = data.get("writingRubric") if isinstance(data.get("writingRubric"), dict) else {}
    title_policy = data.get("titleZonePolicy") if isinstance(data.get("titleZonePolicy"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    text_export = Path(str(outputs.get("textOnlyNarrationExport") or "")) if outputs.get("textOnlyNarrationExport") else None
    decision_fields = {"approvedSubtitleSource", "approvedTextOnlyNarrationPath", "approvedSrtPath", "renderMode", "titleZoneSuppressionVerified", "approvedBy", "approvedAt"}
    rows_with_functions = 0
    rows_with_decision_fields = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("captionFunctions") and int(row.get("targetCueCount") or 0) > 0:
            rows_with_functions += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "subtitleCueCount": summary.get("subtitleCueCount"),
        "targetCueCount": summary.get("targetCueCount"),
        "cuesPerMinute": summary.get("cuesPerMinute"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "rowsMeetingTarget": summary.get("rowsMeetingTarget"),
        "maxGapSeconds": summary.get("maxGapSeconds"),
        "titleZoneCount": summary.get("titleZoneCount"),
        "textOnlyNarrationExport": str(text_export) if text_export else None,
        "textOnlyNarrationExportExists": bool(text_export and text_export.exists()),
        "voiceoverAudioAllowedByDefault": policy.get("voiceoverAudioAllowedByDefault"),
        "outputTxtRequired": policy.get("outputTxtRequired"),
        "srtRequired": policy.get("srtRequired"),
        "renderedSubtitlePreferred": policy.get("renderedSubtitlePreferred"),
        "titleZoneSuppressionRequired": policy.get("titleZoneSuppressionRequired"),
        "audioMode": policy.get("audioMode"),
        "titleZonePolicyMode": title_policy.get("mode"),
        "rowsWithFunctions": rows_with_functions,
        "rowsWithDecisionFields": rows_with_decision_fields,
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def caption_story_plan_ready(evidence: dict[str, Any]) -> bool:
    chapter_rows = int(evidence.get("chapterRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_dense_caption_plan"
        and int(evidence.get("subtitleCueCount") or 0) >= int(evidence.get("targetCueCount") or 1)
        and float(evidence.get("cuesPerMinute") or 0) >= 4.0
        and chapter_rows >= 1
        and int(evidence.get("rowsMeetingTarget") or 0) == chapter_rows
        and float(evidence.get("maxGapSeconds") or 0) <= 75.0
        and int(evidence.get("titleZoneCount") or 0) >= 1
        and evidence.get("textOnlyNarrationExportExists") is True
        and evidence.get("voiceoverAudioAllowedByDefault") is False
        and evidence.get("outputTxtRequired") is True
        and evidence.get("srtRequired") is True
        and evidence.get("renderedSubtitlePreferred") is True
        and evidence.get("titleZoneSuppressionRequired") is True
        and evidence.get("audioMode") == "bgm_only_no_camera_voice"
        and int(evidence.get("rowsWithFunctions") or 0) == chapter_rows
        and int(evidence.get("rowsWithDecisionFields") or 0) == chapter_rows
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def title_typography_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "title_typography_plan" / "title_typography_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    font = data.get("fontEvidence") if isinstance(data.get("fontEvidence"), dict) else {}
    title_zone = data.get("titleZoneEvidence") if isinstance(data.get("titleZoneEvidence"), dict) else {}
    stack = data.get("stackEvidence") if isinstance(data.get("stackEvidence"), dict) else {}
    rows = data.get("titleRows") if isinstance(data.get("titleRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    decision_fields = {"approvedTitleText", "approvedFontFamily", "approvedBackgroundSource", "safeZoneChecked", "noStackedTextChecked", "titleZoneSubtitleSuppressionChecked", "approvedBy", "approvedAt"}
    rows_with_decision_fields = 0
    rows_clean = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        if (
            row.get("cleanTitlePass")
            and row.get("subtitlePolicyPass")
            and row.get("forbiddenTextPass")
            and row.get("segmentExists")
            and row.get("segmentIsVideo")
        ):
            rows_clean += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "titleRowCount": summary.get("titleRowCount"),
        "cleanRowCount": summary.get("cleanRowCount"),
        "openingRowCount": summary.get("openingRowCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "endingRowCount": summary.get("endingRowCount"),
        "fontVerified": summary.get("fontVerified"),
        "titleZoneMode": summary.get("titleZoneMode"),
        "titleZoneCount": summary.get("titleZoneCount"),
        "titleContractStatus": summary.get("titleContractStatus"),
        "stackExtraTextLayerCount": summary.get("stackExtraTextLayerCount"),
        "stackSubtitleOverlayCount": summary.get("stackSubtitleOverlayCount"),
        "manifestFontExists": font.get("manifestFontExists"),
        "verifiedFontItemCount": font.get("verifiedFontItemCount"),
        "titleZoneEvidenceMode": title_zone.get("mode"),
        "stackCheckStatus": stack.get("stackCheckStatus"),
        "rowsWithDecisionFields": rows_with_decision_fields,
        "rowsCleanByRowEvidence": rows_clean,
        "hasOpeningTitlePolicy": bool(policy.get("openingTitlePolicy")),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def title_typography_plan_ready(evidence: dict[str, Any]) -> bool:
    title_rows = int(evidence.get("titleRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_clean_title_typography_plan"
        and title_rows >= 3
        and int(evidence.get("cleanRowCount") or 0) == title_rows
        and int(evidence.get("rowsCleanByRowEvidence") or 0) == title_rows
        and int(evidence.get("openingRowCount") or 0) == 1
        and int(evidence.get("chapterRowCount") or 0) >= 1
        and int(evidence.get("endingRowCount") or 0) >= 1
        and evidence.get("fontVerified") is True
        and evidence.get("manifestFontExists") is True
        and int(evidence.get("verifiedFontItemCount") or 0) >= 1
        and evidence.get("titleZoneMode") == "avoid_title_zones"
        and int(evidence.get("titleZoneCount") or 0) >= title_rows
        and evidence.get("titleContractStatus") == "passed"
        and int(evidence.get("stackExtraTextLayerCount") or 0) == 0
        and int(evidence.get("stackSubtitleOverlayCount") or 0) == 0
        and int(evidence.get("rowsWithDecisionFields") or 0) == title_rows
        and evidence.get("hasOpeningTitlePolicy") is True
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def cover_title_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "cover_title_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualManifestExists": inputs.get("visualManifestExists"),
        "mainTitle": summary.get("mainTitle"),
        "mainTitleUnitCount": summary.get("mainTitleUnitCount"),
        "secondaryTitle": summary.get("secondaryTitle"),
        "secondaryTitlePresent": summary.get("secondaryTitlePresent"),
        "backgroundVideoReady": summary.get("backgroundVideoReady"),
        "backgroundRecognitionHint": summary.get("backgroundRecognitionHint"),
        "clean16x9Deliverable": summary.get("clean16x9Deliverable"),
        "forbiddenHitCount": summary.get("forbiddenHitCount"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def cover_title_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("visualManifestExists") is True
        and bool(str(evidence.get("mainTitle") or "").strip())
        and 1 <= int(evidence.get("mainTitleUnitCount") or 0) <= 8
        and evidence.get("secondaryTitlePresent") is True
        and evidence.get("backgroundVideoReady") is True
        and evidence.get("backgroundRecognitionHint") is True
        and evidence.get("clean16x9Deliverable") is True
        and int(evidence.get("forbiddenHitCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def title_visual_proof_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "title_visual_proof_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualManifestExists": inputs.get("visualManifestExists"),
        "titleVisualRowCount": summary.get("titleVisualRowCount"),
        "passedTitleVisualRowCount": summary.get("passedTitleVisualRowCount"),
        "blockedTitleVisualRowCount": summary.get("blockedTitleVisualRowCount"),
        "openingRowCount": summary.get("openingRowCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "endingRowCount": summary.get("endingRowCount"),
        "rowsWithPackageLocalVideo": summary.get("rowsWithPackageLocalVideo"),
        "rowsWithProbeVideo": summary.get("rowsWithProbeVideo"),
        "rowsWithThreePassedFrames": summary.get("rowsWithThreePassedFrames"),
        "rowsWithOverlayEvidence": summary.get("rowsWithOverlayEvidence"),
        "openingForbiddenHitCount": summary.get("openingForbiddenHitCount"),
        "titleBridgeStatus": summary.get("titleBridgeStatus"),
        "coverTitleStatus": summary.get("coverTitleStatus"),
        "ffmpegAvailable": summary.get("ffmpegAvailable"),
        "ffprobeAvailable": summary.get("ffprobeAvailable"),
        "extractedFrames": summary.get("extractedFrames"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def title_visual_proof_contract_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("titleVisualRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("visualManifestExists") is True
        and row_count >= 3
        and int(evidence.get("passedTitleVisualRowCount") or 0) == row_count
        and int(evidence.get("blockedTitleVisualRowCount") or 0) == 0
        and int(evidence.get("openingRowCount") or 0) == 1
        and int(evidence.get("chapterRowCount") or 0) >= 1
        and int(evidence.get("endingRowCount") or 0) >= 1
        and int(evidence.get("rowsWithPackageLocalVideo") or 0) == row_count
        and int(evidence.get("rowsWithProbeVideo") or 0) == row_count
        and int(evidence.get("rowsWithThreePassedFrames") or 0) == row_count
        and int(evidence.get("openingForbiddenHitCount") or 0) == 0
        and evidence.get("titleBridgeStatus") == "passed"
        and evidence.get("coverTitleStatus") == "passed"
        and evidence.get("ffmpegAvailable") is True
        and evidence.get("ffprobeAvailable") is True
        and evidence.get("extractedFrames") is True
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def visual_establishing_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "visual_establishing_plan" / "visual_establishing_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("establishingRows") if isinstance(data.get("establishingRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    providers = data.get("providerDirectory") if isinstance(data.get("providerDirectory"), dict) else {}
    decision_fields = {
        "selectedLocalClips",
        "selectedStockAssets",
        "selectedAerialAssets",
        "selectedAssetUrls",
        "licenseUrls",
        "localPathsAfterDownload",
        "resolveRole",
        "audioTreatment",
        "approvedBy",
        "approvedAt",
    }
    rows_with_search = 0
    rows_with_decision_fields = 0
    rows_with_evidence = 0
    rows_with_title_evidence = 0
    role_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "")
        role_counts[role] = role_counts.get(role, 0) + 1
        if row.get("localFootageSearchHints") and row.get("stockAerialFallbackQueries") and row.get("famousPlaceHints"):
            rows_with_search += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        if row.get("existingEstablishingEvidence"):
            rows_with_evidence += 1
        if row.get("titleTypographyEvidence"):
            rows_with_title_evidence += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "chapterCount": summary.get("chapterCount"),
        "establishingRowCount": summary.get("establishingRowCount"),
        "rowsWithEvidence": summary.get("rowsWithEvidence"),
        "missingEstablishingCount": summary.get("missingEstablishingCount"),
        "rowsWithTitleTypographyEvidence": summary.get("rowsWithTitleTypographyEvidence"),
        "verifiedAerialCount": summary.get("verifiedAerialCount"),
        "stockAerialClosureStatus": summary.get("stockAerialClosureStatus"),
        "stockAerialUnresolvedPlaceholderCount": summary.get("stockAerialUnresolvedPlaceholderCount"),
        "titleTypographyStatus": summary.get("titleTypographyStatus"),
        "rowCount": len(rows),
        "rowsWithSearch": rows_with_search,
        "rowsWithDecisionFields": rows_with_decision_fields,
        "rowsWithEvidenceByRow": rows_with_evidence,
        "rowsWithTitleEvidenceByRow": rows_with_title_evidence,
        "roleCounts": role_counts,
        "providerKeys": sorted(providers),
        "hasMixkit": "Mixkit Video" in providers,
        "hasPixabay": "Pixabay Video" in providers,
        "hasPexels": "Pexels Video" in providers,
        "localFootageFirst": policy.get("localFootageFirst"),
        "licensedStockOnlyWhenLocalMissing": policy.get("licensedStockOnlyWhenLocalMissing"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "audioMode": policy.get("audioMode"),
        "noBlackSlateFallback": policy.get("noBlackSlateFallback"),
        "noFabricatedDroneClaim": policy.get("noFabricatedDroneClaim"),
        "noPreviousTripDefaults": policy.get("noPreviousTripDefaults"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def visual_establishing_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("establishingRowCount") or 0)
    chapter_count = int(evidence.get("chapterCount") or 0)
    role_counts = evidence.get("roleCounts") if isinstance(evidence.get("roleCounts"), dict) else {}
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_establishing_evidence"
        and chapter_count >= 1
        and row_count >= chapter_count + 2
        and int(evidence.get("missingEstablishingCount") or 0) == 0
        and int(evidence.get("rowsWithSearch") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithEvidenceByRow") or 0) == row_count
        and int(evidence.get("rowsWithTitleEvidenceByRow") or 0) == row_count
        and int(evidence.get("verifiedAerialCount") or 0) >= 1
        and role_counts.get("opening_city_establishing", 0) >= 1
        and role_counts.get("chapter_establishing", 0) >= chapter_count
        and role_counts.get("ending_city_establishing", 0) >= 1
        and evidence.get("stockAerialClosureStatus") in {"passed", "passed_with_warnings", None}
        and int(evidence.get("stockAerialUnresolvedPlaceholderCount") or 0) == 0
        and evidence.get("titleTypographyStatus") in {"ready_with_clean_title_typography_plan", None}
        and evidence.get("hasMixkit") is True
        and evidence.get("hasPixabay") is True
        and evidence.get("hasPexels") is True
        and evidence.get("localFootageFirst") is True
        and evidence.get("licensedStockOnlyWhenLocalMissing") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("audioMode") == "bgm_only_no_camera_voice"
        and evidence.get("noBlackSlateFallback") is True
        and evidence.get("noFabricatedDroneClaim") is True
        and evidence.get("noPreviousTripDefaults") is True
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def effect_motion_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "effect_motion_plan" / "effect_motion_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("effectRows") if isinstance(data.get("effectRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    decision_fields = {
        "selectedEffectType",
        "durationFrames",
        "resolveImplementation",
        "motionDirection",
        "intensity",
        "audioTreatment",
        "titleZoneChecked",
        "appliedInResolve",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_source = 0
    rows_with_decision_fields = 0
    rows_with_recommendation = 0
    row_type_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_type = str(row.get("rowType") or "")
        row_type_counts[row_type] = row_type_counts.get(row_type, 0) + 1
        if row.get("status") == "has_source_evidence":
            rows_with_source += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        recommendation = row.get("recommendedMotion") if isinstance(row.get("recommendedMotion"), dict) else {}
        if recommendation.get("style") and recommendation.get("intensity") == "subtle":
            rows_with_recommendation += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "effectPlanCount": summary.get("effectPlanCount"),
        "effectRowCount": summary.get("effectRowCount"),
        "rowsWithSourceEvidence": summary.get("rowsWithSourceEvidence"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "forbiddenEffectHitCount": summary.get("forbiddenEffectHitCount"),
        "titleMotionRowCount": summary.get("titleMotionRowCount"),
        "transitionMotionRowCount": summary.get("transitionMotionRowCount"),
        "rowCount": len(rows),
        "rowsWithSourceByRow": rows_with_source,
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithRecommendation": rows_with_recommendation,
        "rowTypeCounts": row_type_counts,
        "restrainedEffectsOnly": policy.get("restrainedEffectsOnly"),
        "noTemplateHeavyTransitions": policy.get("noTemplateHeavyTransitions"),
        "motivatedWhipOrRotationAllowed": policy.get("motivatedWhipOrRotationAllowed"),
        "noBlackCardFallback": policy.get("noBlackCardFallback"),
        "titleZoneCheckedBeforeMotion": policy.get("titleZoneCheckedBeforeMotion"),
        "audioMode": policy.get("audioMode"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "writesResolve": policy.get("writesResolve"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def effect_motion_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("effectRowCount") or 0)
    row_type_counts = evidence.get("rowTypeCounts") if isinstance(evidence.get("rowTypeCounts"), dict) else {}
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_restrained_effect_plan"
        and int(evidence.get("effectPlanCount") or 0) >= 2
        and row_count >= 3
        and int(evidence.get("rowsWithSourceEvidence") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithSourceByRow") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithRecommendation") or 0) == row_count
        and int(evidence.get("forbiddenEffectHitCount") or 0) == 0
        and int(evidence.get("titleMotionRowCount") or 0) >= 3
        and int(evidence.get("transitionMotionRowCount") or 0) >= 1
        and row_type_counts.get("opening_title_reveal", 0) >= 1
        and row_type_counts.get("ending_title_reveal", 0) >= 1
        and row_type_counts.get("transition_motion_bridge", 0) >= 1
        and evidence.get("restrainedEffectsOnly") is True
        and evidence.get("motivatedWhipOrRotationAllowed") is True
        and evidence.get("noTemplateHeavyTransitions") is True
        and evidence.get("noBlackCardFallback") is True
        and evidence.get("titleZoneCheckedBeforeMotion") is True
        and evidence.get("audioMode") == "bgm_only_no_camera_voice"
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def effect_motion_blueprint_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    rows = data.get("materializedRows") if isinstance(data.get("materializedRows"), list) else []
    candidate_path = Path(str(outputs.get("candidateBlueprint") or package_dir / "effect_motion_blueprint" / "resolve_timeline_blueprint_effect_motion.json"))
    candidate = load_json(candidate_path) or {}
    candidates = candidate.get("effectMotionCandidates") if isinstance(candidate.get("effectMotionCandidates"), list) else []
    clips = candidate.get("clips") if isinstance(candidate.get("clips"), list) else []
    markers = [
        marker for marker in candidate.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "effect_motion_candidate_marker"
    ] if isinstance(candidate.get("timelineMarkers"), list) else []
    decision_fields = {
        "approveCandidateBlueprint",
        "approvedEffectRows",
        "resolveImplementation",
        "preflightEvidence",
        "timelineReadbackEvidence",
        "frameSampleEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    rows_materialized = 0
    rows_with_decisions = 0
    rows_with_clip_match = 0
    rows_title_safe = 0
    rows_motion_safe = 0
    rows_without_forbidden = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "materialized":
            rows_materialized += 1
        if int(row.get("matchedClipCount") or 0) > 0:
            rows_with_clip_match += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decisions += 1
        if row.get("titleZoneSafe") is True:
            rows_title_safe += 1
        if row.get("motionEvidenceSatisfied") is True:
            rows_motion_safe += 1
        if not row.get("forbiddenEffectHits"):
            rows_without_forbidden += 1
    clip_annotation_count = sum(len(clip.get("effectMotionCandidates") or []) for clip in clips if isinstance(clip, dict) and isinstance(clip.get("effectMotionCandidates"), list))
    candidate_decision_count = 0
    candidate_bgm_only_count = 0
    candidate_without_forbidden = 0
    for item in candidates:
        if not isinstance(item, dict):
            continue
        decision = item.get("decision") if isinstance(item.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            candidate_decision_count += 1
        if item.get("audioTreatment") == "bgm_only_no_camera_voice":
            candidate_bgm_only_count += 1
        if not item.get("forbiddenEffectHits"):
            candidate_without_forbidden += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "candidateBlueprint": str(candidate_path),
        "candidateBlueprintExists": candidate_path.exists(),
        "candidateHasEffectMotionPlan": isinstance(candidate.get("effectMotionBlueprintPlan"), dict),
        "effectRowCount": summary.get("effectRowCount"),
        "materializedEffectCount": summary.get("materializedEffectCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsWithClipMatch": summary.get("rowsWithClipMatch"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "titleMotionRowCount": summary.get("titleMotionRowCount"),
        "transitionMotionRowCount": summary.get("transitionMotionRowCount"),
        "motionEffectRowCount": summary.get("motionEffectRowCount"),
        "motionEffectRowsWithEvidence": summary.get("motionEffectRowsWithEvidence"),
        "forbiddenEffectHitCount": summary.get("forbiddenEffectHitCount"),
        "candidateEffectMotionCount": summary.get("candidateEffectMotionCount"),
        "rowCount": len(rows),
        "rowsMaterializedByRow": rows_materialized,
        "rowsWithDecisionFieldsByRow": rows_with_decisions,
        "rowsWithClipMatchByRow": rows_with_clip_match,
        "rowsTitleZoneSafe": rows_title_safe,
        "rowsMotionSafe": rows_motion_safe,
        "rowsWithoutForbiddenHits": rows_without_forbidden,
        "candidateEffects": len(candidates),
        "candidateMarkers": len(markers),
        "clipAnnotationCount": clip_annotation_count,
        "candidateRowsWithDecisionFields": candidate_decision_count,
        "candidateRowsBgmOnly": candidate_bgm_only_count,
        "candidateRowsWithoutForbiddenHits": candidate_without_forbidden,
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "mutatesActiveBlueprintByDefault": safety.get("mutatesActiveBlueprintByDefault"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def effect_motion_blueprint_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("effectRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_effect_motion_blueprint"
        and evidence.get("candidateBlueprintExists")
        and evidence.get("candidateHasEffectMotionPlan")
        and row_count >= 3
        and int(evidence.get("materializedEffectCount") or 0) == row_count
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsMaterializedByRow") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithClipMatch") or 0) == row_count
        and int(evidence.get("rowsWithClipMatchByRow") or 0) == row_count
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("titleMotionRowCount") or 0) >= 3
        and int(evidence.get("transitionMotionRowCount") or 0) >= 1
        and int(evidence.get("motionEffectRowsWithEvidence") or 0) == int(evidence.get("motionEffectRowCount") or 0)
        and int(evidence.get("forbiddenEffectHitCount") or 0) == 0
        and int(evidence.get("rowsTitleZoneSafe") or 0) == row_count
        and int(evidence.get("rowsMotionSafe") or 0) == row_count
        and int(evidence.get("rowsWithoutForbiddenHits") or 0) == row_count
        and int(evidence.get("candidateEffectMotionCount") or 0) == row_count
        and int(evidence.get("candidateEffects") or 0) == row_count
        and int(evidence.get("candidateMarkers") or 0) == row_count
        and int(evidence.get("clipAnnotationCount") or 0) >= row_count
        and int(evidence.get("candidateRowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("candidateRowsBgmOnly") or 0) == row_count
        and int(evidence.get("candidateRowsWithoutForbiddenHits") or 0) == row_count
        and evidence.get("activeBlueprintUpdated") is False
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("mutatesActiveBlueprintByDefault") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def feedback_regression_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "feedback_regression_plan" / "feedback_regression_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    commands = data.get("commands") if isinstance(data.get("commands"), dict) else {}
    probes = data.get("probes") if isinstance(data.get("probes"), list) else []
    risk_types = set(str(item) for item in summary.get("riskTypes") or [])
    probe_ids = [str(row.get("id") or "") for row in probes if isinstance(row, dict)]
    audio_policy_cmd = " ".join(str(item) for item in commands.get("preRenderAudioPolicyCommand") or [])
    feedback_cmd = " ".join(str(item) for item in commands.get("postRenderFeedbackAuditCommand") or [])
    final_qa_cmd = " ".join(str(item) for item in commands.get("finalQaSuiteCommand") or [])
    required_stages = policy.get("requiredStages") if isinstance(policy.get("requiredStages"), list) else []
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "probeCount": summary.get("probeCount"),
        "openingProbeCount": summary.get("openingProbeCount"),
        "sevenMinuteProbeCount": summary.get("sevenMinuteProbeCount"),
        "audioPolicyProbeCount": summary.get("audioPolicyProbeCount"),
        "finalFeedbackAuditProbeCount": summary.get("finalFeedbackAuditProbeCount"),
        "feedbackTimestampsCsv": summary.get("feedbackTimestampsCsv"),
        "audioPolicyFeedbackTimestampsCsv": summary.get("audioPolicyFeedbackTimestampsCsv"),
        "riskTypes": sorted(risk_types),
        "probeIds": probe_ids,
        "hasOpeningTitleProbe": "opening_title" in probe_ids,
        "hasSevenMinuteVerticalProbe": "reported_vertical_clip_7_04" in probe_ids,
        "hasSevenMinuteVoiceProbe": "reported_voice_at_7_04" in probe_ids,
        "hasOpeningBgmProbe": "opening_bgm_no_voice" in probe_ids,
        "audioPolicyCommandIncludesPlan": "prepare_audio_scene_policy_plan.py" in audio_policy_cmd and "--feedback-timestamps" in audio_policy_cmd,
        "feedbackAuditCommandIncludesPlan": "audit_feedback_regressions.py" in feedback_cmd and "--feedback-timestamps" in feedback_cmd and "--include-title-points" in feedback_cmd,
        "finalQaCommandIncludesPlan": "run_final_qa_suite.py" in final_qa_cmd and "--feedback-timestamps" in final_qa_cmd,
        "requiredStageCount": len(required_stages),
        "writesResolve": policy.get("writesResolve"),
        "queuesRender": policy.get("queuesRender"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "modifiesSourceFootage": policy.get("modifiesSourceFootage"),
    }


def feedback_regression_plan_ready(evidence: dict[str, Any]) -> bool:
    risks = set(evidence.get("riskTypes") or [])
    required_risks = {"title_cleanliness", "visual_orientation", "bgm_voice_leak", "opening_bgm_voice_leak"}
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_feedback_regression_plan"
        and int(evidence.get("probeCount") or 0) >= 4
        and int(evidence.get("openingProbeCount") or 0) >= 1
        and int(evidence.get("sevenMinuteProbeCount") or 0) >= 2
        and int(evidence.get("audioPolicyProbeCount") or 0) >= 2
        and int(evidence.get("finalFeedbackAuditProbeCount") or 0) >= 4
        and required_risks.issubset(risks)
        and evidence.get("hasOpeningTitleProbe") is True
        and evidence.get("hasSevenMinuteVerticalProbe") is True
        and evidence.get("hasSevenMinuteVoiceProbe") is True
        and evidence.get("hasOpeningBgmProbe") is True
        and "opening_title=0" in str(evidence.get("feedbackTimestampsCsv") or "")
        and "reported_vertical_clip=7:04" in str(evidence.get("feedbackTimestampsCsv") or "")
        and "reported_voice_at_7_04=7:04" in str(evidence.get("feedbackTimestampsCsv") or "")
        and evidence.get("audioPolicyCommandIncludesPlan") is True
        and evidence.get("feedbackAuditCommandIncludesPlan") is True
        and evidence.get("finalQaCommandIncludesPlan") is True
        and int(evidence.get("requiredStageCount") or 0) >= 3
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def audio_scene_policy_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("sceneRows") if isinstance(data.get("sceneRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    decision_fields = {
        "muteA1A2SourceAudio",
        "routeBgmToTrack",
        "targetMusicDb",
        "allowIntentionalAmbient",
        "ambientApprovalReason",
        "voiceoverAllowed",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_bgm = 0
    rows_with_decision_fields = 0
    rows_with_source_risks = 0
    rows_with_post_render_evidence = 0
    row_type_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_type = str(row.get("rowType") or "")
        row_type_counts[row_type] = row_type_counts.get(row_type, 0) + 1
        if row.get("bgmCovered") is True:
            rows_with_bgm += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        if row.get("sourceAudioRisks"):
            rows_with_source_risks += 1
        post_render = row.get("postRenderEvidence") if isinstance(row.get("postRenderEvidence"), dict) else {}
        if post_render.get("bgmAudioAuditStatus"):
            rows_with_post_render_evidence += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "sceneWindowCount": summary.get("sceneWindowCount"),
        "bgmCoveredWindowCount": summary.get("bgmCoveredWindowCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "sourceAudioRiskCount": summary.get("sourceAudioRiskCount"),
        "readyBgmCueCount": summary.get("readyBgmCueCount"),
        "voiceoverDisabled": summary.get("voiceoverDisabled"),
        "sourceAudioDisabled": summary.get("sourceAudioDisabled"),
        "policyMode": summary.get("policyMode"),
        "titleWindowCount": summary.get("titleWindowCount"),
        "transitionWindowCount": summary.get("transitionWindowCount"),
        "establishingWindowCount": summary.get("establishingWindowCount"),
        "feedbackWindowCount": summary.get("feedbackWindowCount"),
        "knownFeedbackProbeCount": summary.get("knownFeedbackProbeCount"),
        "rowCount": len(rows),
        "rowsWithBgmByRow": rows_with_bgm,
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithSourceRisksByRow": rows_with_source_risks,
        "rowsWithPostRenderEvidence": rows_with_post_render_evidence,
        "rowTypeCounts": row_type_counts,
        "titleTransitionScenicBgmLed": policy.get("titleTransitionScenicBgmLed"),
        "voiceoverAudioAllowedByDefault": policy.get("voiceoverAudioAllowedByDefault"),
        "sourceCameraVoiceAllowedByDefault": policy.get("sourceCameraVoiceAllowedByDefault"),
        "intentionalAmbientRequiresExplicitApproval": policy.get("intentionalAmbientRequiresExplicitApproval"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "writesResolve": policy.get("writesResolve"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def audio_scene_policy_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("sceneWindowCount") or 0)
    row_type_counts = evidence.get("rowTypeCounts") if isinstance(evidence.get("rowTypeCounts"), dict) else {}
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_bgm_only_scene_policy"
        and row_count >= 8
        and int(evidence.get("bgmCoveredWindowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithBgmByRow") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("sourceAudioRiskCount") or 0) == 0
        and int(evidence.get("rowsWithSourceRisksByRow") or 0) == 0
        and int(evidence.get("readyBgmCueCount") or 0) >= 1
        and evidence.get("voiceoverDisabled") is True
        and evidence.get("sourceAudioDisabled") is True
        and evidence.get("policyMode") == "bgm_only_no_camera_voice"
        and int(evidence.get("titleWindowCount") or 0) >= 3
        and int(evidence.get("transitionWindowCount") or 0) >= 1
        and int(evidence.get("establishingWindowCount") or 0) >= 1
        and int(evidence.get("feedbackWindowCount") or 0) >= 1
        and int(evidence.get("knownFeedbackProbeCount") or 0) >= 1
        and row_type_counts.get("opening_title_audio", 0) >= 1
        and row_type_counts.get("feedback_audio_probe", 0) >= 1
        and evidence.get("titleTransitionScenicBgmLed") is True
        and evidence.get("voiceoverAudioAllowedByDefault") is False
        and evidence.get("sourceCameraVoiceAllowedByDefault") is False
        and evidence.get("intentionalAmbientRequiresExplicitApproval") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def footage_select_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "footage_select_plan" / "footage_select_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("selectionRows") if isinstance(data.get("selectionRows"), list) else []
    chapters = data.get("chapterRows") if isinstance(data.get("chapterRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    decision_fields = {
        "approvedUse",
        "approvedTier",
        "targetDurationSeconds",
        "trimStartSeconds",
        "trimEndSeconds",
        "chapterPlacement",
        "useAsOpeningOrEnding",
        "useAsBridgeBeforeAfter",
        "orientationRepairRequired",
        "captionFunction",
        "bgmMoodCue",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_decision_fields = 0
    rows_with_score = 0
    rows_with_use = 0
    tier_counts: dict[str, int] = {}
    function_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tier = str(row.get("selectionTier") or "")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        function = str(row.get("creatorFunction") or "")
        function_counts[function] = function_counts.get(function, 0) + 1
        if isinstance(row.get("selectionScore"), int):
            rows_with_score += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        recommended = row.get("recommendedUse") if isinstance(row.get("recommendedUse"), dict) else {}
        if recommended.get("use") and recommended.get("targetDurationRangeSeconds"):
            rows_with_use += 1
    chapter_decision_fields = {
        "approvedChapterPool",
        "heroRows",
        "mainRows",
        "bridgeRows",
        "rejectRows",
        "repairRows",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    chapters_with_decision_fields = 0
    chapters_with_pool = 0
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        decision = chapter.get("decision") if isinstance(chapter.get("decision"), dict) else {}
        if chapter_decision_fields.issubset(set(decision)):
            chapters_with_decision_fields += 1
        if int(chapter.get("sourceVideoCount") or 0) >= 1:
            chapters_with_pool += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "inputSource": summary.get("inputSource"),
        "sourceVideoCount": summary.get("sourceVideoCount"),
        "candidateVideoCount": summary.get("candidateVideoCount"),
        "heroCandidateCount": summary.get("heroCandidateCount"),
        "mainStoryCandidateCount": summary.get("mainStoryCandidateCount"),
        "textureBridgeCandidateCount": summary.get("textureBridgeCandidateCount"),
        "utilityContextCount": summary.get("utilityContextCount"),
        "repairOrRejectCount": summary.get("repairOrRejectCount"),
        "orientationRepairCandidateCount": summary.get("orientationRepairCandidateCount"),
        "derivedOrExcludedRejectCount": summary.get("derivedOrExcludedRejectCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "chaptersNeedingCoverage": summary.get("chaptersNeedingCoverage"),
        "tierCounts": summary.get("tierCounts") or tier_counts,
        "functionCounts": summary.get("functionCounts") or function_counts,
        "rowCount": len(rows),
        "chapterRows": len(chapters),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithScore": rows_with_score,
        "rowsWithRecommendedUse": rows_with_use,
        "chaptersWithDecisionFields": chapters_with_decision_fields,
        "chaptersWithPool": chapters_with_pool,
        "rawFootageSelectionBeforeAssembly": policy.get("rawFootageSelectionBeforeAssembly"),
        "selectiveShotChoiceRequired": policy.get("selectiveShotChoiceRequired"),
        "derivedExportsRejected": policy.get("derivedExportsRejected"),
        "orientationRepairBeforeUse": policy.get("orientationRepairBeforeUse"),
        "localFootageFirstForBridges": policy.get("localFootageFirstForBridges"),
        "chapterVarietyRequiredBeforeEffects": policy.get("chapterVarietyRequiredBeforeEffects"),
        "doesNotModifySourceFootage": policy.get("doesNotModifySourceFootage"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "writesResolve": policy.get("writesResolve"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def footage_select_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("sourceVideoCount") or 0)
    chapter_count = int(evidence.get("chapterRowCount") or 0)
    tier_counts = evidence.get("tierCounts") if isinstance(evidence.get("tierCounts"), dict) else {}
    function_counts = evidence.get("functionCounts") if isinstance(evidence.get("functionCounts"), dict) else {}
    tier_category_count = len([name for name, count in tier_counts.items() if int(count or 0) > 0])
    function_category_count = len([name for name, count in function_counts.items() if int(count or 0) > 0])
    return (
        evidence.get("exists")
        and evidence.get("status") in {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"}
        and row_count >= 10
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithScore") or 0) == row_count
        and int(evidence.get("rowsWithRecommendedUse") or 0) == row_count
        and int(evidence.get("candidateVideoCount") or 0) >= 3
        and int(evidence.get("textureBridgeCandidateCount") or 0) >= 1
        and chapter_count >= 1
        and int(evidence.get("chapterRows") or 0) == chapter_count
        and int(evidence.get("chaptersWithDecisionFields") or 0) == chapter_count
        and int(evidence.get("chaptersWithPool") or 0) == chapter_count
        and tier_category_count >= 3
        and function_category_count >= 3
        and evidence.get("rawFootageSelectionBeforeAssembly") is True
        and evidence.get("selectiveShotChoiceRequired") is True
        and evidence.get("derivedExportsRejected") is True
        and evidence.get("orientationRepairBeforeUse") is True
        and evidence.get("localFootageFirstForBridges") is True
        and evidence.get("chapterVarietyRequiredBeforeEffects") is True
        and evidence.get("doesNotModifySourceFootage") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def raw_intake_completeness_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "raw_intake_completeness_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "indexedVideoCount": summary.get("indexedVideoCount"),
        "filesystemVideoCount": summary.get("filesystemVideoCount"),
        "activeSourceVideoCount": summary.get("activeSourceVideoCount"),
        "sourceSizeGB": summary.get("sourceSizeGB"),
        "largeSource": summary.get("largeSource"),
        "recognitionCoverageRatio": summary.get("recognitionCoverageRatio"),
        "routeMissingVideoCount": summary.get("routeMissingVideoCount"),
        "routeDuplicateVideoCount": summary.get("routeDuplicateVideoCount"),
        "footageSelectMissingVideoCount": summary.get("footageSelectMissingVideoCount"),
        "activeDerivedVideoCount": summary.get("activeDerivedVideoCount"),
        "staleArtifactCount": summary.get("staleArtifactCount"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "warningCheckCount": summary.get("warningCheckCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def raw_intake_completeness_ready(evidence: dict[str, Any]) -> bool:
    indexed = int(evidence.get("indexedVideoCount") or 0)
    filesystem = int(evidence.get("filesystemVideoCount") or 0)
    active = int(evidence.get("activeSourceVideoCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and indexed > 0
        and active > 0
        and filesystem <= indexed
        and float(evidence.get("recognitionCoverageRatio") or 0) >= 1.0
        and int(evidence.get("routeMissingVideoCount") or 0) == 0
        and int(evidence.get("routeDuplicateVideoCount") or 0) == 0
        and int(evidence.get("footageSelectMissingVideoCount") or 0) == 0
        and int(evidence.get("activeDerivedVideoCount") or 0) == 0
        and int(evidence.get("staleArtifactCount") or 0) == 0
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceDrive") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def source_selection_repair_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json"
    audit_path = package_dir / "source_selection_coverage_contract_audit.json"
    data = load_json(path) or {}
    audit = load_json(audit_path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    audit_summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    repair_rows = data.get("repairRows") if isinstance(data.get("repairRows"), list) else []
    chapter_rows = data.get("chapterCoverageRows") if isinstance(data.get("chapterCoverageRows"), list) else []
    required_decision_fields = {
        "acceptedRepair",
        "ownerScriptExecuted",
        "replacementRowIndexes",
        "approvedFallback",
        "resolveBlueprintUpdate",
        "postRepairAudit",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    repair_rows_with_decision_fields = 0
    for row in repair_rows:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if required_decision_fields.issubset(set(decision)):
            repair_rows_with_decision_fields += 1
    ready_chapter_rows = [
        row for row in chapter_rows if isinstance(row, dict) and row.get("status") == "ready_with_chapter_selection_coverage"
    ]
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "auditPath": str(audit_path),
        "auditExists": audit_path.exists(),
        "auditStatus": audit.get("status"),
        "sourceVideoCount": summary.get("sourceVideoCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "readyChapterCount": summary.get("readyChapterCount"),
        "candidateVideoCount": summary.get("candidateVideoCount"),
        "heroCandidateCount": summary.get("heroCandidateCount"),
        "movementBridgeCandidateCount": summary.get("movementBridgeCandidateCount"),
        "livedInTextureCandidateCount": summary.get("livedInTextureCandidateCount"),
        "destinationPayoffCandidateCount": summary.get("destinationPayoffCandidateCount"),
        "blockingRepairRowCount": summary.get("blockingRepairRowCount"),
        "warningRepairRowCount": summary.get("warningRepairRowCount"),
        "repairRowCount": len(repair_rows),
        "chapterCoverageRowCount": len(chapter_rows),
        "readyChapterCoverageRowCount": len(ready_chapter_rows),
        "repairRowsWithDecisionFields": repair_rows_with_decision_fields,
        "auditBlockedCheckCount": audit_summary.get("blockedCheckCount"),
        "blocksFilenameOrderAssembly": policy.get("blocksFilenameOrderAssembly"),
        "blocksWeakChapterCoverageBeforeEffects": policy.get("blocksWeakChapterCoverageBeforeEffects"),
        "localFootageBeforeStockOrAerialFallback": policy.get("localFootageBeforeStockOrAerialFallback"),
        "orientationRepairClosedBeforeFinalUse": policy.get("orientationRepairClosedBeforeFinalUse"),
        "repairRowsMustCloseBeforeResolveApply": policy.get("repairRowsMustCloseBeforeResolveApply"),
        "doesNotModifySourceFootage": policy.get("doesNotModifySourceFootage"),
        "writesResolve": policy.get("writesResolve"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "safetyWritesResolve": safety.get("writesResolve"),
        "safetyDownloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "safetyModifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def source_selection_repair_plan_ready(evidence: dict[str, Any]) -> bool:
    chapter_count = int(evidence.get("chapterRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("auditExists")
        and evidence.get("status") == "ready_no_source_selection_repairs_needed"
        and evidence.get("auditStatus") == "passed"
        and int(evidence.get("sourceVideoCount") or 0) > 0
        and chapter_count >= 1
        and int(evidence.get("readyChapterCount") or 0) == chapter_count
        and int(evidence.get("chapterCoverageRowCount") or 0) == chapter_count
        and int(evidence.get("readyChapterCoverageRowCount") or 0) == chapter_count
        and int(evidence.get("candidateVideoCount") or 0) > 0
        and int(evidence.get("heroCandidateCount") or 0) >= 1
        and int(evidence.get("movementBridgeCandidateCount") or 0) >= max(1, chapter_count - 1)
        and int(evidence.get("livedInTextureCandidateCount") or 0) >= 1
        and int(evidence.get("destinationPayoffCandidateCount") or 0) >= 1
        and int(evidence.get("blockingRepairRowCount") or 0) == 0
        and int(evidence.get("repairRowsWithDecisionFields") or 0) == int(evidence.get("repairRowCount") or 0)
        and int(evidence.get("auditBlockedCheckCount") or 0) == 0
        and evidence.get("blocksFilenameOrderAssembly") is True
        and evidence.get("blocksWeakChapterCoverageBeforeEffects") is True
        and evidence.get("localFootageBeforeStockOrAerialFallback") is True
        and evidence.get("orientationRepairClosedBeforeFinalUse") is True
        and evidence.get("repairRowsMustCloseBeforeResolveApply") is True
        and evidence.get("doesNotModifySourceFootage") is True
        and evidence.get("writesResolve") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("safetyWritesResolve") is False
        and evidence.get("safetyDownloadsExternalAssets") is False
        and evidence.get("safetyModifiesSourceFootage") is False
    )


def first_assembly_source_order_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "first_assembly_source_order_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "activeSourceVideoCount": summary.get("activeSourceVideoCount"),
        "sourceSizeGB": summary.get("sourceSizeGB"),
        "largeSource": summary.get("largeSource"),
        "footageSelectInputSource": summary.get("footageSelectInputSource"),
        "footageSelectSourceVideoCount": summary.get("footageSelectSourceVideoCount"),
        "candidateVideoCount": summary.get("candidateVideoCount"),
        "candidateRowsUsed": summary.get("candidateRowsUsed"),
        "deliveryChapterCount": summary.get("deliveryChapterCount"),
        "sortedChapterCount": summary.get("sortedChapterCount"),
        "riskyTopSelectionRowCount": summary.get("riskyTopSelectionRowCount"),
        "missingTopSelectionDataCount": summary.get("missingTopSelectionDataCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def first_assembly_source_order_contract_ready(evidence: dict[str, Any]) -> bool:
    chapters = int(evidence.get("deliveryChapterCount") or 0)
    candidates = int(evidence.get("candidateVideoCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("activeSourceVideoCount") or 0) > 0
        and int(evidence.get("footageSelectSourceVideoCount") or 0) >= int(evidence.get("activeSourceVideoCount") or 0)
        and chapters >= 1
        and int(evidence.get("sortedChapterCount") or 0) >= chapters
        and candidates >= 3
        and int(evidence.get("candidateRowsUsed") or 0) >= min(candidates, max(3, chapters))
        and int(evidence.get("riskyTopSelectionRowCount") or 0) == 0
        and int(evidence.get("missingTopSelectionDataCount") or 0) == 0
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and (not evidence.get("largeSource") or evidence.get("footageSelectInputSource") == "media_index")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def large_source_unattended_readiness_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "large_source_unattended_readiness_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "largeSource": summary.get("largeSource"),
        "activeSourceVideoCount": summary.get("activeSourceVideoCount"),
        "expectedActiveSourceCount": summary.get("expectedActiveSourceCount"),
        "sourceSizeGB": summary.get("sourceSizeGB"),
        "recognitionCoverageRatio": summary.get("recognitionCoverageRatio"),
        "footageSelectInputSource": summary.get("footageSelectInputSource"),
        "candidateVideoCount": summary.get("candidateVideoCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "firstAssemblyStatus": summary.get("firstAssemblyStatus"),
        "unattendedFirstDraftStatus": summary.get("unattendedFirstDraftStatus"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "warningCheckCount": summary.get("warningCheckCount"),
        "externalMediaIntake": inputs.get("externalMediaIntake"),
        "requireExternalIntake": inputs.get("requireExternalIntake"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def large_source_unattended_readiness_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") in {"passed", "passed_with_warnings"}
        and int(evidence.get("activeSourceVideoCount") or 0) > 0
        and int(evidence.get("expectedActiveSourceCount") or 0) > 0
        and float(evidence.get("recognitionCoverageRatio") or 0) >= 1.0
        and (not evidence.get("largeSource") or evidence.get("footageSelectInputSource") == "media_index")
        and int(evidence.get("candidateVideoCount") or 0) >= 3
        and int(evidence.get("chapterRowCount") or 0) >= 1
        and evidence.get("firstAssemblyStatus") == "passed"
        and evidence.get("unattendedFirstDraftStatus") in {"passed", "passed_with_warnings"}
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def opening_story_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "opening_story_plan" / "opening_story_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("beatRows") if isinstance(data.get("beatRows"), list) else []
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    required_beats = {
        "viewer_promise",
        "destination_proof",
        "clean_hero_title",
        "practical_arrival",
        "lived_in_texture",
        "first_chapter_handoff",
    }
    decision_fields = {
        "approvedBeat",
        "selectedClipSourcePaths",
        "targetTimelineStartSeconds",
        "targetTimelineEndSeconds",
        "captionOrTitleText",
        "bgmMoodCue",
        "audioPolicy",
        "transitionOut",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    beat_ids: list[str] = []
    rows_with_decision_fields = 0
    rows_with_evidence = 0
    rows_with_bgm_audio_policy = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        beat_id = str(row.get("beatId") or "")
        if beat_id:
            beat_ids.append(beat_id)
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        if int(row.get("evidenceCount") or 0) > 0:
            rows_with_evidence += 1
        if decision.get("audioPolicy") == "bgm_only_no_camera_voice":
            rows_with_bgm_audio_policy += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "openingWindowSeconds": summary.get("openingWindowSeconds"),
        "openingVideoClipCount": summary.get("openingVideoClipCount"),
        "openingCoverageRatio": summary.get("openingCoverageRatio"),
        "firstClipStartSeconds": summary.get("firstClipStartSeconds"),
        "beatRowCount": summary.get("beatRowCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsWithEvidence": summary.get("rowsWithEvidence"),
        "missingBeatCount": summary.get("missingBeatCount"),
        "missingBeatIds": summary.get("missingBeatIds"),
        "destinationProofClipCount": summary.get("destinationProofClipCount"),
        "routeArrivalClipCount": summary.get("routeArrivalClipCount"),
        "livedInTextureClipCount": summary.get("livedInTextureClipCount"),
        "titleClipCount": summary.get("titleClipCount"),
        "weakTitleHitCount": summary.get("weakTitleHitCount"),
        "firstHandoffClipCount": summary.get("firstHandoffClipCount"),
        "rowCount": len(rows),
        "beatIds": beat_ids,
        "missingRequiredBeatIds": sorted(required_beats.difference(beat_ids)),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithEvidenceByRow": rows_with_evidence,
        "rowsWithBgmAudioPolicy": rows_with_bgm_audio_policy,
        "firstThreeMinutesNeedViewerPromise": policy.get("firstThreeMinutesNeedViewerPromise"),
        "destinationProofBeforeExplanation": policy.get("destinationProofBeforeExplanation"),
        "practicalArrivalReturnsAfterHook": policy.get("practicalArrivalReturnsAfterHook"),
        "livedInTextureBeforeMinuteThree": policy.get("livedInTextureBeforeMinuteThree"),
        "cleanTitleNoStackedText": policy.get("cleanTitleNoStackedText"),
        "titleZoneSubtitleSuppressionRequired": policy.get("titleZoneSubtitleSuppressionRequired"),
        "bgmOnlyOpeningDefault": policy.get("bgmOnlyOpeningDefault"),
        "localFootageBeforeStock": policy.get("localFootageBeforeStock"),
        "writesResolve": policy.get("writesResolve"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "modifiesSourceFootage": policy.get("modifiesSourceFootage"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def opening_story_plan_ready(evidence: dict[str, Any]) -> bool:
    beat_count = int(evidence.get("beatRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_opening_story_plan"
        and beat_count >= 6
        and int(evidence.get("rowCount") or 0) == beat_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == beat_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == beat_count
        and int(evidence.get("rowsWithEvidence") or 0) == beat_count
        and int(evidence.get("rowsWithEvidenceByRow") or 0) == beat_count
        and int(evidence.get("rowsWithBgmAudioPolicy") or 0) == beat_count
        and int(evidence.get("missingBeatCount") or 0) == 0
        and not evidence.get("missingRequiredBeatIds")
        and int(evidence.get("openingVideoClipCount") or 0) >= beat_count
        and float(evidence.get("openingCoverageRatio") or 0) >= 0.5
        and int(evidence.get("destinationProofClipCount") or 0) >= 1
        and int(evidence.get("routeArrivalClipCount") or 0) >= 1
        and int(evidence.get("livedInTextureClipCount") or 0) >= 1
        and int(evidence.get("titleClipCount") or 0) >= 1
        and int(evidence.get("weakTitleHitCount") or 0) == 0
        and int(evidence.get("firstHandoffClipCount") or 0) >= 1
        and evidence.get("firstThreeMinutesNeedViewerPromise") is True
        and evidence.get("destinationProofBeforeExplanation") is True
        and evidence.get("practicalArrivalReturnsAfterHook") is True
        and evidence.get("livedInTextureBeforeMinuteThree") is True
        and evidence.get("cleanTitleNoStackedText") is True
        and evidence.get("titleZoneSubtitleSuppressionRequired") is True
        and evidence.get("bgmOnlyOpeningDefault") is True
        and evidence.get("localFootageBeforeStock") is True
        and evidence.get("writesResolve") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def chapter_arc_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "chapter_arc_plan" / "chapter_arc_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("chapterRows") if isinstance(data.get("chapterRows"), list) else []
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    decision_fields = {
        "approvedChapterArc",
        "selectedContextClip",
        "selectedMovementClip",
        "selectedTextureClip",
        "selectedPayoffClip",
        "selectedAftertasteClip",
        "captionArcEvidence",
        "bgmArcEvidence",
        "transitionHandoffEvidence",
        "resolveBlueprintEvidence",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    required_beats = {"context", "movement", "texture", "payoff", "aftertaste"}
    rows_with_decision_fields = 0
    rows_with_required_beat_map = 0
    missing_beat_count = 0
    missing_beats_with_owner = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        detected = row.get("detectedBeats") if isinstance(row.get("detectedBeats"), dict) else {}
        if required_beats.issubset(set(detected)):
            rows_with_required_beat_map += 1
        missing = [str(item) for item in row.get("missingBeatIds") or []]
        owners = row.get("ownerScriptsForMissingBeats") if isinstance(row.get("ownerScriptsForMissingBeats"), list) else []
        owner_ids = {str(owner.get("beatId") or "") for owner in owners if isinstance(owner, dict)}
        missing_beat_count += len(missing)
        missing_beats_with_owner += sum(1 for beat_id in missing if beat_id in owner_ids)
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "blueprintVideoClipCount": summary.get("blueprintVideoClipCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "chaptersWithContextBeat": summary.get("chaptersWithContextBeat"),
        "chaptersWithMovementBeat": summary.get("chaptersWithMovementBeat"),
        "chaptersWithTextureBeat": summary.get("chaptersWithTextureBeat"),
        "chaptersWithPayoffBeat": summary.get("chaptersWithPayoffBeat"),
        "chaptersWithAftertasteBeat": summary.get("chaptersWithAftertasteBeat"),
        "chaptersMissingRequiredBeatCount": summary.get("chaptersMissingRequiredBeatCount"),
        "p0RepairRowCount": summary.get("p0RepairRowCount"),
        "rowCount": len(rows),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithRequiredBeatMap": rows_with_required_beat_map,
        "missingBeatCountByRow": missing_beat_count,
        "missingBeatsWithOwner": missing_beats_with_owner,
        "chapterArcRequiredBeforeRhythmOrResolveTrust": policy.get("chapterArcRequiredBeforeRhythmOrResolveTrust"),
        "contextMovementTexturePayoffAftertasteGrammar": policy.get("contextMovementTexturePayoffAftertasteGrammar"),
        "physicalBridgeBeforeTransitionEffect": policy.get("physicalBridgeBeforeTransitionEffect"),
        "audienceFacingCaptionArcOnly": policy.get("audienceFacingCaptionArcOnly"),
        "bgmOnlyNoCameraVoiceDefault": policy.get("bgmOnlyNoCameraVoiceDefault"),
        "referenceAnchoredButNonCopying": policy.get("referenceAnchoredButNonCopying"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def chapter_arc_plan_ready(evidence: dict[str, Any]) -> bool:
    chapter_count = int(evidence.get("chapterRowCount") or 0)
    missing_count = int(evidence.get("missingBeatCountByRow") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_chapter_arc_plan"
        and chapter_count >= 1
        and int(evidence.get("rowCount") or 0) == chapter_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == chapter_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == chapter_count
        and int(evidence.get("rowsWithRequiredBeatMap") or 0) == chapter_count
        and int(evidence.get("missingBeatsWithOwner") or 0) == missing_count
        and int(evidence.get("blueprintVideoClipCount") or 0) >= 1
        and evidence.get("chapterArcRequiredBeforeRhythmOrResolveTrust") is True
        and evidence.get("contextMovementTexturePayoffAftertasteGrammar") is True
        and evidence.get("physicalBridgeBeforeTransitionEffect") is True
        and evidence.get("audienceFacingCaptionArcOnly") is True
        and evidence.get("bgmOnlyNoCameraVoiceDefault") is True
        and evidence.get("referenceAnchoredButNonCopying") is True
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def edit_rhythm_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("shotRows") if isinstance(data.get("shotRows"), list) else []
    chapters = data.get("chapterRows") if isinstance(data.get("chapterRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    reference = data.get("referenceProfile") if isinstance(data.get("referenceProfile"), dict) else {}
    target = data.get("targetRhythmProfile") if isinstance(data.get("targetRhythmProfile"), dict) else {}
    decision_fields = {
        "keepOrRetimingDecision",
        "approvedRhythmRole",
        "targetDurationSeconds",
        "trimStartSeconds",
        "trimEndSeconds",
        "cutawayBefore",
        "cutawayAfter",
        "replacementOrInsertSource",
        "captionFunction",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_decision_fields = 0
    rows_with_treatment = 0
    risk_rows = 0
    risk_rows_with_guidance = 0
    role_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        role = str(row.get("rhythmRole") or "")
        role_counts[role] = role_counts.get(role, 0) + 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        treatment = row.get("recommendedTreatment") if isinstance(row.get("recommendedTreatment"), dict) else {}
        if treatment.get("editorGuidance") and treatment.get("targetDurationRangeSeconds"):
            rows_with_treatment += 1
        if row.get("riskReasons"):
            risk_rows += 1
            if treatment.get("editorGuidance"):
                risk_rows_with_guidance += 1
    chapter_decision_fields = {
        "approvedChapterRhythm",
        "addCutaways",
        "retimeRows",
        "captionOrBgmNote",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    chapters_with_decision_fields = 0
    chapters_with_categories = 0
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        decision = chapter.get("decision") if isinstance(chapter.get("decision"), dict) else {}
        if chapter_decision_fields.issubset(set(decision)):
            chapters_with_decision_fields += 1
        if int(chapter.get("coveredCategoryCount") or 0) >= 1:
            chapters_with_categories += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "primaryVisualShotCount": summary.get("primaryVisualShotCount"),
        "recommendedMinimumShotCount": summary.get("recommendedMinimumShotCount"),
        "estimatedAdditionalCutawayBeats": summary.get("estimatedAdditionalCutawayBeats"),
        "averageShotSeconds": summary.get("averageShotSeconds"),
        "medianShotSeconds": summary.get("medianShotSeconds"),
        "rhythmRiskCount": summary.get("rhythmRiskCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "chaptersNeedingVarietyOrRetime": summary.get("chaptersNeedingVarietyOrRetime"),
        "categoryCounts": summary.get("categoryCounts"),
        "referenceReady": summary.get("referenceReady"),
        "rowCount": len(rows),
        "chapterRows": len(chapters),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithTreatment": rows_with_treatment,
        "riskRowsByRow": risk_rows,
        "riskRowsWithGuidance": risk_rows_with_guidance,
        "roleCounts": role_counts,
        "chaptersWithDecisionFields": chapters_with_decision_fields,
        "chaptersWithCategories": chapters_with_categories,
        "referenceExists": reference.get("exists"),
        "referencePacingStatus": reference.get("pacingStatus"),
        "referenceAverageShotLengthSeconds": reference.get("averageShotLengthSeconds"),
        "referenceMedianShotLengthSeconds": reference.get("medianShotLengthSeconds"),
        "targetAverageRangeSeconds": target.get("targetAverageRangeSeconds"),
        "longShotSoftLimitSeconds": target.get("longShotSoftLimitSeconds"),
        "referenceAnchoredButNonCopying": policy.get("referenceAnchoredButNonCopying"),
        "avoidBareConcatenation": policy.get("avoidBareConcatenation"),
        "realFootageFunctionRequired": policy.get("realFootageFunctionRequired"),
        "livedInRouteTextureRequired": policy.get("livedInRouteTextureRequired"),
        "bgmAndCaptionsCarryNoVoiceoverSections": policy.get("bgmAndCaptionsCarryNoVoiceoverSections"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "writesResolve": policy.get("writesResolve"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def edit_rhythm_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("primaryVisualShotCount") or 0)
    chapter_count = int(evidence.get("chapterRowCount") or 0)
    role_counts = evidence.get("roleCounts") if isinstance(evidence.get("roleCounts"), dict) else {}
    category_count = len([name for name, count in role_counts.items() if int(count or 0) > 0])
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_edit_rhythm_plan"
        and row_count >= 10
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithTreatment") or 0) == row_count
        and chapter_count >= 1
        and int(evidence.get("chapterRows") or 0) == chapter_count
        and int(evidence.get("chaptersWithDecisionFields") or 0) == chapter_count
        and int(evidence.get("chaptersWithCategories") or 0) >= 1
        and int(evidence.get("recommendedMinimumShotCount") or 0) >= row_count
        and int(evidence.get("riskRowsWithGuidance") or 0) == int(evidence.get("riskRowsByRow") or 0)
        and evidence.get("referenceReady") is True
        and evidence.get("referenceExists") is True
        and evidence.get("referencePacingStatus") == "analyzed"
        and float(evidence.get("referenceAverageShotLengthSeconds") or 0) > 0
        and float(evidence.get("referenceMedianShotLengthSeconds") or 0) > 0
        and isinstance(evidence.get("targetAverageRangeSeconds"), list)
        and float(evidence.get("longShotSoftLimitSeconds") or 0) > 0
        and category_count >= 4
        and role_counts.get("title_bridge", 0) >= 1
        and (role_counts.get("route_transition", 0) + role_counts.get("transport_motion", 0)) >= 1
        and evidence.get("referenceAnchoredButNonCopying") is True
        and evidence.get("avoidBareConcatenation") is True
        and evidence.get("realFootageFunctionRequired") is True
        and evidence.get("livedInRouteTextureRequired") is True
        and evidence.get("bgmAndCaptionsCarryNoVoiceoverSections") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def creator_cut_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "creator_cut_plan" / "creator_cut_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("shotRows") if isinstance(data.get("shotRows"), list) else []
    chapters = data.get("chapterRows") if isinstance(data.get("chapterRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    decision_fields = {
        "approvedUse",
        "targetDurationSeconds",
        "trimStartSeconds",
        "trimEndSeconds",
        "bridgeBefore",
        "bridgeAfter",
        "selectedTransitionEffect",
        "bgmPhraseCue",
        "captionFunction",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_decision_fields = 0
    rows_with_creator_function = 0
    rows_with_recommended_use = 0
    rows_with_transition_recipe = 0
    tier_counts: dict[str, int] = {}
    function_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tier = str(row.get("editorialTier") or "")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        function = str(row.get("creatorFunction") or "")
        function_counts[function] = function_counts.get(function, 0) + 1
        if function:
            rows_with_creator_function += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        recommended = row.get("recommendedUse") if isinstance(row.get("recommendedUse"), dict) else {}
        if recommended.get("use") and recommended.get("targetDurationRangeSeconds"):
            rows_with_recommended_use += 1
        recipe = row.get("transitionRecipe") if isinstance(row.get("transitionRecipe"), dict) else {}
        if recipe.get("style") and recipe.get("mustAvoid"):
            rows_with_transition_recipe += 1
    chapters_with_decision_fields = 0
    chapters_with_functions = 0
    chapter_decision_fields = {
        "approvedChapterShape",
        "replaceOrDropRows",
        "requiredBridgeInsert",
        "requiredTextureInsert",
        "endingOrAftertasteNote",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        decision = chapter.get("decision") if isinstance(chapter.get("decision"), dict) else {}
        if chapter_decision_fields.issubset(set(decision)):
            chapters_with_decision_fields += 1
        if int(chapter.get("functionCount") or 0) >= 1:
            chapters_with_functions += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "primaryVisualShotCount": summary.get("primaryVisualShotCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "creatorDecisionRowCount": summary.get("creatorDecisionRowCount"),
        "rejectOrUtilityCount": summary.get("rejectOrUtilityCount"),
        "routeBridgeCandidateCount": summary.get("routeBridgeCandidateCount"),
        "motivatedRotationCandidateCount": summary.get("motivatedRotationCandidateCount"),
        "chaptersNeedingCreatorCoverage": summary.get("chaptersNeedingCreatorCoverage"),
        "tierCounts": summary.get("tierCounts") or tier_counts,
        "functionCounts": summary.get("functionCounts") or function_counts,
        "rowCount": len(rows),
        "chapterRows": len(chapters),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithCreatorFunction": rows_with_creator_function,
        "rowsWithRecommendedUse": rows_with_recommended_use,
        "rowsWithTransitionRecipe": rows_with_transition_recipe,
        "chaptersWithDecisionFields": chapters_with_decision_fields,
        "chaptersWithFunctions": chapters_with_functions,
        "selectiveShotChoiceRequired": policy.get("selectiveShotChoiceRequired"),
        "weakClipsCanBeRejected": policy.get("weakClipsCanBeRejected"),
        "everyKeptShotNeedsCreatorFunction": policy.get("everyKeptShotNeedsCreatorFunction"),
        "physicalBridgeBeforeEffect": policy.get("physicalBridgeBeforeEffect"),
        "motivatedWhipOrRotationAllowed": policy.get("motivatedWhipOrRotationAllowed"),
        "templateEffectsRejected": policy.get("templateEffectsRejected"),
        "referenceAnchoredButNonCopying": policy.get("referenceAnchoredButNonCopying"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "writesResolve": policy.get("writesResolve"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def creator_cut_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("primaryVisualShotCount") or 0)
    chapter_count = int(evidence.get("chapterRowCount") or 0)
    function_counts = evidence.get("functionCounts") if isinstance(evidence.get("functionCounts"), dict) else {}
    function_category_count = len([name for name, count in function_counts.items() if int(count or 0) > 0])
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_creator_cut_plan"
        and row_count >= 10
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("creatorDecisionRowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithCreatorFunction") or 0) == row_count
        and int(evidence.get("rowsWithRecommendedUse") or 0) == row_count
        and int(evidence.get("rowsWithTransitionRecipe") or 0) == row_count
        and chapter_count >= 1
        and int(evidence.get("chapterRows") or 0) == chapter_count
        and int(evidence.get("chaptersWithDecisionFields") or 0) == chapter_count
        and int(evidence.get("chaptersWithFunctions") or 0) == chapter_count
        and function_category_count >= 4
        and int(evidence.get("routeBridgeCandidateCount") or 0) >= 1
        and evidence.get("selectiveShotChoiceRequired") is True
        and evidence.get("weakClipsCanBeRejected") is True
        and evidence.get("everyKeptShotNeedsCreatorFunction") is True
        and evidence.get("physicalBridgeBeforeEffect") is True
        and evidence.get("motivatedWhipOrRotationAllowed") is True
        and evidence.get("templateEffectsRejected") is True
        and evidence.get("referenceAnchoredButNonCopying") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def creator_cut_application_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "creator_cut_application_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "creatorCutPlanExists": inputs.get("creatorCutPlanExists"),
        "visualClipCount": summary.get("visualClipCount"),
        "creatorPlanRowCount": summary.get("creatorPlanRowCount"),
        "matchedCreatorRowCount": summary.get("matchedCreatorRowCount"),
        "passedClipCount": summary.get("passedClipCount"),
        "blockedClipCount": summary.get("blockedClipCount"),
        "chapterCount": summary.get("chapterCount"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "rejectActiveClipCount": summary.get("rejectActiveClipCount"),
        "weakActiveClipCount": summary.get("weakActiveClipCount"),
        "utilityActiveClipCount": summary.get("utilityActiveClipCount"),
        "sameSourceRunMax": summary.get("sameSourceRunMax"),
        "sameFunctionRunMax": summary.get("sameFunctionRunMax"),
        "globalFunctionGroupCount": summary.get("globalFunctionGroupCount"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def creator_cut_application_contract_ready(evidence: dict[str, Any]) -> bool:
    clip_count = int(evidence.get("visualClipCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and evidence.get("creatorCutPlanExists") is True
        and clip_count >= 3
        and int(evidence.get("matchedCreatorRowCount") or 0) == clip_count
        and int(evidence.get("passedClipCount") or 0) == clip_count
        and int(evidence.get("blockedClipCount") or 0) == 0
        and int(evidence.get("chaptersBlocked") or 0) == 0
        and int(evidence.get("rejectActiveClipCount") or 0) == 0
        and int(evidence.get("weakActiveClipCount") or 0) == 0
        and int(evidence.get("globalFunctionGroupCount") or 0) >= 3
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_grammar_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_grammar_plan" / "transition_grammar_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("transitionRows") if isinstance(data.get("transitionRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    decision_fields = {
        "approvedTransitionType",
        "fallbackTransitionType",
        "durationFrames",
        "requiresBridgeInsert",
        "bridgeInsertSource",
        "motionDirection",
        "bgmPhraseCue",
        "captionSuppressionNeeded",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_decision_fields = 0
    rows_with_recommendation = 0
    rows_ready = 0
    rows_needing_bridge = 0
    motion_allowed_rows = 0
    bridge_evidence_rows = 0
    style_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        category = str(row.get("boundaryCategory") or "")
        category_counts[category] = category_counts.get(category, 0) + 1
        if row.get("status") == "ready_with_transition_grammar":
            rows_ready += 1
        if row.get("status") == "needs_bridge_insert":
            rows_needing_bridge += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        recommendation = row.get("recommendation") if isinstance(row.get("recommendation"), dict) else {}
        style = str(recommendation.get("recommendedTransitionType") or "")
        if style:
            style_counts[style] = style_counts.get(style, 0) + 1
            rows_with_recommendation += 1
        if recommendation.get("motionEffectAllowed") is True:
            motion_allowed_rows += 1
        if recommendation.get("physicalBridgeEvidence") is True:
            bridge_evidence_rows += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualClipCount": summary.get("visualClipCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "chapterBoundaryCount": summary.get("chapterBoundaryCount"),
        "titleBoundaryCount": summary.get("titleBoundaryCount"),
        "timelineGapCount": summary.get("timelineGapCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsNeedingBridgeInsert": summary.get("rowsNeedingBridgeInsert"),
        "physicalBridgeEvidenceCount": summary.get("physicalBridgeEvidenceCount"),
        "motivatedMotionEffectCandidateCount": summary.get("motivatedMotionEffectCandidateCount"),
        "recommendedStyleCounts": summary.get("recommendedStyleCounts") or style_counts,
        "boundaryCategoryCounts": summary.get("boundaryCategoryCounts") or category_counts,
        "rowCount": len(rows),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithRecommendation": rows_with_recommendation,
        "rowsReadyByRow": rows_ready,
        "rowsNeedingBridgeByRow": rows_needing_bridge,
        "motionAllowedRowsByRow": motion_allowed_rows,
        "bridgeEvidenceRowsByRow": bridge_evidence_rows,
        "pairLevelTransitionDecisionsRequired": policy.get("pairLevelTransitionDecisionsRequired"),
        "physicalBridgeBeforeMotionEffect": policy.get("physicalBridgeBeforeMotionEffect"),
        "motivatedWhipOrRotationOnly": policy.get("motivatedWhipOrRotationOnly"),
        "templateTransitionsRejected": policy.get("templateTransitionsRejected"),
        "titleZoneSafetyRequired": policy.get("titleZoneSafetyRequired"),
        "bgmPhraseAwarenessRequired": policy.get("bgmPhraseAwarenessRequired"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "writesResolve": policy.get("writesResolve"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def transition_grammar_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("transitionRowCount") or 0)
    style_counts = evidence.get("recommendedStyleCounts") if isinstance(evidence.get("recommendedStyleCounts"), dict) else {}
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_grammar_plan"
        and row_count >= 3
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithRecommendation") or 0) == row_count
        and int(evidence.get("rowsReadyByRow") or 0) == row_count
        and int(evidence.get("rowsNeedingBridgeInsert") or 0) == 0
        and int(evidence.get("rowsNeedingBridgeByRow") or 0) == 0
        and int(evidence.get("physicalBridgeEvidenceCount") or 0) >= 1
        and int(evidence.get("bridgeEvidenceRowsByRow") or 0) >= 1
        and bool(style_counts)
        and evidence.get("pairLevelTransitionDecisionsRequired") is True
        and evidence.get("physicalBridgeBeforeMotionEffect") is True
        and evidence.get("motivatedWhipOrRotationOnly") is True
        and evidence.get("templateTransitionsRejected") is True
        and evidence.get("titleZoneSafetyRequired") is True
        and evidence.get("bgmPhraseAwarenessRequired") is True
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def transition_execution_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_execution_plan" / "transition_execution_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("executionRows") if isinstance(data.get("executionRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    upstream = data.get("upstreamEvidence") if isinstance(data.get("upstreamEvidence"), dict) else {}
    decision_fields = {
        "approvedTransitionType",
        "approvedResolveEffectName",
        "durationFrames",
        "bridgeInsertSource",
        "bgmPhraseCue",
        "subtitleSuppressionConfirmed",
        "audioPolicyConfirmed",
        "resolveImplementation",
        "timelineReadbackEvidence",
        "renderFrameSampleEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_decision_fields = 0
    rows_with_recipe = 0
    rows_ready = 0
    bridge_blocked_rows = 0
    motion_rows = 0
    motion_rows_with_evidence = 0
    rows_bgm_only = 0
    title_boundary_rows = 0
    title_rows_with_subtitle_policy = 0
    forbidden_hits = 0
    style_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "ready_with_transition_execution_recipe":
            rows_ready += 1
        if row.get("requiresBridgeInsert"):
            bridge_blocked_rows += 1
        if row.get("motionStyle"):
            motion_rows += 1
            if row.get("motionHasEvidence"):
                motion_rows_with_evidence += 1
        forbidden_hits += len(row.get("forbiddenRecipeHits") or [])
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
        if recipe.get("resolveEffectName") and recipe.get("implementationSteps") and recipe.get("verificationTargets"):
            rows_with_recipe += 1
        if recipe.get("audioPolicy") == "bgm_only_no_camera_voice":
            rows_bgm_only += 1
        if row.get("boundaryCategory") == "title_boundary":
            title_boundary_rows += 1
            if "title_zone" in str(recipe.get("subtitlePolicy") or ""):
                title_rows_with_subtitle_policy += 1
        style = str(recipe.get("style") or "")
        if style:
            style_counts[style] = style_counts.get(style, 0) + 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "rowsReadyForResolveExecution": summary.get("rowsReadyForResolveExecution"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsWithExecutionRecipe": summary.get("rowsWithExecutionRecipe"),
        "bridgeInsertBlockedRowCount": summary.get("bridgeInsertBlockedRowCount"),
        "motionStyleRowCount": summary.get("motionStyleRowCount"),
        "motionStyleRowsWithEvidence": summary.get("motionStyleRowsWithEvidence"),
        "forbiddenRecipeHitCount": summary.get("forbiddenRecipeHitCount"),
        "executionStyleCounts": summary.get("executionStyleCounts") or style_counts,
        "rowCount": len(rows),
        "rowsReadyByRow": rows_ready,
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithRecipeByRow": rows_with_recipe,
        "bridgeBlockedRowsByRow": bridge_blocked_rows,
        "motionRowsByRow": motion_rows,
        "motionRowsWithEvidenceByRow": motion_rows_with_evidence,
        "rowsBgmOnly": rows_bgm_only,
        "titleBoundaryRows": title_boundary_rows,
        "titleRowsWithSubtitlePolicy": title_rows_with_subtitle_policy,
        "forbiddenHitsByRow": forbidden_hits,
        "transitionBridgeStatus": (upstream.get("transitionBridge") or {}).get("status") if isinstance(upstream.get("transitionBridge"), dict) else None,
        "effectMotionStatus": (upstream.get("effectMotion") or {}).get("status") if isinstance(upstream.get("effectMotion"), dict) else None,
        "bgmSelectionStatus": (upstream.get("bgmSelection") or {}).get("status") if isinstance(upstream.get("bgmSelection"), dict) else None,
        "resolveExecutionRecipeRequired": policy.get("resolveExecutionRecipeRequired"),
        "motionEffectsNeedGrammarEvidence": policy.get("motionEffectsNeedGrammarEvidence"),
        "insertBridgeFirstIsNotEffectReady": policy.get("insertBridgeFirstIsNotEffectReady"),
        "subtitleTitleZoneSafetyRequired": policy.get("subtitleTitleZoneSafetyRequired"),
        "bgmOnlyTransitionAudio": policy.get("bgmOnlyTransitionAudio"),
        "templateEffectsRejected": policy.get("templateEffectsRejected"),
        "writesResolve": policy.get("writesResolve"),
        "queuesRender": policy.get("queuesRender"),
        "downloadsExternalAssets": policy.get("downloadsExternalAssets"),
        "modifiesSourceFootage": policy.get("modifiesSourceFootage"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def transition_execution_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("transitionRowCount") or 0)
    motion_count = int(evidence.get("motionStyleRowCount") or 0)
    title_count = int(evidence.get("titleBoundaryRows") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_execution_plan"
        and row_count >= 3
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsReadyForResolveExecution") or 0) == row_count
        and int(evidence.get("rowsReadyByRow") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithExecutionRecipe") or 0) == row_count
        and int(evidence.get("rowsWithRecipeByRow") or 0) == row_count
        and int(evidence.get("bridgeInsertBlockedRowCount") or 0) == 0
        and int(evidence.get("bridgeBlockedRowsByRow") or 0) == 0
        and int(evidence.get("forbiddenRecipeHitCount") or 0) == 0
        and int(evidence.get("forbiddenHitsByRow") or 0) == 0
        and int(evidence.get("motionRowsWithEvidenceByRow") or 0) == motion_count
        and int(evidence.get("rowsBgmOnly") or 0) == row_count
        and int(evidence.get("titleRowsWithSubtitlePolicy") or 0) >= min(title_count, 1)
        and evidence.get("resolveExecutionRecipeRequired") is True
        and evidence.get("motionEffectsNeedGrammarEvidence") is True
        and evidence.get("insertBridgeFirstIsNotEffectReady") is True
        and evidence.get("subtitleTitleZoneSafetyRequired") is True
        and evidence.get("bgmOnlyTransitionAudio") is True
        and evidence.get("templateEffectsRejected") is True
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def transition_execution_blueprint_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    rows = data.get("materializedRows") if isinstance(data.get("materializedRows"), list) else []
    candidate_path = Path(str(outputs.get("candidateBlueprint") or package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json"))
    candidate = load_json(candidate_path) or {}
    transitions = candidate.get("transitions") if isinstance(candidate.get("transitions"), list) else []
    clips = candidate.get("clips") if isinstance(candidate.get("clips"), list) else []
    markers = [
        marker for marker in candidate.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "transition_execution_candidate_marker"
    ] if isinstance(candidate.get("timelineMarkers"), list) else []
    decision_fields = {
        "approveCandidateBlueprint",
        "approvedTransitionRows",
        "resolveImplementation",
        "preflightEvidence",
        "timelineReadbackEvidence",
        "frameSampleEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    rows_with_decision_fields = 0
    rows_materialized = 0
    rows_with_clip_match = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "materialized":
            rows_materialized += 1
        if row.get("fromClipMatched") is True and row.get("toClipMatched") is True:
            rows_with_clip_match += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
    transition_rows_with_decisions = 0
    transition_rows_without_forbidden = 0
    transition_rows_bridge_safe = 0
    transition_rows_motion_safe = 0
    transition_rows_with_reference_selection = 0
    transition_rows_with_motion_execution = 0
    transition_rows_with_three_beat_motion = 0
    transition_rows_with_bgm_hit_motion = 0
    transition_rows_with_caption_quiet_motion = 0
    transition_rows_with_cutpoint = 0
    transition_rows_with_cutpoint_bgm = 0
    transition_rows_with_cutpoint_landing = 0
    transition_rows_with_cutpoint_handles = 0
    transition_rows_with_action_anchor = 0
    transition_rows_with_outgoing_action_anchor = 0
    transition_rows_with_bridge_match_action_anchor = 0
    transition_rows_with_landing_action_anchor = 0
    transition_rows_with_sensory_continuity = 0
    transition_rows_with_visual_sensory = 0
    transition_rows_with_audio_sensory = 0
    transition_rows_with_caption_sensory = 0
    transition_rows_with_route_mood_sensory = 0
    transition_rows_with_landing_sensory = 0
    transition_rows_with_motion_sensory = 0
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        decision = transition.get("decision") if isinstance(transition.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            transition_rows_with_decisions += 1
        if not transition.get("forbiddenRecipeHits"):
            transition_rows_without_forbidden += 1
        if not transition.get("requiresBridgeInsert") or transition.get("bridgeSequenceSatisfied") is True:
            transition_rows_bridge_safe += 1
        if not transition.get("motionStyle") or transition.get("motionHasEvidence") is True:
            transition_rows_motion_safe += 1
        if transition.get("referenceSelectionApplied") is True and transition.get("selectedCandidateType") and transition.get("selectedStyleFamily"):
            transition_rows_with_reference_selection += 1
        motion_execution = transition.get("transitionMotionExecution") if isinstance(transition.get("transitionMotionExecution"), dict) else {}
        if motion_execution.get("status") == "ready_with_transition_motion_execution":
            transition_rows_with_motion_execution += 1
        if len(motion_execution.get("threeBeatChoreography") or []) >= 3:
            transition_rows_with_three_beat_motion += 1
        bgm = motion_execution.get("bgmChoreography") if isinstance(motion_execution.get("bgmChoreography"), dict) else {}
        if bgm.get("target") == "cut_or_effect_on_bgm_phrase_hit" and bgm.get("allowOffPhrase") is False:
            transition_rows_with_bgm_hit_motion += 1
        caption = motion_execution.get("captionAndTitlePolicy") if isinstance(motion_execution.get("captionAndTitlePolicy"), dict) else {}
        if caption.get("avoidTitleCollision") is True and caption.get("suppressSubtitlesDuringHeroTitleOrFastMotion") is True:
            transition_rows_with_caption_quiet_motion += 1
        cutpoint = transition.get("transitionCutpointPlan") if isinstance(transition.get("transitionCutpointPlan"), dict) else {}
        if cutpoint.get("status") == "ready_with_transition_cutpoint_plan":
            transition_rows_with_cutpoint += 1
        if cutpoint.get("bgmHitAligned") is True:
            transition_rows_with_cutpoint_bgm += 1
        if int(cutpoint.get("landingHoldFrames") or 0) >= (10 if cutpoint.get("importantBoundary") else 6):
            transition_rows_with_cutpoint_landing += 1
        if cutpoint.get("handlesReady") is True:
            transition_rows_with_cutpoint_handles += 1
        action_anchor = transition.get("transitionActionAnchorPlan") if isinstance(transition.get("transitionActionAnchorPlan"), dict) else {}
        if action_anchor.get("status") == "ready_with_transition_action_anchor_plan":
            transition_rows_with_action_anchor += 1
        if (action_anchor.get("outgoingAnchor") or {}).get("ready") is True:
            transition_rows_with_outgoing_action_anchor += 1
        if action_anchor.get("bridgeOrMatchReady") is True:
            transition_rows_with_bridge_match_action_anchor += 1
        if (action_anchor.get("landingAnchor") or {}).get("ready") is True:
            transition_rows_with_landing_action_anchor += 1
        sensory = transition.get("transitionSensoryContinuityPlan") if isinstance(transition.get("transitionSensoryContinuityPlan"), dict) else {}
        channels = sensory.get("cueChannels") if isinstance(sensory.get("cueChannels"), dict) else {}
        if sensory.get("status") == "ready_with_transition_sensory_continuity_plan":
            transition_rows_with_sensory_continuity += 1
        if channels.get("visualContinuityReady") is True:
            transition_rows_with_visual_sensory += 1
        if channels.get("audioContinuityReady") is True:
            transition_rows_with_audio_sensory += 1
        if channels.get("captionQuietReady") is True:
            transition_rows_with_caption_sensory += 1
        if channels.get("routeOrMoodContinuityReady") is True:
            transition_rows_with_route_mood_sensory += 1
        if channels.get("landingContinuityReady") is True:
            transition_rows_with_landing_sensory += 1
        if channels.get("motionContinuityReady") is True:
            transition_rows_with_motion_sensory += 1
    annotated_out = sum(len(clip.get("transitionExecutionOut") or []) for clip in clips if isinstance(clip, dict) and isinstance(clip.get("transitionExecutionOut"), list))
    annotated_in = sum(len(clip.get("transitionExecutionIn") or []) for clip in clips if isinstance(clip, dict) and isinstance(clip.get("transitionExecutionIn"), list))
    annotated_out_motion = sum(
        1
        for clip in clips
        if isinstance(clip, dict)
        for item in (clip.get("transitionExecutionOut") or [])
        if isinstance(item, dict)
        and isinstance(item.get("transitionMotionExecution"), dict)
        and item["transitionMotionExecution"].get("status") == "ready_with_transition_motion_execution"
    )
    annotated_in_motion = sum(
        1
        for clip in clips
        if isinstance(clip, dict)
        for item in (clip.get("transitionExecutionIn") or [])
        if isinstance(item, dict)
        and isinstance(item.get("transitionMotionExecution"), dict)
        and item["transitionMotionExecution"].get("status") == "ready_with_transition_motion_execution"
    )
    marker_motion = sum(
        1
        for marker in markers
        if isinstance(marker.get("payload"), dict)
        and marker["payload"].get("transitionMotionExecutionStatus") == "ready_with_transition_motion_execution"
        and marker["payload"].get("choreographyFamily")
    )
    plan = candidate.get("transitionExecutionBlueprintPlan") if isinstance(candidate.get("transitionExecutionBlueprintPlan"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "candidateBlueprint": str(candidate_path),
        "candidateBlueprintExists": candidate_path.exists(),
        "candidateHasTransitionExecutionPlan": isinstance(candidate.get("transitionExecutionBlueprintPlan"), dict),
        "executionRowCount": summary.get("executionRowCount"),
        "materializedTransitionCount": summary.get("materializedTransitionCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "rowsMissingClipMatch": summary.get("rowsMissingClipMatch"),
        "motionEffectRowCount": summary.get("motionEffectRowCount"),
        "motionEffectRowsWithEvidence": summary.get("motionEffectRowsWithEvidence"),
        "bridgeRequiredRowCount": summary.get("bridgeRequiredRowCount"),
        "bridgeSatisfiedRowCount": summary.get("bridgeSatisfiedRowCount"),
        "referenceSelectionRowCount": summary.get("referenceSelectionRowCount"),
        "rowsWithReferenceSelection": summary.get("rowsWithReferenceSelection"),
        "rowsWithAppliedReferenceSelection": summary.get("rowsWithAppliedReferenceSelection"),
        "blockedReferenceSelectionRowCount": summary.get("blockedReferenceSelectionRowCount"),
        "selectedStyleFamilyCounts": summary.get("selectedStyleFamilyCounts"),
        "choreographyRowCount": summary.get("choreographyRowCount"),
        "rowsWithChoreographyPlan": summary.get("rowsWithChoreographyPlan"),
        "rowsWithMotionExecution": summary.get("rowsWithMotionExecution"),
        "rowsWithThreeBeatMotion": summary.get("rowsWithThreeBeatMotion"),
        "rowsWithBgmHitMotion": summary.get("rowsWithBgmHitMotion"),
        "rowsWithCaptionQuietMotion": summary.get("rowsWithCaptionQuietMotion"),
        "rowsWithMotionDirectionPlan": summary.get("rowsWithMotionDirectionPlan"),
        "rowsWithMotionDirectionMatch": summary.get("rowsWithMotionDirectionMatch"),
        "rowsWithCutpointPlan": summary.get("rowsWithCutpointPlan"),
        "rowsWithCutpointReady": summary.get("rowsWithCutpointReady"),
        "rowsWithCutpointBgmHit": summary.get("rowsWithCutpointBgmHit"),
        "rowsWithCutpointLandingHold": summary.get("rowsWithCutpointLandingHold"),
        "rowsWithCutpointHandles": summary.get("rowsWithCutpointHandles"),
        "blockedCutpointRowCount": summary.get("blockedCutpointRowCount"),
        "rowsWithActionAnchorPlan": summary.get("rowsWithActionAnchorPlan"),
        "rowsWithActionAnchorReady": summary.get("rowsWithActionAnchorReady"),
        "rowsWithOutgoingActionAnchor": summary.get("rowsWithOutgoingActionAnchor"),
        "rowsWithBridgeOrMatchActionAnchor": summary.get("rowsWithBridgeOrMatchActionAnchor"),
        "rowsWithLandingActionAnchor": summary.get("rowsWithLandingActionAnchor"),
        "blockedActionAnchorRowCount": summary.get("blockedActionAnchorRowCount"),
        "rowsWithSensoryContinuityPlan": summary.get("rowsWithSensoryContinuityPlan"),
        "rowsWithSensoryContinuityReady": summary.get("rowsWithSensoryContinuityReady"),
        "rowsWithVisualSensoryContinuity": summary.get("rowsWithVisualSensoryContinuity"),
        "rowsWithAudioSensoryContinuity": summary.get("rowsWithAudioSensoryContinuity"),
        "rowsWithCaptionSensoryContinuity": summary.get("rowsWithCaptionSensoryContinuity"),
        "rowsWithRouteOrMoodSensoryContinuity": summary.get("rowsWithRouteOrMoodSensoryContinuity"),
        "rowsWithLandingSensoryContinuity": summary.get("rowsWithLandingSensoryContinuity"),
        "rowsWithMotionSensoryContinuity": summary.get("rowsWithMotionSensoryContinuity"),
        "blockedSensoryContinuityRowCount": summary.get("blockedSensoryContinuityRowCount"),
        "motionExecutionFromChoreographyCount": summary.get("motionExecutionFromChoreographyCount"),
        "motionExecutionDerivedCount": summary.get("motionExecutionDerivedCount"),
        "blockedMotionExecutionRowCount": summary.get("blockedMotionExecutionRowCount"),
        "choreographyFamilyCounts": summary.get("choreographyFamilyCounts"),
        "candidateTransitionCount": summary.get("candidateTransitionCount"),
        "candidatePlanHasReferenceSelection": bool(plan.get("sourceTransitionReferenceSelection")),
        "candidatePlanHasChoreography": bool(plan.get("sourceTransitionChoreographyPlan")),
        "rowCount": len(rows),
        "rowsMaterializedByRow": rows_materialized,
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithClipMatchByRow": rows_with_clip_match,
        "candidateTransitions": len(transitions),
        "candidateMarkers": len(markers),
        "annotatedOutClipCount": annotated_out,
        "annotatedInClipCount": annotated_in,
        "annotatedOutMotionExecutionCount": annotated_out_motion,
        "annotatedInMotionExecutionCount": annotated_in_motion,
        "transitionRowsWithDecisionFields": transition_rows_with_decisions,
        "transitionRowsWithoutForbiddenHits": transition_rows_without_forbidden,
        "transitionRowsBridgeSafe": transition_rows_bridge_safe,
        "transitionRowsMotionSafe": transition_rows_motion_safe,
        "transitionRowsWithReferenceSelectionApplied": transition_rows_with_reference_selection,
        "transitionRowsWithMotionExecution": transition_rows_with_motion_execution,
        "transitionRowsWithThreeBeatMotion": transition_rows_with_three_beat_motion,
        "transitionRowsWithBgmHitMotion": transition_rows_with_bgm_hit_motion,
        "transitionRowsWithCaptionQuietMotion": transition_rows_with_caption_quiet_motion,
        "transitionRowsWithCutpoint": transition_rows_with_cutpoint,
        "transitionRowsWithCutpointBgm": transition_rows_with_cutpoint_bgm,
        "transitionRowsWithCutpointLanding": transition_rows_with_cutpoint_landing,
        "transitionRowsWithCutpointHandles": transition_rows_with_cutpoint_handles,
        "transitionRowsWithActionAnchor": transition_rows_with_action_anchor,
        "transitionRowsWithOutgoingActionAnchor": transition_rows_with_outgoing_action_anchor,
        "transitionRowsWithBridgeMatchActionAnchor": transition_rows_with_bridge_match_action_anchor,
        "transitionRowsWithLandingActionAnchor": transition_rows_with_landing_action_anchor,
        "transitionRowsWithSensoryContinuity": transition_rows_with_sensory_continuity,
        "transitionRowsWithVisualSensory": transition_rows_with_visual_sensory,
        "transitionRowsWithAudioSensory": transition_rows_with_audio_sensory,
        "transitionRowsWithCaptionSensory": transition_rows_with_caption_sensory,
        "transitionRowsWithRouteMoodSensory": transition_rows_with_route_mood_sensory,
        "transitionRowsWithLandingSensory": transition_rows_with_landing_sensory,
        "transitionRowsWithMotionSensory": transition_rows_with_motion_sensory,
        "markerMotionExecutionCount": marker_motion,
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "mutatesActiveBlueprintByDefault": safety.get("mutatesActiveBlueprintByDefault"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def transition_execution_blueprint_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("executionRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_execution_blueprint"
        and evidence.get("candidateBlueprintExists")
        and evidence.get("candidateHasTransitionExecutionPlan")
        and row_count >= 3
        and int(evidence.get("materializedTransitionCount") or 0) == row_count
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsMaterializedByRow") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithClipMatchByRow") or 0) == row_count
        and int(evidence.get("candidateTransitionCount") or 0) == row_count
        and int(evidence.get("candidateTransitions") or 0) == row_count
        and int(evidence.get("candidateMarkers") or 0) == row_count
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("rowsMissingClipMatch") or 0) == 0
        and int(evidence.get("motionEffectRowsWithEvidence") or 0) == int(evidence.get("motionEffectRowCount") or 0)
        and int(evidence.get("bridgeSatisfiedRowCount") or 0) == int(evidence.get("bridgeRequiredRowCount") or 0)
        and int(evidence.get("referenceSelectionRowCount") or 0) >= row_count
        and int(evidence.get("rowsWithReferenceSelection") or 0) == row_count
        and int(evidence.get("rowsWithAppliedReferenceSelection") or 0) == row_count
        and int(evidence.get("blockedReferenceSelectionRowCount") or 0) == 0
        and int(evidence.get("choreographyRowCount") or 0) >= row_count
        and int(evidence.get("rowsWithChoreographyPlan") or 0) == row_count
        and int(evidence.get("rowsWithMotionExecution") or 0) == row_count
        and int(evidence.get("rowsWithThreeBeatMotion") or 0) == row_count
        and int(evidence.get("rowsWithBgmHitMotion") or 0) == row_count
        and int(evidence.get("rowsWithCaptionQuietMotion") or 0) == row_count
        and int(evidence.get("rowsWithMotionDirectionPlan") or 0) == row_count
        and int(evidence.get("rowsWithMotionDirectionMatch") or 0) == row_count
        and int(evidence.get("rowsWithCutpointPlan") or 0) == row_count
        and int(evidence.get("rowsWithCutpointReady") or 0) == row_count
        and int(evidence.get("rowsWithCutpointBgmHit") or 0) == row_count
        and int(evidence.get("rowsWithCutpointLandingHold") or 0) == row_count
        and int(evidence.get("rowsWithCutpointHandles") or 0) == row_count
        and int(evidence.get("blockedCutpointRowCount") or 0) == 0
        and int(evidence.get("rowsWithActionAnchorPlan") or 0) == row_count
        and int(evidence.get("rowsWithActionAnchorReady") or 0) == row_count
        and int(evidence.get("rowsWithOutgoingActionAnchor") or 0) == row_count
        and int(evidence.get("rowsWithBridgeOrMatchActionAnchor") or 0) == row_count
        and int(evidence.get("rowsWithLandingActionAnchor") or 0) == row_count
        and int(evidence.get("blockedActionAnchorRowCount") or 0) == 0
        and int(evidence.get("rowsWithSensoryContinuityPlan") or 0) == row_count
        and int(evidence.get("rowsWithSensoryContinuityReady") or 0) == row_count
        and int(evidence.get("rowsWithVisualSensoryContinuity") or 0) == row_count
        and int(evidence.get("rowsWithAudioSensoryContinuity") or 0) == row_count
        and int(evidence.get("rowsWithCaptionSensoryContinuity") or 0) == row_count
        and int(evidence.get("rowsWithLandingSensoryContinuity") or 0) == row_count
        and int(evidence.get("blockedSensoryContinuityRowCount") or 0) == 0
        and int(evidence.get("motionExecutionFromChoreographyCount") or 0) == row_count
        and int(evidence.get("motionExecutionDerivedCount") or 0) == 0
        and int(evidence.get("blockedMotionExecutionRowCount") or 0) == 0
        and int(evidence.get("annotatedOutClipCount") or 0) >= row_count
        and int(evidence.get("annotatedInClipCount") or 0) >= row_count
        and int(evidence.get("annotatedOutMotionExecutionCount") or 0) >= row_count
        and int(evidence.get("annotatedInMotionExecutionCount") or 0) >= row_count
        and int(evidence.get("transitionRowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("transitionRowsWithoutForbiddenHits") or 0) == row_count
        and int(evidence.get("transitionRowsBridgeSafe") or 0) == row_count
        and int(evidence.get("transitionRowsMotionSafe") or 0) == row_count
        and int(evidence.get("transitionRowsWithReferenceSelectionApplied") or 0) == row_count
        and int(evidence.get("transitionRowsWithMotionExecution") or 0) == row_count
        and int(evidence.get("transitionRowsWithThreeBeatMotion") or 0) == row_count
        and int(evidence.get("transitionRowsWithBgmHitMotion") or 0) == row_count
        and int(evidence.get("transitionRowsWithCaptionQuietMotion") or 0) == row_count
        and int(evidence.get("transitionRowsWithCutpoint") or 0) == row_count
        and int(evidence.get("transitionRowsWithCutpointBgm") or 0) == row_count
        and int(evidence.get("transitionRowsWithCutpointLanding") or 0) == row_count
        and int(evidence.get("transitionRowsWithCutpointHandles") or 0) == row_count
        and int(evidence.get("transitionRowsWithActionAnchor") or 0) == row_count
        and int(evidence.get("transitionRowsWithOutgoingActionAnchor") or 0) == row_count
        and int(evidence.get("transitionRowsWithBridgeMatchActionAnchor") or 0) == row_count
        and int(evidence.get("transitionRowsWithLandingActionAnchor") or 0) == row_count
        and int(evidence.get("transitionRowsWithSensoryContinuity") or 0) == row_count
        and int(evidence.get("transitionRowsWithVisualSensory") or 0) == row_count
        and int(evidence.get("transitionRowsWithAudioSensory") or 0) == row_count
        and int(evidence.get("transitionRowsWithCaptionSensory") or 0) == row_count
        and int(evidence.get("transitionRowsWithLandingSensory") or 0) == row_count
        and int(evidence.get("markerMotionExecutionCount") or 0) == row_count
        and evidence.get("candidatePlanHasReferenceSelection") is True
        and evidence.get("candidatePlanHasChoreography") is True
        and evidence.get("activeBlueprintUpdated") is False
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("mutatesActiveBlueprintByDefault") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def transition_motif_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_motif_plan" / "transition_motif_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("motifRows") if isinstance(data.get("motifRows"), list) else []
    repairs = data.get("repairRows") if isinstance(data.get("repairRows"), list) else []
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    decision_fields = {
        "approvedMotif",
        "approvedResolveExecutionRow",
        "selectedBridgeOrMatchEvidence",
        "bgmPhraseCue",
        "captionTitleZoneEvidence",
        "styleVariationDecision",
        "appliedInResolve",
        "timelineReadbackEvidence",
        "frameSampleEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    repair_decision_fields = {
        "acceptedRepair",
        "repairAppliedAt",
        "postRepairArtifact",
        "postRepairAudit",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    rows_with_decision_fields = 0
    rows_with_motif = 0
    rows_with_bgm = 0
    title_rows_safe = 0
    repair_rows_with_owner = 0
    repair_rows_with_decisions = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("motif"):
            rows_with_motif += 1
        if row.get("bgmPhraseCue"):
            rows_with_bgm += 1
        if row.get("boundaryCategory") != "title_boundary" or "title" in str(row.get("titleZonePolicy") or ""):
            title_rows_safe += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
    for row in repairs:
        if not isinstance(row, dict):
            continue
        if row.get("ownerScript") and row.get("requiredArtifact") and row.get("acceptanceEvidence"):
            repair_rows_with_owner += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if repair_decision_fields.issubset(set(decision)):
            repair_rows_with_decisions += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "rowsReadyWithMotif": summary.get("rowsReadyWithMotif"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsWithBgmPhraseCue": summary.get("rowsWithBgmPhraseCue"),
        "titleBoundaryRowsSafe": summary.get("titleBoundaryRowsSafe"),
        "rowsWithBridgeEvidence": summary.get("rowsWithBridgeEvidence"),
        "repeatedStyleRunMax": summary.get("repeatedStyleRunMax"),
        "repeatedStyleRunCount": summary.get("repeatedStyleRunCount"),
        "dominantMotif": summary.get("dominantMotif"),
        "dominantMotifShare": summary.get("dominantMotifShare"),
        "blockedMotifRowCount": summary.get("blockedMotifRowCount"),
        "repairRowCount": summary.get("repairRowCount"),
        "rowCount": len(rows),
        "repairRows": len(repairs),
        "rowsWithMotifByRow": rows_with_motif,
        "rowsWithBgmByRow": rows_with_bgm,
        "titleRowsSafeByRow": title_rows_safe,
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "repairRowsWithOwner": repair_rows_with_owner,
        "repairRowsWithDecisionFields": repair_rows_with_decisions,
        "filmLevelTransitionMotifsRequired": policy.get("filmLevelTransitionMotifsRequired"),
        "avoidSingleStyleDefaultChain": policy.get("avoidSingleStyleDefaultChain"),
        "physicalBridgeBeforeMotionEffect": policy.get("physicalBridgeBeforeMotionEffect"),
        "motionMotifsNeedEvidence": policy.get("motionMotifsNeedEvidence"),
        "bgmPhraseCueRequired": policy.get("bgmPhraseCueRequired"),
        "titleZoneSafetyRequired": policy.get("titleZoneSafetyRequired"),
        "templateTransitionsRejected": policy.get("templateTransitionsRejected"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def transition_motif_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("transitionRowCount") or 0)
    repair_count = int(evidence.get("repairRowCount") or 0)
    required_repair_rows = int(evidence.get("blockedMotifRowCount") or 0) + int(evidence.get("repeatedStyleRunCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_motif_plan"
        and row_count >= 3
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithMotifByRow") or 0) == row_count
        and int(evidence.get("rowsWithBgmPhraseCue") or 0) == row_count
        and int(evidence.get("rowsWithBgmByRow") or 0) == row_count
        and int(evidence.get("titleBoundaryRowsSafe") or 0) == row_count
        and int(evidence.get("titleRowsSafeByRow") or 0) == row_count
        and repair_count >= required_repair_rows
        and int(evidence.get("repairRows") or 0) == repair_count
        and int(evidence.get("repairRowsWithOwner") or 0) == repair_count
        and int(evidence.get("repairRowsWithDecisionFields") or 0) == repair_count
        and evidence.get("filmLevelTransitionMotifsRequired") is True
        and evidence.get("avoidSingleStyleDefaultChain") is True
        and evidence.get("physicalBridgeBeforeMotionEffect") is True
        and evidence.get("motionMotifsNeedEvidence") is True
        and evidence.get("bgmPhraseCueRequired") is True
        and evidence.get("titleZoneSafetyRequired") is True
        and evidence.get("templateTransitionsRejected") is True
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def transition_motif_coherence_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_motif_coherence_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "motifFamilyCount": summary.get("motifFamilyCount"),
        "minimumMotifFamilyCount": summary.get("minimumMotifFamilyCount"),
        "dominantMotif": summary.get("dominantMotif"),
        "dominantMotifShare": summary.get("dominantMotifShare"),
        "repeatedMotifRunMax": summary.get("repeatedMotifRunMax"),
        "repeatedStyleRunMax": summary.get("repeatedStyleRunMax"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantReadyBoundaryCount": summary.get("importantReadyBoundaryCount"),
        "chapterOrTimelineBoundaryCount": summary.get("chapterOrTimelineBoundaryCount"),
        "chapterOrTimelineWithBridgeMotifCount": summary.get("chapterOrTimelineWithBridgeMotifCount"),
        "motionMotifCount": summary.get("motionMotifCount"),
        "motionMotifShare": summary.get("motionMotifShare"),
        "motionSpacingViolationCount": summary.get("motionSpacingViolationCount"),
        "openingEndingMotionRowCount": summary.get("openingEndingMotionRowCount"),
        "selectionMismatchCount": summary.get("selectionMismatchCount"),
        "missingSelectionRowCount": summary.get("missingSelectionRowCount"),
        "blockingRepairRowCount": summary.get("blockingRepairRowCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "filmLevelMotifCoherenceRequired": policy.get("filmLevelMotifCoherenceRequired"),
        "referenceSelectionMustMatchMotif": policy.get("referenceSelectionMustMatchMotif"),
        "motionMotifsAreRareSpacedAccents": policy.get("motionMotifsAreRareSpacedAccents"),
        "openingEndingMotionMotifsRejected": policy.get("openingEndingMotionMotifsRejected"),
        "importantBoundariesNeedBridgeMatchDissolveOrTitleReveal": policy.get("importantBoundariesNeedBridgeMatchDissolveOrTitleReveal"),
        "unresolvedMotifRepairsBlockFinalCandidate": policy.get("unresolvedMotifRepairsBlockFinalCandidate"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_motif_coherence_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("transitionRowCount") or 0) >= 3
        and int(evidence.get("motifFamilyCount") or 0) >= int(evidence.get("minimumMotifFamilyCount") or 0)
        and float(evidence.get("dominantMotifShare") or 0.0) <= 0.6
        and int(evidence.get("repeatedMotifRunMax") or 0) <= 3
        and int(evidence.get("repeatedStyleRunMax") or 0) <= 3
        and int(evidence.get("importantReadyBoundaryCount") or 0) == int(evidence.get("importantBoundaryCount") or 0)
        and (
            int(evidence.get("chapterOrTimelineBoundaryCount") or 0) == 0
            or int(evidence.get("chapterOrTimelineWithBridgeMotifCount") or 0) >= 1
        )
        and int(evidence.get("motionSpacingViolationCount") or 0) == 0
        and int(evidence.get("openingEndingMotionRowCount") or 0) == 0
        and int(evidence.get("selectionMismatchCount") or 0) == 0
        and int(evidence.get("missingSelectionRowCount") or 0) == 0
        and int(evidence.get("blockingRepairRowCount") or 0) == 0
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("filmLevelMotifCoherenceRequired") is True
        and evidence.get("referenceSelectionMustMatchMotif") is True
        and evidence.get("motionMotifsAreRareSpacedAccents") is True
        and evidence.get("openingEndingMotionMotifsRejected") is True
        and evidence.get("importantBoundariesNeedBridgeMatchDissolveOrTitleReveal") is True
        and evidence.get("unresolvedMotifRepairsBlockFinalCandidate") is True
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def bridge_sequence_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("sequenceRows") if isinstance(data.get("sequenceRows"), list) else []
    repairs = data.get("repairRows") if isinstance(data.get("repairRows"), list) else []
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    decision_fields = {
        "approvedSequenceType",
        "selectedBeatClipPaths",
        "bridgeBeatTimelinePlacement",
        "bgmPhraseMap",
        "captionSuppressionWindows",
        "resolveBlueprintUpdate",
        "timelineReadbackEvidence",
        "frameSampleEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    repair_decision_fields = {
        "acceptedRepair",
        "repairAppliedAt",
        "postRepairArtifact",
        "postRepairAudit",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    rows_with_decision_fields = 0
    rows_with_two_to_five_beats = 0
    rows_with_bgm = 0
    rows_title_safe = 0
    rows_with_all_candidates = 0
    beat_count_by_row = 0
    beats_with_candidates = 0
    repair_rows_with_owner = 0
    repair_rows_with_decisions = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        beats = row.get("requiredBeats") if isinstance(row.get("requiredBeats"), list) else []
        if 2 <= len(beats) <= 5:
            rows_with_two_to_five_beats += 1
        beat_count_by_row += len(beats)
        candidate_count = 0
        for beat in beats:
            if isinstance(beat, dict) and beat.get("localCandidateEvidence"):
                candidate_count += 1
        beats_with_candidates += candidate_count
        if beats and candidate_count == len(beats):
            rows_with_all_candidates += 1
        if row.get("bgmPhraseCue"):
            rows_with_bgm += 1
        if row.get("titleZoneSafe"):
            rows_title_safe += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
    for row in repairs:
        if not isinstance(row, dict):
            continue
        if row.get("ownerScript") and row.get("requiredArtifact") and row.get("acceptanceEvidence"):
            repair_rows_with_owner += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if repair_decision_fields.issubset(set(decision)):
            repair_rows_with_decisions += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "sequenceRowCount": summary.get("sequenceRowCount"),
        "rowsReadyWithSequence": summary.get("rowsReadyWithSequence"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "totalRequiredBeatCount": summary.get("totalRequiredBeatCount"),
        "requiredBeatsWithLocalCandidates": summary.get("requiredBeatsWithLocalCandidates"),
        "rowsWithAllRequiredBeatCandidates": summary.get("rowsWithAllRequiredBeatCandidates"),
        "missingBeatRowCount": summary.get("missingBeatRowCount"),
        "rowsWithBgmPhraseCue": summary.get("rowsWithBgmPhraseCue"),
        "titleBoundaryRowsSafe": summary.get("titleBoundaryRowsSafe"),
        "repairRowCount": summary.get("repairRowCount"),
        "rowCount": len(rows),
        "repairRows": len(repairs),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithTwoToFiveBeatsByRow": rows_with_two_to_five_beats,
        "totalRequiredBeatCountByRow": beat_count_by_row,
        "requiredBeatsWithLocalCandidatesByRow": beats_with_candidates,
        "rowsWithAllCandidatesByRow": rows_with_all_candidates,
        "rowsWithBgmByRow": rows_with_bgm,
        "titleRowsSafeByRow": rows_title_safe,
        "repairRowsWithOwner": repair_rows_with_owner,
        "repairRowsWithDecisionFields": repair_rows_with_decisions,
        "multiShotBridgeSequencesRequired": policy.get("multiShotBridgeSequencesRequired"),
        "twoToFiveBeatBridgeShape": policy.get("twoToFiveBeatBridgeShape"),
        "localFootageFirst": policy.get("localFootageFirst"),
        "effectIsLastMileOnly": policy.get("effectIsLastMileOnly"),
        "bgmPhraseCueRequired": policy.get("bgmPhraseCueRequired"),
        "titleZoneSafetyRequired": policy.get("titleZoneSafetyRequired"),
        "noBlackCardHardJump": policy.get("noBlackCardHardJump"),
        "noRandomTransitionEffectAsBridge": policy.get("noRandomTransitionEffectAsBridge"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def bridge_sequence_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("sequenceRowCount") or 0)
    repair_count = int(evidence.get("repairRowCount") or 0)
    missing_rows = int(evidence.get("missingBeatRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_bridge_sequence_plan"
        and row_count >= 3
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithTwoToFiveBeatsByRow") or 0) == row_count
        and int(evidence.get("rowsWithBgmPhraseCue") or 0) == row_count
        and int(evidence.get("rowsWithBgmByRow") or 0) == row_count
        and int(evidence.get("titleBoundaryRowsSafe") or 0) == row_count
        and int(evidence.get("titleRowsSafeByRow") or 0) == row_count
        and int(evidence.get("totalRequiredBeatCount") or 0) == int(evidence.get("totalRequiredBeatCountByRow") or 0)
        and int(evidence.get("requiredBeatsWithLocalCandidates") or 0) == int(evidence.get("requiredBeatsWithLocalCandidatesByRow") or 0)
        and int(evidence.get("rowsWithAllRequiredBeatCandidates") or 0) == int(evidence.get("rowsWithAllCandidatesByRow") or 0)
        and repair_count >= missing_rows
        and int(evidence.get("repairRows") or 0) == repair_count
        and int(evidence.get("repairRowsWithOwner") or 0) == repair_count
        and int(evidence.get("repairRowsWithDecisionFields") or 0) == repair_count
        and evidence.get("multiShotBridgeSequencesRequired") is True
        and evidence.get("twoToFiveBeatBridgeShape") is True
        and evidence.get("localFootageFirst") is True
        and evidence.get("effectIsLastMileOnly") is True
        and evidence.get("bgmPhraseCueRequired") is True
        and evidence.get("titleZoneSafetyRequired") is True
        and evidence.get("noBlackCardHardJump") is True
        and evidence.get("noRandomTransitionEffectAsBridge") is True
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def bridge_sequence_blueprint_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    rows = data.get("materializedRows") if isinstance(data.get("materializedRows"), list) else []
    candidate_path = Path(str(outputs.get("candidateBlueprint") or package_dir / "bridge_sequence_blueprint" / "resolve_timeline_blueprint_bridge_sequence.json"))
    candidate = load_json(candidate_path) or {}
    clips = candidate.get("clips") if isinstance(candidate.get("clips"), list) else []
    overlay_track = int(summary.get("overlayTrackIndex") or 0)
    insert_clips = [
        clip for clip in clips
        if isinstance(clip, dict) and clip.get("role") == "bridge_sequence_insert"
    ]
    decision_fields = {
        "approveCandidateBlueprint",
        "selectedBridgeBeatRows",
        "resolveImplementation",
        "preflightEvidence",
        "timelineReadbackEvidence",
        "frameSampleEvidence",
        "approvedBy",
        "approvedAt",
        "editorNotes",
    }
    rows_with_decision_fields = 0
    rows_materialized = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "materialized":
            rows_materialized += 1
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "candidateBlueprint": str(candidate_path),
        "candidateBlueprintExists": candidate_path.exists(),
        "candidateHasBridgeSequencePlan": isinstance(candidate.get("bridgeSequenceBlueprintPlan"), dict),
        "sequenceRowCount": summary.get("sequenceRowCount"),
        "materializedRowCount": summary.get("materializedRowCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "insertedBeatClipCount": summary.get("insertedBeatClipCount"),
        "missingBeatRowCount": summary.get("missingBeatRowCount"),
        "missingBeatCount": summary.get("missingBeatCount"),
        "incompleteRowCount": summary.get("incompleteRowCount"),
        "overlayTrackIndex": overlay_track,
        "candidateClipCount": summary.get("candidateClipCount"),
        "sourceClipCount": summary.get("sourceClipCount"),
        "materializedRows": len(rows),
        "rowsMaterializedByRow": rows_materialized,
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "candidateBridgeSequenceInsertClipCount": len(insert_clips),
        "insertClipsVideoOnly": all(clip.get("includeSourceAudio") is False for clip in insert_clips),
        "insertClipsOnOverlayTrack": all(int(clip.get("trackIndex") or -1) == overlay_track for clip in insert_clips),
        "insertClipsHaveBeatMetadata": all(isinstance(clip.get("bridgeSequence"), dict) and clip["bridgeSequence"].get("beatFunction") for clip in insert_clips),
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "mutatesActiveBlueprintByDefault": safety.get("mutatesActiveBlueprintByDefault"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def bridge_sequence_blueprint_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("sequenceRowCount") or 0)
    inserted_count = int(evidence.get("insertedBeatClipCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_bridge_sequence_blueprint"
        and evidence.get("candidateBlueprintExists")
        and evidence.get("candidateHasBridgeSequencePlan")
        and row_count >= 3
        and int(evidence.get("materializedRowCount") or 0) == row_count
        and int(evidence.get("materializedRows") or 0) == row_count
        and int(evidence.get("rowsMaterializedByRow") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and inserted_count > 0
        and int(evidence.get("candidateBridgeSequenceInsertClipCount") or 0) == inserted_count
        and int(evidence.get("missingBeatRowCount") or 0) == 0
        and int(evidence.get("missingBeatCount") or 0) == 0
        and int(evidence.get("incompleteRowCount") or 0) == 0
        and int(evidence.get("overlayTrackIndex") or 0) >= 2
        and evidence.get("insertClipsVideoOnly") is True
        and evidence.get("insertClipsOnOverlayTrack") is True
        and evidence.get("insertClipsHaveBeatMetadata") is True
        and evidence.get("activeBlueprintUpdated") is False
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("mutatesActiveBlueprintByDefault") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def bridge_sequence_application_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "bridge_sequence_application_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprint": inputs.get("blueprint"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "bridgeSequencePlanStatus": inputs.get("bridgeSequencePlanStatus"),
        "bridgeSequenceBlueprintStatus": inputs.get("bridgeSequenceBlueprintStatus"),
        "plannedSequenceRowCount": summary.get("plannedSequenceRowCount"),
        "requiredSequenceRowCount": summary.get("requiredSequenceRowCount"),
        "auditedSequenceRowCount": summary.get("auditedSequenceRowCount"),
        "passedSequenceRowCount": summary.get("passedSequenceRowCount"),
        "blockedSequenceRowCount": summary.get("blockedSequenceRowCount"),
        "expectedBeatClipCount": summary.get("expectedBeatClipCount"),
        "appliedBeatClipCount": summary.get("appliedBeatClipCount"),
        "missingBeatClipCount": summary.get("missingBeatClipCount"),
        "finalBridgeInsertClipCount": summary.get("finalBridgeInsertClipCount"),
        "sourceAudioLeakClipCount": summary.get("sourceAudioLeakClipCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def bridge_sequence_application_contract_ready(evidence: dict[str, Any]) -> bool:
    required_count = int(evidence.get("requiredSequenceRowCount") or 0)
    expected_count = int(evidence.get("expectedBeatClipCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and evidence.get("bridgeSequencePlanStatus") == "ready_with_bridge_sequence_plan"
        and evidence.get("bridgeSequenceBlueprintStatus") == "ready_with_bridge_sequence_blueprint"
        and required_count >= 3
        and int(evidence.get("auditedSequenceRowCount") or 0) == required_count
        and int(evidence.get("passedSequenceRowCount") or 0) == required_count
        and int(evidence.get("blockedSequenceRowCount") or 0) == 0
        and expected_count > 0
        and int(evidence.get("appliedBeatClipCount") or 0) >= expected_count
        and int(evidence.get("missingBeatClipCount") or 0) == 0
        and int(evidence.get("finalBridgeInsertClipCount") or 0) >= expected_count
        and int(evidence.get("sourceAudioLeakClipCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_bridge_visual_evidence_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_bridge_visual_evidence_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprint": inputs.get("blueprint"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "bridgeSequencePlanStatus": inputs.get("bridgeSequencePlanStatus"),
        "bridgeSequenceBlueprintStatus": inputs.get("bridgeSequenceBlueprintStatus"),
        "bridgeSequenceApplicationStatus": inputs.get("bridgeSequenceApplicationStatus"),
        "requiredBridgeRowCount": summary.get("requiredBridgeRowCount"),
        "auditedBridgeRowCount": summary.get("auditedBridgeRowCount"),
        "passedBridgeRowCount": summary.get("passedBridgeRowCount"),
        "blockedBridgeRowCount": summary.get("blockedBridgeRowCount"),
        "expectedBeatClipCount": summary.get("expectedBeatClipCount"),
        "appliedBeatClipCount": summary.get("appliedBeatClipCount"),
        "passedBridgeVisualClipCount": summary.get("passedBridgeVisualClipCount"),
        "blockedBridgeVisualClipCount": summary.get("blockedBridgeVisualClipCount"),
        "missingBeatClipCount": summary.get("missingBeatClipCount"),
        "frameEvidenceCount": summary.get("frameEvidenceCount"),
        "videoProbeReadyCount": summary.get("videoProbeReadyCount"),
        "distinctBridgeSourceCount": summary.get("distinctBridgeSourceCount"),
        "sourceAudioLeakClipCount": summary.get("sourceAudioLeakClipCount"),
        "blockerCount": summary.get("blockerCount"),
        "warningCount": summary.get("warningCount"),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_bridge_visual_evidence_contract_ready(evidence: dict[str, Any]) -> bool:
    required_count = int(evidence.get("requiredBridgeRowCount") or 0)
    expected_count = int(evidence.get("expectedBeatClipCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and evidence.get("bridgeSequencePlanStatus") == "ready_with_bridge_sequence_plan"
        and evidence.get("bridgeSequenceBlueprintStatus") == "ready_with_bridge_sequence_blueprint"
        and evidence.get("bridgeSequenceApplicationStatus") == "passed"
        and required_count >= 3
        and int(evidence.get("auditedBridgeRowCount") or 0) == required_count
        and int(evidence.get("passedBridgeRowCount") or 0) == required_count
        and int(evidence.get("blockedBridgeRowCount") or 0) == 0
        and expected_count > 0
        and int(evidence.get("appliedBeatClipCount") or 0) >= expected_count
        and int(evidence.get("passedBridgeVisualClipCount") or 0) >= expected_count
        and int(evidence.get("blockedBridgeVisualClipCount") or 0) == 0
        and int(evidence.get("missingBeatClipCount") or 0) == 0
        and int(evidence.get("frameEvidenceCount") or 0) >= expected_count
        and int(evidence.get("videoProbeReadyCount") or 0) >= expected_count
        and int(evidence.get("sourceAudioLeakClipCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def final_blueprint_lineage_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "final_blueprint_lineage_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    stages = data.get("stages") if isinstance(data.get("stages"), list) else []
    passed_stages = [
        row for row in stages
        if isinstance(row, dict) and row.get("status") == "passed"
    ]
    stages_with_plan = [
        row for row in stages
        if isinstance(row, dict) and row.get("ready") and row.get("finalHasPlanKey") is True
    ]
    stages_inside_package = [
        row for row in stages
        if isinstance(row, dict) and row.get("ready") and row.get("candidateBlueprintInsidePackage") is True
    ]
    count_preserved = [
        row for row in stages
        if isinstance(row, dict)
        and row.get("ready")
        and int(row.get("finalCount") or 0) >= int(row.get("sourceCount") or 0)
    ]
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "finalBlueprint": inputs.get("finalBlueprint"),
        "finalBlueprintExists": inputs.get("finalBlueprintExists"),
        "finalBlueprintKind": inputs.get("finalBlueprintKind"),
        "finalBlueprintInsidePackage": inputs.get("finalBlueprintInsidePackage"),
        "minimumReadyStages": inputs.get("minimumReadyStages"),
        "configuredStageCount": summary.get("configuredStageCount"),
        "readyStageCount": summary.get("readyStageCount"),
        "passedStageCount": summary.get("passedStageCount"),
        "blockedReadyStageCount": summary.get("blockedReadyStageCount"),
        "finalPlanKeyCount": summary.get("finalPlanKeyCount"),
        "requiredMinimumReadyStages": summary.get("requiredMinimumReadyStages"),
        "blockerCount": summary.get("blockerCount"),
        "stageCount": len(stages),
        "passedStagesByRow": len(passed_stages),
        "readyStagesWithPlanKey": len(stages_with_plan),
        "readyStagesInsidePackage": len(stages_inside_package),
        "readyStagesWithCountsPreserved": len(count_preserved),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def final_blueprint_lineage_contract_ready(evidence: dict[str, Any]) -> bool:
    required = int(evidence.get("requiredMinimumReadyStages") or evidence.get("minimumReadyStages") or 5)
    ready = int(evidence.get("readyStageCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("finalBlueprintExists") is True
        and evidence.get("finalBlueprintInsidePackage") is True
        and ready >= required
        and int(evidence.get("passedStageCount") or 0) >= required
        and int(evidence.get("blockedReadyStageCount") or 0) == 0
        and int(evidence.get("finalPlanKeyCount") or 0) >= required
        and int(evidence.get("passedStagesByRow") or 0) >= required
        and int(evidence.get("readyStagesWithPlanKey") or 0) >= required
        and int(evidence.get("readyStagesInsidePackage") or 0) >= required
        and int(evidence.get("readyStagesWithCountsPreserved") or 0) >= required
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def final_source_usage_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "final_source_usage_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprint": inputs.get("blueprint"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "footageSelectPlanExists": inputs.get("footageSelectPlanExists"),
        "footageSelectStatus": inputs.get("footageSelectStatus"),
        "visualClipCount": summary.get("visualClipCount"),
        "rawSourceClipCount": summary.get("rawSourceClipCount"),
        "matchedRawSourceClipCount": summary.get("matchedRawSourceClipCount"),
        "unmatchedRawSourceClipCount": summary.get("unmatchedRawSourceClipCount"),
        "selectedCandidateClipCount": summary.get("selectedCandidateClipCount"),
        "utilityClipCount": summary.get("utilityClipCount"),
        "rejectOrRepairActiveClipCount": summary.get("rejectOrRepairActiveClipCount"),
        "uniqueSourceCount": summary.get("uniqueSourceCount"),
        "sameSourceRunMax": summary.get("sameSourceRunMax"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "blockerCount": len(data.get("blockers") or []),
        "warnings": data.get("warnings") or [],
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def final_source_usage_contract_ready(evidence: dict[str, Any]) -> bool:
    raw_count = int(evidence.get("rawSourceClipCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and evidence.get("footageSelectPlanExists") is True
        and evidence.get("footageSelectStatus") in {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"}
        and raw_count >= 1
        and int(evidence.get("matchedRawSourceClipCount") or 0) == raw_count
        and int(evidence.get("unmatchedRawSourceClipCount") or 0) == 0
        and int(evidence.get("selectedCandidateClipCount") or 0) >= 1
        and int(evidence.get("rejectOrRepairActiveClipCount") or 0) == 0
        and int(evidence.get("chaptersBlocked") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def reference_style_repair_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    rows = data.get("repairRows") if isinstance(data.get("repairRows"), list) else []
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    decision_fields = {
        "acceptedRepair",
        "repairOwner",
        "repairAppliedAt",
        "resolveBlueprintEvidence",
        "resolveTimelineReadback",
        "renderFrameSampleEvidence",
        "postRepairAudit",
    }
    rows_with_decision_fields = 0
    rows_with_owner_script = 0
    rows_with_required_artifact = 0
    rows_with_acceptance = 0
    p0_rows = 0
    safe_rows = 0
    area_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        if row.get("ownerScript"):
            rows_with_owner_script += 1
        if row.get("requiredArtifact"):
            rows_with_required_artifact += 1
        if row.get("acceptanceEvidence") and row.get("repairAction"):
            rows_with_acceptance += 1
        if row.get("priority") == "P0":
            p0_rows += 1
        if (row.get("safety") or {}).get("writesResolve") is False:
            safe_rows += 1
        area = str(row.get("area") or "")
        if area:
            area_counts[area] = area_counts.get(area, 0) + 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "repairRowCount": summary.get("repairRowCount"),
        "p0RepairRowCount": summary.get("p0RepairRowCount"),
        "areaCounts": summary.get("areaCounts") or area_counts,
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "safeNoWriteRows": summary.get("safeNoWriteRows"),
        "rowCount": len(rows),
        "rowsWithDecisionFieldsByRow": rows_with_decision_fields,
        "rowsWithOwnerScript": rows_with_owner_script,
        "rowsWithRequiredArtifact": rows_with_required_artifact,
        "rowsWithAcceptanceEvidence": rows_with_acceptance,
        "p0RowsByRow": p0_rows,
        "safeRowsByRow": safe_rows,
        "referenceProfileAvailable": summary.get("referenceProfileAvailable"),
        "referenceAverageShotLengthSeconds": summary.get("referenceAverageShotLengthSeconds"),
        "referenceMedianShotLengthSeconds": summary.get("referenceMedianShotLengthSeconds"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def reference_style_repair_plan_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("repairRowCount") or 0)
    if evidence.get("status") == "ready_no_reference_style_repairs_needed":
        return (
            evidence.get("exists")
            and row_count == 0
            and evidence.get("writesResolve") is False
            and evidence.get("queuesRender") is False
            and evidence.get("downloadsExternalAssets") is False
            and evidence.get("modifiesSourceFootage") is False
            and evidence.get("hasPassRubric") is True
            and evidence.get("hasRejectRubric") is True
        )
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_reference_style_repair_plan"
        and row_count >= 1
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithOwnerScript") or 0) == row_count
        and int(evidence.get("rowsWithRequiredArtifact") or 0) == row_count
        and int(evidence.get("rowsWithAcceptanceEvidence") or 0) == row_count
        and int(evidence.get("safeNoWriteRows") or 0) == row_count
        and int(evidence.get("safeRowsByRow") or 0) == row_count
        and int(evidence.get("p0RepairRowCount") or 0) == int(evidence.get("p0RowsByRow") or 0)
        and bool(evidence.get("areaCounts"))
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def reference_repair_closure_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "reference_repair_closure_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rows = data.get("closureRows") if isinstance(data.get("closureRows"), list) else []
    row_count = len([row for row in rows if isinstance(row, dict)])
    p0_rows = [row for row in rows if isinstance(row, dict) and row.get("priority") == "P0"]
    closed_rows = [row for row in rows if isinstance(row, dict) and row.get("status") == "closed"]
    p0_closed_rows = [row for row in p0_rows if row.get("status") == "closed"]
    rows_with_owner = sum(1 for row in rows if isinstance(row, dict) and row.get("ownerScriptExists") is True)
    rows_with_artifact = sum(1 for row in rows if isinstance(row, dict) and row.get("requiredArtifactExists") is True)
    rows_with_evidence = sum(1 for row in rows if isinstance(row, dict) and row.get("hasReadbackOrFrameSample") is True)
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "referenceStyleRepairPlanExists": inputs.get("referenceStyleRepairPlanExists"),
        "referenceStyleRepairPlanStatus": inputs.get("referenceStyleRepairPlanStatus"),
        "repairRowCount": summary.get("repairRowCount"),
        "p0RepairRowCount": summary.get("p0RepairRowCount"),
        "closedRowCount": summary.get("closedRowCount"),
        "p0ClosedRowCount": summary.get("p0ClosedRowCount"),
        "needsEditorEvidenceRowCount": summary.get("needsEditorEvidenceRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "rowCount": row_count,
        "p0RowsByRow": len(p0_rows),
        "closedRowsByRow": len(closed_rows),
        "p0ClosedRowsByRow": len(p0_closed_rows),
        "rowsWithOwnerScript": rows_with_owner,
        "rowsWithArtifact": rows_with_artifact,
        "rowsWithEvidence": rows_with_evidence,
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def reference_repair_closure_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("repairRowCount") or 0)
    p0_count = int(evidence.get("p0RepairRowCount") or 0)
    if evidence.get("referenceStyleRepairPlanStatus") == "ready_no_reference_style_repairs_needed":
        return (
            evidence.get("exists")
            and evidence.get("status") == "passed"
            and row_count == 0
            and int(evidence.get("blockedRowCount") or 0) == 0
            and evidence.get("writesResolve") is False
            and evidence.get("queuesRender") is False
            and evidence.get("downloadsExternalAssets") is False
            and evidence.get("modifiesSourceFootage") is False
        )
    return (
        evidence.get("exists")
        and evidence.get("referenceStyleRepairPlanExists") is True
        and evidence.get("status") in {"passed", "passed_with_evidence_warnings"}
        and row_count >= 1
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("p0RowsByRow") or 0) == p0_count
        and int(evidence.get("closedRowCount") or 0) == int(evidence.get("closedRowsByRow") or 0)
        and int(evidence.get("p0ClosedRowCount") or 0) == p0_count
        and int(evidence.get("p0ClosedRowsByRow") or 0) == p0_count
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and int(evidence.get("rowsWithOwnerScript") or 0) == row_count
        and int(evidence.get("rowsWithArtifact") or 0) == row_count
        and int(evidence.get("rowsWithEvidence") or 0) >= p0_count
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def rhythm_recut_blueprint_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    rows = data.get("recutRows") if isinstance(data.get("recutRows"), list) else []
    candidate = Path(str(outputs.get("candidateBlueprint") or ""))
    candidate_data = load_json(candidate) or {}
    candidate_plan = candidate_data.get("rhythmRecutPlan") if isinstance(candidate_data.get("rhythmRecutPlan"), dict) else {}
    candidate_clips = candidate_data.get("clips") if isinstance(candidate_data.get("clips"), list) else []
    candidate_transitions = candidate_data.get("transitions") if isinstance(candidate_data.get("transitions"), list) else []
    candidate_bgm_rows = candidate_data.get("bgmPhraseCandidates") if isinstance(candidate_data.get("bgmPhraseCandidates"), list) else []
    candidate_bgm_clip_annotations = sum(len(clip.get("bgmPhraseCandidates") or []) for clip in candidate_clips if isinstance(clip, dict) and isinstance(clip.get("bgmPhraseCandidates"), list))
    candidate_bgm_transition_cues = sum(1 for transition in candidate_transitions if isinstance(transition, dict) and isinstance(transition.get("bgmPhraseCandidate"), dict))
    decision_fields = {
        "approveCandidateBlueprint",
        "selectedCutawaySource",
        "replacementOrInsertSource",
        "resolveImplementation",
        "readbackEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_decision_fields = 0
    rows_with_cutaways = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decision_fields += 1
        if int(row.get("cutawayInsertCount") or 0) > 0:
            rows_with_cutaways += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "baseBlueprintKind": inputs.get("baseBlueprintKind"),
        "candidateHasRhythmRecutPlan": isinstance(candidate_data.get("rhythmRecutPlan"), dict),
        "candidateSourceBlueprintKind": candidate_plan.get("sourceBlueprintKind"),
        "candidateHasBgmPhrasePlan": isinstance(candidate_data.get("bgmPhraseBlueprintPlan"), dict),
        "candidateBlueprint": str(candidate) if outputs.get("candidateBlueprint") else None,
        "candidateBlueprintExists": candidate.exists() if outputs.get("candidateBlueprint") else False,
        "originalClipCount": summary.get("originalClipCount"),
        "revisedClipCount": summary.get("revisedClipCount"),
        "originalPrimaryClipCount": summary.get("originalPrimaryClipCount"),
        "revisedPrimaryClipCount": summary.get("revisedPrimaryClipCount"),
        "longEditableClipCount": summary.get("longEditableClipCount"),
        "splitSourceClipCount": summary.get("splitSourceClipCount"),
        "cutawayInsertCount": summary.get("cutawayInsertCount"),
        "cutawayPoolCount": summary.get("cutawayPoolCount"),
        "keptLongClipCount": summary.get("keptLongClipCount"),
        "averagePrimaryShotBeforeSeconds": summary.get("averagePrimaryShotBeforeSeconds"),
        "averagePrimaryShotAfterSeconds": summary.get("averagePrimaryShotAfterSeconds"),
        "medianPrimaryShotBeforeSeconds": summary.get("medianPrimaryShotBeforeSeconds"),
        "medianPrimaryShotAfterSeconds": summary.get("medianPrimaryShotAfterSeconds"),
        "longShotRiskBefore": summary.get("longShotRiskBefore"),
        "longShotRiskAfter": summary.get("longShotRiskAfter"),
        "durationDeltaSeconds": summary.get("durationDeltaSeconds"),
        "targetAverageUpperSeconds": summary.get("targetAverageUpperSeconds"),
        "longShotSoftLimitSeconds": summary.get("longShotSoftLimitSeconds"),
        "bgmPhraseCandidateCount": summary.get("bgmPhraseCandidateCount"),
        "bgmPhraseClipAnnotationCount": summary.get("bgmPhraseClipAnnotationCount"),
        "bgmPhraseTransitionCueCount": summary.get("bgmPhraseTransitionCueCount"),
        "bgmPhrasePlanPreserved": summary.get("bgmPhrasePlanPreserved"),
        "candidateBgmPhraseCandidateCount": len(candidate_bgm_rows),
        "candidateBgmPhraseClipAnnotationCount": candidate_bgm_clip_annotations,
        "candidateBgmPhraseTransitionCueCount": candidate_bgm_transition_cues,
        "recutRowCount": len(rows),
        "rowsWithDecisionFields": rows_with_decision_fields,
        "rowsWithCutaways": rows_with_cutaways,
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "writesResolve": safety.get("writesResolve"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesOriginalBlueprintByDefault": safety.get("modifiesOriginalBlueprintByDefault"),
        "requiresResolvePreflightBeforeApply": safety.get("requiresResolvePreflightBeforeApply"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def rhythm_recut_blueprint_ready(evidence: dict[str, Any]) -> bool:
    status = evidence.get("status")
    long_count = int(evidence.get("longEditableClipCount") or 0)
    split_count = int(evidence.get("splitSourceClipCount") or 0)
    cutaway_count = int(evidence.get("cutawayInsertCount") or 0)
    recut_rows = int(evidence.get("recutRowCount") or 0)
    no_recut_needed = status == "ready_no_recut_needed" and long_count == 0
    improved_recut = (
        status == "ready_with_rhythm_recut_blueprint"
        and long_count > 0
        and split_count > 0
        and cutaway_count > 0
        and int(evidence.get("rowsWithCutaways") or 0) == recut_rows
        and float(evidence.get("averagePrimaryShotAfterSeconds") or 0) < float(evidence.get("averagePrimaryShotBeforeSeconds") or 0)
        and int(evidence.get("longShotRiskAfter") or 0) < int(evidence.get("longShotRiskBefore") or 0)
    )
    return (
        evidence.get("exists")
        and evidence.get("candidateBlueprintExists") is True
        and evidence.get("baseBlueprintKind") == "bgm_phrase_candidate"
        and evidence.get("candidateHasRhythmRecutPlan") is True
        and evidence.get("candidateSourceBlueprintKind") == "bgm_phrase_candidate"
        and evidence.get("candidateHasBgmPhrasePlan") is True
        and evidence.get("bgmPhrasePlanPreserved") is True
        and int(evidence.get("bgmPhraseCandidateCount") or 0) >= 4
        and int(evidence.get("bgmPhraseCandidateCount") or 0) == int(evidence.get("candidateBgmPhraseCandidateCount") or 0)
        and int(evidence.get("bgmPhraseClipAnnotationCount") or 0) == int(evidence.get("candidateBgmPhraseClipAnnotationCount") or 0)
        and int(evidence.get("bgmPhraseClipAnnotationCount") or 0) >= int(evidence.get("bgmPhraseCandidateCount") or 0)
        and int(evidence.get("bgmPhraseTransitionCueCount") or 0) == int(evidence.get("candidateBgmPhraseTransitionCueCount") or 0)
        and int(evidence.get("bgmPhraseTransitionCueCount") or 0) >= 1
        and (improved_recut or no_recut_needed)
        and int(evidence.get("rowsWithDecisionFields") or 0) == recut_rows
        and abs(float(evidence.get("durationDeltaSeconds") or 0.0)) <= 0.5
        and float(evidence.get("targetAverageUpperSeconds") or 0) > 0
        and float(evidence.get("longShotSoftLimitSeconds") or 0) > 0
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("writesResolve") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesOriginalBlueprintByDefault") is False
        and evidence.get("requiresResolvePreflightBeforeApply") is True
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def transition_polish_blueprint_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rubric = data.get("selectionRubric") if isinstance(data.get("selectionRubric"), dict) else {}
    rows = data.get("polishRows") if isinstance(data.get("polishRows"), list) else []
    candidate = Path(str(outputs.get("candidateBlueprint") or ""))
    candidate_data = load_json(candidate) or {}
    candidate_plan = candidate_data.get("transitionPolishBlueprintPlan") if isinstance(candidate_data.get("transitionPolishBlueprintPlan"), dict) else {}
    transitions = candidate_data.get("transitions") if isinstance(candidate_data.get("transitions"), list) else []
    candidates = candidate_data.get("transitionPolishCandidates") if isinstance(candidate_data.get("transitionPolishCandidates"), list) else []
    clips = candidate_data.get("clips") if isinstance(candidate_data.get("clips"), list) else []
    markers = [
        marker for marker in candidate_data.get("timelineMarkers", [])
        if isinstance(marker, dict) and marker.get("role") == "transition_polish_candidate_marker"
    ] if isinstance(candidate_data.get("timelineMarkers"), list) else []
    clip_annotations = sum(
        len(clip.get("transitionPolishOut") or []) + len(clip.get("transitionPolishIn") or [])
        for clip in clips
        if isinstance(clip, dict)
    )
    transition_annotations = sum(1 for transition in transitions if isinstance(transition, dict) and isinstance(transition.get("transitionPolishCandidate"), dict))
    decision_fields = {
        "approveCandidateBlueprint",
        "approvedPolishRows",
        "resolveImplementation",
        "preflightEvidence",
        "timelineReadbackEvidence",
        "frameSampleEvidence",
        "approvedBy",
        "approvedAt",
    }
    rows_with_decisions = 0
    rows_with_bgm = 0
    rows_with_hit = 0
    rows_title_safe = 0
    rows_blocked = 0
    rows_forbidden = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        bgm = row.get("bgmSync") if isinstance(row.get("bgmSync"), dict) else {}
        title = row.get("titleSubtitleAvoidance") if isinstance(row.get("titleSubtitleAvoidance"), dict) else {}
        if decision_fields.issubset(set(decision)):
            rows_with_decisions += 1
        if bgm.get("phraseIndex") is not None or bgm.get("section"):
            rows_with_bgm += 1
        if bgm.get("hitSeconds") is not None:
            rows_with_hit += 1
        if title.get("avoidTitleOverlayCollision") is True and float(title.get("suppressSubtitleSecondsBefore") or 0) > 0:
            rows_title_safe += 1
        if row.get("status") != "materialized":
            rows_blocked += 1
        rows_forbidden += len(row.get("forbiddenPolishHits") or [])
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "baseBlueprintKind": inputs.get("baseBlueprintKind"),
        "candidateBlueprint": str(candidate) if outputs.get("candidateBlueprint") else None,
        "candidateBlueprintExists": candidate.exists() if outputs.get("candidateBlueprint") else False,
        "candidateHasTransitionPolishPlan": isinstance(candidate_data.get("transitionPolishBlueprintPlan"), dict),
        "candidateSourceBlueprintKind": candidate_plan.get("baseBlueprintKind"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "polishedTransitionCount": summary.get("polishedTransitionCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsWithBgmPhraseCue": summary.get("rowsWithBgmPhraseCue"),
        "rowsWithBgmHit": summary.get("rowsWithBgmHit"),
        "rowsWithTitleSubtitleAvoidance": summary.get("rowsWithTitleSubtitleAvoidance"),
        "motionPolishRowCount": summary.get("motionPolishRowCount"),
        "motionPolishRowsWithEvidence": summary.get("motionPolishRowsWithEvidence"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "clipAnnotationCount": summary.get("clipAnnotationCount"),
        "markerCount": summary.get("markerCount"),
        "candidateBgmPhraseCount": summary.get("candidateBgmPhraseCount"),
        "rowCount": len(rows),
        "candidateTransitionPolishCount": len(candidates),
        "transitionAnnotations": transition_annotations,
        "candidateClipAnnotationCount": clip_annotations,
        "candidateMarkerCount": len(markers),
        "rowsWithDecisionFieldsByRow": rows_with_decisions,
        "rowsWithBgmByRow": rows_with_bgm,
        "rowsWithHitByRow": rows_with_hit,
        "rowsTitleSafeByRow": rows_title_safe,
        "blockedRowsByRow": rows_blocked,
        "forbiddenHitCountByRow": rows_forbidden,
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "mutatesActiveBlueprintByDefault": safety.get("mutatesActiveBlueprintByDefault"),
        "requiresResolvePreflightBeforeApply": safety.get("requiresResolvePreflightBeforeApply"),
        "hasPassRubric": bool(rubric.get("pass")),
        "hasRejectRubric": bool(rubric.get("reject")),
    }


def transition_polish_blueprint_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("transitionRowCount") or 0)
    motion_rows = int(evidence.get("motionPolishRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_polish_blueprint"
        and evidence.get("baseBlueprintKind") in {"rhythm_recut_candidate", "bgm_phrase_candidate"}
        and evidence.get("candidateBlueprintExists") is True
        and evidence.get("candidateHasTransitionPolishPlan") is True
        and evidence.get("candidateSourceBlueprintKind") == evidence.get("baseBlueprintKind")
        and row_count >= 1
        and int(evidence.get("polishedTransitionCount") or 0) == row_count
        and int(evidence.get("rowCount") or 0) == row_count
        and int(evidence.get("candidateTransitionPolishCount") or 0) == row_count
        and int(evidence.get("transitionAnnotations") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFields") or 0) == row_count
        and int(evidence.get("rowsWithDecisionFieldsByRow") or 0) == row_count
        and int(evidence.get("rowsWithBgmPhraseCue") or 0) == row_count
        and int(evidence.get("rowsWithBgmByRow") or 0) == row_count
        and int(evidence.get("rowsWithBgmHit") or 0) == row_count
        and int(evidence.get("rowsWithHitByRow") or 0) == row_count
        and int(evidence.get("rowsWithTitleSubtitleAvoidance") or 0) == row_count
        and int(evidence.get("rowsTitleSafeByRow") or 0) == row_count
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("blockedRowsByRow") or 0) == 0
        and int(evidence.get("forbiddenHitCountByRow") or 0) == 0
        and int(evidence.get("motionPolishRowsWithEvidence") or 0) == motion_rows
        and int(evidence.get("clipAnnotationCount") or 0) >= row_count
        and int(evidence.get("candidateClipAnnotationCount") or 0) >= row_count
        and int(evidence.get("markerCount") or 0) == row_count
        and int(evidence.get("candidateMarkerCount") or 0) == row_count
        and int(evidence.get("candidateBgmPhraseCount") or 0) >= 4
        and evidence.get("activeBlueprintUpdated") is False
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("mutatesActiveBlueprintByDefault") is False
        and evidence.get("requiresResolvePreflightBeforeApply") is True
        and evidence.get("hasPassRubric") is True
        and evidence.get("hasRejectRubric") is True
    )


def transition_quality_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_quality_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "visualClipCount": summary.get("visualClipCount"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "transitionCoverageRatio": summary.get("transitionCoverageRatio"),
        "rowsWithBgmHit": summary.get("rowsWithBgmHit"),
        "rowsTitleSafe": summary.get("rowsTitleSafe"),
        "rowsWithKeyframesOrCleanCut": summary.get("rowsWithKeyframesOrCleanCut"),
        "bgmOnlyAudioRows": summary.get("bgmOnlyAudioRows"),
        "motionRowCount": summary.get("motionRowCount"),
        "motionRowsWithEvidence": summary.get("motionRowsWithEvidence"),
        "craftedTransitionCount": summary.get("craftedTransitionCount"),
        "minimumCraftedTransitionCount": summary.get("minimumCraftedTransitionCount"),
        "bridgeRequiredRows": summary.get("bridgeRequiredRows"),
        "bridgeSatisfiedRows": summary.get("bridgeSatisfiedRows"),
        "forbiddenHitCount": summary.get("forbiddenHitCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def transition_quality_contract_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("transitionRowCount") or 0)
    boundary_count = int(evidence.get("visualBoundaryCount") or 0)
    motion_rows = int(evidence.get("motionRowCount") or 0)
    bridge_rows = int(evidence.get("bridgeRequiredRows") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintKind") == "transition_polish_candidate"
        and evidence.get("blueprintExists") is True
        and row_count > 0
        and row_count >= boundary_count
        and float(evidence.get("transitionCoverageRatio") or 0) >= 1.0
        and int(evidence.get("rowsWithBgmHit") or 0) == row_count
        and int(evidence.get("rowsTitleSafe") or 0) == row_count
        and int(evidence.get("rowsWithKeyframesOrCleanCut") or 0) == row_count
        and int(evidence.get("bgmOnlyAudioRows") or 0) == row_count
        and int(evidence.get("motionRowsWithEvidence") or 0) == motion_rows
        and int(evidence.get("craftedTransitionCount") or 0) >= int(evidence.get("minimumCraftedTransitionCount") or 0)
        and int(evidence.get("bridgeSatisfiedRows") or 0) == bridge_rows
        and int(evidence.get("forbiddenHitCount") or 0) == 0
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def shot_transition_boundary_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "shot_transition_boundary_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "visualClipCount": summary.get("visualClipCount"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "auditedBoundaryCount": summary.get("auditedBoundaryCount"),
        "passedBoundaryCount": summary.get("passedBoundaryCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "pairMatchedBoundaryCount": summary.get("pairMatchedBoundaryCount"),
        "bgmHitBoundaryCount": summary.get("bgmHitBoundaryCount"),
        "titleSafeBoundaryCount": summary.get("titleSafeBoundaryCount"),
        "bgmOnlyBoundaryCount": summary.get("bgmOnlyBoundaryCount"),
        "motionBoundaryCount": summary.get("motionBoundaryCount"),
        "motionSafeBoundaryCount": summary.get("motionSafeBoundaryCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def shot_transition_boundary_contract_ready(evidence: dict[str, Any]) -> bool:
    boundary_count = int(evidence.get("visualBoundaryCount") or 0)
    motion_rows = int(evidence.get("motionBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintKind") == "transition_polish_candidate"
        and evidence.get("blueprintExists") is True
        and boundary_count > 0
        and int(evidence.get("transitionRowCount") or 0) >= boundary_count
        and int(evidence.get("auditedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("passedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("blockedBoundaryCount") or 0) == 0
        and int(evidence.get("pairMatchedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("bgmHitBoundaryCount") or 0) == boundary_count
        and int(evidence.get("titleSafeBoundaryCount") or 0) == boundary_count
        and int(evidence.get("bgmOnlyBoundaryCount") or 0) == boundary_count
        and int(evidence.get("motionSafeBoundaryCount") or 0) == motion_rows
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def transition_motivation_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_motivation_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "transitionCoverageRatio": summary.get("transitionCoverageRatio"),
        "auditedBoundaryCount": summary.get("auditedBoundaryCount"),
        "passedBoundaryCount": summary.get("passedBoundaryCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "motivatedBoundaryCount": summary.get("motivatedBoundaryCount"),
        "pairMatchedBoundaryCount": summary.get("pairMatchedBoundaryCount"),
        "bgmMotivatedBoundaryCount": summary.get("bgmMotivatedBoundaryCount"),
        "bridgeMotivatedBoundaryCount": summary.get("bridgeMotivatedBoundaryCount"),
        "motionMotivatedBoundaryCount": summary.get("motionMotivatedBoundaryCount"),
        "titleSafeMotivatedBoundaryCount": summary.get("titleSafeMotivatedBoundaryCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "forbiddenHitCount": summary.get("forbiddenHitCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_motivation_contract_ready(evidence: dict[str, Any]) -> bool:
    boundary_count = int(evidence.get("visualBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintKind") == "transition_polish_candidate"
        and evidence.get("blueprintExists") is True
        and boundary_count > 0
        and int(evidence.get("transitionRowCount") or 0) >= boundary_count
        and float(evidence.get("transitionCoverageRatio") or 0) >= 1.0
        and int(evidence.get("auditedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("passedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("blockedBoundaryCount") or 0) == 0
        and int(evidence.get("motivatedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("pairMatchedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("bgmMotivatedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("titleSafeMotivatedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("forbiddenHitCount") or 0) == 0
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_pair_continuity_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_pair_continuity_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "transitionCoverageRatio": summary.get("transitionCoverageRatio"),
        "auditedBoundaryCount": summary.get("auditedBoundaryCount"),
        "passedBoundaryCount": summary.get("passedBoundaryCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "pairContinuityPayloadCount": summary.get("pairContinuityPayloadCount"),
        "strongPairFitCount": summary.get("strongPairFitCount"),
        "acceptablePairFitCount": summary.get("acceptablePairFitCount"),
        "weakPairFitCount": summary.get("weakPairFitCount"),
        "styleAllowedBoundaryCount": summary.get("styleAllowedBoundaryCount"),
        "pairMatchedBoundaryCount": summary.get("pairMatchedBoundaryCount"),
        "motionBoundaryCount": summary.get("motionBoundaryCount"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_pair_continuity_contract_ready(evidence: dict[str, Any]) -> bool:
    boundary_count = int(evidence.get("visualBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintKind") == "transition_polish_candidate"
        and evidence.get("blueprintExists") is True
        and boundary_count > 0
        and int(evidence.get("transitionRowCount") or 0) >= boundary_count
        and float(evidence.get("transitionCoverageRatio") or 0) >= 1.0
        and int(evidence.get("auditedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("passedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("blockedBoundaryCount") or 0) == 0
        and int(evidence.get("pairContinuityPayloadCount") or 0) == boundary_count
        and int(evidence.get("pairMatchedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("styleAllowedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("weakPairFitCount") or 0) == 0
        and int(evidence.get("strongPairFitCount") or 0) + int(evidence.get("acceptablePairFitCount") or 0) == boundary_count
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_execution_readiness_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_execution_readiness_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "transitionCoverageRatio": summary.get("transitionCoverageRatio"),
        "auditedBoundaryCount": summary.get("auditedBoundaryCount"),
        "passedBoundaryCount": summary.get("passedBoundaryCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "recipeReadyBoundaryCount": summary.get("recipeReadyBoundaryCount"),
        "bgmHitBoundaryCount": summary.get("bgmHitBoundaryCount"),
        "bgmOnlyBoundaryCount": summary.get("bgmOnlyBoundaryCount"),
        "titleSafeBoundaryCount": summary.get("titleSafeBoundaryCount"),
        "decisionFieldBoundaryCount": summary.get("decisionFieldBoundaryCount"),
        "pairReadyBoundaryCount": summary.get("pairReadyBoundaryCount"),
        "handleReadyBoundaryCount": summary.get("handleReadyBoundaryCount"),
        "motionBoundaryCount": summary.get("motionBoundaryCount"),
        "motionReadyBoundaryCount": summary.get("motionReadyBoundaryCount"),
        "forbiddenHitCount": summary.get("forbiddenHitCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "maxTransitionDurationSeconds": summary.get("maxTransitionDurationSeconds"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_execution_readiness_contract_ready(evidence: dict[str, Any]) -> bool:
    boundary_count = int(evidence.get("visualBoundaryCount") or 0)
    motion_count = int(evidence.get("motionBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintKind") == "transition_polish_candidate"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and boundary_count > 0
        and int(evidence.get("transitionRowCount") or 0) >= boundary_count
        and float(evidence.get("transitionCoverageRatio") or 0) >= 1.0
        and int(evidence.get("auditedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("passedBoundaryCount") or 0) == boundary_count
        and int(evidence.get("blockedBoundaryCount") or 0) == 0
        and int(evidence.get("recipeReadyBoundaryCount") or 0) == boundary_count
        and int(evidence.get("bgmHitBoundaryCount") or 0) == boundary_count
        and int(evidence.get("bgmOnlyBoundaryCount") or 0) == boundary_count
        and int(evidence.get("titleSafeBoundaryCount") or 0) == boundary_count
        and int(evidence.get("decisionFieldBoundaryCount") or 0) == boundary_count
        and int(evidence.get("pairReadyBoundaryCount") or 0) == boundary_count
        and int(evidence.get("handleReadyBoundaryCount") or 0) == boundary_count
        and int(evidence.get("motionReadyBoundaryCount") or 0) == motion_count
        and int(evidence.get("forbiddenHitCount") or 0) == 0
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and float(evidence.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_polish_application_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_polish_application_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionPolishStatus": inputs.get("transitionPolishStatus"),
        "sourceCandidateExists": inputs.get("sourceCandidateExists"),
        "sourceCandidateInsidePackage": inputs.get("sourceCandidateInsidePackage"),
        "finalBlueprintExists": inputs.get("finalBlueprintExists"),
        "finalBlueprintKind": inputs.get("finalBlueprintKind"),
        "finalBlueprintInsidePackage": inputs.get("finalBlueprintInsidePackage"),
        "finalHasTransitionPolishBlueprintPlan": inputs.get("finalHasTransitionPolishBlueprintPlan"),
        "sourcePolishRowCount": summary.get("sourcePolishRowCount"),
        "finalTransitionPolishCandidateCount": summary.get("finalTransitionPolishCandidateCount"),
        "finalTransitionRowCount": summary.get("finalTransitionRowCount"),
        "finalVisualBoundaryCount": summary.get("finalVisualBoundaryCount"),
        "auditedPolishRowCount": summary.get("auditedPolishRowCount"),
        "passedPolishRowCount": summary.get("passedPolishRowCount"),
        "blockedPolishRowCount": summary.get("blockedPolishRowCount"),
        "recipeReadyRowCount": summary.get("recipeReadyRowCount"),
        "bgmHitRowCount": summary.get("bgmHitRowCount"),
        "bgmOnlyRowCount": summary.get("bgmOnlyRowCount"),
        "titleSafeRowCount": summary.get("titleSafeRowCount"),
        "pairReadyRowCount": summary.get("pairReadyRowCount"),
        "clipAnnotationRowCount": summary.get("clipAnnotationRowCount"),
        "markerRowCount": summary.get("markerRowCount"),
        "motionRowCount": summary.get("motionRowCount"),
        "motionReadyRowCount": summary.get("motionReadyRowCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_polish_application_contract_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("sourcePolishRowCount") or 0)
    motion_count = int(evidence.get("motionRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("transitionPolishStatus") == "ready_with_transition_polish_blueprint"
        and evidence.get("sourceCandidateExists") is True
        and evidence.get("sourceCandidateInsidePackage") is True
        and evidence.get("finalBlueprintExists") is True
        and evidence.get("finalBlueprintInsidePackage") is True
        and evidence.get("finalHasTransitionPolishBlueprintPlan") is True
        and row_count >= 1
        and int(evidence.get("finalTransitionPolishCandidateCount") or 0) >= row_count
        and int(evidence.get("finalTransitionRowCount") or 0) >= row_count
        and int(evidence.get("auditedPolishRowCount") or 0) == row_count
        and int(evidence.get("passedPolishRowCount") or 0) == row_count
        and int(evidence.get("blockedPolishRowCount") or 0) == 0
        and int(evidence.get("recipeReadyRowCount") or 0) == row_count
        and int(evidence.get("bgmHitRowCount") or 0) == row_count
        and int(evidence.get("bgmOnlyRowCount") or 0) == row_count
        and int(evidence.get("titleSafeRowCount") or 0) == row_count
        and int(evidence.get("pairReadyRowCount") or 0) == row_count
        and int(evidence.get("clipAnnotationRowCount") or 0) == row_count
        and int(evidence.get("markerRowCount") or 0) == row_count
        and int(evidence.get("motionReadyRowCount") or 0) == motion_count
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def resolve_transition_materialization_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "resolve_transition_materialization_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "blueprintKind": inputs.get("blueprintKind"),
        "buildResolveTimelinePreservesMarkerPayload": inputs.get("buildResolveTimelinePreservesMarkerPayload"),
        "resolveReadbackChecked": inputs.get("resolveReadbackChecked"),
        "transitionCandidateCount": summary.get("transitionCandidateCount"),
        "transitionRowsWithMarkerPayload": summary.get("transitionRowsWithMarkerPayload"),
        "transitionRowsWithClipAnnotation": summary.get("transitionRowsWithClipAnnotation"),
        "visibleEffectRowCount": summary.get("visibleEffectRowCount"),
        "resolveRowsWithPayload": summary.get("resolveRowsWithPayload"),
        "blockedTransitionRowCount": summary.get("blockedTransitionRowCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def resolve_transition_materialization_contract_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("transitionCandidateCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and evidence.get("buildResolveTimelinePreservesMarkerPayload") is True
        and row_count >= 1
        and int(evidence.get("transitionRowsWithMarkerPayload") or 0) == row_count
        and int(evidence.get("transitionRowsWithClipAnnotation") or 0) == row_count
        and int(evidence.get("blockedTransitionRowCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def reference_scene_grammar_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "reference_scene_grammar_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "visualClipCount": summary.get("visualClipCount"),
        "openingClipCount": summary.get("openingClipCount"),
        "openingFunctionCount": summary.get("openingFunctionCount"),
        "chapterCount": summary.get("chapterCount"),
        "chaptersPassed": summary.get("chaptersPassed"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "endingClipCount": summary.get("endingClipCount"),
        "endingAftertasteFound": summary.get("endingAftertasteFound"),
        "pairContinuityStatus": summary.get("pairContinuityStatus"),
        "weakPairFitCount": summary.get("weakPairFitCount"),
        "openingStoryPlanExists": summary.get("openingStoryPlanExists"),
        "chapterArcPlanExists": summary.get("chapterArcPlanExists"),
        "creatorCutPlanExists": summary.get("creatorCutPlanExists"),
        "referenceProfileAvailable": summary.get("referenceProfileAvailable"),
        "blockerCount": summary.get("blockerCount"),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def reference_scene_grammar_contract_ready(evidence: dict[str, Any]) -> bool:
    chapter_count = int(evidence.get("chapterCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and int(evidence.get("visualClipCount") or 0) >= 3
        and int(evidence.get("openingClipCount") or 0) >= 1
        and int(evidence.get("openingFunctionCount") or 0) >= 2
        and chapter_count >= 1
        and int(evidence.get("chaptersPassed") or 0) == chapter_count
        and int(evidence.get("chaptersBlocked") or 0) == 0
        and int(evidence.get("endingClipCount") or 0) >= 1
        and evidence.get("pairContinuityStatus") == "passed"
        and int(evidence.get("weakPairFitCount") or 0) == 0
        and evidence.get("openingStoryPlanExists") is True
        and evidence.get("chapterArcPlanExists") is True
        and evidence.get("creatorCutPlanExists") is True
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def chapter_story_spine_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "chapter_story_spine_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "chaptersWithCompleteStorySpine": summary.get("chaptersWithCompleteStorySpine"),
        "chaptersMissingStorySpine": summary.get("chaptersMissingStorySpine"),
        "rhythmChaptersReady": summary.get("rhythmChaptersReady"),
        "creatorChaptersReady": summary.get("creatorChaptersReady"),
        "finalSourceStatus": summary.get("finalSourceStatus"),
        "creatorApplicationStatus": summary.get("creatorApplicationStatus"),
        "referenceSceneGrammarStatus": summary.get("referenceSceneGrammarStatus"),
        "timelineVarietyStatus": summary.get("timelineVarietyStatus"),
        "transitionSceneArcStatus": summary.get("transitionSceneArcStatus"),
        "referenceTransitionProfileStatus": summary.get("referenceTransitionProfileStatus"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def chapter_story_spine_contract_ready(evidence: dict[str, Any]) -> bool:
    chapter_count = int(evidence.get("chapterRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and chapter_count >= 1
        and int(evidence.get("chaptersWithCompleteStorySpine") or 0) == chapter_count
        and int(evidence.get("chaptersMissingStorySpine") or 0) == 0
        and int(evidence.get("rhythmChaptersReady") or 0) >= chapter_count
        and int(evidence.get("creatorChaptersReady") or 0) >= chapter_count
        and evidence.get("finalSourceStatus") == "passed"
        and evidence.get("creatorApplicationStatus") == "passed"
        and evidence.get("referenceSceneGrammarStatus") == "passed"
        and evidence.get("timelineVarietyStatus") == "passed"
        and evidence.get("transitionSceneArcStatus") == "passed"
        and evidence.get("referenceTransitionProfileStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def shot_flow_continuity_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "shot_flow_continuity_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualClipCount": summary.get("visualClipCount"),
        "chapterCount": summary.get("chapterCount"),
        "chaptersPassed": summary.get("chaptersPassed"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "weakClipCount": summary.get("weakClipCount"),
        "weakFlowPairCount": summary.get("weakFlowPairCount"),
        "sameBeatRunMax": summary.get("sameBeatRunMax"),
        "sameSourceRunMax": summary.get("sameSourceRunMax"),
        "utilityRunMax": summary.get("utilityRunMax"),
        "chapterStorySpineStatus": summary.get("chapterStorySpineStatus"),
        "timelineVarietyStatus": summary.get("timelineVarietyStatus"),
        "transitionPairContinuityStatus": summary.get("transitionPairContinuityStatus"),
        "transitionMicrostructureStatus": summary.get("transitionMicrostructureStatus"),
        "referenceSceneGrammarStatus": summary.get("referenceSceneGrammarStatus"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def shot_flow_continuity_contract_ready(evidence: dict[str, Any]) -> bool:
    chapter_count = int(evidence.get("chapterCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and int(evidence.get("visualClipCount") or 0) >= 3
        and chapter_count >= 1
        and int(evidence.get("chaptersPassed") or 0) == chapter_count
        and int(evidence.get("chaptersBlocked") or 0) == 0
        and int(evidence.get("weakClipCount") or 0) == 0
        and int(evidence.get("weakFlowPairCount") or 0) == 0
        and int(evidence.get("sameBeatRunMax") or 0) <= 3
        and int(evidence.get("sameSourceRunMax") or 0) <= 3
        and int(evidence.get("utilityRunMax") or 0) <= 2
        and evidence.get("chapterStorySpineStatus") == "passed"
        and evidence.get("timelineVarietyStatus") == "passed"
        and evidence.get("transitionPairContinuityStatus") == "passed"
        and evidence.get("transitionMicrostructureStatus") == "passed"
        and evidence.get("referenceSceneGrammarStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def reference_profile_application_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "reference_profile_application_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    profile = data.get("referenceProfile") if isinstance(data.get("referenceProfile"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "referenceProfileStatus": summary.get("referenceProfileStatus"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "pacingStatus": summary.get("pacingStatus"),
        "audioStatus": summary.get("audioStatus"),
        "styleTargetKeyCount": summary.get("styleTargetKeyCount"),
        "requiredArtifactCount": summary.get("requiredArtifactCount"),
        "passedArtifactCount": summary.get("passedArtifactCount"),
        "blockedArtifactCount": summary.get("blockedArtifactCount"),
        "directReferenceArtifactCount": summary.get("directReferenceArtifactCount"),
        "passedDirectReferenceArtifactCount": summary.get("passedDirectReferenceArtifactCount"),
        "minimumReferenceVideos": profile.get("minimumReferenceVideos"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def reference_profile_application_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("referenceVideoCount") or 0) >= int(evidence.get("minimumReferenceVideos") or 2)
        and evidence.get("pacingStatus") == "analyzed"
        and evidence.get("audioStatus") == "analyzed"
        and int(evidence.get("styleTargetKeyCount") or 0) >= 4
        and int(evidence.get("requiredArtifactCount") or 0) >= 10
        and int(evidence.get("passedArtifactCount") or 0) == int(evidence.get("requiredArtifactCount") or 0)
        and int(evidence.get("blockedArtifactCount") or 0) == 0
        and int(evidence.get("passedDirectReferenceArtifactCount") or 0) == int(evidence.get("directReferenceArtifactCount") or 0)
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def reference_transition_profile_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "reference_transition_profile_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "referenceProfileStatus": summary.get("referenceProfileStatus"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "motionShare": summary.get("motionShare"),
        "cleanMatchBreathShare": summary.get("cleanMatchBreathShare"),
        "importantBridgeBreathCoverage": summary.get("importantBridgeBreathCoverage"),
        "maxFamilyRun": summary.get("maxFamilyRun"),
        "dominantFamilyShare": summary.get("dominantFamilyShare"),
        "readyReportCount": summary.get("readyReportCount"),
        "requiredReportCount": summary.get("requiredReportCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def reference_transition_profile_contract_ready(evidence: dict[str, Any]) -> bool:
    rows = int(evidence.get("transitionRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and rows >= 1
        and int(evidence.get("readyReportCount") or 0) >= int(evidence.get("requiredReportCount") or 0)
        and int(evidence.get("blockerCount") or 0) == 0
        and float(evidence.get("motionShare") or 0.0) <= 0.25
        and (rows < 3 or float(evidence.get("cleanMatchBreathShare") or 0.0) >= 0.45)
        and float(evidence.get("importantBridgeBreathCoverage") or 1.0) >= 1.0
        and int(evidence.get("maxFamilyRun") or 0) <= 4
        and (rows < 4 or float(evidence.get("dominantFamilyShare") or 0.0) <= 0.65)
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def timeline_variety_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "timeline_variety_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualClipCount": summary.get("visualClipCount"),
        "rawSourceClipCount": summary.get("rawSourceClipCount"),
        "globalFunctionGroupCount": summary.get("globalFunctionGroupCount"),
        "sameSourceRunMax": summary.get("sameSourceRunMax"),
        "sameFunctionRunMax": summary.get("sameFunctionRunMax"),
        "movementReady": summary.get("movementReady"),
        "textureReady": summary.get("textureReady"),
        "payoffReady": summary.get("payoffReady"),
        "aftertasteReady": summary.get("aftertasteReady"),
        "chaptersNeedingVarietyOrRetime": summary.get("chaptersNeedingVarietyOrRetime"),
        "referenceSceneChaptersBlocked": summary.get("referenceSceneChaptersBlocked"),
        "transitionCadenceStatus": summary.get("transitionCadenceStatus"),
        "finalBlueprintLineageStatus": summary.get("finalBlueprintLineageStatus"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def timeline_variety_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("visualClipCount") or 0) >= 3
        and int(evidence.get("rawSourceClipCount") or 0) >= 1
        and int(evidence.get("globalFunctionGroupCount") or 0) >= 4
        and int(evidence.get("sameSourceRunMax") or 0) <= 3
        and int(evidence.get("sameFunctionRunMax") or 0) <= 4
        and evidence.get("movementReady") is True
        and evidence.get("textureReady") is True
        and evidence.get("payoffReady") is True
        and evidence.get("aftertasteReady") is True
        and int(evidence.get("chaptersNeedingVarietyOrRetime") or 0) == 0
        and int(evidence.get("referenceSceneChaptersBlocked") or 0) == 0
        and evidence.get("transitionCadenceStatus") == "passed"
        and evidence.get("finalBlueprintLineageStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def resolve_transition_apply_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "resolve_transition_apply_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "applyPlanExists": inputs.get("applyPlanExists"),
        "applyPlanStatus": inputs.get("applyPlanStatus"),
        "materializationStatus": inputs.get("materializationStatus"),
        "transitionApplyRowCount": summary.get("transitionApplyRowCount"),
        "passedRowCount": summary.get("passedRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "visibleEffectRowCount": summary.get("visibleEffectRowCount"),
        "visibleEffectRowsWithApplyPath": summary.get("visibleEffectRowsWithApplyPath"),
        "manualResolveRowCount": summary.get("manualResolveRowCount"),
        "fallbackBridgeRequiredRowCount": summary.get("fallbackBridgeRequiredRowCount"),
        "readbackEvidenceRequiredRowCount": summary.get("readbackEvidenceRequiredRowCount"),
        "decisionFieldRowCount": summary.get("decisionFieldRowCount"),
        "markerOnlyBlockedRowCount": summary.get("markerOnlyBlockedRowCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def resolve_transition_apply_contract_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("transitionApplyRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("applyPlanExists") is True
        and evidence.get("applyPlanStatus") == "ready_with_resolve_transition_apply_plan"
        and evidence.get("materializationStatus") == "passed"
        and row_count >= 1
        and int(evidence.get("passedRowCount") or 0) == row_count
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("visibleEffectRowsWithApplyPath") or 0) == int(evidence.get("visibleEffectRowCount") or 0)
        and int(evidence.get("readbackEvidenceRequiredRowCount") or 0) == row_count
        and int(evidence.get("decisionFieldRowCount") or 0) == row_count
        and int(evidence.get("markerOnlyBlockedRowCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_cadence_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_cadence_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "craftedTransitionCount": summary.get("craftedTransitionCount"),
        "minimumCraftedTransitionCount": summary.get("minimumCraftedTransitionCount"),
        "motionTransitionCount": summary.get("motionTransitionCount"),
        "maxMotionAllowed": summary.get("maxMotionAllowed"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "dominantStyle": summary.get("dominantStyle"),
        "dominantStyleShare": summary.get("dominantStyleShare"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "requiredBridgeSequenceRowCount": summary.get("requiredBridgeSequenceRowCount"),
        "expectedBridgeBeatClipCount": summary.get("expectedBridgeBeatClipCount"),
        "appliedBridgeBeatClipCount": summary.get("appliedBridgeBeatClipCount"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_cadence_contract_ready(evidence: dict[str, Any]) -> bool:
    visual_boundaries = int(evidence.get("visualBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and visual_boundaries >= 1
        and int(evidence.get("transitionRowCount") or 0) >= visual_boundaries
        and int(evidence.get("craftedTransitionCount") or 0) >= int(evidence.get("minimumCraftedTransitionCount") or 0)
        and int(evidence.get("motionTransitionCount") or 0) <= int(evidence.get("maxMotionAllowed") or 0)
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and float(evidence.get("dominantStyleShare") or 0.0) <= 0.7
        and int(evidence.get("appliedBridgeBeatClipCount") or 0) >= int(evidence.get("expectedBridgeBeatClipCount") or 0)
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_microstructure_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_microstructure_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "bgmHitBoundaryCount": summary.get("bgmHitBoundaryCount"),
        "titleSafeBoundaryCount": summary.get("titleSafeBoundaryCount"),
        "bgmOnlyBoundaryCount": summary.get("bgmOnlyBoundaryCount"),
        "handleReadyBoundaryCount": summary.get("handleReadyBoundaryCount"),
        "pairReadyBoundaryCount": summary.get("pairReadyBoundaryCount"),
        "weakPairFitCount": summary.get("weakPairFitCount"),
        "motionBoundaryCount": summary.get("motionBoundaryCount"),
        "motionReadyBoundaryCount": summary.get("motionReadyBoundaryCount"),
        "maxMotionAllowed": summary.get("maxMotionAllowed"),
        "maxTransitionDurationSeconds": summary.get("maxTransitionDurationSeconds"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "markerOnlyBlockedRowCount": summary.get("markerOnlyBlockedRowCount"),
        "expectedBridgeBeatClipCount": summary.get("expectedBridgeBeatClipCount"),
        "appliedBridgeBeatClipCount": summary.get("appliedBridgeBeatClipCount"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_microstructure_contract_ready(evidence: dict[str, Any]) -> bool:
    visual_boundaries = int(evidence.get("visualBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and visual_boundaries >= 1
        and int(evidence.get("transitionRowCount") or 0) >= visual_boundaries
        and int(evidence.get("bgmHitBoundaryCount") or 0) == visual_boundaries
        and int(evidence.get("titleSafeBoundaryCount") or 0) == visual_boundaries
        and int(evidence.get("bgmOnlyBoundaryCount") or 0) == visual_boundaries
        and int(evidence.get("handleReadyBoundaryCount") or 0) == visual_boundaries
        and int(evidence.get("pairReadyBoundaryCount") or 0) == visual_boundaries
        and int(evidence.get("weakPairFitCount") or 0) == 0
        and int(evidence.get("motionBoundaryCount") or 0) <= int(evidence.get("maxMotionAllowed") or 0)
        and int(evidence.get("motionReadyBoundaryCount") or 0) == int(evidence.get("motionBoundaryCount") or 0)
        and float(evidence.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and int(evidence.get("markerOnlyBlockedRowCount") or 0) == 0
        and int(evidence.get("appliedBridgeBeatClipCount") or 0) >= int(evidence.get("expectedBridgeBeatClipCount") or 0)
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_scene_arc_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_scene_arc_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "sceneArcStrategyCount": summary.get("sceneArcStrategyCount"),
        "requiredBridgeSequenceRowCount": summary.get("requiredBridgeSequenceRowCount"),
        "expectedBridgeBeatClipCount": summary.get("expectedBridgeBeatClipCount"),
        "appliedBridgeBeatClipCount": summary.get("appliedBridgeBeatClipCount"),
        "motionTransitionCount": summary.get("motionTransitionCount"),
        "maxMotionAllowed": summary.get("maxMotionAllowed"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "dominantStyle": summary.get("dominantStyle"),
        "dominantStyleShare": summary.get("dominantStyleShare"),
        "maxTransitionDurationSeconds": summary.get("maxTransitionDurationSeconds"),
        "movementReady": summary.get("movementReady"),
        "textureReady": summary.get("textureReady"),
        "payoffReady": summary.get("payoffReady"),
        "aftertasteReady": summary.get("aftertasteReady"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_scene_arc_contract_ready(evidence: dict[str, Any]) -> bool:
    important_boundaries = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("visualBoundaryCount") or 0) >= 1
        and (important_boundaries == 0 or int(evidence.get("sceneArcStrategyCount") or 0) >= 1)
        and int(evidence.get("appliedBridgeBeatClipCount") or 0) >= int(evidence.get("expectedBridgeBeatClipCount") or 0)
        and int(evidence.get("motionTransitionCount") or 0) <= int(evidence.get("maxMotionAllowed") or 0)
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and float(evidence.get("dominantStyleShare") or 0.0) <= 0.7
        and float(evidence.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and evidence.get("movementReady") is True
        and evidence.get("textureReady") is True
        and evidence.get("payoffReady") is True
        and evidence.get("aftertasteReady") is True
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_effect_palette_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_effect_palette_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "motifFamilyCount": summary.get("motifFamilyCount"),
        "minimumPaletteFamilyCount": summary.get("minimumPaletteFamilyCount"),
        "dominantMotif": summary.get("dominantMotif"),
        "dominantMotifShare": summary.get("dominantMotifShare"),
        "dominantStyle": summary.get("dominantStyle"),
        "dominantStyleShare": summary.get("dominantStyleShare"),
        "motionTransitionCount": summary.get("motionTransitionCount"),
        "maxMotionAllowed": summary.get("maxMotionAllowed"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "physicalBridgeOrSceneArcCount": summary.get("physicalBridgeOrSceneArcCount"),
        "cleanOrMatchCount": summary.get("cleanOrMatchCount"),
        "maxTransitionDurationSeconds": summary.get("maxTransitionDurationSeconds"),
        "movementReady": summary.get("movementReady"),
        "textureReady": summary.get("textureReady"),
        "payoffReady": summary.get("payoffReady"),
        "aftertasteReady": summary.get("aftertasteReady"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_effect_palette_contract_ready(evidence: dict[str, Any]) -> bool:
    important_boundaries = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("visualBoundaryCount") or 0) >= 1
        and int(evidence.get("transitionRowCount") or 0) >= int(evidence.get("visualBoundaryCount") or 0)
        and int(evidence.get("motifFamilyCount") or 0) >= int(evidence.get("minimumPaletteFamilyCount") or 0)
        and int(evidence.get("cleanOrMatchCount") or 0) >= 1
        and (important_boundaries == 0 or int(evidence.get("physicalBridgeOrSceneArcCount") or 0) >= 1)
        and int(evidence.get("motionTransitionCount") or 0) <= int(evidence.get("maxMotionAllowed") or 0)
        and int(evidence.get("decorativeRepeatedRunMax") or 0) < 4
        and float(evidence.get("dominantMotifShare") or 0.0) <= 0.65
        and float(evidence.get("dominantStyleShare") or 0.0) <= 0.7
        and float(evidence.get("maxTransitionDurationSeconds") or 0.0) <= 0.9
        and evidence.get("movementReady") is True
        and evidence.get("textureReady") is True
        and evidence.get("payoffReady") is True
        and evidence.get("aftertasteReady") is True
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_visual_match_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_visual_match_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "visualMatchReadyRowCount": summary.get("visualMatchReadyRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "motionTransitionCount": summary.get("motionTransitionCount"),
        "maxMotionAllowed": summary.get("maxMotionAllowed"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantBridgeOrSceneHandoffCount": summary.get("importantBridgeOrSceneHandoffCount"),
        "evidenceFamilyCounts": summary.get("evidenceFamilyCounts"),
        "styleCounts": summary.get("styleCounts"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_visual_match_contract_ready(evidence: dict[str, Any]) -> bool:
    important_boundaries = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("visualBoundaryCount") or 0) >= 1
        and int(evidence.get("transitionRowCount") or 0) >= int(evidence.get("visualBoundaryCount") or 0)
        and int(evidence.get("visualMatchReadyRowCount") or 0) == int(evidence.get("transitionRowCount") or 0)
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("motionTransitionCount") or 0) <= int(evidence.get("maxMotionAllowed") or 0)
        and (important_boundaries == 0 or int(evidence.get("importantBridgeOrSceneHandoffCount") or 0) >= important_boundaries)
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_reference_candidates_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_reference_candidates" / "transition_reference_candidates.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "candidateRowCount": summary.get("candidateRowCount"),
        "rowsWithAtLeastThreeCandidates": summary.get("rowsWithAtLeastThreeCandidates"),
        "motionCandidateRowCount": summary.get("motionCandidateRowCount"),
        "maxMotionCandidateRows": summary.get("maxMotionCandidateRows"),
        "rowsNeedingBridgeBeforeEffect": summary.get("rowsNeedingBridgeBeforeEffect"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsWithBridgeOrBreathCandidate": summary.get("importantRowsWithBridgeOrBreathCandidate"),
        "importantBridgeOrBreathCoverage": summary.get("importantBridgeOrBreathCoverage"),
        "primaryStyleFamilyCounts": summary.get("primaryStyleFamilyCounts"),
        "referenceStatus": summary.get("referenceStatus"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def transition_reference_candidates_ready(evidence: dict[str, Any]) -> bool:
    transition_rows = int(evidence.get("transitionRowCount") or 0)
    candidate_rows = int(evidence.get("candidateRowCount") or 0)
    important = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_reference_candidates"
        and transition_rows >= 1
        and candidate_rows == transition_rows
        and int(evidence.get("rowsWithAtLeastThreeCandidates") or 0) == candidate_rows
        and int(evidence.get("motionCandidateRowCount") or 0) <= int(evidence.get("maxMotionCandidateRows") or 0)
        and (important == 0 or float(evidence.get("importantBridgeOrBreathCoverage") or 0.0) >= 1.0)
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def transition_reference_selection_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_reference_selection" / "transition_reference_selection.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "candidateRowCount": summary.get("candidateRowCount"),
        "selectionRowCount": summary.get("selectionRowCount"),
        "selectedRowCount": summary.get("selectedRowCount"),
        "autoSelectedRowCount": summary.get("autoSelectedRowCount"),
        "blockedSelectionRowCount": summary.get("blockedSelectionRowCount"),
        "motionSelectedRowCount": summary.get("motionSelectedRowCount"),
        "maxMotionRows": summary.get("maxMotionRows"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsWithBridgeOrBreathSelection": summary.get("importantRowsWithBridgeOrBreathSelection"),
        "importantBridgeOrBreathSelectionCoverage": summary.get("importantBridgeOrBreathSelectionCoverage"),
        "selectedStyleFamilyCounts": summary.get("selectedStyleFamilyCounts"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
    }


def transition_reference_selection_ready(evidence: dict[str, Any]) -> bool:
    candidate_rows = int(evidence.get("candidateRowCount") or 0)
    selection_rows = int(evidence.get("selectionRowCount") or 0)
    important = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_reference_selection"
        and candidate_rows >= 1
        and selection_rows == candidate_rows
        and int(evidence.get("selectedRowCount") or 0) == candidate_rows
        and int(evidence.get("autoSelectedRowCount") or 0) == candidate_rows
        and int(evidence.get("blockedSelectionRowCount") or 0) == 0
        and int(evidence.get("motionSelectedRowCount") or 0) <= int(evidence.get("maxMotionRows") or 0)
        and (important == 0 or float(evidence.get("importantBridgeOrBreathSelectionCoverage") or 0.0) >= 1.0)
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
    )


def transition_choreography_plan_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_choreography_plan" / "transition_choreography_plan.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "readyChoreographyRowCount": summary.get("readyChoreographyRowCount"),
        "blockedChoreographyRowCount": summary.get("blockedChoreographyRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsWithThreeBeatCount": summary.get("importantRowsWithThreeBeatCount"),
        "motionChoreographyRowCount": summary.get("motionChoreographyRowCount"),
        "maxFamilyRun": summary.get("maxFamilyRun"),
        "dominantFamilyShare": summary.get("dominantFamilyShare"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_choreography_plan_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_with_transition_choreography_plan"
        and int(evidence.get("transitionRowCount") or 0) >= 1
        and int(evidence.get("readyChoreographyRowCount") or 0) == int(evidence.get("transitionRowCount") or 0)
        and int(evidence.get("blockedChoreographyRowCount") or 0) == 0
        and int(evidence.get("importantRowsWithThreeBeatCount") or 0) >= int(evidence.get("importantBoundaryCount") or 0)
        and int(evidence.get("maxFamilyRun") or 0) <= 4
        and (int(evidence.get("transitionRowCount") or 0) < 4 or float(evidence.get("dominantFamilyShare") or 0.0) <= 0.7)
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_choreography_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_choreography_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "passedChoreographyRowCount": summary.get("passedChoreographyRowCount"),
        "blockedChoreographyRowCount": summary.get("blockedChoreographyRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsWithThreeBeatCount": summary.get("importantRowsWithThreeBeatCount"),
        "motionChoreographyRowCount": summary.get("motionChoreographyRowCount"),
        "highIntensityRowCount": summary.get("highIntensityRowCount"),
        "maxFamilyRun": summary.get("maxFamilyRun"),
        "dominantFamilyShare": summary.get("dominantFamilyShare"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_choreography_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("transitionRowCount") or 0) >= 1
        and int(evidence.get("passedChoreographyRowCount") or 0) == int(evidence.get("transitionRowCount") or 0)
        and int(evidence.get("blockedChoreographyRowCount") or 0) == 0
        and int(evidence.get("highIntensityRowCount") or 0) == 0
        and int(evidence.get("importantRowsWithThreeBeatCount") or 0) >= int(evidence.get("importantBoundaryCount") or 0)
        and int(evidence.get("maxFamilyRun") or 0) <= 4
        and (int(evidence.get("transitionRowCount") or 0) < 4 or float(evidence.get("dominantFamilyShare") or 0.0) <= 0.7)
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_motion_direction_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_motion_direction_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "motionDirectionRowCount": summary.get("motionDirectionRowCount"),
        "readyMotionDirectionRowCount": summary.get("readyMotionDirectionRowCount"),
        "blockedMotionDirectionRowCount": summary.get("blockedMotionDirectionRowCount"),
        "rowsWithEffectDirection": summary.get("rowsWithEffectDirection"),
        "rowsWithLandingDirection": summary.get("rowsWithLandingDirection"),
        "rowsWithDirectionMatch": summary.get("rowsWithDirectionMatch"),
        "rowsWithDirectionConfidence": summary.get("rowsWithDirectionConfidence"),
        "bgmAlignedMotionRowCount": summary.get("bgmAlignedMotionRowCount"),
        "titleSafeMotionRowCount": summary.get("titleSafeMotionRowCount"),
        "importantMotionRowCount": summary.get("importantMotionRowCount"),
        "importantMotionRowsWithBridgeSupport": summary.get("importantMotionRowsWithBridgeSupport"),
        "rotationRowCount": summary.get("rotationRowCount"),
        "speedRampRowCount": summary.get("speedRampRowCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_motion_direction_contract_ready(evidence: dict[str, Any]) -> bool:
    motion_rows = int(evidence.get("motionDirectionRowCount") or 0)
    important_motion = int(evidence.get("importantMotionRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("transitionRowCount") or 0) >= 1
        and int(evidence.get("blockedMotionDirectionRowCount") or 0) == 0
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and int(evidence.get("readyMotionDirectionRowCount") or 0) == motion_rows
        and int(evidence.get("rowsWithEffectDirection") or 0) >= motion_rows
        and int(evidence.get("rowsWithLandingDirection") or 0) >= motion_rows
        and int(evidence.get("rowsWithDirectionMatch") or 0) >= motion_rows
        and int(evidence.get("rowsWithDirectionConfidence") or 0) >= motion_rows
        and int(evidence.get("bgmAlignedMotionRowCount") or 0) >= motion_rows
        and int(evidence.get("titleSafeMotionRowCount") or 0) >= motion_rows
        and (important_motion == 0 or int(evidence.get("importantMotionRowsWithBridgeSupport") or 0) >= important_motion)
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_cutpoint_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_cutpoint_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "readyCutpointRowCount": summary.get("readyCutpointRowCount"),
        "blockedCutpointRowCount": summary.get("blockedCutpointRowCount"),
        "rowsWithOutgoingTail": summary.get("rowsWithOutgoingTail"),
        "rowsWithBridgeOrEffectHit": summary.get("rowsWithBridgeOrEffectHit"),
        "rowsWithLandingHold": summary.get("rowsWithLandingHold"),
        "rowsWithHandles": summary.get("rowsWithHandles"),
        "rowsWithBgmHit": summary.get("rowsWithBgmHit"),
        "rowsWithTitleSubtitleQuietZone": summary.get("rowsWithTitleSubtitleQuietZone"),
        "rowsWithBgmOnlyNoSourceVoice": summary.get("rowsWithBgmOnlyNoSourceVoice"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsResolved": summary.get("importantRowsResolved"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_cutpoint_contract_ready(evidence: dict[str, Any]) -> bool:
    rows = int(evidence.get("transitionRowCount") or 0)
    important = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and rows >= 1
        and int(evidence.get("readyCutpointRowCount") or 0) == rows
        and int(evidence.get("blockedCutpointRowCount") or 0) == 0
        and int(evidence.get("rowsWithOutgoingTail") or 0) >= rows
        and int(evidence.get("rowsWithBridgeOrEffectHit") or 0) >= rows
        and int(evidence.get("rowsWithLandingHold") or 0) >= rows
        and int(evidence.get("rowsWithHandles") or 0) >= rows
        and int(evidence.get("rowsWithBgmHit") or 0) >= rows
        and int(evidence.get("rowsWithTitleSubtitleQuietZone") or 0) >= rows
        and int(evidence.get("rowsWithBgmOnlyNoSourceVoice") or 0) >= rows
        and (important == 0 or int(evidence.get("importantRowsResolved") or 0) >= important)
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_action_anchor_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_action_anchor_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "readyActionAnchorRowCount": summary.get("readyActionAnchorRowCount"),
        "blockedActionAnchorRowCount": summary.get("blockedActionAnchorRowCount"),
        "rowsWithOutgoingActionAnchor": summary.get("rowsWithOutgoingActionAnchor"),
        "rowsWithBridgeOrMatchActionAnchor": summary.get("rowsWithBridgeOrMatchActionAnchor"),
        "rowsWithLandingActionAnchor": summary.get("rowsWithLandingActionAnchor"),
        "motionAnchorRowCount": summary.get("motionAnchorRowCount"),
        "rowsWithDirectionalMotionAnchor": summary.get("rowsWithDirectionalMotionAnchor"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsResolved": summary.get("importantRowsResolved"),
        "rowsWithCutpointReady": summary.get("rowsWithCutpointReady"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_action_anchor_contract_ready(evidence: dict[str, Any]) -> bool:
    rows = int(evidence.get("transitionRowCount") or 0)
    motion_rows = int(evidence.get("motionAnchorRowCount") or 0)
    important = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and rows >= 1
        and int(evidence.get("readyActionAnchorRowCount") or 0) == rows
        and int(evidence.get("blockedActionAnchorRowCount") or 0) == 0
        and int(evidence.get("rowsWithOutgoingActionAnchor") or 0) >= rows
        and int(evidence.get("rowsWithBridgeOrMatchActionAnchor") or 0) >= rows
        and int(evidence.get("rowsWithLandingActionAnchor") or 0) >= rows
        and (motion_rows == 0 or int(evidence.get("rowsWithDirectionalMotionAnchor") or 0) >= motion_rows)
        and (important == 0 or int(evidence.get("importantRowsResolved") or 0) >= important)
        and int(evidence.get("rowsWithCutpointReady") or 0) >= rows
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_sensory_continuity_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_sensory_continuity_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "readySensoryContinuityRowCount": summary.get("readySensoryContinuityRowCount"),
        "blockedSensoryContinuityRowCount": summary.get("blockedSensoryContinuityRowCount"),
        "rowsWithVisualSensoryContinuity": summary.get("rowsWithVisualSensoryContinuity"),
        "rowsWithAudioSensoryContinuity": summary.get("rowsWithAudioSensoryContinuity"),
        "rowsWithCaptionSensoryContinuity": summary.get("rowsWithCaptionSensoryContinuity"),
        "rowsWithRouteOrMoodSensoryContinuity": summary.get("rowsWithRouteOrMoodSensoryContinuity"),
        "rowsWithLandingSensoryContinuity": summary.get("rowsWithLandingSensoryContinuity"),
        "motionSensoryRowCount": summary.get("motionSensoryRowCount"),
        "rowsWithMotionSensoryContinuity": summary.get("rowsWithMotionSensoryContinuity"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsWithRouteOrMoodContinuity": summary.get("importantRowsWithRouteOrMoodContinuity"),
        "rowsWithBgmOnlyNoSourceVoice": summary.get("rowsWithBgmOnlyNoSourceVoice"),
        "rowsWithActionAnchorReady": summary.get("rowsWithActionAnchorReady"),
        "rowsWithCutpointReady": summary.get("rowsWithCutpointReady"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_sensory_continuity_contract_ready(evidence: dict[str, Any]) -> bool:
    rows = int(evidence.get("transitionRowCount") or 0)
    motion_rows = int(evidence.get("motionSensoryRowCount") or 0)
    important = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and rows >= 1
        and int(evidence.get("readySensoryContinuityRowCount") or 0) == rows
        and int(evidence.get("blockedSensoryContinuityRowCount") or 0) == 0
        and int(evidence.get("rowsWithVisualSensoryContinuity") or 0) >= rows
        and int(evidence.get("rowsWithAudioSensoryContinuity") or 0) >= rows
        and int(evidence.get("rowsWithCaptionSensoryContinuity") or 0) >= rows
        and int(evidence.get("rowsWithLandingSensoryContinuity") or 0) >= rows
        and int(evidence.get("rowsWithBgmOnlyNoSourceVoice") or 0) >= rows
        and int(evidence.get("rowsWithActionAnchorReady") or 0) >= rows
        and int(evidence.get("rowsWithCutpointReady") or 0) >= rows
        and (important == 0 or int(evidence.get("importantRowsWithRouteOrMoodContinuity") or 0) >= important)
        and (motion_rows == 0 or int(evidence.get("rowsWithMotionSensoryContinuity") or 0) >= motion_rows)
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_breathing_room_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_breathing_room_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "motionAccentBoundaryCount": summary.get("motionAccentBoundaryCount"),
        "highIntensityBoundaryCount": summary.get("highIntensityBoundaryCount"),
        "highIntensityRunMax": summary.get("highIntensityRunMax"),
        "motionSpacingViolationCount": summary.get("motionSpacingViolationCount"),
        "landingDurationViolationCount": summary.get("landingDurationViolationCount"),
        "quietLandingReadyCount": summary.get("quietLandingReadyCount"),
        "breathAfterImportantReadyCount": summary.get("breathAfterImportantReadyCount"),
        "subtitleCollisionRiskCount": summary.get("subtitleCollisionRiskCount"),
        "titleCollisionRiskCount": summary.get("titleCollisionRiskCount"),
        "bridgeLandingEvidenceCount": summary.get("bridgeLandingEvidenceCount"),
        "cleanBreathShare": summary.get("cleanBreathShare"),
        "transitionMicrostructureStatus": summary.get("transitionMicrostructureStatus"),
        "transitionChoreographyStatus": summary.get("transitionChoreographyStatus"),
        "transitionPreviewQualityStatus": summary.get("transitionPreviewQualityStatus"),
        "transitionAuditionQualityStatus": summary.get("transitionAuditionQualityStatus"),
        "transitionStoryboardStatus": summary.get("transitionStoryboardStatus"),
        "referenceTransitionProfileStatus": summary.get("referenceTransitionProfileStatus"),
        "shotFlowContinuityStatus": summary.get("shotFlowContinuityStatus"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_breathing_room_contract_ready(evidence: dict[str, Any]) -> bool:
    important = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and int(evidence.get("visualBoundaryCount") or 0) >= 1
        and int(evidence.get("landingDurationViolationCount") or 0) == 0
        and int(evidence.get("motionSpacingViolationCount") or 0) == 0
        and int(evidence.get("highIntensityRunMax") or 0) <= 1
        and int(evidence.get("subtitleCollisionRiskCount") or 0) == 0
        and int(evidence.get("titleCollisionRiskCount") or 0) == 0
        and (important == 0 or int(evidence.get("breathAfterImportantReadyCount") or 0) >= important)
        and float(evidence.get("cleanBreathShare") or 0.0) >= 0.45
        and evidence.get("transitionMicrostructureStatus") == "passed"
        and evidence.get("transitionChoreographyStatus") == "passed"
        and evidence.get("transitionPreviewQualityStatus") == "passed"
        and evidence.get("transitionAuditionQualityStatus") == "passed"
        and evidence.get("transitionStoryboardStatus") == "passed"
        and evidence.get("referenceTransitionProfileStatus") == "passed"
        and evidence.get("shotFlowContinuityStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def scene_flow_arc_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "scene_flow_arc_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualClipCount": summary.get("visualClipCount"),
        "chapterCount": summary.get("chapterCount"),
        "chaptersPassed": summary.get("chaptersPassed"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "handoffCount": summary.get("handoffCount"),
        "blockedHandoffCount": summary.get("blockedHandoffCount"),
        "blockedWindowCount": summary.get("blockedWindowCount"),
        "weakOrUnclassifiedClipCount": summary.get("weakOrUnclassifiedClipCount"),
        "sameBeatRunMax": summary.get("sameBeatRunMax"),
        "payoffRunMax": summary.get("payoffRunMax"),
        "chapterStorySpineStatus": summary.get("chapterStorySpineStatus"),
        "shotFlowContinuityStatus": summary.get("shotFlowContinuityStatus"),
        "timelineVarietyStatus": summary.get("timelineVarietyStatus"),
        "referenceSceneGrammarStatus": summary.get("referenceSceneGrammarStatus"),
        "transitionSceneArcStatus": summary.get("transitionSceneArcStatus"),
        "transitionBreathingRoomStatus": summary.get("transitionBreathingRoomStatus"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def scene_flow_arc_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and int(evidence.get("visualClipCount") or 0) >= 5
        and int(evidence.get("chapterCount") or 0) >= 1
        and int(evidence.get("chaptersPassed") or 0) == int(evidence.get("chapterCount") or -1)
        and int(evidence.get("chaptersBlocked") or 0) == 0
        and int(evidence.get("blockedHandoffCount") or 0) == 0
        and int(evidence.get("blockedWindowCount") or 0) == 0
        and int(evidence.get("weakOrUnclassifiedClipCount") or 0) == 0
        and int(evidence.get("sameBeatRunMax") or 0) <= 3
        and int(evidence.get("payoffRunMax") or 0) <= 2
        and evidence.get("chapterStorySpineStatus") == "passed"
        and evidence.get("shotFlowContinuityStatus") == "passed"
        and evidence.get("timelineVarietyStatus") == "passed"
        and evidence.get("referenceSceneGrammarStatus") == "passed"
        and evidence.get("transitionSceneArcStatus") == "passed"
        and evidence.get("transitionBreathingRoomStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def final_cut_smoothness_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "final_cut_smoothness_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualClipCount": summary.get("visualClipCount"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "blockedImportantBoundaryCount": summary.get("blockedImportantBoundaryCount"),
        "motionEffectBoundaryCount": summary.get("motionEffectBoundaryCount"),
        "unsupportedMotionEffectCount": summary.get("unsupportedMotionEffectCount"),
        "unstableLandingCount": summary.get("unstableLandingCount"),
        "highIntensityRunMax": summary.get("highIntensityRunMax"),
        "payoffJumpCount": summary.get("payoffJumpCount"),
        "hardCutJumpCount": summary.get("hardCutJumpCount"),
        "weakBoundaryClipCount": summary.get("weakBoundaryClipCount"),
        "transitionMetadataBoundaryCount": summary.get("transitionMetadataBoundaryCount"),
        "bridgeEvidenceBoundaryCount": summary.get("bridgeEvidenceBoundaryCount"),
        "finalBlueprintLineageStatus": summary.get("finalBlueprintLineageStatus"),
        "transitionBreathingRoomStatus": summary.get("transitionBreathingRoomStatus"),
        "sceneFlowArcStatus": summary.get("sceneFlowArcStatus"),
        "shotFlowContinuityStatus": summary.get("shotFlowContinuityStatus"),
        "transitionVisualMatchStatus": summary.get("transitionVisualMatchStatus"),
        "transitionChoreographyStatus": summary.get("transitionChoreographyStatus"),
        "transitionStoryboardStatus": summary.get("transitionStoryboardStatus"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def final_cut_smoothness_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and int(evidence.get("visualClipCount") or 0) >= 4
        and int(evidence.get("visualBoundaryCount") or 0) >= 3
        and int(evidence.get("blockedBoundaryCount") or 0) == 0
        and int(evidence.get("blockedImportantBoundaryCount") or 0) == 0
        and int(evidence.get("unsupportedMotionEffectCount") or 0) == 0
        and int(evidence.get("unstableLandingCount") or 0) == 0
        and int(evidence.get("highIntensityRunMax") or 0) <= 1
        and int(evidence.get("payoffJumpCount") or 0) == 0
        and int(evidence.get("hardCutJumpCount") or 0) == 0
        and int(evidence.get("weakBoundaryClipCount") or 0) == 0
        and evidence.get("finalBlueprintLineageStatus") == "passed"
        and evidence.get("transitionBreathingRoomStatus") == "passed"
        and evidence.get("sceneFlowArcStatus") == "passed"
        and evidence.get("shotFlowContinuityStatus") == "passed"
        and evidence.get("transitionVisualMatchStatus") == "passed"
        and evidence.get("transitionChoreographyStatus") == "passed"
        and evidence.get("transitionStoryboardStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def pacing_watchability_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "pacing_watchability_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualClipCount": summary.get("visualClipCount"),
        "chapterCount": summary.get("chapterCount"),
        "blockedChapterCount": summary.get("blockedChapterCount"),
        "averageVisualShotSeconds": summary.get("averageVisualShotSeconds"),
        "medianVisualShotSeconds": summary.get("medianVisualShotSeconds"),
        "targetAverageRangeSeconds": summary.get("targetAverageRangeSeconds"),
        "targetMedianRangeSeconds": summary.get("targetMedianRangeSeconds"),
        "shortClipCount": summary.get("shortClipCount"),
        "shortClipRunMax": summary.get("shortClipRunMax"),
        "longFlatShotCount": summary.get("longFlatShotCount"),
        "longFlatRunMax": summary.get("longFlatRunMax"),
        "veryLongShotCount": summary.get("veryLongShotCount"),
        "breathingShotCount": summary.get("breathingShotCount"),
        "weakOrPlaceholderClipCount": summary.get("weakOrPlaceholderClipCount"),
        "editRhythmStatus": summary.get("editRhythmStatus"),
        "rhythmRecutApplicationStatus": summary.get("rhythmRecutApplicationStatus"),
        "timelineVarietyStatus": summary.get("timelineVarietyStatus"),
        "referenceSceneGrammarStatus": summary.get("referenceSceneGrammarStatus"),
        "finalCutSmoothnessStatus": summary.get("finalCutSmoothnessStatus"),
        "finalBlueprintLineageStatus": summary.get("finalBlueprintLineageStatus"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def pacing_watchability_contract_ready(evidence: dict[str, Any]) -> bool:
    chapters = int(evidence.get("chapterCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and int(evidence.get("visualClipCount") or 0) >= 3
        and chapters >= 1
        and int(evidence.get("blockedChapterCount") or 0) == 0
        and float(evidence.get("averageVisualShotSeconds") or 0.0) > 0.0
        and float(evidence.get("medianVisualShotSeconds") or 0.0) > 0.0
        and int(evidence.get("longFlatShotCount") or 0) == 0
        and int(evidence.get("veryLongShotCount") or 0) == 0
        and int(evidence.get("longFlatRunMax") or 0) <= 1
        and int(evidence.get("shortClipRunMax") or 0) <= 2
        and int(evidence.get("breathingShotCount") or 0) >= chapters
        and int(evidence.get("weakOrPlaceholderClipCount") or 0) == 0
        and evidence.get("editRhythmStatus") == "ready_with_edit_rhythm_plan"
        and evidence.get("rhythmRecutApplicationStatus") == "passed"
        and evidence.get("timelineVarietyStatus") == "passed"
        and evidence.get("referenceSceneGrammarStatus") == "passed"
        and evidence.get("finalCutSmoothnessStatus") == "passed"
        and evidence.get("finalBlueprintLineageStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def narrative_adjacency_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "narrative_adjacency_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualClipCount": summary.get("visualClipCount"),
        "adjacentPairCount": summary.get("adjacentPairCount"),
        "motivatedPairCount": summary.get("motivatedPairCount"),
        "unmotivatedPairCount": summary.get("unmotivatedPairCount"),
        "blockedPairCount": summary.get("blockedPairCount"),
        "blockedChapterHandoffCount": summary.get("blockedChapterHandoffCount"),
        "payoffJumpWithoutBridgeCount": summary.get("payoffJumpWithoutBridgeCount"),
        "genericPairCount": summary.get("genericPairCount"),
        "unknownFunctionRatio": summary.get("unknownFunctionRatio"),
        "functionRunMax": summary.get("functionRunMax"),
        "shotFlowContinuityStatus": summary.get("shotFlowContinuityStatus"),
        "sceneFlowArcStatus": summary.get("sceneFlowArcStatus"),
        "finalCutSmoothnessStatus": summary.get("finalCutSmoothnessStatus"),
        "transitionBreathingRoomStatus": summary.get("transitionBreathingRoomStatus"),
        "transitionPairContinuityStatus": summary.get("transitionPairContinuityStatus"),
        "transitionMotivationStatus": summary.get("transitionMotivationStatus"),
        "transitionStoryboardStatus": summary.get("transitionStoryboardStatus"),
        "transitionContinuityRehearsalStatus": summary.get("transitionContinuityRehearsalStatus"),
        "pacingWatchabilityStatus": summary.get("pacingWatchabilityStatus"),
        "finalBlueprintLineageStatus": summary.get("finalBlueprintLineageStatus"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def narrative_adjacency_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and int(evidence.get("visualClipCount") or 0) >= 3
        and int(evidence.get("adjacentPairCount") or 0) >= 1
        and int(evidence.get("blockedPairCount") or 0) == 0
        and int(evidence.get("unmotivatedPairCount") or 0) == 0
        and int(evidence.get("blockedChapterHandoffCount") or 0) == 0
        and int(evidence.get("payoffJumpWithoutBridgeCount") or 0) == 0
        and int(evidence.get("genericPairCount") or 0) == 0
        and float(evidence.get("unknownFunctionRatio") or 0.0) <= 0.25
        and int(evidence.get("functionRunMax") or 0) <= 4
        and evidence.get("shotFlowContinuityStatus") == "passed"
        and evidence.get("sceneFlowArcStatus") == "passed"
        and evidence.get("finalCutSmoothnessStatus") == "passed"
        and evidence.get("transitionBreathingRoomStatus") == "passed"
        and evidence.get("transitionPairContinuityStatus") == "passed"
        and evidence.get("transitionMotivationStatus") == "passed"
        and evidence.get("transitionStoryboardStatus") == "passed"
        and evidence.get("transitionContinuityRehearsalStatus") == "passed"
        and evidence.get("pacingWatchabilityStatus") == "passed"
        and evidence.get("finalBlueprintLineageStatus") == "passed"
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_viewer_orientation_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_viewer_orientation_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "viewerOrientationReadyCount": summary.get("viewerOrientationReadyCount"),
        "importantOrientationReadyCount": summary.get("importantOrientationReadyCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "importantBlockedRowCount": summary.get("importantBlockedRowCount"),
        "purposeReadyImportantCount": summary.get("purposeReadyImportantCount"),
        "routeCueImportantCount": summary.get("routeCueImportantCount"),
        "stableLandingImportantCount": summary.get("stableLandingImportantCount"),
        "previewEvidenceImportantCount": summary.get("previewEvidenceImportantCount"),
        "auditionEvidenceImportantCount": summary.get("auditionEvidenceImportantCount"),
        "narrativeReadyImportantCount": summary.get("narrativeReadyImportantCount"),
        "narrativeBlockedPairCount": summary.get("narrativeBlockedPairCount"),
        "narrativeUnmotivatedPairCount": summary.get("narrativeUnmotivatedPairCount"),
        "routeMatchedTransitions": summary.get("routeMatchedTransitions"),
        "routeTransitionPlanCount": summary.get("routeTransitionPlanCount"),
        "routeMatchedTitleBoundaries": summary.get("routeMatchedTitleBoundaries"),
        "routeChapterTitleCount": summary.get("routeChapterTitleCount"),
        "chapterWindowCount": summary.get("chapterWindowCount"),
        "passedChapters": summary.get("passedChapters"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "viewerOrientationRequiredForImportantTransitions": policy.get("viewerOrientationRequiredForImportantTransitions"),
        "routeTitleCaptionOrBridgeCueRequired": policy.get("routeTitleCaptionOrBridgeCueRequired"),
        "stableLandingRequired": policy.get("stableLandingRequired"),
        "narrativeHandoffReasonRequired": policy.get("narrativeHandoffReasonRequired"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_viewer_orientation_contract_ready(evidence: dict[str, Any]) -> bool:
    important_count = int(evidence.get("importantBoundaryCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("transitionRowCount") or 0) >= 3
        and important_count >= 1
        and int(evidence.get("importantOrientationReadyCount") or 0) == important_count
        and int(evidence.get("importantBlockedRowCount") or 0) == 0
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("purposeReadyImportantCount") or 0) == important_count
        and int(evidence.get("routeCueImportantCount") or 0) == important_count
        and int(evidence.get("stableLandingImportantCount") or 0) == important_count
        and int(evidence.get("previewEvidenceImportantCount") or 0) == important_count
        and int(evidence.get("auditionEvidenceImportantCount") or 0) == important_count
        and int(evidence.get("narrativeReadyImportantCount") or 0) == important_count
        and int(evidence.get("narrativeBlockedPairCount") or 0) == 0
        and int(evidence.get("narrativeUnmotivatedPairCount") or 0) == 0
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("viewerOrientationRequiredForImportantTransitions") is True
        and evidence.get("routeTitleCaptionOrBridgeCueRequired") is True
        and evidence.get("stableLandingRequired") is True
        and evidence.get("narrativeHandoffReasonRequired") is True
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_scene_settlement_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_scene_settlement_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualClipCount": summary.get("visualClipCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "settlementRowCount": summary.get("settlementRowCount"),
        "readySettlementCount": summary.get("readySettlementCount"),
        "blockedSettlementCount": summary.get("blockedSettlementCount"),
        "shortSettlementCount": summary.get("shortSettlementCount"),
        "tooFastNextJumpCount": summary.get("tooFastNextJumpCount"),
        "genericLandingOrUtilityCount": summary.get("genericLandingOrUtilityCount"),
        "textureReadyCount": summary.get("textureReadyCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blueprintKind": summary.get("blueprintKind"),
        "blueprintInsidePackage": summary.get("blueprintInsidePackage"),
        "blockers": data.get("blockers") or [],
        "importantTransitionsMustSettleIntoScene": policy.get("importantTransitionsMustSettleIntoScene"),
        "landingClipMustBeReadableSceneFootage": policy.get("landingClipMustBeReadableSceneFootage"),
        "settlementWindowMustContainTextureOrPayoff": policy.get("settlementWindowMustContainTextureOrPayoff"),
        "nextImportantTransitionCannotArriveImmediately": policy.get("nextImportantTransitionCannotArriveImmediately"),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_scene_settlement_contract_ready(evidence: dict[str, Any]) -> bool:
    settlement_count = int(evidence.get("settlementRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintInsidePackage") is True
        and int(evidence.get("importantBoundaryCount") or 0) >= 1
        and settlement_count >= 1
        and int(evidence.get("readySettlementCount") or 0) == settlement_count
        and int(evidence.get("blockedSettlementCount") or 0) == 0
        and int(evidence.get("shortSettlementCount") or 0) == 0
        and int(evidence.get("tooFastNextJumpCount") or 0) == 0
        and int(evidence.get("genericLandingOrUtilityCount") or 0) == 0
        and int(evidence.get("textureReadyCount") or 0) == settlement_count
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("importantTransitionsMustSettleIntoScene") is True
        and evidence.get("landingClipMustBeReadableSceneFootage") is True
        and evidence.get("settlementWindowMustContainTextureOrPayoff") is True
        and evidence.get("nextImportantTransitionCannotArriveImmediately") is True
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_continuity_rehearsal_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_continuity_rehearsal_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    reports = data.get("reports") if isinstance(data.get("reports"), dict) else {}
    def report_status(key: str) -> Any:
        row = reports.get(key)
        return row.get("status") if isinstance(row, dict) else None

    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "rehearsalReadyRowCount": summary.get("rehearsalReadyRowCount"),
        "blockedRehearsalRowCount": summary.get("blockedRehearsalRowCount"),
        "adjacentPairCount": summary.get("adjacentPairCount"),
        "rehearsalReadyPairCount": summary.get("rehearsalReadyPairCount"),
        "blockedAdjacentPairCount": summary.get("blockedAdjacentPairCount"),
        "rowsWithMotionStyle": summary.get("rowsWithMotionStyle"),
        "adjacentMotionPairCount": summary.get("adjacentMotionPairCount"),
        "backToBackImportantPairCount": summary.get("backToBackImportantPairCount"),
        "landingToNextOutgoingAnchorReadyPairCount": summary.get("landingToNextOutgoingAnchorReadyPairCount"),
        "purposeRunMax": summary.get("purposeRunMax"),
        "highImpactPurposeRunViolationCount": summary.get("highImpactPurposeRunViolationCount"),
        "storyboardReadyRowCount": summary.get("storyboardReadyRowCount"),
        "readySensoryContinuityRowCount": summary.get("readySensoryContinuityRowCount"),
        "motionSpacingViolationCount": summary.get("motionSpacingViolationCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "sceneFlowBlockedCheckCount": summary.get("sceneFlowBlockedCheckCount"),
        "finalCutBlockedCheckCount": summary.get("finalCutBlockedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "transitionStoryboardStatus": report_status("transitionStoryboard"),
        "transitionSensoryContinuityStatus": report_status("transitionSensoryContinuity"),
        "transitionAuditionQualityStatus": report_status("transitionAuditionQuality"),
        "transitionAuditionVisualProofStatus": report_status("transitionAuditionVisualProof"),
        "transitionAuditionRoleIntegrityStatus": report_status("transitionAuditionRoleIntegrity"),
        "transitionBreathingRoomStatus": report_status("transitionBreathingRoom"),
        "transitionEffectPaletteStatus": report_status("transitionEffectPalette"),
        "transitionCadenceStatus": report_status("transitionCadence"),
        "referenceTransitionProfileStatus": report_status("referenceTransitionProfile"),
        "sceneFlowArcStatus": report_status("sceneFlowArc"),
        "finalCutSmoothnessStatus": report_status("finalCutSmoothness"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_continuity_rehearsal_contract_ready(evidence: dict[str, Any]) -> bool:
    rows = int(evidence.get("transitionRowCount") or 0)
    pairs = int(evidence.get("adjacentPairCount") or 0)
    upstream_keys = (
        "transitionStoryboardStatus",
        "transitionSensoryContinuityStatus",
        "transitionAuditionQualityStatus",
        "transitionAuditionVisualProofStatus",
        "transitionAuditionRoleIntegrityStatus",
        "transitionBreathingRoomStatus",
        "transitionEffectPaletteStatus",
        "transitionCadenceStatus",
        "referenceTransitionProfileStatus",
        "sceneFlowArcStatus",
        "finalCutSmoothnessStatus",
    )
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and rows >= 1
        and int(evidence.get("rehearsalReadyRowCount") or 0) == rows
        and int(evidence.get("blockedRehearsalRowCount") or 0) == 0
        and int(evidence.get("rehearsalReadyPairCount") or 0) == pairs
        and int(evidence.get("blockedAdjacentPairCount") or 0) == 0
        and int(evidence.get("landingToNextOutgoingAnchorReadyPairCount") or 0) == pairs
        and int(evidence.get("adjacentMotionPairCount") or 0) == 0
        and int(evidence.get("backToBackImportantPairCount") or 0) == 0
        and int(evidence.get("highImpactPurposeRunViolationCount") or 0) == 0
        and int(evidence.get("motionSpacingViolationCount") or 0) == 0
        and int(evidence.get("sceneFlowBlockedCheckCount") or 0) == 0
        and int(evidence.get("finalCutBlockedCheckCount") or 0) == 0
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and all(evidence.get(key) == "passed" for key in upstream_keys)
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_storyboard_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_storyboard_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "storyboardReadyRowCount": summary.get("storyboardReadyRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantStoryboardReadyCount": summary.get("importantStoryboardReadyCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsWithViewerPurpose": summary.get("rowsWithViewerPurpose"),
        "rowsWithOutgoingEvidence": summary.get("rowsWithOutgoingEvidence"),
        "rowsWithBridgeOrMotionBeat": summary.get("rowsWithBridgeOrMotionBeat"),
        "rowsWithLandingEvidence": summary.get("rowsWithLandingEvidence"),
        "rowsWithPreviewEvidence": summary.get("rowsWithPreviewEvidence"),
        "importantPreviewEvidenceCount": summary.get("importantPreviewEvidenceCount"),
        "importantBridgeOrMotionBeatCount": summary.get("importantBridgeOrMotionBeatCount"),
        "motionTransitionCount": summary.get("motionTransitionCount"),
        "motionReadyRowCount": summary.get("motionReadyRowCount"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_preview_packet_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_preview_packet" / "transition_preview_packet.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "previewRowCount": summary.get("previewRowCount"),
        "importantPreviewRowCount": summary.get("importantPreviewRowCount"),
        "readyPreviewRowCount": summary.get("readyPreviewRowCount"),
        "needsFrameExtractionRowCount": summary.get("needsFrameExtractionRowCount"),
        "blockedPreviewRowCount": summary.get("blockedPreviewRowCount"),
        "generatedFrameCount": summary.get("generatedFrameCount"),
        "ffmpegAvailable": summary.get("ffmpegAvailable"),
        "extractedFrames": summary.get("extractedFrames"),
        "updatedTransitionGrammar": summary.get("updatedTransitionGrammar"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_preview_packet_ready(evidence: dict[str, Any]) -> bool:
    important_rows = int(evidence.get("importantPreviewRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") in {"ready_with_transition_preview_packet", "ready_no_important_transitions"}
        and int(evidence.get("blockedPreviewRowCount") or 0) == 0
        and int(evidence.get("needsFrameExtractionRowCount") or 0) == 0
        and (important_rows == 0 or int(evidence.get("readyPreviewRowCount") or 0) >= important_rows)
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_preview_quality_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_preview_quality_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "previewRowCount": summary.get("previewRowCount"),
        "importantPreviewRowCount": summary.get("importantPreviewRowCount"),
        "previewQualityReadyRowCount": summary.get("previewQualityReadyRowCount"),
        "blockedPreviewQualityRowCount": summary.get("blockedPreviewQualityRowCount"),
        "passedFrameCount": summary.get("passedFrameCount"),
        "blockedFrameCount": summary.get("blockedFrameCount"),
        "importantRowsWithOutgoingLanding": summary.get("importantRowsWithOutgoingLanding"),
        "warningCount": summary.get("warningCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_preview_quality_contract_ready(evidence: dict[str, Any]) -> bool:
    important_rows = int(evidence.get("importantPreviewRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("blockedPreviewQualityRowCount") or 0) == 0
        and int(evidence.get("blockedFrameCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and (important_rows == 0 or int(evidence.get("previewQualityReadyRowCount") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("importantRowsWithOutgoingLanding") or 0) >= important_rows)
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_audition_packet_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_audition_packet" / "transition_audition_packet.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "auditionRowCount": summary.get("auditionRowCount"),
        "importantAuditionRowCount": summary.get("importantAuditionRowCount"),
        "readyAuditionRowCount": summary.get("readyAuditionRowCount"),
        "blockedAuditionRowCount": summary.get("blockedAuditionRowCount"),
        "auditionClipCount": summary.get("auditionClipCount"),
        "rowsWithMotionExecution": summary.get("rowsWithMotionExecution"),
        "rowsWithThreeBeatMotion": summary.get("rowsWithThreeBeatMotion"),
        "rowsWithBgmHitMotion": summary.get("rowsWithBgmHitMotion"),
        "rowsWithCaptionQuietMotion": summary.get("rowsWithCaptionQuietMotion"),
        "rowsWithMotionDirection": summary.get("rowsWithMotionDirection"),
        "rowsWithMotionDirectionMatch": summary.get("rowsWithMotionDirectionMatch"),
        "rowsWithCutpoint": summary.get("rowsWithCutpoint"),
        "rowsWithCutpointBgm": summary.get("rowsWithCutpointBgm"),
        "rowsWithCutpointLanding": summary.get("rowsWithCutpointLanding"),
        "rowsWithCutpointHandles": summary.get("rowsWithCutpointHandles"),
        "rowsWithActionAnchor": summary.get("rowsWithActionAnchor"),
        "rowsWithOutgoingActionAnchor": summary.get("rowsWithOutgoingActionAnchor"),
        "rowsWithBridgeOrMatchActionAnchor": summary.get("rowsWithBridgeOrMatchActionAnchor"),
        "rowsWithLandingActionAnchor": summary.get("rowsWithLandingActionAnchor"),
        "ffmpegAvailable": summary.get("ffmpegAvailable"),
        "builtClips": summary.get("builtClips"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_audition_packet_ready(evidence: dict[str, Any]) -> bool:
    important_rows = int(evidence.get("importantAuditionRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") in {"ready_with_transition_audition_packet", "ready_no_important_transitions"}
        and int(evidence.get("blockedAuditionRowCount") or 0) == 0
        and (important_rows == 0 or int(evidence.get("readyAuditionRowCount") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("auditionClipCount") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithMotionExecution") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithThreeBeatMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithBgmHitMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCaptionQuietMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithMotionDirection") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithMotionDirectionMatch") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpoint") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpointBgm") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpointLanding") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpointHandles") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithActionAnchor") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithOutgoingActionAnchor") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithBridgeOrMatchActionAnchor") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithLandingActionAnchor") or 0) >= important_rows)
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_audition_quality_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_audition_quality_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "auditionRowCount": summary.get("auditionRowCount"),
        "importantAuditionRowCount": summary.get("importantAuditionRowCount"),
        "auditionQualityReadyRowCount": summary.get("auditionQualityReadyRowCount"),
        "blockedAuditionQualityRowCount": summary.get("blockedAuditionQualityRowCount"),
        "auditionClipCount": summary.get("auditionClipCount"),
        "probeReadyClipCount": summary.get("probeReadyClipCount"),
        "noAudioClipCount": summary.get("noAudioClipCount"),
        "rowsWithMotionExecution": summary.get("rowsWithMotionExecution"),
        "rowsWithThreeBeatMotion": summary.get("rowsWithThreeBeatMotion"),
        "rowsWithBgmHitMotion": summary.get("rowsWithBgmHitMotion"),
        "rowsWithCaptionQuietMotion": summary.get("rowsWithCaptionQuietMotion"),
        "rowsWithMotionDirection": summary.get("rowsWithMotionDirection"),
        "rowsWithMotionDirectionMatch": summary.get("rowsWithMotionDirectionMatch"),
        "rowsWithCutpoint": summary.get("rowsWithCutpoint"),
        "rowsWithCutpointBgm": summary.get("rowsWithCutpointBgm"),
        "rowsWithCutpointLanding": summary.get("rowsWithCutpointLanding"),
        "rowsWithCutpointHandles": summary.get("rowsWithCutpointHandles"),
        "rowsWithActionAnchor": summary.get("rowsWithActionAnchor"),
        "rowsWithOutgoingActionAnchor": summary.get("rowsWithOutgoingActionAnchor"),
        "rowsWithBridgeOrMatchActionAnchor": summary.get("rowsWithBridgeOrMatchActionAnchor"),
        "rowsWithLandingActionAnchor": summary.get("rowsWithLandingActionAnchor"),
        "rowsWithResolveKeyframeEffect": summary.get("rowsWithResolveKeyframeEffect"),
        "warningCount": summary.get("warningCount"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_audition_quality_contract_ready(evidence: dict[str, Any]) -> bool:
    important_rows = int(evidence.get("importantAuditionRowCount") or 0)
    clip_count = int(evidence.get("auditionClipCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("blockedAuditionQualityRowCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and (important_rows == 0 or int(evidence.get("auditionQualityReadyRowCount") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithMotionExecution") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithThreeBeatMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithBgmHitMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCaptionQuietMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithMotionDirection") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithMotionDirectionMatch") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpoint") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpointBgm") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpointLanding") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCutpointHandles") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithActionAnchor") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithOutgoingActionAnchor") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithBridgeOrMatchActionAnchor") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithLandingActionAnchor") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithResolveKeyframeEffect") or 0) >= important_rows)
        and int(evidence.get("probeReadyClipCount") or 0) >= clip_count
        and int(evidence.get("noAudioClipCount") or 0) >= clip_count
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_audition_visual_proof_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_audition_visual_proof_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "auditionVisualRowCount": summary.get("auditionVisualRowCount"),
        "importantAuditionVisualRowCount": summary.get("importantAuditionVisualRowCount"),
        "passedAuditionVisualRowCount": summary.get("passedAuditionVisualRowCount"),
        "blockedAuditionVisualRowCount": summary.get("blockedAuditionVisualRowCount"),
        "rowsWithPackageLocalClip": summary.get("rowsWithPackageLocalClip"),
        "rowsWithProbeVideo": summary.get("rowsWithProbeVideo"),
        "rowsWithNoAudio": summary.get("rowsWithNoAudio"),
        "rowsWithFrameProof": summary.get("rowsWithFrameProof"),
        "rowsWithDistinctEndpointFrames": summary.get("rowsWithDistinctEndpointFrames"),
        "rowsWithMiddleMotionProof": summary.get("rowsWithMiddleMotionProof"),
        "rowsWithMotionExecution": summary.get("rowsWithMotionExecution"),
        "rowsWithThreeBeatMotion": summary.get("rowsWithThreeBeatMotion"),
        "rowsWithBgmHitMotion": summary.get("rowsWithBgmHitMotion"),
        "rowsWithCaptionQuietMotion": summary.get("rowsWithCaptionQuietMotion"),
        "rowsWithResolveKeyframeEffect": summary.get("rowsWithResolveKeyframeEffect"),
        "transitionAuditionQualityStatus": summary.get("transitionAuditionQualityStatus"),
        "ffmpegAvailable": summary.get("ffmpegAvailable"),
        "ffprobeAvailable": summary.get("ffprobeAvailable"),
        "extractedFrames": summary.get("extractedFrames"),
        "frameCountPerRow": summary.get("frameCountPerRow"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_audition_visual_proof_contract_ready(evidence: dict[str, Any]) -> bool:
    important_rows = int(evidence.get("importantAuditionVisualRowCount") or 0)
    row_count = int(evidence.get("auditionVisualRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("transitionAuditionQualityStatus") == "passed"
        and int(evidence.get("blockedAuditionVisualRowCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and (important_rows == 0 or int(evidence.get("passedAuditionVisualRowCount") or 0) >= important_rows)
        and int(evidence.get("rowsWithPackageLocalClip") or 0) >= row_count
        and int(evidence.get("rowsWithProbeVideo") or 0) >= row_count
        and int(evidence.get("rowsWithNoAudio") or 0) >= row_count
        and int(evidence.get("rowsWithFrameProof") or 0) >= row_count
        and int(evidence.get("rowsWithDistinctEndpointFrames") or 0) >= row_count
        and int(evidence.get("rowsWithMiddleMotionProof") or 0) >= row_count
        and (important_rows == 0 or int(evidence.get("rowsWithMotionExecution") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithThreeBeatMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithBgmHitMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithCaptionQuietMotion") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithResolveKeyframeEffect") or 0) >= important_rows)
        and evidence.get("ffmpegAvailable") is True
        and evidence.get("ffprobeAvailable") is True
        and evidence.get("extractedFrames") is True
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_audition_role_integrity_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "transition_audition_role_integrity_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "auditionRoleRowCount": summary.get("auditionRoleRowCount"),
        "importantAuditionRoleRowCount": summary.get("importantAuditionRoleRowCount"),
        "passedAuditionRoleRowCount": summary.get("passedAuditionRoleRowCount"),
        "blockedAuditionRoleRowCount": summary.get("blockedAuditionRoleRowCount"),
        "rowsWithRoleOrderedSegments": summary.get("rowsWithRoleOrderedSegments"),
        "rowsWithOutgoingLandingSegments": summary.get("rowsWithOutgoingLandingSegments"),
        "rowsWithBridgeOrMotionSegment": summary.get("rowsWithBridgeOrMotionSegment"),
        "rowsWithBridgeSegment": summary.get("rowsWithBridgeSegment"),
        "rowsWithAllSegmentsPassed": summary.get("rowsWithAllSegmentsPassed"),
        "rowsWithConcatOrderEvidence": summary.get("rowsWithConcatOrderEvidence"),
        "rowsWithMotionExecution": summary.get("rowsWithMotionExecution"),
        "rowsWithThreeBeatRoles": summary.get("rowsWithThreeBeatRoles"),
        "transitionAuditionQualityStatus": summary.get("transitionAuditionQualityStatus"),
        "transitionAuditionVisualProofStatus": summary.get("transitionAuditionVisualProofStatus"),
        "ffprobeAvailable": summary.get("ffprobeAvailable"),
        "blockerCount": len(data.get("blockers") or []),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def transition_audition_role_integrity_contract_ready(evidence: dict[str, Any]) -> bool:
    important_rows = int(evidence.get("importantAuditionRoleRowCount") or 0)
    row_count = int(evidence.get("auditionRoleRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("transitionAuditionQualityStatus") == "passed"
        and evidence.get("transitionAuditionVisualProofStatus") == "passed"
        and int(evidence.get("blockedAuditionRoleRowCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and (important_rows == 0 or int(evidence.get("passedAuditionRoleRowCount") or 0) >= important_rows)
        and int(evidence.get("rowsWithRoleOrderedSegments") or 0) >= row_count
        and int(evidence.get("rowsWithOutgoingLandingSegments") or 0) >= row_count
        and int(evidence.get("rowsWithBridgeOrMotionSegment") or 0) >= row_count
        and (important_rows == 0 or int(evidence.get("rowsWithBridgeSegment") or 0) >= important_rows)
        and int(evidence.get("rowsWithAllSegmentsPassed") or 0) >= row_count
        and int(evidence.get("rowsWithConcatOrderEvidence") or 0) >= row_count
        and (important_rows == 0 or int(evidence.get("rowsWithMotionExecution") or 0) >= important_rows)
        and (important_rows == 0 or int(evidence.get("rowsWithThreeBeatRoles") or 0) >= important_rows)
        and evidence.get("ffprobeAvailable") is True
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def transition_storyboard_contract_ready(evidence: dict[str, Any]) -> bool:
    important_boundaries = int(evidence.get("importantBoundaryCount") or 0)
    transition_rows = int(evidence.get("transitionRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and int(evidence.get("visualBoundaryCount") or 0) >= 1
        and transition_rows >= int(evidence.get("visualBoundaryCount") or 0)
        and int(evidence.get("storyboardReadyRowCount") or 0) == transition_rows
        and int(evidence.get("blockedRowCount") or 0) == 0
        and int(evidence.get("rowsWithDecisionFields") or 0) == transition_rows
        and int(evidence.get("rowsWithViewerPurpose") or 0) == transition_rows
        and int(evidence.get("rowsWithOutgoingEvidence") or 0) == transition_rows
        and int(evidence.get("rowsWithLandingEvidence") or 0) == transition_rows
        and (important_boundaries == 0 or int(evidence.get("importantStoryboardReadyCount") or 0) >= important_boundaries)
        and (important_boundaries == 0 or int(evidence.get("importantBridgeOrMotionBeatCount") or 0) >= important_boundaries)
        and (important_boundaries == 0 or int(evidence.get("importantPreviewEvidenceCount") or 0) >= important_boundaries)
        and int(evidence.get("motionReadyRowCount") or 0) == int(evidence.get("motionTransitionCount") or 0)
        and int(evidence.get("blockedCheckCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def unattended_first_draft_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "unattended_first_draft_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "passedGateCount": summary.get("passedGateCount"),
        "blockedGateCount": summary.get("blockedGateCount"),
        "warningGateCount": summary.get("warningGateCount"),
        "requiredGateCount": summary.get("requiredGateCount"),
        "totalGateCount": summary.get("totalGateCount"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def unattended_first_draft_contract_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") in {"passed", "passed_with_warnings"}
        and int(evidence.get("requiredGateCount") or 0) >= 14
        and int(evidence.get("totalGateCount") or 0) >= int(evidence.get("requiredGateCount") or 0)
        and int(evidence.get("blockedGateCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and int(evidence.get("passedGateCount") or 0) >= int(evidence.get("requiredGateCount") or 0)
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def unattended_repair_queue_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "unattended_repair_queue" / "unattended_repair_queue.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rows = data.get("repairRows") if isinstance(data.get("repairRows"), list) else []
    row_count = len([row for row in rows if isinstance(row, dict)])
    actionable_rows = len([row for row in rows if isinstance(row, dict) and row.get("actionable") is True])
    rows_with_forbidden = len([row for row in rows if isinstance(row, dict) and row.get("forbiddenWorkaround")])
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "requiredReportCount": summary.get("requiredReportCount"),
        "missingRequiredReportCount": summary.get("missingRequiredReportCount"),
        "blockedReportCount": summary.get("blockedReportCount"),
        "repairRowCount": summary.get("repairRowCount"),
        "p0RepairRowCount": summary.get("p0RepairRowCount"),
        "actionableRepairRowCount": summary.get("actionableRepairRowCount"),
        "unactionableRepairRowCount": summary.get("unactionableRepairRowCount"),
        "rowsWithOwnerScript": summary.get("rowsWithOwnerScript"),
        "rowsWithCommand": summary.get("rowsWithCommand"),
        "rowsWithAcceptanceEvidence": summary.get("rowsWithAcceptanceEvidence"),
        "rowsWithForbiddenWorkaround": summary.get("rowsWithForbiddenWorkaround"),
        "rowCountByRows": row_count,
        "actionableRowsByRows": actionable_rows,
        "rowsWithForbiddenWorkaroundByRows": rows_with_forbidden,
        "phaseCounts": summary.get("phaseCounts"),
        "blockerCount": len(data.get("blockers") or []),
        "warningCount": len(data.get("warnings") or []),
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def unattended_repair_queue_ready(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_no_unattended_repairs_needed"
        and int(evidence.get("requiredReportCount") or 0) >= 10
        and int(evidence.get("missingRequiredReportCount") or 0) == 0
        and int(evidence.get("blockedReportCount") or 0) == 0
        and int(evidence.get("repairRowCount") or 0) == 0
        and int(evidence.get("p0RepairRowCount") or 0) == 0
        and int(evidence.get("unactionableRepairRowCount") or 0) == 0
        and int(evidence.get("rowCountByRows") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def effect_motion_application_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "effect_motion_application_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    rows = data.get("effectRows") if isinstance(data.get("effectRows"), list) else []
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "finalBlueprint": inputs.get("finalBlueprint"),
        "finalBlueprintExists": inputs.get("finalBlueprintExists"),
        "finalBlueprintKind": inputs.get("finalBlueprintKind"),
        "finalBlueprintInsidePackage": inputs.get("finalBlueprintInsidePackage"),
        "effectMotionStatus": inputs.get("effectMotionStatus"),
        "sourceCandidateExists": inputs.get("sourceCandidateExists"),
        "sourceCandidateInsidePackage": inputs.get("sourceCandidateInsidePackage"),
        "finalHasEffectMotionBlueprintPlan": inputs.get("finalHasEffectMotionBlueprintPlan"),
        "finalBlueprintLineageStatus": inputs.get("finalBlueprintLineageStatus"),
        "sourceEffectRowCount": summary.get("sourceEffectRowCount"),
        "finalEffectMotionCandidateCount": summary.get("finalEffectMotionCandidateCount"),
        "auditedEffectRowCount": summary.get("auditedEffectRowCount"),
        "passedEffectRowCount": summary.get("passedEffectRowCount"),
        "blockedEffectRowCount": summary.get("blockedEffectRowCount"),
        "motionEffectRowCount": summary.get("motionEffectRowCount"),
        "maxMotionAllowed": summary.get("maxMotionAllowed"),
        "titleEffectRowCount": summary.get("titleEffectRowCount"),
        "bgmOnlyRowCount": summary.get("bgmOnlyRowCount"),
        "titleSafeRowCount": summary.get("titleSafeRowCount"),
        "sourceEvidenceRowCount": summary.get("sourceEvidenceRowCount"),
        "motionEvidenceRowCount": summary.get("motionEvidenceRowCount"),
        "decisionFieldsRowCount": summary.get("decisionFieldsRowCount"),
        "clipAnnotationRowCount": summary.get("clipAnnotationRowCount"),
        "markerRowCount": summary.get("markerRowCount"),
        "forbiddenEffectHitCount": summary.get("forbiddenEffectHitCount"),
        "rowCount": len(rows),
        "passedRowCount": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "passed"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": data.get("blockers") or [],
        "warnings": data.get("warnings") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def effect_motion_application_contract_ready(evidence: dict[str, Any]) -> bool:
    row_count = int(evidence.get("sourceEffectRowCount") or 0)
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("finalBlueprintExists") is True
        and evidence.get("finalBlueprintInsidePackage") is True
        and evidence.get("sourceCandidateExists") is True
        and evidence.get("sourceCandidateInsidePackage") is True
        and evidence.get("finalHasEffectMotionBlueprintPlan") is True
        and evidence.get("finalBlueprintLineageStatus") == "passed"
        and evidence.get("effectMotionStatus") == "ready_with_effect_motion_blueprint"
        and row_count >= 3
        and int(evidence.get("auditedEffectRowCount") or 0) == row_count
        and int(evidence.get("passedEffectRowCount") or 0) == row_count
        and int(evidence.get("passedRowCount") or 0) == row_count
        and int(evidence.get("blockedEffectRowCount") or 0) == 0
        and int(evidence.get("motionEffectRowCount") or 0) <= int(evidence.get("maxMotionAllowed") or 0)
        and int(evidence.get("bgmOnlyRowCount") or 0) == row_count
        and int(evidence.get("titleSafeRowCount") or 0) == row_count
        and int(evidence.get("sourceEvidenceRowCount") or 0) == row_count
        and int(evidence.get("motionEvidenceRowCount") or 0) == row_count
        and int(evidence.get("decisionFieldsRowCount") or 0) == row_count
        and int(evidence.get("clipAnnotationRowCount") or 0) == row_count
        and int(evidence.get("markerRowCount") or 0) == row_count
        and int(evidence.get("forbiddenEffectHitCount") or 0) == 0
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def rhythm_recut_application_contract_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "rhythm_recut_application_contract_audit.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    upstream = inputs.get("upstreamReports") if isinstance(inputs.get("upstreamReports"), dict) else {}
    rows = data.get("recutRows") if isinstance(data.get("recutRows"), list) else []
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "blueprint": inputs.get("blueprint"),
        "blueprintExists": inputs.get("blueprintExists"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "upstreamReadyCount": sum(
            1
            for row in upstream.values()
            if isinstance(row, dict) and row.get("exists") is True and row.get("status") in set(row.get("acceptedStatuses") or [])
        ),
        "upstreamReportCount": len(upstream),
        "recutStatus": summary.get("recutStatus"),
        "recutSourceRowCount": summary.get("recutSourceRowCount"),
        "passedRecutRowCount": summary.get("passedRecutRowCount"),
        "blockedRecutRowCount": summary.get("blockedRecutRowCount"),
        "finalRhythmRecutClipCount": summary.get("finalRhythmRecutClipCount"),
        "finalRhythmRecutMainSegmentCount": summary.get("finalRhythmRecutMainSegmentCount"),
        "finalRhythmRecutCutawayCount": summary.get("finalRhythmRecutCutawayCount"),
        "finalLongShotRiskCount": summary.get("finalLongShotRiskCount"),
        "recutAverageBeforeSeconds": summary.get("recutAverageBeforeSeconds"),
        "recutAverageAfterSeconds": summary.get("recutAverageAfterSeconds"),
        "recutLongRiskBefore": summary.get("recutLongRiskBefore"),
        "recutLongRiskAfter": summary.get("recutLongRiskAfter"),
        "recutDurationDeltaSeconds": summary.get("recutDurationDeltaSeconds"),
        "bgmPhrasePlanPreserved": summary.get("bgmPhrasePlanPreserved"),
        "rowCount": len(rows),
        "passedRowCount": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "passed"),
        "blockerCount": summary.get("blockerCount"),
        "warningCount": summary.get("warningCount"),
        "blockers": data.get("blockers") or [],
        "writesResolve": safety.get("writesResolve"),
        "queuesRender": safety.get("queuesRender"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "modifiesSourceFootage": safety.get("modifiesSourceFootage"),
        "modifiesSourceDrive": safety.get("modifiesSourceDrive"),
    }


def rhythm_recut_application_contract_ready(evidence: dict[str, Any]) -> bool:
    recut_status = evidence.get("recutStatus")
    row_count = int(evidence.get("recutSourceRowCount") or 0)
    no_recut_needed = (
        recut_status == "ready_no_recut_needed"
        and row_count == 0
        and int(evidence.get("blockedRecutRowCount") or 0) == 0
    )
    recut_applied = (
        recut_status == "ready_with_rhythm_recut_blueprint"
        and row_count >= 1
        and int(evidence.get("passedRecutRowCount") or 0) == row_count
        and int(evidence.get("blockedRecutRowCount") or 0) == 0
        and int(evidence.get("finalRhythmRecutMainSegmentCount") or 0) >= row_count
        and int(evidence.get("finalRhythmRecutCutawayCount") or 0) >= row_count
        and float(evidence.get("recutAverageAfterSeconds") or 0) < float(evidence.get("recutAverageBeforeSeconds") or 0)
        and int(evidence.get("recutLongRiskAfter") or 0) < int(evidence.get("recutLongRiskBefore") or 0)
    )
    return (
        evidence.get("exists")
        and evidence.get("status") == "passed"
        and evidence.get("blueprintExists") is True
        and evidence.get("blueprintInsidePackage") is True
        and (
            evidence.get("blueprintKind") in {"transition_polish_candidate", "rhythm_recut_candidate", "explicit_blueprint"}
            or (no_recut_needed and evidence.get("blueprintKind") == "active_blueprint")
        )
        and int(evidence.get("upstreamReadyCount") or 0) == int(evidence.get("upstreamReportCount") or -1)
        and (recut_applied or no_recut_needed)
        and int(evidence.get("blockerCount") or 0) == 0
        and not evidence.get("blockers")
        and evidence.get("writesResolve") is False
        and evidence.get("queuesRender") is False
        and evidence.get("downloadsExternalAssets") is False
        and evidence.get("modifiesSourceFootage") is False
        and evidence.get("modifiesSourceDrive") is False
    )


def rhythm_recut_apply_package_evidence(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "rhythm_recut_blueprint" / "rhythm_recut_apply_package_report.json"
    if not path.exists():
        path = package_dir / "rhythm_recut_apply_package_report.json"
    data = load_json(path) or {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    source_summary = summary.get("sourceCandidateSummary") if isinstance(summary.get("sourceCandidateSummary"), dict) else {}
    preflight = data.get("preflight") if isinstance(data.get("preflight"), dict) else {}
    safety = data.get("safety") if isinstance(data.get("safety"), dict) else {}
    output_package = Path(str(data.get("outputPackage") or ""))
    active_blueprint = Path(str(data.get("activeBlueprint") or ""))
    output_report = output_package / "rhythm_recut_apply_package_report.json" if output_package else Path("")
    blueprint = load_json(active_blueprint) if active_blueprint.exists() else {}
    plan = blueprint.get("rhythmRecutPlan") if isinstance(blueprint, dict) and isinstance(blueprint.get("rhythmRecutPlan"), dict) else {}
    next_actions = data.get("nextActions") if isinstance(data.get("nextActions"), list) else []
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "outputPackage": str(output_package) if data.get("outputPackage") else None,
        "outputPackageExists": output_package.exists() if data.get("outputPackage") else False,
        "outputReportExists": output_report.exists() if data.get("outputPackage") else False,
        "activeBlueprint": str(active_blueprint) if data.get("activeBlueprint") else None,
        "activeBlueprintExists": active_blueprint.exists() if data.get("activeBlueprint") else False,
        "activeBlueprintSnapshot": data.get("activeBlueprintSnapshot"),
        "projectName": data.get("projectName"),
        "timelineName": data.get("timelineName"),
        "sourceCandidateStatus": summary.get("sourceCandidateStatus"),
        "activeClipCount": summary.get("activeClipCount"),
        "candidateRevisedClipCount": source_summary.get("revisedClipCount"),
        "candidateCutawayInsertCount": source_summary.get("cutawayInsertCount"),
        "candidateLongShotRiskAfter": source_summary.get("longShotRiskAfter"),
        "candidateDurationDeltaSeconds": source_summary.get("durationDeltaSeconds"),
        "copiedFinalRenderEvidence": summary.get("copiedFinalRenderEvidence"),
        "preflightStatus": preflight.get("status"),
        "preflightReturnCode": preflight.get("returnCode"),
        "preflightBlockerCount": preflight.get("blockerCount"),
        "preflightReport": preflight.get("report"),
        "preflightReportExists": Path(str(preflight.get("report") or "")).exists() if preflight.get("report") else False,
        "rhythmRecutPlanStatus": plan.get("status"),
        "rhythmRecutPlanRequiresPreflight": plan.get("requiresResolvePreflightBeforeApply"),
        "safetyWritesResolve": safety.get("writesResolve"),
        "safetyQueuesRender": safety.get("queuesRender"),
        "safetyDownloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "safetyModifiesSourcePackageBlueprint": safety.get("modifiesSourcePackageBlueprint"),
        "safetyCopiesFinalRenderEvidence": safety.get("copiesFinalRenderEvidence"),
        "requiresResolveApplyContract": safety.get("requiresResolveApplyContract"),
        "requiresReadbackAfterApply": safety.get("requiresReadbackAfterApply"),
        "hasDryRunNextAction": any("build_resolve_timeline.py --blueprint" in str(item) and "--json" in str(item) for item in next_actions),
        "hasApplyContractNextAction": any("prepare_resolve_apply_contract.py" in str(item) for item in next_actions),
        "hasReadbackNextAction": any("audit_resolve_timeline.py" in str(item) for item in next_actions),
    }


def rhythm_recut_apply_package_ready(evidence: dict[str, Any]) -> bool:
    candidate_status = evidence.get("sourceCandidateStatus")
    risk_after_value = evidence.get("candidateLongShotRiskAfter")
    risk_after = int(risk_after_value) if risk_after_value is not None else 9999
    recut_candidate_ok = (
        candidate_status == "ready_no_recut_needed"
        or (
            candidate_status == "ready_with_rhythm_recut_blueprint"
            and int(evidence.get("candidateCutawayInsertCount") or 0) >= 1
            and risk_after == 0
        )
    )
    return (
        evidence.get("exists")
        and evidence.get("status") == "ready_for_resolve_apply_contract"
        and evidence.get("outputPackageExists") is True
        and evidence.get("outputReportExists") is True
        and evidence.get("activeBlueprintExists") is True
        and recut_candidate_ok
        and int(evidence.get("activeClipCount") or 0) == int(evidence.get("candidateRevisedClipCount") or 0)
        and abs(float(evidence.get("candidateDurationDeltaSeconds") or 0.0)) <= 0.5
        and evidence.get("copiedFinalRenderEvidence") is False
        and evidence.get("preflightStatus") in {"ready", "ready_with_warnings"}
        and int(evidence.get("preflightReturnCode") or 0) == 0
        and int(evidence.get("preflightBlockerCount") or 0) == 0
        and evidence.get("preflightReportExists") is True
        and evidence.get("rhythmRecutPlanStatus") == "applied_to_package_pending_resolve_apply"
        and evidence.get("rhythmRecutPlanRequiresPreflight") is True
        and evidence.get("safetyWritesResolve") is False
        and evidence.get("safetyQueuesRender") is False
        and evidence.get("safetyDownloadsExternalAssets") is False
        and evidence.get("safetyModifiesSourcePackageBlueprint") is False
        and evidence.get("safetyCopiesFinalRenderEvidence") is False
        and evidence.get("requiresResolveApplyContract") is True
        and evidence.get("requiresReadbackAfterApply") is True
        and evidence.get("hasDryRunNextAction") is True
        and evidence.get("hasApplyContractNextAction") is True
        and evidence.get("hasReadbackNextAction") is True
    )


def status_of(package_dir: Path, rel: str) -> str | None:
    data = load_json(package_dir / rel)
    return data.get("status") if isinstance(data, dict) else None


def checks_with_text(data: dict[str, Any], needle: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("checks", "requirements"):
        for row in data.get(key) or []:
            text = " ".join(str(row.get(field) or "") for field in ("name", "requirement"))
            if needle.lower() in text.lower():
                out.append(row)
    return out


def any_passed(data: dict[str, Any], needle: str) -> bool:
    return any(row.get("status") == "passed" for row in checks_with_text(data, needle))


def feedback_labels(data: dict[str, Any]) -> list[str]:
    value = data.get("feedbackTimestamps")
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())
    if isinstance(value, list):
        labels: list[str] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            for key in ("id", "label"):
                if item.get(key):
                    labels.append(str(item[key]))
        return sorted(set(labels))
    return []


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else ("warning" if warning else "blocked"),
            "evidence": evidence,
        }
    )


def build_report(package_dir: Path, skill_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    skill_dir = skill_dir.expanduser().resolve()
    checks: list[dict[str, Any]] = []

    skill_patterns, _ = text_contains(skill_dir / "SKILL.md", REQUIRED_SKILL_PATTERNS)
    add_check(
        checks,
        "Skill instructions preserve the user's regression lessons",
        all(skill_patterns.values()),
        {"skill": str(skill_dir / "SKILL.md"), "patterns": skill_patterns},
    )

    script_evidence: dict[str, Any] = {}
    missing_scripts: list[str] = []
    for group, scripts in REQUIRED_SCRIPTS.items():
        group_missing = [name for name in scripts if not (skill_dir / "scripts" / name).exists()]
        script_evidence[group] = {"required": scripts, "missing": group_missing}
        missing_scripts.extend(group_missing)
    add_check(
        checks,
        "Reusable scripts cover recognition, DaVinci, and user-regression gates",
        not missing_scripts,
        script_evidence,
    )

    style_patterns, _ = text_contains(skill_dir / "references" / "bilibili-travel-style.md", REQUIRED_STYLE_PATTERNS)
    add_check(
        checks,
        "Bilibili/Malta style references are source-anchored and non-copying",
        all(style_patterns.values()),
        {"reference": str(skill_dir / "references" / "bilibili-travel-style.md"), "patterns": style_patterns},
    )
    parallel_patterns, _ = text_contains(skill_dir / "references" / "parallel-world-vlog-style.md", REQUIRED_PARALLEL_WORLD_PATTERNS)
    add_check(
        checks,
        "Parallel World full-review, cover, opening, transition, and ending lessons are reusable",
        all(parallel_patterns.values()),
        {"reference": str(skill_dir / "references" / "parallel-world-vlog-style.md"), "patterns": parallel_patterns},
    )
    reference_evidence = reference_profile_evidence(find_reference_analysis(package_dir))
    add_check(
        checks,
        "Malta reference analysis is a reusable pacing/audio/sample-frame profile",
        reference_profile_ready(reference_evidence),
        reference_evidence,
    )
    reference_batch_evidence = reference_batch_profile_evidence(package_dir)
    add_check(
        checks,
        "Reference batch profile learns from multiple supplied creator/reference videos without copying assets",
        reference_batch_profile_ready(reference_batch_evidence),
        reference_batch_evidence,
    )
    reference_profile_application_evidence = reference_profile_application_contract_evidence(package_dir)
    add_check(
        checks,
        "Reference profile application contract proves the reference batch reaches opening, chapter, rhythm, creator, transition, caption, audio, and style gates",
        reference_profile_application_contract_ready(reference_profile_application_evidence),
        reference_profile_application_evidence,
    )
    reference_transition_profile_evidence = reference_transition_profile_contract_evidence(package_dir)
    add_check(
        checks,
        "Reference transition profile contract proves learned references become restrained bridge, breath, match, and motion-balance targets",
        reference_transition_profile_contract_ready(reference_transition_profile_evidence),
        reference_transition_profile_evidence,
    )
    bgm_evidence = bgm_sourcing_evidence(package_dir)
    add_check(
        checks,
        "BGM sourcing brief proactively turns missing-BGM feedback into exact search and decision rows",
        bgm_sourcing_ready(bgm_evidence),
        bgm_evidence,
    )
    bgm_selection_evidence = bgm_selection_package_evidence(package_dir)
    add_check(
        checks,
        "BGM selection package proves music is local, license-traceable, buildable, and blueprint-referenced",
        bgm_selection_package_ready(bgm_selection_evidence),
        bgm_selection_evidence,
    )
    bgm_phrase_evidence = bgm_phrase_blueprint_evidence(package_dir)
    add_check(
        checks,
        "BGM phrase blueprint materializes selected music into section, clip, and transition-cue metadata",
        bgm_phrase_blueprint_ready(bgm_phrase_evidence),
        bgm_phrase_evidence,
    )
    bridge_plan_evidence = transition_bridge_plan_evidence(package_dir)
    add_check(
        checks,
        "Transition bridge plan proactively turns hard-cut/day-jump feedback into exact bridge rows",
        transition_bridge_plan_ready(bridge_plan_evidence),
        bridge_plan_evidence,
    )
    caption_plan_evidence = caption_story_plan_evidence(package_dir)
    add_check(
        checks,
        "Caption story plan proactively turns sparse-subtitle/no-voiceover feedback into dense TXT/SRT rows",
        caption_story_plan_ready(caption_plan_evidence),
        caption_plan_evidence,
    )
    title_plan_evidence = title_typography_plan_evidence(package_dir)
    add_check(
        checks,
        "Title typography plan proactively turns ghosted/stacked-title feedback into exact title rows",
        title_typography_plan_ready(title_plan_evidence),
        title_plan_evidence,
    )
    cover_title_evidence = cover_title_contract_evidence(package_dir)
    add_check(
        checks,
        "Cover title contract enforces Parallel World-style hero title without route/date clutter",
        cover_title_contract_ready(cover_title_evidence),
        cover_title_evidence,
    )
    title_visual_proof_evidence = title_visual_proof_contract_evidence(package_dir)
    add_check(
        checks,
        "Title visual proof contract proves clean title media with actual local frames, not only manifests",
        title_visual_proof_contract_ready(title_visual_proof_evidence),
        title_visual_proof_evidence,
    )
    visual_plan_evidence = visual_establishing_plan_evidence(package_dir)
    add_check(
        checks,
        "Visual establishing plan proactively turns missing-aerial/landmark feedback into exact opening/chapter/ending rows",
        visual_establishing_plan_ready(visual_plan_evidence),
        visual_plan_evidence,
    )
    effect_plan_evidence = effect_motion_plan_evidence(package_dir)
    add_check(
        checks,
        "Effect motion plan proactively turns bare-concatenation/template-effect feedback into restrained motion rows",
        effect_motion_plan_ready(effect_plan_evidence),
        effect_plan_evidence,
    )
    effect_blueprint_evidence = effect_motion_blueprint_evidence(package_dir)
    add_check(
        checks,
        "Effect motion blueprint materializes restrained title and transition effects into a non-destructive Resolve candidate",
        effect_motion_blueprint_ready(effect_blueprint_evidence),
        effect_blueprint_evidence,
    )
    feedback_plan_evidence = feedback_regression_plan_evidence(package_dir)
    add_check(
        checks,
        "Feedback regression plan preserves concrete user complaints as reusable pre-render and post-render probes",
        feedback_regression_plan_ready(feedback_plan_evidence),
        feedback_plan_evidence,
    )
    audio_policy_evidence = audio_scene_policy_plan_evidence(package_dir)
    add_check(
        checks,
        "Audio scene policy plan proactively turns scenic/title voice-leak and missing-BGM feedback into A3 BGM-only rows",
        audio_scene_policy_plan_ready(audio_policy_evidence),
        audio_policy_evidence,
    )
    footage_select_evidence = footage_select_plan_evidence(package_dir)
    add_check(
        checks,
        "Footage select plan turns the raw source pool into hero, main, texture, repair, and reject decisions before first assembly",
        footage_select_plan_ready(footage_select_evidence),
        footage_select_evidence,
    )
    raw_intake_evidence = raw_intake_completeness_evidence(package_dir)
    add_check(
        checks,
        "Raw intake completeness proves every active source video is indexed, recognized, routed exactly once, and scored",
        raw_intake_completeness_ready(raw_intake_evidence),
        raw_intake_evidence,
    )
    source_repair_evidence = source_selection_repair_plan_evidence(package_dir)
    add_check(
        checks,
        "Source selection repair plan proves each chapter has local movement, texture, payoff, and no blocking source gaps before first assembly",
        source_selection_repair_plan_ready(source_repair_evidence),
        source_repair_evidence,
    )
    first_assembly_source_order_evidence = first_assembly_source_order_contract_evidence(package_dir)
    add_check(
        checks,
        "First assembly source order contract proves large unordered folders are cut by full-source selection, not filename order or blueprint fallback samples",
        first_assembly_source_order_contract_ready(first_assembly_source_order_evidence),
        first_assembly_source_order_evidence,
    )
    large_source_unattended_evidence = large_source_unattended_readiness_contract_evidence(package_dir)
    add_check(
        checks,
        "Large source unattended readiness contract proves 100GB unordered folders are media-indexed, recognized, source-selected, first-assembled, and preflighted without filename-order fallback",
        large_source_unattended_readiness_contract_ready(large_source_unattended_evidence),
        large_source_unattended_evidence,
    )
    opening_story_evidence = opening_story_plan_evidence(package_dir)
    add_check(
        checks,
        "Opening story plan proves the first three minutes have viewer promise, destination proof, clean title, route arrival, lived-in texture, and handoff",
        opening_story_plan_ready(opening_story_evidence),
        opening_story_evidence,
    )
    chapter_arc_evidence = chapter_arc_plan_evidence(package_dir)
    add_check(
        checks,
        "Chapter arc plan forces each chapter through context, movement, texture, payoff, and aftertaste before rhythm or Resolve trust",
        chapter_arc_plan_ready(chapter_arc_evidence),
        chapter_arc_evidence,
    )
    rhythm_plan_evidence = edit_rhythm_plan_evidence(package_dir)
    add_check(
        checks,
        "Edit rhythm plan proactively turns AI-assembly and flat pacing feedback into shot-purpose rows",
        edit_rhythm_plan_ready(rhythm_plan_evidence),
        rhythm_plan_evidence,
    )
    creator_cut_evidence = creator_cut_plan_evidence(package_dir)
    add_check(
        checks,
        "Creator cut plan turns reference quality into selective shot choice, bridge use, and motivated transition decisions",
        creator_cut_plan_ready(creator_cut_evidence),
        creator_cut_evidence,
    )
    creator_cut_application_evidence = creator_cut_application_contract_evidence(package_dir)
    add_check(
        checks,
        "Creator cut application contract proves the final candidate blueprint actually applies selective shot choice",
        creator_cut_application_contract_ready(creator_cut_application_evidence),
        creator_cut_application_evidence,
    )
    transition_grammar_evidence = transition_grammar_plan_evidence(package_dir)
    add_check(
        checks,
        "Transition grammar plan turns adjacent clip pairs into specific cut, dissolve, match, whip, rotation, or bridge-insert decisions",
        transition_grammar_plan_ready(transition_grammar_evidence),
        transition_grammar_evidence,
    )
    transition_execution_evidence = transition_execution_plan_evidence(package_dir)
    add_check(
        checks,
        "Transition execution plan turns adjacent-pair transition choices into Resolve-ready recipes with bridge, BGM, subtitle, and readback fields",
        transition_execution_plan_ready(transition_execution_evidence),
        transition_execution_evidence,
    )
    transition_execution_blueprint = transition_execution_blueprint_evidence(package_dir)
    add_check(
        checks,
        "Transition execution blueprint materializes adjacent-pair recipes into a non-destructive Resolve candidate",
        transition_execution_blueprint_ready(transition_execution_blueprint),
        transition_execution_blueprint,
    )
    transition_motif_evidence = transition_motif_plan_evidence(package_dir)
    add_check(
        checks,
        "Transition motif plan prevents repeated dissolve chains, random motion effects, and effects hiding weak route jumps",
        transition_motif_plan_ready(transition_motif_evidence),
        transition_motif_evidence,
    )
    transition_motif_coherence_evidence = transition_motif_coherence_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition motif coherence proves transition motifs form one reference-like film language instead of random per-cut effects",
        transition_motif_coherence_contract_ready(transition_motif_coherence_evidence),
        transition_motif_coherence_evidence,
    )
    bridge_sequence_evidence = bridge_sequence_plan_evidence(package_dir)
    add_check(
        checks,
        "Bridge sequence plan turns important transitions into 2-5 shot route/title bridge sequences instead of single effects",
        bridge_sequence_plan_ready(bridge_sequence_evidence),
        bridge_sequence_evidence,
    )
    bridge_sequence_blueprint = bridge_sequence_blueprint_evidence(package_dir)
    add_check(
        checks,
        "Bridge sequence blueprint materializes planned bridge beats into a non-destructive Resolve candidate",
        bridge_sequence_blueprint_ready(bridge_sequence_blueprint),
        bridge_sequence_blueprint,
    )
    bridge_sequence_application = bridge_sequence_application_contract_evidence(package_dir)
    add_check(
        checks,
        "Bridge sequence application contract proves planned 2-5 shot bridge beats survive into the final candidate blueprint",
        bridge_sequence_application_contract_ready(bridge_sequence_application),
        bridge_sequence_application,
    )
    transition_bridge_visual_evidence = transition_bridge_visual_evidence_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition bridge visual evidence contract proves bridge beats are real local video with frame evidence, not prose or effects only",
        transition_bridge_visual_evidence_contract_ready(transition_bridge_visual_evidence),
        transition_bridge_visual_evidence,
    )
    final_blueprint_lineage = final_blueprint_lineage_contract_evidence(package_dir)
    add_check(
        checks,
        "Final blueprint lineage contract proves the active blueprint inherits the latest ready candidate chain",
        final_blueprint_lineage_contract_ready(final_blueprint_lineage),
        final_blueprint_lineage,
    )
    effect_motion_application = effect_motion_application_contract_evidence(package_dir)
    add_check(
        checks,
        "Effect motion application contract proves restrained title and route-motion effects survive into the final blueprint",
        effect_motion_application_contract_ready(effect_motion_application),
        effect_motion_application,
    )
    final_source_usage = final_source_usage_contract_evidence(package_dir)
    add_check(
        checks,
        "Final source usage contract proves the active blueprint actually consumes footage-select hero/main/texture choices",
        final_source_usage_contract_ready(final_source_usage),
        final_source_usage,
    )
    reference_repair_evidence = reference_style_repair_plan_evidence(package_dir)
    add_check(
        checks,
        "Reference style repair plan turns blocked reference, director, and QA checks into executable repair rows",
        reference_style_repair_plan_ready(reference_repair_evidence),
        reference_repair_evidence,
    )
    reference_repair_closure = reference_repair_closure_evidence(package_dir)
    add_check(
        checks,
        "Reference repair closure audit proves P0 style repairs are closed before another Resolve claim",
        reference_repair_closure_ready(reference_repair_closure),
        reference_repair_closure,
    )
    rhythm_recut_evidence = rhythm_recut_blueprint_evidence(package_dir)
    add_check(
        checks,
        "Rhythm recut blueprint converts flat-pacing diagnosis into a safe candidate Resolve blueprint",
        rhythm_recut_blueprint_ready(rhythm_recut_evidence),
        rhythm_recut_evidence,
    )
    rhythm_recut_application_evidence = rhythm_recut_application_contract_evidence(package_dir)
    add_check(
        checks,
        "Rhythm recut application contract proves the safe recut actually survives into the final candidate blueprint",
        rhythm_recut_application_contract_ready(rhythm_recut_application_evidence),
        rhythm_recut_application_evidence,
    )
    transition_polish_evidence = transition_polish_blueprint_evidence(package_dir)
    add_check(
        checks,
        "Transition polish blueprint turns final transitions into BGM-hit, title-safe, motion-proven Resolve metadata",
        transition_polish_blueprint_ready(transition_polish_evidence),
        transition_polish_evidence,
    )
    transition_quality_evidence = transition_quality_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition quality contract proves the final candidate covers every visual boundary without random or repeated effects",
        transition_quality_contract_ready(transition_quality_evidence),
        transition_quality_evidence,
    )
    shot_transition_boundary_evidence = shot_transition_boundary_contract_evidence(package_dir)
    add_check(
        checks,
        "Shot transition boundary contract proves each adjacent from/to pair has matched BGM-hit title-safe transition metadata",
        shot_transition_boundary_contract_ready(shot_transition_boundary_evidence),
        shot_transition_boundary_evidence,
    )
    transition_motivation_evidence = transition_motivation_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition motivation contract proves every transition has route, bridge, motion, title, or BGM reasoning",
        transition_motivation_contract_ready(transition_motivation_evidence),
        transition_motivation_evidence,
    )
    transition_pair_continuity_evidence = transition_pair_continuity_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition pair continuity contract proves every adjacent from/to shot has visual, route, motion, BGM, or title continuity evidence",
        transition_pair_continuity_contract_ready(transition_pair_continuity_evidence),
        transition_pair_continuity_evidence,
    )
    transition_execution_readiness_evidence = transition_execution_readiness_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition execution readiness contract proves every final transition has a package-local Resolve recipe, BGM hit, title-safe window, pair readiness, and handles",
        transition_execution_readiness_contract_ready(transition_execution_readiness_evidence),
        transition_execution_readiness_evidence,
    )
    transition_polish_application_evidence = transition_polish_application_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition polish application contract proves active/final blueprints preserve BGM-hit title-safe transition polish metadata",
        transition_polish_application_contract_ready(transition_polish_application_evidence),
        transition_polish_application_evidence,
    )
    resolve_transition_materialization_evidence = resolve_transition_materialization_contract_evidence(package_dir)
    add_check(
        checks,
        "Resolve transition materialization contract proves transition recipes survive into Resolve marker payload/readback evidence",
        resolve_transition_materialization_contract_ready(resolve_transition_materialization_evidence),
        resolve_transition_materialization_evidence,
    )
    resolve_transition_apply_evidence = resolve_transition_apply_contract_evidence(package_dir)
    add_check(
        checks,
        "Resolve transition apply contract proves visible transitions have an API, manual Resolve, or bridge-clip apply path instead of marker-only metadata",
        resolve_transition_apply_contract_ready(resolve_transition_apply_evidence),
        resolve_transition_apply_evidence,
    )
    transition_cadence_evidence = transition_cadence_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition cadence contract proves the whole film has restrained motivated transitions instead of bare cuts, repeated templates, or effect spam",
        transition_cadence_contract_ready(transition_cadence_evidence),
        transition_cadence_evidence,
    )
    transition_microstructure_evidence = transition_microstructure_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition microstructure contract proves every adjacent shot transition has a BGM landing, title-safe/BGM-only window, handles, pair continuity, bridge beats, and a real apply path",
        transition_microstructure_contract_ready(transition_microstructure_evidence),
        transition_microstructure_evidence,
    )
    transition_scene_arc_evidence = transition_scene_arc_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition scene arc contract proves polished transitions become reference-like outgoing/bridge/BGM/title-safe/landing moments instead of isolated effects",
        transition_scene_arc_contract_ready(transition_scene_arc_evidence),
        transition_scene_arc_evidence,
    )
    transition_effect_palette_evidence = transition_effect_palette_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition effect palette contract proves the whole film balances clean cuts, matches, bridges, dissolves, title reveals, and rare motivated motion instead of effect spam",
        transition_effect_palette_contract_ready(transition_effect_palette_evidence),
        transition_effect_palette_evidence,
    )
    transition_visual_match_evidence = transition_visual_match_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition visual match contract proves every adjacent pair has concrete visual, bridge, motion, mood, title, local, or BGM continuity evidence",
        transition_visual_match_contract_ready(transition_visual_match_evidence),
        transition_visual_match_evidence,
    )
    transition_reference_candidates = transition_reference_candidates_evidence(package_dir)
    add_check(
        checks,
        "Transition reference candidates prove every boundary has non-copying A/B/C candidates with rare motion accents and bridge/breath coverage before Resolve apply",
        transition_reference_candidates_ready(transition_reference_candidates),
        transition_reference_candidates,
    )
    transition_reference_selection = transition_reference_selection_evidence(package_dir)
    add_check(
        checks,
        "Transition reference selection proves unattended drafts auto-select one safe default per boundary while bridge-missing rows stay blocked",
        transition_reference_selection_ready(transition_reference_selection),
        transition_reference_selection,
    )
    transition_choreography_plan = transition_choreography_plan_evidence(package_dir)
    add_check(
        checks,
        "Transition choreography plan proves each boundary has outgoing, bridge-or-motion, landing, BGM-hit, caption-quiet, and repetition-aware direction",
        transition_choreography_plan_ready(transition_choreography_plan),
        transition_choreography_plan,
    )
    transition_choreography_contract = transition_choreography_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition choreography contract proves V14-style motion accents are restrained, source-motivated, title-safe, and not repeated as a template chain",
        transition_choreography_plan_ready(transition_choreography_plan)
        and transition_choreography_contract_ready(transition_choreography_contract),
        {"transitionChoreographyPlan": transition_choreography_plan, "transitionChoreographyContract": transition_choreography_contract},
    )
    transition_motion_direction_evidence = transition_motion_direction_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition motion direction contract proves rotation, whip, push, and speed-ramp effects match source or bridge movement direction instead of random motion",
        transition_choreography_plan_ready(transition_choreography_plan)
        and transition_choreography_contract_ready(transition_choreography_contract)
        and transition_visual_match_contract_ready(transition_visual_match_evidence)
        and transition_effect_palette_contract_ready(transition_effect_palette_evidence)
        and transition_motion_direction_contract_ready(transition_motion_direction_evidence),
        {
            "transitionChoreographyPlan": transition_choreography_plan,
            "transitionChoreographyContract": transition_choreography_contract,
            "transitionVisualMatch": transition_visual_match_evidence,
            "transitionEffectPalette": transition_effect_palette_evidence,
            "transitionMotionDirection": transition_motion_direction_evidence,
        },
    )
    transition_cutpoint_evidence = transition_cutpoint_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition cutpoint contract proves every boundary has an outgoing tail, BGM-hit bridge/effect point, readable landing hold, handles, quiet title/subtitle zone, and BGM-only audio",
        transition_cutpoint_contract_ready(transition_cutpoint_evidence),
        transition_cutpoint_evidence,
    )
    transition_action_anchor_evidence = transition_action_anchor_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition action-anchor contract proves every boundary leaves from readable action, bridges or matches through a motivated connector, and lands on a stable shot",
        transition_action_anchor_contract_ready(transition_action_anchor_evidence),
        transition_action_anchor_evidence,
    )
    transition_sensory_continuity_evidence = transition_sensory_continuity_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition sensory-continuity contract proves every boundary carries visual, BGM, caption, route/mood, motion, and landing continuity cues before preview or audition",
        transition_sensory_continuity_contract_ready(transition_sensory_continuity_evidence),
        transition_sensory_continuity_evidence,
    )
    transition_preview_packet = transition_preview_packet_evidence(package_dir)
    add_check(
        checks,
        "Transition preview packet proves important boundaries have package-local frame evidence before storyboard approval",
        transition_preview_packet_ready(transition_preview_packet),
        transition_preview_packet,
    )
    transition_preview_quality_evidence = transition_preview_quality_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition preview quality contract proves important preview frames are nonblank, decodable, non-identical, and outgoing/landing complete before storyboard approval",
        transition_preview_packet_ready(transition_preview_packet)
        and transition_preview_quality_contract_ready(transition_preview_quality_evidence),
        {"transitionPreviewPacket": transition_preview_packet, "transitionPreviewQuality": transition_preview_quality_evidence},
    )
    transition_audition_packet = transition_audition_packet_evidence(package_dir)
    add_check(
        checks,
        "Transition audition packet proves important transitions are watchable muted local MP4 previews before storyboard or Resolve apply",
        transition_preview_packet_ready(transition_preview_packet)
        and transition_preview_quality_contract_ready(transition_preview_quality_evidence)
        and transition_audition_packet_ready(transition_audition_packet),
        {
            "transitionPreviewPacket": transition_preview_packet,
            "transitionPreviewQuality": transition_preview_quality_evidence,
            "transitionAuditionPacket": transition_audition_packet,
        },
    )
    transition_audition_quality_evidence = transition_audition_quality_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition audition quality contract proves transition audition MP4s are playable, local, long enough, and muted",
        transition_preview_packet_ready(transition_preview_packet)
        and transition_preview_quality_contract_ready(transition_preview_quality_evidence)
        and transition_audition_packet_ready(transition_audition_packet)
        and transition_audition_quality_contract_ready(transition_audition_quality_evidence),
        {
            "transitionAuditionPacket": transition_audition_packet,
            "transitionAuditionQuality": transition_audition_quality_evidence,
        },
    )
    transition_audition_visual_proof_evidence = transition_audition_visual_proof_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition audition visual proof contract proves audition MP4s have extracted nonblank frames, distinct endpoints, and middle-motion visual change",
        transition_preview_packet_ready(transition_preview_packet)
        and transition_preview_quality_contract_ready(transition_preview_quality_evidence)
        and transition_audition_packet_ready(transition_audition_packet)
        and transition_audition_quality_contract_ready(transition_audition_quality_evidence)
        and transition_audition_visual_proof_contract_ready(transition_audition_visual_proof_evidence),
        {
            "transitionAuditionPacket": transition_audition_packet,
            "transitionAuditionQuality": transition_audition_quality_evidence,
            "transitionAuditionVisualProof": transition_audition_visual_proof_evidence,
        },
    )
    transition_audition_role_integrity_evidence = transition_audition_role_integrity_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition audition role integrity contract proves audition MP4s are built from ordered outgoing/bridge/landing segments, not arbitrary moving clips",
        transition_preview_packet_ready(transition_preview_packet)
        and transition_preview_quality_contract_ready(transition_preview_quality_evidence)
        and transition_audition_packet_ready(transition_audition_packet)
        and transition_audition_quality_contract_ready(transition_audition_quality_evidence)
        and transition_audition_visual_proof_contract_ready(transition_audition_visual_proof_evidence)
        and transition_audition_role_integrity_contract_ready(transition_audition_role_integrity_evidence),
        {
            "transitionAuditionPacket": transition_audition_packet,
            "transitionAuditionQuality": transition_audition_quality_evidence,
            "transitionAuditionVisualProof": transition_audition_visual_proof_evidence,
            "transitionAuditionRoleIntegrity": transition_audition_role_integrity_evidence,
        },
    )
    transition_storyboard_evidence = transition_storyboard_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition storyboard contract proves important transitions have viewer purpose, outgoing/bridge/landing proof, and preview evidence",
        transition_preview_packet_ready(transition_preview_packet)
        and transition_preview_quality_contract_ready(transition_preview_quality_evidence)
        and transition_audition_packet_ready(transition_audition_packet)
        and transition_audition_quality_contract_ready(transition_audition_quality_evidence)
        and transition_audition_visual_proof_contract_ready(transition_audition_visual_proof_evidence)
        and transition_audition_role_integrity_contract_ready(transition_audition_role_integrity_evidence)
        and transition_storyboard_contract_ready(transition_storyboard_evidence),
        {
            "transitionPreviewPacket": transition_preview_packet,
            "transitionPreviewQuality": transition_preview_quality_evidence,
            "transitionAuditionPacket": transition_audition_packet,
            "transitionAuditionQuality": transition_audition_quality_evidence,
            "transitionAuditionVisualProof": transition_audition_visual_proof_evidence,
            "transitionAuditionRoleIntegrity": transition_audition_role_integrity_evidence,
            "transitionStoryboard": transition_storyboard_evidence,
        },
    )
    reference_scene_grammar_evidence = reference_scene_grammar_contract_evidence(package_dir)
    add_check(
        checks,
        "Reference scene grammar contract proves opening, chapters, transitions, and ending use Parallel World/Malta scene functions",
        reference_scene_grammar_contract_ready(reference_scene_grammar_evidence),
        reference_scene_grammar_evidence,
    )
    chapter_story_spine_evidence = chapter_story_spine_contract_evidence(package_dir)
    add_check(
        checks,
        "Chapter story spine contract proves every chapter executes context, movement, lived-in texture, payoff, and aftertaste through final candidate evidence",
        chapter_story_spine_contract_ready(chapter_story_spine_evidence),
        chapter_story_spine_evidence,
    )
    shot_flow_continuity_evidence = shot_flow_continuity_contract_evidence(package_dir)
    add_check(
        checks,
        "Shot flow continuity contract proves each chapter orders final shots into readable travel-film progression",
        shot_flow_continuity_contract_ready(shot_flow_continuity_evidence),
        shot_flow_continuity_evidence,
    )
    transition_breathing_room_evidence = transition_breathing_room_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition breathing-room contract proves motion accents are rare and every important transition lands cleanly",
        transition_breathing_room_contract_ready(transition_breathing_room_evidence),
        transition_breathing_room_evidence,
    )
    scene_flow_arc_evidence = scene_flow_arc_contract_evidence(package_dir)
    add_check(
        checks,
        "Scene flow arc contract proves chapters read as travel-film sequences instead of landmark stacks or effect-hidden jumps",
        scene_flow_arc_contract_ready(scene_flow_arc_evidence),
        scene_flow_arc_evidence,
    )
    final_cut_smoothness_evidence = final_cut_smoothness_contract_evidence(package_dir)
    add_check(
        checks,
        "Final cut smoothness contract proves adjacent shots land cleanly instead of rough hard joins or effect-hidden jumps",
        final_cut_smoothness_contract_ready(final_cut_smoothness_evidence),
        final_cut_smoothness_evidence,
    )
    pacing_watchability_evidence = pacing_watchability_contract_evidence(package_dir)
    add_check(
        checks,
        "Pacing watchability contract proves reference-calibrated final shot lengths, chapter breath, long-hold reduction, and short-clip readability",
        pacing_watchability_contract_ready(pacing_watchability_evidence),
        pacing_watchability_evidence,
    )
    narrative_adjacency_evidence = narrative_adjacency_contract_evidence(package_dir)
    add_check(
        checks,
        "Narrative adjacency contract proves adjacent visual shots are story-motivated instead of random stacks",
        narrative_adjacency_contract_ready(narrative_adjacency_evidence),
        narrative_adjacency_evidence,
    )
    transition_viewer_orientation_evidence = transition_viewer_orientation_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition viewer orientation contract proves important route/day/title/ending jumps keep viewers oriented after the cut",
        transition_viewer_orientation_contract_ready(transition_viewer_orientation_evidence),
        transition_viewer_orientation_evidence,
    )
    transition_scene_settlement_evidence = transition_scene_settlement_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition scene settlement contract proves important route/day/title/ending jumps land into readable local scenes",
        transition_scene_settlement_contract_ready(transition_scene_settlement_evidence),
        transition_scene_settlement_evidence,
    )
    transition_continuity_rehearsal_evidence = transition_continuity_rehearsal_contract_evidence(package_dir)
    add_check(
        checks,
        "Transition continuity rehearsal contract proves approved transition rows connect as one watchable sequence",
        transition_storyboard_contract_ready(transition_storyboard_evidence)
        and transition_breathing_room_contract_ready(transition_breathing_room_evidence)
        and scene_flow_arc_contract_ready(scene_flow_arc_evidence)
        and final_cut_smoothness_contract_ready(final_cut_smoothness_evidence)
        and pacing_watchability_contract_ready(pacing_watchability_evidence)
        and narrative_adjacency_contract_ready(narrative_adjacency_evidence)
        and transition_viewer_orientation_contract_ready(transition_viewer_orientation_evidence)
        and transition_scene_settlement_contract_ready(transition_scene_settlement_evidence)
        and transition_continuity_rehearsal_contract_ready(transition_continuity_rehearsal_evidence),
        {
            "transitionStoryboard": transition_storyboard_evidence,
            "transitionBreathingRoom": transition_breathing_room_evidence,
            "sceneFlowArc": scene_flow_arc_evidence,
            "finalCutSmoothness": final_cut_smoothness_evidence,
            "pacingWatchability": pacing_watchability_evidence,
            "narrativeAdjacency": narrative_adjacency_evidence,
            "transitionViewerOrientation": transition_viewer_orientation_evidence,
            "transitionSceneSettlement": transition_scene_settlement_evidence,
            "transitionContinuityRehearsal": transition_continuity_rehearsal_evidence,
        },
    )
    timeline_variety_evidence = timeline_variety_contract_evidence(package_dir)
    add_check(
        checks,
        "Timeline variety contract proves the final film varies movement, texture, payoff, and aftertaste instead of hiding weak shot choice behind transitions",
        timeline_variety_contract_ready(timeline_variety_evidence),
        timeline_variety_evidence,
    )
    unattended_first_draft_evidence = unattended_first_draft_contract_evidence(package_dir)
    add_check(
        checks,
        "Unattended first-draft contract proves raw intake, story, BGM, captions, titles, rhythm, transitions, repair closure, and blueprint preflight are connected",
        unattended_first_draft_contract_ready(unattended_first_draft_evidence),
        unattended_first_draft_evidence,
    )
    unattended_repair_queue = unattended_repair_queue_evidence(package_dir)
    add_check(
        checks,
        "Unattended repair queue proves a mature package has no remaining routed P0/P1 repairs",
        unattended_repair_queue_ready(unattended_repair_queue),
        unattended_repair_queue,
    )
    rhythm_recut_apply_evidence = rhythm_recut_apply_package_evidence(package_dir)
    add_check(
        checks,
        "Rhythm recut apply package safely turns the candidate blueprint into a Resolve-ready package fork",
        rhythm_recut_apply_package_ready(rhythm_recut_apply_evidence),
        rhythm_recut_apply_evidence,
    )

    render = load_json(package_dir / "render_delivery_verification.json") or {}
    video = render.get("video") if isinstance(render.get("video"), dict) else {}
    add_check(
        checks,
        "Final render is 4K, high-frame-rate, high-bitrate, and verified",
        render.get("status") == "passed"
        and int(video.get("width") or 0) >= 3840
        and int(video.get("height") or 0) >= 2160
        and float(video.get("frameRateValue") or 0) >= args.min_fps
        and float(video.get("bitrateMbps") or 0) >= args.min_video_bitrate_mbps,
        {"renderStatus": render.get("status"), "video": video},
    )

    feedback = load_json(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json") or {}
    feedback_point_labels = feedback_labels(feedback)
    add_check(
        checks,
        "Feedback regression gate covers opening title and 7:04 vertical/BGM/voice complaints",
        feedback.get("status") == "passed"
        and "opening_title" in feedback_point_labels
        and any("seven_minute" in label or "7" in label for label in feedback_point_labels)
        and any_passed(feedback, "no portrait/pillarbox")
        and any_passed(feedback, "BGM-only mix"),
        {"status": feedback.get("status"), "feedbackLabels": feedback_point_labels},
    )

    story = load_json(package_dir / "story_style_contract_audit.json") or {}
    opening_rows = checks_with_text(story, "Opening has one clean")
    opening_evidence = opening_rows[0].get("evidence") if opening_rows else {}
    add_check(
        checks,
        "Story audit rejects duplicate or stacked opening titles",
        story.get("status") == "passed"
        and bool(opening_evidence)
        and opening_evidence.get("openingTitleCount") == 1
        and bool(str(opening_evidence.get("openingTitleText") or "").strip())
        and not opening_evidence.get("repeatedTitleValues")
        and not opening_evidence.get("mismatchedFieldValues")
        and not opening_evidence.get("openingSubtitleValues"),
        {"storyStatus": story.get("status"), "openingEvidence": opening_evidence},
    )

    title = load_json(package_dir / "title_bridge_contract_audit.json") or {}
    add_check(
        checks,
        "Title bridge contract proves clean scenic title media on the Resolve timeline",
        title.get("status") == "passed" and not title.get("blockers"),
        {"status": title.get("status"), "segmentCount": title.get("segmentCount"), "titleClipCount": title.get("titleClipCount")},
    )

    bgm = load_json(package_dir / "bgm_audio_contract_audit.json") or {}
    add_check(
        checks,
        "BGM-only contract proves audible BGM and no source/voiceover leakage",
        bgm.get("status") == "passed"
        and any_passed(bgm, "Voiceover and source-camera audio are disabled")
        and any_passed(bgm, "DaVinci readback has A3 BGM")
        and any_passed(bgm, "Rendered BGM is audible"),
        {"status": bgm.get("status"), "blockers": bgm.get("blockers"), "warnings": bgm.get("warnings")},
    )

    client = load_json(package_dir / "client_delivery_rules_audit.json") or {}
    recognition_rows = checks_with_text(client, "Full-folder recognition report")
    recognition_evidence = recognition_rows[0].get("evidence") if recognition_rows else {}
    add_check(
        checks,
        "Full-folder recognition and route evidence exist before editing claims",
        client.get("status") == "passed"
        and bool(recognition_evidence)
        and (recognition_evidence.get("summary") or {}).get("recognitionCoverageRatio", 0) >= 0.98
        and (recognition_evidence.get("summary") or {}).get("confirmedRouteChapterCount", 0) >= 2,
        {"clientStatus": client.get("status"), "recognitionEvidence": recognition_evidence},
    )
    orientation_rows = checks_with_text(client, "raw portrait/square/unknown")
    orientation_evidence = orientation_rows[0].get("evidence") if orientation_rows else {}
    add_check(
        checks,
        "Client audit proves actual Resolve blueprint source paths contain no raw portrait/square/unknown clips",
        client.get("status") == "passed"
        and bool(orientation_evidence)
        and orientation_rows[0].get("status") == "passed"
        and int(orientation_evidence.get("checkedVideoClipCount") or 0) > 0
        and int(orientation_evidence.get("blockedNonLandscapeCount") or 0) == 0
        and not orientation_evidence.get("probeErrors"),
        {"clientStatus": client.get("status"), "orientationEvidence": orientation_evidence},
    )

    location_truth = load_json(package_dir / "location_truth_contract_audit.json") or {}
    location_summary = location_truth.get("summary") if isinstance(location_truth.get("summary"), dict) else {}
    claim_contract = location_truth.get("claimContract") if isinstance(location_truth.get("claimContract"), dict) else {}
    exact_allowed = bool(location_summary.get("exactPerVideoLocationClaimAllowed"))
    route_allowed = bool(location_summary.get("routeAwareEditClaimAllowed"))
    required_language = str(claim_contract.get("requiredLanguage") or "")
    honest_non_exact = (
        route_allowed
        and not exact_allowed
        and location_truth.get("status") == "passed_with_caveats"
        and "Do not claim" in required_language
        and ("GPS" in required_language or "per-clip" in required_language)
    )
    add_check(
        checks,
        "Location truth contract separates route-ready visual reconstruction from exact per-video geolocation",
        location_truth.get("status") in {"passed", "passed_with_caveats"}
        and (exact_allowed or honest_non_exact)
        and float(location_summary.get("recognitionCoverageRatio") or 0) >= 0.98
        and int(location_summary.get("expectedActiveSourceCount") or 0) > 0,
        {
            "status": location_truth.get("status"),
            "summary": location_summary,
            "claimContract": claim_contract,
            "caveats": location_truth.get("caveats"),
        },
    )

    route_texture = load_json(package_dir / "route_texture_contract_audit.json") or {}
    route_summary = route_texture.get("summary") if isinstance(route_texture.get("summary"), dict) else {}
    add_check(
        checks,
        "Route texture proves transitions, street life, lived-in detail, and landmarks",
        route_texture.get("status") == "passed"
        and route_summary.get("matchedTransitions", 0) >= 1
        and route_summary.get("passedChapters") == route_summary.get("chapterWindowCount")
        and all((route_summary.get("categoryCounts") or {}).get(key, 0) > 0 for key in ("transport", "street", "livedIn", "landmark")),
        {"status": route_texture.get("status"), "summary": route_summary},
    )

    director_intent = load_json(package_dir / "director_intent_contract_audit.json") or {}
    intent_summary = director_intent.get("summary") if isinstance(director_intent.get("summary"), dict) else {}
    intent_manifest = director_intent.get("directorIntentManifest") if isinstance(director_intent.get("directorIntentManifest"), dict) else {}
    add_check(
        checks,
        "Director intent contract proves opening, chapter arc, pacing, captions, and ending aftertaste",
        director_intent.get("status") in {"passed", "passed_with_warnings"}
        and int(intent_summary.get("chapterCount") or 0) >= 5
        and int(intent_summary.get("subtitleCueCount") or 0) >= 80
        and float(intent_summary.get("cuesPerMinute") or 0) >= 3.0
        and 8.0 <= float(intent_summary.get("medianMainClipSeconds") or 0) <= 45.0
        and bool((intent_manifest.get("openingIntent") or {}).get("missionTermsFound"))
        and bool((intent_manifest.get("endingIntent") or {}).get("endingTermsFound")),
        {"status": director_intent.get("status"), "summary": intent_summary, "manifest": intent_manifest},
    )

    stock = load_json(package_dir / "stock_aerial_closure_audit.json") or {}
    stock_summary = stock.get("summary") if isinstance(stock.get("summary"), dict) else {}
    add_check(
        checks,
        "Aerial/stock placeholders are materialized or explicitly closed",
        stock.get("status") == "passed"
        and stock_summary.get("unresolvedPlaceholderCount") == 0
        and stock_summary.get("verifiedAerialCount", 0) >= 1,
        {"status": stock.get("status"), "summary": stock_summary},
    )

    director = load_json(package_dir / "director_polish_contract_audit.json") or {}
    add_check(
        checks,
        "Director polish chain passes without hidden warnings",
        director.get("status") == "passed" and not director.get("warnings") and not director.get("blockers"),
        {"status": director.get("status"), "summary": director.get("summary"), "warnings": director.get("warnings")},
    )

    integrity = load_json(package_dir / "package_integrity_audit_strict_portable.json") or {}
    integrity_summary = integrity.get("summary") if isinstance(integrity.get("summary"), dict) else {}
    add_check(
        checks,
        "Strict portable handoff has no active cross-package dependencies",
        integrity.get("status") == "passed"
        and not integrity.get("warnings")
        and not integrity.get("blockers")
        and integrity_summary.get("activeCoreCrossPackagePathCount", 0) == 0,
        {"status": integrity.get("status"), "summary": integrity_summary, "closed": integrity.get("closedCoreCrossPackagePaths")},
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings = [row["name"] for row in checks if row["status"] == "warning"]
    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "skillDir": str(skill_dir),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "passed": len([row for row in checks if row["status"] == "passed"]),
            "blocked": len(blockers),
            "warnings": len(warnings),
            "total": len(checks),
        },
        "contract": {
            "purpose": "Confirm the reusable Skill, not only the current film, covers the user's repeated delivery failures.",
            "notCompletionProof": "Passing this contract is one-package evidence. It does not prove the whole long-term goal is complete without additional forward tests on other trips.",
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Skill Maturity Contract Audit",
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
        evidence = json.dumps(row["evidence"], ensure_ascii=False)[:2200]
        lines.extend(["", f"### {row['name']}", f"- Status: `{row['status']}`", f"- Evidence: `{evidence}`"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Contract", "", "```json", json.dumps(report["contract"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit unattended Skill maturity against user regression lessons.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--skill-dir")
    parser.add_argument("--min-fps", type=float, default=50.0)
    parser.add_argument("--min-video-bitrate-mbps", type=float, default=60.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve() if args.skill_dir else skill_dir_from_script()
    report = build_report(package_dir, skill_dir, args)
    write_json(package_dir / "skill_maturity_contract_audit.json", report)
    write_markdown(package_dir / "skill_maturity_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "warnings": report["warnings"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
