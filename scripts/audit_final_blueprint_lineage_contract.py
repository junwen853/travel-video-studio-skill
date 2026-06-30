#!/usr/bin/env python3
"""Audit whether the final Resolve blueprint inherits the latest candidate chain."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


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


def resolve_path(package_dir: Path, raw: Any) -> Path:
    path = Path(str(raw or "")).expanduser()
    if not path.is_absolute():
        path = (package_dir / path).resolve()
    return path


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def transitions(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def count_bridge_inserts(blueprint: dict[str, Any]) -> int:
    total = 0
    for clip in clips(blueprint):
        payload = clip.get("bridgeSequence") if isinstance(clip.get("bridgeSequence"), dict) else {}
        text = " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "sourcePath", "sourceName")).lower()
        if clip.get("role") == "bridge_sequence_insert" or payload.get("kind") == "bridge_sequence_insert" or "bridge sequence beat" in text:
            total += 1
    return total


def count_transition_execution(blueprint: dict[str, Any]) -> int:
    total = len(transitions(blueprint))
    if total:
        return total
    for clip in clips(blueprint):
        total += len(clip.get("transitionExecutionOut") if isinstance(clip.get("transitionExecutionOut"), list) else [])
        total += len(clip.get("transitionExecutionIn") if isinstance(clip.get("transitionExecutionIn"), list) else [])
    return total


def count_top_level_list(key: str) -> Callable[[dict[str, Any]], int]:
    def _count(blueprint: dict[str, Any]) -> int:
        rows = blueprint.get(key) if isinstance(blueprint.get(key), list) else []
        return len([row for row in rows if isinstance(row, dict)])

    return _count


def count_clip_annotations(key: str) -> Callable[[dict[str, Any]], int]:
    def _count(blueprint: dict[str, Any]) -> int:
        total = 0
        total += count_top_level_list(key)(blueprint)
        for clip in clips(blueprint):
            total += len(clip.get(key) if isinstance(clip.get(key), list) else [])
        return total

    return _count


def count_rhythm_recut(blueprint: dict[str, Any]) -> int:
    return len([clip for clip in clips(blueprint) if isinstance(clip.get("rhythmRecut"), dict)])


STAGES: list[dict[str, Any]] = [
    {
        "id": "bridge_sequence_blueprint",
        "report": ("bridge_sequence_blueprint", "bridge_sequence_blueprint_report.json"),
        "readyStatuses": {"ready_with_bridge_sequence_blueprint"},
        "planKey": "bridgeSequenceBlueprintPlan",
        "countLabel": "bridgeSequenceInsertClips",
        "summaryKeys": ("insertedBeatClipCount",),
        "finalCount": count_bridge_inserts,
    },
    {
        "id": "transition_execution_blueprint",
        "report": ("transition_execution_blueprint", "transition_execution_blueprint_report.json"),
        "readyStatuses": {"ready_with_transition_execution_blueprint"},
        "planKey": "transitionExecutionBlueprintPlan",
        "countLabel": "transitionExecutionRows",
        "summaryKeys": ("materializedTransitionCount", "executionRowCount"),
        "finalCount": count_transition_execution,
    },
    {
        "id": "effect_motion_blueprint",
        "report": ("effect_motion_blueprint", "effect_motion_blueprint_report.json"),
        "readyStatuses": {"ready_with_effect_motion_blueprint"},
        "planKey": "effectMotionBlueprintPlan",
        "countLabel": "effectMotionCandidates",
        "summaryKeys": ("materializedEffectCount", "candidateEffectMotionCount", "effectRowCount"),
        "finalCount": count_clip_annotations("effectMotionCandidates"),
    },
    {
        "id": "bgm_phrase_blueprint",
        "report": ("bgm_phrase_blueprint", "bgm_phrase_blueprint_report.json"),
        "readyStatuses": {"ready_with_bgm_phrase_blueprint"},
        "planKey": "bgmPhraseBlueprintPlan",
        "countLabel": "bgmPhraseCandidates",
        "summaryKeys": ("materializedPhraseCount", "phraseRowCount"),
        "finalCount": count_clip_annotations("bgmPhraseCandidates"),
    },
    {
        "id": "rhythm_recut_blueprint",
        "report": ("rhythm_recut_blueprint", "rhythm_recut_blueprint_report.json"),
        "readyStatuses": {"ready_with_rhythm_recut_blueprint", "ready_no_recut_needed"},
        "planKey": "rhythmRecutPlan",
        "countLabel": "rhythmRecutClipAnnotations",
        "summaryKeys": ("cutawayInsertCount", "splitSourceClipCount"),
        "finalCount": count_rhythm_recut,
        "allowZeroForStatus": {"ready_no_recut_needed"},
    },
    {
        "id": "transition_polish_blueprint",
        "report": ("transition_polish_blueprint", "transition_polish_blueprint_report.json"),
        "readyStatuses": {"ready_with_transition_polish_blueprint"},
        "planKey": "transitionPolishBlueprintPlan",
        "countLabel": "transitionPolishCandidates",
        "summaryKeys": ("polishedTransitionCount", "transitionRowCount"),
        "finalCount": count_top_level_list("transitionPolishCandidates"),
    },
]


def stage_report_path(package_dir: Path, spec: dict[str, Any]) -> Path:
    return package_dir.joinpath(*spec["report"])


def candidate_path_from_report(package_dir: Path, report: dict[str, Any]) -> Path | None:
    outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
    raw = outputs.get("candidateBlueprint")
    return resolve_path(package_dir, raw) if raw else None


def source_count(report: dict[str, Any], spec: dict[str, Any]) -> int:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    values = [as_int(summary.get(key), 0) for key in spec.get("summaryKeys", ())]
    return max(values) if values else 0


def plan_path_issues(package_dir: Path, plan: dict[str, Any], candidate_path: Path | None) -> list[str]:
    issues: list[str] = []
    for key in ("candidateBlueprint", "report"):
        raw = plan.get(key)
        if not raw:
            issues.append(f"plan_missing_{key}")
            continue
        path = resolve_path(package_dir, raw)
        if not is_inside(path, package_dir):
            issues.append(f"plan_{key}_outside_package")
        if key == "candidateBlueprint" and candidate_path and path.name != candidate_path.name:
            issues.append("plan_candidate_blueprint_differs_from_latest_report")
    return issues


def audit_stage(package_dir: Path, final: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    report_path = stage_report_path(package_dir, spec)
    report = load_json(report_path)
    if not isinstance(report, dict):
        return {
            "stage": spec["id"],
            "status": "missing",
            "report": str(report_path),
            "reportExists": report_path.exists(),
            "ready": False,
            "issues": ["stage_report_missing_or_unreadable"],
        }
    status = str(report.get("status") or "")
    ready = status in spec["readyStatuses"]
    candidate_path = candidate_path_from_report(package_dir, report)
    candidate_exists = bool(candidate_path and candidate_path.exists())
    candidate_inside = bool(candidate_path and is_inside(candidate_path, package_dir))
    plan = final.get(spec["planKey"]) if isinstance(final.get(spec["planKey"]), dict) else {}
    expected_count = source_count(report, spec)
    final_count = int(spec["finalCount"](final))
    allow_zero = status in spec.get("allowZeroForStatus", set())
    issues: list[str] = []
    if not ready:
        issues.append(f"stage_report_not_ready:{status}")
    if not candidate_path:
        issues.append("candidate_blueprint_missing_from_report_outputs")
    elif not candidate_exists:
        issues.append("candidate_blueprint_file_missing")
    elif not candidate_inside:
        issues.append("candidate_blueprint_outside_package")
    if not plan:
        issues.append(f"final_blueprint_missing_{spec['planKey']}")
    else:
        issues.extend(plan_path_issues(package_dir, plan, candidate_path))
    if expected_count <= 0 and not allow_zero:
        issues.append("stage_report_has_no_materialized_rows")
    if expected_count > 0 and final_count < expected_count:
        issues.append(f"final_blueprint_dropped_{spec['countLabel']}:{final_count}/{expected_count}")
    return {
        "stage": spec["id"],
        "status": "passed" if ready and not issues else "blocked",
        "reportStatus": status,
        "report": str(report_path),
        "reportExists": report_path.exists(),
        "ready": ready,
        "candidateBlueprint": str(candidate_path) if candidate_path else None,
        "candidateBlueprintExists": candidate_exists,
        "candidateBlueprintInsidePackage": candidate_inside,
        "planKey": spec["planKey"],
        "finalHasPlanKey": bool(plan),
        "sourceCount": expected_count,
        "finalCount": final_count,
        "countLabel": spec["countLabel"],
        "issues": issues,
    }


def final_blueprint_path(package_dir: Path, explicit: str | None) -> tuple[Path, str]:
    if explicit:
        return resolve_path(package_dir, explicit), "explicit_blueprint"
    return package_dir / "resolve_timeline_blueprint.json", "active_blueprint"


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    final_path, final_kind = final_blueprint_path(package_dir, args.blueprint)
    final = load_json(final_path)
    if not isinstance(final, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "finalBlueprint": str(final_path),
                "finalBlueprintExists": final_path.exists(),
                "finalBlueprintKind": final_kind,
                "finalBlueprintInsidePackage": is_inside(final_path, package_dir),
                "minimumReadyStages": args.minimum_ready_stages,
            },
            "summary": {},
            "stages": [],
            "blockers": [f"missing or unreadable final blueprint: {final_path}"],
            "warnings": [],
            "safety": safety(),
        }
    stages = [audit_stage(package_dir, final, spec) for spec in STAGES]
    ready = [row for row in stages if row.get("ready")]
    passed = [row for row in stages if row.get("status") == "passed"]
    blocked = [row for row in stages if row.get("ready") and row.get("status") != "passed"]
    non_ready_existing = [
        row for row in stages
        if row.get("reportExists") and not row.get("ready") and "stage_report_not_ready" in " ".join(row.get("issues") or [])
    ]
    blockers: list[str] = []
    warnings: list[str] = []
    if not is_inside(final_path, package_dir):
        blockers.append(f"final blueprint is outside package: {final_path}")
    if len(ready) < args.minimum_ready_stages:
        blockers.append(f"not enough ready candidate blueprint stages: {len(ready)}/{args.minimum_ready_stages}")
    for row in blocked[:80]:
        blockers.append(f"{row['stage']}: {', '.join(row.get('issues') or [])}")
    for row in non_ready_existing[:40]:
        warnings.append(f"{row['stage']} exists but is not ready: {row.get('reportStatus')}")
    status = "passed" if not blockers and len(passed) >= args.minimum_ready_stages else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "finalBlueprint": str(final_path),
            "finalBlueprintExists": final_path.exists(),
            "finalBlueprintKind": final_kind,
            "finalBlueprintInsidePackage": is_inside(final_path, package_dir),
            "minimumReadyStages": args.minimum_ready_stages,
        },
        "summary": {
            "configuredStageCount": len(STAGES),
            "readyStageCount": len(ready),
            "passedStageCount": len(passed),
            "blockedReadyStageCount": len(blocked),
            "nonReadyExistingStageCount": len(non_ready_existing),
            "requiredMinimumReadyStages": args.minimum_ready_stages,
            "finalPlanKeyCount": sum(1 for spec in STAGES if isinstance(final.get(spec["planKey"]), dict)),
            "blockerCount": len(blockers),
        },
        "stages": stages,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Final Blueprint Lineage Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Final blueprint: `{report['inputs'].get('finalBlueprint')}`",
        f"Final blueprint kind: `{report['inputs'].get('finalBlueprintKind')}`",
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
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Stages"])
    for row in report.get("stages") or []:
        lines.extend(
            [
                "",
                f"### {row.get('stage')}",
                f"- Status: `{row.get('status')}`",
                f"- Report status: `{row.get('reportStatus')}`",
                f"- Plan key: `{row.get('planKey')}` present=`{row.get('finalHasPlanKey')}`",
                f"- Candidate: `{row.get('candidateBlueprint')}`",
                f"- Count: `{row.get('finalCount')}/{row.get('sourceCount')}` {row.get('countLabel')}",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final Resolve blueprint candidate-chain lineage.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--minimum-ready-stages", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "final_blueprint_lineage_contract_audit.json", report)
    write_markdown(package_dir / "final_blueprint_lineage_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
