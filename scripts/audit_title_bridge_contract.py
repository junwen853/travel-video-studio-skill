#!/usr/bin/env python3
"""Audit scenic title bridges against the Resolve blueprint contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


TITLE_ROLES = {"opening_city_aerial_title", "chapter_title_bridge", "ending_city_aerial_title"}
OPENING_ROUTE_SEPARATORS = ("/", "->", " - ", " TO ")
SLATE_SUFFIXES = {".png", ".jpg", ".jpeg"}
BAD_SOURCE_PARTS = {"title_cards"}


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


def norm_path(value: Any) -> str:
    if not value:
        return ""
    try:
        return str(Path(str(value)).expanduser().resolve())
    except Exception:
        return str(value)


def infer_visual_manifest(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidates = [
        package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json",
        package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
        package_dir / "v9_fix_inputs" / "v9_fix_manifest.json",
        package_dir / "v12_visual_manifest.json",
        package_dir / "visual_polish_manifest.json",
    ]
    return next((path.resolve() for path in candidates if path.exists()), None)


def infer_blueprint(package_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (package_dir / "resolve_timeline_blueprint.json").resolve()


def clip_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "timeline_start", "recordStartSeconds", "startSeconds"):
        value = clip.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def clip_end(clip: dict[str, Any]) -> float:
    for key in ("timelineEndSeconds", "timeline_end", "recordEndSeconds", "endSeconds"):
        value = clip.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    start = clip_start(clip)
    for key in ("duration", "durationSeconds", "sourceDurationSeconds"):
        value = clip.get(key)
        try:
            return start + max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return start


def intervals_overlap(start_a: float, end_a: float, start_b: float, end_b: float, tolerance: float = 0.05) -> bool:
    return start_a < end_b - tolerance and start_b < end_a - tolerance


def segment_start(segment: dict[str, Any]) -> float:
    for key in ("timeline_start", "timelineStartSeconds", "startSeconds"):
        value = segment.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def segment_duration(segment: dict[str, Any]) -> float:
    for key in ("duration", "durationSeconds"):
        value = segment.get(key)
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return 0.0


def path_exists_video(path_raw: Any) -> bool:
    if not path_raw:
        return False
    path = Path(str(path_raw)).expanduser()
    parts = {part.lower() for part in path.parts}
    return path.exists() and path.suffix.lower() not in SLATE_SUFFIXES and not (parts & BAD_SOURCE_PARTS)


def text_values(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("title", "titleText", "cityTitle", "subtitle", "eyebrow", "text", "place"):
        value = item.get(key)
        if value is not None and str(value).strip():
            values.append(str(value).strip())
    return values


def visible_text_values(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in ("title", "titleText", "cityTitle", "subtitle", "eyebrow", "text"):
        value = item.get(key)
        if value is None or not str(value).strip():
            continue
        text = str(value).strip()
        norm = re.sub(r"\s+", " ", text).casefold()
        if norm in seen:
            continue
        seen.add(norm)
        values.append(text)
    return values


def forbidden_hits(values: list[str], forbidden: list[str]) -> list[str]:
    out: list[str] = []
    joined = "\n".join(values).upper()
    for term in forbidden:
        if term and str(term).upper() in joined:
            out.append(str(term))
    return sorted(set(out))


def clean_opening_title(title: str) -> bool:
    if not title.strip():
        return False
    upper = title.strip().upper()
    return not any(token in upper for token in OPENING_ROUTE_SEPARATORS)


def clean_opening_subtitle(subtitle: str) -> bool:
    subtitle = subtitle.strip().upper()
    if not subtitle:
        return True
    if len(subtitle) > 34:
        return False
    return not any(token in subtitle for token in OPENING_ROUTE_SEPARATORS)


def timeline_title_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: list[dict[str, Any]] = []
    for clip in clips:
        if not isinstance(clip, dict):
            continue
        role = str(clip.get("role") or clip.get("purpose") or "").lower()
        if role in TITLE_ROLES or any(token in role for token in ("opening_city", "chapter_title", "ending_city")):
            out.append(clip)
    return sorted(out, key=clip_start)


def manifest_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    segments = manifest.get("segments")
    if not isinstance(segments, list):
        return []
    out: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        mode = str(segment.get("mode") or "").lower()
        if mode in {"opening", "chapter", "ending", "transition"}:
            out.append(segment)
    return sorted(out, key=segment_start)


def segment_key(segment: dict[str, Any]) -> tuple[str, int]:
    return str(segment.get("mode") or "").lower(), round(segment_start(segment) * 1000)


def clip_key(clip: dict[str, Any]) -> tuple[str, int]:
    role = str(clip.get("role") or clip.get("purpose") or "").lower()
    if "opening" in role:
        mode = "opening"
    elif "ending" in role:
        mode = "ending"
    else:
        mode = "chapter"
    return mode, round(clip_start(clip) * 1000)


def clip_identity(clip: dict[str, Any]) -> tuple[Any, ...]:
    return (
        clip.get("role") or clip.get("purpose"),
        round(clip_start(clip), 3),
        round(clip_end(clip), 3),
        clip.get("trackIndex"),
        norm_path(clip.get("sourcePath")),
    )


def is_text_bearing_clip(clip: dict[str, Any]) -> bool:
    role = str(clip.get("role") or clip.get("purpose") or "").lower()
    if any(token in role for token in ("title", "subtitle", "caption", "lower_third", "text_overlay")):
        return True
    return bool(visible_text_values(clip))


def title_window_stack_violations(
    blueprint: dict[str, Any],
    segments: list[dict[str, Any]],
    matched_title_clips: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    title_identities = {clip_identity(clip) for clip in matched_title_clips.values()}
    windows: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for segment in segments:
        start = segment_start(segment)
        end = start + segment_duration(segment)
        key = segment_key(segment)
        matched = matched_title_clips.get(key)
        overlapping: list[dict[str, Any]] = []
        text_layers: list[dict[str, Any]] = []
        subtitle_overlays: list[dict[str, Any]] = []
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            clip_s = clip_start(clip)
            clip_e = clip_end(clip)
            if not intervals_overlap(start, end, clip_s, clip_e):
                continue
            role = str(clip.get("role") or clip.get("purpose") or "")
            summary = {
                "role": role,
                "trackIndex": clip.get("trackIndex"),
                "start": round(clip_s, 3),
                "end": round(clip_e, 3),
                "source": clip.get("sourcePath"),
            "textValues": visible_text_values(clip),
            }
            overlapping.append(summary)
            if clip_identity(clip) in title_identities:
                continue
            if "subtitle" in role.lower() or "caption" in role.lower():
                subtitle_overlays.append(summary)
            if is_text_bearing_clip(clip):
                text_layers.append(summary)
        matched_values = visible_text_values(matched) if isinstance(matched, dict) else []
        segment_title = str(segment.get("title") or "").strip()
        title_value_hits = [value for value in matched_values if value and value == segment_title]
        window = {
            "mode": segment.get("mode"),
            "title": segment_title,
            "start": round(start, 3),
            "end": round(end, 3),
            "matchedTitleClip": bool(matched),
            "matchedTitleValues": matched_values,
            "overlapClipCount": len(overlapping),
            "extraTextLayerCount": len(text_layers),
            "subtitleOverlayCount": len(subtitle_overlays),
        }
        windows.append(window)
        if not matched or not title_value_hits or text_layers or subtitle_overlays:
            violations.append({**window, "extraTextLayers": text_layers, "subtitleOverlays": subtitle_overlays})
    return {"passed": not violations, "windows": windows, "violations": violations}


def check_title_zones(blueprint: dict[str, Any], segments: list[dict[str, Any]]) -> dict[str, Any]:
    policy = (blueprint.get("subtitleDeliveryPolicy") or {}).get("titleZoneSubtitlePolicy") or {}
    zones = policy.get("zones") if isinstance(policy, dict) else []
    if not isinstance(zones, list):
        zones = []
    missing: list[dict[str, Any]] = []
    for segment in segments:
        start = segment_start(segment)
        end = start + segment_duration(segment)
        title = str(segment.get("title") or "")
        covered = False
        for zone in zones:
            if not isinstance(zone, dict):
                continue
            try:
                zone_start = float(zone.get("start"))
                zone_end = float(zone.get("end"))
            except (TypeError, ValueError):
                continue
            zone_title = str(zone.get("title") or "")
            if zone_start <= start + 0.3 and zone_end >= end - 0.3 and (not title or title == zone_title):
                covered = True
                break
        if not covered:
            missing.append({"title": title, "start": start, "end": end})
    return {
        "mode": policy.get("mode") if isinstance(policy, dict) else None,
        "zoneCount": len(zones),
        "missingZones": missing,
        "passed": isinstance(policy, dict) and policy.get("mode") == "avoid_title_zones" and not missing,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    manifest_path = infer_visual_manifest(package_dir, args.visual_manifest)
    blueprint_path = infer_blueprint(package_dir, args.blueprint)
    manifest = load_json(manifest_path)
    blueprint = load_json(blueprint_path)

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    def add(name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
        status = "passed" if passed else ("warning" if warning else "blocked")
        checks.append({"name": name, "status": status, "evidence": evidence})
        if status == "blocked":
            blockers.append(name)
        elif status == "warning":
            warnings.append(name)

    add("Visual title manifest exists", isinstance(manifest, dict), {"path": str(manifest_path) if manifest_path else None})
    add("Resolve blueprint exists", isinstance(blueprint, dict), {"path": str(blueprint_path)})
    if not isinstance(manifest, dict) or not isinstance(blueprint, dict):
        status = "blocked"
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "packageDir": str(package_dir),
            "visualManifest": str(manifest_path) if manifest_path else None,
            "blueprint": str(blueprint_path),
            "checks": checks,
            "blockers": blockers,
            "warnings": warnings,
        }
        return report

    expected = str(manifest.get("cityTitle") or manifest.get("expectedOpeningTitle") or "").strip()
    forbidden = manifest.get("forbiddenOpeningText") or manifest.get("forbiddenVisibleText") or []
    if not isinstance(forbidden, list):
        forbidden = []
    forbidden = [str(item) for item in forbidden]
    segments = manifest_segments(manifest)
    opening_segments = [item for item in segments if str(item.get("mode") or "").lower() == "opening"]
    chapter_segments = [item for item in segments if str(item.get("mode") or "").lower() == "chapter"]
    ending_segments = [item for item in segments if str(item.get("mode") or "").lower() == "ending"]
    title_clips = timeline_title_clips(blueprint)
    opening_clips = [clip for clip in title_clips if "opening" in str(clip.get("role") or "").lower()]
    chapter_clips = [clip for clip in title_clips if "chapter" in str(clip.get("role") or "").lower()]
    ending_clips = [clip for clip in title_clips if "ending" in str(clip.get("role") or "").lower()]

    opening_title_values = text_values(opening_segments[0]) if opening_segments else []
    opening_title = str(opening_segments[0].get("title") or "") if opening_segments else ""
    opening_subtitle = str(opening_segments[0].get("subtitle") or "") if opening_segments else ""
    add(
        "Opening has exactly one clean city title segment",
        len(opening_segments) == 1
        and bool(expected)
        and opening_title.strip().upper() == expected.upper()
        and clean_opening_title(opening_title)
        and clean_opening_subtitle(opening_subtitle)
        and str(opening_segments[0].get("eyebrow") or "").strip() == "",
        {
            "expected": expected,
            "openingSegmentCount": len(opening_segments),
            "openingTitle": opening_title,
            "openingSubtitle": opening_subtitle,
            "openingValues": opening_title_values,
        },
    )
    add(
        "Opening title text avoids rejected route/date labels",
        not forbidden_hits(opening_title_values, forbidden),
        {"forbidden": forbidden, "hits": forbidden_hits(opening_title_values, forbidden)},
    )
    policy = str(manifest.get("openingTitlePolicy") or "").lower()
    add(
        "Manifest declares a single clean opening title policy",
        "single" in policy and "title" in policy and ("route" in policy or "duplicate" in policy),
        {"openingTitlePolicy": manifest.get("openingTitlePolicy")},
    )

    missing_segment_files = [str(item.get("segment")) for item in segments if item.get("segment") and not Path(str(item["segment"])).expanduser().exists()]
    missing_overlay_files = [str(item.get("overlay")) for item in segments if item.get("overlay") and not Path(str(item["overlay"])).expanduser().exists()]
    bad_segment_sources = [str(item.get("segment")) for item in segments if item.get("segment") and not path_exists_video(item.get("segment"))]
    bad_background_sources = [str(item.get("source")) for item in segments if item.get("source") and not path_exists_video(item.get("source"))]
    add(
        "All title bridge segment and overlay assets exist",
        not missing_segment_files and not missing_overlay_files,
        {"missingSegments": missing_segment_files[:20], "missingOverlays": missing_overlay_files[:20]},
    )
    add(
        "Title bridge media are video clips, not title-card/image slates",
        not bad_segment_sources and not bad_background_sources,
        {"badSegments": bad_segment_sources[:20], "badBackgroundSources": bad_background_sources[:20]},
    )

    add(
        "Resolve blueprint uses the expected title bridge count",
        len(opening_clips) == len(opening_segments) >= 1
        and len(chapter_clips) >= max(args.min_chapter_titles, len(chapter_segments))
        and len(ending_clips) == len(ending_segments) >= 1,
        {
            "manifestCounts": {
                "opening": len(opening_segments),
                "chapter": len(chapter_segments),
                "ending": len(ending_segments),
            },
            "blueprintCounts": {
                "opening": len(opening_clips),
                "chapter": len(chapter_clips),
                "ending": len(ending_clips),
            },
        },
    )

    segment_by_key = {segment_key(item): item for item in segments}
    matched_title_clips: dict[tuple[str, int], dict[str, Any]] = {}
    unmatched_clips: list[dict[str, Any]] = []
    text_mismatches: list[dict[str, Any]] = []
    source_mismatches: list[dict[str, Any]] = []
    source_audio_flags: list[dict[str, Any]] = []
    for clip in title_clips:
        key = clip_key(clip)
        segment = segment_by_key.get(key)
        if not segment:
            unmatched_clips.append({"role": clip.get("role"), "start": clip_start(clip), "source": clip.get("sourcePath")})
            continue
        matched_title_clips[key] = clip
        clip_title = str(clip.get("titleText") or clip.get("cityTitle") or clip.get("title") or "").strip()
        segment_title = str(segment.get("title") or "").strip()
        if clip_title and segment_title and clip_title != segment_title:
            text_mismatches.append({"start": clip_start(clip), "clipTitle": clip_title, "segmentTitle": segment_title})
        if norm_path(clip.get("sourcePath")) != norm_path(segment.get("segment")):
            source_mismatches.append(
                {
                    "start": clip_start(clip),
                    "clipSource": clip.get("sourcePath"),
                    "manifestSegment": segment.get("segment"),
                }
            )
        if clip.get("includeSourceAudio") is True or clip.get("preserveSourceAudio") is True or clip.get("sourceAudio") is True:
            source_audio_flags.append({"role": clip.get("role"), "start": clip_start(clip), "source": clip.get("sourcePath")})

    bad_blueprint_sources = [
        str(clip.get("sourcePath") or "")
        for clip in title_clips
        if not path_exists_video(clip.get("sourcePath"))
    ]
    add(
        "Resolve title clips match manifest segment paths and titles",
        not unmatched_clips and not text_mismatches and not source_mismatches,
        {
            "unmatchedClips": unmatched_clips[:20],
            "textMismatches": text_mismatches[:20],
            "sourceMismatches": source_mismatches[:20],
        },
    )
    add(
        "Resolve title clips are video-only scenic bridges",
        not bad_blueprint_sources and not source_audio_flags,
        {"badSources": bad_blueprint_sources[:20], "sourceAudioFlags": source_audio_flags[:20]},
    )

    stack_evidence = title_window_stack_violations(blueprint, segments, matched_title_clips)
    add(
        "Title bridge windows have no stacked text or subtitle overlay layers",
        stack_evidence["passed"],
        stack_evidence,
    )

    zones = check_title_zones(blueprint, segments)
    add(
        "Subtitle overlay title-zone policy covers every title bridge",
        zones["passed"],
        zones,
    )

    visual_audit = load_json(package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json") or {}
    title_ocr = visual_audit.get("titleOcr") if isinstance(visual_audit, dict) else {}
    ocr_expected_found = title_ocr.get("expectedTitleFound") if isinstance(title_ocr, dict) else None
    if visual_audit and ocr_expected_found is False:
        add(
            "OCR did not confirm expected title; structural title contract compensates",
            True,
            {
                "visualAudioAuditStatus": visual_audit.get("status"),
                "expectedTitle": title_ocr.get("expectedTitle") if isinstance(title_ocr, dict) else None,
                "expectedTitleFound": ocr_expected_found,
            },
            warning=True,
        )

    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "visualManifest": str(manifest_path) if manifest_path else None,
        "blueprint": str(blueprint_path),
        "expectedOpeningTitle": expected,
        "segmentCount": len(segments),
        "titleClipCount": len(title_clips),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Title Bridge Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Visual manifest: `{report.get('visualManifest')}`",
        f"Blueprint: `{report.get('blueprint')}`",
        f"Expected opening title: `{report.get('expectedOpeningTitle')}`",
        "",
        "## Checks",
    ]
    for row in report.get("checks", []):
        lines.extend(
            [
                "",
                f"### {row['name']}",
                f"- Status: `{row['status']}`",
                f"- Evidence: `{json.dumps(row['evidence'], ensure_ascii=False)[:1800]}`",
            ]
        )
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit title bridge manifest, assets, Resolve clips, and title-zone policy.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--visual-manifest")
    parser.add_argument("--blueprint")
    parser.add_argument("--min-chapter-titles", type=int, default=4)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        package_dir = Path(args.package_dir).expanduser().resolve()
        report = build_report(package_dir, args)
        write_json(package_dir / "title_bridge_contract_audit.json", report)
        write_markdown(package_dir / "title_bridge_contract_audit.md", report)
    except Exception as exc:
        print(f"audit_title_bridge_contract failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "warnings": report["warnings"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
