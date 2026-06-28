# Installing This Upgrade Into The Personal Plugin

The active plugin cache may require filesystem approval before Codex can write into it. The safe staging copy lives here:

```bash
/Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade
```

## Target Plugin Paths

Copy the files into the installed personal plugin:

```text
/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio/
```

Recommended mapping for this full upgrade:

```text
SKILL.md                               -> SKILL.md
references/                            -> references/
scripts/                               -> scripts/
```

The helper installer performs that full sync and creates a backup of the existing installed `SKILL.md`:

```bash
python3 /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/install_into_plugin.py
```

After installation, validate the installed skill:

```bash
python3 /Users/pengyang/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio
```

## Local Smoke Tests

Run the visual/audio style audit on known-good segments:

```bash
python3 /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_visual_audio_style.py \
  --video /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/v9_fix_inputs/segments/v9_clean_opening_tokyo_title_only.mp4 \
  --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/opening \
  --sample-seconds "0,2,7.5" \
  --visual-manifest /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/v9_fix_inputs/v9_fix_manifest.json \
  --require-clean-title
```

Run it on the 7:04 replacement segment:

```bash
python3 /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_visual_audio_style.py \
  --video /Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260626_2345_codex_route_quality_v7/v9_fix_inputs/segments/v9_replace_vertical_0288_with_landscape_station.mp4 \
  --output-dir /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/qa/replacement_704 \
  --sample-seconds "0,6,14,24"
```

Run it on the final 20-minute render after the render file exists again:

```bash
python3 /Users/pengyang/Documents/videomake/travel-video-studio-skill-upgrade/scripts/audit_visual_audio_style.py \
  --video <final-render.mp4> \
  --output-dir <package>/visual_audio_style_audit \
  --sample-seconds "0,2,8,418.3,424,431.8,444.9,1193" \
  --visual-manifest <package>/v9_fix_inputs/v9_fix_manifest.json \
  --bgm-manifest <package>/bgm/v9_bgm_manifest.json \
  --audio-mode bgm_only \
  --require-clean-title
```
