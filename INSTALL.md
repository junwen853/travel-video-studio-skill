# Install Travel Video Studio Skill

This is a portable Agent Skill. Install it into Codex, Claude Code, Hermes, OpenClaw, or another local agent's skill directory, then start a new thread/session if the skill list does not refresh.

## Install With The Cross-Agent Installer

From this repository:

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

Install into a project-local Claude Code target:

```bash
python3 scripts/install_for_agent.py \
  --agent claude-code \
  --scope project \
  --project-dir /path/to/project
```

Use a custom target if your runtime stores skills somewhere else:

```bash
python3 scripts/install_for_agent.py \
  --agent claude-code \
  --target /custom/skills/travel-video-studio
```

## Install From Release

```bash
mkdir -p ~/.codex/skills/travel-video-studio
curl -L -o /tmp/travel-video-studio-skill-v0.1.14.tar.gz \
  https://github.com/junwen853/travel-video-studio-skill/releases/download/v0.1.14/travel-video-studio-skill-v0.1.14.tar.gz
tar -xzf /tmp/travel-video-studio-skill-v0.1.14.tar.gz --strip-components=1 -C ~/.codex/skills/travel-video-studio
```

## Install From Source

```bash
git clone https://github.com/junwen853/travel-video-studio-skill.git ~/.codex/skills/travel-video-studio
```

Update later with:

```bash
cd ~/.codex/skills/travel-video-studio
git pull
```

## Install From A Local Checkout

From this repository:

```bash
python3 scripts/install_into_plugin.py
```

The default target is:

```text
~/.codex/skills/travel-video-studio
```

Use a custom target if needed:

```bash
python3 scripts/install_into_plugin.py \
  --target "$CODEX_HOME/skills/travel-video-studio"
```

## Configure Project Defaults

Optional but useful:

```bash
export VIDEO_CLAW_STUDIO_DIR="$HOME/Pictures/Video-make/video-claw-studio"
export TRAVEL_VIDEO_REFERENCE="/path/to/reference-travel-film.mp4"
```

`VIDEO_CLAW_STUDIO_DIR` lets helper scripts find your default VideoClaw Studio app or project root. `TRAVEL_VIDEO_REFERENCE` is only used when you explicitly run reference analysis.

## Verify

```bash
python3 -m py_compile ~/.codex/skills/travel-video-studio/scripts/*.py
python3 ~/.codex/skills/travel-video-studio/scripts/check_project_state.py \
  --project-dir "$VIDEO_CLAW_STUDIO_DIR"
```

Use in Codex:

```text
Use $travel-video-studio to inspect /Volumes/TravelDrive/MyTrip.
Do not modify source media. Build a route-aware DaVinci delivery package
with BGM-only audio, TXT/SRT captions, scenic bridges, and final V14 QA.
```
