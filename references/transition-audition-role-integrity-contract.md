# Transition Audition Role Integrity Contract

Use this contract immediately after `audit_transition_audition_visual_proof_contract.py` and before storyboard approval, Resolve apply, final QA, maturity, unattended first-draft, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_audition_role_integrity_contract.py \
  --package-dir <package>
```

The audit reads:

- `transition_audition_packet/transition_audition_packet.json`
- `transition_audition_quality_contract_audit.json`
- `transition_audition_visual_proof_contract_audit.json`

It writes:

- `transition_audition_role_integrity_contract_audit.json`
- `transition_audition_role_integrity_contract_audit.md`

## Pass Standard

- The audition packet, quality audit, and visual-proof audit have passed.
- Every audition row has segment reports in the order `outgoing -> bridge/motion -> landing`.
- Important boundaries have an actual bridge segment; a direct outgoing-to-landing jump cannot pass as a creator-style transition.
- Every segment file is package-local, muted, probeable video with enough duration and resolution.
- The concat list exactly matches the segmentReports order, proving the watchable MP4 was assembled from the planned role sequence.
- Motion execution still carries outgoing/bridge-or-motion/landing beat roles, BGM-hit policy, caption/title quiet zone, and Resolve keyframe effect.

## Repair

If this blocks, repair the transition bridge evidence, choreography, execution blueprint, or audition packet. Rebuild the audition MP4s, then rerun audition quality, visual proof, and role integrity before storyboard or Resolve apply.
