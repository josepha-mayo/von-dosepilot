#!/usr/bin/env python3
"""Verify the immutable current scientific-successor evidence map."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


class CurrentScientificSuccessorEvidenceError(ValueError):
    pass


EXPECTED_BINDINGS = {
    "candidate": {
        "path": "evidence/orientation_specific_control_quality_rank1_20261006.json",
        "sha256": "c3548e944a380432e17feaf8f1146fbf860895bb71b793d278e7e354adc3d768",
    },
    "descriptive_bootstrap": {
        "path": "evidence/current_successor_descriptive_bootstrap_20261006.json",
        "sha256": "e36542bf9224a1e2f250ad681302c1cec9eb3a17e660d4383404f6eb6ab0d1ba",
    },
    "target_deltas_json": {
        "path": "evidence/current_successor_target_deltas_20261006.json",
        "sha256": "e0abd231cd7410311e9ae156ba529299e3f9b95c106a785f3bcbb5e188bd817e",
    },
    "target_deltas_csv": {
        "path": "evidence/current_successor_target_deltas_20261006.csv",
        "sha256": "491585a5c1131cafa5e9d186777bf62da09c3c3bc9d2ebe803e33e76a96924e5",
    },
}

EXPECTED_PRESENTATION = {
    "visual": ("docs/figures/current_successor_summary_20261006.png", "234335506fc424f03af1460440b8d5e4eda6c84a70cc7c61f32da9260f05dfa5"),
    "report_source": ("docs/DosePilot_Technical_Report_20261006.md", "b9f0b31313e3a1700be62c9e0d2b535e7c1596ceb43915b41330e3e42a4873fb"),
    "report_pdf": ("docs/DosePilot_Technical_Report_20261006.pdf", "f8fb82f477e85a36daf2e528ef895fc35f6e3a42ff8a770f9aa697a11cdc825d"),
    "writeup": ("docs/KAGGLE_WRITEUP_20261006.md", "277fe2427feb6932b468ddeafeb6ec62d6ed5bf8321d1f85cd17622743cb06e8"),
    "reviewer_path": ("SUBMISSION_UPDATE_20261006.md", "27c42f55ea191fe8b97ccca0bfa62f7061f0a12ade8baa4ad24e8fb82d1f82d7"),
}


def load(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(actual, expected, label, tolerance=0.0):
    if isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
            raise CurrentScientificSuccessorEvidenceError(label)
    elif actual != expected:
        raise CurrentScientificSuccessorEvidenceError(label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_scientific_successor_evidence")
    same(isinstance(record, dict), True, "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    same(receipt_path.name, "current_scientific_successor_evidence_20261006.json", "INDEX_PATH")
    same(sha256(receipt_path), record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    same(receipt.get("schema"), "dosepilot.current_scientific_successor_evidence.v1", "SCHEMA")
    same(receipt.get("status"), "PASS", "STATUS")
    same(receipt.get("as_of_date"), "2026-10-06", "DATE")
    same(receipt.get("role"), "REPEATED_ADAPTIVE_DEVELOPMENT_EVIDENCE_MAP_NOT_INDEPENDENT_VALIDATION", "ROLE")
    same(receipt.get("evidence_bindings"), EXPECTED_BINDINGS, "EVIDENCE_BINDINGS")
    for binding in EXPECTED_BINDINGS.values():
        same(sha256(root / binding["path"]), binding["sha256"], "BINDING_HASH: " + binding["path"])

    candidate = load(root / EXPECTED_BINDINGS["candidate"]["path"])
    same(candidate["schema"], "dosepilot.orientation_specific_control_quality_rank1.public_evidence.v1", "CANDIDATE_SCHEMA")
    same(candidate["status"], "VERIFIED_NEW_BEST_REPEATED_DEVELOPMENT_CANDIDATE", "CANDIDATE_STATUS")
    same(candidate["role"], "REPEATED_ADAPTIVE_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION", "CANDIDATE_ROLE")
    same(candidate["population"], {"samples": 119, "whole_patients": 59, "targets": 24, "physical_treatment_wells": 64, "per_plate": 32}, "POPULATION")
    same(candidate["metrics"]["candidate"]["mse"], 0.001042745722096212, "CANDIDATE_MSE")
    same(candidate["metrics"]["candidate"]["p90_rmse"], 0.037419695944064885, "CANDIDATE_P90")
    same(candidate["comparisons"]["bandwidth07"]["patient_wins"], 40, "BANDWIDTH_PATIENTS")
    same(candidate["comparisons"]["bandwidth07"]["fold_wins"], 5, "BANDWIDTH_FOLDS")
    same(candidate["comparisons"]["bandwidth07"]["gate"], {"mse": True, "patients": True, "folds": True, "p90": True, "beats_verified_best": True}, "BANDWIDTH_GATE")
    same(candidate["comparisons"]["previous_best"]["patient_wins"], 32, "PREVIOUS_PATIENTS")
    same(candidate["comparisons"]["previous_best"]["fold_wins"], 3, "PREVIOUS_FOLDS")
    same(candidate["comparisons"]["r18"]["passes_all"], True, "R18_GATE")
    same(candidate["verification"]["max_prediction_difference"], 0.0, "MACHINE_RECEIPT_REPLAY")
    same(candidate["verification"]["prediction_tolerance"], 5e-16, "REPLAY_TOLERANCE")
    same(candidate["verification"]["protected22_access"], False, "CANDIDATE_NO_PROTECTED22")
    same(candidate["independent_validation"], False, "CANDIDATE_NO_INDEPENDENT_VALIDATION")
    same(candidate["official_competition_score"], None, "CANDIDATE_NO_SCORE")

    bootstrap = load(root / EXPECTED_BINDINGS["descriptive_bootstrap"]["path"])
    same(bootstrap["schema"], "dosepilot.current_successor_descriptive_patient_bootstrap.v1", "BOOTSTRAP_SCHEMA")
    same(bootstrap["role"], "POST_HOC_DESCRIPTIVE_NOT_CONFIRMATORY", "BOOTSTRAP_ROLE")
    same(bootstrap["candidate"]["mse"], candidate["metrics"]["candidate"]["mse"], "BOOTSTRAP_MSE")
    same(bootstrap["candidate"]["prediction_sha256"], candidate["hashes"]["prediction_sha256"], "BOOTSTRAP_PREDICTIONS")
    same(bootstrap["method"]["bootstrap_resamples"], 100000, "BOOTSTRAP_RESAMPLES")
    same(bootstrap["method"]["selection_adjusted"], False, "BOOTSTRAP_SELECTION_NAIVE")
    bandwidth_ci = bootstrap["comparisons"]["bandwidth07"]["bootstrap_percentile_95_ci"]
    previous_ci = bootstrap["comparisons"]["immediate_predecessor"]["bootstrap_percentile_95_ci"]
    same(bandwidth_ci[1] < 0, True, "BOOTSTRAP_BANDWIDTH_CI")
    same(previous_ci[0] < 0 < previous_ci[1], True, "BOOTSTRAP_PREVIOUS_CI")
    same(bootstrap["patient_level_rows_published"], False, "BOOTSTRAP_NO_ROWS")
    same(bootstrap["independent_validation"], False, "BOOTSTRAP_NO_VALIDATION")
    same(bootstrap["protected22_access"], False, "BOOTSTRAP_NO_PROTECTED22")

    targets = load(root / EXPECTED_BINDINGS["target_deltas_json"]["path"])
    same(targets["schema"], "dosepilot.current_successor_target_deltas.v1", "TARGET_SCHEMA")
    same(targets["role"], "POST_HOC_AGGREGATE_TARGET_DIAGNOSTIC_NOT_CONFIRMATORY", "TARGET_ROLE")
    rows = targets["rows"]
    same(len(rows), 24, "TARGET_ROWS")
    same(set(row["target_index"] for row in rows), set(range(24)), "TARGET_INDICES")
    same(len({row["drug"] for row in rows}), 24, "TARGET_DRUGS")
    for row in rows:
        expected_delta = row["current_mse"] - row["bandwidth07_mse"]
        same(row["delta_mse_current_minus_bandwidth07"], expected_delta, "TARGET_DELTA", 1e-18)
        same(row["improved"], expected_delta < 0, "TARGET_SIGN")
    same(sum(row["improved"] for row in rows), 19, "TARGET_WINS")
    same(sum(not row["improved"] for row in rows), 5, "TARGET_LOSSES")
    same(targets["regressing_targets"], ["Afatinib", "Regorafenib", "AZD7762", "LCL161", "Trametinib"], "TARGET_REGRESSIONS")
    same(sum(row["current_mse"] for row in rows) / 24, targets["candidate_mse"], "TARGET_CURRENT_MEAN", 1e-18)
    same(sum(row["bandwidth07_mse"] for row in rows) / 24, targets["reference_mse"], "TARGET_REFERENCE_MEAN", 1e-18)
    same(targets["patient_level_rows_published"], False, "TARGET_NO_ROWS")
    same(targets["selection_adjusted"], False, "TARGET_SELECTION_NAIVE")
    same(targets["independent_validation"], False, "TARGET_NO_VALIDATION")
    same(targets["protected22_access"], False, "TARGET_NO_PROTECTED22")

    with (root / EXPECTED_BINDINGS["target_deltas_csv"]["path"]).open(newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    same(len(csv_rows), 24, "CSV_ROWS")
    for csv_row, row in zip(csv_rows, rows):
        same(int(csv_row["target_index"]), row["target_index"], "CSV_INDEX")
        same(csv_row["drug"], row["drug"], "CSV_DRUG")
        same(float(csv_row["current_mse"]), row["current_mse"], "CSV_CURRENT")
        same(float(csv_row["bandwidth07_mse"]), row["bandwidth07_mse"], "CSV_REFERENCE")

    same(receipt["presentation_artifacts"], {key: {"path": path, "sha256": digest} for key, (path, digest) in EXPECTED_PRESENTATION.items()}, "PRESENTATION_BINDINGS")
    for path, digest in EXPECTED_PRESENTATION.values():
        same(sha256(root / path), digest, "PRESENTATION_HASH: " + path)
    same((root / EXPECTED_PRESENTATION["report_pdf"][0]).stat().st_size, 192966, "REPORT_BYTES")

    for relative, digest in receipt["artifact_sha256"].items():
        same(sha256(root / relative), digest, "ARTIFACT_HASH: " + relative)

    doc = (root / "docs/CURRENT_SCIENTIFIC_SUCCESSOR_EVIDENCE.md").read_text()
    for phrase in (
        "0.001042745722096212", "40/59 patient wins", "5/5 favorable", "19/24 target-average wins",
        "post-hoc and selection-naive", "immediate predecessor crosses zero",
        "c3548e944a380432e17feaf8f1146fbf860895bb71b793d278e7e354adc3d768",
        "no separate immutable", "does not promote the Windows replay", "Protected22/Lib2 was not accessed",
    ):
        if phrase not in doc:
            raise CurrentScientificSuccessorEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

    boundary = receipt["claim_boundary"]
    for key in (
        "new_model_fit", "protected22_access", "private_patient_arrays_read", "patient_level_rows_published",
        "bootstrap_independently_recomputed", "bootstrap_confirmatory", "windows_replay_machine_receipt_public",
        "windows_replay_independently_reproduced", "independent_validation_created", "biological_result_created",
        "accepted_kaggle_entry_changed", "netlify_changed", "finalist_status_claimed", "clinical_utility_claimed",
    ):
        same(boundary[key], False, "CLAIM_BOUNDARY: " + key)
    same(boundary["official_competition_score"], None, "BOUNDARY_NO_SCORE")

    for key, expected in (
        ("status", "PASS"), ("candidate_family", "orientation_specific_control_quality_rank1"),
        ("candidate_mse", 0.001042745722096212), ("candidate_p90", 0.037419695944064885),
        ("bandwidth07_patient_wins", 40), ("favorable_folds", 5), ("target_wins", 19),
        ("target_losses", 5), ("repeated_development", True), ("independent_validation", False),
        ("protected22_access", False), ("official_competition_score", None),
    ):
        same(record.get(key), expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "candidate_family": "orientation_specific_control_quality_rank1",
        "candidate_mse": 0.001042745722096212,
        "candidate_p90": 0.037419695944064885,
        "bandwidth07_patient_wins": 40,
        "favorable_folds": 5,
        "target_wins": 19,
        "target_losses": 5,
        "presentation_artifacts": len(EXPECTED_PRESENTATION),
        "repeated_development": True,
        "independent_validation": False,
        "protected22_access": False,
        "official_competition_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
