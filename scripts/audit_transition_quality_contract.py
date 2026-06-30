#!/usr/bin/env python3
"""Audit final transition quality on the best available Resolve blueprint."""

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

MOTION_TERMS = ("whip", "rotation", "speed", "ramp", "push", "slide", "blur")
CRAFT_TERMS = ("whip", "rotation", "speed", "ramp", "dissolve", "match", "bridge", "title", "push", "slide")


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


def is_video_clip(clip: dict[str, Any]) -> bool:
    track_type = str(clip.get("trackType") or "video").lower()
    return track_type in {"", "video"} and int(as_float(clip.get("mediaType"), 1) or 1) == 1


def timeline_start(clip: dict[str, Any]) -> float:
    return float(as_float(clip.get("timelineStartSeconds") or clip.get("recordStartSeconds") or clip.get("startSeconds"), 0.0) or 0.0)


def timeline_end(clip: dict[str, Any]) -> float:
    start = timeline_start(clip)
    explicit = as_float(clip.get("timelineEndSeconds") or clip.get("recordEndSeconds") or clip.get("endSeconds"))
    if explicit is not None and explicit > start:
        return explicit
    return start + float(as_float(clip.get("durationSeconds") or clip.get("sourceDurationSeconds"), 0.0) or 0.0)


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


def repeated_decorative_run(styles: list[str]) -> int:
    best = 0
    current = ""
    length = 0
    decorative = {"whip_pan", "rotation", "speed_ramp", "dissolve", "push_slide"}
    for style in styles:
        if style == current:
            length += 1
        else:
            current = style
            length = 1
        if style in decorative:
            best = max(best, length)
    return best


def has_bgm_hit(row: dict[str, Any]) -> bool:
    candidate = row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}
    recipe = candidate.get("selectedRecipe") if isinstance(candidate.get("selectedRecipe"), dict) else {}
    bgm = candidate.get("bgmSync") if isinstance(candidate.get("bgmSync"), dict) else {}
    return bool(
        row.get("bgmHitSeconds") is not None
        or recipe.get("bgmHitSeconds") is not None
        or bgm.get("hitSeconds") is not None
        or row.get("bgmPhraseCue")
    )


def title_safe(row: dict[str, Any]) -> bool:
    candidate = row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}
    title = candidate.get("titleSubtitleAvoidance") if isinstance(candidate.get("titleSubtitleAvoidance"), dict) else {}
    policy = " ".join(str(row.get(key) or "") for key in ("subtitlePolicy", "titleZonePolicy")).lower()
    return bool(
        title.get("avoidTitleOverlayCollision") is True
        or title.get("suppressSubtitleSecondsBefore")
        or "suppress" in policy
        or "title" in policy
    )


def has_keyframes_or_clean_cut(row: dict[str, Any]) -> bool:
    candidate = row.get("transitionPolishCandidate") if isinstance(row.get("transitionPolishCandidate"), dict) else {}
    recipe = candidate.get("selectedRecipe") if isinstance(candidate.get("selectedRecipe"), dict) else {}
    if isinstance(recipe.get("keyframePlan"), list) and recipe.get("keyframePlan"):
        return True
    if isinstance(row.get("keyframePlan"), list) and row.get("keyframePlan"):
        return True
    return normalize_style(row) == "clean_cut"


def audio_bgm_only(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            row.get("audioPolicy"),
            (row.get("transitionPolishCandidate") or {}).get("audioPolicy") if isinstance(row.get("transitionPolishCandidate"), dict) else "",
        )
    ).lower()
    return "bgm" in text and "voice" in text


def forbidden_hits(row: dict[str, Any]) -> list[str]:
    text = style_blob(row)
    hits = [term for term in FORBIDDEN_TERMS if term in text]
    if "spin" in text and not any(term in text for term in ("whip", "rotation match", "motivated", "route")):
        hits.append("unmotivated spin")
    return sorted(set(hits))


def row_motion_safe(row: dict[str, Any]) -> bool:
    text = style_blob(row)
    is_motion = bool(row.get("motionStyle")) or any(term in text for term in MOTION_TERMS)
    if not is_motion:
        return True
    return row.get("motionHasEvidence") is True or row.get("bridgeSequenceSatisfied") is True


def is_crafted(row: dict[str, Any]) -> bool:
    text = style_blob(row)
    if row.get("bridgeSequenceSatisfied") is True:
        return True
    return any(term in text for term in CRAFT_TERMS)


def transition_rows(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("transitions") if isinstance(blueprint.get("transitions"), list) else []
    rows = [row for row in rows if isinstance(row, dict)]
    if rows:
        return rows
    fallback = blueprint.get("transitionPolishCandidates") if isinstance(blueprint.get("transitionPolishCandidates"), list) else []
    out = []
    for item in fallback:
        if isinstance(item, dict):
            out.append({"transitionPolishCandidate": item, "audioPolicy": item.get("audioPolicy")})
    return out


def audited_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    hits = forbidden_hits(row)
    result = {
        "rowIndex": row.get("rowIndex") or index,
        "style": normalize_style(row),
        "hasBgmHit": has_bgm_hit(row),
        "titleSafe": title_safe(row),
        "hasKeyframesOrCleanCut": has_keyframes_or_clean_cut(row),
        "bgmOnlyAudio": audio_bgm_only(row),
        "motionSafe": row_motion_safe(row),
        "crafted": is_crafted(row),
        "requiresBridgeInsert": row.get("requiresBridgeInsert") is True,
        "bridgeSequenceSatisfied": row.get("bridgeSequenceSatisfied") is True,
        "forbiddenHits": hits,
    }
    issues = []
    if not result["hasBgmHit"]:
        issues.append("missing_bgm_hit_or_phrase_cue")
    if not result["titleSafe"]:
        issues.append("missing_title_subtitle_avoidance")
    if not result["hasKeyframesOrCleanCut"]:
        issues.append("missing_keyframe_plan")
    if not result["bgmOnlyAudio"]:
        issues.append("missing_bgm_only_audio_policy")
    if not result["motionSafe"]:
        issues.append("motion_effect_without_evidence")
    if result["requiresBridgeInsert"] and not result["bridgeSequenceSatisfied"]:
        issues.append("bridge_required_but_not_satisfied")
    if hits:
        issues.append("forbidden_transition_style")
    result["issues"] = issues
    result["status"] = "passed" if not issues else "blocked"
    return result


def build_report(package_dir: Path, blueprint_arg: str | None = None) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint, blueprint_path, blueprint_kind = choose_blueprint(package_dir, blueprint_arg)
    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {"blueprint": str(blueprint_path), "blueprintExists": blueprint_path.exists(), "blueprintKind": blueprint_kind},
            "summary": {},
            "transitionRows": [],
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    video_clips = sorted([clip for clip in clips if isinstance(clip, dict) and is_video_clip(clip)], key=lambda item: (timeline_start(item), timeline_end(item)))
    boundary_count = max(0, len(video_clips) - 1)
    raw_rows = transition_rows(blueprint)
    rows = [audited_row(index, row) for index, row in enumerate(raw_rows, start=1)]
    styles = [row["style"] for row in rows]
    transition_count = len(rows)
    crafted_count = sum(1 for row in rows if row["crafted"])
    min_crafted = 0 if transition_count < 5 else max(2, min(6, math.ceil(transition_count * 0.12)))
    decorative_run = repeated_decorative_run(styles)
    blockers = []
    warnings = []
    if boundary_count and transition_count < boundary_count:
        blockers.append(f"transition coverage incomplete: {transition_count}/{boundary_count} visual boundaries")
    if transition_count and crafted_count < min_crafted:
        blockers.append(f"not enough crafted transitions/bridges for long-form rhythm: {crafted_count}/{min_crafted}")
    if decorative_run >= 4:
        blockers.append(f"decorative transition style repeats {decorative_run} times consecutively")
    for row in rows:
        if row["status"] == "blocked":
            blockers.append(f"row {row['rowIndex']}: {', '.join(row['issues'])}")
    if blueprint_kind == "active_blueprint":
        warnings.append("audited active blueprint because no ready transition polish candidate was found")
    status = "passed" if not blockers and transition_count > 0 else "blocked"
    if transition_count == 0 and boundary_count > 0:
        blockers.append("no transition rows or transition polish candidates found")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
        },
        "summary": {
            "visualClipCount": len(video_clips),
            "visualBoundaryCount": boundary_count,
            "transitionRowCount": transition_count,
            "transitionCoverageRatio": round3(transition_count / boundary_count) if boundary_count else 1.0,
            "rowsWithBgmHit": sum(1 for row in rows if row["hasBgmHit"]),
            "rowsTitleSafe": sum(1 for row in rows if row["titleSafe"]),
            "rowsWithKeyframesOrCleanCut": sum(1 for row in rows if row["hasKeyframesOrCleanCut"]),
            "bgmOnlyAudioRows": sum(1 for row in rows if row["bgmOnlyAudio"]),
            "motionRowCount": sum(1 for row in rows if row["style"] in {"whip_pan", "rotation", "speed_ramp", "push_slide"}),
            "motionRowsWithEvidence": sum(1 for row in rows if row["style"] in {"whip_pan", "rotation", "speed_ramp", "push_slide"} and row["motionSafe"]),
            "craftedTransitionCount": crafted_count,
            "minimumCraftedTransitionCount": min_crafted,
            "bridgeRequiredRows": sum(1 for row in rows if row["requiresBridgeInsert"]),
            "bridgeSatisfiedRows": sum(1 for row in rows if row["requiresBridgeInsert"] and row["bridgeSequenceSatisfied"]),
            "forbiddenHitCount": sum(len(row["forbiddenHits"]) for row in rows),
            "decorativeRepeatedRunMax": decorative_run,
            "blockedRowCount": sum(1 for row in rows if row["status"] == "blocked"),
        },
        "transitionRows": rows,
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Transition Quality Contract Audit",
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
    lines.extend(["", "## Rows"])
    for row in report.get("transitionRows") or []:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('style')}",
                f"- Status: `{row.get('status')}`",
                f"- BGM hit: `{row.get('hasBgmHit')}`",
                f"- Title safe: `{row.get('titleSafe')}`",
                f"- Keyframes or clean cut: `{row.get('hasKeyframesOrCleanCut')}`",
                f"- BGM-only audio: `{row.get('bgmOnlyAudio')}`",
                f"- Motion safe: `{row.get('motionSafe')}`",
                f"- Crafted: `{row.get('crafted')}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit transition quality on a travel-video Resolve blueprint.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args.blueprint)
    write_json(package_dir / "transition_quality_contract_audit.json", report)
    write_markdown(package_dir / "transition_quality_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
