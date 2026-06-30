#!/usr/bin/env python3
"""Audit whether a package is ready for an unattended first-draft handoff."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


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


def add_gate(
    gates: list[dict[str, Any]],
    name: str,
    passed: bool,
    evidence: dict[str, Any],
    *,
    required: bool = True,
) -> None:
    gates.append(
        {
            "name": name,
            "status": "passed" if passed else ("blocked" if required else "warning"),
            "required": required,
            "evidence": evidence,
        }
    )


def status_in(data: Any, accepted: set[str]) -> bool:
    return isinstance(data, dict) and data.get("status") in accepted


def bool_field(data: dict[str, Any], key: str) -> bool:
    return data.get(key) is True


def resolve_inside_package(package_dir: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path


def video_clip_count(blueprint: dict[str, Any]) -> int:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").lower()
        track_type = str(row.get("trackType") or "video").lower()
        source = str(row.get("sourcePath") or "").lower()
        if "subtitle" in role or source.endswith((".srt", ".ass", ".vtt")):
            continue
        if track_type in {"", "video"} and as_int(row.get("mediaType"), 1) == 1:
            count += 1
    return count


def build_report(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    gates: list[dict[str, Any]] = []

    raw_intake = load_json(package_dir / "raw_intake_completeness_audit.json") or {}
    raw_summary = summary_of(raw_intake)
    add_gate(
        gates,
        "Full raw intake is accounted before first assembly",
        raw_intake.get("status") == "passed"
        and as_int(raw_summary.get("activeSourceVideoCount")) > 0
        and as_float(raw_summary.get("recognitionCoverageRatio")) >= 1.0
        and as_int(raw_summary.get("routeMissingVideoCount")) == 0
        and as_int(raw_summary.get("routeDuplicateVideoCount")) == 0
        and as_int(raw_summary.get("footageSelectMissingVideoCount")) == 0
        and as_int(raw_summary.get("activeDerivedVideoCount")) == 0
        and as_int(raw_summary.get("staleArtifactCount")) == 0,
        {
            "status": raw_intake.get("status"),
            "activeSourceVideoCount": raw_summary.get("activeSourceVideoCount"),
            "recognitionCoverageRatio": raw_summary.get("recognitionCoverageRatio"),
            "routeMissingVideoCount": raw_summary.get("routeMissingVideoCount"),
            "routeDuplicateVideoCount": raw_summary.get("routeDuplicateVideoCount"),
            "footageSelectMissingVideoCount": raw_summary.get("footageSelectMissingVideoCount"),
            "activeDerivedVideoCount": raw_summary.get("activeDerivedVideoCount"),
            "staleArtifactCount": raw_summary.get("staleArtifactCount"),
            "blockers": raw_intake.get("blockers") or [],
        },
    )

    footage_select = load_json(package_dir / "footage_select_plan" / "footage_select_plan.json") or {}
    footage_summary = summary_of(footage_select)
    add_gate(
        gates,
        "Footage select has scored the source pool before the cut",
        footage_select.get("status")
        in {"ready_with_footage_select_plan", "ready_with_blueprint_fallback_footage_select_plan"}
        and as_int(footage_summary.get("sourceVideoCount")) > 0
        and as_int(footage_summary.get("candidateVideoCount")) > 0
        and as_int(footage_summary.get("chapterRowCount")) >= 1
        and as_int(footage_summary.get("chaptersNeedingCoverage")) == 0,
        {
            "status": footage_select.get("status"),
            "sourceVideoCount": footage_summary.get("sourceVideoCount"),
            "candidateVideoCount": footage_summary.get("candidateVideoCount"),
            "chapterRowCount": footage_summary.get("chapterRowCount"),
            "chaptersNeedingCoverage": footage_summary.get("chaptersNeedingCoverage"),
            "heroCandidateCount": footage_summary.get("heroCandidateCount"),
            "textureBridgeCandidateCount": footage_summary.get("textureBridgeCandidateCount"),
        },
    )

    source_repair = load_json(package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json") or {}
    source_repair_summary = summary_of(source_repair)
    add_gate(
        gates,
        "Source selection coverage has no blocking chapter repair rows before first assembly",
        source_repair.get("status") == "ready_no_source_selection_repairs_needed"
        and as_int(source_repair_summary.get("blockingRepairRowCount")) == 0
        and as_int(source_repair_summary.get("chapterRowCount")) >= 1
        and as_int(source_repair_summary.get("readyChapterCount")) == as_int(source_repair_summary.get("chapterRowCount"))
        and as_int(source_repair_summary.get("heroCandidateCount")) >= 1
        and as_int(source_repair_summary.get("movementBridgeCandidateCount")) >= max(1, as_int(source_repair_summary.get("chapterRowCount")) - 1)
        and as_int(source_repair_summary.get("livedInTextureCandidateCount")) >= 1
        and as_int(source_repair_summary.get("destinationPayoffCandidateCount")) >= 1,
        {
            "status": source_repair.get("status"),
            "chapterRowCount": source_repair_summary.get("chapterRowCount"),
            "readyChapterCount": source_repair_summary.get("readyChapterCount"),
            "blockingRepairRowCount": source_repair_summary.get("blockingRepairRowCount"),
            "warningRepairRowCount": source_repair_summary.get("warningRepairRowCount"),
            "heroCandidateCount": source_repair_summary.get("heroCandidateCount"),
            "movementBridgeCandidateCount": source_repair_summary.get("movementBridgeCandidateCount"),
            "livedInTextureCandidateCount": source_repair_summary.get("livedInTextureCandidateCount"),
            "destinationPayoffCandidateCount": source_repair_summary.get("destinationPayoffCandidateCount"),
        },
    )

    first_assembly_order = load_json(package_dir / "first_assembly_source_order_contract_audit.json") or {}
    first_assembly_summary = summary_of(first_assembly_order)
    add_gate(
        gates,
        "First assembly source order proves the cut used full-source selection instead of filename order",
        first_assembly_order.get("status") == "passed"
        and as_int(first_assembly_summary.get("blockedCheckCount")) == 0
        and as_int(first_assembly_summary.get("deliveryChapterCount")) >= 1
        and as_int(first_assembly_summary.get("sortedChapterCount")) >= as_int(first_assembly_summary.get("deliveryChapterCount"))
        and as_int(first_assembly_summary.get("candidateRowsUsed")) >= min(
            max(3, as_int(first_assembly_summary.get("deliveryChapterCount"))),
            as_int(first_assembly_summary.get("candidateVideoCount")),
        )
        and as_int(first_assembly_summary.get("riskyTopSelectionRowCount")) == 0
        and as_int(first_assembly_summary.get("missingTopSelectionDataCount")) == 0
        and (not first_assembly_summary.get("largeSource") or first_assembly_summary.get("footageSelectInputSource") == "media_index"),
        {
            "status": first_assembly_order.get("status"),
            "activeSourceVideoCount": first_assembly_summary.get("activeSourceVideoCount"),
            "largeSource": first_assembly_summary.get("largeSource"),
            "footageSelectInputSource": first_assembly_summary.get("footageSelectInputSource"),
            "candidateVideoCount": first_assembly_summary.get("candidateVideoCount"),
            "candidateRowsUsed": first_assembly_summary.get("candidateRowsUsed"),
            "deliveryChapterCount": first_assembly_summary.get("deliveryChapterCount"),
            "sortedChapterCount": first_assembly_summary.get("sortedChapterCount"),
            "riskyTopSelectionRowCount": first_assembly_summary.get("riskyTopSelectionRowCount"),
            "missingTopSelectionDataCount": first_assembly_summary.get("missingTopSelectionDataCount"),
            "blockers": first_assembly_order.get("blockers") or [],
        },
    )

    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    coverage = blueprint.get("longFormCoverage") if isinstance(blueprint.get("longFormCoverage"), dict) else {}
    clip_count = video_clip_count(blueprint)
    add_gate(
        gates,
        "Resolve blueprint has a real first assembly",
        clip_count > 0 and (as_float(coverage.get("finalVideoCoverageSeconds")) > 0 or bool(blueprint.get("clips"))),
        {
            "clipCount": clip_count,
            "targetDurationSeconds": coverage.get("targetDurationSeconds"),
            "finalVideoCoverageSeconds": coverage.get("finalVideoCoverageSeconds"),
        },
    )

    opening = load_json(package_dir / "opening_story_plan" / "opening_story_plan.json") or {}
    opening_summary = summary_of(opening)
    opening_rows = as_int(opening_summary.get("beatRowCount"))
    add_gate(
        gates,
        "Opening story has viewer promise, destination proof, title, arrival, texture, and handoff",
        opening.get("status") == "ready_with_opening_story_plan"
        and opening_rows >= 6
        and as_int(opening_summary.get("rowsWithEvidence")) == opening_rows
        and as_int(opening_summary.get("missingBeatCount")) == 0
        and as_int(opening_summary.get("destinationProofClipCount")) >= 1
        and as_int(opening_summary.get("routeArrivalClipCount")) >= 1
        and as_int(opening_summary.get("livedInTextureClipCount")) >= 1
        and as_int(opening_summary.get("titleClipCount")) >= 1
        and as_int(opening_summary.get("firstHandoffClipCount")) >= 1,
        {
            "status": opening.get("status"),
            "beatRowCount": opening_summary.get("beatRowCount"),
            "rowsWithEvidence": opening_summary.get("rowsWithEvidence"),
            "missingBeatCount": opening_summary.get("missingBeatCount"),
            "destinationProofClipCount": opening_summary.get("destinationProofClipCount"),
            "routeArrivalClipCount": opening_summary.get("routeArrivalClipCount"),
            "livedInTextureClipCount": opening_summary.get("livedInTextureClipCount"),
            "titleClipCount": opening_summary.get("titleClipCount"),
            "firstHandoffClipCount": opening_summary.get("firstHandoffClipCount"),
        },
    )

    chapter_arc = load_json(package_dir / "chapter_arc_plan" / "chapter_arc_plan.json") or {}
    chapter_summary = summary_of(chapter_arc)
    chapter_rows = as_int(chapter_summary.get("chapterRowCount"))
    add_gate(
        gates,
        "Chapter arcs are planned before rhythm, transitions, and Resolve trust",
        chapter_arc.get("status") == "ready_with_chapter_arc_plan"
        and chapter_rows >= 1
        and as_int(chapter_summary.get("rowsWithDecisionFields")) == chapter_rows
        and as_int(chapter_summary.get("blueprintVideoClipCount")) >= 1
        and as_int(chapter_summary.get("chaptersMissingRequiredBeatCount"))
        <= as_int(chapter_summary.get("p0RepairRowCount")),
        {
            "status": chapter_arc.get("status"),
            "chapterRowCount": chapter_summary.get("chapterRowCount"),
            "rowsWithDecisionFields": chapter_summary.get("rowsWithDecisionFields"),
            "blueprintVideoClipCount": chapter_summary.get("blueprintVideoClipCount"),
            "chaptersMissingRequiredBeatCount": chapter_summary.get("chaptersMissingRequiredBeatCount"),
            "p0RepairRowCount": chapter_summary.get("p0RepairRowCount"),
        },
    )

    title_plan = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    title_summary = summary_of(title_plan)
    cover_title = load_json(package_dir / "cover_title_contract_audit.json") or {}
    cover_summary = summary_of(cover_title)
    title_visual_proof = load_json(package_dir / "title_visual_proof_contract_audit.json") or {}
    title_visual_summary = summary_of(title_visual_proof)
    add_gate(
        gates,
        "Title and cover contract are clean before viewer-facing delivery",
        title_plan.get("status") == "ready_with_clean_title_typography_plan"
        and as_int(title_summary.get("titleRowCount")) >= 1
        and as_int(title_summary.get("cleanRowCount")) == as_int(title_summary.get("titleRowCount"))
        and cover_title.get("status") == "passed"
        and bool_field(cover_summary, "backgroundVideoReady")
        and bool_field(cover_summary, "clean16x9Deliverable")
        and as_int(cover_summary.get("forbiddenHitCount")) == 0
        and not cover_title.get("blockers"),
        {
            "titleStatus": title_plan.get("status"),
            "titleRowCount": title_summary.get("titleRowCount"),
            "cleanRowCount": title_summary.get("cleanRowCount"),
            "coverStatus": cover_title.get("status"),
            "mainTitle": cover_summary.get("mainTitle"),
            "backgroundVideoReady": cover_summary.get("backgroundVideoReady"),
            "clean16x9Deliverable": cover_summary.get("clean16x9Deliverable"),
            "forbiddenHitCount": cover_summary.get("forbiddenHitCount"),
        },
    )
    title_visual_row_count = as_int(title_visual_summary.get("titleVisualRowCount"))
    add_gate(
        gates,
        "Title visual proof has local probe/frame evidence before first-draft trust",
        title_visual_proof.get("status") == "passed"
        and title_visual_row_count >= 3
        and as_int(title_visual_summary.get("passedTitleVisualRowCount")) == title_visual_row_count
        and as_int(title_visual_summary.get("blockedTitleVisualRowCount")) == 0
        and as_int(title_visual_summary.get("openingRowCount")) == 1
        and as_int(title_visual_summary.get("chapterRowCount")) >= 1
        and as_int(title_visual_summary.get("endingRowCount")) >= 1
        and as_int(title_visual_summary.get("rowsWithPackageLocalVideo")) == title_visual_row_count
        and as_int(title_visual_summary.get("rowsWithProbeVideo")) == title_visual_row_count
        and as_int(title_visual_summary.get("rowsWithThreePassedFrames")) == title_visual_row_count
        and as_int(title_visual_summary.get("openingForbiddenHitCount")) == 0
        and title_visual_summary.get("titleBridgeStatus") == "passed"
        and title_visual_summary.get("coverTitleStatus") == "passed"
        and not title_visual_proof.get("blockers"),
        {
            "titleVisualProofStatus": title_visual_proof.get("status"),
            "titleVisualSummary": title_visual_summary,
            "blockers": title_visual_proof.get("blockers"),
        },
    )

    caption = load_json(package_dir / "caption_story_plan" / "caption_story_plan.json") or {}
    caption_summary = summary_of(caption)
    text_export = resolve_inside_package(package_dir, caption_summary.get("textOnlyNarrationExport"))
    audience = load_json(package_dir / "audience_caption_contract_audit.json") or {}
    add_gate(
        gates,
        "Captions and TXT narration are dense and audience-facing",
        caption.get("status") == "ready_with_dense_caption_plan"
        and as_float(caption_summary.get("cuesPerMinute")) >= 3.0
        and as_int(caption_summary.get("subtitleCueCount")) >= 1
        and bool(text_export and text_export.exists())
        and audience.get("status") == "passed"
        and as_int(audience.get("checkedFileCount")) >= 1
        and as_int(audience.get("violationCount")) == 0,
        {
            "captionStatus": caption.get("status"),
            "subtitleCueCount": caption_summary.get("subtitleCueCount"),
            "cuesPerMinute": caption_summary.get("cuesPerMinute"),
            "textOnlyNarrationExport": str(text_export) if text_export else None,
            "textOnlyNarrationExportExists": bool(text_export and text_export.exists()),
            "audienceStatus": audience.get("status"),
            "checkedFileCount": audience.get("checkedFileCount"),
            "violationCount": audience.get("violationCount"),
        },
    )

    bgm_selection = load_json(package_dir / "bgm_selection_package" / "bgm_selection_package.json") or {}
    bgm_summary = summary_of(bgm_selection)
    add_gate(
        gates,
        "BGM selection is materialized, traceable, buildable, and blueprint-referenced",
        bgm_selection.get("status") == "ready_with_materialized_bgm_selection_package"
        and as_int(bgm_summary.get("candidateCount")) >= 1
        and (
            as_int(bgm_summary.get("verifiedMaterializedBedCount")) >= 1
            or as_int(bgm_summary.get("readySourceTrackCount")) >= 1
        )
        and bool_field(bgm_summary, "buildCommandAvailable")
        and as_int(bgm_summary.get("blueprintBgmAssetCount")) >= 1,
        {
            "status": bgm_selection.get("status"),
            "candidateCount": bgm_summary.get("candidateCount"),
            "verifiedMaterializedBedCount": bgm_summary.get("verifiedMaterializedBedCount"),
            "readySourceTrackCount": bgm_summary.get("readySourceTrackCount"),
            "blueprintBgmAssetCount": bgm_summary.get("blueprintBgmAssetCount"),
            "buildCommandAvailable": bgm_summary.get("buildCommandAvailable"),
        },
    )

    audio_policy = load_json(package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json") or {}
    audio_summary = summary_of(audio_policy)
    add_gate(
        gates,
        "Opening, scenic, title, and transition windows are BGM-only",
        audio_policy.get("status") == "ready_with_bgm_only_scene_policy"
        and audio_summary.get("policyMode") == "bgm_only_no_camera_voice"
        and bool_field(audio_summary, "voiceoverDisabled")
        and bool_field(audio_summary, "sourceAudioDisabled")
        and as_int(audio_summary.get("sourceAudioRiskCount")) == 0
        and as_int(audio_summary.get("bgmCoveredWindowCount")) >= 1,
        {
            "status": audio_policy.get("status"),
            "policyMode": audio_summary.get("policyMode"),
            "voiceoverDisabled": audio_summary.get("voiceoverDisabled"),
            "sourceAudioDisabled": audio_summary.get("sourceAudioDisabled"),
            "sourceAudioRiskCount": audio_summary.get("sourceAudioRiskCount"),
            "bgmCoveredWindowCount": audio_summary.get("bgmCoveredWindowCount"),
        },
    )

    visual = load_json(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json") or {}
    visual_summary = summary_of(visual)
    effect = load_json(package_dir / "effect_motion_plan" / "effect_motion_plan.json") or {}
    effect_summary = summary_of(effect)
    add_gate(
        gates,
        "Scenic establishing and restrained motion planning exist before polish",
        visual.get("status") == "ready_with_establishing_evidence"
        and as_int(visual_summary.get("establishingRowCount")) >= 1
        and as_int(visual_summary.get("missingEstablishingCount")) == 0
        and as_int(visual_summary.get("rowsWithEvidence")) == as_int(visual_summary.get("establishingRowCount"))
        and effect.get("status") in {"ready_with_restrained_effect_plan", "ready_with_effect_motion_plan"}
        and as_int(effect_summary.get("effectRowCount")) >= 1
        and as_int(effect_summary.get("forbiddenEffectHitCount")) == 0,
        {
            "visualStatus": visual.get("status"),
            "establishingRowCount": visual_summary.get("establishingRowCount"),
            "rowsWithEvidence": visual_summary.get("rowsWithEvidence"),
            "missingEstablishingCount": visual_summary.get("missingEstablishingCount"),
            "effectStatus": effect.get("status"),
            "effectRowCount": effect_summary.get("effectRowCount"),
            "forbiddenEffectHitCount": effect_summary.get("forbiddenEffectHitCount"),
        },
    )

    rhythm = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
    rhythm_summary = summary_of(rhythm)
    creator = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    creator_summary = summary_of(creator)
    creator_application = load_json(package_dir / "creator_cut_application_contract_audit.json") or {}
    creator_application_summary = summary_of(creator_application)
    final_source_usage = load_json(package_dir / "final_source_usage_contract_audit.json") or {}
    final_source_usage_summary = summary_of(final_source_usage)
    add_gate(
        gates,
        "Rhythm, creator-cut, and final source usage prove the final candidate applies selective raw footage decisions",
        rhythm.get("status") == "ready_with_edit_rhythm_plan"
        and as_int(rhythm_summary.get("primaryVisualShotCount")) >= 1
        and as_int(rhythm_summary.get("rowsWithDecisionFields")) == as_int(rhythm_summary.get("primaryVisualShotCount"))
        and creator.get("status") == "ready_with_creator_cut_plan"
        and as_int(creator_summary.get("creatorDecisionRowCount")) >= 1
        and as_int(creator_summary.get("primaryVisualShotCount")) >= 1
        and creator_application.get("status") == "passed"
        and as_int(creator_application_summary.get("visualClipCount")) >= 1
        and as_int(creator_application_summary.get("matchedCreatorRowCount")) == as_int(creator_application_summary.get("visualClipCount"))
        and as_int(creator_application_summary.get("blockedClipCount")) == 0
        and as_int(creator_application_summary.get("chaptersBlocked")) == 0
        and as_int(creator_application_summary.get("rejectActiveClipCount")) == 0
        and as_int(creator_application_summary.get("weakActiveClipCount")) == 0
        and final_source_usage.get("status") == "passed"
        and as_int(final_source_usage_summary.get("rawSourceClipCount")) >= 1
        and as_int(final_source_usage_summary.get("matchedRawSourceClipCount")) == as_int(final_source_usage_summary.get("rawSourceClipCount"))
        and as_int(final_source_usage_summary.get("unmatchedRawSourceClipCount")) == 0
        and as_int(final_source_usage_summary.get("selectedCandidateClipCount")) >= 1
        and as_int(final_source_usage_summary.get("rejectOrRepairActiveClipCount")) == 0
        and as_int(final_source_usage_summary.get("chaptersBlocked")) == 0,
        {
            "rhythmStatus": rhythm.get("status"),
            "primaryVisualShotCount": rhythm_summary.get("primaryVisualShotCount"),
            "rowsWithDecisionFields": rhythm_summary.get("rowsWithDecisionFields"),
            "creatorStatus": creator.get("status"),
            "creatorDecisionRowCount": creator_summary.get("creatorDecisionRowCount"),
            "rejectOrUtilityCount": creator_summary.get("rejectOrUtilityCount"),
            "creatorApplicationStatus": creator_application.get("status"),
            "creatorApplicationSummary": creator_application_summary,
            "finalSourceUsageStatus": final_source_usage.get("status"),
            "finalSourceUsageSummary": final_source_usage_summary,
        },
    )

    transition_grammar = load_json(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json") or {}
    transition_execution = load_json(package_dir / "transition_execution_plan" / "transition_execution_plan.json") or {}
    transition_motif = load_json(package_dir / "transition_motif_plan" / "transition_motif_plan.json") or {}
    bridge_sequence = load_json(package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json") or {}
    bgm_phrase = load_json(package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json") or {}
    rhythm_recut = load_json(package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json") or {}
    rhythm_recut_application = load_json(package_dir / "rhythm_recut_application_contract_audit.json") or {}
    transition_choreography_plan = load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json") or {}
    transition_choreography_contract = load_json(package_dir / "transition_choreography_contract_audit.json") or {}
    transition_motion_direction = load_json(package_dir / "transition_motion_direction_contract_audit.json") or {}
    transition_cutpoint = load_json(package_dir / "transition_cutpoint_contract_audit.json") or {}
    transition_action_anchor = load_json(package_dir / "transition_action_anchor_contract_audit.json") or {}
    transition_sensory = load_json(package_dir / "transition_sensory_continuity_contract_audit.json") or {}
    polish = load_json(package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json") or {}
    add_gate(
        gates,
        "Transition planning chain is materialized before Resolve writes",
        transition_grammar.get("status") == "ready_with_transition_grammar_plan"
        and transition_execution.get("status") == "ready_with_transition_execution_plan"
        and transition_motif.get("status") == "ready_with_transition_motif_plan"
        and bridge_sequence.get("status") == "ready_with_bridge_sequence_plan"
        and bgm_phrase.get("status") == "ready_with_bgm_phrase_blueprint"
        and rhythm_recut.get("status") in {"ready_with_rhythm_recut_blueprint", "ready_no_recut_needed"}
        and transition_choreography_plan.get("status") == "ready_with_transition_choreography_plan"
        and transition_choreography_contract.get("status") == "passed"
        and transition_motion_direction.get("status") == "passed"
        and transition_cutpoint.get("status") == "passed"
        and transition_action_anchor.get("status") == "passed"
        and transition_sensory.get("status") == "passed"
        and polish.get("status") == "ready_with_transition_polish_blueprint",
        {
            "transitionGrammarStatus": transition_grammar.get("status"),
            "transitionExecutionStatus": transition_execution.get("status"),
            "transitionMotifStatus": transition_motif.get("status"),
            "bridgeSequenceStatus": bridge_sequence.get("status"),
            "bgmPhraseStatus": bgm_phrase.get("status"),
            "rhythmRecutStatus": rhythm_recut.get("status"),
            "transitionChoreographyPlanStatus": transition_choreography_plan.get("status"),
            "transitionChoreographyContractStatus": transition_choreography_contract.get("status"),
            "transitionMotionDirectionStatus": transition_motion_direction.get("status"),
            "transitionCutpointStatus": transition_cutpoint.get("status"),
            "transitionActionAnchorStatus": transition_action_anchor.get("status"),
            "transitionSensoryContinuityStatus": transition_sensory.get("status"),
            "transitionPolishStatus": polish.get("status"),
        },
    )

    rhythm_recut_application_summary = summary_of(rhythm_recut_application)
    add_gate(
        gates,
        "Rhythm recut application proves long-shot repairs survived into the final candidate blueprint",
        rhythm_recut_application.get("status") == "passed"
        and as_int(rhythm_recut_application_summary.get("blockedRecutRowCount")) == 0
        and (
            rhythm_recut_application_summary.get("recutStatus") == "ready_no_recut_needed"
            or as_int(rhythm_recut_application_summary.get("finalRhythmRecutCutawayCount")) >= 1
        )
        and as_int(rhythm_recut_application_summary.get("blockerCount")) == 0,
        {
            "status": rhythm_recut_application.get("status"),
            "summary": rhythm_recut_application_summary,
            "blockers": rhythm_recut_application.get("blockers") or [],
        },
    )

    transition_quality = load_json(package_dir / "transition_quality_contract_audit.json") or {}
    shot_boundary = load_json(package_dir / "shot_transition_boundary_contract_audit.json") or {}
    transition_motivation = load_json(package_dir / "transition_motivation_contract_audit.json") or {}
    transition_pair_continuity = load_json(package_dir / "transition_pair_continuity_contract_audit.json") or {}
    transition_execution_readiness = load_json(package_dir / "transition_execution_readiness_contract_audit.json") or {}
    transition_polish_application = load_json(package_dir / "transition_polish_application_contract_audit.json") or {}
    resolve_transition_materialization = load_json(package_dir / "resolve_transition_materialization_contract_audit.json") or {}
    resolve_transition_apply = load_json(package_dir / "resolve_transition_apply_contract_audit.json") or {}
    bridge_sequence_application = load_json(package_dir / "bridge_sequence_application_contract_audit.json") or {}
    transition_bridge_visual_evidence = load_json(package_dir / "transition_bridge_visual_evidence_contract_audit.json") or {}
    final_blueprint_lineage = load_json(package_dir / "final_blueprint_lineage_contract_audit.json") or {}
    effect_motion_application = load_json(package_dir / "effect_motion_application_contract_audit.json") or {}
    transition_cadence = load_json(package_dir / "transition_cadence_contract_audit.json") or {}
    transition_microstructure = load_json(package_dir / "transition_microstructure_contract_audit.json") or {}
    reference_scene_grammar = load_json(package_dir / "reference_scene_grammar_contract_audit.json") or {}
    reference_profile_application = load_json(package_dir / "reference_profile_application_contract_audit.json") or {}
    timeline_variety = load_json(package_dir / "timeline_variety_contract_audit.json") or {}
    transition_scene_arc = load_json(package_dir / "transition_scene_arc_contract_audit.json") or {}
    transition_effect_palette = load_json(package_dir / "transition_effect_palette_contract_audit.json") or {}
    transition_visual_match = load_json(package_dir / "transition_visual_match_contract_audit.json") or {}
    transition_reference_candidates = load_json(package_dir / "transition_reference_candidates" / "transition_reference_candidates.json") or {}
    transition_reference_selection = load_json(package_dir / "transition_reference_selection" / "transition_reference_selection.json") or {}
    transition_choreography_plan = load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json") or {}
    transition_choreography_contract = load_json(package_dir / "transition_choreography_contract_audit.json") or {}
    transition_motion_direction = load_json(package_dir / "transition_motion_direction_contract_audit.json") or {}
    transition_cutpoint = load_json(package_dir / "transition_cutpoint_contract_audit.json") or {}
    transition_action_anchor = load_json(package_dir / "transition_action_anchor_contract_audit.json") or {}
    transition_sensory = load_json(package_dir / "transition_sensory_continuity_contract_audit.json") or {}
    transition_preview_packet = load_json(package_dir / "transition_preview_packet" / "transition_preview_packet.json") or {}
    transition_preview_quality = load_json(package_dir / "transition_preview_quality_contract_audit.json") or {}
    transition_audition_packet = load_json(package_dir / "transition_audition_packet" / "transition_audition_packet.json") or {}
    transition_audition_quality = load_json(package_dir / "transition_audition_quality_contract_audit.json") or {}
    transition_audition_visual_proof = load_json(package_dir / "transition_audition_visual_proof_contract_audit.json") or {}
    transition_audition_role_integrity = load_json(package_dir / "transition_audition_role_integrity_contract_audit.json") or {}
    transition_storyboard = load_json(package_dir / "transition_storyboard_contract_audit.json") or {}
    reference_transition_profile = load_json(package_dir / "reference_transition_profile_contract_audit.json") or {}
    chapter_story_spine = load_json(package_dir / "chapter_story_spine_contract_audit.json") or {}
    shot_flow_continuity = load_json(package_dir / "shot_flow_continuity_contract_audit.json") or {}
    transition_breathing_room = load_json(package_dir / "transition_breathing_room_contract_audit.json") or {}
    transition_continuity_rehearsal = load_json(package_dir / "transition_continuity_rehearsal_contract_audit.json") or {}
    pacing_watchability = load_json(package_dir / "pacing_watchability_contract_audit.json") or {}
    scene_flow_arc = load_json(package_dir / "scene_flow_arc_contract_audit.json") or {}
    final_cut_smoothness = load_json(package_dir / "final_cut_smoothness_contract_audit.json") or {}
    tq_summary = summary_of(transition_quality)
    sb_summary = summary_of(shot_boundary)
    tm_summary = summary_of(transition_motivation)
    tpc_summary = summary_of(transition_pair_continuity)
    ter_summary = summary_of(transition_execution_readiness)
    tpa_summary = summary_of(transition_polish_application)
    rtm_summary = summary_of(resolve_transition_materialization)
    rta_summary = summary_of(resolve_transition_apply)
    bsa_summary = summary_of(bridge_sequence_application)
    tbv_summary = summary_of(transition_bridge_visual_evidence)
    fbl_summary = summary_of(final_blueprint_lineage)
    ema_summary = summary_of(effect_motion_application)
    tc_summary = summary_of(transition_cadence)
    tms_summary = summary_of(transition_microstructure)
    rsg_summary = summary_of(reference_scene_grammar)
    rpa_summary = summary_of(reference_profile_application)
    tv_summary = summary_of(timeline_variety)
    tsa_summary = summary_of(transition_scene_arc)
    tep_summary = summary_of(transition_effect_palette)
    tvm_summary = summary_of(transition_visual_match)
    trc_summary = summary_of(transition_reference_candidates)
    trs_summary = summary_of(transition_reference_selection)
    tcp_summary = summary_of(transition_choreography_plan)
    tcc_summary = summary_of(transition_choreography_contract)
    tmd_summary = summary_of(transition_motion_direction)
    tcpn_summary = summary_of(transition_cutpoint)
    taa_summary = summary_of(transition_action_anchor)
    tsc_summary = summary_of(transition_sensory)
    tpp_summary = summary_of(transition_preview_packet)
    tpq_summary = summary_of(transition_preview_quality)
    tap_summary = summary_of(transition_audition_packet)
    taq_summary = summary_of(transition_audition_quality)
    tavp_summary = summary_of(transition_audition_visual_proof)
    tari_summary = summary_of(transition_audition_role_integrity)
    tsb_summary = summary_of(transition_storyboard)
    rtp_summary = summary_of(reference_transition_profile)
    css_summary = summary_of(chapter_story_spine)
    sfc_summary = summary_of(shot_flow_continuity)
    tbr_summary = summary_of(transition_breathing_room)
    tcr_summary = summary_of(transition_continuity_rehearsal)
    pw_summary = summary_of(pacing_watchability)
    sfa_summary = summary_of(scene_flow_arc)
    fcs_summary = summary_of(final_cut_smoothness)
    add_gate(
        gates,
        "Transition reference candidates turn every adjacent boundary into non-copying A/B/C choices before preview, storyboard, or Resolve apply",
        transition_reference_candidates.get("status") == "ready_with_transition_reference_candidates"
        and as_int(trc_summary.get("transitionRowCount")) >= 1
        and as_int(trc_summary.get("candidateRowCount")) == as_int(trc_summary.get("transitionRowCount"))
        and as_int(trc_summary.get("rowsWithAtLeastThreeCandidates")) == as_int(trc_summary.get("candidateRowCount"))
        and as_int(trc_summary.get("motionCandidateRowCount")) <= as_int(trc_summary.get("maxMotionCandidateRows"))
        and (
            as_int(trc_summary.get("importantBoundaryCount")) == 0
            or float(trc_summary.get("importantBridgeOrBreathCoverage") or 0.0) >= 1.0
        ),
        {
            "transitionReferenceCandidatesStatus": transition_reference_candidates.get("status"),
            "transitionReferenceCandidatesSummary": trc_summary,
        },
    )
    add_gate(
        gates,
        "Transition reference selection auto-chooses one safe default transition per boundary for unattended first drafts",
        transition_reference_selection.get("status") == "ready_with_transition_reference_selection"
        and as_int(trs_summary.get("candidateRowCount")) >= 1
        and as_int(trs_summary.get("selectionRowCount")) == as_int(trs_summary.get("candidateRowCount"))
        and as_int(trs_summary.get("selectedRowCount")) == as_int(trs_summary.get("candidateRowCount"))
        and as_int(trs_summary.get("autoSelectedRowCount")) == as_int(trs_summary.get("candidateRowCount"))
        and as_int(trs_summary.get("blockedSelectionRowCount")) == 0
        and as_int(trs_summary.get("motionSelectedRowCount")) <= as_int(trs_summary.get("maxMotionRows"))
        and (
            as_int(trs_summary.get("importantBoundaryCount")) == 0
            or float(trs_summary.get("importantBridgeOrBreathSelectionCoverage") or 0.0) >= 1.0
        ),
        {
            "transitionReferenceSelectionStatus": transition_reference_selection.get("status"),
            "transitionReferenceSelectionSummary": trs_summary,
        },
    )
    add_gate(
        gates,
        "Transition cadence, execution, scene arcs, effect palette, visual match, preview packet quality, storyboard, reference-profile application, scene grammar, and timeline variety prove every boundary and shot function are executable, matched, restrained, previewed, and reference-like",
        transition_quality.get("status") == "passed"
        and shot_boundary.get("status") == "passed"
        and transition_motivation.get("status") == "passed"
        and transition_pair_continuity.get("status") == "passed"
        and transition_execution_readiness.get("status") == "passed"
        and transition_polish_application.get("status") == "passed"
        and resolve_transition_materialization.get("status") == "passed"
        and resolve_transition_apply.get("status") == "passed"
        and bridge_sequence_application.get("status") == "passed"
        and transition_bridge_visual_evidence.get("status") == "passed"
        and final_blueprint_lineage.get("status") == "passed"
        and effect_motion_application.get("status") == "passed"
        and transition_cadence.get("status") == "passed"
        and transition_microstructure.get("status") == "passed"
        and reference_scene_grammar.get("status") == "passed"
        and reference_profile_application.get("status") == "passed"
        and timeline_variety.get("status") == "passed"
        and transition_scene_arc.get("status") == "passed"
        and transition_effect_palette.get("status") == "passed"
        and transition_visual_match.get("status") == "passed"
        and transition_choreography_plan.get("status") == "ready_with_transition_choreography_plan"
        and transition_choreography_contract.get("status") == "passed"
        and transition_motion_direction.get("status") == "passed"
        and transition_cutpoint.get("status") == "passed"
        and transition_action_anchor.get("status") == "passed"
        and transition_sensory.get("status") == "passed"
        and transition_preview_packet.get("status") in {"ready_with_transition_preview_packet", "ready_no_important_transitions"}
        and transition_preview_quality.get("status") == "passed"
        and transition_audition_packet.get("status") in {"ready_with_transition_audition_packet", "ready_no_important_transitions"}
        and transition_audition_quality.get("status") == "passed"
        and transition_audition_visual_proof.get("status") == "passed"
        and transition_audition_role_integrity.get("status") == "passed"
        and transition_storyboard.get("status") == "passed"
        and reference_transition_profile.get("status") == "passed"
        and transition_continuity_rehearsal.get("status") == "passed"
        and pacing_watchability.get("status") == "passed"
        and as_int(tq_summary.get("blockedRowCount")) == 0
        and as_int(sb_summary.get("blockedBoundaryCount")) == 0
        and as_int(tm_summary.get("blockedBoundaryCount")) == 0
        and as_int(tpc_summary.get("blockedBoundaryCount")) == 0
        and as_int(ter_summary.get("blockedBoundaryCount")) == 0
        and as_int(tpc_summary.get("weakPairFitCount")) == 0
        and as_int(ter_summary.get("recipeReadyBoundaryCount")) == as_int(ter_summary.get("visualBoundaryCount"))
        and as_int(ter_summary.get("pairReadyBoundaryCount")) == as_int(ter_summary.get("visualBoundaryCount"))
        and as_int(ter_summary.get("handleReadyBoundaryCount")) == as_int(ter_summary.get("visualBoundaryCount"))
        and as_int(tpa_summary.get("blockedPolishRowCount")) == 0
        and as_int(tpa_summary.get("passedPolishRowCount")) == as_int(tpa_summary.get("sourcePolishRowCount"))
        and as_int(tpa_summary.get("bgmHitRowCount")) == as_int(tpa_summary.get("sourcePolishRowCount"))
        and as_int(tpa_summary.get("titleSafeRowCount")) == as_int(tpa_summary.get("sourcePolishRowCount"))
        and as_int(tpa_summary.get("pairReadyRowCount")) == as_int(tpa_summary.get("sourcePolishRowCount"))
        and as_int(tpa_summary.get("clipAnnotationRowCount")) == as_int(tpa_summary.get("sourcePolishRowCount"))
        and as_int(tpa_summary.get("markerRowCount")) == as_int(tpa_summary.get("sourcePolishRowCount"))
        and as_int(rtm_summary.get("blockedTransitionRowCount")) == 0
        and as_int(rtm_summary.get("transitionCandidateCount")) >= 1
        and as_int(rtm_summary.get("transitionRowsWithMarkerPayload")) == as_int(rtm_summary.get("transitionCandidateCount"))
        and as_int(rtm_summary.get("transitionRowsWithClipAnnotation")) == as_int(rtm_summary.get("transitionCandidateCount"))
        and as_int(rta_summary.get("blockedRowCount")) == 0
        and as_int(rta_summary.get("transitionApplyRowCount")) >= 1
        and as_int(rta_summary.get("passedRowCount")) == as_int(rta_summary.get("transitionApplyRowCount"))
        and as_int(rta_summary.get("visibleEffectRowsWithApplyPath")) == as_int(rta_summary.get("visibleEffectRowCount"))
        and as_int(rta_summary.get("markerOnlyBlockedRowCount")) == 0
        and as_int(rta_summary.get("decisionFieldRowCount")) == as_int(rta_summary.get("transitionApplyRowCount"))
        and as_int(bsa_summary.get("blockedSequenceRowCount")) == 0
        and as_int(bsa_summary.get("missingBeatClipCount")) == 0
        and as_int(bsa_summary.get("sourceAudioLeakClipCount")) == 0
        and as_int(tbv_summary.get("blockedBridgeRowCount")) == 0
        and as_int(tbv_summary.get("blockedBridgeVisualClipCount")) == 0
        and as_int(tbv_summary.get("missingBeatClipCount")) == 0
        and as_int(tbv_summary.get("passedBridgeVisualClipCount")) >= as_int(tbv_summary.get("expectedBeatClipCount"))
        and as_int(tbv_summary.get("frameEvidenceCount")) >= as_int(tbv_summary.get("expectedBeatClipCount"))
        and as_int(tbv_summary.get("videoProbeReadyCount")) >= as_int(tbv_summary.get("expectedBeatClipCount"))
        and as_int(tbv_summary.get("sourceAudioLeakClipCount")) == 0
        and as_int(fbl_summary.get("readyStageCount")) >= as_int(fbl_summary.get("requiredMinimumReadyStages"), 5)
        and as_int(fbl_summary.get("blockedReadyStageCount")) == 0
        and as_int(fbl_summary.get("finalPlanKeyCount")) >= as_int(fbl_summary.get("requiredMinimumReadyStages"), 5)
        and as_int(ema_summary.get("sourceEffectRowCount")) >= 1
        and as_int(ema_summary.get("passedEffectRowCount")) == as_int(ema_summary.get("sourceEffectRowCount"))
        and as_int(ema_summary.get("blockedEffectRowCount")) == 0
        and as_int(ema_summary.get("motionEffectRowCount")) <= as_int(ema_summary.get("maxMotionAllowed"))
        and as_int(ema_summary.get("bgmOnlyRowCount")) == as_int(ema_summary.get("sourceEffectRowCount"))
        and as_int(ema_summary.get("titleSafeRowCount")) == as_int(ema_summary.get("sourceEffectRowCount"))
        and as_int(ema_summary.get("sourceEvidenceRowCount")) == as_int(ema_summary.get("sourceEffectRowCount"))
        and as_int(ema_summary.get("motionEvidenceRowCount")) == as_int(ema_summary.get("sourceEffectRowCount"))
        and as_int(ema_summary.get("clipAnnotationRowCount")) == as_int(ema_summary.get("sourceEffectRowCount"))
        and as_int(ema_summary.get("markerRowCount")) == as_int(ema_summary.get("sourceEffectRowCount"))
        and as_int(ema_summary.get("forbiddenEffectHitCount")) == 0
        and as_int(tc_summary.get("blockedCheckCount")) == 0
        and as_int(tc_summary.get("visualBoundaryCount")) >= 1
        and as_int(tc_summary.get("transitionRowCount")) >= as_int(tc_summary.get("visualBoundaryCount"))
        and as_int(tc_summary.get("craftedTransitionCount")) >= as_int(tc_summary.get("minimumCraftedTransitionCount"))
        and as_int(tc_summary.get("motionTransitionCount")) <= as_int(tc_summary.get("maxMotionAllowed"))
        and as_int(tc_summary.get("decorativeRepeatedRunMax")) < 4
        and as_int(tms_summary.get("blockedCheckCount")) == 0
        and as_int(tms_summary.get("visualBoundaryCount")) >= 1
        and as_int(tms_summary.get("transitionRowCount")) >= as_int(tms_summary.get("visualBoundaryCount"))
        and as_int(tms_summary.get("bgmHitBoundaryCount")) == as_int(tms_summary.get("visualBoundaryCount"))
        and as_int(tms_summary.get("titleSafeBoundaryCount")) == as_int(tms_summary.get("visualBoundaryCount"))
        and as_int(tms_summary.get("bgmOnlyBoundaryCount")) == as_int(tms_summary.get("visualBoundaryCount"))
        and as_int(tms_summary.get("handleReadyBoundaryCount")) == as_int(tms_summary.get("visualBoundaryCount"))
        and as_int(tms_summary.get("pairReadyBoundaryCount")) == as_int(tms_summary.get("visualBoundaryCount"))
        and as_int(tms_summary.get("weakPairFitCount")) == 0
        and as_int(tms_summary.get("markerOnlyBlockedRowCount")) == 0
        and as_int(tms_summary.get("appliedBridgeBeatClipCount")) >= as_int(tms_summary.get("expectedBridgeBeatClipCount"))
        and as_int(rsg_summary.get("chaptersBlocked")) == 0
        and as_int(rsg_summary.get("blockerCount")) == 0
        and as_int(tv_summary.get("blockedCheckCount")) == 0
        and bool_field(tv_summary, "movementReady")
        and bool_field(tv_summary, "textureReady")
        and bool_field(tv_summary, "payoffReady")
        and bool_field(tv_summary, "aftertasteReady")
        and as_int(tv_summary.get("sameSourceRunMax")) <= 3
        and as_int(tv_summary.get("sameFunctionRunMax")) <= 4
        and as_int(tsa_summary.get("blockedCheckCount")) == 0
        and as_int(tsa_summary.get("visualBoundaryCount")) >= 1
        and (
            as_int(tsa_summary.get("importantBoundaryCount")) == 0
            or as_int(tsa_summary.get("sceneArcStrategyCount")) >= 1
        )
        and as_int(tsa_summary.get("appliedBridgeBeatClipCount")) >= as_int(tsa_summary.get("expectedBridgeBeatClipCount"))
        and as_int(tsa_summary.get("motionTransitionCount")) <= as_int(tsa_summary.get("maxMotionAllowed"))
        and as_int(tsa_summary.get("decorativeRepeatedRunMax")) < 4
        and float(tsa_summary.get("dominantStyleShare") or 0.0) <= 0.7
        and bool_field(tsa_summary, "movementReady")
        and bool_field(tsa_summary, "textureReady")
        and bool_field(tsa_summary, "payoffReady")
        and bool_field(tsa_summary, "aftertasteReady")
        and as_int(tep_summary.get("blockedCheckCount")) == 0
        and as_int(tep_summary.get("visualBoundaryCount")) >= 1
        and as_int(tep_summary.get("motifFamilyCount")) >= as_int(tep_summary.get("minimumPaletteFamilyCount"))
        and as_int(tep_summary.get("motionTransitionCount")) <= as_int(tep_summary.get("maxMotionAllowed"))
        and as_int(tep_summary.get("decorativeRepeatedRunMax")) < 4
        and float(tep_summary.get("dominantMotifShare") or 0.0) <= 0.65
        and as_int(tep_summary.get("cleanOrMatchCount")) >= 1
        and (
            as_int(tep_summary.get("importantBoundaryCount")) == 0
            or as_int(tep_summary.get("physicalBridgeOrSceneArcCount")) >= 1
        )
        and as_int(tvm_summary.get("blockedRowCount")) == 0
        and as_int(tvm_summary.get("visualBoundaryCount")) >= 1
        and as_int(tvm_summary.get("visualMatchReadyRowCount")) == as_int(tvm_summary.get("transitionRowCount"))
        and as_int(tvm_summary.get("motionTransitionCount")) <= as_int(tvm_summary.get("maxMotionAllowed"))
        and (
            as_int(tvm_summary.get("importantBoundaryCount")) == 0
            or as_int(tvm_summary.get("importantBridgeOrSceneHandoffCount")) >= as_int(tvm_summary.get("importantBoundaryCount"))
        )
        and as_int(tsb_summary.get("blockedRowCount")) == 0
        and as_int(tsb_summary.get("visualBoundaryCount")) >= 1
        and as_int(tsb_summary.get("storyboardReadyRowCount")) == as_int(tsb_summary.get("transitionRowCount"))
        and as_int(tsb_summary.get("rowsWithViewerPurpose")) == as_int(tsb_summary.get("transitionRowCount"))
        and as_int(tsb_summary.get("rowsWithOutgoingEvidence")) == as_int(tsb_summary.get("transitionRowCount"))
        and as_int(tsb_summary.get("rowsWithLandingEvidence")) == as_int(tsb_summary.get("transitionRowCount"))
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tsb_summary.get("importantPreviewEvidenceCount")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tpp_summary.get("readyPreviewRowCount")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tpq_summary.get("previewQualityReadyRowCount")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and as_int(tpq_summary.get("blockedPreviewQualityRowCount")) == 0
        and as_int(tcc_summary.get("blockedChoreographyRowCount")) == 0
        and as_int(tcc_summary.get("highIntensityRowCount")) == 0
        and as_int(tcc_summary.get("importantRowsWithThreeBeatCount")) >= as_int(tcc_summary.get("importantBoundaryCount"))
        and as_int(tsc_summary.get("blockedSensoryContinuityRowCount")) == 0
        and as_int(tsc_summary.get("readySensoryContinuityRowCount")) >= as_int(tsc_summary.get("transitionRowCount"))
        and as_int(tsc_summary.get("rowsWithVisualSensoryContinuity")) >= as_int(tsc_summary.get("transitionRowCount"))
        and as_int(tsc_summary.get("rowsWithAudioSensoryContinuity")) >= as_int(tsc_summary.get("transitionRowCount"))
        and as_int(tsc_summary.get("rowsWithCaptionSensoryContinuity")) >= as_int(tsc_summary.get("transitionRowCount"))
        and as_int(tsc_summary.get("rowsWithLandingSensoryContinuity")) >= as_int(tsc_summary.get("transitionRowCount"))
        and (
            as_int(tsc_summary.get("importantBoundaryCount")) == 0
            or as_int(tsc_summary.get("importantRowsWithRouteOrMoodContinuity")) >= as_int(tsc_summary.get("importantBoundaryCount"))
        )
        and as_int(tcr_summary.get("blockedRehearsalRowCount")) == 0
        and as_int(tcr_summary.get("blockedAdjacentPairCount")) == 0
        and as_int(tcr_summary.get("rehearsalReadyRowCount")) >= as_int(tcr_summary.get("transitionRowCount"))
        and as_int(tcr_summary.get("rehearsalReadyPairCount")) >= as_int(tcr_summary.get("adjacentPairCount"))
        and as_int(tcr_summary.get("adjacentMotionPairCount")) == 0
        and as_int(tcr_summary.get("backToBackImportantPairCount")) == 0
        and as_int(tcr_summary.get("highImpactPurposeRunViolationCount")) == 0
        and as_int(pw_summary.get("visualClipCount")) >= 3
        and as_int(pw_summary.get("blockedChapterCount")) == 0
        and as_int(pw_summary.get("longFlatShotCount")) == 0
        and as_int(pw_summary.get("veryLongShotCount")) == 0
        and as_int(pw_summary.get("longFlatRunMax")) <= 1
        and as_int(pw_summary.get("shortClipRunMax")) <= 2
        and as_int(pw_summary.get("breathingShotCount")) >= as_int(pw_summary.get("chapterCount"))
        and as_int(pw_summary.get("blockedCheckCount")) == 0
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("readyAuditionRowCount")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithMotionExecution")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithThreeBeatMotion")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithBgmHitMotion")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithCaptionQuietMotion")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithMotionDirection")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithMotionDirectionMatch")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithCutpoint")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithCutpointBgm")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithCutpointLanding")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithCutpointHandles")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithOutgoingActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithBridgeOrMatchActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tap_summary.get("rowsWithLandingActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("auditionQualityReadyRowCount")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithMotionExecution")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithThreeBeatMotion")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithBgmHitMotion")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithCaptionQuietMotion")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithMotionDirection")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithMotionDirectionMatch")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithCutpoint")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithCutpointBgm")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithCutpointLanding")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithCutpointHandles")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithOutgoingActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithBridgeOrMatchActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithLandingActionAnchor")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(taq_summary.get("rowsWithResolveKeyframeEffect")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and as_int(taq_summary.get("blockedAuditionQualityRowCount")) == 0
        and as_int(taq_summary.get("probeReadyClipCount")) >= as_int(taq_summary.get("auditionClipCount"))
        and as_int(taq_summary.get("noAudioClipCount")) >= as_int(taq_summary.get("auditionClipCount"))
        and as_int(tavp_summary.get("blockedAuditionVisualRowCount")) == 0
        and as_int(tavp_summary.get("rowsWithFrameProof")) >= as_int(tavp_summary.get("auditionVisualRowCount"))
        and as_int(tavp_summary.get("rowsWithDistinctEndpointFrames")) >= as_int(tavp_summary.get("auditionVisualRowCount"))
        and as_int(tavp_summary.get("rowsWithMiddleMotionProof")) >= as_int(tavp_summary.get("auditionVisualRowCount"))
        and as_int(tari_summary.get("blockedAuditionRoleRowCount")) == 0
        and as_int(tari_summary.get("rowsWithRoleOrderedSegments")) >= as_int(tari_summary.get("auditionRoleRowCount"))
        and as_int(tari_summary.get("rowsWithBridgeOrMotionSegment")) >= as_int(tari_summary.get("auditionRoleRowCount"))
        and as_int(tari_summary.get("rowsWithConcatOrderEvidence")) >= as_int(tari_summary.get("auditionRoleRowCount"))
        and (
            as_int(tsb_summary.get("importantBoundaryCount")) == 0
            or as_int(tari_summary.get("rowsWithBridgeSegment")) >= as_int(tsb_summary.get("importantBoundaryCount"))
        )
        and as_int(rtp_summary.get("blockerCount")) == 0
        and as_int(rtp_summary.get("readyReportCount")) >= as_int(rtp_summary.get("requiredReportCount"))
        and as_int(rtp_summary.get("transitionRowCount")) >= 1
        and as_float(rtp_summary.get("motionShare")) <= 0.25
        and (
            as_int(rtp_summary.get("transitionRowCount")) < 3
            or as_float(rtp_summary.get("cleanMatchBreathShare")) >= 0.45
        )
        and as_float(rtp_summary.get("importantBridgeBreathCoverage"), 1.0) >= 1.0
        and as_int(tsb_summary.get("motionReadyRowCount")) == as_int(tsb_summary.get("motionTransitionCount"))
        and as_int(tm_summary.get("motivatedBoundaryCount")) == as_int(tm_summary.get("visualBoundaryCount"))
        and as_int(tpc_summary.get("pairContinuityPayloadCount")) == as_int(tpc_summary.get("visualBoundaryCount"))
        and not transition_quality.get("blockers")
        and not shot_boundary.get("blockers")
        and not transition_motivation.get("blockers")
        and not transition_pair_continuity.get("blockers")
        and not transition_execution_readiness.get("blockers")
        and not transition_polish_application.get("blockers")
        and not resolve_transition_materialization.get("blockers")
        and not resolve_transition_apply.get("blockers")
        and not bridge_sequence_application.get("blockers")
        and not transition_bridge_visual_evidence.get("blockers")
        and not final_blueprint_lineage.get("blockers")
        and not effect_motion_application.get("blockers")
        and not transition_cadence.get("blockers")
        and not transition_microstructure.get("blockers")
        and not reference_scene_grammar.get("blockers")
        and not reference_profile_application.get("blockers")
        and not timeline_variety.get("blockers")
        and not transition_scene_arc.get("blockers")
        and not transition_effect_palette.get("blockers")
        and not transition_visual_match.get("blockers")
        and not transition_choreography_plan.get("blockers")
        and not transition_choreography_contract.get("blockers")
        and not transition_motion_direction.get("blockers")
        and not transition_sensory.get("blockers")
        and not transition_preview_packet.get("blockers")
        and not transition_preview_quality.get("blockers")
        and not transition_audition_packet.get("blockers")
        and not transition_audition_quality.get("blockers")
        and not transition_audition_visual_proof.get("blockers")
        and not transition_audition_role_integrity.get("blockers")
        and not transition_storyboard.get("blockers")
        and not reference_transition_profile.get("blockers")
        and not scene_flow_arc.get("blockers")
        and not pacing_watchability.get("blockers")
        and not final_cut_smoothness.get("blockers"),
        {
            "transitionQualityStatus": transition_quality.get("status"),
            "transitionQualityBoundaryCount": tq_summary.get("visualBoundaryCount"),
            "transitionQualityBlockedRows": tq_summary.get("blockedRowCount"),
            "shotBoundaryStatus": shot_boundary.get("status"),
            "shotBoundaryBlocked": sb_summary.get("blockedBoundaryCount"),
            "motivationStatus": transition_motivation.get("status"),
            "motivatedBoundaryCount": tm_summary.get("motivatedBoundaryCount"),
            "visualBoundaryCount": tm_summary.get("visualBoundaryCount"),
            "motivationBlocked": tm_summary.get("blockedBoundaryCount"),
            "pairContinuityStatus": transition_pair_continuity.get("status"),
            "pairContinuitySummary": tpc_summary,
            "transitionExecutionReadinessStatus": transition_execution_readiness.get("status"),
            "transitionExecutionReadinessSummary": ter_summary,
            "transitionPolishApplicationStatus": transition_polish_application.get("status"),
            "transitionPolishApplicationSummary": tpa_summary,
            "resolveTransitionMaterializationStatus": resolve_transition_materialization.get("status"),
            "resolveTransitionMaterializationSummary": rtm_summary,
            "resolveTransitionApplyStatus": resolve_transition_apply.get("status"),
            "resolveTransitionApplySummary": rta_summary,
            "bridgeSequenceApplicationStatus": bridge_sequence_application.get("status"),
            "bridgeSequenceApplicationSummary": bsa_summary,
            "transitionBridgeVisualEvidenceStatus": transition_bridge_visual_evidence.get("status"),
            "transitionBridgeVisualEvidenceSummary": tbv_summary,
            "finalBlueprintLineageStatus": final_blueprint_lineage.get("status"),
            "finalBlueprintLineageSummary": fbl_summary,
            "effectMotionApplicationStatus": effect_motion_application.get("status"),
            "effectMotionApplicationSummary": ema_summary,
            "transitionCadenceStatus": transition_cadence.get("status"),
            "transitionCadenceSummary": tc_summary,
            "transitionMicrostructureStatus": transition_microstructure.get("status"),
            "transitionMicrostructureSummary": tms_summary,
            "referenceSceneGrammarStatus": reference_scene_grammar.get("status"),
            "referenceSceneGrammarSummary": rsg_summary,
            "referenceProfileApplicationStatus": reference_profile_application.get("status"),
            "referenceProfileApplicationSummary": rpa_summary,
            "timelineVarietyStatus": timeline_variety.get("status"),
            "timelineVarietySummary": tv_summary,
            "transitionSceneArcStatus": transition_scene_arc.get("status"),
            "transitionSceneArcSummary": tsa_summary,
            "transitionEffectPaletteStatus": transition_effect_palette.get("status"),
            "transitionEffectPaletteSummary": tep_summary,
            "transitionVisualMatchStatus": transition_visual_match.get("status"),
            "transitionVisualMatchSummary": tvm_summary,
            "transitionChoreographyPlanStatus": transition_choreography_plan.get("status"),
            "transitionChoreographyPlanSummary": tcp_summary,
            "transitionChoreographyContractStatus": transition_choreography_contract.get("status"),
            "transitionChoreographyContractSummary": tcc_summary,
            "transitionMotionDirectionStatus": transition_motion_direction.get("status"),
            "transitionMotionDirectionSummary": tmd_summary,
            "transitionCutpointStatus": transition_cutpoint.get("status"),
            "transitionCutpointSummary": tcpn_summary,
            "transitionActionAnchorStatus": transition_action_anchor.get("status"),
            "transitionActionAnchorSummary": taa_summary,
            "transitionSensoryContinuityStatus": transition_sensory.get("status"),
            "transitionSensoryContinuitySummary": tsc_summary,
            "transitionPreviewPacketStatus": transition_preview_packet.get("status"),
            "transitionPreviewPacketSummary": tpp_summary,
            "transitionPreviewQualityStatus": transition_preview_quality.get("status"),
            "transitionPreviewQualitySummary": tpq_summary,
            "transitionAuditionPacketStatus": transition_audition_packet.get("status"),
            "transitionAuditionPacketSummary": tap_summary,
            "transitionAuditionQualityStatus": transition_audition_quality.get("status"),
            "transitionAuditionQualitySummary": taq_summary,
            "transitionAuditionVisualProofStatus": transition_audition_visual_proof.get("status"),
            "transitionAuditionVisualProofSummary": tavp_summary,
            "transitionAuditionRoleIntegrityStatus": transition_audition_role_integrity.get("status"),
            "transitionAuditionRoleIntegritySummary": tari_summary,
            "transitionStoryboardStatus": transition_storyboard.get("status"),
            "transitionStoryboardSummary": tsb_summary,
            "referenceTransitionProfileStatus": reference_transition_profile.get("status"),
            "referenceTransitionProfileSummary": rtp_summary,
            "transitionContinuityRehearsalStatus": transition_continuity_rehearsal.get("status"),
            "transitionContinuityRehearsalSummary": tcr_summary,
            "pacingWatchabilityStatus": pacing_watchability.get("status"),
            "pacingWatchabilitySummary": pw_summary,
            "sceneFlowArcStatus": scene_flow_arc.get("status"),
            "sceneFlowArcSummary": sfa_summary,
            "finalCutSmoothnessStatus": final_cut_smoothness.get("status"),
            "finalCutSmoothnessSummary": fcs_summary,
        },
    )

    add_gate(
        gates,
        "Chapter story spine proves every chapter executes context, movement, lived-in texture, payoff, and aftertaste",
        chapter_story_spine.get("status") == "passed"
        and as_int(css_summary.get("chapterRowCount")) >= 1
        and as_int(css_summary.get("chaptersWithCompleteStorySpine")) == as_int(css_summary.get("chapterRowCount"))
        and as_int(css_summary.get("chaptersMissingStorySpine")) == 0
        and css_summary.get("referenceSceneGrammarStatus") == "passed"
        and css_summary.get("timelineVarietyStatus") == "passed"
        and css_summary.get("transitionSceneArcStatus") == "passed"
        and css_summary.get("referenceTransitionProfileStatus") == "passed"
        and as_int(css_summary.get("blockedCheckCount")) == 0
        and as_int(css_summary.get("blockerCount")) == 0
        and not chapter_story_spine.get("blockers"),
        {
            "status": chapter_story_spine.get("status"),
            "summary": css_summary,
            "blockers": chapter_story_spine.get("blockers") or [],
        },
    )

    add_gate(
        gates,
        "Shot flow continuity proves each chapter's final clip order is readable before handoff",
        shot_flow_continuity.get("status") == "passed"
        and as_int(sfc_summary.get("visualClipCount")) >= 3
        and as_int(sfc_summary.get("chapterCount")) >= 1
        and as_int(sfc_summary.get("chaptersPassed")) == as_int(sfc_summary.get("chapterCount"))
        and as_int(sfc_summary.get("chaptersBlocked")) == 0
        and as_int(sfc_summary.get("weakClipCount")) == 0
        and as_int(sfc_summary.get("weakFlowPairCount")) == 0
        and as_int(sfc_summary.get("sameBeatRunMax")) <= 3
        and as_int(sfc_summary.get("sameSourceRunMax")) <= 3
        and as_int(sfc_summary.get("utilityRunMax")) <= 2
        and sfc_summary.get("chapterStorySpineStatus") == "passed"
        and sfc_summary.get("timelineVarietyStatus") == "passed"
        and sfc_summary.get("transitionPairContinuityStatus") == "passed"
        and sfc_summary.get("transitionMicrostructureStatus") == "passed"
        and sfc_summary.get("referenceSceneGrammarStatus") == "passed"
        and as_int(sfc_summary.get("blockedCheckCount")) == 0
        and as_int(sfc_summary.get("blockerCount")) == 0
        and not shot_flow_continuity.get("blockers"),
        {
            "status": shot_flow_continuity.get("status"),
            "summary": sfc_summary,
            "blockers": shot_flow_continuity.get("blockers") or [],
        },
    )

    add_gate(
        gates,
        "Transition breathing-room proves important boundaries land before the next idea",
        transition_breathing_room.get("status") == "passed"
        and as_int(tbr_summary.get("visualBoundaryCount")) >= 1
        and as_int(tbr_summary.get("landingDurationViolationCount")) == 0
        and as_int(tbr_summary.get("motionSpacingViolationCount")) == 0
        and as_int(tbr_summary.get("highIntensityRunMax")) <= 1
        and as_int(tbr_summary.get("subtitleCollisionRiskCount")) == 0
        and as_int(tbr_summary.get("titleCollisionRiskCount")) == 0
        and as_int(tbr_summary.get("breathAfterImportantReadyCount")) >= as_int(tbr_summary.get("importantBoundaryCount"))
        and as_int(tbr_summary.get("blockedCheckCount")) == 0
        and as_int(tbr_summary.get("blockerCount")) == 0
        and not transition_breathing_room.get("blockers"),
        {
            "status": transition_breathing_room.get("status"),
            "summary": tbr_summary,
            "blockers": transition_breathing_room.get("blockers") or [],
        },
    )

    add_gate(
        gates,
        "Transition continuity rehearsal proves approved storyboard rows connect as a watchable sequence",
        transition_continuity_rehearsal.get("status") == "passed"
        and as_int(tcr_summary.get("transitionRowCount")) >= 1
        and as_int(tcr_summary.get("rehearsalReadyRowCount")) == as_int(tcr_summary.get("transitionRowCount"))
        and as_int(tcr_summary.get("rehearsalReadyPairCount")) == as_int(tcr_summary.get("adjacentPairCount"))
        and as_int(tcr_summary.get("blockedRehearsalRowCount")) == 0
        and as_int(tcr_summary.get("blockedAdjacentPairCount")) == 0
        and as_int(tcr_summary.get("adjacentMotionPairCount")) == 0
        and as_int(tcr_summary.get("backToBackImportantPairCount")) == 0
        and as_int(tcr_summary.get("highImpactPurposeRunViolationCount")) == 0
        and as_int(tcr_summary.get("blockedCheckCount")) == 0
        and not transition_continuity_rehearsal.get("blockers"),
        {
            "status": transition_continuity_rehearsal.get("status"),
            "summary": tcr_summary,
            "blockers": transition_continuity_rehearsal.get("blockers") or [],
        },
    )

    add_gate(
        gates,
        "Pacing watchability proves reference-calibrated shot lengths, chapter breath, long-hold reduction, and short-clip readability",
        pacing_watchability.get("status") == "passed"
        and as_int(pw_summary.get("visualClipCount")) >= 3
        and as_float(pw_summary.get("averageVisualShotSeconds")) > 0
        and as_float(pw_summary.get("medianVisualShotSeconds")) > 0
        and as_int(pw_summary.get("blockedChapterCount")) == 0
        and as_int(pw_summary.get("longFlatShotCount")) == 0
        and as_int(pw_summary.get("veryLongShotCount")) == 0
        and as_int(pw_summary.get("longFlatRunMax")) <= 1
        and as_int(pw_summary.get("shortClipRunMax")) <= 2
        and as_int(pw_summary.get("breathingShotCount")) >= as_int(pw_summary.get("chapterCount"))
        and as_int(pw_summary.get("blockedCheckCount")) == 0
        and not pacing_watchability.get("blockers"),
        {
            "status": pacing_watchability.get("status"),
            "summary": pw_summary,
            "blockers": pacing_watchability.get("blockers") or [],
        },
    )

    add_gate(
        gates,
        "Scene flow arc proves each chapter reads like a travel sequence, not a landmark stack",
        scene_flow_arc.get("status") == "passed"
        and as_int(sfa_summary.get("visualClipCount")) >= 5
        and as_int(sfa_summary.get("chapterCount")) >= 1
        and as_int(sfa_summary.get("chaptersPassed")) == as_int(sfa_summary.get("chapterCount"))
        and as_int(sfa_summary.get("chaptersBlocked")) == 0
        and as_int(sfa_summary.get("blockedWindowCount")) == 0
        and as_int(sfa_summary.get("blockedHandoffCount")) == 0
        and as_int(sfa_summary.get("weakOrUnclassifiedClipCount")) == 0
        and as_int(sfa_summary.get("sameBeatRunMax")) <= 3
        and as_int(sfa_summary.get("payoffRunMax")) <= 2
        and sfa_summary.get("chapterStorySpineStatus") == "passed"
        and sfa_summary.get("shotFlowContinuityStatus") == "passed"
        and sfa_summary.get("timelineVarietyStatus") == "passed"
        and sfa_summary.get("referenceSceneGrammarStatus") == "passed"
        and sfa_summary.get("transitionSceneArcStatus") == "passed"
        and sfa_summary.get("transitionBreathingRoomStatus") == "passed"
        and as_int(sfa_summary.get("blockedCheckCount")) == 0
        and as_int(sfa_summary.get("blockerCount")) == 0
        and not scene_flow_arc.get("blockers"),
        {
            "status": scene_flow_arc.get("status"),
            "summary": sfa_summary,
            "blockers": scene_flow_arc.get("blockers") or [],
        },
    )

    add_gate(
        gates,
        "Final cut smoothness proves adjacent shots land cleanly instead of rough hard joins or effect-hidden jumps",
        final_cut_smoothness.get("status") == "passed"
        and as_int(fcs_summary.get("visualClipCount")) >= 4
        and as_int(fcs_summary.get("visualBoundaryCount")) >= 3
        and as_int(fcs_summary.get("blockedBoundaryCount")) == 0
        and as_int(fcs_summary.get("blockedImportantBoundaryCount")) == 0
        and as_int(fcs_summary.get("unsupportedMotionEffectCount")) == 0
        and as_int(fcs_summary.get("unstableLandingCount")) == 0
        and as_int(fcs_summary.get("highIntensityRunMax")) <= 1
        and as_int(fcs_summary.get("payoffJumpCount")) == 0
        and as_int(fcs_summary.get("hardCutJumpCount")) == 0
        and as_int(fcs_summary.get("weakBoundaryClipCount")) == 0
        and fcs_summary.get("finalBlueprintLineageStatus") == "passed"
        and fcs_summary.get("transitionBreathingRoomStatus") == "passed"
        and fcs_summary.get("sceneFlowArcStatus") == "passed"
        and fcs_summary.get("shotFlowContinuityStatus") == "passed"
        and fcs_summary.get("transitionVisualMatchStatus") == "passed"
        and fcs_summary.get("transitionChoreographyStatus") == "passed"
        and fcs_summary.get("transitionStoryboardStatus") == "passed"
        and as_int(fcs_summary.get("blockedCheckCount")) == 0
        and as_int(fcs_summary.get("blockerCount")) == 0
        and not final_cut_smoothness.get("blockers"),
        {
            "status": final_cut_smoothness.get("status"),
            "summary": fcs_summary,
            "blockers": final_cut_smoothness.get("blockers") or [],
        },
    )

    repair = load_json(package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json") or {}
    repair_summary = summary_of(repair)
    repair_closure = load_json(package_dir / "reference_repair_closure_audit.json") or {}
    closure_summary = summary_of(repair_closure)
    no_repairs = repair.get("status") == "ready_no_reference_style_repairs_needed"
    add_gate(
        gates,
        "Reference-style repair queue is either empty or P0-closed",
        repair.get("status") in {"ready_with_reference_style_repair_plan", "ready_no_reference_style_repairs_needed"}
        and repair_closure.get("status") in {"passed", "passed_with_evidence_warnings"}
        and (
            no_repairs
            or as_int(closure_summary.get("p0ClosedRowCount")) == as_int(closure_summary.get("p0RepairRowCount"))
        )
        and as_int(closure_summary.get("blockedRowCount")) == 0
        and not repair_closure.get("blockers"),
        {
            "repairStatus": repair.get("status"),
            "repairRowCount": repair_summary.get("repairRowCount"),
            "p0RepairRowCount": repair_summary.get("p0RepairRowCount"),
            "closureStatus": repair_closure.get("status"),
            "p0ClosedRowCount": closure_summary.get("p0ClosedRowCount"),
            "closureP0RepairRowCount": closure_summary.get("p0RepairRowCount"),
            "blockedRowCount": closure_summary.get("blockedRowCount"),
        },
    )

    repair_queue = load_json(package_dir / "unattended_repair_queue" / "unattended_repair_queue.json") or {}
    repair_queue_summary = summary_of(repair_queue)
    queue_status = repair_queue.get("status")
    queue_rows = as_int(repair_queue_summary.get("repairRowCount"))
    queue_actionable_rows = as_int(repair_queue_summary.get("actionableRepairRowCount"))
    add_gate(
        gates,
        "Unattended repair queue is empty or every blocker has an executable owner-script route",
        queue_status in {"ready_no_unattended_repairs_needed", "ready_with_unattended_repair_queue"}
        and queue_actionable_rows == queue_rows
        and as_int(repair_queue_summary.get("unactionableRepairRowCount")) == 0
        and as_int(repair_queue_summary.get("rowsWithOwnerScript")) == queue_rows
        and as_int(repair_queue_summary.get("rowsWithCommand")) == queue_rows
        and as_int(repair_queue_summary.get("rowsWithAcceptanceEvidence")) == queue_rows
        and as_int(repair_queue_summary.get("rowsWithForbiddenWorkaround")) == queue_rows
        and not repair_queue.get("blockers"),
        {
            "repairQueueStatus": queue_status,
            "repairQueueSummary": repair_queue_summary,
            "blockers": repair_queue.get("blockers") or [],
        },
    )

    preflight = load_json(package_dir / "resolve_blueprint_preflight.json") or {}
    clip_summary = preflight.get("clipSummary") if isinstance(preflight.get("clipSummary"), dict) else {}
    add_gate(
        gates,
        "Resolve blueprint preflight is ready before any apply",
        preflight.get("status") in {"ready", "ready_with_warnings"}
        and as_int(clip_summary.get("clipCount")) >= 1
        and as_int(clip_summary.get("missingSourceCount")) == 0
        and as_int(clip_summary.get("invalidRangeCount")) == 0
        and as_int(clip_summary.get("outOfBoundsCount")) == 0
        and as_int(clip_summary.get("overlapCount")) == 0
        and as_int(clip_summary.get("v1GapCount")) == 0
        and not preflight.get("blockers"),
        {
            "status": preflight.get("status"),
            "clipCount": clip_summary.get("clipCount"),
            "missingSourceCount": clip_summary.get("missingSourceCount"),
            "invalidRangeCount": clip_summary.get("invalidRangeCount"),
            "outOfBoundsCount": clip_summary.get("outOfBoundsCount"),
            "overlapCount": clip_summary.get("overlapCount"),
            "v1GapCount": clip_summary.get("v1GapCount"),
            "warnings": preflight.get("warnings") or [],
        },
    )

    add_gate(
        gates,
        "First-draft gate is non-destructive",
        True,
        {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    )

    blockers = [row["name"] for row in gates if row["status"] == "blocked"]
    warnings = [row["name"] for row in gates if row["status"] == "warning"]
    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "contract": "unattended_first_draft_contract",
        "status": status,
        "packageDir": str(package_dir),
        "gates": gates,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "passedGateCount": len([row for row in gates if row["status"] == "passed"]),
            "blockedGateCount": len(blockers),
            "warningGateCount": len(warnings),
            "requiredGateCount": len([row for row in gates if row["required"]]),
            "totalGateCount": len(gates),
            "repairQueueStatus": repair_queue.get("status"),
            "repairQueueRowCount": summary_of(repair_queue).get("repairRowCount"),
            "repairQueueActionableRowCount": summary_of(repair_queue).get("actionableRepairRowCount"),
        },
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
        "contractNotes": [
            "This gate proves first-draft handoff readiness before Resolve apply or final render.",
            "It does not replace final render verification, Resolve readback, final QA, V14 baseline, or forward testing.",
        ],
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Unattended First Draft Contract Audit",
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
        "## Gates",
    ]
    for row in report["gates"]:
        lines.extend(
            [
                "",
                f"### {row['name']}",
                f"- Status: `{row['status']}`",
                f"- Required: `{row['required']}`",
                "- Evidence:",
                "```json",
                json.dumps(row["evidence"], ensure_ascii=False, indent=2)[:4000],
                "```",
            ]
        )
    if report["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Safety", "", "```json", json.dumps(report["safety"], ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Notes"])
    lines.extend(f"- {item}" for item in report["contractNotes"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit unattended first-draft readiness before Resolve apply.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir)
    write_json(package_dir / "unattended_first_draft_contract_audit.json", report)
    write_markdown(package_dir / "unattended_first_draft_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "blockers": report["blockers"],
                    "warnings": report["warnings"],
                    "summary": report["summary"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
