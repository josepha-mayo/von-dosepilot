#!/usr/bin/env python3
"""Verify the reliability-bound scientific-successor rubric receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from verify_clean_scientific_successor_finalist_package_execution import (
    CleanScientificSuccessorFinalistPackageExecutionError,
    verify as verify_clean_execution,
)
from verify_current_successor_grouped_conformal import (
    ReliabilityError,
    verify as verify_grouped_reliability,
)
from verify_finalist_rubric_evidence_current_scientific_successor import (
    CurrentScientificSuccessorRubricEvidenceError,
    verify as verify_predecessor,
)


class CurrentScientificReliabilityRubricEvidenceError(ValueError):
    pass


EXPECTED_BINDINGS = {
    "predecessor": {
        "path": "evidence/finalist_rubric_evidence_r7_20261006.json",
        "sha256": "8d00ee4b6f2a92ea408c81423ae731a42568e3a32ed1e1790c10c088c2277323",
    },
    "grouped_reliability": {
        "path": "evidence/current_successor_grouped_conformal_20261006.json",
        "sha256": "691e5a305e4c3f2f31ce60f35a695fd401b29b104d3fb53ebb00f9ae624a5e4b",
    },
    "clean_scientific_package_execution": {
        "path": "evidence/clean_scientific_successor_finalist_package_execution_20261006.json",
        "sha256": "3fddd240bd33759a205836ae94aef0e5ea66d95c30dc37728dee3fbf4a90cfaa",
    },
}


def load(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(actual, expected, label):
    if actual != expected:
        raise CurrentScientificReliabilityRubricEvidenceError(label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_scientific_reliability_finalist_rubric_evidence")
    same(isinstance(record, dict), True, "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    same(receipt_path.name, "finalist_rubric_evidence_r8_20261006.json", "INDEX_PATH")
    same(sha256(receipt_path), record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    same(receipt.get("schema"), "dosepilot.finalist_rubric_evidence.v8", "SCHEMA")
    same(receipt.get("status"), "PASS", "STATUS")
    same(receipt.get("role"), "CURRENT_SCIENTIFIC_RELIABILITY_JUDGE_CRITERION_EVIDENCE", "ROLE")
    same(receipt.get("evidence_bindings"), EXPECTED_BINDINGS, "EVIDENCE_BINDINGS")
    for binding in EXPECTED_BINDINGS.values():
        same(sha256(root / binding["path"]), binding["sha256"], "BINDING_HASH: " + binding["path"])

    try:
        predecessor = verify_predecessor(root)
        reliability = verify_grouped_reliability(root)
        clean = verify_clean_execution(root)
    except (CurrentScientificSuccessorRubricEvidenceError, ReliabilityError,
            CleanScientificSuccessorFinalistPackageExecutionError) as exc:
        raise CurrentScientificReliabilityRubricEvidenceError("BOUND_VERIFIER: " + str(exc)) from exc

    same(predecessor["candidate_mse"], 0.001042745722096212, "PREDECESSOR_MSE")
    same(predecessor["operational_demo_baseline_replaced"], False, "PREDECESSOR_BASELINE")
    same(reliability["whole_patients"], 59, "RELIABILITY_PATIENTS")
    same(reliability["coverage_80"], 0.8100282485875706, "COVERAGE_80")
    same(reliability["coverage_90"], 0.9194915254237288, "COVERAGE_90")
    same(reliability["coverage_95"], 0.9593926553672316, "COVERAGE_95")
    same(reliability["targets_at_or_above_90"], 24, "RELIABILITY_TARGETS")
    same(reliability["independent_validation"], False, "RELIABILITY_NO_VALIDATION")
    same(clean["package_checks"], 8, "CLEAN_PACKAGE_CHECKS")
    same(clean["canonical_release_stages"], 14, "CLEAN_CANONICAL_STAGES")
    same(clean["canonical_orchestrated_tests"], 173, "CLEAN_CANONICAL_TESTS")
    same(clean["fresh_virtual_environment"], True, "CLEAN_FRESH_VENV")
    same(clean["pip_artifacts_resolved_from_cache"], True, "CLEAN_CACHE")
    same(clean["independent_validation"], False, "CLEAN_NO_VALIDATION")

    rubric = receipt["rubric"]
    same(sum(rubric["weights"].values()), 100, "WEIGHT_SUM")
    same(rubric["combined_self_score"], None, "NO_SELF_SCORE")
    same(rubric["finalist_probability_estimate"], None, "NO_FINALIST_PROBABILITY")
    evidence = receipt["scientific_reliability"]
    same(evidence["candidate_mse"], predecessor["candidate_mse"], "CANDIDATE_MSE")
    same(evidence["coverage_90"], reliability["coverage_90"], "RECEIPT_COVERAGE_90")
    same(evidence["targets_at_or_above_90"], 24, "RECEIPT_TARGETS")
    same(evidence["clean_package_checks"], 8, "RECEIPT_PACKAGE_CHECKS")
    same(evidence["clean_nested_canonical_tests"], 173, "RECEIPT_CANONICAL_TESTS")
    same(evidence["operational_demo_baseline_replaced"], False, "NO_OPERATIONAL_REPLACEMENT")

    limitations = receipt["limitations"]
    for key in (
        "grouped_reliability_confirmatory", "grouped_reliability_selection_adjusted",
        "grouped_reliability_independently_recomputed", "bootstrap_confirmatory",
        "bootstrap_independently_recomputed", "clean_new_machine_certification",
        "windows_replay_machine_receipt_public", "independent_validation",
        "protected22_access", "accepted_kaggle_entry_changed", "netlify_changed",
        "finalist_status_claimed",
    ):
        same(limitations[key], False, "LIMITATION: " + key)
    same(limitations["official_competition_score"], None, "NO_OFFICIAL_SCORE")

    for relative, digest in receipt["artifact_sha256"].items():
        same(sha256(root / relative), digest, "ARTIFACT_HASH: " + relative)

    doc = (root / "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT_SCIENTIFIC_RELIABILITY.md").read_text()
    for phrase in (
        "30% — Problem importance and impact", "0.001042745722096212",
        "0.9194915254237288", "all 24 targets", "selection-unadjusted",
        "post-hoc and selection-naive", "not a network clone",
        "separate immutable", "not independent validation",
    ):
        if phrase not in doc:
            raise CurrentScientificReliabilityRubricEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

    expected_index = {
        "status": "PASS", "criteria": 5, "weight_sum": 100,
        "candidate_family": "orientation_specific_control_quality_rank1",
        "candidate_mse": 0.001042745722096212, "coverage_90": 0.9194915254237288,
        "targets_at_or_above_90": 24, "clean_package_checks": 8,
        "repeated_development": True, "operational_demo_baseline_replaced": False,
        "independent_validation": False, "accepted_kaggle_entry_changed": False,
        "official_competition_score": None,
    }
    for key, expected in expected_index.items():
        same(record.get(key), expected, "INDEX_" + key.upper())
    return expected_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    print(json.dumps(verify(parser.parse_args().root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
