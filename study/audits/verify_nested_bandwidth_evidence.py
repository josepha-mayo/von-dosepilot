#!/usr/bin/env python3
"""Response-free verifier for the public nested-bandwidth evidence receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class NestedBandwidthEvidenceError(ValueError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, label):
    if not condition:
        raise NestedBandwidthEvidenceError(label)


def verify(root):
    root = Path(root)
    path = root / "evidence/nested_bandwidth_selection_20261004.json"
    receipt = json.loads(path.read_text())
    require(receipt["schema"] == "dosepilot.nested_bandwidth_selection.public_evidence.v1",
            "SCHEMA")
    require(receipt["status"] == "PASS", "STATUS")
    require(receipt["decision"] == "EVALUATION_ONLY_RETAIN_BANDWIDTH07", "DECISION")
    for relative, expected in receipt["public_artifact_sha256"].items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH:" + relative)
    cohort = receipt["cohort"]
    require(cohort == {"samples": 119, "whole_patients": 59, "targets": 24,
                       "physical_wells_per_alternative": 64, "per_plate": 32,
                       "outer_patient_folds": 5, "inner_patient_folds": 3}, "COHORT")
    metrics = receipt["metrics"]
    require(metrics["nested"]["mse"] == 0.0010582750420801538, "NESTED_MSE")
    require(metrics["nested"] == metrics["bandwidth07"], "NESTED_FIXED07_PARITY")
    require(metrics["bandwidth10"]["mse"] == 0.001060552730112811, "BW10_MSE")
    require(metrics["bandwidth14"]["mse"] == 0.0010637093585907204, "BW14_MSE")
    require(receipt["selection_counts"] == {"0.7": 5, "1.0": 0, "1.4": 0},
            "SELECTION_COUNTS")
    selections = receipt["foldwise_selections"]
    require(len(selections) == 5, "SELECTION_LENGTH")
    require([row["fold"] for row in selections] == list(range(5)), "FOLD_ORDER")
    require(all(row["bandwidth"] == 0.7 for row in selections), "FOLD_BANDWIDTHS")
    require(all(row["ridge"] == 1.0 for row in selections), "FOLD_RIDGE")
    require(selections[0]["fraction"] == 0.3, "FOLD0_FRACTION")
    require(all(row["fraction"] == 0.1 for row in selections[1:]), "FOLD1_4_FRACTION")
    parity = receipt["nested_vs_fixed07"]
    require(parity == {"prediction_max_absolute_difference": 0.0,
                       "patient_ties": 59, "fold_ties": 5,
                       "target_ties": 24, "orientation_ties": 2}, "PARITY")
    verification = receipt["verification"]
    require(verification["independent_no_refit_audit"] == "PASS", "NO_REFIT_AUDIT")
    require(verification["private_prediction_arrays_published"] is False, "PRIVATE_PUBLISH")
    boundary = receipt["claim_boundary"]
    require(boundary["same_task_repeated_adaptive_development"] is True, "ADAPTIVE")
    require(boundary["independent_validation"] is False, "INDEPENDENCE")
    require(boundary["protected_response_access"] is False, "PROTECTED")
    require(boundary["accepted_kaggle_entry_changed"] is False, "KAGGLE")
    require(boundary["official_competition_score"] is None, "OFFICIAL_SCORE")
    return {"status": "PASS", "receipt_sha256": sha(path),
            "folds_selecting_bandwidth07": 5, "private_or_protected_inputs_read": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.root), indent=2))


if __name__ == "__main__":
    main()

