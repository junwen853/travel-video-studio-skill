# Transition Reference Selection Engine

Use this engine after `prepare_transition_reference_candidates.py` and before `prepare_transition_execution_blueprint.py`, motif, bridge-sequence, choreography, preview, audition, storyboard, transition polish, unattended-first-draft, V14, maturity, final QA, or Resolve apply claims.

The candidate engine creates A/B/C choices. This selection engine chooses one safe default per boundary for unattended first drafts. It does not copy a reference creator's exact transition. It converts the learned reference balance into deterministic selection rules: important route changes prefer real bridge footage, title boundaries prefer clean scenic title breath, endings prefer aftertaste, normal cuts prefer visual match or clean continuity, and motion accents stay rare, source-motivated, and separated.

## Command

```bash
python3 <skill-dir>/scripts/prepare_transition_reference_selection.py \
  --package-dir <package> \
  --json
```

## Inputs

- `transition_reference_candidates/transition_reference_candidates.json`

## Outputs

- `transition_reference_selection/transition_reference_selection.json`
- `transition_reference_selection/transition_reference_selection.md`

Each selected row includes:

- source from/to clip names
- source candidate status
- selected candidate rank/type/family/intensity/duration
- candidate score table
- auto decision fields for BGM hit, bridge or motion evidence, title quiet zone, Resolve implementation, preview/audition evidence, and pending readback evidence
- boundary-specific reason naming the current from/to pair and why the chosen transition family fits that exact boundary
- post-selection proof plan with owner scripts, commands, required artifacts, and acceptance evidence for preview, audition, execution-blueprint, and transition reference-readiness follow-up
- forbidden workaround text that prevents repairing weak transitions by adding stronger decorative effects
- decision issue list; any nonzero `decisionIssueCount` keeps the plan blocked
- blockers when real bridge or title-breath material is still required

## Selection Rules

- Do not leave A/B/C rows for the next agent to choose manually in an unattended first draft.
- Do not treat auto-selected rows as ready if the decision is only generic text, pending readback prose, or a style-family label without a boundary-specific reason and proof plan.
- Important route, day, place, or timeline jumps select physical bridge or scenic breath first. If bridge material is not verified, keep the row blocked instead of selecting a decorative effect.
- Title boundaries select scenic title breath, short mood dissolve after readability, or clean cut to texture. They must not select motion accents.
- Ending transitions select aftertaste hold, visual match exit, or clean BGM cut.
- Normal boundaries prefer visual match, clean continuity, physical bridge, or short breath dissolve before motion.
- Motion accents can be selected only within the reference motion budget and with at least five boundary rows of spacing from another motion accent.
- Forbidden template language such as random spin, flash, glitch, shake, strobe, particles, or whoosh packs must lose selection unless no valid candidate exists, in which case the row blocks.

## Pass Criteria

- Status is `ready_with_transition_reference_selection`.
- Every candidate row has one selected default candidate.
- Blocked selection row count is zero.
- Decision issue count is zero.
- Every selected row has a boundary-specific reason, post-selection proof plan, preview/audition proof owner, and forbidden workaround.
- Selected motion rows do not exceed the candidate budget.
- Important boundaries have bridge, title-breath, or mood-breath selections.
- The following transition execution blueprint report shows `rowsWithAppliedReferenceSelection` equals the execution row count.
- Safety flags prove the command did not write Resolve, queue renders, download assets, or modify source footage.

## Repair Route

If the status is blocked, run or repair transition candidates first. For rows blocked by missing bridge material, repair source selection, bridge sequence, scenic title bridges, visual establishing, or creator cut before Resolve apply. Do not resolve a blocked row by choosing a random rotation, push, flash, glitch, or speed-ramp effect.
