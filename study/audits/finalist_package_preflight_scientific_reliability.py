#!/usr/bin/env python3
"""Run the response-free scientific-reliability finalist-package preflight."""
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
    ("current_release_preflight", [sys.executable, "study/audits/release_preflight_current.py"]),
    ("downloaded_trace_self_test", [sys.executable, "demo/verify_downloaded_trace.py", "--self-test"]),
    ("downloaded_trace_receipt", [sys.executable, "study/audits/verify_downloaded_trace_verifier.py", "--root", "."]),
    ("reviewer_routes", [sys.executable, "study/audits/verify_reviewer_routes.py", "--root", "."]),
    ("reviewer_trace_discovery", [sys.executable, "study/audits/verify_reviewer_trace_discovery.py", "--root", "."]),
    ("verification_chronology", [sys.executable, "study/audits/verify_verification_chronology.py", "--root", "."]),
    ("clean_reviewer_quickstart", [sys.executable, "study/audits/verify_clean_reviewer_quickstart.py", "--root", "."]),
    (
        "current_scientific_reliability_finalist_rubric_evidence",
        [sys.executable, "study/audits/verify_finalist_rubric_evidence_current_scientific_reliability.py", "--root", "."],
    ),
]

BOUND_ARTIFACTS = [
    "study/audits/finalist_package_preflight_scientific_reliability.py",
    "study/audits/verify_finalist_package_preflight_scientific_reliability.py",
    "study/audits/test_finalist_package_preflight_scientific_reliability.py",
    "docs/FINALIST_PACKAGE_PREFLIGHT_SCIENTIFIC_RELIABILITY.md",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(records, canonical, status, failed_check):
    canonical = canonical or {}
    return {
        "schema": "dosepilot.finalist_package_preflight.v6",
        "status": status,
        "role": "RESPONSE_FREE_CURRENT_SCIENTIFIC_RELIABILITY_FINALIST_PACKAGE_VERIFICATION",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "predecessor": {
            "path": "evidence/finalist_package_preflight_r5_20261006.json",
            "sha256": "3efb7f2a8d2e4ba15f976b02876b8c96920a43b83d797dc93ec05ba19615155d",
            "preserved_unchanged": True,
        },
        "supersedes_reason": (
            "Replaces only the predecessor's r7 scientific-successor rubric check with "
            "the immutable r8 reliability and clean-execution successor verifier."
        ),
        "current_scientific_reliability_rubric": {
            "path": "evidence/finalist_rubric_evidence_r8_20261006.json",
            "sha256": "73c4da174b1d1149afb093666c571a7e489640bc8ac39c2d45c54716ae23320a",
            "candidate_family": "orientation_specific_control_quality_rank1",
            "candidate_mse": 0.001042745722096212,
            "candidate_p90": 0.037419695944064885,
            "bandwidth07_patient_wins": 40,
            "favorable_folds": 5,
            "target_wins": 19,
            "coverage_90": 0.9194915254237288,
            "targets_at_or_above_90": 24,
            "clean_package_checks": 8,
            "repeated_development": True,
            "independent_validation": False,
            "operational_demo_baseline_replaced": False,
        },
        "failed_check": failed_check,
        "checks": records,
        "package_check_count": len(records),
        "postcanonical_check_count": max(0, len(records) - 1),
        "current_scientific_reliability_rubric_checked": any(
            record.get("name") == "current_scientific_reliability_finalist_rubric_evidence"
            and record.get("exit_code") == 0
            for record in records
        ),
        "canonical_release_check_count": canonical.get("check_count"),
        "canonical_orchestrated_test_count": canonical.get("orchestrated_test_count"),
        "canonical_preflight_sha256": canonical.get("sha256"),
        "artifact_sha256": {relative: sha256(ROOT / relative) for relative in BOUND_ARTIFACTS},
        "network_requests": 0,
        "canonical_receipt_rewritten": False,
        "historical_v5_predecessor_preserved": True,
        "operational_demo_baseline_replaced": False,
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
        "independent_validation_created": False,
        "accepted_kaggle_entry_changed": False,
        "netlify_deployment_changed": False,
        "official_competition_score": None,
    }


def run(output: Path) -> dict:
    output = output.resolve()
    if output.exists():
        raise ValueError("Output exists; choose a fresh path")
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    canonical = None
    with tempfile.TemporaryDirectory(prefix="dosepilot-finalist-package-scientific-reliability-") as temporary:
        canonical_path = Path(temporary) / "current_release_preflight.json"
        for name, base_command in PACKAGE_CHECKS:
            command = list(base_command)
            if name == "current_release_preflight":
                command.extend(["--output", str(canonical_path)])
            started = time.monotonic()
            completed = subprocess.run(
                command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            record = {
                "name": name,
                "command": ["python3", *command[1:-2]]
                if name == "current_release_preflight"
                else ["python3", *command[1:]],
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
        "current_scientific_reliability_rubric_checked": report["current_scientific_reliability_rubric_checked"],
        "candidate_mse": report["current_scientific_reliability_rubric"]["candidate_mse"],
        "canonical_release_stages": report["canonical_release_check_count"],
        "canonical_orchestrated_tests": report["canonical_orchestrated_test_count"],
    }, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)


if __name__ == "__main__":
    main()
