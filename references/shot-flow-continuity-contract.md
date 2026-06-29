# Shot Flow Continuity Contract

Use this contract after chapter-story-spine, timeline-variety, reference-scene, and transition continuity gates. It proves the final candidate timeline is not only varied at film level, but also ordered inside each chapter in a viewer-readable travel-film flow.

Run:

```bash
python3 <skill-dir>/scripts/audit_shot_flow_continuity_contract.py --package-dir <package>
```

The audit is read-only. It never writes Resolve, queues renders, downloads assets, modifies source footage, or touches the source drive.

## Pass Contract

A passing package must prove:

- The selected final candidate blueprint exists inside the package and has at least three primary visual clips.
- Chapter story-spine, timeline-variety, reference-scene grammar, transition pair-continuity, and transition microstructure reports are accepted.
- Every chapter's final clip order carries movement, lived-in texture, destination payoff, and aftertaste or handoff evidence.
- Payoff shots are supported by nearby movement or texture, not dropped in randomly as effect cover.
- Aftertaste or handoff beats happen near the end of a chapter, not in the middle before more unresolved footage.
- Adjacent story beats avoid random jumps such as aftertaste returning to route setup, repeated payoffs without texture, or long title/effect/utility runs.
- Active final clips do not include rejected, utility-only, weak, placeholder, or unclassified material.
- Same-source, same-beat, and utility/title runs stay short enough that transitions cannot hide a poor shot sequence.

## Repair Guidance

If blocked, repair the actual candidate order before adding more effects. Preferred repairs:

- Move transport, walking, station, road, ferry, or map-like movement clips before landmark payoff when the route feels unearned.
- Insert lived-in texture such as streets, food, markets, hotel, signs, weather, waiting, tickets, or small human moments before or after scenic payoffs.
- Replace title/effect-only bridges with real local bridge footage or a restrained match cut.
- Move aftertaste, sunset, quiet, departure, or callback material to the end of the chapter.
- Replace active rejected, utility-only, weak, black, placeholder, duplicated, obstructed, or unclassified clips through creator-cut/source-selection repair instead of masking them with rotations or speed ramps.

Do not call a draft Parallel World/Malta-like when this gate blocks. The references use scenic openings and clean transitions, but their strength comes from ordered viewer comprehension: setup, movement, texture, payoff, and emotional landing.
