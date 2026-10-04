#!/usr/bin/env python3
"""Verify the fictional demo's withholding and inspectable trace contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


class WithholdingVerificationError(ValueError):
    pass


def require(condition, label):
    if not condition:
        raise WithholdingVerificationError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require_hash(value, label):
    require(isinstance(value, str) and len(value) == 64, label)
    require(all(character in "0123456789abcdef" for character in value), label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("live_demo_withholding")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.live_demo_withholding.v3", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "PUBLIC_DEMO_INSPECTABLE_TRACE_INTEGRITY", "ROLE")

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(load(predecessor_path).get("schema") == "dosepilot.live_demo_withholding.v2", "PREDECESSOR_SCHEMA")
    require(predecessor.get("baseline_digest_record_correct") is False, "PREDECESSOR_DEFECT_DISCLOSED")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    result = subprocess.run(
        ["node", "site/test_app_state.js"], cwd=root, text=True, capture_output=True, check=False,
    )
    require(result.returncode == 0, "NODE_TEST_EXIT")
    node_receipt = json.loads(result.stdout)
    expected = receipt.get("local_state_verification", {})
    for key in (
        "status", "states", "withheld_before_complete", "baseline_outputs", "baseline_withheld",
        "primary_outputs", "plan_hash_stable_across_committed_states",
        "precompletion_measurement_hash_withheld", "precompletion_primary_hash_withheld",
        "baseline_result_hash_present", "complete_measurement_hash_present", "complete_primary_hash_present",
        "full_record_inspectable", "withheld_record_fields_are_null",
    ):
        require(node_receipt.get(key) == expected.get(key), "NODE_TEST_" + key.upper())

    computed = node_receipt.get("trace_sha256", {})
    contract = receipt.get("trace_contract", {})
    expected_hashes = {
        "plan": contract.get("plan_sha256"),
        "baseline_result": contract.get("baseline_result_sha256"),
        "measurement": contract.get("measurement_sha256"),
        "primary_result": contract.get("primary_result_sha256"),
    }
    for key, value in expected_hashes.items():
        require_hash(value, "TRACE_" + key.upper())
        require(computed.get(key) == value, "TRACE_COMPUTED_" + key.upper())
    require(len(set(expected_hashes.values())) == 4, "TRACE_HASH_DISTINCTNESS")
    require(contract.get("schedule_source") == "site/frozen_schedule.js", "TRACE_SCHEDULE_SOURCE")
    require(contract.get("plan_stable_across_committed_states") is True, "TRACE_PLAN_STABLE")
    require(contract.get("precompletion_measurement_hash_withheld") is True, "TRACE_MEASUREMENT_WITHHELD")
    require(contract.get("precompletion_primary_hash_withheld") is True, "TRACE_PRIMARY_WITHHELD")

    browser = receipt.get("production_browser_verification", {})
    require(browser.get("full_record_disclosure_present") is True, "BROWSER_DISCLOSURE")
    require(browser.get("full_record_expands") is True, "BROWSER_DISCLOSURE_EXPANDS")
    require(browser.get("missing_measurement_sha256") is None, "BROWSER_MISSING_MEASUREMENT_NULL")
    require(browser.get("missing_result_sha256") is None, "BROWSER_MISSING_RESULT_NULL")
    require(browser.get("baseline_numeric_outputs") == 23, "BROWSER_BASELINE_OUTPUTS")
    require(browser.get("baseline_withheld") == 1, "BROWSER_BASELINE_WITHHELD")
    require(browser.get("complete_current_outputs") == 24, "BROWSER_COMPLETE_OUTPUTS")
    require(browser.get("complete_withheld") == 0, "BROWSER_COMPLETE_WITHHELD")
    for key, value in expected_hashes.items():
        require(browser.get(key + "_sha256") == value, "BROWSER_HASH_" + key.upper())
    require(browser.get("site_origin_console_errors") == 0, "BROWSER_SITE_ERRORS")

    deployment = receipt.get("production_deployment", {})
    require(deployment.get("site_id") == "d313109a-8052-441a-9439-f42b0ef8034f", "DEPLOY_SITE")
    require(deployment.get("deploy_id") == "6ac278604e8e6176fb3424ea", "DEPLOY_ID")
    require(deployment.get("build_id") == "6ac278604e8e6176fb3424e8", "BUILD_ID")
    require(deployment.get("state") == "ready", "DEPLOY_STATE")
    require(deployment.get("url") == "https://von-dosepilot.netlify.app", "DEPLOY_URL")

    correction = receipt.get("correction", {})
    require(correction.get("predecessor_baseline_digest_was_incorrect") is True, "CORRECTION_DISCLOSED")
    require(correction.get("application_digest_arithmetic_was_incorrect") is False, "CORRECTION_APP_BOUNDARY")
    require(correction.get("scientific_or_model_result_affected") is False, "CORRECTION_SCIENCE_BOUNDARY")

    limitations = receipt.get("limitations", {})
    for key in ("signed", "worm_storage", "physical_provenance", "control_validation", "biological_validation"):
        require(limitations.get(key) is False, "LIMITATION_" + key.upper())

    boundary = receipt.get("claim_boundary", {})
    for key in (
        "new_model_fit", "biological_accuracy_result_created", "independent_validation_created",
        "private_or_protected_inputs_read", "accepted_kaggle_entry_changed",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("netlify_production_deployment_changed") is True, "BOUNDARY_NETLIFY_CHANGED")
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    return {
        "status": "PASS",
        "verified_states": len(expected.get("states", [])),
        "computed_trace_hashes_verified": len(expected_hashes),
        "full_record_inspectable": expected.get("full_record_inspectable"),
        "baseline_numeric_outputs": browser.get("baseline_numeric_outputs"),
        "complete_current_outputs": browser.get("complete_current_outputs"),
        "deploy_id": deployment.get("deploy_id"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
