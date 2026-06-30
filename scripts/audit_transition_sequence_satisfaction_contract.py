#!/usr/bin/env python3
"""Audit whether the transition sequence is viewer-satisfying as one film language."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = "passed"
BLOCKED = "blocked_transition_sequence_satisfaction"


def spec(
    report_id: str,
    path: str,
    accepted: set[str],
    category: str,
    symptom: str,
    owner_script: str,
    required_artifact: str,
    evidence: str,
    priority: str = "P0",
    command: str | None = None,
) -> dict[str, Any]:
    return {
        "reportId": report_id,
        "path": path,
        "accepted": accepted,
        "priority": priority,
        "category": category,
        "phase": "transition_flow",
        "viewerSymptom": symptom,
        "ownerScript": owner_script,
        "requiredArtifact": required_artifact,
        "command": command or f"python3 <skill-dir>/scripts/{owner_script} --package-dir <package> --json",
        "acceptanceEvidence": evidence,
        "forbiddenWorkaround": (
            "Do not hide weak adjacent shots, missing bridge footage, unclear route jumps, or "
            "unsettled landings behind random rotation, whip, flash, speed-ramp, or template effects."
        ),
    }


SEQUENCE_SPECS: tuple[dict[str, Any], ...] = (
    spec(
        "transition_reference_readiness_contract_audit",
        "transition_reference_readiness_contract_audit.json",
        {"passed"},
        "sequence_readiness",
        "The transition chain may pass isolated checks but still not be reference-ready as one sequence.",
        "audit_transition_reference_readiness_contract.py",
        "transition_reference_readiness_contract_audit.json",
        "Transition reference-readiness passes with zero readiness rows and zero metric issues.",
    ),
    spec(
        "transition_watch_reel",
        "transition_watch_reel/transition_watch_reel.json",
        {"ready_with_transition_watch_reel", "ready_no_important_transitions"},
        "watch_reel",
        "Important transitions have not been reviewed as one ordered muted reel.",
        "prepare_transition_watch_reel.py",
        "transition_watch_reel/transition_watch_reel.json",
        "The ordered transition watch reel is package-local, muted, built when important transitions exist, and reviewable.",
        command="python3 <skill-dir>/scripts/prepare_transition_watch_reel.py --package-dir <package> --build-reel --json",
    ),
    spec(
        "transition_watch_reel_review_contract_audit",
        "transition_watch_reel_review_contract_audit.json",
        {"passed", "passed_no_important_transitions"},
        "watch_reel",
        "The ordered reel may leak audio, repeat one template family, or stack high-intensity motion.",
        "audit_transition_watch_reel_review_contract.py",
        "transition_watch_reel_review_contract_audit.json",
        "Watch-reel review proves no audio leakage, invalid timing, repeated template runs, or high-intensity effect spam.",
    ),
    spec(
        "transition_flow_repair_plan",
        "transition_flow_repair_plan/transition_flow_repair_plan.json",
        {"ready_no_transition_flow_repairs_needed"},
        "repair_closure",
        "Known transition-flow repair rows are still open.",
        "prepare_transition_flow_repair_plan.py",
        "transition_flow_repair_plan/transition_flow_repair_plan.json",
        "Transition-flow repair plan is closed before final QA, V14, or handoff.",
    ),
    spec(
        "transition_cadence_contract_audit",
        "transition_cadence_contract_audit.json",
        {"passed"},
        "rhythm_cadence",
        "The film-level transition rhythm may still feel like bare cuts or repeated effects.",
        "audit_transition_cadence_contract.py",
        "transition_cadence_contract_audit.json",
        "Cadence audit proves whole-film transition rhythm, variety, and restraint.",
    ),
    spec(
        "transition_microstructure_contract_audit",
        "transition_microstructure_contract_audit.json",
        {"passed"},
        "rhythm_cadence",
        "Individual boundaries may lack outgoing, bridge-or-match, BGM hit, and landing structure.",
        "audit_transition_microstructure_contract.py",
        "transition_microstructure_contract_audit.json",
        "Microstructure audit proves each boundary has viewer-readable leave, hit, and landing evidence.",
    ),
    spec(
        "transition_scene_arc_contract_audit",
        "transition_scene_arc_contract_audit.json",
        {"passed"},
        "story_flow",
        "Transitions may jump payoff-to-payoff without movement, breath, or route meaning.",
        "audit_transition_scene_arc_contract.py",
        "transition_scene_arc_contract_audit.json",
        "Scene-arc audit proves transitions support setup, movement, texture, payoff, and handoff.",
    ),
    spec(
        "transition_effect_palette_contract_audit",
        "transition_effect_palette_contract_audit.json",
        {"passed"},
        "style_palette",
        "Effects may read as a template pack instead of a coherent travel-film language.",
        "audit_transition_effect_palette_contract.py",
        "transition_effect_palette_contract_audit.json",
        "Effect palette audit proves restrained variety and avoids one-family effect dominance.",
    ),
    spec(
        "transition_motif_coherence_contract_audit",
        "transition_motif_coherence_contract_audit.json",
        {"passed"},
        "style_palette",
        "Transition motifs may not connect to the selected reference-calibrated language.",
        "audit_transition_motif_coherence_contract.py",
        "transition_motif_coherence_contract_audit.json",
        "Motif coherence proves selected transition families form one deliberate film language.",
    ),
    spec(
        "transition_visual_match_contract_audit",
        "transition_visual_match_contract_audit.json",
        {"passed"},
        "story_flow",
        "Adjacent cuts may look arbitrary rather than visually matched or intentionally bridged.",
        "audit_transition_visual_match_contract.py",
        "transition_visual_match_contract_audit.json",
        "Visual-match audit proves outgoing and landing evidence for match-based cuts.",
    ),
    spec(
        "transition_source_coverage_contract_audit",
        "transition_source_coverage_contract_audit.json",
        {"passed"},
        "source_coverage",
        "Important boundaries may not have enough outgoing, bridge, or landing footage to feel intentional.",
        "audit_transition_source_coverage_contract.py",
        "transition_source_coverage_contract_audit.json",
        "Source coverage proves important boundaries have real local footage coverage.",
    ),
    spec(
        "transition_audition_packet",
        "transition_audition_packet/transition_audition_packet.json",
        {"ready_with_transition_audition_packet", "ready_no_important_transitions"},
        "watch_reel",
        "Important transition candidates may lack playable local audition clips.",
        "prepare_transition_audition_packet.py",
        "transition_audition_packet/transition_audition_packet.json",
        "Audition packet proves important boundaries have playable muted outgoing/bridge/landing clips.",
        command="python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
    ),
    spec(
        "transition_audition_quality_contract_audit",
        "transition_audition_quality_contract_audit.json",
        {"passed"},
        "watch_reel",
        "Transition audition clips may be blank, too short, noisy, unordered, or not local.",
        "audit_transition_audition_quality_contract.py",
        "transition_audition_quality_contract_audit.json",
        "Audition quality proves local, muted, nonblank, ordered, and watchable clips.",
    ),
    spec(
        "transition_audition_visual_proof_contract_audit",
        "transition_audition_visual_proof_contract_audit.json",
        {"passed"},
        "watch_reel",
        "Auditions may be accepted without actual frame proof for the transition window.",
        "audit_transition_audition_visual_proof_contract.py",
        "transition_audition_visual_proof_contract_audit.json",
        "Audition visual proof includes endpoint and middle-motion frames for every audition row.",
        command="python3 <skill-dir>/scripts/audit_transition_audition_visual_proof_contract.py --package-dir <package> --extract-frames --json",
    ),
    spec(
        "transition_audition_role_integrity_contract_audit",
        "transition_audition_role_integrity_contract_audit.json",
        {"passed"},
        "watch_reel",
        "Audition clips may concatenate outgoing, bridge, motion, and landing roles in the wrong order.",
        "audit_transition_audition_role_integrity_contract.py",
        "transition_audition_role_integrity_contract_audit.json",
        "Role integrity proves outgoing, bridge-or-motion, and landing segments appear in order.",
    ),
    spec(
        "transition_storyboard_contract_audit",
        "transition_storyboard_contract_audit.json",
        {"passed"},
        "story_flow",
        "Important transitions may lack viewer purpose, bridge, BGM-hit, or landing explanation.",
        "audit_transition_storyboard_contract.py",
        "transition_storyboard_contract_audit.json",
        "Storyboard proof explains viewer purpose, outgoing, bridge, landing, BGM hit, and safety.",
    ),
    spec(
        "transition_breathing_room_contract_audit",
        "transition_breathing_room_contract_audit.json",
        {"passed"},
        "bridge_landing",
        "Motion or important transitions may not settle into stable local footage before the next idea.",
        "audit_transition_breathing_room_contract.py",
        "transition_breathing_room_contract_audit.json",
        "Breathing-room audit proves stable, quiet landing footage after important or motion-heavy transitions.",
    ),
    spec(
        "final_cut_smoothness_contract_audit",
        "final_cut_smoothness_contract_audit.json",
        {"passed"},
        "bridge_landing",
        "Adjacent joins may still feel rough, effect-hidden, or unlanded.",
        "audit_final_cut_smoothness_contract.py",
        "final_cut_smoothness_contract_audit.json",
        "Final-cut smoothness proves bridge, match, breathing, stable landing, and rare motion-effect proof.",
    ),
    spec(
        "transition_continuity_rehearsal_contract_audit",
        "transition_continuity_rehearsal_contract_audit.json",
        {"passed"},
        "bridge_landing",
        "Approved transition rows may not connect as one watchable route sequence.",
        "audit_transition_continuity_rehearsal_contract.py",
        "transition_continuity_rehearsal_contract_audit.json",
        "Continuity rehearsal proves row-to-row transition flow as adjacent viewer continuity.",
    ),
    spec(
        "pacing_watchability_contract_audit",
        "pacing_watchability_contract_audit.json",
        {"passed"},
        "rhythm_cadence",
        "Transitions may be covering long holds, flickery short runs, or flat AI pacing.",
        "audit_pacing_watchability_contract.py",
        "pacing_watchability_contract_audit.json",
        "Pacing watchability proves shot lengths, chapter breath, and short-clip runs are readable.",
    ),
    spec(
        "narrative_adjacency_contract_audit",
        "narrative_adjacency_contract_audit.json",
        {"passed"},
        "story_flow",
        "Adjacent shots may have no route, place, story, bridge, BGM, title, or visual-match reason.",
        "audit_narrative_adjacency_contract.py",
        "narrative_adjacency_contract_audit.json",
        "Narrative adjacency proves each join has a viewer-readable reason.",
    ),
    spec(
        "transition_viewer_orientation_contract_audit",
        "transition_viewer_orientation_contract_audit.json",
        {"passed"},
        "viewer_orientation",
        "After a day/place/title/route transition, viewers may not know where they are or why the film moved.",
        "audit_transition_viewer_orientation_contract.py",
        "transition_viewer_orientation_contract_audit.json",
        "Viewer orientation proves important route/day/title jumps keep viewers oriented after the cut.",
    ),
    spec(
        "transition_scene_settlement_contract_audit",
        "transition_scene_settlement_contract_audit.json",
        {"passed"},
        "bridge_landing",
        "The landing after an important transition may be too fast, generic, or title-only.",
        "audit_transition_scene_settlement_contract.py",
        "transition_scene_settlement_contract_audit.json",
        "Scene settlement proves important transitions land into readable local scenes before another jump.",
    ),
    spec(
        "transition_motion_accent_contract_audit",
        "transition_motion_accent_contract_audit.json",
        {"passed"},
        "motion_restraint",
        "Whip, rotation, push, zoom, or speed-ramp accents may be random, repeated, or title-unsafe.",
        "audit_transition_motion_accent_contract.py",
        "transition_motion_accent_contract_audit.json",
        "Motion-accent audit proves rare, motivated, direction-matched, title-safe, readable accents.",
    ),
    spec(
        "transition_motion_accent_repair_plan",
        "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        {"ready_no_motion_accent_repairs_needed"},
        "motion_restraint",
        "Motion-accent repair rows are still open.",
        "prepare_transition_motion_accent_repair_plan.py",
        "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "Motion-accent repair plan is closed before visible motion is trusted.",
    ),
    spec(
        "transition_effect_recipe_contract_audit",
        "transition_effect_recipe_contract_audit.json",
        {"passed"},
        "motion_restraint",
        "Visible effects may not have restrained timing, easing, BGM-hit, title-safe, and landing parameters.",
        "audit_transition_effect_recipe_contract.py",
        "transition_effect_recipe_contract_audit.json",
        "Effect recipes prove concrete restrained parameters and stable landing holds.",
    ),
    spec(
        "rendered_transition_proof_contract_audit",
        "rendered_transition_proof_contract_audit.json",
        {"passed"},
        "rendered_proof",
        "The final render may hide black flashes, white flashes, raw portrait frames, or unstable landings.",
        "audit_rendered_transition_proof_contract.py",
        "rendered_transition_proof_contract_audit.json",
        "Rendered transition proof passes on current final-MP4 windows.",
    ),
    spec(
        "resolve_transition_apply_contract_audit",
        "resolve_transition_apply_contract_audit.json",
        {"passed"},
        "resolve_apply",
        "Visible transitions may be marker-only, manual-only, or missing Resolve readback proof.",
        "audit_resolve_transition_apply_contract.py",
        "resolve_transition_apply_contract_audit.json",
        "Resolve apply audit proves visible transitions are API-supported, materialized bridge clips, or completed readback/frame evidence.",
    ),
    spec(
        "bridge_sequence_application_contract_audit",
        "bridge_sequence_application_contract_audit.json",
        {"passed"},
        "bridge_landing",
        "Planned route/title/day-change bridge beats may be dropped from the final candidate.",
        "audit_bridge_sequence_application_contract.py",
        "bridge_sequence_application_contract_audit.json",
        "Bridge-sequence application proves planned bridge beats survive into the final candidate.",
    ),
    spec(
        "transition_bridge_visual_evidence_contract_audit",
        "transition_bridge_visual_evidence_contract_audit.json",
        {"passed"},
        "bridge_landing",
        "Bridge beats may be prose-only, nonlocal, unframed, or leaking source-camera audio.",
        "audit_transition_bridge_visual_evidence_contract.py",
        "transition_bridge_visual_evidence_contract_audit.json",
        "Bridge visual evidence proves surviving bridge beats have local video, probe/frame evidence, and no source audio leakage.",
        command="python3 <skill-dir>/scripts/audit_transition_bridge_visual_evidence_contract.py --package-dir <package> --extract-frames --json",
    ),
    spec(
        "reference_transition_profile_contract_audit",
        "reference_transition_profile_contract_audit.json",
        {"passed"},
        "reference_fit",
        "The current transition language may not match the learned bridge, breath, match, and restrained-motion profile.",
        "audit_reference_transition_profile_contract.py",
        "reference_transition_profile_contract_audit.json",
        "Reference transition profile proves the current film applies learned non-copying transition balance.",
    ),
    spec(
        "reference_profile_application_contract_audit",
        "reference_profile_application_contract_audit.json",
        {"passed"},
        "reference_fit",
        "Reference learning may remain unused analysis rather than applied edit behavior.",
        "audit_reference_profile_application_contract.py",
        "reference_profile_application_contract_audit.json",
        "Reference-profile application proves the learned style targets reach opening, rhythm, transitions, captions, audio, and ending.",
    ),
)


PROBLEM_COUNT_KEYS = {
    "transitionReadinessRowCount",
    "p0TransitionReadinessRowCount",
    "p1TransitionReadinessRowCount",
    "metricIssueCount",
    "blockedReelRowCount",
    "blockedReviewRowCount",
    "blockedTransitionRowCount",
    "blockedRowCount",
    "blockedCheckCount",
    "blockedRecipeRowCount",
    "blockerCount",
    "blockedSettlementCount",
    "shortSettlementCount",
    "tooFastNextJumpCount",
    "genericLandingOrUtilityCount",
    "importantBlockedRowCount",
    "blockedPairCount",
    "unmotivatedPairCount",
    "payoffJumpWithoutBridgeCount",
    "longFlatShotCount",
    "veryLongShotCount",
    "rowsWithBlankOrBlackFrame",
    "rowsWithWhiteFlash",
    "rowsWithPillarbox",
    "rowsWithStrobeLikeLumaJump",
    "pendingManualVisibleEffectRowCount",
    "blockedMotionAccentRowCount",
    "highIntensityMotionCount",
    "rotationTooStrongCount",
    "unsupportedMotionAccentCount",
    "directionMismatchMotionCount",
    "titleOrCaptionRiskMotionCount",
    "missingAnchorMotionCount",
    "missingSensoryMotionCount",
    "openRepairRowCount",
    "supportingReportIssueCount",
    "audioLeakRowCount",
    "sourceAudioLeakRowCount",
    "reelAudioStreamCount",
    "invalidTimingRowCount",
    "missingReportCount",
    "missingEvidenceCount",
    "missingFrameProofCount",
    "missingLocalMediaCount",
    "unstableLandingFrameCount",
    "rawPortraitFrameCount",
    "blackFrameCount",
    "whiteFlashFrameCount",
    "unresolvedPlaceholderCount",
}


MAX_LIMITS = {
    "highIntensityRunMax": 1,
    "familyRunMax": 2,
    "motionAccentRunMax": 1,
    "shortClipRunMax": 2,
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


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def summary(data: Any) -> dict[str, Any]:
    return data.get("summary") if isinstance(data, dict) and isinstance(data.get("summary"), dict) else {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def row_from_spec(package_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    path = package_dir / item["path"]
    data = load_json(path) or {}
    status = data.get("status") if isinstance(data, dict) else None
    blockers = data.get("blockers") if isinstance(data, dict) and isinstance(data.get("blockers"), list) else []
    warnings = data.get("warnings") if isinstance(data, dict) and isinstance(data.get("warnings"), list) else []
    accepted = set(item["accepted"])
    passed = bool(path.exists() and status in accepted and not blockers)
    if not path.exists():
        issue = f"{item['reportId']} is missing"
    elif status not in accepted:
        issue = f"{item['reportId']} status is {status!r}; expected one of {sorted(accepted)}"
    elif blockers:
        issue = f"{item['reportId']} still has blockers"
    else:
        issue = ""
    return {
        "repairId": f"transition_sequence_satisfaction_{item['reportId']}",
        "reportId": item["reportId"],
        "sourceReport": "transition_sequence_satisfaction_contract_audit",
        "sourceReportPath": str(path),
        "reportExists": path.exists(),
        "reportStatus": status,
        "acceptedStatuses": sorted(accepted),
        "passed": passed,
        "priority": item["priority"],
        "category": item["category"],
        "phase": item["phase"],
        "viewerSymptom": item["viewerSymptom"],
        "issue": issue,
        "ownerScript": item["ownerScript"],
        "requiredArtifact": item["requiredArtifact"],
        "command": item["command"],
        "acceptanceEvidence": item["acceptanceEvidence"],
        "forbiddenWorkaround": item["forbiddenWorkaround"],
        "summary": summary(data),
        "blockers": [clean(value) for value in blockers[:12]],
        "warnings": [clean(value) for value in warnings[:12]],
    }


def metric_issue_row(row: dict[str, Any], metric: str, value: Any, limit: Any, issue: str) -> dict[str, Any]:
    result = dict(row)
    result.update(
        {
            "repairId": f"transition_sequence_metric_{row['reportId']}_{metric}",
            "passed": False,
            "priority": "P0",
            "category": "metric_issue",
            "viewerSymptom": row.get("viewerSymptom") or "Transition sequence still has viewer-facing metric friction.",
            "issue": issue,
            "metric": metric,
            "metricValue": value,
            "metricLimit": limit,
        }
    )
    return result


def relation_issue_rows(row: dict[str, Any], data: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if row["reportId"] == "transition_watch_reel":
        clip_count = as_int(data.get("clipCount"))
        if row.get("reportStatus") == "ready_with_transition_watch_reel" and data.get("reelBuilt") is not True:
            issues.append(metric_issue_row(row, "reelBuilt", data.get("reelBuilt"), True, "transition watch reel was expected but not built"))
        if as_int(data.get("packageLocalClipCount")) < clip_count:
            issues.append(metric_issue_row(row, "packageLocalClipCount", data.get("packageLocalClipCount"), f">= {clip_count}", "some transition reel clips are not package-local"))
        if as_int(data.get("mutedClipCount")) < clip_count:
            issues.append(metric_issue_row(row, "mutedClipCount", data.get("mutedClipCount"), f">= {clip_count}", "some transition reel clips are not muted"))
    if row["reportId"] == "transition_audition_visual_proof_contract_audit":
        count = as_int(data.get("auditionVisualRowCount"))
        for key in ("rowsWithFrameProof", "rowsWithDistinctEndpointFrames", "rowsWithMiddleMotionProof"):
            if as_int(data.get(key)) < count:
                issues.append(metric_issue_row(row, key, data.get(key), f">= {count}", f"{key} does not cover every audition visual row"))
    if row["reportId"] == "transition_audition_role_integrity_contract_audit":
        count = as_int(data.get("auditionRoleRowCount"))
        for key in ("rowsWithRoleOrderedSegments", "rowsWithBridgeOrMotionSegment", "rowsWithConcatOrderEvidence"):
            if as_int(data.get(key)) < count:
                issues.append(metric_issue_row(row, key, data.get(key), f">= {count}", f"{key} does not cover every audition role row"))
    return issues


def metric_issues(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        data = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        for key in sorted(PROBLEM_COUNT_KEYS):
            if as_int(data.get(key)) > 0:
                issues.append(metric_issue_row(row, key, data.get(key), 0, f"{row['reportId']} summary has nonzero {key}"))
        for key, max_value in MAX_LIMITS.items():
            if as_int(data.get(key)) > max_value:
                issues.append(metric_issue_row(row, key, data.get(key), f"<= {max_value}", f"{row['reportId']} summary exceeds {key} limit"))
        if data.get("reelHasAudio") is True:
            issues.append(metric_issue_row(row, "reelHasAudio", True, False, "transition watch reel has audio leakage"))
        issues.extend(relation_issue_rows(row, data))
    return issues


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    evidence_rows = [row_from_spec(package_dir, item) for item in SEQUENCE_SPECS]
    failed_rows = [row for row in evidence_rows if not row["passed"]]
    metric_rows = metric_issues(evidence_rows)
    sequence_rows = failed_rows + metric_rows
    p0_rows = [row for row in sequence_rows if row.get("priority") == "P0"]
    p1_rows = [row for row in sequence_rows if row.get("priority") == "P1"]
    category_counts: dict[str, int] = {}
    for row in sequence_rows:
        category_counts[str(row.get("category"))] = category_counts.get(str(row.get("category")), 0) + 1
    status = PASSED if not sequence_rows else BLOCKED
    summary_payload = {
        "requiredSequenceReportCount": len(evidence_rows),
        "passedSequenceReportCount": len([row for row in evidence_rows if row["passed"]]),
        "transitionSequenceRowCount": len(sequence_rows),
        "p0TransitionSequenceRowCount": len(p0_rows),
        "p1TransitionSequenceRowCount": len(p1_rows),
        "missingReportCount": len([row for row in failed_rows if not row.get("reportExists")]),
        "blockedReportCount": len([row for row in failed_rows if row.get("reportExists")]),
        "metricIssueCount": len(metric_rows),
        "categoryCounts": category_counts,
        "ownerScripts": sorted({row["ownerScript"] for row in sequence_rows}),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "contract": "transition_sequence_satisfaction",
        "packageDir": str(package_dir),
        "summary": summary_payload,
        "evidenceRows": evidence_rows,
        "transitionSequenceRows": sequence_rows,
        "repairRows": sequence_rows,
        "metricIssues": metric_rows,
        "policy": {
            "blocksFinalQaV14AndHandoffWhenOpen": True,
            "requiresOrderedMutedWatchReelReview": True,
            "requiresBridgeBreathLandingProof": True,
            "requiresRestrainedReferenceCalibratedMotion": True,
            "requiresResolveApplyAndRenderedProof": True,
            "noResolveWrites": True,
        },
        "nextActions": [
            "Run owner scripts for P0 transition sequence rows before another Resolve render or handoff.",
            "Rerun each source report after repair, then rerun this contract before final viewer friction, first-draft satisfaction, final QA, V14, or handoff.",
            "Do not call a draft Parallel World/Malta-level while this contract has transition sequence rows or metric issues.",
        ],
        "safety": safety(),
    }
    if args.max_rows and len(report["transitionSequenceRows"]) > args.max_rows:
        report["transitionSequenceRows"] = report["transitionSequenceRows"][: args.max_rows]
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Sequence Satisfaction Contract",
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
        "## Open Transition Sequence Rows",
    ]
    if not report.get("transitionSequenceRows"):
        lines.append("- None.")
    for row in report.get("transitionSequenceRows", [])[:200]:
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
            "- This gate proves the transitions are satisfying as one viewer sequence, not just locally valid reports.",
            "- It is read-only: no Resolve writes, no render queue, no downloads, no source-drive mutation.",
            "- It blocks random rotation/whip/template effects when bridge, breath, route meaning, or landing proof is missing.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit viewer-level satisfaction across the whole transition sequence.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    output_json = package_dir / "transition_sequence_satisfaction_contract_audit.json"
    output_md = package_dir / "transition_sequence_satisfaction_contract_audit.md"
    write_json(output_json, report)
    write_markdown(output_md, report)
    payload = (
        report
        if args.json
        else {
            "status": report["status"],
            "summary": report["summary"],
            "blockers": [row["repairId"] for row in report["transitionSequenceRows"]],
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
