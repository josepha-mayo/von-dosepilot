#!/usr/bin/env python3
"""Numerical reload and paired warm-inference timings of an existing artifact.

Inputs are the already reconstructed Lib1 TRAIN CSV and constructed additive
model. No refitting or source-workbook access. Timings exclude model loading,
CSV reconstruction and disk evidence writes. They include all 64 identity checks.
"""
from pathlib import Path
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,copy,datetime,hashlib,json,platform,sys,time
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path[:0]=[str(STUDY),str(STUDY/'engine'),str(STUDY/'hybrid_residual')]
from additive_inference import AdditiveModel
from compiled_inference import CompiledAdditiveModel
from durable_workflow import load_backend
from compact_train import load_prepared
from coverage_methods import acquire


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('model','curves','output'):ap.add_argument('--'+n,required=True,type=Path)
    a=ap.parse_args();out=a.output;out.mkdir(exist_ok=False)
    write(out/'TIMING_PROTOCOL.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'paired_rounds':9,'requests_per_round':64,'request_selection_seed':202610021534,
        'alternating_order':True,'warmup_calls_per_backend':12,'threads':1,
        'includes_all_identity_checks':True,'includes_io_or_model_load':False,
        'model_sha256':sha(a.model/'model_private.npz'),'construction_sha256':sha(a.model/'CONSTRUCTION.json'),
        'source_sha256':{n:sha(HERE/n) for n in ('verify_runtime.py','compiled_kernel.py','compiled_inference.py','durable_workflow.py','durable_json.py')}})
    old=AdditiveModel.load(a.model);new=CompiledAdditiveModel.load(a.model)
    D,F,_=load_prepared(a.curves,STUDY/'TRAIN_CATALOG.json')
    assert D['y'].shape==(119,24) and len(set(D['patient_ids']))==59 and set(D['library_ids'])=={'lib1'}
    requests=[];maximum=0.
    for orientation in ('A','B'):
        paid=acquire(F['x_replicates'],new.plan,orientation)
        idx=np.asarray(new.plan['selected_native_indices']);plates=new.plates[orientation];wells=F['well_ids'][:,idx,plates]
        for i in range(119):
            sample=str(D['sample_ids'][i]);run='existing_train_'+orientation
            r={'sample_id':sample,'run_id':run,'orientation':orientation,'measurements':[
                {'sample_id':sample,'run_id':run,'native_id':new.native[j],'drug_id':new.targets[int(new.owner[j])],
                 'dose_nM':str(new.doses[j]),'plate':'p'+str(int(plates[j])+1),'well_id':str(wells[i,j]),'value':float(paid[i,j])} for j in range(64)]}
            x=old.predict(r);z=new.predict(r)
            maximum=max(maximum,max(abs(x['predictions'][target]-z['predictions'][target]) for target in new.targets))
            requests.append(r)
    assert len(requests)==238 and maximum<1e-12
    missing=0
    for i in range(64):
        r=copy.deepcopy(requests[0]);r['measurements'][i]['value']=None
        try:new.predict(r)
        except ValueError:missing+=1
        else:raise AssertionError('Incomplete compiled prediction accepted')
    rng=np.random.default_rng(202610021534);order=rng.permutation(238)[:64];sample=[requests[i] for i in order]
    durations={'original':[],'compiled':[]};backends={'original':old,'compiled':new}
    with threadpool_limits(limits=1):
        for model in backends.values():
            for i in range(12):model.predict(sample[i])
        for round_ in range(9):
            names=('original','compiled') if round_%2==0 else ('compiled','original')
            for name in names:
                start=time.perf_counter()
                for request in sample:backends[name].predict(request)
                durations[name].append((time.perf_counter()-start)/len(sample))
    median={n:float(np.median(v)) for n,v in durations.items()}
    # A separately committed new frame exercises the actual model and exact
    # physical-value identity workflow. Control locations are fictional.
    wf=load_backend();case=out/'operating_case_private';case.mkdir();ledger=case/'ledger';ledger.mkdir();request=requests[0]
    inv={'schema':'dosepilot.spectral_inventory.v1','sample_id':request['sample_id'],'run_id':request['run_id'],
         'orientation':request['orientation'],'plate_instances':{'p1':'verification1','p2':'verification2'},
         'treatment_wells':[{k:r[k] for k in ('native_id','drug_id','dose_nM','plate','well_id')} for r in request['measurements']],
         'controls':[{'control_type':'vehicle','plate':'p1','well_id':'fictional_vehicle'},
                     {'control_type':'viability','plate':'p2','well_id':'fictional_viability'}]}
    write(case/'inventory.json',inv);anchor=sha(a.model/'CONSTRUCTION.json')
    commitment=wf.commit(a.model,anchor,case/'inventory.json',case/'commitment.json',case/'template.json',ledger)
    measurements=json.loads((case/'template.json').read_text());values={r['native_id']:r['value'] for r in request['measurements']}
    for row in measurements['measurements']:row['value']=values[row['native_id']]
    write(case/'measurements.json',measurements)
    result=wf.predict(a.model,anchor,case/'commitment.json',case/'measurements.json',case/'prediction.json',ledger)
    assert result['predictions']==new.predict(request)['predictions']
    before=(case/'prediction.json').read_bytes();(case/'prediction.json').unlink()
    assert wf.predict(a.model,anchor,case/'commitment.json',case/'measurements.json',case/'prediction.json',ledger)==result
    assert (case/'prediction.json').read_bytes()==before
    report={'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'actual_model_sha256':sha(a.model/'model_private.npz'),'same_fitted_model_no_refit':True,
        'single_orientation_records_checked':238,'max_prediction_difference':maximum,
        'missing_positions_rejected':missing,'predictions_are_numerically_equivalent_not_bit_identical':True,
        'paired_warm_timings_seconds_per_request':durations,'median_seconds_per_request':median,
        'median_speedup':median['original']/median['compiled'],'median_time_reduction':1-median['compiled']/median['original'],
        'includes_identity_validation':True,'includes_io_model_load_or_training':False,
        'nine_alternating_paired_rounds':True,'threads':1,'platform':platform.platform(),'python':platform.python_version(),
        'actual_committed_workflow_checked':True,'export_recovered_identically':True,
        'runtime_source_identity_bound':commitment['model_receipt']['runtime_code_sha256'],
        'control_reservations_fictional':True,'independent_biological_validation':False,'new_source_workbook_read':False,'protected_response_access':False}
    write(out/'RESULT.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
