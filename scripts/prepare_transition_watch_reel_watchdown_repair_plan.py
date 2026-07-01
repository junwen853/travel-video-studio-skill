#!/usr/bin/env python3
"""Prepare repair rows until the transition watch reel has been reviewed as a viewer sequence."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CLOSED_STATUS = "ready_no_transition_watch_reel_watchdown_repairs_needed"
OPEN_STATUS = "ready_with_transition_watch_reel_watchdown_repair_plan"
NO_IMPORTANT_REEL_STATUSES = {"ready_no_important_transitions", "passed_no_important_transitions"}
READY_REEL_STATUSES = {"ready_with_transition_watch_reel", "ready_no_important_transitions"}
READY_REVIEW_STATUSES = {"passed", "passed_no_important_transitions"}
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
    "complete",
    "completed",
    "无",
    "无问题",
    "没问题",
    "通过",
    "完成",
    "已完成",
    "已看",
    "看完了",
}

DECISION_TEMPLATE = {
    "watchAccepted": False,
    "reviewedReelPath": "",
    "watchedRange": "",
    "viewerIssueSummary": "",
    "transitionFlowEvidence": "",
    "motivationEvidence": "",
    "effectRestraintEvidence": "",
    "landingContinuityEvidence": "",
    "bgmCaptionSafetyEvidence": "",
    "repairActionTaken": "",
    "postRepairAuditEvidence": "",
    "reviewedBy": "",
    "reviewedAt": "",
    "editorNotes": "",
}

CONTENT_DECISION_FIELDS = (
    "watchedRange",
    "viewerIssueSummary",
    "transitionFlowEvidence",
    "motivationEvidence",
    "effectRestraintEvidence",
    "landingContinuityEvidence",
    "bgmCaptionSafetyEvidence",
    "repairActionTaken",
    "postRepairAuditEvidence",
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


def is_meaningful_text(value: Any, *, min_len: int = 16) -> bool:
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


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_id(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "transition")).strip("_").lower()
    return text[:90] or "transition"


def safety() -> dict[str, bool]:
    return {
        "writesResolve": False,
        "queuesRender": False,
        "downloadsExternalAssets": False,
        "modifiesSourceFootage": False,
        "modifiesSourceDrive": False,
    }


def resolve_package_path(package_dir: Path, raw: Any) -> Path | None:
    value = clean(raw, 4000)
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = package_dir / path
    return path.resolve()


def mtime_iso(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def existing_decisions(output_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_json(output_dir / "transition_watch_reel_watchdown_repair_plan.json") or {}
    out: dict[str, dict[str, Any]] = {}
    if isinstance(data, dict):
        archive = data.get("decisionArchive")
        if isinstance(archive, dict):
            for repair_id, decision in archive.items():
                if isinstance(decision, dict) and clean(repair_id, 120):
                    out[clean(repair_id, 120)] = dict(decision)
        rows = data.get("repairRows") if isinstance(data.get("repairRows"), list) else []
        for row in rows:
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


def matched_reel_path(decision: dict[str, Any], reel_output: Path | None, package_dir: Path) -> bool:
    if not reel_output:
        return False
    reviewed = resolve_package_path(package_dir, decision.get("reviewedReelPath"))
    return bool(reviewed and reviewed == reel_output.resolve())


def decision_quality_issues(decision: dict[str, Any], *, reel_output: Path | None, reel_mtime: str | None, package_dir: Path) -> list[str]:
    issues: list[str] = []
    if decision.get("watchAccepted") is not True:
        issues.append("watchAccepted is not true")
    if not matched_reel_path(decision, reel_output, package_dir):
        issues.append("reviewedReelPath does not match the current transition watch reel")
    for key in CONTENT_DECISION_FIELDS:
        if not is_meaningful_text(decision.get(key)):
            issues.append(f"{key} is missing, too short, or generic")
    if not TIME_RANGE_RE.search(clean(decision.get("watchedRange"), 1000)):
        issues.append("watchedRange lacks timecoded or full-reel range evidence")
    reviewed_at = parse_iso_datetime(decision.get("reviewedAt"))
    if not is_meaningful_text(decision.get("reviewedBy"), min_len=2):
        issues.append("reviewedBy is missing")
    if not reviewed_at:
        issues.append("reviewedAt must be an ISO timestamp from the actual reel review")
    reel_mtime_dt = parse_iso_datetime(reel_mtime)
    if reviewed_at and reel_mtime_dt and reviewed_at < reel_mtime_dt:
        issues.append("reviewedAt is older than the current transition watch reel mtime")
    restraint = clean(decision.get("effectRestraintEvidence"), 1000).lower()
    if not any(term in restraint for term in ("restrain", "not random", "no random", "no template", "克制", "不随机", "非随机", "不套模板", "不是模板")):
        issues.append("effectRestraintEvidence must explicitly prove restrained, non-random, non-template effects")
    return issues


def decision_is_closed(decision: dict[str, Any], *, reel_output: Path | None, reel_mtime: str | None, package_dir: Path) -> bool:
    return not decision_quality_issues(decision, reel_output=reel_output, reel_mtime=reel_mtime, package_dir=package_dir)


def support_issues(watch: dict[str, Any], review: dict[str, Any], reel_output: Path | None) -> list[str]:
    issues: list[str] = []
    watch_summary = watch.get("summary") if isinstance(watch.get("summary"), dict) else {}
    review_summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
    if watch.get("status") not in READY_REEL_STATUSES:
        issues.append(f"transition_watch_reel status is {watch.get('status') or 'missing'}")
    if review.get("status") not in READY_REVIEW_STATUSES:
        issues.append(f"transition_watch_reel_review_contract_audit status is {review.get('status') or 'missing'}")
    if as_int(watch_summary.get("blockedReelRowCount")) > 0:
        issues.append("transition watch reel still has blocked reel rows")
    if as_int(review_summary.get("blockedReviewRowCount")) > 0 or as_int(review_summary.get("blockedCheckCount")) > 0:
        issues.append("transition watch reel automated review still has blocked rows or checks")
    if watch.get("status") not in NO_IMPORTANT_REEL_STATUSES and review.get("status") not in NO_IMPORTANT_REEL_STATUSES:
        if not reel_output:
            issues.append("transition watch reel output path is missing")
        elif not reel_output.exists():
            issues.append(f"transition watch reel mp4 is missing: {reel_output}")
        if review_summary.get("reelProbeReady") is not True:
            issues.append("transition watch reel review did not prove the reel is probeable")
        if review_summary.get("reelHasAudio") not in {False, None}:
            issues.append("transition watch reel review found audio in the muted reel")
    return issues


def repair_id_for(row: dict[str, Any]) -> str:
    return f"transition_reel_watchdown_{safe_id(row.get('rowIndex'))}"


def normalize_review_rows(review: dict[str, Any], watch: dict[str, Any]) -> list[dict[str, Any]]:
    rows = review.get("reviewRows") if isinstance(review.get("reviewRows"), list) else []
    normalized = [row for row in rows if isinstance(row, dict)]
    if normalized:
        return normalized
    watch_rows = watch.get("reelRows") if isinstance(watch.get("reelRows"), list) else []
    out: list[dict[str, Any]] = []
    for row in watch_rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "rowIndex": row.get("rowIndex"),
                "status": "passed" if row.get("status") == "ready_for_reel" else "blocked",
                "family": row.get("boundaryCategory"),
                "highIntensity": False,
                "startSeconds": row.get("reelStartSeconds"),
                "endSeconds": row.get("reelEndSeconds"),
                "durationSeconds": row.get("durationSeconds"),
                "hasBridgeSample": as_int(row.get("bridgeSampleCount")) > 0,
                "motionReady": (row.get("motionExecution") or {}).get("ready") if isinstance(row.get("motionExecution"), dict) else None,
                "sensoryReady": (row.get("sensoryContinuity") or {}).get("ready") if isinstance(row.get("sensoryContinuity"), dict) else None,
                "storyboardPurpose": row.get("storyboardPurpose"),
                "issues": row.get("issues") or [],
                "warnings": row.get("warnings") or [],
            }
        )
    return out


def row_evidence_issues(row: dict[str, Any]) -> list[str]:
    issues = list(row.get("issues") or [])
    if row.get("status") == "blocked":
        issues.append("automated watch reel review row is blocked")
    if as_float(row.get("endSeconds"), -1.0) <= as_float(row.get("startSeconds"), -1.0):
        issues.append("review row lacks a valid reel time range")
    if not is_meaningful_text(row.get("storyboardPurpose"), min_len=8):
        issues.append("review row lacks storyboard purpose")
    if not (row.get("hasBridgeSample") or row.get("motionReady") or row.get("sensoryReady")):
        issues.append("review row lacks bridge, motion, or sensory transition reason")
    return list(dict.fromkeys(issues))


def build_support_row(profile_issues: list[str], previous: dict[str, dict[str, Any]], package_dir: Path) -> dict[str, Any] | None:
    if not profile_issues:
        return None
    repair_id = "transition_reel_watchdown_supporting_reports"
    return {
        "repairId": repair_id,
        "priority": "P0",
        "phase": "transition_flow",
        "issueType": "refresh_transition_watch_reel_and_review",
        "issue": "; ".join(profile_issues),
        "ownerScript": "prepare_transition_watch_reel.py + audit_transition_watch_reel_review_contract.py",
        "requiredArtifact": "transition_watch_reel/transition_watch_reel.json + transition_watch_reel_review_contract_audit.json",
        "command": "python3 <skill-dir>/scripts/prepare_transition_watch_reel.py --package-dir <package> --build-reel --require-muted --json && python3 <skill-dir>/scripts/audit_transition_watch_reel_review_contract.py --package-dir <package> --json",
        "requiredAction": "Rebuild the ordered muted transition watch reel and pass the automated sequence review before closing human/Codex watchdown rows.",
        "acceptanceEvidence": "transition_watch_reel is ready, transition_watch_reel_review_contract_audit passes, the reel MP4 is current, muted, probeable, and ordered.",
        "forbiddenWorkaround": "Do not close transition flow from scattered JSON, screenshots, or individual clips when the ordered reel is stale, missing, noisy, or blocked.",
        "affectedEvidence": {"packageDir": str(package_dir)},
        "decision": merge_decision(previous.get(repair_id)),
    }


def build_watch_row(
    *,
    row: dict[str, Any],
    previous: dict[str, dict[str, Any]],
    reel_output: Path | None,
    reel_mtime: str | None,
    package_dir: Path,
) -> dict[str, Any]:
    repair_id = repair_id_for(row)
    decision = merge_decision(previous.get(repair_id))
    evidence_issues = row_evidence_issues(row)
    decision_issues = decision_quality_issues(decision, reel_output=reel_output, reel_mtime=reel_mtime, package_dir=package_dir)
    closed = not evidence_issues and not decision_issues
    start = row.get("startSeconds")
    end = row.get("endSeconds")
    return {
        "repairId": repair_id,
        "priority": "P0" if row.get("highIntensity") or evidence_issues else "P1",
        "phase": "transition_flow",
        "issueType": "complete_transition_watch_reel_watchdown",
        "rowIndex": row.get("rowIndex"),
        "reelRange": f"{start}-{end}",
        "issue": "; ".join(dict.fromkeys(evidence_issues + decision_issues)),
        "closed": closed,
        "ownerScript": "Codex visual watchdown + transition repair scripts",
        "requiredArtifact": "transition_watch_reel_watchdown_repair_plan/transition_watch_reel_watchdown_repair_plan.json",
        "command": "Watch transition_watch_reel/transition_watch_reel.mp4 at this row range, repair rough flow with transition/choreography/source scripts, then rerun this plan.",
        "requiredAction": "Review this transition in the ordered reel, not as an isolated clip. Confirm viewer flow, motivation, effect restraint, landing continuity, BGM-only/caption safety, and repair evidence.",
        "acceptanceEvidence": "watchAccepted=true, reviewedReelPath matches the current reel, watchedRange is timecoded or full-reel, reviewedAt is after the reel mtime, and every evidence field is concrete and viewer-facing.",
        "forbiddenWorkaround": "Do not approve a transition because the clip exists, the JSON says passed, or the effect looks technically possible; watch the ordered reel and repair abrupt/random/template-feeling motion.",
        "affectedEvidence": {
            "reelOutput": str(reel_output) if reel_output else None,
            "reelMtime": reel_mtime,
            "row": row,
        },
        "evidenceIssues": evidence_issues,
        "decisionIssues": decision_issues,
        "decision": decision,
    }


def build_plan(package_dir: Path, output_dir: Path, explicit_reel_output: str | None) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    previous = existing_decisions(output_dir)
    watch_path = package_dir / "transition_watch_reel" / "transition_watch_reel.json"
    review_path = package_dir / "transition_watch_reel_review_contract_audit.json"
    watch = load_json(watch_path) or {}
    review = load_json(review_path) or {}
    watch_summary = watch.get("summary") if isinstance(watch.get("summary"), dict) else {}
    review_summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
    review_inputs = review.get("inputs") if isinstance(review.get("inputs"), dict) else {}
    reel_output = resolve_package_path(package_dir, explicit_reel_output or watch_summary.get("reelOutput") or review_inputs.get("watchReelOutput"))
    reel_mtime = mtime_iso(reel_output)
    rows = normalize_review_rows(review, watch)
    no_important = watch.get("status") in NO_IMPORTANT_REEL_STATUSES or review.get("status") in NO_IMPORTANT_REEL_STATUSES
    profile_issues = support_issues(watch, review, reel_output)

    watch_rows: list[dict[str, Any]] = []
    if not no_important:
        watch_rows = [
            build_watch_row(row=row, previous=previous, reel_output=reel_output, reel_mtime=reel_mtime, package_dir=package_dir)
            for row in rows
        ]
    repair_rows = [row for row in watch_rows if not row.get("closed")]
    support_row = build_support_row(profile_issues, previous, package_dir)
    if support_row:
        repair_rows.insert(0, support_row)
    closed_rows = [row for row in watch_rows if row.get("closed")]
    decisions = {row["repairId"]: row["decision"] for row in watch_rows}
    status = CLOSED_STATUS if not repair_rows else OPEN_STATUS
    summary = {
        "watchRowCount": len(watch_rows),
        "closedWatchRowCount": len(closed_rows),
        "repairRowCount": len(repair_rows),
        "supportingIssueCount": len(profile_issues),
        "reelRowCount": as_int(review_summary.get("reelRowCount") or watch_summary.get("reelRowCount")),
        "importantReelRowCount": as_int(review_summary.get("importantReelRowCount") or watch_summary.get("importantReelRowCount")),
        "transitionWatchReelStatus": watch.get("status"),
        "transitionWatchReelReviewStatus": review.get("status"),
        "decisionArchiveCount": len(decisions),
        "decisionIssueCount": sum(len(row.get("decisionIssues") or []) for row in watch_rows),
        "rowsWithDecisionIssues": len([row for row in watch_rows if row.get("decisionIssues")]),
        "rowsWithTimecodedOrFullRange": len([row for row in watch_rows if TIME_RANGE_RE.search(clean((row.get("decision") or {}).get("watchedRange"), 1000))]),
        "rowsWithMatchedCurrentReelPath": len([row for row in watch_rows if matched_reel_path(row.get("decision") or {}, reel_output, package_dir)]),
        "rowsReviewedAfterReelMtime": len(
            [
                row
                for row in watch_rows
                if parse_iso_datetime((row.get("decision") or {}).get("reviewedAt"))
                and parse_iso_datetime(reel_mtime)
                and parse_iso_datetime((row.get("decision") or {}).get("reviewedAt")) >= parse_iso_datetime(reel_mtime)
            ]
        ),
        "rowEvidenceIssueCount": sum(len(row.get("evidenceIssues") or []) for row in watch_rows),
        "highIntensityRunMax": review_summary.get("highIntensityRunMax"),
        "familyRunMax": review_summary.get("familyRunMax"),
        "reelOutput": str(reel_output) if reel_output else None,
        "reelOutputExists": bool(reel_output and reel_output.exists()),
        "reelMtime": reel_mtime,
        "ownerScripts": sorted({str(row.get("ownerScript")) for row in repair_rows if row.get("ownerScript")}),
    }
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "summary": summary,
        "inputs": {
            "transitionWatchReel": {"path": str(watch_path), "exists": watch_path.exists(), "status": watch.get("status")},
            "transitionWatchReelReview": {"path": str(review_path), "exists": review_path.exists(), "status": review.get("status")},
            "reelOutput": {"path": str(reel_output) if reel_output else None, "exists": bool(reel_output and reel_output.exists()), "mtime": reel_mtime},
            "supportingIssues": profile_issues,
        },
        "decisionArchive": decisions,
        "watchRows": watch_rows,
        "repairRows": repair_rows,
        "nextActions": [
            "Rebuild the ordered muted transition watch reel and automated review when supporting reports are stale or blocked.",
            "Watch the current transition_watch_reel.mp4 in order, not as scattered per-row clips.",
            "For each row, fill viewer-facing watchdown decisions with timecoded evidence for flow, motivation, effect restraint, landing continuity, and BGM/caption safety.",
            "Repair abrupt, random, template-like, over-rotated, repeated, or poorly landed transitions before Resolve apply, final QA, V14, or Skill maturity claims.",
        ],
        "safety": safety(),
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Transition Watch Reel Watchdown Repair Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan['packageDir']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan.get("summary") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Repair Rows",
    ]
    if not plan.get("repairRows"):
        lines.append("- None.")
    for row in (plan.get("repairRows") or [])[:200]:
        lines.extend(
            [
                "",
                f"### {row.get('repairId')}",
                f"- Priority: `{row.get('priority')}`",
                f"- Issue: {row.get('issue')}",
                f"- Required action: {row.get('requiredAction')}",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Forbidden workaround: {row.get('forbiddenWorkaround')}",
                "- Decision fields to complete:",
            ]
        )
        for key, value in (row.get("decision") or {}).items():
            lines.append(f"  - `{key}`: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(
        [
            "",
            "## Contract",
            "- Transition reel watchdown is not complete until the current ordered muted reel has concrete viewer-facing decisions.",
            "- Passing per-row JSON is not enough; the transition sequence must be watched in order for flow, motivation, restraint, landing, BGM-only, and caption safety.",
            "- Random spins, template-feeling motion, repeated high-intensity effects, abrupt jumps, and unstable landings must reopen repair rows.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare repair rows for transition watch reel visual watchdown.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/transition_watch_reel_watchdown_repair_plan.")
    parser.add_argument("--reel-output", help="Override transition watch reel MP4 path.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "transition_watch_reel_watchdown_repair_plan"
    plan = build_plan(package_dir, output_dir, args.reel_output)
    write_json(output_dir / "transition_watch_reel_watchdown_repair_plan.json", plan)
    write_markdown(output_dir / "transition_watch_reel_watchdown_repair_plan.md", plan)
    payload = plan if args.json else {"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
