# Opening Story Engine

Use this reference when a travel edit needs to feel closer to the four `叽叽歪歪的平行世界` videos or the Malta final, especially when the first minutes feel generic, AI-made, over-titled, or disconnected from the actual route.

## Purpose

The first three minutes decide whether a long travel film feels authored. A strong opening is not only a title card or a pretty montage. It must give the viewer a reason to watch, prove the destination visually, and then return to practical travel reality.

The Opening Story Engine checks six beats:

- viewer promise: why should the viewer keep watching?
- destination proof: can the viewer immediately tell where this trip is going?
- clean hero title: is there one readable place title on real footage, without route/date/internal clutter?
- practical arrival: does the film show airport, train, car, station, road, walking, luggage, ticket, ferry, or hotel arrival?
- lived-in texture: does the film show street, food, hotel, sign, room, weather, crowd, shop, or waiting detail before minute three?
- first handoff: does the opening transition into the first chapter with route or lived-in bridge material rather than a hard reset?

## Required Script

Run this after the first package blueprint exists and before trusting title, BGM, visual establishing, edit rhythm, or director-intent claims:

```bash
python3 <skill-dir>/scripts/prepare_opening_story_plan.py --package-dir <package>
```

The script writes:

- `opening_story_plan/opening_story_plan.json`
- `opening_story_plan/opening_story_plan.md`

It does not write Resolve, download assets, or modify source footage. It turns the first three minutes into auditable beat rows with evidence clips and decision fields.

## Acceptance Bar

Before Resolve apply:

- the first 40 seconds contain a viewer promise backed by real destination or route footage
- the first minute contains a readable destination proof clip such as aerial, skyline, coast, landmark, city, station, bridge, or street identity
- the hero title is one short city/place title on real video, not a black card or stacked route/date label
- the edit returns to practical arrival or route material before minute three
- the opening includes lived-in details before the first main chapter payoff
- the first handoff uses movement, street, hotel, food, weather, or signage evidence
- scenic/title/opening windows stay BGM-led and suppress subtitles inside the hero-title safe zone

Reject openings that:

- start with a black slate, generic country card, or cluttered route/date title
- show only disconnected scenic shots with no route proof
- spend three minutes on explanation without practical arrival footage
- use stock/aerial beauty shots while ignoring usable local route or texture clips
- expose internal labels, project names, edit status, or tool terms in visible text

## Downstream Order

Use this order for a strong first draft:

1. `prepare_footage_select_plan.py` to select the raw source pool.
2. `build_delivery_package.py` to create the initial blueprint using selected local footage.
3. `prepare_opening_story_plan.py` to verify the first three minutes have story intent.
4. `prepare_title_typography_plan.py` and `prepare_visual_establishing_plan.py` to materialize clean title and establishing evidence.
5. `prepare_audio_scene_policy_plan.py` and `prepare_bgm_selection_package.py` to keep the opening BGM-led.
6. `prepare_edit_rhythm_plan.py`, `prepare_creator_cut_plan.py`, and `prepare_transition_grammar_plan.py` to polish the selected timeline.

Do not claim a cut has Parallel World/Malta-style direction if the opening story plan is missing or if any of the six opening beats has no evidence.
