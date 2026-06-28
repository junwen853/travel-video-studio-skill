# Install Travel Video Studio Skill

This is a Codex skill. Install it into your Codex skills directory, then start a new Codex thread or restart Codex if the skill list does not refresh.

## Install From Release

```bash
mkdir -p ~/.codex/skills/travel-video-studio
curl -L -o /tmp/travel-video-studio-skill-v0.1.0.tar.gz \
  https://github.com/junwen853/travel-video-studio-skill/releases/download/v0.1.0/travel-video-studio-skill-v0.1.0.tar.gz
tar -xzf /tmp/travel-video-studio-skill-v0.1.0.tar.gz --strip-components=1 -C ~/.codex/skills/travel-video-studio
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
