# Transition Grammar Engine

Use this reference when a travel cut needs better shot-to-shot flow, especially after the user says transitions still feel weak, abrupt, template-like, or unlike the Parallel World/Malta references.

## Purpose

The transition bridge plan decides what material is needed between chapters. The effect motion plan decides what motion style is allowed. The transition grammar layer decides how each adjacent pair of timeline clips should connect.

This layer prevents three common failures:

- hard jumps between places with no route evidence
- flashy effects used to hide weak footage
- repeated dissolves that make the edit feel generic

## Pair-Level Rules

For every adjacent pair of primary visual clips, identify:

- whether this is a same-scene cut, chapter boundary, title boundary, route movement, or ending transition
- whether physical bridge evidence exists: road, station, train, ferry, plane, car window, walking, signage, map, hotel window, weather, water, skyline, food table, or night/day change
- whether the two clips share a visual match: motion direction, water, road, window, skyline, food, sign, color, shape, or camera movement
- whether BGM phrasing should carry the transition
- whether captions should be suppressed because the transition overlaps a title zone
- the storyboard purpose, outgoing shot, bridge-or-motion beat, landing shot, and preview/frame evidence fields needed by `prepare_transition_preview_packet.py`, `audit_transition_preview_quality_contract.py`, and `audit_transition_storyboard_contract.py`

## Recommended Transition Types

- `straight_cut`: same scene, same activity, or clear action continuity.
- `match_cut`: shared shape, direction, object, color, water, road, window, skyline, sign, or food-table logic.
- `short_dissolve`: time, weather, mood, day-night, scenic aftertaste, or memory-like chapter change.
- `whip_pan_match`: both sides have clear pan, walking, vehicle, crowd, or route-motion energy.
- `rotation_match_cut`: both sides have circular/turning/camera-rotation energy or a strong route-motion bridge. Use rarely.
- `speed_ramp_bridge`: real vehicle, aerial, water, crowd, walking, or camera motion supports a brief ramp.
- `insert_bridge_first`: the pair has no physical route evidence; add bridge footage before effects.

## Hard Rejections

- random spin because the cut feels boring
- flash/glitch/shake/strobe/template-pack transition without story purpose
- route jump covered only by a title card
- whip/rotation across two static scenic shots
- transition effect over unreadable title typography
- source-camera voice leaking under scenic/title transition windows

## Acceptance Bar

Before Resolve apply:

- every chapter/day/place boundary has a transition grammar row
- every row has one recommended transition and one fallback
- every row has storyboard decision fields: `storyboardPurpose`, `outgoingShotEvidence`, `bridgeOrMotionBeatEvidence`, `landingShotEvidence`, `previewStripEvidence`, and `frameSampleEvidence`
- whip/rotation rows cite route-motion evidence
- rows lacking physical bridge evidence are marked `insert_bridge_first`, not effect-ready
- important day/place/title/timeline-gap/ending transitions include a ready `transition_preview_packet` and passed transition preview quality contract before approval
- transition decisions align with creator cut tiers and route texture goals
