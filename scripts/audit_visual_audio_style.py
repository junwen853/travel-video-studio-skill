#!/usr/bin/env python3
"""Audit final travel edits for visual polish and BGM policy regressions."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any


FRAME_W = 640
FRAME_H = 360


def run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def ffprobe_json(path: Path) -> dict[str, Any]:
    proc = run(
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
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    return json.loads(proc.stdout.decode("utf-8"))


def parse_sample_seconds(raw: str) -> list[float]:
    out: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out


def ffmpeg_precise_seek_args(second: float, preroll_seconds: float = 2.0) -> tuple[list[str], list[str]]:
    target = max(second, 0.0)
    pre_seek = max(0.0, target - preroll_seconds)
    post_seek = max(0.0, target - pre_seek)
    return ["-ss", f"{pre_seek:.3f}", "-accurate_seek"], ["-ss", f"{post_seek:.3f}"]


def extract_jpeg(video: Path, second: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pre_seek, post_seek = ffmpeg_precise_seek_args(second)
    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *pre_seek,
            "-i",
            str(video),
            *post_seek,
            "-frames:v",
            "1",
            "-vf",
            f"scale={FRAME_W}:{FRAME_H}:force_original_aspect_ratio=decrease,"
            f"pad={FRAME_W}:{FRAME_H}:(ow-iw)/2:(oh-ih)/2:black",
            "-q:v",
            "2",
            str(out_path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())


def extract_ocr_jpeg(video: Path, second: float, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pre_seek, post_seek = ffmpeg_precise_seek_args(second)
    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *pre_seek,
            "-i",
            str(video),
            *post_seek,
            "-frames:v",
            "1",
            "-vf",
            "scale=1920:-1:force_original_aspect_ratio=decrease,unsharp=5:5:0.8:3:3:0.4",
            "-q:v",
            "2",
            str(out_path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())


def frame_gray_bytes(video: Path, second: float) -> bytes:
    pre_seek, post_seek = ffmpeg_precise_seek_args(second)
    proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            *pre_seek,
            "-i",
            str(video),
            *post_seek,
            "-frames:v",
            "1",
            "-vf",
            f"scale={FRAME_W}:{FRAME_H}:force_original_aspect_ratio=decrease,"
            f"pad={FRAME_W}:{FRAME_H}:(ow-iw)/2:(oh-ih)/2:black,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    data = proc.stdout
    expected = FRAME_W * FRAME_H
    if len(data) != expected:
        raise RuntimeError(f"Expected {expected} gray bytes, got {len(data)}")
    return data


def crop_values(data: bytes, x0: int, x1: int, y0: int = 0, y1: int = FRAME_H) -> list[int]:
    values: list[int] = []
    for y in range(y0, y1):
        start = y * FRAME_W + x0
        values.extend(data[start : y * FRAME_W + x1])
    return values


def frame_metrics(video: Path, second: float) -> dict[str, Any]:
    data = frame_gray_bytes(video, second)
    side_w = int(FRAME_W * 0.115)
    center_margin = int(FRAME_W * 0.28)
    left = crop_values(data, 0, side_w)
    right = crop_values(data, FRAME_W - side_w, FRAME_W)
    center = crop_values(data, center_margin, FRAME_W - center_margin, int(FRAME_H * 0.15), int(FRAME_H * 0.85))

    def mean(values: list[int]) -> float:
        return statistics.fmean(values) if values else 0.0

    def stdev(values: list[int]) -> float:
        return statistics.pstdev(values) if len(values) > 1 else 0.0

    def dark_ratio(values: list[int], threshold: int = 12) -> float:
        return sum(1 for v in values if v <= threshold) / max(1, len(values))

    left_mean = mean(left)
    right_mean = mean(right)
    center_mean = mean(center)
    side_mean = (left_mean + right_mean) / 2.0
    left_dark = dark_ratio(left)
    right_dark = dark_ratio(right)
    side_dark = min(left_dark, right_dark)
    side_std = (stdev(left) + stdev(right)) / 2.0
    contrast = max(0.0, center_mean - side_mean) / 255.0
    pillarbox_score = side_dark * contrast
    suspected = (
        left_dark >= 0.72
        and right_dark >= 0.72
        and side_mean <= 24
        and side_std <= 28
        and center_mean >= 35
        and pillarbox_score >= 0.12
    )
    return {
        "second": second,
        "leftMean": round(left_mean, 3),
        "rightMean": round(right_mean, 3),
        "centerMean": round(center_mean, 3),
        "sideDarkRatio": round(side_dark, 4),
        "sideStd": round(side_std, 3),
        "pillarboxScore": round(pillarbox_score, 4),
        "pillarboxSuspected": suspected,
    }


def maybe_make_contact_sheet(frame_paths: list[Path], output: Path) -> str | None:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    if not frame_paths:
        return None
    images = [Image.open(p).convert("RGB") for p in frame_paths]
    cols = min(4, len(images))
    rows = math.ceil(len(images) / cols)
    label_h = 34
    sheet = Image.new("RGB", (cols * FRAME_W, rows * (FRAME_H + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (path, img) in enumerate(zip(frame_paths, images)):
        x = (idx % cols) * FRAME_W
        y = (idx // cols) * (FRAME_H + label_h)
        sheet.paste(img, (x, y))
        draw.text((x + 10, y + FRAME_H + 8), path.stem, fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    return str(output)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def video_duration_from_probe(probe: dict[str, Any]) -> float:
    try:
        return float(probe.get("format", {}).get("duration", 0.0))
    except (TypeError, ValueError):
        return 0.0


def parse_ebur128_summary(text: str) -> dict[str, float | None]:
    integrated = None
    lra = None
    true_peak = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("I:"):
            match = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s+LUFS", stripped)
            if match:
                integrated = float(match.group(1))
        elif stripped.startswith("LRA:"):
            match = re.search(r"LRA:\s*(-?\d+(?:\.\d+)?)\s+LU", stripped)
            if match:
                lra = float(match.group(1))
        elif stripped.startswith("Peak:"):
            match = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", stripped)
            if match:
                true_peak = float(match.group(1))
    return {"integratedLufs": integrated, "loudnessRangeLu": lra, "truePeakDbfs": true_peak}


def parse_silence_segments(text: str, duration: float) -> list[dict[str, float]]:
    segments: list[dict[str, float]] = []
    open_start: float | None = None
    for line in text.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            open_start = float(start_match.group(1))
        end_match = re.search(
            r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)",
            line,
        )
        if end_match:
            end = float(end_match.group(1))
            dur = float(end_match.group(2))
            start = open_start if open_start is not None else max(0.0, end - dur)
            segments.append({"start": start, "end": end, "duration": dur})
            open_start = None
    if open_start is not None and duration > open_start:
        segments.append({"start": open_start, "end": duration, "duration": duration - open_start})
    return segments


def analyze_audio(video: Path, probe: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    duration = video_duration_from_probe(probe)
    result: dict[str, Any] = {
        "duration": duration,
        "loudness": {},
        "silenceSegments": [],
        "silenceSeconds": 0.0,
        "silenceRatio": 0.0,
    }
    ebur_proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-filter_complex",
            "ebur128=peak=true:framelog=quiet",
            "-f",
            "null",
            "-",
        ]
    )
    if ebur_proc.returncode == 0:
        ebur_text = ebur_proc.stderr.decode("utf-8", "replace")
        result["loudness"] = parse_ebur128_summary(ebur_text)
    else:
        result["loudnessError"] = ebur_proc.stderr.decode("utf-8", "replace").strip()

    silence_proc = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-af",
            f"silencedetect=n={args.silence_threshold_db}dB:d={args.silence_min_duration}",
            "-f",
            "null",
            "-",
        ]
    )
    if silence_proc.returncode == 0:
        silence_text = silence_proc.stderr.decode("utf-8", "replace")
        segments = parse_silence_segments(silence_text, duration)
        result["silenceSegments"] = segments
        silence_seconds = sum(max(0.0, item["duration"]) for item in segments)
        result["silenceSeconds"] = round(silence_seconds, 3)
        result["silenceRatio"] = round(silence_seconds / duration, 5) if duration > 0 else 0.0
    else:
        result["silenceError"] = silence_proc.stderr.decode("utf-8", "replace").strip()
    return result


def normalize_ocr_text(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).upper()


def parse_csv_terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def manifest_title_sample_seconds(path: Path | None) -> list[float]:
    if not path or not path.exists():
        return []
    manifest = load_json(path)
    out: list[float] = []
    for item in manifest.get("segments", []):
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode", "")).lower()
        if mode not in {"opening", "chapter", "ending", "transition"}:
            continue
        raw_start = item.get("timeline_start", item.get("timelineStartSeconds"))
        try:
            start = float(raw_start)
        except (TypeError, ValueError):
            continue
        try:
            duration = float(item.get("duration", 0.0))
        except (TypeError, ValueError):
            duration = 0.0
        out.append(start)
        if duration > 0:
            out.append(start + min(2.0, max(0.0, duration / 2.0)))
    return out


def unique_seconds(values: list[float]) -> list[float]:
    seen: set[int] = set()
    out: list[float] = []
    for value in values:
        key = round(max(value, 0.0) * 1000)
        if key in seen:
            continue
        seen.add(key)
        out.append(round(max(value, 0.0), 3))
    return out


def manifest_title_terms(path: Path | None) -> tuple[str | None, list[str]]:
    if not path or not path.exists():
        return None, []
    manifest = load_json(path)
    expected = manifest.get("cityTitle") or manifest.get("expectedOpeningTitle")
    forbidden = manifest.get("forbiddenOpeningText", [])
    if not isinstance(forbidden, list):
        forbidden = []
    return str(expected) if expected else None, [str(item) for item in forbidden]


def ocr_frame(path: Path, lang: str) -> dict[str, Any]:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return {"available": False, "text": "", "normalizedText": "", "error": "tesseract not found"}
    proc = run(
        [
            tesseract,
            str(path),
            "stdout",
            "-l",
            lang,
            "--psm",
            "11",
        ]
    )
    text = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace").strip()
    return {
        "available": True,
        "returnCode": proc.returncode,
        "text": text.strip(),
        "normalizedText": normalize_ocr_text(text),
        "error": err,
    }


def audit_title_ocr(
    video: Path,
    output_dir: Path,
    sample_seconds: list[float],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    mode = args.title_ocr_mode
    if mode == "skip":
        return {"mode": "skip", "frames": []}, failures, warnings

    manifest_expected, manifest_forbidden = manifest_title_terms(
        Path(args.visual_manifest) if args.visual_manifest else None
    )
    expected = args.expected_title or manifest_expected
    forbidden_terms = manifest_forbidden + parse_csv_terms(args.forbidden_title_text)
    if not expected and args.require_clean_title:
        warnings.append("Clean title OCR has no expected title; provide cityTitle in the visual manifest or --expected-title.")

    tesseract_available = shutil.which("tesseract") is not None
    if not tesseract_available:
        message = "Tesseract OCR is not available; title text OCR was skipped."
        if mode == "required":
            failures.append(message)
        else:
            warnings.append(message)
        return {"mode": mode, "available": False, "frames": []}, failures, warnings

    ocr_seconds = sample_seconds[: max(1, args.max_ocr_frames)]
    frames_dir = output_dir / "ocr_frames"
    frame_reports: list[dict[str, Any]] = []
    combined_norm = ""
    for second in ocr_seconds:
        safe_name = f"ocr_{second:09.3f}".replace(".", "_")
        frame_path = frames_dir / f"{safe_name}.jpg"
        extract_ocr_jpeg(video, second, frame_path)
        frame_report = ocr_frame(frame_path, args.ocr_lang)
        frame_report["second"] = second
        frame_report["frame"] = str(frame_path)
        frame_reports.append(frame_report)
        combined_norm += frame_report.get("normalizedText", "")

    for term in forbidden_terms:
        if normalize_ocr_text(term) and normalize_ocr_text(term) in combined_norm:
            failures.append(f"Forbidden title/opening text detected by OCR: {term}")

    expected_norm = normalize_ocr_text(expected) if expected else ""
    expected_found = bool(expected_norm and expected_norm in combined_norm)
    if expected_norm and not expected_found:
        message = f"Expected opening title was not detected by OCR: {expected}"
        if mode == "required":
            failures.append(message)
        else:
            warnings.append(message)

    return {
        "mode": mode,
        "available": True,
        "lang": args.ocr_lang,
        "expectedTitle": expected,
        "expectedTitleFound": expected_found,
        "forbiddenTerms": forbidden_terms,
        "frames": frame_reports,
    }, failures, warnings


def audit_visual_manifest(path: Path | None, require_clean_title: bool) -> list[str]:
    failures: list[str] = []
    if not path:
        if require_clean_title:
            failures.append("Clean title was required but no visual manifest was provided.")
        return failures
    if not path.exists():
        failures.append(f"Visual manifest does not exist: {path}")
        return failures
    manifest = load_json(path)
    fixes = " ".join(str(item).lower() for item in manifest.get("fixes", []))
    opening_policy = str(manifest.get("openingTitlePolicy", "")).lower()
    opening_segment = str(manifest.get("openingSegment", "")).lower()
    if require_clean_title:
        evidence = "single" in fixes and "title" in fixes
        policy_ok = "single" in opening_policy and "title" in opening_policy
        filename_ok = "title_only" in opening_segment
        if not (evidence or policy_ok or filename_ok):
            failures.append(
                "Visual manifest does not prove a single clean opening title policy."
            )
    forbidden_text = manifest.get("forbiddenOpeningText", [])
    if forbidden_text and not isinstance(forbidden_text, list):
        failures.append("forbiddenOpeningText must be a list when present.")
    return failures


def audit_bgm_manifest(path: Path | None, video_probe: dict[str, Any], audio_mode: str) -> list[str]:
    failures: list[str] = []
    if audio_mode == "skip":
        return failures
    audio_streams = [
        s for s in video_probe.get("streams", []) if s.get("codec_type") == "audio"
    ]
    if not audio_streams:
        failures.append("Audio mode requires final audio, but the video has no audio stream.")
    if not path:
        failures.append("Audio mode requires a BGM manifest, but none was provided.")
        return failures
    if not path.exists():
        failures.append(f"BGM manifest does not exist: {path}")
        return failures
    manifest = load_json(path)
    mode = str(manifest.get("mode", "")).lower()
    if audio_mode == "bgm_only" and "bgm" not in mode:
        failures.append("BGM manifest mode does not declare a BGM-led mix.")
    if audio_mode == "bgm_only" and "camera" not in mode and "voice" not in mode:
        failures.append("BGM-only mode must explicitly document no camera/source voice.")
    output = manifest.get("output")
    if not output or not Path(str(output)).exists():
        failures.append("BGM manifest output file is missing.")
    tracks = manifest.get("tracks", [])
    if not isinstance(tracks, list) or not tracks:
        failures.append("BGM manifest must list at least one track.")
    else:
        for idx, track in enumerate(tracks):
            if not isinstance(track, dict):
                failures.append(f"BGM track {idx} is not an object.")
                continue
            license_url = str(track.get("license", ""))
            if not license_url.startswith(("http://", "https://")):
                failures.append(f"BGM track {idx} has no license URL.")
            path_value = track.get("path")
            if not path_value or not Path(str(path_value)).exists():
                failures.append(f"BGM track {idx} local file is missing.")
    return failures


def audit(args: argparse.Namespace) -> dict[str, Any]:
    video = Path(args.video)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not video.exists():
        raise FileNotFoundError(video)
    probe = ffprobe_json(video)
    visual_manifest_path = Path(args.visual_manifest) if args.visual_manifest else None
    samples = unique_seconds(
        parse_sample_seconds(args.sample_seconds)
        + manifest_title_sample_seconds(visual_manifest_path)
    )
    frames_dir = output_dir / "frames"
    ocr_frames_dir = output_dir / "ocr_frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    shutil.rmtree(ocr_frames_dir, ignore_errors=True)
    frame_paths: list[Path] = []
    sample_reports: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    for second in samples:
        safe_name = f"sample_{second:09.3f}".replace(".", "_")
        jpeg_path = frames_dir / f"{safe_name}.jpg"
        extract_jpeg(video, second, jpeg_path)
        frame_paths.append(jpeg_path)
        metrics = frame_metrics(video, second)
        sample_reports.append(metrics)
        if metrics["pillarboxSuspected"]:
            failures.append(
                f"Pillarbox/vertical content suspected at {second:.3f}s "
                f"(score={metrics['pillarboxScore']})."
            )

    failures.extend(
        audit_visual_manifest(
            Path(args.visual_manifest) if args.visual_manifest else None,
            args.require_clean_title,
        )
    )
    failures.extend(
        audit_bgm_manifest(
            Path(args.bgm_manifest) if args.bgm_manifest else None,
            probe,
            args.audio_mode,
        )
    )
    audio_analysis: dict[str, Any] | None = None
    if args.audio_mode != "skip":
        audio_analysis = analyze_audio(video, probe, args)
        loudness = audio_analysis.get("loudness", {})
        integrated = loudness.get("integratedLufs") if isinstance(loudness, dict) else None
        silence_ratio = float(audio_analysis.get("silenceRatio", 0.0))
        if integrated is None:
            failures.append("Could not measure integrated loudness for the final audio.")
        elif integrated < args.min_integrated_lufs:
            failures.append(
                f"Audio is too quiet for BGM delivery: integrated loudness {integrated:.1f} LUFS "
                f"is below minimum {args.min_integrated_lufs:.1f} LUFS."
            )
        if silence_ratio > args.max_silence_ratio:
            failures.append(
                f"Audio has too much silence: {silence_ratio:.1%} exceeds maximum {args.max_silence_ratio:.1%}."
            )

    title_ocr, ocr_failures, ocr_warnings = audit_title_ocr(video, output_dir, samples, args)
    failures.extend(ocr_failures)
    warnings.extend(ocr_warnings)
    contact_sheet = maybe_make_contact_sheet(frame_paths, output_dir / "contact_sheet.jpg")
    status = "blocked" if failures else "passed"
    report = {
        "status": status,
        "video": str(video),
        "probe": probe,
        "audioMode": args.audio_mode,
        "sampleSeconds": samples,
        "samples": sample_reports,
        "visualManifest": args.visual_manifest,
        "bgmManifest": args.bgm_manifest,
        "audioAnalysis": audio_analysis,
        "titleOcr": title_ocr,
        "contactSheet": contact_sheet,
        "warnings": warnings,
        "failures": failures,
    }
    report_path = output_dir / "visual_audio_style_audit.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = [
        "# Visual Audio Style Audit",
        "",
        f"Status: `{status}`",
        f"Video: `{video}`",
        f"Audio mode: `{args.audio_mode}`",
        "",
        "## Failures",
    ]
    if failures:
        md_lines.extend(f"- {item}" for item in failures)
    else:
        md_lines.append("- None")
    md_lines.extend(["", "## Warnings"])
    if warnings:
        md_lines.extend(f"- {item}" for item in warnings)
    else:
        md_lines.append("- None")
    if audio_analysis:
        loudness = audio_analysis.get("loudness", {})
        md_lines.extend(
            [
                "",
                "## Audio",
                f"- Integrated loudness: `{loudness.get('integratedLufs')}` LUFS",
                f"- Loudness range: `{loudness.get('loudnessRangeLu')}` LU",
                f"- True peak: `{loudness.get('truePeakDbfs')}` dBFS",
                f"- Silence ratio: `{audio_analysis.get('silenceRatio')}`",
                f"- Silence seconds: `{audio_analysis.get('silenceSeconds')}`",
            ]
        )
    if title_ocr.get("mode") != "skip":
        md_lines.extend(
            [
                "",
                "## Title OCR",
                f"- Mode: `{title_ocr.get('mode')}`",
                f"- Expected title: `{title_ocr.get('expectedTitle')}`",
                f"- Expected title found: `{title_ocr.get('expectedTitleFound')}`",
                f"- Forbidden terms: `{title_ocr.get('forbiddenTerms')}`",
            ]
        )
        for frame in title_ocr.get("frames", []):
            text = str(frame.get("text", "")).replace("\n", " ")[:220]
            md_lines.append(f"- {frame.get('second')}s OCR: `{text}`")
    md_lines.extend(["", "## Samples"])
    for item in sample_reports:
        md_lines.append(
            "- {second:.3f}s: pillarbox={pillarboxSuspected}, score={pillarboxScore}, "
            "sideDark={sideDarkRatio}, centerMean={centerMean}".format(**item)
        )
    if contact_sheet:
        md_lines.extend(["", f"Contact sheet: `{contact_sheet}`"])
    (output_dir / "visual_audio_style_audit.md").write_text(
        "\n".join(md_lines) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sample-seconds", required=True)
    parser.add_argument("--visual-manifest")
    parser.add_argument("--bgm-manifest")
    parser.add_argument(
        "--audio-mode",
        choices=["skip", "bgm_only", "bgm_dominant"],
        default="skip",
    )
    parser.add_argument("--require-clean-title", action="store_true")
    parser.add_argument("--min-integrated-lufs", type=float, default=-35.0)
    parser.add_argument("--max-silence-ratio", type=float, default=0.20)
    parser.add_argument("--silence-threshold-db", default="-45")
    parser.add_argument("--silence-min-duration", type=float, default=0.75)
    parser.add_argument(
        "--title-ocr-mode",
        choices=["skip", "auto", "required"],
        default="auto",
    )
    parser.add_argument("--expected-title")
    parser.add_argument("--forbidden-title-text")
    parser.add_argument("--ocr-lang", default="eng+chi_sim+jpn")
    parser.add_argument("--max-ocr-frames", type=int, default=24)
    args = parser.parse_args()
    try:
        report = audit(args)
    except Exception as exc:
        print(f"audit_visual_audio_style failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "failures": report["failures"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
