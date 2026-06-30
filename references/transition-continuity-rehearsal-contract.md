# Transition Continuity Rehearsal Contract

Use this contract after transition storyboard, audition, sensory-continuity, breathing-room, effect-palette, scene-flow, and final-cut smoothness reports exist.

Run:

```bash
python3 <skill-dir>/scripts/audit_transition_continuity_rehearsal_contract.py \
  --package-dir <package>
```

This gate catches a failure that per-boundary checks can miss: every transition looks valid in isolation, but the film still feels random, jumpy, or like a stack of effects when watched continuously.

The audit reads:

- `transition_storyboard_contract_audit.json`
- `transition_sensory_continuity_contract_audit.json`
- `transition_audition_quality_contract_audit.json`
- `transition_audition_visual_proof_contract_audit.json`
- `transition_audition_role_integrity_contract_audit.json`
- `transition_breathing_room_contract_audit.json`
- `transition_effect_palette_contract_audit.json`
- `transition_cadence_contract_audit.json`
- `reference_transition_profile_contract_audit.json`
- `scene_flow_arc_contract_audit.json`
- `final_cut_smoothness_contract_audit.json`

Pass criteria:

- every upstream report is accepted
- every storyboard row is ready and every sensory-continuity row is ready
- each row has viewer purpose, outgoing evidence, landing evidence, and required audition evidence
- the landing of row `N` connects to the outgoing evidence of row `N+1` through source identity or visual/route terms
- motion/rotation/whip/speed-ramp/BGM-handoff rows are not adjacent without a stable buffer row
- important route/title/time-jump boundaries do not stack back-to-back without scene breath
- high-impact purpose runs do not dominate the film
- breathing-room, scene-flow, final-cut smoothness, cadence, and effect-palette reports have no unresolved blockers

If this audit blocks, do not approve Resolve apply, final QA, V14 baseline, or Skill maturity. Repair by changing the shot order, adding stable route/texture bridge footage, downgrading adjacent motion effects to match cuts or clean cuts, or adding a quieter landing beat between important transitions. Then rerun storyboard, audition, sensory-continuity, breathing-room, continuity rehearsal, unattended-first-draft, V14, maturity, and final QA.
