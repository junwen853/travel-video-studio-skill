# Transition Choreography Contract

Run `scripts/audit_transition_choreography_contract.py` immediately after `prepare_transition_choreography_plan.py` and before preview/audition/storyboard approval, Resolve apply, final QA, maturity, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_choreography_contract.py \
  --package-dir <package>
```

## Contract

The audit passes only when:

- the choreography plan status is `ready_with_transition_choreography_plan`
- every choreography row is ready
- every important transition has outgoing, bridge-or-motion, and landing beats
- BGM choreography targets a phrase hit within the allowed tolerance
- captions and titles have a quiet zone around the transition hit
- motion accents cite source motion, two-sided motion, or physical bridge evidence
- rotation remains subtle and no row uses high-intensity effect language
- family repetition and dominant-family share stay below the configured limits

## Expected Artifacts

- `transition_choreography_contract_audit.json`
- `transition_choreography_contract_audit.md`

## Repair

If blocked, repair the upstream transition grammar/execution/bridge/visual-match evidence first. Do not solve a blocked choreography row by adding a stronger effect. Add bridge footage, select a better landing shot, downgrade to a clean cut/match cut, or choose a quieter dissolve that fits the BGM phrase and title zone.

After repair, rerun choreography plan, choreography contract, preview packet, audition packet, storyboard, reference-transition-profile, unattended first-draft, V14 baseline, and maturity checks.

## Safety

The audit reads package-local JSON and writes package-local audit files only. It does not write Resolve, queue renders, download assets, modify source footage, or touch source drives.
