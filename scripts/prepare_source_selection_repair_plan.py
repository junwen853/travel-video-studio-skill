#!/usr/bin/env python3
"""Prepare blocking repair rows for weak raw-source selection coverage."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


CANDIDATE_TIERS = {"hero_candidate", "main_story_candidate", "texture_bridge_candidate"}
REPAIR_TIERS = {"repair_before_use", "reject_or_review", "reject_excluded"}
REQUIRED_CHAPTER_FUNCTIONS = {
    "route_movement_bridge": {
        "ownerScript": "prepare_transition_bridge_plan.py",
        "issueType": "missing_route_movement_bridge",
        "requiredAction": "Select local movement or transport footage for the chapter boundary before using stock, aerial fallback, or a flashy transition.",
    },
    "lived_in_texture": {
        "ownerScript": "prepare_chapter_arc_plan.py",
        "issueType": "missing_lived_in_texture",
        "requiredAction": "Select small real-life details so the chapter feels traveled rather than assembled from scenic shots only.",
    },
    "destination_payoff_or_title_candidate": {
        "ownerScript": "prepare_visual_establishing_plan.py",
        "issueType": "missing_destination_payoff",
        "requiredAction": "Find or create a strong place-identity/payoff shot for chapter title, climax, or aftertaste use.",
    },
}
DECISION_FIELDS = {
    "acceptedRepair": "",
    "ownerScriptExecuted": "",
    "replacementRowIndexes": [],
    "approvedFallback": "",
    "resolveBlueprintUpdate": "",
    "postRepairAudit": "",
    "readbackEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}
GENERIC_DECISION_TEXT = {
    "ok",
    "okay",
    "pass",
    "passed",
    "done",
    "none",
    "n/a",
    "na",
    "no issue",
    "no issues",
    "fixed",
    "reviewed",
    "complete",
    "completed",
    "无",
    "无问题",
    "没问题",
    "通过",
    "完成",
    "已完成",
    "已看",
}
REQUIRED_DECISION_TEXT_FIELDS = (
    "acceptedRepair",
    "ownerScriptExecuted",
    "resolveBlueprintUpdate",
    "postRepairAudit",
    "readbackEvidence",
    "approvedBy",
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


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean(value: Any, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def is_meaningful_text(value: Any, *, min_len: int = 12) -> bool:
    text = clean(value, 1000)
    if len(text) < min_len:
        return False
    normalized = re.sub(r"[\s.。,_-]+", " ", text).strip().lower()
    return normalized not in GENERIC_DECISION_TEXT


def parse_iso_datetime(value: Any) -> datetime | None:
    text = clean(value, 100)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def row_index(row: dict[str, Any]) -> int:
    return as_int(row.get("rowIndex"))


def source_name(row: dict[str, Any]) -> str:
    source = str(row.get("sourceName") or row.get("sourcePath") or row.get("fileId") or "")
    return Path(source).name if source else f"row_{row_index(row)}"


def row_ready(row: dict[str, Any]) -> bool:
    return row.get("selectionTier") in CANDIDATE_TIERS and row.get("status") == "ready_for_first_cut_selection"


def row_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in (
            "sourceName",
            "sourcePath",
            "place",
            "city",
            "selectionTier",
            "creatorFunction",
            "status",
        )
    ).lower()


def chapter_key_for(row: dict[str, Any]) -> str:
    place = str(row.get("place") or "unknown")
    date = str(row.get("date") or "unknown")
    return f"{date} | {place}"


def find_footage_select(
    package_dir: Path | None,
    project_dir: Path | None,
    explicit_path: Path | None,
) -> tuple[Path | None, dict[str, Any]]:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(explicit_path)
    if package_dir:
        candidates.extend(
            [
                package_dir / "footage_select_plan" / "footage_select_plan.json",
                package_dir / "footage_select_plan.json",
            ]
        )
    if project_dir:
        candidates.extend(
            [
                project_dir / "footage_select_plan" / "footage_select_plan.json",
                project_dir / "footage_select_plan.json",
            ]
        )
    for path in candidates:
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    return None, {}


def output_root(args: argparse.Namespace, package_dir: Path | None, project_dir: Path | None) -> Path:
    if args.output_dir:
        return Path(args.output_dir).expanduser().resolve()
    if package_dir:
        return package_dir / "source_selection_repair_plan"
    if project_dir:
        return project_dir / "source_selection_repair_plan"
    raise SystemExit("Provide --package-dir, --project-dir, or --output-dir.")


def existing_decisions(output_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_json(output_dir / "source_selection_repair_plan.json") or {}
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(data, dict):
        return out

    def keep_best(repair_id: str, decision: dict[str, Any]) -> None:
        current = out.get(repair_id)
        if current is None or len(decision_quality_issues({"decision": decision})) < len(decision_quality_issues({"decision": current})):
            out[repair_id] = dict(decision)

    archive = data.get("decisionArchive")
    if isinstance(archive, dict):
        for repair_id, decision in archive.items():
            if isinstance(decision, dict) and clean(repair_id, 120):
                keep_best(clean(repair_id, 120), decision)
    for row_key in ("repairRows", "closedRepairRows"):
        rows = data.get(row_key) if isinstance(data.get(row_key), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            repair_id = clean(row.get("repairId"), 120)
            decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
            if repair_id:
                keep_best(repair_id, decision)
    return out


def merge_decision(existing: dict[str, Any] | None) -> dict[str, Any]:
    decision = dict(DECISION_FIELDS)
    if isinstance(existing, dict):
        decision.update(existing)
    return decision


def decision_quality_issues(row: dict[str, Any]) -> list[str]:
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    issues: list[str] = []
    for key in REQUIRED_DECISION_TEXT_FIELDS:
        if not is_meaningful_text(decision.get(key)):
            issues.append(f"{key} is missing, too short, or generic")
    replacement_rows = decision.get("replacementRowIndexes")
    if not (isinstance(replacement_rows, list) and replacement_rows) and not is_meaningful_text(decision.get("approvedFallback")):
        issues.append("replacementRowIndexes or approvedFallback must explain what replaced or safely excluded the weak source")
    if not parse_iso_datetime(decision.get("approvedAt")):
        issues.append("approvedAt must be an ISO timestamp from the actual repair closure")
    return issues


def apply_previous_decisions(rows: list[dict[str, Any]], previous: dict[str, dict[str, Any]]) -> None:
    for row in rows:
        repair_id = clean(row.get("repairId"), 120)
        row["decision"] = merge_decision(previous.get(repair_id))
        row["decisionIssues"] = decision_quality_issues(row)


def row_closed(row: dict[str, Any]) -> bool:
    return not row.get("decisionIssues")


def normalized_chapters(footage_select: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in footage_select.get("selectionRows") or [] if isinstance(row, dict)]
    by_key: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_key.setdefault(chapter_key_for(row), []).append(row)
    chapter_rows = [row for row in footage_select.get("chapterRows") or [] if isinstance(row, dict)]
    if chapter_rows:
        out: list[dict[str, Any]] = []
        for chapter in chapter_rows:
            key = str(chapter.get("chapterKey") or "")
            chapter_selection_rows = by_key.get(key, [])
            out.append({"chapter": chapter, "selectionRows": chapter_selection_rows})
        return out
    return [
        {
            "chapter": {
                "chapterIndex": index,
                "chapterKey": key,
                "sourceVideoCount": len(chapter_rows_for_key),
            },
            "selectionRows": chapter_rows_for_key,
        }
        for index, (key, chapter_rows_for_key) in enumerate(sorted(by_key.items()), 1)
    ]


def make_repair_row(
    *,
    repair_id: str,
    severity: str,
    issue_type: str,
    scope: str,
    owner_script: str,
    problem: str,
    required_action: str,
    chapter_key: str | None = None,
    affected_rows: list[int] | None = None,
    candidate_rows: list[int] | None = None,
    evidence_required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "repairId": repair_id,
        "severity": severity,
        "issueType": issue_type,
        "scope": scope,
        "chapterKey": chapter_key,
        "ownerScript": owner_script,
        "problem": problem,
        "requiredAction": required_action,
        "allowedFallbacks": [
            "Use selected local footage first.",
            "Use verified stock/aerial only when local footage cannot honestly cover the gap.",
            "Use generated title/bridge media only after the missing source function is documented.",
        ],
        "evidenceRequired": evidence_required
        or [
            "updated source_selection_repair_plan.json",
            "updated resolve_timeline_blueprint.json or candidate blueprint",
            "matching post-repair audit report",
        ],
        "affectedRowIndexes": affected_rows or [],
        "candidateRowIndexes": candidate_rows or [],
        "decision": dict(DECISION_FIELDS),
    }


def chapter_coverage_row(index: int, chapter_key: str, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ready_rows = [row for row in rows if row_ready(row)]
    ready_indexes = [row_index(row) for row in ready_rows if row_index(row)]
    functions = Counter(str(row.get("creatorFunction") or "") for row in ready_rows)
    tiers = Counter(str(row.get("selectionTier") or "") for row in rows)
    repair_rows = [row for row in rows if row.get("selectionTier") in REPAIR_TIERS or row.get("status") != "ready_for_first_cut_selection"]
    repair_indexes = [row_index(row) for row in repair_rows if row_index(row)]
    repair_plan_rows: list[dict[str, Any]] = []

    if not ready_rows:
        repair_plan_rows.append(
            make_repair_row(
                repair_id=f"chapter_{index:03d}_no_ready_candidates",
                severity="blocker",
                issue_type="chapter_has_no_ready_candidate_source",
                scope="chapter",
                chapter_key=chapter_key,
                owner_script="prepare_footage_select_plan.py",
                problem="Chapter has no hero/main/texture source row ready for first-cut selection.",
                required_action="Re-score the source pool, exclude weak rows, and select at least one ready local source before assembly.",
                affected_rows=repair_indexes,
            )
        )

    for function_name, spec in REQUIRED_CHAPTER_FUNCTIONS.items():
        if functions.get(function_name, 0) > 0:
            continue
        repair_plan_rows.append(
            make_repair_row(
                repair_id=f"chapter_{index:03d}_{spec['issueType']}",
                severity="blocker",
                issue_type=spec["issueType"],
                scope="chapter",
                chapter_key=chapter_key,
                owner_script=spec["ownerScript"],
                problem=f"Chapter lacks a ready `{function_name}` source candidate.",
                required_action=str(spec["requiredAction"]),
                affected_rows=repair_indexes,
                candidate_rows=ready_indexes,
            )
        )

    candidate_count = len(ready_rows)
    if candidate_count < 2 and len(rows) >= 4:
        repair_plan_rows.append(
            make_repair_row(
                repair_id=f"chapter_{index:03d}_thin_candidate_pool",
                severity="blocker",
                issue_type="thin_chapter_candidate_pool",
                scope="chapter",
                chapter_key=chapter_key,
                owner_script="prepare_creator_cut_plan.py",
                problem="Chapter has too few selected local candidates to support a V14-level first draft.",
                required_action="Promote stronger hero/main/texture rows or shorten the chapter before transition/effect work begins.",
                affected_rows=repair_indexes,
                candidate_rows=ready_indexes,
            )
        )

    status = "blocked_source_selection_coverage_needs_repair" if repair_plan_rows else "ready_with_chapter_selection_coverage"
    coverage = {
        "chapterIndex": index,
        "chapterKey": chapter_key,
        "status": status,
        "sourceVideoCount": len(rows),
        "readyCandidateCount": candidate_count,
        "readyCandidateRowIndexes": ready_indexes,
        "repairOrRejectRowIndexes": repair_indexes,
        "heroCandidateCount": sum(1 for row in ready_rows if row.get("selectionTier") == "hero_candidate"),
        "mainStoryCandidateCount": sum(1 for row in ready_rows if row.get("selectionTier") == "main_story_candidate"),
        "textureBridgeCandidateCount": sum(1 for row in ready_rows if row.get("selectionTier") == "texture_bridge_candidate"),
        "functionCounts": dict(functions),
        "tierCounts": dict(tiers),
        "missingFunctions": [
            function_name for function_name in REQUIRED_CHAPTER_FUNCTIONS if functions.get(function_name, 0) == 0
        ],
        "decision": {
            "approvedChapterCoverage": "",
            "openingOrPayoffRows": [],
            "movementRows": [],
            "textureRows": [],
            "bridgeRows": [],
            "repairRowsClosed": [],
            "resolveImplementation": "",
            "readbackEvidence": "",
            "approvedBy": "",
            "approvedAt": "",
            "editorNotes": "",
        },
    }
    return coverage, repair_plan_rows


def build_plan(package_dir: Path | None, project_dir: Path | None, footage_select_path: Path | None, output_dir: Path) -> dict[str, Any]:
    previous = existing_decisions(output_dir)
    selected_path, footage_select = find_footage_select(package_dir, project_dir, footage_select_path)
    if not footage_select:
        missing_row = make_repair_row(
            repair_id="global_missing_footage_select_plan",
            severity="blocker",
            issue_type="missing_footage_select_plan",
            scope="global",
            owner_script="prepare_footage_select_plan.py",
            problem="No footage_select_plan.json was found.",
            required_action="Run prepare_footage_select_plan.py before building or auditing the first assembly.",
        )
        apply_previous_decisions([missing_row], previous)
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked_missing_footage_select_plan",
            "packageDir": str(package_dir) if package_dir else None,
            "projectDir": str(project_dir) if project_dir else None,
            "outputDir": str(output_dir),
            "inputs": {"footageSelectPlan": str(selected_path) if selected_path else None},
            "summary": {
                "blockingRepairRowCount": 1,
                "warningRepairRowCount": 0,
                "openRepairRowCount": 1,
                "closedRepairRowCount": 0,
                "decisionIssueCount": len(missing_row.get("decisionIssues") or []),
                "rowsWithDecisionIssues": 1 if missing_row.get("decisionIssues") else 0,
                "chapterRowCount": 0,
            },
            "chapterCoverageRows": [],
            "decisionArchive": {missing_row["repairId"]: missing_row["decision"]},
            "repairRows": [missing_row],
            "safety": safety(),
        }

    selection_rows = [row for row in footage_select.get("selectionRows") or [] if isinstance(row, dict)]
    chapters = normalized_chapters(footage_select)
    repair_rows: list[dict[str, Any]] = []
    chapter_coverage_rows: list[dict[str, Any]] = []
    for index, chapter_bundle in enumerate(chapters, 1):
        chapter = chapter_bundle["chapter"]
        key = str(chapter.get("chapterKey") or f"chapter_{index:03d}")
        coverage, repairs = chapter_coverage_row(index, key, chapter_bundle["selectionRows"])
        chapter_coverage_rows.append(coverage)
        repair_rows.extend(repairs)

    ready_rows = [row for row in selection_rows if row_ready(row)]
    hero_rows = [row for row in ready_rows if row.get("selectionTier") == "hero_candidate"]
    movement_rows = [row for row in ready_rows if row.get("creatorFunction") == "route_movement_bridge"]
    texture_rows = [row for row in ready_rows if row.get("creatorFunction") == "lived_in_texture"]
    payoff_rows = [row for row in ready_rows if row.get("creatorFunction") == "destination_payoff_or_title_candidate"]
    repair_or_reject_rows = [
        row for row in selection_rows if row.get("selectionTier") in REPAIR_TIERS or row.get("status") != "ready_for_first_cut_selection"
    ]

    required_hero_count = 2 if len(selection_rows) >= 10 and len(chapters) >= 2 else 1
    if len(hero_rows) < required_hero_count:
        repair_rows.append(
            make_repair_row(
                repair_id="global_not_enough_hero_candidates",
                severity="blocker",
                issue_type="not_enough_opening_ending_hero_candidates",
                scope="global",
                owner_script="prepare_visual_establishing_plan.py",
                problem=f"Only {len(hero_rows)} hero candidates are ready; {required_hero_count} are required for opening/ending confidence.",
                required_action="Promote or source strong place-identity shots before title, chapter payoff, or ending work.",
                candidate_rows=[row_index(row) for row in hero_rows if row_index(row)],
            )
        )
    if len(movement_rows) < max(1, len(chapters) - 1):
        repair_rows.append(
            make_repair_row(
                repair_id="global_not_enough_route_movement_bridges",
                severity="blocker",
                issue_type="not_enough_route_movement_bridges",
                scope="global",
                owner_script="prepare_transition_bridge_plan.py",
                problem="The source pool does not contain enough ready route movement bridges for chapter transitions.",
                required_action="Select local transport/walking/window/signage movement first; only then document stock/aerial fallback.",
                candidate_rows=[row_index(row) for row in movement_rows if row_index(row)],
            )
        )
    repair_ratio = len(repair_or_reject_rows) / len(selection_rows) if selection_rows else 1.0
    if selection_rows and repair_ratio > 0.55 and len(ready_rows) < max(3, len(chapters) * 2):
        repair_rows.append(
            make_repair_row(
                repair_id="global_repair_reject_pool_dominates",
                severity="blocker",
                issue_type="repair_or_reject_pool_dominates",
                scope="global",
                owner_script="prepare_footage_select_plan.py",
                problem="Repair/reject rows dominate the source pool, so the first draft would hide weak source choice with edits.",
                required_action="Re-run source exclusion, orientation repair, and footage selection before creator-cut planning.",
                affected_rows=[row_index(row) for row in repair_or_reject_rows if row_index(row)],
                candidate_rows=[row_index(row) for row in ready_rows if row_index(row)],
            )
        )
    orientation_repair_rows = [
        row
        for row in repair_or_reject_rows
        if "orientation" in row_text(row) or row.get("selectionTier") == "repair_before_use"
    ]
    if orientation_repair_rows:
        repair_rows.append(
            make_repair_row(
                repair_id="global_orientation_repair_rows_require_closure",
                severity="warning",
                issue_type="orientation_repair_rows_require_closure",
                scope="global",
                owner_script="prepare_orientation_repair_package.py",
                problem="Portrait, square, or unknown-orientation rows exist and must not enter a 16:9 master raw.",
                required_action="Repair, design as phone inserts, or keep excluded before final source usage approval.",
                affected_rows=[row_index(row) for row in orientation_repair_rows if row_index(row)],
                evidence_required=[
                    "orientation_repair_package manifest",
                    "final_source_usage_contract_audit.json",
                    "Resolve readback showing no raw portrait/square/unknown full-frame clips",
                ],
            )
        )

    apply_previous_decisions(repair_rows, previous)
    blocking = [row for row in repair_rows if row.get("severity") == "blocker"]
    warnings = [row for row in repair_rows if row.get("severity") != "blocker"]
    open_warnings = [row for row in warnings if not row_closed(row)]
    closed_warnings = [row for row in warnings if row_closed(row)]
    open_repair_rows = blocking + open_warnings
    closed_repair_rows = closed_warnings
    required_scripts = sorted({str(row.get("ownerScript")) for row in open_repair_rows if row.get("ownerScript")})
    status = "ready_no_source_selection_repairs_needed" if not open_repair_rows else "blocked_source_selection_coverage_needs_repair"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir) if package_dir else None,
        "projectDir": str(project_dir) if project_dir else None,
        "outputDir": str(output_dir),
        "inputs": {
            "footageSelectPlan": str(selected_path) if selected_path else None,
            "footageSelectStatus": footage_select.get("status"),
        },
        "summary": {
            "sourceVideoCount": len(selection_rows),
            "chapterRowCount": len(chapter_coverage_rows),
            "readyChapterCount": sum(1 for row in chapter_coverage_rows if row.get("status") == "ready_with_chapter_selection_coverage"),
            "chaptersBlocked": sum(1 for row in chapter_coverage_rows if row.get("status") != "ready_with_chapter_selection_coverage"),
            "candidateVideoCount": len(ready_rows),
            "heroCandidateCount": len(hero_rows),
            "movementBridgeCandidateCount": len(movement_rows),
            "livedInTextureCandidateCount": len(texture_rows),
            "destinationPayoffCandidateCount": len(payoff_rows),
            "repairOrRejectRowCount": len(repair_or_reject_rows),
            "orientationRepairRowCount": len(orientation_repair_rows),
            "repairOrRejectRatio": round(repair_ratio, 4),
            "blockingRepairRowCount": len(blocking),
            "warningRepairRowCount": len(open_warnings),
            "totalWarningRepairRowCount": len(warnings),
            "closedWarningRepairRowCount": len(closed_warnings),
            "openRepairRowCount": len(open_repair_rows),
            "closedRepairRowCount": len(closed_repair_rows),
            "totalRepairRowCount": len(repair_rows),
            "decisionArchiveCount": len(repair_rows),
            "decisionIssueCount": sum(len(row.get("decisionIssues") or []) for row in repair_rows),
            "rowsWithDecisionIssues": len([row for row in repair_rows if row.get("decisionIssues")]),
            "rowsWithClosureDecision": len([row for row in repair_rows if row_closed(row)]),
            "requiredOwnerScripts": required_scripts,
        },
        "policy": {
            "blocksFilenameOrderAssembly": True,
            "blocksWeakChapterCoverageBeforeEffects": True,
            "localFootageBeforeStockOrAerialFallback": True,
            "orientationRepairClosedBeforeFinalUse": True,
            "repairRowsMustCloseBeforeResolveApply": True,
            "doesNotModifySourceFootage": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "globalCoverage": {
            "heroCandidateRows": [row_index(row) for row in hero_rows if row_index(row)],
            "movementBridgeRows": [row_index(row) for row in movement_rows if row_index(row)],
            "livedInTextureRows": [row_index(row) for row in texture_rows if row_index(row)],
            "destinationPayoffRows": [row_index(row) for row in payoff_rows if row_index(row)],
            "topReadySourceNames": [source_name(row) for row in sorted(ready_rows, key=lambda item: as_int(item.get("selectionScore")), reverse=True)[:20]],
        },
        "chapterCoverageRows": chapter_coverage_rows,
        "decisionArchive": {str(row.get("repairId")): row.get("decision") for row in repair_rows if row.get("repairId")},
        "closedRepairRows": closed_repair_rows,
        "repairRows": open_repair_rows,
        "safety": safety(),
    }


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Source Selection Repair Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan.get('packageDir')}`",
        f"Project: `{plan.get('projectDir')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blocking Repair Rows",
    ]
    blockers = [row for row in plan.get("repairRows") or [] if row.get("severity") == "blocker"]
    if not blockers:
        lines.append("- None.")
    for row in blockers:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Scope: `{row.get('scope')}`",
                f"- Chapter: `{row.get('chapterKey')}`",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Problem: {row.get('problem')}",
                f"- Required action: {row.get('requiredAction')}",
                f"- Candidate rows: `{row.get('candidateRowIndexes')}`",
                f"- Affected rows: `{row.get('affectedRowIndexes')}`",
                f"- Decision issues: `{', '.join(row.get('decisionIssues') or []) or 'none'}`",
            ]
        )
    warnings = [row for row in plan.get("repairRows") or [] if row.get("severity") != "blocker"]
    lines.extend(["", "## Warning Repair Rows"])
    if not warnings:
        lines.append("- None.")
    for row in warnings:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Problem: {row.get('problem')}",
                f"- Required action: {row.get('requiredAction')}",
                f"- Decision issues: `{', '.join(row.get('decisionIssues') or []) or 'none'}`",
            ]
        )
    closed_rows = plan.get("closedRepairRows") or []
    lines.extend(["", "## Closed Repair Rows"])
    if not closed_rows:
        lines.append("- None.")
    for row in closed_rows:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Closure: `{json.dumps(row.get('decision'), ensure_ascii=False)[:1200]}`",
            ]
        )
    lines.extend(["", "## Chapter Coverage"])
    for row in plan.get("chapterCoverageRows") or []:
        lines.extend(
            [
                "",
                f"### {row.get('chapterKey')}",
                f"- Status: `{row.get('status')}`",
                f"- Source videos: `{row.get('sourceVideoCount')}`",
                f"- Ready candidates: `{row.get('readyCandidateCount')}`",
                f"- Missing functions: `{', '.join(row.get('missingFunctions') or []) or 'none'}`",
                f"- Ready rows: `{row.get('readyCandidateRowIndexes')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Contract",
            "- Do not trust a first assembly when blocking repair rows exist.",
            "- Close local movement, lived-in texture, and destination payoff gaps before stock/aerial fallback.",
            "- Close orientation repair rows before final source usage approval.",
            "- Rerun source selection repair, unattended first draft, final source usage, final QA, Skill maturity, and V14 baseline audits after repair.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare source-selection repair rows for weak chapter coverage.")
    parser.add_argument("--package-dir")
    parser.add_argument("--project-dir")
    parser.add_argument("--footage-select-plan")
    parser.add_argument("--output-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve() if args.package_dir else None
    project_dir = Path(args.project_dir).expanduser().resolve() if args.project_dir else None
    footage_select_path = Path(args.footage_select_plan).expanduser().resolve() if args.footage_select_plan else None
    out_dir = output_root(args, package_dir, project_dir)
    plan = build_plan(package_dir, project_dir, footage_select_path, out_dir)
    write_json(out_dir / "source_selection_repair_plan.json", plan)
    write_markdown(out_dir / "source_selection_repair_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "outputDir": str(out_dir), "summary": plan["summary"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if str(plan.get("status") or "").startswith("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
