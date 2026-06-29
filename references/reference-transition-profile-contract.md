# Reference Transition Profile Contract

Use this contract after reference-profile application, transition visual-match, transition choreography, preview/audition/storyboard, and before chapter-story-spine, unattended-first-draft, V14 baseline, maturity, final QA, or Resolve apply claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_reference_transition_profile_contract.py \
  --package-dir <package> \
  --json
```

For a one-reference calibration project only:

```bash
python3 <skill-dir>/scripts/audit_reference_transition_profile_contract.py \
  --package-dir <package> \
  --allow-single-reference \
  --min-reference-videos 1 \
  --json
```

## Required Inputs

- `reference/reference_batch_profile.json`
- `transition_effect_palette_contract_audit.json`
- `transition_visual_match_contract_audit.json`
- `transition_choreography_plan/transition_choreography_plan.json`
- `transition_choreography_contract_audit.json`
- `transition_storyboard_contract_audit.json`

## Pass Criteria

- The reference profile is ready, non-copying, and has pacing/audio/style targets.
- Effect palette, visual match, choreography, and storyboard reports pass with no blockers.
- Motion accents are rare: whip, rotation, push, and speed-ramp rows stay under the reference target and are not allowed to dominate the timeline.
- Clean continuity, visual-match cuts, mood dissolves, scenic title breaths, and ending aftertaste holds carry most boundaries.
- Important day/place/title/timeline-gap/ending transitions have bridge-or-breath coverage plus outgoing, bridge-or-motion, and landing choreography.
- Every transition row carries BGM-hit choreography and title/subtitle quiet-zone policy.
- No high-intensity, template, flash, or repeated effect chain is allowed.

## Repair Route

If blocked, repair transition evidence instead of weakening the contract. Typical fixes are:

- rerun or repair `prepare_transition_choreography_plan.py`
- add route/texture/scenic bridge beats for important boundaries
- replace repeated motion transitions with clean cuts, visual matches, mood dissolves, or scenic breaths
- rerun preview, audition, storyboard, unattended-first-draft, V14, and maturity audits
