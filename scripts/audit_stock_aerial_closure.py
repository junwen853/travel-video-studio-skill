#!/usr/bin/env python3
"""Audit whether stock/aerial search placeholders are materialized or explicitly closed."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PLACEHOLDER_STATUSES = {"license_unverified_placeholder", "placeholder", "needs_search", "needs web search and approval"}
BAD_SOURCE_TOKENS = ("stock need", "license_unverified_placeholder", "placeholder", "title_cards")


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


def resolve_path(value: Any) -> Path | None:
    if not value:
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except Exception:
        return None


def norm_path(value: Any) -> str:
    path = resolve_path(value)
    return str(path) if path else str(value or "")


def path_exists(value: Any) -> bool:
    path = resolve_path(value)
    return bool(path and path.exists())


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else ("warning" if warning else "blocked"),
            "evidence": evidence,
        }
    )


def asset_items(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "rows", "assets"):
        value = ledger.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def verified_aerial_items(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in asset_items(ledger):
        if str(item.get("type") or "").lower() != "aerial_or_stock":
            continue
        if str(item.get("licenseStatus") or "").lower() != "verified":
            continue
        if path_exists(item.get("localPath")):
            out.append(item)
    return out


def title_segments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in manifest.get("segments") or [] if isinstance(row, dict)]


def infer_title_manifest(package_dir: Path, blueprint: dict[str, Any]) -> Path:
    policy = blueprint.get("scenicTitleBridgePolicy") if isinstance(blueprint.get("scenicTitleBridgePolicy"), dict) else {}
    candidate = resolve_path(policy.get("manifest"))
    if candidate and candidate.exists():
        return candidate
    return package_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json"


def is_placeholder(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or "").lower()
    license_status = str(item.get("licenseStatus") or "").lower()
    return status in PLACEHOLDER_STATUSES or license_status in PLACEHOLDER_STATUSES or "needs web search" in license_status


def source_paths(blueprint: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for clip in blueprint.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        path = norm_path(clip.get("sourcePath") or clip.get("assetPath"))
        if path:
            out.add(path)
    return out


def source_path_risks(paths: set[str]) -> list[str]:
    risks: list[str] = []
    for path in paths:
        lower = path.lower()
        if any(token in lower for token in BAD_SOURCE_TOKENS):
            risks.append(path)
        elif path and not Path(path).exists():
            risks.append(path)
    return sorted(set(risks))


def route_texture_passed(route_texture: dict[str, Any]) -> bool:
    summary = route_texture.get("summary") if isinstance(route_texture.get("summary"), dict) else {}
    try:
        return (
            route_texture.get("status") == "passed"
            and int(summary.get("chapterWindowCount") or 0) > 0
            and int(summary.get("chapterWindowCount") or 0) == int(summary.get("passedChapters") or -1)
            and int(summary.get("matchedTransitions") or 0) >= 1
        )
    except (TypeError, ValueError):
        return False


def closure_decisions(stock_plan: list[dict[str, Any]], route_ok: bool) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for index, item in enumerate(stock_plan, start=1):
        placeholder = is_placeholder(item)
        if placeholder and route_ok:
            decision = "closed_optional_not_used_covered_by_local_route_texture"
            status = "closed"
            reason = "The final Resolve timeline uses real local/source footage and route bridge clips for this chapter; this search row is a historical optional stock suggestion, not a render dependency."
        elif placeholder:
            decision = "unresolved_placeholder"
            status = "blocked"
            reason = "The placeholder was not materialized and route-texture coverage does not prove it is optional."
        else:
            decision = "materialized_or_not_placeholder"
            status = "closed"
            reason = "This stock/aerial row is not marked as an unresolved search placeholder."
        decisions.append(
            {
                "index": index,
                "chapterIndex": item.get("chapterIndex"),
                "target": item.get("target"),
                "timelineStartSeconds": item.get("timelineStartSeconds"),
                "durationSeconds": item.get("durationSeconds"),
                "trackIndex": item.get("trackIndex"),
                "sourceStatus": item.get("status"),
                "licenseStatus": item.get("licenseStatus"),
                "decision": decision,
                "closureStatus": status,
                "reason": reason,
            }
        )
    return decisions


def update_blueprint_closure(package_dir: Path, blueprint: dict[str, Any], report: dict[str, Any]) -> None:
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    blueprint["stockAerialClosurePolicy"] = {
        "status": report["status"],
        "report": str(package_dir / "stock_aerial_closure_audit.json"),
        "placeholderCount": report["summary"]["placeholderCount"],
        "closedPlaceholderCount": report["summary"]["closedPlaceholderCount"],
        "unresolvedPlaceholderCount": report["summary"]["unresolvedPlaceholderCount"],
        "closureMode": "materialized_or_explicitly_closed",
        "note": "Unmaterialized stock/aerial search rows are not final render dependencies when closed by this audit.",
    }
    write_json(blueprint_path, blueprint)


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    blueprint = load_json(blueprint_path) or {}
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    title_manifest_path = infer_title_manifest(package_dir, blueprint)
    title_manifest = load_json(title_manifest_path) or {}
    route_texture = load_json(package_dir / "route_texture_contract_audit.json") or {}
    director = load_json(package_dir / "director_polish_contract_audit.json") or {}
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    stock_plan = [row for row in blueprint.get("stockInsertPlan") or [] if isinstance(row, dict)]
    placeholders = [row for row in stock_plan if is_placeholder(row)]
    verified_aerials = verified_aerial_items(ledger)
    segments = title_segments(title_manifest)
    opening = next((row for row in segments if str(row.get("mode") or "").lower() == "opening"), None)
    ending = next((row for row in segments if str(row.get("mode") or "").lower() == "ending"), None)
    paths = source_paths(blueprint)
    risks = source_path_risks(paths)
    route_ok = route_texture_passed(route_texture)
    decisions = closure_decisions(stock_plan, route_ok)
    unresolved = [row for row in decisions if row["closureStatus"] == "blocked"]
    closed_placeholders = [
        row
        for row in decisions
        if row["closureStatus"] == "closed"
        and (
            str(row.get("sourceStatus") or "").lower() in PLACEHOLDER_STATUSES
            or str(row.get("licenseStatus") or "").lower() in PLACEHOLDER_STATUSES
            or "needs web search" in str(row.get("licenseStatus") or "").lower()
        )
    ]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "Blueprint stock/aerial plan is inspected and classified",
        bool(blueprint) and isinstance(blueprint.get("stockInsertPlan"), list),
        {"blueprint": str(blueprint_path), "stockInsertPlanCount": len(stock_plan), "placeholderCount": len(placeholders)},
    )
    add_check(
        checks,
        "Required opening aerial or establishing asset is verified and used",
        bool(opening)
        and path_exists(opening.get("source"))
        and path_exists(opening.get("segment"))
        and bool(verified_aerials)
        and any(norm_path(item.get("localPath")) == norm_path(opening.get("source")) for item in verified_aerials),
        {"opening": opening, "verifiedAerials": verified_aerials},
    )
    add_check(
        checks,
        "Ending title uses real establishing footage and not a slate",
        bool(ending) and path_exists(ending.get("source")) and path_exists(ending.get("segment")),
        {"ending": ending},
    )
    add_check(
        checks,
        "Resolve timeline does not depend on unresolved stock placeholders",
        not risks,
        {"sourcePathRiskCount": len(risks), "sourcePathRisks": risks[:30]},
    )
    add_check(
        checks,
        "Route texture audit proves optional stock placeholders are covered by real timeline footage",
        route_ok,
        {"routeTextureStatus": route_texture.get("status"), "routeTextureSummary": route_texture.get("summary")},
    )
    add_check(
        checks,
        "Stock/aerial placeholders are materialized or explicitly closed",
        not unresolved,
        {
            "placeholderCount": len(placeholders),
            "closedPlaceholderCount": len(closed_placeholders),
            "unresolvedPlaceholderCount": len(unresolved),
            "unresolved": unresolved[:20],
        },
    )
    add_check(
        checks,
        "Existing director-polish warning is explainable by closure evidence",
        director.get("status") in {"passed", "passed_with_warnings", None}
        and render.get("status") in {"passed", None},
        {"directorPolishStatus": director.get("status"), "directorPolishWarnings": director.get("warnings"), "renderStatus": render.get("status")},
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings = [row["name"] for row in checks if row["status"] == "warning"]
    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "stockInsertPlanCount": len(stock_plan),
            "placeholderCount": len(placeholders),
            "closedPlaceholderCount": len(closed_placeholders),
            "unresolvedPlaceholderCount": len(unresolved),
            "verifiedAerialCount": len(verified_aerials),
            "sourcePathRiskCount": len(risks),
            "routeTexturePassed": route_ok,
        },
        "closureDecisions": decisions,
        "contract": {
            "purpose": "Prevent search-only stock/aerial plans from masquerading as finished assets.",
            "allowedClosure": "A placeholder can be closed without download only when it is not referenced by the final Resolve timeline and route/title audits prove real local or verified stock footage covers the need.",
            "notAllowed": "Do not fabricate that stock footage was downloaded; unresolved placeholders must be materialized, explicitly closed with coverage evidence, or kept as blockers.",
        },
    }
    if args.update_blueprint and status != "blocked":
        update_blueprint_closure(package_dir, blueprint, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Stock/Aerial Closure Audit",
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
        evidence = json.dumps(row["evidence"], ensure_ascii=False)[:2200]
        lines.extend(["", f"### {row['name']}", f"- Status: `{row['status']}`", f"- Evidence: `{evidence}`"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Closure Decisions"])
    for row in report["closureDecisions"][:120]:
        lines.append(f"- `{row['closureStatus']}` chapter=`{row.get('chapterIndex')}` target=`{row.get('target')}` decision=`{row['decision']}`")
    lines.extend(["", "## Contract", "", "```json", json.dumps(report["contract"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit stock/aerial placeholders for materialization or explicit closure.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--update-blueprint", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        package_dir = Path(args.package_dir)
        report = build_report(package_dir, args)
    except Exception as exc:
        print(f"audit_stock_aerial_closure failed: {exc}")
        return 1
    package_dir = Path(args.package_dir).expanduser().resolve()
    write_json(package_dir / "stock_aerial_closure_audit.json", report)
    write_markdown(package_dir / "stock_aerial_closure_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
