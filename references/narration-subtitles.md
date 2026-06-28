# Narration, TTS, and Subtitles

## Voiceover Style

Default voiceover language is Chinese unless the user asks otherwise. Keep it long-form travel-documentary-like:

- natural and warm
- not a tourist-guide lecture
- location-aware
- not overconfident when route recognition is uncertain
- allow short pauses around establishing shots and transitions
- preserve quiet stretches; a 20-minute film should not be wall-to-wall narration

For each chapter, write:

- one place-card line
- one voiceover paragraph
- one optional transition line into the next chapter

For a 20-minute film, the voiceover can be only a few minutes total if the footage, BGM, and natural sound carry the rest.

## TTS

Local default is macOS `say`, because it avoids cloud upload and can create audio immediately. Use cloud TTS only after explicit approval.

Use:

```bash
python3 <skill-dir>/scripts/make_voiceover_audio.py --script voiceover_script.txt --output-dir voiceover
```

For a package-level flow that also refreshes title cards and Resolve enrichment, prefer:

```bash
python3 <skill-dir>/scripts/prepare_delivery_assets.py --package-dir <package> --generate-local-voiceover
```

Omit `--generate-local-voiceover` when only title/place cards and enrichment should be prepared.

The script creates:

- `voiceover.aiff`
- `voiceover.m4a` when FFmpeg is available
- `subtitles.srt` estimated from line lengths and audio duration

If a high-quality commercial TTS is required, create a provider-specific request plan and record provider, voice, cost, and license/usage rules.

## Subtitle Rules

- Generate SRT even if timing is approximate.
- Keep each subtitle short enough for mobile reading.
- Use punctuation to create natural pauses.
- After audio is produced, retime subtitles by actual audio duration or ASR alignment.
- Burn-in subtitles only after user approves style; otherwise deliver `.srt`.
- When the user rejects voiceover, treat TXT/SRT captions as the narrative layer and do not generate local TTS.
- Keep opening, chapter, and ending title zones clean. Suppress or trim rendered subtitle overlays inside those title windows unless the user explicitly asks for captions over titles.
- For a no-voiceover long-form travel film, subtitles should be dense enough to carry route, emotion, and visual honesty. Use at least 4 cues/minute as a planning target unless a slower reference profile justifies otherwise.

Run:

```bash
python3 <skill-dir>/scripts/prepare_caption_story_plan.py --package-dir <package>
```

This plan must exist before subtitle overlay generation or maturity claims. It writes `caption_story_plan/caption_story_plan.json`, `.md`, and `text_only_narration_export.txt`. The plan records full-film and per-chapter cue targets, actual cue count, cues/minute, longest subtitle gap, title-zone suppression policy, no-voiceover/TXT/SRT policy, caption functions, rewrite decision fields, and a pass/reject rubric. If it reports `needs_caption_expansion`, add cues or rewrite the SRT/TXT before rendering.

## Audio QA

Target final mix:

- voiceover intelligible over BGM
- music under narration, typically around -24 to -18 LUFS relative bed depending on content
- avoid clipping
- include short fades around chapter changes

When the user rejects voiceover or complains that scenic/opening/transition moments contain their voice, switch the planning default to `bgm_only_no_camera_voice`. Before any Resolve apply, run:

```bash
python3 <skill-dir>/scripts/prepare_audio_scene_policy_plan.py --package-dir <package> --feedback-timestamps reported_voice_at_7_04=7:04
```

Use the timestamp argument only for actual user-reported moments. The resulting plan must keep A3 BGM active, A1/A2 source or voiceover audio muted/absent, and intentional ambience disabled unless explicitly approved with a reason.
