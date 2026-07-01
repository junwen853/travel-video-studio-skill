#!/usr/bin/env python3
"""Prepare repair rows until the final candidate has been watched as a film."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CLOSED_STATUS = "ready_no_editorial_watchdown_repairs_needed"
OPEN_STATUS = "ready_with_editorial_watchdown_repair_plan"
TIME_RANGE_RE = re.compile(r"(?i)(?:\bfull\b|\bentire\b|\bwhole\b|全片|完整|全程|从头到尾|\d{1,2}:\d{2}(?::\d{2})?)")
GENERIC_DECISION_TEXT = {
    "ok",
    "okay",
    "pass",
    "passed",
    "done",
    "none",
    "n/a",
    "na",
    "no issue",
    "no issues",
    "fixed",
    "reviewed",
    "无",
    "无问题",
    "没问题",
    "通过",
    "完成",
    "已看",
}

DECISION_TEMPLATE = {
    "watchAccepted": False,
    "reviewedOutputPath": "",
    "watchedRange": "",
    "viewerFacingIssueSummary": "",
    "openingTitleEvidence": "",
    "chapterContinuityEvidence": "",
    "transitionEvidence": "",
    "bgmCaptionEvidence": "",
    "endingAftertasteEvidence": "",
    "referenceFitEvidence": "",
    "repairActionTaken": "",
    "postRepairAuditEvidence": "",
    "reviewedBy": "",
    "reviewedAt": "",
    "editorNotes": "",
}

REQUIRED_DECISION_TEXT_FIELDS = tuple(key for key in DECISION_TEMPLATE if key not in {"watchAccepted", "editorNotes"})

SUPPORTING_REPORTS: tuple[tuple[str, str, set[str]], ...] = (
    ("render_delivery_verification", "render_delivery_verification.json", {"passed"}),
    ("visual_audio_style_audit", "visual_audio_style_audit/visual_audio_style_audit.json", {"passed"}),
    ("story_style_contract_audit", "story_style_contract_audit.json", {"passed"}),
    ("audience_caption_contract_audit", "audience_caption_contract_audit.json", {"passed"}),
    ("bgm_musicality_contract_audit", "bgm_musicality_contract_audit.json", {"passed"}),
    ("director_intent_contract_audit", "director_intent_contract_audit.json", {"passed", "passed_with_warnings"}),
    ("director_polish_contract_audit", "director_polish_contract_audit.json", {"passed", "passed_with_warnings"}),
    ("reference_review_repair_plan", "reference_review_repair_plan/reference_review_repair_plan.json", {"ready_no_reference_review_repairs_needed"}),
    ("reference_profile_application_contract_audit", "reference_profile_application_contract_audit.json", {"passed"}),
    ("reference_transition_profile_contract_audit", "reference_transition_profile_contract_audit.json", {"passed"}),
    ("chapter_story_spine_contract_audit", "chapter_story_spine_contract_audit.json", {"passed"}),
    ("shot_flow_continuity_contract_audit", "shot_flow_continuity_contract_audit.json", {"passed"}),
    ("final_cut_smoothness_contract_audit", "final_cut_smoothness_contract_audit.json", {"passed"}),
    ("pacing_watchability_contract_audit", "pacing_watchability_contract_audit.json", {"passed"}),
    ("narrative_adjacency_contract_audit", "narrative_adjacency_contract_audit.json", {"passed"}),
    ("transition_viewer_orientation_contract_audit", "transition_viewer_orientation_contract_audit.json", {"passed"}),
    ("transition_scene_settlement_contract_audit", "transition_scene_settlement_contract_audit.json", {"passed"}),
    ("transition_flow_repair_plan", "transition_flow_repair_plan/transition_flow_repair_plan.json", {"ready_no_transition_flow_repairs_needed"}),
    ("transition_sequence_satisfaction_contract_audit", "transition_sequence_satisfaction_contract_audit.json", {"passed"}),
    ("transition_audition_quality_contract_audit", "transition_audition_quality_contract_audit.json", {"passed"}),
    ("transition_audition_visual_proof_contract_audit", "transition_audition_visual_proof_contract_audit.json", {"passed"}),
    ("transition_storyboard_contract_audit", "transition_storyboard_contract_audit.json", {"passed"}),
)


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


def is_meaningful_text(value: Any, *, min_len: int = 12) -> bool:
    text = clean(value, 1000)
    if len(text) < min_len:
        return False
    normalized = re.sub(r"[\s.。,_-]+", " ", text).strip().lower()
    return normalized not in GENERIC_DECISION_TEXT


def parse_iso_datetime(value: Any) -> datetime | None:
    text = clean(value, 100)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def safe_id(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "watchdown")).strip("_").lower()
    return text[:90] or "watchdown"


def resolve_path(value: Any, *, base: Path) -> Path | None:
    if not clean(value, 1000):
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


def report_summary(data: Any) -> dict[str, Any]:
    return data.get("summary") if isinstance(data, dict) and isinstance(data.get("summary"), dict) else {}


def infer_output(package_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    report_candidates = [
        package_dir / "render_delivery_verification.json",
        package_dir / "FINAL_DELIVERY_REPORT.json",
        package_dir / "render_plan.json",
    ]
    candidate_keys = (
        "output",
        "finalOutput",
        "outputPath",
        "renderedOutput",
        "targetOutput",
        "finalOutputPath",
    )
    for report_path in report_candidates:
        data = load_json(report_path) or {}
        if not isinstance(data, dict):
            continue
        for key in candidate_keys:
            candidate = data.get(key)
            if candidate:
                path = resolve_path(candidate, base=package_dir)
                if path and path.exists():
                    return path
        summary = report_summary(data)
        for key in candidate_keys:
            candidate = summary.get(key)
            if candidate:
                path = resolve_path(candidate, base=package_dir)
                if path and path.exists():
                    return path
    renders = sorted((package_dir / "renders").glob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    return renders[0].resolve() if renders else None


def output_evidence(package_dir: Path, output_path: Path | None) -> dict[str, Any]:
    evidence = {
        "path": str(output_path) if output_path else None,
        "exists": bool(output_path and output_path.exists()),
        "sizeBytes": None,
        "mtime": None,
        "inPackage": False,
    }
    if output_path and output_path.exists():
        stat = output_path.stat()
        evidence.update(
            {
                "sizeBytes": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "inPackage": package_dir in output_path.parents or output_path == package_dir,
            }
        )
    return evidence


def existing_decisions(output_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_json(output_dir / "editorial_watchdown_repair_plan.json") or {}
    out: dict[str, dict[str, Any]] = {}
    for key in ("repairRows", "watchRows"):
        rows = data.get(key) if isinstance(data, dict) and isinstance(data.get(key), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            repair_id = clean(row.get("repairId"), 140)
            decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
            if repair_id:
                out[repair_id] = dict(decision)
    return out


def merge_decision(existing: dict[str, Any] | None) -> dict[str, Any]:
    decision = dict(DECISION_TEMPLATE)
    if isinstance(existing, dict):
        decision.update(existing)
    return decision


def decision_quality_issues(decision: dict[str, Any], *, package_dir: Path, output_path: Path | None, output: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if decision.get("watchAccepted") is not True:
        issues.append("watchAccepted is not true")
    missing = [key for key in REQUIRED_DECISION_TEXT_FIELDS if not clean(decision.get(key), 300)]
    if missing:
        issues.append("missing required decision fields: " + ", ".join(missing))
    if not output_path or not output_path.exists():
        issues.append("current final output is missing")
    watched_range = clean(decision.get("watchedRange"), 300)
    if watched_range and not TIME_RANGE_RE.search(watched_range):
        issues.append("watchedRange must name the full film/section or include timecode ranges")
    reviewed = resolve_path(decision.get("reviewedOutputPath"), base=package_dir)
    if output_path and output_path.exists() and (not reviewed or reviewed != output_path.resolve()):
        issues.append("reviewedOutputPath does not match the current final MP4")
    reviewed_at = parse_iso_datetime(decision.get("reviewedAt"))
    if not reviewed_at:
        issues.append("reviewedAt must be an ISO timestamp from the current watchdown")
    output_mtime = parse_iso_datetime(output.get("mtime"))
    if reviewed_at and output_mtime and reviewed_at < output_mtime:
        issues.append("reviewedAt is older than the current final MP4 mtime")
    if not is_meaningful_text(decision.get("reviewedBy"), min_len=2):
        issues.append("reviewedBy is missing or too generic")
    evidence_fields = (
        "viewerFacingIssueSummary",
        "openingTitleEvidence",
        "chapterContinuityEvidence",
        "transitionEvidence",
        "bgmCaptionEvidence",
        "endingAftertasteEvidence",
        "referenceFitEvidence",
        "repairActionTaken",
        "postRepairAuditEvidence",
    )
    generic_fields = [key for key in evidence_fields if clean(decision.get(key), 1000) and not is_meaningful_text(decision.get(key), min_len=12)]
    if generic_fields:
        issues.append("decision evidence is too generic: " + ", ".join(generic_fields))
    return issues


def decision_is_closed(decision: dict[str, Any], *, package_dir: Path, output_path: Path | None, output: dict[str, Any]) -> bool:
    return not decision_quality_issues(decision, package_dir=package_dir, output_path=output_path, output=output)


def first_list(data: Any, keys: tuple[str, ...]) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    for key in keys:
        value = summary.get(key)
        if isinstance(value, list):
            return value
    return []


def chapter_specs(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "chapter_arc_plan" / "chapter_arc_plan.json") or {}
    rows = first_list(data, ("chapterRows", "chapters", "rows", "chapterPlanRows", "arcRows"))
    specs: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:30], start=1):
        if not isinstance(row, dict):
            continue
        title = clean(
            row.get("chapterTitle")
            or row.get("title")
            or row.get("chapter")
            or row.get("name")
            or row.get("routeLabel")
            or f"chapter {index}",
            120,
        )
        specs.append(
            {
                "repairId": f"chapter_watchdown_{index:02d}_{safe_id(title)}",
                "phase": "editorial_watchdown",
                "issueType": "chapter_flow_not_signed_off",
                "watchFocus": f"Watch chapter {index}: {title}. Confirm context, movement, texture, payoff, and aftertaste/handoff survive in the final candidate.",
                "sourceReports": ["chapter_arc_plan", "chapter_story_spine_contract_audit", "shot_flow_continuity_contract_audit", "pacing_watchability_contract_audit"],
                "affectedEvidence": {"chapterIndex": index, "chapterTitle": title, "chapterRow": row},
            }
        )
    if not specs:
        specs.append(
            {
                "repairId": "chapter_watchdown_all",
                "phase": "editorial_watchdown",
                "issueType": "chapter_flow_not_signed_off",
                "watchFocus": "Watch every chapter as a viewer and verify it is more than a landmark/filename-order montage.",
                "sourceReports": ["chapter_arc_plan", "chapter_story_spine_contract_audit", "pacing_watchability_contract_audit"],
                "affectedEvidence": {"chapterPlanAvailable": bool(data)},
            }
        )
    return specs


def row_specs(package_dir: Path) -> list[dict[str, Any]]:
    specs = [
        {
            "repairId": "final_output_watchdown_asset",
            "phase": "editorial_watchdown",
            "issueType": "final_output_not_available_for_watchdown",
            "watchFocus": "Confirm the actual final MP4 exists, is current, and is the file being reviewed.",
            "sourceReports": ["render_delivery_verification", "FINAL_DELIVERY_REPORT"],
            "affectedEvidence": {},
        },
        {
            "repairId": "opening_watchdown",
            "phase": "editorial_watchdown",
            "issueType": "opening_not_viewer_signed_off",
            "watchFocus": "Watch the first three minutes for destination promise, clean hero title, BGM-only scenic opening, and no subtitle/title collision.",
            "sourceReports": ["opening_story_plan", "cover_title_contract_audit", "title_visual_proof_contract_audit", "visual_audio_style_audit"],
            "affectedEvidence": {},
        },
    ]
    specs.extend(chapter_specs(package_dir))
    specs.extend(
        [
            {
                "repairId": "transition_flow_watchdown",
                "phase": "editorial_watchdown",
                "issueType": "transition_flow_not_viewer_signed_off",
                "watchFocus": "Watch all day/place/chapter joins for motivated bridge footage, stable landings, rare motion accents, and no rough hard-cut/effect-spam cadence.",
                "sourceReports": ["transition_flow_repair_plan", "transition_sequence_satisfaction_contract_audit", "transition_storyboard_contract_audit", "transition_audition_quality_contract_audit", "final_cut_smoothness_contract_audit"],
                "affectedEvidence": {},
            },
            {
                "repairId": "bgm_caption_watchdown",
                "phase": "editorial_watchdown",
                "issueType": "bgm_caption_not_viewer_signed_off",
                "watchFocus": "Listen through the candidate for real musical BGM, no scenic voice leakage, and audience-facing subtitles that do not describe the workflow.",
                "sourceReports": ["bgm_audio_contract_audit", "bgm_musicality_contract_audit", "audience_caption_contract_audit", "audio_scene_policy_plan"],
                "affectedEvidence": {},
            },
            {
                "repairId": "ending_watchdown",
                "phase": "editorial_watchdown",
                "issueType": "ending_not_viewer_signed_off",
                "watchFocus": "Watch the last section for scenic aftertaste, route closure, BGM landing, and no abrupt leftover-clip ending.",
                "sourceReports": ["director_intent_contract_audit", "visual_establishing_plan", "story_style_contract_audit"],
                "affectedEvidence": {},
            },
            {
                "repairId": "reference_fit_watchdown",
                "phase": "editorial_watchdown",
                "issueType": "reference_fit_not_viewer_signed_off",
                "watchFocus": "Compare the whole candidate against the non-copying Parallel World/Malta lessons: cover/title, opening, pacing, transition language, route texture, captions, BGM, and ending.",
                "sourceReports": ["reference_review_repair_plan", "reference_profile_application_contract_audit", "reference_transition_profile_contract_audit", "director_polish_contract_audit"],
                "affectedEvidence": {},
            },
        ]
    )
    return specs


def supporting_report_evidence(package_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    evidence: list[dict[str, Any]] = []
    issues: list[str] = []
    for report_id, rel_path, accepted in SUPPORTING_REPORTS:
        path = package_dir / rel_path
        data = load_json(path) or {}
        status = data.get("status") if isinstance(data, dict) else None
        row = {
            "reportId": report_id,
            "path": str(path),
            "exists": path.exists(),
            "status": status,
            "acceptedStatuses": sorted(accepted),
            "accepted": bool(path.exists() and status in accepted),
            "summary": report_summary(data),
        }
        evidence.append(row)
        if not row["accepted"]:
            issues.append(f"{report_id} is {status or 'missing'}")
    return evidence, issues


def build_watch_row(
    *,
    spec: dict[str, Any],
    previous: dict[str, dict[str, Any]],
    package_dir: Path,
    output_path: Path | None,
    output: dict[str, Any],
    support_issues: list[str],
) -> dict[str, Any]:
    repair_id = str(spec["repairId"])
    decision = merge_decision(previous.get(repair_id))
    decision_issues = decision_quality_issues(decision, package_dir=package_dir, output_path=output_path, output=output)
    closed = not decision_issues
    issues: list[str] = []
    if not output.get("exists"):
        issues.append("final MP4 is missing or could not be inferred for review")
    if support_issues:
        issues.append("supporting final audits are not all accepted: " + "; ".join(support_issues[:12]))
    issues.extend(f"decision issue: {issue}" for issue in decision_issues)
    return {
        "repairId": repair_id,
        "priority": "P0",
        "phase": spec.get("phase", "editorial_watchdown"),
        "issueType": spec.get("issueType"),
        "sourceReport": "editorial_watchdown_repair_plan",
        "sourceReports": spec.get("sourceReports") or [],
        "issue": "; ".join(dict.fromkeys(issues)),
        "ownerScript": "Codex visual/audio review + prepare_editorial_watchdown_repair_plan.py",
        "requiredArtifact": "editorial_watchdown_repair_plan/editorial_watchdown_repair_plan.json",
        "command": "python3 <skill-dir>/scripts/prepare_editorial_watchdown_repair_plan.py --package-dir <package> --final-output <final-mp4> --json",
        "watchFocus": spec.get("watchFocus"),
        "requiredAction": "Watch the actual final candidate from beginning to end as a viewer. Repair weak sections with the relevant owner scripts, then fill every decision field for this row and rerun the watchdown plan.",
        "acceptanceEvidence": "watchAccepted=true, reviewedOutputPath equals the current final MP4, watchedRange covers the whole relevant section, viewer-facing issues are closed or explicitly accepted, and post-repair audit evidence names current reports.",
        "forbiddenWorkaround": "Do not call the package ready from technical QA alone, screenshots, contact sheets, sampled frames, stale renders, or internal workflow notes.",
        "affectedEvidence": {**(spec.get("affectedEvidence") or {}), "finalOutput": output},
        "decision": decision,
        "decisionIssues": decision_issues,
        "closed": closed and not issues,
    }


def build_plan(package_dir: Path, output_dir: Path, final_output: str | None) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_path = infer_output(package_dir, final_output)
    output = output_evidence(package_dir, output_path)
    previous = existing_decisions(output_dir)
    support_evidence, support_issues = supporting_report_evidence(package_dir)
    watch_rows = [
        build_watch_row(
            spec=spec,
            previous=previous,
            package_dir=package_dir,
            output_path=output_path,
            output=output,
            support_issues=support_issues,
        )
        for spec in row_specs(package_dir)
    ]
    repair_rows = [row for row in watch_rows if row.get("issue") or not row.get("closed")]
    closed_rows = [row for row in watch_rows if row.get("closed")]
    status = CLOSED_STATUS if not repair_rows else OPEN_STATUS
    summary = {
        "watchRowCount": len(watch_rows),
        "closedWatchRowCount": len(closed_rows),
        "repairRowCount": len(repair_rows),
        "chapterWatchRowCount": len([row for row in watch_rows if str(row.get("repairId", "")).startswith("chapter_watchdown")]),
        "supportingReportCount": len(support_evidence),
        "supportingReportIssueCount": len(support_issues),
        "decisionIssueCount": sum(len(row.get("decisionIssues") or []) for row in watch_rows),
        "rowsWithDecisionIssues": len([row for row in watch_rows if row.get("decisionIssues")]),
        "rowsWithTimecodedOrFullRange": len([row for row in watch_rows if TIME_RANGE_RE.search(clean((row.get("decision") or {}).get("watchedRange"), 300))]),
        "rowsReviewedAfterFinalOutputMtime": len(
            [
                row
                for row in watch_rows
                if parse_iso_datetime((row.get("decision") or {}).get("reviewedAt"))
                and parse_iso_datetime(output.get("mtime"))
                and parse_iso_datetime((row.get("decision") or {}).get("reviewedAt")) >= parse_iso_datetime(output.get("mtime"))
            ]
        ),
        "finalOutput": output.get("path"),
        "finalOutputExists": output.get("exists"),
        "ownerScripts": sorted({str(row.get("ownerScript")) for row in repair_rows if row.get("ownerScript")}),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "summary": summary,
        "inputs": {
            "finalOutput": output,
            "supportingReports": support_evidence,
            "supportingReportIssues": support_issues,
        },
        "watchRows": watch_rows,
        "repairRows": repair_rows,
        "nextActions": [
            "Open the current final MP4 and watch it as a viewer from start to finish.",
            "For each open watchdown row, repair the cut with the named source plan/audit owner scripts before editing decision fields.",
            "Fill the decision fields only after watching the current final output path, then rerun this script until it returns ready_no_editorial_watchdown_repairs_needed.",
            "Only then run unattended repair queue, final QA, V14 baseline, Skill maturity, and handoff.",
        ],
        "safety": safety(),
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Editorial Watchdown Repair Plan",
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
        "## Open Repair Rows",
    ]
    if not plan.get("repairRows"):
        lines.append("- None.")
    for row in plan.get("repairRows", [])[:250]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Issue: {row.get('issue')}",
                f"- Watch focus: {row.get('watchFocus')}",
                f"- Owner: `{row.get('ownerScript')}`",
                f"- Required action: {row.get('requiredAction')}",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
                f"- Decision issues: `{row.get('decisionIssues')}`",
                "- Decision fields to complete:",
            ]
        )
        for key, value in row.get("decision", {}).items():
            lines.append(f"  - `{key}`: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(
        [
            "",
            "## Contract",
            "- Technical QA does not replace watching the actual final candidate as a film.",
            "- The reviewed output path must match the current final MP4; stale V1/V2/V14 renders do not close this gate.",
            "- `reviewedAt` must be an ISO timestamp after the current final MP4 modification time, and `watchedRange` must name full-film/section coverage or timecode ranges.",
            "- Decision evidence must be concrete viewer-facing notes; generic `ok`, `done`, `pass`, or empty repair/audit text does not close a row.",
            "- Repair weak viewing sections through their owner scripts, then rerun final QA instead of leaving viewer-facing notes in captions or handoff text.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare repair rows for final editorial watchdown.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/editorial_watchdown_repair_plan.")
    parser.add_argument("--final-output", "--output", dest="final_output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "editorial_watchdown_repair_plan"
    plan = build_plan(package_dir, output_dir, args.final_output)
    write_json(output_dir / "editorial_watchdown_repair_plan.json", plan)
    write_markdown(output_dir / "editorial_watchdown_repair_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
