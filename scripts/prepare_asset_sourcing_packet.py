#!/usr/bin/env python3
"""Create an approval-ready sourcing packet for BGM, stock/aerial, and fonts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROVIDERS: dict[str, dict[str, Any]] = {
    "Pixabay Music": {
        "assetTypes": ["bgm"],
        "licenseUrl": "https://pixabay.com/service/license-summary/",
        "costModel": "free library, per-asset license review still required",
        "bestFor": "backup music cues, temp tracks, simple documentary beds",
    },
    "Pixabay Video": {
        "assetTypes": ["aerial_or_stock"],
        "licenseUrl": "https://pixabay.com/service/license-summary/",
        "costModel": "free library, per-asset license review still required",
        "bestFor": "free establishing shots when quality and license fit the edit",
    },
    "Pexels Video": {
        "assetTypes": ["aerial_or_stock"],
        "licenseUrl": "https://www.pexels.com/license/",
        "costModel": "free library, per-asset license review still required",
        "bestFor": "free city inserts, street ambience, skyline cutaways",
    },
    "Artlist": {
        "assetTypes": ["bgm"],
        "licenseUrl": "https://artlist.io/license",
        "costModel": "subscription or plan-based licensing",
        "bestFor": "polished long-form travel documentary BGM",
    },
    "Epidemic Sound": {
        "assetTypes": ["bgm"],
        "licenseUrl": "https://www.epidemicsound.com/licensing/",
        "costModel": "subscription or plan-based licensing",
        "bestFor": "polished long-form BGM, stems, and alternates",
    },
    "Pond5": {
        "assetTypes": ["aerial_or_stock"],
        "licenseUrl": "https://www.pond5.com/legal/license",
        "costModel": "marketplace purchase/license per asset or plan",
        "bestFor": "specific paid Tokyo/Osaka aerials and premium establishing shots",
    },
    "Shutterstock Video": {
        "assetTypes": ["aerial_or_stock"],
        "licenseUrl": "https://www.shutterstock.com/license",
        "costModel": "subscription, pack, or enhanced license depending on use",
        "bestFor": "specific paid landmarks, skyline, and crowd/timelapse inserts",
    },
    "Motion Array": {
        "assetTypes": ["bgm", "aerial_or_stock"],
        "licenseUrl": "https://motionarray.com/license/",
        "costModel": "subscription license; verify active plan and project coverage",
        "bestFor": "music, motion graphics, and occasional stock inserts",
    },
    "Google Fonts": {
        "assetTypes": ["font"],
        "licenseUrl": "https://developers.google.com/fonts/faq",
        "costModel": "open-source fonts, verify the specific family license",
        "bestFor": "downloadable Noto/Source Han style fallback fonts",
    },
}


DECISION_TEMPLATE = {
    "selectedAssetTitle": "",
    "selectedAssetUrl": "",
    "localPath": "",
    "provider": "",
    "licenseUrl": "",
    "priceOrPlan": "",
    "invoiceOrSubscriptionEvidence": "",
    "attributionRequired": None,
    "attributionText": "",
    "usageRestrictions": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_type(asset_type: Any) -> str:
    value = str(asset_type or "").strip()
    if value in {"bgm", "aerial_or_stock", "font"}:
        return value
    return "unknown"


def provider_options(item: dict[str, Any]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    asset_type = normalize_type(item.get("type"))
    for search in item.get("suggestedSearches") or []:
        provider = search.get("provider")
        if not provider:
            continue
        meta = PROVIDERS.get(provider, {})
        options.append(
            {
                "provider": provider,
                "searchUrl": search.get("url", ""),
                "licenseUrl": meta.get("licenseUrl", ""),
                "costModel": meta.get("costModel", ""),
                "bestFor": meta.get("bestFor", ""),
                "verificationSteps": verification_steps(asset_type, provider),
            }
        )
    if asset_type == "aerial_or_stock" and not any(option["provider"] == "Motion Array" for option in options):
        meta = PROVIDERS["Motion Array"]
        options.append(
            {
                "provider": "Motion Array",
                "searchUrl": "https://motionarray.com/browse/stock-video/?q=" + str(item.get("query", "")).replace(" ", "%20"),
                "licenseUrl": meta["licenseUrl"],
                "costModel": meta["costModel"],
                "bestFor": meta["bestFor"],
                "verificationSteps": verification_steps(asset_type, "Motion Array"),
            }
        )
    if asset_type == "bgm" and not any(option["provider"] == "Motion Array" for option in options):
        meta = PROVIDERS["Motion Array"]
        options.append(
            {
                "provider": "Motion Array",
                "searchUrl": "https://motionarray.com/browse/royalty-free-music/?q=" + str(item.get("query", "")).replace(" ", "%20"),
                "licenseUrl": meta["licenseUrl"],
                "costModel": meta["costModel"],
                "bestFor": meta["bestFor"],
                "verificationSteps": verification_steps(asset_type, "Motion Array"),
            }
        )
    return options


def verification_steps(asset_type: str, provider: str) -> list[str]:
    common = [
        "Open the provider search result and pick one exact asset, not only a search page.",
        "Open the provider license page on the same day you approve the asset.",
        "Record selectedAssetUrl, licenseUrl, priceOrPlan, and invoice/subscription evidence.",
        "Download/import only after approval, then record the localPath.",
    ]
    if asset_type == "bgm":
        return [
            *common,
            "Confirm the license covers online video and a 20+ minute travel film.",
            "Check attribution, content ID, monetization, and perpetual-use rules.",
        ]
    if asset_type == "aerial_or_stock":
        return [
            *common,
            "Confirm the license covers edited video, online publishing, and the intended resolution.",
            "Prefer professional stock/high-rise establishing shots where drone use is restricted.",
        ]
    if asset_type == "font":
        return [
            "Use installed system fonts for rendering only, or pick an open/commercial font source.",
            "Do not redistribute font files unless the license explicitly allows it.",
            "Record family name, license URL, local font path, and whether the font is bundled.",
        ]
    return common


def source_need(item: dict[str, Any], index: int) -> dict[str, Any]:
    asset_type = normalize_type(item.get("type"))
    row = {
        "assetRowIndex": index,
        "type": asset_type,
        "chapterIndex": item.get("chapterIndex"),
        "place": item.get("place"),
        "query": item.get("query"),
        "font": item.get("font"),
        "role": item.get("role"),
        "currentLicenseStatus": item.get("licenseStatus"),
        "approvalRequired": bool(item.get("approvalRequired")),
        "currentSelectedAssetUrl": item.get("selectedAssetUrl", ""),
        "currentLocalPath": item.get("localPath", ""),
        "providerOptions": provider_options(item),
        "decision": dict(DECISION_TEMPLATE),
        "notes": item.get("notes", ""),
    }
    if asset_type == "font":
        row["providerOptions"] = font_provider_options(item)
        if item.get("licenseStatus") == "system-font-render-only" and item.get("matchStatus", "matched") == "matched":
            row["decision"]["provider"] = "local system font"
            row["decision"]["localPath"] = item.get("localPath", "")
        row["decision"]["licenseUrl"] = item.get("licenseUrl", "")
    return row


def font_provider_options(item: dict[str, Any]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if item.get("localPath") and item.get("licenseStatus") == "system-font-render-only" and item.get("matchStatus", "matched") == "matched":
        options.append(
            {
                "provider": "local system font",
                "searchUrl": "",
                "licenseUrl": "",
                "costModel": "already installed; render-only use, do not redistribute font files",
                "bestFor": "local title/subtitle rendering inside the final exported video",
                "verificationSteps": verification_steps("font", "local system font"),
            }
        )
    elif item.get("localPath"):
        options.append(
            {
                "provider": "local fallback candidate",
                "searchUrl": "",
                "licenseUrl": "",
                "costModel": "not approved by default; requested family did not match",
                "bestFor": "diagnostic only until the user approves this fallback style",
                "verificationSteps": verification_steps("font", "local fallback candidate"),
            }
        )
    meta = PROVIDERS["Google Fonts"]
    font_name = str(item.get("font") or "").replace(" ", "%20")
    options.append(
        {
            "provider": "Google Fonts",
            "searchUrl": f"https://fonts.google.com/?query={font_name}",
            "licenseUrl": meta["licenseUrl"],
            "costModel": meta["costModel"],
            "bestFor": meta["bestFor"],
            "verificationSteps": verification_steps("font", "Google Fonts"),
        }
    )
    return options


def chapter_needs(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    chapters_by_index = {chapter.get("index"): chapter for chapter in delivery.get("chapters") or []}
    needs: list[dict[str, Any]] = []
    for cue in delivery.get("bgmCues") or []:
        chapter = chapters_by_index.get(cue.get("chapterIndex"), {})
        needs.append(
            {
                "type": "bgm",
                "chapterIndex": cue.get("chapterIndex"),
                "place": cue.get("place") or chapter.get("place"),
                "mood": cue.get("mood"),
                "queries": cue.get("queries") or [],
                "durationUse": "long-form music bed or chapter cue; avoid short-video energy unless approved",
            }
        )
    for block in delivery.get("assetSearch") or []:
        chapter = chapters_by_index.get(block.get("chapterIndex"), {})
        needs.append(
            {
                "type": "aerial_or_stock",
                "chapterIndex": block.get("chapterIndex"),
                "place": block.get("place") or chapter.get("place"),
                "aerialTargets": block.get("aerialTargets") or [],
                "queries": block.get("queries") or [],
                "durationUse": "establishing shot, route bridge, day transition, or missing local cutaway",
            }
        )
    return needs


def provider_directory() -> list[dict[str, Any]]:
    return [
        {
            "provider": name,
            "assetTypes": meta["assetTypes"],
            "licenseUrl": meta["licenseUrl"],
            "costModel": meta["costModel"],
            "bestFor": meta["bestFor"],
        }
        for name, meta in PROVIDERS.items()
    ]


def build_packet(package_dir: Path, delivery: dict[str, Any], ledger: dict[str, Any], ledger_path: Path) -> dict[str, Any]:
    items = ledger.get("items") or []
    sourcing_rows = [source_need(item, index) for index, item in enumerate(items)]
    unverified = [
        row
        for row in sourcing_rows
        if row["type"] in {"bgm", "aerial_or_stock"}
        and (row.get("currentLicenseStatus") in {"", None, "unverified"} or not (row.get("currentSelectedAssetUrl") or row.get("currentLocalPath")))
    ]
    blockers = []
    if unverified:
        blockers.append(f"{len(unverified)} BGM/stock/aerial rows still need exact asset selection and license verification.")
    packet = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked" if blockers else "ready_for_asset_import",
        "packageDir": str(package_dir),
        "sourceDeliveryPlan": str(package_dir / "delivery_plan.json"),
        "sourceAssetLedger": str(ledger_path),
        "sourceAssetLedgerMtime": datetime.fromtimestamp(ledger_path.stat().st_mtime).isoformat(timespec="seconds")
        if ledger_path.exists()
        else None,
        "providerDirectory": provider_directory(),
        "chapterNeeds": chapter_needs(delivery),
        "sourcingRows": sourcing_rows,
        "summary": {
            "rowCount": len(sourcing_rows),
            "bgmRows": sum(1 for row in sourcing_rows if row["type"] == "bgm"),
            "aerialOrStockRows": sum(1 for row in sourcing_rows if row["type"] == "aerial_or_stock"),
            "fontRows": sum(1 for row in sourcing_rows if row["type"] == "font"),
            "unverifiedBgmOrStock": len(unverified),
        },
        "blockers": blockers,
        "nextActions": next_actions(package_dir, len(unverified)),
        "approvalRule": "Do not download/import BGM or stock/aerial into final Resolve timelines until the corresponding ledger row is selected, licensed, and approved.",
    }
    return packet


def next_actions(package_dir: Path, unverified_count: int) -> list[dict[str, str]]:
    if not unverified_count:
        return [
            {
                "priority": "P1",
                "action": "Import approved assets",
                "command": f"Use selected local paths from {package_dir / 'asset_ledger' / 'asset_license_ledger.json'} in the Resolve blueprint/audio tracks.",
            }
        ]
    return [
        {
            "priority": "P0",
            "action": "Select exact BGM and stock/aerial assets",
            "command": f"Open {package_dir / 'asset_sourcing' / 'asset_sourcing_packet.md'} and choose exact provider assets.",
        },
        {
            "priority": "P0",
            "action": "Verify license and approval evidence",
            "command": f"Update {package_dir / 'asset_ledger' / 'asset_license_ledger.json'} with selectedAssetUrl/localPath/licenseStatus after approval.",
        },
        {
            "priority": "P0",
            "action": "Rebuild packet and audit",
            "command": f"python3 <skill-dir>/scripts/prepare_asset_sourcing_packet.py --package-dir {package_dir} && python3 <skill-dir>/scripts/audit_delivery_package.py --package-dir {package_dir}",
        },
    ]


def write_packet_markdown(path: Path, packet: dict[str, Any]) -> None:
    lines = [
        "# Asset Sourcing Packet",
        "",
        f"Status: `{packet['status']}`",
        f"Package: `{packet['packageDir']}`",
        f"Source ledger: `{packet['sourceAssetLedger']}`",
        "",
        "> Final render is blocked until every BGM and stock/aerial row has an exact asset, license URL, approval evidence, and local path or selected asset URL.",
        "",
        "## Provider License Directory",
    ]
    for provider in packet["providerDirectory"]:
        types = ", ".join(provider["assetTypes"])
        lines.append(f"- {provider['provider']} ({types}): {provider['licenseUrl']} - {provider['costModel']}")

    lines.extend(["", "## Chapter Needs"])
    for need in packet["chapterNeeds"] or [{"type": "none", "place": "No external assets requested"}]:
        lines.append(f"- {need['type']} | Chapter {need.get('chapterIndex')} | {need.get('place')}: {need.get('durationUse', '')}")
        if need.get("mood"):
            lines.append(f"  - Mood: {need['mood']}")
        if need.get("aerialTargets"):
            lines.append(f"  - Targets: {', '.join(need['aerialTargets'])}")
        if need.get("queries"):
            lines.append(f"  - Queries: {'; '.join(need['queries'])}")

    for asset_type, heading in (("bgm", "BGM Rows"), ("aerial_or_stock", "Aerial/Stock Rows"), ("font", "Font Rows")):
        rows = [row for row in packet["sourcingRows"] if row["type"] == asset_type]
        lines.extend(["", f"## {heading}"])
        if not rows:
            lines.append("- None")
            continue
        for row in rows:
            title = row.get("query") or row.get("font") or row.get("type")
            lines.append("")
            lines.append(f"### Row {row['assetRowIndex']}: {title}")
            lines.append(f"- Place: {row.get('place') or ''}")
            lines.append(f"- Current status: `{row.get('currentLicenseStatus')}`")
            lines.append(f"- Approval required: `{row.get('approvalRequired')}`")
            if row.get("currentLocalPath"):
                lines.append(f"- Current local path: `{row['currentLocalPath']}`")
            lines.append("- Provider options:")
            for option in row.get("providerOptions") or []:
                search = option.get("searchUrl") or "local/system"
                lines.append(f"  - {option['provider']}: {search}")
                if option.get("licenseUrl"):
                    lines.append(f"    - License: {option['licenseUrl']}")
            lines.append("- Decision fields to fill:")
            for key in DECISION_TEMPLATE:
                lines.append(f"  - {key}: ")

    lines.extend(["", "## Blockers"])
    lines.extend(f"- {item}" for item in packet["blockers"] or ["None"])
    lines.extend(["", "## Next Actions"])
    for action in packet["nextActions"]:
        lines.append(f"- [{action['priority']}] {action['action']}: `{action['command']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_packet_outputs(output_dir: Path, packet: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "asset_sourcing_packet.json", packet)
    write_packet_markdown(output_dir / "asset_sourcing_packet.md", packet)


def build_from_package(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery_path = package_dir / "delivery_plan.json"
    ledger_path = package_dir / "asset_ledger" / "asset_license_ledger.json"
    if not delivery_path.exists():
        raise SystemExit(f"Missing delivery plan: {delivery_path}")
    if not ledger_path.exists():
        raise SystemExit(f"Missing asset ledger: {ledger_path}")
    delivery = load_json(delivery_path)
    ledger = load_json(ledger_path)
    return build_packet(package_dir, delivery, ledger, ledger_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an asset sourcing packet from a delivery package.")
    parser.add_argument("--package-dir", required=True, help="Delivery package directory containing delivery_plan.json.")
    parser.add_argument("--output-dir", help="Override output directory; defaults to <package>/asset_sourcing.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    packet = build_from_package(package_dir)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "asset_sourcing"
    write_packet_outputs(output_dir, packet)
    if args.json:
        print(json.dumps(packet, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote asset sourcing packet to {output_dir}")
        for blocker in packet["blockers"]:
            print(f"BLOCKER: {blocker}")
    return 2 if packet["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
