#!/usr/bin/env python3
"""Build and optionally apply a confirmed route from Codex visual review notes."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def media_date(row: dict[str, Any]) -> str:
    name = str(row.get("name") or row.get("path") or "")
    match = re.search(r"(20\d{6})", name)
    if match:
        value = match.group(1)
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    value = row.get("metadataTime") or row.get("created") or row.get("modified") or ""
    return str(value)[:10] if value else "unknown"


def confidence_token(value: Any) -> str:
    text = str(value or "unknown").strip().lower().replace("-", "_")
    if text.startswith("high"):
        return "high"
    if text.startswith("medium_high"):
        return "medium_high"
    if text.startswith("medium"):
        return "medium"
    if text.startswith("low"):
        return "low"
    return "unknown"


def confidence_score(token: str) -> float:
    return {"high": 0.82, "medium_high": 0.68, "medium": 0.56, "low": 0.35}.get(token, 0.4)


def active_exclusions(project_dir: Path) -> tuple[set[str], set[str], list[dict[str, Any]]]:
    payload = load_json(project_dir / "source_exclusions.json") or {}
    items = [item for item in payload.get("items") or [] if item.get("active", True)]
    paths = {str(item.get("path")) for item in items if item.get("path")}
    ids = {str(item.get("fileId")) for item in items if item.get("fileId")}
    return paths, ids, items


def latest_codex_visual_report(project_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    for pointer_name in ("latest_codex_visual_route_review.json", "latest_codex_visual_review.json"):
        pointer = load_json(project_dir / pointer_name) or {}
        for key in ("path", "report", "json"):
            if pointer.get(key):
                path = Path(str(pointer[key])).expanduser()
                report = load_json(path)
                if report:
                    return path, report
    candidates = sorted(project_dir.glob("codex_visual_review/*/codex_visual_review.json"))
    if candidates:
        return candidates[-1], load_json(candidates[-1]) or {}
    return None, {}


def sampled_frames_for_date(codex_visual: dict[str, Any], date: str) -> list[str]:
    for day in codex_visual.get("days") or []:
        if str(day.get("date")) != date:
            continue
        frames: list[str] = []
        for video in day.get("videos") or []:
            for frame in video.get("sampledFrames") or []:
                if len(frames) < 8:
                    frames.append(str(frame))
        return frames
    return []


def infer_country(project_dir: Path, day: dict[str, Any]) -> str:
    explicit = str(day.get("country") or day.get("region") or "").strip()
    if explicit:
        return explicit
    project = load_json(project_dir / "project.json") or {}
    text = " ".join(
        str(project.get(key) or "")
        for key in ("title", "subtitle", "destination", "places", "routeText")
    ).lower()
    day_text = " ".join(str(day.get(key) or "") for key in ("city", "routeNode", "chapterTitle")).lower()
    combined = text + " " + day_text
    if any(token in combined for token in ("香港", "港澳", "hong kong", "澳门", "macau", "macao")):
        return "Hong Kong/Macau"
    if any(token in combined for token in ("日本", "tokyo", "osaka", "京都", "japan")):
        return "Japan"
    return ""


def day_selected_rows(day: dict[str, Any], by_date: dict[str, list[dict[str, Any]]], files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = {str(item) for item in day.get("videoNames") or []}
    ids = {str(item) for item in day.get("videoIds") or day.get("videos") or []}
    paths = {str(item) for item in day.get("videoPaths") or []}
    if names or ids or paths:
        return [
            row
            for row in files
            if str(row.get("name")) in names
            or str(row.get("fileId")) in ids
            or str(row.get("path")) in paths
        ]
    date = str(day.get("date") or "")
    return by_date.get(date, [])


def sampled_frames_for_day(codex_visual: dict[str, Any], day: dict[str, Any]) -> list[str]:
    frames = [str(item) for item in day.get("representativeFrames") or day.get("sampledFrames") or []]
    if frames:
        return frames[:8]
    return sampled_frames_for_date(codex_visual, str(day.get("date") or ""))


def build_candidate(project_dir: Path) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    media = load_json(project_dir / "media_index.json") or {}
    source_paths, source_ids, exclusion_items = active_exclusions(project_dir)
    codex_path, codex_visual = latest_codex_visual_report(project_dir)
    codex_route = codex_visual.get("codexVisualRoute") or {}
    days = codex_route.get("days") or []
    blockers: list[str] = []
    warnings: list[str] = []
    if not media:
        blockers.append("media_index.json is missing.")
    if not codex_visual:
        blockers.append("Latest Codex visual review is missing.")
    if codex_visual.get("status") not in {"ready", "ready_with_warnings", "ready_with_caveats"}:
        blockers.append(f"Codex visual review is not ready: {codex_visual.get('status')}.")
    if codex_route.get("provider") != "codex_visual_inspection":
        blockers.append("Codex visual route provider is not codex_visual_inspection.")
    if codex_route.get("localModelUsed") is not False:
        blockers.append("Codex visual route must not depend on a local model for this workflow.")
    if not days:
        blockers.append("Codex visual route has no day chapters.")

    files = [
        row
        for row in media.get("files") or []
        if row.get("kind") == "video" and str(row.get("path")) not in source_paths and str(row.get("fileId")) not in source_ids
    ]
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(files, key=lambda item: (media_date(item), str(item.get("name") or ""))):
        by_date.setdefault(media_date(row), []).append(row)

    expected_count = int(codex_route.get("sourceVideoCoverage") or codex_visual.get("sourceVideoCount") or 0)
    if expected_count and len(files) != expected_count:
        blockers.append(f"Active source count {len(files)} does not match Codex visual coverage {expected_count}.")

    chapters: list[dict[str, Any]] = []
    uncovered_keys = {str(row.get("fileId") or row.get("path") or row.get("name")) for row in files}
    assigned_keys: set[str] = set()
    for index, day in enumerate(days, start=1):
        date = str(day.get("date") or "")
        rows = day_selected_rows(day, by_date, files)
        if not rows:
            warnings.append(f"No active source videos matched Codex visual chapter {index} ({date}).")
        token = confidence_token(day.get("confidence"))
        videos = [str(row.get("fileId")) for row in rows if row.get("fileId")]
        video_paths = [str(row.get("path")) for row in rows if row.get("path")]
        video_names = [str(row.get("name")) for row in rows if row.get("name")]
        row_keys = {str(row.get("fileId") or row.get("path") or row.get("name")) for row in rows}
        duplicate_keys = sorted(row_keys & assigned_keys)
        if duplicate_keys:
            warnings.append(f"Codex visual chapter {index} reuses {len(duplicate_keys)} source videos already assigned to an earlier chapter.")
        assigned_keys.update(row_keys)
        uncovered_keys.difference_update(row_keys)
        duration = round(sum(float(row.get("duration") or 0) for row in rows), 3)
        chapters.append(
            {
                "index": index,
                "chapter": day.get("chapterTitle") or day.get("routeNode") or f"Day {index}",
                "originalChapter": day.get("chapterTitle"),
                "place": day.get("routeNode") or day.get("chapterTitle") or "",
                "originalPlace": day.get("routeNode") or day.get("chapterTitle") or "",
                "city": day.get("city") or "",
                "country": infer_country(project_dir, day),
                "date": date,
                "timeRange": date,
                "confidence": confidence_score(token),
                "confidenceLevel": f"codex_visual_{token}",
                "videos": videos,
                "videoPaths": video_paths,
                "videoNames": video_names,
                "durationSeconds": duration,
                "representativeFrames": sampled_frames_for_day(codex_visual, day),
                "evidence": [{"type": "codex_visual_contact_sheet", "detail": item} for item in day.get("visualEvidence") or []],
                "userModifiedPlace": "",
                "userNotes": day.get("editUse") or "Confirmed from Codex visual review with route-honesty caveats.",
                "markedUnimportant": False,
                "markedDoNotCut": False,
                "needsHumanReview": False,
                "reviewDecision": "codex_visual_confirmed",
                "confirmedAt": now,
            }
        )
    if uncovered_keys:
        blockers.append(f"Active source videos not represented in Codex visual route: {len(uncovered_keys)} missing.")

    route = {
        "createdAt": now,
        "projectDir": str(project_dir),
        "mode": "codex_visual_confirmed_route",
        "sourceCodexVisualReview": str(codex_path) if codex_path else None,
        "sourceVideoCount": len(files),
        "excludedSourceCount": len(exclusion_items),
        "chapterCount": len(chapters),
        "needsHumanReviewCount": 0,
        "routeSummary": codex_route.get("routeSummary"),
        "routeConfidence": codex_route.get("routeConfidence"),
        "recommended20MinuteChapterPlan": codex_route.get("recommended20MinuteChapterPlan") or [],
        "chapters": chapters,
        "notes": [
            "Generated from Codex direct visual inspection, not local 7B/Ollama and not cloud API.",
            "No GPS metadata exists; exact place names remain conservative unless supported by visible evidence.",
            "Active source exclusions are not included in route chapters.",
        ],
    }
    status = "ready_to_apply" if not blockers and chapters else "blocked"
    return {
        "createdAt": now,
        "status": status,
        "canApply": status == "ready_to_apply",
        "projectDir": str(project_dir),
        "candidate": route,
        "blockers": blockers,
        "warnings": warnings,
        "sourceExclusions": exclusion_items,
    }


def write_markdown(path: Path, candidate: dict[str, Any]) -> None:
    route = candidate["candidate"]
    lines = [
        "# Codex Visual Confirmed Route Candidate",
        "",
        f"Status: `{candidate['status']}`",
        f"Can apply: `{candidate['canApply']}`",
        f"Source videos: `{route['sourceVideoCount']}`",
        f"Excluded sources: `{route['excludedSourceCount']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in candidate["blockers"] or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in candidate["warnings"] or ["None"])
    lines.extend(["", "## Chapters"])
    for chapter in route.get("chapters") or []:
        lines.append(
            f"- {chapter['index']}. `{chapter['date']}` `{chapter['chapter']}` "
            f"videos={len(chapter.get('videos') or [])} confidence={chapter.get('confidenceLevel')}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_candidate(candidate: dict[str, Any], project_dir: Path) -> None:
    if not candidate.get("canApply"):
        raise SystemExit("Candidate is not ready to apply: " + "; ".join(candidate.get("blockers") or []))
    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    confirmed_path = project_dir / "confirmed_route_timeline.json"
    if confirmed_path.exists():
        backup_path = project_dir / "route_backups" / f"confirmed_route_timeline_{now_tag}.json"
        write_json(backup_path, load_json(confirmed_path) or {})
        candidate["backupConfirmedRoute"] = str(backup_path)
    write_json(confirmed_path, candidate["candidate"])
    write_json(project_dir / "latest_confirmed_route.json", {"files": {"confirmedRoute": str(confirmed_path)}, "createdAt": candidate["createdAt"]})
    candidate["applied"] = True
    candidate["appliedConfirmedRoute"] = str(confirmed_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare/apply a confirmed route from the latest Codex visual review.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "route_review" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = build_candidate(project_dir)
    candidate_path = output_dir / "codex_visual_confirmed_route_candidate.json"
    markdown_path = output_dir / "codex_visual_confirmed_route_candidate.md"
    candidate["candidateJson"] = str(candidate_path)
    candidate["candidateMarkdown"] = str(markdown_path)
    if args.apply:
        apply_candidate(candidate, project_dir)
    write_json(candidate_path, candidate)
    write_markdown(markdown_path, candidate)
    write_json(
        project_dir / "latest_confirmed_route_candidate.json",
        {"candidate": str(candidate_path), "createdAt": candidate["createdAt"], "status": candidate["status"]},
    )
    if args.json:
        print(json.dumps(candidate, ensure_ascii=False, indent=2))
    else:
        print(f"Codex visual confirmed route candidate: {candidate['status']}")
        print(f"Candidate JSON: {candidate_path}")
        print(f"Candidate Markdown: {markdown_path}")
        if candidate.get("applied"):
            print(f"Applied confirmed route: {candidate['appliedConfirmedRoute']}")
            if candidate.get("backupConfirmedRoute"):
                print(f"Backup confirmed route: {candidate['backupConfirmedRoute']}")
        for blocker in candidate.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if candidate.get("canApply") else 2


if __name__ == "__main__":
    raise SystemExit(main())
