#!/usr/bin/env python3
"""Materialize restrained effect-motion rows into a non-destructive Resolve blueprint candidate."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint": "",
    "approvedEffectRows": "",
    "resolveImplementation": "",
    "preflightEvidence": "",
    "timelineReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

FORBIDDEN_TERMS = (
    "glitch",
    "shake",
    "random spin",
    "spin template",
    "unmotivated spin",
    "flash",
    "particle",
    "strobe",
    "template pack",
    "logo reveal",
    "neon wipe",
)


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any, default: float | None = None) -> float | None:
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


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def is_video_clip(clip: dict[str, Any]) -> bool:
    track_type = str(clip.get("trackType") or "video").lower()
    return track_type in {"", "video"} and int(as_float(clip.get("mediaType"), 1) or 1) == 1


def blueprint_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def effect_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("effectRows") if isinstance(plan.get("effectRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def choose_base_blueprint(package_dir: Path) -> tuple[dict[str, Any] | None, Path, str]:
    candidates = [
        (
            package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json",
            "candidateBlueprint",
            "transition_execution_candidate",
        ),
        (
            package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json",
            "candidateBlueprint",
            "bridge_sequence_candidate",
        ),
    ]
    for report_path, output_key, kind in candidates:
        report = load_json(report_path) or {}
        outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
        candidate_path = Path(str(outputs.get(output_key) or ""))
        if "ready" in str(report.get("status") or "") and candidate_path.exists():
            return load_json(candidate_path), candidate_path, kind
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint"


def safety_policy() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "mutatesActiveBlueprintByDefault": False,
    }


def forbidden_hits(row: dict[str, Any]) -> list[str]:
    recommended = row.get("recommendedMotion") if isinstance(row.get("recommendedMotion"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    selected = {
        "rowType": row.get("rowType"),
        "recommendedStyle": recommended.get("style"),
        "selectedEffectType": decision.get("selectedEffectType"),
        "resolveImplementation": decision.get("resolveImplementation"),
    }
    text = json.dumps(selected, ensure_ascii=False).lower()
    hits = [term for term in FORBIDDEN_TERMS if term in text]
    if "spin" in text and not any(term in text for term in ("whip", "rotation match", "motivated", "route motion")):
        hits.append("unmotivated spin")
    return sorted(set(hits))


def recommended(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("recommendedMotion") if isinstance(row.get("recommendedMotion"), dict) else {}
    return value


def effect_style(row: dict[str, Any]) -> str:
    rec = recommended(row)
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    return str(decision.get("selectedEffectType") or rec.get("style") or "")


def effect_duration_frames(row: dict[str, Any]) -> int:
    rec = recommended(row)
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    return as_int(decision.get("durationFrames") or rec.get("durationFrames"), 12)


def effect_window(row: dict[str, Any], transitions: list[dict[str, Any]], fps: float) -> tuple[float, float]:
    start = as_float(row.get("timelineStartSeconds"))
    end = as_float(row.get("timelineEndSeconds"))
    if start is not None and end is not None and end > start:
        return round3(start), round3(end)
    boundary_index = as_int(row.get("boundaryIndex"), -1)
    matching = [
        item for item in transitions
        if isinstance(item, dict) and as_int(item.get("rowIndex"), -2) == boundary_index
    ]
    if not matching and transitions:
        matching = [transitions[min(max(boundary_index - 1, 0), len(transitions) - 1)]] if boundary_index > 0 else []
    if matching:
        transition = matching[0]
        boundary = float(as_float(transition.get("boundarySeconds"), 0.0) or 0.0)
        duration = max(0.2, float(as_float(transition.get("durationSeconds"), 0.0) or 0.0))
        return round3(max(0.0, boundary - duration / 2.0)), round3(boundary + duration / 2.0)
    duration = max(0.2, effect_duration_frames(row) / max(fps, 1.0))
    return 0.0, round3(duration)


def clip_overlaps(clip: dict[str, Any], start: float, end: float) -> bool:
    return is_video_clip(clip) and timeline_start(clip) < end and timeline_end(clip) > start


def select_clip_indices(clips: list[dict[str, Any]], start: float, end: float, row: dict[str, Any]) -> list[int]:
    overlaps = [index for index, clip in enumerate(clips) if clip_overlaps(clip, start, end)]
    if overlaps:
        return overlaps
    row_type = str(row.get("rowType") or "")
    keywords = []
    if "opening" in row_type:
        keywords = ["opening", "title", "hero"]
    elif "ending" in row_type:
        keywords = ["ending", "title", "aftertaste"]
    elif "chapter" in row_type:
        keywords = ["chapter", "title"]
    elif "transition" in row_type:
        keywords = ["bridge", "transition", "route"]
    scored: list[tuple[int, int]] = []
    for index, clip in enumerate(clips):
        text = json.dumps(clip, ensure_ascii=False).lower()
        score = sum(1 for keyword in keywords if keyword in text)
        if score:
            scored.append((score, index))
    if scored:
        scored.sort(reverse=True)
        return [scored[0][1]]
    return []


def keyframes_for(row: dict[str, Any], *, fps: float) -> list[dict[str, Any]]:
    style = effect_style(row).lower()
    duration = effect_duration_frames(row)
    if "opacity" in style or "fade" in style or "title" in str(row.get("rowType") or ""):
        return [
            {"frame": 0, "opacity": 0.0, "scale": 1.015},
            {"frame": max(1, duration // 2), "opacity": 1.0, "scale": 1.0},
            {"frame": duration, "opacity": 1.0, "scale": 1.0},
        ]
    if "rotation" in style:
        return [
            {"frame": 0, "rotationDegrees": 0, "scale": 1.0},
            {"frame": max(1, duration // 2), "rotationDegrees": "3_to_8_degrees_matching_motion", "scale": 1.03},
            {"frame": duration, "rotationDegrees": 0, "scale": 1.0},
        ]
    if "whip" in style:
        return [
            {"frame": 0, "positionX": 0, "motionBlur": 0.0},
            {"frame": max(1, duration // 2), "positionX": "directional_push", "motionBlur": 0.35},
            {"frame": duration, "positionX": 0, "motionBlur": 0.0},
        ]
    if "speed" in style or "ramp" in style:
        return [
            {"segment": "pre", "speedPercent": 100},
            {"segment": "middle", "speedPercent": "180_to_240_if_motion_supports"},
            {"segment": "post", "speedPercent": 100},
        ]
    return [
        {"frame": 0, "opacity": 1.0},
        {"frame": max(1, duration), "opacity": 1.0},
    ]


def title_zone_safe(row: dict[str, Any]) -> bool:
    row_type = str(row.get("rowType") or "")
    if "title_reveal" not in row_type:
        return True
    source = row.get("sourceEvidence") if isinstance(row.get("sourceEvidence"), dict) else {}
    title = source.get("titleTypography") if isinstance(source.get("titleTypography"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    return (
        title.get("cleanTitlePass") is True
        and title.get("subtitlePolicyPass") is True
        and decision.get("audioTreatment", "bgm_only_no_camera_voice") == "bgm_only_no_camera_voice"
    )


def source_safe(row: dict[str, Any]) -> bool:
    return row.get("status") == "has_source_evidence"


def motion_safe(row: dict[str, Any]) -> bool:
    row_type = str(row.get("rowType") or "")
    rec = recommended(row)
    style = effect_style(row).lower()
    if any(term in style for term in ("whip", "rotation", "speed", "ramp")):
        return rec.get("routeMotionEvidence") is True or "title_reveal" in row_type
    return True


def build_candidate(package_dir: Path, *, fps: float, update_blueprint: bool) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    plan_path = package_dir / "effect_motion_plan" / "effect_motion_plan.json"
    output_dir = package_dir / "effect_motion_blueprint"
    candidate_path = output_dir / "resolve_timeline_blueprint_effect_motion.json"
    report_path = output_dir / "effect_motion_blueprint_report.json"
    markdown_path = output_dir / "effect_motion_blueprint_report.md"
    base_blueprint, base_path, base_kind = choose_base_blueprint(package_dir)
    plan = load_json(plan_path)

    if not isinstance(base_blueprint, dict) or not isinstance(plan, dict):
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "needs_effect_motion_blueprint_inputs",
            "packageDir": str(package_dir),
            "inputs": {
                "baseBlueprint": str(base_path),
                "baseBlueprintExists": base_path.exists(),
                "effectMotionPlan": str(plan_path),
                "effectMotionPlanExists": plan_path.exists(),
            },
            "outputs": {
                "candidateBlueprint": str(candidate_path),
                "reportJson": str(report_path),
                "reportMarkdown": str(markdown_path),
            },
            "summary": {},
            "materializedRows": [],
            "safety": safety_policy(),
            "nextActions": ["Run prepare_effect_motion_plan.py after title, visual establishing, and transition bridge planning, then rerun this script."],
        }
        write_json(report_path, report)
        write_markdown(markdown_path, report)
        return report

    candidate = copy.deepcopy(base_blueprint)
    clips = blueprint_clips(candidate)
    transitions = candidate.get("transitions") if isinstance(candidate.get("transitions"), list) else []
    rows = effect_rows(plan)
    candidates: list[dict[str, Any]] = []
    materialized_rows: list[dict[str, Any]] = []
    rows_with_decisions = 0
    rows_with_clip_match = 0
    title_rows = 0
    transition_rows = 0
    blocked_rows = 0
    motion_rows = 0
    motion_rows_with_evidence = 0
    forbidden_total = 0

    for row in rows:
        start, end = effect_window(row, transitions, fps)
        clip_indices = select_clip_indices(clips, start, end, row)
        row_type = str(row.get("rowType") or "")
        if "title_reveal" in row_type:
            title_rows += 1
        if row_type == "transition_motion_bridge":
            transition_rows += 1
        style = effect_style(row)
        if any(term in style.lower() for term in ("whip", "rotation", "speed", "ramp")):
            motion_rows += 1
            if motion_safe(row):
                motion_rows_with_evidence += 1
        decision = dict(DECISION_FIELDS)
        effect = {
            "role": "effect_motion_candidate",
            "rowIndex": row.get("rowIndex"),
            "rowType": row_type,
            "status": row.get("status"),
            "timelineStartSeconds": start,
            "timelineEndSeconds": end,
            "targetTitle": row.get("targetTitle"),
            "effectStyle": style,
            "durationFrames": effect_duration_frames(row),
            "intensity": recommended(row).get("intensity") or (row.get("decision") or {}).get("intensity") or "subtle",
            "audioTreatment": (row.get("decision") or {}).get("audioTreatment") or "bgm_only_no_camera_voice",
            "titleZoneSafe": title_zone_safe(row),
            "sourceEvidenceSatisfied": source_safe(row),
            "motionEvidenceSatisfied": motion_safe(row),
            "forbiddenEffectHits": forbidden_hits(row),
            "keyframePlan": keyframes_for(row, fps=fps),
            "matchedClipIndices": clip_indices,
            "decision": decision,
        }
        candidates.append(effect)
        for index in clip_indices:
            clips[index].setdefault("effectMotionCandidates", []).append(effect)
        if set(DECISION_FIELDS).issubset(set(decision)):
            rows_with_decisions += 1
        if clip_indices:
            rows_with_clip_match += 1
        forbidden_total += len(effect["forbiddenEffectHits"])
        blocked = (
            not source_safe(row)
            or not clip_indices
            or not title_zone_safe(row)
            or not motion_safe(row)
            or bool(effect["forbiddenEffectHits"])
            or str(effect.get("intensity") or "").lower() not in {"subtle", "low", "restrained"}
        )
        if blocked:
            blocked_rows += 1
        materialized_rows.append(
            {
                "rowIndex": row.get("rowIndex"),
                "rowType": row_type,
                "status": "materialized" if not blocked else "needs_effect_motion_blueprint_repair",
                "timelineStartSeconds": start,
                "timelineEndSeconds": end,
                "effectStyle": style,
                "durationFrames": effect["durationFrames"],
                "matchedClipCount": len(clip_indices),
                "sourceEvidenceSatisfied": effect["sourceEvidenceSatisfied"],
                "titleZoneSafe": effect["titleZoneSafe"],
                "motionEvidenceSatisfied": effect["motionEvidenceSatisfied"],
                "forbiddenEffectHits": effect["forbiddenEffectHits"],
                "decision": dict(DECISION_FIELDS),
            }
        )

    candidate["clips"] = clips
    candidate["effectMotionCandidates"] = candidates
    candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    candidate["effectMotionBlueprintPlan"] = {
        "status": "candidate_not_applied_to_resolve",
        "createdAt": candidate["updatedAt"],
        "baseBlueprint": str(base_path),
        "baseBlueprintKind": base_kind,
        "sourceEffectMotionPlan": str(plan_path),
        "report": str(report_path),
        "candidateBlueprint": str(candidate_path),
        "fps": fps,
        "defaultBehavior": "writes a separate candidate blueprint and leaves the active blueprint untouched",
    }
    candidate.setdefault("timelineMarkers", [])
    if isinstance(candidate["timelineMarkers"], list):
        for effect in candidates:
            candidate["timelineMarkers"].append(
                {
                    "startSeconds": effect["timelineStartSeconds"],
                    "durationSeconds": max(0.25, effect["timelineEndSeconds"] - effect["timelineStartSeconds"]),
                    "color": "Orange",
                    "name": f"Effect Motion {effect.get('rowIndex')}",
                    "note": f"{effect.get('rowType')}: {effect.get('effectStyle')}",
                    "role": "effect_motion_candidate_marker",
                    "payload": {"rowIndex": effect.get("rowIndex"), "rowType": effect.get("rowType"), "durationFrames": effect.get("durationFrames")},
                }
            )
        candidate["timelineMarkers"] = sorted(candidate["timelineMarkers"], key=lambda item: (float(item.get("startSeconds") or 0.0), str(item.get("role") or "")))

    status = "ready_with_effect_motion_blueprint" if rows and not blocked_rows else "needs_effect_motion_blueprint_repair"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "baseBlueprint": str(base_path),
            "baseBlueprintKind": base_kind,
            "effectMotionPlan": str(plan_path),
            "effectMotionPlanStatus": plan.get("status"),
        },
        "outputs": {
            "candidateBlueprint": str(candidate_path),
            "reportJson": str(report_path),
            "reportMarkdown": str(markdown_path),
            "activeBlueprintUpdated": bool(update_blueprint),
        },
        "summary": {
            "effectRowCount": len(rows),
            "materializedEffectCount": len(candidates),
            "rowsWithDecisionFields": rows_with_decisions,
            "rowsWithClipMatch": rows_with_clip_match,
            "blockedRowCount": blocked_rows,
            "titleMotionRowCount": title_rows,
            "transitionMotionRowCount": transition_rows,
            "motionEffectRowCount": motion_rows,
            "motionEffectRowsWithEvidence": motion_rows_with_evidence,
            "forbiddenEffectHitCount": forbidden_total,
            "candidateClipCount": len(clips),
            "candidateEffectMotionCount": len(candidates),
        },
        "materializedRows": materialized_rows,
        "selectionRubric": {
            "pass": [
                "Every effect motion row becomes a candidate effect-motion object in the blueprint.",
                "Matched clips carry effectMotionCandidates metadata with restrained keyframes.",
                "Title reveal rows are title-zone safe and BGM-only.",
                "Whip, rotation, and speed-ramp rows require route-motion evidence.",
            ],
            "reject": [
                "Effect rows remain prose-only.",
                "Glitch, random spin, flash, shake, particle, logo reveal, or template-pack effects are selected.",
                "Motion effects hide missing route bridge footage, weak titles, missing BGM, or wrong route evidence.",
                "The script writes Resolve, queues render, downloads assets, or mutates source footage.",
            ],
        },
        "safety": safety_policy(),
        "nextActions": [
            f"Run audit_resolve_blueprint.py --blueprint {candidate_path} --package-dir {package_dir} before using this candidate.",
            "Review effect_motion_blueprint_report.json and fill decision.approveCandidateBlueprint before Resolve apply.",
            "If approved, use a package fork or explicit --update-blueprint path so stale final QA is not reused.",
        ],
    }

    write_json(candidate_path, candidate)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    if update_blueprint:
        active_path = package_dir / "resolve_timeline_blueprint.json"
        active_blueprint = load_json(active_path) or {}
        backup = package_dir / f"resolve_timeline_blueprint.before_effect_motion_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        write_json(backup, active_blueprint)
        write_json(active_path, candidate)
        report["outputs"]["activeBlueprintBackup"] = str(backup)
        write_json(report_path, report)
        write_markdown(markdown_path, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Effect Motion Blueprint Report",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Materialized Rows",
    ]
    for row in report.get("materializedRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('rowType')}",
                f"- Status: `{row.get('status')}`",
                f"- Timeline: {row.get('timelineStartSeconds')}s-{row.get('timelineEndSeconds')}s",
                f"- Effect style: `{row.get('effectStyle')}`",
                f"- Duration: {row.get('durationFrames')} frames",
                f"- Matched clips: {row.get('matchedClipCount')}",
                f"- Source/title/motion safe: {row.get('sourceEvidenceSatisfied')} / {row.get('titleZoneSafe')} / {row.get('motionEvidenceSatisfied')}",
            ]
        )
        if row.get("forbiddenEffectHits"):
            lines.append(f"- Forbidden hits: `{', '.join(row.get('forbiddenEffectHits') or [])}`")
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an effect-motion Resolve blueprint candidate.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--fps", type=float, default=30.0, help="Timeline frame rate used to convert duration frames. Default: 30.")
    parser.add_argument("--update-blueprint", action="store_true", help="Replace the active blueprint after writing a backup. Default is non-destructive.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_candidate(Path(args.package_dir), fps=max(args.fps, 1.0), update_blueprint=args.update_blueprint)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report.get("status"), **(report.get("summary") or {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
