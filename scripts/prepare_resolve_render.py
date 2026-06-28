#!/usr/bin/env python3
"""Prepare or queue a DaVinci Resolve render from a delivery package."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from resolve_common import get_resolve


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("._") or "travel_video"


def find_timeline(project: Any, name: str | None) -> Any:
    if not name:
        return project.GetCurrentTimeline()
    for idx in range(1, int(project.GetTimelineCount()) + 1):
        timeline = project.GetTimelineByIndex(idx)
        if timeline and timeline.GetName() == name:
            project.SetCurrentTimeline(timeline)
            return timeline
    return None


def resolve_mapping(value: str, mapping: dict[str, Any]) -> str | None:
    if value in mapping:
        mapped = mapping[value]
        return str(mapped) if mapped else value
    values = {str(v): str(v) for v in mapping.values()}
    if value in values:
        return values[value]
    needle = value.casefold()
    for key, mapped in mapping.items():
        if str(key).casefold() == needle:
            return str(mapped) if mapped else str(key)
        if str(mapped).casefold() == needle:
            return str(mapped)
    return None


def resolve_format_and_codec(project: Any, render_format: str, codec: str) -> tuple[str, str, dict[str, Any]]:
    formats = project.GetRenderFormats() or {}
    resolved_format = resolve_mapping(render_format, formats)
    if not resolved_format:
        raise RuntimeError(f"Render format is not available: {render_format}. Available: {sorted(formats)}")
    codecs = project.GetRenderCodecs(resolved_format) or {}
    resolved_codec = resolve_mapping(codec, codecs)
    if not resolved_codec:
        raise RuntimeError(
            f"Render codec is not available for {resolved_format}: {codec}. "
            f"Available descriptions: {sorted(codecs)}"
        )
    return resolved_format, resolved_codec, {"formats": formats, "codecs": codecs}


def load_package(package_dir: Path) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json")
    delivery_audit = None
    resolve_audit = None
    if (package_dir / "delivery_audit.json").exists():
        delivery_audit = load_json(package_dir / "delivery_audit.json")
    if (package_dir / "resolve_audit.json").exists():
        resolve_audit = load_json(package_dir / "resolve_audit.json")
    return blueprint, delivery_audit, resolve_audit


def build_gate(
    package_dir: Path,
    project_name: str,
    timeline_name: str,
    delivery_audit: dict[str, Any] | None,
    resolve_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not delivery_audit:
        blockers.append("delivery_audit.json is missing. Run audit_delivery_package.py first.")
    else:
        blockers.extend(delivery_audit.get("blockers") or [])
        if delivery_audit.get("assetSummary", {}).get("unverifiedBgmOrStock"):
            blockers.append("BGM/stock/aerial rows are still unverified in the asset ledger.")
        if delivery_audit.get("status") == "blocked":
            blockers.append("delivery_audit.json does not allow final render yet.")
    if not resolve_audit:
        blockers.append("resolve_audit.json is missing. Run audit_resolve_timeline.py after creating the Resolve timeline.")
    else:
        if resolve_audit.get("projectName") != project_name:
            blockers.append(
                f"resolve_audit.json project mismatch: {resolve_audit.get('projectName')} != {project_name}"
            )
        if resolve_audit.get("timelineName") != timeline_name:
            blockers.append(
                f"resolve_audit.json timeline mismatch: {resolve_audit.get('timelineName')} != {timeline_name}"
            )
        if resolve_audit.get("warnings"):
            blockers.extend(f"Resolve audit warning: {item}" for item in resolve_audit["warnings"])
        video_items = sum(row.get("itemCount", 0) for row in resolve_audit.get("tracks", {}).get("video", []))
        if video_items <= 0:
            blockers.append("Resolve audit found no video timeline items.")
    if not (package_dir / "render_plan.json").exists():
        warnings.append("render_plan.json will be created by this command.")
    return {"allowed": not blockers, "blockers": list(dict.fromkeys(blockers)), "warnings": list(dict.fromkeys(warnings))}


def render_settings(args: argparse.Namespace, blueprint: dict[str, Any], target_dir: Path, custom_name: str) -> dict[str, Any]:
    resolution = blueprint.get("resolution") if isinstance(blueprint.get("resolution"), dict) else {}
    width = int(args.width or resolution.get("width") or 3840)
    height = int(args.height or resolution.get("height") or 2160)
    fps = float(args.fps or blueprint.get("fps") or 25)
    video_quality = args.video_quality
    if isinstance(video_quality, str) and video_quality.strip().isdigit():
        video_quality = int(video_quality.strip())
    settings: dict[str, Any] = {
        "SelectAllFrames": True,
        "TargetDir": str(target_dir),
        "CustomName": custom_name,
        "UniqueFilenameStyle": 1,
        "ExportVideo": True,
        "ExportAudio": True,
        "FormatWidth": width,
        "FormatHeight": height,
        "FrameRate": fps,
        "PixelAspectRatio": "square",
        "VideoQuality": video_quality,
        "AudioCodec": "aac",
        "AudioBitDepth": 16,
        "AudioSampleRate": 48000,
        "NetworkOptimization": True,
    }
    if args.export_subtitle:
        settings["ExportSubtitle"] = True
        settings["SubtitleFormat"] = args.subtitle_format
    return settings


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    blueprint, delivery_audit, resolve_audit = load_package(package_dir)
    project_name = args.project_name or blueprint.get("projectName") or "Travel Video"
    timeline_name = args.timeline_name or blueprint.get("timelineName") or "Travel Video Master"
    target_dir = Path(args.target_dir).expanduser().resolve() if args.target_dir else package_dir / "renders"
    custom_name = args.custom_name or slug(timeline_name)
    settings = render_settings(args, blueprint, target_dir, custom_name)
    gate = build_gate(package_dir, project_name, timeline_name, delivery_audit, resolve_audit)
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "packageDir": str(package_dir),
        "projectName": project_name,
        "timelineName": timeline_name,
        "targetDir": str(target_dir),
        "customName": custom_name,
        "requestedFormat": args.render_format,
        "requestedCodec": args.codec,
        "renderSettings": settings,
        "subtitle": {
            "exportSubtitle": bool(args.export_subtitle),
            "subtitleFormat": args.subtitle_format if args.export_subtitle else None,
            "sidecar": blueprint.get("assets", {}).get("subtitles") if isinstance(blueprint.get("assets"), dict) else None,
        },
        "gate": gate,
        "dryRun": not args.queue,
        "queued": False,
        "started": False,
        "jobId": None,
        "jobStatus": None,
        "resolveWarnings": [],
    }


def queue_render(plan: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if not plan["gate"]["allowed"]:
        raise RuntimeError("Render queue is blocked: " + "; ".join(plan["gate"]["blockers"]))
    resolve = get_resolve()
    project_manager = resolve.GetProjectManager()
    project = project_manager.LoadProject(plan["projectName"]) if plan["projectName"] else project_manager.GetCurrentProject()
    if not project:
        raise RuntimeError(f"Resolve project not found: {plan['projectName']}")
    timeline = find_timeline(project, plan["timelineName"])
    if not timeline:
        raise RuntimeError(f"Resolve timeline not found: {plan['timelineName']}")
    project.SetCurrentTimeline(timeline)
    Path(plan["targetDir"]).mkdir(parents=True, exist_ok=True)
    try:
        resolve.OpenPage("deliver")
    except Exception as exc:  # noqa: BLE001
        plan["resolveWarnings"].append(f"Unable to switch to Deliver page: {exc}")

    render_format, codec, available = resolve_format_and_codec(project, args.render_format, args.codec)
    plan["resolvedFormat"] = render_format
    plan["resolvedCodec"] = codec
    plan["availableFormats"] = available["formats"]
    plan["availableCodecs"] = available["codecs"]
    if not project.SetCurrentRenderFormatAndCodec(render_format, codec):
        raise RuntimeError(f"Resolve rejected render format/codec: {render_format}/{codec}")
    if not project.SetCurrentRenderMode(1):
        plan["resolveWarnings"].append("Resolve rejected single-clip render mode.")
    if not project.SetRenderSettings(plan["renderSettings"]):
        raise RuntimeError("Resolve rejected render settings.")
    job_id = project.AddRenderJob()
    if not job_id:
        raise RuntimeError("Resolve did not return a render job id.")
    plan["queued"] = True
    plan["jobId"] = job_id
    try:
        plan["jobStatus"] = project.GetRenderJobStatus(job_id)
    except Exception as exc:  # noqa: BLE001
        plan["resolveWarnings"].append(f"Unable to read render job status: {exc}")
    if args.start:
        started = bool(project.StartRendering([job_id], bool(args.interactive)))
        plan["started"] = started
        try:
            plan["jobStatus"] = project.GetRenderJobStatus(job_id)
        except Exception as exc:  # noqa: BLE001
            plan["resolveWarnings"].append(f"Unable to read render job status after start: {exc}")
    project_manager.SaveProject()
    return plan


def print_human(plan: dict[str, Any]) -> None:
    print("DaVinci Resolve render plan")
    print(f"Project: {plan['projectName']}")
    print(f"Timeline: {plan['timelineName']}")
    print(f"Output: {plan['targetDir']}/{plan['customName']}")
    print(f"Format request: {plan['requestedFormat']} / {plan['requestedCodec']}")
    print(f"Dry-run: {plan['dryRun']}")
    if plan.get("queued"):
        print(f"Queued job id: {plan['jobId']}")
    if plan.get("started"):
        print("Rendering started.")
    for blocker in plan["gate"].get("blockers", []):
        print(f"BLOCKER: {blocker}")
    for warning in plan["gate"].get("warnings", []):
        print(f"WARNING: {warning}")
    for warning in plan.get("resolveWarnings", []):
        print(f"RESOLVE WARNING: {warning}")
    print("Use --queue only after the package audit, asset licenses, and Resolve readback are clean.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare or queue a Resolve render from a Travel Video Studio package.")
    parser.add_argument("--package-dir", required=True, help="Delivery package directory.")
    parser.add_argument("--project-name", help="Resolve project name. Defaults to blueprint projectName.")
    parser.add_argument("--timeline-name", help="Resolve timeline name. Defaults to blueprint timelineName.")
    parser.add_argument("--target-dir", help="Render output directory. Defaults to <package>/renders.")
    parser.add_argument("--custom-name", help="Output basename. Defaults to sanitized timeline name.")
    parser.add_argument("--format", dest="render_format", default="mp4", help="Resolve render format, default mp4.")
    parser.add_argument("--codec", default="H.264", help="Resolve render codec description/name, default H.264.")
    parser.add_argument(
        "--video-quality",
        default="80000",
        help="Resolve VideoQuality value. Numeric values request input bitrate; default 80000 for high-bitrate 4K masters.",
    )
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--fps", type=float)
    parser.add_argument("--export-subtitle", action="store_true", help="Ask Resolve to export native subtitle items.")
    parser.add_argument("--subtitle-format", default="BurnIn", choices=["BurnIn", "EmbeddedCaptions", "SeparateFile"])
    parser.add_argument("--queue", action="store_true", help="Actually add a Resolve render job. Requires clean gates.")
    parser.add_argument("--start", action="store_true", help="Start the newly queued render job.")
    parser.add_argument("--interactive", action="store_true", help="Start rendering with Resolve interactive UI error feedback.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan = build_plan(args)
    if args.start and not args.queue:
        parser.error("--start requires --queue.")
    exit_code = 0
    if args.queue:
        try:
            plan = queue_render(plan, args)
            plan["dryRun"] = False
        except Exception as exc:  # noqa: BLE001
            plan["error"] = str(exc)
            exit_code = 2
    output_path = Path(plan["packageDir"]) / "render_plan.json"
    write_json(output_path, plan)
    if plan.get("jobId"):
        write_json(Path(plan["packageDir"]) / "render_job_status.json", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print_human(plan)
        if plan.get("error"):
            print(f"ERROR: {plan['error']}")
        print(f"Render plan written: {output_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
