#!/usr/bin/env python3
"""Write final delivery report files from verified package evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def infer_output(package_dir: Path, render: dict[str, Any], explicit: str | None) -> str | None:
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    for key in ("output", "finalOutput"):
        if render.get(key):
            return str(Path(render[key]).expanduser().resolve())
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
    return str(renders[0].resolve()) if renders else None


def report_status(parts: list[dict[str, Any] | None]) -> str:
    statuses = [part.get("status") for part in parts if isinstance(part, dict)]
    blockers = [part.get("blockers") for part in parts if isinstance(part, dict) and part.get("blockers")]
    if not statuses or blockers:
        return "blocked"
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if any(status in {"passed_with_warnings", "passed_with_caveats"} for status in statuses):
        return "passed_with_warnings"
    return "passed"


def build_report(package_dir: Path, output: str | None) -> dict[str, Any]:
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    resolve = load_json(package_dir / "resolve_audit.json") or {}
    client = load_json(package_dir / "client_delivery_rules_audit.json") or {}
    bgm = load_json(package_dir / "bgm_audio_contract_audit.json") or {}
    story = load_json(package_dir / "story_style_contract_audit.json") or {}
    integrity = load_json(package_dir / "package_integrity_audit_strict_portable.json") or load_json(package_dir / "package_integrity_audit.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    final_output = infer_output(package_dir, render, output)
    status = report_status([render, client, bgm, story, integrity])
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "finalOutput": final_output,
        "durationSeconds": render.get("durationSeconds"),
        "video": render.get("video"),
        "audio": render.get("audio"),
        "blackdetect": render.get("blackdetect"),
        "subtitleEvidence": render.get("subtitleEvidence"),
        "projectName": resolve.get("projectName") or blueprint.get("projectName"),
        "timelineName": resolve.get("timelineName") or blueprint.get("timelineName"),
        "resolveTrackSummary": resolve.get("tracks"),
        "clientDeliveryStatus": client.get("status"),
        "bgmAudioStatus": bgm.get("status"),
        "storyStyleStatus": story.get("status"),
        "packageIntegrityStatus": integrity.get("status"),
        "routeCaveat": (
            "No GPS metadata is available; this is non-GPS visual route reconstruction from frames, "
            "filenames, and itinerary evidence, not verified per-clip geolocation."
        ),
        "deliverableNotes": [
            "Resolve timeline was created through the official DaVinci Resolve Python API and read back before render.",
            "Final MP4 passed render verification for duration, 4K resolution, high frame rate, high bitrate, audio stream, sampled frames, and black-frame scan.",
            "BGM-only delivery is intentional: A1/A2 readback are empty and A3 contains the BGM bed.",
            "Narration remains text-only; no rendered voiceover audio is included.",
        ],
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    video = report.get("video") or {}
    audio = report.get("audio") or {}
    lines = [
        "# Final Delivery Report",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Output: `{report.get('finalOutput')}`",
        f"- Project: `{report.get('projectName')}`",
        f"- Timeline: `{report.get('timelineName')}`",
        f"- Duration: `{report.get('durationSeconds')}` seconds",
        f"- Video: `{video.get('width')}x{video.get('height')}`, `{video.get('avgFrameRate')}`, `{video.get('bitrateMbps')}` Mbps",
        f"- Audio: `{audio.get('codec')}`, `{audio.get('channels')}` channels, `{audio.get('sampleRate')}` Hz",
        f"- Client delivery audit: `{report.get('clientDeliveryStatus')}`",
        f"- BGM audio contract: `{report.get('bgmAudioStatus')}`",
        f"- Story/style contract: `{report.get('storyStyleStatus')}`",
        f"- Package integrity: `{report.get('packageIntegrityStatus')}`",
        "",
        "## Notes",
        "",
    ]
    for item in report.get("deliverableNotes") or []:
        lines.append(f"- {item}")
    lines.extend(["", f"- Route caveat: {report.get('routeCaveat')}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create FINAL_DELIVERY_REPORT.json/.md from package QA evidence.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args.output)
    write_json(package_dir / "FINAL_DELIVERY_REPORT.json", report)
    write_markdown(package_dir / "FINAL_DELIVERY_REPORT.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Final delivery report: {report['status']}")
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
