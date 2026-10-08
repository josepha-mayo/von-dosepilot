#!/usr/bin/env python3
"""Independent replay using separately written local-regression and QC algebra."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from verify_local_response_tiers import replay as independent_base
BUDGETS=(64,120,124,128)
ARMS=('uncalibrated','asymmetric','balanced','full_common')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def quality_correction(s,Q,o,arm):
    v=np.asarray(Q,float)
    if v.ndim!=2 or v.shape[1]!=10 or not np.isfinite(v).all():raise ValueError('ten quality summaries required')
    mean=(v[:,0]+v[:,1])/2
    F=np.column_stack((mean,(v[:,0]-v[:,1])/2,mean**2,(v[:,2]+v[:,3])/2,(v[:,2]-v[:,3])/2,(v[:,4]+v[:,5])/2,(v[:,4]-v[:,5])/2))
    if o=='B':F=np.column_stack((F,(v[:,6]+v[:,7])/2,(v[:,6]-v[:,7])/2,(v[:,8]+v[:,9])/2,(v[:,8]-v[:,9])/2))
    prefix='calibration_'+o+'_';F-=s[prefix+'feature_mean']
    common=s[prefix+'common_mean']+F@s[prefix+'common_beta'];dev=s[prefix+'deviation_mean']+F@s[prefix+'rank1_beta']
    if arm=='uncalibrated':return np.zeros((len(v),24))
    strength=1/9 if o=='A' else 1/3
    if arm=='full_common':return common[:,None]+strength*dev
    if arm=='asymmetric':return strength*(common[:,None]+dev)
    return (common[:,None]+dev)/3

def verify(out):
    result=json.loads((out/'RESULT.json').read_text());z=np.load(out/'predictions_private.npz',allow_pickle=False)
    if sha(out/'predictions_private.npz')!=result['prediction_sha256']:raise ValueError('prediction hash')
    y=z['y'];p=z['patients'].astype(str);folds=z['folds'];ids=np.unique(p)
    if y.shape!=(119,24) or len(ids)!=59:raise ValueError('119 samples,59 whole patients required')
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids]);count=0;maxdiff=0.
    reconstructed={b:{a:np.full((2,119,24),np.nan) for a in ARMS} for b in BUDGETS}
    for f in range(5):
        rec=json.loads((out/f'fold_{f}_record.json').read_text())
        tr=set(rec['train_patients']);te=set(rec['test_patients'])
        if tr&te or tr!=set(p[folds!=f]) or te!=set(p[folds==f]):raise ValueError('patient exclusion')
        for b in BUDGETS:
            s=np.load(out/f'fold_{f}_budget{b}_model.npz',allow_pickle=False);paid=np.load(out/f'fold_{f}_budget{b}_paid.npz',allow_pickle=False)
            plan=json.loads((out/f'fold_{f}_budget{b}_plan.json').read_text());native=np.asarray(plan['selected_native_indices']);owner=np.asarray(plan['coordinate_target_indices']);ix=paid['indices']
            if len(native)!=b or len(set(native))!=b or not np.array_equal(native,s['native']) or not np.array_equal(owner,s['kernel_owner']):raise ValueError('exact measurement identities')
            if not np.array_equal(ix,np.flatnonzero(folds==f)) or set(s['training_patients'].astype(str))!=tr:raise ValueError('saved membership')
            if paid['Q'].shape!=(len(ix),10) or not np.isfinite(paid['Q']).all():raise ValueError('aligned measured controls')
            for oi,o in enumerate(('A','B')):
                plates=np.asarray(plan[f'orientation_{o}_plate_indices'])
                if np.count_nonzero(plates==0)!=b//2 or np.count_nonzero(plates==1)!=b//2 or len(set(zip(native,plates)))!=b or not np.array_equal(plates,s['plate_'+o]):raise ValueError('physical plate accounting')
                if paid[o].shape!=(len(ix),b) or not np.isfinite(paid[o]).all():raise ValueError('paid-value interface')
                base=independent_base(s,paid[o],rec['selected_base'][str(b)])
                for a in ARMS:
                    q=base+quality_correction(s,paid['Q'],o,a);reconstructed[b][a][oi,ix]=q;count+=len(ix)*24
    for b in BUDGETS:
        for a in ARMS:
            q=reconstructed[b][a];expected=z[f'budget{b}_{a}']
            if not np.isfinite(q).all():raise ValueError('incomplete prediction rows')
            difference=float(np.max(abs(q-expected)));maxdiff=max(maxdiff,difference)
            if difference>1e-10:raise ValueError('independent prediction reconstruction')
            e=((q[0]-y)**2+(q[1]-y)**2)/2;pt=np.array([e[p==g].mean(0) for g in ids]);per=pt.mean(1)
            m=result['tiers'][str(b)][a]['metrics']
            if abs(float(per.mean())-m['mse'])>1e-13 or abs(float(np.quantile(np.sqrt(per),.9))-m['p90'])>1e-12:raise ValueError('patient-balanced error')
            if max(abs(float(per[pf==f].mean())-m['fold_mse'][f]) for f in range(5))>1e-13:raise ValueError('fold metrics')
            achieved=per.mean()<=result['same_budget_half_error_target'] and np.quantile(np.sqrt(per),.9)<=.037419695944064885
            if bool(achieved)!=result['tiers'][str(b)][a]['accuracy_only_half_error']:raise ValueError('half-error label mismatch')
    for k in ('uncalibrated_reproduction_maxdiff','outer_label_curve_control_mutation_maxdiff','outer_state_mutation_maxdiff'):
        if result[k]>1e-12:raise ValueError('control or training-exclusion sentinel')
    report={'status':'PASS','independent_model_and_control_algebra':True,'predictions_reconstructed':count,'maximum_prediction_difference':maxdiff,'physical_costs_checked':list(BUDGETS),'standard_controls_explicitly_required':True,'whole_patient_membership_checked':True,'result_sha256':sha(out/'RESULT.json'),'verifier_sha256':sha(Path(__file__)),'independent_biological_confirmation':False}
    with (out/'VERIFICATION.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);a=ap.parse_args();verify(a.out)
