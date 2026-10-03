#!/usr/bin/env python3
"""Run the current public release checks, including the endpoint contract.

The historical release_preflight.py remains byte-pinned by the frozen-schedule
receipt. This additive runner extends it without rewriting that evidence.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from release_preflight import CHECKS as HISTORICAL_CHECKS
from release_preflight import ROOT, digest, unittest_count


CHECKS = HISTORICAL_CHECKS + [
    (
        "target_definition_tests",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "study/audits",
            "-p",
            "test_target_definitions.py",
            "-v",
        ],
        ["study/audits"],
    ),
    (
        "target_definitions",
        [sys.executable, "study/audits/verify_target_definitions.py", "--root", "."],
        ["study/audits"],
    ),
]


def run(output: Path):
    if output.exists():
        raise ValueError("Output exists; choose a fresh path")
    records = []
    with tempfile.TemporaryDirectory(prefix="dosepilot-current-release-") as temporary:
        demo_output = Path(temporary) / "fictional_lifecycle"
        bandwidth_demo_output = Path(temporary) / "fictional_bandwidth_lifecycle"
        checks = CHECKS + [
            (
                "fictional_lifecycle_demo",
                [
                    sys.executable,
                    "study/durable_runtime/run_lifecycle_demo.py",
                    "--output",
                    str(demo_output),
                ],
                ["study/durable_runtime", "study/hybrid_residual", "study/spectral_residual"],
            ),
            (
                "fictional_bandwidth_lifecycle_demo",
                [
                    sys.executable,
                    "study/durable_runtime/run_bandwidth_lifecycle_demo.py",
                    "--output",
                    str(bandwidth_demo_output),
                ],
                ["study/durable_runtime", "study/hybrid_residual", "study/spectral_residual"],
            ),
        ]
        for name, command, python_paths in checks:
            environment = os.environ.copy()
            if python_paths:
                environment["PYTHONPATH"] = os.pathsep.join(
                    [str(ROOT / item) for item in python_paths]
                    + ([environment["PYTHONPATH"]] if environment.get("PYTHONPATH") else [])
                )
            started = time.monotonic()
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            record = {
                "name": name,
                "command": command,
                "exit_code": completed.returncode,
                "elapsed_seconds": time.monotonic() - started,
                "output_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                "output_tail": completed.stdout[-4000:],
                "unittest_count": unittest_count(completed.stdout),
            }
            records.append(record)
            if completed.returncode:
                report = {
                    "schema": "dosepilot.current_release_preflight.v1",
                    "status": "FAIL",
                    "failed_check": name,
                    "checks": records,
                    "private_or_protected_inputs_read": False,
                }
                output.write_text(json.dumps(report, indent=2) + "\n")
                raise SystemExit(completed.returncode)
    report = {
        "schema": "dosepilot.current_release_preflight.v1",
        "status": "PASS",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checks": records,
        "check_count": len(records),
        "orchestrated_test_count": sum(item["unittest_count"] for item in records),
        "target_definition_tests_included": True,
        "target_definition_verifier_included": True,
        "fictional_lifecycle_demo_completed": any(
            item["name"] == "fictional_lifecycle_demo" and item["exit_code"] == 0
            for item in records
        ),
        "fictional_bandwidth_lifecycle_demo_completed": any(
            item["name"] == "fictional_bandwidth_lifecycle_demo" and item["exit_code"] == 0
            for item in records
        ),
        "historical_preflight_source_sha256": digest(ROOT / "study/audits/release_preflight.py"),
        "source_sha256": digest(Path(__file__)),
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
        "accepted_kaggle_entry_changed": False,
        "official_competition_score": None,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"status": "PASS", "checks": [item["name"] for item in records]},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)

