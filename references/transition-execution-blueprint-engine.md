# Transition Execution Blueprint Engine

Use this reference after `transition-execution-engine.md` when transition recipes need to become a preflightable Resolve blueprint candidate.

## Purpose

`prepare_transition_execution_blueprint.py` materializes transition execution rows, transition reference selections, transition choreography, motion-direction plans, cutpoint timing, transition action anchors, and transition sensory continuity into blueprint-level candidate transition objects. It prevents "Cross Dissolve here", "rotation match cut here", "candidate A/B/C selected", or "add a cool rotation" from remaining a prose instruction with no timeline evidence.

The default behavior is non-destructive:

- reads `transition_execution_plan/transition_execution_plan.json`
- reads `transition_reference_selection/transition_reference_selection.json`
- reads `transition_choreography_plan/transition_choreography_plan.json`, including `motionDirectionPlan`
- uses `bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json` as the base when it is ready, otherwise `resolve_timeline_blueprint.json`
- writes `transition_execution_blueprint/resolve_timeline_blueprint_transition_execution.json`
- writes `transition_execution_blueprint/transition_execution_blueprint_report.json` and `.md`
- leaves the active `resolve_timeline_blueprint.json` unchanged unless `--update-blueprint` is explicitly passed

## Command

```bash
python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package> --json
```

Optional active blueprint replacement, only after review:

```bash
python3 <skill-dir>/scripts/prepare_transition_execution_blueprint.py --package-dir <package> --update-blueprint
```

## Timeline Behavior

The script adds:

- top-level `transitions[]` rows with role `transition_execution_candidate`
- `transitionExecutionOut` metadata on outgoing clips
- `transitionExecutionIn` metadata on incoming clips
- timeline markers with role `transition_execution_candidate_marker`

Each candidate transition records the approved transition type, Resolve effect name, duration frames, selected candidate rank/type/family/intensity, selected Resolve recipe, selected preview hint, keyframe plan, BGM cue, subtitle policy, audio policy, bridge requirement, motion evidence, `transitionMotionExecution`, `transitionCutpointPlan`, `transitionActionAnchorPlan`, `transitionSensoryContinuityPlan`, and decision/readback fields.

`transitionMotionExecution` must carry the choreography family, source transition style, restrained intensity, outgoing/bridge-or-motion/landing three-beat choreography, BGM phrase-hit target, caption/title quiet-zone policy, `motionDirectionPlan`, Resolve keyframe recipe, and safety checks for BGM-only/no-source-voice, title safety, direction match, and no template motion. The Resolve keyframe recipe must include `effect`, `durationFrames`, monotonic `transformKeyframes`, `easing`, `parameterEnvelope`, BGM-only `audioKeyframes`, and `qualityControls`; run `audit_transition_effect_recipe_contract.py` after this blueprint is generated.

`transitionCutpointPlan` must carry the boundary frame, outgoing tail frames, bridge/effect hit frames, landing hold frames, available pre/post roll, required handles, BGM hit offset/tolerance, title/subtitle quiet-zone readiness, BGM-only audio proof, and important-boundary resolution. This is the guard that makes transitions feel edited rather than merely effect-labeled.

`transitionActionAnchorPlan` must carry outgoing, bridge-or-match, and landing anchors, plus directional motion-anchor readiness for visible motion transitions. It blocks when a transition has timing and an effect but the viewer cannot tell what action is being left, why the bridge/match exists, or what stable shot they land on.

`transitionSensoryContinuityPlan` must prove each boundary carries visual continuity, BGM-only phrase-hit audio continuity, title/subtitle quiet-zone continuity, route or mood continuity for important boundaries, motion-direction continuity when visible motion is used, and a stable landing. It blocks transitions that have effect timing and action anchors but still feel mechanical.

## Required Follow-Up

Before Resolve apply:

```bash
python3 <skill-dir>/scripts/audit_resolve_blueprint.py \
  --blueprint <package>/transition_execution_blueprint/resolve_timeline_blueprint_transition_execution.json \
  --package-dir <package>
```

Then either:

- fork a new package that uses the candidate blueprint, or
- explicitly rerun with `--update-blueprint` after approval

Do not reuse stale final QA from the source package after the active blueprint changes.

## Acceptance Bar

Pass:

- report status is `ready_with_transition_execution_blueprint`
- candidate blueprint exists
- candidate `transitions[]` count equals execution row count
- `rowsWithAppliedReferenceSelection` equals execution row count
- `rowsWithMotionExecution`, `rowsWithThreeBeatMotion`, `rowsWithBgmHitMotion`, and `rowsWithCaptionQuietMotion` equal execution row count
- `rowsWithCutpointReady`, `rowsWithCutpointBgmHit`, `rowsWithCutpointLandingHold`, and `rowsWithCutpointHandles` equal execution row count
- `rowsWithActionAnchorReady`, `rowsWithOutgoingActionAnchor`, `rowsWithBridgeOrMatchActionAnchor`, and `rowsWithLandingActionAnchor` equal execution row count
- `rowsWithSensoryContinuityReady`, visual/audio/caption/landing sensory counts, and zero blocked sensory rows prove each transition has viewer-readable continuity channels
- `motionExecutionFromChoreographyCount` equals execution row count and `motionExecutionDerivedCount` is zero
- transition objects, clip annotations, and markers carry the selected candidate type/family plus ready `transitionMotionExecution`, and transition objects carry ready `transitionCutpointPlan`, `transitionActionAnchorPlan`, and `transitionSensoryContinuityPlan`
- `audit_transition_effect_recipe_contract.py` passes, proving visible effects have executable restrained keyframes, easing, parameter envelopes, BGM-only audio keyframes, BGM-hit timing, and stable landing holds
- every transition row has decision fields
- adjacent clips have in/out transition metadata
- bridge-required rows are not marked ready until bridge sequences are materialized
- motion effects are allowed only with recorded motion evidence
- no Resolve writes, render queues, downloads, or source-footage modifications occur

Reject:

- transition recipes remain prose-only
- reference selection rows exist but do not appear in the candidate blueprint
- choreography rows exist but do not appear as `transitionMotionExecution` in transitions, clip annotations, and markers
- cutpoint timing remains implicit, so the chosen effect has no readable leave point, BGM hit point, or landing hold
- action anchors remain implicit, so the transition has no readable outgoing action, motivated bridge/match, or stable landing proof
- sensory continuity remains implicit, so the transition has timing and anchors but no visual/BGM/caption/route/landing continuity proof
- random spin, flash, glitch, shake, or template effects appear as selected recipes
- bridge-required rows are marked ready without a materialized bridge sequence
- the active blueprint is changed without explicit `--update-blueprint`
