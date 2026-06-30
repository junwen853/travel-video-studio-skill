# Transition Viewer Orientation Contract

Run this after transition storyboard, narrative adjacency, route texture, chapter story spine, shot-flow continuity, motif coherence, breathing-room, pacing, and final-blueprint lineage reports exist.

```bash
python3 <skill-dir>/scripts/audit_transition_viewer_orientation_contract.py --package-dir <package>
```

Outputs:

- `transition_viewer_orientation_contract_audit.json`
- `transition_viewer_orientation_contract_audit.md`

## Purpose

This contract proves important travel-film transitions orient the viewer, not just the editor.

It blocks when:

- a route, day, chapter, title, timeline-gap, or ending transition has no viewer-facing purpose
- the transition lacks a route, title, caption, BGM, bridge, scenic, or aftertaste cue
- the landing shot is generic, unknown, black, placeholder, duplicate, or weak
- preview/audition evidence is missing for an important transition
- narrative adjacency cannot explain why the film moved from the outgoing shot to the landing shot
- route texture or chapter story spine does not support the claimed place/time handoff

## Passing Standard

The audit passes only when:

- `transition_storyboard_contract_audit.json` passes
- `narrative_adjacency_contract_audit.json` passes with no blocked or unmotivated pairs
- `route_texture_contract_audit.json` passes or passes with warnings
- `chapter_story_spine_contract_audit.json` passes
- every important transition has purpose, route/title/caption/bridge cue, stable landing, preview evidence, audition evidence, and narrative handoff reason
- motif coherence, breathing-room, pacing, shot-flow, and final-blueprint lineage agree with the orientation claim

## Repair Order

1. Repair the transition storyboard row first: purpose, outgoing, bridge/motion cue, landing, preview, and audition fields.
2. If geography or time is unclear, add or relabel physical bridge footage through bridge sequence planning.
3. If the landing is weak, replace it with a creator-cut hero/main/texture shot.
4. If route texture or chapter spine blocks, repair chapter context, movement, texture, payoff, or aftertaste beats.
5. Rerun narrative adjacency, route texture, storyboard, viewer-orientation, final QA, V14 baseline, and maturity gates.
