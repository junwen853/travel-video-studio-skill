#!/usr/bin/env python3
"""Prepare a proactive BGM sourcing brief for long-form travel edits."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


PROVIDERS = {
    "Mixkit Music": {
        "licenseUrl": "https://mixkit.co/license/#musicFree",
        "homeUrl": "https://mixkit.co/free-stock-music/",
        "costModel": "free music library; exact track and license page still must be recorded",
        "bestFor": "first-pass serene, cinematic, ambient, and travel-friendly beds",
    },
    "Pixabay Music": {
        "licenseUrl": "https://pixabay.com/service/license-summary/",
        "faqUrl": "https://pixabay.com/service/faq/",
        "homeUrl": "https://pixabay.com/music/",
        "costModel": "free library; keep exact track URL, license summary, and download/certificate evidence",
        "bestFor": "backup beds and simple documentary cues; note possible Content ID claims",
    },
    "Artlist": {
        "licenseUrl": "https://artlist.io/license",
        "homeUrl": "https://artlist.io/",
        "costModel": "subscription/plan licensing",
        "bestFor": "polished long-form documentary travel BGM",
    },
    "Epidemic Sound": {
        "licenseUrl": "https://www.epidemicsound.com/licensing/",
        "homeUrl": "https://www.epidemicsound.com/",
        "costModel": "subscription/plan licensing",
        "bestFor": "polished music beds and alternates",
    },
    "Motion Array": {
        "licenseUrl": "https://motionarray.com/license/",
        "homeUrl": "https://motionarray.com/browse/royalty-free-music/",
        "costModel": "subscription license; verify active plan and project coverage",
        "bestFor": "music plus motion assets when a project already uses Motion Array",
    },
}


MOOD_TERMS = {
    "opening": ["serene", "warm piano", "ambient", "cinematic", "soft strings"],
    "city": ["chill", "documentary", "light pulse", "soft synth", "urban travel"],
    "transport": ["motion", "hopeful", "minimal beat", "road trip", "train window"],
    "temple": ["reflective", "calm", "acoustic", "soft cinematic", "spacious"],
    "ending": ["nostalgic", "gentle", "warm", "reflective", "aftertaste"],
}


DECISION_FIELDS = {
    "selectedAssetTitle": "",
    "selectedAssetUrl": "",
    "provider": "",
    "licenseUrl": "",
    "localPathAfterDownload": "",
    "durationSeconds": None,
    "loopOrCrossfadePlan": "",
    "attributionRequired": None,
    "attributionText": "",
    "contentIdRiskChecked": False,
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


def clean_words(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:180]


def package_title(package_dir: Path, delivery: dict[str, Any], blueprint: dict[str, Any]) -> str:
    for value in (
        delivery.get("title"),
        delivery.get("projectName"),
        blueprint.get("projectName"),
        blueprint.get("timelineName"),
        package_dir.parent.name,
        package_dir.name,
    ):
        text = clean_words(value)
        if text:
            return text
    return "travel film"


def infer_duration(package_dir: Path, blueprint: dict[str, Any]) -> float:
    for path in (package_dir / "render_delivery_verification.json", package_dir / "FINAL_DELIVERY_REPORT.json"):
        data = load_json(path) or {}
        for key in ("durationSeconds", "duration"):
            try:
                value = float(data.get(key))
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
    for key in ("targetDurationSeconds", "actualVideoCoverageSeconds"):
        try:
            value = float(blueprint.get(key))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return 20 * 60.0


def verified_bgm_items(package_dir: Path) -> list[dict[str, Any]]:
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    items = ledger.get("items") if isinstance(ledger.get("items"), list) else []
    verified: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "bgm":
            continue
        status = str(item.get("licenseStatus") or "").lower()
        if status.startswith("verified") and (item.get("localPath") or item.get("selectedAssetUrl")):
            verified.append(item)
    return verified


def mood_bucket(text: str, index: int, total: int) -> str:
    lower = text.lower()
    if index == 1:
        return "opening"
    if index == total:
        return "ending"
    if any(token in lower for token in ("train", "rail", "airport", "flight", "车", "机场", "地铁", "metro", "taxi")):
        return "transport"
    if any(token in lower for token in ("temple", "shrine", "寺", "神社", "asakusa", "senso")):
        return "temple"
    return "city"


def base_search_terms(title: str, country: str, place: str, mood: str) -> list[str]:
    terms = MOOD_TERMS.get(mood, MOOD_TERMS["city"])
    geographic = " ".join(item for item in (country, place) if item).strip()
    return [
        f"{geographic} long form travel documentary music {terms[0]} {terms[1]}".strip(),
        f"cinematic travel vlog background music {terms[2]} {terms[3]}".strip(),
        f"{title} calm documentary BGM instrumental no vocals".strip(),
        f"travel film {terms[-1]} piano ambient soft strings".strip(),
    ]


def provider_searches(query: str) -> list[dict[str, Any]]:
    q = quote_plus(query)
    mixkit_site_q = quote_plus(f"site:mixkit.co/free-stock-music/ {query}")
    return [
        {
            "provider": "Mixkit Music",
            "searchUrl": f"https://www.google.com/search?q={mixkit_site_q}",
            "licenseUrl": PROVIDERS["Mixkit Music"]["licenseUrl"],
            "notes": "Open exact Mixkit track pages from search results; record the track URL, license page, and local download path.",
        },
        {
            "provider": "Pixabay Music",
            "searchUrl": f"https://pixabay.com/music/search/{q}/",
            "licenseUrl": PROVIDERS["Pixabay Music"]["licenseUrl"],
            "notes": "Record exact track URL and license/certificate evidence; note Pixabay FAQ Content ID caveat.",
        },
        {
            "provider": "Artlist",
            "searchUrl": f"https://artlist.io/search?search={q}",
            "licenseUrl": PROVIDERS["Artlist"]["licenseUrl"],
            "notes": "Use only with a verified active plan or project license evidence.",
        },
        {
            "provider": "Epidemic Sound",
            "searchUrl": f"https://www.epidemicsound.com/search/?term={q}",
            "licenseUrl": PROVIDERS["Epidemic Sound"]["licenseUrl"],
            "notes": "Use only with a verified plan/project coverage for the intended channel.",
        },
        {
            "provider": "Motion Array",
            "searchUrl": f"https://motionarray.com/browse/royalty-free-music/?q={q}",
            "licenseUrl": PROVIDERS["Motion Array"]["licenseUrl"],
            "notes": "Use only with subscription/project evidence.",
        },
    ]


def chapter_rows(delivery: dict[str, Any], title: str) -> list[dict[str, Any]]:
    chapters = [row for row in delivery.get("chapters") or [] if isinstance(row, dict) and not row.get("markedDoNotCut")]
    total = len(chapters) or 1
    rows: list[dict[str, Any]] = []
    for fallback_index, chapter in enumerate(chapters, start=1):
        index = int(chapter.get("index") or fallback_index)
        place = clean_words(chapter.get("place") or chapter.get("chapter") or chapter.get("city") or "travel route")
        country = clean_words(chapter.get("country") or "")
        text = " ".join(str(chapter.get(key) or "") for key in ("chapter", "place", "city", "country"))
        mood = mood_bucket(text, fallback_index, total)
        queries = base_search_terms(title, country, place, mood)
        rows.append(
            {
                "chapterIndex": index,
                "chapter": chapter.get("chapter"),
                "place": place,
                "moodBucket": mood,
                "preferredMoodTerms": MOOD_TERMS.get(mood),
                "searchPhrases": queries,
                "providerSearches": [option for query in queries[:2] for option in provider_searches(query)],
                "decision": dict(DECISION_FIELDS),
            }
        )
    return rows


def section_plan(duration: float, chapter_count: int) -> list[dict[str, Any]]:
    return [
        {
            "section": "continuous_bed",
            "targetDurationSeconds": round(duration, 3),
            "role": "One or more approved instrumental tracks crossfaded into an uninterrupted BGM bed.",
            "mustAvoid": ["lyrics that fight captions", "aggressive trailer hits", "abrupt endings", "camera/source voice in scenic sections"],
        },
        {
            "section": "opening_and_title",
            "targetDurationSeconds": 45,
            "role": "BGM-led scenic opening/title section; no source-camera or voiceover leakage.",
            "mustAvoid": ["voice under hero title", "music with heavy drops before route context is established"],
        },
        {
            "section": "day_place_transitions",
            "targetDurationSeconds": max(20, chapter_count * 12),
            "role": "Subtle continuity music over station, street, skyline, food, hotel-window, vehicle, or aerial bridge footage.",
            "mustAvoid": ["hard silence", "unmotivated pop-song chorus", "dialogue accidentally driving the transition"],
        },
        {
            "section": "ending_aftertaste",
            "targetDurationSeconds": 45,
            "role": "Reflective final cue that lets the route settle before the film ends.",
            "mustAvoid": ["sudden cutoff", "generic outro sting", "spoken narration after user rejected voiceover"],
        },
    ]


def build_brief(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery = load_json(package_dir / "delivery_plan.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    reference = load_json(package_dir / "reference" / "reference_analysis.json") or load_json(
        Path("/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference/reference_analysis.json")
    ) or {}
    title = package_title(package_dir, delivery, blueprint)
    duration = infer_duration(package_dir, blueprint)
    rows = chapter_rows(delivery, title)
    verified = verified_bgm_items(package_dir)
    status = "ready_with_verified_bgm" if verified else "needs_bgm_selection"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "sourceDeliveryPlan": str(package_dir / "delivery_plan.json"),
        "targetTitle": title,
        "targetDurationSeconds": round(duration, 3),
        "verifiedBgmItems": verified,
        "providerDirectory": PROVIDERS,
        "sectionPlan": section_plan(duration, len(rows)),
        "chapterBgmRows": rows,
        "referencePacing": {
            "referenceAnalysis": reference.get("referencePath"),
            "averageShotLengthSeconds": (reference.get("pacingProfile") or {}).get("averageShotLengthSeconds"),
            "medianShotLengthSeconds": (reference.get("pacingProfile") or {}).get("medianShotLengthSeconds"),
            "meanVolumeDb": (reference.get("audioProfile") or {}).get("meanVolumeDb"),
        },
        "selectionRubric": {
            "pass": [
                "instrumental or no distracting vocals",
                "supports Chinese captions and route pacing",
                "loopable/crossfade-friendly for long-form BGM bed",
                "works under scenic opening, bridge, and ending sections",
                "exact asset URL, license URL, local path, and approval evidence can be recorded",
            ],
            "reject": [
                "short-video hyper energy unless a specific scene needs it",
                "heavy lyrics, comedy stings, sports/trailer aggression, abrupt watermark tags",
                "unclear license, missing exact track page, or missing download/certificate evidence",
                "music that would make source-camera voice feel intentional during scenic/title windows",
            ],
        },
        "nextActions": [
            "Open the first-pass Mixkit/Pixabay provider searches for each chapter mood.",
            "Pick one exact main bed and optionally one transition/ending alternate.",
            "Fill decision fields with selectedAssetUrl, licenseUrl, localPathAfterDownload, attribution, and approval evidence.",
            "Update asset_ledger/asset_license_ledger.json and rerun prepare_asset_sourcing_packet.py plus audit_bgm_audio_contract.py.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
            "claimUsableWithoutLicense": False,
        },
    }


def write_markdown(path: Path, brief: dict[str, Any]) -> None:
    lines = [
        "# BGM Sourcing Brief",
        "",
        f"Status: `{brief['status']}`",
        f"Package: `{brief['packageDir']}`",
        f"Target title: `{brief['targetTitle']}`",
        f"Target duration: `{brief['targetDurationSeconds']}` seconds",
        "",
        "## Verified BGM",
    ]
    if brief["verifiedBgmItems"]:
        for item in brief["verifiedBgmItems"]:
            lines.append(f"- {item.get('name') or item.get('selectedAssetUrl')}: `{item.get('localPath') or item.get('selectedAssetUrl')}`")
    else:
        lines.append("- None yet. Final render remains blocked until the asset ledger records a verified BGM row.")
    lines.extend(["", "## Section Plan"])
    for item in brief["sectionPlan"]:
        lines.append(f"- `{item['section']}`: {item['role']} Target `{item['targetDurationSeconds']}`s")
    lines.extend(["", "## Chapter Search Rows"])
    for row in brief["chapterBgmRows"]:
        lines.extend(["", f"### Chapter {row['chapterIndex']}: {row.get('chapter') or row.get('place')}"])
        lines.append(f"- Mood: `{row['moodBucket']}` ({', '.join(row.get('preferredMoodTerms') or [])})")
        lines.append("- Search phrases:")
        for query in row["searchPhrases"]:
            lines.append(f"  - {query}")
        lines.append("- First provider searches:")
        for option in row["providerSearches"][:6]:
            lines.append(f"  - {option['provider']}: {option['searchUrl']}")
            lines.append(f"    - License: {option['licenseUrl']}")
        lines.append("- Decision fields to fill:")
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in brief["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in brief["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in brief["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a BGM sourcing brief for a travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/bgm_sourcing.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "bgm_sourcing"
    brief = build_brief(package_dir)
    write_json(output_dir / "bgm_sourcing_brief.json", brief)
    write_markdown(output_dir / "bgm_sourcing_brief.md", brief)
    if args.json:
        print(json.dumps(brief, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": brief["status"], "outputDir": str(output_dir), "verifiedBgmCount": len(brief["verifiedBgmItems"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
