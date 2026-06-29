#!/usr/bin/env python3
"""Audit whether every transition is backed by concrete from/to pair continuity."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide"}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}
ROUTE_TAGS = {"route_bridge_context", "bridge_sequence", "motion_match", "title_or_ending_handoff"}
LOCAL_TAGS = {"same_source_trim", "same_chapter_continuity", "place_or_chapter_continuity", "invisible_continuity_cut", "bgm_phrase_hit"}


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


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round3(value: float) -> float:
    return round(float(value), 3)


def source_name(value: Any) -> str:
    text = str(value or "")
    return Path(text).name if text else ""


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    duration = as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0
    return start + duration


def clip_text(clip: dict[str, Any]) -> str:
    return " ".join(
        str(clip.get(key) or "")
        for key in ("role", "purpose", "place", "titleText", "subtitle", "sourcePath", "sourceName", "name", "notes")
    ).lower()


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt")):
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type not in {"", "video"}:
        return False
    return int(as_float(clip.get("mediaType"), 1) or 1) == 1


def choose_blueprint(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path, str]:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
        return load_json(path), path, "explicit_blueprint"
    candidates = [
        (package_dir / "transition_polish_blueprint" / "transition_polish_blueprint_report.json", "candidateBlueprint", "transition_polish_candidate"),
        (package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json", "candidateBlueprint", "rhythm_recut_candidate"),
        (package_dir / "bgm_phrase_blueprint" / "bgm_phrase_blueprint_report.json", "candidateBlueprint", "bgm_phrase_candidate"),
        (package_dir / "transition_execution_blueprint" / "transition_execution_blueprint_report.json", "candidateBlueprint", "transition_execution_candidate"),
    ]
    for report_path, output_key, kind in candidates:
        report = load_json(report_path) or {}
        outputs = report.get("outputs") if isinstance(report.get("outputs"), dict) else {}
        raw = outputs.get(output_key)
        if not raw or not str(report.get("status") or "").startswith("ready"):
            continue
        path = Path(str(raw)).expanduser()
        if not path.is_absolute():
            path = (package_dir / path).resolve()
        if not is_inside(path, package_dir):
            continue
        data = load_json(path)
        if isinstance(data, dict):
            return data, path, kind
    active = package_dir / "resolve_timeline_blueprint.json"
    return load_json(active), active, "active_blueprint"


def primary_visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    video = [row for row in rows if isinstance(row, dict) and is_video_clip(row)]
    return sorted(video, key=lambda item: (timeline_start(item), timeline_end(item), str(item.get("sourcePath") or "")))


def boundary_category(left: dict[str, Any], right: dict[str, Any]) -> str:
    text = f"{clip_text(left)} {clip_text(right)}"
    if "title" in text or "opening_city" in text:
        return "title_boundary"
    if "ending" in text:
        return "ending_transition"
    if left.get("chapterIndex") is not None and right.get("chapterIndex") is not None and str(left.get("chapterIndex")) != str(right.get("chapterIndex")):
        return "chapter_boundary"
    if timeline_start(right) - timeline_end(left) > 0.2:
        return "timeline_gap"
    return "same_chapter_cut"


def visual_boundaries(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(clips, clips[1:]), start=1):
        rows.append(
            {
                "boundaryIndex": index,
                "boundarySeconds": round3(timeline_end(left)),
                "category": boundary_category(left, right),
                "fromSourcePath": left.get("sourcePath") or left.get("sourceName"),
                "toSourcePath": right.get("sourcePath") or right.get("sourceName"),
                "fromSourceName": source_name(left.get("sourcePath") or left.get("sourceName")),
                "toSourceName": source_name(right.get("sourcePath") or right.get("sourceName")),
                "fromRole": left.get("role"),
                "toRole": right.get("role"),
                "fromChapterIndex": left.get("chapterIndex"),
                "toChapterIndex": right.get("chapterIndex"),
            }
        )
    return rows


def transition_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}


def pair_continuity(row: dict[str, Any]) -> dict[str, Any]:
    candidate = transition_candidate(row)
    payload = candidate.get("pairContinuity") if isinstance(candidate.get("pairContinuity"), dict) else {}
    if payload:
        return payload
    return row.get("pairContinuity") if isinstance(row.get("pairContinuity"), dict) else {}


def transition_boundary(row: dict[str, Any]) -> float | None:
    candidate = transition_candidate(row)
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds"):
        value = as_float(row.get(key))
        if value is not None:
            return value
    return as_float(candidate.get("boundarySeconds"))


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    out = [row for row in rows if isinstance(row, dict)]
    if out:
        return out
    candidates = blueprint.get("transitionPolishCandidates") if isinstance(blueprint.get("transitionPolishCandidates"), list) else []
    return [
        {
            "rowIndex": item.get("rowIndex"),
            "boundarySeconds": item.get("boundarySeconds"),
            "fromSourcePath": item.get("fromSourcePath"),
            "toSourcePath": item.get("toSourcePath"),
            "transitionPolishCandidate": item,
        }
        for item in candidates
        if isinstance(item, dict)
    ]


def pair_matches(boundary: dict[str, Any], transition: dict[str, Any]) -> bool:
    payload = pair_continuity(transition)
    from_transition = source_name(transition.get("fromSourcePath") or payload.get("fromSourcePath"))
    to_transition = source_name(transition.get("toSourcePath") or payload.get("toSourcePath"))
    left = boundary.get("fromSourceName")
    right = boundary.get("toSourceName")
    return bool((not from_transition or from_transition == left) and (not to_transition or to_transition == right))


def nearest_transition(boundary: dict[str, Any], rows: list[dict[str, Any]], *, tolerance: float) -> dict[str, Any] | None:
    exact = [row for row in rows if row.get("rowIndex") == boundary.get("boundaryIndex")]
    if exact:
        return exact[0]
    candidates: list[tuple[float, dict[str, Any]]] = []
    boundary_seconds = float(boundary.get("boundarySeconds") or 0.0)
    for row in rows:
        value = transition_boundary(row)
        if value is None:
            continue
        distance = abs(value - boundary_seconds)
        if distance <= tolerance:
            candidates.append((distance, row))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def normalize_style(row: dict[str, Any]) -> str:
    payload = pair_continuity(row)
    if payload.get("style"):
        return str(payload["style"])
    candidate = transition_candidate(row)
    recipe = candidate.get("selectedRecipe") if isinstance(candidate.get("selectedRecipe"), dict) else {}
    text = json.dumps(
        {
            "type": row.get("approvedTransitionType"),
            "effect": row.get("resolveEffectName"),
            "recipe": recipe.get("recipeId"),
            "recipeEffect": recipe.get("resolveEffectName"),
        },
        ensure_ascii=False,
    ).lower()
    if "whip" in text:
        return "whip_pan"
    if "rotation" in text:
        return "rotation"
    if "speed" in text or "ramp" in text:
        return "speed_ramp"
    if "push" in text or "slide" in text:
        return "push_slide"
    if "dissolve" in text or "cross" in text:
        return "dissolve"
    if "match" in text:
        return "match_cut"
    if "bridge" in text:
        return "bridge"
    return "clean_cut"


def audited_boundary(boundary: dict[str, Any], transition: dict[str, Any] | None) -> dict[str, Any]:
    if not transition:
        return {**boundary, "status": "blocked", "style": None, "pairFit": None, "issues": ["missing_transition_for_pair_continuity"]}
    payload = pair_continuity(transition)
    tags = set(str(item) for item in (payload.get("evidenceTags") if isinstance(payload.get("evidenceTags"), list) else []))
    style = normalize_style(transition)
    category = str(boundary.get("category") or "")
    score = int(payload.get("continuityScore") or 0)
    pair_fit = str(payload.get("pairFit") or "")
    issues: list[str] = []
    if not pair_matches(boundary, transition):
        issues.append("transition_pair_does_not_match_actual_from_to_boundary")
    if not payload:
        issues.append("missing_pair_continuity_payload")
    if pair_fit not in {"strong", "acceptable"} or score < 44:
        issues.append("weak_pair_continuity")
    if payload.get("styleAllowed") is not True:
        issues.append("transition_style_not_allowed_by_pair_continuity")
    if not tags:
        issues.append("missing_pair_continuity_evidence_tags")
    if category in {"chapter_boundary", "timeline_gap"} and not (tags & ROUTE_TAGS):
        issues.append("route_or_timeline_jump_without_route_bridge_motion_or_title_handoff")
    if category == "same_chapter_cut" and not (tags & LOCAL_TAGS):
        issues.append("same_chapter_cut_without_local_visual_or_bgm_continuity")
    if category in {"title_boundary", "ending_transition"} and "title_or_ending_handoff" not in tags:
        issues.append("title_or_ending_boundary_without_clean_handoff_tag")
    if style in MOTION_STYLES and not ({"motion_match", "bridge_sequence"} & tags):
        issues.append("motion_style_without_motion_match_or_bridge_sequence_tag")
    if style in {"whip_pan", "rotation", "speed_ramp"} and pair_fit != "strong":
        issues.append("flashy_motion_transition_not_strong_pair_fit")
    return {
        **boundary,
        "status": "passed" if not issues else "blocked",
        "transitionRowIndex": transition.get("rowIndex"),
        "transitionBoundarySeconds": transition_boundary(transition),
        "style": style,
        "pairFit": pair_fit,
        "continuityScore": score,
        "styleAllowed": payload.get("styleAllowed"),
        "evidenceTags": sorted(tags),
        "viewerContinuityReason": payload.get("viewerContinuityReason") if isinstance(payload.get("viewerContinuityReason"), list) else [],
        "pairMatched": pair_matches(boundary, transition),
        "issues": issues,
    }


def counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "missing")
        out[key] = out.get(key, 0) + 1
    return out


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint, blueprint_path, blueprint_kind = choose_blueprint(package_dir, args.blueprint)
    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {"blueprint": str(blueprint_path), "blueprintExists": blueprint_path.exists(), "blueprintKind": blueprint_kind},
            "summary": {},
            "boundaryRows": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    clips = primary_visual_clips(blueprint)
    boundaries = visual_boundaries(clips)
    rows = transition_rows(blueprint)
    audited = [audited_boundary(boundary, nearest_transition(boundary, rows, tolerance=args.tolerance_seconds)) for boundary in boundaries]
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    motion_count = sum(1 for row in audited if row.get("style") in MOTION_STYLES)
    blockers = [f"boundary {row.get('boundaryIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[:80]]
    if len(audited) >= 8 and motion_count > math.ceil(len(audited) * 0.30):
        blockers.append(f"too many motion-driven transitions for reference-like travel pacing: {motion_count}/{len(audited)}")
    if boundaries and not rows:
        blockers.append("no transition rows found in selected blueprint")
    if not audited and len(clips) > 1:
        blockers.append("visual boundaries exist but no pair-continuity rows were audited")
    warnings = []
    if blueprint_kind == "active_blueprint":
        warnings.append("audited active blueprint because no ready transition-polish candidate was found")
    status = "passed" if not blockers and (not boundaries or rows) else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "toleranceSeconds": args.tolerance_seconds,
        },
        "summary": {
            "visualClipCount": len(clips),
            "visualBoundaryCount": len(boundaries),
            "transitionRowCount": len(rows),
            "transitionCoverageRatio": round3(len(rows) / len(boundaries)) if boundaries else 1.0,
            "auditedBoundaryCount": len(audited),
            "passedBoundaryCount": sum(1 for row in audited if row.get("status") == "passed"),
            "blockedBoundaryCount": len(blocked_rows),
            "pairContinuityPayloadCount": sum(1 for row in audited if row.get("evidenceTags")),
            "strongPairFitCount": sum(1 for row in audited if row.get("pairFit") == "strong"),
            "acceptablePairFitCount": sum(1 for row in audited if row.get("pairFit") == "acceptable"),
            "weakPairFitCount": sum(1 for row in audited if row.get("pairFit") == "weak"),
            "styleAllowedBoundaryCount": sum(1 for row in audited if row.get("styleAllowed") is True),
            "pairMatchedBoundaryCount": sum(1 for row in audited if row.get("pairMatched") is True),
            "motionBoundaryCount": motion_count,
            "categoryCounts": counts(audited, "category"),
            "styleCounts": counts(audited, "style"),
            "pairFitCounts": counts(audited, "pairFit"),
        },
        "boundaryRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Pair Continuity Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Blueprint: `{report['inputs'].get('blueprint')}`",
        f"Blueprint kind: `{report['inputs'].get('blueprintKind')}`",
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
    lines.extend(["", "## Boundary Rows"])
    for row in (report.get("boundaryRows") or [])[:160]:
        lines.extend(
            [
                "",
                f"### Boundary {row.get('boundaryIndex')}: {row.get('category')} / {row.get('style')}",
                f"- Status: `{row.get('status')}`",
                f"- Pair fit: `{row.get('pairFit')}` score `{row.get('continuityScore')}`",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- Tags: `{', '.join(row.get('evidenceTags') or [])}`",
                f"- Reasons: `{'; '.join(row.get('viewerContinuityReason') or [])}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit from/to pair continuity for every shot transition.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--tolerance-seconds", type=float, default=0.75)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_pair_continuity_contract_audit.json", report)
    write_markdown(package_dir / "transition_pair_continuity_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
