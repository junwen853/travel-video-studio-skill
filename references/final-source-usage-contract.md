# Final Source Usage Contract

Run this after the final candidate blueprint exists and before Resolve apply, render, final QA, maturity, or V14 claims:

```bash
python3 <skill-dir>/scripts/audit_final_source_usage_contract.py --package-dir <package>
```

Optional explicit blueprint:

```bash
python3 <skill-dir>/scripts/audit_final_source_usage_contract.py \
  --package-dir <package> \
  --blueprint <package>/transition_polish_blueprint/resolve_timeline_blueprint_transition_polish.json
```

The audit proves the final active/candidate blueprint actually consumes `footage_select_plan/footage_select_plan.json` instead of merely planning selective source use. It treats package-local title cards, subtitle overlays, generated scenic bridges, stock/aerial assets, maps, and BGM-related media as generated/exempt assets only when their role/path proves that intent. Every real raw visual source must match a footage-select row by source path/name/basename.

Required pass conditions:

- `footage_select_plan.json` exists and has `ready_with_footage_select_plan` or `ready_with_blueprint_fallback_footage_select_plan`.
- The audited blueprint exists and is inside the package.
- Every final raw source clip matches a footage-select row.
- No `reject_or_review`, `reject_excluded`, `repair_before_use`, or `needs_editor_or_repair_decision` source appears without an approved repair/design exception.
- The final raw source set includes hero/main/texture selected candidates.
- Utility-context footage cannot dominate the source count or duration.
- Chapters with selectable candidate pools cannot end up with only utility or unmatched footage.
- Same-source repetition and low source diversity are blocked before effects are allowed to hide the problem.

Outputs:

- `final_source_usage_contract_audit.json`
- `final_source_usage_contract_audit.md`

If blocked, replace the offending final blueprint clips with hero, main story, or texture bridge candidates from `footage_select_plan.json`, or record a concrete approved exception in the selection row decision fields when route honesty requires a repair-design insert. Then rerun final source usage, creator-cut application, final-blueprint lineage, unattended-first-draft, final QA, Skill maturity, and V14 baseline gates.
