# Effect Motion Blueprint Engine

Use this reference after `prepare_effect_motion_plan.py` when title reveals, route-motion effects, whip/rotation, speed ramps, or subtle scenic motion need to become a preflightable Resolve blueprint candidate.

## Purpose

`prepare_effect_motion_blueprint.py` materializes restrained effect-motion rows into candidate blueprint metadata. It prevents "add a subtle rotation" or "use a clean title fade" from remaining a prose suggestion with no timeline evidence.

The default behavior is non-destructive:

- reads `effect_motion_plan/effect_motion_plan.json`
- uses `transition_execution_blueprint/resolve_timeline_blueprint_transition_execution.json` as the base when it is ready, otherwise falls back to bridge sequence or active blueprint
- writes `effect_motion_blueprint/resolve_timeline_blueprint_effect_motion.json`
- writes `effect_motion_blueprint/effect_motion_blueprint_report.json` and `.md`
- leaves the active `resolve_timeline_blueprint.json` unchanged unless `--update-blueprint` is explicitly passed

## Command

```bash
python3 <skill-dir>/scripts/prepare_effect_motion_blueprint.py --package-dir <package> --json
```

Optional active blueprint replacement, only after review:

```bash
python3 <skill-dir>/scripts/prepare_effect_motion_blueprint.py --package-dir <package> --update-blueprint
```

## Timeline Behavior

The script adds:

- top-level `effectMotionCandidates[]` rows
- per-clip `effectMotionCandidates` metadata
- timeline markers with role `effect_motion_candidate_marker`

Each candidate records row type, title/transition target, restrained effect style, duration frames, keyframe plan, title-zone safety, source evidence, motion evidence, BGM-only audio treatment, forbidden-effect hits, and decision/readback fields.

## Acceptance Bar

Pass:

- report status is `ready_with_effect_motion_blueprint`
- candidate blueprint exists
- effect candidate count equals effect row count
- every effect row has decision fields and a clip match
- title reveal rows are title-zone safe and BGM-only
- whip, rotation, and speed-ramp rows have route-motion evidence
- no glitch, random spin, flash, shake, particle, logo reveal, or template-pack effects
- no Resolve writes, render queues, downloads, or source-footage modifications occur

Reject:

- effect rows remain prose-only
- motion effects hide missing route bridge footage, weak title typography, missing BGM, or wrong route evidence
- title effects overlap subtitles or duplicate/ghosted titles
- the active blueprint is changed without explicit `--update-blueprint`
