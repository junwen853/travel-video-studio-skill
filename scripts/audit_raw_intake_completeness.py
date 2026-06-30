#!/usr/bin/env python3
"""Audit raw media intake completeness before unattended travel-video editing."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mts", ".m2ts", ".mxf", ".avi", ".mkv", ".insv"}
DERIVED_TERMS = (
    "render",
    "renders",
    "export",
    "exports",
    "final",
    "master",
    "delivery_packages",
    "resolve",
    "premiere",
    "fcpx",
    "title_cards",
    "placeholder",
    "sample",
    "test",
    "成片",
    "终稿",
    "导出",
    "输出",
)


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_path(value: Any) -> str:
    if not value:
        return ""
    try:
        return str(Path(str(value)).expanduser().resolve())
    except Exception:
        return str(value)


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def is_video_path(path: Path | str) -> bool:
    item = Path(str(path))
    return not item.name.startswith("._") and item.suffix.lower() in VIDEO_EXTS


def is_video_row(row: dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    if str(row.get("kind") or row.get("mediaType") or "").lower() in {"video", "1"}:
        return True
    path = str(row.get("path") or row.get("sourcePath") or row.get("videoPath") or row.get("name") or "")
    return is_video_path(path)


def row_key(row: dict[str, Any]) -> str:
    for key in ("path", "sourcePath", "videoPath", "fileId", "videoId", "id", "name", "sourceName"):
        value = row.get(key)
        if value:
            text = str(value)
            if key.lower().endswith("path") or key == "path":
                return normalize_path(text)
            return text
    return ""


def row_keys(row: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for key in ("path", "sourcePath", "videoPath", "fileId", "videoId", "id", "name", "sourceName"):
        value = row.get(key)
        if not value:
            continue
        text = str(value)
        keys.add(text)
        if key.lower().endswith("path") or key == "path":
            keys.add(normalize_path(text))
            keys.add(source_name(text))
    return {key for key in keys if key}


def derived_like(value: Any) -> bool:
    text = str(value or "").lower()
    return any(term.lower() in text for term in DERIVED_TERMS)


def latest_file(root: Path, pattern: str) -> Path | None:
    candidates = sorted(root.glob(pattern), key=lambda path: path.stat().st_mtime if path.exists() else 0)
    return candidates[-1] if candidates else None


def infer_project_dir(package_dir: Path | None, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if package_dir:
        for rel in ("delivery_plan.json", "workflow_run_report.json", "client_delivery_rules_audit.json", "longform_delivery_audit.json"):
            data = load_json(package_dir / rel)
            if isinstance(data, dict) and data.get("projectDir"):
                return Path(str(data["projectDir"])).expanduser().resolve()
        parts = package_dir.resolve().parts
        if "delivery_packages" in parts:
            return Path(*parts[: parts.index("delivery_packages")])
    raise FileNotFoundError("Project directory could not be inferred; pass --project-dir.")


def latest_intake(project_dir: Path, explicit: str | None) -> tuple[Path | None, dict[str, Any]]:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path, load_json(path) or {}
    search_roots = [project_dir, project_dir.parent, project_dir.parent.parent]
    candidates: list[Path] = []
    for root in search_roots:
        if root.exists():
            candidates.extend(root.glob("external_media_intake/*/external_media_intake.json"))
            candidates.extend(root.glob("external_media_intake.json"))
    candidates = sorted(set(candidates), key=lambda path: path.stat().st_mtime if path.exists() else 0)
    if not candidates:
        return None, {}
    return candidates[-1], load_json(candidates[-1]) or {}


def latest_recognition_report(project_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    pointer = load_json(project_dir / "latest_footage_recognition_route_report.json") or {}
    report_path = pointer.get("report") or pointer.get("path") or pointer.get("json")
    if report_path:
        path = Path(str(report_path)).expanduser()
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    latest = latest_file(project_dir, "recognition_reports/*/footage_recognition_route_report.json")
    return (latest, load_json(latest) or {}) if latest else (None, {})


def load_footage_select(package_dir: Path | None, project_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    candidates: list[Path] = []
    if package_dir:
        candidates.append(package_dir / "footage_select_plan" / "footage_select_plan.json")
    candidates.append(project_dir / "footage_select_plan" / "footage_select_plan.json")
    for path in candidates:
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    return None, {}


def scan_media_roots(roots: list[str], max_files: int) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    truncated = False
    for raw in roots:
        root = Path(raw).expanduser()
        if not root.exists():
            missing.append(str(root))
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if not name.startswith(".") and name not in {"__MACOSX"}]
            for filename in filenames:
                path = Path(dirpath) / filename
                if not is_video_path(path):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                files.append({"path": normalize_path(path), "name": filename, "sizeBytes": size})
                if len(files) >= max_files:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break
    total_size = sum(int(row.get("sizeBytes") or 0) for row in files)
    return {
        "scannedVideoCount": len(files),
        "scannedVideoSizeBytes": total_size,
        "scannedVideoSizeGB": round(total_size / 1024 / 1024 / 1024, 3),
        "missingRoots": missing,
        "truncated": truncated,
        "maxFiles": max_files,
        "sampleVideos": [row["path"] for row in files[:12]],
        "files": files,
    }


def active_source_exclusion_keys(recognition: dict[str, Any], footage_select: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for source in (recognition, footage_select):
        for field in ("sourceExclusions", "excludedDerivedSources", "excludedSources"):
            for item in source.get(field) or []:
                if isinstance(item, dict):
                    if item.get("active", True):
                        keys.update(row_keys(item))
                elif item:
                    keys.add(str(item))
                    keys.add(normalize_path(item))
                    keys.add(source_name(item))
    rows = footage_select.get("selectionRows") if isinstance(footage_select.get("selectionRows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("selectionTier") in {"reject_excluded", "reject_or_review"} or row.get("status") == "excluded_from_first_cut":
            if any("derived" in str(reason).lower() or "excluded" in str(reason).lower() for reason in row.get("riskReasons") or []):
                keys.update(row_keys(row))
    return {key for key in keys if key}


def route_key_counts(route: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}

    def add_keys(values: set[str]) -> None:
        for key in {item for item in values if item}:
            counts[key] = counts.get(key, 0) + 1

    chapters = route.get("chapters") if isinstance(route.get("chapters"), list) else []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        for field in ("videos", "sourceVideos", "clips", "media"):
            for item in chapter.get(field) or []:
                if isinstance(item, dict):
                    add_keys(row_keys(item))
                elif item:
                    add_keys({str(item), normalize_path(item), source_name(item)})
        for field in ("videoPaths", "videoNames", "videoIds", "fileIds"):
            for item in chapter.get(field) or []:
                add_keys({str(item), normalize_path(item), source_name(item)})
    return counts


def rows_for_route(route: dict[str, Any]) -> set[str]:
    return set(route_key_counts(route))


def rows_for_recognition(recognition: dict[str, Any]) -> list[dict[str, Any]]:
    rows = recognition.get("rows") if isinstance(recognition.get("rows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def recognized(row: dict[str, Any]) -> bool:
    if row.get("excluded") or row.get("excludeFromSource"):
        return False
    text = " ".join(str(row.get(key) or "") for key in ("place", "city", "location", "confidenceLevel", "status")).lower()
    return bool(text.strip()) and not any(token in text for token in ("unknown", "unrecognized", "missing"))


def mtime(path: Path | None) -> float:
    try:
        return path.stat().st_mtime if path and path.exists() else 0.0
    except OSError:
        return 0.0


def stale_after_media_index(path: Path | None, media_index_path: Path) -> bool:
    return bool(path and path.exists() and mtime(path) + 1 < mtime(media_index_path))


def build_report(package_dir: Path | None, args: argparse.Namespace) -> dict[str, Any]:
    project_dir = infer_project_dir(package_dir, args.project_dir)
    project = load_json(project_dir / "project.json") or {}
    media_index_path = project_dir / "media_index.json"
    media_index = load_json(media_index_path) or {}
    media_roots = [normalize_path(root) for root in project.get("mediaRoots") or [] if root]
    scan = scan_media_roots(media_roots, args.max_scan_files) if media_roots and not args.no_filesystem_scan else {
        "scannedVideoCount": 0,
        "scannedVideoSizeBytes": 0,
        "scannedVideoSizeGB": 0,
        "missingRoots": [],
        "truncated": False,
        "maxFiles": args.max_scan_files,
        "sampleVideos": [],
        "files": [],
    }
    intake_path, intake = latest_intake(project_dir, args.intake_json)
    recognition_path, recognition = latest_recognition_report(project_dir)
    route_path = project_dir / "confirmed_route_timeline.json"
    route = load_json(route_path) or {}
    footage_select_path, footage_select = load_footage_select(package_dir, project_dir)

    indexed_files = [row for row in media_index.get("files") or [] if isinstance(row, dict) and is_video_row(row)]
    indexed_count = int((media_index.get("summary") or {}).get("videoCount") or media_index.get("videoCount") or len(indexed_files) or 0)
    indexed_size = int((media_index.get("summary") or {}).get("totalSize") or media_index.get("totalSize") or sum(int(row.get("sizeBytes") or row.get("size") or 0) for row in indexed_files))
    scan_count = int(scan.get("scannedVideoCount") or 0)
    source_size_gb = max(float(scan.get("scannedVideoSizeGB") or 0), indexed_size / 1024 / 1024 / 1024)
    exclusion_keys = active_source_exclusion_keys(recognition, footage_select)
    active_rows = [row for row in indexed_files if not (row_keys(row) & exclusion_keys)]
    active_keys = {row_key(row) for row in active_rows if row_key(row)}
    derived_rows = [row for row in active_rows if derived_like(row.get("path") or row.get("name"))]
    derived_excluded = [row for row in indexed_files if (row_keys(row) & exclusion_keys) and derived_like(row.get("path") or row.get("name"))]

    recognition_rows = rows_for_recognition(recognition)
    recognition_active = [row for row in recognition_rows if not (row_keys(row) & exclusion_keys)]
    recognized_rows = [row for row in recognition_active if recognized(row)]
    recognition_keys = {key for row in recognition_active for key in row_keys(row)}
    route_counts = route_key_counts(route)
    route_keys = set(route_counts)
    footage_rows = footage_select.get("selectionRows") if isinstance(footage_select.get("selectionRows"), list) else []
    footage_keys = {row_key(row) for row in footage_rows if isinstance(row, dict) and row_key(row)}

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    def add(name: str, passed: bool, evidence: dict[str, Any], *, warning: bool = False) -> None:
        checks.append({"name": name, "status": "passed" if passed else ("warning" if warning else "blocked"), "evidence": evidence})
        if not passed and not warning:
            blockers.append(name)
        elif not passed:
            warnings.append(name)

    media_roots_ok = bool(media_roots) and not scan.get("missingRoots")
    add(
        "Project has mounted media roots and the source drive is readable",
        media_roots_ok,
        {"mediaRoots": media_roots, "missingRoots": scan.get("missingRoots"), "project": str(project_dir / "project.json")},
    )
    scan_ok = bool(media_index_path.exists()) and indexed_count > 0 and (args.no_filesystem_scan or scan_count <= indexed_count) and not scan.get("truncated")
    add(
        "Media index covers the full selected source tree, not a partial sample",
        scan_ok,
        {
            "mediaIndex": str(media_index_path),
            "mediaIndexExists": media_index_path.exists(),
            "indexedVideoCount": indexed_count,
            "filesystemVideoCount": scan_count,
            "filesystemScanEnabled": not args.no_filesystem_scan,
            "scanTruncated": scan.get("truncated"),
            "sourceSizeGB": round(source_size_gb, 3),
        },
    )
    large_source = source_size_gb >= args.large_source_gb or indexed_count >= args.large_source_min_videos
    intake_ready = bool(intake) and intake.get("status") in {"ready_for_project_choice", "passed", "ready"}
    add(
        "External media intake records the chosen project/media root for large unordered folders",
        (not large_source) or intake_ready,
        {
            "largeSource": large_source,
            "largeSourceThresholdGB": args.large_source_gb,
            "largeSourceVideoThreshold": args.large_source_min_videos,
            "intakeJson": str(intake_path) if intake_path else None,
            "intakeStatus": intake.get("status"),
        },
        warning=not large_source,
    )
    add(
        "Derived exports, final masters, placeholders, and prior renders are excluded from active raw sources",
        not derived_rows,
        {
            "activeDerivedVideoCount": len(derived_rows),
            "excludedDerivedVideoCount": len(derived_excluded),
            "activeDerivedSamples": [row.get("path") or row.get("name") for row in derived_rows[:20]],
        },
    )
    recognition_missing = sorted(
        key for key in active_keys if key and key not in recognition_keys and source_name(key) not in recognition_keys
    )
    recognition_coverage = len(recognized_rows) / len(active_rows) if active_rows else 0.0
    recognition_ok = (
        bool(recognition)
        and recognition.get("status") in {"passed", "ready", "ready_with_caveats", "passed_with_caveats"}
        and len(recognition_active) == len(active_rows)
        and not recognition_missing
        and recognition_coverage >= args.min_recognition_coverage
    )
    add(
        "Recognition report accounts for every active source video before cutting",
        recognition_ok,
        {
            "recognitionReport": str(recognition_path) if recognition_path else None,
            "recognitionStatus": recognition.get("status"),
            "activeSourceVideoCount": len(active_rows),
            "recognitionActiveRowCount": len(recognition_active),
            "recognizedRowCount": len(recognized_rows),
            "missingRecognitionVideoKeys": recognition_missing[:30],
            "recognitionCoverageRatio": round(recognition_coverage, 4),
            "minRecognitionCoverage": args.min_recognition_coverage,
        },
    )
    route_missing = sorted(key for key in active_keys if key and key not in route_keys and source_name(key) not in route_keys)
    route_duplicates = sorted(
        key for key in active_keys if key and max(route_counts.get(key, 0), route_counts.get(source_name(key), 0)) > 1
    )
    route_ok = (
        bool(route)
        and int(route.get("chapterCount") or len(route.get("chapters") or [])) >= 2
        and not route_missing
        and not route_duplicates
    )
    add(
        "Confirmed route assigns every active source video exactly once into a multi-chapter trip",
        route_ok,
        {
            "confirmedRoute": str(route_path),
            "chapterCount": route.get("chapterCount") or len(route.get("chapters") or []),
            "activeSourceVideoCount": len(active_rows),
            "routeKeyCount": len(route_keys),
            "missingRouteVideoKeys": route_missing[:30],
            "duplicateRouteVideoKeys": route_duplicates[:30],
            "needsHumanReviewCount": route.get("needsHumanReviewCount"),
        },
    )
    footage_missing = sorted(key for key in active_keys if key and key not in footage_keys and source_name(key) not in footage_keys)
    footage_summary = footage_select.get("summary") if isinstance(footage_select.get("summary"), dict) else {}
    footage_ok = bool(footage_select) and footage_select.get("status") == "ready_with_footage_select_plan" and len(footage_rows) >= len(active_rows) and not footage_missing
    add(
        "Footage select plan scores and tiers every active source video before first assembly",
        footage_ok,
        {
            "footageSelectPlan": str(footage_select_path) if footage_select_path else None,
            "footageSelectStatus": footage_select.get("status"),
            "activeSourceVideoCount": len(active_rows),
            "selectionRowCount": len(footage_rows),
            "missingSelectionVideoKeys": footage_missing[:30],
            "summary": footage_summary,
        },
    )
    stale_items = {
        "recognition": stale_after_media_index(recognition_path, media_index_path),
        "confirmedRoute": stale_after_media_index(route_path, media_index_path),
        "footageSelect": stale_after_media_index(footage_select_path, media_index_path),
    }
    add(
        "Route, recognition, and footage-selection artifacts are not stale relative to media_index.json",
        not any(stale_items.values()),
        {"mediaIndexMtime": mtime(media_index_path), "staleArtifacts": stale_items},
    )

    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir) if package_dir else None,
        "projectDir": str(project_dir),
        "inputs": {
            "projectJson": str(project_dir / "project.json"),
            "mediaIndex": str(media_index_path),
            "externalMediaIntake": str(intake_path) if intake_path else None,
            "recognitionReport": str(recognition_path) if recognition_path else None,
            "confirmedRoute": str(route_path),
            "footageSelectPlan": str(footage_select_path) if footage_select_path else None,
        },
        "summary": {
            "mediaRootCount": len(media_roots),
            "indexedVideoCount": indexed_count,
            "filesystemVideoCount": scan_count,
            "activeSourceVideoCount": len(active_rows),
            "sourceSizeGB": round(source_size_gb, 3),
            "largeSource": large_source,
            "recognitionCoverageRatio": round(recognition_coverage, 4),
            "routeMissingVideoCount": len(route_missing),
            "routeDuplicateVideoCount": len(route_duplicates),
            "footageSelectMissingVideoCount": len(footage_missing),
            "activeDerivedVideoCount": len(derived_rows),
            "excludedDerivedVideoCount": len(derived_excluded),
            "staleArtifactCount": sum(1 for value in stale_items.values() if value),
            "checkCount": len(checks),
            "passedCheckCount": sum(1 for row in checks if row["status"] == "passed"),
            "blockedCheckCount": sum(1 for row in checks if row["status"] == "blocked"),
            "warningCheckCount": sum(1 for row in checks if row["status"] == "warning"),
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceDrive": False,
            "modifiesSourceFootage": False,
            "filesystemScanReadsMetadataOnly": True,
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Raw Intake Completeness Audit",
        "",
        f"Status: `{report['status']}`",
        f"Project: `{report['projectDir']}`",
        f"Package: `{report.get('packageDir')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
    ]
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Checks"])
    for row in report.get("checks") or []:
        lines.extend(
            [
                "",
                f"### {row.get('name')}",
                f"- Status: `{row.get('status')}`",
                f"- Evidence: `{json.dumps(row.get('evidence'), ensure_ascii=False)[:1600]}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit raw source intake completeness for unattended travel-video editing.")
    parser.add_argument("--package-dir")
    parser.add_argument("--project-dir")
    parser.add_argument("--intake-json")
    parser.add_argument("--large-source-gb", type=float, default=100.0)
    parser.add_argument("--large-source-min-videos", type=int, default=80)
    parser.add_argument("--min-recognition-coverage", type=float, default=1.0)
    parser.add_argument("--max-scan-files", type=int, default=100000)
    parser.add_argument("--no-filesystem-scan", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve() if args.package_dir else None
    report = build_report(package_dir, args)
    output_root = package_dir or Path(report["projectDir"])
    write_json(output_root / "raw_intake_completeness_audit.json", report)
    write_markdown(output_root / "raw_intake_completeness_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
