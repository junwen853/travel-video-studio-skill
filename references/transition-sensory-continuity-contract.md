# Transition Sensory Continuity Contract

Run `scripts/audit_transition_sensory_continuity_contract.py` after `prepare_transition_execution_blueprint.py`, `audit_transition_cutpoint_contract.py`, and `audit_transition_action_anchor_contract.py`, before transition preview, audition, storyboard, Resolve apply, final QA, maturity, unattended first-draft, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_sensory_continuity_contract.py \
  --package-dir <package>
```

## Outputs

- `transition_sensory_continuity_contract_audit.json`
- `transition_sensory_continuity_contract_audit.md`

## Contract

Every transition candidate must carry `transitionSensoryContinuityPlan` proving:

- visual continuity is readable from outgoing shot through connector into landing shot
- BGM phrase timing is present and transition audio remains BGM-only
- subtitles and titles have a quiet zone around the boundary
- important day/place/title/timeline/ending boundaries have route, bridge, mood, title-breath, or aftertaste continuity
- the landing shot is stable enough for the viewer to orient
- motion effects have matching source/bridge/landing direction and sensory motivation

This contract blocks "has an effect but still feels mechanical" edits: random adjacent clips, BGM-deaf transitions, subtitle/title collisions, decorative motion, or route jumps with no mood or texture handoff.

## Repair

Repair source and timeline choices before adding stronger effects:

- choose adjacent shots with matching subject, shape, direction, texture, route cue, or mood
- move the cut/effect to a BGM phrase hit and keep A1/A2 muted in scenic/title/transition windows
- suppress or move captions around fast motion and title reveals
- insert a short street, transport, signage, weather, food, hotel, or scenic bridge for important jumps
- extend the landing hold or replace the landing clip when the viewer cannot orient
- downgrade motion accents to clean cuts or match cuts when direction or sensory motivation is weak

After repair, rerun transition execution blueprint, cutpoint, action-anchor, sensory-continuity, microstructure, preview, audition, storyboard, unattended first-draft, V14 baseline, and maturity checks.

## Safety

The audit reads package-local JSON and writes package-local audit files only. It does not write Resolve, queue renders, download assets, modify source footage, or touch source drives.
