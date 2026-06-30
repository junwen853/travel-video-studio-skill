# Transition Cutpoint Contract

Run `scripts/audit_transition_cutpoint_contract.py` after `prepare_transition_execution_blueprint.py` and before transition preview, audition, storyboard, Resolve apply, final QA, maturity, unattended first-draft, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_cutpoint_contract.py \
  --package-dir <package>
```

## Contract

The audit passes only when every transition candidate has an explicit `transitionCutpointPlan` proving:

- outgoing tail frames exist before the cut or effect
- the bridge, match, dissolve, or restrained motion accent lands on the BGM phrase hit
- the landing shot holds long enough for the viewer to orient before the next idea
- source pre-roll and post-roll handles are sufficient for the chosen transition duration
- title/subtitle quiet zones exist around the boundary
- scenic/title/transition audio remains BGM-only with no source-camera or voice leakage
- important chapter, title, route-gap, or ending boundaries resolve through bridge footage, visual match, title breath, or aftertaste instead of a naked hard cut

This contract is about timing. It does not decide which transition style is right; the grammar, reference-selection, choreography, motion-direction, visual-match, and breathing-room gates do that earlier. It blocks when an otherwise valid-looking transition still has no readable leave point, hit point, or landing point.

## Repair

Repair upstream rather than forcing a stronger effect:

- trim the outgoing clip to a readable action, scenic edge, gesture, or route cue
- move the bridge/effect hit to the nearest BGM phrase boundary
- increase the first readable landing hold
- choose a shorter transition if source handles are weak
- insert a route texture bridge for important day/place jumps
- suppress subtitles around the title or fast-motion boundary
- downgrade to a clean match cut when the cutpoint is strong without an effect

After repair, rerun transition execution blueprint, cutpoint contract, microstructure, breathing-room, preview packet, audition packet, storyboard, unattended first-draft, V14 baseline, and maturity checks.

## Safety

The audit reads package-local JSON and writes package-local audit files only. It does not write Resolve, queue renders, download assets, modify source footage, or touch source drives.
