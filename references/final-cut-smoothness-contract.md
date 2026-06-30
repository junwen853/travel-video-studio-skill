# Final Cut Smoothness Contract

Use `scripts/audit_final_cut_smoothness_contract.py` after final-blueprint lineage, transition breathing-room, scene-flow arc, shot-flow continuity, visual-match, choreography, and storyboard reports pass.

This gate exists because a package can pass many plan-level transition checks and still feel like a rough AI assembly if the active/final candidate blueprint has abrupt adjacent joins. It audits the final candidate itself.

## Run

```bash
python3 <skill-dir>/scripts/audit_final_cut_smoothness_contract.py \
  --package-dir <package> \
  --json
```

It writes:

- `final_cut_smoothness_contract_audit.json`
- `final_cut_smoothness_contract_audit.md`

## What Must Pass

- The candidate blueprint must be package-local and contain enough visual clips and adjacent boundaries to audit.
- Upstream final-blueprint lineage, transition breathing-room, scene-flow arc, shot-flow continuity, visual-match, choreography, and storyboard reports must be accepted.
- Important chapter, title, and timeline-gap boundaries need final transition metadata plus bridge, match, or breathing-room proof.
- Whip, rotation, push/slide, and speed-ramp accents must be rare, evidence-backed, and land on stable primary clips.
- Payoff-to-payoff hard jumps, weak/placeholder clips, unclassified landings, and effect-hidden title/unknown jumps are blockers.

## Repair Rules

Do not repair a blocked row by adding a flashier transition. Fix the underlying cut:

- Add or relabel physical route bridge footage: station, street, vehicle, sign, hotel window, food, weather, or walking detail.
- Replace weak or unclassified landing clips with creator-cut hero/main/texture selections.
- Use clean cut, match cut, short dissolve, or bridge insert when the two shots do not have motion energy.
- Keep rotation, whip, push, and speed-ramp accents for rare two-sided route-motion joins only.
- Give every high-intensity transition enough stable landing footage before the next title, caption, or idea.
- Rerun final-blueprint lineage, transition breathing-room, scene-flow arc, and this contract after any candidate rewrite.

## Relationship To Other Gates

- `transition_visual_match_contract` proves transition rows have visual or bridge evidence.
- `transition_choreography_contract` proves important transitions have outgoing, bridge-or-motion, and landing beats.
- `transition_breathing_room_contract` proves important boundaries land before the next idea.
- `scene_flow_arc_contract` proves chapters form readable travel arcs.
- This contract proves the final candidate blueprint did not lose those decisions and still cuts smoothly shot-to-shot.
