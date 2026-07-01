# One-Shot Autonomy Contract

Use this contract when the Skill must prove that another agent can receive a large unordered travel-footage folder and produce a V14-level first draft without repeated user diagnosis.

The gate is intentionally higher than a normal package check. It aggregates raw intake, full-source selection, story structure, edit rhythm, creator-style shot choice, clean titles, dense viewer-facing captions, BGM-only audio, BGM musicality, default transition selection, ordered muted transition watch reel, watch-reel sequence review, transition-sequence satisfaction, reference-profile application, reference-transition language, reference scene grammar, timeline variety, director intent, route texture, final-viewer friction, current-output editorial watchdown closure, first-draft satisfaction, unattended repair closure, whole-film satisfaction, unattended first-draft chain closure, and Resolve blueprint preflight.

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
- `transition_watch_reel/transition_watch_reel.json` is `ready_with_transition_watch_reel` or `ready_no_important_transitions`; important transition rows must be package-local, muted, ordered, and built into a reel.
- `transition_watch_reel_review_contract_audit.json` is `passed` or `passed_no_important_transitions`, with no audio leakage, repeated template run, stacked high-intensity motion, or blocked review row.
- `reference_profile_application_contract_audit.json`, `reference_transition_profile_contract_audit.json`, `reference_scene_grammar_contract_audit.json`, and `timeline_variety_contract_audit.json` are `passed`; reference learning must reach concrete opening, chapter, rhythm, creator-cut, transition, caption, audio, scene-grammar, timeline-variety, and bridge/breath/match/motion-balance evidence.
- `director_intent_contract_audit.json` and `route_texture_contract_audit.json` are `passed` or `passed_with_warnings`, with warning statuses recorded as caveats rather than hidden viewer-facing defects.
- `editorial_watchdown_repair_plan/editorial_watchdown_repair_plan.json` is `ready_no_editorial_watchdown_repairs_needed` for the current final MP4.
- `unattended_repair_queue/unattended_repair_queue.json` is `ready_no_unattended_repairs_needed`.
- `whole_film_satisfaction_contract_audit.json` is `passed`.

Forbidden shortcuts:

- Do not claim the Skill has learned from V14, Malta, or the reference videos while one-shot autonomy rows remain open.
- Do not claim Bilibili/Malta-style delivery from aggregate satisfaction alone when reference-profile application, reference-transition profile, reference scene grammar, timeline variety, director intent, or route texture reports are missing or blocked.
- Do not substitute final QA, Skill maturity, V14 baseline, or prose notes for closing this gate.
- Do not treat a technically renderable Resolve blueprint as one-shot ready unless source choice, story, rhythm, BGM, captions, titles, transitions, whole-film satisfaction, and repair closure are all connected.
