# Transition Audition Packet Engine

Use this engine after `prepare_transition_preview_packet.py`, `audit_transition_preview_quality_contract.py`, and `prepare_transition_execution_blueprint.py`, and before `audit_transition_storyboard_contract.py`, Resolve apply, final QA, maturity, or V14 baseline claims.

Static outgoing and landing frames prove a boundary is not blank, but they do not prove the cut flows. Important route, title, timeline-gap, and ending transitions need a short muted MP4 audition that can be watched locally: outgoing edge, bridge or motion beat when available, then landing edge.

The audition row must carry the same `transitionMotionExecution` and `transitionCutpointPlan` that were materialized into the transition execution blueprint. This keeps audition proof tied to the selected choreography family, BGM phrase hit, caption/title quiet zone, motion-direction plan, cutpoint leave/hit/landing timing, and Resolve keyframe recipe instead of becoming a generic stitched preview.

## Command

```bash
python3 <skill-dir>/scripts/prepare_transition_audition_packet.py \
  --package-dir <package> \
  --build-clips
```

The script reads:

- `transition_preview_packet/transition_preview_packet.json`
- `transition_preview_quality_contract_audit.json`
- `transition_bridge_visual_evidence_contract_audit.json` when bridge-beat clips exist
- `transition_execution_blueprint/resolve_timeline_blueprint_transition_execution.json`

It writes:

- `transition_audition_packet/transition_audition_packet.json`
- `transition_audition_packet/transition_audition_packet.md`
- `transition_audition_packet/row_###/transition_audition.mp4`
- `transition_audition_packet/row_###/audition.md`

## Pass Standard

- Status is `ready_with_transition_audition_packet` or `ready_no_important_transitions`.
- Every important transition row has a package-local `transition_audition.mp4`.
- Every important audition row has ready `motionExecution` and cutpoint timing with three-beat choreography, BGM-hit policy, caption/title quiet-zone policy, motion-direction evidence for visible motion effects, readable outgoing/landing holds, and a Resolve keyframe effect.
- Auditions are muted visual proof; they must not carry source-camera voice or noise.
- The script writes only package-local review files. It does not write Resolve, queue renders, download assets, modify source footage, or modify source drives.

## Repair

If the packet is `needs_audition_build`, rerun with `--build-clips`. If it is blocked, repair the upstream preview packet, bridge visual evidence, or transition execution blueprint first. Do not approve storyboard or Resolve apply from metadata alone.
