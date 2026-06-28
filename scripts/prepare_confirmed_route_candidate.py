#!/usr/bin/env python3
"""Prepare an approval-gated confirmed route candidate from a route review packet."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from project_discovery import discover_project_path


DEFAULT_APP_DIR = Path("/Users/pengyang/Pictures/Video-make/video-claw-studio")
APPLY_DECISIONS = {"confirmed", "corrected", "split", "merge"}
BLOCKING_DECISIONS = {"pending", "", "rerun_recognition"}


def load_json(path: Path | None) -> Any:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def discover_project(path: Path, project_name: str | None) -> Path:
    return discover_project_path(path, project_name)


def resolve_review_path(args: argparse.Namespace) -> Path:
    if args.route_review:
        path = Path(args.route_review).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Route review not found: {path}")
        return path
    project_dir = discover_project(Path(args.project_dir), args.project_name)
    pointer_path = project_dir / "latest_route_review.json"
    pointer = load_json(pointer_path)
    if isinstance(pointer, dict) and pointer.get("routeReview"):
        path = Path(pointer["routeReview"]).expanduser().resolve()
        if path.exists():
            return path
    reviews = sorted(project_dir.glob("route_review/*/route_review.json"))
    path = latest(reviews)
    if path:
        return path
    raise SystemExit(f"No route_review.json found under {project_dir}")


def clean(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def corrected_value(chapter: dict[str, Any], key: str) -> str:
    candidates = [
        chapter.get(f"corrected{key[:1].upper()}{key[1:]}"),
        chapter.get(f"userModified{key[:1].upper()}{key[1:]}"),
        chapter.get(key),
    ]
    for value in candidates:
        text = clean(value)
        if text:
            return text
    return ""


def chapter_to_confirmed(chapter: dict[str, Any], now: str) -> dict[str, Any]:
    decision = clean(chapter.get("reviewDecision"), "pending")
    place = corrected_value(chapter, "place")
    city = corrected_value(chapter, "city")
    country = corrected_value(chapter, "country")
    videos = []
    video_paths = []
    video_names = []
    for video in chapter.get("videos", []) or []:
        if video:
            videos.append(video)
    for path in chapter.get("videoPaths", []) or []:
        if path:
            video_paths.append(path)
    for name in chapter.get("videoNames", []) or []:
        if name:
            video_names.append(name)
    if not videos:
        for sample in chapter.get("locationSamples", []) or []:
            video = sample.get("video")
            if video and video not in videos:
                videos.append(video)
    return {
        "chapter": corrected_value(chapter, "chapter") or place,
        "originalChapter": chapter.get("chapter"),
        "place": place,
        "originalPlace": chapter.get("place"),
        "city": city,
        "country": country,
        "timeRange": chapter.get("timeRange") or "",
        "confidence": chapter.get("confidence"),
        "confidenceLevel": chapter.get("confidenceLevel"),
        "videos": videos,
        "videoPaths": video_paths,
        "videoNames": video_names,
        "representativeFrames": chapter.get("frames", [])[:6],
        "userModifiedPlace": place if decision == "corrected" else "",
        "userNotes": chapter.get("userNotes") or f"route_review decision: {decision}",
        "markedUnimportant": bool(chapter.get("markedUnimportant")),
        "markedDoNotCut": bool(chapter.get("markedDoNotCut")) or decision == "exclude",
        "reviewDecision": decision,
        "confirmedAt": now,
    }


def assess_review(review: dict[str, Any], args: argparse.Namespace) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    coverage = review.get("coverage", {})
    coverage_ratio = float(coverage.get("coverageRatio") or 0)
    uncovered = int(coverage.get("uncoveredVideoCount") or 0)
    if coverage_ratio < args.min_coverage:
        blockers.append(
            f"Route review coverage ratio is {coverage_ratio:.4f}; need at least {args.min_coverage:.2f} before applying confirmed route."
        )
    if uncovered:
        blockers.append(f"{uncovered} media videos are not assigned to a reviewed route chapter.")
    declared = set(review.get("project", {}).get("declaredRegions") or [])
    inferred = set(review.get("project", {}).get("inferredRegions") or [])
    if declared and inferred and declared.isdisjoint(inferred):
        message = f"Project declared regions {sorted(declared)} do not match inferred regions {sorted(inferred)}."
        if args.accept_inferred_region:
            warnings.append(message + " User accepted inferred region for candidate generation.")
        else:
            blockers.append(message)
    for stale in review.get("freshness", {}).get("stale") or []:
        if stale == "confirmed_route_timeline.json is older than route_timeline.json":
            warnings.append(stale)
        else:
            blockers.append(stale)
    pending = []
    rerun = []
    for chapter in review.get("chapters", []) or []:
        decision = clean(chapter.get("reviewDecision"), "pending")
        if decision in BLOCKING_DECISIONS:
            pending.append(f"{chapter.get('index')}. {chapter.get('place')}: {decision}")
        elif decision == "rerun_recognition":
            rerun.append(f"{chapter.get('index')}. {chapter.get('place')}")
        elif decision not in APPLY_DECISIONS and decision != "exclude":
            blockers.append(f"Unsupported review decision for chapter {chapter.get('index')}: {decision}")
    if pending:
        blockers.append("Route review has pending chapter decisions: " + "; ".join(pending[:10]))
    if rerun:
        blockers.append("Route review asks for recognition rerun: " + "; ".join(rerun[:10]))
    if not review.get("chapters"):
        blockers.append("Route review has no chapters.")
    return list(dict.fromkeys(blockers)), list(dict.fromkeys(warnings))


def build_candidate(review_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    review = load_json(review_path)
    if not isinstance(review, dict):
        raise SystemExit(f"Invalid route review: {review_path}")
    now = datetime.now().isoformat(timespec="seconds")
    blockers, warnings = assess_review(review, args)
    candidate_chapters = []
    draft_chapters = []
    for chapter in review.get("chapters", []) or []:
        decision = clean(chapter.get("reviewDecision"), "pending")
        confirmed = chapter_to_confirmed(chapter, now)
        if decision in APPLY_DECISIONS or decision == "exclude":
            candidate_chapters.append(confirmed)
        else:
            draft_chapters.append(confirmed)
    candidate_route = {
        "createdAt": now,
        "projectDir": review.get("projectDir"),
        "mode": "route_review_candidate",
        "sourceRouteReview": str(review_path),
        "chapterCount": len(candidate_chapters),
        "chapters": candidate_chapters,
        "notes": [
            "Generated by prepare_confirmed_route_candidate.py.",
            "Do not apply this file unless status is ready_to_apply and the user explicitly approves --apply.",
            "Excluded chapters are preserved with markedDoNotCut=true for auditability.",
        ],
    }
    status = "ready_to_apply" if not blockers and candidate_chapters else "blocked"
    return {
        "createdAt": now,
        "sourceRouteReview": str(review_path),
        "projectDir": review.get("projectDir"),
        "status": status,
        "canApply": status == "ready_to_apply",
        "minCoverage": args.min_coverage,
        "candidate": candidate_route,
        "draftChapters": draft_chapters,
        "blockers": blockers,
        "warnings": warnings,
        "nextActions": next_actions(review, blockers),
    }


def next_actions(review: dict[str, Any], blockers: list[str]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    text = "\n".join(blockers)
    if "declared regions" in text:
        actions.append(
            {
                "priority": "P0",
                "action": "Resolve project/media mismatch",
                "detail": "Rename/update project route metadata to the inferred media route or rerun recognition on the intended footage.",
            }
        )
    if "coverage ratio" in text or "not assigned" in text:
        actions.append(
            {
                "priority": "P0",
                "action": "Repair route coverage",
                "detail": "Rerun location/route recognition so most source videos are assigned to route chapters before building a 20-minute film.",
            }
        )
    if "pending chapter decisions" in text:
        actions.append(
            {
                "priority": "P0",
                "action": "Edit route review decisions",
                "detail": f"Open {review.get('reviewMarkdown')} and route_review.json, then set reviewDecision per chapter.",
            }
        )
    if not actions:
        actions.append({"priority": "P1", "action": "Apply candidate after approval", "detail": "Run with --apply only after user approval."})
    return actions


def write_markdown(path: Path, candidate: dict[str, Any]) -> None:
    lines = [
        "# Confirmed Route Candidate",
        "",
        f"Status: `{candidate['status']}`",
        f"Can apply: `{candidate['canApply']}`",
        f"Source review: `{candidate['sourceRouteReview']}`",
        f"Project directory: `{candidate['projectDir']}`",
        f"Candidate chapters: {candidate['candidate']['chapterCount']}",
        f"Draft/pending chapters: {len(candidate.get('draftChapters') or [])}",
        "",
        "## Blockers",
    ]
    lines.extend(f"- {item}" for item in candidate["blockers"] or ["None"])
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {item}" for item in candidate["warnings"] or ["None"])
    lines.append("")
    lines.append("## Next Actions")
    for action in candidate["nextActions"]:
        lines.append(f"- [{action['priority']}] {action['action']}: {action['detail']}")
    lines.append("")
    lines.append("## Candidate Chapters")
    for chapter in candidate["candidate"]["chapters"] or []:
        lines.append(
            f"- `{chapter['reviewDecision']}` {chapter.get('chapter')} -> {chapter.get('place')} "
            f"({chapter.get('city')}/{chapter.get('country')}), videos={len(chapter.get('videos') or [])}"
        )
    if candidate.get("draftChapters"):
        lines.append("")
        lines.append("## Draft/Pending Chapters")
        for chapter in candidate["draftChapters"]:
            lines.append(
                f"- `{chapter['reviewDecision']}` {chapter.get('chapter')} -> {chapter.get('place')} "
                f"({chapter.get('city')}/{chapter.get('country')})"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_candidate(candidate: dict[str, Any]) -> None:
    if not candidate.get("canApply"):
        raise SystemExit("Candidate is not ready to apply: " + "; ".join(candidate.get("blockers") or []))
    project_dir = Path(candidate["projectDir"]).expanduser().resolve()
    confirmed_path = project_dir / "confirmed_route_timeline.json"
    latest_path = project_dir / "latest_confirmed_route.json"
    write_json(confirmed_path, candidate["candidate"])
    write_json(latest_path, {"files": {"confirmedRoute": str(confirmed_path)}, "createdAt": candidate["createdAt"]})


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a confirmed-route candidate from route_review.json.")
    parser.add_argument("--project-dir", default=str(DEFAULT_APP_DIR), help="VideoClaw app or project directory.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app root.")
    parser.add_argument("--route-review", help="Path to route_review.json. Defaults to latest_route_review.json.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to the route review directory.")
    parser.add_argument("--min-coverage", type=float, default=0.65, help="Minimum route coverage ratio required for --apply.")
    parser.add_argument("--accept-inferred-region", action="store_true", help="Allow declared/inferred region mismatch as a warning.")
    parser.add_argument("--apply", action="store_true", help="Write confirmed_route_timeline.json if all gates pass.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    review_path = resolve_review_path(args)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else review_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = build_candidate(review_path, args)
    candidate_path = output_dir / "confirmed_route_candidate.json"
    markdown_path = output_dir / "confirmed_route_candidate.md"
    candidate["candidateJson"] = str(candidate_path)
    candidate["candidateMarkdown"] = str(markdown_path)
    write_json(candidate_path, candidate)
    write_markdown(markdown_path, candidate)
    project_dir = Path(candidate["projectDir"]).expanduser().resolve() if candidate.get("projectDir") else None
    if project_dir:
        write_json(
            project_dir / "latest_confirmed_route_candidate.json",
            {"candidate": str(candidate_path), "createdAt": candidate["createdAt"], "status": candidate["status"]},
        )
    if args.apply:
        apply_candidate(candidate)
    if args.json:
        print(json.dumps(candidate, ensure_ascii=False, indent=2))
    else:
        print(f"Confirmed route candidate status: {candidate['status']}")
        print(f"Candidate JSON: {candidate_path}")
        print(f"Candidate Markdown: {markdown_path}")
        for blocker in candidate["blockers"]:
            print(f"BLOCKER: {blocker}")
        for action in candidate["nextActions"]:
            print(f"NEXT {action['priority']}: {action['action']}")
    return 0 if candidate["canApply"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
