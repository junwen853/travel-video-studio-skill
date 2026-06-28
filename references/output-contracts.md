# Output Contracts

## Core Artifacts

`project.json`

- Project metadata, user-facing title/destination, media roots, and style preset.
- Use it to detect whether the intended trip matches actual media.

`media_index.json`

- Scan result for source media.
- Important fields: `summary.videoCount`, `summary.totalDuration`, `roots`, `missingRoots`, `files`.

`external_media_intake.json`

- Mounted-drive project/media-root choice packet written by `prepare_external_media_intake.py`.
- Important fields: `status`, `defaultSelectedProject`, `projects`, `externalDiscovery.likelyTravelRoots`, `recommendedChoices`, `blockers`, `warnings`, and `safety`.
- Use it before a long-form package build when a drive contains multiple trips, such as Japan and Hong Kong/Macau, or when an existing project title conflicts with its media root.
- `recommendedChoices[].nextCommands` should point at explicit `--project-name` commands; do not rely on the default project when `warnings` says multiple trip regions are present.

`analysis/light/<timestamp>/frame_index.json`

- Lightweight extracted frame catalog.
- Important fields: `createdAt`, `frameCount`, `frames`.
- Each frame should include `videoId`, `sourceVideo`, `timestamp`, `path`, and visual heuristics such as brightness/contrast/edge detail when available.

`local_prefilter.json`

- Local video/frame selection for cloud budget.
- Important fields: `localModelUsed`, `localModelError`, `videos`, `cloudFrameBudget`, `summary`.
- Video entries should include `priority`, `sendToCloud`, `localPlaceHints`, and review flags.

`location_recognition/*`

- Channel-specific request, raw result, and parsed result artifacts.
- Channels normally include landmark, OCR, scene, and language/region.

`location_candidates.json`

- Multi-evidence candidates before picking a final place per video.

`video_location_map.json`

- Best place per video.
- Important fields: `videoCount`, confidence-level counts, `videos[].bestPlace`, `videos[].city`, `videos[].confidence`, `videos[].needsHumanReview`.

`route_timeline.json`

- Automatic route reconstruction.
- Important fields: `chapterCount`, `chapters`, `needsHumanReviewCount`, `transitChapterCount`.

`confirmed_route_timeline.json`

- User-confirmed route. This is the only route artifact that should drive a final route-aware rough cut.
- Important fields: `chapters[].place`, `chapters[].originalPlace`, `chapters[].userModifiedPlace`, `chapters[].markedDoNotCut`.

`latest_route_review.json`

- Pointer to the newest route review packet.
- Important fields: `routeReview`, `createdAt`, `status`.
- Use it when `confirmed_route_timeline.json` is stale, the project route/title conflicts with inferred media, or route chapters still need human review.

`latest_route_coverage_scaffold.json`

- Pointer to the newest full-media route coverage scaffold.
- Important fields: `scaffold`, `createdAt`, `status`.

`route_scaffold/<timestamp>/route_coverage_scaffold.json`

- Full-media route scaffold written by `build_route_coverage_scaffold.py`.
- Important fields: `status`, `mode`, `coverage`, `chapterCount`, `chapters`, `warnings`, `scaffoldMarkdown`, `contactSheet`.
- It may use ordered media and filename markers such as `chapter_osaka`, `map_osaka_tokyo`, or `end`; it is not confirmed location recognition.
- Use it as `prepare_route_review.py --route-source <route_coverage_scaffold.json>` when automatic route coverage is too low.

`route_review/<timestamp>/route_review.json`

- Machine-readable route/location review packet written by `prepare_route_review.py`.
- Important fields: `status`, `project.declaredRegions`, `project.inferredRegions`, `freshness.stale`, `coverage`, `chapters`, `uncoveredVideos`, `blockers`, `warnings`, `contactSheet`, `reviewMarkdown`.
- Do not rename this to `confirmed_route_timeline.json`; use it to make a reviewed confirmed route after decisions.

`route_review/<timestamp>/contact_sheet.jpg`

- Human-readable frame evidence for confirming/correcting the route.
- Use it to spot obvious mismatches, such as a Hong Kong/Macau project title with Japan/Tokyo/Osaka footage.

`latest_route_decision_sheet.json`

- Pointer to the newest route decision sheet.
- Important fields: `decisionSheet`, `createdAt`, `status`.

`route_review/<timestamp>/route_decision_sheet.json`

- Editable route approval sheet written by `prepare_route_decision_sheet.py`.
- Important fields: `sourceRouteReview`, `projectRegionReview`, `approval`, `decisionRows`, `blockers`, `nextCommands`, and `safety`.
- It is not a confirmed route. Use it to copy explicit `reviewDecision` and `corrected*` fields into `route_review.json`, then run `prepare_confirmed_route_candidate.py`.
- A region mismatch remains unresolved until `projectRegionReview.approvedResolution`, `approvedBy`, and chapter decisions are explicitly filled or the user selects different media.

`route_review/<timestamp>/route_decision_application.json`

- Dry-run or applied route decision application report written by `apply_route_decision_sheet.py`.
- Important fields: `status`, `applied`, `wouldApply`, `summary`, `blockers`, `warnings`, and `safety`.
- It is safe by default and only writes decisions back into `route_review.json` with `--apply`.
- It never writes `confirmed_route_timeline.json`; use `prepare_confirmed_route_candidate.py` after route review decisions are applied.

`latest_confirmed_route_candidate.json`

- Pointer to the newest confirmed route candidate.
- Important fields: `candidate`, `createdAt`, `status`.

`route_review/<timestamp>/confirmed_route_candidate.json`

- Approval-gated candidate written by `prepare_confirmed_route_candidate.py`.
- Important fields: `status`, `canApply`, `candidate`, `draftChapters`, `blockers`, `warnings`, `nextActions`, `candidateMarkdown`.
- This is not final unless `canApply` is true and the user approves `--apply`.
- A blocked candidate is useful evidence: it explains what must be fixed before `confirmed_route_timeline.json` can be rewritten.

`latest_location_route_pipeline.json`

- Latest pipeline status envelope.
- Important fields: `dryRun`, `allowCloudCall`, `cloudProviderUsed`, `localModelUsed`, `providerWarnings`, `projectWarnings`, `steps`, `errors`, `finalFiles`, `summary`.

`resolve_timeline_blueprint.json`

- Resolve API assembly blueprint.
- Important fields: `projectName`, `timelineName`, `fps`, `resolution`, `tracks`, `clips`, `assets`, `coverageRatio`, `subtitleCues`, `audioPlan`, `stockInsertPlan`, `transitionPlan`, and `timelineMarkers`.
- Footage clips can set `includeSourceAudio: true` to preserve camera/source audio on A1 during Resolve writes. Title cards, overlays, and other video-only inserts should leave source audio disabled and keep `mediaType: 1`.
- `longFormCoverage` records initial selected seconds, visual-bed fill seconds/clips, final covered seconds, and target seconds. Use it to prove the 20-minute plan is actually covered by timeline media when source duration is available.
- Do not treat this as proof that Resolve was written. It is only the input to `build_resolve_timeline.py`.

`resolve_blueprint_preflight.json`

- No-write preflight report written by `audit_resolve_blueprint.py`.
- Important fields: `status`, `clipSummary`, `assetSummary`, `enrichmentSummary`, `blockers`, `warnings`, and `safety`.
- It proves whether the blueprint is structurally safe to attempt a Resolve write: source files exist, source ranges are within probed durations, same-track overlaps are absent, V1 covers the long-form target, generated title/place card assets exist, subtitle and marker plans are present, and source-footage audio policy is represented.
- `status: blocked` must block `build_resolve_timeline.py --apply`. `ready_with_warnings` can still be blocked by package-level delivery gates such as route review, voiceover, BGM, stock/aerial, or licenses.

`resolve_timeline_enrichment.json`

- Long-form editorial enrichment written by `enrich_resolve_blueprint.py`.
- Important fields: `subtitlePlan`, `subtitleCues`, `audioPlan.voiceover`, `audioPlan.bgmCues`, `stockInsertPlan`, `transitionPlan`, `timelineMarkers`, and `summary`.
- This is the evidence that narration, subtitles, BGM placeholders, stock/aerial placeholders, transitions, and chapter markers are represented in the Resolve handoff before actual timeline writing.

`delivery_assets_report.json`

- Package-level local asset preparation report written by `prepare_delivery_assets.py`.
- Important fields: `titleCards.status`, `titleCards.manifest`, `voiceover.status`, `voiceover.result`, `resolveEnrichment`, `blockers`, and `safety`.
- It may prove local title/place cards were generated and Resolve enrichment was refreshed. It does not prove BGM, stock/aerial, or font licenses are approved.
- Local TTS is generated only when the script is called with `--generate-local-voiceover`; otherwise voiceover remains a recorded blocker/next action.

`workflow_run_report.json`

- Safe local orchestration report written by `run_delivery_workflow.py`.
- Important fields: `status`, `packageDir`, `steps`, `projectStateSummary`, `resolveApiSummary`, `routeDecisionSummary`, `routeDecisionApplicationSummary`, `assetDecisionSummary`, `dryRunSummary`, `resolveApplyContractSummary`, `renderPlanSummary`, `auditSummary`, `blockers`, `warnings`, `safety`, and `nextManualApprovals`.
- It proves which package-preparation commands ran and whether each returned an expected code. It does not prove final delivery unless `auditSummary.finalRenderAllowed` is true and required Resolve readback/render artifacts also exist.
- Safety fields must remain false for `writesResolve`, `queuesRender`, and `downloadsExternalAssets` in the safe workflow.
- `check_project_state.py` may return code 2 when the project has route, freshness, or mismatch blockers. In a safe workflow report this is not a workflow failure if the step has `ok: true`; those issues must appear under `projectStateSummary.blockingIssues` and top-level `blockers`.
- `resolveApiSummary` records whether DaVinci Resolve Studio, the scripting module, the Fusion script library, and a live Resolve process are reachable. If `reachable` is false, the workflow may still build a package, but actual Resolve writes/readback/render gates remain blocked.
- `renderPlanSummary` proves that `prepare_resolve_render.py` wrote a safe render plan. It does not mean a render was queued or started; `queued` and `started` must stay false until explicit user approval.

`resolve_audit.json`

- Resolve readback report after an actual timeline write.
- Important fields: `projectName`, `timelineName`, `startFrame`, `endFrame`, `tracks`, `items`, `warnings`.
- Final render must not proceed when this is missing, mismatched, or contains warnings.

`resolve_apply_contract.json`

- Approval contract written by `prepare_resolve_apply_contract.py` before any actual `build_resolve_timeline.py --apply`.
- Important fields: `status`, `projectName`, `timelineName`, `fps`, `resolution`, `trackPlan`, `clipPlan`, `resolveBlueprintPreflightStatus`, `preflightSummary`, `longFormCoverage`, `writeCommand`, `readbackAuditCommand`, `approval`, `blockers`, `warnings`, and `safety`.
- `status` must be `awaiting_user_approval` and the user must explicitly approve before running the write command.
- It does not prove Resolve was written; `resolve_audit.json` is still required after any actual write.

`render_plan.json`

- Resolve render/export plan written by `prepare_resolve_render.py`.
- Important fields: `projectName`, `timelineName`, `targetDir`, `customName`, `requestedFormat`, `requestedCodec`, `renderSettings`, `gate`, `queued`, `started`, `jobId`, `jobStatus`.
- `gate.allowed` must be true and `delivery_audit.json.finalRenderAllowed` must be true before `--queue` or `--start`.

`render_job_status.json`

- Present only after an approved render job is queued or started.
- Important fields mirror `render_plan.json` plus `jobId`, `jobStatus`, and `started`.

`asset_sourcing/asset_sourcing_packet.json`

- Provider and approval packet for exact BGM, stock/aerial, and font decisions.
- Important fields: `status`, `providerDirectory`, `chapterNeeds`, `sourcingRows`, `summary.unverifiedBgmOrStock`, `blockers`, and `nextActions`.
- `providerDirectory[].licenseUrl` is only the provider/license reference; it is not proof that an individual asset is approved.
- BGM and stock/aerial `sourcingRows` must be reconciled back into `asset_ledger/asset_license_ledger.json` before final render.

`asset_sourcing/asset_decision_reconciliation.json`

- Dry-run or applied reconciliation report written by `apply_asset_sourcing_decisions.py`.
- Important fields: `status`, `applied`, `summary`, `rowReports`, `blockers`, `warnings`, and `safety`.
- It is safe by default and only updates `asset_license_ledger.json` with `--apply`.
- Final BGM/stock/aerial rows need exact asset URL or local path, provider, license URL, approver, approval time, and evidence before the ledger can become final-ready.

## Freshness Rules

Treat an artifact as stale when:

- `latest_location_route_pipeline.json` is older than the latest `frame_index.json`.
- `local_prefilter.json` is older than the latest `frame_index.json`.
- `route_timeline.json` is older than `video_location_map.json`.
- `confirmed_route_timeline.json` is older than `route_timeline.json`.
- the pipeline reports far fewer videos/frames than the latest frame index or media index.

When stale, do not delete anything. Report which file is stale and which stage must be rerun.

## Mismatch Rules

Warn or block when:

- project title/destination says Hong Kong/Macau but media roots or recognized places say Japan/Tokyo/Osaka
- project title/destination says Japan/Tokyo/Osaka but recognized places say Hong Kong/Macau
- route chapters are all `unknown`
- most videos require human review
- cloud run was expected but the pipeline is still `dryRun: true` or `allowCloudCall: false`

Mismatch is not always a bug. It can mean the user selected the wrong project, used old artifacts, or intentionally changed the media root. Ask for confirmation before final cutting.
