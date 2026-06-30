#!/usr/bin/env python3
"""Prepare a deterministic recovery plan for a matched travel project that is not safe to cut yet."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from project_discovery import default_app_dir, discover_app_and_project
except Exception:  # noqa: BLE001
    discover_app_and_project = None  # type: ignore[assignment]


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


def skill_dir_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_project(path: Path, project_name: str | None) -> tuple[Path, Path]:
    if discover_app_and_project:
        app_dir, project_dir, _projects = discover_app_and_project(path, project_name)
        if not project_dir:
            raise SystemExit(f"Project not found under: {path}")
        return app_dir, project_dir
    path = path.expanduser().resolve()
    if (path / "projects").exists():
        if not project_name:
            raise SystemExit("--project-name is required when --project-dir points at an app root")
        return path, path / "projects" / project_name
    app_dir = path.parent.parent if path.parent.name == "projects" else path
    return app_dir, path


def q(value: str | Path) -> str:
    return shlex.quote(str(value))


def command(
    command_id: str,
    title: str,
    argv: list[str | Path],
    *,
    approval_required: bool = False,
    writes_project: bool = False,
    calls_cloud: bool = False,
    writes_resolve: bool = False,
    downloads_external_assets: bool = False,
) -> dict[str, Any]:
    return {
        "id": command_id,
        "title": title,
        "command": " ".join(q(item) for item in argv),
        "approvalRequired": approval_required,
        "writesProjectFiles": writes_project,
        "callsCloudVision": calls_cloud,
        "writesResolve": writes_resolve,
        "downloadsExternalAssets": downloads_external_assets,
    }


def latest_recognition_report(project_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    pointer = load_json(project_dir / "latest_footage_recognition_route_report.json")
    if isinstance(pointer, dict) and pointer.get("report"):
        path = Path(str(pointer["report"])).expanduser()
        if path.exists():
            data = load_json(path)
            if isinstance(data, dict):
                return path, data
    candidates = sorted((project_dir / "recognition_reports").glob("*/footage_recognition_route_report.json"))
    for path in reversed(candidates):
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    return None, None


def latest_json_in_tree(project_dir: Path, name: str) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = sorted(project_dir.rglob(name), key=lambda path: path.stat().st_mtime if path.exists() else 0)
    for path in reversed(candidates):
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    return None, None


def latest_confirmed_route_candidate(project_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    pointer = load_json(project_dir / "latest_confirmed_route_candidate.json")
    if isinstance(pointer, dict):
        for key in ("candidate", "path", "report", "json"):
            if pointer.get(key):
                path = Path(str(pointer[key])).expanduser()
                data = load_json(path)
                if isinstance(data, dict):
                    return path, data
    return latest_json_in_tree(project_dir, "codex_visual_confirmed_route_candidate.json")


def count_frames(frame_index: Any) -> int:
    if not isinstance(frame_index, dict):
        return 0
    if isinstance(frame_index.get("frameCount"), int):
        return int(frame_index["frameCount"])
    if isinstance(frame_index.get("frames"), list):
        return len(frame_index["frames"])
    files = frame_index.get("files")
    if isinstance(files, dict):
        total = 0
        for item in files.values():
            if isinstance(item, dict):
                total += count_frames(item)
        return total
    if not isinstance(files, list):
        return 0
    total = 0
    for item in files:
        if not isinstance(item, dict):
            continue
        frames = item.get("frames")
        if isinstance(frames, list):
            total += len(frames)
        elif isinstance(item.get("framePaths"), list):
            total += len(item["framePaths"])
    return total


def choice_matches_project(choice: dict[str, Any], project_dir: Path) -> bool:
    if choice.get("recommendedProjectName") == project_dir.name:
        return True
    for item in choice.get("matchingProjects") or []:
        if isinstance(item, dict) and Path(str(item.get("projectDir", ""))).expanduser() == project_dir:
            return True
    return False


def intake_summary(intake: Any, project_dir: Path) -> dict[str, Any]:
    if not isinstance(intake, dict):
        return {"status": None, "choiceCount": 0, "matchedChoices": [], "unknownChoices": [], "regions": []}
    choices = [row for row in intake.get("recommendedChoices") or [] if isinstance(row, dict)]
    matched = [row for row in choices if choice_matches_project(row, project_dir)]
    unknown = [row for row in choices if row.get("status") == "needs_identification"]
    regions = sorted({str(row.get("region")) for row in choices if row.get("region")})
    return {
        "status": intake.get("status"),
        "volumeRoot": intake.get("volumeRoot"),
        "choiceCount": len(choices),
        "matchedChoices": [
            {
                "choiceId": row.get("choiceId"),
                "status": row.get("status"),
                "region": row.get("region"),
                "sourceRoot": row.get("sourceRoot"),
                "videoCount": row.get("videoCount"),
                "recommendedProjectName": row.get("recommendedProjectName"),
            }
            for row in matched
        ],
        "unknownChoices": [row.get("choiceId") for row in unknown],
        "regions": regions,
        "warnings": intake.get("warnings") if isinstance(intake.get("warnings"), list) else [],
        "safety": intake.get("safety") if isinstance(intake.get("safety"), dict) else {},
    }


def contains_any(texts: list[str], needles: list[str]) -> bool:
    text = "\n".join(texts).lower()
    return any(needle.lower() in text for needle in needles)


def classify_blockers(
    project_dir: Path,
    artifacts: dict[str, Any],
    intake_info: dict[str, Any],
) -> tuple[list[str], list[str]]:
    blocker_types: list[str] = []
    caveat_types: list[str] = []
    recognition = artifacts.get("recognition") if isinstance(artifacts.get("recognition"), dict) else {}
    recognition_summary = recognition.get("summary") if isinstance(recognition.get("summary"), dict) else {}
    recognition_blockers = [str(item) for item in recognition.get("blockers") or []]
    recognition_next = [str(item) for item in recognition.get("nextActions") or []]
    location = artifacts.get("locationTruth") if isinstance(artifacts.get("locationTruth"), dict) else {}
    location_summary = location.get("summary") if isinstance(location.get("summary"), dict) else {}
    location_blockers = [str(item) for item in location.get("blockers") or []]
    route_review = artifacts.get("routeReviewPointer") if isinstance(artifacts.get("routeReviewPointer"), dict) else {}
    decision_sheet = artifacts.get("routeDecisionSheet") if isinstance(artifacts.get("routeDecisionSheet"), dict) else {}
    pipeline = artifacts.get("pipeline") if isinstance(artifacts.get("pipeline"), dict) else {}
    all_blocker_text = recognition_blockers + recognition_next + location_blockers

    if not project_dir.exists():
        blocker_types.append("project_missing")
    if not artifacts.get("mediaIndexPath"):
        blocker_types.append("media_index_missing")
    if not artifacts.get("frameIndexPath") or int(artifacts.get("frameCount") or 0) == 0:
        blocker_types.append("frame_index_missing")
    if intake_info.get("choiceCount", 0) > 1 or len(intake_info.get("regions") or []) > 1:
        blocker_types.append("multi_root_choice")
    if intake_info.get("unknownChoices"):
        blocker_types.append("unknown_media_root")
    if recognition.get("status") == "blocked":
        blocker_types.append("recognition_blocked")
    if contains_any(all_blocker_text, ["cloud vision", "mimo", "provider", "cloud"]):
        blocker_types.append("provider_missing")
    if recognition_summary.get("cloudCallsAllowed") is False or pipeline.get("allowCloudCall") is False:
        blocker_types.append("cloud_call_not_approved")
    if not artifacts.get("confirmedRoutePath") or contains_any(all_blocker_text, ["confirmed_route_timeline", "confirmed route"]):
        blocker_types.append("confirmed_route_missing")
    if route_review.get("status") == "blocked" or decision_sheet.get("status") in {"needs_user_approval", "blocked"}:
        blocker_types.append("route_review_pending")
    if int(recognition_summary.get("needsHumanReviewCount") or 0) > 0:
        blocker_types.append("route_review_pending")
    if location.get("status") == "blocked" or location_summary.get("routeAwareEditClaimAllowed") is False:
        blocker_types.append("route_not_ready")
    if location_summary.get("exactPerVideoLocationClaimAllowed") is False:
        caveat_types.append("exact_per_video_location_unverified")
    if not recognition_summary.get("codexVisualProviderUsed") and not artifacts.get("confirmedRoutePath"):
        caveat_types.append("codex_visual_review_needed")

    return sorted(set(blocker_types)), sorted(set(caveat_types))


def phase_status(blocker_types: list[str], required: set[str], *, after_recovery: bool = False) -> str:
    if after_recovery:
        return "after_recovery"
    return "needed" if required.intersection(blocker_types) else "ready_or_not_applicable"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    skill_dir = Path(args.skill_dir).expanduser().resolve() if args.skill_dir else skill_dir_from_script()
    scripts_dir = skill_dir / "scripts"
    app_dir, project_dir = resolve_project(Path(args.project_dir), args.project_name)
    project_data = load_json(project_dir / "project.json") or {}
    media_index_path = project_dir / "media_index.json" if (project_dir / "media_index.json").exists() else None
    media_index = load_json(media_index_path)
    frame_index_path = project_dir / "latest_frame_index.json" if (project_dir / "latest_frame_index.json").exists() else None
    frame_index_pointer = load_json(frame_index_path)
    actual_frame_index_path = frame_index_path
    frame_index = frame_index_pointer
    if isinstance(frame_index_pointer, dict):
        pointer_value = frame_index_pointer.get("frameIndex")
        files_value = frame_index_pointer.get("files")
        if not pointer_value and isinstance(files_value, dict):
            pointer_value = files_value.get("frameIndex")
        if pointer_value:
            candidate = Path(str(pointer_value)).expanduser()
            if candidate.exists():
                actual_frame_index_path = candidate
                frame_index = load_json(candidate)
    pipeline = load_json(project_dir / "latest_location_route_pipeline.json") or {}
    route_review_pointer = load_json(project_dir / "latest_route_review.json") or {}
    route_decision_sheet = load_json(project_dir / "latest_route_decision_sheet.json") or {}
    recognition_path, recognition = latest_recognition_report(project_dir)
    route_candidate_path, route_candidate = latest_confirmed_route_candidate(project_dir)
    location_path = Path(args.location_truth_json).expanduser().resolve() if args.location_truth_json else None
    location_truth = load_json(location_path)
    if not isinstance(location_truth, dict):
        location_path, location_truth = latest_json_in_tree(project_dir, "location_truth_contract_audit.json")
    intake_path = Path(args.intake_json).expanduser().resolve() if args.intake_json else None
    intake = load_json(intake_path)
    if not isinstance(intake, dict):
        intake_path, intake = latest_json_in_tree(app_dir, "external_media_intake.json")
    intake_info = intake_summary(intake, project_dir)

    media_summary = media_index.get("summary") if isinstance(media_index, dict) and isinstance(media_index.get("summary"), dict) else {}
    recognition_summary = recognition.get("summary") if isinstance(recognition, dict) and isinstance(recognition.get("summary"), dict) else {}
    location_summary = location_truth.get("summary") if isinstance(location_truth, dict) and isinstance(location_truth.get("summary"), dict) else {}
    confirmed_route_path = project_dir / "confirmed_route_timeline.json" if (project_dir / "confirmed_route_timeline.json").exists() else None
    artifacts = {
        "mediaIndexPath": str(media_index_path) if media_index_path else None,
        "frameIndexPath": str(actual_frame_index_path) if actual_frame_index_path else None,
        "frameCount": count_frames(frame_index),
        "confirmedRoutePath": str(confirmed_route_path) if confirmed_route_path else None,
        "pipeline": pipeline,
        "routeReviewPointer": route_review_pointer,
        "routeDecisionSheet": route_decision_sheet,
        "recognitionReportPath": str(recognition_path) if recognition_path else None,
        "recognition": recognition,
        "confirmedRouteCandidatePath": str(route_candidate_path) if route_candidate_path else None,
        "confirmedRouteCandidate": route_candidate,
        "locationTruthPath": str(location_path) if location_path else None,
        "locationTruth": location_truth,
        "intakePath": str(intake_path) if intake_path else None,
        "intake": intake,
    }
    blocker_types, caveat_types = classify_blockers(project_dir, artifacts, intake_info)
    editing_allowed_now = (
        isinstance(recognition, dict)
        and recognition.get("status") in {"ready", "passed", "passed_with_caveats"}
        and isinstance(location_truth, dict)
        and location_truth.get("status") in {"passed", "passed_with_caveats"}
        and location_summary.get("routeAwareEditClaimAllowed") is True
        and not any(item in blocker_types for item in ("project_missing", "media_index_missing", "frame_index_missing", "recognition_blocked", "route_not_ready"))
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_dir / "blocked_project_recovery" / timestamp
    volume_root = str(intake_info.get("volumeRoot") or "/Volumes")
    target_minutes = str(args.target_duration_minutes)
    candidate_ready = isinstance(route_candidate, dict) and route_candidate.get("canApply") is True
    candidate_summary = None
    if isinstance(route_candidate, dict):
        candidate_body = route_candidate.get("candidate") if isinstance(route_candidate.get("candidate"), dict) else {}
        candidate_summary = {
            "status": route_candidate.get("status"),
            "canApply": route_candidate.get("canApply"),
            "chapterCount": candidate_body.get("chapterCount"),
            "sourceVideoCount": candidate_body.get("sourceVideoCount"),
            "candidateJson": str(route_candidate_path) if route_candidate_path else route_candidate.get("candidateJson"),
            "sourceCodexVisualReview": candidate_body.get("sourceCodexVisualReview"),
        }

    commands_common = {
        "check_state": command(
            "check_state",
            "Read current project state",
            [sys.executable, scripts_dir / "check_project_state.py", "--project-dir", project_dir, "--json"],
        ),
        "discover_external_media": command(
            "discover_external_media",
            "Rediscover mounted travel roots without writing the drive",
            [
                sys.executable,
                scripts_dir / "discover_external_media.py",
                "--volume-root",
                volume_root,
                "--max-depth",
                "3",
                "--min-videos",
                "20",
                "--sample-limit",
                "5",
                "--output",
                output_dir / "external_media_discovery.json",
            ],
        ),
        "external_intake": command(
            "prepare_external_media_intake",
            "Regenerate explicit project/media-root choice packet",
            [
                sys.executable,
                scripts_dir / "prepare_external_media_intake.py",
                "--project-dir",
                app_dir,
                "--volume-root",
                volume_root,
                "--max-depth",
                "3",
                "--min-videos",
                "20",
                "--sample-limit",
                "5",
                "--output-dir",
                output_dir / "external_media_intake",
            ],
            writes_project=False,
        ),
        "media_index_dry": command(
            "run_videoclaw_media_index_dry",
            "Dry-run media index repair",
            [sys.executable, scripts_dir / "run_videoclaw_media_index.py", "--project-dir", project_dir, "--json"],
        ),
        "media_index_apply": command(
            "run_videoclaw_media_index_apply_after_approval",
            "Apply media index repair after counts are approved",
            [sys.executable, scripts_dir / "run_videoclaw_media_index.py", "--project-dir", project_dir, "--apply", "--json"],
            approval_required=True,
            writes_project=True,
        ),
        "route_pipeline_local": command(
            "run_videoclaw_route_pipeline_local",
            "Refresh local frames/prefilter/route scaffold without cloud calls",
            [sys.executable, scripts_dir / "run_videoclaw_route_pipeline.py", "--project-dir", project_dir, "--json"],
            writes_project=True,
        ),
        "route_pipeline_mimo": command(
            "run_videoclaw_route_pipeline_mimo_after_approval",
            "Run cloud visual recognition only after explicit approval and configured Mimo/API key",
            [
                sys.executable,
                scripts_dir / "run_videoclaw_route_pipeline.py",
                "--project-dir",
                project_dir,
                "--allow-cloud-call",
                "--cloud-provider-id",
                "mimo",
                "--json",
            ],
            approval_required=True,
            writes_project=True,
            calls_cloud=True,
        ),
        "route_review": command(
            "prepare_route_review",
            "Prepare route review packet/contact sheet",
            [sys.executable, scripts_dir / "prepare_route_review.py", "--project-dir", project_dir, "--json"],
            writes_project=True,
        ),
        "route_decision_sheet": command(
            "prepare_route_decision_sheet",
            "Prepare editable route decision sheet",
            [sys.executable, scripts_dir / "prepare_route_decision_sheet.py", "--project-dir", project_dir, "--json"],
            writes_project=True,
        ),
        "codex_visual_confirmed_route": command(
            "prepare_codex_visual_confirmed_route",
            "Convert Codex visual review notes into a confirmed route candidate",
            [
                sys.executable,
                scripts_dir / "prepare_codex_visual_confirmed_route.py",
                "--project-dir",
                project_dir,
                "--output-dir",
                output_dir / "codex_visual_confirmed_route",
                "--json",
            ],
            writes_project=True,
        ),
        "codex_visual_confirmed_route_apply": command(
            "prepare_codex_visual_confirmed_route_apply_after_approval",
            "Apply Codex visual confirmed route only after full-folder review is approved",
            [
                sys.executable,
                scripts_dir / "prepare_codex_visual_confirmed_route.py",
                "--project-dir",
                project_dir,
                "--output-dir",
                output_dir / "codex_visual_confirmed_route",
                "--apply",
                "--json",
            ],
            approval_required=True,
            writes_project=True,
        ),
        "confirmed_route_candidate_audit": command(
            "audit_confirmed_route_candidate",
            "Audit confirmed-route candidate coverage before any route apply",
            [
                sys.executable,
                scripts_dir / "audit_confirmed_route_candidate.py",
                "--project-dir",
                project_dir,
                "--output-dir",
                output_dir / "confirmed_route_candidate_audit",
                "--json",
            ],
            writes_project=False,
        ),
        "confirmed_route_candidate": command(
            "prepare_confirmed_route_candidate",
            "Prepare gated confirmed-route candidate from route decisions",
            [sys.executable, scripts_dir / "prepare_confirmed_route_candidate.py", "--project-dir", project_dir, "--json"],
            writes_project=True,
        ),
        "recognition_report": command(
            "prepare_footage_recognition_report",
            "Rebuild recognition/route-readiness report",
            [sys.executable, scripts_dir / "prepare_footage_recognition_report.py", "--project-dir", project_dir, "--json"],
            writes_project=True,
        ),
        "location_truth": command(
            "audit_location_truth_contract",
            "Re-audit route-aware and exact-location claim level",
            [
                sys.executable,
                scripts_dir / "audit_location_truth_contract.py",
                "--project-dir",
                project_dir,
                "--output-dir",
                output_dir / "location_truth",
                "--json",
            ],
            writes_project=False,
        ),
        "delivery_workflow": command(
            "run_delivery_workflow_after_recovery",
            "Start safe package workflow only after recognition and location truth gates allow route-aware editing",
            [
                sys.executable,
                scripts_dir / "run_delivery_workflow.py",
                "--project-dir",
                app_dir,
                "--project-name",
                project_dir.name,
                "--target-duration-minutes",
                target_minutes,
                "--json",
            ],
            writes_project=True,
        ),
    }

    phases = [
        {
            "order": 1,
            "id": "source_root_lock",
            "title": "Lock the selected project/media root before any editing",
            "status": phase_status(blocker_types, {"multi_root_choice", "unknown_media_root"}),
            "why": "Mounted drives can contain Japan, Hong Kong/Macau, and unknown backup roots. The Skill must choose explicitly instead of defaulting to the last successful project.",
            "commands": [commands_common["check_state"], commands_common["discover_external_media"], commands_common["external_intake"]],
            "exitCriteria": [
                "The intended source root and project folder are named explicitly.",
                "Unknown mounted roots are either ignored with a reason or converted into their own project.",
                "The source drive remains read-only.",
            ],
        },
        {
            "order": 2,
            "id": "local_artifact_refresh",
            "title": "Refresh local media, frame, and route scaffolds without cloud",
            "status": phase_status(blocker_types, {"media_index_missing", "frame_index_missing"}),
            "why": "A recovery agent needs current media counts and extracted frames before judging recognition quality.",
            "commands": [commands_common["media_index_dry"], commands_common["media_index_apply"], commands_common["route_pipeline_local"]],
            "exitCriteria": [
                "media_index.json accounts for every active source video.",
                "latest_frame_index.json has representative frames for the whole folder.",
                "No source drive files are modified.",
            ],
        },
        {
            "order": 3,
            "id": "recognition_path",
            "title": "Choose a real recognition path: Mimo/cloud approval or Codex visual review",
            "status": phase_status(blocker_types, {"provider_missing", "cloud_call_not_approved", "recognition_blocked"}),
            "why": "Local placeholder rows or disabled cloud runs cannot be treated as verified location recognition.",
            "commands": [commands_common["route_pipeline_mimo"], commands_common["route_review"], commands_common["codex_visual_confirmed_route"]],
            "manualWork": [
                "If cloud is approved, verify the Mimo/API key and rerun with --allow-cloud-call.",
                "If cloud is not approved, Codex must inspect the route review contact sheet and write stable Codex visual route notes before confirming the route.",
            ],
            "exitCriteria": [
                "Recognition report no longer says cloud/Mimo did not actually run unless the Codex visual path replaces it.",
                "Every active source video has reviewable location evidence or an explicit unknown/do-not-cut decision.",
            ],
        },
        {
            "order": 4,
            "id": "route_confirmation",
            "title": "Resolve route review into a confirmed route before cutting",
            "status": "candidate_ready_awaiting_approval"
            if candidate_ready and not confirmed_route_path
            else phase_status(blocker_types, {"confirmed_route_missing", "route_review_pending", "route_not_ready"}),
            "why": "A broad scaffold is enough to inspect footage, but not enough to claim a route-aware travel film.",
            "commands": [
                commands_common["route_review"],
                commands_common["route_decision_sheet"],
                commands_common["confirmed_route_candidate"],
                commands_common["confirmed_route_candidate_audit"],
                commands_common["codex_visual_confirmed_route_apply"],
            ],
            "exitCriteria": [
                "confirmed_route_timeline.json exists and links all active videos or documents excluded/unknown videos.",
                "audit_confirmed_route_candidate.py passes or passes only with explicit non-GPS caveats before any route apply command.",
                "Route decision sheet approval is recorded before any apply step.",
                "No project route files are overwritten from a blocked review.",
            ],
        },
        {
            "order": 5,
            "id": "truth_gates",
            "title": "Re-run recognition and location-truth gates",
            "status": "needed",
            "why": "The Skill should not proceed based on stale blocked reports.",
            "commands": [commands_common["recognition_report"], commands_common["location_truth"]],
            "exitCriteria": [
                "prepare_footage_recognition_report.py is ready or lists only non-cutting caveats.",
                "audit_location_truth_contract.py allows route-aware edit claims, or the project remains blocked.",
                "Exact GPS/per-clip location claims remain forbidden unless verified evidence exists.",
            ],
        },
        {
            "order": 6,
            "id": "package_build_gate",
            "title": "Build the delivery package only after recovery gates pass",
            "status": "ready_now" if editing_allowed_now else "after_recovery",
            "why": "The current purpose is Skill correctness: do not hide a route/recognition failure by cutting anyway.",
            "commands": [commands_common["delivery_workflow"]],
            "exitCriteria": [
                "Recognition report is ready.",
                "Location truth allows route-aware edit claims.",
                "The package workflow remains DaVinci-first and safe until explicit Resolve write/render approval.",
            ],
        },
    ]

    status = "ready_no_recovery_needed" if editing_allowed_now else "recovery_plan_ready"
    if "project_missing" in blocker_types:
        status = "blocked"

    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "projectDir": str(project_dir),
        "appDir": str(app_dir),
        "skillDir": str(skill_dir),
        "editingAllowedNow": editing_allowed_now,
        "blockerTypes": blocker_types,
        "caveatTypes": caveat_types,
        "summary": {
            "projectName": project_dir.name,
            "title": project_data.get("title") if isinstance(project_data, dict) else None,
            "mediaRoots": project_data.get("mediaRoots") if isinstance(project_data, dict) else None,
            "mediaVideoCount": media_summary.get("videoCount") or recognition_summary.get("mediaVideoCount") or location_summary.get("indexedVideoCount"),
            "frameCount": artifacts["frameCount"],
            "recognitionStatus": recognition.get("status") if isinstance(recognition, dict) else None,
            "recognitionCoverageRatio": recognition_summary.get("recognitionCoverageRatio"),
            "locationTruthStatus": location_truth.get("status") if isinstance(location_truth, dict) else None,
            "routeAwareEditClaimAllowed": location_summary.get("routeAwareEditClaimAllowed"),
            "exactPerVideoLocationClaimAllowed": location_summary.get("exactPerVideoLocationClaimAllowed"),
            "confirmedRouteExists": bool(confirmed_route_path),
            "confirmedRouteCandidate": candidate_summary,
            "routeReviewStatus": route_review_pointer.get("status") if isinstance(route_review_pointer, dict) else None,
            "routeDecisionSheetStatus": route_decision_sheet.get("status") if isinstance(route_decision_sheet, dict) else None,
        },
        "sourceIntake": intake_info,
        "artifacts": {
            "mediaIndex": str(media_index_path) if media_index_path else None,
            "frameIndex": str(actual_frame_index_path) if actual_frame_index_path else None,
            "pipeline": str(project_dir / "latest_location_route_pipeline.json") if (project_dir / "latest_location_route_pipeline.json").exists() else None,
            "routeReviewPointer": str(project_dir / "latest_route_review.json") if (project_dir / "latest_route_review.json").exists() else None,
            "routeDecisionSheetPointer": str(project_dir / "latest_route_decision_sheet.json") if (project_dir / "latest_route_decision_sheet.json").exists() else None,
            "confirmedRouteCandidate": str(route_candidate_path) if route_candidate_path else None,
            "confirmedRoute": str(confirmed_route_path) if confirmed_route_path else None,
            "recognitionReport": str(recognition_path) if recognition_path else None,
            "locationTruthReport": str(location_path) if location_path else None,
            "intake": str(intake_path) if intake_path else None,
        },
        "recognitionBlockers": recognition.get("blockers") if isinstance(recognition, dict) else [],
        "locationTruthBlockers": location_truth.get("blockers") if isinstance(location_truth, dict) else [],
        "phases": phases,
        "safety": {
            "modifiesSourceDrive": False,
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "callsCloudVisionByDefault": False,
            "writesProjectFiles": True,
            "requiresExplicitApprovalForCloud": True,
            "requiresExplicitApprovalForRouteApply": True,
            "requiresExplicitApprovalForResolveApply": True,
        },
        "handoffPrompt": (
            "Use $travel-video-studio on this project. Do not cut yet unless the latest recognition report is ready "
            "and audit_location_truth_contract.py allows route-aware edit claims. Follow blocked_project_recovery_plan.json "
            "phase order, preserve the source drive read-only, and only use Mimo/cloud, route apply, Resolve apply, or render "
            "after explicit approval."
        ),
        "nextAction": "Review and audit the ready confirmed-route candidate, apply only after approval, then re-run truth gates before package build."
        if candidate_ready and not confirmed_route_path
        else "Start with the first phase whose status is `needed`; if all phases are clear, re-run truth gates before package build.",
        "contract": {
            "purpose": "Convert a matched-but-blocked travel project into an auditable recovery path instead of letting another agent cut unsafe footage.",
            "notFinalDelivery": "This plan is not a film and not proof of route truth. It is the deterministic path to reach safe route-aware editing.",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report["outputJson"] = str(output_dir / "blocked_project_recovery_plan.json")
    report["outputMarkdown"] = str(output_dir / "blocked_project_recovery_plan.md")
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Blocked Project Recovery Plan",
        "",
        f"Status: `{report['status']}`",
        f"Project: `{report['projectDir']}`",
        f"Editing allowed now: `{report['editingAllowedNow']}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(report["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Blocker Types",
    ]
    if report.get("blockerTypes"):
        lines.extend(f"- `{item}`" for item in report["blockerTypes"])
    else:
        lines.append("- none")
    if report.get("caveatTypes"):
        lines.extend(["", "## Caveats"])
        lines.extend(f"- `{item}`" for item in report["caveatTypes"])
    lines.extend(["", "## Phases"])
    for phase in report["phases"]:
        lines.extend(["", f"### {phase['order']}. {phase['title']}", f"- Status: `{phase['status']}`", f"- Why: {phase['why']}"])
        if phase.get("manualWork"):
            lines.append("- Manual work:")
            lines.extend(f"  - {item}" for item in phase["manualWork"])
        lines.append("- Commands:")
        for cmd in phase.get("commands") or []:
            flags = []
            if cmd.get("approvalRequired"):
                flags.append("approval required")
            if cmd.get("callsCloudVision"):
                flags.append("cloud")
            if cmd.get("writesProjectFiles"):
                flags.append("project write")
            flag_text = f" ({', '.join(flags)})" if flags else ""
            lines.extend(["", f"```bash\n{cmd['command']}\n```", f"{cmd['title']}{flag_text}"])
        lines.append("- Exit criteria:")
        lines.extend(f"  - {item}" for item in phase.get("exitCriteria") or [])
    if report.get("recognitionBlockers"):
        lines.extend(["", "## Recognition Blockers"])
        lines.extend(f"- {item}" for item in report["recognitionBlockers"])
    if report.get("locationTruthBlockers"):
        lines.extend(["", "## Location Truth Blockers"])
        lines.extend(f"- {item}" for item in report["locationTruthBlockers"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "```json",
            json.dumps(report["safety"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Handoff Prompt",
            "",
            report["handoffPrompt"],
            "",
            "## Contract",
            "",
            "```json",
            json.dumps(report["contract"], ensure_ascii=False, indent=2),
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a recovery plan for a travel project that is matched but not safe to cut yet.")
    parser.add_argument("--project-dir", required=True, help="VideoClaw app dir or project dir.")
    parser.add_argument("--project-name", help="Project folder name when --project-dir points at the app.")
    parser.add_argument("--intake-json", help="External media intake JSON for mounted drive ambiguity.")
    parser.add_argument("--location-truth-json", help="Latest location truth audit JSON for the blocked project.")
    parser.add_argument("--output-dir", help="Output directory. Defaults to <project>/blocked_project_recovery/<timestamp>.")
    parser.add_argument("--skill-dir", help="Skill directory. Defaults to the parent of this script directory.")
    parser.add_argument("--target-duration-minutes", type=float, default=20.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args)
    output_json = Path(report["outputJson"])
    output_markdown = Path(report["outputMarkdown"])
    write_json(output_json, report)
    write_markdown(output_markdown, report)

    project_dir = Path(report["projectDir"])
    if project_dir.exists():
        write_json(
            project_dir / "latest_blocked_project_recovery_plan.json",
            {
                "createdAt": report["createdAt"],
                "status": report["status"],
                "recoveryPlan": str(output_json),
                "recoveryPlanMarkdown": str(output_markdown),
                "editingAllowedNow": report["editingAllowedNow"],
                "blockerTypes": report["blockerTypes"],
            },
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "editingAllowedNow": report["editingAllowedNow"],
                    "blockerTypes": report["blockerTypes"],
                    "outputJson": report["outputJson"],
                    "outputMarkdown": report["outputMarkdown"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
