#!/usr/bin/env python3
"""Install the staged Travel Video Studio upgrade into the personal plugin cache."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def install(staging: Path, target: Path) -> list[str]:
    actions: list[str] = []
    if not staging.exists():
        raise FileNotFoundError(staging)
    skill_md = target / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(skill_md)

    skill_src = staging / "SKILL.md"
    if not skill_src.exists():
        skill_src = staging / "SKILL.md.installed_snapshot"
    if not skill_src.exists():
        raise FileNotFoundError(staging / "SKILL.md")

    original = skill_md.read_text(encoding="utf-8")
    backup = skill_md.with_suffix(f".md.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    backup.write_text(original, encoding="utf-8")
    shutil.copy2(skill_src, skill_md)
    actions.append(f"copied {skill_src} -> {skill_md}")

    for folder in ["references", "scripts"]:
        src_root = staging / folder
        if not src_root.exists():
            continue
        for src in sorted(src_root.rglob("*")):
            if not src.is_file():
                continue
            dst = target / src.relative_to(staging)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            actions.append(f"copied {src} -> {dst}")

    actions.append(f"backup {backup}")
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--staging",
        default="/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade",
    )
    parser.add_argument(
        "--target",
        default="/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio",
    )
    args = parser.parse_args()
    actions = install(Path(args.staging), Path(args.target))
    for action in actions:
        print(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
