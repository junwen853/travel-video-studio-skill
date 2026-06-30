#!/usr/bin/env python3
"""Audit whether a Travel Video Studio package is ready for long-form delivery."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "delivery_plan.json",
    "long_form_structure.md",
    "voiceover_script.txt",
    "subtitles.srt",
    "delivery_assets_report.json",
    "asset_search_plan.md",
    "asset_ledger/asset_license_ledger.json",
    "asset_sourcing/asset_sourcing_packet.json",
    "bgm_cues.md",
    "edit_decision_plan.md",
    "resolve_timeline_enrichment.json",
    "resolve_timeline_blueprint.json",
    "resolve_blueprint_preflight.json",
    "davinci_build_notes.md",
    "qa_checklist.md",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_info(path: Path) -> dict[str, Any]:
    return {"exists": path.exists(), "size": path.stat().st_size if path.exists() else 0, "path": str(path)}


def ffprobe_duration(path: Path) -> float | None:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return None


def audit_assets(ledger: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"total": 0, "unverifiedBgmOrStock": 0, "fontsAvailable": 0, "unverifiedFonts": 0}
    if not ledger:
        blockers.append("Asset license ledger is missing.")
        return blockers, warnings, summary
    items = ledger.get("items", [])
    summary["total"] = len(items)
    for item in items:
        asset_type = item.get("type")
        status = item.get("licenseStatus")
        local = item.get("localPath")
        selected = item.get("selectedAssetUrl")
        if asset_type in {"bgm", "aerial_or_stock"}:
            if status in {"", None, "unverified"} or (not local and not selected):
                summary["unverifiedBgmOrStock"] += 1
        if asset_type == "font" and status == "system-font-render-only" and local and item.get("matchStatus", "matched") == "matched":
            summary["fontsAvailable"] += 1
        if asset_type == "font" and status != "system-font-render-only":
            summary["unverifiedFonts"] += 1
    if summary["unverifiedBgmOrStock"]:
        blockers.append(f"{summary['unverifiedBgmOrStock']} BGM/stock/aerial asset rows are still unverified.")
    if summary["fontsAvailable"] == 0:
        warnings.append("No local font match found in asset ledger.")
    if summary["unverifiedFonts"]:
        warnings.append(f"{summary['unverifiedFonts']} preferred font rows need a verified font source or approved fallback.")
    return blockers, warnings, summary


def audit_asset_sourcing(packet: dict[str, Any] | None, package_dir: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(packet), "status": None, "unverifiedBgmOrStock": None, "rowCount": 0, "providerCount": 0}
    if not packet:
        blockers.append("Asset sourcing packet is missing; generate it before selecting BGM/stock/aerial assets.")
        return blockers, warnings, summary
    packet_summary = packet.get("summary") or {}
    summary.update(
        {
            "status": packet.get("status"),
            "unverifiedBgmOrStock": packet_summary.get("unverifiedBgmOrStock"),
            "rowCount": packet_summary.get("rowCount", 0),
            "providerCount": len(packet.get("providerDirectory") or []),
            "packetMarkdown": str(package_dir / "asset_sourcing" / "asset_sourcing_packet.md"),
        }
    )
    source_ledger = packet.get("sourceAssetLedger")
    expected_ledger = str(package_dir / "asset_ledger" / "asset_license_ledger.json")
    if source_ledger and Path(source_ledger).expanduser().resolve() != Path(expected_ledger).resolve():
        warnings.append("Asset sourcing packet points at a different asset ledger.")
    if packet.get("status") == "blocked" and packet_summary.get("unverifiedBgmOrStock"):
        warnings.append("Asset sourcing packet is ready for selection work but still has unverified BGM/stock/aerial rows.")
    if not packet.get("providerDirectory"):
        blockers.append("Asset sourcing packet has no provider/license directory.")
    return blockers, warnings, summary


def audit_delivery_assets(report: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(report), "status": None, "titleCards": None, "voiceover": None}
    if not report:
        warnings.append("Delivery assets report is missing; run prepare_delivery_assets.py for title cards and optional local voiceover.")
        return blockers, warnings, summary
    title_cards = report.get("titleCards") or {}
    voiceover = report.get("voiceover") or {}
    summary.update(
        {
            "status": report.get("status"),
            "titleCards": title_cards.get("status"),
            "titleCardCount": title_cards.get("cardCount"),
            "voiceover": voiceover.get("status"),
            "voiceoverGenerated": voiceover.get("generated"),
            "resolveEnrichmentRefreshed": (report.get("resolveEnrichment") or {}).get("refreshed"),
        }
    )
    if title_cards.get("status") not in {"ready", "exists"}:
        warnings.append("Delivery assets report says title/place cards are not ready.")
    if voiceover.get("status") not in {"ready", "exists"}:
        warnings.append("Delivery assets report says voiceover audio is not ready.")
    return blockers, warnings, summary


def is_no_voiceover_mode(delivery: dict[str, Any] | None, blueprint: dict[str, Any] | None) -> bool:
    if isinstance(delivery, dict) and (delivery.get("voiceover") or {}).get("mode") == "text_only_user_requested_no_voiceover_audio":
        return True
    if isinstance(blueprint, dict) and blueprint.get("voiceoverDisabled") is True:
        return True
    audio_plan = blueprint.get("audioPlan") if isinstance(blueprint, dict) and isinstance(blueprint.get("audioPlan"), dict) else {}
    voiceover = audio_plan.get("voiceover") if isinstance(audio_plan.get("voiceover"), dict) else {}
    return str(voiceover.get("status") or "").startswith("disabled_")


def required_file_satisfied(package_dir: Path, name: str, no_voiceover: bool) -> bool:
    primary = package_dir / name
    if primary.exists() and primary.stat().st_size > 0:
        return True
    if no_voiceover and name == "voiceover_script.txt":
        alt = package_dir / "narration_text_only_v4.txt"
        return alt.exists() and alt.stat().st_size > 0
    if name == "subtitles.srt":
        alt = package_dir / "subtitles_v4_dense.srt"
        return alt.exists() and alt.stat().st_size > 0
    return False


def load_route_review(project_dir: str | None) -> dict[str, Any] | None:
    if not project_dir:
        return None
    pointer_path = Path(project_dir).expanduser().resolve() / "latest_route_review.json"
    if not pointer_path.exists():
        return None
    try:
        pointer = load_json(pointer_path)
        review_path = Path(pointer.get("routeReview", "")).expanduser()
        if review_path.exists():
            return load_json(review_path)
    except Exception:  # noqa: BLE001
        return None
    return None


def load_route_coverage_scaffold(project_dir: str | None) -> dict[str, Any] | None:
    if not project_dir:
        return None
    pointer_path = Path(project_dir).expanduser().resolve() / "latest_route_coverage_scaffold.json"
    if not pointer_path.exists():
        return None
    try:
        pointer = load_json(pointer_path)
        scaffold_path = Path(pointer.get("scaffold", "")).expanduser()
        if scaffold_path.exists():
            return load_json(scaffold_path)
    except Exception:  # noqa: BLE001
        return None
    return None


def audit_route_coverage_scaffold(scaffold: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(scaffold), "status": None, "coverageRatio": None, "chapterCount": None}
    if not scaffold:
        warnings.append("Route coverage scaffold is missing; run build_route_coverage_scaffold.py if route coverage is low.")
        return blockers, warnings, summary
    summary.update(
        {
            "status": scaffold.get("status"),
            "coverageRatio": scaffold.get("coverage", {}).get("coverageRatio"),
            "coveredVideoCount": scaffold.get("coverage", {}).get("coveredVideoCount"),
            "mediaVideoCount": scaffold.get("coverage", {}).get("mediaVideoCount"),
            "chapterCount": scaffold.get("chapterCount"),
            "scaffoldMarkdown": scaffold.get("scaffoldMarkdown"),
            "contactSheet": scaffold.get("contactSheet"),
        }
    )
    if scaffold.get("coverage", {}).get("coverageRatio", 0) < 0.65:
        blockers.append("Route coverage scaffold does not cover enough media.")
    elif scaffold.get("status") == "review_needed":
        warnings.append("Route coverage scaffold exists and still requires review.")
    return blockers, warnings, summary


def audit_route_review(route_review: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(route_review), "status": None, "reviewMarkdown": None, "contactSheet": None}
    if not route_review:
        warnings.append("Route review packet is missing; run prepare_route_review.py before confirming route chapters.")
        return blockers, warnings, summary
    summary.update(
        {
            "status": route_review.get("status"),
            "reviewMarkdown": route_review.get("reviewMarkdown"),
            "contactSheet": route_review.get("contactSheet"),
            "coverageRatio": route_review.get("coverage", {}).get("coverageRatio"),
            "uncoveredVideoCount": route_review.get("coverage", {}).get("uncoveredVideoCount"),
            "declaredRegions": route_review.get("project", {}).get("declaredRegions"),
            "inferredRegions": route_review.get("project", {}).get("inferredRegions"),
        }
    )
    if route_review.get("status") == "blocked":
        blockers.append("Route review packet is blocked; resolve it before final route-aware cutting.")
    elif route_review.get("status") == "review_needed":
        warnings.append("Route review packet still needs decisions.")
    return blockers, warnings, summary


def load_route_decision_sheet(project_dir: str | None) -> dict[str, Any] | None:
    if not project_dir:
        return None
    pointer_path = Path(project_dir).expanduser().resolve() / "latest_route_decision_sheet.json"
    if not pointer_path.exists():
        return None
    try:
        pointer = load_json(pointer_path)
        sheet_path = Path(pointer.get("decisionSheet", "")).expanduser()
        if sheet_path.exists():
            return load_json(sheet_path)
    except Exception:  # noqa: BLE001
        return None
    return None


def audit_route_decision_sheet(sheet: dict[str, Any] | None, route_review: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    rows = sheet.get("decisionRows") if isinstance(sheet, dict) and isinstance(sheet.get("decisionRows"), list) else []
    summary = {"exists": bool(sheet), "status": None, "rowCount": 0, "filledDecisionCount": 0}
    if not sheet:
        if route_review and route_review.get("status") in {"blocked", "review_needed"}:
            warnings.append("Route decision sheet is missing; run prepare_route_decision_sheet.py before editing chapter decisions.")
        return blockers, warnings, summary
    filled = sum(1 for row in rows if row.get("reviewDecision"))
    summary.update(
        {
            "status": sheet.get("status"),
            "decisionSheetJson": sheet.get("decisionSheetJson"),
            "decisionSheetMarkdown": sheet.get("decisionSheetMarkdown"),
            "rowCount": len(rows),
            "filledDecisionCount": filled,
            "regionMismatch": (sheet.get("projectRegionReview") or {}).get("mismatch"),
            "blockerCount": len(sheet.get("blockers") or []),
        }
    )
    if sheet.get("blockers"):
        blockers.append("Route decision sheet still needs approval or chapter decisions.")
    elif rows and filled < len(rows):
        warnings.append("Route decision sheet exists but not all chapter decisions are filled.")
    return blockers, warnings, summary


def load_route_decision_application(project_dir: str | None) -> dict[str, Any] | None:
    if not project_dir:
        return None
    review_root = Path(project_dir).expanduser().resolve() / "route_review"
    if not review_root.exists():
        return None
    reports = sorted(review_root.glob("*/route_decision_application.json"))
    if not reports:
        return None
    try:
        return load_json(max(reports, key=lambda p: p.stat().st_mtime))
    except Exception:  # noqa: BLE001
        return None


def audit_route_decision_application(report: dict[str, Any] | None, route_decision: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(report), "status": None, "applied": False, "wouldApply": False}
    if not report:
        if route_decision:
            warnings.append("Route decision application report is missing; run apply_route_decision_sheet.py before candidate generation.")
        return blockers, warnings, summary
    report_summary = report.get("summary") or {}
    summary.update(
        {
            "status": report.get("status"),
            "applied": bool(report.get("applied")),
            "wouldApply": bool(report.get("wouldApply")),
            "rowCount": report_summary.get("rowCount"),
            "filledDecisionCount": report_summary.get("filledDecisionCount"),
            "blockerCount": len(report.get("blockers") or []),
        }
    )
    if report.get("status") == "blocked":
        warnings.append("Route decision application is blocked until the decision sheet is approved and filled.")
    return blockers, warnings, summary


def load_confirmed_route_candidate(project_dir: str | None) -> dict[str, Any] | None:
    if not project_dir:
        return None
    pointer_path = Path(project_dir).expanduser().resolve() / "latest_confirmed_route_candidate.json"
    if not pointer_path.exists():
        return None
    try:
        pointer = load_json(pointer_path)
        candidate_path = Path(pointer.get("candidate", "")).expanduser()
        if candidate_path.exists():
            return load_json(candidate_path)
    except Exception:  # noqa: BLE001
        return None
    return None


def load_confirmed_route(project_dir: str | None) -> dict[str, Any] | None:
    if not project_dir:
        return None
    path = Path(project_dir).expanduser().resolve() / "confirmed_route_timeline.json"
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:  # noqa: BLE001
        return None


def is_applied_codex_visual_route(route: dict[str, Any] | None) -> bool:
    if not route:
        return False
    chapters = route.get("chapters") or []
    return (
        route.get("mode") == "codex_visual_confirmed_route"
        and int(route.get("chapterCount") or len(chapters)) >= 2
        and int(route.get("sourceVideoCount") or 0) > 0
        and int(route.get("needsHumanReviewCount") or 0) == 0
        and all(chapter.get("reviewDecision") == "codex_visual_confirmed" for chapter in chapters)
    )


def audit_confirmed_route_candidate(candidate: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(candidate), "status": None, "canApply": False, "candidateMarkdown": None}
    if not candidate:
        warnings.append("Confirmed route candidate is missing; run prepare_confirmed_route_candidate.py after route review.")
        return blockers, warnings, summary
    summary.update(
        {
            "status": candidate.get("status"),
            "canApply": bool(candidate.get("canApply")),
            "candidateJson": candidate.get("candidateJson"),
            "candidateMarkdown": candidate.get("candidateMarkdown"),
            "chapterCount": candidate.get("candidate", {}).get("chapterCount"),
            "draftChapterCount": len(candidate.get("draftChapters") or []),
        }
    )
    if candidate.get("status") == "blocked":
        blockers.append("Confirmed route candidate is blocked; resolve candidate blockers before writing confirmed_route_timeline.json.")
    elif not candidate.get("canApply"):
        warnings.append("Confirmed route candidate exists but is not marked apply-ready.")
    return blockers, warnings, summary


def audit_blueprint(blueprint: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {
        "clipCount": 0,
        "coverageRatio": 0,
        "titleCards": 0,
        "sourceAudioClipCount": 0,
        "videoOnlyClipCount": 0,
        "missingSources": [],
        "subtitleCueCount": 0,
        "timelineMarkerCount": 0,
        "bgmCueCount": 0,
        "stockPlaceholderCount": 0,
        "transitionCount": 0,
        "voiceoverPlanStatus": None,
        "longFormCoverage": None,
    }
    if not blueprint:
        blockers.append("Resolve timeline blueprint is missing.")
        return blockers, warnings, summary
    clips = blueprint.get("clips", [])
    summary["clipCount"] = len(clips)
    summary["coverageRatio"] = float(blueprint.get("coverageRatio") or 0)
    title_roles = {"title_card", "place_card", "chapter_title_bridge"}
    summary["titleCards"] = sum(1 for c in clips if c.get("role") in title_roles)
    summary["sourceAudioClipCount"] = sum(1 for c in clips if c.get("includeSourceAudio"))
    summary["videoOnlyClipCount"] = max(0, summary["clipCount"] - summary["sourceAudioClipCount"])
    audio_plan = blueprint.get("audioPlan") if isinstance(blueprint.get("audioPlan"), dict) else {}
    summary["subtitleCueCount"] = len(blueprint.get("subtitleCues") or [])
    summary["timelineMarkerCount"] = len(blueprint.get("timelineMarkers") or [])
    summary["bgmCueCount"] = len(audio_plan.get("bgmCues") or [])
    summary["stockPlaceholderCount"] = len(blueprint.get("stockInsertPlan") or [])
    summary["transitionCount"] = len(blueprint.get("transitionPlan") or [])
    summary["voiceoverPlanStatus"] = (audio_plan.get("voiceover") or {}).get("status") if isinstance(audio_plan.get("voiceover"), dict) else None
    summary["longFormCoverage"] = blueprint.get("longFormCoverage")
    missing = sorted({c.get("sourcePath") for c in clips if c.get("sourcePath") and not Path(c["sourcePath"]).exists()})
    summary["missingSources"] = missing
    if missing:
        blockers.append(f"{len(missing)} Resolve blueprint source files are missing.")
    if summary["clipCount"] == 0:
        blockers.append("Resolve blueprint has no clips.")
    if summary["coverageRatio"] < 0.65:
        blockers.append(f"Resolve blueprint coverage ratio is {summary['coverageRatio']:.3f}; long-form target needs more selected footage/assets.")
    elif summary["coverageRatio"] < 0.9:
        warnings.append(f"Resolve blueprint coverage ratio is {summary['coverageRatio']:.3f}; still weak for a 20-minute film.")
    if summary["titleCards"] == 0:
        warnings.append("No title/place cards found in Resolve blueprint.")
    if summary["sourceAudioClipCount"] == 0:
        warnings.append("No Resolve blueprint clips are marked to preserve source/camera audio on A1.")
    if summary["subtitleCueCount"] == 0:
        warnings.append("Resolve blueprint has no parsed subtitle cues.")
    if summary["timelineMarkerCount"] == 0:
        warnings.append("Resolve blueprint has no chapter/audio/stock/transition markers.")
    if summary["bgmCueCount"] == 0:
        warnings.append("Resolve blueprint has no BGM cue plan.")
    if summary["stockPlaceholderCount"] == 0:
        warnings.append("Resolve blueprint has no stock/aerial placeholder plan.")
    if not summary["voiceoverPlanStatus"]:
        warnings.append("Resolve blueprint has no voiceover import/mix plan.")
    return blockers, warnings, summary


def audit_resolve_enrichment(enrichment: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(enrichment), "status": None, "subtitleCueCount": 0, "timelineMarkerCount": 0, "stockPlaceholderCount": 0}
    if not enrichment:
        warnings.append("Resolve timeline enrichment report is missing; run enrich_resolve_blueprint.py after package changes.")
        return blockers, warnings, summary
    enrichment_summary = enrichment.get("summary") or {}
    summary.update(
        {
            "status": enrichment.get("status"),
            "subtitleCueCount": enrichment_summary.get("subtitleCueCount", 0),
            "timelineMarkerCount": enrichment_summary.get("timelineMarkerCount", 0),
            "voiceoverExists": enrichment_summary.get("voiceoverExists"),
            "bgmCueCount": enrichment_summary.get("bgmCueCount", 0),
            "stockPlaceholderCount": enrichment_summary.get("stockPlaceholderCount", 0),
            "transitionCount": enrichment_summary.get("transitionCount", 0),
            "unverifiedBgmCueCount": enrichment_summary.get("unverifiedBgmCueCount", 0),
            "unverifiedStockPlaceholderCount": enrichment_summary.get("unverifiedStockPlaceholderCount", 0),
        }
    )
    if summary["subtitleCueCount"] == 0:
        warnings.append("Resolve enrichment has no subtitle cues.")
    if summary["timelineMarkerCount"] == 0:
        warnings.append("Resolve enrichment has no timeline markers.")
    return blockers, warnings, summary


def audit_resolve_blueprint_preflight(preflight: dict[str, Any] | None, blueprint: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    clip_summary = preflight.get("clipSummary") if isinstance(preflight, dict) and isinstance(preflight.get("clipSummary"), dict) else {}
    enrichment = preflight.get("enrichmentSummary") if isinstance(preflight, dict) and isinstance(preflight.get("enrichmentSummary"), dict) else {}
    summary = {
        "exists": bool(preflight),
        "status": None,
        "clipCount": None,
        "sourceFileCount": None,
        "missingSourceCount": None,
        "invalidRangeCount": None,
        "outOfBoundsCount": None,
        "overlapCount": None,
        "v1GapCount": None,
        "sourceAudioClipCount": None,
        "titleCardCount": None,
        "subtitleCueCount": None,
        "timelineMarkerCount": None,
        "voiceoverStatus": None,
    }
    if not preflight:
        blockers.append("Resolve blueprint preflight is missing; run audit_resolve_blueprint.py before Resolve --apply.")
        return blockers, warnings, summary
    summary.update(
        {
            "status": preflight.get("status"),
            "clipCount": clip_summary.get("clipCount"),
            "sourceFileCount": clip_summary.get("sourceFileCount"),
            "missingSourceCount": clip_summary.get("missingSourceCount"),
            "invalidRangeCount": clip_summary.get("invalidRangeCount"),
            "outOfBoundsCount": clip_summary.get("outOfBoundsCount"),
            "overlapCount": clip_summary.get("overlapCount"),
            "v1GapCount": clip_summary.get("v1GapCount"),
            "sourceAudioClipCount": clip_summary.get("sourceAudioClipCount"),
            "titleCardCount": clip_summary.get("titleCardCount"),
            "subtitleCueCount": enrichment.get("subtitleCueCount"),
            "timelineMarkerCount": enrichment.get("timelineMarkerCount"),
            "voiceoverStatus": enrichment.get("voiceoverStatus"),
            "blockerCount": len(preflight.get("blockers") or []),
            "warningCount": len(preflight.get("warnings") or []),
        }
    )
    if blueprint and preflight.get("blueprint") and Path(preflight["blueprint"]).expanduser().resolve() != Path(blueprint.get("blueprintPath", preflight["blueprint"])).expanduser().resolve():
        warnings.append("Resolve blueprint preflight points at a different blueprint path.")
    if preflight.get("status") == "blocked":
        blockers.extend(f"Resolve blueprint preflight: {item}" for item in preflight.get("blockers") or [])
    elif preflight.get("status") == "ready_with_warnings":
        warnings.extend(f"Resolve blueprint preflight: {item}" for item in preflight.get("warnings") or [])
    return blockers, warnings, summary


def load_asset_reconciliation(package_dir: Path) -> dict[str, Any] | None:
    path = package_dir / "asset_sourcing" / "asset_decision_reconciliation.json"
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:  # noqa: BLE001
        return None


def audit_asset_reconciliation(report: dict[str, Any] | None, asset_summary: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(report), "status": None, "applied": False}
    if not report:
        if asset_summary.get("unverifiedBgmOrStock"):
            warnings.append("Asset decision reconciliation report is missing; run apply_asset_sourcing_decisions.py after filling sourcing decisions.")
        return blockers, warnings, summary
    report_summary = report.get("summary") or {}
    summary.update(
        {
            "status": report.get("status"),
            "applied": bool(report.get("applied")),
            "decisionRowsFilled": report_summary.get("decisionRowsFilled"),
            "verifiedBgmOrStock": report_summary.get("verifiedBgmOrStock"),
            "unverifiedBgmOrStock": report_summary.get("unverifiedBgmOrStock"),
            "blockerCount": len(report.get("blockers") or []),
        }
    )
    if report.get("status") == "blocked" and asset_summary.get("unverifiedBgmOrStock"):
        warnings.append("Asset decision reconciliation confirms BGM/stock/aerial decisions are still incomplete.")
    return blockers, warnings, summary


def audit_render_plan(render_plan: dict[str, Any] | None, blueprint: dict[str, Any] | None, package_dir: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(render_plan), "queued": False, "started": False, "targetDir": None, "customName": None}
    if not render_plan:
        warnings.append("Resolve render plan has not been prepared yet.")
        return blockers, warnings, summary
    summary.update(
        {
            "queued": bool(render_plan.get("queued")),
            "started": bool(render_plan.get("started")),
            "targetDir": render_plan.get("targetDir"),
            "customName": render_plan.get("customName"),
            "requestedFormat": render_plan.get("requestedFormat"),
            "requestedCodec": render_plan.get("requestedCodec"),
        }
    )
    if render_plan.get("packageDir") and Path(render_plan["packageDir"]).resolve() != package_dir:
        warnings.append("render_plan.json points at a different package directory.")
    if blueprint:
        if render_plan.get("projectName") != blueprint.get("projectName"):
            warnings.append("render_plan.json project name differs from the Resolve blueprint.")
        if render_plan.get("timelineName") != blueprint.get("timelineName"):
            warnings.append("render_plan.json timeline name differs from the Resolve blueprint.")
    settings = render_plan.get("renderSettings") or {}
    summary["settings"] = {
        "width": settings.get("FormatWidth"),
        "height": settings.get("FormatHeight"),
        "fps": settings.get("FrameRate"),
        "videoQuality": settings.get("VideoQuality"),
        "exportsVideo": settings.get("ExportVideo"),
        "exportsAudio": settings.get("ExportAudio"),
    }
    for key in ("TargetDir", "CustomName", "ExportVideo", "ExportAudio", "FormatWidth", "FormatHeight", "FrameRate", "VideoQuality"):
        if key not in settings:
            blockers.append(f"render_plan.json is missing render setting: {key}")
    if settings.get("ExportVideo") is not True:
        blockers.append("render_plan.json does not export video.")
    if settings.get("ExportAudio") is not True:
        blockers.append("render_plan.json does not export audio.")
    if "VideoQuality" in settings:
        raw_quality = settings.get("VideoQuality")
        numeric_quality = None
        if isinstance(raw_quality, (int, float)):
            numeric_quality = float(raw_quality)
        elif isinstance(raw_quality, str) and raw_quality.strip().isdigit():
            numeric_quality = float(raw_quality.strip())
        elif str(raw_quality) not in {"High", "Best"}:
            blockers.append("render_plan.json VideoQuality must be numeric high bitrate, High, or Best.")
        if numeric_quality is not None and numeric_quality < 60000:
            blockers.append("render_plan.json VideoQuality is below the 60000 high-bitrate floor for 4K masters.")
    if render_plan.get("gate", {}).get("blockers"):
        warnings.append("render_plan.json was created while render gates still had blockers.")
    if render_plan.get("error"):
        warnings.append(f"render_plan.json records a failed queue/start attempt: {render_plan['error']}")
    return blockers, warnings, summary


def load_resolve_apply_contract(package_dir: Path) -> dict[str, Any] | None:
    path = package_dir / "resolve_apply_contract.json"
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:  # noqa: BLE001
        return None


def audit_resolve_apply_contract(contract: dict[str, Any] | None, blueprint: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(contract), "status": None, "projectName": None, "timelineName": None}
    if not contract:
        warnings.append("Resolve apply contract is missing; run prepare_resolve_apply_contract.py before requesting Resolve --apply approval.")
        return blockers, warnings, summary
    clip_plan = contract.get("clipPlan") if isinstance(contract.get("clipPlan"), dict) else {}
    summary.update(
        {
            "status": contract.get("status"),
            "projectName": contract.get("projectName"),
            "timelineName": contract.get("timelineName"),
            "clipCount": clip_plan.get("clipCount"),
            "sourceFileCount": clip_plan.get("sourceFileCount"),
            "blockerCount": len(contract.get("blockers") or []),
            "requiresApproval": (contract.get("approval") or {}).get("required"),
        }
    )
    if blueprint:
        if contract.get("projectName") != blueprint.get("projectName"):
            warnings.append("Resolve apply contract project name differs from blueprint.")
        if contract.get("timelineName") != blueprint.get("timelineName"):
            warnings.append("Resolve apply contract timeline name differs from blueprint.")
    if contract.get("status") == "blocked":
        warnings.append("Resolve apply contract exists but is blocked by delivery gates.")
    elif contract.get("status") == "awaiting_user_approval":
        warnings.append("Resolve apply contract is waiting for explicit user approval before --apply.")
    return blockers, warnings, summary


def audit_resolve_readback(resolve_audit: dict[str, Any] | None, blueprint: dict[str, Any] | None) -> tuple[list[str], list[str], dict[str, Any]]:
    blockers: list[str] = []
    warnings: list[str] = []
    summary = {"exists": bool(resolve_audit), "projectName": None, "timelineName": None, "videoItems": 0, "audioItems": 0, "subtitleItems": 0}
    if not resolve_audit:
        warnings.append("Resolve readback audit is missing; run audit_resolve_timeline.py after an actual Resolve timeline write.")
        return blockers, warnings, summary
    summary["projectName"] = resolve_audit.get("projectName")
    summary["timelineName"] = resolve_audit.get("timelineName")
    for track_type in ("video", "audio", "subtitle"):
        summary[f"{track_type}Items"] = sum(row.get("itemCount", 0) for row in resolve_audit.get("tracks", {}).get(track_type, []))
    if blueprint:
        if resolve_audit.get("projectName") != blueprint.get("projectName"):
            blockers.append("Resolve readback audit project name does not match the blueprint.")
        if resolve_audit.get("timelineName") != blueprint.get("timelineName"):
            blockers.append("Resolve readback audit timeline name does not match the blueprint.")
    if summary["videoItems"] <= 0:
        blockers.append("Resolve readback audit found no video items.")
    for warning in resolve_audit.get("warnings") or []:
        blockers.append(f"Resolve readback warning: {warning}")
    return blockers, warnings, summary


def audit_package(package_dir: Path) -> dict[str, Any]:
    files = {name: file_info(package_dir / name) for name in REQUIRED_FILES}
    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[dict[str, str]] = []

    delivery = load_json(package_dir / "delivery_plan.json") if (package_dir / "delivery_plan.json").exists() else None
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") if (package_dir / "resolve_timeline_blueprint.json").exists() else None
    if isinstance(blueprint, dict):
        blueprint["blueprintPath"] = str(package_dir / "resolve_timeline_blueprint.json")
    no_voiceover = is_no_voiceover_mode(delivery, blueprint)
    if no_voiceover:
        files["narration_text_only_v4.txt"] = file_info(package_dir / "narration_text_only_v4.txt")
    if (package_dir / "subtitles_v4_dense.srt").exists():
        files["subtitles_v4_dense.srt"] = file_info(package_dir / "subtitles_v4_dense.srt")

    for name in REQUIRED_FILES:
        if not required_file_satisfied(package_dir, name, no_voiceover):
            blockers.append(f"Required file missing or empty: {name}")
    resolve_enrichment = load_json(package_dir / "resolve_timeline_enrichment.json") if (package_dir / "resolve_timeline_enrichment.json").exists() else None
    blueprint_preflight = load_json(package_dir / "resolve_blueprint_preflight.json") if (package_dir / "resolve_blueprint_preflight.json").exists() else None
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") if (package_dir / "asset_ledger" / "asset_license_ledger.json").exists() else None
    asset_sourcing = (
        load_json(package_dir / "asset_sourcing" / "asset_sourcing_packet.json")
        if (package_dir / "asset_sourcing" / "asset_sourcing_packet.json").exists()
        else None
    )
    delivery_assets = load_json(package_dir / "delivery_assets_report.json") if (package_dir / "delivery_assets_report.json").exists() else None
    render_plan = load_json(package_dir / "render_plan.json") if (package_dir / "render_plan.json").exists() else None
    resolve_audit = load_json(package_dir / "resolve_audit.json") if (package_dir / "resolve_audit.json").exists() else None
    route_review = load_route_review(delivery.get("projectDir") if isinstance(delivery, dict) else None)
    route_decision_sheet = load_route_decision_sheet(delivery.get("projectDir") if isinstance(delivery, dict) else None)
    route_decision_application = load_route_decision_application(delivery.get("projectDir") if isinstance(delivery, dict) else None)
    route_scaffold = load_route_coverage_scaffold(delivery.get("projectDir") if isinstance(delivery, dict) else None)
    route_candidate = load_confirmed_route_candidate(delivery.get("projectDir") if isinstance(delivery, dict) else None)
    confirmed_route = load_confirmed_route(delivery.get("projectDir") if isinstance(delivery, dict) else None)
    codex_visual_route_applied = is_applied_codex_visual_route(confirmed_route)
    asset_reconciliation = load_asset_reconciliation(package_dir)
    resolve_apply_contract = load_resolve_apply_contract(package_dir)

    if delivery:
        for warning in delivery.get("warnings", []):
            warnings.append(f"Delivery warning: {warning}")
        if any(ch.get("needsHumanReview") for ch in delivery.get("chapters", [])):
            blockers.append("At least one route chapter still needs human review.")
            if route_review and route_review.get("reviewMarkdown"):
                route_command = (
                    f"Open {route_review.get('reviewMarkdown')} and "
                    f"{route_review.get('contactSheet') or 'the generated contact sheet'}, resolve blockers, then create a fresh confirmed_route_timeline.json."
                )
            else:
                project_dir = delivery.get("projectDir") or "<project-dir>"
                route_command = f"python3 <skill-dir>/scripts/prepare_route_review.py --project-dir {project_dir}"
            next_actions.append(
                {
                    "priority": "P0",
                    "action": "Review and confirm route chapters",
                    "command": route_command,
                }
            )
        target_minutes = float(delivery.get("target", {}).get("durationMinutes") or 0)
        if target_minutes < 15:
            blockers.append("Target duration is below long-form threshold.")
    else:
        target_minutes = 0.0

    bp_blockers, bp_warnings, bp_summary = audit_blueprint(blueprint)
    blockers.extend(bp_blockers)
    warnings.extend(bp_warnings)

    enrichment_blockers, enrichment_warnings, enrichment_summary = audit_resolve_enrichment(resolve_enrichment)
    blockers.extend(enrichment_blockers)
    warnings.extend(enrichment_warnings)

    preflight_blockers, preflight_warnings, preflight_summary = audit_resolve_blueprint_preflight(blueprint_preflight, blueprint)
    blockers.extend(preflight_blockers)
    warnings.extend(preflight_warnings)

    asset_blockers, asset_warnings, asset_summary = audit_assets(ledger)
    blockers.extend(asset_blockers)
    warnings.extend(asset_warnings)

    sourcing_blockers, sourcing_warnings, sourcing_summary = audit_asset_sourcing(asset_sourcing, package_dir)
    blockers.extend(sourcing_blockers)
    warnings.extend(sourcing_warnings)

    delivery_assets_blockers, delivery_assets_warnings, delivery_assets_summary = audit_delivery_assets(delivery_assets)
    blockers.extend(delivery_assets_blockers)
    if no_voiceover:
        delivery_assets_warnings = [item for item in delivery_assets_warnings if "voiceover" not in item.lower()]
    warnings.extend(delivery_assets_warnings)

    route_scaffold_blockers, route_scaffold_warnings, route_scaffold_summary = audit_route_coverage_scaffold(route_scaffold)
    blockers.extend(route_scaffold_blockers)
    warnings.extend(route_scaffold_warnings)

    if codex_visual_route_applied:
        route_review_summary = {
            "exists": bool(route_review),
            "status": "superseded_by_codex_visual_confirmed_route",
            "confirmedRouteMode": confirmed_route.get("mode"),
            "confirmedRouteChapterCount": confirmed_route.get("chapterCount"),
            "confirmedRouteSourceVideoCount": confirmed_route.get("sourceVideoCount"),
        }
        route_decision_summary = {"exists": bool(route_decision_sheet), "status": "not_required_codex_visual_route_applied"}
        route_application_summary = {"exists": bool(route_decision_application), "status": "not_required_codex_visual_route_applied"}
    else:
        route_review_blockers, route_review_warnings, route_review_summary = audit_route_review(route_review)
        blockers.extend(route_review_blockers)
        warnings.extend(route_review_warnings)

        route_decision_blockers, route_decision_warnings, route_decision_summary = audit_route_decision_sheet(route_decision_sheet, route_review)
        blockers.extend(route_decision_blockers)
        warnings.extend(route_decision_warnings)

        route_application_blockers, route_application_warnings, route_application_summary = audit_route_decision_application(
            route_decision_application, route_decision_sheet
        )
        blockers.extend(route_application_blockers)
        warnings.extend(route_application_warnings)

    route_candidate_blockers, route_candidate_warnings, route_candidate_summary = audit_confirmed_route_candidate(route_candidate)
    blockers.extend(route_candidate_blockers)
    warnings.extend(route_candidate_warnings)

    asset_reconciliation_blockers, asset_reconciliation_warnings, asset_reconciliation_summary = audit_asset_reconciliation(asset_reconciliation, asset_summary)
    blockers.extend(asset_reconciliation_blockers)
    warnings.extend(asset_reconciliation_warnings)

    render_blockers, render_warnings, render_summary = audit_render_plan(render_plan, blueprint, package_dir)
    blockers.extend(render_blockers)
    warnings.extend(render_warnings)

    contract_blockers, contract_warnings, contract_summary = audit_resolve_apply_contract(resolve_apply_contract, blueprint)
    blockers.extend(contract_blockers)
    warnings.extend(contract_warnings)

    resolve_blockers, resolve_warnings, resolve_summary = audit_resolve_readback(resolve_audit, blueprint)
    blockers.extend(resolve_blockers)
    warnings.extend(resolve_warnings)

    voiceover_path = package_dir / "voiceover" / "voiceover.m4a"
    voiceover_duration = ffprobe_duration(voiceover_path) if voiceover_path.exists() else None
    if no_voiceover:
        if voiceover_path.exists():
            warnings.append("Voiceover audio file exists, but blueprint is configured to keep voiceover out of the render.")
    elif not voiceover_path.exists():
        warnings.append("Voiceover audio has not been generated yet.")
        next_actions.append(
            {
                "priority": "P0",
                "action": "Generate voiceover audio",
                "command": f"python3 <skill-dir>/scripts/prepare_delivery_assets.py --package-dir {package_dir} --generate-local-voiceover",
            }
        )
    elif not voiceover_duration:
        blockers.append("Voiceover audio exists but duration could not be probed.")

    title_manifest = package_dir / "title_cards" / "title_cards_manifest.json"
    if not title_manifest.exists():
        warnings.append("Title/place card manifest is missing.")
        next_actions.append(
            {
                "priority": "P0",
                "action": "Generate title/place cards and update blueprint",
                "command": f"python3 <skill-dir>/scripts/prepare_delivery_assets.py --package-dir {package_dir}",
            }
        )

    if not delivery_assets:
        next_actions.append(
            {
                "priority": "P0",
                "action": "Prepare local delivery assets report",
                "command": f"python3 <skill-dir>/scripts/prepare_delivery_assets.py --package-dir {package_dir}",
            }
        )

    if not resolve_enrichment or not enrichment_summary.get("timelineMarkerCount") or not enrichment_summary.get("subtitleCueCount"):
        next_actions.append(
            {
                "priority": "P0",
                "action": "Refresh Resolve timeline enrichment",
                "command": f"python3 <skill-dir>/scripts/enrich_resolve_blueprint.py --package-dir {package_dir}",
            }
        )
    if not blueprint_preflight or preflight_summary.get("status") == "blocked":
        next_actions.append(
            {
                "priority": "P0",
                "action": "Preflight Resolve blueprint before apply",
                "command": f"python3 <skill-dir>/scripts/audit_resolve_blueprint.py --blueprint {package_dir / 'resolve_timeline_blueprint.json'} --package-dir {package_dir}",
            }
        )

    if not asset_sourcing:
        next_actions.append(
            {
                "priority": "P0",
                "action": "Prepare asset sourcing packet",
                "command": f"python3 <skill-dir>/scripts/prepare_asset_sourcing_packet.py --package-dir {package_dir}",
            }
        )
    elif asset_summary.get("unverifiedBgmOrStock"):
        next_actions.append(
            {
                "priority": "P0",
                "action": "Refresh asset sourcing packet after ledger edits",
                "command": f"python3 <skill-dir>/scripts/prepare_asset_sourcing_packet.py --package-dir {package_dir}",
            }
        )
        next_actions.append(
            {
                "priority": "P0",
                "action": "Select and verify BGM/stock/aerial assets",
                "command": f"Open and update {package_dir / 'asset_ledger' / 'asset_license_ledger.json'} with selectedAssetUrl/localPath and verified licenseStatus.",
            }
        )
        next_actions.append(
            {
                "priority": "P0",
                "action": "Reconcile filled asset sourcing decisions",
                "command": f"python3 <skill-dir>/scripts/apply_asset_sourcing_decisions.py --package-dir {package_dir}",
            }
        )

    if not codex_visual_route_applied and (not route_scaffold or (route_scaffold.get("coverage", {}).get("coverageRatio") or 0) < 0.65):
        project_dir = delivery.get("projectDir") if isinstance(delivery, dict) else "<project-dir>"
        next_actions.append(
            {
                "priority": "P0",
                "action": "Build route coverage scaffold",
                "command": f"python3 <skill-dir>/scripts/build_route_coverage_scaffold.py --project-dir {project_dir}",
            }
        )
    elif not codex_visual_route_applied and route_review and route_review.get("route", {}).get("sourceKind") != "route_coverage_scaffold":
        project_dir = delivery.get("projectDir") if isinstance(delivery, dict) else "<project-dir>"
        scaffold_path = route_scaffold.get("scaffoldJson") or "<route_coverage_scaffold.json>"
        next_actions.append(
            {
                "priority": "P0",
                "action": "Regenerate route review from full scaffold",
                "command": f"python3 <skill-dir>/scripts/prepare_route_review.py --project-dir {project_dir} --route-source {scaffold_path}",
            }
        )

    if not codex_visual_route_applied and route_review and (not route_decision_sheet or route_decision_sheet.get("status") != "approved"):
        project_dir = delivery.get("projectDir") if isinstance(delivery, dict) else "<project-dir>"
        next_actions.append(
            {
                "priority": "P0",
                "action": "Prepare or fill route decision sheet",
                "command": f"python3 <skill-dir>/scripts/prepare_route_decision_sheet.py --project-dir {project_dir}",
            }
        )
    if not codex_visual_route_applied and route_decision_sheet and (not route_decision_application or route_decision_application.get("status") == "blocked"):
        project_dir = delivery.get("projectDir") if isinstance(delivery, dict) else "<project-dir>"
        next_actions.append(
            {
                "priority": "P0",
                "action": "Validate or apply route decision sheet",
                "command": f"python3 <skill-dir>/scripts/apply_route_decision_sheet.py --project-dir {project_dir}",
            }
        )

    if not route_candidate or route_candidate.get("status") == "blocked":
        project_dir = delivery.get("projectDir") if isinstance(delivery, dict) else "<project-dir>"
        next_actions.append(
            {
                "priority": "P0",
                "action": "Prepare or repair confirmed route candidate",
                "command": f"python3 <skill-dir>/scripts/prepare_confirmed_route_candidate.py --project-dir {project_dir}",
            }
        )

    if not render_plan:
        next_actions.append(
            {
                "priority": "P1",
                "action": "Prepare Resolve render plan",
                "command": f"python3 <skill-dir>/scripts/prepare_resolve_render.py --package-dir {package_dir}",
            }
        )
    if not resolve_apply_contract:
        next_actions.append(
            {
                "priority": "P1",
                "action": "Prepare Resolve apply approval contract",
                "command": f"python3 <skill-dir>/scripts/prepare_resolve_apply_contract.py --package-dir {package_dir}",
            }
        )

    if not resolve_audit:
        project_name = blueprint.get("projectName") if blueprint else "<project>"
        timeline_name = blueprint.get("timelineName") if blueprint else "<timeline>"
        next_actions.append(
            {
                "priority": "P1",
                "action": "Read back actual Resolve timeline",
                "command": f"python3 <skill-dir>/scripts/audit_resolve_timeline.py --project-name \"{project_name}\" --timeline-name \"{timeline_name}\" --output {package_dir / 'resolve_audit.json'}",
            }
        )

    if bp_summary.get("coverageRatio", 0) < 0.65:
        next_actions.append(
            {
                "priority": "P0",
                "action": "Increase timeline coverage for long-form film",
                "command": "Select more source ranges, add approved aerial/stock, or extend chapter pacing before Resolve apply.",
            }
        )

    if not resolve_audit and not any(action["action"].startswith("Dry-run Resolve") for action in next_actions):
        next_actions.append(
            {
                "priority": "P1",
                "action": "Dry-run Resolve timeline",
                "command": f"python3 <skill-dir>/scripts/build_resolve_timeline.py --blueprint {package_dir / 'resolve_timeline_blueprint.json'}",
            }
        )

    render_gate_allowed = bool(render_plan and (render_plan.get("gate") or {}).get("allowed") is True)
    render_ready = bool(render_plan and resolve_audit and render_gate_allowed and not blockers)
    if blockers:
        status = "blocked"
    elif not resolve_audit:
        # Resolve readback is only possible after an approved timeline write.
        # Non-blocking warnings should not prevent the apply contract from
        # reaching the explicit approval gate.
        status = "ready_for_resolve_write"
    elif render_ready and warnings:
        status = "ready_for_final_render_with_warnings"
    elif render_ready:
        status = "ready_for_final_render"
    elif warnings:
        status = "draft"
    elif render_plan:
        status = "ready_for_final_render"
    else:
        status = "draft"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "packageDir": str(package_dir),
        "status": status,
        "targetMinutes": target_minutes,
        "files": files,
        "blueprintSummary": bp_summary,
        "resolveEnrichmentSummary": enrichment_summary,
        "resolveBlueprintPreflightSummary": preflight_summary,
        "assetSummary": asset_summary,
        "assetSourcingSummary": sourcing_summary,
        "deliveryAssetsSummary": delivery_assets_summary,
        "routeScaffoldSummary": route_scaffold_summary,
        "routeReviewSummary": route_review_summary,
        "routeDecisionSummary": route_decision_summary,
        "routeDecisionApplicationSummary": route_application_summary,
        "routeCandidateSummary": route_candidate_summary,
        "assetDecisionSummary": asset_reconciliation_summary,
        "resolveApplyContractSummary": contract_summary,
        "renderSummary": render_summary,
        "resolveAuditSummary": resolve_summary,
        "voiceover": {
            "path": str(voiceover_path),
            "exists": voiceover_path.exists(),
            "durationSeconds": voiceover_duration,
            "disabledByUserRequest": no_voiceover,
            "textOnlyNarration": str(package_dir / "narration_text_only_v4.txt") if no_voiceover else None,
        },
        "blockers": blockers,
        "warnings": warnings,
        "nextActions": next_actions,
        "finalRenderAllowed": render_ready or (status == "ready_for_final_render" and not asset_summary.get("unverifiedBgmOrStock")),
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Delivery Audit",
        "",
        f"Status: `{report['status']}`",
        f"Final render allowed: `{report['finalRenderAllowed']}`",
        f"Target minutes: {report['targetMinutes']}",
        f"Coverage ratio: {report['blueprintSummary'].get('coverageRatio')}",
        f"Long-form fill: `{report['blueprintSummary'].get('longFormCoverage')}`",
        f"Source-audio clips: `{report['blueprintSummary'].get('sourceAudioClipCount')}`",
        f"Resolve enrichment: `{report['resolveEnrichmentSummary'].get('status') or report['resolveEnrichmentSummary'].get('exists')}`",
        f"Resolve blueprint preflight: `{report['resolveBlueprintPreflightSummary'].get('status') or report['resolveBlueprintPreflightSummary'].get('exists')}`",
        f"Delivery assets: `{report['deliveryAssetsSummary'].get('status') or report['deliveryAssetsSummary'].get('exists')}`",
        f"Asset sourcing: `{report['assetSourcingSummary'].get('status') or report['assetSourcingSummary'].get('exists')}`",
        f"Asset decision reconciliation: `{report['assetDecisionSummary'].get('status') or report['assetDecisionSummary'].get('exists')}`",
        f"Route scaffold: `{report['routeScaffoldSummary'].get('coverageRatio') if report['routeScaffoldSummary'].get('exists') else False}`",
        f"Route review: `{report['routeReviewSummary'].get('status') or report['routeReviewSummary'].get('exists')}`",
        f"Route decision sheet: `{report['routeDecisionSummary'].get('status') or report['routeDecisionSummary'].get('exists')}`",
        f"Route decision application: `{report['routeDecisionApplicationSummary'].get('status') or report['routeDecisionApplicationSummary'].get('exists')}`",
        f"Route candidate: `{report['routeCandidateSummary'].get('status') or report['routeCandidateSummary'].get('exists')}`",
        f"Resolve apply contract: `{report['resolveApplyContractSummary'].get('status') or report['resolveApplyContractSummary'].get('exists')}`",
        f"Render plan: `{report['renderSummary'].get('exists')}`",
        f"Resolve readback audit: `{report['resolveAuditSummary'].get('exists')}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in report["blockers"] or ["None"])
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {item}" for item in report["warnings"] or ["None"])
    lines.append("")
    lines.append("## Next Actions")
    for action in report["nextActions"]:
        lines.append(f"- [{action['priority']}] {action['action']}: `{action['command']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a long-form Travel Video Studio package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = audit_package(package_dir)
    (package_dir / "delivery_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(package_dir / "delivery_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Delivery audit status: {report['status']}")
        for blocker in report["blockers"]:
            print(f"BLOCKER: {blocker}")
        for action in report["nextActions"]:
            print(f"NEXT {action['priority']}: {action['action']}")
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
