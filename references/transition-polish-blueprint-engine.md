# Transition Polish Blueprint Engine

Use `scripts/prepare_transition_polish_blueprint.py` after BGM phrase and rhythm recut candidates exist. This pass turns transition metadata into final micro-transition execution rows before Resolve apply.

## Purpose

The earlier transition scripts decide what should happen: grammar, execution recipes, motif safety, bridge sequences, effect motion, BGM phrase cues, and rhythm recut. This pass verifies the final candidate still keeps those decisions together after recut and writes a single non-destructive candidate blueprint with per-transition polish metadata.

## Required Behavior

- Start from the latest safe candidate blueprint, preferring `rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json`.
- Preserve all existing transition, effect, BGM phrase, bridge, and rhythm recut metadata.
- Add `transitionPolishCandidates` at the blueprint level.
- Add `transition.transitionPolishCandidate` to every candidate transition.
- Add `transitionPolishOut` / `transitionPolishIn` annotations to adjacent clips.
- Add timeline markers with `role: transition_polish_candidate_marker`.
- Keep the active `resolve_timeline_blueprint.json` untouched unless `--update-blueprint` is explicitly approved.

## Pass Rules

Every polish row should have:

- BGM sync: phrase index/section and a hit point with a `0.35s` tolerance.
- Title/subtitle avoidance: suppress captions around the transition hit and avoid title overlay collision.
- Resolve recipe: effect name, duration frames/seconds, and keyframe plan.
- Motion proof: whip, rotation, push, slide, speed ramp, or similar motion requires route-motion or bridge evidence.
- BGM-only audio policy: no source voice or camera audio may be introduced.
- Decision fields for editor approval, preflight evidence, readback evidence, and frame sample evidence.

## Reject Rules

Reject or mark repair-needed if:

- A transition has no BGM phrase cue or hit.
- A motion transition lacks motion or bridge evidence.
- A random spin, glitch, flash, shake, strobe, particle, template, or whoosh-pack style appears.
- The row hides missing route continuity with an effect.
- The row has no title/subtitle avoidance policy.

## Expected Artifacts

- `transition_polish_blueprint/resolve_timeline_blueprint_transition_polish.json`
- `transition_polish_blueprint/transition_polish_blueprint_report.json`
- `transition_polish_blueprint/transition_polish_blueprint_report.md`
- `transition_quality_contract_audit.json`
- `transition_quality_contract_audit.md`

Before Resolve apply, run:

```bash
python3 <skill-dir>/scripts/audit_transition_quality_contract.py \
  --package-dir <package>

python3 <skill-dir>/scripts/audit_resolve_blueprint.py \
  --blueprint <package>/transition_polish_blueprint/resolve_timeline_blueprint_transition_polish.json \
  --package-dir <package>
```

## Transition Quality Contract

The quality audit must pass before a final-quality claim. It checks that the best available transition-polish candidate covers every adjacent visual boundary, carries BGM-hit timing, suppresses title/subtitle collisions, keeps BGM-only audio policy, requires motion evidence for whip/rotation/speed-ramp effects, rejects template/glitch/flash/shake styles, and blocks repeated decorative-effect chains.
