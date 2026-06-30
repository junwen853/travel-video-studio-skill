# Transition Execution Readiness Engine

Use this reference after `prepare_transition_polish_blueprint.py` and before any Resolve apply when the user wants transitions closer to the Parallel World / Malta references.

## Purpose

`audit_transition_execution_readiness_contract.py` checks that transition polish is not just advisory text. Every adjacent visual boundary must have a package-local transition-polish candidate that is executable enough for Resolve:

- matched from/to source pair
- selected Resolve recipe
- keyframe plan
- BGM hit or phrase cue
- BGM-only/no-voice audio treatment
- title/subtitle collision avoidance
- pair-continuity evidence
- adjacent clip duration/handle proxy
- apply/readback/frame-sample decision fields

## Command

```bash
python3 <skill-dir>/scripts/audit_transition_execution_readiness_contract.py --package-dir <package> --json
```

Outputs:

- `<package>/transition_execution_readiness_contract_audit.json`
- `<package>/transition_execution_readiness_contract_audit.md`

The script is read-only. It does not write Resolve, queue renders, download assets, modify source media, or mutate the active blueprint.

## Pass Bar

The audit should pass only when:

- the selected blueprint is the package-local `transition_polish_candidate`
- transition row count covers every adjacent visual boundary
- every boundary has recipe, keyframes, BGM hit, title-safety, BGM-only audio, decision fields, pair readiness, and handle readiness
- motion styles such as whip, rotation, speed-ramp, or push-slide have motion or bridge evidence and strong enough pair continuity
- decorative effects are not repeated in a long run
- transition duration stays restrained for long-form travel pacing

## Reject Bar

Block the edit when:

- the workflow audits an active/stale blueprint instead of the transition-polish candidate
- transition rows are generic labels without Resolve recipe metadata
- a boundary has no BGM phrase/hit, no title-safe window, or no BGM-only audio treatment
- pair continuity is weak or unmatched to the actual from/to shot
- whip/rotation/speed-ramp effects are used without route motion or bridge evidence
- transition handles are too short for the planned effect duration
- decorative effects repeat like a template pack

## Repair Route

If blocked, repair in this order:

1. Rerun `prepare_transition_grammar_plan.py`, `prepare_transition_execution_plan.py`, and `prepare_transition_execution_blueprint.py` if the transition row itself is missing.
2. Rerun `prepare_bridge_sequence_plan.py` and `prepare_bridge_sequence_blueprint.py` when route or chapter boundaries lack physical bridge evidence.
3. Rerun `prepare_bgm_phrase_blueprint.py` when BGM hit or phrase cue metadata is missing.
4. Rerun `prepare_transition_polish_blueprint.py` so selected recipes, keyframes, title avoidance, and pair-continuity payloads are materialized.
5. Re-run this audit, then preflight the candidate blueprint before any Resolve write.
