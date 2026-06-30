#!/usr/bin/env python3
"""Analyze a local long-form reference video into a reusable style profile."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


FRAME_W = 426
FRAME_H = 240


def default_reference_video() -> str | None:
    configured = os.environ.get("TRAVEL_VIDEO_REFERENCE")
    if not configured:
        return None
    return str(Path(configured).expanduser())


def run_json(cmd: list[str]) -> Any:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "command failed")
    return json.loads(result.stdout)


def probe(path: Path) -> dict[str, Any]:
    return run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,duration,bit_rate",
            "-of",
            "json",
            str(path),
        ]
    )


def frame_rate_value(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            denominator = float(den)
            return float(num) / denominator if denominator else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def video_summary(data: dict[str, Any]) -> dict[str, Any]:
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    fmt = data.get("format") or {}
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    duration = float(fmt.get("duration") or video.get("duration") or 0)
    frame_rate = frame_rate_value(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    return {
        "durationSeconds": duration,
        "durationMinutes": round(duration / 60, 2) if duration else 0,
        "width": width,
        "height": height,
        "aspectRatio": round(width / height, 4) if height else 0,
        "frameRate": round(frame_rate, 3) if frame_rate else None,
        "containerBitrateMbps": round(float(fmt.get("bit_rate") or 0) / 1_000_000, 3),
        "videoBitrateMbps": round(float(video.get("bit_rate") or 0) / 1_000_000, 3),
        "videoCodec": video.get("codec_name"),
        "audioCodec": audio.get("codec_name"),
        "audioBitrateMbps": round(float(audio.get("bit_rate") or 0) / 1_000_000, 3) if audio else 0,
        "audioStreams": len([s for s in data.get("streams", []) if s.get("codec_type") == "audio"]),
        "videoStreams": len([s for s in data.get("streams", []) if s.get("codec_type") == "video"]),
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def run_text(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def detect_scene_cuts(path: Path, threshold: float) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"status": "skipped", "reason": "ffmpeg not found", "sceneThreshold": threshold}
    result = run_text(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
            "-an",
            "-vf",
            f"scale=320:-1,select='gt(scene,{threshold})',showinfo",
            "-vsync",
            "vfr",
            "-f",
            "null",
            "-",
        ]
    )
    if result.returncode != 0:
        return {
            "status": "failed",
            "reason": (result.stderr or result.stdout).strip()[-1200:],
            "sceneThreshold": threshold,
        }
    timestamps = []
    for match in re.finditer(r"pts_time:([0-9.]+)", result.stderr):
        try:
            timestamps.append(round(float(match.group(1)), 3))
        except ValueError:
            continue
    duration = float((probe(path).get("format") or {}).get("duration") or 0)
    cut_points = [0.0, *sorted(set(timestamps))]
    if duration > 0 and (not cut_points or cut_points[-1] < duration):
        cut_points.append(duration)
    shot_lengths = [
        round(max(0.0, cut_points[index + 1] - cut_points[index]), 3)
        for index in range(len(cut_points) - 1)
        if cut_points[index + 1] > cut_points[index]
    ]
    return {
        "status": "analyzed",
        "sceneThreshold": threshold,
        "sceneCutCount": len(timestamps),
        "estimatedShotCount": len(shot_lengths),
        "sceneCutTimestampsSeconds": timestamps[:500],
        "truncatedSceneCuts": max(0, len(timestamps) - 500),
        "averageShotLengthSeconds": round(statistics.fmean(shot_lengths), 3) if shot_lengths else 0,
        "medianShotLengthSeconds": round(statistics.median(shot_lengths), 3) if shot_lengths else 0,
        "p10ShotLengthSeconds": round(percentile(shot_lengths, 0.10), 3),
        "p90ShotLengthSeconds": round(percentile(shot_lengths, 0.90), 3),
        "longShotCountOver20s": sum(1 for value in shot_lengths if value >= 20),
        "shortShotCountUnder3s": sum(1 for value in shot_lengths if 0 < value <= 3),
    }


def analyze_audio(path: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"status": "skipped", "reason": "ffmpeg not found"}
    volume = run_text([ffmpeg, "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"])
    silence = run_text(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
            "-vn",
            "-af",
            "silencedetect=noise=-45dB:d=1",
            "-f",
            "null",
            "-",
        ]
    )
    out: dict[str, Any] = {"status": "analyzed"}
    text = volume.stderr
    for key, pattern in {
        "meanVolumeDb": r"mean_volume:\s*([-0-9.]+) dB",
        "maxVolumeDb": r"max_volume:\s*([-0-9.]+) dB",
    }.items():
        match = re.search(pattern, text)
        if match:
            out[key] = float(match.group(1))
    silence_events = []
    starts: list[float] = []
    for line in silence.stderr.splitlines():
        start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start:
            starts.append(float(start.group(1)))
            continue
        end = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
        if end:
            start_value = starts.pop(0) if starts else None
            silence_events.append(
                {
                    "startSeconds": round(start_value, 3) if start_value is not None else None,
                    "endSeconds": round(float(end.group(1)), 3),
                    "durationSeconds": round(float(end.group(2)), 3),
                }
            )
    out["silenceEventCount"] = len(silence_events)
    out["silenceEvents"] = silence_events[:100]
    out["truncatedSilenceEvents"] = max(0, len(silence_events) - 100)
    out["totalDetectedSilenceSeconds"] = round(sum(float(item["durationSeconds"]) for item in silence_events), 3)
    if volume.returncode != 0:
        out["volumeWarning"] = volume.stderr.strip()[-800:]
    if silence.returncode != 0:
        out["silenceWarning"] = silence.stderr.strip()[-800:]
    return out


def sample_times(duration: float, frames: int) -> list[float]:
    if duration <= 0 or frames <= 0:
        return []
    margin = min(8.0, duration * 0.01)
    start = margin
    end = max(start, duration - margin)
    if frames == 1:
        return [round(duration / 2, 3)]
    return [round(start + (end - start) * index / (frames - 1), 3) for index in range(frames)]


def extract_sample_frames(path: Path, output_dir: Path, times: list[float]) -> list[dict[str, Any]]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return []
    frames_dir = output_dir / "reference_frame_samples"
    frames_dir.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    for index, second in enumerate(times, start=1):
        frame_path = frames_dir / f"{index:03d}_{second:08.3f}s.jpg"
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{second:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={FRAME_W}:{FRAME_H}:force_original_aspect_ratio=decrease,pad={FRAME_W}:{FRAME_H}:(ow-iw)/2:(oh-ih)/2:black",
                "-q:v",
                "2",
                str(frame_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and frame_path.exists():
            samples.append(
                {
                    "index": index,
                    "second": second,
                    "timecode": seconds_to_timecode(second),
                    "framePath": str(frame_path),
                    "visualReviewPrompt": "Classify as transport, street, lived-in detail, landmark, food/interior, talking-head, title/context insert, or scenic breathing shot.",
                }
            )
    return samples


def make_labeled_contact_sheet(samples: list[dict[str, Any]], output: Path) -> Path | None:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    if not samples:
        return None
    cols = 6
    rows = math.ceil(len(samples) / cols)
    label_h = 34
    sheet = Image.new("RGB", (cols * FRAME_W, rows * (FRAME_H + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for sample in samples:
        path = Path(sample["framePath"])
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        index = int(sample["index"]) - 1
        x = (index % cols) * FRAME_W
        y = (index // cols) * (FRAME_H + label_h)
        sheet.paste(image, (x, y))
        label = f"{sample['index']:02d} {sample['timecode']}"
        draw.rectangle((x, y + FRAME_H, x + FRAME_W, y + FRAME_H + label_h), fill=(245, 245, 245))
        draw.text((x + 8, y + FRAME_H + 9), label, fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    return output


def make_contact_sheet(path: Path, output: Path, frames: int = 24) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    data = probe(path)
    duration = float(data.get("format", {}).get("duration") or 0)
    if duration <= 0:
        return None
    fps_expr = f"fps={frames / duration:.8f},scale=360:-1,tile=6x4"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(path), "-frames:v", "1", "-vf", fps_expr, str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    return output if result.returncode == 0 and output.exists() else None


def seconds_to_timecode(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    sec = total % 60
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def style_targets(summary: dict[str, Any], pacing: dict[str, Any]) -> dict[str, Any]:
    avg = float(pacing.get("averageShotLengthSeconds") or 0)
    median = float(pacing.get("medianShotLengthSeconds") or 0)
    if avg <= 0:
        avg_range = [6, 42]
    else:
        avg_range = [max(5, round(avg * 0.55, 1)), min(45, round(avg * 1.65, 1))]
    return {
        "referenceDurationMinutes": summary.get("durationMinutes"),
        "longFormTarget": "20+ minute travel film with breathing room; do not compress into a short recap.",
        "frameRateGuidance": "Match source/project delivery, but final client exports should remain high-frame-rate when footage supports it.",
        "averageShotLengthTargetSeconds": avg_range,
        "medianShotLengthReferenceSeconds": round(median, 3),
        "structureTarget": [
            "transport and arrival moments",
            "street/city impression",
            "lived-in details such as food, hotel, waiting, conversations, interiors",
            "landmark payoff",
            "quiet bridge before the next day/place",
        ],
        "audioTarget": "BGM or intentional ambience should carry scenic/title/transition sections; do not let accidental camera voice lead those sections.",
        "textTarget": "Use frequent natural Chinese captions outside title-safe zones when voiceover is rejected.",
    }


def build_report(
    path: Path,
    output_dir: Path,
    skip_contact_sheet: bool,
    skip_scene_detect: bool,
    skip_audio_analysis: bool,
    scene_threshold: float,
    frames: int,
) -> dict[str, Any]:
    data = probe(path)
    summary = video_summary(data)
    duration = float(summary.get("durationSeconds") or 0)
    video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_rows = extract_sample_frames(path, output_dir, sample_times(duration, frames))
    contact = make_labeled_contact_sheet(sample_rows, output_dir / "reference_contact_sheet.jpg") if not skip_contact_sheet else None
    if not skip_contact_sheet:
        contact = contact or make_contact_sheet(path, output_dir / "reference_contact_sheet.jpg", frames=frames)
    pacing = {"status": "skipped", "reason": "disabled", "sceneThreshold": scene_threshold}
    if not skip_scene_detect:
        pacing = detect_scene_cuts(path, scene_threshold)
    audio = {"status": "skipped", "reason": "disabled"}
    if not skip_audio_analysis:
        audio = analyze_audio(path)
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "referencePath": str(path),
        "durationSeconds": duration,
        "durationMinutes": round(duration / 60, 2),
        "summary": summary,
        "format": data.get("format", {}),
        "videoStreams": video_streams,
        "audioStreams": audio_streams,
        "pacingProfile": pacing,
        "audioProfile": audio,
        "sampleFrames": sample_rows,
        "contactSheet": str(contact) if contact else None,
        "styleTargets": style_targets(summary, pacing),
        "referenceUsageContract": {
            "allowed": "Use pacing, route rhythm, audio/text balance, and shot-category observations as non-copying guidance.",
            "forbidden": "Do not copy exact footage, title design, music, narration, subtitles, or creator branding.",
        },
        "fullReviewContract": {
            "requiredBeforeSkillLearning": True,
            "repairPlanScript": "prepare_reference_review_repair_plan.py",
            "requiredObservations": [
                "full-film timeline strip evidence",
                "opening/title construction",
                "chapter rhythm and shot-function alternation",
                "transition language and bridge/breath/match balance",
                "ending aftertaste",
                "BGM/audio/caption behavior",
                "non-copying reusable Skill takeaways",
            ],
            "acceptedStatus": "ready_no_reference_review_repairs_needed",
        },
        "styleImplications": [
            "This is long-form reference material, not a short recap.",
            "Use sparse narration and long visual passages.",
            "A 20-minute target should be treated as a lower bound; this reference is closer to 40 minutes.",
            "Chapter rhythm, transport, street texture, and emotional aftertaste matter as much as landmark coverage.",
            "Use sampled frames as a visual worksheet for route texture categories before judging a future edit as Malta-like.",
        ],
    }
    (output_dir / "reference_analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [
        "# Reference Analysis",
        "",
        f"Reference: `{path}`",
        f"Duration: {duration / 60:.2f} minutes",
        f"Primary video: `{summary['width']}x{summary['height']}` at `{summary['frameRate']}` fps",
        f"Bitrate: container `{summary['containerBitrateMbps']}` Mbps, video `{summary['videoBitrateMbps']}` Mbps",
        f"Video streams: {len(video_streams)}",
        f"Audio streams: {len(audio_streams)}",
    ]
    if contact:
        md.append(f"Contact sheet: `{contact}`")
    md.extend(
        [
            "",
            "## Pacing Profile",
            f"- Scene detection: `{pacing.get('status')}` at threshold `{pacing.get('sceneThreshold')}`",
            f"- Estimated shots: `{pacing.get('estimatedShotCount', 0)}`",
            f"- Average shot length: `{pacing.get('averageShotLengthSeconds', 0)}` seconds",
            f"- Median shot length: `{pacing.get('medianShotLengthSeconds', 0)}` seconds",
            f"- Long shots >=20s: `{pacing.get('longShotCountOver20s', 0)}`",
            f"- Short shots <=3s: `{pacing.get('shortShotCountUnder3s', 0)}`",
            "",
            "## Audio Profile",
            f"- Audio analysis: `{audio.get('status')}`",
            f"- Mean volume: `{audio.get('meanVolumeDb')}` dB",
            f"- Max volume: `{audio.get('maxVolumeDb')}` dB",
            f"- Detected silence: `{audio.get('totalDetectedSilenceSeconds', 0)}` seconds across `{audio.get('silenceEventCount', 0)}` events",
            "",
            "## Style Targets",
        ]
    )
    for key, value in report["styleTargets"].items():
        md.append(f"- `{key}`: {json.dumps(value, ensure_ascii=False)}")
    md.extend(["", "## Sample Frame Review Worksheet"])
    for sample in sample_rows:
        md.append(f"- `{sample['timecode']}` `{sample['framePath']}` - {sample['visualReviewPrompt']}")
    md.extend(
        [
            "",
            "## Full-Film Review Contract",
            "- Run `prepare_reference_review_repair_plan.py` after batch profiling.",
            "- Close the repair row with full-film timeline strip evidence, opening/title observations, chapter rhythm, transition language, ending aftertaste, BGM/audio/caption behavior, and non-copying Skill takeaways.",
            "- Do not treat this per-video analysis as complete reference learning until the repair plan returns `ready_no_reference_review_repairs_needed`.",
        ]
    )
    md.extend(["", "## Style Implications"])
    md.extend(f"- {item}" for item in report["styleImplications"])
    md.extend(
        [
            "",
            "## Usage Contract",
            f"- Allowed: {report['referenceUsageContract']['allowed']}",
            f"- Forbidden: {report['referenceUsageContract']['forbidden']}",
        ]
    )
    (output_dir / "reference_analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze long-form travel reference video.")
    parser.add_argument("--reference", default=default_reference_video(), help="Reference video path. Defaults to TRAVEL_VIDEO_REFERENCE when set.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--skip-contact-sheet", action="store_true")
    parser.add_argument("--skip-scene-detect", action="store_true")
    parser.add_argument("--skip-audio-analysis", action="store_true")
    parser.add_argument("--scene-threshold", type=float, default=0.35)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.reference:
        parser.error("--reference is required unless TRAVEL_VIDEO_REFERENCE is set")
    report = build_report(
        Path(args.reference).expanduser().resolve(),
        Path(args.output_dir).expanduser().resolve(),
        args.skip_contact_sheet,
        args.skip_scene_detect,
        args.skip_audio_analysis,
        args.scene_threshold,
        args.frames,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Reference duration: {report['durationMinutes']} minutes")
        if report.get("contactSheet"):
            print(f"Contact sheet: {report['contactSheet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
