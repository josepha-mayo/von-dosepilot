#!/usr/bin/env python3
"""Run the public, response-free release checks from one command."""
from __future__ import annotations
from pathlib import Path
import argparse, datetime, hashlib, json, os, subprocess, sys, tempfile, time

ROOT = Path(__file__).resolve().parents[2]

CHECKS = [
    ("evidence", [sys.executable, "study/audits/verify_evidence_consistency.py", "--root", "."], []),
    ("audit_tests", [sys.executable, "-m", "unittest", "discover", "-s", "study/audits", "-p", "test_*evidence_consistency.py", "-v"],
     ["study/audits"]),
    ("durable_runtime", [sys.executable, "-m", "unittest", "discover", "-s", "study/durable_runtime", "-p", "test_*.py", "-v"],
     ["study/durable_runtime", "study/hybrid_residual", "study/spectral_residual"]),
    ("acquisition", [sys.executable, "-m", "unittest", "discover", "-s", "study/multioutput_acquisition", "-p", "test_*.py", "-v"],
     ["study/engine", "study/acceleration", "study/multioutput_acquisition"]),
    ("structured_kernels", [sys.executable, "-m", "unittest", "discover", "-s", "study/structured_kernels", "-p", "test_*.py", "-v"],
     ["study/hybrid_residual", "study/structured_kernels"]),
    ("aligned_additive", [sys.executable, "-m", "unittest", "discover", "-s", "study/aligned_additive", "-p", "test_*.py", "-v"],
     ["study/hybrid_residual", "study/aligned_additive"]),
    ("ooc_compiler", [sys.executable, "-m", "unittest", "discover", "-s", "demo", "-p", "test_*.py", "-v"], ["demo"]),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    if output.exists():
        raise ValueError("Output exists; choose a fresh path")
    records = []
    with tempfile.TemporaryDirectory(prefix="dosepilot-release-") as temporary:
        demo_output = Path(temporary) / "fictional_lifecycle"
        checks = CHECKS + [("fictional_lifecycle_demo", [
            sys.executable, "study/durable_runtime/run_lifecycle_demo.py",
            "--output", str(demo_output)],
            ["study/durable_runtime", "study/hybrid_residual", "study/spectral_residual"])]
        for name, command, python_paths in checks:
            environment = os.environ.copy()
            if python_paths:
                environment["PYTHONPATH"] = os.pathsep.join(
                    [str(ROOT / item) for item in python_paths]
                    + ([environment["PYTHONPATH"]] if environment.get("PYTHONPATH") else []))
            started = time.monotonic()
            completed = subprocess.run(command, cwd=ROOT, env=environment,
                                       text=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            record = {
                "name": name,
                "command": command,
                "exit_code": completed.returncode,
                "elapsed_seconds": time.monotonic() - started,
                "output_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                "output_tail": completed.stdout[-4000:],
            }
            records.append(record)
            if completed.returncode:
                report = {"schema": "dosepilot.release_preflight.v1", "status": "FAIL",
                          "failed_check": name, "checks": records,
                          "private_or_protected_inputs_read": False}
                output.write_text(json.dumps(report, indent=2) + "\n")
                raise SystemExit(completed.returncode)
    report = {
        "schema": "dosepilot.release_preflight.v1",
        "status": "PASS",
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checks": records,
        "check_count": len(records),
        "source_sha256": digest(Path(__file__)),
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "checks": [item["name"] for item in records]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
