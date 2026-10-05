#!/usr/bin/env python3
"""Verify the one-command finalist-package preflight and its public receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class FinalistPackagePreflightError(ValueError):
    pass


EXPECTED_CHECKS = [
    "current_release_preflight",
    "downloaded_trace_self_test",
    "downloaded_trace_receipt",
    "reviewer_routes",
    "reviewer_trace_discovery",
    "verification_chronology",
    "clean_reviewer_quickstart",
    "finalist_rubric_evidence",
]


def require(condition, label):
    if not condition:
        raise FinalistPackagePreflightError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("finalist_package_preflight")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.finalist_package_preflight.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "RESPONSE_FREE_ONE_COMMAND_FINALIST_PACKAGE_VERIFICATION", "ROLE")
    require(receipt.get("failed_check") is None, "FAILED_CHECK")
    checks = receipt.get("checks", [])
    require([item.get("name") for item in checks] == EXPECTED_CHECKS, "CHECK_ORDER")
    require(all(item.get("exit_code") == 0 for item in checks), "CHECK_EXIT")
    require(receipt.get("package_check_count") == 8, "PACKAGE_CHECK_COUNT")
    require(receipt.get("postcanonical_check_count") == 7, "POSTCANONICAL_CHECK_COUNT")
    require(receipt.get("canonical_release_check_count") == 14, "CANONICAL_STAGE_COUNT")
    require(receipt.get("canonical_orchestrated_test_count") == 173, "CANONICAL_TEST_COUNT")
    require(len(receipt.get("canonical_preflight_sha256", "")) == 64, "CANONICAL_RECEIPT_HASH")
    require(receipt.get("network_requests") == 0, "NETWORK_REQUESTS")
    require(receipt.get("canonical_receipt_rewritten") is False, "CANONICAL_RECEIPT_REWRITTEN")
    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)
    for key in (
        "private_or_protected_inputs_read",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
    ):
        require(receipt.get(key) is False, "BOUNDARY_" + key.upper())
    require(receipt.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")
    for key, expected in (
        ("status", "PASS"),
        ("package_check_count", 8),
        ("postcanonical_check_count", 7),
        ("canonical_release_check_count", 14),
        ("canonical_orchestrated_test_count", 173),
        ("network_requests", 0),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected, "INDEX_" + key.upper())
    return {
        "status": "PASS",
        "package_checks": 8,
        "canonical_release_stages": 14,
        "canonical_orchestrated_tests": 173,
        "network_requests": 0,
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
