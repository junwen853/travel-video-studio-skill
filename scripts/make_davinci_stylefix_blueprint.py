#!/usr/bin/env python3
"""Create a DaVinci-first style-fix blueprint from an existing travel blueprint."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".hevc",
    ".insv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mts",
    ".webm",
}
AUDIO_EXTENSIONS = {".aac", ".aiff", ".aif", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
IMAGE_TEXT_EXTENSIONS = {".ass", ".jpeg", ".jpg", ".png", ".srt", ".txt", ".vtt"}
DESIGNED_VERTICAL_INSERT_TOKENS = {
    "designed_phone_insert",
    "phone_insert",
    "portrait_insert",
    "vertical_insert",
    "split_screen",
    "picture_in_picture",
    "pip",
}
NORMALIZATION_TREATMENT_TOKENS = {"crop", "matte", "blur", "pillar", "fill", "reframe", "safe_area"}
TITLE_TOKEN_MAP = [
    (("hong kong", "香港", "港澳", "维港", "維港"), "HONG KONG"),
    (("macao", "macau", "澳门", "澳門"), "MACAU"),
    (("tokyo", "东京", "東京"), "TOKYO"),
    (("osaka", "大阪"), "OSAKA"),
    (("kyoto", "京都"), "KYOTO"),
    (("japan", "日本"), "JAPAN"),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean(value: Any) -> str:
    return str(value or "").strip()


def title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def title_from_text(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    lower = text.lower()
    for tokens, title in TITLE_TOKEN_MAP:
        if any(token.lower() in lower for token in tokens):
            return title
    ascii_like = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    words = [word for word in ascii_like.upper().split() if word]
    if words:
        return " ".join(words[:3])
    return ""


def iter_possible_titles(base: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    opening_hook = base.get("openingHook") if isinstance(base.get("openingHook"), dict) else {}
    values.extend(opening_hook.get(key) for key in ("cityTitle", "titleText", "place", "subtitle"))
    for clip in base.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        if clip.get("role") == "opening_city_aerial_title" or float(clip.get("timelineStartSeconds") or 0) <= 15:
            values.extend(clip.get(key) for key in ("cityTitle", "titleText", "place", "chapter", "purpose"))
    values.extend(base.get(key) for key in ("projectName", "timelineName", "title", "projectDir"))
    return values


def infer_opening_title(base: dict[str, Any], explicit: str | None) -> str:
    explicit_title = title_from_text(explicit)
    if explicit_title:
        return explicit_title
    for value in iter_possible_titles(base):
        title = title_from_text(value)
        if title:
            return title
    return "TRAVEL"


def infer_project_name(base: dict[str, Any], explicit: str | None, suffix: str) -> str:
    if clean(explicit):
        return clean(explicit)
    base_name = clean(base.get("projectName") or base.get("title") or Path(clean(base.get("projectDir")) or "Travel").name)
    if not base_name:
        base_name = "Travel"
    return f"{base_name} {suffix}".strip()


def infer_timeline_name(base: dict[str, Any], explicit: str | None, suffix: str) -> str:
    if clean(explicit):
        return clean(explicit)
    base_name = clean(base.get("timelineName") or base.get("projectName") or "Travel Longform")
    return f"{base_name} {suffix}".strip()


def infer_bgm_mood(base: dict[str, Any], explicit: str | None, opening_title: str) -> str:
    if clean(explicit):
        return clean(explicit)
    audio_plan = base.get("audioPlan") if isinstance(base.get("audioPlan"), dict) else {}
    for cue in audio_plan.get("bgmCues") or []:
        if isinstance(cue, dict) and clean(cue.get("mood")):
            return clean(cue["mood"])
    title = opening_title.lower()
    if "hong kong" in title or "macau" in title:
        return "harbor travel documentary bed: warm piano, airy pads, restrained percussion"
    if title in {"tokyo", "osaka", "kyoto", "japan"}:
        return "calm long-form Japan travel documentary: piano, soft synth, light strings, restrained city pulse"
    return "serene long-form travel documentary bed: warm piano, ambient texture, restrained city pulse"


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return float(json.loads(proc.stdout)["format"]["duration"])


def stream_rotation(stream: dict[str, Any]) -> int:
    tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
    values: list[Any] = []
    if tags.get("rotate") is not None:
        values.append(tags.get("rotate"))
    for side_data in stream.get("side_data_list") or []:
        if isinstance(side_data, dict) and side_data.get("rotation") is not None:
            values.append(side_data.get("rotation"))
    for value in values:
        try:
            return int(round(float(value))) % 360
        except (TypeError, ValueError):
            continue
    return 0


def probe_geometry(path: Path, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = str(path)
    if key in cache:
        return cache[key]
    if not path.exists():
        cache[key] = {"orientation": "unknown", "error": "source missing"}
        return cache[key]
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        cache[key] = {"orientation": "unknown", "error": (proc.stderr or proc.stdout).strip()}
        return cache[key]
    try:
        probe = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        cache[key] = {"orientation": "unknown", "error": str(exc)}
        return cache[key]
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), {})
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    rotation = stream_rotation(video)
    display_width, display_height = (height, width) if rotation in {90, 270} else (width, height)
    if display_width <= 0 or display_height <= 0:
        orientation = "unknown"
    elif display_width > display_height:
        orientation = "landscape"
    elif display_height > display_width:
        orientation = "portrait"
    else:
        orientation = "square"
    cache[key] = {
        "rawWidth": width,
        "rawHeight": height,
        "rotationDegrees": rotation,
        "displayWidth": display_width,
        "displayHeight": display_height,
        "orientation": orientation,
    }
    return cache[key]


def clip_timeline_interval(clip: dict[str, Any]) -> tuple[float, float]:
    start = float(clip.get("timelineStartSeconds") or 0)
    end = float(clip.get("timelineEndSeconds") or 0)
    if end <= start and clip.get("durationSeconds") is not None:
        end = start + float(clip.get("durationSeconds") or 0)
    return start, end


def clip_role_text(clip: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("role", "purpose", "name", "visualTreatment", "normalization", "orientationPolicy", "customData"):
        value = clip.get(key)
        if value:
            values.append(json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value))
    return " ".join(values).lower()


def is_video_source_clip(clip: dict[str, Any]) -> bool:
    source_raw = str(clip.get("sourcePath") or "").strip()
    if not source_raw:
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type == "audio":
        return False
    suffix = Path(source_raw).suffix.lower()
    if suffix in AUDIO_EXTENSIONS or suffix in IMAGE_TEXT_EXTENSIONS:
        return False
    return suffix in VIDEO_EXTENSIONS or track_type == "video"


def has_declared_vertical_design_exception(clip: dict[str, Any]) -> bool:
    text = clip_role_text(clip)
    has_insert_declaration = any(token in text for token in DESIGNED_VERTICAL_INSERT_TOKENS)
    has_treatment = any(token in text for token in NORMALIZATION_TREATMENT_TOKENS) or any(
        clip.get(key)
        for key in (
            "crop",
            "cropMode",
            "matte",
            "blurBackground",
            "scaleMode",
            "transform",
            "visualTreatment",
            "normalization",
            "orientationPolicy",
        )
    )
    return has_insert_declaration and bool(has_treatment)


def find_clip_by_role_and_start(clips: list[dict[str, Any]], role: str, start: float) -> dict[str, Any] | None:
    for clip in clips:
        if clip.get("role") == role and abs(float(clip.get("timelineStartSeconds") or 0) - start) < 0.05:
            return clip
    return None


def make_blueprint(args: argparse.Namespace) -> dict[str, Any]:
    base_path = Path(args.base_blueprint)
    output_dir = Path(args.output_dir)
    fix_manifest_path = Path(args.fix_manifest)
    bgm_manifest_path = Path(args.bgm_manifest)
    base = load_json(base_path)
    fix_manifest = load_json(fix_manifest_path)
    bgm_manifest = load_json(bgm_manifest_path)

    opening_segment = Path(fix_manifest["openingSegment"])
    replacement_segment = Path(fix_manifest["replacementSegment"])
    bgm_path = Path(bgm_manifest["output"])
    for required in [opening_segment, replacement_segment, bgm_path]:
        if not required.exists():
            raise FileNotFoundError(required)

    blueprint = dict(base)
    opening_title = infer_opening_title(base, getattr(args, "opening_title", None))
    opening_place = clean(getattr(args, "opening_place", None)) or f"{title_case(opening_title)} opening"
    bgm_mood = infer_bgm_mood(base, getattr(args, "bgm_mood", None), opening_title)
    project_name = infer_project_name(base, getattr(args, "project_name", None), "DaVinci StyleFix BGMOnly")
    timeline_name = infer_timeline_name(base, getattr(args, "timeline_name", None), "DaVinci StyleFix BGMOnly")
    blueprint["createdAt"] = datetime.now().isoformat(timespec="seconds")
    blueprint["updatedAt"] = blueprint["createdAt"]
    blueprint["projectName"] = project_name
    blueprint["timelineName"] = timeline_name
    blueprint["outputDir"] = str(output_dir)
    blueprint["voiceoverDisabled"] = True
    blueprint["davinciStyleFixVersion"] = "davinci_stylefix_bgm_only_v2"

    clips = [dict(clip) for clip in base.get("clips", [])]
    for clip in clips:
        if clip.get("trackType") == "video" or int(clip.get("mediaType") or 1) == 1:
            clip["includeSourceAudio"] = False
            clip["mediaType"] = 1
            clip.pop("sourceAudioTrackIndex", None)

    opening = find_clip_by_role_and_start(clips, "opening_city_aerial_title", 0.0)
    if opening is None:
        opening = {
            "role": "opening_city_aerial_title",
            "timelineStartSeconds": 0.0,
            "timelineEndSeconds": 8.0,
            "trackType": "video",
            "trackIndex": 2,
            "mediaType": 1,
        }
        clips.append(opening)
    opening_duration = probe_duration(opening_segment)
    opening.update(
        {
            "role": "opening_city_aerial_title",
            "chapterIndex": 0,
            "place": opening_place,
            "sourcePath": str(opening_segment),
            "sourceStartSeconds": 0.0,
            "sourceEndSeconds": min(8.0, opening_duration),
            "timelineStartSeconds": 0.0,
            "timelineEndSeconds": min(8.0, opening_duration),
            "trackType": "video",
            "trackIndex": 2,
            "mediaType": 1,
            "includeSourceAudio": False,
            "cityTitle": opening_title,
            "titleText": opening_title,
            "subtitle": "",
            "openingTitlePolicy": "single_city_title_only",
            "purpose": f"DaVinci clean opening: single {opening_title} title with BGM-only mix",
        }
    )

    replacement_duration = probe_duration(replacement_segment)
    geometry_cache: dict[str, dict[str, Any]] = {}
    orientation_fixes: list[dict[str, Any]] = []
    orientation_blockers: list[dict[str, Any]] = []
    for index, clip in enumerate(clips):
        if not is_video_source_clip(clip):
            continue
        source_path = Path(str(clip.get("sourcePath"))).expanduser()
        if source_path == replacement_segment:
            continue
        geometry = probe_geometry(source_path, geometry_cache)
        if not geometry.get("error") and (
            geometry.get("orientation") == "landscape" or has_declared_vertical_design_exception(clip)
        ):
            continue
        start, end = clip_timeline_interval(clip)
        duration = end - start
        item = {
            "clipIndex": index,
            "sourcePath": str(source_path),
            "role": clip.get("role") or clip.get("purpose"),
            "timelineStartSeconds": round(start, 3),
            "timelineEndSeconds": round(end, 3),
            "durationSeconds": round(duration, 3),
            "geometry": geometry,
        }
        if geometry.get("error") or duration <= 0 or replacement_duration + 0.05 < duration:
            item["blocker"] = "source unprobeable, invalid duration, or replacement segment too short"
            orientation_blockers.append(item)
            continue
        original_source = str(source_path)
        clip.update(
            {
                "role": "main_footage_landscape_replacement",
                "sourcePath": str(replacement_segment),
                "sourceStartSeconds": 0.0,
                "sourceEndSeconds": min(replacement_duration, duration),
                "timelineStartSeconds": start,
                "timelineEndSeconds": end,
                "durationSeconds": duration,
                "trackType": "video",
                "trackIndex": int(clip.get("trackIndex") or 1),
                "mediaType": 1,
                "includeSourceAudio": False,
                "purpose": "DaVinci stylefix replacement for raw portrait/square/unknown source; subtitles handled separately",
                "replacesSource": original_source,
                "orientationFix": {
                    "status": "applied",
                    "originalSource": original_source,
                    "originalGeometry": geometry,
                    "replacementSource": str(replacement_segment),
                },
            }
        )
        item["replacementSource"] = str(replacement_segment)
        item["status"] = "replaced"
        orientation_fixes.append(item)
    if orientation_blockers:
        raise RuntimeError(f"Raw non-landscape source clips could not be repaired: {json.dumps(orientation_blockers[:5], ensure_ascii=False)}")

    assets = dict(blueprint.get("assets") or {})
    assets["bgm"] = [str(bgm_path)]
    assets["bgmManifest"] = str(bgm_manifest_path)
    assets["visualFixManifest"] = str(fix_manifest_path)
    subtitles = assets.get("subtitles")
    if subtitles and not Path(str(subtitles)).exists():
        assets.pop("subtitles", None)
    blueprint["assets"] = assets

    blueprint["audioPlan"] = {
        "mode": "bgm_only_no_camera_voice",
        "voiceover": {
            "role": "voiceover",
            "status": "disabled_user_requested_text_only",
            "sourcePath": None,
            "exists": False,
        },
        "sourceAudio": {
            "status": "disabled_for_scenic_bgm_only_delivery",
            "trackIndex": 1,
            "policy": "all timeline footage imported video-only; no camera/user voice in opening, scenic, or transition beds",
        },
        "bgmCues": [
            {
                "chapterIndex": 0,
                "place": "full film",
                "mood": bgm_mood,
                "timelineStartSeconds": 0.0,
                "durationSeconds": float(bgm_manifest.get("durationTargetSeconds") or 1200.0),
                "trackIndex": 3,
                "fadeInSeconds": 1.5,
                "fadeOutSeconds": 4.0,
                "targetDbMusicOnly": -18,
                "licenseStatus": "verified_manifest",
                "manifest": str(bgm_manifest_path),
                "status": "ready",
            }
        ],
    }

    markers = list(blueprint.get("timelineMarkers") or [])
    markers.append(
        {
            "startSeconds": 0.0,
            "durationSeconds": 8.0,
            "color": "Green",
            "name": f"STYLEFIX: clean {opening_title} opening title",
            "note": "single city title, no route subtitle, BGM-only",
            "role": "quality_fix",
            "customData": {"fix": "opening_clean_title", "source": str(opening_segment)},
        }
    )
    for fix in orientation_fixes:
        markers.append(
            {
                "startSeconds": fix["timelineStartSeconds"],
                "durationSeconds": fix["durationSeconds"],
                "color": "Green",
                "name": "STYLEFIX: replace raw non-landscape source clip",
                "note": f"source {Path(fix['sourcePath']).name} replaced before Resolve import",
                "role": "quality_fix",
                "customData": {
                    "fix": "replace_raw_non_landscape_source",
                    "source": fix["sourcePath"],
                    "replacement": fix["replacementSource"],
                    "geometry": fix["geometry"],
                },
            }
        )
    markers.append(
        {
            "startSeconds": 0.0,
            "durationSeconds": 12.0,
            "color": "Cyan",
            "name": "STYLEFIX AUDIO: BGM-only no camera voice",
            "note": "A3 BGM bed from verified manifest; source audio disabled",
            "role": "audio_policy",
            "customData": {"bgmManifest": str(bgm_manifest_path), "mode": "bgm_only_no_camera_voice"},
        }
    )
    blueprint["timelineMarkers"] = markers

    blueprint["clips"] = clips
    blueprint["manualQualityFix"] = {
        "createdAt": blueprint["createdAt"],
        "fixes": [
            "DaVinci-first stylefix blueprint generated from an existing Resolve blueprint.",
            f"Opening V2 title clip replaced with title-only {opening_title} segment.",
            f"{len(orientation_fixes)} raw portrait/square/unknown source clip(s) replaced before Resolve import.",
            "All video clips are imported video-only; source camera/user audio disabled.",
            "A3 receives verified BGM-only bed from the provided BGM manifest.",
        ],
        "orientationFixes": orientation_fixes,
        "sourceBlueprint": str(base_path),
        "fixManifest": str(fix_manifest_path),
        "bgmManifest": str(bgm_manifest_path),
    }
    blueprint["openingHook"] = {
        "status": "ready",
        "cityTitle": opening_title,
        "subtitle": "",
        "titleClip": str(opening_segment),
        "rule": "single_city_title_only; no route/date/subtitle text near hero title",
    }
    blueprint["visualNormalizationPolicy"] = {
        "status": "applied",
        "targetCanvas": "3840x2160 landscape",
        "rules": [
            "all raw portrait/square/unknown source clips are ffprobe-scanned and replaced or blocked before Resolve import",
            "no raw portrait clips are allowed unless declared as a designed insert",
            "all final feedback timestamps must pass audit_visual_audio_style.py",
        ],
        "orientationFixes": orientation_fixes,
    }
    return blueprint


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-blueprint", required=True)
    parser.add_argument("--fix-manifest", required=True)
    parser.add_argument("--bgm-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--project-name")
    parser.add_argument("--timeline-name")
    parser.add_argument("--opening-title")
    parser.add_argument("--opening-place")
    parser.add_argument("--bgm-mood")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    blueprint = make_blueprint(args)
    blueprint_path = output_dir / "resolve_timeline_blueprint_v10_davinci_stylefix.json"
    write_json(blueprint_path, blueprint)
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed",
        "blueprint": str(blueprint_path),
        "projectName": blueprint["projectName"],
        "timelineName": blueprint["timelineName"],
        "clipCount": len(blueprint.get("clips", [])),
        "sourceAudioClipCount": sum(1 for clip in blueprint.get("clips", []) if clip.get("includeSourceAudio")),
        "bgm": blueprint.get("assets", {}).get("bgm"),
        "openingHook": blueprint.get("openingHook"),
        "manualQualityFix": blueprint.get("manualQualityFix"),
    }
    write_json(output_dir / "v10_davinci_stylefix_blueprint_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
