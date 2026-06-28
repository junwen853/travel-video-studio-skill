# Long-Form Travel Style

## Target

Default target is a 20-minute travel film, not a short recap. A 1-2 minute output is a failure unless the user explicitly changes the target duration. Local reference films may be 20-40 minutes, so the workflow must scale beyond short recap pacing.

Use `analyze_reference_video.py` to write `reference_analysis.json` and a contact sheet before copying its pacing assumptions into a new project.

Use `prepare_reference_batch_profile.py` when the user provides multiple reference videos. The generated `reference_batch_profile.json` should become the pacing/audio/sample-frame source for rhythm planning and reference-style audits.

Use Bilibili long-form travel creators such as `叽叽歪歪的平行世界` as a pacing reference, not as material to copy. The useful traits are sustained route, lived-in travel reality, chapter breathing, transport, street texture, food/waiting/weather details, natural reactions, and a watchable documentary-vlog rhythm. Do not copy titles, narration lines, thumbnails, music, or footage.

The film should feel like a real trip being reconstructed, not a montage of scenic shots. Every chapter needs a reason to exist in the route: arrival, exploration, transition, mistake, meal, weather change, landmark, night walk, hotel, train, airport, or emotional callback.

## Structure

For a 20-minute film:

- opening route promise: 35-60s
- 4-6 main chapters: usually 2.5-5 minutes each when footage supports it
- transitions: 15-45s each, using transport, street details, hotel windows, food prep, maps, signage, stations, airports, escalators, rain, night streets, or ambient cutaways
- ending: 45-75s, with callback and emotional aftertaste

For a 40-minute Malta-like reference film, expand chapter duration instead of increasing narration density. Use more natural sound, street sequences, transportation, food, waiting, map pauses, and human reaction beats.

Do not compress every place into equal time. Give more time to chapters with stronger footage, richer human moments, clearer local texture, or more important route meaning. Shorter chapters are acceptable only when they function as bridges.

## Minimum 20-Minute Shape

A normal 20-minute trip film should usually follow this shape:

- 00:00-01:00: opening route promise, best hook visuals, title typography, and route expectation
- 01:00-05:00: arrival and first city texture
- 05:00-09:00: first major place or day-one experience
- 09:00-13:00: transport, meal, hotel, street wandering, or route change
- 13:00-17:30: strongest landmark, neighborhood, or day-two/day-three chapter
- 17:30-19:15: final movement, night/morning contrast, or emotional return
- 19:15-20:00: ending callback, quiet close, credits or final title card

If source footage supports a different structure, adjust the timings, but keep the same long-form principles: route, chapters, breathing room, and lived-in transitions.

## Narration

Narration should guide, not flood:

- use sparse spoken paragraphs
- leave long stretches for natural sound and BGM
- avoid explaining what the viewer can see
- mark uncertain locations honestly
- tie every claim to actual route evidence or user-confirmed context
- leave 20-60 second stretches where only source audio, BGM, and visuals carry the film

## Visual Rhythm

Use repeated long-form patterns:

- establish place with aerial/skyline/map/title card
- enter street-level detail
- show human reaction, food, transit, weather, or waiting
- widen again before leaving the place
- transition with geography, sound, or motion

Do not use short-video pacing as the default. Avoid constant speed ramps, over-dense captions, generic beat cuts, and endless beauty shots with no route function. Let selected clips breathe when they show walking, ordering food, entering stations, checking maps, changing weather, or people reacting.

Before first assembly from unordered source media, generate `footage_select_plan/footage_select_plan.json` with:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --project-dir <project>
```

This plan should exist before `build_delivery_package.py` when the user expects a strong first draft from a large folder. It scores every active source video, promotes hero/main/texture bridge candidates, rejects prior exports, flags portrait/square/unknown clips for repair, and exposes missing chapter movement/detail/payoff coverage. The first assembly should use this plan to sort local footage before stock, effects, or rhythm recut are considered.

After `build_delivery_package.py`, generate `opening_story_plan/opening_story_plan.json` with:

```bash
python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package>
```

This plan should exist before title, BGM/audio, visual establishing, rhythm, or creator-cut planning. It verifies that the first three minutes have a viewer promise, destination proof, one clean hero title, practical arrival, lived-in texture, and first chapter handoff. Missing opening beats are structure blockers, not minor polish notes.

Generate `chapter_arc_plan/chapter_arc_plan.json` with:

```bash
python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package>
```

This plan should exist before edit rhythm, creator cut, transition execution, captions, BGM decisions, or Resolve trust. It converts each chapter into context, movement, lived-in texture, destination payoff, and aftertaste/handoff rows. Missing chapter beats must map to owner scripts before an effect or stock insert is allowed to compensate.

Generate `edit_rhythm_plan/edit_rhythm_plan.json` with:

```bash
python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package>
```

This plan should exist before Resolve writes when the user wants Malta/Bilibili-style quality. It compares the current blueprint to the reference pacing profile, lists every primary visual shot, marks long raw holds and missing cutaway beats, and creates per-chapter rhythm rows. Use it to decide where to trim, split, insert transport/street/food/hotel/weather details, or keep a deliberate breathing shot.

Then generate `rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json` with:

```bash
python3 <skill-dir>/scripts/prepare_creator_cut_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_grammar_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_execution_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_motif_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bridge_sequence_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bgm_phrase_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_rhythm_recut_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package>
```

The creator cut plan must run first. It decides which clips are hero, main story, texture bridge, utility, or reject/review; assigns creator functions; and records whether any whip-pan or rotation transition is truly motivated by route motion. The transition grammar plan gives every adjacent clip pair an exact transition recommendation and fallback, the transition execution plan turns those rows into Resolve recipes, the transition execution blueprint makes those recipes visible in the candidate timeline, the transition motif plan audits the whole chain for repeated dissolves, random motion, missing BGM phrase cues, title-zone risk, or effects hiding weak route jumps, the bridge sequence plan turns important route/title/timeline-gap changes into 2-5 shot connective beats, the bridge sequence blueprint turns local bridge beats into a preflightable Resolve candidate, and the BGM phrase blueprint ties selected music sections to clip and transition cues. The rhythm recut candidate then turns the diagnosis into an executable Resolve blueprint draft without touching the original blueprint by default. It should shorten flat holds into main segments plus existing-footage cutaways, preserve the package duration, keep inserted clips video-only/BGM-led, and pass `audit_resolve_blueprint.py --blueprint <candidate> --package-dir <package>` before any `--update-blueprint` or Resolve apply. The reference style repair plan converts blocked style/director/QA checks into P0/P1 repair rows with scripts and acceptance evidence.

When the candidate is approved, use a package fork before touching Resolve:

```bash
python3 <skill-dir>/scripts/prepare_rhythm_recut_apply_package.py --source-package <package> --output-dir <new-package> --run-preflight
```

The new package is the Resolve target. It should carry the active recut blueprint, package-local rewritten asset paths, no copied final-render proof, and explicit next actions for dry-run, apply contract, Resolve readback, render, and final QA.

Before Resolve apply or final QA, preserve concrete user complaints as package-level feedback probes:

```bash
python3 <skill-dir>/scripts/prepare_feedback_regression_plan.py --package-dir <package>
```

This plan should feed `opening_title=0`, `reported_vertical_clip=7:04`, `reported_voice_at_7_04=7:04`, and `opening_bgm_no_voice=0` into audio-scene policy, feedback audit, and final QA instead of relying on conversation memory.

## Aerials, Inserts, BGM, and Typography

A 20-minute delivery package must plan more than raw footage:

- aerial or establishing inserts for the main city/region, using licensed stock or approved local assets
- local texture inserts for chapter bridges: streets, stations, signs, hotel windows, food, traffic, weather, crowds, water, skyline, or train/plane movement
- BGM arcs that can sustain long sections: opening theme, city exploration bed, transition bed, emotional ending bed
- restrained cinematic title cards and place cards with special fonts only when license status is recorded
- subtitles that support the voiceover and do not crowd the frame

When legal assets are not available yet, write exact search/sourcing tasks and keep final render blocked until licensing is verified.

## Route Honesty

If GPS is missing and location recognition is uncertain, do not pretend every clip has exact location truth. Use confidence language in plans and narration:

- confirmed by metadata, folder, OCR, or user decision
- visually likely
- route scaffold only
- needs human review

The edit can still be watchable with a scaffolded route, but the delivery report must state what was confirmed and what was inferred.

## Acceptance Bar

The package is not long-form ready unless it has:

- `long_form_structure.md`
- target duration around 20 minutes unless the user changes it
- an explicit rejection of 1-2 minute short-video pacing
- coverage ratio in `resolve_timeline_blueprint.json` is high enough to support the target duration
- `resolve_timeline_blueprint.json.longFormCoverage` explains initial selected footage, opening/transition/ending fill, final covered seconds, and target seconds
- `footage_select_plan/footage_select_plan.json` proves source media was scored and selected before first assembly
- `reference/reference_batch_profile.json` exists when multiple reference videos are supplied, and exposes aggregate pacing/audio/sample-frame targets
- `opening_story_plan/opening_story_plan.json` proves the first three minutes contain viewer promise, destination proof, clean hero title, practical route/arrival material, lived-in texture, and first handoff
- `chapter_arc_plan/chapter_arc_plan.json` proves each chapter has context/movement/texture/payoff/aftertaste rows, or assigned owner-script repairs for missing beats
- `transition_execution_plan/transition_execution_plan.json` proves adjacent-pair transitions have Resolve-ready recipes and no bridge-missing row is hidden behind an effect
- `transition_execution_blueprint/transition_execution_blueprint_report.json` proves transition recipes were materialized as candidate blueprint metadata before Resolve apply
- `transition_motif_plan/transition_motif_plan.json` proves the whole transition chain avoids repeated/template defaults and has BGM/title-zone/repair evidence
- `bridge_sequence_plan/bridge_sequence_plan.json` proves important route/title/timeline-gap transitions have 2-5 shot bridge beats or owner-script repairs
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.json` proves local bridge beats were materialized into a non-destructive candidate blueprint before Resolve apply
- `effect_motion_blueprint/effect_motion_blueprint_report.json` proves restrained title/transition motion rows were materialized into candidate clip metadata before Resolve apply
- `bgm_phrase_blueprint/bgm_phrase_blueprint_report.json` proves selected music was materialized into phrase rows, clip annotations, and transition cues before rhythm recut or Resolve apply
- `reference_style_repair_plan/reference_style_repair_plan.json` proves blocked reference/director/QA style gaps become executable repair rows before another Resolve write
- chapter time allocations
- transition plan between chapters/days
- feedback regression plan preserving known rejected timestamps before final render QA
- route-aware clip selection blueprint
- BGM plan that can sustain long sections
- aerial/establishing-shot plan or approved assets for major cities/regions
- typography and subtitle style plan
- narration density check proving the voiceover is not flooding the film
- route honesty notes for uncertain location recognition
- DaVinci timeline blueprint for actual assembly
- final render verification after export, including duration, resolution, audio, sampled frames, black-frame scan, and subtitle evidence
