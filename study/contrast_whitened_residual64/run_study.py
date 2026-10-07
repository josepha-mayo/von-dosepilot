#!/usr/bin/env python3
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'): os.environ[name]='1'
import argparse,copy,datetime,hashlib,importlib.util,json,platform,sys,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
spec=importlib.util.spec_from_file_location('joint_incumbent_helper',STUDY/'joint_own_drug_kernel64/run_study.py')
parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
sys.path.insert(0,str(HERE))
from noise import contrast_transforms
MENU=[{'transform':t,'fraction':f,'ridge':l} for t in ('identity','diagonal_contrast','full_contrast') for f,l in parent.OPTIONS]
SEED=202610071200

def build(x,y,reps,p,catalog,ix):
    # Only the existing 64-well base and input kernel are reused. Joint candidates are discarded.
    plan,base,kernel,old_coefs,_unused=parent.build(x,y,p,catalog,ix)
    transforms=contrast_transforms(reps[ix],p[ix]);coefs=[]
    for transform in transforms:
        k=copy.copy(kernel)
        k.ur=k.u.T@(k.sw[:,None]*(k.residual@transform['white']))
        coefs.extend([np.zeros_like(k.residual)]+[k.coefficients(l,f)[0]@transform['color'] for f,l in parent.OPTIONS[1:]])
    return plan,base,kernel,coefs,transforms

def predict_all(x,ix,bundle):
    plan,base,kernel,coefs,_=bundle;out=np.empty((30,2,len(ix),24))
    for oi,o in enumerate(('A','B')):
        paid=parent.acquire(x[ix],plan,o);z=(paid-base.mean_x)/base.scale_x
        cross=kernel.centered_cross(z);bp=base.predict(paid)
        for k,c in enumerate(coefs): out[k,oi]=bp+cross@c
    return out

def fit_outer(x,y,reps,p,catalog,folds,f):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]): raise ValueError('outer overlap')
    inner,_=parent.patient_folds(p[tr],3,parent.evaluate.SALT+f'|inner|{f}')
    oof=np.full((30,2,len(tr),24),np.nan)
    for g in range(3):
        fit=tr[inner!=g];val=tr[inner==g]
        if set(p[fit])&set(p[val]): raise ValueError('inner overlap')
        pred=predict_all(x,val,build(x,y,reps,p,catalog,fit))
        for k in range(30):
            for o in (0,1):oof[k,o,inner==g,:]=pred[k,o]
    if not np.isfinite(oof).all(): raise ValueError('inner predictions incomplete')
    scores=[float(parent.pt(q,y[tr],p[tr]).mean()) for q in oof]
    chosen=int(np.argmin(scores));baseline=int(np.argmin(scores[:10]))
    bundle=build(x,y,reps,p,catalog,tr);pred=predict_all(x,te,bundle)
    poison_difference=0.
    for oi,o in enumerate(('A','B')):
        masked=np.full_like(x,np.nan);plan=bundle[0]
        native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
        for row in te:masked[row,native,plate]=x[row,native,plate]
        paid=parent.acquire(masked[te],plan,o);base=bundle[1];k=bundle[2]
        pp=base.predict(paid)+k.centered_cross((paid-base.mean_x)/base.scale_x)@bundle[3][chosen]
        poison_difference=max(poison_difference,float(np.max(np.abs(pp-pred[chosen,oi]))))
    if poison_difference>1e-12:raise ValueError('unpaid dependence')
    transform=bundle[4][chosen//10]
    rec={'fold':f,'selected_index':chosen,'selected':MENU[chosen],'baseline_index':baseline,'inner_mse':scores,
         'noise_proxy':{k:v for k,v in transform.items() if k not in ('white','color')},
         'unpaid_poison_maxdiff':poison_difference,'treatment_wells':64,'per_plate':[32,32]}
    return pred[chosen],pred[baseline],rec

def check_freeze(curves,catalog,scientific):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for k,p in {'curves':curves,'catalog':catalog,'scientific64':scientific}.items():
        if parent.sha(p)!=fr['inputs'][k]:raise ValueError('input changed '+k)
    for rel,h in fr['files'].items():
        if parent.sha(ROOT/rel)!=h:raise ValueError('source changed '+rel)
    return fr

def compare(candidate,reference,y,p,folds,targets):
    # This is the same whole-patient aggregation and prespecified gate as the prior experiment.
    old_seed=parent.SEED;parent.SEED=SEED
    try:return parent.compare(candidate,reference,y,p,folds,targets)
    finally:parent.SEED=old_seed

def execute(curves,catalog_path,scientific_path,out):
    freeze=check_freeze(curves,catalog_path,scientific_path);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    parent.dump(out/'STARTED.json',{'utc':parent.utc(),'freeze_sha256':parent.sha(HERE/'FREEZE.json'),
               'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'protected22_access':False})
    try:
        data,features,reps=parent.load_prepared(curves,catalog_path)
        x,y,p=features['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=parent.catalog_from_features(features);folds,_=parent.patient_folds(p,5,parent.evaluate.SALT+'|outer')
        with np.load(scientific_path,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            scientific=z['candidate'].copy()
        if abs(parent.metrics(scientific,y,p,folds)['mse']-parent.EXPECTED_SCI)>1e-15:raise ValueError('reference score')
        candidate=np.full((2,*y.shape),np.nan);baseline=candidate.copy();records=[]
        with threadpool_limits(limits=1):
            for f in range(5):
                c,b,r=fit_outer(x,y,reps,p,catalog,folds,f)
                candidate[:,folds==f]=c;baseline[:,folds==f]=b;records.append(r)
                parent.dump(out/f'fold_{f}_selection.json',r)
                np.savez_compressed(out/f'fold_{f}_private.npz',candidate=c,baseline=b)
                print(json.dumps({'event':'outer_complete','fold':f,'selected':r['selected']}),flush=True)
            changed=y.copy();changed[folds==0]+=np.arange(24)[None,:]+17
            changed_reps=reps.copy();changed_reps[folds==0,:,0]+=133;changed_reps[folds==0,:,1]-=71
            sentinel,_,srec=fit_outer(x,changed,changed_reps,p,catalog,folds,0)
        mutation=float(np.max(np.abs(sentinel-candidate[:,folds==0])))
        if mutation>1e-12 or srec['selected_index']!=records[0]['selected_index']:raise ValueError('outer-label isolation')
        bm=parent.metrics(baseline,y,p,folds)
        if abs(bm['mse']-parent.EXPECTED_BASE)>1e-12:raise ValueError('baseline reconstruction')
        cb=compare(candidate,baseline,y,p,folds,data['drug_ids']);cs=compare(candidate,scientific,y,p,folds,data['drug_ids'])
        np.savez_compressed(out/'predictions_private.npz',candidate=candidate,baseline=baseline,scientific64=scientific,
              y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.contrast_whitened_residual64.result.v1','status':'COMPLETE',
          'candidate':parent.metrics(candidate,y,p,folds),'baseline64':bm,'scientific64':parent.metrics(scientific,y,p,folds),
          'candidate_vs_baseline':cb,'candidate_vs_scientific64':cs,'selections':records,'treatment_wells':64,'per_plate':[32,32],
          'outer_label_and_replicate_mutation_maxdiff':mutation,'baseline_mse_difference':abs(bm['mse']-parent.EXPECTED_BASE),
          'decision':'ELIGIBLE_FOR_INDEPENDENT_REPLAY' if cb['gate_pass'] and cs['gate_pass'] else 'REJECT_FOR_PROMOTION',
          'prediction_sha256':parent.sha(out/'predictions_private.npz'),'freeze_sha256':parent.sha(HERE/'FREEZE.json'),
          'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,
          'kaggle_entry_changed':False,'finished_utc':parent.utc()}
        parent.dump(out/'RESULT.json',result);print(json.dumps(result,indent=2),flush=True)
        return result
    except BaseException as exc:
        parent.dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--scientific64',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.scientific64,a.out)
