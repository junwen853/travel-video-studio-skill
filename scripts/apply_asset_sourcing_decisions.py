#!/usr/bin/env python3
"""Validate and optionally reconcile filled asset sourcing decisions into the asset ledger."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


FINAL_ASSET_TYPES = {"bgm", "aerial_or_stock"}
VERIFIED_STATUSES = {"verified", "licensed", "approved", "system-font-render-only"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def has_decision(decision: dict[str, Any]) -> bool:
    keys = ("selectedAssetTitle", "selectedAssetUrl", "localPath", "provider", "licenseUrl", "approvedBy", "approvedAt")
    return any(clean(decision.get(key)) for key in keys)


def validate_decision(row: dict[str, Any], decision: dict[str, Any]) -> tuple[list[str], list[str], str]:
    blockers: list[str] = []
    warnings: list[str] = []
    asset_type = row.get("type")
    if not has_decision(decision):
        if asset_type in FINAL_ASSET_TYPES:
            blockers.append("No filled decision fields.")
        return blockers, warnings, "unchanged"
    if asset_type in FINAL_ASSET_TYPES:
        required = ["provider", "licenseUrl", "approvedBy", "approvedAt"]
        for key in required:
            if not clean(decision.get(key)):
                blockers.append(f"Missing required decision field: {key}")
        if not clean(decision.get("selectedAssetUrl")) and not clean(decision.get("localPath")):
            blockers.append("Missing selectedAssetUrl or localPath.")
        local_path = clean(decision.get("localPath"))
        if local_path and not Path(local_path).expanduser().exists():
            warnings.append(f"Local asset path does not exist yet: {local_path}")
        if blockers:
            return blockers, warnings, "incomplete"
        return blockers, warnings, "verified"
    if asset_type == "font":
        if not clean(decision.get("localPath")) and not clean(decision.get("selectedAssetUrl")):
            warnings.append("Font decision has no localPath or selectedAssetUrl; keeping as unverified.")
            return blockers, warnings, "incomplete"
        if not clean(decision.get("licenseUrl")) and clean(decision.get("provider")) != "local system font":
            warnings.append("Font decision has no licenseUrl; keeping as unverified.")
            return blockers, warnings, "incomplete"
        return blockers, warnings, "system-font-render-only" if clean(decision.get("provider")) == "local system font" else "verified"
    warnings.append(f"Unknown asset type: {asset_type}")
    return blockers, warnings, "unchanged"


def update_item(item: dict[str, Any], row: dict[str, Any], decision: dict[str, Any], status: str, now: str) -> dict[str, Any]:
    updated = dict(item)
    for src, dst in [
        ("selectedAssetTitle", "selectedAssetTitle"),
        ("selectedAssetUrl", "selectedAssetUrl"),
        ("localPath", "localPath"),
        ("provider", "provider"),
        ("licenseUrl", "licenseUrl"),
        ("priceOrPlan", "priceOrPlan"),
        ("invoiceOrSubscriptionEvidence", "invoiceOrSubscriptionEvidence"),
        ("attributionRequired", "attributionRequired"),
        ("attributionText", "attributionText"),
        ("usageRestrictions", "usageRestrictions"),
        ("approvedBy", "approvedBy"),
        ("approvedAt", "approvedAt"),
        ("editorNotes", "editorNotes"),
    ]:
        value = decision.get(src)
        if value not in ("", None):
            updated[dst] = value
    if status in VERIFIED_STATUSES:
        updated["licenseStatus"] = status
        updated["approvalRequired"] = False
    updated["lastReconciledAt"] = now
    updated["sourceSourcingRow"] = row.get("assetRowIndex")
    return updated


def summarize_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    unverified_final = 0
    verified_final = 0
    for item in items:
        if item.get("type") not in FINAL_ASSET_TYPES:
            continue
        status = item.get("licenseStatus")
        has_asset = bool(item.get("localPath") or item.get("selectedAssetUrl"))
        if status in VERIFIED_STATUSES and has_asset:
            verified_final += 1
        else:
            unverified_final += 1
    return {"verifiedBgmOrStock": verified_final, "unverifiedBgmOrStock": unverified_final}


def reconcile(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    ledger_path = Path(args.ledger).expanduser().resolve() if args.ledger else package_dir / "asset_ledger" / "asset_license_ledger.json"
    packet_path = Path(args.packet).expanduser().resolve() if args.packet else package_dir / "asset_sourcing" / "asset_sourcing_packet.json"
    ledger = load_json(ledger_path)
    packet = load_json(packet_path)
    items = list(ledger.get("items") or [])
    rows = packet.get("sourcingRows") or []
    now = datetime.now().isoformat(timespec="seconds")
    blockers: list[str] = []
    warnings: list[str] = []
    row_reports: list[dict[str, Any]] = []
    updated_items = list(items)

    for row in rows:
        row_index = row.get("assetRowIndex")
        if not isinstance(row_index, int) or row_index < 0 or row_index >= len(items):
            warnings.append(f"Skipping sourcing row with invalid assetRowIndex: {row_index}")
            continue
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        row_blockers, row_warnings, status = validate_decision(row, decision)
        if row_blockers:
            blockers.extend(f"Row {row_index} ({row.get('type')} {row.get('place') or row.get('font')}): {item}" for item in row_blockers)
        if row_warnings:
            warnings.extend(f"Row {row_index} ({row.get('type')} {row.get('place') or row.get('font')}): {item}" for item in row_warnings)
        changed = has_decision(decision) and status not in {"unchanged", "incomplete"} and not row_blockers
        if changed:
            updated_items[row_index] = update_item(items[row_index], row, decision, status, now)
        row_reports.append(
            {
                "assetRowIndex": row_index,
                "type": row.get("type"),
                "place": row.get("place"),
                "font": row.get("font"),
                "decisionFilled": has_decision(decision),
                "status": status,
                "willUpdateLedger": bool(changed and args.apply),
                "blockers": row_blockers,
                "warnings": row_warnings,
            }
        )

    if args.apply and blockers:
        warnings.append("Ledger was not updated because reconciliation blockers remain.")
    elif args.apply:
        ledger["items"] = updated_items
        summary = summarize_items(updated_items)
        ledger["status"] = "ready" if summary["unverifiedBgmOrStock"] == 0 else "draft"
        ledger["finalReady"] = summary["unverifiedBgmOrStock"] == 0
        ledger["lastReconciledAt"] = now
        write_json(ledger_path, ledger)

    resulting_items = updated_items if args.apply and not blockers else items
    summary = summarize_items(resulting_items)
    report = {
        "createdAt": now,
        "status": "blocked" if blockers or summary["unverifiedBgmOrStock"] else "ready",
        "packageDir": str(package_dir),
        "sourceAssetLedger": str(ledger_path),
        "sourceSourcingPacket": str(packet_path),
        "applied": bool(args.apply and not blockers),
        "summary": {
            "sourcingRows": len(rows),
            "decisionRowsFilled": sum(1 for report_row in row_reports if report_row["decisionFilled"]),
            **summary,
        },
        "rowReports": row_reports,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "nextActions": [
            "Fill exact selectedAssetUrl/localPath, provider, licenseUrl, approvedBy, and approvedAt for every BGM/stock/aerial row.",
            "Run this script again with --apply only after all final asset rows are approved.",
            "Refresh prepare_asset_sourcing_packet.py and audit_delivery_package.py after ledger reconciliation.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesLedgerOnlyWithApply": True,
            "writesResolve": False,
        },
    }
    report_dir = package_dir / "asset_sourcing"
    write_json(report_dir / "asset_decision_reconciliation.json", report)
    write_markdown(report_dir / "asset_decision_reconciliation.md", report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Asset Decision Reconciliation",
        "",
        f"Status: `{report['status']}`",
        f"Applied: `{report['applied']}`",
        f"Ledger: `{report['sourceAssetLedger']}`",
        f"Sourcing packet: `{report['sourceSourcingPacket']}`",
        "",
        "## Summary",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Blockers"])
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in report.get("warnings") or ["None"])
    lines.extend(["", "## Filled Rows"])
    for row in report.get("rowReports") or []:
        if row.get("decisionFilled"):
            lines.append(
                f"- Row {row.get('assetRowIndex')}: `{row.get('type')}` {row.get('place') or row.get('font')} -> `{row.get('status')}`"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and optionally apply asset sourcing decisions.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--packet", help="Path to asset_sourcing_packet.json. Defaults to package asset_sourcing directory.")
    parser.add_argument("--ledger", help="Path to asset_license_ledger.json. Defaults to package asset_ledger directory.")
    parser.add_argument("--apply", action="store_true", help="Update asset_license_ledger.json when all filled final decisions are valid.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = reconcile(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Asset decision reconciliation status: {report['status']}")
        print(f"Applied: {report['applied']}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
