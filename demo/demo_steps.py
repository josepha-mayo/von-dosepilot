#!/usr/bin/env python3
"""Recorded synthetic CLI demonstration; no fitting, source workbook, or network.

Each step invokes the unchanged R21/R24 programs. Fresh output paths are required.
Raw command, exit, elapsed time and output records are retained in COMMANDS.jsonl.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def load(path: Path):
    return json.loads(path.read_text())

def new_json(path: Path, value) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')

def verify_assets():
    manifest = load(HERE/'PACKAGE_MANIFEST.json')
    for name, item in manifest['files'].items():
        b = (HERE/name).read_bytes()
        if len(b) != item['bytes'] or sha(b) != item['sha256']:
            raise ValueError('Original synthetic asset changed: '+name)
    return manifest

def invoke(out: Path, label: str, script: str, args: list[str], expected: int):
    argv = [sys.executable, '-B', str(HERE/script), *args]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    t = time.perf_counter()
    r = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env)
    record = dict(label=label, argv=argv, expected_exit=expected, actual_exit=r.returncode,
                  elapsed_seconds=time.perf_counter()-t, stdout=r.stdout, stderr=r.stderr,
                  synthetic=True, biological_fit=False)
    with (out/'COMMANDS.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, allow_nan=False)+'\n')
    # Display the actual CLI response. Line wrapping is the terminal's only formatting.
    print((r.stdout+r.stderr).strip(), flush=True)
    print(f'[actual process exit: {r.returncode}; expected: {expected}]', flush=True)
    if r.returncode != expected:
        raise RuntimeError(label+' did not produce its expected exit')
    return r

def common(manifest, ledger):
    return ['--model', str(HERE/'model.json'), '--model-sha256', manifest['files']['model.json']['sha256'], '--ledger', str(ledger)]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('step', choices=['prepare','plan','predict','missing','reject','recover','evidence'])
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args(); out=a.output.resolve(); m=verify_assets()
    inv=load(HERE/'inventory.json'); model=load(HERE/'model.json')
    if a.step=='prepare':
        out.mkdir(parents=True, exist_ok=False); (out/'ledger').mkdir()
        new_json(out/'CAPTURE_SCOPE.json', {'scope':'WHOLLY INVENTED SOFTWARE DEMONSTRATION',
            'sample': inv['sample_id'], 'biological_weights_included':False,
            'model_sha256':m['files']['model.json']['sha256'],
            'old_runtime_sha256':m['files']['dosepilot.py']['sha256'],
            'laboratory_execution':False, 'source_workbook_read':False,
            'live_model_api':False, 'protected_values_read':False})
        print('Verified all 9 original synthetic package payloads.')
        print('Sample: '+inv['sample_id']+' | Run: '+inv['run_id'])
        print(f"Available fictional inventory: {len(inv['wells'])} physical wells.")
        print('Required acquisition: 64 treatment wells, 32 per plate.')
        print('Controls are additional. The plan is fixed, not an arbitrary-budget optimizer.')
        print('All parameters, drug identifiers and measurements in this demo are invented.')
        return
    if not (out/'CAPTURE_SCOPE.json').exists():
        raise ValueError('Run prepare once in a fresh output directory first')
    c=common(m,out/'ledger')
    if a.step=='plan':
        invoke(out,'commit plan','dosepilot.py',['plan',*c,'--inventory',str(HERE/'inventory.json'),
            '--budget','64','--nonce',m['demo_nonce'],'--output',str(out/'plan.json'),
            '--template',str(out/'template.json')],0)
        plan=load(out/'plan.json'); assert plan['treatment_wells']==64
        assert plan['plate_counts']=={'p1':32,'p2':32}
        assert len(list((out/'ledger').glob('*.json')))==1
        print('\nCommitted before accepting response values. Same sample/run cannot choose a second layout.')
        print('Physical identity preview:')
        for row in plan['measurements'][:3]:
            print(f"  {row['drug_id']:<19} {row['concentration_nM']:>4} nM | {row['plate_instance']} {row['well']}")
    elif a.step in ('predict','missing'):
        is_missing=a.step=='missing'; target=out/(a.step+'.json')
        invoke(out,a.step,'dosepilot.py',['predict',*c,'--plan',str(out/'plan.json'),
            '--measurements',str(HERE/('one_missing.json' if is_missing else 'measurements.json')),
            '--output',str(target)],0)
        result=load(target); assert result['predicted_targets']==(23 if is_missing else 24)
        if not is_missing:
            print('\nAll 24 fictional response summaries (AUC, rounded for display):')
            pred=result['predictions']
            for i in range(12):
                def cell(j):
                    return f"{pred[j]['drug_id']}: {pred[j]['normalized_log_dose_auc']: .5f}"
                print('  '+cell(i)+'       '+cell(i+12))
        else:
            absent=[x for x in result['predictions'] if x['normalized_log_dose_auc'] is None]
            assert len(absent)==1
            print('\n'+absent[0]['drug_id']+': '+absent[0]['status'])
            print('Missing positions: '+str(absent[0]['missing_positions']))
            print('All 64 row identities are retained; the unavailable value is null.')
            print('No imputation. No silent deletion. Other own-drug heads still run.')
    elif a.step=='reject':
        bad=copy.deepcopy(load(HERE/'measurements.json'))
        bad['rows'][0]['concentration_nM']='1.01'
        new_json(out/'wrong_dose.json',bad)
        invoke(out,'wrong exact concentration','dosepilot.py',['predict',*c,'--plan',str(out/'plan.json'),
            '--measurements',str(out/'wrong_dose.json'),'--output',str(out/'bad_prediction.json')],2)
        assert not (out/'bad_prediction.json').exists()
        invoke(out,'budget 63','dosepilot.py',['plan',*c,'--inventory',str(HERE/'inventory.json'),
            '--budget','63','--nonce','insufficient-budget-demo','--output',str(out/'budget63.json'),
            '--template',str(out/'budget63_template.json')],2)
        assert not (out/'budget63.json').exists()
        print('\nWrong-dose and budget-63 requests produced NO prediction/plan file.')
        print('Near a native dose is not the same as the native dose.')
    elif a.step=='recover':
        scenario=out/'separate_recovery_fixture'; scenario.mkdir();ledger=scenario/'ledger';ledger.mkdir()
        c2=common(m,ledger)
        print('Separate invented I/O-failure fixture. This is not another biological trial.')
        invoke(out,'injected output path failure','dosepilot.py',['plan',*c2,'--inventory',str(HERE/'inventory.json'),
            '--budget','64','--nonce',m['demo_nonce'],'--output',str(scenario/'absent_parent/plan.json'),
            '--template',str(scenario/'unused_template.json')],2)
        entries=list(ledger.glob('*.json')); assert len(entries)==1
        before=entries[0].read_bytes()
        invoke(out,'recover exact existing commitment','recover_plan.py',[*c2,'--sample-id',inv['sample_id'],
            '--run-id',inv['run_id'],'--output',str(scenario/'recovered')],0)
        after=entries[0].read_bytes(); recovered=load(scenario/'recovered/plan.json')
        assert before==after and load(entries[0])==recovered
        print('\nRecovered original orientation '+recovered['orientation']+'; original nonce retained.')
        print('Original commitment SHA256: '+sha(before))
        print('Ledger bytes unchanged: True. New layout selected: False.')
        new_json(scenario/'CAPTURE_ASSERTIONS.json',dict(ledger_sha256_before=sha(before),ledger_sha256_after=sha(after),
            same_plan=True, same_nonce=True, same_orientation=True, new_layout_selected=False))
    else:
        print('HISTORICAL BIOLOGICAL EVIDENCE, not results of the synthetic demo')
        print('119 organoids / 59 whole patients / 24 targets / 64 treatment wells')
        print('Five outer and three inner whole-patient development folds')
        print('')
        print('R9 paired comparison     MSE 0.0017214230')
        print('R13 retained method     MSE 0.0011448587  (33.49% lower than R9)')
        print('R18 lower point         MSE 0.0011414048  (not promoted)')
        print('')
        print('R13 improves 53/59 patients, but six drugs and six patients regress.')
        print('Gedatolisib + Palbociclib combined error worsens 20.94% versus R9.')
        print('Repeated development, NOT successful independent validation.')
        print('See the unchanged 19-page R24 technical report and source experiment records.')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('DEMONSTRATION STOPPED: '+str(exc), file=sys.stderr)
        raise
