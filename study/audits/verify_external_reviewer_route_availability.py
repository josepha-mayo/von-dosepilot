#!/usr/bin/env python3
"""Verify the dated external reviewer-route availability receipt offline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class ExternalReviewerRouteAvailabilityError(ValueError):
    pass


EXPECTED_ROUTES = {
    "live_demo": {
        "requested_url": "https://von-dosepilot.netlify.app",
        "resolved_url": "https://von-dosepilot.netlify.app/",
        "title": "von DosePilot — 64 wells → 24 response summaries",
        "marker": "24 response summaries. 64 traceable wells.",
        "marker_kind": "unique_heading",
    },
    "demo_video": {
        "requested_url": "https://youtu.be/QeOGJIgx378",
        "resolved_url": "https://www.youtube.com/watch?v=QeOGJIgx378",
        "title": "von DosePilot | AI4S Drug-Screen Reconstruction Demo - YouTube",
        "marker": "video_element_present",
        "marker_kind": "dom_element",
    },
    "public_repository": {
        "requested_url": "https://github.com/josepha-mayo/von-dosepilot",
        "resolved_url": "https://github.com/josepha-mayo/von-dosepilot",
        "title": "GitHub - josepha-mayo/von-dosepilot: Measurement-aware drug-screen reconstruction: traceable 64-well workflow, synthetic demo, and transparent retrospective evidence. · GitHub",
        "marker": "von-dosepilot",
        "marker_kind": "unique_visible_text",
    },
    "reviewer_entrypoint": {
        "requested_url": "https://github.com/josepha-mayo/von-dosepilot/blob/master/00_REVIEWER_START_HERE.md",
        "resolved_url": "https://github.com/josepha-mayo/von-dosepilot/blob/master/00_REVIEWER_START_HERE.md",
        "title": "von-dosepilot/00_REVIEWER_START_HERE.md at master · josepha-mayo/von-dosepilot · GitHub",
        "marker": "Reviewer start here",
        "marker_kind": "visible_text",
    },
    "current_report": {
        "requested_url": "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Current.pdf",
        "resolved_url": "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/DosePilot_Technical_Report_Current.pdf",
        "title": "von-dosepilot/docs/DosePilot_Technical_Report_Current.pdf at master · josepha-mayo/von-dosepilot · GitHub",
        "marker": "DosePilot_Technical_Report_Current.pdf",
        "marker_kind": "visible_text",
    },
}


def require(condition, label):
    if not condition:
        raise ExternalReviewerRouteAvailabilityError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("external_reviewer_route_availability")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)

    require(receipt.get("schema") == "dosepilot.external_reviewer_route_availability.v1", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "POINT_IN_TIME_EXTERNAL_REVIEWER_ROUTE_AVAILABILITY", "ROLE")
    require(receipt.get("observed_utc") == "2026-10-05T12:10:27Z", "OBSERVED_UTC")
    source = receipt.get("source", {})
    require(source.get("public_commit") == "ca9002482646ff4e406fbbd986a84885ac578e3a", "SOURCE_COMMIT")
    require(source.get("public_tree") == "1c67ddfd615bd97091007e5e5313d6c9ce5038b8", "SOURCE_TREE")

    routes = receipt.get("routes", {})
    require(routes == EXPECTED_ROUTES, "ROUTES")
    verification = receipt.get("verification", {})
    require(verification.get("routes_requested") == 5, "ROUTES_REQUESTED")
    require(verification.get("routes_resolved") == 5, "ROUTES_RESOLVED")
    require(verification.get("expected_identity_markers_found") == 5, "IDENTITY_MARKERS")
    require(verification.get("isolated_browser") is True, "ISOLATED_BROWSER")
    require(verification.get("authentication_used") is False, "AUTHENTICATION")
    require(verification.get("forms_submitted") is False, "FORMS_SUBMITTED")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    failure = receipt.get("preserved_operational_limitation", {})
    require(failure.get("status") == "GENERAL_PUBLIC_FETCH_UNAVAILABLE_BROWSER_SUCCEEDED", "LIMITATION_STATUS")
    require(failure.get("general_fetch_failures") == 5, "LIMITATION_FETCHES")
    require(failure.get("browser_routes_resolved") == 5, "LIMITATION_BROWSER")
    require(failure.get("scientific_model_or_product_failure") is False, "LIMITATION_SCOPE")

    boundary = receipt.get("claim_boundary", {})
    require(boundary.get("point_in_time_external_availability_verified") is True, "BOUNDARY_AVAILABILITY")
    for key in (
        "future_uptime_verified",
        "uninterrupted_video_playback_verified",
        "pdf_download_or_render_verified",
        "authenticated_kaggle_state_verified",
        "content_completeness_verified",
        "new_model_fit",
        "biological_accuracy_result_created",
        "independent_validation_created",
        "private_or_protected_inputs_read",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
        "repository_changed_by_browser_check",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    for key, expected in (
        ("status", "PASS"),
        ("observed_utc", "2026-10-05T12:10:27Z"),
        ("routes_requested", 5),
        ("routes_resolved", 5),
        ("expected_identity_markers_found", 5),
        ("point_in_time_external_availability_verified", True),
        ("future_uptime_verified", False),
        ("uninterrupted_video_playback_verified", False),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "observed_utc": "2026-10-05T12:10:27Z",
        "routes_requested": 5,
        "routes_resolved": 5,
        "expected_identity_markers_found": 5,
        "point_in_time_external_availability_verified": True,
        "future_uptime_verified": False,
        "uninterrupted_video_playback_verified": False,
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
