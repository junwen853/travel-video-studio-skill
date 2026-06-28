# DaVinci Resolve API

## Confirmed Local Install

Default macOS paths:

```text
/Applications/DaVinci Resolve/DaVinci Resolve.app
/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting
```

The official local README says external scripts require Resolve to be running and these environment values:

```bash
RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"
```

Use `scripts/check_resolve_api.py` to verify:

- app installed
- scripting module present
- `fusionscript.so` present
- Resolve process running
- API reachable
- product/version
- current project/timeline

If `check_resolve_api.py` is reachable but returns `currentPage: null`, `database: null`, `CreateProject` returns `None`, or `AddItemListToMediaPool`/`CreateEmptyTimeline` returns empty inside an `Untitled Project`, inspect the Resolve UI for blocking modals. Resolve Studio 21 can show a software update dialog before the project manager is usable; dismissing it returns the API to `currentPage: media` and `Local Database`.

When importing DJI or other large HEVC media from an external drive, prefer a small proxy smoke test first. Generate short local H.264 proxies, write a Resolve test timeline, and run `audit_resolve_timeline.py` before attempting a long-form write from original files.

## Write Contract

Before `build_resolve_timeline.py --apply`, state:

- project name
- timeline name
- fps and resolution
- tracks that will be created
- number of source files and clips
- fact that the script creates a new project/timeline and does not modify existing work

Prepare the machine-readable write contract first:

```bash
python3 <skill-dir>/scripts/prepare_resolve_apply_contract.py --package-dir <package>
```

The contract must record current delivery blockers, track plan, clip/source counts, write command, readback audit command, and explicit approval fields. It is not approval by itself.

The dry-run command is always safe:

```bash
python3 <skill-dir>/scripts/build_resolve_timeline.py --blueprint <package>/resolve_timeline_blueprint.json
```

The blueprint preflight is also safe and must run before any write approval:

```bash
python3 <skill-dir>/scripts/audit_resolve_blueprint.py --blueprint <package>/resolve_timeline_blueprint.json --package-dir <package>
```

It verifies source file existence, source in/out bounds, timeline ranges, same-track overlaps, V1 coverage gaps, generated title/place cards, subtitle sidecar status, marker/enrichment counts, and source-audio policy. A blocked preflight blocks `--apply`.

The write command requires explicit approval:

```bash
python3 <skill-dir>/scripts/build_resolve_timeline.py --blueprint <package>/resolve_timeline_blueprint.json --apply
```

## Render Contract

Preparing a render plan is safe and does not change Resolve:

```bash
python3 <skill-dir>/scripts/prepare_resolve_render.py --package-dir <package>
```

Before `prepare_resolve_render.py --queue` or `--queue --start`, state:

- project and timeline name
- output directory and custom output name
- format, codec, frame rate, resolution, `VideoQuality` high-bitrate target, and subtitle export mode
- current `delivery_audit.json` status
- current `resolve_audit.json` project/timeline match and warning status
- fact that `--queue` adds a job to the Resolve render queue, while `--start` starts rendering

Queue/start requires explicit user approval. Never queue a final render while package audit blockers remain, BGM/stock/aerial licenses are unverified, or the Resolve timeline has not been read back.

## Current API Coverage

The plugin can:

- connect to Resolve Studio through the official Python API
- create a new project
- set timeline frame rate and resolution
- create a new timeline
- create/name video, audio, and subtitle tracks
- import referenced source media
- append source ranges at explicit record frames
- convert source in/out seconds using each source media file's own probed FPS, while converting timeline record frames using the project timeline FPS
- preserve source/camera audio on A1 for footage clips marked `includeSourceAudio` by omitting `mediaType` in Resolve's append call
- enrich blueprints with subtitle cues, voiceover/BGM mix plans, stock/aerial placeholders, transition plans, and timeline markers
- write chapter, voiceover, BGM, stock/aerial, and transition markers to Resolve timelines during approved `--apply`
- import transparent subtitle overlay videos as normal video clips on V3 when visible captions are required
- save the project
- report skipped/missing source files
- generate title/place card MP4 assets and include them on V2
- preflight Resolve blueprints before write approval with ffprobe-backed range and coverage checks
- read back the current/named timeline for track and item counts
- prepare Resolve render settings in `render_plan.json`
- set `VideoQuality` in `render_plan.json`; use a numeric high-bitrate target such as `80000` for 4K long-form H.264/H.265 masters unless a platform-specific export target says otherwise
- queue and optionally start a Resolve render job through `SetRenderSettings`, `SetCurrentRenderFormatAndCodec`, `AddRenderJob`, and `StartRendering` after clean gates and explicit approval
- verify final MP4 delivery with ffprobe, sampled frame checks, full-film blackdetect, and subtitle evidence before claiming the render is deliverable

Known subtitle boundary:

- Resolve Studio 21 local smoke testing can create a subtitle track through the Python API, but `Timeline.ImportIntoTimeline(<srt>)` returned `False` and readback showed zero subtitle items. Do not claim native SRT import unless a fresh smoke test proves it on the user's installed Resolve version.
- For visible subtitles, generate an alpha overlay movie with `scripts/prepare_subtitle_overlay_asset.py`, add it to the blueprint as a V3 `subtitle_overlay_video`, write the Resolve timeline, and verify V3 item count/readback. For sidecar-only delivery, record that choice in the final report and expect `audit_story_style_contract.py` to warn unless sidecar was explicitly requested.

Still required for later passes:

- exact Resolve-native subtitle item creation if a supported API path is later verified
- route/map graphics beyond static cards
- color correction and stabilization
- extended Resolve render status polling, retry handling, and post-render publish automation

Never report those later passes as finished unless they are actually written and read back.

## Audit

After any actual `--apply`, run:

```bash
python3 <skill-dir>/scripts/audit_resolve_timeline.py --project-name "<project>" --timeline-name "<timeline>" --output <package>/resolve_audit.json
```

Delivery evidence must include item counts by video/audio/subtitle track and warnings from this audit.
