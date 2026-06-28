# Editor Integration

## Preferred Order

1. **DaVinci Resolve scripting API**
   - Best professional route now that Resolve is installed.
   - Use the official Python API, not Computer Use, for the 20-minute assembly.
   - Create a new project/timeline, import source clips, place route-aware ranges, then audit.
   - Prepare render settings with `prepare_resolve_render.py`; queue/start only after the package audit reports `ready_for_final_render`.

2. **FFmpeg/direct render package**
   - Best for deterministic previews and simple final assembly.
   - No GUI control, low token cost, easy to audit.
   - Use when timeline needs cuts, fades, audio bed, subtitle burn-in, and simple overlays.

3. **FCPXML/EDL/XML handoff**
   - Best generic route for Final Cut Pro, Resolve, and Premiere import.
   - Generate importable timeline data plus a human-readable edit decision plan.
   - Good for handing to another editor or NLE.

4. **Premiere scripting/import**
   - Prefer XML/EDL import or ExtendScript if available.
   - Avoid GUI automation for routine import/export.

5. **Computer Use fallback**
   - Use only for GUI-only tools such as CapCut/Jianying when no import/API path is reliable.
   - Keep actions short: import project, load timeline, verify export settings, export.

## Current Machine Detection

Check `/Applications` for:

- DaVinci Resolve
- Final Cut Pro
- Adobe Premiere Pro
- CapCut/Jianying

If Resolve is installed, run `check_resolve_api.py`. If it is not reachable, ask the user to open Resolve and enable Local external scripting.

## Xcode vs Codex

This is a Codex plugin, not an Xcode extension. Install it in Codex through the personal plugin marketplace. Xcode is only relevant if a separate native macOS app or Final Cut extension is later developed.
