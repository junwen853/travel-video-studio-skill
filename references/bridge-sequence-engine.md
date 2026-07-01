# Bridge Sequence Engine

Use this reference when transitions still feel like single effects instead of observed travel, especially after transition grammar, execution, and motif plans exist.

## Purpose

`prepare_bridge_sequence_plan.py` turns adjacent-pair transition logic into a 2-5 shot bridge sequence. `prepare_bridge_sequence_blueprint.py` then materializes approved local beats into a non-destructive Resolve candidate blueprint. Together they prevent a cut from jumping from clip A to clip B with only a dissolve, spin, black card, or title card.

The sequence should explain the move:

- leave the previous place with a grounded cue
- show route motion when the trip changes place or day
- establish the next place with a local visual signal
- settle into lived-in texture such as street, food, hotel, weather, signage, or human-scale detail
- keep clean title holds free of subtitles, route/date clutter, and stacked text

This is non-copying reference application: use the Parallel World/Malta lesson that transitions often need connective tissue, not a copied transition preset.

## Command

```bash
python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package> --json
python3 <skill-dir>/scripts/prepare_bridge_sequence_blueprint.py --package-dir <package> --json
```

Outputs:

- `<package>/bridge_sequence_plan/bridge_sequence_plan.json`
- `<package>/bridge_sequence_plan/bridge_sequence_plan.md`
- `<package>/bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json`
- `<package>/bridge_sequence_blueprint/bridge_sequence_blueprint_report.json`
- `<package>/bridge_sequence_blueprint/bridge_sequence_blueprint_report.md`

## Inputs

Run this after:

- `prepare_transition_grammar_plan.py`
- `prepare_transition_execution_plan.py`
- `prepare_transition_motif_plan.py`

It also reads these artifacts when present:

- `resolve_timeline_blueprint.json`
- `transition_bridge_plan/transition_bridge_plan.json`
- `creator_cut_plan/creator_cut_plan.json`
- `edit_rhythm_plan/edit_rhythm_plan.json`

## Sequence Types

- `clean_title_bridge_sequence`: scenic pre-roll, one clean title hold, and a handoff to arrival or lived-in texture.
- `route_texture_bridge_sequence`: exit context, route motion, arrival establishing, and lived-in texture.
- `visual_match_sequence`: a short matching object/action/shape/color beat plus a grounding detail when needed.
- `ending_aftertaste_sequence`: payoff, departure/movement callback, and a music-tail image.
- `simple_continuity_sequence`: direct continuity with an optional detail beat.

## Repair Ownership

The plan creates repair rows instead of hiding weak continuity:

- missing bridge beats -> `prepare_footage_select_plan.py`
- title-zone overlap -> `prepare_title_typography_plan.py`
- upstream motif repair -> the owner script named by `transition_motif_plan.json`
- bridge beat materialization -> `prepare_bridge_sequence_blueprint.py`
- final active timeline replacement -> package fork, `--update-blueprint` after approval, or a Resolve apply contract after preflight

## Acceptance Bar

Pass:

- `bridge_sequence_plan.json` exists and status is `ready_with_bridge_sequence_plan`
- `bridge_sequence_blueprint_report.json` exists and status is `ready_with_bridge_sequence_blueprint` when local beat candidates are available
- every sequence row has decision fields, BGM phrase cue, title-zone safety, and required beat rows
- every required beat has a selected local candidate or approved verified fallback before the plan can be `ready`; missing local candidates create repair rows, but any `missingBeatRowCount`, `repairRowCount`, or `blockingBridgeSequenceIssueCount` above zero blocks V14/maturity claims
- important route/title/timeline-gap boundaries are represented as materialized candidate sequence beats, not only one transition effect

Reject:

- a city/day/place jump relies on a single dissolve, spin, black card, or title card
- a missing route-motion or lived-in beat is hidden by a flashy effect
- a bridge sequence plan is called ready while any required beat is still missing or only described in a repair row
- title bridge beats contain subtitles, route/date clutter, stacked titles, or workflow labels
- selected bridge footage has no local source path and no verified licensed fallback decision
- a bridge sequence plan remains prose-only when local candidate footage exists and can be placed in a candidate blueprint
