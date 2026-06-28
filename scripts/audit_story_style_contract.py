#!/usr/bin/env python3
"""Audit a travel edit for story, subtitle, BGM, transition, and DaVinci-readback readiness."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


SRT_TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def infer_visual_audio_audit(package_dir: Path) -> Path | None:
    default = package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json"
    if default.exists():
        return default.resolve()
    candidates = [
        path
        for path in (package_dir / "qa").glob("**/visual_audio_style_audit.json")
        if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime).resolve()


def srt_seconds(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_srt(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
    cues: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        time_index = next((idx for idx, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        match = SRT_TIME_RE.search(lines[time_index])
        if not match:
            continue
        start = srt_seconds(match.group("start"))
        end = srt_seconds(match.group("end"))
        if end <= start:
            continue
        cues.append({"start": start, "end": end, "text": " ".join(lines[time_index + 1 :]).strip()})
    return cues


def cue_gap_stats(cues: list[dict[str, Any]], duration: float) -> dict[str, Any]:
    if not cues:
        return {"maxGapSeconds": None, "longGaps": []}
    sorted_cues = sorted(cues, key=lambda cue: cue["start"])
    gaps: list[dict[str, float]] = []
    prev_end = 0.0
    for cue in sorted_cues:
        start = float(cue["start"])
        if start > prev_end:
            gaps.append({"start": round(prev_end, 3), "end": round(start, 3), "duration": round(start - prev_end, 3)})
        prev_end = max(prev_end, float(cue["end"]))
    if duration > prev_end:
        gaps.append({"start": round(prev_end, 3), "end": round(duration, 3), "duration": round(duration - prev_end, 3)})
    max_gap = max((gap["duration"] for gap in gaps), default=0.0)
    return {"maxGapSeconds": max_gap, "longGaps": sorted(gaps, key=lambda gap: gap["duration"], reverse=True)[:10]}


def find_subtitle_path(package_dir: Path, blueprint: dict[str, Any]) -> Path | None:
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    candidates: list[Path] = []
    if assets.get("subtitles"):
        candidates.append(Path(str(assets["subtitles"])).expanduser())
    candidates.extend(sorted(package_dir.glob("subtitles*_dense.srt")))
    candidates.extend([package_dir / "subtitles.srt", package_dir / "subtitles_v4_dense.srt"])
    for path in candidates:
        if path.exists():
            return path.resolve()
    return None


def track_count(resolve_audit: dict[str, Any], kind: str, index: int) -> int | None:
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        try:
            if int(row.get("index") or -1) == index:
                return int(row.get("itemCount") or 0)
        except (TypeError, ValueError):
            continue
    return None


def total_track_items(resolve_audit: dict[str, Any], kind: str) -> int:
    total = 0
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        try:
            total += int(row.get("itemCount") or 0)
        except (TypeError, ValueError):
            pass
    return total


def timeline_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds"):
        try:
            return float(clip.get(key))
        except (TypeError, ValueError):
            continue
    return 0.0


def clip_duration(clip: dict[str, Any]) -> float:
    for key in ("durationSeconds", "sourceDurationSeconds"):
        try:
            value = float(clip.get(key))
            if value > 0:
                return value
        except (TypeError, ValueError):
            continue
    try:
        return max(0.0, float(clip.get("sourceEndSeconds") or 0) - float(clip.get("sourceStartSeconds") or 0))
    except (TypeError, ValueError):
        return 0.0


def infer_final_output(package_dir: Path, explicit: str | None) -> Path | None:
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


def ffprobe_duration(path: Path | None) -> float:
    if not path or not path.exists():
        return 0.0
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0.0
    try:
        return float((json.loads(result.stdout).get("format") or {}).get("duration") or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def infer_duration(package_dir: Path, blueprint: dict[str, Any], final_output: Path | None) -> float:
    for report_name in ("render_delivery_verification.json", "FINAL_DELIVERY_REPORT.json"):
        report = load_json(package_dir / report_name) or {}
        for key in ("durationSeconds", "duration"):
            try:
                value = float(report.get(key))
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        probe = report.get("probe") if isinstance(report.get("probe"), dict) else {}
        try:
            value = float(probe.get("durationSeconds") or probe.get("duration") or 0)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    probed = ffprobe_duration(final_output)
    if probed > 0:
        return probed
    for value in (blueprint.get("targetDurationSeconds"), blueprint.get("actualVideoCoverageSeconds")):
        try:
            duration = float(value)
            if duration > 0:
                return duration
        except (TypeError, ValueError):
            pass
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return max((timeline_start(clip) + clip_duration(clip) for clip in clips if isinstance(clip, dict)), default=0.0)


def role_contains(clip: dict[str, Any], tokens: tuple[str, ...]) -> bool:
    text = " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "type", "name")).lower()
    return any(token in text for token in tokens)


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def unique_texts(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalized_text(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def repeated_title_phrase(text: str) -> bool:
    cleaned = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", " ", text).strip().upper()
    if not cleaned:
        return False
    words = cleaned.split()
    if len(words) >= 2 and any(words[index] == words[index + 1] for index in range(len(words) - 1)):
        return True
    if len(words) >= 2 and len(words) % 2 == 0 and words[: len(words) // 2] == words[len(words) // 2 :]:
        return True
    compact = "".join(words)
    if len(compact) >= 4 and len(compact) % 2 == 0 and compact[: len(compact) // 2] == compact[len(compact) // 2 :]:
        return True
    return False


def opening_title_evidence(
    early_clips: list[dict[str, Any]], opening_visuals: list[dict[str, Any]], forbidden_terms: tuple[str, ...]
) -> dict[str, Any]:
    title_clips = [
        clip
        for clip in early_clips
        if clip.get("cityTitle") or clip.get("titleText") or clip.get("title") or role_contains(clip, ("city_title", "opening_city"))
    ]
    clip_values: list[dict[str, Any]] = []
    all_main_values: list[str] = []
    repeated_values: list[str] = []
    mismatched_field_values: list[dict[str, Any]] = []
    subtitle_values: list[str] = []
    for clip in title_clips:
        main_values = unique_texts([clip.get("cityTitle"), clip.get("titleText"), clip.get("title")])
        subtitles = unique_texts([clip.get("subtitle")])
        if len(main_values) > 1:
            mismatched_field_values.append({"sourcePath": clip.get("sourcePath"), "values": main_values})
        for value in main_values:
            if repeated_title_phrase(value):
                repeated_values.append(value)
        all_main_values.extend(main_values)
        subtitle_values.extend(subtitles)
        clip_values.append(
            {
                "role": clip.get("role") or clip.get("purpose"),
                "sourcePath": clip.get("sourcePath"),
                "mainTitleValues": main_values,
                "subtitleValues": subtitles,
            }
        )
    unique_main_values = unique_texts(all_main_values)
    title_text = " ".join(unique_main_values)
    forbidden_hits = [term for term in forbidden_terms if term in title_text.upper()]
    passed = (
        bool(opening_visuals)
        and len(title_clips) == 1
        and len(unique_main_values) == 1
        and not subtitle_values
        and not forbidden_hits
        and not repeated_values
        and not mismatched_field_values
    )
    return {
        "passed": passed,
        "openingVisualCount": len(opening_visuals),
        "openingTitleCount": len(title_clips),
        "openingTitleText": title_text,
        "openingTitleValues": unique_main_values,
        "openingSubtitleValues": subtitle_values,
        "forbiddenTerms": list(forbidden_terms),
        "forbiddenHits": forbidden_hits,
        "repeatedTitleValues": repeated_values,
        "mismatchedFieldValues": mismatched_field_values,
        "titleClips": clip_values,
        "openingPaths": [clip.get("sourcePath") for clip in opening_visuals[:5]],
    }


def path_is_visual_bridge(path: str) -> bool:
    name = Path(path).name.lower()
    parts = {part.lower() for part in Path(path).parts}
    return bool(path) and "title_cards" not in parts and not name.endswith((".png", ".jpg", ".jpeg"))


def chapter_title_bridge_evidence(clips: list[dict[str, Any]], min_chapters: int) -> dict[str, Any]:
    title_clips = []
    slate_sources: list[str] = []
    missing_sources: list[str] = []
    long_texts: list[str] = []
    for clip in clips:
        if not isinstance(clip, dict):
            continue
        role = str(clip.get("role") or clip.get("purpose") or "").lower()
        if "subtitle" in role:
            continue
        if not any(token in role for token in ("chapter_title", "place_card", "title_card")):
            continue
        source = str(clip.get("sourcePath") or "")
        if not source or not Path(source).expanduser().exists():
            missing_sources.append(source)
        if not path_is_visual_bridge(source):
            slate_sources.append(source)
        for key in ("title", "titleText", "cityTitle", "place", "subtitle", "text"):
            text = str(clip.get(key) or "").strip()
            if len(text) > 46:
                long_texts.append(text)
        title_clips.append(clip)
    passed = len(title_clips) >= min_chapters and not slate_sources and not missing_sources and not long_texts
    return {
        "passed": passed,
        "chapterTitleClipCount": len(title_clips),
        "requiredChapterTitleClipCount": min_chapters,
        "slateSources": slate_sources[:20],
        "missingSources": missing_sources[:20],
        "longTexts": long_texts[:20],
        "roles": [clip.get("role") or clip.get("purpose") for clip in title_clips[:20]],
    }


def asset_ledger_summary(package_dir: Path) -> dict[str, Any]:
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    items = ledger.get("items") if isinstance(ledger.get("items"), list) else []
    unresolved = [
        item
        for item in items
        if item.get("type") in {"bgm", "aerial_or_stock", "font"}
        and item.get("licenseStatus") not in {"verified", "verified_original_generated_local", "system-font-render-only"}
    ]
    return {
        "exists": bool(ledger),
        "finalReady": ledger.get("finalReady"),
        "itemCount": len(items),
        "unresolvedCount": len(unresolved),
        "unresolved": unresolved[:10],
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    delivery_plan = load_json(package_dir / "delivery_plan.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or load_json(package_dir / "resolve_readback_audit_v10.json") or {}
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    style_audit_path = infer_visual_audio_audit(package_dir)
    style = load_json(style_audit_path) or {}
    client = load_json(package_dir / "client_delivery_rules_audit.json") or {}
    longform = load_json(package_dir / "longform_delivery_audit.json") or {}
    final_output = infer_final_output(package_dir, args.output)
    duration = infer_duration(package_dir, blueprint, final_output)
    checks: list[dict[str, Any]] = []

    def add(requirement: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
        checks.append(
            {
                "requirement": requirement,
                "status": "passed" if passed else ("warning" if warning else "blocked"),
                "evidence": evidence,
            }
        )

    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    early = [clip for clip in clips if isinstance(clip, dict) and timeline_start(clip) <= args.opening_window_seconds]
    opening_visuals = [
        clip
        for clip in early
        if role_contains(clip, ("opening", "aerial", "establish"))
        and path_is_visual_bridge(str(clip.get("sourcePath") or ""))
    ]
    forbidden_opening_terms = ("TOKYO / OSAKA", "JAPAN 2025", "OSAKA - TOKYO - OSAKA", "OSAKA -> TOKYO -> OSAKA")
    opening_evidence = opening_title_evidence(early, opening_visuals, forbidden_opening_terms)
    add(
        "Opening has one clean city/title moment over real establishing footage",
        opening_evidence["passed"],
        opening_evidence,
    )

    transition_plan = blueprint.get("transitionPlan") if isinstance(blueprint.get("transitionPlan"), list) else []
    bridge_clips = [
        clip
        for clip in clips
        if isinstance(clip, dict)
        and role_contains(clip, ("transition", "bridge", "establish", "aerial"))
        and path_is_visual_bridge(str(clip.get("sourcePath") or ""))
    ]
    add(
        "Day/place changes are supported by visual bridge footage",
        len(transition_plan) >= args.min_transitions and len(bridge_clips) >= args.min_transitions,
        {
            "transitionPlanCount": len(transition_plan),
            "bridgeClipCount": len(bridge_clips),
            "bridgeRoles": [clip.get("role") or clip.get("purpose") for clip in bridge_clips[:12]],
        },
    )

    chapter_title_evidence = chapter_title_bridge_evidence(clips, args.min_transitions)
    add(
        "Chapter title moments use scenic bridge clips with short visible text",
        chapter_title_evidence["passed"],
        chapter_title_evidence,
    )

    tail_start = max(0.0, duration - args.ending_window_seconds)
    tail = [clip for clip in clips if isinstance(clip, dict) and timeline_start(clip) >= tail_start]
    ending_visuals = [
        clip
        for clip in tail
        if role_contains(clip, ("ending", "aerial", "establish"))
        and path_is_visual_bridge(str(clip.get("sourcePath") or ""))
    ]
    add(
        "Ending uses scenic/establishing footage instead of a black or generic slate",
        bool(ending_visuals),
        {"tailStartSeconds": tail_start, "endingVisualCount": len(ending_visuals), "endingPaths": [clip.get("sourcePath") for clip in ending_visuals[:5]]},
    )

    srt_path = find_subtitle_path(package_dir, blueprint)
    cues = parse_srt(srt_path)
    gap_stats = cue_gap_stats(cues, duration)
    cues_per_minute = len(cues) / (duration / 60) if duration > 0 else 0.0
    add(
        "Subtitle/TXT guidance is dense enough for a no-voiceover travel film",
        len(cues) >= args.min_subtitle_cues
        and cues_per_minute >= args.min_cues_per_minute
        and (gap_stats["maxGapSeconds"] is None or float(gap_stats["maxGapSeconds"]) <= args.max_subtitle_gap_seconds),
        {
            "subtitlePath": str(srt_path) if srt_path else None,
            "cueCount": len(cues),
            "cuesPerMinute": round(cues_per_minute, 3),
            "maxGapSeconds": gap_stats["maxGapSeconds"],
            "longGaps": gap_stats["longGaps"][:5],
        },
    )

    overlay_clips = [clip for clip in clips if isinstance(clip, dict) and role_contains(clip, ("subtitle_overlay",))]
    native_subtitle_items = total_track_items(resolve_audit, "subtitle")
    subtitle_policy = blueprint.get("subtitleDeliveryPolicy") if isinstance(blueprint.get("subtitleDeliveryPolicy"), dict) else {}
    rendered_subtitles_ok = bool(overlay_clips) or native_subtitle_items > 0 or subtitle_policy.get("mode") in {"burned_in", "resolve_overlay_video"}
    sidecar_only_ok = not args.require_rendered_subtitles and bool(cues)
    add(
        "Rendered subtitle mode is explicit and verifiable",
        rendered_subtitles_ok,
        {
            "requireRenderedSubtitles": args.require_rendered_subtitles,
            "nativeSubtitleItems": native_subtitle_items,
            "overlayClipCount": len(overlay_clips),
            "subtitleDeliveryPolicy": subtitle_policy,
            "sidecarCueCount": len(cues),
        },
        warning=sidecar_only_ok,
    )

    add(
        "No-voiceover/BGM-led audio policy is reflected in Resolve readback",
        (
            args.audio_mode != "bgm_only"
            or (
                (track_count(resolve_audit, "audio", 1) in {0, None})
                and (track_count(resolve_audit, "audio", 2) in {0, None})
                and (track_count(resolve_audit, "audio", 3) or 0) > 0
                and not (blueprint.get("assets") or {}).get("voiceover")
            )
        ),
        {
            "audioMode": args.audio_mode,
            "a1SourceItems": track_count(resolve_audit, "audio", 1),
            "a2VoiceoverItems": track_count(resolve_audit, "audio", 2),
            "a3BgmItems": track_count(resolve_audit, "audio", 3),
            "voiceoverAsset": (blueprint.get("assets") or {}).get("voiceover") if isinstance(blueprint.get("assets"), dict) else None,
        },
    )

    audio_metrics = style.get("audioMetrics") if isinstance(style.get("audioMetrics"), dict) else {}
    audio_analysis = style.get("audioAnalysis") if isinstance(style.get("audioAnalysis"), dict) else {}
    if not audio_metrics and audio_analysis:
        loudness = audio_analysis.get("loudness") if isinstance(audio_analysis.get("loudness"), dict) else {}
        audio_metrics = {
            **loudness,
            "silenceSeconds": audio_analysis.get("silenceSeconds"),
            "silenceRatio": audio_analysis.get("silenceRatio"),
        }
    integrated = audio_metrics.get("integratedLufs")
    silence_ratio = audio_metrics.get("silenceRatio")
    add(
        "BGM is audible and not mostly silent",
        integrated is not None
        and args.min_integrated_lufs <= float(integrated) <= args.max_integrated_lufs
        and silence_ratio is not None
        and float(silence_ratio) <= args.max_silence_ratio,
        {"audioMetrics": audio_metrics, "styleAuditStatus": style.get("status")},
        warning=not bool(audio_metrics),
    )

    visual_policy = blueprint.get("visualNormalizationPolicy") if isinstance(blueprint.get("visualNormalizationPolicy"), dict) else {}
    pillarbox_failures = [
        sample
        for sample in (style.get("samples") or [])
        if isinstance(sample, dict) and sample.get("pillarboxSuspected")
    ]
    add(
        "Portrait/pillarbox regressions are blocked or explicitly normalized",
        visual_policy.get("status") in {"ready", "applied_v10", "applied"} and not pillarbox_failures,
        {"visualNormalizationPolicy": visual_policy, "pillarboxFailures": pillarbox_failures[:5], "styleAuditStatus": style.get("status")},
    )

    ledger = asset_ledger_summary(package_dir)
    add(
        "BGM, aerial/stock, and fonts have traceable asset evidence",
        ledger["exists"] and ledger["finalReady"] is True and ledger["unresolvedCount"] == 0,
        ledger,
        warning=args.asset_license_warning_only,
    )

    render_status_ok = render.get("status") == "passed"
    style_ok = style.get("status") == "passed"
    client_ok = client.get("status") in {"passed", "passed_with_warnings"}
    longform_status = longform.get("status")
    longform_ok = not longform_status or longform_status in {"passed", "passed_with_caveats", "passed_with_warnings"}
    add(
        "Final render passed technical, visual/audio, and client-rule audits",
        render_status_ok and style_ok and client_ok and longform_ok,
        {
            "renderStatus": render.get("status"),
            "styleStatus": style.get("status"),
            "clientStatus": client.get("status"),
            "longformStatus": longform_status,
            "longformWarnings": longform.get("warnings"),
            "styleAudit": str(style_audit_path) if style_audit_path else None,
        },
    )

    main_clips = [clip for clip in clips if isinstance(clip, dict) and role_contains(clip, ("main_footage",))]
    durations = [clip_duration(clip) for clip in main_clips if clip_duration(clip) > 0]
    avg_shot = sum(durations) / len(durations) if durations else 0.0
    add(
        "Timeline pacing has enough varied main footage for long-form travel rhythm",
        len(main_clips) >= args.min_main_clips and args.min_avg_shot_seconds <= avg_shot <= args.max_avg_shot_seconds,
        {"mainClipCount": len(main_clips), "averageMainClipSeconds": round(avg_shot, 3), "durationSeconds": duration},
        warning=True,
    )

    blocked = [row for row in checks if row["status"] == "blocked"]
    warnings = [row for row in checks if row["status"] == "warning"]
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked" if blocked else ("passed_with_warnings" if warnings else "passed"),
        "packageDir": str(package_dir),
        "finalOutput": str(final_output) if final_output else None,
        "durationSeconds": round(duration, 3),
        "checks": checks,
        "blockers": [row["requirement"] for row in blocked],
        "warnings": [row["requirement"] for row in warnings],
        "summary": {
            "passed": len([row for row in checks if row["status"] == "passed"]),
            "blocked": len(blocked),
            "warnings": len(warnings),
        },
        "routeCaveat": "Non-GPS visual route reconstruction remains a caveat unless per-clip geolocation is separately verified.",
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Story Style Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Final output: `{report.get('finalOutput')}`",
        f"Duration seconds: `{report.get('durationSeconds')}`",
        "",
        "## Summary",
        f"- Passed: `{report['summary']['passed']}`",
        f"- Blocked: `{report['summary']['blocked']}`",
        f"- Warnings: `{report['summary']['warnings']}`",
        "",
        "## Checks",
    ]
    for row in report["checks"]:
        evidence = json.dumps(row["evidence"], ensure_ascii=False)[:2000]
        lines.extend(["", f"### {row['requirement']}", f"- Status: `{row['status']}`", f"- Evidence: `{evidence}`"])
    if report.get("routeCaveat"):
        lines.extend(["", "## Caveat", report["routeCaveat"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit story/style readiness for a DaVinci travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output", help="Final render path.")
    parser.add_argument("--audio-mode", choices=["bgm_only", "preserve_source"], default="bgm_only")
    parser.add_argument("--require-rendered-subtitles", action="store_true")
    parser.add_argument("--min-subtitle-cues", type=int, default=55)
    parser.add_argument("--min-cues-per-minute", type=float, default=2.5)
    parser.add_argument("--max-subtitle-gap-seconds", type=float, default=75.0)
    parser.add_argument("--min-transitions", type=int, default=4)
    parser.add_argument("--opening-window-seconds", type=float, default=12.0)
    parser.add_argument("--ending-window-seconds", type=float, default=18.0)
    parser.add_argument("--min-integrated-lufs", type=float, default=-24.0)
    parser.add_argument("--max-integrated-lufs", type=float, default=-12.0)
    parser.add_argument("--max-silence-ratio", type=float, default=0.15)
    parser.add_argument("--asset-license-warning-only", action="store_true")
    parser.add_argument("--min-main-clips", type=int, default=35)
    parser.add_argument("--min-avg-shot-seconds", type=float, default=4.0)
    parser.add_argument("--max-avg-shot-seconds", type=float, default=40.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    json_path = package_dir / "story_style_contract_audit.json"
    md_path = package_dir / "story_style_contract_audit.md"
    write_json(json_path, report)
    write_markdown(md_path, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Story style contract audit: {report['status']}")
        print(f"Report: {md_path}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
        for warning in report.get("warnings") or []:
            print(f"WARNING: {warning}")
    return 0 if report["status"] in {"passed", "passed_with_warnings"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
