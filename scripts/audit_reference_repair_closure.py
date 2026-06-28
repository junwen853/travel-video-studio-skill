#!/usr/bin/env python3
"""Audit whether reference-style repair rows are actually closed by evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ACCEPTED_STATUSES = {
    "passed",
    "passed_with_warnings",
    "passed_with_caveats",
    "ready",
    "ready_with_warnings",
    "ready_with_reference_style_repair_plan",
    "ready_no_reference_style_repairs_needed",
    "ready_with_rhythm_recut_blueprint",
    "ready_no_recut_needed",
    "ready_with_transition_polish_blueprint",
    "ready_with_bgm_phrase_blueprint",
    "ready_with_effect_motion_blueprint",
    "ready_with_bridge_sequence_blueprint",
    "ready_with_transition_execution_blueprint",
    "ready_with_creator_cut_plan",
    "ready_with_edit_rhythm_plan",
    "ready_with_opening_story_plan",
    "ready_with_chapter_arc_plan",
}

DECISION_FIELDS = {
    "acceptedRepair",
    "repairOwner",
    "repairAppliedAt",
    "resolveBlueprintEvidence",
    "resolveTimelineReadback",
    "renderFrameSampleEvidence",
    "postRepairAudit",
    "editorNotes",
}

POST_AUDIT_BY_AREA = {
    "reference_profile": ("reference/reference_batch_profile.json", "reference/reference_analysis.json"),
    "longform_structure": ("longform_delivery_audit.json", "reference_style_alignment_audit.json"),
    "route_arc": ("director_intent_contract_audit.json", "location_truth_contract_audit.json"),
    "route_bridges": (
        "transition_polish_blueprint/transition_polish_blueprint_report.json",
        "transition_execution_blueprint/transition_execution_blueprint_report.json",
        "transition_bridge_plan/transition_bridge_plan.json",
    ),
    "lived_in_texture": ("creator_cut_plan/creator_cut_plan.json", "route_texture_contract_audit.json"),
    "shot_pacing": ("rhythm_recut_blueprint/rhythm_recut_blueprint_report.json", "edit_rhythm_plan/edit_rhythm_plan.json"),
    "opening_title": ("opening_story_plan/opening_story_plan.json", "title_bridge_contract_audit.json"),
    "audio_caption_story": ("bgm_audio_contract_audit.json", "audience_caption_contract_audit.json", "story_style_contract_audit.json"),
    "ending_aftertaste": ("director_intent_contract_audit.json", "visual_establishing_plan/visual_establishing_plan.json"),
    "qa_chain": ("final_qa_suite_report.json", "director_polish_contract_audit.json", "package_integrity_audit.json"),
    "reference_style_gap": ("reference_style_alignment_audit.json", "director_intent_contract_audit.json"),
}


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


def resolve_artifact(package_dir: Path, raw: Any) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    if path.is_absolute():
        return path
    return package_dir / path


def report_status(path: Path | None) -> str | None:
    data = load_json(path)
    if isinstance(data, dict):
        return data.get("status")
    return None


def accepted_report(path: Path | None) -> bool:
    status = report_status(path)
    return status in ACCEPTED_STATUSES


def contains_readback_or_frame_evidence(value: Any, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("readback", "frame", "sample", "contactsheet", "contact_sheet", "screenshot")):
                if item not in (None, "", [], {}):
                    return True
            if contains_readback_or_frame_evidence(item, depth + 1):
                return True
    elif isinstance(value, list):
        return any(contains_readback_or_frame_evidence(item, depth + 1) for item in value)
    return False


def post_audit_candidates(package_dir: Path, row: dict[str, Any]) -> list[Path]:
    out: list[Path] = []
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    if decision.get("postRepairAudit"):
        path = resolve_artifact(package_dir, decision.get("postRepairAudit"))
        if path:
            out.append(path)
    for rel in POST_AUDIT_BY_AREA.get(str(row.get("area") or ""), ()):
        out.append(package_dir / rel)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in out:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def decision_complete(row: dict[str, Any]) -> bool:
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    if not DECISION_FIELDS.issubset(set(decision)):
        return False
    if decision.get("acceptedRepair") not in {True, "true", "yes", "approved", "accepted"}:
        return False
    required_strings = ("repairOwner", "repairAppliedAt", "resolveBlueprintEvidence", "postRepairAudit")
    has_readback_or_frame = bool(
        str(decision.get("resolveTimelineReadback") or "").strip()
        or str(decision.get("renderFrameSampleEvidence") or "").strip()
    )
    return all(str(decision.get(key) or "").strip() for key in required_strings) and has_readback_or_frame


def closure_row(package_dir: Path, skill_dir: Path, row: dict[str, Any]) -> dict[str, Any]:
    required_artifact = resolve_artifact(package_dir, row.get("requiredArtifact"))
    owner_script = skill_dir / "scripts" / str(row.get("ownerScript") or "")
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    audits = post_audit_candidates(package_dir, row)
    passing_audits = [path for path in audits if accepted_report(path)]
    evidence_audits = [path for path in passing_audits if contains_readback_or_frame_evidence(load_json(path))]
    artifact_exists = bool(required_artifact and required_artifact.exists())
    artifact_status = report_status(required_artifact)
    artifact_ready = artifact_exists and (artifact_status is None or artifact_status in ACCEPTED_STATUSES)
    owner_exists = owner_script.exists()
    decision_ok = decision_complete(row)
    has_readback_or_frame_sample = bool(
        str(decision.get("resolveTimelineReadback") or "").strip()
        or str(decision.get("renderFrameSampleEvidence") or "").strip()
        or evidence_audits
    )
    if artifact_ready and owner_exists and passing_audits and has_readback_or_frame_sample:
        status = "closed"
    elif artifact_ready and owner_exists and passing_audits:
        status = "needs_editor_evidence"
    else:
        status = "blocked"
    return {
        "rowIndex": row.get("rowIndex"),
        "priority": row.get("priority"),
        "area": row.get("area"),
        "ownerScript": row.get("ownerScript"),
        "ownerScriptExists": owner_exists,
        "requiredArtifact": str(required_artifact) if required_artifact else None,
        "requiredArtifactExists": artifact_exists,
        "requiredArtifactStatus": artifact_status,
        "decisionComplete": decision_ok,
        "hasReadbackOrFrameSample": has_readback_or_frame_sample,
        "passingPostRepairAudits": [str(path) for path in passing_audits],
        "readbackFrameEvidenceReports": [str(path) for path in evidence_audits],
        "status": status,
    }


def build_report(package_dir: Path, skill_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    skill_dir = skill_dir.expanduser().resolve()
    plan_path = package_dir / "reference_style_repair_plan" / "reference_style_repair_plan.json"
    plan = load_json(plan_path) or {}
    rows = plan.get("repairRows") if isinstance(plan.get("repairRows"), list) else []
    closure_rows = [closure_row(package_dir, skill_dir, row) for row in rows if isinstance(row, dict)]
    p0_rows = [row for row in closure_rows if row.get("priority") == "P0"]
    closed = [row for row in closure_rows if row.get("status") == "closed"]
    needs_evidence = [row for row in closure_rows if row.get("status") == "needs_editor_evidence"]
    blocked = [row for row in closure_rows if row.get("status") == "blocked"]
    if not rows and plan.get("status") == "ready_no_reference_style_repairs_needed":
        status = "passed"
    elif rows and not blocked and not [row for row in p0_rows if row.get("status") != "closed"]:
        status = "passed_with_evidence_warnings" if needs_evidence else "passed"
    else:
        status = "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "skillDir": str(skill_dir),
        "inputs": {
            "referenceStyleRepairPlan": str(plan_path),
            "referenceStyleRepairPlanExists": plan_path.exists(),
            "referenceStyleRepairPlanStatus": plan.get("status"),
        },
        "summary": {
            "repairRowCount": len(closure_rows),
            "p0RepairRowCount": len(p0_rows),
            "closedRowCount": len(closed),
            "p0ClosedRowCount": len([row for row in p0_rows if row.get("status") == "closed"]),
            "needsEditorEvidenceRowCount": len(needs_evidence),
            "blockedRowCount": len(blocked),
        },
        "closureRows": closure_rows,
        "blockers": [
            f"row {row.get('rowIndex')} {row.get('area')}: {row.get('status')}"
            for row in closure_rows
            if row.get("status") == "blocked" or (row.get("priority") == "P0" and row.get("status") != "closed")
        ],
        "warnings": [
            f"row {row.get('rowIndex')} {row.get('area')}: needs editor/readback/frame evidence"
            for row in needs_evidence
        ],
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Reference Repair Closure Audit",
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
        "## Closure Rows",
    ]
    for row in report.get("closureRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('area')} / {row.get('priority')}",
                f"- Status: `{row.get('status')}`",
                f"- Owner script exists: `{row.get('ownerScriptExists')}`",
                f"- Required artifact exists: `{row.get('requiredArtifactExists')}`",
                f"- Required artifact status: `{row.get('requiredArtifactStatus')}`",
                f"- Decision complete: `{row.get('decisionComplete')}`",
                f"- Readback/frame/audit evidence: `{row.get('hasReadbackOrFrameSample')}`",
                f"- Evidence reports: `{len(row.get('readbackFrameEvidenceReports') or [])}`",
            ]
        )
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit closure evidence for reference-style repair rows.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--skill-dir", default=str(skill_dir_from_script()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    report = build_report(package_dir, skill_dir)
    write_json(package_dir / "reference_repair_closure_audit.json", report)
    write_markdown(package_dir / "reference_repair_closure_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
