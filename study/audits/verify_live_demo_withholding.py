#!/usr/bin/env python3
"""Verify the fictional demo's withholding and browser-local trace contract."""
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
    require(receipt.get("schema") == "dosepilot.live_demo_withholding.v2", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "PUBLIC_DEMO_STATE_AND_TRACE_INTEGRITY", "ROLE")

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(load(predecessor_path).get("schema") == "dosepilot.live_demo_withholding.v1", "PREDECESSOR_SCHEMA")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    contract = receipt.get("trace_contract", {})
    require(contract.get("algorithm") == "SHA-256 via Web Crypto", "TRACE_ALGORITHM")
    require(contract.get("payloads") == ["plan", "measurements", "baseline_result", "primary_result"], "TRACE_PAYLOADS")
    require(contract.get("plan_stable_across_committed_states") is True, "TRACE_PLAN_STABLE")
    require(contract.get("precompletion_measurement_hash_withheld") is True, "TRACE_MEASUREMENT_WITHHELD")
    require(contract.get("precompletion_primary_hash_withheld") is True, "TRACE_PRIMARY_WITHHELD")
    for key in ("plan_sha256", "baseline_result_sha256", "measurement_sha256", "primary_result_sha256"):
        require_hash(contract.get(key), "TRACE_" + key.upper())
    require(len(set(contract[key] for key in ("plan_sha256", "baseline_result_sha256", "measurement_sha256", "primary_result_sha256"))) == 4, "TRACE_HASH_DISTINCTNESS")
    expected_trace_hashes = {
        "plan_sha256": "e1f2b0c63bb4a3db78568cbf331b247475b6eba7d6794c835a9d42941b3e748e",
        "baseline_result_sha256": "90ff9f3bfd8c192604d7e130cb042477d1f1753fbe8bef18c6ff510739644194",
        "measurement_sha256": "71a23a872e794f60751def3dcd2a27b54453b9b481fa736099269d549941573d",
        "primary_result_sha256": "ed48e0320d740685b350373e72dce6f736a86c78992bfdd481a92439ca9181a6",
    }
    require(all(contract.get(key) == value for key, value in expected_trace_hashes.items()), "TRACE_HASH_VALUE")

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
    ):
        require(node_receipt.get(key) == expected.get(key), "NODE_TEST_" + key.upper())

    browser = receipt.get("production_browser_verification", {})
    require(browser.get("fresh_withheld") == 24, "BROWSER_FRESH_WITHHELD")
    require(browser.get("missing_wells_present") == 63, "BROWSER_MISSING_WELLS")
    require(browser.get("missing_current_outputs") == 0, "BROWSER_MISSING_PRIMARY")
    require(browser.get("baseline_numeric_outputs") == 23, "BROWSER_BASELINE_OUTPUTS")
    require(browser.get("baseline_withheld") == 1, "BROWSER_BASELINE_WITHHELD")
    require(browser.get("baseline_withheld_label") == "Afatinib: withheld", "BROWSER_BASELINE_LABEL")
    require(browser.get("complete_current_outputs") == 24, "BROWSER_COMPLETE_OUTPUTS")
    require(browser.get("complete_withheld") == 0, "BROWSER_COMPLETE_WITHHELD")
    require(browser.get("site_origin_console_errors") == 0, "BROWSER_SITE_ERRORS")
    require(browser.get("plan_hash_stable_across_committed_states") is True, "BROWSER_PLAN_STABLE")
    require(browser.get("precompletion_measurement_hash_withheld") is True, "BROWSER_MEASUREMENT_WITHHELD")
    require(browser.get("precompletion_primary_hash_withheld") is True, "BROWSER_PRIMARY_WITHHELD")

    deployment = receipt.get("production_deployment", {})
    require(deployment.get("site_id") == "d313109a-8052-441a-9439-f42b0ef8034f", "DEPLOY_SITE")
    require(deployment.get("deploy_id") == "6ac26bba8ecb6d2873e98282", "DEPLOY_ID")
    require(deployment.get("build_id") == "6ac26bba8ecb6d2873e98280", "BUILD_ID")
    require(deployment.get("state") == "ready", "DEPLOY_STATE")
    require(deployment.get("url") == "https://von-dosepilot.netlify.app", "DEPLOY_URL")

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
        "status": "PASS", "verified_states": len(expected.get("states", [])),
        "fresh_withheld": browser.get("fresh_withheld"),
        "baseline_numeric_outputs": browser.get("baseline_numeric_outputs"),
        "baseline_withheld": browser.get("baseline_withheld"),
        "complete_current_outputs": browser.get("complete_current_outputs"),
        "trace_hashes_verified": 4, "deploy_id": deployment.get("deploy_id"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
