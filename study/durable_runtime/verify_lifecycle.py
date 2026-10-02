#!/usr/bin/env python3
"""Verify the lifecycle adapter on one existing, complete author-side record.

Reads only the explicitly supplied saved input case and constructed model. No
refitting, workbook access or clinical/missingness-accuracy claim is performed.
"""
from pathlib import Path
import argparse
import copy
import datetime
import hashlib
import json
import os
import sys
import time
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import numpy as np
import lifecycle
from additive_inference import AdditiveModel


def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def verify(modeldir,sourcecase,out):
    if out.exists():raise ValueError('New output directory required')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();anchor=digest(modeldir/'CONSTRUCTION.json')
    inventory=json.loads((sourcecase/'inventory.json').read_text())
    complete_source=json.loads((sourcecase/'measurements.json').read_text())
    values={r['native_id']:r['value'] for r in complete_source['measurements']}
    assert len(values)==64
    model=AdditiveModel.load(modeldir)
    write(out/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'model_sha256':digest(modeldir/'model_private.npz'),'construction_sha256':anchor,
        'inventory_source_sha256':digest(sourcecase/'inventory.json'),
        'measurement_source_sha256':digest(sourcecase/'measurements.json'),
        'verifier_sha256':digest(Path(__file__)),'new_source_response_read':False,
        'source':'Existing author-side Lib1 TRAIN saved request; not new observations',
        'control_reservations_synthetic':True})
    case=out/'operating_case_private';case.mkdir();ledger=case/'ledger';ledger.mkdir()
    inv=case/'inventory.json';write(inv,inventory)
    commitment=case/'commitment.json';template=case/'template.json'
    args=dict(model_dir=modeldir,construction_sha256=anchor,ledger_dir=ledger,commitment=commitment)
    committed=lifecycle.execute('commit',**args,inventory=inv,template=template)
    assert committed['model_receipt']['lifecycle_policy']==lifecycle.POLICY
    complete=json.loads(template.read_text())
    for row in complete['measurements']:row['value']=values[row['native_id']]
    request={'sample_id':complete['sample_id'],'run_id':complete['run_id'],
        'orientation':complete['orientation'],'measurements':[
        dict(row,sample_id=complete['sample_id'],run_id=complete['run_id']) for row in complete['measurements']]}
    original=model.predict(request)
    blocked=copy.deepcopy(complete);blocked['measurements'][0]['value']=None
    missing=case/'one_missing.json';write(missing,blocked)
    try:lifecycle.execute('predict',**args,measurements=missing,output=case/'rejected_primary.json')
    except ValueError:pass
    else:raise AssertionError('Missing primary was produced')
    assert not (case/'rejected_primary.json').exists()
    recovery=lifecycle.execute('recover',**args,measurements=missing,output=case/'baseline_only.json',acknowledge_baseline_only=True)
    assert len(recovery['baseline_predictions'])==23 and recovery['primary_predictions']=={}
    # Direct arithmetic only for unchanged own-drug baseline heads.
    paid=np.array([values[n] for n in model.native],float)
    zz=(paid-model.a['mean_x'])/model.a['scale_x']
    base=model.a['mean_y']+zz@model.a['beta'];max_base_error=0.
    affected=model.targets[int(model.owner[0])]
    assert affected not in recovery['baseline_predictions']
    for j,target in enumerate(model.targets):
        if target!=affected:
            max_base_error=max(max_base_error,abs(base[j]-recovery['baseline_predictions'][target]))
    altered=copy.deepcopy(complete);altered['measurements'][1]['value']+=.01
    bad=case/'changed_observation_private.json';write(bad,altered)
    try:lifecycle.execute('predict',**args,measurements=bad,output=case/'should_not_exist.json')
    except ValueError as exc:assert 'OBSERVATION_CHANGED' in str(exc)
    else:raise AssertionError('Recovery history was bypassed')
    assert not (case/'should_not_exist.json').exists() and not list(ledger.glob('*.prediction.json'))
    full=case/'complete.json';write(full,complete)
    got=lifecycle.execute('predict',**args,measurements=full,output=case/'primary.json')
    diff=max(abs(got['predictions'][t]-original['predictions'][t]) for t in model.targets)
    assert diff<1e-13 and max_base_error<1e-13
    first_bytes=(case/'primary.json').read_bytes();(case/'primary.json').unlink()
    restored=lifecycle.execute('predict',**args,measurements=full,output=case/'primary.json')
    assert got==restored and (case/'primary.json').read_bytes()==first_bytes
    try:lifecycle.execute('recover',**args,measurements=missing,output=case/'late_baseline.json',acknowledge_baseline_only=True)
    except ValueError as exc:assert 'PRIMARY_RESULT_ALREADY' in str(exc)
    else:raise AssertionError('Primary frame could be downgraded')
    canonical_files=list(ledger.glob('*.json'))
    for p in canonical_files:
        json.loads(p.read_text())
        assert p.stat().st_mode&0o077==0
    result={'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'lifecycle_policy':lifecycle.POLICY,'saved_complete_records_used':1,
        'primary_incomplete_rejected':True,'explicit_baseline_outputs':23,
        'primary_outputs_with_missing_input':0,'later_complete_primary_outputs':24,
        'history_checked_automatically_by_predict':True,'changed_prior_reading_rejected':True,
        'maximum_compiled_primary_difference':float(diff),'maximum_baseline_difference':float(max_base_error),
        'export_recovered_byte_identically':True,'primary_cannot_be_downgraded':True,
        'ledger_json_files_complete_and_private':len(canonical_files),
        'runtime_implementation_and_sources_bound':committed['model_receipt'],
        'new_model_fit':False,'new_workbook_read':False,'protected_response_access':False,
        'new_independent_validation':False,'control_reservations_synthetic':True,
        'source':'One previously saved Lib1 TRAIN request','seconds':time.monotonic()-started}
    write(out/'RESULT.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('model-dir','source-case','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();verify(a.model_dir,a.source_case,a.output)
