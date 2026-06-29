# Transition Visual Match Contract

`audit_transition_visual_match_contract.py` is the pair-level transition gate. It blocks a travel edit where adjacent clips technically have a transition row but the cut still feels arbitrary, template-like, or unsupported by the footage.

## Required Inputs

- `transition_grammar_plan/transition_grammar_plan.json`
- `transition_pair_continuity_contract_audit.json`
- `transition_execution_readiness_contract_audit.json`
- `transition_microstructure_contract_audit.json`
- `transition_scene_arc_contract_audit.json`
- `transition_effect_palette_contract_audit.json`

## Pass Criteria

- Every adjacent visual boundary has a transition grammar row.
- Every row has at least one concrete connection family: visual match, physical bridge, two-sided movement, mood/title reason, same-chapter continuity, or BGM phrase cue.
- Match cuts must cite shared visual terms such as window, skyline, water, road, sign, food, street, sky, color, shape, reflection, crowd, or their project-language equivalents.
- Whip, rotation, speed-ramp, or push transitions must have two-sided motion evidence plus physical route bridge evidence.
- Chapter, timeline-gap, title, and ending boundaries must have a bridge or scene-handoff reason. A title card alone is not enough.
- Reject or repair-tier clips cannot be hidden by a transition effect.
- Downstream pair-continuity, execution-readiness, microstructure, scene-arc, and effect-palette audits must agree with the row decisions.

## Outputs

- `transition_visual_match_contract_audit.json`
- `transition_visual_match_contract_audit.md`

## Safety

The audit is read-only. It does not write Resolve, queue renders, download assets, modify source footage, or modify source drives.
