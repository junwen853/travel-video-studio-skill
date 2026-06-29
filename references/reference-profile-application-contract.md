# Reference Profile Application Contract

Use this contract after `prepare_reference_batch_profile.py` and after the downstream story, rhythm, creator-cut, transition, caption, audio, and style audits exist. It proves that the four Parallel World videos, Malta final, or another supplied reference set were applied as aggregate non-copying edit guidance instead of being stored as an unused analysis artifact.

## Command

```bash
python3 <skill-dir>/scripts/audit_reference_profile_application_contract.py \
  --package-dir <package> \
  --json
```

For a one-reference calibration project only:

```bash
python3 <skill-dir>/scripts/audit_reference_profile_application_contract.py \
  --package-dir <package> \
  --allow-single-reference \
  --min-reference-videos 1 \
  --json
```

## Required Inputs

- `reference/reference_batch_profile.json`
- `opening_story_plan/opening_story_plan.json`
- `chapter_arc_plan/chapter_arc_plan.json`
- `edit_rhythm_plan/edit_rhythm_plan.json`
- `creator_cut_plan/creator_cut_plan.json`
- `transition_grammar_plan/transition_grammar_plan.json`
- `transition_execution_plan/transition_execution_plan.json`
- `caption_story_plan/caption_story_plan.json`
- `audio_scene_policy_plan/audio_scene_policy_plan.json`
- `reference_scene_grammar_contract_audit.json`
- `timeline_variety_contract_audit.json`
- `reference_style_alignment_audit.json`
- `director_intent_contract_audit.json`

## Pass Criteria

- The reference batch profile is a true multi-video profile by default, with analyzed pacing, audio, sample-frame, style-target, and non-copying evidence.
- Chapter-arc planning exposes reference batch status and per-chapter reference grammar.
- Edit-rhythm planning exposes the reference profile and target rhythm profile.
- Reference scene grammar and reference style alignment both pass with direct reference-profile evidence.
- Opening, creator-cut, transition, caption, audio, director-intent, and timeline-variety artifacts are ready enough to carry the reference style into the first draft.
- No artifact copies reference footage, title text, captions, narration, music, creator branding, or visible watermark elements.

## Repair Route

If blocked, do not claim the Skill has learned the references. Regenerate or repair the missing downstream plan first. Typical fixes are: rerun `prepare_reference_batch_profile.py`, rerun `prepare_chapter_arc_plan.py`, rerun `prepare_edit_rhythm_plan.py`, rerun creator-cut and transition planning, then rerun reference-style, director-intent, scene-grammar, and timeline-variety audits before this contract.
