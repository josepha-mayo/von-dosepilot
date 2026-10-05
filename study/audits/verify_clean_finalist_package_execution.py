#!/usr/bin/env python3
"""Verify the clean isolated finalist-package execution receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CleanFinalistPackageExecutionError(ValueError):
    pass


EXPECTED_PUBLIC_COMMIT = "19d4ca004705581ab3b4ebd7f710a49f298caeeb"
EXPECTED_PUBLIC_TREE = "4601ff63fd1af15aa13a9daae10946502781cfbd"
EXPECTED_PACKAGES = {
    "joblib": "1.5.3",
    "numpy": "2.3.5",
    "pandas": "2.2.3",
    "pip": "25.0.1",
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
        raise CleanFinalistPackageExecutionError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("clean_finalist_package_execution")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.clean_finalist_package_execution.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "CLEAN_ISOLATED_FINALIST_PACKAGE_EXECUTION", "ROLE")

    source = receipt.get("source", {})
    require(source.get("public_commit") == EXPECTED_PUBLIC_COMMIT, "SOURCE_COMMIT")
    require(source.get("public_tree") == EXPECTED_PUBLIC_TREE, "SOURCE_TREE")
    require(source.get("archive_tree") == EXPECTED_PUBLIC_TREE, "ARCHIVE_TREE")
    require(source.get("archive_file_count") == 453, "ARCHIVE_FILE_COUNT")
    require(source.get("fresh_source_directory") is True, "FRESH_SOURCE_DIRECTORY")
    require(source.get("fresh_public_clone") is False, "NOT_PUBLIC_CLONE")

    environment = receipt.get("environment", {})
    require(environment.get("python") == "3.12.14", "PYTHON_VERSION")
    require(environment.get("operating_system") == "Ubuntu 24.04.3 LTS", "OPERATING_SYSTEM")
    require(environment.get("architecture") == "x86_64", "ARCHITECTURE")
    require(environment.get("glibc") == "2.39", "GLIBC")
    require(environment.get("fresh_virtual_environment") is True, "FRESH_VENV")
    require(environment.get("live_dependency_install") is True, "LIVE_DEPENDENCY_INSTALL")
    require(environment.get("installed_packages") == EXPECTED_PACKAGES, "PACKAGE_VERSIONS")

    requirements = receipt.get("requirements", {})
    for relative, expected in requirements.items():
        require(sha(root / relative) == expected, "REQUIREMENTS_HASH: " + relative)
    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    execution = receipt.get("execution", {})
    require(execution.get("command") == ["python3", "study/audits/finalist_package_preflight.py", "--output", "finalist_package_preflight.json"], "COMMAND")
    require(execution.get("status") == "PASS", "EXECUTION_STATUS")
    require(execution.get("package_checks") == 8, "PACKAGE_CHECKS")
    require(execution.get("canonical_release_stages") == 14, "CANONICAL_STAGES")
    require(execution.get("canonical_orchestrated_tests") == 173, "CANONICAL_TESTS")
    require(execution.get("package_runner_network_requests") == 0, "RUNNER_NETWORK")
    require(execution.get("dependency_install_network_access") is True, "INSTALL_NETWORK_DISCLOSURE")
    require(len(execution.get("output_sha256", "")) == 64, "OUTPUT_HASH")
    require(len(execution.get("canonical_preflight_sha256", "")) == 64, "CANONICAL_HASH")

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
