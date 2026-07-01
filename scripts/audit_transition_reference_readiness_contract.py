#!/usr/bin/env python3
"""Aggregate transition craft gates into one reference-readiness contract."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = "passed"
BLOCKED = "blocked_transition_reference_readiness"


def spec(
    report_id: str,
    path: str,
    accepted: set[str],
    phase: str,
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
        "phase": phase,
        "ownerScript": owner_script,
        "requiredArtifact": required_artifact,
        "command": command or f"python3 <skill-dir>/scripts/{owner_script} --package-dir <package> --json",
        "acceptanceEvidence": evidence,
        "forbiddenWorkaround": "Do not hide weak adjacent shots, route gaps, missing bridge footage, or unresolved style drift behind stronger transition effects.",
    }


REPORT_SPECS: tuple[dict[str, Any], ...] = (
    spec(
        "transition_pair_continuity_contract_audit",
        "transition_pair_continuity_contract_audit.json",
        {"passed"},
        "pair_continuity",
        "audit_transition_pair_continuity_contract.py",
        "transition_pair_continuity_contract_audit.json",
        "Every adjacent pair has continuity or an explicit viewer-readable transition reason.",
    ),
    spec(
        "transition_execution_readiness_contract_audit",
        "transition_execution_readiness_contract_audit.json",
        {"passed"},
        "execution",
        "audit_transition_execution_readiness_contract.py",
        "transition_execution_readiness_contract_audit.json",
        "Every transition row is executable, BGM-hit aware, title safe, and not marker-only prose.",
    ),
    spec(
        "transition_polish_application_contract_audit",
        "transition_polish_application_contract_audit.json",
        {"passed"},
        "execution",
        "audit_transition_polish_application_contract.py",
        "transition_polish_application_contract_audit.json",
        "Transition polish metadata survives into the active or final blueprint.",
    ),
    spec(
        "resolve_transition_materialization_contract_audit",
        "resolve_transition_materialization_contract_audit.json",
        {"passed"},
        "resolve_apply",
        "audit_resolve_transition_materialization_contract.py",
        "resolve_transition_materialization_contract_audit.json",
        "Resolve marker/readback payloads carry the transition recipe and effect payloads.",
    ),
    spec(
        "resolve_transition_apply_contract_audit",
        "resolve_transition_apply_contract_audit.json",
        {"passed"},
        "resolve_apply",
        "audit_resolve_transition_apply_contract.py",
        "resolve_transition_apply_contract_audit.json",
        "Visible effects are API-supported, materialized bridge clips, or completed readback/frame evidence.",
    ),
    spec(
        "bridge_sequence_application_contract_audit",
        "bridge_sequence_application_contract_audit.json",
        {"passed"},
        "bridge",
        "audit_bridge_sequence_application_contract.py",
        "bridge_sequence_application_contract_audit.json",
        "Important route/title/day/timeline-gap transitions have bridge beats that survive into the final candidate.",
    ),
    spec(
        "transition_bridge_visual_evidence_contract_audit",
        "transition_bridge_visual_evidence_contract_audit.json",
        {"passed"},
        "bridge",
        "audit_transition_bridge_visual_evidence_contract.py",
        "transition_bridge_visual_evidence_contract_audit.json",
        "Surviving bridge beats have real local source video, probe/frame evidence, and no source-camera audio leakage.",
        command="python3 <skill-dir>/scripts/audit_transition_bridge_visual_evidence_contract.py --package-dir <package> --extract-frames --json",
    ),
    spec(
        "transition_cadence_contract_audit",
        "transition_cadence_contract_audit.json",
        {"passed"},
        "film_cadence",
        "audit_transition_cadence_contract.py",
        "transition_cadence_contract_audit.json",
        "Film-level cadence is crafted without bare concatenation, repeated templates, or effect spam.",
    ),
    spec(
        "transition_microstructure_contract_audit",
        "transition_microstructure_contract_audit.json",
        {"passed"},
        "film_cadence",
        "audit_transition_microstructure_contract.py",
        "transition_microstructure_contract_audit.json",
        "Each boundary has outgoing, bridge-or-motion, landing, BGM-hit, and caption/title-safe structure.",
    ),
    spec(
        "transition_cutpoint_contract_audit",
        "transition_cutpoint_contract_audit.json",
        {"passed"},
        "cutpoint",
        "audit_transition_cutpoint_contract.py",
        "transition_cutpoint_contract_audit.json",
        "Cutpoints land on readable action, route, BGM, or visual-match anchors.",
    ),
    spec(
        "transition_action_anchor_contract_audit",
        "transition_action_anchor_contract_audit.json",
        {"passed"},
        "cutpoint",
        "audit_transition_action_anchor_contract.py",
        "transition_action_anchor_contract_audit.json",
        "Motion and match transitions have outgoing/landing action anchors.",
    ),
    spec(
        "transition_sensory_continuity_contract_audit",
        "transition_sensory_continuity_contract_audit.json",
        {"passed"},
        "sensory",
        "audit_transition_sensory_continuity_contract.py",
        "transition_sensory_continuity_contract_audit.json",
        "Transitions preserve visual, BGM, caption, route-or-mood, and landing continuity.",
    ),
    spec(
        "transition_scene_arc_contract_audit",
        "transition_scene_arc_contract_audit.json",
        {"passed"},
        "scene_flow",
        "audit_transition_scene_arc_contract.py",
        "transition_scene_arc_contract_audit.json",
        "Transitions support scene arc instead of jumping payoff-to-payoff without movement or breath.",
    ),
    spec(
        "transition_effect_palette_contract_audit",
        "transition_effect_palette_contract_audit.json",
        {"passed"},
        "style_palette",
        "audit_transition_effect_palette_contract.py",
        "transition_effect_palette_contract_audit.json",
        "Effect families match the reference-like palette with enough variety and restrained motion.",
    ),
    spec(
        "transition_motif_coherence_contract_audit",
        "transition_motif_coherence_contract_audit.json",
        {"passed"},
        "style_palette",
        "audit_transition_motif_coherence_contract.py",
        "transition_motif_coherence_contract_audit.json",
        "Motif rows and reference-selected style families form one deliberate film language.",
    ),
    spec(
        "transition_visual_match_contract_audit",
        "transition_visual_match_contract_audit.json",
        {"passed"},
        "style_palette",
        "audit_transition_visual_match_contract.py",
        "transition_visual_match_contract_audit.json",
        "Visual matches are backed by outgoing/landing evidence instead of arbitrary adjacent cuts.",
    ),
    spec(
        "transition_source_coverage_contract_audit",
        "transition_source_coverage_contract_audit.json",
        {"passed"},
        "source_coverage",
        "audit_transition_source_coverage_contract.py",
        "transition_source_coverage_contract_audit.json",
        "Outgoing, bridge, and landing footage coverage exists for important transition boundaries.",
    ),
    spec(
        "transition_reference_candidates",
        "transition_reference_candidates/transition_reference_candidates.json",
        {"ready_with_transition_reference_candidates"},
        "reference_choice",
        "prepare_transition_reference_candidates.py",
        "transition_reference_candidates/transition_reference_candidates.json",
        "Every boundary has non-copying A/B/C transition candidates.",
    ),
    spec(
        "transition_reference_selection",
        "transition_reference_selection/transition_reference_selection.json",
        {"ready_with_transition_reference_selection"},
        "reference_choice",
        "prepare_transition_reference_selection.py",
        "transition_reference_selection/transition_reference_selection.json",
        "Every boundary has a selected unattended-safe transition default or a blocked bridge-missing row.",
    ),
    spec(
        "transition_choreography_plan",
        "transition_choreography_plan/transition_choreography_plan.json",
        {"ready_with_transition_choreography_plan"},
        "choreography",
        "prepare_transition_choreography_plan.py",
        "transition_choreography_plan/transition_choreography_plan.json",
        "Important boundaries have outgoing, bridge-or-motion, landing, BGM-hit, and caption-quiet choreography.",
    ),
    spec(
        "transition_choreography_contract_audit",
        "transition_choreography_contract_audit.json",
        {"passed"},
        "choreography",
        "audit_transition_choreography_contract.py",
        "transition_choreography_contract_audit.json",
        "Choreography blocks repeated or high-intensity template-like motion.",
    ),
    spec(
        "transition_motion_direction_contract_audit",
        "transition_motion_direction_contract_audit.json",
        {"passed"},
        "motion",
        "audit_transition_motion_direction_contract.py",
        "transition_motion_direction_contract_audit.json",
        "Motion direction, push, rotation, whip, and ramp choices align with source movement and landing.",
    ),
    spec(
        "transition_motion_accent_contract_audit",
        "transition_motion_accent_contract_audit.json",
        {"passed"},
        "motion",
        "audit_transition_motion_accent_contract.py",
        "transition_motion_accent_contract_audit.json",
        "Motion accents are rare, motivated, source-backed, title-safe, and not back-to-back.",
    ),
    spec(
        "transition_motion_accent_repair_plan",
        "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        {"ready_no_motion_accent_repairs_needed"},
        "motion",
        "prepare_transition_motion_accent_repair_plan.py",
        "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "All motion-accent repair rows are closed before handoff.",
    ),
    spec(
        "transition_effect_recipe_contract_audit",
        "transition_effect_recipe_contract_audit.json",
        {"passed"},
        "motion",
        "audit_transition_effect_recipe_contract.py",
        "transition_effect_recipe_contract_audit.json",
        "Effect recipes have concrete duration, easing, keyframe, BGM-hit, and title-safe parameters.",
    ),
    spec(
        "rendered_transition_proof_contract_audit",
        "rendered_transition_proof_contract_audit.json",
        {"passed"},
        "rendered_proof",
        "audit_rendered_transition_proof_contract.py",
        "rendered_transition_proof_contract_audit.json",
        "Final MP4 transition windows have rendered-frame proof with no flash, raw portrait, or unstable landing blockers.",
    ),
    spec(
        "transition_preview_packet",
        "transition_preview_packet/transition_preview_packet.json",
        {"ready_with_transition_preview_packet", "ready_no_important_transitions"},
        "preview_audition",
        "prepare_transition_preview_packet.py",
        "transition_preview_packet/transition_preview_packet.json",
        "Important boundaries have package-local outgoing/landing frame evidence.",
        command="python3 <skill-dir>/scripts/prepare_transition_preview_packet.py --package-dir <package> --extract-frames --update-transition-grammar --json",
    ),
    spec(
        "transition_preview_quality_contract_audit",
        "transition_preview_quality_contract_audit.json",
        {"passed"},
        "preview_audition",
        "audit_transition_preview_quality_contract.py",
        "transition_preview_quality_contract_audit.json",
        "Preview frames are nonblank, local, decodable, and distinct enough to judge.",
    ),
    spec(
        "transition_audition_packet",
        "transition_audition_packet/transition_audition_packet.json",
        {"ready_with_transition_audition_packet", "ready_no_important_transitions"},
        "preview_audition",
        "prepare_transition_audition_packet.py",
        "transition_audition_packet/transition_audition_packet.json",
        "Important boundaries have playable muted outgoing/bridge/landing MP4 proof.",
        command="python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
    ),
    spec(
        "transition_audition_quality_contract_audit",
        "transition_audition_quality_contract_audit.json",
        {"passed"},
        "preview_audition",
        "audit_transition_audition_quality_contract.py",
        "transition_audition_quality_contract_audit.json",
        "Audition clips are local, muted, nonblank, ordered, and watchable.",
    ),
    spec(
        "transition_watch_reel",
        "transition_watch_reel/transition_watch_reel.json",
        {"ready_with_transition_watch_reel", "ready_no_important_transitions"},
        "watch_reel",
        "prepare_transition_watch_reel.py",
        "transition_watch_reel/transition_watch_reel.json",
        "Important transition auditions are concatenated into one ordered muted review reel.",
        command="python3 <skill-dir>/scripts/prepare_transition_watch_reel.py --package-dir <package> --build-reel --require-muted --json",
    ),
    spec(
        "transition_watch_reel_review_contract_audit",
        "transition_watch_reel_review_contract_audit.json",
        {"passed", "passed_no_important_transitions"},
        "watch_reel",
        "audit_transition_watch_reel_review_contract.py",
        "transition_watch_reel_review_contract_audit.json",
        "The ordered watch reel passes family-run, high-intensity-run, timing, local-media, and no-audio checks.",
    ),
    spec(
        "transition_audition_visual_proof_contract_audit",
        "transition_audition_visual_proof_contract_audit.json",
        {"passed"},
        "preview_audition",
        "audit_transition_audition_visual_proof_contract.py",
        "transition_audition_visual_proof_contract_audit.json",
        "Audition clips have frame proof for the transition window, not just JSON prose.",
        command="python3 <skill-dir>/scripts/audit_transition_audition_visual_proof_contract.py --package-dir <package> --extract-frames --json",
    ),
    spec(
        "transition_audition_role_integrity_contract_audit",
        "transition_audition_role_integrity_contract_audit.json",
        {"passed"},
        "preview_audition",
        "audit_transition_audition_role_integrity_contract.py",
        "transition_audition_role_integrity_contract_audit.json",
        "Outgoing, bridge/motion, and landing roles appear in the expected order.",
    ),
    spec(
        "transition_storyboard_contract_audit",
        "transition_storyboard_contract_audit.json",
        {"passed"},
        "storyboard",
        "audit_transition_storyboard_contract.py",
        "transition_storyboard_contract_audit.json",
        "Transition storyboard rows explain viewer purpose, outgoing, bridge, landing, BGM-hit, and safety.",
    ),
    spec(
        "reference_transition_profile_contract_audit",
        "reference_transition_profile_contract_audit.json",
        {"passed"},
        "reference_fit",
        "audit_reference_transition_profile_contract.py",
        "reference_transition_profile_contract_audit.json",
        "The current film's transitions match the learned bridge/breath/match/motion balance.",
    ),
    spec(
        "transition_breathing_room_contract_audit",
        "transition_breathing_room_contract_audit.json",
        {"passed"},
        "landing",
        "audit_transition_breathing_room_contract.py",
        "transition_breathing_room_contract_audit.json",
        "Motion or important transitions land into stable local footage before the next idea.",
    ),
    spec(
        "final_cut_smoothness_contract_audit",
        "final_cut_smoothness_contract_audit.json",
        {"passed"},
        "landing",
        "audit_final_cut_smoothness_contract.py",
        "final_cut_smoothness_contract_audit.json",
        "The final candidate has no rough hard joins after planning.",
    ),
    spec(
        "transition_continuity_rehearsal_contract_audit",
        "transition_continuity_rehearsal_contract_audit.json",
        {"passed"},
        "landing",
        "audit_transition_continuity_rehearsal_contract.py",
        "transition_continuity_rehearsal_contract_audit.json",
        "Transition flow is rehearsed as adjacent viewer continuity, not isolated effects.",
    ),
    spec(
        "narrative_adjacency_contract_audit",
        "narrative_adjacency_contract_audit.json",
        {"passed"},
        "landing",
        "audit_narrative_adjacency_contract.py",
        "narrative_adjacency_contract_audit.json",
        "Adjacent shots have route, place, story, BGM, bridge, or visual-match reasons.",
    ),
    spec(
        "transition_viewer_orientation_contract_audit",
        "transition_viewer_orientation_contract_audit.json",
        {"passed"},
        "landing",
        "audit_transition_viewer_orientation_contract.py",
        "transition_viewer_orientation_contract_audit.json",
        "Viewer understands where the film is after day/place/title/route transitions.",
    ),
    spec(
        "transition_scene_settlement_contract_audit",
        "transition_scene_settlement_contract_audit.json",
        {"passed"},
        "landing",
        "audit_transition_scene_settlement_contract.py",
        "transition_scene_settlement_contract_audit.json",
        "Important transitions settle into a readable scene before another transition or payoff.",
    ),
    spec(
        "transition_flow_repair_plan",
        "transition_flow_repair_plan/transition_flow_repair_plan.json",
        {"ready_no_transition_flow_repairs_needed"},
        "repair_closure",
        "prepare_transition_flow_repair_plan.py",
        "transition_flow_repair_plan/transition_flow_repair_plan.json",
        "All transition-flow repair rows are closed before final QA, V14, or handoff.",
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
        "repairId": f"transition_reference_readiness_{item['reportId']}",
        "reportId": item["reportId"],
        "sourceReport": "transition_reference_readiness_contract_audit",
        "sourceReportPath": str(path),
        "reportExists": path.exists(),
        "reportStatus": status,
        "acceptedStatuses": sorted(accepted),
        "passed": passed,
        "priority": item["priority"],
        "phase": item["phase"],
        "issue": issue,
        "ownerScript": item["ownerScript"],
        "requiredArtifact": item["requiredArtifact"],
        "command": item["command"],
        "acceptanceEvidence": item["acceptanceEvidence"],
        "forbiddenWorkaround": item["forbiddenWorkaround"],
        "summary": summary(data),
        "blockers": [clean(value) for value in blockers[:12]],
        "warnings": [clean(value) for value in (data.get("warnings") or [])[:12]] if isinstance(data, dict) else [],
    }


def metric_issues(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_report = {row["reportId"]: row for row in rows}
    issues: list[dict[str, Any]] = []
    watch = by_report.get("transition_watch_reel_review_contract_audit", {}).get("summary", {})
    if watch:
        if as_int(watch.get("highIntensityRunMax")) > 1:
            issues.append({"metric": "highIntensityRunMax", "value": watch.get("highIntensityRunMax"), "limit": 1})
        if as_int(watch.get("familyRunMax")) > 2:
            issues.append({"metric": "familyRunMax", "value": watch.get("familyRunMax"), "limit": 2})
        if watch.get("reelHasAudio") is True:
            issues.append({"metric": "reelHasAudio", "value": True, "limit": False})
    accent = by_report.get("transition_motion_accent_contract_audit", {}).get("summary", {})
    for key in (
        "blockedMotionAccentRowCount",
        "highIntensityMotionCount",
        "rotationTooStrongCount",
        "unsupportedMotionAccentCount",
        "directionMismatchMotionCount",
        "titleOrCaptionRiskMotionCount",
        "missingAnchorMotionCount",
        "missingSensoryMotionCount",
    ):
        if as_int(accent.get(key)) > 0:
            issues.append({"metric": key, "value": accent.get(key), "limit": 0})
    rendered = by_report.get("rendered_transition_proof_contract_audit", {}).get("summary", {})
    for key in ("blackFrameCount", "whiteFlashFrameCount", "rawPortraitFrameCount", "unstableLandingFrameCount"):
        if as_int(rendered.get(key)) > 0:
            issues.append({"metric": key, "value": rendered.get(key), "limit": 0})
    return issues


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    evidence_rows = [row_from_spec(package_dir, item) for item in REPORT_SPECS]
    readiness_rows = [row for row in evidence_rows if not row["passed"]]
    metric_rows = metric_issues(evidence_rows)
    p0_rows = [row for row in readiness_rows if row.get("priority") == "P0"]
    p1_rows = [row for row in readiness_rows if row.get("priority") == "P1"]
    phase_counts: dict[str, int] = {}
    for row in readiness_rows:
        phase_counts[row["phase"]] = phase_counts.get(row["phase"], 0) + 1
    status = PASSED if not readiness_rows and not metric_rows else BLOCKED
    summary_payload = {
        "requiredTransitionReportCount": len(evidence_rows),
        "passedTransitionReportCount": len([row for row in evidence_rows if row["passed"]]),
        "transitionReadinessRowCount": len(readiness_rows),
        "p0TransitionReadinessRowCount": len(p0_rows),
        "p1TransitionReadinessRowCount": len(p1_rows),
        "metricIssueCount": len(metric_rows),
        "phaseCounts": phase_counts,
        "ownerScripts": sorted({row["ownerScript"] for row in readiness_rows}),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "summary": summary_payload,
        "evidenceRows": evidence_rows,
        "transitionReadinessRows": readiness_rows,
        "repairRows": readiness_rows,
        "metricIssues": metric_rows,
        "policy": {
            "allTransitionCraftReportsRequired": True,
            "referenceTransitionProfileRequired": True,
            "watchReelReviewRequired": True,
            "renderedTransitionProofRequired": True,
            "repairClosureRequired": True,
            "noResolveWrites": True,
        },
        "nextActions": [
            "Run owner scripts for open P0 transition readiness rows before another Resolve render or handoff.",
            "Rerun the named source report after each transition repair, then rerun this contract.",
            "Only pass final QA or V14 when this contract has zero transition readiness rows and zero metric issues.",
        ],
        "safety": safety(),
    }
    if args.max_rows and len(report["transitionReadinessRows"]) > args.max_rows:
        report["transitionReadinessRows"] = report["transitionReadinessRows"][: args.max_rows]
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Reference Readiness Contract",
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
        "## Open Transition Readiness Rows",
    ]
    if not report.get("transitionReadinessRows"):
        lines.append("- None.")
    for row in report.get("transitionReadinessRows", [])[:200]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Phase: `{row.get('phase')}`",
                f"- Report: `{row.get('reportId')}` status=`{row.get('reportStatus')}`",
                f"- Issue: {row.get('issue')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Command: `{row.get('command')}`",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
            ]
        )
        if row.get("blockers"):
            lines.append(f"- Source blockers: `{'; '.join(row.get('blockers') or [])}`")
    if report.get("metricIssues"):
        lines.extend(["", "## Metric Issues"])
        for item in report["metricIssues"]:
            lines.append(f"- `{item.get('metric')}` value `{item.get('value')}` exceeds limit `{item.get('limit')}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- This gate proves the transition chain is reference-ready as a whole, not only locally plausible.",
            "- It is read-only: no Resolve writes, no render queue, no downloads, no source-drive mutation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit reference-readiness across all transition craft gates.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    output_json = package_dir / "transition_reference_readiness_contract_audit.json"
    output_md = package_dir / "transition_reference_readiness_contract_audit.md"
    write_json(output_json, report)
    write_markdown(output_md, report)
    payload = (
        report
        if args.json
        else {
            "status": report["status"],
            "summary": report["summary"],
            "blockers": [row["repairId"] for row in report["transitionReadinessRows"]],
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
