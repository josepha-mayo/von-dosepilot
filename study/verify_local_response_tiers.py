#!/usr/bin/env python3
"""Independent model replay using augmented weighted normal equations.
Does not import the candidate model, runner, or local regression implementation.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json
from pathlib import Path
import numpy as np
CONFIGS=(('original',0.,0.),('own',.7,.5),('own',.7,1.),('own',1.4,1.),('response',.7,.5),('response',.7,1.),('response',1.4,1.))
NAMES=('original','own07_half','own07_full','own14_full','response07_half','response07_full','response14_full','nested_primary')
BUDGETS=(64,120,124,128)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replay(s,paid,index):
    base_id,spectral=divmod(int(index),10);kind,h,rho=CONFIGS[base_id]
    z=(paid-s['mean_x'])/s['scale_x'];t=s['kernel_z'];base=s['mean_y']+z@s['beta']
    K=z@t.T
    for j in range(24):
        cols=np.flatnonzero(s['kernel_owner']==j)
        distance=np.sum((z[:,None,cols]-t[None,:,cols])**2,axis=2)
        K+=len(cols)*np.exp(-distance/(2*len(cols)*.49))
    K=K-(K@s['kernel_weights'])[:,None]-s['kernel_mean'][None,:]+s['kernel_grand']
    correction=K@s['all_coefs'][spectral]
    if kind=='original':return base+correction
    local=np.empty_like(base);prior=s['kernel_weights']
    if kind=='response':
        q=(base-s['response_mean'])/s['response_scale'];distance=np.mean((q[:,None,:]-s['response_training'][None,:,:])**2,axis=2)
        logk=-distance/(2*h*h);logk-=logk.max(1,keepdims=True);w=np.exp(logk)*prior[None,:];w/=w.sum(1,keepdims=True);shared_weights=(1-rho)*prior[None,:]+rho*w
    for j in range(24):
        cols=np.flatnonzero(s['kernel_owner']==j);q=z[:,cols];fit=t[:,cols]
        if kind=='own':
            distance=np.mean((q[:,None,:]-fit[None,:,:])**2,axis=2)
            logk=-distance/(2*h*h);logk-=logk.max(1,keepdims=True);w=np.exp(logk)*prior[None,:];w/=w.sum(1,keepdims=True);weights=(1-rho)*prior[None,:]+rho*w
        else:weights=shared_weights
        X=np.c_[np.ones(len(fit)),fit];penalty=np.diag(np.r_[0.,np.repeat(.01,len(cols))])
        gram=np.einsum('mn,ni,nj->mij',weights,X,X,optimize=True)+penalty[None,:,:]
        rhs=np.einsum('mn,ni,n->mi',weights,X,s['train_y'][:,j],optimize=True)
        coeff=np.linalg.solve(gram,rhs[...,None])[...,0]
        local[:,j]=np.sum(np.c_[np.ones(len(q)),q]*coeff,axis=1)
    return local+correction

def metrics(q,y,p,folds):
    error=((q[0]-y)**2+(q[1]-y)**2)/2;ids=np.unique(p);per=np.array([error[p==g].mean() for g in ids]);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids])
    return {'mse':float(per.mean()),'p90':float(np.quantile(np.sqrt(per),.9)),'fold_mse':[float(per[pf==f].mean()) for f in range(5)]}

def verify(out):
    result=json.loads((out/'RESULT.json').read_text());z=np.load(out/'predictions_private.npz',allow_pickle=False)
    if sha(out/'predictions_private.npz')!=result['prediction_sha256']:raise ValueError('prediction hash')
    y=z['y'];p=z['patients'].astype(str);folds=z['folds'];ids=np.unique(p)
    if y.shape!=(119,24) or len(ids)!=59:raise ValueError('population count')
    for g in ids:
        if len(np.unique(folds[p==g]))!=1:raise ValueError('patient fold contamination')
    rebuilt={b:{a:np.full((2,119,24),np.nan) for a in NAMES} for b in BUDGETS};maxdiff=0.;count=0
    for f in range(5):
        rec=json.loads((out/f'fold_{f}_record.json').read_text())
        tr=set(rec['train_patients']);te=set(rec['test_patients'])
        if tr&te or te!=set(p[folds==f]) or tr!=set(p[folds!=f]):raise ValueError('training membership')
        for b in BUDGETS:
            s=np.load(out/f'fold_{f}_budget{b}_model.npz',allow_pickle=False);paid=np.load(out/f'fold_{f}_budget{b}_paid.npz',allow_pickle=False)
            plan=json.loads((out/f'fold_{f}_budget{b}_plan.json').read_text());indices=paid['indices'];native=np.asarray(plan['selected_native_indices']);owner=np.asarray(plan['coordinate_target_indices'])
            if not np.array_equal(indices,np.flatnonzero(folds==f)):raise ValueError('query membership')
            if set(s['training_patients'].astype(str))!=tr or len(native)!=b or len(set(native))!=b:raise ValueError('model training or cost mismatch')
            if not np.array_equal(native,s['native']) or not np.array_equal(owner,s['kernel_owner']):raise ValueError('measurement identity mismatch')
            counts=np.bincount(owner,minlength=24)
            if counts.min()<2 or counts.max()>6:raise ValueError('target coverage')
            for o in ('A','B'):
                plates=np.asarray(plan[f'orientation_{o}_plate_indices'])
                if not np.array_equal(plates,s['plate_'+o]) or np.count_nonzero(plates==0)!=b//2 or np.count_nonzero(plates==1)!=b//2 or len(set(zip(native,plates)))!=b:raise ValueError('physical plates')
                if paid[o].shape!=(len(indices),b) or not np.isfinite(paid[o]).all():raise ValueError('complete paid inputs')
            for a in NAMES:
                index=rec['selected'][str(b)][a]
                for oi,o in enumerate(('A','B')):
                    q=replay(s,paid[o],index);rebuilt[b][a][oi,indices]=q;count+=len(indices)*24
    for b in BUDGETS:
        for a in NAMES:
            pred=rebuilt[b][a]
            if not np.isfinite(pred).all():raise ValueError('missing final predictions')
            d=float(np.max(abs(pred-z[f'budget{b}_{a}'])));maxdiff=max(maxdiff,d)
            if d>1e-10:raise ValueError('independent weighted regression prediction mismatch')
            m=metrics(pred,y,p,folds);expected=result['tiers'][str(b)][a]['metrics']
            if abs(m['mse']-expected['mse'])>1e-13 or abs(m['p90']-expected['p90'])>1e-12 or max(abs(u-v) for u,v in zip(m['fold_mse'],expected['fold_mse']))>1e-13:raise ValueError('metrics')
    integrated=z['scientific64']+rebuilt[64]['nested_primary']-rebuilt[64]['original']
    if np.max(abs(integrated-z['integration64']))>1e-10:raise ValueError('integration arithmetic')
    im=metrics(integrated,y,p,folds)
    if abs(im['mse']-result['integration64']['metrics']['mse'])>1e-13:raise ValueError('integration metric')
    for key in ('control64_maxdiff','control128_maxdiff','outer_label_mutation_maxdiff','outer_state_mutation_maxdiff'):
        if result[key]>1e-12:raise ValueError('control/sentinel failed')
    receipt={'status':'PASS','independent_augmented_regression_replay':True,'predictions_reconstructed':count,'maximum_prediction_difference':maxdiff,'cost_tiers_checked':list(BUDGETS),'whole_patient_membership_checked':True,'outer_label_exclusion_sentinel':result['outer_label_mutation_maxdiff'],'result_sha256':sha(out/'RESULT.json'),'verifier_sha256':sha(Path(__file__)),'independent_biological_confirmation':False}
    with (out/'VERIFICATION.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(receipt),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);a=ap.parse_args();verify(a.out)
