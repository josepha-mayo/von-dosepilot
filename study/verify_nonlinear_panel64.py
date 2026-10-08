#!/usr/bin/env python3
"""Independent arithmetic replay. Does not import the candidate implementation."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json
from pathlib import Path
import numpy as np

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(out):
    r=json.loads((out/'RESULT.json').read_text())
    if digest(out/'predictions_private.npz')!=r['prediction_sha256']:raise ValueError('prediction hash')
    z=np.load(out/'predictions_private.npz',allow_pickle=False)
    y=z['y'];p=z['patients'].astype(str);folds=z['folds'];ids=np.unique(p)
    if y.shape!=(119,24) or len(ids)!=59:raise ValueError('denominator')
    for g in ids:
        if len(np.unique(folds[p==g]))!=1:raise ValueError('patient split')
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids]);maxdiff=0.;count=0
    for arm in ('original','nonlinear_panel'):
        pred=np.full((2,119,24),np.nan)
        for f in range(5):
            s=np.load(out/f'fold_{f}_{arm}_model.npz',allow_pickle=False)
            paid=np.load(out/f'fold_{f}_{arm}_paid.npz',allow_pickle=False)
            indices=paid['indices']
            if not np.array_equal(indices,np.flatnonzero(folds==f)):raise ValueError('fold query identity')
            plan=json.loads((out/f'fold_{f}_{arm}_plan.json').read_text())
            native=np.asarray(plan['selected_native_indices']);owner=np.asarray(plan['coordinate_target_indices'])
            if len(native)!=64 or len(set(native))!=64:raise ValueError('64 distinct native inputs')
            if sorted(np.bincount(owner,minlength=24))!=[2]*8+[3]*16:raise ValueError('target cardinality')
            if not np.array_equal(native,s['native']):raise ValueError('saved native identity')
            for oi,o in enumerate(('A','B')):
                plates=np.asarray(plan[f'orientation_{o}_plate_indices'])
                if np.count_nonzero(plates==0)!=32 or np.count_nonzero(plates==1)!=32 or len(set(zip(native,plates)))!=64:raise ValueError('physical budget')
                if not np.array_equal(plates,s['plate_'+o]):raise ValueError('plate identity')
                if paid[o].shape!=(len(indices),64) or not np.isfinite(paid[o]).all():raise ValueError('paid-only interface')
                q=(paid[o]-s['mean_x'])/s['scale_x'];t=s['z'];raw=q@t.T
                for j in range(24):
                    cols=np.flatnonzero(s['owner']==j)
                    dist=np.sum((q[:,cols][:,None,:]-t[:,cols][None,:,:])**2,axis=2)
                    raw+=len(cols)*np.exp(-dist/(2*len(cols)*.49))
                K=raw-(raw@s['weights'])[:,None]-s['kernel_mean'][None,:]+s['grand']
                pred[oi,indices]=s['mean_y']+q@s['beta']+K@s['coef'];count+=len(indices)*24
        if not np.isfinite(pred).all():raise ValueError('missing predictions')
        diff=float(np.max(abs(pred-z[arm])));maxdiff=max(maxdiff,diff)
        if diff>1e-12:raise ValueError('saved-model prediction mismatch')
        errors=((pred[0]-y)**2+(pred[1]-y)**2)/2
        per=np.array([errors[p==g].mean() for g in ids]);m=r['arms'][arm]['metrics']
        if abs(float(per.mean())-m['mse'])>1e-14 or abs(float(np.quantile(np.sqrt(per),.9))-m['p90'])>1e-14:raise ValueError('metric mismatch')
        if max(abs(float(per[pf==f].mean())-m['fold_mse'][f]) for f in range(5))>1e-14:raise ValueError('fold mismatch')
        print(json.dumps({'arm':arm,'mse':float(per.mean()),'p90':float(np.quantile(np.sqrt(per),.9))}),flush=True)
    if np.max(abs(z['original']-z['operating']))>1e-12:raise ValueError('reference control mismatch')
    if r['outer_mutation_maxdiff']>1e-12 or r['outer_state_maxdiff']>1e-12:raise ValueError('training exclusion sentinel failed')
    report={'status':'PASS','independent_saved_model_replay':True,'predictions_reconstructed':count,'max_prediction_difference':maxdiff,'original_64_physical_budget_checked':True,'whole_patient_metrics_checked':True,'outer_label_exclusion_sentinel':r['outer_mutation_maxdiff'],'biological_independent_validation':False,'verifier_sha256':digest(Path(__file__)),'result_sha256':digest(out/'RESULT.json')}
    with (out/'VERIFICATION.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);a=ap.parse_args();verify(a.out)
