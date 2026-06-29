# Creator Cut Application Contract

Use this contract after `prepare_creator_cut_plan.py` and after the final candidate blueprint exists, normally after transition polish or rhythm recut. The goal is to prove that the edit actually applies creator-style shot selection instead of only producing an advisory plan.

## Command

```bash
python3 <skill-dir>/scripts/audit_creator_cut_application_contract.py --package-dir <package>
```

Optional explicit candidate:

```bash
python3 <skill-dir>/scripts/audit_creator_cut_application_contract.py \
  --package-dir <package> \
  --blueprint <package>/transition_polish_blueprint/resolve_timeline_blueprint_transition_polish.json
```

## Inputs

- `creator_cut_plan/creator_cut_plan.json`
- optional `edit_rhythm_plan/edit_rhythm_plan.json`
- best package-local candidate blueprint in this order: transition polish, rhythm recut, BGM phrase, effect motion, transition execution, bridge sequence, then active `resolve_timeline_blueprint.json`

## Pass Criteria

- Every primary visual clip in the candidate matches a creator-cut row.
- Rejected rows (`reject_or_replace`, `reject_or_review`, `reject_excluded`) are not active unless the row has an explicit approved exception.
- Weak, placeholder, black, duplicate, obstructed, or generic clips are repaired, demoted, removed, or approved with evidence.
- Chapters with enough clips include movement plus texture/payoff variety; they are not only route labels or repeated utility footage.
- Same-source, same-function, utility-heavy, and low-diversity runs stay below the contract limits.
- The audit writes only package reports and never writes Resolve, queues renders, downloads assets, or modifies source footage.

## Outputs

- `creator_cut_application_contract_audit.json`
- `creator_cut_application_contract_audit.md`

## Repair Route

If blocked, do not hide the issue with a rotation, whip, zoom, or speed-ramp. First replace the weak active clip with a hero/main/texture candidate from the footage select or creator-cut plan. If the clip is needed for route honesty, record the exception in the creator-cut row decision fields, then rerun the audit. After changing the candidate blueprint, rerun transition readiness, reference scene grammar, unattended first-draft, final QA, maturity, and V14 baseline gates.
