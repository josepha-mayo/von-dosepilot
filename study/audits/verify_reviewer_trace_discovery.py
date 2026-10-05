#!/usr/bin/env python3
"""Verify reviewer-route integrity and discovery of trace and nested evidence.

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
    require(receipt.get("schema") == "dosepilot.reviewer_route_integrity.v16", "SCHEMA")
    require(receipt.get("status") == "PASS", "STATUS")
    require(receipt.get("role") == "REVIEWER_NAVIGATION_CURRENT_PACKAGE_RUBRIC_SUCCESSOR_AND_CLEAN_PACKAGE_CHRONOLOGY_TRACE_OFFLINE_NESTED_REPORT_NEGATIVE_CONTROL", "ROLE")

    predecessor = receipt.get("predecessor", {})
    predecessor_path = root / predecessor.get("path", "")
    require(sha(predecessor_path) == predecessor.get("sha256"), "PREDECESSOR_HASH")
    require(load(predecessor_path).get("schema") == "dosepilot.reviewer_route_integrity.v15", "PREDECESSOR_SCHEMA")
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
    offline_doc = "docs/VERIFY_DOWNLOADED_TRACE.md"
    offline_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/VERIFY_DOWNLOADED_TRACE.md"
    require(offline_doc in readme, "README_OFFLINE_TRACE_LINK")
    require(offline_doc in reviewer, "REVIEWER_OFFLINE_TRACE_LINK")
    require(offline_url in writeup, "WRITEUP_OFFLINE_TRACE_LINK")
    require("demo/verify_downloaded_trace.py" in readme, "README_OFFLINE_TRACE_COMMAND")
    require("demo/verify_downloaded_trace.py" in reviewer, "REVIEWER_OFFLINE_TRACE_COMMAND")
    package_doc = "docs/FINALIST_PACKAGE_PREFLIGHT_CURRENT.md"
    package_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FINALIST_PACKAGE_PREFLIGHT_CURRENT.md"
    require(package_doc in readme, "README_FINALIST_PREFLIGHT_LINK")
    require(package_doc in reviewer, "REVIEWER_FINALIST_PREFLIGHT_LINK")
    require(package_url in writeup, "WRITEUP_FINALIST_PREFLIGHT_LINK")
    require("study/audits/finalist_package_preflight_current.py" in readme, "README_FINALIST_PREFLIGHT_COMMAND")
    require("study/audits/finalist_package_preflight_current.py" in reviewer, "REVIEWER_FINALIST_PREFLIGHT_COMMAND")
    rubric_doc = "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT.md"
    rubric_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FINALIST_RUBRIC_EVIDENCE_CURRENT.md"
    require(rubric_doc in readme, "README_CURRENT_RUBRIC_LINK")
    require(rubric_doc in reviewer, "REVIEWER_CURRENT_RUBRIC_LINK")
    require(rubric_url in writeup, "WRITEUP_CURRENT_RUBRIC_LINK")
    package_rubric_doc = "docs/FINALIST_RUBRIC_EVIDENCE_CURRENT_PACKAGE.md"
    package_rubric_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/FINALIST_RUBRIC_EVIDENCE_CURRENT_PACKAGE.md"
    require(package_rubric_doc in readme, "README_CURRENT_PACKAGE_RUBRIC_LINK")
    require(package_rubric_doc in reviewer, "REVIEWER_CURRENT_PACKAGE_RUBRIC_LINK")
    require(package_rubric_url in writeup, "WRITEUP_CURRENT_PACKAGE_RUBRIC_LINK")
    for text, label in ((readme, "README"), (reviewer, "REVIEWER"), (writeup, "WRITEUP")):
        require("self-score" in text and ("finalist-probability" in text or "finalist probability" in text), label + "_CURRENT_RUBRIC_BOUNDARY")
    require("current technical report is bound to this 173-test" in readme, "README_CURRENT_REPORT_BINDING")
    require("current technical report is bound to this 173-test" in reviewer, "REVIEWER_CURRENT_REPORT_BINDING")
    require("historical 168-test receipt" in readme, "README_HISTORICAL_168_BINDING")
    require("historical 168-test receipt" in reviewer, "REVIEWER_HISTORICAL_168_BINDING")
    clean_doc = "docs/CLEAN_FINALIST_PACKAGE_EXECUTION.md"
    clean_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/CLEAN_FINALIST_PACKAGE_EXECUTION.md"
    require(clean_doc in readme, "README_CLEAN_PACKAGE_LINK")
    require(clean_doc in reviewer, "REVIEWER_CLEAN_PACKAGE_LINK")
    require(clean_url in writeup, "WRITEUP_CLEAN_PACKAGE_LINK")
    for text, label in ((readme, "README"), (reviewer, "REVIEWER"), (writeup, "WRITEUP")):
        require("8" in text and "173" in text, label + "_CLEAN_PACKAGE_COUNTS")
        require("not a network clone" in text, label + "_CLEAN_PACKAGE_CLONE_BOUNDARY")
        require("clean-new-machine" in text and "independent biological validation" in text, label + "_CLEAN_PACKAGE_SCOPE")
    current_clean_doc = "docs/CLEAN_CURRENT_FINALIST_PACKAGE_EXECUTION.md"
    current_clean_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/CLEAN_CURRENT_FINALIST_PACKAGE_EXECUTION.md"
    require(current_clean_doc in readme, "README_CURRENT_CLEAN_PACKAGE_LINK")
    require(current_clean_doc in reviewer, "REVIEWER_CURRENT_CLEAN_PACKAGE_LINK")
    require(current_clean_url in writeup, "WRITEUP_CURRENT_CLEAN_PACKAGE_LINK")
    for text, label in ((readme, "README"), (reviewer, "REVIEWER"), (writeup, "WRITEUP")):
        require("current rubric successor" in text, label + "_CURRENT_CLEAN_RUBRIC_SUCCESSOR")
        require("local pip cache" in text, label + "_CURRENT_CLEAN_CACHE_BOUNDARY")
        require("not a network clone" in text, label + "_CURRENT_CLEAN_CLONE_BOUNDARY")
        require("clean-new-machine" in text and "independent biological validation" in text, label + "_CURRENT_CLEAN_SCOPE")
    nested_doc = "docs/NESTED_BANDWIDTH_EVALUATION.md"
    nested_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/NESTED_BANDWIDTH_EVALUATION.md"
    require(nested_doc in readme, "README_NESTED_LINK")
    require(nested_doc in reviewer, "REVIEWER_NESTED_LINK")
    require(nested_url in writeup, "WRITEUP_NESTED_LINK")
    plain_readme = readme.replace("**", "")
    plain_reviewer = reviewer.replace("**", "")
    plain_writeup = writeup.replace("**", "")
    require("All 5/5 outer training sets" in plain_readme, "README_NESTED_SELECTION")
    require("all 5/5 outer training sets" in plain_reviewer, "REVIEWER_NESTED_SELECTION")
    require("all 5/5 outer training sets" in plain_writeup, "WRITEUP_NESTED_SELECTION")
    for text, label in ((readme, "README"), (reviewer, "REVIEWER"), (writeup, "WRITEUP")):
        require("not independent validation" in text, label + "_NESTED_BOUNDARY")
    coopt_doc = "docs/COOPTIMIZED_CALIBRATED_CONTROL_NEGATIVE.md"
    coopt_url = "https://github.com/josepha-mayo/von-dosepilot/blob/master/docs/COOPTIMIZED_CALIBRATED_CONTROL_NEGATIVE.md"
    require(coopt_doc in readme, "README_COOPT_LINK")
    require(coopt_doc in reviewer, "REVIEWER_COOPT_LINK")
    require(coopt_url in writeup, "WRITEUP_COOPT_LINK")
    for text, label in ((plain_readme, "README"), (plain_reviewer, "REVIEWER"), (plain_writeup, "WRITEUP")):
        require("3/59" in text and "0/5" in text and "22/24" in text, label + "_COOPT_ADVERSE_SLICES")
        require("no retry" in text and "not independent validation" in text, label + "_COOPT_BOUNDARY")
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

    offline_record = receipt.get("downloaded_trace_verifier", {})
    offline_path = root / offline_record.get("path", "")
    require(sha(offline_path) == offline_record.get("sha256"), "OFFLINE_TRACE_RECEIPT_HASH")
    offline = load(offline_path)
    require(offline.get("schema") == "dosepilot.downloaded_trace_verifier.v1", "OFFLINE_TRACE_SCHEMA")
    require(offline.get("status") == "PASS", "OFFLINE_TRACE_STATUS")
    offline_verification = offline.get("verification", {})
    require(offline_verification.get("valid_state_cases") == 5, "OFFLINE_TRACE_VALID_CASES")
    require(offline_verification.get("invalid_cases_rejected") == 12, "OFFLINE_TRACE_TAMPER_CASES")
    require(offline_verification.get("exact_six_field_contract") is True, "OFFLINE_TRACE_FIELD_CONTRACT")
    require(offline_verification.get("filename_state_binding") is True, "OFFLINE_TRACE_FILENAME_BINDING")
    require(offline_verification.get("known_public_demo_digests_bound") == 4, "OFFLINE_TRACE_DIGESTS")
    require(offline.get("claim_boundary", {}).get("private_or_protected_inputs_read") is False, "OFFLINE_TRACE_NO_PROTECTED")
    require(offline.get("claim_boundary", {}).get("biological_accuracy_result_created") is False, "OFFLINE_TRACE_NO_BIOLOGY")

    package_record = receipt.get("finalist_package_preflight", {})
    package_path = root / package_record.get("path", "")
    require(sha(package_path) == package_record.get("sha256"), "FINALIST_PREFLIGHT_RECEIPT_HASH")
    package = load(package_path)
    require(package.get("schema") == "dosepilot.finalist_package_preflight.v2", "FINALIST_PREFLIGHT_SCHEMA")
    require(package.get("status") == "PASS", "FINALIST_PREFLIGHT_STATUS")
    require(package.get("package_check_count") == 8, "FINALIST_PREFLIGHT_PACKAGE_CHECKS")
    require(package.get("postcanonical_check_count") == 7, "FINALIST_PREFLIGHT_POSTCANONICAL_CHECKS")
    require(package.get("current_rubric_successor_checked") is True, "FINALIST_PREFLIGHT_CURRENT_RUBRIC")
    require(package.get("checks", [])[-1].get("name") == "current_finalist_rubric_evidence", "FINALIST_PREFLIGHT_CURRENT_RUBRIC_CHECK")
    require(package.get("canonical_release_check_count") == 14, "FINALIST_PREFLIGHT_CANONICAL_STAGES")
    require(package.get("canonical_orchestrated_test_count") == 173, "FINALIST_PREFLIGHT_CANONICAL_TESTS")
    require(package.get("network_requests") == 0, "FINALIST_PREFLIGHT_NETWORK")
    require(package.get("canonical_receipt_rewritten") is False, "FINALIST_PREFLIGHT_CANONICAL_PRESERVED")
    require(package.get("private_or_protected_inputs_read") is False, "FINALIST_PREFLIGHT_NO_PROTECTED")
    require(package.get("biological_accuracy_result_created") is False, "FINALIST_PREFLIGHT_NO_BIOLOGY")

    clean_record = receipt.get("clean_finalist_package_execution", {})
    clean_path = root / clean_record.get("path", "")
    require(sha(clean_path) == clean_record.get("sha256"), "CLEAN_PACKAGE_RECEIPT_HASH")
    clean = load(clean_path)
    require(clean.get("schema") == "dosepilot.clean_finalist_package_execution.v1", "CLEAN_PACKAGE_SCHEMA")
    current_clean_record = receipt.get("clean_current_finalist_package_execution", {})
    current_clean_path = root / current_clean_record.get("path", "")
    require(sha(current_clean_path) == current_clean_record.get("sha256"), "CURRENT_CLEAN_PACKAGE_RECEIPT_HASH")
    current_clean = load(current_clean_path)
    require(current_clean.get("schema") == "dosepilot.clean_current_finalist_package_execution.v1", "CURRENT_CLEAN_PACKAGE_SCHEMA")
    require(current_clean.get("status") == "PASS", "CURRENT_CLEAN_PACKAGE_STATUS")
    current_clean_execution = current_clean.get("execution", {})
    require(current_clean_execution.get("package_checks") == 8, "CURRENT_CLEAN_PACKAGE_CHECKS")
    require(current_clean_execution.get("current_rubric_successor_checked") is True, "CURRENT_CLEAN_PACKAGE_RUBRIC_SUCCESSOR")
    require(current_clean_execution.get("canonical_release_stages") == 14, "CURRENT_CLEAN_PACKAGE_STAGES")
    require(current_clean_execution.get("canonical_orchestrated_tests") == 173, "CURRENT_CLEAN_PACKAGE_TESTS")
    require(clean.get("status") == "PASS", "CLEAN_PACKAGE_STATUS")
    clean_execution = clean.get("execution", {})
    require(clean_execution.get("package_checks") == 8, "CLEAN_PACKAGE_CHECKS")
    require(clean_execution.get("canonical_release_stages") == 14, "CLEAN_PACKAGE_STAGES")
    require(clean_execution.get("canonical_orchestrated_tests") == 173, "CLEAN_PACKAGE_TESTS")
    clean_source = clean.get("source", {})
    require(clean_source.get("fresh_source_directory") is True, "CLEAN_PACKAGE_FRESH_SOURCE")
    require(clean_source.get("fresh_public_clone") is False, "CLEAN_PACKAGE_NOT_PUBLIC_CLONE")
    clean_boundary = clean.get("claim_boundary", {})
    require(clean_boundary.get("clean_new_machine_certification") is False, "CLEAN_PACKAGE_NOT_NEW_MACHINE")
    require(clean_boundary.get("independent_biological_validation") is False, "CLEAN_PACKAGE_NOT_INDEPENDENT")

    rubric_record = receipt.get("current_finalist_rubric_evidence", {})
    rubric_path = root / rubric_record.get("path", "")
    require(sha(rubric_path) == rubric_record.get("sha256"), "CURRENT_RUBRIC_RECEIPT_HASH")
    rubric = load(rubric_path)
    require(rubric.get("schema") == "dosepilot.finalist_rubric_evidence.v2", "CURRENT_RUBRIC_SCHEMA")
    require(rubric.get("status") == "PASS", "CURRENT_RUBRIC_STATUS")
    require(rubric.get("role") == "CURRENT_JUDGE_CRITERION_TO_EVIDENCE_MAP", "CURRENT_RUBRIC_ROLE")
    require(rubric.get("rubric", {}).get("weights") == {
        "problem_importance_impact": 30,
        "technical_approach_innovation": 30,
        "results_validation": 20,
        "reproducibility_implementation": 10,
        "presentation": 10,
    }, "CURRENT_RUBRIC_WEIGHTS")
    require(rubric.get("rubric", {}).get("combined_self_score") is None, "CURRENT_RUBRIC_NO_SELF_SCORE")
    rubric_boundary = rubric.get("claim_boundary", {})
    require(rubric_boundary.get("finalist_status_claimed") is False, "CURRENT_RUBRIC_NO_FINALIST_STATUS")
    require(rubric_boundary.get("accepted_kaggle_entry_changed") is False, "CURRENT_RUBRIC_NO_KAGGLE_CHANGE")
    require(rubric_boundary.get("independent_validation_created") is False, "CURRENT_RUBRIC_NO_INDEPENDENT_VALIDATION")

    package_rubric_record = receipt.get("current_package_finalist_rubric_evidence", {})
    package_rubric_path = root / package_rubric_record.get("path", "")
    require(sha(package_rubric_path) == package_rubric_record.get("sha256"), "CURRENT_PACKAGE_RUBRIC_RECEIPT_HASH")
    package_rubric = load(package_rubric_path)
    require(package_rubric.get("schema") == "dosepilot.finalist_rubric_evidence.v4", "CURRENT_PACKAGE_RUBRIC_SCHEMA")
    require(package_rubric.get("status") == "PASS", "CURRENT_PACKAGE_RUBRIC_STATUS")
    require(package_rubric.get("role") == "CURRENT_JUDGE_CRITERION_TO_EVIDENCE_MAP", "CURRENT_PACKAGE_RUBRIC_ROLE")
    require(package_rubric.get("rubric", {}).get("combined_self_score") is None, "CURRENT_PACKAGE_RUBRIC_NO_SELF_SCORE")
    package_rubric_boundary = package_rubric.get("claim_boundary", {})
    require(package_rubric_boundary.get("finalist_status_claimed") is False, "CURRENT_PACKAGE_RUBRIC_NO_FINALIST_STATUS")
    require(package_rubric_boundary.get("accepted_kaggle_entry_changed") is False, "CURRENT_PACKAGE_RUBRIC_NO_KAGGLE_CHANGE")
    require(package_rubric_boundary.get("independent_validation_created") is False, "CURRENT_PACKAGE_RUBRIC_NO_INDEPENDENT_VALIDATION")
    require(package_rubric_boundary.get("clean_new_machine_certification") is False, "CURRENT_PACKAGE_RUBRIC_NOT_NEW_MACHINE")
    require(package_rubric_boundary.get("live_dependency_download_claimed") is False, "CURRENT_PACKAGE_RUBRIC_NO_LIVE_DOWNLOAD_CLAIM")

    nested_record = receipt.get("nested_bandwidth_evidence", {})
    nested_path = root / nested_record.get("path", "")
    require(sha(nested_path) == nested_record.get("sha256"), "NESTED_RECEIPT_HASH")
    nested = load(nested_path)
    require(nested.get("schema") == "dosepilot.nested_bandwidth_selection.public_evidence.v1", "NESTED_SCHEMA")
    require(nested.get("status") == "PASS", "NESTED_STATUS")
    require(nested.get("selection_counts") == {"0.7": 5, "1.0": 0, "1.4": 0}, "NESTED_SELECTIONS")
    require(nested.get("nested_vs_fixed07", {}).get("prediction_max_absolute_difference") == 0.0, "NESTED_EXACT_EQUALITY")
    require(nested.get("claim_boundary", {}).get("independent_validation") is False, "NESTED_NOT_INDEPENDENT")
    require(nested.get("claim_boundary", {}).get("protected_response_access") is False, "NESTED_NO_PROTECTED")

    coopt_record = receipt.get("cooptimized_control", {})
    coopt_path = root / coopt_record.get("path", "")
    require(sha(coopt_path) == coopt_record.get("sha256"), "COOPT_RECEIPT_HASH")
    coopt = load(coopt_path)
    require(coopt.get("schema") == "dosepilot.cooptimized_calibrated_control.public_result.v1", "COOPT_SCHEMA")
    require(coopt.get("decision") == "REJECT_RETAIN_BANDWIDTH07", "COOPT_DECISION")
    require(coopt.get("metrics", {}).get("cooptimized_calibrated_interpolation", {}).get("mse") == 0.0014389065202742948, "COOPT_MSE")
    comparison = coopt.get("candidate_vs_bandwidth07", {})
    require(comparison.get("patient_wins") == 3, "COOPT_PATIENT_WINS")
    require(comparison.get("fold_wins") == 0, "COOPT_FOLD_WINS")
    require(comparison.get("target_regressions") == 22, "COOPT_TARGET_REGRESSIONS")
    require(coopt.get("verification", {}).get("independent_no_refit_arithmetic_and_budget_audit") == "PASS", "COOPT_NO_REFIT_AUDIT")
    require(coopt.get("family_closed") is True and coopt.get("automatic_retry") is False, "COOPT_CLOSED")
    require(coopt.get("independent_validation") is False and coopt.get("protected_response_access") is False, "COOPT_BOUNDARY")

    report_record = receipt.get("current_report", {})
    report_path = root / report_record.get("path", "")
    require(sha(report_path) == report_record.get("sha256"), "CURRENT_REPORT_RECEIPT_HASH")
    report = load(report_path)
    require(report.get("schema") == "dosepilot.current_technical_report_release.v7", "CURRENT_REPORT_SCHEMA")
    require(report.get("status") == "PASS", "CURRENT_REPORT_STATUS")
    claims = report.get("claim_checks", {})
    require(claims.get("nested_bandwidth_selection_counts") == {"0.7": 5, "1.0": 0, "1.4": 0}, "CURRENT_REPORT_NESTED_SELECTIONS")
    require(claims.get("nested_bandwidth_prediction_max_absolute_difference_vs_fixed07") == 0.0, "CURRENT_REPORT_NESTED_EQUALITY")
    require(claims.get("nested_bandwidth_independent_validation") is False, "CURRENT_REPORT_NESTED_BOUNDARY")
    require(claims.get("cooptimized_control_decision") == "REJECT_RETAIN_BANDWIDTH07", "CURRENT_REPORT_COOPT_DECISION")
    require(claims.get("cooptimized_control_mse") == 0.0014389065202742948, "CURRENT_REPORT_COOPT_MSE")
    require(claims.get("cooptimized_control_patient_wins") == 3, "CURRENT_REPORT_COOPT_PATIENT_WINS")
    require(claims.get("cooptimized_control_fold_wins") == 0, "CURRENT_REPORT_COOPT_FOLD_WINS")
    require(claims.get("cooptimized_control_target_regressions") == 22, "CURRENT_REPORT_COOPT_TARGET_REGRESSIONS")
    require(claims.get("cooptimized_control_no_refit_audit") == "PASS", "CURRENT_REPORT_COOPT_AUDIT")
    require(claims.get("cooptimized_control_family_closed") is True, "CURRENT_REPORT_COOPT_CLOSED")
    require(claims.get("cooptimized_control_independent_validation") is False, "CURRENT_REPORT_COOPT_BOUNDARY")
    require(claims.get("release_preflight_tests") == 173, "CURRENT_REPORT_PREFLIGHT_TESTS")
    require(claims.get("clean_finalist_package_execution_linked") is True, "CURRENT_REPORT_CLEAN_PACKAGE_LINK")
    require(claims.get("clean_finalist_package_checks") == 8, "CURRENT_REPORT_CLEAN_PACKAGE_CHECKS")
    require(claims.get("clean_finalist_package_canonical_stages") == 14, "CURRENT_REPORT_CLEAN_PACKAGE_STAGES")
    require(claims.get("clean_finalist_package_canonical_tests") == 173, "CURRENT_REPORT_CLEAN_PACKAGE_TESTS")
    require(claims.get("clean_finalist_package_fresh_source_directory") is True, "CURRENT_REPORT_CLEAN_PACKAGE_FRESH_SOURCE")
    require(claims.get("clean_finalist_package_fresh_public_clone") is False, "CURRENT_REPORT_CLEAN_PACKAGE_NOT_CLONE")
    require(claims.get("clean_finalist_package_clean_new_machine_certification") is False, "CURRENT_REPORT_CLEAN_PACKAGE_NOT_NEW_MACHINE")
    require(claims.get("clean_finalist_package_independent_biological_validation") is False, "CURRENT_REPORT_CLEAN_PACKAGE_NOT_INDEPENDENT")
    report_entrypoint = (root / report.get("entrypoint", {}).get("path", "")).read_text()
    require("clean isolated 8/8 finalist-package execution" in report_entrypoint, "CURRENT_REPORT_CLEAN_PACKAGE_DOCUMENTED")

    verification = receipt.get("verification", {})
    require(local_targets == verification.get("local_targets"), "LOCAL_TARGET_COUNT")
    require(github_targets == verification.get("github_master_targets"), "GITHUB_TARGET_COUNT")
    require(anchors == verification.get("anchors"), "ANCHOR_COUNT")
    require(verification.get("required_urls") == len(REQUIRED_URLS), "REQUIRED_URL_COUNT")
    require(verification.get("trace_links") == 3, "TRACE_LINK_COUNT")
    require(verification.get("offline_trace_verifier_links") == 3, "OFFLINE_TRACE_LINK_COUNT")
    require(verification.get("finalist_package_preflight_links") == 3, "FINALIST_PREFLIGHT_LINK_COUNT")
    require(verification.get("clean_finalist_package_execution_links") == 3, "CLEAN_PACKAGE_LINK_COUNT")
    require(verification.get("clean_current_finalist_package_execution_links") == 3, "CURRENT_CLEAN_PACKAGE_LINK_COUNT")
    require(verification.get("nested_links") == 3, "NESTED_LINK_COUNT")
    require(verification.get("cooptimized_links") == 3, "COOPT_LINK_COUNT")
    require(verification.get("current_rubric_links") == 3, "CURRENT_RUBRIC_LINK_COUNT")
    require(verification.get("current_package_rubric_links") == 3, "CURRENT_PACKAGE_RUBRIC_LINK_COUNT")
    require(verification.get("current_report_cooptimized_control_documented") is True, "CURRENT_REPORT_COOPT_DOCUMENTED")
    require(verification.get("current_report_clean_finalist_package_documented") is True, "CURRENT_REPORT_CLEAN_PACKAGE_RECEIPT")
    require(verification.get("current_report_bound_test_count") == 173, "CURRENT_REPORT_BOUND_TESTS")
    require(verification.get("historical_168_originally_bound_earlier_report_revision") is True, "HISTORICAL_168_REPORT_BINDING")
    require(verification.get("adversarial_tests_passed") == 22, "ADVERSARIAL_TEST_COUNT")
    require(verification.get("finalist_package_current_rubric_successor_checked") is True, "FINALIST_PREFLIGHT_CURRENT_RUBRIC_BOUND")
    require(verification.get("network_requests") == 0, "NETWORK_REQUESTS")

    failure = receipt.get("preserved_operational_failure", {})
    require(failure.get("status") == "INITIAL_MARKDOWN_NORMALIZATION_DEFECT", "PRESERVED_FAILURE_STATUS")
    require(failure.get("initial_passes") == 9, "PRESERVED_FAILURE_PASSES")
    require(failure.get("initial_failures") == 3, "PRESERVED_FAILURE_FAILURES")
    require(failure.get("initial_errors") == 1, "PRESERVED_FAILURE_ERRORS")
    require(failure.get("scientific_or_product_failure") is False, "PRESERVED_FAILURE_SCOPE")
    require(failure.get("corrected_tests_passed") == 13, "PRESERVED_FAILURE_CORRECTION")

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
        "offline_trace_verifier_links": 3,
        "finalist_package_preflight_links": 3,
        "finalist_package_current_rubric_successor_checked": True,
        "clean_finalist_package_execution_links": 3,
        "clean_current_finalist_package_execution_links": 3,
        "nested_links": 3,
        "cooptimized_links": 3,
        "current_rubric_links": 3,
        "current_package_rubric_links": 3,
        "network_requests": 0,
        "downloadable_trace_linked": True,
        "offline_downloaded_trace_verifier_linked": True,
        "finalist_package_preflight_linked": True,
        "clean_finalist_package_execution_linked": True,
        "clean_current_finalist_package_execution_linked": True,
        "clean_current_finalist_package_checks": 8,
        "clean_current_finalist_package_current_rubric_successor_checked": True,
        "cooptimized_control_linked": True,
        "current_finalist_rubric_evidence_linked": True,
        "current_finalist_rubric_self_score_assigned": False,
        "current_finalist_probability_estimated": False,
        "current_package_finalist_rubric_evidence_linked": True,
        "current_package_finalist_rubric_self_score_assigned": False,
        "current_package_finalist_probability_estimated": False,
        "current_report_cooptimized_control_documented": True,
        "current_report_clean_finalist_package_documented": True,
        "cooptimized_control_decision": "REJECT_RETAIN_BANDWIDTH07",
        "cooptimized_control_independent_validation": False,
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
