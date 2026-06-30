#!/usr/bin/env python3
"""Prepare repair rows when reference videos were not reviewed as full films."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROFILE_ACCEPTED = {"ready_with_reference_batch_profile"}
MIN_REFERENCE_COUNT = 2
MIN_SAMPLE_FRAMES_PER_REFERENCE = 12

DECISION_TEMPLATE = {
    "reviewAccepted": False,
    "fullFilmTimelineStripEvidence": "",
    "openingTitleObservation": "",
    "chapterRhythmObservation": "",
    "transitionLanguageObservation": "",
    "endingAftertasteObservation": "",
    "audioBgmCaptionObservation": "",
    "nonCopyingStyleNotes": "",
    "applicableSkillUpdates": "",
    "reviewedBy": "",
    "reviewedAt": "",
    "editorNotes": "",
}

REQUIRED_DECISION_TEXT_FIELDS = tuple(key for key in DECISION_TEMPLATE if key not in {"reviewAccepted", "editorNotes"})


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


def clean(value: Any, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def safe_id(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "reference")).strip("_")
    return text[:80] or "reference"


def resolve_path(value: Any, *, base: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def existing_decisions(output_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_json(output_dir / "reference_review_repair_plan.json") or {}
    rows = data.get("repairRows") if isinstance(data, dict) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        repair_id = clean(row.get("repairId"), 120)
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if repair_id:
            out[repair_id] = dict(decision)
    return out


def merge_decision(existing: dict[str, Any] | None) -> dict[str, Any]:
    decision = dict(DECISION_TEMPLATE)
    if isinstance(existing, dict):
        decision.update(existing)
    return decision


def decision_is_closed(decision: dict[str, Any]) -> bool:
    if decision.get("reviewAccepted") is not True:
        return False
    return all(bool(clean(decision.get(key), 220)) for key in REQUIRED_DECISION_TEXT_FIELDS)


def analysis_markdown_path(analysis_path: Path) -> Path:
    return analysis_path.with_suffix(".md")


def sample_coverage(sample_frames: list[dict[str, Any]], duration_seconds: float) -> dict[str, Any]:
    seconds: list[float] = []
    for row in sample_frames:
        if not isinstance(row, dict):
            continue
        try:
            seconds.append(float(row.get("second") or 0.0))
        except (TypeError, ValueError):
            continue
    if not seconds or duration_seconds <= 0:
        return {
            "sampleSecondCount": len(seconds),
            "hasOpeningCoverage": False,
            "hasMiddleCoverage": False,
            "hasEndingCoverage": False,
            "minRelativePosition": None,
            "maxRelativePosition": None,
        }
    rel = [min(1.0, max(0.0, second / duration_seconds)) for second in seconds]
    return {
        "sampleSecondCount": len(seconds),
        "hasOpeningCoverage": min(rel) <= 0.08,
        "hasMiddleCoverage": any(0.35 <= value <= 0.65 for value in rel),
        "hasEndingCoverage": max(rel) >= 0.85,
        "minRelativePosition": round(min(rel), 4),
        "maxRelativePosition": round(max(rel), 4),
    }


def reference_row_evidence(row: dict[str, Any], package_dir: Path) -> dict[str, Any]:
    analysis_path = resolve_path(row.get("analysisPath"), base=package_dir)
    data = load_json(analysis_path) if analysis_path else None
    data = data if isinstance(data, dict) else {}
    analysis_dir = analysis_path.parent if analysis_path else package_dir
    contact_path = resolve_path(data.get("contactSheet"), base=analysis_dir)
    sample_frames = data.get("sampleFrames") if isinstance(data.get("sampleFrames"), list) else []
    duration_seconds = float(data.get("durationSeconds") or row.get("durationSeconds") or 0.0)
    coverage = sample_coverage(sample_frames, duration_seconds)
    pacing = data.get("pacingProfile") if isinstance(data.get("pacingProfile"), dict) else {}
    audio = data.get("audioProfile") if isinstance(data.get("audioProfile"), dict) else {}
    md_path = analysis_markdown_path(analysis_path) if analysis_path else None
    return {
        "referencePath": row.get("referencePath"),
        "analysisPath": str(analysis_path) if analysis_path else None,
        "analysisExists": bool(analysis_path and analysis_path.exists()),
        "analysisMarkdown": str(md_path) if md_path else None,
        "analysisMarkdownExists": bool(md_path and md_path.exists()),
        "contactSheet": str(contact_path) if contact_path else None,
        "contactSheetExists": bool(contact_path and contact_path.exists()),
        "durationSeconds": duration_seconds,
        "durationMinutes": round(duration_seconds / 60, 3) if duration_seconds else row.get("durationMinutes"),
        "pacingStatus": row.get("pacingStatus") or pacing.get("status"),
        "audioStatus": row.get("audioStatus") or audio.get("status"),
        "estimatedShotCount": row.get("estimatedShotCount") or pacing.get("estimatedShotCount"),
        "sceneCutCount": pacing.get("sceneCutCount"),
        "sampleFrameCount": len(sample_frames) or int(row.get("sampleFrameCount") or 0),
        **coverage,
    }


def evidence_issues(evidence: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not evidence.get("analysisExists"):
        issues.append("per-video reference_analysis.json is missing")
        return issues
    if not evidence.get("analysisMarkdownExists"):
        issues.append("per-video reference_analysis.md review worksheet is missing")
    if evidence.get("pacingStatus") != "analyzed":
        issues.append("scene-cut pacing was not analyzed")
    if evidence.get("audioStatus") != "analyzed":
        issues.append("audio loudness/silence was not analyzed")
    if int(evidence.get("estimatedShotCount") or 0) <= 0:
        issues.append("estimated shot count is missing")
    if int(evidence.get("sampleFrameCount") or 0) < MIN_SAMPLE_FRAMES_PER_REFERENCE:
        issues.append(f"sample frame worksheet has fewer than {MIN_SAMPLE_FRAMES_PER_REFERENCE} frames")
    if not evidence.get("contactSheetExists"):
        issues.append("contact sheet or timeline strip evidence is missing")
    if not evidence.get("hasOpeningCoverage"):
        issues.append("sample evidence does not cover the opening")
    if not evidence.get("hasMiddleCoverage"):
        issues.append("sample evidence does not cover the middle")
    if not evidence.get("hasEndingCoverage"):
        issues.append("sample evidence does not cover the ending")
    return issues


def profile_issues(profile: dict[str, Any], profile_path: Path) -> list[str]:
    issues: list[str] = []
    if not profile_path.exists():
        return ["reference/reference_batch_profile.json is missing"]
    status = profile.get("status")
    if status not in PROFILE_ACCEPTED:
        issues.append(f"reference batch profile status is {status or 'unknown'}")
    summary = profile.get("summary") if isinstance(profile.get("summary"), dict) else {}
    reference_count = int(summary.get("referenceVideoCount") or 0)
    if reference_count < MIN_REFERENCE_COUNT:
        issues.append(f"reference batch profile has fewer than {MIN_REFERENCE_COUNT} analyzed videos")
    if int(summary.get("failedReferenceCount") or 0) > 0:
        issues.append("one or more reference videos failed analysis")
    usage = profile.get("referenceUsageContract") if isinstance(profile.get("referenceUsageContract"), dict) else {}
    if "copy" not in str(usage.get("forbidden") or "").lower() or "non-copying" not in str(usage.get("allowed") or "").lower():
        issues.append("non-copying usage contract is missing or weak")
    targets = profile.get("styleTargets") if isinstance(profile.get("styleTargets"), dict) else {}
    for key in ("openingTarget", "transitionTarget", "endingTarget"):
        if not clean(targets.get(key), 120):
            issues.append(f"{key} is missing from style targets")
    return issues


def build_profile_row(
    *,
    package_dir: Path,
    profile_path: Path,
    issues: list[str],
    previous: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not issues:
        return None
    repair_id = "reference_review_batch_profile"
    return {
        "repairId": repair_id,
        "priority": "P0",
        "phase": "reference_style",
        "issueType": "refresh_reference_batch_profile",
        "sourceReport": "reference_batch_profile",
        "sourceReportPath": str(profile_path),
        "issue": "; ".join(issues),
        "ownerScript": "prepare_reference_batch_profile.py",
        "requiredArtifact": "reference/reference_batch_profile.json",
        "command": "python3 <skill-dir>/scripts/prepare_reference_batch_profile.py --reference-dir <reference-dir> --package-dir <package> --recursive --force --frames 48 --json",
        "requiredAction": "Rebuild the reference batch profile from the supplied full reference video folder before style, rhythm, transition, or final QA claims.",
        "acceptanceEvidence": "reference_batch_profile.json has at least two successful references, analyzed pacing/audio, non-copying usage terms, and opening/transition/ending targets.",
        "forbiddenWorkaround": "Do not learn from a few screenshots, old downloaded images, copied creator assets, or a single reference clip when the user supplied a reference set.",
        "affectedEvidence": {"profilePath": str(profile_path), "packageDir": str(package_dir)},
        "decision": merge_decision(previous.get(repair_id)),
    }


def build_reference_row(
    *,
    ordinal: int,
    row: dict[str, Any],
    evidence: dict[str, Any],
    previous: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    name = Path(str(row.get("referencePath") or f"reference_{ordinal}")).stem
    repair_id = f"reference_review_{safe_id(name)}"
    decision = merge_decision(previous.get(repair_id))
    issues = evidence_issues(evidence)
    if not decision_is_closed(decision):
        issues.append("full-film reference review decision fields are not complete")
    if not issues:
        return None
    return {
        "repairId": repair_id,
        "priority": "P0",
        "phase": "reference_style",
        "issueType": "complete_full_reference_review",
        "sourceReport": "reference_batch_profile",
        "sourceReportPath": evidence.get("analysisPath"),
        "referencePath": row.get("referencePath"),
        "issue": "; ".join(dict.fromkeys(issues)),
        "ownerScript": "analyze_reference_video.py + Codex visual review",
        "requiredArtifact": "reference_review_repair_plan/reference_review_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/analyze_reference_video.py --reference <reference-video> --output-dir <package>/reference/reference_items/<id> --frames 48 --json",
        "requiredAction": "Review the reference as a full film: opening/title construction, chapter rhythm, transition context, ending aftertaste, audio/BGM/caption behavior, and non-copying takeaways. Fill every decision field in this row before rerunning the plan.",
        "acceptanceEvidence": "The row has reviewAccepted=true plus timeline-strip evidence and concrete observations for opening/title, chapter rhythm, transition language, ending, audio/BGM/caption, and reusable non-copying Skill lessons.",
        "forbiddenWorkaround": "Do not mark this closed from sampled-frame impressions alone, copied reference titles/music/subtitles, vague style adjectives, or unreviewed contact sheets.",
        "affectedEvidence": evidence,
        "decision": decision,
    }


def build_plan(package_dir: Path, output_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    previous = existing_decisions(output_dir)
    profile_path = package_dir / "reference" / "reference_batch_profile.json"
    profile = load_json(profile_path) or {}
    profile = profile if isinstance(profile, dict) else {}
    rows = profile.get("referenceReports") if isinstance(profile.get("referenceReports"), list) else []
    repair_rows: list[dict[str, Any]] = []

    profile_row = build_profile_row(
        package_dir=package_dir,
        profile_path=profile_path,
        issues=profile_issues(profile, profile_path),
        previous=previous,
    )
    if profile_row:
        repair_rows.append(profile_row)

    reference_evidence: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        evidence = reference_row_evidence(row, package_dir)
        reference_evidence.append(evidence)
        repair_row = build_reference_row(ordinal=ordinal, row=row, evidence=evidence, previous=previous)
        if repair_row:
            repair_rows.append(repair_row)

    closed_decisions = sum(1 for row in rows if isinstance(row, dict) and decision_is_closed(merge_decision(previous.get(f"reference_review_{safe_id(Path(str(row.get('referencePath') or 'reference')).stem)}"))))
    status = "ready_no_reference_review_repairs_needed" if not repair_rows else "ready_with_reference_review_repair_plan"
    summary = {
        "repairRowCount": len(repair_rows),
        "referenceVideoCount": len(rows),
        "referenceRowsWithClosedFullReviewDecision": closed_decisions,
        "profileStatus": profile.get("status"),
        "profileAccepted": profile.get("status") in PROFILE_ACCEPTED,
        "referencesWithAnalysis": sum(1 for item in reference_evidence if item.get("analysisExists")),
        "referencesWithContactSheet": sum(1 for item in reference_evidence if item.get("contactSheetExists")),
        "referencesWithOpeningMiddleEndingCoverage": sum(
            1
            for item in reference_evidence
            if item.get("hasOpeningCoverage") and item.get("hasMiddleCoverage") and item.get("hasEndingCoverage")
        ),
        "ownerScripts": sorted({str(row.get("ownerScript")) for row in repair_rows if row.get("ownerScript")}),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "summary": summary,
        "inputs": {
            "profile": {"path": str(profile_path), "exists": profile_path.exists(), "status": profile.get("status")},
            "referenceEvidence": reference_evidence,
        },
        "repairRows": repair_rows,
        "nextActions": [
            "Generate or refresh the reference batch profile with enough timeline samples for each supplied reference video.",
            "Review every reference video as a full film, not only a few frames: opening, chapters, transitions, ending, BGM/audio/captions, and title/cover construction.",
            "Fill the decision fields in each repair row, then rerun this script until it returns ready_no_reference_review_repairs_needed.",
            "Only then run reference profile application, reference transition profile, transition flow, final QA, V14, and Skill maturity gates.",
        ],
        "safety": safety(),
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Reference Review Repair Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Repair Rows",
    ]
    if not plan.get("repairRows"):
        lines.append("- None.")
    for row in plan.get("repairRows", [])[:200]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Source: `{row.get('sourceReportPath')}`",
                f"- Issue: {row.get('issue')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Required action: {row.get('requiredAction')}",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
                "- Decision fields to complete:",
            ]
        )
        for key, value in row.get("decision", {}).items():
            lines.append(f"  - `{key}`: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(
        [
            "",
            "## Contract",
            "- Reference learning is not complete until full-film evidence exists for each supplied reference video.",
            "- Contact sheets are navigation aids; final style rules must be based on beginning-to-end review of opening, chapters, transitions, ending, audio, captions, and title/cover construction.",
            "- Do not copy reference assets. Convert observations into non-copying rhythm, shot-function, title, transition, BGM, caption, and ending rules.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare repair rows for incomplete full-film reference review.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/reference_review_repair_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "reference_review_repair_plan"
    plan = build_plan(package_dir, output_dir)
    write_json(output_dir / "reference_review_repair_plan.json", plan)
    write_markdown(output_dir / "reference_review_repair_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
