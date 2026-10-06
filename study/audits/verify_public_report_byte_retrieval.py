#!/usr/bin/env python3
"""Verify the point-in-time public technical-report byte-retrieval receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class PublicReportByteRetrievalError(ValueError):
    pass


EXPECTED_SOURCE = {
    "repository": "josepha-mayo/von-dosepilot",
    "public_commit": "43a5205d1ff04c4ebe2c93f2b463609f80629c05",
    "public_tree": "1a823d4b8bfab4cccd6947437a85dee90aea8ce5",
    "path": "docs/DosePilot_Technical_Report_Current.pdf",
    "requested_url": "https://github.com/josepha-mayo/von-dosepilot/blob/43a5205d1ff04c4ebe2c93f2b463609f80629c05/docs/DosePilot_Technical_Report_Current.pdf",
}

EXPECTED_RETRIEVAL = {
    "interface": "github_repository_file_fetch",
    "transfer_encoding": "base64",
    "response_content_decoded": True,
    "retrieved_bytes": 92307,
    "retrieved_sha256": "23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1",
    "github_blob_sha": "6899cb6b2c53c1c1d67a9fadb5d073923daaf21e",
}


def require(condition, label):
    if not condition:
        raise PublicReportByteRetrievalError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_blob_sha(path):
    payload = Path(path).read_bytes()
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("public_report_byte_retrieval_verification")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(receipt_path.name == "public_report_byte_retrieval_verification_20261006.json", "INDEX_PATH")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    require(receipt.get("schema") == "dosepilot.public_report_byte_retrieval.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "POINT_IN_TIME_PUBLIC_REPOSITORY_BYTE_RETRIEVAL", "ROLE")
    require(receipt.get("observed_utc") == "2026-10-06T06:04:11Z", "OBSERVED_UTC")
    require(receipt.get("source") == EXPECTED_SOURCE, "SOURCE")
    require(receipt.get("retrieval") == EXPECTED_RETRIEVAL, "RETRIEVAL")

    exact = receipt.get("exact_tree_comparison", {})
    require(exact.get("path") == EXPECTED_SOURCE["path"], "EXACT_PATH")
    require(exact.get("bytes") == EXPECTED_RETRIEVAL["retrieved_bytes"], "EXACT_BYTES")
    require(exact.get("sha256") == EXPECTED_RETRIEVAL["retrieved_sha256"], "EXACT_SHA256")
    require(exact.get("git_blob_sha") == EXPECTED_RETRIEVAL["github_blob_sha"], "EXACT_BLOB")
    require(exact.get("retrieved_bytes_match_exact_tree_pdf") is True, "EXACT_MATCH")
    pdf = root / exact["path"]
    require(pdf.stat().st_size == exact["bytes"], "PDF_SIZE")
    require(sha(pdf) == exact["sha256"], "PDF_HASH")
    require(git_blob_sha(pdf) == exact["git_blob_sha"], "PDF_BLOB")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    boundary = receipt.get("claim_boundary", {})
    require(boundary.get("public_repository_file_bytes_retrieved") is True, "BOUNDARY_RETRIEVED")
    require(boundary.get("retrieved_bytes_match_exact_tree_pdf") is True, "BOUNDARY_MATCH")
    for key in (
        "anonymous_raw_http_verified",
        "browser_download_button_verified",
        "future_availability_verified",
        "accessibility_conformance_verified",
        "content_completeness_verified",
        "independent_validation_created",
        "new_model_fit",
        "private_or_protected_inputs_read",
        "biological_accuracy_result_created",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    for key, expected in (
        ("status", "PASS"),
        ("observed_utc", "2026-10-06T06:04:11Z"),
        ("public_commit", EXPECTED_SOURCE["public_commit"]),
        ("public_tree", EXPECTED_SOURCE["public_tree"]),
        ("pdf_sha256", EXPECTED_RETRIEVAL["retrieved_sha256"]),
        ("pdf_bytes", EXPECTED_RETRIEVAL["retrieved_bytes"]),
        ("github_blob_sha", EXPECTED_RETRIEVAL["github_blob_sha"]),
        ("public_repository_file_bytes_retrieved", True),
        ("retrieved_bytes_match_exact_tree_pdf", True),
        ("anonymous_raw_http_verified", False),
        ("browser_download_button_verified", False),
        ("future_availability_verified", False),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "observed_utc": receipt["observed_utc"],
        "public_commit": EXPECTED_SOURCE["public_commit"],
        "public_tree": EXPECTED_SOURCE["public_tree"],
        "pdf_sha256": EXPECTED_RETRIEVAL["retrieved_sha256"],
        "pdf_bytes": EXPECTED_RETRIEVAL["retrieved_bytes"],
        "github_blob_sha": EXPECTED_RETRIEVAL["github_blob_sha"],
        "public_repository_file_bytes_retrieved": True,
        "retrieved_bytes_match_exact_tree_pdf": True,
        "anonymous_raw_http_verified": False,
        "browser_download_button_verified": False,
        "future_availability_verified": False,
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
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
