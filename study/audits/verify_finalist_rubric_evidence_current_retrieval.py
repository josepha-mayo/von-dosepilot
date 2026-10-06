#!/usr/bin/env python3
"""Verify the retrieval-bound current-report finalist-rubric successor."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CurrentRetrievalRubricEvidenceError(ValueError):
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
        "path": "evidence/finalist_rubric_evidence_r5_20261006.json",
        "sha256": "b8917193d24f486bf194bf7f3ad2ba6b63e25c716efc58b573ccb0760208107c",
    },
    "public_report_byte_retrieval": {
        "path": "evidence/public_report_byte_retrieval_verification_20261006.json",
        "sha256": "efa5356a6adbb4bbff483f9ab2036993ca87f9021d2cff65f076a8c6d741b489",
    },
}

EXPECTED_REPORT = {
    "path": "docs/DosePilot_Technical_Report_Current.pdf",
    "sha256": "23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1",
    "bytes": 92307,
    "git_blob_sha": "6899cb6b2c53c1c1d67a9fadb5d073923daaf21e",
    "retrieval_commit": "43a5205d1ff04c4ebe2c93f2b463609f80629c05",
    "retrieval_tree": "1a823d4b8bfab4cccd6947437a85dee90aea8ce5",
}


def load(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_blob_sha(path):
    payload = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()


def same(actual, expected, label):
    if actual != expected:
        raise CurrentRetrievalRubricEvidenceError(label)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("current_report_retrieval_finalist_rubric_evidence")
    same(isinstance(record, dict), True, "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    same(receipt_path.name, "finalist_rubric_evidence_r6_20261006.json", "INDEX_CURRENT_PATH")
    same(sha256(receipt_path), record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    same(receipt.get("schema"), "dosepilot.finalist_rubric_evidence.v6", "SCHEMA")
    same(receipt.get("status"), "PASS", "STATUS")
    same(receipt.get("as_of_date"), "2026-10-06", "DATE")
    same(
        receipt.get("role"),
        "CURRENT_REPORT_RETRIEVAL_BOUND_JUDGE_CRITERION_EVIDENCE_SUCCESSOR",
        "ROLE",
    )
    same(receipt.get("evidence_bindings"), EXPECTED_BINDINGS, "EVIDENCE_BINDINGS")
    for binding in EXPECTED_BINDINGS.values():
        same(sha256(root / binding["path"]), binding["sha256"], "BINDING_HASH: " + binding["path"])

    predecessor = load(root / EXPECTED_BINDINGS["predecessor"]["path"])
    same(predecessor.get("schema"), "dosepilot.finalist_rubric_evidence.v5", "PREDECESSOR_SCHEMA")
    same(predecessor.get("status"), "PASS", "PREDECESSOR_STATUS")
    same(predecessor["rubric"]["weights"], EXPECTED_WEIGHTS, "PREDECESSOR_WEIGHTS")
    same(predecessor["rubric"]["combined_self_score"], None, "PREDECESSOR_NO_SCORE")
    same(predecessor["presentation_successor"]["embedded_render_verified"], True, "PREDECESSOR_RENDER")
    same(predecessor["presentation_successor"]["raw_download_verified"], False, "PREDECESSOR_NO_DOWNLOAD")
    same(predecessor["claim_boundary"]["independent_validation_created"], False, "PREDECESSOR_NO_VALIDATION")
    same(predecessor["claim_boundary"]["accepted_kaggle_entry_changed"], False, "PREDECESSOR_NO_KAGGLE_CHANGE")
    same(predecessor["claim_boundary"]["official_competition_score"], None, "PREDECESSOR_NO_OFFICIAL_SCORE")

    retrieval = load(root / EXPECTED_BINDINGS["public_report_byte_retrieval"]["path"])
    same(retrieval.get("schema"), "dosepilot.public_report_byte_retrieval.v1", "RETRIEVAL_SCHEMA")
    same(retrieval.get("status"), "PASS", "RETRIEVAL_STATUS")
    same(retrieval["source"]["public_commit"], EXPECTED_REPORT["retrieval_commit"], "RETRIEVAL_COMMIT")
    same(retrieval["source"]["public_tree"], EXPECTED_REPORT["retrieval_tree"], "RETRIEVAL_TREE")
    same(retrieval["source"]["path"], EXPECTED_REPORT["path"], "RETRIEVAL_PATH")
    same(retrieval["retrieval"]["interface"], "github_repository_file_fetch", "RETRIEVAL_INTERFACE")
    same(retrieval["retrieval"]["transfer_encoding"], "base64", "RETRIEVAL_ENCODING")
    same(retrieval["retrieval"]["response_content_decoded"], True, "RETRIEVAL_DECODED")
    same(retrieval["retrieval"]["retrieved_bytes"], EXPECTED_REPORT["bytes"], "RETRIEVAL_BYTES")
    same(retrieval["retrieval"]["retrieved_sha256"], EXPECTED_REPORT["sha256"], "RETRIEVAL_SHA256")
    same(retrieval["retrieval"]["github_blob_sha"], EXPECTED_REPORT["git_blob_sha"], "RETRIEVAL_BLOB")
    same(retrieval["exact_tree_comparison"]["retrieved_bytes_match_exact_tree_pdf"], True, "RETRIEVAL_MATCH")
    same(retrieval["claim_boundary"]["public_repository_file_bytes_retrieved"], True, "RETRIEVAL_PUBLIC_FILE")
    same(retrieval["claim_boundary"]["anonymous_raw_http_verified"], False, "RETRIEVAL_NO_RAW_HTTP")
    same(retrieval["claim_boundary"]["browser_download_button_verified"], False, "RETRIEVAL_NO_BUTTON")
    same(retrieval["claim_boundary"]["independent_validation_created"], False, "RETRIEVAL_NO_VALIDATION")

    report_path = root / EXPECTED_REPORT["path"]
    same(sha256(report_path), EXPECTED_REPORT["sha256"], "CURRENT_PDF_HASH")
    same(report_path.stat().st_size, EXPECTED_REPORT["bytes"], "CURRENT_PDF_BYTES")
    same(git_blob_sha(report_path), EXPECTED_REPORT["git_blob_sha"], "CURRENT_PDF_BLOB")

    rubric = receipt["rubric"]
    same(rubric["weights"], EXPECTED_WEIGHTS, "WEIGHTS")
    same(sum(rubric["weights"].values()), 100, "WEIGHT_SUM")
    same(rubric["combined_self_score"], None, "NO_SELF_SCORE")
    same(rubric["last_verified_on_platform"], "2026-10-01", "PLATFORM_DATE")
    same(rubric["current_run_public_retrieval"], "NOT_ATTEMPTED_NO_REFRESH_CLAIM", "NO_REFRESH")

    expected_inherited = {
        "criteria": 5,
        "incumbent_mse": 0.0010582750420801538,
        "incumbent_p90": 0.0378942853087202,
        "patient_wins": 38,
        "patients": 59,
        "favorable_folds": 5,
        "nested_outer_training_sets_selecting_07": 5,
        "treatment_wells_per_orientation": 64,
        "report_bound_package_checks": 8,
        "canonical_release_stages": 14,
        "canonical_response_free_tests": 173,
        "protected22_primary": "NOT_ESTIMABLE",
    }
    same(receipt["inherited_verified_state"], expected_inherited, "INHERITED_STATE")

    presentation = receipt["presentation_retrieval_successor"]
    same(presentation["adds_only_public_repository_file_retrieval_evidence"], True, "PRESENTATION_NARROW_SCOPE")
    same(presentation["current_report_sha256"], EXPECTED_REPORT["sha256"], "PRESENTATION_PDF_HASH")
    same(presentation["current_report_bytes"], EXPECTED_REPORT["bytes"], "PRESENTATION_PDF_BYTES")
    same(presentation["current_report_git_blob_sha"], EXPECTED_REPORT["git_blob_sha"], "PRESENTATION_BLOB")
    same(presentation["public_repository_file_bytes_retrieved"], True, "PRESENTATION_RETRIEVED")
    same(presentation["retrieved_bytes_match_exact_tree_pdf"], True, "PRESENTATION_MATCH")
    same(presentation["embedded_render_verified_in_predecessor"], True, "PRESENTATION_RENDER")
    same(presentation["exact_tree_pages_rendered_in_predecessor"], 10, "PRESENTATION_PAGES")
    same(presentation["anonymous_raw_http_verified"], False, "PRESENTATION_NO_RAW_HTTP")
    same(presentation["browser_download_button_verified"], False, "PRESENTATION_NO_BUTTON")
    same(presentation["raw_pdf_download_verified"], False, "PRESENTATION_NO_GENERIC_DOWNLOAD")

    for relative, expected in receipt["artifact_sha256"].items():
        same(sha256(root / relative), expected, "ARTIFACT_HASH: " + relative)

    verification = receipt["verification"]
    same(verification["standalone_verifier"], "PASS", "VERIFICATION_STATUS")
    same(verification["successor_tamper_tests"], 12, "VERIFICATION_TESTS")
    same(verification["predecessor_hash_verified"], True, "VERIFICATION_PREDECESSOR")
    same(verification["byte_retrieval_receipt_hash_verified"], True, "VERIFICATION_RETRIEVAL")
    same(verification["predecessor_artifacts_reverified"], False, "VERIFICATION_PREDECESSOR_ARTIFACTS")
    for key in ("source_workbook_opened", "patient_or_prediction_arrays_opened", "protected_response_access"):
        same(verification[key], False, "VERIFICATION_BOUNDARY: " + key)

    doc = (root / "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT_RETRIEVAL.md").read_text()
    required = (
        "verified public repository-file retrieval",
        EXPECTED_REPORT["sha256"],
        "92,307 bytes",
        EXPECTED_REPORT["git_blob_sha"],
        "38/59 patient wins",
        "5/5 favorable folds",
        "exactly 64 treatment wells",
        "NOT_ESTIMABLE",
        "does not verify anonymous raw-HTTP access",
        "official competition result",
    )
    for phrase in required:
        if phrase not in doc:
            raise CurrentRetrievalRubricEvidenceError("DOCUMENT_REQUIRED_TEXT: " + phrase)

    boundary = receipt["claim_boundary"]
    same(boundary["public_repository_file_bytes_retrieved"], True, "BOUNDARY_RETRIEVED")
    same(boundary["retrieved_bytes_match_exact_tree_pdf"], True, "BOUNDARY_MATCH")
    for key in (
        "anonymous_raw_http_verified",
        "browser_download_button_verified",
        "raw_pdf_download_verified",
        "new_model_fit",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "protected_response_access",
        "private_patient_arrays_read",
        "accepted_kaggle_entry_changed",
        "finalist_status_claimed",
        "prospective_ooc_performance_claimed",
        "clinical_utility_claimed",
        "future_availability_verified",
        "content_completeness_verified",
        "accessibility_conformance_verified",
    ):
        same(boundary[key], False, "CLAIM_BOUNDARY: " + key)
    same(boundary["official_competition_score"], None, "BOUNDARY_NO_SCORE")

    for key, expected in (
        ("status", "PASS"),
        ("criteria", 5),
        ("weight_sum", 100),
        ("current_report_sha256", EXPECTED_REPORT["sha256"]),
        ("current_report_bytes", EXPECTED_REPORT["bytes"]),
        ("current_report_git_blob_sha", EXPECTED_REPORT["git_blob_sha"]),
        ("public_report_render_verified", True),
        ("public_repository_file_bytes_retrieved", True),
        ("retrieved_bytes_match_exact_tree_pdf", True),
        ("anonymous_raw_http_verified", False),
        ("browser_download_button_verified", False),
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
        "current_report_git_blob_sha": EXPECTED_REPORT["git_blob_sha"],
        "public_report_render_verified": True,
        "public_repository_file_bytes_retrieved": True,
        "retrieved_bytes_match_exact_tree_pdf": True,
        "anonymous_raw_http_verified": False,
        "browser_download_button_verified": False,
        "raw_download_verified": False,
        "predecessor_hash_verified": True,
        "byte_retrieval_receipt_hash_verified": True,
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
