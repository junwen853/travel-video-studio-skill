#!/usr/bin/env python3
"""Prepare a raw-footage selection and highlight triage plan before editing."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


HERO_TERMS = (
    "aerial",
    "drone",
    "skyline",
    "tower",
    "castle",
    "temple",
    "shrine",
    "bridge",
    "harbor",
    "coast",
    "sea",
    "ocean",
    "mountain",
    "sunset",
    "night",
    "landmark",
    "establish",
    "title",
    "航拍",
    "天际线",
    "地标",
    "城堡",
    "寺",
    "神社",
    "桥",
    "海",
    "山",
    "夜景",
)

MOVEMENT_TERMS = (
    "airport",
    "station",
    "train",
    "subway",
    "metro",
    "bus",
    "taxi",
    "car",
    "road",
    "window",
    "ferry",
    "boat",
    "plane",
    "walk",
    "walking",
    "escalator",
    "elevator",
    "transfer",
    "route",
    "arrival",
    "departure",
    "机场",
    "车站",
    "火车",
    "地铁",
    "车窗",
    "出租",
    "巴士",
    "轮渡",
    "飞机",
    "步行",
    "抵达",
    "出发",
)

LIVED_IN_TERMS = (
    "street",
    "market",
    "food",
    "restaurant",
    "hotel",
    "room",
    "shop",
    "ticket",
    "sign",
    "map",
    "weather",
    "rain",
    "crowd",
    "luggage",
    "table",
    "coffee",
    "街",
    "市场",
    "饭",
    "餐",
    "酒店",
    "房间",
    "店",
    "票",
    "路牌",
    "地图",
    "天气",
    "雨",
    "人群",
    "行李",
)

WEAK_TERMS = (
    "render",
    "master",
    "final",
    "export",
    "vlog",
    "placeholder",
    "title_cards",
    "black",
    "slate",
    "sample",
    "test",
    "duplicate",
    "obstruct",
    "blur",
    "shaky",
    "dark",
    "成片",
    "终稿",
    "导出",
    "占位",
    "黑屏",
    "模糊",
    "遮挡",
    "重复",
)

DECISION_FIELDS = {
    "approvedUse": "",
    "approvedTier": "",
    "targetDurationSeconds": None,
    "trimStartSeconds": None,
    "trimEndSeconds": None,
    "chapterPlacement": "",
    "useAsOpeningOrEnding": "",
    "useAsBridgeBeforeAfter": "",
    "orientationRepairRequired": "",
    "captionFunction": "",
    "bgmMoodCue": "",
    "resolveImplementation": "",
    "readbackEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
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


def clean_words(value: Any, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def media_date(row: dict[str, Any]) -> str:
    for key in ("date", "captureDate", "createdDate"):
        value = str(row.get(key) or "")
        if re.match(r"20\d\d-\d\d-\d\d", value):
            return value[:10]
    name = str(row.get("name") or row.get("sourceName") or row.get("path") or "")
    match = re.search(r"(20\d{6})", name)
    if match:
        value = match.group(1)
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    value = row.get("metadataTime") or row.get("created") or row.get("modified") or ""
    return str(value)[:10] if value else "unknown"


def first_video_stream(row: dict[str, Any]) -> dict[str, Any]:
    probe = row.get("probe") if isinstance(row.get("probe"), dict) else {}
    streams = probe.get("streams") if isinstance(probe.get("streams"), list) else []
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "video" and stream.get("codec_name") != "mjpeg":
            return stream
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "video":
            return stream
    return {}


def display_orientation(row: dict[str, Any]) -> dict[str, Any]:
    if isinstance(row.get("orientation"), dict):
        orient = dict(row["orientation"])
        orient.setdefault("orientation", "unknown")
        return orient
    stream = first_video_stream(row)
    width = int(as_float(row.get("width") or stream.get("width"), 0) or 0)
    height = int(as_float(row.get("height") or stream.get("height"), 0) or 0)
    tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
    rotate = tags.get("rotate")
    side_data = stream.get("side_data_list") if isinstance(stream.get("side_data_list"), list) else []
    if rotate is None:
        for item in side_data:
            if isinstance(item, dict) and "rotation" in item:
                rotate = item.get("rotation")
                break
    try:
        rotation = int(float(rotate or 0)) % 360
    except (TypeError, ValueError):
        rotation = 0
    display_width, display_height = width, height
    if rotation in {90, 270}:
        display_width, display_height = height, width
    if not display_width or not display_height:
        kind = "unknown"
    elif abs(display_width - display_height) <= 8:
        kind = "square"
    elif display_width > display_height:
        kind = "landscape"
    else:
        kind = "vertical"
    return {
        "width": width,
        "height": height,
        "displayWidth": display_width,
        "displayHeight": display_height,
        "rotation": rotation,
        "orientation": kind,
    }


def frame_rate_value(row: dict[str, Any]) -> float | None:
    value = row.get("fps") or row.get("frameRate") or first_video_stream(row).get("avg_frame_rate")
    if value is None:
        return None
    text = str(value)
    if "/" in text:
        num, den = text.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else None
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def media_duration(row: dict[str, Any]) -> float:
    for key in ("durationSeconds", "duration", "sourceDurationSeconds"):
        value = as_float(row.get(key))
        if value and value > 0:
            return value
    start = as_float(row.get("sourceStartSeconds"), 0.0) or 0.0
    end = as_float(row.get("sourceEndSeconds"), 0.0) or 0.0
    return max(0.0, end - start)


def media_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    path = str(row.get("path") or row.get("sourcePath") or row.get("videoPath") or "")
    name = str(row.get("name") or row.get("sourceName") or (Path(path).name if path else ""))
    file_id = str(row.get("fileId") or row.get("videoId") or row.get("id") or "")
    return path, name, file_id


def media_text(row: dict[str, Any], recognition: dict[str, Any] | None = None) -> str:
    bits = [
        row.get("name"),
        row.get("path"),
        row.get("sourcePath"),
        row.get("role"),
        row.get("purpose"),
        row.get("place"),
        row.get("city"),
    ]
    if recognition:
        bits.extend(
            [
                recognition.get("place"),
                recognition.get("city"),
                recognition.get("confidenceLevel"),
                recognition.get("notes"),
            ]
        )
    return " ".join(str(bit or "") for bit in bits).lower()


def confidence_token(value: Any) -> str:
    text = str(value or "unknown").lower().replace("-", "_")
    if text.startswith("codex_visual_high") or text.startswith("high"):
        return "high"
    if "medium_high" in text:
        return "medium_high"
    if text.startswith("codex_visual_medium") or text.startswith("medium"):
        return "medium"
    if text.startswith("low"):
        return "low"
    if text in {"missing", "unrecognized", "unknown"}:
        return text
    return "unknown"


def latest_recognition_report(project_dir: Path) -> dict[str, Any]:
    pointer = load_json(project_dir / "latest_footage_recognition_route_report.json") or {}
    report_path = pointer.get("report") or pointer.get("path") or pointer.get("json")
    if report_path:
        data = load_json(Path(str(report_path)).expanduser())
        if isinstance(data, dict):
            return data
    reports = sorted((project_dir / "recognition_reports").glob("*/footage_recognition_route_report.json"))
    if reports:
        return load_json(reports[-1]) or {}
    return {}


def recognition_lookup(project_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    report = latest_recognition_report(project_dir)
    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    by_path = {str(row.get("path")): row for row in rows if isinstance(row, dict) and row.get("path")}
    by_id = {str(row.get("fileId")): row for row in rows if isinstance(row, dict) and row.get("fileId")}
    return by_path, by_id, report


def load_frame_counts(project_dir: Path) -> dict[str, int]:
    pointer = load_json(project_dir / "latest_frame_index.json") or {}
    frame_path = None
    if isinstance(pointer.get("files"), dict):
        frame_path = pointer["files"].get("frameIndex")
    frame_path = frame_path or pointer.get("frameIndex")
    frame_index = load_json(Path(str(frame_path)).expanduser()) if frame_path else pointer
    frames = frame_index.get("frames") if isinstance(frame_index, dict) and isinstance(frame_index.get("frames"), list) else []
    counts: dict[str, int] = defaultdict(int)
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for key in ("videoPath", "sourcePath", "path"):
            if frame.get(key):
                counts[str(frame[key])] += 1
        for key in ("videoId", "fileId"):
            if frame.get(key):
                counts[str(frame[key])] += 1
    return counts


def active_exclusions(project_dir: Path) -> tuple[set[str], set[str]]:
    payload = load_json(project_dir / "source_exclusions.json") or {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    paths = {str(item.get("path")) for item in items if isinstance(item, dict) and item.get("active", True) and item.get("path")}
    ids = {str(item.get("fileId")) for item in items if isinstance(item, dict) and item.get("active", True) and item.get("fileId")}
    return paths, ids


def blueprint_rows(package_dir: Path | None) -> list[dict[str, Any]]:
    if not package_dir:
        return []
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        track_type = str(row.get("trackType") or "video").lower()
        text = media_text(row)
        if track_type != "video" or "subtitle_overlay" in text:
            continue
        clone = dict(row)
        if row.get("sourcePath"):
            clone["path"] = row.get("sourcePath")
            clone.setdefault("name", Path(str(row.get("sourcePath"))).name)
        out.append(clone)
    return out


def media_rows(project_dir: Path | None, package_dir: Path | None) -> tuple[list[dict[str, Any]], str]:
    if project_dir:
        media = load_json(project_dir / "media_index.json") or {}
        rows = media.get("files") if isinstance(media.get("files"), list) else []
        videos = [row for row in rows if isinstance(row, dict) and row.get("kind") == "video" and row.get("path")]
        if videos:
            return videos, "media_index"
    fallback = blueprint_rows(package_dir)
    return fallback, "resolve_blueprint_fallback" if fallback else "none"


def score_row(
    row: dict[str, Any],
    recognition: dict[str, Any] | None,
    frame_count: int,
    excluded: bool,
) -> tuple[int, list[str], list[str]]:
    text = media_text(row, recognition)
    duration = media_duration(row)
    orient = display_orientation(row)
    fps = frame_rate_value(row)
    confidence = confidence_token((recognition or {}).get("confidenceLevel") or row.get("confidenceLevel"))
    score = 45
    signals: list[str] = []
    risks: list[str] = []

    if excluded:
        score -= 100
        risks.append("active_source_exclusion")
    if contains_any(text, WEAK_TERMS):
        score -= 35
        risks.append("derived_or_weak_filename_signal")
    if contains_any(text, HERO_TERMS):
        score += 22
        signals.append("high_recognition_place_or_payoff")
    if contains_any(text, MOVEMENT_TERMS):
        score += 16
        signals.append("route_movement")
    if contains_any(text, LIVED_IN_TERMS):
        score += 14
        signals.append("lived_in_texture")

    orientation = str(orient.get("orientation") or "unknown")
    if orientation == "landscape":
        score += 8
        signals.append("landscape_master_ready")
    elif orientation == "vertical":
        score -= 34
        risks.append("vertical_requires_reframe_or_insert_design")
    elif orientation == "square":
        score -= 22
        risks.append("square_requires_reframe_or_insert_design")
    else:
        score -= 18
        risks.append("unknown_orientation")

    display_width = int(orient.get("displayWidth") or 0)
    display_height = int(orient.get("displayHeight") or 0)
    if display_width >= 3200 and display_height >= 1800:
        score += 10
        signals.append("4k_or_near_4k")
    elif display_width >= 1920 and display_height >= 1080:
        score += 5
        signals.append("hd_or_better")
    elif display_width and display_height:
        score -= 12
        risks.append("low_resolution_for_4k_master")

    if fps and fps >= 50:
        score += 4
        signals.append("high_frame_rate_source")
    elif fps and fps < 24:
        score -= 5
        risks.append("low_frame_rate_source")

    if duration < 1.5:
        score -= 25
        risks.append("too_short_to_register")
    elif 3 <= duration <= 45:
        score += 8
        signals.append("good_editable_duration")
    elif duration > 180:
        score -= 10
        risks.append("very_long_raw_take_needs_subselection")
    elif duration > 75:
        score -= 4
        risks.append("long_raw_take_needs_highlight_trim")

    if confidence in {"high", "medium_high"}:
        score += 12
        signals.append("strong_location_signal")
    elif confidence == "medium":
        score += 6
        signals.append("usable_location_signal")
    elif confidence in {"missing", "unrecognized", "low", "unknown"}:
        score -= 10
        risks.append("weak_location_signal")

    if (recognition or {}).get("needsHumanReview"):
        score -= 8
        risks.append("needs_location_human_review")
    if frame_count > 0:
        score += min(6, frame_count)
        signals.append("sampled_frame_evidence")
    if row.get("hasGPS"):
        score += 5
        signals.append("gps_metadata_available")

    return max(0, min(100, score)), signals, risks


def infer_function(text: str, score: int, orientation: str, excluded: bool) -> str:
    if excluded:
        return "reject_excluded_source"
    if orientation in {"vertical", "square", "unknown"} and score < 50:
        return "orientation_repair_review"
    if contains_any(text, MOVEMENT_TERMS):
        return "route_movement_bridge"
    if contains_any(text, LIVED_IN_TERMS):
        return "lived_in_texture"
    if contains_any(text, HERO_TERMS):
        return "destination_payoff_or_title_candidate"
    if score >= 72:
        return "main_story_candidate"
    if score < 38:
        return "reject_or_manual_review"
    return "utility_context"


def tier_for(score: int, function: str, risks: list[str]) -> str:
    if function == "reject_excluded_source":
        return "reject_excluded"
    if "derived_or_weak_filename_signal" in risks:
        return "reject_or_review"
    if function == "orientation_repair_review":
        return "repair_before_use"
    if score >= 82 and function in {"destination_payoff_or_title_candidate", "route_movement_bridge", "main_story_candidate"}:
        return "hero_candidate"
    if score >= 54 and function in {"route_movement_bridge", "lived_in_texture"}:
        return "texture_bridge_candidate"
    if score >= 68:
        return "main_story_candidate"
    if score >= 44:
        return "utility_context"
    return "reject_or_review"


def recommended_use(tier: str, function: str, duration: float, orientation: str) -> dict[str, Any]:
    if tier.startswith("reject"):
        return {
            "use": "exclude_from_first_cut",
            "targetDurationRangeSeconds": [0, 0],
            "reason": "Do not let weak, excluded, duplicate, or derived material enter the first assembly.",
        }
    if tier == "repair_before_use":
        return {
            "use": "repair_orientation_or_design_as_phone_insert_before_use",
            "targetDurationRangeSeconds": [2, 5],
            "reason": f"{orientation} footage cannot enter a 16:9 master as raw full-frame material.",
        }
    if function == "route_movement_bridge":
        return {
            "use": "use_as_route_or_chapter_bridge",
            "targetDurationRangeSeconds": [3, min(9, max(4, round(duration, 1)))],
            "reason": "Movement material is the first-choice glue between places before stock or effects.",
        }
    if function == "lived_in_texture":
        return {
            "use": "use_as_texture_cutaway",
            "targetDurationRangeSeconds": [1.5, min(6, max(2, round(duration, 1)))],
            "reason": "Small real-life details make the route feel traveled instead of generated.",
        }
    if tier == "hero_candidate":
        return {
            "use": "use_for_opening_chapter_payoff_or_ending",
            "targetDurationRangeSeconds": [5, min(12, max(6, round(duration, 1)))],
            "reason": "Strong place identity can carry a title, payoff, or aftertaste moment.",
        }
    if tier == "main_story_candidate":
        return {
            "use": "use_as_main_story_shot",
            "targetDurationRangeSeconds": [3, min(8, max(4, round(duration, 1)))],
            "reason": "Good source, but still trim to a deliberate beat.",
        }
    return {
        "use": "use_only_if_needed_for_context",
        "targetDurationRangeSeconds": [1.5, 4],
        "reason": "Usable but not strong enough to lead the film.",
    }


def build_rows(project_dir: Path | None, package_dir: Path | None, rows: list[dict[str, Any]], input_source: str) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    frame_counts: dict[str, int] = {}
    excluded_paths: set[str] = set()
    excluded_ids: set[str] = set()
    if project_dir:
        by_path, by_id, _report = recognition_lookup(project_dir)
        frame_counts = load_frame_counts(project_dir)
        excluded_paths, excluded_ids = active_exclusions(project_dir)

    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(sorted(rows, key=lambda item: (media_date(item), str(item.get("name") or item.get("path") or ""))), 1):
        path, name, file_id = media_identity(row)
        identity = path or file_id or name
        if identity and identity in seen:
            continue
        seen.add(identity)
        recognition = by_path.get(path) or by_id.get(file_id) or {}
        frame_count = max(frame_counts.get(path, 0), frame_counts.get(file_id, 0))
        excluded = bool(path in excluded_paths or file_id in excluded_ids)
        score, signals, risks = score_row(row, recognition, frame_count, excluded)
        text = media_text(row, recognition)
        orient = display_orientation(row)
        orientation = str(orient.get("orientation") or "unknown")
        function = infer_function(text, score, orientation, excluded)
        tier = tier_for(score, function, risks)
        duration = media_duration(row)
        row_status = "ready_for_first_cut_selection"
        if tier in {"reject_or_review", "repair_before_use"} or risks:
            row_status = "needs_editor_or_repair_decision"
        if tier == "reject_excluded":
            row_status = "excluded_from_first_cut"
        output.append(
            {
                "rowIndex": index,
                "inputSource": input_source,
                "fileId": file_id,
                "sourcePath": path,
                "sourceName": name,
                "date": media_date(row),
                "durationSeconds": round(duration, 3),
                "fps": round(frame_rate_value(row), 3) if frame_rate_value(row) else None,
                "orientation": orient,
                "place": recognition.get("place") or row.get("place") or "unknown",
                "city": recognition.get("city") or row.get("city") or "",
                "confidenceLevel": recognition.get("confidenceLevel") or row.get("confidenceLevel") or "unknown",
                "needsHumanReview": bool(recognition.get("needsHumanReview")),
                "frameEvidenceCount": frame_count,
                "selectionScore": score,
                "selectionTier": tier,
                "creatorFunction": function,
                "signals": signals,
                "riskReasons": risks,
                "recommendedUse": recommended_use(tier, function, duration, orientation),
                "status": row_status,
                "decision": dict(DECISION_FIELDS),
            }
        )
    return output


def build_chapter_rows(selection_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selection_rows:
        place = str(row.get("place") or "unknown")
        date = str(row.get("date") or "unknown")
        grouped[f"{date} | {place}"].append(row)
    chapter_rows: list[dict[str, Any]] = []
    for index, (key, rows) in enumerate(sorted(grouped.items()), 1):
        tier_counts = Counter(str(row.get("selectionTier") or "") for row in rows)
        function_counts = Counter(str(row.get("creatorFunction") or "") for row in rows)
        candidate_rows = [
            row
            for row in rows
            if row.get("selectionTier") in {"hero_candidate", "main_story_candidate", "texture_bridge_candidate"}
        ]
        has_bridge = any(row.get("creatorFunction") == "route_movement_bridge" for row in rows)
        has_lived = any(row.get("creatorFunction") == "lived_in_texture" for row in rows)
        has_payoff = any(row.get("creatorFunction") == "destination_payoff_or_title_candidate" for row in rows)
        missing = []
        if not has_bridge:
            missing.append("route_movement_bridge")
        if not has_lived:
            missing.append("lived_in_texture")
        if not has_payoff:
            missing.append("destination_payoff_or_title_candidate")
        chapter_rows.append(
            {
                "chapterIndex": index,
                "chapterKey": key,
                "sourceVideoCount": len(rows),
                "candidateVideoCount": len(candidate_rows),
                "heroCandidateCount": tier_counts.get("hero_candidate", 0),
                "textureBridgeCandidateCount": tier_counts.get("texture_bridge_candidate", 0),
                "repairOrRejectCount": tier_counts.get("repair_before_use", 0)
                + tier_counts.get("reject_or_review", 0)
                + tier_counts.get("reject_excluded", 0),
                "tierCounts": dict(tier_counts),
                "functionCounts": dict(function_counts),
                "missingCoverageFunctions": missing,
                "recommendedPattern": [
                    "start with one readable place identity",
                    "connect with route movement",
                    "add lived-in detail",
                    "pay off with the strongest view/activity",
                    "leave with bridge or aftertaste footage",
                ],
                "status": "needs_more_selective_coverage" if missing or not candidate_rows else "has_selectable_chapter_pool",
                "decision": {
                    "approvedChapterPool": "",
                    "heroRows": [],
                    "mainRows": [],
                    "bridgeRows": [],
                    "rejectRows": [],
                    "repairRows": [],
                    "resolveImplementation": "",
                    "readbackEvidence": "",
                    "approvedBy": "",
                    "approvedAt": "",
                    "editorNotes": "",
                },
            }
        )
    return chapter_rows


def build_plan(project_dir: Path | None, package_dir: Path | None, output_dir: Path) -> dict[str, Any]:
    rows, input_source = media_rows(project_dir, package_dir)
    selection_rows = build_rows(project_dir, package_dir, rows, input_source)
    chapter_rows = build_chapter_rows(selection_rows)
    tier_counts = Counter(str(row.get("selectionTier") or "") for row in selection_rows)
    function_counts = Counter(str(row.get("creatorFunction") or "") for row in selection_rows)
    scores = [int(row.get("selectionScore") or 0) for row in selection_rows]
    decision_fields = set(DECISION_FIELDS)
    rows_with_decision_fields = sum(
        1 for row in selection_rows if isinstance(row.get("decision"), dict) and decision_fields.issubset(set(row["decision"]))
    )
    ready_candidates = tier_counts.get("hero_candidate", 0) + tier_counts.get("main_story_candidate", 0) + tier_counts.get(
        "texture_bridge_candidate", 0
    )
    repair_or_reject = tier_counts.get("repair_before_use", 0) + tier_counts.get("reject_or_review", 0) + tier_counts.get(
        "reject_excluded", 0
    )
    recognition_report = latest_recognition_report(project_dir) if project_dir else {}
    status = "blocked_missing_media_index_or_blueprint"
    if selection_rows and input_source == "media_index":
        status = "ready_with_footage_select_plan"
    elif selection_rows:
        status = "ready_with_blueprint_fallback_footage_select_plan"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "projectDir": str(project_dir) if project_dir else None,
        "packageDir": str(package_dir) if package_dir else None,
        "outputDir": str(output_dir),
        "inputs": {
            "mediaIndex": str(project_dir / "media_index.json") if project_dir else None,
            "recognitionReportStatus": recognition_report.get("status"),
            "recognitionReport": recognition_report.get("outputDir") or recognition_report.get("projectDir"),
            "resolveBlueprintFallback": str(package_dir / "resolve_timeline_blueprint.json") if package_dir else None,
            "inputSource": input_source,
        },
        "summary": {
            "inputSource": input_source,
            "sourceVideoCount": len(selection_rows),
            "candidateVideoCount": ready_candidates,
            "heroCandidateCount": tier_counts.get("hero_candidate", 0),
            "mainStoryCandidateCount": tier_counts.get("main_story_candidate", 0),
            "textureBridgeCandidateCount": tier_counts.get("texture_bridge_candidate", 0),
            "utilityContextCount": tier_counts.get("utility_context", 0),
            "repairOrRejectCount": repair_or_reject,
            "orientationRepairCandidateCount": tier_counts.get("repair_before_use", 0),
            "derivedOrExcludedRejectCount": tier_counts.get("reject_excluded", 0),
            "rowsWithDecisionFields": rows_with_decision_fields,
            "chapterRowCount": len(chapter_rows),
            "chaptersNeedingCoverage": sum(1 for row in chapter_rows if row.get("status") == "needs_more_selective_coverage"),
            "averageSelectionScore": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "medianSelectionScore": round(statistics.median(scores), 3) if scores else 0.0,
            "tierCounts": dict(tier_counts),
            "functionCounts": dict(function_counts),
        },
        "policy": {
            "rawFootageSelectionBeforeAssembly": True,
            "selectiveShotChoiceRequired": True,
            "derivedExportsRejected": True,
            "orientationRepairBeforeUse": True,
            "localFootageFirstForBridges": True,
            "chapterVarietyRequiredBeforeEffects": True,
            "doesNotModifySourceFootage": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
        "chapterRows": chapter_rows,
        "selectionRows": selection_rows,
        "selectionRubric": {
            "pass": [
                "The first assembly prefers hero, main story, and texture bridge candidates instead of raw folder order.",
                "Derived exports, duplicates, weak files, and excluded sources are rejected before editing.",
                "Vertical, square, or unknown-orientation clips are marked for repair/design before they can enter a 16:9 master.",
                "Every chapter pool exposes missing movement, lived-in, and payoff coverage before effects or stock are used.",
                "Local bridge footage is selected before stock/aerial fallback or flashy transitions.",
            ],
            "reject": [
                "A 100GB source folder is cut by filename order without scoring or chapter-pool coverage.",
                "Prior rendered exports or final masters re-enter the raw source set.",
                "Vertical phone clips enter the 16:9 master without a repair/design decision.",
                "Weak footage is kept and hidden with transition effects instead of being demoted or rejected.",
            ],
        },
        "nextActions": [
            "Use hero_candidate rows for opening, chapter payoff, and ending before searching stock footage.",
            "Use route_movement_bridge and lived_in_texture rows to support transitions and avoid hard day/place jumps.",
            "Reject or repair every repair_before_use and reject_or_review row before Resolve apply.",
            "After build_delivery_package.py runs, confirm the package copied this plan and sorted chapter media by selection score.",
        ],
        "safety": {
            "modifiesSourceFootage": False,
            "writesResolve": False,
            "downloadsExternalAssets": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Footage Select Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Project: `{plan.get('projectDir')}`",
        f"Package: `{plan.get('packageDir')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Chapter Pools",
    ]
    for row in plan["chapterRows"]:
        lines.extend(
            [
                "",
                f"### {row['chapterKey']}",
                f"- Status: `{row['status']}`",
                f"- Source videos: `{row['sourceVideoCount']}`",
                f"- Candidates: `{row['candidateVideoCount']}`",
                f"- Hero: `{row['heroCandidateCount']}`",
                f"- Texture bridge: `{row['textureBridgeCandidateCount']}`",
                f"- Missing functions: `{', '.join(row['missingCoverageFunctions']) if row['missingCoverageFunctions'] else 'none'}`",
            ]
        )
    top = sorted(plan["selectionRows"], key=lambda row: int(row.get("selectionScore") or 0), reverse=True)
    lines.extend(["", "## Top Candidate Rows"])
    for row in top[:40]:
        if row.get("selectionTier") not in {"hero_candidate", "main_story_candidate", "texture_bridge_candidate"}:
            continue
        use = row.get("recommendedUse") if isinstance(row.get("recommendedUse"), dict) else {}
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['selectionTier']} / {row['creatorFunction']}",
                f"- Score: `{row['selectionScore']}`",
                f"- Source: `{row.get('sourceName')}`",
                f"- Place: `{row.get('place')}`",
                f"- Duration: `{row.get('durationSeconds')}`",
                f"- Use: `{use.get('use')}`",
            ]
        )
    review_rows = [row for row in plan["selectionRows"] if row.get("status") != "ready_for_first_cut_selection"]
    lines.extend(["", "## Repair Or Reject Rows"])
    if not review_rows:
        lines.append("- None.")
    for row in review_rows[:80]:
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['selectionTier']}",
                f"- Source: `{row.get('sourceName')}`",
                f"- Score: `{row.get('selectionScore')}`",
                f"- Risks: `{', '.join(row.get('riskReasons') or [])}`",
                "- Decision fields to fill:",
            ]
        )
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_dirs(args: argparse.Namespace) -> tuple[Path | None, Path | None, Path]:
    project_dir = Path(args.project_dir).expanduser().resolve() if args.project_dir else None
    package_dir = Path(args.package_dir).expanduser().resolve() if args.package_dir else None
    if not project_dir and package_dir:
        delivery = load_json(package_dir / "delivery_plan.json") or {}
        if delivery.get("projectDir"):
            project_dir = Path(str(delivery["projectDir"])).expanduser().resolve()
    if not project_dir and not package_dir:
        raise SystemExit("Provide --project-dir, --package-dir, or both.")
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    elif package_dir:
        output_dir = package_dir / "footage_select_plan"
    else:
        output_dir = project_dir / "footage_select_plan"  # type: ignore[operator]
    return project_dir, package_dir, output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a raw-footage selection plan before travel-video assembly.")
    parser.add_argument("--project-dir", help="VideoClaw project directory containing media_index.json.")
    parser.add_argument("--package-dir", help="Optional delivery package for blueprint fallback or package-local output.")
    parser.add_argument("--output-dir", help="Defaults to <package>/footage_select_plan or <project>/footage_select_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir, package_dir, output_dir = resolve_dirs(args)
    plan = build_plan(project_dir, package_dir, output_dir)
    write_json(output_dir / "footage_select_plan.json", plan)
    write_markdown(output_dir / "footage_select_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 2 if plan["status"] == "blocked_missing_media_index_or_blueprint" else 0


if __name__ == "__main__":
    raise SystemExit(main())
