#!/usr/bin/env python3
"""Audit cover/hero title construction against the Parallel World reference formula."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts", ".m2ts"}
IMAGE_SLATE_SUFFIXES = {".png", ".jpg", ".jpeg"}
ROUTE_DATE_TOKENS = ("/", "->", "→", " - ", " TO ", "20")
INTERNAL_TOKENS = (
    "CODEX",
    "DAVINCI",
    "RESOLVE",
    "SKILL",
    "V14",
    "QA",
    "SRT",
    "TXT",
    "BGM",
    "交付",
    "时间线",
    "修复",
    "本次剪辑",
)
ESTABLISHING_HINTS = (
    "aerial",
    "drone",
    "skyline",
    "city",
    "coast",
    "bridge",
    "river",
    "water",
    "mountain",
    "tower",
    "temple",
    "castle",
    "station",
    "train",
    "street",
    "landmark",
    "航拍",
    "城市",
    "天际线",
    "海",
    "桥",
    "山",
    "塔",
    "寺",
    "车站",
    "街",
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


def find_manifest(package_dir: Path, explicit: str | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        [
            package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json",
            package_dir / "v12_visual_manifest.json",
            package_dir / "v8_visual_polish" / "v8_visual_polish_manifest.json",
            package_dir / "visual_polish_manifest.json",
        ]
    )
    return next((path.resolve() for path in candidates if path.exists()), None)


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def upper(value: Any) -> str:
    return clean_text(value).upper()


def words_or_cjk_count(value: str) -> int:
    text = clean_text(value)
    if not text:
        return 0
    words = [item for item in re.split(r"\s+", text) if item]
    if len(words) > 1:
        return len(words)
    cjk = re.findall(r"[\u3400-\u9fff]", text)
    if cjk:
        return len(cjk)
    return 1


def has_route_date_or_internal(value: str, forbidden: list[str]) -> list[str]:
    text = upper(value)
    hits = [token for token in ROUTE_DATE_TOKENS if token in text]
    hits.extend(token for token in INTERNAL_TOKENS if token in text)
    hits.extend(str(token) for token in forbidden if token and str(token).upper() in text)
    if re.search(r"\b20\d{2}\b", text):
        hits.append("year")
    return sorted(set(hits))


def is_video(path_raw: Any) -> bool:
    if not path_raw:
        return False
    path = Path(str(path_raw)).expanduser()
    if not path.exists():
        return False
    if path.suffix.lower() in IMAGE_SLATE_SUFFIXES:
        return False
    return path.suffix.lower() in VIDEO_SUFFIXES or path.suffix.lower() == ""


def opening_segment(manifest: dict[str, Any]) -> dict[str, Any] | None:
    rows = manifest.get("segments") if isinstance(manifest.get("segments"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("mode") or "").lower() == "opening":
            return row
    clips = manifest.get("clips") if isinstance(manifest.get("clips"), list) else []
    for row in clips:
        if isinstance(row, dict) and str(row.get("mode") or "").lower() == "opening":
            return row
    return None


def opening_clip_style(manifest: dict[str, Any], segment: dict[str, Any]) -> dict[str, Any]:
    clips = manifest.get("clips") if isinstance(manifest.get("clips"), list) else []
    seg_id = segment.get("id")
    for row in clips:
        if not isinstance(row, dict):
            continue
        if row.get("id") == seg_id and isinstance(row.get("coverHeroTitleStyle"), dict):
            return row["coverHeroTitleStyle"]
    style = segment.get("coverHeroTitleStyle")
    return style if isinstance(style, dict) else {}


def title_values(manifest: dict[str, Any], segment: dict[str, Any]) -> tuple[str, str]:
    title = clean_text(segment.get("title") or manifest.get("cityTitle") or manifest.get("expectedOpeningTitle"))
    subtitle = clean_text(segment.get("subtitle") or manifest.get("coverSubtitle") or manifest.get("englishSubtitle"))
    return title, subtitle


def background_text(segment: dict[str, Any]) -> str:
    values = [segment.get("source"), segment.get("segment"), segment.get("background"), segment.get("title"), segment.get("subtitle")]
    return " ".join(clean_text(value) for value in values)


def background_has_hint(segment: dict[str, Any], style: dict[str, Any]) -> bool:
    explicit = clean_text(style.get("backgroundRecognition")).lower()
    if any(token in explicit for token in ("high", "establish", "landmark", "route")):
        return True
    text = background_text(segment).lower()
    return any(hint.lower() in text for hint in ESTABLISHING_HINTS)


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    manifest_path = find_manifest(package_dir, args.visual_manifest)
    manifest = load_json(manifest_path)
    title_plan = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    title_audit = load_json(package_dir / "title_bridge_contract_audit.json") or {}
    if not isinstance(manifest, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {"visualManifest": str(manifest_path) if manifest_path else None, "visualManifestExists": False},
            "summary": {},
            "checks": [],
            "blockers": ["cover/title visual manifest missing"],
            "warnings": [],
            "safety": safety(),
        }
    segment = opening_segment(manifest) or {}
    style = opening_clip_style(manifest, segment)
    forbidden = [str(item) for item in manifest.get("forbiddenOpeningText") or manifest.get("forbiddenVisibleText") or []]
    title, subtitle = title_values(manifest, segment)
    title_hits = has_route_date_or_internal(title, forbidden)
    subtitle_hits = has_route_date_or_internal(subtitle, forbidden)
    source_path = segment.get("source")
    segment_path = segment.get("segment")
    title_words = words_or_cjk_count(title)
    subtitle_ok = bool(subtitle) and len(subtitle) <= 34 and not subtitle_hits
    checks = [
        {
            "name": "Opening cover/hero title segment exists",
            "status": "passed" if segment else "blocked",
            "evidence": {"manifest": str(manifest_path), "segmentId": segment.get("id")},
        },
        {
            "name": "Main title is oversized destination text only",
            "status": "passed" if title and 1 <= title_words <= 8 and not title_hits else "blocked",
            "evidence": {"title": title, "titleUnitCount": title_words, "forbiddenHits": title_hits},
        },
        {
            "name": "Secondary title is a short designed English/place line",
            "status": "passed" if subtitle_ok else "blocked",
            "evidence": {"subtitle": subtitle, "length": len(subtitle), "forbiddenHits": subtitle_hits},
        },
        {
            "name": "Background is high-recognition scenic video, not screenshot or slate",
            "status": "passed" if is_video(source_path) and is_video(segment_path) and background_has_hint(segment, style) else "blocked",
            "evidence": {
                "source": source_path,
                "segment": segment_path,
                "sourceIsVideo": is_video(source_path),
                "segmentIsVideo": is_video(segment_path),
                "backgroundHint": background_has_hint(segment, style),
                "style": style,
            },
        },
        {
            "name": "Cover frame uses clean 16:9 deliverable style without screenshot chrome",
            "status": "passed" if style.get("clean16x9Deliverable") is True or "clean 16:9" in clean_text(manifest.get("coverHeroTitlePolicy")).lower() else "blocked",
            "evidence": {"style": style, "coverHeroTitlePolicy": manifest.get("coverHeroTitlePolicy")},
        },
        {
            "name": "Title plan and title bridge contract support the hero title",
            "status": "passed" if title_plan.get("status") == "ready_with_clean_title_typography_plan" and title_audit.get("status") in {"passed", "passed_with_warnings"} else "blocked",
            "evidence": {"titlePlanStatus": title_plan.get("status"), "titleBridgeStatus": title_audit.get("status")},
        },
    ]
    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings: list[str] = []
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "visualManifest": str(manifest_path) if manifest_path else None,
            "visualManifestExists": bool(manifest_path and manifest_path.exists()),
            "titleTypographyPlan": str(package_dir / "title_typography_plan" / "title_typography_plan.json"),
            "titleBridgeContractAudit": str(package_dir / "title_bridge_contract_audit.json"),
        },
        "summary": {
            "openingSegmentExists": bool(segment),
            "mainTitle": title,
            "mainTitleUnitCount": title_words,
            "secondaryTitle": subtitle,
            "secondaryTitlePresent": bool(subtitle),
            "backgroundVideoReady": is_video(source_path) and is_video(segment_path),
            "backgroundRecognitionHint": background_has_hint(segment, style),
            "clean16x9Deliverable": style.get("clean16x9Deliverable") is True or "clean 16:9" in clean_text(manifest.get("coverHeroTitlePolicy")).lower(),
            "forbiddenHitCount": len(title_hits) + len(subtitle_hits),
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Cover Title Contract Audit",
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
    for row in report.get("checks") or []:
        lines.extend(
            [
                "",
                f"### {row.get('name')}",
                f"- Status: `{row.get('status')}`",
                f"- Evidence: `{json.dumps(row.get('evidence'), ensure_ascii=False)[:1600]}`",
            ]
        )
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the cover/hero title contract for a travel video package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--visual-manifest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "cover_title_contract_audit.json", report)
    write_markdown(package_dir / "cover_title_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
