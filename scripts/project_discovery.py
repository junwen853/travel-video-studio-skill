"""Shared project discovery helpers for VideoClaw Studio packages."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


TEST_NAME_HINTS = ("test", "测试", "复盘", "自检", "导演脑")
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mts", ".mxf", ".avi", ".insv"}


def default_app_dir() -> Path:
    """Return the default VideoClaw Studio app directory for the current user."""
    configured = os.environ.get("VIDEO_CLAW_STUDIO_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Pictures" / "Video-make" / "video-claw-studio"


def collect_text_terms(value: Any) -> str:
    chunks: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            chunks.append(collect_text_terms(item))
    elif isinstance(value, list):
        for item in value:
            chunks.append(collect_text_terms(item))
    elif isinstance(value, str):
        chunks.append(value)
    return " ".join(chunks).lower()


def infer_region(text: str) -> str | None:
    hk = ["hong kong", "macao", "macau", "hk", "香港", "澳门", "澳門", "港澳", "维港", "維港"]
    jp = ["japan", "tokyo", "osaka", "kyoto", "日本", "东京", "東京", "大阪", "京都"]
    hk_hit = any(term in text for term in hk)
    jp_hit = any(term in text for term in jp)
    if hk_hit and not jp_hit:
        return "hong-kong-macao"
    if jp_hit and not hk_hit:
        return "japan"
    if hk_hit and jp_hit:
        return "mixed-hk-macao-japan"
    return None


def load_json_safe(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def is_app_dir(path: Path) -> bool:
    return (path / "projects").exists() and ((path / "server.py").exists() or (path / "data").exists() or (path / "data" / "config.json").exists())


def project_media_stats(project_dir: Path) -> dict[str, float | int]:
    media_index = project_dir / "media_index.json"
    project_json = load_json_safe(project_dir / "project.json")
    if not media_index.exists():
        return mounted_media_root_stats(project_json)
    data = load_json_safe(media_index)
    if not isinstance(data, dict):
        return {"videoCount": 0, "totalDuration": 0.0, "fileCount": 0}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    files = data.get("files") if isinstance(data.get("files"), list) else []
    video_count = summary.get("videoCount")
    if video_count is None:
        video_count = sum(1 for item in files if isinstance(item, dict) and item.get("kind") == "video")
    total_duration = summary.get("totalDuration")
    if total_duration is None:
        total_duration = 0.0
        for item in files:
            if not isinstance(item, dict) or item.get("kind") != "video":
                continue
            duration = item.get("duration") or item.get("probe", {}).get("format", {}).get("duration")
            try:
                total_duration += float(duration or 0)
            except Exception:  # noqa: BLE001
                pass
    return {"videoCount": int(video_count or 0), "totalDuration": float(total_duration or 0), "fileCount": len(files)}


def mounted_media_root_stats(project_data: Any) -> dict[str, float | int]:
    if not isinstance(project_data, dict):
        return {"videoCount": 0, "totalDuration": 0.0, "fileCount": 0}
    roots = project_data.get("mediaRoots") if isinstance(project_data.get("mediaRoots"), list) else []
    video_count = 0
    file_count = 0
    for root in roots:
        if not isinstance(root, str):
            continue
        path = Path(root).expanduser()
        if not path.exists() or not path.is_dir():
            continue
        try:
            children = list(path.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_file() or child.name.startswith("._"):
                continue
            file_count += 1
            if child.suffix.lower() in VIDEO_EXTS:
                video_count += 1
    return {"videoCount": int(video_count), "totalDuration": 0.0, "fileCount": int(file_count)}


def project_region_status(project_dir: Path) -> dict[str, Any]:
    project_data = load_json_safe(project_dir / "project.json")
    if not isinstance(project_data, dict):
        return {"intendedRegion": None, "mediaRegion": None, "mismatch": False}
    project_text = collect_text_terms(
        {
            "projectName": project_data.get("projectName"),
            "title": project_data.get("title"),
            "destination": project_data.get("destination"),
            "stylePreset": project_data.get("stylePreset"),
        }
    )
    media_text = collect_text_terms(project_data.get("mediaRoots", []))
    media_index = load_json_safe(project_dir / "media_index.json")
    if isinstance(media_index, dict):
        media_text += " " + collect_text_terms(media_index)
    intended = infer_region(project_text)
    media_region = infer_region(media_text)
    mismatch = bool(intended and media_region and intended != media_region and "mixed" not in (intended, media_region))
    return {"intendedRegion": intended, "mediaRegion": media_region, "mismatch": mismatch}


def latest_artifact_mtime(project_dir: Path) -> float:
    candidates = [
        project_dir / "project.json",
        project_dir / "media_index.json",
        project_dir / "video_location_map.json",
        project_dir / "route_timeline.json",
        project_dir / "confirmed_route_timeline.json",
        project_dir / "latest_location_route_pipeline.json",
        project_dir / "latest_route_review.json",
        project_dir / "latest_route_coverage_scaffold.json",
        project_dir / "latest_confirmed_route_candidate.json",
    ]
    candidates += list(project_dir.rglob("frame_index.json"))
    existing = [path for path in candidates if path.exists()]
    return max((path.stat().st_mtime for path in existing), default=0.0)


def artifact_count(project_dir: Path) -> int:
    names = [
        "project.json",
        "media_index.json",
        "video_location_map.json",
        "route_timeline.json",
        "confirmed_route_timeline.json",
        "latest_location_route_pipeline.json",
        "latest_route_review.json",
    ]
    return sum(1 for name in names if (project_dir / name).exists())


def likely_test_project(project_dir: Path) -> bool:
    name = project_dir.name.lower()
    return any(hint in name for hint in TEST_NAME_HINTS)


def project_score(project_dir: Path) -> tuple[int, int, int, float, int, int, float]:
    stats = project_media_stats(project_dir)
    video_count = int(stats["videoCount"])
    total_duration = float(stats["totalDuration"])
    region_ok = 0 if project_region_status(project_dir)["mismatch"] else 1
    return (
        1 if video_count > 0 else 0,
        region_ok,
        0 if likely_test_project(project_dir) else 1,
        total_duration,
        video_count,
        artifact_count(project_dir),
        latest_artifact_mtime(project_dir),
    )


def project_list(app_dir: Path) -> list[Path]:
    projects_dir = app_dir / "projects"
    return sorted([path for path in projects_dir.iterdir() if path.is_dir()]) if projects_dir.exists() else []


def select_project(projects: list[Path], project_name: str | None = None) -> Path | None:
    if project_name:
        for project in projects:
            if project.name == project_name:
                return project
        raise SystemExit(f"Project not found: {project_name}")
    scored = [(project_score(project), project) for project in projects if artifact_count(project) or project_media_stats(project)["videoCount"]]
    if not scored:
        return None
    return max(scored, key=lambda row: row[0])[1]


def discover_project_path(path: Path, project_name: str | None = None) -> Path:
    path = path.expanduser().resolve()
    if (path / "projects").exists():
        selected = select_project(project_list(path), project_name)
        if selected:
            return selected
    return path


def discover_app_and_project(path: Path, project_name: str | None = None) -> tuple[Path, Path | None, list[Path]]:
    path = path.expanduser().resolve()
    if is_app_dir(path) or (path / "projects").exists():
        app_dir = path
        projects = project_list(app_dir)
        return app_dir, select_project(projects, project_name), projects
    project_dir = path
    app_dir = project_dir.parent.parent if project_dir.parent.name == "projects" else project_dir
    return app_dir, project_dir, [project_dir]
