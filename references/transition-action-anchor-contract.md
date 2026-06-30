# Transition Action Anchor Contract

Run `scripts/audit_transition_action_anchor_contract.py` after `prepare_transition_execution_blueprint.py` and `audit_transition_cutpoint_contract.py`, before `audit_transition_sensory_continuity_contract.py`, transition preview, audition, storyboard, Resolve apply, final QA, maturity, unattended first-draft, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_action_anchor_contract.py \
  --package-dir <package> \
  --json
```

It writes:

- `transition_action_anchor_contract_audit.json`
- `transition_action_anchor_contract_audit.md`

## Contract

Every transition candidate must carry `transitionActionAnchorPlan` proving:

- outgoing anchor: the cut leaves from a readable action, route cue, gesture, object, scenic edge, or signage clue
- bridge-or-match anchor: the middle beat is a real bridge, visual match, dissolve reason, or restrained motion connector
- landing anchor: the next shot lands on a stable readable place, subject, texture, payoff, or route orientation
- motion anchor: whip, rotation, push, and speed-ramp accents have directional action evidence and match the landing direction
- important boundary resolution: chapter, title, route-gap, and ending joins resolve through bridge, match, breath, or aftertaste instead of a naked effect
- cutpoint dependency: the action anchors sit on a ready outgoing/hit/landing cutpoint plan

## Repair Rules

Do not repair a blocked action-anchor row by adding a stronger effect. Repair the source join:

- choose a clearer outgoing exit frame or trim earlier/later to a readable action
- insert street, transport, signage, food, weather, hotel, walking, or other route texture bridge footage
- replace weak landing clips with creator-cut hero/main/texture picks
- downgrade rotation, whip, push, or speed-ramp to a clean match cut or short dissolve when directional action is weak
- keep title/subtitle quiet zones and BGM-only audio intact after the anchor repair

After repair, rerun transition execution blueprint, cutpoint contract, action-anchor contract, sensory-continuity contract, microstructure, preview, audition, storyboard, unattended first-draft, V14 baseline, and maturity checks.

## Safety

The audit reads package-local JSON and writes package-local audit files only. It does not write Resolve, queue renders, download assets, modify source footage, or touch source drives.
