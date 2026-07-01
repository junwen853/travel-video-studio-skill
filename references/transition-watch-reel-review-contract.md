# Transition Watch Reel Review Contract

Use this contract after `prepare_transition_watch_reel.py --build-reel --require-muted`. It audits the ordered reel as one sequence, not as scattered per-row clips.

Run:

```bash
python3 scripts/audit_transition_watch_reel_review_contract.py --package-dir <package> --json
```

Accepted statuses:

- `passed`
- `passed_no_important_transitions`

Blocking conditions:

- `transition_watch_reel/transition_watch_reel.json` is missing or not ready.
- The watch reel report was not generated with muted-review policy enabled: `summary.requireMuted`, `inputs.requireMuted`, and `policy.watchReelMuteRequired` must all be `true`.
- `transition_watch_reel/transition_watch_reel.mp4` is missing, not probeable, or contains audio.
- Reel row timing is invalid or out of order.
- Any review row lacks a storyboard purpose plus bridge, motion, or sensory reason.
- One transition family repeats too long, making the sequence feel templated.
- High-intensity whip/rotation/speed/zoom/flash motion repeats or dominates the reel.

Required evidence:

- `transition_watch_reel_review_contract_audit.json`
- `transition_watch_reel_review_contract_audit.md`
- The underlying `transition_watch_reel/transition_watch_reel.mp4`

Editorial rule:

The watch reel must prove the transition language is readable before Resolve apply. A reel that technically exists but plays like random effects, repeated rotation templates, or high-energy motion covering weak shot choices is not reference-ready.
