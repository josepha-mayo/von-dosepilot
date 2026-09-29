#!/usr/bin/env python3
"""Reproduce R9 and R13 from a pinned, previously released Lib1 input kit.

This is a new reproducibility run, not new validation or permission to read Lib2.
No historical prediction, fitted-weight, or run-manifest file is an input.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
LOCK_SHA256 = '8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path: Path, value: object) -> None:
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def member(root: Path, relative: str) -> Path:
    p = PurePosixPath(relative)
    if p.is_absolute() or str(p) != relative or '..' in p.parts or '\\' in relative:
        raise ValueError('Unsafe input relative path')
    path = root.joinpath(*p.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Input escapes declared directory')
    return path


def check_inputs(input_dir: Path) -> tuple[dict, dict]:
    if digest(HERE / 'STUDY_LOCK.json') != LOCK_SHA256:
        raise ValueError('Study lock differs from released identity')
    lock = json.loads((HERE / 'STUDY_LOCK.json').read_text())
    for name, wanted in lock['engine_files'].items():
        if digest(member(HERE / 'engine', name)) != wanted:
            raise ValueError('Frozen engine changed: ' + name)
    for name, record in lock['input_files'].items():
        path = member(input_dir, name)
        if not path.is_file() or path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise ValueError('Scientific input changed: ' + name)
    for name, version in lock['deps'].items():
        if importlib.metadata.version(name) != version:
            raise ValueError('Install the pinned dependency version for ' + name)
    paths = {name: member(input_dir, relative) for name, relative in lock['input_roles'].items()}
    return lock, paths


def install_read_audit(inputs: Path, output: Path) -> set[str]:
    """Record file reads and reject undeclared research paths and networking.

    A Python audit hook is a reproducibility tripwire, not an OS security sandbox.
    It also permits the existing interpreter, native libraries and /proc metadata.
    """
    roots = [HERE.resolve(), inputs.resolve(), output.resolve(),
             Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve(),
             Path('/usr').resolve(), Path('/lib').resolve(), Path('/etc').resolve(),
             Path('/proc').resolve(), Path('/sys').resolve()]
    reads: set[str] = set()
    def hook(event, args):
        if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'}:
            raise PermissionError('Reproduction forbids network and child processes')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode = args[1]
            reading = mode is None or 'r' in str(mode) or '+' in str(mode)
            if reading:
                if not any(path.is_relative_to(root) for root in roots) and path != Path('/dev/null'):
                    raise PermissionError('Undeclared file read blocked: ' + str(path))
                reads.add(str(path))
    sys.addaudithook(hook)
    return reads


def regenerate_r9(data, features, output, provenance):
    import numpy as np
    import evaluate as first
    import evaluate_bracketing as bracket
    import bracketing_methods as bm
    from methods import patient_folds
    output.mkdir()
    x, y, patients = features['x'], data['y'], data['patient_ids']
    layout = features['layout']
    folds, assignments = patient_folds(patients, 5, first.SALT + '|outer')
    dump(output/'outer_patient_folds.json', assignments)
    prediction = {family: np.full_like(y, np.nan) for family in bm.PREDICTORS}
    mask = np.zeros_like(x, dtype=bool)
    wells = np.empty((len(y), 32, 2), dtype=object)
    for fold in range(5):
        fit, test = folds != fold, folds == fold
        if set(patients[fit]) & set(patients[test]):
            raise AssertionError('Patient crosses outer split')
        directory = output/f'outer_{fold:02d}'
        directory.mkdir()
        selections = bracket.select_lambdas(x[fit], y[fit], patients[fit], data['sample_ids'][fit],
            layout, directory/'selection', 3, first.SALT + f'|inner|{fold}')
        plan = bm.plan_panel(x[fit], y[fit], patients[fit], layout)
        selected = plan['selected_native_indices']
        paid = bm.acquire(x[test], plan)
        context = bm.fit_prediction_context(bm.acquire(x[fit], plan), y[fit], patients[fit], plan, layout.target_ids)
        mask[np.ix_(np.flatnonzero(test), selected)] = True
        wells[test] = features['well_ids'][test][:, selected]
        if any(len(set(v.ravel())) != 64 for v in wells[test]):
            raise AssertionError('R9 paid-well budget mismatch')
        for family in bm.PREDICTORS:
            model = bm.BracketingPredictor(context, plan, selections[family]['lambda'], family)
            prediction[family][test] = model.predict(paid)
            bracket.save_model(directory/f'model__{family}.npz', model, context)
        dump(directory/'plan.json', plan)
        dump(directory/'selection_result.json', selections)
        np.savez_compressed(directory/'paid_test.npz',sample_ids=data['sample_ids'][test],
            patient_ids=patients[test],paid_native=paid,encoded=bm.encode_paid(paid,plan),
            paid_source_well_ids=wells[test].astype(str),y=y[test])
        print(json.dumps({'event':'r9_reproduction_fold','fold':fold}),flush=True)
    if any(not np.isfinite(p).all() for p in prediction.values()):
        raise AssertionError('R9 predictions incomplete')
    np.savez_compressed(output/'oof_predictions.npz', **data, folds=folds,
        native_ids=layout.native_ids,action_mask=mask,paid_source_well_ids=wells.astype(str),**prediction)
    manifest={'schema':'von.r9_reproduction.v1','committed':True,'historical_run_identity_claimed':False,
              'provenance':provenance,'files':{str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    dump(output/'MANIFEST.json',manifest)
    return {'prediction':prediction['own_drug_all24'],'folds':folds,'well_ids':wells.astype(str),'action_mask':mask,
            'provenance':{'schema':'von.reference_reproduction.v1','manifest_sha256':digest(output/'MANIFEST.json'),
                          'reference_refit':True,'historical_run_identity_claimed':False,
                          'oof_sha256':digest(output/'oof_predictions.npz')}},prediction


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists():
        print('ERROR: output already exists; no overwrite or implicit retry',file=sys.stderr)
        return 2
    try:
        lock,paths=check_inputs(args.inputs.resolve())
    except Exception as exc:
        print('ERROR: preflight: '+str(exc),file=sys.stderr)
        return 2
    if args.check_only:
        print(json.dumps({'status':'preflight_passed','numerical_inputs_loaded':False,
            'code_files':len(lock['engine_files']),'input_files':len(lock['input_files'])}))
        return 0
    output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    provenance={'role':'reproduction_of_published_private_TRAIN_result_not_new_validation',
        'historical_manifest_hashes':lock['historical_source_manifests'],
        'study_lock_sha256':LOCK_SHA256,'wrapper_sha256':digest(Path(__file__)),
        'independent_reviewer':False,'original_source_workbook_opened':False,
        'protected_response_access':False,'old_predictions_or_models_input':False,
        'python_version':platform.python_version(),'deps':lock['deps']}
    dump(output/'ATTEMPT_STARTED.json',{'created_unix':time.time(),'provenance':provenance})
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name]='1'
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(HERE/'engine'))
    try:
        import numpy as np
        import evaluate as first
        import evaluate_bracketing as bracket
        import evaluate_coverage as coverage
        from threadpoolctl import threadpool_limits, ThreadpoolController
        # Discover native libraries before the scientific I/O tripwire. This may
        # call the platform loader, but reads no research inputs or model data.
        ThreadpoolController()
        readset=install_read_audit(args.inputs.resolve(),output)
        data,metadata=first.load_train(paths['train'],paths['metadata'])
        if list(data['y'].shape)!=lock['expected_shape'] or len(set(data['patient_ids']))!=lock['expected_patients']:
            raise ValueError('Fixed TRAIN cohort identity/shape changed')
        if set(data['library_ids'])!={'lib1'}:
            raise ValueError('Non-TRAIN library prohibited')
        features=bracket.load_bracketing_features(data,metadata,paths['train'],paths['curves'],paths['preparation_audit'],paths['query_pool'],paths['contract'])
        with threadpool_limits(limits=1):
            reference,reference_predictions=regenerate_r9(data,features,output/'r9_reproduction',provenance)
            result=coverage.run(data,features,reference,output/'r13_reproduction',provenance)
        def mse(p):
            _,risk=coverage.patient_errors((p-data['y'])**2,data['patient_ids'])
            return float(risk.mean())
        metrics={'r9_own24':mse(reference_predictions['own_drug_all24']),
                 'r9_shared24':mse(reference_predictions['shared_all24']),
                 'r13_single64_expected_loss':result['metrics']['single64_expected_loss']['all24']['mse'],
                 'r13_matched_paired_native':result['metrics']['matched_paired_native']['all24']['mse']}
        comparisons={name:{'observed':value,'reference':lock['expected_mse'][name],
            'absolute_difference':abs(value-lock['expected_mse'][name]),
            'matches':bool(np.isclose(value,lock['expected_mse'][name],rtol=0,atol=lock['absolute_mse_tolerance']))}
            for name,value in metrics.items()}
        status=all(c['matches'] for c in comparisons.values())
        dump(output/'READ_AUDIT.json',{'mechanism':'Python audit hook, not OS sandbox','read_paths':sorted(readset),
            'network_and_children_blocked':True,'historical_prediction_or_weight_paths':[]})
        receipt={'status':'reproduced' if status else 'mismatch','comparisons':comparisons,
            'seconds':time.perf_counter()-started,'new_validation':False,'new_predictive_gain':False,
            'provenance':provenance,'physical_budget':64,'historical_manifest_impersonated':False}
        dump(output/'RESULT.json',receipt)
        if not status:
            raise AssertionError('One or more fixed published metrics failed reproduction')
        dump(output/'MANIFEST.json',{'schema':'von.real_train_reproduction.v1','committed':True,
            'files':{str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file()}})
        print(json.dumps(receipt,indent=2),flush=True)
        return 0
    except Exception as exc:
        dump(output/'FAILURE.json',{'error':str(exc),'type':type(exc).__name__,
            'traceback':traceback.format_exc(),'elapsed_seconds':time.perf_counter()-started,
            'preserve_all_outputs':True,'retry_performed':False})
        print('ERROR: reproduction failed; evidence retained: '+str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
