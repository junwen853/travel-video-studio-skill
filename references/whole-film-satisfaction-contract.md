# Whole Film Satisfaction Contract

Use `scripts/audit_whole_film_satisfaction_contract.py` after render verification, editorial watchdown, final viewer friction, first-draft satisfaction, transition sequence satisfaction, reference/style, director, and unattended repair queue reports exist.

Run it before final QA, V14 baseline, Skill maturity, release/handoff claims, or telling a user that the Skill can produce a reference-level first serious draft without more feedback.

```bash
python3 <skill-dir>/scripts/audit_whole_film_satisfaction_contract.py --package-dir <package> --json
```

## What It Proves

The contract verifies the film as one viewer experience, not a collection of isolated passes:

- current final MP4 is verified and is the file being judged
- opening has promise, destination signal, clean hero title, BGM-only scenic tone, and title-zone subtitle avoidance
- chapters have context, movement, lived-in texture, payoff, and aftertaste/handoff
- rhythm avoids AI-looking long holds, short flicker runs, and repetitive shot roles
- BGM is musical, traceable, and not replaced by hum/tone/source-camera audio
- captions are audience-facing, dense, and title-safe
- transitions pass as an ordered muted viewer sequence, have rendered proof, and do not rely on random whip/rotation/template effects
- reference learning is actually applied to opening, pacing, transitions, captions, BGM, route texture, and ending
- director intent, route texture, and director polish are proven by current reports
- editorial watchdown is closed for the current output path
- final viewer friction, first-draft satisfaction, and unattended repair queue have zero open rows

## Blocking Status

`blocked_whole_film_satisfaction` means the package is not ready for final QA, V14, Skill maturity, release, or handoff.

Do not bypass this by saying all individual technical audits passed. The point is to catch the common failure where parts are valid but the whole film still feels like an AI assembly.

## Repair Rule

Every open row must name:

- source report
- viewer symptom
- owner script
- required artifact
- command
- acceptance evidence
- forbidden workaround

Repair in this order when possible: final output, opening/title, chapters/source/rhythm, BGM/captions, transitions, reference fit, director/route texture, editorial watchdown, final viewer friction, first-draft satisfaction, unattended repair queue.

After repairs, rerun the source report, then rerun this contract.

## Forbidden Workarounds

- Do not close from screenshots, contact sheets, sampled frames, stale V14 renders, or manifest prose.
- Do not use stronger transitions to hide weak source selection, missing bridge footage, or unclear route/story adjacency.
- Do not pass with hum/tone/silence/camera audio as BGM.
- Do not leave captions that speak to the editor or describe tool/QA status.
- Do not claim reference-level quality without current-output editorial watchdown closure.

## Safety

The contract is read-only. It must not write Resolve timelines, queue renders, download assets, modify source footage, or mutate a source drive.
