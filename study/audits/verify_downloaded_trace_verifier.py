#!/usr/bin/env python3
"""Verify the offline downloaded-trace checker and its public evidence receipt."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


class DownloadedTraceVerifierError(ValueError):
    pass


def require(condition, label):
    if not condition:
        raise DownloadedTraceVerifierError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("downloaded_trace_verifier")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.downloaded_trace_verifier.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    module_path = root / "demo/verify_downloaded_trace.py"
    spec = importlib.util.spec_from_file_location("dosepilot_downloaded_trace", module_path)
    require(spec is not None and spec.loader is not None, "MODULE_SPEC")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = receipt.get("source_trace_receipt", {})
    source_path = root / source.get("path", "")
    require(sha(source_path) == source.get("sha256"), "SOURCE_TRACE_RECEIPT_HASH")
    source_receipt = load(source_path)
    require(source_receipt.get("schema") == "dosepilot.live_demo_withholding.v4", "SOURCE_TRACE_SCHEMA")
    source_hashes = source_receipt.get("trace_contract", {})
    require(source_hashes.get("plan_sha256") == module.PLAN, "SOURCE_PLAN_DIGEST")
    require(source_hashes.get("baseline_result_sha256") == module.BASELINE, "SOURCE_BASELINE_DIGEST")
    require(source_hashes.get("measurement_sha256") == module.MEASUREMENT, "SOURCE_MEASUREMENT_DIGEST")
    require(source_hashes.get("primary_result_sha256") == module.PRIMARY, "SOURCE_PRIMARY_DIGEST")
    result = module.self_test()
    require(result.get("status") == "PASS", "SELF_TEST_STATUS")
    require(result.get("valid_state_cases") == 5, "VALID_STATE_CASES")
    require(result.get("invalid_cases_rejected") == 12, "INVALID_CASES_REJECTED")
    require(result.get("private_or_protected_inputs_read") is False, "SELF_TEST_PROTECTED_BOUNDARY")
    require(result.get("biological_accuracy_result_created") is False, "SELF_TEST_BIOLOGICAL_BOUNDARY")

    verification = receipt.get("verification", {})
    require(verification.get("valid_state_cases") == 5, "RECEIPT_VALID_STATE_CASES")
    require(verification.get("invalid_cases_rejected") == 12, "RECEIPT_INVALID_CASES")
    require(verification.get("exact_six_field_contract") is True, "SIX_FIELD_CONTRACT")
    require(verification.get("filename_state_binding") is True, "FILENAME_BINDING")
    require(verification.get("known_public_demo_digests_bound") == 4, "DIGEST_COUNT")
    for key, expected in (
        ("status", "PASS"),
        ("valid_state_cases", 5),
        ("invalid_cases_rejected", 12),
        ("exact_six_field_contract", True),
        ("filename_state_binding", True),
        ("known_public_demo_digests_bound", 4),
        ("canonical_release_preflight_changed", False),
        ("canonical_orchestrated_response_free_tests", 173),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected, "INDEX_" + key.upper())
    boundary = receipt.get("claim_boundary", {})
    for key in (
        "new_model_fit",
        "private_or_protected_inputs_read",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")
    return {
        "status": "PASS",
        "valid_state_cases": 5,
        "invalid_cases_rejected": 12,
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
