#!/usr/bin/env python3
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'): os.environ[name]='1'
import argparse,datetime,hashlib,json,platform,sys,time,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration'),str(STUDY/'hybrid_residual')]
from compact_train import load_prepared
from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features
from fast_coverage import plan_panel_fast
from methods import patient_folds
import evaluate
from bandwidth_additive import BandwidthAdditive
from joint import solve_joint,predict_joint
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
JOINT_PENALTIES=(.1,1.,10.)
MENU=[{'kind':'sequential','fraction':f,'ridge':l} for f,l in OPTIONS]+[{'kind':'joint','linear_ridge':.01,'kernel_ridge':k} for k in JOINT_PENALTIES]
EXPECTED_BASE=.0010582750420801538
EXPECTED_SCI=.001042745722096212
SEED=202610071130

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f: json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def pt(pred,y,p):
    err=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([err[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    risks=pt(pred,y,p); losses=risks.mean(1)
    pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(losses.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(losses),.9)),
            'fold_mse':[float(losses[pf==f].mean()) for f in range(5)],
            'orientation_mse':[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in np.unique(p)])) for o in (0,1)]}

def build(x,y,p,catalog,ix):
    plan=plan_panel_fast(x[ix],y[ix],p[ix],catalog)
    a,b=[acquire(x[ix],plan,o) for o in ('A','B')]
    context=fit_prediction_context(a,b,y[ix],p[ix],plan,catalog.target_ids)
    base=CoveragePredictor(context,plan,.01)
    z=(np.r_[a,b]-base.mean_x)/base.scale_x
    residual=np.r_[y[ix]-base.predict(a),y[ix]-base.predict(b)]
    ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True)
    w=np.tile(1./(len(ids)*count[inv]),2)/2
    owner=np.asarray(plan['coordinate_target_indices'],int)
    kernel=BandwidthAdditive(z,residual,w,owner,.7)
    coefs=[np.zeros_like(residual)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
    yc=np.r_[y[ix],y[ix]]-base.mean_y
    joints=[solve_joint(z,yc,w,owner,kernel.e,kernel.u,k,.01) for k in JOINT_PENALTIES]
    return plan,base,kernel,coefs,joints

def predict_all(x,ix,bundle):
    plan,base,kernel,coefs,joints=bundle
    out=np.empty((len(MENU),2,len(ix),24))
    for oi,o in enumerate(('A','B')):
        paid=acquire(x[ix],plan,o);zq=(paid-base.mean_x)/base.scale_x
        cross=kernel.centered_cross(zq);bp=base.predict(paid)
        for k,c in enumerate(coefs): out[k,oi]=bp+cross@c
        for k,s in enumerate(joints,10): out[k,oi]=base.mean_y+predict_joint(zq,cross,s)
    return out

def choose(x,y,p,catalog,outer_ix,f):
    inner,_=patient_folds(p[outer_ix],3,evaluate.SALT+f'|inner|{f}')
    oof=np.full((len(MENU),2,len(outer_ix),24),np.nan)
    for g in range(3):
        tr=outer_ix[inner!=g];va=outer_ix[inner==g]
        if set(p[tr])&set(p[va]): raise ValueError('inner patient overlap')
        pred=predict_all(x,va,build(x,y,p,catalog,tr))
        for k in range(len(MENU)):
            for o in (0,1): oof[k,o,inner==g,:]=pred[k,o]
    if not np.isfinite(oof).all(): raise ValueError('incomplete inner predictions')
    scores=[float(pt(q,y[outer_ix],p[outer_ix]).mean()) for q in oof]
    return int(np.argmin(scores)),int(np.argmin(scores[:10])),scores

def fit_outer(x,y,p,catalog,folds,f):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]): raise ValueError('outer patient overlap')
    selected,baseline,scores=choose(x,y,p,catalog,tr,f)
    bundle=build(x,y,p,catalog,tr);pred=predict_all(x,te,bundle)
    # Poison ALL unpurchased measurements separately for each alternative layout.
    max_unpaid=0.
    for oi,o in enumerate(('A','B')):
        masked=np.full_like(x,np.nan);plan=bundle[0]
        native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
        for row in te: masked[row,native,plate]=x[row,native,plate]
        paid=acquire(masked[te],plan,o);zq=(paid-bundle[1].mean_x)/bundle[1].scale_x
        cross=bundle[2].centered_cross(zq)
        if selected<10: poisoned=bundle[1].predict(paid)+cross@bundle[3][selected]
        else: poisoned=bundle[1].mean_y+predict_joint(zq,cross,bundle[4][selected-10])
        max_unpaid=max(max_unpaid,float(np.max(np.abs(poisoned-pred[selected,oi]))))
    if max_unpaid>1e-12: raise ValueError('unpaid measurements influence prediction')
    return pred[selected],pred[baseline],{'fold':f,'selected_index':selected,'selected':MENU[selected],
       'baseline_index':baseline,'inner_mse':scores,'unpurchased_poison_maxdiff':max_unpaid,
       'max_joint_stationarity':max(s['max_stationarity_error'] for s in bundle[4]),
       'treatment_wells':64,'per_plate':[32,32]}

def compare(candidate,reference,y,p,folds,targets):
    c=pt(candidate,y,p);r=pt(reference,y,p);d=c.mean(1)-r.mean(1);t=c.mean(0)-r.mean(0)
    cm,rm=metrics(candidate,y,p,folds),metrics(reference,y,p,folds)
    rng=np.random.default_rng(SEED);boot=d[rng.integers(len(d),size=(100000,len(d)))].mean(1)
    wins=int((d<-1e-15).sum());fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']))
    tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,
       'patient_losses':int((d>1e-15).sum()),'patient_ties':int((np.abs(d)<=1e-15).sum()),
       'fold_wins':fw,'p90_nonworse':tail,'target_wins':int((t<-1e-15).sum()),
       'regressing_targets':[str(targets[i]) for i in range(24) if t[i]>1e-15],
       'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
       'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}

def check_freeze(curves,catalog,scientific):
    freeze=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for key,path in {'curves':curves,'catalog':catalog,'scientific64':scientific}.items():
        if sha(path)!=freeze['inputs'][key]: raise ValueError('input hash changed: '+key)
    for rel,h in freeze['files'].items():
        if sha(ROOT/rel)!=h: raise ValueError('source hash changed: '+rel)
    return freeze

def execute(curves,catalog_path,scientific_path,out):
    freeze=check_freeze(curves,catalog_path,scientific_path)
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),
         'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'protected22_access':False})
    try:
        data,features,_=load_prepared(curves,catalog_path)
        x,y,p=features['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=catalog_from_features(features);folds,_=patient_folds(p,5,evaluate.SALT+'|outer')
        with np.load(scientific_path,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):
                raise ValueError('scientific comparator identity mismatch')
            scientific=z['candidate'].copy()
        if abs(metrics(scientific,y,p,folds)['mse']-EXPECTED_SCI)>1e-15: raise ValueError('comparator MSE mismatch')
        candidate=np.full((2,*y.shape),np.nan);baseline=candidate.copy();records=[]
        with threadpool_limits(limits=1):
            for f in range(5):
                c,b,r=fit_outer(x,y,p,catalog,folds,f)
                candidate[:,folds==f]=c;baseline[:,folds==f]=b;records.append(r)
                dump(out/f'fold_{f}_selection.json',r)
                np.savez_compressed(out/f'fold_{f}_private.npz',candidate=c,baseline=b)
                print(json.dumps({'event':'outer_complete','fold':f,'selected':r['selected']}),flush=True)
            changed=y.copy();changed[folds==0]+=np.linspace(17.,39.,24)[None,:]
            sentinel,_,sentinel_record=fit_outer(x,changed,p,catalog,folds,0)
        mutation=float(np.max(np.abs(sentinel-candidate[:,folds==0])))
        if mutation>1e-12 or sentinel_record['selected_index']!=records[0]['selected_index']:
            raise ValueError('outer-label isolation failed')
        bm=metrics(baseline,y,p,folds)
        if abs(bm['mse']-EXPECTED_BASE)>1e-12: raise ValueError('baseline reconstruction failed')
        cm=metrics(candidate,y,p,folds)
        vs_base=compare(candidate,baseline,y,p,folds,data['drug_ids'])
        vs_sci=compare(candidate,scientific,y,p,folds,data['drug_ids'])
        np.savez_compressed(out/'predictions_private.npz',candidate=candidate,baseline=baseline,scientific64=scientific,
             y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.joint_own_drug_kernel64.result.v1','status':'COMPLETE','candidate':cm,
           'baseline64':bm,'scientific64':metrics(scientific,y,p,folds),'candidate_vs_baseline':vs_base,
           'candidate_vs_scientific64':vs_sci,'selections':records,'treatment_wells':64,'per_plate':[32,32],
           'outer_label_mutation_maxdiff':mutation,'baseline_mse_difference':abs(bm['mse']-EXPECTED_BASE),
           'decision':'ELIGIBLE_FOR_INDEPENDENT_REPLAY' if vs_base['gate_pass'] and vs_sci['gate_pass'] else 'REJECT_FOR_PROMOTION',
           'prediction_sha256':sha(out/'predictions_private.npz'),'freeze_sha256':sha(HERE/'FREEZE.json'),
           'protected22_access':False,'independent_validation':False,'selection_adjusted':False,
           'automatic_promotion':False,'kaggle_entry_changed':False,'finished_utc':utc()}
        dump(out/'RESULT.json',result)
        print(json.dumps(result,indent=2),flush=True)
        return result
    except BaseException as exc:
        dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc(),'automatic_retry':False})
        raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--scientific64',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.scientific64,a.out)
