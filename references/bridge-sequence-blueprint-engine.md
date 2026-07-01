# Bridge Sequence Blueprint Engine

Use this reference after `bridge-sequence-engine.md` when the plan needs to become an executable Resolve blueprint candidate.

## Purpose

`prepare_bridge_sequence_blueprint.py` materializes the 2-5 shot bridge sequence plan into actual candidate blueprint clips. It prevents the Skill from stopping at prose like "insert route bridge footage" while the timeline still only has a dissolve, title card, or hard jump.

The default behavior is non-destructive:

- reads `resolve_timeline_blueprint.json`
- reads `bridge_sequence_plan/bridge_sequence_plan.json`
- writes `bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json`
- writes `bridge_sequence_blueprint/bridge_sequence_blueprint_report.json` and `.md`
- leaves the active `resolve_timeline_blueprint.json` unchanged unless `--update-blueprint` is explicitly passed

## Command

```bash
python3 <skill-dir>/scripts/prepare_bridge_sequence_blueprint.py --package-dir <package> --json
```

Optional active blueprint replacement, only after review:

```bash
python3 <skill-dir>/scripts/prepare_bridge_sequence_blueprint.py --package-dir <package> --update-blueprint
```

## Timeline Behavior

The script places video-only `bridge_sequence_insert` clips on a dedicated overlay video track, default V4, around each transition row's boundary. This keeps source media read-only and preserves the active blueprint by default while making the bridge sequence visible in Resolve preflight and import.

Each inserted beat records:

- source path and source window
- timeline window
- source sequence row and beat function
- BGM phrase cue
- title-zone policy
- candidate score
- source-diversity proof so one clip is not reused for most bridge beats
- source-handle proof so the real source window covers the planned beat duration

## Required Follow-Up

Before Resolve apply:

```bash
python3 <skill-dir>/scripts/audit_resolve_blueprint.py \
  --blueprint <package>/bridge_sequence_blueprint/resolve_timeline_blueprint_bridge_sequence.json \
  --package-dir <package>
```

Then either:

- fork a new package that uses the candidate blueprint, or
- explicitly rerun with `--update-blueprint` after approval

Do not reuse stale final QA from the source package after the active blueprint changes.

## Acceptance Bar

Pass:

- report status is `ready_with_bridge_sequence_blueprint`
- candidate blueprint exists
- inserted beat clip count is greater than zero
- every bridge sequence row has decision fields
- route bridge rows use at least three distinct source clips when enough beats exist, and no 3+ beat sequence repeats the same source on adjacent beats
- every inserted bridge beat has enough real source duration for its timeline duration
- inserted clips are video-only and on the declared overlay track
- no Resolve writes, render queues, downloads, or source-footage modifications occur

Reject:

- the report adds no clips to the candidate blueprint
- required beats cannot resolve to local source clips
- a selected bridge clip is shorter than the intended beat and would require freeze, stretch, or loop filler
- a 2-5 shot bridge repeats the same source across most beats or repeats one source on adjacent beats
- inserted bridge clips carry source-camera audio into BGM-only transition windows
- the active blueprint is changed without explicit `--update-blueprint`
