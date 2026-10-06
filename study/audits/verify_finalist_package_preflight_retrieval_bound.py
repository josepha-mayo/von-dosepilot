#!/usr/bin/env python3
"""Verify the retrieval-bound finalist-package preflight and receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class RetrievalBoundFinalistPackagePreflightError(ValueError):
    pass


EXPECTED_CHECKS = [
    "current_release_preflight",
    "downloaded_trace_self_test",
    "downloaded_trace_receipt",
    "reviewer_routes",
    "reviewer_trace_discovery",
    "verification_chronology",
    "clean_reviewer_quickstart",
    "current_report_retrieval_finalist_rubric_evidence",
]

REPORT_SHA256 = "23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1"
REPORT_BYTES = 92307
REPORT_BLOB = "6899cb6b2c53c1c1d67a9fadb5d073923daaf21e"


def require(condition, label):
    if not condition:
        raise RetrievalBoundFinalistPackagePreflightError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_report_retrieval_finalist_package_preflight")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(receipt_path.name == "finalist_package_preflight_r4_20261006.json", "INDEX_CURRENT_PATH")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.finalist_package_preflight.v4", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(
        receipt.get("role")
        == "RESPONSE_FREE_CURRENT_REPORT_RETRIEVAL_BOUND_FINALIST_PACKAGE_VERIFICATION",
        "ROLE",
    )

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(
        load(predecessor_path).get("schema") == "dosepilot.finalist_package_preflight.v3",
        "PREDECESSOR_SCHEMA",
    )
    require(predecessor.get("preserved_unchanged") is True, "PREDECESSOR_PRESERVED")

    rubric = receipt.get("current_report_retrieval_rubric", {})
    rubric_path = root / rubric.get("path", "")
    require(sha(rubric_path) == rubric.get("sha256"), "CURRENT_RETRIEVAL_RUBRIC_HASH")
    rubric_receipt = load(rubric_path)
    require(
        rubric_receipt.get("schema") == "dosepilot.finalist_rubric_evidence.v6",
        "CURRENT_RETRIEVAL_RUBRIC_SCHEMA",
    )
    require(rubric_receipt.get("status") == "PASS", "CURRENT_RETRIEVAL_RUBRIC_STATUS")
    require(rubric.get("current_report_sha256") == REPORT_SHA256, "CURRENT_REPORT_HASH")
    require(rubric.get("current_report_bytes") == REPORT_BYTES, "CURRENT_REPORT_BYTES")
    require(rubric.get("current_report_git_blob_sha") == REPORT_BLOB, "CURRENT_REPORT_BLOB")
    require(rubric.get("public_repository_file_bytes_retrieved") is True, "REPOSITORY_BYTES_RETRIEVED")
    require(rubric.get("retrieved_bytes_match_exact_tree_pdf") is True, "RETRIEVED_BYTES_MATCH")
    require(rubric.get("anonymous_raw_http_verified") is False, "NO_ANONYMOUS_RAW_HTTP")
    require(rubric.get("browser_download_button_verified") is False, "NO_BROWSER_BUTTON")
    require(rubric.get("raw_download_verified") is False, "NO_GENERIC_RAW_DOWNLOAD")

    require(receipt.get("failed_check") is None, "FAILED_CHECK")
    checks = receipt.get("checks", [])
    require([item.get("name") for item in checks] == EXPECTED_CHECKS, "CHECK_ORDER")
    require(all(item.get("exit_code") == 0 for item in checks), "CHECK_EXIT")
    require(receipt.get("package_check_count") == 8, "PACKAGE_CHECK_COUNT")
    require(receipt.get("postcanonical_check_count") == 7, "POSTCANONICAL_CHECK_COUNT")
    require(
        receipt.get("current_report_retrieval_rubric_successor_checked") is True,
        "CURRENT_RETRIEVAL_RUBRIC_SUCCESSOR",
    )
    require(receipt.get("public_repository_file_bytes_retrieved") is True, "RECEIPT_BYTES_RETRIEVED")
    require(receipt.get("retrieved_bytes_match_exact_tree_pdf") is True, "RECEIPT_BYTES_MATCH")
    require(receipt.get("anonymous_raw_http_verified") is False, "RECEIPT_NO_RAW_HTTP")
    require(receipt.get("browser_download_button_verified") is False, "RECEIPT_NO_BUTTON")
    require(receipt.get("raw_download_verified") is False, "RECEIPT_NO_GENERIC_DOWNLOAD")
    require(
        receipt.get("historical_report_bound_predecessor_preserved") is True,
        "HISTORICAL_REPORT_BOUND_PRESERVED",
    )
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
        ("current_report_retrieval_rubric_successor_checked", True),
        ("current_report_sha256", REPORT_SHA256),
        ("current_report_bytes", REPORT_BYTES),
        ("current_report_git_blob_sha", REPORT_BLOB),
        ("public_repository_file_bytes_retrieved", True),
        ("retrieved_bytes_match_exact_tree_pdf", True),
        ("anonymous_raw_http_verified", False),
        ("browser_download_button_verified", False),
        ("raw_download_verified", False),
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
        "current_report_retrieval_rubric_successor_checked": True,
        "historical_report_bound_predecessor_preserved": True,
        "current_report_sha256": REPORT_SHA256,
        "current_report_bytes": REPORT_BYTES,
        "current_report_git_blob_sha": REPORT_BLOB,
        "public_repository_file_bytes_retrieved": True,
        "retrieved_bytes_match_exact_tree_pdf": True,
        "anonymous_raw_http_verified": False,
        "browser_download_button_verified": False,
        "raw_download_verified": False,
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
