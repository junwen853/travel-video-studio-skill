# Transition Scene Settlement Contract

Run this after transition viewer orientation, breathing-room, scene-flow, shot-flow, pacing, narrative adjacency, and final-blueprint lineage audits:

```bash
python3 <skill-dir>/scripts/audit_transition_scene_settlement_contract.py --package-dir <package>
```

Outputs:

- `transition_scene_settlement_contract_audit.json`
- `transition_scene_settlement_contract_audit.md`

Purpose:

- Prove important route, day, place, title, and ending transitions land into a readable scene, not a single title/card/placeholder or an immediate second jump.
- Check the final or latest candidate Resolve blueprint, not only plan text.
- Require the post-transition settlement window to contain enough local footage plus lived texture, movement, payoff, route, or aftertaste evidence.
- Block rough "AI slideshow" transitions where the cut is technically motivated but the audience has no time to settle into the new place.

Passing standard:

- Required upstream orientation, breathing-room, storyboard, scene-flow, shot-flow, pacing, narrative, and lineage reports are accepted.
- The final candidate blueprint is package-local and has important transition boundaries.
- Important transitions have a stable landing clip plus at least two post-transition clips or the configured settlement duration, except ending aftertaste transitions.
- The next important transition does not arrive immediately after a route/title/chapter landing.
- Settlement windows contain lived texture or payoff footage and avoid utility, placeholder, duplicate, or title-only clips.

Repair order:

1. Replace title-only or placeholder landings with real local scenic/arrival/street/transport/texture footage.
2. Add 1-3 local clips after important route/day/title transitions before the next chapter jump.
3. Prefer existing source footage cutaways over new stock unless local material is missing.
4. Re-run transition viewer orientation, breathing-room, scene-flow, pacing, and this settlement contract before Resolve apply.
