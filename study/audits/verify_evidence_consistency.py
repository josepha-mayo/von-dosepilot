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
    "structured_additive": "95651af89e64f12b771b23f202a8824430d965aec124a798c81c6a929e792af6",
    "lifecycle_acquisition": "7dc4b086a5609d7ce7cefcbb17231bddbb029ae413c15fe734649f42b9c799a2",
    "aligned_additive": "fca4fff12f931caa9dbc4c70f5ebc05668a743f18f7fac0fa3e030a99581a550",
    "bandwidth_successor": "a98b574217bb433b363ac6f8077032c036552268a09af129e2e038d8ba2c5758",
    "bandwidth_lifecycle": "e09203bc03e787a9285ba3b06cde968fe7ded71d8370e29aced722370af7a027",
    "frozen_ooc_release_binding": "bb2234239ff20484af50f6a5f0497934dc6ba4077f677deebdf12a33c6da28cf",
}

PINNED_DOCUMENTS = {
    "docs/EVIDENCE_LEDGER.md": "d393517b7733e8e2788cd63e6619175249a03e0a96aa0c71e2ecaaa05663147e",
    "docs/KAGGLE_WRITEUP.md": "da691ddf225508f786206851df852b9873052e8ec10b30b292be04649e54e16a",
}

CURRENT_REPORT_RECEIPT_SHA256 = "e6efd0143083efc36e612ae0887ba086f94640c951aee1d523832a9da7836101"


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
    if index.get("as_of_date") != "2026-10-03":
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

    report_index = index["current_technical_report"]
    same(report_index["sha256"], CURRENT_REPORT_RECEIPT_SHA256, "INDEX_CURRENT_REPORT_RECEIPT_PIN")
    report_receipt_path = root / report_index["path"]
    same(sha(report_receipt_path), report_index["sha256"], "CURRENT_REPORT_RECEIPT_HASH")
    current_report = load(report_receipt_path)
    same(current_report["schema"], "dosepilot.current_technical_report_release.v1", "CURRENT_REPORT_SCHEMA")
    same(current_report["status"], "PASS", "CURRENT_REPORT_STATUS")
    same(current_report["role"], "CURRENT_JUDGE_FACING_TECHNICAL_REPORT", "CURRENT_REPORT_ROLE")
    for part in ("entrypoint", "source", "pdf", "renderer"):
        record = current_report[part]
        same(sha(root / record["path"]), record["sha256"], "CURRENT_REPORT_FILE_HASH: " + record["path"])
    historical_report = current_report["historical_submitted_pdf"]
    same(sha(root / historical_report["path"]), historical_report["sha256"], "CURRENT_REPORT_HISTORICAL_HASH")
    same(historical_report["replaced"], False, "CURRENT_REPORT_HISTORICAL_PRESERVED")
    same((root / current_report["pdf"]["path"]).stat().st_size, current_report["pdf"]["bytes"], "CURRENT_REPORT_PDF_BYTES")
    same(current_report["pdf"]["pages"], 10, "CURRENT_REPORT_PAGES")
    same(current_report["pdf"]["blank_pages"], 0, "CURRENT_REPORT_NO_BLANK_PAGES")
    same(current_report["pdf"]["visual_review"], "PASS", "CURRENT_REPORT_VISUAL_REVIEW")
    same(current_report["renderer"]["invariant_output"], True, "CURRENT_REPORT_INVARIANT")
    same(current_report["renderer"]["two_consecutive_builds_byte_identical"], True, "CURRENT_REPORT_DETERMINISTIC")
    report_preflight_path = root / report_index["preflight_path"]
    same(sha(report_preflight_path), report_index["preflight_sha256"], "CURRENT_REPORT_PREFLIGHT_HASH")
    report_preflight = load(report_preflight_path)
    same(report_preflight["status"], report_index["preflight_status"], "CURRENT_REPORT_PREFLIGHT_STATUS")
    same(report_preflight["orchestrated_test_count"], report_index["preflight_response_free_tests"], "CURRENT_REPORT_PREFLIGHT_TESTS")
    same(report_preflight["private_or_protected_inputs_read"], False, "CURRENT_REPORT_PREFLIGHT_NO_PRIVATE")
    same(report_preflight["biological_accuracy_result_created"], False, "CURRENT_REPORT_PREFLIGHT_NO_ACCURACY")
    claim_checks = current_report["claim_checks"]
    same(claim_checks["bandwidth_successor_mse"], 0.0010582750420801538, "CURRENT_REPORT_MSE", 1e-15)
    same(claim_checks["protected22_primary"], "NOT_ESTIMABLE", "CURRENT_REPORT_PROTECTED22")
    same(claim_checks["release_preflight_tests"], 148, "CURRENT_REPORT_PREFLIGHT")
    for key in ("repeated_adaptive_development_disclosed", "adverse_target_slices_disclosed"):
        same(claim_checks[key], True, "CURRENT_REPORT_DISCLOSURE: " + key)
    same(claim_checks["prospective_ooc_experiment_claimed"], False, "CURRENT_REPORT_NO_OOC_CLAIM")
    same(claim_checks["official_competition_score"], None, "CURRENT_REPORT_NO_SCORE")
    for key in ("private_or_protected_inputs_read", "biological_accuracy_result_created", "accepted_kaggle_entry_changed"):
        same(current_report[key], False, "CURRENT_REPORT_BOUNDARY: " + key)
    for key in ("role", "status", "pages", "historical_submitted_pdf_replaced", "accepted_kaggle_entry_changed", "biological_accuracy_result_created"):
        receipt_value = {
            "role": current_report["role"],
            "status": current_report["status"],
            "pages": current_report["pdf"]["pages"],
            "historical_submitted_pdf_replaced": historical_report["replaced"],
            "accepted_kaggle_entry_changed": current_report["accepted_kaggle_entry_changed"],
            "biological_accuracy_result_created": current_report["biological_accuracy_result_created"],
        }[key]
        same(report_index[key], receipt_value, "INDEX_CURRENT_REPORT_" + key.upper())

    access = receipts["protected22_access"]
    completed = receipts["protected22_completed"]
    prior = receipts["protected22_prior_incomplete"]
    spectral = receipts["spectral_successor"]
    structured = receipts["structured_additive"]
    lifecycle = receipts["lifecycle_acquisition"]
    aligned = receipts["aligned_additive"]
    bandwidth = receipts["bandwidth_successor"]
    bandwidth_lifecycle = receipts["bandwidth_lifecycle"]
    frozen_schedule = receipts["frozen_ooc_release_binding"]
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

    # The current internal incumbent and its two later uses must agree across
    # independently pinned aggregate receipts.  These are same-task Lib1
    # development comparisons, never cross-study or external validation.
    same(structured["schema"], "dosepilot.structured_research_and_explicit_recovery.v1", "ADDITIVE_SCHEMA")
    research = structured["research"]
    additive_mse = research["mse"]["recovered_additive_control"]
    additive_p90 = research["p90_rmse"]["additive"]
    same(additive_mse, 0.001060552730112811, "ADDITIVE_MSE", 1e-15)
    same(research["new_independent_validation"], False, "ADDITIVE_NOT_INDEPENDENT")
    same(structured["protected_lib2_accessed"], False, "ADDITIVE_NO_LIB2")
    same(structured["official_score"], None, "ADDITIVE_NO_OFFICIAL_SCORE")

    additive_index = index["additive_incumbent"]
    same(
        additive_index["population"],
        {
            "samples": research["cohort"]["samples"],
            "patients": research["cohort"]["whole_patients"],
            "targets": research["cohort"]["targets"],
            "physical_wells_per_alternative": research["cohort"]["physical_wells_per_alternative"],
            "per_plate": research["cohort"]["per_plate"],
        },
        "INDEX_ADDITIVE_FRAME",
    )
    same(additive_index["role"], "REPEATED_ADAPTIVE_DEVELOPMENT", "INDEX_ADDITIVE_ROLE")
    same(additive_index["mse"], additive_mse, "INDEX_ADDITIVE_MSE", 1e-15)
    same(additive_index["p90_rmse"], additive_p90, "INDEX_ADDITIVE_P90", 1e-15)
    for reference, index_suffix in (("s2", "s2"), ("r13", "r13"), ("r18", "r18")):
        comparison = research["recovered_additive_control"]["vs_" + reference]
        same(
            additive_index["relative_gain_vs_" + index_suffix],
            comparison["relative_gain_percent"] / 100.0,
            "INDEX_ADDITIVE_GAIN_" + reference.upper(),
            1e-15,
        )
        same(
            additive_index["patient_wins_vs_" + index_suffix],
            comparison["patient_wins"],
            "INDEX_ADDITIVE_WINS_" + reference.upper(),
        )
        same(comparison["fold_wins"], 5, "ADDITIVE_FOLDS_" + reference.upper())
        pass_key = "all_successor_clauses_passed" if reference == "s2" else "all_original_clauses_passed"
        same(comparison[pass_key], True, "ADDITIVE_GATE_" + reference.upper())
    same(additive_index["fold_wins_vs_s2"], research["recovered_additive_control"]["vs_s2"]["fold_wins"], "INDEX_ADDITIVE_FOLDS")
    same(additive_index["independent_validation"], False, "INDEX_ADDITIVE_NOT_INDEPENDENT")
    same(additive_index["protected22_used"], False, "INDEX_ADDITIVE_NO_LIB2")
    same(additive_index["official_competition_score"], None, "INDEX_ADDITIVE_NO_SCORE")
    same(additive_index["current_internal_incumbent"], False, "INDEX_ADDITIVE_NOT_INCUMBENT")

    same(bandwidth["schema"], "dosepilot.bandwidth_additive_successor.v1", "BANDWIDTH_SCHEMA")
    same(bandwidth["status"], "PASSES_INCUMBENT_AND_HISTORICAL_DEVELOPMENT_SCREENS", "BANDWIDTH_STATUS")
    same(bandwidth["model_kind"], "dosepilot.additive_kernel_bandwidth.v1", "BANDWIDTH_MODEL_KIND")
    same(bandwidth["bandwidth_multiplier"], 0.7, "BANDWIDTH_MULTIPLIER")
    same(bandwidth["metrics"]["bandwidth07"]["mse"], 0.0010582750420801538, "BANDWIDTH_MSE", 1e-15)
    same(bandwidth["metrics"]["bandwidth07"]["p90_rmse"], 0.0378942853087202, "BANDWIDTH_P90", 1e-15)
    same(bandwidth["metrics"]["additive"]["mse"], additive_mse, "BANDWIDTH_ADDITIVE_REFERENCE", 1e-15)
    same(bandwidth["comparisons"]["additive"]["patient_wins"], 38, "BANDWIDTH_ADDITIVE_WINS")
    same(bandwidth["comparisons"]["additive"]["fold_wins"], 5, "BANDWIDTH_ADDITIVE_FOLDS")
    same(bandwidth["comparisons"]["additive"]["passes_all"], True, "BANDWIDTH_ADDITIVE_GATE")
    same(bandwidth["comparisons"]["r13"]["patient_wins"], 49, "BANDWIDTH_R13_WINS")
    same(bandwidth["comparisons"]["r13"]["passes_all"], True, "BANDWIDTH_R13_GATE")
    same(bandwidth["comparisons"]["r18"]["patient_wins"], 47, "BANDWIDTH_R18_WINS")
    same(bandwidth["comparisons"]["r18"]["passes_all"], True, "BANDWIDTH_R18_GATE")
    same(bandwidth["target_nonworse_vs_additive"], 14, "BANDWIDTH_TARGET_NONWORSE")
    same(bandwidth["repeated_adaptive_development"], True, "BANDWIDTH_REPEATED_DEVELOPMENT")
    same(bandwidth["independent_validation"], False, "BANDWIDTH_NOT_INDEPENDENT")
    same(bandwidth["protected_response_access"], False, "BANDWIDTH_NO_PROTECTED")
    same(bandwidth["official_competition_score"], None, "BANDWIDTH_NO_SCORE")
    bandwidth_index = index["bandwidth_successor"]
    same(bandwidth_index["role"], "REPEATED_ADAPTIVE_DEVELOPMENT", "INDEX_BANDWIDTH_ROLE")
    same(bandwidth_index["model_kind"], bandwidth["model_kind"], "INDEX_BANDWIDTH_MODEL_KIND")
    same(bandwidth_index["bandwidth_multiplier"], bandwidth["bandwidth_multiplier"], "INDEX_BANDWIDTH_MULTIPLIER")
    same(bandwidth_index["mse"], bandwidth["metrics"]["bandwidth07"]["mse"], "INDEX_BANDWIDTH_MSE", 1e-15)
    same(bandwidth_index["p90_rmse"], bandwidth["metrics"]["bandwidth07"]["p90_rmse"], "INDEX_BANDWIDTH_P90", 1e-15)
    same(bandwidth_index["additive_reference_mse"], additive_mse, "INDEX_BANDWIDTH_ADDITIVE", 1e-15)
    same(bandwidth_index["patient_wins_vs_additive"], bandwidth["comparisons"]["additive"]["patient_wins"], "INDEX_BANDWIDTH_ADDITIVE_WINS")
    same(bandwidth_index["fold_wins_vs_additive"], bandwidth["comparisons"]["additive"]["fold_wins"], "INDEX_BANDWIDTH_ADDITIVE_FOLDS")
    same(bandwidth_index["patient_wins_vs_r13"], bandwidth["comparisons"]["r13"]["patient_wins"], "INDEX_BANDWIDTH_R13_WINS")
    same(bandwidth_index["patient_wins_vs_r18"], bandwidth["comparisons"]["r18"]["patient_wins"], "INDEX_BANDWIDTH_R18_WINS")
    same(bandwidth_index["target_nonworse_vs_additive"], bandwidth["target_nonworse_vs_additive"], "INDEX_BANDWIDTH_TARGETS")
    same(bandwidth_index["passes_incumbent_gate"], True, "INDEX_BANDWIDTH_INCUMBENT_GATE")
    same(bandwidth_index["passes_internal_gate_vs_r13_and_r18"], True, "INDEX_BANDWIDTH_HISTORICAL_GATE")
    same(bandwidth_index["physical_plan_changed"], False, "INDEX_BANDWIDTH_PLAN")
    same(bandwidth_index["independent_validation"], False, "INDEX_BANDWIDTH_NOT_INDEPENDENT")
    same(bandwidth_index["protected22_used"], False, "INDEX_BANDWIDTH_NO_LIB2")
    same(bandwidth_index["official_competition_score"], None, "INDEX_BANDWIDTH_NO_SCORE")
    same(bandwidth_index["current_internal_incumbent"], True, "INDEX_BANDWIDTH_INCUMBENT")

    same(bandwidth_lifecycle["schema"], "dosepilot.bandwidth07_durable_lifecycle.v1", "BANDWIDTH_LIFECYCLE_SCHEMA")
    same(bandwidth_lifecycle["status"], "PASS", "BANDWIDTH_LIFECYCLE_STATUS")
    same(bandwidth_lifecycle["role"], "ENGINEERING_AND_REPRODUCIBILITY_EVIDENCE", "BANDWIDTH_LIFECYCLE_ROLE")
    same(bandwidth_lifecycle["model_kind"], bandwidth["model_kind"], "BANDWIDTH_LIFECYCLE_MODEL_KIND")
    same(bandwidth_lifecycle["bandwidth_multiplier"], bandwidth["bandwidth_multiplier"], "BANDWIDTH_LIFECYCLE_MULTIPLIER")
    same(bandwidth_lifecycle["lifecycle_policy"], "dosepilot.bandwidth07_complete_lifecycle.v1", "BANDWIDTH_LIFECYCLE_POLICY")
    lifecycle_verification = bandwidth_lifecycle["verification"]
    same(lifecycle_verification["new_bandwidth_lifecycle_tests"], 10, "BANDWIDTH_LIFECYCLE_NEW_TESTS")
    same(lifecycle_verification["durable_runtime_tests_total"], 65, "BANDWIDTH_LIFECYCLE_TOTAL_TESTS")
    same(lifecycle_verification["fictional_cli_invocations"], 6, "BANDWIDTH_LIFECYCLE_CLI_CALLS")
    same(lifecycle_verification["complete_primary_outputs"], 24, "BANDWIDTH_LIFECYCLE_OUTPUTS")
    same(lifecycle_verification["single_missing_primary_outputs"], 0, "BANDWIDTH_LIFECYCLE_MISSING_PRIMARY")
    same(lifecycle_verification["single_missing_historical_baseline_outputs"], 23, "BANDWIDTH_LIFECYCLE_BASELINE")
    for key in (
        "wrong_model_family_rejected", "wrong_bandwidth_rejected",
        "all_64_single_missing_positions_withheld",
        "changed_recorded_measurement_rejected",
        "lost_export_recovered_byte_identically", "historical_lifecycle_unmodified",
    ):
        same(lifecycle_verification[key], True, "BANDWIDTH_LIFECYCLE_" + key.upper())
    for path, expected in bandwidth_lifecycle["code_sha256"].items():
        same(sha(root / path), expected, "BANDWIDTH_LIFECYCLE_CODE_HASH: " + path)
    for key in (
        "accuracy_mse_changed", "new_model_fit", "new_biological_validation",
        "protected_response_access", "private_patient_arrays_read",
        "fitted_biological_weights_published", "accepted_kaggle_entry_changed",
    ):
        same(bandwidth_lifecycle[key], False, "BANDWIDTH_LIFECYCLE_FALSE_BOUNDARY: " + key)
    same(bandwidth_lifecycle["official_competition_score"], None, "BANDWIDTH_LIFECYCLE_NO_SCORE")
    current_lifecycle_index = index["bandwidth_lifecycle"]
    same(current_lifecycle_index["role"], bandwidth_lifecycle["role"], "INDEX_BANDWIDTH_LIFECYCLE_ROLE")
    same(current_lifecycle_index["model_kind"], bandwidth_lifecycle["model_kind"], "INDEX_BANDWIDTH_LIFECYCLE_MODEL")
    same(current_lifecycle_index["bandwidth_multiplier"], bandwidth_lifecycle["bandwidth_multiplier"], "INDEX_BANDWIDTH_LIFECYCLE_MULTIPLIER")
    same(current_lifecycle_index["policy"], bandwidth_lifecycle["lifecycle_policy"], "INDEX_BANDWIDTH_LIFECYCLE_POLICY")
    same(current_lifecycle_index["commands"], bandwidth_lifecycle["commands"], "INDEX_BANDWIDTH_LIFECYCLE_COMMANDS")
    for index_key, receipt_key in (
        ("new_adapter_tests", "new_bandwidth_lifecycle_tests"),
        ("durable_runtime_tests_total", "durable_runtime_tests_total"),
        ("fictional_cli_invocations", "fictional_cli_invocations"),
        ("single_missing_primary_predictions", "single_missing_primary_outputs"),
        ("single_missing_historical_baseline_estimates", "single_missing_historical_baseline_outputs"),
        ("wrong_model_family_rejected", "wrong_model_family_rejected"),
        ("wrong_bandwidth_rejected", "wrong_bandwidth_rejected"),
        ("lost_export_recovered_byte_identically", "lost_export_recovered_byte_identically"),
    ):
        same(current_lifecycle_index[index_key], lifecycle_verification[receipt_key], "INDEX_BANDWIDTH_LIFECYCLE_" + index_key.upper())
    same(current_lifecycle_index["new_biological_accuracy_improvement"], False, "INDEX_BANDWIDTH_LIFECYCLE_NO_ACCURACY")
    same(current_lifecycle_index["protected_response_access"], False, "INDEX_BANDWIDTH_LIFECYCLE_NO_PROTECTED")
    same(current_lifecycle_index["accepted_kaggle_entry_changed"], False, "INDEX_BANDWIDTH_LIFECYCLE_NO_ENTRY_CHANGE")
    same(current_lifecycle_index["official_competition_score"], None, "INDEX_BANDWIDTH_LIFECYCLE_NO_SCORE")

    same(frozen_schedule["schema"], "dosepilot.frozen_ooc_release_binding.v1", "FROZEN_SCHEDULE_SCHEMA")
    same(frozen_schedule["status"], "PASS", "FROZEN_SCHEDULE_STATUS")
    same(frozen_schedule["role"], "RESPONSE_FREE_ENGINEERING_AND_RELEASE_EVIDENCE", "FROZEN_SCHEDULE_ROLE")
    schedule_receipt = frozen_schedule["schedule_receipt"]
    same(sha(root / schedule_receipt["path"]), schedule_receipt["sha256"], "FROZEN_SCHEDULE_RECEIPT_HASH")
    for group in ("source_files_sha256", "audit_code_sha256", "public_surface_sha256"):
        for path, expected in frozen_schedule[group].items():
            same(sha(root / path), expected, "FROZEN_SCHEDULE_FILE_HASH: " + path)
    schedule_verification = frozen_schedule["verification"]
    same(schedule_verification["orientations"], 2, "FROZEN_SCHEDULE_ORIENTATIONS")
    same(schedule_verification["treatment_wells_per_orientation"], 64, "FROZEN_SCHEDULE_WELLS")
    same(schedule_verification["plate_counts_per_orientation"], {"p1": 32, "p2": 32}, "FROZEN_SCHEDULE_PLATES")
    same(schedule_verification["targets"], 24, "FROZEN_SCHEDULE_TARGETS")
    same(schedule_verification["two_dose_targets"], 8, "FROZEN_SCHEDULE_TWO_DOSE")
    same(schedule_verification["three_dose_targets"], 16, "FROZEN_SCHEDULE_THREE_DOSE")
    for key in ("ab_same_treatments", "ab_complementary_plate_assignment", "public_site_schedule_exact", "manifest_table_exact", "release_preflight_stage_added"):
        same(schedule_verification[key], True, "FROZEN_SCHEDULE_TRUE: " + key)
    same(schedule_verification["public_schedule_rows"], 64, "FROZEN_SCHEDULE_PUBLIC_ROWS")
    same(schedule_verification["transport_escape_literals"], 0, "FROZEN_SCHEDULE_ESCAPES")
    same(schedule_verification["new_tamper_tests"], 5, "FROZEN_SCHEDULE_TESTS")
    same(schedule_verification["new_tamper_tests_passed"], 5, "FROZEN_SCHEDULE_TESTS_PASS")
    same(schedule_verification["release_preflight_check_count"], 12, "FROZEN_SCHEDULE_PREFLIGHT_COUNT")
    same(schedule_verification["orchestrated_response_free_tests"], 148, "FROZEN_SCHEDULE_PREFLIGHT_ORCHESTRATED")
    for key in ("prospective_experiment_executed", "biological_validation_created", "protected_response_access", "private_patient_rows_read", "fitted_biological_weights_published", "accepted_kaggle_entry_changed"):
        same(frozen_schedule[key], False, "FROZEN_SCHEDULE_FALSE_BOUNDARY: " + key)
    same(frozen_schedule["official_competition_score"], None, "FROZEN_SCHEDULE_NO_SCORE")

    schedule_index = index["frozen_ooc_release_binding"]
    for key in ("role", "status"):
        same(schedule_index[key], frozen_schedule[key], "INDEX_FROZEN_SCHEDULE_" + key.upper())
    for key in ("treatment_wells_per_orientation", "plate_counts_per_orientation", "targets", "two_dose_targets", "three_dose_targets", "ab_same_treatments", "ab_complementary_plate_assignment", "public_schedule_rows", "public_site_schedule_exact", "manifest_table_exact", "transport_escape_literals", "new_tamper_tests_passed", "release_preflight_check_count", "orchestrated_response_free_tests"):
        same(schedule_index[key], schedule_verification[key], "INDEX_FROZEN_SCHEDULE_" + key.upper())
    for key in ("prospective_experiment_executed", "biological_validation_created", "protected_response_access", "private_patient_rows_read", "accepted_kaggle_entry_changed", "official_competition_score"):
        same(schedule_index[key], frozen_schedule[key], "INDEX_FROZEN_SCHEDULE_BOUNDARY_" + key.upper())

    same(aligned["schema"], "dosepilot.residual_alignment_additive.v1", "RAW_AK_SCHEMA")
    same(aligned["status"], "COMPLETE", "RAW_AK_STATUS")
    same(aligned["decision"], "REJECT_RETAIN_ADDITIVE", "RAW_AK_DECISION")
    same(aligned["metrics"]["additive"]["mse"], additive_mse, "RAW_AK_ADDITIVE_REFERENCE", 1e-15)
    same(aligned["metrics"]["raw_ak"]["mse"] > additive_mse, True, "RAW_AK_NOT_LOWER")
    same(aligned["raw_ak_vs_additive"]["passes_all"], False, "RAW_AK_GATE_FAILED")
    same(all(value is False for value in aligned["raw_ak_vs_additive"]["gate"].values()), True, "RAW_AK_ALL_CLAUSES_FAILED")
    same(aligned["repeated_adaptive_development"], True, "RAW_AK_REPEATED_DEVELOPMENT")
    same(aligned["independent_validation"], False, "RAW_AK_NOT_INDEPENDENT")
    same(aligned["protected_response_access"], False, "RAW_AK_NO_PROTECTED")
    same(aligned["official_competition_score"], None, "RAW_AK_NO_SCORE")
    raw_index = index["raw_ak_challenger"]
    same(raw_index["status"], aligned["status"], "INDEX_RAW_AK_STATUS")
    same(raw_index["decision"], aligned["decision"], "INDEX_RAW_AK_DECISION")
    same(raw_index["role"], "REPEATED_ADAPTIVE_DEVELOPMENT_NEGATIVE_RESULT", "INDEX_RAW_AK_ROLE")
    same(raw_index["mse"], aligned["metrics"]["raw_ak"]["mse"], "INDEX_RAW_AK_MSE", 1e-15)
    same(raw_index["additive_reference_mse"], aligned["metrics"]["additive"]["mse"], "INDEX_RAW_AK_REFERENCE", 1e-15)
    same(raw_index["mse_change_percent"], aligned["raw_ak_vs_additive"]["mse_change_percent"], "INDEX_RAW_AK_CHANGE", 1e-15)
    for key in ("patient_wins", "patient_losses", "patient_ties", "fold_wins"):
        same(raw_index[key], aligned["raw_ak_vs_additive"][key], "INDEX_RAW_AK_" + key.upper())
    same(raw_index["p90_nonworse"], aligned["raw_ak_vs_additive"]["gate"]["p90_nonworse"], "INDEX_RAW_AK_P90")
    same(raw_index["target_regressions"], len(aligned["target_regressions_vs_additive"]), "INDEX_RAW_AK_TARGET_REGRESSIONS")
    same(raw_index["patient_regressions"], aligned["patient_regression_count_vs_additive"], "INDEX_RAW_AK_PATIENT_REGRESSIONS")
    same(raw_index["passes_incumbent_gate"], aligned["raw_ak_vs_additive"]["passes_all"], "INDEX_RAW_AK_GATE")
    same(raw_index["automatic_retry"], aligned["automatic_retry"], "INDEX_RAW_AK_NO_RETRY")
    same(raw_index["independent_validation"], aligned["independent_validation"], "INDEX_RAW_AK_NOT_INDEPENDENT")
    same(raw_index["protected_response_access"], aligned["protected_response_access"], "INDEX_RAW_AK_NO_PROTECTED")
    same(raw_index["official_competition_score"], aligned["official_competition_score"], "INDEX_RAW_AK_NO_SCORE")

    same(lifecycle["schema"], "dosepilot.durable_lifecycle_and_acquisition.v1", "LIFECYCLE_SCHEMA")
    same(lifecycle["accuracy_incumbent"]["mse"], additive_mse, "LIFECYCLE_ADDITIVE_REFERENCE", 1e-15)
    same(lifecycle["accuracy_incumbent"]["unchanged"], True, "LIFECYCLE_ACCURACY_UNCHANGED")
    lifecycle_record = lifecycle["new_lifecycle"]
    lifecycle_index = index["durable_lifecycle"]
    same(lifecycle_index["role"], "ENGINEERING_AND_REPRODUCIBILITY_EVIDENCE", "INDEX_LIFECYCLE_ROLE")
    same(lifecycle_index["policy"], lifecycle_record["policy"], "INDEX_LIFECYCLE_POLICY")
    same(lifecycle_index["commands"], lifecycle_record["commands"], "INDEX_LIFECYCLE_COMMANDS")
    same(lifecycle_index["durable_runtime_tests"], lifecycle["tests"]["durable_runtime_suite_including_previous_cases"], "INDEX_LIFECYCLE_TESTS")
    same(lifecycle_index["single_missing_primary_predictions"], lifecycle_record["missing_case_primary_predictions"], "INDEX_LIFECYCLE_PRIMARY_WITHHELD")
    same(lifecycle_index["single_missing_baseline_estimates"], lifecycle_record["single_missing_baseline_estimates"], "INDEX_LIFECYCLE_BASELINES")
    for index_key, receipt_key in (
        ("affected_head_withheld", "affected_head_withheld"),
        ("missing_value_imputation", "missing_value_imputation"),
        ("automatic_recovery_history_check_on_predict", "automatic_recovery_history_check_on_predict"),
        ("tested_platform", "tested_platform"),
        ("physical_power_loss_certification", "physical_power_loss_certification"),
        ("noncooperating_manual_edits_prevented", "noncooperating_manual_edits_prevented"),
    ):
        same(lifecycle_index[index_key], lifecycle_record[receipt_key], "INDEX_LIFECYCLE_" + index_key.upper())
    same(lifecycle_index["warm_prediction_speedup"], lifecycle["recovered_compiled_runtime"]["speedup"], "INDEX_LIFECYCLE_SPEEDUP", 1e-15)
    same(lifecycle_index["end_to_end_cli_speedup_claimed"], lifecycle["recovered_compiled_runtime"]["end_to_end_cli_speedup_claimed"], "INDEX_LIFECYCLE_NOT_CLI_SPEED")
    for key in ("new_biological_accuracy_improvement", "accepted_kaggle_entry_changed", "protected_data_status_changed"):
        same(lifecycle_index[key], lifecycle[key], "INDEX_LIFECYCLE_" + key.upper())
    same(lifecycle_index["official_competition_score"], lifecycle["official_score"], "INDEX_LIFECYCLE_NO_SCORE")

    for relative_path, expected_hash in PINNED_DOCUMENTS.items():
        if sha(root / relative_path) != expected_hash:
            raise EvidenceError("PINNED_DOCUMENT_HASH: " + relative_path)
    ledger = (root / "docs/EVIDENCE_LEDGER.md").read_text()
    ledger_required = [
        "Reconciled 3 October 2026",
        "Completed Protected22 missingness execution",
        "S2 spectral residual successor",
        "Previous additive drug-group kernel",
        "MSE 0.0010605527 is 0.8963% below S2",
        "Bandwidth-0.7 additive successor",
        "MSE 0.0010582750 is 0.2148% below additive",
        "38/59 patient wins, 5/5 favorable folds",
        "Residual-alignment additive challenger",
        "MSE 0.0010608378 is 0.0269% worse than additive",
        "Current bandwidth-0.7 lifecycle",
        "Ten current-model adapter tests",
        "Durable predecessor additive-1.0 lifecycle",
        "65 tests",
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
        "0.0010605527",
        "Bandwidth-0.7 additive successor",
        "0.0010582750",
        "38/59 patient means and all 5/5 outer folds versus additive",
        "0.0010608378",
        "0.0269% worse than additive",
        "24/59 patient wins, 2/5 favorable folds, worse p90",
        "durable CLI now has an explicit bandwidth-0.7 path",
        "rejects additive-1.0 artifacts and wrong bandwidth metadata",
        "23 unaffected estimates when one reading is missing",
        "bandwidth-0.7 primary itself requires all 64 readings",
        "65 durable-runtime tests pass in total",
        "not another biological accuracy test",
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
        "The additive incumbent is independent validation",
        "The bandwidth-0.7 successor is independent validation",
        "The residual-alignment challenger is promoted",
        "The durable lifecycle is new biological evidence",
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
        "additive_incumbent_mse": additive_mse,
        "bandwidth_successor_mse": bandwidth["metrics"]["bandwidth07"]["mse"],
        "bandwidth_lifecycle_tests": lifecycle_verification["durable_runtime_tests_total"],
        "frozen_ooc_schedule_rows": schedule_verification["public_schedule_rows"],
        "frozen_ooc_schedule_tamper_tests": schedule_verification["new_tamper_tests_passed"],
        "current_report_pages": current_report["pdf"]["pages"],
        "current_report_deterministic": current_report["renderer"]["two_consecutive_builds_byte_identical"],
        "raw_ak_decision": aligned["decision"],
        "durable_runtime_tests": lifecycle["tests"]["durable_runtime_suite_including_previous_cases"],
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
