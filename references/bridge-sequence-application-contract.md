# Bridge Sequence Application Contract

Use this contract after `prepare_bridge_sequence_plan.py`, `prepare_bridge_sequence_blueprint.py`, and the later candidate-blueprint steps such as rhythm recut, BGM phrase, effect motion, and transition polish.

The purpose is narrow: prove that planned multi-shot bridge sequences did not disappear from the final candidate blueprint. A transition can look "polished" in metadata while still dropping the actual station, street, skyline, route-motion, or title-safe bridge beats that make the edit feel like a human travel film. This audit blocks that failure.

After this contract passes, run `audit_transition_bridge_visual_evidence_contract.py --package-dir <package> --extract-frames`. The application contract proves bridge beats survived; the visual evidence contract proves those beats point to real local video sources with probe/frame evidence and no source-camera audio.

## Required Inputs

- `bridge_sequence_plan/bridge_sequence_plan.json`
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.json`
- a package-local final candidate blueprint, inferred in this order:
  - `transition_polish_blueprint`
  - `rhythm_recut_blueprint`
  - `bgm_phrase_blueprint`
  - `effect_motion_blueprint`
  - `transition_execution_blueprint`
  - `bridge_sequence_blueprint`
  - active `resolve_timeline_blueprint.json`

Run:

```bash
python3 <skill-dir>/scripts/audit_bridge_sequence_application_contract.py --package-dir <package>
```

The script writes:

- `bridge_sequence_application_contract_audit.json`
- `bridge_sequence_application_contract_audit.md`

## Pass Criteria

- `bridge_sequence_plan` is `ready_with_bridge_sequence_plan`.
- `bridge_sequence_plan.summary.missingBeatRowCount`, `repairRowCount`, and `blockingBridgeSequenceIssueCount` are all `0`.
- `bridge_sequence_blueprint_report` is `ready_with_bridge_sequence_blueprint`.
- The selected final candidate blueprint exists and is inside the package.
- Every ready important bridge-sequence row has its planned `bridge_sequence_insert` clips in the final candidate.
- Applied bridge beat functions cover the required plan functions.
- Applied bridge beats preserve source diversity: route bridge rows must not collapse into one repeated clip, and 3+ beat rows cannot repeat the same source on adjacent beats.
- Bridge insert clips are video-only/BGM-led and do not carry source-camera audio.

## Blocking Failures

- A title/day/place/timeline-gap row was planned but no bridge insert survives in the final candidate.
- A required route-motion, establishing, lived-in, payoff, title-clean, or aftertaste bridge beat is still missing in the plan.
- The final candidate has fewer bridge insert clips than the planned required beats.
- The final candidate repeats one source across most bridge beats or repeats the same source on adjacent bridge beats.
- The final candidate keeps only a decorative transition effect where a 2-5 shot bridge sequence was planned.
- Inserted scenic/title/transition clips leak source audio.
- The selected candidate blueprint is missing, stale, or outside the package.

## Usage Rule

Do not treat transition polish, pair-continuity, or execution-readiness as sufficient by themselves. They prove the transition metadata can execute; this contract proves the physical bridge footage made it into the actual candidate cut.

Do not treat this contract alone as final bridge approval. Pair it with `transition_bridge_visual_evidence_contract_audit.json` before final blueprint lineage, storyboard approval, Resolve apply, final QA, or external handoff.
