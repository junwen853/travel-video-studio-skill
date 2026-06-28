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
    "feedback_plan": "prepare_feedback_regression_plan.py",
    "bgm_only": "bgm_only_no_camera_voice",
    "caption_overlay": "prepare_subtitle_overlay_asset.py",
    "orientation_repair": "prepare_orientation_repair_package.py",
    "visual_establishing": "prepare_visual_establishing_plan.py",
    "bilibili_malta": "bilibili-travel-style.md",
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
    "prepare_feedback_regression_plan.py",
    "audit_feedback_regressions.py",
    "prepare_bgm_sourcing_brief.py",
    "prepare_bgm_selection_package.py",
    "build_bgm_bed.py",
    "audit_bgm_audio_contract.py",
    "prepare_caption_story_plan.py",
    "prepare_subtitle_overlay_asset.py",
    "prepare_orientation_repair_package.py",
    "prepare_visual_establishing_plan.py",
    "prepare_transition_bridge_plan.py",
    "prepare_effect_motion_plan.py",
    "prepare_edit_rhythm_plan.py",
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
    rhythm = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
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

    rhythm_summary = get_summary(rhythm)
    route_summary = get_summary(route_texture)
    director_summary = get_summary(director_intent)
    add_check(
        checks,
        "Bilibili/Malta style, route texture, rhythm, and director polish gates pass",
        passed_status(reference)
        and passed_status(route_texture)
        and director_intent.get("status") in {"passed", "passed_with_warnings"}
        and passed_status(director_polish)
        and rhythm.get("status") == "ready_with_edit_rhythm_plan"
        and int(route_summary.get("matchedTransitions") or 0) >= 1
        and int(rhythm_summary.get("primaryVisualShotCount") or 0) >= 40,
        {
            "referenceStyleStatus": reference.get("status"),
            "routeTextureStatus": route_texture.get("status"),
            "routeTextureSummary": route_summary,
            "directorIntentStatus": director_intent.get("status"),
            "directorIntentSummary": director_summary,
            "directorPolishStatus": director_polish.get("status"),
            "editRhythmStatus": rhythm.get("status"),
            "editRhythmSummary": rhythm_summary,
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
        "Final QA suite preserves the V14 17-stage handoff floor",
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
        "Skill maturity preserves the V14 29-check reusable-skill floor",
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
