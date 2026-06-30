# Transition Effect Recipe Contract

Run this after `prepare_transition_execution_blueprint.py`, cutpoint/action-anchor/sensory-continuity audits, motion-accent audit, and transition audition quality:

```bash
python3 <skill-dir>/scripts/audit_transition_effect_recipe_contract.py --package-dir <package>
```

The audit writes:

- `transition_effect_recipe_contract_audit.json`
- `transition_effect_recipe_contract_audit.md`

## What It Blocks

- visible transition effects that only have a name, marker, or prose note instead of executable Resolve keyframes
- rotation, whip, push/slide, speed-ramp, dissolve, or title-breath rows without easing and parameter envelopes
- excessive rotation, translation, scale, motion blur, or retime parameters that make the film feel like a template edit
- visible effects that are not aligned to BGM hits, do not mute A1/A2, lack a stable landing hold, or collide with title/subtitle zones
- random spin, flash, glitch, shake, particle, strobe, whoosh-pack, or template language

## Required Recipe Shape

Every transition row must carry `transitionMotionExecution.resolveKeyframeRecipe` with:

- `effect`
- `durationFrames`
- `transformKeyframes[]` with monotonic frame numbers from 0 to duration
- `easing.curve` and landing-hold intent
- `parameterEnvelope` limits for rotation, translation, scale, motion blur, opacity, retime, and duration
- `audioKeyframes[]` that force A1/A2 to `-inf` and keep A3 BGM active
- `qualityControls` for template-motion rejection, BGM-only audio, title safety, landing hold, phrase hit, source-motion requirement, and Resolve readback

## Repair Order

1. Rerun `prepare_transition_execution_blueprint.py` so transition rows include the latest keyframe recipe fields.
2. Downgrade unsupported visible effects to clean cuts, visual matches, mood dissolves, or real bridge sequences.
3. Reduce rotation/translation/scale/blur/retime envelopes until the audit passes.
4. Rerun cutpoint, action-anchor, sensory-continuity, motion-accent, preview, audition, storyboard, and this contract before Resolve apply or final QA.

## Safety

This audit only reads package JSON and writes local audit reports. It must not write Resolve, queue renders, download assets, or modify source footage.
