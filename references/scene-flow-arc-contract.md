# Scene Flow Arc Contract

Use this contract after chapter story-spine, shot-flow continuity, timeline-variety, reference scene-grammar, transition scene-arc, and transition breathing-room reports exist.

Run:

```bash
python3 <skill-dir>/scripts/audit_scene_flow_arc_contract.py --package-dir <package>
```

This is a no-write audit. It reads the final candidate Resolve blueprint plus upstream QA reports and writes:

- `scene_flow_arc_contract_audit.json`
- `scene_flow_arc_contract_audit.md`

## Purpose

This gate prevents a technically valid edit from still feeling like an AI montage. Adjacent transitions may pass while the viewer still experiences the film as random landmarks, hard chapter jumps, or decorative motion. A reference-like travel sequence needs a scene arc:

- context or setup
- route movement
- lived-in texture
- destination payoff
- aftertaste or handoff

## Blocks

Block the package when any chapter:

- has too few visual clips to form a readable scene
- lacks movement, lived-in texture, or destination payoff
- opens on a payoff without nearby route grounding
- ends without aftertaste or a real handoff
- contains weak, placeholder, black-slate, generic, duplicate, or unclassified clips
- stacks landmark/payoff shots without movement or texture between them
- relies on title cards, effects, or transition metadata to hide missing route footage

Block chapter handoffs when:

- the outgoing chapter has no aftertaste, movement, or route texture near its end
- the incoming chapter starts with payoff imagery before grounding the new place
- a boundary becomes payoff-to-payoff, producing a tourist-slideshow jump

## Relationship To Other Gates

This gate does not replace:

- `audit_chapter_story_spine_contract.py`: proves the planned story spine exists and survives.
- `audit_shot_flow_continuity_contract.py`: proves chapter clip order is readable.
- `audit_timeline_variety_contract.py`: proves whole-film function variety.
- `audit_transition_breathing_room_contract.py`: proves transitions have readable landings.

It sits above them and verifies the viewer-facing scene arc created by their combined evidence.

## Repair

If blocked, repair the package by:

- adding or replacing clips from the footage select plan, preferring local route texture first
- inserting movement or lived-in detail between destination payoffs
- using bridge-sequence clips for day/place handoffs
- demoting utility or weak clips through creator-cut/final-source usage repair
- rerunning transition scene-arc, shot-flow, timeline-variety, scene-flow arc, unattended-first-draft, V14 baseline, maturity, and final QA

Do not fix a blocked scene-flow arc by adding more spin, zoom, whip, glitch, or speed-ramp effects. The missing unit is usually source selection, route texture, chapter structure, or aftertaste.
