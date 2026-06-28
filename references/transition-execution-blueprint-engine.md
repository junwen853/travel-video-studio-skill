# Transition Execution Blueprint Engine

Use this reference after `transition-execution-engine.md` when transition recipes need to become a preflightable Resolve blueprint candidate.

## Purpose

`prepare_transition_execution_blueprint.py` materializes transition execution rows into blueprint-level candidate transition objects. It prevents "Cross Dissolve here" or "rotation match cut here" from remaining a prose instruction with no timeline evidence.

The default behavior is non-destructive:

- reads `transition_execution_plan/transition_execution_plan.json`
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

Each candidate transition records the approved transition type, Resolve effect name, duration frames, keyframe plan, BGM cue, subtitle policy, audio policy, bridge requirement, motion evidence, and decision/readback fields.

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
- every transition row has decision fields
- adjacent clips have in/out transition metadata
- bridge-required rows are not marked ready until bridge sequences are materialized
- motion effects are allowed only with recorded motion evidence
- no Resolve writes, render queues, downloads, or source-footage modifications occur

Reject:

- transition recipes remain prose-only
- random spin, flash, glitch, shake, or template effects appear as selected recipes
- bridge-required rows are marked ready without a materialized bridge sequence
- the active blueprint is changed without explicit `--update-blueprint`
