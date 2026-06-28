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
- `opening_story_plan/opening_story_plan.json` / `.md`: first-three-minute viewer promise, destination proof, clean title, practical arrival, lived-in texture, and first handoff plan
- `long_form_structure.md`: 20-minute chapter and pacing structure
- `voiceover_script.txt`: approved or draft narration
- `narration_text_only_v4.txt`: required when the user rejects rendered voiceover audio
- `subtitles.srt`: initial subtitle timing draft
- `subtitles_v4_dense.srt`: required for quality recuts that need richer full-film text captions
- `delivery_assets_report.json` / `.md`: local title/place card generation, optional local voiceover status, and Resolve enrichment refresh report
- `edit_decision_plan.md`: chapter/clip/transition plan
- `resolve_timeline_enrichment.json`: subtitle cues, voiceover/BGM mix plan, stock/aerial placeholders, transition cues, and Resolve timeline markers
- `resolve_timeline_blueprint.json`: input for DaVinci Resolve API timeline creation
- `transition_execution_plan/transition_execution_plan.json` / `.md`: Resolve-ready transition recipes for adjacent-pair cuts, dissolves, whip/rotation/speed ramps, bridge inserts, BGM cues, and readback evidence
- `reference_style_repair_plan/reference_style_repair_plan.json` / `.md`: exact repair rows for blocked reference-style, director-intent, director-polish, or final-QA gaps
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
- `qa_checklist.md`: final delivery checklist
- `delivery_audit.json` / `delivery_audit.md`: machine-readable final readiness audit
- `workflow_run_report.json` / `.md`: safe local workflow report with command outcomes, project-state summary, Resolve API summary, route decision summary, route decision application summary, asset decision summary, Resolve dry-run summary, Resolve apply contract summary, render-plan summary, audit status, safety flags, and remaining blockers

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
- reference batch profile exists before rhythm/style claims when multiple reference videos were supplied
- opening story plan exists after first package build and proves all six first-three-minute beats before title, BGM, rhythm, creator-cut, director-intent, or Resolve apply claims
- cloud/API stages have either completed or the user accepted dry-run limitations
- voiceover audio exists or the chosen TTS command is tested
- if the user says not to use voiceover, voiceover audio is removed from the timeline and the narration is exported as TXT only
- subtitles exist and have a sync plan
- quality recuts have dense full-film captions, not only opening subtitles
- local delivery assets report exists; title/place cards are generated or explicitly deferred, and local TTS is either generated with approval or still recorded as pending
- BGM has source and license status
- aerial/stock inserts have source and license status
- BGM and stock/aerial rows in the asset ledger are no longer `unverified`
- asset sourcing packet exists and records official license pages plus exact decision fields before download/import
- asset decision reconciliation has been run after sourcing choices are filled, and the ledger reflects approved decisions
- DaVinci Resolve API has been checked
- Resolve timeline enrichment exists and records subtitle cues, audio plan, stock/aerial placeholders, transitions, and markers
- Resolve timeline blueprint dry-run passes
- Resolve timeline blueprint records whether footage selection sorted first-assembly chapter media by tier/score
- transition execution plan exists before Resolve apply when transition grammar exists; bridge-missing rows must remain blocked until real bridge footage is inserted
- reference style repair plan exists after rhythm recut planning or any blocked reference/director/final-QA audit, and P0 style gaps are assigned to concrete scripts/artifacts before the next Resolve write
- Resolve blueprint preflight is present and not blocked before any `--apply`
- Resolve apply contract exists and is not used for `--apply` until blockers are clear and the user approves
- title/place cards have been generated or explicitly deferred
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
