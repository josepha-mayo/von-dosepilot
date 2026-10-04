#!/usr/bin/env python3
"""Verify the clean public-clone quickstart evidence and its claim boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CleanQuickstartError(ValueError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, label):
    if not condition:
        raise CleanQuickstartError(label)


def verify(root):
    root = Path(root)
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("clean_reviewer_quickstart")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.clean_reviewer_quickstart_release.v2", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "CLEAN_PUBLIC_CLONE_SOFTWARE_EXECUTION", "ROLE")

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(predecessor.get("preserved_unchanged") is True, "PREDECESSOR_PRESERVED")
    original = load(predecessor_path)
    require(original.get("schema") == "dosepilot.clean_reviewer_quickstart.v1", "PREDECESSOR_SCHEMA")
    require(original.get("status") == "PASS", "PREDECESSOR_STATUS")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)
    for relative, expected in receipt.get("implementation_sha256", {}).items():
        require(sha(root / relative) == expected, "IMPLEMENTATION_HASH: " + relative)

    source = original.get("source", {})
    require(source.get("repository") == "https://github.com/josepha-mayo/von-dosepilot", "SOURCE_REPOSITORY")
    require(source.get("commit") == record.get("source_commit"), "SOURCE_COMMIT")
    require(source.get("tree") == record.get("source_tree"), "SOURCE_TREE")
    require(source.get("clone_kind") == "fresh shallow public clone", "SOURCE_CLONE_KIND")

    environment = original.get("environment", {})
    require(environment.get("fresh_virtual_environment") is True, "FRESH_VENV")
    require(environment.get("new_machine") is False, "NOT_NEW_MACHINE")

    requirements = original.get("requirements", {})
    require(requirements.get("installation_status") == "PASS", "INSTALLATION_STATUS")
    require(requirements.get("requirements.txt") == sha(root / "requirements.txt"), "REQUIREMENTS_HASH")
    require(requirements.get("study/requirements.txt") == sha(root / "study/requirements.txt"), "STUDY_REQUIREMENTS_HASH")

    lifecycle = original.get("fictional_bandwidth_lifecycle", {})
    require(lifecycle.get("status") == "PASS", "LIFECYCLE_STATUS")
    require(lifecycle.get("runner_sha256") == sha(root / "study/durable_runtime/run_bandwidth_lifecycle_demo.py"), "LIFECYCLE_RUNNER_HASH")
    require(lifecycle.get("model_kind") == "dosepilot.additive_kernel_bandwidth.v1", "LIFECYCLE_MODEL")
    require(lifecycle.get("bandwidth_multiplier") == 0.7, "LIFECYCLE_BANDWIDTH")
    for key, expected in (
        ("cli_invocations", 6),
        ("explicit_baseline_outputs", 23),
        ("complete_primary_outputs", 24),
    ):
        require(lifecycle.get(key) == expected, "LIFECYCLE_" + key.upper())
    for key in (
        "missing_primary_rejected",
        "changed_old_reading_rejected_automatically",
        "lost_export_recovered_identically",
    ):
        require(lifecycle.get(key) is True, "LIFECYCLE_" + key.upper())
    require(lifecycle.get("data") == "ALL FICTIONAL; NO BIOLOGICAL VALIDATION", "LIFECYCLE_DATA_BOUNDARY")

    preflight = original.get("current_release_preflight", {})
    require(preflight.get("status") == "PASS", "PREFLIGHT_STATUS")
    require(preflight.get("runner_sha256") == sha(root / "study/audits/release_preflight_current.py"), "PREFLIGHT_RUNNER_HASH")
    require(preflight.get("check_count") == 14, "PREFLIGHT_CHECKS")
    require(preflight.get("orchestrated_response_free_tests") == 173, "PREFLIGHT_TESTS")

    scope = original.get("scope", {})
    false_scope = (
        "protected_responses_read",
        "private_patient_arrays_read",
        "source_workbook_read",
        "public_workbook_reconstruction_executed",
        "new_model_fit",
        "new_biological_result",
        "independent_biological_validation",
        "prospective_ooc_execution",
        "clean_new_machine_certification",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
    )
    for key in false_scope:
        require(scope.get(key) is False, "SCOPE_" + key.upper())
    require(scope.get("official_competition_score") is None, "SCOPE_OFFICIAL_SCORE")
    for key in (
        "private_or_protected_inputs_read",
        "biological_accuracy_result_created",
        "accepted_kaggle_entry_changed",
    ):
        require(preflight.get(key) is False, "PREFLIGHT_" + key.upper())
    require(preflight.get("official_competition_score") is None, "PREFLIGHT_OFFICIAL_SCORE")

    documentation = (root / receipt["verification_documentation"]["path"]).read_text()
    normalized_documentation = " ".join(documentation.replace("**", "").split())
    for phrase in (
        "not a clean-new-machine certification",
        "not independent biological validation",
        "does not reproduce the external workbook",
        "does not create a new biological accuracy result",
    ):
        require(phrase in normalized_documentation, "DOCUMENTATION_BOUNDARY: " + phrase)

    preserved_failure = receipt.get("preserved_operational_failure", {})
    require(preserved_failure.get("status") == "INITIAL_LITERAL_ASSERTION_FAILURE", "PRESERVED_FAILURE_STATUS")
    require(preserved_failure.get("cause") == "Markdown line wrapping split a required phrase", "PRESERVED_FAILURE_CAUSE")
    require(preserved_failure.get("scientific_or_product_failure") is False, "PRESERVED_FAILURE_SCOPE")
    require(preserved_failure.get("corrected_tests_passed") == 8, "PRESERVED_FAILURE_CORRECTION")

    index_pairs = {
        "status": receipt["status"],
        "source_commit": source["commit"],
        "source_tree": source["tree"],
        "fresh_public_clone": True,
        "fresh_virtual_environment": True,
        "clean_new_machine_certification": False,
        "release_preflight_stages": 14,
        "orchestrated_response_free_tests": 173,
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
        "accepted_kaggle_entry_changed": False,
        "official_competition_score": None,
    }
    for key, expected in index_pairs.items():
        require(record.get(key) == expected, "INDEX_" + key.upper())
    require(record.get("documentation_path") == receipt["documentation"]["path"], "INDEX_DOCUMENTATION_PATH")
    require(record.get("documentation_sha256") == receipt["documentation"]["sha256"], "INDEX_DOCUMENTATION_HASH")
    require(record.get("verification_documentation_path") == receipt["verification_documentation"]["path"], "INDEX_VERIFICATION_DOCUMENTATION_PATH")
    require(record.get("verification_documentation_sha256") == receipt["verification_documentation"]["sha256"], "INDEX_VERIFICATION_DOCUMENTATION_HASH")

    return {
        "status": "PASS",
        "source_commit": source["commit"],
        "source_tree": source["tree"],
        "fresh_public_clone": True,
        "fresh_virtual_environment": True,
        "clean_new_machine_certification": False,
        "release_preflight_stages": 14,
        "orchestrated_response_free_tests": 173,
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
