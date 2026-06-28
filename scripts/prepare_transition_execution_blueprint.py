#!/usr/bin/env python3
"""Materialize transition execution rows into a non-destructive Resolve blueprint candidate."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint": "",
    "approvedTransitionRows": "",
    "resolveImplementation": "",
    "preflightEvidence": "",
    "timelineReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

FORBIDDEN_TERMS = (
    "random spin",
    "glitch",
    "flash",
    "shake",
    "strobe",
    "template",
    "particle",
    "whoosh pack",
)


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def is_video_clip(clip: dict[str, Any]) -> bool:
    track_type = str(clip.get("trackType") or "video").lower()
    return track_type in {"", "video"} and int(as_float(clip.get("mediaType"), 1) or 1) == 1


def blueprint_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def row_source_keys(clip: dict[str, Any]) -> set[str]:
    keys = set()
    for value in (clip.get("sourcePath"), clip.get("sourceName")):
        text = str(value or "")
        if text:
            keys.add(text)
            keys.add(source_name(text))
    return {key for key in keys if key}


def boundary_seconds(row: dict[str, Any]) -> float:
    explicit = as_float(row.get("timelineStartSeconds"))
    if explicit is not None:
        return explicit
    from_clip = row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}
    to_clip = row.get("toClip") if isinstance(row.get("toClip"), dict) else {}
    left = timeline_end(from_clip)
    right = timeline_start(to_clip)
    if left or right:
        return (left + right) / 2.0
    return 0.0


def candidate_source_path(row_clip: dict[str, Any]) -> str:
    return str(row_clip.get("sourcePath") or row_clip.get("sourceName") or "")


def select_clip_index(clips: list[dict[str, Any]], row_clip: dict[str, Any], boundary: float, *, side: str) -> int | None:
    keys = row_source_keys(row_clip)
    scored: list[tuple[tuple[float, float, int], int]] = []
    for index, clip in enumerate(clips):
        if not is_video_clip(clip):
            continue
        clip_keys = row_source_keys(clip)
        if keys and not (keys & clip_keys):
            continue
        if side == "from":
            edge = timeline_end(clip)
            side_penalty = 0.0 if edge <= boundary + 0.75 else 10_000.0
        else:
            edge = timeline_start(clip)
            side_penalty = 0.0 if edge >= boundary - 0.75 else 10_000.0
        scored.append(((side_penalty, abs(edge - boundary), float(index)), index))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    return scored[0][1]


def forbidden_hits(row: dict[str, Any]) -> list[str]:
    upstream = row.get("forbiddenRecipeHits") if isinstance(row.get("forbiddenRecipeHits"), list) else []
    if upstream:
        return [str(item) for item in upstream if str(item).strip()]
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    selected_fields = {
        "resolveEffectName": recipe.get("resolveEffectName"),
        "trackOperation": recipe.get("trackOperation"),
        "style": recipe.get("style"),
        "approvedTransitionType": decision.get("approvedTransitionType"),
        "approvedResolveEffectName": decision.get("approvedResolveEffectName"),
    }
    text = json.dumps(selected_fields, ensure_ascii=False).lower()
    return [term for term in FORBIDDEN_TERMS if term in text]


def bridge_row_indices(package_dir: Path) -> set[int]:
    report = load_json(package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json") or {}
    rows = report.get("materializedRows") if isinstance(report.get("materializedRows"), list) else []
    out: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "materialized" and int(row.get("insertedBeatCount") or 0) > 0:
            out.add(as_int(row.get("rowIndex"), -1))
    return {value for value in out if value >= 0}


def choose_base_blueprint(package_dir: Path) -> tuple[dict[str, Any] | None, Path, str]:
    bridge_report = load_json(package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json") or {}
    outputs = bridge_report.get("outputs") if isinstance(bridge_report.get("outputs"), dict) else {}
    bridge_candidate = Path(str(outputs.get("candidateBlueprint") or package_dir / "bridge_sequence_blueprint" / "resolve_timeline_blueprint_bridge_sequence.json"))
    if bridge_report.get("status") == "ready_with_bridge_sequence_blueprint" and bridge_candidate.exists():
        return load_json(bridge_candidate), bridge_candidate, "bridge_sequence_candidate"
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint"


def safety_policy() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "mutatesActiveBlueprintByDefault": False,
    }


def transition_payload(row: dict[str, Any], *, fps: float, boundary: float, bridge_satisfied: bool) -> dict[str, Any]:
    recipe = row.get("executionRecipe") if isinstance(row.get("executionRecipe"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    duration_frames = as_int(recipe.get("durationFrames") or decision.get("durationFrames"), 0)
    duration_seconds = duration_frames / fps if fps > 0 else 0.0
    return {
        "role": "transition_execution_candidate",
        "rowIndex": row.get("rowIndex"),
        "status": row.get("status"),
        "boundaryCategory": row.get("boundaryCategory"),
        "boundarySeconds": round3(boundary),
        "fromSourcePath": candidate_source_path(row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}),
        "toSourcePath": candidate_source_path(row.get("toClip") if isinstance(row.get("toClip"), dict) else {}),
        "approvedTransitionType": decision.get("approvedTransitionType") or recipe.get("style") or (row.get("grammarRecommendation") or {}).get("recommendedTransitionType"),
        "resolveEffectName": decision.get("approvedResolveEffectName") or recipe.get("resolveEffectName"),
        "durationFrames": duration_frames,
        "durationSeconds": round3(duration_seconds),
        "preRollFrames": as_int(recipe.get("preRollFrames"), 0),
        "postRollFrames": as_int(recipe.get("postRollFrames"), 0),
        "trackOperation": recipe.get("trackOperation"),
        "keyframePlan": recipe.get("keyframePlan") if isinstance(recipe.get("keyframePlan"), list) else [],
        "implementationSteps": recipe.get("implementationSteps") if isinstance(recipe.get("implementationSteps"), list) else [],
        "audioPolicy": recipe.get("audioPolicy"),
        "subtitlePolicy": recipe.get("subtitlePolicy"),
        "bgmPhraseCue": recipe.get("bgmPhraseCue") or decision.get("bgmPhraseCue"),
        "requiresBridgeInsert": row.get("requiresBridgeInsert") is True,
        "bridgeSequenceSatisfied": bridge_satisfied,
        "motionStyle": row.get("motionStyle") is True,
        "motionHasEvidence": row.get("motionHasEvidence") is True,
        "forbiddenRecipeHits": forbidden_hits(row),
        "decision": dict(DECISION_FIELDS),
    }


def build_candidate(package_dir: Path, *, fps: float, update_blueprint: bool) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    plan_path = package_dir / "transition_execution_plan" / "transition_execution_plan.json"
    output_dir = package_dir / "transition_execution_blueprint"
    candidate_path = output_dir / "resolve_timeline_blueprint_transition_execution.json"
    report_path = output_dir / "transition_execution_blueprint_report.json"
    markdown_path = output_dir / "transition_execution_blueprint_report.md"
    base_blueprint, base_path, base_kind = choose_base_blueprint(package_dir)
    plan = load_json(plan_path)

    if not isinstance(base_blueprint, dict) or not isinstance(plan, dict):
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "needs_transition_execution_blueprint_inputs",
            "packageDir": str(package_dir),
            "inputs": {
                "baseBlueprint": str(base_path),
                "baseBlueprintExists": base_path.exists(),
                "transitionExecutionPlan": str(plan_path),
                "transitionExecutionPlanExists": plan_path.exists(),
            },
            "outputs": {
                "candidateBlueprint": str(candidate_path),
                "reportJson": str(report_path),
                "reportMarkdown": str(markdown_path),
            },
            "summary": {},
            "materializedRows": [],
            "safety": safety_policy(),
            "nextActions": ["Run prepare_transition_execution_plan.py after transition grammar planning, then rerun this script."],
        }
        write_json(report_path, report)
        write_markdown(markdown_path, report)
        return report

    rows = plan.get("executionRows") if isinstance(plan.get("executionRows"), list) else []
    rows = [row for row in rows if isinstance(row, dict)]
    candidate = copy.deepcopy(base_blueprint)
    clips = blueprint_clips(candidate)
    satisfied_bridge_rows = bridge_row_indices(package_dir)
    transitions: list[dict[str, Any]] = []
    materialized_rows: list[dict[str, Any]] = []
    rows_with_decisions = 0
    blocked_rows = 0
    motion_rows = 0
    motion_rows_with_evidence = 0
    bridge_required_rows = 0
    bridge_satisfied_rows = 0

    for row in sorted(rows, key=boundary_seconds):
        boundary = boundary_seconds(row)
        row_index = as_int(row.get("rowIndex"), -1)
        requires_bridge = row.get("requiresBridgeInsert") is True
        bridge_satisfied = (not requires_bridge) or row_index in satisfied_bridge_rows
        payload = transition_payload(row, fps=fps, boundary=boundary, bridge_satisfied=bridge_satisfied)
        transitions.append(payload)

        from_index = select_clip_index(clips, row.get("fromClip") if isinstance(row.get("fromClip"), dict) else {}, boundary, side="from")
        to_index = select_clip_index(clips, row.get("toClip") if isinstance(row.get("toClip"), dict) else {}, boundary, side="to")
        clip_refs = {"fromClipIndex": from_index, "toClipIndex": to_index}
        if from_index is not None:
            clips[from_index].setdefault("transitionExecutionOut", []).append({**payload, **clip_refs})
        if to_index is not None:
            clips[to_index].setdefault("transitionExecutionIn", []).append({**payload, **clip_refs})

        decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
        if set(DECISION_FIELDS).issubset(set(decision)):
            rows_with_decisions += 1
        if payload.get("motionStyle"):
            motion_rows += 1
            if payload.get("motionHasEvidence"):
                motion_rows_with_evidence += 1
        if requires_bridge:
            bridge_required_rows += 1
            if bridge_satisfied:
                bridge_satisfied_rows += 1
        row_blocked = (
            row.get("status") != "ready_with_transition_execution_recipe"
            or not bridge_satisfied
            or bool(payload.get("forbiddenRecipeHits"))
            or (payload.get("motionStyle") and not payload.get("motionHasEvidence"))
        )
        if row_blocked:
            blocked_rows += 1
        materialized_rows.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "materialized" if not row_blocked else "needs_transition_execution_blueprint_repair",
                "boundarySeconds": round3(boundary),
                "resolveEffectName": payload.get("resolveEffectName"),
                "approvedTransitionType": payload.get("approvedTransitionType"),
                "durationFrames": payload.get("durationFrames"),
                "fromClipMatched": from_index is not None,
                "toClipMatched": to_index is not None,
                "requiresBridgeInsert": requires_bridge,
                "bridgeSequenceSatisfied": bridge_satisfied,
                "motionStyle": payload.get("motionStyle"),
                "motionHasEvidence": payload.get("motionHasEvidence"),
                "forbiddenRecipeHits": payload.get("forbiddenRecipeHits"),
                "decision": dict(DECISION_FIELDS),
            }
        )

    candidate["clips"] = clips
    candidate["transitions"] = transitions
    candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    candidate["transitionExecutionBlueprintPlan"] = {
        "status": "candidate_not_applied_to_resolve",
        "createdAt": candidate["updatedAt"],
        "baseBlueprint": str(base_path),
        "baseBlueprintKind": base_kind,
        "sourceTransitionExecutionPlan": str(plan_path),
        "report": str(report_path),
        "candidateBlueprint": str(candidate_path),
        "fps": fps,
        "defaultBehavior": "writes a separate candidate blueprint and leaves the active blueprint untouched",
    }
    candidate.setdefault("timelineMarkers", [])
    if isinstance(candidate["timelineMarkers"], list):
        for transition in transitions:
            candidate["timelineMarkers"].append(
                {
                    "startSeconds": transition["boundarySeconds"],
                    "durationSeconds": max(0.25, transition["durationSeconds"]),
                    "color": "Purple",
                    "name": f"Transition Execution {transition.get('rowIndex')}",
                    "note": f"{transition.get('approvedTransitionType')} -> {transition.get('resolveEffectName')}",
                    "role": "transition_execution_candidate_marker",
                    "payload": {
                        "rowIndex": transition.get("rowIndex"),
                        "resolveEffectName": transition.get("resolveEffectName"),
                        "durationFrames": transition.get("durationFrames"),
                    },
                }
            )
        candidate["timelineMarkers"] = sorted(candidate["timelineMarkers"], key=lambda item: (float(item.get("startSeconds") or 0.0), str(item.get("role") or "")))

    rows_missing_clip_match = sum(1 for row in materialized_rows if not row.get("fromClipMatched") or not row.get("toClipMatched"))
    status = "ready_with_transition_execution_blueprint" if rows and not blocked_rows and not rows_missing_clip_match else "needs_transition_execution_blueprint_repair"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "baseBlueprint": str(base_path),
            "baseBlueprintKind": base_kind,
            "transitionExecutionPlan": str(plan_path),
            "bridgeSequenceBlueprintRowsSatisfied": sorted(satisfied_bridge_rows),
        },
        "outputs": {
            "candidateBlueprint": str(candidate_path),
            "reportJson": str(report_path),
            "reportMarkdown": str(markdown_path),
            "activeBlueprintUpdated": bool(update_blueprint),
        },
        "summary": {
            "executionRowCount": len(rows),
            "materializedTransitionCount": len(transitions),
            "rowsWithDecisionFields": rows_with_decisions,
            "blockedRowCount": blocked_rows,
            "rowsMissingClipMatch": rows_missing_clip_match,
            "motionEffectRowCount": motion_rows,
            "motionEffectRowsWithEvidence": motion_rows_with_evidence,
            "bridgeRequiredRowCount": bridge_required_rows,
            "bridgeSatisfiedRowCount": bridge_satisfied_rows,
            "candidateClipCount": len(clips),
            "candidateTransitionCount": len(transitions),
        },
        "materializedRows": materialized_rows,
        "selectionRubric": {
            "pass": [
                "Every transition execution row becomes a candidate transition object in the blueprint.",
                "Adjacent source clips are annotated with in/out transition execution metadata.",
                "Motion effects are present only when the execution plan recorded route or two-sided motion evidence.",
                "Bridge-required transitions are not marked ready until bridge sequence rows are materialized.",
            ],
            "reject": [
                "Transition recipes remain prose-only and do not appear in the candidate blueprint.",
                "A random spin, flash, glitch, shake, or template effect appears in a candidate row.",
                "A bridge-required row is marked ready without a materialized bridge sequence.",
                "The script writes Resolve, queues render, downloads assets, or mutates source footage.",
            ],
        },
        "safety": safety_policy(),
        "nextActions": [
            f"Run audit_resolve_blueprint.py --blueprint {candidate_path} --package-dir {package_dir} before using this candidate.",
            "Review transition_execution_blueprint_report.json and fill decision.approveCandidateBlueprint before Resolve apply.",
            "If approved, use a package fork or explicit --update-blueprint path so stale final QA is not reused.",
        ],
    }

    write_json(candidate_path, candidate)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    if update_blueprint:
        active_path = package_dir / "resolve_timeline_blueprint.json"
        active_blueprint = load_json(active_path) or {}
        backup = package_dir / f"resolve_timeline_blueprint.before_transition_execution_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        write_json(backup, active_blueprint)
        write_json(active_path, candidate)
        report["outputs"]["activeBlueprintBackup"] = str(backup)
        write_json(report_path, report)
        write_markdown(markdown_path, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Execution Blueprint Report",
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
        "## Materialized Rows",
    ]
    for row in report.get("materializedRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('approvedTransitionType')}",
                f"- Status: `{row.get('status')}`",
                f"- Boundary: {row.get('boundarySeconds')}s",
                f"- Resolve effect: `{row.get('resolveEffectName')}`",
                f"- Duration: {row.get('durationFrames')} frames",
                f"- Clip match: from={row.get('fromClipMatched')} to={row.get('toClipMatched')}",
                f"- Bridge satisfied: {row.get('bridgeSequenceSatisfied')}",
                f"- Motion evidence: {row.get('motionStyle')} / {row.get('motionHasEvidence')}",
            ]
        )
        if row.get("forbiddenRecipeHits"):
            lines.append(f"- Forbidden hits: `{', '.join(row.get('forbiddenRecipeHits') or [])}`")
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a transition-execution Resolve blueprint candidate.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--fps", type=float, default=30.0, help="Timeline frame rate used to convert duration frames. Default: 30.")
    parser.add_argument("--update-blueprint", action="store_true", help="Replace the active blueprint after writing a backup. Default is non-destructive.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_candidate(Path(args.package_dir), fps=max(args.fps, 1.0), update_blueprint=args.update_blueprint)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report.get("status"), **(report.get("summary") or {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
