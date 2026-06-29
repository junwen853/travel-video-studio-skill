# Footage Select Engine

Use this reference before building the first delivery package from a large unordered travel source folder. This layer is earlier than the edit rhythm, creator cut, and transition grammar passes: it decides which raw videos deserve to enter the first assembly at all.

## Purpose

The user wants a future agent to receive 100GB+ of mixed footage and make a strong first draft without repeated correction. That requires raw-footage triage before the Resolve blueprint is built.

The Footage Select Engine turns a source folder or `media_index.json` into a machine-readable shot pool:

- hero candidates for opening, chapter payoff, cover/title background, and ending
- main story candidates for route and experience beats
- texture bridge candidates for transport, street, food, hotel, weather, signage, and daily travel details
- utility context that should be short and secondary
- repair/reject rows for portrait, square, unknown-orientation, duplicate, derived, placeholder, weak, or excluded clips

## Selection Bias

Default to selective editing. A clip should not enter the first assembly just because it exists.

Prefer local user footage before stock or aerial fallback:

- use local skyline, transport, station, street, food, hotel-window, weather, and signage clips as bridge material
- use local landmark or scenic clips as chapter payoff when they are readable and landscape
- use stock/aerial only when local footage cannot make the place legible, and only with license evidence

Reject or demote:

- prior exports, final masters, VLOG renders, screen recordings, slates, and placeholder title cards
- raw portrait/square/unknown-orientation clips unless there is an explicit phone/PiP/reframe design
- shaky, obstructed, black, duplicate, too-short, or extremely long clips with no story value
- weak footage that would need a random transition effect to feel interesting

## Required Script

Run this after media indexing and route/location recognition, before `build_delivery_package.py`:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --project-dir <project>
```

After `build_delivery_package.py` creates a package, run the source coverage repair gate before trusting the first assembly:

```bash
python3 <skill-dir>/scripts/prepare_source_selection_repair_plan.py --package-dir <package> --project-dir <project>
python3 <skill-dir>/scripts/audit_source_selection_coverage_contract.py --package-dir <package>
```

When only a package exists, run the fallback mode:

```bash
python3 <skill-dir>/scripts/prepare_footage_select_plan.py --package-dir <package>
python3 <skill-dir>/scripts/prepare_source_selection_repair_plan.py --package-dir <package>
python3 <skill-dir>/scripts/audit_source_selection_coverage_contract.py --package-dir <package>
```

The script writes:

- `footage_select_plan/footage_select_plan.json`
- `footage_select_plan/footage_select_plan.md`
- `source_selection_repair_plan/source_selection_repair_plan.json`
- `source_selection_repair_plan/source_selection_repair_plan.md`
- `source_selection_coverage_contract_audit.json` / `.md`
- `raw_intake_completeness_audit.json` / `.md` after the package exists and `audit_raw_intake_completeness.py` is run

If run at project level, `build_delivery_package.py` should read the plan and sort each chapter's media pool by `selectionTier` and `selectionScore`, while dropping `reject_excluded` rows and deprioritizing repair/review rows.

## Acceptance Bar

Before first assembly:

- every active source video is represented in `selectionRows`
- `audit_raw_intake_completeness.py` passes, proving media index, recognition report, confirmed route, and footage select agree on every active source video
- hero/main/texture/utility/reject tiers exist where the source supports them
- every row has decision fields for approved use, trim, orientation repair, BGM/caption role, Resolve implementation, and readback evidence
- chapter pools show whether movement, lived-in detail, and payoff coverage are missing
- `source_selection_repair_plan.json` closes those missing chapter functions into blocking repair rows before effects, stock/aerial fallback, rhythm, creator-cut, or Resolve apply
- vertical/square/unknown footage is marked for repair before use
- derived exports and active exclusions are blocked from first-cut selection
- the plan proves source media was triaged before stock, effects, or transition grammar are used
- after the final candidate blueprint exists, `audit_final_source_usage_contract.py` proves final raw clips still match selected hero/main/texture rows and do not reintroduce unmatched, repair, reject, or utility-dominant material

## Downstream Order

Use the output in this order:

1. Build or refresh the package so high-score local footage is chosen first.
2. Run `prepare_source_selection_repair_plan.py` and `audit_source_selection_coverage_contract.py`; stop when blocking repair rows exist.
3. Run `prepare_edit_rhythm_plan.py` to decide pacing and cutaway needs.
4. Run `prepare_creator_cut_plan.py` to classify the selected timeline clips by creator function.
5. Run `prepare_transition_grammar_plan.py` to decide exact adjacent-pair transitions.
6. Run rhythm recut and Resolve preflight only after the above plans agree.

Do not claim the Skill can reliably make a Bilibili/Malta-style first draft if this raw-footage selection layer is missing or only run after the timeline has already been assembled.
