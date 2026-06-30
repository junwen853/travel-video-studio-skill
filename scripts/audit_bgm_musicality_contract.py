#!/usr/bin/env python3
"""Audit whether the BGM bed is real, musical, and phrase-usable."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


ACCEPTED_SELECTION_STATUSES = {"ready_with_materialized_bgm_selection_package"}
ACCEPTED_PHRASE_STATUSES = {"ready_with_bgm_phrase_blueprint"}
BAD_IDENTITY_TERMS = (
    "sine",
    "tone",
    "hum",
    "buzz",
    "beep",
    "procedural",
    "generated tone",
    "placeholder",
    "silence",
)
BAND_CENTERS = (80.0, 160.0, 320.0, 640.0, 1280.0, 2560.0, 4200.0)


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


def clean(value: Any, limit: int = 800) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def summary_of(report: Any) -> dict[str, Any]:
    return report.get("summary") if isinstance(report, dict) and isinstance(report.get("summary"), dict) else {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def resolve_path(value: Any, base: Path | None = None) -> Path | None:
    if not value:
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute() and base:
        path = base / path
    return path.resolve()


def infer_blueprint(package_dir: Path, explicit: str | None) -> Path:
    return resolve_path(explicit, package_dir) if explicit else (package_dir / "resolve_timeline_blueprint.json").resolve()


def infer_bgm_manifest(package_dir: Path, blueprint: dict[str, Any], explicit: str | None) -> Path | None:
    if explicit:
        return resolve_path(explicit, package_dir)
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    for key in ("bgmManifest", "bgm_manifest"):
        path = resolve_path(assets.get(key), package_dir)
        if path and path.exists():
            return path
    for cue in (blueprint.get("audioPlan") or {}).get("bgmCues") or []:
        if isinstance(cue, dict):
            path = resolve_path(cue.get("manifest"), package_dir)
            if path and path.exists():
                return path
    candidates = sorted((package_dir / "bgm").glob("*manifest*.json"))
    return candidates[-1].resolve() if candidates else None


def infer_bgm_output(package_dir: Path, manifest: dict[str, Any], blueprint: dict[str, Any], explicit: str | None) -> Path | None:
    if explicit:
        return resolve_path(explicit, package_dir)
    path = resolve_path(manifest.get("output"), package_dir)
    if path and path.exists():
        return path
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    rows = assets.get("bgm") if isinstance(assets.get("bgm"), list) else []
    for item in rows:
        candidate = resolve_path(item, package_dir)
        if candidate and candidate.exists():
            return candidate
    return None


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
    return as_float((probe.get("format") or {}).get("duration"), 0.0)


def decode_samples(path: Path, *, sample_rate: int, sample_seconds: float) -> list[float]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(path),
        "-t",
        f"{sample_seconds:.3f}",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "-",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    raw = proc.stdout
    if len(raw) < 2:
        return []
    return [value / 32768.0 for (value,) in struct.iter_unpack("<h", raw[: len(raw) - (len(raw) % 2)])]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[int(index)]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-9))


def goertzel_power(samples: list[float], sample_rate: int, frequency: float) -> float:
    if not samples:
        return 0.0
    n = len(samples)
    k = int(0.5 + (n * frequency) / sample_rate)
    omega = (2.0 * math.pi * k) / n
    coeff = 2.0 * math.cos(omega)
    q0 = q1 = q2 = 0.0
    for sample in samples:
        q0 = coeff * q1 - q2 + sample
        q2 = q1
        q1 = q0
    return max(0.0, q1 * q1 + q2 * q2 - coeff * q1 * q2)


def chunked(samples: list[float], size: int) -> list[list[float]]:
    return [samples[index : index + size] for index in range(0, len(samples), size) if len(samples[index : index + size]) >= size // 2]


def analyze_audio(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    probe = ffprobe_json(path)
    duration = duration_from_probe(probe)
    sample_seconds = min(max(duration, 0.0), args.sample_seconds)
    samples = decode_samples(path, sample_rate=args.sample_rate, sample_seconds=sample_seconds)
    if not samples:
        return {
            "path": str(path),
            "durationSeconds": duration,
            "analyzedSeconds": 0.0,
            "decodeFailed": True,
        }

    window_size = max(1, int(args.sample_rate * args.window_seconds))
    windows = chunked(samples, window_size)
    rms_values: list[float] = []
    peak_values: list[float] = []
    clipped_windows = 0
    for window in windows:
        rms = math.sqrt(sum(sample * sample for sample in window) / max(len(window), 1))
        peak = max(abs(sample) for sample in window)
        rms_values.append(rms)
        peak_values.append(peak)
        if peak >= args.clip_peak_threshold:
            clipped_windows += 1

    rms_db_values = [db(value) for value in rms_values]
    silent_windows = sum(1 for value in rms_db_values if value <= args.silent_window_db)
    dynamic_range = percentile(rms_db_values, 0.95) - percentile(rms_db_values, 0.10)

    band_chunks = chunked(samples, max(512, int(args.sample_rate * args.band_window_seconds)))
    band_totals = [0.0 for _ in BAND_CENTERS]
    window_active_counts: list[int] = []
    centroids: list[float] = []
    for window in band_chunks:
        powers = [goertzel_power(window, args.sample_rate, frequency) for frequency in BAND_CENTERS]
        total = sum(powers)
        if total <= 0.0:
            window_active_counts.append(0)
            centroids.append(0.0)
            continue
        for index, power in enumerate(powers):
            band_totals[index] += power
        max_power = max(powers)
        active = sum(1 for power in powers if max_power and power >= max_power * args.min_band_relative_energy)
        window_active_counts.append(active)
        centroids.append(sum(freq * power for freq, power in zip(BAND_CENTERS, powers)) / total)

    total_band_energy = sum(band_totals)
    active_band_count = 0
    single_band_dominance = 0.0
    if total_band_energy > 0.0:
        single_band_dominance = max(band_totals) / total_band_energy
        active_band_count = sum(1 for power in band_totals if power >= max(band_totals) * args.min_band_relative_energy)
    centroid_values = [value for value in centroids if value > 0.0]
    centroid_range = percentile(centroid_values, 0.95) - percentile(centroid_values, 0.10) if centroid_values else 0.0
    median_window_active_bands = percentile([float(value) for value in window_active_counts], 0.5) if window_active_counts else 0.0

    return {
        "path": str(path),
        "durationSeconds": round(duration, 3),
        "analyzedSeconds": round(len(samples) / args.sample_rate, 3),
        "sampleRate": args.sample_rate,
        "windowCount": len(windows),
        "rmsDbP10": round(percentile(rms_db_values, 0.10), 3) if rms_db_values else None,
        "rmsDbP50": round(percentile(rms_db_values, 0.50), 3) if rms_db_values else None,
        "rmsDbP95": round(percentile(rms_db_values, 0.95), 3) if rms_db_values else None,
        "dynamicRangeDb": round(dynamic_range, 3),
        "silentWindowRatio": round(silent_windows / max(len(windows), 1), 4),
        "clippedWindowRatio": round(clipped_windows / max(len(windows), 1), 4),
        "activeBandCount": active_band_count,
        "medianWindowActiveBandCount": round(median_window_active_bands, 3),
        "singleBandDominance": round(single_band_dominance, 4),
        "centroidRangeHz": round(centroid_range, 3),
        "bandEnergy": {str(int(freq)): round(power, 6) for freq, power in zip(BAND_CENTERS, band_totals)},
        "decodeFailed": False,
    }


def identity_text(manifest: dict[str, Any], selection: dict[str, Any], path: Path | None) -> str:
    parts: list[str] = [str(path or "")]
    for track in manifest.get("tracks") or []:
        if isinstance(track, dict):
            parts.extend(str(track.get(key) or "") for key in ("name", "artist", "genre", "mood", "path", "license"))
    for row in selection.get("selectedMaterializedBeds") or []:
        if isinstance(row, dict):
            parts.extend(str(row.get(key) or "") for key in ("name", "artist", "genre", "role", "localPath", "licenseUrl"))
    return " ".join(parts).lower()


def bad_identity_terms(identity: str) -> list[str]:
    normalized = re.sub(r"[_-]+", " ", identity.lower())
    matches: list[str] = []
    for term in BAD_IDENTITY_TERMS:
        pattern = r"(?<![a-z0-9])" + r"\s+".join(re.escape(part) for part in term.split()) + r"(?![a-z0-9])"
        if re.search(pattern, normalized):
            matches.append(term)
    return sorted(matches)


def track_identity_summary(manifest: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    tracks = [track for track in manifest.get("tracks") or [] if isinstance(track, dict)]
    selected = [row for row in selection.get("selectedMaterializedBeds") or [] if isinstance(row, dict)]
    named_tracks = sum(1 for track in tracks if clean(track.get("name") or Path(str(track.get("path") or "")).stem))
    descriptive_tracks = sum(1 for track in tracks if clean(track.get("artist") or track.get("genre") or track.get("mood")))
    license_tracks = sum(1 for track in tracks if str(track.get("license") or "").startswith(("http://", "https://", "local-original-audio://")))
    return {
        "manifestTrackCount": len(tracks),
        "selectedMaterializedBedCount": len(selected),
        "namedTrackCount": named_tracks,
        "descriptiveTrackCount": descriptive_tracks,
        "licenseTrackCount": license_tracks,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = infer_blueprint(package_dir, args.blueprint)
    blueprint = load_json(blueprint_path) or {}
    selection_path = package_dir / "bgm_selection_package" / "bgm_selection_package.json"
    selection = load_json(selection_path) or {}
    phrase_path = package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json"
    phrase = load_json(phrase_path) or {}
    manifest_path = infer_bgm_manifest(package_dir, blueprint if isinstance(blueprint, dict) else {}, args.bgm_manifest)
    manifest = load_json(manifest_path) or {}
    bgm_output = infer_bgm_output(package_dir, manifest if isinstance(manifest, dict) else {}, blueprint if isinstance(blueprint, dict) else {}, args.bgm_output)
    blockers: list[str] = []
    warnings: list[str] = []

    if not isinstance(blueprint, dict) or not blueprint:
        blockers.append("Resolve blueprint is missing")
    if not isinstance(selection, dict) or selection.get("status") not in ACCEPTED_SELECTION_STATUSES:
        blockers.append(f"BGM selection package status is {selection.get('status')}")
    if not isinstance(phrase, dict) or phrase.get("status") not in ACCEPTED_PHRASE_STATUSES:
        blockers.append(f"BGM phrase blueprint status is {phrase.get('status')}")
    if not isinstance(manifest, dict) or not manifest:
        blockers.append("BGM manifest is missing")
    if not bgm_output or not bgm_output.exists():
        blockers.append("BGM output audio file is missing")

    audio_metrics: dict[str, Any] = {}
    if bgm_output and bgm_output.exists():
        try:
            audio_metrics = analyze_audio(bgm_output, args)
        except Exception as exc:
            audio_metrics = {"path": str(bgm_output), "decodeFailed": True, "error": str(exc)}
            blockers.append(f"BGM audio could not be analyzed: {exc}")

    identity_summary = track_identity_summary(manifest if isinstance(manifest, dict) else {}, selection if isinstance(selection, dict) else {})
    identity = identity_text(manifest if isinstance(manifest, dict) else {}, selection if isinstance(selection, dict) else {}, bgm_output)
    bad_terms = bad_identity_terms(identity)
    phrase_summary = summary_of(phrase)

    if bad_terms:
        blockers.append(f"BGM identity contains placeholder or tone terms: {', '.join(bad_terms)}")
    if identity_summary["manifestTrackCount"] < args.min_manifest_tracks:
        blockers.append("BGM manifest has too few source track rows")
    if identity_summary["namedTrackCount"] < args.min_named_tracks:
        blockers.append("BGM manifest lacks named music tracks")
    if identity_summary["licenseTrackCount"] < args.min_license_tracks:
        blockers.append("BGM manifest lacks traceable music license rows")
    if identity_summary["descriptiveTrackCount"] < args.min_descriptive_tracks:
        warnings.append("BGM manifest has weak artist/genre/mood metadata")

    if audio_metrics and not audio_metrics.get("decodeFailed"):
        if as_float(audio_metrics.get("durationSeconds")) < args.min_duration_seconds:
            blockers.append("BGM bed is too short for a long-form travel delivery")
        if as_float(audio_metrics.get("analyzedSeconds")) < args.min_analyzed_seconds:
            blockers.append("BGM analysis window is too short to prove musicality")
        if as_float(audio_metrics.get("dynamicRangeDb")) < args.min_dynamic_range_db:
            blockers.append("BGM dynamic range is too flat and may be a hum/tone bed")
        if as_float(audio_metrics.get("silentWindowRatio")) > args.max_silent_window_ratio:
            blockers.append("BGM has too much silence")
        if as_float(audio_metrics.get("clippedWindowRatio")) > args.max_clipped_window_ratio:
            blockers.append("BGM has too many clipped windows")
        if as_int(audio_metrics.get("activeBandCount")) < args.min_active_bands:
            blockers.append("BGM lacks enough active frequency bands")
        if as_float(audio_metrics.get("medianWindowActiveBandCount")) < args.min_median_window_active_bands:
            blockers.append("BGM windows are too single-band dominated")
        if as_float(audio_metrics.get("singleBandDominance")) > args.max_single_band_dominance:
            blockers.append("BGM is dominated by one frequency band")
        if as_float(audio_metrics.get("centroidRangeHz")) < args.min_centroid_range_hz:
            warnings.append("BGM has limited spectral movement; human listen recommended")

    if as_int(phrase_summary.get("phraseRowCount")) < args.min_phrase_rows:
        blockers.append("BGM phrase blueprint has too few phrase rows")
    if as_int(phrase_summary.get("sectionRowCount")) < args.min_section_rows:
        blockers.append("BGM phrase blueprint is missing opening/body/transition/ending section coverage")
    candidate_transitions = as_int(phrase_summary.get("candidateTransitionCount"))
    if candidate_transitions and as_int(phrase_summary.get("transitionsWithPhraseCue")) < candidate_transitions:
        blockers.append("Not every transition has a BGM phrase cue")

    summary = {
        "bgmOutput": str(bgm_output) if bgm_output else None,
        "selectionStatus": selection.get("status") if isinstance(selection, dict) else None,
        "phraseStatus": phrase.get("status") if isinstance(phrase, dict) else None,
        **identity_summary,
        "badIdentityTerms": bad_terms,
        "phraseRowCount": phrase_summary.get("phraseRowCount"),
        "sectionRowCount": phrase_summary.get("sectionRowCount"),
        "candidateTransitionCount": phrase_summary.get("candidateTransitionCount"),
        "transitionsWithPhraseCue": phrase_summary.get("transitionsWithPhraseCue"),
        "audio": audio_metrics,
        "blockerCount": len(blockers),
        "warningCount": len(warnings),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(blueprint_path),
            "bgmSelectionPackage": str(selection_path),
            "bgmPhraseBlueprintReport": str(phrase_path),
            "bgmManifest": str(manifest_path) if manifest_path else None,
            "bgmOutput": str(bgm_output) if bgm_output else None,
        },
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "requiresRealMusicNotHumTone": True,
            "requiresTraceableNamedTrack": True,
            "requiresBgmPhraseCoverage": True,
            "requiresMultiBandAudioEnergy": True,
            "requiresDynamicMovement": True,
            "humanListenRecommendedWhenWarnings": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BGM Musicality Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(
        [
            "",
            "## Contract",
            "- The BGM bed must be a real named music asset, not a sine tone, hum, silence, or placeholder.",
            "- The selected bed must have phrase rows for opening/title, body, transitions, and ending before Resolve apply.",
            "- The decoded audio must show usable dynamics and multi-band energy so scenic/title/transition sections are music-led.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether the BGM bed is musical rather than a hum/tone placeholder.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--bgm-manifest")
    parser.add_argument("--bgm-output")
    parser.add_argument("--sample-rate", type=int, default=11025)
    parser.add_argument("--sample-seconds", type=float, default=180.0)
    parser.add_argument("--window-seconds", type=float, default=0.5)
    parser.add_argument("--band-window-seconds", type=float, default=1.0)
    parser.add_argument("--silent-window-db", type=float, default=-52.0)
    parser.add_argument("--clip-peak-threshold", type=float, default=0.985)
    parser.add_argument("--min-band-relative-energy", type=float, default=0.08)
    parser.add_argument("--min-duration-seconds", type=float, default=10.0)
    parser.add_argument("--min-analyzed-seconds", type=float, default=8.0)
    parser.add_argument("--min-dynamic-range-db", type=float, default=3.0)
    parser.add_argument("--max-silent-window-ratio", type=float, default=0.2)
    parser.add_argument("--max-clipped-window-ratio", type=float, default=0.05)
    parser.add_argument("--min-active-bands", type=int, default=4)
    parser.add_argument("--min-median-window-active-bands", type=float, default=3.0)
    parser.add_argument("--max-single-band-dominance", type=float, default=0.7)
    parser.add_argument("--min-centroid-range-hz", type=float, default=120.0)
    parser.add_argument("--min-manifest-tracks", type=int, default=1)
    parser.add_argument("--min-named-tracks", type=int, default=1)
    parser.add_argument("--min-license-tracks", type=int, default=1)
    parser.add_argument("--min-descriptive-tracks", type=int, default=1)
    parser.add_argument("--min-phrase-rows", type=int, default=3)
    parser.add_argument("--min-section-rows", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir)
    report = build_report(package_dir, args)
    write_json(package_dir / "bgm_musicality_contract_audit.json", report)
    write_markdown(package_dir / "bgm_musicality_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"], "warnings": report["warnings"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
