#!/usr/bin/env python3
"""Audit whether the final cut has reference-like scene-flow arcs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PRIMARY_BEATS = ("context", "movement", "texture", "payoff", "aftertaste")
UTILITY_BEATS = {"title", "transition", "effect", "utility", "unclassified"}
REPORT_SPECS = {
    "chapterStorySpine": ("chapter_story_spine_contract_audit.json", {"passed"}),
    "shotFlowContinuity": ("shot_flow_continuity_contract_audit.json", {"passed"}),
    "timelineVariety": ("timeline_variety_contract_audit.json", {"passed"}),
    "referenceSceneGrammar": ("reference_scene_grammar_contract_audit.json", {"passed"}),
    "transitionSceneArc": ("transition_scene_arc_contract_audit.json", {"passed"}),
    "transitionBreathingRoom": ("transition_breathing_room_contract_audit.json", {"passed"}),
}

TERM_BEATS = {
    "context": (
        "context",
        "opening",
        "chapter",
        "city",
        "place",
        "promise",
        "people",
        "face",
        "reaction",
        "vlog",
        "title_bridge",
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
        "departure",
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
        "crowd",
        "night",
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
        "route echo",
    ),
}
TITLE_TERMS = ("title", "opening_city", "chapter_title", "ending_city", "subtitle_overlay")
WEAK_TERMS = ("black", "placeholder", "slate", "generic", "test", "sample", "duplicate", "obstruct", "blur")
FUNCTION_BEATS = {
    "opening_hook": "context",
    "route_observation": "context",
    "title_bridge": "context",
    "route_movement": "movement",
    "transport_motion": "movement",
    "route_transition": "movement",
    "lived_in_detail": "texture",
    "street_texture": "texture",
    "destination_payoff": "payoff",
    "landmark_payoff": "payoff",
    "scenic_breathing": "payoff",
    "ending_aftertaste": "aftertaste",
    "aftertaste": "aftertaste",
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


def as_float(value: Any, default: float | None = 0.0) -> float | None:
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
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


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


def classify_beat(clip: dict[str, Any]) -> tuple[str, list[str]]:
    text = clip_text(clip)
    groups: set[str] = set()
    function = str(clip.get("creatorFunction") or "")
    if function in FUNCTION_BEATS:
        groups.add(FUNCTION_BEATS[function])
    if any(term in text for term in TITLE_TERMS) and "scenic" not in text and "bridge" not in text:
        return "title", sorted(groups or {"context"})
    if "transition" in text or "bridge" in text or "motion" in text:
        groups.add("movement")
    for beat, terms in TERM_BEATS.items():
        if any(term in text for term in terms):
            groups.add(beat)
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


def run_length(values: list[str], target: str | None = None) -> int:
    best = 0
    current_value = ""
    current = 0
    for value in values:
        active = value == target if target else value == current_value
        if active:
            current += 1
        else:
            current_value = value
            current = 1
            if target and value != target:
                current = 0
        best = max(best, current)
    return best


def annotate_clip(index: int, clip: dict[str, Any]) -> dict[str, Any]:
    beat, groups = classify_beat(clip)
    text = clip_text(clip)
    issues: list[str] = []
    if beat == "unclassified":
        issues.append("clip_has_no_scene_flow_role")
    if any(term in text for term in WEAK_TERMS):
        issues.append("weak_or_placeholder_clip")
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
        "issues": issues,
    }


def window_rows(primary_rows: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    if len(primary_rows) < size:
        return []
    out: list[dict[str, Any]] = []
    for start in range(0, len(primary_rows) - size + 1):
        rows = primary_rows[start : start + size]
        beats = [str(row.get("beat") or "") for row in rows]
        issues: list[str] = []
        if len(set(beats)) < 3:
            issues.append("window_lacks_three_beat_variety")
        if run_length(beats, "payoff") > 2:
            issues.append("window_is_landmark_payoff_stack")
        if "texture" not in beats and "movement" not in beats:
            issues.append("window_lacks_route_reality_or_lived_texture")
        if beats[0] == "payoff" and "movement" not in beats[:3] and "texture" not in beats[:3]:
            issues.append("window_opens_on_payoff_without_grounding")
        out.append(
            {
                "windowIndex": start + 1,
                "startClipIndex": rows[0].get("clipIndex"),
                "endClipIndex": rows[-1].get("clipIndex"),
                "beatSequence": beats,
                "status": "passed" if not issues else "blocked",
                "issues": issues,
            }
        )
    return out


def analyze_chapter(chapter_index: str, rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    rows = sorted(rows, key=lambda item: (float(item.get("timelineStartSeconds") or 0.0), int(item.get("clipIndex") or 0)))
    primary_rows = [row for row in rows if row.get("beat") in PRIMARY_BEATS]
    beats = [str(row.get("beat") or "") for row in primary_rows]
    groups = sorted({beat for row in rows for beat in row.get("beatGroups", []) if beat in PRIMARY_BEATS})
    issues: list[str] = []
    if len(rows) < args.min_chapter_clips:
        issues.append("chapter_has_too_few_visual_clips_for_scene_flow")
    if len(primary_rows) < args.min_primary_beats:
        issues.append("chapter_has_too_few_primary_scene_beats")
    for beat in ("movement", "texture", "payoff"):
        if beat not in beats and beat not in groups:
            issues.append(f"chapter_missing_{beat}_beat")
    if len(rows) >= 4 and "aftertaste" not in beats and "aftertaste" not in groups:
        issues.append("chapter_missing_aftertaste_or_handoff_beat")
    if beats and beats[0] == "payoff" and not ({"movement", "texture"} & set(beats[:3])):
        issues.append("chapter_opens_with_payoff_without_route_grounding")
    if beats and beats[-1] == "context" and "aftertaste" not in beats[-3:] and len(rows) >= 4:
        issues.append("chapter_ends_on_context_without_aftertaste_or_handoff")
    if run_length(beats) > args.max_same_beat_run:
        issues.append(f"same_scene_beat_run_too_long:{run_length(beats)}")
    if run_length(beats, "payoff") > args.max_payoff_run:
        issues.append(f"payoff_run_too_long:{run_length(beats, 'payoff')}")
    weak_rows = [row for row in rows if row.get("issues")]
    if weak_rows:
        issues.append("chapter_contains_weak_or_unclassified_scene_flow_clip")
    windows = window_rows(primary_rows, args.window_size)
    blocked_windows = [row for row in windows if row.get("status") == "blocked"]
    if blocked_windows:
        issues.append("chapter_has_blocked_scene_flow_windows")
    return {
        "chapterIndex": chapter_index,
        "status": "passed" if not issues else "blocked",
        "clipCount": len(rows),
        "primaryBeatCount": len(primary_rows),
        "beatSequence": beats,
        "beatGroups": groups,
        "windowCount": len(windows),
        "blockedWindowCount": len(blocked_windows),
        "blockedWindows": blocked_windows[: args.max_blocked_rows_in_report],
        "sameBeatRunMax": run_length(beats),
        "payoffRunMax": run_length(beats, "payoff"),
        "weakOrUnclassifiedClipCount": len(weak_rows),
        "issues": issues,
    }


def chapter_handoffs(chapters: list[dict[str, Any]], grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for left, right in zip(chapters, chapters[1:]):
        left_rows = grouped.get(str(left.get("chapterIndex")), [])
        right_rows = grouped.get(str(right.get("chapterIndex")), [])
        left_beats = [str(row.get("beat") or "") for row in left_rows if row.get("beat") in PRIMARY_BEATS]
        right_beats = [str(row.get("beat") or "") for row in right_rows if row.get("beat") in PRIMARY_BEATS]
        left_tail = left_beats[-3:]
        right_head = right_beats[:3]
        issues: list[str] = []
        if "aftertaste" not in left_tail and not ({"movement", "texture"} & set(left_tail)):
            issues.append("outgoing_chapter_lacks_aftertaste_or_route_texture")
        if not ({"context", "movement", "texture"} & set(right_head)):
            issues.append("incoming_chapter_lacks_grounding_before_payoff")
        if left_tail and right_head and left_tail[-1] == "payoff" and right_head[0] == "payoff":
            issues.append("chapter_boundary_is_payoff_to_payoff_jump")
        out.append(
            {
                "fromChapter": left.get("chapterIndex"),
                "toChapter": right.get("chapterIndex"),
                "outgoingTail": left_tail,
                "incomingHead": right_head,
                "status": "passed" if not issues else "blocked",
                "issues": issues,
            }
        )
    return out


def load_reports(package_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, (relative, accepted) in REPORT_SPECS.items():
        path = package_dir / relative
        data = load_json(path) or {}
        out[name] = {
            "path": str(path),
            "exists": path.exists(),
            "status": data.get("status"),
            "acceptedStatuses": sorted(accepted),
            "accepted": data.get("status") in accepted,
            "summary": summary_of(data),
            "blockers": data.get("blockers") or [],
            "warnings": data.get("warnings") or [],
        }
    return out


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: dict[str, Any]) -> None:
    checks.append({"name": name, "status": "passed" if passed else "blocked", "evidence": evidence})


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint, blueprint_path, blueprint_kind, blueprint_inside_package = choose_blueprint(package_dir, args.blueprint)
    reports = load_reports(package_dir)
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
            "handoffRows": [],
            "checks": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }

    clips = primary_visual_clips(blueprint)
    annotated = [annotate_clip(index, clip) for index, clip in enumerate(clips, start=1)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in annotated:
        grouped.setdefault(str(row.get("chapterIndex") or "unassigned"), []).append(row)
    chapters = [analyze_chapter(key, rows, args) for key, rows in sorted(grouped.items(), key=lambda item: chapter_sort_key(item[0]))]
    handoffs = chapter_handoffs(chapters, grouped)
    blocked_chapters = [row for row in chapters if row.get("status") == "blocked"]
    blocked_handoffs = [row for row in handoffs if row.get("status") == "blocked"]
    blocked_windows = sum(as_int(row.get("blockedWindowCount")) for row in chapters)
    weak_clip_count = sum(as_int(row.get("weakOrUnclassifiedClipCount")) for row in chapters)
    same_beat_run = max((as_int(row.get("sameBeatRunMax")) for row in chapters), default=0)
    payoff_run = max((as_int(row.get("payoffRunMax")) for row in chapters), default=0)
    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "Final candidate blueprint is inside the package and has enough visual clips for scene-flow proof",
        blueprint_path.exists() and blueprint_inside_package and len(clips) >= args.min_total_visual_clips,
        {
            "blueprint": str(blueprint_path),
            "blueprintKind": blueprint_kind,
            "blueprintExists": blueprint_path.exists(),
            "blueprintInsidePackage": blueprint_inside_package,
            "visualClipCount": len(clips),
            "minTotalVisualClips": args.min_total_visual_clips,
        },
    )
    add_check(
        checks,
        "Upstream story, variety, reference, transition, and breathing-room reports are accepted",
        all(row["exists"] and row["accepted"] for row in reports.values()),
        {
            name: {
                "exists": row["exists"],
                "status": row["status"],
                "acceptedStatuses": row["acceptedStatuses"],
                "blockerCount": len(row["blockers"]),
            }
            for name, row in reports.items()
        },
    )
    add_check(
        checks,
        "Each chapter forms a readable travel arc instead of a landmark/effect montage",
        bool(chapters) and not blocked_chapters,
        {
            "chapterCount": len(chapters),
            "blockedChapterCount": len(blocked_chapters),
            "blockedChapters": blocked_chapters[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Sliding scene-flow windows contain movement, texture, or context between payoffs",
        blocked_windows == 0 and same_beat_run <= args.max_same_beat_run and payoff_run <= args.max_payoff_run,
        {
            "blockedWindowCount": blocked_windows,
            "sameBeatRunMax": same_beat_run,
            "maxSameBeatRun": args.max_same_beat_run,
            "payoffRunMax": payoff_run,
            "maxPayoffRun": args.max_payoff_run,
        },
    )
    add_check(
        checks,
        "Chapter handoffs have route texture or aftertaste before the next destination claim",
        not blocked_handoffs,
        {
            "handoffCount": len(handoffs),
            "blockedHandoffCount": len(blocked_handoffs),
            "blockedHandoffs": blocked_handoffs[: args.max_blocked_rows_in_report],
        },
    )
    add_check(
        checks,
        "Scene flow does not rely on weak, placeholder, or unclassified clips",
        weak_clip_count == 0,
        {"weakOrUnclassifiedClipCount": weak_clip_count},
    )

    blocked_checks = [row for row in checks if row["status"] == "blocked"]
    chapter_blockers = [
        f"chapter {row.get('chapterIndex')}: {', '.join(row.get('issues') or [])}"
        for row in blocked_chapters
    ]
    handoff_blockers = [
        f"handoff {row.get('fromChapter')}->{row.get('toChapter')}: {', '.join(row.get('issues') or [])}"
        for row in blocked_handoffs
    ]
    blockers = [row["name"] for row in blocked_checks] + chapter_blockers[: args.max_blocked_rows_in_report] + handoff_blockers[: args.max_blocked_rows_in_report]
    warnings = [warning for report in reports.values() for warning in report["warnings"]]
    summary = {
        "visualClipCount": len(clips),
        "chapterCount": len(chapters),
        "chaptersPassed": len(chapters) - len(blocked_chapters),
        "chaptersBlocked": len(blocked_chapters),
        "handoffCount": len(handoffs),
        "blockedHandoffCount": len(blocked_handoffs),
        "blockedWindowCount": blocked_windows,
        "weakOrUnclassifiedClipCount": weak_clip_count,
        "sameBeatRunMax": same_beat_run,
        "payoffRunMax": payoff_run,
        "chapterStorySpineStatus": reports["chapterStorySpine"]["status"],
        "shotFlowContinuityStatus": reports["shotFlowContinuity"]["status"],
        "timelineVarietyStatus": reports["timelineVariety"]["status"],
        "referenceSceneGrammarStatus": reports["referenceSceneGrammar"]["status"],
        "transitionSceneArcStatus": reports["transitionSceneArc"]["status"],
        "transitionBreathingRoomStatus": reports["transitionBreathingRoom"]["status"],
        "passedCheckCount": len(checks) - len(blocked_checks),
        "blockedCheckCount": len(blocked_checks),
        "blockerCount": len(blockers),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if not blockers else "blocked",
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "blueprintInsidePackage": blueprint_inside_package,
            "windowSize": args.window_size,
            "minChapterClips": args.min_chapter_clips,
            "minPrimaryBeats": args.min_primary_beats,
        },
        "summary": summary,
        "clipRows": annotated,
        "chapterRows": chapters,
        "handoffRows": handoffs,
        "checks": checks,
        "reports": reports,
        "blockers": blockers,
        "warnings": warnings,
        "policy": {
            "requiresSceneFlowArc": True,
            "blocksLandmarkOnlyMontage": True,
            "blocksPayoffToPayoffHandoffs": True,
            "requiresMovementTexturePayoff": True,
            "requiresAftertasteOrHandoff": True,
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Scene Flow Arc Contract Audit",
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
    lines.extend(["", "## Chapters"])
    for row in report.get("chapterRows") or []:
        lines.extend(
            [
                "",
                f"### Chapter {row.get('chapterIndex')}",
                f"- Status: `{row.get('status')}`",
                f"- Sequence: `{', '.join(row.get('beatSequence') or [])}`",
                f"- Blocked windows: `{row.get('blockedWindowCount')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(["", f"### {row.get('name')}", f"- Status: `{row.get('status')}`"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit scene-flow arcs for reference-like travel editing.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--min-total-visual-clips", type=int, default=5)
    parser.add_argument("--min-chapter-clips", type=int, default=3)
    parser.add_argument("--min-primary-beats", type=int, default=3)
    parser.add_argument("--max-same-beat-run", type=int, default=3)
    parser.add_argument("--max-payoff-run", type=int, default=2)
    parser.add_argument("--max-blocked-rows-in-report", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "scene_flow_arc_contract_audit.json", report)
    write_markdown(package_dir / "scene_flow_arc_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
