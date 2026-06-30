#!/usr/bin/env python3
"""Audit cross-project forward-test evidence for Travel Video Studio skill maturity."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


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


def skill_dir_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def status_of(path: Path) -> str | None:
    data = load_json(path)
    return data.get("status") if isinstance(data, dict) else None


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if passed else ("warning" if warning else "blocked"),
            "evidence": evidence,
        }
    )


def recovery_command_texts(recovery_plan: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for phase in recovery_plan.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        for command in phase.get("commands") or []:
            if isinstance(command, dict) and command.get("command"):
                texts.append(str(command["command"]))
    return texts


def checks_with_text(data: dict[str, Any], needle: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for key in ("checks", "requirements"):
        for row in data.get(key) or []:
            if not isinstance(row, dict):
                continue
            text = " ".join(str(row.get(field) or "") for field in ("name", "requirement"))
            if needle.lower() in text.lower():
                matches.append(row)
    return matches


def run_quick_validate(skill_dir: Path, validator: Path | None) -> dict[str, Any]:
    if not validator:
        codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
        default = codex_home / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
        validator = default if default.exists() else None
    if not validator or not validator.exists():
        return {"available": False, "returnCode": None, "stdout": "", "stderr": "quick_validate.py not found"}
    proc = subprocess.run([sys.executable, str(validator), str(skill_dir)], check=False, capture_output=True, text=True)
    return {
        "available": True,
        "command": [sys.executable, str(validator), str(skill_dir)],
        "returnCode": proc.returncode,
        "stdout": proc.stdout[-2000:],
        "stderr": proc.stderr[-2000:],
    }


def latest_recognition_report(project_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    pointer = load_json(project_dir / "latest_footage_recognition_route_report.json")
    if isinstance(pointer, dict) and pointer.get("report"):
        path = Path(str(pointer["report"])).expanduser()
        if path.exists():
            data = load_json(path)
            if isinstance(data, dict):
                return path, data
    candidates = sorted((project_dir / "recognition_reports").glob("*/footage_recognition_route_report.json"))
    for path in reversed(candidates):
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    return None, None


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    skill_dir = Path(args.skill_dir).expanduser().resolve() if args.skill_dir else skill_dir_from_script()
    intake_path = Path(args.intake_json).expanduser().resolve()
    ready_package = Path(args.ready_package_dir).expanduser().resolve() if args.ready_package_dir else None
    blocked_project = Path(args.blocked_project_dir).expanduser().resolve() if args.blocked_project_dir else None
    blocked_location_path = Path(args.blocked_location_truth_json).expanduser().resolve() if args.blocked_location_truth_json else None
    blocked_recovery_path = Path(args.blocked_recovery_plan_json).expanduser().resolve()
    checks: list[dict[str, Any]] = []

    validation = run_quick_validate(skill_dir, Path(args.quick_validate).expanduser().resolve() if args.quick_validate else None)
    add_check(
        checks,
        "Installed Skill validates before forward-test evidence is trusted",
        validation.get("returnCode") == 0,
        validation,
    )

    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="ignore") if (skill_dir / "SKILL.md").exists() else ""
    add_check(
        checks,
        "Skill instructions require regression-first and forward-test thinking",
        "Treat every live edit as Skill regression testing" in skill_text
        and "forward-test" in skill_text.lower()
        and "Do not call a turn complete when it only patches one output" in skill_text,
        {"skill": str(skill_dir / "SKILL.md")},
    )

    intake = load_json(intake_path) or {}
    choices = intake.get("recommendedChoices") if isinstance(intake.get("recommendedChoices"), list) else []
    ready_choices = [row for row in choices if isinstance(row, dict) and row.get("status") == "ready_for_project_workflow"]
    unknown_choices = [row for row in choices if isinstance(row, dict) and row.get("status") == "needs_identification"]
    region_set = sorted({str(row.get("region")) for row in choices if isinstance(row, dict) and row.get("region")})
    safety = intake.get("safety") if isinstance(intake.get("safety"), dict) else {}
    add_check(
        checks,
        "External intake distinguishes multiple mounted trip roots instead of defaulting silently",
        intake.get("status") == "ready_for_project_choice"
        and len(choices) >= 2
        and len(ready_choices) >= 2
        and bool(unknown_choices)
        and len(region_set) >= 2
        and safety.get("modifiesSourceDrive") is False,
        {
            "intake": str(intake_path),
            "status": intake.get("status"),
            "choiceCount": len(choices),
            "readyChoices": [(row.get("choiceId"), row.get("recommendedProjectName")) for row in ready_choices],
            "unknownChoices": [row.get("choiceId") for row in unknown_choices],
            "regions": region_set,
            "warnings": intake.get("warnings"),
            "safety": safety,
        },
    )

    final_qa = load_json(ready_package / "final_qa_suite_report.json") if ready_package else None
    current_client = load_json(ready_package / "client_delivery_rules_audit.json") if ready_package else None
    orientation_rows = checks_with_text(current_client, "raw portrait/square/unknown") if isinstance(current_client, dict) else []
    orientation_evidence = orientation_rows[0].get("evidence") if orientation_rows else {}
    stages = final_qa.get("stages") if isinstance(final_qa, dict) and isinstance(final_qa.get("stages"), list) else []
    stage_names = {row.get("stage"): row for row in stages if isinstance(row, dict)}
    add_check(
        checks,
        "Known-good package still passes full final QA and current client gates",
        isinstance(final_qa, dict)
        and final_qa.get("status") == "passed"
        and int((final_qa.get("summary") or {}).get("totalStages") or 0) >= args.min_final_qa_stages
        and "director_intent_contract_audit" in stage_names
        and "location_truth_contract_audit" in stage_names,
        {
            "package": str(ready_package) if ready_package else None,
            "status": final_qa.get("status") if isinstance(final_qa, dict) else None,
            "summary": final_qa.get("summary") if isinstance(final_qa, dict) else None,
            "stageNames": sorted(stage_names),
        },
    )
    add_check(
        checks,
        "Known-good package current client audit includes the latest blueprint source-orientation gate",
        isinstance(current_client, dict)
        and current_client.get("status") == "passed"
        and bool(orientation_evidence)
        and orientation_rows[0].get("status") == "passed"
        and int(orientation_evidence.get("checkedVideoClipCount") or 0) > 0
        and int(orientation_evidence.get("blockedNonLandscapeCount") or 0) == 0
        and not orientation_evidence.get("probeErrors"),
        {
            "package": str(ready_package) if ready_package else None,
            "clientStatus": current_client.get("status") if isinstance(current_client, dict) else None,
            "clientBlockers": current_client.get("blockers") if isinstance(current_client, dict) else None,
            "orientationEvidence": orientation_evidence,
        },
    )

    recognition_path, recognition = latest_recognition_report(blocked_project) if blocked_project else (None, None)
    recognition_blockers = recognition.get("blockers") if isinstance(recognition, dict) and isinstance(recognition.get("blockers"), list) else []
    recognition_summary = recognition.get("summary") if isinstance(recognition, dict) and isinstance(recognition.get("summary"), dict) else {}
    add_check(
        checks,
        "Blocked forward-test project is correctly refused before cutting",
        isinstance(recognition, dict)
        and recognition.get("status") == "blocked"
        and int(recognition_summary.get("mediaVideoCount") or 0) >= args.min_blocked_project_videos
        and any("Cloud vision recognition did not actually run" in item for item in recognition_blockers)
        and any("confirmed_route_timeline" in item for item in recognition_blockers)
        and any("Route review" in item for item in recognition_blockers),
        {
            "project": str(blocked_project) if blocked_project else None,
            "recognitionReport": str(recognition_path) if recognition_path else None,
            "status": recognition.get("status") if isinstance(recognition, dict) else None,
            "summary": recognition_summary,
            "blockers": recognition_blockers,
        },
    )

    blocked_location = load_json(blocked_location_path)
    blocked_summary = blocked_location.get("summary") if isinstance(blocked_location, dict) and isinstance(blocked_location.get("summary"), dict) else {}
    add_check(
        checks,
        "Blocked forward-test project cannot claim route-ready or exact per-video location truth",
        isinstance(blocked_location, dict)
        and blocked_location.get("status") == "blocked"
        and blocked_summary.get("routeAwareEditClaimAllowed") is False
        and blocked_summary.get("exactPerVideoLocationClaimAllowed") is False
        and int(blocked_summary.get("expectedActiveSourceCount") or 0) >= args.min_blocked_project_videos,
        {
            "locationTruth": str(blocked_location_path) if blocked_location_path else None,
            "status": blocked_location.get("status") if isinstance(blocked_location, dict) else None,
            "summary": blocked_summary,
            "blockers": blocked_location.get("blockers") if isinstance(blocked_location, dict) else None,
        },
    )

    recovery_plan = load_json(blocked_recovery_path)
    recovery_summary = recovery_plan.get("summary") if isinstance(recovery_plan, dict) and isinstance(recovery_plan.get("summary"), dict) else {}
    recovery_safety = recovery_plan.get("safety") if isinstance(recovery_plan, dict) and isinstance(recovery_plan.get("safety"), dict) else {}
    recovery_blockers = set(recovery_plan.get("blockerTypes") or []) if isinstance(recovery_plan, dict) else set()
    recovery_commands = recovery_command_texts(recovery_plan) if isinstance(recovery_plan, dict) else []
    required_command_names = [
        "prepare_route_review.py",
        "prepare_route_decision_sheet.py",
        "prepare_confirmed_route_candidate.py",
        "audit_confirmed_route_candidate.py",
        "prepare_footage_recognition_report.py",
        "audit_location_truth_contract.py",
    ]
    add_check(
        checks,
        "Blocked forward-test project gets an actionable recovery plan instead of a dead-end refusal",
        isinstance(recovery_plan, dict)
        and recovery_plan.get("status") == "recovery_plan_ready"
        and recovery_plan.get("editingAllowedNow") is False
        and len(recovery_plan.get("phases") or []) >= 5
        and {"provider_missing", "confirmed_route_missing", "route_review_pending", "route_not_ready"}.issubset(recovery_blockers)
        and all(name in "\n".join(recovery_commands) for name in required_command_names)
        and recovery_safety.get("modifiesSourceDrive") is False
        and recovery_safety.get("writesResolve") is False
        and recovery_safety.get("downloadsExternalAssets") is False
        and recovery_safety.get("callsCloudVisionByDefault") is False
        and recovery_safety.get("requiresExplicitApprovalForCloud") is True,
        {
            "recoveryPlan": str(blocked_recovery_path),
            "status": recovery_plan.get("status") if isinstance(recovery_plan, dict) else None,
            "summary": recovery_summary,
            "blockerTypes": sorted(recovery_blockers),
            "commandNamesRequired": required_command_names,
            "commandsFound": recovery_commands[:12],
            "safety": recovery_safety,
        },
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    warnings = [row["name"] for row in checks if row["status"] == "warning"]
    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "skillDir": str(skill_dir),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "passed": len([row for row in checks if row["status"] == "passed"]),
            "blocked": len(blockers),
            "warnings": len(warnings),
            "total": len(checks),
        },
        "contract": {
            "purpose": "Prove the Skill generalizes beyond one successful package by testing a ready package, a matched-but-blocked trip, an unknown mounted media root, and an actionable recovery path for blocked trips.",
            "notCompletionProof": "This is stronger forward-test evidence, but still not proof that all future travel folders will be perfect without more trips and real renders.",
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Skill Forward-Test Contract Audit",
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
    for row in report["checks"]:
        evidence = json.dumps(row["evidence"], ensure_ascii=False)[:2400]
        lines.extend(["", f"### {row['name']}", f"- Status: `{row['status']}`", f"- Evidence: `{evidence}`"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Contract", "", "```json", json.dumps(report["contract"], ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit cross-project forward-test evidence for Skill maturity.")
    parser.add_argument("--skill-dir")
    parser.add_argument("--intake-json", required=True)
    parser.add_argument("--ready-package-dir", required=True)
    parser.add_argument("--blocked-project-dir", required=True)
    parser.add_argument("--blocked-location-truth-json", required=True)
    parser.add_argument("--blocked-recovery-plan-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--quick-validate")
    parser.add_argument("--min-final-qa-stages", type=int, default=17)
    parser.add_argument("--min-blocked-project-videos", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args)
    output_dir = Path(args.output_dir).expanduser().resolve()
    write_json(output_dir / "skill_forward_test_contract_audit.json", report)
    write_markdown(output_dir / "skill_forward_test_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "warnings": report["warnings"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
