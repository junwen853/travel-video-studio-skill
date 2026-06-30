#!/usr/bin/env python3
"""Enrich a Resolve blueprint with subtitle, audio, stock, transition, and marker plans."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


SRT_TIME_RE = re.compile(
    r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})\s+-->\s+"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def srt_seconds(match: re.Match[str], prefix: str) -> float:
    hours = int(match.group(f"{prefix}h"))
    minutes = int(match.group(f"{prefix}m"))
    seconds = int(match.group(f"{prefix}s"))
    millis = int(match.group(f"{prefix}ms"))
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def parse_srt(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    chunks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
    cues: list[dict[str, Any]] = []
    for chunk in chunks:
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_index = next((idx for idx, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            continue
        match = SRT_TIME_RE.search(lines[time_index])
        if not match:
            continue
        text = "\n".join(lines[time_index + 1 :]).strip()
        start = srt_seconds(match, "s")
        end = srt_seconds(match, "e")
        cues.append(
            {
                "index": len(cues) + 1,
                "startSeconds": round(start, 3),
                "endSeconds": round(end, 3),
                "durationSeconds": round(max(0.0, end - start), 3),
                "text": text,
                "status": "estimated_timing",
            }
        )
    return cues


def ffprobe_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


def section_for_chapter(delivery: dict[str, Any], chapter_index: Any) -> dict[str, Any] | None:
    for section in delivery.get("longFormSections") or []:
        if section.get("chapterIndex") == chapter_index:
            return section
    return None


def marker(start: float, duration: float, color: str, name: str, note: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "startSeconds": round(max(0.0, start), 3),
        "durationSeconds": round(max(1.0, duration), 3),
        "color": color,
        "name": name,
        "note": note,
        "role": role,
        "customData": payload,
    }


def chapter_markers(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    markers = []
    for section in delivery.get("longFormSections") or []:
        role = str(section.get("targetRole") or "chapter")
        place = str(section.get("place") or "Chapter")
        markers.append(
            marker(
                float(section.get("startSeconds") or 0),
                min(10.0, float(section.get("durationSeconds") or 1)),
                "Blue" if section.get("chapterIndex") not in {0, 999} else "Green",
                f"CHAPTER {section.get('chapterIndex')}: {place}",
                f"{role}; {section.get('voiceoverPolicy') or ''}".strip(),
                "chapter",
                {"chapterIndex": section.get("chapterIndex"), "place": place, "targetRole": role},
            )
        )
    return markers


def voiceover_plan(delivery: dict[str, Any], blueprint: dict[str, Any]) -> dict[str, Any]:
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    path = Path(str(assets.get("voiceover") or "")).expanduser()
    duration = ffprobe_duration(path) if str(path) else None
    return {
        "role": "voiceover",
        "trackIndex": 2,
        "sourcePath": str(path) if str(path) else "",
        "exists": path.exists() if str(path) else False,
        "durationSeconds": duration,
        "timelineStartSeconds": 0.0,
        "targetMix": {
            "voicePriority": True,
            "suggestedPeakDb": -6,
            "duckBgmUnderVoiceDb": -24,
            "musicOnlyBedDb": -18,
        },
        "status": "ready_to_import" if path.exists() else "pending_tts_or_recording",
        "scriptFile": delivery.get("voiceover", {}).get("scriptFile"),
    }


def bgm_plan(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    plan = []
    for cue in delivery.get("bgmCues") or []:
        section = section_for_chapter(delivery, cue.get("chapterIndex")) or {}
        start = float(section.get("startSeconds") or 0)
        duration = float(section.get("durationSeconds") or 180)
        plan.append(
            {
                "chapterIndex": cue.get("chapterIndex"),
                "place": cue.get("place"),
                "mood": cue.get("mood"),
                "timelineStartSeconds": round(start, 3),
                "durationSeconds": round(duration, 3),
                "trackIndex": 3,
                "fadeInSeconds": 2.5,
                "fadeOutSeconds": 3.5,
                "targetDbDuringVoiceover": -24,
                "targetDbMusicOnly": -18,
                "queries": cue.get("queries") or [],
                "licenseStatus": cue.get("licenseStatus") or "unverified",
                "status": "license_unverified_placeholder",
            }
        )
    return plan


def stock_plan(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    plan = []
    for block in delivery.get("assetSearch") or []:
        section = section_for_chapter(delivery, block.get("chapterIndex")) or {}
        section_start = float(section.get("startSeconds") or 0)
        section_duration = float(section.get("durationSeconds") or 120)
        for idx, target in enumerate(block.get("aerialTargets") or []):
            planned_start = section_start + min(section_duration - 8, 8 + idx * 18)
            plan.append(
                {
                    "chapterIndex": block.get("chapterIndex"),
                    "place": block.get("place"),
                    "target": target,
                    "timelineStartSeconds": round(max(section_start, planned_start), 3),
                    "durationSeconds": 5.0,
                    "trackIndex": 2,
                    "purpose": "establishing_or_transition_insert",
                    "queries": block.get("queries") or [],
                    "licenseStatus": block.get("licenseStatus") or "unverified",
                    "status": "license_unverified_placeholder",
                }
            )
    return plan


def transition_plan(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    plan = []
    sections = {section.get("chapterIndex"): section for section in delivery.get("longFormSections") or []}
    for transition in delivery.get("transitions") or []:
        section = sections.get(transition.get("afterChapter")) or {}
        start = float(section.get("startSeconds") or 0) + max(0.0, float(section.get("durationSeconds") or 0) - 12.0)
        plan.append(
            {
                "afterChapter": transition.get("afterChapter"),
                "bridge": transition.get("bridge"),
                "suggestion": transition.get("suggestion"),
                "timelineStartSeconds": round(start, 3),
                "durationSeconds": 8.0,
                "fallbackAssetNeed": transition.get("fallbackAssetNeed"),
                "status": "planned_bridge",
            }
        )
    return plan


def cue_markers(audio_plan: dict[str, Any], bgm: list[dict[str, Any]], stock: list[dict[str, Any]], transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = []
    if audio_plan.get("sourcePath"):
        markers.append(
            marker(
                float(audio_plan.get("timelineStartSeconds") or 0),
                min(10.0, float(audio_plan.get("durationSeconds") or 10)),
                "Purple",
                "VOICEOVER",
                f"{audio_plan.get('status')} | {audio_plan.get('sourcePath')}",
                "voiceover",
                {"trackIndex": audio_plan.get("trackIndex"), "sourcePath": audio_plan.get("sourcePath"), "status": audio_plan.get("status")},
            )
        )
    for item in bgm:
        markers.append(
            marker(
                item["timelineStartSeconds"],
                min(12.0, item["durationSeconds"]),
                "Cyan",
                f"BGM NEED: {item.get('place')}",
                f"{item.get('mood')} | {item.get('status')}",
                "bgm",
                item,
            )
        )
    for item in stock:
        markers.append(
            marker(
                item["timelineStartSeconds"],
                item["durationSeconds"],
                "Yellow",
                f"STOCK NEED: {item.get('target')}",
                f"{item.get('purpose')} | {item.get('status')}",
                "stock_or_aerial",
                item,
            )
        )
    for item in transitions:
        markers.append(
            marker(
                item["timelineStartSeconds"],
                item["durationSeconds"],
                "Orange",
                f"TRANSITION: {item.get('bridge')}",
                str(item.get("suggestion") or ""),
                "transition",
                item,
            )
        )
    return markers


def build_enrichment(delivery: dict[str, Any], blueprint: dict[str, Any], package_dir: Path) -> dict[str, Any]:
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    subtitle_path = Path(str(assets.get("subtitles") or delivery.get("subtitles", {}).get("srtFile") or package_dir / "subtitles.srt")).expanduser()
    subtitle_cues = parse_srt(subtitle_path)
    voice = voiceover_plan(delivery, blueprint)
    bgm = bgm_plan(delivery)
    stock = stock_plan(delivery)
    transitions = transition_plan(delivery)
    markers = chapter_markers(delivery) + cue_markers(voice, bgm, stock, transitions)
    enrichment = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "packageDir": str(package_dir),
        "sourceDeliveryPlan": str(package_dir / "delivery_plan.json"),
        "sourceBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
        "subtitlePlan": {
            "sourcePath": str(subtitle_path),
            "exists": subtitle_path.exists(),
            "cueCount": len(subtitle_cues),
            "status": "sidecar_srt_ready" if subtitle_cues else "missing_or_unparsed_srt",
            "resolveNativeStatus": "pending_import_or_burn_in_after_style_approval",
        },
        "subtitleCues": subtitle_cues,
        "audioPlan": {
            "voiceover": voice,
            "bgmCues": bgm,
            "sourceAudioPolicy": "keep original sound on A1 where useful; duck under voiceover and BGM during narration",
            "ambienceTrack": {"trackIndex": 4, "status": "planned_for_street_station_room_tone"},
        },
        "stockInsertPlan": stock,
        "transitionPlan": transitions,
        "timelineMarkers": sorted(markers, key=lambda item: (item["startSeconds"], item["role"], item["name"])),
        "summary": {
            "subtitleCueCount": len(subtitle_cues),
            "timelineMarkerCount": len(markers),
            "voiceoverExists": bool(voice.get("exists")),
            "bgmCueCount": len(bgm),
            "stockPlaceholderCount": len(stock),
            "transitionCount": len(transitions),
            "unverifiedBgmCueCount": sum(1 for item in bgm if item.get("status") == "license_unverified_placeholder"),
            "unverifiedStockPlaceholderCount": sum(1 for item in stock if item.get("status") == "license_unverified_placeholder"),
        },
        "status": "planned_with_placeholders",
        "readyRule": "Subtitle sidecar, voiceover audio, BGM and stock placeholders must be resolved into approved media or accepted sidecar handoff before final render.",
    }
    return enrichment


def apply_enrichment_to_blueprint(blueprint: dict[str, Any], enrichment: dict[str, Any]) -> dict[str, Any]:
    blueprint["subtitleCues"] = enrichment["subtitleCues"]
    blueprint["audioPlan"] = enrichment["audioPlan"]
    blueprint["stockInsertPlan"] = enrichment["stockInsertPlan"]
    blueprint["transitionPlan"] = enrichment["transitionPlan"]
    blueprint["timelineMarkers"] = enrichment["timelineMarkers"]
    blueprint["enrichmentSummary"] = enrichment["summary"]
    blueprint["enrichedAt"] = datetime.now().isoformat(timespec="seconds")
    notes = blueprint.setdefault("notes", [])
    note = "Blueprint includes subtitle/audio/BGM/stock/transition marker enrichment for Resolve long-form assembly."
    if note not in notes:
        notes.append(note)
    return blueprint


def enrich_package(package_dir: Path, update_blueprint: bool = True) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    delivery_path = package_dir / "delivery_plan.json"
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    if not delivery_path.exists():
        raise SystemExit(f"Missing delivery plan: {delivery_path}")
    if not blueprint_path.exists():
        raise SystemExit(f"Missing Resolve blueprint: {blueprint_path}")
    delivery = load_json(delivery_path)
    blueprint = load_json(blueprint_path)
    enrichment = build_enrichment(delivery, blueprint, package_dir)
    write_json(package_dir / "resolve_timeline_enrichment.json", enrichment)
    if update_blueprint:
        blueprint = apply_enrichment_to_blueprint(blueprint, enrichment)
        write_json(blueprint_path, blueprint)
    return enrichment


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich resolve_timeline_blueprint.json with long-form timeline plans.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--no-update-blueprint", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    enrichment = enrich_package(Path(args.package_dir), update_blueprint=not args.no_update_blueprint)
    if args.json:
        print(json.dumps(enrichment, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote Resolve timeline enrichment for {enrichment['packageDir']}")
        print(f"Subtitle cues: {enrichment['summary']['subtitleCueCount']}")
        print(f"Timeline markers: {enrichment['summary']['timelineMarkerCount']}")
        print(f"Stock placeholders: {enrichment['summary']['stockPlaceholderCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
