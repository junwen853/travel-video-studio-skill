#!/usr/bin/env python3
"""Audit whether a travel edit aligns with reusable Bilibili/Malta-style rules."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


TRANSPORT_TERMS = (
    "airport",
    "terminal",
    "boarding",
    "flight",
    "train",
    "rail",
    "shinkansen",
    "station",
    "metro",
    "subway",
    "taxi",
    "road",
    "window",
    "bridge",
    "transfer",
    "机场",
    "列车",
    "新干线",
    "地铁",
    "车站",
    "航班",
)
STREET_CITY_TERMS = (
    "street",
    "walking",
    "city",
    "skyline",
    "shopping",
    "retail",
    "district",
    "canal",
    "river",
    "night",
    "街",
    "城市",
    "街区",
    "人潮",
    "夜",
)
LIVED_IN_TERMS = (
    "hotel",
    "food",
    "dinner",
    "shop",
    "interior",
    "convenience",
    "waiting",
    "table",
    "restaurant",
    "retail",
    "酒店",
    "便利店",
    "餐",
    "店",
    "室内",
    "等待",
)
LANDMARK_TERMS = (
    "castle",
    "tower",
    "temple",
    "shrine",
    "dotonbori",
    "akihabara",
    "ginza",
    "asakusa",
    "senso",
    "大阪城",
    "东京塔",
    "寺",
    "神社",
    "道顿堀",
    "秋叶原",
    "银座",
)
AI_SLIDESHOW_RISK_TERMS = (
    "title_cards",
    "black slate",
    "placeholder",
    "generic japan",
    "travel film",
    "slideshow",
    "图片开图",
    "长片开场",
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


def skill_dir_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


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
    except Exception:
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


def role_text(clip: dict[str, Any]) -> str:
    return " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "type", "name")).lower()


def source_path(clip: dict[str, Any]) -> str:
    return str(clip.get("sourcePath") or "")


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def safe_percent(value: float, denom: float) -> float:
    return round((value / denom) * 100, 2) if denom else 0.0


def chapter_texts(delivery_plan: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for chapter in delivery_plan.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        out.append(
            " ".join(
                str(chapter.get(key) or "")
                for key in ("chapter", "place", "city", "country", "confidenceLevel")
            )
        )
    return out


def text_category_evidence(texts: list[str]) -> dict[str, Any]:
    combined = "\n".join(texts)
    categories = {
        "transport": has_any(combined, TRANSPORT_TERMS),
        "streetCity": has_any(combined, STREET_CITY_TERMS),
        "livedInDetails": has_any(combined, LIVED_IN_TERMS),
        "landmarkPayoff": has_any(combined, LANDMARK_TERMS),
    }
    per_chapter = []
    for index, text in enumerate(texts, start=1):
        per_chapter.append(
            {
                "index": index,
                "transport": has_any(text, TRANSPORT_TERMS),
                "streetCity": has_any(text, STREET_CITY_TERMS),
                "livedInDetails": has_any(text, LIVED_IN_TERMS),
                "landmarkPayoff": has_any(text, LANDMARK_TERMS),
                "text": text,
            }
        )
    return {"categories": categories, "perChapter": per_chapter}


def count_track(resolve_audit: dict[str, Any], kind: str, index: int) -> int | None:
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        try:
            if int(row.get("index") or -1) == index:
                return int(row.get("itemCount") or 0)
        except (TypeError, ValueError):
            continue
    return None


def cue_count(path: Path | None) -> int:
    if not path or not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    return sum(1 for block in re.split(r"\n\s*\n", text.strip()) if "-->" in block)


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


def find_reference_analysis(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    env_reference = os.environ.get("TRAVEL_VIDEO_REFERENCE_ANALYSIS")
    candidates = [
        package_dir / "reference" / "reference_batch_profile.json",
        package_dir / "reference" / "reference_analysis.json",
        package_dir / "reference" / "reference_analysis.md",
    ]
    if env_reference:
        candidates.insert(0, Path(env_reference).expanduser())
    return next((path for path in candidates if path.exists()), None)


def reference_profile_evidence(path: Path | None) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "referenceAnalysis": str(path) if path else None,
        "exists": bool(path and path.exists()),
        "profileAvailable": False,
    }
    if not path or not path.exists() or path.suffix.lower() != ".json":
        return evidence
    data = load_json(path) or {}
    pacing = data.get("pacingProfile") if isinstance(data.get("pacingProfile"), dict) else {}
    audio = data.get("audioProfile") if isinstance(data.get("audioProfile"), dict) else {}
    samples = data.get("sampleFrames") if isinstance(data.get("sampleFrames"), list) else []
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    evidence.update(
        {
            "profileAvailable": True,
            "durationMinutes": summary.get("durationMinutes") or summary.get("totalDurationMinutes") or data.get("durationMinutes"),
            "pacingStatus": pacing.get("status"),
            "estimatedShotCount": pacing.get("estimatedShotCount"),
            "averageShotLengthSeconds": pacing.get("averageShotLengthSeconds"),
            "medianShotLengthSeconds": pacing.get("medianShotLengthSeconds"),
            "audioStatus": audio.get("status"),
            "meanVolumeDb": audio.get("meanVolumeDb"),
            "sampleFrameCount": len(samples),
            "contactSheet": data.get("contactSheet"),
        }
    )
    return evidence


def reference_profile_ready(evidence: dict[str, Any]) -> bool:
    if not evidence.get("exists"):
        return False
    if not evidence.get("profileAvailable"):
        return False
    return (
        evidence.get("pacingStatus") == "analyzed"
        and evidence.get("audioStatus") == "analyzed"
        and int(evidence.get("estimatedShotCount") or 0) >= 50
        and float(evidence.get("averageShotLengthSeconds") or 0) > 0
        and int(evidence.get("sampleFrameCount") or 0) >= 12
    )


def check_status(name: str, report: Any, accepted: set[str]) -> dict[str, Any]:
    status = report.get("status") if isinstance(report, dict) else None
    return {"name": name, "status": status, "passed": status in accepted}


def score_check(name: str, passed: bool, points: int, evidence: Any, *, warning: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "status": "passed" if passed else ("warning" if warning else "blocked"),
        "points": points if passed else 0,
        "maxPoints": points,
        "evidence": evidence,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    delivery_plan = load_json(package_dir / "delivery_plan.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    visual_audio = load_json(package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json") or {}
    client = load_json(package_dir / "client_delivery_rules_audit.json") or {}
    story = load_json(package_dir / "story_style_contract_audit.json") or {}
    feedback = load_json(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json") or {}
    longform = load_json(package_dir / "longform_delivery_audit.json") or {}
    final_output = infer_final_output(package_dir, args.output)
    duration = infer_duration(package_dir, blueprint, final_output)
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    chapters = delivery_plan.get("chapters") if isinstance(delivery_plan.get("chapters"), list) else []
    texts = chapter_texts(delivery_plan)
    category_evidence = text_category_evidence(texts)
    categories = category_evidence["categories"]

    main_clips = [clip for clip in clips if isinstance(clip, dict) and "main_footage" in role_text(clip)]
    bridge_clips = [
        clip
        for clip in clips
        if isinstance(clip, dict) and has_any(role_text(clip), ("transition", "bridge", "establish", "aerial"))
    ]
    title_clips = [
        clip
        for clip in clips
        if isinstance(clip, dict) and has_any(role_text(clip), ("opening_city", "chapter_title", "ending_city"))
    ]
    subtitle_overlays = [clip for clip in clips if isinstance(clip, dict) and "subtitle_overlay" in role_text(clip)]
    transition_plan = blueprint.get("transitionPlan") if isinstance(blueprint.get("transitionPlan"), list) else []
    markers = blueprint.get("timelineMarkers") if isinstance(blueprint.get("timelineMarkers"), list) else []
    durations = [clip_duration(clip) for clip in main_clips if clip_duration(clip) > 0]
    avg_shot = sum(durations) / len(durations) if durations else 0.0
    unique_sources = {
        Path(source_path(clip)).name
        for clip in clips
        if isinstance(clip, dict) and source_path(clip) and "subtitle_overlay" not in role_text(clip)
    }
    ai_risk_sources = [
        source_path(clip)
        for clip in clips
        if isinstance(clip, dict) and has_any(source_path(clip), AI_SLIDESHOW_RISK_TERMS)
    ]
    subtitle_path = find_subtitle_path(package_dir, blueprint)
    subtitles = cue_count(subtitle_path)
    cues_per_minute = subtitles / (duration / 60) if duration > 0 else 0.0
    reference_analysis = find_reference_analysis(package_dir, args.reference_analysis)
    reference_evidence = reference_profile_evidence(reference_analysis)
    style_reference = (
        Path(args.style_reference).expanduser()
        if args.style_reference
        else skill_dir_from_script() / "references" / "bilibili-travel-style.md"
    )

    upstream_statuses = [
        check_status("render_delivery_verification", render, {"passed"}),
        check_status("visual_audio_style_audit", visual_audio, {"passed"}),
        check_status("client_delivery_rules_audit", client, {"passed", "passed_with_warnings"}),
        check_status("story_style_contract_audit", story, {"passed", "passed_with_warnings"}),
        check_status("feedback_regression_audit", feedback, {"passed", "passed_with_warnings"}),
        check_status("longform_delivery_audit", longform, {"passed", "passed_with_caveats", "passed_with_warnings"}),
    ]

    checks = [
        score_check(
            "Reference material is present, profiled, and explicitly non-copying",
            reference_profile_ready(reference_evidence) and bool(style_reference and style_reference.exists()),
            10,
            {**reference_evidence, "styleReference": str(style_reference) if style_reference else None},
        ),
        score_check(
            "Long-form duration target is met",
            duration >= args.min_duration_seconds,
            10,
            {"durationSeconds": round(duration, 3), "minDurationSeconds": args.min_duration_seconds},
        ),
        score_check(
            "Route has multiple day/place chapters with visible travel arc",
            len(chapters) >= args.min_chapters
            and all(not chapter.get("markedDoNotCut") for chapter in chapters if isinstance(chapter, dict))
            and sum(1 for value in categories.values() if value) >= 4,
            14,
            {"chapterCount": len(chapters), **category_evidence},
        ),
        score_check(
            "Transport and connective tissue are first-class story material",
            categories["transport"] and len(transition_plan) >= args.min_transitions and len(bridge_clips) >= args.min_transitions,
            12,
            {"transportDetected": categories["transport"], "transitionPlanCount": len(transition_plan), "bridgeClipCount": len(bridge_clips)},
        ),
        score_check(
            "Street, lived-in, and landmark beats are balanced",
            categories["streetCity"] and categories["livedInDetails"] and categories["landmarkPayoff"],
            12,
            {"categories": categories, "perChapter": category_evidence["perChapter"]},
        ),
        score_check(
            "The edit uses varied real footage instead of a slideshow skeleton",
            len(main_clips) >= args.min_main_clips
            and len(unique_sources) >= args.min_unique_sources
            and args.min_avg_shot_seconds <= avg_shot <= args.max_avg_shot_seconds
            and not ai_risk_sources,
            12,
            {
                "mainClipCount": len(main_clips),
                "uniqueSourceCount": len(unique_sources),
                "averageMainClipSeconds": round(avg_shot, 3),
                "aiSlideshowRiskSources": ai_risk_sources[:20],
            },
        ),
        score_check(
            "Opening, chapters, and ending have scenic title/bridge structure",
            len(title_clips) >= args.min_title_clips and bool(blueprint.get("scenicTitleBridgePolicy")),
            10,
            {
                "titleClipCount": len(title_clips),
                "requiredTitleClipCount": args.min_title_clips,
                "scenicTitleBridgePolicy": blueprint.get("scenicTitleBridgePolicy"),
            },
        ),
        score_check(
            "No-voiceover mode is carried by BGM and dense captions",
            (count_track(resolve_audit, "audio", 1) in {0, None})
            and (count_track(resolve_audit, "audio", 2) in {0, None})
            and (count_track(resolve_audit, "audio", 3) or 0) > 0
            and len(subtitle_overlays) >= args.min_subtitle_overlays
            and subtitles >= args.min_subtitle_cues
            and cues_per_minute >= args.min_cues_per_minute,
            12,
            {
                "audioTracks": {
                    "A1": count_track(resolve_audit, "audio", 1),
                    "A2": count_track(resolve_audit, "audio", 2),
                    "A3": count_track(resolve_audit, "audio", 3),
                },
                "subtitleOverlayCount": len(subtitle_overlays),
                "subtitlePath": str(subtitle_path) if subtitle_path else None,
                "subtitleCueCount": subtitles,
                "cuesPerMinute": round(cues_per_minute, 3),
            },
        ),
        score_check(
            "Upstream technical/client/feedback audits support the style claim",
            all(row["passed"] for row in upstream_statuses),
            8,
            {"upstreamStatuses": upstream_statuses},
        ),
    ]

    max_score = sum(row["maxPoints"] for row in checks)
    score = sum(row["points"] for row in checks)
    score_percent = safe_percent(score, max_score)
    blocked = [row for row in checks if row["status"] == "blocked"]
    warnings = [row for row in checks if row["status"] == "warning"]
    if score_percent < args.min_score:
        blocked.append(
            {
                "name": "Minimum reference-style alignment score",
                "status": "blocked",
                "points": score,
                "maxPoints": max_score,
                "evidence": {"scorePercent": score_percent, "minScore": args.min_score},
            }
        )
    status = "blocked" if blocked else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "finalOutput": str(final_output) if final_output else None,
        "score": score,
        "maxScore": max_score,
        "scorePercent": score_percent,
        "checks": checks,
        "blockers": [row["name"] for row in blocked],
        "warnings": [row["name"] for row in warnings],
        "styleContract": {
            "target": "Bilibili/Malta-inspired long-form travel documentary vlog; non-copying reference alignment",
            "mustFeelLike": [
                "real route movement",
                "transport and street connective tissue",
                "lived-in hotel/food/shop/waiting texture",
                "scenic chapter breathing room",
                "BGM-led no-voiceover storytelling",
            ],
            "routeCaveat": "Non-GPS route reconstruction remains a caveat unless per-clip geolocation is separately verified.",
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Reference Style Alignment Audit",
        "",
        f"Status: `{report['status']}`",
        f"Score: `{report['score']}/{report['maxScore']}` (`{report['scorePercent']}%`)",
        f"Package: `{report['packageDir']}`",
        f"Final output: `{report.get('finalOutput')}`",
        "",
        "## Checks",
    ]
    for row in report["checks"]:
        evidence = json.dumps(row["evidence"], ensure_ascii=False)[:1800]
        lines.extend(["", f"### {row['name']}", f"- Status: `{row['status']}`", f"- Points: `{row['points']}/{row['maxPoints']}`", f"- Evidence: `{evidence}`"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Style Contract"])
    lines.append(json.dumps(report["styleContract"], ensure_ascii=False, indent=2))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit reference-style alignment for a travel edit package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--reference-analysis")
    parser.add_argument("--style-reference")
    parser.add_argument("--min-duration-seconds", type=float, default=18 * 60)
    parser.add_argument("--min-chapters", type=int, default=5)
    parser.add_argument("--min-transitions", type=int, default=4)
    parser.add_argument("--min-main-clips", type=int, default=35)
    parser.add_argument("--min-unique-sources", type=int, default=35)
    parser.add_argument("--min-avg-shot-seconds", type=float, default=6.0)
    parser.add_argument("--max-avg-shot-seconds", type=float, default=42.0)
    parser.add_argument("--min-title-clips", type=int, default=7)
    parser.add_argument("--min-subtitle-overlays", type=int, default=80)
    parser.add_argument("--min-subtitle-cues", type=int, default=80)
    parser.add_argument("--min-cues-per-minute", type=float, default=3.5)
    parser.add_argument("--min-score", type=float, default=88.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = build_report(Path(args.package_dir), args)
    except Exception as exc:
        print(f"audit_reference_style_alignment failed: {exc}", file=sys.stderr)
        return 1
    package_dir = Path(args.package_dir).expanduser().resolve()
    json_path = package_dir / "reference_style_alignment_audit.json"
    md_path = package_dir / "reference_style_alignment_audit.md"
    write_json(json_path, report)
    write_markdown(md_path, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "scorePercent": report["scorePercent"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
