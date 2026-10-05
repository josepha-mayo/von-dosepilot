#!/usr/bin/env python3
"""Verify the clean isolated execution of the current finalist package."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CleanCurrentFinalistPackageExecutionError(ValueError):
    pass


EXPECTED_PUBLIC_COMMIT = "64424e9c0a8c158e47300398f892b2ec148ed7de"
EXPECTED_PUBLIC_TREE = "7ffe0b761f8e02ad8b784a653fac489538c7198a"
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
        raise CleanCurrentFinalistPackageExecutionError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("clean_current_finalist_package_execution")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(
        receipt.get("schema")
        == "dosepilot.clean_current_finalist_package_execution.v1",
        "SCHEMA",
    )
    require(receipt.get("status") == "PASS", "STATUS")
    require(
        receipt.get("role")
        == "CLEAN_ISOLATED_CURRENT_FINALIST_PACKAGE_EXECUTION",
        "ROLE",
    )

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(
        load(predecessor_path).get("schema")
        == "dosepilot.clean_finalist_package_execution.v1",
        "PREDECESSOR_SCHEMA",
    )
    require(predecessor.get("preserved_unchanged") is True, "PREDECESSOR_PRESERVED")

    source = receipt.get("source", {})
    require(source.get("public_commit") == EXPECTED_PUBLIC_COMMIT, "SOURCE_COMMIT")
    require(source.get("public_tree") == EXPECTED_PUBLIC_TREE, "SOURCE_TREE")
    require(source.get("archive_tree") == EXPECTED_PUBLIC_TREE, "ARCHIVE_TREE")
    require(source.get("archive_file_count") == 439, "ARCHIVE_FILE_COUNT")
    require(
        source.get("archive_sha256")
        == "5ec2b0430824399f691739c8b5bbc7082b9c2fdb6c5ba59967f271fc70ad7b49",
        "ARCHIVE_HASH",
    )
    require(source.get("archive_bytes") == 3921920, "ARCHIVE_BYTES")
    require(source.get("fresh_source_directory") is True, "FRESH_SOURCE_DIRECTORY")
    require(source.get("fresh_public_clone") is False, "NOT_PUBLIC_CLONE")

    environment = receipt.get("environment", {})
    require(environment.get("python") == "3.12.14", "PYTHON_VERSION")
    require(environment.get("pip") == "25.0.1", "PIP_VERSION")
    require(environment.get("operating_system") == "Ubuntu 24.04", "OPERATING_SYSTEM")
    require(environment.get("architecture") == "x86_64", "ARCHITECTURE")
    require(environment.get("glibc") == "2.39", "GLIBC")
    require(environment.get("fresh_virtual_environment") is True, "FRESH_VENV")
    require(
        environment.get("pip_artifacts_resolved_from_cache") is True,
        "PIP_CACHE",
    )
    require(environment.get("installed_packages") == EXPECTED_PACKAGES, "PACKAGE_VERSIONS")
    require(
        environment.get("installed_package_manifest_sha256")
        == "e2eadc914d499096dcc649c03200ee9e4e644c9d9d39cc4b0e6b1be30fa45724",
        "PACKAGE_MANIFEST_HASH",
    )

    requirements = receipt.get("requirements", {})
    for relative, expected in requirements.items():
        require(sha(root / relative) == expected, "REQUIREMENTS_HASH: " + relative)
    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    execution = receipt.get("execution", {})
    require(
        execution.get("command")
        == [
            ".venv/bin/python",
            "study/audits/finalist_package_preflight_current.py",
            "--output",
            "finalist_package_preflight_current.json",
        ],
        "COMMAND",
    )
    require(execution.get("status") == "PASS", "EXECUTION_STATUS")
    require(execution.get("package_checks") == 8, "PACKAGE_CHECKS")
    require(execution.get("current_rubric_successor_checked") is True, "CURRENT_RUBRIC")
    require(execution.get("canonical_release_stages") == 14, "CANONICAL_STAGES")
    require(execution.get("canonical_orchestrated_tests") == 173, "CANONICAL_TESTS")
    require(execution.get("package_runner_network_requests") == 0, "RUNNER_NETWORK")
    require(execution.get("output_bytes") == 9066, "OUTPUT_BYTES")
    require(
        execution.get("output_sha256")
        == "90f5cda3ae64ce61f4a82cdcae0f569410bcfad920bbcb7c7b07ca406e08f571",
        "OUTPUT_HASH",
    )
    require(
        execution.get("canonical_preflight_sha256")
        == "c2e108d7da66b095aec21fbcaf6b1b012e6603e9f537c9b6d319990b64df6a63",
        "CANONICAL_HASH",
    )

    scope = receipt.get("claim_boundary", {})
    for key in (
        "clean_new_machine_certification",
        "independent_biological_validation",
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

    for key, expected in (
        ("status", "PASS"),
        ("public_commit", EXPECTED_PUBLIC_COMMIT),
        ("public_tree", EXPECTED_PUBLIC_TREE),
        ("fresh_virtual_environment", True),
        ("package_checks", 8),
        ("current_rubric_successor_checked", True),
        ("canonical_release_stages", 14),
        ("canonical_orchestrated_tests", 173),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "public_commit": EXPECTED_PUBLIC_COMMIT,
        "public_tree": EXPECTED_PUBLIC_TREE,
        "fresh_virtual_environment": True,
        "package_checks": 8,
        "current_rubric_successor_checked": True,
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
