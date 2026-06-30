# Transition Cadence Contract

## Purpose

`audit_transition_cadence_contract.py` is the film-level transition rhythm gate. It does not replace pair-level transition audits; it summarizes them and blocks the edit when the whole film still feels like bare concatenation, a repeated template chain, or decorative effect spam.

Use it after these upstream reports exist:

- `transition_motif_plan/transition_motif_plan.json`
- `transition_quality_contract_audit.json`
- `shot_transition_boundary_contract_audit.json`
- `transition_motivation_contract_audit.json`
- `transition_pair_continuity_contract_audit.json`
- `transition_execution_readiness_contract_audit.json`
- `resolve_transition_apply_contract_audit.json`
- `bridge_sequence_application_contract_audit.json`
- `final_blueprint_lineage_contract_audit.json`

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_cadence_contract.py \
  --package-dir <package>
```

The script writes:

- `transition_cadence_contract_audit.json`
- `transition_cadence_contract_audit.md`

It is read-only. It does not write Resolve, queue renders, download assets, or modify source footage.

## Pass Criteria

A passed report means:

- every visual boundary has transition coverage;
- enough crafted transitions exist for the film length;
- motion transitions stay below the configured share and have evidence;
- repeated decorative runs stay below four;
- no single transition style dominates the film;
- important route/title/timeline-gap boundaries have materialized bridge-sequence beats;
- Resolve apply evidence is not marker-only;
- the final blueprint lineage proves the latest candidate chain survived.

## Blocked Means Repair

If this audit blocks, do not write Resolve or claim the draft is V14-quality. Repair the owner report named in `blockers`:

- bare-cut coverage: repair `transition_quality_contract_audit.json`;
- repeated-template cadence: repair `transition_motif_plan.json` or transition polish;
- unmotivated motion: repair motivation, pair-continuity, and execution-readiness rows;
- missing important bridge beats: repair bridge sequence plan/blueprint/application;
- marker-only visible effects: repair Resolve transition apply plan;
- stale candidate chain: repair final blueprint lineage and rerun later audits.

Rerun this audit after the upstream repair. A later final QA or maturity pass should treat a missing cadence audit as a Skill integration bug.
