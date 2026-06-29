# Timeline Variety Contract

## Purpose

`audit_timeline_variety_contract.py` is the film-level shot-function gate. It blocks a draft that technically has transitions, BGM, and selected sources but still feels like a flat AI montage because the final timeline repeats the same source, same visual function, or same utility-style footage.

Use it after these upstream reports exist:

- `edit_rhythm_plan/edit_rhythm_plan.json`
- `creator_cut_plan/creator_cut_plan.json`
- `final_blueprint_lineage_contract_audit.json`
- `transition_cadence_contract_audit.json`
- `final_source_usage_contract_audit.json`
- `creator_cut_application_contract_audit.json`
- `reference_scene_grammar_contract_audit.json`

## Command

```bash
python3 <skill-dir>/scripts/audit_timeline_variety_contract.py \
  --package-dir <package>
```

The script writes:

- `timeline_variety_contract_audit.json`
- `timeline_variety_contract_audit.md`

It is read-only. It does not write Resolve, queue renders, download assets, or modify source footage.

## Pass Criteria

A passed report means:

- the final candidate uses footage-select hero/main/texture decisions, not unmatched or repair/reject sources;
- creator-cut application matched every visual clip and no weak, rejected, or utility-heavy clip run remains;
- the full film includes route movement, lived-in/street texture, destination/landmark payoff, and ending aftertaste;
- edit-rhythm rows are decision-complete and no chapter still needs variety or retiming;
- transition cadence and final blueprint lineage passed, but they are not being used to hide weak shot choice;
- reference scene grammar proved the opening, chapters, and ending carry the same function variety.

## Blocked Means Repair

If this audit blocks, repair the named owner report instead of adding more decorative effects:

- source repetition or reject/repair footage: repair `final_source_usage_contract_audit.json`;
- same function or weak active clips: repair `creator_cut_application_contract_audit.json`;
- missing movement/texture/payoff/aftertaste: repair `creator_cut_plan.json`, `edit_rhythm_plan.json`, or the final blueprint;
- chapter variety gaps: repair `edit_rhythm_plan.json` and `chapter_arc_plan.json`;
- transition polish hiding weak material: repair `transition_cadence_contract_audit.json` and `final_blueprint_lineage_contract_audit.json`;
- weak opening/chapter/ending structure: repair `reference_scene_grammar_contract_audit.json`.

Rerun this audit before Resolve apply, final QA, maturity, or V14 baseline claims.
