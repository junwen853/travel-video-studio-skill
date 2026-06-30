# Unattended Repair Queue Engine

Use `scripts/prepare_unattended_repair_queue.py --package-dir <package>` after the core planning, transition, reference-repair, final viewer friction, first draft satisfaction, and Resolve preflight reports exist, and before `audit_unattended_first_draft_contract.py`, `audit_v14_baseline_contract.py`, `audit_skill_maturity_contract.py`, or final handoff.

The engine does not edit Resolve, queue renders, download assets, modify source footage, or write to mounted source drives. It reads package reports and writes:

- `unattended_repair_queue/unattended_repair_queue.json`
- `unattended_repair_queue/unattended_repair_queue.md`

If `final_qa_suite_report.json` already exists, the queue also reads its blocked stages and creates extra repair rows for untracked final-QA failures. This is not a dependency cycle: the queue does not require final QA to exist, and it skips summary/meta stages such as V14 baseline or Skill maturity so the agent repairs the underlying blocked reports first. If `first_draft_satisfaction_contract_audit.json` is missing or blocked, the queue routes it through `audit_first_draft_satisfaction_contract.py` instead of letting final QA hide the aggregate issue.

## Purpose

This queue turns a large set of blockers into ordered, machine-readable repair work. A future agent should not need to infer what to fix first from dozens of audit files. Each repair row must name:

- priority: `P0` before `P1`
- phase: intake/route, source selection, story spine, caption/audio, title/establishing, creator cut, transition flow, reference style, or Resolve preflight
- source report and blocker
- owner script
- required artifact
- command
- acceptance evidence
- forbidden workaround
- no-write safety flags

## Status Meanings

- `ready_no_unattended_repairs_needed`: all required reports are present and accepted; the queue is empty.
- `ready_with_unattended_repair_queue`: blockers or missing reports exist, but every row has an executable repair route.
- `blocked_unactionable_repair_queue`: at least one row is missing an owner script, command, artifact, acceptance evidence, forbidden workaround, or no-write safety proof.

`ready_with_unattended_repair_queue` is not a delivery pass. It only means the next agent has a usable repair route. The package remains blocked until the source audits, first-draft satisfaction audit, unattended first-draft audit, V14 baseline, and final QA pass.

## Repair Principles

- Fix source intake, route truth, and source selection before style, stock, or transition polish.
- Fix opening/chapter story spine before rhythm recut and creator-cut claims.
- Fix BGM/audio/caption policy before any Resolve apply when scenic/title/transition windows are involved.
- Fix title and establishing evidence before cover/title or director-polish claims.
- Fix creator cut and final source usage before adding stronger effects.
- Fix bridge, match, breathing-room, choreography, storyboard, and final-cut smoothness before adding whip, rotation, speed-ramp, flash, or zoom effects.
- Fix Resolve transition apply blockers before handoff: pending manual visible effects must become API-supported cuts, materialized bridge clips, or completed Resolve readback plus frame-sample evidence. `--allow-planned-manual-visible-effects` is never an unattended repair.
- Fix final QA blocked stages through their owner preparation scripts, not by rerunning final QA repeatedly. BGM, caption, title, reference style, source selection, transition preview/audition/choreography, Resolve apply, render, and package-integrity stages each need concrete repair artifacts before the next final QA run.
- Fix reference-style rows with artifacts and closure evidence instead of repeating "make it closer to the reference."
- Never use an effect, stock insert, black card, generic title, or stale QA report to hide a blocker from a lower phase.

## Typical Command

```bash
python3 <skill-dir>/scripts/prepare_unattended_repair_queue.py --package-dir <package> --json
```

Then run:

```bash
python3 <skill-dir>/scripts/audit_unattended_first_draft_contract.py --package-dir <package> --json
python3 <skill-dir>/scripts/audit_first_draft_satisfaction_contract.py --package-dir <package> --json
python3 <skill-dir>/scripts/audit_v14_baseline_contract.py --package-dir <package> --json
python3 <skill-dir>/scripts/run_final_qa_suite.py --package-dir <package>
```
