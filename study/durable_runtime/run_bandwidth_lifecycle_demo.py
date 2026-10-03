#!/usr/bin/env python3
"""Exercise the bandwidth-0.7 lifecycle using only seeded fictional data."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "hybrid_residual")]
import bandwidth_lifecycle
from bandwidth_fixture import upgrade_fixture
import test_recover_baseline as fixtures


def run(output):
    if output.exists():
        raise ValueError("Output already exists; choose a fresh directory")
    fixture = fixtures.Tests("test_record_order")
    fixture.setUp()
    try:
        model, anchor, _ = upgrade_fixture(fixture)
        output.mkdir(parents=True, exist_ok=False)
        shutil.copytree(model, output / "model")
        shutil.copy2(fixture.d / "inventory.json", output / "inventory.json")
        ledger = output / "ledger"
        ledger.mkdir()
        common = [
            "--model-dir", str(output / "model"),
            "--construction-sha256", anchor,
            "--ledger-dir", str(ledger),
            "--commitment", str(output / "commitment.json"),
        ]
        environment = os.environ.copy()
        for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            environment[key] = "1"
        events = []

        def cli(command, arguments, expected):
            process = subprocess.run(
                [sys.executable, str(HERE / "bandwidth_lifecycle.py"), command,
                 *common, *arguments],
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            text = process.stdout.strip() if expected == 0 else process.stderr.strip()
            if process.returncode != expected:
                raise RuntimeError("Demo command failed: " + process.stderr)
            result = json.loads(text)
            events.append({"command": command, "expected_exit": expected,
                           "actual_exit": process.returncode, "result": result})
            return result

        cli("commit", ["--inventory", str(output / "inventory.json"),
                       "--template", str(output / "template.json")], 0)
        complete = json.loads((output / "template.json").read_text())
        for row, value in zip(complete["measurements"], fixture.values):
            row["value"] = float(value)
        missing = copy.deepcopy(complete)
        missing["measurements"][0]["value"] = None
        (output / "missing.json").write_text(json.dumps(missing, indent=2) + "\n")
        cli("predict", ["--measurements", str(output / "missing.json"),
                        "--output", str(output / "rejected.json")], 2)
        recovery = cli(
            "recover",
            ["--measurements", str(output / "missing.json"),
             "--output", str(output / "baseline.json"),
             "--acknowledge-baseline-only"],
            0,
        )
        assert recovery["baseline_outputs"] == 23
        changed = copy.deepcopy(complete)
        changed["measurements"][1]["value"] += 0.01
        (output / "changed.json").write_text(json.dumps(changed, indent=2) + "\n")
        rejected = cli("predict", ["--measurements", str(output / "changed.json"),
                                   "--output", str(output / "forbidden.json")], 2)
        assert "OBSERVATION_CHANGED" in rejected["reason"]
        (output / "complete.json").write_text(json.dumps(complete, indent=2) + "\n")
        result = cli("predict", ["--measurements", str(output / "complete.json"),
                                 "--output", str(output / "primary.json")], 0)
        assert result["primary_outputs"] == 24
        before = (output / "primary.json").read_bytes()
        (output / "primary.json").unlink()
        cli("predict", ["--measurements", str(output / "complete.json"),
                        "--output", str(output / "primary.json")], 0)
        assert before == (output / "primary.json").read_bytes()
        summary = {
            "status": "PASS",
            "data": "ALL FICTIONAL; NO BIOLOGICAL VALIDATION",
            "model_kind": "dosepilot.additive_kernel_bandwidth.v1",
            "bandwidth_multiplier": 0.7,
            "lifecycle_policy": bandwidth_lifecycle.POLICY,
            "cli_invocations": len(events),
            "missing_primary_rejected": True,
            "explicit_baseline_outputs": 23,
            "changed_old_reading_rejected_automatically": True,
            "complete_primary_outputs": 24,
            "lost_export_recovered_identically": True,
            "private_data_downloaded": False,
            "clinical_use_validated": False,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        (output / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
        (output / "CLI_TRANSCRIPT.json").write_text(json.dumps(events, indent=2) + "\n")
        (output / "FICTIONAL_DATA_NOTICE.txt").write_text(
            "All model parameters and measurements are seeded fictional fixtures. "
            "This is a software demonstration, not a biological experiment.\n"
        )
        print(json.dumps(summary, indent=2))
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output.resolve())
