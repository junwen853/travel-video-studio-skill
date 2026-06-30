#!/usr/bin/env python3
"""Audit a finished long-form travel film against the end-to-end delivery promise."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def ffprobe_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


def path_exists(value: str | None) -> bool:
    return bool(value) and Path(value).expanduser().exists()


def count_srt_cues(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for block in path.read_text(encoding="utf-8", errors="ignore").strip().split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if any("-->" in line for line in lines):
            count += 1
    return count


def check(checks: list[dict[str, Any]], requirement: str, passed: bool, evidence: str, *, warning: bool = False) -> None:
    if passed:
        status = "passed"
    else:
        status = "warning" if warning else "blocked"
    checks.append({"requirement": requirement, "status": status, "evidence": evidence})


def newest_existing(package_dir: Path, names: list[str]) -> Path | None:
    candidates = [package_dir / name for name in names if (package_dir / name).exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_project_artifact(project_dir: Path | None, name: str) -> Any | None:
    if not project_dir:
        return None
    return load_json(project_dir / name)


def voiceover_disabled(package_dir: Path, blueprint: dict[str, Any], enrichment: dict[str, Any], quality_report: dict[str, Any]) -> bool:
    if blueprint.get("voiceoverDisabled") is True or quality_report.get("voiceoverDisabled") is True:
        return True
    voiceover_plans = [
        (blueprint.get("audioPlan") or {}).get("voiceover") or {},
        (enrichment.get("audioPlan") or {}).get("voiceover") or {},
    ]
    if any(plan.get("status") == "disabled_user_requested_text_only" for plan in voiceover_plans):
        return True
    return (package_dir / "narration_text_only_v4.txt").exists() and not (package_dir / "voiceover" / "voiceover.m4a").exists()


def timeline_track_count(resolve_audit: dict[str, Any], kind: str, index: int) -> int | None:
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        if int(row.get("index") or -1) == index:
            return int(row.get("itemCount") or 0)
    return None


def infer_final_output(package_dir: Path, render_verification: dict[str, Any], render_plan: dict[str, Any], final_report: dict[str, Any]) -> Path:
    candidates: list[str] = []
    for value in (
        render_verification.get("output"),
        render_plan.get("finalOutput"),
        render_plan.get("output"),
        final_report.get("finalOutput"),
    ):
        if value:
            candidates.append(str(value))
    target_dir = render_plan.get("targetDir")
    custom_name = render_plan.get("customName")
    if target_dir and custom_name:
        candidates.append(str(Path(target_dir) / f"{custom_name}.mp4"))
    for value in candidates:
        path = Path(value).expanduser()
        if path.exists() and file_size(path) > 0:
            return path
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    if renders:
        return renders[0]
    return package_dir / "renders" / "__missing__.mp4"


def source_audio_disabled_for_bgm_only(blueprint: dict[str, Any]) -> bool:
    audio_plan = blueprint.get("audioPlan") if isinstance(blueprint.get("audioPlan"), dict) else {}
    source_audio = audio_plan.get("sourceAudio") if isinstance(audio_plan.get("sourceAudio"), dict) else {}
    if str(source_audio.get("status") or "").startswith("disabled"):
        return True
    mode = str(audio_plan.get("mode") or "").lower()
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return "bgm_only" in mode and clips and all(not clip.get("includeSourceAudio") for clip in clips)


def acceptable_preflight_warning(warning: Any, *, no_voiceover_mode: bool, source_audio_disabled: bool) -> bool:
    text = str(warning)
    if no_voiceover_mode and "Voiceover plan status" in text:
        return True
    if source_audio_disabled and "not marked to preserve source/camera audio" in text:
        return True
    return False


def subtitle_manifest_cue_count(package_dir: Path) -> tuple[int, Path | None]:
    manifests = sorted(package_dir.glob("subtitle_overlays_*/manifest.json"), key=lambda path: path.stat().st_mtime)
    if not manifests:
        return 0, None
    manifest = manifests[-1]
    payload = load_json(manifest) or {}
    cues = payload.get("cues") or payload.get("items") or []
    return int(payload.get("cueCount") or len(cues)), manifest


def route_caveat_is_honest(text: str) -> bool:
    normalized = text.lower()
    if not normalized:
        return False
    uncertainty_terms = (
        "not a verified per-clip geolocation",
        "not verified per-clip gps geolocation",
        "not verified per-clip geolocation",
        "no gps metadata",
        "non-gps visual route reconstruction",
    )
    return any(term in normalized for term in uncertainty_terms)


def audit(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    checks: list[dict[str, Any]] = []

    delivery_plan = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    enrichment = load_json(package_dir / "resolve_timeline_enrichment.json") or {}
    delivery_audit = load_json(package_dir / "delivery_audit.json") or {}
    resolve_preflight = load_json(package_dir / "resolve_blueprint_preflight.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    render_plan = load_json(package_dir / "render_plan.json") or {}
    render_verification = load_json(package_dir / "render_delivery_verification.json") or {}
    final_report = load_json(package_dir / "FINAL_DELIVERY_REPORT.json") or {}
    story_audit = load_json(package_dir / "story_style_contract_audit.json") or {}
    client_audit = load_json(package_dir / "client_delivery_rules_audit.json") or {}
    quality_report = load_json(package_dir / "quality_recut_report.json") or {}
    asset_ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    delivery_assets = load_json(package_dir / "delivery_assets_report.json") or {}
    no_voiceover_mode = voiceover_disabled(package_dir, blueprint, enrichment, quality_report)

    project_dir_value = delivery_plan.get("projectDir") or str(package_dir.parents[1]) if len(package_dir.parents) > 1 else None
    project_dir = Path(project_dir_value).expanduser().resolve() if project_dir_value else None

    final_output = infer_final_output(package_dir, render_verification, render_plan, final_report).expanduser()

    duration = float(render_verification.get("durationSeconds") or final_report.get("durationSeconds") or 0)
    video = render_verification.get("video") or final_report.get("video") or {}
    audio = render_verification.get("audio") or final_report.get("audio") or {}
    blackdetect = render_verification.get("blackdetect") or {}

    check(
        checks,
        "Final MP4 exists",
        final_output.exists() and file_size(final_output) >= int(args.min_size_mb * 1024 * 1024),
        f"{final_output} ({file_size(final_output)} bytes)",
    )
    check(
        checks,
        "Final render verification passed",
        render_verification.get("status") == "passed" and not render_verification.get("blockers"),
        f"status={render_verification.get('status')} blockers={render_verification.get('blockers')}",
    )
    check(
        checks,
        "Long-form duration is around 20 minutes, not a 1-2 minute short",
        duration >= args.min_duration_seconds,
        f"durationSeconds={duration} required>={args.min_duration_seconds}",
    )
    check(
        checks,
        "Final video resolution is delivery-grade 4K",
        int(video.get("width") or 0) == args.width and int(video.get("height") or 0) == args.height,
        f"resolution={video.get('width')}x{video.get('height')} expected={args.width}x{args.height}",
    )
    check(
        checks,
        "Final video frame rate is high enough for smooth delivery",
        float(video.get("frameRateValue") or 0) >= args.min_fps,
        f"frameRateValue={video.get('frameRateValue')} required>={args.min_fps}",
    )
    check(
        checks,
        "Final video bitrate is high enough for the requested high-quality export",
        float(video.get("bitrateMbps") or 0) >= args.min_video_bitrate_mbps,
        f"bitrateMbps={video.get('bitrateMbps')} required>={args.min_video_bitrate_mbps}",
    )
    check(
        checks,
        "Final output has stereo audio",
        bool(audio.get("codec")) and int(audio.get("channels") or 0) >= 2,
        f"audio={audio}",
    )
    check(
        checks,
        "Full-film black-frame scan passed",
        blackdetect.get("blackSegmentCount") == 0,
        f"blackdetect={blackdetect}",
    )

    target = float(blueprint.get("targetDurationSeconds") or 0)
    coverage = float(blueprint.get("actualVideoCoverageSeconds") or blueprint.get("longFormCoverage", {}).get("finalVideoCoverageSeconds") or 0)
    check(
        checks,
        "DaVinci blueprint targets the requested long-form duration",
        target >= args.min_duration_seconds and coverage >= args.min_duration_seconds * 0.98,
        f"targetDurationSeconds={target} actualVideoCoverageSeconds={coverage}",
    )
    check(
        checks,
        "DaVinci Resolve timeline was written and read back",
        bool(resolve_audit.get("projectName")) and bool(resolve_audit.get("timelineName")) and not resolve_audit.get("warnings"),
        f"project={resolve_audit.get('projectName')} timeline={resolve_audit.get('timelineName')} warnings={resolve_audit.get('warnings')}",
    )
    preflight_status = resolve_preflight.get("status")
    preflight_warnings = resolve_preflight.get("warnings") or []
    source_audio_disabled = source_audio_disabled_for_bgm_only(blueprint)
    acceptable_preflight_warnings = (
        preflight_status == "ready_with_warnings"
        and not resolve_preflight.get("blockers")
        and preflight_warnings
        and all(
            acceptable_preflight_warning(
                item,
                no_voiceover_mode=no_voiceover_mode,
                source_audio_disabled=source_audio_disabled,
            )
            for item in preflight_warnings
        )
    )
    check(
        checks,
        "Resolve blueprint preflight is clean",
        (preflight_status == "ready" and not resolve_preflight.get("blockers")) or acceptable_preflight_warnings,
        f"status={preflight_status} blockers={resolve_preflight.get('blockers')} warnings={preflight_warnings}",
    )
    final_report_passed = final_report.get("status") in {
        "passed",
        "passed_with_caveats",
        "delivered",
        "delivered_with_route_caveats",
    }
    render_verified = render_verification.get("status") == "passed" and not render_verification.get("blockers")
    downstream_audits_passed = (
        story_audit.get("status") in {"passed", "passed_with_caveats"}
        and client_audit.get("status") in {"passed", "passed_with_caveats"}
        and render_verified
    )
    check(
        checks,
        "Delivery audit allowed final render",
        (
            delivery_audit.get("status") in {"ready_for_final_render", "ready_for_final_render_with_warnings"}
            and bool(delivery_audit.get("finalRenderAllowed", True))
            and not delivery_audit.get("blockers")
        )
        or ((final_report_passed or downstream_audits_passed) and render_verified and not delivery_audit.get("blockers")),
        (
            f"status={delivery_audit.get('status')} blockers={delivery_audit.get('blockers')} "
            f"finalReportStatus={final_report.get('status')} renderVerification={render_verification.get('status')}"
        ),
    )

    if no_voiceover_mode:
        narration_txt = newest_existing(package_dir, ["narration_text_only_v4.txt", "voiceover_script.txt"])
        a2_count = timeline_track_count(resolve_audit, "audio", 2)
        check(
            checks,
            "Voiceover audio is disabled and exported as text only",
            bool(narration_txt) and file_size(narration_txt) > 0 and a2_count == 0,
            f"narrationText={narration_txt} a2VoiceoverItemCount={a2_count}",
        )
    else:
        voiceover_path = Path((enrichment.get("audioPlan") or {}).get("voiceover", {}).get("sourcePath") or package_dir / "voiceover" / "voiceover.m4a")
        voiceover_duration = ffprobe_duration(voiceover_path)
        check(
            checks,
            "Voiceover script and generated audio exist",
            (package_dir / "voiceover_script.txt").exists() and path_exists(str(voiceover_path)) and (voiceover_duration or 0) >= 10,
            f"script={package_dir / 'voiceover_script.txt'} voiceover={voiceover_path} duration={voiceover_duration}",
        )

    srt = newest_existing(package_dir, ["subtitles_v4_dense.srt", "subtitles.srt"]) or package_dir / "subtitles.srt"
    subtitle_evidence = render_verification.get("subtitles") or {}
    cue_count = count_srt_cues(srt)
    overlay_cue_count, overlay_manifest = subtitle_manifest_cue_count(package_dir)
    check(
        checks,
        "Dense subtitles exist and are represented in the final delivery evidence",
        cue_count >= args.min_subtitle_cues
        and bool(subtitle_evidence.get("sidecar") or subtitle_evidence.get("subtitleStreamCount") or subtitle_evidence.get("burnedInOverlayManifest")),
        f"srt={srt} cueCount={cue_count} overlayCueCount={overlay_cue_count} overlayManifest={overlay_manifest} evidence={subtitle_evidence}",
    )

    ledger_items = asset_ledger.get("items") or []
    type_counts = Counter(item.get("type") for item in ledger_items)
    bgm_rows = [item for item in ledger_items if item.get("type") == "bgm"]
    aerial_rows = [item for item in ledger_items if item.get("type") == "aerial_or_stock"]
    font_rows = [item for item in ledger_items if item.get("type") == "font"]
    bad_bgm = [item for item in bgm_rows if item.get("licenseStatus") != "verified" or not path_exists(item.get("localPath"))]
    bad_aerial = [
        item
        for item in aerial_rows
        if item.get("licenseStatus") != "verified" or not (path_exists(item.get("localPath")) or item.get("selectedAssetUrl") == "user-provided-source-footage")
    ]
    good_fonts = [item for item in font_rows if item.get("licenseStatus") == "system-font-render-only" and path_exists(item.get("localPath"))]

    check(
        checks,
        "BGM has verified local source evidence",
        bool(bgm_rows) and not bad_bgm and asset_ledger.get("finalReady") is True,
        f"bgmRows={len(bgm_rows)} badBgmRows={len(bad_bgm)} finalReady={asset_ledger.get('finalReady')}",
    )
    bgm_file = newest_existing(package_dir, ["bgm/original_tokyo_osaka_ambient_20min.m4a"])
    bgm_duration = ffprobe_duration(bgm_file) if bgm_file else None
    check(
        checks,
        "BGM bed can sustain the long-form runtime",
        bool(bgm_file) and (bgm_duration or 0) >= args.min_duration_seconds * 0.9,
        f"bgm={bgm_file} duration={bgm_duration}",
    )
    bgm_track_count = timeline_track_count(resolve_audit, "audio", 3)
    check(
        checks,
        "BGM is present on the Resolve timeline audio track",
        bool(bgm_track_count and bgm_track_count > 0),
        f"a3BgmItemCount={bgm_track_count}",
    )
    check(
        checks,
        "Aerial or establishing inserts have verified evidence",
        bool(aerial_rows) and not bad_aerial,
        f"aerialRows={len(aerial_rows)} badAerialRows={len(bad_aerial)}",
    )
    check(
        checks,
        "Typography/font use is auditable",
        bool(good_fonts),
        f"fontRows={len(font_rows)} systemFontRows={len(good_fonts)}",
    )

    title_manifest = load_json(package_dir / "title_cards" / "title_cards_manifest.json") or {}
    title_card_count = len(title_manifest.get("cards") or title_manifest.get("items") or [])
    if not title_card_count:
        title_card_count = len(list((package_dir / "title_cards").glob("*.mp4")))
    check(
        checks,
        "Opening/chapter/ending title cards exist",
        title_card_count >= 3 and (delivery_assets.get("titleCards") or {}).get("status") == "ready",
        f"titleCardCount={title_card_count} deliveryAssetsTitleStatus={(delivery_assets.get('titleCards') or {}).get('status')}",
    )

    transition_count = len(enrichment.get("transitionPlan") or blueprint.get("transitionPlan") or [])
    marker_count = len(enrichment.get("timelineMarkers") or blueprint.get("timelineMarkers") or [])
    check(
        checks,
        "Day/chapter transitions and Resolve markers are planned",
        transition_count > 0 and marker_count > 0,
        f"transitionCount={transition_count} markerCount={marker_count}",
    )

    location_recognition = load_project_artifact(project_dir, "latest_location_recognition.json") or {}
    route_pipeline = load_project_artifact(project_dir, "latest_location_route_pipeline.json") or {}
    confirmed_route = load_project_artifact(project_dir, "confirmed_route_timeline.json") or {}
    check(
        checks,
        "Cloud/local route recognition artifacts exist",
        bool(location_recognition) and bool(route_pipeline) and bool(confirmed_route),
        (
            f"cloudProvider={location_recognition.get('summary', {}).get('cloudProviderUsed') or location_recognition.get('cloudProviderModel')} "
            f"localModel={route_pipeline.get('localModelUsed')} confirmedChapters={confirmed_route.get('chapterCount')}"
        ),
    )
    route_caveat = (
        final_report.get("knownCaveat")
        or final_report.get("routeCaveat")
        or story_audit.get("routeCaveat")
        or ""
    )
    check(
        checks,
        "Route/location certainty is honestly documented",
        route_caveat_is_honest(route_caveat),
        f"knownCaveat={route_caveat}",
    )
    if route_caveat_is_honest(route_caveat):
        checks.append(
            {
                "requirement": "Verified per-clip geolocation remains unproven",
                "status": "blocked" if args.require_verified_per_clip_location else "warning",
                "evidence": route_caveat,
            }
        )

    workflow = load_json(package_dir / "workflow_run_report.json") or {}
    workflow_blocked = workflow.get("status") == "blocked"
    check(
        checks,
        "Safe workflow report is present; later final reports supersede stale blockers",
        bool(workflow),
        f"workflowStatus={workflow.get('status')} deliveryAuditStatus={delivery_audit.get('status')} finalReportStatus={final_report.get('status')}",
        warning=True,
    )
    if workflow_blocked and final_report_passed:
        checks.append(
            {
                "requirement": "Stale workflow blockers were superseded by later apply/render/verification reports",
                "status": "warning",
                "evidence": f"workflow blockers={workflow.get('blockers')} finalReportStatus={final_report.get('status')}",
            }
        )

    required_docs = [
        "long_form_structure.md",
        "edit_decision_plan.md",
        "bgm_cues.md",
        "asset_search_plan.md",
        "qa_checklist.md",
        "davinci_build_notes.md",
        "FINAL_DELIVERY_REPORT.md",
    ]
    missing_docs = [name for name in required_docs if not (package_dir / name).exists() or file_size(package_dir / name) == 0]
    check(
        checks,
        "Long-form handoff documents exist",
        not missing_docs,
        f"missingDocs={missing_docs}",
    )

    blocked = [row for row in checks if row["status"] == "blocked"]
    warnings = [row for row in checks if row["status"] == "warning"]
    status = "blocked" if blocked else ("passed_with_caveats" if warnings else "passed")

    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "projectDir": str(project_dir) if project_dir else None,
        "finalOutput": str(final_output),
        "summary": {
            "checks": len(checks),
            "passed": len([row for row in checks if row["status"] == "passed"]),
            "warnings": len(warnings),
            "blocked": len(blocked),
            "assetTypeCounts": dict(type_counts),
        },
        "checks": checks,
        "blockers": [row["requirement"] for row in blocked],
        "warnings": [row["requirement"] for row in warnings],
        "routeCaveat": route_caveat,
        "note": "passed_with_caveats means the rendered long-form film is deliverable, but route/location truth is not proven at GPS/per-clip certainty.",
    }


def write_report(report: dict[str, Any], package_dir: Path) -> None:
    json_path = package_dir / "longform_delivery_audit.json"
    md_path = package_dir / "longform_delivery_audit.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Long-Form Delivery Audit",
        "",
        f"Status: `{report['status']}`",
        f"Final output: `{report['finalOutput']}`",
        "",
        "## Summary",
        f"- Checks: `{report['summary']['checks']}`",
        f"- Passed: `{report['summary']['passed']}`",
        f"- Warnings: `{report['summary']['warnings']}`",
        f"- Blocked: `{report['summary']['blocked']}`",
        "",
        "## Checks",
    ]
    for row in report["checks"]:
        lines.extend(["", f"### {row['requirement']}", f"- Status: `{row['status']}`", f"- Evidence: `{row['evidence']}`"])
    if report.get("routeCaveat"):
        lines.extend(["", "## Route Caveat", report["routeCaveat"]])
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a completed 20-minute travel film delivery package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-duration-seconds", type=float, default=1190.0)
    parser.add_argument("--min-size-mb", type=float, default=100.0)
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--min-fps", type=float, default=50.0)
    parser.add_argument("--min-video-bitrate-mbps", type=float, default=60.0)
    parser.add_argument("--min-subtitle-cues", type=int, default=40)
    parser.add_argument("--require-verified-per-clip-location", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = audit(package_dir, args)
    write_report(report, package_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Long-form delivery audit: {report['status']}")
        print(f"Passed: {report['summary']['passed']}; warnings: {report['summary']['warnings']}; blocked: {report['summary']['blocked']}")
        for blocker in report["blockers"]:
            print(f"BLOCKER: {blocker}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
    return 0 if report["status"] in {"passed", "passed_with_caveats"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
