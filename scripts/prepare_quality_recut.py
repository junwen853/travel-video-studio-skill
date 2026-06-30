#!/usr/bin/env python3
"""Prepare a higher-quality recut package from an existing long-form delivery package."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def replace_path_values(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_path_values(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_path_values(item, old, new) for key, item in value.items()}
    return value


def clean_quality_suffix(value: Any) -> str:
    text = str(value or "Travel Video").strip()
    text = re.sub(r"(\s+Quality\s+v\d+)+$", "", text, flags=re.IGNORECASE).strip()
    return text or "Travel Video"


TITLE_TOKEN_MAP = [
    (("hong kong", "香港", "港澳", "维港", "維港"), "HONG KONG"),
    (("macao", "macau", "澳门", "澳門"), "MACAU"),
    (("tokyo", "东京", "東京"), "TOKYO"),
    (("osaka", "大阪"), "OSAKA"),
    (("kyoto", "京都"), "KYOTO"),
    (("japan", "日本"), "JAPAN"),
]


def title_from_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lower = text.lower()
    for tokens, title in TITLE_TOKEN_MAP:
        if any(token.lower() in lower for token in tokens):
            return title
    ascii_like = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    words = [word for word in ascii_like.upper().split() if word]
    return " ".join(words[:3]) if words else ""


def infer_title_from_payloads(delivery: dict[str, Any], blueprint: dict[str, Any], fallback: str = "TRAVEL") -> str:
    candidates: list[Any] = []
    for payload in (blueprint.get("openingHook"), blueprint.get("endingHook")):
        if isinstance(payload, dict):
            candidates.extend(payload.get(key) for key in ("cityTitle", "titleText", "place", "subtitle"))
    for clip in blueprint.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        if clip.get("role") in {"opening_city_aerial_title", "ending_city_aerial_title"} or float(clip.get("timelineStartSeconds") or 0) <= 15:
            candidates.extend(clip.get(key) for key in ("cityTitle", "titleText", "place", "chapter", "purpose"))
    candidates.extend(blueprint.get(key) for key in ("projectName", "timelineName", "title", "projectDir"))
    candidates.extend(delivery.get(key) for key in ("title", "projectDir"))
    for candidate in candidates:
        title = title_from_text(candidate)
        if title:
            return title
    return fallback


def infer_route_subtitle(delivery: dict[str, Any], blueprint: dict[str, Any], opening_title: str) -> str:
    values = []
    for section in delivery.get("longFormSections") or []:
        if isinstance(section, dict) and section.get("place"):
            values.append(str(section["place"]))
    for chapter in blueprint.get("chapters") or []:
        if isinstance(chapter, dict) and chapter.get("place"):
            values.append(str(chapter["place"]))
    titles = []
    for value in values:
        title = title_from_text(value)
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= 2:
            break
    if len(titles) >= 2 and opening_title in titles:
        return " TO ".join(titles[:2])
    return ""


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def run_city_aerial_title(
    aerial_path: str,
    output_dir: Path,
    city_title: str,
    subtitle: str,
    fps: float,
    duration: float,
    label: str,
) -> dict[str, Any]:
    if not aerial_path or not Path(aerial_path).expanduser().exists():
        return {"status": "skipped", "reason": "aerial source missing", "output": None}
    output = output_dir / "aerial_titles" / f"{label}_{city_title.lower().replace(' ', '_')}.mp4"
    cmd = [
        sys.executable,
        str(script_dir() / "make_city_aerial_title.py"),
        "--aerial",
        aerial_path,
        "--city-title",
        city_title,
        "--subtitle",
        subtitle,
        "--output",
        str(output),
        "--fps",
        str(fps),
        "--duration",
        str(duration),
        "--json",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    payload.update(
        {
            "returnCode": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-4000:],
            "output": str(output),
        }
    )
    return payload


def regenerate_clean_title_cards(output_dir: Path, fps: float) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(script_dir() / "generate_title_cards.py"),
        "--delivery-plan",
        str(output_dir / "delivery_plan.json"),
        "--blueprint",
        str(output_dir / "resolve_timeline_blueprint.json"),
        "--output-dir",
        str(output_dir / "title_cards"),
        "--fps",
        str(fps),
        "--update-blueprint",
        "--json",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    payload.update(
        {
            "returnCode": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-4000:],
        }
    )
    return payload


def remove_bad_opening_slates(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for clip in clips:
        role = str(clip.get("role") or "")
        source = str(clip.get("sourcePath") or "")
        chapter = clip.get("chapterIndex")
        start = float(clip.get("timelineStartSeconds") or clip.get("startSeconds") or 0)
        if chapter == 0 and ("title_card" in role or "title_cards/opening" in source) and start <= 1:
            continue
        if role in {"opening_aerial_insert_v4", "opening_city_aerial_title"}:
            continue
        cleaned.append(clip)
    return cleaned


def remove_plain_ending_slates(clips: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    cleaned = []
    for clip in clips:
        role = str(clip.get("role") or "")
        source = str(clip.get("sourcePath") or "")
        start = float(clip.get("timelineStartSeconds") or clip.get("startSeconds") or 0)
        if start >= max(0.0, duration - 20.0) and ("title_card" in role or "title_cards/ending" in source):
            continue
        if clip.get("role") == "ending_aerial_insert_v4":
            continue
        cleaned.append(clip)
    return cleaned


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hh = int(seconds // 3600)
    mm = int((seconds % 3600) // 60)
    ss = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ss += 1
        ms = 0
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def section_at(sections: list[dict[str, Any]], seconds: float) -> dict[str, Any]:
    current = sections[0] if sections else {"place": "旅途", "targetRole": "main_chapter"}
    for section in sections:
        start = float(section.get("startSeconds") or 0)
        duration = float(section.get("durationSeconds") or 0)
        if start <= seconds < start + duration:
            return section
        if start <= seconds:
            current = section
    return current


def caption_text(section: dict[str, Any], index: int) -> str:
    place = section.get("place") or "旅途"
    role = section.get("targetRole") or ""
    opening = [
        "这一次不做一分钟速览，把这段旅程慢慢剪成一条能走进去的路。",
        "先看城市的呼吸，再看景点本身。",
        "画面里的路牌、车窗、街口，会比一句旁白更诚实。",
    ]
    ending = [
        "旅行结束前，再把这些零散的镜头放回同一条路上。",
        "片尾不急着总结，只把音乐和最后的街景留住。",
        "真正留下来的，往往不是打卡点，而是路上的停顿。",
    ]
    generic = [
        f"{place}这一段，先让街景和声音带路。",
        "不用把每一秒都解释完，观众需要一点自己进入的空间。",
        "看招牌、车流、天气和人群，路线会慢慢浮出来。",
        "这一段适合放慢，让镜头之间有一点呼吸。",
        "从一个地点到下一个地点，中间的路也要被看见。",
        "保留现场声，让画面不要像模板生成的旅行片。",
        "这里的重点不是炫技，而是把真实的移动感剪出来。",
        "如果地点还不能百分百确认，字幕只说画面证据能支持的部分。",
    ]
    if "opening" in role.lower() or str(place).lower() == "opening":
        pool = opening
    elif "ending" in role.lower() or str(place).lower() == "ending":
        pool = ending
    else:
        pool = generic
    return pool[index % len(pool)]


def make_dense_srt(sections: list[dict[str, Any]], duration: float, interval: float, cue_duration: float) -> tuple[str, list[dict[str, Any]]]:
    cues: list[dict[str, Any]] = []
    starts = [0.0, 8.0, 18.0, 34.0]
    t = 60.0
    while t < max(60.0, duration - 18.0):
        starts.append(t)
        t += interval
    starts.extend([max(0.0, duration - 52.0), max(0.0, duration - 32.0), max(0.0, duration - 14.0)])
    starts = sorted({round(item, 3) for item in starts if 0 <= item < duration - 1})
    lines: list[str] = []
    for idx, start in enumerate(starts, start=1):
        end = min(duration - 0.2, start + cue_duration)
        section = section_at(sections, start)
        text = caption_text(section, idx - 1)
        cues.append(
            {
                "index": idx,
                "startSeconds": start,
                "endSeconds": end,
                "durationSeconds": round(end - start, 3),
                "text": text,
                "mode": "text_caption_no_voiceover",
                "place": section.get("place"),
            }
        )
        lines.extend([str(idx), f"{fmt_time(start)} --> {fmt_time(end)}", text, ""])
    return "\n".join(lines).strip() + "\n", cues


def add_or_replace_aerial_clip(clips: list[dict[str, Any]], source_path: str, start: float, duration: float, role: str) -> None:
    if not source_path or not Path(source_path).expanduser().exists():
        return
    clips[:] = [
        clip
        for clip in clips
        if not (
            clip.get("role") == role
            or (clip.get("role") == "aerial_insert" and abs(float(clip.get("timelineStartSeconds") or -999) - start) < 0.1)
        )
    ]
    clips.append(
        {
            "role": role,
            "trackType": "video",
            "trackIndex": 2,
            "sourcePath": source_path,
            "timelineStartSeconds": round(start, 3),
            "durationSeconds": duration,
            "sourceStartSeconds": 0.0,
            "sourceEndSeconds": duration,
            "includeSourceAudio": False,
        }
    )
    clips.sort(key=lambda item: (float(item.get("timelineStartSeconds") or 0), int(item.get("trackIndex") or 1)))


def build_quality_package(args: argparse.Namespace) -> dict[str, Any]:
    source_dir = Path(args.source_package).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else source_dir.parent / f"{timestamp}_quality_v4"
    output_dir.mkdir(parents=True, exist_ok=True)

    for name in [
        "asset_ledger",
        "asset_sourcing",
        "bgm",
        "title_cards",
    ]:
        copy_if_exists(source_dir / name, output_dir / name)
    for name in [
        "long_form_structure.md",
        "edit_decision_plan.md",
        "asset_search_plan.md",
        "bgm_cues.md",
        "qa_checklist.md",
        "davinci_build_notes.md",
        "delivery_assets_report.json",
        "delivery_assets_report.md",
    ]:
        copy_if_exists(source_dir / name, output_dir / name)

    old = str(source_dir)
    new = str(output_dir)
    delivery = replace_path_values(load_json(source_dir / "delivery_plan.json"), old, new)
    blueprint = replace_path_values(load_json(source_dir / "resolve_timeline_blueprint.json"), old, new)
    enrichment = replace_path_values(load_json(source_dir / "resolve_timeline_enrichment.json"), old, new)

    duration = float(blueprint.get("targetDurationSeconds") or args.target_duration_seconds)
    fps = float(args.fps)
    project_name = args.project_name or f"{clean_quality_suffix(blueprint.get('projectName'))} Quality v4"
    timeline_name = args.timeline_name or f"{clean_quality_suffix(blueprint.get('timelineName') or 'Travel Video Master')} Quality v4"
    city_title = (args.city_title or infer_title_from_payloads(delivery, blueprint)).upper()
    opening_subtitle = args.opening_subtitle if args.opening_subtitle is not None else infer_route_subtitle(delivery, blueprint, city_title)
    ending_city_title = (args.ending_city_title or city_title).upper()
    ending_subtitle = args.ending_subtitle if args.ending_subtitle is not None else opening_subtitle
    captions_path = output_dir / "subtitles_v4_dense.srt"
    narration_txt = output_dir / "narration_text_only_v4.txt"

    sections = delivery.get("longFormSections") or []
    srt_text, cues = make_dense_srt(sections, duration, args.caption_interval_seconds, args.caption_duration_seconds)
    write_text(captions_path, srt_text)
    original_script = read_text(source_dir / "voiceover_script.txt").strip()
    write_text(
        narration_txt,
        "\n".join(
            [
                f"{city_title} v4 文案稿",
                "",
                "用户要求：最终成片不再使用口播音轨；此 TXT 只作为剪辑文案、字幕和章节说明来源。",
                "",
                "原始口播稿：",
                original_script or "(empty)",
                "",
                "新增全片字幕/地点卡文案见 subtitles_v4_dense.srt。",
            ]
        )
        + "\n",
    )

    for payload in (delivery, blueprint, enrichment):
        payload["updatedAt"] = datetime.now().isoformat(timespec="seconds")

    delivery["outputDir"] = str(output_dir)
    delivery["status"] = "quality_recut_prepared"
    delivery["qualityRecut"] = {
        "sourcePackage": str(source_dir),
        "mode": "no_voiceover_audio_text_only",
        "fps": fps,
        "targetVideoBitrate": args.target_video_bitrate,
        "captionCueCount": len(cues),
        "narrationText": str(narration_txt),
        "subtitleSidecar": str(captions_path),
        "requirements": [
            "No rendered voiceover audio track.",
            "BGM must be audible in final mix.",
            "Opening and ending must include city aerial or verified establishing footage.",
            "Final render must be 4K and high frame rate.",
        ],
    }
    delivery["voiceover"] = {
        "mode": "text_only_user_requested_no_voiceover_audio",
        "scriptFile": str(narration_txt),
        "ttsNextStep": None,
    }
    delivery["subtitles"] = {"srtFile": str(captions_path), "timing": "dense_text_caption_v4", "cueCount": len(cues)}

    blueprint["projectName"] = project_name
    blueprint["timelineName"] = timeline_name
    blueprint["fps"] = fps
    blueprint["targetRender"] = {
        "resolution": "3840x2160",
        "fps": fps,
        "videoBitrate": args.target_video_bitrate,
        "audio": "AAC 48kHz stereo",
        "voiceoverAudio": "disabled",
        "subtitleMode": "burned-in dense captions after render",
    }
    blueprint["subtitleCues"] = cues
    blueprint.setdefault("assets", {})
    blueprint["assets"]["subtitles"] = str(captions_path)
    blueprint["assets"].pop("voiceover", None)
    blueprint["voiceoverDisabled"] = True
    blueprint["timelineStartTimecode"] = "00:00:00:00"
    audio_plan = blueprint.get("audioPlan") if isinstance(blueprint.get("audioPlan"), dict) else {}
    audio_plan["voiceover"] = {
        "role": "voiceover",
        "status": "disabled_user_requested_text_only",
        "scriptFile": str(narration_txt),
        "sourcePath": None,
        "exists": False,
    }
    audio_plan["sourceAudioPolicy"] = "keep useful source ambience on A1, but final mix must make BGM clearly audible; no voiceover audio."
    blueprint["audioPlan"] = audio_plan

    enrichment["sourceDeliveryPlan"] = str(output_dir / "delivery_plan.json")
    enrichment["sourceBlueprint"] = str(output_dir / "resolve_timeline_blueprint.json")
    enrichment["subtitlePlan"] = {
        "sourcePath": str(captions_path),
        "exists": True,
        "cueCount": len(cues),
        "status": "dense_sidecar_srt_ready_for_burn_in",
        "resolveNativeStatus": "sidecar_burn_in_after_render",
    }
    enrichment["subtitleCues"] = cues
    enrichment.setdefault("audioPlan", {})
    enrichment["audioPlan"]["voiceover"] = audio_plan["voiceover"]
    enrichment["audioPlan"]["sourceAudioPolicy"] = audio_plan["sourceAudioPolicy"]
    enrichment["summary"] = {
        **(enrichment.get("summary") or {}),
        "subtitleCueCount": len(cues),
        "voiceoverExists": False,
        "voiceoverDisabled": True,
        "qualityRecut": "v4_high_fps_no_voiceover_dense_captions",
    }
    enrichment["status"] = "quality_recut_ready_for_resolve_apply"

    write_json(output_dir / "delivery_plan.json", delivery)
    write_json(output_dir / "resolve_timeline_blueprint.json", blueprint)
    title_card_report = regenerate_clean_title_cards(output_dir, fps)
    refreshed_blueprint = load_json(output_dir / "resolve_timeline_blueprint.json")
    if isinstance(refreshed_blueprint, dict):
        blueprint = refreshed_blueprint

    aerials = blueprint.get("assets", {}).get("aerials") or []
    aerial_path = aerials[0] if aerials else ""
    clips = blueprint.get("clips") or []
    city_title_report = run_city_aerial_title(
        aerial_path,
        output_dir,
        city_title,
        opening_subtitle,
        fps,
        args.opening_aerial_duration_seconds,
        "opening",
    )
    ending_title_report = run_city_aerial_title(
        aerial_path,
        output_dir,
        ending_city_title,
        ending_subtitle,
        fps,
        args.ending_aerial_duration_seconds,
        "ending",
    )
    clips = remove_bad_opening_slates(clips)
    clips = remove_plain_ending_slates(clips, duration)
    city_title_output = city_title_report.get("output")
    if city_title_report.get("status") == "ready" and city_title_output and Path(city_title_output).exists():
        clips.append(
            {
                "role": "opening_city_aerial_title",
                "trackType": "video",
                "trackIndex": 2,
                "sourcePath": city_title_output,
                "timelineStartSeconds": 0.0,
                "durationSeconds": args.opening_aerial_duration_seconds,
                "sourceStartSeconds": 0.0,
                "sourceEndSeconds": args.opening_aerial_duration_seconds,
                "includeSourceAudio": False,
                "cityTitle": city_title,
                "subtitle": opening_subtitle,
                "purpose": "client hook: city aerial with clean English title typography",
            }
        )
    else:
        add_or_replace_aerial_clip(clips, aerial_path, 0.0, args.opening_aerial_duration_seconds, "opening_aerial_insert_v4")
    add_or_replace_aerial_clip(clips, aerial_path, 429.25, 8.0, "transition_aerial_bridge_1_v4")
    add_or_replace_aerial_clip(clips, aerial_path, 759.62, 8.0, "transition_aerial_bridge_2_v4")
    ending_title_output = ending_title_report.get("output")
    ending_start = max(0.0, duration - args.ending_aerial_duration_seconds)
    if ending_title_report.get("status") == "ready" and ending_title_output and Path(ending_title_output).exists():
        clips.append(
            {
                "role": "ending_city_aerial_title",
                "trackType": "video",
                "trackIndex": 2,
                "sourcePath": ending_title_output,
                "timelineStartSeconds": round(ending_start, 3),
                "durationSeconds": args.ending_aerial_duration_seconds,
                "sourceStartSeconds": 0.0,
                "sourceEndSeconds": args.ending_aerial_duration_seconds,
                "includeSourceAudio": False,
                "cityTitle": ending_city_title,
                "subtitle": ending_subtitle,
                "purpose": "client outro: aerial closing card with clean title typography",
            }
        )
    else:
        add_or_replace_aerial_clip(clips, aerial_path, ending_start, args.ending_aerial_duration_seconds, "ending_aerial_insert_v4")
    clips.sort(key=lambda item: (float(item.get("timelineStartSeconds") or 0), int(item.get("trackIndex") or 1)))
    blueprint["clips"] = clips
    blueprint["openingHook"] = {
        "status": "ready" if city_title_report.get("status") == "ready" else "fallback_aerial_only",
        "cityTitle": city_title,
        "subtitle": opening_subtitle,
        "aerialSource": aerial_path,
        "titleClip": city_title_output if city_title_report.get("status") == "ready" else None,
        "rule": "First viewport must be city aerial/establishing video with clean city title; no internal IDs or black placeholder slates.",
    }
    blueprint["endingHook"] = {
        "status": "ready" if ending_title_report.get("status") == "ready" else "fallback_aerial_only",
        "cityTitle": ending_city_title,
        "subtitle": ending_subtitle,
        "aerialSource": aerial_path,
        "titleClip": ending_title_output if ending_title_report.get("status") == "ready" else None,
        "rule": "Final seconds should close on aerial/establishing video with clean typography, not a plain slate.",
    }
    blueprint["visualNormalizationPolicy"] = {
        "status": "planned",
        "targetCanvas": "3840x2160 landscape",
        "rules": [
            "Do not mix portrait/rotated clips raw into the final horizontal master.",
            "Landscape source should fill the frame; portrait clips require approved crop/blur/matte treatment or exclusion.",
            "Derived prior exports must be excluded unless explicitly approved as source material.",
        ],
    }
    blueprint["effectPlan"] = [
        {
            "name": "opening_title_reveal",
            "style": "slow aerial bed with clean city title overlay",
            "intensity": "restrained",
            "status": "planned_in_opening_title_clip",
        },
        {
            "name": "chapter_bridge_fades",
            "style": "short cross-dissolve or motion bridge over city/street establishing footage",
            "intensity": "subtle",
            "status": "planned_for_editor_or_resolve",
        },
    ]

    markers = blueprint.get("timelineMarkers") or []
    markers.append(
        {
            "role": "quality_recut",
            "name": "v4 quality rules",
            "startSeconds": 0,
            "durationSeconds": 5,
            "color": "Yellow",
            "note": "59.94fps, no voiceover audio, dense captions, audible BGM, aerial intro/outro.",
        }
    )
    blueprint["timelineMarkers"] = markers

    write_json(output_dir / "resolve_timeline_blueprint.json", blueprint)
    write_json(output_dir / "resolve_timeline_enrichment.json", enrichment)

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "prepared",
        "sourcePackage": str(source_dir),
        "outputDir": str(output_dir),
        "projectName": project_name,
        "timelineName": timeline_name,
        "fps": fps,
        "targetVideoBitrate": args.target_video_bitrate,
        "voiceoverDisabled": True,
        "captionCueCount": len(cues),
        "subtitleSidecar": str(captions_path),
        "narrationText": str(narration_txt),
        "aerialSource": aerial_path,
        "aerialSourceExists": bool(aerial_path and Path(aerial_path).exists()),
        "openingHook": blueprint["openingHook"],
        "endingHook": blueprint["endingHook"],
        "cityTitleClipReport": city_title_report,
        "endingCityTitleClipReport": ending_title_report,
        "titleCardReport": title_card_report,
        "nextCommands": [
            f"python3 <skill-dir>/scripts/audit_resolve_blueprint.py --blueprint {output_dir / 'resolve_timeline_blueprint.json'} --package-dir {output_dir}",
            f"python3 <skill-dir>/scripts/build_resolve_timeline.py --blueprint {output_dir / 'resolve_timeline_blueprint.json'} --apply",
            f"python3 <skill-dir>/scripts/prepare_resolve_render.py --package-dir {output_dir} --fps {fps} --custom-name {timeline_name.replace(' ', '_')}",
        ],
    }
    write_json(output_dir / "quality_recut_report.json", report)
    lines = [
        "# Quality Recut Report",
        "",
        f"Status: `{report['status']}`",
        f"Output package: `{output_dir}`",
        f"FPS: `{fps}`",
        f"Voiceover audio: `disabled`",
        f"Caption cues: `{len(cues)}`",
        f"Aerial source: `{aerial_path}`",
        "",
        "## Next Commands",
    ]
    lines.extend(f"- `{cmd}`" for cmd in report["nextCommands"])
    write_text(output_dir / "quality_recut_report.md", "\n".join(lines) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a high-fps no-voiceover quality recut package.")
    parser.add_argument("--source-package", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--fps", type=float, default=59.94)
    parser.add_argument("--target-duration-seconds", type=float, default=1200.0)
    parser.add_argument("--target-video-bitrate", default="80M")
    parser.add_argument("--caption-interval-seconds", type=float, default=24.0)
    parser.add_argument("--caption-duration-seconds", type=float, default=5.5)
    parser.add_argument("--city-title")
    parser.add_argument("--opening-subtitle")
    parser.add_argument("--opening-aerial-duration-seconds", type=float, default=8.0)
    parser.add_argument("--ending-city-title")
    parser.add_argument("--ending-subtitle")
    parser.add_argument("--ending-aerial-duration-seconds", type=float, default=8.0)
    parser.add_argument("--project-name")
    parser.add_argument("--timeline-name")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_quality_package(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Prepared quality recut package: {report['outputDir']}")
        print(f"Caption cues: {report['captionCueCount']}")
        print(f"Voiceover disabled: {report['voiceoverDisabled']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
