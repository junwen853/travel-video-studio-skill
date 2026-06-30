#!/usr/bin/env python3
"""Audit whether the final candidate is watchable at reference-calibrated pacing."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_SPECS = {
    "editRhythmPlan": ("edit_rhythm_plan/edit_rhythm_plan.json", {"ready_with_edit_rhythm_plan"}),
    "rhythmRecutApplication": ("rhythm_recut_application_contract_audit.json", {"passed"}),
    "timelineVariety": ("timeline_variety_contract_audit.json", {"passed"}),
    "referenceSceneGrammar": ("reference_scene_grammar_contract_audit.json", {"passed"}),
    "finalCutSmoothness": ("final_cut_smoothness_contract_audit.json", {"passed"}),
    "finalBlueprintLineage": ("final_blueprint_lineage_contract_audit.json", {"passed"}),
}
TITLE_TERMS = ("title", "opening_city", "chapter_title", "ending_city", "hero title", "subtitle_overlay")
BREATH_TERMS = ("scenic", "breathing", "aerial", "skyline", "payoff", "aftertaste", "ending", "sunset", "quiet", "view")
WEAK_TERMS = ("black", "placeholder", "slate", "generic", "test", "sample", "duplicate")


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


def as_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def summary_of(data: Any) -> dict[str, Any]:
    return data.get("summary") if isinstance(data, dict) and isinstance(data.get("summary"), dict) else {}


def inputs_of(data: Any) -> dict[str, Any]:
    return data.get("inputs") if isinstance(data, dict) and isinstance(data.get("inputs"), dict) else {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"), None)
    if explicit is not None and explicit > start:
        return float(explicit)
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + float(duration)


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in (
            "role",
            "purpose",
            "place",
            "city",
            "chapter",
            "titleText",
            "subtitle",
            "sourcePath",
            "sourceName",
            "name",
            "notes",
            "creatorFunction",
            "editorialTier",
            "rhythmRole",
        )
    ).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt", ".txt")):
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type not in {"", "video"}:
        return False
    return as_int(clip.get("mediaType"), 1) == 1


def choose_blueprint(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path, str, bool]:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
        return load_json(path), path, "explicit_blueprint", is_inside(path, package_dir)
    candidates = [
        (package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json", "candidateBlueprint", "transition_polish_candidate"),
        (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json", "candidateBlueprint", "rhythm_recut_candidate"),
        (package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json", "candidateBlueprint", "bgm_phrase_candidate"),
        (package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json", "candidateBlueprint", "effect_motion_candidate"),
        (package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json", "candidateBlueprint", "transition_execution_candidate"),
        (package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json", "candidateBlueprint", "bridge_sequence_candidate"),
    ]
    for report_path, output_key, kind in candidates:
        report = load_json(report_path) or {}
        outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
        raw = outputs.get(output_key)
        if not raw or not str(report.get("status") or "").startswith("ready"):
            continue
        path = Path(str(raw)).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
        data = load_json(path)
        if isinstance(data, dict):
            return data, path, kind, is_inside(path, package_dir)
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint", is_inside(active, package_dir)


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return sorted([row for row in rows if isinstance(row, dict) and is_video_clip(row)], key=lambda item: (timeline_start(item), timeline_end(item)))


def max_run(flags: list[bool]) -> int:
    best = current = 0
    for flag in flags:
        if flag:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def normalize_chapter(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return "unassigned"
    text = str(value).strip()
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return text


def target_profile(edit_rhythm: dict[str, Any]) -> dict[str, Any]:
    target = edit_rhythm.get("targetRhythmProfile") if isinstance(edit_rhythm.get("targetRhythmProfile"), dict) else {}
    reference = edit_rhythm.get("referenceProfile") if isinstance(edit_rhythm.get("referenceProfile"), dict) else {}
    ref_avg = as_float(reference.get("averageShotLengthSeconds"), 6.0) or 6.0
    ref_median = as_float(reference.get("medianShotLengthSeconds"), 3.0) or 3.0
    ref_p90 = as_float(reference.get("p90ShotLengthSeconds"), 12.0) or 12.0
    avg_range = target.get("targetAverageRangeSeconds") if isinstance(target.get("targetAverageRangeSeconds"), list) else None
    median_range = target.get("targetMedianRangeSeconds") if isinstance(target.get("targetMedianRangeSeconds"), list) else None
    return {
        "referenceAverageShotLengthSeconds": round3(as_float(target.get("referenceAverageShotLengthSeconds"), ref_avg) or ref_avg),
        "referenceMedianShotLengthSeconds": round3(as_float(target.get("referenceMedianShotLengthSeconds"), ref_median) or ref_median),
        "referenceP90ShotLengthSeconds": round3(as_float(target.get("referenceP90ShotLengthSeconds"), ref_p90) or ref_p90),
        "targetAverageRangeSeconds": [
            round3(as_float((avg_range or [max(4.0, ref_avg * 0.85), min(12.0, max(7.5, ref_avg * 1.8))])[0], 4.0) or 4.0),
            round3(as_float((avg_range or [4.0, min(12.0, max(7.5, ref_avg * 1.8))])[1], 12.0) or 12.0),
        ],
        "targetMedianRangeSeconds": [
            round3(as_float((median_range or [max(2.0, ref_median * 0.75), min(8.0, max(4.5, ref_median * 2.0))])[0], 2.0) or 2.0),
            round3(as_float((median_range or [2.0, min(8.0, max(4.5, ref_median * 2.0))])[1], 8.0) or 8.0),
        ],
        "longShotSoftLimitSeconds": round3(as_float(target.get("longShotSoftLimitSeconds"), min(18.0, max(10.0, ref_p90))) or 12.0),
        "breathingShotLimitSeconds": round3(as_float(target.get("breathingShotLimitSeconds"), 24.0) or 24.0),
        "minimumRegisterSeconds": 1.2,
    }


def annotate_clip(index: int, clip: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    start = timeline_start(clip)
    end = timeline_end(clip)
    duration = max(0.0, end - start)
    text = clip_text(clip)
    is_title = any(term in text for term in TITLE_TERMS)
    is_breath = any(term in text for term in BREATH_TERMS)
    is_weak = any(term in text for term in WEAK_TERMS)
    long_limit = float(target["longShotSoftLimitSeconds"])
    breath_limit = float(target["breathingShotLimitSeconds"])
    min_register = float(target["minimumRegisterSeconds"])
    issues: list[str] = []
    if duration > breath_limit:
        issues.append("very_long_shot_over_breathing_limit")
    if duration > long_limit and not is_breath and not is_title:
        issues.append("long_flat_shot_without_breathing_role")
    if duration < min_register and not is_title:
        issues.append("too_short_to_register")
    if is_title and duration > 8.0:
        issues.append("title_or_card_hold_too_long")
    if is_weak:
        issues.append("weak_or_placeholder_clip_in_pacing_sample")
    return {
        "clipIndex": index,
        "chapterIndex": normalize_chapter(clip.get("chapterIndex")),
        "sourcePath": clip.get("sourcePath"),
        "sourceName": Path(str(clip.get("sourcePath") or clip.get("sourceName") or "")).name,
        "timelineStartSeconds": round3(start),
        "timelineEndSeconds": round3(end),
        "durationSeconds": round3(duration),
        "role": clip.get("role"),
        "purpose": clip.get("purpose"),
        "creatorFunction": clip.get("creatorFunction"),
        "rhythmRole": clip.get("rhythmRole"),
        "isBreathingShot": is_breath,
        "isTitleShot": is_title,
        "issues": issues,
        "status": "passed" if not issues else "blocked",
    }


def chapter_rows(rows: list[dict[str, Any]], target: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("chapterIndex") or "unassigned"), []).append(row)
    out: list[dict[str, Any]] = []
    avg_hi = float(target["targetAverageRangeSeconds"][1])
    for chapter, chapter_clips in sorted(grouped.items(), key=lambda item: (9999 if item[0] == "unassigned" else int(float(item[0])) if item[0].replace(".", "", 1).isdigit() else 9998, item[0])):
        durations = [float(row.get("durationSeconds") or 0.0) for row in chapter_clips if float(row.get("durationSeconds") or 0.0) > 0]
        issues: list[str] = []
        breath_count = sum(1 for row in chapter_clips if row.get("isBreathingShot"))
        long_flat_count = sum(1 for row in chapter_clips if "long_flat_shot_without_breathing_role" in (row.get("issues") or []))
        short_run = max_run(["too_short_to_register" in (row.get("issues") or []) for row in chapter_clips])
        avg = sum(durations) / len(durations) if durations else 0.0
        if len(chapter_clips) >= 4 and breath_count == 0:
            issues.append("chapter_has_no_breathing_or_payoff_shot")
        if avg > avg_hi * 1.25:
            issues.append("chapter_average_shot_length_too_slow")
        if long_flat_count > max(0, len(chapter_clips) // 5):
            issues.append("chapter_has_too_many_long_flat_shots")
        if short_run > 2:
            issues.append("chapter_has_short_flicker_run")
        out.append(
            {
                "chapterIndex": chapter,
                "shotCount": len(chapter_clips),
                "durationSeconds": round3(sum(durations)),
                "averageShotSeconds": round3(avg),
                "medianShotSeconds": round3(statistics.median(durations)) if durations else 0.0,
                "breathingShotCount": breath_count,
                "longFlatShotCount": long_flat_count,
                "shortFlickerRunMax": short_run,
                "issues": issues,
                "status": "passed" if not issues else "blocked",
            }
        )
    return out


def load_reports(package_dir: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for name, (rel_path, accepted) in REPORT_SPECS.items():
        path = package_dir / rel_path
        data = load_json(path) or {}
        reports[name] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(accepted),
            "accepted": data.get("status") in accepted,
            "summary": summary_of(data),
            "inputs": inputs_of(data),
            "blockers": data.get("blockers") or [],
            "warnings": data.get("warnings") or [],
            "data": data,
        }
    return reports


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reports = load_reports(package_dir)
    edit_rhythm = reports["editRhythmPlan"]["data"]
    target = target_profile(edit_rhythm)
    blueprint, blueprint_path, blueprint_kind, blueprint_inside = choose_blueprint(package_dir, args.blueprint)
    clips = primary_visual_clips(blueprint or {})
    rows = [annotate_clip(index, clip, target) for index, clip in enumerate(clips, start=1)]
    chapters = chapter_rows(rows, target)
    durations = [float(row.get("durationSeconds") or 0.0) for row in rows if float(row.get("durationSeconds") or 0.0) > 0]
    avg = sum(durations) / len(durations) if durations else 0.0
    median = statistics.median(durations) if durations else 0.0
    short_flags = ["too_short_to_register" in (row.get("issues") or []) for row in rows]
    long_flat_flags = ["long_flat_shot_without_breathing_role" in (row.get("issues") or []) for row in rows]
    very_long = [row for row in rows if "very_long_shot_over_breathing_limit" in (row.get("issues") or [])]
    weak = [row for row in rows if "weak_or_placeholder_clip_in_pacing_sample" in (row.get("issues") or [])]
    blocked_chapters = [row for row in chapters if row.get("status") == "blocked"]
    target_avg_lo, target_avg_hi = [float(value) for value in target["targetAverageRangeSeconds"]]
    target_median_lo, target_median_hi = [float(value) for value in target["targetMedianRangeSeconds"]]
    short_count = sum(1 for flag in short_flags if flag)
    long_flat_count = sum(1 for flag in long_flat_flags if flag)
    breath_count = sum(1 for row in rows if row.get("isBreathingShot"))

    blockers: list[str] = []
    if not blueprint or not blueprint_path.exists():
        blockers.append("final candidate blueprint is missing")
    if not blueprint_inside:
        blockers.append("selected blueprint is outside the package")
    if not rows:
        blockers.append("final candidate has no primary visual clips")
    if not all(report["exists"] and report["accepted"] and not report["blockers"] for report in reports.values()):
        blockers.append("required upstream pacing/style reports are missing or blocked")
    if reports["editRhythmPlan"]["summary"].get("referenceReady") is not True:
        blockers.append("edit rhythm plan does not prove the reference pacing profile is ready")
    if not (target_avg_lo <= avg <= target_avg_hi):
        blockers.append("average visual shot length is outside the reference-calibrated range")
    if not (target_median_lo <= median <= target_median_hi):
        blockers.append("median visual shot length is outside the reference-calibrated range")
    if very_long:
        blockers.append("one or more visual shots exceed the breathing-shot duration limit")
    if long_flat_count > max(args.max_long_flat_shots, int(len(rows) * args.max_long_flat_ratio)):
        blockers.append("too many long flat shots remain after rhythm recut")
    if max_run(long_flat_flags) > args.max_long_flat_run:
        blockers.append("long flat shots stack without a breathing or cutaway break")
    if short_count / max(1, len(rows)) > args.max_short_clip_ratio:
        blockers.append("too many sub-register short clips create flicker pacing")
    if max_run(short_flags) > args.max_short_clip_run:
        blockers.append("short clips run together as unreadable flicker")
    if len(rows) >= args.min_visuals_for_breathing and breath_count < max(1, len(chapters)):
        blockers.append("not enough breathing/payoff/aftertaste shots for the number of chapters")
    if weak:
        blockers.append("weak or placeholder clips remain in the pacing sample")
    blockers.extend(f"chapter {row.get('chapterIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_chapters[: args.max_blocked_rows_in_report])

    summary = {
        "visualClipCount": len(rows),
        "chapterCount": len(chapters),
        "blockedChapterCount": len(blocked_chapters),
        "averageVisualShotSeconds": round3(avg),
        "medianVisualShotSeconds": round3(median),
        "targetAverageRangeSeconds": target["targetAverageRangeSeconds"],
        "targetMedianRangeSeconds": target["targetMedianRangeSeconds"],
        "longShotSoftLimitSeconds": target["longShotSoftLimitSeconds"],
        "breathingShotLimitSeconds": target["breathingShotLimitSeconds"],
        "shortClipCount": short_count,
        "shortClipRatio": round3(short_count / max(1, len(rows))),
        "shortClipRunMax": max_run(short_flags),
        "longFlatShotCount": long_flat_count,
        "longFlatRunMax": max_run(long_flat_flags),
        "veryLongShotCount": len(very_long),
        "breathingShotCount": breath_count,
        "weakOrPlaceholderClipCount": len(weak),
        "editRhythmStatus": reports["editRhythmPlan"]["status"],
        "rhythmRecutApplicationStatus": reports["rhythmRecutApplication"]["status"],
        "timelineVarietyStatus": reports["timelineVariety"]["status"],
        "referenceSceneGrammarStatus": reports["referenceSceneGrammar"]["status"],
        "finalCutSmoothnessStatus": reports["finalCutSmoothness"]["status"],
        "finalBlueprintLineageStatus": reports["finalBlueprintLineage"]["status"],
        "blockedCheckCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintKind": blueprint_kind,
            "blueprintExists": blueprint_path.exists(),
            "blueprintInsidePackage": blueprint_inside,
            "reports": {name: report["path"] for name, report in reports.items()},
            "maxLongFlatRatio": args.max_long_flat_ratio,
            "maxShortClipRatio": args.max_short_clip_ratio,
        },
        "summary": summary,
        "targetPacingProfile": target,
        "reports": reports,
        "auditedRows": rows,
        "chapterRows": chapters,
        "blockers": blockers,
        "warnings": [warning for report in reports.values() for warning in report["warnings"]],
        "policy": {
            "referencePacingProfileRequired": True,
            "longFlatShotRunsRejected": True,
            "shortFlickerRunsRejected": True,
            "chapterBreathingRequired": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Pacing Watchability Contract Audit",
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
    lines.extend(["", "## Chapter Pacing"])
    for row in report.get("chapterRows", [])[:80]:
        lines.extend(
            [
                "",
                f"### Chapter {row.get('chapterIndex')} - `{row.get('status')}`",
                f"- Shots: `{row.get('shotCount')}`",
                f"- Average / median seconds: `{row.get('averageShotSeconds')}` / `{row.get('medianShotSeconds')}`",
                f"- Breathing shots: `{row.get('breathingShotCount')}`",
                f"- Long flat / short-run max: `{row.get('longFlatShotCount')}` / `{row.get('shortFlickerRunMax')}`",
            ]
        )
        if row.get("issues"):
            lines.append(f"- Issues: `{', '.join(row.get('issues') or [])}`")
    lines.extend(
        [
            "",
            "## Contract",
            "- Use the local reference pacing profile through `edit_rhythm_plan`.",
            "- Reject long raw holds that are not scenic breathing, payoff, or aftertaste.",
            "- Reject unreadable short-clip runs that create accidental flicker.",
            "- Require chapter-level breathing points so the film does not feel like a flat asset dump.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final-candidate pacing watchability against the reference rhythm profile.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--max-long-flat-ratio", type=float, default=0.08)
    parser.add_argument("--max-long-flat-shots", type=int, default=0)
    parser.add_argument("--max-long-flat-run", type=int, default=1)
    parser.add_argument("--max-short-clip-ratio", type=float, default=0.18)
    parser.add_argument("--max-short-clip-run", type=int, default=2)
    parser.add_argument("--min-visuals-for-breathing", type=int, default=6)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(Path(args.package_dir), args)
    package_dir = Path(args.package_dir).expanduser().resolve()
    write_json(package_dir / "pacing_watchability_contract_audit.json", report)
    write_markdown(package_dir / "pacing_watchability_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
