#!/usr/bin/env python3
"""Audit whether the final timeline has film-level shot-function variety."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


MOVEMENT_TERMS = ("movement", "route", "transport", "station", "train", "metro", "walk", "arrival", "bridge", "motion")
TEXTURE_TERMS = ("texture", "lived", "street", "food", "hotel", "market", "shop", "detail", "daily", "interior")
PAYOFF_TERMS = ("payoff", "landmark", "destination", "scenic", "aerial", "skyline", "hero", "view", "coast", "temple")
AFTERTASTE_TERMS = ("aftertaste", "ending", "callback", "final", "sunset", "depart", "quiet")


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


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def inputs_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("inputs"), dict):
        return data["inputs"]
    return {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def count_term_hits(counts: Any, terms: tuple[str, ...]) -> int:
    if not isinstance(counts, dict):
        return 0
    total = 0
    for key, value in counts.items():
        key_text = str(key or "").lower()
        if any(term in key_text for term in terms):
            total += as_int(value)
    return total


def has_group(groups: Any, terms: tuple[str, ...]) -> bool:
    if isinstance(groups, dict):
        return count_term_hits(groups, terms) > 0
    if not isinstance(groups, list):
        return False
    return any(any(term in str(item or "").lower() for term in terms) for item in groups)


def report_path(package_dir: Path, name: str) -> Path:
    return package_dir / name


def check_row(name: str, passed: bool, evidence: dict[str, Any], blockers: list[str], message: str) -> dict[str, Any]:
    if not passed:
        blockers.append(message)
    return {"name": name, "status": "passed" if passed else "blocked", "evidence": evidence, "message": message}


def build_report(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    rhythm = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
    creator = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    creator_application = load_json(report_path(package_dir, "creator_cut_application_contract_audit.json")) or {}
    final_source = load_json(report_path(package_dir, "final_source_usage_contract_audit.json")) or {}
    reference_scene = load_json(report_path(package_dir, "reference_scene_grammar_contract_audit.json")) or {}
    transition_cadence = load_json(report_path(package_dir, "transition_cadence_contract_audit.json")) or {}
    final_lineage = load_json(report_path(package_dir, "final_blueprint_lineage_contract_audit.json")) or {}

    rhythm_summary = summary_of(rhythm)
    creator_summary = summary_of(creator)
    creator_app_summary = summary_of(creator_application)
    final_source_summary = summary_of(final_source)
    reference_summary = summary_of(reference_scene)
    transition_summary = summary_of(transition_cadence)
    lineage_summary = summary_of(final_lineage)
    creator_inputs = inputs_of(creator_application)
    source_inputs = inputs_of(final_source)

    visual_count = as_int(creator_app_summary.get("visualClipCount"))
    raw_count = as_int(final_source_summary.get("rawSourceClipCount"))
    groups = creator_app_summary.get("globalFunctionGroups") or []
    creator_function_counts = creator_summary.get("functionCounts")
    rhythm_category_counts = rhythm_summary.get("categoryCounts")
    ending_functions = reference_summary.get("endingFunctions") or []

    movement_ready = (
        has_group(groups, MOVEMENT_TERMS)
        or count_term_hits(creator_function_counts, MOVEMENT_TERMS) > 0
        or count_term_hits(rhythm_category_counts, MOVEMENT_TERMS) > 0
    )
    texture_ready = (
        has_group(groups, TEXTURE_TERMS)
        or count_term_hits(creator_function_counts, TEXTURE_TERMS) > 0
        or count_term_hits(rhythm_category_counts, TEXTURE_TERMS) > 0
    )
    payoff_ready = (
        has_group(groups, PAYOFF_TERMS)
        or count_term_hits(creator_function_counts, PAYOFF_TERMS) > 0
        or count_term_hits(rhythm_category_counts, PAYOFF_TERMS) > 0
        or "payoff" in (reference_summary.get("openingFunctions") or [])
    )
    aftertaste_ready = (
        bool(reference_summary.get("endingAftertasteFound"))
        or has_group(groups, AFTERTASTE_TERMS)
        or any(any(term in str(item or "").lower() for term in AFTERTASTE_TERMS) for item in ending_functions)
    )

    blockers: list[str] = []
    checks: list[dict[str, Any]] = []
    checks.append(
        check_row(
            "Upstream rhythm, source, creator, transition, lineage, and scene grammar reports exist",
            all(
                [
                    (package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json").exists(),
                    (package_dir / "creator_cut_plan" / "creator_cut_plan.json").exists(),
                    report_path(package_dir, "creator_cut_application_contract_audit.json").exists(),
                    report_path(package_dir, "final_source_usage_contract_audit.json").exists(),
                    report_path(package_dir, "reference_scene_grammar_contract_audit.json").exists(),
                    report_path(package_dir, "transition_cadence_contract_audit.json").exists(),
                    report_path(package_dir, "final_blueprint_lineage_contract_audit.json").exists(),
                ]
            ),
            {
                "editRhythmPlanExists": (package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json").exists(),
                "creatorCutPlanExists": (package_dir / "creator_cut_plan" / "creator_cut_plan.json").exists(),
                "creatorApplicationAuditExists": report_path(package_dir, "creator_cut_application_contract_audit.json").exists(),
                "finalSourceUsageAuditExists": report_path(package_dir, "final_source_usage_contract_audit.json").exists(),
                "referenceSceneGrammarAuditExists": report_path(package_dir, "reference_scene_grammar_contract_audit.json").exists(),
                "transitionCadenceAuditExists": report_path(package_dir, "transition_cadence_contract_audit.json").exists(),
                "finalBlueprintLineageAuditExists": report_path(package_dir, "final_blueprint_lineage_contract_audit.json").exists(),
            },
            blockers,
            "missing one or more upstream reports required for timeline variety",
        )
    )
    checks.append(
        check_row(
            "Final candidate uses selected raw footage instead of unmatched, repair, reject, or utility-dominant sources",
            final_source.get("status") == "passed"
            and source_inputs.get("blueprintExists") is True
            and source_inputs.get("blueprintInsidePackage") is True
            and raw_count >= 1
            and as_int(final_source_summary.get("matchedRawSourceClipCount")) == raw_count
            and as_int(final_source_summary.get("unmatchedRawSourceClipCount")) == 0
            and as_int(final_source_summary.get("selectedCandidateClipCount")) >= max(1, int(raw_count * 0.4))
            and as_int(final_source_summary.get("rejectOrRepairActiveClipCount")) == 0
            and as_int(final_source_summary.get("chaptersBlocked")) == 0
            and as_int(final_source_summary.get("sameSourceRunMax")) <= 3
            and as_float(final_source_summary.get("utilityDurationRatio")) <= 0.25
            and not final_source.get("blockers"),
            {
                "status": final_source.get("status"),
                "blueprintKind": source_inputs.get("blueprintKind"),
                "summary": final_source_summary,
            },
            blockers,
            "final source usage still looks like weak source selection or repeated raw footage",
        )
    )
    checks.append(
        check_row(
            "Creator-cut application proves the final clips vary by editorial function",
            creator_application.get("status") == "passed"
            and creator_inputs.get("blueprintExists") is True
            and creator_inputs.get("blueprintInsidePackage") is True
            and visual_count >= 3
            and as_int(creator_app_summary.get("matchedCreatorRowCount")) == visual_count
            and as_int(creator_app_summary.get("blockedClipCount")) == 0
            and as_int(creator_app_summary.get("chaptersBlocked")) == 0
            and as_int(creator_app_summary.get("rejectActiveClipCount")) == 0
            and as_int(creator_app_summary.get("weakActiveClipCount")) == 0
            and as_int(creator_app_summary.get("globalFunctionGroupCount")) >= 4
            and as_int(creator_app_summary.get("sameFunctionRunMax")) <= 4
            and as_int(creator_app_summary.get("sameSourceRunMax")) <= 3
            and not creator_application.get("blockers"),
            {
                "status": creator_application.get("status"),
                "blueprintKind": creator_inputs.get("blueprintKind"),
                "summary": creator_app_summary,
            },
            blockers,
            "creator-cut application lacks enough function variety or still contains weak/repeated clips",
        )
    )
    checks.append(
        check_row(
            "Whole film includes movement, lived-in texture, destination payoff, and ending aftertaste",
            movement_ready and texture_ready and payoff_ready and aftertaste_ready,
            {
                "movementReady": movement_ready,
                "textureReady": texture_ready,
                "payoffReady": payoff_ready,
                "aftertasteReady": aftertaste_ready,
                "globalFunctionGroups": groups,
                "creatorFunctionCounts": creator_function_counts,
                "rhythmCategoryCounts": rhythm_category_counts,
                "endingFunctions": ending_functions,
            },
            blockers,
            "timeline function coverage is incomplete: need movement, texture, payoff, and aftertaste",
        )
    )
    checks.append(
        check_row(
            "Edit rhythm and chapter windows are decision-complete before Resolve apply",
            rhythm.get("status") == "ready_with_edit_rhythm_plan"
            and as_int(rhythm_summary.get("primaryVisualShotCount")) >= 3
            and as_int(rhythm_summary.get("rowsWithDecisionFields")) == as_int(rhythm_summary.get("primaryVisualShotCount"))
            and as_int(rhythm_summary.get("chaptersNeedingVarietyOrRetime")) == 0
            and bool(rhythm_summary.get("referenceReady")),
            {"status": rhythm.get("status"), "summary": rhythm_summary},
            blockers,
            "edit rhythm plan still lacks decision-complete shot rows, reference readiness, or chapter variety",
        )
    )
    checks.append(
        check_row(
            "Transition cadence and final blueprint lineage cannot be used to hide weak shot choice",
            transition_cadence.get("status") == "passed"
            and final_lineage.get("status") == "passed"
            and as_int(transition_summary.get("blockedCheckCount")) == 0
            and as_int(transition_summary.get("craftedTransitionCount")) >= as_int(transition_summary.get("minimumCraftedTransitionCount"))
            and as_int(lineage_summary.get("blockedReadyStageCount")) == 0,
            {
                "transitionCadenceStatus": transition_cadence.get("status"),
                "transitionCadenceSummary": transition_summary,
                "finalBlueprintLineageStatus": final_lineage.get("status"),
                "finalBlueprintLineageSummary": lineage_summary,
            },
            blockers,
            "transition cadence or blueprint lineage is not clean enough to trust the final candidate",
        )
    )
    checks.append(
        check_row(
            "Reference scene grammar proves opening, chapters, and ending carry the same variety contract",
            reference_scene.get("status") == "passed"
            and as_int(reference_summary.get("openingFunctionCount")) >= 2
            and as_int(reference_summary.get("chapterCount")) >= 1
            and as_int(reference_summary.get("chaptersBlocked")) == 0
            and as_int(reference_summary.get("endingClipCount")) >= 1
            and as_int(reference_summary.get("weakPairFitCount")) == 0
            and not reference_scene.get("blockers"),
            {"status": reference_scene.get("status"), "summary": reference_summary},
            blockers,
            "reference scene grammar has not proved opening/chapter/ending variety",
        )
    )

    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "summary": {
            "visualClipCount": visual_count,
            "rawSourceClipCount": raw_count,
            "globalFunctionGroupCount": as_int(creator_app_summary.get("globalFunctionGroupCount")),
            "sameSourceRunMax": max(as_int(creator_app_summary.get("sameSourceRunMax")), as_int(final_source_summary.get("sameSourceRunMax"))),
            "sameFunctionRunMax": as_int(creator_app_summary.get("sameFunctionRunMax")),
            "movementReady": movement_ready,
            "textureReady": texture_ready,
            "payoffReady": payoff_ready,
            "aftertasteReady": aftertaste_ready,
            "chaptersNeedingVarietyOrRetime": rhythm_summary.get("chaptersNeedingVarietyOrRetime"),
            "referenceSceneChaptersBlocked": reference_summary.get("chaptersBlocked"),
            "transitionCadenceStatus": transition_cadence.get("status"),
            "finalBlueprintLineageStatus": final_lineage.get("status"),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": sum(1 for row in checks if row["status"] == "blocked"),
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": [],
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Timeline Variety Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Checks",
    ]
    for row in report.get("checks") or []:
        lines.extend(["", f"### {row.get('name')}", f"- Status: `{row.get('status')}`", f"- Message: {row.get('message')}"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final timeline shot-function variety across the film.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir)
    write_json(package_dir / "timeline_variety_contract_audit.json", report)
    write_markdown(package_dir / "timeline_variety_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
