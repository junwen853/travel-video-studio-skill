# Transition Reference Readiness Contract

Run this after all transition planning, preview, audition, watch-reel, Resolve apply, rendered-proof, and flow-repair reports exist. Run it before `transition-sequence-satisfaction-contract.md`, final QA, V14 baseline, Skill maturity, Resolve handoff, or claiming the first draft matches the Parallel World/Malta reference level.

## Required Command

```bash
python3 <skill-dir>/scripts/audit_transition_reference_readiness_contract.py \
  --package-dir <package> \
  --json
```

The only passing status is `passed`. The blocked status is `blocked_transition_reference_readiness`.

## Purpose

This is a whole-chain transition craft gate. It prevents the agent from passing isolated transition reports while the film still feels like hard concatenation, random rotation/whip effects, repeated templates, weak route jumps, missing bridge footage, unstable landings, or reference-style analysis that never reached the final candidate.

## What It Blocks

- missing or blocked pair-continuity, execution-readiness, polish-application, Resolve materialization, or Resolve apply reports
- important route/title/day/timeline transitions without applied bridge beats or visual bridge evidence
- film-level cadence that reads as bare cuts, repeated dissolves, random motion, or effect spam
- transition reference selections that only name a chosen candidate without boundary-specific reason, preview/audition proof plan, forbidden workaround, or zero decision issues
- motion accents that are too frequent, high intensity, unsupported, direction mismatched, title unsafe, or missing action/sensory anchors
- missing preview frames, audition clips, ordered watch reel, visual proof, role integrity, or storyboard evidence
- final rendered transition windows with flash, raw portrait frames, or unstable landings
- transition-flow repair rows that remain open

## Required Evidence

Every open row must include:

- source report and current status
- owner script
- command
- required artifact
- acceptance evidence
- forbidden workaround

If this contract blocks, repair via the listed owner scripts and rerun the source audits, this contract, transition sequence satisfaction, final viewer friction, unattended repair queue, final QA, V14 baseline, and Skill maturity.

## Safety

The script is read-only. It must not write Resolve, queue renders, download external assets, modify source footage, or mutate a source drive.
