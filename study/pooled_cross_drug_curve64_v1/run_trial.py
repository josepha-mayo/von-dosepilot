#!/usr/bin/env python3
"""One-shot 64-well pooled cross-drug trial. Prepared; biological run is pending.

Requires the existing authorized D: repository and pinned Lib1 TRAIN CSV. The
freeze and evaluation phases are separate. No network, secrets, workbook or
Protected22 access. A fresh output directory is required; failures are retained.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
import argparse,datetime,hashlib,importlib,json,platform,sys,traceback
from pathlib import Path
import numpy as np
from pooled_curve64 import PooledCurveResidual,encode_paid,assert_disjoint,ALPHAS
PACKAGE=Path(__file__).resolve().parent
INPUT_HASHES={'curves':'b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94',
 'catalog':'84eae3976307448ac696852d39d1b2376cce479d8af5e386ce04097020deff5e',
 'reference':'ab7bd69e97fc0295a9f4066be0396d82d628bba5b69302bb9670f31561e6df12'}
DEPENDENCIES={
 'study/compact_train.py':'50a9140441680b9a889a165bbd6921d2ed42f65e7fe43efd18078db05340b34e',
 'study/engine/coverage_methods.py':'2c5cb8c5e1ed67f7d68677020102d70f60a42e12a1316d3e8a515fc28a9d63f8',
 'study/engine/sparse_methods.py':'511ea1665a7f245cd3a2923fd8a6be6f5c2e45ba901da1620f7298a4125ec64c',
 'study/engine/methods.py':'6fc6909ab92057aa8715383f0001f4bcaa14df85d0e897ed8900f88efb1aaf5f',
 'study/engine/evaluate.py':'24593a7d8608fd3ce98c367e1760af596b3b33554c1ef7a3f8ac645b046b700b',
 'study/acceleration/fast_coverage.py':'bf99cf292ed0f398043872239a7cd2eff8995f3d4aea4f98a62955a89bea724e',
 'study/hybrid_residual/bandwidth_additive.py':'30723fbc8f6843c200891e14e5fb254e707298fa5514b668c4f005a4562edb30',
 'study/hybrid_residual/additive_kernel.py':'683004e39904c6648c0283395697c914903e78db60a7e98f90362dc8b2c49b1a',
 'study/hybrid_residual/kernel_spectral.py':'869bfc27cb72afe644f2e85ee5d255004e2afcf8b765b4cc56d8cd7d8927131e'}
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
MENU=[{'kind':'incumbent','fraction':f,'ridge':l} for f,l in OPTIONS]+[{'kind':'pooled_curve','ridge':a} for a in ALPHAS]
BASE_MSE=.0010582750420801538;REFERENCE_MSE=.001042745722096212;REFERENCE_P90=.037419695944064885
TARGET=REFERENCE_MSE/2;BOOTSTRAP_SEED=202610071328

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,x):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def package_files():
    return ['run_trial.py','pooled_curve64.py','PROTOCOL.md','tests/test_pooled_curve64.py','tests/test_trial_guards.py']

def check_paths(a):
    # Preserve the user's device/drive boundary, not a fallback to a laptop.
    if os.name!='nt':raise RuntimeError('biological evaluation is restricted to the authorized Windows D: workspace')
    for p in (a.repo,a.curves,a.reference,a.freeze,a.out):
        if p.resolve().drive.upper()!='D:':raise ValueError('every biological input/output must be on D:')

def verify_source(a):
    check_paths(a)
    paths={'curves':a.curves,'catalog':a.repo/'study/TRAIN_CATALOG.json','reference':a.reference}
    for k,p in paths.items():
        if sha(p)!=INPUT_HASHES[k]:raise ValueError('input hash differs: '+k)
    for rel,h in DEPENDENCIES.items():
        if sha(a.repo/rel)!=h:raise ValueError('dependency changed: '+rel)
    return paths

def freeze(a):
    verify_source(a)
    if a.out.exists():raise ValueError('output already exists; do not freeze over an old attempt')
    record={'schema':'dosepilot.pooled_curve64.freeze.v1','state':'FROZEN_LOCALLY_BEFORE_OUTCOME_NOT_PUBLIC_COMMIT',
      'utc':utc(),'inputs':INPUT_HASHES,'dependencies':DEPENDENCIES,'package':{p:sha(PACKAGE/p) for p in package_files()},
      'menu':MENU,'outer_folds':5,'inner_folds':3,'treatment_wells':64,'per_plate':[32,32],
      'half_error_target':TARGET,'bootstrap_resamples':100000,'bootstrap_seed':BOOTSTRAP_SEED,
      'automatic_retry':False,'automatic_promotion':False,'protected22_access':False,
      'biological_evaluation_completed':False}
    a.freeze.parent.mkdir(parents=True,exist_ok=True);dump(a.freeze,record)
    print(json.dumps({'status':'LOCAL_FREEZE_WRITTEN','path':str(a.freeze),'public_commit':None}))

def load_engine(repo):
    sys.path[:0]=[str(repo/'study'),str(repo/'study/engine'),str(repo/'study/acceleration'),str(repo/'study/hybrid_residual')]
    return {name:importlib.import_module(name) for name in ('compact_train','coverage_methods','fast_coverage','methods','bandwidth_additive')}

def risks(pred,y,p):
    err=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([err[p==g].mean(axis=0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    r=risks(pred,y,p).mean(1);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(r.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(r),.9)),
      'fold_mse':[float(r[pf==f].mean()) for f in range(5)]}
def comparison(c,b,y,p,folds,drug_ids):
    cr=risks(c,y,p);br=risks(b,y,p);d=cr.mean(1)-br.mean(1);td=cr.mean(0)-br.mean(0)
    cm,bm=metrics(c,y,p,folds),metrics(b,y,p,folds);rng=np.random.default_rng(BOOTSTRAP_SEED)
    boot=d[rng.integers(len(d),size=(100000,len(d)))].mean(1)
    wins=int((d<-1e-15).sum());fw=sum(a<bb-1e-15 for a,bb in zip(cm['fold_mse'],bm['fold_mse']));tail=cm['p90_patient_rmse']<=bm['p90_patient_rmse']+1e-15
    return {'relative_mse_gain':1-cm['mse']/bm['mse'],'patient_wins':wins,'patient_losses':int((d>1e-15).sum()),
      'patient_ties':int((abs(d)<=1e-15).sum()),'fold_wins':fw,'p90_nonworse':tail,
      'target_wins':int((td<-1e-15).sum()),'regressing_targets':[str(drug_ids[j]) for j in range(24) if td[j]>1e-15],
      'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
      'gate_pass':bool(cm['mse']<bm['mse']-1e-15 and wins>=30 and fw==5 and tail)}

def build(engine,x,y,p,catalog,bounds,ix):
    cm=engine['coverage_methods'];plan=engine['fast_coverage'].plan_panel_fast(x[ix],y[ix],p[ix],catalog)
    a,b=[cm.acquire(x[ix],plan,o) for o in ('A','B')]
    ctx=cm.fit_prediction_context(a,b,y[ix],p[ix],plan,catalog.target_ids);base=cm.CoveragePredictor(ctx,plan,.01)
    bpa,bpb=base.predict(a),base.predict(b);z=(np.r_[a,b]-base.mean_x)/base.scale_x
    residual=np.r_[y[ix]-bpa,y[ix]-bpb]
    ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inv]),2)/2
    kernel=engine['bandwidth_additive'].BandwidthAdditive(z,residual,w,np.asarray(plan['coordinate_target_indices']),.7)
    coefs=[np.zeros_like(residual)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
    fa,t=encode_paid(a,bpa,plan,bounds,'A');fb,_=encode_paid(b,bpb,plan,bounds,'B')
    flattened_res=np.r_[(y[ix]-bpa).ravel(),(y[ix]-bpb).ravel()]
    patients=np.concatenate((np.repeat(p[ix],24),np.repeat(p[ix],24)))
    pooled=[PooledCurveResidual(alpha).fit(np.r_[fa,fb],flattened_res,np.r_[t,t],patients) for alpha in ALPHAS]
    return {'plan':plan,'base':base,'kernel':kernel,'coefs':coefs,'pooled':pooled,'bounds':bounds}

def predict_paid_options(bundle,paid,o):
    base=bundle['base'];bp=base.predict(paid);cross=bundle['kernel'].centered_cross((paid-base.mean_x)/base.scale_x)
    out=[bp+cross@coef for coef in bundle['coefs']]
    features,t=encode_paid(paid,bp,bundle['plan'],bundle['bounds'],o)
    out.extend(bp+model.predict(features,t).reshape(len(paid),24) for model in bundle['pooled'])
    return np.stack(out)
def export_selected(bundle,selected):
    """Only trusted numerical arrays and JSON metadata, never pickled objects."""
    base=bundle['base'];k=bundle['kernel']
    state={'selected_index':np.asarray(selected),'plan_json':np.asarray(json.dumps(bundle['plan'],sort_keys=True)),
      'bounds':np.asarray(bundle['bounds']),'base_mean_x':base.mean_x.copy(),'base_scale_x':base.scale_x.copy(),
      'base_mean_y':base.mean_y.copy(),'base_beta':base.beta.copy()}
    if selected<10:
        state.update(kernel_z=k.z.copy(),kernel_owner=k.owner.copy(),kernel_weights=k.w.copy(),
          kernel_mean=k.train_mean.copy(),kernel_grand=np.asarray(k.grand),kernel_coef=bundle['coefs'][selected].copy())
    else:
        state.update({'pooled_'+key:np.asarray(value).copy() for key,value in bundle['pooled'][selected-10].state.items()})
    return state


def predict_exported(state,paid,orientation):
    """Separate saved-model inference path accepting exactly 64 paid values."""
    paid=np.asarray(paid,float)
    if paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():raise ValueError('64 finite paid cells required')
    if orientation not in ('A','B'):raise ValueError('unknown orientation')
    base=state['base_mean_y']+((paid-state['base_mean_x'])/state['base_scale_x'])@state['base_beta']
    selected=int(state['selected_index'])
    if selected<10:
        zq=(paid-state['base_mean_x'])/state['base_scale_x'];zt=state['kernel_z'];raw=zq@zt.T
        for target in range(24):
            cols=np.flatnonzero(state['kernel_owner']==target)
            distances=np.sum((zq[:,None,cols]-zt[None,:,cols])**2,axis=2)
            raw+=len(cols)*np.exp(-distances/(2*len(cols)*.49))
        centered=raw-(raw@state['kernel_weights'])[:,None]-state['kernel_mean'][None,:]+state['kernel_grand']
        return base+centered@state['kernel_coef']
    if selected>12:raise ValueError('outside frozen selection menu')
    features,tasks=encode_paid(paid,base,json.loads(str(state['plan_json'])),state['bounds'],orientation)
    model={key.removeprefix('pooled_'):value for key,value in state.items() if key.startswith('pooled_')}
    return base+PooledCurveResidual.predict_state(model,features,tasks).reshape(len(paid),24)


def predict_all(engine,bundle,x,ix):
    return np.stack([predict_paid_options(bundle,engine['coverage_methods'].acquire(x[ix],bundle['plan'],o),o) for o in ('A','B')],axis=1)

def outer(engine,xtrain,y,p,catalog,bounds,folds,f,xquery):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f);assert_disjoint(p[tr],p[te])
    inner,_=engine['methods'].patient_folds(p[tr],3,f'von-organoid-sentinel-v1|inner|{f}')
    oof=np.full((13,2,len(tr),24),np.nan)
    for g in range(3):
        fit=tr[inner!=g];val=tr[inner==g];assert_disjoint(p[fit],p[val])
        bundle=build(engine,xtrain,y,p,catalog,bounds,fit);pred=predict_all(engine,bundle,xtrain,val)
        for k in range(13):
            for o in (0,1):oof[k,o,inner==g,:]=pred[k,o]
    if not np.isfinite(oof).all():raise ValueError('incomplete inner predictions')
    scores=[float(risks(v,y[tr],p[tr]).mean()) for v in oof];selected=int(np.argmin(scores));baseline=int(np.argmin(scores[:10]))
    bundle=build(engine,xtrain,y,p,catalog,bounds,tr);allpred=predict_all(engine,bundle,xquery,te)
    max_poison=0.;max_saved=0.;plan=bundle['plan'];state=export_selected(bundle,selected)
    for oi,o in enumerate(('A','B')):
        native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
        poisoned=np.full((len(te),xquery.shape[1],2),np.nan);poisoned[:,native,plate]=xquery[te][:,native,plate]
        paid=engine['coverage_methods'].acquire(poisoned,plan,o)
        other=predict_paid_options(bundle,paid,o)[selected]
        max_poison=max(max_poison,float(np.max(abs(other-allpred[selected,oi]))))
        max_saved=max(max_saved,float(np.max(abs(predict_exported(state,paid,o)-allpred[selected,oi]))))
    if max_poison>1e-12:raise ValueError('unpaid observation dependence')
    if max_saved>1e-12:raise ValueError('saved-model inference mismatch')
    return allpred[selected],allpred[baseline],{'fold':f,'selected_index':selected,'selected':MENU[selected],
      'inner_mse':scores,'baseline_index':baseline,'unpaid_poison_maxdiff':max_poison,'saved_model_replay_maxdiff':max_saved},bundle

def run(a):
    verify_source(a);fr=json.loads(a.freeze.read_text())
    if fr.get('state')!='FROZEN_LOCALLY_BEFORE_OUTCOME_NOT_PUBLIC_COMMIT' or fr['menu']!=MENU:raise ValueError('invalid trial freeze')
    if fr['inputs']!=INPUT_HASHES or fr['dependencies']!=DEPENDENCIES:raise ValueError('freeze input/dependency contract differs')
    if set(fr['package'])!=set(package_files()):raise ValueError('freeze package is incomplete')
    for rel,h in fr['package'].items():
        if sha(PACKAGE/rel)!=h:raise ValueError('package changed after freeze '+rel)
    a.out.mkdir(parents=True,exist_ok=False)
    dump(a.out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(a.freeze),'python':sys.version,'numpy':np.__version__,'platform':platform.platform()})
    try:
        e=load_engine(a.repo);ct=e['compact_train'];data,features,_=ct.load_prepared(a.curves,a.repo/'study/TRAIN_CATALOG.json')
        x,y,p=features['x_replicates'],data['y'],data['patient_ids'].astype(str);catalog=e['coverage_methods'].catalog_from_features(features)
        spec=ct.read_catalog(a.repo/'study/TRAIN_CATALOG.json');bounds=np.array([spec['target_bounds_nM'][str(t)] for t in data['drug_ids']],float)
        folds,_=e['methods'].patient_folds(p,5,'von-organoid-sentinel-v1|outer')
        with np.load(a.reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('retained comparator identity mismatch')
            reference=z['candidate'].copy()
        rm=metrics(reference,y,p,folds)
        if abs(rm['mse']-REFERENCE_MSE)>1e-15 or abs(rm['p90_patient_rmse']-REFERENCE_P90)>1e-12:raise ValueError('retained score mismatch')
        candidate=np.full((2,*y.shape),np.nan);baseline=candidate.copy();records=[]
        for f in range(5):
            c,b,r,bundle=outer(e,x,y,p,catalog,bounds,folds,f,x);candidate[:,folds==f]=c;baseline[:,folds==f]=b;records.append(r)
            dump(a.out/f'fold_{f}_selection.json',r);dump(a.out/f'fold_{f}_plan.json',bundle['plan'])
            np.savez_compressed(a.out/f'fold_{f}_private.npz',candidate=c,baseline=b)
            np.savez_compressed(a.out/f'fold_{f}_model_private.npz',**export_selected(bundle,r['selected_index']))
            print(json.dumps({'event':'outer_complete','fold':f,'selected':r['selected']}),flush=True)
        altered_x=x.copy();altered_y=y.copy();altered_x[folds==0]+=137;altered_y[folds==0]-=71
        sentinel,_,rr,_=outer(e,altered_x,altered_y,p,catalog,bounds,folds,0,x)
        mutation=float(np.max(abs(sentinel-candidate[:,folds==0])))
        if mutation>1e-12 or rr['selected_index']!=records[0]['selected_index']:raise ValueError('outer training path leakage')
        bm=metrics(baseline,y,p,folds)
        if abs(bm['mse']-BASE_MSE)>1e-12:raise ValueError('operating baseline not reproduced')
        cb=comparison(candidate,baseline,y,p,folds,data['drug_ids']);cr=comparison(candidate,reference,y,p,folds,data['drug_ids']);cm=metrics(candidate,y,p,folds)
        np.savez_compressed(a.out/'predictions_private.npz',candidate=candidate,baseline=baseline,reference=reference,y=y,patients=p,folds=folds,drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.pooled_curve64.result.v1','status':'COMPLETE','candidate':cm,'operating64':bm,'retained64':rm,
          'vs_operating64':cb,'vs_retained64':cr,'selections':records,'treatment_wells':64,'per_plate':[32,32],
          'half_error_target':TARGET,'half_error_point_and_tail_met':bool(cm['mse']<=TARGET and cr['p90_nonworse']),
          'decision':'ELIGIBLE_FOR_FRESH_REPLAY_AND_R13_R18_AUDIT' if cb['gate_pass'] and cr['gate_pass'] else 'REJECT_FOR_PROMOTION',
          'outer_label_curve_mutation_maxdiff':mutation,'prediction_sha256':sha(a.out/'predictions_private.npz'),
          'freeze_sha256':sha(a.freeze),'protected22_access':False,'independent_validation':False,'selection_adjusted':False,
          'automatic_promotion':False,'kaggle_entry_changed':False,'finished_utc':utc()}
        dump(a.out/'RESULT.json',result);print(json.dumps(result,indent=2))
    except BaseException as exc:
        dump(a.out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc(),'automatic_retry':False});raise

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('phase',choices=['freeze','run'])
    ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True)
    ap.add_argument('--freeze',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    (freeze if a.phase=='freeze' else run)(a)
if __name__=='__main__':main()
