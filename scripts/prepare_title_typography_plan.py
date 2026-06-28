#!/usr/bin/env python3
"""Prepare a proactive clean-title and typography planning packet."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TITLE_ROLES = ("opening_city_aerial_title", "chapter_title_bridge", "ending_city_aerial_title")
OPENING_FORBIDDEN_SEPARATORS = ("/", "->", " - ", " TO ")
BAD_SOURCE_PARTS = {"title_cards"}
BAD_SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}

DECISION_FIELDS = {
    "approvedTitleText": "",
    "approvedSubtitleText": "",
    "approvedFontFamily": "",
    "approvedFontPathOrLicenseUrl": "",
    "approvedBackgroundSource": "",
    "approvedSegmentPath": "",
    "safeZoneChecked": False,
    "noStackedTextChecked": False,
    "titleZoneSubtitleSuppressionChecked": False,
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


def clean_words(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def clip_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "startSeconds", "timelineStart", "recordStartSeconds"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    return 0.0


def clip_end(clip: dict[str, Any]) -> float:
    for key in ("timelineEndSeconds", "endSeconds", "timelineEnd", "recordEndSeconds"):
        value = as_float(clip.get(key))
        if value is not None:
            return value
    start = clip_start(clip)
    for key in ("durationSeconds", "duration"):
        value = as_float(clip.get(key))
        if value is not None:
            return start + max(0.0, value)
    return start


def segment_start(segment: dict[str, Any]) -> float:
    for key in ("timeline_start", "timelineStartSeconds", "startSeconds"):
        value = as_float(segment.get(key))
        if value is not None:
            return value
    return 0.0


def segment_end(segment: dict[str, Any]) -> float:
    start = segment_start(segment)
    for key in ("duration", "durationSeconds"):
        value = as_float(segment.get(key))
        if value is not None:
            return start + max(0.0, value)
    return start


def path_exists(path_raw: Any) -> bool:
    if not path_raw:
        return False
    return Path(str(path_raw)).expanduser().exists()


def path_is_video(path_raw: Any) -> bool:
    if not path_raw:
        return False
    path = Path(str(path_raw)).expanduser()
    lower_parts = {part.lower() for part in path.parts}
    return path.exists() and path.suffix.lower() not in BAD_SOURCE_SUFFIXES and not (lower_parts & BAD_SOURCE_PARTS)


def title_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: list[dict[str, Any]] = []
    for clip in clips:
        if not isinstance(clip, dict):
            continue
        role = str(clip.get("role") or clip.get("purpose") or "").lower()
        if role in TITLE_ROLES or any(token in role for token in ("opening_city", "chapter_title", "ending_city")):
            out.append(clip)
    return sorted(out, key=clip_start)


def infer_mode(value: dict[str, Any]) -> str:
    role = str(value.get("role") or value.get("mode") or value.get("purpose") or "").lower()
    if "opening" in role:
        return "opening"
    if "ending" in role:
        return "ending"
    return "chapter"


def manifest_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in manifest.get("segments") or []:
        if isinstance(row, dict) and str(row.get("mode") or "").lower() in {"opening", "chapter", "ending"}:
            out.append(row)
    return sorted(out, key=segment_start)


def match_segment(clip: dict[str, Any], segments: list[dict[str, Any]]) -> dict[str, Any] | None:
    start = clip_start(clip)
    mode = infer_mode(clip)
    best: tuple[float, dict[str, Any]] | None = None
    for segment in segments:
        if str(segment.get("mode") or "").lower() != mode:
            continue
        distance = abs(segment_start(segment) - start)
        if distance <= 0.5 and (best is None or distance < best[0]):
            best = (distance, segment)
    return best[1] if best else None


def clean_opening_title(title: str) -> bool:
    title = title.strip().upper()
    return bool(title) and not any(token in title for token in OPENING_FORBIDDEN_SEPARATORS)


def forbidden_hits(values: list[str], forbidden: list[str]) -> list[str]:
    joined = "\n".join(values).upper()
    return sorted({term for term in forbidden if term and str(term).upper() in joined})


def font_evidence(manifest: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    font_path = clean_words(manifest.get("font"))
    items = ledger.get("items") if isinstance(ledger.get("items"), list) else []
    font_items = [item for item in items if isinstance(item, dict) and item.get("type") == "font"]
    verified = [
        item
        for item in font_items
        if str(item.get("licenseStatus") or "").lower() in {"verified", "system-font-render-only"}
        and (item.get("localPath") or item.get("selectedAssetUrl"))
    ]
    return {
        "manifestFont": font_path or None,
        "manifestFontExists": bool(font_path and Path(font_path).expanduser().exists()),
        "ledgerFontItemCount": len(font_items),
        "verifiedFontItemCount": len(verified),
        "verifiedFontItems": verified,
    }


def title_zone_evidence(blueprint: dict[str, Any]) -> dict[str, Any]:
    policy = blueprint.get("subtitleDeliveryPolicy") if isinstance(blueprint.get("subtitleDeliveryPolicy"), dict) else {}
    title_policy = policy.get("titleZoneSubtitlePolicy") if isinstance(policy.get("titleZoneSubtitlePolicy"), dict) else {}
    zones = title_policy.get("zones") if isinstance(title_policy.get("zones"), list) else []
    return {
        "mode": title_policy.get("mode"),
        "zoneCount": len(zones),
        "zones": zones[:20],
        "renderedCueCount": policy.get("renderedCueCount"),
    }


def title_contract_stack_evidence(title_audit: dict[str, Any]) -> dict[str, Any]:
    out = {
        "status": title_audit.get("status"),
        "stackCheckStatus": None,
        "subtitleZoneCheckStatus": None,
        "windowCount": 0,
        "extraTextLayerCount": None,
        "subtitleOverlayCount": None,
    }
    for check in title_audit.get("checks") or []:
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or "")
        evidence = check.get("evidence") if isinstance(check.get("evidence"), dict) else {}
        if "stacked text" in name.lower() or "subtitle overlay" in name.lower():
            windows = evidence.get("windows") if isinstance(evidence.get("windows"), list) else []
            out.update(
                {
                    "stackCheckStatus": check.get("status"),
                    "windowCount": len(windows),
                    "extraTextLayerCount": sum(int(row.get("extraTextLayerCount") or 0) for row in windows if isinstance(row, dict)),
                    "subtitleOverlayCount": sum(int(row.get("subtitleOverlayCount") or 0) for row in windows if isinstance(row, dict)),
                }
            )
        if "subtitle title-zone policy" in name.lower():
            out["subtitleZoneCheckStatus"] = check.get("status")
    return out


def build_plan(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    manifest_path = package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json"
    manifest = load_json(manifest_path) or {}
    title_audit = load_json(package_dir / "title_bridge_contract_audit.json") or {}
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    clips = title_clips(blueprint)
    segments = manifest_segments(manifest)
    forbidden = [str(item) for item in manifest.get("forbiddenVisibleText") or []]
    forbidden_opening = [str(item) for item in manifest.get("forbiddenOpeningText") or []] or forbidden
    rows: list[dict[str, Any]] = []
    for index, clip in enumerate(clips, start=1):
        segment = match_segment(clip, segments) or {}
        mode = infer_mode(clip)
        title = clean_words(clip.get("titleText") or clip.get("cityTitle") or segment.get("title") or clip.get("place"))
        subtitle = clean_words(clip.get("subtitle") if clip.get("subtitle") is not None else segment.get("subtitle"))
        values = [item for item in (title, subtitle, clean_words(clip.get("cityTitle"))) if item]
        row_forbidden = forbidden_opening if mode == "opening" else forbidden
        hits = forbidden_hits(values, row_forbidden)
        segment_path = segment.get("segment") or clip.get("sourcePath")
        background_source = segment.get("source") or clip.get("sourcePath")
        row = {
            "index": index,
            "mode": mode,
            "role": clip.get("role"),
            "chapterIndex": clip.get("chapterIndex"),
            "timelineStartSeconds": round(clip_start(clip), 3),
            "timelineEndSeconds": round(clip_end(clip), 3),
            "targetTitle": title,
            "targetSubtitle": subtitle,
            "openingSubtitleAllowed": mode != "opening",
            "forbiddenVisibleText": row_forbidden,
            "forbiddenHits": hits,
            "sourceBackground": background_source,
            "segmentPath": segment_path,
            "overlayPath": segment.get("overlay"),
            "sourceBackgroundExists": path_exists(background_source),
            "segmentExists": path_exists(segment_path),
            "overlayExists": path_exists(segment.get("overlay")),
            "segmentIsVideo": path_is_video(segment_path),
            "sourceIsVideo": path_is_video(background_source),
            "cleanTitlePass": clean_opening_title(title) if mode == "opening" else bool(title.strip()),
            "subtitlePolicyPass": not (mode == "opening" and subtitle.strip()),
            "forbiddenTextPass": not hits,
            "safeZone": {
                "mainTitle": "center hero-safe for opening; lower-left cinematic safe band for chapter/ending",
                "subtitle": "forbidden for opening; short optional chapter subtitle below main title",
                "renderedSubtitleOverlay": "must be suppressed or trimmed inside this title window",
            },
            "decision": dict(DECISION_FIELDS),
        }
        rows.append(row)

    opening_rows = [row for row in rows if row["mode"] == "opening"]
    chapter_rows = [row for row in rows if row["mode"] == "chapter"]
    ending_rows = [row for row in rows if row["mode"] == "ending"]
    font = font_evidence(manifest, ledger)
    title_zone = title_zone_evidence(blueprint)
    stack = title_contract_stack_evidence(title_audit)
    clean_rows = [
        row
        for row in rows
        if row["cleanTitlePass"]
        and row["subtitlePolicyPass"]
        and row["forbiddenTextPass"]
        and row["segmentExists"]
        and row["segmentIsVideo"]
    ]
    status = (
        "ready_with_clean_title_typography_plan"
        if rows
        and len(clean_rows) == len(rows)
        and len(opening_rows) == 1
        and len(chapter_rows) >= 1
        and len(ending_rows) >= 1
        and font["manifestFontExists"]
        and font["verifiedFontItemCount"] >= 1
        and title_zone["mode"] == "avoid_title_zones"
        and int(title_zone["zoneCount"] or 0) >= len(rows)
        and title_audit.get("status") == "passed"
        and stack.get("extraTextLayerCount") == 0
        and stack.get("subtitleOverlayCount") == 0
        else "needs_title_typography_decisions"
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
            "titleManifest": str(manifest_path),
            "titleBridgeContractAudit": str(package_dir / "title_bridge_contract_audit.json"),
            "assetLedger": str(package_dir / "asset_ledger" / "asset_license_ledger.json"),
        },
        "summary": {
            "titleRowCount": len(rows),
            "cleanRowCount": len(clean_rows),
            "openingRowCount": len(opening_rows),
            "chapterRowCount": len(chapter_rows),
            "endingRowCount": len(ending_rows),
            "thumbnailCoverPolicy": "parallel_world_establishing_background_plus_oversized_destination_title",
            "fontVerified": font["manifestFontExists"] and font["verifiedFontItemCount"] >= 1,
            "titleZoneMode": title_zone["mode"],
            "titleZoneCount": title_zone["zoneCount"],
            "titleContractStatus": title_audit.get("status"),
            "stackExtraTextLayerCount": stack.get("extraTextLayerCount"),
            "stackSubtitleOverlayCount": stack.get("subtitleOverlayCount"),
        },
        "policy": {
            "openingTitlePolicy": "single clean city/place title only; no secondary city, route/date label, subtitle, or stacked/ghosted text behind the hero title",
            "thumbnailCoverPolicy": "use one high-recognition aerial/skyline/coast/landmark/route background, oversized 1-5 word Chinese destination title, smaller English/place subtitle, yellow/orange/white high-contrast typography, and no internal labels or route/date clutter",
            "chapterTitlePolicy": "short readable place/day label on scenic video; route arrows allowed only for a movement chapter, never for the opening hero title",
            "endingTitlePolicy": "short closing place/region title with aftertaste; no project slug or internal route label",
            "fontPolicy": "use verified system-font-render-only or licensed font evidence; do not redistribute commercial font files",
            "subtitleTitleZonePolicy": "rendered subtitles must be suppressed or trimmed during all title windows",
            "noBlackSlatePolicy": "title backgrounds must be real scenic/video clips, not black cards, image slates, or title_cards outputs",
        },
        "fontEvidence": font,
        "titleZoneEvidence": title_zone,
        "stackEvidence": stack,
        "titleRows": rows,
        "selectionRubric": {
            "pass": [
                "Cover/hero title candidate uses a high-recognition establishing background, oversized destination title, and smaller English/place subtitle.",
                "Opening has exactly one clean title value and no subtitle or route/date text behind it.",
                "Every opening/chapter/ending title row uses a real video segment, not a black slate or image card.",
                "Font evidence is verified as render-only system font or licensed selected font.",
                "Rendered subtitle overlays are suppressed inside every title window.",
                "Title bridge contract passes with zero stacked text layers and zero subtitle overlays.",
            ],
            "reject": [
                "Cover/hero title uses a low-recognition closeup, timid small text, long sentence, AI-looking gradient, or cluttered handheld frame.",
                "Opening title includes a route label such as TOKYO / OSAKA, date, project slug, or secondary city.",
                "A title row has missing media, black title_cards media, PNG/JPG slate, or unverified stock background.",
                "A subtitle overlay or extra text clip overlaps the hero/chapter title window.",
                "Font falls back silently to a generic family without license/system-font evidence.",
                "The plan overfits a previous trip by forcing TOKYO/OSAKA/JAPAN onto a different route.",
            ],
        },
        "nextActions": [
            "If status is needs_title_typography_decisions, fix the title manifest or regenerate scenic title bridges before subtitle overlay generation.",
            "Use the titleRows decisions as the approved source for prepare_scenic_title_bridges.py and audit_title_bridge_contract.py.",
            "Rerun prepare_title_typography_plan.py after title media or font choices change.",
        ],
        "safety": {
            "writesResolve": False,
            "rendersTitleMedia": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Title Typography Plan",
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
        "## Policy",
    ]
    for key, value in plan["policy"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Font Evidence", "", "```json", json.dumps(plan["fontEvidence"], ensure_ascii=False, indent=2)[:3000], "```"])
    lines.extend(["", "## Title Rows"])
    for row in plan["titleRows"]:
        lines.extend(
            [
                "",
                f"### {row['index']}. {row['mode']} - {row.get('targetTitle')}",
                f"- Window: `{row['timelineStartSeconds']}`s to `{row['timelineEndSeconds']}`s",
                f"- Subtitle: `{row.get('targetSubtitle')}`",
                f"- Segment: `{row.get('segmentPath')}`",
                f"- Background: `{row.get('sourceBackground')}`",
                f"- Clean title pass: `{row['cleanTitlePass']}`",
                f"- Subtitle policy pass: `{row['subtitlePolicyPass']}`",
                f"- Forbidden text pass: `{row['forbiddenTextPass']}`",
                "- Decision fields to fill:",
            ]
        )
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
    parser = argparse.ArgumentParser(description="Prepare a title typography plan for a travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/title_typography_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "title_typography_plan"
    plan = build_plan(package_dir)
    write_json(output_dir / "title_typography_plan.json", plan)
    write_markdown(output_dir / "title_typography_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
