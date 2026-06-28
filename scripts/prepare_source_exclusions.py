#!/usr/bin/env python3
"""Detect prior renders/derived videos and write a source exclusion list."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import discover_project_path


DERIVED_TOKENS = ("vlog", "render", "master", "highbitrate", "final", "export", "成片", "终稿", "成稿")


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detect_derived(media_index: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in media_index.get("files") or []:
        if item.get("kind") != "video":
            continue
        name = str(item.get("name") or Path(str(item.get("path") or "")).name)
        lower = name.lower()
        matched = [token for token in DERIVED_TOKENS if token in lower or token in name]
        if matched:
            rows.append(
                {
                    "fileId": item.get("fileId"),
                    "name": name,
                    "path": item.get("path"),
                    "active": True,
                    "reason": "detected_prior_render_or_derived_export",
                    "matchedTokens": matched,
                    "doNotCut": True,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare source_exclusions.json for derived/prior-render media.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--project-name")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = discover_project_path(Path(args.project_dir).expanduser(), args.project_name)
    media_index = load_json(project_dir / "media_index.json") or {}
    rows = detect_derived(media_index)
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "ready",
        "projectDir": str(project_dir),
        "items": rows,
        "summary": {"detected": len(rows), "active": sum(1 for row in rows if row.get("active"))},
        "rule": "Active exclusions must not be used as raw footage in route scaffolds, delivery packages, or final timelines.",
    }
    out = project_dir / "source_exclusions.json"
    write_json(out, report)
    write_json(project_dir / "latest_source_exclusions.json", {"createdAt": report["createdAt"], "status": report["status"], "sourceExclusions": str(out)})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Source exclusions: {len(rows)} active")
        print(f"File: {out}")
        for row in rows:
            print(f"- {row['name']}: {row['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
