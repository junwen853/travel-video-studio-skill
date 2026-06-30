#!/usr/bin/env python3
"""Audit whether shot transitions have narrative and visual motivation."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


FORBIDDEN_TERMS = (
    "glitch",
    "flash",
    "shake",
    "strobe",
    "template",
    "particle",
    "random spin",
    "whoosh pack",
)
MOTION_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide"}
DECORATIVE_STYLES = {"whip_pan", "rotation", "speed_ramp", "push_slide", "dissolve"}
IMPORTANT_CATEGORIES = {"chapter_boundary", "timeline_gap", "title_boundary", "ending_transition"}


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
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass")):
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
        (package_dir / "bridge_sequence_blueprint" / "bridge_sequence_blueprint_report.json", "candidateBlueprint", "bridge_sequence_candidate"),
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
    left_text = clip_text(left)
    right_text = clip_text(right)
    left_chapter = left.get("chapterIndex")
    right_chapter = right.get("chapterIndex")
    if "title" in left_text or "title" in right_text or "opening_city" in left_text or "ending_city" in right_text:
        return "title_boundary"
    if "ending" in left_text or "ending" in right_text:
        return "ending_transition"
    if left_chapter is not None and right_chapter is not None and str(left_chapter) != str(right_chapter):
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
                "timelineGapSeconds": round3(timeline_start(right) - timeline_end(left)),
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


def transition_boundary(row: dict[str, Any]) -> float | None:
    candidate = row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}
    for key in ("boundarySeconds", "timelineStartSeconds", "startSeconds"):
        value = as_float(row.get(key))
        if value is not None:
            return value
    return as_float(candidate.get("boundarySeconds"))


def style_blob(row: dict[str, Any]) -> str:
    candidate = row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}
    recipe = candidate.get("selectedRecipe") if isinstance(candidate.get("selectedRecipe"), dict) else {}
    values = [
        row.get("approvedTransitionType"),
        row.get("resolveEffectName"),
        row.get("trackOperation"),
        row.get("motionStyle"),
        recipe.get("recipeId"),
        recipe.get("resolveEffectName"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def normalize_style(row: dict[str, Any]) -> str:
    text = style_blob(row)
    if "whip" in text:
        return "whip_pan"
    if "rotation" in text:
        return "rotation"
    if "speed" in text or "ramp" in text:
        return "speed_ramp"
    if "dissolve" in text or "cross" in text:
        return "dissolve"
    if "match" in text:
        return "match_cut"
    if "bridge" in text:
        return "bridge"
    if "push" in text or "slide" in text:
        return "push_slide"
    return "clean_cut"


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
            "audioPolicy": item.get("audioPolicy"),
        }
        for item in candidates
        if isinstance(item, dict)
    ]


def pair_matches(boundary: dict[str, Any], transition: dict[str, Any]) -> bool:
    from_transition = source_name(transition.get("fromSourcePath"))
    to_transition = source_name(transition.get("toSourcePath"))
    if not from_transition and not to_transition:
        return False
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
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def transition_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}


def motivation(row: dict[str, Any]) -> dict[str, Any]:
    candidate = transition_candidate(row)
    payload = candidate.get("transitionMotivation") if isinstance(candidate.get("transitionMotivation"), dict) else {}
    if payload:
        return payload
    return row.get("transitionMotivation") if isinstance(row.get("transitionMotivation"), dict) else {}


def has_bgm_hit(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    recipe = candidate.get("selectedRecipe") if isinstance(candidate.get("selectedRecipe"), dict) else {}
    bgm = candidate.get("bgmSync") if isinstance(candidate.get("bgmSync"), dict) else {}
    motivation_payload = motivation(row)
    evidence = motivation_payload.get("evidence") if isinstance(motivation_payload.get("evidence"), dict) else {}
    return bool(
        row.get("bgmHitSeconds") is not None
        or row.get("bgmPhraseCue")
        or recipe.get("bgmHitSeconds") is not None
        or bgm.get("hitSeconds") is not None
        or bgm.get("phraseIndex") is not None
        or evidence.get("bgmHitSeconds") is not None
        or evidence.get("bgmPhraseIndex") is not None
    )


def motion_safe(row: dict[str, Any], style: str) -> bool:
    if style not in MOTION_STYLES:
        return True
    candidate = transition_candidate(row)
    payload = motivation(row)
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    return (
        row.get("motionHasEvidence") is True
        or row.get("bridgeSequenceSatisfied") is True
        or candidate.get("motionEvidenceSatisfied") is True
        or candidate.get("bridgeSequenceSatisfied") is True
        or evidence.get("motionEvidenceSatisfied") is True
        or evidence.get("bridgeSequenceSatisfied") is True
    )


def bridge_satisfied(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    payload = motivation(row)
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    return (
        row.get("bridgeSequenceSatisfied") is True
        or candidate.get("bridgeSequenceSatisfied") is True
        or evidence.get("bridgeSequenceSatisfied") is True
        or str(payload.get("strategy") or "") == "route_bridge_sequence"
    )


def title_safe(row: dict[str, Any]) -> bool:
    candidate = transition_candidate(row)
    title = candidate.get("titleSubtitleAvoidance") if isinstance(candidate.get("titleSubtitleAvoidance"), dict) else {}
    payload = motivation(row)
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    policy = " ".join(str(row.get(key) or "") for key in ("subtitlePolicy", "titleZonePolicy")).lower()
    return bool(title.get("avoidTitleOverlayCollision") is True or evidence.get("titleSubtitleAvoidance") is True or "suppress" in policy or "title" in policy)


def forbidden_hits(row: dict[str, Any]) -> list[str]:
    payload = motivation(row)
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    text = " ".join(
        str(value or "")
        for value in (
            style_blob(row),
            payload.get("strategy"),
            payload.get("viewerEffect"),
            evidence.get("sourceTransitionType"),
            evidence.get("sourceResolveEffectName"),
        )
    ).lower()
    hits = [term for term in FORBIDDEN_TERMS if term in text]
    if "spin" in text and not any(term in text for term in ("whip", "rotation match", "motivated", "route")):
        hits.append("unmotivated spin")
    return sorted(set(hits))


def motivation_complete(row: dict[str, Any]) -> bool:
    payload = motivation(row)
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    return bool(
        payload.get("strategy")
        and payload.get("viewerEffect")
        and isinstance(payload.get("allowedBecause"), list)
        and payload.get("allowedBecause")
        and evidence
    )


def repeated_decorative_run(styles: list[str]) -> int:
    best = 0
    current = ""
    length = 0
    for style in styles:
        if style == current:
            length += 1
        else:
            current = style
            length = 1
        if style in DECORATIVE_STYLES:
            best = max(best, length)
    return best


def audited_boundary(boundary: dict[str, Any], transition: dict[str, Any] | None) -> dict[str, Any]:
    if not transition:
        return {
            **boundary,
            "status": "blocked",
            "transitionRowIndex": None,
            "style": None,
            "motivationStrategy": None,
            "issues": ["missing_transition_candidate_for_boundary"],
        }
    style = normalize_style(transition)
    payload = motivation(transition)
    strategy = str(payload.get("strategy") or "")
    category = str(boundary.get("category") or "")
    pair_ok = pair_matches(boundary, transition)
    bgm_ok = has_bgm_hit(transition)
    motion_ok = motion_safe(transition, style)
    bridge_ok = bridge_satisfied(transition)
    title_ok = title_safe(transition)
    hits = forbidden_hits(transition)
    issues: list[str] = []
    if not pair_ok:
        issues.append("transition_not_tied_to_this_from_to_pair")
    if not motivation_complete(transition):
        issues.append("missing_transition_motivation_payload")
    if not bgm_ok:
        issues.append("missing_bgm_phrase_or_hit_motivation")
    if style in MOTION_STYLES and not motion_ok:
        issues.append("motion_transition_without_motion_or_bridge_evidence")
    if category in {"chapter_boundary", "timeline_gap"} and not bridge_ok and strategy not in {"route_bridge_sequence", "motion_match_on_bgm_hit"}:
        issues.append("route_jump_without_bridge_or_motion_motivation")
    if category in {"title_boundary", "ending_transition"} and not title_ok:
        issues.append("title_or_ending_transition_without_title_safe_handoff")
    if category in IMPORTANT_CATEGORIES and style == "clean_cut" and not bridge_ok and strategy == "clean_continuity_cut":
        issues.append("important_boundary_reduced_to_unmotivated_clean_cut")
    if hits:
        issues.append("forbidden_or_random_transition_style")
    return {
        **boundary,
        "status": "passed" if not issues else "blocked",
        "transitionRowIndex": transition.get("rowIndex"),
        "transitionBoundarySeconds": transition_boundary(transition),
        "style": style,
        "motivationStrategy": strategy,
        "motivationViewerEffect": payload.get("viewerEffect"),
        "pairMatched": pair_ok,
        "hasBgmMotivation": bgm_ok,
        "motionMotivated": style in MOTION_STYLES and motion_ok,
        "bridgeMotivated": bridge_ok,
        "titleSafeMotivated": title_ok,
        "motivationPayloadComplete": motivation_complete(transition),
        "forbiddenHits": hits,
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
    styles = [str(row.get("style")) for row in audited if row.get("style")]
    decorative_run = repeated_decorative_run(styles)
    motion_count = sum(1 for row in audited if row.get("style") in MOTION_STYLES)
    blocked_rows = [row for row in audited if row.get("status") == "blocked"]
    blockers = [f"boundary {row.get('boundaryIndex')}: {', '.join(row.get('issues') or [])}" for row in blocked_rows[:80]]
    if decorative_run >= 4:
        blockers.append(f"decorative transition style repeats {decorative_run} times consecutively")
    if len(audited) >= 8 and motion_count > math.ceil(len(audited) * 0.35):
        blockers.append(f"too many motion/effect-driven transitions: {motion_count}/{len(audited)}")
    if boundaries and not rows:
        blockers.append("no transition rows found in selected blueprint")
    if not audited and len(clips) > 1:
        blockers.append("visual boundaries exist but no boundary rows were audited")
    warnings = []
    if blueprint_kind == "active_blueprint":
        warnings.append("audited active blueprint because no ready transition/motivation candidate was found")
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
            "motivatedBoundaryCount": sum(1 for row in audited if row.get("motivationPayloadComplete") is True),
            "pairMatchedBoundaryCount": sum(1 for row in audited if row.get("pairMatched") is True),
            "bgmMotivatedBoundaryCount": sum(1 for row in audited if row.get("hasBgmMotivation") is True),
            "bridgeMotivatedBoundaryCount": sum(1 for row in audited if row.get("bridgeMotivated") is True),
            "motionMotivatedBoundaryCount": sum(1 for row in audited if row.get("motionMotivated") is True),
            "titleSafeMotivatedBoundaryCount": sum(1 for row in audited if row.get("titleSafeMotivated") is True),
            "importantBoundaryCount": sum(1 for row in audited if row.get("category") in IMPORTANT_CATEGORIES),
            "forbiddenHitCount": sum(len(row.get("forbiddenHits") or []) for row in audited),
            "decorativeRepeatedRunMax": decorative_run,
            "styleCounts": counts(audited, "style"),
            "categoryCounts": counts(audited, "category"),
            "motivationStrategyCounts": counts(audited, "motivationStrategy"),
        },
        "boundaryRows": audited,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Motivation Contract Audit",
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
                f"- Strategy: `{row.get('motivationStrategy')}`",
                f"- Viewer effect: {row.get('motivationViewerEffect')}",
                f"- From: `{row.get('fromSourceName')}`",
                f"- To: `{row.get('toSourceName')}`",
                f"- BGM/bridge/motion/title: `{row.get('hasBgmMotivation')}` / `{row.get('bridgeMotivated')}` / `{row.get('motionMotivated')}` / `{row.get('titleSafeMotivated')}`",
                f"- Issues: `{', '.join(row.get('issues') or [])}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit narrative and visual motivation for every shot transition.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--tolerance-seconds", type=float, default=0.75)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "transition_motivation_contract_audit.json", report)
    write_markdown(package_dir / "transition_motivation_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
