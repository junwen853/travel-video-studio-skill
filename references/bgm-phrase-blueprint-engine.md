# BGM Phrase Blueprint Engine

Use this reference after `prepare_bgm_selection_package.py` has produced a verified local BGM bed and after bridge/transition/effect candidate blueprints exist. The goal is to make music feel intentionally cut, not merely present.

## Command

```bash
python3 <skill-dir>/scripts/prepare_bgm_phrase_blueprint.py --package-dir <package> --json
```

The default behavior is non-destructive. It writes:

- `bgm_phrase_blueprint/resolve_timeline_blueprint_bgm_phrase.json`
- `bgm_phrase_blueprint/bgm_phrase_blueprint_report.json`
- `bgm_phrase_blueprint/bgm_phrase_blueprint_report.md`

Only use `--update-blueprint` after the report, candidate blueprint, Resolve preflight, and audio-readback expectations are approved.

## What It Must Materialize

- top-level `bgmPhraseCandidates[]` rows for opening/title, chapter/body, transition, and ending sections
- `audioPlan.bgmPhraseMap` with selected bed, target duration, phrase rows, and transition cue count
- `timelineMarkers[]` with role `bgm_phrase_candidate_marker`
- per-clip `bgmPhraseCandidates` annotations for clips overlapping BGM phrase windows
- per-transition `bgmPhraseCandidate` cue metadata so cuts, dissolves, whip/rotation match cuts, and bridge inserts are tied to phrase boundaries

## Pass Bar

- Selected BGM bed is local, license-traceable, target-duration-covering, and already accepted by `bgm_selection_package`.
- Opening/title, transition, body, and ending windows are present as candidate rows.
- Every candidate transition has a BGM phrase cue.
- Scene windows remain `bgm_only_no_camera_voice`; audio policy must not report source/voiceover leakage.
- The candidate blueprint leaves active package files untouched unless explicitly approved.

## Reject Bar

- BGM is only a URL, search result, or prose note.
- Transitions are selected without phrase-boundary cue metadata.
- Effects are used to hide weak bridge footage, missing route texture, missing BGM, or title problems.
- The script downloads music, writes Resolve, queues render, mutates source footage, or silently replaces the active blueprint.

## Resolve Handoff

Before applying the candidate, run a Resolve blueprint preflight against the candidate JSON and check that A3 BGM, transition cues, title-zone safety, and no A1/A2 source voice leakage remain true after timeline readback. If the candidate is approved, fork the package or use the explicit update path so old QA reports are not reused.
