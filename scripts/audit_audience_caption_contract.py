#!/usr/bin/env python3
"""Audit that final captions/narration are audience-facing, not editor reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from audience_text_policy import file_violations


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def candidate_text_files(package_dir: Path, extra_files: list[str]) -> list[Path]:
    blueprint = load_json(package_dir / "resolve_timeline_blueprint.json") or {}
    assets = blueprint.get("assets") if isinstance(blueprint.get("assets"), dict) else {}
    candidates: list[Path] = []
    if assets.get("subtitles"):
        candidates.append(Path(str(assets["subtitles"])).expanduser())
    candidates.extend(sorted(package_dir.glob("subtitles*.srt")))
    candidates.extend(sorted(package_dir.glob("subtitles*_dense.srt")))
    candidates.extend(
        [
            package_dir / "voiceover_script.txt",
            package_dir / "narration.txt",
            package_dir / "caption_story_plan" / "text_only_narration_export.txt",
        ]
    )
    candidates.extend(Path(item).expanduser() for item in extra_files)
    unique: dict[str, Path] = {}
    for path in candidates:
        if path.exists() and path.is_file():
            unique[str(path.resolve())] = path.resolve()
    return sorted(unique.values(), key=lambda path: str(path))


def build_report(package_dir: Path, extra_files: list[str]) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    files = candidate_text_files(package_dir, extra_files)
    violations: list[dict[str, Any]] = []
    for path in files:
        violations.extend(file_violations(path))
    status = "blocked" if violations or not files else "passed"
    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "checkedFiles": [str(path) for path in files],
        "checkedFileCount": len(files),
        "violationCount": len(violations),
        "violations": violations[:100],
        "policy": {
            "audienceFacingOnly": True,
            "forbidden": [
                "Do not tell the user what was edited, fixed, removed, exported, rendered, or QA-checked.",
                "Do not expose tool names, version labels, track names, delivery-package state, or workflow status.",
                "Captions and TXT narration must read like travel-film text the viewer can see on screen.",
            ],
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Audience Caption Contract Audit",
        "",
        f"Status: `{report['status']}`",
        f"Package: `{report['packageDir']}`",
        f"Checked files: `{report['checkedFileCount']}`",
        f"Violations: `{report['violationCount']}`",
        "",
        "## Checked Files",
    ]
    lines.extend(f"- `{item}`" for item in report["checkedFiles"])
    if report["violations"]:
        lines.extend(["", "## Violations"])
        for row in report["violations"]:
            lines.append(f"- `{row['path']}` item `{row['index']}` rule `{row['rule']}` match `{row['match']}`")
    lines.extend(["", "## Policy"])
    lines.extend(f"- {item}" for item in report["policy"]["forbidden"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit final subtitles/TXT narration for audience-facing language.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--extra-file", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    package_dir = Path(args.package_dir).expanduser().resolve()
    report = build_report(package_dir, args.extra_file)
    write_json(package_dir / "audience_caption_contract_audit.json", report)
    write_markdown(package_dir / "audience_caption_contract_audit.md", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": report["status"], "violationCount": report["violationCount"]}, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
