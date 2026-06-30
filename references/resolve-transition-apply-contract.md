# Resolve Transition Apply Contract

Use this contract after `audit_resolve_transition_materialization_contract.py` and before any Resolve `--apply` approval.

## Purpose

Transition materialization proves the selected recipe payload survives into the final blueprint and Resolve marker customData. It does not prove the visible effect is actually applied in Resolve.

`prepare_resolve_transition_apply_plan.py` and `audit_resolve_transition_apply_contract.py` close that gap. They separate three states:

- API-supported structure: adjacent clips, real bridge clips, and marker payloads that `build_resolve_timeline.py` can write.
- Manual Resolve/Fusion/effect work: visible dissolves, rotations, whip/push/slide, speed ramps, blur, and other treatments that the local Resolve scripting README does not expose as a stable direct adjacent-transition API.
- Blocked marker-only state: a visible transition that exists only as planning text or marker metadata.

## Required Evidence

The apply audit may pass only when:

- `resolve_transition_apply_plan/resolve_transition_apply_plan.json` exists and is `ready_with_resolve_transition_apply_plan`;
- every transition row has an `applyMethod`;
- no visible transition uses `timeline_marker_handoff_only`;
- visible effects either have a manual Resolve/Fusion instruction with required readback/frame evidence, or are replaced by materialized bridge clips;
- every row has apply decision fields, acceptance evidence, marker payload readiness, and clip annotation readiness;
- the Resolve transition materialization audit is present and passed when available.

## Failure Policy

If this audit blocks, do not approve Resolve apply, final QA, V14 baseline, or Skill maturity claims. Repair the final blueprint, add real bridge clips, or perform the manual Resolve/Fusion/effect step with readback/frame evidence. Do not claim a rotation, whip, dissolve, or speed ramp is applied when only marker customData exists.

This contract is intentionally strict because the Resolve Python API can reliably create timelines, clips, tracks, markers, and render plans, but the local scripting README does not document a stable direct API for applying arbitrary adjacent-clip transitions.
