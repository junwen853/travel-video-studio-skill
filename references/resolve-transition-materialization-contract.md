# Resolve Transition Materialization Contract

Use this contract after `prepare_transition_polish_blueprint.py` and `audit_transition_polish_application_contract.py`, before any Resolve apply approval.

## Purpose

Transition polish metadata proves the edit has selected recipes, BGM hits, title-safe windows, motion evidence, and pair continuity. That is still not enough if the final Resolve write adapter cannot carry the recipe payload forward.

`audit_resolve_transition_materialization_contract.py` closes that gap. It checks the active/final blueprint, the Resolve timeline build adapter, and optional `resolve_audit.json` readback evidence so transition rows are not only planning text.

## Required Evidence

The audit may pass only when:

- the checked blueprint exists inside the package;
- the blueprint contains one or more final `transitionPolishCandidates`;
- every candidate has a selected recipe with `recipeId`, `resolveEffectName`, duration, keyframe plan, and transition motivation;
- every candidate is mirrored by clip-level `transitionPolishOut` or `transitionPolishIn` annotation;
- every candidate has a transition timeline marker whose payload identifies the row and selected recipe/effect;
- `build_resolve_timeline.py` preserves marker `payload` into Resolve marker customData;
- if `resolve_audit.json` exists, readback marker customData covers the transition rows.

## Failure Policy

If this audit blocks, do not approve Resolve apply or call the edit V14-ready. Repair the candidate/final blueprint so transition markers carry row and recipe payloads, or repair the Resolve adapter if marker customData is being dropped. Then run `prepare_resolve_transition_apply_plan.py` and `audit_resolve_transition_apply_contract.py`, followed by unattended-first-draft, Skill maturity, V14 baseline, and the final QA suite.

This contract is the guard against a common weak edit: the plan says "rotation/whip/dissolve on BGM hit", but the actual Resolve handoff only contains plain adjacent clips and generic markers.
