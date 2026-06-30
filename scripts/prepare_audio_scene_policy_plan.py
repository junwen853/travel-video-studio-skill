#!/usr/bin/env python3
"""Prepare BGM-only audio policy rows for scenic/title/transition windows."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "muteA1A2SourceAudio": True,
    "routeBgmToTrack": 3,
    "targetMusicDb": -18,
    "allowIntentionalAmbient": False,
    "ambientApprovalReason": "",
    "voiceoverAllowed": False,
    "resolveImplementation": "",
    "readbackEvidence": "",
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}

KNOWN_FEEDBACK_PROBES = [
    {
        "label": "reported_voice_or_vertical_at_7_04",
        "second": 424.0,
        "source": "known_user_regression_probe",
        "note": "User flagged a 7:04 scenic/opening-style moment where BGM should lead and user/source voice must not leak.",
    }
]

READY_LICENSE_STATUSES = {"verified_manifest", "verified", "licensed", "approved"}
READY_CUE_STATUSES = {"ready", "verified", "approved", "applied"}


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


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def parse_timestamp(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if ":" not in text:
        return as_float(text)
    parts = text.split(":")
    try:
        nums = [float(part) for part in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def window(start: Any, end: Any = None, duration: Any = None, fallback_duration: float = 8.0) -> tuple[float, float] | None:
    start_seconds = as_float(start)
    if start_seconds is None:
        return None
    end_seconds = as_float(end)
    if end_seconds is None:
        duration_seconds = as_float(duration, fallback_duration)
        end_seconds = start_seconds + max(0.1, float(duration_seconds or fallback_duration))
    if end_seconds <= start_seconds:
        end_seconds = start_seconds + fallback_duration
    return start_seconds, end_seconds


def overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def contained_by(a_start: float, a_end: float, b_start: float, b_end: float, tolerance: float = 0.15) -> bool:
    return b_start <= a_start + tolerance and b_end >= a_end - tolerance


def clip_window(clip: dict[str, Any]) -> tuple[float, float] | None:
    return window(
        first_present(clip.get("timelineStartSeconds"), clip.get("startSeconds")),
        first_present(clip.get("timelineEndSeconds"), clip.get("endSeconds")),
        clip.get("durationSeconds"),
    )


def clip_list(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("clips", "timelineClips", "videoClips", "audioClips", "items"):
        rows = blueprint.get(key)
        if isinstance(rows, list):
            out.extend(row for row in rows if isinstance(row, dict))
    return out


def audio_plan(blueprint: dict[str, Any]) -> dict[str, Any]:
    plan = blueprint.get("audioPlan")
    return plan if isinstance(plan, dict) else {}


def bgm_cues(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    plan = audio_plan(blueprint)
    rows = plan.get("bgmCues") if isinstance(plan.get("bgmCues"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def cue_window(cue: dict[str, Any], fallback_duration: float) -> tuple[float, float] | None:
    return window(
        first_present(cue.get("timelineStartSeconds"), cue.get("startSeconds"), 0),
        first_present(cue.get("timelineEndSeconds"), cue.get("endSeconds")),
        first_present(cue.get("durationSeconds"), fallback_duration),
        fallback_duration=max(8.0, fallback_duration),
    )


def is_ready_bgm_cue(cue: dict[str, Any]) -> bool:
    track_index = int(as_float(cue.get("trackIndex"), -1) or -1)
    status = clean_words(cue.get("status")).lower()
    license_status = clean_words(cue.get("licenseStatus")).lower()
    return (
        track_index == 3
        and (not status or status in READY_CUE_STATUSES)
        and (not license_status or license_status in READY_LICENSE_STATUSES)
    )


def target_duration(blueprint: dict[str, Any], clips: list[dict[str, Any]], cues: list[dict[str, Any]]) -> float:
    candidates: list[float] = []
    for key in ("targetDurationSeconds", "actualVideoCoverageSeconds"):
        value = as_float(blueprint.get(key))
        if value:
            candidates.append(value)
    target_render = blueprint.get("targetRender") if isinstance(blueprint.get("targetRender"), dict) else {}
    value = as_float(target_render.get("durationSeconds"))
    if value:
        candidates.append(value)
    for clip in clips:
        clip_range = clip_window(clip)
        if clip_range:
            candidates.append(clip_range[1])
    for cue in cues:
        cue_range = cue_window(cue, 0)
        if cue_range:
            candidates.append(cue_range[1])
    return max(candidates) if candidates else 0.0


def plan_rows(package_dir: Path, rel: str, key: str) -> list[dict[str, Any]]:
    data = load_json(package_dir / rel) or {}
    rows = data.get(key) if isinstance(data.get(key), list) else []
    return [row for row in rows if isinstance(row, dict)]


def feedback_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json") or {}
    value = data.get("feedbackTimestamps")
    out: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            second = parse_timestamp(first_present(item.get("second"), item.get("seconds"), item.get("timestamp")))
            if second is None:
                continue
            out.append(
                {
                    "label": clean_words(item.get("label") or item.get("id") or f"feedback_{second:.2f}"),
                    "second": second,
                    "source": clean_words(item.get("source") or "feedback_regression_audit"),
                }
            )
    elif isinstance(value, dict):
        for label, second_value in value.items():
            second = parse_timestamp(second_value)
            if second is not None:
                out.append({"label": clean_words(label), "second": second, "source": "feedback_regression_audit"})
    return out


def feedback_plan_rows(package_dir: Path) -> list[dict[str, Any]]:
    data = load_json(package_dir / "feedback_regression_plan" / "feedback_regression_plan.json") or {}
    rows = data.get("probes") if isinstance(data.get("probes"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("includeInAudioPolicy") is False:
            continue
        second = parse_timestamp(first_present(row.get("second"), row.get("timestamp")))
        if second is None:
            continue
        out.append(
            {
                "label": clean_words(row.get("label") or row.get("id") or f"feedback_{second:.2f}"),
                "second": second,
                "source": "feedback_regression_plan",
                "note": clean_words(row.get("complaint") or row.get("riskType")),
            }
        )
    return out


def parse_feedback_arguments(values: list[str] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in values or []:
        for item in str(raw).split(","):
            item = item.strip()
            if not item:
                continue
            if "=" in item:
                label, timestamp = item.split("=", 1)
            else:
                label, timestamp = f"manual_feedback_{len(out) + 1}", item
            second = parse_timestamp(timestamp)
            if second is not None:
                out.append({"label": clean_words(label), "second": second, "source": "cli_feedback_timestamp"})
    return out


def audio_policy_evidence(blueprint: dict[str, Any]) -> dict[str, Any]:
    plan = audio_plan(blueprint)
    return {
        "audioPlanMode": plan.get("mode"),
        "sourceAudio": plan.get("sourceAudio") if isinstance(plan.get("sourceAudio"), dict) else {},
        "voiceover": plan.get("voiceover") if isinstance(plan.get("voiceover"), dict) else {},
        "voiceoverDisabledFlag": blueprint.get("voiceoverDisabled"),
    }


def source_audio_disabled(blueprint: dict[str, Any]) -> bool:
    evidence = audio_policy_evidence(blueprint)
    source_audio = evidence.get("sourceAudio") if isinstance(evidence.get("sourceAudio"), dict) else {}
    status = clean_words(source_audio.get("status")).lower()
    return "disabled" in status


def voiceover_disabled(blueprint: dict[str, Any]) -> bool:
    evidence = audio_policy_evidence(blueprint)
    voiceover = evidence.get("voiceover") if isinstance(evidence.get("voiceover"), dict) else {}
    status = clean_words(voiceover.get("status")).lower()
    return bool(blueprint.get("voiceoverDisabled")) or "disabled" in status or (
        not voiceover.get("exists") and not voiceover.get("sourcePath")
    )


def clip_risks(clip: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    track_type = clean_words(clip.get("trackType")).lower()
    track_index = int(as_float(clip.get("trackIndex"), -1) or -1)
    media_type = as_float(clip.get("mediaType"))
    if clip.get("includeSourceAudio") is True:
        risks.append("includeSourceAudio_true")
    if track_type == "audio" and track_index in {1, 2}:
        risks.append(f"audio_on_A{track_index}")
    if media_type is not None and int(media_type) != 1 and track_type in {"", "video"}:
        risks.append(f"mediaType_{int(media_type)}_not_video_only")
    return risks


def overlapping_clip_evidence(clips: list[dict[str, Any]], start: float, end: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    for clip in clips:
        clip_range = clip_window(clip)
        if not clip_range or not overlaps(start, end, clip_range[0], clip_range[1]):
            continue
        item = {
            "role": clip.get("role"),
            "chapterIndex": clip.get("chapterIndex"),
            "sourcePath": clip.get("sourcePath"),
            "timelineStartSeconds": clip_range[0],
            "timelineEndSeconds": clip_range[1],
            "trackType": clip.get("trackType"),
            "trackIndex": clip.get("trackIndex"),
            "mediaType": clip.get("mediaType"),
            "includeSourceAudio": clip.get("includeSourceAudio"),
            "purpose": clip.get("purpose"),
        }
        evidence.append(item)
        risk_reasons = clip_risks(clip)
        if risk_reasons:
            risks.append({"clip": item, "riskReasons": risk_reasons})
    return evidence[:20], risks


def matching_bgm_cues(cues: list[dict[str, Any]], start: float, end: float, duration: float) -> tuple[list[dict[str, Any]], bool]:
    matches: list[dict[str, Any]] = []
    covered = False
    for cue in cues:
        cue_range = cue_window(cue, duration)
        if not cue_range or not overlaps(start, end, cue_range[0], cue_range[1]):
            continue
        ready = is_ready_bgm_cue(cue)
        matches.append(
            {
                "timelineStartSeconds": cue_range[0],
                "timelineEndSeconds": cue_range[1],
                "trackIndex": cue.get("trackIndex"),
                "status": cue.get("status"),
                "licenseStatus": cue.get("licenseStatus"),
                "targetDbMusicOnly": cue.get("targetDbMusicOnly"),
                "manifest": cue.get("manifest"),
                "readyForPolicy": ready,
            }
        )
        if ready and contained_by(start, end, cue_range[0], cue_range[1]):
            covered = True
    return matches, covered


def checks_by_name(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = audit.get("checks") if isinstance(audit.get("checks"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in checks:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"])] = row
    return out


def post_render_evidence(package_dir: Path, start: float, end: float) -> dict[str, Any]:
    bgm_audit = load_json(package_dir / "bgm_audio_contract_audit.json") or {}
    feedback_audit = load_json(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json") or {}
    checks = checks_by_name(bgm_audit)
    feedback_check = checks.get("Feedback/title timestamps prove audible BGM and no leaked voice") or {}
    bgm_check = (feedback_check.get("evidence") or {}).get("bgmCheck") if isinstance(feedback_check.get("evidence"), dict) else {}
    bgm_evidence = bgm_check.get("evidence") if isinstance(bgm_check, dict) and isinstance(bgm_check.get("evidence"), dict) else {}
    audio_windows = bgm_evidence.get("audioWindows") if isinstance(bgm_evidence.get("audioWindows"), list) else []
    matching_windows = []
    for item in audio_windows:
        if not isinstance(item, dict):
            continue
        second = as_float(item.get("second"))
        if second is not None and start - 0.1 <= second <= end + 0.1:
            matching_windows.append(item)
    names = [
        "Resolve blueprint has a full-film A3 BGM cue",
        "Voiceover and source-camera audio are disabled for BGM-only delivery",
        "Scenic/title/transition windows have no A1/A2 voice or source-audio overlaps",
        "DaVinci readback has A3 BGM and no A1/A2 voice/source items",
        "Rendered BGM is audible and not mostly silent",
        "Feedback/title timestamps prove audible BGM and no leaked voice",
    ]
    return {
        "bgmAudioAuditStatus": bgm_audit.get("status"),
        "feedbackRegressionStatus": feedback_audit.get("status"),
        "relevantChecks": {name: (checks.get(name) or {}).get("status") for name in names},
        "audioWindows": matching_windows,
    }


def add_scene_row(
    rows: list[dict[str, Any]],
    row_type: str,
    label: str,
    start: float,
    end: float,
    source_evidence: dict[str, Any],
) -> None:
    rows.append(
        {
            "rowType": row_type,
            "label": clean_words(label, limit=180),
            "timelineStartSeconds": round(start, 3),
            "timelineEndSeconds": round(end, 3),
            "anchorSeconds": round(start, 3),
            "requiredMixMode": "bgm_only_no_camera_voice",
            "sourceEvidence": source_evidence,
        }
    )


def build_base_rows(package_dir: Path, extra_feedback: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for title in plan_rows(package_dir, "title_typography_plan/title_typography_plan.json", "titleRows"):
        span = window(title.get("timelineStartSeconds"), title.get("timelineEndSeconds"), fallback_duration=4.0)
        if not span:
            continue
        mode = clean_words(title.get("mode") or "title")
        row_type = "chapter_title_audio"
        if mode == "opening":
            row_type = "opening_title_audio"
        elif mode == "ending":
            row_type = "ending_title_audio"
        add_scene_row(
            rows,
            row_type,
            title.get("targetTitle") or title.get("titleText") or title.get("role") or "title",
            span[0],
            span[1],
            {"titleTypography": {key: title.get(key) for key in ("mode", "role", "chapterIndex", "cleanTitlePass", "segmentExists")}},
        )

    for transition in plan_rows(package_dir, "transition_bridge_plan/transition_bridge_plan.json", "boundaryRows"):
        plan = transition.get("existingTransitionPlan") if isinstance(transition.get("existingTransitionPlan"), dict) else {}
        span = window(plan.get("timelineStartSeconds"), None, plan.get("durationSeconds"), fallback_duration=8.0)
        if not span:
            continue
        add_scene_row(
            rows,
            "transition_audio",
            transition.get("routeIntent") or plan.get("bridge") or f"boundary_{transition.get('boundaryIndex')}",
            span[0],
            span[1],
            {
                "transitionBridge": {
                    "boundaryIndex": transition.get("boundaryIndex"),
                    "status": transition.get("status"),
                    "routeIntent": transition.get("routeIntent"),
                    "existingBridgeEvidenceCount": len(transition.get("existingBridgeEvidence") or []),
                }
            },
        )

    for visual in plan_rows(package_dir, "visual_establishing_plan/visual_establishing_plan.json", "establishingRows"):
        anchor = as_float(visual.get("timelineAnchorSeconds"))
        if anchor is None:
            continue
        role = clean_words(visual.get("role") or "visual_establishing")
        row_type = "visual_establishing_audio"
        if role.startswith("opening"):
            row_type = "opening_establishing_audio"
        elif role.startswith("ending"):
            row_type = "ending_establishing_audio"
        elif role.startswith("chapter"):
            row_type = "chapter_establishing_audio"
        add_scene_row(
            rows,
            row_type,
            visual.get("title") or visual.get("city") or role,
            anchor,
            min(duration or anchor + 8.0, anchor + 8.0),
            {
                "visualEstablishing": {
                    "role": visual.get("role"),
                    "chapterIndex": visual.get("chapterIndex"),
                    "status": visual.get("status"),
                    "existingEstablishingEvidenceCount": len(visual.get("existingEstablishingEvidence") or []),
                }
            },
        )

    for effect in plan_rows(package_dir, "effect_motion_plan/effect_motion_plan.json", "effectRows"):
        span = window(effect.get("timelineStartSeconds"), effect.get("timelineEndSeconds"), fallback_duration=4.0)
        if not span:
            continue
        add_scene_row(
            rows,
            "effect_motion_audio",
            effect.get("targetTitle") or effect.get("rowType") or "effect_motion",
            span[0],
            span[1],
            {
                "effectMotion": {
                    "rowType": effect.get("rowType"),
                    "status": effect.get("status"),
                    "recommendedMotion": effect.get("recommendedMotion"),
                }
            },
        )

    feedback_items = feedback_plan_rows(package_dir) + feedback_rows(package_dir) + extra_feedback
    unique_feedback: list[dict[str, Any]] = []
    seen_feedback: set[tuple[str, int]] = set()
    for item in feedback_items:
        second = as_float(item.get("second"))
        if second is None:
            continue
        key = (clean_words(item.get("label")).lower(), round(second * 1000))
        if key in seen_feedback:
            continue
        seen_feedback.add(key)
        unique_feedback.append(item)
    feedback_items = unique_feedback
    existing_seconds = [float(item["second"]) for item in feedback_items if as_float(item.get("second")) is not None]
    for probe in KNOWN_FEEDBACK_PROBES:
        second = float(probe["second"])
        if duration >= second and not any(abs(second - item) <= 2.0 for item in existing_seconds):
            feedback_items.append(dict(probe))
    for item in feedback_items:
        second = as_float(item.get("second"))
        if second is None or (duration and second > duration + 2):
            continue
        start = max(0.0, second - 4.0)
        end = min(duration or second + 4.0, second + 4.0)
        add_scene_row(
            rows,
            "feedback_audio_probe",
            item.get("label") or f"feedback_{second:.2f}",
            start,
            end,
            {"feedbackProbe": {"second": second, "source": item.get("source"), "note": item.get("note")}},
        )
    return rows


def enrich_rows(package_dir: Path, blueprint: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clips = clip_list(blueprint)
    cues = bgm_cues(blueprint)
    duration = target_duration(blueprint, clips, cues)
    policy_evidence = audio_policy_evidence(blueprint)
    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        start = float(row["timelineStartSeconds"])
        end = float(row["timelineEndSeconds"])
        clip_evidence, risks = overlapping_clip_evidence(clips, start, end)
        cue_evidence, bgm_covered = matching_bgm_cues(cues, start, end, duration)
        item = dict(row)
        item.update(
            {
                "rowIndex": index,
                "bgmCueEvidence": cue_evidence,
                "bgmCovered": bgm_covered,
                "sourceAudioPolicyEvidence": policy_evidence,
                "clipEvidence": clip_evidence,
                "sourceAudioRisks": risks,
                "postRenderEvidence": post_render_evidence(package_dir, start, end),
                "decision": dict(DECISION_FIELDS),
            }
        )
        item["status"] = "ready_bgm_only_window" if bgm_covered and not risks else "needs_audio_policy_fix"
        enriched.append(item)
    return enriched


def build_plan(package_dir: Path, feedback_timestamps: list[str] | None = None) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    blueprint = load_json(blueprint_path) or {}
    clips = clip_list(blueprint)
    cues = bgm_cues(blueprint)
    duration = target_duration(blueprint, clips, cues)
    extra_feedback = parse_feedback_arguments(feedback_timestamps)
    base_rows = build_base_rows(package_dir, extra_feedback, duration)
    rows = enrich_rows(package_dir, blueprint, base_rows)

    ready_cue_count = sum(1 for cue in cues if is_ready_bgm_cue(cue))
    rows_with_bgm = sum(1 for row in rows if row.get("bgmCovered"))
    source_audio_risk_count = sum(len(row.get("sourceAudioRisks") or []) for row in rows)
    rows_with_decision_fields = sum(
        1
        for row in rows
        if isinstance(row.get("decision"), dict) and set(DECISION_FIELDS).issubset(set(row["decision"]))
    )
    voice_disabled = voiceover_disabled(blueprint)
    source_disabled = source_audio_disabled(blueprint)
    policy_mode = (audio_plan(blueprint)).get("mode")
    status = (
        "ready_with_bgm_only_scene_policy"
        if blueprint_path.exists()
        and rows
        and rows_with_bgm == len(rows)
        and rows_with_decision_fields == len(rows)
        and source_audio_risk_count == 0
        and ready_cue_count >= 1
        and policy_mode == "bgm_only_no_camera_voice"
        and voice_disabled
        and source_disabled
        else ("needs_audio_scene_policy_decisions" if blueprint_path.exists() else "blocked_missing_resolve_blueprint")
    )
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "inputs": {
            "resolveBlueprint": str(blueprint_path),
            "bgmSourcingBrief": str(package_dir / "bgm_sourcing" / "bgm_sourcing_brief.json"),
            "bgmAudioContractAudit": str(package_dir / "bgm_audio_contract_audit.json"),
            "titleTypographyPlan": str(package_dir / "title_typography_plan" / "title_typography_plan.json"),
            "transitionBridgePlan": str(package_dir / "transition_bridge_plan" / "transition_bridge_plan.json"),
            "visualEstablishingPlan": str(package_dir / "visual_establishing_plan" / "visual_establishing_plan.json"),
            "effectMotionPlan": str(package_dir / "effect_motion_plan" / "effect_motion_plan.json"),
            "feedbackRegressionPlan": str(package_dir / "feedback_regression_plan" / "feedback_regression_plan.json"),
            "feedbackRegressionAudit": str(package_dir / "feedback_regression_audit" / "feedback_regression_audit.json"),
        },
        "summary": {
            "targetDurationSeconds": duration,
            "sceneWindowCount": len(rows),
            "bgmCoveredWindowCount": rows_with_bgm,
            "rowsWithDecisionFields": rows_with_decision_fields,
            "sourceAudioRiskCount": source_audio_risk_count,
            "readyBgmCueCount": ready_cue_count,
            "voiceoverDisabled": voice_disabled,
            "sourceAudioDisabled": source_disabled,
            "policyMode": policy_mode,
            "titleWindowCount": sum(1 for row in rows if "title_audio" in str(row.get("rowType"))),
            "transitionWindowCount": sum(1 for row in rows if row.get("rowType") == "transition_audio"),
            "establishingWindowCount": sum(1 for row in rows if "establishing_audio" in str(row.get("rowType"))),
            "feedbackWindowCount": sum(1 for row in rows if row.get("rowType") == "feedback_audio_probe"),
            "knownFeedbackProbeCount": sum(
                1
                for row in rows
                if ((row.get("sourceEvidence") or {}).get("feedbackProbe") or {}).get("source")
                in {"known_user_regression_probe", "feedback_regression_plan"}
            ),
        },
        "policy": {
            "audioMode": "bgm_only_no_camera_voice",
            "titleTransitionScenicBgmLed": True,
            "voiceoverAudioAllowedByDefault": False,
            "sourceCameraVoiceAllowedByDefault": False,
            "intentionalAmbientRequiresExplicitApproval": True,
            "writesResolve": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "sceneRows": rows,
        "selectionRubric": {
            "pass": [
                "Every title, establishing, transition, effect, and feedback probe window is covered by a ready A3 BGM cue.",
                "A1/A2 source camera audio and voiceover are absent from scenic/title/transition windows unless an explicit approved ambient exception exists.",
                "Resolve implementation decisions name the BGM track, target level, mute policy, and readback evidence.",
                "Post-render evidence, when available, confirms audible BGM and no leaked voice at feedback/title timestamps.",
            ],
            "reject": [
                "Any opening, aerial, scenery, title, or transition window carrying user/camera voice by accident.",
                "Any BGM cue that is unverified, not on A3, too short for the scene window, or silent after render.",
                "Any generic ambience exception without explicit approval and a reason tied to story.",
                "Any workflow that treats BGM checks as only post-render QA instead of pre-Resolve planning.",
            ],
        },
        "nextActions": [
            "Fill decision fields before Resolve apply for any row that needs manual mix implementation.",
            "Keep A1/A2 muted or empty for scenic/title/transition windows; route the approved music bed to A3.",
            "After Resolve apply, paste timeline readback evidence into each row and rerun audit_bgm_audio_contract.py.",
            "Add new user-reported timestamps through --feedback-timestamps label=mm:ss so they become reusable regression probes.",
        ],
        "safety": {
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Audio Scene Policy Plan",
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
        "## Scene Rows",
    ]
    for row in plan["sceneRows"]:
        risks = row.get("sourceAudioRisks") or []
        lines.extend(
            [
                "",
                f"### Row {row['rowIndex']}: {row['rowType']}",
                f"- Label: {row.get('label')}",
                f"- Window: `{row.get('timelineStartSeconds')}` to `{row.get('timelineEndSeconds')}`",
                f"- Status: `{row.get('status')}`",
                f"- BGM covered: `{row.get('bgmCovered')}`",
                f"- Source audio risk count: {len(risks)}",
                "- Decision fields to fill:",
            ]
        )
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare BGM-only audio policy rows for scene windows.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir", help="Defaults to <package>/audio_scene_policy_plan.")
    parser.add_argument(
        "--feedback-timestamps",
        action="append",
        help="Comma-separated label=mm:ss probes, for example reported_voice_at_7_04=7:04.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "audio_scene_policy_plan"
    plan = build_plan(package_dir, args.feedback_timestamps)
    write_json(output_dir / "audio_scene_policy_plan.json", plan)
    write_markdown(output_dir / "audio_scene_policy_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
