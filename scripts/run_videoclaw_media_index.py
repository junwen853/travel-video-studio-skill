#!/usr/bin/env python3
"""Dry-run or write a VideoClaw Studio media index for a selected project."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from project_discovery import default_app_dir, discover_app_and_project, load_json_safe


DEFAULT_APP_DIR = default_app_dir()


def load_videoclaw_server(app_dir: Path) -> Any:
    server_path = app_dir / "server.py"
    if not server_path.exists():
        raise SystemExit(f"VideoClaw server.py not found under app dir: {app_dir}")
    spec = importlib.util.spec_from_file_location("videoclaw_server_runtime", server_path)
    if not spec or not spec.loader:
        raise SystemExit(f"Unable to load VideoClaw server.py: {server_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summarize_scan(scan: dict[str, Any]) -> dict[str, Any]:
    files = scan.get("files") if isinstance(scan.get("files"), list) else []
    videos = [item for item in files if isinstance(item, dict) and item.get("kind") == "video"]
    return {
        "fileCount": scan.get("fileCount"),
        "scannedCount": scan.get("scannedCount"),
        "videoCount": scan.get("videoCount"),
        "imageCount": scan.get("imageCount"),
        "totalDuration": scan.get("totalDuration"),
        "totalSize": scan.get("totalSize"),
        "duplicateCount": scan.get("duplicateCount"),
        "hasGPSCount": scan.get("hasGPSCount"),
        "missingRoots": scan.get("missingRoots") or [],
        "mediaTypeCounts": scan.get("mediaTypeCounts") or {},
        "sampleVideos": [item.get("path") for item in videos[:6] if item.get("path")],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    app_dir, selected_project, _projects = discover_app_and_project(Path(args.project_dir), args.project_name)
    if not selected_project:
        raise SystemExit("No VideoClaw project selected.")
    server = load_videoclaw_server(app_dir)
    project_data = load_json_safe(selected_project / "project.json")
    project_data = project_data if isinstance(project_data, dict) else {}
    media_roots = project_data.get("mediaRoots") if isinstance(project_data.get("mediaRoots"), list) else []
    if not media_roots:
        raise SystemExit(f"Selected project has no mediaRoots: {selected_project}")

    if args.apply:
        result = server.run_media_index(
            {
                "projectDir": str(selected_project),
                "project": project_data,
                "mediaRoots": media_roots,
                "maxFiles": args.max_files,
            }
        )
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        scan_data = load_json_safe(selected_project / "scan.json")
        scan_data = scan_data if isinstance(scan_data, dict) else {}
        missing_roots = scan_data.get("missingRoots") or summary.get("missingRoots") or []
        outputs = result.get("files") if isinstance(result.get("files"), dict) else {}
    else:
        scan = server.scan_media_roots(media_roots, max_files=args.max_files)
        summary = summarize_scan(scan)
        missing_roots = summary.get("missingRoots") or []
        outputs = {}

    video_count = int(summary.get("videoCount") or 0)
    blockers = []
    if missing_roots:
        blockers.append("At least one media root is missing; reconnect the source drive or fix project.json mediaRoots.")
    if video_count <= 0:
        blockers.append("No videos were found under the selected media roots.")
    status = "blocked" if blockers else ("media_index_written" if args.apply else "ready_to_apply_media_index")
    return {
        "status": status,
        "appDir": str(app_dir),
        "projectDir": str(selected_project),
        "projectName": selected_project.name,
        "mediaRoots": media_roots,
        "apply": bool(args.apply),
        "maxFiles": args.max_files,
        "summary": summary,
        "outputs": outputs,
        "blockers": blockers,
        "safety": {
            "modifiesSourceDrive": False,
            "writesProjectArtifacts": bool(args.apply),
            "writesResolve": False,
            "externalCloudCalls": False,
        },
    }


def print_human(report: dict[str, Any]) -> None:
    summary = report.get("summary") or {}
    print(f"Media index status: {report['status']}")
    print(f"Project: {report['projectName']}")
    print(f"Videos: {summary.get('videoCount')}")
    print(f"Duration seconds: {summary.get('totalDuration')}")
    print(f"Missing roots: {len(summary.get('missingRoots') or [])}")
    if report.get("outputs"):
        print("Outputs:")
        for key, value in report["outputs"].items():
            print(f"- {key}: {value}")
    for blocker in report.get("blockers") or []:
        print(f"BLOCKER: {blocker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or write VideoClaw media_index.json for a selected project.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app dir or project dir.")
    parser.add_argument("--project-name", help="Optional project name when --project-dir points at the app.")
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--apply", action="store_true", help="Write media_index.json, duplicate_groups.json, and scan.json.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
