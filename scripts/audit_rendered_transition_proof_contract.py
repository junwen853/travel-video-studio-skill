#!/usr/bin/env python3
"""Audit rendered transition windows from the final MP4, not just the blueprint."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


FRAME_W = 640
FRAME_H = 360
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
VISIBLE_TERMS = ("rotation", "whip", "push", "speed", "zoom", "dissolve", "breath", "motion")
UPSTREAM_REPORTS = {
    "renderDeliveryVerification": (("render_delivery_verification.json",), {"passed"}),
    "visualAudioStyleAudit": (
        ("visual_audio_style_audit/visual_audio_style_audit.json", "visual_audio_style_audit.json"),
        {"passed"},
    ),
    "bgmAudioContractAudit": (("bgm_audio_contract_audit.json",), {"passed", "passed_with_warnings"}),
    "transitionEffectRecipeContractAudit": (("transition_effect_recipe_contract_audit.json",), {"passed"}),
}


def run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean(value: Any, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def resolve_package_path(package_dir: Path, raw: Any) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    return path if path.is_absolute() else (package_dir / path).resolve()


def infer_output(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for report_name in ("render_delivery_verification.json", "FINAL_DELIVERY_REPORT.json"):
        report = load_json(package_dir / report_name) or {}
        candidate = report.get("output") or report.get("finalOutput")
        path = resolve_package_path(package_dir, candidate)
        if path and path.exists():
            return path
    plan = load_json(package_dir / "render_plan.json") or {}
    for key in ("finalOutput", "output"):
        path = resolve_package_path(package_dir, plan.get(key))
        if path and path.exists():
            return path
    if plan.get("targetDir") and plan.get("customName"):
        target_dir = resolve_package_path(package_dir, plan.get("targetDir"))
        if target_dir:
            candidate = target_dir / f"{plan['customName']}.mp4"
            if candidate.exists():
                return candidate.resolve()
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    return renders[0].resolve() if renders else None


def ffprobe_duration(path: Path) -> tuple[float, dict[str, Any], str | None]:
    proc = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-show_streams", "-of", "json", str(path)])
    if proc.returncode != 0:
        return 0.0, {}, proc.stderr.decode("utf-8", "replace").strip()
    try:
        probe = json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return 0.0, {}, str(exc)
    return as_float((probe.get("format") or {}).get("duration")), probe, None


def report_status(package_dir: Path, candidates: tuple[str, ...]) -> tuple[Path | None, str | None]:
    for relative in candidates:
        path = package_dir / relative
        data = load_json(path)
        if isinstance(data, dict):
            return path, data.get("status")
    return None, None


def upstream_evidence(package_dir: Path, skip: bool) -> tuple[dict[str, Any], list[str]]:
    evidence: dict[str, Any] = {}
    blockers: list[str] = []
    if skip:
        return {"skipped": True}, blockers
    for name, (candidates, accepted) in UPSTREAM_REPORTS.items():
        path, status = report_status(package_dir, candidates)
        evidence[name] = {
            "path": str(path) if path else None,
            "status": status,
            "acceptedStatuses": sorted(accepted),
            "accepted": status in accepted,
        }
        if status not in accepted:
            blockers.append(f"{name} status is {status}; expected one of {sorted(accepted)}")
    return evidence, blockers


def blueprint_candidates(package_dir: Path, explicit: str | None) -> list[Path]:
    out: list[Path] = []
    if explicit:
        out.append(resolve_package_path(package_dir, explicit) or Path(explicit).expanduser().resolve())
    out.append(package_dir / "resolve_timeline_blueprint.json")
    for report_path in (
        package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json",
        package_dir / "final_blueprint_lineage_contract_audit.json",
    ):
        report = load_json(report_path) or {}
        outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        for key in ("candidateBlueprint", "activeBlueprint", "finalBlueprint"):
            path = resolve_package_path(package_dir, outputs.get(key) or summary.get(key))
            if path:
                out.append(path)
    out.extend(
        [
            package_dir / "transition_execution_blueprint" / "resolve_timeline_blueprint_transition_execution.json",
            package_dir / "transition_polish_blueprint" / "resolve_timeline_blueprint_transition_polish.json",
            package_dir / "rhythm_recut_blueprint" / "resolve_timeline_blueprint_rhythm_recut.json",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in out:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def marker_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for marker in blueprint.get("timelineMarkers") or []:
        if not isinstance(marker, dict):
            continue
        role = str(marker.get("role") or "").lower()
        name = str(marker.get("name") or "").lower()
        if "transition" not in role and "transition" not in name:
            continue
        payload = marker.get("payload") if isinstance(marker.get("payload"), dict) else {}
        rows.append(
            {
                "rowIndex": payload.get("rowIndex") or marker.get("name"),
                "boundaryCategory": payload.get("boundaryCategory") or marker.get("role"),
                "boundarySeconds": marker.get("startSeconds"),
                "durationSeconds": marker.get("durationSeconds"),
                "approvedTransitionType": payload.get("selectedCandidateType") or payload.get("resolveEffectName"),
                "resolveEffectName": payload.get("resolveEffectName") or marker.get("note"),
                "source": "timelineMarkers",
            }
        )
    return rows


def load_transition_rows(package_dir: Path, explicit: str | None) -> tuple[Path | None, list[dict[str, Any]]]:
    best_path: Path | None = None
    best_rows: list[dict[str, Any]] = []
    for path in blueprint_candidates(package_dir, explicit):
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        rows = [row for row in data.get("transitions") or [] if isinstance(row, dict)]
        if not rows:
            rows = marker_rows(data)
        if rows:
            best_path = path
            best_rows = rows
            break
    return best_path, best_rows


def transition_second(row: dict[str, Any]) -> float | None:
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds", "recordStartSeconds", "seconds"):
        if row.get(key) is not None:
            return as_float(row.get(key), -1.0)
    cutpoint = row.get("transitionCutpointPlan") if isinstance(row.get("transitionCutpointPlan"), dict) else {}
    for key in ("boundarySeconds", "hitSeconds", "startSeconds"):
        if cutpoint.get(key) is not None:
            return as_float(cutpoint.get(key), -1.0)
    return None


def style_blob(row: dict[str, Any]) -> str:
    motion = row.get("transitionMotionExecution") if isinstance(row.get("transitionMotionExecution"), dict) else {}
    recipe = motion.get("resolveKeyframeRecipe") if isinstance(motion.get("resolveKeyframeRecipe"), dict) else {}
    return " ".join(
        clean(value).lower()
        for value in (
            row.get("boundaryCategory"),
            row.get("approvedTransitionType"),
            row.get("selectedCandidateType"),
            row.get("selectedStyleFamily"),
            row.get("resolveEffectName"),
            motion.get("sourceTransitionStyle"),
            motion.get("choreographyFamily"),
            recipe.get("effect"),
        )
    )


def transition_rank(row: dict[str, Any]) -> tuple[int, float]:
    blob = style_blob(row)
    category = str(row.get("boundaryCategory") or "").lower()
    important = category in IMPORTANT_CATEGORIES or any(term in blob for term in VISIBLE_TERMS)
    return (0 if important else 1, as_float(transition_second(row), 0.0))


def selected_rows(rows: list[dict[str, Any]], duration: float, max_rows: int) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for row in rows:
        second = transition_second(row)
        if second is None or second < 0 or second > max(duration, 0.0):
            continue
        clone = dict(row)
        clone["renderBoundarySeconds"] = round(second, 3)
        valid.append(clone)
    return sorted(valid, key=transition_rank)[:max_rows]


def seek_args(second: float, preroll: float = 2.0) -> tuple[list[str], list[str]]:
    target = max(second, 0.0)
    pre_seek = max(0.0, target - preroll)
    post_seek = max(0.0, target - pre_seek)
    return ["-ss", f"{pre_seek:.3f}", "-accurate_seek"], ["-ss", f"{post_seek:.3f}"]


def gray_frame(video: Path, second: float) -> bytes:
    pre_seek, post_seek = seek_args(second)
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
    expected = FRAME_W * FRAME_H
    if len(proc.stdout) != expected:
        raise RuntimeError(f"Expected {expected} gray bytes, got {len(proc.stdout)}")
    return proc.stdout


def extract_jpeg(video: Path, second: float, out_path: Path) -> None:
    pre_seek, post_seek = seek_args(second)
    out_path.parent.mkdir(parents=True, exist_ok=True)
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


def crop(data: bytes, x0: int, x1: int, y0: int = 0, y1: int = FRAME_H) -> list[int]:
    out: list[int] = []
    for y in range(y0, y1):
        out.extend(data[y * FRAME_W + x0 : y * FRAME_W + x1])
    return out


def frame_metrics(data: bytes, second: float, args: argparse.Namespace) -> dict[str, Any]:
    values = list(data)
    mean = statistics.fmean(values)
    stddev = statistics.pstdev(values) if len(values) > 1 else 0.0
    side_w = int(FRAME_W * 0.115)
    center_margin = int(FRAME_W * 0.28)
    left = crop(data, 0, side_w)
    right = crop(data, FRAME_W - side_w, FRAME_W)
    center = crop(data, center_margin, FRAME_W - center_margin, int(FRAME_H * 0.15), int(FRAME_H * 0.85))

    def avg(raw: list[int]) -> float:
        return statistics.fmean(raw) if raw else 0.0

    def stdev(raw: list[int]) -> float:
        return statistics.pstdev(raw) if len(raw) > 1 else 0.0

    def dark(raw: list[int]) -> float:
        return sum(1 for value in raw if value <= args.pillarbox_dark_threshold) / max(1, len(raw))

    left_mean = avg(left)
    right_mean = avg(right)
    center_mean = avg(center)
    side_mean = (left_mean + right_mean) / 2.0
    side_std = (stdev(left) + stdev(right)) / 2.0
    side_dark = min(dark(left), dark(right))
    contrast = max(0.0, center_mean - side_mean) / 255.0
    pillarbox_score = side_dark * contrast
    return {
        "second": round(second, 3),
        "meanLuma": round(mean, 3),
        "stddevLuma": round(stddev, 3),
        "minLuma": min(values),
        "maxLuma": max(values),
        "likelyBlank": bool(mean <= args.blank_luma_mean or (mean <= args.blank_luma_near_black_mean and stddev <= args.blank_luma_std)),
        "likelyWhiteFlash": bool(mean >= args.white_luma_mean and stddev <= args.white_luma_std),
        "leftMean": round(left_mean, 3),
        "rightMean": round(right_mean, 3),
        "centerMean": round(center_mean, 3),
        "sideDarkRatio": round(side_dark, 4),
        "sideStd": round(side_std, 3),
        "pillarboxScore": round(pillarbox_score, 4),
        "pillarboxSuspected": bool(
            side_dark >= args.pillarbox_min_side_dark_ratio
            and side_mean <= args.pillarbox_max_side_mean
            and side_std <= args.pillarbox_max_side_std
            and center_mean >= args.pillarbox_min_center_mean
            and pillarbox_score >= args.pillarbox_min_score
        ),
    }


def sample_times(boundary: float, duration: float, args: argparse.Namespace) -> list[float]:
    raw = [boundary - args.pre_seconds, boundary, boundary + args.post_seconds, boundary + args.landing_hold_seconds]
    out: list[float] = []
    seen: set[int] = set()
    for value in raw:
        second = min(max(value, 0.0), max(duration - 0.04, 0.0))
        key = round(second * 1000)
        if key not in seen:
            seen.add(key)
            out.append(round(second, 3))
    return out


def audit_row(video: Path, row: dict[str, Any], output_dir: Path, duration: float, args: argparse.Namespace) -> dict[str, Any]:
    boundary = as_float(row.get("renderBoundarySeconds"))
    row_id = clean(row.get("rowIndex") or len(str(row)), 80)
    row_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", row_id).strip("_") or "transition"
    samples: list[dict[str, Any]] = []
    issues: list[str] = []
    frame_paths: list[str] = []
    for idx, second in enumerate(sample_times(boundary, duration, args), start=1):
        frame_path = output_dir / "frames" / f"transition_{row_slug}_{idx}_{second:.3f}s.jpg"
        try:
            gray = gray_frame(video, second)
            metrics = frame_metrics(gray, second, args)
            extract_jpeg(video, second, frame_path)
            metrics["frame"] = str(frame_path)
            frame_paths.append(str(frame_path))
            samples.append(metrics)
        except Exception as exc:  # noqa: BLE001
            samples.append({"second": second, "extracted": False, "error": str(exc)})
            issues.append("frame_extraction_failed")

    if any(item.get("likelyBlank") for item in samples):
        issues.append("black_or_blank_frame_in_transition_window")
    if any(item.get("likelyWhiteFlash") for item in samples):
        issues.append("white_flash_frame_in_transition_window")
    if any(item.get("pillarboxSuspected") for item in samples):
        issues.append("pillarbox_or_raw_vertical_frame_in_transition_window")
    means = [as_float(item.get("meanLuma")) for item in samples if item.get("meanLuma") is not None]
    max_jump = max([abs(a - b) for a, b in zip(means, means[1:])] or [0.0])
    if max_jump >= args.max_flash_luma_delta:
        issues.append("strobe_like_luma_jump_in_transition_window")
    landing_means = means[-2:]
    landing_jump = abs(landing_means[1] - landing_means[0]) if len(landing_means) == 2 else 0.0
    warnings: list[str] = []
    if landing_jump >= args.max_landing_luma_delta:
        warnings.append("landing_hold_luma_changed_too_much_to_prove_settlement")

    return {
        "rowIndex": row.get("rowIndex"),
        "status": "passed" if not issues else "blocked",
        "boundarySeconds": boundary,
        "boundaryCategory": row.get("boundaryCategory"),
        "approvedTransitionType": row.get("approvedTransitionType") or row.get("selectedCandidateType"),
        "resolveEffectName": row.get("resolveEffectName"),
        "samples": samples,
        "maxLumaJump": round(max_jump, 3),
        "landingLumaJump": round(landing_jump, 3),
        "framePaths": frame_paths,
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
    }


def maybe_contact_sheet(paths: list[str], output: Path) -> str | None:
    try:
        from PIL import Image, ImageDraw  # type: ignore[import-not-found]
    except Exception:
        return None
    if not paths:
        return None
    images = []
    for raw in paths[:80]:
        path = Path(raw)
        if path.exists():
            images.append((path, Image.open(path).convert("RGB")))
    if not images:
        return None
    cols = min(4, len(images))
    rows = math.ceil(len(images) / cols)
    label_h = 32
    sheet = Image.new("RGB", (cols * FRAME_W, rows * (FRAME_H + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (path, img) in enumerate(images):
        x = (idx % cols) * FRAME_W
        y = (idx // cols) * (FRAME_H + label_h)
        sheet.paste(img, (x, y))
        draw.text((x + 8, y + FRAME_H + 8), path.stem[:90], fill=(20, 20, 20))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    return str(output)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = package_dir / "qa" / "rendered_transition_proof"
    output_dir.mkdir(parents=True, exist_ok=True)
    blockers: list[str] = []
    warnings: list[str] = []
    output = infer_output(package_dir, args.output)
    if not output or not output.exists():
        blockers.append("No final render MP4 could be inferred. Pass --output explicitly.")
        duration = 0.0
        probe: dict[str, Any] = {}
    else:
        duration, probe, probe_error = ffprobe_duration(output)
        if probe_error:
            blockers.append(f"ffprobe failed: {probe_error}")
        if duration <= 0:
            blockers.append("Final render duration is zero or unreadable.")
    upstream, upstream_blockers = upstream_evidence(package_dir, args.skip_upstream_gates)
    blockers.extend(upstream_blockers)

    blueprint_path, raw_rows = load_transition_rows(package_dir, args.blueprint)
    if not blueprint_path:
        blockers.append("No transition blueprint with transition rows or markers could be found.")
    rows = selected_rows(raw_rows, duration, args.max_transition_samples) if duration > 0 else []
    if not rows and raw_rows:
        blockers.append("Transition rows exist but none have render-time boundary seconds inside the final video duration.")
    if not raw_rows:
        blockers.append("Transition blueprint has no transition rows or transition markers.")

    audited_rows: list[dict[str, Any]] = []
    if output and output.exists() and duration > 0:
        for row in rows:
            audited_rows.append(audit_row(output, row, output_dir, duration, args))
    blocked_rows = [row for row in audited_rows if row.get("status") == "blocked"]
    for row in blocked_rows[: args.max_blocked_rows_in_report]:
        blockers.append(f"transition row {row.get('rowIndex')} at {row.get('boundarySeconds')}s: {', '.join(row.get('issues') or [])}")
    row_warnings = [f"transition row {row.get('rowIndex')}: {item}" for row in audited_rows for item in (row.get("warnings") or [])]
    warnings.extend(row_warnings[: args.max_blocked_rows_in_report])
    frame_paths = [frame for row in audited_rows for frame in (row.get("framePaths") or [])]
    contact_sheet = maybe_contact_sheet(frame_paths, output_dir / "rendered_transition_proof_contact_sheet.jpg")

    summary = {
        "rawTransitionRowCount": len(raw_rows),
        "auditedTransitionRowCount": len(audited_rows),
        "blockedTransitionRowCount": len(blocked_rows),
        "rowsWithBlankOrBlackFrame": sum(
            1 for row in audited_rows if "black_or_blank_frame_in_transition_window" in (row.get("issues") or [])
        ),
        "rowsWithWhiteFlash": sum(1 for row in audited_rows if "white_flash_frame_in_transition_window" in (row.get("issues") or [])),
        "rowsWithPillarbox": sum(
            1 for row in audited_rows if "pillarbox_or_raw_vertical_frame_in_transition_window" in (row.get("issues") or [])
        ),
        "rowsWithStrobeLikeLumaJump": sum(
            1 for row in audited_rows if "strobe_like_luma_jump_in_transition_window" in (row.get("issues") or [])
        ),
        "maxObservedLumaJump": max([as_float(row.get("maxLumaJump")) for row in audited_rows] or [0.0]),
        "contactSheet": contact_sheet,
        "blockerCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "output": str(output) if output else None,
        "durationSeconds": duration,
        "probe": {"format": probe.get("format"), "streamCount": len(probe.get("streams") or [])},
        "inputs": {
            "blueprint": str(blueprint_path) if blueprint_path else None,
            "preSeconds": args.pre_seconds,
            "postSeconds": args.post_seconds,
            "landingHoldSeconds": args.landing_hold_seconds,
            "maxTransitionSamples": args.max_transition_samples,
        },
        "upstreamReports": upstream,
        "summary": summary,
        "auditedRows": audited_rows,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Rendered Transition Proof Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Output: `{report.get('output')}`",
        f"Blueprint: `{(report.get('inputs') or {}).get('blueprint')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
    ]
    if (report.get("summary") or {}).get("contactSheet"):
        lines.extend(["", f"Contact sheet: `{report['summary']['contactSheet']}`"])
    lines.extend(["", "## Blockers"])
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in report.get("warnings") or ["None"])
    lines.extend(["", "## Audited Rows"])
    for row in report.get("auditedRows", [])[:120]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')} - `{row.get('status')}`",
                f"- Boundary: `{row.get('boundarySeconds')}` seconds; category: `{row.get('boundaryCategory')}`",
                f"- Type/effect: `{row.get('approvedTransitionType')}` / `{row.get('resolveEffectName')}`",
                f"- Luma: maxJump=`{row.get('maxLumaJump')}` landingJump=`{row.get('landingLumaJump')}`",
                f"- Issues: `{', '.join(row.get('issues') or []) or 'None'}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit rendered final-MP4 transition windows.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output", help="Final MP4 path. Defaults to package reports/render directory.")
    parser.add_argument("--blueprint", help="Blueprint containing transition rows. Defaults to active/final transition blueprints.")
    parser.add_argument("--pre-seconds", type=float, default=0.24)
    parser.add_argument("--post-seconds", type=float, default=0.24)
    parser.add_argument("--landing-hold-seconds", type=float, default=0.9)
    parser.add_argument("--max-transition-samples", type=int, default=80)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=16)
    parser.add_argument("--blank-luma-mean", type=float, default=5.0)
    parser.add_argument("--blank-luma-near-black-mean", type=float, default=12.0)
    parser.add_argument("--blank-luma-std", type=float, default=1.2)
    parser.add_argument("--white-luma-mean", type=float, default=248.0)
    parser.add_argument("--white-luma-std", type=float, default=2.5)
    parser.add_argument("--max-flash-luma-delta", type=float, default=190.0)
    parser.add_argument("--max-landing-luma-delta", type=float, default=140.0)
    parser.add_argument("--pillarbox-dark-threshold", type=int, default=12)
    parser.add_argument("--pillarbox-min-side-dark-ratio", type=float, default=0.72)
    parser.add_argument("--pillarbox-max-side-mean", type=float, default=24.0)
    parser.add_argument("--pillarbox-max-side-std", type=float, default=28.0)
    parser.add_argument("--pillarbox-min-center-mean", type=float, default=35.0)
    parser.add_argument("--pillarbox-min-score", type=float, default=0.12)
    parser.add_argument("--skip-upstream-gates", action="store_true", help="Only for isolated script smoke tests.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(args)
    write_json(package_dir / "rendered_transition_proof_contract_audit.json", report)
    write_markdown(package_dir / "rendered_transition_proof_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
