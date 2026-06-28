#!/usr/bin/env python3
"""Summarize VideoClaw Studio location and route artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import default_app_dir, discover_project_path


DEFAULT_APP_DIR = default_app_dir()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


def latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def discover_project(path: Path, project_name: str | None) -> Path:
    return discover_project_path(path, project_name)


def artifact(project_dir: Path, name: str) -> tuple[Path | None, Any]:
    path = latest(list(project_dir.glob(name)))
    return path, load_json(path) if path else None


def confidence_summary(video_map: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(video_map, dict):
        return {}
    videos = video_map.get("videos", [])
    levels = Counter(v.get("confidenceLevel", "unknown") for v in videos if isinstance(v, dict))
    places = Counter()
    review = []
    for video in videos:
        if not isinstance(video, dict):
            continue
        place = video.get("bestPlace") or "unknown"
        places[place] += 1
        if video.get("needsHumanReview") or place == "unknown":
            review.append(
                {
                    "videoName": video.get("videoName") or Path(video.get("videoPath", "")).name,
                    "bestPlace": place,
                    "confidence": video.get("confidence"),
                    "confidenceLevel": video.get("confidenceLevel"),
                }
            )
    return {
        "videoCount": video_map.get("videoCount", len(videos)),
        "confidenceLevels": dict(levels),
        "topPlaces": places.most_common(10),
        "needsHumanReview": review[:25],
    }


def route_summary(route: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(route, dict):
        return {}
    chapters = route.get("chapters", [])
    compact = []
    for idx, chapter in enumerate(chapters, 1):
        if not isinstance(chapter, dict):
            continue
        compact.append(
            {
                "index": idx,
                "chapter": chapter.get("chapter"),
                "place": chapter.get("place"),
                "city": chapter.get("city"),
                "confidence": chapter.get("confidence"),
                "videoCount": len(chapter.get("videos", []) or []),
                "isTransit": bool(chapter.get("isTransit")),
                "needsHumanReview": bool(chapter.get("needsHumanReview")),
                "markedDoNotCut": bool(chapter.get("markedDoNotCut")),
            }
        )
    return {
        "chapterCount": route.get("chapterCount", len(chapters)),
        "needsHumanReviewCount": route.get("needsHumanReviewCount"),
        "transitChapterCount": route.get("transitChapterCount"),
        "chapters": compact,
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = discover_project(Path(args.project_dir), args.project_name)
    video_map_path, video_map = artifact(project_dir, "video_location_map.json")
    route_path, route = artifact(project_dir, "route_timeline.json")
    confirmed_path, confirmed = artifact(project_dir, "confirmed_route_timeline.json")
    pipeline_path, pipeline = artifact(project_dir, "latest_location_route_pipeline.json")

    ready_for_cut = False
    confirmed_is_stale = False
    if video_map_path and route_path and confirmed_path:
        ready_for_cut = confirmed_path.stat().st_mtime >= route_path.stat().st_mtime
        confirmed_is_stale = not ready_for_cut

    if isinstance(confirmed, dict) and not confirmed_is_stale:
        route_source = confirmed
        route_label = "confirmed_route_timeline.json"
    else:
        route_source = route
        route_label = "route_timeline.json"

    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "projectDir": str(project_dir),
        "artifacts": {
            "videoLocationMap": str(video_map_path) if video_map_path else None,
            "routeTimeline": str(route_path) if route_path else None,
            "confirmedRoute": str(confirmed_path) if confirmed_path else None,
            "pipeline": str(pipeline_path) if pipeline_path else None,
        },
        "pipeline": {
            "dryRun": pipeline.get("dryRun") if isinstance(pipeline, dict) else None,
            "allowCloudCall": pipeline.get("allowCloudCall") if isinstance(pipeline, dict) else None,
            "cloudProviderUsed": pipeline.get("cloudProviderUsed") if isinstance(pipeline, dict) else None,
            "localModelUsed": pipeline.get("localModelUsed") if isinstance(pipeline, dict) else None,
        },
        "videoLocationSummary": confidence_summary(video_map),
        "routeSource": route_label,
        "confirmedRouteStale": confirmed_is_stale,
        "routeSummary": route_summary(route_source),
        "readyForRouteAwareCut": ready_for_cut,
    }


def print_human(summary: dict[str, Any]) -> None:
    print("Route recognition summary")
    print(f"Project: {summary['projectDir']}")
    print(f"Route source: {summary['routeSource']}")
    if summary.get("confirmedRouteStale"):
        print("Confirmed route: stale, using route_timeline.json for summary")
    print(f"Ready for route-aware cut: {summary['readyForRouteAwareCut']}")
    pipeline = summary["pipeline"]
    print(
        "Pipeline: "
        f"dryRun={pipeline.get('dryRun')}, allowCloudCall={pipeline.get('allowCloudCall')}, "
        f"cloud={pipeline.get('cloudProviderUsed')}, local={pipeline.get('localModelUsed')}"
    )
    loc = summary["videoLocationSummary"]
    if loc:
        print()
        print(f"Videos: {loc.get('videoCount')}, confidence={loc.get('confidenceLevels')}")
        print("Top places:")
        for place, count in loc.get("topPlaces", []):
            print(f"  - {place}: {count}")
        if loc.get("needsHumanReview"):
            print("Needs review:")
            for item in loc["needsHumanReview"][:10]:
                print(
                    f"  - {item.get('videoName')}: {item.get('bestPlace')} "
                    f"({item.get('confidenceLevel')}, {item.get('confidence')})"
                )
    route = summary["routeSummary"]
    if route:
        print()
        print(f"Chapters: {route.get('chapterCount')}")
        for chapter in route.get("chapters", []):
            flags = []
            if chapter.get("isTransit"):
                flags.append("transit")
            if chapter.get("needsHumanReview"):
                flags.append("review")
            if chapter.get("markedDoNotCut"):
                flags.append("do-not-cut")
            flag_text = f" [{' '.join(flags)}]" if flags else ""
            print(
                f"  {chapter['index']:02d}. {chapter.get('place') or chapter.get('chapter')} "
                f"- videos={chapter.get('videoCount')}, confidence={chapter.get('confidence')}{flag_text}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize VideoClaw route/location results.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app root or project directory.")
    parser.add_argument("--project-name", help="Project folder name under app_root/projects.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    summary = build_summary(args)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_human(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
