#!/usr/bin/env python3
"""Discover likely external travel media roots without modifying source drives."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mts", ".mxf", ".avi", ".insv"}
DEFAULT_TERMS = [
    "2025",
    "日本",
    "东京",
    "大阪",
    "japan",
    "tokyo",
    "osaka",
    "ac4",
    "dji",
    "港澳",
    "香港",
    "澳门",
    "hong",
    "macau",
    "macao",
]


def safe_scandir(path: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(path) as entries:
            return list(entries)
    except OSError:
        return []


def video_file_info(path: Path) -> dict[str, Any] | None:
    if path.name.startswith("._") or path.suffix.lower() not in VIDEO_EXTS:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return {"path": str(path), "sizeBytes": stat.st_size}


def direct_video_summary(path: Path, sample_limit: int) -> dict[str, Any]:
    count = 0
    size = 0
    samples: list[str] = []
    apple_double_count = 0
    for entry in safe_scandir(path):
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
        except OSError:
            continue
        file_path = Path(entry.path)
        if file_path.name.startswith("._") and file_path.suffix.lower() in VIDEO_EXTS:
            apple_double_count += 1
            continue
        info = video_file_info(file_path)
        if not info:
            continue
        count += 1
        size += int(info["sizeBytes"])
        if len(samples) < sample_limit:
            samples.append(str(file_path))
    return {
        "directVideoCount": count,
        "directVideoSizeBytes": size,
        "directVideoSizeGB": round(size / 1024 / 1024 / 1024, 3),
        "sampleVideos": samples,
        "ignoredAppleDoubleVideoCount": apple_double_count,
    }


def matched_terms(path: Path, terms: list[str]) -> list[str]:
    text = str(path).lower()
    return [term for term in terms if term.lower() in text]


def discover(volume_root: Path, max_depth: int, min_videos: int, sample_limit: int, terms: list[str]) -> dict[str, Any]:
    volumes = []
    if volume_root == Path("/Volumes"):
        roots = [p for p in sorted(volume_root.iterdir(), key=lambda x: x.name.lower()) if p.name != "Macintosh HD"]
    else:
        roots = [volume_root]
    candidates = []
    stack: list[tuple[Path, int, str]] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        volumes.append(str(root))
        stack.append((root, 0, root.name))
    while stack:
        path, depth, volume_name = stack.pop()
        summary = direct_video_summary(path, sample_limit)
        terms_found = matched_terms(path, terms)
        if summary["directVideoCount"] >= min_videos or terms_found:
            candidates.append(
                {
                    "path": str(path),
                    "volume": volume_name,
                    "depth": depth,
                    "matchedTerms": terms_found,
                    **summary,
                }
            )
        if depth >= max_depth:
            continue
        for entry in safe_scandir(path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append((Path(entry.path), depth + 1, volume_name))
            except OSError:
                continue
    candidates.sort(
        key=lambda row: (
            -int(row["directVideoCount"]),
            -int(row["directVideoSizeBytes"]),
            str(row["path"]).lower(),
        )
    )
    likely = [row for row in candidates if row["directVideoCount"] >= min_videos and row["matchedTerms"]]
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "volumeRoot": str(volume_root),
        "maxDepth": max_depth,
        "minVideos": min_videos,
        "volumes": volumes,
        "candidateCount": len(candidates),
        "likelyTravelRootCount": len(likely),
        "likelyTravelRoots": likely[:50],
        "candidates": candidates[:200],
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"External media discovery: {report['volumeRoot']}")
    print(f"Volumes: {', '.join(report['volumes']) or '<none>'}")
    print(f"Likely travel roots: {report['likelyTravelRootCount']}")
    for row in report["likelyTravelRoots"][:20]:
        print(
            f"- {row['directVideoCount']:4d} videos, "
            f"{row['directVideoSizeGB']:8.2f} GB, "
            f"terms={row['matchedTerms']}: {row['path']}"
        )
        for sample in row["sampleVideos"][:3]:
            print(f"  sample: {sample}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover likely external travel media roots.")
    parser.add_argument("--volume-root", default="/Volumes", help="Volume root or a single mounted drive path.")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--min-videos", type=int, default=1)
    parser.add_argument("--sample-limit", type=int, default=6)
    parser.add_argument("--term", action="append", help="Extra keyword to flag likely travel roots.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    terms = DEFAULT_TERMS + (args.term or [])
    report = discover(Path(args.volume_root).expanduser().resolve(), args.max_depth, args.min_videos, args.sample_limit, terms)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0 if report["likelyTravelRootCount"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
