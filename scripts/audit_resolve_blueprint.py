#!/usr/bin/env python3
"""Preflight a Resolve timeline blueprint before any DaVinci --apply write."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


VIDEO_ONLY_ROLES = {
    "title_card",
    "place_card",
    "chapter_title_bridge",
    "map_card",
    "aerial_insert",
    "stock_insert",
    "overlay",
}

TITLE_BRIDGE_ROLES = {
    "title_card",
    "place_card",
    "chapter_title_bridge",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def probe_duration(path: Path, cache: dict[str, float | None]) -> float | None:
    key = str(path)
    if key in cache:
        return cache[key]
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        cache[key] = None
        return None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        cache[key] = None
        return None
    try:
        cache[key] = float(json.loads(result.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        cache[key] = None
    return cache[key]


def clip_interval(clip: dict[str, Any]) -> tuple[float, float]:
    start = as_float(clip.get("timelineStartSeconds"))
    end = as_float(clip.get("timelineEndSeconds"))
    if end <= start and clip.get("durationSeconds") is not None:
        end = start + as_float(clip.get("durationSeconds"))
    return start, end


def source_interval(clip: dict[str, Any]) -> tuple[float, float]:
    start = as_float(clip.get("sourceStartSeconds"))
    end = as_float(clip.get("sourceEndSeconds"))
    if end <= start and clip.get("durationSeconds") is not None:
        end = start + as_float(clip.get("durationSeconds"))
    return start, end


def track_key(clip: dict[str, Any]) -> tuple[str, int]:
    return str(clip.get("trackType") or "video"), int(clip.get("trackIndex") or 1)


def audit_track_overlaps(
    clips: list[dict[str, Any]],
    fps: float,
) -> tuple[list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    overlaps: list[dict[str, Any]] = []
    frame_tolerance = max(0.001, 1.5 / max(1.0, fps))
    by_track: dict[tuple[str, int], list[tuple[float, float, dict[str, Any]]]] = defaultdict(list)
    for clip in clips:
        start, end = clip_interval(clip)
        by_track[track_key(clip)].append((start, end, clip))
    for key, rows in by_track.items():
        rows.sort(key=lambda row: (row[0], row[1]))
        previous_end = None
        previous_clip: dict[str, Any] | None = None
        for start, end, clip in rows:
            if previous_end is not None and start < previous_end - frame_tolerance:
                item = {
                    "trackType": key[0],
                    "trackIndex": key[1],
                    "previousRole": previous_clip.get("role") if previous_clip else None,
                    "role": clip.get("role"),
                    "overlapStartSeconds": round(start, 3),
                    "previousEndSeconds": round(previous_end, 3),
                    "sourcePath": clip.get("sourcePath"),
                }
                overlaps.append(item)
                blockers.append(
                    f"Track {key[0]} {key[1]} has overlapping clips around {start:.2f}s."
                )
            if previous_end is None or end > previous_end:
                previous_end = end
                previous_clip = clip
    return blockers, overlaps


def audit_v1_gaps(clips: list[dict[str, Any]], target_seconds: float, fps: float) -> tuple[list[str], list[dict[str, float]]]:
    blockers: list[str] = []
    gaps: list[dict[str, float]] = []
    tolerance = max(1.0, 2.0 / max(1.0, fps))
    intervals = []
    for clip in clips:
        if track_key(clip) != ("video", 1):
            continue
        start, end = clip_interval(clip)
        if end > start:
            intervals.append((max(0.0, start), min(target_seconds, end)))
    intervals.sort()
    cursor = 0.0
    for start, end in intervals:
        if start > cursor + tolerance:
            gaps.append({"startSeconds": round(cursor, 3), "endSeconds": round(start, 3), "durationSeconds": round(start - cursor, 3)})
        cursor = max(cursor, end)
    if target_seconds and cursor < target_seconds - tolerance:
        gaps.append({"startSeconds": round(cursor, 3), "endSeconds": round(target_seconds, 3), "durationSeconds": round(target_seconds - cursor, 3)})
    if gaps:
        blockers.append(f"V1 has {len(gaps)} timeline coverage gaps before the target duration.")
    return blockers, gaps


def audit_clips(blueprint: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    fps = as_float(blueprint.get("fps"), 25.0) or 25.0
    target_seconds = as_float(blueprint.get("targetDurationSeconds"), 0.0)
    duration_cache: dict[str, float | None] = {}
    missing_sources: list[str] = []
    unprobeable_sources: list[str] = []
    invalid_ranges: list[dict[str, Any]] = []
    out_of_bounds: list[dict[str, Any]] = []
    too_short: list[dict[str, Any]] = []
    role_counts = Counter(str(clip.get("role") or "unknown") for clip in clips)
    source_audio_count = 0
    footage_without_source_audio = 0
    title_with_audio = 0
    title_card_count = 0

    for index, clip in enumerate(clips):
        source_path = clip.get("sourcePath")
        role = str(clip.get("role") or "")
        timeline_start, timeline_end = clip_interval(clip)
        source_start, source_end = source_interval(clip)
        if clip.get("includeSourceAudio"):
            source_audio_count += 1
        if role in TITLE_BRIDGE_ROLES:
            title_card_count += 1
            if clip.get("includeSourceAudio"):
                title_with_audio += 1
        elif role not in VIDEO_ONLY_ROLES and int(clip.get("trackIndex") or 1) == 1 and not clip.get("includeSourceAudio"):
            footage_without_source_audio += 1
        if not source_path:
            invalid_ranges.append({"clipIndex": index, "reason": "missing sourcePath", "role": role})
            continue
        path = Path(str(source_path)).expanduser()
        if not path.exists():
            missing_sources.append(str(path))
            continue
        source_duration = probe_duration(path, duration_cache)
        if source_duration is None:
            unprobeable_sources.append(str(path))
        if timeline_end <= timeline_start:
            invalid_ranges.append(
                {
                    "clipIndex": index,
                    "reason": "timeline end <= start",
                    "role": role,
                    "sourcePath": str(path),
                    "timelineStartSeconds": timeline_start,
                    "timelineEndSeconds": timeline_end,
                }
            )
        if source_end <= source_start:
            invalid_ranges.append(
                {
                    "clipIndex": index,
                    "reason": "source end <= start",
                    "role": role,
                    "sourcePath": str(path),
                    "sourceStartSeconds": source_start,
                    "sourceEndSeconds": source_end,
                }
            )
        if timeline_end - timeline_start < 0.5:
            too_short.append({"clipIndex": index, "role": role, "sourcePath": str(path), "durationSeconds": round(timeline_end - timeline_start, 3)})
        if source_duration is not None and source_end > source_duration + max(0.05, 1.0 / fps):
            out_of_bounds.append(
                {
                    "clipIndex": index,
                    "role": role,
                    "sourcePath": str(path),
                    "sourceEndSeconds": round(source_end, 3),
                    "sourceDurationSeconds": round(source_duration, 3),
                }
            )

    if missing_sources:
        blockers.append(f"{len(set(missing_sources))} referenced source files are missing.")
    if invalid_ranges:
        blockers.append(f"{len(invalid_ranges)} clips have invalid source or timeline ranges.")
    if out_of_bounds:
        blockers.append(f"{len(out_of_bounds)} clips exceed probed source duration.")
    overlap_blockers, overlaps = audit_track_overlaps(clips, fps)
    blockers.extend(overlap_blockers)
    gap_blockers, v1_gaps = audit_v1_gaps(clips, target_seconds, fps) if target_seconds else ([], [])
    blockers.extend(gap_blockers)

    if unprobeable_sources:
        warnings.append(f"{len(set(unprobeable_sources))} source files exist but could not be probed with ffprobe.")
    if too_short:
        warnings.append(f"{len(too_short)} clips are shorter than 0.5s and may be accidental flashes.")
    if footage_without_source_audio:
        warnings.append(f"{footage_without_source_audio} V1 footage clips are not marked to preserve source/camera audio.")
    if title_with_audio:
        warnings.append(f"{title_with_audio} title/place card clips are unexpectedly marked with source audio.")
    if title_card_count == 0:
        warnings.append("No title/place card clips are present in the Resolve blueprint.")

    summary = {
        "clipCount": len(clips),
        "sourceFileCount": len({str(clip.get("sourcePath")) for clip in clips if clip.get("sourcePath")}),
        "roleCounts": dict(role_counts),
        "sourceAudioClipCount": source_audio_count,
        "footageWithoutSourceAudioCount": footage_without_source_audio,
        "titleCardCount": title_card_count,
        "missingSourceCount": len(set(missing_sources)),
        "missingSources": sorted(set(missing_sources))[:50],
        "unprobeableSourceCount": len(set(unprobeable_sources)),
        "invalidRangeCount": len(invalid_ranges),
        "invalidRanges": invalid_ranges[:50],
        "outOfBoundsCount": len(out_of_bounds),
        "outOfBounds": out_of_bounds[:50],
        "shortClipCount": len(too_short),
        "overlapCount": len(overlaps),
        "overlaps": overlaps[:50],
        "v1GapCount": len(v1_gaps),
        "v1Gaps": v1_gaps[:50],
    }
    return blockers, warnings, summary


def audit_assets(blueprint: dict[str, Any], package_dir: Path | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    title_cards = [Path(str(path)).expanduser() for path in assets.get("titleCards", []) if path]
    missing_title_cards = [str(path) for path in title_cards if not path.exists()]
    subtitles = Path(str(assets.get("subtitles") or "")).expanduser() if assets.get("subtitles") else None
    voiceover = Path(str(assets.get("voiceover") or "")).expanduser() if assets.get("voiceover") else None
    bgm = [Path(str(path)).expanduser() for path in assets.get("bgm", []) if path] if isinstance(assets.get("bgm"), list) else []
    missing_bgm = [str(path) for path in bgm if not path.exists()]
    if missing_title_cards:
        blockers.append(f"{len(missing_title_cards)} generated title/place card assets are missing.")
    if not subtitles or not subtitles.exists():
        warnings.append("Subtitle SRT sidecar is missing from blueprint assets.")
    if voiceover and not voiceover.exists():
        warnings.append("Voiceover asset path is planned but not generated yet.")
    if missing_bgm:
        warnings.append(f"{len(missing_bgm)} planned BGM assets are missing.")
    manifest_exists = False
    if package_dir:
        manifest_exists = (package_dir / "title_cards" / "title_cards_manifest.json").exists()
        if title_cards and not manifest_exists:
            warnings.append("Title cards are referenced but title_cards_manifest.json is missing.")
    summary = {
        "titleCardAssetCount": len(title_cards),
        "missingTitleCardAssetCount": len(missing_title_cards),
        "missingTitleCardAssets": missing_title_cards,
        "titleCardsManifestExists": manifest_exists,
        "subtitleSidecar": str(subtitles) if subtitles else "",
        "subtitleSidecarExists": bool(subtitles and subtitles.exists()),
        "voiceoverPath": str(voiceover) if voiceover else "",
        "voiceoverExists": bool(voiceover and voiceover.exists()),
        "bgmAssetCount": len(bgm),
        "missingBgmAssetCount": len(missing_bgm),
    }
    return blockers, warnings, summary


def audit_enrichment(blueprint: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    audio_plan = blueprint.get("audioPlan") if isinstance(blueprint.get("audioPlan"), dict) else {}
    voice = audio_plan.get("voiceover") if isinstance(audio_plan.get("voiceover"), dict) else {}
    bgm = audio_plan.get("bgmCues") if isinstance(audio_plan.get("bgmCues"), list) else []
    subtitles = blueprint.get("subtitleCues") if isinstance(blueprint.get("subtitleCues"), list) else []
    stock = blueprint.get("stockInsertPlan") if isinstance(blueprint.get("stockInsertPlan"), list) else []
    transitions = blueprint.get("transitionPlan") if isinstance(blueprint.get("transitionPlan"), list) else []
    markers = blueprint.get("timelineMarkers") if isinstance(blueprint.get("timelineMarkers"), list) else []
    marker_roles = Counter(str(marker.get("role") or "unknown") for marker in markers)
    if not subtitles:
        warnings.append("Blueprint has no parsed subtitle cues; Resolve handoff will rely on external subtitle work.")
    if not bgm:
        warnings.append("Blueprint has no BGM cue plan.")
    if not stock:
        warnings.append("Blueprint has no stock/aerial placeholder plan.")
    if not transitions:
        warnings.append("Blueprint has no chapter transition plan.")
    if not markers:
        warnings.append("Blueprint has no Resolve timeline markers.")
    if not voice:
        warnings.append("Blueprint has no voiceover mix/import plan.")
    elif voice.get("status") != "ready_to_import":
        warnings.append(f"Voiceover plan status is `{voice.get('status')}`.")
    summary = {
        "subtitleCueCount": len(subtitles),
        "bgmCueCount": len(bgm),
        "stockPlaceholderCount": len(stock),
        "transitionCount": len(transitions),
        "timelineMarkerCount": len(markers),
        "markerRoles": dict(marker_roles),
        "voiceoverStatus": voice.get("status"),
    }
    return blockers, warnings, summary


def build_report(blueprint_path: Path, package_dir: Path | None = None) -> dict[str, Any]:
    blueprint_path = blueprint_path.expanduser().resolve()
    blueprint = load_json(blueprint_path)
    package_dir = package_dir.expanduser().resolve() if package_dir else blueprint_path.parent
    blockers: list[str] = []
    warnings: list[str] = []

    fps = as_float(blueprint.get("fps"), 25.0) or 25.0
    target_seconds = as_float(blueprint.get("targetDurationSeconds"), 0.0)
    coverage_ratio = as_float(blueprint.get("coverageRatio"), 0.0)
    if not blueprint.get("projectName"):
        blockers.append("Blueprint projectName is missing.")
    if not blueprint.get("timelineName"):
        blockers.append("Blueprint timelineName is missing.")
    if fps <= 0:
        blockers.append("Blueprint fps must be positive.")
    if target_seconds < 900:
        warnings.append("Blueprint target duration is below 15 minutes; this is weak for the requested long-form film.")
    if coverage_ratio < 0.95:
        blockers.append(f"Blueprint coverageRatio is {coverage_ratio:.3f}; expected at least 0.95 before Resolve write.")

    clip_blockers, clip_warnings, clip_summary = audit_clips(blueprint)
    asset_blockers, asset_warnings, asset_summary = audit_assets(blueprint, package_dir)
    enrichment_blockers, enrichment_warnings, enrichment_summary = audit_enrichment(blueprint)
    blockers.extend(clip_blockers + asset_blockers + enrichment_blockers)
    warnings.extend(clip_warnings + asset_warnings + enrichment_warnings)

    status = "blocked" if blockers else ("ready_with_warnings" if warnings else "ready")
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "blueprint": str(blueprint_path),
        "packageDir": str(package_dir) if package_dir else "",
        "projectName": blueprint.get("projectName"),
        "timelineName": blueprint.get("timelineName"),
        "fps": fps,
        "resolution": blueprint.get("resolution"),
        "targetDurationSeconds": target_seconds,
        "coverageRatio": coverage_ratio,
        "longFormCoverage": blueprint.get("longFormCoverage"),
        "clipSummary": clip_summary,
        "assetSummary": asset_summary,
        "enrichmentSummary": enrichment_summary,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "nextActions": next_actions(blockers, warnings, package_dir),
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "modifiesSourceDrive": False,
        },
    }
    return report


def next_actions(blockers: list[str], warnings: list[str], package_dir: Path | None) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if any("missing" in item.lower() for item in blockers):
        actions.append({"priority": "P0", "action": "Restore or regenerate missing referenced media/assets.", "command": "Reconnect source drives or rerun prepare_delivery_assets.py."})
    if any("coverage" in item.lower() or "gap" in item.lower() for item in blockers):
        actions.append({"priority": "P0", "action": "Repair long-form V1 timeline coverage before Resolve write.", "command": "Rerun build_delivery_package.py or select more source ranges."})
    if any("overlap" in item.lower() for item in blockers):
        actions.append({"priority": "P0", "action": "Fix same-track overlaps before Resolve write.", "command": "Regenerate or edit resolve_timeline_blueprint.json."})
    if warnings and package_dir:
        actions.append({"priority": "P1", "action": "Refresh package-level delivery audit.", "command": f"python3 <skill-dir>/scripts/audit_delivery_package.py --package-dir {package_dir}"})
    return actions


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Resolve Blueprint Preflight",
        "",
        f"Status: `{report['status']}`",
        f"Project: `{report.get('projectName')}`",
        f"Timeline: `{report.get('timelineName')}`",
        f"Coverage ratio: `{report.get('coverageRatio')}`",
        "",
        "## Clips",
        f"- Clips: {report['clipSummary'].get('clipCount')}",
        f"- Source files: {report['clipSummary'].get('sourceFileCount')}",
        f"- Source-audio clips: {report['clipSummary'].get('sourceAudioClipCount')}",
        f"- Title/place cards: {report['clipSummary'].get('titleCardCount')}",
        f"- V1 gaps: {report['clipSummary'].get('v1GapCount')}",
        f"- Same-track overlaps: {report['clipSummary'].get('overlapCount')}",
        "",
        "## Enrichment",
        f"- Subtitle cues: {report['enrichmentSummary'].get('subtitleCueCount')}",
        f"- BGM cues: {report['enrichmentSummary'].get('bgmCueCount')}",
        f"- Stock/aerial placeholders: {report['enrichmentSummary'].get('stockPlaceholderCount')}",
        f"- Transition cues: {report['enrichmentSummary'].get('transitionCount')}",
        f"- Timeline markers: {report['enrichmentSummary'].get('timelineMarkerCount')}",
        f"- Voiceover status: `{report['enrichmentSummary'].get('voiceoverStatus')}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in report.get("warnings") or ["None"])
    lines.extend(["", "## Next Actions"])
    for action in report.get("nextActions") or []:
        lines.append(f"- {action.get('priority')}: {action.get('action')} `{action.get('command')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight resolve_timeline_blueprint.json before DaVinci --apply.")
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--package-dir")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    blueprint_path = Path(args.blueprint).expanduser().resolve()
    package_dir = Path(args.package_dir).expanduser().resolve() if args.package_dir else blueprint_path.parent
    report = build_report(blueprint_path, package_dir)
    output = Path(args.output).expanduser().resolve() if args.output else package_dir / "resolve_blueprint_preflight.json"
    markdown = output.with_suffix(".md")
    write_json(output, report)
    write_markdown(markdown, report)
    report["preflightJson"] = str(output)
    report["preflightMarkdown"] = str(markdown)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Resolve blueprint preflight status: {report['status']}")
        print(f"Preflight JSON: {output}")
        print(f"Preflight Markdown: {markdown}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
