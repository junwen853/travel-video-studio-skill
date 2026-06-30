#!/usr/bin/env python3
"""Audit whether transitions keep viewers oriented across route, day, and chapter jumps."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "transitionStoryboard": ("transition_storyboard_contract_audit.json", {"passed"}),
    "narrativeAdjacency": ("narrative_adjacency_contract_audit.json", {"passed"}),
    "routeTexture": ("route_texture_contract_audit.json", {"passed", "passed_with_warnings"}),
    "chapterStorySpine": ("chapter_story_spine_contract_audit.json", {"passed"}),
    "shotFlowContinuity": ("shot_flow_continuity_contract_audit.json", {"passed"}),
    "transitionMotifCoherence": ("transition_motif_coherence_contract_audit.json", {"passed"}),
    "transitionBreathingRoom": ("transition_breathing_room_contract_audit.json", {"passed"}),
    "pacingWatchability": ("pacing_watchability_contract_audit.json", {"passed"}),
    "finalBlueprintLineage": ("final_blueprint_lineage_contract_audit.json", {"passed"}),
}

IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition", "ending_or_aftertaste_boundary"}
ORIENTATION_PURPOSES = {"route_move", "time_jump", "title_reveal", "texture_bridge", "scenic_breath", "payoff_handoff", "ending_aftertaste"}
ROUTE_CUE_TERMS = (
    "route",
    "bridge",
    "transport",
    "street",
    "station",
    "train",
    "airport",
    "ferry",
    "bus",
    "taxi",
    "road",
    "walking",
    "arrival",
    "departure",
    "hotel",
    "sign",
    "signage",
    "city",
    "place",
    "chapter",
    "title",
    "caption",
    "subtitle",
    "bgm",
    "phrase",
    "aftertaste",
    "landing",
    "scenic",
    "aerial",
    "establish",
    "establishing",
    "车站",
    "机场",
    "街",
    "路",
    "桥",
    "酒店",
    "城市",
    "到达",
    "出发",
    "字幕",
    "标题",
    "航拍",
)
GENERIC_BAD_TERMS = ("generic", "placeholder", "black", "slate", "duplicate", "test", "sample", "unknown", "utility")


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


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def lower_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    return clean(value).lower()


def present(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return bool(clean(value))
    if isinstance(value, list):
        return any(present(item) for item in value)
    if isinstance(value, dict):
        return any(present(item) for item in value.values())
    return value is not None


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
    for name, (relative, accepted) in REPORT_SPECS.items():
        path = package_dir / relative
        data = load_json(path) or {}
        reports[name] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(accepted),
            "accepted": data.get("status") in accepted,
            "summary": summary_of(data),
            "blockers": data.get("blockers") or [],
            "warnings": data.get("warnings") or [],
            "data": data,
        }
    return reports


def row_index(row: dict[str, Any]) -> int:
    return as_int(row.get("rowIndex") or row.get("pairIndex"), 0)


def source_key(row: dict[str, Any]) -> tuple[str, str]:
    left = clean(row.get("fromSourceName") or row.get("fromSourcePath"))
    right = clean(row.get("toSourceName") or row.get("toSourcePath"))
    return left, right


def narrative_lookup(report: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = report.get("adjacencyRows") if isinstance(report.get("adjacencyRows"), list) else []
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            index = as_int(row.get("pairIndex"), -1)
            if index >= 0:
                out[index] = row
    return out


def storyboard_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("auditedRows") if isinstance(report.get("auditedRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def has_route_cue(row: dict[str, Any]) -> bool:
    fields = [
        row.get("storyboardPurpose"),
        row.get("outgoingShotEvidence"),
        row.get("bridgeOrMotionBeatEvidence"),
        row.get("landingShotEvidence"),
        row.get("previewStripEvidence"),
        row.get("transitionAuditionEvidence"),
        row.get("bridgeTerms"),
        row.get("fromMotionTerms"),
        row.get("toMotionTerms"),
        row.get("fromSourceName"),
        row.get("toSourceName"),
    ]
    text = " ".join(lower_text(item) for item in fields)
    return any(term in text for term in ROUTE_CUE_TERMS)


def weak_landing(row: dict[str, Any]) -> bool:
    text = lower_text(row.get("landingShotEvidence") or row.get("toSourceName"))
    return not text or any(term in text for term in GENERIC_BAD_TERMS)


def has_orientation_purpose(row: dict[str, Any]) -> bool:
    purpose = clean(row.get("storyboardPurpose")).lower()
    if purpose in ORIENTATION_PURPOSES:
        return True
    return str(row.get("boundaryCategory") or "").lower() not in IMPORTANT_CATEGORIES


def narrative_support(row: dict[str, Any], narrative: dict[str, dict[str, Any]]) -> dict[str, Any]:
    index = row_index(row)
    match = narrative.get(index) or {}
    if not match:
        row_sources = source_key(row)
        for candidate in narrative.values():
            if source_key(candidate) == row_sources:
                match = candidate
                break
    reasons = match.get("reasons") if isinstance(match.get("reasons"), list) else []
    issues = match.get("issues") if isinstance(match.get("issues"), list) else []
    return {
        "rowIndex": index,
        "matched": bool(match),
        "category": match.get("category"),
        "reasons": reasons,
        "issues": issues,
        "hasRouteTitleBridgeOrAftertasteReason": bool(
            {
                "route_or_movement_handoff",
                "aftertaste_or_breathing_handoff",
                "title_handoff",
                "explicit_transition_bridge_or_bgm_metadata",
                "same_chapter_place_continuity",
            }
            & set(str(item) for item in reasons)
        ),
    }


def orientation_row(row: dict[str, Any], narrative: dict[str, dict[str, Any]]) -> dict[str, Any]:
    category = clean(row.get("boundaryCategory")).lower()
    important = bool(row.get("importantBoundary")) or category in IMPORTANT_CATEGORIES
    support = narrative_support(row, narrative)
    issues: list[str] = []
    if important and not has_orientation_purpose(row):
        issues.append("important_transition_lacks_viewer_orientation_purpose")
    if important and not has_route_cue(row):
        issues.append("important_transition_lacks_route_title_caption_or_bridge_cue")
    if important and weak_landing(row):
        issues.append("important_transition_lands_on_unknown_or_generic_shot")
    if important and not present(row.get("previewStripEvidence")):
        issues.append("important_transition_lacks_preview_orientation_evidence")
    if important and not present(row.get("transitionAuditionEvidence")):
        issues.append("important_transition_lacks_watchable_orientation_audition")
    if important and (not support["matched"] or not support["hasRouteTitleBridgeOrAftertasteReason"]):
        issues.append("important_transition_lacks_narrative_handoff_reason")
    if support["issues"]:
        issues.append("narrative_adjacency_reports_boundary_issues")
    return {
        "rowIndex": row_index(row),
        "boundaryCategory": category,
        "storyboardPurpose": row.get("storyboardPurpose"),
        "importantBoundary": important,
        "fromSourceName": row.get("fromSourceName"),
        "toSourceName": row.get("toSourceName"),
        "landingShotEvidence": row.get("landingShotEvidence"),
        "bridgeOrMotionBeatEvidence": row.get("bridgeOrMotionBeatEvidence"),
        "previewStripEvidence": row.get("previewStripEvidence"),
        "transitionAuditionEvidence": row.get("transitionAuditionEvidence"),
        "hasRouteCue": has_route_cue(row),
        "hasOrientationPurpose": has_orientation_purpose(row),
        "weakLanding": weak_landing(row),
        "narrativeSupport": support,
        "status": "passed" if not issues else "blocked",
        "issues": issues,
    }


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    storyboard = reports["transitionStoryboard"]["data"] if isinstance(reports["transitionStoryboard"]["data"], dict) else {}
    narrative = reports["narrativeAdjacency"]["data"] if isinstance(reports["narrativeAdjacency"]["data"], dict) else {}
    narrative_rows = narrative_lookup(narrative)
    rows = [orientation_row(row, narrative_rows) for row in storyboard_rows(storyboard)]
    important_rows = [row for row in rows if row["importantBoundary"]]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    important_blocked = [row for row in important_rows if row["status"] == "blocked"]
    route_cued = [row for row in important_rows if row["hasRouteCue"]]
    purpose_ready = [row for row in important_rows if row["hasOrientationPurpose"]]
    landing_ready = [row for row in important_rows if not row["weakLanding"]]
    preview_ready = [row for row in important_rows if present(row["previewStripEvidence"])]
    audition_ready = [row for row in important_rows if present(row["transitionAuditionEvidence"])]
    narrative_ready = [
        row
        for row in important_rows
        if row["narrativeSupport"]["matched"] and row["narrativeSupport"]["hasRouteTitleBridgeOrAftertasteReason"]
    ]

    route_summary = reports["routeTexture"]["summary"]
    narrative_summary = reports["narrativeAdjacency"]["summary"]
    spine_summary = reports["chapterStorySpine"]["summary"]
    motif_summary = reports["transitionMotifCoherence"]["summary"]

    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Required storyboard, narrative, route, chapter, shot-flow, motif, breathing-room, pacing, and lineage reports are accepted",
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
        "Important transitions orient the viewer with purpose, route/title/caption/bridge cues, stable landing, preview, and audition evidence",
        len(rows) >= args.min_transition_rows
        and len(important_rows) >= args.min_important_rows
        and len(purpose_ready) == len(important_rows)
        and len(route_cued) == len(important_rows)
        and len(landing_ready) == len(important_rows)
        and (args.allow_missing_preview or len(preview_ready) == len(important_rows))
        and len(audition_ready) == len(important_rows)
        and not important_blocked,
        {
            "transitionRowCount": len(rows),
            "importantBoundaryCount": len(important_rows),
            "minTransitionRows": args.min_transition_rows,
            "minImportantRows": args.min_important_rows,
            "purposeReadyCount": len(purpose_ready),
            "routeCueCount": len(route_cued),
            "stableLandingCount": len(landing_ready),
            "previewEvidenceCount": len(preview_ready),
            "auditionEvidenceCount": len(audition_ready),
            "importantBlockedRows": important_blocked[: args.max_rows_in_report],
        },
    )
    add_check(
        checks,
        "Important transitions have narrative handoff reasons that match the final adjacent-shot audit",
        len(narrative_ready) == len(important_rows)
        and as_int(narrative_summary.get("blockedChapterHandoffCount")) == 0
        and as_int(narrative_summary.get("unmotivatedPairCount")) == 0
        and as_int(narrative_summary.get("blockedPairCount")) == 0,
        {
            "importantBoundaryCount": len(important_rows),
            "narrativeReadyImportantCount": len(narrative_ready),
            "narrativeAdjacencySummary": narrative_summary,
        },
    )
    add_check(
        checks,
        "Route texture and chapter spine support viewer orientation across the whole film",
        as_int(route_summary.get("matchedTransitions")) >= max(1, int(as_int(route_summary.get("transitionPlanCount")) * args.min_route_match_ratio))
        and as_int(route_summary.get("matchedTitleBoundaries")) >= max(1, int(as_int(route_summary.get("chapterTitleCount")) * args.min_title_match_ratio))
        and as_int(route_summary.get("passedChapters")) >= max(1, int(as_int(route_summary.get("chapterWindowCount")) * args.min_chapter_pass_ratio))
        and as_int(spine_summary.get("chaptersMissingStorySpine")) == 0
        and as_int(spine_summary.get("blockedCheckCount")) == 0,
        {
            "routeTextureSummary": route_summary,
            "chapterStorySpineSummary": spine_summary,
            "minRouteMatchRatio": args.min_route_match_ratio,
            "minTitleMatchRatio": args.min_title_match_ratio,
            "minChapterPassRatio": args.min_chapter_pass_ratio,
        },
    )
    add_check(
        checks,
        "Motif coherence and pacing agree that orientation is not being hidden behind random motion or rushed landings",
        as_int(motif_summary.get("openingEndingMotionRowCount")) == 0
        and as_int(motif_summary.get("selectionMismatchCount")) == 0
        and as_int(motif_summary.get("motionSpacingViolationCount")) == 0
        and as_int(reports["transitionBreathingRoom"]["summary"].get("blockedCheckCount")) == 0
        and as_int(reports["pacingWatchability"]["summary"].get("blockedCheckCount")) == 0,
        {
            "transitionMotifCoherenceSummary": motif_summary,
            "transitionBreathingRoomSummary": reports["transitionBreathingRoom"]["summary"],
            "pacingWatchabilitySummary": reports["pacingWatchability"]["summary"],
        },
    )

    blocked_checks = [check for check in checks if check["status"] == "blocked"]
    blockers = [check["name"] for check in blocked_checks]
    blockers.extend(f"row {row.get('rowIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[: args.max_rows_in_report])
    summary = {
        "transitionRowCount": len(rows),
        "importantBoundaryCount": len(important_rows),
        "viewerOrientationReadyCount": len(rows) - len(blocked_rows),
        "importantOrientationReadyCount": len(important_rows) - len(important_blocked),
        "blockedRowCount": len(blocked_rows),
        "importantBlockedRowCount": len(important_blocked),
        "purposeReadyImportantCount": len(purpose_ready),
        "routeCueImportantCount": len(route_cued),
        "stableLandingImportantCount": len(landing_ready),
        "previewEvidenceImportantCount": len(preview_ready),
        "auditionEvidenceImportantCount": len(audition_ready),
        "narrativeReadyImportantCount": len(narrative_ready),
        "narrativeBlockedPairCount": narrative_summary.get("blockedPairCount"),
        "narrativeUnmotivatedPairCount": narrative_summary.get("unmotivatedPairCount"),
        "routeMatchedTransitions": route_summary.get("matchedTransitions"),
        "routeTransitionPlanCount": route_summary.get("transitionPlanCount"),
        "routeMatchedTitleBoundaries": route_summary.get("matchedTitleBoundaries"),
        "routeChapterTitleCount": route_summary.get("chapterTitleCount"),
        "chapterWindowCount": route_summary.get("chapterWindowCount"),
        "passedChapters": route_summary.get("passedChapters"),
        "blockedCheckCount": len(blocked_checks),
        "blockerCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blocked_checks and not blocked_rows else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "reports": {name: report["path"] for name, report in reports.items()},
            "minTransitionRows": args.min_transition_rows,
            "minImportantRows": args.min_important_rows,
            "allowMissingPreview": args.allow_missing_preview,
        },
        "summary": summary,
        "orientationRows": rows,
        "checks": checks,
        "reports": {name: {key: value for key, value in report.items() if key != "data"} for name, report in reports.items()},
        "blockers": blockers,
        "warnings": [warning for report in reports.values() for warning in report["warnings"]],
        "policy": {
            "viewerOrientationRequiredForImportantTransitions": True,
            "routeTitleCaptionOrBridgeCueRequired": True,
            "stableLandingRequired": True,
            "narrativeHandoffReasonRequired": True,
            "previewAndAuditionEvidenceRequired": not args.allow_missing_preview,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Viewer Orientation Contract Audit",
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
    lines.extend(["", "## Orientation Rows"])
    for row in report.get("orientationRows", [])[:120]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: `{row.get('boundaryCategory')}` / `{row.get('storyboardPurpose')}`",
                f"- Status: `{row.get('status')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Landing: `{row.get('landingShotEvidence')}`",
                f"- Cue: `{row.get('bridgeOrMotionBeatEvidence')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Important route, title, day/place, and ending transitions must orient the viewer, not only look polished.",
            "- Use a viewer purpose, route/title/caption/bridge cue, stable landing shot, preview evidence, and watchable muted audition evidence.",
            "- A chapter or timeline jump cannot pass if the final adjacent-shot audit lacks a route, title, bridge, aftertaste, BGM, or place-continuity reason.",
            "- Do not hide unclear geography or time jumps behind rotation, whip, speed-ramp, or generic scenic footage.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit viewer orientation across important travel-film transitions.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--min-transition-rows", type=int, default=3)
    parser.add_argument("--min-important-rows", type=int, default=1)
    parser.add_argument("--min-route-match-ratio", type=float, default=0.75)
    parser.add_argument("--min-title-match-ratio", type=float, default=0.75)
    parser.add_argument("--min-chapter-pass-ratio", type=float, default=0.8)
    parser.add_argument("--allow-missing-preview", action="store_true")
    parser.add_argument("--max-rows-in-report", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_viewer_orientation_contract_audit.json", report)
    write_markdown(package_dir / "transition_viewer_orientation_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
