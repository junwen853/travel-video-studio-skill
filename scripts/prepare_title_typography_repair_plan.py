#!/usr/bin/env python3
"""Prepare repair rows for blocked cover, title, and typography gates."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ACCEPTED_REPORT_STATUSES = {
    "title_typography_plan": {"ready_with_clean_title_typography_plan"},
    "title_bridge_contract_audit": {"passed", "passed_with_warnings"},
    "cover_title_contract_audit": {"passed"},
    "title_visual_proof_contract_audit": {"passed"},
}

DECISION_FIELDS = {
    "repairAccepted": False,
    "ownerScriptExecuted": "",
    "approvedTitleText": "",
    "approvedSubtitleText": "",
    "approvedFontEvidence": "",
    "approvedBackgroundEvidence": "",
    "updatedManifestEvidence": "",
    "updatedBlueprintEvidence": "",
    "renderFrameSampleEvidence": "",
    "postRepairAudit": "",
    "editorNotes": "",
}

DEFAULT_ACTION = {
    "priority": "P0",
    "ownerScript": "prepare_title_typography_plan.py",
    "requiredArtifact": "title_typography_plan/title_typography_plan.json",
    "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
    "repairType": "repair_title_typography_plan",
    "requiredAction": "Rebuild the title typography plan with one clean destination title, verified font evidence, scenic video background evidence, and title-zone subtitle suppression.",
    "acceptanceEvidence": "title_typography_plan is ready, cover/title and title visual proof audits pass, and final QA reports no title repair rows.",
}

ISSUE_ACTIONS: list[tuple[tuple[str, ...], dict[str, str]]] = [
    (
        ("stack", "ghost", "duplicate", "extra text", "subtitle overlay", "title-zone", "collision"),
        {
            "ownerScript": "prepare_scenic_title_bridges.py",
            "requiredArtifact": "clean_scenic_title_bridges/clean_scenic_title_bridges_manifest.json",
            "command": "python3 <skill-dir>/scripts/prepare_scenic_title_bridges.py --package-dir <package> --update-blueprint --json",
            "repairType": "remove_stacked_or_overlapping_title_text",
            "requiredAction": "Regenerate scenic title bridges with only one main title layer and suppress rendered subtitles inside every title window.",
            "acceptanceEvidence": "title bridge and visual proof audits show zero extra text layers, zero subtitle overlays, and clean frame samples.",
        },
    ),
    (
        ("route", "date", "internal", "project", "label", "slug", "codex", "resolve", "v14", "qa", "srt", "txt"),
        {
            "ownerScript": "prepare_title_typography_plan.py",
            "requiredArtifact": "title_typography_plan/title_typography_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
            "repairType": "remove_route_date_or_internal_title_text",
            "requiredAction": "Replace route/date/internal title text with a single audience-facing destination title and a short designed place/English subtitle where allowed.",
            "acceptanceEvidence": "cover/title, title bridge, audience caption, and story-style audits show no route/date/internal workflow text in viewer-facing title windows.",
        },
    ),
    (
        ("black", "slate", "title_cards", "png", "jpg", "missing media", "missing", "not video", "background"),
        {
            "ownerScript": "prepare_scenic_title_bridges.py",
            "requiredArtifact": "clean_scenic_title_bridges/clean_scenic_title_bridges_manifest.json",
            "command": "python3 <skill-dir>/scripts/prepare_scenic_title_bridges.py --package-dir <package> --update-blueprint --json",
            "repairType": "replace_bad_title_background",
            "requiredAction": "Replace black slates, stale title_cards, PNG/JPG cards, or missing title media with high-recognition scenic video from local footage or approved stock/aerial evidence.",
            "acceptanceEvidence": "title visual proof ffprobe/frame samples pass with 16:9 scenic video segments and no stale title_cards source paths.",
        },
    ),
    (
        ("font", "license", "typography"),
        {
            "ownerScript": "prepare_title_typography_plan.py",
            "requiredArtifact": "title_typography_plan/title_typography_plan.json",
            "command": "python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package> --json",
            "repairType": "repair_font_or_typography_evidence",
            "requiredAction": "Attach verified system-font-render-only or licensed font evidence and ensure the title design uses readable high-contrast hero typography.",
            "acceptanceEvidence": "title typography plan reports verified font evidence and cover/title audit accepts the hero formula.",
        },
    ),
    (
        ("cover", "hero", "oversized", "establish", "recognition", "16:9", "screenshot"),
        {
            "ownerScript": "prepare_scenic_title_bridges.py",
            "requiredArtifact": "clean_scenic_title_bridges/clean_scenic_title_bridges_manifest.json",
            "command": "python3 <skill-dir>/scripts/prepare_scenic_title_bridges.py --package-dir <package> --update-blueprint --json",
            "repairType": "repair_cover_hero_title_formula",
            "requiredAction": "Choose a high-recognition 16:9 establishing background and oversized destination title, with no screenshot chrome, clutter, route/date labels, or timid small text.",
            "acceptanceEvidence": "cover/title contract passes and extracted title proof frames show a clean Parallel World/Malta-style hero title.",
        },
    ),
]


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


def clean(value: Any, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def report_specs(package_dir: Path) -> dict[str, Path]:
    return {
        "title_typography_plan": package_dir / "title_typography_plan" / "title_typography_plan.json",
        "title_bridge_contract_audit": package_dir / "title_bridge_contract_audit.json",
        "cover_title_contract_audit": package_dir / "cover_title_contract_audit.json",
        "title_visual_proof_contract_audit": package_dir / "title_visual_proof_contract_audit.json",
    }


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def blocked_checks(data: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for check in data.get("checks") or []:
        if not isinstance(check, dict):
            continue
        if check.get("status") in {"passed", "passed_with_warnings"}:
            continue
        name = clean(check.get("name"), 240)
        evidence = check.get("evidence") if isinstance(check.get("evidence"), dict) else {}
        detail = clean(json.dumps(evidence, ensure_ascii=False), 400) if evidence else ""
        rows.append(f"{name}: {detail}" if detail else name)
    return rows


def report_issues(report_id: str, path: Path, data: dict[str, Any]) -> list[str]:
    accepted = ACCEPTED_REPORT_STATUSES[report_id]
    issues: list[str] = []
    if not path.exists():
        issues.append(f"{report_id} is missing")
        return issues
    status = str(data.get("status") or "")
    if status not in accepted:
        issues.append(f"{report_id} status is {status or 'unknown'}")
    issues.extend(clean(item) for item in data.get("blockers") or [] if clean(item))
    issues.extend(blocked_checks(data))
    return issues


def issue_action(issue_text: str) -> dict[str, str]:
    lowered = issue_text.lower()
    for keywords, action in ISSUE_ACTIONS:
        if any(keyword in lowered for keyword in keywords):
            merged = dict(DEFAULT_ACTION)
            merged.update(action)
            return merged
    return dict(DEFAULT_ACTION)


def affected_evidence(report_id: str, data: dict[str, Any]) -> dict[str, Any]:
    summary = summary_of(data)
    out = {
        "status": data.get("status"),
        "summary": summary,
    }
    if report_id == "title_typography_plan":
        out.update(
            {
                "titleRowCount": summary.get("titleRowCount"),
                "cleanRowCount": summary.get("cleanRowCount"),
                "fontVerified": summary.get("fontVerified"),
                "titleZoneMode": summary.get("titleZoneMode"),
                "stackExtraTextLayerCount": summary.get("stackExtraTextLayerCount"),
                "stackSubtitleOverlayCount": summary.get("stackSubtitleOverlayCount"),
            }
        )
    if report_id == "cover_title_contract_audit":
        out.update({"mainTitle": summary.get("mainTitle"), "secondaryTitle": summary.get("secondaryTitle")})
    if report_id == "title_visual_proof_contract_audit":
        out.update(
            {
                "segmentCount": summary.get("segmentCount"),
                "validFrameSampleCount": summary.get("validFrameSampleCount"),
                "blockedSegmentCount": summary.get("blockedSegmentCount"),
            }
        )
    return out


def make_repair_row(
    *,
    ordinal: int,
    report_id: str,
    report_path: Path,
    issue_text: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    action = issue_action(issue_text)
    return {
        "repairId": f"title_typography_{report_id}_{ordinal}",
        "priority": action["priority"],
        "phase": "title_establishing",
        "issueType": action["repairType"],
        "sourceReport": report_id,
        "sourceReportPath": str(report_path),
        "sourceReportExists": report_path.exists(),
        "sourceStatus": data.get("status"),
        "issue": issue_text,
        "ownerScript": action["ownerScript"],
        "requiredArtifact": action["requiredArtifact"],
        "command": action["command"],
        "requiredAction": action["requiredAction"],
        "allowedFixes": [
            "single clean destination title",
            "short designed English/place subtitle only where allowed",
            "verified scenic video background",
            "verified font or system-font-render-only evidence",
            "subtitle suppression inside title windows",
            "updated Resolve blueprint title clip source paths",
        ],
        "forbiddenFixes": [
            "stacked duplicate title layers",
            "route/date/project labels behind the hero title",
            "black slate or stale title_cards media",
            "PNG/JPG title card in a final 16:9 master",
            "rendered subtitles over the hero/chapter title",
            "unverified font or stock background claims",
        ],
        "acceptanceEvidence": action["acceptanceEvidence"],
        "forbiddenWorkaround": "Do not cover title defects with shadows, duplicated text, extra labels, OCR excuses, or a stronger effect; rebuild the title media and prove it with structural audits plus frame samples.",
        "affectedEvidence": affected_evidence(report_id, data),
        "decision": dict(DECISION_FIELDS),
    }


def build_plan(package_dir: Path, output_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    specs = report_specs(package_dir)
    reports: dict[str, dict[str, Any]] = {}
    repair_rows: list[dict[str, Any]] = []
    ordinal = 0
    for report_id, path in specs.items():
        data = load_json(path) or {}
        reports[report_id] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(ACCEPTED_REPORT_STATUSES[report_id]),
            "summary": summary_of(data),
        }
        for issue in report_issues(report_id, path, data):
            ordinal += 1
            repair_rows.append(
                make_repair_row(
                    ordinal=ordinal,
                    report_id=report_id,
                    report_path=path,
                    issue_text=issue,
                    data=data,
                )
            )

    status = "ready_no_title_typography_repairs_needed" if not repair_rows else "ready_with_title_typography_repair_plan"
    summary = {
        "repairRowCount": len(repair_rows),
        "reportsChecked": len(reports),
        "blockedReportCount": sum(1 for row in reports.values() if row.get("status") not in row.get("acceptedStatuses", [])),
        "missingReportCount": sum(1 for row in reports.values() if row.get("exists") is not True),
        "ownerScripts": sorted({str(row.get("ownerScript")) for row in repair_rows if row.get("ownerScript")}),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {"reports": reports},
        "summary": summary,
        "repairRows": repair_rows,
        "nextActions": [
            "Run each title-establishing ownerScript in priority order.",
            "Rerun prepare_title_typography_plan.py, audit_cover_title_contract.py, audit_title_bridge_contract.py, audit_title_visual_proof_contract.py --extract-frames, final QA, V14, and maturity checks.",
            "Do not write Resolve, render, or claim delivery while this plan has open P0 repair rows.",
        ],
        "safety": safety(),
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Title Typography Repair Plan",
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
        "## Repair Rows",
    ]
    if not plan.get("repairRows"):
        lines.append("- None.")
    for row in plan.get("repairRows", [])[:200]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Source report: `{row.get('sourceReport')}`",
                f"- Issue type: `{row.get('issueType')}`",
                f"- Issue: {row.get('issue')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Required artifact: `{row.get('requiredArtifact')}`",
                f"- Required action: {row.get('requiredAction')}",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Contract",
            "- A title repair plan with repair rows is not a delivery pass.",
            "- Repair title media and blueprint references before relying on OCR or final-render contact sheets.",
            "- Re-run structural title audits and frame-sample visual proof after every title repair.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare repair rows for blocked cover/title/typography checks.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/title_typography_repair_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "title_typography_repair_plan"
    plan = build_plan(package_dir, output_dir)
    write_json(output_dir / "title_typography_repair_plan.json", plan)
    write_markdown(output_dir / "title_typography_repair_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
