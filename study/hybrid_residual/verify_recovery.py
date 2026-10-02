#!/usr/bin/env python3
"""Check artificial missing-input masks on an existing fitted additive artifact.

These are software checks on existing TRAIN records, not additional patients,
new biological observations, or an accuracy estimate under real missingness.
"""
from pathlib import Path
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,copy,datetime,hashlib,json,math,sys,time
import numpy as np


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('study','model','curves','output'):ap.add_argument('--'+name,required=True,type=Path)
    args=ap.parse_args();study=args.study.resolve();out=args.output.resolve();out.mkdir(exist_ok=False)
    sys.path[:0]=[str(study),str(study/'engine'),str(study/'hybrid_residual')]
    from compact_train import load_prepared
    from coverage_methods import acquire
    from recover_baseline import compute_baseline,recover
    from additive_inference import AdditiveModel
    from additive_workflow import load_backend
    workflow=load_backend();anchor=sha(args.model/'CONSTRUCTION.json')
    receipt=workflow.model_receipt(args.model,anchor);model=AdditiveModel.load(args.model)
    write(out/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'construction_sha256':anchor,'curves_sha256':sha(args.curves),'verifier_sha256':sha(__file__),
        'recovery_code_sha256':sha(study/'hybrid_residual/recover_baseline.py'),
        'new_fit':False,'real_missingness_estimate':False})
    data,feat,_=load_prepared(args.curves,study/'TRAIN_CATALOG.json');start=time.monotonic()
    checked=scalar_comparisons=0;maximum_error=0.;first=None
    for orientation in ('A','B'):
        paid=acquire(feat['x_replicates'],model.plan,orientation)
        indices=np.asarray(model.plan['selected_native_indices']);plates=model.plates[orientation]
        wells=feat['well_ids'][:,indices,plates]
        for i in range(119):
            sample=str(data['sample_ids'][i]);run='existing_train_record_'+orientation
            inventory={'schema':'dosepilot.spectral_inventory.v1','sample_id':sample,'run_id':run,
                'orientation':orientation,'plate_instances':{'p1':'verification_p1','p2':'verification_p2'},
                'treatment_wells':[{'native_id':model.native[j],'drug_id':model.targets[int(model.owner[j])],
                'dose_nM':str(model.doses[j]),'plate':'p'+str(int(plates[j])+1),'well_id':str(wells[i,j])} for j in range(64)],
                'controls':[{'control_type':'vehicle','plate':'p1','well_id':'fictional_control1'},
                            {'control_type':'viability','plate':'p2','well_id':'fictional_control2'}]}
            commitment=workflow.build_commitment(model,receipt,inventory)
            measurements=workflow.measurement_template(commitment)
            for row,value in zip(measurements['measurements'],paid[i]):row['value']=float(value)
            if first is None:first=(inventory,copy.deepcopy(measurements))
            direct=[]
            for j in range(24):
                ix=np.flatnonzero(model.a['feature_mask'][j])
                direct.append(float(model.a['mean_y'][j])+math.fsum(
                    (float(paid[i,k])-float(model.a['mean_x'][k]))/float(model.a['scale_x'][k])*float(model.a['beta'][k,j]) for k in ix))
            for missing in range(64):
                old=measurements['measurements'][missing]['value'];measurements['measurements'][missing]['value']=None
                result=compute_baseline(model,workflow,commitment,measurements)
                affected=model.targets[int(model.owner[missing])]
                assert result['primary_predictions']=={} and result['kernel_prediction_called'] is False
                assert set(result['baseline_predictions'])==set(model.targets)-{affected}
                for j,name in enumerate(model.targets):
                    if name!=affected:
                        error=abs(result['baseline_predictions'][name]-direct[j]);maximum_error=max(maximum_error,error);scalar_comparisons+=1
                checked+=1;measurements['measurements'][missing]['value']=old
        print(json.dumps({'orientation':orientation,'mask_cases':checked}),flush=True)
    assert checked==238*64 and maximum_error<1e-12
    # One complete file/ledger workflow with two incomplete stages and a later
    # separately labelled primary completion. Control reservations are fictional.
    case=out/'actual_model_workflow_private';case.mkdir();ledger=case/'ledger';ledger.mkdir()
    inventory,measure=first;write(case/'inventory.json',inventory)
    commitment=workflow.commit(args.model,anchor,case/'inventory.json',case/'commitment.json',case/'template.json',ledger)
    assert measure['commitment_id']==commitment['commitment_id']
    other=int(np.flatnonzero(model.owner!=model.owner[0])[0]);original=copy.deepcopy(measure)
    measure['measurements'][0]['value']=None;measure['measurements'][other]['value']=None
    write(case/'stage1.json',measure)
    one=recover(args.model,anchor,case/'commitment.json',case/'stage1.json',case/'report1.json',ledger,True)
    assert len(one['baseline_predictions'])==22 and not list(ledger.glob('*.prediction.json'))
    measure['measurements'][other]['value']=original['measurements'][other]['value'];write(case/'stage2.json',measure)
    two=recover(args.model,anchor,case/'commitment.json',case/'stage2.json',case/'report2.json',ledger,True)
    assert len(two['baseline_predictions'])==23
    (case/'report2.json').unlink()
    again=recover(args.model,anchor,case/'commitment.json',case/'stage2.json',case/'report2.json',ledger,True)
    assert again==two
    complete=case/'complete.json';write(complete,original)
    primary=workflow.predict(args.model,anchor,case/'commitment.json',complete,case/'primary.json',ledger)
    assert len(primary['predictions'])==24 and primary['model_kind']==model.MODEL_KIND
    try:recover(args.model,anchor,case/'commitment.json',case/'stage2.json',case/'late.json',ledger,True)
    except ValueError as exc:assert 'PRIMARY_RESULT_ALREADY' in str(exc)
    else:raise AssertionError('Recovery replaced primary')
    result={'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'existing_sample_orientation_records':238,'artificial_single_missing_masks':checked,
        'baseline_scalar_comparisons':scalar_comparisons,'maximum_baseline_difference':maximum_error,
        'baseline_outputs_per_single_missing_case':23,'primary_outputs_per_missing_case':0,
        'ledger_stage_baseline_counts':[22,23],'later_complete_primary_outputs':24,
        'export_copy_recovered_identically':True,'primary_ledger_preserved':True,
        'construction_sha256':anchor,'model_sha256':receipt['model_sha256'],
        'runtime_source_sha256':sha(study/'hybrid_residual/recover_baseline.py'),
        'verification_source_sha256':sha(__file__),'model_fit_called':False,'protected_response_access':False,
        'raw_workbook_opened':False,'independent_biological_validation':False,
        'missingness_was_synthetic':True,'control_reservations_synthetic':True,
        'seconds':time.monotonic()-start}
    write(out/'RESULT.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
