#!/usr/bin/env python3
"""Prepare a media-root decision packet for mounted travel drives."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from discover_external_media import DEFAULT_TERMS, discover
from project_discovery import (
    artifact_count,
    discover_app_and_project,
    infer_region,
    load_json_safe,
    project_media_stats,
    project_region_status,
    select_project,
)


DEFAULT_APP_DIR = Path("/Users/pengyang/Pictures/Video-make/video-claw-studio")


def normalize_path(value: str | Path) -> str:
    try:
        return str(Path(value).expanduser().resolve())
    except Exception:  # noqa: BLE001
        return str(value)


def slug(value: str) -> str:
    out = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return out[:80] or "choice"


def load_project_row(project_dir: Path, candidate_paths: set[str]) -> dict[str, Any]:
    project = load_json_safe(project_dir / "project.json")
    project = project if isinstance(project, dict) else {}
    roots = project.get("mediaRoots") if isinstance(project.get("mediaRoots"), list) else []
    normalized_roots = [normalize_path(root) for root in roots if isinstance(root, str)]
    matched_roots = [root for root in normalized_roots if root in candidate_paths]
    region = project_region_status(project_dir)
    stats = project_media_stats(project_dir)
    return {
        "projectName": project_dir.name,
        "projectDir": str(project_dir),
        "title": project.get("title") or project.get("projectName"),
        "destination": project.get("destination"),
        "mediaRoots": normalized_roots,
        "matchedExternalRoots": matched_roots,
        "region": region,
        "mediaStats": stats,
        "artifactCount": artifact_count(project_dir),
    }


def candidate_region(row: dict[str, Any]) -> str | None:
    text = " ".join([str(row.get("path") or ""), " ".join(row.get("matchedTerms") or [])]).lower()
    return infer_region(text)


def matching_projects(candidate: dict[str, Any], projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_path = normalize_path(candidate["path"])
    return [
        project
        for project in projects
        if candidate_path in project.get("matchedExternalRoots", [])
    ]


def choice_status(candidate: dict[str, Any], matches: list[dict[str, Any]]) -> str:
    region = candidate_region(candidate)
    if not region:
        return "needs_identification"
    if not matches:
        return "needs_project_creation_or_import"
    if any(match.get("region", {}).get("mismatch") for match in matches):
        return "project_metadata_mismatch"
    return "ready_for_project_workflow"


def build_choice(candidate: dict[str, Any], projects: list[dict[str, Any]], app_dir: Path, target_minutes: float) -> dict[str, Any]:
    matches = matching_projects(candidate, projects)
    region = candidate_region(candidate)
    primary = matches[0] if matches else None
    choice_id = slug(f"{region or 'unknown'}-{Path(candidate['path']).name}")
    row = {
        "choiceId": choice_id,
        "status": choice_status(candidate, matches),
        "region": region,
        "sourceRoot": normalize_path(candidate["path"]),
        "videoCount": candidate.get("directVideoCount"),
        "sizeGB": candidate.get("directVideoSizeGB"),
        "matchedTerms": candidate.get("matchedTerms") or [],
        "ignoredAppleDoubleVideoCount": candidate.get("ignoredAppleDoubleVideoCount", 0),
        "sampleVideos": candidate.get("sampleVideos") or [],
        "matchingProjects": matches,
        "recommendedProjectName": primary.get("projectName") if primary else None,
        "nextCommands": [],
    }
    if primary:
        project_name = primary["projectName"]
        row["nextCommands"] = [
            f"python3 <skill-dir>/scripts/check_project_state.py --project-dir {app_dir} --project-name {project_name}",
            f"python3 <skill-dir>/scripts/run_delivery_workflow.py --project-dir {app_dir} --project-name {project_name} --target-duration-minutes {target_minutes:g}",
        ]
    else:
        row["nextCommands"] = [
            "Create or select a VideoClaw project whose mediaRoots points at this sourceRoot, then rerun this intake packet.",
        ]
    return row


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# External Media Intake",
        "",
        f"Status: `{report['status']}`",
        f"App dir: `{report['appDir']}`",
        f"Volume root: `{report['volumeRoot']}`",
        f"Default selected project: `{(report.get('defaultSelectedProject') or {}).get('projectName')}`",
        "",
        "## Recommended Choices",
        "",
    ]
    for choice in report["recommendedChoices"]:
        lines += [
            f"### {choice['choiceId']}",
            "",
            f"- Status: `{choice['status']}`",
            f"- Region: `{choice.get('region')}`",
            f"- Source root: `{choice['sourceRoot']}`",
            f"- Videos: `{choice['videoCount']}`",
            f"- Size GB: `{choice['sizeGB']}`",
            f"- Matching project: `{choice.get('recommendedProjectName')}`",
            f"- Ignored AppleDouble files: `{choice.get('ignoredAppleDoubleVideoCount')}`",
            "",
            "Next commands:",
        ]
        for command in choice.get("nextCommands") or []:
            lines.append(f"- `{command}`")
        if choice.get("sampleVideos"):
            lines += ["", "Sample videos:"]
            lines += [f"- `{sample}`" for sample in choice["sampleVideos"][:6]]
        lines.append("")
    if report.get("blockers"):
        lines += ["## Blockers", ""]
        lines += [f"- {item}" for item in report["blockers"]]
        lines.append("")
    if report.get("warnings"):
        lines += ["## Warnings", ""]
        lines += [f"- {item}" for item in report["warnings"]]
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    app_dir, selected_project, projects = discover_app_and_project(Path(args.project_dir), args.project_name)
    if not selected_project and projects:
        selected_project = select_project(projects)
    discovery = discover(
        Path(args.volume_root).expanduser().resolve(),
        args.max_depth,
        args.min_videos,
        args.sample_limit,
        DEFAULT_TERMS,
    )
    candidate_paths = {normalize_path(row["path"]) for row in discovery.get("likelyTravelRoots") or []}
    project_rows = [load_project_row(project, candidate_paths) for project in projects]
    default_row = load_project_row(selected_project, candidate_paths) if selected_project else None
    choices = [
        build_choice(candidate, project_rows, app_dir, args.target_duration_minutes)
        for candidate in discovery.get("likelyTravelRoots") or []
    ]
    blockers = []
    warnings = []
    if not choices:
        blockers.append("No likely travel media roots found on the mounted volume root.")
    if default_row and default_row.get("region", {}).get("mismatch"):
        blockers.append(
            "Default selected project has a project/media region mismatch; use an explicit project choice before final cutting."
        )
    if len([choice for choice in choices if choice.get("region")]) > 1:
        warnings.append("Multiple trip regions are present on the mounted drive; choose one project/media root explicitly.")
    for choice in choices:
        if choice["status"] != "ready_for_project_workflow":
            warnings.append(f"{choice['choiceId']} is `{choice['status']}`.")
    status = "ready_for_project_choice" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "appDir": str(app_dir),
        "volumeRoot": str(Path(args.volume_root).expanduser().resolve()),
        "defaultSelectedProject": default_row,
        "projectCount": len(project_rows),
        "projects": project_rows,
        "externalDiscovery": discovery,
        "recommendedChoices": choices,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "writesProjectConfig": False,
            "writesResolve": False,
            "downloadsExternalAssets": False,
            "modifiesSourceDrive": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an external-drive media intake decision packet.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app dir or project dir.")
    parser.add_argument("--project-name", help="Optional explicit project name.")
    parser.add_argument("--volume-root", default="/Volumes", help="Mounted drive or /Volumes root.")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--min-videos", type=int, default=20)
    parser.add_argument("--sample-limit", type=int, default=6)
    parser.add_argument("--target-duration-minutes", type=float, default=20.0)
    parser.add_argument("--output-dir", help="Output directory. Defaults to <app>/external_media_intake/<timestamp>.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    app_dir = Path(report["appDir"])
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else app_dir / "external_media_intake" / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "external_media_intake.json"
    md_path = output_dir / "external_media_intake.md"
    report["intakeJson"] = str(json_path)
    report["intakeMarkdown"] = str(md_path)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(md_path, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"External media intake: {report['status']}")
        print(f"Report: {md_path}")
        for choice in report["recommendedChoices"]:
            print(f"- {choice['choiceId']}: {choice['status']} -> {choice.get('recommendedProjectName')}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
