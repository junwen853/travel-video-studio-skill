#!/usr/bin/env python3
"""Run the safe local Travel Video Studio delivery workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import default_app_dir


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
DEFAULT_APP_DIR = default_app_dir()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def truncate(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>..."


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def parse_step_json(step: dict[str, Any]) -> dict[str, Any] | None:
    stdout = step.get("stdout", "").strip()
    if not stdout.startswith("{"):
        return None
    try:
        payload = json.loads(stdout)
    except Exception:  # noqa: BLE001
        return None
    return payload if isinstance(payload, dict) else None


def summarize_project_state(status: dict[str, Any] | None) -> dict[str, Any] | None:
    if not status:
        return None
    artifacts = status.get("artifacts") if isinstance(status.get("artifacts"), dict) else {}
    media_index = artifacts.get("mediaIndex") if isinstance(artifacts.get("mediaIndex"), dict) else {}
    route_timeline = artifacts.get("routeTimeline") if isinstance(artifacts.get("routeTimeline"), dict) else {}
    confirmed_route = artifacts.get("confirmedRoute") if isinstance(artifacts.get("confirmedRoute"), dict) else {}
    return {
        "projectDir": status.get("projectDir"),
        "mediaVideoCount": media_index.get("videoCount"),
        "mediaDurationSeconds": media_index.get("totalDuration"),
        "routeChapterCount": route_timeline.get("chapterCount"),
        "confirmedRouteChapterCount": confirmed_route.get("chapterCount"),
        "blockingIssues": status.get("blockingIssues") or [],
        "warnings": status.get("warnings") or [],
        "recommendedNextAction": status.get("recommendedNextAction"),
        "routeMediaMismatch": status.get("routeMediaMismatch"),
    }


def summarize_resolve_api(status: dict[str, Any] | None) -> dict[str, Any] | None:
    if not status:
        return None
    install = status.get("install") if isinstance(status.get("install"), dict) else {}
    return {
        "appExists": install.get("appExists"),
        "scriptApiExists": install.get("scriptApiExists"),
        "scriptModuleExists": install.get("scriptModuleExists"),
        "scriptLibExists": install.get("scriptLibExists"),
        "processCount": len(status.get("processes") or []),
        "reachable": bool(status.get("reachable")),
        "productName": status.get("productName"),
        "version": status.get("version"),
        "currentProject": status.get("currentProject"),
        "currentTimeline": status.get("currentTimeline"),
        "currentPage": status.get("currentPage"),
        "error": status.get("error"),
    }


def summarize_render_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    gate = plan.get("gate") if isinstance(plan.get("gate"), dict) else {}
    settings = plan.get("renderSettings") if isinstance(plan.get("renderSettings"), dict) else {}
    return {
        "exists": True,
        "projectName": plan.get("projectName"),
        "timelineName": plan.get("timelineName"),
        "targetDir": plan.get("targetDir"),
        "customName": plan.get("customName"),
        "requestedFormat": plan.get("requestedFormat"),
        "requestedCodec": plan.get("requestedCodec"),
        "resolution": {
            "width": settings.get("FormatWidth"),
            "height": settings.get("FormatHeight"),
        },
        "fps": settings.get("FrameRate"),
        "videoQuality": settings.get("VideoQuality"),
        "exportsVideo": settings.get("ExportVideo"),
        "exportsAudio": settings.get("ExportAudio"),
        "gateAllowed": gate.get("allowed"),
        "gateBlockerCount": len(gate.get("blockers") or []),
        "queued": bool(plan.get("queued")),
        "started": bool(plan.get("started")),
    }


def summarize_route_decision_sheet(sheet: dict[str, Any] | None) -> dict[str, Any] | None:
    if not sheet:
        return None
    rows = sheet.get("decisionRows") if isinstance(sheet.get("decisionRows"), list) else []
    return {
        "exists": True,
        "status": sheet.get("status"),
        "decisionSheetJson": sheet.get("decisionSheetJson"),
        "decisionSheetMarkdown": sheet.get("decisionSheetMarkdown"),
        "rowCount": len(rows),
        "suggestedConfirmOrCorrect": sum(
            1 for row in rows if row.get("suggestedDecision") in {"confirmed", "corrected", "split", "merge"}
        ),
        "filledDecisionCount": sum(1 for row in rows if row.get("reviewDecision")),
        "regionMismatch": (sheet.get("projectRegionReview") or {}).get("mismatch"),
        "blockerCount": len(sheet.get("blockers") or []),
    }


def summarize_asset_reconciliation(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "applied": bool(report.get("applied")),
        "decisionRowsFilled": summary.get("decisionRowsFilled"),
        "verifiedBgmOrStock": summary.get("verifiedBgmOrStock"),
        "unverifiedBgmOrStock": summary.get("unverifiedBgmOrStock"),
        "blockerCount": len(report.get("blockers") or []),
    }


def summarize_bgm_sourcing(brief: dict[str, Any] | None) -> dict[str, Any] | None:
    if not brief:
        return None
    return {
        "exists": True,
        "status": brief.get("status"),
        "verifiedBgmCount": len(brief.get("verifiedBgmItems") or []),
        "chapterRows": len(brief.get("chapterBgmRows") or []),
        "sectionPlanCount": len(brief.get("sectionPlan") or []),
        "targetDurationSeconds": brief.get("targetDurationSeconds"),
    }


def summarize_footage_select_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "inputSource": summary.get("inputSource"),
        "sourceVideoCount": summary.get("sourceVideoCount"),
        "candidateVideoCount": summary.get("candidateVideoCount"),
        "heroCandidateCount": summary.get("heroCandidateCount"),
        "mainStoryCandidateCount": summary.get("mainStoryCandidateCount"),
        "textureBridgeCandidateCount": summary.get("textureBridgeCandidateCount"),
        "repairOrRejectCount": summary.get("repairOrRejectCount"),
        "orientationRepairCandidateCount": summary.get("orientationRepairCandidateCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "chaptersNeedingCoverage": summary.get("chaptersNeedingCoverage"),
        "averageSelectionScore": summary.get("averageSelectionScore"),
    }


def summarize_raw_intake_completeness(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "projectDir": report.get("projectDir"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_opening_story_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "openingWindowSeconds": summary.get("openingWindowSeconds"),
        "openingVideoClipCount": summary.get("openingVideoClipCount"),
        "openingCoverageRatio": summary.get("openingCoverageRatio"),
        "beatRowCount": summary.get("beatRowCount"),
        "rowsWithEvidence": summary.get("rowsWithEvidence"),
        "missingBeatCount": summary.get("missingBeatCount"),
        "missingBeatIds": summary.get("missingBeatIds"),
        "destinationProofClipCount": summary.get("destinationProofClipCount"),
        "routeArrivalClipCount": summary.get("routeArrivalClipCount"),
        "livedInTextureClipCount": summary.get("livedInTextureClipCount"),
        "titleClipCount": summary.get("titleClipCount"),
        "weakTitleHitCount": summary.get("weakTitleHitCount"),
        "firstHandoffClipCount": summary.get("firstHandoffClipCount"),
    }


def summarize_chapter_arc_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
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
    }


def summarize_bgm_selection_package(package: dict[str, Any] | None) -> dict[str, Any] | None:
    if not package:
        return None
    summary = package.get("summary") if isinstance(package.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": package.get("status"),
        "candidateCount": summary.get("candidateCount"),
        "materializedBedCount": summary.get("materializedBedCount"),
        "verifiedMaterializedBedCount": summary.get("verifiedMaterializedBedCount"),
        "readySourceTrackCount": summary.get("readySourceTrackCount"),
        "blueprintBgmAssetCount": summary.get("blueprintBgmAssetCount"),
        "bgmCueCount": summary.get("bgmCueCount"),
        "buildCommandAvailable": summary.get("buildCommandAvailable"),
    }


def summarize_bgm_phrase_blueprint(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "baseBlueprintKind": inputs.get("baseBlueprintKind"),
        "selectedBgmBedCount": summary.get("selectedBgmBedCount"),
        "phraseRowCount": summary.get("phraseRowCount"),
        "sectionRowCount": summary.get("sectionRowCount"),
        "transitionCueCount": summary.get("transitionCueCount"),
        "transitionsWithPhraseCue": summary.get("transitionsWithPhraseCue"),
        "candidateTransitionCount": summary.get("candidateTransitionCount"),
        "clipAnnotationCount": summary.get("clipAnnotationCount"),
        "sourceAudioRiskCount": summary.get("sourceAudioRiskCount"),
        "candidateBlueprint": outputs.get("candidateBlueprint"),
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
    }


def summarize_transition_bridge_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "chapterCount": summary.get("chapterCount"),
        "boundaryRowCount": summary.get("boundaryRowCount"),
        "boundariesWithEvidence": summary.get("boundariesWithEvidence"),
        "missingBoundaryCount": summary.get("missingBoundaryCount"),
        "existingTransitionPlanCount": summary.get("existingTransitionPlanCount"),
        "existingBridgeClipCount": summary.get("existingBridgeClipCount"),
        "sectionPlanCount": len(plan.get("sectionPlan") or []),
    }


def summarize_visual_establishing_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "chapterCount": summary.get("chapterCount"),
        "establishingRowCount": summary.get("establishingRowCount"),
        "rowsWithEvidence": summary.get("rowsWithEvidence"),
        "missingEstablishingCount": summary.get("missingEstablishingCount"),
        "rowsWithTitleTypographyEvidence": summary.get("rowsWithTitleTypographyEvidence"),
        "verifiedAerialCount": summary.get("verifiedAerialCount"),
        "stockAerialClosureStatus": summary.get("stockAerialClosureStatus"),
    }


def summarize_effect_motion_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "effectPlanCount": summary.get("effectPlanCount"),
        "effectRowCount": summary.get("effectRowCount"),
        "rowsWithSourceEvidence": summary.get("rowsWithSourceEvidence"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "forbiddenEffectHitCount": summary.get("forbiddenEffectHitCount"),
        "titleMotionRowCount": summary.get("titleMotionRowCount"),
        "transitionMotionRowCount": summary.get("transitionMotionRowCount"),
    }


def summarize_effect_motion_blueprint(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "baseBlueprintKind": inputs.get("baseBlueprintKind"),
        "effectMotionPlanStatus": inputs.get("effectMotionPlanStatus"),
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
        "candidateBlueprint": outputs.get("candidateBlueprint"),
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
    }


def summarize_audio_scene_policy_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "sceneWindowCount": summary.get("sceneWindowCount"),
        "bgmCoveredWindowCount": summary.get("bgmCoveredWindowCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "sourceAudioRiskCount": summary.get("sourceAudioRiskCount"),
        "readyBgmCueCount": summary.get("readyBgmCueCount"),
        "voiceoverDisabled": summary.get("voiceoverDisabled"),
        "sourceAudioDisabled": summary.get("sourceAudioDisabled"),
        "feedbackWindowCount": summary.get("feedbackWindowCount"),
        "knownFeedbackProbeCount": summary.get("knownFeedbackProbeCount"),
    }


def summarize_feedback_regression_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "probeCount": summary.get("probeCount"),
        "openingProbeCount": summary.get("openingProbeCount"),
        "sevenMinuteProbeCount": summary.get("sevenMinuteProbeCount"),
        "audioPolicyProbeCount": summary.get("audioPolicyProbeCount"),
        "feedbackTimestampsCsv": summary.get("feedbackTimestampsCsv"),
        "audioPolicyFeedbackTimestampsCsv": summary.get("audioPolicyFeedbackTimestampsCsv"),
    }


def summarize_reference_batch_profile(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    pacing = plan.get("pacingProfile") if isinstance(plan.get("pacingProfile"), dict) else {}
    audio = plan.get("audioProfile") if isinstance(plan.get("audioProfile"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "failedReferenceCount": summary.get("failedReferenceCount"),
        "totalDurationMinutes": summary.get("totalDurationMinutes"),
        "estimatedShotCount": pacing.get("estimatedShotCount"),
        "averageShotLengthSeconds": pacing.get("averageShotLengthSeconds"),
        "medianShotLengthSeconds": pacing.get("medianShotLengthSeconds"),
        "audioMeanVolumeDb": audio.get("meanVolumeDb"),
        "sampleFrameCount": summary.get("sampleFrameCount"),
    }


def summarize_edit_rhythm_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "primaryVisualShotCount": summary.get("primaryVisualShotCount"),
        "recommendedMinimumShotCount": summary.get("recommendedMinimumShotCount"),
        "estimatedAdditionalCutawayBeats": summary.get("estimatedAdditionalCutawayBeats"),
        "averageShotSeconds": summary.get("averageShotSeconds"),
        "medianShotSeconds": summary.get("medianShotSeconds"),
        "rhythmRiskCount": summary.get("rhythmRiskCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "chaptersNeedingVarietyOrRetime": summary.get("chaptersNeedingVarietyOrRetime"),
        "referenceReady": summary.get("referenceReady"),
    }


def summarize_creator_cut_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "primaryVisualShotCount": summary.get("primaryVisualShotCount"),
        "creatorDecisionRowCount": summary.get("creatorDecisionRowCount"),
        "rejectOrUtilityCount": summary.get("rejectOrUtilityCount"),
        "routeBridgeCandidateCount": summary.get("routeBridgeCandidateCount"),
        "motivatedRotationCandidateCount": summary.get("motivatedRotationCandidateCount"),
        "chaptersNeedingCreatorCoverage": summary.get("chaptersNeedingCreatorCoverage"),
    }


def summarize_transition_grammar_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "visualClipCount": summary.get("visualClipCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "rowsNeedingBridgeInsert": summary.get("rowsNeedingBridgeInsert"),
        "physicalBridgeEvidenceCount": summary.get("physicalBridgeEvidenceCount"),
        "motivatedMotionEffectCandidateCount": summary.get("motivatedMotionEffectCandidateCount"),
        "recommendedStyleCounts": summary.get("recommendedStyleCounts"),
    }


def summarize_transition_execution_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "rowsReadyForResolveExecution": summary.get("rowsReadyForResolveExecution"),
        "rowsWithExecutionRecipe": summary.get("rowsWithExecutionRecipe"),
        "bridgeInsertBlockedRowCount": summary.get("bridgeInsertBlockedRowCount"),
        "motionStyleRowCount": summary.get("motionStyleRowCount"),
        "motionStyleRowsWithEvidence": summary.get("motionStyleRowsWithEvidence"),
        "forbiddenRecipeHitCount": summary.get("forbiddenRecipeHitCount"),
        "executionStyleCounts": summary.get("executionStyleCounts"),
    }


def summarize_transition_execution_blueprint(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "baseBlueprintKind": inputs.get("baseBlueprintKind"),
        "executionRowCount": summary.get("executionRowCount"),
        "materializedTransitionCount": summary.get("materializedTransitionCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "rowsMissingClipMatch": summary.get("rowsMissingClipMatch"),
        "motionEffectRowCount": summary.get("motionEffectRowCount"),
        "motionEffectRowsWithEvidence": summary.get("motionEffectRowsWithEvidence"),
        "bridgeRequiredRowCount": summary.get("bridgeRequiredRowCount"),
        "bridgeSatisfiedRowCount": summary.get("bridgeSatisfiedRowCount"),
        "candidateTransitionCount": summary.get("candidateTransitionCount"),
        "candidateBlueprint": outputs.get("candidateBlueprint"),
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
    }


def summarize_transition_motif_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
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
    }


def summarize_bridge_sequence_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
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
    }


def summarize_bridge_sequence_blueprint(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "sequenceRowCount": summary.get("sequenceRowCount"),
        "materializedRowCount": summary.get("materializedRowCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "insertedBeatClipCount": summary.get("insertedBeatClipCount"),
        "missingBeatRowCount": summary.get("missingBeatRowCount"),
        "missingBeatCount": summary.get("missingBeatCount"),
        "overlayTrackIndex": summary.get("overlayTrackIndex"),
        "candidateClipCount": summary.get("candidateClipCount"),
        "candidateBlueprint": outputs.get("candidateBlueprint"),
        "activeBlueprintUpdated": outputs.get("activeBlueprintUpdated"),
    }


def summarize_bridge_sequence_application_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "requiredSequenceRowCount": summary.get("requiredSequenceRowCount"),
        "passedSequenceRowCount": summary.get("passedSequenceRowCount"),
        "blockedSequenceRowCount": summary.get("blockedSequenceRowCount"),
        "expectedBeatClipCount": summary.get("expectedBeatClipCount"),
        "appliedBeatClipCount": summary.get("appliedBeatClipCount"),
        "missingBeatClipCount": summary.get("missingBeatClipCount"),
        "finalBridgeInsertClipCount": summary.get("finalBridgeInsertClipCount"),
        "sourceAudioLeakClipCount": summary.get("sourceAudioLeakClipCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_final_blueprint_lineage_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "finalBlueprintKind": inputs.get("finalBlueprintKind"),
        "finalBlueprintInsidePackage": inputs.get("finalBlueprintInsidePackage"),
        "readyStageCount": summary.get("readyStageCount"),
        "passedStageCount": summary.get("passedStageCount"),
        "blockedReadyStageCount": summary.get("blockedReadyStageCount"),
        "finalPlanKeyCount": summary.get("finalPlanKeyCount"),
        "requiredMinimumReadyStages": summary.get("requiredMinimumReadyStages"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_final_source_usage_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "footageSelectStatus": inputs.get("footageSelectStatus"),
        "rawSourceClipCount": summary.get("rawSourceClipCount"),
        "matchedRawSourceClipCount": summary.get("matchedRawSourceClipCount"),
        "unmatchedRawSourceClipCount": summary.get("unmatchedRawSourceClipCount"),
        "selectedCandidateClipCount": summary.get("selectedCandidateClipCount"),
        "utilityClipCount": summary.get("utilityClipCount"),
        "rejectOrRepairActiveClipCount": summary.get("rejectOrRepairActiveClipCount"),
        "sameSourceRunMax": summary.get("sameSourceRunMax"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_rhythm_recut_blueprint(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    inputs = plan.get("inputs") if isinstance(plan.get("inputs"), dict) else {}
    outputs = plan.get("outputs") if isinstance(plan.get("outputs"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "baseBlueprintKind": inputs.get("baseBlueprintKind"),
        "candidateBlueprint": outputs.get("candidateBlueprint"),
        "longEditableClipCount": summary.get("longEditableClipCount"),
        "splitSourceClipCount": summary.get("splitSourceClipCount"),
        "cutawayInsertCount": summary.get("cutawayInsertCount"),
        "averagePrimaryShotBeforeSeconds": summary.get("averagePrimaryShotBeforeSeconds"),
        "averagePrimaryShotAfterSeconds": summary.get("averagePrimaryShotAfterSeconds"),
        "longShotRiskBefore": summary.get("longShotRiskBefore"),
        "longShotRiskAfter": summary.get("longShotRiskAfter"),
        "durationDeltaSeconds": summary.get("durationDeltaSeconds"),
        "bgmPhrasePlanPreserved": summary.get("bgmPhrasePlanPreserved"),
        "bgmPhraseCandidateCount": summary.get("bgmPhraseCandidateCount"),
        "bgmPhraseClipAnnotationCount": summary.get("bgmPhraseClipAnnotationCount"),
        "bgmPhraseTransitionCueCount": summary.get("bgmPhraseTransitionCueCount"),
    }


def summarize_transition_polish_blueprint(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "baseBlueprintKind": inputs.get("baseBlueprintKind"),
        "candidateBlueprint": outputs.get("candidateBlueprint"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "polishedTransitionCount": summary.get("polishedTransitionCount"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "rowsWithBgmPhraseCue": summary.get("rowsWithBgmPhraseCue"),
        "rowsWithBgmHit": summary.get("rowsWithBgmHit"),
        "rowsWithTitleSubtitleAvoidance": summary.get("rowsWithTitleSubtitleAvoidance"),
        "motionPolishRowCount": summary.get("motionPolishRowCount"),
        "motionPolishRowsWithEvidence": summary.get("motionPolishRowsWithEvidence"),
        "downgradedMotionRowCount": summary.get("downgradedMotionRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "clipAnnotationCount": summary.get("clipAnnotationCount"),
        "markerCount": summary.get("markerCount"),
        "candidateBgmPhraseCount": summary.get("candidateBgmPhraseCount"),
    }


def summarize_transition_quality_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "transitionCoverageRatio": summary.get("transitionCoverageRatio"),
        "rowsWithBgmHit": summary.get("rowsWithBgmHit"),
        "rowsTitleSafe": summary.get("rowsTitleSafe"),
        "bgmOnlyAudioRows": summary.get("bgmOnlyAudioRows"),
        "motionRowCount": summary.get("motionRowCount"),
        "motionRowsWithEvidence": summary.get("motionRowsWithEvidence"),
        "craftedTransitionCount": summary.get("craftedTransitionCount"),
        "minimumCraftedTransitionCount": summary.get("minimumCraftedTransitionCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_shot_transition_boundary_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_motivation_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "motivatedBoundaryCount": summary.get("motivatedBoundaryCount"),
        "pairMatchedBoundaryCount": summary.get("pairMatchedBoundaryCount"),
        "bgmMotivatedBoundaryCount": summary.get("bgmMotivatedBoundaryCount"),
        "bridgeMotivatedBoundaryCount": summary.get("bridgeMotivatedBoundaryCount"),
        "motionMotivatedBoundaryCount": summary.get("motionMotivatedBoundaryCount"),
        "titleSafeMotivatedBoundaryCount": summary.get("titleSafeMotivatedBoundaryCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "forbiddenHitCount": summary.get("forbiddenHitCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_pair_continuity_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "passedBoundaryCount": summary.get("passedBoundaryCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "pairContinuityPayloadCount": summary.get("pairContinuityPayloadCount"),
        "strongPairFitCount": summary.get("strongPairFitCount"),
        "acceptablePairFitCount": summary.get("acceptablePairFitCount"),
        "weakPairFitCount": summary.get("weakPairFitCount"),
        "styleAllowedBoundaryCount": summary.get("styleAllowedBoundaryCount"),
        "pairMatchedBoundaryCount": summary.get("pairMatchedBoundaryCount"),
        "motionBoundaryCount": summary.get("motionBoundaryCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_execution_readiness_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "passedBoundaryCount": summary.get("passedBoundaryCount"),
        "blockedBoundaryCount": summary.get("blockedBoundaryCount"),
        "recipeReadyBoundaryCount": summary.get("recipeReadyBoundaryCount"),
        "bgmHitBoundaryCount": summary.get("bgmHitBoundaryCount"),
        "titleSafeBoundaryCount": summary.get("titleSafeBoundaryCount"),
        "decisionFieldBoundaryCount": summary.get("decisionFieldBoundaryCount"),
        "pairReadyBoundaryCount": summary.get("pairReadyBoundaryCount"),
        "handleReadyBoundaryCount": summary.get("handleReadyBoundaryCount"),
        "motionBoundaryCount": summary.get("motionBoundaryCount"),
        "motionReadyBoundaryCount": summary.get("motionReadyBoundaryCount"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "maxTransitionDurationSeconds": summary.get("maxTransitionDurationSeconds"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_polish_application_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "finalBlueprintKind": inputs.get("finalBlueprintKind"),
        "finalBlueprintInsidePackage": inputs.get("finalBlueprintInsidePackage"),
        "sourcePolishRowCount": summary.get("sourcePolishRowCount"),
        "finalTransitionPolishCandidateCount": summary.get("finalTransitionPolishCandidateCount"),
        "finalTransitionRowCount": summary.get("finalTransitionRowCount"),
        "auditedPolishRowCount": summary.get("auditedPolishRowCount"),
        "passedPolishRowCount": summary.get("passedPolishRowCount"),
        "blockedPolishRowCount": summary.get("blockedPolishRowCount"),
        "recipeReadyRowCount": summary.get("recipeReadyRowCount"),
        "bgmHitRowCount": summary.get("bgmHitRowCount"),
        "titleSafeRowCount": summary.get("titleSafeRowCount"),
        "pairReadyRowCount": summary.get("pairReadyRowCount"),
        "clipAnnotationRowCount": summary.get("clipAnnotationRowCount"),
        "markerRowCount": summary.get("markerRowCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_creator_cut_application_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "visualClipCount": summary.get("visualClipCount"),
        "matchedCreatorRowCount": summary.get("matchedCreatorRowCount"),
        "blockedClipCount": summary.get("blockedClipCount"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "rejectActiveClipCount": summary.get("rejectActiveClipCount"),
        "utilityActiveClipCount": summary.get("utilityActiveClipCount"),
        "sameSourceRunMax": summary.get("sameSourceRunMax"),
        "sameFunctionRunMax": summary.get("sameFunctionRunMax"),
        "globalFunctionGroupCount": summary.get("globalFunctionGroupCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_reference_scene_grammar_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "referenceProfileAvailable": summary.get("referenceProfileAvailable"),
        "visualClipCount": summary.get("visualClipCount"),
        "openingFunctionCount": summary.get("openingFunctionCount"),
        "openingFunctions": summary.get("openingFunctions"),
        "chapterCount": summary.get("chapterCount"),
        "chaptersPassed": summary.get("chaptersPassed"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "endingFunctions": summary.get("endingFunctions"),
        "endingAftertasteFound": summary.get("endingAftertasteFound"),
        "pairContinuityStatus": summary.get("pairContinuityStatus"),
        "weakPairFitCount": summary.get("weakPairFitCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_unattended_first_draft_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "passedGateCount": summary.get("passedGateCount"),
        "blockedGateCount": summary.get("blockedGateCount"),
        "warningGateCount": summary.get("warningGateCount"),
        "requiredGateCount": summary.get("requiredGateCount"),
        "totalGateCount": summary.get("totalGateCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_reference_style_repair_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    targets = plan.get("referenceTargets") if isinstance(plan.get("referenceTargets"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "repairRowCount": summary.get("repairRowCount"),
        "p0RepairRowCount": summary.get("p0RepairRowCount"),
        "areaCounts": summary.get("areaCounts"),
        "rowsWithDecisionFields": summary.get("rowsWithDecisionFields"),
        "safeNoWriteRows": summary.get("safeNoWriteRows"),
        "referenceProfileAvailable": summary.get("referenceProfileAvailable"),
        "referenceAverageShotLengthSeconds": targets.get("averageShotLengthSeconds"),
        "referenceMedianShotLengthSeconds": targets.get("medianShotLengthSeconds"),
    }


def summarize_reference_repair_closure(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "repairRowCount": summary.get("repairRowCount"),
        "p0RepairRowCount": summary.get("p0RepairRowCount"),
        "closedRowCount": summary.get("closedRowCount"),
        "p0ClosedRowCount": summary.get("p0ClosedRowCount"),
        "needsEditorEvidenceRowCount": summary.get("needsEditorEvidenceRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_rhythm_recut_apply_package(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    preflight = plan.get("preflight") if isinstance(plan.get("preflight"), dict) else {}
    safety = plan.get("safety") if isinstance(plan.get("safety"), dict) else {}
    source_summary = summary.get("sourceCandidateSummary") if isinstance(summary.get("sourceCandidateSummary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "outputPackage": plan.get("outputPackage"),
        "activeBlueprint": plan.get("activeBlueprint"),
        "projectName": plan.get("projectName"),
        "timelineName": plan.get("timelineName"),
        "sourceCandidateStatus": summary.get("sourceCandidateStatus"),
        "activeClipCount": summary.get("activeClipCount"),
        "cutawayInsertCount": source_summary.get("cutawayInsertCount"),
        "averagePrimaryShotAfterSeconds": source_summary.get("averagePrimaryShotAfterSeconds"),
        "longShotRiskAfter": source_summary.get("longShotRiskAfter"),
        "preflightStatus": preflight.get("status"),
        "preflightBlockerCount": preflight.get("blockerCount"),
        "copiedFinalRenderEvidence": summary.get("copiedFinalRenderEvidence"),
        "writesResolve": safety.get("writesResolve"),
    }


def summarize_caption_story_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "subtitleCueCount": summary.get("subtitleCueCount"),
        "targetCueCount": summary.get("targetCueCount"),
        "cuesPerMinute": summary.get("cuesPerMinute"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "rowsMeetingTarget": summary.get("rowsMeetingTarget"),
        "maxGapSeconds": summary.get("maxGapSeconds"),
        "titleZoneCount": summary.get("titleZoneCount"),
        "textOnlyNarrationExport": summary.get("textOnlyNarrationExport"),
    }


def summarize_audience_caption_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    return {
        "exists": True,
        "status": report.get("status"),
        "checkedFileCount": report.get("checkedFileCount"),
        "violationCount": report.get("violationCount"),
        "checkedFiles": report.get("checkedFiles") or [],
    }


def summarize_title_typography_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "titleRowCount": summary.get("titleRowCount"),
        "cleanRowCount": summary.get("cleanRowCount"),
        "openingRowCount": summary.get("openingRowCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "endingRowCount": summary.get("endingRowCount"),
        "fontVerified": summary.get("fontVerified"),
        "titleZoneMode": summary.get("titleZoneMode"),
        "titleContractStatus": summary.get("titleContractStatus"),
    }


def summarize_cover_title_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "mainTitle": summary.get("mainTitle"),
        "mainTitleUnitCount": summary.get("mainTitleUnitCount"),
        "secondaryTitle": summary.get("secondaryTitle"),
        "secondaryTitlePresent": summary.get("secondaryTitlePresent"),
        "backgroundVideoReady": summary.get("backgroundVideoReady"),
        "backgroundRecognitionHint": summary.get("backgroundRecognitionHint"),
        "clean16x9Deliverable": summary.get("clean16x9Deliverable"),
        "forbiddenHitCount": summary.get("forbiddenHitCount"),
        "blockers": report.get("blockers") or [],
    }


def summarize_route_decision_application(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "applied": bool(report.get("applied")),
        "wouldApply": bool(report.get("wouldApply")),
        "rowCount": summary.get("rowCount"),
        "filledDecisionCount": summary.get("filledDecisionCount"),
        "regionMismatch": summary.get("regionMismatch"),
        "blockerCount": len(report.get("blockers") or []),
    }


def summarize_resolve_apply_contract(contract: dict[str, Any] | None) -> dict[str, Any] | None:
    if not contract:
        return None
    clip_plan = contract.get("clipPlan") if isinstance(contract.get("clipPlan"), dict) else {}
    return {
        "exists": True,
        "status": contract.get("status"),
        "projectName": contract.get("projectName"),
        "timelineName": contract.get("timelineName"),
        "clipCount": clip_plan.get("clipCount"),
        "sourceFileCount": clip_plan.get("sourceFileCount"),
        "coverageRatio": contract.get("coverageRatio"),
        "blockerCount": len(contract.get("blockers") or []),
        "requiresApproval": (contract.get("approval") or {}).get("required"),
    }


def summarize_blueprint_preflight(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    clip_summary = report.get("clipSummary") if isinstance(report.get("clipSummary"), dict) else {}
    enrichment = report.get("enrichmentSummary") if isinstance(report.get("enrichmentSummary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "clipCount": clip_summary.get("clipCount"),
        "sourceFileCount": clip_summary.get("sourceFileCount"),
        "sourceAudioClipCount": clip_summary.get("sourceAudioClipCount"),
        "titleCardCount": clip_summary.get("titleCardCount"),
        "missingSourceCount": clip_summary.get("missingSourceCount"),
        "invalidRangeCount": clip_summary.get("invalidRangeCount"),
        "outOfBoundsCount": clip_summary.get("outOfBoundsCount"),
        "overlapCount": clip_summary.get("overlapCount"),
        "v1GapCount": clip_summary.get("v1GapCount"),
        "subtitleCueCount": enrichment.get("subtitleCueCount"),
        "bgmCueCount": enrichment.get("bgmCueCount"),
        "stockPlaceholderCount": enrichment.get("stockPlaceholderCount"),
        "transitionCount": enrichment.get("transitionCount"),
        "timelineMarkerCount": enrichment.get("timelineMarkerCount"),
        "voiceoverStatus": enrichment.get("voiceoverStatus"),
        "blockerCount": len(report.get("blockers") or []),
        "warningCount": len(report.get("warnings") or []),
    }


def run_step(step_id: str, command: list[str], ok_codes: set[int] | None = None) -> dict[str, Any]:
    ok_codes = ok_codes or {0}
    started = datetime.now().isoformat(timespec="seconds")
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    ended = datetime.now().isoformat(timespec="seconds")
    return {
        "id": step_id,
        "command": command,
        "startedAt": started,
        "endedAt": ended,
        "returnCode": result.returncode,
        "ok": result.returncode in ok_codes,
        "stdout": truncate(result.stdout),
        "stderr": truncate(result.stderr),
    }


def discover_output_dir(build_step: dict[str, Any], explicit_output_dir: str | None) -> Path:
    if explicit_output_dir:
        return Path(explicit_output_dir).expanduser().resolve()
    for line in build_step.get("stdout", "").splitlines():
        if line.startswith("Output: "):
            return Path(line.split("Output: ", 1)[1].strip()).expanduser().resolve()
    raise SystemExit("Unable to determine package output directory from build_delivery_package output.")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Delivery Workflow Run",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report.get('packageDir')}`",
        f"Started: {report['startedAt']}",
        f"Ended: {report['endedAt']}",
        "",
        "## Safety",
    ]
    for key, value in report["safety"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Steps"])
    for step in report["steps"]:
        lines.append(f"- {step['id']}: rc `{step['returnCode']}`, ok `{step['ok']}`")
    if report.get("projectStateSummary"):
        project = report["projectStateSummary"]
        lines.extend(
            [
                "",
                "## Project State",
                f"- Media videos: {project.get('mediaVideoCount')}",
                f"- Media duration: {project.get('mediaDurationSeconds')}s",
                f"- Project blockers: {len(project.get('blockingIssues') or [])}",
                f"- Project warnings: {len(project.get('warnings') or [])}",
            ]
        )
    if report.get("resolveApiSummary"):
        resolve = report["resolveApiSummary"]
        lines.extend(
            [
                "",
                "## Resolve API",
                f"- App installed: `{resolve.get('appExists')}`",
                f"- Reachable: `{resolve.get('reachable')}`",
                f"- Product: {resolve.get('productName')} {resolve.get('version')}",
                f"- Current project: {resolve.get('currentProject')}",
            ]
        )
    if report.get("routeDecisionSummary"):
        route = report["routeDecisionSummary"]
        lines.extend(
            [
                "",
                "## Route Decision Sheet",
                f"- Exists: `{route.get('exists')}`",
                f"- Rows: {route.get('rowCount')}",
                f"- Suggested confirm/correct: {route.get('suggestedConfirmOrCorrect')}",
                f"- Filled decisions: {route.get('filledDecisionCount')}",
                f"- Region mismatch: `{route.get('regionMismatch')}`",
            ]
        )
    if report.get("routeDecisionApplicationSummary"):
        route_app = report["routeDecisionApplicationSummary"]
        lines.extend(
            [
                "",
                "## Route Decision Application",
                f"- Exists: `{route_app.get('exists')}`",
                f"- Status: `{route_app.get('status')}`",
                f"- Would apply: `{route_app.get('wouldApply')}`",
                f"- Applied: `{route_app.get('applied')}`",
                f"- Filled decisions: {route_app.get('filledDecisionCount')}",
            ]
        )
    if report.get("footageSelectSummary"):
        select = report["footageSelectSummary"]
        lines.extend(
            [
                "",
                "## Footage Select Plan",
                f"- Exists: `{select.get('exists')}`",
                f"- Status: `{select.get('status')}`",
                f"- Input source: `{select.get('inputSource')}`",
                f"- Source videos: {select.get('sourceVideoCount')}",
                f"- Candidates: {select.get('candidateVideoCount')}",
                f"- Hero/main/bridge: {select.get('heroCandidateCount')} / {select.get('mainStoryCandidateCount')} / {select.get('textureBridgeCandidateCount')}",
                f"- Repair or reject: {select.get('repairOrRejectCount')}",
            ]
        )
    if report.get("rawIntakeCompletenessSummary"):
        intake = report["rawIntakeCompletenessSummary"]
        lines.extend(
            [
                "",
                "## Raw Intake Completeness",
                f"- Status: `{intake.get('status')}`",
                f"- Indexed/filesystem/active videos: {intake.get('indexedVideoCount')} / {intake.get('filesystemVideoCount')} / {intake.get('activeSourceVideoCount')}",
                f"- Large source: `{intake.get('largeSource')}`; size GB: {intake.get('sourceSizeGB')}",
                f"- Recognition coverage: {intake.get('recognitionCoverageRatio')}",
                f"- Route missing/duplicate: {intake.get('routeMissingVideoCount')} / {intake.get('routeDuplicateVideoCount')}",
                f"- Footage select missing: {intake.get('footageSelectMissingVideoCount')}",
                f"- Active derived/stale artifacts: {intake.get('activeDerivedVideoCount')} / {intake.get('staleArtifactCount')}",
            ]
        )
    if report.get("openingStorySummary"):
        opening = report["openingStorySummary"]
        lines.extend(
            [
                "",
                "## Opening Story Plan",
                f"- Exists: `{opening.get('exists')}`",
                f"- Status: `{opening.get('status')}`",
                f"- Window: {opening.get('openingWindowSeconds')}s",
                f"- Opening clips: {opening.get('openingVideoClipCount')}",
                f"- Coverage ratio: {opening.get('openingCoverageRatio')}",
                f"- Beat evidence: {opening.get('rowsWithEvidence')} / {opening.get('beatRowCount')}",
                f"- Missing beats: {opening.get('missingBeatCount')} `{opening.get('missingBeatIds')}`",
                f"- Destination/route/lived/title/handoff clips: {opening.get('destinationProofClipCount')} / {opening.get('routeArrivalClipCount')} / {opening.get('livedInTextureClipCount')} / {opening.get('titleClipCount')} / {opening.get('firstHandoffClipCount')}",
                f"- Weak title hits: {opening.get('weakTitleHitCount')}",
            ]
        )
    if report.get("assetDecisionSummary"):
        asset = report["assetDecisionSummary"]
        lines.extend(
            [
                "",
                "## Asset Decision Reconciliation",
                f"- Exists: `{asset.get('exists')}`",
                f"- Status: `{asset.get('status')}`",
                f"- Applied: `{asset.get('applied')}`",
                f"- Filled decisions: {asset.get('decisionRowsFilled')}",
                f"- Unverified BGM/stock: {asset.get('unverifiedBgmOrStock')}",
            ]
        )
    if report.get("bgmSourcingSummary"):
        bgm = report["bgmSourcingSummary"]
        lines.extend(
            [
                "",
                "## BGM Sourcing Brief",
                f"- Exists: `{bgm.get('exists')}`",
                f"- Status: `{bgm.get('status')}`",
                f"- Verified BGM rows: {bgm.get('verifiedBgmCount')}",
                f"- Chapter BGM rows: {bgm.get('chapterRows')}",
                f"- Section plans: {bgm.get('sectionPlanCount')}",
            ]
        )
    if report.get("bgmSelectionSummary"):
        bgm_selection = report["bgmSelectionSummary"]
        lines.extend(
            [
                "",
                "## BGM Selection Package",
                f"- Exists: `{bgm_selection.get('exists')}`",
                f"- Status: `{bgm_selection.get('status')}`",
                f"- Candidates: {bgm_selection.get('candidateCount')}",
                f"- Verified materialized beds: {bgm_selection.get('verifiedMaterializedBedCount')}",
                f"- Ready source tracks: {bgm_selection.get('readySourceTrackCount')}",
                f"- Build command available: `{bgm_selection.get('buildCommandAvailable')}`",
            ]
        )
    if report.get("transitionBridgeSummary"):
        bridge = report["transitionBridgeSummary"]
        lines.extend(
            [
                "",
                "## Transition Bridge Plan",
                f"- Exists: `{bridge.get('exists')}`",
                f"- Status: `{bridge.get('status')}`",
                f"- Chapter count: {bridge.get('chapterCount')}",
                f"- Boundary rows: {bridge.get('boundaryRowCount')}",
                f"- Boundaries with evidence: {bridge.get('boundariesWithEvidence')}",
                f"- Missing boundaries: {bridge.get('missingBoundaryCount')}",
                f"- Existing bridge clips: {bridge.get('existingBridgeClipCount')}",
            ]
        )
    if report.get("captionStorySummary"):
        caption = report["captionStorySummary"]
        lines.extend(
            [
                "",
                "## Caption Story Plan",
                f"- Exists: `{caption.get('exists')}`",
                f"- Status: `{caption.get('status')}`",
                f"- Cues: {caption.get('subtitleCueCount')} / target {caption.get('targetCueCount')}",
                f"- Cues per minute: {caption.get('cuesPerMinute')}",
                f"- Chapter rows: {caption.get('chapterRowCount')}",
                f"- Rows meeting target: {caption.get('rowsMeetingTarget')}",
                f"- Text export: `{caption.get('textOnlyNarrationExport')}`",
            ]
        )
    if report.get("audienceCaptionSummary"):
        audience = report["audienceCaptionSummary"]
        lines.extend(
            [
                "",
                "## Audience Caption Contract",
                f"- Exists: `{audience.get('exists')}`",
                f"- Status: `{audience.get('status')}`",
                f"- Checked files: {audience.get('checkedFileCount')}",
                f"- Violations: {audience.get('violationCount')}",
            ]
        )
    if report.get("titleTypographySummary"):
        title = report["titleTypographySummary"]
        lines.extend(
            [
                "",
                "## Title Typography Plan",
                f"- Exists: `{title.get('exists')}`",
                f"- Status: `{title.get('status')}`",
                f"- Title rows: {title.get('titleRowCount')}",
                f"- Clean rows: {title.get('cleanRowCount')}",
                f"- Opening/chapter/ending rows: {title.get('openingRowCount')} / {title.get('chapterRowCount')} / {title.get('endingRowCount')}",
                f"- Font verified: `{title.get('fontVerified')}`",
                f"- Title-zone mode: `{title.get('titleZoneMode')}`",
            ]
        )
    if report.get("coverTitleSummary"):
        cover = report["coverTitleSummary"]
        lines.extend(
            [
                "",
                "## Cover Title Contract",
                f"- Exists: `{cover.get('exists')}`",
                f"- Status: `{cover.get('status')}`",
                f"- Main title: `{cover.get('mainTitle')}`",
                f"- Secondary title: `{cover.get('secondaryTitle')}`",
                f"- Background video/recognition: `{cover.get('backgroundVideoReady')}` / `{cover.get('backgroundRecognitionHint')}`",
                f"- Clean 16:9: `{cover.get('clean16x9Deliverable')}`",
                f"- Forbidden hits: {cover.get('forbiddenHitCount')}",
            ]
        )
    if report.get("visualEstablishingSummary"):
        visual = report["visualEstablishingSummary"]
        lines.extend(
            [
                "",
                "## Visual Establishing Plan",
                f"- Exists: `{visual.get('exists')}`",
                f"- Status: `{visual.get('status')}`",
                f"- Establishing rows: {visual.get('establishingRowCount')}",
                f"- Rows with evidence: {visual.get('rowsWithEvidence')}",
                f"- Verified aerial rows: {visual.get('verifiedAerialCount')}",
            ]
        )
    if report.get("effectMotionSummary"):
        effect = report["effectMotionSummary"]
        lines.extend(
            [
                "",
                "## Effect Motion Plan",
                f"- Exists: `{effect.get('exists')}`",
                f"- Status: `{effect.get('status')}`",
                f"- Effect rows: {effect.get('effectRowCount')}",
                f"- Source-backed rows: {effect.get('rowsWithSourceEvidence')}",
                f"- Forbidden effect hits: {effect.get('forbiddenEffectHitCount')}",
            ]
        )
    if report.get("effectMotionBlueprintSummary"):
        effect_blueprint = report["effectMotionBlueprintSummary"]
        lines.extend(
            [
                "",
                "## Effect Motion Blueprint",
                f"- Exists: `{effect_blueprint.get('exists')}`",
                f"- Status: `{effect_blueprint.get('status')}`",
                f"- Base blueprint: `{effect_blueprint.get('baseBlueprintKind')}`",
                f"- Effect rows: {effect_blueprint.get('effectRowCount')}",
                f"- Candidate effects: {effect_blueprint.get('candidateEffectMotionCount')}",
                f"- Blocked rows: {effect_blueprint.get('blockedRowCount')}",
                f"- Forbidden effect hits: {effect_blueprint.get('forbiddenEffectHitCount')}",
            ]
        )
    if report.get("bgmPhraseBlueprintSummary"):
        bgm_phrase = report["bgmPhraseBlueprintSummary"]
        lines.extend(
            [
                "",
                "## BGM Phrase Blueprint",
                f"- Exists: `{bgm_phrase.get('exists')}`",
                f"- Status: `{bgm_phrase.get('status')}`",
                f"- Base blueprint: `{bgm_phrase.get('baseBlueprintKind')}`",
                f"- Selected beds: {bgm_phrase.get('selectedBgmBedCount')}",
                f"- Phrase/section rows: {bgm_phrase.get('phraseRowCount')} / {bgm_phrase.get('sectionRowCount')}",
                f"- Transition cues: {bgm_phrase.get('transitionCueCount')} / {bgm_phrase.get('candidateTransitionCount')}",
                f"- Clip annotations: {bgm_phrase.get('clipAnnotationCount')}",
                f"- Source-audio risks: {bgm_phrase.get('sourceAudioRiskCount')}",
            ]
        )
    if report.get("audioScenePolicySummary"):
        audio = report["audioScenePolicySummary"]
        lines.extend(
            [
                "",
                "## Audio Scene Policy Plan",
                f"- Exists: `{audio.get('exists')}`",
                f"- Status: `{audio.get('status')}`",
                f"- Scene windows: {audio.get('sceneWindowCount')}",
                f"- BGM-covered windows: {audio.get('bgmCoveredWindowCount')}",
                f"- Source-audio risks: {audio.get('sourceAudioRiskCount')}",
                f"- Feedback probes: {audio.get('feedbackWindowCount')}",
            ]
        )
    if report.get("feedbackRegressionPlanSummary"):
        feedback = report["feedbackRegressionPlanSummary"]
        lines.extend(
            [
                "",
                "## Feedback Regression Plan",
                f"- Exists: `{feedback.get('exists')}`",
                f"- Status: `{feedback.get('status')}`",
                f"- Probes: {feedback.get('probeCount')}",
                f"- Opening probes: {feedback.get('openingProbeCount')}",
                f"- 7:04 probes: {feedback.get('sevenMinuteProbeCount')}",
                f"- Audio-policy probes: {feedback.get('audioPolicyProbeCount')}",
            ]
        )
    if report.get("referenceBatchSummary"):
        reference = report["referenceBatchSummary"]
        lines.extend(
            [
                "",
                "## Reference Batch Profile",
                f"- Exists: `{reference.get('exists')}`",
                f"- Status: `{reference.get('status')}`",
                f"- Reference videos: {reference.get('referenceVideoCount')}",
                f"- Total minutes: {reference.get('totalDurationMinutes')}",
                f"- Estimated shots: {reference.get('estimatedShotCount')}",
                f"- Average/median shot: {reference.get('averageShotLengthSeconds')} / {reference.get('medianShotLengthSeconds')}",
                f"- Sample frames: {reference.get('sampleFrameCount')}",
            ]
        )
    if report.get("editRhythmSummary"):
        rhythm = report["editRhythmSummary"]
        lines.extend(
            [
                "",
                "## Edit Rhythm Plan",
                f"- Exists: `{rhythm.get('exists')}`",
                f"- Status: `{rhythm.get('status')}`",
                f"- Primary visual shots: {rhythm.get('primaryVisualShotCount')}",
                f"- Recommended minimum shots: {rhythm.get('recommendedMinimumShotCount')}",
                f"- Additional cutaway beats: {rhythm.get('estimatedAdditionalCutawayBeats')}",
                f"- Rhythm risk rows: {rhythm.get('rhythmRiskCount')}",
            ]
        )
    if report.get("creatorCutSummary"):
        creator = report["creatorCutSummary"]
        lines.extend(
            [
                "",
                "## Creator Cut Plan",
                f"- Exists: `{creator.get('exists')}`",
                f"- Status: `{creator.get('status')}`",
                f"- Primary visual shots: {creator.get('primaryVisualShotCount')}",
                f"- Creator decision rows: {creator.get('creatorDecisionRowCount')}",
                f"- Reject/utility rows: {creator.get('rejectOrUtilityCount')}",
                f"- Route bridge candidates: {creator.get('routeBridgeCandidateCount')}",
            ]
        )
    if report.get("transitionGrammarSummary"):
        grammar = report["transitionGrammarSummary"]
        lines.extend(
            [
                "",
                "## Transition Grammar Plan",
                f"- Exists: `{grammar.get('exists')}`",
                f"- Status: `{grammar.get('status')}`",
                f"- Transition rows: {grammar.get('transitionRowCount')}",
                f"- Rows needing bridge insert: {grammar.get('rowsNeedingBridgeInsert')}",
                f"- Physical bridge evidence rows: {grammar.get('physicalBridgeEvidenceCount')}",
                f"- Motion effect candidates: {grammar.get('motivatedMotionEffectCandidateCount')}",
            ]
        )
    if report.get("transitionExecutionSummary"):
        execution = report["transitionExecutionSummary"]
        lines.extend(
            [
                "",
                "## Transition Execution Plan",
                f"- Exists: `{execution.get('exists')}`",
                f"- Status: `{execution.get('status')}`",
                f"- Transition rows: {execution.get('transitionRowCount')}",
                f"- Ready for Resolve execution: {execution.get('rowsReadyForResolveExecution')}",
                f"- Rows with execution recipe: {execution.get('rowsWithExecutionRecipe')}",
                f"- Bridge insert blocked rows: {execution.get('bridgeInsertBlockedRowCount')}",
                f"- Motion rows/evidence: {execution.get('motionStyleRowCount')} / {execution.get('motionStyleRowsWithEvidence')}",
                f"- Forbidden recipe hits: {execution.get('forbiddenRecipeHitCount')}",
            ]
        )
    if report.get("transitionExecutionBlueprintSummary"):
        execution_blueprint = report["transitionExecutionBlueprintSummary"]
        lines.extend(
            [
                "",
                "## Transition Execution Blueprint",
                f"- Exists: `{execution_blueprint.get('exists')}`",
                f"- Status: `{execution_blueprint.get('status')}`",
                f"- Base blueprint: `{execution_blueprint.get('baseBlueprintKind')}`",
                f"- Execution rows: {execution_blueprint.get('executionRowCount')}",
                f"- Candidate transitions: {execution_blueprint.get('candidateTransitionCount')}",
                f"- Blocked rows: {execution_blueprint.get('blockedRowCount')}",
                f"- Missing clip matches: {execution_blueprint.get('rowsMissingClipMatch')}",
            ]
        )
    if report.get("rhythmRecutBlueprintSummary"):
        recut = report["rhythmRecutBlueprintSummary"]
        lines.extend(
            [
                "",
                "## Rhythm Recut Blueprint",
                f"- Exists: `{recut.get('exists')}`",
                f"- Status: `{recut.get('status')}`",
                f"- Base blueprint: `{recut.get('baseBlueprintKind')}`",
                f"- Long/split/cutaway: {recut.get('longEditableClipCount')} / {recut.get('splitSourceClipCount')} / {recut.get('cutawayInsertCount')}",
                f"- Average shot before/after: {recut.get('averagePrimaryShotBeforeSeconds')} / {recut.get('averagePrimaryShotAfterSeconds')}",
                f"- Long-shot risk before/after: {recut.get('longShotRiskBefore')} / {recut.get('longShotRiskAfter')}",
                f"- Duration delta: {recut.get('durationDeltaSeconds')}",
                f"- BGM phrase preserved: `{recut.get('bgmPhrasePlanPreserved')}`",
                f"- BGM phrase rows/clip annotations/transition cues: {recut.get('bgmPhraseCandidateCount')} / {recut.get('bgmPhraseClipAnnotationCount')} / {recut.get('bgmPhraseTransitionCueCount')}",
            ]
        )
    if report.get("transitionPolishBlueprintSummary"):
        polish = report["transitionPolishBlueprintSummary"]
        lines.extend(
            [
                "",
                "## Transition Polish Blueprint",
                f"- Exists: `{polish.get('exists')}`",
                f"- Status: `{polish.get('status')}`",
                f"- Base blueprint: `{polish.get('baseBlueprintKind')}`",
                f"- Transition rows: {polish.get('transitionRowCount')}",
                f"- Polished transitions: {polish.get('polishedTransitionCount')}",
                f"- BGM phrase/hit rows: {polish.get('rowsWithBgmPhraseCue')} / {polish.get('rowsWithBgmHit')}",
                f"- Title-safe rows: {polish.get('rowsWithTitleSubtitleAvoidance')}",
                f"- Motion rows/evidence: {polish.get('motionPolishRowCount')} / {polish.get('motionPolishRowsWithEvidence')}",
                f"- Downgraded unsupported motion rows: {polish.get('downgradedMotionRowCount')}",
                f"- Blocked rows: {polish.get('blockedRowCount')}",
            ]
        )
    if report.get("transitionQualitySummary"):
        quality = report["transitionQualitySummary"]
        lines.extend(
            [
                "",
                "## Transition Quality Contract",
                f"- Exists: `{quality.get('exists')}`",
                f"- Status: `{quality.get('status')}`",
                f"- Blueprint kind: `{quality.get('blueprintKind')}`",
                f"- Boundaries/transitions: {quality.get('visualBoundaryCount')} / {quality.get('transitionRowCount')}",
                f"- BGM/title/audio rows: {quality.get('rowsWithBgmHit')} / {quality.get('rowsTitleSafe')} / {quality.get('bgmOnlyAudioRows')}",
                f"- Motion rows/evidence: {quality.get('motionRowCount')} / {quality.get('motionRowsWithEvidence')}",
                f"- Crafted transitions: {quality.get('craftedTransitionCount')} / {quality.get('minimumCraftedTransitionCount')}",
                f"- Decorative repeated run max: {quality.get('decorativeRepeatedRunMax')}",
                f"- Blocked rows: {quality.get('blockedRowCount')}",
            ]
        )
    if report.get("shotTransitionBoundarySummary"):
        boundary = report["shotTransitionBoundarySummary"]
        lines.extend(
            [
                "",
                "## Shot Transition Boundary Contract",
                f"- Exists: `{boundary.get('exists')}`",
                f"- Status: `{boundary.get('status')}`",
                f"- Blueprint kind: `{boundary.get('blueprintKind')}`",
                f"- Boundaries/transitions: {boundary.get('visualBoundaryCount')} / {boundary.get('transitionRowCount')}",
                f"- Passed/blocked boundaries: {boundary.get('passedBoundaryCount')} / {boundary.get('blockedBoundaryCount')}",
                f"- Pair/BGM/title/audio boundaries: {boundary.get('pairMatchedBoundaryCount')} / {boundary.get('bgmHitBoundaryCount')} / {boundary.get('titleSafeBoundaryCount')} / {boundary.get('bgmOnlyBoundaryCount')}",
                f"- Motion rows/evidence: {boundary.get('motionBoundaryCount')} / {boundary.get('motionSafeBoundaryCount')}",
                f"- Important boundaries: {boundary.get('importantBoundaryCount')}",
                f"- Decorative repeated run max: {boundary.get('decorativeRepeatedRunMax')}",
            ]
        )
    if report.get("transitionMotivationSummary"):
        motivation = report["transitionMotivationSummary"]
        lines.extend(
            [
                "",
                "## Transition Motivation Contract",
                f"- Exists: `{motivation.get('exists')}`",
                f"- Status: `{motivation.get('status')}`",
                f"- Blueprint kind: `{motivation.get('blueprintKind')}`",
                f"- Boundaries/transitions: {motivation.get('visualBoundaryCount')} / {motivation.get('transitionRowCount')}",
                f"- Motivated/pair-matched: {motivation.get('motivatedBoundaryCount')} / {motivation.get('pairMatchedBoundaryCount')}",
                f"- BGM/bridge/motion/title motivations: {motivation.get('bgmMotivatedBoundaryCount')} / {motivation.get('bridgeMotivatedBoundaryCount')} / {motivation.get('motionMotivatedBoundaryCount')} / {motivation.get('titleSafeMotivatedBoundaryCount')}",
                f"- Important/blocked boundaries: {motivation.get('importantBoundaryCount')} / {motivation.get('blockedBoundaryCount')}",
                f"- Forbidden hits: {motivation.get('forbiddenHitCount')}",
            ]
        )
    if report.get("transitionPairContinuitySummary"):
        continuity = report["transitionPairContinuitySummary"]
        lines.extend(
            [
                "",
                "## Transition Pair Continuity Contract",
                f"- Exists: `{continuity.get('exists')}`",
                f"- Status: `{continuity.get('status')}`",
                f"- Blueprint kind: `{continuity.get('blueprintKind')}`",
                f"- Boundaries/transitions: {continuity.get('visualBoundaryCount')} / {continuity.get('transitionRowCount')}",
                f"- Passed/blocked boundaries: {continuity.get('passedBoundaryCount')} / {continuity.get('blockedBoundaryCount')}",
                f"- Strong/acceptable/weak pair fits: {continuity.get('strongPairFitCount')} / {continuity.get('acceptablePairFitCount')} / {continuity.get('weakPairFitCount')}",
                f"- Payload/style/pair matched: {continuity.get('pairContinuityPayloadCount')} / {continuity.get('styleAllowedBoundaryCount')} / {continuity.get('pairMatchedBoundaryCount')}",
                f"- Motion boundaries: {continuity.get('motionBoundaryCount')}",
            ]
        )
    if report.get("transitionExecutionReadinessSummary"):
        readiness = report["transitionExecutionReadinessSummary"]
        lines.extend(
            [
                "",
                "## Transition Execution Readiness Contract",
                f"- Exists: `{readiness.get('exists')}`",
                f"- Status: `{readiness.get('status')}`",
                f"- Blueprint kind/package-local: `{readiness.get('blueprintKind')}` / `{readiness.get('blueprintInsidePackage')}`",
                f"- Boundaries/transitions: {readiness.get('visualBoundaryCount')} / {readiness.get('transitionRowCount')}",
                f"- Passed/blocked boundaries: {readiness.get('passedBoundaryCount')} / {readiness.get('blockedBoundaryCount')}",
                f"- Recipe/BGM/title/decision/pair/handle ready: {readiness.get('recipeReadyBoundaryCount')} / {readiness.get('bgmHitBoundaryCount')} / {readiness.get('titleSafeBoundaryCount')} / {readiness.get('decisionFieldBoundaryCount')} / {readiness.get('pairReadyBoundaryCount')} / {readiness.get('handleReadyBoundaryCount')}",
                f"- Motion rows/ready: {readiness.get('motionBoundaryCount')} / {readiness.get('motionReadyBoundaryCount')}",
                f"- Max transition duration: {readiness.get('maxTransitionDurationSeconds')}",
            ]
        )
    if report.get("creatorCutApplicationSummary"):
        application = report["creatorCutApplicationSummary"]
        lines.extend(
            [
                "",
                "## Creator Cut Application Contract",
                f"- Exists: `{application.get('exists')}`",
                f"- Status: `{application.get('status')}`",
                f"- Blueprint kind/package-local: `{application.get('blueprintKind')}` / `{application.get('blueprintInsidePackage')}`",
                f"- Visual clips / matched creator rows: {application.get('visualClipCount')} / {application.get('matchedCreatorRowCount')}",
                f"- Blocked clips / chapters: {application.get('blockedClipCount')} / {application.get('chaptersBlocked')}",
                f"- Reject/utility active clips: {application.get('rejectActiveClipCount')} / {application.get('utilityActiveClipCount')}",
                f"- Same-source/function max run: {application.get('sameSourceRunMax')} / {application.get('sameFunctionRunMax')}",
                f"- Function groups: {application.get('globalFunctionGroupCount')}",
            ]
        )
    if report.get("referenceSceneGrammarSummary"):
        grammar = report["referenceSceneGrammarSummary"]
        lines.extend(
            [
                "",
                "## Reference Scene Grammar Contract",
                f"- Exists: `{grammar.get('exists')}`",
                f"- Status: `{grammar.get('status')}`",
                f"- Blueprint kind: `{grammar.get('blueprintKind')}`",
                f"- Visual clips: {grammar.get('visualClipCount')}",
                f"- Opening functions: {grammar.get('openingFunctionCount')} `{', '.join(grammar.get('openingFunctions') or [])}`",
                f"- Chapters passed/blocked: {grammar.get('chaptersPassed')} / {grammar.get('chaptersBlocked')}",
                f"- Ending functions: `{', '.join(grammar.get('endingFunctions') or [])}`",
                f"- Pair-continuity status / weak: {grammar.get('pairContinuityStatus')} / {grammar.get('weakPairFitCount')}",
            ]
        )
    if report.get("unattendedFirstDraftSummary"):
        first_draft = report["unattendedFirstDraftSummary"]
        lines.extend(
            [
                "",
                "## Unattended First Draft Contract",
                f"- Exists: `{first_draft.get('exists')}`",
                f"- Status: `{first_draft.get('status')}`",
                f"- Passed/blocked/warning gates: {first_draft.get('passedGateCount')} / {first_draft.get('blockedGateCount')} / {first_draft.get('warningGateCount')}",
                f"- Required/total gates: {first_draft.get('requiredGateCount')} / {first_draft.get('totalGateCount')}",
            ]
        )
    if report.get("referenceStyleRepairSummary"):
        repair = report["referenceStyleRepairSummary"]
        lines.extend(
            [
                "",
                "## Reference Style Repair Plan",
                f"- Exists: `{repair.get('exists')}`",
                f"- Status: `{repair.get('status')}`",
                f"- Repair rows: {repair.get('repairRowCount')}",
                f"- P0 repair rows: {repair.get('p0RepairRowCount')}",
                f"- Area counts: `{repair.get('areaCounts')}`",
                f"- Reference profile available: `{repair.get('referenceProfileAvailable')}`",
            ]
        )
    if report.get("referenceRepairClosureSummary"):
        closure = report["referenceRepairClosureSummary"]
        lines.extend(
            [
                "",
                "## Reference Repair Closure",
                f"- Exists: `{closure.get('exists')}`",
                f"- Status: `{closure.get('status')}`",
                f"- Repair rows: {closure.get('repairRowCount')}",
                f"- P0 closed: {closure.get('p0ClosedRowCount')} / {closure.get('p0RepairRowCount')}",
                f"- Closed rows: {closure.get('closedRowCount')}",
                f"- Needs editor evidence: {closure.get('needsEditorEvidenceRowCount')}",
                f"- Blocked rows: {closure.get('blockedRowCount')}",
            ]
        )
    if report.get("dryRunSummary"):
        dry = report["dryRunSummary"]
        lines.extend(
            [
                "",
                "## Resolve Dry Run",
                f"- Clips: {dry.get('clipCount')}",
                f"- Coverage ratio: {dry.get('coverageRatio')}",
                f"- Source-audio clips: {dry.get('sourceAudioClipCount')}",
                f"- Missing sources: {len(dry.get('missingSourceFiles') or [])}",
                f"- Pending audio: {len(dry.get('pendingAudioAssets') or [])}",
            ]
        )
    if report.get("resolveBlueprintPreflightSummary"):
        preflight = report["resolveBlueprintPreflightSummary"]
        lines.extend(
            [
                "",
                "## Resolve Blueprint Preflight",
                f"- Exists: `{preflight.get('exists')}`",
                f"- Status: `{preflight.get('status')}`",
                f"- Clips: {preflight.get('clipCount')}",
                f"- Source files: {preflight.get('sourceFileCount')}",
                f"- Source-audio clips: {preflight.get('sourceAudioClipCount')}",
                f"- Title/place cards: {preflight.get('titleCardCount')}",
                f"- Missing sources: {preflight.get('missingSourceCount')}",
                f"- Invalid ranges: {preflight.get('invalidRangeCount')}",
                f"- Same-track overlaps: {preflight.get('overlapCount')}",
                f"- V1 gaps: {preflight.get('v1GapCount')}",
            ]
        )
    if report.get("renderPlanSummary"):
        render = report["renderPlanSummary"]
        lines.extend(
            [
                "",
                "## Resolve Render Plan",
                f"- Exists: `{render.get('exists')}`",
                f"- Gate allowed: `{render.get('gateAllowed')}`",
                f"- Gate blockers: {render.get('gateBlockerCount')}",
                f"- Queued: `{render.get('queued')}`",
                f"- Started: `{render.get('started')}`",
            ]
        )
    if report.get("resolveApplyContractSummary"):
        contract = report["resolveApplyContractSummary"]
        lines.extend(
            [
                "",
                "## Resolve Apply Contract",
                f"- Exists: `{contract.get('exists')}`",
                f"- Status: `{contract.get('status')}`",
                f"- Project: {contract.get('projectName')}",
                f"- Timeline: {contract.get('timelineName')}",
                f"- Blockers: {contract.get('blockerCount')}",
            ]
        )
    if report.get("auditSummary"):
        audit = report["auditSummary"]
        lines.extend(
            [
                "",
                "## Delivery Audit",
                f"- Status: `{audit.get('status')}`",
                f"- Final render allowed: `{audit.get('finalRenderAllowed')}`",
                f"- Blockers: {len(audit.get('blockers') or [])}",
                f"- Warnings: {len(audit.get('warnings') or [])}",
            ]
        )
    lines.extend(["", "## Blockers"])
    for blocker in report.get("blockers") or ["None"]:
        lines.append(f"- {blocker}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def safe_workflow(args: argparse.Namespace) -> dict[str, Any]:
    started = datetime.now().isoformat(timespec="seconds")
    project_dir = Path(args.project_dir).expanduser().resolve()
    steps: list[dict[str, Any]] = []

    check_cmd = ["python3", str(SCRIPTS_DIR / "check_project_state.py"), "--project-dir", str(project_dir), "--json"]
    if args.project_name:
        check_cmd += ["--project-name", args.project_name]
    steps.append(run_step("check_project_state", check_cmd, ok_codes={0, 2}))

    resolve_check_cmd = ["python3", str(SCRIPTS_DIR / "check_resolve_api.py"), "--json"]
    steps.append(run_step("check_resolve_api", resolve_check_cmd, ok_codes={0, 2}))

    route_review_cmd = ["python3", str(SCRIPTS_DIR / "prepare_route_review.py"), "--project-dir", str(project_dir), "--json"]
    if args.project_name:
        route_review_cmd += ["--project-name", args.project_name]
    steps.append(run_step("prepare_route_review", route_review_cmd, ok_codes={0, 2}))

    route_sheet_cmd = ["python3", str(SCRIPTS_DIR / "prepare_route_decision_sheet.py"), "--project-dir", str(project_dir), "--json"]
    if args.project_name:
        route_sheet_cmd += ["--project-name", args.project_name]
    steps.append(run_step("prepare_route_decision_sheet", route_sheet_cmd, ok_codes={0, 2}))

    route_apply_cmd = ["python3", str(SCRIPTS_DIR / "apply_route_decision_sheet.py"), "--project-dir", str(project_dir), "--json"]
    if args.project_name:
        route_apply_cmd += ["--project-name", args.project_name]
    steps.append(run_step("route_decision_application", route_apply_cmd, ok_codes={0, 2}))

    footage_select_cmd = ["python3", str(SCRIPTS_DIR / "prepare_footage_select_plan.py"), "--project-dir", str(project_dir), "--json"]
    steps.append(run_step("prepare_footage_select_plan", footage_select_cmd, ok_codes={0, 2}))

    build_cmd = [
        "python3",
        str(SCRIPTS_DIR / "build_delivery_package.py"),
        "--project-dir",
        str(project_dir),
        "--target-duration-minutes",
        str(args.target_duration_minutes),
    ]
    if args.project_name:
        build_cmd += ["--project-name", args.project_name]
    if args.output_dir:
        build_cmd += ["--output-dir", str(Path(args.output_dir).expanduser().resolve())]
    steps.append(run_step("build_delivery_package", build_cmd))
    if not steps[-1]["ok"]:
        package_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None
        return finish_report(args, started, steps, package_dir, status="failed")

    package_dir = discover_output_dir(steps[-1], args.output_dir)

    raw_intake_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_raw_intake_completeness.py"),
        "--package-dir",
        str(package_dir),
        "--project-dir",
        str(project_dir),
        "--json",
    ]
    steps.append(run_step("audit_raw_intake_completeness", raw_intake_cmd, ok_codes={0, 2}))

    if args.reference or args.reference_dir:
        reference_batch_cmd = [
            "python3",
            str(SCRIPTS_DIR / "prepare_reference_batch_profile.py"),
            "--package-dir",
            str(package_dir),
            "--json",
        ]
        for reference in args.reference or []:
            reference_batch_cmd += ["--reference", str(Path(reference).expanduser())]
        for reference_dir in args.reference_dir or []:
            reference_batch_cmd += ["--reference-dir", str(Path(reference_dir).expanduser())]
        if args.reference_recursive:
            reference_batch_cmd.append("--recursive")
        steps.append(run_step("prepare_reference_batch_profile", reference_batch_cmd, ok_codes={0, 2}))

    opening_story_cmd = ["python3", str(SCRIPTS_DIR / "prepare_opening_story_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_opening_story_plan", opening_story_cmd, ok_codes={0, 2}))

    chapter_arc_cmd = ["python3", str(SCRIPTS_DIR / "prepare_chapter_arc_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_chapter_arc_plan", chapter_arc_cmd, ok_codes={0, 2}))

    assets_cmd = ["python3", str(SCRIPTS_DIR / "prepare_delivery_assets.py"), "--package-dir", str(package_dir)]
    if args.generate_local_voiceover:
        assets_cmd.append("--generate-local-voiceover")
    if args.force_title_cards:
        assets_cmd.append("--force-title-cards")
    if args.force_voiceover:
        assets_cmd.append("--force-voiceover")
    if args.voice:
        assets_cmd += ["--voice", args.voice]
    if args.rate:
        assets_cmd += ["--rate", str(args.rate)]
    steps.append(run_step("prepare_delivery_assets", assets_cmd, ok_codes={0, 2}))

    sourcing_cmd = ["python3", str(SCRIPTS_DIR / "prepare_asset_sourcing_packet.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_asset_sourcing_packet", sourcing_cmd, ok_codes={0, 2}))

    bgm_sourcing_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bgm_sourcing_brief.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_bgm_sourcing_brief", bgm_sourcing_cmd))

    bgm_selection_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bgm_selection_package.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_bgm_selection_package", bgm_selection_cmd, ok_codes={0, 2}))

    transition_bridge_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_bridge_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_transition_bridge_plan", transition_bridge_cmd))

    caption_story_cmd = ["python3", str(SCRIPTS_DIR / "prepare_caption_story_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_caption_story_plan", caption_story_cmd))

    audience_caption_cmd = ["python3", str(SCRIPTS_DIR / "audit_audience_caption_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_audience_caption_contract", audience_caption_cmd, ok_codes={0, 2}))

    title_typography_cmd = ["python3", str(SCRIPTS_DIR / "prepare_title_typography_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_title_typography_plan", title_typography_cmd))

    cover_title_cmd = ["python3", str(SCRIPTS_DIR / "audit_cover_title_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_cover_title_contract", cover_title_cmd, ok_codes={0, 2}))

    visual_establishing_cmd = ["python3", str(SCRIPTS_DIR / "prepare_visual_establishing_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_visual_establishing_plan", visual_establishing_cmd))

    effect_motion_cmd = ["python3", str(SCRIPTS_DIR / "prepare_effect_motion_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_effect_motion_plan", effect_motion_cmd))

    feedback_regression_plan_cmd = ["python3", str(SCRIPTS_DIR / "prepare_feedback_regression_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_feedback_regression_plan", feedback_regression_plan_cmd))

    audio_scene_policy_cmd = ["python3", str(SCRIPTS_DIR / "prepare_audio_scene_policy_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_audio_scene_policy_plan", audio_scene_policy_cmd))

    edit_rhythm_cmd = ["python3", str(SCRIPTS_DIR / "prepare_edit_rhythm_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_edit_rhythm_plan", edit_rhythm_cmd))

    creator_cut_cmd = ["python3", str(SCRIPTS_DIR / "prepare_creator_cut_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_creator_cut_plan", creator_cut_cmd))

    transition_grammar_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_grammar_plan.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_transition_grammar_plan", transition_grammar_cmd))

    transition_execution_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_execution_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_transition_execution_plan", transition_execution_cmd, ok_codes={0, 2}))

    transition_motif_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_motif_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_transition_motif_plan", transition_motif_cmd, ok_codes={0, 2}))

    bridge_sequence_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bridge_sequence_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_bridge_sequence_plan", bridge_sequence_cmd, ok_codes={0, 2}))

    bridge_sequence_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bridge_sequence_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_bridge_sequence_blueprint", bridge_sequence_blueprint_cmd, ok_codes={0, 2}))

    transition_execution_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_execution_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_transition_execution_blueprint", transition_execution_blueprint_cmd, ok_codes={0, 2}))

    effect_motion_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_effect_motion_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_effect_motion_blueprint", effect_motion_blueprint_cmd, ok_codes={0, 2}))

    bgm_phrase_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bgm_phrase_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_bgm_phrase_blueprint", bgm_phrase_blueprint_cmd, ok_codes={0, 2}))

    rhythm_recut_cmd = ["python3", str(SCRIPTS_DIR / "prepare_rhythm_recut_blueprint.py"), "--package-dir", str(package_dir)]
    steps.append(run_step("prepare_rhythm_recut_blueprint", rhythm_recut_cmd))

    transition_polish_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_polish_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_transition_polish_blueprint", transition_polish_cmd, ok_codes={0, 2}))

    transition_quality_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_quality_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_quality_contract", transition_quality_cmd, ok_codes={0, 2}))

    shot_transition_boundary_cmd = ["python3", str(SCRIPTS_DIR / "audit_shot_transition_boundary_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_shot_transition_boundary_contract", shot_transition_boundary_cmd, ok_codes={0, 2}))

    transition_motivation_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_motivation_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_motivation_contract", transition_motivation_cmd, ok_codes={0, 2}))

    transition_pair_continuity_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_pair_continuity_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_pair_continuity_contract", transition_pair_continuity_cmd, ok_codes={0, 2}))

    transition_execution_readiness_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_execution_readiness_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_execution_readiness_contract", transition_execution_readiness_cmd, ok_codes={0, 2}))

    transition_polish_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_polish_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_polish_application_contract", transition_polish_application_cmd, ok_codes={0, 2}))

    bridge_sequence_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_bridge_sequence_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_bridge_sequence_application_contract", bridge_sequence_application_cmd, ok_codes={0, 2}))

    final_blueprint_lineage_cmd = ["python3", str(SCRIPTS_DIR / "audit_final_blueprint_lineage_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_final_blueprint_lineage_contract", final_blueprint_lineage_cmd, ok_codes={0, 2}))

    final_source_usage_cmd = ["python3", str(SCRIPTS_DIR / "audit_final_source_usage_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_final_source_usage_contract", final_source_usage_cmd, ok_codes={0, 2}))

    creator_cut_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_creator_cut_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_creator_cut_application_contract", creator_cut_application_cmd, ok_codes={0, 2}))

    reference_scene_grammar_cmd = ["python3", str(SCRIPTS_DIR / "audit_reference_scene_grammar_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_reference_scene_grammar_contract", reference_scene_grammar_cmd, ok_codes={0, 2}))

    reference_repair_cmd = ["python3", str(SCRIPTS_DIR / "prepare_reference_style_repair_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_reference_style_repair_plan", reference_repair_cmd))

    reference_repair_closure_cmd = ["python3", str(SCRIPTS_DIR / "audit_reference_repair_closure.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_reference_repair_closure", reference_repair_closure_cmd, ok_codes={0, 2}))

    if args.prepare_rhythm_recut_apply_package:
        rhythm_recut_apply_cmd = [
            "python3",
            str(SCRIPTS_DIR / "prepare_rhythm_recut_apply_package.py"),
            "--source-package",
            str(package_dir),
            "--run-preflight",
            "--json",
        ]
        if args.rhythm_recut_apply_output_dir:
            rhythm_recut_apply_cmd += ["--output-dir", str(Path(args.rhythm_recut_apply_output_dir).expanduser())]
        if args.force_rhythm_recut_apply_package:
            rhythm_recut_apply_cmd.append("--force")
        steps.append(run_step("prepare_rhythm_recut_apply_package", rhythm_recut_apply_cmd))

    reconcile_cmd = ["python3", str(SCRIPTS_DIR / "apply_asset_sourcing_decisions.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("asset_decision_reconciliation", reconcile_cmd, ok_codes={0, 2}))

    dry_run_cmd = ["python3", str(SCRIPTS_DIR / "build_resolve_timeline.py"), "--blueprint", str(package_dir / "resolve_timeline_blueprint.json"), "--json"]
    steps.append(run_step("resolve_timeline_dry_run", dry_run_cmd))

    preflight_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_resolve_blueprint.py"),
        "--blueprint",
        str(package_dir / "resolve_timeline_blueprint.json"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("resolve_blueprint_preflight", preflight_cmd, ok_codes={0, 2}))

    unattended_first_draft_cmd = ["python3", str(SCRIPTS_DIR / "audit_unattended_first_draft_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_unattended_first_draft_contract", unattended_first_draft_cmd, ok_codes={0, 2}))

    audit_cmd = ["python3", str(SCRIPTS_DIR / "audit_delivery_package.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_delivery_package", audit_cmd, ok_codes={0, 2}))

    contract_cmd = ["python3", str(SCRIPTS_DIR / "prepare_resolve_apply_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_resolve_apply_contract", contract_cmd, ok_codes={0, 2}))

    if not args.skip_render_plan or args.prepare_render_plan:
        render_cmd = [
            "python3",
            str(SCRIPTS_DIR / "prepare_resolve_render.py"),
            "--package-dir",
            str(package_dir),
            "--json",
        ]
        steps.append(run_step("prepare_resolve_render", render_cmd, ok_codes={0, 2}))
        steps.append(run_step("audit_delivery_package", audit_cmd, ok_codes={0, 2}))

    return finish_report(args, started, steps, package_dir)


def finish_report(args: argparse.Namespace, started: str, steps: list[dict[str, Any]], package_dir: Path | None, status: str | None = None) -> dict[str, Any]:
    ended = datetime.now().isoformat(timespec="seconds")
    project_state_summary = None
    resolve_api_summary = None
    route_decision_summary = None
    route_decision_application_summary = None
    footage_select_summary = None
    raw_intake_completeness_summary = None
    opening_story_summary = None
    chapter_arc_summary = None
    asset_decision_summary = None
    bgm_sourcing_summary = None
    bgm_selection_summary = None
    transition_bridge_summary = None
    caption_story_summary = None
    audience_caption_summary = None
    title_typography_summary = None
    cover_title_summary = None
    visual_establishing_summary = None
    effect_motion_summary = None
    effect_motion_blueprint_summary = None
    bgm_phrase_blueprint_summary = None
    feedback_regression_plan_summary = None
    reference_batch_summary = None
    audio_scene_policy_summary = None
    edit_rhythm_summary = None
    creator_cut_summary = None
    transition_grammar_summary = None
    transition_execution_summary = None
    transition_execution_blueprint_summary = None
    transition_motif_summary = None
    bridge_sequence_summary = None
    bridge_sequence_blueprint_summary = None
    rhythm_recut_summary = None
    transition_polish_summary = None
    transition_quality_summary = None
    shot_transition_boundary_summary = None
    transition_motivation_summary = None
    transition_pair_continuity_summary = None
    transition_execution_readiness_summary = None
    transition_polish_application_summary = None
    bridge_sequence_application_summary = None
    final_blueprint_lineage_summary = None
    final_source_usage_summary = None
    creator_cut_application_summary = None
    reference_scene_grammar_summary = None
    unattended_first_draft_summary = None
    reference_style_repair_summary = None
    reference_repair_closure_summary = None
    rhythm_recut_apply_summary = None
    resolve_apply_contract_summary = None
    resolve_blueprint_preflight_summary = None
    dry_run_summary = None
    audit_summary = None
    render_plan_summary = None
    blockers: list[str] = []
    warnings: list[str] = []

    if package_dir and (package_dir / "delivery_audit.json").exists():
        audit_summary = load_json(package_dir / "delivery_audit.json")
        blockers.extend(audit_summary.get("blockers") or [])
        warnings.extend(audit_summary.get("warnings") or [])
    if package_dir and (package_dir / "render_plan.json").exists():
        render_plan = load_json(package_dir / "render_plan.json")
        render_plan_summary = summarize_render_plan(render_plan)
    if package_dir and (package_dir / "workflow_run_report.json").exists():
        pass
    for step in steps:
        payload = parse_step_json(step)
        if step["id"] == "check_project_state":
            project_state_summary = summarize_project_state(payload)
            if project_state_summary:
                blockers.extend(
                    f"Project state blocker: {item}" for item in project_state_summary.get("blockingIssues") or []
                )
                warnings.extend(
                    f"Project state warning: {item}" for item in project_state_summary.get("warnings") or []
                )
        if step["id"] == "check_resolve_api":
            resolve_api_summary = summarize_resolve_api(payload)
            if resolve_api_summary and not resolve_api_summary.get("reachable"):
                blockers.append(
                    "Resolve API blocker: open DaVinci Resolve Studio and enable Local external scripting."
                )
        if step["id"] == "prepare_route_decision_sheet":
            route_decision_summary = summarize_route_decision_sheet(payload)
        if step["id"] == "route_decision_application":
            route_decision_application_summary = summarize_route_decision_application(payload)
        if step["id"] == "prepare_footage_select_plan":
            footage_select_summary = summarize_footage_select_plan(payload)
        if step["id"] == "audit_raw_intake_completeness":
            raw_intake_completeness_summary = summarize_raw_intake_completeness(payload)
            if raw_intake_completeness_summary and raw_intake_completeness_summary.get("status") == "blocked":
                blockers.extend(
                    f"Raw intake completeness blocker: {item}"
                    for item in raw_intake_completeness_summary.get("blockers") or []
                )
            if raw_intake_completeness_summary and raw_intake_completeness_summary.get("warnings"):
                warnings.extend(
                    f"Raw intake completeness warning: {item}"
                    for item in raw_intake_completeness_summary.get("warnings") or []
                )
        if step["id"] == "prepare_opening_story_plan":
            opening_story_summary = summarize_opening_story_plan(payload)
        if step["id"] == "prepare_chapter_arc_plan":
            chapter_arc_summary = summarize_chapter_arc_plan(payload)
        if step["id"] == "asset_decision_reconciliation":
            asset_decision_summary = summarize_asset_reconciliation(payload)
        if step["id"] == "prepare_bgm_sourcing_brief":
            bgm_sourcing_summary = payload
        if step["id"] == "prepare_bgm_selection_package":
            bgm_selection_summary = summarize_bgm_selection_package(payload)
        if step["id"] == "prepare_transition_bridge_plan":
            transition_bridge_summary = summarize_transition_bridge_plan(payload)
        if step["id"] == "prepare_caption_story_plan":
            caption_story_summary = summarize_caption_story_plan(payload)
        if step["id"] == "audit_audience_caption_contract":
            audience_caption_summary = summarize_audience_caption_contract(payload)
            if audience_caption_summary and audience_caption_summary.get("status") == "blocked":
                blockers.append(
                    f"Audience caption blocker: {audience_caption_summary.get('violationCount')} editor-facing caption/TXT violations"
                )
        if step["id"] == "prepare_title_typography_plan":
            title_typography_summary = summarize_title_typography_plan(payload)
        if step["id"] == "audit_cover_title_contract":
            cover_title_summary = summarize_cover_title_contract(payload)
            if cover_title_summary and cover_title_summary.get("status") == "blocked":
                blockers.extend(f"Cover title blocker: {item}" for item in cover_title_summary.get("blockers") or [])
        if step["id"] == "prepare_visual_establishing_plan":
            visual_establishing_summary = summarize_visual_establishing_plan(payload)
        if step["id"] == "prepare_effect_motion_plan":
            effect_motion_summary = summarize_effect_motion_plan(payload)
        if step["id"] == "prepare_effect_motion_blueprint":
            effect_motion_blueprint_summary = summarize_effect_motion_blueprint(payload)
        if step["id"] == "prepare_bgm_phrase_blueprint":
            bgm_phrase_blueprint_summary = summarize_bgm_phrase_blueprint(payload)
        if step["id"] == "prepare_feedback_regression_plan":
            feedback_regression_plan_summary = summarize_feedback_regression_plan(payload)
        if step["id"] == "prepare_reference_batch_profile":
            reference_batch_summary = summarize_reference_batch_profile(payload)
        if step["id"] == "prepare_audio_scene_policy_plan":
            audio_scene_policy_summary = summarize_audio_scene_policy_plan(payload)
        if step["id"] == "prepare_edit_rhythm_plan":
            edit_rhythm_summary = summarize_edit_rhythm_plan(payload)
        if step["id"] == "prepare_creator_cut_plan":
            creator_cut_summary = summarize_creator_cut_plan(payload)
        if step["id"] == "prepare_transition_grammar_plan":
            transition_grammar_summary = summarize_transition_grammar_plan(payload)
        if step["id"] == "prepare_transition_execution_plan":
            transition_execution_summary = summarize_transition_execution_plan(payload)
        if step["id"] == "prepare_transition_execution_blueprint":
            transition_execution_blueprint_summary = summarize_transition_execution_blueprint(payload)
        if step["id"] == "prepare_transition_motif_plan":
            transition_motif_summary = summarize_transition_motif_plan(payload)
        if step["id"] == "prepare_bridge_sequence_plan":
            bridge_sequence_summary = summarize_bridge_sequence_plan(payload)
        if step["id"] == "prepare_bridge_sequence_blueprint":
            bridge_sequence_blueprint_summary = summarize_bridge_sequence_blueprint(payload)
        if step["id"] == "prepare_rhythm_recut_blueprint":
            rhythm_recut_summary = summarize_rhythm_recut_blueprint(payload)
        if step["id"] == "prepare_transition_polish_blueprint":
            transition_polish_summary = summarize_transition_polish_blueprint(payload)
        if step["id"] == "audit_transition_quality_contract":
            transition_quality_summary = summarize_transition_quality_contract(payload)
            if transition_quality_summary and transition_quality_summary.get("status") == "blocked":
                blockers.extend(f"Transition quality blocker: {item}" for item in transition_quality_summary.get("blockers") or [])
            if transition_quality_summary and transition_quality_summary.get("warnings"):
                warnings.extend(f"Transition quality warning: {item}" for item in transition_quality_summary.get("warnings") or [])
        if step["id"] == "audit_shot_transition_boundary_contract":
            shot_transition_boundary_summary = summarize_shot_transition_boundary_contract(payload)
            if shot_transition_boundary_summary and shot_transition_boundary_summary.get("status") == "blocked":
                blockers.extend(f"Shot transition boundary blocker: {item}" for item in shot_transition_boundary_summary.get("blockers") or [])
            if shot_transition_boundary_summary and shot_transition_boundary_summary.get("warnings"):
                warnings.extend(f"Shot transition boundary warning: {item}" for item in shot_transition_boundary_summary.get("warnings") or [])
        if step["id"] == "audit_transition_motivation_contract":
            transition_motivation_summary = summarize_transition_motivation_contract(payload)
            if transition_motivation_summary and transition_motivation_summary.get("status") == "blocked":
                blockers.extend(f"Transition motivation blocker: {item}" for item in transition_motivation_summary.get("blockers") or [])
            if transition_motivation_summary and transition_motivation_summary.get("warnings"):
                warnings.extend(f"Transition motivation warning: {item}" for item in transition_motivation_summary.get("warnings") or [])
        if step["id"] == "audit_transition_pair_continuity_contract":
            transition_pair_continuity_summary = summarize_transition_pair_continuity_contract(payload)
            if transition_pair_continuity_summary and transition_pair_continuity_summary.get("status") == "blocked":
                blockers.extend(f"Transition pair continuity blocker: {item}" for item in transition_pair_continuity_summary.get("blockers") or [])
            if transition_pair_continuity_summary and transition_pair_continuity_summary.get("warnings"):
                warnings.extend(f"Transition pair continuity warning: {item}" for item in transition_pair_continuity_summary.get("warnings") or [])
        if step["id"] == "audit_transition_execution_readiness_contract":
            transition_execution_readiness_summary = summarize_transition_execution_readiness_contract(payload)
            if transition_execution_readiness_summary and transition_execution_readiness_summary.get("status") == "blocked":
                blockers.extend(f"Transition execution readiness blocker: {item}" for item in transition_execution_readiness_summary.get("blockers") or [])
            if transition_execution_readiness_summary and transition_execution_readiness_summary.get("warnings"):
                warnings.extend(f"Transition execution readiness warning: {item}" for item in transition_execution_readiness_summary.get("warnings") or [])
        if step["id"] == "audit_transition_polish_application_contract":
            transition_polish_application_summary = summarize_transition_polish_application_contract(payload)
            if transition_polish_application_summary and transition_polish_application_summary.get("status") == "blocked":
                blockers.extend(f"Transition polish application blocker: {item}" for item in transition_polish_application_summary.get("blockers") or [])
            if transition_polish_application_summary and transition_polish_application_summary.get("warnings"):
                warnings.extend(f"Transition polish application warning: {item}" for item in transition_polish_application_summary.get("warnings") or [])
        if step["id"] == "audit_bridge_sequence_application_contract":
            bridge_sequence_application_summary = summarize_bridge_sequence_application_contract(payload)
            if bridge_sequence_application_summary and bridge_sequence_application_summary.get("status") == "blocked":
                blockers.extend(f"Bridge sequence application blocker: {item}" for item in bridge_sequence_application_summary.get("blockers") or [])
            if bridge_sequence_application_summary and bridge_sequence_application_summary.get("warnings"):
                warnings.extend(f"Bridge sequence application warning: {item}" for item in bridge_sequence_application_summary.get("warnings") or [])
        if step["id"] == "audit_final_blueprint_lineage_contract":
            final_blueprint_lineage_summary = summarize_final_blueprint_lineage_contract(payload)
            if final_blueprint_lineage_summary and final_blueprint_lineage_summary.get("status") == "blocked":
                blockers.extend(f"Final blueprint lineage blocker: {item}" for item in final_blueprint_lineage_summary.get("blockers") or [])
            if final_blueprint_lineage_summary and final_blueprint_lineage_summary.get("warnings"):
                warnings.extend(f"Final blueprint lineage warning: {item}" for item in final_blueprint_lineage_summary.get("warnings") or [])
        if step["id"] == "audit_final_source_usage_contract":
            final_source_usage_summary = summarize_final_source_usage_contract(payload)
            if final_source_usage_summary and final_source_usage_summary.get("status") == "blocked":
                blockers.extend(f"Final source usage blocker: {item}" for item in final_source_usage_summary.get("blockers") or [])
            if final_source_usage_summary and final_source_usage_summary.get("warnings"):
                warnings.extend(f"Final source usage warning: {item}" for item in final_source_usage_summary.get("warnings") or [])
        if step["id"] == "audit_creator_cut_application_contract":
            creator_cut_application_summary = summarize_creator_cut_application_contract(payload)
            if creator_cut_application_summary and creator_cut_application_summary.get("status") == "blocked":
                blockers.extend(f"Creator cut application blocker: {item}" for item in creator_cut_application_summary.get("blockers") or [])
            if creator_cut_application_summary and creator_cut_application_summary.get("warnings"):
                warnings.extend(f"Creator cut application warning: {item}" for item in creator_cut_application_summary.get("warnings") or [])
        if step["id"] == "audit_reference_scene_grammar_contract":
            reference_scene_grammar_summary = summarize_reference_scene_grammar_contract(payload)
            if reference_scene_grammar_summary and reference_scene_grammar_summary.get("status") == "blocked":
                blockers.extend(f"Reference scene grammar blocker: {item}" for item in reference_scene_grammar_summary.get("blockers") or [])
            if reference_scene_grammar_summary and reference_scene_grammar_summary.get("warnings"):
                warnings.extend(f"Reference scene grammar warning: {item}" for item in reference_scene_grammar_summary.get("warnings") or [])
        if step["id"] == "prepare_reference_style_repair_plan":
            reference_style_repair_summary = summarize_reference_style_repair_plan(payload)
        if step["id"] == "audit_reference_repair_closure":
            reference_repair_closure_summary = summarize_reference_repair_closure(payload)
            if reference_repair_closure_summary and reference_repair_closure_summary.get("status") == "blocked":
                blockers.extend(f"Reference repair closure blocker: {item}" for item in reference_repair_closure_summary.get("blockers") or [])
            if reference_repair_closure_summary and reference_repair_closure_summary.get("warnings"):
                warnings.extend(f"Reference repair closure warning: {item}" for item in reference_repair_closure_summary.get("warnings") or [])
        if step["id"] == "prepare_rhythm_recut_apply_package":
            rhythm_recut_apply_summary = summarize_rhythm_recut_apply_package(payload)
        if step["id"] == "prepare_resolve_apply_contract":
            resolve_apply_contract_summary = summarize_resolve_apply_contract(payload)
        if step["id"] == "resolve_blueprint_preflight":
            resolve_blueprint_preflight_summary = summarize_blueprint_preflight(payload)
            if payload and payload.get("status") == "blocked":
                blockers.extend(f"Resolve blueprint preflight blocker: {item}" for item in payload.get("blockers") or [])
            elif payload and payload.get("warnings"):
                warnings.extend(f"Resolve blueprint preflight warning: {item}" for item in payload.get("warnings") or [])
        if step["id"] == "audit_unattended_first_draft_contract":
            unattended_first_draft_summary = summarize_unattended_first_draft_contract(payload)
            if unattended_first_draft_summary and unattended_first_draft_summary.get("status") == "blocked":
                blockers.extend(
                    f"Unattended first draft blocker: {item}"
                    for item in unattended_first_draft_summary.get("blockers") or []
                )
            if unattended_first_draft_summary and unattended_first_draft_summary.get("warnings"):
                warnings.extend(
                    f"Unattended first draft warning: {item}"
                    for item in unattended_first_draft_summary.get("warnings") or []
                )
        if step["id"] == "resolve_timeline_dry_run":
            dry_run_summary = payload
        if not step["ok"]:
            blockers.append(f"Workflow step failed: {step['id']} (rc {step['returnCode']})")

    if not route_decision_summary and project_state_summary and project_state_summary.get("projectDir"):
        pointer_path = Path(str(project_state_summary["projectDir"])) / "latest_route_decision_sheet.json"
        if pointer_path.exists():
            pointer = load_json(pointer_path)
            sheet_path = Path(str(pointer.get("decisionSheet", ""))).expanduser()
            if sheet_path.exists():
                route_decision_summary = summarize_route_decision_sheet(load_json(sheet_path))
    if not asset_decision_summary and package_dir and (package_dir / "asset_sourcing" / "asset_decision_reconciliation.json").exists():
        asset_decision_summary = summarize_asset_reconciliation(
            load_json(package_dir / "asset_sourcing" / "asset_decision_reconciliation.json")
        )
    if package_dir and (package_dir / "footage_select_plan" / "footage_select_plan.json").exists():
        footage_select_summary = summarize_footage_select_plan(
            load_json(package_dir / "footage_select_plan" / "footage_select_plan.json")
        )
    if package_dir and (package_dir / "raw_intake_completeness_audit.json").exists():
        raw_intake_completeness_summary = summarize_raw_intake_completeness(
            load_json(package_dir / "raw_intake_completeness_audit.json")
        )
    if package_dir and (package_dir / "opening_story_plan" / "opening_story_plan.json").exists():
        opening_story_summary = summarize_opening_story_plan(
            load_json(package_dir / "opening_story_plan" / "opening_story_plan.json")
        )
    if package_dir and (package_dir / "chapter_arc_plan" / "chapter_arc_plan.json").exists():
        chapter_arc_summary = summarize_chapter_arc_plan(
            load_json(package_dir / "chapter_arc_plan" / "chapter_arc_plan.json")
        )
    if package_dir and (package_dir / "bgm_sourcing" / "bgm_sourcing_brief.json").exists():
        bgm_sourcing_summary = summarize_bgm_sourcing(load_json(package_dir / "bgm_sourcing" / "bgm_sourcing_brief.json"))
    if package_dir and (package_dir / "bgm_selection_package" / "bgm_selection_package.json").exists():
        bgm_selection_summary = summarize_bgm_selection_package(
            load_json(package_dir / "bgm_selection_package" / "bgm_selection_package.json")
        )
    if package_dir and (package_dir / "transition_bridge_plan" / "transition_bridge_plan.json").exists():
        transition_bridge_summary = summarize_transition_bridge_plan(
            load_json(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json")
        )
    if package_dir and (package_dir / "caption_story_plan" / "caption_story_plan.json").exists():
        caption_story_summary = summarize_caption_story_plan(
            load_json(package_dir / "caption_story_plan" / "caption_story_plan.json")
        )
    if package_dir and (package_dir / "audience_caption_contract_audit.json").exists():
        audience_caption_summary = summarize_audience_caption_contract(
            load_json(package_dir / "audience_caption_contract_audit.json")
        )
    if package_dir and (package_dir / "title_typography_plan" / "title_typography_plan.json").exists():
        title_typography_summary = summarize_title_typography_plan(
            load_json(package_dir / "title_typography_plan" / "title_typography_plan.json")
        )
    if package_dir and (package_dir / "cover_title_contract_audit.json").exists():
        cover_title_summary = summarize_cover_title_contract(
            load_json(package_dir / "cover_title_contract_audit.json")
        )
    if package_dir and (package_dir / "visual_establishing_plan" / "visual_establishing_plan.json").exists():
        visual_establishing_summary = summarize_visual_establishing_plan(
            load_json(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json")
        )
    if package_dir and (package_dir / "effect_motion_plan" / "effect_motion_plan.json").exists():
        effect_motion_summary = summarize_effect_motion_plan(
            load_json(package_dir / "effect_motion_plan" / "effect_motion_plan.json")
        )
    if package_dir and (package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json").exists():
        effect_motion_blueprint_summary = summarize_effect_motion_blueprint(
            load_json(package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json")
        )
    if package_dir and (package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json").exists():
        bgm_phrase_blueprint_summary = summarize_bgm_phrase_blueprint(
            load_json(package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json")
        )
    if package_dir and (package_dir / "feedback_regression_plan" / "feedback_regression_plan.json").exists():
        feedback_regression_plan_summary = summarize_feedback_regression_plan(
            load_json(package_dir / "feedback_regression_plan" / "feedback_regression_plan.json")
        )
    if package_dir and (package_dir / "reference" / "reference_batch_profile.json").exists():
        reference_batch_summary = summarize_reference_batch_profile(
            load_json(package_dir / "reference" / "reference_batch_profile.json")
        )
    if package_dir and (package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json").exists():
        audio_scene_policy_summary = summarize_audio_scene_policy_plan(
            load_json(package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json")
        )
    if package_dir and (package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json").exists():
        edit_rhythm_summary = summarize_edit_rhythm_plan(
            load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json")
        )
    if package_dir and (package_dir / "creator_cut_plan" / "creator_cut_plan.json").exists():
        creator_cut_summary = summarize_creator_cut_plan(
            load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json")
        )
    if package_dir and (package_dir / "transition_grammar_plan" / "transition_grammar_plan.json").exists():
        transition_grammar_summary = summarize_transition_grammar_plan(
            load_json(package_dir / "transition_grammar_plan" / "transition_grammar_plan.json")
        )
    if package_dir and (package_dir / "transition_execution_plan" / "transition_execution_plan.json").exists():
        transition_execution_summary = summarize_transition_execution_plan(
            load_json(package_dir / "transition_execution_plan" / "transition_execution_plan.json")
        )
    if package_dir and (package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json").exists():
        transition_execution_blueprint_summary = summarize_transition_execution_blueprint(
            load_json(package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json")
        )
    if package_dir and (package_dir / "transition_motif_plan" / "transition_motif_plan.json").exists():
        transition_motif_summary = summarize_transition_motif_plan(
            load_json(package_dir / "transition_motif_plan" / "transition_motif_plan.json")
        )
    if package_dir and (package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json").exists():
        bridge_sequence_summary = summarize_bridge_sequence_plan(
            load_json(package_dir / "bridge_sequence_plan" / "bridge_sequence_plan.json")
        )
    if package_dir and (package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json").exists():
        bridge_sequence_blueprint_summary = summarize_bridge_sequence_blueprint(
            load_json(package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json")
        )
    if package_dir and (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json").exists():
        rhythm_recut_summary = summarize_rhythm_recut_blueprint(
            load_json(package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json")
        )
    if package_dir and (package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json").exists():
        transition_polish_summary = summarize_transition_polish_blueprint(
            load_json(package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json")
        )
    if package_dir and (package_dir / "transition_quality_contract_audit.json").exists():
        transition_quality_summary = summarize_transition_quality_contract(
            load_json(package_dir / "transition_quality_contract_audit.json")
        )
    if package_dir and (package_dir / "shot_transition_boundary_contract_audit.json").exists():
        shot_transition_boundary_summary = summarize_shot_transition_boundary_contract(
            load_json(package_dir / "shot_transition_boundary_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_motivation_contract_audit.json").exists():
        transition_motivation_summary = summarize_transition_motivation_contract(
            load_json(package_dir / "transition_motivation_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_pair_continuity_contract_audit.json").exists():
        transition_pair_continuity_summary = summarize_transition_pair_continuity_contract(
            load_json(package_dir / "transition_pair_continuity_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_execution_readiness_contract_audit.json").exists():
        transition_execution_readiness_summary = summarize_transition_execution_readiness_contract(
            load_json(package_dir / "transition_execution_readiness_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_polish_application_contract_audit.json").exists():
        transition_polish_application_summary = summarize_transition_polish_application_contract(
            load_json(package_dir / "transition_polish_application_contract_audit.json")
        )
    if package_dir and (package_dir / "bridge_sequence_application_contract_audit.json").exists():
        bridge_sequence_application_summary = summarize_bridge_sequence_application_contract(
            load_json(package_dir / "bridge_sequence_application_contract_audit.json")
        )
    if package_dir and (package_dir / "final_blueprint_lineage_contract_audit.json").exists():
        final_blueprint_lineage_summary = summarize_final_blueprint_lineage_contract(
            load_json(package_dir / "final_blueprint_lineage_contract_audit.json")
        )
    if package_dir and (package_dir / "final_source_usage_contract_audit.json").exists():
        final_source_usage_summary = summarize_final_source_usage_contract(
            load_json(package_dir / "final_source_usage_contract_audit.json")
        )
    if package_dir and (package_dir / "creator_cut_application_contract_audit.json").exists():
        creator_cut_application_summary = summarize_creator_cut_application_contract(
            load_json(package_dir / "creator_cut_application_contract_audit.json")
        )
    if package_dir and (package_dir / "reference_scene_grammar_contract_audit.json").exists():
        reference_scene_grammar_summary = summarize_reference_scene_grammar_contract(
            load_json(package_dir / "reference_scene_grammar_contract_audit.json")
        )
    if package_dir and (package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json").exists():
        reference_style_repair_summary = summarize_reference_style_repair_plan(
            load_json(package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json")
        )
    if package_dir and (package_dir / "reference_repair_closure_audit.json").exists():
        reference_repair_closure_summary = summarize_reference_repair_closure(
            load_json(package_dir / "reference_repair_closure_audit.json")
        )
    if package_dir and (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_apply_package_report.json").exists():
        rhythm_recut_apply_summary = summarize_rhythm_recut_apply_package(
            load_json(package_dir / "rhythm_recut_blueprint" / "rhythm_recut_apply_package_report.json")
        )
    if not route_decision_application_summary and project_state_summary and project_state_summary.get("projectDir"):
        review_root = Path(str(project_state_summary["projectDir"])) / "route_review"
        reports = sorted(review_root.glob("*/route_decision_application.json")) if review_root.exists() else []
        if reports:
            route_decision_application_summary = summarize_route_decision_application(load_json(max(reports, key=lambda p: p.stat().st_mtime)))
    if not resolve_apply_contract_summary and package_dir and (package_dir / "resolve_apply_contract.json").exists():
        resolve_apply_contract_summary = summarize_resolve_apply_contract(load_json(package_dir / "resolve_apply_contract.json"))
    if not resolve_blueprint_preflight_summary and package_dir and (package_dir / "resolve_blueprint_preflight.json").exists():
        resolve_blueprint_preflight_summary = summarize_blueprint_preflight(load_json(package_dir / "resolve_blueprint_preflight.json"))
    if package_dir and (package_dir / "unattended_first_draft_contract_audit.json").exists():
        unattended_first_draft_summary = summarize_unattended_first_draft_contract(
            load_json(package_dir / "unattended_first_draft_contract_audit.json")
        )

    final_status = status
    if not final_status:
        if audit_summary and audit_summary.get("status") == "blocked":
            final_status = "blocked"
        elif any(not step["ok"] for step in steps):
            final_status = "failed"
        elif blockers:
            final_status = "blocked"
        elif audit_summary and audit_summary.get("status"):
            final_status = str(audit_summary["status"])
        else:
            final_status = "draft"

    report = {
        "createdAt": ended,
        "startedAt": started,
        "endedAt": ended,
        "status": final_status,
        "packageDir": str(package_dir) if package_dir else None,
        "projectDir": str(Path(args.project_dir).expanduser().resolve()),
        "targetDurationMinutes": args.target_duration_minutes,
        "steps": steps,
        "projectStateSummary": project_state_summary,
        "resolveApiSummary": resolve_api_summary,
        "routeDecisionSummary": route_decision_summary,
        "routeDecisionApplicationSummary": route_decision_application_summary,
        "footageSelectSummary": footage_select_summary,
        "rawIntakeCompletenessSummary": raw_intake_completeness_summary,
        "openingStorySummary": opening_story_summary,
        "chapterArcSummary": chapter_arc_summary,
        "assetDecisionSummary": asset_decision_summary,
        "bgmSourcingSummary": bgm_sourcing_summary,
        "bgmSelectionSummary": bgm_selection_summary,
        "transitionBridgeSummary": transition_bridge_summary,
        "captionStorySummary": caption_story_summary,
        "audienceCaptionSummary": audience_caption_summary,
        "titleTypographySummary": title_typography_summary,
        "coverTitleSummary": cover_title_summary,
        "visualEstablishingSummary": visual_establishing_summary,
        "effectMotionSummary": effect_motion_summary,
        "effectMotionBlueprintSummary": effect_motion_blueprint_summary,
        "bgmPhraseBlueprintSummary": bgm_phrase_blueprint_summary,
        "feedbackRegressionPlanSummary": feedback_regression_plan_summary,
        "referenceBatchSummary": reference_batch_summary,
        "audioScenePolicySummary": audio_scene_policy_summary,
        "editRhythmSummary": edit_rhythm_summary,
        "creatorCutSummary": creator_cut_summary,
        "transitionGrammarSummary": transition_grammar_summary,
        "transitionExecutionSummary": transition_execution_summary,
        "transitionExecutionBlueprintSummary": transition_execution_blueprint_summary,
        "transitionMotifSummary": transition_motif_summary,
        "bridgeSequenceSummary": bridge_sequence_summary,
        "bridgeSequenceBlueprintSummary": bridge_sequence_blueprint_summary,
        "rhythmRecutBlueprintSummary": rhythm_recut_summary,
        "transitionPolishBlueprintSummary": transition_polish_summary,
        "transitionQualitySummary": transition_quality_summary,
        "shotTransitionBoundarySummary": shot_transition_boundary_summary,
        "transitionMotivationSummary": transition_motivation_summary,
        "transitionPairContinuitySummary": transition_pair_continuity_summary,
        "transitionExecutionReadinessSummary": transition_execution_readiness_summary,
        "transitionPolishApplicationSummary": transition_polish_application_summary,
        "bridgeSequenceApplicationSummary": bridge_sequence_application_summary,
        "finalBlueprintLineageSummary": final_blueprint_lineage_summary,
        "finalSourceUsageSummary": final_source_usage_summary,
        "creatorCutApplicationSummary": creator_cut_application_summary,
        "referenceSceneGrammarSummary": reference_scene_grammar_summary,
        "unattendedFirstDraftSummary": unattended_first_draft_summary,
        "referenceStyleRepairSummary": reference_style_repair_summary,
        "referenceRepairClosureSummary": reference_repair_closure_summary,
        "rhythmRecutApplyPackageSummary": rhythm_recut_apply_summary,
        "resolveApplyContractSummary": resolve_apply_contract_summary,
        "resolveBlueprintPreflightSummary": resolve_blueprint_preflight_summary,
        "dryRunSummary": dry_run_summary,
        "renderPlanSummary": render_plan_summary,
        "auditSummary": audit_summary,
        "blockers": unique(blockers),
        "warnings": unique(warnings),
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "localTtsGenerated": bool(args.generate_local_voiceover),
            "externalCloudCalls": False,
        },
        "nextManualApprovals": [
            "Confirm or repair route/location review decisions.",
            "Approve route_decision_sheet.json before writing decisions back to route_review.json.",
            "Select and verify BGM/stock/aerial licenses.",
            "Review bgm_selection_package.json before Resolve apply so the selected BGM bed is local, license-traceable, target-duration-covering, and referenced by the active blueprint.",
            "Review footage_select_plan.json before trusting first assembly; repair/reject rows should not lead the cut.",
            "Review raw_intake_completeness_audit.json before trusting any large unordered source folder; every active source video must be indexed, recognized, routed exactly once, and scored before first assembly.",
            "Review opening_story_plan.json before title, BGM, rhythm, or Resolve apply so the first three minutes have viewer promise, destination proof, clean title, practical arrival, lived-in texture, and first handoff.",
            "Review chapter_arc_plan.json before rhythm/creator-cut/Resolve apply so every chapter has context, movement, lived-in texture, payoff, and aftertaste decisions.",
            "Fill transition_bridge_plan.json local bridge or stock/aerial fallback decisions before final claims.",
            "Review caption_story_plan/text_only_narration_export.txt and dense SRT before subtitle overlay generation.",
            "Review audience_caption_contract_audit.json so final captions/TXT are viewer-facing travel-film text, not edit-status reports.",
            "Review title_typography_plan.json before generating or trusting title bridge media.",
            "Review visual_establishing_plan.json before trusting opening/chapter/ending aerial, landmark, or city establishing shots.",
            "Review effect_motion_plan.json before adding Resolve title, route, or transition effects.",
            "Preflight effect_motion_blueprint/resolve_timeline_blueprint_effect_motion.json before approving title or transition motion effects for Resolve.",
            "Preflight bgm_phrase_blueprint/resolve_timeline_blueprint_bgm_phrase.json before approving BGM phrase cues, transition sync, or music-led scenic sections for Resolve.",
            "Review feedback_regression_plan.json so original user complaints stay in pre-render audio policy, post-render feedback audit, and final QA commands.",
            "Review reference_batch_profile.json when local reference videos are supplied so rhythm/style targets are based on measured reference evidence.",
            "Review audio_scene_policy_plan.json before Resolve apply so opening/scenic/title/transition windows are A3 BGM-led with no A1/A2 voice leak.",
            "Review edit_rhythm_plan.json before Resolve apply so long raw clips, missing cutaways, and weak chapter variety are fixed before the edit feels AI-assembled.",
            "Review creator_cut_plan.json before transition execution so weak clips are demoted and kept clips have creator functions.",
            "Review transition_grammar_plan.json and transition_execution_plan.json before Resolve apply so every adjacent pair has an approved, source-backed execution recipe.",
            "Preflight transition_execution_blueprint/resolve_timeline_blueprint_transition_execution.json before approving transition effects for Resolve.",
            "Review transition_motif_plan.json before Resolve apply so the film does not rely on repeated dissolves, random motion, or effects hiding weak route jumps.",
            "Review bridge_sequence_plan.json before rhythm recut or Resolve apply so important route/title/timeline-gap transitions become 2-5 shot bridge sequences instead of single effects.",
            "Review transition_motivation_contract_audit.json before Resolve apply so each transition has a viewer-facing route, motion, title, bridge, or BGM motivation instead of a decorative effect.",
            "Review transition_pair_continuity_contract_audit.json before Resolve apply so every adjacent from/to shot has concrete visual, route, motion, BGM, or title continuity evidence.",
            "Review transition_execution_readiness_contract_audit.json before Resolve apply so every transition has a package-local Resolve recipe, BGM hit, title-safe window, pair readiness, handles, and decision fields.",
            "Review transition_polish_application_contract_audit.json before Resolve apply so final/active blueprints do not drop transition-polish metadata after candidate generation.",
            "Review bridge_sequence_application_contract_audit.json before Resolve apply so planned 2-5 shot bridge sequences survive into the final candidate blueprint.",
            "Review final_blueprint_lineage_contract_audit.json before Resolve apply so the active final blueprint inherits the latest ready candidate chain instead of an old or partial blueprint.",
            "Review final_source_usage_contract_audit.json before Resolve apply so the final raw clips actually come from footage_select_plan hero/main/texture choices and do not reintroduce unmatched, repair, reject, or utility-dominant sources.",
            "Review creator_cut_application_contract_audit.json before Resolve apply so rejected/utility/weak creator-cut rows cannot remain active in the final candidate blueprint.",
            "Review reference_scene_grammar_contract_audit.json before Resolve apply so opening, chapters, transitions, and ending follow the Parallel World/Malta scene-function grammar.",
            "Preflight bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json before approving bridge sequence inserts for Resolve.",
            "Review rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json and preflight it before replacing the active Resolve blueprint.",
            "Review unattended_first_draft_contract_audit.json before Resolve apply or handoff; it proves raw intake, story, BGM, captions, titles, rhythm, transitions, repair closure, and blueprint preflight are connected.",
            "Review reference_style_repair_plan.json so blocked reference/director/QA gaps become executable repair rows before another Resolve write.",
            "When the rhythm recut candidate is approved, generate/review the rhythm recut apply package before any Resolve write.",
            "Approve local TTS, recorded voiceover, or imported narration audio.",
            "Approve resolve_apply_contract.json only after delivery audit blockers are cleared.",
            "Approve Resolve --apply only after the apply contract is approved.",
        ],
    }
    if package_dir:
        write_json(package_dir / "workflow_run_report.json", report)
        write_markdown(package_dir / "workflow_run_report.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the safe local long-form delivery workflow.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR))
    parser.add_argument("--project-name")
    parser.add_argument("--output-dir")
    parser.add_argument("--reference", action="append", default=[], help="Reference video path for batch style profiling. Can be repeated.")
    parser.add_argument("--reference-dir", action="append", default=[], help="Directory of reference videos for batch style profiling. Can be repeated.")
    parser.add_argument("--reference-recursive", action="store_true", help="Search --reference-dir recursively.")
    parser.add_argument("--target-duration-minutes", type=float, default=20.0)
    parser.add_argument("--generate-local-voiceover", action="store_true")
    parser.add_argument("--force-title-cards", action="store_true")
    parser.add_argument("--force-voiceover", action="store_true")
    parser.add_argument("--voice")
    parser.add_argument("--rate", type=int, default=175)
    parser.add_argument(
        "--prepare-render-plan",
        action="store_true",
        help="Deprecated compatibility flag. A safe render plan is prepared by default.",
    )
    parser.add_argument("--skip-render-plan", action="store_true", help="Skip the safe render_plan.json preparation step.")
    parser.add_argument("--prepare-rhythm-recut-apply-package", action="store_true", help="Fork a new package that uses the rhythm-recut candidate as the active blueprint.")
    parser.add_argument("--rhythm-recut-apply-output-dir", help="Optional output dir for --prepare-rhythm-recut-apply-package.")
    parser.add_argument("--force-rhythm-recut-apply-package", action="store_true", help="Replace the generated rhythm-recut apply output dir if it already exists.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = safe_workflow(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Workflow status: {report['status']}")
        print(f"Package: {report.get('packageDir')}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 2 if report["status"] in {"blocked", "failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
