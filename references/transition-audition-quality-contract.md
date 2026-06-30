# Transition Audition Quality Contract

Use this contract immediately after `prepare_transition_audition_packet.py --build-clips` and before `audit_transition_audition_visual_proof_contract.py`, storyboard approval, Resolve apply, final QA, maturity, or V14 baseline claims.

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_audition_quality_contract.py \
  --package-dir <package>
```

The audit reads `transition_audition_packet/transition_audition_packet.json` and writes:

- `transition_audition_quality_contract_audit.json`
- `transition_audition_quality_contract_audit.md`

## Pass Standard

- The audition packet status is `ready_with_transition_audition_packet` or `ready_no_important_transitions`.
- Every important audition row has a package-local MP4 file.
- Every important audition row carries ready `motionExecution` from the transition execution blueprint.
- The motion execution row has outgoing/bridge-or-motion/landing three-beat choreography, BGM-hit policy, caption/title quiet-zone policy, motion-direction evidence for visible motion effects, and a Resolve keyframe effect.
- `ffprobe` can read each MP4 and find a video stream.
- Each clip meets the minimum duration and resolution.
- Audio streams are blocked by default; auditions are visual transition proof, not BGM or source-audio approval.
- Passing this contract only proves the MP4 is playable; the visual-proof contract must still extract frames and prove endpoint/middle-motion change.

## Repair

If a clip is missing, too short, unreadable, outside the package, contains audio, lacks ready motion execution, lacks motion-direction proof, or fails frame-delta proof in the visual contract, rebuild the audition packet after repairing the transition execution blueprint, transition preview packet, and bridge visual evidence.
