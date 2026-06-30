# Rendered Transition Proof Contract

Use this contract after a Resolve or FFmpeg final MP4 exists and before claiming the edit has reference-quality transitions. It checks rendered transition windows from the actual final video, not only planning metadata.

Run:

```bash
python3 <skill-dir>/scripts/audit_rendered_transition_proof_contract.py --package-dir <package>
```

The audit writes:

- `rendered_transition_proof_contract_audit.json`
- `rendered_transition_proof_contract_audit.md`
- `qa/rendered_transition_proof/frames/*.jpg`
- `qa/rendered_transition_proof/rendered_transition_proof_contact_sheet.jpg` when Pillow is available

It infers the final MP4 from `render_delivery_verification.json`, `FINAL_DELIVERY_REPORT.json`, `render_plan.json`, or the newest `renders/*.mp4`. It infers transition rows from the active blueprint, transition execution blueprint, final blueprint lineage, transition polish blueprint, or rhythm-recut blueprint.

## What It Blocks

Block the edit when rendered transition windows contain:

- black or blank frames that create AI-looking black flashes
- white-flash or strobe-like frames
- raw vertical/pillarboxed footage inside the 16:9 master
- transition boundary timestamps that cannot be mapped into the final render
- missing upstream proof from render verification, visual/audio style QA, BGM audio contract, or transition effect recipe contract

## Why This Exists

Planning gates can prove that a transition has BGM-hit timing, keyframes, recipes, preview clips, and Resolve apply metadata, but they cannot prove the final MP4 actually looks clean. This contract closes that gap by sampling the rendered frames around each important transition boundary.

## Repair Order

If the audit blocks:

1. Inspect `qa/rendered_transition_proof/rendered_transition_proof_contact_sheet.jpg`.
2. For blank/white flash rows, remove flash-style effects, shorten crossfades, or replace the boundary with bridge footage.
3. For pillarbox rows, repair the source orientation with reframing, blur-matte/PiP treatment, or replacement footage.
4. For unstable landing rows, add breathing-room footage after the transition instead of chaining another effect immediately.
5. Re-render or regenerate the tested preview/final MP4, then rerun this contract before final QA.

Do not mark a transition as fixed because the blueprint changed. This contract only passes when the rendered MP4 evidence passes.
