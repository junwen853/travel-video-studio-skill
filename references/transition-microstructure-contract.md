# Transition Microstructure Contract

This contract prevents a travel film from passing QA with transition metadata that still feels like hard adjacent clips, repeated effect coverups, or unlanded BGM timing.

## Required Inputs

- `transition_quality_contract_audit.json`
- `shot_transition_boundary_contract_audit.json`
- `transition_motivation_contract_audit.json`
- `transition_pair_continuity_contract_audit.json`
- `transition_execution_readiness_contract_audit.json`
- `transition_polish_application_contract_audit.json`
- `resolve_transition_apply_contract_audit.json`
- `bridge_sequence_application_contract_audit.json`
- `final_blueprint_lineage_contract_audit.json`
- `transition_cadence_contract_audit.json`
- `transition_cutpoint_contract_audit.json`
- `transition_action_anchor_contract_audit.json`
- `transition_sensory_continuity_contract_audit.json`

All inputs must live inside the delivery package and must already be accepted by their own contracts.

## Pass Criteria

Every adjacent visual boundary must be audited and covered by transition rows. Each boundary must have:

- a package-local Resolve recipe or clean-cut decision
- a concrete BGM hit
- BGM-only transition audio
- title-safe timing
- pair-readiness evidence
- source handles
- ready cutpoint timing with outgoing tail, BGM-hit bridge/effect point, and readable landing hold
- ready action-anchor proof with outgoing action, bridge-or-match connector, stable landing shot, and directional motion anchor when a visible motion effect is used
- ready sensory-continuity proof with visual, BGM-only phrase-hit, caption quiet-zone, route/mood, motion-direction when applicable, and landing continuity channels
- motivated visual, route, bridge, motion, title, or BGM continuity

Weak adjacent-pair fit is not allowed. Motion transitions must have motion evidence, must remain under the film-level motion allowance, must not repeat as a local template run, and must not exceed the configured maximum transition duration.

Important route/title/timeline jumps must survive as materialized bridge beats with no source audio leakage. Visible effects must have a Resolve API, manual Resolve, Fusion, or bridge-clip apply path instead of marker-only metadata.

## Outputs

- `transition_microstructure_contract_audit.json`
- `transition_microstructure_contract_audit.md`

The script is read-only. It does not write Resolve, queue renders, download assets, or modify source footage.
