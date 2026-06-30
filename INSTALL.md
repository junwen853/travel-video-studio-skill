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
curl -L -o /tmp/travel-video-studio-skill-v0.1.80.tar.gz \
  https://github.com/junwen853/travel-video-studio-skill/releases/download/v0.1.80/travel-video-studio-skill-v0.1.80.tar.gz
tar -xzf /tmp/travel-video-studio-skill-v0.1.80.tar.gz --strip-components=1 -C ~/.codex/skills/travel-video-studio
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
test -f ~/.codex/skills/travel-video-studio/scripts/audit_rhythm_recut_application_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_effect_motion_application_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_reference_profile_application_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_reference_transition_profile_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_large_source_unattended_readiness_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/prepare_transition_reference_candidates.py
test -f ~/.codex/skills/travel-video-studio/scripts/prepare_transition_reference_selection.py
test -f ~/.codex/skills/travel-video-studio/scripts/prepare_transition_preview_packet.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_preview_quality_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/prepare_transition_audition_packet.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_audition_quality_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_audition_visual_proof_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_audition_role_integrity_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_motion_direction_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_motion_accent_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_cutpoint_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_action_anchor_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_sensory_continuity_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_storyboard_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_breathing_room_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_scene_flow_arc_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_final_cut_smoothness_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_continuity_rehearsal_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_pacing_watchability_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_narrative_adjacency_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_motif_coherence_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_viewer_orientation_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_scene_settlement_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/prepare_unattended_repair_queue.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_chapter_story_spine_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_shot_flow_continuity_contract.py
test -f ~/.codex/skills/travel-video-studio/scripts/audit_transition_bridge_visual_evidence_contract.py
test -f ~/.codex/skills/travel-video-studio/references/reference-profile-application-contract.md
test -f ~/.codex/skills/travel-video-studio/references/reference-transition-profile-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-reference-candidate-engine.md
test -f ~/.codex/skills/travel-video-studio/references/transition-reference-selection-engine.md
test -f ~/.codex/skills/travel-video-studio/references/chapter-story-spine-contract.md
test -f ~/.codex/skills/travel-video-studio/references/shot-flow-continuity-contract.md
test -f ~/.codex/skills/travel-video-studio/references/large-source-unattended-readiness-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-preview-packet-engine.md
test -f ~/.codex/skills/travel-video-studio/references/transition-preview-quality-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-audition-packet-engine.md
test -f ~/.codex/skills/travel-video-studio/references/transition-audition-quality-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-audition-visual-proof-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-audition-role-integrity-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-motion-direction-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-motion-accent-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-cutpoint-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-action-anchor-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-sensory-continuity-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-storyboard-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-breathing-room-contract.md
test -f ~/.codex/skills/travel-video-studio/references/scene-flow-arc-contract.md
test -f ~/.codex/skills/travel-video-studio/references/final-cut-smoothness-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-continuity-rehearsal-contract.md
test -f ~/.codex/skills/travel-video-studio/references/pacing-watchability-contract.md
test -f ~/.codex/skills/travel-video-studio/references/narrative-adjacency-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-motif-coherence-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-viewer-orientation-contract.md
test -f ~/.codex/skills/travel-video-studio/references/transition-scene-settlement-contract.md
test -f ~/.codex/skills/travel-video-studio/references/unattended-repair-queue-engine.md
test -f ~/.codex/skills/travel-video-studio/references/transition-bridge-visual-evidence-contract.md
python3 ~/.codex/skills/travel-video-studio/scripts/check_project_state.py \
  --project-dir "$VIDEO_CLAW_STUDIO_DIR"
```

Use in Codex:

```text
Use $travel-video-studio to inspect /Volumes/TravelDrive/MyTrip.
Do not modify source media. Build a route-aware DaVinci delivery package
with BGM-only audio, TXT/SRT captions, scenic bridges, and final V14 QA.
```
