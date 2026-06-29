# Transition Polish Application Contract

Use this contract after `prepare_transition_polish_blueprint.py`, `audit_transition_quality_contract.py`, `audit_shot_transition_boundary_contract.py`, `audit_transition_motivation_contract.py`, `audit_transition_pair_continuity_contract.py`, and `audit_transition_execution_readiness_contract.py`.

## Purpose

The transition polish blueprint proves that a candidate has BGM-hit timing, title/subtitle avoidance, pair-continuity evidence, and restrained Resolve keyframes. It does not prove that a later active/final blueprint still contains those rows.

`audit_transition_polish_application_contract.py` closes that gap. It compares `transition_polish_blueprint/transition_polish_blueprint_report.json` and its candidate blueprint against the active `resolve_timeline_blueprint.json` by default, or a supplied `--blueprint`, and blocks if the final blueprint dropped or damaged the polish metadata.

## Required Evidence

The audit must pass only when:

- `transition_polish_blueprint_report.json` is `ready_with_transition_polish_blueprint`.
- The source transition-polish candidate exists inside the package.
- The final/active blueprint exists inside the package.
- The final/active blueprint contains `transitionPolishBlueprintPlan`.
- Every source `polishRows` entry appears in the final blueprint by row index or by matching from/to source pair and boundary seconds.
- Every final row keeps its selected recipe, Resolve effect, keyframes, duration no longer than 0.9 seconds, BGM hit/phrase cue, BGM-only/no-voice policy, title/subtitle avoidance, pair-continuity evidence, and Resolve apply decision fields.
- Motion-style rows such as whip, rotation, speed ramp, push, or slide still carry strong motion or bridge evidence.
- Final clips preserve `transitionPolishOut` or `transitionPolishIn` annotations.
- Final timeline markers preserve `transition_polish_candidate_marker` payloads.

## Failure Policy

If this audit blocks, do not approve Resolve apply. Repair the package by making the approved transition-polish candidate the active/final blueprint through the safe apply/fork path, or by regenerating the final blueprint from the latest polished candidate. Then rerun this audit, the transition execution-readiness audit, unattended-first-draft audit, V14 baseline audit, and final QA suite.

This audit is intentionally stricter than a prose handoff. A transition plan that does not survive into the final blueprint cannot be treated as learned Skill behavior.
