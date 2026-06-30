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


def summarize_source_selection_repair_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "sourceVideoCount": summary.get("sourceVideoCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "readyChapterCount": summary.get("readyChapterCount"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "candidateVideoCount": summary.get("candidateVideoCount"),
        "heroCandidateCount": summary.get("heroCandidateCount"),
        "movementBridgeCandidateCount": summary.get("movementBridgeCandidateCount"),
        "livedInTextureCandidateCount": summary.get("livedInTextureCandidateCount"),
        "destinationPayoffCandidateCount": summary.get("destinationPayoffCandidateCount"),
        "blockingRepairRowCount": summary.get("blockingRepairRowCount"),
        "warningRepairRowCount": summary.get("warningRepairRowCount"),
        "requiredOwnerScripts": summary.get("requiredOwnerScripts") or [],
    }


def summarize_source_selection_coverage_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "sourceVideoCount": summary.get("sourceVideoCount"),
        "chapterRowCount": summary.get("chapterRowCount"),
        "readyChapterCount": summary.get("readyChapterCount"),
        "candidateVideoCount": summary.get("candidateVideoCount"),
        "blockingRepairRowCount": summary.get("blockingRepairRowCount"),
        "warningRepairRowCount": summary.get("warningRepairRowCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_first_assembly_source_order_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_large_source_unattended_readiness_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
        "externalMediaIntake": inputs.get("externalMediaIntake"),
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


def summarize_bgm_musicality_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    audio = summary.get("audio") if isinstance(summary.get("audio"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "bgmOutput": summary.get("bgmOutput"),
        "manifestTrackCount": summary.get("manifestTrackCount"),
        "namedTrackCount": summary.get("namedTrackCount"),
        "licenseTrackCount": summary.get("licenseTrackCount"),
        "badIdentityTerms": summary.get("badIdentityTerms"),
        "phraseRowCount": summary.get("phraseRowCount"),
        "sectionRowCount": summary.get("sectionRowCount"),
        "activeBandCount": audio.get("activeBandCount"),
        "medianWindowActiveBandCount": audio.get("medianWindowActiveBandCount"),
        "singleBandDominance": audio.get("singleBandDominance"),
        "dynamicRangeDb": audio.get("dynamicRangeDb"),
        "silentWindowRatio": audio.get("silentWindowRatio"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
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


def summarize_reference_review_repair_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "repairRowCount": summary.get("repairRowCount"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "closedFullReviewDecisionCount": summary.get("referenceRowsWithClosedFullReviewDecision"),
        "referencesWithAnalysis": summary.get("referencesWithAnalysis"),
        "referencesWithContactSheet": summary.get("referencesWithContactSheet"),
        "referencesWithOpeningMiddleEndingCoverage": summary.get("referencesWithOpeningMiddleEndingCoverage"),
        "ownerScripts": summary.get("ownerScripts"),
    }


def summarize_editorial_watchdown_repair_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "watchRowCount": summary.get("watchRowCount"),
        "closedWatchRowCount": summary.get("closedWatchRowCount"),
        "repairRowCount": summary.get("repairRowCount"),
        "chapterWatchRowCount": summary.get("chapterWatchRowCount"),
        "supportingReportIssueCount": summary.get("supportingReportIssueCount"),
        "finalOutput": summary.get("finalOutput"),
        "finalOutputExists": summary.get("finalOutputExists"),
        "ownerScripts": summary.get("ownerScripts"),
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


def summarize_transition_reference_candidates(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "candidateRowCount": summary.get("candidateRowCount"),
        "rowsWithAtLeastThreeCandidates": summary.get("rowsWithAtLeastThreeCandidates"),
        "motionCandidateRowCount": summary.get("motionCandidateRowCount"),
        "maxMotionCandidateRows": summary.get("maxMotionCandidateRows"),
        "rowsNeedingBridgeBeforeEffect": summary.get("rowsNeedingBridgeBeforeEffect"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantBridgeOrBreathCoverage": summary.get("importantBridgeOrBreathCoverage"),
        "primaryStyleFamilyCounts": summary.get("primaryStyleFamilyCounts"),
        "referenceStatus": summary.get("referenceStatus"),
        "referenceVideoCount": summary.get("referenceVideoCount"),
    }


def summarize_transition_reference_selection(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "candidateRowCount": summary.get("candidateRowCount"),
        "selectionRowCount": summary.get("selectionRowCount"),
        "selectedRowCount": summary.get("selectedRowCount"),
        "autoSelectedRowCount": summary.get("autoSelectedRowCount"),
        "blockedSelectionRowCount": summary.get("blockedSelectionRowCount"),
        "motionSelectedRowCount": summary.get("motionSelectedRowCount"),
        "maxMotionRows": summary.get("maxMotionRows"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantBridgeOrBreathSelectionCoverage": summary.get("importantBridgeOrBreathSelectionCoverage"),
        "selectedStyleFamilyCounts": summary.get("selectedStyleFamilyCounts"),
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
        "referenceSelectionRowCount": summary.get("referenceSelectionRowCount"),
        "rowsWithReferenceSelection": summary.get("rowsWithReferenceSelection"),
        "rowsWithAppliedReferenceSelection": summary.get("rowsWithAppliedReferenceSelection"),
        "blockedReferenceSelectionRowCount": summary.get("blockedReferenceSelectionRowCount"),
        "selectedStyleFamilyCounts": summary.get("selectedStyleFamilyCounts"),
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
        "rowsWithDirectionalActionAnchor": summary.get("rowsWithDirectionalActionAnchor"),
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
        "blockedMotionExecutionRowCount": summary.get("blockedMotionExecutionRowCount"),
        "choreographyFamilyCounts": summary.get("choreographyFamilyCounts"),
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


def summarize_transition_bridge_visual_evidence_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "requiredBridgeRowCount": summary.get("requiredBridgeRowCount"),
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


def summarize_effect_motion_application_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "finalBlueprintKind": inputs.get("finalBlueprintKind"),
        "finalBlueprintInsidePackage": inputs.get("finalBlueprintInsidePackage"),
        "sourceEffectRowCount": summary.get("sourceEffectRowCount"),
        "finalEffectMotionCandidateCount": summary.get("finalEffectMotionCandidateCount"),
        "auditedEffectRowCount": summary.get("auditedEffectRowCount"),
        "passedEffectRowCount": summary.get("passedEffectRowCount"),
        "blockedEffectRowCount": summary.get("blockedEffectRowCount"),
        "motionEffectRowCount": summary.get("motionEffectRowCount"),
        "maxMotionAllowed": summary.get("maxMotionAllowed"),
        "bgmOnlyRowCount": summary.get("bgmOnlyRowCount"),
        "titleSafeRowCount": summary.get("titleSafeRowCount"),
        "clipAnnotationRowCount": summary.get("clipAnnotationRowCount"),
        "markerRowCount": summary.get("markerRowCount"),
        "forbiddenEffectHitCount": summary.get("forbiddenEffectHitCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_cadence_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_microstructure_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "bgmHitBoundaryCount": summary.get("bgmHitBoundaryCount"),
        "titleSafeBoundaryCount": summary.get("titleSafeBoundaryCount"),
        "bgmOnlyBoundaryCount": summary.get("bgmOnlyBoundaryCount"),
        "readyCutpointRowCount": summary.get("readyCutpointRowCount"),
        "blockedCutpointRowCount": summary.get("blockedCutpointRowCount"),
        "readyActionAnchorRowCount": summary.get("readyActionAnchorRowCount"),
        "blockedActionAnchorRowCount": summary.get("blockedActionAnchorRowCount"),
        "handleReadyBoundaryCount": summary.get("handleReadyBoundaryCount"),
        "pairReadyBoundaryCount": summary.get("pairReadyBoundaryCount"),
        "weakPairFitCount": summary.get("weakPairFitCount"),
        "motionBoundaryCount": summary.get("motionBoundaryCount"),
        "motionReadyBoundaryCount": summary.get("motionReadyBoundaryCount"),
        "maxTransitionDurationSeconds": summary.get("maxTransitionDurationSeconds"),
        "decorativeRepeatedRunMax": summary.get("decorativeRepeatedRunMax"),
        "markerOnlyBlockedRowCount": summary.get("markerOnlyBlockedRowCount"),
        "expectedBridgeBeatClipCount": summary.get("expectedBridgeBeatClipCount"),
        "appliedBridgeBeatClipCount": summary.get("appliedBridgeBeatClipCount"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_cutpoint_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_action_anchor_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_sensory_continuity_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockedCheckCount": summary.get("blockedCheckCount"),
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


def summarize_rhythm_recut_application_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "recutStatus": summary.get("recutStatus"),
        "recutSourceRowCount": summary.get("recutSourceRowCount"),
        "passedRecutRowCount": summary.get("passedRecutRowCount"),
        "blockedRecutRowCount": summary.get("blockedRecutRowCount"),
        "finalRhythmRecutClipCount": summary.get("finalRhythmRecutClipCount"),
        "finalRhythmRecutMainSegmentCount": summary.get("finalRhythmRecutMainSegmentCount"),
        "finalRhythmRecutCutawayCount": summary.get("finalRhythmRecutCutawayCount"),
        "finalLongShotRiskCount": summary.get("finalLongShotRiskCount"),
        "bgmPhrasePlanPreserved": summary.get("bgmPhrasePlanPreserved"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
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


def summarize_resolve_transition_materialization_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "blueprintKind": inputs.get("blueprintKind"),
        "blueprintInsidePackage": inputs.get("blueprintInsidePackage"),
        "buildResolveTimelinePreservesMarkerPayload": inputs.get("buildResolveTimelinePreservesMarkerPayload"),
        "resolveReadbackChecked": inputs.get("resolveReadbackChecked"),
        "transitionCandidateCount": summary.get("transitionCandidateCount"),
        "transitionRowsWithMarkerPayload": summary.get("transitionRowsWithMarkerPayload"),
        "transitionRowsWithClipAnnotation": summary.get("transitionRowsWithClipAnnotation"),
        "visibleEffectRowCount": summary.get("visibleEffectRowCount"),
        "resolveRowsWithPayload": summary.get("resolveRowsWithPayload"),
        "blockedTransitionRowCount": summary.get("blockedTransitionRowCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_resolve_transition_apply_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    inputs = report.get("inputs") if isinstance(report.get("inputs"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "applyPlanStatus": inputs.get("applyPlanStatus"),
        "materializationStatus": inputs.get("materializationStatus"),
        "transitionApplyRowCount": summary.get("transitionApplyRowCount"),
        "passedRowCount": summary.get("passedRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "visibleEffectRowCount": summary.get("visibleEffectRowCount"),
        "visibleEffectRowsWithApplyPath": summary.get("visibleEffectRowsWithApplyPath"),
        "manualResolveRowCount": summary.get("manualResolveRowCount"),
        "pendingManualVisibleEffectRowCount": summary.get("pendingManualVisibleEffectRowCount"),
        "manualResolveEvidenceReadyRowCount": summary.get("manualResolveEvidenceReadyRowCount"),
        "fallbackBridgeEvidenceReadyRowCount": summary.get("fallbackBridgeEvidenceReadyRowCount"),
        "fallbackBridgeRequiredRowCount": summary.get("fallbackBridgeRequiredRowCount"),
        "readbackEvidenceRequiredRowCount": summary.get("readbackEvidenceRequiredRowCount"),
        "decisionFieldRowCount": summary.get("decisionFieldRowCount"),
        "markerOnlyBlockedRowCount": summary.get("markerOnlyBlockedRowCount"),
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


def summarize_reference_profile_application_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_reference_transition_profile_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_chapter_story_spine_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_shot_flow_continuity_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_timeline_variety_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_scene_arc_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_effect_palette_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_motif_coherence_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "motifFamilyCount": summary.get("motifFamilyCount"),
        "minimumMotifFamilyCount": summary.get("minimumMotifFamilyCount"),
        "dominantMotif": summary.get("dominantMotif"),
        "dominantMotifShare": summary.get("dominantMotifShare"),
        "repeatedMotifRunMax": summary.get("repeatedMotifRunMax"),
        "repeatedStyleRunMax": summary.get("repeatedStyleRunMax"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantReadyBoundaryCount": summary.get("importantReadyBoundaryCount"),
        "motionMotifCount": summary.get("motionMotifCount"),
        "motionSpacingViolationCount": summary.get("motionSpacingViolationCount"),
        "openingEndingMotionRowCount": summary.get("openingEndingMotionRowCount"),
        "selectionMismatchCount": summary.get("selectionMismatchCount"),
        "blockingRepairRowCount": summary.get("blockingRepairRowCount"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_visual_match_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_source_coverage_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "readySourceCoverageRowCount": summary.get("readySourceCoverageRowCount"),
        "blockedSourceCoverageRowCount": summary.get("blockedSourceCoverageRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "motionTransitionCount": summary.get("motionTransitionCount"),
        "bridgeReadyRowCount": summary.get("bridgeReadyRowCount"),
        "motionSourceReadyRowCount": summary.get("motionSourceReadyRowCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "issueCounts": summary.get("issueCounts"),
        "styleCounts": summary.get("styleCounts"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_choreography_plan(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "readyChoreographyRowCount": summary.get("readyChoreographyRowCount"),
        "blockedChoreographyRowCount": summary.get("blockedChoreographyRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsWithThreeBeatCount": summary.get("importantRowsWithThreeBeatCount"),
        "motionChoreographyRowCount": summary.get("motionChoreographyRowCount"),
        "motionDirectionReadyRowCount": summary.get("motionDirectionReadyRowCount"),
        "motionDirectionBlockedRowCount": summary.get("motionDirectionBlockedRowCount"),
        "maxFamilyRun": summary.get("maxFamilyRun"),
        "dominantFamilyShare": summary.get("dominantFamilyShare"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_choreography_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "passedChoreographyRowCount": summary.get("passedChoreographyRowCount"),
        "blockedChoreographyRowCount": summary.get("blockedChoreographyRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantRowsWithThreeBeatCount": summary.get("importantRowsWithThreeBeatCount"),
        "motionChoreographyRowCount": summary.get("motionChoreographyRowCount"),
        "highIntensityRowCount": summary.get("highIntensityRowCount"),
        "maxFamilyRun": summary.get("maxFamilyRun"),
        "dominantFamilyShare": summary.get("dominantFamilyShare"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_motion_direction_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "motionDirectionRowCount": summary.get("motionDirectionRowCount"),
        "readyMotionDirectionRowCount": summary.get("readyMotionDirectionRowCount"),
        "blockedMotionDirectionRowCount": summary.get("blockedMotionDirectionRowCount"),
        "rowsWithEffectDirection": summary.get("rowsWithEffectDirection"),
        "rowsWithLandingDirection": summary.get("rowsWithLandingDirection"),
        "rowsWithDirectionMatch": summary.get("rowsWithDirectionMatch"),
        "rowsWithDirectionConfidence": summary.get("rowsWithDirectionConfidence"),
        "importantMotionRowCount": summary.get("importantMotionRowCount"),
        "importantMotionRowsWithBridgeSupport": summary.get("importantMotionRowsWithBridgeSupport"),
        "effectDirectionCounts": summary.get("effectDirectionCounts"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_motion_accent_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "motionAccentRowCount": summary.get("motionAccentRowCount"),
        "readyMotionAccentRowCount": summary.get("readyMotionAccentRowCount"),
        "blockedMotionAccentRowCount": summary.get("blockedMotionAccentRowCount"),
        "maxMotionAccentAllowed": summary.get("maxMotionAccentAllowed"),
        "motionAccentShare": summary.get("motionAccentShare"),
        "motionAccentRunMax": summary.get("motionAccentRunMax"),
        "highIntensityMotionCount": summary.get("highIntensityMotionCount"),
        "rotationTooStrongCount": summary.get("rotationTooStrongCount"),
        "unsupportedMotionAccentCount": summary.get("unsupportedMotionAccentCount"),
        "directionMismatchMotionCount": summary.get("directionMismatchMotionCount"),
        "titleOrCaptionRiskMotionCount": summary.get("titleOrCaptionRiskMotionCount"),
        "missingAnchorMotionCount": summary.get("missingAnchorMotionCount"),
        "missingSensoryMotionCount": summary.get("missingSensoryMotionCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_effect_recipe_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "visibleEffectRowCount": summary.get("visibleEffectRowCount"),
        "blockedRecipeRowCount": summary.get("blockedRecipeRowCount"),
        "rowsWithEasing": summary.get("rowsWithEasing"),
        "rowsWithBgmHit": summary.get("rowsWithBgmHit"),
        "rowsWithLandingHold": summary.get("rowsWithLandingHold"),
        "maxRotationDegreesSeen": summary.get("maxRotationDegreesSeen"),
        "maxTranslatePercentSeen": summary.get("maxTranslatePercentSeen"),
        "maxScaleSeen": summary.get("maxScaleSeen"),
        "maxMotionBlurSeen": summary.get("maxMotionBlurSeen"),
        "maxRetimePercentSeen": summary.get("maxRetimePercentSeen"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_storyboard_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "visualBoundaryCount": summary.get("visualBoundaryCount"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "storyboardReadyRowCount": summary.get("storyboardReadyRowCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "importantStoryboardReadyCount": summary.get("importantStoryboardReadyCount"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_breathing_room_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
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
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_continuity_rehearsal_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "transitionBreathingRoomStatus": summary.get("transitionBreathingRoomStatus"),
        "sceneFlowArcStatus": summary.get("sceneFlowArcStatus"),
        "finalCutSmoothnessStatus": summary.get("finalCutSmoothnessStatus"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_pacing_watchability_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
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
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_narrative_adjacency_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
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
        "adjacentPairCount": summary.get("adjacentPairCount"),
        "motivatedPairCount": summary.get("motivatedPairCount"),
        "unmotivatedPairCount": summary.get("unmotivatedPairCount"),
        "blockedPairCount": summary.get("blockedPairCount"),
        "blockedChapterHandoffCount": summary.get("blockedChapterHandoffCount"),
        "payoffJumpWithoutBridgeCount": summary.get("payoffJumpWithoutBridgeCount"),
        "genericPairCount": summary.get("genericPairCount"),
        "unknownFunctionRatio": summary.get("unknownFunctionRatio"),
        "functionRunMax": summary.get("functionRunMax"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_viewer_orientation_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "transitionRowCount": summary.get("transitionRowCount"),
        "importantBoundaryCount": summary.get("importantBoundaryCount"),
        "viewerOrientationReadyCount": summary.get("viewerOrientationReadyCount"),
        "importantOrientationReadyCount": summary.get("importantOrientationReadyCount"),
        "blockedRowCount": summary.get("blockedRowCount"),
        "importantBlockedRowCount": summary.get("importantBlockedRowCount"),
        "routeCueImportantCount": summary.get("routeCueImportantCount"),
        "stableLandingImportantCount": summary.get("stableLandingImportantCount"),
        "narrativeReadyImportantCount": summary.get("narrativeReadyImportantCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_scene_settlement_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_scene_flow_arc_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
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
        "chapterCount": summary.get("chapterCount"),
        "chaptersPassed": summary.get("chaptersPassed"),
        "chaptersBlocked": summary.get("chaptersBlocked"),
        "blockedWindowCount": summary.get("blockedWindowCount"),
        "blockedHandoffCount": summary.get("blockedHandoffCount"),
        "weakOrUnclassifiedClipCount": summary.get("weakOrUnclassifiedClipCount"),
        "sameBeatRunMax": summary.get("sameBeatRunMax"),
        "payoffRunMax": summary.get("payoffRunMax"),
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_final_cut_smoothness_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
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
        "passedCheckCount": summary.get("passedCheckCount"),
        "blockedCheckCount": summary.get("blockedCheckCount"),
        "blockerCount": summary.get("blockerCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_preview_packet(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "previewRowCount": summary.get("previewRowCount"),
        "importantPreviewRowCount": summary.get("importantPreviewRowCount"),
        "readyPreviewRowCount": summary.get("readyPreviewRowCount"),
        "needsFrameExtractionRowCount": summary.get("needsFrameExtractionRowCount"),
        "blockedPreviewRowCount": summary.get("blockedPreviewRowCount"),
        "generatedFrameCount": summary.get("generatedFrameCount"),
        "ffmpegAvailable": summary.get("ffmpegAvailable"),
        "extractedFrames": summary.get("extractedFrames"),
        "updatedTransitionGrammar": summary.get("updatedTransitionGrammar"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_preview_quality_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "previewRowCount": summary.get("previewRowCount"),
        "importantPreviewRowCount": summary.get("importantPreviewRowCount"),
        "previewQualityReadyRowCount": summary.get("previewQualityReadyRowCount"),
        "blockedPreviewQualityRowCount": summary.get("blockedPreviewQualityRowCount"),
        "passedFrameCount": summary.get("passedFrameCount"),
        "blockedFrameCount": summary.get("blockedFrameCount"),
        "importantRowsWithOutgoingLanding": summary.get("importantRowsWithOutgoingLanding"),
        "warningCount": summary.get("warningCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_audition_packet(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "rowsWithDirectionalActionAnchor": summary.get("rowsWithDirectionalActionAnchor"),
        "ffmpegAvailable": summary.get("ffmpegAvailable"),
        "builtClips": summary.get("builtClips"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_audition_quality_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "rowsWithDirectionalActionAnchor": summary.get("rowsWithDirectionalActionAnchor"),
        "rowsWithResolveKeyframeEffect": summary.get("rowsWithResolveKeyframeEffect"),
        "warningCount": summary.get("warningCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_watch_reel(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "reelRowCount": summary.get("reelRowCount"),
        "importantReelRowCount": summary.get("importantReelRowCount"),
        "readyReelRowCount": summary.get("readyReelRowCount"),
        "blockedReelRowCount": summary.get("blockedReelRowCount"),
        "clipCount": summary.get("clipCount"),
        "packageLocalClipCount": summary.get("packageLocalClipCount"),
        "mutedClipCount": summary.get("mutedClipCount"),
        "rowsWithBridgeSamples": summary.get("rowsWithBridgeSamples"),
        "rowsWithMotionExecution": summary.get("rowsWithMotionExecution"),
        "rowsWithSensoryContinuity": summary.get("rowsWithSensoryContinuity"),
        "totalReelDurationSeconds": summary.get("totalReelDurationSeconds"),
        "reelBuilt": summary.get("reelBuilt"),
        "reelOutput": summary.get("reelOutput"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_audition_visual_proof_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "auditionVisualRowCount": summary.get("auditionVisualRowCount"),
        "passedAuditionVisualRowCount": summary.get("passedAuditionVisualRowCount"),
        "blockedAuditionVisualRowCount": summary.get("blockedAuditionVisualRowCount"),
        "rowsWithPackageLocalClip": summary.get("rowsWithPackageLocalClip"),
        "rowsWithProbeVideo": summary.get("rowsWithProbeVideo"),
        "rowsWithNoAudio": summary.get("rowsWithNoAudio"),
        "rowsWithFrameProof": summary.get("rowsWithFrameProof"),
        "rowsWithDistinctEndpointFrames": summary.get("rowsWithDistinctEndpointFrames"),
        "rowsWithMiddleMotionProof": summary.get("rowsWithMiddleMotionProof"),
        "rowsWithMotionExecution": summary.get("rowsWithMotionExecution"),
        "rowsWithResolveKeyframeEffect": summary.get("rowsWithResolveKeyframeEffect"),
        "transitionAuditionQualityStatus": summary.get("transitionAuditionQualityStatus"),
        "ffmpegAvailable": summary.get("ffmpegAvailable"),
        "ffprobeAvailable": summary.get("ffprobeAvailable"),
        "extractedFrames": summary.get("extractedFrames"),
        "frameCountPerRow": summary.get("frameCountPerRow"),
        "warningCount": summary.get("warningCount"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_transition_audition_role_integrity_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "auditionRoleRowCount": summary.get("auditionRoleRowCount"),
        "passedAuditionRoleRowCount": summary.get("passedAuditionRoleRowCount"),
        "blockedAuditionRoleRowCount": summary.get("blockedAuditionRoleRowCount"),
        "importantAuditionRoleRowCount": summary.get("importantAuditionRoleRowCount"),
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
        "warningCount": summary.get("warningCount"),
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


def summarize_skill_maturity_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "passedCheckCount": summary.get("passed"),
        "blockedCheckCount": summary.get("blocked"),
        "warningCheckCount": summary.get("warnings"),
        "totalCheckCount": summary.get("total"),
        "blockers": report.get("blockers") or [],
        "warnings": report.get("warnings") or [],
    }


def summarize_v14_baseline_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "passedCheckCount": summary.get("passed"),
        "blockedCheckCount": summary.get("blocked"),
        "totalCheckCount": summary.get("total"),
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


def summarize_unattended_repair_queue(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
        "requiredReportCount": summary.get("requiredReportCount"),
        "missingRequiredReportCount": summary.get("missingRequiredReportCount"),
        "blockedReportCount": summary.get("blockedReportCount"),
        "repairRowCount": summary.get("repairRowCount"),
        "p0RepairRowCount": summary.get("p0RepairRowCount"),
        "actionableRepairRowCount": summary.get("actionableRepairRowCount"),
        "unactionableRepairRowCount": summary.get("unactionableRepairRowCount"),
        "phaseCounts": summary.get("phaseCounts"),
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


def summarize_title_visual_proof_contract(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": report.get("status"),
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
        "blockers": report.get("blockers") or [],
    }


def summarize_title_typography_repair_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "repairRowCount": summary.get("repairRowCount"),
        "blockedReportCount": summary.get("blockedReportCount"),
        "missingReportCount": summary.get("missingReportCount"),
        "ownerScripts": summary.get("ownerScripts") or [],
        "blockers": [
            f"{row.get('repairId')}: {row.get('issue')}"
            for row in (plan.get("repairRows") or [])[:12]
            if isinstance(row, dict)
        ],
    }


def summarize_transition_flow_repair_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    summary = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
    return {
        "exists": True,
        "status": plan.get("status"),
        "repairRowCount": summary.get("repairRowCount"),
        "blockedReportCount": summary.get("blockedReportCount"),
        "missingReportCount": summary.get("missingReportCount"),
        "ownerScripts": summary.get("ownerScripts") or [],
        "sourceReportsWithRepairs": summary.get("sourceReportsWithRepairs") or [],
        "blockers": [
            f"{row.get('repairId')}: {row.get('issue')}"
            for row in (plan.get("repairRows") or [])[:16]
            if isinstance(row, dict)
        ],
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
    if report.get("sourceSelectionRepairSummary"):
        source_repair = report["sourceSelectionRepairSummary"]
        lines.extend(
            [
                "",
                "## Source Selection Repair Plan",
                f"- Status: `{source_repair.get('status')}`",
                f"- Chapters ready/total: {source_repair.get('readyChapterCount')} / {source_repair.get('chapterRowCount')}",
                f"- Candidates: {source_repair.get('candidateVideoCount')}",
                f"- Hero/movement/texture/payoff: {source_repair.get('heroCandidateCount')} / {source_repair.get('movementBridgeCandidateCount')} / {source_repair.get('livedInTextureCandidateCount')} / {source_repair.get('destinationPayoffCandidateCount')}",
                f"- Blocking/warning repairs: {source_repair.get('blockingRepairRowCount')} / {source_repair.get('warningRepairRowCount')}",
            ]
        )
    if report.get("sourceSelectionCoverageSummary"):
        source_coverage = report["sourceSelectionCoverageSummary"]
        lines.extend(
            [
                "",
                "## Source Selection Coverage Audit",
                f"- Status: `{source_coverage.get('status')}`",
                f"- Ready chapters: {source_coverage.get('readyChapterCount')} / {source_coverage.get('chapterRowCount')}",
                f"- Blocked checks: {source_coverage.get('blockedCheckCount')}",
                f"- Blocking/warning repairs: {source_coverage.get('blockingRepairRowCount')} / {source_coverage.get('warningRepairRowCount')}",
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
    if report.get("bgmMusicalitySummary"):
        bgm_music = report["bgmMusicalitySummary"]
        lines.extend(
            [
                "",
                "## BGM Musicality Contract",
                f"- Exists: `{bgm_music.get('exists')}`",
                f"- Status: `{bgm_music.get('status')}`",
                f"- Named/license tracks: {bgm_music.get('namedTrackCount')} / {bgm_music.get('licenseTrackCount')}",
                f"- Dynamic range dB: {bgm_music.get('dynamicRangeDb')}",
                f"- Active bands: {bgm_music.get('activeBandCount')}",
                f"- Single-band dominance: {bgm_music.get('singleBandDominance')}",
                f"- Bad identity terms: `{bgm_music.get('badIdentityTerms')}`",
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
    if report.get("referenceReviewRepairSummary"):
        reference_review = report["referenceReviewRepairSummary"]
        lines.extend(
            [
                "",
                "## Reference Review Repair Plan",
                f"- Exists: `{reference_review.get('exists')}`",
                f"- Status: `{reference_review.get('status')}`",
                f"- Repair rows: {reference_review.get('repairRowCount')}",
                f"- Reference videos: {reference_review.get('referenceVideoCount')}",
                f"- Closed full-review decisions: {reference_review.get('closedFullReviewDecisionCount')}",
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
                f"- Reference selections applied: {execution_blueprint.get('rowsWithAppliedReferenceSelection')} / {execution_blueprint.get('executionRowCount')}",
                f"- Selection blockers: {execution_blueprint.get('blockedReferenceSelectionRowCount')}",
                f"- Motion execution applied: {execution_blueprint.get('rowsWithMotionExecution')} / {execution_blueprint.get('executionRowCount')}",
                f"- Three-beat/BGM/title-safe rows: {execution_blueprint.get('rowsWithThreeBeatMotion')} / {execution_blueprint.get('rowsWithBgmHitMotion')} / {execution_blueprint.get('rowsWithCaptionQuietMotion')}",
                f"- Motion direction rows: {execution_blueprint.get('rowsWithMotionDirectionPlan')} / {execution_blueprint.get('rowsWithMotionDirectionMatch')}",
                f"- Cutpoint ready rows: {execution_blueprint.get('rowsWithCutpointReady')} / {execution_blueprint.get('executionRowCount')}",
                f"- Cutpoint BGM/landing/handle rows: {execution_blueprint.get('rowsWithCutpointBgmHit')} / {execution_blueprint.get('rowsWithCutpointLandingHold')} / {execution_blueprint.get('rowsWithCutpointHandles')}",
                f"- Action-anchor ready rows: {execution_blueprint.get('rowsWithActionAnchorReady')} / {execution_blueprint.get('executionRowCount')}",
                f"- Action-anchor outgoing/bridge/landing rows: {execution_blueprint.get('rowsWithOutgoingActionAnchor')} / {execution_blueprint.get('rowsWithBridgeOrMatchActionAnchor')} / {execution_blueprint.get('rowsWithLandingActionAnchor')}",
                f"- Sensory continuity ready rows: {execution_blueprint.get('rowsWithSensoryContinuityReady')} / {execution_blueprint.get('executionRowCount')}",
                f"- Sensory visual/audio/caption rows: {execution_blueprint.get('rowsWithVisualSensoryContinuity')} / {execution_blueprint.get('rowsWithAudioSensoryContinuity')} / {execution_blueprint.get('rowsWithCaptionSensoryContinuity')}",
                f"- Motion blockers: {execution_blueprint.get('blockedMotionExecutionRowCount')}",
                f"- Cutpoint blockers: {execution_blueprint.get('blockedCutpointRowCount')}",
                f"- Action-anchor blockers: {execution_blueprint.get('blockedActionAnchorRowCount')}",
                f"- Sensory continuity blockers: {execution_blueprint.get('blockedSensoryContinuityRowCount')}",
                f"- Blocked rows: {execution_blueprint.get('blockedRowCount')}",
                f"- Missing clip matches: {execution_blueprint.get('rowsMissingClipMatch')}",
            ]
        )
    if report.get("transitionCutpointSummary"):
        cutpoint = report["transitionCutpointSummary"]
        lines.extend(
            [
                "",
                "## Transition Cutpoint Contract",
                f"- Exists: `{cutpoint.get('exists')}`",
                f"- Status: `{cutpoint.get('status')}`",
                f"- Ready rows: {cutpoint.get('readyCutpointRowCount')} / {cutpoint.get('transitionRowCount')}",
                f"- Outgoing/bridge/landing rows: {cutpoint.get('rowsWithOutgoingTail')} / {cutpoint.get('rowsWithBridgeOrEffectHit')} / {cutpoint.get('rowsWithLandingHold')}",
                f"- BGM/title/audio rows: {cutpoint.get('rowsWithBgmHit')} / {cutpoint.get('rowsWithTitleSubtitleQuietZone')} / {cutpoint.get('rowsWithBgmOnlyNoSourceVoice')}",
                f"- Important resolved rows: {cutpoint.get('importantRowsResolved')} / {cutpoint.get('importantBoundaryCount')}",
            ]
        )
    if report.get("transitionActionAnchorSummary"):
        anchor = report["transitionActionAnchorSummary"]
        lines.extend(
            [
                "",
                "## Transition Action Anchor Contract",
                f"- Exists: `{anchor.get('exists')}`",
                f"- Status: `{anchor.get('status')}`",
                f"- Ready rows: {anchor.get('readyActionAnchorRowCount')} / {anchor.get('transitionRowCount')}",
                f"- Outgoing/bridge/landing rows: {anchor.get('rowsWithOutgoingActionAnchor')} / {anchor.get('rowsWithBridgeOrMatchActionAnchor')} / {anchor.get('rowsWithLandingActionAnchor')}",
                f"- Directional motion rows: {anchor.get('rowsWithDirectionalMotionAnchor')} / {anchor.get('motionAnchorRowCount')}",
                f"- Important resolved rows: {anchor.get('importantRowsResolved')} / {anchor.get('importantBoundaryCount')}",
            ]
        )
    if report.get("transitionSensoryContinuitySummary"):
        sensory = report["transitionSensoryContinuitySummary"]
        lines.extend(
            [
                "",
                "## Transition Sensory Continuity Contract",
                f"- Exists: `{sensory.get('exists')}`",
                f"- Status: `{sensory.get('status')}`",
                f"- Ready rows: {sensory.get('readySensoryContinuityRowCount')} / {sensory.get('transitionRowCount')}",
                f"- Visual/audio/caption rows: {sensory.get('rowsWithVisualSensoryContinuity')} / {sensory.get('rowsWithAudioSensoryContinuity')} / {sensory.get('rowsWithCaptionSensoryContinuity')}",
                f"- Route-or-mood/landing rows: {sensory.get('rowsWithRouteOrMoodSensoryContinuity')} / {sensory.get('rowsWithLandingSensoryContinuity')}",
                f"- Motion rows: {sensory.get('rowsWithMotionSensoryContinuity')} / {sensory.get('motionSensoryRowCount')}",
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
    if report.get("transitionEffectRecipeSummary"):
        recipe = report["transitionEffectRecipeSummary"]
        lines.extend(
            [
                "",
                "## Transition Effect Recipe Contract",
                f"- Exists: `{recipe.get('exists')}`",
                f"- Status: `{recipe.get('status')}`",
                f"- Transition rows / visible effects: {recipe.get('transitionRowCount')} / {recipe.get('visibleEffectRowCount')}",
                f"- Blocked recipe rows / blockers: {recipe.get('blockedRecipeRowCount')} / {recipe.get('blockerCount')}",
                f"- Easing/BGM-hit/landing rows: {recipe.get('rowsWithEasing')} / {recipe.get('rowsWithBgmHit')} / {recipe.get('rowsWithLandingHold')}",
                f"- Max rotation/translate/scale/blur/retime: {recipe.get('maxRotationDegreesSeen')} / {recipe.get('maxTranslatePercentSeen')} / {recipe.get('maxScaleSeen')} / {recipe.get('maxMotionBlurSeen')} / {recipe.get('maxRetimePercentSeen')}",
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
    if report.get("transitionSourceCoverageSummary"):
        source_coverage = report["transitionSourceCoverageSummary"]
        lines.extend(
            [
                "",
                "## Transition Source Coverage Contract",
                f"- Exists: `{source_coverage.get('exists')}`",
                f"- Status: `{source_coverage.get('status')}`",
                f"- Ready/blocked rows: {source_coverage.get('readySourceCoverageRowCount')} / {source_coverage.get('blockedSourceCoverageRowCount')}",
                f"- Important boundaries: {source_coverage.get('importantBoundaryCount')}",
                f"- Motion transitions: {source_coverage.get('motionTransitionCount')}",
                f"- Bridge/motion source ready: {source_coverage.get('bridgeReadyRowCount')} / {source_coverage.get('motionSourceReadyRowCount')}",
                f"- Blocked checks: {source_coverage.get('blockedCheckCount')}",
            ]
        )
    if report.get("resolveTransitionApplySummary"):
        transition_apply = report["resolveTransitionApplySummary"]
        lines.extend(
            [
                "",
                "## Resolve Transition Apply Contract",
                f"- Exists: `{transition_apply.get('exists')}`",
                f"- Status: `{transition_apply.get('status')}`",
                f"- Apply/materialization status: `{transition_apply.get('applyPlanStatus')}` / `{transition_apply.get('materializationStatus')}`",
                f"- Passed/blocked rows: {transition_apply.get('passedRowCount')} / {transition_apply.get('blockedRowCount')}",
                f"- Visible effects/apply paths: {transition_apply.get('visibleEffectRowCount')} / {transition_apply.get('visibleEffectRowsWithApplyPath')}",
                f"- Pending manual visible effects: {transition_apply.get('pendingManualVisibleEffectRowCount')}",
                f"- Manual evidence/bridge evidence ready: {transition_apply.get('manualResolveEvidenceReadyRowCount')} / {transition_apply.get('fallbackBridgeEvidenceReadyRowCount')}",
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
    if report.get("skillMaturitySummary"):
        maturity = report["skillMaturitySummary"]
        lines.extend(
            [
                "",
                "## Skill Maturity Contract",
                f"- Exists: `{maturity.get('exists')}`",
                f"- Status: `{maturity.get('status')}`",
                f"- Passed/blocked/warning checks: {maturity.get('passedCheckCount')} / {maturity.get('blockedCheckCount')} / {maturity.get('warningCheckCount')}",
                f"- Total checks: {maturity.get('totalCheckCount')}",
            ]
        )
    if report.get("v14BaselineSummary"):
        v14 = report["v14BaselineSummary"]
        lines.extend(
            [
                "",
                "## V14 Baseline Contract",
                f"- Exists: `{v14.get('exists')}`",
                f"- Status: `{v14.get('status')}`",
                f"- Passed/blocked checks: {v14.get('passedCheckCount')} / {v14.get('blockedCheckCount')}",
                f"- Total checks: {v14.get('totalCheckCount')}",
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

    source_selection_repair_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_source_selection_repair_plan.py"),
        "--package-dir",
        str(package_dir),
        "--project-dir",
        str(project_dir),
        "--json",
    ]
    steps.append(run_step("prepare_source_selection_repair_plan", source_selection_repair_cmd, ok_codes={0, 2}))

    source_selection_audit_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_source_selection_coverage_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_source_selection_coverage_contract", source_selection_audit_cmd, ok_codes={0, 2}))

    first_assembly_source_order_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_first_assembly_source_order_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_first_assembly_source_order_contract", first_assembly_source_order_cmd, ok_codes={0, 2}))

    large_source_unattended_readiness_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_large_source_unattended_readiness_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_large_source_unattended_readiness_contract", large_source_unattended_readiness_cmd, ok_codes={0, 2}))

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

        reference_review_repair_cmd = [
            "python3",
            str(SCRIPTS_DIR / "prepare_reference_review_repair_plan.py"),
            "--package-dir",
            str(package_dir),
            "--json",
        ]
        steps.append(run_step("prepare_reference_review_repair_plan", reference_review_repair_cmd, ok_codes={0}))

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

    title_visual_proof_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_title_visual_proof_contract.py"),
        "--package-dir",
        str(package_dir),
        "--extract-frames",
        "--json",
    ]
    steps.append(run_step("audit_title_visual_proof_contract", title_visual_proof_cmd, ok_codes={0, 2}))

    title_repair_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_title_typography_repair_plan.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("prepare_title_typography_repair_plan", title_repair_cmd, ok_codes={0, 2}))

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

    transition_reference_candidates_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_reference_candidates.py"),
        "--package-dir",
        str(package_dir),
    ]
    steps.append(run_step("prepare_transition_reference_candidates", transition_reference_candidates_cmd, ok_codes={0, 2}))

    transition_reference_selection_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_reference_selection.py"),
        "--package-dir",
        str(package_dir),
    ]
    steps.append(run_step("prepare_transition_reference_selection", transition_reference_selection_cmd, ok_codes={0, 2}))

    transition_motif_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_motif_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_transition_motif_plan", transition_motif_cmd, ok_codes={0, 2}))

    bridge_sequence_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bridge_sequence_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_bridge_sequence_plan", bridge_sequence_cmd, ok_codes={0, 2}))

    bridge_sequence_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bridge_sequence_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_bridge_sequence_blueprint", bridge_sequence_blueprint_cmd, ok_codes={0, 2}))

    transition_choreography_plan_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_choreography_plan.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("prepare_transition_choreography_plan", transition_choreography_plan_cmd, ok_codes={0, 2}))

    transition_execution_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_transition_execution_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_transition_execution_blueprint", transition_execution_blueprint_cmd, ok_codes={0, 2}))

    transition_cutpoint_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_cutpoint_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_cutpoint_contract", transition_cutpoint_cmd, ok_codes={0, 2}))

    transition_action_anchor_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_action_anchor_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_action_anchor_contract", transition_action_anchor_cmd, ok_codes={0, 2}))

    transition_sensory_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_sensory_continuity_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_sensory_continuity_contract", transition_sensory_cmd, ok_codes={0, 2}))

    effect_motion_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_effect_motion_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_effect_motion_blueprint", effect_motion_blueprint_cmd, ok_codes={0, 2}))

    bgm_phrase_blueprint_cmd = ["python3", str(SCRIPTS_DIR / "prepare_bgm_phrase_blueprint.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_bgm_phrase_blueprint", bgm_phrase_blueprint_cmd, ok_codes={0, 2}))

    bgm_musicality_cmd = ["python3", str(SCRIPTS_DIR / "audit_bgm_musicality_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_bgm_musicality_contract", bgm_musicality_cmd, ok_codes={0, 2}))

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

    resolve_transition_materialization_cmd = ["python3", str(SCRIPTS_DIR / "audit_resolve_transition_materialization_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_resolve_transition_materialization_contract", resolve_transition_materialization_cmd, ok_codes={0, 2}))

    resolve_transition_apply_plan_cmd = ["python3", str(SCRIPTS_DIR / "prepare_resolve_transition_apply_plan.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("prepare_resolve_transition_apply_plan", resolve_transition_apply_plan_cmd, ok_codes={0, 2}))

    resolve_transition_apply_contract_cmd = ["python3", str(SCRIPTS_DIR / "audit_resolve_transition_apply_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_resolve_transition_apply_contract", resolve_transition_apply_contract_cmd, ok_codes={0, 2}))

    bridge_sequence_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_bridge_sequence_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_bridge_sequence_application_contract", bridge_sequence_application_cmd, ok_codes={0, 2}))

    transition_bridge_visual_evidence_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_bridge_visual_evidence_contract.py"),
        "--package-dir",
        str(package_dir),
        "--extract-frames",
        "--json",
    ]
    steps.append(run_step("audit_transition_bridge_visual_evidence_contract", transition_bridge_visual_evidence_cmd, ok_codes={0, 2}))

    final_blueprint_lineage_cmd = ["python3", str(SCRIPTS_DIR / "audit_final_blueprint_lineage_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_final_blueprint_lineage_contract", final_blueprint_lineage_cmd, ok_codes={0, 2}))

    effect_motion_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_effect_motion_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_effect_motion_application_contract", effect_motion_application_cmd, ok_codes={0, 2}))

    transition_cadence_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_cadence_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_cadence_contract", transition_cadence_cmd, ok_codes={0, 2}))

    transition_microstructure_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_microstructure_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_microstructure_contract", transition_microstructure_cmd, ok_codes={0, 2}))

    final_source_usage_cmd = ["python3", str(SCRIPTS_DIR / "audit_final_source_usage_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_final_source_usage_contract", final_source_usage_cmd, ok_codes={0, 2}))

    creator_cut_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_creator_cut_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_creator_cut_application_contract", creator_cut_application_cmd, ok_codes={0, 2}))

    rhythm_recut_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_rhythm_recut_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_rhythm_recut_application_contract", rhythm_recut_application_cmd, ok_codes={0, 2}))

    reference_scene_grammar_cmd = ["python3", str(SCRIPTS_DIR / "audit_reference_scene_grammar_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_reference_scene_grammar_contract", reference_scene_grammar_cmd, ok_codes={0, 2}))

    reference_profile_application_cmd = ["python3", str(SCRIPTS_DIR / "audit_reference_profile_application_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_reference_profile_application_contract", reference_profile_application_cmd, ok_codes={0, 2}))

    timeline_variety_cmd = ["python3", str(SCRIPTS_DIR / "audit_timeline_variety_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_timeline_variety_contract", timeline_variety_cmd, ok_codes={0, 2}))

    transition_scene_arc_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_scene_arc_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_scene_arc_contract", transition_scene_arc_cmd, ok_codes={0, 2}))

    transition_effect_palette_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_effect_palette_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_effect_palette_contract", transition_effect_palette_cmd, ok_codes={0, 2}))

    transition_motif_coherence_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_motif_coherence_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_motif_coherence_contract", transition_motif_coherence_cmd, ok_codes={0, 2}))

    transition_visual_match_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_visual_match_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_visual_match_contract", transition_visual_match_cmd, ok_codes={0, 2}))

    transition_source_coverage_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_source_coverage_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_source_coverage_contract", transition_source_coverage_cmd, ok_codes={0, 2}))

    transition_choreography_contract_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_choreography_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_choreography_contract", transition_choreography_contract_cmd, ok_codes={0, 2}))

    transition_motion_direction_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_motion_direction_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_motion_direction_contract", transition_motion_direction_cmd, ok_codes={0, 2}))

    transition_preview_packet_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_preview_packet.py"),
        "--package-dir",
        str(package_dir),
        "--extract-frames",
        "--update-transition-grammar",
        "--json",
    ]
    steps.append(run_step("prepare_transition_preview_packet", transition_preview_packet_cmd, ok_codes={0, 2}))

    transition_preview_quality_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_preview_quality_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_preview_quality_contract", transition_preview_quality_cmd, ok_codes={0, 2}))

    transition_audition_packet_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_audition_packet.py"),
        "--package-dir",
        str(package_dir),
        "--build-clips",
        "--json",
    ]
    steps.append(run_step("prepare_transition_audition_packet", transition_audition_packet_cmd, ok_codes={0, 2}))

    transition_audition_quality_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_audition_quality_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_audition_quality_contract", transition_audition_quality_cmd, ok_codes={0, 2}))

    transition_watch_reel_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_watch_reel.py"),
        "--package-dir",
        str(package_dir),
        "--build-reel",
        "--json",
    ]
    steps.append(run_step("prepare_transition_watch_reel", transition_watch_reel_cmd, ok_codes={0, 2}))

    transition_audition_visual_proof_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_audition_visual_proof_contract.py"),
        "--package-dir",
        str(package_dir),
        "--extract-frames",
        "--json",
    ]
    steps.append(run_step("audit_transition_audition_visual_proof_contract", transition_audition_visual_proof_cmd, ok_codes={0, 2}))

    transition_audition_role_integrity_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_audition_role_integrity_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_audition_role_integrity_contract", transition_audition_role_integrity_cmd, ok_codes={0, 2}))

    transition_motion_accent_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_motion_accent_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_motion_accent_contract", transition_motion_accent_cmd, ok_codes={0, 2}))

    transition_motion_accent_repair_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_motion_accent_repair_plan.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("prepare_transition_motion_accent_repair_plan", transition_motion_accent_repair_cmd, ok_codes={0, 2}))

    transition_effect_recipe_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_effect_recipe_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_effect_recipe_contract", transition_effect_recipe_cmd, ok_codes={0, 2}))

    transition_storyboard_cmd = ["python3", str(SCRIPTS_DIR / "audit_transition_storyboard_contract.py"), "--package-dir", str(package_dir), "--json"]
    steps.append(run_step("audit_transition_storyboard_contract", transition_storyboard_cmd, ok_codes={0, 2}))

    reference_transition_profile_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_reference_transition_profile_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_reference_transition_profile_contract", reference_transition_profile_cmd, ok_codes={0, 2}))

    chapter_story_spine_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_chapter_story_spine_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_chapter_story_spine_contract", chapter_story_spine_cmd, ok_codes={0, 2}))

    shot_flow_continuity_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_shot_flow_continuity_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_shot_flow_continuity_contract", shot_flow_continuity_cmd, ok_codes={0, 2}))

    transition_breathing_room_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_breathing_room_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_breathing_room_contract", transition_breathing_room_cmd, ok_codes={0, 2}))

    scene_flow_arc_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_scene_flow_arc_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_scene_flow_arc_contract", scene_flow_arc_cmd, ok_codes={0, 2}))

    final_cut_smoothness_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_final_cut_smoothness_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_final_cut_smoothness_contract", final_cut_smoothness_cmd, ok_codes={0, 2}))

    transition_continuity_rehearsal_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_continuity_rehearsal_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_continuity_rehearsal_contract", transition_continuity_rehearsal_cmd, ok_codes={0, 2}))

    pacing_watchability_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_pacing_watchability_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_pacing_watchability_contract", pacing_watchability_cmd, ok_codes={0, 2}))

    narrative_adjacency_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_narrative_adjacency_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_narrative_adjacency_contract", narrative_adjacency_cmd, ok_codes={0, 2}))

    transition_viewer_orientation_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_viewer_orientation_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_viewer_orientation_contract", transition_viewer_orientation_cmd, ok_codes={0, 2}))

    transition_scene_settlement_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_transition_scene_settlement_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_transition_scene_settlement_contract", transition_scene_settlement_cmd, ok_codes={0, 2}))

    transition_flow_repair_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_transition_flow_repair_plan.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("prepare_transition_flow_repair_plan", transition_flow_repair_cmd, ok_codes={0, 2}))

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

    editorial_watchdown_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_editorial_watchdown_repair_plan.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("prepare_editorial_watchdown_repair_plan", editorial_watchdown_cmd, ok_codes={0}))

    unattended_repair_queue_cmd = [
        "python3",
        str(SCRIPTS_DIR / "prepare_unattended_repair_queue.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("prepare_unattended_repair_queue", unattended_repair_queue_cmd, ok_codes={0, 2}))

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

    skill_maturity_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_skill_maturity_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_skill_maturity_contract", skill_maturity_cmd, ok_codes={0, 2}))

    v14_baseline_cmd = [
        "python3",
        str(SCRIPTS_DIR / "audit_v14_baseline_contract.py"),
        "--package-dir",
        str(package_dir),
        "--json",
    ]
    steps.append(run_step("audit_v14_baseline_contract", v14_baseline_cmd, ok_codes={0, 2}))

    return finish_report(args, started, steps, package_dir)


def finish_report(args: argparse.Namespace, started: str, steps: list[dict[str, Any]], package_dir: Path | None, status: str | None = None) -> dict[str, Any]:
    ended = datetime.now().isoformat(timespec="seconds")
    project_state_summary = None
    resolve_api_summary = None
    route_decision_summary = None
    route_decision_application_summary = None
    footage_select_summary = None
    raw_intake_completeness_summary = None
    source_selection_repair_summary = None
    source_selection_coverage_summary = None
    first_assembly_source_order_summary = None
    large_source_unattended_readiness_summary = None
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
    title_visual_proof_summary = None
    title_typography_repair_summary = None
    visual_establishing_summary = None
    effect_motion_summary = None
    effect_motion_blueprint_summary = None
    bgm_phrase_blueprint_summary = None
    bgm_musicality_summary = None
    feedback_regression_plan_summary = None
    reference_batch_summary = None
    reference_review_repair_summary = None
    audio_scene_policy_summary = None
    edit_rhythm_summary = None
    creator_cut_summary = None
    transition_grammar_summary = None
    transition_execution_summary = None
    transition_reference_candidates_summary = None
    transition_reference_selection_summary = None
    transition_execution_blueprint_summary = None
    transition_cutpoint_summary = None
    transition_action_anchor_summary = None
    transition_sensory_continuity_summary = None
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
    resolve_transition_materialization_summary = None
    resolve_transition_apply_summary = None
    bridge_sequence_application_summary = None
    transition_bridge_visual_evidence_summary = None
    final_blueprint_lineage_summary = None
    effect_motion_application_summary = None
    transition_cadence_summary = None
    transition_microstructure_summary = None
    final_source_usage_summary = None
    creator_cut_application_summary = None
    rhythm_recut_application_summary = None
    reference_scene_grammar_summary = None
    reference_profile_application_summary = None
    timeline_variety_summary = None
    transition_scene_arc_summary = None
    transition_effect_palette_summary = None
    transition_motif_coherence_summary = None
    transition_visual_match_summary = None
    transition_source_coverage_summary = None
    transition_choreography_plan_summary = None
    transition_choreography_contract_summary = None
    transition_motion_direction_summary = None
    transition_preview_packet_summary = None
    transition_preview_quality_summary = None
    transition_audition_packet_summary = None
    transition_audition_quality_summary = None
    transition_watch_reel_summary = None
    transition_audition_visual_proof_summary = None
    transition_audition_role_integrity_summary = None
    transition_motion_accent_summary = None
    transition_effect_recipe_summary = None
    transition_storyboard_summary = None
    reference_transition_profile_summary = None
    chapter_story_spine_summary = None
    shot_flow_continuity_summary = None
    transition_breathing_room_summary = None
    transition_continuity_rehearsal_summary = None
    pacing_watchability_summary = None
    narrative_adjacency_summary = None
    transition_viewer_orientation_summary = None
    transition_scene_settlement_summary = None
    transition_flow_repair_summary = None
    scene_flow_arc_summary = None
    final_cut_smoothness_summary = None
    unattended_first_draft_summary = None
    reference_style_repair_summary = None
    reference_repair_closure_summary = None
    editorial_watchdown_summary = None
    unattended_repair_queue_summary = None
    rhythm_recut_apply_summary = None
    skill_maturity_summary = None
    v14_baseline_summary = None
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
        if step["id"] == "prepare_source_selection_repair_plan":
            source_selection_repair_summary = summarize_source_selection_repair_plan(payload)
            if source_selection_repair_summary and source_selection_repair_summary.get("status") == "blocked_source_selection_coverage_needs_repair":
                blockers.append(
                    "Source selection coverage blocker: close source_selection_repair_plan.json blocking repair rows before trusting the first assembly."
                )
            if source_selection_repair_summary and int(source_selection_repair_summary.get("warningRepairRowCount") or 0) > 0:
                warnings.append(
                    "Source selection coverage warning: close orientation/repair warning rows before final source usage approval."
                )
        if step["id"] == "audit_source_selection_coverage_contract":
            source_selection_coverage_summary = summarize_source_selection_coverage_contract(payload)
            if source_selection_coverage_summary and source_selection_coverage_summary.get("status") == "blocked":
                blockers.extend(
                    f"Source selection coverage audit blocker: {item}"
                    for item in source_selection_coverage_summary.get("blockers") or []
                )
            if source_selection_coverage_summary and source_selection_coverage_summary.get("warnings"):
                warnings.extend(
                    f"Source selection coverage warning: {item}"
                    for item in source_selection_coverage_summary.get("warnings") or []
                )
        if step["id"] == "audit_first_assembly_source_order_contract":
            first_assembly_source_order_summary = summarize_first_assembly_source_order_contract(payload)
            if first_assembly_source_order_summary and first_assembly_source_order_summary.get("status") == "blocked":
                blockers.extend(
                    f"First assembly source order blocker: {item}"
                    for item in first_assembly_source_order_summary.get("blockers") or []
                )
            if first_assembly_source_order_summary and first_assembly_source_order_summary.get("warnings"):
                warnings.extend(
                    f"First assembly source order warning: {item}"
                    for item in first_assembly_source_order_summary.get("warnings") or []
                )
        if step["id"] == "audit_large_source_unattended_readiness_contract":
            large_source_unattended_readiness_summary = summarize_large_source_unattended_readiness_contract(payload)
            if large_source_unattended_readiness_summary and large_source_unattended_readiness_summary.get("status") == "blocked":
                blockers.extend(
                    f"Large source unattended readiness blocker: {item}"
                    for item in large_source_unattended_readiness_summary.get("blockers") or []
                )
            if large_source_unattended_readiness_summary and large_source_unattended_readiness_summary.get("warnings"):
                warnings.extend(
                    f"Large source unattended readiness warning: {item}"
                    for item in large_source_unattended_readiness_summary.get("warnings") or []
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
        if step["id"] == "audit_title_visual_proof_contract":
            title_visual_proof_summary = summarize_title_visual_proof_contract(payload)
            if title_visual_proof_summary and title_visual_proof_summary.get("status") == "blocked":
                blockers.extend(f"Title visual proof blocker: {item}" for item in title_visual_proof_summary.get("blockers") or [])
        if step["id"] == "prepare_title_typography_repair_plan":
            title_typography_repair_summary = summarize_title_typography_repair_plan(payload)
            if (
                title_typography_repair_summary
                and title_typography_repair_summary.get("status") == "ready_with_title_typography_repair_plan"
            ):
                blockers.extend(
                    f"Title typography repair blocker: {item}"
                    for item in title_typography_repair_summary.get("blockers") or []
                )
        if step["id"] == "prepare_visual_establishing_plan":
            visual_establishing_summary = summarize_visual_establishing_plan(payload)
        if step["id"] == "prepare_effect_motion_plan":
            effect_motion_summary = summarize_effect_motion_plan(payload)
        if step["id"] == "prepare_effect_motion_blueprint":
            effect_motion_blueprint_summary = summarize_effect_motion_blueprint(payload)
        if step["id"] == "prepare_bgm_phrase_blueprint":
            bgm_phrase_blueprint_summary = summarize_bgm_phrase_blueprint(payload)
        if step["id"] == "audit_bgm_musicality_contract":
            bgm_musicality_summary = summarize_bgm_musicality_contract(payload)
            if bgm_musicality_summary and bgm_musicality_summary.get("status") == "blocked":
                blockers.extend(f"BGM musicality blocker: {item}" for item in bgm_musicality_summary.get("blockers") or [])
            if bgm_musicality_summary and bgm_musicality_summary.get("warnings"):
                warnings.extend(f"BGM musicality warning: {item}" for item in bgm_musicality_summary.get("warnings") or [])
        if step["id"] == "prepare_feedback_regression_plan":
            feedback_regression_plan_summary = summarize_feedback_regression_plan(payload)
        if step["id"] == "prepare_reference_batch_profile":
            reference_batch_summary = summarize_reference_batch_profile(payload)
        if step["id"] == "prepare_reference_review_repair_plan":
            reference_review_repair_summary = summarize_reference_review_repair_plan(payload)
            if reference_review_repair_summary and reference_review_repair_summary.get("status") != "ready_no_reference_review_repairs_needed":
                blockers.append(
                    f"Reference review repair blocker: {reference_review_repair_summary.get('repairRowCount')} full-reference review rows remain open"
                )
        if step["id"] == "prepare_editorial_watchdown_repair_plan":
            editorial_watchdown_summary = summarize_editorial_watchdown_repair_plan(payload)
            if editorial_watchdown_summary and editorial_watchdown_summary.get("status") != "ready_no_editorial_watchdown_repairs_needed":
                blockers.append(
                    f"Editorial watchdown blocker: {editorial_watchdown_summary.get('repairRowCount')} final viewer-review rows remain open"
                )
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
        if step["id"] == "prepare_transition_reference_candidates":
            transition_reference_candidates_summary = summarize_transition_reference_candidates(payload)
            if transition_reference_candidates_summary and str(transition_reference_candidates_summary.get("status") or "").startswith("blocked"):
                blockers.append("Transition reference candidates are blocked; run transition grammar/execution before motif, preview, or Resolve apply.")
        if step["id"] == "prepare_transition_reference_selection":
            transition_reference_selection_summary = summarize_transition_reference_selection(payload)
            if transition_reference_selection_summary and str(transition_reference_selection_summary.get("status") or "").startswith("blocked"):
                blockers.append("Transition reference selection is blocked; repair bridge/title-breath rows before preview, storyboard, or Resolve apply.")
        if step["id"] == "prepare_transition_execution_blueprint":
            transition_execution_blueprint_summary = summarize_transition_execution_blueprint(payload)
        if step["id"] == "audit_transition_cutpoint_contract":
            transition_cutpoint_summary = summarize_transition_cutpoint_contract(payload)
            if transition_cutpoint_summary and transition_cutpoint_summary.get("status") == "blocked":
                blockers.extend(f"Transition cutpoint blocker: {item}" for item in transition_cutpoint_summary.get("blockers") or [])
            if transition_cutpoint_summary and transition_cutpoint_summary.get("warnings"):
                warnings.extend(f"Transition cutpoint warning: {item}" for item in transition_cutpoint_summary.get("warnings") or [])
        if step["id"] == "audit_transition_action_anchor_contract":
            transition_action_anchor_summary = summarize_transition_action_anchor_contract(payload)
            if transition_action_anchor_summary and transition_action_anchor_summary.get("status") == "blocked":
                blockers.extend(f"Transition action-anchor blocker: {item}" for item in transition_action_anchor_summary.get("blockers") or [])
            if transition_action_anchor_summary and transition_action_anchor_summary.get("warnings"):
                warnings.extend(f"Transition action-anchor warning: {item}" for item in transition_action_anchor_summary.get("warnings") or [])
        if step["id"] == "audit_transition_sensory_continuity_contract":
            transition_sensory_continuity_summary = summarize_transition_sensory_continuity_contract(payload)
            if transition_sensory_continuity_summary and transition_sensory_continuity_summary.get("status") == "blocked":
                blockers.extend(f"Transition sensory-continuity blocker: {item}" for item in transition_sensory_continuity_summary.get("blockers") or [])
            if transition_sensory_continuity_summary and transition_sensory_continuity_summary.get("warnings"):
                warnings.extend(f"Transition sensory-continuity warning: {item}" for item in transition_sensory_continuity_summary.get("warnings") or [])
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
        if step["id"] == "audit_resolve_transition_materialization_contract":
            resolve_transition_materialization_summary = summarize_resolve_transition_materialization_contract(payload)
            if resolve_transition_materialization_summary and resolve_transition_materialization_summary.get("status") == "blocked":
                blockers.extend(f"Resolve transition materialization blocker: {item}" for item in resolve_transition_materialization_summary.get("blockers") or [])
            if resolve_transition_materialization_summary and resolve_transition_materialization_summary.get("warnings"):
                warnings.extend(f"Resolve transition materialization warning: {item}" for item in resolve_transition_materialization_summary.get("warnings") or [])
        if step["id"] in {"prepare_resolve_transition_apply_plan", "audit_resolve_transition_apply_contract"}:
            resolve_transition_apply_summary = summarize_resolve_transition_apply_contract(payload)
            if resolve_transition_apply_summary and str(resolve_transition_apply_summary.get("status") or "").startswith("blocked"):
                blockers.extend(f"Resolve transition apply blocker: {item}" for item in resolve_transition_apply_summary.get("blockers") or [])
            if resolve_transition_apply_summary and resolve_transition_apply_summary.get("warnings"):
                warnings.extend(f"Resolve transition apply warning: {item}" for item in resolve_transition_apply_summary.get("warnings") or [])
        if step["id"] == "audit_bridge_sequence_application_contract":
            bridge_sequence_application_summary = summarize_bridge_sequence_application_contract(payload)
            if bridge_sequence_application_summary and bridge_sequence_application_summary.get("status") == "blocked":
                blockers.extend(f"Bridge sequence application blocker: {item}" for item in bridge_sequence_application_summary.get("blockers") or [])
            if bridge_sequence_application_summary and bridge_sequence_application_summary.get("warnings"):
                warnings.extend(f"Bridge sequence application warning: {item}" for item in bridge_sequence_application_summary.get("warnings") or [])
        if step["id"] == "audit_transition_bridge_visual_evidence_contract":
            transition_bridge_visual_evidence_summary = summarize_transition_bridge_visual_evidence_contract(payload)
            if transition_bridge_visual_evidence_summary and transition_bridge_visual_evidence_summary.get("status") == "blocked":
                blockers.extend(f"Transition bridge visual evidence blocker: {item}" for item in transition_bridge_visual_evidence_summary.get("blockers") or [])
            if transition_bridge_visual_evidence_summary and transition_bridge_visual_evidence_summary.get("warnings"):
                warnings.extend(f"Transition bridge visual evidence warning: {item}" for item in transition_bridge_visual_evidence_summary.get("warnings") or [])
        if step["id"] == "audit_final_blueprint_lineage_contract":
            final_blueprint_lineage_summary = summarize_final_blueprint_lineage_contract(payload)
            if final_blueprint_lineage_summary and final_blueprint_lineage_summary.get("status") == "blocked":
                blockers.extend(f"Final blueprint lineage blocker: {item}" for item in final_blueprint_lineage_summary.get("blockers") or [])
            if final_blueprint_lineage_summary and final_blueprint_lineage_summary.get("warnings"):
                warnings.extend(f"Final blueprint lineage warning: {item}" for item in final_blueprint_lineage_summary.get("warnings") or [])
        if step["id"] == "audit_effect_motion_application_contract":
            effect_motion_application_summary = summarize_effect_motion_application_contract(payload)
            if effect_motion_application_summary and effect_motion_application_summary.get("status") == "blocked":
                blockers.extend(f"Effect motion application blocker: {item}" for item in effect_motion_application_summary.get("blockers") or [])
            if effect_motion_application_summary and effect_motion_application_summary.get("warnings"):
                warnings.extend(f"Effect motion application warning: {item}" for item in effect_motion_application_summary.get("warnings") or [])
        if step["id"] == "audit_transition_cadence_contract":
            transition_cadence_summary = summarize_transition_cadence_contract(payload)
            if transition_cadence_summary and transition_cadence_summary.get("status") == "blocked":
                blockers.extend(f"Transition cadence blocker: {item}" for item in transition_cadence_summary.get("blockers") or [])
            if transition_cadence_summary and transition_cadence_summary.get("warnings"):
                warnings.extend(f"Transition cadence warning: {item}" for item in transition_cadence_summary.get("warnings") or [])
        if step["id"] == "audit_transition_microstructure_contract":
            transition_microstructure_summary = summarize_transition_microstructure_contract(payload)
            if transition_microstructure_summary and transition_microstructure_summary.get("status") == "blocked":
                blockers.extend(f"Transition microstructure blocker: {item}" for item in transition_microstructure_summary.get("blockers") or [])
            if transition_microstructure_summary and transition_microstructure_summary.get("warnings"):
                warnings.extend(f"Transition microstructure warning: {item}" for item in transition_microstructure_summary.get("warnings") or [])
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
        if step["id"] == "audit_rhythm_recut_application_contract":
            rhythm_recut_application_summary = summarize_rhythm_recut_application_contract(payload)
            if rhythm_recut_application_summary and rhythm_recut_application_summary.get("status") == "blocked":
                blockers.extend(f"Rhythm recut application blocker: {item}" for item in rhythm_recut_application_summary.get("blockers") or [])
            if rhythm_recut_application_summary and rhythm_recut_application_summary.get("warnings"):
                warnings.extend(f"Rhythm recut application warning: {item}" for item in rhythm_recut_application_summary.get("warnings") or [])
        if step["id"] == "audit_reference_scene_grammar_contract":
            reference_scene_grammar_summary = summarize_reference_scene_grammar_contract(payload)
            if reference_scene_grammar_summary and reference_scene_grammar_summary.get("status") == "blocked":
                blockers.extend(f"Reference scene grammar blocker: {item}" for item in reference_scene_grammar_summary.get("blockers") or [])
            if reference_scene_grammar_summary and reference_scene_grammar_summary.get("warnings"):
                warnings.extend(f"Reference scene grammar warning: {item}" for item in reference_scene_grammar_summary.get("warnings") or [])
        if step["id"] == "audit_reference_profile_application_contract":
            reference_profile_application_summary = summarize_reference_profile_application_contract(payload)
            if reference_profile_application_summary and reference_profile_application_summary.get("status") == "blocked":
                blockers.extend(f"Reference profile application blocker: {item}" for item in reference_profile_application_summary.get("blockers") or [])
            if reference_profile_application_summary and reference_profile_application_summary.get("warnings"):
                warnings.extend(f"Reference profile application warning: {item}" for item in reference_profile_application_summary.get("warnings") or [])
        if step["id"] == "audit_timeline_variety_contract":
            timeline_variety_summary = summarize_timeline_variety_contract(payload)
            if timeline_variety_summary and timeline_variety_summary.get("status") == "blocked":
                blockers.extend(f"Timeline variety blocker: {item}" for item in timeline_variety_summary.get("blockers") or [])
            if timeline_variety_summary and timeline_variety_summary.get("warnings"):
                warnings.extend(f"Timeline variety warning: {item}" for item in timeline_variety_summary.get("warnings") or [])
        if step["id"] == "audit_transition_scene_arc_contract":
            transition_scene_arc_summary = summarize_transition_scene_arc_contract(payload)
            if transition_scene_arc_summary and transition_scene_arc_summary.get("status") == "blocked":
                blockers.extend(f"Transition scene arc blocker: {item}" for item in transition_scene_arc_summary.get("blockers") or [])
            if transition_scene_arc_summary and transition_scene_arc_summary.get("warnings"):
                warnings.extend(f"Transition scene arc warning: {item}" for item in transition_scene_arc_summary.get("warnings") or [])
        if step["id"] == "audit_transition_effect_palette_contract":
            transition_effect_palette_summary = summarize_transition_effect_palette_contract(payload)
            if transition_effect_palette_summary and transition_effect_palette_summary.get("status") == "blocked":
                blockers.extend(f"Transition effect palette blocker: {item}" for item in transition_effect_palette_summary.get("blockers") or [])
            if transition_effect_palette_summary and transition_effect_palette_summary.get("warnings"):
                warnings.extend(f"Transition effect palette warning: {item}" for item in transition_effect_palette_summary.get("warnings") or [])
        if step["id"] == "audit_transition_motif_coherence_contract":
            transition_motif_coherence_summary = summarize_transition_motif_coherence_contract(payload)
            if transition_motif_coherence_summary and transition_motif_coherence_summary.get("status") == "blocked":
                blockers.extend(f"Transition motif coherence blocker: {item}" for item in transition_motif_coherence_summary.get("blockers") or [])
            if transition_motif_coherence_summary and transition_motif_coherence_summary.get("warnings"):
                warnings.extend(f"Transition motif coherence warning: {item}" for item in transition_motif_coherence_summary.get("warnings") or [])
        if step["id"] == "audit_transition_visual_match_contract":
            transition_visual_match_summary = summarize_transition_visual_match_contract(payload)
            if transition_visual_match_summary and transition_visual_match_summary.get("status") == "blocked":
                blockers.extend(f"Transition visual match blocker: {item}" for item in transition_visual_match_summary.get("blockers") or [])
            if transition_visual_match_summary and transition_visual_match_summary.get("warnings"):
                warnings.extend(f"Transition visual match warning: {item}" for item in transition_visual_match_summary.get("warnings") or [])
        if step["id"] == "audit_transition_source_coverage_contract":
            transition_source_coverage_summary = summarize_transition_source_coverage_contract(payload)
            if transition_source_coverage_summary and transition_source_coverage_summary.get("status") == "blocked":
                blockers.extend(
                    f"Transition source coverage blocker: {item}"
                    for item in transition_source_coverage_summary.get("blockers") or []
                )
            if transition_source_coverage_summary and transition_source_coverage_summary.get("warnings"):
                warnings.extend(
                    f"Transition source coverage warning: {item}"
                    for item in transition_source_coverage_summary.get("warnings") or []
                )
        if step["id"] == "prepare_transition_choreography_plan":
            transition_choreography_plan_summary = summarize_transition_choreography_plan(payload)
            if transition_choreography_plan_summary and str(transition_choreography_plan_summary.get("status") or "").startswith(("blocked", "needs")):
                blockers.extend(f"Transition choreography plan blocker: {item}" for item in transition_choreography_plan_summary.get("blockers") or [])
            if transition_choreography_plan_summary and transition_choreography_plan_summary.get("warnings"):
                warnings.extend(f"Transition choreography plan warning: {item}" for item in transition_choreography_plan_summary.get("warnings") or [])
        if step["id"] == "audit_transition_choreography_contract":
            transition_choreography_contract_summary = summarize_transition_choreography_contract(payload)
            if transition_choreography_contract_summary and transition_choreography_contract_summary.get("status") == "blocked":
                blockers.extend(f"Transition choreography contract blocker: {item}" for item in transition_choreography_contract_summary.get("blockers") or [])
            if transition_choreography_contract_summary and transition_choreography_contract_summary.get("warnings"):
                warnings.extend(f"Transition choreography contract warning: {item}" for item in transition_choreography_contract_summary.get("warnings") or [])
        if step["id"] == "audit_transition_motion_direction_contract":
            transition_motion_direction_summary = summarize_transition_motion_direction_contract(payload)
            if transition_motion_direction_summary and transition_motion_direction_summary.get("status") == "blocked":
                blockers.extend(f"Transition motion direction blocker: {item}" for item in transition_motion_direction_summary.get("blockers") or [])
            if transition_motion_direction_summary and transition_motion_direction_summary.get("warnings"):
                warnings.extend(f"Transition motion direction warning: {item}" for item in transition_motion_direction_summary.get("warnings") or [])
        if step["id"] == "prepare_transition_preview_packet":
            transition_preview_packet_summary = summarize_transition_preview_packet(payload)
            if transition_preview_packet_summary and str(transition_preview_packet_summary.get("status") or "").startswith("blocked"):
                blockers.extend(f"Transition preview packet blocker: {item}" for item in transition_preview_packet_summary.get("blockers") or [])
            if transition_preview_packet_summary and transition_preview_packet_summary.get("status") == "needs_frame_extraction":
                blockers.append("Transition preview packet blocker: important transition rows still need frame extraction evidence")
            if transition_preview_packet_summary and transition_preview_packet_summary.get("warnings"):
                warnings.extend(f"Transition preview packet warning: {item}" for item in transition_preview_packet_summary.get("warnings") or [])
        if step["id"] == "audit_transition_preview_quality_contract":
            transition_preview_quality_summary = summarize_transition_preview_quality_contract(payload)
            if transition_preview_quality_summary and transition_preview_quality_summary.get("status") == "blocked":
                blockers.extend(f"Transition preview quality blocker: {item}" for item in transition_preview_quality_summary.get("blockers") or [])
            if transition_preview_quality_summary and transition_preview_quality_summary.get("warnings"):
                warnings.extend(f"Transition preview quality warning: {item}" for item in transition_preview_quality_summary.get("warnings") or [])
        if step["id"] == "prepare_transition_audition_packet":
            transition_audition_packet_summary = summarize_transition_audition_packet(payload)
            if transition_audition_packet_summary and str(transition_audition_packet_summary.get("status") or "").startswith("blocked"):
                blockers.extend(f"Transition audition packet blocker: {item}" for item in transition_audition_packet_summary.get("blockers") or [])
            if transition_audition_packet_summary and transition_audition_packet_summary.get("status") == "needs_audition_build":
                blockers.append("Transition audition packet blocker: important transition rows still need playable MP4 auditions")
            if transition_audition_packet_summary and transition_audition_packet_summary.get("warnings"):
                warnings.extend(f"Transition audition packet warning: {item}" for item in transition_audition_packet_summary.get("warnings") or [])
        if step["id"] == "audit_transition_audition_quality_contract":
            transition_audition_quality_summary = summarize_transition_audition_quality_contract(payload)
            if transition_audition_quality_summary and transition_audition_quality_summary.get("status") == "blocked":
                blockers.extend(f"Transition audition quality blocker: {item}" for item in transition_audition_quality_summary.get("blockers") or [])
            if transition_audition_quality_summary and transition_audition_quality_summary.get("warnings"):
                warnings.extend(f"Transition audition quality warning: {item}" for item in transition_audition_quality_summary.get("warnings") or [])
        if step["id"] == "prepare_transition_watch_reel":
            transition_watch_reel_summary = summarize_transition_watch_reel(payload)
            if transition_watch_reel_summary and str(transition_watch_reel_summary.get("status") or "").startswith("blocked"):
                blockers.extend(f"Transition watch reel blocker: {item}" for item in transition_watch_reel_summary.get("blockers") or [])
            if transition_watch_reel_summary and transition_watch_reel_summary.get("status") == "needs_transition_watch_reel_build":
                blockers.append("Transition watch reel blocker: important transition auditions were not concatenated into a review reel")
            if transition_watch_reel_summary and transition_watch_reel_summary.get("warnings"):
                warnings.extend(f"Transition watch reel warning: {item}" for item in transition_watch_reel_summary.get("warnings") or [])
        if step["id"] == "audit_transition_audition_visual_proof_contract":
            transition_audition_visual_proof_summary = summarize_transition_audition_visual_proof_contract(payload)
            if transition_audition_visual_proof_summary and transition_audition_visual_proof_summary.get("status") == "blocked":
                blockers.extend(f"Transition audition visual proof blocker: {item}" for item in transition_audition_visual_proof_summary.get("blockers") or [])
            if transition_audition_visual_proof_summary and transition_audition_visual_proof_summary.get("warnings"):
                warnings.extend(f"Transition audition visual proof warning: {item}" for item in transition_audition_visual_proof_summary.get("warnings") or [])
        if step["id"] == "audit_transition_audition_role_integrity_contract":
            transition_audition_role_integrity_summary = summarize_transition_audition_role_integrity_contract(payload)
            if transition_audition_role_integrity_summary and transition_audition_role_integrity_summary.get("status") == "blocked":
                blockers.extend(f"Transition audition role integrity blocker: {item}" for item in transition_audition_role_integrity_summary.get("blockers") or [])
            if transition_audition_role_integrity_summary and transition_audition_role_integrity_summary.get("warnings"):
                warnings.extend(f"Transition audition role integrity warning: {item}" for item in transition_audition_role_integrity_summary.get("warnings") or [])
        if step["id"] == "audit_transition_motion_accent_contract":
            transition_motion_accent_summary = summarize_transition_motion_accent_contract(payload)
            if transition_motion_accent_summary and transition_motion_accent_summary.get("status") == "blocked":
                blockers.extend(f"Transition motion accent blocker: {item}" for item in transition_motion_accent_summary.get("blockers") or [])
            if transition_motion_accent_summary and transition_motion_accent_summary.get("warnings"):
                warnings.extend(f"Transition motion accent warning: {item}" for item in transition_motion_accent_summary.get("warnings") or [])
        if step["id"] == "audit_transition_effect_recipe_contract":
            transition_effect_recipe_summary = summarize_transition_effect_recipe_contract(payload)
            if transition_effect_recipe_summary and transition_effect_recipe_summary.get("status") == "blocked":
                blockers.extend(f"Transition effect recipe blocker: {item}" for item in transition_effect_recipe_summary.get("blockers") or [])
            if transition_effect_recipe_summary and transition_effect_recipe_summary.get("warnings"):
                warnings.extend(f"Transition effect recipe warning: {item}" for item in transition_effect_recipe_summary.get("warnings") or [])
        if step["id"] == "audit_transition_storyboard_contract":
            transition_storyboard_summary = summarize_transition_storyboard_contract(payload)
            if transition_storyboard_summary and transition_storyboard_summary.get("status") == "blocked":
                blockers.extend(f"Transition storyboard blocker: {item}" for item in transition_storyboard_summary.get("blockers") or [])
            if transition_storyboard_summary and transition_storyboard_summary.get("warnings"):
                warnings.extend(f"Transition storyboard warning: {item}" for item in transition_storyboard_summary.get("warnings") or [])
        if step["id"] == "audit_reference_transition_profile_contract":
            reference_transition_profile_summary = summarize_reference_transition_profile_contract(payload)
            if reference_transition_profile_summary and reference_transition_profile_summary.get("status") == "blocked":
                blockers.extend(f"Reference transition profile blocker: {item}" for item in reference_transition_profile_summary.get("blockers") or [])
            if reference_transition_profile_summary and reference_transition_profile_summary.get("warnings"):
                warnings.extend(f"Reference transition profile warning: {item}" for item in reference_transition_profile_summary.get("warnings") or [])
        if step["id"] == "audit_chapter_story_spine_contract":
            chapter_story_spine_summary = summarize_chapter_story_spine_contract(payload)
            if chapter_story_spine_summary and chapter_story_spine_summary.get("status") == "blocked":
                blockers.extend(f"Chapter story spine blocker: {item}" for item in chapter_story_spine_summary.get("blockers") or [])
            if chapter_story_spine_summary and chapter_story_spine_summary.get("warnings"):
                warnings.extend(f"Chapter story spine warning: {item}" for item in chapter_story_spine_summary.get("warnings") or [])
        if step["id"] == "audit_shot_flow_continuity_contract":
            shot_flow_continuity_summary = summarize_shot_flow_continuity_contract(payload)
            if shot_flow_continuity_summary and shot_flow_continuity_summary.get("status") == "blocked":
                blockers.extend(f"Shot flow continuity blocker: {item}" for item in shot_flow_continuity_summary.get("blockers") or [])
            if shot_flow_continuity_summary and shot_flow_continuity_summary.get("warnings"):
                warnings.extend(f"Shot flow continuity warning: {item}" for item in shot_flow_continuity_summary.get("warnings") or [])
        if step["id"] == "audit_transition_breathing_room_contract":
            transition_breathing_room_summary = summarize_transition_breathing_room_contract(payload)
            if transition_breathing_room_summary and transition_breathing_room_summary.get("status") == "blocked":
                blockers.extend(f"Transition breathing-room blocker: {item}" for item in transition_breathing_room_summary.get("blockers") or [])
            if transition_breathing_room_summary and transition_breathing_room_summary.get("warnings"):
                warnings.extend(f"Transition breathing-room warning: {item}" for item in transition_breathing_room_summary.get("warnings") or [])
        if step["id"] == "audit_scene_flow_arc_contract":
            scene_flow_arc_summary = summarize_scene_flow_arc_contract(payload)
            if scene_flow_arc_summary and scene_flow_arc_summary.get("status") == "blocked":
                blockers.extend(f"Scene flow arc blocker: {item}" for item in scene_flow_arc_summary.get("blockers") or [])
            if scene_flow_arc_summary and scene_flow_arc_summary.get("warnings"):
                warnings.extend(f"Scene flow arc warning: {item}" for item in scene_flow_arc_summary.get("warnings") or [])
        if step["id"] == "audit_final_cut_smoothness_contract":
            final_cut_smoothness_summary = summarize_final_cut_smoothness_contract(payload)
            if final_cut_smoothness_summary and final_cut_smoothness_summary.get("status") == "blocked":
                blockers.extend(f"Final cut smoothness blocker: {item}" for item in final_cut_smoothness_summary.get("blockers") or [])
            if final_cut_smoothness_summary and final_cut_smoothness_summary.get("warnings"):
                warnings.extend(f"Final cut smoothness warning: {item}" for item in final_cut_smoothness_summary.get("warnings") or [])
        if step["id"] == "audit_transition_continuity_rehearsal_contract":
            transition_continuity_rehearsal_summary = summarize_transition_continuity_rehearsal_contract(payload)
            if transition_continuity_rehearsal_summary and transition_continuity_rehearsal_summary.get("status") == "blocked":
                blockers.extend(f"Transition continuity rehearsal blocker: {item}" for item in transition_continuity_rehearsal_summary.get("blockers") or [])
            if transition_continuity_rehearsal_summary and transition_continuity_rehearsal_summary.get("warnings"):
                warnings.extend(f"Transition continuity rehearsal warning: {item}" for item in transition_continuity_rehearsal_summary.get("warnings") or [])
        if step["id"] == "audit_pacing_watchability_contract":
            pacing_watchability_summary = summarize_pacing_watchability_contract(payload)
            if pacing_watchability_summary and pacing_watchability_summary.get("status") == "blocked":
                blockers.extend(f"Pacing watchability blocker: {item}" for item in pacing_watchability_summary.get("blockers") or [])
            if pacing_watchability_summary and pacing_watchability_summary.get("warnings"):
                warnings.extend(f"Pacing watchability warning: {item}" for item in pacing_watchability_summary.get("warnings") or [])
        if step["id"] == "audit_narrative_adjacency_contract":
            narrative_adjacency_summary = summarize_narrative_adjacency_contract(payload)
            if narrative_adjacency_summary and narrative_adjacency_summary.get("status") == "blocked":
                blockers.extend(f"Narrative adjacency blocker: {item}" for item in narrative_adjacency_summary.get("blockers") or [])
            if narrative_adjacency_summary and narrative_adjacency_summary.get("warnings"):
                warnings.extend(f"Narrative adjacency warning: {item}" for item in narrative_adjacency_summary.get("warnings") or [])
        if step["id"] == "audit_transition_viewer_orientation_contract":
            transition_viewer_orientation_summary = summarize_transition_viewer_orientation_contract(payload)
            if transition_viewer_orientation_summary and transition_viewer_orientation_summary.get("status") == "blocked":
                blockers.extend(f"Transition viewer orientation blocker: {item}" for item in transition_viewer_orientation_summary.get("blockers") or [])
            if transition_viewer_orientation_summary and transition_viewer_orientation_summary.get("warnings"):
                warnings.extend(f"Transition viewer orientation warning: {item}" for item in transition_viewer_orientation_summary.get("warnings") or [])
        if step["id"] == "audit_transition_scene_settlement_contract":
            transition_scene_settlement_summary = summarize_transition_scene_settlement_contract(payload)
            if transition_scene_settlement_summary and transition_scene_settlement_summary.get("status") == "blocked":
                blockers.extend(f"Transition scene settlement blocker: {item}" for item in transition_scene_settlement_summary.get("blockers") or [])
            if transition_scene_settlement_summary and transition_scene_settlement_summary.get("warnings"):
                warnings.extend(f"Transition scene settlement warning: {item}" for item in transition_scene_settlement_summary.get("warnings") or [])
        if step["id"] == "prepare_transition_flow_repair_plan":
            transition_flow_repair_summary = summarize_transition_flow_repair_plan(payload)
            if (
                transition_flow_repair_summary
                and transition_flow_repair_summary.get("status") == "ready_with_transition_flow_repair_plan"
            ):
                blockers.extend(
                    f"Transition flow repair blocker: {item}"
                    for item in transition_flow_repair_summary.get("blockers") or []
                )
        if step["id"] == "prepare_reference_style_repair_plan":
            reference_style_repair_summary = summarize_reference_style_repair_plan(payload)
        if step["id"] == "audit_reference_repair_closure":
            reference_repair_closure_summary = summarize_reference_repair_closure(payload)
            if reference_repair_closure_summary and reference_repair_closure_summary.get("status") == "blocked":
                blockers.extend(f"Reference repair closure blocker: {item}" for item in reference_repair_closure_summary.get("blockers") or [])
            if reference_repair_closure_summary and reference_repair_closure_summary.get("warnings"):
                warnings.extend(f"Reference repair closure warning: {item}" for item in reference_repair_closure_summary.get("warnings") or [])
        if step["id"] == "prepare_unattended_repair_queue":
            unattended_repair_queue_summary = summarize_unattended_repair_queue(payload)
            if unattended_repair_queue_summary and unattended_repair_queue_summary.get("status") == "blocked_unactionable_repair_queue":
                blockers.extend(f"Unattended repair queue blocker: {item}" for item in unattended_repair_queue_summary.get("blockers") or [])
            if unattended_repair_queue_summary and unattended_repair_queue_summary.get("warnings"):
                warnings.extend(f"Unattended repair queue warning: {item}" for item in unattended_repair_queue_summary.get("warnings") or [])
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
        if step["id"] == "audit_skill_maturity_contract":
            skill_maturity_summary = summarize_skill_maturity_contract(payload)
            if skill_maturity_summary and skill_maturity_summary.get("status") == "blocked":
                blockers.extend(
                    f"Skill maturity blocker: {item}" for item in skill_maturity_summary.get("blockers") or []
                )
            if skill_maturity_summary and skill_maturity_summary.get("warnings"):
                warnings.extend(
                    f"Skill maturity warning: {item}" for item in skill_maturity_summary.get("warnings") or []
                )
        if step["id"] == "audit_v14_baseline_contract":
            v14_baseline_summary = summarize_v14_baseline_contract(payload)
            if v14_baseline_summary and v14_baseline_summary.get("status") == "blocked":
                blockers.extend(f"V14 baseline blocker: {item}" for item in v14_baseline_summary.get("blockers") or [])
            if v14_baseline_summary and v14_baseline_summary.get("warnings"):
                warnings.extend(f"V14 baseline warning: {item}" for item in v14_baseline_summary.get("warnings") or [])
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
    if package_dir and (package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json").exists():
        source_selection_repair_summary = summarize_source_selection_repair_plan(
            load_json(package_dir / "source_selection_repair_plan" / "source_selection_repair_plan.json")
        )
    if package_dir and (package_dir / "source_selection_coverage_contract_audit.json").exists():
        source_selection_coverage_summary = summarize_source_selection_coverage_contract(
            load_json(package_dir / "source_selection_coverage_contract_audit.json")
        )
    if package_dir and (package_dir / "first_assembly_source_order_contract_audit.json").exists():
        first_assembly_source_order_summary = summarize_first_assembly_source_order_contract(
            load_json(package_dir / "first_assembly_source_order_contract_audit.json")
        )
    if package_dir and (package_dir / "large_source_unattended_readiness_contract_audit.json").exists():
        large_source_unattended_readiness_summary = summarize_large_source_unattended_readiness_contract(
            load_json(package_dir / "large_source_unattended_readiness_contract_audit.json")
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
    if package_dir and (package_dir / "title_visual_proof_contract_audit.json").exists():
        title_visual_proof_summary = summarize_title_visual_proof_contract(
            load_json(package_dir / "title_visual_proof_contract_audit.json")
        )
    if package_dir and (package_dir / "title_typography_repair_plan" / "title_typography_repair_plan.json").exists():
        title_typography_repair_summary = summarize_title_typography_repair_plan(
            load_json(package_dir / "title_typography_repair_plan" / "title_typography_repair_plan.json")
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
    if package_dir and (package_dir / "bgm_musicality_contract_audit.json").exists():
        bgm_musicality_summary = summarize_bgm_musicality_contract(
            load_json(package_dir / "bgm_musicality_contract_audit.json")
        )
    if package_dir and (package_dir / "feedback_regression_plan" / "feedback_regression_plan.json").exists():
        feedback_regression_plan_summary = summarize_feedback_regression_plan(
            load_json(package_dir / "feedback_regression_plan" / "feedback_regression_plan.json")
        )
    if package_dir and (package_dir / "reference" / "reference_batch_profile.json").exists():
        reference_batch_summary = summarize_reference_batch_profile(
            load_json(package_dir / "reference" / "reference_batch_profile.json")
        )
    if package_dir and (package_dir / "reference_review_repair_plan" / "reference_review_repair_plan.json").exists():
        reference_review_repair_summary = summarize_reference_review_repair_plan(
            load_json(package_dir / "reference_review_repair_plan" / "reference_review_repair_plan.json")
        )
    if package_dir and (package_dir / "editorial_watchdown_repair_plan" / "editorial_watchdown_repair_plan.json").exists():
        editorial_watchdown_summary = summarize_editorial_watchdown_repair_plan(
            load_json(package_dir / "editorial_watchdown_repair_plan" / "editorial_watchdown_repair_plan.json")
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
    if package_dir and (package_dir / "transition_reference_candidates" / "transition_reference_candidates.json").exists():
        transition_reference_candidates_summary = summarize_transition_reference_candidates(
            load_json(package_dir / "transition_reference_candidates" / "transition_reference_candidates.json")
        )
    if package_dir and (package_dir / "transition_reference_selection" / "transition_reference_selection.json").exists():
        transition_reference_selection_summary = summarize_transition_reference_selection(
            load_json(package_dir / "transition_reference_selection" / "transition_reference_selection.json")
        )
    if package_dir and (package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json").exists():
        transition_execution_blueprint_summary = summarize_transition_execution_blueprint(
            load_json(package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json")
        )
    if package_dir and (package_dir / "transition_cutpoint_contract_audit.json").exists():
        transition_cutpoint_summary = summarize_transition_cutpoint_contract(
            load_json(package_dir / "transition_cutpoint_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_action_anchor_contract_audit.json").exists():
        transition_action_anchor_summary = summarize_transition_action_anchor_contract(
            load_json(package_dir / "transition_action_anchor_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_sensory_continuity_contract_audit.json").exists():
        transition_sensory_continuity_summary = summarize_transition_sensory_continuity_contract(
            load_json(package_dir / "transition_sensory_continuity_contract_audit.json")
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
    if package_dir and (package_dir / "resolve_transition_materialization_contract_audit.json").exists():
        resolve_transition_materialization_summary = summarize_resolve_transition_materialization_contract(
            load_json(package_dir / "resolve_transition_materialization_contract_audit.json")
        )
    if package_dir and (package_dir / "resolve_transition_apply_contract_audit.json").exists():
        resolve_transition_apply_summary = summarize_resolve_transition_apply_contract(
            load_json(package_dir / "resolve_transition_apply_contract_audit.json")
        )
    if package_dir and (package_dir / "bridge_sequence_application_contract_audit.json").exists():
        bridge_sequence_application_summary = summarize_bridge_sequence_application_contract(
            load_json(package_dir / "bridge_sequence_application_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_bridge_visual_evidence_contract_audit.json").exists():
        transition_bridge_visual_evidence_summary = summarize_transition_bridge_visual_evidence_contract(
            load_json(package_dir / "transition_bridge_visual_evidence_contract_audit.json")
        )
    if package_dir and (package_dir / "final_blueprint_lineage_contract_audit.json").exists():
        final_blueprint_lineage_summary = summarize_final_blueprint_lineage_contract(
            load_json(package_dir / "final_blueprint_lineage_contract_audit.json")
        )
    if package_dir and (package_dir / "effect_motion_application_contract_audit.json").exists():
        effect_motion_application_summary = summarize_effect_motion_application_contract(
            load_json(package_dir / "effect_motion_application_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_cadence_contract_audit.json").exists():
        transition_cadence_summary = summarize_transition_cadence_contract(
            load_json(package_dir / "transition_cadence_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_microstructure_contract_audit.json").exists():
        transition_microstructure_summary = summarize_transition_microstructure_contract(
            load_json(package_dir / "transition_microstructure_contract_audit.json")
        )
    if package_dir and (package_dir / "final_source_usage_contract_audit.json").exists():
        final_source_usage_summary = summarize_final_source_usage_contract(
            load_json(package_dir / "final_source_usage_contract_audit.json")
        )
    if package_dir and (package_dir / "creator_cut_application_contract_audit.json").exists():
        creator_cut_application_summary = summarize_creator_cut_application_contract(
            load_json(package_dir / "creator_cut_application_contract_audit.json")
        )
    if package_dir and (package_dir / "rhythm_recut_application_contract_audit.json").exists():
        rhythm_recut_application_summary = summarize_rhythm_recut_application_contract(
            load_json(package_dir / "rhythm_recut_application_contract_audit.json")
        )
    if package_dir and (package_dir / "reference_scene_grammar_contract_audit.json").exists():
        reference_scene_grammar_summary = summarize_reference_scene_grammar_contract(
            load_json(package_dir / "reference_scene_grammar_contract_audit.json")
        )
    if package_dir and (package_dir / "reference_profile_application_contract_audit.json").exists():
        reference_profile_application_summary = summarize_reference_profile_application_contract(
            load_json(package_dir / "reference_profile_application_contract_audit.json")
        )
    if package_dir and (package_dir / "timeline_variety_contract_audit.json").exists():
        timeline_variety_summary = summarize_timeline_variety_contract(
            load_json(package_dir / "timeline_variety_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_scene_arc_contract_audit.json").exists():
        transition_scene_arc_summary = summarize_transition_scene_arc_contract(
            load_json(package_dir / "transition_scene_arc_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_effect_palette_contract_audit.json").exists():
        transition_effect_palette_summary = summarize_transition_effect_palette_contract(
            load_json(package_dir / "transition_effect_palette_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_motif_coherence_contract_audit.json").exists():
        transition_motif_coherence_summary = summarize_transition_motif_coherence_contract(
            load_json(package_dir / "transition_motif_coherence_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_visual_match_contract_audit.json").exists():
        transition_visual_match_summary = summarize_transition_visual_match_contract(
            load_json(package_dir / "transition_visual_match_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_source_coverage_contract_audit.json").exists():
        transition_source_coverage_summary = summarize_transition_source_coverage_contract(
            load_json(package_dir / "transition_source_coverage_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_choreography_plan" / "transition_choreography_plan.json").exists():
        transition_choreography_plan_summary = summarize_transition_choreography_plan(
            load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json")
        )
    if package_dir and (package_dir / "transition_choreography_contract_audit.json").exists():
        transition_choreography_contract_summary = summarize_transition_choreography_contract(
            load_json(package_dir / "transition_choreography_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_motion_direction_contract_audit.json").exists():
        transition_motion_direction_summary = summarize_transition_motion_direction_contract(
            load_json(package_dir / "transition_motion_direction_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_preview_packet" / "transition_preview_packet.json").exists():
        transition_preview_packet_summary = summarize_transition_preview_packet(
            load_json(package_dir / "transition_preview_packet" / "transition_preview_packet.json")
        )
    if package_dir and (package_dir / "transition_preview_quality_contract_audit.json").exists():
        transition_preview_quality_summary = summarize_transition_preview_quality_contract(
            load_json(package_dir / "transition_preview_quality_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_audition_packet" / "transition_audition_packet.json").exists():
        transition_audition_packet_summary = summarize_transition_audition_packet(
            load_json(package_dir / "transition_audition_packet" / "transition_audition_packet.json")
        )
    if package_dir and (package_dir / "transition_audition_quality_contract_audit.json").exists():
        transition_audition_quality_summary = summarize_transition_audition_quality_contract(
            load_json(package_dir / "transition_audition_quality_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_watch_reel" / "transition_watch_reel.json").exists():
        transition_watch_reel_summary = summarize_transition_watch_reel(
            load_json(package_dir / "transition_watch_reel" / "transition_watch_reel.json")
        )
    if package_dir and (package_dir / "transition_audition_visual_proof_contract_audit.json").exists():
        transition_audition_visual_proof_summary = summarize_transition_audition_visual_proof_contract(
            load_json(package_dir / "transition_audition_visual_proof_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_audition_role_integrity_contract_audit.json").exists():
        transition_audition_role_integrity_summary = summarize_transition_audition_role_integrity_contract(
            load_json(package_dir / "transition_audition_role_integrity_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_motion_accent_contract_audit.json").exists():
        transition_motion_accent_summary = summarize_transition_motion_accent_contract(
            load_json(package_dir / "transition_motion_accent_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_effect_recipe_contract_audit.json").exists():
        transition_effect_recipe_summary = summarize_transition_effect_recipe_contract(
            load_json(package_dir / "transition_effect_recipe_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_storyboard_contract_audit.json").exists():
        transition_storyboard_summary = summarize_transition_storyboard_contract(
            load_json(package_dir / "transition_storyboard_contract_audit.json")
        )
    if package_dir and (package_dir / "reference_transition_profile_contract_audit.json").exists():
        reference_transition_profile_summary = summarize_reference_transition_profile_contract(
            load_json(package_dir / "reference_transition_profile_contract_audit.json")
        )
    if package_dir and (package_dir / "chapter_story_spine_contract_audit.json").exists():
        chapter_story_spine_summary = summarize_chapter_story_spine_contract(
            load_json(package_dir / "chapter_story_spine_contract_audit.json")
        )
    if package_dir and (package_dir / "shot_flow_continuity_contract_audit.json").exists():
        shot_flow_continuity_summary = summarize_shot_flow_continuity_contract(
            load_json(package_dir / "shot_flow_continuity_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_breathing_room_contract_audit.json").exists():
        transition_breathing_room_summary = summarize_transition_breathing_room_contract(
            load_json(package_dir / "transition_breathing_room_contract_audit.json")
        )
    if package_dir and (package_dir / "scene_flow_arc_contract_audit.json").exists():
        scene_flow_arc_summary = summarize_scene_flow_arc_contract(
            load_json(package_dir / "scene_flow_arc_contract_audit.json")
        )
    if package_dir and (package_dir / "final_cut_smoothness_contract_audit.json").exists():
        final_cut_smoothness_summary = summarize_final_cut_smoothness_contract(
            load_json(package_dir / "final_cut_smoothness_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_continuity_rehearsal_contract_audit.json").exists():
        transition_continuity_rehearsal_summary = summarize_transition_continuity_rehearsal_contract(
            load_json(package_dir / "transition_continuity_rehearsal_contract_audit.json")
        )
    if package_dir and (package_dir / "pacing_watchability_contract_audit.json").exists():
        pacing_watchability_summary = summarize_pacing_watchability_contract(
            load_json(package_dir / "pacing_watchability_contract_audit.json")
        )
    if package_dir and (package_dir / "narrative_adjacency_contract_audit.json").exists():
        narrative_adjacency_summary = summarize_narrative_adjacency_contract(
            load_json(package_dir / "narrative_adjacency_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_viewer_orientation_contract_audit.json").exists():
        transition_viewer_orientation_summary = summarize_transition_viewer_orientation_contract(
            load_json(package_dir / "transition_viewer_orientation_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_scene_settlement_contract_audit.json").exists():
        transition_scene_settlement_summary = summarize_transition_scene_settlement_contract(
            load_json(package_dir / "transition_scene_settlement_contract_audit.json")
        )
    if package_dir and (package_dir / "transition_flow_repair_plan" / "transition_flow_repair_plan.json").exists():
        transition_flow_repair_summary = summarize_transition_flow_repair_plan(
            load_json(package_dir / "transition_flow_repair_plan" / "transition_flow_repair_plan.json")
        )
    if package_dir and (package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json").exists():
        reference_style_repair_summary = summarize_reference_style_repair_plan(
            load_json(package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json")
        )
    if package_dir and (package_dir / "reference_repair_closure_audit.json").exists():
        reference_repair_closure_summary = summarize_reference_repair_closure(
            load_json(package_dir / "reference_repair_closure_audit.json")
        )
    if package_dir and (package_dir / "unattended_repair_queue" / "unattended_repair_queue.json").exists():
        unattended_repair_queue_summary = summarize_unattended_repair_queue(
            load_json(package_dir / "unattended_repair_queue" / "unattended_repair_queue.json")
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
    if package_dir and (package_dir / "skill_maturity_contract_audit.json").exists():
        skill_maturity_summary = summarize_skill_maturity_contract(
            load_json(package_dir / "skill_maturity_contract_audit.json")
        )
    if package_dir and (package_dir / "v14_baseline_contract_audit.json").exists():
        v14_baseline_summary = summarize_v14_baseline_contract(
            load_json(package_dir / "v14_baseline_contract_audit.json")
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
        "sourceSelectionRepairSummary": source_selection_repair_summary,
        "sourceSelectionCoverageSummary": source_selection_coverage_summary,
        "firstAssemblySourceOrderSummary": first_assembly_source_order_summary,
        "largeSourceUnattendedReadinessSummary": large_source_unattended_readiness_summary,
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
        "titleVisualProofSummary": title_visual_proof_summary,
        "titleTypographyRepairSummary": title_typography_repair_summary,
        "visualEstablishingSummary": visual_establishing_summary,
        "effectMotionSummary": effect_motion_summary,
        "effectMotionBlueprintSummary": effect_motion_blueprint_summary,
        "bgmPhraseBlueprintSummary": bgm_phrase_blueprint_summary,
        "bgmMusicalitySummary": bgm_musicality_summary,
        "feedbackRegressionPlanSummary": feedback_regression_plan_summary,
        "referenceBatchSummary": reference_batch_summary,
        "referenceReviewRepairSummary": reference_review_repair_summary,
        "audioScenePolicySummary": audio_scene_policy_summary,
        "editRhythmSummary": edit_rhythm_summary,
        "creatorCutSummary": creator_cut_summary,
        "transitionGrammarSummary": transition_grammar_summary,
        "transitionExecutionSummary": transition_execution_summary,
        "transitionReferenceCandidatesSummary": transition_reference_candidates_summary,
        "transitionReferenceSelectionSummary": transition_reference_selection_summary,
        "transitionExecutionBlueprintSummary": transition_execution_blueprint_summary,
        "transitionCutpointSummary": transition_cutpoint_summary,
        "transitionActionAnchorSummary": transition_action_anchor_summary,
        "transitionSensoryContinuitySummary": transition_sensory_continuity_summary,
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
        "resolveTransitionMaterializationSummary": resolve_transition_materialization_summary,
        "resolveTransitionApplySummary": resolve_transition_apply_summary,
        "bridgeSequenceApplicationSummary": bridge_sequence_application_summary,
        "transitionBridgeVisualEvidenceSummary": transition_bridge_visual_evidence_summary,
        "finalBlueprintLineageSummary": final_blueprint_lineage_summary,
        "effectMotionApplicationSummary": effect_motion_application_summary,
        "transitionCadenceSummary": transition_cadence_summary,
        "transitionMicrostructureSummary": transition_microstructure_summary,
        "finalSourceUsageSummary": final_source_usage_summary,
        "creatorCutApplicationSummary": creator_cut_application_summary,
        "rhythmRecutApplicationSummary": rhythm_recut_application_summary,
        "referenceSceneGrammarSummary": reference_scene_grammar_summary,
        "referenceProfileApplicationSummary": reference_profile_application_summary,
        "timelineVarietySummary": timeline_variety_summary,
        "transitionSceneArcSummary": transition_scene_arc_summary,
        "transitionEffectPaletteSummary": transition_effect_palette_summary,
        "transitionMotifCoherenceSummary": transition_motif_coherence_summary,
        "transitionVisualMatchSummary": transition_visual_match_summary,
        "transitionSourceCoverageSummary": transition_source_coverage_summary,
        "transitionChoreographyPlanSummary": transition_choreography_plan_summary,
        "transitionChoreographyContractSummary": transition_choreography_contract_summary,
        "transitionMotionDirectionSummary": transition_motion_direction_summary,
        "transitionPreviewPacketSummary": transition_preview_packet_summary,
        "transitionPreviewQualitySummary": transition_preview_quality_summary,
        "transitionAuditionPacketSummary": transition_audition_packet_summary,
        "transitionAuditionQualitySummary": transition_audition_quality_summary,
        "transitionWatchReelSummary": transition_watch_reel_summary,
        "transitionAuditionVisualProofSummary": transition_audition_visual_proof_summary,
        "transitionAuditionRoleIntegritySummary": transition_audition_role_integrity_summary,
        "transitionMotionAccentSummary": transition_motion_accent_summary,
        "transitionEffectRecipeSummary": transition_effect_recipe_summary,
        "transitionStoryboardSummary": transition_storyboard_summary,
        "referenceTransitionProfileSummary": reference_transition_profile_summary,
        "chapterStorySpineSummary": chapter_story_spine_summary,
        "shotFlowContinuitySummary": shot_flow_continuity_summary,
        "transitionBreathingRoomSummary": transition_breathing_room_summary,
        "sceneFlowArcSummary": scene_flow_arc_summary,
        "finalCutSmoothnessSummary": final_cut_smoothness_summary,
        "transitionContinuityRehearsalSummary": transition_continuity_rehearsal_summary,
        "pacingWatchabilitySummary": pacing_watchability_summary,
        "narrativeAdjacencySummary": narrative_adjacency_summary,
        "transitionViewerOrientationSummary": transition_viewer_orientation_summary,
        "transitionSceneSettlementSummary": transition_scene_settlement_summary,
        "transitionFlowRepairSummary": transition_flow_repair_summary,
        "unattendedFirstDraftSummary": unattended_first_draft_summary,
        "referenceStyleRepairSummary": reference_style_repair_summary,
        "referenceRepairClosureSummary": reference_repair_closure_summary,
        "editorialWatchdownSummary": editorial_watchdown_summary,
        "unattendedRepairQueueSummary": unattended_repair_queue_summary,
        "rhythmRecutApplyPackageSummary": rhythm_recut_apply_summary,
        "skillMaturitySummary": skill_maturity_summary,
        "v14BaselineSummary": v14_baseline_summary,
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
            "Review bgm_musicality_contract_audit.json before Resolve apply so the BGM bed is real music with dynamics and multi-band energy, not a hum, tone, silence, or placeholder.",
            "Review transition_effect_recipe_contract_audit.json before Resolve apply so visible transitions have restrained keyframes, easing, envelopes, BGM-only audio, BGM-hit timing, and landing holds instead of marker-only or template effects.",
            "Review footage_select_plan.json before trusting first assembly; repair/reject rows should not lead the cut.",
            "Review raw_intake_completeness_audit.json before trusting any large unordered source folder; every active source video must be indexed, recognized, routed exactly once, and scored before first assembly.",
            "Review source_selection_repair_plan.json before opening/chapter/transition work; every chapter needs ready local movement, lived-in texture, and payoff coverage before effects or stock fallback.",
            "Review first_assembly_source_order_contract_audit.json before rhythm/opening work so the first assembly proves it used full-source footage selection instead of filename order, blueprint fallback samples, or repair/reject rows.",
            "Review large_source_unattended_readiness_contract_audit.json before handing a 100GB unordered source folder to another AI; it proves media-root intake, whole-folder recognition, source selection, first assembly, unattended first draft, and blueprint preflight are connected.",
            "Review opening_story_plan.json before title, BGM, rhythm, or Resolve apply so the first three minutes have viewer promise, destination proof, clean title, practical arrival, lived-in texture, and first handoff.",
            "Review chapter_arc_plan.json before rhythm/creator-cut/Resolve apply so every chapter has context, movement, lived-in texture, payoff, and aftertaste decisions.",
            "Fill transition_bridge_plan.json local bridge or stock/aerial fallback decisions before final claims.",
            "Review caption_story_plan/text_only_narration_export.txt and dense SRT before subtitle overlay generation.",
            "Review audience_caption_contract_audit.json so final captions/TXT are viewer-facing travel-film text, not edit-status reports.",
            "Review title_typography_plan.json before generating or trusting title bridge media.",
            "Review title_visual_proof_contract_audit.json before approving the opening/chapter/ending title look; it must contain package-local video probe plus nonblank 16:9 frame evidence.",
            "Review title_typography_repair_plan.json before Resolve apply or handoff; ready_with_title_typography_repair_plan means title/cover repair rows are still open.",
            "Review visual_establishing_plan.json before trusting opening/chapter/ending aerial, landmark, or city establishing shots.",
            "Review effect_motion_plan.json before adding Resolve title, route, or transition effects.",
            "Preflight effect_motion_blueprint/resolve_timeline_blueprint_effect_motion.json before approving title or transition motion effects for Resolve.",
            "Preflight bgm_phrase_blueprint/resolve_timeline_blueprint_bgm_phrase.json before approving BGM phrase cues, transition sync, or music-led scenic sections for Resolve.",
            "Review feedback_regression_plan.json so original user complaints stay in pre-render audio policy, post-render feedback audit, and final QA commands.",
            "Review reference_batch_profile.json when local reference videos are supplied so rhythm/style targets are based on measured reference evidence.",
            "Review reference_review_repair_plan/reference_review_repair_plan.json when local reference videos are supplied so full-film review evidence is closed before reference learning, final QA, V14, or Skill maturity claims.",
            "Review editorial_watchdown_repair_plan/editorial_watchdown_repair_plan.json before handoff; ready_with_editorial_watchdown_repair_plan means the current final MP4 still has open full-film viewer-review rows.",
            "Review audio_scene_policy_plan.json before Resolve apply so opening/scenic/title/transition windows are A3 BGM-led with no A1/A2 voice leak.",
            "Review edit_rhythm_plan.json before Resolve apply so long raw clips, missing cutaways, and weak chapter variety are fixed before the edit feels AI-assembled.",
            "Review creator_cut_plan.json before transition execution so weak clips are demoted and kept clips have creator functions.",
            "Review rhythm_recut_application_contract_audit.json before Resolve apply so rhythm-recut main segments and cutaways actually survived into the final candidate blueprint.",
            "Review transition_grammar_plan.json and transition_execution_plan.json before Resolve apply so every adjacent pair has an approved, source-backed execution recipe.",
            "Review transition_reference_candidates/transition_reference_candidates.md before motif, preview, storyboard, or Resolve apply so every boundary has non-copying reference-calibrated A/B/C candidates instead of generic hard cuts or random effects.",
            "Review transition_reference_selection/transition_reference_selection.md before preview, storyboard, or Resolve apply so unattended drafts use one safe default transition per boundary and keep bridge-missing rows blocked.",
            "Preflight transition_execution_blueprint/resolve_timeline_blueprint_transition_execution.json before approving transition effects for Resolve.",
            "Review transition_motif_plan.json before Resolve apply so the film does not rely on repeated dissolves, random motion, or effects hiding weak route jumps.",
            "Review bridge_sequence_plan.json before rhythm recut or Resolve apply so important route/title/timeline-gap transitions become 2-5 shot bridge sequences instead of single effects.",
            "Review transition_motivation_contract_audit.json before Resolve apply so each transition has a viewer-facing route, motion, title, bridge, or BGM motivation instead of a decorative effect.",
            "Review transition_pair_continuity_contract_audit.json before Resolve apply so every adjacent from/to shot has concrete visual, route, motion, BGM, or title continuity evidence.",
            "Review transition_execution_readiness_contract_audit.json before Resolve apply so every transition has a package-local Resolve recipe, BGM hit, title-safe window, pair readiness, handles, and decision fields.",
            "Review transition_polish_application_contract_audit.json before Resolve apply so final/active blueprints do not drop transition-polish metadata after candidate generation.",
            "Review resolve_transition_materialization_contract_audit.json before Resolve apply so transition recipe/effect payloads survive into Resolve markers/readback instead of remaining only as planning text.",
            "Review resolve_transition_apply_plan.json and resolve_transition_apply_contract_audit.json before Resolve apply so visible transitions are not marker-only and manual Resolve/Fusion or bridge-clip steps have readback/frame evidence.",
            "Review bridge_sequence_application_contract_audit.json before Resolve apply so planned 2-5 shot bridge sequences survive into the final candidate blueprint.",
            "Review transition_bridge_visual_evidence_contract_audit.json before Resolve apply so bridge sequence inserts have concrete local video, probe/frame evidence, beat metadata, and no source-camera audio.",
            "Review final_blueprint_lineage_contract_audit.json before Resolve apply so the active final blueprint inherits the latest ready candidate chain instead of an old or partial blueprint.",
            "Review effect_motion_application_contract_audit.json before Resolve apply so title reveals and route-motion effects survive into the final blueprint without overusing rotation/whip/speed-ramp effects.",
            "Review transition_cadence_contract_audit.json before Resolve apply so the finished film has full-boundary transition coverage, restrained motivated motion, no repeated-template cadence, and materialized bridge beats at important boundaries.",
            "Review transition_microstructure_contract_audit.json before Resolve apply so every adjacent shot transition has a BGM landing, title-safe/BGM-only window, handles, pair continuity, bridge beats, and a real apply path.",
            "Review final_source_usage_contract_audit.json before Resolve apply so the final raw clips actually come from footage_select_plan hero/main/texture choices and do not reintroduce unmatched, repair, reject, or utility-dominant sources.",
            "Review creator_cut_application_contract_audit.json before Resolve apply so rejected/utility/weak creator-cut rows cannot remain active in the final candidate blueprint.",
            "Review reference_scene_grammar_contract_audit.json before Resolve apply so opening, chapters, transitions, and ending follow the Parallel World/Malta scene-function grammar.",
            "Review reference_profile_application_contract_audit.json before Resolve apply so the reference batch profile reaches opening, chapter, rhythm, creator, transition, caption, audio, and style gates instead of staying as unused analysis.",
            "Review timeline_variety_contract_audit.json before Resolve apply so movement, lived-in texture, destination payoff, and ending aftertaste vary across the whole film instead of hiding weak shot choice behind transitions.",
            "Review transition_scene_arc_contract_audit.json before Resolve apply so important boundaries become outgoing/bridge-or-motion/BGM-hit/title-safe/landing scene arcs, not isolated effects.",
            "Review transition_effect_palette_contract_audit.json before Resolve apply so the whole film balances clean cuts, match cuts, bridges, dissolves, title reveals, and rare motivated motion instead of effect spam.",
            "Review transition_motif_coherence_contract_audit.json before Resolve apply so transition motifs form a coherent film language and reference-selected styles do not contradict motif rows.",
            "Review transition_visual_match_contract_audit.json before Resolve apply so every adjacent pair has concrete visual, bridge, motion, mood, title, local, or BGM continuity evidence instead of arbitrary effects.",
            "Review transition_source_coverage_contract_audit.json before Resolve apply so every transition row has selected outgoing, bridge, motion, and landing source material instead of hiding weak clips behind rotation, whip, or zoom effects.",
            "Review transition_choreography_plan/transition_choreography_plan.md and transition_choreography_contract_audit.json before preview/storyboard so every important boundary has outgoing, bridge-or-motion, landing, BGM-hit, and caption-quiet choreography.",
            "Review transition_motion_direction_contract_audit.json before preview/storyboard so rotation, whip, push, and speed-ramp effects match source or bridge movement direction instead of random motion.",
            "Review transition_preview_packet/transition_preview_packet.md, transition_preview_quality_contract_audit.json, transition_audition_packet/transition_audition_packet.md, transition_audition_quality_contract_audit.json, transition_watch_reel/transition_watch_reel.md, transition_audition_visual_proof_contract_audit.json, transition_audition_role_integrity_contract_audit.json, and transition_storyboard_contract_audit.json before Resolve apply so important route/title/day-change transitions have generated nonblank frame evidence plus playable muted outgoing/bridge/landing MP4 proof, one ordered watch reel, distinct endpoint, middle-motion, and ordered segment-role proof.",
            "Review transition_breathing_room_contract_audit.json before Resolve apply so motion accents are rare, separated by calm boundaries, and important transitions land on stable readable footage without title/subtitle collision.",
            "Review scene_flow_arc_contract_audit.json before Resolve apply so chapters form setup, movement, lived-in texture, payoff, and aftertaste/handoff arcs instead of landmark stacks or effect-hidden jumps.",
            "Review final_cut_smoothness_contract_audit.json before Resolve apply so the final candidate's adjacent shots have bridge, match, breathing, stable landing, and rare motion-effect proof instead of rough hard joins.",
            "Review transition_continuity_rehearsal_contract_audit.json before Resolve apply so row-to-row transition landings carry into the next outgoing shot and motion accents do not stack without stable buffer.",
            "Review pacing_watchability_contract_audit.json before Resolve apply so reference-calibrated shot lengths, chapter breathing, long-hold reduction, and short-clip readability are proven in the final candidate.",
            "Review narrative_adjacency_contract_audit.json before Resolve apply so every adjacent visual shot has a viewer-readable route, place, story-function, bridge, BGM, title, or transition reason instead of random clip stacking.",
            "Review transition_viewer_orientation_contract_audit.json before Resolve apply so important route/day/place/title/ending transitions tell viewers where they are, why the film moved, and what the landing shot means.",
            "Review transition_scene_settlement_contract_audit.json before Resolve apply so important transitions land into enough local scene footage instead of a title-only/card-only landing or an immediate second jump.",
            "Review transition_flow_repair_plan.json before Resolve apply or handoff; ready_with_transition_flow_repair_plan means transition/adjacent-shot repair rows are still open.",
            "Review reference_transition_profile_contract_audit.json before Resolve apply so the current film's transition language matches the learned reference bridge, breath, match, and restrained-motion profile.",
            "Review chapter_story_spine_contract_audit.json before Resolve apply so every chapter executes context, movement, lived-in texture, payoff, and aftertaste instead of becoming title-only or effect-masked.",
            "Preflight bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json before approving bridge sequence inserts for Resolve.",
            "Review rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json and preflight it before replacing the active Resolve blueprint.",
            "Review unattended_first_draft_contract_audit.json before Resolve apply or handoff; it proves raw intake, story, BGM, captions, titles, rhythm, transitions, repair closure, and blueprint preflight are connected.",
            "Review skill_maturity_contract_audit.json before handing the package to another AI; it proves the reusable Skill safeguards, not only one timeline, cover the known failure set.",
            "Review v14_baseline_contract_audit.json before claiming a first draft should feel like V14; it proves the V14 lessons are active gates rather than historical notes.",
            "Review unattended_repair_queue/unattended_repair_queue.md when any gate blocks; it orders P0/P1 repairs by owner script, command, required artifact, acceptance evidence, and forbidden workaround.",
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
