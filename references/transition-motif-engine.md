# Transition Motif Engine

Use this reference when shot-to-shot transitions still feel abrupt, repetitive, effect-heavy, or unlike the Parallel World/Malta references after transition grammar and execution plans exist.

## Purpose

`prepare_transition_motif_plan.py` reviews the whole transition chain, not only a single adjacent pair. It decides whether the film is using a deliberate set of motifs:

- `physical_route_bridge`: transport, walking, road, station, water, weather, hotel, street, food, skyline, or route evidence
- `visual_match`: shared object, shape, color, direction, window, road, water, sign, food table, or camera/action continuity
- `mood_dissolve`: time, weather, title, scenic aftertaste, ending, or memory-like transition
- `motivated_motion`: whip, rotation, or speed-ramp only with real two-sided/route motion evidence
- `title_clean_reveal`: clean title-boundary transition with subtitle/title-zone safety
- `simple_continuity`: straight cut or simple cut where the scene already connects

This layer prevents a technically valid transition plan from becoming a generic chain of repeated dissolves, random spins, template effects, or route jumps hidden behind titles.

## Command

```bash
python3 <skill-dir>/scripts/prepare_transition_motif_plan.py --package-dir <package> --json
python3 <skill-dir>/scripts/prepare_bridge_sequence_plan.py --package-dir <package> --json
```

Outputs:

- `<package>/transition_motif_plan/transition_motif_plan.json`
- `<package>/transition_motif_plan/transition_motif_plan.md`
- `<package>/bridge_sequence_plan/bridge_sequence_plan.json`
- `<package>/bridge_sequence_plan/bridge_sequence_plan.md`

## Inputs

Run this after:

- `prepare_transition_grammar_plan.py`
- `prepare_transition_execution_plan.py`

It also reads these artifacts when present:

- `transition_bridge_plan/transition_bridge_plan.json`
- `effect_motion_plan/effect_motion_plan.json`
- `bgm_selection_package/bgm_selection_package.json`
- `chapter_arc_plan/chapter_arc_plan.json`

## Repair Ownership

The motif plan creates repair rows instead of hiding weak transitions:

- missing physical bridge -> `prepare_transition_bridge_plan.py`
- unmotivated whip/rotation/ramp -> `prepare_effect_motion_plan.py`
- missing BGM phrase cue -> `prepare_bgm_selection_package.py`
- repeated transition style run -> `prepare_transition_grammar_plan.py`
- unsafe execution recipe -> `prepare_transition_execution_plan.py`

P0 rows must be resolved before final render or V14 baseline claims. P1 rows require review; repeated style is acceptable only when it is justified by real same-scene continuity.

## Acceptance Bar

Pass:

- `transition_motif_plan.json` exists and status is `ready_with_transition_motif_plan`
- every transition row has a motif, decision fields, BGM phrase cue, and title-zone policy when relevant
- motion motifs cite route/bridge/two-sided motion evidence
- bridge or motion failures create owner-script repair rows
- repeated style runs are detected and either repaired or explicitly justified
- important route/title/timeline-gap transitions are handed to `bridge_sequence_plan` so a single effect does not replace real connective footage

Reject:

- four or more adjacent transitions repeat the same style with no continuity reason
- spin, flash, glitch, shake, ramp, or rotation is used to hide weak footage
- a route jump has no physical bridge and no repair row
- title-boundary transitions lack subtitle/title-zone safety
