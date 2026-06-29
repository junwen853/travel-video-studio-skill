# Transition Breathing-Room Contract

Use this contract after transition choreography, preview/audition proof, storyboard proof, reference-transition profile, and shot-flow continuity exist. It is a no-write gate for travel films that should feel closer to the Parallel World/Malta references.

## Purpose

The edit must not only have transitions; it must let the viewer land after them. A boundary can pass the older transition gates while still feeling cheap if it stacks whip/rotation/speed-ramp effects, interrupts the landing shot immediately, or collides with a title/subtitle zone. This contract blocks those cases before Resolve apply or final handoff.

## Required Evidence

- Final candidate Resolve blueprint inside the package.
- `transition_choreography_plan/transition_choreography_plan.json`.
- `transition_microstructure_contract_audit.json`.
- `transition_choreography_contract_audit.json`.
- `transition_preview_quality_contract_audit.json`.
- `transition_audition_quality_contract_audit.json`.
- `transition_storyboard_contract_audit.json`.
- `reference_transition_profile_contract_audit.json`.
- `shot_flow_continuity_contract_audit.json`.

## Passing Rules

- Every adjacent visual boundary has choreography and storyboard rows.
- Important boundaries such as chapter changes, title transitions, timeline gaps, and endings have bridge-or-motion evidence plus landing evidence.
- Important or motion boundaries land on stable readable footage for the configured hold time.
- Motion accents are rare, motivated, and separated by calm boundaries; consecutive motion accents block.
- High-intensity whip/speed/push transitions require proven landing evidence and may not run back-to-back.
- Motion transitions must not touch hero title/subtitle zones or omit caption quiet-zone policy.
- The full transition set keeps enough clean cuts, match cuts, dissolves, bridges, or breath-style boundaries so the film does not become effect spam.

## Repair Guidance

- If a boundary fails landing duration, extend the landing shot or insert a short scenic/street/transport/texture beat after the transition.
- If motion spacing fails, replace some whip/rotation/speed-ramp rows with match cuts, clean cuts, mood dissolves, or local bridge clips.
- If title/subtitle risk fails, suppress V3 subtitles in the title zone, move the title to a quiet scenic section, or remove the visible motion effect from that boundary.
- If important bridge evidence is missing, add a 2-5 shot bridge sequence using local route footage before using stock/aerial fallback.
- If clean-breath share fails, reduce decorative effects first; do not use stock footage to hide weak source selection.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_breathing_room_contract.py --package-dir <package> --json
```

The script writes `transition_breathing_room_contract_audit.json` and `.md`. It never writes Resolve, queues renders, downloads assets, edits source footage, or modifies source drives.
