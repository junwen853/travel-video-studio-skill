#!/usr/bin/env python3
"""Audit whether the edit uses a reference-like travel scene grammar."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


FUNCTION_TERMS = {
    "context": (
        "person",
        "people",
        "face",
        "reaction",
        "talk",
        "vlog",
        "companion",
        "friend",
        "family",
        "context",
        "promise",
        "人",
        "朋友",
        "家人",
        "反应",
        "口播",
        "说话",
        "同行",
    ),
    "movement": (
        "airport",
        "station",
        "train",
        "subway",
        "metro",
        "road",
        "car",
        "taxi",
        "bus",
        "ferry",
        "boat",
        "plane",
        "walk",
        "walking",
        "bridge",
        "luggage",
        "ticket",
        "window",
        "escalator",
        "route",
        "arrival",
        "departure",
        "机场",
        "车站",
        "火车",
        "地铁",
        "路",
        "车",
        "船",
        "飞机",
        "步行",
        "桥",
        "行李",
        "票",
        "车窗",
        "抵达",
        "出发",
    ),
    "texture": (
        "street",
        "shop",
        "market",
        "food",
        "restaurant",
        "hotel",
        "room",
        "interior",
        "sign",
        "weather",
        "rain",
        "night",
        "table",
        "coffee",
        "waiting",
        "crowd",
        "convenience",
        "街",
        "店",
        "市场",
        "饭",
        "餐",
        "酒店",
        "房间",
        "室内",
        "路牌",
        "天气",
        "雨",
        "夜",
        "桌",
        "等待",
        "人群",
        "便利店",
    ),
    "payoff": (
        "aerial",
        "drone",
        "skyline",
        "landmark",
        "tower",
        "castle",
        "temple",
        "shrine",
        "museum",
        "coast",
        "sea",
        "ocean",
        "mountain",
        "park",
        "activity",
        "show",
        "view",
        "panorama",
        "harbor",
        "dotonbori",
        "skytree",
        "航拍",
        "天际线",
        "地标",
        "塔",
        "城",
        "寺",
        "神社",
        "博物馆",
        "海",
        "山",
        "公园",
        "景点",
        "活动",
        "道顿堀",
    ),
    "aftertaste": (
        "sunset",
        "dusk",
        "quiet",
        "ending",
        "final",
        "callback",
        "aftertaste",
        "night",
        "window",
        "road",
        "train",
        "airport",
        "departure",
        "leaving",
        "fade",
        "夕阳",
        "黄昏",
        "安静",
        "结尾",
        "回望",
        "夜景",
        "车窗",
        "路",
        "火车",
        "机场",
        "离开",
        "回程",
    ),
}

WEAK_TERMS = (
    "black slate",
    "placeholder",
    "generic",
    "slideshow",
    "test",
    "sample",
    "duplicate",
    "blur",
    "obstruct",
    "黑屏",
    "占位",
    "通用",
    "模糊",
    "遮挡",
    "重复",
)


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
        for key in (
            "role",
            "purpose",
            "place",
            "city",
            "country",
            "chapter",
            "titleText",
            "subtitle",
            "sourcePath",
            "sourceName",
            "name",
            "notes",
        )
    ).lower()


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in text for term in terms)


def is_video_clip(clip: dict[str, Any]) -> bool:
    text = clip_text(clip)
    if "subtitle_overlay" in text or str(clip.get("sourcePath") or "").lower().endswith((".srt", ".ass", ".vtt")):
        return False
    track_type = str(clip.get("trackType") or "video").lower()
    if track_type not in {"", "video"}:
        return False
    return int(as_float(clip.get("mediaType"), 1) or 1) == 1


def classify_clip(clip: dict[str, Any]) -> list[str]:
    text = clip_text(clip)
    functions = [name for name, terms in FUNCTION_TERMS.items() if has_any(text, terms)]
    if not functions:
        functions.append("unclassified")
    return functions


def weak_clip(clip: dict[str, Any]) -> bool:
    return has_any(clip_text(clip), WEAK_TERMS)


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
        (package_dir / "effect_motion_blueprint" / "effect_motion_blueprint_report.json", "candidateBlueprint", "effect_motion_candidate"),
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


def visual_clips(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    return sorted([row for row in rows if isinstance(row, dict) and is_video_clip(row)], key=lambda item: (timeline_start(item), timeline_end(item)))


def reference_profile(package_dir: Path, explicit: str | None = None) -> tuple[dict[str, Any] | None, Path | None]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend([package_dir / "reference" / "reference_batch_profile.json", package_dir / "reference" / "reference_analysis.json"])
    for path in candidates:
        if path.exists():
            data = load_json(path)
            if isinstance(data, dict):
                return data, path
    return None, None


def opening_rows(clips: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    cutoff = min(max(duration * 0.15, 45.0), 180.0)
    rows = [clip for clip in clips if timeline_start(clip) <= cutoff]
    return rows[: max(3, min(len(rows), 18))]


def ending_rows(clips: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not clips:
        return []
    cutoff = max(0.0, duration - min(max(duration * 0.10, 45.0), 180.0))
    rows = [clip for clip in clips if timeline_end(clip) >= cutoff]
    return rows[-max(3, min(len(rows), 12)) :]


def functions_in(rows: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        out.update(classify_clip(row))
    out.discard("unclassified")
    return out


def chapter_key(clip: dict[str, Any]) -> str:
    for key in ("chapterIndex", "chapter", "place", "city"):
        value = clip.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "timeline"


def chapter_audits(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        grouped.setdefault(chapter_key(clip), []).append(clip)
    rows: list[dict[str, Any]] = []
    for index, (key, items) in enumerate(grouped.items(), start=1):
        funcs = sorted(functions_in(items))
        required = {"movement", "texture", "payoff"}
        if len(items) >= 4:
            required.add("aftertaste")
        missing = sorted(required - set(funcs))
        rows.append(
            {
                "chapterIndex": index,
                "chapterKey": key,
                "clipCount": len(items),
                "functions": funcs,
                "missingFunctions": missing,
                "weakClipCount": sum(1 for item in items if weak_clip(item)),
                "status": "passed" if not missing and not all(weak_clip(item) for item in items) else "blocked",
            }
        )
    return rows


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
    reference, reference_path = reference_profile(package_dir, args.reference_analysis)
    pair_continuity = load_json(package_dir / "transition_pair_continuity_contract_audit.json") or {}
    opening_story = load_json(package_dir / "opening_story_plan" / "opening_story_plan.json") or {}
    chapter_arc = load_json(package_dir / "chapter_arc_plan" / "chapter_arc_plan.json") or {}
    creator_cut = load_json(package_dir / "creator_cut_plan" / "creator_cut_plan.json") or {}
    if not isinstance(blueprint, dict):
        return {
            "createdAt": datetime.now().isoformat(timespec="seconds"),
            "status": "blocked",
            "packageDir": str(package_dir),
            "inputs": {"blueprint": str(blueprint_path), "blueprintExists": blueprint_path.exists(), "blueprintKind": blueprint_kind},
            "summary": {},
            "opening": {},
            "chapters": [],
            "ending": {},
            "blockers": [f"missing or unreadable blueprint: {blueprint_path}"],
            "warnings": [],
            "safety": safety(),
        }
    clips = visual_clips(blueprint)
    duration = max((timeline_end(clip) for clip in clips), default=0.0)
    opening = opening_rows(clips, duration)
    ending = ending_rows(clips, duration)
    opening_functions = functions_in(opening)
    ending_functions = functions_in(ending)
    chapters = chapter_audits(clips)
    pair_summary = pair_continuity.get("summary") if isinstance(pair_continuity.get("summary"), dict) else {}
    reference_targets = reference.get("styleTargets") if isinstance(reference and reference.get("styleTargets"), dict) else {}
    blockers: list[str] = []
    warnings: list[str] = []
    if not clips:
        blockers.append("no visual clips available for reference scene grammar audit")
    if len(opening_functions) < 2:
        blockers.append("opening lacks enough scene-function variety")
    if "payoff" not in opening_functions:
        blockers.append("opening lacks destination-proof payoff imagery")
    if not ({"movement", "texture", "context"} & opening_functions):
        blockers.append("opening lacks route reality, lived-in texture, or human context")
    if opening and all(weak_clip(row) for row in opening):
        blockers.append("opening is built only from weak, placeholder, duplicate, or generic clips")
    if sum(1 for row in chapters if row.get("status") == "passed") < max(1, len(chapters) - 1):
        blockers.append("too many chapters lack movement/texture/payoff scene grammar")
    if "aftertaste" not in ending_functions and not ({"movement", "payoff"} <= ending_functions):
        blockers.append("ending lacks aftertaste, route callback, or final scenic movement")
    if ending and all(weak_clip(row) for row in ending):
        blockers.append("ending is built only from weak, placeholder, duplicate, or generic clips")
    if pair_continuity.get("status") != "passed" or int(pair_summary.get("weakPairFitCount") or 0) > 0:
        blockers.append("transition pair-continuity audit must pass before reference scene grammar can pass")
    if not opening_story:
        blockers.append("opening_story_plan is missing")
    if not chapter_arc:
        blockers.append("chapter_arc_plan is missing")
    if not creator_cut:
        blockers.append("creator_cut_plan is missing")
    if not reference:
        warnings.append("no package reference profile found; using bundled Parallel World/Malta scene grammar only")
    elif reference.get("referenceUsageContract") is None and not reference_targets:
        blockers.append("reference profile exists but lacks non-copying style targets or usage contract")
    blocked_chapters = [row for row in chapters if row.get("status") == "blocked"]
    for row in blocked_chapters[:40]:
        missing = ", ".join(row.get("missingFunctions") or [])
        if missing:
            blockers.append(f"chapter {row.get('chapterKey')}: missing {missing}")
        elif int(row.get("weakClipCount") or 0) >= int(row.get("clipCount") or 0):
            blockers.append(f"chapter {row.get('chapterKey')}: all clips are weak/placeholders")
        else:
            blockers.append(f"chapter {row.get('chapterKey')}: scene grammar blocked")
    status = "passed" if not blockers else "blocked"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "blueprint": str(blueprint_path),
            "blueprintExists": blueprint_path.exists(),
            "blueprintKind": blueprint_kind,
            "referenceAnalysis": str(reference_path) if reference_path else None,
            "referenceProfileAvailable": bool(reference),
        },
        "summary": {
            "visualClipCount": len(clips),
            "durationSeconds": round(duration, 3),
            "openingClipCount": len(opening),
            "openingFunctionCount": len(opening_functions),
            "openingFunctions": sorted(opening_functions),
            "chapterCount": len(chapters),
            "chaptersPassed": sum(1 for row in chapters if row.get("status") == "passed"),
            "chaptersBlocked": len(blocked_chapters),
            "endingClipCount": len(ending),
            "endingFunctions": sorted(ending_functions),
            "endingAftertasteFound": "aftertaste" in ending_functions,
            "pairContinuityStatus": pair_continuity.get("status"),
            "weakPairFitCount": pair_summary.get("weakPairFitCount"),
            "openingStoryPlanExists": bool(opening_story),
            "chapterArcPlanExists": bool(chapter_arc),
            "creatorCutPlanExists": bool(creator_cut),
            "referenceProfileAvailable": bool(reference),
            "blockerCount": len(blockers),
        },
        "opening": {
            "status": "passed" if not any(item.startswith("opening ") for item in blockers) else "blocked",
            "functions": sorted(opening_functions),
            "clipRows": clip_rows(opening),
        },
        "chapters": chapters,
        "ending": {
            "status": "passed" if not any(item.startswith("ending ") for item in blockers) else "blocked",
            "functions": sorted(ending_functions),
            "clipRows": clip_rows(ending),
        },
        "blockers": blockers,
        "warnings": warnings,
        "safety": safety(),
    }


def clip_rows(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, clip in enumerate(clips, start=1):
        rows.append(
            {
                "index": index,
                "startSeconds": round(timeline_start(clip), 3),
                "endSeconds": round(timeline_end(clip), 3),
                "sourceName": Path(str(clip.get("sourcePath") or clip.get("sourceName") or "")).name,
                "chapterKey": chapter_key(clip),
                "functions": classify_clip(clip),
                "weakClip": weak_clip(clip),
            }
        )
    return rows


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Reference Scene Grammar Contract Audit",
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
    lines.extend(["", "## Chapters"])
    for row in report.get("chapters") or []:
        lines.extend(
            [
                "",
                f"### {row.get('chapterKey')}",
                f"- Status: `{row.get('status')}`",
                f"- Clip count: `{row.get('clipCount')}`",
                f"- Functions: `{', '.join(row.get('functions') or [])}`",
                f"- Missing: `{', '.join(row.get('missingFunctions') or [])}`",
                f"- Weak clips: `{row.get('weakClipCount')}`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit reference-like travel scene grammar.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--blueprint")
    parser.add_argument("--reference-analysis")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "reference_scene_grammar_contract_audit.json", report)
    write_markdown(package_dir / "reference_scene_grammar_contract_audit.md", report)
    payload = report if args.json else {"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
