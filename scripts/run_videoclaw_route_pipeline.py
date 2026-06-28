#!/usr/bin/env python3
"""Run the VideoClaw local route pipeline with cloud calls disabled by default."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from project_discovery import discover_app_and_project


DEFAULT_APP_DIR = Path("/Users/pengyang/Pictures/Video-make/video-claw-studio")


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


def summarize_steps(result: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for step in result.get("steps") or []:
        if not isinstance(step, dict):
            continue
        out.append(
            {
                "id": step.get("id"),
                "ok": step.get("ok"),
                "error": step.get("error"),
                "summary": step.get("summary") or {},
                "files": step.get("files") or {},
            }
        )
    return out


def build_payload(args: argparse.Namespace, project_dir: Path) -> dict[str, Any]:
    max_analysis_videos = args.max_analysis_videos
    max_cloud_videos = args.max_cloud_videos
    max_cloud_frames = args.max_cloud_frames
    if args.client_full_recognition:
        max_analysis_videos = max(max_analysis_videos, 120)
        max_cloud_videos = max(max_cloud_videos, 80)
        max_cloud_frames = max(max_cloud_frames, 300)
    return {
        "projectDir": str(project_dir),
        "dryRun": not args.allow_cloud_call,
        "allowCloudCall": bool(args.allow_cloud_call),
        "clientFullRecognition": bool(args.client_full_recognition),
        "includeRouteAwareDraft": not args.skip_route_aware_draft,
        "includeVideoBrain": not args.skip_video_brain,
        "includeEDL": not args.skip_edl,
        "maxAnalysisVideos": max_analysis_videos,
        "framesPerVideo": args.frames_per_video,
        "frameWidth": args.frame_width,
        "maxOutputMB": args.max_output_mb,
        "maxCloudVideos": max_cloud_videos,
        "maxCloudFrames": max_cloud_frames,
        "cloudProviderId": args.cloud_provider_id,
        "localProviderId": args.local_provider_id,
        "cloudBudget": {"maxFrames": max_cloud_frames},
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    app_dir, selected_project, _projects = discover_app_and_project(Path(args.project_dir), args.project_name)
    if not selected_project:
        raise SystemExit("No VideoClaw project selected.")
    server = load_videoclaw_server(app_dir)
    result = server.run_location_route_pipeline(build_payload(args, selected_project))
    return {
        "status": "completed_with_errors" if result.get("errors") else "completed",
        "appDir": str(app_dir),
        "projectDir": str(selected_project),
        "projectName": selected_project.name,
        "allowCloudCall": bool(args.allow_cloud_call),
        "cloudProviderUsed": result.get("cloudProviderUsed"),
        "localModelUsed": result.get("localModelUsed"),
        "providerWarnings": result.get("providerWarnings") or [],
        "projectWarnings": result.get("projectWarnings") or [],
        "steps": summarize_steps(result),
        "errors": result.get("errors") or [],
        "finalFiles": result.get("finalFiles") or result.get("files") or {},
        "summary": result.get("summary") or {},
        "safety": {
            "modifiesSourceDrive": False,
            "writesProjectArtifacts": True,
            "writesResolve": False,
            "externalCloudCalls": bool(args.allow_cloud_call),
        },
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"Route pipeline status: {report['status']}")
    print(f"Project: {report['projectName']}")
    print(f"Cloud calls: {report['allowCloudCall']}")
    print(f"Local model used: {report.get('localModelUsed')}")
    for step in report.get("steps") or []:
        suffix = f" error={step.get('error')}" if step.get("error") else ""
        print(f"- {step.get('id')}: ok={step.get('ok')}{suffix}")
    for warning in report.get("providerWarnings") or []:
        print(f"WARNING: {warning}")
    for warning in report.get("projectWarnings") or []:
        print(f"WARNING: {warning}")
    for error in report.get("errors") or []:
        print(f"ERROR: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VideoClaw location/route pipeline safely.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app dir or project dir.")
    parser.add_argument("--project-name", help="Optional project name when --project-dir points at the app.")
    parser.add_argument("--max-analysis-videos", type=int, default=60)
    parser.add_argument("--frames-per-video", type=int, default=4)
    parser.add_argument("--frame-width", type=int, default=720)
    parser.add_argument("--max-output-mb", type=float, default=160.0)
    parser.add_argument("--max-cloud-videos", type=int, default=60)
    parser.add_argument("--max-cloud-frames", type=int, default=160)
    parser.add_argument(
        "--client-full-recognition",
        action="store_true",
        help="Client delivery mode: extract/recognize across the full video set instead of accepting prefilter sampling.",
    )
    parser.add_argument("--cloud-provider-id", default="openai-compatible")
    parser.add_argument("--local-provider-id", default="ollama-local")
    parser.add_argument("--allow-cloud-call", action="store_true", help="Allow real cloud location recognition API calls.")
    parser.add_argument("--skip-route-aware-draft", action="store_true")
    parser.add_argument("--skip-video-brain", action="store_true")
    parser.add_argument("--skip-edl", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 2 if report["status"] == "completed_with_errors" else 0


if __name__ == "__main__":
    raise SystemExit(main())
