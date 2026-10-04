#!/usr/bin/env python3
"""Verify reviewer-route integrity and discovery of the downloadable trace.

This response-free checker reads public aggregate JSON and Markdown only. It
makes no network request and opens no workbook, model, prediction, or patient
array.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from verify_reviewer_routes import (
    AUDITED_SURFACES,
    BARE_URL,
    GITHUB_BLOB_PREFIX,
    MARKDOWN_LINK,
    REQUIRED_URLS,
    markdown_slug,
    split_markdown_target,
)


class ReviewerTraceDiscoveryError(ValueError):
    pass


def require(condition, label):
    if not condition:
        raise ReviewerTraceDiscoveryError(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def headings(path):
    import re

    return {
        markdown_slug(value)
        for value in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", path.read_text(), re.MULTILINE)
    }


def verify(root):
    root = Path(root).resolve()
    index = load(root / "evidence/EVIDENCE_INDEX.json")
    record = index.get("reviewer_route_integrity")
    require(isinstance(record, dict), "INDEX_RECORD")
    receipt_path = root / record.get("path", "")
    require(sha(receipt_path) == record.get("sha256"), "INDEX_RECEIPT_HASH")
    receipt = load(receipt_path)
    require(receipt.get("schema") == "dosepilot.reviewer_route_integrity.v2", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "REVIEWER_NAVIGATION_AND_TRACE_DISCOVERY", "ROLE")

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(load(predecessor_path).get("schema") == "dosepilot.reviewer_route_integrity.v1", "PREDECESSOR_SCHEMA")
    require(predecessor.get("preserved_unchanged") is True, "PREDECESSOR_PRESERVED")

    for relative, expected in receipt.get("artifact_sha256", {}).items():
        require(sha(root / relative) == expected, "ARTIFACT_HASH: " + relative)

    surfaces = receipt.get("audited_surfaces", {})
    require(tuple(surfaces) == AUDITED_SURFACES, "AUDITED_SURFACES")
    for relative, expected in surfaces.items():
        require(sha(root / relative) == expected, "SURFACE_HASH: " + relative)

    local_targets = 0
    github_targets = 0
    anchors = 0
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
                    if fragment or parsed.fragment:
                        require((fragment or parsed.fragment) in headings(target), "MISSING_ANCHOR: " + label)
                    github_targets += 1
                    anchors += int(bool(fragment or parsed.fragment))
                continue
            require(parsed.scheme == "", "UNSUPPORTED_LINK_SCHEME: " + label)
            target = (source.parent / path_part).resolve() if path_part else source
            require(root == target or root in target.parents, "LOCAL_TARGET_OUTSIDE_REPO: " + label)
            require(target.exists(), "MISSING_LOCAL_TARGET: " + label + ": " + path_part)
            if fragment:
                require(fragment in headings(target), "MISSING_ANCHOR: " + label)
            local_targets += 1
            anchors += int(bool(fragment))
        for raw in BARE_URL.findall(text):
            parsed = urlsplit(raw.rstrip(".,;:)]}"))
            require(parsed.scheme == "https" and bool(parsed.netloc), "MALFORMED_BARE_URL: " + relative)

    for label, url in REQUIRED_URLS.items():
        require(url in combined_text, "REQUIRED_URL_MISSING: " + label)

    readme = (root / "README.md").read_text()
    reviewer = (root / "00_REVIEWER_START_HERE.md").read_text()
    writeup = (root / "docs/KAGGLE_WRITEUP.md").read_text()
    require("docs/LIVE_DEMO_TRACE_EXPORT.md" in readme, "README_TRACE_LINK")
    require("docs/LIVE_DEMO_TRACE_EXPORT.md" in reviewer, "REVIEWER_TRACE_LINK")
    trace_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/LIVE_DEMO_TRACE_EXPORT.md"
    require(trace_url in writeup, "WRITEUP_TRACE_LINK")
    require("Downloadable state-bound evidence record:" in writeup, "WRITEUP_TRACE_LABEL")
    require("no raw readings or model outputs" in reviewer, "REVIEWER_TRACE_BOUNDARY")
    nonportable = []
    for match in MARKDOWN_LINK.finditer(writeup):
        target = match.group(1).strip().split()[0].strip("<>")
        if not target.startswith(("https://", "http://", "mailto:", "#")):
            nonportable.append(target)
    require(not nonportable, "KAGGLE_WRITEUP_NONPORTABLE_LINK")

    live_record = receipt.get("live_demo_trace", {})
    live_path = root / live_record.get("path", "")
    require(sha(live_path) == live_record.get("sha256"), "LIVE_TRACE_RECEIPT_HASH")
    live = load(live_path)
    require(live.get("schema") == "dosepilot.live_demo_withholding.v4", "LIVE_TRACE_SCHEMA")
    contract = live.get("export_contract", {})
    require(contract.get("visible_and_exported_record_identical") is True, "LIVE_TRACE_EXACT_EXPORT")
    require(contract.get("contains_raw_readings") is False, "LIVE_TRACE_NO_READINGS")
    require(contract.get("contains_model_outputs") is False, "LIVE_TRACE_NO_OUTPUTS")
    require(contract.get("contains_patient_or_protected_data") is False, "LIVE_TRACE_NO_PROTECTED")

    verification = receipt.get("verification", {})
    require(local_targets == verification.get("local_targets"), "LOCAL_TARGET_COUNT")
    require(github_targets == verification.get("github_master_targets"), "GITHUB_TARGET_COUNT")
    require(anchors == verification.get("anchors"), "ANCHOR_COUNT")
    require(verification.get("required_urls") == len(REQUIRED_URLS), "REQUIRED_URL_COUNT")
    require(verification.get("trace_links") == 3, "TRACE_LINK_COUNT")
    require(verification.get("adversarial_tests_passed") == 10, "ADVERSARIAL_TEST_COUNT")
    require(verification.get("network_requests") == 0, "NETWORK_REQUESTS")

    boundary = receipt.get("claim_boundary", {})
    for key in (
        "external_playback_verified",
        "new_model_fit",
        "biological_accuracy_result_created",
        "private_or_protected_inputs_read",
        "accepted_kaggle_entry_changed",
        "netlify_deployment_changed",
        "export_contains_raw_readings_or_outputs",
    ):
        require(boundary.get(key) is False, "BOUNDARY_" + key.upper())
    require(boundary.get("official_competition_score") is None, "BOUNDARY_OFFICIAL_SCORE")

    expected_index = {
        "status": "PASS",
        "audited_surfaces": len(AUDITED_SURFACES),
        "local_targets": local_targets,
        "github_master_targets": github_targets,
        "anchors": anchors,
        "required_urls": len(REQUIRED_URLS),
        "trace_links": 3,
        "network_requests": 0,
        "downloadable_trace_linked": True,
        "export_contains_raw_readings_or_outputs": False,
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
        "accepted_kaggle_entry_changed": False,
        "official_competition_score": None,
    }
    for key, expected in expected_index.items():
        require(record.get(key) == expected, "INDEX_" + key.upper())
    return expected_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
