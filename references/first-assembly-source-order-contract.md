# First Assembly Source Order Contract

This contract prevents a large unordered source folder from becoming a filename-order montage or a blueprint-fallback sample cut.

## Required Inputs

- `raw_intake_completeness_audit.json`
- `footage_select_plan/footage_select_plan.json`
- `source_selection_repair_plan/source_selection_repair_plan.json`
- `source_selection_coverage_contract_audit.json`
- `delivery_plan.json`
- `resolve_timeline_blueprint.json`

## Pass Criteria

For large or unordered trips, the footage select plan must come from the project `media_index`, not from a small active-blueprint fallback. Every active source video must be represented in the selection plan, and raw intake must show no missing selection rows, active derived sources, or stale artifacts.

The first assembly must record `used_for_first_assembly_sort` in both `delivery_plan.json` and `resolve_timeline_blueprint.json`. Every delivery chapter must be sorted by footage-selection tier and score, with hero/main/texture candidates leading the cut.

Repair, reject, derived, portrait/square/unknown-orientation, and weak rows must not lead the first assembly. Chapter pools must already contain local movement, lived-in texture, and destination payoff coverage before transition effects, stock/aerial fallback, or rhythm recut tries to compensate.

## Outputs

- `first_assembly_source_order_contract_audit.json`
- `first_assembly_source_order_contract_audit.md`

The script is read-only. It does not write Resolve, queue renders, download assets, or modify source footage.
