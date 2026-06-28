# Reference Style Repair Engine

Use this reference after reference-style, director-intent, director-polish, transition execution, or final QA checks expose that the cut still does not feel close enough to the user's Parallel World/Malta references.

The repair engine turns vague style feedback into a concrete repair queue. It does not edit Resolve, render, download assets, or modify source footage.

## Run

```bash
python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py --package-dir <package>
python3 <skill-dir>/scripts/audit_transition_quality_contract.py --package-dir <package>
python3 <skill-dir>/scripts/audit_reference_repair_closure.py --package-dir <package>
```

Optional local reference profile:

```bash
python3 <skill-dir>/scripts/prepare_reference_style_repair_plan.py \
  --package-dir <package> \
  --reference-analysis <package>/reference/reference_analysis.json
```

Outputs:

- `reference_style_repair_plan/reference_style_repair_plan.json`
- `reference_style_repair_plan/reference_style_repair_plan.md`
- `transition_quality_contract_audit.json`
- `transition_quality_contract_audit.md`
- `reference_repair_closure_audit.json`
- `reference_repair_closure_audit.md`

## What It Repairs

The plan reads available audits and planning artifacts, then creates one repair row for each blocked style/director/QA gap. Rows cover:

- missing reference profile or non-copying reference evidence
- weak opening promise, destination proof, clean hero title, arrival, lived-in texture, or first handoff
- route arc gaps: arrival, movement, exploration, closure
- missing physical bridge footage between places/days
- weak lived-in texture between landmarks
- long raw holds, filename-order pacing, slideshow structure, or missing cutaways
- BGM/voice leakage, sparse subtitles, or editor-facing captions
- abrupt ending without route aftertaste
- hidden upstream QA blockers

Each row must include:

- source audit and blocked check
- repair area and priority
- owner script
- required artifact
- repair action
- acceptance evidence
- reference rule
- safety flags
- decision/readback/render-frame evidence fields

## Acceptance Bar

Pass only when:

- every blocked reference/director/QA check has an exact repair row
- P0 rows identify the next artifact to regenerate or audit
- P0 rows are closed by `audit_reference_repair_closure.py` before another Resolve/final-quality claim
- shot pacing, opening/title, route bridge, audio/caption, and ending issues map to concrete Skill scripts
- the plan stays non-destructive

Reject:

- generic advice such as "make it more cinematic"
- hiding weak footage behind spin, flash, glitch, or template effects
- claiming reference quality before rerunning the originating audits

## Workflow Position

Run this after `prepare_rhythm_recut_blueprint.py` during safe workflow and again after rendered-draft audits. Use the repair plan as the bridge from "the audit says it is not good enough" to "these are the exact rows to fix before the next Resolve write"; use the closure audit as the gate that proves P0 rows have required artifacts, post-repair audits, and readback/frame evidence.
