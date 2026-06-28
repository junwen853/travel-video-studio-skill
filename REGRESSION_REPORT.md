# Travel Video Studio Regression Report

Generated in workspace:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade
```

## User Feedback Converted Into Tests

- Opening title must be one clean city title. The Japan draft feedback specifically rejected ghosted/duplicated title layers such as `TOKYO / OSAKA` plus extra route/date text.
- Around 00:07:04, the draft must not insert a portrait/pillarboxed source clip into a 16:9 master.
- Scenic openings and transition shots must not expose source-camera/user voice when the user asked for BGM-led/no-voiceover delivery.
- BGM must be audible, continuous, and documented by a manifest with track paths and license URLs.

## Smoke Test Results

### Clean Opening Segment

Command:

```bash
python3 travel-video-studio-skill-upgrade/scripts/audit_visual_audio_style.py --video /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/v9_fix_inputs/segments/v9_clean_opening_tokyo_title_only.mp4 --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/opening --sample-seconds 0,2,7.5 --visual-manifest /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/v9_fix_inputs/v9_fix_manifest.json --require-clean-title
```

Result: `passed`

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/opening/visual_audio_style_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/opening/contact_sheet.jpg
```

### 00:07:04 Replacement Segment

Command:

```bash
python3 travel-video-studio-skill-upgrade/scripts/audit_visual_audio_style.py --video /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/v9_fix_inputs/segments/v9_replace_vertical_0288_with_landscape_station.mp4 --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/replacement_704 --sample-seconds 0,6,14,24
```

Result: `passed`

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/replacement_704/visual_audio_style_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/replacement_704/contact_sheet.jpg
```

### Original Bad Portrait Source

Command:

```bash
python3 travel-video-studio-skill-upgrade/scripts/audit_visual_audio_style.py --video "/Volumes/My Passport/2025日本东京大阪行ac4/DJI_20250725084726_0288_D.MP4" --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bad_vertical_0288 --sample-seconds 0,6,14,24
```

Expected result: `blocked`

Actual result: `blocked`

Detected failures:

```text
Pillarbox/vertical content suspected at 0.000s
Pillarbox/vertical content suspected at 6.000s
Pillarbox/vertical content suspected at 14.000s
Pillarbox/vertical content suspected at 24.000s
```

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bad_vertical_0288/visual_audio_style_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bad_vertical_0288/contact_sheet.jpg
```

### Full Blueprint Orientation Gate

User correction: do not only fix the named 00:07:04 clip. The Skill must scan every actual Resolve blueprint video `sourcePath` so any raw portrait/square/unknown source is replaced, explicitly designed, or blocked before delivery.

New finding:

```text
The v13 blueprint still contained DJI_20250725093642_0289_D.MP4 at 445.79s.
ffprobe display geometry: 1080x1920 portrait, rotation 270 degrees.
```

Skill fixes added:

- `audit_client_delivery_rules.py` now ffprobe-scans every blueprint video source path and adds the hard gate `Resolve blueprint contains no raw portrait/square/unknown video clips in the 16:9 master`.
- `make_davinci_stylefix_blueprint.py` now scans all source clips, writes `manualQualityFix.orientationFixes`, and replaces or blocks every raw non-landscape source instead of hard-coding only the user-reported 0288 clip.
- `audit_skill_maturity_contract.py` now requires client-rule evidence that actual Resolve blueprint source paths contain no raw portrait/square/unknown clips.

Positive fixture:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/orientation_stylefix_positive_fixture
```

Result:

```text
client_delivery_rules_audit.json: passed
checkedVideoClipCount: 155
blockedNonLandscapeCount: 0
orientationFixes: DJI_20250725093642_0289_D.MP4 replaced before Resolve import
```

Negative fixture:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/orientation_raw_portrait_negative_fixture
```

Expected result: `blocked`

Actual result: `blocked`

Detected blocker:

```text
Resolve blueprint contains no raw portrait/square/unknown video clips in the 16:9 master
firstBlocked: /Volumes/My Passport/2025日本东京大阪行ac4/DJI_20250725093642_0289_D.MP4
geometry: raw 1920x1080, rotation 270, display 1080x1920 portrait
```

### DaVinci v14 Orientation Repair Delivery

Real DaVinci API regression package:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair
```

Result:

```text
Resolve project: 日本东京大阪行 Resolve Longform v14 Orientation Repair
Timeline: 日本东京大阪行 20min Master v14 Orientation Repair
Final render: renders/japan_tokyo_osaka_v14_orientation_repair_4k59.mp4
Final QA suite: passed, 17/17 stages
Video: 3840x2160, 59.94fps, 79.97 Mbps, 1200.17s
Audio: AAC stereo, A3 BGM only, -19.3 LUFS, silence ratio 5.9%
Blackdetect: 0 black segments
```

Regression fixes proven by this package:

- `prepare_orientation_repair_package.py` now rewrites JSON/text inside copied asset directories, not only top-level package files, so `asset_ledger`, BGM manifests, title manifests, subtitle overlay manifests, and visual polish manifests do not retain stale source-package paths.
- `prepare_orientation_repair_package.py` now removes absolute `sourcePackage` paths from active Resolve blueprints and stores only `sourcePackageName`, keeping strict portable handoff clean.
- `prepare_orientation_repair_package.py` now syncs `clean_scenic_title_bridges_manifest.json` title segment paths from the final blueprint, so a repaired opening title such as `v9_clean_opening_tokyo_title_only.mp4` does not conflict with an older manifest segment.
- `prepare_resolve_render.py` now writes `VideoQuality` into Resolve render settings, defaulting to numeric `80000` for high-bitrate 4K masters; `audit_delivery_package.py` blocks missing or low `VideoQuality`.
- `audit_bgm_audio_contract.py` and `audit_story_style_contract.py` now discover the latest `qa/**/visual_audio_style_audit.json`, not only the legacy top-level visual audit path.
- `audit_director_intent_contract.py` no longer hard-blocks on final QA status, avoiding a circular dependency where final QA contains the director intent audit.
- `audit_skill_maturity_contract.py` accepts director intent `passed_with_warnings` when all concrete director-intent metrics pass and only the final-QA informational warning remains.
- `prepare_final_delivery_report.py` now writes `FINAL_DELIVERY_REPORT.json` and `.md`, including machine-auditable route caveat wording for non-GPS visual route reconstruction.

Key user-feedback gates now pass:

```text
Opening title: single clean TOKYO title, no TOKYO TOKYO / route/date ghosting
00:07:04 / 424s area: landscape station footage, no raw 0289 portrait source
BGM: present on A3, audible, no A1/A2 source or voiceover leakage
Stock/aerial: opening aerial verified, 22 optional stock placeholders explicitly closed by real route-texture coverage
Strict portable package integrity: passed
```

### Forward-Test Stale Evidence Guard

New defect found after adding the full blueprint orientation gate: the old cross-project forward-test trusted `final_qa_suite_report.json` from the known-good v13 package, even though that report was generated before the new blueprint source-orientation gate existed. This allowed stale "known-good" evidence to remain green while the current client audit correctly blocked on `DJI_20250725093642_0289_D.MP4`.

Skill fixes added:

- `audit_skill_forward_test_contract.py` now requires the ready package to pass both the historical full final QA suite and the current `client_delivery_rules_audit.json`.
- The current client audit must include the latest `Resolve blueprint contains no raw portrait/square/unknown video clips in the 16:9 master` row, with `blockedNonLandscapeCount: 0` and no probe errors.
- If a new gate invalidates the old ready package, the forward-test blocks until a new real package/render is created or the ready package is genuinely repaired and revalidated.

Current expected forward-test result after this stricter guard:

```text
status: blocked
blocker: Known-good package current client audit includes the latest blueprint source-orientation gate
reason: v13 current client audit blocks on DJI_20250725093642_0289_D.MP4 at 445.79s
```

### BGM Builder

Command:

```bash
python3 travel-video-studio-skill-upgrade/scripts/build_bgm_bed.py --track-manifest /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/bgm/v9_bgm_manifest.json --output /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bgm_test/bgm_test_12s.m4a --duration 12 --manifest-output /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bgm_test/bgm_test_manifest.json
```

Result: `passed`

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bgm_test/bgm_test_12s.m4a
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bgm_test/bgm_test_manifest.json
```

### Opening With BGM Final-Gate Test

Command:

```bash
python3 travel-video-studio-skill-upgrade/scripts/audit_visual_audio_style.py --video /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bgm_test/opening_with_bgm_test.mp4 --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/opening_with_bgm_audit --sample-seconds 0,2,7.5 --visual-manifest /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/v9_fix_inputs/v9_fix_manifest.json --bgm-manifest /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/bgm_test/bgm_test_manifest.json --audio-mode bgm_only --require-clean-title
```

Result: `passed`

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/opening_with_bgm_audit/visual_audio_style_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/opening_with_bgm_audit/contact_sheet.jpg
```

## Current Limitation

The previously rendered v9 20-minute MP4 was not present in the package `renders/` directory during this audit pass, so the new visual/audio gate was validated on repair segments and a short muxed BGM test rather than the full final render. Once a final 20-minute render exists, run the full command in `INSTALL.md` and keep its report beside the package.

## Malta Reference Analysis

Command:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/analyze_reference_video.py --reference /Users/pengyang/Downloads/马耳他终稿5.16.mp4 --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference
```

Result: `passed`

Key finding: the reference is about 39.91 minutes and should calibrate the Skill toward long-form route documentary pacing, with sparse narration, transport texture, street/food/interior details, and emotional aftertaste.

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference/reference_analysis.md
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference/reference_contact_sheet.jpg
```

## DaVinci v10 StyleFix Regression

User correction: the Skill must use DaVinci Resolve, not only FFmpeg or documentation.

Created a new Resolve-backed package:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_1750_davinci_v10_stylefix_bgm
```

Generated DaVinci-first blueprint:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_1750_davinci_v10_stylefix_bgm/resolve_timeline_blueprint.json
```

Key blueprint fixes:

- Project: `日本东京大阪行 Resolve Longform v10 DaVinci StyleFix BGMOnly`
- Timeline: `日本东京大阪行 20min Master v10 DaVinci StyleFix BGMOnly`
- Opening V2 clip: `v9_clean_opening_tokyo_title_only.mp4`
- 00:07:04 replacement: `v9_replace_vertical_0288_with_landscape_station.mp4`
- Source camera/user audio: disabled for all video clips
- BGM: `v9_mixkit_serene_travel_bed_20min.m4a` on A3

Resolve write result:

```text
requestedClipCount: 63
appendedClipCount: 63
requestedSourceAudioClipCount: 0
sourceAudioTimelineItemCount: 0
appendedAudioAssetCount: 1
```

Resolve readback evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_1750_davinci_v10_stylefix_bgm/resolve_readback_audit_v10.json
```

Readback verified:

```text
A1 Source audio itemCount: 0
A2 Voiceover itemCount: 0
A3 BGM itemCount: 1
V2 opening item: v9_clean_opening_tokyo_title_only.mp4
V1 around 00:07:04 item: v9_replace_vertical_0288_with_landscape_station.mp4
```

DaVinci render job:

```text
jobId: 841354ca-2b59-4bc7-be19-77127e531507
customName: 日本东京大阪行_20min_Master_v10_DaVinci_StyleFix_BGMOnly_4K60
targetDir: /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_1750_davinci_v10_stylefix_bgm/renders
```

The job must be allowed to finish, then verified with:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/verify_render_delivery.py ...
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_visual_audio_style.py ...
```

Use the actual installed plugin cache path for the current session if the cachebuster version differs.

## DaVinci v11r4 Subtitle Overlay Regression

User correction: final travel edits must use DaVinci Resolve directly and must include visible subtitles, BGM, scenic opening/ending, route-aware transitions, and high-quality 4K60 export.

Created final Resolve-backed package:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_1850_davinci_v11_subtitle_overlay
```

Final DaVinci output:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_1850_davinci_v11_subtitle_overlay/renders/日本东京大阪行_20min_Master_v11r4_DaVinci_SubtitleOverlay_4K60.mp4
```

Key Skill fixes validated:

- DaVinci Resolve Studio 21 API is reachable and current project/timeline are v11r4.
- Native SRT import is not assumed: local Resolve 21 smoke test failed direct `ImportIntoTimeline(<srt>)`.
- Visible subtitles are rendered as 95 transparent MOV segments on V3.
- Resolve readback verifies V1=55, V2=8, V3=95, A1=0, A2=0, A3=1, skipped clips=0, warnings=0.
- Opening is a single clean `TOKYO` over establishing footage.
- 00:07:04 no longer uses a portrait/pillarboxed source.
- A3 BGM is present and audible; A1 source camera audio and A2 voiceover are disabled.
- Final render is 3840x2160, 59.94fps, about 111.873 Mbps, with AAC stereo audio.

Final QA results:

```text
render_delivery_verification.json: passed
visual_audio_style_audit/visual_audio_style_audit.json: passed
client_delivery_rules_audit.json: passed
story_style_contract_audit.json: passed
longform_delivery_audit.json: passed_with_caveats
```

The only remaining caveat is not a technical blocker: per-clip GPS-grade geolocation is unproven because the source videos contain no GPS metadata. Route labels are reconstructed from Codex visual inspection and source chronology, and the Skill must keep this caveat visible unless a later provider verifies exact per-clip locations.

## DaVinci v12 Scenic Chapter Title Regression

New defect found after v11: final contact sheet showed the 60s chapter moment still used a copied black `title_cards/chapter_1.mp4` slate with long cropped place text. The old client audit incorrectly passed because it trusted `v8_visual_polish_manifest.json` instead of verifying the actual Resolve blueprint source paths.

Skill fixes added:

- `audit_client_delivery_rules.py` now checks actual blueprint title/chapter source paths and blocks `title_cards`/image slates, missing sources, or long visible title text.
- `audit_resolve_blueprint.py` and `audit_delivery_package.py` now treat `chapter_title_bridge` as a valid video-only title/bridge role.
- v12 package replaces six old `place_card` clips with scenic `chapter_title_bridge` clips from `v8_visual_polish/segments`.

v12 package:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_1945_davinci_v12_scenic_chapter_titles
```

DaVinci readback before final render:

```text
Project: 日本东京大阪行 Resolve Longform v12 DaVinci Scenic Chapter Titles
Timeline: 日本东京大阪行 20min Master v12 DaVinci Scenic Chapter Titles
video: V1=55, V2=8, V3=95
audio: A1=0, A2=0, A3=1, A4=0
subtitle: S1=0
```

Render job queued and started:

```text
jobId: 9d14e7cc-786c-4ba8-8f33-4c3d2c9ee172
```

## DaVinci v13 Feedback Regression Gate

New Skill lesson: every concrete user complaint must become a reusable regression gate, not just a one-off fix to the current film.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_feedback_regressions.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_feedback_regressions.py
```

Validated on the v13 Resolve-rendered package:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Command:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_feedback_regressions.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --feedback-timestamps opening_title=0,seven_minute_four_vertical_bgm_voice=7:04 --include-title-points
```

Result: `passed`

Regression checks now covered:

- final Resolve render exists and `render_delivery_verification.json` passed
- Resolve readback matches the current v13 blueprint timeline
- opening title is a single clean city title with no ghosted route/date text
- visual/audio audit has no forbidden title OCR hits
- opening, 00:07:04, and title/chapter moments have no portrait/pillarbox regression
- BGM-only mix is audible at feedback/title moments
- Resolve readback proves A1 source audio = 0, A2 voiceover = 0, A3 BGM = 1
- scenic/title clips do not request source-camera audio
- visible subtitle overlay is dense and intentionally suppressed during title zones

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/feedback_regression_audit/feedback_regression_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/feedback_regression_audit/contact_sheet.jpg
```

Installed `SKILL.md` now requires this audit after user feedback and treats live edit fixes as Skill regression testing. The Bilibili/Malta style reference was also updated with current creator/source anchors and a license-friendly BGM sourcing rule.

## Reference Style Alignment Gate

New Skill lesson: passing technical render QA is not enough. The Skill must also prove the cut has route rhythm and lived-in travel texture instead of feeling like an AI assembly.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_reference_style_alignment.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_reference_style_alignment.py
```

Validated on the v13 Resolve-rendered package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_reference_style_alignment.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Result: `passed`

Score: `100.0%`

Reference-style checks now covered:

- Malta/Bilibili reference material exists and is treated as non-copying style guidance
- 20-minute long-form duration is met
- route is broken into multiple day/place chapters with a visible travel arc
- transport and connective tissue are first-class story material
- street, lived-in, and landmark beats are balanced
- real footage variety is sufficient; the edit is not a slideshow skeleton
- opening, chapters, and ending have scenic title/bridge structure
- no-voiceover mode is carried by BGM and dense captions
- upstream technical/client/feedback audits support the style claim

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/reference_style_alignment_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/reference_style_alignment_audit.md
```

## Package Integrity / Stale Evidence Gate

New Skill lesson: a package can render correctly while still carrying stale paths from older delivery packages. That is dangerous because future AI/editor handoffs may accidentally treat old subtitles, BGM, voiceover markers, or render reports as current evidence.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_package_integrity.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_package_integrity.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_package_integrity.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Default result after closure upgrade: `passed`

Strict portable handoff command:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_package_integrity.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --strict-portable
```

Strict result after closure upgrade: `passed`, with no blockers and no warnings.

Repair performed on v13:

- `resolve_timeline_blueprint.json` now points `assets.subtitles` to the current package's `subtitles_v4_dense.srt`
- disabled voiceover marker text in the blueprint no longer points to the old v7 voiceover path
- dependent audits were regenerated after the blueprint repair: client delivery rules, story style contract, reference style alignment, feedback regression

The previous warning is now explicitly closed: `resolve_audit.json` preserves the factual DaVinci readback marker text from the already-written timeline, which still contains an old disabled voiceover marker note. `audit_package_integrity.py` now classifies it as `closed_disabled_voiceover_marker_reference` only when A1=0, A2=0, A3>0, `bgm_audio_contract_audit.json` passes, and `story_style_contract_audit.json` passes. It does not represent an active A2 voiceover item or current blueprint dependency.

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/package_integrity_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/package_integrity_audit_strict_portable.json
```

## Title Bridge Contract Gate

New Skill lesson: OCR can miss a clean rendered title, but the Skill still needs deterministic proof that the title bridge is structurally correct. The opening-title complaint should be guarded by manifest, media, Resolve blueprint, and subtitle-zone contract evidence rather than OCR alone.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_title_bridge_contract.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_title_bridge_contract.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_title_bridge_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Result: `passed`

Title contract checks now covered:

```text
clean title manifest exists
Resolve blueprint exists
opening has exactly one clean city title segment
opening title avoids rejected route/date labels
segment and overlay assets exist
title bridge media are video clips, not title-card/image slates
Resolve V2 title clips match manifest paths and titles
Resolve title clips import video-only
title bridge windows have no stacked text clips or subtitle overlays
subtitle title-zone policy covers every title bridge
OCR miss is kept as a warning when structural title evidence passes
```

Negative fixture:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/title_stack_negative_fixture
```

The fixture injects a `subtitle_overlay_video` clip over the 0-8s opening title window. Expected result: `blocked`. Actual result: `blocked` on `Title bridge windows have no stacked text or subtitle overlay layers`.

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/title_bridge_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/title_bridge_contract_audit.md
```

## BGM Audio Contract Gate

New Skill lesson: a render can have audible music while the package still carries stale BGM evidence from an older delivery package. The user's "no source/user voice, add BGM" complaint needs one deterministic audio contract that links the final MP4, BGM manifest, Resolve blueprint, DaVinci readback, feedback timestamp windows, and asset ledger.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_bgm_audio_contract.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_bgm_audio_contract.py
```

Initial validation on the v13 package correctly blocked:

```text
BGM manifest output matches Resolve blueprint BGM asset: blocked
BGM bed is materialized inside the current package: blocked
Asset ledger verifies the actual BGM bed used in Resolve: blocked
```

Repair performed on v13:

- `bgm/v9_bgm_manifest.json` now points `output` to the current v13 package BGM bed.
- `asset_ledger/asset_license_ledger.json` now records the actual `v9_mixkit_serene_travel_bed_20min.m4a` used by Resolve, instead of an old v7 original ambient file.
- `audit_package_integrity.py` now treats `bgm_audio_contract_audit.json` and `title_bridge_contract_audit.json` as core reports.

Re-run command:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_bgm_audio_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Final result: `passed`

BGM contract checks now covered:

```text
BGM manifest exists and declares bgm_only_no_camera_voice
BGM manifest output matches Resolve blueprint assets.bgm
BGM bed is materialized inside the current package
BGM duration covers the final render
BGM source tracks are traceable and travel-appropriate
Resolve blueprint has a full-film A3 BGM cue
voiceover and source-camera audio are disabled
scenic/title/transition windows have no A1/A2 voice or source-audio overlaps
DaVinci readback has A3 BGM and no A1/A2 items
rendered BGM is audible and not mostly silent
feedback/title timestamps prove audible BGM and no leaked voice
asset ledger verifies the actual BGM bed used in Resolve
```

Negative fixture:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/scenic_audio_overlap_negative_fixture
```

The fixture injects an A2 `voiceover_audio` clip over the 0-8s opening scenic/title window. Expected result: `blocked`. Actual result with `--allow-external-bgm-bed`: `blocked` only on `Scenic/title/transition windows have no A1/A2 voice or source-audio overlaps`.

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/bgm_audio_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/bgm_audio_contract_audit.md
```

## Route Texture Contract Gate

New Skill lesson: a technically valid long-form render can still feel like an AI assembly if days/places are joined only by title cards or hard cuts. The user's target is a Bilibili/Malta-like travel film, so the Skill needs deterministic proof that route movement, street life, daily details, and landmark payoffs exist on the actual timeline.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_route_texture_contract.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_route_texture_contract.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_route_texture_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Result: `passed`

Route texture contract checks now covered:

```text
planned transitions are backed by explicit physical bridge clips
chapter title moments have nearby route connective tissue
chapters contain texture beyond title cards
global timeline balances transport, street life, daily detail, and landmarks
opening and ending breathe on real visual material
slideshow/title-card sources cannot masquerade as route texture
story/style/title/BGM upstream audits support the route-texture claim
```

v13 evidence summary:

```text
transitionPlanCount: 6
bridgeClipCount: 13
matchedTransitions: 6
chapterTitleCount: 6
matchedTitleBoundaries: 5
chapterWindowCount: 6
passedChapters: 6
transport/street/lived-in/landmark counts: 46 / 46 / 43 / 43
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/route_texture_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/route_texture_contract_audit.md
```

## Stock/Aerial Closure Gate

New Skill lesson: stock/aerial search rows are not deliverable evidence by themselves. The Skill must either materialize a verified local aerial/stock asset, or explicitly prove that the search-only placeholder is not used by the final Resolve timeline and is covered by real local route/title footage. This keeps the Skill from pretending a web-search TODO is a finished insert.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_stock_aerial_closure.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_stock_aerial_closure.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_stock_aerial_closure.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --update-blueprint
```

Result: `passed`

Stock/aerial closure checks now covered:

```text
blueprint stockInsertPlan rows are inspected and classified
required opening aerial or establishing asset is verified and used
ending title uses real establishing footage instead of a slate
final Resolve timeline source paths do not depend on unresolved stock placeholders
route texture audit proves optional stock placeholders are covered by real footage
placeholders are either materialized or explicitly closed
existing director-polish stock warnings are explainable by closure evidence
```

v13 evidence summary:

```text
stockInsertPlanCount: 22
placeholderCount: 22
closedPlaceholderCount: 22
unresolvedPlaceholderCount: 0
verifiedAerialCount: 1
sourcePathRiskCount: 0
routeTexturePassed: true
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/stock_aerial_closure_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/stock_aerial_closure_audit.md
```

## Director Polish Contract Gate

New Skill lesson: once titles, BGM, route texture, subtitles, stock/aerial closure, and Resolve output individually pass, the Skill still needs one final director-level evidence chain. Otherwise a cut can look technically valid while still feeling like a template: weak opening, unproven font/asset choices, wrong BGM mood, no subtle effects plan, or unresolved stock/aerial placeholders.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_director_polish_contract.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_director_polish_contract.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_director_polish_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Result: `passed`

Director polish checks now covered:

```text
upstream technical/story/route/title/BGM/visual audits support the polish claim
opening uses one clean city title over verified aerial or establishing footage
chapter and ending typography are restrained and title-safe
BGM mood, license, and Resolve A3 mix are travel-film appropriate
effect plan exists and stays subtle/restrained rather than template-heavy
dense rendered subtitles stay out of title zones
final render is 4K, high-frame-rate, high-bitrate, and long-form
final title/V2 polish media are not black slates, image cards, or placeholders
stock/aerial closure evidence proves optional search placeholders are not render dependencies
```

v13 evidence summary:

```text
upstreamPassed: 8 / 8
titleSegmentCount: 8
chapterTitleCount: 6
bgmTrackCount: 9
effectPlanCount: 2
renderedSubtitleCount: 92
stockInsertBacklogCount: 22
stockAerialClosureStatus: passed
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/director_polish_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/director_polish_contract_audit.md
```

## Portable Handoff Integrity Gate

New Skill lesson: strict package integrity should not leave vague cross-package warnings for another AI/editor. If an old package path is only a disabled voiceover marker, the Skill must close it with Resolve/audio evidence instead of either hiding it or blocking blindly.

Updated installed Skill scripts:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_package_integrity.py
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/run_final_qa_suite.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/run_final_qa_suite.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --feedback-timestamps opening_title=0,seven_minute_four_vertical_bgm_voice=7:04
```

Result: `passed`

Portable handoff checks now covered:

```text
package integrity distinguishes active cross-package dependencies from closed historical references
disabled voiceover marker paths close only when Resolve readback proves A1=0, A2=0, A3>0
BGM/audio contract and story style contract must both pass before a voiceover marker is closed
final QA accepts package integrity only as passed, not passed_with_warnings
```

v13 evidence summary:

```text
package_integrity_audit: passed
package_integrity_audit_strict_portable: passed
coreCrossPackagePathCount: 1
activeCoreCrossPackagePathCount: 0
closedCoreCrossPackagePathCount: 1
criticalCrossPackagePathCount: 0
closed reference: closed_disabled_voiceover_marker_reference
closure evidence: A1=0, A2=0, A3=1, bgmAudioContract=passed, storyStyleContract=passed
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/package_integrity_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/package_integrity_audit_strict_portable.json
```

## Style Source Anchor Refresh

New Skill lesson: creator-reference requests must become inspectable source anchors, not only vague taste words. The Skill should preserve non-copying Bilibili/Malta style references and practical licensed-BGM source routes so another AI can repeat the research.

Updated installed Skill reference:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/references/bilibili-travel-style.md
```

Refresh notes:

```text
2026-06-28 source anchors added for 影视飓风 Bilibili space, 叽叽歪歪的平行世界 Bilibili space, Mixkit music/license pages, and Pixabay music/license discovery.
The reference keeps these as style/source anchors only; it forbids copying exact videos, narration, music, or titles.
```

## Story Opening Title Regression Gate

New Skill lesson: a passed story/style report must not contain `TOKYO TOKYO` or similar duplicate opening-title evidence. The user's opening-title complaint needs to be guarded at both the title-bridge level and the broader story/style contract level.

Updated installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_story_style_contract.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_story_style_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --audio-mode bgm_only --require-rendered-subtitles
```

Result: `passed`

v13 opening-title evidence after repair:

```text
openingTitleCount: 1
openingTitleText: TOKYO
openingTitleValues: [TOKYO]
openingSubtitleValues: []
forbiddenHits: []
repeatedTitleValues: []
mismatchedFieldValues: []
```

Negative function check:

```text
TOKYO -> False
TOKYO TOKYO -> True
OSAKA OSAKA -> True
OSAKA -> TOKYO -> False
日本日本 -> True
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/story_style_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/story_style_contract_audit.md
```

## Location Truth Contract Gate

New Skill lesson: the Skill must optimize reusable travel-footage reasoning, not just one finished film. It must distinguish "route-aware edit is possible from visual frame review" from "every video has verified exact location." For no-GPS footage, the allowed claim may be visual route reconstruction with caveats; exact per-video geolocation needs GPS, user-confirmed labels, or verified cloud/per-video evidence.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_location_truth_contract.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_location_truth_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Result: `passed_with_caveats`

v13 location-truth evidence:

```text
indexedVideoCount: 59
expectedActiveSourceCount: 58
activeRecognitionRows: 58
recognizedVideoCount: 58
recognitionCoverageRatio: 1.0
frameCount: 236
framesPerVideo: 4.069
chapterCount: 6
routeVideoCoverage: 58
verifiedPerClipLocationCount: 0
gpsMetadataVideoCount: 0
weakConfidenceVideoCount: 15
cloudFramesSent: 0
cloudRecognitionErrorCount: 4
primaryRecognitionProvider: codex_visual_inspection
claimLevel: visual_route_ready_with_caveats
routeAwareEditClaimAllowed: true
exactPerVideoLocationClaimAllowed: false
```

Strict proof that exact per-video claims are blocked:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_location_truth_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --require-verified-per-clip-location --output-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/location_truth_strict_probe
```

Expected/actual result: `blocked`

Blocker:

```text
Verified per-clip location was required but only 0/58 active videos have GPS/user/cloud-verified labels.
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/location_truth_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/location_truth_contract_audit.md
```

## Director Intent Contract Gate

New Skill lesson: passing technical/style audits is still not enough if the edit has no explicit director intent. The Skill needs a reusable gate that proves the film has a mission, route arc, chapter beat logic, long-form shot rhythm, caption-led story/honesty, BGM/no-voiceover support, and ending aftertaste before it claims Bilibili/Malta-like quality.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_director_intent_contract.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_director_intent_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Result: `passed`

v13 director-intent evidence:

```text
mainClipCount: 55
medianMainClipSeconds: 28.0
subtitleCueCount: 95
cuesPerMinute: 4.75
chapterCount: 6
passed: 8
blocked: 0
warnings: 0
```

The script also writes a reusable manifest:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/director_intent_manifest.json
```

Validated downstream effects:

```text
director_polish_contract_audit: passed, upstreamPassed 9/9
skill_maturity_contract_audit: passed, total 15/15
final_qa_suite_report: passed, total 17/17
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/director_intent_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/director_intent_contract_audit.md
```

## Cross-Trip Forward-Test Contract Gate

New Skill lesson: the Skill must not overfit the Japan v13 package. After substantial Skill revisions, it should prove three behaviors at once: a known-good package still passes, a separate matched trip is correctly blocked before unsafe cutting, and an unknown mounted media root is not silently selected.

Forward-test evidence from `/Volumes/My Passport`:

```text
/Volumes/My Passport/ac4 20250729 backup -> 168 videos -> needs_identification
/Volumes/My Passport/2025日本东京大阪行ac4 -> 59 videos -> ready_for_project_workflow -> 日本东京大阪行-6c28b7
/Volumes/My Passport/2025姥爷港澳行ac4 -> 35 videos -> ready_for_project_workflow -> 姥爷港澳行-ac4-外置盘素材库预检-c0cb5d
```

港澳 project state:

```text
mediaIndex: 35 videos
frameIndex: 35 videos / 140 frames
videoLocationMap: 35 videos
routeTimeline: 2 chapters
confirmedRoute: missing
cloud provider key: missing
local Ollama: offline/model missing
```

The Hong Kong/Macau recognition report was expected to block:

```text
Cloud vision recognition did not actually run for this latest pass; route/location rows are not Mimo-verified.
confirmed_route_timeline.json is still a broad scaffold instead of day/place chapters.
Route review still needs human decisions before a client-deliverable route-aware cut.
```

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_skill_forward_test_contract.py
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/prepare_blocked_project_recovery_plan.py
```

Blocked-project recovery plan:

```text
status: recovery_plan_ready
editingAllowedNow: false
mediaVideoCount: 35
frameCount: 140
phaseCount: 6
blockerTypes: cloud_call_not_approved, confirmed_route_missing, multi_root_choice, provider_missing, recognition_blocked, route_not_ready, route_review_pending, unknown_media_root
```

Recovery plan evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/recovery_plan/blocked_project_recovery_plan.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/recovery_plan/blocked_project_recovery_plan.md
```

Validated command:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_skill_forward_test_contract.py --intake-json /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/intake/external_media_intake.json --ready-package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --blocked-project-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d --blocked-location-truth-json /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/location_truth/location_truth_contract_audit.json --blocked-recovery-plan-json /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/recovery_plan/blocked_project_recovery_plan.json --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/forward_contract
```

Result: `passed`

Summary:

```text
passed: 7
blocked: 0
warnings: 0
total: 7
```

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/external_media_discovery.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/intake/external_media_intake.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/location_truth/location_truth_contract_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/forward_contract/skill_forward_test_contract_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_hk_macau/forward_contract/skill_forward_test_contract_audit.md
```

## Skill Maturity Contract Gate

New Skill lesson: the final handoff should prove the reusable Skill covers the user's original failure set, not only that the current render has a pile of green reports. Add one package-level maturity contract that maps user complaints to Skill rules, scripts, references, and package evidence.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_skill_maturity_contract.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_skill_maturity_contract.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy
```

Result: `passed`

Maturity checks now covered:

```text
Skill instructions preserve regression-first, DaVinci-first, no-default-Ollama, clean-title, BGM/no-voiceover, and strict-handoff rules
required scripts exist for route recognition, DaVinci delivery, and user-regression gates
Bilibili/Malta style references are source-anchored and non-copying
final render is 4K, high-frame-rate, high-bitrate, and verified
feedback audit covers opening title and 7:04 vertical/BGM/voice complaints
story audit rejects duplicate/stacked opening titles
location truth separates route-ready visual reconstruction from exact per-video geolocation
director intent proves opening mission, route arc, long-form pacing, captions, and ending aftertaste
forward-test script exists and Skill instructions require cross-trip validation after substantial revisions
BGM-only, route texture, stock/aerial closure, director polish, and strict portable handoff all pass
```

v13 evidence summary:

```text
passed: 15
blocked: 0
warnings: 0
total: 15
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/skill_maturity_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/skill_maturity_contract_audit.md
```

## Final QA Suite Gate

New Skill lesson: individual audits are easy to forget under deadline pressure. The Skill now needs a single final handoff gate that runs or verifies every final render, style, feedback, location-truth, director-intent, stock/aerial closure, director-polish, package-integrity, and Skill-maturity check in one report.

Added installed Skill script:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/run_final_qa_suite.py
```

Backup copy:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/run_final_qa_suite.py
```

Validated on the v13 package:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/run_final_qa_suite.py --package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy --feedback-timestamps opening_title=0,reported_vertical_clip=7:04
```

Result: `passed`

Suite summary: `17/17` stages passed, `0` blockers.

Final suite stages:

```text
render_delivery_verification: passed
visual_audio_style_audit: passed
bgm_audio_contract_audit: passed
location_truth_contract_audit: passed_with_caveats
client_delivery_rules_audit: passed
longform_delivery_audit: passed_with_caveats
story_style_contract_audit: passed
reference_style_alignment_audit: passed
director_intent_contract_audit: passed
route_texture_contract_audit: passed
title_bridge_contract_audit: passed
stock_aerial_closure_audit: passed
director_polish_contract_audit: passed
feedback_regression_audit: passed
package_integrity_audit: passed
package_integrity_audit_strict_portable: passed
skill_maturity_contract_audit: passed
```

The suite keeps both package integrity reports coherent: strict portable mode is saved to `package_integrity_audit_strict_portable.json`, then the default `package_integrity_audit.json` is restored as a non-strict report.

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/final_qa_suite_report.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260627_2130_davinci_v13_skill_title_subtitle_policy/final_qa_suite_report.md
```

## Cross-Trip Forward-Test Gate

New Skill lesson: one successful Japan package is not enough evidence that the Skill will behave correctly on a messy mounted drive. After the v14 DaVinci repair, the Skill was forward-tested against three distinct external-media states: a known-good Japan package, a matched Hong Kong/Macau project that must stay blocked before cutting, and an unknown mounted `ac4 20250729 backup` root that must be identified instead of silently selected.

Command:

```bash
python3 /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/scripts/audit_skill_forward_test_contract.py \
  --skill-dir /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio \
  --intake-json /Users/pengyang/Pictures/Video-make/video-claw-studio/external_media_intake/20260626_162844/external_media_intake.json \
  --ready-package-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair \
  --blocked-project-dir /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d \
  --blocked-location-truth-json /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/forward_test_location_truth/location_truth_contract_audit.json \
  --blocked-recovery-plan-json /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/forward_test_recovery_plan/blocked_project_recovery_plan.json \
  --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_20260628
```

Result: `passed`

Forward-test summary:

```text
passed: 8
blocked: 0
warnings: 0
total: 8
```

Key evidence:

```text
external intake distinguishes Japan, Hong Kong/Macau, and unknown roots
Japan v14 known-good package passes final QA 17/17 and current orientation gate
Hong Kong/Macau project remains blocked before cutting because cloud recognition was dry-run, no confirmed route exists, and route review needs decisions
Hong Kong/Macau location-truth audit forbids route-ready and exact per-video claims
blocked project recovery plan gives a phase-by-phase route to Mimo/Codex visual review, route confirmation, truth gates, and only then package building
```

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_20260628/skill_forward_test_contract_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/forward_test_20260628/skill_forward_test_contract_audit.md
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/forward_test_location_truth/location_truth_contract_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/forward_test_recovery_plan/blocked_project_recovery_plan.json
```

## Hong Kong/Macau Codex Visual Route Candidate

New Skill lesson: a blocked matched project should not remain a dead end. After forward-test proved the Hong Kong/Macau project was correctly blocked before cutting, Codex visual inspection was used to create full-folder route evidence without cloud calls, Resolve writes, or source-drive modification.

Generated full-folder visual survey:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/codex_visual_review/20260628_hkmacao_visual_survey/visual_survey_manifest.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/codex_visual_review/20260628_hkmacao_visual_survey/contact_sheet_all_videos_best_frame.jpg
```

Coverage:

```text
35 source videos
140 sampled frames
6 filming dates
9 visual route chapters
```

Route candidate:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/codex_visual_review/20260628_hkmacao_visual_survey/codex_visual_review.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/codex_visual_review/20260628_hkmacao_visual_survey/confirmed_route_candidate/codex_visual_confirmed_route_candidate.json
```

Result: `ready_to_apply`

The candidate is not applied to `confirmed_route_timeline.json`; applying route decisions remains approval-gated. This preserves the blocked-project safety contract while giving the next agent a concrete route-ready candidate to review.

Script fix generalized from this project:

```text
prepare_codex_visual_confirmed_route.py no longer hard-codes country="Japan".
It supports explicit per-chapter videoNames/videoIds/videoPaths, so same-date multi-stop travel days do not duplicate every same-day video into every chapter.
prepare_blocked_project_recovery_plan.py now surfaces a ready confirmed-route candidate in summary/artifacts/nextAction while keeping editingAllowedNow=false until the route is explicitly applied and truth gates pass.
```

Hong Kong/Macau chapter evidence:

```text
Arrival Rail / West Kowloon Transfer
Harbourfront / Tsim Sha Tsui Texture
Hong Kong Street / Tram Corridor
Hong Kong Island Coast / Swimming Shed
Repulse Bay / Beach Pause
Victoria Peak / Night Skyline
Central Tram / Harbour Wheel
Hong Kong-Zhuhai-Macao Bridge Transit
Macau / The Parisian
```

## Confirmed Route Candidate Audit Gate

New Skill lesson: a ready-looking route candidate is still not safe to apply until a deterministic gate proves it matches the selected project and active source media. The previous recovery plan could surface a ready candidate, but it did not force an independent pre-apply audit.

Added reusable script:

```text
scripts/audit_confirmed_route_candidate.py
```

The gate checks:

```text
candidate exists and is apply-ready
candidate projectDir matches the selected project
media_index.json active source videos are assigned exactly once
no unknown, excluded, or duplicated source references appear in chapters
same-date multi-stop chapters have explicit source mapping rather than date-only duplication
chapter metadata includes route labels, confidence/review decision, and visual evidence
country/region labels do not inherit the wrong trip, such as Japan on a Hong Kong/Macau project
non-GPS visual reconstruction caveats remain explicit
```

Hong Kong/Macau audit result:

```text
status: passed_with_caveats
activeSourceVideoCount: 35
assignedSourceVideoCount: 35
missingSourceVideoCount: 0
duplicateSourceVideoCount: 0
unknownReferenceCount: 0
expectedRegion: hong_kong_macau
countries: Hong Kong/Macau
exactPerVideoLocationClaimAllowed: false
```

Evidence:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/codex_visual_review/20260628_hkmacao_visual_survey/confirmed_route_candidate/confirmed_route_candidate_audit.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/姥爷港澳行-ac4-外置盘素材库预检-c0cb5d/codex_visual_review/20260628_hkmacao_visual_survey/confirmed_route_candidate/confirmed_route_candidate_audit.md
```

Negative fixture:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/confirmed_route_candidate_negative_fixture/bad_country_candidate.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/confirmed_route_candidate_negative_fixture/confirmed_route_candidate_audit.json
```

The negative fixture intentionally relabels every Hong Kong/Macau chapter as `Japan`. The new audit blocks it with:

```text
Candidate country labels conflict with project region hong_kong_macau: ['Japan']
```

Skill integration:

```text
SKILL.md now requires audit_confirmed_route_candidate.py after prepare_codex_visual_confirmed_route.py or prepare_confirmed_route_candidate.py and before any route --apply.
prepare_blocked_project_recovery_plan.py now places audit_confirmed_route_candidate.py before the approval-gated apply command.
audit_skill_forward_test_contract.py now requires the blocked-project recovery plan to include audit_confirmed_route_candidate.py.
audit_skill_maturity_contract.py now requires the script and the SKILL.md rule.
```

Validation:

```text
quick_validate: passed
py_compile changed scripts: passed
Hong Kong/Macau candidate audit: passed_with_caveats
bad-country negative fixture: blocked as expected
blocked recovery plan regenerated with candidate audit command
forward-test contract: passed 8/8
skill maturity contract: passed 16/16
```

## Trip Generalization Contract

New Skill lesson: rescue scripts created for one rendered Japan/Tokyo/Osaka package must not become hidden defaults for every future trip. A script that fixes `TOKYO` title clutter or Japan portrait footage can only be reusable when it derives the title, country, BGM mood, and Resolve names from the selected project/package or explicit arguments.

Generalized scripts:

```text
make_davinci_stylefix_blueprint.py
prepare_orientation_repair_package.py
prepare_quality_recut.py
prepare_route_decision_sheet.py
apply_route_decision_sheet.py
build_delivery_package.py
prepare_confirmed_route_candidate.py
prepare_codex_visual_confirmed_route.py
```

Key fixes:

```text
make_davinci_stylefix_blueprint.py no longer forces cityTitle/titleText="TOKYO"; it infers title, project name, timeline name, opening place, and BGM mood or accepts explicit arguments.
prepare_orientation_repair_package.py no longer defaults Resolve project/timeline names to 日本东京大阪行; it derives them from the source blueprint/package.
prepare_quality_recut.py no longer defaults city/ending titles to TOKYO/JAPAN or writes Tokyo-to-Osaka narration; it infers titles/subtitles from the source package.
build_delivery_package.py no longer uses Tokyo as the generic fallback chapter for asset/BGM queries.
prepare_route_decision_sheet.py no longer fills missing country with Japan; it infers from sample/chapter/review context, including 港澳, or leaves it for review.
apply_route_decision_sheet.py now accepts generic accept_inferred_media_route while preserving legacy accept_inferred_japan_route compatibility.
```

Added reusable audit:

```text
scripts/audit_trip_generalization_contract.py
```

Audit result:

```text
status: passed
passed: 13
blocked: 0
warnings: 0
```

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/trip_generalization_20260628/trip_generalization_contract_audit.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/trip_generalization_20260628/trip_generalization_contract_audit.md
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/stylefix_generalization_japan/v10_davinci_stylefix_blueprint_report.json
```

Sanity checks:

```text
Japan project-name inference still yields openingHook.cityTitle=TOKYO.
Hong Kong/Macau project-name inference yields HONG KONG / Hong Kong-Macau instead of falling back to Japan.
trip generalization audit is now referenced in SKILL.md and required by audit_skill_maturity_contract.py.
quick_validate: passed
forward-test contract: passed 8/8
skill maturity contract: passed 16/16
```

Music/source reference update:

```text
references/music-stock-fonts.md now records that even private/nonprofit drafts should use traceable license-friendly BGM/stock sources. Mixkit remains first-pass for free traceable BGM; Pixabay Music requires exact track URL and certificate/license evidence because automated Content ID claims can still occur.
```

## Malta Reference Style Profile Gate

New Skill lesson: "剪成马尔他终稿那种效果" cannot be represented by a vague style note or a single unlabeled contact sheet. The Skill now requires a reusable reference profile with pacing, audio, sampled-frame evidence, and a non-copying usage contract before claiming Bilibili/Malta-style alignment.

Upgraded script:

```text
scripts/analyze_reference_video.py
```

The script now records:

```text
duration / frame rate / bitrate
scene-cut pacing profile
average and median shot length
audio loudness and detected long silence
24 timecoded frame samples by default
labeled contact sheet
non-copying usage contract
style target hints for route texture, BGM/no-voiceover support, subtitles, and breathing room
```

Current Malta profile evidence:

```text
referenceDurationMinutes: 39.91
frameRate: 29.97
sceneCutCount: 405
estimatedShotCount: 406
averageShotLengthSeconds: 5.897
medianShotLengthSeconds: 3.103
longShotCountOver20s: 19
shortShotCountUnder3s: 190
meanVolumeDb: -22.8
detectedLongSilenceSeconds: 0
sampleFrameCount: 24
```

Evidence:

```text
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference/reference_analysis.json
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference/reference_analysis.md
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference/reference_contact_sheet.jpg
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/malta_reference/reference_frame_samples/
```

Gate integration:

```text
audit_reference_style_alignment.py now requires a real Malta reference profile, not only an old markdown report.
audit_skill_maturity_contract.py now requires analyze_reference_video.py and verifies the reference profile has pacingProfile, audioProfile, at least 12 sampled frames, and a contact sheet.
SKILL.md now tells future agents to rerun analyze_reference_video.py when the Malta reference profile is stale or shallow.
```

Validation:

```text
py_compile: passed
quick_validate: passed
analyze_reference_video.py on /Users/pengyang/Downloads/马耳他终稿5.16.mp4: passed
audit_reference_style_alignment.py on Japan v14 package: passed 100%
audit_skill_maturity_contract.py on Japan v14 package: passed 17/17
```

## Proactive BGM Sourcing Brief

New Skill lesson: the repeated "no BGM / scenic section has source voice" complaint should not depend on memory or a final audio audit alone. The Skill now generates a proactive BGM sourcing brief before asset decisions, so future agents get concrete search rows and selection evidence fields instead of a vague reminder to "find music online."

Added script:

```text
scripts/prepare_bgm_sourcing_brief.py
```

The script writes:

```text
bgm_sourcing/bgm_sourcing_brief.json
bgm_sourcing/bgm_sourcing_brief.md
```

It records:

```text
verified BGM rows already present in the package
continuous-bed / opening-title / transition / ending section plan
chapter mood buckets such as opening, city, transport, temple, ending
Mixkit/Pixabay-first search URLs plus Artlist/Epidemic/Motion Array fallbacks
license URLs and Content ID caution fields
exact selected-asset decision fields
pass/reject rubric for long-form travel BGM
```

Evidence on the Japan v14 package:

```text
status: ready_with_verified_bgm
verifiedBgmCount: 1
chapterRows: 6
sectionPlanCount: 4
targetDurationSeconds: 1200.171
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/bgm_sourcing/bgm_sourcing_brief.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/bgm_sourcing/bgm_sourcing_brief.md
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_bgm_sourcing_brief.py after prepare_asset_sourcing_packet.py.
SKILL.md now requires a BGM sourcing brief before asset decisions.
references/music-stock-fonts.md now documents the BGM brief command and evidence requirements.
audit_skill_maturity_contract.py now requires prepare_bgm_sourcing_brief.py and verifies the package has a usable BGM brief.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_bgm_sourcing_brief.py on Japan v14 package: ready_with_verified_bgm
audit_skill_maturity_contract.py on Japan v14 package: passed 18/18
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Proactive BGM Selection Package

New Skill lesson: a BGM sourcing brief is still too early to close the user's "no BGM" complaint. The Skill now creates a BGM selection package that proves selected music is local, license-traceable, long enough, referenced by the active Resolve blueprint, and rebuildable before audio policy or Resolve writes.

Added script:

```text
scripts/prepare_bgm_selection_package.py
```

The script writes:

```text
bgm_selection_package/bgm_selection_package.json
bgm_selection_package/bgm_selection_package.md
bgm_selection_package/track_manifest_for_build_bed.json
```

It records:

```text
materialized BGM bed candidates from bgm/v9_bgm_manifest.json
source component tracks with local paths, license URLs, duration probes, and decision fields
asset-ledger BGM evidence
active Resolve blueprint BGM asset and A3 cue evidence
target duration coverage
build_bgm_bed.py command for rebuilding the bed from approved local source tracks
next audit command for audit_bgm_audio_contract.py
safety flags proving no download, Resolve write, render queue, or source-footage mutation
```

Evidence on the Japan v14 package:

```text
status: ready_with_materialized_bgm_selection_package
candidateCount: 4
materializedBedCount: 1
verifiedMaterializedBedCount: 1
readySourceTrackCount: 3
blueprintBgmAssetCount: 1
bgmCueCount: 1
sectionPlanCount: 4
chapterBgmRowCount: 6
buildCommandAvailable: true
selected bed: v9_mixkit_serene_travel_bed_20min
selected bed localPathExists: true
selected bed licenseUrlPresent: true
selected bed coversTargetDuration: true
selected bed referencedByBlueprint: true
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/bgm_selection_package/bgm_selection_package.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/bgm_selection_package/bgm_selection_package.md
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/bgm_selection_package/track_manifest_for_build_bed.json
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_bgm_selection_package.py after prepare_bgm_sourcing_brief.py.
SKILL.md now requires a BGM selection package before trusting BGM/no-voiceover claims.
references/music-stock-fonts.md now documents the BGM selection package and build command requirements.
audit_skill_maturity_contract.py now requires prepare_bgm_selection_package.py and verifies selected BGM bed locality, license traceability, target-duration coverage, blueprint reference, build command, and BGM/audio audit handoff before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate on staging upgrade skill root: passed
prepare_bgm_selection_package.py on Japan v14 package: ready_with_materialized_bgm_selection_package
audit_skill_maturity_contract.py on Japan v14 package: passed 29/29
audit_skill_forward_test_contract.py from staging skill root: passed 8/8
audit_trip_generalization_contract.py from staging skill root: passed 13/13
```

## Proactive Effect Motion Plan

New Skill lesson: the user's "不能裸拼、要有合适过渡、不要太 AI 模板感" feedback should not wait for final director-polish QA. The Skill now generates a proactive effect/motion plan before Resolve effect decisions, so future agents get exact restrained rows for opening/chapter/ending title reveals and day/place transition motion.

Added script:

```text
scripts/prepare_effect_motion_plan.py
```

The script writes:

```text
effect_motion_plan/effect_motion_plan.json
effect_motion_plan/effect_motion_plan.md
```

It records:

```text
opening title reveal row
chapter title reveal rows
ending title reveal row
day/place transition motion rows
title typography source evidence
transition bridge source evidence
visual establishing source evidence
blueprint effectPlan evidence
subtle fade/dissolve/match-cut/route-marker recommendations
title-zone checks
BGM-only/no-camera-voice policy
exact Resolve implementation/readback decision fields
pass/reject rubric that rejects glitch, spin, flash, shake, particle, logo-reveal, or template-pack effects
```

Evidence on the Japan v14 package:

```text
status: ready_with_restrained_effect_plan
effectPlanCount: 2
effectRowCount: 13
rowsWithSourceEvidence: 13
rowsWithDecisionFields: 13
forbiddenEffectHitCount: 0
titleMotionRowCount: 8
transitionMotionRowCount: 5
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/effect_motion_plan/effect_motion_plan.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/effect_motion_plan/effect_motion_plan.md
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_effect_motion_plan.py after prepare_visual_establishing_plan.py and before asset decision reconciliation.
SKILL.md now requires the effect motion plan before adding or trusting Resolve title, route, or transition effects.
references/music-stock-fonts.md now documents restrained effect/motion planning and rejects template-heavy transition packs.
audit_skill_maturity_contract.py now requires prepare_effect_motion_plan.py and verifies restrained effect rows, source evidence, decision fields, title/transition row counts, BGM-only policy, no black-card fallback, no template-heavy transitions, and zero forbidden effect hits before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_effect_motion_plan.py on Japan v14 package: ready_with_restrained_effect_plan
audit_skill_maturity_contract.py on Japan v14 package: passed 23/23
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Proactive Feedback Regression Plan

New Skill lesson: the user's concrete rejection set should not live only in chat memory or in a post-render audit command. The Skill now writes a pre-render feedback regression plan so opening title ghosting, 7:04 portrait footage, 7:04 BGM/source-voice leakage, and opening BGM/no-voiceover remain package-level probes before Resolve apply, after render, and inside final QA.

Added script:

```text
scripts/prepare_feedback_regression_plan.py
```

The script writes:

```text
feedback_regression_plan/feedback_regression_plan.json
feedback_regression_plan/feedback_regression_plan.md
```

It records:

```text
one probe for opening clean-title regression at 0s
one probe for reported 7:04 portrait/pillarbox regression
one probe for reported 7:04 BGM/source-voice leakage
one probe for opening scenic BGM/no-voiceover leakage
the exact feedback timestamp CSV for audit_feedback_regressions.py and run_final_qa_suite.py
the exact audio-policy timestamp CSV for prepare_audio_scene_policy_plan.py
pre-render and post-render evidence requirements for each probe
safety flags proving no Resolve write, render queue, external download, or source-footage mutation
```

Evidence on the Japan v14 package:

```text
status: ready_with_feedback_regression_plan
probeCount: 4
openingProbeCount: 2
sevenMinuteProbeCount: 2
audioPolicyProbeCount: 3
finalFeedbackAuditProbeCount: 4
feedbackTimestampsCsv: opening_title=0,reported_vertical_clip=7:04,reported_voice_at_7_04=7:04,opening_bgm_no_voice=0
audioPolicyFeedbackTimestampsCsv: opening_title=0,reported_voice_at_7_04=7:04,opening_bgm_no_voice=0
```

Audio policy integration on the Japan v14 package:

```text
prepare_audio_scene_policy_plan.py status: ready_with_bgm_only_scene_policy
sceneWindowCount: 39
bgmCoveredWindowCount: 39
sourceAudioRiskCount: 0
feedbackWindowCount: 10
knownFeedbackProbeCount: 3
feedbackRegressionPlan input: feedback_regression_plan/feedback_regression_plan.json
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_feedback_regression_plan.py after prepare_effect_motion_plan.py and before prepare_audio_scene_policy_plan.py.
prepare_audio_scene_policy_plan.py now consumes feedback_regression_plan.json in addition to existing feedback audit rows and CLI feedback timestamps.
SKILL.md now requires the feedback regression plan before audio scene policy and final QA.
references/bilibili-travel-style.md and references/long-form-travel-style.md now document this pre-render feedback-probe workflow.
audit_skill_maturity_contract.py now requires prepare_feedback_regression_plan.py and verifies the opening, 7:04 portrait, 7:04 BGM/voice, opening BGM/no-voiceover probes, generated commands, and safety flags before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate on installed skill: passed
quick_validate on staging upgrade skill root: passed
prepare_feedback_regression_plan.py on Japan v14 package: ready_with_feedback_regression_plan
prepare_audio_scene_policy_plan.py consumed feedback_regression_plan.json and stayed ready_with_bgm_only_scene_policy
audit_skill_maturity_contract.py on Japan v14 package: passed 28/28
audit_skill_forward_test_contract.py from staging skill root: passed 8/8
audit_trip_generalization_contract.py from staging skill root: passed 13/13
```

## Proactive Audio Scene Policy Plan

New Skill lesson: the user's "片头/风景/转场不要配我的声音，必须有 BGM" feedback should be prevented before Resolve writes, not merely detected after render. The Skill now generates a proactive audio scene policy plan that enumerates opening/title/visual-establishing/transition/effect/feedback windows and requires A3 BGM with no A1/A2 source-camera or voiceover leakage.

Added script:

```text
scripts/prepare_audio_scene_policy_plan.py
```

The script writes:

```text
audio_scene_policy_plan/audio_scene_policy_plan.json
audio_scene_policy_plan/audio_scene_policy_plan.md
```

It records:

```text
opening/chapter/ending title audio windows
visual-establishing audio windows
day/place transition audio windows
effect-motion audio windows
feedback timestamp probes, including the known 7:04 scenic/voice complaint when applicable
ready A3 BGM cue coverage evidence
source-audio/voiceover disabled policy evidence
overlapping clip evidence and source-audio risk reasons
post-render BGM/audio audit evidence when available
exact mute, BGM track, target dB, ambient-exception, Resolve implementation, and readback decision fields
pass/reject rubric that blocks accidental user/camera voice in scenic/title/transition moments
```

Evidence on the Japan v14 package:

```text
status: ready_with_bgm_only_scene_policy
sceneWindowCount: 38
bgmCoveredWindowCount: 38
rowsWithDecisionFields: 38
sourceAudioRiskCount: 0
readyBgmCueCount: 1
voiceoverDisabled: true
sourceAudioDisabled: true
feedbackWindowCount: 9
knownFeedbackProbeCount: 1
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/audio_scene_policy_plan/audio_scene_policy_plan.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/audio_scene_policy_plan/audio_scene_policy_plan.md
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_audio_scene_policy_plan.py after prepare_effect_motion_plan.py and before asset decision reconciliation.
SKILL.md now requires the audio scene policy plan before asset decisions or Resolve writes when BGM/no-voiceover complaints exist.
references/music-stock-fonts.md and references/narration-subtitles.md now document that selecting music is not enough; exact scene-window mix policy is required.
audit_skill_maturity_contract.py now requires prepare_audio_scene_policy_plan.py and verifies scene windows, A3 BGM coverage, decision fields, zero source-audio risks, disabled voiceover/source policy, feedback probes, and no Resolve/write/download side effects before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_audio_scene_policy_plan.py on Japan v14 package: ready_with_bgm_only_scene_policy
audit_skill_maturity_contract.py on Japan v14 package: passed 24/24
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Proactive Edit Rhythm Plan

New Skill lesson: the user's "剪得差、太像 AI 拼接、要像马耳他终稿/哔哩哔哩旅行片" feedback should be turned into pre-Resolve shot-purpose and pacing decisions, not only post-render style scores. The Skill now generates a proactive edit rhythm plan that compares the current blueprint against the Malta reference pacing profile and lists exactly which shots need trim, split, cutaway, or chapter-variety work.

Added script:

```text
scripts/prepare_edit_rhythm_plan.py
```

The script writes:

```text
edit_rhythm_plan/edit_rhythm_plan.json
edit_rhythm_plan/edit_rhythm_plan.md
```

It records:

```text
one row per primary visual shot
one row per chapter rhythm block
Malta/reference average, median, and long-shot pacing targets
rhythm roles such as opening hook, transport, route transition, lived-in detail, title bridge, and ending aftertaste
long raw-hold and missing-cutaway risk rows
recommended trim/split/cutaway treatment for risky shots
chapter variety coverage and recommended chapter beat pattern
exact Resolve implementation, readback, and approval decision fields
pass/reject rubric that blocks bare concatenation, landmark-only montages, and style claims without pre-Resolve rhythm decisions
```

Evidence on the Japan v14 package:

```text
status: ready_with_edit_rhythm_plan
primaryVisualShotCount: 63
recommendedMinimumShotCount: 114
estimatedAdditionalCutawayBeats: 51
averageShotSeconds: 19.683
medianShotSeconds: 28.0
rhythmRiskCount: 41
rowsWithDecisionFields: 63
chapterRowCount: 8
chaptersNeedingVarietyOrRetime: 8
referenceReady: true
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/edit_rhythm_plan/edit_rhythm_plan.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/edit_rhythm_plan/edit_rhythm_plan.md
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_edit_rhythm_plan.py after prepare_audio_scene_policy_plan.py and before asset decision reconciliation.
SKILL.md now requires the edit rhythm plan before asset decisions or Resolve writes when Malta/Bilibili-style quality, flat pacing, or AI-assembly complaints exist.
references/bilibili-travel-style.md and references/long-form-travel-style.md now document the pre-Resolve rhythm workflow.
audit_skill_maturity_contract.py now requires prepare_edit_rhythm_plan.py and verifies shot rows, chapter rows, reference pacing evidence, decision fields, rhythm-role coverage, risk guidance, no Resolve/write/download side effects, and pass/reject rubric before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_edit_rhythm_plan.py on Japan v14 package: ready_with_edit_rhythm_plan
audit_skill_maturity_contract.py on Japan v14 package: passed 25/25
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Proactive Rhythm Recut Blueprint

New Skill lesson: the user's "不要只诊断剪得像 AI，要自动改出能交给达芬奇的蓝图" feedback should not stop at edit-rhythm rows. The Skill now converts long-shot/pacing diagnosis into a separate, non-destructive Resolve blueprint candidate before asset decisions or Resolve writes.

Added script:

```text
scripts/prepare_rhythm_recut_blueprint.py
```

The script writes:

```text
rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json
rhythm_recut_blueprint/rhythm_recut_blueprint_report.json
rhythm_recut_blueprint/rhythm_recut_blueprint_report.md
```

It records:

```text
one row per recut long source clip
existing-footage cutaway selections and source ranges
main-segment/cutaway rhythmRecut metadata on revised clips
before/after average shot length, median shot length, long-shot risk, and total duration delta
candidate blueprint path that does not replace the active blueprint by default
exact approval, Resolve implementation, readback, and editor-note decision fields
pass/reject rubric requiring duration stability, existing local footage, BGM-only inserted clips, and Resolve preflight before apply
```

Evidence on the Japan v14 package:

```text
status: ready_with_rhythm_recut_blueprint
originalClipCount: 155
revisedClipCount: 319
originalPrimaryClipCount: 55
revisedPrimaryClipCount: 219
longEditableClipCount: 48
splitSourceClipCount: 48
cutawayInsertCount: 82
cutawayPoolCount: 52
averagePrimaryShotBeforeSeconds: 19.683
averagePrimaryShotAfterSeconds: 5.463
medianPrimaryShotBeforeSeconds: 28.0
medianPrimaryShotAfterSeconds: 6.25
longShotRiskBefore: 48
longShotRiskAfter: 0
timelineDurationBeforeSeconds: 1200.0
timelineDurationAfterSeconds: 1200.0
durationDeltaSeconds: 0.0
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/rhythm_recut_blueprint/rhythm_recut_blueprint_report.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/rhythm_recut_blueprint/rhythm_recut_blueprint_report.md
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/rhythm_recut_blueprint/candidate_resolve_blueprint_preflight.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/rhythm_recut_blueprint/candidate_resolve_blueprint_preflight.md
```

Candidate preflight:

```text
audit_resolve_blueprint.py --blueprint <candidate> --package-dir <package>: ready_with_warnings
blockers: 0
missingSourceCount: 0
invalidRangeCount: 0
outOfBoundsCount: 0
overlapCount: 0
v1GapCount: 0
sourceAudioClipCount: 0
expected warnings: BGM-only/no-voiceover source-audio policy
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_rhythm_recut_blueprint.py after prepare_edit_rhythm_plan.py and before asset decision reconciliation.
SKILL.md now requires the rhythm recut candidate blueprint after edit rhythm planning and before any active blueprint replacement.
references/bilibili-travel-style.md and references/long-form-travel-style.md now document the candidate-blueprint workflow and preflight requirement.
audit_skill_maturity_contract.py now requires prepare_rhythm_recut_blueprint.py and verifies candidate blueprint existence, split/cutaway counts, duration stability, before/after rhythm improvement, safety flags, decision fields, and pass/reject rubric before maturity can pass.
```

Validation:

```text
py_compile: passed
prepare_rhythm_recut_blueprint.py on Japan v14 package: ready_with_rhythm_recut_blueprint
candidate audit_resolve_blueprint.py preflight: ready_with_warnings, no blockers
audit_skill_maturity_contract.py on Japan v14 package: passed 26/26
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Rhythm Recut Apply Package

New Skill lesson: a good recut candidate is still not enough. The Skill must not silently overwrite the active delivery package or push a pacing experiment straight into Resolve. It now creates a separate Resolve-ready package fork where the approved rhythm recut candidate becomes the active blueprint, then runs the normal preflight, delivery audit, and Resolve apply-contract gates.

Added script:

```text
scripts/prepare_rhythm_recut_apply_package.py
```

The script writes:

```text
<new-package>/resolve_timeline_blueprint.json
<new-package>/resolve_timeline_blueprint_rhythm_recut_applied.json
<new-package>/rhythm_recut_apply_package_report.json
<new-package>/rhythm_recut_apply_package_report.md
<new-package>/resolve_blueprint_preflight.json
<source-package>/rhythm_recut_blueprint/rhythm_recut_apply_package_report.json
<source-package>/rhythm_recut_blueprint/rhythm_recut_apply_package_report.md
```

It records:

```text
source candidate status and before/after rhythm metrics
new package path and active recut blueprint path
copied reusable input/assets/plans only, without copying final render proof
path rewrites from source package to new package across copied JSON/text manifests
standard resolve_blueprint_preflight.json output for downstream apply contracts
safety flags proving no Resolve write, render queue, external download, source-footage mutation, or source-package blueprint replacement
manual approval, Resolve apply, readback, and render next actions
```

Evidence on the Japan v14 package:

```text
sourcePackage: /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair
outputPackage: /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0605_rhythm_recut_apply
status: ready_for_resolve_apply_contract
activeClipCount: 319
copiedFinalRenderEvidence: false
preflightStatus: ready_with_warnings
preflightBlockerCount: 0
preflightWarningCount: 2
```

Resolve dry-run evidence on the apply package:

```text
projectName: 日本东京大阪行 Resolve Longform v14 Orientation Repair Rhythm Recut
timelineName: 日本东京大阪行 20min Master v14 Orientation Repair Rhythm Recut
clipCount: 319
sourceFileCount: 143
audioAssetCount: 1
missingSourceFiles: []
sourceAudioClipCount: 0
subtitleCueCount: 58
timelineMarkerCount: 50
bgmCueCount: 1
stockPlaceholderCount: 22
coverageRatio: 1.0
actualVideoCoverageSeconds: 1200.0
```

Downstream gates:

```text
audit_delivery_package.py on recut apply package: ready_for_resolve_write, blockers 0
prepare_resolve_apply_contract.py on recut apply package: awaiting_user_approval, blockers 0
expected warnings: BGM-only/no-source-audio policy, disabled voiceover, route decision sheet not approved yet
quick_validate.py on installed skill: passed
quick_validate.py on staging upgrade skill root: passed
audit_skill_maturity_contract.py on Japan v14 package: passed 27/27
audit_skill_forward_test_contract.py from staging skill root: passed 8/8
audit_trip_generalization_contract.py from staging skill root: passed 13/13
```

Gate integration:

```text
run_delivery_workflow.py can now generate the rhythm recut apply package with --prepare-rhythm-recut-apply-package after the candidate blueprint passes review.
SKILL.md now requires a separate apply-package fork before any active blueprint replacement or Resolve write.
references/bilibili-travel-style.md and references/long-form-travel-style.md now document the candidate-to-apply-package workflow.
audit_skill_maturity_contract.py now requires prepare_rhythm_recut_apply_package.py and verifies the apply fork, active recut blueprint, standard preflight, no copied render proof, safety flags, and zero preflight blockers before maturity can pass.
travel-video-studio-skill-upgrade now includes a real SKILL.md plus full scripts/ and references/ sync; install_into_plugin.py copies the complete skill surface instead of only the early style-audit subset.
```

## Proactive Visual Establishing Plan

New Skill lesson: the user's repeated "Tokyo should have Tokyo aerial/landmark footage, opening/ending should not feel generic, do not wait for me to remind you" feedback must be front-loaded before stock decisions and Resolve writes. The Skill now generates a proactive visual establishing plan so future agents get exact opening, chapter, and ending rows for aerials, landmarks, local scenic footage, and fallback stock searches.

Added script:

```text
scripts/prepare_visual_establishing_plan.py
```

The script writes:

```text
visual_establishing_plan/visual_establishing_plan.json
visual_establishing_plan/visual_establishing_plan.md
```

It records:

```text
one row for the opening city/place signal
one row for every chapter establishing moment
one row for the ending scenic aftertaste
local-footage-first search hints
trip-derived famous-place/landmark hints, without forcing previous-trip defaults
licensed Mixkit/Pixabay/Pexels/Artgrid/Storyblocks fallback searches
title typography evidence for each row
existing Resolve blueprint timeline evidence for scenic/aerial/title bridge coverage
verified aerial/stock ledger evidence
BGM-only/no-camera-voice policy
exact local clip / stock asset / license / approval decision fields
pass/reject rubric for missing aerials, generic openings, black slates, and fabricated stock/license claims
```

Evidence on the Japan v14 package:

```text
status: ready_with_establishing_evidence
chapterCount: 6
establishingRowCount: 8
rowsWithEvidence: 8
missingEstablishingCount: 0
rowsWithTitleTypographyEvidence: 8
verifiedAerialCount: 1
stockAerialClosureStatus: passed
stockAerialUnresolvedPlaceholderCount: 0
titleTypographyStatus: ready_with_clean_title_typography_plan
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/visual_establishing_plan/visual_establishing_plan.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/visual_establishing_plan/visual_establishing_plan.md
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_visual_establishing_plan.py after prepare_title_typography_plan.py and before asset decision reconciliation.
SKILL.md now requires the visual establishing plan before trusting aerial, landmark, or city-establishing coverage.
references/music-stock-fonts.md now documents the proactive visual establishing workflow: local footage first, trip-derived landmark hints, stock/aerial only as licensed fallback, exact selected asset URL/license/local path required.
audit_skill_maturity_contract.py now requires prepare_visual_establishing_plan.py and verifies opening/chapter/ending rows, search hints, decision fields, title evidence, timeline evidence, verified aerial count, stock/aerial closure, local-footage-first policy, BGM-only audio policy, and no previous-trip defaults before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_visual_establishing_plan.py on Japan v14 package: ready_with_establishing_evidence
audit_skill_maturity_contract.py on Japan v14 package: passed 22/22
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Proactive Title Typography Plan

New Skill lesson: the repeated "opening title is ghosted / duplicate / has another text behind it / needs a more intentional font" complaint should not wait for a final OCR or title-bridge audit. The Skill now generates a proactive title typography plan before title bridge media is trusted, so future agents get exact title rows, font evidence, safe-zone rules, and no-stacked-text evidence before final render.

Added script:

```text
scripts/prepare_title_typography_plan.py
```

The script writes:

```text
title_typography_plan/title_typography_plan.json
title_typography_plan/title_typography_plan.md
```

It records:

```text
one row per opening/chapter/ending title window
approved title/subtitle decision fields
opening single-clean-title policy
forbidden route/date/project-slug text
scenic/video background and segment evidence
verified system-font-render-only or licensed font evidence
subtitle title-zone suppression policy
title contract stack evidence proving zero extra text layers and zero subtitle overlays
pass/reject rubric for ghosted, stacked, generic, or black-slate titles
```

Evidence on the Japan v14 package:

```text
status: ready_with_clean_title_typography_plan
titleRowCount: 8
cleanRowCount: 8
openingRowCount: 1
chapterRowCount: 6
endingRowCount: 1
fontVerified: true
titleZoneMode: avoid_title_zones
titleZoneCount: 8
titleContractStatus: passed
stackExtraTextLayerCount: 0
stackSubtitleOverlayCount: 0
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/title_typography_plan/title_typography_plan.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/title_typography_plan/title_typography_plan.md
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_title_typography_plan.py after caption_story_plan.
SKILL.md now requires the title typography plan before generating, trusting, or handing off title bridge media.
references/music-stock-fonts.md now documents title typography planning, font evidence, hero title cleanliness, and title-zone suppression.
audit_skill_maturity_contract.py now requires prepare_title_typography_plan.py and verifies clean title rows, one opening title, font evidence, scenic/video segment evidence, title-zone policy, and zero stacked/ghosted text before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_title_typography_plan.py on Japan v14 package: ready_with_clean_title_typography_plan
audit_skill_maturity_contract.py on Japan v14 package: passed 21/21
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Proactive Caption Story Plan

New Skill lesson: the repeated "subtitles are too sparse / do not generate voiceover / export the text document instead" complaint should not wait for final story or feedback QA. The Skill now generates a proactive caption story plan before subtitle overlay generation, so future agents get measurable SRT density targets and a text-only narration export before any render.

Added script:

```text
scripts/prepare_caption_story_plan.py
```

The script writes:

```text
caption_story_plan/caption_story_plan.json
caption_story_plan/caption_story_plan.md
caption_story_plan/text_only_narration_export.txt
```

It records:

```text
full-film subtitle target cue count and cues-per-minute
per-chapter cue targets and actual cue evidence
longest subtitle gap and gap limits
title-zone suppression policy for opening/chapter/ending title windows
no-voiceover/TXT/SRT handoff policy
caption function rows for route honesty, visual observation, movement, lived-in texture, and ending aftertaste
rewrite/approval decision fields
pass/reject rubric for no-voiceover travel films
```

Evidence on the Japan v14 package:

```text
status: ready_with_dense_caption_plan
subtitleCueCount: 95
targetCueCount: 81
cuesPerMinute: 4.749
chapterRowCount: 6
rowsMeetingTarget: 6
maxGapSeconds: 10.955
titleZoneCount: 16
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/caption_story_plan/caption_story_plan.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/caption_story_plan/caption_story_plan.md
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/caption_story_plan/text_only_narration_export.txt
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_caption_story_plan.py after prepare_transition_bridge_plan.py.
SKILL.md now requires the caption story plan before subtitle overlay generation and maturity claims.
references/narration-subtitles.md now documents no-voiceover TXT/SRT delivery, title-zone suppression, and the 4 cues/minute planning target.
audit_skill_maturity_contract.py now requires prepare_caption_story_plan.py and verifies dense cue counts, per-chapter targets, text-only narration export, no-default-voiceover policy, title-zone suppression, decision fields, and pass/reject rubric before maturity can pass.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_caption_story_plan.py on Japan v14 package: ready_with_dense_caption_plan
audit_skill_maturity_contract.py on Japan v14 package: passed 20/20
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```

## Proactive Transition Bridge Plan

New Skill lesson: the user's repeated "day-to-day transition / street ambience / city texture" feedback should not wait for a final route-texture audit. The Skill now generates a proactive transition bridge plan before asset decisions and Resolve writes, so future agents get exact boundary rows for every day/place/chapter jump instead of relying on memory or vague "add transitions" notes.

Added script:

```text
scripts/prepare_transition_bridge_plan.py
```

The script writes:

```text
transition_bridge_plan/transition_bridge_plan.json
transition_bridge_plan/transition_bridge_plan.md
```

It records:

```text
one row per interchapter day/place boundary
local-footage-first search hints for station, street, skyline, vehicle, signage, food, hotel window, weather, or aerial bridge footage
licensed stock/aerial fallback queries with provider and license URLs
BGM-only/no-camera-voice policy for scenic/title/transition windows
subtitle/title-zone and restrained effect policies
existing Resolve blueprint bridge evidence when already present
exact selected-local-clip / selected-stock-asset / license / approval decision fields
pass/reject rubric that blocks black-card, hard-cut, or AI-looking transitions
```

Evidence on the Japan v14 package:

```text
status: ready_with_bridge_evidence
chapterCount: 6
boundaryRowCount: 5
boundariesWithEvidence: 5
missingBoundaryCount: 0
existingTransitionPlanCount: 6
existingBridgeClipCount: 21
```

Evidence paths:

```text
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/transition_bridge_plan/transition_bridge_plan.json
/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/transition_bridge_plan/transition_bridge_plan.md
```

Gate integration:

```text
run_delivery_workflow.py now runs prepare_transition_bridge_plan.py after prepare_bgm_sourcing_brief.py and before asset decision reconciliation.
SKILL.md now requires the transition bridge plan before asset decisions or Resolve writes.
references/music-stock-fonts.md now documents transition bridge asset sourcing: local footage first, stock/aerial only as licensed fallback, exact selected asset URL/license/local path required.
audit_skill_maturity_contract.py now requires prepare_transition_bridge_plan.py and verifies the package has fresh boundary rows, local/stock search hints, decision fields, BGM-only audio policy, pass/reject rubric, and zero missing bridge boundaries before maturity can pass.
audit_skill_maturity_contract.py also no longer hard-codes TOKYO/OSAKA as the only acceptable clean opening titles; the maturity gate now checks for one nonempty clean title so future trips are not contaminated by Japan-specific defaults.
```

Validation:

```text
py_compile: passed
quick_validate: passed
prepare_transition_bridge_plan.py on Japan v14 package: ready_with_bridge_evidence
audit_skill_maturity_contract.py on Japan v14 package: passed 19/19
audit_skill_forward_test_contract.py: passed 8/8
audit_trip_generalization_contract.py: passed 13/13
```
