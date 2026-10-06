#!/usr/bin/env python3
"""Verify the scientific-successor finalist-package preflight receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class ScientificSuccessorFinalistPackagePreflightError(ValueError):
    pass


EXPECTED_CHECKS = [
    "current_release_preflight", "downloaded_trace_self_test", "downloaded_trace_receipt",
    "reviewer_routes", "reviewer_trace_discovery", "verification_chronology",
    "clean_reviewer_quickstart", "current_scientific_successor_finalist_rubric_evidence",
]


def require(condition, label):
    if not condition:
        raise ScientificSuccessorFinalistPackagePreflightError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_scientific_successor_finalist_package_preflight")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(receipt_path.name == "finalist_package_preflight_r5_20261006.json", "INDEX_PATH")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.finalist_package_preflight.v5", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "RESPONSE_FREE_CURRENT_SCIENTIFIC_SUCCESSOR_FINALIST_PACKAGE_VERIFICATION", "ROLE")

    predecessor = receipt["predecessor"]
    predecessor_path = root / predecessor["path"]
    require(sha(predecessor_path) == predecessor["sha256"], "PREDECESSOR_HASH")
    require(load(predecessor_path)["schema"] == "dosepilot.finalist_package_preflight.v4", "PREDECESSOR_SCHEMA")
    require(predecessor["preserved_unchanged"] is True, "PREDECESSOR_PRESERVED")

    rubric = receipt["current_scientific_successor_rubric"]
    rubric_path = root / rubric["path"]
    require(sha(rubric_path) == rubric["sha256"], "SCIENTIFIC_RUBRIC_HASH")
    rubric_receipt = load(rubric_path)
    require(rubric_receipt["schema"] == "dosepilot.finalist_rubric_evidence.v7", "SCIENTIFIC_RUBRIC_SCHEMA")
    require(rubric_receipt["status"] == "PASS", "SCIENTIFIC_RUBRIC_STATUS")
    require(rubric["candidate_family"] == "orientation_specific_control_quality_rank1", "CANDIDATE_FAMILY")
    require(rubric["candidate_mse"] == 0.001042745722096212, "CANDIDATE_MSE")
    require(rubric["candidate_p90"] == 0.037419695944064885, "CANDIDATE_P90")
    require(rubric["bandwidth07_patient_wins"] == 40, "CANDIDATE_PATIENTS")
    require(rubric["favorable_folds"] == 5, "CANDIDATE_FOLDS")
    require(rubric["target_wins"] == 19, "CANDIDATE_TARGETS")
    require(rubric["repeated_development"] is True, "CANDIDATE_DEVELOPMENT")
    require(rubric["independent_validation"] is False, "NO_INDEPENDENT_VALIDATION")
    require(rubric["operational_demo_baseline_replaced"] is False, "NO_OPERATIONAL_REPLACEMENT")

    checks = receipt.get("checks", [])
    require(receipt.get("failed_check") is None, "FAILED_CHECK")
    require([item.get("name") for item in checks] == EXPECTED_CHECKS, "CHECK_ORDER")
    require(all(item.get("exit_code") == 0 for item in checks), "CHECK_EXIT")
    require(receipt.get("package_check_count") == 8, "PACKAGE_CHECK_COUNT")
    require(receipt.get("postcanonical_check_count") == 7, "POSTCANONICAL_CHECK_COUNT")
    require(receipt.get("current_scientific_successor_rubric_checked") is True, "SCIENTIFIC_RUBRIC_CHECKED")
    require(receipt.get("canonical_release_check_count") == 14, "CANONICAL_STAGE_COUNT")
    require(receipt.get("canonical_orchestrated_test_count") == 173, "CANONICAL_TEST_COUNT")
    require(len(receipt.get("canonical_preflight_sha256", "")) == 64, "CANONICAL_RECEIPT_HASH")
    require(receipt.get("network_requests") == 0, "NETWORK_REQUESTS")
    require(receipt.get("canonical_receipt_rewritten") is False, "CANONICAL_RECEIPT_REWRITTEN")
    require(receipt.get("historical_v4_predecessor_preserved") is True, "HISTORICAL_V4_PRESERVED")
    require(receipt.get("operational_demo_baseline_replaced") is False, "RECEIPT_NO_OPERATIONAL_REPLACEMENT")
    for relative, expected in receipt["artifact_sha256"].items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)
    for key in (
        "private_or_protected_inputs_read", "biological_accuracy_result_created",
        "independent_validation_created", "accepted_kaggle_entry_changed", "netlify_deployment_changed",
    ):
        require(receipt.get(key) is False, "BOUNDARY_" + key.upper())
    require(receipt.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    for key, expected in (
        ("status", "PASS"), ("package_check_count", 8), ("postcanonical_check_count", 7),
        ("current_scientific_successor_rubric_checked", True),
        ("candidate_family", "orientation_specific_control_quality_rank1"),
        ("candidate_mse", 0.001042745722096212), ("bandwidth07_patient_wins", 40),
        ("favorable_folds", 5), ("target_wins", 19), ("repeated_development", True),
        ("operational_demo_baseline_replaced", False), ("independent_validation", False),
        ("canonical_release_check_count", 14), ("canonical_orchestrated_test_count", 173),
        ("network_requests", 0), ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected, "INDEX_" + key.upper())

    return {
        "status": "PASS", "package_checks": 8,
        "current_scientific_successor_rubric_checked": True,
        "candidate_family": "orientation_specific_control_quality_rank1",
        "candidate_mse": 0.001042745722096212, "bandwidth07_patient_wins": 40,
        "favorable_folds": 5, "target_wins": 19, "repeated_development": True,
        "operational_demo_baseline_replaced": False, "independent_validation": False,
        "canonical_release_stages": 14, "canonical_orchestrated_tests": 173,
        "network_requests": 0, "accepted_kaggle_entry_changed": False,
        "official_competition_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
