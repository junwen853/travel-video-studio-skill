# Chapter Story Spine Contract

Use this contract after `prepare_chapter_arc_plan.py`, `prepare_edit_rhythm_plan.py`, `prepare_creator_cut_plan.py`, `audit_reference_scene_grammar_contract.py`, `audit_timeline_variety_contract.py`, `audit_transition_scene_arc_contract.py`, and `audit_reference_transition_profile_contract.py`.

Run:

```bash
python3 <skill-dir>/scripts/audit_chapter_story_spine_contract.py --package-dir <package>
```

The audit blocks when a chapter is only a title, landmark pile, stock/aerial placeholder, hard-cut chain, or transition-effect cover-up. A ready chapter must carry this spine:

- context: why the chapter matters to the viewer
- movement: how the trip physically enters or changes place
- texture: street, food, hotel, weather, waiting, sign, room, crowd, or other lived-in detail
- payoff: landmark, activity, skyline, coast, mountain, aerial, or destination reward
- aftertaste: quiet handoff, departure, night, route callback, or bridge into the next chapter

Passing requires the story spine to survive into rhythm rows, creator-cut rows, selected raw footage usage, reference scene grammar, timeline variety, transition scene arcs, and reference-transition profile balance. Effects, whip/rotation moves, or BGM hits cannot compensate for missing route movement or lived-in footage.

The script writes `chapter_story_spine_contract_audit.json` and `.md` without writing Resolve, downloading assets, queueing renders, or modifying source footage.
