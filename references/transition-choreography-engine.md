# Transition Choreography Engine

Use `scripts/prepare_transition_choreography_plan.py` after `audit_transition_visual_match_contract.py` and before transition preview, audition, storyboard, final QA, maturity, or V14 claims.

## Purpose

Visual-match evidence says two adjacent shots can connect. Choreography says how the viewer should experience that connection: the outgoing action, the bridge-or-motion beat, the landing action, the BGM phrase hit, the caption quiet zone, and the restrained effect family.

This is the layer that prevents a technically valid transition plan from feeling like generic hard cuts, repeated dissolves, random rotations, or effect templates.

## Command

```bash
python3 <skill-dir>/scripts/prepare_transition_choreography_plan.py \
  --package-dir <package>
```

## Inputs

- `transition_execution_plan/transition_execution_plan.json`
- fallback `transition_grammar_plan/transition_grammar_plan.json`
- visual-match, bridge, scene-arc, effect-palette, BGM phrase, and pair-continuity evidence when available

## Outputs

- `transition_choreography_plan/transition_choreography_plan.json`
- `transition_choreography_plan/transition_choreography_plan.md`

## Required Behavior

Every row should carry:

- `choreographyFamily`: clean continuity, visual match, scenic title breath, route bridge triptych, motivated motion accent, mood dissolve, texture bridge cutaway, or ending aftertaste.
- `threeBeatChoreography`: outgoing, bridge-or-motion, and landing actions.
- `bgmChoreography`: cut or effect aligned to a BGM phrase hit with tight tolerance.
- `captionAndTitlePolicy`: title collision avoidance and subtitle quiet zone.
- `intensity`: restrained intensity; rotation must stay subtle.
- `motionEvidence`: source movement, two-sided motion, or physical bridge proof for whip, rotation, push, and speed-ramp rows.

## Blockers

Block or repair when:

- an important day/place/title/timeline-gap/ending transition lacks outgoing, bridge-or-motion, and landing beats
- motion or rotation is chosen without physical motion or bridge evidence
- the same choreography family repeats too long or dominates the film
- the transition language contains flash, glitch, shake, strobe, template, particle, whoosh, or random spin terms
- BGM hit alignment or caption/title quiet-zone metadata is missing

## Safety

The script writes package-local plan files only. It does not write Resolve, queue renders, download assets, modify source footage, or touch source drives.
