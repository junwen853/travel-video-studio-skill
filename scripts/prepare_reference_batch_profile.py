#!/usr/bin/env python3
"""Analyze multiple travel reference videos into one reusable style profile."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".m4v"}


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


def seconds_to_timecode(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 3) if values else 0.0


def median(values: list[float]) -> float:
    return round(statistics.median(values), 3) if values else 0.0


def discover_references(reference_dirs: list[str], references: list[str], recursive: bool) -> list[Path]:
    paths: list[Path] = []
    for item in references:
        path = Path(item).expanduser()
        if path.exists() and path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES:
            paths.append(path.resolve())
    for item in reference_dirs:
        root = Path(item).expanduser()
        if not root.exists() or not root.is_dir():
            continue
        iterator = root.rglob("*") if recursive else root.glob("*")
        for path in iterator:
            if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES:
                paths.append(path.resolve())
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return sorted(out, key=lambda path: path.name.lower())


def safe_stem(path: Path, index: int) -> str:
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in path.stem).strip("_")
    return f"{index:02d}_{stem or 'reference'}"


def analyze_one(
    reference: Path,
    item_dir: Path,
    *,
    force: bool,
    skip_contact_sheet: bool,
    skip_scene_detect: bool,
    skip_audio_analysis: bool,
    scene_threshold: float,
    frames: int,
) -> dict[str, Any]:
    json_path = item_dir / "reference_analysis.json"
    if json_path.exists() and not force:
        existing = load_json(json_path)
        if isinstance(existing, dict):
            existing["batchReuse"] = True
            return existing
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().with_name("analyze_reference_video.py")),
        "--reference",
        str(reference),
        "--output-dir",
        str(item_dir),
        "--scene-threshold",
        str(scene_threshold),
        "--frames",
        str(frames),
        "--json",
    ]
    if skip_contact_sheet:
        cmd.append("--skip-contact-sheet")
    if skip_scene_detect:
        cmd.append("--skip-scene-detect")
    if skip_audio_analysis:
        cmd.append("--skip-audio-analysis")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "referencePath": str(reference),
            "status": "failed_reference_analysis",
            "error": (result.stderr or result.stdout).strip()[-1400:],
        }
    data = load_json(json_path)
    if isinstance(data, dict):
        data["batchReuse"] = False
        return data
    try:
        parsed = json.loads(result.stdout)
        parsed["batchReuse"] = False
        return parsed
    except Exception:
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "referencePath": str(reference),
            "status": "failed_reference_analysis_parse",
            "error": result.stdout.strip()[-1400:],
        }


def aggregate_pacing(reports: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = [r.get("pacingProfile") for r in reports if isinstance(r.get("pacingProfile"), dict) and r["pacingProfile"].get("status") == "analyzed"]
    shot_counts = [int(p.get("estimatedShotCount") or 0) for p in analyzed]
    total_shots = sum(shot_counts)
    weighted_avg = 0.0
    if total_shots:
        weighted_avg = sum(float(p.get("averageShotLengthSeconds") or 0) * int(p.get("estimatedShotCount") or 0) for p in analyzed) / total_shots
    return {
        "status": "analyzed" if analyzed else "missing_reference_pacing",
        "sourceProfileCount": len(analyzed),
        "estimatedShotCount": total_shots,
        "averageShotLengthSeconds": round(weighted_avg, 3) if weighted_avg else mean([float(p.get("averageShotLengthSeconds") or 0) for p in analyzed if p.get("averageShotLengthSeconds")]),
        "medianShotLengthSeconds": median([float(p.get("medianShotLengthSeconds") or 0) for p in analyzed if p.get("medianShotLengthSeconds")]),
        "p10ShotLengthSeconds": median([float(p.get("p10ShotLengthSeconds") or 0) for p in analyzed if p.get("p10ShotLengthSeconds")]),
        "p90ShotLengthSeconds": median([float(p.get("p90ShotLengthSeconds") or 0) for p in analyzed if p.get("p90ShotLengthSeconds")]),
        "longShotCountOver20s": sum(int(p.get("longShotCountOver20s") or 0) for p in analyzed),
        "shortShotCountUnder3s": sum(int(p.get("shortShotCountUnder3s") or 0) for p in analyzed),
    }


def aggregate_audio(reports: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = [r.get("audioProfile") for r in reports if isinstance(r.get("audioProfile"), dict) and r["audioProfile"].get("status") == "analyzed"]
    return {
        "status": "analyzed" if analyzed else "missing_reference_audio",
        "sourceProfileCount": len(analyzed),
        "meanVolumeDb": mean([float(a.get("meanVolumeDb")) for a in analyzed if a.get("meanVolumeDb") is not None]),
        "maxVolumeDb": mean([float(a.get("maxVolumeDb")) for a in analyzed if a.get("maxVolumeDb") is not None]),
        "silenceEventCount": sum(int(a.get("silenceEventCount") or 0) for a in analyzed),
        "totalDetectedSilenceSeconds": round(sum(float(a.get("totalDetectedSilenceSeconds") or 0) for a in analyzed), 3),
    }


def aggregate_samples(reports: list[dict[str, Any]], max_samples: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for report_index, report in enumerate(reports, start=1):
        reference = Path(str(report.get("referencePath") or "reference")).name
        duration = float(report.get("durationSeconds") or 0)
        for sample in report.get("sampleFrames") or []:
            if not isinstance(sample, dict):
                continue
            second = float(sample.get("second") or 0)
            samples.append(
                {
                    "batchIndex": len(samples) + 1,
                    "referenceIndex": report_index,
                    "referenceName": reference,
                    "second": second,
                    "timecode": sample.get("timecode") or seconds_to_timecode(second),
                    "relativePosition": round(second / duration, 4) if duration else None,
                    "framePath": sample.get("framePath"),
                    "visualReviewPrompt": sample.get("visualReviewPrompt"),
                }
            )
    if len(samples) <= max_samples:
        return samples
    step = max(1, len(samples) / max_samples)
    selected = []
    cursor = 0.0
    while len(selected) < max_samples and round(cursor) < len(samples):
        selected.append(samples[round(cursor)])
        cursor += step
    for index, sample in enumerate(selected, start=1):
        sample["batchIndex"] = index
    return selected


def style_targets(summary: dict[str, Any], pacing: dict[str, Any], audio: dict[str, Any]) -> dict[str, Any]:
    avg = float(pacing.get("averageShotLengthSeconds") or 5.0)
    med = float(pacing.get("medianShotLengthSeconds") or 3.0)
    p90 = float(pacing.get("p90ShotLengthSeconds") or 12.0)
    return {
        "referenceVideoCount": summary.get("referenceVideoCount"),
        "totalReferenceMinutes": summary.get("totalDurationMinutes"),
        "averageShotLengthReferenceSeconds": round(avg, 3),
        "medianShotLengthReferenceSeconds": round(med, 3),
        "targetAverageRangeSeconds": [round(max(3.5, avg * 0.75), 3), round(min(12.0, max(7.5, avg * 1.8)), 3)],
        "targetMedianRangeSeconds": [round(max(1.8, med * 0.75), 3), round(min(7.5, max(4.0, med * 2.0)), 3)],
        "longShotSoftLimitSeconds": round(min(20.0, max(10.0, p90)), 3),
        "audioMeanVolumeReferenceDb": audio.get("meanVolumeDb"),
        "openingTarget": "viewer promise, destination proof, clean hero title, practical arrival, lived-in texture, first handoff",
        "transitionTarget": "physical route bridge or motivated match before any whip/rotation/speed-ramp effect",
        "transitionStyleTargets": {
            "maxMotionShare": 0.25,
            "minCleanMatchBreathShare": 0.45,
            "minBridgeBreathImportantCoverage": 1.0,
            "maxDominantFamilyShare": 0.65,
            "maxFamilyRun": 4,
            "requireBgmHit": True,
            "requireCaptionQuietZone": True,
            "forbidHighIntensity": True,
        },
        "endingTarget": "route aftertaste after the main experience",
    }


def build_profile(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir).expanduser().resolve()
    item_root = output_dir / "reference_items"
    references = discover_references(args.reference_dir or [], args.reference or [], args.recursive)
    if args.max_videos:
        references = references[: args.max_videos]
    reports = [
        analyze_one(
            reference,
            item_root / safe_stem(reference, index),
            force=args.force,
            skip_contact_sheet=args.skip_contact_sheet,
            skip_scene_detect=args.skip_scene_detect,
            skip_audio_analysis=args.skip_audio_analysis,
            scene_threshold=args.scene_threshold,
            frames=args.frames,
        )
        for index, reference in enumerate(references, start=1)
    ]
    successful = [report for report in reports if report.get("pacingProfile") or report.get("audioProfile")]
    pacing = aggregate_pacing(successful)
    audio = aggregate_audio(successful)
    samples = aggregate_samples(successful, args.max_samples)
    durations = [float(r.get("durationSeconds") or 0) for r in successful]
    summary = {
        "referenceVideoCount": len(successful),
        "failedReferenceCount": len(reports) - len(successful),
        "totalDurationSeconds": round(sum(durations), 3),
        "totalDurationMinutes": round(sum(durations) / 60, 3) if durations else 0,
        "averageDurationMinutes": round(mean(durations) / 60, 3) if durations else 0,
        "frameRates": sorted({str((r.get("summary") or {}).get("frameRate")) for r in successful if isinstance(r.get("summary"), dict)}),
        "sampleFrameCount": len(samples),
    }
    status = (
        "ready_with_reference_batch_profile"
        if len(successful) >= 2 and pacing.get("status") == "analyzed"
        else ("ready_with_single_reference_profile" if len(successful) == 1 else "blocked_missing_reference_videos")
    )
    profile = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "referencePaths": [str(path) for path in references],
        "outputDir": str(output_dir),
        "summary": summary,
        "pacingProfile": pacing,
        "audioProfile": audio,
        "sampleFrames": samples,
        "contactSheet": None,
        "styleTargets": style_targets(summary, pacing, audio),
        "referenceReports": [
            {
                "referencePath": report.get("referencePath"),
                "analysisPath": str(item_root / safe_stem(Path(str(report.get("referencePath") or f"reference_{index}")), index) / "reference_analysis.json"),
                "analysisMarkdownPath": str(item_root / safe_stem(Path(str(report.get("referencePath") or f"reference_{index}")), index) / "reference_analysis.md"),
                "fullReviewPrompt": "Review the reference as a full film before learning from it: opening/title, chapter rhythm, transition language, ending aftertaste, BGM/audio/caption behavior, and non-copying Skill takeaways.",
                "fullReviewRepairPlan": "Run prepare_reference_review_repair_plan.py and close this reference row before final QA or Skill maturity.",
                "durationMinutes": report.get("durationMinutes"),
                "pacingStatus": (report.get("pacingProfile") or {}).get("status") if isinstance(report.get("pacingProfile"), dict) else None,
                "audioStatus": (report.get("audioProfile") or {}).get("status") if isinstance(report.get("audioProfile"), dict) else None,
                "estimatedShotCount": (report.get("pacingProfile") or {}).get("estimatedShotCount") if isinstance(report.get("pacingProfile"), dict) else None,
                "averageShotLengthSeconds": (report.get("pacingProfile") or {}).get("averageShotLengthSeconds") if isinstance(report.get("pacingProfile"), dict) else None,
                "medianShotLengthSeconds": (report.get("pacingProfile") or {}).get("medianShotLengthSeconds") if isinstance(report.get("pacingProfile"), dict) else None,
                "sampleFrameCount": len(report.get("sampleFrames") or []) if isinstance(report.get("sampleFrames"), list) else 0,
                "batchReuse": report.get("batchReuse"),
                "error": report.get("error"),
            }
            for index, report in enumerate(reports, start=1)
        ],
        "referenceUsageContract": {
            "allowed": "Use aggregate pacing, rhythm, audio, opening, transition, caption, and ending patterns as non-copying guidance.",
            "forbidden": "Do not copy exact footage, titles, subtitles, narration, creator branding, or music from the references.",
        },
        "acceptanceRubric": {
            "pass": [
                "At least two reference videos are analyzed for a batch profile when the user supplies a reference set.",
                "Aggregate pacing and audio profiles are available to downstream rhythm/style audits.",
                "Sample frames are carried as a visual review worksheet, not as assets to copy.",
                "The profile records a non-copying usage contract.",
            ],
            "reject": [
                "Only random single-frame impressions with no scene-cut or audio profile.",
                "Reference assets copied into the user film.",
                "No aggregate style targets for rhythm, transitions, opening, or ending.",
            ],
        },
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    }
    write_json(output_dir / "reference_batch_profile.json", profile)
    write_json(output_dir / "reference_analysis.json", profile)
    write_markdown(output_dir / "reference_batch_profile.md", profile)
    return profile


def write_markdown(path: Path, profile: dict[str, Any]) -> None:
    lines = [
        "# Reference Batch Profile",
        "",
        f"Status: `{profile['status']}`",
        f"Output: `{profile['outputDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(profile["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Pacing Profile",
        "",
        "```json",
        json.dumps(profile["pacingProfile"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Audio Profile",
        "",
        "```json",
        json.dumps(profile["audioProfile"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Style Targets",
        "",
        "```json",
        json.dumps(profile["styleTargets"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Reference Reports",
    ]
    for row in profile["referenceReports"]:
        lines.extend(
            [
                "",
                f"### {Path(str(row.get('referencePath') or 'reference')).name}",
                f"- Analysis: `{row.get('analysisPath')}`",
                f"- Analysis markdown: `{row.get('analysisMarkdownPath')}`",
                f"- Full-review prompt: {row.get('fullReviewPrompt')}",
                f"- Duration minutes: {row.get('durationMinutes')}",
                f"- Pacing/audio: `{row.get('pacingStatus')}` / `{row.get('audioStatus')}`",
                f"- Shots: {row.get('estimatedShotCount')}",
                f"- Average/median shot: {row.get('averageShotLengthSeconds')} / {row.get('medianShotLengthSeconds')}",
                f"- Samples: {row.get('sampleFrameCount')}",
            ]
        )
        if row.get("error"):
            lines.append(f"- Error: {row.get('error')}")
    lines.extend(["", "## Sample Frame Worksheet"])
    for sample in profile["sampleFrames"][:160]:
        lines.append(f"- `{sample.get('referenceName')}` `{sample.get('timecode')}` `{sample.get('framePath')}`")
    lines.extend(
        [
            "",
            "## Usage Contract",
            f"- Allowed: {profile['referenceUsageContract']['allowed']}",
            f"- Forbidden: {profile['referenceUsageContract']['forbidden']}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze multiple travel reference videos into one batch style profile.")
    parser.add_argument("--reference", action="append", default=[], help="Reference video path. Can be repeated.")
    parser.add_argument("--reference-dir", action="append", default=[], help="Directory containing reference videos. Can be repeated.")
    parser.add_argument("--package-dir", help="When set, defaults output to <package>/reference.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to <package>/reference when --package-dir is set.")
    parser.add_argument("--recursive", action="store_true", help="Search reference dirs recursively.")
    parser.add_argument("--max-videos", type=int, default=0)
    parser.add_argument("--max-samples", type=int, default=80)
    parser.add_argument("--frames", type=int, default=18)
    parser.add_argument("--scene-threshold", type=float, default=0.35)
    parser.add_argument("--skip-contact-sheet", action="store_true")
    parser.add_argument("--skip-scene-detect", action="store_true")
    parser.add_argument("--skip-audio-analysis", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-analyze references even when per-video JSON exists.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.output_dir:
        if not args.package_dir:
            parser.error("--output-dir is required unless --package-dir is set")
        args.output_dir = str(Path(args.package_dir).expanduser().resolve() / "reference")
    profile = build_profile(args)
    if args.json:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": profile["status"], "outputDir": profile["outputDir"], "summary": profile["summary"]}, ensure_ascii=False, indent=2))
    return 2 if profile["status"] == "blocked_missing_reference_videos" else 0


if __name__ == "__main__":
    raise SystemExit(main())
