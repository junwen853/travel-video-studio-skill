# Narrative Adjacency Contract

Use this contract when the edit is technically smooth but still feels like unrelated clips stacked together. The goal is to make every adjacent visual shot answer one viewer question: why does this shot follow the previous shot?

## Required Audit

Run:

```bash
python3 scripts/audit_narrative_adjacency_contract.py --package-dir <package>
```

The audit is read-only. It writes:

- `narrative_adjacency_contract_audit.json`
- `narrative_adjacency_contract_audit.md`

Do not approve a Resolve write, final QA, V14 baseline, or unattended first draft claim when this audit is blocked.

## Passing Standard

Every adjacent visual pair must have at least one viewer-readable reason:

- same chapter plus same city/place continuity
- source trim continuity from the same clip
- story-function progression such as title to context, context to movement, movement to texture, texture to payoff, payoff to aftertaste, or aftertaste to the next route/title/context
- explicit route or movement handoff
- aftertaste or breathing handoff
- title/chapter/ending handoff
- explicit transition, bridge, BGM phrase, visual match, storyboard, action-anchor, sensory-continuity, or landing metadata
- transition pair metadata matching the actual adjacent from/to shots

The audit blocks pairs that are merely pretty, random, or effect-covered.

## Blocked Patterns

Repair before handoff when the audit reports:

- `adjacent_pair_has_no_viewer_readable_reason`: insert or replace with route, texture, context, bridge, or aftertaste material.
- `adjacent_pair_contains_unknown_story_function`: add or repair `role`, `purpose`, `creatorFunction`, `place`, `city`, or chapter metadata before trusting the candidate.
- `adjacent_pair_contains_generic_or_weak_clip`: demote or replace placeholder, black, duplicate, utility, weak, or generic clips.
- `payoff_to_payoff_jump_without_bridge_movement_or_breath`: add a movement/texture/breathing bridge between landmark/scenic payoffs.
- `chapter_or_timeline_handoff_lacks_route_title_bridge_or_aftertaste`: add a route bridge, chapter title handoff, transit shot, quiet aftertaste, or explicit bridge sequence before the next destination claim.

## Repair Order

1. Re-open `edit_rhythm_plan.json` and `creator_cut_plan.json`. Assign a clear function to each active visual shot: context, movement, texture, payoff, aftertaste, title, or bridge.
2. If the pair crosses a chapter/day/place boundary, prefer a local route bridge or title-safe scenic bridge over a decorative effect.
3. If the pair is payoff-to-payoff, insert lived-in texture, movement, or aftertaste before the next landmark.
4. If the pair is weak because metadata is missing but the footage is usable, repair the blueprint metadata and rerun the audit.
5. If the pair only works because of a transition effect, ensure transition motivation, pair-continuity, storyboard, breathing-room, and final-cut smoothness audits also pass.

## Relation To Other Gates

This gate is stricter than transition pair-continuity and smoother than chapter-level scene-flow. It checks the actual final candidate row by row after candidate-chain generation. It must sit near:

- `audit_shot_flow_continuity_contract.py`
- `audit_scene_flow_arc_contract.py`
- `audit_final_cut_smoothness_contract.py`
- `audit_transition_continuity_rehearsal_contract.py`
- `audit_pacing_watchability_contract.py`

Together these gates prevent AI-looking travel edits where titles, BGM, and transitions hide a random shot order.
