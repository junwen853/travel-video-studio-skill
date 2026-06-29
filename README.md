# Travel Video Studio Skill

Turn unordered travel footage into a route-aware long-form edit package for DaVinci Resolve.

This is a portable Agent Skill for Codex, Claude Code, Hermes, OpenClaw/Lobster-style workflows, and any local coding agent that can read a `SKILL.md` skill folder. It handles the messy real-world case: a drive full of phone, DJI, action-cam, and camera videos with no GPS metadata, inconsistent folders, mixed portrait/landscape clips, unclear route order, missing BGM, and a user who wants a polished travel film instead of a raw montage.

## What It Does

- Scans local or external-drive footage without modifying source media.
- Extracts and reviews representative frames so Codex can identify likely filming locations from visual evidence.
- Reconstructs a trip route from unordered clips, folder names, dates, OCR/signage evidence, and optional cloud or local recognition passes.
- Scores and tiers raw footage before first assembly, so large folders are cut from hero/main/texture bridge candidates instead of filename order.
- Plans the first three minutes as a real opening story: viewer promise, destination proof, clean title, practical arrival, lived-in texture, and first handoff.
- Plans each chapter as a complete vlog arc: context, movement, lived-in texture, destination payoff, and aftertaste/handoff before rhythm or Resolve trust.
- Builds recognition reports, route reviews, route decision sheets, and delivery packages.
- Learns from multiple local reference videos as an aggregate, non-copying batch profile.
- Plans BGM, BGM phrase cues, subtitles, city/aerial establishing shots, chapter titles, transitions, typography, visual bridge material, and restrained effect-motion candidates.
- Converts transition decisions into Resolve-ready recipes and candidate blueprint metadata, audits the whole transition motif chain, plans 2-5 shot bridge sequences, materializes those beats, and adds final BGM-hit/title-safe/motion-proven transition polish metadata into non-destructive Resolve candidate blueprints.
- Runs rhythm recut candidates from the latest BGM phrase blueprint so long-shot repairs preserve transition, effect, and music-cue metadata.
- Converts blocked reference/director/QA style gaps into concrete repair rows with owner scripts, required artifacts, and acceptance evidence.
- Generates DaVinci Resolve timeline blueprints and safety contracts before writing to Resolve.
- Audits final delivery quality: clean titles, no portrait regressions, BGM-only no-voiceover mode, dense title-safe subtitles, route texture, export quality, and V14 baseline maturity.

The default finishing path is DaVinci Resolve through the Resolve Python API. GUI automation is treated as a fallback, not the normal route.

## Why This Exists

The V14 baseline encoded here came from repeated failure fixes:

- No ghosted or duplicated opening titles.
- No accidental portrait clips in a 16:9 master.
- No voice or camera audio leaking under scenic/title sections when BGM-only is required.
- No empty BGM plan.
- No sparse subtitles.
- No black-card chapter jumps.
- No "AI slideshow" pacing where clips are simply stacked together.
- No stale Tokyo/Japan defaults leaking into future trips.
- No final claim without machine-readable QA.

The point is not to preserve one finished film. The point is to make the first serious draft from a new folder behave like the corrected V14 version.

## Requirements

- Codex Desktop/CLI, Claude Code, Hermes, OpenClaw, or another agent that can read a local Agent Skill folder.
- macOS recommended for DaVinci Resolve integration.
- Python 3.10 or newer.
- `ffmpeg` and `ffprobe` on PATH.
- DaVinci Resolve or DaVinci Resolve Studio for final timeline creation and render handoff.
- Optional: Tesseract OCR for local sign/station OCR.
- Optional: Ollama vision model only when explicitly requested. The normal route is Codex visual inspection plus approved cloud/API calls only when needed.

## Install

Use the cross-agent installer from a source checkout:

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

Install from the latest release asset:

```bash
mkdir -p ~/.codex/skills/travel-video-studio
curl -L -o /tmp/travel-video-studio-skill-v0.1.24.tar.gz \
  https://github.com/junwen853/travel-video-studio-skill/releases/download/v0.1.24/travel-video-studio-skill-v0.1.24.tar.gz
tar -xzf /tmp/travel-video-studio-skill-v0.1.24.tar.gz --strip-components=1 -C ~/.codex/skills/travel-video-studio
```

Or install from source:

```bash
git clone https://github.com/junwen853/travel-video-studio-skill.git ~/.codex/skills/travel-video-studio
```

If you use a custom Codex home:

```bash
export CODEX_HOME=/path/to/.codex
mkdir -p "$CODEX_HOME/skills"
git clone https://github.com/junwen853/travel-video-studio-skill.git "$CODEX_HOME/skills/travel-video-studio"
```

Restart Codex or open a new Codex thread if the skill list does not refresh immediately.

For non-Codex runtimes, install the same folder into the runtime's local skill directory. Default targets are documented in `references/agent-runtime-compatibility.md`.

## Quick Start

Set your VideoClaw Studio app or project root if you have one:

```bash
export VIDEO_CLAW_STUDIO_DIR="$HOME/Pictures/Video-make/video-claw-studio"
```

Then ask Codex:

```text
Use $travel-video-studio to inspect /Volumes/TravelDrive/2026-Japan.
Do not modify the source drive.
Identify where each video was likely filmed, reconstruct the route,
build a 20-minute DaVinci Resolve delivery package, use BGM-only,
export TXT/SRT narration, and run the full V14 QA gates before saying it is deliverable.
```

For a pure project-state check:

```bash
python3 ~/.codex/skills/travel-video-studio/scripts/check_project_state.py \
  --project-dir "$VIDEO_CLAW_STUDIO_DIR"
```

For a safe local workflow:

```bash
python3 ~/.codex/skills/travel-video-studio/scripts/run_delivery_workflow.py \
  --project-dir "$VIDEO_CLAW_STUDIO_DIR" \
  --target-duration-minutes 20
```

For an optional local reference film:

```bash
python3 ~/.codex/skills/travel-video-studio/scripts/analyze_reference_video.py \
  --reference /path/to/reference-travel-film.mp4 \
  --output-dir /path/to/delivery-package/reference
```

## Typical Output

A delivery package usually contains:

- `footage_recognition_route_report.md`
- `confirmed_route_timeline.json`
- `delivery_plan.json`
- `subtitles.srt`
- `caption_story_plan/text_only_narration_export.txt`
- `opening_story_plan/opening_story_plan.md`
- `chapter_arc_plan/chapter_arc_plan.md`
- `reference/reference_batch_profile.md`
- `bgm_sourcing/bgm_sourcing_brief.md`
- `transition_bridge_plan/transition_bridge_plan.md`
- `transition_execution_plan/transition_execution_plan.md`
- `transition_execution_blueprint/transition_execution_blueprint_report.md`
- `transition_motif_plan/transition_motif_plan.md`
- `bridge_sequence_plan/bridge_sequence_plan.md`
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.md`
- `reference_style_repair_plan/reference_style_repair_plan.md`
- `effect_motion_blueprint/effect_motion_blueprint_report.md`
- `bgm_phrase_blueprint/bgm_phrase_blueprint_report.md`
- `rhythm_recut_blueprint/rhythm_recut_blueprint_report.md`
- `transition_polish_blueprint/transition_polish_blueprint_report.md`
- `transition_quality_contract_audit.md`
- `shot_transition_boundary_contract_audit.md`
- `title_typography_plan/title_typography_plan.md`
- `cover_title_contract_audit.md`
- `raw_intake_completeness_audit.md`
- `reference_repair_closure_audit.md`
- `visual_establishing_plan/visual_establishing_plan.md`
- `resolve_timeline_blueprint.json`
- `resolve_blueprint_preflight.md`
- `render_plan.json`
- final QA reports, including `final_qa_suite_report.json` and `v14_baseline_contract_audit.json`

## DaVinci Resolve Path

The skill prefers DaVinci Resolve API control:

1. Inspect Resolve availability with `check_resolve_api.py`.
2. Build or refresh the package blueprint.
3. Run `audit_resolve_blueprint.py` before any apply.
4. Prepare `prepare_resolve_apply_contract.py`.
5. Apply only after explicit approval.
6. Read back the actual Resolve timeline.
7. Render at high quality and run final QA.

This is intentionally stricter than simply making an FFMPEG montage. The skill is designed for repeatable, auditable finishing.

## Quality Gates

A package is not considered deliverable until the relevant audits pass:

- visual/audio style audit
- BGM/audio contract
- client delivery rules
- location truth contract
- long-form delivery audit
- story style contract
- reference style alignment
- director intent contract
- route texture contract
- title bridge contract
- stock/aerial closure
- director polish contract
- feedback regression audit
- package integrity audit
- raw intake completeness audit
- skill maturity contract
- V14 baseline contract
- final QA suite

## Safety Rules

- Source media is read-only.
- Cloud recognition, downloads, route file writes, Resolve writes, renders, and TTS generation are approval-gated.
- Exact per-video location is never claimed from visuals alone. GPS-grade claims require GPS, user confirmation, or verified per-clip evidence.
- BGM/stock/font rows must keep source URL and license evidence for future-safe delivery.

## Repository Layout

- `SKILL.md`: Codex skill entrypoint and workflow rules.
- `references/`: editing, DaVinci, BGM, subtitles, route, and output contracts.
- `scripts/`: executable helpers and audit gates.
- `examples/`: public summaries and release notes, without private project paths.

## Validate The Skill

```bash
python3 -m py_compile ~/.codex/skills/travel-video-studio/scripts/*.py
python3 ~/.codex/skills/travel-video-studio/scripts/audit_v14_baseline_contract.py \
  --package-dir /path/to/delivery-package \
  --skill-dir ~/.codex/skills/travel-video-studio
```

For a full final package:

```bash
python3 ~/.codex/skills/travel-video-studio/scripts/run_final_qa_suite.py \
  --package-dir /path/to/delivery-package \
  --skill-dir ~/.codex/skills/travel-video-studio
```

## License

MIT. See `LICENSE`.
