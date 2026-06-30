# Transition Watch Reel Contract

Use this contract after `prepare_transition_audition_packet.py --build-clips` and `audit_transition_audition_quality_contract.py`. The goal is to make important transition auditions reviewable as one ordered muted reel before storyboard approval, Resolve apply, final QA, or V14 handoff.

Run:

```bash
python3 scripts/prepare_transition_watch_reel.py --package-dir <package> --build-reel --json
```

Accepted statuses:

- `ready_with_transition_watch_reel`
- `ready_no_important_transitions`

Blocking conditions:

- `transition_audition_packet/transition_audition_packet.json` is missing or not ready.
- Important audition rows are not ready, missing clips, outside the package, too short, too small, or not probeable video.
- Any audition clip contains an audio stream when muted transition review is required.
- The reel is not built when important transitions exist.
- The report safety flags show Resolve writes, render queueing, downloads, or source-footage modification.

Required evidence:

- `transition_watch_reel/transition_watch_reel.json`
- `transition_watch_reel/transition_watch_reel.md`
- `transition_watch_reel/transition_watch_reel.mp4` when important transitions exist

Review rule:

Watch the reel in order. It is not a final-render substitute; it is the early review surface that catches rough day/place/title jumps, random effects, unstable landings, leaked camera audio, and unwatchable transition flow before the timeline is written or handed to another AI/editor.
