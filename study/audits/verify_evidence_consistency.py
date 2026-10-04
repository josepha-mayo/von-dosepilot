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
import re
from pathlib import Path

from verify_finalist_rubric_evidence import (
    RubricEvidenceError,
    verify as verify_finalist_rubric_evidence,
)


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
    "cross_patient_bandwidth": "3293f76dfc7e48f81087d971864066dc4b6c8d257b4d9fdc8d464b8396562caf",
    "simplex_stacking": "8af8887860ef738c2657f100a1a5031e02309b718ac1bd10473c319c0b0e3464",
    "isotonic_paid_features": "01934ca5139a219814572bd5b3e28923c98b8ad37ee3146a405f5ddd247476da",
    "bandwidth_lifecycle": "e09203bc03e787a9285ba3b06cde968fe7ded71d8370e29aced722370af7a027",
    "frozen_ooc_release_binding": "cd503cc69c8026d60c52a85e5e5970c2d66f6ecbba38579b4a6551cca607b1c3",
    "target_definitions_release": "57c6a5d2e443f6669981bd321e5b3ecf9ba1efcec74df86511bf0507760796dc",
    "reviewer_path_release": "4a68f8b0e2d1d4b586979f97f83120c54ad781a8091ffdd60f72bd9c9d701e56",
    "development_search_governance": "8dfc4b3fbcfdf8f45cb626edb872fc240b4add41fccfbace350499246aabecce",
}

PINNED_DOCUMENTS = {
    "docs/EVIDENCE_LEDGER.md": "012da3d9fb39b240e7161fc05e96d904c185e0df975002642ffa6044c2c50e1a",
    "docs/KAGGLE_WRITEUP.md": "f3de611b5bc3bf951a6f0766f7f087f399c58d3dadc35350845447440b988d3d",
}

CURRENT_REPORT_RECEIPT_SHA256 = "8179b404fca98bc7117fecbab352db4f4c339ddae04fb7f6a560ff8961ee9cdf"


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


def ensure_portable_kaggle_links(text):
    """Kaggle-rendered Markdown must not rely on GitHub-relative targets."""
    targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    nonportable = [
        target
        for target in targets
        if not target.startswith(("https://", "http://", "mailto:", "#"))
    ]
    if nonportable:
        raise EvidenceError("KAGGLE_WRITEUP_NONPORTABLE_LINK: " + nonportable[0])


def ensure_current_quickstart(readme, reviewer, writeup):
    current_demo = "study/durable_runtime/run_bandwidth_lifecycle_demo.py"
    current_preflight = "study/audits/release_preflight_current.py"
    current_verifier = "study/audits/verify_evidence_consistency.py --root ."
    if current_demo not in readme:
        raise EvidenceError("README_CURRENT_DEMO")
    if current_preflight not in readme:
        raise EvidenceError("README_CURRENT_PREFLIGHT")
    if "python -m pip install -r study/requirements.txt" not in readme:
        raise EvidenceError("README_PREFLIGHT_DEPENDENCIES")
    if current_verifier not in reviewer:
        raise EvidenceError("REVIEWER_CURRENT_VERIFIER")
    if current_demo not in writeup:
        raise EvidenceError("WRITEUP_CURRENT_DEMO")


def verify(root, enforce_pins=True):
    root = Path(root)
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    if index.get("schema") != "dosepilot.evidence_index.v1":
        raise EvidenceError("INDEX_SCHEMA")
    if index.get("as_of_date") != "2026-10-04":
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
    same(current_report["schema"], "dosepilot.current_technical_report_release.v4", "CURRENT_REPORT_SCHEMA")
    same(current_report["status"], "PASS", "CURRENT_REPORT_STATUS")
    same(current_report["role"], "CURRENT_JUDGE_FACING_TECHNICAL_REPORT", "CURRENT_REPORT_ROLE")
    report_predecessor = current_report["predecessor"]
    same(sha(root / report_predecessor["path"]), report_predecessor["sha256"], "CURRENT_REPORT_PREDECESSOR_HASH")
    same(report_predecessor["preserved_unchanged"], True, "CURRENT_REPORT_PREDECESSOR_PRESERVED")
    report_entrypoint_text = (root / current_report["entrypoint"]["path"]).read_text()
    if report_index["path"] not in report_entrypoint_text:
        raise EvidenceError("CURRENT_REPORT_ENTRYPOINT_STALE_RECEIPT_LINK")
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
    same(claim_checks["cross_patient_bandwidth_decision"], "REJECT_RETAIN_BANDWIDTH07", "CURRENT_REPORT_CPM_DECISION")
    same(claim_checks["cross_patient_bandwidth_mse"], 0.0010574875414830203, "CURRENT_REPORT_CPM_MSE", 1e-15)
    same(claim_checks["cross_patient_bandwidth_fold_wins"], 4, "CURRENT_REPORT_CPM_FOLDS")
    same(claim_checks["cross_patient_bandwidth_target_regressions"], 9, "CURRENT_REPORT_CPM_TARGETS")
    same(claim_checks["release_preflight_tests"], 168, "CURRENT_REPORT_PREFLIGHT")
    same(claim_checks["release_preflight_stages"], 14, "CURRENT_REPORT_PREFLIGHT_STAGES")
    same(claim_checks["bandwidth_point_estimate_post_selection"], True, "CURRENT_REPORT_SELECTION_DISCLOSURE")
    same(claim_checks["ab_expected_loss_uniform_assignment"], True, "CURRENT_REPORT_AB_ESTIMAND")
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

    target_release = receipts["target_definitions_release"]
    same(target_release["schema"], "dosepilot.target_definitions_release.v1", "TARGET_DEFINITIONS_SCHEMA")
    same(target_release["status"], "PASS", "TARGET_DEFINITIONS_STATUS")
    same(target_release["role"], "RESPONSE_FREE_ENDPOINT_AND_MEASUREMENT_CONTRACT", "TARGET_DEFINITIONS_ROLE")
    for path, expected in target_release["source_sha256"].items():
        same(sha(root / path), expected, "TARGET_DEFINITIONS_FILE_HASH: " + path)
    target_population = target_release["population"]
    same(target_population, {"samples": 119, "whole_patients": 59, "targets": 24}, "TARGET_DEFINITIONS_POPULATION")
    target_endpoint = target_release["endpoint"]
    same(target_endpoint["kind"], "unclipped normalized log-dose trapezoidal AUC", "TARGET_DEFINITIONS_ENDPOINT")
    same(target_endpoint["target_aggregation"], "arithmetic mean of separately computed p1 and p2 AUCs", "TARGET_DEFINITIONS_AGGREGATION")
    for key in ("clinical_response_endpoint", "ic50_endpoint", "drug_ranking_endpoint"):
        same(target_endpoint[key], False, "TARGET_DEFINITIONS_FALSE_ENDPOINT: " + key)
    accounting = target_release["measurement_accounting"]
    same(accounting["full_source_nodes_one_plate"], 208, "TARGET_DEFINITIONS_ONE_PLATE")
    same(accounting["full_source_treatment_measurements_two_plates"], 416, "TARGET_DEFINITIONS_FULL_MEASUREMENTS")
    same(accounting["selected_measurements_per_deployment"], 64, "TARGET_DEFINITIONS_SELECTED")
    same(accounting["selected_per_plate"], {"p1": 32, "p2": 32}, "TARGET_DEFINITIONS_PLATES")
    same(accounting["two_dose_targets"], 8, "TARGET_DEFINITIONS_TWO_DOSE")
    same(accounting["three_dose_targets"], 16, "TARGET_DEFINITIONS_THREE_DOSE")
    target_verification = target_release["verification"]
    same(target_verification["response_free_verifier_status"], "PASS", "TARGET_DEFINITIONS_VERIFIER")
    same(target_verification["quadrature_weights_verified"], True, "TARGET_DEFINITIONS_QUADRATURE")
    same(target_verification["target_table_rows_verified"], 24, "TARGET_DEFINITIONS_TABLE")
    same(target_verification["tamper_tests_passed"], 7, "TARGET_DEFINITIONS_TESTS")
    same(target_verification["public_train_byte_identical_reproduction"], True, "TARGET_DEFINITIONS_REPRODUCTION")
    same(target_verification["viability_values_numerically_converted_by_reproducer"], 0, "TARGET_DEFINITIONS_NO_RESPONSES")
    target_scope = target_release["scope"]
    for key in ("new_model_fit", "biological_accuracy_result_created", "independent_validation", "protected_response_access", "private_patient_rows_read", "fitted_biological_weights_published", "accepted_kaggle_entry_changed"):
        same(target_scope[key], False, "TARGET_DEFINITIONS_SCOPE: " + key)
    same(target_scope["official_competition_score"], None, "TARGET_DEFINITIONS_NO_SCORE")
    target_index = index["target_definitions"]
    for key, receipt_value in (
        ("role", target_release["role"]),
        ("status", target_release["status"]),
        ("targets", target_population["targets"]),
        ("full_source_treatment_measurements_two_plates", accounting["full_source_treatment_measurements_two_plates"]),
        ("selected_measurements_per_deployment", accounting["selected_measurements_per_deployment"]),
        ("selected_per_plate", accounting["selected_per_plate"]),
        ("two_dose_targets", accounting["two_dose_targets"]),
        ("three_dose_targets", accounting["three_dose_targets"]),
        ("quadrature_weights_verified", target_verification["quadrature_weights_verified"]),
        ("viability_values_numerically_converted_by_reproducer", target_verification["viability_values_numerically_converted_by_reproducer"]),
        ("protected_response_access", target_scope["protected_response_access"]),
        ("biological_accuracy_result_created", target_scope["biological_accuracy_result_created"]),
        ("official_competition_score", target_scope["official_competition_score"]),
    ):
        same(target_index[key], receipt_value, "INDEX_TARGET_DEFINITIONS_" + key.upper())

    reviewer_release = receipts["reviewer_path_release"]
    same(reviewer_release["schema"], "dosepilot.reviewer_path_release.v5", "REVIEWER_PATH_SCHEMA")
    same(reviewer_release["status"], "PASS", "REVIEWER_PATH_STATUS")
    same(reviewer_release["role"], "JUDGE_NAVIGATION_AND_CLAIM_BOUNDARY", "REVIEWER_PATH_ROLE")
    reviewer_predecessor = reviewer_release["predecessor"]
    same(sha(root / reviewer_predecessor["path"]), reviewer_predecessor["sha256"], "REVIEWER_PATH_PREDECESSOR_HASH")
    same(reviewer_predecessor["preserved_unchanged"], True, "REVIEWER_PATH_PREDECESSOR_PRESERVED")
    reviewer_entry = reviewer_release["entrypoint"]
    same(sha(root / reviewer_entry["path"]), reviewer_entry["sha256"], "REVIEWER_PATH_ENTRY_HASH")
    for path, expected in reviewer_release["bound_artifacts"].items():
        same(sha(root / path), expected, "REVIEWER_PATH_FILE_HASH: " + path)
    reviewer_text = (root / reviewer_entry["path"]).read_text()
    for phrase in (
        "Current technical report",
        "TARGET_DEFINITIONS.md",
        "FINALIST_RUBRIC_EVIDENCE.md",
        "10/24 target-average errors regress",
        "A/B prediction vectors are never combined into a 128-well predictor",
        "Protected22/Lib2 is exposed",
        "cross-patient median bandwidth",
        "not an official competition score",
    ):
        if phrase not in reviewer_text:
            raise EvidenceError("REVIEWER_PATH_REQUIRED_TEXT: " + phrase)
    if "\\n" in reviewer_text:
        raise EvidenceError("REVIEWER_PATH_TRANSPORT_ESCAPE")
    prepared_writeup = (root / "docs/KAGGLE_WRITEUP.md").read_text()
    ensure_portable_kaggle_links(prepared_writeup)
    for phrase in (
        "90-second reviewer path:",
        "00_REVIEWER_START_HERE.md",
        "Current ten-page technical report:",
        "DosePilot_Technical_Report_Current.pdf",
        "Exact definitions of all 24 outputs:",
        "TARGET_DEFINITIONS.md",
        "Historical submitted technical report:",
        "DosePilot_Technical_Report_Public.pdf",
    ):
        if phrase not in prepared_writeup:
            raise EvidenceError("PREPARED_WRITEUP_FAST_LANE: " + phrase)
    if "\\n" in prepared_writeup:
        raise EvidenceError("PREPARED_WRITEUP_TRANSPORT_ESCAPE")
    readme_text = (root / "README.md").read_text()
    ensure_current_quickstart(readme_text, reviewer_text, prepared_writeup)
    finalist_text = (root / "docs/FINALIST_AUDIT.md").read_text()
    if "python study/audits/verify_evidence_consistency.py --root ." not in finalist_text:
        raise EvidenceError("FINALIST_AUDIT_CURRENT_VERIFIER")
    if "python study/audits/verify_finalist_audit.py --root ." in finalist_text:
        raise EvidenceError("FINALIST_AUDIT_STALE_VERIFIER")
    for phrase in (
        "post-selection development point estimate",
        "uniform 1:1 choice between A and B",
    ):
        if phrase not in reviewer_text:
            raise EvidenceError("REVIEWER_SELECTION_OR_ESTIMAND_DISCLOSURE: " + phrase)
    reviewer_contract = reviewer_release["review_path"]
    same(reviewer_contract["estimated_seconds"], 90, "REVIEWER_PATH_SECONDS")
    same(reviewer_contract["current_model_mse"], 0.0010582750420801538, "REVIEWER_PATH_MSE", 1e-15)
    same(reviewer_contract["physical_measurements_per_deployment"], 64, "REVIEWER_PATH_MEASUREMENTS")
    same(reviewer_contract["outputs"], 24, "REVIEWER_PATH_OUTPUTS")
    for key in (
        "target_definition_linked",
        "current_report_linked",
        "negative_results_linked",
        "cross_patient_negative_linked",
        "prospective_boundary_linked",
        "prepared_writeup_fast_lane_linked",
        "prepared_writeup_links_portable",
        "current_model_demo_documented",
        "current_release_preflight_documented",
        "bandwidth_post_selection_disclosed",
        "uniform_ab_estimand_disclosed",
        "rubric_evidence_map_linked",
    ):
        same(reviewer_contract[key], True, "REVIEWER_PATH_LINK: " + key)
    same(reviewer_contract["rubric_self_score_assigned"], False, "REVIEWER_PATH_NO_SELF_SCORE")
    reviewer_scope = reviewer_release["scope"]
    for key in ("new_model_fit", "biological_accuracy_result_created", "independent_validation", "protected_response_access", "private_patient_rows_read", "accepted_kaggle_entry_changed"):
        same(reviewer_scope[key], False, "REVIEWER_PATH_SCOPE: " + key)
    same(reviewer_scope["official_competition_score"], None, "REVIEWER_PATH_NO_SCORE")
    reviewer_index = index["reviewer_path"]
    for key, receipt_value in (
        ("role", reviewer_release["role"]),
        ("status", reviewer_release["status"]),
        ("entrypoint", reviewer_entry["path"]),
        ("estimated_seconds", reviewer_contract["estimated_seconds"]),
        ("current_model_mse", reviewer_contract["current_model_mse"]),
        ("physical_measurements_per_deployment", reviewer_contract["physical_measurements_per_deployment"]),
        ("outputs", reviewer_contract["outputs"]),
        ("new_model_fit", reviewer_scope["new_model_fit"]),
        ("biological_accuracy_result_created", reviewer_scope["biological_accuracy_result_created"]),
        ("protected_response_access", reviewer_scope["protected_response_access"]),
        ("accepted_kaggle_entry_changed", reviewer_scope["accepted_kaggle_entry_changed"]),
        ("official_competition_score", reviewer_scope["official_competition_score"]),
        ("rubric_evidence_map_linked", reviewer_contract["rubric_evidence_map_linked"]),
        ("rubric_self_score_assigned", reviewer_contract["rubric_self_score_assigned"]),
    ):
        same(reviewer_index[key], receipt_value, "INDEX_REVIEWER_PATH_" + key.upper())

    governance = receipts["development_search_governance"]
    same(governance["schema"], "dosepilot.development_search_governance_release.v2", "GOVERNANCE_SCHEMA")
    same(governance["status"], "PASS", "GOVERNANCE_STATUS")
    same(governance["role"], "ADAPTIVE_DEVELOPMENT_GOVERNANCE_UPDATE", "GOVERNANCE_ROLE")
    governance_predecessor = governance["predecessor"]
    same(sha(root / governance_predecessor["path"]), governance_predecessor["sha256"], "GOVERNANCE_PREDECESSOR_HASH")
    same(governance_predecessor["preserved_unchanged"], True, "GOVERNANCE_PREDECESSOR_PRESERVED")
    for path, expected in governance["source_sha256"].items():
        same(sha(root / path), expected, "GOVERNANCE_FILE_HASH: " + path)
    governance_registry = governance["registry"]
    same(sha(root / governance_registry["path"]), governance_registry["sha256"], "GOVERNANCE_REGISTRY_HASH")
    same(governance_registry["registered_families"], 22, "GOVERNANCE_FAMILIES")
    same(governance_registry["rejected_families"], 15, "GOVERNANCE_REJECTED")
    same(governance_registry["unpromoted_references"], 3, "GOVERNANCE_UNPROMOTED")
    same(governance_registry["current_incumbent"], "bandwidth07_additive", "GOVERNANCE_INCUMBENT")
    same(governance_registry["current_incumbent_mse"], 0.0010582750420801538, "GOVERNANCE_MSE", 1e-15)
    same(governance_registry["exhaustive_historical_search_claimed"], False, "GOVERNANCE_NONEXHAUSTIVE")
    governance_verification = governance["verification"]
    same(governance_verification["response_free_governance_tests"], 33, "GOVERNANCE_TESTS")
    same(governance_verification["registry_cli"], "PASS", "GOVERNANCE_CLI")
    same(governance_verification["isotonic_synthetic_tests_before_fit"], 7, "GOVERNANCE_ISOTONIC_TESTS")
    same(governance_verification["isotonic_independent_no_refit_arithmetic_audit"], "PASS", "GOVERNANCE_ISOTONIC_AUDIT")
    new_family = governance["new_closed_family"]
    same(new_family["family_id"], "isotonic_paid_features", "GOVERNANCE_NEW_FAMILY")
    same(new_family["decision"], "REJECT_RETAIN_BANDWIDTH07", "GOVERNANCE_NEW_DECISION")
    same(sha(root / new_family["evidence_path"]), new_family["evidence_sha256"], "GOVERNANCE_NEW_EVIDENCE_HASH")
    same(sha(root / new_family["protocol_path"]), new_family["protocol_sha256"], "GOVERNANCE_NEW_PROTOCOL_HASH")
    same(new_family["automatic_retry"], False, "GOVERNANCE_NEW_NO_RETRY")
    for key in ("incumbent_changed", "new_independent_validation", "protected_response_access", "accepted_kaggle_entry_changed"):
        same(governance["claim_boundary"][key], False, "GOVERNANCE_BOUNDARY: " + key)
    same(governance["claim_boundary"]["official_competition_score"], None, "GOVERNANCE_NO_SCORE")
    governance_index = index["development_search_governance"]
    expected_governance_index = {
        "role": governance["role"],
        "status": governance["status"],
        "registered_families": governance_registry["registered_families"],
        "rejected_families": governance_registry["rejected_families"],
        "unpromoted_references": governance_registry["unpromoted_references"],
        "incumbent": governance_registry["current_incumbent"],
        "incumbent_mse": governance_registry["current_incumbent_mse"],
        "response_free_tests": governance_verification["response_free_governance_tests"],
        "strict_proposal_protocol_binding": True,
        "exhaustive_historical_search_claimed": governance_registry["exhaustive_historical_search_claimed"],
        "new_model_fit": False,
        "biological_accuracy_result_created": False,
        "private_or_protected_inputs_read": governance["claim_boundary"]["protected_response_access"],
        "accepted_kaggle_entry_changed": governance["claim_boundary"]["accepted_kaggle_entry_changed"],
        "official_competition_score": governance["claim_boundary"]["official_competition_score"],
    }
    same(governance_index, expected_governance_index, "INDEX_GOVERNANCE")

    current_preflight_index = index["current_release_preflight"]
    current_preflight_path = root / current_preflight_index["path"]
    same(sha(current_preflight_path), current_preflight_index["sha256"], "CURRENT_PREFLIGHT_HASH")
    same(sha(root / current_preflight_index["predecessor_path"]), current_preflight_index["predecessor_sha256"], "CURRENT_PREFLIGHT_PREDECESSOR_HASH")
    current_preflight = load(current_preflight_path)
    for key in ("schema", "status", "check_count", "target_definition_tests_included", "target_definition_verifier_included", "private_or_protected_inputs_read", "biological_accuracy_result_created", "accepted_kaggle_entry_changed", "official_competition_score"):
        same(current_preflight[key], current_preflight_index[key], "CURRENT_PREFLIGHT_" + key.upper())
    same(current_preflight["orchestrated_test_count"], current_preflight_index["orchestrated_response_free_tests"], "CURRENT_PREFLIGHT_TESTS")
    same([item["name"] for item in current_preflight["checks"]][-4:], ["target_definition_tests", "target_definitions", "fictional_lifecycle_demo", "fictional_bandwidth_lifecycle_demo"], "CURRENT_PREFLIGHT_FINAL_STAGES")

    access = receipts["protected22_access"]
    completed = receipts["protected22_completed"]
    prior = receipts["protected22_prior_incomplete"]
    spectral = receipts["spectral_successor"]
    structured = receipts["structured_additive"]
    lifecycle = receipts["lifecycle_acquisition"]
    aligned = receipts["aligned_additive"]
    bandwidth = receipts["bandwidth_successor"]
    cross_patient = receipts["cross_patient_bandwidth"]
    simplex = receipts["simplex_stacking"]
    isotonic = receipts["isotonic_paid_features"]
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
    candidate_metrics = bandwidth["metrics"]["bandwidth07"]
    additive_metrics = bandwidth["metrics"]["additive"]
    same(additive_metrics["p90_rmse"], additive_p90, "BANDWIDTH_ADDITIVE_P90_REFERENCE", 1e-15)
    candidate_orientations = candidate_metrics["orientation_mse"]
    same(len(candidate_orientations), 2, "BANDWIDTH_ORIENTATION_COUNT")
    same(
        all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in candidate_orientations),
        True,
        "BANDWIDTH_ORIENTATION_VALUES",
    )
    additive_comparison = bandwidth["comparisons"]["additive"]
    same(additive_comparison["patient_wins"], 38, "BANDWIDTH_ADDITIVE_WINS")
    same(additive_comparison["patient_wins"] + additive_comparison["patient_losses"], 59, "BANDWIDTH_ADDITIVE_PATIENT_ACCOUNTING")
    same(additive_comparison["fold_wins"], 5, "BANDWIDTH_ADDITIVE_FOLDS")
    derived_additive_gate = (
        candidate_metrics["mse"] < additive_metrics["mse"]
        and additive_comparison["patient_wins"] >= 30
        and additive_comparison["fold_wins"] == 5
        and candidate_metrics["p90_rmse"] <= additive_metrics["p90_rmse"]
    )
    same(additive_comparison["passes_all"], derived_additive_gate, "BANDWIDTH_ADDITIVE_DERIVED_GATE")
    same(derived_additive_gate, True, "BANDWIDTH_ADDITIVE_GATE")

    # Derive every historical promotion clause from independently pinned
    # aggregate receipts instead of accepting a stored passes_all boolean.
    for reference, expected_wins in (("r13", 49), ("r18", 47)):
        comparison = bandwidth["comparisons"][reference]
        reference_metrics = spectral["metrics"][reference]
        same(bandwidth["metrics"][reference]["mse"], reference_metrics["mse"], "BANDWIDTH_" + reference.upper() + "_REFERENCE", 1e-15)
        derived_relative_gain = 1.0 - candidate_metrics["mse"] / reference_metrics["mse"]
        same(comparison["relative_gain"], derived_relative_gain, "BANDWIDTH_" + reference.upper() + "_GAIN", 1e-15)
        same(comparison["patient_wins"], expected_wins, "BANDWIDTH_" + reference.upper() + "_WINS")
        same(comparison["patient_wins"] + comparison["patient_losses"], 59, "BANDWIDTH_" + reference.upper() + "_PATIENT_ACCOUNTING")
        same(comparison["fold_wins"], 5, "BANDWIDTH_" + reference.upper() + "_FOLDS")
        derived_historical_gate = (
            derived_relative_gain >= 0.05
            and comparison["patient_wins"] >= 40
            and comparison["fold_wins"] >= 4
            and candidate_metrics["p90_rmse"] <= reference_metrics["p90_rmse"]
            and all(value < reference_metrics["mse"] for value in candidate_orientations)
        )
        same(comparison["passes_all"], derived_historical_gate, "BANDWIDTH_" + reference.upper() + "_DERIVED_GATE")
        same(derived_historical_gate, True, "BANDWIDTH_" + reference.upper() + "_GATE")
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

    same(frozen_schedule["schema"], "dosepilot.frozen_ooc_release_binding.v7", "FROZEN_SCHEDULE_SCHEMA")
    same(frozen_schedule["status"], "PASS", "FROZEN_SCHEDULE_STATUS")
    same(frozen_schedule["role"], "RESPONSE_FREE_ENGINEERING_AND_RELEASE_EVIDENCE", "FROZEN_SCHEDULE_ROLE")
    frozen_predecessor = frozen_schedule["predecessor"]
    same(sha(root / frozen_predecessor["path"]), frozen_predecessor["sha256"], "FROZEN_SCHEDULE_PREDECESSOR_HASH")
    same(frozen_predecessor["preserved_unchanged"], True, "FROZEN_SCHEDULE_PREDECESSOR_PRESERVED")
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
    same(schedule_verification["prepared_kaggle_relative_links"], 0, "FROZEN_SCHEDULE_KAGGLE_LINKS")
    same(schedule_verification["bandwidth_post_selection_disclosed"], True, "FROZEN_SCHEDULE_SELECTION_DISCLOSURE")
    same(schedule_verification["overstated_search_label_absent"], True, "FROZEN_SCHEDULE_SEARCH_LABEL")
    same(schedule_verification["cross_patient_negative_disclosed"], True, "FROZEN_SCHEDULE_CPM_DISCLOSURE")
    same(schedule_verification["cross_patient_negative_linked"], True, "FROZEN_SCHEDULE_CPM_LINK")
    for key in ("promotion_gate_predicates_derived", "orientation_vector_validated", "additive_p90_crosschecked", "historical_fold_counts_pinned"):
        same(schedule_verification[key], True, "FROZEN_SCHEDULE_GATE_HARDENING: " + key)
    same(schedule_verification["new_tamper_tests"], 7, "FROZEN_SCHEDULE_TESTS")
    same(schedule_verification["new_tamper_tests_passed"], 7, "FROZEN_SCHEDULE_TESTS_PASS")
    same(schedule_verification["release_preflight_check_count"], 14, "FROZEN_SCHEDULE_PREFLIGHT_COUNT")
    same(schedule_verification["orchestrated_response_free_tests"], 168, "FROZEN_SCHEDULE_PREFLIGHT_ORCHESTRATED")
    for key in ("prospective_experiment_executed", "biological_validation_created", "protected_response_access", "private_patient_rows_read", "fitted_biological_weights_published", "accepted_kaggle_entry_changed"):
        same(frozen_schedule[key], False, "FROZEN_SCHEDULE_FALSE_BOUNDARY: " + key)
    same(frozen_schedule["official_competition_score"], None, "FROZEN_SCHEDULE_NO_SCORE")

    schedule_index = index["frozen_ooc_release_binding"]
    for key in ("role", "status"):
        same(schedule_index[key], frozen_schedule[key], "INDEX_FROZEN_SCHEDULE_" + key.upper())
    for key in ("treatment_wells_per_orientation", "plate_counts_per_orientation", "targets", "two_dose_targets", "three_dose_targets", "ab_same_treatments", "ab_complementary_plate_assignment", "public_schedule_rows", "public_site_schedule_exact", "manifest_table_exact", "transport_escape_literals", "bandwidth_post_selection_disclosed", "overstated_search_label_absent", "cross_patient_negative_disclosed", "cross_patient_negative_linked", "promotion_gate_predicates_derived", "orientation_vector_validated", "additive_p90_crosschecked", "historical_fold_counts_pinned", "new_tamper_tests_passed", "release_preflight_check_count", "orchestrated_response_free_tests"):
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

    same(cross_patient["schema"], "dosepilot.cross_patient_bandwidth.public_aggregate.v1", "CPM_SCHEMA")
    same(cross_patient["status"], "COMPLETE", "CPM_STATUS")
    same(cross_patient["decision"], "REJECT_RETAIN_BANDWIDTH07", "CPM_DECISION")
    same(cross_patient["metrics"]["bandwidth07"]["mse"], bandwidth["metrics"]["bandwidth07"]["mse"], "CPM_BANDWIDTH_REFERENCE", 1e-15)
    same(cross_patient["metrics"]["cross_patient_median"]["mse"] < cross_patient["metrics"]["bandwidth07"]["mse"], True, "CPM_MEAN_LOWER")
    same(cross_patient["candidate_vs_bandwidth07"]["patient_wins"] >= 30, True, "CPM_PATIENT_BREADTH")
    same(cross_patient["candidate_vs_bandwidth07"]["fold_wins"], 4, "CPM_FOLD_WINS")
    same(cross_patient["candidate_vs_bandwidth07"]["gate"]["all_five_folds_favorable"], False, "CPM_FOLD_GATE_FAILED")
    same(cross_patient["candidate_vs_bandwidth07"]["passes_all"], False, "CPM_GATE_FAILED")
    same(cross_patient["failed_promotion_clause"], "ALL_FIVE_FOLDS_FAVORABLE_VS_BANDWIDTH07", "CPM_FAILED_CLAUSE")
    same(cross_patient["historical_gate"]["r13"]["passes_all"], True, "CPM_R13_GATE")
    same(cross_patient["historical_gate"]["r18"]["passes_all"], True, "CPM_R18_GATE")
    same(cross_patient["verification"]["status"], "PASS", "CPM_VERIFICATION")
    same(cross_patient["verification"]["fit_routine_called"], False, "CPM_NO_REFIT_VERIFIER")
    same(cross_patient["repeated_adaptive_development"], True, "CPM_REPEATED_DEVELOPMENT")
    same(cross_patient["independent_validation"], False, "CPM_NOT_INDEPENDENT")
    same(cross_patient["protected_response_access"], False, "CPM_NO_PROTECTED")
    same(cross_patient["accepted_kaggle_entry_changed"], False, "CPM_NO_ENTRY_CHANGE")
    same(cross_patient["official_competition_score"], None, "CPM_NO_SCORE")
    same(cross_patient["automatic_retry"], False, "CPM_NO_RETRY")
    cpm_index = index["cross_patient_bandwidth_challenger"]
    same(cpm_index["status"], cross_patient["status"], "INDEX_CPM_STATUS")
    same(cpm_index["decision"], cross_patient["decision"], "INDEX_CPM_DECISION")
    same(cpm_index["role"], cross_patient["role"], "INDEX_CPM_ROLE")
    same(cpm_index["mse"], cross_patient["metrics"]["cross_patient_median"]["mse"], "INDEX_CPM_MSE", 1e-15)
    same(cpm_index["bandwidth07_reference_mse"], cross_patient["metrics"]["bandwidth07"]["mse"], "INDEX_CPM_REFERENCE", 1e-15)
    for key in ("relative_gain", "patient_wins", "patient_losses", "patient_ties", "fold_wins", "p90_nonworse"):
        same(cpm_index[key], cross_patient["candidate_vs_bandwidth07"][key], "INDEX_CPM_" + key.upper(), 1e-15 if key == "relative_gain" else 0.0)
    same(cpm_index["required_fold_wins"], 5, "INDEX_CPM_REQUIRED_FOLDS")
    same(cpm_index["target_regressions"], len(cross_patient["regressing_targets_vs_bandwidth07"]), "INDEX_CPM_TARGET_REGRESSIONS")
    same(cpm_index["passes_incumbent_gate"], cross_patient["candidate_vs_bandwidth07"]["passes_all"], "INDEX_CPM_GATE")
    for key in ("automatic_retry", "independent_validation", "protected_response_access", "accepted_kaggle_entry_changed", "official_competition_score"):
        same(cpm_index[key], cross_patient[key], "INDEX_CPM_" + key.upper())

    same(simplex["schema"], "dosepilot.simplex_stacking.public_evidence.v1", "SIMPLEX_SCHEMA")
    same(simplex["status"], "COMPLETE", "SIMPLEX_STATUS")
    same(simplex["decision"], "REJECT_RETAIN_BANDWIDTH07", "SIMPLEX_DECISION")
    same(simplex["candidate"]["mse"] > simplex["bandwidth07_incumbent"]["mse"], True, "SIMPLEX_MEAN_WORSE")
    same(simplex["bandwidth07_incumbent"]["mse"], bandwidth["metrics"]["bandwidth07"]["mse"], "SIMPLEX_BANDWIDTH_REFERENCE", 1e-15)
    comparison_record = simplex["comparison_to_incumbent"]
    same(comparison_record["patient_wins"], 23, "SIMPLEX_PATIENT_WINS")
    same(comparison_record["fold_wins"], 2, "SIMPLEX_FOLD_WINS")
    same(comparison_record["p90_nonworse"], False, "SIMPLEX_P90_FAILED")
    same(comparison_record["target_regressions"], 16, "SIMPLEX_TARGET_REGRESSIONS")
    same(simplex["inner_stacking_diagnostic"]["interpretation"], "Every inner objective improved, but held-patient mean, breadth, fold consistency and tail worsened.", "SIMPLEX_INNER_OUTER_DIVERGENCE")
    same(simplex["promotion_gate"]["all_gates_passed"], False, "SIMPLEX_GATE_FAILED")
    same(simplex["verification"]["independent_no_refit_status"], "PASS", "SIMPLEX_VERIFICATION")
    same(simplex["verification"]["simplex_kkt_folds_verified"], 5, "SIMPLEX_KKT")
    same(simplex["verification"]["held_target_predictions_reconstructed"], 5712, "SIMPLEX_RECONSTRUCTION")
    for key in ("automatic_retry", "independent_validation", "protected_response_access", "accepted_kaggle_entry_changed", "official_competition_score"):
        expected = False if key != "official_competition_score" else None
        same(simplex[key], expected, "SIMPLEX_BOUNDARY_" + key.upper())
    simplex_index = index["simplex_stacking_challenger"]
    for key in ("status", "decision", "role", "automatic_retry", "independent_validation", "protected_response_access", "accepted_kaggle_entry_changed", "official_competition_score"):
        same(simplex_index[key], simplex[key], "INDEX_SIMPLEX_" + key.upper())
    same(simplex_index["mse"], simplex["candidate"]["mse"], "INDEX_SIMPLEX_MSE", 1e-15)
    same(simplex_index["bandwidth07_reference_mse"], simplex["bandwidth07_incumbent"]["mse"], "INDEX_SIMPLEX_REFERENCE", 1e-15)
    for key in ("relative_gain", "patient_wins", "patient_losses", "patient_ties", "fold_wins", "p90_nonworse"):
        same(simplex_index[key], comparison_record[key], "INDEX_SIMPLEX_" + key.upper(), 1e-15 if key == "relative_gain" else 0.0)
    same(simplex_index["target_regressions"], comparison_record["target_regressions"], "INDEX_SIMPLEX_TARGETS")
    same(simplex_index["all_inner_objectives_improved"], True, "INDEX_SIMPLEX_INNER")
    same(simplex_index["passes_incumbent_gate"], False, "INDEX_SIMPLEX_GATE")
    same(simplex_index["independent_no_refit_verification"], "PASS", "INDEX_SIMPLEX_VERIFICATION")

    same(isotonic["schema"], "dosepilot.isotonic_paid_features.public_result.v1", "ISOTONIC_SCHEMA")
    same(isotonic["status"], "COMPLETE", "ISOTONIC_STATUS")
    same(isotonic["decision"], "REJECT_RETAIN_BANDWIDTH07", "ISOTONIC_DECISION")
    candidate_metric = isotonic["metrics"]["isotonic_candidate"]
    incumbent_metric = isotonic["metrics"]["bandwidth07_incumbent"]
    same(candidate_metric["mse"], 0.0010731733783205333, "ISOTONIC_MSE", 1e-15)
    same(incumbent_metric["mse"], bandwidth["metrics"]["bandwidth07"]["mse"], "ISOTONIC_REFERENCE", 1e-15)
    same(candidate_metric["mse"] > incumbent_metric["mse"], True, "ISOTONIC_MEAN_WORSE")
    isotonic_comparison = isotonic["candidate_vs_bandwidth07"]
    same(isotonic_comparison["patient_wins"], 24, "ISOTONIC_PATIENT_WINS")
    same(isotonic_comparison["patient_losses"], 35, "ISOTONIC_PATIENT_LOSSES")
    same(isotonic_comparison["fold_wins"], 2, "ISOTONIC_FOLD_WINS")
    same(isotonic_comparison["p90_nonworse"], False, "ISOTONIC_P90_FAILED")
    same(isotonic_comparison["target_regressions"], 13, "ISOTONIC_TARGET_REGRESSIONS")
    same(isotonic["promotion_gate"]["all_gates_passed"], False, "ISOTONIC_GATE_FAILED")
    same(isotonic["independent_no_refit_verification"], "PASS", "ISOTONIC_VERIFICATION")
    for key in ("automatic_retry", "independent_validation", "protected_response_access", "accepted_kaggle_entry_changed", "official_competition_score"):
        expected = False if key != "official_competition_score" else None
        same(isotonic[key], expected, "ISOTONIC_BOUNDARY_" + key.upper())
    isotonic_index = index["isotonic_paid_features_challenger"]
    for key in ("status", "decision", "role", "automatic_retry", "independent_validation", "protected_response_access", "accepted_kaggle_entry_changed", "official_competition_score"):
        same(isotonic_index[key], isotonic[key], "INDEX_ISOTONIC_" + key.upper())
    same(isotonic_index["mse"], candidate_metric["mse"], "INDEX_ISOTONIC_MSE", 1e-15)
    same(isotonic_index["bandwidth07_reference_mse"], incumbent_metric["mse"], "INDEX_ISOTONIC_REFERENCE", 1e-15)
    for key in ("relative_gain", "patient_wins", "patient_losses", "patient_ties", "fold_wins", "p90_nonworse"):
        same(isotonic_index[key], isotonic_comparison[key], "INDEX_ISOTONIC_" + key.upper(), 1e-15 if key == "relative_gain" else 0.0)
    same(isotonic_index["target_regressions"], isotonic_comparison["target_regressions"], "INDEX_ISOTONIC_TARGETS")
    same(isotonic_index["passes_incumbent_gate"], False, "INDEX_ISOTONIC_GATE")
    same(isotonic_index["independent_no_refit_verification"], "PASS", "INDEX_ISOTONIC_VERIFICATION")

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
    for phrase in (
        "post-selection development point estimate",
        "uniform 1:1 assignment",
    ):
        if phrase not in writeup:
            raise EvidenceError("WRITEUP_SELECTION_OR_ESTIMAND_DISCLOSURE: " + phrase)
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

    rubric_index = index["finalist_rubric_evidence"]
    same(sha(root / rubric_index["path"]), rubric_index["sha256"], "INDEX_RUBRIC_EVIDENCE_HASH")
    try:
        rubric_result = verify_finalist_rubric_evidence(root)
    except RubricEvidenceError as exc:
        raise EvidenceError("RUBRIC_EVIDENCE: " + str(exc)) from exc
    same(rubric_index["status"], rubric_result["status"], "INDEX_RUBRIC_EVIDENCE_STATUS")
    same(rubric_index["criteria"], rubric_result["criteria"], "INDEX_RUBRIC_EVIDENCE_CRITERIA")
    same(rubric_index["weight_sum"], rubric_result["weight_sum"], "INDEX_RUBRIC_EVIDENCE_WEIGHT_SUM")
    same(rubric_index["official_competition_score"], rubric_result["official_competition_score"], "INDEX_RUBRIC_EVIDENCE_NO_SCORE")
    same(rubric_index["accepted_kaggle_entry_changed"], False, "INDEX_RUBRIC_EVIDENCE_NO_KAGGLE_CHANGE")
    same(rubric_index["protected_response_access"], False, "INDEX_RUBRIC_EVIDENCE_NO_PROTECTED")
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
        "target_definitions_verified": target_verification["target_table_rows_verified"],
        "reviewer_path_seconds": reviewer_contract["estimated_seconds"],
        "rubric_evidence_criteria": rubric_result["criteria"],
        "rubric_evidence_weight_sum": rubric_result["weight_sum"],
        "current_preflight_tests": current_preflight["orchestrated_test_count"],
        "raw_ak_decision": aligned["decision"],
        "cross_patient_bandwidth_decision": cross_patient["decision"],
        "simplex_stacking_decision": simplex["decision"],
        "isotonic_paid_features_decision": isotonic["decision"],
        "development_governance_families": governance_registry["registered_families"],
        "development_governance_tests": governance_verification["response_free_governance_tests"],
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
