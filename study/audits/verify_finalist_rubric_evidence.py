#!/usr/bin/env python3
"""Verify the response-free finalist rubric evidence map.

This verifier reads aggregate JSON and Markdown only. It never opens a source
workbook, patient-level array, prediction array, or fitted biological model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


class RubricEvidenceError(ValueError):
    pass


EXPECTED_WEIGHTS = {
    "problem_importance_impact": 30,
    "technical_approach_innovation": 30,
    "results_validation": 20,
    "reproducibility_implementation": 10,
    "presentation": 10,
}


def load(path: Path):
    return json.loads(path.read_text())


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same(actual, expected, label, tolerance=0.0):
    if isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
            raise RubricEvidenceError(label)
    elif actual != expected:
        raise RubricEvidenceError(label)


def verify(root: Path):
    root = Path(root)
    receipt = load(root / "evidence/finalist_rubric_evidence_20261004.json")
    same(receipt["schema"], "dosepilot.finalist_rubric_evidence.v1", "SCHEMA")
    same(receipt["status"], "PASS", "STATUS")
    same(receipt["as_of_date"], "2026-10-04", "DATE")

    rubric = receipt["rubric"]
    same(rubric["weights"], EXPECTED_WEIGHTS, "RUBRIC_WEIGHTS")
    same(sum(rubric["weights"].values()), 100, "RUBRIC_WEIGHT_SUM")
    same(rubric["last_verified_on_platform"], "2026-10-01", "RUBRIC_VERIFICATION_DATE")
    same(rubric["current_run_public_retrieval"], "UNAVAILABLE_NO_REFRESH_CLAIM", "RUBRIC_REFRESH_BOUNDARY")
    same(rubric["combined_self_score"], None, "NO_SELF_SCORE")

    criteria = receipt["criteria"]
    same(set(criteria), set(EXPECTED_WEIGHTS), "CRITERIA_SET")
    for name, expected_weight in EXPECTED_WEIGHTS.items():
        same(criteria[name]["weight"], expected_weight, "CRITERION_WEIGHT: " + name)
        if not criteria[name]["evidence"]:
            raise RubricEvidenceError("CRITERION_EMPTY: " + name)
        if not criteria[name]["limitations"]:
            raise RubricEvidenceError("CRITERION_LIMITATIONS_EMPTY: " + name)

    for relative, expected in receipt["artifact_sha256"].items():
        path = root / relative
        if not path.is_file():
            raise RubricEvidenceError("ARTIFACT_MISSING: " + relative)
        same(sha(path), expected, "ARTIFACT_HASH: " + relative)

    target = load(root / "evidence/target_definitions_release_20261003.json")
    accounting = target["measurement_accounting"]
    same(target["status"], "PASS", "TARGET_STATUS")
    same(target["population"], {"samples": 119, "whole_patients": 59, "targets": 24}, "TARGET_POPULATION")
    same(accounting["full_source_treatment_measurements_two_plates"], 416, "FULL_MEASUREMENTS")
    same(accounting["selected_measurements_per_deployment"], 64, "SELECTED_MEASUREMENTS")
    same(accounting["selected_per_plate"], {"p1": 32, "p2": 32}, "PLATE_COUNTS")

    bandwidth = load(root / "evidence/bandwidth_successor_20261003.json")
    same(bandwidth["metrics"]["bandwidth07"]["mse"], 0.0010582750420801538, "INCUMBENT_MSE", 1e-15)
    same(bandwidth["metrics"]["bandwidth07"]["p90_rmse"], 0.0378942853087202, "INCUMBENT_P90", 1e-15)
    same(bandwidth["comparisons"]["additive"]["patient_wins"], 38, "PATIENT_WINS")
    same(bandwidth["comparisons"]["additive"]["fold_wins"], 5, "FOLD_WINS")
    same(len(bandwidth["target_regressions_vs_additive"]), 10, "TARGET_REGRESSIONS")
    same(bandwidth["repeated_adaptive_development"], True, "ADAPTIVE_DISCLOSURE")
    same(bandwidth["independent_validation"], False, "NO_INDEPENDENT_VALIDATION")

    protected = load(root / "evidence/PROTECTED22_ACCESS_STATUS.json")
    same(protected["status"], "EXPOSED_DO_NOT_TREAT_AS_HOLDOUT", "PROTECTED22_EXPOSED")
    same(protected["primary"], "NOT_ESTIMABLE", "PROTECTED22_PRIMARY")
    same(protected["independent_confirmation"], False, "PROTECTED22_NO_CONFIRMATION")

    stroma = load(root / "evidence/stroma_context_confirmation_20260930.json")
    same(stroma["status"], "CONFIRMATION_COMPLETE_GATE_PASSED", "STROMA_STATUS")
    same(stroma["confirmation"]["all_gate_components_passed"], True, "STROMA_GATE")
    limitations = " ".join(stroma["limitations"])
    if "not the original fitted R13 weights" not in limitations:
        raise RubricEvidenceError("STROMA_SCOPE")

    pipeline = load(root / "evidence/r33_public_pipeline.json")
    same(pipeline["status"], "PASS", "PIPELINE_STATUS")
    same(pipeline["public_raw_source_to_results_verified"], True, "PIPELINE_PUBLIC_ROUTE")
    same(pipeline["independent_validation"], False, "PIPELINE_NO_VALIDATION")

    lifecycle = load(root / "evidence/bandwidth_lifecycle_20261003.json")
    same(lifecycle["status"], "PASS", "LIFECYCLE_STATUS")
    same(lifecycle["verification"]["durable_runtime_tests_total"], 65, "LIFECYCLE_TESTS")
    same(lifecycle["verification"]["complete_primary_outputs"], 24, "LIFECYCLE_OUTPUTS")
    same(lifecycle["physical_contract"]["physical_execution_certified"], False, "NO_PHYSICAL_CERTIFICATION")

    preflight = load(root / receipt["current_release_preflight"]["path"])
    same(sha(root / receipt["current_release_preflight"]["path"]), receipt["current_release_preflight"]["sha256"], "PREFLIGHT_HASH")
    same(preflight["status"], "PASS", "PREFLIGHT_STATUS")
    same(preflight["orchestrated_test_count"], 173, "PREFLIGHT_TESTS")
    same(preflight["private_or_protected_inputs_read"], False, "PREFLIGHT_NO_PRIVATE")

    report = load(root / "evidence/current_technical_report_r4_20261004.json")
    same(report["status"], "PASS", "REPORT_STATUS")
    same(report["pdf"]["pages"], 10, "REPORT_PAGES")
    same(report["claim_checks"]["official_competition_score"], None, "REPORT_NO_SCORE")

    verification = receipt["verification"]
    same(verification["standalone_verifier"], "PASS", "VERIFICATION_STATUS")
    same(verification["rubric_tamper_tests"], 12, "VERIFICATION_TESTS")
    same(verification["artifact_hashes_verified"], 10, "VERIFICATION_ARTIFACTS")
    same(verification["existing_central_evidence_tests"], 42, "VERIFICATION_CENTRAL_TESTS")
    same(verification["python_compile"], "PASS", "VERIFICATION_COMPILE")
    for key in ("source_workbook_opened", "patient_or_prediction_arrays_opened", "protected_response_access"):
        same(verification[key], False, "VERIFICATION_BOUNDARY: " + key)

    doc = (root / "docs/FINALIST_RUBRIC_EVIDENCE.md").read_text()
    required = (
        "does **not** assign DosePilot a judge score",
        "64 identified treatment measurements",
        "416 eligible treatment measurements",
        "38/59 patient wins",
        "5/5 favorable folds",
        "Ten target means regress",
        "NOT_ESTIMABLE",
        "matched-CAF study does not validate the incumbent's fitted weights",
        "official competition score",
        "finalist status",
    )
    for phrase in required:
        if phrase not in doc:
            raise RubricEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

    boundary = receipt["claim_boundary"]
    for key in (
        "new_model_fit",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "protected_response_access",
        "private_patient_arrays_read",
        "accepted_kaggle_entry_changed",
        "finalist_status_claimed",
        "prospective_ooc_performance_claimed",
        "clinical_utility_claimed",
        "realized_cost_or_time_saving_claimed",
    ):
        same(boundary[key], False, "CLAIM_BOUNDARY: " + key)
    same(boundary["official_competition_score"], None, "BOUNDARY_NO_SCORE")

    return {
        "status": "PASS",
        "criteria": len(criteria),
        "weight_sum": sum(rubric["weights"].values()),
        "artifact_hashes_verified": len(receipt["artifact_sha256"]),
        "incumbent_mse": bandwidth["metrics"]["bandwidth07"]["mse"],
        "treatment_measurements": accounting["selected_measurements_per_deployment"],
        "outputs": target["population"]["targets"],
        "protected22_primary": protected["primary"],
        "public_source_to_results": pipeline["status"],
        "durable_runtime_tests": lifecycle["verification"]["durable_runtime_tests_total"],
        "current_preflight_tests": preflight["orchestrated_test_count"],
        "official_competition_score": None,
        "private_or_protected_inputs_read": False,
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
