#!/usr/bin/env python3
"""Reproduce the frozen post-hoc measurement-perturbation audit.

Requires a completed public bandwidth replay from reproduce_bandwidth.py.
Does not refit or select a model. Perturbations are synthetic software stress
tests, not estimates of biological assay noise.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np

SEEDS=(11,29,47,83,131)
SIGMAS=(.01,.05,.10)
OFFSETS=(('p1_x_0.95',0,.95),('p1_x_1.05',0,1.05),
         ('p2_x_0.95',1,.95),('p2_x_1.05',1,1.05))
EXPECTED_MSE=.0010582750420801538

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def model_predict(model,paid):
    z=(paid-model['mean_x'])/model['scale_x']
    base=model['mean_y']+z@model['beta']
    train=model['z_training'];owner=model['kernel_owner']
    bw=float(model['kernel_bandwidth_multiplier'])
    if abs(bw-.7)>1e-15:
        raise ValueError('Expected frozen bandwidth multiplier 0.7')
    raw=z@train.T
    for j in range(24):
        g=np.flatnonzero(owner==j);a,b=z[:,g],train[:,g]
        dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
        raw+=len(g)*np.exp(-dist/(2*len(g)*bw*bw))
    centered=raw-(raw@model['weights'])[:,None]-model['train_kernel_mean'][None,:]+float(model['kernel_grand'])
    out=base+centered@model['dual_coefficients']
    if not np.isfinite(out).all():
        raise ValueError('Nonfinite prediction')
    return out

def metrics(pred,y,patients):
    err=((pred[0]-y)**2+(pred[1]-y)**2)/2
    ids=np.unique(patients)
    pt=np.stack([err[patients==g].mean(0) for g in ids])
    per=pt.mean(1)
    return {'mse':float(per.mean()),'p90_rmse':float(np.quantile(np.sqrt(per),.9)),
            'target_mse':pt.mean(0)}

def load_npz(path):
    with np.load(path,allow_pickle=False) as z:
        return {k:z[k].copy() for k in z.files}

def execute(study,curves,replay,runtime_receipt,output):
    if output.exists():
        raise ValueError('Output exists; choose a fresh file')
    sys.path[:0]=[str(study),str(study/'engine'),str(study/'acceleration')]
    from compact_train import load_prepared
    from coverage_methods import acquire
    data,feat,_=load_prepared(curves,study/'TRAIN_CATALOG.json')
    x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
    saved=load_npz(replay/'predictions_private.npz')
    for key,val in [('y',y),('patients',p),('sample_ids',data['sample_ids']),('drug_ids',data['drug_ids'])]:
        if not np.array_equal(saved[key],val):
            raise ValueError('Replay identity mismatch: '+key)
    folds=saved['folds']
    baseline=np.full((2,*y.shape),np.nan)
    noise={sigma:{seed:np.full((2,*y.shape),np.nan) for seed in SEEDS} for sigma in SIGMAS}
    offsets={name:np.full((2,*y.shape),np.nan) for name,_,_ in OFFSETS}
    plan_checks=[];parity=0.;started=time.monotonic()
    for fold in range(5):
        te=np.flatnonzero(folds==fold);folder=replay/f'outer_{fold:02}'
        plan=json.loads((folder/'plan.json').read_text())
        model=load_npz(folder/'bandwidth07_model_private.npz')
        idx=np.asarray(plan['selected_native_indices'])
        if len(idx)!=64 or len(set(idx.tolist()))!=64:
            raise ValueError('Physical well count changed')
        for oi,o in enumerate(('A','B')):
            plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
            if (plate==0).sum()!=32 or (plate==1).sum()!=32:
                raise ValueError('Plate accounting changed')
            paid=acquire(x[te],plan,o)
            base_pred=model_predict(model,paid);baseline[oi,te]=base_pred
            parity=max(parity,float(np.max(np.abs(base_pred-saved['bandwidth07'][oi,te]))))
            for si,sigma in enumerate(SIGMAS):
                for seed in SEEDS:
                    rng=np.random.default_rng(seed+1000*si+100*fold+10*oi)
                    pert=paid+rng.normal(size=paid.shape)*(sigma*model['scale_x'])
                    noise[sigma][seed][oi,te]=model_predict(model,pert)
            for name,plate_id,factor in OFFSETS:
                pert=paid.copy();pert[:,plate==plate_id]*=factor
                offsets[name][oi,te]=model_predict(model,pert)
            plan_checks.append({'fold':fold,'orientation':o,'wells':64,
                                'p1':int((plate==0).sum()),'p2':int((plate==1).sum())})
    if parity>1e-12:
        raise ValueError('Frozen prediction parity failed')
    base=metrics(baseline,y,p)
    if abs(base['mse']-EXPECTED_MSE)>1e-12:
        raise ValueError('Frozen baseline MSE mismatch')
    noise_report={}
    for sigma in SIGMAS:
        runs=[]
        for seed in SEEDS:
            m=metrics(noise[sigma][seed],y,p);delta=m['target_mse']-base['target_mse'];j=int(np.argmax(delta))
            runs.append({'seed':seed,'mse':m['mse'],'p90_rmse':m['p90_rmse'],
                         'relative_mse_change':m['mse']/base['mse']-1,
                         'worst_target':str(data['drug_ids'][j]),
                         'worst_target_mse_delta':float(delta[j])})
        vals=np.array([r['mse'] for r in runs])
        noise_report[str(sigma)]={'runs':runs,'mean_mse':float(vals.mean()),
            'std_mse':float(vals.std(ddof=0)),'worst_mse':float(vals.max()),
            'mean_relative_mse_change':float(vals.mean()/base['mse']-1)}
    offset_report={}
    for name,pred in offsets.items():
        m=metrics(pred,y,p);delta=m['target_mse']-base['target_mse'];j=int(np.argmax(delta))
        offset_report[name]={'mse':m['mse'],'p90_rmse':m['p90_rmse'],
            'relative_mse_change':m['mse']/base['mse']-1,
            'worst_target':str(data['drug_ids'][j]),
            'worst_target_mse_delta':float(delta[j])}
    runtime=json.loads(runtime_receipt.read_text())
    result={'schema':'dosepilot.bandwidth_simulated_robustness.v1','status':'PASS',
      'baseline':{'mse':base['mse'],'p90_rmse':base['p90_rmse']},
      'noise':noise_report,'plate_offsets':offset_report,
      'single_missing':{'policy':'WITHHOLD_PRIMARY_NO_REPLACEMENT_WELL',
        'positions_checked_in_existing_runtime_receipt':runtime['single_missing_positions_checked'],
        'all_withheld':runtime['all_missing_cases_withheld']},
      'saved_prediction_max_difference':parity,'plan_checks':plan_checks,
      'seeds':list(SEEDS),'sigmas_z_space':list(SIGMAS),
      'new_model_fit':False,'new_model_selection':False,'same64wells':True,
      'protected_response_access':False,'independent_validation':False,
      'synthetic_perturbations_not_measured_assay_noise':True,
      'replay_result_sha256':sha(replay/'RESULT.json'),
      'runtime_receipt_sha256':sha(runtime_receipt),
      'source_sha256':sha(__file__),'seconds':time.monotonic()-started}
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--curves',type=Path,required=True)
    p.add_argument('--replay',type=Path,required=True)
    p.add_argument('--runtime-receipt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();execute(a.study.resolve(),a.curves.resolve(),a.replay.resolve(),
                             a.runtime_receipt.resolve(),a.output.resolve())
if __name__=='__main__':
    main()
