#!/usr/bin/env python3
"""Verify the finalist-facing navigation surfaces without network access."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


AUDITED_SURFACES = (
    "README.md",
    "00_REVIEWER_START_HERE.md",
    "CURRENT_TECHNICAL_REPORT.md",
    "docs/KAGGLE_WRITEUP.md",
    "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT.md",
)
REPOSITORY = "https://github.com/josepha-mayo/von-dosepilot"
GITHUB_BLOB_PREFIX = "/josepha-mayo/von-dosepilot/blob/master/"
REQUIRED_URLS = {
    "live_demo": "https://von-dosepilot.netlify.app",
    "demo_video": "https://youtu.be/QeOGJIgx378",
    "public_repository": REPOSITORY,
    "reviewer_entrypoint": REPOSITORY + "/blob/master/00_REVIEWER_START_HERE.md",
    "current_report": REPOSITORY + "/blob/master/docs/DosePilot_Technical_Report_Current.pdf",
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
BARE_URL = re.compile(r"https://[^\s<>]+")


class ReviewerRouteError(ValueError):
    pass


def require(condition, label):
    if not condition:
        raise ReviewerRouteError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def markdown_slug(value):
    value = re.sub(r"<[^>]*>", "", value)
    value = re.sub(r"[`*_~]", "", value).lower().strip()
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return re.sub(r" +", "-", value)


def split_markdown_target(raw):
    raw = raw.strip().split()[0].strip("<>")
    if "#" in raw:
        path, fragment = raw.split("#", 1)
    else:
        path, fragment = raw, ""
    return unquote(path), unquote(fragment)


def verify_anchor(path, fragment, label):
    if not fragment:
        return
    require(path.suffix.lower() == ".md", "ANCHOR_NON_MARKDOWN: " + label)
    headings = {markdown_slug(value) for value in HEADING.findall(path.read_text())}
    require(fragment in headings, "MISSING_ANCHOR: " + label + "#" + fragment)


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("reviewer_route_integrity")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") in {
        "dosepilot.reviewer_route_integrity.v1",
        "dosepilot.reviewer_route_integrity.v2",
        "dosepilot.reviewer_route_integrity.v3",
        "dosepilot.reviewer_route_integrity.v4",
        "dosepilot.reviewer_route_integrity.v5",
        "dosepilot.reviewer_route_integrity.v6",
        "dosepilot.reviewer_route_integrity.v7",
        "dosepilot.reviewer_route_integrity.v8",
        "dosepilot.reviewer_route_integrity.v9",
        "dosepilot.reviewer_route_integrity.v10",
        "dosepilot.reviewer_route_integrity.v11",
        "dosepilot.reviewer_route_integrity.v12",
        "dosepilot.reviewer_route_integrity.v13",
        "dosepilot.reviewer_route_integrity.v14",
        "dosepilot.reviewer_route_integrity.v15",
        "dosepilot.reviewer_route_integrity.v16",
        "dosepilot.reviewer_route_integrity.v17",
        "dosepilot.reviewer_route_integrity.v18",
        "dosepilot.reviewer_route_integrity.v19",
        "dosepilot.reviewer_route_integrity.v20",
    }, "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") in {
        "REVIEWER_NAVIGATION_TARGET_INTEGRITY",
        "REVIEWER_NAVIGATION_AND_TRACE_DISCOVERY",
        "REVIEWER_NAVIGATION_TRACE_AND_NESTED_EVIDENCE",
        "REVIEWER_NAVIGATION_TRACE_NESTED_AND_REPORT_EVIDENCE",
        "REVIEWER_NAVIGATION_TRACE_NESTED_REPORT_AND_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_TRACE_NESTED_AND_CURRENT_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_TRACE_OFFLINE_VERIFIER_NESTED_AND_CURRENT_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_FINALIST_PREFLIGHT_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CLEAN_EXECUTION_FINALIST_PREFLIGHT_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_REPORT_CLEAN_EXECUTION_FINALIST_PREFLIGHT_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_REPORT_CHRONOLOGY_CLEAN_EXECUTION_FINALIST_PREFLIGHT_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_RUBRIC_MAP_CHRONOLOGY_CLEAN_EXECUTION_FINALIST_PREFLIGHT_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_PACKAGE_AND_RUBRIC_MAP_CHRONOLOGY_CLEAN_EXECUTION_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_CLEAN_PACKAGE_AND_RUBRIC_MAP_CHRONOLOGY_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_PACKAGE_RUBRIC_SUCCESSOR_AND_CLEAN_PACKAGE_CHRONOLOGY_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_REPORT_CURRENT_PACKAGE_RUBRIC_SUCCESSOR_AND_CLEAN_PACKAGE_CHRONOLOGY_TRACE_OFFLINE_NESTED_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CURRENT_REPORT_BOUND_RUBRIC_SUCCESSOR_CURRENT_PACKAGE_CLEAN_PACKAGE_CHRONOLOGY_TRACE_OFFLINE_NESTED_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_REPORT_BOUND_PACKAGE_CURRENT_REPORT_RUBRIC_SUCCESSOR_CLEAN_PACKAGE_CHRONOLOGY_TRACE_OFFLINE_NESTED_NEGATIVE_CONTROL",
        "REVIEWER_NAVIGATION_CLEAN_REPORT_BOUND_EXECUTION_REPORT_BOUND_PACKAGE_CURRENT_REPORT_RUBRIC_SUCCESSOR_CHRONOLOGY_TRACE_OFFLINE_NESTED_NEGATIVE_CONTROL",
    }, "ROLE")

    if receipt.get("schema") == "dosepilot.reviewer_route_integrity.v1":
        documentation = receipt.get("documentation", {})
        require(sha(root / documentation.get("path", "")) == documentation.get("sha256"), "DOCUMENTATION_HASH")
        implementation = receipt.get("implementation_sha256", {})
    else:
        implementation = receipt.get("artifact_sha256", {})
    for relative, expected in implementation.items():
        require(sha(root / relative) == expected, "IMPLEMENTATION_HASH: " + relative)

    surfaces = receipt.get("audited_surfaces", {})
    require(tuple(surfaces) == AUDITED_SURFACES, "AUDITED_SURFACES")
    for relative, expected in surfaces.items():
        require(sha(root / relative) == expected, "SURFACE_HASH: " + relative)

    local_targets = 0
    github_targets = 0
    anchors = 0
    external_occurrences = 0
    combined_text = ""
    for relative in AUDITED_SURFACES:
        source = root / relative
        text = source.read_text()
        combined_text += "\n" + text
        for match in MARKDOWN_LINK.finditer(text):
            raw = match.group(1)
            path_part, fragment = split_markdown_target(raw)
            parsed = urlsplit(path_part)
            label = relative + ":" + str(text.count("\n", 0, match.start()) + 1)
            if parsed.scheme in ("http", "https"):
                require(parsed.scheme == "https", "NON_HTTPS_LINK: " + label)
                if parsed.netloc == "github.com" and parsed.path.startswith(GITHUB_BLOB_PREFIX):
                    repo_relative = unquote(parsed.path[len(GITHUB_BLOB_PREFIX):])
                    target = (root / repo_relative).resolve()
                    require(root == target or root in target.parents, "GITHUB_TARGET_OUTSIDE_REPO: " + label)
                    require(target.is_file(), "MISSING_GITHUB_TARGET: " + label + ": " + repo_relative)
                    verify_anchor(target, fragment or parsed.fragment, label)
                    github_targets += 1
                    anchors += int(bool(fragment or parsed.fragment))
                else:
                    external_occurrences += 1
                continue
            require(parsed.scheme == "", "UNSUPPORTED_LINK_SCHEME: " + label)
            target = (source.parent / path_part).resolve() if path_part else source
            require(root == target or root in target.parents, "LOCAL_TARGET_OUTSIDE_REPO: " + label)
            require(target.exists(), "MISSING_LOCAL_TARGET: " + label + ": " + path_part)
            verify_anchor(target, fragment, label)
            local_targets += 1
            anchors += int(bool(fragment))

        for raw in BARE_URL.findall(text):
            clean = raw.rstrip(".,;:)]}")
            parsed = urlsplit(clean)
            require(parsed.scheme == "https" and bool(parsed.netloc), "MALFORMED_BARE_URL: " + relative)

    for label, url in REQUIRED_URLS.items():
        require(url in combined_text, "REQUIRED_URL_MISSING: " + label)

    expected = receipt.get("verification", {})
    require(local_targets == expected.get("local_targets"), "LOCAL_TARGET_COUNT")
    require(github_targets == expected.get("github_master_targets"), "GITHUB_TARGET_COUNT")
    require(anchors == expected.get("anchors"), "ANCHOR_COUNT")
    require(expected.get("required_urls") == len(REQUIRED_URLS), "REQUIRED_URL_COUNT")
    require(expected.get("network_requests") == 0, "NETWORK_REQUESTS")

    if receipt.get("schema") == "dosepilot.reviewer_route_integrity.v1":
        failure = receipt.get("preserved_operational_failure", {})
        require(failure.get("status") == "INITIAL_TEST_FIXTURE_ERROR", "PRESERVED_FAILURE_STATUS")
        require(failure.get("initial_passes") == 1, "PRESERVED_FAILURE_PASSES")
        require(failure.get("initial_errors") == 7, "PRESERVED_FAILURE_ERRORS")
        require(failure.get("route_scientific_or_product_failure") is False, "PRESERVED_FAILURE_SCOPE")
        require(failure.get("corrected_tests_passed") == 8, "PRESERVED_FAILURE_CORRECTION")

        discovery = receipt.get("preserved_broad_discovery_failure", {})
        require(discovery.get("status") == "TWO_HISTORICAL_IMPORT_ERRORS", "DISCOVERY_FAILURE_STATUS")
        require(discovery.get("scientific_or_product_failure") is False, "DISCOVERY_FAILURE_SCOPE")
        require(discovery.get("canonical_preflight_status") == "PASS", "DISCOVERY_PREFLIGHT_STATUS")
        require(discovery.get("affected_tests_with_required_path_passed") == 24, "DISCOVERY_CORRECTED_TESTS")
        require(discovery.get("canonical_orchestrated_count_changed") is False, "DISCOVERY_COUNT_BOUNDARY")

    boundary = receipt.get("claim_boundary", {})
    for key in (
        "external_playback_verified",
        "external_availability_verified",
        "new_model_fit",
        "biological_accuracy_result_created",
        "private_or_protected_inputs_read",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    for key, expected_value in (
        ("status", "PASS"),
        ("audited_surfaces", len(AUDITED_SURFACES)),
        ("local_targets", local_targets),
        ("github_master_targets", github_targets),
        ("anchors", anchors),
        ("required_urls", len(REQUIRED_URLS)),
        ("network_requests", 0),
        ("external_playback_verified", False),
        ("private_or_protected_inputs_read", False),
        ("biological_accuracy_result_created", False),
        ("accepted_kaggle_entry_changed", False),
        ("official_competition_score", None),
    ):
        require(record.get(key) == expected_value, "INDEX_" + key.upper())

    return {
        "status": "PASS",
        "audited_surfaces": len(AUDITED_SURFACES),
        "local_targets": local_targets,
        "github_master_targets": github_targets,
        "anchors": anchors,
        "required_urls": len(REQUIRED_URLS),
        "network_requests": 0,
        "external_playback_verified": False,
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
