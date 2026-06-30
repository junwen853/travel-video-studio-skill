# Transition Sequence Satisfaction Contract

This contract turns "the transitions still feel bad" into a blocking, machine-readable gate.

## Purpose

Use `scripts/audit_transition_sequence_satisfaction_contract.py` after transition reference-readiness and before final viewer friction, first-draft satisfaction, final QA, V14 baseline, or handoff.

It verifies the transition system as one viewer sequence, not only as isolated JSON rows:

- The ordered transition watch reel exists when important transitions exist, is package-local, and is muted.
- Watch-reel review passes with no audio leakage, invalid timing, repeated template-family runs, or stacked high-intensity motion.
- Bridge, breath, route meaning, viewer orientation, scene settlement, and stable landing evidence are closed.
- Motion accents are rare, motivated, title-safe, BGM-hit aligned, and not back-to-back.
- Resolve apply and rendered-transition proof show visible transitions actually survive into the final candidate/export.
- Reference transition profile and reference-profile application prove the learned Parallel World/Malta transition language is applied without copying assets.

## Required Status

The contract passes only when:

- `status` is `passed`.
- `summary.requiredSequenceReportCount` covers the transition sequence source reports.
- `summary.passedSequenceReportCount == summary.requiredSequenceReportCount`.
- `summary.transitionSequenceRowCount == 0`.
- `summary.p0TransitionSequenceRowCount == 0`.
- `summary.metricIssueCount == 0`.

`blocked_transition_sequence_satisfaction` means the cut is not ready for final QA, V14, or handoff.

## Metric Blockers

The gate blocks on sequence symptoms that are easy to miss in isolated reports:

- `transition_watch_reel_review_contract_audit.summary.reelHasAudio == true`.
- `highIntensityRunMax > 1`.
- `familyRunMax > 2`.
- `motionAccentRunMax > 1`.
- `shortClipRunMax > 2`.
- Any open repair, blocker, missing evidence, pending manual visible effect, black/white flash, portrait frame, source-audio leak, unstable landing, or nonzero transition-readiness metric issue.

## Repair Rule

Every open row must name:

- `ownerScript`.
- `requiredArtifact`.
- `command`.
- `acceptanceEvidence`.
- `forbiddenWorkaround`.

Do not repair a weak transition sequence by adding stronger effects. Repair the source issue: shot order, route bridge, local bridge footage, BGM-hit timing, title/caption safety, Resolve apply proof, rendered proof, or reference-fit evidence.

## Safety

The audit is read-only. It must not write Resolve, queue renders, download assets, modify source footage, or mutate the source drive.
