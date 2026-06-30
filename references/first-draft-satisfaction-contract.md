# First Draft Satisfaction Contract

Use `scripts/audit_first_draft_satisfaction_contract.py --package-dir <package>` after final viewer friction and transition reference-readiness reports exist, and before final QA, V14 baseline, Skill maturity, or handoff.

```bash
python3 <skill-dir>/scripts/audit_first_draft_satisfaction_contract.py \
  --package-dir <package> \
  --json
```

The only passing status is `passed`. The blocked status is `blocked_first_draft_satisfaction`.

This gate answers one question: if another agent receives a large unordered travel-footage folder, has the first serious draft already closed the failures that previously required many manual V1-V14 corrections?

## What It Aggregates

- Full-source intake, large-source unattended readiness, source selection, first assembly, final source usage, and creator-cut application.
- Opening story, clean scenic title, title visual proof, title repair closure, and establishing material.
- BGM selection, BGM-only/no-voiceover policy, BGM musicality, and audience-facing captions.
- Chapter arcs, shot flow, scene grammar, rhythm, pacing, timeline variety, and narrative adjacency.
- Transition-flow repair closure, transition reference-readiness, ordered watch reel, rendered transition proof, and Resolve transition apply proof.
- Full-film reference review, reference repair closure, reference profile application, reference transition profile, director intent, route texture, director polish, editorial watchdown, and final viewer friction.

It deliberately does not require `final_qa_suite_report.json`, `v14_baseline_contract_audit.json`, or `skill_maturity_contract_audit.json`; those gates should depend on this one, not the other way around.

## Blocked Rows

Every blocked row must include:

- `ownerScript`
- `requiredArtifact`
- `command`
- `acceptanceEvidence`
- `forbiddenWorkaround`
- read-only safety flags

If a row lacks those fields, fix the Skill or the audit script before claiming maturity.

## Forbidden Workarounds

- Do not make the gate pass by deleting a required report from the aggregate list.
- Do not claim reference-level quality from final QA alone while this gate is blocked.
- Do not hide weak source selection with stock, title cards, stronger transitions, or BGM.
- Do not hide rough transitions with random rotation, whip, flash, speed-ramp, or template effects.
- Do not close BGM rows with hum, tone, silence, source-camera audio, or generated voiceover when BGM-only delivery was requested.
- Do not close title rows from manifest prose or stale screenshots; use package-local frame evidence.

## Repair Order

Repair P0 rows in this order:

1. Source and route.
2. Opening/title/establishing.
3. BGM and captions.
4. Story spine and rhythm.
5. Transitions and Resolve apply proof.
6. Reference fit and route texture.
7. Watchdown and final viewer friction.

After repairs, rerun the source report, this contract, unattended repair queue, final QA, V14 baseline, and Skill maturity as applicable.
