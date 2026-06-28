#!/usr/bin/env python3
"""Install Travel Video Studio into a local Codex skills directory."""

from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def install(staging: Path, target: Path) -> list[str]:
    actions: list[str] = []
    if not staging.exists():
        raise FileNotFoundError(staging)
    target.mkdir(parents=True, exist_ok=True)
    skill_md = target / "SKILL.md"

    skill_src = staging / "SKILL.md"
    if not skill_src.exists():
        raise FileNotFoundError(staging / "SKILL.md")

    backup = None
    if skill_md.exists():
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

    if backup:
        actions.append(f"backup {backup}")
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--staging",
        default=str(Path(__file__).resolve().parents[1]),
    )
    parser.add_argument(
        "--target",
        default=str(default_codex_home() / "skills" / "travel-video-studio"),
    )
    args = parser.parse_args()
    actions = install(Path(args.staging), Path(args.target))
    for action in actions:
        print(action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
