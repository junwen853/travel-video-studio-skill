# Transition Motion Accent Contract

Run this after choreography, motion-direction, cutpoint, action-anchor, sensory-continuity, breathing-room, audition proof, effect-motion application, and final-cut smoothness reports exist:

```bash
python3 <skill-dir>/scripts/audit_transition_motion_accent_contract.py --package-dir <package>
```

The audit writes:

- `transition_motion_accent_contract_audit.json`
- `transition_motion_accent_contract_audit.md`

The contract blocks motion accents that make a travel film feel templated or AI-made:

- too many whip, rotation, push, zoom, slide, or speed-ramp accents for the number of visual boundaries
- back-to-back motion accents without a breathing transition
- random spin, flash, shake, glitch, particle, or template language
- rotation that is not subtle
- motion without source or bridge movement evidence
- motion direction that conflicts with the outgoing, bridge, or landing shot
- missing BGM-hit timing, title/subtitle quiet zone, directional action anchor, sensory continuity, or readable landing hold

Repair order:

1. Downgrade unsupported motion accents to clean cuts, visual matches, mood dissolves, or physical route bridge inserts.
2. Keep only rare motion accents where source motion, bridge movement, and landing direction agree.
3. Add or repair cutpoint, action-anchor, sensory-continuity, and audition evidence before re-running this audit.

When the audit blocks, run:

```bash
python3 <skill-dir>/scripts/prepare_transition_motion_accent_repair_plan.py --package-dir <package> --json
```

The repair plan writes `transition_motion_accent_repair_plan/transition_motion_accent_repair_plan.json` and `.md`. A `ready_with_transition_motion_accent_repair_plan` status means there are still open repairs; it is not a delivery pass. Close the owner-script rows and rerun the motion-accent audit, final QA, V14 baseline, and maturity checks until the plan returns `ready_no_motion_accent_repairs_needed`.
