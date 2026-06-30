# Agent Runtime Compatibility

This skill is authored in the portable Agent Skills layout: one `SKILL.md` entrypoint plus optional `references/`, `scripts/`, and `examples/` resources. Keep `SKILL.md` as the single source of truth for the travel-video workflow; compatibility files must only explain how another agent runtime locates and runs the same skill.

## Supported Runtime Targets

| Runtime | Default user install target | Notes |
| --- | --- | --- |
| Codex | `~/.codex/skills/travel-video-studio` | Primary supported runtime. `$CODEX_HOME` overrides `~/.codex`. |
| Claude Code | `~/.claude/skills/travel-video-studio` | Use the same `SKILL.md`; invoke it by name or by asking Claude Code to use the local skill folder. |
| Hermes | `~/.hermes/skills/travel-video-studio` | Hermes advertises Agent Skills compatibility; keep the folder shape unchanged. |
| OpenClaw / Lobster workflows | `~/.openclaw/skills/travel-video-studio` | Use the same skill folder and scripts. Lobster is treated as an OpenClaw execution surface, not a separate skill format. |
| OpenClaw workspace | `<workspace>/skills/travel-video-studio` | Use `--scope project --project-dir <workspace>` for workspace-local installs. |
| Generic agent | any local folder | Point the agent at `SKILL.md` and tell it to treat `<skill-dir>` as that folder. |

Use `scripts/install_for_agent.py` to copy the skill into these targets without changing the workflow content.

## Runtime Rules

- Resolve `<skill-dir>` to the installed folder for the current runtime before running helper commands.
- Keep source media read-only and keep the existing approval gates for cloud calls, downloads, Resolve writes, renders, and TTS.
- Prefer the bundled scripts for deterministic checks, regardless of agent runtime.
- Do not add runtime-specific edits to the core travel-video rules unless the behavior is also valid for Codex.
- Do not expose Codex-only final-response directives when operating under another agent. Report git, render, and QA status in plain text unless that runtime defines its own directive syntax.

## Install Commands

```bash
python3 scripts/install_for_agent.py --agent codex
python3 scripts/install_for_agent.py --agent claude-code
python3 scripts/install_for_agent.py --agent hermes
python3 scripts/install_for_agent.py --agent openclaw
python3 scripts/install_for_agent.py --agent lobster
```

Install into every known user-level target:

```bash
python3 scripts/install_for_agent.py --agent all
```

Install into a project/workspace-local target:

```bash
python3 scripts/install_for_agent.py --agent claude-code --scope project --project-dir /path/to/project
python3 scripts/install_for_agent.py --agent openclaw --scope project --project-dir /path/to/workspace
```

Use `--target /custom/path/travel-video-studio` when a runtime has a different local skills directory.

## Portability Checklist

- `SKILL.md` exists at the installed folder root.
- `references/` and `scripts/` are copied with no `__pycache__`, `.pyc`, media, QA, or private output artifacts.
- Python scripts compile on the target machine.
- `ffmpeg` and `ffprobe` are available before media scanning or rendering.
- DaVinci Resolve API checks pass before using the Resolve finishing path.
