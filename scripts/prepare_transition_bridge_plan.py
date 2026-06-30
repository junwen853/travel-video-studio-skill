#!/usr/bin/env python3
"""Prepare proactive route-aware transition bridge planning rows."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


BRIDGE_TERMS = (
    "transition_bridge",
    "chapter_title_bridge",
    "title_bridge",
    "route bridge",
    "visual bridge",
    "bridge footage",
    "opening_visual_bed",
    "ending_visual_bed",
    "aerial",
    "establishing",
    "establish",
)

TRANSPORT_TERMS = (
    "airport",
    "flight",
    "plane",
    "station",
    "train",
    "rail",
    "metro",
    "subway",
    "taxi",
    "bus",
    "tram",
    "ferry",
    "车",
    "机场",
    "地铁",
    "火车",
    "高铁",
)

STREET_TERMS = ("street", "road", "walk", "alley", "market", "shop", "signage", "city", "街", "路", "店", "招牌")
FOOD_TERMS = ("food", "restaurant", "dinner", "breakfast", "cafe", "table", "meal", "饭", "餐", "咖啡")
HOTEL_TERMS = ("hotel", "lobby", "window", "room", "elevator", "convenience", "酒店", "窗", "电梯")
QUIET_TERMS = ("temple", "shrine", "garden", "park", "museum", "寺", "神社", "公园")

DECISION_FIELDS = {
    "selectedLocalClips": [],
    "selectedStockAssets": [],
    "selectedAerialAssets": [],
    "licenseUrls": [],
    "localPathsAfterDownload": [],
    "resolveRole": "transition_bridge_footage",
    "timelinePlacementNotes": "",
    "audioTreatment": "bgm_only_no_camera_voice",
    "subtitleLine": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

PROVIDERS = {
    "Pixabay Video": {
        "homeUrl": "https://pixabay.com/videos/",
        "licenseUrl": "https://pixabay.com/service/license-summary/",
        "bestFor": "free establishing, skyline, street, and transport stock where exact video URL is recorded",
    },
    "Pexels Video": {
        "homeUrl": "https://www.pexels.com/videos/",
        "licenseUrl": "https://www.pexels.com/license/",
        "bestFor": "free city/street ambience fallbacks where exact clip URL is recorded",
    },
    "Mixkit Video": {
        "homeUrl": "https://mixkit.co/free-stock-video/",
        "licenseUrl": "https://mixkit.co/license/#videoFree",
        "bestFor": "free polished aerial, skyline, and lifestyle inserts where exact clip page is recorded",
    },
    "Artgrid": {
        "homeUrl": "https://artgrid.io/",
        "licenseUrl": "https://artgrid.io/license",
        "bestFor": "paid premium travel footage when a subscription/project license is verified",
    },
    "Storyblocks": {
        "homeUrl": "https://www.storyblocks.com/video",
        "licenseUrl": "https://www.storyblocks.com/license",
        "bestFor": "paid backup footage when a subscription/project license is verified",
    },
}


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_words(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def lower_text(value: Any) -> str:
    return clean_words(value, limit=1000).lower()


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def active_chapters(delivery: dict[str, Any], blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = [
        row
        for row in delivery.get("chapters") or []
        if isinstance(row, dict) and not row.get("markedDoNotCut")
    ]
    if chapters:
        out: list[dict[str, Any]] = []
        for fallback_index, row in enumerate(chapters, start=1):
            out.append(
                {
                    "index": int(row.get("index") or fallback_index),
                    "chapter": clean_words(row.get("chapter") or row.get("title") or f"Chapter {fallback_index}"),
                    "place": clean_words(row.get("place") or row.get("routeStop") or row.get("city") or ""),
                    "city": clean_words(row.get("city") or ""),
                    "country": clean_words(row.get("country") or ""),
                }
            )
        return out

    markers = [
        row
        for row in blueprint.get("timelineMarkers") or []
        if isinstance(row, dict) and "chapter" in lower_text(row.get("name") or row.get("note") or row.get("label"))
    ]
    out = []
    for fallback_index, row in enumerate(markers, start=1):
        label = clean_words(row.get("name") or row.get("label") or row.get("note") or f"Chapter {fallback_index}")
        out.append({"index": fallback_index, "chapter": label, "place": label, "city": "", "country": ""})
    return out


def chapter_text(chapter: dict[str, Any]) -> str:
    return " ".join(clean_words(chapter.get(key)) for key in ("chapter", "place", "city", "country")).strip()


def city_token(chapter: dict[str, Any]) -> str:
    city = clean_words(chapter.get("city") or chapter.get("place") or chapter.get("chapter")).lower()
    city = re.sub(r"\blikely\b|\bexact\b|\bunconfirmed\b|\bcorridor\b", "", city)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", city).strip()


def plan_rows(delivery: dict[str, Any], blueprint: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for source in (delivery.get("transitions"), blueprint.get("transitionPlan")):
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict):
                continue
            try:
                after = int(item.get("afterChapter"))
            except (TypeError, ValueError):
                continue
            rows[after] = item
    return rows


def clip_start(clip: dict[str, Any]) -> float | None:
    for key in ("timelineStartSeconds", "startSeconds", "start", "timelineStart"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    return None


def clip_end(clip: dict[str, Any]) -> float | None:
    for key in ("timelineEndSeconds", "endSeconds", "end", "timelineEnd"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    start = clip_start(clip)
    duration = as_float(clip.get("durationSeconds") or clip.get("duration"))
    if start is not None and duration is not None:
        return start + duration
    return None


def is_bridge_clip(clip: dict[str, Any]) -> bool:
    text = lower_text(
        " ".join(
            str(clip.get(key) or "")
            for key in ("role", "purpose", "name", "type", "label", "sourcePath")
        )
    )
    return any(term in text for term in BRIDGE_TERMS)


def bridge_evidence_for_boundary(
    bridge_clips: list[dict[str, Any]],
    boundary_index: int,
    anchor: float | None,
    window_seconds: float,
) -> list[dict[str, Any]]:
    matches: list[tuple[float, dict[str, Any]]] = []
    for clip in bridge_clips:
        start = clip_start(clip)
        end = clip_end(clip)
        chapter_index = clip.get("chapterIndex")
        chapter_match = chapter_index in {boundary_index, boundary_index + 1}
        distance = 0.0
        if anchor is not None and start is not None and end is not None:
            if start <= anchor <= end:
                distance = 0.0
            else:
                distance = min(abs(anchor - start), abs(anchor - end))
            if distance > window_seconds and not chapter_match:
                continue
        elif not chapter_match:
            continue
        evidence = {
            "role": clip.get("role"),
            "chapterIndex": chapter_index,
            "timelineStartSeconds": start,
            "timelineEndSeconds": end,
            "distanceSeconds": round(distance, 3),
            "sourcePath": clip.get("sourcePath"),
            "purpose": clip.get("purpose"),
        }
        matches.append((distance, evidence))
    matches.sort(key=lambda item: (item[0], str(item[1].get("timelineStartSeconds"))))
    return [item for _, item in matches[:5]]


def required_categories(from_chapter: dict[str, Any], to_chapter: dict[str, Any]) -> list[str]:
    text = lower_text(chapter_text(from_chapter) + " " + chapter_text(to_chapter))
    categories = ["route_signage_or_geographic_hint", "street_ambient_texture"]
    if any(term in text for term in TRANSPORT_TERMS):
        categories.append("transport_motion")
    if city_token(from_chapter) and city_token(to_chapter) and city_token(from_chapter) != city_token(to_chapter):
        categories.extend(["transport_motion", "establishing_skyline_or_aerial"])
    if any(term in text for term in FOOD_TERMS):
        categories.append("food_or_table_detail")
    if any(term in text for term in HOTEL_TERMS):
        categories.append("hotel_window_lobby_or_convenience_detail")
    if any(term in text for term in QUIET_TERMS):
        categories.append("quiet_weather_temple_or_garden_detail")
    if not any(item.endswith("detail") for item in categories):
        categories.append("lived_in_daily_detail")
    return unique(categories)


def local_search_hints(from_chapter: dict[str, Any], to_chapter: dict[str, Any], categories: list[str]) -> list[str]:
    place_bits = unique(
        [
            clean_words(from_chapter.get("city") or from_chapter.get("place")),
            clean_words(to_chapter.get("city") or to_chapter.get("place")),
            clean_words(from_chapter.get("country") or to_chapter.get("country")),
        ]
    )
    hints = [f"local footage with visible cue: {bit}" for bit in place_bits[:4]]
    if "transport_motion" in categories:
        hints.extend(["airport/station/platform/train-window/metro/taxi movement", "tickets, signage, escalator, luggage, road or rail detail"])
    if "street_ambient_texture" in categories:
        hints.extend(["street walk, storefronts, traffic lights, crowds, night lights", "wide-to-detail pairing: skyline or landmark -> hands/food/signage"])
    if "food_or_table_detail" in categories:
        hints.append("restaurant table, food prep, menu, drink, breakfast, convenience-store detail")
    if "hotel_window_lobby_or_convenience_detail" in categories:
        hints.append("hotel window, lobby, elevator, corridor, convenience-store transition")
    if "quiet_weather_temple_or_garden_detail" in categories:
        hints.append("rain, garden, temple approach, shrine gate, quiet crowd ambience")
    return unique(hints)


def provider_searches(query: str) -> list[dict[str, Any]]:
    q = quote_plus(query)
    mixkit_q = quote_plus(f"site:mixkit.co/free-stock-video/ {query}")
    return [
        {
            "provider": "Pixabay Video",
            "searchUrl": f"https://pixabay.com/videos/search/{q}/",
            "licenseUrl": PROVIDERS["Pixabay Video"]["licenseUrl"],
        },
        {
            "provider": "Pexels Video",
            "searchUrl": f"https://www.pexels.com/search/videos/{q}/",
            "licenseUrl": PROVIDERS["Pexels Video"]["licenseUrl"],
        },
        {
            "provider": "Mixkit Video",
            "searchUrl": f"https://www.google.com/search?q={mixkit_q}",
            "licenseUrl": PROVIDERS["Mixkit Video"]["licenseUrl"],
        },
        {
            "provider": "Artgrid",
            "searchUrl": f"https://artgrid.io/search?q={q}",
            "licenseUrl": PROVIDERS["Artgrid"]["licenseUrl"],
        },
        {
            "provider": "Storyblocks",
            "searchUrl": f"https://www.storyblocks.com/video/search/{q}",
            "licenseUrl": PROVIDERS["Storyblocks"]["licenseUrl"],
        },
    ]


def stock_queries(from_chapter: dict[str, Any], to_chapter: dict[str, Any], categories: list[str]) -> list[dict[str, Any]]:
    geo = " ".join(
        unique(
            [
                clean_words(to_chapter.get("city") or to_chapter.get("place")),
                clean_words(to_chapter.get("country") or from_chapter.get("country")),
            ]
        )
    ).strip() or "travel city"
    query_intents = ["establishing skyline travel ambience", "street walking signage ambience"]
    if "transport_motion" in categories:
        query_intents.append("station train window airport transfer")
    if "food_or_table_detail" in categories:
        query_intents.append("restaurant food table travel detail")
    if "quiet_weather_temple_or_garden_detail" in categories:
        query_intents.append("quiet temple garden rain travel")
    rows: list[dict[str, Any]] = []
    for intent in unique(query_intents):
        query = f"{geo} {intent}"
        rows.append(
            {
                "need": intent,
                "query": query,
                "providerSearches": provider_searches(query),
                "licenseDecisionRequired": True,
                "downloadAllowedByThisScript": False,
            }
        )
    return rows


def section_plan(chapter_count: int, boundary_count: int) -> list[dict[str, Any]]:
    return [
        {
            "section": "opening_city_signal",
            "targetDurationSeconds": {"min": 20, "ideal": 45, "max": 75},
            "role": "Open on approved aerial/establishing/scenic footage plus one clean city title; keep BGM-only audio.",
        },
        {
            "section": "chapter_boundaries",
            "targetDurationSeconds": {"min": boundary_count * 15, "ideal": boundary_count * 30, "max": boundary_count * 45},
            "role": "Each day/place boundary must use local route texture first, then licensed stock only when local footage is missing.",
        },
        {
            "section": "ending_aftertaste",
            "targetDurationSeconds": {"min": 20, "ideal": 45, "max": 75},
            "role": "End with scenic return/departure/detail footage and music tail, not a black card or abrupt hard cut.",
        },
        {
            "section": "global_lived_in_texture",
            "targetDurationSeconds": {"min": max(60, chapter_count * 12), "ideal": max(120, chapter_count * 20), "max": max(180, chapter_count * 30)},
            "role": "Across the film, preserve street, food, hotel, weather, signage, and transport details so landmarks do not become a slideshow.",
        },
    ]


def build_plan(package_dir: Path, bridge_window_seconds: float) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    route_audit = load_json(package_dir / "route_texture_contract_audit.json") or {}
    chapters = active_chapters(delivery, blueprint)
    plans = plan_rows(delivery, blueprint)
    clips = [row for row in blueprint.get("clips") or [] if isinstance(row, dict)]
    bridge_clips = [row for row in clips if is_bridge_clip(row)]

    boundary_rows: list[dict[str, Any]] = []
    for index in range(1, len(chapters)):
        from_chapter = chapters[index - 1]
        to_chapter = chapters[index]
        planned = plans.get(index) or {}
        anchor = as_float(planned.get("timelineStartSeconds"))
        categories = required_categories(from_chapter, to_chapter)
        evidence = bridge_evidence_for_boundary(bridge_clips, index, anchor, bridge_window_seconds)
        status = "has_bridge_evidence" if evidence else "needs_bridge_selection"
        route_intent = f"Bridge Chapter {from_chapter['index']} to Chapter {to_chapter['index']}: {from_chapter['chapter']} -> {to_chapter['chapter']}"
        boundary_rows.append(
            {
                "boundaryIndex": index,
                "afterChapter": from_chapter["index"],
                "beforeChapter": to_chapter["index"],
                "status": status,
                "routeIntent": route_intent,
                "fromChapter": from_chapter,
                "toChapter": to_chapter,
                "targetDurationSeconds": {"min": 15, "ideal": 30, "max": 45},
                "requiredVisualCategories": categories,
                "localFootageSearchHints": local_search_hints(from_chapter, to_chapter, categories),
                "stockFallbackQueries": stock_queries(from_chapter, to_chapter, categories),
                "audioPolicy": {
                    "mode": "bgm_only_no_camera_voice",
                    "allowedSourceAudio": "only intentional low ambient texture after explicit editor approval",
                    "blocked": ["camera chatter", "voiceover", "unplanned A1/A2 dialogue in scenic/title/transition windows"],
                },
                "subtitlePolicy": {
                    "style": "short route/emotion caption if needed; no subtitle over opening/chapter title safe zone",
                    "examples": [
                        "From station noise into the city rhythm.",
                        "The route shifts before the scenery does.",
                    ],
                },
                "effectPolicy": {
                    "style": "restrained dissolve, match cut, sound bridge, or simple route marker; no template-heavy effects",
                    "avoid": ["black cards", "hard cut between cities", "generic AI-looking transition overlays"],
                },
                "existingTransitionPlan": {
                    "bridge": planned.get("bridge"),
                    "suggestion": planned.get("suggestion"),
                    "timelineStartSeconds": anchor,
                    "durationSeconds": planned.get("durationSeconds"),
                    "status": planned.get("status"),
                },
                "existingBridgeEvidence": evidence,
                "decision": dict(DECISION_FIELDS),
            }
        )

    boundaries_with_evidence = sum(1 for row in boundary_rows if row["existingBridgeEvidence"])
    missing_boundary_count = len(boundary_rows) - boundaries_with_evidence
    if boundary_rows:
        status = "ready_with_bridge_evidence" if missing_boundary_count == 0 else "needs_bridge_selection"
    else:
        status = "ready_no_interchapter_boundaries" if chapters else "blocked_missing_chapters"

    route_summary = route_audit.get("summary") if isinstance(route_audit.get("summary"), dict) else {}
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "deliveryPlan": str(package_dir / "delivery_plan.json"),
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "routeTextureAudit": str(package_dir / "route_texture_contract_audit.json"),
        },
        "summary": {
            "chapterCount": len(chapters),
            "boundaryRowCount": len(boundary_rows),
            "boundariesWithEvidence": boundaries_with_evidence,
            "missingBoundaryCount": missing_boundary_count,
            "existingTransitionPlanCount": len(plans),
            "existingBridgeClipCount": len(bridge_clips),
            "routeTextureStatus": route_audit.get("status"),
            "routeTextureMatchedTransitions": route_summary.get("matchedTransitions"),
        },
        "policy": {
            "localFootageFirst": True,
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
            "licensedStockOnlyWhenLocalMissing": True,
            "audioMode": "bgm_only_no_camera_voice",
            "noBlackCardOrHardCutFallback": True,
        },
        "providerDirectory": PROVIDERS,
        "sectionPlan": section_plan(len(chapters), len(boundary_rows)),
        "boundaryRows": boundary_rows,
        "selectionRubric": {
            "pass": [
                "Every chapter/day/place boundary has at least one local bridge clip or a verified licensed stock/aerial fallback.",
                "The bridge footage visually explains movement, street ambience, lived-in detail, weather, food, hotel, signage, or city scale.",
                "Scenic/title/transition windows are BGM-led and contain no accidental camera voice or generated voiceover.",
                "Any stock/aerial fallback records exact source URL, license URL, local path, and approval evidence.",
                "Transitions feel like observed travel, not black cards, hard cuts, or template-heavy AI effects.",
            ],
            "reject": [
                "A boundary jumps between cities/days using only a title card or hard cut.",
                "A bridge row has no selected local clip and no verified licensed fallback.",
                "Opening, title, or transition footage exposes source-camera speech after BGM-only/no-voiceover requirements.",
                "A stock/aerial clip is described as downloaded or licensed without an exact URL and local path.",
                "The plan overfits one previous trip by forcing Tokyo/Osaka/Japan labels onto a different project.",
            ],
        },
        "nextActions": [
            "Search local footage first using each boundary row's localFootageSearchHints.",
            "Fill decision.selectedLocalClips or verified stock/aerial fields for any needs_bridge_selection row.",
            "Update the Resolve blueprint with role=transition_bridge_footage and rerun audit_route_texture_contract.py.",
            "Rerun prepare_transition_bridge_plan.py after bridge clips are placed so final maturity evidence is fresh.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
            "claimUsableWithoutLicense": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Bridge Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Section Plan",
    ]
    for item in plan["sectionPlan"]:
        lines.append(f"- `{item['section']}`: {item['role']} Target `{item['targetDurationSeconds']}`")
    lines.extend(["", "## Boundary Rows"])
    if not plan["boundaryRows"]:
        lines.append("- No interchapter boundaries were found. Verify that the delivery plan has real chapters before cutting.")
    for row in plan["boundaryRows"]:
        lines.extend(
            [
                "",
                f"### Boundary {row['boundaryIndex']}: Chapter {row['afterChapter']} -> {row['beforeChapter']}",
                f"- Status: `{row['status']}`",
                f"- Intent: {row['routeIntent']}",
                f"- Target duration: `{row['targetDurationSeconds']}`",
                f"- Required visuals: {', '.join(row['requiredVisualCategories'])}",
                "- Local search hints:",
            ]
        )
        lines.extend(f"  - {item}" for item in row["localFootageSearchHints"])
        lines.append("- Stock/aerial fallback searches:")
        for query in row["stockFallbackQueries"]:
            lines.append(f"  - {query['query']}")
            for option in query["providerSearches"][:3]:
                lines.append(f"    - {option['provider']}: {option['searchUrl']}")
                lines.append(f"      - License: {option['licenseUrl']}")
        lines.append("- Existing bridge evidence:")
        if row["existingBridgeEvidence"]:
            for item in row["existingBridgeEvidence"]:
                lines.append(
                    f"  - `{item.get('role')}` {item.get('timelineStartSeconds')}s-{item.get('timelineEndSeconds')}s: `{item.get('sourcePath')}`"
                )
        else:
            lines.append("  - None yet. This boundary needs local bridge selection or a verified licensed fallback.")
        lines.append("- Decision fields to fill:")
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a transition bridge plan for a travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_bridge_plan.")
    parser.add_argument("--bridge-window-seconds", type=float, default=40.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_bridge_plan"
    plan = build_plan(package_dir, args.bridge_window_seconds)
    write_json(output_dir / "transition_bridge_plan.json", plan)
    write_markdown(output_dir / "transition_bridge_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": plan["status"],
                    "outputDir": str(output_dir),
                    "boundaryRowCount": plan["summary"]["boundaryRowCount"],
                    "missingBoundaryCount": plan["summary"]["missingBoundaryCount"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
