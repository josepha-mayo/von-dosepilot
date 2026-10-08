#!/usr/bin/env python3
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
import argparse,importlib.util,json,sys,time,socket,traceback,importlib.metadata
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
spec=importlib.util.spec_from_file_location('stable_operating64_helpers',STUDY/'global_conditional_curve64/run_study.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
sys.path.insert(0,str(HERE));from model import coefficients,PENALTIES
ARMS=('operating_reproduction','independent_output_control','external_output_primary')
OPTIONS={'operating_reproduction':g.OPTIONS,'independent_output_control':('identity',)+PENALTIES,'external_output_primary':('identity',)+PENALTIES}
SEED=202610080106;NETWORK=[]
def deny(*a,**kw):NETWORK.append('blocked');raise RuntimeError('network disabled during biological fitting')

def build(x,y,p,catalog,ix,prior):
    plan=g.plan_panel_fast(x[ix],y[ix],p[ix],catalog);g.validate_plan(plan,catalog)
    a,b=[g.acquire(x[ix],plan,o) for o in ('A','B')]
    context=g.fit_prediction_context(a,b,y[ix],p[ix],plan,catalog.target_ids);base=g.CoveragePredictor(context,plan,.01)
    z=(np.r_[a,b]-base.mean_x)/base.scale_x;residual=np.r_[y[ix]-base.predict(a),y[ix]-base.predict(b)]
    ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inv]),2)/2
    kernel=g.BandwidthAdditive(z,residual,w,np.asarray(plan['coordinate_target_indices']),.7)
    existing=[np.zeros_like(residual)]+[kernel.coefficients(l,f)[0] for f,l in g.OPTIONS[1:]]
    independent=[np.zeros_like(residual)]+[coefficients(kernel.e,kernel.u,w,residual,np.eye(24),l) for l in PENALTIES]
    external=[np.zeros_like(residual)]+[coefficients(kernel.e,kernel.u,w,residual,prior,l) for l in PENALTIES]
    variants=[{'name':name,'state':None,'kernel':kernel,'coefs':coef} for name,coef in zip(ARMS,(existing,independent,external))]
    return {'plan':plan,'base':base,'variants':variants}

def predict_all(x,ix,bundle):
    base=bundle['base'];out={name:np.empty((len(OPTIONS[name]),2,len(ix),24)) for name in ARMS}
    for oi,o in enumerate(('A','B')):
        paid=g.acquire(x[ix],bundle['plan'],o);zq=(paid-base.mean_x)/base.scale_x;bp=base.predict(paid)
        for v in bundle['variants']:
            cross=v['kernel'].centered_cross(zq)
            for k,c in enumerate(v['coefs']):out[v['name']][k,oi]=bp+cross@c
    return out

def fit_outer(xfit,y,p,catalog,folds,f,xquery,prior):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=g.patient_folds(p[tr],3,g.evaluate.SALT+f'|inner|{f}')
    oof={name:np.full((len(OPTIONS[name]),2,len(tr),24),np.nan) for name in ARMS}
    for k in range(3):
        fit=tr[inner!=k];val=tr[inner==k]
        if set(p[fit])&set(p[val]):raise ValueError('inner patient overlap')
        predicted=predict_all(xfit,val,build(xfit,y,p,catalog,fit,prior))
        for name in ARMS:
            for i in range(len(OPTIONS[name])):
                for oi in (0,1):oof[name][i,oi,inner==k,:]=predicted[name][i,oi]
    scores={name:[float(g.risks(q,y[tr],p[tr]).mean()) for q in oof[name]] for name in ARMS}
    if any(not np.isfinite(q).all() for q in oof.values()):raise ValueError('incomplete inner predictions')
    selected={name:int(np.argmin(scores[name])) for name in ARMS}
    bundle=build(xfit,y,p,catalog,tr,prior);pred=predict_all(xquery,te,bundle);states={};estimates={};records={}
    for vi,name in enumerate(ARMS):
        i=selected[name];estimate=pred[name][i]
        state=g.payload(bundle,10*vi+i);state['kernel_weights']=bundle['variants'][vi]['kernel'].w.copy()
        replaydiff=0.;poisondiff=0.
        for oi,o in enumerate(('A','B')):
            paid=g.acquire(xquery[te],bundle['plan'],o);again=g.predict_payload(state,paid,o)
            replaydiff=max(replaydiff,float(np.max(abs(again-estimate[oi]))))
            masked=np.full((len(te),xquery.shape[1],2),np.nan);native=state['native_indices'];plate=state['plate_'+o]
            masked[:,native,plate]=xquery[te][:,native,plate]
            poisoned=g.predict_payload(state,g.acquire(masked,bundle['plan'],o),o)
            poisondiff=max(poisondiff,float(np.max(abs(poisoned-again))))
        if replaydiff>1e-12 or poisondiff>1e-12:raise ValueError('saved-model or physical input invariant')
        states[name]=state;estimates[name]=estimate
        records[name]={'selected_index':i,'selected_option':OPTIONS[name][i],'inner_mse':scores[name],
              'saved_state_replay_maxdiff':replaydiff,'unpaid_poison_maxdiff':poisondiff}
    return estimates,{'fold':f,'arms':records,'treatment_wells':64,'per_plate':[32,32]},states,bundle['plan']

def check(curves,catalog,reference,source):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for key,p in {'curves':curves,'catalog':catalog,'reference':reference,'external_prepared':source}.items():
        if g.sha(p)!=fr['inputs'][key]:raise ValueError('input hash '+key)
    for path,h in fr['source_sha256'].items():
        if g.sha(ROOT/path)!=h:raise ValueError('source hash '+path)
    for package,version in fr['runtime_versions'].items():
        if importlib.metadata.version(package)!=version:raise ValueError('runtime changed '+package)
    return fr

def execute(curves,catalog_path,reference,source,out):
    fr=check(curves,catalog_path,reference,source);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    g.dump(out/'STARTED.json',{'utc':g.utc(),'freeze_sha256':g.sha(HERE/'FREEZE.json'),'runtime_versions':fr['runtime_versions'],'network_denied':True})
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny;began=time.perf_counter()
    try:
        with np.load(source,allow_pickle=False) as z:prior=z['prior'].copy();names=z['drug_names'].astype(str);source_cells=len(z['cell_keys'])
        data,feat,_=g.load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str);catalog=g.catalog_from_features(feat)
        if not np.array_equal(names,catalog.target_ids):raise ValueError('output prior target identity')
        if prior.shape!=(24,24) or source_cells!=33:raise ValueError('external source contract')
        np.linalg.cholesky(prior)
        folds,_=g.patient_folds(p,5,g.evaluate.SALT+'|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('comparator identity')
            retained=z['candidate'].copy();saved_operating=z['bandwidth07'].copy()
        predictions={name:np.full((2,*y.shape),np.nan) for name in ARMS};records=[];first=None
        with threadpool_limits(limits=1):
            for f in range(5):
                pred,rec,states,plan=fit_outer(x,y,p,catalog,folds,f,x,prior)
                for name in ARMS:
                    predictions[name][:,folds==f]=pred[name];np.savez_compressed(out/f'fold_{f}_{name}_model_private.npz',**states[name])
                records.append(rec);g.dump(out/f'fold_{f}_selection.json',rec);g.dump(out/f'fold_{f}_plan.json',plan)
                if f==0:first={name:{k:np.asarray(v).copy() for k,v in state.items()} for name,state in states.items()}
                print(json.dumps({'event':'outer_complete','fold':f,'choices':{a:rec['arms'][a]['selected_option'] for a in ARMS}}),flush=True)
            xx=x.copy();yy=y.copy();xx[folds==0]+=71;yy[folds==0]-=103
            sentinel,srec,sstates,_=fit_outer(xx,yy,p,catalog,folds,0,x,prior)
        isolation={}
        for name in ARMS:
            delta=float(np.max(abs(sentinel[name]-predictions[name][:,folds==0])))
            sd=max(float(np.max(abs(np.asarray(sstates[name][k])-first[name][k]))) for k in first[name])
            if delta>1e-12 or sd>1e-12 or srec['arms'][name]['selected_index']!=records[0]['arms'][name]['selected_index']:raise ValueError('outer evaluation path '+name)
            isolation[name]={'prediction_maxdiff':delta,'state_maxdiff':sd}
        op=predictions['operating_reproduction'];difference=float(np.max(abs(op-saved_operating)))
        if difference>1e-12 or abs(g.metrics(op,y,p,folds)['mse']-g.EXPECTED_BASE)>1e-12:raise ValueError('operating reference not reproduced')
        if NETWORK or any(not np.isfinite(q).all() for q in predictions.values()):raise ValueError('network or incomplete predictions')
        arms={};g.SEED=SEED
        for name in ARMS[1:]:
            m=g.metrics(predictions[name],y,p,folds);vr=g.compare(predictions[name],retained,y,p,folds,data['drug_ids']);vo=g.compare(predictions[name],op,y,p,folds,data['drug_ids'])
            arms[name]={'metrics':m,'vs_retained64':vr,'vs_operating64':vo,'half_error_target_met':bool(m['mse']<=g.HALF_TARGET and vr['p90_nonworse']),
                'decision':'ELIGIBLE_FOR_FRESH_FULL_REPLAY' if vr['gate_pass'] and vo['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        direct=g.compare(predictions['external_output_primary'],predictions['independent_output_control'],y,p,folds,data['drug_ids'])
        np.savez_compressed(out/'predictions_private.npz',**predictions,retained64=retained,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        r={'schema':'dosepilot.external_output_coupling64.result.v1','status':'COMPLETE','primary_arm':'external_output_primary','arms':arms,
          'external_vs_independent_control':direct,'operating_reproduction':g.metrics(op,y,p,folds),'operating_saved_prediction_maxdiff':difference,
          'source_cell_identifiers':source_cells,'source_drugs':20,'output_prior_sha256':g.sha(source),'fold_records':records,
          'outer_label_and_curve_mutation':isolation,'network_attempts':len(NETWORK),'treatment_wells':64,'per_plate':[32,32],
          'half_error_target':g.HALF_TARGET,'prediction_sha256':g.sha(out/'predictions_private.npz'),'freeze_sha256':g.sha(HERE/'FREEZE.json'),
          'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,'kaggle_entry_changed':False,
          'elapsed_seconds':time.perf_counter()-began,'finished_utc':g.utc()}
        g.dump(out/'RESULT.json',r);print(json.dumps({k:v for k,v in r.items() if k!='fold_records'},indent=2),flush=True);return r
    except BaseException as e:g.dump(out/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'utc':g.utc(),'automatic_retry':False});raise
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.source,a.out)
