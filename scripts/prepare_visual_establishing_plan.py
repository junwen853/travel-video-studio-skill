#!/usr/bin/env python3
"""Prepare proactive aerial, landmark, and establishing-shot planning rows."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


PROVIDERS = {
    "Mixkit Video": {
        "homeUrl": "https://mixkit.co/free-stock-video/",
        "licenseUrl": "https://mixkit.co/license/#videoFree",
        "bestFor": "first-pass free aerial, skyline, and city establishing clips when exact clip pages are recorded",
    },
    "Pixabay Video": {
        "homeUrl": "https://pixabay.com/videos/",
        "licenseUrl": "https://pixabay.com/service/license-summary/",
        "bestFor": "free skyline, landmark, street, and transport footage with exact video URLs and license notes",
    },
    "Pexels Video": {
        "homeUrl": "https://www.pexels.com/videos/",
        "licenseUrl": "https://www.pexels.com/license/",
        "bestFor": "free street, skyline, and lived-in ambience fallbacks where exact clip URLs are recorded",
    },
    "Artgrid": {
        "homeUrl": "https://artgrid.io/",
        "licenseUrl": "https://artgrid.io/license",
        "bestFor": "paid premium travel footage when subscription/project coverage is verified",
    },
    "Storyblocks": {
        "homeUrl": "https://www.storyblocks.com/video",
        "licenseUrl": "https://www.storyblocks.com/license",
        "bestFor": "paid backup aerial, landmark, and motion footage with active license evidence",
    },
}


CITY_LANDMARK_HINTS = {
    "tokyo": [
        "Tokyo Tower",
        "Shibuya crossing",
        "Shinjuku skyline",
        "Tokyo Skytree",
        "Sumida River",
        "Tokyo Station",
        "Asakusa Senso-ji",
        "Ginza streets",
        "Akihabara neon streets",
    ],
    "osaka": [
        "Dotonbori",
        "Osaka Castle",
        "Umeda skyline",
        "Namba streets",
        "Tsutenkaku",
        "Kansai Airport",
        "Tombori River Walk",
    ],
    "kyoto": [
        "Fushimi Inari",
        "Kiyomizu-dera",
        "Gion streets",
        "Arashiyama",
        "Kyoto Station",
    ],
    "hong kong": [
        "Victoria Harbour",
        "Central skyline",
        "Star Ferry",
        "Tsim Sha Tsui promenade",
        "Peak Tram",
        "MTR station",
    ],
    "macau": [
        "Ruins of Saint Paul",
        "Senado Square",
        "Macau Tower",
        "Cotai skyline",
        "Taipa streets",
    ],
    "paris": [
        "Eiffel Tower",
        "Seine River",
        "Louvre",
        "Montmartre",
        "Arc de Triomphe",
        "Paris Metro",
    ],
    "london": [
        "Tower Bridge",
        "Thames River",
        "London skyline",
        "Westminster",
        "Underground station",
    ],
    "new york": [
        "Manhattan skyline",
        "Brooklyn Bridge",
        "Times Square",
        "Central Park",
        "subway station",
    ],
    "rome": [
        "Colosseum",
        "Roman Forum",
        "Trevi Fountain",
        "Spanish Steps",
        "Tiber River",
    ],
    "malta": [
        "Valletta skyline",
        "Grand Harbour",
        "Mdina streets",
        "Sliema waterfront",
        "coastal road",
    ],
}


ROLE_TERMS = {
    "opening_city_establishing": ("opening_city", "opening_visual_bed", "clean_opening", "opening"),
    "chapter_establishing": ("chapter_title_bridge", "title_bridge", "transition_bridge", "visual_establishing", "establishing_or_transition"),
    "ending_city_establishing": ("ending_city", "ending_visual_bed", "clean_ending", "ending"),
}


DECISION_FIELDS = {
    "selectedLocalClips": [],
    "selectedStockAssets": [],
    "selectedAerialAssets": [],
    "selectedAssetUrls": [],
    "licenseUrls": [],
    "localPathsAfterDownload": [],
    "resolveRole": "visual_establishing_footage",
    "timelinePlacementNotes": "",
    "titleText": "",
    "audioTreatment": "bgm_only_no_camera_voice",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
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


def chapter_text(chapter: dict[str, Any]) -> str:
    return " ".join(clean_words(chapter.get(key)) for key in ("chapter", "place", "city", "country")).strip()


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
    out: list[dict[str, Any]] = []
    for fallback_index, row in enumerate(markers, start=1):
        label = clean_words(row.get("name") or row.get("label") or row.get("note") or f"Chapter {fallback_index}")
        out.append({"index": fallback_index, "chapter": label, "place": label, "city": "", "country": ""})
    return out


def geography_text(chapter: dict[str, Any] | None, fallback: str = "travel city") -> str:
    if not chapter:
        return fallback
    return (
        clean_words(chapter.get("city"))
        or clean_words(chapter.get("place"))
        or clean_words(chapter.get("chapter"))
        or clean_words(chapter.get("country"))
        or fallback
    )


def landmark_hints_for(chapter: dict[str, Any] | None) -> list[str]:
    text = lower_text(chapter_text(chapter or {}))
    hints: list[str] = []
    for token, places in CITY_LANDMARK_HINTS.items():
        if token in text:
            hints.extend(places)
    if not hints:
        geo = geography_text(chapter)
        hints.extend(
            [
                f"{geo} skyline",
                f"{geo} landmark",
                f"{geo} station",
                f"{geo} street signage",
                f"{geo} aerial or high-view establishing",
            ]
        )
    return unique(hints)[:9]


def provider_searches(query: str) -> list[dict[str, Any]]:
    q = quote_plus(query)
    mixkit_q = quote_plus(f"site:mixkit.co/free-stock-video/ {query}")
    return [
        {
            "provider": "Mixkit Video",
            "searchUrl": f"https://www.google.com/search?q={mixkit_q}",
            "licenseUrl": PROVIDERS["Mixkit Video"]["licenseUrl"],
        },
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


def search_rows(chapter: dict[str, Any] | None, role: str) -> list[dict[str, Any]]:
    geo = geography_text(chapter)
    intents = {
        "opening_city_establishing": ["aerial skyline 4K", "city landmark establishing shot", "street opening travel ambience"],
        "chapter_establishing": ["landmark establishing shot", "street signage travel ambience", "station or transport establishing"],
        "ending_city_establishing": ["sunset skyline ending shot", "airport departure establishing", "reflective city aerial"],
    }.get(role, ["travel establishing shot"])
    rows: list[dict[str, Any]] = []
    for hint in landmark_hints_for(chapter)[:5]:
        for intent in intents[:2]:
            query = f"{hint} {geo} {intent} licensed stock footage"
            rows.append(
                {
                    "need": intent,
                    "query": query,
                    "providerSearches": provider_searches(query),
                    "licenseDecisionRequired": True,
                    "downloadAllowedByThisScript": False,
                }
            )
    return rows[:8]


def local_search_hints(chapter: dict[str, Any] | None, role: str) -> list[str]:
    geo = geography_text(chapter)
    hints = [
        f"local wide shot or high-view establishing cue for {geo}",
        f"local footage with readable sign, station, skyline, or landmark cue for {geo}",
        "wide-to-detail pair: skyline/landmark first, then street/food/hotel/signage texture",
        "avoid black slates, generic country labels, phone-obstructed frames, and template route text",
    ]
    if role == "opening_city_establishing":
        hints.append("opening must breathe with BGM-only audio before captions take over")
    elif role == "ending_city_establishing":
        hints.append("ending should leave scenic aftertaste with music tail, not abrupt narration or hard stop")
    else:
        hints.append("chapter establishing should connect to nearby route texture, not replace it with a slideshow")
    return unique(hints)


def clip_matches_role(clip: dict[str, Any], role: str) -> bool:
    text = lower_text(
        " ".join(
            str(clip.get(key) or "")
            for key in ("role", "purpose", "name", "type", "label", "sourcePath")
        )
    )
    return any(term in text for term in ROLE_TERMS.get(role, ()))


def clip_evidence_for_row(
    clips: list[dict[str, Any]],
    role: str,
    chapter_index: int | None,
    anchor: float | None,
    window_seconds: float,
) -> list[dict[str, Any]]:
    matches: list[tuple[float, dict[str, Any]]] = []
    for clip in clips:
        if not clip_matches_role(clip, role):
            continue
        role_text = lower_text(clip.get("role"))
        clip_chapter = clip.get("chapterIndex")
        chapter_match = chapter_index is not None and str(clip_chapter or "") == str(chapter_index)
        start = clip_start(clip)
        end = clip_end(clip)
        distance = 0.0
        if anchor is not None and start is not None and end is not None:
            if start <= anchor <= end:
                distance = 0.0
            else:
                distance = min(abs(anchor - start), abs(anchor - end))
            if distance > window_seconds and not chapter_match:
                continue
            if role == "chapter_establishing" and distance > window_seconds and "chapter_title_bridge" not in role_text:
                continue
        elif chapter_index is not None and not chapter_match and role == "chapter_establishing":
            continue
        evidence = {
            "role": clip.get("role"),
            "chapterIndex": clip_chapter,
            "timelineStartSeconds": start,
            "timelineEndSeconds": end,
            "distanceSeconds": round(distance, 3),
            "sourcePath": clip.get("sourcePath"),
            "purpose": clip.get("purpose"),
        }
        matches.append((distance, evidence))
    matches.sort(key=lambda item: (item[0], str(item[1].get("timelineStartSeconds"))))
    return [item for _, item in matches[:6]]


def title_rows_for_plan(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    rows = data.get("titleRows") if isinstance(data.get("titleRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def title_evidence_for_row(title_rows: list[dict[str, Any]], role: str, chapter_index: int | None) -> dict[str, Any] | None:
    role_terms = {
        "opening_city_establishing": ("opening",),
        "chapter_establishing": ("chapter",),
        "ending_city_establishing": ("ending",),
    }.get(role, ())
    for row in title_rows:
        text = lower_text(" ".join(str(row.get(key) or "") for key in ("mode", "role", "titleRole", "kind", "titleText", "targetTitle")))
        if role_terms and not any(term in text for term in role_terms):
            continue
        if role == "chapter_establishing" and chapter_index is not None:
            if str(row.get("chapterIndex") or row.get("chapter") or "") != str(chapter_index):
                continue
        return {
            "mode": row.get("mode"),
            "role": row.get("role") or row.get("titleRole") or row.get("kind"),
            "chapterIndex": row.get("chapterIndex"),
            "titleText": row.get("titleText") or row.get("targetTitle") or row.get("approvedTitleText"),
            "subtitleText": row.get("targetSubtitle") or row.get("approvedSubtitleText"),
            "backgroundSourcePath": row.get("backgroundSourcePath") or row.get("sourceBackground") or row.get("segmentPath"),
            "segmentPath": row.get("segmentPath"),
            "status": row.get("status"),
        }
    return None


def verified_aerial_items(package_dir: Path) -> list[dict[str, Any]]:
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    items = ledger.get("items") if isinstance(ledger.get("items"), list) else []
    verified: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "aerial_or_stock":
            continue
        status = lower_text(item.get("licenseStatus"))
        if status.startswith("verified") and (item.get("localPath") or item.get("selectedAssetUrl")):
            verified.append(
                {
                    "name": item.get("name"),
                    "localPath": item.get("localPath"),
                    "selectedAssetUrl": item.get("selectedAssetUrl"),
                    "licenseStatus": item.get("licenseStatus"),
                    "approvalEvidence": item.get("approvalEvidence"),
                }
            )
    return verified


def anchor_for_chapter(clips: list[dict[str, Any]], chapter_index: int) -> float | None:
    starts = [
        clip_start(clip)
        for clip in clips
        if str(clip.get("chapterIndex") or "") == str(chapter_index)
        and lower_text(clip.get("role")) in {"chapter_title_bridge", "title_bridge"}
    ]
    starts = [value for value in starts if value is not None]
    if starts:
        return min(starts)
    return None


def build_rows(
    package_dir: Path,
    chapters: list[dict[str, Any]],
    clips: list[dict[str, Any]],
    title_rows: list[dict[str, Any]],
    window_seconds: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first = chapters[0] if chapters else None
    last = chapters[-1] if chapters else None
    row_specs: list[tuple[str, dict[str, Any] | None, int | None, float | None]] = [
        ("opening_city_establishing", first, None, 0.0),
    ]
    for chapter in chapters:
        row_specs.append(("chapter_establishing", chapter, int(chapter["index"]), anchor_for_chapter(clips, int(chapter["index"]))))
    ending_anchor = None
    ending_starts = [
        clip_start(clip)
        for clip in clips
        if clip_matches_role(clip, "ending_city_establishing") and clip_start(clip) is not None
    ]
    if ending_starts:
        ending_anchor = min(ending_starts)
    row_specs.append(("ending_city_establishing", last, None, ending_anchor))

    for row_index, (role, chapter, chapter_index, anchor) in enumerate(row_specs, start=1):
        title_evidence = title_evidence_for_row(title_rows, role, chapter_index)
        evidence = clip_evidence_for_row(clips, role, chapter_index, anchor, window_seconds)
        status = "has_establishing_evidence" if evidence else "needs_establishing_selection"
        geography = geography_text(chapter)
        row = {
            "rowIndex": row_index,
            "role": role,
            "chapterIndex": chapter_index,
            "status": status,
            "title": clean_words((chapter or {}).get("chapter") or role.replace("_", " ").title()),
            "place": clean_words((chapter or {}).get("place") or geography),
            "city": clean_words((chapter or {}).get("city") or geography),
            "country": clean_words((chapter or {}).get("country") or ""),
            "timelineAnchorSeconds": anchor,
            "editorIntent": {
                "opening_city_establishing": "Make the city/place legible immediately with real scenic footage, clean title typography, and BGM-only audio.",
                "chapter_establishing": "Give the chapter a real place signal before detail shots take over.",
                "ending_city_establishing": "Close on scenic return/departure imagery with music aftertaste.",
            }[role],
            "requiredVisualCategories": [
                "city_or_place_identity",
                "landmark_or_skyline_signal",
                "local_route_texture",
                "scenic_breathing_room",
            ],
            "famousPlaceHints": landmark_hints_for(chapter),
            "localFootageSearchHints": local_search_hints(chapter, role),
            "stockAerialFallbackQueries": search_rows(chapter, role),
            "existingEstablishingEvidence": evidence,
            "titleTypographyEvidence": title_evidence,
            "decision": dict(DECISION_FIELDS),
        }
        row["decision"]["titleText"] = clean_words((title_evidence or {}).get("titleText") or "")
        rows.append(row)
    return rows


def build_plan(package_dir: Path, window_seconds: float) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    stock = load_json(package_dir / "stock_aerial_closure_audit.json") or {}
    title = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    chapters = active_chapters(delivery, blueprint)
    clips = [row for row in blueprint.get("clips") or [] if isinstance(row, dict)]
    title_rows = title_rows_for_plan(package_dir)
    rows = build_rows(package_dir, chapters, clips, title_rows, window_seconds)
    verified_aerials = verified_aerial_items(package_dir)
    rows_with_evidence = sum(1 for row in rows if row.get("existingEstablishingEvidence"))
    missing_count = len(rows) - rows_with_evidence
    rows_with_title = sum(1 for row in rows if row.get("titleTypographyEvidence"))
    stock_summary = stock.get("summary") if isinstance(stock.get("summary"), dict) else {}
    status = (
        "ready_with_establishing_evidence"
        if rows and missing_count == 0
        else ("needs_establishing_selection" if rows else "blocked_missing_chapters")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "deliveryPlan": str(package_dir / "delivery_plan.json"),
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "titleTypographyPlan": str(package_dir / "title_typography_plan" / "title_typography_plan.json"),
            "assetLedger": str(package_dir / "asset_ledger" / "asset_license_ledger.json"),
            "stockAerialClosureAudit": str(package_dir / "stock_aerial_closure_audit.json"),
        },
        "summary": {
            "chapterCount": len(chapters),
            "establishingRowCount": len(rows),
            "rowsWithEvidence": rows_with_evidence,
            "missingEstablishingCount": missing_count,
            "rowsWithTitleTypographyEvidence": rows_with_title,
            "verifiedAerialCount": len(verified_aerials),
            "stockAerialClosureStatus": stock.get("status"),
            "stockAerialUnresolvedPlaceholderCount": stock_summary.get("unresolvedPlaceholderCount"),
            "titleTypographyStatus": title.get("status"),
        },
        "policy": {
            "localFootageFirst": True,
            "licensedStockOnlyWhenLocalMissing": True,
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
            "audioMode": "bgm_only_no_camera_voice",
            "noBlackSlateFallback": True,
            "noFabricatedDroneClaim": True,
            "noPreviousTripDefaults": True,
        },
        "providerDirectory": PROVIDERS,
        "verifiedAerialItems": verified_aerials,
        "titleTypographySummary": title.get("summary") if isinstance(title.get("summary"), dict) else {},
        "stockAerialClosureSummary": stock_summary,
        "establishingRows": rows,
        "selectionRubric": {
            "pass": [
                "Opening, each chapter title, and ending have real scenic/local/aerial establishing evidence or a verified licensed fallback.",
                "The opening row makes the actual city/place legible with one clean title and BGM-only audio.",
                "Chapter rows use local route texture first; stock/aerial fallback is only selected when local footage cannot carry the place signal.",
                "Every stock/aerial fallback has exact asset URL, license URL, local path, and approval evidence before final render.",
                "Rows do not force a previous trip's city, country, route, title, or famous-place list onto a different project.",
            ],
            "reject": [
                "Opening, chapter, or ending title moments rely on black slates, random project IDs, or generic country/date labels.",
                "A stock/aerial clip is described as downloaded, licensed, or usable without exact asset and license evidence.",
                "The plan uses a city landmark that is not supported by the current trip/project route.",
                "Scenic establishing sections leak source-camera voice or generated voiceover when BGM-only/no-voiceover was requested.",
                "The plan jumps from landmark to landmark without street, station, food, hotel, weather, or route texture.",
            ],
        },
        "nextActions": [
            "Use localFootageSearchHints to pick real footage for any needs_establishing_selection row.",
            "Use stockAerialFallbackQueries only when local footage cannot provide the city/place signal.",
            "Record exact selected asset URLs, license URLs, local paths, and approval evidence in the asset ledger before final render.",
            "Regenerate scenic title bridges or repair the Resolve blueprint if titleTypographyEvidence or existingEstablishingEvidence is missing.",
            "Rerun prepare_visual_establishing_plan.py after asset decisions and timeline changes so maturity evidence is fresh.",
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
        "# Visual Establishing Plan",
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
        "## Verified Aerial / Stock",
    ]
    if plan["verifiedAerialItems"]:
        for item in plan["verifiedAerialItems"]:
            lines.append(f"- {item.get('name') or item.get('selectedAssetUrl')}: `{item.get('localPath') or item.get('selectedAssetUrl')}`")
    else:
        lines.append("- None verified yet. Local establishing footage may still be usable, but stock/aerial fallback cannot be claimed.")
    lines.extend(["", "## Establishing Rows"])
    if not plan["establishingRows"]:
        lines.append("- No chapters were found. Build or repair delivery_plan.json before cutting.")
    for row in plan["establishingRows"]:
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['role']}",
                f"- Status: `{row['status']}`",
                f"- Chapter: `{row.get('chapterIndex')}`",
                f"- Place: {row.get('place')}",
                f"- Intent: {row['editorIntent']}",
                f"- Famous/place hints: {', '.join(row['famousPlaceHints'])}",
                "- Local footage search hints:",
            ]
        )
        lines.extend(f"  - {item}" for item in row["localFootageSearchHints"])
        lines.append("- Stock/aerial fallback searches:")
        for query in row["stockAerialFallbackQueries"][:4]:
            lines.append(f"  - {query['query']}")
            for option in query["providerSearches"][:3]:
                lines.append(f"    - {option['provider']}: {option['searchUrl']}")
                lines.append(f"      - License: {option['licenseUrl']}")
        lines.append("- Existing establishing evidence:")
        if row["existingEstablishingEvidence"]:
            for item in row["existingEstablishingEvidence"]:
                lines.append(
                    f"  - `{item.get('role')}` {item.get('timelineStartSeconds')}s-{item.get('timelineEndSeconds')}s: `{item.get('sourcePath')}`"
                )
        else:
            lines.append("  - None yet.")
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
    parser = argparse.ArgumentParser(description="Prepare a visual establishing/aerial plan for a travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/visual_establishing_plan.")
    parser.add_argument("--evidence-window-seconds", type=float, default=90.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "visual_establishing_plan"
    plan = build_plan(package_dir, args.evidence_window_seconds)
    write_json(output_dir / "visual_establishing_plan.json", plan)
    write_markdown(output_dir / "visual_establishing_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": plan["status"],
                    "outputDir": str(output_dir),
                    "summary": plan["summary"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
