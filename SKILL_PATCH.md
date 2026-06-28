# Travel Video Studio Skill Upgrade Patch

This patch captures the latest product bar for the travel-video-studio skill. It is written as an installable upgrade note because the active plugin cache may be read-only in some Codex sessions.

## Add These Rules To SKILL.md

### Reference Style Gate

Before cutting or revising a long-form travel film, create a `style_reference_report.json` and `.md` from:

- the user-specified reference creators, such as 影视飓风 and 叽叽歪歪的平行世界
- any local reference film supplied by the user, especially `/Users/pengyang/Downloads/马耳他终稿5.16.mp4`
- the current project footage contact sheets

The report must convert references into non-copying editing rules: pacing, route rhythm, transition types, title restraint, BGM energy, subtitle density, and what must not appear. Do not copy titles, narration, music, footage, or creator-specific branding.

### Opening Title Gate

The first city title must be clean and singular.

Block final delivery when the opening title moment shows:

- multiple city names stacked or competing, such as `TOKYO / OSAKA` when the chapter is Tokyo
- a second text layer, route line, date, eyebrow, internal ID, or subtitle sitting behind or too close to the hero title
- placeholder Chinese, project slugs, random IDs, or file names
- black title slate instead of approved aerial, skyline, station, street, hotel-window, vehicle, or other scenic establishing footage

The opening title manifest must declare:

```json
{
  "openingTitlePolicy": "single_city_title_only",
  "cityTitle": "TOKYO",
  "forbiddenOpeningText": ["TOKYO / OSAKA", "JAPAN 2025", "route", "project id"],
  "backgroundType": "approved_aerial_or_establishing_video"
}
```

### Vertical And Pillarbox Gate

Do not rely on stream dimensions alone. A 3840x2160 render can still contain a portrait clip with black side bars.

Every final audit must sample:

- the opening title
- every chapter title
- every day/place transition
- any clip whose source orientation is portrait, rotated, or unknown
- the exact timestamps mentioned by the user in feedback

Block final delivery if a 16:9 master contains unexplained vertical/pillarboxed material. The only allowed exceptions are intentional phone-screen inserts or social-media screenshots, and they must have a manifest row with layout, duration, reason, and designed background treatment.

### BGM-Only Scenic Mode

When the user rejects voiceover or says scenic/opening sections should not contain their voice, use `bgm_only_no_camera_voice` for scenic/title/transition beds.

Required behavior:

- import or render a continuous BGM bed on the final audio mix
- mute source camera audio and generated TTS unless explicitly approved
- keep narration as TXT/SRT when the user asks for text-only narration
- keep a `bgm_manifest.json` with local paths, track names, artists, provider URLs, and license URLs
- use license-safe/free sources such as Mixkit or Pixabay instead of untracked web rips
- verify the final render has an audio stream and that the audio policy matches the manifest

### Client-Visible Polish Gate

The Skill must not stop at "technically rendered." It must create a contact sheet and reject the edit when it still feels like a rough AI assembly:

- generic or duplicate title design
- abrupt hard cuts between travel days without transport/street/weather/food/aerial bridge shots
- sparse subtitles over long stretches
- BGM missing, inaudible, or stylistically mismatched
- source-camera talking over city establishing shots
- low frame rate, low bitrate, or non-4K delivery when the source supports 4K60
- visible black bars, rotated clips, or phone UI mistakes

### DaVinci-First Finishing Gate

When DaVinci Resolve is installed and reachable, do not claim the Skill has delivered a long-form film from an FFmpeg-only assembly. The Skill must:

- create or update a real Resolve project/timeline through the official Resolve API
- write only a new project or duplicated timeline unless the user explicitly authorizes editing an existing timeline
- import footage according to the approved blueprint
- disable source-camera/user audio when the user requests BGM-only or no voiceover
- put BGM on the declared music track, normally A3
- read the timeline back with `audit_resolve_timeline.py`
- verify that readback matches the intended title, replacement clips, track counts, source-audio policy, and BGM item
- render through Resolve when the user specifically says to use DaVinci

Use `scripts/make_davinci_stylefix_blueprint.py` for regressions like the Japan v7 draft: duplicate opening title, 7:04 portrait clip, missing BGM, or camera voice over scenic openings.

## New Scripts

Add these scripts to the skill's `scripts/` directory:

- `audit_visual_audio_style.py`: frame-sample QA for pillarbox, clean-title manifest, BGM manifest, and final audio policy
- `build_bgm_bed.py`: deterministic BGM bed builder from approved local tracks plus license manifest
- `make_davinci_stylefix_blueprint.py`: generates a DaVinci-first corrected blueprint from an older Resolve blueprint plus approved visual/BGM fix manifests

## Workflow Insert

Add this after final render verification and before `audit_client_delivery_rules.py`:

```bash
python3 <skill-dir>/scripts/audit_visual_audio_style.py \
  --video <final-render.mp4> \
  --output-dir <package>/visual_audio_style_audit \
  --sample-seconds "0,2,8,<chapter-times>,<user-feedback-times>" \
  --visual-manifest <package>/visual_polish_manifest.json \
  --bgm-manifest <package>/bgm/bgm_manifest.json \
  --audio-mode bgm_only \
  --require-clean-title
```

If this audit blocks, fix the edit and render again. Do not tell the user the Skill is good enough while this gate is failing.

## Regression Cases From The Japan Draft

- Opening must show one clean `TOKYO` title only. It must not show `TOKYO / OSAKA`, `JAPAN 2025`, route copy, subtitle text, or duplicate/ghosted title layers.
- Around 00:07:04, the edit must not include the portrait/pillarboxed `DJI_20250725084726_0288_D.MP4` segment. Use a landscape station/street/transition alternative.
- Scenic openings and transitions must not expose camera/source voice. They should use an audible BGM bed.
- The final output target remains 4K, 59.94/60 fps, and high bitrate unless a platform-specific export target says otherwise.
