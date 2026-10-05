#!/usr/bin/env python3
"""Verify the dated public technical-report render receipt offline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class PublicReportRenderVerificationError(ValueError):
    pass


EXPECTED_PAGE = {
    "requested_url": "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Current.pdf",
    "resolved_url": "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Current.pdf",
    "title": "von-dosepilot/docs/DosePilot_Technical_Report_Current.pdf at master · josepha-mayo/von-dosepilot · GitHub",
    "displayed_size": "89.9 KB",
}

EXPECTED_VIEWER = {
    "host": "viewscreen.githubusercontent.com",
    "iframe_title": "File display",
    "commit_binding": "d2cb880668c7801dfa96ffdeb6fd50142d7bb645",
    "path_binding": "docs/DosePilot_Technical_Report_Current.pdf",
    "raw_target": "https://raw.githubusercontent.com/josepha-mayo/von-dosepilot/d2cb880668c7801dfa96ffdeb6fd50142d7bb645/docs/DosePilot_Technical_Report_Current.pdf",
    "more_pages_control_used": True,
    "visible_page_markers": ["Page 5", "Negative results and external evidence"],
}

EXPECTED_PDF = {
    "path": "docs/DosePilot_Technical_Report_Current.pdf",
    "sha256": "1d5d7098d53838373ab57ad32ab01d61d3dcfe8d577f8b3bfb09f33f1b4a0ff2",
    "bytes": 92034,
    "pages": 10,
    "page_size": "A4",
    "pdf_version": "1.4",
    "encrypted": False,
    "javascript": False,
    "pdfinfo_pass": True,
    "pdftoppm_pages_rendered": 10,
}


def require(condition, label):
    if not condition:
        raise PublicReportRenderVerificationError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("public_report_render_verification")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    require(receipt.get("schema") == "dosepilot.public_report_render_verification.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "POINT_IN_TIME_PUBLIC_REPORT_RENDER_VERIFICATION", "ROLE")
    require(receipt.get("observed_utc") == "2026-10-05T13:43:44Z", "OBSERVED_UTC")
    source = receipt.get("source", {})
    require(source.get("public_commit") == "d2cb880668c7801dfa96ffdeb6fd50142d7bb645", "SOURCE_COMMIT")
    require(source.get("public_tree") == "09d7f10bb559d954078ec250ee8e77f7c6371243", "SOURCE_TREE")
    require(receipt.get("public_page") == EXPECTED_PAGE, "PUBLIC_PAGE")
    require(receipt.get("embedded_viewer") == EXPECTED_VIEWER, "EMBEDDED_VIEWER")
    require(receipt.get("exact_pdf") == EXPECTED_PDF, "EXACT_PDF")
    require(sha(root / EXPECTED_PDF["path"]) == EXPECTED_PDF["sha256"], "PDF_HASH")
    require((root / EXPECTED_PDF["path"]).stat().st_size == EXPECTED_PDF["bytes"], "PDF_SIZE")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    limitation = receipt.get("preserved_operational_limitation", {})
    require(limitation.get("status") == "DOWNLOAD_EVENT_TIMEOUT_EMBEDDED_RENDER_SUCCEEDED", "LIMITATION_STATUS")
    require(limitation.get("download_event_timeout_seconds") == 30, "LIMITATION_TIMEOUT")
    require(limitation.get("downloaded_file_captured") is False, "LIMITATION_CAPTURE")
    require(limitation.get("downloaded_bytes_compared") is False, "LIMITATION_BYTES")
    require(limitation.get("scientific_model_or_product_failure") is False, "LIMITATION_SCOPE")

    boundary = receipt.get("claim_boundary", {})
    require(boundary.get("public_embedded_pdf_render_verified") is True, "BOUNDARY_RENDER")
    require(boundary.get("exact_tree_pdf_structural_render_verified") is True, "BOUNDARY_STRUCTURAL")
    for key in (
        "raw_download_success_verified",
        "browser_downloaded_bytes_compared",
        "future_availability_verified",
        "content_completeness_verified",
        "accessibility_conformance_verified",
        "new_model_fit",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "private_or_protected_inputs_read",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    for key, expected in (
        ("status", "PASS"),
        ("observed_utc", "2026-10-05T13:43:44Z"),
        ("pdf_sha256", EXPECTED_PDF["sha256"]),
        ("pdf_pages", 10),
        ("public_embedded_pdf_render_verified", True),
        ("raw_download_success_verified", False),
        ("browser_downloaded_bytes_compared", False),
        ("future_availability_verified", False),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "observed_utc": "2026-10-05T13:43:44Z",
        "pdf_sha256": EXPECTED_PDF["sha256"],
        "pdf_pages": 10,
        "public_embedded_pdf_render_verified": True,
        "raw_download_success_verified": False,
        "browser_downloaded_bytes_compared": False,
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

