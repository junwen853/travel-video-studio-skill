#!/usr/bin/env python3
"""Install Travel Video Studio for Codex, Claude Code, Hermes, or OpenClaw."""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SKILL_NAME = "travel-video-studio"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "qa",
    "delivery_packages",
    "outputs",
    "renders",
    "frames",
    "ocr_frames",
    "sample_frames",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".mp4",
    ".mov",
    ".m4v",
    ".mkv",
    ".avi",
    ".wav",
    ".m4a",
    ".mp3",
}

INCLUDE_FILES = ("SKILL.md", "LICENSE", "README.md", "INSTALL.md")
INCLUDE_DIRS = ("references", "scripts", "examples")


@dataclass(frozen=True)
class AgentTarget:
    name: str
    env_home: str
    default_home: str
    skills_parts: tuple[str, ...] = ("skills",)
    project_parts: tuple[str, ...] | None = None

    def user_target(self) -> Path:
        home = Path(os.environ.get(self.env_home, self.default_home)).expanduser()
        return home.joinpath(*self.skills_parts, SKILL_NAME)

    def project_target(self, project_dir: Path) -> Path:
        parts = self.project_parts or (f".{self.name}", *self.skills_parts)
        return project_dir.joinpath(*parts, SKILL_NAME)


TARGETS: dict[str, AgentTarget] = {
    "codex": AgentTarget("codex", "CODEX_HOME", "~/.codex"),
    "claude-code": AgentTarget("claude", "CLAUDE_HOME", "~/.claude"),
    "hermes": AgentTarget("hermes", "HERMES_HOME", "~/.hermes"),
    "openclaw": AgentTarget("openclaw", "OPENCLAW_HOME", "~/.openclaw", ("skills",), ("skills",)),
}

ALIASES = {
    "claude": "claude-code",
    "claude-code": "claude-code",
    "codex": "codex",
    "hermes": "hermes",
    "openclaw": "openclaw",
    "claw": "openclaw",
    "openclaw-workspace": "openclaw",
    "lobster": "openclaw",
    "crayfish": "openclaw",
    "xiaolongxia": "openclaw",
    "小龙虾": "openclaw",
}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if path.name == ".DS_Store":
        return True
    return False


def iter_sources(source: Path) -> list[Path]:
    paths: list[Path] = []
    for name in INCLUDE_FILES:
        path = source / name
        if path.exists() and path.is_file():
            paths.append(path)
    for dirname in INCLUDE_DIRS:
        root = source / dirname
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and not should_skip(path.relative_to(source)):
                paths.append(path)
    return paths


def backup_existing(dst: Path) -> Path | None:
    if not dst.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = dst.with_name(f"{dst.name}.bak-{timestamp}")
    shutil.copy2(dst, backup)
    return backup


def copy_skill(source: Path, target: Path, dry_run: bool = False, backup: bool = True) -> list[str]:
    if not (source / "SKILL.md").exists():
        raise FileNotFoundError(source / "SKILL.md")

    actions: list[str] = []
    for src in iter_sources(source):
        rel = src.relative_to(source)
        dst = target / rel
        actions.append(f"copy {rel} -> {dst}")
        if dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if backup and dst.name == "SKILL.md":
            bak = backup_existing(dst)
            if bak:
                actions.append(f"backup {dst} -> {bak}")
        shutil.copy2(src, dst)
    return actions


def resolve_targets(agent: str, scope: str, project_dir: Path | None, custom_target: str | None) -> list[tuple[str, Path]]:
    if custom_target:
        return [(agent, Path(custom_target).expanduser())]

    if agent == "all":
        agents = ["codex", "claude-code", "hermes", "openclaw"]
    else:
        agents = [ALIASES.get(agent, agent)]

    resolved: list[tuple[str, Path]] = []
    for item in agents:
        if item not in TARGETS:
            raise ValueError(f"Unsupported agent: {item}")
        target = TARGETS[item]
        if scope == "project":
            if not project_dir:
                raise ValueError("--project-dir is required for --scope project")
            resolved.append((item, target.project_target(project_dir.expanduser().resolve())))
        else:
            resolved.append((item, target.user_target()))
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument(
        "--agent",
        default="codex",
        help="codex, claude-code, hermes, openclaw, lobster, or all",
    )
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-dir")
    parser.add_argument("--target", help="Exact target folder; overrides agent/scope defaults.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    project_dir = Path(args.project_dir) if args.project_dir else None
    targets = resolve_targets(args.agent, args.scope, project_dir, args.target)

    for agent, target in targets:
        print(f"[{agent}] {target}")
        actions = copy_skill(source, target, dry_run=args.dry_run, backup=not args.no_backup)
        for action in actions:
            print(f"  {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
