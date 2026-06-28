#!/usr/bin/env python3
"""Prepare an auditable BGM selection and build package."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


DECISION_FIELDS = {
    "selectedForFinalBed": False,
    "selectionRole": "",
    "approvedAssetTitle": "",
    "approvedAssetUrl": "",
    "approvedLicenseUrl": "",
    "approvedLocalPath": "",
    "durationSeconds": None,
    "loopOrCrossfadePlan": "",
    "attributionRequired": None,
    "attributionText": "",
    "contentIdRiskChecked": False,
    "approvedBy": "",
    "approvedAt": "",
    "editorNotes": "",
}


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


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ffprobe_duration(path: Path) -> float | None:
    if not path.exists():
        return None
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
        return float((payload.get("format") or {}).get("duration") or 0)
    except Exception:
        return None


def target_duration(package_dir: Path, blueprint: dict[str, Any], bgm_manifest: dict[str, Any]) -> float:
    for value in (
        bgm_manifest.get("durationTargetSeconds"),
        blueprint.get("targetDurationSeconds"),
        blueprint.get("actualVideoCoverageSeconds"),
    ):
        try:
            number = float(value)
            if number > 0:
                return number
        except (TypeError, ValueError):
            pass
    render = load_json(package_dir / "render_delivery_verification.json") or {}
    try:
        return float(render.get("durationSeconds") or 20 * 60.0)
    except (TypeError, ValueError):
        return 20 * 60.0


def unique_by_path(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("localPath") or row.get("path") or row.get("selectedAssetUrl") or row.get("name") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def blueprint_bgm_assets(blueprint: dict[str, Any]) -> list[str]:
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    rows = assets.get("bgm") if isinstance(assets.get("bgm"), list) else []
    return [str(item) for item in rows if item]


def bgm_cues(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    audio = blueprint.get("audioPlan") if isinstance(blueprint.get("audioPlan"), dict) else {}
    rows = audio.get("bgmCues") if isinstance(audio.get("bgmCues"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def ledger_bgm_items(package_dir: Path) -> list[dict[str, Any]]:
    ledger = load_json(package_dir / "asset_ledger" / "asset_license_ledger.json") or {}
    rows = ledger.get("items") if isinstance(ledger.get("items"), list) else []
    return [row for row in rows if isinstance(row, dict) and row.get("type") == "bgm"]


def manifest_bgm_rows(bgm_manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    output = bgm_manifest.get("output")
    output_row = None
    if output:
        output_path = Path(str(output)).expanduser()
        output_row = {
            "source": "bgm_manifest_output",
            "name": output_path.stem,
            "localPath": str(output_path),
            "licenseUrl": next((track.get("license") for track in bgm_manifest.get("tracks") or [] if isinstance(track, dict) and track.get("license")), ""),
            "durationSeconds": ffprobe_duration(output_path),
            "role": "materialized_continuous_bed",
        }
    track_rows: list[dict[str, Any]] = []
    for track in bgm_manifest.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        path = Path(str(track.get("path") or "")).expanduser()
        track_rows.append(
            {
                "source": "bgm_manifest_track",
                "name": track.get("name") or path.stem,
                "artist": track.get("artist"),
                "genre": track.get("genre"),
                "localPath": str(path) if str(path) else "",
                "licenseUrl": track.get("license"),
                "durationSeconds": ffprobe_duration(path),
                "role": "source_component_track",
            }
        )
    return output_row, unique_by_path(track_rows)


def normalize_candidate(row: dict[str, Any], target_seconds: float, blueprint_assets: list[str]) -> dict[str, Any]:
    local = Path(str(row.get("localPath") or row.get("path") or "")).expanduser()
    exists = local.exists() if str(local) else False
    duration = row.get("durationSeconds")
    if duration is None and exists:
        duration = ffprobe_duration(local)
    license_url = str(row.get("licenseUrl") or row.get("license") or row.get("selectedAssetUrl") or "")
    role = str(row.get("role") or row.get("selectionRole") or "")
    decision = dict(DECISION_FIELDS)
    decision.update(
        {
            "selectedForFinalBed": role == "materialized_continuous_bed" and exists,
            "selectionRole": role,
            "approvedAssetTitle": row.get("name") or "",
            "approvedAssetUrl": row.get("selectedAssetUrl") or "",
            "approvedLicenseUrl": license_url,
            "approvedLocalPath": str(local) if exists else str(row.get("localPath") or ""),
            "durationSeconds": duration,
            "loopOrCrossfadePlan": "Use build_bgm_bed.py to crossfade source tracks into a full-duration A3 bed." if role == "source_component_track" else "Use as the full continuous BGM bed if duration covers the target.",
            "contentIdRiskChecked": bool(row.get("contentIdRiskChecked")),
        }
    )
    return {
        "source": row.get("source"),
        "name": row.get("name"),
        "artist": row.get("artist"),
        "genre": row.get("genre"),
        "role": role,
        "localPath": str(local) if str(row.get("localPath") or row.get("path") or "") else "",
        "localPathExists": exists,
        "licenseUrl": license_url,
        "licenseUrlPresent": license_url.startswith(("http://", "https://")),
        "durationSeconds": duration,
        "coversTargetDuration": bool(duration and float(duration) >= target_seconds * 0.98),
        "referencedByBlueprint": str(local) in blueprint_assets,
        "decision": decision,
    }


def write_track_manifest(path: Path, source_tracks: list[dict[str, Any]]) -> Path | None:
    ready = [
        {
            "path": row["localPath"],
            "name": row.get("name"),
            "artist": row.get("artist"),
            "genre": row.get("genre"),
            "license": row.get("licenseUrl"),
        }
        for row in source_tracks
        if row.get("localPathExists") and row.get("licenseUrlPresent")
    ]
    if not ready:
        return None
    output = path / "track_manifest_for_build_bed.json"
    write_json(output, {"tracks": ready})
    return output


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "bgm_selection_package"
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    sourcing = load_json(package_dir / "bgm_sourcing" / "bgm_sourcing_brief.json") or {}
    bgm_manifest_path = Path(str(args.bgm_manifest)).expanduser() if args.bgm_manifest else package_dir / "bgm" / "v9_bgm_manifest.json"
    bgm_manifest = load_json(bgm_manifest_path) or {}
    target_seconds = target_duration(package_dir, blueprint, bgm_manifest)
    blueprint_assets = blueprint_bgm_assets(blueprint)
    output_row, source_tracks = manifest_bgm_rows(bgm_manifest)
    raw_candidates: list[dict[str, Any]] = []
    if output_row:
        raw_candidates.append(output_row)
    raw_candidates.extend(source_tracks)
    for item in ledger_bgm_items(package_dir):
        raw_candidates.append(
            {
                "source": "asset_ledger",
                "name": item.get("name"),
                "localPath": item.get("localPath"),
                "selectedAssetUrl": item.get("selectedAssetUrl"),
                "licenseUrl": item.get("selectedAssetUrl"),
                "role": "ledger_verified_bgm" if str(item.get("licenseStatus") or "").startswith("verified") else "ledger_bgm_candidate",
                "contentIdRiskChecked": item.get("contentIdRiskChecked"),
            }
        )
    candidates = [normalize_candidate(row, target_seconds, blueprint_assets) for row in unique_by_path(raw_candidates)]
    materialized_beds = [row for row in candidates if row["role"] == "materialized_continuous_bed"]
    verified_beds = [
        row
        for row in materialized_beds
        if row["localPathExists"]
        and row["licenseUrlPresent"]
        and row["coversTargetDuration"]
        and row["referencedByBlueprint"]
    ]
    ready_source_tracks = [
        row for row in candidates if row["role"] == "source_component_track" and row["localPathExists"] and row["licenseUrlPresent"]
    ]
    track_manifest = write_track_manifest(output_dir, ready_source_tracks)
    bgm_output = output_dir / "rebuilt_bgm_bed.m4a"
    build_command = None
    if track_manifest:
        build_command = [
            "python3",
            str(Path(__file__).resolve().parent / "build_bgm_bed.py"),
            "--track-manifest",
            str(track_manifest),
            "--output",
            str(bgm_output),
            "--duration",
            f"{target_seconds:.3f}",
            "--manifest-output",
            str(output_dir / "rebuilt_bgm_bed_manifest.json"),
        ]
    status = "ready_with_materialized_bgm_selection_package" if verified_beds else "needs_bgm_selection_or_materialization"
    section_plan = sourcing.get("sectionPlan") if isinstance(sourcing.get("sectionPlan"), list) else []
    chapter_rows = sourcing.get("chapterBgmRows") if isinstance(sourcing.get("chapterBgmRows"), list) else []
    report = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "outputDir": str(output_dir),
        "inputs": {
            "bgmSourcingBrief": str(package_dir / "bgm_sourcing" / "bgm_sourcing_brief.json"),
            "bgmManifest": str(bgm_manifest_path),
            "assetLedger": str(package_dir / "asset_ledger" / "asset_license_ledger.json"),
            "resolveBlueprint": str(package_dir / "resolve_timeline_blueprint.json"),
        },
        "summary": {
            "targetDurationSeconds": target_seconds,
            "candidateCount": len(candidates),
            "materializedBedCount": len(materialized_beds),
            "verifiedMaterializedBedCount": len(verified_beds),
            "readySourceTrackCount": len(ready_source_tracks),
            "blueprintBgmAssetCount": len(blueprint_assets),
            "bgmCueCount": len(bgm_cues(blueprint)),
            "sectionPlanCount": len(section_plan),
            "chapterBgmRowCount": len(chapter_rows),
            "trackManifestForBuildBed": str(track_manifest) if track_manifest else None,
            "buildCommandAvailable": build_command is not None,
        },
        "selectedMaterializedBeds": verified_beds,
        "candidateRows": candidates,
        "sectionPlan": section_plan,
        "chapterBgmRows": chapter_rows,
        "commands": {
            "buildBgmBed": build_command,
            "nextAudit": [
                "python3",
                str(Path(__file__).resolve().parent / "audit_bgm_audio_contract.py"),
                "--package-dir",
                str(package_dir),
                "--audio-mode",
                "bgm_only",
            ],
        },
        "policy": {
            "purpose": "Make BGM selection, license evidence, local files, and bed-building commands auditable before Resolve writes.",
            "downloadsExternalAssets": False,
            "writesResolve": False,
            "queuesRender": False,
            "modifiesSourceFootage": False,
            "requiresExactTrackUrlBeforeDownload": True,
            "requiresLicenseUrlBeforeUse": True,
            "requiresLocalPathBeforeBuild": True,
            "requiresAudibleBgmAuditAfterRender": True,
        },
        "blockers": []
        if verified_beds
        else [
            "No materialized full-duration BGM bed is both local, license-traceable, target-duration-covering, and referenced by the active Resolve blueprint."
        ],
        "nextActions": [
            "If selectedMaterializedBeds is empty, fill one candidate decision row with exact track URL, license URL, local path, and approval evidence.",
            "Run the buildBgmBed command only after the source tracks are local and license-traceable.",
            "Update bgm/v9_bgm_manifest.json, asset_ledger, and resolve_timeline_blueprint.json assets.bgm/audioPlan after a new bed is built.",
            "Run audit_bgm_audio_contract.py and final feedback/visual-audio audits after render.",
        ],
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BGM Selection Package",
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
        "## Selected Materialized Beds",
    ]
    if report["selectedMaterializedBeds"]:
        for row in report["selectedMaterializedBeds"]:
            lines.append(f"- {row.get('name')}: `{row.get('localPath')}`")
    else:
        lines.append("- None yet.")
    lines.extend(["", "## Candidate Rows"])
    for row in report["candidateRows"]:
        lines.extend(
            [
                "",
                f"### {row.get('name') or row.get('localPath')}",
                f"- Role: `{row.get('role')}`",
                f"- Local exists: `{row.get('localPathExists')}`",
                f"- License URL present: `{row.get('licenseUrlPresent')}`",
                f"- Duration: `{row.get('durationSeconds')}`",
                f"- Covers target: `{row.get('coversTargetDuration')}`",
                f"- Referenced by blueprint: `{row.get('referencedByBlueprint')}`",
            ]
        )
    lines.extend(["", "## Commands"])
    for name, command in report["commands"].items():
        if command:
            lines.extend(["", f"### {name}", "", "```bash", " ".join(str(item) for item in command), "```"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in report["nextActions"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an auditable BGM selection package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--bgm-manifest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(args)
    output_dir = Path(report["outputDir"])
    write_json(output_dir / "bgm_selection_package.json", report)
    write_markdown(output_dir / "bgm_selection_package.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "summary": report["summary"], "blockers": report["blockers"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"].startswith("needs_") else 0


if __name__ == "__main__":
    raise SystemExit(main())
