#!/usr/bin/env python3
"""One nested fixed-budget acquisition experiment, no automatic refit/retry."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import argparse, datetime, hashlib, importlib.metadata, json, sys, time, traceback
import numpy as np

OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
EXPECTED={'additive':.001060552730112811,'s2':.0010701439454817465,'r13':.001144858681382854}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def risks(pred,y,p):
    e=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds,targets):
    pp=risks(pred,y,p);v=pp.mean(1);ids=np.unique(p);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in ids])
    return dict(mse=float(v.mean()),p90_rmse=float(np.quantile(np.sqrt(v),.9)),
        fold_mse=[float(v[pf==f].mean()) for f in range(5)],
        target_mse=dict(zip(map(str,targets),map(float,pp.mean(0)))),
        orientation_mse=[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in ids])) for o in (0,1)])

def execute(a):
    root=a.study.resolve();here=Path(__file__).resolve().parent
    if a.output.exists():raise ValueError('Output already exists')
    freeze=json.loads(a.freeze.read_text())
    for name,h in freeze['source'].items():
        if sha(here/name)!=h:raise ValueError('Frozen source changed: '+name)
    for name,h in freeze['parent_source'].items():
        if sha(root/name)!=h:raise ValueError('Parent source changed: '+name)
    locked=json.loads((root/'STUDY_LOCK.json').read_text())
    for name,h in locked['engine_files'].items():
        if sha(root/'engine'/name)!=h:raise ValueError('Locked engine changed:'+name)
    for name,v in locked['deps'].items():
        if importlib.metadata.version(name)!=v:raise ValueError('Pinned dependency changed:'+name)
    if a.cache and sha(a.cache)!=freeze['cache_sha256']:raise ValueError('Input cache changed')
    if sha(a.r18)!=freeze['r18_sha256']:raise ValueError('R18 changed')
    sys.path[:0]=[str(root),str(root/'engine'),str(root/'acceleration'),str(root/'hybrid_residual'),str(here)]
    from methods import patient_folds
    import evaluate
    from coverage_methods import CoverageCatalog,CoveragePredictor,acquire,fit_prediction_context,catalog_from_features
    from fast_coverage import plan_panel_fast
    from additive_kernel import AdditiveKernel
    from kernel_spectral import KernelSpectral
    from global_acquisition import optimize
    if a.cache:
        with np.load(a.cache,allow_pickle=False) as z:d={k:z[k].copy() for k in z.files}
        x,y,p,wells=d['x'],d['y'],d['patient_ids'].astype(str),d['well_ids']
        catalog=CoverageCatalog(d['native_ids'],d['drug_ids'],d['native_target_indices'],tuple(d['concentrations']))
        inputs_role='verified_historical_private_train_kit_cache'
    else:
        from compact_train import load_prepared
        d,feat,_=load_prepared(a.curves,root/'TRAIN_CATALOG.json')
        x,y,p,wells=feat['x_replicates'],d['y'],d['patient_ids'].astype(str),feat['well_ids']
        catalog=catalog_from_features(feat);inputs_role='public_derived_train_csv'
    if y.shape!=(119,24) or len(set(p))!=59 or set(d['library_ids'])!={'lib1'}:raise ValueError('Task changed')
    a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    write(a.output/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'freeze':sha(a.freeze),'inputs_role':inputs_role,'protected_response_access':False})
    folds,_=patient_folds(p,5,evaluate.SALT+'|outer')
    names=('additive','forced_sweep','selected_plan','s2','r13');pred={n:np.full((2,*y.shape),np.nan) for n in names}
    records=[]
    def build(ix):
        old=plan_panel_fast(x[ix],y[ix],p[ix],catalog)
        new=optimize(x[ix],y[ix],p[ix],catalog,old)
        plans=[old,new];bundles=[]
        ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inv]),2)/2
        for plan in plans:
            pa,pb=[acquire(x[ix],plan,o) for o in ('A','B')]
            ctx=fit_prediction_context(pa,pb,y[ix],p[ix],plan,catalog.target_ids);base=CoveragePredictor(ctx,plan,.01)
            z=(np.r_[pa,pb]-base.mean_x)/base.scale_x;res=np.r_[y[ix]-base.predict(pa),y[ix]-base.predict(pb)]
            kernel=AdditiveKernel(z,res,w,np.asarray(plan['coordinate_target_indices']))
            coefs=[np.zeros_like(res)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
            bundles.append((base,kernel,coefs))
        base,k,_=bundles[0];s2=KernelSpectral(k.z,k.residual,k.w,False)
        s2co=[np.zeros_like(k.residual)]+[s2.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
        return plans,bundles,(s2,s2co)
    def evaluate_options(ix,plans,bundles,s2bundle):
        result=np.empty((2,10,2,len(ix),24));s2result=np.empty((10,2,len(ix),24))
        for pi,(plan,(base,k,coefs)) in enumerate(zip(plans,bundles)):
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[ix],plan,o);z=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
                cross=k.centered_cross(z)
                for ci,c in enumerate(coefs):result[pi,ci,oi]=bp+cross@c
                if pi==0:
                    kk,cc=s2bundle;scross=kk.centered_cross(z)
                    for ci,c in enumerate(cc):s2result[ci,oi]=bp+scross@c
        return result,s2result
    for f in range(5):
        tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f);inner,_=patient_folds(p[tr],3,evaluate.SALT+f'|inner|{f}')
        io=np.full((2,10,2,len(tr),24),np.nan);sio=np.full((10,2,len(tr),24),np.nan)
        folder=a.output/f'outer_{f:02}';folder.mkdir()
        for inf in range(3):
            fit=tr[inner!=inf];va=tr[inner==inf]
            if set(p[fit])&set(p[va]):raise ValueError('Patient leakage')
            pl,bu,sb=build(fit);q,s=evaluate_options(va,pl,bu,sb)
            io[:,:,:,inner==inf]=q;sio[:,:,inner==inf]=s
            sub=folder/f'inner_{inf:02}';sub.mkdir();write(sub/'fitting_only_sweep_plan.json',pl[1])
        if not np.isfinite(io).all() or not np.isfinite(sio).all():raise ValueError('Incomplete inner predictions')
        scores=np.array([[risks(io[pi,ci],y[tr],p[tr]).mean() for ci in range(10)] for pi in range(2)])
        sscore=np.array([risks(q,y[tr],p[tr]).mean() for q in sio])
        oldc=int(np.argmin(scores[0]));newc=int(np.argmin(scores[1]));combined=np.unravel_index(int(np.argmin(scores)),scores.shape);sci=int(np.argmin(sscore))
        choices={'additive':(0,oldc),'forced_sweep':(1,newc),'selected_plan':combined}
        pl,bu,sb=build(tr);q,s=evaluate_options(te,pl,bu,sb)
        for name,(pi,ci) in choices.items():pred[name][:,te]=q[pi,ci]
        pred['s2'][:,te]=s[sci];pred['r13'][:,te]=q[0,0]
        np.savez_compressed(folder/'inner_predictions_private.npz',all_plans=io,s2=sio,y=y[tr],patients=p[tr],inner_folds=inner)
        for pi,(plan,(base,k,coefs)) in enumerate(zip(pl,bu)):
            write(folder/f'plan_{pi}.json',plan)
            # Save every selected option once. No weights or raw inputs are public.
            for ci in sorted({c for pidx,c in choices.values() if pidx==pi}):
                np.savez_compressed(folder/f'plan{pi}_model{ci}_private.npz',**base.arrays(),**k.arrays(coefs[ci]))
            for oi,o in enumerate(('A','B')):
                paid=acquire(x[te],plan,o);native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
                physical=wells[te][:,native,plate]
                if (plate==0).sum()!=32 or (plate==1).sum()!=32 or not all(len(set(v))==64 for v in physical):raise ValueError('Physical budget changed')
                masked=np.full_like(x[te],np.nan);masked[:,native,plate]=paid
                np.testing.assert_array_equal(acquire(masked,plan,o),paid)
        rec={'fold':f,'selection':{n:[int(pi),int(ci)] for n,(pi,ci) in choices.items()},'s2_choice':sci,'scores':scores.tolist(),'s2_scores':sscore.tolist(),'changed_targets':pl[1]['changed_targets'],'proxy_before':pl[1]['proxy_initial'],'proxy_after':pl[1]['proxy_final'],'distinct_physical_wells':64,'per_plate':32,'inner_acquisition_fit_only':True}
        records.append(rec);write(folder/'selection.json',rec);print(json.dumps(rec),flush=True)
    if not all(np.isfinite(q).all() for q in pred.values()):raise ValueError('Incomplete outer predictions')
    np.savez_compressed(a.output/'predictions_private.npz',**pred,y=y,patients=p,folds=folds,sample_ids=d['sample_ids'],drug_ids=d['drug_ids'])
    write(a.output/'PREDICTIONS_COMMITTED.json',{'sha256':sha(a.output/'predictions_private.npz'),'r18_opened':False})
    ms={n:metrics(q,y,p,folds,d['drug_ids']) for n,q in pred.items()}
    for n,value in EXPECTED.items():
        if abs(ms[n]['mse']-value)>1e-12:raise ValueError('Historical control did not reproduce: '+n)
    with np.load(a.r18,allow_pickle=False) as z:
        print('R18_KEYS',z.files,flush=True)
        for key,value in [('y',y),('sample_ids',d['sample_ids']),('patient_ids',p),('drug_ids',d['drug_ids']),('folds',folds)]:
            if not np.array_equal(z[key],value):raise ValueError('R18 identity mismatch:'+key)
        # Historical R18 has the same alternative prediction convention.
        r18=np.stack([z['candidate_A'],z['candidate_B']])
    ms['r18']=metrics(r18,y,p,folds,d['drug_ids'])
    if abs(ms['r18']['mse']-.0011414048112341991)>1e-12:raise ValueError('R18 MSE mismatch')
    per={n:risks(q,y,p).mean(1) for n,q in {**pred,'r18':r18}.items()}
    pairs={};decision={}
    for name in ('forced_sweep','selected_plan'):
        pairs[name]={}
        for ref in ('additive','s2','r13','r18'):
            c,r=ms[name],ms[ref];delta=per[name]-per[ref];original=ref in ('r13','r18')
            wins=int((delta<0).sum());fw=sum(x<z for x,z in zip(c['fold_mse'],r['fold_mse']))
            gate={'mse':c['mse']<=.95*r['mse'] if original else c['mse']<r['mse'],'patients':wins>=(40 if original else 30),'folds':fw>=(4 if original else 3),'p90':c['p90_rmse']<=r['p90_rmse']}
            if original:gate['each_orientation_below_reference_expected']=max(c['orientation_mse'])<r['mse']
            rng=np.random.default_rng(20261002);boot=delta[rng.integers(0,59,(10000,59))].mean(1)
            pairs[name][ref]={'relative_gain':1-c['mse']/r['mse'],'patient_wins':wins,'patient_losses':int((delta>0).sum()),'ties':int((delta==0).sum()),'fold_wins':fw,'gate':gate,'pass':all(gate.values()),'descriptive_delta_ci95':np.quantile(boot,[.025,.975]).tolist()}
        decision[name]='ELIGIBLE' if all(v['pass'] for v in pairs[name].values()) else 'REJECT_RETAIN_ADDITIVE'
    result={'status':'COMPLETE','metrics':ms,'comparisons':pairs,'decisions':decision,'selections':records,'prediction_sha256':sha(a.output/'predictions_private.npz'),'elapsed_seconds':time.monotonic()-start,'input_role':inputs_role,'new_independent_validation':False,'protected_response_access':False,'publication_or_submission_changed':False}
    write(a.output/'RESULT.json',result);print(json.dumps({'status':result['status'],'mse':{n:v['mse'] for n,v in ms.items()},'comparisons':pairs,'decisions':decision},indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',required=True,type=Path);p.add_argument('--freeze',required=True,type=Path);p.add_argument('--r18',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--cache',type=Path);g.add_argument('--curves',type=Path)
    a=p.parse_args()
    if a.output.exists():p.error('Output exists; refuse duplicate attempt')
    try:execute(a)
    except BaseException as exc:
        if a.output.exists():write(a.output/'FAILURE.json',{'error':str(exc),'traceback':traceback.format_exc(),'no_automatic_retry':True})
        raise
if __name__=='__main__':main()
