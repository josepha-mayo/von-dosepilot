#!/usr/bin/env python3
"""Reproduce the fixed hybrid-kernel development study from the public TRAIN CSV.

No historical prediction or private metadata kit is required. Generated patient
arrays and kernel parameters containing fitting inputs are PRIVATE artifacts.
The historical R18 comparison remains in the audited original study receipt.
"""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from pathlib import Path
import argparse,datetime,hashlib,importlib.metadata,json,sys,time,traceback
import numpy as np
from kernel_spectral import KernelSpectral
STUDY=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration')]
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
EXPECTED={'hybrid':.001067047226436295,'s2':.0010701439454817465,'target_rms':.0010696206908889856,'r13':.001144858681382854}
LOCK='8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write_new(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def risks(pred,y,p):
    error=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([error[p==g].mean(0) for g in np.unique(p)])

def measurements_summary(pred,y,p,folds,targets):
    pt=risks(pred,y,p);per_patient=pt.mean(1)
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return dict(mse=float(per_patient.mean()),p90_rmse=float(np.quantile(np.sqrt(per_patient),.9)),
                fold_mse=[float(per_patient[pf==f].mean()) for f in range(5)],
                target_mse=dict(zip(map(str,targets),map(float,pt.mean(0)))),
                orientation_mse=[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in np.unique(p)])) for o in (0,1)])

def execute(curves,out,fit_final):
    from threadpoolctl import threadpool_limits
    from compact_train import load_prepared
    from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features
    from fast_coverage import plan_panel_fast
    from methods import patient_folds
    import evaluate
    if out.exists():raise ValueError('Output exists; preserve it and choose a new directory')
    if sha(STUDY/'STUDY_LOCK.json')!=LOCK:raise ValueError('Historical study lock changed')
    lock=json.loads((STUDY/'STUDY_LOCK.json').read_text())
    for n,h in lock['engine_files'].items():
        if Path(n).name!=n or sha(STUDY/'engine'/n)!=h:raise ValueError('Historical scientific engine changed: '+n)
    for n,v in lock['deps'].items():
        if importlib.metadata.version(n)!=v:raise ValueError('Pinned dependency required: '+n+'=='+v)
    data,feat,_=load_prepared(curves,STUDY/'TRAIN_CATALOG.json')
    x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str);catalog=catalog_from_features(feat)
    if y.shape!=(119,24) or len(set(p))!=59 or set(data['library_ids'])!={'lib1'}:raise ValueError('Historical task changed')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    write_new(out/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'curves_sha256':sha(curves),'code_sha256':{n:sha(Path(__file__).with_name(n)) for n in ['reproduce.py','kernel_spectral.py']},'options':OPTIONS,'old_prediction_input':False,'private_metadata_kit_used':False,'protected_response_access':False})
    outer,_=patient_folds(p,5,evaluate.SALT+'|outer')
    families=['hybrid','s2','target_rms'];preds={n:np.full((2,*y.shape),np.nan) for n in [*families,'r13']};records=[]
    def build(ix):
        plan=plan_panel_fast(x[ix],y[ix],p[ix],catalog);pa,pb=[acquire(x[ix],plan,o) for o in ('A','B')]
        context=fit_prediction_context(pa,pb,y[ix],p[ix],plan,catalog.target_ids);base=CoveragePredictor(context,plan,.01)
        z=(np.r_[pa,pb]-base.mean_x)/base.scale_x;res=np.r_[y[ix]-base.predict(pa),y[ix]-base.predict(pb)]
        ids,inverse,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inverse]),2)/2
        rms=np.maximum(np.sqrt(w@(res*res)),.005);models={}
        for n in families:
            scale=rms if n=='target_rms' else np.ones(24)
            model=KernelSpectral(z,res/scale,w,n=='hybrid')
            coefficients=[np.zeros((len(z),24))]+[model.coefficients(l,f)[0]*scale for f,l in OPTIONS[1:]]
            models[n]=(model,coefficients)
        return plan,base,models
    def choose(indices,salt):
        folds,_=patient_folds(p[indices],3,salt);io={n:np.full((10,2,len(indices),24),np.nan) for n in families}
        for k in range(3):
            tr=indices[folds!=k];va=indices[folds==k]
            if set(p[tr])&set(p[va]):raise ValueError('Patient leakage')
            plan,base,models=build(tr)
            for oidx,o in enumerate(('A','B')):
                paid=acquire(x[va],plan,o);z=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
                for n,(m,coefs) in models.items():
                    kk=m.centered_cross(z)
                    for j,c in enumerate(coefs):io[n][j,oidx,folds==k]=bp+kk@c
        scores={n:[float(risks(a,y[indices],p[indices]).mean()) for a in io[n]] for n in families}
        chosen={n:min(range(10),key=lambda j:(s[j],j)) for n,s in scores.items()}
        return chosen,scores,io,folds
    with threadpool_limits(limits=1):
        for f in range(5):
            tr=np.flatnonzero(outer!=f);te=np.flatnonzero(outer==f)
            chosen,scores,io,inner=choose(tr,evaluate.SALT+f'|inner|{f}');plan,base,models=build(tr)
            d=out/f'outer_{f:02}';d.mkdir();write_new(d/'plan.json',plan)
            np.savez_compressed(d/'inner_predictions_private.npz',**io,y=y[tr],patients=p[tr],folds=inner)
            for n,(m,coefs) in models.items():np.savez_compressed(d/(n+'_model_private.npz'),**base.arrays(),**m.arrays(coefs[chosen[n]]))
            indices=np.array(plan['selected_native_indices'])
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[te],plan,o);z=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid);preds['r13'][oi,te]=bp
                pl=np.array(plan[f'orientation_{o}_plate_indices']);well_ids=feat['well_ids'][te][:,indices,pl]
                if not all(len(set(w))==64 for w in well_ids) or (pl==0).sum()!=32 or (pl==1).sum()!=32:raise ValueError('Physical budget changed')
                masked=np.full_like(x[te],np.nan);masked[:,indices,pl]=paid
                np.testing.assert_array_equal(acquire(masked,plan,o),paid)
                for n,(m,coefs) in models.items():preds[n][oi,te]=bp+m.predict(z,coefs[chosen[n]])
            rec={'fold':f,'selected':{n:OPTIONS[j] for n,j in chosen.items()},'inner_scores':scores,'wells':64,'per_plate':32}
            records.append(rec);write_new(d/'selection.json',rec);print(json.dumps({'fold':f,'selected':rec['selected']}),flush=True)
        if not all(np.isfinite(v).all() for v in preds.values()):raise ValueError('Incomplete held-patient prediction')
        np.savez_compressed(out/'predictions_private.npz',**preds,y=y,patients=p,folds=outer,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        ms={n:measurements_summary(v,y,p,outer,data['drug_ids']) for n,v in preds.items()};cp=risks(preds['hybrid'],y,p);pairs={}
        for n in ['s2','target_rms','r13']:
            rp=risks(preds[n],y,p);delta=cp.mean(1)-rp.mean(1)
            pairs[n]={'patient_wins':int((delta<0).sum()),'patient_losses':int((delta>0).sum()),'fold_wins':sum(a<b for a,b in zip(ms['hybrid']['fold_mse'],ms[n]['fold_mse'])),'relative_gain':1-ms['hybrid']['mse']/ms[n]['mse']}
        matches={n:abs(ms[n]['mse']-v)<=1e-12 for n,v in EXPECTED.items()}
        result={'status':'PASS' if all(matches.values()) else 'MISMATCH','metrics':ms,'comparisons':pairs,'expected_matches':matches,'selections':records,'source_route':'public_derived_csv','old_prediction_input':False,'private_metadata_kit_used':False,'protected_response_access':False,'independent_validation':False,'r18_gate_source':'Separately verified historical comparison, not an input to this public replay','prediction_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-started}
        write_new(out/'RESULT.json',result)
        if not all(matches.values()):raise ValueError('Fixed result did not reproduce')
        if fit_final:
            allrows=np.arange(len(y));chosen,scores,_,_=choose(allrows,evaluate.SALT+'|hybrid_kernel_final')
            plan,base,models=build(allrows);m,coefs=models['hybrid'];option=OPTIONS[chosen['hybrid']];d=out/'final_model';d.mkdir()
            arrays=dict(base.arrays(),**m.arrays(coefs[chosen['hybrid']]),native_ids=np.asarray(plan['selected_native_ids']),drug_ids=data['drug_ids'],plate_A=np.asarray(plan['orientation_A_plate_indices']),plate_B=np.asarray(plan['orientation_B_plate_indices']))
            np.savez_compressed(d/'model_private.npz',**arrays);write_new(d/'plan.json',plan)
            write_new(d/'CONSTRUCTION.json',{'model_kind':'dosepilot.hybrid_kernel.v1','selected':option,'inner_mse':scores['hybrid'],'training_samples':119,'training_patients':59,'plan_sha256':sha(d/'plan.json'),'model_sha256':sha(d/'model_private.npz'),'private_training_features_in_model':True,'new_validation':False,'requires_all64_values':True})
        print(json.dumps({'status':result['status'],'mse':{n:m['mse'] for n,m in ms.items()},'comparisons':pairs},indent=2))
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--fit-final',action='store_true');a=ap.parse_args()
    if a.output.exists():ap.error('Output exists; choose a new path')
    try:execute(a.curves,a.output,a.fit_final)
    except BaseException as exc:
        if a.output.exists():write_new(a.output/'FAILURE.json',{'error':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
if __name__=='__main__':main()
