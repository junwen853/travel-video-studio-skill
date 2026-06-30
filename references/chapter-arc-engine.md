# Chapter Arc Engine

Use this reference when a travel edit needs to feel like a complete long-form vlog chapter instead of a folder-order montage.

## Purpose

`prepare_chapter_arc_plan.py` creates one row per route/chapter and checks whether that chapter has the five beats that repeatedly appear in strong Parallel World/Malta-style travel films:

- `context`: person, reaction, route purpose, or clear viewer-facing reason
- `movement`: airport, station, train, road, walking, map, ticket, luggage, ferry, or practical travel motion
- `texture`: street, hotel, food, shop, sign, weather, room, waiting, crowd, or other lived-in detail
- `payoff`: landmark, skyline, coast, mountain, activity, museum/site, aerial, or strong destination reward
- `aftertaste`: quiet observation, dusk/night, departure, window/road callback, or bridge into the next chapter

The plan does not write DaVinci Resolve, render, download assets, or modify source footage. It turns the chapter story shape into a reviewable decision artifact before edit rhythm, creator cut, transition execution, subtitle overlay, BGM, or final QA claims.

## Command

```bash
python3 <skill-dir>/scripts/prepare_chapter_arc_plan.py --package-dir <package> --json
```

Outputs:

- `<package>/chapter_arc_plan/chapter_arc_plan.json`
- `<package>/chapter_arc_plan/chapter_arc_plan.md`

## Inputs

The script reads these files when present:

- `delivery_plan.json`
- `resolve_timeline_blueprint.json`
- `opening_story_plan/opening_story_plan.json`
- `edit_rhythm_plan/edit_rhythm_plan.json`
- `creator_cut_plan/creator_cut_plan.json`
- `transition_bridge_plan/transition_bridge_plan.json`
- `reference/reference_batch_profile.json`

It can infer chapter rows from `delivery_plan.json` first, then from blueprint `chapterIndex` values when the delivery plan has no chapters.

## How To Use The Rows

Each chapter row includes:

- target timeline window
- detected beat evidence and example clips
- missing beat IDs
- local source-search hints
- owner scripts for repairs
- decision fields for selected clips, captions, BGM, transition handoff, Resolve evidence, and readback evidence

Treat missing beats as structure work, not post-render polish. Repair them with source footage first:

- `context` -> `prepare_caption_story_plan.py`
- `movement` -> `prepare_footage_select_plan.py`
- `texture` -> `prepare_creator_cut_plan.py`
- `payoff` -> `prepare_visual_establishing_plan.py`
- `aftertaste` -> `prepare_transition_bridge_plan.py`

Only after real movement/bridge evidence exists should transition grammar or execution choose whip-pan, rotation, speed-ramp, or other motion effects. If evidence is missing, use straight cuts, short dissolves, or insert real bridge footage.

## Acceptance Bar

Pass:

- `chapter_arc_plan.json` exists and status is `ready_with_chapter_arc_plan`
- every chapter row has the full decision-field set
- missing beats, if any, are assigned to owner scripts before Resolve apply
- captions are audience-facing travel-film lines, not editor/status reports
- BGM and transition handoff fields explain how the viewer moves emotionally or geographically into the next chapter

Reject:

- a chapter is only scenic shots with no movement, texture, or aftertaste
- flashy effects hide a missing boundary
- captions report workflow state such as version, QA, Resolve, export, or fixes
- the edit claims Parallel World/Malta influence without chapter-level beat rows
