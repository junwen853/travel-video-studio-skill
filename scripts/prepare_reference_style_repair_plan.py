#!/usr/bin/env python3
"""Prepare a reference-style repair plan from audits and planning artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_REFERENCE_TARGETS = {
    "source": "parallel_world_batch_profile",
    "averageShotLengthSeconds": 5.0,
    "medianShotLengthSeconds": 2.95,
    "shortShotUnder3sShare": "high_but_not_hypercut",
    "longBreathingShotPolicy": "few deliberate 20s+ scenic or human moments only when image value is high",
    "audioMeanVolumeDb": -19.93,
    "openingRule": "viewer promise, destination proof, clean hero title, practical arrival, lived-in texture, first handoff",
    "endingRule": "route aftertaste after the main experience",
}

DECISION_FIELDS = {
    "acceptedRepair": False,
    "repairOwner": "",
    "repairAppliedAt": "",
    "resolveBlueprintEvidence": "",
    "resolveTimelineReadback": "",
    "renderFrameSampleEvidence": "",
    "postRepairAudit": "",
    "editorNotes": "",
}

CHECK_TO_REPAIR = (
    (
        ("Reference material is present", "reference"),
        {
            "area": "reference_profile",
            "priority": "P0",
            "ownerScript": "analyze_reference_video.py",
            "requiredArtifact": "reference/reference_analysis.json",
            "repairAction": "Analyze at least one local long-form travel reference or the supplied Malta/four-video reference set before claiming Bilibili/Malta-style quality.",
            "acceptanceEvidence": "reference_analysis.json has pacingStatus=analyzed, audioStatus=analyzed, sample frames, contact sheet, and a non-copying contract.",
        },
    ),
    (
        ("Long-form duration target", "duration"),
        {
            "area": "longform_structure",
            "priority": "P1",
            "ownerScript": "build_delivery_package.py",
            "requiredArtifact": "resolve_timeline_blueprint.json",
            "repairAction": "Rebuild or extend the package with enough real visual coverage for the requested long-form target; do not pad with black/title slates.",
            "acceptanceEvidence": "reference_style_alignment_audit shows duration target met and longform_delivery_audit passes.",
        },
    ),
    (
        ("Route has multiple", "Route arc", "route"),
        {
            "area": "route_arc",
            "priority": "P0",
            "ownerScript": "prepare_route_review.py",
            "requiredArtifact": "delivery_plan.json",
            "repairAction": "Repair chapter order and route evidence so arrival, movement, exploration, and closure read as a real trip.",
            "acceptanceEvidence": "director_intent_contract_audit route arc check passes and location truth caveat remains honest.",
        },
    ),
    (
        ("Transport and connective", "transition", "bridge"),
        {
            "area": "route_bridges",
            "priority": "P0",
            "ownerScript": "prepare_transition_bridge_plan.py",
            "requiredArtifact": "transition_bridge_plan/transition_bridge_plan.json",
            "repairAction": "Insert local route bridge footage first: airport, train, road, ferry, walking, sign, hotel, map/device, weather, or street reset before scenic payoff.",
            "acceptanceEvidence": "transition bridge plan has local footage evidence and transition execution rows are no longer bridge-blocked.",
        },
    ),
    (
        ("Street, lived-in", "Chapter beats", "lived"),
        {
            "area": "lived_in_texture",
            "priority": "P1",
            "ownerScript": "prepare_creator_cut_plan.py",
            "requiredArtifact": "creator_cut_plan/creator_cut_plan.json",
            "repairAction": "Add or promote street, food, hotel, shop, waiting, sign, and human/context clips between transport and landmark payoff.",
            "acceptanceEvidence": "creator cut keeps texture bridge/main rows and route_texture_contract_audit category counts include street, livedIn, landmark, and transport.",
        },
    ),
    (
        ("edit_rhythm_plan", "edit rhythm"),
        {
            "area": "shot_pacing",
            "priority": "P0",
            "ownerScript": "prepare_edit_rhythm_plan.py",
            "requiredArtifact": "edit_rhythm_plan/edit_rhythm_plan.json",
            "repairAction": "Generate the edit rhythm plan so every primary shot has a function, long raw holds are identified, and missing cutaway beats become trim/split/insert decisions.",
            "acceptanceEvidence": "edit_rhythm_plan is ready, primary visual rows have decision fields, and long-shot/cutaway risks are explicit before recut.",
        },
    ),
    (
        ("varied real footage", "Shot pacing", "slideshow", "dump", "edit_rhythm_plan", "rhythm_recut_blueprint"),
        {
            "area": "shot_pacing",
            "priority": "P0",
            "ownerScript": "prepare_rhythm_recut_blueprint.py",
            "requiredArtifact": "rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json",
            "repairAction": "Split long raw holds, insert existing-footage cutaways from different functions, and demote weak clips instead of keeping filename-order montage pacing.",
            "acceptanceEvidence": "rhythm recut report lowers longShotRiskAfter and reference/director audits accept the median/average shot rhythm.",
        },
    ),
    (
        ("Opening", "title", "hero", "opening_story_plan"),
        {
            "area": "opening_title",
            "priority": "P0",
            "ownerScript": "prepare_opening_story_plan.py",
            "requiredArtifact": "opening_story_plan/opening_story_plan.json",
            "repairAction": "Repair the first three minutes around promise, destination proof, one clean scenic hero title, arrival reality, lived-in texture, and first handoff.",
            "acceptanceEvidence": "opening_story_plan is ready and title_bridge/title_typography audits show no ghosted, stacked, or internal-label title text.",
        },
    ),
    (
        ("No-voiceover", "BGM", "Captions", "audio"),
        {
            "area": "audio_caption_story",
            "priority": "P0",
            "ownerScript": "prepare_audio_scene_policy_plan.py",
            "requiredArtifact": "audio_scene_policy_plan/audio_scene_policy_plan.json",
            "repairAction": "Keep scenic/title/transition windows BGM-led, suppress A1/A2 voice leakage, and rewrite TXT/SRT as audience-facing travel narration.",
            "acceptanceEvidence": "bgm_audio_contract, audience_caption_contract, and story_style_contract pass with dense viewer-facing captions.",
        },
    ),
    (
        ("Ending", "aftertaste", "abrupt"),
        {
            "area": "ending_aftertaste",
            "priority": "P1",
            "ownerScript": "prepare_visual_establishing_plan.py",
            "requiredArtifact": "visual_establishing_plan/visual_establishing_plan.json",
            "repairAction": "End on route aftertaste: departure, night city, road, train/plane/ferry, quiet scenic wide, final reaction, or route callback plus clean title/credit.",
            "acceptanceEvidence": "director intent ending check passes and final contact sheet shows a scenic/route-aware ending rather than a leftover clip.",
        },
    ),
    (
        ("Upstream technical", "Existing technical", "QA"),
        {
            "area": "qa_chain",
            "priority": "P0",
            "ownerScript": "run_final_qa_suite.py",
            "requiredArtifact": "final_qa_suite_report.json",
            "repairAction": "Rerun failed technical/client/story/audio/style checks after each repair and do not claim reference quality until the chain supports it.",
            "acceptanceEvidence": "reference_style_alignment, director_intent, director_polish, final QA, and strict portable package integrity all pass.",
        },
    ),
    (
        ("creator_cut_plan", "creator cut"),
        {
            "area": "lived_in_texture",
            "priority": "P1",
            "ownerScript": "prepare_creator_cut_plan.py",
            "requiredArtifact": "creator_cut_plan/creator_cut_plan.json",
            "repairAction": "Classify every selected visual clip into hero, main, texture, utility, or reject/review and demote weak clips before effects or recut.",
            "acceptanceEvidence": "creator_cut_plan has one decision row per visual clip, weak clips are reject/utility instead of leading the cut, and chapter coverage rows are present.",
        },
    ),
    (
        ("transition_grammar_plan", "transition_execution_plan"),
        {
            "area": "route_bridges",
            "priority": "P0",
            "ownerScript": "prepare_transition_grammar_plan.py",
            "requiredArtifact": "transition_grammar_plan/transition_grammar_plan.json",
            "repairAction": "Generate adjacent-pair transition decisions and execution recipes so bridge gaps, match cuts, dissolves, and motivated motion effects are explicit.",
            "acceptanceEvidence": "transition grammar and execution plans both exist; bridge-missing rows stay blocked until real route bridge footage exists.",
        },
    ),
)


def load_json(path: Path | None) -> Any | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_text(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def plan_summary(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("summary"), dict):
        return data["summary"]
    return {}


def find_reference_analysis(package_dir: Path, explicit: str | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend(
        [
            package_dir / "reference" / "reference_analysis.json",
            package_dir / "reference" / "reference_batch_profile.json",
        ]
    )
    return next((path.resolve() for path in candidates if path.exists()), None)


def reference_targets(reference_path: Path | None) -> dict[str, Any]:
    targets = dict(DEFAULT_REFERENCE_TARGETS)
    data = load_json(reference_path) if reference_path else None
    if not isinstance(data, dict):
        targets["referenceAnalysis"] = str(reference_path) if reference_path else None
        targets["profileAvailable"] = False
        return targets
    pacing = data.get("pacingProfile") if isinstance(data.get("pacingProfile"), dict) else {}
    audio = data.get("audioProfile") if isinstance(data.get("audioProfile"), dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    avg = pacing.get("averageShotLengthSeconds")
    median = pacing.get("medianShotLengthSeconds")
    targets.update(
        {
            "source": "local_reference_analysis",
            "referenceAnalysis": str(reference_path),
            "profileAvailable": True,
            "durationMinutes": summary.get("durationMinutes") or data.get("durationMinutes"),
            "averageShotLengthSeconds": avg if avg else targets["averageShotLengthSeconds"],
            "medianShotLengthSeconds": median if median else targets["medianShotLengthSeconds"],
            "estimatedShotCount": pacing.get("estimatedShotCount"),
            "longShotCountOver20s": pacing.get("longShotCountOver20s"),
            "shortShotCountUnder3s": pacing.get("shortShotCountUnder3s"),
            "audioMeanVolumeDb": audio.get("meanVolumeDb") if audio.get("meanVolumeDb") is not None else targets["audioMeanVolumeDb"],
            "sampleFrameCount": len(data.get("sampleFrames") or []) if isinstance(data.get("sampleFrames"), list) else None,
            "contactSheet": data.get("contactSheet"),
        }
    )
    return targets


def blocked_checks(report: dict[str, Any], source: str) -> list[dict[str, Any]]:
    rows = report.get("checks") if isinstance(report.get("checks"), list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("status") == "blocked":
            out.append(
                {
                    "source": source,
                    "name": clean_text(row.get("name")),
                    "status": row.get("status"),
                    "evidence": row.get("evidence") if isinstance(row.get("evidence"), dict) else {},
                }
            )
    for blocker in report.get("blockers") or []:
        name = clean_text(blocker)
        if name and not any(row["name"] == name and row["source"] == source for row in out):
            out.append({"source": source, "name": name, "status": "blocked", "evidence": {}})
    return out


def match_template(name: str) -> dict[str, Any]:
    lower = name.lower()
    for needles, template in CHECK_TO_REPAIR:
        if any(str(needle).lower() in lower for needle in needles):
            return dict(template)
    return {
        "area": "reference_style_gap",
        "priority": "P1",
        "ownerScript": "audit_reference_style_alignment.py",
        "requiredArtifact": "reference_style_alignment_audit.json",
        "repairAction": "Inspect the blocked check and repair the underlying structure, footage choice, audio, caption, transition, or QA artifact before claiming reference-style quality.",
        "acceptanceEvidence": "The originating blocked check passes on rerun and the repair row has readback/render-frame evidence.",
    }


def repair_row(index: int, blocked: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    evidence = blocked.get("evidence") if isinstance(blocked.get("evidence"), dict) else {}
    return {
        "rowIndex": index,
        "sourceAudit": blocked.get("source"),
        "blockedCheck": blocked.get("name"),
        "area": template["area"],
        "priority": template["priority"],
        "ownerScript": template["ownerScript"],
        "requiredArtifact": template["requiredArtifact"],
        "repairAction": template["repairAction"],
        "acceptanceEvidence": template["acceptanceEvidence"],
        "evidenceSnippet": clean_text(json.dumps(evidence, ensure_ascii=False), 800),
        "referenceRule": reference_rule_for_area(template["area"]),
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
        "decision": dict(DECISION_FIELDS),
    }


def reference_rule_for_area(area: str) -> str:
    rules = {
        "reference_profile": "Study full-film timeline strips, opening, ending, scene-cut pacing, audio continuity, and sample frames; do not copy assets.",
        "longform_structure": "Keep the film sustained by real route footage, not padding.",
        "route_arc": "The route should read as arrival, movement, exploration, and closure.",
        "route_bridges": "Bridge places with physical route evidence before using visual effects.",
        "lived_in_texture": "Balance landmarks with street, shop, hotel, food, waiting, signs, and human/context texture.",
        "shot_pacing": "Use many short connective beats, 4-9 second story beats, and only a few valuable breathing shots.",
        "opening_title": "Use a high-recognition establishing background and one clean oversized destination title.",
        "audio_caption_story": "Use BGM plus audience-facing captions to carry story when voiceover is rejected.",
        "ending_aftertaste": "End after the main experience with route aftertaste, not an abrupt leftover clip.",
        "qa_chain": "Reference quality is only credible after the technical, style, feedback, and package gates support it.",
    }
    return rules.get(area, "Use the Parallel World/Malta references as a non-copying quality bar.")


def artifact_status(package_dir: Path) -> dict[str, Any]:
    artifacts = {
        "openingStory": package_dir / "opening_story_plan" / "opening_story_plan.json",
        "editRhythm": package_dir / "edit_rhythm_plan" / "edit_rhythm_plan.json",
        "creatorCut": package_dir / "creator_cut_plan" / "creator_cut_plan.json",
        "transitionGrammar": package_dir / "transition_grammar_plan" / "transition_grammar_plan.json",
        "transitionExecution": package_dir / "transition_execution_plan" / "transition_execution_plan.json",
        "rhythmRecut": package_dir / "rhythm_recut_blueprint" / "rhythm_recut_blueprint_report.json",
        "referenceStyleAudit": package_dir / "reference_style_alignment_audit.json",
        "directorIntentAudit": package_dir / "director_intent_contract_audit.json",
        "directorPolishAudit": package_dir / "director_polish_contract_audit.json",
    }
    out = {}
    for name, path in artifacts.items():
        data = load_json(path) or {}
        out[name] = {
            "exists": path.exists(),
            "status": data.get("status"),
            "summary": plan_summary(data),
        }
    return out


def seeded_setup_rows(package_dir: Path, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    required = [
        ("openingStory", "opening_story_plan/opening_story_plan.json", "prepare_opening_story_plan.py", "opening_title"),
        ("editRhythm", "edit_rhythm_plan/edit_rhythm_plan.json", "prepare_edit_rhythm_plan.py", "shot_pacing"),
        ("creatorCut", "creator_cut_plan/creator_cut_plan.json", "prepare_creator_cut_plan.py", "lived_in_texture"),
        ("transitionGrammar", "transition_grammar_plan/transition_grammar_plan.json", "prepare_transition_grammar_plan.py", "route_bridges"),
        ("transitionExecution", "transition_execution_plan/transition_execution_plan.json", "prepare_transition_execution_plan.py", "route_bridges"),
        ("rhythmRecut", "rhythm_recut_blueprint/resolve_timeline_blueprint_rhythm_recut.json", "prepare_rhythm_recut_blueprint.py", "shot_pacing"),
    ]
    rows = []
    for name, artifact, script, area in required:
        info = artifacts.get(name) or {}
        if info.get("exists"):
            continue
        rows.append(
            {
                "source": "reference_style_repair_preflight",
                "name": f"Missing {artifact}",
                "status": "blocked",
                "evidence": {"packageDir": str(package_dir), "artifact": artifact, "ownerScript": script, "area": area},
            }
        )
    return rows


def build_plan(package_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    package_dir = package_dir.expanduser().resolve()
    reference_path = find_reference_analysis(package_dir, args.reference_analysis)
    targets = reference_targets(reference_path)
    reference_audit = load_json(package_dir / "reference_style_alignment_audit.json") or {}
    director_intent = load_json(package_dir / "director_intent_contract_audit.json") or {}
    director_polish = load_json(package_dir / "director_polish_contract_audit.json") or {}
    final_qa = load_json(package_dir / "final_qa_suite_report.json") or {}
    artifacts = artifact_status(package_dir)

    blocked = []
    blocked.extend(blocked_checks(reference_audit, "reference_style_alignment_audit"))
    blocked.extend(blocked_checks(director_intent, "director_intent_contract_audit"))
    blocked.extend(blocked_checks(director_polish, "director_polish_contract_audit"))
    blocked.extend(blocked_checks(final_qa, "final_qa_suite_report"))
    blocked.extend(seeded_setup_rows(package_dir, artifacts))

    seen: set[tuple[str, str]] = set()
    unique_blocked = []
    for item in blocked:
        key = (str(item.get("source")), str(item.get("name")))
        if key in seen:
            continue
        seen.add(key)
        unique_blocked.append(item)

    rows = [repair_row(index + 1, item, match_template(item.get("name") or "")) for index, item in enumerate(unique_blocked)]
    priority_counts: dict[str, int] = {}
    area_counts: dict[str, int] = {}
    for row in rows:
        priority_counts[row["priority"]] = priority_counts.get(row["priority"], 0) + 1
        area_counts[row["area"]] = area_counts.get(row["area"], 0) + 1

    if rows:
        status = "ready_with_reference_style_repair_plan"
    elif reference_audit.get("status") == "passed" and director_intent.get("status") in {"passed", "passed_with_warnings"}:
        status = "ready_no_reference_style_repairs_needed"
    else:
        status = "ready_with_reference_style_repair_plan"
        rows = [
            repair_row(
                1,
                {
                    "source": "reference_style_repair_preflight",
                    "name": "Reference-style audits have not been run yet",
                    "status": "blocked",
                    "evidence": {"packageDir": str(package_dir)},
                },
                {
                    "area": "qa_chain",
                    "priority": "P0",
                    "ownerScript": "audit_reference_style_alignment.py",
                    "requiredArtifact": "reference_style_alignment_audit.json",
                    "repairAction": "Run reference-style, director-intent, and director-polish audits after the package has enough timeline/audio/subtitle evidence.",
                    "acceptanceEvidence": "All three audits exist; blocked checks are converted into concrete repair rows.",
                },
            )
        ]
        priority_counts = {"P0": 1}
        area_counts = {"qa_chain": 1}

    return {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "packageDir": str(package_dir),
        "referenceTargets": targets,
        "inputs": {
            "referenceAnalysis": str(reference_path) if reference_path else None,
            "referenceStyleAudit": str(package_dir / "reference_style_alignment_audit.json"),
            "directorIntentAudit": str(package_dir / "director_intent_contract_audit.json"),
            "directorPolishAudit": str(package_dir / "director_polish_contract_audit.json"),
            "finalQaSuite": str(package_dir / "final_qa_suite_report.json"),
        },
        "artifactStatus": artifacts,
        "summary": {
            "repairRowCount": len(rows),
            "p0RepairRowCount": priority_counts.get("P0", 0),
            "areaCounts": area_counts,
            "rowsWithDecisionFields": sum(1 for row in rows if set(DECISION_FIELDS).issubset(set((row.get("decision") or {}).keys()))),
            "safeNoWriteRows": sum(1 for row in rows if (row.get("safety") or {}).get("writesResolve") is False),
            "referenceProfileAvailable": bool(targets.get("profileAvailable")),
            "referenceAverageShotLengthSeconds": targets.get("averageShotLengthSeconds"),
            "referenceMedianShotLengthSeconds": targets.get("medianShotLengthSeconds"),
        },
        "repairRows": rows,
        "selectionRubric": {
            "pass": [
                "Every blocked reference/director/QA check has an exact repair row.",
                "Every repair row names the owner script, required artifact, acceptance evidence, and post-repair audit.",
                "Shot pacing, opening/title, route bridge, audio/caption, and ending issues map to concrete Skill artifacts.",
                "The plan does not write Resolve, queue renders, download assets, or modify source footage.",
            ],
            "reject": [
                "Generic advice such as 'make it better' without script and evidence.",
                "Repair row that hides weak footage with flashy effects.",
                "Claiming reference style without rerunning reference/director/QA audits after repair.",
            ],
        },
        "nextActions": [
            "Execute P0 rows first, then rerun the originating audits.",
            "When a rhythm recut candidate is accepted, fork a recut apply package before Resolve writes.",
            "After Resolve apply, fill readback/frame-sample decision fields and rerun director polish plus final QA.",
        ],
        "safety": {
            "writesResolve": False,
            "queuesRender": False,
            "downloadsExternalAssets": False,
            "modifiesSourceFootage": False,
        },
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Reference Style Repair Plan",
        "",
        f"Status: `{plan['status']}`",
        f"Package: `{plan['packageDir']}`",
        "",
        "## Reference Targets",
        "",
        "```json",
        json.dumps(plan["referenceTargets"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(plan["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Repair Rows",
    ]
    for row in plan["repairRows"][:160]:
        lines.extend(
            [
                "",
                f"### Row {row.get('rowIndex')}: {row.get('area')} / {row.get('priority')}",
                f"- Source audit: `{row.get('sourceAudit')}`",
                f"- Blocked check: {row.get('blockedCheck')}",
                f"- Owner script: `{row.get('ownerScript')}`",
                f"- Required artifact: `{row.get('requiredArtifact')}`",
                f"- Repair action: {row.get('repairAction')}",
                f"- Acceptance evidence: {row.get('acceptanceEvidence')}",
                f"- Reference rule: {row.get('referenceRule')}",
                "- Decision fields to fill:",
            ]
        )
        for key in DECISION_FIELDS:
            lines.append(f"  - {key}: ")
    lines.extend(["", "## Selection Rubric", "", "Pass:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["pass"])
    lines.extend(["", "Reject:"])
    lines.extend(f"- {item}" for item in plan["selectionRubric"]["reject"])
    lines.extend(["", "## Next Actions"])
    lines.extend(f"- {item}" for item in plan["nextActions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a reference-style repair plan from package audits.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--reference-analysis", help="Optional reference_analysis.json path.")
    parser.add_argument("--output-dir", help="Defaults to <package>/reference_style_repair_plan.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    package_dir = Path(args.package_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else package_dir / "reference_style_repair_plan"
    plan = build_plan(package_dir, args)
    write_json(output_dir / "reference_style_repair_plan.json", plan)
    write_markdown(output_dir / "reference_style_repair_plan.md", plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"status": plan["status"], "outputDir": str(output_dir), "summary": plan["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
