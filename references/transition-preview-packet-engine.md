# Transition Preview Packet Engine

Use this engine after transition grammar, visual-match, scene-arc, effect-palette, microstructure, pair-continuity, execution-readiness, transition-polish, bridge-application, and final-blueprint-lineage checks exist, and before `audit_transition_preview_quality_contract.py`, `prepare_transition_audition_packet.py`, `audit_transition_audition_quality_contract.py`, and `audit_transition_storyboard_contract.py`.

## Purpose

The storyboard contract should not approve important travel transitions from metadata alone. The preview packet turns each important day/place/title/timeline-gap/ending boundary into package-local frame evidence that another agent or editor can inspect without reopening the whole source folder.

## Command

```bash
python3 <skill-dir>/scripts/prepare_transition_preview_packet.py \
  --package-dir <package> \
  --extract-frames \
  --update-transition-grammar
```

Use `--include-all-rows` when every adjacent pair needs review, not only important boundaries. Omit `--extract-frames` only for a dry-run command packet.

## Inputs

- `transition_grammar_plan/transition_grammar_plan.json`
- `resolve_timeline_blueprint.json`
- readable local source video paths for the outgoing and landing clips
- optional bridge source path in the transition grammar decision fields

## Outputs

- `transition_preview_packet/transition_preview_packet.json`
- `transition_preview_packet/transition_preview_packet.md`
- `transition_preview_packet/row_###/preview.md`
- package-local JPEG frames such as `outgoing.jpg`, `bridge.jpg`, and `landing.jpg` when extraction succeeds
- optional updates to `transition_grammar_plan.json` decision fields: `previewStripEvidence` and `frameSampleEvidence`

## Pass Criteria

The packet is ready when every selected important boundary has:

- an outgoing frame or existing outgoing preview evidence
- a landing frame or existing landing preview evidence
- a preview row markdown path
- no missing required source path
- no failed frame extraction

`ready_no_important_transitions` is acceptable only when the transition grammar has no important day/place/title/timeline-gap/ending boundaries.

After the packet is ready, run `audit_transition_preview_quality_contract.py`, then build and audit the transition audition packet. Do not approve storyboard, Resolve apply, final QA, maturity, or V14 baseline until the quality audit proves the generated frames decode, are not blank, outgoing/landing evidence is not identical, and the audition layer proves important transitions can be watched as muted local MP4s.

## Blockers

Block instead of approving storyboard when:

- `transition_grammar_plan.json` is missing or has no transition rows
- source paths are missing or point at unavailable files
- `ffmpeg` is unavailable and no existing frame evidence is present
- extraction fails for required outgoing or landing samples
- the packet is only `needs_frame_extraction`

## Safety

The script writes only package-local preview files and optional package-local transition grammar decision fields. It does not write Resolve, queue renders, download assets, modify source footage, or modify source drives.
