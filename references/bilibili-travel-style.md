# Bilibili Long-Form Travel Style Reference

This file converts user-requested reference creators and an optional local reference film into reusable, non-copying editing rules for the Travel Video Studio skill.

## Sources To Check

- 影视飓风 official site: https://www.ysjf.com/
- 影视飓风 Bilibili space, user handle `946974`: https://space.bilibili.com/946974
- 影视飓风 Bilibili travel/vlog/camera-teaching search and related pages can be used to study B-roll thinking, camera movement, and creator-quality expectations, not to copy exact shots or scripts.
- 叽叽歪歪的平行世界 Bilibili space: https://space.bilibili.com/405004967/
- 叽叽歪歪的平行世界 travel-search entries can be used to study long-route family travel rhythm, lived-in connective tissue, and non-rushed route storytelling.
- Mixkit free stock music and license pages for traceable BGM sourcing:
  - https://mixkit.co/free-stock-music/
  - https://mixkit.co/license/#musicFree
- Pixabay Music is an alternate traceable BGM source when Mixkit does not fit the mood: https://pixabay.com/music/
- Optional local reference film: analyze any user-supplied long-form travel reference with `scripts/analyze_reference_video.py`.
- User-specified creator reference: `叽叽歪歪的平行世界`
- Local four-video creator learning profile: read `references/parallel-world-vlog-style.md` and `references/reference-batch-profile-engine.md` when the user provides downloaded videos or cover/title screenshots from `叽叽歪歪的平行世界`.

The Bilibili pages may be dynamic or partially inaccessible in headless browsing. Treat them as style references to study visually when available, not as sources to copy.

Web-checked source anchors on 2026-06-28:

- Bilibili confirms the 影视飓风 creator-space anchor at `space.bilibili.com/946974`; use it as a craft/production-quality reference, especially for camera movement, B-roll intention, and post workflow discipline.
- Bilibili confirms the 叽叽歪歪的平行世界 creator-space anchor at `space.bilibili.com/405004967`; the public profile describes family/world-travel positioning, which is relevant for lived-in route rhythm and long-route storytelling.
- Bilibili search for `叽叽歪歪的平行世界` surfaces travel-long-video related entries; use search results as discovery, then inspect actual videos visually when accessible.
- Mixkit free stock music and Mixkit license pages remain practical first-pass BGM sources because the asset and license pages can be recorded in the package.
- Pixabay Music is usable only with extra caution: record the track page, license/certificate evidence when available, and note possible Content ID claims in the asset ledger.

Web research note from the current Skill update: Bilibili search and creator-space pages are enough to confirm the relevant creator/style anchors, while Mixkit's free music and license pages provide a practical traceable BGM route. Even when the user says a private/nonprofit draft is not for monetization, keep the Skill on license-friendly music/stock sources so future deliveries do not inherit avoidable copyright risk.

Director-polish note from the current Skill update: use the creator references as a quality bar for visible craft, not as assets to copy. The final Skill should prove a clean aerial/establishing opening, restrained title typography, travel-appropriate BGM mood, motivated transition effects, dense but non-invasive subtitles, and a real route texture chain. These checks now belong in `audit_director_polish_contract.py`; failing them means the cut may be technically valid but still too template-like.

## Style Target

The target is a polished long-form travel documentary vlog, not a bare montage and not an AI slideshow.

The cut should feel like someone actually traveled through the route:

- transport establishes movement between places
- city identity appears through real signs, stations, skyline, streets, weather, food, interiors, waiting, and small human details
- chapters breathe before moving on
- transitions feel motivated by route, time of day, or mood
- music carries scenic sections without drowning captions
- subtitles are frequent enough to guide the viewer, but not so dense that the image disappears

## Opening Rules

The opening must make the city/place immediately legible and premium.

- Use an approved aerial, skyline, street, station, vehicle-window, or other real establishing clip.
- Use one clean city title, such as `TOKYO` or `OSAKA`.
- Do not stack `TOKYO / OSAKA` unless the film is explicitly opening as a whole-route map.
- Do not put route copy, dates, subtitles, or small labels behind the city title.
- Avoid black slates and generic `JAPAN 2025` cards for final delivery.
- Let the opening breathe with BGM only unless the user explicitly approves spoken narration there.

For `叽叽歪歪的平行世界`-style references, use the stricter opening/cover pattern in `parallel-world-vlog-style.md`: viewer promise, destination proof, practical route/arrival footage, and a cover/hero title built from a high-recognition establishing image with a huge destination title plus small English/place subtitle.

After the first package blueprint exists, read `references/opening-story-engine.md` and run the opening story gate before trusting title, BGM, rhythm, or director-polish claims:

```bash
python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package>
```

The plan must prove viewer promise, destination proof, clean hero title, practical arrival, lived-in texture, and first chapter handoff in the first three minutes.

## Route Rhythm

A route-aware travel edit should alternate between:

- arrival and movement: airport, train, station, road, escalator, map-like visual cues
- first city impression: skyline, street signs, crowd flow, storefronts, weather
- lived-in details: food, hotel, waiting, ticket gates, alleys, handheld reaction shots
- major landmark or destination payoff
- quiet bridge to the next place or day

The edit should not jump directly from landmark to landmark for 20 minutes. It needs connective tissue.

Before building the first package from a large unordered folder, run the raw-footage selection pass:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --project-dir <project>
python3 <skill-dir>/scripts/audit_raw_intake_completeness.py --project-dir <project> --package-dir <package>
```

Read `references/footage-select-engine.md`, `references/source-selection-repair-contract.md`, and `references/large-source-unattended-readiness-contract.md` before this step. The plan should identify hero, main story, texture bridge, utility, repair, and reject rows across the whole source pool. The raw-intake, first-assembly source-order, and large-source unattended-readiness audits must pass after the package exists, so first assembly starts from the best local footage instead of filename order, partial source scan, or transition effects hiding weak source selection.

Before trusting a Resolve blueprint as "not AI-made", run:

```bash
python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_edit_rhythm_plan.py --package-dir <package>
```

Use the opening plan to repair missing first-three-minute story beats first. Read `references/chapter-arc-engine.md` and use the chapter arc plan to force every chapter into context, movement, lived-in texture, payoff, and aftertaste/handoff decisions. Then use the rhythm plan to assign every primary visual shot a function and to surface long raw holds that need trim/split/cutaway work. The Malta reference pacing profile is a target for varied rhythm, not a requirement to copy the reference shot-for-shot.

When that plan reports long raw holds, immediately generate the non-destructive rhythm recut candidate:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_creator_cut_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_grammar_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_execution_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_motif_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bridge_sequence_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_effect_motion_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bgm_phrase_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_rhythm_recut_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_polish_blueprint.py --package-dir <package>
python3 <skill-dir>/scripts/audit_transition_quality_contract.py --package-dir <package>
python3 <skill-dir>/scripts/audit_shot_transition_boundary_contract.py --package-dir <package>
python3 <skill-dir>/scripts/audit_effect_motion_application_contract.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_preview_packet.py --package-dir <package> --extract-frames --update-transition-grammar
python3 <skill-dir>/scripts/audit_cover_title_contract.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package>
python3 <skill-dir>/scripts/audit_reference_repair_closure.py --package-dir <package>
```

Read `references/footage-select-engine.md`, `references/creator-cut-engine.md`, `references/transition-grammar-engine.md`, `references/transition-execution-engine.md`, `references/transition-execution-blueprint-engine.md`, `references/transition-motif-engine.md`, `references/bridge-sequence-engine.md`, `references/bridge-sequence-blueprint-engine.md`, `references/bridge-sequence-application-contract.md`, `references/transition-polish-application-contract.md`, `references/resolve-transition-materialization-contract.md`, `references/resolve-transition-apply-contract.md`, `references/effect-motion-blueprint-engine.md`, `references/effect-motion-application-contract.md`, `references/bgm-phrase-blueprint-engine.md`, `references/transition-polish-blueprint-engine.md`, `references/transition-execution-readiness-engine.md`, `references/transition-preview-packet-engine.md`, and `references/reference-style-repair-engine.md` before this step. The package-level footage select fallback proves the selected timeline came from triaged source material. The creator cut plan must run before the recut candidate. It should be stricter than the normal rhythm plan: demote weak clips, identify hero/main/texture/utility/reject tiers, and allow whip-pan or rotation match cuts only when real movement/route evidence supports them. The transition grammar plan decides exact adjacent-pair transitions, the transition execution plan converts those choices into Resolve-ready recipes, the execution blueprint materializes them as candidate transition metadata, the motif plan audits the whole chain for repeated dissolves, random motion, missing BGM phrase cues, title-zone risk, or effects hiding weak route jumps, the bridge sequence plan turns important route/title/timeline-gap transitions into 2-5 shot bridge beats, the bridge sequence blueprint materializes local beats into a non-destructive Resolve candidate, the bridge sequence application contract proves those bridge beats survive into the final candidate, the effect motion blueprint materializes restrained title/transition motion as candidate metadata, the effect motion application contract proves restrained fade/whip/rotation/ramp rows survive into the final blueprint without overuse, the BGM phrase blueprint ties those transition candidates to selected music phrase markers before rhythm recut, the transition polish blueprint adds final BGM-hit timing, title/subtitle avoidance, motion-proof, and restrained keyframe metadata after recut, the transition polish application contract proves that metadata survives into the active/final blueprint, the Resolve transition materialization contract proves recipe/effect payloads survive into marker customData/readback evidence, the Resolve transition apply contract proves visible effects have API/manual/bridge apply paths instead of marker-only metadata, the transition preview packet engine generates package-local outgoing/landing frame evidence for important boundaries, and the transition quality audit plus transition execution readiness contract prove the candidate covers every visual boundary without random/repeated effects and is Resolve-executable. The recut candidate should start from the BGM phrase candidate, break long holds with existing local-footage cutaways, keep total duration stable, preserve transition/effect/BGM phrase metadata plus BGM-only audio policy, and be preflighted with `audit_resolve_blueprint.py --blueprint <package>/rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json --package-dir <package>` before it replaces the active blueprint. The reference repair plan should convert blocked reference/director/final-QA checks into exact repair rows instead of leaving "make it closer to the reference" as prose, and the closure audit should keep P0 style repairs blocked until artifacts plus post-repair evidence close them.

After candidate review, prefer a new package fork instead of in-place replacement:

```bash
python3 <skill-dir>/scripts/prepare_rhythm_recut_apply_package.py --source-package <package> --output-dir <new-package> --run-preflight
```

The fork must make the recut blueprint active, keep the source package unmodified, avoid copying stale final-render QA, and provide the package that will go through Resolve dry-run, apply contract, readback, render, and final QA.

## Transition Rules

Between days and places, prefer real visual bridge clips:

- station platforms, train windows, taxi/road footage, airport movement
- wide skyline or aerial inserts
- street ambience and signage
- weather, hotel window, elevator/escalator, night-to-day changes
- food/table shots when moving into a slower chapter

Reject transitions that are only black cards, hard cuts, or generic text.

## Audio Rules

When the user requests no voiceover, scenic/title/transition sections must be BGM-led.

- Build a continuous BGM bed from approved local tracks.
- Materialize the selected bed with `prepare_bgm_phrase_blueprint.py` before rhythm recut or Resolve apply, so opening/title, route transitions, scenic bridges, and ending sections carry BGM phrase cue metadata.
- Use relaxed, travel-friendly moods: serene, atmospheric, chillout, reflective, warm, hopeful, soft cinematic.
- Avoid aggressive sports/trailer tracks unless the scene demands impact.
- Muted source camera audio is the default for scenic establishing shots.
- Source audio can appear only when it adds real place texture and is intentionally mixed.

## Subtitle And Text Rules

- Captions should support story, route, and emotion rather than repeat obvious visuals.
- Use short, natural Chinese sentences.
- Keep title typography separate from subtitles. Never let a subtitle overlap the hero title safe zone.
- Use consistent subtitle styling across the whole film.
- Export narration TXT/SRT when voiceover is rejected; do not sneak in generated voice.

## Visual QA Rules

Always create a contact sheet from the final render with:

- opening title samples
- every chapter title
- every day/place transition
- the exact timestamps from user feedback
- several mid-film subtitle samples
- ending samples

Before final render exists, generate a machine-readable feedback plan so the exact rejected failures are not retyped from memory:

```bash
python3 <skill-dir>/scripts/prepare_feedback_regression_plan.py --package-dir <package>
```

The plan must carry opening-title, 7:04 portrait, 7:04 BGM/voice, and opening BGM/no-voiceover probes into the pre-render audio policy, post-render feedback audit, and final QA suite.

Block delivery if the contact sheet shows:

- duplicate/ghosted titles
- portrait clips with black side bars in a 16:9 master
- black slates pretending to be title cards
- generic text instead of route-specific city/place titles
- sparse subtitles or unreadable text
- scenic sections that rely on source-camera voice instead of music

## Local Reference Extraction

For any user-supplied long-form local reference film, analyze:

- average shot length and chapter pacing
- where music changes happen
- how titles appear and disappear
- how transport/streets/food/interiors connect destinations
- subtitle density and tone
- how long scenic shots are allowed to breathe
- cover/title card construction when screenshots or title frames are provided: background recognizability, title scale, Chinese/English hierarchy, color contrast, platform safe zones, and absence of internal labels

Use those observations as pacing targets, not as assets to copy.

When multiple local reference videos are available, generate a batch profile before rhythm/style judgments:

After the downstream story, rhythm, creator-cut, transition, caption, audio, and style artifacts exist, run `audit_reference_profile_application_contract.py` and read `reference-profile-application-contract.md` so the reference batch profile is proven applied instead of left as unused analysis. Keep `source-selection-repair-contract.md`, `final-blueprint-lineage-contract.md`, `transition-cadence-contract.md`, and `final-source-usage-contract.md` in the style handoff so source repair, candidate lineage, cadence, and final raw-source usage remain explicit.

```bash
python3 <skill-dir>/scripts/prepare_reference_batch_profile.py --reference-dir <reference-folder> --package-dir <package>
```

This writes `reference/reference_batch_profile.json` and a compatibility `reference/reference_analysis.json` so edit rhythm, reference-style, and repair planning use aggregate measured pacing/audio/sample-frame targets instead of a few screenshots.

When the user asks to learn from the four downloaded `叽叽歪歪的平行世界` videos, do not stop at random frame sampling. Review full-film timeline strips, opening strips, ending strips, transition context, and cover screenshots, then apply `parallel-world-vlog-style.md` as the reusable non-copying standard.

Observed reusable traits from the V14 training reference pass:

- Duration is about 39.91 minutes, so the pacing target is long-form documentary vlog rather than a compressed recap.
- The enriched local profile detects about 406 shots at scene threshold `0.35`, with average shot length about 5.9 seconds, median about 3.1 seconds, 19 long shots over 20 seconds, and 190 quick shots under 3 seconds. Treat this as a rhythm reference: varied short connective beats plus occasional breathing shots, not a flat slideshow or a hyper-cut short.
- The audio profile reports continuous audio with mean volume around `-22.8 dB` and no detected long silence at `-45 dB`/1s, so future no-voiceover cuts still need a continuous BGM/ambience bed instead of empty scenic/title sections.
- The generated sample-frame worksheet should be visually classified for transport, street, lived-in detail, landmark, food/interior, talking-head/context insert, and scenic breathing shots before claiming a future package matches the reference direction.
- Transport is part of the story: ferry/boat-window views, road footage, car interiors, parking, train/vehicle movement, and arrival moments create route continuity.
- Human presence matters: car conversations, restaurant/table moments, walking reactions, and occasional direct-to-camera explanation make the travel feel lived-in.
- The edit mixes scenic payoff with practical travel texture: coastline, streets, museums/signage, food closeups, parking/arrival, night driving, and quiet observational frames.
- Educational/context inserts can appear, such as flags, maps, museum signs, or historical panels, but they should be integrated as a travel chapter beat rather than dumped as slideshow filler.
- A 20-minute Japan cut should keep enough breathing room for station/platform/train/street/food/weather details instead of rushing from landmark to landmark.
- If the user rejects voiceover, the reference-like feeling should come from subtitles, BGM, scene ordering, and natural ambient texture rather than generated narration.
- When reference-style, director-intent, director-polish, or final QA audits are blocked, generate `reference_style_repair_plan/reference_style_repair_plan.json`, run `reference_repair_closure_audit.json`, and fix/close P0 rows before another Resolve write.
- Before Resolve apply or final QA handoff, run `audit_large_source_unattended_readiness_contract.py`, `audit_final_blueprint_lineage_contract.py`, `audit_effect_motion_application_contract.py`, `audit_reference_profile_application_contract.py`, and `audit_final_source_usage_contract.py` so large unordered source folders are fully indexed/recognized/selected before style work, BGM phrase, effect motion, bridge sequence, transition execution, rhythm recut, transition polish, and reference-profile application work is present in the active/final blueprint and downstream plans, restrained effects are not dropped or overused, and the final raw clips still come from footage-select hero/main/texture choices rather than unmatched or utility-dominant source material.

Expected generated evidence inside each delivery package:

```text
<package>/reference/reference_analysis.md
<package>/reference/reference_analysis.json
<package>/reference/reference_batch_profile.json
<package>/reference/reference_batch_profile.md
<package>/reference/reference_contact_sheet.jpg
<package>/reference/reference_frame_samples/
```
