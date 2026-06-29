# Delivery Workflow

## Goal

Create a 20-minute travel film package that an editor or automated renderer can actually finish. The package must include story, sound, subtitles, visual inserts, transitions, typography, a DaVinci Resolve timeline blueprint, and a machine-readable edit plan.

## Required Package Contents

Create a timestamped folder under the project, usually:

```text
delivery_packages/<timestamp>/
```

Expected files:

- `delivery_plan.json`: machine-readable package summary
- app-level or package-level `external_media_intake.json` / `.md`: mounted-drive project/media-root choice packet when multiple trip roots or mismatches exist
- source project `route_review/<timestamp>/route_review.md`: route/location review packet when human review is required
- source project `route_review/<timestamp>/contact_sheet.jpg`: frame evidence for confirming or correcting the route
- source project `route_scaffold/<timestamp>/route_coverage_scaffold.md`: full-media scaffold when automatic route coverage is too low
- source project `route_review/<timestamp>/route_decision_sheet.json` / `.md`: editable approval sheet for route decisions and project/media region mismatch
- source project `route_review/<timestamp>/route_decision_application.json` / `.md`: dry-run or approved application of route decisions back into `route_review.json`
- source project `route_review/<timestamp>/confirmed_route_candidate.md`: approval-gated candidate or repair plan before confirmed-route writes
- source or package `footage_select_plan/footage_select_plan.json` / `.md`: raw-footage scoring and highlight-selection plan used before first assembly
- source or package `raw_intake_completeness_audit.json` / `.md`: full source-tree, recognition, confirmed-route, footage-select, derived-exclusion, and stale-artifact gate before trusting large unordered folders
- `opening_story_plan/opening_story_plan.json` / `.md`: first-three-minute viewer promise, destination proof, clean title, practical arrival, lived-in texture, and first handoff plan
- `chapter_arc_plan/chapter_arc_plan.json` / `.md`: per-chapter context, movement, lived-in texture, payoff, and aftertaste/handoff planning with owner-script repair rows
- `long_form_structure.md`: 20-minute chapter and pacing structure
- `voiceover_script.txt`: approved or draft narration
- `narration_text_only_v4.txt`: required when the user rejects rendered voiceover audio
- `subtitles.srt`: initial subtitle timing draft
- `subtitles_v4_dense.srt`: required for quality recuts that need richer full-film text captions
- `delivery_assets_report.json` / `.md`: local title/place card generation, optional local voiceover status, and Resolve enrichment refresh report
- `cover_title_contract_audit.json` / `.md`: cover/hero title gate proving high-recognition scenic background, oversized destination title, short designed English/place subtitle, clean 16:9 frame, and no route/date/project clutter
- `edit_decision_plan.md`: chapter/clip/transition plan
- `resolve_timeline_enrichment.json`: subtitle cues, voiceover/BGM mix plan, stock/aerial placeholders, transition cues, and Resolve timeline markers
- `resolve_timeline_blueprint.json`: input for DaVinci Resolve API timeline creation
- `transition_execution_plan/transition_execution_plan.json` / `.md`: Resolve-ready transition recipes for adjacent-pair cuts, dissolves, whip/rotation/speed ramps, bridge inserts, BGM cues, and readback evidence
- `transition_execution_blueprint/resolve_timeline_blueprint_transition_execution.json`: non-destructive Resolve candidate containing transition execution metadata, markers, and clip in/out transition annotations
- `transition_execution_blueprint/transition_execution_blueprint_report.json` / `.md`: transition materialization summary, safety flags, and approval/follow-up instructions
- `transition_motif_plan/transition_motif_plan.json` / `.md`: film-level transition motif audit for repeated dissolves, random motion effects, BGM phrase cues, title-zone safety, and owner-script repairs
- `bridge_sequence_plan/bridge_sequence_plan.json` / `.md`: 2-5 shot route/title bridge sequence plan for important transitions that cannot be solved by a single effect
- `bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json`: non-destructive Resolve candidate containing video-only materialized bridge sequence inserts
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.json` / `.md`: bridge sequence materialization summary, safety flags, and approval/follow-up instructions
- `bridge_sequence_application_contract_audit.json` / `.md`: final-candidate gate proving planned 2-5 shot bridge inserts survived later candidate-blueprint stages and stayed video-only/BGM-led
- `transition_polish_blueprint/resolve_timeline_blueprint_transition_polish.json`: non-destructive Resolve candidate containing final BGM-hit, title-safe, motion-proven transition polish metadata
- `transition_polish_blueprint/transition_polish_blueprint_report.json` / `.md`: final transition polish summary, safety flags, and approval/follow-up instructions
- `transition_polish_application_contract_audit.json` / `.md`: active/final-blueprint gate proving transition-polish rows survived candidate-to-final handoff
- `resolve_transition_materialization_contract_audit.json` / `.md`: active/final-blueprint and Resolve-adapter gate proving transition recipe/effect payloads survive into timeline marker customData/readback evidence
- `final_blueprint_lineage_contract_audit.json` / `.md`: active/final-blueprint gate proving the final Resolve blueprint inherited the latest ready candidate chain instead of an old or partial blueprint
- `final_source_usage_contract_audit.json` / `.md`: active/final-blueprint gate proving final raw clips actually match footage-select hero/main/texture choices and do not reintroduce unmatched, repair, reject, or utility-dominant source material
- `transition_quality_contract_audit.json` / `.md`: final transition quality gate proving visual-boundary coverage, BGM-hit timing, title/subtitle avoidance, motion evidence, and no repeated/template effects
- `shot_transition_boundary_contract_audit.json` / `.md`: shot-to-shot boundary gate proving each adjacent from/to pair maps to transition metadata with BGM-hit, title-safe, BGM-only, and motion-evidence checks
- `transition_motivation_contract_audit.json` / `.md`: transition motivation gate proving each boundary has route, bridge, motion, title, or BGM reasoning rather than decorative effects
- `transition_pair_continuity_contract_audit.json` / `.md`: pair-continuity gate proving every adjacent from/to shot has concrete visual, route, motion, BGM, or title continuity evidence
- `transition_execution_readiness_contract_audit.json` / `.md`: execution-readiness gate proving every final transition has a package-local Resolve recipe, keyframes, BGM hit, title-safe window, pair readiness, and handle evidence
- `creator_cut_application_contract_audit.json` / `.md`: final-candidate gate proving creator-cut hero/main/texture/reject decisions are applied instead of only planned
- `reference_scene_grammar_contract_audit.json` / `.md`: scene-grammar gate proving opening, chapters, transitions, and ending use reference-like context/movement/texture/payoff/aftertaste functions
- `audience_caption_contract_audit.json` / `.md`: caption/TXT gate proving final viewer text is audience-facing and does not expose edit-status, tool, QA, or version language
- `unattended_first_draft_contract_audit.json` / `.md`: no-write first-draft gate proving raw intake, footage select, opening/chapter story, title/cover, captions, BGM, audio policy, establishing/effects, rhythm/creator cut, transition QA, reference repair closure, and Resolve preflight are connected before handoff
- `reference_style_repair_plan/reference_style_repair_plan.json` / `.md`: exact repair rows for blocked reference-style, director-intent, director-polish, or final-QA gaps
- `reference_repair_closure_audit.json` / `.md`: closure gate proving P0 reference-style repair rows have required artifacts, post-repair audit evidence, and readback/frame evidence
- `resolve_blueprint_preflight.json` / `.md`: no-write Resolve blueprint safety audit covering source files, source ranges, track overlaps, V1 gaps, title cards, subtitles, markers, and source audio
- `resolve_apply_contract.json` / `.md`: approval contract before any actual DaVinci timeline write
- `davinci_build_notes.md`: Resolve write steps and remaining manual/polish passes
- `render_plan.json`: Resolve final render settings created by `prepare_resolve_render.py`
- `render_job_status.json`: present only after an approved Resolve render job is queued
- `render_delivery_verification.json` / `.md`: final MP4 verification after export, including duration, streams, sample frames, black-frame scan, and subtitle evidence
- `longform_delivery_audit.json` / `.md`: final 20-minute-film promise audit, covering voiceover, subtitles, BGM, aerial/stock evidence, typography/title cards, transitions, DaVinci readback, route-recognition artifacts, route honesty, and final render proof
- `quality_recut_report.json` / `.md`: required when revising a weak draft into a higher-quality 59.94/60fps, high-bitrate, no-voiceover, dense-caption version
- `title_cards/title_cards_manifest.json`: generated title/place cards when enabled
- `reference/reference_analysis.json`: Malta/reference-film analysis when available
- `reference/reference_batch_profile.json` / `.md`: aggregate profile for multiple supplied reference videos
- `asset_search_plan.md`: aerial, BGM, font, and optional stock queries
- `asset_ledger/asset_license_ledger.json`: machine-readable licensing status
- `asset_sourcing/asset_sourcing_packet.json` / `.md`: provider/license directory, exact selection fields, approval evidence requirements, and sourcing next actions
- `asset_sourcing/asset_decision_reconciliation.json` / `.md`: dry-run or applied reconciliation of filled sourcing decisions back into the asset ledger
- `bgm_cues.md`: music mood, timing, source/license status
- `effect_motion_blueprint/resolve_timeline_blueprint_effect_motion.json`: non-destructive Resolve candidate containing restrained title/transition effect-motion metadata and markers
- `effect_motion_blueprint/effect_motion_blueprint_report.json` / `.md`: effect-motion materialization summary, safety flags, and approval/follow-up instructions
- `bgm_phrase_blueprint/resolve_timeline_blueprint_bgm_phrase.json`: non-destructive Resolve candidate containing BGM section/phrase rows, timeline markers, clip annotations, and per-transition phrase cues
- `bgm_phrase_blueprint/bgm_phrase_blueprint_report.json` / `.md`: BGM phrase materialization summary, safety flags, and approval/follow-up instructions
- `qa_checklist.md`: final delivery checklist
- `delivery_audit.json` / `delivery_audit.md`: machine-readable final readiness audit
- `workflow_run_report.json` / `.md`: safe local workflow report with command outcomes, project-state summary, Resolve API summary, route decision summary, route decision application summary, asset decision summary, audience-caption and unattended-first-draft summaries, BGM phrase blueprint summary, Resolve dry-run summary, Resolve apply contract summary, render-plan summary, audit status, safety flags, and remaining blockers

## Chapter Structure

For each route chapter, produce:

- place name and confidence
- representative footage type
- narration intent
- subtitle style
- BGM mood
- transition into and out of the chapter
- establishing shot or aerial need
- missing evidence or human-review note

## Transitions

Use content-based transitions instead of generic effects:

- Day 1 to Day 2: morning street, train/metro, hotel window, food prep, map card
- City to city: station, airport, road, map route animation, luggage/detail shot
- Landmark to street: ambient street cutaway, sign/OCR insert, crowd or traffic rhythm
- Night to morning: sound bridge, fade through black, alarm/hotel/street ambience

If footage lacks a transition, add an insert request to `asset_search_plan.md` or a local footage query.

## Delivery Gates

The package is not final until:

- route mismatch and stale artifacts are resolved
- mounted-drive media roots are explicitly matched to the intended project when multiple trips or project/media mismatches exist
- route coverage scaffold covers the source media when automatic route coverage is weak
- route review packet blockers are resolved and a fresh `confirmed_route_timeline.json` exists when human review was required
- route decision sheet is reviewed and its decisions are copied into `route_review.json` before candidate generation
- route decision application report proves the decision sheet is either blocked, ready to apply, or applied
- confirmed-route candidate is apply-ready before overwriting `confirmed_route_timeline.json`
- footage select plan exists before first assembly, proves active source videos were tiered, and blocks derived/portrait/weak footage from leading the cut
- raw intake completeness audit passes after first package build, proving the media index covers the mounted source tree and every active source video is recognized, routed exactly once, scored, non-derived, and fresh
- reference batch profile exists before rhythm/style claims when multiple reference videos were supplied
- opening story plan exists after first package build and proves all six first-three-minute beats before title, BGM, rhythm, creator-cut, director-intent, or Resolve apply claims
- chapter arc plan exists after opening-story planning and before rhythm/creator-cut/Resolve trust, proving each chapter has beat decisions or assigned repair owners
- cloud/API stages have either completed or the user accepted dry-run limitations
- voiceover audio exists or the chosen TTS command is tested
- if the user says not to use voiceover, voiceover audio is removed from the timeline and the narration is exported as TXT only
- subtitles exist and have a sync plan
- quality recuts have dense full-film captions, not only opening subtitles
- local delivery assets report exists; title/place cards are generated or explicitly deferred, and local TTS is either generated with approval or still recorded as pending
- cover title contract audit passes before final-quality claims, proving the hero title follows the reference cover formula and avoids ghosted route/date/project labels
- BGM has source and license status
- BGM phrase blueprint report exists before rhythm recut or Resolve apply, proving selected music became opening/body/transition/ending phrase rows, clip annotations, and per-transition cue metadata without mutating the active blueprint by default
- aerial/stock inserts have source and license status
- BGM and stock/aerial rows in the asset ledger are no longer `unverified`
- asset sourcing packet exists and records official license pages plus exact decision fields before download/import
- asset decision reconciliation has been run after sourcing choices are filled, and the ledger reflects approved decisions
- DaVinci Resolve API has been checked
- Resolve timeline enrichment exists and records subtitle cues, audio plan, stock/aerial placeholders, transitions, and markers
- Resolve timeline blueprint dry-run passes
- Resolve timeline blueprint records whether footage selection sorted first-assembly chapter media by tier/score
- transition execution plan exists before Resolve apply when transition grammar exists; bridge-missing rows must remain blocked until real bridge footage is inserted
- transition execution blueprint report exists before Resolve apply, proving approved transition recipes became candidate `transitions[]`, clip in/out metadata, and timeline markers without mutating the active blueprint by default
- transition motif plan exists after transition execution and before Resolve apply, proving repeated/template transitions, missing BGM cues, title-zone risk, and unmotivated motion effects are repaired or explicitly assigned
- bridge sequence plan exists after transition motif and before rhythm recut/Resolve apply, proving important route/title/timeline-gap transitions have 2-5 shot bridge beats or owner-script repairs
- bridge sequence blueprint report exists before Resolve apply when local bridge candidates are available, proving those beats became video-only candidate clips without mutating the active blueprint by default
- bridge sequence application contract audit passes before Resolve apply, proving later rhythm/BGM/effect/transition-polish candidates did not drop the planned 2-5 shot bridge inserts or re-enable source audio
- rhythm recut blueprint report exists before Resolve apply when long-shot risks exist, proving the recut started from the BGM phrase candidate and preserved transition/effect/BGM phrase metadata
- transition polish blueprint report, application audit, Resolve transition materialization audit, and final blueprint lineage audit exist before Resolve apply, proving final transitions carry BGM-hit timing, title/subtitle avoidance, motion-evidence checks, restrained keyframes, active/final-blueprint survival after rhythm recut, Resolve marker/readback payload survival, and latest candidate-chain inheritance
- transition quality contract audit passes before Resolve apply, proving the transition-polish candidate covers every visual boundary and does not hide route gaps with random/repeated effects
- shot transition boundary contract audit passes before Resolve apply, proving every adjacent visual boundary has the correct from/to transition row instead of generic hard cuts or random rotations
- transition motivation, pair-continuity, execution-readiness, transition-polish application, Resolve transition materialization, bridge-sequence application, final-blueprint lineage, creator-cut application, and reference scene-grammar contract audits pass before Resolve apply, proving every transition has route/bridge/motion/title/BGM reasoning, every adjacent from/to shot has concrete continuity evidence, every final transition is Resolve-executable, polished transition metadata and Resolve marker/readback payloads survive, planned bridge beats survive into the final candidate, the active blueprint inherits the latest ready candidate chain, rejected/weak shots are not active in the final candidate, and the opening/chapters/ending are not a flat montage
- audience caption contract audit passes before subtitle overlay or handoff, proving captions/TXT read like travel-film text rather than user-facing edit notes
- reference style repair plan exists after rhythm recut planning or any blocked reference/director/final-QA audit, and P0 style gaps are assigned to concrete scripts/artifacts before the next Resolve write
- reference repair closure audit exists after the repair plan; P0 rows must be closed or Resolve/final-quality claims stay blocked
- Resolve blueprint preflight is present and not blocked before any `--apply`
- unattended first-draft contract audit passes before Resolve apply or external handoff, proving the package has one connected first-draft chain instead of isolated planning files
- Resolve apply contract exists and is not used for `--apply` until blockers are clear and the user approves
- title/place cards have been generated or explicitly deferred
- effect motion blueprint report exists before Resolve apply when effect motion rows are ready, proving restrained title/transition effects became candidate metadata without mutating the active blueprint by default
- actual Resolve writes have a readback audit report
- render plan has been prepared and re-audited
- `delivery_audit.json` reports no blockers before final render
- safe local workflow report exists when the package was prepared through the combined workflow, and it records no failed safe steps; `check_project_state.py` returning 2 for project blockers is acceptable when the report preserves those blockers as project-state blockers
- `delivery_audit.json` reports `ready_for_final_render` before a Resolve render is queued or started
- final render verification passes before the output is called deliverable
- final render verification proves the required frame rate and bitrate for high-quality masters
- long-form delivery audit passes or reports only explicit route/location certainty caveats
- final editor path is selected, with DaVinci API preferred

Use "blocked", "draft", or "ready" status explicitly.
