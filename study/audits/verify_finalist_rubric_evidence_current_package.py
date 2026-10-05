#!/usr/bin/env python3
"""Verify the current-package successor finalist-rubric evidence map."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from verify_finalist_rubric_evidence_current import (
    EXPECTED_BINDINGS as PREDECESSOR_BINDINGS,
    EXPECTED_WEIGHTS,
)


class CurrentPackageRubricEvidenceError(ValueError):
    pass


EXPECTED_BINDINGS = {
    "predecessor": {
        "path": "evidence/finalist_rubric_evidence_r2_20261005.json",
        "sha256": "bf948a727137529a7daba7fc44e125440d89faa915c06f0ad6ee9989367f600a",
    },
    "current_package_preflight": {
        "path": "evidence/finalist_package_preflight_r2_20261005.json",
        "sha256": "232e601a3e3b326e16e2d27ba767164ccec58ce5f5fe2ee2fc8a8d13700f2496",
    },
    "clean_current_package": {
        "path": "evidence/clean_current_finalist_package_execution_20261005.json",
        "sha256": "5b6bae37b328d9130ee639c7988632e561a05716761db83b674e37df61e922c3",
    },
}


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(actual, expected, label):
    if actual != expected:
        raise CurrentPackageRubricEvidenceError(label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_package_finalist_rubric_evidence")
    same(isinstance(record, dict), True, "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    same(sha(receipt_path), record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    same(receipt.get("schema"), "dosepilot.finalist_rubric_evidence.v3", "SCHEMA")
    same(receipt.get("status"), "PASS", "STATUS")
    same(receipt.get("as_of_date"), "2026-10-05", "DATE")
    same(receipt.get("role"), "CURRENT_JUDGE_CRITERION_TO_EVIDENCE_MAP", "ROLE")
    same(receipt.get("evidence_bindings"), EXPECTED_BINDINGS, "EVIDENCE_BINDINGS")
    for binding in EXPECTED_BINDINGS.values():
        same(sha(root / binding["path"]), binding["sha256"], "BINDING_HASH: " + binding["path"])

    predecessor = load(root / EXPECTED_BINDINGS["predecessor"]["path"])
    same(predecessor["schema"], "dosepilot.finalist_rubric_evidence.v2", "PREDECESSOR_SCHEMA")
    same(predecessor["status"], "PASS", "PREDECESSOR_STATUS")
    same(predecessor["rubric"]["weights"], EXPECTED_WEIGHTS, "PREDECESSOR_WEIGHTS")
    same(predecessor["rubric"]["combined_self_score"], None, "PREDECESSOR_NO_SCORE")
    same(predecessor["evidence_bindings"], PREDECESSOR_BINDINGS, "PREDECESSOR_BINDINGS")
    for binding in PREDECESSOR_BINDINGS.values():
        same(sha(root / binding["path"]), binding["sha256"], "PREDECESSOR_BINDING_HASH: " + binding["path"])
    for relative, expected in predecessor["artifact_sha256"].items():
        same(sha(root / relative), expected, "PREDECESSOR_ARTIFACT_HASH: " + relative)
    same(predecessor["claim_boundary"]["independent_validation_created"], False, "PREDECESSOR_NO_VALIDATION")
    same(predecessor["claim_boundary"]["accepted_kaggle_entry_changed"], False, "PREDECESSOR_NO_KAGGLE_CHANGE")
    same(predecessor["claim_boundary"]["official_competition_score"], None, "PREDECESSOR_NO_OFFICIAL_SCORE")

    package = load(root / EXPECTED_BINDINGS["current_package_preflight"]["path"])
    same(package["schema"], "dosepilot.finalist_package_preflight.v2", "PACKAGE_SCHEMA")
    same(package["status"], "PASS", "PACKAGE_STATUS")
    same(package["package_check_count"], 8, "PACKAGE_CHECKS")
    same(package["current_rubric_successor_checked"], True, "PACKAGE_RUBRIC_SUCCESSOR")
    same(package["canonical_release_check_count"], 14, "PACKAGE_CANONICAL_STAGES")
    same(package["canonical_orchestrated_test_count"], 173, "PACKAGE_CANONICAL_TESTS")
    same(package["network_requests"], 0, "PACKAGE_NETWORK")

    clean = load(root / EXPECTED_BINDINGS["clean_current_package"]["path"])
    same(clean["schema"], "dosepilot.clean_current_finalist_package_execution.v1", "CLEAN_SCHEMA")
    same(clean["status"], "PASS", "CLEAN_STATUS")
    same(clean["source"]["public_commit"], "64424e9c0a8c158e47300398f892b2ec148ed7de", "CLEAN_COMMIT")
    same(clean["source"]["public_tree"], "7ffe0b761f8e02ad8b784a653fac489538c7198a", "CLEAN_TREE")
    same(clean["source"]["fresh_source_directory"], True, "CLEAN_SOURCE")
    same(clean["source"]["fresh_public_clone"], False, "CLEAN_NOT_CLONE")
    same(clean["environment"]["fresh_virtual_environment"], True, "CLEAN_VENV")
    same(clean["environment"]["pip_artifacts_resolved_from_cache"], True, "CLEAN_CACHE")
    same(clean["environment"]["live_dependency_download_claimed"], False, "CLEAN_NO_DOWNLOAD_CLAIM")
    same(clean["execution"]["status"], "PASS", "CLEAN_EXECUTION")
    same(clean["execution"]["package_checks"], 8, "CLEAN_CHECKS")
    same(clean["execution"]["current_rubric_successor_checked"], True, "CLEAN_RUBRIC_SUCCESSOR")
    same(clean["execution"]["canonical_release_stages"], 14, "CLEAN_STAGES")
    same(clean["execution"]["canonical_orchestrated_tests"], 173, "CLEAN_TESTS")
    same(clean["execution"]["package_runner_network_requests"], 0, "CLEAN_NETWORK")

    for relative, expected in receipt["artifact_sha256"].items():
        same(sha(root / relative), expected, "ARTIFACT_HASH: " + relative)
    verification = receipt["verification"]
    same(verification["standalone_verifier"], "PASS", "VERIFICATION_STATUS")
    same(verification["successor_tamper_tests"], 10, "VERIFICATION_TESTS")
    same(verification["artifact_hashes_verified"], 5, "VERIFICATION_ARTIFACTS")
    same(verification["predecessor_reverified"], True, "VERIFICATION_PREDECESSOR")
    for key in ("source_workbook_opened", "patient_or_prediction_arrays_opened", "protected_response_access"):
        same(verification[key], False, "VERIFICATION_BOUNDARY: " + key)

    doc = (root / "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT_PACKAGE.md").read_text()
    required = (
        "does **not**",
        "last platform-verified values",
        "64 identified treatment measurements",
        "416 eligible treatment measurements",
        "38/59 patient wins",
        "all 5/5 outer training sets",
        "NOT_ESTIMABLE",
        "primary v2 one-command finalist-package runner",
        "current rubric successor enforced",
        "local pip cache",
        "5/5 required external reviewer routes",
        "browser download event timed out",
        "official competition score",
        "finalist status",
    )
    for phrase in required:
        if phrase not in doc:
            raise CurrentPackageRubricEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

    boundary = receipt["claim_boundary"]
    for key in (
        "new_model_fit",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "protected_response_access",
        "private_patient_arrays_read",
        "accepted_kaggle_entry_changed",
        "finalist_status_claimed",
        "prospective_ooc_performance_claimed",
        "clinical_utility_claimed",
        "realized_cost_or_time_saving_claimed",
        "future_uptime_claimed",
        "raw_pdf_download_verified",
        "clean_new_machine_certification",
        "fresh_public_clone_claimed",
        "live_dependency_download_claimed",
    ):
        same(boundary[key], False, "CLAIM_BOUNDARY: " + key)
    same(boundary["official_competition_score"], None, "BOUNDARY_NO_SCORE")

    for key, expected in (
        ("status", "PASS"),
        ("criteria", 5),
        ("weight_sum", 100),
        ("nested_outer_training_sets_selecting_07", 5),
        ("clean_current_package_checks", 8),
        ("current_rubric_successor_checked", True),
        ("external_routes_resolved", 5),
        ("public_report_render_verified", True),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        same(record.get(key), expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "criteria": 5,
        "weight_sum": 100,
        "nested_outer_training_sets_selecting_07": 5,
        "clean_current_package_checks": 8,
        "current_rubric_successor_checked": True,
        "canonical_response_free_tests": 173,
        "external_routes_resolved": 5,
        "public_report_render_verified": True,
        "protected22_primary": "NOT_ESTIMABLE",
        "accepted_kaggle_entry_changed": False,
        "official_competition_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
