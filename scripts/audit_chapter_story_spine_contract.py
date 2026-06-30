#!/usr/bin/env python3
"""Audit whether chapter-level story spine plans actually survive into the cut."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_BEATS = ("context", "movement", "texture", "payoff", "aftertaste")


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


def normalize_chapter(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return "unassigned"
    text = str(value).strip()
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except ValueError:
        pass
    return text


def rows_by_chapter(rows: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, dict):
            out[normalize_chapter(row.get("chapterIndex"))] = row
    return out


def beat_evidence(row: dict[str, Any], beat_id: str) -> int:
    beats = row.get("detectedBeats") if isinstance(row.get("detectedBeats"), dict) else {}
    beat = beats.get(beat_id) if isinstance(beats.get(beat_id), dict) else {}
    return as_int(beat.get("evidenceCount"))


def category_ready(row: dict[str, Any], terms: tuple[str, ...]) -> bool:
    categories = row.get("categoryCoverage") if isinstance(row.get("categoryCoverage"), dict) else {}
    for key, value in categories.items():
        if value and any(term in str(key or "").lower() for term in terms):
            return True
    return False


def has_creator_function(row: dict[str, Any], function_name: str) -> bool:
    functions = row.get("creatorFunctions") if isinstance(row.get("creatorFunctions"), list) else []
    return function_name in {str(item) for item in functions}


def check_row(name: str, passed: bool, evidence: dict[str, Any], blockers: list[str], message: str) -> dict[str, Any]:
    if not passed:
        blockers.append(message)
    return {
        "name": name,
        "status": "passed" if passed else "blocked",
        "message": message,
        "evidence": evidence,
    }


def chapter_spine_rows(chapter_arc: dict[str, Any], rhythm: dict[str, Any], creator: dict[str, Any]) -> list[dict[str, Any]]:
    chapter_rows = chapter_arc.get("chapterRows") if isinstance(chapter_arc.get("chapterRows"), list) else []
    rhythm_rows = rows_by_chapter(rhythm.get("chapterRows"))
    creator_rows = rows_by_chapter(creator.get("chapterRows"))
    out: list[dict[str, Any]] = []
    for row in chapter_rows:
        if not isinstance(row, dict):
            continue
        key = normalize_chapter(row.get("chapterIndex"))
        rhythm_row = rhythm_rows.get(key) or {}
        creator_row = creator_rows.get(key) or {}
        missing_beats = [beat_id for beat_id in REQUIRED_BEATS if beat_evidence(row, beat_id) <= 0]
        rhythm_ready = (
            rhythm_row.get("status") == "has_chapter_rhythm_plan"
            and as_int(rhythm_row.get("coveredCategoryCount")) >= 3
            and category_ready(rhythm_row, ("transport", "route", "motion", "movement"))
            and (
                category_ready(rhythm_row, ("street", "texture", "lived", "detail"))
                or has_creator_function(creator_row, "lived_in_detail")
            )
            and (
                category_ready(rhythm_row, ("payoff", "landmark", "scenic"))
                or has_creator_function(creator_row, "destination_payoff")
            )
        )
        creator_ready = (
            creator_row.get("status") == "has_creator_chapter_shape"
            and not creator_row.get("missingCreatorFunctions")
            and has_creator_function(creator_row, "route_movement")
            and has_creator_function(creator_row, "lived_in_detail")
            and has_creator_function(creator_row, "destination_payoff")
            and as_int(creator_row.get("rejectOrUtilityCount")) <= max(1, int(as_int(creator_row.get("shotCount")) * 0.25))
        )
        aftertaste_ready = beat_evidence(row, "aftertaste") > 0 or has_creator_function(creator_row, "ending_aftertaste")
        passed = not missing_beats and rhythm_ready and creator_ready and aftertaste_ready
        out.append(
            {
                "chapterIndex": key,
                "chapterTitle": row.get("chapterTitle"),
                "status": "passed" if passed else "blocked",
                "missingBeatIds": missing_beats,
                "beatEvidence": {beat_id: beat_evidence(row, beat_id) for beat_id in REQUIRED_BEATS},
                "rhythmReady": rhythm_ready,
                "creatorReady": creator_ready,
                "aftertasteReady": aftertaste_ready,
                "rhythmStatus": rhythm_row.get("status"),
                "rhythmCoveredCategoryCount": rhythm_row.get("coveredCategoryCount"),
                "creatorStatus": creator_row.get("status"),
                "creatorFunctions": creator_row.get("creatorFunctions") or [],
                "rejectOrUtilityCount": creator_row.get("rejectOrUtilityCount"),
                "ownerScriptsForMissingBeats": row.get("ownerScriptsForMissingBeats") or [],
            }
        )
    return out


def build_report(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    chapter_arc = load_json(package_dir / "chapter_arc_plan" / "chapter_arc_plan.json") or {}
    rhythm = load_json(package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json") or {}
    creator = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    creator_application = load_json(package_dir / "creator_cut_application_contract_audit.json") or {}
    final_source = load_json(package_dir / "final_source_usage_contract_audit.json") or {}
    reference_scene = load_json(package_dir / "reference_scene_grammar_contract_audit.json") or {}
    timeline_variety = load_json(package_dir / "timeline_variety_contract_audit.json") or {}
    transition_scene_arc = load_json(package_dir / "transition_scene_arc_contract_audit.json") or {}
    reference_transition = load_json(package_dir / "reference_transition_profile_contract_audit.json") or {}

    chapter_summary = summary_of(chapter_arc)
    rhythm_summary = summary_of(rhythm)
    creator_summary = summary_of(creator)
    creator_app_summary = summary_of(creator_application)
    final_source_summary = summary_of(final_source)
    reference_summary = summary_of(reference_scene)
    variety_summary = summary_of(timeline_variety)
    transition_scene_summary = summary_of(transition_scene_arc)
    reference_transition_summary = summary_of(reference_transition)
    creator_inputs = inputs_of(creator_application)
    final_source_inputs = inputs_of(final_source)
    spine_rows = chapter_spine_rows(chapter_arc, rhythm, creator)
    blocked_spines = [row for row in spine_rows if row.get("status") == "blocked"]

    blockers: list[str] = []
    checks: list[dict[str, Any]] = []
    chapter_count = as_int(chapter_summary.get("chapterRowCount"))
    checks.append(
        check_row(
            "Chapter arc plan has decision-complete context, movement, texture, payoff, and aftertaste rows",
            chapter_arc.get("status") == "ready_with_chapter_arc_plan"
            and chapter_count >= 1
            and as_int(chapter_summary.get("rowsWithDecisionFields")) == chapter_count
            and as_int(chapter_summary.get("chaptersMissingRequiredBeatCount")) == 0
            and len(spine_rows) == chapter_count,
            {"status": chapter_arc.get("status"), "summary": chapter_summary},
            blockers,
            "chapter arc plan is missing, incomplete, or still has missing story beats",
        )
    )
    checks.append(
        check_row(
            "Every chapter spine survives into rhythm and creator-cut chapter rows",
            bool(spine_rows) and not blocked_spines,
            {"chapterRows": spine_rows[:80], "blockedChapterCount": len(blocked_spines)},
            blockers,
            "one or more chapters do not carry the required story spine through rhythm and creator-cut planning",
        )
    )
    checks.append(
        check_row(
            "Edit rhythm and creator-cut plans are ready and chapter-complete",
            rhythm.get("status") == "ready_with_edit_rhythm_plan"
            and creator.get("status") == "ready_with_creator_cut_plan"
            and as_int(rhythm_summary.get("chapterRowCount")) >= chapter_count
            and as_int(creator_summary.get("chapterRowCount")) >= chapter_count
            and as_int(rhythm_summary.get("chaptersNeedingVarietyOrRetime")) == 0
            and as_int(creator_summary.get("chaptersNeedingCreatorCoverage")) == 0,
            {
                "rhythmStatus": rhythm.get("status"),
                "rhythmSummary": rhythm_summary,
                "creatorStatus": creator.get("status"),
                "creatorSummary": creator_summary,
            },
            blockers,
            "rhythm or creator-cut chapter coverage is not ready",
        )
    )
    checks.append(
        check_row(
            "Final candidate uses selected raw footage and applies creator functions",
            final_source.get("status") == "passed"
            and creator_application.get("status") == "passed"
            and final_source_inputs.get("blueprintExists") is True
            and final_source_inputs.get("blueprintInsidePackage") is True
            and creator_inputs.get("blueprintExists") is True
            and creator_inputs.get("blueprintInsidePackage") is True
            and as_int(final_source_summary.get("rawSourceClipCount")) >= 1
            and as_int(final_source_summary.get("rejectOrRepairActiveClipCount")) == 0
            and as_float(final_source_summary.get("utilityDurationRatio")) <= 0.25
            and as_int(creator_app_summary.get("chaptersBlocked")) == 0
            and as_int(creator_app_summary.get("rejectActiveClipCount")) == 0
            and as_int(creator_app_summary.get("weakActiveClipCount")) == 0
            and as_int(creator_app_summary.get("globalFunctionGroupCount")) >= 4,
            {
                "finalSourceStatus": final_source.get("status"),
                "finalSourceSummary": final_source_summary,
                "creatorApplicationStatus": creator_application.get("status"),
                "creatorApplicationSummary": creator_app_summary,
            },
            blockers,
            "final candidate still looks like weak, utility-dominant, or unapplied source selection",
        )
    )
    checks.append(
        check_row(
            "Reference scene grammar and timeline variety prove the story spine at film level",
            reference_scene.get("status") == "passed"
            and timeline_variety.get("status") == "passed"
            and as_int(reference_summary.get("chaptersBlocked")) == 0
            and as_int(reference_summary.get("blockerCount")) == 0
            and variety_summary.get("movementReady") is True
            and variety_summary.get("textureReady") is True
            and variety_summary.get("payoffReady") is True
            and variety_summary.get("aftertasteReady") is True
            and as_int(variety_summary.get("blockedCheckCount")) == 0,
            {
                "referenceSceneStatus": reference_scene.get("status"),
                "referenceSceneSummary": reference_summary,
                "timelineVarietyStatus": timeline_variety.get("status"),
                "timelineVarietySummary": variety_summary,
            },
            blockers,
            "film-level scene grammar or variety does not prove movement, texture, payoff, and aftertaste",
        )
    )
    checks.append(
        check_row(
            "Transitions support the chapter spine instead of masking missing route texture",
            transition_scene_arc.get("status") == "passed"
            and reference_transition.get("status") == "passed"
            and as_int(transition_scene_summary.get("blockedCheckCount")) == 0
            and transition_scene_summary.get("movementReady") is True
            and transition_scene_summary.get("textureReady") is True
            and transition_scene_summary.get("payoffReady") is True
            and transition_scene_summary.get("aftertasteReady") is True
            and as_int(reference_transition_summary.get("blockerCount")) == 0
            and as_float(reference_transition_summary.get("motionShare")) <= 0.25,
            {
                "transitionSceneArcStatus": transition_scene_arc.get("status"),
                "transitionSceneArcSummary": transition_scene_summary,
                "referenceTransitionProfileStatus": reference_transition.get("status"),
                "referenceTransitionProfileSummary": reference_transition_summary,
            },
            blockers,
            "transitions are not yet proven to support the chapter story spine",
        )
    )

    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "summary": {
            "chapterRowCount": chapter_count,
            "chaptersWithCompleteStorySpine": len([row for row in spine_rows if row.get("status") == "passed"]),
            "chaptersMissingStorySpine": len(blocked_spines),
            "rhythmChaptersReady": rhythm_summary.get("chapterRowCount"),
            "creatorChaptersReady": creator_summary.get("chapterRowCount"),
            "finalSourceStatus": final_source.get("status"),
            "creatorApplicationStatus": creator_application.get("status"),
            "referenceSceneGrammarStatus": reference_scene.get("status"),
            "timelineVarietyStatus": timeline_variety.get("status"),
            "transitionSceneArcStatus": transition_scene_arc.get("status"),
            "referenceTransitionProfileStatus": reference_transition.get("status"),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": sum(1 for row in checks if row["status"] == "blocked"),
            "blockerCount": len(blockers),
        },
        "spineRows": spine_rows,
        "checks": checks,
        "blockers": blockers,
        "warnings": [],
        "policy": {
            "chapterSpineBeats": list(REQUIRED_BEATS),
            "noTitleOnlyChapters": True,
            "noEffectOnlyTransitionMasking": True,
            "selectedRawFootageMustCarryStorySpine": True,
            "referenceAnchoredButNonCopying": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Chapter Story Spine Contract Audit",
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
    lines.extend(["", "## Chapter Rows"])
    for row in report.get("spineRows") or []:
        lines.extend(
            [
                "",
                f"### Chapter {row.get('chapterIndex')}: {row.get('chapterTitle') or ''}",
                f"- Status: `{row.get('status')}`",
                f"- Missing beats: `{', '.join(row.get('missingBeatIds') or []) or 'none'}`",
                f"- Rhythm ready: `{row.get('rhythmReady')}`",
                f"- Creator ready: `{row.get('creatorReady')}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit chapter story-spine execution across plans and final candidate reports.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir)
    write_json(package_dir / "chapter_story_spine_contract_audit.json", report)
    write_markdown(package_dir / "chapter_story_spine_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
