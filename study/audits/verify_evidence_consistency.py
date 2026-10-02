#!/usr/bin/env python3
"""Verify the normalized public evidence index against canonical receipts.

This checker reads aggregate public JSON and Markdown only.  It does not open a
workbook, fitted model, patient-level array, or prediction array.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


class EvidenceError(ValueError):
    pass


PINNED_RECEIPTS = {
    "protected22_access": "02ad1bb10be00d0c26fa02589b9b1fc84b670c107110985f155646b11921c7d8",
    "protected22_completed": "0bf74c4398c73e22cdb67cd1080a70a97c0607ab944cfbb7eb0eaf2a412fd7ba",
    "protected22_prior_incomplete": "7393b0de4fdd8a34191ea1afe1822d3a7f7a042db6ab84f35160be739a9e204f",
    "spectral_successor": "71e1de87f55010579c0b2e6f59fe408813ef039a5310d1ebdba0d9f3b99bceaa",
}

PINNED_DOCUMENTS = {
    "docs/EVIDENCE_LEDGER.md": "2f4f56df93cde210c68e0c09b62c8e0d915b62035c59e9866fd0f117a10d1599",
    "docs/KAGGLE_WRITEUP.md": "e7807b78879cf7697710ccaaac525937f4570797a65479a0d6ffb71c56435f57",
}


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(actual, expected, label, tolerance=0.0):
    if isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
            raise EvidenceError(label)
    elif actual != expected:
        raise EvidenceError(label)


def verify(root, enforce_pins=True):
    root = Path(root)
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    if index.get("schema") != "dosepilot.evidence_index.v1":
        raise EvidenceError("INDEX_SCHEMA")
    if index.get("as_of_date") != "2026-10-02":
        raise EvidenceError("INDEX_DATE")
    if index.get("cross_study_raw_mse_comparison_allowed") is not False:
        raise EvidenceError("CROSS_STUDY_MSE_RULE")
    receipts = {}
    for name, record in index["canonical_receipts"].items():
        if name not in PINNED_RECEIPTS:
            raise EvidenceError("UNKNOWN_RECEIPT: " + name)
        if enforce_pins and record["sha256"] != PINNED_RECEIPTS[name]:
            raise EvidenceError("PINNED_RECEIPT_HASH: " + name)
        path = root / record["path"]
        if sha(path) != record["sha256"]:
            raise EvidenceError("RECEIPT_HASH: " + name)
        receipts[name] = load(path)

    access = receipts["protected22_access"]
    completed = receipts["protected22_completed"]
    prior = receipts["protected22_prior_incomplete"]
    spectral = receipts["spectral_successor"]
    normalized = index["protected22"]
    same(
        normalized["future_interpretation"],
        "All 61 PDOs and 31 patients are exposed. There is no estimable frozen full-cohort primary and no untouched confirmation; the 29-patient result is a prespecified conditional diagnostic only.",
        "INDEX_FUTURE_INTERPRETATION",
    )

    same(access["status"], "EXPOSED_DO_NOT_TREAT_AS_HOLDOUT", "ACCESS_STATUS")
    same(access["all_planned_records_processed_by_current_run"], True, "ALL_PROCESSED")
    same(access["automatic_retry_authorized"], False, "NO_RETRY")
    same(access["independent_confirmation"], False, "NO_INDEPENDENT_CONFIRMATION")
    same(completed["status"], "PRIMARY_NOT_ESTIMABLE", "PRIMARY_STATUS")
    same(completed["full_primary_estimable"], False, "PRIMARY_ESTIMABLE")
    same(completed["primary"], None, "PRIMARY_NULL")
    same(completed["confirmation_passed"], False, "CONFIRMATION_FALSE")
    same(completed["new_untouched_subset_created"], False, "NO_NEW_UNTOUCHED_SUBSET")
    same(completed["official_score"], None, "NO_OFFICIAL_SCORE")
    same(
        completed["prior_project_exposure"]["current_run_untouched_confirmation"],
        False,
        "NOT_UNTOUCHED",
    )

    cells = completed["access"]
    if cells["numeric_cells"] + cells["unavailable_cells"] != cells["authorized_cells"]:
        raise EvidenceError("CELL_ARITHMETIC")
    same(cells["cells_accessed"], cells["authorized_cells"], "ALL_AUTHORIZED_ACCESSED")
    same(access["numeric_cells"], cells["numeric_cells"], "ACCESS_NUMERIC")
    same(access["unavailable_cells"], cells["unavailable_cells"], "ACCESS_UNAVAILABLE")
    same(completed["original_frame"], {"pdos": 61, "patients": 31, "targets": 22}, "FRAME")
    same(normalized["population"], completed["original_frame"], "INDEX_FRAME")

    conditional = completed["complete_patient_conditional"]
    same(completed["pdos_in_complete_patients"], 54, "CONDITIONAL_PDOS")
    same(conditional["patients"], 29, "CONDITIONAL_PATIENTS")
    same(conditional["candidate_mse"], 0.0017349426720150692, "CONDITIONAL_CANDIDATE", 1e-15)
    same(conditional["comparator_mse"], 0.002268954667464861, "CONDITIONAL_COMPARATOR", 1e-15)
    same(conditional["strict_patient_wins"], 26, "CONDITIONAL_WINS")
    same(conditional["strict_patient_losses"], 3, "CONDITIONAL_LOSSES")
    same(conditional["target_nonworse"], 16, "CONDITIONAL_TARGETS")

    same(prior["status"], "INCOMPLETE_NO_EFFICACY_SCORE", "PRIOR_STATUS")
    same(prior["execution"]["samples_reached"], 15, "PRIOR_PDOS")
    same(prior["execution"]["whole_patients_reached"], 9, "PRIOR_PATIENTS")
    same(prior["execution"]["predictions_constructed"], False, "PRIOR_NO_PREDICTIONS")
    same(prior["execution"]["efficacy_metrics_constructed"], False, "PRIOR_NO_METRICS")
    same(
        completed["prior_project_exposure"]["source_receipt"],
        index["canonical_receipts"]["protected22_prior_incomplete"]["path"],
        "PRIOR_LINK",
    )
    normalized_prior = normalized["prior_incomplete_attempt"]
    same(normalized_prior["status"], prior["status"], "INDEX_PRIOR_STATUS")
    same(normalized_prior["pdos_reached"], prior["execution"]["samples_reached"], "INDEX_PRIOR_PDOS")
    same(normalized_prior["patients_reached"], prior["execution"]["whole_patients_reached"], "INDEX_PRIOR_PATIENTS")
    same(normalized_prior["predictions_constructed"], prior["execution"]["predictions_constructed"], "INDEX_PRIOR_PREDICTIONS")
    same(normalized_prior["efficacy_metrics_constructed"], prior["execution"]["efficacy_metrics_constructed"], "INDEX_PRIOR_METRICS")
    same(normalized_prior["retained_separately"], True, "INDEX_PRIOR_SEPARATE")

    observed = normalized["completed_missingness_execution"]["observed_gate"]
    normalized_completed = normalized["completed_missingness_execution"]
    same(normalized_completed["status"], completed["status"], "INDEX_COMPLETED_STATUS")
    same(normalized_completed["primary"], completed["primary"], "INDEX_PRIMARY")
    same(normalized_completed["untouched_confirmation"], False, "INDEX_UNTOUCHED")
    same(normalized["access"]["authorized_cells"], cells["authorized_cells"], "INDEX_AUTHORIZED")
    same(normalized["access"]["accessed_cells"], cells["cells_accessed"], "INDEX_ACCESSED")
    same(normalized["access"]["numeric_cells"], cells["numeric_cells"], "INDEX_NUMERIC")
    same(normalized["access"]["unavailable_cells"], cells["unavailable_cells"], "INDEX_UNAVAILABLE")
    same(normalized["access"]["all_records_exposed"], True, "INDEX_EXPOSED")
    same(normalized["access"]["automatic_retry_authorized"], False, "INDEX_NO_RETRY")
    same(observed["full_primary_estimable"], False, "INDEX_OBSERVED_PRIMARY")
    same(observed["candidate_mse_lower"], None, "INDEX_OBSERVED_CANDIDATE")
    same(observed["p90_nonworse"], None, "INDEX_OBSERVED_P90")
    same(observed["strict_patient_wins"], None, "INDEX_OBSERVED_WINS")
    same(observed["target_nonworse"], None, "INDEX_OBSERVED_TARGETS")
    same(observed["confirmation_passed"], False, "INDEX_OBSERVED_PASS")
    requirements = normalized_completed["gate_requirements"]
    fixed = completed["fixed_gate"]
    same(requirements["full_primary_must_be_estimable"], fixed["full_primary_estimable"], "INDEX_GATE_PRIMARY_REQUIREMENT")
    same(requirements["strict_patient_wins_min"], fixed["strict_patient_wins_min"], "INDEX_GATE_WINS_REQUIREMENT")
    same(requirements["target_nonworse_min"], fixed["target_nonworse_min"], "INDEX_GATE_TARGET_REQUIREMENT")
    same(requirements["candidate_mse_must_be_lower"], fixed["candidate_mse_lower"], "INDEX_GATE_MSE_REQUIREMENT")
    same(requirements["p90_must_be_nonworse"], fixed["p90_nonworse"], "INDEX_GATE_P90_REQUIREMENT")
    same(
        normalized_completed["conditional_diagnostic_is_primary"],
        False,
        "CONDITIONAL_NOT_PRIMARY",
    )
    normalized_conditional = normalized_completed["conditional_diagnostic"]
    same(normalized_conditional["pdos"], completed["pdos_in_complete_patients"], "INDEX_CONDITIONAL_PDOS")
    same(normalized_conditional["patients"], conditional["patients"], "INDEX_CONDITIONAL_PATIENTS")
    same(normalized_conditional["candidate_mse"], conditional["candidate_mse"], "INDEX_CONDITIONAL_CANDIDATE", 1e-15)
    same(normalized_conditional["comparator_mse"], conditional["comparator_mse"], "INDEX_CONDITIONAL_COMPARATOR", 1e-15)
    same(normalized_conditional["strict_patient_wins"], conditional["strict_patient_wins"], "INDEX_CONDITIONAL_WINS")
    same(normalized_conditional["strict_patient_losses"], conditional["strict_patient_losses"], "INDEX_CONDITIONAL_LOSSES")
    same(normalized_conditional["target_nonworse"], conditional["target_nonworse"], "INDEX_CONDITIONAL_NONWORSE")
    same(normalized_conditional["targets"], completed["original_frame"]["targets"], "INDEX_CONDITIONAL_TARGETS")

    same(spectral["scientific_status"], "PASSES_UNCHANGED_INTERNAL_DEVELOPMENT_SCREEN", "S2_STATUS")
    same(spectral["original_frame"]["samples"], 119, "S2_SAMPLES")
    same(spectral["original_frame"]["whole_patients"], 59, "S2_PATIENTS")
    same(spectral["original_frame"]["targets"], 24, "S2_TARGETS")
    same(spectral["original_frame"]["physical_wells_per_alternative"], 64, "S2_WELLS")
    same(spectral["metrics"]["r13_soft"]["mse"], 0.0010701439454817465, "S2_MSE", 1e-15)
    same(spectral["new_independent_validation"], False, "S2_NOT_INDEPENDENT")
    same(spectral["protected_lib2_used"], False, "S2_NO_LIB2")
    same(spectral["official_score"], None, "S2_NO_OFFICIAL_SCORE")
    spectral_index = index["spectral_successor"]
    same(
        spectral_index["population"],
        {
            "samples": spectral["original_frame"]["samples"],
            "patients": spectral["original_frame"]["whole_patients"],
            "targets": spectral["original_frame"]["targets"],
            "physical_wells_per_alternative": spectral["original_frame"]["physical_wells_per_alternative"],
        },
        "INDEX_S2_FRAME",
    )
    same(spectral_index["role"], "REPEATED_ADAPTIVE_DEVELOPMENT", "INDEX_S2_ROLE")
    same(spectral_index["independent_validation"], False, "INDEX_S2_NOT_INDEPENDENT")
    same(spectral_index["protected22_used"], False, "INDEX_S2_NO_LIB2")
    same(spectral_index["official_competition_score"], None, "INDEX_S2_NO_SCORE")
    same(spectral_index["mse"], spectral["metrics"]["r13_soft"]["mse"], "INDEX_S2_MSE", 1e-15)
    same(spectral_index["r13_mse"], spectral["metrics"]["r13"]["mse"], "INDEX_R13_MSE", 1e-15)
    same(spectral_index["r18_mse"], spectral["metrics"]["r18"]["mse"], "INDEX_R18_MSE", 1e-15)
    same(spectral_index["patient_wins_vs_r13"], spectral["comparisons"]["r13"]["patient_wins"], "INDEX_S2_R13_WINS")
    same(spectral_index["patient_wins_vs_r18"], spectral["comparisons"]["r18"]["patient_wins"], "INDEX_S2_R18_WINS")
    same(spectral_index["fold_wins_vs_each"], 5, "INDEX_S2_FOLDS")
    all_gates = all(
        all(comparison["gate"].values())
        for comparison in spectral["comparisons"].values()
    )
    same(spectral_index["passes_internal_gate_vs_r13_and_r18"], all_gates, "INDEX_S2_GATE")

    for relative_path, expected_hash in PINNED_DOCUMENTS.items():
        if sha(root / relative_path) != expected_hash:
            raise EvidenceError("PINNED_DOCUMENT_HASH: " + relative_path)
    ledger = (root / "docs/EVIDENCE_LEDGER.md").read_text()
    ledger_required = [
        "Reconciled 2 October 2026",
        "Completed Protected22 missingness execution",
        "S2 spectral residual successor",
        "All 61 PDOs and 31 patients are exposed",
        "no estimable frozen full-cohort Lib2 primary",
        "conditional diagnostic",
        "0.0017349427 versus 0.0022689547",
        "26/29 patient wins and 16/22 target errors nonworse",
        "0.0010701439",
        "49/59 and 47/59 patient wins",
    ]
    for phrase in ledger_required:
        if phrase not in ledger:
            raise EvidenceError("LEDGER_MISSING: " + phrase)
    if "project therefore has **no Lib2 efficacy score**" in ledger:
        raise EvidenceError("LEDGER_STALE_NO_SCORE_CLAIM")
    writeup = (root / "docs/KAGGLE_WRITEUP.md").read_text()
    writeup_required = [
        "S2 spectral residual successor",
        "0.0010701439",
        "6.53% below R13 and 6.24% below",
        "49/59 patient means versus R13 and 47/59 versus R18",
        "19,642",
        "primary is **NOT_ESTIMABLE**",
        "54 PDOs from 29 patients",
        "0.0017349427",
        "0.0022689547",
        "not independent confirmation",
    ]
    for phrase in writeup_required:
        if phrase not in writeup:
            raise EvidenceError("WRITEUP_MISSING: " + phrase)
    forbidden = [
        "S2 is independent prospective confirmation",
        "S2 is an official competition score",
        "Protected22 confirmation passed",
    ]
    for phrase in forbidden:
        if phrase in writeup:
            raise EvidenceError("WRITEUP_FORBIDDEN: " + phrase)
    return {
        "status": "PASS",
        "canonical_receipts": len(receipts),
        "protected22_cells_reconciled": cells["authorized_cells"],
        "spectral_mse": spectral["metrics"]["r13_soft"]["mse"],
        "private_arrays_read": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.root)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            parser.error("Output exists; choose a fresh path")
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
