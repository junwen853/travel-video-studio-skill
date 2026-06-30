# Transition Source Coverage Contract

Use `scripts/audit_transition_source_coverage_contract.py` after transition grammar is planned and before transition reference selection, preview, audition, Resolve apply, final QA, Skill maturity, or V14 baseline claims.

This gate exists because a transition can look valid in planning text while the cut still feels mechanical: the row may name a rotation, match cut, speed ramp, or bridge, but the actual source selection does not contain usable outgoing, bridge, motion, or landing material. The contract checks source-level evidence before effects are allowed to hide a weak pair.

## Required Inputs

- `transition_grammar_plan/transition_grammar_plan.json`
- `footage_select_plan/footage_select_plan.json`
- `creator_cut_plan/creator_cut_plan.json`
- `edit_rhythm_plan/edit_rhythm_plan.json`
- `transition_bridge_plan/transition_bridge_plan.json`

## Pass Criteria

- Every transition row has outgoing and landing evidence from footage selection, creator-cut, or edit-rhythm planning.
- Important chapter, timeline-gap, title, and ending boundaries have route/bridge source coverage before a visible effect is approved.
- Motion transitions such as whip, rotation, speed ramp, or push/slide require two-sided motion terms plus route/bridge source material.
- Match cuts require shared visual terms or source-function support, not only adjacent timestamps.
- Weak, repair, reject, or utility-only clips cannot be saved by flashy transitions.
- `insert_bridge_first` or `needs_bridge_insert` rows remain blockers until bridge footage is selected or materialized.

## Outputs

- `transition_source_coverage_contract_audit.json`
- `transition_source_coverage_contract_audit.md`

## Repair

If blocked, repair the source plan before changing effects:

- Replace weak outgoing or landing clips through `prepare_footage_select_plan.py`, `prepare_source_selection_repair_plan.py`, or `prepare_creator_cut_plan.py`.
- Add local transport, street, signage, hotel, food, weather, skyline, water, or aerial bridge clips through `prepare_transition_bridge_plan.py`.
- Downgrade motion transitions to match cuts, short dissolves, or straight cuts when motion evidence is one-sided or decorative.
- Rerun transition grammar, source coverage, visual match, choreography, preview/audition, final-cut smoothness, unattended-first-draft, V14 baseline, and final QA after repair.

## Safety

The audit is read-only. It does not write Resolve, queue renders, download assets, modify source footage, or modify source drives.
