#!/usr/bin/env python3
"""Run the final Travel Video Studio QA gates in one reproducible suite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ACCEPTED_STATUSES = {
    "render_delivery_verification": {"passed"},
    "visual_audio_style_audit": {"passed"},
    "bgm_audio_contract_audit": {"passed", "passed_with_warnings"},
    "bgm_musicality_contract_audit": {"passed"},
    "location_truth_contract_audit": {"passed", "passed_with_caveats", "passed_with_warnings"},
    "client_delivery_rules_audit": {"passed", "passed_with_warnings"},
    "longform_delivery_audit": {"passed", "passed_with_caveats", "passed_with_warnings"},
    "story_style_contract_audit": {"passed"},
    "audience_caption_contract_audit": {"passed"},
    "title_bridge_contract_audit": {"passed", "passed_with_warnings"},
    "cover_title_contract_audit": {"passed"},
    "title_visual_proof_contract_audit": {"passed"},
    "title_typography_repair_plan": {"ready_no_title_typography_repairs_needed"},
    "reference_style_alignment_audit": {"passed"},
    "director_intent_contract_audit": {"passed", "passed_with_warnings"},
    "route_texture_contract_audit": {"passed", "passed_with_warnings"},
    "stock_aerial_closure_audit": {"passed", "passed_with_warnings"},
    "director_polish_contract_audit": {"passed", "passed_with_warnings"},
    "feedback_regression_audit": {"passed", "passed_with_warnings"},
    "editorial_watchdown_repair_plan": {"ready_no_editorial_watchdown_repairs_needed"},
    "final_viewer_friction_contract_audit": {"passed"},
    "package_integrity_audit": {"passed"},
    "package_integrity_audit_strict_portable": {"passed"},
    "transition_pair_continuity_contract_audit": {"passed"},
    "transition_execution_readiness_contract_audit": {"passed"},
    "transition_polish_application_contract_audit": {"passed"},
    "resolve_transition_materialization_contract_audit": {"passed"},
    "resolve_transition_apply_contract_audit": {"passed"},
    "bridge_sequence_application_contract_audit": {"passed"},
    "transition_bridge_visual_evidence_contract_audit": {"passed"},
    "source_selection_coverage_contract_audit": {"passed"},
    "first_assembly_source_order_contract_audit": {"passed"},
    "large_source_unattended_readiness_contract_audit": {"passed", "passed_with_warnings"},
    "final_blueprint_lineage_contract_audit": {"passed"},
    "effect_motion_application_contract_audit": {"passed"},
    "transition_cadence_contract_audit": {"passed"},
    "transition_microstructure_contract_audit": {"passed"},
    "transition_cutpoint_contract_audit": {"passed"},
    "transition_action_anchor_contract_audit": {"passed"},
    "transition_sensory_continuity_contract_audit": {"passed"},
    "final_source_usage_contract_audit": {"passed"},
    "creator_cut_application_contract_audit": {"passed"},
    "rhythm_recut_application_contract_audit": {"passed"},
    "reference_scene_grammar_contract_audit": {"passed"},
    "reference_review_repair_plan": {"ready_no_reference_review_repairs_needed"},
    "reference_profile_application_contract_audit": {"passed"},
    "timeline_variety_contract_audit": {"passed"},
    "transition_scene_arc_contract_audit": {"passed"},
    "transition_effect_palette_contract_audit": {"passed"},
    "transition_motif_coherence_contract_audit": {"passed"},
    "transition_visual_match_contract_audit": {"passed"},
    "transition_source_coverage_contract_audit": {"passed"},
    "transition_reference_candidates": {"ready_with_transition_reference_candidates"},
    "transition_reference_selection": {"ready_with_transition_reference_selection"},
    "transition_choreography_plan": {"ready_with_transition_choreography_plan"},
    "transition_choreography_contract_audit": {"passed"},
    "transition_motion_direction_contract_audit": {"passed"},
    "transition_motion_accent_contract_audit": {"passed"},
    "transition_motion_accent_repair_plan": {"ready_no_motion_accent_repairs_needed"},
    "transition_effect_recipe_contract_audit": {"passed"},
    "rendered_transition_proof_contract_audit": {"passed"},
    "transition_preview_packet": {"ready_with_transition_preview_packet", "ready_no_important_transitions"},
    "transition_preview_quality_contract_audit": {"passed"},
    "transition_audition_packet": {"ready_with_transition_audition_packet", "ready_no_important_transitions"},
    "transition_audition_quality_contract_audit": {"passed"},
    "transition_watch_reel": {"ready_with_transition_watch_reel", "ready_no_important_transitions"},
    "transition_watch_reel_review_contract_audit": {"passed", "passed_no_important_transitions"},
    "transition_audition_visual_proof_contract_audit": {"passed"},
    "transition_audition_role_integrity_contract_audit": {"passed"},
    "transition_storyboard_contract_audit": {"passed"},
    "reference_transition_profile_contract_audit": {"passed"},
    "chapter_story_spine_contract_audit": {"passed"},
    "shot_flow_continuity_contract_audit": {"passed"},
    "transition_breathing_room_contract_audit": {"passed"},
    "scene_flow_arc_contract_audit": {"passed"},
    "final_cut_smoothness_contract_audit": {"passed"},
    "transition_continuity_rehearsal_contract_audit": {"passed"},
    "pacing_watchability_contract_audit": {"passed"},
    "narrative_adjacency_contract_audit": {"passed"},
    "transition_viewer_orientation_contract_audit": {"passed"},
    "transition_scene_settlement_contract_audit": {"passed"},
    "transition_flow_repair_plan": {"ready_no_transition_flow_repairs_needed"},
    "transition_reference_readiness_contract_audit": {"passed"},
    "unattended_repair_queue": {"ready_no_unattended_repairs_needed"},
    "unattended_first_draft_contract_audit": {"passed", "passed_with_warnings"},
    "skill_maturity_contract_audit": {"passed", "passed_with_warnings"},
    "v14_baseline_contract_audit": {"passed"},
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


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def infer_output(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for report_name in ("render_delivery_verification.json", "FINAL_DELIVERY_REPORT.json"):
        report = load_json(package_dir / report_name) or {}
        candidate = report.get("output") or report.get("finalOutput")
        if candidate:
            path = Path(str(candidate)).expanduser()
            if path.exists():
                return path.resolve()
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    return renders[0].resolve() if renders else None


def infer_visual_manifest(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidates = [
        package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json",
        package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
        package_dir / "v9_fix_inputs" / "v9_fix_manifest.json",
        package_dir / "v12_visual_manifest.json",
    ]
    return next((path.resolve() for path in candidates if path.exists()), None)


def infer_bgm_manifest(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    for key in ("bgmManifest", "bgm_manifest"):
        if assets.get(key):
            path = Path(str(assets[key])).expanduser()
            if path.exists():
                return path.resolve()
    cues = (blueprint.get("audioPlan") or {}).get("bgmCues") or []
    for cue in cues:
        if isinstance(cue, dict) and cue.get("manifest"):
            path = Path(str(cue["manifest"])).expanduser()
            if path.exists():
                return path.resolve()
    candidates = sorted((package_dir / "bgm").glob("*manifest*.json"))
    return candidates[-1].resolve() if candidates else None


def manifest_sample_seconds(path: Path | None) -> list[float]:
    data = load_json(path) or {}
    out: list[float] = [0.0, 2.0, 7.5]
    for item in data.get("segments") or []:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "").lower()
        if mode not in {"opening", "chapter", "ending", "transition"}:
            continue
        try:
            start = float(item.get("timeline_start", item.get("timelineStartSeconds")))
            duration = float(item.get("duration", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        out.append(max(0.0, start))
        if duration > 0:
            out.append(max(0.0, start + min(2.0, duration / 2.0)))
    unique: list[float] = []
    seen: set[int] = set()
    for second in out:
        key = round(second * 1000)
        if key in seen:
            continue
        seen.add(key)
        unique.append(round(second, 3))
    return unique


def run_command(name: str, cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return {
        "name": name,
        "command": cmd,
        "returnCode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def report_status(path: Path) -> str | None:
    data = load_json(path) or {}
    return data.get("status") if isinstance(data, dict) else None


def stage_report_path(package_dir: Path, stage: str, *, strict: bool = False) -> Path:
    if stage == "visual_audio_style_audit":
        return package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json"
    if stage == "feedback_regression_audit":
        return package_dir / "feedback_regression_audit" / "feedback_regression_audit.json"
    if stage == "package_integrity_audit_strict_portable":
        return package_dir / "package_integrity_audit_strict_portable.json"
    if stage == "transition_preview_packet":
        return package_dir / "transition_preview_packet" / "transition_preview_packet.json"
    if stage == "transition_choreography_plan":
        return package_dir / "transition_choreography_plan" / "transition_choreography_plan.json"
    if stage == "transition_reference_candidates":
        return package_dir / "transition_reference_candidates" / "transition_reference_candidates.json"
    if stage == "transition_reference_selection":
        return package_dir / "transition_reference_selection" / "transition_reference_selection.json"
    if stage == "title_typography_repair_plan":
        return package_dir / "title_typography_repair_plan" / "title_typography_repair_plan.json"
    if stage == "transition_audition_packet":
        return package_dir / "transition_audition_packet" / "transition_audition_packet.json"
    if stage == "transition_watch_reel":
        return package_dir / "transition_watch_reel" / "transition_watch_reel.json"
    if stage == "transition_motion_accent_repair_plan":
        return package_dir / "transition_motion_accent_repair_plan" / "transition_motion_accent_repair_plan.json"
    if stage == "transition_flow_repair_plan":
        return package_dir / "transition_flow_repair_plan" / "transition_flow_repair_plan.json"
    if stage == "editorial_watchdown_repair_plan":
        return package_dir / "editorial_watchdown_repair_plan" / "editorial_watchdown_repair_plan.json"
    if stage == "unattended_repair_queue":
        return package_dir / "unattended_repair_queue" / "unattended_repair_queue.json"
    return package_dir / f"{stage}.json"


def evaluate_stage(package_dir: Path, stage: str, command_result: dict[str, Any] | None = None) -> dict[str, Any]:
    path = stage_report_path(package_dir, stage)
    status = report_status(path)
    accepted = ACCEPTED_STATUSES.get(stage, {"passed"})
    ok = status in accepted
    command_ok = command_result is None or command_result.get("returnCode") == 0
    return {
        "stage": stage,
        "status": status,
        "acceptedStatuses": sorted(accepted),
        "report": str(path),
        "reportExists": path.exists(),
        "commandReturnCode": command_result.get("returnCode") if command_result else None,
        "passed": bool(ok and command_ok and path.exists()),
        "command": command_result.get("command") if command_result else None,
    }


def copy_package_integrity_strict(package_dir: Path) -> None:
    src_json = package_dir / "package_integrity_audit.json"
    src_md = package_dir / "package_integrity_audit.md"
    if src_json.exists():
        (package_dir / "package_integrity_audit_strict_portable.json").write_bytes(src_json.read_bytes())
    if src_md.exists():
        (package_dir / "package_integrity_audit_strict_portable.md").write_bytes(src_md.read_bytes())


def build_suite(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    scripts = script_dir()
    output = infer_output(package_dir, args.output)
    visual_manifest = infer_visual_manifest(package_dir, args.visual_manifest)
    bgm_manifest = infer_bgm_manifest(package_dir, args.bgm_manifest)
    commands: list[tuple[str, list[str], bool]] = []

    render_status = report_status(package_dir / "render_delivery_verification.json")
    if args.rerun_render_verification or render_status not in ACCEPTED_STATUSES["render_delivery_verification"]:
        if not output:
            raise FileNotFoundError("Final output MP4 could not be inferred for render verification.")
        commands.append(
            (
                "render_delivery_verification",
                [
                    sys.executable,
                    str(scripts / "verify_render_delivery.py"),
                    "--package-dir",
                    str(package_dir),
                    "--output",
                    str(output),
                    "--min-fps",
                    str(args.min_fps),
                    "--min-video-bitrate-mbps",
                    str(args.min_video_bitrate_mbps),
                    "--expect-subtitles",
                    args.expect_subtitles,
                ]
                + (["--skip-blackdetect"] if args.skip_blackdetect else []),
                False,
            )
        )

    visual_status = report_status(package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json")
    if args.rerun_visual_audio or visual_status not in ACCEPTED_STATUSES["visual_audio_style_audit"]:
        if not output:
            raise FileNotFoundError("Final output MP4 could not be inferred for visual/audio audit.")
        sample_seconds = args.sample_seconds or ",".join(str(x) for x in manifest_sample_seconds(visual_manifest))
        cmd = [
            sys.executable,
            str(scripts / "audit_visual_audio_style.py"),
            "--video",
            str(output),
            "--output-dir",
            str(package_dir / "visual_audio_style_audit"),
            "--sample-seconds",
            sample_seconds,
            "--audio-mode",
            args.audio_mode,
            "--require-clean-title",
        ]
        if visual_manifest:
            cmd += ["--visual-manifest", str(visual_manifest)]
        if bgm_manifest:
            cmd += ["--bgm-manifest", str(bgm_manifest)]
        commands.append(("visual_audio_style_audit", cmd, False))

    commands.extend(
        [
            (
                "bgm_audio_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_bgm_audio_contract.py"),
                    "--package-dir",
                    str(package_dir),
                    "--audio-mode",
                    args.audio_mode,
                ],
                False,
            ),
            (
                "bgm_musicality_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_bgm_musicality_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "client_delivery_rules_audit",
                [
                    sys.executable,
                    str(scripts / "audit_client_delivery_rules.py"),
                    "--package-dir",
                    str(package_dir),
                    "--min-fps",
                    str(args.min_fps),
                    "--min-video-bitrate-mbps",
                    str(args.min_video_bitrate_mbps),
                ],
                False,
            ),
            (
                "location_truth_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_location_truth_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "longform_delivery_audit",
                [
                    sys.executable,
                    str(scripts / "audit_longform_delivery.py"),
                    "--package-dir",
                    str(package_dir),
                    "--min-fps",
                    str(args.min_fps),
                    "--min-video-bitrate-mbps",
                    str(args.min_video_bitrate_mbps),
                ],
                False,
            ),
            (
                "audience_caption_contract_audit",
                [sys.executable, str(scripts / "audit_audience_caption_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "story_style_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_story_style_contract.py"),
                    "--package-dir",
                    str(package_dir),
                    "--audio-mode",
                    args.audio_mode,
                    "--require-rendered-subtitles",
                ],
                False,
            ),
            (
                "reference_style_alignment_audit",
                [sys.executable, str(scripts / "audit_reference_style_alignment.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "director_intent_contract_audit",
                [sys.executable, str(scripts / "audit_director_intent_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "route_texture_contract_audit",
                [sys.executable, str(scripts / "audit_route_texture_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "title_bridge_contract_audit",
                [sys.executable, str(scripts / "audit_title_bridge_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "cover_title_contract_audit",
                [sys.executable, str(scripts / "audit_cover_title_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "title_visual_proof_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_title_visual_proof_contract.py"),
                    "--package-dir",
                    str(package_dir),
                    "--extract-frames",
                ],
                False,
            ),
            (
                "title_typography_repair_plan",
                [
                    sys.executable,
                    str(scripts / "prepare_title_typography_repair_plan.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "stock_aerial_closure_audit",
                [sys.executable, str(scripts / "audit_stock_aerial_closure.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "director_polish_contract_audit",
                [sys.executable, str(scripts / "audit_director_polish_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "feedback_regression_audit",
                [
                    sys.executable,
                    str(scripts / "audit_feedback_regressions.py"),
                    "--package-dir",
                    str(package_dir),
                    "--feedback-timestamps",
                    args.feedback_timestamps,
                    "--include-title-points",
                ],
                False,
            ),
            (
                "package_integrity_audit_strict_portable",
                [
                    sys.executable,
                    str(scripts / "audit_package_integrity.py"),
                    "--package-dir",
                    str(package_dir),
                    "--strict-portable",
                ],
                True,
            ),
            (
                "package_integrity_audit",
                [sys.executable, str(scripts / "audit_package_integrity.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "transition_pair_continuity_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_pair_continuity_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_execution_readiness_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_execution_readiness_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_polish_application_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_polish_application_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "resolve_transition_materialization_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_resolve_transition_materialization_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "resolve_transition_apply_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_resolve_transition_apply_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "bridge_sequence_application_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_bridge_sequence_application_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_bridge_visual_evidence_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_bridge_visual_evidence_contract.py"),
                    "--package-dir",
                    str(package_dir),
                    "--extract-frames",
                ],
                False,
            ),
            (
                "source_selection_coverage_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_source_selection_coverage_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "first_assembly_source_order_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_first_assembly_source_order_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "large_source_unattended_readiness_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_large_source_unattended_readiness_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "final_blueprint_lineage_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_final_blueprint_lineage_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "effect_motion_application_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_effect_motion_application_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_cadence_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_cadence_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_microstructure_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_microstructure_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_cutpoint_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_cutpoint_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_action_anchor_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_action_anchor_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_sensory_continuity_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_sensory_continuity_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "final_source_usage_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_final_source_usage_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "creator_cut_application_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_creator_cut_application_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "rhythm_recut_application_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_rhythm_recut_application_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "reference_scene_grammar_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_reference_scene_grammar_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "reference_review_repair_plan",
                [
                    sys.executable,
                    str(scripts / "prepare_reference_review_repair_plan.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "reference_profile_application_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_reference_profile_application_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "timeline_variety_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_timeline_variety_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_scene_arc_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_scene_arc_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_effect_palette_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_effect_palette_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_visual_match_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_visual_match_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_source_coverage_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_source_coverage_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_reference_candidates",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_reference_candidates.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_reference_selection",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_reference_selection.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_motif_coherence_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_motif_coherence_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_choreography_plan",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_choreography_plan.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_choreography_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_choreography_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_motion_direction_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_motion_direction_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_preview_packet",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_preview_packet.py"),
                    "--package-dir",
                    str(package_dir),
                    "--extract-frames",
                    "--update-transition-grammar",
                ],
                False,
            ),
            (
                "transition_preview_quality_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_preview_quality_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_audition_packet",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_audition_packet.py"),
                    "--package-dir",
                    str(package_dir),
                    "--build-clips",
                ],
                False,
            ),
            (
                "transition_audition_quality_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_audition_quality_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_watch_reel",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_watch_reel.py"),
                    "--package-dir",
                    str(package_dir),
                    "--build-reel",
                ],
                False,
            ),
            (
                "transition_watch_reel_review_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_watch_reel_review_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_audition_visual_proof_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_audition_visual_proof_contract.py"),
                    "--package-dir",
                    str(package_dir),
                    "--extract-frames",
                ],
                False,
            ),
            (
                "transition_audition_role_integrity_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_audition_role_integrity_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_motion_accent_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_motion_accent_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_motion_accent_repair_plan",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_motion_accent_repair_plan.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_effect_recipe_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_effect_recipe_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "rendered_transition_proof_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_rendered_transition_proof_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ]
                + (["--output", str(output)] if output else []),
                False,
            ),
            (
                "transition_storyboard_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_storyboard_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "reference_transition_profile_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_reference_transition_profile_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "chapter_story_spine_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_chapter_story_spine_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "shot_flow_continuity_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_shot_flow_continuity_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_breathing_room_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_breathing_room_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "scene_flow_arc_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_scene_flow_arc_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "final_cut_smoothness_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_final_cut_smoothness_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_continuity_rehearsal_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_continuity_rehearsal_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "pacing_watchability_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_pacing_watchability_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "narrative_adjacency_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_narrative_adjacency_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_viewer_orientation_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_viewer_orientation_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_scene_settlement_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_scene_settlement_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_flow_repair_plan",
                [
                    sys.executable,
                    str(scripts / "prepare_transition_flow_repair_plan.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "transition_reference_readiness_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_transition_reference_readiness_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "editorial_watchdown_repair_plan",
                [
                    sys.executable,
                    str(scripts / "prepare_editorial_watchdown_repair_plan.py"),
                    "--package-dir",
                    str(package_dir),
                ]
                + (["--final-output", str(output)] if output else []),
                False,
            ),
            (
                "final_viewer_friction_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_final_viewer_friction_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "unattended_repair_queue",
                [
                    sys.executable,
                    str(scripts / "prepare_unattended_repair_queue.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "unattended_first_draft_contract_audit",
                [
                    sys.executable,
                    str(scripts / "audit_unattended_first_draft_contract.py"),
                    "--package-dir",
                    str(package_dir),
                ],
                False,
            ),
            (
                "skill_maturity_contract_audit",
                [sys.executable, str(scripts / "audit_skill_maturity_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
            (
                "v14_baseline_contract_audit",
                [sys.executable, str(scripts / "audit_v14_baseline_contract.py"), "--package-dir", str(package_dir)],
                False,
            ),
        ]
    )

    command_results: dict[str, dict[str, Any]] = {}
    stages: list[dict[str, Any]] = []
    failed_command = False
    for stage, cmd, copy_strict in commands:
        result = run_command(stage, cmd)
        command_results[stage] = result
        if copy_strict:
            copy_package_integrity_strict(package_dir)
        stage_eval = evaluate_stage(package_dir, stage, result)
        stages.append(stage_eval)
        if result["returnCode"] != 0 and not stage_eval["passed"]:
            failed_command = True
            if args.stop_on_failure:
                break

    # Evaluate reports that may have been reused rather than rerun.
    for stage in ACCEPTED_STATUSES:
        if any(row["stage"] == stage for row in stages):
            continue
        stages.append(evaluate_stage(package_dir, stage))

    blockers = [row for row in stages if not row["passed"]]
    status = "blocked" if blockers or failed_command else "passed"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "finalOutput": str(output) if output else None,
        "visualManifest": str(visual_manifest) if visual_manifest else None,
        "bgmManifest": str(bgm_manifest) if bgm_manifest else None,
        "feedbackTimestamps": args.feedback_timestamps,
        "rerunRenderVerification": args.rerun_render_verification,
        "rerunVisualAudio": args.rerun_visual_audio,
        "stages": sorted(stages, key=lambda row: row["stage"]),
        "blockers": [row["stage"] for row in blockers],
        "commandResults": command_results,
        "summary": {
            "passedStages": len([row for row in stages if row["passed"]]),
            "blockedStages": len(blockers),
            "totalStages": len(stages),
        },
    }
    write_json(package_dir / "final_qa_suite_report.json", report)
    write_markdown(package_dir / "final_qa_suite_report.md", report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Final QA Suite Report",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Final output: `{report.get('finalOutput')}`",
        f"Passed stages: `{report['summary']['passedStages']}/{report['summary']['totalStages']}`",
        "",
        "## Stages",
    ]
    for row in report["stages"]:
        lines.append(
            f"- `{row['stage']}`: status=`{row.get('status')}`, passed=`{row['passed']}`, report=`{row['report']}`"
        )
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final QA gates for a Travel Video Studio delivery package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--visual-manifest")
    parser.add_argument("--bgm-manifest")
    parser.add_argument("--feedback-timestamps", default="opening_title=0")
    parser.add_argument("--sample-seconds")
    parser.add_argument("--audio-mode", choices=["bgm_only", "preserve_source"], default="bgm_only")
    parser.add_argument("--min-fps", type=float, default=50.0)
    parser.add_argument("--min-video-bitrate-mbps", type=float, default=60.0)
    parser.add_argument("--expect-subtitles", choices=["none", "any", "sidecar", "embedded", "burned-in"], default="burned-in")
    parser.add_argument("--rerun-render-verification", action="store_true")
    parser.add_argument("--rerun-visual-audio", action="store_true")
    parser.add_argument("--skip-blackdetect", action="store_true")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = build_suite(args)
    except Exception as exc:
        print(f"run_final_qa_suite failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
