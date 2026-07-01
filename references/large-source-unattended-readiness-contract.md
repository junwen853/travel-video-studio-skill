# Large Source Unattended Readiness Contract

Use this contract when the source folder is large, unordered, mounted from an external drive, or expected to work without the user pointing out missing recognition, weak source choice, route mistakes, or filename-order cutting. It is the "100GB folder can reach a safe first draft" gate.

## Command

```bash
python3 <skill-dir>/scripts/audit_large_source_unattended_readiness_contract.py \
  --package-dir <package> \
  --min-free-gb 40 \
  --working-set-ratio 0.35 \
  --json
```

When a mounted drive or ambiguous media root is involved:

```bash
python3 <skill-dir>/scripts/audit_large_source_unattended_readiness_contract.py \
  --package-dir <package> \
  --project-dir <project> \
  --external-media-intake <external_media_intake.json> \
  --require-external-intake \
  --min-free-gb 40 \
  --working-set-ratio 0.35 \
  --json
```

## Required Inputs

- `raw_intake_completeness_audit.json`
- latest footage recognition route report
- `location_truth_contract_audit.json`
- `footage_select_plan/footage_select_plan.json`
- `source_selection_repair_plan/source_selection_repair_plan.json`
- `source_selection_coverage_contract_audit.json`
- `first_assembly_source_order_contract_audit.json`
- `unattended_first_draft_contract_audit.json`
- `resolve_blueprint_preflight.json` when Resolve blueprint preflight exists
- `external_media_intake.json` when a large mounted or ambiguous media root is involved
- Project `mediaRoots` or ready external-intake `sourceRoot` values that point to the source footage roots.

## Pass Criteria

- The selected project/media root is known and the media index covers the active source videos.
- Large sources use `media_index` as the footage-select input, not blueprint fallback or samples.
- External media intake is ready when the source is large or explicitly required.
- Package and project write paths are outside the source footage roots, no source root is nested inside the package, and missing source roots block the run.
- The package volume has an explicit free-space budget before unattended work starts: by default at least `max(40GB, min(sourceSizeGB * 0.35, 120GB))`.
- Resume checkpoints exist for raw intake, recognition, location truth, footage selection, source repair, source coverage, first assembly, unattended first draft, and external intake when required.
- Whole-folder recognition covers every active source video and has no missing or duplicated route rows.
- Location truth allows route-aware editing while avoiding GPS/per-clip overclaiming.
- Source selection has enough hero/main/texture candidates and no missing footage-select rows.
- Source repair and source-selection coverage have no blocking rows before effects, stock, or rhythm recut are used.
- First assembly proves it used scored source selection rather than filename order.
- Unattended first-draft and Resolve blueprint preflight are connected before any Resolve write.

## Repair Route

If blocked, repair in order. First fix media root/project choice with `prepare_external_media_intake.py`, move package/project outputs outside the source footage root if needed, and free or choose enough workspace storage before starting a long unattended run. Then rebuild or apply the media index with `run_videoclaw_media_index.py`, regenerate recognition and truth reports, rerun footage selection and source-selection repair, rebuild the package so first assembly records selection sorting, and only then rerun unattended first-draft and Resolve preflight. Do not hide weak large-source selection, unsafe storage, or missing checkpoints behind transitions, stock footage, or rhythm recut.
