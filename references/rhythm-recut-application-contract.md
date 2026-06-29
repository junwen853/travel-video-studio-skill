# Rhythm Recut Application Contract

Use this contract after `prepare_rhythm_recut_blueprint.py`, `prepare_transition_polish_blueprint.py`, final blueprint lineage, creator-cut application, final-source usage, and timeline-variety audits. The goal is to prove that long-shot rhythm repairs actually survived into the final candidate blueprint, not only into an advisory report.

## Command

```bash
python3 <skill-dir>/scripts/audit_rhythm_recut_application_contract.py \
  --package-dir <package>
```

Optional explicit candidate:

```bash
python3 <skill-dir>/scripts/audit_rhythm_recut_application_contract.py \
  --package-dir <package> \
  --blueprint <package>/transition_polish_blueprint/resolve_timeline_blueprint_transition_polish.json
```

## Inputs

- `edit_rhythm_plan/edit_rhythm_plan.json`
- `rhythm_recut_blueprint/rhythm_recut_blueprint_report.json`
- `final_blueprint_lineage_contract_audit.json`
- `creator_cut_application_contract_audit.json`
- `final_source_usage_contract_audit.json`
- `timeline_variety_contract_audit.json`
- best package-local candidate blueprint in this order: transition polish, rhythm recut, then active `resolve_timeline_blueprint.json`

## Pass Criteria

- Upstream rhythm, creator-cut, source-usage, lineage, and timeline-variety reports are ready or passed.
- If a rhythm recut was needed, the final candidate comes from the rhythm/transition-polish candidate chain.
- Every planned recut source has the expected `main_segment` and `cutaway_insert` `rhythmRecut` annotations in the final candidate.
- Cutaway inserts are BGM-only/video-only and do not leak source-camera audio.
- The recut report reduces average primary shot length and long-shot risk while keeping timeline duration stable.
- If no recut is needed, the edit rhythm plan has no outstanding rhythm-risk rows.
- The audit is read-only: it never writes Resolve, queues renders, downloads assets, or modifies source footage.

## Blocked Means Repair

If blocked, do not hide the problem with a rotation, whip, zoom, speed-ramp, or extra title. Rebuild the rhythm recut candidate from the latest BGM phrase/effect/transition candidate chain, run transition polish again, rerun final blueprint lineage, then rerun this contract. If the candidate is approved for the actual package, fork with `prepare_rhythm_recut_apply_package.py` before Resolve apply so stale final-render evidence is not reused.
