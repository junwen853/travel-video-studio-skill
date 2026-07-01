#!/usr/bin/env python3
"""Audit that reusable travel-video scripts do not hard-code the previous trip."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


RISK_PATTERNS = [
    {
        "id": "stylefix_forces_tokyo_title",
        "file": "make_davinci_stylefix_blueprint.py",
        "pattern": r'"(?:cityTitle|titleText)"\s*:\s*"TOKYO"',
        "detail": "Style-fix blueprint must infer or accept an opening title instead of forcing TOKYO.",
    },
    {
        "id": "stylefix_tokyo_opening_place",
        "file": "make_davinci_stylefix_blueprint.py",
        "pattern": r'"Tokyo opening"|single TOKYO title|title-only TOKYO',
        "detail": "Style-fix opening labels must not be Tokyo-specific.",
    },
    {
        "id": "stylefix_japan_default_resolve_name",
        "file": "make_davinci_stylefix_blueprint.py",
        "pattern": r'default\s*=\s*"[^"]*(?:日本|东京|大阪|TOKYO|OSAKA|JAPAN)[^"]*"',
        "detail": "Style-fix CLI defaults must not name the Japan/Tokyo/Osaka trip.",
    },
    {
        "id": "orientation_repair_japan_default_resolve_name",
        "file": "prepare_orientation_repair_package.py",
        "pattern": r'"[^"]*(?:日本|东京|大阪|TOKYO|OSAKA|JAPAN)[^"]*Orientation Repair[^"]*"',
        "detail": "Orientation repair defaults must derive names from the source package.",
    },
    {
        "id": "delivery_package_tokyo_fallback",
        "file": "build_delivery_package.py",
        "pattern": r'\{"index":\s*1,\s*"place":\s*"Tokyo"\}',
        "detail": "Delivery-package fallback chapters must be generic unless the media/project proves Tokyo.",
    },
    {
        "id": "quality_recut_forces_tokyo_title",
        "file": "prepare_quality_recut.py",
        "pattern": r'--(?:city-title|opening-subtitle|ending-city-title|ending-subtitle)"\s*,\s*default\s*=\s*"[^"]*(?:TOKYO|OSAKA|JAPAN)[^"]*"',
        "detail": "Quality recut CLI defaults must infer titles from the source package instead of forcing Japan text.",
    },
    {
        "id": "quality_recut_tokyo_osaka_caption",
        "file": "prepare_quality_recut.py",
        "pattern": r"东京到大阪|日本东京大阪行",
        "detail": "Quality recut captions and narration handoff must be trip-neutral unless inferred from source.",
    },
    {
        "id": "route_decision_forces_japan_country",
        "file": "prepare_route_decision_sheet.py",
        "pattern": r'corrections\["country"\]\s*=\s*"Japan"',
        "detail": "Route decisions must infer country from evidence/review context, not default to Japan.",
    },
    {
        "id": "route_decision_japan_resolution",
        "file": "prepare_route_decision_sheet.py",
        "pattern": r'"accept_inferred_japan_route"\s+if mismatch',
        "detail": "Region-mismatch approvals must use a generic inferred-media-route resolution.",
    },
]

REQUIRED_DERIVATION_TOKENS = {
    "make_davinci_stylefix_blueprint.py": ["infer_opening_title", "infer_project_name", "infer_bgm_mood"],
    "prepare_orientation_repair_package.py": ["default_resolve_names"],
    "prepare_quality_recut.py": ["infer_title_from_payloads", "infer_route_subtitle"],
    "prepare_route_decision_sheet.py": ["inferred_country_from_review", "accept_inferred_media_route"],
}

REQUIRED_CONTRACT_TOKENS = {
    "audit_transition_audition_quality_contract.py": [
        "packet_summary.get(\"buildClips\")",
        "packet_summary.get(\"builtClips\")",
        "packet_inputs.get(\"buildClips\")",
    ],
    "prepare_editorial_watchdown_repair_plan.py": [
        "TIME_RANGE_RE",
        "reviewedAt is older than the current final MP4 mtime",
        "decisionIssueCount",
        "rowsReviewedAfterFinalOutputMtime",
    ],
    "audit_skill_maturity_contract.py": [
        "rowsReviewedAfterFinalOutputMtime",
        "rowsWithTimecodedOrFullRange",
    ],
    "audit_v14_baseline_contract.py": [
        "rowsReviewedAfterFinalOutputMtime",
        "rowsWithTimecodedOrFullRange",
    ],
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def skill_dir_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def markdown_paths(skill_dir: Path) -> list[Path]:
    paths = [skill_dir / "SKILL.md", skill_dir / "README.md"]
    references_dir = skill_dir / "references"
    if references_dir.exists():
        paths.extend(sorted(references_dir.glob("*.md")))
    return [path for path in paths if path.exists()]


def transition_audition_command_check(skill_dir: Path) -> dict[str, Any]:
    token = "prepare_transition_audition_packet.py"
    matches: list[dict[str, Any]] = []
    scanned = 0
    for path in markdown_paths(skill_dir):
        scanned += 1
        lines = read_text(path).splitlines()
        for index, line in enumerate(lines):
            if token not in line:
                continue
            window = "\n".join(lines[index : index + 4])
            if "--build-clips" in window:
                continue
            matches.append(
                {
                    "file": str(path),
                    "line": index + 1,
                    "text": line.strip()[:240],
                }
            )
    return {
        "name": "transition_audition_commands_build_clips",
        "status": "passed" if not matches else "blocked",
        "file": str(skill_dir),
        "detail": "Reference docs and SKILL instructions must not teach metadata-only transition audition packets; use prepare_transition_audition_packet.py --build-clips.",
        "filesScanned": scanned,
        "matches": matches[:40],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    skill_dir = Path(args.skill_dir).expanduser().resolve() if args.skill_dir else skill_dir_from_script()
    scripts_dir = skill_dir / "scripts"
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    for rule in RISK_PATTERNS:
        path = scripts_dir / str(rule["file"])
        text = read_text(path)
        matches = [
            {"line": line_no, "text": line.strip()[:240]}
            for line_no, line in enumerate(text.splitlines(), start=1)
            if re.search(str(rule["pattern"]), line)
        ]
        passed = path.exists() and not matches
        checks.append(
            {
                "name": rule["id"],
                "status": "passed" if passed else "blocked",
                "file": str(path),
                "detail": rule["detail"],
                "matches": matches[:20],
            }
        )
        if not path.exists():
            blockers.append(f"{rule['file']} is missing.")
        elif matches:
            blockers.append(str(rule["detail"]))

    for filename, tokens in REQUIRED_DERIVATION_TOKENS.items():
        path = scripts_dir / filename
        text = read_text(path)
        missing = [token for token in tokens if token not in text]
        checks.append(
            {
                "name": f"{filename} exposes generic derivation hooks",
                "status": "passed" if path.exists() and not missing else "blocked",
                "file": str(path),
                "requiredTokens": tokens,
                "missingTokens": missing,
            }
        )
        if missing:
            blockers.append(f"{filename} is missing generic derivation hooks: {', '.join(missing)}")

    for filename, tokens in REQUIRED_CONTRACT_TOKENS.items():
        path = scripts_dir / filename
        text = read_text(path)
        missing = [token for token in tokens if token not in text]
        checks.append(
            {
                "name": f"{filename} preserves reusable contract tokens",
                "status": "passed" if path.exists() and not missing else "blocked",
                "file": str(path),
                "requiredTokens": tokens,
                "missingTokens": missing,
            }
        )
        if missing:
            blockers.append(f"{filename} is missing reusable contract tokens: {', '.join(missing)}")

    audition_command_check = transition_audition_command_check(skill_dir)
    checks.append(audition_command_check)
    if audition_command_check["status"] == "blocked":
        blockers.append("Transition audition commands must include --build-clips in SKILL/reference docs.")

    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else skill_dir / "qa" / "trip_generalization"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "skillDir": str(skill_dir),
        "checks": checks,
        "blockers": sorted(dict.fromkeys(blockers)),
        "warnings": sorted(dict.fromkeys(warnings)),
        "summary": {
            "passed": len([check for check in checks if check["status"] == "passed"]),
            "blocked": len([check for check in checks if check["status"] == "blocked"]),
            "warnings": len(warnings),
            "total": len(checks),
        },
        "outputJson": str(output_dir / "trip_generalization_contract_audit.json"),
        "outputMarkdown": str(output_dir / "trip_generalization_contract_audit.md"),
        "contract": {
            "purpose": "Prevent a repair script written for one Japan/Tokyo/Osaka package from silently contaminating future trips.",
            "notAStyleProof": "This is a script-generalization guard. It complements, but does not replace, package render QA and visual review.",
        },
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Trip Generalization Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Skill: `{report['skillDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Checks",
    ]
    for check in report.get("checks") or []:
        lines.extend(
            [
                "",
                f"### {check['name']}",
                f"- Status: `{check['status']}`",
                f"- File: `{check['file']}`",
            ]
        )
        if check.get("detail"):
            lines.append(f"- Detail: {check['detail']}")
        if check.get("matches"):
            lines.append("- Matches:")
            lines.extend(f"  - line {item['line']}: `{item['text']}`" for item in check["matches"])
        if check.get("missingTokens"):
            lines.append(f"- Missing tokens: `{check['missingTokens']}`")
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Contract", "", "```json", json.dumps(report["contract"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit trip-specific hardcoded defaults in reusable travel-video scripts.")
    parser.add_argument("--skill-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    output_json = Path(report["outputJson"])
    output_markdown = Path(report["outputMarkdown"])
    write_json(output_json, report)
    write_markdown(output_markdown, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
