#!/usr/bin/env python3
"""Audit a travel-video package for stale evidence and cross-package drift."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PASSED_STATUSES = {"passed", "passed_with_warnings", "passed_with_caveats", "ready_for_final_render", "ready_for_final_render_with_warnings"}
CORE_REPORTS = [
    "render_delivery_verification.json",
    "resolve_timeline_blueprint.json",
    "resolve_audit.json",
    "visual_audio_style_audit/visual_audio_style_audit.json",
    "bgm_audio_contract_audit.json",
    "location_truth_contract_audit.json",
    "client_delivery_rules_audit.json",
    "story_style_contract_audit.json",
    "title_bridge_contract_audit.json",
    "reference_style_alignment_audit.json",
    "director_intent_contract_audit.json",
    "route_texture_contract_audit.json",
    "stock_aerial_closure_audit.json",
    "director_polish_contract_audit.json",
    "feedback_regression_audit/feedback_regression_audit.json",
    "longform_delivery_audit.json",
    "delivery_audit.json",
]
PATH_RE = re.compile(r"(/Users/[^\"\\\n\r]+|/Volumes/[^\"\\\n\r]+|/System/[^\"\\\n\r]+)")
IGNORED_FILE_SUFFIXES = (".stale_from_v12",)
IGNORED_NAMES = {"package_integrity_audit.json", "package_integrity_audit.md"}
VOICEOVER_PATH_TOKENS = ("/voiceover/", "voiceover.m4a", "voiceover.wav", "voiceover.mp3")


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_path(value: Any) -> Path | None:
    if not value:
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except Exception:
        return None


def is_inside(path: Path | None, root: Path) -> bool:
    if not path:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def delivery_package_name(path: str) -> str | None:
    marker = "/delivery_packages/"
    if marker not in path:
        return None
    tail = path.split(marker, 1)[1]
    return tail.split("/", 1)[0]


def current_package_name(package_dir: Path) -> str:
    return package_dir.name


def report_status(data: Any) -> str | None:
    return data.get("status") if isinstance(data, dict) else None


def extract_paths_from_text(text: str) -> list[str]:
    out: list[str] = []
    for match in PATH_RE.finditer(text):
        raw = match.group(1)
        # Strip common punctuation accidentally captured from prose/commands.
        cleaned = raw.rstrip(" .,;:)'`]}")
        out.append(cleaned)
    return sorted(set(out))


def classify_external_path(path: str, package_dir: Path) -> str | None:
    current_name = current_package_name(package_dir)
    pkg_name = delivery_package_name(path)
    if pkg_name and pkg_name != current_name:
        return "other_delivery_package"
    return None


def scan_cross_package_paths(package_dir: Path, include_all_json: bool) -> list[dict[str, Any]]:
    files: list[Path] = []
    if include_all_json:
        files = sorted(package_dir.glob("**/*.json"))
    else:
        files = [package_dir / rel for rel in CORE_REPORTS]
    findings: list[dict[str, Any]] = []
    for path in files:
        if not path.exists() or path.name in IGNORED_NAMES or any(str(path).endswith(suffix) for suffix in IGNORED_FILE_SUFFIXES):
            continue
        try:
            rel = str(path.relative_to(package_dir))
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        external = []
        for raw in extract_paths_from_text(text):
            kind = classify_external_path(raw, package_dir)
            if kind:
                external.append({"path": raw, "kind": kind, "package": delivery_package_name(raw)})
        if external:
            findings.append({"file": rel, "externalPackagePaths": external[:40], "count": len(external)})
    return findings


def track_count(resolve_audit: dict[str, Any], media_type: str, index: int) -> int:
    for row in ((resolve_audit.get("tracks") or {}).get(media_type) or []):
        if row.get("index") == index:
            try:
                return int(row.get("itemCount") or 0)
            except (TypeError, ValueError):
                return 0
    items = ((resolve_audit.get("items") or {}).get(media_type) or {}).get(str(index)) or []
    return len(items) if isinstance(items, list) else 0


def named_row_passed(data: dict[str, Any], containers: tuple[str, ...], name_fragment: str) -> bool:
    needle = name_fragment.lower()
    for container in containers:
        for row in data.get(container) or []:
            text = str(row.get("name") or row.get("requirement") or "").lower()
            if needle in text and row.get("status") == "passed":
                return True
    return False


def closed_cross_package_reference(package_dir: Path, file_name: str, external: dict[str, Any]) -> dict[str, Any] | None:
    raw_path = str(external.get("path") or "")
    if file_name != "resolve_audit.json":
        return None
    if not any(token in raw_path.lower() for token in VOICEOVER_PATH_TOKENS):
        return None

    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    bgm_contract = load_json(package_dir / "bgm_audio_contract_audit.json") or {}
    story_contract = load_json(package_dir / "story_style_contract_audit.json") or {}
    a1_items = track_count(resolve_audit, "audio", 1)
    a2_items = track_count(resolve_audit, "audio", 2)
    a3_items = track_count(resolve_audit, "audio", 3)
    bgm_contract_ok = (
        bgm_contract.get("status") == "passed"
        and named_row_passed(bgm_contract, ("checks",), "Voiceover and source-camera audio are disabled")
        and named_row_passed(bgm_contract, ("checks",), "DaVinci readback has A3 BGM and no A1/A2")
    )
    story_contract_ok = (
        story_contract.get("status") == "passed"
        and named_row_passed(story_contract, ("requirements", "checks"), "No-voiceover/BGM-led audio policy")
    )
    if a1_items == 0 and a2_items == 0 and a3_items > 0 and bgm_contract_ok and story_contract_ok:
        closed = dict(external)
        closed.update(
            {
                "closure": "closed_disabled_voiceover_marker_reference",
                "evidence": {
                    "A1": a1_items,
                    "A2": a2_items,
                    "A3": a3_items,
                    "bgmAudioContract": bgm_contract.get("status"),
                    "storyStyleContract": story_contract.get("status"),
                },
            }
        )
        return closed
    return None


def close_cross_package_paths(package_dir: Path, findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    for finding in findings:
        active_external = []
        closed_external = []
        for external in finding.get("externalPackagePaths") or []:
            closure = closed_cross_package_reference(package_dir, finding["file"], external)
            if closure:
                closed_external.append(closure)
            else:
                active_external.append(external)
        if active_external:
            active.append({"file": finding["file"], "externalPackagePaths": active_external, "count": len(active_external)})
        if closed_external:
            closed.append({"file": finding["file"], "closedExternalPackagePaths": closed_external, "count": len(closed_external)})
    return active, closed


def core_report_checks(package_dir: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    def add(name: str, passed: bool, evidence: Any, *, warning: bool = False) -> None:
        status = "passed" if passed else ("warning" if warning else "blocked")
        checks.append({"name": name, "status": status, "evidence": evidence})
        if status == "blocked":
            blockers.append(name)
        elif status == "warning":
            warnings.append(name)

    render = load_json(package_dir / "render_delivery_verification.json") or {}
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    resolve_audit = load_json(package_dir / "resolve_audit.json") or {}
    final_output = as_path(render.get("output") or render.get("finalOutput"))
    add(
        "Final render evidence points at this package",
        bool(final_output and final_output.exists() and is_inside(final_output, package_dir / "renders") and render.get("status") == "passed"),
        {"output": str(final_output) if final_output else None, "renderStatus": render.get("status")},
    )
    add(
        "Resolve readback identity matches blueprint identity",
        bool(blueprint)
        and bool(resolve_audit)
        and blueprint.get("projectName") == resolve_audit.get("projectName")
        and blueprint.get("timelineName") == resolve_audit.get("timelineName"),
        {
            "blueprintProject": blueprint.get("projectName"),
            "readbackProject": resolve_audit.get("projectName"),
            "blueprintTimeline": blueprint.get("timelineName"),
            "readbackTimeline": resolve_audit.get("timelineName"),
        },
    )
    for rel in CORE_REPORTS:
        path = package_dir / rel
        data = load_json(path)
        if not path.exists():
            add(f"Core report exists: {rel}", False, {"path": str(path)}, warning=True)
            continue
        status = report_status(data)
        if status:
            add(
                f"Core report status acceptable: {rel}",
                status in PASSED_STATUSES,
                {"status": status, "path": str(path)},
                warning=rel == "delivery_audit.json" and status == "ready_for_final_render_with_warnings",
            )
    return checks, blockers, warnings


def build_report(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    checks, blockers, warnings = core_report_checks(package_dir)
    core_cross_paths = scan_cross_package_paths(package_dir, include_all_json=False)
    active_core_cross_paths, closed_core_cross_paths = close_cross_package_paths(package_dir, core_cross_paths)
    all_cross_paths = scan_cross_package_paths(package_dir, include_all_json=args.include_all_json)

    critical_cross = []
    for finding in active_core_cross_paths:
        file_name = finding["file"]
        external = finding["externalPackagePaths"]
        if file_name in {
            "render_delivery_verification.json",
            "resolve_audit.json",
            "visual_audio_style_audit/visual_audio_style_audit.json",
            "feedback_regression_audit/feedback_regression_audit.json",
            "reference_style_alignment_audit.json",
        }:
            # These reports may cite sidecar subtitles or references, but final output/readback identities are checked separately.
            continue
        critical_cross.append({"file": file_name, "externalPackagePaths": external, "count": finding["count"]})

    if active_core_cross_paths:
        warnings.append("Core reports contain cross-package paths; review whether they are reusable assets or stale evidence.")
    if critical_cross and args.strict_portable:
        blockers.append("Strict portable handoff forbids cross-package paths in core package reports.")
    elif critical_cross:
        warnings.append("Core package reports contain cross-package dependencies; copy/materialize assets before portable handoff.")

    if all_cross_paths and args.include_all_json:
        warnings.append("Some non-core JSON artifacts contain historical cross-package paths; ignore archived files or refresh before handoff.")

    status = "blocked" if blockers else ("passed_with_warnings" if warnings else "passed")
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "strictPortable": args.strict_portable,
        "includeAllJson": args.include_all_json,
        "summary": {
            "coreCrossPackagePathCount": sum(item["count"] for item in core_cross_paths),
            "activeCoreCrossPackagePathCount": sum(item["count"] for item in active_core_cross_paths),
            "closedCoreCrossPackagePathCount": sum(item["count"] for item in closed_core_cross_paths),
            "criticalCrossPackagePathCount": sum(item["count"] for item in critical_cross),
        },
        "checks": checks,
        "coreCrossPackagePaths": core_cross_paths,
        "activeCoreCrossPackagePaths": active_core_cross_paths,
        "closedCoreCrossPackagePaths": closed_core_cross_paths,
        "criticalCrossPackagePaths": critical_cross,
        "allJsonCrossPackagePathCount": sum(item["count"] for item in all_cross_paths),
        "allJsonCrossPackageFiles": [{"file": item["file"], "count": item["count"]} for item in all_cross_paths[:80]],
        "blockers": blockers,
        "warnings": warnings,
        "interpretation": {
            "passed": "Core render/readback/QA evidence is coherent for this package.",
            "passed_with_warnings": "The current render can be valid, but some sidecar/report paths still point outside this package. Materialize assets before portable handoff.",
            "blocked": "Package identity or strict portability is not proven.",
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Package Integrity Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Strict portable: `{report['strictPortable']}`",
        "",
        "## Checks",
    ]
    for row in report["checks"]:
        lines.extend(
            [
                "",
                f"### {row['name']}",
                f"- Status: `{row['status']}`",
                f"- Evidence: `{json.dumps(row['evidence'], ensure_ascii=False)[:1500]}`",
            ]
        )
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in report["warnings"])
    if report.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in report["blockers"])
    if report.get("criticalCrossPackagePaths"):
        lines.extend(["", "## Critical Cross-Package Paths"])
        for item in report["criticalCrossPackagePaths"][:40]:
            lines.append(f"- `{item['file']}`: `{item['count']}` paths")
    if report.get("closedCoreCrossPackagePaths"):
        lines.extend(["", "## Closed Cross-Package References"])
        for item in report["closedCoreCrossPackagePaths"][:40]:
            lines.append(f"- `{item['file']}`: `{item['count']}` closed paths")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit package freshness, identity, and stale cross-package references.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--strict-portable", action="store_true")
    parser.add_argument("--include-all-json", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = build_report(Path(args.package_dir), args)
    except Exception as exc:
        print(f"audit_package_integrity failed: {exc}", file=sys.stderr)
        return 1
    package_dir = Path(args.package_dir).expanduser().resolve()
    json_path = package_dir / "package_integrity_audit.json"
    md_path = package_dir / "package_integrity_audit.md"
    write_json(json_path, report)
    write_markdown(md_path, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "blockers": report["blockers"], "warnings": report["warnings"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
