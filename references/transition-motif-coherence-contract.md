# Transition Motif Coherence Contract

Run this after the transition motif plan, reference selection, cadence, effect-palette, and scene-arc reports exist.

```bash
python3 <skill-dir>/scripts/audit_transition_motif_coherence_contract.py --package-dir <package>
```

Outputs:

- `transition_motif_coherence_contract_audit.json`
- `transition_motif_coherence_contract_audit.md`

## Purpose

This contract proves the whole film uses a coherent transition language instead of treating every adjacent pair as an isolated effect choice.

It blocks when:

- one motif or style dominates the whole film without reference-like variety
- four or more rows repeat the same motif/style chain
- route, chapter, title, timeline-gap, or ending boundaries lack bridge, match, dissolve, or title-reveal logic
- whip, rotation, or speed-ramp motifs appear too often, too close together, or in opening/title/ending moments
- the reference-selected transition family contradicts the motif row
- motif repair rows remain unresolved before final candidate claims

## Passing Standard

The audit passes only when:

- `transition_motif_plan.json` is `ready_with_transition_motif_plan`
- `transition_reference_selection.json` is `ready_with_transition_reference_selection`
- cadence, effect-palette, and scene-arc audits pass
- every motif row is BGM-cued and title-safe when needed
- important boundaries use `physical_route_bridge`, `visual_match`, `mood_dissolve`, or `title_clean_reveal`
- motion motifs are rare spaced accents, never an opening/title/ending crutch
- selected reference families match the motif language row by row

## Repair Order

1. Repair missing or weak motif rows in `prepare_transition_motif_plan.py`.
2. Repair candidate selection in `prepare_transition_reference_selection.py`.
3. Add physical bridge material through `prepare_bridge_sequence_plan.py` and `prepare_bridge_sequence_blueprint.py`.
4. Downgrade unsupported motion effects through `prepare_transition_grammar_plan.py` or `prepare_effect_motion_plan.py`.
5. Rerun cadence, effect-palette, scene-arc, motif-coherence, final QA, V14 baseline, and maturity gates.
