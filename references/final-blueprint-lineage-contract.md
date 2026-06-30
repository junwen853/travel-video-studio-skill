# Final Blueprint Lineage Contract

Use this contract after transition-polish, bridge-sequence, creator-cut, rhythm-recut, BGM phrase, effect-motion, and transition-execution candidate work has produced ready reports.

The failure it prevents: an agent runs good planning and candidate-blueprint scripts, but the active `resolve_timeline_blueprint.json` used for Resolve still points at an older or partially updated timeline. That produces a draft that looks as if the Skill ignored its own experience.

Run:

```bash
python3 <skill-dir>/scripts/audit_final_blueprint_lineage_contract.py --package-dir <package>
```

For a candidate or forked package:

```bash
python3 <skill-dir>/scripts/audit_final_blueprint_lineage_contract.py \
  --package-dir <package> \
  --blueprint <package>/resolve_timeline_blueprint.json
```

The audit writes:

- `final_blueprint_lineage_contract_audit.json`
- `final_blueprint_lineage_contract_audit.md`

## Pass Criteria

- The final blueprint is inside the current package.
- At least five candidate-blueprint stages are ready by default.
- Every ready stage's report has a package-local `outputs.candidateBlueprint`.
- The final blueprint contains the stage plan key, such as `bgmPhraseBlueprintPlan`, `effectMotionBlueprintPlan`, `rhythmRecutPlan`, or `transitionPolishBlueprintPlan`.
- Materialized candidate metadata is not dropped from the final blueprint: BGM phrase rows, effect-motion rows, transition execution rows, bridge insert clips, rhythm recut annotations, and transition-polish rows must meet or exceed the latest ready report counts.

## Repair

If blocked, do not render or apply Resolve yet.

First identify the newest ready candidate stage that is missing from the final blueprint. Then either:

- rerun the downstream candidate script chain from that stage forward, or
- fork a clean apply package from the approved candidate blueprint, then rerun Resolve preflight, unattended-first-draft, package-integrity, final QA, Skill maturity, and V14 baseline gates.

Do not manually copy one metadata list into the final blueprint as a cosmetic fix. The final blueprint must reflect the real candidate lineage used for Resolve.
