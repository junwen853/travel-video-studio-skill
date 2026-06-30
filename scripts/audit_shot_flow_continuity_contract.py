#!/usr/bin/env python3
"""Audit whether chapter shots flow in a viewer-readable order."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


PRIMARY_BEATS = ("context", "movement", "texture", "payoff", "aftertaste")
UTILITY_BEATS = {"title", "transition", "effect", "utility", "unclassified"}
REJECT_TIERS = {"reject_or_replace", "reject_or_review", "reject_excluded"}
UTILITY_TIERS = {"utility_only", "utility_context"}
TITLE_TERMS = ("title", "opening_city", "chapter_title", "ending_city", "subtitle_overlay")
WEAK_TERMS = ("black", "placeholder", "slate", "generic", "test", "sample", "duplicate", "obstruct", "blur")

FUNCTION_BEATS = {
    "route_movement": "movement",
    "transport_motion": "movement",
    "route_transition": "movement",
    "lived_in_detail": "texture",
    "street_texture": "texture",
    "destination_payoff": "payoff",
    "landmark_payoff": "payoff",
    "opening_hook": "context",
    "scenic_breathing": "context",
    "route_observation": "context",
    "title_bridge": "context",
    "ending_aftertaste": "aftertaste",
    "aftertaste": "aftertaste",
}

TERM_BEATS = {
    "aftertaste": (
        "aftertaste",
        "ending",
        "callback",
        "final",
        "sunset",
        "dusk",
        "quiet",
        "departure",
        "leaving",
        "night window",
    ),
    "movement": (
        "movement",
        "route",
        "transport",
        "station",
        "train",
        "metro",
        "subway",
        "airport",
        "road",
        "walk",
        "arrival",
        "bridge",
        "motion",
        "ferry",
        "bus",
        "car",
        "luggage",
        "ticket",
    ),
    "texture": (
        "texture",
        "lived",
        "street",
        "food",
        "hotel",
        "market",
        "shop",
        "detail",
        "daily",
        "interior",
        "sign",
        "weather",
        "coffee",
        "room",
    ),
    "payoff": (
        "payoff",
        "landmark",
        "destination",
        "scenic",
        "aerial",
        "drone",
        "skyline",
        "hero",
        "viewpoint",
        "coast",
        "temple",
        "tower",
        "castle",
        "harbor",
        "mountain",
        "panorama",
    ),
    "context": ("context", "people", "face", "reaction", "vlog", "opening", "chapter", "city", "place"),
}

ALLOWED_PAIRS = {
    ("context", "context"),
    ("context", "movement"),
    ("context", "texture"),
    ("context", "payoff"),
    ("movement", "context"),
    ("movement", "movement"),
    ("movement", "texture"),
    ("movement", "payoff"),
    ("movement", "aftertaste"),
    ("texture", "context"),
    ("texture", "movement"),
    ("texture", "texture"),
    ("texture", "payoff"),
    ("texture", "aftertaste"),
    ("payoff", "movement"),
    ("payoff", "texture"),
    ("payoff", "aftertaste"),
    ("aftertaste", "aftertaste"),
}


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


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def inputs_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("inputs"), dict):
        return data["inputs"]
    return {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


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
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in (
            "role",
            "purpose",
            "place",
            "titleText",
            "subtitle",
            "sourcePath",
            "sourceName",
            "name",
            "notes",
            "creatorFunction",
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
    video = [row for row in rows if isinstance(row, dict) and is_video_clip(row)]
    return sorted(video, key=lambda item: (timeline_start(item), timeline_end(item), str(item.get("sourcePath") or "")))


def plan_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("clipRows", "shotRows", "selectionRows", "rows"):
        rows = plan.get(key)
        if isinstance(rows, list):
            out.extend(row for row in rows if isinstance(row, dict))
    return out


def lookup_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        keys = {
            str(row.get("sourcePath") or ""),
            str(row.get("sourceName") or ""),
            source_name(row.get("sourcePath") or row.get("sourceName")),
        }
        for key in keys:
            if key and key not in lookup:
                lookup[key] = row
    return lookup


def match_row(clip: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in (
        str(clip.get("sourcePath") or ""),
        str(clip.get("sourceName") or ""),
        source_name(clip.get("sourcePath") or clip.get("sourceName")),
    ):
        if key in lookup:
            return lookup[key]
    return None


def row_function(clip: dict[str, Any], creator_row: dict[str, Any] | None, creator_audit_row: dict[str, Any] | None) -> str:
    for row in (creator_audit_row, creator_row, clip):
        if isinstance(row, dict):
            value = row.get("creatorFunction")
            if value:
                return str(value)
    return ""


def row_tier(creator_row: dict[str, Any] | None, creator_audit_row: dict[str, Any] | None) -> str:
    for row in (creator_audit_row, creator_row):
        if isinstance(row, dict):
            value = row.get("editorialTier") or row.get("selectionTier")
            if value:
                return str(value)
    return ""


def classify_beat(clip: dict[str, Any], creator_row: dict[str, Any] | None, creator_audit_row: dict[str, Any] | None) -> tuple[str, list[str]]:
    text = clip_text(clip)
    function = row_function(clip, creator_row, creator_audit_row)
    groups: set[str] = set()
    if function in FUNCTION_BEATS:
        groups.add(FUNCTION_BEATS[function])
    for beat, terms in TERM_BEATS.items():
        if any(term in text for term in terms):
            groups.add(beat)
    if any(term in text for term in TITLE_TERMS) and "bridge" not in text and "scenic" not in text:
        return "title", sorted(groups or {"context"})
    if "transition" in text or "whip" in text or "speed_ramp" in text or "rotation" in text:
        groups.add("movement")
    if not groups:
        return "unclassified", []
    for beat in ("aftertaste", "movement", "texture", "payoff", "context"):
        if beat in groups:
            return beat, sorted(groups)
    return "unclassified", sorted(groups)


def normalize_chapter(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return "unassigned"
    text = str(value).strip()
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except ValueError:
        pass
    return text


def chapter_sort_key(value: str) -> tuple[int, str]:
    if value == "unassigned":
        return (999999, value)
    try:
        return (int(float(value)), value)
    except ValueError:
        return (999998, value)


def run_length(values: list[str]) -> int:
    best = 0
    current = ""
    length = 0
    for value in values:
        if value == current:
            length += 1
        else:
            current = value
            length = 1
        best = max(best, length)
    return best


def annotate_clip(index: int, clip: dict[str, Any], creator_row: dict[str, Any] | None, creator_audit_row: dict[str, Any] | None) -> dict[str, Any]:
    beat, groups = classify_beat(clip, creator_row, creator_audit_row)
    tier = row_tier(creator_row, creator_audit_row)
    issues: list[str] = []
    text = clip_text(clip)
    audit_issues = creator_audit_row.get("issues") if isinstance(creator_audit_row, dict) else []
    if tier in REJECT_TIERS:
        issues.append("reject_or_repair_clip_is_active")
    if tier in UTILITY_TIERS:
        issues.append("utility_clip_is_active")
    if beat == "unclassified":
        issues.append("clip_has_no_readable_story_beat")
    if any(term in text for term in WEAK_TERMS) or any("weak" in str(item) for item in (audit_issues or [])):
        issues.append("weak_or_placeholder_clip_is_active")
    return {
        "clipIndex": index,
        "chapterIndex": normalize_chapter(clip.get("chapterIndex")),
        "sourcePath": clip.get("sourcePath"),
        "sourceName": source_name(clip.get("sourcePath") or clip.get("sourceName")),
        "timelineStartSeconds": round3(timeline_start(clip)),
        "timelineEndSeconds": round3(timeline_end(clip)),
        "durationSeconds": round3(max(0.0, timeline_end(clip) - timeline_start(clip))),
        "role": clip.get("role"),
        "purpose": clip.get("purpose"),
        "beat": beat,
        "beatGroups": groups,
        "creatorFunction": row_function(clip, creator_row, creator_audit_row),
        "editorialTier": tier,
        "creatorAuditStatus": creator_audit_row.get("status") if isinstance(creator_audit_row, dict) else None,
        "issues": issues,
    }


def primary_sequence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("beat") in PRIMARY_BEATS]


def first_index(sequence: list[str], beat: str) -> int | None:
    try:
        return sequence.index(beat)
    except ValueError:
        return None


def last_index(sequence: list[str], beat: str) -> int | None:
    for index in range(len(sequence) - 1, -1, -1):
        if sequence[index] == beat:
            return index
    return None


def weak_pairs(sequence: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(sequence, sequence[1:]), start=1):
        if (left, right) not in ALLOWED_PAIRS:
            out.append({"pairIndex": index, "fromBeat": left, "toBeat": right, "reason": "unmotivated_beat_jump"})
        if left == "aftertaste" and right != "aftertaste" and index < len(sequence) - 1:
            out.append({"pairIndex": index, "fromBeat": left, "toBeat": right, "reason": "aftertaste_returns_to_middle_of_chapter"})
    return out


def analyze_chapter(chapter_index: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(rows, key=lambda item: (float(item.get("timelineStartSeconds") or 0.0), int(item.get("clipIndex") or 0)))
    primary_rows = primary_sequence(rows)
    sequence = [str(row.get("beat") or "") for row in primary_rows]
    all_beats = [str(row.get("beat") or "") for row in rows]
    groups = sorted({beat for row in rows for beat in row.get("beatGroups", []) if beat in PRIMARY_BEATS})
    source_sequence = [str(row.get("sourceName") or "") for row in rows]
    issues: list[str] = []
    if len(rows) < 3:
        issues.append("chapter_has_too_few_visual_clips")
    if len(primary_rows) < 3:
        issues.append("chapter_has_too_few_primary_story_beats")
    for beat in ("movement", "texture", "payoff"):
        if beat not in sequence and beat not in groups:
            issues.append(f"chapter_missing_{beat}_beat")
    if "aftertaste" not in sequence and "aftertaste" not in groups:
        issues.append("chapter_missing_aftertaste_or_handoff_beat")
    if chapter_index == "unassigned" and len(rows) >= 3:
        issues.append("chapter_index_missing_on_final_visual_clips")

    first_movement = first_index(sequence, "movement")
    first_texture = first_index(sequence, "texture")
    first_payoff = first_index(sequence, "payoff")
    last_payoff = last_index(sequence, "payoff")
    first_aftertaste = first_index(sequence, "aftertaste")
    last_aftertaste = last_index(sequence, "aftertaste")
    if first_payoff is not None and first_payoff == 0 and len(sequence) >= 4 and not (sequence[1:3] and {"movement", "texture"} & set(sequence[1:3])):
        issues.append("chapter_opens_with_payoff_without_nearby_movement_or_texture")
    if first_payoff is not None and first_movement is not None and first_movement > first_payoff + 2:
        issues.append("route_movement_arrives_too_late_after_payoff")
    if last_payoff is not None and first_texture is not None and first_texture > last_payoff:
        issues.append("lived_in_texture_only_arrives_after_final_payoff")
    if first_aftertaste is not None and len(sequence) >= 4 and first_aftertaste < math.floor(len(sequence) * 0.5):
        issues.append("aftertaste_or_handoff_appears_too_early")
    if last_aftertaste is not None and len(sequence) >= 4 and last_aftertaste < len(sequence) - 2:
        issues.append("chapter_continues_too_long_after_aftertaste")

    pair_rows = weak_pairs(sequence)
    if pair_rows:
        issues.append("chapter_has_unmotivated_beat_jumps")
    utility_run = run_length([beat for beat in all_beats if beat in UTILITY_BEATS])
    same_beat_run = run_length(sequence)
    same_source_run = run_length(source_sequence)
    if utility_run > 2:
        issues.append(f"utility_or_title_run_too_long:{utility_run}")
    if same_beat_run > 3:
        issues.append(f"same_story_beat_run_too_long:{same_beat_run}")
    if same_source_run > 3 and len(rows) >= 5:
        issues.append(f"same_source_run_too_long:{same_source_run}")
    rejected_or_weak = [row for row in rows if row.get("issues")]
    if rejected_or_weak:
        issues.append("chapter_contains_reject_utility_weak_or_unclassified_clip")
    return {
        "chapterIndex": chapter_index,
        "status": "passed" if not issues else "blocked",
        "clipCount": len(rows),
        "primaryBeatCount": len(primary_rows),
        "beatSequence": sequence,
        "beatGroups": groups,
        "weakPairCount": len(pair_rows),
        "weakPairs": pair_rows[:40],
        "sameBeatRunMax": same_beat_run,
        "sameSourceRunMax": same_source_run,
        "utilityRunMax": utility_run,
        "rejectedOrWeakClipCount": len(rejected_or_weak),
        "issues": issues,
    }


def check_row(name: str, passed: bool, evidence: dict[str, Any], blockers: list[str], message: str) -> dict[str, Any]:
    if not passed:
        blockers.append(message)
    return {"name": name, "status": "passed" if passed else "blocked", "evidence": evidence, "message": message}


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, args.blueprint)
    creator_plan = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    creator_audit = load_json(package_dir / "creator_cut_application_contract_audit.json") or {}
    creator_lookup = lookup_rows(plan_rows(creator_plan))
    creator_audit_lookup = lookup_rows(plan_rows(creator_audit))
    chapter_story = load_json(package_dir / "chapter_story_spine_contract_audit.json") or {}
    timeline_variety = load_json(package_dir / "timeline_variety_contract_audit.json") or {}
    pair_continuity = load_json(package_dir / "transition_pair_continuity_contract_audit.json") or {}
    microstructure = load_json(package_dir / "transition_microstructure_contract_audit.json") or {}
    reference_scene = load_json(package_dir / "reference_scene_grammar_contract_audit.json") or {}

    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {
                "blueprint": str(blueprint_path),
                "blueprintExists": blueprint_path.exists(),
                "blueprintKind": blueprint_kind,
                "blueprintInsidePackage": blueprint_inside_package,
            },
            "summary": {},
            "clipRows": [],
            "chapterRows": [],
            "checks": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }

    clips = primary_visual_clips(blueprint)
    annotated = [
        annotate_clip(index, clip, match_row(clip, creator_lookup), match_row(clip, creator_audit_lookup))
        for index, clip in enumerate(clips, start=1)
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in annotated:
        grouped.setdefault(str(row.get("chapterIndex") or "unassigned"), []).append(row)
    chapters = [analyze_chapter(key, rows) for key, rows in sorted(grouped.items(), key=lambda item: chapter_sort_key(item[0]))]
    blocked_chapters = [row for row in chapters if row.get("status") == "blocked"]
    weak_clip_count = sum(1 for row in annotated if row.get("issues"))
    weak_pair_count = sum(as_int(row.get("weakPairCount")) for row in chapters)
    same_beat_run = max((as_int(row.get("sameBeatRunMax")) for row in chapters), default=0)
    same_source_run = max((as_int(row.get("sameSourceRunMax")) for row in chapters), default=0)
    utility_run = max((as_int(row.get("utilityRunMax")) for row in chapters), default=0)

    chapter_story_summary = summary_of(chapter_story)
    timeline_variety_summary = summary_of(timeline_variety)
    pair_summary = summary_of(pair_continuity)
    micro_summary = summary_of(microstructure)
    reference_summary = summary_of(reference_scene)
    blockers: list[str] = []
    checks: list[dict[str, Any]] = []
    checks.append(
        check_row(
            "Final candidate blueprint is available inside the package",
            blueprint_path.exists() and blueprint_inside_package and len(clips) >= 3,
            {
                "blueprint": str(blueprint_path),
                "blueprintKind": blueprint_kind,
                "blueprintExists": blueprint_path.exists(),
                "blueprintInsidePackage": blueprint_inside_package,
                "visualClipCount": len(clips),
            },
            blockers,
            "final candidate blueprint is missing, outside the package, or too small for shot-flow proof",
        )
    )
    checks.append(
        check_row(
            "Upstream chapter, variety, and transition gates are accepted",
            chapter_story.get("status") == "passed"
            and timeline_variety.get("status") == "passed"
            and pair_continuity.get("status") == "passed"
            and microstructure.get("status") == "passed"
            and reference_scene.get("status") == "passed"
            and as_int(chapter_story_summary.get("blockerCount")) == 0
            and as_int(timeline_variety_summary.get("blockedCheckCount")) == 0
            and as_int(pair_summary.get("weakPairCount")) == 0
            and as_int(micro_summary.get("blockedCheckCount")) == 0,
            {
                "chapterStorySpineStatus": chapter_story.get("status"),
                "timelineVarietyStatus": timeline_variety.get("status"),
                "transitionPairContinuityStatus": pair_continuity.get("status"),
                "transitionMicrostructureStatus": microstructure.get("status"),
                "referenceSceneGrammarStatus": reference_scene.get("status"),
                "transitionPairSummary": pair_summary,
                "transitionMicrostructureSummary": micro_summary,
            },
            blockers,
            "upstream chapter, variety, scene, or transition continuity gates are not clean",
        )
    )
    checks.append(
        check_row(
            "Every chapter has ordered movement, texture, payoff, and aftertaste or handoff beats",
            bool(chapters) and not blocked_chapters,
            {"chapterRows": chapters[:80], "blockedChapterCount": len(blocked_chapters)},
            blockers,
            "one or more chapters have random shot order, missing beats, weak clips, or title/effect runs",
        )
    )
    checks.append(
        check_row(
            "Shot adjacency does not hide weak flow behind transitions",
            weak_pair_count == 0 and same_beat_run <= 3 and same_source_run <= 3 and utility_run <= 2,
            {
                "weakFlowPairCount": weak_pair_count,
                "sameBeatRunMax": same_beat_run,
                "sameSourceRunMax": same_source_run,
                "utilityRunMax": utility_run,
            },
            blockers,
            "chapter shot adjacency still has unmotivated jumps or repeated source/beat/utility runs",
        )
    )
    checks.append(
        check_row(
            "Final visual clips remain selective and audience-readable",
            weak_clip_count == 0
            and len(annotated) >= 3
            and as_int(reference_summary.get("chaptersBlocked")) == 0
            and as_int(timeline_variety_summary.get("globalFunctionGroupCount")) >= 4,
            {
                "weakClipCount": weak_clip_count,
                "visualClipCount": len(annotated),
                "referenceSceneSummary": reference_summary,
                "timelineVarietySummary": timeline_variety_summary,
            },
            blockers,
            "active final clips still include weak, utility, reject, unclassified, or under-varied material",
        )
    )

    blockers.extend(
        f"chapter {row.get('chapterIndex')}: {', '.join(row.get('issues') or [])}"
        for row in blocked_chapters[:80]
    )
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "creatorCutStatus": creator_plan.get("status"),
            "creatorCutApplicationStatus": creator_audit.get("status"),
        },
        "summary": {
            "visualClipCount": len(annotated),
            "chapterCount": len(chapters),
            "chaptersPassed": sum(1 for row in chapters if row.get("status") == "passed"),
            "chaptersBlocked": len(blocked_chapters),
            "weakClipCount": weak_clip_count,
            "weakFlowPairCount": weak_pair_count,
            "sameBeatRunMax": same_beat_run,
            "sameSourceRunMax": same_source_run,
            "utilityRunMax": utility_run,
            "chapterStorySpineStatus": chapter_story.get("status"),
            "timelineVarietyStatus": timeline_variety.get("status"),
            "transitionPairContinuityStatus": pair_continuity.get("status"),
            "transitionMicrostructureStatus": microstructure.get("status"),
            "referenceSceneGrammarStatus": reference_scene.get("status"),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": sum(1 for row in checks if row["status"] == "blocked"),
            "blockerCount": len(blockers),
        },
        "clipRows": annotated,
        "chapterRows": chapters,
        "checks": checks,
        "blockers": blockers,
        "warnings": [],
        "policy": {
            "chapterBeatOrder": "context/movement/texture build toward payoff, then aftertaste or handoff",
            "noEffectMaskedRandomJumps": True,
            "noTitleOrUtilityRuns": True,
            "noRejectWeakOrUnclassifiedFinalClips": True,
            "referenceAnchoredButNonCopying": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Shot Flow Continuity Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report.get('inputs', {}).get('blueprint')}`",
        f"Blueprint kind: `{report.get('inputs', {}).get('blueprintKind')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(["", f"### {row.get('name')}", f"- Status: `{row.get('status')}`", f"- Message: {row.get('message')}"])
    lines.extend(["", "## Chapters"])
    for row in report.get("chapterRows") or []:
        lines.extend(
            [
                "",
                f"### Chapter {row.get('chapterIndex')}",
                f"- Status: `{row.get('status')}`",
                f"- Beats: `{', '.join(row.get('beatSequence') or [])}`",
                f"- Issues: `{', '.join(row.get('issues') or []) or 'none'}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit chapter-level shot-flow continuity on the final candidate blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "shot_flow_continuity_contract_audit.json", report)
    write_markdown(package_dir / "shot_flow_continuity_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
