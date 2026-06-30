#!/usr/bin/env python3
"""Read-only VideoClaw Studio project health checker."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import default_app_dir, discover_app_and_project


DEFAULT_APP_DIR = default_app_dir()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


def iso_mtime(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def rel(path: Path | None, root: Path) -> str | None:
    if not path:
        return None
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def discover_project(input_path: Path, project_name: str | None) -> tuple[Path, Path | None, list[Path]]:
    return discover_app_and_project(input_path, project_name)


def provider_status(app_dir: Path) -> list[dict[str, Any]]:
    cfg_path = app_dir / "data" / "config.json"
    cfg = load_json(cfg_path) if cfg_path.exists() else {}
    providers = cfg.get("providers", []) if isinstance(cfg, dict) else []
    out = []
    for provider in providers:
        env_name = provider.get("apiKeyEnv") or ""
        base_url = provider.get("baseUrl") or ""
        status = {
            "id": provider.get("id"),
            "label": provider.get("label"),
            "enabled": bool(provider.get("enabled")),
            "tier": provider.get("tier"),
            "model": provider.get("model"),
            "baseUrl": base_url,
            "apiKeyEnv": env_name,
            "apiKeyVisible": bool(os.environ.get(env_name)) if env_name else True,
            "capabilities": provider.get("capabilities", []),
        }
        if "127.0.0.1:11434" in base_url or "localhost:11434" in base_url:
            status["ollama"] = probe_ollama(provider.get("model"))
        out.append(status)
    return out


def probe_ollama(expected_model: str | None) -> dict[str, Any]:
    url = "http://127.0.0.1:11434/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
        return {
            "reachable": True,
            "models": models,
            "expectedModelPresent": bool(expected_model and expected_model in models),
        }
    except Exception as exc:  # noqa: BLE001
        return {"reachable": False, "error": str(exc), "expectedModelPresent": False}


def artifact_paths(project_dir: Path) -> dict[str, Path | None]:
    return {
        "project": latest(list(project_dir.glob("project.json"))),
        "mediaIndex": latest(list(project_dir.glob("media_index.json"))),
        "frameIndex": latest(list(project_dir.rglob("frame_index.json"))),
        "localPrefilter": latest(list(project_dir.glob("local_prefilter.json"))),
        "locationCandidates": latest(list(project_dir.glob("location_candidates.json"))),
        "videoLocationMap": latest(list(project_dir.glob("video_location_map.json"))),
        "routeTimeline": latest(list(project_dir.glob("route_timeline.json"))),
        "confirmedRoute": latest(list(project_dir.glob("confirmed_route_timeline.json"))),
        "pipeline": latest(list(project_dir.glob("latest_location_route_pipeline.json"))),
        "timelineDraft": latest(list(project_dir.rglob("timeline_draft*.json"))),
    }


def count_unique(items: list[dict[str, Any]], *keys: str) -> int:
    values = set()
    for item in items:
        for key in keys:
            value = item.get(key)
            if value:
                values.add(str(value))
                break
    return len(values)


def summarize_artifact(name: str, path: Path | None, app_dir: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"path": rel(path, app_dir), "mtime": iso_mtime(path), "exists": bool(path)}
    if not path:
        return info
    data = load_json(path)
    if isinstance(data, dict) and data.get("_error"):
        info["error"] = data["_error"]
        return info

    if name == "project" and isinstance(data, dict):
        info.update(
            {
                "projectName": data.get("projectName"),
                "title": data.get("title"),
                "destination": data.get("destination"),
                "mediaRoots": data.get("mediaRoots", []),
            }
        )
    elif name == "mediaIndex" and isinstance(data, dict):
        summary = data.get("summary", {})
        info.update(
            {
                "videoCount": summary.get("videoCount"),
                "fileCount": summary.get("fileCount"),
                "totalDuration": summary.get("totalDuration"),
                "missingRoots": data.get("missingRoots", []),
            }
        )
    elif name == "frameIndex" and isinstance(data, dict):
        frames = data.get("frames", [])
        info.update(
            {
                "frameCount": data.get("frameCount", len(frames) if isinstance(frames, list) else None),
                "videoCount": count_unique(frames, "videoId", "sourceVideo") if isinstance(frames, list) else None,
                "ocrCandidateCount": data.get("ocrCandidateCount"),
                "locationCandidateCount": data.get("locationCandidateCount"),
            }
        )
    elif name == "localPrefilter" and isinstance(data, dict):
        videos = data.get("videos", [])
        priorities = Counter(v.get("priority", "unknown") for v in videos if isinstance(v, dict))
        info.update(
            {
                "localModelUsed": data.get("localModelUsed"),
                "localModelError": data.get("localModelError"),
                "videoCount": len(videos) if isinstance(videos, list) else None,
                "sendToCloudCount": sum(1 for v in videos if isinstance(v, dict) and v.get("sendToCloud")),
                "priorities": dict(priorities),
                "cloudFrameBudget": data.get("cloudFrameBudget"),
                "summary": data.get("summary"),
            }
        )
    elif name == "videoLocationMap" and isinstance(data, dict):
        info.update(
            {
                "videoCount": data.get("videoCount"),
                "highCount": data.get("highCount"),
                "mediumCount": data.get("mediumCount"),
                "lowCount": data.get("lowCount"),
                "unknownCount": data.get("unknownCount"),
                "needsHumanReviewCount": data.get("needsHumanReviewCount"),
            }
        )
    elif name in {"routeTimeline", "confirmedRoute"} and isinstance(data, dict):
        info.update(
            {
                "chapterCount": data.get("chapterCount"),
                "needsHumanReviewCount": data.get("needsHumanReviewCount"),
                "transitChapterCount": data.get("transitChapterCount"),
            }
        )
    elif name == "pipeline" and isinstance(data, dict):
        steps = data.get("steps", [])
        info.update(
            {
                "dryRun": data.get("dryRun"),
                "allowCloudCall": data.get("allowCloudCall"),
                "cloudProviderUsed": data.get("cloudProviderUsed"),
                "localModelUsed": data.get("localModelUsed"),
                "stepCount": len(steps) if isinstance(steps, list) else None,
                "failedSteps": [
                    s.get("id") for s in steps if isinstance(s, dict) and s.get("ok") is False
                ],
                "errors": data.get("errors", []),
                "projectWarnings": data.get("projectWarnings", []),
                "providerWarnings": data.get("providerWarnings", []),
            }
        )
    return info


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


def detect_mismatch(paths: dict[str, Path | None]) -> dict[str, Any]:
    project_data = load_json(paths["project"]) if paths.get("project") else {}
    if isinstance(project_data, dict):
        project_text = collect_text_terms(
            {
                "projectName": project_data.get("projectName"),
                "title": project_data.get("title"),
                "destination": project_data.get("destination"),
                "stylePreset": project_data.get("stylePreset"),
            }
        )
        media_roots_text = collect_text_terms(project_data.get("mediaRoots", []))
    else:
        project_text = ""
        media_roots_text = ""
    media_text = media_roots_text + " "
    media_text += collect_text_terms(load_json(paths["mediaIndex"])) if paths.get("mediaIndex") else ""
    detected_text = " ".join(
        collect_text_terms(load_json(paths[k]))
        for k in ("videoLocationMap", "routeTimeline", "confirmedRoute")
        if paths.get(k)
    )
    intended = infer_region(project_text)
    media_region = infer_region(media_text)
    detected = infer_region(detected_text)
    warnings = []
    blocking = False
    if intended and media_region and intended != media_region and "mixed" not in (intended, media_region):
        warnings.append(f"Project intent looks like {intended}, but media roots/files look like {media_region}.")
        blocking = True
    if intended and detected and intended != detected and "mixed" not in (intended, detected):
        warnings.append(f"Project intent looks like {intended}, but detected route looks like {detected}.")
        blocking = True
    return {
        "intendedRegion": intended,
        "mediaRegion": media_region,
        "detectedRegion": detected,
        "warnings": warnings,
        "blocking": blocking,
    }


def freshness(paths: dict[str, Path | None]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    blocking: list[str] = []

    def older(a: str, b: str) -> bool:
        pa, pb = paths.get(a), paths.get(b)
        return bool(pa and pb and pa.stat().st_mtime < pb.stat().st_mtime)

    if older("pipeline", "frameIndex"):
        warnings.append("latest_location_route_pipeline.json is older than the latest frame_index.json.")
    if older("localPrefilter", "frameIndex"):
        warnings.append("local_prefilter.json is older than the latest frame_index.json.")
    if older("routeTimeline", "videoLocationMap"):
        warnings.append("route_timeline.json is older than video_location_map.json.")
    if older("confirmedRoute", "routeTimeline"):
        blocking.append("confirmed_route_timeline.json is older than route_timeline.json.")
    return warnings, blocking


def recommend(status: dict[str, Any]) -> str:
    artifacts = status["artifacts"]
    blockers = status["blockingIssues"]
    if blockers:
        return "Resolve blocking issues before generating or trusting a route-aware cut."
    if not artifacts["mediaIndex"]["exists"]:
        return "Run media scan to create media_index.json."
    if not artifacts["frameIndex"]["exists"]:
        return "Run light frame extraction to create analysis/light/*/frame_index.json."
    if not artifacts["localPrefilter"]["exists"] or any("local_prefilter" in w for w in status["warnings"]):
        return "Run local prefilter before cloud recognition."
    if not artifacts["pipeline"]["exists"]:
        return "Run the Location-Route Pipeline first in dry-run mode."
    pipeline = artifacts["pipeline"]
    if pipeline.get("dryRun") or not pipeline.get("allowCloudCall"):
        return "Review local prefilter and explicitly approve cloud recognition if real location IDs are needed."
    if not artifacts["routeTimeline"]["exists"]:
        return "Merge recognition results and reconstruct route_timeline.json."
    if not artifacts["confirmedRoute"]["exists"]:
        return "Review route_timeline.json and save confirmed_route_timeline.json."
    if not artifacts["timelineDraft"]["exists"]:
        return "Generate a route-aware timeline draft from the confirmed route."
    return "Project is ready for route-aware edit review."


def build_status(args: argparse.Namespace) -> dict[str, Any]:
    app_dir, project_dir, project_candidates = discover_project(Path(args.project_dir), args.project_name)
    tools = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
    }
    status: dict[str, Any] = {
        "checkedAt": datetime.now().isoformat(timespec="seconds"),
        "appDir": str(app_dir),
        "projectDir": str(project_dir) if project_dir else None,
        "projectCandidates": [str(p) for p in project_candidates[-10:]],
        "tools": tools,
        "providers": provider_status(app_dir),
        "artifacts": {},
        "warnings": [],
        "blockingIssues": [],
    }
    if not project_dir or not project_dir.exists():
        status["blockingIssues"].append("No project directory found. Pass --project-dir to an app root or project folder.")
        status["recommendedNextAction"] = recommend(status)
        return status

    paths = artifact_paths(project_dir)
    status["artifacts"] = {name: summarize_artifact(name, path, app_dir) for name, path in paths.items()}

    fresh_warnings, fresh_blockers = freshness(paths)
    status["warnings"].extend(fresh_warnings)
    status["blockingIssues"].extend(fresh_blockers)

    mismatch = detect_mismatch(paths)
    status["routeMediaMismatch"] = mismatch
    status["warnings"].extend(mismatch["warnings"])
    if mismatch["blocking"]:
        status["blockingIssues"].append("Project/media/detected-route region mismatch must be confirmed before final cutting.")

    if not tools["ffmpeg"] or not tools["ffprobe"]:
        status["blockingIssues"].append("ffmpeg/ffprobe is missing; frame extraction cannot run.")

    cloud_providers = [p for p in status["providers"] if p.get("tier") == "cloud" and p.get("enabled")]
    missing_cloud_keys = [p["id"] for p in cloud_providers if not p.get("apiKeyVisible")]
    if missing_cloud_keys:
        status["warnings"].append(f"Enabled cloud provider key not visible in this shell: {', '.join(missing_cloud_keys)}.")

    status["recommendedNextAction"] = recommend(status)
    return status


def print_human(status: dict[str, Any]) -> None:
    print("Travel Video Studio status")
    print(f"App: {status['appDir']}")
    print(f"Project: {status.get('projectDir') or 'not found'}")
    print()
    print("Tools:")
    for name, path in status["tools"].items():
        print(f"  - {name}: {'ok at ' + path if path else 'missing'}")
    print()
    print("Providers:")
    for provider in status["providers"]:
        key = "ok" if provider.get("apiKeyVisible") else "missing"
        extra = ""
        if provider.get("ollama"):
            ollama = provider["ollama"]
            extra = f", ollama={'ok' if ollama.get('reachable') else 'offline'}, model={'ok' if ollama.get('expectedModelPresent') else 'missing'}"
        print(
            f"  - {provider.get('id')}: enabled={provider.get('enabled')}, tier={provider.get('tier')}, "
            f"model={provider.get('model')}, key={key}{extra}"
        )
    print()
    print("Artifacts:")
    for name, info in status["artifacts"].items():
        bits = [f"exists={info.get('exists')}", f"mtime={info.get('mtime')}"]
        for key in ("videoCount", "frameCount", "chapterCount", "localModelUsed", "dryRun", "allowCloudCall"):
            if key in info and info[key] is not None:
                bits.append(f"{key}={info[key]}")
        print(f"  - {name}: " + ", ".join(bits))
    if status.get("warnings"):
        print()
        print("Warnings:")
        for item in status["warnings"]:
            print(f"  - {item}")
    if status.get("blockingIssues"):
        print()
        print("Blocking issues:")
        for item in status["blockingIssues"]:
            print(f"  - {item}")
    print()
    print(f"Next: {status['recommendedNextAction']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only VideoClaw Studio project health checker.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app root or a project directory.")
    parser.add_argument("--project-name", help="Project folder name under app_root/projects.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    status = build_status(args)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print_human(status)
    return 2 if status.get("blockingIssues") else 0


if __name__ == "__main__":
    sys.exit(main())
