# Transition Audition Visual Proof Contract

Use this contract immediately after `audit_transition_audition_quality_contract.py` and before `audit_transition_audition_role_integrity_contract.py`, storyboard approval, Resolve apply, final QA, maturity, unattended first-draft, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_audition_visual_proof_contract.py \
  --package-dir <package> \
  --extract-frames
```

The audit reads:

- `transition_audition_packet/transition_audition_packet.json`
- `transition_audition_quality_contract_audit.json`

It writes:

- `transition_audition_visual_proof_contract_audit.json`
- `transition_audition_visual_proof_contract_audit.md`
- `transition_audition_visual_proof/row_###_*/frame_*.jpg`

## Pass Standard

- The audition packet is ready and the audition-quality audit has passed.
- Every audition MP4 is package-local, muted, probeable, long enough, and 16:9.
- `ffmpeg` extracts the required frames from every audition row.
- Extracted frames are nonblank and not visually uniform.
- First and last sampled frames differ enough to prove the transition moved from outgoing to landing footage.
- Consecutive sampled frames contain enough delta to prove bridge or motion flow exists inside the audition.
- Every important row still carries ready motion execution, three-beat choreography, BGM-hit policy, caption/title quiet zone, and a Resolve keyframe effect.
- Passing this contract proves the MP4 has visual change; the role-integrity contract must still prove it was assembled from ordered outgoing/bridge/landing segments.

## Repair

If this blocks, do not approve the storyboard or Resolve apply. Repair the transition execution blueprint, preview packet, bridge visual evidence, or audition packet, then rebuild the audition MP4s and rerun audition quality, visual-proof, and role-integrity audits.
