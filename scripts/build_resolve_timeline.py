#!/usr/bin/env python3
"""Build a DaVinci Resolve project/timeline from a Travel Video Studio blueprint."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from resolve_common import get_resolve, seconds_to_frames


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clip_key(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def media_property(item: Any, key: str) -> str:
    try:
        value = item.GetClipProperty(key)
        if value:
            return str(value)
    except Exception:  # noqa: BLE001
        pass
    try:
        props = item.GetClipProperty()
        if isinstance(props, dict):
            return str(props.get(key) or "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def probe_duration_seconds(path: str) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


def probe_video_fps(path: str) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate,r_frame_rate",
            "-of",
            "json",
            path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        stream = (json.loads(result.stdout).get("streams") or [{}])[0]
    except Exception:  # noqa: BLE001
        return None
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = str(stream.get(key) or "")
        if "/" in value:
            num, den = value.split("/", 1)
            try:
                den_f = float(den)
                fps = float(num) / den_f if den_f else 0
            except ValueError:
                fps = 0
        else:
            try:
                fps = float(value)
            except ValueError:
                fps = 0
        if fps > 0:
            return fps
    return None


def summarize_blueprint(blueprint: dict[str, Any]) -> dict[str, Any]:
    clips = blueprint.get("clips", [])
    paths = sorted({clip_key(c["sourcePath"]) for c in clips if c.get("sourcePath")})
    assets = blueprint.get("assets", {}) if isinstance(blueprint.get("assets"), dict) else {}
    audio_plan = blueprint.get("audioPlan", {}) if isinstance(blueprint.get("audioPlan"), dict) else {}
    voiceover_plan = audio_plan.get("voiceover", {}) if isinstance(audio_plan.get("voiceover"), dict) else {}
    audio_assets = []
    for key in ("voiceover",):
        path = assets.get(key)
        if path:
            audio_assets.append(path)
    for path in assets.get("bgm", []) if isinstance(assets.get("bgm"), list) else []:
        audio_assets.append(path)
    by_chapter = defaultdict(int)
    source_audio_clip_count = 0
    for clip in clips:
        by_chapter[str(clip.get("place") or clip.get("chapterIndex"))] += 1
        if clip.get("includeSourceAudio"):
            source_audio_clip_count += 1
    missing = [path for path in paths if not Path(path).exists()]
    missing_audio = [path for path in audio_assets if not Path(path).exists()]
    return {
        "projectName": blueprint.get("projectName"),
        "timelineName": blueprint.get("timelineName"),
        "fps": blueprint.get("fps"),
        "resolution": blueprint.get("resolution"),
        "clipCount": len(clips),
        "sourceFileCount": len(paths),
        "audioAssetCount": len(audio_assets),
        "missingSourceFiles": missing,
        "pendingAudioAssets": missing_audio,
        "clipsByPlace": dict(by_chapter),
        "sourceAudioClipCount": source_audio_clip_count,
        "subtitleSidecar": assets.get("subtitles"),
        "subtitleCueCount": len(blueprint.get("subtitleCues") or []),
        "timelineMarkerCount": len(blueprint.get("timelineMarkers") or []),
        "bgmCueCount": len(audio_plan.get("bgmCues") or []),
        "stockPlaceholderCount": len(blueprint.get("stockInsertPlan") or []),
        "transitionCount": len(blueprint.get("transitionPlan") or []),
        "voiceoverPlanStatus": voiceover_plan.get("status"),
        "longFormCoverage": blueprint.get("longFormCoverage"),
        "coverageRatio": blueprint.get("coverageRatio"),
        "actualVideoCoverageSeconds": blueprint.get("actualVideoCoverageSeconds"),
    }


def ensure_tracks(timeline: Any, blueprint: dict[str, Any]) -> list[str]:
    notes = []
    for track in blueprint.get("tracks", []):
        track_type = track.get("type")
        index = int(track.get("index") or 1)
        if track_type not in {"video", "audio", "subtitle"}:
            continue
        while timeline.GetTrackCount(track_type) < index:
            if track_type == "audio":
                ok = timeline.AddTrack("audio", {"audioType": "stereo", "index": timeline.GetTrackCount("audio") + 1})
            else:
                ok = timeline.AddTrack(track_type)
            notes.append(f"add {track_type} track {index}: {ok}")
            if not ok:
                break
        name = track.get("name")
        if name and timeline.GetTrackCount(track_type) >= index:
            ok = timeline.SetTrackName(track_type, index, name)
            notes.append(f"name {track_type} track {index}: {ok}")
    return notes


def import_media(resolve: Any, media_paths: list[str]) -> dict[str, Any]:
    storage = resolve.GetMediaStorage()
    imported = storage.AddItemListToMediaPool(media_paths)
    items = {}
    for item in imported or []:
        path = media_property(item, "File Path")
        if path:
            items[clip_key(path)] = item
        name = media_property(item, "File Name")
        if name:
            items.setdefault(name, item)
    return items


def append_audio_assets(media_pool: Any, imported: dict[str, Any], blueprint: dict[str, Any], fps: float) -> tuple[int, list[dict[str, str]], list[dict[str, Any]]]:
    assets = blueprint.get("assets", {}) if isinstance(blueprint.get("assets"), dict) else {}
    requested = []
    voiceover = assets.get("voiceover")
    if voiceover and Path(voiceover).exists():
        requested.append({"path": voiceover, "trackIndex": 2, "role": "voiceover"})
    for bgm in assets.get("bgm", []) if isinstance(assets.get("bgm"), list) else []:
        if bgm and Path(bgm).exists():
            requested.append({"path": bgm, "trackIndex": 3, "role": "bgm"})
    skipped = []
    appended_assets = []
    appended_count = 0
    for item in requested:
        media = imported.get(clip_key(item["path"])) or imported.get(Path(item["path"]).name)
        if not media:
            skipped.append({"path": item["path"], "reason": "audio asset not imported"})
            continue
        duration = probe_duration_seconds(item["path"])
        if not duration or duration <= 0:
            skipped.append({"path": item["path"], "reason": "unable to probe audio duration"})
            continue
        result = media_pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": media,
                    "startFrame": 0,
                    "endFrame": seconds_to_frames(duration, fps),
                    "recordFrame": 0,
                    "mediaType": 2,
                    "trackIndex": item["trackIndex"],
                }
            ]
        )
        count = len(result or [])
        appended_count += count
        appended_assets.append({**item, "durationSeconds": duration, "appendedItems": count})
    return appended_count, skipped, appended_assets


def append_markers(timeline: Any, blueprint: dict[str, Any], fps: float) -> tuple[int, list[dict[str, Any]]]:
    appended = 0
    skipped = []
    used_frames: set[int] = set()
    allowed_colors = {"Blue", "Cyan", "Green", "Yellow", "Red", "Pink", "Purple", "Fuchsia", "Rose", "Lavender", "Sky", "Mint", "Lemon", "Sand", "Cocoa", "Cream"}
    color_aliases = {"Orange": "Yellow", "White": "Cream", "Black": "Cocoa"}
    for item in blueprint.get("timelineMarkers") or []:
        try:
            start = seconds_to_frames(float(item.get("startSeconds") or 0), fps)
            duration = max(1, seconds_to_frames(float(item.get("durationSeconds") or 1), fps))
            original_start = start
            while start in used_frames:
                start += 1
            raw_name = str(item.get("name") or item.get("role") or "Marker")
            name = raw_name if len(raw_name) <= 80 else raw_name[:77].rstrip() + "..."
            note = str(item.get("note") or "")
            if raw_name != name:
                note = f"Full marker name: {raw_name}\n{note}".strip()
            custom_payload = dict(item.get("customData") or {})
            if raw_name != name:
                custom_payload["fullName"] = raw_name
            if original_start != start:
                custom_payload["originalFrame"] = original_start
                custom_payload["frameOffsetForResolveMarkerCollision"] = start - original_start
            custom_data = json.dumps(custom_payload, ensure_ascii=False)
            color = str(item.get("color") or "Blue")
            color = color_aliases.get(color, color)
            if color not in allowed_colors:
                color = "Blue"
            ok = timeline.AddMarker(
                start,
                color,
                name,
                note[:900],
                duration,
                custom_data,
            )
        except Exception as exc:  # noqa: BLE001
            skipped.append({"marker": item.get("name") or item.get("role"), "reason": str(exc)})
            continue
        if ok:
            appended += 1
            used_frames.add(start)
        else:
            skipped.append({"marker": item.get("name") or item.get("role"), "reason": "Resolve rejected marker"})
    return appended, skipped


def build_timeline(blueprint: dict[str, Any], render_jobs: bool = False) -> dict[str, Any]:
    resolve = get_resolve()
    project_manager = resolve.GetProjectManager()
    project_name = blueprint.get("projectName") or f"Travel Video {datetime.now():%Y%m%d_%H%M%S}"
    project = project_manager.CreateProject(project_name)
    if not project:
        project_name = f"{project_name} {datetime.now():%H%M%S}"
        project = project_manager.CreateProject(project_name)
    if not project:
        raise RuntimeError(f"Unable to create Resolve project: {project_name}")

    fps = float(blueprint.get("fps") or 25)
    resolution = blueprint.get("resolution") or {}
    project.SetSetting("timelineFrameRate", str(fps))
    project.SetSetting("timelineResolutionWidth", str(int(resolution.get("width") or 3840)))
    project.SetSetting("timelineResolutionHeight", str(int(resolution.get("height") or 2160)))

    media_pool = project.GetMediaPool()
    timeline_name = blueprint.get("timelineName") or "Travel Video Master"
    timeline = media_pool.CreateEmptyTimeline(timeline_name)
    if not timeline:
        raise RuntimeError(f"Unable to create timeline: {timeline_name}")
    project.SetCurrentTimeline(timeline)
    timeline_start_timecode = str(blueprint.get("timelineStartTimecode") or "00:00:00:00")
    timeline.SetStartTimecode(timeline_start_timecode)
    track_notes = ensure_tracks(timeline, blueprint)

    source_paths = sorted({clip_key(c["sourcePath"]) for c in blueprint.get("clips", []) if c.get("sourcePath")})
    assets = blueprint.get("assets", {}) if isinstance(blueprint.get("assets"), dict) else {}
    for key in ("voiceover",):
        path = assets.get(key)
        if path and Path(path).exists():
            source_paths.append(clip_key(path))
    for path in assets.get("bgm", []) if isinstance(assets.get("bgm"), list) else []:
        if path and Path(path).exists():
            source_paths.append(clip_key(path))
    source_paths = sorted(set(source_paths))
    existing_paths = [p for p in source_paths if Path(p).exists()]
    imported = import_media(resolve, existing_paths)

    clip_infos = []
    skipped = []
    source_fps_cache: dict[str, float] = {}
    for clip in blueprint.get("clips", []):
        source_path = clip.get("sourcePath")
        if not source_path:
            skipped.append({"clip": clip, "reason": "missing sourcePath"})
            continue
        item = imported.get(clip_key(source_path)) or imported.get(Path(source_path).name)
        if not item:
            skipped.append({"sourcePath": source_path, "reason": "not imported or missing"})
            continue
        source_key = clip_key(source_path)
        if source_key not in source_fps_cache:
            source_fps_cache[source_key] = probe_video_fps(source_key) or fps
        source_fps = source_fps_cache[source_key]
        start = seconds_to_frames(float(clip.get("sourceStartSeconds") or 0), source_fps)
        end = seconds_to_frames(float(clip.get("sourceEndSeconds") or 0), source_fps)
        record = seconds_to_frames(float(clip.get("timelineStartSeconds") or 0), fps)
        if end <= start:
            skipped.append({"sourcePath": source_path, "reason": "invalid source range"})
            continue
        clip_info = {
            "mediaPoolItem": item,
            "startFrame": start,
            "endFrame": end,
            "recordFrame": record,
            "trackIndex": int(clip.get("trackIndex") or 1),
        }
        if not clip.get("includeSourceAudio"):
            clip_info["mediaType"] = int(clip.get("mediaType") or 1)
        clip_infos.append(clip_info)

    appended = media_pool.AppendToTimeline(clip_infos) if clip_infos else []
    audio_appended, audio_skipped, appended_audio_assets = append_audio_assets(media_pool, imported, blueprint, fps)
    markers_appended, marker_skipped = append_markers(timeline, blueprint, fps)
    skipped.extend(audio_skipped)
    skipped.extend(marker_skipped)
    try:
        source_audio_timeline_item_count = len(timeline.GetItemListInTrack("audio", 1) or [])
    except Exception:  # noqa: BLE001
        source_audio_timeline_item_count = None
    project_manager.SaveProject()
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "projectName": project.GetName(),
        "timelineName": timeline.GetName(),
        "timelineStartTimecode": timeline_start_timecode,
        "fps": fps,
        "sourceFileCount": len(source_paths),
        "sourceFps": source_fps_cache,
        "importedFileCount": len(imported),
        "requestedClipCount": len(blueprint.get("clips", [])),
        "appendedClipCount": len(appended or []),
        "requestedSourceAudioClipCount": sum(1 for clip in blueprint.get("clips", []) if clip.get("includeSourceAudio")),
        "sourceAudioTimelineItemCount": source_audio_timeline_item_count,
        "appendedAudioAssetCount": audio_appended,
        "appendedAudioAssets": appended_audio_assets,
        "requestedMarkerCount": len(blueprint.get("timelineMarkers") or []),
        "appendedMarkerCount": markers_appended,
        "subtitleSidecar": assets.get("subtitles"),
        "subtitleCueCount": len(blueprint.get("subtitleCues") or []),
        "skipped": skipped,
        "trackNotes": track_notes,
        "renderJobsQueued": bool(render_jobs),
    }


def print_human(summary: dict[str, Any], applied: bool) -> None:
    if applied:
        print("Built DaVinci Resolve timeline")
        print(f"Project: {summary['projectName']}")
        print(f"Timeline: {summary['timelineName']}")
        print(f"Imported files: {summary['importedFileCount']}/{summary['sourceFileCount']}")
        print(f"Appended clips: {summary['appendedClipCount']}/{summary['requestedClipCount']}")
        print(
            "Source audio items: "
            f"{summary.get('sourceAudioTimelineItemCount')}/"
            f"{summary.get('requestedSourceAudioClipCount', 0)}"
        )
        print(f"Appended audio assets: {summary.get('appendedAudioAssetCount', 0)}")
        print(f"Appended markers: {summary.get('appendedMarkerCount', 0)}/{summary.get('requestedMarkerCount', 0)}")
        if summary.get("subtitleSidecar"):
            print(f"Subtitle sidecar: {summary['subtitleSidecar']}")
        if summary.get("skipped"):
            print("Skipped:")
            for item in summary["skipped"][:20]:
                print(f"  - {item}")
    else:
        print("DaVinci Resolve dry-run")
        print(f"Project: {summary['projectName']}")
        print(f"Timeline: {summary['timelineName']}")
        print(f"Clips: {summary['clipCount']}")
        print(f"Source files: {summary['sourceFileCount']}")
        print(f"Source-audio clips: {summary.get('sourceAudioClipCount', 0)}")
        print(f"Audio assets: {summary['audioAssetCount']}")
        print(f"Subtitle cues: {summary.get('subtitleCueCount', 0)}")
        print(f"Timeline markers: {summary.get('timelineMarkerCount', 0)}")
        print(f"BGM cues: {summary.get('bgmCueCount', 0)}")
        print(f"Stock placeholders: {summary.get('stockPlaceholderCount', 0)}")
        print(f"Coverage ratio: {summary.get('coverageRatio')}")
        if summary.get("longFormCoverage"):
            fill = summary["longFormCoverage"]
            print(
                "Long-form fill: "
                f"{fill.get('initialVideoCoverageSeconds')}s -> {fill.get('finalVideoCoverageSeconds')}s "
                f"(+{fill.get('coverageFillAddedSeconds')}s)"
            )
        if summary.get("subtitleSidecar"):
            print(f"Subtitle sidecar: {summary['subtitleSidecar']}")
        if summary["missingSourceFiles"]:
            print("Missing source files:")
            for path in summary["missingSourceFiles"][:20]:
                print(f"  - {path}")
        if summary.get("pendingAudioAssets"):
            print("Pending audio assets:")
            for path in summary["pendingAudioAssets"][:20]:
                print(f"  - {path}")
        print("Use --apply only after approving the write contract.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Resolve timeline from resolve_timeline_blueprint.json.")
    parser.add_argument("--blueprint", required=True, help="Path to resolve_timeline_blueprint.json.")
    parser.add_argument("--apply", action="store_true", help="Actually create project/timeline in Resolve.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    blueprint = load_json(Path(args.blueprint).expanduser().resolve())
    if args.apply:
        summary = build_timeline(blueprint)
    else:
        summary = summarize_blueprint(blueprint)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_human(summary, args.apply)
    return 0 if not summary.get("missingSourceFiles") else 2


if __name__ == "__main__":
    raise SystemExit(main())
