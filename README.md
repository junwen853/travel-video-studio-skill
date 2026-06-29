# Travel Video Studio Skill

Turn unordered travel footage into a route-aware long-form edit package for DaVinci Resolve.

This is a portable Agent Skill for Codex, Claude Code, Hermes, OpenClaw/Lobster-style workflows, and any local coding agent that can read a `SKILL.md` skill folder. It handles the messy real-world case: a drive full of phone, DJI, action-cam, and camera videos with no GPS metadata, inconsistent folders, mixed portrait/landscape clips, unclear route order, missing BGM, and a user who wants a polished travel film instead of a raw montage.

## What It Does

- Scans local or external-drive footage without modifying source media.
- Extracts and reviews representative frames so Codex can identify likely filming locations from visual evidence.
- Reconstructs a trip route from unordered clips, folder names, dates, OCR/signage evidence, and optional cloud or local recognition passes.
- Scores and tiers raw footage before first assembly, then audits that large folders are actually cut from full-source hero/main/texture bridge candidates instead of filename order or blueprint fallback samples.
- Audits 100GB-class unordered folders for unattended readiness, proving media-root intake, whole-folder recognition, source selection, first assembly, first-draft chain, and blueprint preflight are connected before another AI or editor takes over.
- Plans the first three minutes as a real opening story: viewer promise, destination proof, clean title, practical arrival, lived-in texture, and first handoff.
- Plans each chapter as a complete vlog arc: context, movement, lived-in texture, destination payoff, and aftertaste/handoff before rhythm or Resolve trust.
- Builds recognition reports, route reviews, route decision sheets, and delivery packages.
- Learns from multiple local reference videos as an aggregate, non-copying batch profile.
- Plans BGM, BGM phrase cues, subtitles, city/aerial establishing shots, chapter titles, transitions, typography, visual bridge material, and restrained effect-motion candidates with final application proof.
- Converts transition decisions into Resolve-ready recipes and candidate blueprint metadata, audits the whole transition motif/cadence chain, plans 2-5 shot bridge sequences, materializes those beats, proves those bridge inserts survive into the final candidate, and proves final BGM-hit/title-safe/motion-proven/pair-continuous/execution-ready transition polish metadata plus Resolve marker/readback payloads and latest candidate-chain lineage survive into the active/final Resolve blueprint.
- Runs rhythm recut candidates from the latest BGM phrase blueprint and audits final application so long-shot repairs preserve transition, effect, music-cue metadata, and actual main-segment/cutaway survival in the final candidate.
- Converts blocked reference/director/QA style gaps into concrete repair rows with owner scripts, required artifacts, and acceptance evidence.
- Audits transition execution readiness so final transitions have package-local Resolve recipes, BGM hits, title-safe windows, pair readiness, and handle evidence before Resolve apply.
- Audits effect-motion application, transition-polish application, Resolve transition materialization, and Resolve transition apply paths so active/final blueprints cannot drop restrained title/rotation/whip/speed-ramp metadata, BGM-hit/title-safe transition metadata, marker/readback payloads, or visible-effect API/manual/bridge handoff proof after candidate generation.
- Audits bridge-sequence application so planned route/title/day-change bridge beats cannot be dropped from the final candidate blueprint.
- Audits final blueprint lineage, effect-motion application, film-level transition cadence, shot-to-shot transition microstructure, whole-film transition effect palette, pair-level visual match, transition choreography, transition bridge visual evidence, transition preview quality, transition audition quality, and transition storyboard proof so the active Resolve blueprint cannot silently fall back to an old or partial candidate, bare-cut montage, repeated-template chain, effect-spam transition rhythm, one dominant motif, arbitrary adjacent-pair cuts, unlanded BGM hits, unsafe titles, missing handles, dropped effect-motion rows, weak adjacent-pair joins, missing outgoing/bridge-or-motion/landing choreography, prose-only bridge beats, bridge clips without local video/frame evidence, blank/duplicate preview frames, unwatchable transition flow, or unpreviewed day/title transitions after BGM phrase, effect motion, rhythm recut, bridge, transition execution, and transition polish stages.
- Audits final source usage so final raw clips must come from footage-select hero/main/texture choices instead of unmatched, repair, reject, or utility-dominant source material.
- Audits creator-cut application so rejected, weak, utility, or unmatched clips cannot remain active in the final candidate blueprint.
- Audits reference scene grammar so opening, chapters, transitions, and ending use context/movement/texture/payoff/aftertaste structure instead of flat montage.
- Audits reference profile application and reference transition profile so multi-video learning reaches opening, chapter, rhythm, creator-cut, transition, caption, audio, scene-grammar, and current-film bridge/breath/match/motion-balance gates instead of remaining unused analysis.
- Audits timeline variety so the final film has movement, lived-in texture, destination payoff, and ending aftertaste instead of hiding weak shot choice behind transitions.
- Audits the unattended first-draft chain before Resolve apply, connecting raw intake, first-assembly source order, story, BGM, captions, titles, rhythm, rhythm-recut application, final-source usage, creator-cut application, reference-profile application, reference-transition-profile, timeline-variety, effect-motion application, transition-polish application, Resolve transition materialization/apply paths, bridge-sequence application, final-blueprint lineage, transition cadence, transition microstructure, transition scene-arc/effect-palette/visual-match/preview-quality/audition-quality/storyboard, execution readiness, scene grammar, repair closure, and blueprint preflight into one gate.
- Generates DaVinci Resolve timeline blueprints and safety contracts before writing to Resolve.
- Audits final delivery quality: clean titles, no portrait regressions, BGM-only no-voiceover mode, dense title-safe subtitles, full-source first-assembly order, final-source usage, creator-cut application, rhythm-recut application, reference-profile application, reference-transition-profile, timeline-variety, effect-motion application, transition-polish application, Resolve transition materialization/apply paths, bridge-sequence application, transition bridge visual evidence, final-blueprint lineage, transition cadence, transition microstructure, transition effect palette, transition visual match, transition choreography, transition preview quality, transition audition quality, transition storyboard, transition pair-continuity/execution readiness, reference scene grammar, route texture, export quality, and V14 baseline maturity.

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
curl -L -o /tmp/travel-video-studio-skill-v0.1.55.tar.gz \
  https://github.com/junwen853/travel-video-studio-skill/releases/download/v0.1.55/travel-video-studio-skill-v0.1.55.tar.gz
tar -xzf /tmp/travel-video-studio-skill-v0.1.55.tar.gz --strip-components=1 -C ~/.codex/skills/travel-video-studio
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
- `reference_profile_application_contract_audit.md`
- `bgm_sourcing/bgm_sourcing_brief.md`
- `transition_bridge_plan/transition_bridge_plan.md`
- `transition_execution_plan/transition_execution_plan.md`
- `transition_execution_blueprint/transition_execution_blueprint_report.md`
- `transition_motif_plan/transition_motif_plan.md`
- `bridge_sequence_plan/bridge_sequence_plan.md`
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.md`
- `bridge_sequence_application_contract_audit.md`
- `transition_bridge_visual_evidence_contract_audit.md`
- `effect_motion_application_contract_audit.md`
- `transition_polish_application_contract_audit.md`
- `final_blueprint_lineage_contract_audit.md`
- `transition_cadence_contract_audit.md`
- `transition_microstructure_contract_audit.md`
- `transition_scene_arc_contract_audit.md`
- `transition_effect_palette_contract_audit.md`
- `transition_visual_match_contract_audit.md`
- `transition_preview_packet/transition_preview_packet.md`
- `transition_preview_quality_contract_audit.md`
- `transition_audition_packet/transition_audition_packet.md`
- `transition_audition_quality_contract_audit.md`
- `transition_storyboard_contract_audit.md`
- `reference_transition_profile_contract_audit.md`
- `final_source_usage_contract_audit.md`
- `reference_style_repair_plan/reference_style_repair_plan.md`
- `effect_motion_blueprint/effect_motion_blueprint_report.md`
- `bgm_phrase_blueprint/bgm_phrase_blueprint_report.md`
- `rhythm_recut_blueprint/rhythm_recut_blueprint_report.md`
- `rhythm_recut_application_contract_audit.md`
- `transition_polish_blueprint/transition_polish_blueprint_report.md`
- `transition_quality_contract_audit.md`
- `shot_transition_boundary_contract_audit.md`
- `transition_motivation_contract_audit.md`
- `transition_pair_continuity_contract_audit.md`
- `transition_execution_readiness_contract_audit.md`
- `creator_cut_application_contract_audit.md`
- `reference_scene_grammar_contract_audit.md`
- `audience_caption_contract_audit.md`
- `unattended_first_draft_contract_audit.md`
- `title_typography_plan/title_typography_plan.md`
- `cover_title_contract_audit.md`
- `raw_intake_completeness_audit.md`
- `source_selection_repair_plan/source_selection_repair_plan.md`
- `source_selection_coverage_contract_audit.md`
- `first_assembly_source_order_contract_audit.md`
- `large_source_unattended_readiness_contract_audit.md`
- `reference_repair_closure_audit.md`
- `visual_establishing_plan/visual_establishing_plan.md`
- `resolve_timeline_blueprint.json`
- `resolve_blueprint_preflight.md`
- `render_plan.json`
- final QA reports, including `final_qa_suite_report.json`, `transition_pair_continuity_contract_audit.json`, `transition_execution_readiness_contract_audit.json`, `transition_polish_application_contract_audit.json`, `effect_motion_application_contract_audit.json`, `bridge_sequence_application_contract_audit.json`, `transition_bridge_visual_evidence_contract_audit.json`, `source_selection_coverage_contract_audit.json`, `first_assembly_source_order_contract_audit.json`, `large_source_unattended_readiness_contract_audit.json`, `final_blueprint_lineage_contract_audit.json`, `transition_cadence_contract_audit.json`, `transition_microstructure_contract_audit.json`, `transition_scene_arc_contract_audit.json`, `transition_effect_palette_contract_audit.json`, `transition_visual_match_contract_audit.json`, `transition_preview_packet/transition_preview_packet.json`, `transition_preview_quality_contract_audit.json`, `transition_audition_packet/transition_audition_packet.json`, `transition_audition_quality_contract_audit.json`, `transition_storyboard_contract_audit.json`, `reference_transition_profile_contract_audit.json`, `final_source_usage_contract_audit.json`, `creator_cut_application_contract_audit.json`, `rhythm_recut_application_contract_audit.json`, `reference_scene_grammar_contract_audit.json`, `reference_profile_application_contract_audit.json`, and `v14_baseline_contract_audit.json`

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
- first assembly source-order contract
- large source unattended-readiness contract
- transition pair-continuity contract
- transition execution-readiness contract
- transition-polish application contract
- effect-motion application contract
- Resolve transition materialization contract
- Resolve transition apply contract
- bridge-sequence application contract
- transition bridge visual evidence contract
- final blueprint lineage contract
- transition cadence contract
- transition microstructure contract
- transition effect palette contract
- transition visual match contract
- transition choreography plan/contract
- transition preview quality contract
- transition audition quality contract
- transition storyboard contract
- creator-cut application contract
- reference scene grammar contract
- reference profile application contract
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
python3 ~/.codex/skills/travel-video-studio/scripts/audit_large_source_unattended_readiness_contract.py \
  --package-dir /path/to/delivery-package \
  --json
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
