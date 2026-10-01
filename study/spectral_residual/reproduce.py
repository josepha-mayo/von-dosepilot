#!/usr/bin/env python3
"""Reproduce the spectral residual successor from the public-route TRAIN CSV.

No private metadata kit, old predictions, protected source or paid API is used.
Generated arrays and fitted model weights are author-side research artifacts.
The full two-reference promotion receipt is separate: this command reconstructs
R13 and the successor, but does not fabricate unavailable R18 patient arrays.
"""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
from pathlib import Path
import argparse,datetime,hashlib,importlib.metadata,json,sys,time,traceback
import numpy as np
from threadpoolctl import threadpool_limits
STUDY=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration')]
from compact_train import load_prepared
from methods import patient_folds
import evaluate
from coverage_methods import acquire,fit_prediction_context,CoveragePredictor
from fast_coverage import plan_panel_fast
from soft_residual import fit_soft
LOCK_SHA='8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
EXPECTED={'r13':0.001144858681382854,'spectral':0.0010701439454817465}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def patient_errors(a,y,p):
    error=((a[0]-y)**2+(a[1]-y)**2)/2
    return np.stack([error[p==g].mean(0) for g in np.unique(p)])

def run(curves,out,fit_final):
    assert sha(STUDY/'STUDY_LOCK.json')==LOCK_SHA,'Study lock changed'
    lock=json.loads((STUDY/'STUDY_LOCK.json').read_text())
    for n,h in lock['engine_files'].items():
        assert Path(n).name==n and sha(STUDY/'engine'/n)==h,n
    for n,v in lock['deps'].items():assert importlib.metadata.version(n)==v,n
    data,features,catalogue_targets=load_prepared(curves,STUDY/'TRAIN_CATALOG.json')
    from coverage_methods import catalog_from_features
    catalog=catalog_from_features(features);x=features['x_replicates'];y=data['y'];p=data['patient_ids']
    folds,_=patient_folds(p,5,evaluate.SALT+'|outer')
    assert y.shape==(119,24) and len(set(p))==59
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    sources=[Path(__file__),Path(__file__).with_name('soft_residual.py'),Path(__file__).with_name('residual_rank.py'),STUDY/'acceleration/fast_coverage.py']
    dump(out/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'curves_sha256':sha(curves),'source_sha256':{str(s.relative_to(STUDY)):sha(s) for s in sources},'options':OPTIONS,'old_predictions_input':False,'private_metadata_kit_used':False,'protected_response_access':False})
    def fit_base(indices):
        plan=plan_panel_fast(x[indices],y[indices],p[indices],catalog)
        a,b=[acquire(x[indices],plan,o) for o in ('A','B')]
        ctx=fit_prediction_context(a,b,y[indices],p[indices],plan,catalog.target_ids)
        return plan,ctx,CoveragePredictor(ctx,plan,.01)
    def model(ctx,base,index):
        frac,lam=OPTIONS[index]
        return base if index==0 else fit_soft(ctx,base,lam,frac)
    def select(indices,salt):
        infold,_=patient_folds(p[indices],3,salt)
        oof=np.full((len(OPTIONS),2,len(indices),24),np.nan)
        for k in range(3):
            tr=indices[infold!=k];va=indices[infold==k]
            assert not set(p[tr])&set(p[va])
            plan,ctx,base=fit_base(tr);models=[model(ctx,base,i) for i in range(len(OPTIONS))]
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[va],plan,o)
                for i,m in enumerate(models):oof[i,oi,infold==k]=m.predict(paid)
        assert np.isfinite(oof).all()
        scores=[float(patient_errors(a,y[indices],p[indices]).mean()) for a in oof]
        return min(range(len(scores)),key=lambda i:(scores[i],i)),scores,oof,infold
    predictions={n:np.full((2,*y.shape),np.nan) for n in ('spectral','r13')};records=[]
    with threadpool_limits(limits=1):
        for f in range(5):
            tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
            ci,scores,oof,infold=select(tr,evaluate.SALT+f'|inner|{f}')
            plan,ctx,base=fit_base(tr);m=model(ctx,base,ci);folder=out/f'outer_{f:02}';folder.mkdir()
            dump(folder/'plan.json',plan);np.savez_compressed(folder/'model_private.npz',**m.arrays())
            np.savez_compressed(folder/'inner_oof_private.npz',predictions=oof,y=y[tr],patients=p[tr],folds=infold)
            idx=np.asarray(plan['selected_native_indices'])
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[te],plan,o);predictions['spectral'][oi,te]=m.predict(paid);predictions['r13'][oi,te]=base.predict(paid)
                pl=np.asarray(plan[f'orientation_{o}_plate_indices']);wells=features['well_ids'][te][:,idx,pl]
                assert all(len(set(v))==64 for v in wells) and (pl==0).sum()==(pl==1).sum()==32
                masked=np.full_like(x[te],np.nan);masked[:,idx,pl]=paid
                np.testing.assert_array_equal(m.predict(acquire(masked,plan,o)),predictions['spectral'][oi,te])
            r={'fold':f,'selected':OPTIONS[ci],'inner_mse':scores,'physical_wells':64,'unpaid_mask_invariant':True}
            records.append(r);dump(folder/'selection.json',r);print(json.dumps(r),flush=True)
        for v in predictions.values():assert np.isfinite(v).all()
        risks={n:patient_errors(a,y,p) for n,a in predictions.items()}
        pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)]);metrics={}
        for n,v in risks.items():
            loss=v.mean(1)
            metrics[n]={'mse':float(loss.mean()),'p90_rmse':float(np.quantile(np.sqrt(loss),.9)),'fold_mse':[float(loss[pf==f].mean()) for f in range(5)],'target_mse':dict(zip(map(str,data['drug_ids']),map(float,v.mean(0))))}
        delta=risks['spectral'].mean(1)-risks['r13'].mean(1)
        matches={n:abs(metrics[n]['mse']-EXPECTED[n])<1e-12 for n in EXPECTED}
        np.savez_compressed(out/'predictions_private.npz',**data,folds=folds,**predictions)
        result={'status':'PASS' if all(matches.values()) else 'MISMATCH','metrics':metrics,'matches':matches,'patient_wins_vs_r13':int((delta<0).sum()),'patient_losses_vs_r13':int((delta>0).sum()),'selections':records,'prediction_sha256':sha(out/'predictions_private.npz'),'private_metadata_kit_used':False,'old_predictions_input':False,'protected_response_access':False,'new_independent_validation':False,'two_reference_gate':'See independently verified cycle receipt; R18 patient arrays are not inputs here.','seconds':time.monotonic()-start}
        dump(out/'RESULT.json',result)
        if not all(matches.values()):raise ValueError('Recorded experiment failed reproduction')
        if fit_final:
            ix=np.arange(len(y));ci,scores,_,_=select(ix,evaluate.SALT+'|spectral_final')
            plan,ctx,base=fit_base(ix);m=model(ctx,base,ci);dst=out/'final_model';dst.mkdir()
            dump(dst/'plan.json',plan)
            arrays=m.arrays();arrays.update(native_ids=np.asarray(plan['selected_native_ids']),drug_ids=data['drug_ids'],plate_A=np.asarray(plan['orientation_A_plate_indices']),plate_B=np.asarray(plan['orientation_B_plate_indices']))
            np.savez_compressed(dst/'model_private.npz',**arrays)
            dump(dst/'CONSTRUCTION.json',{'selected':OPTIONS[ci],'inner_mse':scores,'training_patients':59,'training_samples':119,'plan_sha256':sha(dst/'plan.json'),'model_sha256':sha(dst/'model_private.npz'),'new_validation':False,'requires_all64_values':True})
        print(json.dumps({'status':result['status'],'metrics':metrics,'wins':result['patient_wins_vs_r13']},indent=2),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--fit-final',action='store_true');args=ap.parse_args()
    if args.output.exists():ap.error('Output exists; preserve it and choose a fresh path')
    try:run(args.curves,args.output,args.fit_final)
    except BaseException as exc:
        if args.output.exists():dump(args.output/'FAILURE.json',{'error':str(exc),'traceback':traceback.format_exc(),'automatic_retry':False})
        raise
if __name__=='__main__':main()
