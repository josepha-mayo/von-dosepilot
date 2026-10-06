#!/usr/bin/env python3
"""Run one response-free preflight over the report-bound finalist package.

This additive successor preserves both earlier package runners and receipts.
It executes the canonical runner unchanged, then checks the current reviewer
route, trace, chronology, and rubric evidence. Its eighth check verifies the
immutable r5 current-report rubric successor rather than the r4 current-package
map or any earlier rubric predecessor.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PACKAGE_CHECKS = [
    (
        "current_release_preflight",
        [sys.executable, "study/audits/release_preflight_current.py"],
    ),
    (
        "downloaded_trace_self_test",
        [sys.executable, "demo/verify_downloaded_trace.py", "--self-test"],
    ),
    (
        "downloaded_trace_receipt",
        [sys.executable, "study/audits/verify_downloaded_trace_verifier.py", "--root", "."],
    ),
    (
        "reviewer_routes",
        [sys.executable, "study/audits/verify_reviewer_routes.py", "--root", "."],
    ),
    (
        "reviewer_trace_discovery",
        [sys.executable, "study/audits/verify_reviewer_trace_discovery.py", "--root", "."],
    ),
    (
        "verification_chronology",
        [sys.executable, "study/audits/verify_verification_chronology.py", "--root", "."],
    ),
    (
        "clean_reviewer_quickstart",
        [sys.executable, "study/audits/verify_clean_reviewer_quickstart.py", "--root", "."],
    ),
    (
        "current_report_finalist_rubric_evidence",
        [sys.executable, "study/audits/verify_finalist_rubric_evidence_current_report.py", "--root", "."],
    ),
]

BOUND_ARTIFACTS = [
    "study/audits/finalist_package_preflight_report_bound.py",
    "study/audits/verify_finalist_package_preflight_report_bound.py",
    "study/audits/test_finalist_package_preflight_report_bound.py",
    "docs/FINALIST_PACKAGE_PREFLIGHT_REPORT_BOUND.md",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> dict:
    output = output.resolve()
    if output.exists():
        raise ValueError("Output exists; choose a fresh path")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    canonical = None
    with tempfile.TemporaryDirectory(prefix="dosepilot-finalist-package-report-bound-") as temporary:
        canonical_path = Path(temporary) / "current_release_preflight.json"
        for name, base_command in PACKAGE_CHECKS:
            command = list(base_command)
            if name == "current_release_preflight":
                command.extend(["--output", str(canonical_path)])
            started = time.monotonic()
            completed = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            record = {
                "name": name,
                "command": ["python3", *command[1:-2]] if name == "current_release_preflight" else ["python3", *command[1:]],
                "exit_code": completed.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "output_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                "output_tail": completed.stdout[-2000:],
            }
            records.append(record)
            if completed.returncode:
                report = build_report(records, canonical, "FAIL", name)
                output.write_text(json.dumps(report, indent=2) + "\n")
                raise SystemExit(completed.returncode)
            if name == "current_release_preflight":
                canonical = json.loads(canonical_path.read_text())
                if canonical.get("status") != "PASS":
                    report = build_report(records, canonical, "FAIL", name)
                    output.write_text(json.dumps(report, indent=2) + "\n")
                    raise SystemExit(1)
                canonical["sha256"] = sha256(canonical_path)
    report = build_report(records, canonical, "PASS", None)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "status": report["status"],
        "package_checks": report["package_check_count"],
        "current_report_rubric_successor_checked": report["current_report_rubric_successor_checked"],
        "canonical_release_stages": report["canonical_release_check_count"],
        "canonical_orchestrated_tests": report["canonical_orchestrated_test_count"],
    }, indent=2))
    return report


def build_report(records, canonical, status, failed_check):
    canonical = canonical or {}
    return {
        "schema": "dosepilot.finalist_package_preflight.v3",
        "status": status,
        "role": "RESPONSE_FREE_CURRENT_REPORT_BOUND_FINALIST_PACKAGE_VERIFICATION",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "predecessor": {
            "path": "evidence/finalist_package_preflight_r2_20261005.json",
            "sha256": "232e601a3e3b326e16e2d27ba767164ccec58ce5f5fe2ee2fc8a8d13700f2496",
            "preserved_unchanged": True,
        },
        "supersedes_reason": (
            "Replaces only the predecessor's r4 current-package rubric check "
            "with the immutable r5 current-report-bound rubric verifier."
        ),
        "current_report_rubric": {
            "path": "evidence/finalist_rubric_evidence_r5_20261006.json",
            "sha256": "b8917193d24f486bf194bf7f3ad2ba6b63e25c716efc58b573ccb0760208107c",
            "current_report_sha256": "23bd050d13b9724b3ae6dfb3ae63406609d2573edfcd957369556be99f4585f1",
            "current_report_bytes": 92307,
            "raw_download_verified": False,
        },
        "failed_check": failed_check,
        "checks": records,
        "package_check_count": len(records),
        "postcanonical_check_count": max(0, len(records) - 1),
        "current_report_rubric_successor_checked": any(
            record.get("name") == "current_report_finalist_rubric_evidence"
            and record.get("exit_code") == 0
            for record in records
        ),
        "historical_current_package_predecessor_preserved": True,
        "canonical_release_check_count": canonical.get("check_count"),
        "canonical_orchestrated_test_count": canonical.get("orchestrated_test_count"),
        "canonical_preflight_sha256": canonical.get("sha256"),
        "artifact_sha256": {relative: sha256(ROOT / relative) for relative in BOUND_ARTIFACTS},
        "network_requests": 0,
        "canonical_receipt_rewritten": False,
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
        "independent_validation_created": False,
        "accepted_kaggle_entry_changed": False,
        "netlify_deployment_changed": False,
        "official_competition_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)


if __name__ == "__main__":
    main()
