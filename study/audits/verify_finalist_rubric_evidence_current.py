#!/usr/bin/env python3
"""Verify the current successor finalist-rubric evidence map response-free."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from verify_finalist_rubric_evidence import verify as verify_predecessor


class CurrentRubricEvidenceError(ValueError):
    pass


EXPECTED_WEIGHTS = {
    "problem_importance_impact": 30,
    "technical_approach_innovation": 30,
    "results_validation": 20,
    "reproducibility_implementation": 10,
    "presentation": 10,
}

EXPECTED_BINDINGS = {
    "predecessor": {
        "path": "evidence/finalist_rubric_evidence_20261004.json",
        "sha256": "6f6db1375116a3cbde3ea7cccb448a2881ae51c8dea61488624ede312233ddb7",
    },
    "nested_bandwidth_selection": {
        "path": "evidence/nested_bandwidth_selection_20261004.json",
        "sha256": "328cd770b957c48b20e652494f1de28c7f710cc49a9242e0d66ba56190981bdb",
    },
    "cooptimized_control": {
        "path": "evidence/cooptimized_calibrated_control_20261004.json",
        "sha256": "1238e432ed0a9abffce855440b6f290c056373f988ced6b3d3b57ce85c1cd74e",
    },
    "clean_finalist_package": {
        "path": "evidence/clean_finalist_package_execution_20261005.json",
        "sha256": "7a2fa4415c6676fbe89ee94b396fa4e040c925783c38ab8eda241e504515de4c",
    },
    "external_routes": {
        "path": "evidence/external_reviewer_route_availability_20261005.json",
        "sha256": "832c42375d6b15b5397cdfd03254b9baeffe1c70214a55a2f47c00e470a9a2f6",
    },
    "public_report_render": {
        "path": "evidence/public_report_render_verification_20261005.json",
        "sha256": "360f939617d637d29dbe28edd492dbb603e5826c0c1fa495dafb104c7257b0c1",
    },
    "current_report": {
        "path": "evidence/current_technical_report_r7_20261005.json",
        "sha256": "8579dd80843cf8598067146a6f36dde4907522f9d9aefec27aa8cb91730f03e1",
    },
    "canonical_preflight": {
        "path": "evidence/release_preflight_rubric_map_pass1_20261004.json",
        "sha256": "92ca10dc68228ff438618d160859a5b5d86ae2d934a798041be45e515dc42d2b",
    },
}


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(actual, expected, label, tolerance=0.0):
    if isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
            raise CurrentRubricEvidenceError(label)
    elif actual != expected:
        raise CurrentRubricEvidenceError(label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_finalist_rubric_evidence")
    same(isinstance(record, dict), True, "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    same(sha(receipt_path), record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    same(receipt.get("schema"), "dosepilot.finalist_rubric_evidence.v2", "SCHEMA")
    same(receipt.get("status"), "PASS", "STATUS")
    same(receipt.get("as_of_date"), "2026-10-05", "DATE")
    same(receipt.get("role"), "CURRENT_JUDGE_CRITERION_TO_EVIDENCE_MAP", "ROLE")
    rubric = receipt["rubric"]
    same(rubric["weights"], EXPECTED_WEIGHTS, "RUBRIC_WEIGHTS")
    same(sum(rubric["weights"].values()), 100, "RUBRIC_WEIGHT_SUM")
    same(rubric["last_verified_on_platform"], "2026-10-01", "RUBRIC_VERIFICATION_DATE")
    same(rubric["current_run_public_retrieval"], "UNAVAILABLE_NO_REFRESH_CLAIM", "RUBRIC_REFRESH_BOUNDARY")
    same(rubric["combined_self_score"], None, "NO_SELF_SCORE")

    criteria = receipt["criteria"]
    same(set(criteria), set(EXPECTED_WEIGHTS), "CRITERIA_SET")
    for name, weight in EXPECTED_WEIGHTS.items():
        same(criteria[name]["weight"], weight, "CRITERION_WEIGHT: " + name)
        if not criteria[name]["evidence"] or not criteria[name]["limitations"]:
            raise CurrentRubricEvidenceError("CRITERION_CONTENT: " + name)

    same(receipt["evidence_bindings"], EXPECTED_BINDINGS, "EVIDENCE_BINDINGS")
    for binding in EXPECTED_BINDINGS.values():
        same(sha(root / binding["path"]), binding["sha256"], "BINDING_HASH: " + binding["path"])
    predecessor = verify_predecessor(root)
    same(predecessor["status"], "PASS", "PREDECESSOR_STATUS")
    same(predecessor["criteria"], 5, "PREDECESSOR_CRITERIA")

    nested = load(root / EXPECTED_BINDINGS["nested_bandwidth_selection"]["path"])
    same(nested["status"], "PASS", "NESTED_STATUS")
    same(nested["selection_counts"], {"0.7": 5, "1.0": 0, "1.4": 0}, "NESTED_SELECTIONS")
    same(nested["nested_vs_fixed07"]["prediction_max_absolute_difference"], 0.0, "NESTED_PREDICTIONS")
    same(nested["nested_vs_fixed07"]["patient_ties"], 59, "NESTED_PATIENTS")
    same(nested["nested_vs_fixed07"]["fold_ties"], 5, "NESTED_FOLDS")
    same(nested["nested_vs_fixed07"]["target_ties"], 24, "NESTED_TARGETS")
    same(nested["claim_boundary"]["independent_validation"], False, "NESTED_NO_VALIDATION")

    control = load(root / EXPECTED_BINDINGS["cooptimized_control"]["path"])
    same(control["decision"], "REJECT_RETAIN_BANDWIDTH07", "CONTROL_DECISION")
    same(control["candidate_vs_bandwidth07"]["patient_wins"], 3, "CONTROL_PATIENT_WINS")
    same(control["candidate_vs_bandwidth07"]["fold_wins"], 0, "CONTROL_FOLD_WINS")
    same(control["candidate_vs_bandwidth07"]["target_regressions"], 22, "CONTROL_TARGET_REGRESSIONS")
    same(control["candidate_vs_bandwidth07"]["all_gates_passed"], False, "CONTROL_GATE")
    same(control["family_closed"], True, "CONTROL_CLOSED")
    same(control["automatic_retry"], False, "CONTROL_NO_RETRY")

    clean = load(root / EXPECTED_BINDINGS["clean_finalist_package"]["path"])
    same(clean["execution"]["status"], "PASS", "CLEAN_STATUS")
    same(clean["execution"]["package_checks"], 8, "CLEAN_CHECKS")
    same(clean["execution"]["canonical_release_stages"], 14, "CLEAN_STAGES")
    same(clean["execution"]["canonical_orchestrated_tests"], 173, "CLEAN_TESTS")
    same(clean["source"]["fresh_source_directory"], True, "CLEAN_SOURCE")
    same(clean["source"]["fresh_public_clone"], False, "CLEAN_NOT_CLONE")
    same(clean["claim_boundary"]["clean_new_machine_certification"], False, "CLEAN_NOT_MACHINE")

    routes = load(root / EXPECTED_BINDINGS["external_routes"]["path"])
    same(routes["verification"]["routes_resolved"], 5, "ROUTES_RESOLVED")
    same(routes["verification"]["expected_identity_markers_found"], 5, "ROUTES_IDENTITIES")
    same(routes["claim_boundary"]["future_uptime_verified"], False, "ROUTES_NO_FUTURE")
    same(routes["claim_boundary"]["uninterrupted_video_playback_verified"], False, "ROUTES_NO_PLAYBACK")

    render = load(root / EXPECTED_BINDINGS["public_report_render"]["path"])
    same(render["claim_boundary"]["public_embedded_pdf_render_verified"], True, "RENDER_PUBLIC")
    same(render["claim_boundary"]["exact_tree_pdf_structural_render_verified"], True, "RENDER_EXACT_TREE")
    same(render["exact_pdf"]["pages"], 10, "RENDER_PAGES")
    same(render["claim_boundary"]["raw_download_success_verified"], False, "RENDER_NO_DOWNLOAD")
    same(render["claim_boundary"]["browser_downloaded_bytes_compared"], False, "RENDER_NO_BYTES")

    report = load(root / EXPECTED_BINDINGS["current_report"]["path"])
    same(report["status"], "PASS", "REPORT_STATUS")
    same(report["pdf"]["pages"], 10, "REPORT_PAGES")
    same(report["pdf"]["sha256"], render["exact_pdf"]["sha256"], "REPORT_RENDER_HASH")
    same(report["claim_checks"]["official_competition_score"], None, "REPORT_NO_SCORE")

    for relative, expected in receipt["artifact_sha256"].items():
        same(sha(root / relative), expected, "ARTIFACT_HASH: " + relative)
    verification = receipt["verification"]
    same(verification["standalone_verifier"], "PASS", "VERIFICATION_STATUS")
    same(verification["successor_tamper_tests"], 14, "VERIFICATION_TESTS")
    same(verification["artifact_hashes_verified"], 3, "VERIFICATION_ARTIFACTS")
    same(verification["predecessor_verifier_passed"], True, "VERIFICATION_PREDECESSOR")
    for key in ("source_workbook_opened", "patient_or_prediction_arrays_opened", "protected_response_access"):
        same(verification[key], False, "VERIFICATION_BOUNDARY: " + key)

    doc = (root / "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT.md").read_text()
    required = (
        "does **not**",
        "last platform-verified values",
        "64 identified treatment measurements",
        "416 eligible treatment measurements",
        "38/59 patient wins",
        "all 5/5 outer training sets",
        "NOT_ESTIMABLE",
        "8/8 package checks",
        "5/5 required external reviewer routes",
        "browser download event timed out",
        "official competition score",
        "finalist status",
    )
    for phrase in required:
        if phrase not in doc:
            raise CurrentRubricEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

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
        "future_uptime_claimed",
        "raw_pdf_download_verified",
    ):
        same(boundary[key], False, "CLAIM_BOUNDARY: " + key)
    same(boundary["official_competition_score"], None, "BOUNDARY_NO_SCORE")

    for key, expected in (
        ("status", "PASS"),
        ("criteria", 5),
        ("weight_sum", 100),
        ("nested_outer_training_sets_selecting_07", 5),
        ("clean_package_checks", 8),
        ("external_routes_resolved", 5),
        ("public_report_render_verified", True),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        same(record.get(key), expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "criteria": 5,
        "weight_sum": 100,
        "nested_outer_training_sets_selecting_07": 5,
        "clean_package_checks": 8,
        "canonical_response_free_tests": 173,
        "external_routes_resolved": 5,
        "public_report_render_verified": True,
        "protected22_primary": "NOT_ESTIMABLE",
        "accepted_kaggle_entry_changed": False,
        "official_competition_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

