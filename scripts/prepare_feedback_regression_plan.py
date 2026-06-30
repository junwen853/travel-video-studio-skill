#!/usr/bin/env python3
"""Prepare reusable feedback-regression probes before final render QA exists."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PROBES = [
    {
        "id": "opening_title",
        "label": "opening_title",
        "second": 0.0,
        "timestamp": "0",
        "complaint": "Opening hero title must be one clean city title, with no duplicate, ghosted, route/date, project-id, or subtitle text in the title zone.",
        "riskType": "title_cleanliness",
        "requiredPreRenderEvidence": [
            "title_typography_plan has exactly one clean opening row",
            "title_bridge_contract has no stacked title or subtitle overlay layers",
            "subtitle overlay policy avoids title zones",
        ],
        "requiredPostRenderEvidence": [
            "audit_feedback_regressions clean-title check passes",
            "audit_visual_audio_style has no forbidden title OCR hits",
        ],
        "includeInAudioPolicy": True,
        "includeInFinalFeedbackAudit": True,
    },
    {
        "id": "reported_vertical_clip_7_04",
        "label": "reported_vertical_clip",
        "second": 424.0,
        "timestamp": "7:04",
        "complaint": "The reported 7:04 moment must not show raw portrait, pillarboxed, square, rotated, or unknown-orientation footage in the 16:9 master.",
        "riskType": "visual_orientation",
        "requiredPreRenderEvidence": [
            "client_delivery_rules actual Resolve blueprint source-orientation gate passes",
            "resolve_blueprint_preflight has no missing, invalid, out-of-bounds, overlap, or V1-gap blockers",
        ],
        "requiredPostRenderEvidence": [
            "audit_feedback_regressions reports no portrait/pillarbox regression at this timestamp",
            "sampled contact sheet frame is visually landscape-safe",
        ],
        "includeInAudioPolicy": False,
        "includeInFinalFeedbackAudit": True,
    },
    {
        "id": "reported_voice_at_7_04",
        "label": "reported_voice_at_7_04",
        "second": 424.0,
        "timestamp": "7:04",
        "complaint": "The reported 7:04 scenic/title-style moment must be BGM-led and must not leak source-camera/user voice or generated voiceover.",
        "riskType": "bgm_voice_leak",
        "requiredPreRenderEvidence": [
            "audio_scene_policy_plan has a feedback_audio_probe row covering 7:04",
            "Resolve blueprint audio plan is bgm_only_no_camera_voice",
            "A1/A2 source and voiceover audio are disabled unless explicitly approved",
        ],
        "requiredPostRenderEvidence": [
            "audit_feedback_regressions BGM-only mix check passes",
            "audit_bgm_audio_contract proves A3 BGM, no A1/A2 voice/source items, and audible rendered BGM",
        ],
        "includeInAudioPolicy": True,
        "includeInFinalFeedbackAudit": True,
    },
    {
        "id": "opening_bgm_no_voice",
        "label": "opening_bgm_no_voice",
        "second": 0.0,
        "timestamp": "0",
        "complaint": "Opening scenic/cover footage must have BGM ambience, not user/source-camera voice or generated narration.",
        "riskType": "opening_bgm_voice_leak",
        "requiredPreRenderEvidence": [
            "audio_scene_policy_plan opening rows are A3 BGM-led",
            "voiceover remains text-only when the user rejects narration audio",
        ],
        "requiredPostRenderEvidence": [
            "audit_feedback_regressions BGM-only mix check passes at opening/title points",
        ],
        "includeInAudioPolicy": True,
        "includeInFinalFeedbackAudit": True,
    },
]


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_words(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def parse_timestamp(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    if ":" not in raw:
        try:
            return float(raw)
        except ValueError:
            return None
    parts = raw.split(":")
    try:
        nums = [float(part) for part in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def timestamp_label(seconds: float) -> str:
    if seconds <= 0:
        return "0"
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    if abs(remainder - round(remainder)) < 0.001:
        return f"{minutes}:{int(round(remainder)):02d}"
    return f"{minutes}:{remainder:05.2f}"


def parse_feedback_items(values: list[str] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in values or []:
        for part in str(raw).split(","):
            item = part.strip()
            if not item:
                continue
            if "=" in item:
                label, timestamp = item.split("=", 1)
            else:
                label, timestamp = f"manual_feedback_{len(rows) + 1}", item
            second = parse_timestamp(timestamp)
            if second is None:
                continue
            rows.append(
                {
                    "id": re.sub(r"[^A-Za-z0-9_.-]+", "_", label.strip()).strip("_") or f"manual_{len(rows) + 1}",
                    "label": clean_words(label),
                    "second": round(max(0.0, second), 3),
                    "timestamp": timestamp_label(max(0.0, second)),
                    "complaint": "User-provided feedback timestamp that must remain in future feedback regression audits.",
                    "riskType": "manual_user_feedback",
                    "requiredPreRenderEvidence": ["review and map this timestamp to title, orientation, audio, subtitle, or pacing gates"],
                    "requiredPostRenderEvidence": ["audit_feedback_regressions includes this timestamp and passes"],
                    "includeInAudioPolicy": True,
                    "includeInFinalFeedbackAudit": True,
                }
            )
    return rows


def dedupe_probes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        second = float(row.get("second") or 0.0)
        key = (str(row.get("id") or row.get("label") or ""), round(second * 1000))
        if key in seen:
            continue
        seen.add(key)
        item = dict(row)
        item["second"] = round(max(0.0, second), 3)
        item["timestamp"] = str(item.get("timestamp") or timestamp_label(item["second"]))
        out.append(item)
    return out


def plan_context(package_dir: Path) -> dict[str, Any]:
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    title_plan = load_json(package_dir / "title_typography_plan" / "title_typography_plan.json") or {}
    audio_plan = load_json(package_dir / "audio_scene_policy_plan" / "audio_scene_policy_plan.json") or {}
    feedback_audit = load_json(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json") or {}
    return {
        "packageDir": str(package_dir),
        "projectName": blueprint.get("projectName"),
        "timelineName": blueprint.get("timelineName"),
        "targetDurationSeconds": blueprint.get("targetDurationSeconds"),
        "titleTypographyStatus": title_plan.get("status"),
        "audioScenePolicyStatus": audio_plan.get("status"),
        "feedbackRegressionStatus": feedback_audit.get("status"),
    }


def build_commands(package_dir: Path, probes: list[dict[str, Any]]) -> dict[str, Any]:
    skill_dir = Path(__file__).resolve().parents[1]
    feedback_csv = ",".join(
        f"{probe['label']}={probe['timestamp']}" for probe in probes if probe.get("includeInFinalFeedbackAudit", True)
    )
    audio_csv = ",".join(f"{probe['label']}={probe['timestamp']}" for probe in probes if probe.get("includeInAudioPolicy"))
    return {
        "feedbackTimestampsCsv": feedback_csv,
        "audioPolicyFeedbackTimestampsCsv": audio_csv,
        "preRenderAudioPolicyCommand": [
            "python3",
            str(skill_dir / "scripts" / "prepare_audio_scene_policy_plan.py"),
            "--package-dir",
            str(package_dir),
            "--feedback-timestamps",
            audio_csv,
        ],
        "postRenderFeedbackAuditCommand": [
            "python3",
            str(skill_dir / "scripts" / "audit_feedback_regressions.py"),
            "--package-dir",
            str(package_dir),
            "--feedback-timestamps",
            feedback_csv,
            "--include-title-points",
        ],
        "finalQaSuiteCommand": [
            "python3",
            str(skill_dir / "scripts" / "run_final_qa_suite.py"),
            "--package-dir",
            str(package_dir),
            "--feedback-timestamps",
            feedback_csv,
        ],
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    probes = dedupe_probes([dict(row) for row in DEFAULT_PROBES] + parse_feedback_items(args.feedback_timestamps))
    commands = build_commands(package_dir, probes)
    required_risks = {"title_cleanliness", "visual_orientation", "bgm_voice_leak", "opening_bgm_voice_leak"}
    risk_types = {str(row.get("riskType") or "") for row in probes}
    opening_count = sum(1 for row in probes if float(row.get("second") or 0.0) <= 0.5)
    seven_minute_count = sum(1 for row in probes if abs(float(row.get("second") or 0.0) - 424.0) <= 1.0)
    audio_count = sum(1 for row in probes if row.get("includeInAudioPolicy"))
    status = "ready_with_feedback_regression_plan" if required_risks.issubset(risk_types) and opening_count >= 1 and seven_minute_count >= 2 and audio_count >= 2 else "blocked"
    blockers: list[str] = []
    if status == "blocked":
        if not required_risks.issubset(risk_types):
            blockers.append("Required default feedback risk types are missing.")
        if opening_count < 1:
            blockers.append("Opening feedback probe is missing.")
        if seven_minute_count < 2:
            blockers.append("7:04 orientation/audio feedback probes are missing.")
        if audio_count < 2:
            blockers.append("Audio-policy feedback probes are missing.")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "context": plan_context(package_dir),
        "probes": probes,
        "commands": commands,
        "summary": {
            "probeCount": len(probes),
            "openingProbeCount": opening_count,
            "sevenMinuteProbeCount": seven_minute_count,
            "audioPolicyProbeCount": audio_count,
            "finalFeedbackAuditProbeCount": sum(1 for row in probes if row.get("includeInFinalFeedbackAudit", True)),
            "riskTypes": sorted(risk_types),
            "feedbackTimestampsCsv": commands["feedbackTimestampsCsv"],
            "audioPolicyFeedbackTimestampsCsv": commands["audioPolicyFeedbackTimestampsCsv"],
        },
        "policy": {
            "purpose": "Turn concrete user complaints into reusable pre-render and post-render regression probes.",
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
            "requiredStages": [
                "prepare_audio_scene_policy_plan before Resolve apply",
                "audit_feedback_regressions after final render",
                "run_final_qa_suite with the same feedback timestamps before handoff",
            ],
        },
        "blockers": blockers,
        "nextActions": [
            {
                "priority": "P1",
                "action": "Refresh the pre-render audio scene policy using the planned feedback probes.",
                "command": " ".join(commands["preRenderAudioPolicyCommand"]),
            },
            {
                "priority": "P1",
                "action": "After render verification, run the feedback regression audit with the same planned probes.",
                "command": " ".join(commands["postRenderFeedbackAuditCommand"]),
            },
        ],
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Feedback Regression Plan",
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
        "## Probes",
    ]
    for probe in report["probes"]:
        lines.extend(
            [
                "",
                f"### {probe['id']}",
                f"- Time: `{probe['timestamp']}`",
                f"- Risk: `{probe['riskType']}`",
                f"- Complaint: {probe['complaint']}",
                f"- Include in audio policy: `{probe.get('includeInAudioPolicy')}`",
                f"- Include in final feedback audit: `{probe.get('includeInFinalFeedbackAudit')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "```bash",
            " ".join(report["commands"]["preRenderAudioPolicyCommand"]),
            " ".join(report["commands"]["postRenderFeedbackAuditCommand"]),
            " ".join(report["commands"]["finalQaSuiteCommand"]),
            "```",
        ]
    )
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare reusable feedback regression probes.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--feedback-timestamps", action="append")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args)
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = package_dir / "feedback_regression_plan"
    write_json(output_dir / "feedback_regression_plan.json", report)
    write_markdown(output_dir / "feedback_regression_plan.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
