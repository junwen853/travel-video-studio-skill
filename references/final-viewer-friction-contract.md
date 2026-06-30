# Final Viewer Friction Contract

Run this contract after final technical/style reports and `transition-reference-readiness-contract.md` exist, and before `first-draft-satisfaction-contract.md`, unattended repair queue, final QA handoff, V14 baseline claims, Skill maturity claims, or release.

## Required Command

```bash
python3 <skill-dir>/scripts/audit_final_viewer_friction_contract.py \
  --package-dir <package> \
  --json
```

The only passing status is `passed`. The blocked status is `blocked_final_viewer_friction`.

## Purpose

This is an aggregation gate for viewer-facing roughness. It does not replace watching the whole film, but it prevents a technically valid export from hiding unresolved viewer problems across title, BGM, captions, source selection, story spine, transitions, reference fit, route texture, and editorial watchdown.

## What It Blocks

- missing or blocked final render verification
- weak opening/title proof, ghosted/stacked titles, route/date clutter, or missing title frame evidence
- workflow/report-like subtitles instead of viewer-facing travel text
- hum/tone/silence/voice leakage instead of musical BGM-only scenic sound
- sampled-folder or filename-order cutting from large unordered sources
- weak creator-cut source use, flat pacing, or chapter landmark stacks
- rough transitions, missing bridge/landing proof, repeated high-intensity effects, or marker-only visible transitions
- reference/Malta/Parallel World analysis that was not applied to real package artifacts
- route texture gaps and an unclosed whole-film editorial watchdown

## Required Evidence

Every open row must include:

- viewer symptom
- source report and current status
- owner script
- command
- required artifact
- acceptance evidence
- forbidden workaround

If this contract blocks, repair via the listed owner scripts and rerun the source audits, transition reference-readiness, this contract, first-draft satisfaction, unattended repair queue, final QA, V14 baseline, and Skill maturity.

## Safety

The script is read-only. It must not write Resolve, queue renders, download external assets, modify source footage, or mutate a source drive.
