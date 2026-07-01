# BGM Musicality Contract

Use this after `prepare_bgm_selection_package.py`, `prepare_bgm_phrase_blueprint.py`, and `audit_bgm_audio_contract.py` when a travel film must feel music-led rather than merely contain audible audio.

## Command

```bash
python3 <skill-dir>/scripts/audit_bgm_musicality_contract.py --package-dir <package>
```

The audit writes:

- `bgm_musicality_contract_audit.json`
- `bgm_musicality_contract_audit.md`

## What It Blocks

- sine tones, hums, buzzes, silence, placeholders, and procedural test beds that can pass simple audibility checks
- BGM manifests without named, traceable music rows
- BGM selection packages without positive audition evidence, provider/music identity, explicit non-procedural/non-tone decisions, Content-ID check, or opening/body/transition/ending fit notes
- selected beds without opening/body/transition/ending phrase coverage
- one-band audio, flat dynamics, clipped audio, or mostly silent beds
- transitions that are not tied to BGM phrase cues when a phrase blueprint exists

## Repair Order

1. Replace hum/tone/procedural beds with a real local music track or a built bed from traceable local tracks.
2. Fill the BGM selection decision with provider, music identity type, positive audition result, audition notes, structure notes, opening/body/transition/ending fit notes, explicit `isProceduralGenerated=false`, explicit `isPlaceholderTone=false`, and Content-ID risk check.
3. Rebuild the full-duration A3 bed with `build_bgm_bed.py` when multiple source tracks need crossfades.
4. Rerun `prepare_bgm_selection_package.py`, then `prepare_bgm_phrase_blueprint.py`.
5. Rerun `audit_bgm_audio_contract.py` and this musicality audit before Resolve apply or final QA.
6. If this audit passes with warnings, do a human listen pass before claiming reference/Malta-quality delivery.

## Safety

This audit only reads package JSON and decodes the selected BGM bed through ffmpeg. It must not download music, write Resolve, queue renders, or modify source footage.
