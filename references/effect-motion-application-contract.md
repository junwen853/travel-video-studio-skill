# Effect Motion Application Contract

Use this contract after `prepare_effect_motion_blueprint.py` and `audit_final_blueprint_lineage_contract.py`. It proves that restrained title reveals, rotation/whip/speed-ramp choices, and other effect-motion rows survived into the final Resolve blueprint instead of remaining candidate-only metadata.

## Command

```bash
python3 <skill-dir>/scripts/audit_effect_motion_application_contract.py \
  --package-dir <package> \
  --json
```

Optional explicit blueprint check:

```bash
python3 <skill-dir>/scripts/audit_effect_motion_application_contract.py \
  --package-dir <package> \
  --blueprint <package>/resolve_timeline_blueprint.json \
  --json
```

## Required Inputs

- `effect_motion_blueprint/effect_motion_blueprint_report.json`
- `effect_motion_blueprint/resolve_timeline_blueprint_effect_motion.json`
- `final_blueprint_lineage_contract_audit.json`
- the final active or explicitly supplied Resolve blueprint

## Pass Criteria

- `effect_motion_blueprint_report.json` is `ready_with_effect_motion_blueprint`.
- Every materialized effect-motion row exists in the final blueprint.
- Final rows keep clip annotations and timeline markers, not only top-level prose metadata.
- Title reveals remain title-zone safe, BGM-only, source-evidence backed, and restrained.
- Rotation, whip, speed-ramp, push, or slide rows have motion evidence and stay under the film-level motion allowance.
- Effect duration and intensity remain restrained.
- No glitch, random spin, flash, shake, particle, logo reveal, or template-pack style appears.
- `final_blueprint_lineage_contract_audit.json` has passed.

## Repair Route

If blocked, do not add more effects. Rebuild the chain from the latest effect-motion candidate: repair `effect_motion_plan`, rerun `prepare_effect_motion_blueprint.py`, rerun BGM phrase, rhythm recut, transition polish, final blueprint lineage, and then rerun this contract. If motion effects are overused, replace weaker motion rows with match cuts, clean dissolves, or bridge footage before Resolve apply.
