#!/usr/bin/env python3
"""Audit whether location/route evidence supports the claimed location truth level."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


READY_STATUSES = {
    "ready",
    "ready_with_warnings",
    "ready_with_caveats",
    "passed",
    "passed_with_warnings",
    "passed_with_caveats",
}
UNKNOWN_TOKENS = ("unknown", "unrecognized", "unresolved", "未识别", "未知")
VERIFIED_TOKENS = (
    "gps",
    "geotag",
    "geolocation",
    "cloud_verified",
    "mimo_verified",
    "human_verified",
    "user_verified",
    "exact_verified",
    "verified_per_clip",
)
WEAK_CONFIDENCE_TOKENS = ("medium", "low", "unknown", "scaffold", "estimated")


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


def as_path(value: Any) -> Path | None:
    if not value:
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except Exception:
        return None


def row_key(item: dict[str, Any]) -> str:
    for key in ("fileId", "id", "videoId", "path", "sourceVideo", "name", "video"):
        value = item.get(key)
        if value:
            return str(value)
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def is_video_file(item: dict[str, Any]) -> bool:
    media_type = str(item.get("mediaType") or "").lower()
    if media_type and "image" in media_type:
        return False
    path = str(item.get("path") or item.get("name") or "").lower()
    return path.endswith((".mp4", ".mov", ".m4v", ".mts", ".m2ts", ".avi", ".mkv")) or "video" in media_type


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def infer_project_dir(package_dir: Path | None, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if package_dir:
        for rel in ("client_delivery_rules_audit.json", "longform_delivery_audit.json", "delivery_plan.json", "workflow_run_report.json"):
            data = load_json(package_dir / rel)
            if isinstance(data, dict) and data.get("projectDir"):
                return Path(str(data["projectDir"])).expanduser().resolve()
        parts = package_dir.resolve().parts
        if "delivery_packages" in parts:
            index = parts.index("delivery_packages")
            return Path(*parts[:index])
    raise FileNotFoundError("Project directory could not be inferred; pass --project-dir.")


def latest_recognition_report(project_dir: Path) -> tuple[Path | None, dict[str, Any] | None, dict[str, Any] | None]:
    pointer_path = project_dir / "latest_footage_recognition_route_report.json"
    pointer = load_json(pointer_path)
    if isinstance(pointer, dict):
        report_path = as_path(pointer.get("report"))
        if report_path and report_path.exists():
            report = load_json(report_path)
            if isinstance(report, dict):
                return report_path, report, pointer
    candidates = sorted((project_dir / "recognition_reports").glob("*/footage_recognition_route_report.json"))
    for path in reversed(candidates):
        report = load_json(path)
        if isinstance(report, dict):
            return path, report, pointer if isinstance(pointer, dict) else None
    return None, None, pointer if isinstance(pointer, dict) else None


def active_source_exclusion_keys(report: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for item in report.get("sourceExclusions") or []:
        if not isinstance(item, dict):
            continue
        if item.get("active") is False:
            continue
        for key in (item.get("fileId"), item.get("path"), item.get("name")):
            if key:
                keys.add(str(key))
    return keys


def is_excluded_row(row: dict[str, Any], exclusion_keys: set[str]) -> bool:
    if truthy(row.get("excludedFromCut")):
        return True
    keys = {str(row.get(key)) for key in ("fileId", "path", "name") if row.get(key)}
    return bool(keys & exclusion_keys)


def is_recognized_row(row: dict[str, Any]) -> bool:
    place = str(row.get("place") or row.get("location") or row.get("recognizedPlace") or "").strip().lower()
    level = str(row.get("confidenceLevel") or row.get("confidence") or "").strip().lower()
    if not place or any(token in place for token in UNKNOWN_TOKENS):
        return False
    if level == "excluded" or any(token == level for token in UNKNOWN_TOKENS):
        return False
    return True


def verified_reason(row: dict[str, Any]) -> str | None:
    if truthy(row.get("hasGPS")):
        return "gps_metadata"
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "confidenceLevel",
            "confidence",
            "provider",
            "recognitionProvider",
            "evidenceProvider",
            "truthLevel",
            "locationTruth",
            "source",
            "notes",
        )
    ).lower()
    if any(token in text for token in VERIFIED_TOKENS):
        return "verified_label"
    return None


def weak_confidence(row: dict[str, Any]) -> bool:
    level = str(row.get("confidenceLevel") or row.get("confidence") or "").lower()
    if "medium_high" in level:
        return True
    return any(token in level for token in WEAK_CONFIDENCE_TOKENS)


def route_video_keys(route: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for chapter in route.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        for field in ("videos", "fileIds", "videoIds"):
            for value in chapter.get(field) or []:
                keys.add(str(value))
        for value in chapter.get("videoPaths") or []:
            keys.add(str(value))
        for value in chapter.get("videoNames") or []:
            keys.add(str(value))
    return keys


def add_check(checks: list[dict[str, Any]], name: str, status: str, evidence: Any) -> None:
    checks.append({"name": name, "status": status, "evidence": evidence})


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve() if args.package_dir else None
    project_dir = infer_project_dir(package_dir, args.project_dir)
    report_path, recognition, pointer = latest_recognition_report(project_dir)
    media_index = load_json(project_dir / "media_index.json") or {}
    confirmed_route = load_json(project_dir / "confirmed_route_timeline.json") or {}

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    caveats: list[str] = []

    if not isinstance(recognition, dict):
        add_check(checks, "Latest footage recognition report exists", "blocked", {"projectDir": str(project_dir)})
        blockers.append("latest_footage_recognition_route_report.json or its target report is missing.")
        recognition = {}
    else:
        add_check(
            checks,
            "Latest footage recognition report exists",
            "passed",
            {"pointer": str(project_dir / "latest_footage_recognition_route_report.json"), "report": str(report_path), "status": recognition.get("status")},
        )

    if recognition.get("status") and recognition.get("status") not in READY_STATUSES:
        blockers.append(f"Recognition report status is not ready: {recognition.get('status')}.")

    media_files = [row for row in media_index.get("files") or [] if isinstance(row, dict) and is_video_file(row)]
    indexed_video_count = int((media_index.get("summary") or {}).get("videoCount") or len(media_files) or 0)
    exclusion_keys = active_source_exclusion_keys(recognition)
    active_media = [row for row in media_files if row_key(row) not in exclusion_keys and str(row.get("path") or "") not in exclusion_keys and str(row.get("name") or "") not in exclusion_keys]
    expected_active_count = int((recognition.get("summary") or {}).get("mediaVideoCount") or len(active_media) or max(0, indexed_video_count - len(exclusion_keys)))

    rows = [row for row in recognition.get("rows") or [] if isinstance(row, dict)]
    active_rows = [row for row in rows if not is_excluded_row(row, exclusion_keys)]
    recognized_rows = [row for row in active_rows if is_recognized_row(row)]
    unknown_rows = [row for row in active_rows if not is_recognized_row(row)]
    coverage_ratio = len(recognized_rows) / expected_active_count if expected_active_count else 0.0

    source_accounting_ok = indexed_video_count > 0 and expected_active_count > 0 and len(active_rows) == expected_active_count
    if source_accounting_ok:
        source_status = "passed"
    else:
        source_status = "blocked"
        blockers.append(
            f"Source accounting mismatch: indexed={indexed_video_count}, expectedActive={expected_active_count}, activeRows={len(active_rows)}."
        )
    add_check(
        checks,
        "Source accounting separates original videos from excluded derived exports",
        source_status,
        {
            "indexedVideoCount": indexed_video_count,
            "expectedActiveSourceCount": expected_active_count,
            "activeRecognitionRows": len(active_rows),
            "activeSourceExclusionCount": len(exclusion_keys),
            "sourceExclusions": recognition.get("sourceExclusions") or [],
        },
    )

    recognition_ok = coverage_ratio >= args.min_coverage and not unknown_rows and not recognition.get("unrecognizedVideos")
    if not recognition_ok:
        blockers.append(
            f"Per-video recognition coverage is incomplete: recognized={len(recognized_rows)}/{expected_active_count}, ratio={coverage_ratio:.4f}."
        )
    add_check(
        checks,
        "Every active source video has a conservative location row",
        "passed" if recognition_ok else "blocked",
        {
            "recognizedVideoCount": len(recognized_rows),
            "expectedActiveSourceCount": expected_active_count,
            "coverageRatio": round(coverage_ratio, 4),
            "minCoverage": args.min_coverage,
            "unknownRows": [row.get("name") or row.get("path") for row in unknown_rows[:20]],
        },
    )

    summary = recognition.get("summary") if isinstance(recognition.get("summary"), dict) else {}
    codex = recognition.get("codexVisualEvidence") if isinstance(recognition.get("codexVisualEvidence"), dict) else {}
    frame_count = int(summary.get("frameCount") or codex.get("sampledFrameCoverage") or 0)
    frames_per_video = frame_count / expected_active_count if expected_active_count else 0.0
    frame_ok = frame_count >= expected_active_count * args.min_frames_per_video
    if not frame_ok:
        blockers.append(f"Frame evidence is too sparse: {frame_count} frames for {expected_active_count} active videos.")
    add_check(
        checks,
        "Frame/contact-sheet evidence is broad enough for visual route review",
        "passed" if frame_ok else "blocked",
        {
            "frameCount": frame_count,
            "expectedActiveSourceCount": expected_active_count,
            "framesPerVideo": round(frames_per_video, 3),
            "minFramesPerVideo": args.min_frames_per_video,
            "codexSampledFrameCoverage": codex.get("sampledFrameCoverage"),
        },
    )

    primary_provider = summary.get("primaryRecognitionProvider") or codex.get("provider") or summary.get("cloudProviderUsed")
    cloud_frames_sent = int(summary.get("cloudFramesSent") or 0)
    cloud_errors = summary.get("cloudRecognitionErrors") or []
    codex_coverage = int(codex.get("sourceVideoCoverage") or summary.get("codexVisualSourceCoverage") or 0)
    codex_ready = codex.get("status") in READY_STATUSES and codex_coverage >= expected_active_count > 0
    provider_status = "passed"
    if primary_provider == "codex_visual_inspection" and codex_ready:
        provider_status = "caveat"
        caveats.append("Primary location evidence is Codex visual inspection of sampled frames, not GPS/per-clip geolocation.")
    elif cloud_frames_sent <= 0 and cloud_errors:
        provider_status = "blocked"
        blockers.append("Cloud recognition appears requested but did not successfully process frames, and no full Codex visual coverage replaces it.")
    if cloud_errors and codex_ready:
        caveats.append("Mimo/cloud provider did not successfully process frames in this pass; Codex visual inspection is the effective provider.")
    add_check(
        checks,
        "Recognition provider provenance is explicit and not overstated",
        provider_status,
        {
            "primaryRecognitionProvider": primary_provider,
            "codexVisualStatus": codex.get("status"),
            "codexVisualSourceCoverage": codex_coverage,
            "cloudProviderUsed": summary.get("cloudProviderUsed"),
            "cloudFramesSent": cloud_frames_sent,
            "cloudRecognitionErrors": cloud_errors,
            "localModelUsed": summary.get("localModelUsed"),
        },
    )

    route_keys = route_video_keys(confirmed_route) if isinstance(confirmed_route, dict) else set()
    active_keys = {str(row.get("fileId") or row.get("path") or row.get("name")) for row in active_rows}
    route_missing = sorted(key for key in active_keys if key and key not in route_keys)
    chapter_count = int(confirmed_route.get("chapterCount") or len(confirmed_route.get("chapters") or [])) if isinstance(confirmed_route, dict) else 0
    needs_review_count = int(confirmed_route.get("needsHumanReviewCount") or 0) if isinstance(confirmed_route, dict) else 0
    route_ok = chapter_count >= 2 and needs_review_count == 0 and not route_missing
    if not route_ok:
        blockers.append(
            f"Confirmed route is not fully linked to active videos: chapters={chapter_count}, needsReview={needs_review_count}, missing={len(route_missing)}."
        )
    route_confidence = str(confirmed_route.get("routeConfidence") or "")
    if "uncertainty" in route_confidence.lower() or "not gps" in route_confidence.lower():
        caveats.append("Confirmed route is explicitly usable with honest uncertainty, not exact per-clip truth.")
    add_check(
        checks,
        "Confirmed route links active videos into multi-chapter travel order",
        "passed" if route_ok else "blocked",
        {
            "chapterCount": chapter_count,
            "needsHumanReviewCount": needs_review_count,
            "routeVideoCoverage": len(active_keys) - len(route_missing),
            "expectedActiveSourceCount": len(active_keys),
            "missingRouteVideoKeys": route_missing[:20],
            "routeConfidence": route_confidence,
        },
    )

    derived_sources = recognition.get("derivedSources") or []
    excluded_derived = recognition.get("excludedDerivedSources") or []
    if derived_sources:
        blockers.append("Derived/prior render files remain active as source material.")
    add_check(
        checks,
        "Derived or prior-render files are excluded from raw-source claims",
        "passed" if not derived_sources else "blocked",
        {"activeDerivedSources": derived_sources, "excludedDerivedSources": excluded_derived},
    )

    verified_rows = [row for row in active_rows if verified_reason(row)]
    gps_rows = [row for row in active_rows if truthy(row.get("hasGPS"))]
    weak_rows = [row for row in active_rows if weak_confidence(row)]
    exact_ok = expected_active_count > 0 and len(verified_rows) >= expected_active_count
    if weak_rows:
        caveats.append(f"{len(weak_rows)}/{expected_active_count} active videos carry medium/weak visual confidence labels.")
    if not gps_rows:
        caveats.append("No active source video has GPS metadata.")
    if args.require_verified_per_clip_location and not exact_ok:
        blockers.append(
            f"Verified per-clip location was required but only {len(verified_rows)}/{expected_active_count} active videos have GPS/user/cloud-verified labels."
        )
    add_check(
        checks,
        "Per-video exact location truth is not claimed without verification",
        "passed" if exact_ok else ("blocked" if args.require_verified_per_clip_location else "caveat"),
        {
            "requireVerifiedPerClipLocation": args.require_verified_per_clip_location,
            "verifiedPerClipLocationCount": len(verified_rows),
            "gpsMetadataVideoCount": len(gps_rows),
            "expectedActiveSourceCount": expected_active_count,
            "weakConfidenceVideoCount": len(weak_rows),
            "confidenceCounts": summary.get("confidenceCounts"),
            "sampleWeakConfidenceVideos": [row.get("name") for row in weak_rows[:20]],
        },
    )

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    caveats = sorted(set(caveats))
    base_route_blockers = [item for item in blockers if not item.startswith("Verified per-clip location was required")]
    route_claim_allowed = not base_route_blockers and recognition_ok and route_ok
    exact_claim_allowed = not blockers and exact_ok
    if exact_claim_allowed:
        claim_level = "per_clip_verified"
    elif route_claim_allowed and blockers:
        claim_level = "strict_per_clip_blocked_but_visual_route_ready"
    elif route_claim_allowed:
        claim_level = "visual_route_ready_with_caveats"
    else:
        claim_level = "blocked"
    status = "blocked" if blockers else ("passed" if exact_claim_allowed and not warnings and not caveats else "passed_with_caveats")
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir) if package_dir else None,
        "projectDir": str(project_dir),
        "recognitionReport": str(report_path) if report_path else None,
        "latestRecognitionPointer": pointer,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "caveats": caveats,
        "summary": {
            "indexedVideoCount": indexed_video_count,
            "expectedActiveSourceCount": expected_active_count,
            "activeRecognitionRows": len(active_rows),
            "recognizedVideoCount": len(recognized_rows),
            "recognitionCoverageRatio": round(coverage_ratio, 4),
            "frameCount": frame_count,
            "framesPerVideo": round(frames_per_video, 3),
            "chapterCount": chapter_count,
            "routeVideoCoverage": len(active_keys) - len(route_missing),
            "verifiedPerClipLocationCount": len(verified_rows),
            "gpsMetadataVideoCount": len(gps_rows),
            "weakConfidenceVideoCount": len(weak_rows),
            "cloudFramesSent": cloud_frames_sent,
            "cloudRecognitionErrorCount": len(cloud_errors),
            "primaryRecognitionProvider": primary_provider,
            "claimLevel": claim_level,
            "routeAwareEditClaimAllowed": route_claim_allowed,
            "exactPerVideoLocationClaimAllowed": exact_claim_allowed,
        },
        "claimContract": {
            "routeAwareEdit": "allowed" if route_claim_allowed else "blocked",
            "exactPerVideoLocation": "allowed" if exact_claim_allowed else "not_allowed",
            "requiredLanguage": (
                "Say the route/place order is reconstructed from visual frame review and chronology. "
                "Do not claim GPS-grade or verified per-clip location unless exactPerVideoLocation is allowed."
            ),
        },
        "nextActions": next_actions(blockers, caveats, args.require_verified_per_clip_location),
    }
    return report


def next_actions(blockers: list[str], caveats: list[str], strict: bool) -> list[str]:
    actions: list[str] = []
    if blockers:
        actions.append("Fix blockers before building or claiming a route-aware delivery package.")
    if strict or any("Verified per-clip" in item for item in blockers):
        actions.append("For exact per-video location truth, add GPS/user-confirmed labels or run an approved cloud vision pass with valid credentials and per-video evidence.")
    if caveats:
        actions.append("Keep customer-facing copy conservative: visual route reconstruction, not verified GPS/per-clip geolocation.")
    if not actions:
        actions.append("Location truth contract is clean; continue to package/style QA.")
    return actions


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Location Truth Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Project: `{report['projectDir']}`",
        f"Package: `{report.get('packageDir')}`",
        f"Recognition report: `{report.get('recognitionReport')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Claim Contract",
        "",
        "```json",
        json.dumps(report["claimContract"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Checks",
    ]
    for row in report["checks"]:
        evidence = json.dumps(row.get("evidence"), ensure_ascii=False)[:2200]
        lines.extend(["", f"### {row['name']}", f"- Status: `{row['status']}`", f"- Evidence: `{evidence}`"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("caveats"):
        lines.extend(["", "## Caveats"])
        lines.extend(f"- {item}" for item in report["caveats"])
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report["nextActions"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether route/location evidence supports the claimed per-video location truth level.")
    parser.add_argument("--package-dir")
    parser.add_argument("--project-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--min-coverage", type=float, default=0.98)
    parser.add_argument("--min-frames-per-video", type=float, default=3.0)
    parser.add_argument("--require-verified-per-clip-location", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.package_dir and not args.project_dir:
        parser.error("Pass --package-dir, --project-dir, or both.")
    report = build_report(args)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else (
        Path(args.package_dir).expanduser().resolve() if args.package_dir else Path(report["projectDir"])
    )
    write_json(output_dir / "location_truth_contract_audit.json", report)
    write_markdown(output_dir / "location_truth_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "caveats": report["caveats"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
