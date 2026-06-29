# Source Selection Repair Contract

Use this contract after `footage_select_plan/footage_select_plan.json` exists and before opening, chapter, transition, stock/aerial, rhythm, creator-cut, or Resolve apply work begins.

The contract prevents a large unordered source folder from turning into a filename-order montage. A first draft is not trustworthy just because every source file was indexed and scored. Each chapter must have enough selected local material to support a travel-film arc:

- route movement or transport bridge
- lived-in texture
- destination payoff or title-capable place identity
- at least one ready hero/main/texture candidate
- no blocking orientation/repair/reject dependency

## Commands

```bash
python3 <skill-dir>/scripts/prepare_source_selection_repair_plan.py --package-dir <package> --project-dir <project>
python3 <skill-dir>/scripts/audit_source_selection_coverage_contract.py --package-dir <package>
```

The prepare script writes:

- `source_selection_repair_plan/source_selection_repair_plan.json`
- `source_selection_repair_plan/source_selection_repair_plan.md`

The audit script writes:

- `source_selection_coverage_contract_audit.json`
- `source_selection_coverage_contract_audit.md`

## Pass

The package passes only when:

- `source_selection_repair_plan.json` status is `ready_no_source_selection_repairs_needed`
- `source_selection_coverage_contract_audit.json` status is `passed`
- every chapter coverage row is `ready_with_chapter_selection_coverage`
- `blockingRepairRowCount` is `0`
- opening/ending hero, route movement, lived-in texture, and destination payoff pools exist
- warning repair rows, usually orientation repair rows, contain decision fields and are closed before final source usage approval

## Block

Block the first assembly when any of these happen:

- a chapter has no ready local source candidate
- a chapter lacks route movement, lived-in texture, or destination payoff coverage
- a large source pool has too few selected candidates for the chapter count
- repair/reject rows dominate the source pool
- there are not enough hero candidates for opening and ending confidence
- route movement bridges are too thin for day/place transitions

## Owner Scripts

Repair rows point to the next owner script:

- `prepare_footage_select_plan.py`: re-score, reject weak/derived rows, promote better candidates
- `prepare_transition_bridge_plan.py`: close movement/transport/day-jump bridge gaps
- `prepare_chapter_arc_plan.py`: close lived-in texture gaps
- `prepare_visual_establishing_plan.py`: close payoff, title, landmark, aerial, or ending gaps
- `prepare_creator_cut_plan.py`: shorten or restructure chapters when the local source pool is too thin
- `prepare_orientation_repair_package.py`: repair portrait/square/unknown footage before final source use

## Rerun After Repair

After closing any blocking repair row, rerun:

```bash
python3 <skill-dir>/scripts/prepare_source_selection_repair_plan.py --package-dir <package> --project-dir <project>
python3 <skill-dir>/scripts/audit_source_selection_coverage_contract.py --package-dir <package>
python3 <skill-dir>/scripts/audit_unattended_first_draft_contract.py --package-dir <package>
python3 <skill-dir>/scripts/audit_final_source_usage_contract.py --package-dir <package>
python3 <skill-dir>/scripts/run_final_qa_suite.py --package-dir <package>
python3 <skill-dir>/scripts/audit_skill_maturity_contract.py --package-dir <package>
python3 <skill-dir>/scripts/audit_v14_baseline_contract.py --package-dir <package>
```

This contract is non-destructive: it does not write Resolve, queue renders, download assets, or modify source footage.
