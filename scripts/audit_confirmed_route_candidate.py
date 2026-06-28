#!/usr/bin/env python3
"""Audit a confirmed-route candidate before any approved route apply step."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from project_discovery import default_app_dir, discover_app_and_project
except Exception:  # noqa: BLE001
    discover_app_and_project = None  # type: ignore[assignment]


ACCEPTED_DECISIONS = {"codex_visual_confirmed", "confirmed", "corrected", "split", "merge", "exclude"}
BLOCKING_COUNTRY_CONFLICTS = {
    "hong_kong_macau": ("japan",),
    "japan": ("hong kong", "macau", "macao"),
}


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalize(value: Any) -> str:
    return clean(value).lower()


def resolve_project(path: Path, project_name: str | None) -> tuple[Path, Path]:
    path = path.expanduser().resolve()
    if discover_app_and_project:
        app_dir, project_dir, _projects = discover_app_and_project(path, project_name)
        if not project_dir:
            raise SystemExit(f"Project not found under: {path}")
        return app_dir, project_dir
    if (path / "projects").exists():
        if not project_name:
            raise SystemExit("--project-name is required when --project-dir points at an app root")
        return path, path / "projects" / project_name
    app_dir = path.parent.parent if path.parent.name == "projects" else path
    return app_dir, path


def latest_json_in_tree(project_dir: Path, names: tuple[str, ...]) -> tuple[Path | None, dict[str, Any] | None]:
    candidates: list[Path] = []
    for name in names:
        candidates.extend(project_dir.rglob(name))
    candidates = sorted(candidates, key=lambda path: path.stat().st_mtime if path.exists() else 0)
    for path in reversed(candidates):
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    return None, None


def resolve_candidate(project_dir: Path, explicit: str | None) -> tuple[Path | None, dict[str, Any] | None]:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        data = load_json(path)
        return path, data if isinstance(data, dict) else None
    pointer = load_json(project_dir / "latest_confirmed_route_candidate.json")
    if isinstance(pointer, dict):
        for key in ("candidate", "path", "report", "json"):
            if pointer.get(key):
                path = Path(str(pointer[key])).expanduser()
                data = load_json(path)
                if isinstance(data, dict):
                    return path, data
    return latest_json_in_tree(project_dir, ("codex_visual_confirmed_route_candidate.json", "confirmed_route_candidate.json"))


def active_exclusion_keys(project_dir: Path, candidate: dict[str, Any] | None) -> tuple[set[str], list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    source_file = load_json(project_dir / "source_exclusions.json")
    if isinstance(source_file, dict):
        items.extend(item for item in source_file.get("items") or [] if isinstance(item, dict))
    if isinstance(candidate, dict):
        items.extend(item for item in candidate.get("sourceExclusions") or [] if isinstance(item, dict))

    keys: set[str] = set()
    active_items: list[dict[str, Any]] = []
    for item in items:
        if item.get("active") is False:
            continue
        active_items.append(item)
        for field in ("fileId", "path", "name"):
            value = item.get(field)
            if value:
                keys.add(str(value))
                if field == "path":
                    keys.add(Path(str(value)).name)
    return keys, active_items


def row_id(row: dict[str, Any]) -> str:
    return clean(row.get("fileId") or row.get("path") or row.get("name"))


def row_keys(row: dict[str, Any]) -> set[str]:
    keys = {clean(row.get(field)) for field in ("fileId", "path", "name", "hash") if clean(row.get(field))}
    path = clean(row.get("path"))
    if path:
        keys.add(Path(path).name)
    return keys


def load_media_rows(project_dir: Path, candidate: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], list[str]]:
    media = load_json(project_dir / "media_index.json")
    blockers: list[str] = []
    if not isinstance(media, dict):
        return [], [], {}, ["media_index.json is missing or invalid."]
    exclusion_keys, _items = active_exclusion_keys(project_dir, candidate)
    all_video_rows = [row for row in media.get("files") or [] if isinstance(row, dict) and row.get("kind") == "video"]
    active_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    for row in all_video_rows:
        keys = row_keys(row)
        if truthy(row.get("excludedFromCut")) or bool(keys & exclusion_keys):
            excluded_rows.append(row)
        else:
            active_rows.append(row)
    key_to_row: dict[str, str] = {}
    for row in active_rows:
        rid = row_id(row)
        for key in row_keys(row):
            key_to_row[key] = rid
    if not active_rows:
        blockers.append("media_index.json has no active source videos.")
    return active_rows, excluded_rows, key_to_row, blockers


def route_body(candidate: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    body = candidate.get("candidate")
    if isinstance(body, dict):
        return body
    if isinstance(candidate.get("chapters"), list):
        return candidate
    return {}


def chapter_refs(chapter: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for field in ("videos", "fileIds", "videoIds"):
        for value in chapter.get(field) or []:
            if clean(value):
                refs.add(clean(value))
    for field in ("videoPaths", "videoNames"):
        for value in chapter.get(field) or []:
            if clean(value):
                refs.add(clean(value))
                if field == "videoPaths":
                    refs.add(Path(clean(value)).name)
    return refs


def add_check(checks: list[dict[str, Any]], name: str, status: str, evidence: Any) -> None:
    checks.append({"name": name, "status": status, "evidence": evidence})


def infer_expected_region(project_dir: Path, route: dict[str, Any]) -> str | None:
    project = load_json(project_dir / "project.json") or {}
    parts = [project_dir.name]
    if isinstance(project, dict):
        for key in ("title", "subtitle", "destination", "places", "routeText", "mediaRoots"):
            value = project.get(key)
            if isinstance(value, (list, tuple)):
                parts.extend(str(item) for item in value)
            else:
                parts.append(str(value or ""))
    parts.append(str(route.get("routeSummary") or ""))
    text = "\n".join(parts).lower()
    if any(token in text for token in ("hong kong", "macau", "macao", "\u9999\u6e2f", "\u6fb3\u95e8", "\u6e2f\u6fb3")):
        return "hong_kong_macau"
    if any(token in text for token in ("japan", "tokyo", "osaka", "kyoto", "\u65e5\u672c", "\u6771\u4eac", "\u4eac\u90fd", "\u5927\u962a")):
        return "japan"
    return None


def country_region(value: str) -> str | None:
    text = value.lower()
    if any(token in text for token in ("hong kong", "macau", "macao", "\u9999\u6e2f", "\u6fb3\u95e8", "\u6e2f\u6fb3")):
        return "hong_kong_macau"
    if any(token in text for token in ("japan", "tokyo", "osaka", "kyoto", "\u65e5\u672c", "\u6771\u4eac", "\u4eac\u90fd", "\u5927\u962a")):
        return "japan"
    return None


def audit_region(project_dir: Path, route: dict[str, Any], checks: list[dict[str, Any]]) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    expected = infer_expected_region(project_dir, route)
    countries = sorted({clean(chapter.get("country")) for chapter in route.get("chapters") or [] if clean(chapter.get("country"))})
    chapter_regions = sorted({region for country in countries if (region := country_region(country))})
    if expected:
        conflict_tokens = BLOCKING_COUNTRY_CONFLICTS.get(expected, ())
        conflicts = [country for country in countries if any(token in country.lower() for token in conflict_tokens)]
        if conflicts:
            blockers.append(f"Candidate country labels conflict with project region {expected}: {conflicts}")
        if expected not in chapter_regions:
            warnings.append(f"Project region looks like {expected}, but chapter country labels do not clearly include it.")
    add_check(
        checks,
        "Project/candidate region labels do not inherit the wrong trip country",
        "blocked" if blockers else ("warning" if warnings else "passed"),
        {"expectedRegion": expected, "countries": countries, "chapterRegions": chapter_regions},
    )
    return blockers, warnings, {"expectedRegion": expected, "countries": countries, "chapterRegions": chapter_regions}


def audit_chapters(
    route: dict[str, Any],
    active_rows: list[dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
    key_to_row: dict[str, str],
    checks: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    caveats: list[str] = []
    active_ids = {row_id(row) for row in active_rows}
    excluded_key_to_row: dict[str, str] = {}
    for row in excluded_rows:
        rid = row_id(row)
        for key in row_keys(row):
            excluded_key_to_row[key] = rid

    chapters = [chapter for chapter in route.get("chapters") or [] if isinstance(chapter, dict)]
    assigned_by_chapter: dict[str, list[int]] = {}
    unknown_refs: list[dict[str, Any]] = []
    excluded_refs: list[dict[str, Any]] = []
    empty_chapters: list[int] = []
    weak_chapters: list[int] = []
    metadata_gaps: list[dict[str, Any]] = []

    for index, chapter in enumerate(chapters, start=1):
        refs = chapter_refs(chapter)
        matched_rows = sorted({key_to_row[ref] for ref in refs if ref in key_to_row})
        chapter_unknown = sorted(ref for ref in refs if ref not in key_to_row and ref not in excluded_key_to_row)
        chapter_excluded = sorted(ref for ref in refs if ref in excluded_key_to_row)
        if chapter_unknown:
            unknown_refs.append({"chapter": index, "unknownRefs": chapter_unknown[:12], "unknownRefCount": len(chapter_unknown)})
        if chapter_excluded:
            excluded_refs.append({"chapter": index, "excludedRefs": chapter_excluded[:12], "excludedRefCount": len(chapter_excluded)})
        if not matched_rows:
            empty_chapters.append(index)
        for rid in matched_rows:
            assigned_by_chapter.setdefault(rid, []).append(index)

        gaps: list[str] = []
        if not clean(chapter.get("chapter")) and not clean(chapter.get("place")):
            gaps.append("chapter_or_place")
        if not clean(chapter.get("timeRange")) and not clean(chapter.get("date")):
            gaps.append("date_or_timeRange")
        if not clean(chapter.get("country")):
            gaps.append("country")
        if not clean(chapter.get("confidenceLevel")) and chapter.get("confidence") in (None, ""):
            gaps.append("confidence")
        decision = clean(chapter.get("reviewDecision"))
        if decision and decision not in ACCEPTED_DECISIONS:
            gaps.append(f"unsupported_reviewDecision:{decision}")
        if not (chapter.get("representativeFrames") or chapter.get("evidence")):
            gaps.append("representativeFrames_or_evidence")
        if gaps:
            metadata_gaps.append({"chapter": index, "gaps": gaps})

        confidence_text = normalize(chapter.get("confidenceLevel") or chapter.get("confidence"))
        if "low" in confidence_text or "unknown" in confidence_text:
            weak_chapters.append(index)

    duplicates = {rid: indices for rid, indices in assigned_by_chapter.items() if len(set(indices)) > 1}
    missing = sorted(active_ids - set(assigned_by_chapter))
    assigned_count = len(set(assigned_by_chapter))

    if unknown_refs:
        blockers.append(f"Candidate references source videos not found in media_index.json: {sum(item['unknownRefCount'] for item in unknown_refs)} refs.")
    if excluded_refs:
        blockers.append(f"Candidate references active source exclusions: {sum(item['excludedRefCount'] for item in excluded_refs)} refs.")
    if empty_chapters:
        blockers.append(f"Candidate has chapters with no active source videos: {empty_chapters}")
    if duplicates:
        blockers.append(f"Candidate assigns {len(duplicates)} active source videos to more than one chapter.")
    if missing:
        blockers.append(f"Candidate misses {len(missing)} active source videos from media_index.json.")
    if metadata_gaps:
        blockers.append(f"Candidate chapters have missing required route metadata/evidence: {len(metadata_gaps)} chapters.")
    if weak_chapters:
        caveats.append(f"Candidate contains low/unknown-confidence chapters: {weak_chapters}")

    add_check(
        checks,
        "Every active source video is assigned exactly once",
        "blocked" if any(item in "\n".join(blockers) for item in ("references source", "active source exclusions", "no active source", "assigns", "misses")) else "passed",
        {
            "activeSourceVideoCount": len(active_rows),
            "assignedSourceVideoCount": assigned_count,
            "missingCount": len(missing),
            "duplicateCount": len(duplicates),
            "unknownRefCount": sum(item["unknownRefCount"] for item in unknown_refs),
            "excludedRefCount": sum(item["excludedRefCount"] for item in excluded_refs),
        },
    )
    add_check(
        checks,
        "Each chapter has route metadata, confidence, decision, and evidence",
        "blocked" if metadata_gaps or empty_chapters else ("warning" if weak_chapters else "passed"),
        {"chapterCount": len(chapters), "metadataGaps": metadata_gaps[:20], "weakChapters": weak_chapters},
    )
    return blockers, warnings, caveats, {
        "activeSourceVideoCount": len(active_rows),
        "excludedSourceVideoCount": len(excluded_rows),
        "assignedSourceVideoCount": assigned_count,
        "missingSourceVideoCount": len(missing),
        "duplicateSourceVideoCount": len(duplicates),
        "unknownReferenceCount": sum(item["unknownRefCount"] for item in unknown_refs),
        "excludedReferenceCount": sum(item["excludedRefCount"] for item in excluded_refs),
        "missingSourceVideos": missing[:50],
        "duplicateSourceVideos": [{"source": key, "chapters": value} for key, value in sorted(duplicates.items())[:50]],
        "unknownReferences": unknown_refs[:50],
        "excludedReferences": excluded_refs[:50],
        "emptyChapters": empty_chapters,
        "metadataGaps": metadata_gaps[:50],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    app_dir, project_dir = resolve_project(Path(args.project_dir), args.project_name)
    candidate_path, candidate = resolve_candidate(project_dir, args.candidate_json)
    route = route_body(candidate)
    created_at = datetime.now().isoformat(timespec="seconds")

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    caveats: list[str] = []

    if not isinstance(candidate, dict):
        blockers.append("Confirmed route candidate is missing or invalid.")
        candidate = {}
    wrapper_status = candidate.get("status")
    can_apply = candidate.get("canApply")
    if wrapper_status == "blocked":
        blockers.append("Confirmed route candidate status is blocked.")
    if can_apply is False:
        blockers.append("Confirmed route candidate is not marked canApply=true.")
    if not route:
        blockers.append("Confirmed route candidate has no candidate route body.")

    chapters = [chapter for chapter in route.get("chapters") or [] if isinstance(chapter, dict)] if route else []
    declared_chapter_count = route.get("chapterCount") if isinstance(route, dict) else None
    if route and int(declared_chapter_count or len(chapters)) != len(chapters):
        blockers.append(f"Route chapterCount {declared_chapter_count} does not match chapter rows {len(chapters)}.")
    if route and not chapters:
        blockers.append("Candidate route has no chapters.")
    route_project = clean(route.get("projectDir") or candidate.get("projectDir"))
    if route_project and Path(route_project).expanduser().resolve() != project_dir:
        blockers.append(f"Candidate projectDir does not match selected project: {route_project}")

    active_rows, excluded_rows, key_to_row, media_blockers = load_media_rows(project_dir, candidate)
    blockers.extend(media_blockers)
    declared_source_count = route.get("sourceVideoCount") if isinstance(route, dict) else None
    if declared_source_count is not None and int(declared_source_count or 0) != len(active_rows):
        blockers.append(f"Candidate sourceVideoCount {declared_source_count} does not match active media_index videos {len(active_rows)}.")
    elif declared_source_count is None and route:
        warnings.append("Candidate route does not declare sourceVideoCount; coverage is audited from media_index.json only.")

    add_check(
        checks,
        "Candidate exists and is apply-ready before approval",
        "blocked" if any("candidate" in item.lower() for item in blockers) else "passed",
        {
            "candidateJson": str(candidate_path) if candidate_path else None,
            "status": wrapper_status,
            "canApply": can_apply,
            "mode": route.get("mode") if route else None,
            "chapterCount": declared_chapter_count,
        },
    )
    add_check(
        checks,
        "media_index.json provides active source rows",
        "blocked" if media_blockers else "passed",
        {"activeSourceVideoCount": len(active_rows), "excludedSourceVideoCount": len(excluded_rows)},
    )

    chapter_summary: dict[str, Any] = {}
    if route and active_rows:
        chapter_blockers, chapter_warnings, chapter_caveats, chapter_summary = audit_chapters(
            route, active_rows, excluded_rows, key_to_row, checks
        )
        blockers.extend(chapter_blockers)
        warnings.extend(chapter_warnings)
        caveats.extend(chapter_caveats)

    region_summary: dict[str, Any] = {}
    if route:
        region_blockers, region_warnings, region_summary = audit_region(project_dir, route, checks)
        blockers.extend(region_blockers)
        warnings.extend(region_warnings)

    if active_rows and not any(truthy(row.get("hasGPS")) for row in active_rows):
        caveats.append("No active source video has GPS metadata; do not claim exact per-video geolocation.")
    notes = " ".join(str(item) for item in route.get("notes") or []).lower() if route else ""
    if "not cloud" in notes or "not local" in notes or route.get("mode") == "codex_visual_confirmed_route":
        caveats.append("Route is visual/Codex-confirmed, not GPS-grade or cloud-verified per-clip truth.")
    if route and route.get("needsHumanReviewCount") not in (None, 0):
        blockers.append(f"Candidate route still has needsHumanReviewCount={route.get('needsHumanReviewCount')}.")

    blockers = sorted(dict.fromkeys(blockers))
    warnings = sorted(dict.fromkeys(warnings))
    caveats = sorted(dict.fromkeys(caveats))
    status = "blocked" if blockers else ("passed_with_caveats" if warnings or caveats else "passed")

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else (
        candidate_path.parent if candidate_path else project_dir / "route_candidate_audit"
    )
    output_json = output_dir / "confirmed_route_candidate_audit.json"
    output_markdown = output_dir / "confirmed_route_candidate_audit.md"

    next_actions = []
    if blockers:
        next_actions.append("Fix the candidate blockers before any --apply writes confirmed_route_timeline.json.")
    else:
        next_actions.append("After explicit approval, apply the audited candidate, then rerun audit_location_truth_contract.py.")
    if warnings or caveats:
        next_actions.append("Carry the non-GPS visual-route caveat into recognition, package, and final delivery language.")

    report = {
        "createdAt": created_at,
        "status": status,
        "projectDir": str(project_dir),
        "appDir": str(app_dir),
        "candidateJson": str(candidate_path) if candidate_path else None,
        "outputJson": str(output_json),
        "outputMarkdown": str(output_markdown),
        "summary": {
            "candidateStatus": wrapper_status,
            "canApply": can_apply,
            "mode": route.get("mode") if route else None,
            "chapterCount": len(chapters),
            "declaredChapterCount": declared_chapter_count,
            "declaredSourceVideoCount": declared_source_count,
            **chapter_summary,
            **region_summary,
            "routeAwareEditClaimAllowedAfterApply": status != "blocked",
            "exactPerVideoLocationClaimAllowed": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "caveats": caveats,
        "checks": checks,
        "nextActions": next_actions,
        "safety": {
            "modifiesSourceDrive": False,
            "writesConfirmedRouteTimeline": False,
            "writesResolve": False,
            "queuesRender": False,
            "callsCloudVision": False,
            "downloadsExternalAssets": False,
            "writesAuditFilesOnly": True,
            "requiresExplicitApprovalForRouteApply": True,
        },
        "contract": {
            "purpose": "Prove a ready confirmed-route candidate covers all active source videos exactly once before any approved route apply step.",
            "notLocationTruth": "This audit allows route-aware editing with caveats; it never upgrades visual review into GPS-grade per-video geolocation.",
        },
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Confirmed Route Candidate Audit",
        "",
        f"Status: `{report['status']}`",
        f"Project: `{report['projectDir']}`",
        f"Candidate: `{report.get('candidateJson')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in report.get("warnings") or ["None"])
    lines.extend(["", "## Caveats"])
    lines.extend(f"- {item}" for item in report.get("caveats") or ["None"])
    lines.extend(["", "## Checks"])
    for check in report.get("checks") or []:
        lines.append(f"- `{check['status']}` {check['name']}")
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "```json",
            json.dumps(report["safety"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Contract",
            "",
            "```json",
            json.dumps(report["contract"], ensure_ascii=False, indent=2),
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a confirmed-route candidate before any --apply route write.")
    parser.add_argument("--project-dir", required=True, help="VideoClaw app dir or project dir.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app.")
    parser.add_argument("--candidate-json", help="Candidate JSON. Defaults to latest_confirmed_route_candidate.json or newest candidate file.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to the candidate directory.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    output_json = Path(report["outputJson"])
    output_markdown = Path(report["outputMarkdown"])
    write_json(output_json, report)
    write_markdown(output_markdown, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Confirmed route candidate audit: {report['status']}")
        print(f"Audit JSON: {output_json}")
        print(f"Audit Markdown: {output_markdown}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
