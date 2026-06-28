# Reference Batch Profile Engine

Use this reference when the user supplies multiple creator/reference videos, especially the four `叽叽歪歪的平行世界` videos plus a Malta final. The goal is to learn reusable rhythm, opening, transition, audio, caption, and ending patterns without copying assets.

## Run

Analyze a reference folder:

```bash
python3 <skill-dir>/scripts/prepare_reference_batch_profile.py \
  --reference-dir <folder-with-reference-videos> \
  --package-dir <package>
```

Analyze explicit files:

```bash
python3 <skill-dir>/scripts/prepare_reference_batch_profile.py \
  --reference /path/to/reference-1.mp4 \
  --reference /path/to/reference-2.mp4 \
  --package-dir <package>
```

Outputs under `<package>/reference/`:

- `reference_batch_profile.json`
- `reference_batch_profile.md`
- compatibility copy: `reference_analysis.json`
- per-video analyses under `reference_items/`

## What It Measures

The batch profile aggregates:

- total and average reference duration
- frame rate set
- scene-cut shot count
- average, median, p10, and p90 shot lengths
- short-shot and long-breathing-shot counts
- audio loudness and silence evidence
- sampled frame worksheet rows
- non-copying usage contract
- downstream style targets for rhythm, transition, opening, and ending

## Acceptance Bar

Pass only when:

- at least two reference videos are analyzed for a true batch profile
- per-video analysis JSON exists or is freshly generated
- aggregate `pacingProfile.status` and `audioProfile.status` are `analyzed`
- `sampleFrames` carries enough worksheet rows for visual review
- the profile is explicitly non-copying

Reject:

- using only a few random screenshots as "learning"
- copying reference titles, subtitles, branding, music, or footage
- running reference-style audits without a local reference profile when the user supplied references

## Workflow Position

Run this before `prepare_edit_rhythm_plan.py`, `audit_reference_style_alignment.py`, and `prepare_reference_style_repair_plan.py`. The generated `reference_analysis.json` compatibility file lets existing rhythm/style scripts use the batch targets without special handling.
