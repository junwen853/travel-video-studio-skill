# Creator Cut Engine

Use this reference when the user wants the edit to get closer to the four `叽叽歪歪的平行世界` videos, the Malta final, or any creator-quality long-form travel vlog. This is a non-copying editorial standard. Do not copy footage, titles, music, or narration from references.

## Purpose

The Skill already knows how to build a route-aware package. The Creator Cut Engine adds the timeline-level editorial judgment layer: choose fewer and better selected shots, assign every kept shot a function, and make transitions feel like a traveled route instead of a raw clip stack.

Run the raw-footage selection layer first when a project source folder is available:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --project-dir <project>
```

The creator cut should refine the selected timeline, not compensate for a missing source-pool triage pass.

## Shot Tiers

Classify every usable visual clip before Resolve apply.

- Hero: aerial, skyline, coast, landmark, strong human reaction, or unusually clear place identity. Use for opening, chapter payoff, cover/title background, or ending.
- Main story: route movement, arrival, street exploration, meal/activity, room view, local detail, or companion/context that moves the film forward.
- Texture bridge: station, road, vehicle window, signage, weather, food table, walking, escalator, hotel window, night street, water, skyline, or quiet ambient detail.
- Utility only: technically usable but visually ordinary; use only to patch route continuity, not as a long hold.
- Reject/review: repeated, shaky, obstructed, black, accidental, low-recognition, internal slate, or long raw footage with no route/story value.

The default bias is selective. A clip should not enter the final timeline just because it exists.

## Creator Chapter Pattern

Each chapter should contain at least three functions:

- establish: where are we now?
- movement: how did we get here or leave here?
- lived-in detail: what makes this moment feel real?
- payoff: what was worth seeing?
- aftertaste: what emotional or route residue carries into the next section?

If adjacent clips share the same function, split them with a different function before adding effects.

## Transition Rules

Prioritize real route evidence before motion effects.

Strong transition sources:

- road, train, plane, ferry, car window, taxi, airport, station, bridge, escalator, elevator
- walking direction, pan/tilt, skyline, water movement, weather, day-night shift
- signage, tickets, maps, phone navigation, hotel window, food-table reset

Allowed transition effects:

- straight cut when action or eyeline matches
- short dissolve for time, weather, mood, or day-night change
- match cut by motion, color, shape, water, road, window, or skyline
- whip-pan or rotation match cut only when both sides have clear motion/route energy
- short speed ramp only for actual movement footage such as vehicle, aerial, water, walking, or crowd flow

Reject effects that hide weak material: random spin, flash, glitch, shake, particle, repeated whoosh, template pack, or a route jump with no physical bridge footage.

After this shot-selection pass, run the pair-level transition grammar:

```bash
python3 <skill-dir>/scripts/prepare_transition_grammar_plan.py --package-dir <package>
```

Use the transition grammar rows to decide exactly how adjacent clips connect. If a row says `insert_bridge_first`, add or relabel real route footage before choosing an effect.

## Subtitle And BGM Role

No-voiceover cuts must let BGM and captions carry structure.

- Captions should sound like travel-film observations, not editor reports.
- BGM should change or breathe with sections: opening promise, city exploration, route transition, scenic payoff, ending aftertaste.
- After transition/effect candidate blueprints exist, run `prepare_bgm_phrase_blueprint.py` so section changes and transition effects are tied to candidate BGM phrase markers instead of loose notes.
- Scenic/title/transition windows should be BGM-led unless intentional ambient is approved.

## Acceptance Bar

Before calling a cut creator-like:

- The first minute has a strong visual hook and a clear destination signal.
- Every primary clip has a creator function, not only a location label.
- Weak or duplicate clips are explicitly rejected or demoted to utility.
- Every chapter has establish/movement/detail/payoff/aftertaste coverage or an explicit missing-coverage row.
- Every day/place boundary has real bridge footage before any transition effect.
- BGM phrase blueprint rows cover opening/body/transition/ending sections and every candidate transition has a phrase cue.
- Whip/rotation transitions are motivated by movement; they are not default decoration.
- The ending uses quiet route aftertaste, not a leftover clip.
