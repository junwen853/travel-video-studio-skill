# Transition Motion Direction Contract

Run `scripts/audit_transition_motion_direction_contract.py` after `prepare_transition_choreography_plan.py`, `audit_transition_choreography_contract.py`, `audit_transition_visual_match_contract.py`, and `audit_transition_effect_palette_contract.py`, before preview packet, audition packet, storyboard, Resolve apply, final QA, maturity, unattended first-draft, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_motion_direction_contract.py \
  --package-dir <package>
```

## Contract

The audit passes only when:

- the transition choreography plan and choreography contract are ready/passed
- visual-match and effect-palette contracts are passed
- every visible motion transition has `motionDirectionPlan.required=true`
- whip, rotation, push, and speed-ramp rows have effect direction and landing direction
- the effect direction matches source or bridge motion instead of inventing a random move
- direction confidence meets the configured threshold
- important motion boundaries retain bridge or route-direction support
- rotation remains explicit or subtle, and speed ramps follow travel or zoom motion
- motion accents stay BGM-hit aligned and title/subtitle safe

No motion rows is acceptable. This contract blocks only when visible motion effects exist without directional proof.

## Repair

Do not repair a blocked row by adding a stronger effect. Repair one of these upstream facts:

- add real bridge footage with clear route movement
- choose a landing shot whose motion direction matches the outgoing shot
- downgrade the row to a match cut, dissolve, or clean cut
- update transition grammar/choreography evidence with actual directional terms
- remove rotation/whip/speed ramp where source footage does not support it

After repair, rerun choreography plan, choreography contract, motion-direction contract, preview packet, audition packet, storyboard, reference-transition-profile, unattended first-draft, V14 baseline, and maturity checks.

## Safety

The audit reads package-local JSON and writes package-local audit files only. It does not write Resolve, queue renders, download assets, modify source footage, or touch source drives.
