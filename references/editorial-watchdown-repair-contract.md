# Editorial Watchdown Repair Contract

Use this contract after a final MP4 candidate exists and before handoff, release, or any claim that the package is viewer-ready. Technical QA proves the file is structurally valid; this gate proves the current output was watched as a film.

## Required Command

```bash
python3 <skill-dir>/scripts/prepare_editorial_watchdown_repair_plan.py \
  --package-dir <package> \
  --final-output <final-mp4> \
  --json
```

The closed status is `ready_no_editorial_watchdown_repairs_needed`. The repair status is `ready_with_editorial_watchdown_repair_plan`.

## What Must Be Reviewed

- current final MP4 path, not an old draft or stale V14 render
- opening/title/BGM-only first impression
- every chapter's context, movement, lived-in texture, payoff, and aftertaste/handoff
- day/place/chapter transitions for bridge footage, stable landing, and restrained motivated motion
- BGM/caption behavior across the whole film
- ending aftertaste and route closure
- non-copying fit to the supplied Parallel World/Malta reference lessons

## Decision Fields

Each open row must have:

- `watchAccepted=true`
- `reviewedOutputPath` matching the current final MP4
- `watchedRange`
- viewer-facing issue summary
- opening, chapter, transition, BGM/caption, ending, and reference-fit evidence
- repair action taken or explicit no-repair rationale
- post-repair audit evidence
- reviewer and review timestamp

## Blockers

Do not close this gate from screenshots, contact sheets, sampled frames, internal workflow notes, a previous output path, or technical QA alone. If a row remains open, repair through the row's owner script and rerun final QA, V14 baseline, Skill maturity, and the unattended repair queue.
