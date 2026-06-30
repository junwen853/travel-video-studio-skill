#!/usr/bin/env python3
"""Read back and audit the current or named DaVinci Resolve timeline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from resolve_common import get_resolve


def item_name(item: Any) -> str:
    for method in ("GetName",):
        try:
            value = getattr(item, method)()
            if value:
                return str(value)
        except Exception:  # noqa: BLE001
            pass
    try:
        props = item.GetProperty()
        if isinstance(props, dict):
            return str(props.get("Name") or props.get("Clip Name") or "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def item_range(item: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"name": item_name(item)}
    for key, method in {
        "start": "GetStart",
        "end": "GetEnd",
        "duration": "GetDuration",
        "leftOffset": "GetLeftOffset",
        "rightOffset": "GetRightOffset",
    }.items():
        try:
            out[key] = getattr(item, method)()
        except Exception:  # noqa: BLE001
            out[key] = None
    try:
        out["track"] = item.GetTrackTypeAndIndex()
    except Exception:  # noqa: BLE001
        out["track"] = None
    return out


def find_timeline(project: Any, name: str | None) -> Any:
    if not name:
        return project.GetCurrentTimeline()
    for idx in range(1, int(project.GetTimelineCount()) + 1):
        timeline = project.GetTimelineByIndex(idx)
        if timeline and timeline.GetName() == name:
            project.SetCurrentTimeline(timeline)
            return timeline
    return None


def audit(project_name: str | None, timeline_name: str | None) -> dict[str, Any]:
    resolve = get_resolve()
    pm = resolve.GetProjectManager()
    project = pm.LoadProject(project_name) if project_name else pm.GetCurrentProject()
    if not project:
        raise RuntimeError(f"Project not found or loaded: {project_name or '<current>'}")
    timeline = find_timeline(project, timeline_name)
    if not timeline:
        raise RuntimeError(f"Timeline not found: {timeline_name or '<current>'}")

    tracks = {}
    items = {}
    for track_type in ("video", "audio", "subtitle"):
        count = int(timeline.GetTrackCount(track_type) or 0)
        tracks[track_type] = []
        items[track_type] = {}
        for idx in range(1, count + 1):
            try:
                name = timeline.GetTrackName(track_type, idx)
            except Exception:  # noqa: BLE001
                name = ""
            try:
                item_list = timeline.GetItemListInTrack(track_type, idx) or []
            except Exception:  # noqa: BLE001
                item_list = []
            tracks[track_type].append({"index": idx, "name": name, "itemCount": len(item_list)})
            items[track_type][str(idx)] = [item_range(item) for item in item_list]

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "product": resolve.GetProductName(),
        "version": resolve.GetVersionString(),
        "projectName": project.GetName(),
        "timelineName": timeline.GetName(),
        "startFrame": timeline.GetStartFrame(),
        "endFrame": timeline.GetEndFrame(),
        "startTimecode": timeline.GetStartTimecode(),
        "tracks": tracks,
        "items": items,
        "markers": timeline.GetMarkers(),
        "warnings": [],
    }
    if sum(t["itemCount"] for t in tracks.get("video", [])) == 0:
        report["warnings"].append("No video items found.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a Resolve timeline by reading it back.")
    parser.add_argument("--project-name")
    parser.add_argument("--timeline-name")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit(args.project_name, args.timeline_name)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Project: {report['projectName']}")
        print(f"Timeline: {report['timelineName']}")
        for track_type, rows in report["tracks"].items():
            print(f"{track_type}: " + ", ".join(f"{row['index']}={row['itemCount']}" for row in rows))
        if report["warnings"]:
            print("Warnings:")
            for warning in report["warnings"]:
                print(f"  - {warning}")
    return 2 if report["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
