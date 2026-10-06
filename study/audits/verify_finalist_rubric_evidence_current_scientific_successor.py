#!/usr/bin/env python3
"""Verify the scientific-successor finalist-rubric evidence successor."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from verify_current_scientific_successor_evidence import (
    CurrentScientificSuccessorEvidenceError,
    verify as verify_scientific_successor,
)


class CurrentScientificSuccessorRubricEvidenceError(ValueError):
    pass


EXPECTED_WEIGHTS = {
    "problem_importance_impact": 30,
    "technical_approach_innovation": 30,
    "results_validation": 20,
    "reproducibility_implementation": 10,
    "presentation": 10,
}

EXPECTED_BINDINGS = {
    "predecessor": {
        "path": "evidence/finalist_rubric_evidence_r6_20261006.json",
        "sha256": "62031d0fcd4897447b8bc2123113227ca97d5dfd89e6415e58ec167a76399e36",
    },
    "current_scientific_successor": {
        "path": "evidence/current_scientific_successor_evidence_20261006.json",
        "sha256": "ba3b1546bee6267b6ea31e973bb572112427499a659ff9e8dc98202b5725c90c",
    },
}


def load(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(actual, expected, label):
    if actual != expected:
        raise CurrentScientificSuccessorRubricEvidenceError(label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_scientific_successor_finalist_rubric_evidence")
    same(isinstance(record, dict), True, "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    same(receipt_path.name, "finalist_rubric_evidence_r7_20261006.json", "INDEX_PATH")
    same(sha256(receipt_path), record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    same(receipt.get("schema"), "dosepilot.finalist_rubric_evidence.v7", "SCHEMA")
    same(receipt.get("status"), "PASS", "STATUS")
    same(receipt.get("as_of_date"), "2026-10-06", "DATE")
    same(receipt.get("role"), "CURRENT_SCIENTIFIC_SUCCESSOR_JUDGE_CRITERION_EVIDENCE", "ROLE")
    same(receipt.get("evidence_bindings"), EXPECTED_BINDINGS, "EVIDENCE_BINDINGS")
    for binding in EXPECTED_BINDINGS.values():
        same(sha256(root / binding["path"]), binding["sha256"], "BINDING_HASH: " + binding["path"])

    predecessor = load(root / EXPECTED_BINDINGS["predecessor"]["path"])
    same(predecessor["schema"], "dosepilot.finalist_rubric_evidence.v6", "PREDECESSOR_SCHEMA")
    same(predecessor["status"], "PASS", "PREDECESSOR_STATUS")
    same(predecessor["rubric"]["weights"], EXPECTED_WEIGHTS, "PREDECESSOR_WEIGHTS")
    same(predecessor["rubric"]["combined_self_score"], None, "PREDECESSOR_NO_SCORE")
    same(predecessor["presentation_retrieval_successor"]["public_repository_file_bytes_retrieved"], True, "PREDECESSOR_RETRIEVAL")
    same(predecessor["claim_boundary"]["independent_validation_created"], False, "PREDECESSOR_NO_VALIDATION")

    try:
        scientific = verify_scientific_successor(root)
    except CurrentScientificSuccessorEvidenceError as exc:
        raise CurrentScientificSuccessorRubricEvidenceError("SCIENTIFIC_SUCCESSOR: " + str(exc)) from exc
    same(scientific["candidate_mse"], 0.001042745722096212, "SCIENTIFIC_MSE")
    same(scientific["candidate_p90"], 0.037419695944064885, "SCIENTIFIC_P90")
    same(scientific["bandwidth07_patient_wins"], 40, "SCIENTIFIC_PATIENTS")
    same(scientific["favorable_folds"], 5, "SCIENTIFIC_FOLDS")
    same(scientific["target_wins"], 19, "SCIENTIFIC_TARGET_WINS")
    same(scientific["target_losses"], 5, "SCIENTIFIC_TARGET_LOSSES")
    same(scientific["independent_validation"], False, "SCIENTIFIC_NO_VALIDATION")
    same(scientific["protected22_access"], False, "SCIENTIFIC_NO_PROTECTED22")

    rubric = receipt["rubric"]
    same(rubric["weights"], EXPECTED_WEIGHTS, "WEIGHTS")
    same(sum(rubric["weights"].values()), 100, "WEIGHT_SUM")
    same(rubric["combined_self_score"], None, "NO_SELF_SCORE")
    same(rubric["finalist_probability_estimate"], None, "NO_FINALIST_PROBABILITY")
    same(rubric["last_verified_on_platform"], "2026-10-01", "PLATFORM_DATE")
    same(rubric["current_run_public_retrieval"], "NOT_ATTEMPTED_NO_REFRESH_CLAIM", "NO_REFRESH")

    successor = receipt["scientific_successor"]
    same(successor["family_id"], "orientation_specific_control_quality_rank1", "FAMILY")
    same(successor["mse"], scientific["candidate_mse"], "SUCCESSOR_MSE")
    same(successor["p90_patient_rmse"], scientific["candidate_p90"], "SUCCESSOR_P90")
    same(successor["patient_wins_vs_bandwidth07"], 40, "SUCCESSOR_PATIENTS")
    same(successor["favorable_folds_vs_bandwidth07"], 5, "SUCCESSOR_FOLDS")
    same(successor["target_average_wins_vs_bandwidth07"], 19, "SUCCESSOR_TARGETS")
    same(successor["immediate_predecessor_patient_wins"], 32, "SUCCESSOR_PREVIOUS_PATIENTS")
    same(successor["immediate_predecessor_favorable_folds"], 3, "SUCCESSOR_PREVIOUS_FOLDS")
    same(successor["repeated_adaptive_development"], True, "SUCCESSOR_DEVELOPMENT")
    same(successor["operational_demo_baseline_replaced"], False, "SUCCESSOR_NO_OPERATIONAL_REPLACEMENT")

    limitations = receipt["limitations"]
    for key in (
        "bootstrap_independently_recomputed", "bootstrap_confirmatory", "windows_replay_machine_receipt_public",
        "windows_replay_independently_reproduced", "independent_validation", "protected22_access",
        "accepted_kaggle_entry_changed", "netlify_changed", "finalist_status_claimed",
    ):
        same(limitations[key], False, "LIMITATION: " + key)
    same(limitations["official_competition_score"], None, "NO_OFFICIAL_SCORE")

    for relative, digest in receipt["artifact_sha256"].items():
        same(sha256(root / relative), digest, "ARTIFACT_HASH: " + relative)

    doc = (root / "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT_SCIENTIFIC_SUCCESSOR.md").read_text()
    for phrase in (
        "30% — Problem importance and impact", "30% — Technical approach and innovation",
        "20% — Results and validation", "10% — Reproducibility and implementation",
        "10% — Presentation", "0.001042745722096212", "40/59 patient",
        "5/5 favorable", "19/24 target-average", "post-hoc and selection-naive",
        "no separate immutable", "Protected22/Lib2 was not accessed", "not independent validation",
    ):
        if phrase not in doc:
            raise CurrentScientificSuccessorRubricEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

    for key, expected in (
        ("status", "PASS"), ("criteria", 5), ("weight_sum", 100),
        ("candidate_family", "orientation_specific_control_quality_rank1"),
        ("candidate_mse", 0.001042745722096212), ("bandwidth07_patient_wins", 40),
        ("favorable_folds", 5), ("target_wins", 19), ("repeated_development", True),
        ("independent_validation", False), ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        same(record.get(key), expected, "INDEX_" + key.upper())

    return {
        "status": "PASS", "criteria": 5, "weight_sum": 100,
        "candidate_family": "orientation_specific_control_quality_rank1",
        "candidate_mse": 0.001042745722096212, "bandwidth07_patient_wins": 40,
        "favorable_folds": 5, "target_wins": 19, "repeated_development": True,
        "operational_demo_baseline_replaced": False, "independent_validation": False,
        "accepted_kaggle_entry_changed": False, "official_competition_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
