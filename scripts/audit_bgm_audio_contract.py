#!/usr/bin/env python3
"""Audit the BGM-only audio contract from manifest to final render."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED_STATUSES = {"passed", "passed_with_warnings", "passed_with_caveats"}
SCENIC_ROLE_TOKENS = ("opening", "ending", "title", "bridge", "aerial", "establish", "transition", "visual_bed")
FORBIDDEN_AUDIO_ROLE_TOKENS = ("source", "camera", "voice", "voiceover", "dialogue", "dialog", "mic", "microphone")


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ffprobe_json(path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return json.loads(proc.stdout)


def duration_from_probe(probe: dict[str, Any]) -> float:
    try:
        return float((probe.get("format") or {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def audio_streams(probe: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in probe.get("streams", []) if row.get("codec_type") == "audio"]


def resolve_path(value: Any) -> Path | None:
    if not value:
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except Exception:
        return None


def is_inside(path: Path | None, root: Path) -> bool:
    if not path:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def infer_output(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for report_name in ("render_delivery_verification.json", "FINAL_DELIVERY_REPORT.json"):
        report = load_json(package_dir / report_name) or {}
        candidate = report.get("output") or report.get("finalOutput")
        path = resolve_path(candidate)
        if path and path.exists():
            return path
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
    return renders[0].resolve() if renders else None


def infer_blueprint(package_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (package_dir / "resolve_timeline_blueprint.json").resolve()


def infer_bgm_manifest(package_dir: Path, blueprint: dict[str, Any], explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    for key in ("bgmManifest", "bgm_manifest"):
        path = resolve_path(assets.get(key))
        if path and path.exists():
            return path
    for cue in (blueprint.get("audioPlan") or {}).get("bgmCues") or []:
        if isinstance(cue, dict):
            path = resolve_path(cue.get("manifest"))
            if path and path.exists():
                return path
    candidates = sorted((package_dir / "bgm").glob("*manifest*.json"))
    return candidates[-1].resolve() if candidates else None


def infer_visual_audio_audit(package_dir: Path) -> Path | None:
    default = package_dir / "visual_audio_style_audit" / "visual_audio_style_audit.json"
    if default.exists():
        return default.resolve()
    candidates = [
        path
        for path in (package_dir / "qa").glob("**/visual_audio_style_audit.json")
        if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime).resolve()


def track_count(resolve_audit: dict[str, Any], kind: str, index: int) -> int | None:
    for row in (resolve_audit.get("tracks") or {}).get(kind, []) or []:
        try:
            if int(row.get("index")) == index:
                return int(row.get("itemCount") or 0)
        except (TypeError, ValueError):
            continue
    return None


def clip_start(clip: dict[str, Any]) -> float:
    for key in ("timelineStartSeconds", "recordStartSeconds", "startSeconds"):
        try:
            return float(clip.get(key))
        except (TypeError, ValueError):
            continue
    return 0.0


def clip_end(clip: dict[str, Any]) -> float:
    for key in ("timelineEndSeconds", "recordEndSeconds", "endSeconds"):
        try:
            return float(clip.get(key))
        except (TypeError, ValueError):
            continue
    start = clip_start(clip)
    for key in ("durationSeconds", "duration", "sourceDurationSeconds"):
        try:
            duration = float(clip.get(key))
            if duration > 0:
                return start + duration
        except (TypeError, ValueError):
            continue
    try:
        return start + max(0.0, float(clip.get("sourceEndSeconds") or 0) - float(clip.get("sourceStartSeconds") or 0))
    except (TypeError, ValueError):
        return start


def intervals_overlap(start_a: float, end_a: float, start_b: float, end_b: float, tolerance: float = 0.05) -> bool:
    return start_a < end_b - tolerance and start_b < end_a - tolerance


def role_text(clip: dict[str, Any]) -> str:
    return " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "name", "type")).lower()


def clip_summary(clip: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": clip.get("role") or clip.get("purpose"),
        "trackType": clip.get("trackType"),
        "trackIndex": clip.get("trackIndex"),
        "start": round(clip_start(clip), 3),
        "end": round(clip_end(clip), 3),
        "source": clip.get("sourcePath"),
        "includeSourceAudio": clip.get("includeSourceAudio"),
        "preserveSourceAudio": clip.get("preserveSourceAudio"),
        "sourceAudio": clip.get("sourceAudio"),
    }


def path_set(values: list[Any]) -> set[str]:
    out: set[str] = set()
    for value in values:
        path = resolve_path(value)
        if path:
            out.add(str(path))
    return out


def scenic_source_audio_flags(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for clip in blueprint.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        role = str(clip.get("role") or clip.get("purpose") or "").lower()
        if not any(token in role for token in SCENIC_ROLE_TOKENS):
            continue
        if clip.get("trackType") == "audio":
            continue
        if clip.get("includeSourceAudio") is True or clip.get("preserveSourceAudio") is True or clip.get("sourceAudio") is True:
            flags.append(
                {
                    "role": clip.get("role") or clip.get("purpose"),
                    "start": clip.get("timelineStartSeconds"),
                    "source": clip.get("sourcePath"),
                    "includeSourceAudio": clip.get("includeSourceAudio"),
                    "preserveSourceAudio": clip.get("preserveSourceAudio"),
                    "sourceAudio": clip.get("sourceAudio"),
                }
            )
    return flags


def scenic_audio_overlap_flags(blueprint: dict[str, Any]) -> dict[str, Any]:
    clips = [clip for clip in blueprint.get("clips") or [] if isinstance(clip, dict)]
    scenic_windows: list[dict[str, Any]] = []
    forbidden_audio: list[dict[str, Any]] = []
    overlaps: list[dict[str, Any]] = []
    for clip in clips:
        role = role_text(clip)
        track_type = str(clip.get("trackType") or "").lower()
        if track_type == "audio":
            continue
        if any(token in role for token in SCENIC_ROLE_TOKENS):
            scenic_windows.append(clip)
    for clip in clips:
        role = role_text(clip)
        track_type = str(clip.get("trackType") or "").lower()
        try:
            track_index = int(clip.get("trackIndex") or 0)
        except (TypeError, ValueError):
            track_index = 0
        is_audio = track_type == "audio" or ("audio" in role and "subtitle" not in role)
        is_bgm = "bgm" in role or "music" in role or track_index == 3
        forbidden_role = any(token in role for token in FORBIDDEN_AUDIO_ROLE_TOKENS)
        if is_audio and not is_bgm and (track_index in {1, 2} or forbidden_role):
            forbidden_audio.append(clip)
    for window in scenic_windows:
        window_start = clip_start(window)
        window_end = clip_end(window)
        for audio in forbidden_audio:
            if intervals_overlap(window_start, window_end, clip_start(audio), clip_end(audio)):
                overlaps.append({"scenicWindow": clip_summary(window), "audioClip": clip_summary(audio)})
    return {
        "scenicWindowCount": len(scenic_windows),
        "forbiddenAudioClipCount": len(forbidden_audio),
        "overlapCount": len(overlaps),
        "overlaps": overlaps[:30],
    }


def find_check(report: dict[str, Any], needle: str) -> dict[str, Any] | None:
    needle_l = needle.lower()
    for row in report.get("checks") or []:
        text = str(row.get("name") or row.get("requirement") or "").lower()
        if needle_l in text:
            return row
    return None


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = infer_blueprint(package_dir, args.blueprint)
    blueprint = load_json(blueprint_path)
    output = infer_output(package_dir, args.output)
    if not isinstance(blueprint, dict):
        blueprint = {}
    bgm_manifest_path = infer_bgm_manifest(package_dir, blueprint, args.bgm_manifest)
    bgm_manifest = load_json(bgm_manifest_path)
    if not isinstance(bgm_manifest, dict):
        bgm_manifest = {}

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    def add(name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
        status = "passed" if passed else ("warning" if warning else "blocked")
        checks.append({"name": name, "status": status, "evidence": evidence})
        if status == "blocked":
            blockers.append(name)
        elif status == "warning":
            warnings.append(name)

    add("Resolve blueprint exists", bool(blueprint), {"path": str(blueprint_path)})
    add("BGM manifest exists", bool(bgm_manifest), {"path": str(bgm_manifest_path) if bgm_manifest_path else None})
    add("Final render exists", bool(output and output.exists()), {"output": str(output) if output else None})

    final_probe: dict[str, Any] = {}
    final_duration = 0.0
    if output and output.exists():
        final_probe = ffprobe_json(output)
        final_duration = duration_from_probe(final_probe)
        add(
            "Final render has an audio stream",
            bool(audio_streams(final_probe)),
            {"audioStreams": audio_streams(final_probe), "durationSeconds": final_duration},
        )

    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    audio_plan = blueprint.get("audioPlan") if isinstance(blueprint.get("audioPlan"), dict) else {}
    bgm_assets = path_set(assets.get("bgm") if isinstance(assets.get("bgm"), list) else [])
    manifest_output = resolve_path(bgm_manifest.get("output"))
    manifest_mode = str(bgm_manifest.get("mode") or "").lower()
    manifest_tracks = bgm_manifest.get("tracks") if isinstance(bgm_manifest.get("tracks"), list) else []
    bad_tracks: list[dict[str, Any]] = []
    mood_text = " ".join(
        str(track.get(key) or "")
        for track in manifest_tracks
        if isinstance(track, dict)
        for key in ("name", "genre", "mood", "artist")
    ).lower()
    for index, track in enumerate(manifest_tracks):
        if not isinstance(track, dict):
            bad_tracks.append({"index": index, "reason": "track is not an object"})
            continue
        track_path = resolve_path(track.get("path"))
        license_url = str(track.get("license") or "")
        if not track_path or not track_path.exists():
            bad_tracks.append({"index": index, "reason": "missing local file", "path": track.get("path")})
        if not license_url.startswith(("http://", "https://", "local-original-audio://")):
            bad_tracks.append({"index": index, "reason": "missing license URL", "license": license_url})
    add(
        "BGM manifest declares BGM-only no-camera-voice mode",
        "bgm" in manifest_mode and "camera" in manifest_mode and "voice" in manifest_mode,
        {"mode": bgm_manifest.get("mode")},
    )
    add(
        "BGM manifest output matches Resolve blueprint BGM asset",
        bool(manifest_output and str(manifest_output) in bgm_assets),
        {
            "manifestOutput": str(manifest_output) if manifest_output else None,
            "blueprintBgmAssets": sorted(bgm_assets),
        },
    )
    add(
        "BGM bed is materialized inside the current package",
        bool(manifest_output and manifest_output.exists() and (args.allow_external_bgm_bed or is_inside(manifest_output, package_dir))),
        {"manifestOutput": str(manifest_output) if manifest_output else None, "allowExternalBgmBed": args.allow_external_bgm_bed},
    )
    bgm_probe = ffprobe_json(manifest_output) if manifest_output and manifest_output.exists() else {}
    bgm_duration = duration_from_probe(bgm_probe) if bgm_probe else 0.0
    duration_target = 0.0
    try:
        duration_target = float(bgm_manifest.get("durationTargetSeconds") or 0.0)
    except (TypeError, ValueError):
        duration_target = 0.0
    duration_required = max(0.0, final_duration - args.duration_slack_seconds) * args.min_bgm_duration_ratio
    add(
        "BGM bed duration covers the final render",
        bool(bgm_duration and final_duration and bgm_duration >= duration_required and duration_target >= duration_required),
        {
            "bgmDurationSeconds": bgm_duration,
            "durationTargetSeconds": duration_target,
            "finalDurationSeconds": final_duration,
            "requiredSeconds": duration_required,
        },
    )
    add(
        "BGM source tracks are traceable and travel-appropriate",
        bool(manifest_tracks) and not bad_tracks and any(term in mood_text for term in args.allowed_mood_terms),
        {
            "trackCount": len(manifest_tracks),
            "badTracks": bad_tracks[:20],
            "allowedMoodTerms": args.allowed_mood_terms,
            "moodTextSample": mood_text[:500],
        },
    )

    cues = audio_plan.get("bgmCues") if isinstance(audio_plan.get("bgmCues"), list) else []
    ready_cues = [cue for cue in cues if isinstance(cue, dict) and str(cue.get("status") or "").lower() == "ready"]
    bad_cues = []
    for cue in ready_cues:
        try:
            start = float(cue.get("timelineStartSeconds") or 0.0)
            duration = float(cue.get("durationSeconds") or 0.0)
        except (TypeError, ValueError):
            start = 999.0
            duration = 0.0
        if start > 0.5 or duration < duration_required or int(cue.get("trackIndex") or 0) != 3:
            bad_cues.append(cue)
    add(
        "Resolve blueprint has a full-film A3 BGM cue",
        bool(ready_cues) and not bad_cues and "bgm" in str(audio_plan.get("mode") or "").lower(),
        {
            "audioPlanMode": audio_plan.get("mode"),
            "readyCueCount": len(ready_cues),
            "badCues": bad_cues[:10],
            "cues": ready_cues[:5],
        },
    )
    source_audio = audio_plan.get("sourceAudio") if isinstance(audio_plan.get("sourceAudio"), dict) else {}
    voiceover = audio_plan.get("voiceover") if isinstance(audio_plan.get("voiceover"), dict) else {}
    scenic_flags = scenic_source_audio_flags(blueprint)
    scenic_overlap_flags = scenic_audio_overlap_flags(blueprint)
    add(
        "Voiceover and source-camera audio are disabled for BGM-only delivery",
        str(audio_plan.get("mode") or "").lower().find("no_camera_voice") >= 0
        and str(source_audio.get("status") or "").lower().find("disabled") >= 0
        and str(voiceover.get("status") or "").lower().find("disabled") >= 0
        and not (assets.get("voiceover") if isinstance(assets, dict) else None)
        and not scenic_flags,
        {
            "audioPlanMode": audio_plan.get("mode"),
            "sourceAudio": source_audio,
            "voiceover": voiceover,
            "voiceoverAsset": assets.get("voiceover") if isinstance(assets, dict) else None,
            "scenicSourceAudioFlags": scenic_flags[:20],
        },
    )
    add(
        "Scenic/title/transition windows have no A1/A2 voice or source-audio overlaps",
        scenic_overlap_flags["overlapCount"] == 0,
        scenic_overlap_flags,
    )

    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    a1_count = track_count(resolve_audit, "audio", 1)
    a2_count = track_count(resolve_audit, "audio", 2)
    a3_count = track_count(resolve_audit, "audio", 3)
    add(
        "DaVinci readback has A3 BGM and no A1/A2 voice/source items",
        (a1_count in {0, None}) and (a2_count in {0, None}) and (a3_count or 0) >= 1,
        {"A1": a1_count, "A2": a2_count, "A3": a3_count},
    )

    visual_audit_path = infer_visual_audio_audit(package_dir)
    visual = load_json(visual_audit_path) or {}
    audio_analysis = visual.get("audioAnalysis") if isinstance(visual.get("audioAnalysis"), dict) else {}
    loudness = audio_analysis.get("loudness") if isinstance(audio_analysis.get("loudness"), dict) else {}
    integrated = loudness.get("integratedLufs")
    silence_ratio = audio_analysis.get("silenceRatio")
    try:
        integrated_ok = integrated is not None and float(integrated) >= args.min_integrated_lufs
        silence_ok = silence_ratio is not None and float(silence_ratio) <= args.max_silence_ratio
    except (TypeError, ValueError):
        integrated_ok = False
        silence_ok = False
    add(
        "Rendered BGM is audible and not mostly silent",
        visual.get("status") == "passed" and str(visual.get("audioMode") or "") == args.audio_mode and integrated_ok and silence_ok,
        {
            "visualAudioStatus": visual.get("status"),
            "visualAudioAudit": str(visual_audit_path) if visual_audit_path else None,
            "audioMode": visual.get("audioMode"),
            "integratedLufs": integrated,
            "silenceRatio": silence_ratio,
            "minIntegratedLufs": args.min_integrated_lufs,
            "maxSilenceRatio": args.max_silence_ratio,
        },
    )

    feedback = load_json(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json") or {}
    feedback_bgm_check = find_check(feedback, "BGM-only mix")
    add(
        "Feedback/title timestamps prove audible BGM and no leaked voice",
        bool(feedback_bgm_check and feedback_bgm_check.get("status") in PASSED_STATUSES),
        {"feedbackStatus": feedback.get("status"), "bgmCheck": feedback_bgm_check},
        warning=not bool(feedback_bgm_check),
    )

    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    ledger_items = ledger.get("items") if isinstance(ledger.get("items"), list) else []
    bgm_items = [item for item in ledger_items if isinstance(item, dict) and item.get("type") == "bgm"]
    ledger_paths = path_set([item.get("localPath") for item in bgm_items])
    add(
        "Asset ledger verifies the actual BGM bed used in Resolve",
        bool(ledger)
        and ledger.get("finalReady") is True
        and bool(bgm_items)
        and bool(ledger_paths & ({str(manifest_output)} if manifest_output else set()) | (ledger_paths & bgm_assets))
        and all(str(item.get("licenseStatus") or "").lower().find("verified") >= 0 for item in bgm_items),
        {
            "ledger": str(package_dir / "asset_ledger" / "asset_license_ledger.json"),
            "finalReady": ledger.get("finalReady"),
            "bgmItemCount": len(bgm_items),
            "ledgerBgmPaths": sorted(ledger_paths),
            "manifestOutput": str(manifest_output) if manifest_output else None,
            "blueprintBgmAssets": sorted(bgm_assets),
        },
    )

    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "finalOutput": str(output) if output else None,
        "blueprint": str(blueprint_path),
        "bgmManifest": str(bgm_manifest_path) if bgm_manifest_path else None,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BGM Audio Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Final output: `{report.get('finalOutput')}`",
        f"BGM manifest: `{report.get('bgmManifest')}`",
        "",
        "## Checks",
    ]
    for row in report.get("checks", []):
        lines.extend(
            [
                "",
                f"### {row['name']}",
                f"- Status: `{row['status']}`",
                f"- Evidence: `{json.dumps(row['evidence'], ensure_ascii=False)[:1800]}`",
            ]
        )
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit BGM-only audio evidence from source manifest to final render.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output")
    parser.add_argument("--blueprint")
    parser.add_argument("--bgm-manifest")
    parser.add_argument("--audio-mode", choices=["bgm_only", "bgm_dominant"], default="bgm_only")
    parser.add_argument("--allow-external-bgm-bed", action="store_true")
    parser.add_argument("--min-bgm-duration-ratio", type=float, default=0.99)
    parser.add_argument("--duration-slack-seconds", type=float, default=1.0)
    parser.add_argument("--min-integrated-lufs", type=float, default=-35.0)
    parser.add_argument("--max-silence-ratio", type=float, default=0.15)
    parser.add_argument(
        "--allowed-mood-terms",
        nargs="+",
        default=["serene", "calm", "ambient", "chillout", "cinematic", "film", "piano", "soft", "travel"],
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        package_dir = Path(args.package_dir).expanduser().resolve()
        report = build_report(package_dir, args)
        write_json(package_dir / "bgm_audio_contract_audit.json", report)
        write_markdown(package_dir / "bgm_audio_contract_audit.md", report)
    except Exception as exc:
        print(f"audit_bgm_audio_contract failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "warnings": report["warnings"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
