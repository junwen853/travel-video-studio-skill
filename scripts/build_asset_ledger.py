#!/usr/bin/env python3
"""Create an auditable BGM/aerial/font asset license ledger from a delivery package."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from typing import Any


FONT_ALIASES = {
    "Hiragino Mincho ProN": ["hiragino mincho", "hiragino mincho pron", "ヒラギノ明朝"],
    "Yu Mincho": ["yu mincho", "yumincho", "游明朝"],
    "Noto Serif CJK JP": ["noto serif cjk", "noto serif cjk jp"],
    "Shippori Mincho": ["shippori mincho"],
    "Hiragino Sans": ["hiragino sans", "ヒラギノ角ゴシック"],
    "Noto Sans CJK": ["noto sans cjk"],
    "Source Han Sans": ["source han sans"],
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def search_url(provider: str, query: str) -> str:
    q = quote_plus(query)
    urls = {
        "Pixabay Music": f"https://pixabay.com/music/search/{q}/",
        "Pixabay Video": f"https://pixabay.com/videos/search/{q}/",
        "Pexels Video": f"https://www.pexels.com/search/videos/{q}/",
        "Pond5": f"https://www.pond5.com/stock-video-footage/tag/{q}/",
        "Shutterstock Video": f"https://www.shutterstock.com/video/search/{q}",
        "Artlist": f"https://artlist.io/search?search={q}",
        "Epidemic Sound": f"https://www.epidemicsound.com/search/?term={q}",
    }
    return urls[provider]


def fc_match(font_name: str) -> dict[str, str | None]:
    tool = shutil.which("fc-match")
    if not tool:
        return {"font": font_name, "path": None, "family": None}
    result = subprocess.run([tool, "-f", "%{family}\n%{file}\n", font_name], check=False, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    return {
        "font": font_name,
        "family": lines[0] if lines else None,
        "path": lines[1] if len(lines) > 1 else None,
    }


def normalize_font_text(value: str | None) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def font_match_status(font_name: str, family: str | None, path: str | None) -> str:
    combined = f"{family or ''} {path or ''}"
    combined_norm = normalize_font_text(combined)
    aliases = FONT_ALIASES.get(font_name, [font_name])
    for alias in aliases:
        if normalize_font_text(alias) and normalize_font_text(alias) in combined_norm:
            return "matched"
    if path:
        return "fallback"
    return "missing"


def bgm_items(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for cue in delivery.get("bgmCues", []):
        for query in cue.get("queries", []):
            items.append(
                {
                    "type": "bgm",
                    "chapterIndex": cue.get("chapterIndex"),
                    "place": cue.get("place"),
                    "query": query,
                    "suggestedSearches": [
                        {"provider": "Pixabay Music", "url": search_url("Pixabay Music", query)},
                        {"provider": "Artlist", "url": search_url("Artlist", query)},
                        {"provider": "Epidemic Sound", "url": search_url("Epidemic Sound", query)},
                    ],
                    "selectedAssetUrl": "",
                    "localPath": "",
                    "licenseStatus": "unverified",
                    "approvalRequired": True,
                    "notes": "Select, verify license, download/import, then update this row.",
                }
            )
    return items


def aerial_items(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for block in delivery.get("assetSearch", []):
        for query in block.get("queries", []):
            items.append(
                {
                    "type": "aerial_or_stock",
                    "chapterIndex": block.get("chapterIndex"),
                    "place": block.get("place"),
                    "query": query,
                    "suggestedSearches": [
                        {"provider": "Pexels Video", "url": search_url("Pexels Video", query)},
                        {"provider": "Pixabay Video", "url": search_url("Pixabay Video", query)},
                        {"provider": "Pond5", "url": search_url("Pond5", query)},
                        {"provider": "Shutterstock Video", "url": search_url("Shutterstock Video", query)},
                    ],
                    "selectedAssetUrl": "",
                    "localPath": "",
                    "licenseStatus": "unverified",
                    "approvalRequired": True,
                    "notes": "Prefer user-owned footage first; use stock only after license approval.",
                }
            )
    return items


def font_items(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    typography = delivery.get("typography", {})
    items = []
    for role, fonts in typography.items():
        if not isinstance(fonts, list):
            continue
        for font_name in fonts:
            match = fc_match(font_name)
            match_status = font_match_status(font_name, match.get("family"), match.get("path"))
            is_usable_system_font = match_status == "matched" and bool(match.get("path"))
            items.append(
                {
                    "type": "font",
                    "role": role,
                    "font": font_name,
                    "matchedFamily": match.get("family"),
                    "localPath": match.get("path"),
                    "matchStatus": match_status,
                    "licenseStatus": "system-font-render-only" if is_usable_system_font else "unverified",
                    "approvalRequired": not is_usable_system_font,
                    "notes": (
                        "Do not redistribute font files; rendered video output can use installed local system fonts."
                        if is_usable_system_font
                        else "Requested font did not match an installed family; choose a verified system fallback or licensed font source."
                    ),
                }
            )
    return items


def write_markdown(path: Path, ledger: dict[str, Any]) -> None:
    lines = ["# Asset License Ledger", ""]
    lines.append("Every final BGM, stock/aerial, and font decision must be auditable. Unverified rows are not final-delivery ready.")
    for item in ledger["items"]:
        title = item.get("query") or item.get("font") or item.get("type")
        lines.extend(["", f"## {item['type']}: {title}", f"- License status: {item.get('licenseStatus')}", f"- Approval required: {item.get('approvalRequired')}"])
        if item.get("place"):
            lines.append(f"- Place: {item['place']}")
        if item.get("localPath"):
            lines.append(f"- Local path: `{item['localPath']}`")
        searches = item.get("suggestedSearches") or []
        if searches:
            lines.append("- Suggested searches:")
            for search in searches:
                lines.append(f"  - {search['provider']}: {search['url']}")
        if item.get("notes"):
            lines.append(f"- Notes: {item['notes']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a BGM/aerial/font license ledger.")
    parser.add_argument("--delivery-plan", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    delivery = load_json(Path(args.delivery_plan).expanduser().resolve())
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    ledger = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "sourceDeliveryPlan": str(Path(args.delivery_plan).expanduser().resolve()),
        "status": "draft",
        "items": bgm_items(delivery) + aerial_items(delivery) + font_items(delivery),
        "finalReady": False,
        "readyRule": "All BGM and aerial/stock rows must have selectedAssetUrl/localPath plus verified licenseStatus before final render.",
    }
    (output / "asset_license_ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(output / "asset_license_ledger.md", ledger)
    if args.json:
        print(json.dumps(ledger, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote asset ledger with {len(ledger['items'])} items to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
