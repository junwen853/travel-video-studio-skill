# One-Shot Autonomy Contract

Use this contract when the Skill must prove that another agent can receive a large unordered travel-footage folder and produce a V14-level first draft without repeated user diagnosis.

The gate is intentionally higher than a normal package check. It aggregates raw intake, full-source selection, story structure, edit rhythm, creator-style shot choice, clean titles, dense viewer-facing captions, BGM-only audio, BGM musicality, default transition selection, transition-sequence satisfaction, final-viewer friction, first-draft satisfaction, unattended repair closure, whole-film satisfaction, unattended first-draft chain closure, and Resolve blueprint preflight.

Required behavior:

- Read only package reports. Do not write Resolve, queue renders, download assets, mutate source footage, or modify the source drive.
- Block when required reports are missing, stale, unaccepted, or accepted with metric evidence that still undermines one-shot delivery.
- Convert every open issue into a repair row with owner script, required artifact, command, acceptance evidence, and forbidden workaround.
- Treat `blocked_one_shot_autonomy` as a hard stop before final QA, V14 baseline, Skill maturity, release, or handoff.
- Allow explicit caveat/warning statuses only where upstream contracts already accept them, such as non-GPS route honesty or blueprint preflight warnings; record these as warnings rather than hiding them.

Passing evidence:

- `one_shot_autonomy_contract_audit.json` has status `passed`.
- `summary.oneShotAutonomyRowCount`, `p0OneShotAutonomyRowCount`, and `metricIssueCount` are all `0`.
- `summary.passedReportCount` equals `summary.requiredReportCount`.
- `unattended_repair_queue/unattended_repair_queue.json` is `ready_no_unattended_repairs_needed`.
- `whole_film_satisfaction_contract_audit.json` is `passed`.

Forbidden shortcuts:

- Do not claim the Skill has learned from V14, Malta, or the reference videos while one-shot autonomy rows remain open.
- Do not substitute final QA, Skill maturity, V14 baseline, or prose notes for closing this gate.
- Do not treat a technically renderable Resolve blueprint as one-shot ready unless source choice, story, rhythm, BGM, captions, titles, transitions, whole-film satisfaction, and repair closure are all connected.
