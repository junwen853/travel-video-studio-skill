#!/usr/bin/env python3
"""Prepare a user-approval contract before writing a DaVinci Resolve timeline."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clip_source_stats(blueprint: dict[str, Any]) -> dict[str, Any]:
    clips = blueprint.get("clips") if isinstance(blueprint.get("clips"), list) else []
    source_paths = [str(clip.get("sourcePath")) for clip in clips if clip.get("sourcePath")]
    missing = [path for path in sorted(set(source_paths)) if not Path(path).expanduser().exists()]
    roles = Counter(str(clip.get("role") or clip.get("kind") or "main_footage") for clip in clips)
    total_seconds = 0.0
    for clip in clips:
        try:
            total_seconds += max(0.0, float(clip.get("timelineEndSeconds") or 0) - float(clip.get("timelineStartSeconds") or 0))
        except Exception:  # noqa: BLE001
            pass
    return {
        "clipCount": len(clips),
        "sourceFileCount": len(set(source_paths)),
        "missingSourceFiles": missing,
        "roles": dict(roles),
        "timelineClipSeconds": round(total_seconds, 3),
    }


def track_summary(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for track in blueprint.get("tracks") or []:
        rows.append(
            {
                "type": track.get("type"),
                "index": track.get("index"),
                "name": track.get("name"),
                "role": track.get("role"),
            }
        )
    return rows


def build_contract(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    blueprint_path = package_dir / "resolve_timeline_blueprint.json"
    audit_path = package_dir / "delivery_audit.json"
    preflight_path = package_dir / "resolve_blueprint_preflight.json"
    if not blueprint_path.exists():
        raise SystemExit(f"Missing Resolve blueprint: {blueprint_path}")
    blueprint = load_json(blueprint_path)
    audit = load_json(audit_path) if audit_path.exists() else None
    preflight = load_json(preflight_path) if preflight_path.exists() else None
    stats = clip_source_stats(blueprint)
    blockers: list[str] = []
    warnings: list[str] = []
    if stats["missingSourceFiles"]:
        blockers.append(f"{len(stats['missingSourceFiles'])} source files are missing from disk.")
    if not preflight:
        blockers.append("resolve_blueprint_preflight.json is missing. Run audit_resolve_blueprint.py first.")
    else:
        if preflight.get("status") == "blocked":
            blockers.extend(f"Resolve blueprint preflight: {item}" for item in preflight.get("blockers") or [])
        elif preflight.get("status") == "ready_with_warnings":
            warnings.extend(f"Resolve blueprint preflight: {item}" for item in preflight.get("warnings") or [])
    if not audit:
        blockers.append("delivery_audit.json is missing. Run audit_delivery_package.py first.")
    else:
        blockers.extend(audit.get("blockers") or [])
        if audit.get("status") not in {"ready_for_resolve_write", "ready_for_final_render"}:
            blockers.append(f"delivery_audit.json status is not write-ready: {audit.get('status')}")
        if audit.get("assetSummary", {}).get("unverifiedBgmOrStock"):
            blockers.append("BGM/stock/aerial asset rows are still unverified.")
        if audit.get("routeDecisionSummary", {}).get("status") not in {"approved", None}:
            warnings.append("Route decision sheet is not approved yet.")
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    pending_audio = []
    voiceover = assets.get("voiceover")
    if voiceover and not Path(str(voiceover)).expanduser().exists():
        pending_audio.append(str(voiceover))
    for bgm in assets.get("bgm", []) if isinstance(assets.get("bgm"), list) else []:
        if bgm and not Path(str(bgm)).expanduser().exists():
            pending_audio.append(str(bgm))
    if pending_audio:
        warnings.append(f"{len(pending_audio)} planned audio assets are not present yet.")
    status = "blocked" if blockers else "awaiting_user_approval"
    now = datetime.now().isoformat(timespec="seconds")
    contract = {
        "createdAt": now,
        "status": status,
        "packageDir": str(package_dir),
        "blueprint": str(blueprint_path),
        "deliveryAudit": str(audit_path) if audit else "",
        "resolveBlueprintPreflight": str(preflight_path) if preflight else "",
        "resolveBlueprintPreflightStatus": preflight.get("status") if preflight else None,
        "projectName": args.project_name or blueprint.get("projectName") or "Travel Video",
        "timelineName": args.timeline_name or blueprint.get("timelineName") or "Travel Video Master",
        "fps": blueprint.get("fps") or 25,
        "resolution": blueprint.get("resolution") or {"width": 3840, "height": 2160},
        "trackPlan": track_summary(blueprint),
        "clipPlan": stats,
        "subtitleCueCount": len(blueprint.get("subtitleCues") or []),
        "timelineMarkerCount": len(blueprint.get("timelineMarkers") or []),
        "stockPlaceholderCount": len(blueprint.get("stockInsertPlan") or []),
        "transitionCount": len(blueprint.get("transitionPlan") or []),
        "longFormCoverage": blueprint.get("longFormCoverage"),
        "coverageRatio": blueprint.get("coverageRatio"),
        "preflightSummary": {
            "status": preflight.get("status") if preflight else None,
            "clipSummary": preflight.get("clipSummary") if preflight else None,
            "enrichmentSummary": preflight.get("enrichmentSummary") if preflight else None,
        },
        "pendingAudioAssets": pending_audio,
        "writeCommand": f"python3 <skill-dir>/scripts/build_resolve_timeline.py --blueprint {blueprint_path} --apply",
        "readbackAuditCommand": (
            f"python3 <skill-dir>/scripts/audit_resolve_timeline.py "
            f"--project-name \"{args.project_name or blueprint.get('projectName') or 'Travel Video'}\" "
            f"--timeline-name \"{args.timeline_name or blueprint.get('timelineName') or 'Travel Video Master'}\" "
            f"--output {package_dir / 'resolve_audit.json'}"
        ),
        "approval": {
            "required": True,
            "approvedBy": "",
            "approvedAt": "",
            "approvedCommand": "",
            "notes": "",
        },
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "safety": {
            "writesResolve": False,
            "createsNewProject": True,
            "modifiesExistingTimelines": False,
            "queuesRender": False,
            "requiresExplicitApplyApproval": True,
        },
    }
    output_path = package_dir / "resolve_apply_contract.json"
    markdown_path = package_dir / "resolve_apply_contract.md"
    contract["contractJson"] = str(output_path)
    contract["contractMarkdown"] = str(markdown_path)
    write_json(output_path, contract)
    write_markdown(markdown_path, contract)
    return contract


def write_markdown(path: Path, contract: dict[str, Any]) -> None:
    lines = [
        "# Resolve Apply Contract",
        "",
        f"Status: `{contract['status']}`",
        f"Project: `{contract['projectName']}`",
        f"Timeline: `{contract['timelineName']}`",
        f"FPS: `{contract['fps']}`",
        f"Resolution: `{contract['resolution']}`",
        f"Coverage ratio: `{contract.get('coverageRatio')}`",
        "",
        "## Write Scope",
        "- Creates a new Resolve project/timeline from the blueprint.",
        "- Imports only referenced media paths from the blueprint.",
        "- Does not queue or start rendering.",
        "- Does not modify existing timelines.",
        "",
        "## Track Plan",
    ]
    for track in contract.get("trackPlan") or []:
        lines.append(f"- {track.get('type')} {track.get('index')}: {track.get('name') or track.get('role')}")
    lines.extend(
        [
            "",
            "## Clip Plan",
            f"- Clips: {contract['clipPlan'].get('clipCount')}",
            f"- Source files: {contract['clipPlan'].get('sourceFileCount')}",
            f"- Missing sources: {len(contract['clipPlan'].get('missingSourceFiles') or [])}",
            f"- Subtitle cues: {contract.get('subtitleCueCount')}",
            f"- Timeline markers: {contract.get('timelineMarkerCount')}",
            f"- Stock placeholders: {contract.get('stockPlaceholderCount')}",
            f"- Blueprint preflight: {contract.get('resolveBlueprintPreflightStatus')}",
            "",
            "## Commands",
            f"- Apply: `{contract['writeCommand']}`",
            f"- Readback audit: `{contract['readbackAuditCommand']}`",
            "",
            "## Blockers",
        ]
    )
    lines.extend(f"- {item}" for item in contract.get("blockers") or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in contract.get("warnings") or ["None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a Resolve --apply approval contract.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--project-name", help="Override Resolve project name for contract display.")
    parser.add_argument("--timeline-name", help="Override Resolve timeline name for contract display.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    contract = build_contract(args)
    if args.json:
        print(json.dumps(contract, ensure_ascii=False, indent=2))
    else:
        print(f"Resolve apply contract status: {contract['status']}")
        print(f"Contract JSON: {contract['contractJson']}")
        print(f"Contract Markdown: {contract['contractMarkdown']}")
        for blocker in contract.get("blockers") or []:
            print(f"BLOCKER: {blocker}")
    return 0 if contract["status"] == "awaiting_user_approval" else 2


if __name__ == "__main__":
    raise SystemExit(main())
