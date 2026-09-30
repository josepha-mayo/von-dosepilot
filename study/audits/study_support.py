"""Strict local input adapter for previously exposed Lib1 TRAIN experiments."""
from __future__ import annotations
import hashlib, importlib.metadata, json, os, sys
from pathlib import Path

LOCK_SHA = '8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')

def setup(study):
    study = Path(study).resolve()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    if sha(study/'STUDY_LOCK.json') != LOCK_SHA:
        raise ValueError('Frozen study lock changed')
    lock = json.loads((study/'STUDY_LOCK.json').read_text())
    for name, expected in lock['engine_files'].items():
        if Path(name).name != name or sha(study/'engine'/name) != expected:
            raise ValueError('Frozen engine changed: '+name)
    for name, expected in lock['deps'].items():
        if importlib.metadata.version(name) != expected:
            raise ValueError('Pinned dependency required: '+name+'=='+expected)
    sys.path[:0] = [str(study), str(study/'engine')]
    return lock

def load_inputs(study, *, curves=None, legacy_inputs=None):
    """Public CSV route or explicit compatibility route, never an automatic fallback."""
    import numpy as np
    if (curves is None) == (legacy_inputs is None):
        raise ValueError('Select exactly one explicit input route')
    lock = setup(study)
    if curves is not None:
        from compact_train import load_prepared, read_catalog
        spec = read_catalog(Path(study)/'TRAIN_CATALOG.json')
        data, features, _ = load_prepared(Path(curves), Path(study)/'TRAIN_CATALOG.json')
        bounds = np.asarray([spec['target_bounds_nM'][str(d)] for d in data['drug_ids']], float)
        route = 'public_compact_csv'
        input_sha = sha(curves)
    else:
        import reproduce_train as old
        import evaluate, evaluate_bracketing
        _, paths = old.check_inputs(Path(legacy_inputs).resolve())
        data, metadata = evaluate.load_train(paths['train'], paths['metadata'])
        features = evaluate_bracketing.load_bracketing_features(data, metadata, paths['train'], paths['curves'], paths['preparation_audit'], paths['query_pool'], paths['contract'])
        with np.load(paths['train'], allow_pickle=False) as z:
            if not np.array_equal(z['drug_ids'], data['drug_ids']):
                raise ValueError('Target identity mismatch')
            bounds = z['common_intervals_nM'].copy()
        route = 'private_historical_compatibility'
        input_sha = sha(paths['curves'])
    if data['y'].shape != (119,24) or len(set(data['patient_ids'])) != 59 or set(data['library_ids']) != {'lib1'}:
        raise ValueError('Frozen cohort changed')
    if input_sha != lock['input_files']['train/train_curves.csv']['sha256']:
        raise ValueError('Exact TRAIN CSV identity changed')
    return data, features, bounds, {'route':route, 'curves_sha256':input_sha, 'private_metadata_kit_used':legacy_inputs is not None}

def patient_risks(error, patients):
    import numpy as np
    ids = np.unique(patients)
    return ids, np.asarray([error[patients == p].mean(axis=0) for p in ids])
