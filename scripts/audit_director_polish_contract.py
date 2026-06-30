#!/usr/bin/env python3
"""Audit director-level travel-film polish across assets, timeline, and QA evidence."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED = {"passed", "passed_with_warnings", "passed_with_caveats"}
MOOD_TERMS = (
    "serene",
    "travel",
    "chillout",
    "ambient",
    "atmospheric",
    "cinematic",
    "piano",
    "soft",
    "warm",
    "gentle",
    "reflective",
    "hopeful",
    "film score",
    "electronica",
)
FORBIDDEN_TITLE_TERMS = (
    "JAPAN 2025",
    "TOKYO / OSAKA",
    "OSAKA - TOKYO - OSAKA",
    "OSAKA -> TOKYO -> OSAKA",
    "TITLE_CARD",
    "PLACE_CARD",
    "UNTITLED",
    "PLACEHOLDER",
)
SLATE_SUFFIXES = {".png", ".jpg", ".jpeg"}


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


def resolve_path(value: Any) -> Path | None:
    if not value:
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except Exception:
        return None


def status(report: Any) -> str | None:
    return report.get("status") if isinstance(report, dict) else None


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else ("warning" if warning else "blocked"),
            "evidence": evidence,
        }
    )


def report_check(name: str, report: Any, accepted: set[str] = PASSED) -> dict[str, Any]:
    report_status = status(report)
    return {"name": name, "status": report_status, "passed": report_status in accepted}


def cue_count(path: Path | None) -> int:
    if not path or not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    return sum(1 for block in re.split(r"\n\s*\n", text.strip()) if "-->" in block)


def track_count(resolve_audit: dict[str, Any], kind: str, index: int) -> int | None:
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        try:
            if int(row.get("index")) == index:
                return int(row.get("itemCount") or 0)
        except (TypeError, ValueError):
            continue
    return None


def title_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in manifest.get("segments") or [] if isinstance(row, dict)]


def asset_items(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "rows", "assets"):
        value = ledger.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def ledger_item(items: list[dict[str, Any]], item_type: str) -> dict[str, Any] | None:
    for item in items:
        if str(item.get("type") or "").lower() == item_type:
            return item
    return None


def path_exists(path_raw: Any) -> bool:
    path = resolve_path(path_raw)
    return bool(path and path.exists())


def title_text_clean(text: str) -> bool:
    upper = text.upper()
    return bool(text.strip()) and not any(term in upper for term in FORBIDDEN_TITLE_TERMS)


def title_source_is_video(source_raw: Any) -> bool:
    path = resolve_path(source_raw)
    if not path or not path.exists():
        return False
    lower_parts = {part.lower() for part in path.parts}
    return path.suffix.lower() not in SLATE_SUFFIXES and "title_cards" not in lower_parts


def stock_backlog(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in blueprint.get("stockInsertPlan") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").lower() in {"ready", "applied", "verified"}:
            continue
        out.append(
            {
                "chapterIndex": item.get("chapterIndex"),
                "target": item.get("target"),
                "status": item.get("status"),
                "licenseStatus": item.get("licenseStatus"),
            }
        )
    return out


def stock_closure_passed(report: dict[str, Any], backlog_count: int) -> bool:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    try:
        return (
            report.get("status") == "passed"
            and int(summary.get("unresolvedPlaceholderCount") or 0) == 0
            and int(summary.get("closedPlaceholderCount") or 0) >= backlog_count
        )
    except (TypeError, ValueError):
        return False


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    manifest_path = resolve_path((blueprint.get("scenicTitleBridgePolicy") or {}).get("manifest")) or (
        package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json"
    )
    title_manifest = load_json(manifest_path) or {}
    bgm_manifest_path = resolve_path((blueprint.get("assets") or {}).get("bgmManifest")) or (package_dir / "bgm" / "v9_bgm_manifest.json")
    bgm_manifest = load_json(bgm_manifest_path) or {}
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    visual_audio = load_json(package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json") or {}
    stock_closure = load_json(package_dir / "stock_aerial_closure_audit.json") or {}
    upstream = {
        "render_delivery_verification": render,
        "client_delivery_rules_audit": load_json(package_dir / "client_delivery_rules_audit.json") or {},
        "story_style_contract_audit": load_json(package_dir / "story_style_contract_audit.json") or {},
        "reference_style_alignment_audit": load_json(package_dir / "reference_style_alignment_audit.json") or {},
        "director_intent_contract_audit": load_json(package_dir / "director_intent_contract_audit.json") or {},
        "route_texture_contract_audit": load_json(package_dir / "route_texture_contract_audit.json") or {},
        "title_bridge_contract_audit": load_json(package_dir / "title_bridge_contract_audit.json") or {},
        "bgm_audio_contract_audit": load_json(package_dir / "bgm_audio_contract_audit.json") or {},
        "visual_audio_style_audit": visual_audio,
    }
    segments = title_segments(title_manifest)
    opening = next((row for row in segments if str(row.get("mode") or "").lower() == "opening"), None)
    ending = next((row for row in segments if str(row.get("mode") or "").lower() == "ending"), None)
    chapters = [row for row in segments if str(row.get("mode") or "").lower() == "chapter"]
    items = asset_items(ledger)
    bgm_item = ledger_item(items, "bgm")
    aerial_item = ledger_item(items, "aerial_or_stock")
    font_item = ledger_item(items, "font")

    subtitle_policy = blueprint.get("subtitleDeliveryPolicy") if isinstance(blueprint.get("subtitleDeliveryPolicy"), dict) else {}
    title_zone = subtitle_policy.get("titleZoneSubtitlePolicy") if isinstance(subtitle_policy.get("titleZoneSubtitlePolicy"), dict) else {}
    subtitle_path = resolve_path((blueprint.get("assets") or {}).get("subtitles")) or (package_dir / "subtitles.srt")
    effect_plan = blueprint.get("effectPlan") if isinstance(blueprint.get("effectPlan"), list) else []
    audio_plan = blueprint.get("audioPlan") if isinstance(blueprint.get("audioPlan"), dict) else {}
    bgm_cues = audio_plan.get("bgmCues") if isinstance(audio_plan.get("bgmCues"), list) else []
    bgm_text = " ".join(
        [str((cue or {}).get("mood") or "") for cue in bgm_cues if isinstance(cue, dict)]
        + [str(track.get("genre") or "") + " " + str(track.get("name") or "") for track in bgm_manifest.get("tracks") or [] if isinstance(track, dict)]
    ).lower()
    backlog = stock_backlog(blueprint)
    closure_ok = stock_closure_passed(stock_closure, len(backlog))
    render_video = render.get("video") if isinstance(render.get("video"), dict) else {}
    checks: list[dict[str, Any]] = []

    upstream_statuses = [report_check(name, report) for name, report in upstream.items()]
    add_check(
        checks,
        "Upstream technical, story, route, title, BGM, and visual audits support polish claim",
        all(row["passed"] for row in upstream_statuses),
        {"upstreamStatuses": upstream_statuses},
    )
    add_check(
        checks,
        "Opening uses a clean city title over verified aerial or establishing footage",
        bool(opening)
        and title_text_clean(str(opening.get("title") or ""))
        and not str(opening.get("subtitle") or "").strip()
        and not str(opening.get("eyebrow") or "").strip()
        and title_source_is_video(opening.get("source"))
        and path_exists(opening.get("segment"))
        and path_exists(opening.get("overlay"))
        and bool(aerial_item and str(aerial_item.get("licenseStatus") or "").lower() == "verified" and path_exists(aerial_item.get("localPath"))),
        {
            "opening": opening,
            "aerialLedgerItem": aerial_item,
            "manifestPolicy": title_manifest.get("openingTitlePolicy"),
            "font": title_manifest.get("font"),
        },
    )
    add_check(
        checks,
        "Chapter and ending typography are restrained and structurally title-safe",
        len(chapters) >= args.min_chapter_titles
        and bool(ending and title_text_clean(str(ending.get("title") or "")))
        and all(title_text_clean(str(row.get("title") or "")) and path_exists(row.get("segment")) and path_exists(row.get("overlay")) for row in chapters)
        and title_zone.get("mode") == "avoid_title_zones"
        and len(title_zone.get("zones") or []) >= len(segments)
        and bool(font_item and str(font_item.get("licenseStatus") or "").lower() in {"verified", "system-font-render-only"} and path_exists(font_item.get("localPath"))),
        {
            "chapterTitleCount": len(chapters),
            "ending": ending,
            "titleZonePolicy": title_zone,
            "fontLedgerItem": font_item,
        },
    )
    add_check(
        checks,
        "BGM mood, license, and Resolve mix are travel-film appropriate",
        bool(bgm_manifest_path and bgm_manifest_path.exists())
        and bgm_manifest.get("mode") == "bgm_only_no_camera_voice"
        and len(bgm_manifest.get("tracks") or []) >= args.min_bgm_tracks
        and any(term in bgm_text for term in MOOD_TERMS)
        and bool(bgm_item and str(bgm_item.get("licenseStatus") or "").lower() == "verified" and path_exists(bgm_item.get("localPath")))
        and track_count(resolve_audit, "audio", 3) == 1
        and (track_count(resolve_audit, "audio", 1) or 0) == 0
        and (track_count(resolve_audit, "audio", 2) or 0) == 0,
        {
            "bgmManifest": str(bgm_manifest_path) if bgm_manifest_path else None,
            "bgmMode": bgm_manifest.get("mode"),
            "bgmTracks": bgm_manifest.get("tracks"),
            "audioTracks": {
                "A1": track_count(resolve_audit, "audio", 1),
                "A2": track_count(resolve_audit, "audio", 2),
                "A3": track_count(resolve_audit, "audio", 3),
            },
            "bgmLedgerItem": bgm_item,
        },
    )
    add_check(
        checks,
        "Effect plan exists and stays restrained instead of template-heavy",
        len(effect_plan) >= args.min_effects
        and any(str(row.get("name") or "").lower() == "opening_title_reveal" for row in effect_plan)
        and any("bridge" in str(row.get("name") or "").lower() for row in effect_plan)
        and all(str(row.get("intensity") or "").lower() in {"restrained", "subtle", "low", "gentle"} for row in effect_plan),
        {"effectPlan": effect_plan},
    )
    add_check(
        checks,
        "Dense subtitles are rendered without invading title zones",
        subtitle_policy.get("mode") == "resolve_overlay_video"
        and int(subtitle_policy.get("renderedCueCount") or 0) >= args.min_rendered_subtitles
        and cue_count(subtitle_path) >= args.min_subtitle_cues
        and track_count(resolve_audit, "video", 3) is not None
        and (track_count(resolve_audit, "video", 3) or 0) >= args.min_rendered_subtitles
        and title_zone.get("mode") == "avoid_title_zones",
        {
            "subtitlePolicy": subtitle_policy,
            "subtitlePath": str(subtitle_path) if subtitle_path else None,
            "srtCueCount": cue_count(subtitle_path),
            "V3OverlayCount": track_count(resolve_audit, "video", 3),
        },
    )
    add_check(
        checks,
        "Final render quality supports a premium long-form master",
        render.get("status") == "passed"
        and int(render_video.get("width") or 0) >= 3840
        and int(render_video.get("height") or 0) >= 2160
        and float(render_video.get("frameRateValue") or 0) >= args.min_fps
        and float(render_video.get("bitrateMbps") or 0) >= args.min_video_bitrate_mbps
        and float(render.get("durationSeconds") or 0) >= args.min_duration_seconds,
        {
            "renderStatus": render.get("status"),
            "video": render_video,
            "durationSeconds": render.get("durationSeconds"),
        },
    )
    add_check(
        checks,
        "No final title or V2 polish media depends on black slates, image cards, or placeholders",
        all(title_source_is_video(row.get("segment")) and "placeholder" not in str(row).lower() for row in segments),
        {"segmentCount": len(segments), "segments": segments},
    )
    add_check(
        checks,
        "Stock/aerial search placeholders are materialized or explicitly closed",
        not backlog or closure_ok,
        {
            "stockInsertBacklogCount": len(backlog),
            "backlogSample": backlog[:12],
            "stockAerialClosureStatus": stock_closure.get("status"),
            "stockAerialClosureSummary": stock_closure.get("summary"),
        },
        warning=True,
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings = [row["name"] for row in checks if row["status"] == "warning"]
    status_value = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status_value,
        "packageDir": str(package_dir),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "upstreamPassed": sum(1 for row in upstream_statuses if row["passed"]),
            "upstreamTotal": len(upstream_statuses),
            "titleSegmentCount": len(segments),
            "chapterTitleCount": len(chapters),
            "bgmTrackCount": len(bgm_manifest.get("tracks") or []),
            "effectPlanCount": len(effect_plan),
            "renderedSubtitleCount": int(subtitle_policy.get("renderedCueCount") or 0),
            "stockInsertBacklogCount": len(backlog),
            "stockAerialClosureStatus": stock_closure.get("status"),
        },
        "contract": {
            "purpose": "Prove the edit has director-level polish instead of only passing isolated technical checks.",
            "mustProve": [
                "premium aerial or establishing opening with one clean city title",
                "traceable font/BGM/aerial asset evidence",
                "travel-appropriate BGM mood and no source/user voice leakage",
                "restrained transition/title effects instead of template-heavy gimmicks",
                "dense rendered subtitles with title-zone separation",
                "4K high-frame-rate/high-bitrate Resolve master",
            ],
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Director Polish Contract Audit",
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
        "## Checks",
    ]
    for row in report["checks"]:
        evidence = json.dumps(row["evidence"], ensure_ascii=False)[:2400]
        lines.extend(["", f"### {row['name']}", f"- Status: `{row['status']}`", f"- Evidence: `{evidence}`"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Contract", "", "```json", json.dumps(report["contract"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit director-level polish for a Travel Video Studio delivery package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-chapter-titles", type=int, default=5)
    parser.add_argument("--min-bgm-tracks", type=int, default=3)
    parser.add_argument("--min-effects", type=int, default=2)
    parser.add_argument("--min-rendered-subtitles", type=int, default=80)
    parser.add_argument("--min-subtitle-cues", type=int, default=80)
    parser.add_argument("--min-duration-seconds", type=float, default=18 * 60)
    parser.add_argument("--min-fps", type=float, default=50.0)
    parser.add_argument("--min-video-bitrate-mbps", type=float, default=60.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        package_dir = Path(args.package_dir)
        report = build_report(package_dir, args)
    except Exception as exc:
        print(f"audit_director_polish_contract failed: {exc}")
        return 1
    package_dir = Path(args.package_dir).expanduser().resolve()
    write_json(package_dir / "director_polish_contract_audit.json", report)
    write_markdown(package_dir / "director_polish_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "warnings": report["warnings"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
