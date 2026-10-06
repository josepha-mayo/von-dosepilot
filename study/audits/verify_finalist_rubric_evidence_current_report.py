#!/usr/bin/env python3
"""Verify the current-report-bound finalist-rubric evidence successor."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CurrentReportRubricEvidenceError(ValueError):
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
        "path": "evidence/finalist_rubric_evidence_r4_20261005.json",
        "sha256": "f673eea6d102745370e14b35c78e1c6d3e5e00574efe74ad9a1373e4279fb1e5",
    },
    "current_report_render": {
        "path": "evidence/public_report_render_verification_r2_20261005.json",
        "sha256": "de99f25117086be218e638d7d8a7d6a1ba70dc020070e041e4d0405e0d883ecc",
    },
}

EXPECTED_REPORT = {
    "path": "docs/DosePilot_Technical_Report_Current.pdf",
    "sha256": "23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1",
    "bytes": 92307,
    "pages": 10,
    "public_commit": "a7483aa3a275d50aa32bdb043c52a203d8b8d41e",
}


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(actual, expected, label):
    if actual != expected:
        raise CurrentReportRubricEvidenceError(label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_report_finalist_rubric_evidence")
    same(isinstance(record, dict), True, "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    same(receipt_path.name, "finalist_rubric_evidence_r5_20261006.json", "INDEX_CURRENT_PATH")
    same(sha(receipt_path), record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    same(receipt.get("schema"), "dosepilot.finalist_rubric_evidence.v5", "SCHEMA")
    same(receipt.get("status"), "PASS", "STATUS")
    same(receipt.get("as_of_date"), "2026-10-06", "DATE")
    same(receipt.get("role"), "CURRENT_REPORT_BOUND_JUDGE_CRITERION_EVIDENCE_SUCCESSOR", "ROLE")
    same(receipt.get("evidence_bindings"), EXPECTED_BINDINGS, "EVIDENCE_BINDINGS")
    for binding in EXPECTED_BINDINGS.values():
        same(sha(root / binding["path"]), binding["sha256"], "BINDING_HASH: " + binding["path"])

    predecessor = load(root / EXPECTED_BINDINGS["predecessor"]["path"])
    same(predecessor.get("schema"), "dosepilot.finalist_rubric_evidence.v4", "PREDECESSOR_SCHEMA")
    same(predecessor.get("status"), "PASS", "PREDECESSOR_STATUS")
    same(predecessor["rubric"]["weights"], EXPECTED_WEIGHTS, "PREDECESSOR_WEIGHTS")
    same(predecessor["rubric"]["combined_self_score"], None, "PREDECESSOR_NO_SCORE")
    same(predecessor["claim_boundary"]["independent_validation_created"], False, "PREDECESSOR_NO_VALIDATION")
    same(predecessor["claim_boundary"]["accepted_kaggle_entry_changed"], False, "PREDECESSOR_NO_KAGGLE_CHANGE")
    same(predecessor["claim_boundary"]["official_competition_score"], None, "PREDECESSOR_NO_OFFICIAL_SCORE")

    render = load(root / EXPECTED_BINDINGS["current_report_render"]["path"])
    same(render.get("schema"), "dosepilot.public_report_render_verification.v2", "RENDER_SCHEMA")
    same(render.get("status"), "PASS", "RENDER_STATUS")
    same(render["source"]["public_commit"], EXPECTED_REPORT["public_commit"], "RENDER_COMMIT")
    same(render["exact_pdf"]["path"], EXPECTED_REPORT["path"], "RENDER_PATH")
    same(render["exact_pdf"]["sha256"], EXPECTED_REPORT["sha256"], "RENDER_PDF_HASH")
    same(render["exact_pdf"]["bytes"], EXPECTED_REPORT["bytes"], "RENDER_PDF_BYTES")
    same(render["exact_pdf"]["pages"], EXPECTED_REPORT["pages"], "RENDER_PAGES")
    same(render["claim_boundary"]["public_embedded_pdf_render_verified"], True, "RENDER_EMBEDDED")
    same(render["claim_boundary"]["exact_tree_pdf_structural_render_verified"], True, "RENDER_STRUCTURAL")
    same(render["claim_boundary"]["raw_download_success_verified"], False, "RENDER_NO_RAW_DOWNLOAD")
    same(render["claim_boundary"]["browser_downloaded_bytes_compared"], False, "RENDER_NO_BYTE_COMPARE")
    same(render["claim_boundary"]["independent_validation_created"], False, "RENDER_NO_VALIDATION")
    same(sha(root / EXPECTED_REPORT["path"]), EXPECTED_REPORT["sha256"], "CURRENT_PDF_HASH")
    same((root / EXPECTED_REPORT["path"]).stat().st_size, EXPECTED_REPORT["bytes"], "CURRENT_PDF_BYTES")

    rubric = receipt["rubric"]
    same(rubric["weights"], EXPECTED_WEIGHTS, "WEIGHTS")
    same(sum(rubric["weights"].values()), 100, "WEIGHT_SUM")
    same(rubric["combined_self_score"], None, "NO_SELF_SCORE")
    same(rubric["last_verified_on_platform"], "2026-10-01", "PLATFORM_DATE")
    same(rubric["current_run_public_retrieval"], "NOT_ATTEMPTED_NO_REFRESH_CLAIM", "NO_REFRESH")

    inherited = receipt["inherited_verified_state"]
    expected_inherited = {
        "criteria": 5,
        "incumbent_mse": 0.0010582750420801538,
        "incumbent_p90": 0.0378942853087202,
        "patient_wins": 38,
        "patients": 59,
        "favorable_folds": 5,
        "nested_outer_training_sets_selecting_07": 5,
        "treatment_wells_per_orientation": 64,
        "current_package_checks": 8,
        "canonical_release_stages": 14,
        "canonical_response_free_tests": 173,
        "protected22_primary": "NOT_ESTIMABLE",
    }
    same(inherited, expected_inherited, "INHERITED_STATE")

    presentation = receipt["presentation_successor"]
    same(presentation["replaces_only_predecessor_render_binding"], True, "PRESENTATION_NARROW_SCOPE")
    same(presentation["current_report_sha256"], EXPECTED_REPORT["sha256"], "PRESENTATION_PDF_HASH")
    same(presentation["current_report_bytes"], EXPECTED_REPORT["bytes"], "PRESENTATION_PDF_BYTES")
    same(presentation["public_viewer_commit_binding"], EXPECTED_REPORT["public_commit"], "PRESENTATION_COMMIT")
    same(presentation["embedded_render_verified"], True, "PRESENTATION_RENDER")
    same(presentation["exact_tree_pages_rendered"], 10, "PRESENTATION_PAGES")
    same(presentation["raw_download_verified"], False, "PRESENTATION_NO_DOWNLOAD")
    same(presentation["downloaded_bytes_compared"], False, "PRESENTATION_NO_COMPARE")

    for relative, expected in receipt["artifact_sha256"].items():
        same(sha(root / relative), expected, "ARTIFACT_HASH: " + relative)

    verification = receipt["verification"]
    same(verification["standalone_verifier"], "PASS", "VERIFICATION_STATUS")
    same(verification["successor_tamper_tests"], 10, "VERIFICATION_TESTS")
    same(verification["predecessor_hash_verified"], True, "VERIFICATION_PREDECESSOR")
    same(verification["current_render_receipt_hash_verified"], True, "VERIFICATION_RENDER")
    same(verification["predecessor_artifacts_reverified"], False, "VERIFICATION_PREDECESSOR_ARTIFACTS")
    for key in ("source_workbook_opened", "patient_or_prediction_arrays_opened", "protected_response_access"):
        same(verification[key], False, "VERIFICATION_BOUNDARY: " + key)

    doc = (root / "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT_REPORT.md").read_text()
    required = (
        "current report's own render receipt",
        "23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1",
        "92,307 bytes",
        "a7483aa3a275d50aa32bdb043c52a203d8b8d41e",
        "38/59 patient wins",
        "5/5 favorable folds",
        "exactly 64 treatment wells",
        "NOT_ESTIMABLE",
        "Raw download was not tested",
        "official competition result",
    )
    for phrase in required:
        if phrase not in doc:
            raise CurrentReportRubricEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

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
        "future_uptime_claimed",
        "content_completeness_claimed",
        "accessibility_conformance_claimed",
        "raw_pdf_download_verified",
        "browser_downloaded_bytes_compared",
    ):
        same(boundary[key], False, "CLAIM_BOUNDARY: " + key)
    same(boundary["official_competition_score"], None, "BOUNDARY_NO_SCORE")

    for key, expected in (
        ("status", "PASS"),
        ("criteria", 5),
        ("weight_sum", 100),
        ("current_report_sha256", EXPECTED_REPORT["sha256"]),
        ("current_report_bytes", EXPECTED_REPORT["bytes"]),
        ("public_viewer_commit_binding", EXPECTED_REPORT["public_commit"]),
        ("public_report_render_verified", True),
        ("raw_download_verified", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        same(record.get(key), expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "criteria": 5,
        "weight_sum": 100,
        "current_report_sha256": EXPECTED_REPORT["sha256"],
        "current_report_bytes": EXPECTED_REPORT["bytes"],
        "public_viewer_commit_binding": EXPECTED_REPORT["public_commit"],
        "public_report_render_verified": True,
        "raw_download_verified": False,
        "predecessor_hash_verified": True,
        "current_render_receipt_hash_verified": True,
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
