#!/usr/bin/env python3
"""Audit whether current transition language matches the learned reference profile."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROFILE_BATCH_STATUS = "ready_with_reference_batch_profile"
PROFILE_SINGLE_STATUS = "ready_with_single_reference_profile"
READY_REPORTS: dict[str, tuple[str, set[str]]] = {
    "transitionEffectPalette": ("transition_effect_palette_contract_audit.json", {"passed"}),
    "transitionVisualMatch": ("transition_visual_match_contract_audit.json", {"passed"}),
    "transitionChoreographyPlan": (
        "transition_choreography_plan/transition_choreography_plan.json",
        {"ready_with_transition_choreography_plan"},
    ),
    "transitionChoreographyContract": ("transition_choreography_contract_audit.json", {"passed"}),
    "transitionStoryboard": ("transition_storyboard_contract_audit.json", {"passed"}),
}
MOTION_FAMILIES = {"motivated_motion_accent"}
CLEAN_MATCH_BREATH_FAMILIES = {
    "clean_continuity_cut",
    "visual_match_cut",
    "mood_dissolve_breath",
    "scenic_title_breath",
    "ending_aftertaste_hold",
}
BRIDGE_BREATH_FAMILIES = {
    "route_bridge_triptych",
    "texture_bridge_cutaway",
    "scenic_title_breath",
    "ending_aftertaste_hold",
}


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


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def find_reference_profile(package_dir: Path, explicit: str | None) -> tuple[dict[str, Any], Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        [
            package_dir / "reference" / "reference_batch_profile.json",
            package_dir / "reference" / "reference_analysis.json",
        ]
    )
    for path in candidates:
        data = load_json(path)
        if isinstance(data, dict):
            return data, path
    return {}, candidates[0] if candidates else package_dir / "reference" / "reference_batch_profile.json"


def profile_ready(profile: dict[str, Any], path: Path, args: argparse.Namespace) -> dict[str, Any]:
    summary = summary_of(profile)
    pacing = profile.get("pacingProfile") if isinstance(profile.get("pacingProfile"), dict) else {}
    audio = profile.get("audioProfile") if isinstance(profile.get("audioProfile"), dict) else {}
    style_targets = profile.get("styleTargets") if isinstance(profile.get("styleTargets"), dict) else {}
    contract = profile.get("referenceUsageContract") if isinstance(profile.get("referenceUsageContract"), dict) else {}
    source_safety = profile.get("safety") if isinstance(profile.get("safety"), dict) else {}
    status = profile.get("status")
    accepted_status = status == PROFILE_BATCH_STATUS or (args.allow_single_reference and status == PROFILE_SINGLE_STATUS)
    reference_count = as_int(summary.get("referenceVideoCount"))
    usage_allowed = str(contract.get("allowed") or "").lower()
    usage_forbidden = str(contract.get("forbidden") or "").lower()
    ready = (
        path.exists()
        and accepted_status
        and reference_count >= args.min_reference_videos
        and pacing.get("status") == "analyzed"
        and audio.get("status") == "analyzed"
        and as_int(pacing.get("estimatedShotCount")) > 0
        and isinstance(style_targets, dict)
        and bool(style_targets)
        and "non-copying" in usage_allowed
        and "copy" in usage_forbidden
        and source_safety.get("writesResolve") is False
        and source_safety.get("downloadsExternalAssets") is False
    )
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": status,
        "acceptedStatus": accepted_status,
        "referenceVideoCount": reference_count,
        "minimumReferenceVideos": args.min_reference_videos,
        "pacingStatus": pacing.get("status"),
        "audioStatus": audio.get("status"),
        "estimatedShotCount": pacing.get("estimatedShotCount"),
        "styleTargetsPresent": bool(style_targets),
        "transitionTarget": style_targets.get("transitionTarget"),
        "usageAllowed": contract.get("allowed"),
        "usageForbidden": contract.get("forbidden"),
        "writesResolve": source_safety.get("writesResolve"),
        "downloadsExternalAssets": source_safety.get("downloadsExternalAssets"),
        "ready": ready,
    }


def transition_targets(profile: dict[str, Any]) -> dict[str, Any]:
    style_targets = profile.get("styleTargets") if isinstance(profile.get("styleTargets"), dict) else {}
    raw = style_targets.get("transitionStyleTargets") if isinstance(style_targets.get("transitionStyleTargets"), dict) else {}
    return {
        "maxMotionShare": as_float(raw.get("maxMotionShare"), 0.25),
        "minCleanMatchBreathShare": as_float(raw.get("minCleanMatchBreathShare"), 0.45),
        "minBridgeBreathImportantCoverage": as_float(raw.get("minBridgeBreathImportantCoverage"), 1.0),
        "maxDominantFamilyShare": as_float(raw.get("maxDominantFamilyShare"), 0.65),
        "maxFamilyRun": as_int(raw.get("maxFamilyRun"), 4),
        "requireBgmHit": raw.get("requireBgmHit", True) is not False,
        "requireCaptionQuietZone": raw.get("requireCaptionQuietZone", True) is not False,
        "forbidHighIntensity": raw.get("forbidHighIntensity", True) is not False,
    }


def report_row(package_dir: Path, report_id: str, rel_path: str, accepted: set[str]) -> dict[str, Any]:
    path = package_dir / rel_path
    data = load_json(path) or {}
    summary = summary_of(data)
    return {
        "id": report_id,
        "path": str(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "acceptedStatuses": sorted(accepted),
        "passed": path.exists() and data.get("status") in accepted and not data.get("blockers"),
        "summary": summary,
        "blockers": data.get("blockers") or [],
    }


def choreography_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = plan.get("choreographyRows") if isinstance(plan.get("choreographyRows"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def has_three_beats(row: dict[str, Any]) -> bool:
    beats = row.get("threeBeatChoreography") if isinstance(row.get("threeBeatChoreography"), list) else []
    roles = {beat.get("role") for beat in beats if isinstance(beat, dict) and beat.get("action")}
    return {"outgoing", "bridge_or_motion", "landing"}.issubset(roles)


def row_has_bgm_hit(row: dict[str, Any]) -> bool:
    bgm = row.get("bgmChoreography") if isinstance(row.get("bgmChoreography"), dict) else {}
    return bgm.get("target") == "cut_or_effect_on_bgm_phrase_hit" and as_float(bgm.get("hitToleranceSeconds"), 99.0) <= 0.35


def row_has_caption_quiet_zone(row: dict[str, Any]) -> bool:
    caption = row.get("captionAndTitlePolicy") if isinstance(row.get("captionAndTitlePolicy"), dict) else {}
    return caption.get("avoidTitleCollision") is True and as_float(caption.get("quietZoneBeforeSeconds")) >= 0.25


def max_run(values: list[str]) -> int:
    best = 0
    current = 0
    previous = None
    for value in values:
        if value == previous:
            current += 1
        else:
            current = 1
            previous = value
        best = max(best, current)
    return best


def transition_language_summary(package_dir: Path, reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    choreography = load_json(package_dir / "transition_choreography_plan" / "transition_choreography_plan.json") or {}
    contract_summary = reports["transitionChoreographyContract"].get("summary") or {}
    rows = choreography_rows(choreography)
    families = [str(row.get("choreographyFamily") or "") for row in rows]
    family_counts: dict[str, int] = {}
    for family in families:
        family_counts[family] = family_counts.get(family, 0) + 1
    total = len(rows)
    important_rows = [row for row in rows if row.get("importantBoundary")]
    clean_match_breath_count = sum(1 for family in families if family in CLEAN_MATCH_BREATH_FAMILIES)
    bridge_breath_rows = [row for row in rows if str(row.get("choreographyFamily") or "") in BRIDGE_BREATH_FAMILIES]
    important_bridge_breath_count = sum(
        1 for row in important_rows if str(row.get("choreographyFamily") or "") in BRIDGE_BREATH_FAMILIES
    )
    motion_count = sum(1 for family in families if family in MOTION_FAMILIES)
    dominant_share = max(family_counts.values()) / total if total else 0.0
    return {
        "transitionRowCount": total,
        "importantBoundaryCount": len(important_rows),
        "importantRowsWithThreeBeatCount": sum(1 for row in important_rows if has_three_beats(row)),
        "motionFamilyCount": motion_count,
        "motionShare": round(motion_count / total, 3) if total else 0.0,
        "cleanMatchBreathCount": clean_match_breath_count,
        "cleanMatchBreathShare": round(clean_match_breath_count / total, 3) if total else 0.0,
        "bridgeBreathCount": len(bridge_breath_rows),
        "importantBridgeBreathCount": important_bridge_breath_count,
        "importantBridgeBreathCoverage": round(important_bridge_breath_count / len(important_rows), 3) if important_rows else 1.0,
        "bgmHitRowCount": sum(1 for row in rows if row_has_bgm_hit(row)),
        "captionQuietZoneRowCount": sum(1 for row in rows if row_has_caption_quiet_zone(row)),
        "highIntensityRowCount": as_int(contract_summary.get("highIntensityRowCount")),
        "blockedChoreographyRowCount": as_int(contract_summary.get("blockedChoreographyRowCount")),
        "maxFamilyRun": max_run(families),
        "dominantFamilyShare": round(dominant_share, 3),
        "choreographyFamilyCounts": family_counts,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    profile, profile_path = find_reference_profile(package_dir, args.reference_profile)
    profile_info = profile_ready(profile, profile_path, args)
    targets = transition_targets(profile)
    reports = {
        report_id: report_row(package_dir, report_id, rel_path, accepted)
        for report_id, (rel_path, accepted) in READY_REPORTS.items()
    }
    language = transition_language_summary(package_dir, reports)
    blockers: list[str] = []
    warnings: list[str] = []
    if not profile_info["ready"]:
        blockers.append("reference batch profile is not ready enough to anchor transition style")
    for row in reports.values():
        if not row["exists"]:
            blockers.append(f"{row['id']} is missing")
        elif row["status"] not in row["acceptedStatuses"]:
            blockers.append(f"{row['id']} has status {row['status']}, expected {row['acceptedStatuses']}")
        elif row.get("blockers"):
            blockers.append(f"{row['id']} still has blockers")
    total = as_int(language.get("transitionRowCount"))
    if total < 1:
        blockers.append("transition choreography has no rows")
    if as_int(language.get("blockedChoreographyRowCount")) > 0:
        blockers.append("transition choreography still contains blocked rows")
    if targets["forbidHighIntensity"] and as_int(language.get("highIntensityRowCount")) > 0:
        blockers.append("high-intensity transition rows are not allowed for the reference profile")
    if as_int(language.get("importantRowsWithThreeBeatCount")) < as_int(language.get("importantBoundaryCount")):
        blockers.append("important transitions do not all have outgoing/bridge-or-motion/landing choreography")
    if total >= 4 and as_float(language.get("motionShare")) > as_float(targets["maxMotionShare"]):
        blockers.append(
            f"motion transition share {language.get('motionShare')} exceeds reference target {targets['maxMotionShare']}"
        )
    if total >= 3 and as_float(language.get("cleanMatchBreathShare")) < as_float(targets["minCleanMatchBreathShare"]):
        blockers.append(
            "clean/match/breath transition share is below the reference-style floor"
        )
    if as_float(language.get("importantBridgeBreathCoverage")) < as_float(targets["minBridgeBreathImportantCoverage"]):
        blockers.append("important route/title/day/ending transitions lack bridge-or-breath coverage")
    if as_int(language.get("maxFamilyRun")) > as_int(targets["maxFamilyRun"]):
        blockers.append("transition family repeats too many times in a row")
    if total >= 4 and as_float(language.get("dominantFamilyShare")) > as_float(targets["maxDominantFamilyShare"]):
        blockers.append("one transition family dominates the film beyond the reference target")
    if targets["requireBgmHit"] and as_int(language.get("bgmHitRowCount")) < total:
        blockers.append("not every transition row carries BGM-hit choreography")
    if targets["requireCaptionQuietZone"] and as_int(language.get("captionQuietZoneRowCount")) < total:
        blockers.append("not every transition row carries caption/title quiet-zone policy")
    if total < 4:
        warnings.append("transition sample is small; dominant-share and motion-share checks are lenient")
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "referenceProfile": str(profile_path),
            "referenceProfileExists": profile_path.exists(),
            "minReferenceVideos": args.min_reference_videos,
            "allowSingleReference": args.allow_single_reference,
        },
        "summary": {
            "referenceProfileStatus": profile_info["status"],
            "referenceVideoCount": profile_info["referenceVideoCount"],
            "transitionRowCount": language["transitionRowCount"],
            "importantBoundaryCount": language["importantBoundaryCount"],
            "motionShare": language["motionShare"],
            "cleanMatchBreathShare": language["cleanMatchBreathShare"],
            "importantBridgeBreathCoverage": language["importantBridgeBreathCoverage"],
            "maxFamilyRun": language["maxFamilyRun"],
            "dominantFamilyShare": language["dominantFamilyShare"],
            "readyReportCount": sum(1 for row in reports.values() if row.get("passed")),
            "requiredReportCount": len(reports),
            "blockerCount": len(blockers),
            "warningCount": len(warnings),
        },
        "referenceProfile": profile_info,
        "transitionTargets": targets,
        "transitionLanguage": language,
        "reports": list(reports.values()),
        "blockers": blockers,
        "warnings": warnings,
        "acceptanceRubric": {
            "pass": [
                "Reference profile is ready and non-copying.",
                "Effect palette, visual match, choreography, and storyboard contracts pass.",
                "Motion accents stay rare while clean cuts, matches, bridges, and breath holds carry most boundaries.",
                "Important boundaries have bridge-or-breath coverage plus three-beat choreography.",
            ],
            "reject": [
                "The cut relies on repeated rotation, whip, push, speed-ramp, flash, or template transitions.",
                "Reference analysis exists but current transitions do not reflect the learned pacing and bridge language.",
                "Important day/place/title/ending boundaries lack bridge footage, breath, or landing intent.",
            ],
        },
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Reference Transition Profile Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Targets",
        "",
        "```json",
        json.dumps(report["transitionTargets"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Transition Language",
        "",
        "```json",
        json.dumps(report["transitionLanguage"], ensure_ascii=False, indent=2),
        "```",
    ]
    if report["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Required Reports"])
    for row in report["reports"]:
        lines.extend(
            [
                "",
                f"### {row['id']}",
                f"- Status: `{row.get('status')}`",
                f"- Passed: `{row.get('passed')}`",
                f"- Path: `{row.get('path')}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit reference-style transition profile application.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--reference-profile", help="Optional explicit reference_batch_profile.json path.")
    parser.add_argument("--min-reference-videos", type=int, default=2)
    parser.add_argument("--allow-single-reference", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "reference_transition_profile_contract_audit.json", report)
    write_markdown(package_dir / "reference_transition_profile_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
