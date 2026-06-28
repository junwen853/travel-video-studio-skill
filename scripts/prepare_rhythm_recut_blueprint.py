#!/usr/bin/env python3
"""Prepare a non-destructive rhythm recut Resolve blueprint candidate."""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


EDITABLE_ROLES = {
    "opening_visual_bed",
    "main_footage",
    "main_footage_landscape_replacement",
    "transition_bridge_footage",
    "ending_visual_bed",
}
TITLE_OR_OVERLAY_TOKENS = (
    "subtitle",
    "title_card",
    "chapter_title",
    "city_aerial_title",
    "opening_city_aerial_title",
    "ending_city_aerial_title",
)
CUTAWAY_ROLES = {
    "transport_motion",
    "street_texture",
    "lived_in_detail",
    "landmark_payoff",
    "route_transition",
    "scenic_breathing",
    "opening_hook",
    "ending_aftertaste",
    "route_observation",
}
DECISION_FIELDS = {
    "approveCandidateBlueprint": "",
    "selectedCutawaySource": "",
    "replacementOrInsertSource": "",
    "resolveImplementation": "",
    "readbackEvidence": "",
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def round3(value: float) -> float:
    return round(float(value), 3)


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(first_present(clip.get("timelineStartSeconds"), clip.get("recordStartSeconds"), clip.get("startSeconds")), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(first_present(clip.get("timelineEndSeconds"), clip.get("recordEndSeconds"), clip.get("endSeconds")))
    if explicit is not None and explicit > start:
        return explicit
    duration = clip_duration(clip)
    return start + duration


def clip_duration(clip: dict[str, Any]) -> float:
    start = as_float(first_present(clip.get("timelineStartSeconds"), clip.get("recordStartSeconds"), clip.get("startSeconds")))
    end = as_float(first_present(clip.get("timelineEndSeconds"), clip.get("recordEndSeconds"), clip.get("endSeconds")))
    if start is not None and end is not None and end > start:
        return end - start
    for key in ("durationSeconds", "sourceDurationSeconds"):
        duration = as_float(clip.get(key))
        if duration and duration > 0:
            return duration
    source_start = as_float(clip.get("sourceStartSeconds"), 0.0) or 0.0
    source_end = as_float(clip.get("sourceEndSeconds"), 0.0) or 0.0
    return max(0.0, source_end - source_start)


def source_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("sourceStartSeconds"), 0.0) or 0.0)


def source_end(clip: dict[str, Any]) -> float:
    explicit = as_float(clip.get("sourceEndSeconds"))
    if explicit is not None and explicit > source_start(clip):
        return explicit
    return source_start(clip) + clip_duration(clip)


def track_index(clip: dict[str, Any]) -> int:
    return int(as_float(clip.get("trackIndex"), 1) or 1)


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(str(clip.get(key) or "") for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath")).lower()


def source_name(path: Any) -> str:
    text = str(path or "")
    return Path(text).name if text else ""


def stable_clip_id(clip: dict[str, Any]) -> str:
    return "|".join(
        [
            str(clip.get("role") or ""),
            str(clip.get("sourcePath") or ""),
            f"{timeline_start(clip):.3f}",
            f"{timeline_end(clip):.3f}",
            str(track_index(clip)),
        ]
    )


def is_video_clip(clip: dict[str, Any]) -> bool:
    track_type = str(clip.get("trackType") or "video").lower()
    return track_type in {"", "video"} and int(as_float(clip.get("mediaType"), 1) or 1) == 1


def is_overlay_or_title(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    return any(token in text for token in TITLE_OR_OVERLAY_TOKENS)


def is_editable_primary(clip: dict[str, Any]) -> bool:
    if not isinstance(clip, dict) or not is_video_clip(clip):
        return False
    role = str(clip.get("role") or "")
    if role in EDITABLE_ROLES:
        return True
    if track_index(clip) != 1:
        return False
    return not is_overlay_or_title(clip)


def visual_stat_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for clip in clips:
        if not isinstance(clip, dict) or not is_video_clip(clip):
            continue
        if "subtitle_overlay" in clip_text(clip):
            continue
        duration = clip_duration(clip)
        if duration <= 0:
            continue
        out.append(clip)
    return out


def duration_stats(clips: list[dict[str, Any]], soft_limit: float) -> dict[str, Any]:
    durations = [clip_duration(clip) for clip in clips if clip_duration(clip) > 0]
    return {
        "shotCount": len(durations),
        "averageSeconds": round3(sum(durations) / len(durations)) if durations else 0.0,
        "medianSeconds": round3(statistics.median(durations)) if durations else 0.0,
        "longShotRiskCount": sum(1 for value in durations if value > soft_limit),
        "maxSeconds": round3(max(durations)) if durations else 0.0,
    }


def build_row_lookup(edit_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = edit_plan.get("shotRows") if isinstance(edit_plan.get("shotRows"), list) else []
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = "|".join(
            [
                str(row.get("blueprintRole") or ""),
                str(row.get("sourcePath") or ""),
                f"{float(as_float(row.get('timelineStartSeconds'), 0.0) or 0.0):.3f}",
                f"{float(as_float(row.get('timelineEndSeconds'), 0.0) or 0.0):.3f}",
                str(int(as_float(row.get("trackIndex"), 1) or 1)),
            ]
        )
        lookup[key] = row
    return lookup


def row_for_clip(clip: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return lookup.get(stable_clip_id(clip), {})


def target_profile(edit_plan: dict[str, Any]) -> dict[str, Any]:
    target = edit_plan.get("targetRhythmProfile") if isinstance(edit_plan.get("targetRhythmProfile"), dict) else {}
    avg_range = target.get("targetAverageRangeSeconds") if isinstance(target.get("targetAverageRangeSeconds"), list) else [5.0, 10.0]
    return {
        "targetAverageUpperSeconds": float(as_float(avg_range[-1] if avg_range else None, 10.0) or 10.0),
        "longShotSoftLimitSeconds": float(as_float(target.get("longShotSoftLimitSeconds"), 12.0) or 12.0),
        "breathingShotLimitSeconds": float(as_float(target.get("breathingShotLimitSeconds"), 24.0) or 24.0),
    }


def rhythm_role_for(clip: dict[str, Any], row: dict[str, Any]) -> str:
    return str(row.get("rhythmRole") or clip.get("rhythmRole") or clip.get("role") or "route_observation")


def should_recut(clip: dict[str, Any], row: dict[str, Any], target: dict[str, Any]) -> bool:
    duration = clip_duration(clip)
    if duration <= target["longShotSoftLimitSeconds"]:
        return False
    if duration < 10.0:
        return False
    role = str(clip.get("role") or "")
    if role in {"chapter_title_bridge", "opening_city_aerial_title", "ending_city_aerial_title"}:
        return False
    risks = row.get("riskReasons") if isinstance(row.get("riskReasons"), list) else []
    if risks:
        return True
    return duration > max(target["longShotSoftLimitSeconds"], target["targetAverageUpperSeconds"])


def complementary_roles(role: str) -> set[str]:
    if role in {"transport_motion", "route_transition"}:
        return {"street_texture", "lived_in_detail", "landmark_payoff", "scenic_breathing", "route_observation"}
    if role == "lived_in_detail":
        return {"transport_motion", "street_texture", "landmark_payoff", "route_transition"}
    if role == "landmark_payoff":
        return {"transport_motion", "street_texture", "lived_in_detail", "route_transition"}
    if role in {"opening_hook", "ending_aftertaste", "scenic_breathing"}:
        return {"transport_motion", "street_texture", "lived_in_detail", "landmark_payoff", "route_transition"}
    return {"transport_motion", "street_texture", "lived_in_detail", "landmark_payoff", "route_transition", "scenic_breathing"}


def build_cutaway_pool(
    clips: list[dict[str, Any]],
    row_lookup: dict[str, dict[str, Any]],
    *,
    min_cutaway_seconds: float,
) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    for clip in clips:
        if not is_editable_primary(clip):
            continue
        duration = clip_duration(clip)
        source_duration = max(0.0, source_end(clip) - source_start(clip))
        if max(duration, source_duration) < min_cutaway_seconds:
            continue
        row = row_for_clip(clip, row_lookup)
        rhythm_role = rhythm_role_for(clip, row)
        if rhythm_role not in CUTAWAY_ROLES:
            continue
        pool.append(
            {
                "clip": clip,
                "row": row,
                "sourcePath": clip.get("sourcePath"),
                "sourceName": source_name(clip.get("sourcePath")),
                "sourceStartSeconds": source_start(clip),
                "sourceEndSeconds": source_end(clip),
                "durationSeconds": duration,
                "chapterIndex": clip.get("chapterIndex"),
                "rhythmRole": rhythm_role,
                "blueprintRole": clip.get("role"),
                "rowIndex": row.get("rowIndex"),
                "purpose": clip.get("purpose"),
                "place": clip.get("place"),
            }
        )
    return pool


def candidate_score(candidate: dict[str, Any], clip: dict[str, Any], row: dict[str, Any], role: str, use_count: int) -> tuple[int, float, str]:
    score = 0
    source = str(candidate.get("sourcePath") or "")
    if source and source != str(clip.get("sourcePath") or ""):
        score += 60
    else:
        score -= 80
    if candidate.get("rhythmRole") in complementary_roles(role):
        score += 25
    if candidate.get("chapterIndex") == clip.get("chapterIndex"):
        score += 8
    if candidate.get("chapterIndex") is not None and clip.get("chapterIndex") is not None:
        try:
            if abs(int(candidate["chapterIndex"]) - int(clip["chapterIndex"])) == 1:
                score += 4
        except (TypeError, ValueError):
            pass
    if "title" in str(candidate.get("blueprintRole") or "").lower():
        score -= 20
    if row.get("rowIndex") and candidate.get("rowIndex") == row.get("rowIndex"):
        score -= 40
    score -= use_count * 2
    return (score, float(candidate.get("durationSeconds") or 0.0), str(candidate.get("sourceName") or ""))


def select_cutaway(
    pool: list[dict[str, Any]],
    clip: dict[str, Any],
    row: dict[str, Any],
    role: str,
    use_counts: dict[str, int],
) -> dict[str, Any] | None:
    if not pool:
        return None
    scored = []
    for candidate in pool:
        key = str(candidate.get("sourcePath") or "")
        scored.append((candidate_score(candidate, clip, row, role, use_counts.get(key, 0)), candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored else None


def choose_cutaway_count(duration: float, target: dict[str, Any], cutaway_seconds: float) -> int:
    soft_limit = float(target["longShotSoftLimitSeconds"])
    main_target = min(8.0, max(6.0, float(target["targetAverageUpperSeconds"]) * 0.75))
    min_cutaways = 2 if duration > float(target["breathingShotLimitSeconds"]) else 1
    for count in range(min_cutaways, 5):
        main_total = duration - (count * cutaway_seconds)
        if main_total <= 4.0:
            continue
        main_count = count + 1
        main_each = main_total / main_count
        if 3.5 <= main_each <= min(soft_limit, main_target * 1.2):
            return count
    return min(4, max(1, math.ceil(duration / max(soft_limit, 1.0)) - 1))


def distribute_main_durations(total: float, count: int) -> list[float]:
    if count <= 0:
        return []
    each = total / count
    durations = [round3(each) for _ in range(count)]
    drift = round3(total - sum(durations))
    durations[-1] = round3(durations[-1] + drift)
    return durations


def cutaway_source_window(candidate: dict[str, Any], duration: float, use_counts: dict[str, int]) -> tuple[float, float]:
    source = str(candidate.get("sourcePath") or "")
    use_count = use_counts.get(source, 0)
    start = float(candidate.get("sourceStartSeconds") or 0.0)
    end = float(candidate.get("sourceEndSeconds") or start + duration)
    available = max(duration, end - start)
    max_offset = max(0.0, available - duration)
    if max_offset <= 0:
        offset = 0.0
    else:
        offset = min(max_offset, (use_count * (duration + 1.0)) % (max_offset + 0.001))
    cut_start = round3(start + offset)
    cut_end = round3(cut_start + duration)
    if cut_end > end and end > start:
        cut_end = round3(end)
        cut_start = round3(max(start, cut_end - duration))
    use_counts[source] = use_count + 1
    return cut_start, cut_end


def recut_clip(
    clip: dict[str, Any],
    row: dict[str, Any],
    pool: list[dict[str, Any]],
    target: dict[str, Any],
    use_counts: dict[str, int],
    *,
    cutaway_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    original_start = timeline_start(clip)
    original_end = timeline_end(clip)
    duration = original_end - original_start
    role = rhythm_role_for(clip, row)
    cutaway_count = choose_cutaway_count(duration, target, cutaway_seconds)
    main_total = max(0.0, duration - (cutaway_count * cutaway_seconds))
    main_durations = distribute_main_durations(main_total, cutaway_count + 1)
    if not main_durations:
        return [clip], None

    pieces: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    cursor = original_start
    source_cursor = source_start(clip)
    sequence_count = len(main_durations) + cutaway_count
    for index, main_duration in enumerate(main_durations):
        piece = copy.deepcopy(clip)
        piece["timelineStartSeconds"] = round3(cursor)
        piece["timelineEndSeconds"] = round3(cursor + main_duration)
        piece["sourceStartSeconds"] = round3(source_cursor)
        piece["sourceEndSeconds"] = round3(source_cursor + main_duration)
        piece["durationSeconds"] = round3(main_duration)
        piece["includeSourceAudio"] = False
        piece["rhythmRecut"] = {
            "kind": "main_segment",
            "sourceClipRole": clip.get("role"),
            "originalTimelineStartSeconds": round3(original_start),
            "originalTimelineEndSeconds": round3(original_end),
            "segmentIndex": len(pieces) + 1,
            "segmentCount": sequence_count,
            "sourceRowIndex": row.get("rowIndex"),
            "rhythmRole": role,
            "reason": "split long raw hold into shorter travel-film beats",
        }
        pieces.append(piece)
        cursor += main_duration
        source_cursor += main_duration

        if index >= cutaway_count:
            continue
        candidate = select_cutaway(pool, clip, row, role, use_counts)
        if not candidate:
            return [clip], None
        cut_start, cut_end = cutaway_source_window(candidate, cutaway_seconds, use_counts)
        cutaway = copy.deepcopy(candidate["clip"])
        cutaway.update(
            {
                "role": "rhythm_cutaway_insert",
                "chapterIndex": clip.get("chapterIndex"),
                "sourcePath": candidate.get("sourcePath"),
                "sourceStartSeconds": cut_start,
                "sourceEndSeconds": cut_end,
                "timelineStartSeconds": round3(cursor),
                "timelineEndSeconds": round3(cursor + cutaway_seconds),
                "durationSeconds": round3(cutaway_seconds),
                "trackType": "video",
                "trackIndex": track_index(clip),
                "mediaType": 1,
                "includeSourceAudio": False,
                "purpose": (
                    "rhythm recut cutaway to break a long flat shot; "
                    f"source role {candidate.get('rhythmRole')}"
                ),
                "rhythmRecut": {
                    "kind": "cutaway_insert",
                    "sourceClipRole": candidate.get("blueprintRole"),
                    "sourceRowIndex": candidate.get("rowIndex"),
                    "sourceRhythmRole": candidate.get("rhythmRole"),
                    "replacementForRowIndex": row.get("rowIndex"),
                    "originalTimelineStartSeconds": round3(original_start),
                    "originalTimelineEndSeconds": round3(original_end),
                    "segmentIndex": len(pieces) + 1,
                    "segmentCount": sequence_count,
                    "reason": "insert motivated real-footage cutaway inside long hold",
                },
            }
        )
        pieces.append(cutaway)
        decisions.append(
            {
                "segmentIndex": len(pieces),
                "cutawaySourcePath": candidate.get("sourcePath"),
                "cutawaySourceName": candidate.get("sourceName"),
                "cutawayRhythmRole": candidate.get("rhythmRole"),
                "cutawaySourceRowIndex": candidate.get("rowIndex"),
                "cutawaySourceStartSeconds": cut_start,
                "cutawaySourceEndSeconds": cut_end,
            }
        )
        cursor += cutaway_seconds

    if pieces:
        pieces[-1]["timelineEndSeconds"] = round3(original_end)
        if pieces[-1].get("rhythmRecut", {}).get("kind") == "main_segment":
            last_duration = max(0.0, timeline_end(pieces[-1]) - timeline_start(pieces[-1]))
            pieces[-1]["durationSeconds"] = round3(last_duration)
            pieces[-1]["sourceEndSeconds"] = round3(float(pieces[-1].get("sourceStartSeconds") or 0.0) + last_duration)

    decision = {
        "rowIndex": row.get("rowIndex"),
        "sourcePath": clip.get("sourcePath"),
        "sourceName": source_name(clip.get("sourcePath")),
        "blueprintRole": clip.get("role"),
        "rhythmRole": role,
        "chapterIndex": clip.get("chapterIndex"),
        "originalTimelineStartSeconds": round3(original_start),
        "originalTimelineEndSeconds": round3(original_end),
        "originalDurationSeconds": round3(duration),
        "newSegmentCount": len(pieces),
        "mainSegmentCount": len([piece for piece in pieces if piece.get("rhythmRecut", {}).get("kind") == "main_segment"]),
        "cutawayInsertCount": len(decisions),
        "cutaways": decisions,
        "decision": dict(DECISION_FIELDS),
        "editorGuidance": "Candidate only. Review in Resolve, then apply or refine after readback.",
    }
    return pieces, decision


def sort_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        clips,
        key=lambda clip: (
            round3(timeline_start(clip)),
            int(as_float(clip.get("trackIndex"), 1) or 1),
            str(clip.get("role") or ""),
            str(clip.get("sourcePath") or ""),
        ),
    )


def timeline_duration(clips: list[dict[str, Any]], fallback: float = 0.0) -> float:
    ends = [timeline_end(clip) for clip in clips if isinstance(clip, dict) and is_video_clip(clip) and timeline_end(clip) > 0]
    return max([fallback, *ends], default=fallback)


def build_candidate(package_dir: Path, *, cutaway_seconds: float) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    plan_path = package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json"
    output_dir = package_dir / "rhythm_recut_blueprint"
    candidate_path = output_dir / "resolve_timeline_blueprint_rhythm_recut.json"
    report_path = output_dir / "rhythm_recut_blueprint_report.json"
    markdown_path = output_dir / "rhythm_recut_blueprint_report.md"

    blueprint = load_json(blueprint_path)
    edit_plan = load_json(plan_path)
    if not isinstance(blueprint, dict) or not isinstance(edit_plan, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "needs_rhythm_recut_inputs",
            "packageDir": str(package_dir),
            "inputs": {
                "resolveBlueprint": str(blueprint_path),
                "resolveBlueprintExists": blueprint_path.exists(),
                "editRhythmPlan": str(plan_path),
                "editRhythmPlanExists": plan_path.exists(),
            },
            "outputs": {
                "candidateBlueprint": str(candidate_path),
                "reportJson": str(report_path),
                "reportMarkdown": str(markdown_path),
            },
            "summary": {},
            "recutRows": [],
            "selectionRubric": selection_rubric(),
            "safety": safety_policy(),
            "nextActions": ["Run prepare_edit_rhythm_plan.py and ensure resolve_timeline_blueprint.json exists first."],
        }

    original_clips = [clip for clip in blueprint.get("clips") or [] if isinstance(clip, dict)]
    row_lookup = build_row_lookup(edit_plan)
    target = target_profile(edit_plan)
    cutaway_pool = build_cutaway_pool(original_clips, row_lookup, min_cutaway_seconds=cutaway_seconds)
    revised_clips: list[dict[str, Any]] = []
    recut_rows: list[dict[str, Any]] = []
    kept_long_rows: list[dict[str, Any]] = []
    use_counts: dict[str, int] = {}

    for clip in original_clips:
        if not is_editable_primary(clip):
            revised_clips.append(copy.deepcopy(clip))
            continue
        row = row_for_clip(clip, row_lookup)
        if should_recut(clip, row, target):
            pieces, decision = recut_clip(clip, row, cutaway_pool, target, use_counts, cutaway_seconds=cutaway_seconds)
            revised_clips.extend(pieces)
            if decision:
                recut_rows.append(decision)
            else:
                revised_clips.pop()
                revised_clips.append(copy.deepcopy(clip))
                kept_long_rows.append(
                    {
                        "sourcePath": clip.get("sourcePath"),
                        "sourceName": source_name(clip.get("sourcePath")),
                        "timelineStartSeconds": round3(timeline_start(clip)),
                        "timelineEndSeconds": round3(timeline_end(clip)),
                        "durationSeconds": round3(clip_duration(clip)),
                        "reason": "no suitable cutaway candidate found",
                    }
                )
        else:
            revised_clips.append(copy.deepcopy(clip))

    revised_clips = sort_clips(revised_clips)
    candidate = copy.deepcopy(blueprint)
    candidate["clips"] = revised_clips
    candidate["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    candidate["rhythmRecutPlan"] = {
        "status": "candidate_not_applied_to_resolve",
        "createdAt": candidate["updatedAt"],
        "sourceBlueprint": str(blueprint_path),
        "sourceEditRhythmPlan": str(plan_path),
        "report": str(report_path),
        "defaultBehavior": "writes a separate candidate blueprint and leaves the original blueprint untouched",
        "cutawaySeconds": cutaway_seconds,
    }

    before_visual = visual_stat_clips(original_clips)
    after_visual = visual_stat_clips(revised_clips)
    before_editable = [clip for clip in original_clips if is_editable_primary(clip)]
    after_editable = [clip for clip in revised_clips if is_editable_primary(clip)]
    before_stats = duration_stats(before_visual, target["longShotSoftLimitSeconds"])
    after_stats = duration_stats(after_visual, target["longShotSoftLimitSeconds"])
    before_duration = timeline_duration(original_clips, float(as_float(blueprint.get("targetDurationSeconds"), 0.0) or 0.0))
    after_duration = timeline_duration(revised_clips, before_duration)
    duration_delta = round3(after_duration - before_duration)
    long_editable_clips = [
        clip
        for clip in original_clips
        if is_editable_primary(clip)
        and should_recut(clip, row_for_clip(clip, row_lookup), target)
    ]
    cutaway_insert_count = sum(int(row.get("cutawayInsertCount") or 0) for row in recut_rows)
    split_source_clip_count = len(recut_rows)
    if not long_editable_clips:
        status = "ready_no_recut_needed"
    elif split_source_clip_count and cutaway_insert_count and abs(duration_delta) <= 0.5 and after_stats["averageSeconds"] < before_stats["averageSeconds"]:
        status = "ready_with_rhythm_recut_blueprint"
    else:
        status = "needs_rhythm_recut_review"

    report = {
        "createdAt": candidate["updatedAt"],
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(blueprint_path),
            "editRhythmPlan": str(plan_path),
        },
        "outputs": {
            "candidateBlueprint": str(candidate_path),
            "reportJson": str(report_path),
            "reportMarkdown": str(markdown_path),
        },
        "targetRhythmProfile": target,
        "summary": {
            "originalClipCount": len(original_clips),
            "revisedClipCount": len(revised_clips),
            "originalPrimaryClipCount": len(before_editable),
            "revisedPrimaryClipCount": len(after_editable),
            "longEditableClipCount": len(long_editable_clips),
            "splitSourceClipCount": split_source_clip_count,
            "cutawayInsertCount": cutaway_insert_count,
            "cutawayPoolCount": len(cutaway_pool),
            "keptLongClipCount": len(kept_long_rows),
            "averagePrimaryShotBeforeSeconds": before_stats["averageSeconds"],
            "averagePrimaryShotAfterSeconds": after_stats["averageSeconds"],
            "medianPrimaryShotBeforeSeconds": before_stats["medianSeconds"],
            "medianPrimaryShotAfterSeconds": after_stats["medianSeconds"],
            "longShotRiskBefore": before_stats["longShotRiskCount"],
            "longShotRiskAfter": after_stats["longShotRiskCount"],
            "maxShotBeforeSeconds": before_stats["maxSeconds"],
            "maxShotAfterSeconds": after_stats["maxSeconds"],
            "timelineDurationBeforeSeconds": round3(before_duration),
            "timelineDurationAfterSeconds": round3(after_duration),
            "durationDeltaSeconds": duration_delta,
            "targetAverageUpperSeconds": target["targetAverageUpperSeconds"],
            "longShotSoftLimitSeconds": target["longShotSoftLimitSeconds"],
        },
        "recutRows": recut_rows,
        "keptLongRows": kept_long_rows,
        "selectionRubric": selection_rubric(),
        "safety": safety_policy(),
        "nextActions": [
            "Review the candidate blueprint in a dry run before replacing the active Resolve blueprint.",
            "If approved, rerun audit_resolve_blueprint.py against the candidate blueprint before any Resolve apply.",
            "After Resolve readback, fill each recut row decision.readbackEvidence and rerun reference-style and director-polish audits.",
        ],
    }
    write_json(candidate_path, candidate)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    return report


def selection_rubric() -> dict[str, list[str]]:
    return {
        "pass": [
            "The script writes a separate candidate blueprint and does not modify Resolve or source footage.",
            "Long raw holds are split into shorter main segments plus real-footage cutaways from the existing blueprint.",
            "The candidate preserves total timeline duration within 0.5 seconds unless an editor explicitly approves otherwise.",
            "Cutaways stay BGM-only with includeSourceAudio false and carry row-level review fields.",
            "A Resolve blueprint preflight can be run against the candidate before any apply step.",
        ],
        "reject": [
            "The original resolve_timeline_blueprint.json is overwritten without explicit update approval.",
            "Cutaways come from fabricated, downloaded, or untracked stock media instead of approved local footage.",
            "The timeline becomes shorter or longer by more than 0.5 seconds without a written editor decision.",
            "The report claims the cut is fixed but no candidate blueprint or row-level decisions exist.",
        ],
    }


def safety_policy() -> dict[str, bool]:
    return {
        "downloadsExternalAssets": False,
        "writesResolve": False,
        "modifiesSourceFootage": False,
        "modifiesOriginalBlueprintByDefault": False,
        "requiresResolvePreflightBeforeApply": True,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Rhythm Recut Blueprint Report",
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
        "## Outputs",
        "",
        f"- Candidate blueprint: `{(report.get('outputs') or {}).get('candidateBlueprint')}`",
        f"- Report JSON: `{(report.get('outputs') or {}).get('reportJson')}`",
        "",
        "## Recut Decisions",
    ]
    rows = report.get("recutRows") if isinstance(report.get("recutRows"), list) else []
    if not rows:
        lines.append("- None.")
    for row in rows[:80]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('rhythmRole')}",
                f"- Window: `{row.get('originalTimelineStartSeconds')}` to `{row.get('originalTimelineEndSeconds')}` ({row.get('originalDurationSeconds')}s)",
                f"- Source: `{row.get('sourceName')}`",
                f"- New segments: {row.get('newSegmentCount')} ({row.get('cutawayInsertCount')} cutaways)",
                "- Cutaways:",
            ]
        )
        for cutaway in row.get("cutaways") or []:
            lines.append(
                f"  - `{cutaway.get('cutawaySourceName')}` "
                f"as `{cutaway.get('cutawayRhythmRole')}` "
                f"({cutaway.get('cutawaySourceStartSeconds')}-{cutaway.get('cutawaySourceEndSeconds')}s)"
            )
        lines.append("- Decision fields to fill:")
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    kept = report.get("keptLongRows") if isinstance(report.get("keptLongRows"), list) else []
    if kept:
        lines.extend(["", "## Kept Long Rows"])
        for row in kept[:40]:
            lines.append(f"- `{row.get('sourceName')}` at {row.get('timelineStartSeconds')}-{row.get('timelineEndSeconds')}s: {row.get('reason')}")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in report["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in report["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report["nextActions"])
    write_text(path, "\n".join(lines) + "\n")


def maybe_update_blueprint(package_dir: Path, report: dict[str, Any]) -> Path | None:
    candidate_path = Path(str((report.get("outputs") or {}).get("candidateBlueprint") or ""))
    if not candidate_path.exists():
        return None
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = package_dir / f"resolve_timeline_blueprint.before_rhythm_recut_{timestamp}.json"
    shutil.copy2(blueprint_path, backup_path)
    shutil.copy2(candidate_path, blueprint_path)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a non-destructive rhythm recut Resolve blueprint candidate.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--cutaway-seconds", type=float, default=3.5)
    parser.add_argument("--update-blueprint", action="store_true", help="Back up and replace resolve_timeline_blueprint.json with the candidate.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_candidate(package_dir, cutaway_seconds=max(2.0, float(args.cutaway_seconds)))
    backup = None
    if args.update_blueprint and report.get("status") in {"ready_with_rhythm_recut_blueprint", "ready_no_recut_needed"}:
        backup = maybe_update_blueprint(package_dir, report)
        report["updatedOriginalBlueprint"] = True
        report["originalBlueprintBackup"] = str(backup) if backup else None
        write_json(Path(str((report.get("outputs") or {}).get("reportJson"))), report)
        write_markdown(Path(str((report.get("outputs") or {}).get("reportMarkdown"))), report)
    payload = report if args.json else {"status": report.get("status"), "outputs": report.get("outputs"), "summary": report.get("summary"), "backup": str(backup) if backup else None}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
