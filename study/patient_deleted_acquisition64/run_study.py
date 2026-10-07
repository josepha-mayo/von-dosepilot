#!/usr/bin/env python3
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
import argparse,importlib.util,json,sys,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('frozen_64_kernel_helpers',ROOT/'study/global_conditional_curve64/run_study.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
sys.path.insert(0,str(HERE));from planner import plan_patient_deleted
SEED=202610071300
MENU=[{'policy':policy,'fraction':f,'kernel_ridge':l} for policy in ('original','patient_deleted') for f,l in g.OPTIONS]

def build(x,y,p,catalog,ix,policy):
    plan=g.plan_panel_fast(x[ix],y[ix],p[ix],catalog) if policy=='original' else plan_patient_deleted(x[ix],y[ix],p[ix],catalog)
    a,b=[g.acquire(x[ix],plan,o) for o in ('A','B')]
    ctx=g.fit_prediction_context(a,b,y[ix],p[ix],plan,catalog.target_ids);base=g.CoveragePredictor(ctx,plan,.01)
    z=(np.r_[a,b]-base.mean_x)/base.scale_x;res=np.r_[y[ix]-base.predict(a),y[ix]-base.predict(b)]
    ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inv]),2)/2
    kernel=g.BandwidthAdditive(z,res,w,np.asarray(plan['coordinate_target_indices']),.7)
    coef=[np.zeros_like(res)]+[kernel.coefficients(l,f)[0] for f,l in g.OPTIONS[1:]]
    return {'plan':plan,'base':base,'variants':[{'name':policy,'state':None,'kernel':kernel,'coefs':coef}]}

def predict_all(x,ix,bundle):
    base=bundle['base'];plan=bundle['plan'];v=bundle['variants'][0];out=np.empty((10,2,len(ix),24))
    for oi,o in enumerate(('A','B')):
        paid=g.acquire(x[ix],plan,o);cross=v['kernel'].centered_cross((paid-base.mean_x)/base.scale_x);bp=base.predict(paid)
        for k,c in enumerate(v['coefs']):out[k,oi]=bp+cross@c
    return out

def fit_outer(xfit,y,p,catalog,folds,f,xquery):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer overlap')
    inner,_=g.patient_folds(p[tr],3,g.evaluate.SALT+f'|inner|{f}');oof=np.full((20,2,len(tr),24),np.nan)
    for fold in range(3):
        fit=tr[inner!=fold];val=tr[inner==fold]
        if set(p[fit])&set(p[val]):raise ValueError('inner overlap')
        for pi,policy in enumerate(('original','patient_deleted')):
            pr=predict_all(xfit,val,build(xfit,y,p,catalog,fit,policy))
            for k in range(10):
                for o in (0,1):oof[pi*10+k,o,inner==fold,:]=pr[k,o]
    if not np.isfinite(oof).all():raise ValueError('inner predictions missing')
    scores=[float(g.risks(q,y[tr],p[tr]).mean()) for q in oof];chosen=int(np.argmin(scores));reference=int(np.argmin(scores[:10]))
    original=build(xfit,y,p,catalog,tr,'original');baseline=predict_all(xquery,te,original)[reference]
    candidate_bundle=original if chosen<10 else build(xfit,y,p,catalog,tr,'patient_deleted')
    candidate=predict_all(xquery,te,candidate_bundle)[chosen%10]
    state=g.payload(candidate_bundle,chosen%10);state['kernel_weights']=candidate_bundle['variants'][0]['kernel'].w.copy()
    maxreplay=0.;maxpoison=0.
    for oi,o in enumerate(('A','B')):
        paid=g.acquire(xquery[te],candidate_bundle['plan'],o)
        pp=g.predict_payload(state,paid,o);maxreplay=max(maxreplay,float(np.max(np.abs(pp-candidate[oi]))))
        masked=np.full((len(te),xquery.shape[1],2),np.nan);native=state['native_indices'];plate=state['plate_'+o]
        masked[:,native,plate]=xquery[te][:,native,plate]
        mp=g.predict_payload(state,g.acquire(masked,candidate_bundle['plan'],o),o)
        maxpoison=max(maxpoison,float(np.max(np.abs(mp-pp))))
    if maxreplay>1e-12 or maxpoison>1e-12:raise ValueError('replay or physical-input invariant failed')
    plan=candidate_bundle['plan'];original_plan=original['plan']
    changed=len(set(plan['selected_native_indices'])-set(original_plan['selected_native_indices']))
    rec={'fold':f,'selected_index':chosen,'selected':MENU[chosen],'baseline_index':reference,'inner_mse':scores,
         'changed_native_doses_from_original':changed,'state_replay_maxdiff':maxreplay,'unpaid_poison_maxdiff':maxpoison,
         'treatment_wells':64,'per_plate':[32,32]}
    return candidate,baseline,rec,state,plan

def check(curves,catalog,scientific):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for k,path in {'curves':curves,'catalog':catalog,'scientific64':scientific}.items():
        if g.sha(path)!=fr['inputs'][k]:raise ValueError('input hash '+k)
    for rel,h in fr['files'].items():
        if g.sha(ROOT/rel)!=h:raise ValueError('source hash '+rel)
    return fr

def execute(curves,catalog_path,scientific_path,out):
    fr=check(curves,catalog_path,scientific_path);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    g.dump(out/'STARTED.json',{'utc':g.utc(),'freeze_sha256':g.sha(HERE/'FREEZE.json'),'python':sys.version,'numpy':np.__version__,'protected22_access':False})
    try:
        data,feat,_=g.load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=g.catalog_from_features(feat);folds,_=g.patient_folds(p,5,g.evaluate.SALT+'|outer')
        with np.load(scientific_path,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            scientific=z['candidate'].copy()
        candidate=np.full((2,*y.shape),np.nan);baseline=candidate.copy();records=[];first_state=None
        with threadpool_limits(limits=1):
            for fold in range(5):
                c,b,r,state,plan=fit_outer(x,y,p,catalog,folds,fold,x)
                candidate[:,folds==fold]=c;baseline[:,folds==fold]=b;records.append(r)
                g.dump(out/f'fold_{fold}_selection.json',r);g.dump(out/f'fold_{fold}_plan.json',plan)
                np.savez_compressed(out/f'fold_{fold}_model_private.npz',**state)
                if fold==0:first_state={k:np.asarray(v).copy() for k,v in state.items()}
                print(json.dumps({'event':'outer_complete','fold':fold,'selected':r['selected'],'changed_doses':r['changed_native_doses_from_original']}),flush=True)
            xx=x.copy();yy=y.copy();xx[folds==0]+=37;yy[folds==0]+=71
            sentinel,_,sr,ss,_=fit_outer(xx,yy,p,catalog,folds,0,x)
        mutation=float(np.max(np.abs(sentinel-candidate[:,folds==0])))
        state_diff=max(float(np.max(np.abs(np.asarray(ss[k])-first_state[k]))) for k in first_state)
        if mutation>1e-12 or state_diff>1e-12 or sr['selected_index']!=records[0]['selected_index']:raise ValueError('outer-label training leakage')
        bm=g.metrics(baseline,y,p,folds)
        if abs(bm['mse']-g.EXPECTED_BASE)>1e-12:raise ValueError('baseline not reproduced')
        g.SEED=SEED
        cb=g.compare(candidate,baseline,y,p,folds,data['drug_ids']);cs=g.compare(candidate,scientific,y,p,folds,data['drug_ids']);cm=g.metrics(candidate,y,p,folds)
        np.savez_compressed(out/'predictions_private.npz',candidate=candidate,baseline64=baseline,scientific64=scientific,
           y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        r={'schema':'dosepilot.patient_deleted_acquisition64.result.v1','status':'COMPLETE','candidate':cm,'operating64':bm,
          'scientific64':g.metrics(scientific,y,p,folds),'candidate_vs_operating64':cb,'candidate_vs_scientific64':cs,
          'selections':records,'treatment_wells':64,'per_plate':[32,32],'half_error_target':g.HALF_TARGET,
          'half_error_target_met':bool(cm['mse']<=g.HALF_TARGET and cs['p90_nonworse']),
          'decision':'ELIGIBLE_FOR_FULL_REPLAY' if cb['gate_pass'] and cs['gate_pass'] else 'REJECT_FOR_PROMOTION',
          'outer_label_and_curve_mutation_maxdiff':mutation,'outer_state_mutation_maxdiff':state_diff,
          'baseline_mse_difference':abs(bm['mse']-g.EXPECTED_BASE),'prediction_sha256':g.sha(out/'predictions_private.npz'),
          'freeze_sha256':g.sha(HERE/'FREEZE.json'),'protected22_access':False,'independent_validation':False,
          'selection_adjusted':False,'automatic_promotion':False,'kaggle_entry_changed':False,'finished_utc':g.utc()}
        g.dump(out/'RESULT.json',r);print(json.dumps(r,indent=2),flush=True);return r
    except BaseException as exc:g.dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--scientific64',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.scientific64,a.out)
