# Pacing Watchability Contract

## Purpose

`audit_pacing_watchability_contract.py` is the reference-calibrated viewing-rhythm gate. It blocks a package that passes source selection, transition, scene-flow, and final-cut checks but still feels like a flat asset dump, long raw-footage hold, or unreadable flicker montage.

Use it after these upstream reports exist:

- `edit_rhythm_plan/edit_rhythm_plan.json`
- `rhythm_recut_application_contract_audit.json`
- `timeline_variety_contract_audit.json`
- `reference_scene_grammar_contract_audit.json`
- `final_cut_smoothness_contract_audit.json`
- `final_blueprint_lineage_contract_audit.json`

## Command

```bash
python3 <skill-dir>/scripts/audit_pacing_watchability_contract.py \
  --package-dir <package>
```

The script writes:

- `pacing_watchability_contract_audit.json`
- `pacing_watchability_contract_audit.md`

It is read-only. It does not write Resolve, queue renders, download assets, or modify source footage.

## Pass Criteria

A passed report means:

- the final candidate blueprint is inside the package and readable;
- the edit rhythm plan proves a ready local reference pacing profile;
- average and median final visual shot lengths are inside the reference-calibrated target ranges;
- long non-scenic raw holds do not remain after rhythm recut;
- sub-register short clips do not form accidental flicker runs;
- each substantial chapter has at least one readable breathing, payoff, or aftertaste shot;
- upstream rhythm-recut, timeline-variety, scene-grammar, final-cut smoothness, and final-blueprint lineage gates passed.

## Blocked Means Repair

If this audit blocks, repair the edit instead of adding more effects:

- long flat shots: repair `rhythm_recut_blueprint` / `rhythm_recut_application_contract_audit.json`;
- short flicker runs: lengthen or remove unreadable micro-clips before Resolve apply;
- missing chapter breath: add a real scenic, payoff, aftertaste, or quiet texture clip from user footage;
- reference range mismatch: regenerate `edit_rhythm_plan` from the local reference profile and rebuild the latest candidate chain;
- missing upstream reports: rerun final QA in order rather than approving Resolve apply.

Rerun this audit before Resolve apply, final QA, maturity, or V14 baseline claims.
