#!/usr/bin/env python3
"""Offline verifier for a JSON trace downloaded from the fictional demo.

This checks the six-field export contract and the exact public-demo digests. It
does not authenticate who created the file and is not physical or biological
provenance.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SCHEMA = "dosepilot.browser_demo_trace.v1"
FIELDS = (
    "schema",
    "state",
    "plan_sha256",
    "measurement_sha256",
    "result_sha256",
    "result_kind",
)
PLAN = "e1f2b0c63bb4a3db78568cbf331b247475b6eba7d6794c835a9d42941b3e748e"
BASELINE = "90ff9f3bfd8c4982ae2dc00adbb68067d43c14dc0a0bfb9b9789126b39644194"
MEASUREMENT = "71a23a872e794f60751def3dcd2a27b54453b9b481fa736099269d549941573d"
PRIMARY = "ed48e0320d740685b350373e72dce6f736a86c78992bfdd481a92439ca9181a6"
STATE_CONTRACTS = {
    "fresh": (None, None, None, "withheld"),
    "committed": (PLAN, None, None, "withheld"),
    "missing": (PLAN, None, None, "withheld"),
    "recovered": (PLAN, None, BASELINE, "historical baseline • 23 outputs"),
    "complete": (PLAN, MEASUREMENT, PRIMARY, "bandwidth-0.7 primary • 24 outputs"),
}
MAX_BYTES = 4096
LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TraceVerificationError(ValueError):
    """A stable, reviewer-readable verification failure."""


def object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TraceVerificationError("DUPLICATE_FIELD: " + key)
        result[key] = value
    return result


def parse_record(raw: bytes):
    if len(raw) > MAX_BYTES:
        raise TraceVerificationError("FILE_TOO_LARGE")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TraceVerificationError("NOT_UTF8") from error
    try:
        record = json.loads(text, object_pairs_hook=object_without_duplicates)
    except TraceVerificationError:
        raise
    except json.JSONDecodeError as error:
        raise TraceVerificationError("INVALID_JSON") from error
    if not isinstance(record, dict):
        raise TraceVerificationError("NOT_JSON_OBJECT")
    return record


def validate_record(record, expected_filename: str | None = None):
    if tuple(record) != FIELDS:
        missing = sorted(set(FIELDS) - set(record))
        extra = sorted(set(record) - set(FIELDS))
        if missing:
            raise TraceVerificationError("MISSING_FIELDS: " + ",".join(missing))
        if extra:
            raise TraceVerificationError("EXTRA_FIELDS: " + ",".join(extra))
        raise TraceVerificationError("FIELD_ORDER")
    if record["schema"] != SCHEMA:
        raise TraceVerificationError("SCHEMA")
    state = record["state"]
    if state not in STATE_CONTRACTS:
        raise TraceVerificationError("STATE")
    if expected_filename is not None:
        expected = f"dosepilot-trace-{state}.json"
        if Path(expected_filename).name != expected:
            raise TraceVerificationError("FILENAME_STATE_MISMATCH")
    for field in ("plan_sha256", "measurement_sha256", "result_sha256"):
        value = record[field]
        if value is not None and (not isinstance(value, str) or LOWER_SHA256.fullmatch(value) is None):
            raise TraceVerificationError("DIGEST_FORMAT: " + field)
    expected = STATE_CONTRACTS[state]
    actual = (
        record["plan_sha256"],
        record["measurement_sha256"],
        record["result_sha256"],
        record["result_kind"],
    )
    labels = ("PLAN_DIGEST", "MEASUREMENT_DIGEST", "RESULT_DIGEST", "RESULT_KIND")
    for label, actual_value, expected_value in zip(labels, actual, expected):
        if actual_value != expected_value:
            raise TraceVerificationError(label)
    return {
        "status": "PASS",
        "schema": SCHEMA,
        "state": state,
        "filename_checked": expected_filename is not None,
        "exact_field_set": True,
        "state_contract_matched": True,
        "known_public_demo_digests_matched": True,
        "contains_raw_readings_or_model_outputs": False,
        "signed_or_authenticated": False,
        "physical_or_biological_provenance": False,
    }


def canonical_record(state: str):
    plan, measurement, result, kind = STATE_CONTRACTS[state]
    return {
        "schema": SCHEMA,
        "state": state,
        "plan_sha256": plan,
        "measurement_sha256": measurement,
        "result_sha256": result,
        "result_kind": kind,
    }


def self_test():
    valid = 0
    for state in STATE_CONTRACTS:
        record = canonical_record(state)
        parsed = parse_record((json.dumps(record) + "\n").encode())
        validate_record(parsed, f"dosepilot-trace-{state}.json")
        valid += 1

    invalid_cases = []

    def reject(label, record=None, filename=None, raw=None):
        try:
            parsed = parse_record(raw if raw is not None else (json.dumps(record) + "\n").encode())
            validate_record(parsed, filename)
        except TraceVerificationError:
            invalid_cases.append(label)
            return
        raise AssertionError("self-test accepted invalid case: " + label)

    changed = canonical_record("complete")
    changed["result_sha256"] = "0" * 64
    reject("changed_result", changed, "dosepilot-trace-complete.json")
    changed = canonical_record("complete")
    changed["measurement_sha256"] = MEASUREMENT.upper()
    reject("uppercase_digest", changed, "dosepilot-trace-complete.json")
    changed = canonical_record("recovered")
    changed["measurement_sha256"] = MEASUREMENT
    reject("invented_recovery_measurement", changed, "dosepilot-trace-recovered.json")
    changed = canonical_record("missing")
    changed["result_kind"] = "historical baseline • 23 outputs"
    reject("wrong_result_kind", changed, "dosepilot-trace-missing.json")
    changed = canonical_record("fresh")
    changed["raw_readings"] = [0.1]
    reject("extra_raw_readings", changed, "dosepilot-trace-fresh.json")
    changed = canonical_record("fresh")
    changed.pop("result_kind")
    reject("missing_field", changed, "dosepilot-trace-fresh.json")
    changed = canonical_record("fresh")
    changed["schema"] = "dosepilot.browser_demo_trace.v2"
    reject("wrong_schema", changed, "dosepilot-trace-fresh.json")
    changed = canonical_record("fresh")
    changed["state"] = "reset"
    reject("unknown_state", changed, "dosepilot-trace-reset.json")
    reject("filename_mismatch", canonical_record("complete"), "dosepilot-trace-recovered.json")
    reject("malformed_json", raw=b"{not json", filename="dosepilot-trace-fresh.json")
    duplicate = '{"schema":"dosepilot.browser_demo_trace.v1","schema":"x"}'
    reject("duplicate_field", raw=duplicate.encode(), filename="dosepilot-trace-fresh.json")
    reject("oversize", raw=b" " * (MAX_BYTES + 1), filename="dosepilot-trace-fresh.json")
    return {
        "status": "PASS",
        "valid_state_cases": valid,
        "invalid_cases_rejected": len(invalid_cases),
        "invalid_case_labels": invalid_cases,
        "private_or_protected_inputs_read": False,
        "biological_accuracy_result_created": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", nargs="?", help="downloaded JSON path, or - for stdin")
    parser.add_argument("--expected-filename", help="required when checking stdin filename semantics")
    parser.add_argument("--self-test", action="store_true", help="run five valid and twelve tamper cases")
    args = parser.parse_args()
    if args.self_test:
        if args.trace:
            parser.error("trace is not accepted with --self-test")
        print(json.dumps(self_test(), indent=2, sort_keys=True))
        return
    if not args.trace:
        parser.error("trace is required unless --self-test is used")
    if args.trace == "-":
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        filename = args.expected_filename
    else:
        path = Path(args.trace)
        raw = path.read_bytes()
        filename = args.expected_filename or path.name
    result = validate_record(parse_record(raw), filename)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, TraceVerificationError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}), file=sys.stderr)
        raise SystemExit(2)
