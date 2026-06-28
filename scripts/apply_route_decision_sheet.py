#!/usr/bin/env python3
"""Validate and optionally apply a route decision sheet back into route_review.json."""

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


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


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


def validate_sheet(sheet: dict[str, Any], args: argparse.Namespace) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    rows = sheet.get("decisionRows") if isinstance(sheet.get("decisionRows"), list) else []
    if not rows:
        blockers.append("Decision sheet has no decisionRows.")
    region = sheet.get("projectRegionReview") if isinstance(sheet.get("projectRegionReview"), dict) else {}
    if region.get("mismatch"):
        approved_resolution = clean(region.get("approvedResolution"))
        approved_by = clean(region.get("approvedBy"))
        approved_at = clean(region.get("approvedAt"))
        if approved_resolution not in {"accept_inferred_media_route", "accept_inferred_japan_route"}:
            blockers.append("Region mismatch needs approvedResolution='accept_inferred_media_route' or different media.")
        if not approved_by or not approved_at:
            blockers.append("Region mismatch approval needs approvedBy and approvedAt.")
    approval = sheet.get("approval") if isinstance(sheet.get("approval"), dict) else {}
    if clean(approval.get("status")) != "approved":
        blockers.append("Decision sheet approval.status must be 'approved'.")
    if not clean(approval.get("approvedBy")) or not clean(approval.get("approvedAt")):
        blockers.append("Decision sheet approval needs approvedBy and approvedAt.")
    for row in rows:
        idx = row.get("index")
        decision = clean(row.get("reviewDecision"))
        if args.use_suggestions and not decision:
            decision = clean(row.get("suggestedDecision"))
            warnings.append(f"Row {idx} uses suggestedDecision because reviewDecision is empty.")
        if decision not in APPLY_DECISIONS:
            blockers.append(f"Row {idx} has unsupported or missing reviewDecision: {decision or '<empty>'}")
        if decision == "corrected" and not clean(row.get("correctedPlace")):
            blockers.append(f"Row {idx} is corrected but correctedPlace is empty.")
        if decision == "exclude" and not row.get("markedDoNotCut"):
            warnings.append(f"Row {idx} is exclude; markedDoNotCut will be forced true.")
    return list(dict.fromkeys(blockers)), list(dict.fromkeys(warnings))


def apply_rows(review: dict[str, Any], sheet: dict[str, Any], args: argparse.Namespace, now: str) -> dict[str, Any]:
    rows_by_index = {row.get("index"): row for row in sheet.get("decisionRows") or []}
    updated = dict(review)
    updated_chapters = []
    applied_count = 0
    for chapter in review.get("chapters") or []:
        row = rows_by_index.get(chapter.get("index"))
        if not row:
            updated_chapters.append(chapter)
            continue
        decision = clean(row.get("reviewDecision"))
        if args.use_suggestions and not decision:
            decision = clean(row.get("suggestedDecision"))
        next_chapter = dict(chapter)
        next_chapter["reviewDecision"] = decision
        next_chapter["userNotes"] = clean(row.get("userNotes")) or clean((sheet.get("approval") or {}).get("notes"))
        next_chapter["decisionAppliedAt"] = now
        for sheet_key, review_key in [
            ("correctedChapter", "correctedChapter"),
            ("correctedPlace", "correctedPlace"),
            ("correctedCity", "correctedCity"),
            ("correctedCountry", "correctedCountry"),
        ]:
            value = clean(row.get(sheet_key))
            if value:
                next_chapter[review_key] = value
        if decision == "corrected":
            for key in ("chapter", "place", "city", "country"):
                value = clean(row.get(f"corrected{key[:1].upper()}{key[1:]}"))
                if value:
                    next_chapter[key] = value
        if decision == "exclude":
            next_chapter["markedDoNotCut"] = True
        elif row.get("markedDoNotCut"):
            next_chapter["markedDoNotCut"] = True
        next_chapter["needsHumanReview"] = False
        updated_chapters.append(next_chapter)
        applied_count += 1
    updated["chapters"] = updated_chapters
    updated["status"] = "reviewed"
    updated["reviewDecisionAppliedAt"] = now
    updated["decisionSheet"] = sheet.get("decisionSheetJson") or ""
    updated["decisionSheetApproval"] = sheet.get("approval")
    if (sheet.get("projectRegionReview") or {}).get("mismatch"):
        updated["acceptedRegionMismatch"] = sheet.get("projectRegionReview")
    updated["blockers"] = []
    updated["warnings"] = list(dict.fromkeys([*(review.get("warnings") or []), "Route decisions applied from route_decision_sheet.json."]))
    updated["needsHumanReviewCount"] = sum(1 for ch in updated_chapters if ch.get("needsHumanReview"))
    updated["appliedDecisionCount"] = applied_count
    return updated


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    sheet_path = resolve_sheet_path(args)
    sheet = load_json(sheet_path)
    if not isinstance(sheet, dict):
        raise SystemExit(f"Invalid decision sheet: {sheet_path}")
    review_path = Path(sheet.get("sourceRouteReview", "")).expanduser().resolve()
    review = load_json(review_path)
    if not isinstance(review, dict):
        raise SystemExit(f"Invalid source route review: {review_path}")
    now = datetime.now().isoformat(timespec="seconds")
    blockers, warnings = validate_sheet(sheet, args)
    would_apply = not blockers
    applied = False
    applied_review = None
    if args.apply and would_apply:
        applied_review = apply_rows(review, sheet, args, now)
        write_json(review_path, applied_review)
        applied = True
        project_dir = Path(clean(sheet.get("projectDir")) or clean(review.get("projectDir"))).expanduser().resolve()
        if project_dir.exists():
            write_json(project_dir / "latest_route_review.json", {"routeReview": str(review_path), "createdAt": now, "status": "reviewed"})
    elif args.apply and blockers:
        warnings.append("route_review.json was not updated because decision sheet blockers remain.")
    rows = sheet.get("decisionRows") if isinstance(sheet.get("decisionRows"), list) else []
    report = {
        "createdAt": now,
        "status": "ready_to_apply" if would_apply and not applied else ("applied" if applied else "blocked"),
        "sourceDecisionSheet": str(sheet_path),
        "sourceRouteReview": str(review_path),
        "applied": applied,
        "wouldApply": would_apply,
        "summary": {
            "rowCount": len(rows),
            "filledDecisionCount": sum(1 for row in rows if row.get("reviewDecision")),
            "useSuggestions": bool(args.use_suggestions),
            "regionMismatch": (sheet.get("projectRegionReview") or {}).get("mismatch"),
            "reviewChapterCount": len(review.get("chapters") or []),
            "appliedDecisionCount": applied_review.get("appliedDecisionCount") if applied_review else 0,
        },
        "blockers": blockers,
        "warnings": warnings,
        "nextActions": [
            "Fill route_decision_sheet.json approval and reviewDecision fields, then rerun this script.",
            "Run prepare_confirmed_route_candidate.py with --accept-inferred-region after route_review.json is updated.",
            "Use --apply only after the user approves writing the reviewed route decisions back into route_review.json.",
        ],
        "safety": {
            "writesRouteReviewOnlyWithApply": True,
            "writesConfirmedRoute": False,
            "writesResolve": False,
        },
    }
    report_path = sheet_path.parent / "route_decision_application.json"
    report_md = sheet_path.parent / "route_decision_application.md"
    report["applicationJson"] = str(report_path)
    report["applicationMarkdown"] = str(report_md)
    write_json(report_path, report)
    write_markdown(report_md, report)
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Route Decision Application",
        "",
        f"Status: `{report['status']}`",
        f"Applied: `{report['applied']}`",
        f"Would apply: `{report['wouldApply']}`",
        f"Decision sheet: `{report['sourceDecisionSheet']}`",
        f"Route review: `{report['sourceRouteReview']}`",
        "",
        "## Summary",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Blockers"])
    lines.extend(f"- {item}" for item in report.get("blockers") or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in report.get("warnings") or ["None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and optionally apply route decision sheet decisions.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app or project directory.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app root.")
    parser.add_argument("--decision-sheet", help="Path to route_decision_sheet.json. Defaults to latest route decision sheet.")
    parser.add_argument("--use-suggestions", action="store_true", help="Use suggestedDecision where reviewDecision is empty. Requires --apply for writes.")
    parser.add_argument("--apply", action="store_true", help="Write approved decisions back into route_review.json.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Route decision application status: {report['status']}")
        print(f"Applied: {report['applied']}")
        for blocker in report.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if report["status"] in {"ready_to_apply", "applied"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
