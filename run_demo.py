#!/usr/bin/env python3
"""Run the preserved fictional DosePilot operating workflow; never a study fit."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh result directory")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    output = args.output.expanduser().resolve()
    if output.exists():
        parser.error("Refusing existing output directory")
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(here / "demo" / "run_operating_demo.py"),
             "--output", str(output)],
            cwd=here / "demo", check=False,
        )
    except OSError as exc:
        print(f"Could not start demo: {exc}", file=sys.stderr)
        return 2
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
