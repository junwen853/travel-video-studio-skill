#!/usr/bin/env python3
"""Run a local Ollama vision model over extracted travel footage frames."""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def latest_frame_index(project_dir: Path) -> dict[str, Any]:
    pointer = load_json(project_dir / "latest_frame_index.json") or {}
    frame_path = None
    if isinstance(pointer.get("files"), dict):
        frame_path = pointer["files"].get("frameIndex")
    frame_path = frame_path or pointer.get("frameIndex")
    if frame_path:
        return load_json(Path(frame_path).expanduser()) or pointer
    return pointer


def active_exclusions(project_dir: Path) -> tuple[set[str], set[str]]:
    payload = load_json(project_dir / "source_exclusions.json") or {}
    items = [item for item in payload.get("items") or [] if item.get("active", True)]
    return (
        {str(item.get("path")) for item in items if item.get("path")},
        {str(item.get("fileId")) for item in items if item.get("fileId")},
    )


def media_files(project_dir: Path) -> list[dict[str, Any]]:
    media = load_json(project_dir / "media_index.json") or {}
    excluded_paths, excluded_ids = active_exclusions(project_dir)
    rows = []
    for row in media.get("files") or []:
        if row.get("kind") != "video":
            continue
        if str(row.get("path")) in excluded_paths or str(row.get("fileId")) in excluded_ids:
            continue
        rows.append(row)
    return sorted(rows, key=lambda item: (str(item.get("created") or item.get("modified") or ""), str(item.get("name") or "")))


def group_frames(frame_index: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for frame in frame_index.get("frames") or []:
        source = str(frame.get("sourceVideo") or "")
        video_id = str(frame.get("videoId") or "")
        if source:
            grouped[source].append(frame)
        if video_id:
            grouped[video_id].append(frame)
    return grouped


def frame_score(frame: dict[str, Any]) -> float:
    score = 0.0
    if frame.get("isLocationCandidate"):
        score += 20.0
    if frame.get("isOcrCandidate"):
        score += 12.0
    if frame.get("hasFaceCandidate"):
        score -= 5.0
    score += float(frame.get("clarity") or 0) * 0.4
    score += float(frame.get("edgeDetail") or 0) * 1.5
    score += float(frame.get("colorfulness") or 0) * 0.2
    dark = float(frame.get("darkPct") or 0)
    bright = float(frame.get("brightPct") or 0)
    if dark > 0.55 or bright > 0.55:
        score -= 20.0
    return score


def choose_frames(frames: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if not frames or count <= 0:
        return []
    ranked = sorted(frames, key=frame_score, reverse=True)
    selected: list[dict[str, Any]] = []
    used_times: list[float] = []
    for frame in ranked:
        timestamp = float(frame.get("timestamp") or 0)
        if any(abs(timestamp - used) < 8 for used in used_times) and len(ranked) > count:
            continue
        selected.append(frame)
        used_times.append(timestamp)
        if len(selected) >= count:
            return sorted(selected, key=lambda item: float(item.get("timestamp") or 0))
    return sorted(ranked[:count], key=lambda item: float(item.get("timestamp") or 0))


def image_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def ollama_generate(host: str, model: str, prompt: str, image_paths: list[Path], timeout: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64(path) for path in image_paths],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_ctx": 8192},
    }
    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        data = json.loads(response.read().decode("utf-8"))
    return str(data.get("response") or "")


def parse_json_response(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def confidence_level(confidence: float) -> str:
    if confidence >= 0.72:
        return "high"
    if confidence >= 0.48:
        return "medium"
    if confidence > 0:
        return "low"
    return "unknown"


def normalize_result(raw: dict[str, Any], row: dict[str, Any], frames: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        confidence = float(raw.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    level = str(raw.get("confidenceLevel") or confidence_level(confidence)).lower()
    if level not in {"high", "medium", "low", "unknown"}:
        level = confidence_level(confidence)
    best_place = str(raw.get("bestPlace") or raw.get("place") or "").strip() or "unknown"
    city = str(raw.get("city") or "").strip()
    country = str(raw.get("country") or "").strip() or "Japan"
    landmarks = raw.get("landmarks") if isinstance(raw.get("landmarks"), list) else []
    scene_cues = raw.get("sceneCues") if isinstance(raw.get("sceneCues"), list) else []
    needs_review = bool(raw.get("needsHumanReview")) or level in {"low", "unknown"} or best_place == "unknown"
    return {
        "videoId": row.get("fileId"),
        "videoPath": row.get("path"),
        "videoName": row.get("name"),
        "bestPlace": best_place,
        "city": city,
        "country": country,
        "confidence": round(confidence, 3),
        "confidenceLevel": level,
        "evidence": [
            {
                "type": "local_ollama_vision",
                "source": "ollama",
                "modelReason": str(raw.get("reason") or raw.get("rationale") or "")[:500],
                "landmarks": [str(item)[:120] for item in landmarks[:8]],
                "sceneCues": [str(item)[:120] for item in scene_cues[:8]],
                "frameCount": len(frames),
            }
        ],
        "conflictingCandidates": raw.get("alternativePlaces") if isinstance(raw.get("alternativePlaces"), list) else [],
        "needsHumanReview": needs_review,
        "representativeFrames": [frame.get("path") for frame in frames if frame.get("path")],
    }


def prompt_for_video(row: dict[str, Any], route_hint: str) -> str:
    return f"""
You are identifying filming locations from still frames of one travel video.
Video file: {row.get("name")}
Created date: {str(row.get("created") or row.get("modified") or "")[:10]}
Trip hint: {route_hint}

Return JSON only with this exact shape:
{{
  "bestPlace": "specific landmark, neighborhood, transit hub, or broad city; use unknown if not visible",
  "city": "city if visible or strongly supported",
  "country": "Japan",
  "confidence": 0.0,
  "confidenceLevel": "high|medium|low|unknown",
  "needsHumanReview": true,
  "landmarks": ["visible landmark/signage/architecture"],
  "sceneCues": ["visual evidence"],
  "alternativePlaces": [],
  "reason": "short evidence-based explanation"
}}

Rules:
- Do not use the folder name alone as evidence.
- Prefer visible landmarks, signs, station names, skyline features, road signs, menus, or storefront text.
- If the frames only show generic streets, vehicles, food, hotel rooms, airports, or interiors, keep confidence low.
- If Tokyo/Osaka/Kyoto cannot be distinguished from the frames, use bestPlace="unknown" and confidence <= 0.35.
""".strip()


def build_local_map(report: dict[str, Any]) -> dict[str, Any]:
    videos = [row["location"] for row in report.get("rows") or [] if row.get("status") == "recognized"]
    levels = Counter(row.get("confidenceLevel") or "unknown" for row in videos)
    return {
        "createdAt": report["createdAt"],
        "method": "local_ollama_vision",
        "model": report["model"],
        "videoCount": len(videos),
        "confirmedCount": 0,
        "highCount": int(levels.get("high") or 0),
        "mediumCount": int(levels.get("medium") or 0),
        "lowCount": int(levels.get("low") or 0),
        "unknownCount": int(levels.get("unknown") or 0),
        "needsHumanReviewCount": sum(1 for row in videos if row.get("needsHumanReview")),
        "videos": videos,
    }


def merge_location_map(project_dir: Path, local_map: dict[str, Any], timestamp: str, min_confidence: float) -> Path:
    path = project_dir / "video_location_map.json"
    current = load_json(path) or {"videos": []}
    backup = project_dir / f"video_location_map.before_local_ollama_{timestamp}.json"
    if path.exists():
        shutil.copy2(path, backup)
    by_id = {str(row.get("videoId")): dict(row) for row in current.get("videos") or [] if row.get("videoId")}
    for local in local_map.get("videos") or []:
        if float(local.get("confidence") or 0) < min_confidence:
            continue
        key = str(local.get("videoId"))
        existing = by_id.get(key, {})
        existing_confidence = float(existing.get("confidence") or 0)
        if local.get("confidenceLevel") == "high" or float(local.get("confidence") or 0) >= existing_confidence:
            by_id[key] = local
    videos = list(by_id.values())
    levels = Counter(row.get("confidenceLevel") or "unknown" for row in videos)
    merged = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "method": "merged_local_ollama_vision",
        "backup": str(backup) if backup.exists() else None,
        "videoCount": len(videos),
        "confirmedCount": 0,
        "highCount": int(levels.get("high") or 0),
        "mediumCount": int(levels.get("medium") or 0),
        "lowCount": int(levels.get("low") or 0),
        "unknownCount": int(levels.get("unknown") or 0),
        "needsHumanReviewCount": sum(1 for row in videos if row.get("needsHumanReview")),
        "videos": videos,
    }
    write_json(path, merged)
    return backup


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Local Ollama Vision Recognition",
        "",
        f"Status: `{report['status']}`",
        f"Model: `{report['model']}`",
        f"Project: `{report['projectDir']}`",
        "",
        "## Summary",
        f"- Eligible videos: `{report['summary']['eligibleVideoCount']}`",
        f"- Processed videos: `{report['summary']['processedVideoCount']}`",
        f"- Recognized videos: `{report['summary']['recognizedVideoCount']}`",
        f"- Errors: `{report['summary']['errorCount']}`",
        f"- Confidence: `{report['summary']['confidenceCounts']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.extend(["", "## Rows"])
    lines.append("| File | Place | Confidence | Review | Frames |")
    lines.append("| --- | --- | --- | --- | ---: |")
    for row in report.get("rows") or []:
        location = row.get("location") or {}
        lines.append(
            f"| `{row.get('videoName')}` | {location.get('bestPlace') or row.get('status')} | "
            f"{location.get('confidenceLevel')} ({location.get('confidence')}) | "
            f"{location.get('needsHumanReview')} | {len(row.get('frames') or [])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = Path(args.project_dir).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "local_vision_recognition" / timestamp
    frame_index = latest_frame_index(project_dir)
    grouped = group_frames(frame_index)
    videos = media_files(project_dir)
    if args.max_videos > 0:
        videos = videos[: args.max_videos]
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not frame_index.get("frames"):
        blockers.append("No extracted frames found. Run the route pipeline/frame extraction first.")
    processed = 0
    for video in videos:
        frames = grouped.get(str(video.get("path"))) or grouped.get(str(video.get("name"))) or []
        selected = choose_frames(frames, args.frames_per_video)
        row = {
            "videoId": video.get("fileId"),
            "videoName": video.get("name"),
            "videoPath": video.get("path"),
            "frames": [frame.get("path") for frame in selected if frame.get("path")],
            "status": "pending",
        }
        image_paths = [Path(str(frame.get("path"))).expanduser() for frame in selected if frame.get("path")]
        image_paths = [path for path in image_paths if path.exists()]
        if not image_paths:
            row["status"] = "no_frames"
            row["error"] = "No representative frame files exist for this video."
            rows.append(row)
            continue
        try:
            response = ollama_generate(
                args.ollama_host,
                args.model,
                prompt_for_video(video, args.route_hint),
                image_paths,
                args.timeout_seconds,
            )
            raw = parse_json_response(response)
            if not raw:
                row["status"] = "error"
                row["error"] = f"Model did not return parseable JSON: {response[:500]}"
            else:
                row["status"] = "recognized"
                row["location"] = normalize_result(raw, video, selected)
                processed += 1
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            row["status"] = "error"
            row["error"] = str(exc)
        rows.append(row)

    recognized = [row for row in rows if row.get("status") == "recognized"]
    errors = [row for row in rows if row.get("status") == "error"]
    confidence_counts = Counter((row.get("location") or {}).get("confidenceLevel") or "unknown" for row in recognized)
    if errors:
        blockers.append(f"{len(errors)} videos failed local Ollama recognition.")
    if not recognized:
        blockers.append("Local Ollama vision did not recognize any videos.")
    local_map = build_local_map(
        {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "model": args.model,
            "rows": rows,
        }
    )
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked" if blockers else "ready",
        "projectDir": str(project_dir),
        "outputDir": str(output_dir),
        "model": args.model,
        "ollamaHost": args.ollama_host,
        "routeHint": args.route_hint,
        "summary": {
            "eligibleVideoCount": len(media_files(project_dir)),
            "requestedVideoCount": len(videos),
            "processedVideoCount": processed,
            "recognizedVideoCount": len(recognized),
            "errorCount": len(errors),
            "confidenceCounts": dict(confidence_counts),
            "framesPerVideo": args.frames_per_video,
        },
        "rows": rows,
        "localLocationMap": local_map,
        "blockers": blockers,
        "warnings": [
            "Local vision recognition is evidence, not GPS truth. Keep low-confidence rows in human review.",
            "Cloud vision should still run when Mimo/OpenAI API credentials are available.",
        ],
    }
    if args.update_project_location_map:
        if len(recognized) < len(videos) and not args.allow_partial_update:
            report["status"] = "blocked"
            report["blockers"].append("Refusing to update video_location_map.json from a partial local recognition run.")
        else:
            backup = merge_location_map(project_dir, local_map, timestamp, args.min_update_confidence)
            report["projectLocationMapUpdated"] = True
            report["projectLocationMapBackup"] = str(backup) if backup.exists() else None
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "local_ollama_vision_recognition.json"
    md_path = output_dir / "local_ollama_vision_recognition.md"
    local_map_path = output_dir / "local_ollama_video_location_map.json"
    report["json"] = str(json_path)
    report["markdown"] = str(md_path)
    report["localLocationMapPath"] = str(local_map_path)
    write_json(json_path, report)
    write_json(local_map_path, local_map)
    write_markdown(md_path, report)
    write_json(
        project_dir / "latest_local_ollama_vision_recognition.json",
        {"createdAt": report["createdAt"], "status": report["status"], "report": str(json_path), "markdown": str(md_path)},
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Ollama vision recognition over extracted footage frames.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--model", default="qwen2.5vl:7b")
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--route-hint", default="Japan trip, likely Tokyo, Osaka, and Kyoto. Use visual evidence only.")
    parser.add_argument("--frames-per-video", type=int, default=3)
    parser.add_argument("--max-videos", type=int, default=0, help="0 means all eligible source videos.")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--update-project-location-map", action="store_true")
    parser.add_argument("--allow-partial-update", action="store_true")
    parser.add_argument("--min-update-confidence", type=float, default=0.48)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Local Ollama vision recognition: {report['status']}")
        print(f"Markdown: {report['markdown']}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
