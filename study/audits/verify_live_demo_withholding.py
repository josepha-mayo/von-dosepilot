#!/usr/bin/env python3
"""Verify the public fictional demo's numerical-withholding contract."""
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


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("live_demo_withholding")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.live_demo_withholding.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "PUBLIC_DEMO_STATE_INTEGRITY", "ROLE")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    defect = receipt.get("defect", {})
    require(defect.get("precompletion_numerical_values_rendered") == 24, "DEFECT_PRECOMPLETION")
    require(defect.get("baseline_numbers_rendered") == 24, "DEFECT_BASELINE_RENDERED")
    require(defect.get("baseline_outputs_claimed") == 23, "DEFECT_BASELINE_CLAIMED")

    result = subprocess.run(
        ["node", "site/test_app_state.js"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    require(result.returncode == 0, "NODE_TEST_EXIT")
    node_receipt = json.loads(result.stdout)
    expected = receipt.get("local_state_verification", {})
    for key in ("status", "states", "withheld_before_complete", "baseline_outputs", "baseline_withheld", "primary_outputs"):
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

    deployment = receipt.get("production_deployment", {})
    require(deployment.get("site_id") == "d313109a-8052-441a-9439-f42b0ef8034f", "DEPLOY_SITE")
    require(deployment.get("deploy_id") == "6ac25f15cbb08b59f33ed4c6", "DEPLOY_ID")
    require(deployment.get("state") == "ready", "DEPLOY_STATE")
    require(deployment.get("url") == "https://von-dosepilot.netlify.app", "DEPLOY_URL")

    boundary = receipt.get("claim_boundary", {})
    for key in (
        "new_model_fit",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "private_or_protected_inputs_read",
        "accepted_kaggle_entry_changed",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("netlify_production_deployment_changed") is True, "BOUNDARY_NETLIFY_CHANGED")
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    return {
        "status": "PASS",
        "verified_states": len(expected.get("states", [])),
        "fresh_withheld": browser.get("fresh_withheld"),
        "baseline_numeric_outputs": browser.get("baseline_numeric_outputs"),
        "baseline_withheld": browser.get("baseline_withheld"),
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
