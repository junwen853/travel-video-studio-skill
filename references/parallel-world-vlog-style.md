# Parallel World Four-Video Reference Profile

This reference distills four user-provided local videos from `叽叽歪歪的平行世界` into reusable, non-copying rules for Travel Video Studio. Use it when the user asks the Skill to learn from this creator, supplies downloaded creator-reference videos, references this creator's cover/title style, or wants a first draft to feel closer to a polished Bilibili long-form travel vlog.

Do not copy footage, music, exact titles, subtitles, narration, watermarking, thumbnail language, creator branding, or unique story beats. Only use the pacing, shot-function balance, transition logic, cover/title-card layout principles, and audience-facing caption behavior as an editing standard.

## Review Method

Do not rely on a few random extracted frames when learning from local reference videos. The 2026-06-28 pass used:

- full-film timeline strips every 10 seconds for all four videos
- opening strips every 2 seconds for the first 3 minutes
- ending strips every 2 seconds for the last 3 minutes
- scene-cut pacing and audio loudness/silence analysis
- separate user-provided cover/title screenshots

Future reference-learning passes should use the same standard before writing durable Skill rules. Contact sheets are a navigation aid; the useful learning comes from the whole beginning-to-end timeline, transition context, opening construction, and ending construction.

When multiple local reference videos are available, run `prepare_reference_batch_profile.py` first. The batch profile should aggregate scene-cut rhythm, audio continuity, sampled frame worksheets, and non-copying style targets before edit rhythm or reference-style audits use the reference.

## Measured Batch Profile

The 2026-06-28 local reference pass analyzed four downloaded videos, about `95.48` total minutes.

- Average video duration: about `23.87` minutes.
- Frame rate: all references were about `29.97 fps`.
- Estimated shot count: `1112` total at scene threshold `0.35`.
- Average shot length: about `5.00` seconds.
- Median shot length: about `2.95` seconds.
- Short shots under 3 seconds: `549`.
- Long breathing shots over 20 seconds: `31`.
- Mean audio loudness: about `-19.93 dB`.

Practical target: a future 20-minute travel film should not be a slow raw-footage chain, but it also should not become a short-video hypercut. Use many 1.5-4 second connective beats, frequent 4-9 second story beats, and a few deliberate 20+ second scenic or human moments when the image has real value.

## Opening Pattern

Open with a clear viewer question or trip promise, then prove the place visually and return to the real route.

- In the first 40 seconds, establish why the viewer should watch: destination question, route promise, unusual activity, or immediate human context.
- Within the first minute, show at least two of: aerial/skyline/coast/mountain, water/road/rail movement, city or landscape identity, travel companion reaction, map/route cue, and local texture.
- In minutes 1-3, return to practical travel reality: car, ferry, plane, airport, station, road, hotel, luggage, tickets, room view, or street arrival.
- Put the main title on real footage, not a black slate. Keep it short and clean.
- Use creator-style restraint: one short title or place label over a strong image is better than stacked route/date text.
- Avoid starting with internal project labels, editor status captions, generic country cards, or long route summaries.

After the initial Resolve blueprint exists, turn this pattern into an auditable package artifact:

```bash
python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package>
```

Do not claim this reference style if `opening_story_plan/opening_story_plan.json` is missing or if any of the six opening beats lacks evidence.

## Cover And Hero Title Style

The reference covers and hero title cards use a simple but high-impact formula:

- Background: one high-recognition establishing image, usually aerial, skyline, coast, bridge, mountain, or city panorama. It must identify the destination without explanation.
- Composition: keep the destination subject visible behind or around the title. Leave large readable sky/water/building space; do not choose cluttered handheld frames for covers.
- Main title: oversized 1-5 word Chinese destination title, extremely bold, centered or slightly below center, occupying roughly 35-55% of frame height.
- Secondary title: small English romanization/place name beneath the Chinese title with wide letter spacing or handwritten/script styling. Keep it secondary.
- Color: high-contrast yellow/orange/white against blue sky, water, city, or darker scenic backgrounds. Use a subtle shadow/stroke only for readability.
- Safe zone: keep platform watermark/creator mark in the top corner clear; do not overlap subtitles, random labels, project slugs, dates, or route arrows with the hero title.
- Rounded screenshot borders or platform chrome are not part of the deliverable design. Generate clean 16:9 cover/title media for the final package.
- For a Japan/Tokyo/Osaka-style project, use the same formula with the actual trip city or landmark: for example, a skyline, crossing, station, castle, tower, river, train, or street view plus one clean city/place title.

Reject covers that use black slates, low-recognition closeups, small timid text, stacked city names, long sentences, AI-looking gradient backgrounds, or title text that fights the subject.

Before final-quality claims, run `audit_cover_title_contract.py --package-dir <package>` so this cover/hero formula is checked against actual title media and manifest evidence.

## Chapter Rhythm

Each chapter should alternate visual functions instead of staying in one mode.

- Person/context: short direct-to-camera or companion reaction that tells the viewer why this moment matters.
- Movement: ferry, car, train, walking, bridge, airport, station, road, map screen, ticketing, or luggage.
- Place texture: street, sign, shopfront, hotel, room view, food/table, weather, waiting, parking, interior.
- Payoff: landmark, landscape, aerial, mountain, coast, skyline, museum/site, activity, or unique local experience.
- Aftertaste: a quieter observation before the next chapter, not an immediate hard reset.

When building an edit rhythm plan, require every primary clip to carry one of these functions. If several adjacent clips have the same function, split with a motivated cutaway from a different function.

When person/context footage runs for more than a short beat, intercut B-roll or visual evidence. Long talking segments should be supported by the place, food, object, road, map, sign, or activity being discussed.

Before rhythm or Resolve trust, generate `chapter_arc_plan/chapter_arc_plan.json` with `prepare_chapter_arc_plan.py`. Use `references/chapter-arc-engine.md` so every chapter has explicit context, movement, texture, payoff, and aftertaste/handoff rows, with owner scripts for any missing beat.

## Transition And Bridge Rules

The reference style rarely depends on flashy transitions. It uses physical route evidence and motivated visual association.

- Prefer road, ferry, train, walking, airport/station, parking, hotel window, escalator, signage, map/device screen, food-table reset, night-to-day change, or weather as bridge footage.
- Use match cuts where possible: window to skyline, vehicle movement to road, sign to destination, food closeup to table reaction, landscape wide to human reaction.
- Use simple dissolves or short fades for time-of-day or mood shifts. Avoid glitch, random spin, zoom-whip, flash-frame, and generic template transitions unless the actual footage motivates them. A whip-pan or rotation match cut is acceptable only when adjacent real route footage has clear motion energy, such as vehicle movement, walking direction, water movement, aerial drift, or a camera pan.
- Do not bridge days with black cards only. A title can sit on top of a real bridge image, but the bridge image must still carry the transition.
- For route changes, include at least one practical travel shot before the next scenic payoff.

## Effect And Graphic Vocabulary

Effects should clarify, not decorate.

- Allowed by default: clean title fade-in/out, subtle scale drift on scenic still-like shots, gentle dissolve, match cut, restrained speed ramp for vehicle/water/aerial motion, short freeze or monochrome emphasis only when used as a clear explanation beat.
- Materialize approved restrained effects with `prepare_effect_motion_blueprint.py` before Resolve apply, so fade/scale/whip/rotation/ramp choices are candidate metadata, not loose notes.
- Useful inserts: map/device screen, sign, timetable, museum/context panel, product/vehicle detail, or route-relevant graphic when it explains the travel moment.
- Forbidden as a default look: heavy template overlays, repeated whoosh transitions, random RGB/glitch effects, stacked captions around titles, fake drone claims, and unrelated stock beauty shots.
- If using a special insert or graphic, pair it with adjacent real footage so it feels like part of the trip rather than a slideshow detour.

## Creator Cut Selection

Before the first package build, create a raw footage selection pool with:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --project-dir <project>
```

Use `references/footage-select-engine.md` for the acceptance bar. The plan must score the whole source pool, identify hero/main/texture bridge candidates, reject prior exports, and flag portrait/square/unknown clips for repair. This is what prevents a large folder from becoming a filename-order montage.

Before any rhythm recut or Resolve write, create `creator_cut_plan/creator_cut_plan.json` with:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_creator_cut_plan.py --package-dir <package>
```

Use the plan to be stricter than a normal assembly:

- Hero clips are opening/title/payoff/ending candidates.
- Main story clips move route, activity, place, or emotion forward.
- Texture bridge clips connect chapters with street, transport, food, weather, hotel, signage, or quiet travel detail.
- Utility clips may patch route continuity but should not become long holds.
- Reject/review clips should be dropped, shortened, or replaced; do not rescue them with spin, flash, zoom, or template effects.

The reference feeling comes from selective shot choice plus route evidence. Effects are secondary.

After creator cut selection, run `prepare_transition_grammar_plan.py` so each adjacent pair has a specific cut/dissolve/match/whip/rotation/speed-ramp/bridge-insert decision. Then run `prepare_transition_execution_plan.py`, `prepare_transition_motif_plan.py`, `prepare_bridge_sequence_plan.py`, `prepare_bridge_sequence_blueprint.py`, `prepare_transition_execution_blueprint.py`, `prepare_bgm_phrase_blueprint.py`, and after rhythm recut `prepare_transition_polish_blueprint.py` plus `audit_transition_quality_contract.py` and `audit_shot_transition_boundary_contract.py` so the whole transition chain becomes Resolve-ready recipes, candidate transition metadata, materialized bridge sequences, selected-music phrase cues, final BGM-hit/title-safe/motion-proven transition polish metadata, visual-boundary coverage evidence, and exact from/to boundary matching instead of repeated dissolves, random motion, effects hiding weak route jumps, or one-effect city/day jumps. This is the guard against vague "add some transition" editing.

After reference-style, director-intent, director-polish, or final QA checks run, use `prepare_reference_style_repair_plan.py` so every blocked check becomes a repair row with an owner script, required artifact, acceptance evidence, and post-repair audit. Do not allow "closer to the reference" to remain an unassigned note.

## Audio And Caption Behavior

The references rely on continuous sound support and frequent viewer-facing subtitles.

- Keep scenic/title/transition windows BGM-led or intentionally ambient; do not let accidental source-camera voice dominate those windows.
- For no-voiceover deliveries, use captions and scene order to carry story logic.
- Captions should be audience-facing travel narration: observation, route context, feeling, practical surprise, or chapter setup.
- Never write captions that explain the edit process, QA status, tool names, versions, delivery state, or what the editor fixed.
- Caption density can be high during person/context beats, but reduce or suppress captions during clean hero titles.

## Ending Pattern

End with aftertaste after the main experience, not an abrupt stop. A good ending returns to a road, airport, vehicle movement, final human reaction, quiet scenic view, night city, or route callback.

Good ending candidates:

- dusk/night road or city movement
- airport/plane/ferry/train departure or arrival
- final landscape or skyline wide
- companion reaction after the main experience
- quiet route callback before final title/credits

## Skill Application Checklist

Before saying a package has learned this reference style, verify:

- The cover/hero title uses a high-recognition establishing background, oversized destination title, secondary English/place line, and no cluttered internal labels, proven by `cover_title_contract_audit.json`.
- The reference batch profile exists when multiple local references were supplied, with aggregate pacing/audio/sample-frame targets and a non-copying usage contract.
- The opening has human/context plus real establishing footage within the first minute.
- The opening story plan proves the first 3 minutes contain viewer promise, destination proof, clean hero title, practical route/arrival material, lived-in texture, and first handoff.
- The chapter plan includes person/context, movement, texture, payoff, and aftertaste roles.
- The chapter arc plan exists at `chapter_arc_plan/chapter_arc_plan.json` and missing beats are assigned to owner scripts before effects are chosen.
- Every day/place boundary has physical bridge footage or an explicit local-footage search row.
- The edit rhythm plan targets about 3-second median rhythm with some longer breathing shots, not a flat sequence of long raw clips.
- The footage select plan proves the source pool was scored before first assembly, with hero/main/texture candidates and repair/reject rows.
- The creator cut plan rejects/demotes weak clips, assigns every kept clip a creator function, and allows whip/rotation transitions only when motion evidence supports them.
- The transition grammar plan gives every adjacent pair a recommended transition and fallback, and marks missing bridge footage as `insert_bridge_first`.
- The transition execution plan converts every adjacent-pair decision into a concrete Resolve recipe and keeps bridge-missing rows blocked instead of hiding them with spin/flash/template effects.
- The transition execution blueprint report proves those recipes are present as candidate transitions, clip in/out metadata, and timeline markers before Resolve apply.
- The transition motif plan proves repeated/template transition chains, missing BGM phrase cues, title-zone risk, and unmotivated motion effects are repaired or assigned.
- The BGM phrase blueprint report proves selected music has opening/body/transition/ending rows, clip annotations, and per-transition phrase cues before rhythm recut or Resolve apply.
- The transition polish blueprint report proves final transitions have BGM-hit timing, title/subtitle avoidance, motion-proof, and restrained keyframes before Resolve apply.
- The bridge sequence plan proves important route/title/timeline-gap transitions have 2-5 shot bridge beats or owner-script repairs.
- The bridge sequence blueprint report proves local bridge beats are present as video-only candidate clips before Resolve apply.
- The reference style repair plan converts blocked reference/director/QA checks into P0/P1 repair rows before the next Resolve write.
- Effect motion rows prefer fade/dissolve/match-cut/subtle motion and reject template-heavy effects.
- Effect motion blueprint rows prove approved effects are candidate-materialized on clips before Resolve apply.
- BGM/audio policy protects scenic/title/transition windows from accidental source voice.
- Subtitle/TXT/SRT lines are for viewers, not for the user/editor.
- The ending resolves with route aftertaste rather than stopping abruptly.
