#!/usr/bin/env python3
"""Create a conservative route decision proposal without approving or applying it."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import default_app_dir, discover_project_path


DEFAULT_APP_DIR = default_app_dir()
APPLY_DECISIONS = {"confirmed", "corrected", "split", "merge", "exclude"}


def load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    return max(existing, key=lambda p: p.stat().st_mtime) if existing else None


def resolve_sheet_path(args: argparse.Namespace) -> Path:
    if args.decision_sheet:
        path = Path(args.decision_sheet).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Decision sheet not found: {path}")
        return path
    project_dir = discover_project_path(Path(args.project_dir).expanduser().resolve(), args.project_name)
    pointer = load_json(project_dir / "latest_route_decision_sheet.json")
    if isinstance(pointer, dict) and pointer.get("decisionSheet"):
        path = Path(pointer["decisionSheet"]).expanduser().resolve()
        if path.exists():
            return path
    path = latest(sorted(project_dir.glob("route_review/*/route_decision_sheet.json")))
    if path:
        return path
    raise SystemExit(f"No route_decision_sheet.json found under {project_dir}")


def clean(value: Any, fallback: str = "") -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def confidence_value(row: dict[str, Any]) -> float:
    try:
        return float(row.get("confidence") or 0.0)
    except Exception:  # noqa: BLE001
        return 0.0


def confidence_band(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.6:
        return "medium"
    return "low"


def proposal_for_row(row: dict[str, Any], strict_confidence: float) -> dict[str, Any]:
    suggested = clean(row.get("suggestedDecision"))
    confidence = confidence_value(row)
    band = confidence_band(confidence)
    risk_flags: list[str] = []
    auto_fill_safe = False
    proposed = ""
    proposed_reason = ""

    if suggested in APPLY_DECISIONS and confidence >= strict_confidence:
        proposed = suggested
        auto_fill_safe = True
        proposed_reason = "suggested decision is applyable and confidence is high enough for a draft fill"
    elif suggested in APPLY_DECISIONS and confidence >= 0.6:
        proposed = suggested
        proposed_reason = "suggested decision is plausible but should be visually checked before filling official reviewDecision"
        risk_flags.append("medium_confidence_visual_check_required")
    elif suggested in APPLY_DECISIONS:
        proposed = ""
        proposed_reason = "confidence is too low for auto-fill; inspect contact sheet or rerun cloud recognition"
        risk_flags.append("low_confidence_needs_visual_or_cloud_review")
    else:
        proposed = ""
        proposed_reason = "suggested decision is not applyable; keep pending"
        risk_flags.append("non_applyable_suggested_decision")

    if row.get("needsHumanReview"):
        risk_flags.append("source_route_review_requires_human_review")
    if "unknown" in clean(row.get("originalPlace")).lower() or "unknown" in clean(row.get("correctedPlace")).lower():
        risk_flags.append("unknown_place_present")
        auto_fill_safe = False
    if proposed == "corrected" and not clean(row.get("correctedPlace")):
        risk_flags.append("corrected_place_missing")
        auto_fill_safe = False
    if proposed == "exclude" and not row.get("markedDoNotCut"):
        risk_flags.append("exclude_requires_marked_do_not_cut")

    return {
        "index": row.get("index"),
        "originalChapter": row.get("originalChapter"),
        "originalPlace": row.get("originalPlace"),
        "correctedChapter": row.get("correctedChapter"),
        "correctedPlace": row.get("correctedPlace"),
        "correctedCity": row.get("correctedCity"),
        "correctedCountry": row.get("correctedCountry"),
        "suggestedDecision": suggested,
        "existingReviewDecision": row.get("reviewDecision") or "",
        "proposedReviewDecision": proposed,
        "autoFillSafe": auto_fill_safe,
        "confidence": confidence,
        "confidenceBand": band,
        "videoCount": row.get("videoCount"),
        "durationSeconds": row.get("durationSeconds"),
        "sampleVideos": row.get("sampleVideos") or [],
        "representativeFrames": row.get("representativeFrames") or [],
        "notes": row.get("notes") or [],
        "riskFlags": sorted(set(risk_flags)),
        "reason": proposed_reason,
    }


def build_suggested_sheet(sheet: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
    by_index = {item.get("index"): item for item in proposals}
    suggested = json.loads(json.dumps(sheet, ensure_ascii=False))
    for row in suggested.get("decisionRows") or []:
        proposal = by_index.get(row.get("index"))
        if not proposal:
            continue
        if proposal.get("autoFillSafe") and not row.get("reviewDecision"):
            row["reviewDecision"] = proposal.get("proposedReviewDecision")
            row["userNotes"] = clean(row.get("userNotes")) or "Draft-filled by route decision proposal; user must visually approve before applying."
        row["proposal"] = {
            "autoFillSafe": proposal.get("autoFillSafe"),
            "confidenceBand": proposal.get("confidenceBand"),
            "riskFlags": proposal.get("riskFlags"),
            "reason": proposal.get("reason"),
        }
    approval = suggested.setdefault("approval", {})
    approval["status"] = "pending"
    approval.setdefault("approvedBy", "")
    approval.setdefault("approvedAt", "")
    suggested["status"] = "draft_proposal_not_approved"
    suggested["blockers"] = [
        "Suggested sheet is not approved; inspect route_decision_proposal.md and contact sheet before copying decisions into the official route_decision_sheet.json.",
        "approval.status must be 'approved' with approvedBy/approvedAt before route decisions can be applied.",
    ]
    suggested["safety"] = {
        **(suggested.get("safety") or {}),
        "isOfficialDecisionSheet": False,
        "writesRouteReview": False,
        "writesConfirmedRoute": False,
    }
    return suggested


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    sheet_path = resolve_sheet_path(args)
    sheet = load_json(sheet_path)
    if not isinstance(sheet, dict):
        raise SystemExit(f"Invalid decision sheet: {sheet_path}")
    review_path = Path(clean(sheet.get("sourceRouteReview"))).expanduser().resolve()
    review = load_json(review_path)
    proposals = [proposal_for_row(row, args.strict_confidence) for row in sheet.get("decisionRows") or []]
    auto_fill_count = sum(1 for item in proposals if item.get("autoFillSafe"))
    unresolved = [item for item in proposals if not item.get("autoFillSafe")]
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else sheet_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    proposal_json = output_dir / "route_decision_proposal.json"
    proposal_md = output_dir / "route_decision_proposal.md"
    suggested_sheet_json = output_dir / "route_decision_sheet.suggested.json"
    suggested_sheet_md = output_dir / "route_decision_sheet.suggested.md"
    status = "proposal_ready"
    if unresolved:
        status = "needs_visual_review"
    if not proposals:
        status = "blocked"
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "sourceDecisionSheet": str(sheet_path),
        "sourceRouteReview": str(review_path),
        "reviewMarkdown": sheet.get("reviewMarkdown") or (review or {}).get("reviewMarkdown") if isinstance(review, dict) else "",
        "contactSheet": sheet.get("contactSheet") or (review or {}).get("contactSheet") if isinstance(review, dict) else "",
        "strictConfidence": args.strict_confidence,
        "summary": {
            "rowCount": len(proposals),
            "autoFillSafeCount": auto_fill_count,
            "needsVisualReviewCount": len(unresolved),
            "existingFilledDecisionCount": sum(1 for row in sheet.get("decisionRows") or [] if row.get("reviewDecision")),
        },
        "proposalRows": proposals,
        "suggestedSheetJson": str(suggested_sheet_json),
        "suggestedSheetMarkdown": str(suggested_sheet_md),
        "blockers": [] if proposals else ["Decision sheet has no decisionRows."],
        "warnings": [
            "This is a proposal only; it does not approve route decisions and does not modify route_review.json.",
            "Low/medium-confidence rows must be checked against contact_sheet.jpg or rerun through cloud recognition before final route confirmation.",
        ],
        "nextActions": [
            "Open route_decision_proposal.md and the route contact sheet.",
            "Copy only visually approved proposed decisions into the official route_decision_sheet.json.",
            "Set approval.status='approved', approvedBy, and approvedAt in the official sheet only after review.",
            "Run apply_route_decision_sheet.py without --apply to validate, then use --apply only after explicit approval.",
        ],
        "safety": {
            "writesOfficialDecisionSheet": False,
            "writesRouteReview": False,
            "writesConfirmedRoute": False,
            "writesResolve": False,
        },
    }
    suggested_sheet = build_suggested_sheet(sheet, proposals)
    write_json(proposal_json, report)
    write_markdown(proposal_md, report)
    write_json(suggested_sheet_json, suggested_sheet)
    write_suggested_markdown(suggested_sheet_md, suggested_sheet, report)
    project_dir = Path(clean(sheet.get("projectDir"))).expanduser().resolve() if sheet.get("projectDir") else None
    if project_dir and project_dir.exists():
        write_json(
            project_dir / "latest_route_decision_proposal.json",
            {"proposal": str(proposal_json), "createdAt": report["createdAt"], "status": report["status"]},
        )
    report["proposalJson"] = str(proposal_json)
    report["proposalMarkdown"] = str(proposal_md)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Route Decision Proposal",
        "",
        f"Status: `{report['status']}`",
        f"Decision sheet: `{report['sourceDecisionSheet']}`",
        f"Route review: `{report['sourceRouteReview']}`",
        f"Contact sheet: `{report.get('contactSheet')}`",
        "",
        "## Summary",
    ]
    for key, value in (report.get("summary") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Proposal Rows"])
    for row in report.get("proposalRows") or []:
        flags = ", ".join(row.get("riskFlags") or []) or "none"
        lines.extend(
            [
                f"### {row.get('index')}. {row.get('originalChapter') or row.get('originalPlace')}",
                f"- Existing place: `{row.get('originalPlace')}`",
                f"- Corrected place: `{row.get('correctedPlace')}` / `{row.get('correctedCity')}` / `{row.get('correctedCountry')}`",
                f"- Suggested decision: `{row.get('suggestedDecision')}`",
                f"- Proposed reviewDecision: `{row.get('proposedReviewDecision') or '<leave blank>'}`",
                f"- Auto-fill safe: `{row.get('autoFillSafe')}`",
                f"- Confidence: `{row.get('confidence')}` ({row.get('confidenceBand')})",
                f"- Risk flags: `{flags}`",
                f"- Reason: {row.get('reason')}",
            ]
        )
        if row.get("sampleVideos"):
            lines.append("- Sample videos: " + ", ".join(row["sampleVideos"][:4]))
        lines.append("")
    lines.extend(["## Next Actions"])
    lines.extend(f"- {item}" for item in report.get("nextActions") or [])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_suggested_markdown(path: Path, sheet: dict[str, Any], report: dict[str, Any]) -> None:
    lines = [
        "# Suggested Route Decision Sheet",
        "",
        "This file is a draft convenience copy. It is not approved and is not the official route decision sheet.",
        "",
        f"Official sheet: `{report['sourceDecisionSheet']}`",
        f"Proposal: `{report.get('proposalJson') or path.with_name('route_decision_proposal.json')}`",
        "",
        "## Draft Rows",
    ]
    for row in sheet.get("decisionRows") or []:
        proposal = row.get("proposal") or {}
        lines.extend(
            [
                f"### {row.get('index')}. {row.get('originalChapter')}",
                f"- Draft reviewDecision: `{row.get('reviewDecision') or '<blank>'}`",
                f"- Auto-fill safe: `{proposal.get('autoFillSafe')}`",
                f"- Risk flags: `{', '.join(proposal.get('riskFlags') or []) or 'none'}`",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a conservative route decision proposal without approving it.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app or project directory.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app root.")
    parser.add_argument("--decision-sheet", help="Path to route_decision_sheet.json. Defaults to latest route decision sheet.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to the decision sheet directory.")
    parser.add_argument("--strict-confidence", type=float, default=0.8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Route decision proposal status: {report['status']}")
        print(f"Proposal JSON: {report['proposalJson']}")
        print(f"Proposal Markdown: {report['proposalMarkdown']}")
        print(f"Suggested sheet: {report['suggestedSheetJson']}")
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
