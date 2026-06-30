#!/usr/bin/env python3
"""Run local Tesseract OCR over extracted frames and produce place hints."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PLACE_PATTERNS: list[tuple[str, str, list[str]]] = [
    ("浅草寺雷门", "东京", ["浅草", "淺草", "雷門", "雷门", "asakusa", "sensoji", "senso-ji"]),
    ("东京晴空塔", "东京", ["スカイツリー", "晴空塔", "skytree", "tokyo skytree"]),
    ("东京塔", "东京", ["東京タワー", "东京塔", "東京塔", "tokyo tower"]),
    ("涩谷", "东京", ["渋谷", "涩谷", "shibuya"]),
    ("新宿", "东京", ["新宿", "shinjuku"]),
    ("秋叶原", "东京", ["秋葉原", "秋叶原", "akihabara"]),
    ("银座", "东京", ["銀座", "银座", "ginza"]),
    ("上野", "东京", ["上野", "ueno"]),
    ("东京站", "东京", ["東京駅", "东京站", "tokyo station"]),
    ("羽田机场", "东京", ["羽田", "haneda"]),
    ("成田机场", "东京", ["成田", "narita"]),
    ("道顿堀", "大阪", ["道頓堀", "道顿堀", "dotonbori", "doutonbori"]),
    ("难波", "大阪", ["難波", "なんば", "ナンバ", "难波", "namba"]),
    ("心斋桥", "大阪", ["心斎橋", "心斋桥", "shinsaibashi"]),
    ("梅田", "大阪", ["梅田", "umeda"]),
    ("大阪城", "大阪", ["大阪城", "osaka castle"]),
    ("大阪", "大阪", ["大阪", "osaka"]),
    ("京都站", "京都", ["京都駅", "京都站", "kyoto station"]),
    ("清水寺", "京都", ["清水寺", "kiyomizu"]),
    ("伏见稻荷", "京都", ["伏見稲荷", "伏见稻荷", "fushimi inari"]),
    ("祇园", "京都", ["祇園", "祗园", "gion"]),
    ("京都", "京都", ["京都", "kyoto"]),
    ("东京", "东京", ["東京", "东京", "tokyo"]),
]


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
        if frame.get("sourceVideo"):
            grouped[str(frame["sourceVideo"])].append(frame)
        if frame.get("videoId"):
            grouped[str(frame["videoId"])].append(frame)
    return grouped


def frame_score(frame: dict[str, Any]) -> float:
    score = 0.0
    if frame.get("isOcrCandidate"):
        score += 30.0
    if frame.get("isLocationCandidate"):
        score += 10.0
    score += float(frame.get("clarity") or 0) * 0.35
    score += float(frame.get("edgeDetail") or 0) * 1.6
    return score


def choose_frames(frames: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    ranked = sorted(frames, key=frame_score, reverse=True)
    selected = ranked[:count]
    return sorted(selected, key=lambda item: float(item.get("timestamp") or 0))


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def run_tesseract(image: Path, lang: str, timeout: int) -> tuple[str, str | None]:
    result = subprocess.run(
        ["tesseract", str(image), "stdout", "-l", lang, "--psm", "11"],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    text = clean_text(result.stdout)
    err = clean_text(result.stderr)
    if result.returncode != 0:
        return text, err or f"tesseract exit {result.returncode}"
    return text, None


def detect_places(text: str) -> list[dict[str, Any]]:
    normalized = text.lower()
    hits = []
    for place, city, needles in PLACE_PATTERNS:
        matched = []
        for needle in needles:
            if needle.lower() in normalized:
                matched.append(needle)
        if matched:
            hits.append({"place": place, "city": city, "matchedText": matched})
    return hits


def location_from_hits(row: dict[str, Any], texts: list[dict[str, Any]]) -> dict[str, Any]:
    place_counter: Counter[str] = Counter()
    city_by_place: dict[str, str] = {}
    evidence = []
    for item in texts:
        for hit in item.get("placeHits") or []:
            place_counter[hit["place"]] += len(hit.get("matchedText") or [])
            city_by_place[hit["place"]] = hit["city"]
            evidence.append(
                {
                    "type": "local_tesseract_ocr",
                    "source": "tesseract",
                    "frame": item.get("frame"),
                    "timecode": item.get("timecode"),
                    "matchedText": hit.get("matchedText"),
                    "place": hit["place"],
                }
            )
    if not place_counter:
        return {
            "videoId": row.get("fileId"),
            "videoPath": row.get("path"),
            "videoName": row.get("name"),
            "bestPlace": "unknown",
            "city": "",
            "country": "Japan",
            "confidence": 0.0,
            "confidenceLevel": "unknown",
            "evidence": [],
            "conflictingCandidates": [],
            "needsHumanReview": True,
            "representativeFrames": [item.get("frame") for item in texts if item.get("frame")],
        }
    best, score = place_counter.most_common(1)[0]
    total = sum(place_counter.values())
    confidence = min(0.85, 0.35 + 0.12 * score + 0.08 * (score / max(1, total)))
    level = "high" if confidence >= 0.72 else ("medium" if confidence >= 0.48 else "low")
    alternatives = [
        {"place": place, "city": city_by_place.get(place, ""), "score": count}
        for place, count in place_counter.most_common()
        if place != best
    ]
    return {
        "videoId": row.get("fileId"),
        "videoPath": row.get("path"),
        "videoName": row.get("name"),
        "bestPlace": best,
        "city": city_by_place.get(best, ""),
        "country": "Japan",
        "confidence": round(confidence, 3),
        "confidenceLevel": level,
        "evidence": evidence[:12],
        "conflictingCandidates": alternatives[:8],
        "needsHumanReview": level != "high" or bool(alternatives),
        "representativeFrames": [item.get("frame") for item in texts if item.get("frame")],
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Local Tesseract OCR Recognition",
        "",
        f"Status: `{report['status']}`",
        f"Project: `{report['projectDir']}`",
        f"Language: `{report['language']}`",
        "",
        "## Summary",
        f"- Eligible videos: `{report['summary']['eligibleVideoCount']}`",
        f"- Processed videos: `{report['summary']['processedVideoCount']}`",
        f"- Videos with OCR place hits: `{report['summary']['placeHitVideoCount']}`",
        f"- Confidence: `{report['summary']['confidenceCounts']}`",
        "",
        "## Rows",
        "| File | Place | Confidence | OCR hits | Review |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in report.get("rows") or []:
        loc = row.get("location") or {}
        lines.append(
            f"| `{row.get('videoName')}` | {loc.get('bestPlace')} | "
            f"{loc.get('confidenceLevel')} ({loc.get('confidence')}) | "
            f"{row.get('placeHitCount')} | {loc.get('needsHumanReview')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = Path(args.project_dir).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "local_ocr_recognition" / timestamp
    frame_index = latest_frame_index(project_dir)
    grouped = group_frames(frame_index)
    videos = media_files(project_dir)
    if args.max_videos > 0:
        videos = videos[: args.max_videos]
    rows = []
    for video in videos:
        frames = grouped.get(str(video.get("path"))) or grouped.get(str(video.get("name"))) or []
        selected = choose_frames(frames, args.frames_per_video)
        ocr_items = []
        errors = []
        for frame in selected:
            image = Path(str(frame.get("path") or "")).expanduser()
            if not image.exists():
                continue
            try:
                text, error = run_tesseract(image, args.language, args.timeout_seconds)
            except subprocess.TimeoutExpired:
                text, error = "", "tesseract timeout"
            hits = detect_places(text)
            if error:
                errors.append({"frame": str(image), "error": error[:500]})
            ocr_items.append(
                {
                    "frame": str(image),
                    "timecode": frame.get("timecode"),
                    "timestamp": frame.get("timestamp"),
                    "text": text,
                    "placeHits": hits,
                }
            )
        location = location_from_hits(video, ocr_items)
        rows.append(
            {
                "videoId": video.get("fileId"),
                "videoName": video.get("name"),
                "videoPath": video.get("path"),
                "frameCount": len(selected),
                "ocr": ocr_items,
                "errors": errors,
                "placeHitCount": sum(len(item.get("placeHits") or []) for item in ocr_items),
                "location": location,
            }
        )
    locations = [row["location"] for row in rows]
    levels = Counter(loc.get("confidenceLevel") or "unknown" for loc in locations)
    local_map = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "method": "local_tesseract_ocr",
        "language": args.language,
        "videoCount": len(locations),
        "confirmedCount": 0,
        "highCount": int(levels.get("high") or 0),
        "mediumCount": int(levels.get("medium") or 0),
        "lowCount": int(levels.get("low") or 0),
        "unknownCount": int(levels.get("unknown") or 0),
        "needsHumanReviewCount": sum(1 for loc in locations if loc.get("needsHumanReview")),
        "videos": locations,
    }
    blockers = []
    if not frame_index.get("frames"):
        blockers.append("No frame index found.")
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked" if blockers else "ready",
        "projectDir": str(project_dir),
        "outputDir": str(output_dir),
        "language": args.language,
        "summary": {
            "eligibleVideoCount": len(media_files(project_dir)),
            "processedVideoCount": len(rows),
            "placeHitVideoCount": sum(1 for row in rows if row.get("placeHitCount")),
            "confidenceCounts": dict(levels),
            "framesPerVideo": args.frames_per_video,
        },
        "rows": rows,
        "localLocationMap": local_map,
        "blockers": blockers,
        "warnings": [
            "OCR only recognizes visible text; generic scenery still needs vision/cloud or human review.",
            "Do not overwrite the main location map from OCR-only evidence without review.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "local_tesseract_ocr_recognition.json"
    md_path = output_dir / "local_tesseract_ocr_recognition.md"
    map_path = output_dir / "local_tesseract_video_location_map.json"
    report["json"] = str(json_path)
    report["markdown"] = str(md_path)
    report["localLocationMapPath"] = str(map_path)
    write_json(json_path, report)
    write_json(map_path, local_map)
    write_markdown(md_path, report)
    write_json(
        project_dir / "latest_local_tesseract_ocr_recognition.json",
        {"createdAt": report["createdAt"], "status": report["status"], "report": str(json_path), "markdown": str(md_path)},
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Tesseract OCR over extracted frames.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--language", default="jpn+eng+chi_sim+chi_tra")
    parser.add_argument("--frames-per-video", type=int, default=3)
    parser.add_argument("--max-videos", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Local Tesseract OCR recognition: {report['status']}")
        print(f"Markdown: {report['markdown']}")
        print(f"Videos with OCR place hits: {report['summary']['placeHitVideoCount']}")
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
