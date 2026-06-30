#!/usr/bin/env python3
"""Aggregate final-viewer friction into executable repair rows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = "passed"
BLOCKED = "blocked_final_viewer_friction"


REPORT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "reportId": "render_delivery_verification",
        "path": "render_delivery_verification.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "final_output",
        "viewerSymptom": "The final MP4 is stale, missing, technically weak, or not verified as a high-quality 4K/high-FPS export.",
        "ownerScript": "prepare_resolve_render.py",
        "requiredArtifact": "render_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_resolve_render.py --package-dir <package> --json",
        "acceptanceEvidence": "Render verification passes on the current final MP4 with the target FPS, bitrate, subtitles, audio, and black-frame checks.",
        "forbiddenWorkaround": "Do not judge viewer quality from stale exports, low-frame-rate drafts, screenshots, or unverified renders.",
    },
    {
        "reportId": "visual_audio_style_audit",
        "path": "visual_audio_style_audit/visual_audio_style_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "opening_audio_visual",
        "viewerSymptom": "The viewer sees or hears a weak first impression: bad title frame, black/scenic mismatch, missing BGM, or voice leakage.",
        "ownerScript": "prepare_scenic_title_bridges.py",
        "requiredArtifact": "clean_scenic_title_bridges/clean_scenic_title_bridges_manifest.json",
        "command": "python3 <skill-dir>/scripts/prepare_scenic_title_bridges.py --package-dir <package> --json",
        "acceptanceEvidence": "Visual/audio style audit passes against the current output and current visual/BGM manifests.",
        "forbiddenWorkaround": "Do not cover title or audio problems with extra labels, shadows, workflow captions, or stronger effects.",
    },
    {
        "reportId": "cover_title_contract_audit",
        "path": "cover_title_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "opening_title",
        "viewerSymptom": "Opening or cover title looks unlike the reference: ghosted, stacked, route/date cluttered, or not on a strong scenic frame.",
        "ownerScript": "prepare_title_typography_plan.py",
        "requiredArtifact": "title_typography_plan/title_typography_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Cover-title, title bridge, and title visual proof audits pass with actual clean 16:9 frame evidence.",
        "forbiddenWorkaround": "Do not add duplicate text, route labels, date labels, or drop shadows to hide a weak title composition.",
    },
    {
        "reportId": "title_visual_proof_contract_audit",
        "path": "title_visual_proof_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "opening_title",
        "viewerSymptom": "Title claims are only manifest prose; no extracted local frames prove the viewer actually sees a clean title.",
        "ownerScript": "audit_title_visual_proof_contract.py",
        "requiredArtifact": "title_visual_proof_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_title_visual_proof_contract.py --package-dir <package> --extract-frames --json",
        "acceptanceEvidence": "Extracted title frames prove no stacked text, subtitle collision, black slate, or wrong title media.",
        "forbiddenWorkaround": "Do not close title defects from OCR excuses, contact sheets, or old title screenshots.",
    },
    {
        "reportId": "audience_caption_contract_audit",
        "path": "audience_caption_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "caption_audio",
        "viewerSymptom": "Subtitles feel like notes to the editor or workflow report instead of natural viewer-facing travel-film text.",
        "ownerScript": "prepare_caption_story_plan.py",
        "requiredArtifact": "caption_story_plan/caption_story_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_caption_story_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Audience-caption audit passes and TXT/SRT/burned captions are dense, title-safe, and viewer-facing.",
        "forbiddenWorkaround": "Do not show QA, version, Resolve, export, repair, SRT/TXT, or delivery-status language to viewers.",
    },
    {
        "reportId": "bgm_musicality_contract_audit",
        "path": "bgm_musicality_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "caption_audio",
        "viewerSymptom": "The film has hum, tone, silence, one-band placeholder audio, or weak scenic music instead of usable BGM.",
        "ownerScript": "prepare_bgm_selection_package.py",
        "requiredArtifact": "bgm_selection_package/bgm_selection_package.json",
        "command": "python3 <skill-dir>/scripts/prepare_bgm_selection_package.py --package-dir <package> --json",
        "acceptanceEvidence": "BGM selection, phrase blueprint, BGM/audio, and musicality audits prove audible musical BGM with no scenic voice leakage.",
        "forbiddenWorkaround": "Do not pass with sine pads, hum tones, silence, camera audio, generated voiceover, or untraceable music.",
    },
    {
        "reportId": "bgm_audio_contract_audit",
        "path": "bgm_audio_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "caption_audio",
        "viewerSymptom": "Scenic/title/transition sections leak source-camera or voiceover audio instead of BGM-only travel-film sound.",
        "ownerScript": "prepare_audio_scene_policy_plan.py",
        "requiredArtifact": "audio_scene_policy_plan/audio_scene_policy_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_audio_scene_policy_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Audio-scene policy, BGM/audio contract, and Resolve readback prove A3 BGM-only scenic/title/transition sections.",
        "forbiddenWorkaround": "Do not leave camera/user voice under scenic openings, title bridges, transition bridges, or aerial/landmark sequences.",
    },
    {
        "reportId": "raw_intake_completeness_audit",
        "path": "raw_intake_completeness_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "source_route",
        "viewerSymptom": "The edit may be a sampled-folder or filename-order montage rather than a full 100GB-source travel film.",
        "ownerScript": "prepare_footage_recognition_report.py",
        "requiredArtifact": "recognition_reports/latest_footage_recognition_route_report.json",
        "command": "python3 <skill-dir>/scripts/prepare_footage_recognition_report.py --project-dir <project-dir> --json",
        "acceptanceEvidence": "Raw intake proves every active source video is indexed, recognized, routed exactly once, non-derived, and fresh.",
        "forbiddenWorkaround": "Do not cut from a sample folder, derived export, stale media index, or filename order.",
    },
    {
        "reportId": "large_source_unattended_readiness_contract_audit",
        "path": "large_source_unattended_readiness_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P0",
        "phase": "source_route",
        "viewerSymptom": "A large unordered folder cannot yet reach a safe first draft without manual rescue.",
        "ownerScript": "audit_large_source_unattended_readiness_contract.py",
        "requiredArtifact": "large_source_unattended_readiness_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_large_source_unattended_readiness_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Large-source readiness proves intake, recognition, source selection, first assembly, preflight, and unattended draft gates are connected.",
        "forbiddenWorkaround": "Do not hand off a 100GB unordered folder until the chain is connected end to end.",
    },
    {
        "reportId": "creator_cut_application_contract_audit",
        "path": "creator_cut_application_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "creator_cut",
        "viewerSymptom": "The viewer sees weak, redundant, utility, or reject footage because the final candidate did not apply creator-level shot choices.",
        "ownerScript": "prepare_creator_cut_plan.py",
        "requiredArtifact": "creator_cut_plan/creator_cut_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_creator_cut_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Creator-cut and final-source-usage audits prove active shots are selected hero/main/texture choices in a readable order.",
        "forbiddenWorkaround": "Do not let transitions, stock, titles, or speed effects rescue weak footage; demote, replace, or reorder weak shots first.",
    },
    {
        "reportId": "pacing_watchability_contract_audit",
        "path": "pacing_watchability_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "creator_cut",
        "viewerSymptom": "The cut feels AI-made because long holds, flickery short runs, or repetitive shot roles were not repaired.",
        "ownerScript": "prepare_edit_rhythm_plan.py",
        "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Pacing watchability, rhythm recut, and timeline-variety audits pass with reference-calibrated shot lengths and chapter breath.",
        "forbiddenWorkaround": "Do not add effects over flat pacing or leave long raw holds untouched.",
    },
    {
        "reportId": "chapter_story_spine_contract_audit",
        "path": "chapter_story_spine_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "story_spine",
        "viewerSymptom": "Chapters feel like landmark stacks instead of travel sequences with context, movement, texture, payoff, and aftertaste.",
        "ownerScript": "prepare_chapter_arc_plan.py",
        "requiredArtifact": "chapter_arc_plan/chapter_arc_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Chapter story spine, shot-flow, scene-flow, and narrative-adjacency audits pass for every chapter.",
        "forbiddenWorkaround": "Do not hide missing story beats behind title cards, stock inserts, or transition effects.",
    },
    {
        "reportId": "transition_flow_repair_plan",
        "path": "transition_flow_repair_plan/transition_flow_repair_plan.json",
        "accepted": {"ready_no_transition_flow_repairs_needed"},
        "priority": "P0",
        "phase": "transition_flow",
        "viewerSymptom": "Adjacent shots still feel rough, random, hard-cut, route-confusing, or effect-hidden.",
        "ownerScript": "prepare_transition_flow_repair_plan.py",
        "requiredArtifact": "transition_flow_repair_plan/transition_flow_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_flow_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Transition-flow repair plan returns ready_no_transition_flow_repairs_needed after all owner-script repairs and transition audits pass.",
        "forbiddenWorkaround": "Do not patch isolated transition failures with random rotation, whip, flash, or stronger template effects.",
    },
    {
        "reportId": "transition_watch_reel_review_contract_audit",
        "path": "transition_watch_reel_review_contract_audit.json",
        "accepted": {"passed", "passed_no_important_transitions"},
        "priority": "P0",
        "phase": "transition_flow",
        "viewerSymptom": "Important transitions were never reviewed as one ordered sequence, or the reel repeats high-intensity/template motion.",
        "ownerScript": "audit_transition_watch_reel_review_contract.py",
        "requiredArtifact": "transition_watch_reel_review_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_transition_watch_reel_review_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "The ordered muted transition watch reel passes timing, local media, family-variety, and high-intensity restraint checks.",
        "forbiddenWorkaround": "Do not approve transition flow from scattered clips, JSON rows, screenshots, or a reel with effect spam.",
    },
    {
        "reportId": "transition_reference_readiness_contract_audit",
        "path": "transition_reference_readiness_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "transition_flow",
        "viewerSymptom": "Transition subreports pass in isolation, but the whole transition chain is not yet reference-ready.",
        "ownerScript": "audit_transition_reference_readiness_contract.py",
        "requiredArtifact": "transition_reference_readiness_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/audit_transition_reference_readiness_contract.py --package-dir <package> --json",
        "acceptanceEvidence": "Transition reference-readiness aggregation passes with zero readiness rows and zero metric issues.",
        "forbiddenWorkaround": "Do not claim Parallel World/Malta-level transition quality from scattered local checks without the aggregate readiness gate.",
    },
    {
        "reportId": "rendered_transition_proof_contract_audit",
        "path": "rendered_transition_proof_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "transition_flow",
        "viewerSymptom": "The final render may contain black/white flashes, raw vertical frames, or unstable landing frames at transitions.",
        "ownerScript": "prepare_transition_audition_packet.py",
        "requiredArtifact": "transition_audition_packet/transition_audition_packet.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_audition_packet.py --package-dir <package> --build-clips --json",
        "acceptanceEvidence": "Rendered transition proof passes against the current final MP4 with no flash, raw pillarbox, or unstable landing blockers.",
        "forbiddenWorkaround": "Do not treat a transition as fixed until both preview/audition evidence and rendered-frame proof are clean.",
    },
    {
        "reportId": "resolve_transition_apply_contract_audit",
        "path": "resolve_transition_apply_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "transition_flow",
        "viewerSymptom": "Visible transitions are only marker metadata or pending manual instructions, not actually applied in Resolve/readback.",
        "ownerScript": "prepare_resolve_transition_apply_plan.py",
        "requiredArtifact": "resolve_transition_apply_plan/resolve_transition_apply_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_resolve_transition_apply_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Resolve transition apply audit proves each visible transition is API-supported, a materialized bridge clip, or completed readback/frame evidence.",
        "forbiddenWorkaround": "Do not treat marker customData, planned manual effects, or Fusion notes as unattended-applied transitions.",
    },
    {
        "reportId": "transition_motion_accent_repair_plan",
        "path": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "accepted": {"ready_no_motion_accent_repairs_needed"},
        "priority": "P0",
        "phase": "transition_flow",
        "viewerSymptom": "Whip, rotation, push, zoom, or speed-ramp accents are random, overused, title-unsafe, or missing stable landings.",
        "ownerScript": "prepare_transition_motion_accent_repair_plan.py",
        "requiredArtifact": "transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_motion_accent_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Motion-accent repair plan is closed and motion-accent audit proves rare, motivated, direction-matched, readable accents.",
        "forbiddenWorkaround": "Do not use stronger motion to hide weak adjacent footage, missing bridge clips, or unclear route jumps.",
    },
    {
        "reportId": "reference_profile_application_contract_audit",
        "path": "reference_profile_application_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "reference_style",
        "viewerSymptom": "The four reference videos or Malta final were analyzed but not actually applied to opening, rhythm, transitions, captions, audio, and ending.",
        "ownerScript": "prepare_reference_style_repair_plan.py",
        "requiredArtifact": "reference_style_repair_plan/reference_style_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Reference-profile application and reference-repair closure prove learned style targets became concrete package artifacts.",
        "forbiddenWorkaround": "Do not claim reference fit from vague adjectives, unused analysis files, copied assets, or sampled-frame impressions.",
    },
    {
        "reportId": "reference_transition_profile_contract_audit",
        "path": "reference_transition_profile_contract_audit.json",
        "accepted": {"passed"},
        "priority": "P0",
        "phase": "reference_style",
        "viewerSymptom": "Transitions do not match the learned non-copying bridge, breath, match, and restrained-motion balance.",
        "ownerScript": "prepare_transition_reference_candidates.py",
        "requiredArtifact": "transition_reference_candidates/transition_reference_candidates.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_reference_candidates.py --package-dir <package> --json",
        "acceptanceEvidence": "Reference-transition profile, candidates, selection, motif, and watch-reel review all pass.",
        "forbiddenWorkaround": "Do not leave A/B/C choices unresolved or select a random visible effect to imitate reference quality.",
    },
    {
        "reportId": "route_texture_contract_audit",
        "path": "route_texture_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "priority": "P1",
        "phase": "reference_style",
        "viewerSymptom": "The travel film lacks lived-in route texture: movement, street life, transport, food, waiting, weather, or local detail.",
        "ownerScript": "prepare_visual_establishing_plan.py",
        "requiredArtifact": "visual_establishing_plan/visual_establishing_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_visual_establishing_plan.py --package-dir <package> --json",
        "acceptanceEvidence": "Route texture and visual-establishing audits prove real bridge/texture footage or closed stock/aerial decisions.",
        "forbiddenWorkaround": "Do not build a landmark-only montage and hide missing lived-in detail with title cards or effects.",
    },
    {
        "reportId": "editorial_watchdown_repair_plan",
        "path": "editorial_watchdown_repair_plan/editorial_watchdown_repair_plan.json",
        "accepted": {"ready_no_editorial_watchdown_repairs_needed"},
        "priority": "P0",
        "phase": "final_watchdown",
        "viewerSymptom": "The current final MP4 has not been watched and signed off as a whole viewer-facing film.",
        "ownerScript": "prepare_editorial_watchdown_repair_plan.py",
        "requiredArtifact": "editorial_watchdown_repair_plan/editorial_watchdown_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_editorial_watchdown_repair_plan.py --package-dir <package> --final-output <final-mp4> --json",
        "acceptanceEvidence": "Editorial watchdown closes current-output rows for opening, chapters, transitions, BGM/captions, ending, and reference fit.",
        "forbiddenWorkaround": "Do not hand off from technical QA, sampled frames, screenshots, or stale V1/V2/V14 watch notes alone.",
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


def row_from_spec(package_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = package_dir / spec["path"]
    data = load_json(path) or {}
    status = data.get("status") if isinstance(data, dict) else None
    blockers = data.get("blockers") if isinstance(data, dict) and isinstance(data.get("blockers"), list) else []
    warnings = data.get("warnings") if isinstance(data, dict) and isinstance(data.get("warnings"), list) else []
    accepted = set(spec["accepted"])
    passed = bool(path.exists() and status in accepted and not blockers)
    issue = ""
    if not path.exists():
        issue = f"{spec['reportId']} is missing"
    elif status not in accepted:
        issue = f"{spec['reportId']} status is {status!r}; expected one of {sorted(accepted)}"
    elif blockers:
        issue = f"{spec['reportId']} still has blockers"
    return {
        "repairId": f"final_viewer_friction_{spec['reportId']}",
        "reportId": spec["reportId"],
        "sourceReport": "final_viewer_friction_contract_audit",
        "sourceReportPath": str(path),
        "reportExists": path.exists(),
        "reportStatus": status,
        "acceptedStatuses": sorted(accepted),
        "passed": passed,
        "priority": spec["priority"],
        "phase": spec["phase"],
        "viewerSymptom": spec["viewerSymptom"],
        "issue": issue,
        "ownerScript": spec["ownerScript"],
        "requiredArtifact": spec["requiredArtifact"],
        "command": spec["command"],
        "acceptanceEvidence": spec["acceptanceEvidence"],
        "forbiddenWorkaround": spec["forbiddenWorkaround"],
        "summary": summary(data),
        "blockers": [clean(item) for item in blockers[:12]],
        "warnings": [clean(item) for item in warnings[:12]],
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    evidence_rows = [row_from_spec(package_dir, spec) for spec in REPORT_SPECS]
    friction_rows = [row for row in evidence_rows if not row["passed"]]
    p0_rows = [row for row in friction_rows if row.get("priority") == "P0"]
    p1_rows = [row for row in friction_rows if row.get("priority") == "P1"]
    phase_counts: dict[str, int] = {}
    for row in friction_rows:
        phase_counts[row["phase"]] = phase_counts.get(row["phase"], 0) + 1
    summary_payload = {
        "evidenceReportCount": len(evidence_rows),
        "passedEvidenceReportCount": len([row for row in evidence_rows if row["passed"]]),
        "viewerFrictionRowCount": len(friction_rows),
        "p0ViewerFrictionRowCount": len(p0_rows),
        "p1ViewerFrictionRowCount": len(p1_rows),
        "phaseCounts": phase_counts,
        "ownerScripts": sorted({row["ownerScript"] for row in friction_rows}),
    }
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": PASSED if not friction_rows else BLOCKED,
        "packageDir": str(package_dir),
        "summary": summary_payload,
        "evidenceRows": evidence_rows,
        "viewerFrictionRows": friction_rows,
        "repairRows": friction_rows,
        "policy": {
            "aggregateViewerFacingFailures": True,
            "blockTechnicalPassWithoutViewerContracts": True,
            "routeEveryOpenViewerIssueToOwnerScript": True,
            "noResolveWrites": True,
        },
        "nextActions": [
            "Run each owner script for P0 rows before another Resolve render or handoff.",
            "Rerun the named source report after each repair, then rerun this contract.",
            "Only pass final QA when this contract has zero viewer-friction rows.",
        ],
        "safety": safety(),
    }
    if args.max_rows and len(report["viewerFrictionRows"]) > args.max_rows:
        report["viewerFrictionRows"] = report["viewerFrictionRows"][: args.max_rows]
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Final Viewer Friction Contract",
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
        "## Viewer Friction Rows",
    ]
    if not report.get("viewerFrictionRows"):
        lines.append("- None.")
    for row in report.get("viewerFrictionRows", [])[:200]:
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
    lines.extend(
        [
            "",
            "## Contract",
            "- This is an aggregation gate, not a replacement for full-film watching.",
            "- Every open row must have an owner script and acceptance evidence before another handoff claim.",
            "- The gate is read-only: no Resolve writes, no render queue, no downloads, no source-drive mutation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final viewer-facing friction and route repairs.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    output_json = package_dir / "final_viewer_friction_contract_audit.json"
    output_md = package_dir / "final_viewer_friction_contract_audit.md"
    write_json(output_json, report)
    write_markdown(output_md, report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": [row["repairId"] for row in report["viewerFrictionRows"]]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
