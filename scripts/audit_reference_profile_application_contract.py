#!/usr/bin/env python3
"""Audit that a reference batch profile is applied by downstream edit plans."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


DIRECT_REFERENCE_ARTIFACTS = {
    "chapter_arc_plan",
    "edit_rhythm_plan",
    "reference_scene_grammar_contract_audit",
    "reference_style_alignment_audit",
}

ARTIFACTS: list[dict[str, Any]] = [
    {
        "id": "opening_story_plan",
        "path": "opening_story_plan/opening_story_plan.json",
        "accepted": {"ready_with_opening_story_plan"},
        "terms": ("viewer promise", "destination proof", "first chapter handoff"),
        "role": "opening_story_support",
    },
    {
        "id": "chapter_arc_plan",
        "path": "chapter_arc_plan/chapter_arc_plan.json",
        "accepted": {"ready_with_chapter_arc_plan"},
        "terms": ("referenceRule", "referenceBatchProfileStatus", "referenceAnchoredButNonCopying"),
        "role": "direct_reference_application",
    },
    {
        "id": "edit_rhythm_plan",
        "path": "edit_rhythm_plan/edit_rhythm_plan.json",
        "accepted": {"ready_with_edit_rhythm_plan"},
        "terms": ("referenceProfile", "targetRhythmProfile", "referenceReady"),
        "role": "direct_reference_application",
    },
    {
        "id": "creator_cut_plan",
        "path": "creator_cut_plan/creator_cut_plan.json",
        "accepted": {"ready_with_creator_cut_plan"},
        "terms": ("referenceAnchoredButNonCopying", "creatorFunction", "editorialTier"),
        "role": "creator_shot_selection_support",
    },
    {
        "id": "transition_grammar_plan",
        "path": "transition_grammar_plan/transition_grammar_plan.json",
        "accepted": {"ready_with_transition_grammar_plan"},
        "terms": ("physicalBridgeBeforeMotionEffect", "bgmPhraseAwarenessRequired", "titleZoneSafetyRequired"),
        "role": "transition_reference_support",
    },
    {
        "id": "transition_execution_plan",
        "path": "transition_execution_plan/transition_execution_plan.json",
        "accepted": {"ready_with_transition_execution_plan"},
        "terms": ("transition", "bridge", "resolve"),
        "role": "transition_execution_support",
    },
    {
        "id": "caption_story_plan",
        "path": "caption_story_plan/caption_story_plan.json",
        "accepted": {"ready_with_dense_caption_plan"},
        "terms": ("audience-facing", "title-zone", "no-voiceover"),
        "role": "caption_story_support",
    },
    {
        "id": "audio_scene_policy_plan",
        "path": "audio_scene_policy_plan/audio_scene_policy_plan.json",
        "accepted": {"ready_with_bgm_only_scene_policy"},
        "terms": ("bgm_only_no_camera_voice", "A3", "feedback"),
        "role": "bgm_no_voiceover_support",
    },
    {
        "id": "reference_scene_grammar_contract_audit",
        "path": "reference_scene_grammar_contract_audit.json",
        "accepted": {"passed"},
        "terms": ("referenceProfileAvailable", "openingFunctions", "endingFunctions"),
        "role": "direct_reference_application",
    },
    {
        "id": "timeline_variety_contract_audit",
        "path": "timeline_variety_contract_audit.json",
        "accepted": {"passed"},
        "terms": ("movementReady", "textureReady", "payoffReady", "aftertasteReady"),
        "role": "timeline_variety_support",
    },
    {
        "id": "reference_style_alignment_audit",
        "path": "reference_style_alignment_audit.json",
        "accepted": {"passed"},
        "terms": ("reference", "transport", "lived", "landmark"),
        "role": "direct_reference_application",
    },
    {
        "id": "director_intent_contract_audit",
        "path": "director_intent_contract_audit.json",
        "accepted": {"passed", "passed_with_warnings"},
        "terms": ("director", "opening", "route", "ending"),
        "role": "director_intent_support",
    },
]

STYLE_TARGET_KEYS = {
    "targetAverageRangeSeconds",
    "targetMedianRangeSeconds",
    "longShotSoftLimitSeconds",
    "openingTarget",
    "transitionTarget",
    "endingTarget",
}


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


def summary_of(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True).lower()


def term_hits(data: Any, terms: tuple[str, ...]) -> list[str]:
    text = json_text(data)
    return [term for term in terms if term.lower() in text]


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


def profile_evidence(profile: dict[str, Any], path: Path, *, min_reference_videos: int, allow_single_reference: bool) -> dict[str, Any]:
    summary = summary_of(profile)
    pacing = profile.get("pacingProfile") if isinstance(profile.get("pacingProfile"), dict) else {}
    audio = profile.get("audioProfile") if isinstance(profile.get("audioProfile"), dict) else {}
    style_targets = profile.get("styleTargets") if isinstance(profile.get("styleTargets"), dict) else {}
    contract = profile.get("referenceUsageContract") if isinstance(profile.get("referenceUsageContract"), dict) else {}
    safety = profile.get("safety") if isinstance(profile.get("safety"), dict) else {}
    target_keys = sorted(key for key in STYLE_TARGET_KEYS if key in style_targets)
    status = profile.get("status")
    accepted_status = status == "ready_with_reference_batch_profile" or (
        allow_single_reference and status == "ready_with_single_reference_profile"
    )
    count = as_int(summary.get("referenceVideoCount"))
    ready = (
        path.exists()
        and accepted_status
        and count >= min_reference_videos
        and pacing.get("status") == "analyzed"
        and audio.get("status") == "analyzed"
        and as_int(pacing.get("estimatedShotCount")) > 0
        and len(target_keys) >= 4
        and "non-copying" in str(contract.get("allowed") or "").lower()
        and "copy" in str(contract.get("forbidden") or "").lower()
        and safety.get("writesResolve") is False
        and safety.get("downloadsExternalAssets") is False
    )
    return {
        "path": str(path),
        "exists": path.exists(),
        "status": status,
        "acceptedStatus": accepted_status,
        "referenceVideoCount": count,
        "minimumReferenceVideos": min_reference_videos,
        "failedReferenceCount": summary.get("failedReferenceCount"),
        "totalDurationMinutes": summary.get("totalDurationMinutes"),
        "pacingStatus": pacing.get("status"),
        "audioStatus": audio.get("status"),
        "estimatedShotCount": pacing.get("estimatedShotCount"),
        "averageShotLengthSeconds": pacing.get("averageShotLengthSeconds"),
        "sampleFrameCount": summary.get("sampleFrameCount"),
        "styleTargetKeys": target_keys,
        "usageAllowed": contract.get("allowed"),
        "usageForbidden": contract.get("forbidden"),
        "writesResolve": safety.get("writesResolve"),
        "downloadsExternalAssets": safety.get("downloadsExternalAssets"),
        "ready": ready,
    }


def artifact_row(package_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = package_dir / str(spec["path"])
    data = load_json(path)
    exists = isinstance(data, dict)
    status = data.get("status") if isinstance(data, dict) else None
    hits = term_hits(data, spec["terms"]) if exists else []
    direct_required = spec["id"] in DIRECT_REFERENCE_ARTIFACTS
    passed = exists and status in spec["accepted"] and (not direct_required or bool(hits))
    return {
        "id": spec["id"],
        "path": str(path),
        "exists": exists,
        "status": status,
        "acceptedStatuses": sorted(spec["accepted"]),
        "role": spec["role"],
        "directReferenceEvidenceRequired": direct_required,
        "referenceEvidenceHits": hits,
        "summary": summary_of(data),
        "passed": passed,
    }


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    profile, profile_path = find_reference_profile(package_dir, args.reference_profile)
    profile_info = profile_evidence(
        profile,
        profile_path,
        min_reference_videos=args.min_reference_videos,
        allow_single_reference=args.allow_single_reference,
    )
    artifacts = [artifact_row(package_dir, spec) for spec in ARTIFACTS]
    blockers: list[str] = []
    warnings: list[str] = []
    if not profile_info["ready"]:
        blockers.append("reference batch profile is missing, shallow, single-reference-only, or lacks pacing/audio/style-target evidence")
    for row in artifacts:
        if not row["exists"]:
            blockers.append(f"{row['id']} is missing")
        elif row["status"] not in row["acceptedStatuses"]:
            blockers.append(f"{row['id']} has status {row['status']}, expected one of {row['acceptedStatuses']}")
        elif row["directReferenceEvidenceRequired"] and not row["referenceEvidenceHits"]:
            blockers.append(f"{row['id']} does not expose direct reference-profile application evidence")
    direct_count = sum(1 for row in artifacts if row["directReferenceEvidenceRequired"] and row["passed"])
    required_direct_count = len(DIRECT_REFERENCE_ARTIFACTS)
    if direct_count < required_direct_count:
        blockers.append(f"only {direct_count}/{required_direct_count} direct reference-application artifacts passed")
    style_support_count = sum(1 for row in artifacts if row["passed"])
    if style_support_count < len(ARTIFACTS):
        warnings.append("not every downstream style-support artifact is ready")
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
            "pacingStatus": profile_info["pacingStatus"],
            "audioStatus": profile_info["audioStatus"],
            "styleTargetKeyCount": len(profile_info["styleTargetKeys"]),
            "requiredArtifactCount": len(ARTIFACTS),
            "passedArtifactCount": style_support_count,
            "blockedArtifactCount": len([row for row in artifacts if not row["passed"]]),
            "directReferenceArtifactCount": required_direct_count,
            "passedDirectReferenceArtifactCount": direct_count,
            "blockerCount": len(blockers),
        },
        "referenceProfile": profile_info,
        "artifacts": artifacts,
        "blockers": blockers,
        "warnings": warnings,
        "acceptanceRubric": {
            "pass": [
                "A multi-video reference batch profile has pacing, audio, sample-frame, style-target, and non-copying evidence.",
                "Chapter arc, edit rhythm, reference scene grammar, and reference style alignment expose direct reference-profile evidence.",
                "Opening, creator cut, transitions, captions, audio policy, director intent, and timeline variety are ready enough to carry that style into the first draft.",
            ],
            "reject": [
                "Reference videos were analyzed but only stored as a profile with no downstream plan consuming them.",
                "A cut claims Parallel World/Malta style while rhythm, chapter arc, transition, caption, or audio plans are missing.",
                "A plan copies assets, titles, music, narration, or branding from the references instead of using aggregate style targets.",
            ],
        },
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "modifiesSourceDrive": False,
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Reference Profile Application Contract Audit",
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
        "## Reference Profile",
        "",
        "```json",
        json.dumps(report["referenceProfile"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Artifact Checks",
    ]
    for row in report["artifacts"]:
        lines.extend(
            [
                "",
                f"### {row['id']}",
                f"- Status: `{row.get('status')}`",
                f"- Passed: `{row.get('passed')}`",
                f"- Role: `{row.get('role')}`",
                f"- Direct reference evidence required: `{row.get('directReferenceEvidenceRequired')}`",
                f"- Reference evidence hits: `{', '.join(row.get('referenceEvidenceHits') or [])}`",
                f"- Path: `{row.get('path')}`",
            ]
        )
    if report["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(["", "## Safety", "", "```json", json.dumps(report["safety"], ensure_ascii=False, indent=2), "```"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether a reference batch profile is applied by downstream edit plans.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--reference-profile", help="Optional explicit reference_batch_profile.json path.")
    parser.add_argument("--min-reference-videos", type=int, default=2)
    parser.add_argument("--allow-single-reference", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args)
    write_json(package_dir / "reference_profile_application_contract_audit.json", report)
    write_markdown(package_dir / "reference_profile_application_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
