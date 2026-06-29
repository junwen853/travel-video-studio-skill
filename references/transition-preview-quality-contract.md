# Transition Preview Quality Contract

Use this contract immediately after `prepare_transition_preview_packet.py` and before `audit_transition_storyboard_contract.py`, Resolve apply, final QA, maturity, or V14 baseline claims.

Run:

```bash
python3 <skill-dir>/scripts/audit_transition_preview_quality_contract.py \
  --package-dir <package>
```

The audit reads `transition_preview_packet/transition_preview_packet.json` and writes:

- `transition_preview_quality_contract_audit.json`
- `transition_preview_quality_contract_audit.md`

It is read-only. It does not write Resolve, queue renders, download assets, modify source footage, or modify the source drive.

## Pass Criteria

Important route, title, timeline-gap, chapter, and ending transitions need inspectable package-local preview evidence:

- the preview packet status is `ready_with_transition_preview_packet` or `ready_no_important_transitions`
- every important preview row has outgoing and landing frame outputs
- at least two important-role frames decode and pass minimum size checks
- frames are not black/blank
- outgoing and landing frames are not byte-identical
- blocked preview-quality rows equal zero

Very dark or low-detail frames are warnings, not automatic blockers, so night scenes can still pass after the frames decode and are not blank.

## Blockers

Block storyboard approval when the audit reports:

- missing `transition_preview_packet/transition_preview_packet.json`
- preview packet status is not ready
- required outgoing or landing frame output is missing
- frame file is missing, too small, or undecodable
- frame mean luma is below the blank-frame floor
- outgoing and landing frames are identical

Do not work around this with a prose note. Repair the transition preview packet by regenerating frames from the real source clips, replacing weak source selections, or choosing a different bridge/landing shot, then rerun this audit and storyboard.
