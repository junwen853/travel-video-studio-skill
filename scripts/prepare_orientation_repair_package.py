#!/usr/bin/env python3
"""Prepare a new delivery package after source-orientation client gates block an older package."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any


ASSET_DIRS = [
    "aerial_titles",
    "asset_ledger",
    "asset_sourcing",
    "bgm",
    "clean_scenic_title_bridges",
    "overlay_video_burnin",
    "subtitle_overlay_assets",
    "subtitle_overlays_title_safe",
    "title_cards",
    "v8_visual_polish",
    "v9_fix_inputs",
]

INPUT_FILES = [
    "asset_search_plan.md",
    "bgm_cues.md",
    "caption_overlap_fix_report.json",
    "caption_rewrite_report.json",
    "davinci_build_notes.md",
    "delivery_assets_report.json",
    "delivery_assets_report.md",
    "delivery_plan.json",
    "edit_decision_plan.md",
    "long_form_structure.md",
    "narration.txt",
    "narration_text_only_v4.txt",
    "qa_checklist.md",
    "quality_recut_report.json",
    "quality_recut_report.md",
    "resolve_timeline_enrichment.json",
    "subtitles.srt",
    "subtitles_v4_dense.srt",
    "v12_visual_manifest.json",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean(value: Any) -> str:
    return str(value or "").strip()


def rewrite_paths(value: Any, source_dir: Path, output_dir: Path) -> Any:
    if isinstance(value, str):
        source = str(source_dir)
        output = str(output_dir)
        if source in value:
            return value.replace(source, output)
        if "\n" not in value and len(value) < 2048:
            for anchor in ASSET_DIRS:
                token = f"/{anchor}/"
                if token not in value:
                    continue
                relative = value.split(token, 1)[1]
                candidate = output_dir / anchor / relative
                if candidate.exists():
                    return str(candidate)
        return value
    if isinstance(value, list):
        return [rewrite_paths(item, source_dir, output_dir) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_paths(item, source_dir, output_dir) for key, item in value.items()}
    return value


def copy_path(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return True


def rewrite_copied_asset_paths(output_dir: Path, source_dir: Path, copied_dirs: list[str]) -> list[str]:
    rewritten: list[str] = []
    text_suffixes = {".md", ".srt", ".txt"}
    for rel in copied_dirs:
        root = output_dir / rel
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            try:
                if suffix == ".json":
                    data = rewrite_paths(load_json(path), source_dir, output_dir)
                    write_json(path, data)
                    rewritten.append(str(path.relative_to(output_dir)))
                elif suffix in text_suffixes:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    replaced = text.replace(str(source_dir), str(output_dir))
                    if replaced != text:
                        path.write_text(replaced, encoding="utf-8")
                        rewritten.append(str(path.relative_to(output_dir)))
            except Exception:
                continue
    return rewritten


def load_stylefix_module() -> Any:
    module_path = Path(__file__).with_name("make_davinci_stylefix_blueprint.py")
    spec = importlib.util.spec_from_file_location("make_davinci_stylefix_blueprint", module_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load stylefix module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def localize_manifest(manifest_path: Path, source_dir: Path, output_dir: Path, rel: str) -> Path:
    data = rewrite_paths(load_json(manifest_path), source_dir, output_dir)
    localized = output_dir / rel
    write_json(localized, data)
    return localized


def default_resolve_names(source_package: Path, args: argparse.Namespace) -> tuple[str, str]:
    source_blueprint = load_json(source_package / "resolve_timeline_blueprint.json")
    if not isinstance(source_blueprint, dict):
        source_blueprint = {}
    base_project = clean(source_blueprint.get("projectName") or source_blueprint.get("title") or source_package.parent.parent.name)
    base_timeline = clean(source_blueprint.get("timelineName") or source_blueprint.get("projectName") or source_package.name)
    project_name = clean(args.project_name) or f"{base_project or 'Travel'} Orientation Repair"
    timeline_name = clean(args.timeline_name) or f"{base_timeline or 'Travel Longform'} Orientation Repair"
    return project_name, timeline_name


def sync_title_manifest_with_blueprint(output_dir: Path, blueprint: dict[str, Any]) -> list[str]:
    manifest_path = output_dir / "clean_scenic_title_bridges" / "clean_scenic_title_bridges_manifest.json"
    if not manifest_path.exists():
        return []
    manifest = load_json(manifest_path)
    segments = manifest.get("segments") if isinstance(manifest.get("segments"), list) else []
    title_clips = [
        clip for clip in blueprint.get("clips", [])
        if clip.get("role") in {"opening_city_aerial_title", "chapter_title_bridge", "ending_city_aerial_title"}
    ]
    updated: list[str] = []
    for segment in segments:
        try:
            start = float(segment.get("timeline_start") or segment.get("timelineStartSeconds") or 0)
        except (TypeError, ValueError):
            continue
        match = next(
            (
                clip for clip in title_clips
                if abs(float(clip.get("timelineStartSeconds") or 0) - start) < 0.05
            ),
            None,
        )
        if not match or not match.get("sourcePath"):
            continue
        if segment.get("segment") != match.get("sourcePath"):
            segment["segment"] = match["sourcePath"]
            updated.append(str(start))
        title = match.get("cityTitle") or match.get("titleText") or match.get("title")
        if title:
            segment["title"] = title
        if match.get("role") == "opening_city_aerial_title":
            segment["subtitle"] = ""
            segment["eyebrow"] = ""
    if updated:
        write_json(manifest_path, manifest)
    return updated


def build_report(
    source_package: Path,
    output_dir: Path,
    copied_dirs: list[str],
    copied_files: list[str],
    blueprint: dict[str, Any],
    blueprint_path: Path,
) -> dict[str, Any]:
    orientation_fixes = ((blueprint.get("manualQualityFix") or {}).get("orientationFixes") or [])
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": "prepared" if orientation_fixes else "prepared_no_orientation_fixes",
        "sourcePackage": str(source_package),
        "outputDir": str(output_dir),
        "blueprint": str(blueprint_path),
        "projectName": blueprint.get("projectName"),
        "timelineName": blueprint.get("timelineName"),
        "copiedAssetDirs": copied_dirs,
        "copiedInputFiles": copied_files,
        "orientationFixCount": len(orientation_fixes),
        "orientationFixes": orientation_fixes,
        "nextActions": [
            "Run audit_resolve_blueprint.py on the new package before any Resolve write.",
            "Run build_resolve_timeline.py --blueprint <package>/resolve_timeline_blueprint.json as a dry-run.",
            "Create a new Resolve project/timeline from this package, read it back, then render and run final QA.",
            "Do not reuse stale final_qa_suite_report.json from the source package as proof for this repair package.",
        ],
    }


def prepare_package(args: argparse.Namespace) -> dict[str, Any]:
    source_package = Path(args.source_package).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not (source_package / "resolve_timeline_blueprint.json").exists():
        raise FileNotFoundError(source_package / "resolve_timeline_blueprint.json")
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        raise FileExistsError(f"Output directory is not empty; pass --force to replace generated files: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_dirs: list[str] = []
    for rel in ASSET_DIRS:
        if copy_path(source_package / rel, output_dir / rel):
            copied_dirs.append(rel)
    rewritten_asset_files = rewrite_copied_asset_paths(output_dir, source_package, copied_dirs)

    copied_files: list[str] = []
    for rel in INPUT_FILES:
        source = source_package / rel
        target = output_dir / rel
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() == ".json":
                write_json(target, rewrite_paths(load_json(source), source_package, output_dir))
            else:
                text = source.read_text(encoding="utf-8", errors="ignore")
                target.write_text(text.replace(str(source_package), str(output_dir)), encoding="utf-8")
            copied_files.append(rel)

    fix_manifest_rel = args.fix_manifest_rel
    bgm_manifest_rel = args.bgm_manifest_rel
    fix_manifest = localize_manifest(source_package / fix_manifest_rel, source_package, output_dir, fix_manifest_rel)
    bgm_manifest = localize_manifest(source_package / bgm_manifest_rel, source_package, output_dir, bgm_manifest_rel)

    stylefix = load_stylefix_module()
    project_name, timeline_name = default_resolve_names(source_package, args)
    stylefix_args = Namespace(
        base_blueprint=str(source_package / "resolve_timeline_blueprint.json"),
        fix_manifest=str(fix_manifest),
        bgm_manifest=str(bgm_manifest),
        output_dir=str(output_dir),
        project_name=project_name,
        timeline_name=timeline_name,
        opening_title=None,
        opening_place=None,
        bgm_mood=None,
    )
    blueprint = stylefix.make_blueprint(stylefix_args)
    blueprint = rewrite_paths(blueprint, source_package, output_dir)
    blueprint["createdAt"] = datetime.now().isoformat(timespec="seconds")
    blueprint["updatedAt"] = blueprint["createdAt"]
    blueprint.pop("sourcePackage", None)
    blueprint["sourcePackageName"] = source_package.name
    blueprint["repairPackageVersion"] = "v14_orientation_repair"
    blueprint["outputDir"] = str(output_dir)
    blueprint["projectName"] = project_name
    blueprint["timelineName"] = timeline_name
    synced_title_manifest_starts = sync_title_manifest_with_blueprint(output_dir, blueprint)

    blueprint_path = output_dir / "resolve_timeline_blueprint.json"
    write_json(blueprint_path, blueprint)
    write_json(output_dir / "resolve_timeline_blueprint_v14_orientation_repair.json", blueprint)

    report = build_report(source_package, output_dir, copied_dirs, copied_files, blueprint, blueprint_path)
    report["rewrittenCopiedAssetFiles"] = rewritten_asset_files
    report["syncedTitleManifestStarts"] = synced_title_manifest_starts
    write_json(output_dir / "orientation_repair_package_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an orientation-fixed repair package from a blocked delivery package.")
    parser.add_argument("--source-package", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--project-name")
    parser.add_argument("--timeline-name")
    parser.add_argument("--fix-manifest-rel", default="v9_fix_inputs/v9_fix_manifest.json")
    parser.add_argument("--bgm-manifest-rel", default="bgm/v9_bgm_manifest.json")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = prepare_package(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Orientation repair package: {report['status']}")
        print(f"Package: {report['outputDir']}")
        print(f"Blueprint: {report['blueprint']}")
        print(f"Orientation fixes: {report['orientationFixCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
