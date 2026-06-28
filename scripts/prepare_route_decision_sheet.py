#!/usr/bin/env python3
"""Create a human-approval route decision sheet from a route review packet."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import discover_project_path


DEFAULT_APP_DIR = Path("/Users/pengyang/Pictures/Video-make/video-claw-studio")
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


def resolve_review_path(args: argparse.Namespace) -> Path:
    if args.route_review:
        path = Path(args.route_review).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Route review not found: {path}")
        return path
    project_dir = discover_project_path(Path(args.project_dir).expanduser().resolve(), args.project_name)
    pointer = load_json(project_dir / "latest_route_review.json")
    if isinstance(pointer, dict) and pointer.get("routeReview"):
        path = Path(pointer["routeReview"]).expanduser().resolve()
        if path.exists():
            return path
    path = latest(sorted(project_dir.glob("route_review/*/route_review.json")))
    if path:
        return path
    raise SystemExit(f"No route_review.json found under {project_dir}")


def clean(value: Any, fallback: str = "") -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def first_known_sample(chapter: dict[str, Any]) -> dict[str, Any]:
    for sample in chapter.get("locationSamples") or []:
        place = clean(sample.get("bestPlace"))
        if place and "unknown" not in place.lower():
            return sample
    return {}


def infer_country_from_text(*values: Any) -> str:
    text = " ".join(str(value or "") for value in values).lower()
    if any(token in text for token in ("hong kong", "香港", "港澳", "维港", "維港")):
        return "Hong Kong/Macau" if "港澳" in text else "Hong Kong"
    if any(token in text for token in ("macao", "macau", "澳门", "澳門")):
        return "Macau"
    if any(token in text for token in ("japan", "tokyo", "osaka", "kyoto", "日本", "东京", "東京", "大阪", "京都")):
        return "Japan"
    return ""


def inferred_country_from_review(review: dict[str, Any], chapter: dict[str, Any], sample: dict[str, Any]) -> str:
    sample_country = clean(sample.get("country"))
    if sample_country:
        return sample_country
    chapter_country = infer_country_from_text(chapter.get("place"), chapter.get("city"), chapter.get("chapter"))
    if chapter_country:
        return chapter_country
    project = review.get("project") if isinstance(review.get("project"), dict) else {}
    region_country = infer_country_from_text(project.get("inferredRegions"), project.get("declaredRegions"), review.get("projectDir"))
    return region_country


def suggested_decision(chapter: dict[str, Any], review: dict[str, Any]) -> tuple[str, dict[str, str], list[str]]:
    sample = first_known_sample(chapter)
    place = clean(chapter.get("place"))
    city = clean(chapter.get("city"))
    country = clean(chapter.get("country"))
    notes: list[str] = []
    corrections = {"place": place, "city": city, "country": country, "chapter": clean(chapter.get("chapter"))}
    if sample:
        sample_place = clean(sample.get("bestPlace"))
        sample_city = clean(sample.get("city"))
        if sample_place and ("unknown" in place.lower() or chapter.get("confidenceLevel") == "low"):
            corrections["place"] = sample_place
            notes.append(f"Sample suggests place: {sample_place}")
        if sample_city and not city:
            corrections["city"] = sample_city
            notes.append(f"Sample suggests city: {sample_city}")
    if not country and (city or sample):
        inferred_country = inferred_country_from_review(review, chapter, sample)
        if inferred_country:
            corrections["country"] = inferred_country
            notes.append("Country inferred from review packet context.")
        else:
            notes.append("Country is still unknown; do not apply route until reviewed.")
    if chapter.get("needsHumanReview"):
        notes.append("Human confirmation still required before applying confirmed route.")
    if any("unknown" in corrections[key].lower() for key in ("place", "chapter")):
        return "pending", corrections, notes
    if corrections["place"] != place or corrections["city"] != city or corrections["country"] != country:
        return "corrected", corrections, notes
    return "confirmed", corrections, notes


def decision_rows(review: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for chapter in review.get("chapters") or []:
        decision, corrections, notes = suggested_decision(chapter, review)
        rows.append(
            {
                "index": chapter.get("index"),
                "chapterId": chapter.get("chapterId"),
                "originalChapter": chapter.get("chapter"),
                "originalPlace": chapter.get("place"),
                "originalCity": chapter.get("city"),
                "originalCountry": chapter.get("country"),
                "suggestedDecision": decision,
                "reviewDecision": "",
                "correctedChapter": corrections["chapter"],
                "correctedPlace": corrections["place"],
                "correctedCity": corrections["city"],
                "correctedCountry": corrections["country"],
                "markedDoNotCut": False,
                "videoCount": chapter.get("videoCount"),
                "durationSeconds": chapter.get("durationSeconds"),
                "confidence": chapter.get("confidence"),
                "confidenceLevel": chapter.get("confidenceLevel"),
                "needsHumanReview": chapter.get("needsHumanReview"),
                "sampleVideos": (chapter.get("videoNames") or [])[:6],
                "representativeFrames": (chapter.get("frames") or [])[:6],
                "evidence": chapter.get("evidence") or [],
                "notes": notes,
                "userNotes": "",
            }
        )
    return rows


def build_sheet(review_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    review = load_json(review_path)
    if not isinstance(review, dict):
        raise SystemExit(f"Invalid route review: {review_path}")
    rows = decision_rows(review)
    declared = review.get("project", {}).get("declaredRegions") or []
    inferred = review.get("project", {}).get("inferredRegions") or []
    mismatch = bool(declared and inferred and set(declared).isdisjoint(set(inferred)))
    blockers = []
    if mismatch:
        blockers.append("Project declared region and inferred media region differ; user must accept the inferred media route or pick the intended media.")
    if any(not row.get("reviewDecision") for row in rows):
        blockers.append("Decision sheet is not approved; fill reviewDecision for every chapter before route application.")
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "createdAt": now,
        "status": "needs_user_approval",
        "sourceRouteReview": str(review_path),
        "projectDir": review.get("projectDir"),
        "reviewMarkdown": review.get("reviewMarkdown"),
        "contactSheet": review.get("contactSheet"),
        "coverage": review.get("coverage"),
        "projectRegionReview": {
            "declaredRegions": declared,
            "inferredRegions": inferred,
            "mismatch": mismatch,
            "suggestedResolution": "accept_inferred_media_route" if mismatch else "no_region_override_needed",
            "approvedResolution": "",
            "approvedBy": "",
            "approvedAt": "",
        },
        "approval": {
            "status": "pending",
            "approvedBy": "",
            "approvedAt": "",
            "notes": "",
        },
        "decisionRows": rows,
        "allowedReviewDecisions": sorted(APPLY_DECISIONS | {"rerun_recognition", "pending"}),
        "blockers": blockers,
        "nextCommands": {
            "afterEditingSheet": "Copy each decisionRows[].reviewDecision/corrected* value into route_review.json chapters.",
            "candidateDryRun": f"python3 <skill-dir>/scripts/prepare_confirmed_route_candidate.py --route-review {review_path} --accept-inferred-region",
            "candidateApply": f"python3 <skill-dir>/scripts/prepare_confirmed_route_candidate.py --route-review {review_path} --accept-inferred-region --apply",
        },
        "safety": {
            "writesConfirmedRoute": False,
            "modifiesSourceReview": False,
            "requiresUserApprovalBeforeApply": True,
        },
    }


def merge_existing_sheet(sheet: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(existing, dict):
        return sheet
    merged = dict(sheet)
    for key in ("approval", "projectRegionReview"):
        if isinstance(existing.get(key), dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **{k: v for k, v in existing[key].items() if v not in ("", None)}}
    existing_rows = {
        row.get("index"): row
        for row in existing.get("decisionRows", [])
        if isinstance(row, dict) and row.get("index") is not None
    }
    preserved_keys = {
        "reviewDecision",
        "correctedChapter",
        "correctedPlace",
        "correctedCity",
        "correctedCountry",
        "markedDoNotCut",
        "userNotes",
    }
    rows = []
    for row in merged.get("decisionRows") or []:
        prev = existing_rows.get(row.get("index"))
        if isinstance(prev, dict):
            next_row = dict(row)
            for key in preserved_keys:
                if prev.get(key) not in ("", None, False):
                    next_row[key] = prev[key]
            rows.append(next_row)
        else:
            rows.append(row)
    merged["decisionRows"] = rows
    blockers = []
    region = merged.get("projectRegionReview") or {}
    if region.get("mismatch"):
        if region.get("approvedResolution") not in {"accept_inferred_media_route", "accept_inferred_japan_route"} or not region.get("approvedBy") or not region.get("approvedAt"):
            blockers.append("Project declared region and inferred media region differ; user must accept the inferred media route or pick the intended media.")
    if any(not row.get("reviewDecision") for row in rows):
        blockers.append("Decision sheet is not approved; fill reviewDecision for every chapter before route application.")
    approval = merged.get("approval") or {}
    if approval.get("status") == "approved" and not blockers:
        merged["status"] = "approved"
    elif approval.get("status") == "approved":
        merged["status"] = "partially_approved"
    else:
        merged["status"] = "needs_user_approval"
    merged["blockers"] = blockers
    merged["preservedExistingDecisions"] = bool(existing_rows)
    return merged


def write_markdown(path: Path, sheet: dict[str, Any]) -> None:
    lines = [
        "# Route Decision Sheet",
        "",
        f"Status: `{sheet['status']}`",
        f"Source review: `{sheet['sourceRouteReview']}`",
        f"Contact sheet: `{sheet.get('contactSheet')}`",
        "",
        "## Region Review",
        f"- Declared: `{sheet['projectRegionReview'].get('declaredRegions')}`",
        f"- Inferred: `{sheet['projectRegionReview'].get('inferredRegions')}`",
        f"- Suggested resolution: `{sheet['projectRegionReview'].get('suggestedResolution')}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in sheet.get("blockers") or ["None"])
    lines.extend(
        [
            "",
            "## Decisions",
            "Fill `reviewDecision` in the JSON sheet or copy the suggested decision into `route_review.json` after visually checking the contact sheet.",
            "",
        ]
    )
    for row in sheet.get("decisionRows") or []:
        lines.extend(
            [
                f"### {row.get('index')}. {row.get('originalChapter')}",
                f"- Original place: `{row.get('originalPlace')}` ({row.get('originalCity')}/{row.get('originalCountry')})",
                f"- Suggested decision: `{row.get('suggestedDecision')}`",
                f"- Corrected place: `{row.get('correctedPlace')}` ({row.get('correctedCity')}/{row.get('correctedCountry')})",
                f"- Videos: {row.get('videoCount')}, duration: {row.get('durationSeconds')}s, confidence: {row.get('confidence')}",
            ]
        )
        for note in row.get("notes") or []:
            lines.append(f"- Note: {note}")
        if row.get("sampleVideos"):
            lines.append("- Sample videos: " + ", ".join(row["sampleVideos"][:4]))
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a route decision sheet from route_review.json.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app or project directory.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app root.")
    parser.add_argument("--route-review", help="Path to route_review.json. Defaults to latest_route_review.json.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to route review directory.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    review_path = resolve_review_path(args)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else review_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet = build_sheet(review_path, args)
    json_path = output_dir / "route_decision_sheet.json"
    markdown_path = output_dir / "route_decision_sheet.md"
    sheet = merge_existing_sheet(sheet, load_json(json_path))
    sheet["decisionSheetJson"] = str(json_path)
    sheet["decisionSheetMarkdown"] = str(markdown_path)
    write_json(json_path, sheet)
    write_markdown(markdown_path, sheet)
    project_dir = Path(sheet["projectDir"]).expanduser().resolve() if sheet.get("projectDir") else None
    if project_dir:
        write_json(
            project_dir / "latest_route_decision_sheet.json",
            {"decisionSheet": str(json_path), "createdAt": sheet["createdAt"], "status": sheet["status"]},
        )
    if args.json:
        print(json.dumps(sheet, ensure_ascii=False, indent=2))
    else:
        print(f"Route decision sheet status: {sheet['status']}")
        print(f"Decision sheet JSON: {json_path}")
        print(f"Decision sheet Markdown: {markdown_path}")
        for blocker in sheet.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 2 if sheet.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
