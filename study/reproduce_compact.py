#!/usr/bin/env python3
"""Reproduce the fixed R9/R13 development results from one verified TRAIN CSV.

No private per-record metadata kit, cached predictions, raw workbook, paid
service or accelerator is required. The CSV is still a caller-supplied research
input. This command does not perform an independent biological validation.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
LOCK_SHA = '8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
sys.path.insert(0, str(HERE / 'engine'))
sys.dont_write_bytecode = True


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: object) -> None:
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--curves', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Output exists: preserve prior attempts and choose a new path explicitly')
    try:
        if digest(HERE / 'STUDY_LOCK.json') != LOCK_SHA:
            raise ValueError('Frozen scientific lock changed')
        lock = json.loads((HERE / 'STUDY_LOCK.json').read_text())
        for name, expected in lock['engine_files'].items():
            if Path(name).name != name or digest(HERE / 'engine' / name) != expected:
                raise ValueError('Frozen engine changed: ' + name)
        for name, expected in lock['deps'].items():
            if importlib.metadata.version(name) != expected:
                raise ValueError('Install pinned study dependency: ' + name + '==' + expected)
        from compact_train import load_prepared, CATALOG_SHA256
        # This consumes only the caller-supplied CSV and patient-free catalog.
        data, features, _ = load_prepared(args.curves.resolve(), HERE / 'TRAIN_CATALOG.json')
    except Exception as exc:
        print('Preflight failed: ' + str(exc), file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    provenance = {
        'role': 'Compact input-route reproduction of historical development results',
        'python': platform.python_version(), 'deps': lock['deps'],
        'study_lock_sha256': LOCK_SHA, 'catalog_sha256': CATALOG_SHA256,
        'wrapper_sha256': digest(Path(__file__)),
        'loader_sha256': digest(HERE / 'compact_train.py'),
        'curves_sha256': features['audit']['curve_sha256'],
        'private_metadata_kit_used': False, 'original_source_workbook_opened': False,
        'protected_response_access': False, 'old_predictions_or_weights_input': False,
        'independent_validation': False, 'new_accuracy_gain': False,
    }
    dump(output / 'ATTEMPT_STARTED.json', {'unix': time.time(), 'provenance': provenance})
    try:
        import evaluate_coverage as coverage
        from threadpoolctl import threadpool_limits
        from reproduce_train import regenerate_r9
        with threadpool_limits(limits=1):
            reference, r9 = regenerate_r9(data, features, output / 'r9', provenance)
            r13 = coverage.run(data, features, reference, output / 'r13', provenance)
        def mse(prediction):
            return float(coverage.patient_errors((prediction-data['y'])**2, data['patient_ids'])[1].mean())
        observed = {
            'r9_own24': mse(r9['own_drug_all24']),
            'r9_shared24': mse(r9['shared_all24']),
            'r13_single64_expected_loss': r13['metrics']['single64_expected_loss']['all24']['mse'],
            'r13_matched_paired_native': r13['metrics']['matched_paired_native']['all24']['mse'],
        }
        comparisons = {k: {'observed': v, 'expected': lock['expected_mse'][k],
                          'absolute_difference': abs(v-lock['expected_mse'][k]),
                          'matches': abs(v-lock['expected_mse'][k]) <= lock['absolute_mse_tolerance']}
                       for k, v in observed.items()}
        success = all(c['matches'] for c in comparisons.values())
        result = {'status': 'PASS' if success else 'MISMATCH', 'comparisons': comparisons,
                  'seconds': time.perf_counter()-started, 'input_audit': features['audit'],
                  'provenance': provenance, 'new_accuracy_gain': False,
                  'public_raw_source_end_to_end_completed': False}
        dump(output / 'RESULT.json', result)
        print(json.dumps(result, indent=2), flush=True)
        return 0 if success else 1
    except Exception as exc:
        dump(output / 'FAILURE.json', {'type': type(exc).__name__, 'message': str(exc),
             'traceback': traceback.format_exc(), 'automatic_retry': False})
        print('Reproduction failed; preserve outputs: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
