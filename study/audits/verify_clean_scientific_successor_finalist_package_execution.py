#!/usr/bin/env python3
"""Verify the clean isolated scientific-successor package execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CleanScientificSuccessorFinalistPackageExecutionError(ValueError):
    pass


EXPECTED_PUBLIC_COMMIT = "f9090a2b75ffbc3639006ecc9298b7f217b6f78b"
EXPECTED_PUBLIC_TREE = "de6a12b3d3f6cbaa008b983756a28a03572ecbc5"
EXPECTED_PACKAGES = {
    "joblib": "1.5.3",
    "numpy": "2.3.5",
    "pandas": "2.2.3",
    "python-dateutil": "2.9.0.post0",
    "pytz": "2026.5",
    "scikit-learn": "1.8.0",
    "scipy": "1.17.0",
    "six": "1.17.0",
    "threadpoolctl": "3.6.0",
    "tzdata": "2026.5",
}


def require(condition, label):
    if not condition:
        raise CleanScientificSuccessorFinalistPackageExecutionError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("clean_scientific_successor_finalist_package_execution")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(
        receipt.get("schema")
        == "dosepilot.clean_scientific_successor_finalist_package_execution.v1",
        "SCHEMA",
    )
    require(receipt.get("status") == "PASS", "STATUS")
    require(
        receipt.get("role")
        == "CLEAN_ISOLATED_SCIENTIFIC_SUCCESSOR_FINALIST_PACKAGE_EXECUTION",
        "ROLE",
    )

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(
        load(predecessor_path).get("schema")
        == "dosepilot.clean_retrieval_bound_finalist_package_execution.v1",
        "PREDECESSOR_SCHEMA",
    )
    require(predecessor.get("preserved_unchanged") is True, "PREDECESSOR_PRESERVED")

    source = receipt.get("source", {})
    require(source.get("public_commit") == EXPECTED_PUBLIC_COMMIT, "SOURCE_COMMIT")
    require(source.get("public_tree") == EXPECTED_PUBLIC_TREE, "SOURCE_TREE")
    require(source.get("archive_tree") == EXPECTED_PUBLIC_TREE, "ARCHIVE_TREE")
    require(source.get("archive_file_count") == 597, "ARCHIVE_FILE_COUNT")
    require(source.get("archive_bytes") == 5386240, "ARCHIVE_BYTES")
    require(
        source.get("archive_sha256")
        == "dfb62c36d449fd8118746fdb9028b0b99aec2b60e56140b8b70d8f51e68afef9",
        "ARCHIVE_HASH",
    )
    require(source.get("fresh_source_directory") is True, "FRESH_SOURCE_DIRECTORY")
    require(source.get("fresh_public_clone") is False, "NOT_PUBLIC_CLONE")

    environment = receipt.get("environment", {})
    require(environment.get("python") == "3.12.14", "PYTHON_VERSION")
    require(environment.get("pip") == "25.0.1", "PIP_VERSION")
    require(environment.get("operating_system") == "Ubuntu 24.04", "OPERATING_SYSTEM")
    require(environment.get("kernel") == "Linux 6.18.44", "KERNEL")
    require(environment.get("architecture") == "x86_64", "ARCHITECTURE")
    require(environment.get("glibc") == "2.39", "GLIBC")
    require(environment.get("fresh_virtual_environment") is True, "FRESH_VENV")
    require(environment.get("pip_artifacts_resolved_from_cache") is True, "PIP_CACHE")
    require(
        environment.get("live_dependency_download_claimed") is False,
        "NO_LIVE_DOWNLOAD_CLAIM",
    )
    require(environment.get("installed_packages") == EXPECTED_PACKAGES, "PACKAGE_VERSIONS")
    require(
        environment.get("installed_package_manifest_sha256")
        == "02e6c6917e82981079c348f34540e04a657660e242833a9b183ac9069a6c0ee7",
        "PACKAGE_MANIFEST_HASH",
    )

    for relative, expected in receipt.get("requirements", {}).items():
        require(sha(root / relative) == expected, "REQUIREMENTS_HASH: " + relative)
    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    execution = receipt.get("execution", {})
    require(
        execution.get("command")
        == [
            ".venv/bin/python",
            "study/audits/finalist_package_preflight_scientific_successor.py",
            "--output",
            "finalist_package_preflight_scientific_successor.json",
        ],
        "COMMAND",
    )
    require(execution.get("status") == "PASS", "EXECUTION_STATUS")
    require(execution.get("package_checks") == 8, "PACKAGE_CHECKS")
    require(
        execution.get("current_scientific_successor_rubric_checked") is True,
        "SCIENTIFIC_RUBRIC",
    )
    require(
        execution.get("candidate_family")
        == "orientation_specific_control_quality_rank1",
        "CANDIDATE_FAMILY",
    )
    require(execution.get("candidate_mse") == 0.001042745722096212, "CANDIDATE_MSE")
    require(execution.get("bandwidth07_patient_wins") == 40, "CANDIDATE_PATIENTS")
    require(execution.get("favorable_folds") == 5, "CANDIDATE_FOLDS")
    require(execution.get("target_wins") == 19, "CANDIDATE_TARGETS")
    require(execution.get("repeated_development") is True, "REPEATED_DEVELOPMENT")
    require(
        execution.get("operational_demo_baseline_replaced") is False,
        "NO_OPERATIONAL_REPLACEMENT",
    )
    require(execution.get("independent_validation") is False, "NO_VALIDATION")
    require(execution.get("canonical_release_stages") == 14, "CANONICAL_STAGES")
    require(execution.get("canonical_orchestrated_tests") == 173, "CANONICAL_TESTS")
    require(execution.get("package_runner_network_requests") == 0, "RUNNER_NETWORK")
    require(execution.get("output_bytes") == 10611, "OUTPUT_BYTES")
    require(
        execution.get("output_sha256")
        == "23ca36516634e8896619be78d77f92e1a497e13290dcd87967a86fe4723e02ee",
        "OUTPUT_HASH",
    )
    require(
        execution.get("canonical_preflight_sha256")
        == "5298f5132b95289a7cbab061f6d6352f9af6059d0e0437f8347d36227b84b101",
        "CANONICAL_HASH",
    )

    scope = receipt.get("claim_boundary", {})
    for key in (
        "clean_new_machine_certification",
        "independent_biological_validation",
        "independent_reproduction",
        "bootstrap_independently_recomputed",
        "prospective_ooc_evidence",
        "private_or_protected_inputs_read",
        "source_workbook_read",
        "model_fit_created",
        "biological_accuracy_result_created",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
    ):
        require(scope.get(key) is False, "BOUNDARY_" + key.upper())
    require(scope.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    expected_record = (
        ("status", "PASS"),
        ("public_commit", EXPECTED_PUBLIC_COMMIT),
        ("public_tree", EXPECTED_PUBLIC_TREE),
        ("fresh_virtual_environment", True),
        ("pip_artifacts_resolved_from_cache", True),
        ("live_dependency_download_claimed", False),
        ("package_checks", 8),
        ("current_scientific_successor_rubric_checked", True),
        ("candidate_mse", 0.001042745722096212),
        ("bandwidth07_patient_wins", 40),
        ("favorable_folds", 5),
        ("target_wins", 19),
        ("repeated_development", True),
        ("operational_demo_baseline_replaced", False),
        ("independent_validation", False),
        ("canonical_release_stages", 14),
        ("canonical_orchestrated_tests", 173),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    )
    for key, expected in expected_record:
        require(record.get(key) == expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "public_commit": EXPECTED_PUBLIC_COMMIT,
        "public_tree": EXPECTED_PUBLIC_TREE,
        "fresh_virtual_environment": True,
        "pip_artifacts_resolved_from_cache": True,
        "live_dependency_download_claimed": False,
        "package_checks": 8,
        "current_scientific_successor_rubric_checked": True,
        "candidate_mse": 0.001042745722096212,
        "bandwidth07_patient_wins": 40,
        "favorable_folds": 5,
        "target_wins": 19,
        "repeated_development": True,
        "operational_demo_baseline_replaced": False,
        "independent_validation": False,
        "canonical_release_stages": 14,
        "canonical_orchestrated_tests": 173,
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
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
