# Reference Review Completeness Contract

Use this contract when the user supplies local creator/reference videos and expects the Skill to learn from them. The goal is to force full-film review before the Skill converts reference lessons into rhythm, title, transition, BGM, caption, or ending rules.

## Required Gate

Run after `prepare_reference_batch_profile.py`:

```bash
python3 <skill-dir>/scripts/prepare_reference_review_repair_plan.py --package-dir <package> --json
```

The only delivery-ready status is:

```text
ready_no_reference_review_repairs_needed
```

`ready_with_reference_review_repair_plan` is a repair state. Do not run final QA, V14, Skill maturity, or Resolve handoff as complete while repair rows remain.

## What Counts as Full Review

For every supplied reference video, record concrete observations for:

- full-film timeline strip evidence, not only a few sampled frames
- opening/title construction and first-three-minute promise
- chapter rhythm and shot-function alternation
- transition language, bridge/breath/match balance, and motion restraint
- ending aftertaste
- BGM/audio/caption behavior
- non-copying reusable Skill takeaways

Contact sheets and frame samples are navigation aids. They do not prove learning unless the repair row decision fields are completed with specific observations.

## Forbidden Shortcuts

Reject:

- learning from random screenshots or thumbnails only
- copying reference footage, title wording, subtitles, music, narration, creator branding, or unique story beats
- vague notes such as "more cinematic" or "closer to Bilibili" without evidence fields
- applying reference-style audits when full-film reference review rows are still open

## Workflow Position

The order is:

1. `prepare_reference_batch_profile.py`
2. `prepare_reference_review_repair_plan.py`
3. close every repair row decision field
4. rerun `prepare_reference_review_repair_plan.py`
5. run `audit_reference_profile_application_contract.py`
6. run `audit_reference_transition_profile_contract.py`
7. run final QA, V14 baseline, and Skill maturity

This makes reference learning reusable: another AI can inspect the repair rows and know exactly which reference-film observations must exist before claiming Parallel World/Malta-level style learning.
