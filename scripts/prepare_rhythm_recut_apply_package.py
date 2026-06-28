#!/usr/bin/env python3
"""Fork a package and make the rhythm-recut candidate its active Resolve blueprint."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


COPY_DIRS = [
    "aerial_titles",
    "asset_ledger",
    "asset_sourcing",
    "audio_scene_policy_plan",
    "bgm",
    "bgm_sourcing",
    "caption_story_plan",
    "clean_scenic_title_bridges",
    "edit_rhythm_plan",
    "effect_motion_plan",
    "overlay_video_burnin",
    "rhythm_recut_blueprint",
    "subtitle_overlay_assets",
    "subtitle_overlays_title_safe",
    "title_cards",
    "title_typography_plan",
    "transition_bridge_plan",
    "v8_visual_polish",
    "v9_fix_inputs",
    "visual_establishing_plan",
]

COPY_FILES = [
    "asset_search_plan.md",
    "bgm_cues.md",
    "caption_overlap_fix_report.json",
    "caption_rewrite_report.json",
    "davinci_build_notes.md",
    "delivery_assets_report.json",
    "delivery_assets_report.md",
    "delivery_plan.json",
    "edit_decision_plan.md",
    "long_form_structure.md",
    "narration.txt",
    "narration_text_only_v4.txt",
    "qa_checklist.md",
    "quality_recut_report.json",
    "quality_recut_report.md",
    "resolve_timeline_enrichment.json",
    "subtitles.srt",
    "subtitles_v4_dense.srt",
    "v12_visual_manifest.json",
]

FINAL_EVIDENCE_PREFIXES = (
    "final_qa_suite",
    "render_delivery_verification",
    "render_job_status",
    "visual_audio_style_audit",
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def clean(value: Any) -> str:
    return str(value or "").strip()


def rewrite_paths(value: Any, source_package: Path, output_dir: Path) -> Any:
    if isinstance(value, str):
        source = str(source_package)
        output = str(output_dir)
        if source in value:
            return value.replace(source, output)
        return value
    if isinstance(value, list):
        return [rewrite_paths(item, source_package, output_dir) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_paths(item, source_package, output_dir) for key, item in value.items()}
    return value


def copy_path(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return True


def rewrite_copied_paths(output_dir: Path, source_package: Path, copied_dirs: list[str]) -> list[str]:
    rewritten: list[str] = []
    text_suffixes = {".md", ".srt", ".txt"}
    for rel in copied_dirs:
        root = output_dir / rel
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                if path.suffix.lower() == ".json":
                    data = rewrite_paths(load_json(path), source_package, output_dir)
                    write_json(path, data)
                    rewritten.append(str(path.relative_to(output_dir)))
                elif path.suffix.lower() in text_suffixes:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    updated = text.replace(str(source_package), str(output_dir))
                    if updated != text:
                        write_text(path, updated)
                        rewritten.append(str(path.relative_to(output_dir)))
            except Exception:
                continue
    return rewritten


def default_output_dir(source_package: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return source_package.parent / f"{stamp}_rhythm_recut_apply"


def default_resolve_names(source_package: Path, candidate: dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    base_project = clean(candidate.get("projectName") or source_package.parent.parent.name or "Travel")
    base_timeline = clean(candidate.get("timelineName") or candidate.get("projectName") or source_package.name or "Travel Longform")
    project_name = clean(args.project_name) or f"{base_project} Rhythm Recut"
    timeline_name = clean(args.timeline_name) or f"{base_timeline} Rhythm Recut"
    return project_name, timeline_name


def validate_candidate(candidate_report: dict[str, Any], candidate_blueprint: Path) -> list[str]:
    blockers: list[str] = []
    if candidate_report.get("status") not in {"ready_with_rhythm_recut_blueprint", "ready_no_recut_needed"}:
        blockers.append(f"Candidate report status is not ready: {candidate_report.get('status')}")
    if not candidate_blueprint.exists():
        blockers.append(f"Candidate blueprint missing: {candidate_blueprint}")
    summary = candidate_report.get("summary") if isinstance(candidate_report.get("summary"), dict) else {}
    if candidate_report.get("status") == "ready_with_rhythm_recut_blueprint":
        if int(summary.get("splitSourceClipCount") or 0) <= 0:
            blockers.append("Candidate report has no split source clips.")
        if int(summary.get("cutawayInsertCount") or 0) <= 0:
            blockers.append("Candidate report has no cutaway inserts.")
        if float(summary.get("averagePrimaryShotAfterSeconds") or 0) >= float(summary.get("averagePrimaryShotBeforeSeconds") or 0):
            blockers.append("Candidate report does not improve average primary shot length.")
        if int(summary.get("longShotRiskAfter") or 0) >= int(summary.get("longShotRiskBefore") or 0):
            blockers.append("Candidate report does not reduce long-shot risk.")
    if abs(float(summary.get("durationDeltaSeconds") or 0.0)) > 0.5:
        blockers.append("Candidate duration delta is larger than 0.5 seconds.")
    return blockers


def run_preflight(active_blueprint: Path, output_dir: Path) -> dict[str, Any]:
    script = Path(__file__).with_name("audit_resolve_blueprint.py")
    report_path = output_dir / "resolve_blueprint_preflight.json"
    cmd = [
        "python3",
        str(script),
        "--blueprint",
        str(active_blueprint),
        "--package-dir",
        str(output_dir),
        "--output",
        str(report_path),
        "--json",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    payload = load_json(report_path) or {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "command": cmd,
        "returnCode": result.returncode,
        "stdoutTail": result.stdout[-4000:],
        "stderrTail": result.stderr[-4000:],
        "report": str(report_path),
        "status": payload.get("status"),
        "blockerCount": len(payload.get("blockers") or []),
        "warningCount": len(payload.get("warnings") or []),
    }


def report_status(blockers: list[str], preflight: dict[str, Any] | None) -> str:
    if blockers:
        return "blocked"
    if not preflight:
        return "prepared_pending_preflight"
    if preflight.get("returnCode") != 0:
        return "blocked_preflight_failed"
    if preflight.get("blockerCount"):
        return "blocked_preflight"
    if preflight.get("status") in {"ready", "ready_with_warnings"}:
        return "ready_for_resolve_apply_contract"
    return "needs_preflight_review"


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Rhythm Recut Apply Package",
        "",
        f"Status: `{report['status']}`",
        f"Source package: `{report['sourcePackage']}`",
        f"Output package: `{report['outputPackage']}`",
        f"Active blueprint: `{report['activeBlueprint']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Safety",
        "",
        "```json",
        json.dumps(report.get("safety") or {}, ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    preflight = report.get("preflight")
    if preflight:
        lines.extend(["", "## Preflight", "", "```json", json.dumps(preflight, ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    write_text(path, "\n".join(lines) + "\n")


def prepare_package(args: argparse.Namespace) -> dict[str, Any]:
    source_package = Path(args.source_package).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_output_dir(source_package)
    candidate_report_path = (
        Path(args.candidate_report).expanduser().resolve()
        if args.candidate_report
        else source_package / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json"
    )
    candidate_report = load_json(candidate_report_path) or {}
    outputs = candidate_report.get("outputs") if isinstance(candidate_report.get("outputs"), dict) else {}
    candidate_blueprint = (
        Path(args.candidate_blueprint).expanduser().resolve()
        if args.candidate_blueprint
        else Path(str(outputs.get("candidateBlueprint") or source_package / "rhythm_recut_blueprint" / "resolve_timeline_blueprint_rhythm_recut.json"))
    )
    blockers = validate_candidate(candidate_report, candidate_blueprint)

    if not source_package.exists():
        blockers.append(f"Source package missing: {source_package}")
    if output_dir.exists() and any(output_dir.iterdir()):
        if args.force:
            shutil.rmtree(output_dir)
        else:
            blockers.append(f"Output directory is not empty; pass --force to replace generated files: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_dirs: list[str] = []
    copied_files: list[str] = []
    rewritten_files: list[str] = []
    if not blockers:
        for rel in COPY_DIRS:
            if copy_path(source_package / rel, output_dir / rel):
                copied_dirs.append(rel)
        rewritten_files.extend(rewrite_copied_paths(output_dir, source_package, copied_dirs))
        for rel in COPY_FILES:
            source = source_package / rel
            target = output_dir / rel
            if not source.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() == ".json":
                write_json(target, rewrite_paths(load_json(source), source_package, output_dir))
            else:
                text = source.read_text(encoding="utf-8", errors="ignore")
                write_text(target, text.replace(str(source_package), str(output_dir)))
            copied_files.append(rel)

    candidate = load_json(candidate_blueprint) or {}
    active_blueprint = output_dir / "resolve_timeline_blueprint.json"
    active_snapshot = output_dir / "resolve_timeline_blueprint_rhythm_recut_applied.json"
    project_name, timeline_name = default_resolve_names(source_package, candidate if isinstance(candidate, dict) else {}, args)
    active_clip_count = 0
    if not blockers and isinstance(candidate, dict):
        candidate = rewrite_paths(candidate, source_package, output_dir)
        candidate["projectName"] = project_name
        candidate["timelineName"] = timeline_name
        candidate["outputDir"] = str(output_dir)
        candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        candidate["sourcePackageName"] = source_package.name
        plan = candidate.get("rhythmRecutPlan") if isinstance(candidate.get("rhythmRecutPlan"), dict) else {}
        plan.update(
            {
                "status": "applied_to_package_pending_resolve_apply",
                "sourcePackage": str(source_package),
                "sourceCandidateBlueprint": str(candidate_blueprint),
                "sourceCandidateReport": str(candidate_report_path),
                "activeBlueprint": str(active_blueprint),
                "requiresResolvePreflightBeforeApply": True,
                "writesResolve": False,
            }
        )
        candidate["rhythmRecutPlan"] = plan
        active_clip_count = len(candidate.get("clips") or [])
        write_json(active_blueprint, candidate)
        write_json(active_snapshot, candidate)
    elif not blockers:
        blockers.append(f"Candidate blueprint is not valid JSON: {candidate_blueprint}")

    preflight = run_preflight(active_blueprint, output_dir) if args.run_preflight and not blockers else None
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": report_status(blockers, preflight),
        "sourcePackage": str(source_package),
        "outputPackage": str(output_dir),
        "sourceCandidateReport": str(candidate_report_path),
        "sourceCandidateBlueprint": str(candidate_blueprint),
        "activeBlueprint": str(active_blueprint),
        "activeBlueprintSnapshot": str(active_snapshot),
        "projectName": project_name,
        "timelineName": timeline_name,
        "copiedAssetDirs": copied_dirs,
        "copiedInputFiles": copied_files,
        "rewrittenCopiedFiles": rewritten_files,
        "summary": {
            "sourceCandidateStatus": candidate_report.get("status"),
            "activeClipCount": active_clip_count,
            "sourceCandidateSummary": candidate_report.get("summary") if isinstance(candidate_report.get("summary"), dict) else {},
            "copiedFinalRenderEvidence": False,
        },
        "preflight": preflight,
        "blockers": blockers,
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourcePackageBlueprint": False,
            "copiesFinalRenderEvidence": False,
            "requiresResolveApplyContract": True,
            "requiresReadbackAfterApply": True,
        },
        "nextActions": [
            f"Run build_resolve_timeline.py --blueprint {active_blueprint} --json as a dry-run.",
            f"Run prepare_resolve_apply_contract.py --package-dir {output_dir} before any Resolve write.",
            "Use build_resolve_timeline.py --apply only after explicit approval, then run audit_resolve_timeline.py readback.",
            "Render and rerun final QA; do not reuse the source package final QA as proof for this recut package.",
        ],
    }
    write_json(output_dir / "rhythm_recut_apply_package_report.json", report)
    write_markdown(output_dir / "rhythm_recut_apply_package_report.md", report)

    source_report = source_package / "rhythm_recut_blueprint" / "rhythm_recut_apply_package_report.json"
    source_report_md = source_package / "rhythm_recut_blueprint" / "rhythm_recut_apply_package_report.md"
    write_json(source_report, report)
    write_markdown(source_report_md, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new package whose active blueprint is the approved rhythm-recut candidate.")
    parser.add_argument("--source-package", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--candidate-blueprint")
    parser.add_argument("--candidate-report")
    parser.add_argument("--project-name")
    parser.add_argument("--timeline-name")
    parser.add_argument("--run-preflight", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = prepare_package(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "outputPackage": report["outputPackage"], "activeBlueprint": report["activeBlueprint"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
