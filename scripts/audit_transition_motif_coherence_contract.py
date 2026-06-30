#!/usr/bin/env python3
"""Audit whether film-level transition motifs form a coherent travel-film language."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionMotif": ("transition_motif_plan/transition_motif_plan.json", {"ready_with_transition_motif_plan"}),
    "transitionReferenceSelection": (
        "transition_reference_selection/transition_reference_selection.json",
        {"ready_with_transition_reference_selection"},
    ),
    "transitionCadence": ("transition_cadence_contract_audit.json", {"passed"}),
    "transitionEffectPalette": ("transition_effect_palette_contract_audit.json", {"passed"}),
    "transitionSceneArc": ("transition_scene_arc_contract_audit.json", {"passed"}),
}

IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition", "ending_or_aftertaste_boundary"}
OPENING_ENDING_CATEGORIES = {"title_boundary", "ending_transition", "ending_or_aftertaste_boundary"}
MOTION_MOTIFS = {"motivated_motion"}
ANCHOR_MOTIFS = {"physical_route_bridge", "visual_match", "mood_dissolve", "simple_continuity"}
REFERENCE_MOTIFS = ANCHOR_MOTIFS | {"title_clean_reveal", "motivated_motion"}
IMPORTANT_MOTIFS = {"physical_route_bridge", "visual_match", "mood_dissolve", "title_clean_reveal"}
MOTIF_TO_STYLE_FAMILIES = {
    "physical_route_bridge": {"physical_bridge"},
    "visual_match": {"visual_match", "clean_cut"},
    "mood_dissolve": {"mood_dissolve", "title_breath"},
    "title_clean_reveal": {"title_breath", "clean_cut", "mood_dissolve"},
    "motivated_motion": {"motion_accent"},
    "simple_continuity": {"clean_cut", "visual_match", "physical_bridge"},
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
    return data.get("summary") if isinstance(data, dict) and isinstance(data.get("summary"), dict) else {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def load_reports(package_dir: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for key, (relative, accepted) in REPORT_SPECS.items():
        path = package_dir / relative
        data = load_json(path) or {}
        reports[key] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(accepted),
            "accepted": data.get("status") in accepted,
            "summary": summary_of(data),
            "blockers": data.get("blockers") or [],
            "warnings": data.get("warnings") or [],
            "raw": data,
        }
    return reports


def dict_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): as_int(count) for key, count in value.items() if as_int(count) > 0}


def run_stats(values: list[str]) -> tuple[int, list[dict[str, Any]]]:
    if not values:
        return 0, []
    runs: list[dict[str, Any]] = []
    best = 1
    current = values[0]
    start = 0
    for index, value in enumerate(values[1:], start=1):
        if value == current:
            best = max(best, index - start + 1)
            continue
        runs.append({"value": current, "startRow": start + 1, "endRow": index, "length": index - start})
        current = value
        start = index
    runs.append({"value": current, "startRow": start + 1, "endRow": len(values), "length": len(values) - start})
    return best, runs


def row_index(row: dict[str, Any]) -> int:
    return as_int(row.get("rowIndex"), 0)


def selected_lookup(selection: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = selection.get("selectionRows") if isinstance(selection.get("selectionRows"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            out[row_index(row)] = row
    return out


def family_for_selection(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    selected = row.get("selectedCandidate") if isinstance(row.get("selectedCandidate"), dict) else {}
    return str(selected.get("styleFamily") or "")


def selection_alignment(motif: str, family: str) -> bool:
    allowed = MOTIF_TO_STYLE_FAMILIES.get(motif)
    if not allowed:
        return False
    return family in allowed


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    motif_plan = reports["transitionMotif"]["raw"] if isinstance(reports["transitionMotif"]["raw"], dict) else {}
    selection_plan = reports["transitionReferenceSelection"]["raw"] if isinstance(reports["transitionReferenceSelection"]["raw"], dict) else {}
    motif_summary = reports["transitionMotif"]["summary"]
    selection_summary = reports["transitionReferenceSelection"]["summary"]
    cadence_summary = reports["transitionCadence"]["summary"]
    palette_summary = reports["transitionEffectPalette"]["summary"]
    scene_summary = reports["transitionSceneArc"]["summary"]

    motif_rows = [row for row in motif_plan.get("motifRows", []) if isinstance(row, dict)] if isinstance(motif_plan, dict) else []
    repair_rows = [row for row in motif_plan.get("repairRows", []) if isinstance(row, dict)] if isinstance(motif_plan, dict) else []
    selection_by_row = selected_lookup(selection_plan)
    row_count = len(motif_rows)
    motifs = [str(row.get("motif") or "") for row in motif_rows]
    styles = [str(row.get("executionStyle") or "") for row in motif_rows]
    motif_counts = dict_counts(motif_summary.get("motifCounts")) or {item: motifs.count(item) for item in sorted(set(motifs)) if item}
    style_counts = dict_counts(motif_summary.get("styleCounts")) or {item: styles.count(item) for item in sorted(set(styles)) if item}
    motif_family_count = len([motif for motif, count in motif_counts.items() if count > 0 and motif in REFERENCE_MOTIFS])
    min_family_count = 1 if row_count <= 2 else (2 if row_count <= 5 else args.min_motif_family_count)
    repeated_motif_run_max, motif_runs = run_stats(motifs)
    repeated_style_run_max, style_runs = run_stats(styles)
    dominant_motif = None
    dominant_motif_share = 0.0
    if motif_counts and row_count:
        dominant_motif, dominant_count = max(motif_counts.items(), key=lambda item: item[1])
        dominant_motif_share = round(dominant_count / row_count, 4)

    motion_rows = [row for row in motif_rows if str(row.get("motif") or "") in MOTION_MOTIFS]
    motion_indices = sorted(row_index(row) for row in motion_rows)
    motion_spacing_violations = [
        {"previousRow": previous, "row": current}
        for previous, current in zip(motion_indices, motion_indices[1:])
        if current - previous < args.min_motion_spacing
    ]
    first_last_rows = [row for row in motif_rows if row_index(row) in {1, row_count} or row.get("boundaryCategory") in OPENING_ENDING_CATEGORIES]
    first_last_motion_rows = [
        {"rowIndex": row.get("rowIndex"), "boundaryCategory": row.get("boundaryCategory"), "motif": row.get("motif")}
        for row in first_last_rows
        if row.get("motif") in MOTION_MOTIFS
    ]
    important_rows = [row for row in motif_rows if row.get("boundaryCategory") in IMPORTANT_CATEGORIES]
    important_ready_rows = [
        row for row in important_rows if str(row.get("motif") or "") in IMPORTANT_MOTIFS and row.get("bgmPhraseCue")
    ]
    chapter_like_rows = [row for row in motif_rows if row.get("boundaryCategory") in {"chapter_boundary", "timeline_gap"}]
    chapter_like_with_bridge = [
        row for row in chapter_like_rows if str(row.get("motif") or "") in {"physical_route_bridge", "visual_match", "mood_dissolve"}
    ]
    anchor_count = sum(count for motif, count in motif_counts.items() if motif in ANCHOR_MOTIFS)
    title_rows = [row for row in motif_rows if row.get("boundaryCategory") == "title_boundary"]
    title_safe_rows = [row for row in title_rows if "title" in str(row.get("titleZonePolicy") or "").lower()]

    missing_selection_rows: list[dict[str, Any]] = []
    selection_mismatches: list[dict[str, Any]] = []
    for row in motif_rows:
        index = row_index(row)
        selected = selection_by_row.get(index)
        family = family_for_selection(selected)
        motif = str(row.get("motif") or "")
        if not selected:
            missing_selection_rows.append({"rowIndex": index, "motif": motif})
            continue
        if not selection_alignment(motif, family):
            selection_mismatches.append(
                {
                    "rowIndex": index,
                    "motif": motif,
                    "selectedStyleFamily": family,
                    "boundaryCategory": row.get("boundaryCategory"),
                }
            )

    blocking_repair_rows = [
        row
        for row in repair_rows
        if str(row.get("priority") or "").upper() == "P0" or str(row.get("status") or "").startswith("needs")
    ]
    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required motif, reference-selection, cadence, palette, and scene-arc inputs are accepted",
        all(report["exists"] and report["accepted"] for report in reports.values()),
        {
            name: {
                "exists": report["exists"],
                "status": report["status"],
                "acceptedStatuses": report["acceptedStatuses"],
                "blockerCount": len(report["blockers"]),
            }
            for name, report in reports.items()
        },
    )
    add_check(
        checks,
        "Every motif row is ready, BGM-cued, title-safe when needed, and free of unresolved repair rows",
        row_count >= args.min_transition_rows
        and as_int(motif_summary.get("rowsReadyWithMotif")) == row_count
        and as_int(motif_summary.get("rowsWithBgmPhraseCue")) == row_count
        and len(title_safe_rows) == len(title_rows)
        and as_int(motif_summary.get("blockedMotifRowCount")) == 0
        and not blocking_repair_rows,
        {
            "transitionRowCount": row_count,
            "minTransitionRows": args.min_transition_rows,
            "rowsReadyWithMotif": motif_summary.get("rowsReadyWithMotif"),
            "rowsWithBgmPhraseCue": motif_summary.get("rowsWithBgmPhraseCue"),
            "titleBoundaryRowsSafe": motif_summary.get("titleBoundaryRowsSafe"),
            "titleBoundaryCount": len(title_rows),
            "localTitleBoundarySafeCount": len(title_safe_rows),
            "blockedMotifRowCount": motif_summary.get("blockedMotifRowCount"),
            "repairRowCount": len(repair_rows),
            "blockingRepairRows": blocking_repair_rows[: args.max_rows_in_report],
        },
    )
    add_check(
        checks,
        "The whole film has a coherent motif vocabulary instead of one dominant template",
        motif_family_count >= min_family_count
        and dominant_motif_share <= args.max_dominant_motif_share
        and repeated_motif_run_max <= args.max_repeated_motif_run
        and repeated_style_run_max <= args.max_repeated_style_run
        and anchor_count >= max(1, row_count - len(motion_rows) - len(title_rows) - 1),
        {
            "motifCounts": motif_counts,
            "styleCounts": style_counts,
            "motifFamilyCount": motif_family_count,
            "minimumMotifFamilyCount": min_family_count,
            "dominantMotif": dominant_motif,
            "dominantMotifShare": dominant_motif_share,
            "maxDominantMotifShare": args.max_dominant_motif_share,
            "repeatedMotifRunMax": repeated_motif_run_max,
            "maxRepeatedMotifRun": args.max_repeated_motif_run,
            "repeatedStyleRunMax": repeated_style_run_max,
            "maxRepeatedStyleRun": args.max_repeated_style_run,
            "longMotifRuns": [row for row in motif_runs if row["length"] > args.max_repeated_motif_run][: args.max_rows_in_report],
            "longStyleRuns": [row for row in style_runs if row["length"] > args.max_repeated_style_run][: args.max_rows_in_report],
            "anchorMotifCount": anchor_count,
        },
    )
    add_check(
        checks,
        "Important route, title, gap, and ending boundaries use bridge, match, dissolve, or title-reveal motifs",
        len(important_ready_rows) == len(important_rows)
        and (
            not chapter_like_rows
            or len(chapter_like_with_bridge) == len(chapter_like_rows)
            or as_int(scene_summary.get("sceneArcStrategyCount")) >= 1
        ),
        {
            "importantBoundaryCount": len(important_rows),
            "importantReadyBoundaryCount": len(important_ready_rows),
            "chapterOrTimelineBoundaryCount": len(chapter_like_rows),
            "chapterOrTimelineWithBridgeMotifCount": len(chapter_like_with_bridge),
            "sceneArcStrategyCount": scene_summary.get("sceneArcStrategyCount"),
            "blockedImportantRows": [
                {
                    "rowIndex": row.get("rowIndex"),
                    "boundaryCategory": row.get("boundaryCategory"),
                    "motif": row.get("motif"),
                    "bgmPhraseCue": row.get("bgmPhraseCue"),
                }
                for row in important_rows
                if row not in important_ready_rows
            ][: args.max_rows_in_report],
        },
    )
    add_check(
        checks,
        "Motion motifs are rare spaced accents and never open, close, or cover title/ending moments",
        len(motion_rows) <= max(1, int(row_count * args.max_motion_share))
        and not motion_spacing_violations
        and not first_last_motion_rows,
        {
            "motionMotifCount": len(motion_rows),
            "motionMotifShare": round(len(motion_rows) / row_count, 4) if row_count else 0.0,
            "maxMotionShare": args.max_motion_share,
            "minMotionSpacing": args.min_motion_spacing,
            "motionSpacingViolationCount": len(motion_spacing_violations),
            "motionSpacingViolations": motion_spacing_violations[: args.max_rows_in_report],
            "openingEndingMotionRowCount": len(first_last_motion_rows),
            "openingEndingMotionRows": first_last_motion_rows[: args.max_rows_in_report],
            "paletteMotionTransitionCount": palette_summary.get("motionTransitionCount"),
            "paletteMaxMotionAllowed": palette_summary.get("maxMotionAllowed"),
        },
    )
    add_check(
        checks,
        "Reference-selected transition families match the motif language for each boundary",
        as_int(selection_summary.get("selectionRowCount")) == row_count
        and as_int(selection_summary.get("blockedSelectionRowCount")) == 0
        and not missing_selection_rows
        and not selection_mismatches,
        {
            "selectionStatus": reports["transitionReferenceSelection"]["status"],
            "selectionRowCount": selection_summary.get("selectionRowCount"),
            "selectedRowCount": selection_summary.get("selectedRowCount"),
            "blockedSelectionRowCount": selection_summary.get("blockedSelectionRowCount"),
            "selectedStyleFamilyCounts": selection_summary.get("selectedStyleFamilyCounts"),
            "missingSelectionRowCount": len(missing_selection_rows),
            "selectionMismatchCount": len(selection_mismatches),
            "missingSelectionRows": missing_selection_rows[: args.max_rows_in_report],
            "selectionMismatches": selection_mismatches[: args.max_rows_in_report],
        },
    )
    add_check(
        checks,
        "Downstream cadence, palette, and scene-arc reports agree with the motif-coherence contract",
        as_int(cadence_summary.get("blockedCheckCount")) == 0
        and as_int(palette_summary.get("blockedCheckCount")) == 0
        and as_int(scene_summary.get("blockedCheckCount")) == 0
        and as_float(palette_summary.get("dominantMotifShare")) <= args.max_dominant_motif_share
        and as_int(palette_summary.get("decorativeRepeatedRunMax")) <= args.max_repeated_style_run
        and as_int(palette_summary.get("motionTransitionCount")) <= as_int(palette_summary.get("maxMotionAllowed")),
        {
            "transitionCadenceStatus": reports["transitionCadence"]["status"],
            "cadenceBlockedCheckCount": cadence_summary.get("blockedCheckCount"),
            "transitionEffectPaletteStatus": reports["transitionEffectPalette"]["status"],
            "paletteBlockedCheckCount": palette_summary.get("blockedCheckCount"),
            "paletteDominantMotifShare": palette_summary.get("dominantMotifShare"),
            "paletteDecorativeRepeatedRunMax": palette_summary.get("decorativeRepeatedRunMax"),
            "transitionSceneArcStatus": reports["transitionSceneArc"]["status"],
            "sceneArcBlockedCheckCount": scene_summary.get("blockedCheckCount"),
            "sceneArcStrategyCount": scene_summary.get("sceneArcStrategyCount"),
        },
    )

    blockers = [row["name"] for row in checks if row["status"] == "blocked"]
    summary = {
        "transitionRowCount": row_count,
        "motifFamilyCount": motif_family_count,
        "minimumMotifFamilyCount": min_family_count,
        "motifCounts": motif_counts,
        "styleCounts": style_counts,
        "dominantMotif": dominant_motif,
        "dominantMotifShare": dominant_motif_share,
        "repeatedMotifRunMax": repeated_motif_run_max,
        "repeatedStyleRunMax": repeated_style_run_max,
        "anchorMotifCount": anchor_count,
        "importantBoundaryCount": len(important_rows),
        "importantReadyBoundaryCount": len(important_ready_rows),
        "chapterOrTimelineBoundaryCount": len(chapter_like_rows),
        "chapterOrTimelineWithBridgeMotifCount": len(chapter_like_with_bridge),
        "motionMotifCount": len(motion_rows),
        "motionMotifShare": round(len(motion_rows) / row_count, 4) if row_count else 0.0,
        "motionSpacingViolationCount": len(motion_spacing_violations),
        "openingEndingMotionRowCount": len(first_last_motion_rows),
        "selectionMismatchCount": len(selection_mismatches),
        "missingSelectionRowCount": len(missing_selection_rows),
        "repairRowCount": len(repair_rows),
        "blockingRepairRowCount": len(blocking_repair_rows),
        "titleBoundaryCount": len(title_rows),
        "titleBoundarySafeCount": len(title_safe_rows),
        "passedCheckCount": len(checks) - len(blockers),
        "blockedCheckCount": len(blockers),
        "blockerCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "reports": {key: row["path"] for key, row in reports.items()},
            "minTransitionRows": args.min_transition_rows,
            "minMotifFamilyCount": args.min_motif_family_count,
            "maxDominantMotifShare": args.max_dominant_motif_share,
            "maxRepeatedMotifRun": args.max_repeated_motif_run,
            "maxRepeatedStyleRun": args.max_repeated_style_run,
            "maxMotionShare": args.max_motion_share,
            "minMotionSpacing": args.min_motion_spacing,
        },
        "summary": summary,
        "checks": checks,
        "reports": {key: {k: v for k, v in row.items() if k != "raw"} for key, row in reports.items()},
        "blockers": blockers,
        "warnings": [warning for report in reports.values() for warning in report["warnings"]],
        "policy": {
            "filmLevelMotifCoherenceRequired": True,
            "referenceSelectionMustMatchMotif": True,
            "motionMotifsAreRareSpacedAccents": True,
            "openingEndingMotionMotifsRejected": True,
            "importantBoundariesNeedBridgeMatchDissolveOrTitleReveal": True,
            "unresolvedMotifRepairsBlockFinalCandidate": True,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Motif Coherence Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Upstream Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"][:80])
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(
            [
                "",
                f"### {row.get('name')}",
                f"- Status: `{row.get('status')}`",
                f"- Evidence: `{json.dumps(row.get('evidence'), ensure_ascii=False)[:1800]}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Contract",
            "- Treat transitions as a film-level language, not isolated effects.",
            "- Keep motion motifs rare, spaced, and absent from opening/title/ending moments.",
            "- Use physical bridge, visual match, mood dissolve, or title reveal for route/title/gap boundaries.",
            "- Block final candidates when reference-selected style families contradict the motif plan.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit film-level transition motif coherence from existing transition reports.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-transition-rows", type=int, default=3)
    parser.add_argument("--min-motif-family-count", type=int, default=3)
    parser.add_argument("--max-dominant-motif-share", type=float, default=0.6)
    parser.add_argument("--max-repeated-motif-run", type=int, default=3)
    parser.add_argument("--max-repeated-style-run", type=int, default=3)
    parser.add_argument("--max-motion-share", type=float, default=0.22)
    parser.add_argument("--min-motion-spacing", type=int, default=5)
    parser.add_argument("--max-rows-in-report", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_motif_coherence_contract_audit.json", report)
    write_markdown(package_dir / "transition_motif_coherence_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
