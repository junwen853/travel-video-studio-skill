# Transition Effect Palette Contract

`audit_transition_effect_palette_contract.py` is the film-level effect-palette gate. It blocks a travel edit that technically has transitions but still feels amateur because the whole film relies on one default style, repeated template effects, or too many rotation/whip/speed-ramp moves.

## Required Inputs

- `transition_motif_plan/transition_motif_plan.json`
- `transition_cadence_contract_audit.json`
- `transition_microstructure_contract_audit.json`
- `transition_scene_arc_contract_audit.json`
- `transition_quality_contract_audit.json`
- `transition_pair_continuity_contract_audit.json`
- `transition_execution_readiness_contract_audit.json`
- `timeline_variety_contract_audit.json`
- `final_source_usage_contract_audit.json`
- `creator_cut_application_contract_audit.json`

## Pass Criteria

- The transition chain has enough palette families for the number of boundaries: clean/simple continuity, visual match, mood dissolve, physical bridge, title reveal, and rare motivated motion.
- Motion effects are accents, not the language of the whole film. Rotation, whip, push, and speed ramp must stay under the configured share and must carry route/motion evidence.
- No motif or style dominates the film. Repeated template runs are blocked unless upstream motif planning repairs them.
- Important route, title, timeline-gap, and ending boundaries have physical bridge or scene-arc proof.
- The palette supports strong shot choice and creator-cut decisions instead of hiding weak, rejected, repair, or utility footage.

## Outputs

- `transition_effect_palette_contract_audit.json`
- `transition_effect_palette_contract_audit.md`

The audit is read-only. It does not write Resolve, queue renders, download assets, modify source footage, or modify source drives.
