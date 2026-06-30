# Reference Scene Grammar Engine

Use this reference when judging whether a travel edit has absorbed the Parallel World/Malta structure rather than merely passing technical checks.

## Run

```bash
python3 <skill-dir>/scripts/audit_reference_scene_grammar_contract.py \
  --package-dir <package> \
  --json
```

Outputs:

- `reference_scene_grammar_contract_audit.json`
- `reference_scene_grammar_contract_audit.md`

## What It Checks

The audit reads the best package-local candidate blueprint plus current planning/audit artifacts. It classifies visual clips into scene functions:

- `context`: human reaction, companion, promise, or viewer reason
- `movement`: road, train, airport, walking, luggage, station, route material
- `texture`: street, shop, hotel, food, weather, waiting, local detail
- `payoff`: aerial, skyline, landmark, coast, activity, scenic reward
- `aftertaste`: quiet ending, route callback, night, departure, final scenic movement

## Pass Bar

Pass only when:

- opening clips include destination-proof payoff imagery and at least one route/context/texture function
- chapters carry movement, texture, and payoff; longer chapters also need aftertaste/handoff evidence
- ending clips provide aftertaste, route callback, or final scenic movement
- `transition_pair_continuity_contract_audit.json` passes with no weak pair fits
- `opening_story_plan`, `chapter_arc_plan`, and `creator_cut_plan` exist

Reject:

- flat file-order montages
- chapters made only of scenery or only of transport
- endings that stop on leftover footage
- claiming reference style before scene functions and pair-continuity are both proven

This gate is non-destructive. It does not write Resolve, render, download assets, or modify source media.
