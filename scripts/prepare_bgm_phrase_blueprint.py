#!/usr/bin/env python3
"""Materialize BGM phrase and transition-cue rows into a non-destructive blueprint candidate."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "approveCandidateBlueprint": "",
    "approvedBgmPhraseRows": "",
    "selectedBgmBed": "",
    "resolveImplementation": "",
    "preflightEvidence": "",
    "timelineReadbackEvidence": "",
    "audioReadbackEvidence": "",
    "frameSampleEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}


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


def choose_base_blueprint(package_dir: Path) -> tuple[dict[str, Any] | None, Path, str]:
    candidates = [
        (
            package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json",
            "candidateBlueprint",
            "effect_motion_candidate",
        ),
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


def target_duration(package_dir: Path, blueprint: dict[str, Any], selection: dict[str, Any]) -> float:
    summary = selection.get("summary") if isinstance(selection.get("summary"), dict) else {}
    for value in (
        summary.get("targetDurationSeconds"),
        blueprint.get("targetDurationSeconds"),
        blueprint.get("actualVideoCoverageSeconds"),
    ):
        number = as_float(value)
        if number and number > 0:
            return number
    clips = blueprint_clips(blueprint)
    max_end = max((timeline_end(clip) for clip in clips if is_video_clip(clip)), default=0.0)
    if max_end > 0:
        return max_end
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    return float(as_float(render.get("durationSeconds"), 20 * 60.0) or 20 * 60.0)


def selected_bgm_beds(selection: dict[str, Any]) -> list[dict[str, Any]]:
    rows = selection.get("selectedMaterializedBeds") if isinstance(selection.get("selectedMaterializedBeds"), list) else []
    beds = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("localPath") or row.get("approvedLocalPath") or "")
        license_url = str(row.get("licenseUrl") or row.get("approvedLicenseUrl") or "")
        beds.append(
            {
                "name": row.get("name") or Path(path).stem,
                "localPath": path,
                "localPathExists": bool(row.get("localPathExists")) or (bool(path) and Path(path).expanduser().exists()),
                "licenseUrl": license_url,
                "licenseUrlPresent": bool(row.get("licenseUrlPresent")) or license_url.startswith(("http://", "https://")),
                "durationSeconds": row.get("durationSeconds"),
                "coversTargetDuration": row.get("coversTargetDuration"),
                "referencedByBlueprint": row.get("referencedByBlueprint"),
            }
        )
    return beds


def transition_boundary(transition: dict[str, Any]) -> float | None:
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds"):
        number = as_float(transition.get(key))
        if number is not None:
            return number
    from_clip = transition.get("fromClip") if isinstance(transition.get("fromClip"), dict) else {}
    to_clip = transition.get("toClip") if isinstance(transition.get("toClip"), dict) else {}
    left = timeline_end(from_clip)
    right = timeline_start(to_clip)
    if left or right:
        return (left + right) / 2.0
    return None


def infer_transitions(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    transitions: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        boundary = transition_boundary(row)
        if boundary is None:
            continue
        transitions.append(
            {
                "rowIndex": row.get("rowIndex", index),
                "boundarySeconds": round3(boundary),
                "boundaryCategory": row.get("boundaryCategory") or row.get("role") or "adjacent_pair",
                "source": "blueprint_transitions",
            }
        )
    if transitions:
        return transitions
    clips = sorted([clip for clip in blueprint_clips(blueprint) if is_video_clip(clip)], key=timeline_start)
    for index, (left, right) in enumerate(zip(clips, clips[1:]), start=1):
        left_end = timeline_end(left)
        right_start = timeline_start(right)
        if right_start < left_end:
            continue
        transitions.append(
            {
                "rowIndex": index,
                "boundarySeconds": round3((left_end + right_start) / 2.0),
                "boundaryCategory": "inferred_adjacent_pair",
                "source": "clip_adjacency",
            }
        )
    return transitions


def section_source(selection: dict[str, Any], name: str) -> dict[str, Any]:
    rows = selection.get("sectionPlan") if isinstance(selection.get("sectionPlan"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("section") or "") == name:
            return row
    return {}


def beat_cues(start: float, end: float, phrase_seconds: float = 16.0) -> list[float]:
    cues: list[float] = [round3(start)]
    cursor = start + phrase_seconds
    while cursor < end - 1.0:
        cues.append(round3(cursor))
        cursor += phrase_seconds
    if end > start:
        cues.append(round3(end))
    return cues


def add_phrase(
    rows: list[dict[str, Any]],
    *,
    section: str,
    role: str,
    start: float,
    end: float,
    mood: str,
    action: str,
    bed: dict[str, Any] | None,
    source_section: dict[str, Any],
    transition: dict[str, Any] | None = None,
) -> None:
    start = max(0.0, start)
    end = max(start, end)
    if end - start < 0.5:
        return
    index = len(rows) + 1
    row = {
        "role": "bgm_phrase_candidate",
        "phraseIndex": index,
        "section": section,
        "sectionRole": source_section.get("role") or role,
        "timelineStartSeconds": round3(start),
        "timelineEndSeconds": round3(end),
        "durationSeconds": round3(end - start),
        "moodBucket": mood,
        "bgmAction": action,
        "audioTreatment": "bgm_only_no_camera_voice",
        "selectedBgmBed": {
            "name": bed.get("name") if bed else "",
            "localPath": bed.get("localPath") if bed else "",
            "licenseUrl": bed.get("licenseUrl") if bed else "",
        },
        "beatCueSeconds": beat_cues(start, end),
        "cutPolicy": "Prefer cuts, title reveals, bridge inserts, and restrained motion keyframes on beatCueSeconds or within +/-0.35s.",
        "transitionCue": None,
        "decision": dict(DECISION_FIELDS),
    }
    if transition:
        row["transitionCue"] = {
            "transitionRowIndex": transition.get("rowIndex"),
            "boundarySeconds": transition.get("boundarySeconds"),
            "boundaryCategory": transition.get("boundaryCategory"),
            "cue": "cut_or_effect_on_bgm_phrase_boundary",
        }
    rows.append(row)


def build_phrase_rows(blueprint: dict[str, Any], selection: dict[str, Any], target_seconds: float, beds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    bed = beds[0] if beds else None
    opening_end = min(target_seconds, max(12.0, min(45.0, target_seconds * 0.18)))
    ending_start = max(opening_end, target_seconds - min(45.0, max(12.0, target_seconds * 0.14)))
    add_phrase(
        rows,
        section="opening_and_title",
        role="BGM-led scenic promise, clean hero title, no camera voice.",
        start=0.0,
        end=opening_end,
        mood="opening",
        action="start_bed_with_clean_title_lift",
        bed=bed,
        source_section=section_source(selection, "opening_and_title"),
    )
    transitions = [row for row in infer_transitions(blueprint) if 0 <= float(row["boundarySeconds"]) <= target_seconds]
    transition_windows: list[tuple[float, float]] = []
    for transition in transitions:
        boundary = float(transition["boundarySeconds"])
        start = max(opening_end, boundary - 6.0)
        end = min(ending_start, boundary + 6.0)
        if end - start >= 0.5:
            transition_windows.append((start, end))
            add_phrase(
                rows,
                section="day_place_transitions",
                role="BGM phrase cue for route bridge, match cut, dissolve, whip, or rotation only when footage supports it.",
                start=start,
                end=end,
                mood="transition",
                action="accent_boundary_without_source_voice",
                bed=bed,
                source_section=section_source(selection, "day_place_transitions"),
                transition=transition,
            )
    body_segments: list[tuple[float, float]] = []
    cursor = opening_end
    for start, end in sorted(transition_windows):
        start = max(opening_end, min(ending_start, start))
        end = max(opening_end, min(ending_start, end))
        if start - cursor >= 12.0:
            body_segments.append((cursor, start))
        cursor = max(cursor, end)
    if ending_start - cursor >= 12.0:
        body_segments.append((cursor, ending_start))
    if not body_segments and ending_start - opening_end >= 12.0:
        body_segments.append((opening_end, ending_start))
    for start, end in body_segments:
        cursor = start
        while end - cursor > 0.5:
            segment_end = min(end, cursor + 40.0)
            add_phrase(
                rows,
                section="chapter_body",
                role="Low-friction travel bed under lived-in place detail, captions, and route texture.",
                start=cursor,
                end=segment_end,
                mood="city_texture",
                action="hold_bed_under_caption_story",
                bed=bed,
                source_section=section_source(selection, "continuous_bed"),
            )
            cursor = segment_end
    add_phrase(
        rows,
        section="ending_aftertaste",
        role="Reflective scenic tail with breathing room and no spoken wrap-up.",
        start=ending_start,
        end=target_seconds,
        mood="ending",
        action="music_tail_fade_with_scenic_aftertaste",
        bed=bed,
        source_section=section_source(selection, "ending_aftertaste"),
    )
    ordered = sorted(rows, key=lambda row: (float(row["timelineStartSeconds"]), int(row["phraseIndex"])))
    for index, row in enumerate(ordered, start=1):
        row["phraseIndex"] = index
    return ordered


def clip_overlaps(clip: dict[str, Any], start: float, end: float) -> bool:
    return is_video_clip(clip) and timeline_start(clip) < end and timeline_end(clip) > start


def nearest_phrase(rows: list[dict[str, Any]], boundary: float) -> dict[str, Any] | None:
    if not rows:
        return None
    return min(
        rows,
        key=lambda row: min(
            abs(float(row.get("timelineStartSeconds") or 0.0) - boundary),
            abs(float(row.get("timelineEndSeconds") or 0.0) - boundary),
            abs(((float(row.get("timelineStartSeconds") or 0.0) + float(row.get("timelineEndSeconds") or 0.0)) / 2.0) - boundary),
        ),
    )


def annotate_candidate(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    clips = blueprint_clips(candidate)
    clip_annotations = 0
    for row in rows:
        start = float(row["timelineStartSeconds"])
        end = float(row["timelineEndSeconds"])
        for clip in clips:
            if clip_overlaps(clip, start, end):
                clip.setdefault("bgmPhraseCandidates", []).append(row)
                clip_annotations += 1
    candidate["clips"] = clips
    transitions = candidate.get("transitions") if isinstance(candidate.get("transitions"), list) else []
    transition_cues = 0
    if isinstance(transitions, list):
        for transition in transitions:
            if not isinstance(transition, dict):
                continue
            boundary = transition_boundary(transition)
            if boundary is None:
                continue
            phrase = nearest_phrase(rows, boundary)
            if not phrase:
                continue
            payload = {
                "role": "bgm_phrase_transition_cue",
                "phraseIndex": phrase.get("phraseIndex"),
                "boundarySeconds": round3(boundary),
                "cue": "cut_or_effect_on_bgm_phrase_boundary",
                "allowedTransitionEnergy": "restrained_route_motivated",
                "audioTreatment": "bgm_only_no_camera_voice",
            }
            transition["bgmPhraseCandidate"] = payload
            transition_cues += 1
        candidate["transitions"] = transitions
    candidate.setdefault("timelineMarkers", [])
    marker_count = 0
    if isinstance(candidate["timelineMarkers"], list):
        for row in rows:
            marker_count += 1
            candidate["timelineMarkers"].append(
                {
                    "startSeconds": row["timelineStartSeconds"],
                    "durationSeconds": max(0.25, float(row["timelineEndSeconds"]) - float(row["timelineStartSeconds"])),
                    "color": "Purple",
                    "name": f"BGM Phrase {row.get('phraseIndex')}",
                    "note": f"{row.get('section')}: {row.get('bgmAction')}",
                    "role": "bgm_phrase_candidate_marker",
                    "payload": {
                        "phraseIndex": row.get("phraseIndex"),
                        "section": row.get("section"),
                        "beatCueSeconds": row.get("beatCueSeconds"),
                    },
                }
            )
        candidate["timelineMarkers"] = sorted(
            candidate["timelineMarkers"],
            key=lambda item: (float(item.get("startSeconds") or 0.0), str(item.get("role") or "")),
        )
    return clip_annotations, transition_cues, marker_count


def build_candidate(package_dir: Path, *, update_blueprint: bool) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = package_dir / "bgm_phrase_blueprint"
    candidate_path = output_dir / "resolve_timeline_blueprint_bgm_phrase.json"
    report_path = output_dir / "bgm_phrase_blueprint_report.json"
    markdown_path = output_dir / "bgm_phrase_blueprint_report.md"
    base_blueprint, base_path, base_kind = choose_base_blueprint(package_dir)
    selection_path = package_dir / "bgm_selection_package" / "bgm_selection_package.json"
    selection = load_json(selection_path)
    audio_policy_path = package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json"
    audio_policy = load_json(audio_policy_path) or {}

    if not isinstance(base_blueprint, dict) or not isinstance(selection, dict):
        report = {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "needs_bgm_phrase_blueprint_inputs",
            "packageDir": str(package_dir),
            "inputs": {
                "baseBlueprint": str(base_path),
                "baseBlueprintExists": base_path.exists(),
                "bgmSelectionPackage": str(selection_path),
                "bgmSelectionPackageExists": selection_path.exists(),
            },
            "outputs": {
                "candidateBlueprint": str(candidate_path),
                "reportJson": str(report_path),
                "reportMarkdown": str(markdown_path),
            },
            "summary": {},
            "materializedRows": [],
            "safety": safety_policy(),
            "nextActions": ["Run prepare_bgm_selection_package.py, transition/effect candidate blueprints, then rerun this script."],
        }
        write_json(report_path, report)
        write_markdown(markdown_path, report)
        return report

    candidate = copy.deepcopy(base_blueprint)
    beds = selected_bgm_beds(selection)
    verified_beds = [bed for bed in beds if bed.get("localPathExists") and bed.get("licenseUrlPresent")]
    target_seconds = target_duration(package_dir, candidate, selection)
    rows = build_phrase_rows(candidate, selection, target_seconds, verified_beds)
    clip_annotations, transition_cues, marker_count = annotate_candidate(candidate, rows)
    audio_summary = audio_policy.get("summary") if isinstance(audio_policy.get("summary"), dict) else {}
    source_audio_risk = as_int(audio_summary.get("sourceAudioRiskCount"), 0)
    rows_with_decisions = 0
    blocked_rows = 0
    materialized_rows: list[dict[str, Any]] = []
    for row in rows:
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if set(DECISION_FIELDS).issubset(set(decision)):
            rows_with_decisions += 1
        blocked = not verified_beds or source_audio_risk > 0
        if blocked:
            blocked_rows += 1
        materialized_rows.append(
            {
                "phraseIndex": row.get("phraseIndex"),
                "section": row.get("section"),
                "status": "materialized" if not blocked else "needs_bgm_phrase_blueprint_repair",
                "timelineStartSeconds": row.get("timelineStartSeconds"),
                "timelineEndSeconds": row.get("timelineEndSeconds"),
                "durationSeconds": row.get("durationSeconds"),
                "bgmAction": row.get("bgmAction"),
                "transitionCue": row.get("transitionCue"),
                "selectedBgmBedLocal": bool((row.get("selectedBgmBed") or {}).get("localPath")),
                "selectedBgmBedLicense": bool((row.get("selectedBgmBed") or {}).get("licenseUrl")),
                "audioTreatment": row.get("audioTreatment"),
                "decision": dict(DECISION_FIELDS),
            }
        )

    updated_at = datetime.now().isoformat(timespec="seconds")
    candidate["updatedAt"] = updated_at
    candidate["bgmPhraseCandidates"] = rows
    candidate["bgmPhraseBlueprintPlan"] = {
        "status": "candidate_not_applied_to_resolve",
        "createdAt": updated_at,
        "baseBlueprint": str(base_path),
        "baseBlueprintKind": base_kind,
        "sourceBgmSelectionPackage": str(selection_path),
        "sourceAudioScenePolicyPlan": str(audio_policy_path),
        "report": str(report_path),
        "candidateBlueprint": str(candidate_path),
        "defaultBehavior": "writes a separate candidate blueprint and leaves the active blueprint untouched",
        "audioTreatment": "bgm_only_no_camera_voice",
    }
    audio_plan = candidate.get("audioPlan") if isinstance(candidate.get("audioPlan"), dict) else {}
    audio_plan["bgmPhraseMap"] = {
        "status": "candidate_not_applied_to_resolve",
        "targetDurationSeconds": round3(target_seconds),
        "selectedBgmBeds": verified_beds,
        "phraseRows": rows,
        "transitionCueCount": transition_cues,
    }
    candidate["audioPlan"] = audio_plan

    status = "ready_with_bgm_phrase_blueprint" if rows and verified_beds and not blocked_rows else "needs_bgm_phrase_blueprint_repair"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "baseBlueprint": str(base_path),
            "baseBlueprintKind": base_kind,
            "bgmSelectionPackage": str(selection_path),
            "bgmSelectionPackageStatus": selection.get("status"),
            "audioScenePolicyPlan": str(audio_policy_path),
            "audioScenePolicyStatus": audio_policy.get("status"),
        },
        "outputs": {
            "candidateBlueprint": str(candidate_path),
            "reportJson": str(report_path),
            "reportMarkdown": str(markdown_path),
            "activeBlueprintUpdated": bool(update_blueprint),
        },
        "summary": {
            "targetDurationSeconds": round3(target_seconds),
            "selectedBgmBedCount": len(verified_beds),
            "phraseRowCount": len(rows),
            "sectionRowCount": len({row.get("section") for row in rows}),
            "materializedPhraseCount": len(rows),
            "rowsWithDecisionFields": rows_with_decisions,
            "blockedRowCount": blocked_rows,
            "candidateClipCount": len(blueprint_clips(candidate)),
            "clipAnnotationCount": clip_annotations,
            "candidateTransitionCount": len(candidate.get("transitions") or []),
            "transitionCueCount": transition_cues,
            "transitionsWithPhraseCue": transition_cues,
            "markerCount": marker_count,
            "sourceAudioRiskCount": source_audio_risk,
            "audioScenePolicyStatus": audio_policy.get("status"),
        },
        "materializedRows": materialized_rows,
        "selectionRubric": {
            "pass": [
                "A verified local, license-traceable BGM bed is selected before phrase rows are trusted.",
                "Opening, body, transition, and ending phrase rows are materialized into blueprint metadata.",
                "Every candidate transition has a BGM phrase cue before Resolve apply.",
                "Clips overlapping scenic/title/transition windows carry bgmPhraseCandidates metadata.",
            ],
            "reject": [
                "Music is only mentioned in prose or a sourcing URL.",
                "Transition effects are not tied to phrase boundaries.",
                "Opening/title/transition windows can still leak source-camera or voiceover audio.",
                "The script writes Resolve, queues render, downloads assets, or mutates source footage.",
            ],
        },
        "safety": safety_policy(),
        "nextActions": [
            f"Run audit_resolve_blueprint.py --blueprint {candidate_path} --package-dir {package_dir} before using this candidate.",
            "Review bgm_phrase_blueprint_report.json and fill decision.approveCandidateBlueprint before Resolve apply.",
            "If approved, use a package fork or explicit --update-blueprint path so stale audio/style QA is not reused.",
        ],
    }
    write_json(candidate_path, candidate)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    if update_blueprint:
        active_path = package_dir / "resolve_timeline_blueprint.json"
        active_blueprint = load_json(active_path) or {}
        backup = package_dir / f"resolve_timeline_blueprint.before_bgm_phrase_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        write_json(backup, active_blueprint)
        write_json(active_path, candidate)
        report["outputs"]["activeBlueprintBackup"] = str(backup)
        write_json(report_path, report)
        write_markdown(markdown_path, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BGM Phrase Blueprint Report",
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
                f"### Phrase {row.get('phraseIndex')}: {row.get('section')}",
                f"- Status: `{row.get('status')}`",
                f"- Timeline: {row.get('timelineStartSeconds')}s-{row.get('timelineEndSeconds')}s",
                f"- Action: `{row.get('bgmAction')}`",
                f"- Audio treatment: `{row.get('audioTreatment')}`",
                f"- Selected bed local/license: {row.get('selectedBgmBedLocal')} / {row.get('selectedBgmBedLicense')}",
            ]
        )
        if row.get("transitionCue"):
            lines.append(f"- Transition cue: `{row.get('transitionCue')}`")
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a BGM phrase Resolve blueprint candidate.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--update-blueprint", action="store_true", help="Replace the active blueprint after writing a backup. Default is non-destructive.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_candidate(Path(args.package_dir), update_blueprint=args.update_blueprint)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report.get("status"), **(report.get("summary") or {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
