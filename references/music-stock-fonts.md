# Music, Aerials, Stock, and Fonts

## Search Policy

Use web search for current assets whenever the package needs material not already in the user's footage. Record source URLs, license notes, price/free status, and attribution requirements.

Never claim an asset is usable in final delivery until its license is checked.

Current source guidance from the 2026-06-28 web check:

- Bilibili creator-space references for 影视飓风 (`https://space.bilibili.com/946974`, official site `https://www.ysjf.com/`) and 叽叽歪歪的平行世界 (`https://space.bilibili.com/405004967/`) are style anchors only; do not copy footage, music, titles, or narration.
- Mixkit remains the preferred first-pass free BGM/stock source because its music (`https://mixkit.co/free-stock-music/`) and license (`https://mixkit.co/license/#musicFree`) pages can be recorded in the package.
- Pixabay Music (`https://pixabay.com/music/`) can be used, but keep the exact track URL, license summary URL (`https://pixabay.com/service/license-summary/`), and download/license certificate evidence. Pixabay's own FAQ (`https://pixabay.com/service/faq/`) warns that some music can still trigger automated Content ID claims even when legal to use.
- A private/nonprofit draft still uses license-friendly sourcing in this Skill so future public/client deliveries do not inherit avoidable copyright or Content ID risk.

Run:

```bash
python3 <skill-dir>/scripts/build_asset_ledger.py --delivery-plan <package>/delivery_plan.json --output-dir <package>/asset_ledger
```

The ledger is the source of truth for final delivery. BGM and aerial/stock rows must have a selected URL/local path and verified license status before final render.

After the ledger exists, run:

```bash
python3 <skill-dir>/scripts/prepare_asset_sourcing_packet.py --package-dir <package>
```

The sourcing packet is the working packet for selecting exact assets. It must include official license URLs, provider search URLs, price/free/subscription status, attribution requirements, selected asset URL, local path after download/import, and approval evidence. A search URL or license homepage is not enough by itself; every final asset must be an exact selected asset with a verified license row in the ledger.

Then run:

```bash
python3 <skill-dir>/scripts/prepare_bgm_sourcing_brief.py --package-dir <package>
```

This brief narrows BGM work into a usable travel-film search packet. It must include Mixkit/Pixabay-first searches, paid-library fallbacks, chapter mood buckets, continuous-bed/opening/transition/ending section plans, exact decision fields, and a pass/reject rubric. A missing BGM complaint is not closed until this brief exists and either a verified BGM row is recorded or the brief clearly lists the next exact asset-selection work.

Then run:

```bash
python3 <skill-dir>/scripts/prepare_bgm_selection_package.py --package-dir <package>
```

This package proves the selected music can actually ship: the final BGM bed must be local, license-traceable, long enough for the film, referenced by the active Resolve blueprint, and rebuildable from local source tracks through `build_bgm_bed.py`. A provider search URL or license homepage is not enough; the package must expose exact candidate rows, decision fields, track manifest, build command, and next BGM/audio contract audit.

Record the BGM phrase blueprint as a required later step. After transition and effect candidate blueprints exist, read `bgm-phrase-blueprint-engine.md` and run:

```bash
python3 <skill-dir>/scripts/prepare_bgm_phrase_blueprint.py --package-dir <package>
```

This blueprint step turns the selected bed into section/phrase/transition-cue metadata. A BGM complaint is not closed until opening/body/transition/ending windows, clip annotations, timeline markers, and per-transition BGM cue rows exist in a non-destructive candidate blueprint.

After phrase rows exist, read `bgm-musicality-contract.md` and run `audit_bgm_musicality_contract.py`. A BGM complaint is still open if the selected bed is a sine tone, hum, buzz, silence, placeholder, one-band audio, flat dynamics, unnamed/untraceable music, or missing opening/body/transition/ending phrase coverage.

Then run:

```bash
python3 <skill-dir>/scripts/prepare_transition_bridge_plan.py --package-dir <package>
```

This plan narrows transition and stock-footage work into usable boundary rows. It must include local-footage-first search hints, licensed stock/aerial fallback searches, exact license/provider URLs, BGM-only/no-camera-voice audio policy, subtitle title-zone policy, selected-clip decision fields, and existing Resolve bridge evidence when available. A day/place transition complaint is not closed until each boundary has a selected local bridge clip or a verified licensed fallback and `audit_route_texture_contract.py` can prove the bridge is on the actual timeline.

Then run:

```bash
python3 <skill-dir>/scripts/prepare_visual_establishing_plan.py --package-dir <package>
```

This plan narrows city aerial, landmark, and establishing-shot work into usable opening/chapter/ending rows. It must include local-footage-first search hints, trip-derived famous-place/landmark hints, licensed stock/aerial fallback searches, exact provider/license URLs, title typography evidence, existing timeline evidence, BGM-only/no-camera-voice policy, and selected-asset decision fields. A missing-aerial or generic-opening complaint is not closed until the opening, each chapter establishing row, and the ending have local scenic evidence or a verified licensed fallback and the actual Resolve blueprint/title bridge evidence can be audited.

Then run:

```bash
python3 <skill-dir>/scripts/prepare_effect_motion_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_effect_motion_blueprint.py --package-dir <package>
```

This plan narrows effect work into restrained opening/chapter/ending title reveal rows and day/place transition motion rows. Then the blueprint script materializes those rows as non-destructive candidate metadata. It must tie each motion row to title typography, transition bridge, visual establishing, and blueprint `effectPlan` evidence; record exact implementation/readback decision fields; and reject glitch, random spin, flash, shake, particle, logo-reveal, or generic template-pack effects. Motivated whip-pan or rotation match cuts are allowed only when real route-motion footage supports the boundary. A client delivery cannot be a bare concatenation, but motion should support real route footage rather than hiding weak BGM, missing bridges, duplicate titles, or wrong location evidence.

For shot-to-shot decisions, run `prepare_transition_grammar_plan.py` after creator-cut planning. Its rows decide exact adjacent-pair transitions before effect choices are implemented in Resolve.

Then run:

```bash
python3 <skill-dir>/scripts/prepare_audio_scene_policy_plan.py --package-dir <package>
```

This plan turns BGM/no-voiceover work into exact scene-window rows before Resolve writes. It must prove opening/title/visual-establishing/transition/effect/feedback windows are covered by ready A3 BGM, contain zero accidental A1/A2 source-camera or voiceover leakage, and preserve user complaint timestamps such as `reported_voice_at_7_04=7:04` as reusable regression probes. Selecting or downloading music is not enough if the scene windows can still carry the user's voice.

## BGM

For Japan/Tokyo footage, default mood:

- calm, spacious, melodic
- light piano, ambient synth, soft strings, subtle city pulse
- avoid overused high-energy vlog tracks unless user asks

Search query examples:

- `licensed cinematic Japan travel piano ambient BGM`
- `royalty free Tokyo travel documentary music license`
- `Artlist Japan travel documentary ambient`
- `Epidemic Sound Tokyo travel calm ambient`
- `Pixabay Music Japanese travel cinematic license`

## Aerial and Establishing Shots

For Tokyo, useful establishing targets:

- Tokyo Tower
- Shibuya crossing
- Shinjuku skyline
- Tokyo Skytree
- Sumida River
- Tokyo Station
- Asakusa/Senso-ji

Search query examples:

- `licensed Tokyo Tower aerial 4K stock footage`
- `Tokyo skyline aerial 4K royalty free`
- `Shibuya crossing timelapse licensed stock video`
- `Tokyo Skytree drone stock footage license`

If drone footage is legally restricted in a location, prefer licensed stock from professional libraries or high-rise/skyline establishing shots instead of pretending to fly a drone.

Do not wait until final QA to decide the city signal. `prepare_visual_establishing_plan.py` should be generated before asset decisions so the editor knows which row needs local footage, which row can use a verified stock/aerial fallback, and which exact famous-place hints are appropriate for the selected trip. The hints may include known landmarks for common cities such as Tokyo, Osaka, Hong Kong, Macau, Paris, or London, but they must be treated as selectable hints derived from the current route text, never as defaults that contaminate another trip.

## Transition Bridge Assets

Use the user's footage first. Search for station platforms, train or road windows, airport movement, taxi/metro shots, street signs, hotel windows, convenience stores, food/table details, weather, skyline, and quiet walking texture around the same chapter boundary before looking online.

Only use stock/aerial fallback when local footage cannot explain the route change. Good fallback queries are generated by `prepare_transition_bridge_plan.py`, but they should follow this shape:

- `<next city or region> station train window travel stock footage license`
- `<next city or region> skyline street ambience 4K stock video license`
- `<next city or region> airport transfer street signage travel video license`
- `<next city or region> food market hotel window travel detail stock footage`

Every fallback clip needs exact selected asset URL, license URL, local path after download, approval evidence, and a note explaining why local footage was insufficient. Do not use a stock search result as if it were already a selected/downloaded bridge clip.

## Fonts and Typography

For Japan-themed edits, prefer restrained cinematic typography:

- place cards: Hiragino Mincho ProN, Yu Mincho, Noto Serif CJK, Shippori Mincho
- subtitles: Hiragino Sans, Noto Sans CJK, Source Han Sans
- map labels: Noto Sans CJK or system sans

If a font is not installed, search for a licensed source and record the license. Do not bundle commercial fonts without permission.

Treat generic font fallback as unverified. For example, if `fc-match` returns Verdana for Noto CJK or Shippori Mincho, the requested style is not actually available; choose an installed family, download a licensed open font, or record an approved fallback before final render.

Before generating or trusting title bridge media, run:

```bash
python3 <skill-dir>/scripts/prepare_title_typography_plan.py --package-dir <package>
python3 <skill-dir>/scripts/audit_cover_title_contract.py --package-dir <package>
```

This plan must prove the opening has one clean hero title, no secondary city/date/route label behind it, no rendered subtitle overlay in the title zone, verified render-only system font or licensed font evidence, and scenic/video background evidence. The cover title contract must additionally prove the reference-style formula: high-recognition scenic background, oversized destination title, short designed English/place subtitle, clean 16:9 frame, and no route/date/project clutter. If either report blocks, regenerate scenic title bridges or repair the font/title manifest before final render.

## Visual Packaging

Use typography for:

- opening title
- day cards
- place cards
- route/map labels
- subtitle burn-in style

Keep route transitions understated: map line, ambient street insert, station/vehicle movement, or match cut by color/motion.

Before trusting effects, run:

```bash
python3 <skill-dir>/scripts/prepare_effect_motion_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_effect_motion_blueprint.py --package-dir <package>
```

Use effects only for subtle support:

- title reveals: short fade, tiny scale settle, or gentle dissolve
- transitions: match cut by direction/color, route marker, or short dissolve over real bridge footage
- ending: music-tail fade and scenic breathing room

Reject effects that feel like template overlays or short-video packs. If the cut lacks BGM, route bridges, title cleanliness, or real establishing footage, fix those upstream assets instead of masking the problem with motion graphics.
