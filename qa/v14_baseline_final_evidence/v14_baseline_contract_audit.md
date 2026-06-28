# V14 Baseline Contract Audit

Status: `passed`
Package: `/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair`
Skill: `/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio`

## Summary

```json
{
  "passed": 12,
  "blocked": 0,
  "total": 12
}
```

## Checks

### Skill root contains the V14 baseline workflow, scripts, and gates
- Status: `passed`
- Evidence:
```json
{
  "skillDir": "/Users/pengyang/.codex/plugins/cache/personal/travel-video-studio/0.1.0+codex.20260626173111/skills/travel-video-studio",
  "missingSkillPatterns": [],
  "missingScripts": [],
  "scriptCount": 23
}
```

### DaVinci Resolve is the finishing path with readback and final report
- Status: `passed`
- Evidence:
```json
{
  "finalReportStatus": "passed",
  "resolveProject": "日本东京大阪行 Resolve Longform v14 Orientation Repair",
  "resolveTimeline": "日本东京大阪行 20min Master v14 Orientation Repair",
  "resolveTrackSummary": {
    "video": [
      {
        "index": 1,
        "name": "V1 Main travel footage",
        "itemCount": 55
      },
      {
        "index": 2,
        "name": "V2 Titles maps aerial inserts",
        "itemCount": 8
      },
      {
        "index": 3,
        "name": "V3 Burned subtitle overlay",
        "itemCount": 92
      }
    ],
    "audio": [
      {
        "index": 1,
        "name": "A1 Source audio",
        "itemCount": 0
      },
      {
        "index": 2,
        "name": "A2 Voiceover",
        "itemCount": 0
      },
      {
        "index": 3,
        "name": "A3 BGM",
        "itemCount": 1
      },
      {
        "index": 4,
        "name": "A4 Ambience",
        "itemCount": 0
      }
    ],
    "subtitle": [
      {
        "index": 1,
        "name": "S1 Chinese subtitles",
        "itemCount": 0
      }
    ]
  }
}
```

### Opening and chapter titles are clean scenic bridges with no ghost text
- Status: `passed`
- Evidence:
```json
{
  "titleContractStatus": "passed",
  "titlePlanStatus": "ready_with_clean_title_typography_plan",
  "titlePlanSummary": {
    "titleRowCount": 8,
    "cleanRowCount": 8,
    "openingRowCount": 1,
    "chapterRowCount": 6,
    "endingRowCount": 1,
    "fontVerified": true,
    "titleZoneMode": "avoid_title_zones",
    "titleZoneCount": 8,
    "titleContractStatus": "passed",
    "stackExtraTextLayerCount": 0,
    "stackSubtitleOverlayCount": 0
  },
  "titleClipCount": 8,
  "segmentCount": 8
}
```

### Known user complaints are reusable feedback regression probes
- Status: `passed`
- Evidence:
```json
{
  "feedbackPlanStatus": "ready_with_feedback_regression_plan",
  "feedbackAuditStatus": "passed",
  "feedbackTimestampsCsv": "opening_title=0,reported_vertical_clip=7:04,reported_voice_at_7_04=7:04,opening_bgm_no_voice=0",
  "requiredTimestamps": [
    "opening_title=0",
    "reported_vertical_clip=7:04",
    "reported_voice_at_7_04=7:04",
    "opening_bgm_no_voice=0"
  ]
}
```

### BGM-only delivery disables voiceover/source-camera audio and keeps TXT/SRT narration
- Status: `passed`
- Evidence:
```json
{
  "audioScenePolicyStatus": "ready_with_bgm_only_scene_policy",
  "audioSceneSummary": {
    "targetDurationSeconds": 1200.099,
    "sceneWindowCount": 39,
    "bgmCoveredWindowCount": 39,
    "rowsWithDecisionFields": 39,
    "sourceAudioRiskCount": 0,
    "readyBgmCueCount": 1,
    "voiceoverDisabled": true,
    "sourceAudioDisabled": true,
    "policyMode": "bgm_only_no_camera_voice",
    "titleWindowCount": 8,
    "transitionWindowCount": 5,
    "establishingWindowCount": 8,
    "feedbackWindowCount": 10,
    "knownFeedbackProbeCount": 3
  },
  "bgmAudioStatus": "passed",
  "a1Items": 0,
  "a2Items": 0,
  "a3Items": 1,
  "textOnlyNarrationExportExists": true
}
```

### Dense subtitles are rendered through a V3/title-safe overlay policy
- Status: `passed`
- Evidence:
```json
{
  "captionPlanStatus": "ready_with_dense_caption_plan",
  "captionSummary": {
    "durationSeconds": 1200.171,
    "chapterCount": 6,
    "chapterRowCount": 6,
    "rowsMeetingTarget": 6,
    "subtitleCueCount": 95,
    "targetCueCount": 81,
    "cuesPerMinute": 4.749,
    "minCuesPerMinute": 4.0,
    "maxGapSeconds": 10.955,
    "gapCountOver75Seconds": 0,
    "titleZoneCount": 16,
    "titleZoneOverlapCueCount": 18,
    "renderedCueCount": 92,
    "subtitleMode": "resolve_overlay_video",
    "textOnlyNarrationExport": "/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/caption_story_plan/text_only_narration_export.txt"
  },
  "subtitleDeliveryPolicy": {
    "mode": "resolve_overlay_video",
    "status": "prepared",
    "overlayTrack": 3,
    "overlayMode": "segments",
    "overlayClipCount": 92,
    "overlayPath": null,
    "overlayDirectory": "/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/subtitle_overlays_title_safe/segments",
    "cueCount": 95,
    "renderedCueCount": 92,
    "titleZoneSubtitlePolicy": {
      "mode": "avoid_title_zones",
      "zones": [
        {
          "role": "opening_city_aerial_title",
          "start": 0.0,
          "end": 8.25,
          "title": "TOKYO"
        },
        {
          "role": "chapter_title_bridge",
          "start": 59.75,
          "end": 64.25,
          "title": "ARRIVAL"
        },
        {
          "role": "chapter_title_bridge",
          "start": 193.78,
          "end": 198.28,
          "title": "OSAKA"
        },
        {
          "role": "chapter_title_bridge",
          "start": 361.54,
          "end": 366.04,
          "title": "OSAKA -> TOKYO"
        },
        {
          "role": "chapter_title_bridge",
          "start": 664.2,
          "end": 668.7,
          "title": "TOKYO"
        },
        {
          "role": "chapter_title_bridge",
          "start": 770.2,
          "end": 774.7,
          "title": "AKIHABARA"
        },
        {
          "role": "chapter_title_bridge",
          "start": 876.2,
          "end": 880.7,
          "title": "BACK TO OSAKA"
        },
        {
          "role": "ending_city_aerial_title",
          "start": 1191.75,
          "end": 1200.25,
          "title": "JAPAN"
        }
      ],
      "originalCueCount": 95,
      "keptCueCount": 92,
      "droppedCueCount": 3,
      "splitCueCount": 0,
      "minKeptCueDurationSeconds": 0.75
    },
    "nativeSubtitleImportNote": "Resolve 21 Python API can create subtitle tracks, but direct SRT ImportIntoTimeline returned False in local smoke testing; use overlay video or explicitly accept sidecar delivery."
  },
  "v3Items": 92
}
```

### Source orientation is scanned and V14-style repair replaces raw portrait clips
- Status: `passed`
- Evidence:
```json
{
  "orientationRepairStatus": "prepared",
  "orientationFixCount": 1,
  "clientStatus": "passed",
  "clientSummary": {
    "passed": 19,
    "blocked": 0,
    "warnings": 0
  },
  "orientationEvidence": {
    "passed": true,
    "checkedVideoClipCount": 155,
    "uniqueVideoSourceCount": 143,
    "landscapeClipCount": 155,
    "allowedDesignedNonLandscapeCount": 0,
    "blockedNonLandscapeCount": 0,
    "visualNormalizationPolicy": {
      "status": "applied_v10",
      "targetCanvas": "3840x2160 landscape",
      "rules": [
        "all raw portrait/square/unknown source clips are ffprobe-scanned and replaced or blocked before Resolve import",
        "no raw portrait clips are allowed unless declared as a designed insert",
        "all final feedback timestamps must pass audit_visual_audio_style.py"
      ],
      "orientationFixes": [
        {
          "clipIndex": 24,
          "sourcePath": "/Volumes/My Passport/2025日本东京大阪行ac4/DJI_20250725093642_0289_D.MP4",
          "role": "main_footage",
          "timelineStartSeconds": 445.79,
          "timelineEndSeconds": 473.79,
          "durationSeconds": 28.0,
          "geometry": {
            "rawWidth": 1920,
            "rawHeight": 1080,
            "rotationDegrees": 270,
            "displayWidth": 1080,
            "displayHeight": 1920,
            "orientation": "portrait"
          },
          "replacementSource": "/Users/pengyang/Pictures/Video-make/video-claw-studio/projects/日本东京大阪行-6c28b7/delivery_packages/20260628_0240_davinci_v14_orientation_repair/v9_fix_inputs/segments/v9_replace_vertical_0288_with_landscape_station.mp4",
          "status": "replaced"
        }
      ]
    },
    "blockedNonLandscapeClips": [],
    "allowedDesignedNonLandscapeClips": [],
    "probeErrors": []
  }
}
```

### Opening, chapters, ending, aerials, and day transitions use scenic/route-aware bridge material
- Status: `passed`
- Evidence:
```json
{
  "visualEstablishingStatus": "ready_with_establishing_evidence",
  "visualEstablishingSummary": {
    "chapterCount": 6,
    "establishingRowCount": 8,
    "rowsWithEvidence": 8,
    "missingEstablishingCount": 0,
    "rowsWithTitleTypographyEvidence": 8,
    "verifiedAerialCount": 1,
    "stockAerialClosureStatus": "passed",
    "stockAerialUnresolvedPlaceholderCount": 0,
    "titleTypographyStatus": "ready_with_clean_title_typography_plan"
  },
  "stockAerialStatus": "passed",
  "stockAerialSummary": {
    "stockInsertPlanCount": 22,
    "placeholderCount": 22,
    "closedPlaceholderCount": 22,
    "unresolvedPlaceholderCount": 0,
    "verifiedAerialCount": 1,
    "sourcePathRiskCount": 0,
    "routeTexturePassed": true
  },
  "transitionBridgeStatus": "ready_with_bridge_evidence",
  "transitionBridgeSummary": {
    "chapterCount": 6,
    "boundaryRowCount": 5,
    "boundariesWithEvidence": 5,
    "missingBoundaryCount": 0,
    "existingTransitionPlanCount": 6,
    "existingBridgeClipCount": 21,
    "routeTextureStatus": "passed",
    "routeTextureMatchedTransitions": 6
  }
}
```

### Bilibili/Malta style, route texture, rhythm, and director polish gates pass
- Status: `passed`
- Evidence:
```json
{
  "referenceStyleStatus": "passed",
  "routeTextureStatus": "passed",
  "routeTextureSummary": {
    "transitionPlanCount": 6,
    "bridgeClipCount": 13,
    "matchedTransitions": 6,
    "chapterTitleCount": 6,
    "matchedTitleBoundaries": 5,
    "chapterWindowCount": 6,
    "passedChapters": 6,
    "categoryCounts": {
      "transport": 46,
      "street": 46,
      "livedIn": 43,
      "landmark": 43
    }
  },
  "directorIntentStatus": "passed",
  "directorIntentSummary": {
    "passed": 9,
    "blocked": 0,
    "warnings": 0,
    "total": 9,
    "mainClipCount": 55,
    "medianMainClipSeconds": 28.0,
    "subtitleCueCount": 95,
    "cuesPerMinute": 4.75,
    "chapterCount": 6
  },
  "directorPolishStatus": "passed",
  "editRhythmStatus": "ready_with_edit_rhythm_plan",
  "editRhythmSummary": {
    "timelineDurationSeconds": 1200.0,
    "primaryVisualShotCount": 63,
    "recommendedMinimumShotCount": 114,
    "estimatedAdditionalCutawayBeats": 51,
    "averageShotSeconds": 19.683,
    "medianShotSeconds": 28.0,
    "rhythmRiskCount": 41,
    "rowsWithDecisionFields": 63,
    "chapterRowCount": 8,
    "chaptersNeedingVarietyOrRetime": 8,
    "categoryCounts": {
      "opening_hook": 5,
      "transport_motion": 22,
      "title_bridge": 8,
      "route_transition": 18,
      "lived_in_detail": 6,
      "ending_aftertaste": 4
    },
    "referenceReady": true
  }
}
```

### Final output quality matches the V14 4K high-frame-rate high-bitrate floor
- Status: `passed`
- Evidence:
```json
{
  "renderStatus": "passed",
  "video": {
    "codec": "h264",
    "width": 3840,
    "height": 2160,
    "avgFrameRate": "60000/1001",
    "frameRateValue": 59.94005994005994,
    "bitrateMbps": 79.97,
    "frames": "71934"
  },
  "durationSeconds": 1200.170667
}
```

### Final QA suite preserves the V14 17-stage handoff floor
- Status: `passed`
- Evidence:
```json
{
  "finalQaStatus": "passed",
  "finalQaSummary": {
    "passedStages": 17,
    "blockedStages": 0,
    "totalStages": 17
  },
  "strictPackageIntegrityStatus": "passed",
  "strictPackageIntegritySummary": {
    "coreCrossPackagePathCount": 0,
    "activeCoreCrossPackagePathCount": 0,
    "closedCoreCrossPackagePathCount": 0,
    "criticalCrossPackagePathCount": 0
  }
}
```

### Skill maturity preserves the V14 29-check reusable-skill floor
- Status: `passed`
- Evidence:
```json
{
  "skillMaturityStatus": "passed",
  "skillMaturitySummary": {
    "passed": 29,
    "blocked": 0,
    "warnings": 0,
    "total": 29
  }
}
```
