# Transition Bridge Visual Evidence Contract

## Purpose

Use this contract after `audit_bridge_sequence_application_contract.py` and before final blueprint lineage, storyboard approval, Resolve apply, or final QA. It closes the gap where an edit says a day/place/title boundary has a bridge sequence, but the proof is only prose, marker metadata, or a decorative transition effect.

The contract proves important transitions have concrete local video bridge beats: station, train, street, skyline, weather, food, hotel-window, signage, water, aerial, landmark, or other real visual material that helps the viewer move from one moment to the next.

## Required Inputs

- `bridge_sequence_plan/bridge_sequence_plan.json`
- `bridge_sequence_blueprint/bridge_sequence_blueprint_report.json`
- `bridge_sequence_application_contract_audit.json`
- the selected candidate or active Resolve blueprint containing `bridge_sequence_insert` clips

The preferred command is:

```bash
python3 scripts/audit_transition_bridge_visual_evidence_contract.py --package-dir <package> --extract-frames
```

## Pass Rules

A package passes only when:

- `bridge_sequence_plan` is `ready_with_bridge_sequence_plan`
- `bridge_sequence_blueprint_report` is `ready_with_bridge_sequence_blueprint`
- `bridge_sequence_application_contract_audit` is `passed`
- every important route/title/timeline-gap/ending bridge row has applied `bridge_sequence_insert` clips
- every required beat function survives into the candidate blueprint
- every bridge insert has a local source path, existing source file, probeable video stream, and frame evidence
- every bridge insert is video-only and does not leak A1/A2 source-camera voice into BGM-only transition windows
- `blockedBridgeRowCount`, `blockedBridgeVisualClipCount`, `missingBeatClipCount`, and `sourceAudioLeakClipCount` are all zero

## Block Rules

Block the package when:

- bridge evidence is only a plan, marker, title, dissolve, rotation, or prose note
- a required bridge beat is missing from the final candidate
- a bridge beat points to a missing, non-local, non-video, or undecodable source
- frame evidence cannot be generated or found when required
- the bridge beat carries source-camera audio
- a route/title/day-change boundary relies on a single effect without physical route, title, or texture footage

## Output Contract

The script writes:

- `transition_bridge_visual_evidence_contract_audit.json`
- `transition_bridge_visual_evidence_contract_audit.md`
- optional package-local frame evidence under `transition_bridge_visual_evidence/`

Downstream gates must treat this as a hard prerequisite for storyboard approval, unattended first drafts, V14 baseline, skill maturity, and final QA.
