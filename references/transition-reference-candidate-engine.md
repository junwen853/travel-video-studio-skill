# Transition Reference Candidate Engine

Use this engine after `prepare_transition_grammar_plan.py` and `prepare_transition_execution_plan.py`, and before motif, bridge-sequence, choreography, preview, audition, storyboard, reference-transition-profile, unattended-first-draft, V14, maturity, final QA, or Resolve apply claims.

The purpose is to turn vague feedback like "make the transitions closer to Parallel World/Malta" into a row-level A/B/C candidate ladder. It does not copy a creator's exact edit. It uses the reference profile only as a non-copying balance target: clean continuity and visual matches carry most cuts, physical bridge or scenic breath carries important route/title/day changes, and whip/rotation/speed-ramp accents stay rare, motivated, and separated by stable landing footage.

## Command

```bash
python3 <skill-dir>/scripts/prepare_transition_reference_candidates.py \
  --package-dir <package> \
  --json
```

## Inputs

- `transition_grammar_plan/transition_grammar_plan.json`
- `transition_execution_plan/transition_execution_plan.json` when available
- `reference/reference_batch_profile.json` or `reference/reference_analysis.json` when available
- `transition_choreography_plan/transition_choreography_plan.json` when available
- `bgm_phrase_blueprint/bgm_phrase_blueprint_report.json` when available

## Outputs

- `transition_reference_candidates/transition_reference_candidates.json`
- `transition_reference_candidates/transition_reference_candidates.md`

Each row must include:

- source from/to clip names
- upstream grammar/execution style
- row status
- A/B/C transition candidates
- style family, intensity, duration frames
- Resolve implementation hint
- FFmpeg or local preview hint
- required evidence
- rejection reasons
- decision/readback fields

## Candidate Rules

- Important route or timeline jumps must choose physical bridge footage first. A dissolve or motion effect is allowed only after the route change has visual evidence.
- Title boundaries use scenic title breath, short mood dissolve after readability, or clean cut to texture. They must not use random route/date labels, stacked text, subtitles over title zones, or visible template effects.
- Ending transitions prefer aftertaste holds, gentle visual matches, or clean BGM cuts. Do not stop on leftover footage.
- Motion accents are allowed only when grammar shows route motion, bridge evidence, or two-sided movement. They must remain rare and separated.
- Clean cuts and visual matches are not "boring" when the source choice, rhythm, and BGM phrasing are strong. They are the default reference-like language.

## Pass Criteria

- Status is `ready_with_transition_reference_candidates`.
- Every adjacent visual boundary has at least one candidate, preferably three.
- Important boundaries have bridge, title-breath, or mood-breath candidates.
- Motion candidates stay within the reference target and are not clustered.
- Rows needing bridge footage are explicit as `needs_bridge_insert_before_effect`, not hidden behind flashy effects.
- The plan is consumed by preview/audition/storyboard, reference-transition-profile, unattended-first-draft, V14, maturity, and final QA before Resolve apply.

## Repair Route

If rows are missing, run transition grammar and execution first. If important rows need bridge footage, repair source selection, bridge sequence, scenic title bridge, visual establishing, or creator cut before approving Resolve. Do not fix missing route continuity by adding more rotation, whip, glitch, flash, push, zoom, or speed-ramp effects.
