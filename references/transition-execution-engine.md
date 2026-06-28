# Transition Execution Engine

Use this reference after `transition-grammar-engine.md` when the cut needs stronger shot-to-shot flow and the user expects actual DaVinci execution, not only transition suggestions.

## Purpose

The transition grammar plan decides the right transition type for every adjacent pair. The transition execution plan turns those decisions into Resolve-ready recipes that another agent can implement and audit.

This layer prevents these failures:

- "Add a transition" remains vague and never reaches the timeline.
- Whip, rotation, speed ramp, or dissolve effects are applied as decoration.
- A row marked `insert_bridge_first` gets hidden behind a flashy effect instead of repaired with real route footage.
- The transition looks good in prose but has no readback or frame-sample proof after Resolve apply.

## Required Script

Run this after `prepare_transition_grammar_plan.py` and before rhythm recut, Resolve blueprint updates, or Resolve apply:

```bash
python3 <skill-dir>/scripts/prepare_transition_execution_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_transition_motif_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_bridge_sequence_blueprint.py --package-dir <package>
```

The script writes:

- `transition_execution_plan/transition_execution_plan.json`
- `transition_execution_plan/transition_execution_plan.md`
- `transition_motif_plan/transition_motif_plan.json`
- `transition_motif_plan/transition_motif_plan.md`
- `bridge_sequence_plan/bridge_sequence_plan.json`
- `bridge_sequence_plan/bridge_sequence_plan.md`
- `bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json`
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.json`
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.md`

These scripts do not write Resolve, queue renders, download assets, or modify source footage.

## Execution Rules

Every transition row must state:

- approved transition type and fallback
- Resolve effect name or explicit `none_straight_cut`
- duration frames and handle needs
- bridge insert requirement
- BGM phrase cue
- title-zone subtitle suppression
- BGM-only/no-camera-voice policy
- exact Resolve implementation notes
- timeline readback evidence field
- render frame-sample evidence field

Allowed execution recipes:

- `none_straight_cut`: action, gaze, motion, or same-scene continuity.
- `none_or_2_frame_soft_cut`: visual match by shape, direction, object, color, water, road, window, skyline, sign, or food-table logic.
- `Cross Dissolve`: short mood, weather, time, title, or ending transition with enough handles.
- `Transform whip-pan match cut`: only when grammar shows route-motion energy on both sides.
- `Transform rotation match cut`: rare and subtle, only with turning, walking, vehicle, water, aerial, or camera-rotation evidence.
- `Speed ramp on real route bridge`: only on vehicle, aerial, water, crowd, walking, or real camera-motion footage.
- `none_until_bridge_inserted`: blocked until real bridge footage is selected.

## Rejections

Reject:

- random spin, flash, glitch, shake, particle, repeated whoosh, or template-pack transition
- motion effect across static scenic shots with no bridge evidence
- route jump hidden behind a title card
- transition covering unreadable title typography
- source-camera voice under scenic/title transition windows

## Acceptance Bar

Before Resolve apply:

- every transition grammar row has one execution recipe
- `insert_bridge_first` rows remain blocked until bridge footage is inserted
- whip/rotation/speed-ramp rows cite grammar motion or bridge evidence
- title-boundary rows suppress or trim subtitles in the title zone
- scenic/title/transition rows stay BGM-only
- approved recipes are copied into the Resolve blueprint or apply contract only after title, BGM, and bridge safety pass
- the transition motif plan proves the whole chain is not just repeated dissolves, random motion effects, or effects hiding weak route jumps
- the bridge sequence plan proves important route/title/timeline-gap transitions become 2-5 shot bridge beats instead of one effect hiding a missing travel bridge
- the bridge sequence blueprint report proves those beats have been materialized into a non-destructive candidate blueprint before Resolve apply
