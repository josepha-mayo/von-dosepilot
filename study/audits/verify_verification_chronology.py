#!/usr/bin/env python3
"""Verify the additive response-free release-test chronology."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class ChronologyError(ValueError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, label):
    if not condition:
        raise ChronologyError(label)


def verify(root):
    root = Path(root)
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("verification_chronology")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record["path"]
    require(sha(receipt_path) == record["sha256"], "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.verification_chronology.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")

    expected = [157, 168, 173]
    states = receipt.get("states")
    require(isinstance(states, list) and [x.get("orchestrated_test_count") for x in states] == expected, "COUNTS")
    require(all(x.get("check_count") == 14 and x.get("status") == "PASS" for x in states), "STAGE_STATUS")
    require(all(states[i]["orchestrated_test_count"] < states[i + 1]["orchestrated_test_count"] for i in range(len(states) - 1)), "MONOTONE_ADDITIONS")
    for state in states:
        path = root / state["path"]
        require(sha(path) == state["sha256"], "STATE_HASH: " + state["path"])
        value = load(path)
        require(value.get("status") == "PASS", "STATE_STATUS: " + state["path"])
        require(value.get("check_count") == state["check_count"], "STATE_CHECKS: " + state["path"])
        require(value.get("orchestrated_test_count") == state["orchestrated_test_count"], "STATE_TESTS: " + state["path"])
        require(value.get("private_or_protected_inputs_read") is False, "STATE_PRIVATE: " + state["path"])
        require(value.get("biological_accuracy_result_created") is False, "STATE_ACCURACY: " + state["path"])
        require(value.get("accepted_kaggle_entry_changed") is False, "STATE_ENTRY: " + state["path"])
        require(value.get("official_competition_score") is None, "STATE_SCORE: " + state["path"])

    milestone = receipt.get("governance_milestone", {})
    milestone_path = root / milestone.get("path", "")
    require(sha(milestone_path) == milestone.get("sha256"), "GOVERNANCE_MILESTONE_HASH")
    milestone_value = load(milestone_path)
    require(milestone_value.get("verification", {}).get("current_release_preflight_orchestrated_tests") == 171, "GOVERNANCE_MILESTONE_TESTS")

    latest = states[-1]
    current = index.get("current_release_preflight", {})
    require(current.get("path") == latest["path"], "INDEX_CURRENT_PATH")
    require(current.get("sha256") == latest["sha256"], "INDEX_CURRENT_HASH")
    require(current.get("orchestrated_response_free_tests") == 173, "INDEX_CURRENT_TESTS")

    for path, expected_hash in receipt.get("artifact_sha256", {}).items():
        require(sha(root / path) == expected_hash, "ARTIFACT_HASH: " + path)
    readme = (root / "README.md").read_text()
    reviewer = (root / "00_REVIEWER_START_HERE.md").read_text()
    chronology = (root / "docs/VERIFICATION_CHRONOLOGY.md").read_text()
    require("173 orchestrated response-free tests" in readme, "README_CURRENT_COUNT")
    require("173 response-free tests passed" in reviewer, "REVIEWER_CURRENT_COUNT")
    require("168-test receipt" in readme and "168-test receipt" in reviewer, "HISTORICAL_168_CONTEXT")
    require("not 173 biological experiments" in chronology, "SOFTWARE_BIOLOGY_BOUNDARY")

    boundary = receipt.get("claim_boundary", {})
    for key in ("private_or_protected_inputs_read", "biological_accuracy_result_created", "accepted_kaggle_entry_changed"):
        require(boundary.get(key) is False, "BOUNDARY: " + key)
    require(boundary.get("official_competition_score") is None, "BOUNDARY_SCORE")
    failure = receipt.get("preserved_operational_failure", {})
    require(failure.get("status") == "IMPORT_PATH_FAILURE", "PRESERVED_FAILURE_STATUS")
    require(failure.get("scientific_or_product_failure") is False, "PRESERVED_FAILURE_SCOPE")
    require(failure.get("correct_invocation_tests_passed") == 3, "PRESERVED_FAILURE_CORRECTION")
    return {
        "status": "PASS",
        "preflight_receipts": len(states),
        "governance_milestone_tests": 171,
        "latest_orchestrated_test_count": 173,
        "historical_receipts_preserved": True,
        "private_or_protected_inputs_read": False,
        "preserved_operational_failure": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
