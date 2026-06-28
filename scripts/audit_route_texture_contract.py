#!/usr/bin/env python3
"""Audit route transitions and lived-in travel texture for long-form edits."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


TRANSPORT_TERMS = (
    "airport",
    "terminal",
    "boarding",
    "flight",
    "arrival",
    "departure",
    "train",
    "rail",
    "shinkansen",
    "station",
    "platform",
    "metro",
    "subway",
    "taxi",
    "road",
    "vehicle",
    "window",
    "bridge",
    "transfer",
    "escalator",
    "elevator",
    "ferry",
    "boat",
    "bus",
    "机场",
    "航班",
    "飞机",
    "到达",
    "出发",
    "列车",
    "新干线",
    "电车",
    "地铁",
    "车站",
    "站台",
    "车窗",
    "路上",
    "交通",
    "桥",
    "码头",
    "船",
    "巴士",
)
STREET_TERMS = (
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
    "market",
    "alley",
    "storefront",
    "crowd",
    "signage",
    "neighborhood",
    "sidewalk",
    "plaza",
    "crossing",
    "weather",
    "rain",
    "街",
    "城市",
    "街区",
    "步行",
    "人潮",
    "夜",
    "河",
    "运河",
    "招牌",
    "商店",
    "市场",
    "路口",
    "天气",
)
LIVED_IN_TERMS = (
    "hotel",
    "food",
    "dinner",
    "breakfast",
    "lunch",
    "shop",
    "interior",
    "convenience",
    "waiting",
    "table",
    "restaurant",
    "cafe",
    "ticket",
    "vending",
    "room",
    "lobby",
    "mall",
    "酒店",
    "便利店",
    "餐",
    "早餐",
    "晚餐",
    "午餐",
    "饭",
    "店",
    "室内",
    "等待",
    "票",
    "咖啡",
    "商场",
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
    "park",
    "aerial",
    "observation",
    "museum",
    "大阪城",
    "东京塔",
    "寺",
    "神社",
    "道顿堀",
    "秋叶原",
    "银座",
    "浅草",
    "公园",
    "航拍",
    "展望",
    "博物馆",
)
BRIDGE_ROLE_TERMS = (
    "transition_bridge",
    "opening_visual_bed",
    "ending_visual_bed",
    "visual_bed",
    "aerial",
    "establish",
    "establishing",
)
BRIDGE_PURPOSE_TERMS = (
    "chapter bridge",
    "transition bridge",
    "route bridge",
    "route-aware bridge",
    "long-form chapter bridge",
    "visual bridge",
)
TITLE_TERMS = ("opening_city", "chapter_title", "ending_city", "title_bridge")
SLIDESHOW_RISK_TERMS = (
    "title_cards",
    "black slate",
    "black_card",
    "placeholder",
    "generic japan",
    "slideshow",
    "png",
    "jpg",
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


def text_has(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def timeline_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds", "timeline_start"):
        try:
            return float(clip.get(key))
        except (TypeError, ValueError):
            continue
    return 0.0


def clip_duration(clip: dict[str, Any]) -> float:
    for key in ("durationSeconds", "duration", "duration_seconds"):
        try:
            value = float(clip.get(key))
            if value > 0:
                return value
        except (TypeError, ValueError):
            continue
    try:
        start = float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or 0)
        end = float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or 0)
        if end > start:
            return end - start
    except (TypeError, ValueError):
        pass
    try:
        source_start = float(clip.get("sourceStartSeconds") or 0)
        source_end = float(clip.get("sourceEndSeconds") or 0)
        if source_end > source_start:
            return source_end - source_start
    except (TypeError, ValueError):
        pass
    return 0.0


def timeline_end(clip: dict[str, Any]) -> float:
    for key in ("timelineEndSeconds", "recordEndSeconds", "endSeconds"):
        try:
            return float(clip.get(key))
        except (TypeError, ValueError):
            continue
    return timeline_start(clip) + clip_duration(clip)


def role_text(clip: dict[str, Any]) -> str:
    return str(clip.get("role") or clip.get("type") or "").lower()


def clip_text(clip: dict[str, Any]) -> str:
    keys = (
        "role",
        "type",
        "name",
        "chapter",
        "place",
        "city",
        "country",
        "purpose",
        "sourcePath",
        "assetPath",
    )
    return " ".join(str(clip.get(key) or "") for key in keys).lower()


def source_path(clip: dict[str, Any]) -> str:
    return str(clip.get("sourcePath") or clip.get("assetPath") or "")


def is_subtitle(clip: dict[str, Any]) -> bool:
    return "subtitle_overlay" in role_text(clip)


def is_title_clip(clip: dict[str, Any]) -> bool:
    text = role_text(clip)
    return text_has(text, TITLE_TERMS)


def is_bridge_clip(clip: dict[str, Any]) -> bool:
    purpose = str(clip.get("purpose") or "").lower()
    return text_has(role_text(clip), BRIDGE_ROLE_TERMS) or text_has(purpose, BRIDGE_PURPOSE_TERMS)


def categories_for_clip(clip: dict[str, Any]) -> dict[str, bool]:
    text = clip_text(clip)
    return {
        "transport": text_has(text, TRANSPORT_TERMS),
        "street": text_has(text, STREET_TERMS),
        "livedIn": text_has(text, LIVED_IN_TERMS),
        "landmark": text_has(text, LANDMARK_TERMS),
    }


def overlap_seconds(clip: dict[str, Any], start: float, end: float) -> float:
    left = max(timeline_start(clip), start)
    right = min(timeline_end(clip), end)
    return max(0.0, right - left)


def infer_duration(blueprint: dict[str, Any], clips: list[dict[str, Any]]) -> float:
    for key in ("targetDurationSeconds", "actualVideoCoverageSeconds"):
        try:
            value = float(blueprint.get(key))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return max((timeline_end(clip) for clip in clips), default=0.0)


def infer_title_segments(package_dir: Path, blueprint: dict[str, Any], clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest_path: Path | None = None
    policy = blueprint.get("scenicTitleBridgePolicy") if isinstance(blueprint.get("scenicTitleBridgePolicy"), dict) else {}
    if policy.get("manifest"):
        manifest_path = Path(str(policy["manifest"])).expanduser()
    candidates = [
        manifest_path,
        package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json",
        package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
    ]
    for path in candidates:
        data = load_json(path)
        if isinstance(data, dict) and isinstance(data.get("segments"), list):
            out: list[dict[str, Any]] = []
            for item in data["segments"]:
                if not isinstance(item, dict):
                    continue
                out.append(
                    {
                        "mode": str(item.get("mode") or ""),
                        "title": str(item.get("title") or item.get("id") or ""),
                        "start": timeline_start(item),
                        "end": timeline_start(item) + clip_duration(item),
                        "source": str(item.get("segment") or item.get("source") or ""),
                    }
                )
            return sorted(out, key=lambda row: row["start"])
    out = []
    for clip in clips:
        if not is_title_clip(clip):
            continue
        out.append(
            {
                "mode": "chapter" if "chapter" in role_text(clip) else ("opening" if "opening" in role_text(clip) else "ending"),
                "title": str(clip.get("place") or clip.get("name") or role_text(clip)),
                "start": timeline_start(clip),
                "end": timeline_end(clip),
                "source": source_path(clip),
            }
        )
    return sorted(out, key=lambda row: row["start"])


def chapter_windows(title_segments: list[dict[str, Any]], final_duration: float) -> list[dict[str, Any]]:
    chapters = [row for row in title_segments if row.get("mode") == "chapter"]
    windows: list[dict[str, Any]] = []
    for index, row in enumerate(chapters):
        start = float(row["start"])
        next_start = float(chapters[index + 1]["start"]) if index + 1 < len(chapters) else final_duration
        windows.append(
            {
                "index": index + 1,
                "title": row.get("title") or f"Chapter {index + 1}",
                "start": start,
                "end": max(start, next_start),
            }
        )
    return windows


def nearby_bridge(clips: list[dict[str, Any]], anchor: float, window_seconds: float) -> list[dict[str, Any]]:
    out = []
    for clip in clips:
        if is_subtitle(clip) or is_title_clip(clip) or not is_bridge_clip(clip):
            continue
        start = timeline_start(clip)
        end = timeline_end(clip)
        distance = 0.0 if start <= anchor <= end else min(abs(anchor - start), abs(anchor - end))
        if distance <= window_seconds:
            out.append(
                {
                    "role": role_text(clip),
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "distanceSeconds": round(distance, 3),
                    "source": source_path(clip),
                    "categories": categories_for_clip(clip),
                }
            )
    return sorted(out, key=lambda row: row["distanceSeconds"])


def check_status(name: str, report: Any, accepted: set[str]) -> dict[str, Any]:
    status = report.get("status") if isinstance(report, dict) else None
    return {"name": name, "status": status, "passed": status in accepted}


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else ("warning" if warning else "blocked"),
            "evidence": evidence,
        }
    )


def summarize_chapters(
    windows: list[dict[str, Any]],
    content_clips: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in windows:
        overlapping = [
            clip
            for clip in content_clips
            if overlap_seconds(clip, float(window["start"]), float(window["end"])) >= args.min_chapter_clip_overlap_seconds
        ]
        category_counts = {"transport": 0, "street": 0, "livedIn": 0, "landmark": 0}
        for clip in overlapping:
            cats = categories_for_clip(clip)
            for key, value in cats.items():
                category_counts[key] += 1 if value else 0
        texture_categories = sum(1 for key in ("transport", "street", "livedIn", "landmark") if category_counts[key] > 0)
        rows.append(
            {
                **window,
                "contentClipCount": len(overlapping),
                "categoryCounts": category_counts,
                "textureCategories": texture_categories,
                "passed": len(overlapping) >= args.min_chapter_content_clips and texture_categories >= args.min_chapter_texture_categories,
                "sampleSources": [source_path(clip) for clip in overlapping[:6]],
            }
        )
    return rows


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    clips = [clip for clip in (blueprint.get("clips") or []) if isinstance(clip, dict)]
    content_clips = [clip for clip in clips if not is_subtitle(clip) and not is_title_clip(clip)]
    transition_plan = blueprint.get("transitionPlan") if isinstance(blueprint.get("transitionPlan"), list) else []
    title_segments = infer_title_segments(package_dir, blueprint, clips)
    final_duration = infer_duration(blueprint, clips)
    windows = chapter_windows(title_segments, final_duration)
    chapter_rows = summarize_chapters(windows, content_clips, args)

    transition_matches = []
    for item in transition_plan:
        if not isinstance(item, dict):
            continue
        try:
            anchor = float(item.get("timelineStartSeconds"))
        except (TypeError, ValueError):
            continue
        matches = nearby_bridge(clips, anchor, args.bridge_window_seconds)
        transition_matches.append(
            {
                "afterChapter": item.get("afterChapter"),
                "anchor": round(anchor, 3),
                "bridge": item.get("bridge"),
                "matches": matches[:5],
                "matched": bool(matches),
            }
        )

    chapter_title_matches = []
    chapter_titles = [row for row in title_segments if row.get("mode") == "chapter"]
    for index, row in enumerate(chapter_titles):
        if index == 0 and args.allow_first_chapter_without_prebridge:
            continue
        matches = nearby_bridge(clips, float(row["start"]), args.title_bridge_window_seconds)
        chapter_title_matches.append(
            {
                "title": row.get("title"),
                "start": round(float(row["start"]), 3),
                "matches": matches[:5],
                "matched": bool(matches),
            }
        )

    category_counts = {"transport": 0, "street": 0, "livedIn": 0, "landmark": 0}
    for clip in content_clips:
        cats = categories_for_clip(clip)
        for key, value in cats.items():
            category_counts[key] += 1 if value else 0

    bridge_clips = [clip for clip in content_clips if is_bridge_clip(clip)]
    opening_visual = [clip for clip in content_clips if "opening_visual_bed" in role_text(clip)]
    ending_visual = [clip for clip in content_clips if "ending_visual_bed" in role_text(clip)]
    risk_sources = [
        source_path(clip)
        for clip in clips
        if not is_subtitle(clip) and text_has(source_path(clip), SLIDESHOW_RISK_TERMS)
    ]

    upstream = [
        check_status("story_style_contract_audit", load_json(package_dir / "story_style_contract_audit.json"), {"passed"}),
        check_status("reference_style_alignment_audit", load_json(package_dir / "reference_style_alignment_audit.json"), {"passed"}),
        check_status("title_bridge_contract_audit", load_json(package_dir / "title_bridge_contract_audit.json"), {"passed", "passed_with_warnings"}),
        check_status("bgm_audio_contract_audit", load_json(package_dir / "bgm_audio_contract_audit.json"), {"passed", "passed_with_warnings"}),
    ]

    matched_transitions = sum(1 for row in transition_matches if row["matched"])
    transition_match_ratio = matched_transitions / len(transition_matches) if transition_matches else 0.0
    matched_titles = sum(1 for row in chapter_title_matches if row["matched"])
    title_match_ratio = matched_titles / len(chapter_title_matches) if chapter_title_matches else 1.0
    passed_chapters = sum(1 for row in chapter_rows if row["passed"])
    chapter_texture_ratio = passed_chapters / len(chapter_rows) if chapter_rows else 0.0

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Transition plan is backed by physical bridge clips",
        len(transition_plan) >= args.min_transition_plan
        and len(bridge_clips) >= args.min_transition_bridge_clips
        and transition_match_ratio >= args.min_transition_match_ratio,
        {
            "transitionPlanCount": len(transition_plan),
            "bridgeClipCount": len(bridge_clips),
            "matchedTransitions": matched_transitions,
            "transitionMatchRatio": round(transition_match_ratio, 3),
            "matches": transition_matches,
        },
    )
    add_check(
        checks,
        "Chapter title moments have nearby route connective tissue",
        len(chapter_titles) >= args.min_chapters and title_match_ratio >= args.min_title_bridge_match_ratio,
        {
            "chapterTitleCount": len(chapter_titles),
            "matchedTitleBoundaries": matched_titles,
            "evaluatedTitleBoundaries": len(chapter_title_matches),
            "titleMatchRatio": round(title_match_ratio, 3),
            "matches": chapter_title_matches,
        },
    )
    add_check(
        checks,
        "Chapters contain lived-in texture beyond title cards",
        len(chapter_rows) >= args.min_chapters and chapter_texture_ratio >= args.min_chapter_texture_ratio,
        {
            "chapterWindowCount": len(chapter_rows),
            "passedChapters": passed_chapters,
            "chapterTextureRatio": round(chapter_texture_ratio, 3),
            "chapters": chapter_rows,
        },
    )
    add_check(
        checks,
        "Global route texture balances movement, street life, daily detail, and landmarks",
        category_counts["transport"] >= args.min_transport_clips
        and category_counts["street"] + category_counts["livedIn"] >= args.min_street_livedin_clips
        and category_counts["landmark"] >= args.min_landmark_clips,
        {
            "categoryCounts": category_counts,
            "minTransportClips": args.min_transport_clips,
            "minStreetLivedInClips": args.min_street_livedin_clips,
            "minLandmarkClips": args.min_landmark_clips,
        },
    )
    add_check(
        checks,
        "Opening and ending breathe on real visual material",
        len(opening_visual) >= args.min_opening_visual_clips and len(ending_visual) >= args.min_ending_visual_clips,
        {
            "openingVisualBedClips": len(opening_visual),
            "endingVisualBedClips": len(ending_visual),
            "openingSamples": [source_path(clip) for clip in opening_visual[:5]],
            "endingSamples": [source_path(clip) for clip in ending_visual[:5]],
        },
    )
    add_check(
        checks,
        "No slideshow or stale title-card source is used as route texture",
        not risk_sources,
        {"riskSources": risk_sources[:20]},
    )
    add_check(
        checks,
        "Upstream story/style/title/BGM contracts support the route texture claim",
        all(row["passed"] for row in upstream),
        {"upstreamStatuses": upstream},
        warning=True,
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings = [row["name"] for row in checks if row["status"] == "warning"]
    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "transitionPlanCount": len(transition_plan),
            "bridgeClipCount": len(bridge_clips),
            "matchedTransitions": matched_transitions,
            "chapterTitleCount": len(chapter_titles),
            "matchedTitleBoundaries": matched_titles,
            "chapterWindowCount": len(chapter_rows),
            "passedChapters": passed_chapters,
            "categoryCounts": category_counts,
        },
        "contract": {
            "purpose": "Prevent AI-looking travel assemblies by requiring route movement, bridge footage, street/lived-in detail, and landmark payoff to exist on the actual timeline.",
            "styleReference": "Bilibili/Malta-style long-form travel rhythm; non-copying, route-aware, BGM-led when voiceover is rejected.",
            "failureMeaning": "A package can pass technical render checks and still fail this contract if days/places are joined only by titles, hard cuts, black cards, or landmark-only montage.",
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Route Texture Contract Audit",
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
        lines.extend(
            [
                "",
                f"### {row['name']}",
                f"- Status: `{row['status']}`",
                f"- Evidence: `{evidence}`",
            ]
        )
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Contract", "", "```json", json.dumps(report["contract"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit route connective tissue and lived-in texture in a travel edit package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-chapters", type=int, default=5)
    parser.add_argument("--min-transition-plan", type=int, default=4)
    parser.add_argument("--min-transition-bridge-clips", type=int, default=4)
    parser.add_argument("--min-transition-match-ratio", type=float, default=0.75)
    parser.add_argument("--min-title-bridge-match-ratio", type=float, default=0.75)
    parser.add_argument("--min-chapter-texture-ratio", type=float, default=0.8)
    parser.add_argument("--min-chapter-content-clips", type=int, default=2)
    parser.add_argument("--min-chapter-texture-categories", type=int, default=1)
    parser.add_argument("--min-chapter-clip-overlap-seconds", type=float, default=1.0)
    parser.add_argument("--min-transport-clips", type=int, default=4)
    parser.add_argument("--min-street-livedin-clips", type=int, default=8)
    parser.add_argument("--min-landmark-clips", type=int, default=4)
    parser.add_argument("--min-opening-visual-clips", type=int, default=2)
    parser.add_argument("--min-ending-visual-clips", type=int, default=1)
    parser.add_argument("--bridge-window-seconds", type=float, default=24.0)
    parser.add_argument("--title-bridge-window-seconds", type=float, default=28.0)
    parser.add_argument("--allow-first-chapter-without-prebridge", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        package_dir = Path(args.package_dir)
        report = build_report(package_dir, args)
    except Exception as exc:
        print(f"audit_route_texture_contract failed: {exc}")
        return 1
    package_dir = Path(args.package_dir).expanduser().resolve()
    write_json(package_dir / "route_texture_contract_audit.json", report)
    write_markdown(package_dir / "route_texture_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
