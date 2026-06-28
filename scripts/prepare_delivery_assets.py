#!/usr/bin/env python3
"""Prepare local delivery assets for a Travel Video Studio package."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from enrich_resolve_blueprint import enrich_package
from generate_title_cards import card_specs, find_font, make_card_png, make_mp4, update_blueprint
from make_voiceover_audio import run_tts


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_title_cards(package_dir: Path, force: bool, fps: float) -> dict[str, Any]:
    delivery_path = package_dir / "delivery_plan.json"
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    output = package_dir / "title_cards"
    manifest_path = output / "title_cards_manifest.json"
    if manifest_path.exists() and not force:
        manifest = load_json(manifest_path)
        cards = manifest.get("cards") or []
        missing = [card for card in cards if not card.get("mp4") or not Path(card["mp4"]).exists()]
        if blueprint_path.exists() and cards and not missing:
            update_blueprint(blueprint_path, manifest, fps)
        return {
            "status": "exists" if cards and not missing else "partial",
            "manifest": str(manifest_path),
            "cardCount": len(cards),
            "created": False,
            "missingVideos": missing,
        }
    if not delivery_path.exists():
        raise SystemExit(f"Missing delivery plan: {delivery_path}")
    if not blueprint_path.exists():
        raise SystemExit(f"Missing Resolve blueprint: {blueprint_path}")
    delivery = load_json(delivery_path)
    cards = []
    resolution = load_json(blueprint_path).get("resolution") if blueprint_path.exists() else {}
    width = int((resolution or {}).get("width") or 3840)
    height = int((resolution or {}).get("height") or 2160)
    output.mkdir(parents=True, exist_ok=True)
    for spec in card_specs(delivery):
        stem = spec["id"]
        png = output / f"{stem}.png"
        mp4 = output / f"{stem}.mp4"
        make_card_png(png, spec["title"], spec["subtitle"], width, height)
        ok = make_mp4(png, mp4, spec["durationSeconds"], fps)
        cards.append({**spec, "png": str(png), "mp4": str(mp4) if ok else None, "videoCreated": ok})
    manifest = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "cards": cards,
        "font": find_font(),
    }
    write_json(manifest_path, manifest)
    update_blueprint(blueprint_path, manifest, fps)
    return {
        "status": "ready" if all(card["videoCreated"] for card in cards) else "partial",
        "manifest": str(manifest_path),
        "cardCount": len(cards),
        "created": True,
        "missingVideos": [card for card in cards if not card["videoCreated"]],
    }


def prepare_voiceover(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    script_path = package_dir / "voiceover_script.txt"
    output_dir = package_dir / "voiceover"
    audio_path = output_dir / "voiceover.m4a"
    if audio_path.exists() and not args.force_voiceover:
        return {
            "status": "exists",
            "generated": False,
            "audio": str(audio_path),
            "requiresExplicitFlag": False,
        }
    if not args.generate_local_voiceover:
        return {
            "status": "pending_explicit_generation",
            "generated": False,
            "audio": str(audio_path),
            "requiresExplicitFlag": True,
            "command": f"python3 <skill-dir>/scripts/prepare_delivery_assets.py --package-dir {package_dir} --generate-local-voiceover",
        }
    if not script_path.exists():
        raise SystemExit(f"Missing voiceover script: {script_path}")
    tts_args = argparse.Namespace(script=str(script_path), output_dir=str(output_dir), voice=args.voice, rate=args.rate)
    result = run_tts(tts_args)
    voiceover_srt = output_dir / "subtitles.srt"
    if voiceover_srt.exists():
        shutil.copyfile(voiceover_srt, package_dir / "subtitles.srt")
    return {
        "status": "ready" if result.get("m4a") or result.get("aiff") else "partial",
        "generated": True,
        "result": result,
        "rootSubtitlesUpdated": voiceover_srt.exists(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Delivery Assets Report",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Title Cards",
        f"- Status: `{report['titleCards']['status']}`",
        f"- Manifest: `{report['titleCards'].get('manifest')}`",
        f"- Card count: {report['titleCards'].get('cardCount')}",
        "",
        "## Voiceover",
        f"- Status: `{report['voiceover']['status']}`",
        f"- Generated: `{report['voiceover'].get('generated')}`",
    ]
    if report["voiceover"].get("command"):
        lines.append(f"- Command: `{report['voiceover']['command']}`")
    lines.extend(
        [
            "",
            "## Resolve Enrichment",
            f"- Refreshed: `{report['resolveEnrichment'].get('refreshed')}`",
            f"- Subtitle cues: {report['resolveEnrichment'].get('subtitleCueCount')}",
            f"- Timeline markers: {report['resolveEnrichment'].get('timelineMarkerCount')}",
            "",
            "## Blockers",
        ]
    )
    lines.extend(f"- {item}" for item in report["blockers"] or ["None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_assets(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    if not package_dir.exists():
        raise SystemExit(f"Package directory not found: {package_dir}")
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json")
    fps = float(blueprint.get("fps") or args.fps or 25)
    title_cards = generate_title_cards(package_dir, force=args.force_title_cards, fps=fps)
    voiceover = prepare_voiceover(package_dir, args)
    enrichment = enrich_package(package_dir, update_blueprint=True)
    enrichment_summary = enrichment.get("summary") or {}
    blockers = []
    if title_cards.get("status") not in {"ready", "exists"}:
        blockers.append("Title/place cards are not fully generated.")
    if voiceover.get("status") not in {"ready", "exists"}:
        blockers.append("Voiceover audio still needs explicit local TTS generation or recorded audio.")
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "packageDir": str(package_dir),
        "status": "blocked" if blockers else "ready",
        "titleCards": title_cards,
        "voiceover": voiceover,
        "resolveEnrichment": {
            "refreshed": True,
            "subtitleCueCount": enrichment_summary.get("subtitleCueCount", 0),
            "timelineMarkerCount": enrichment_summary.get("timelineMarkerCount", 0),
            "voiceoverExists": enrichment_summary.get("voiceoverExists"),
        },
        "blockers": blockers,
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "generatesLocalTtsOnlyWithFlag": True,
        },
    }
    write_json(package_dir / "delivery_assets_report.json", report)
    write_markdown(package_dir / "delivery_assets_report.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare local title cards, optional local TTS, and Resolve enrichment for a package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--generate-local-voiceover", action="store_true", help="Use local macOS say TTS for the voiceover.")
    parser.add_argument("--force-title-cards", action="store_true")
    parser.add_argument("--force-voiceover", action="store_true")
    parser.add_argument("--voice", help="macOS voice name for local TTS.")
    parser.add_argument("--rate", type=int, default=175)
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = prepare_assets(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Delivery asset preparation status: {report['status']}")
        print(f"Title cards: {report['titleCards']['status']}")
        print(f"Voiceover: {report['voiceover']['status']}")
        for blocker in report["blockers"]:
            print(f"BLOCKER: {blocker}")
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
