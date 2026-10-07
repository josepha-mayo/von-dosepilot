#!/usr/bin/env python3
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
import argparse,datetime,hashlib,json,platform,sys,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration'),str(STUDY/'hybrid_residual')]
from conditional import exact_auc_map,fit_population,condition,predict as conditional_predict
from full_curves import full_training_curves
from compact_train import load_prepared,read_catalog
from coverage_methods import acquire,fit_prediction_context,CoveragePredictor,catalog_from_features,validate_plan
from fast_coverage import plan_panel_fast
from methods import patient_folds
import evaluate
from bandwidth_additive import BandwidthAdditive
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
BASES=('own_drug','conditional_rank0','conditional_rank4','conditional_rank12')
MENU=[{'base':base,'fraction':f,'kernel_ridge':l} for base in BASES for f,l in OPTIONS]
EXPECTED_BASE=.0010582750420801538;EXPECTED_SCI=.001042745722096212
HALF_TARGET=EXPECTED_SCI/2;SEED=202610071236

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def risks(pred,y,p):
    e=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(pred,y,p,folds):
    v=risks(pred,y,p);r=v.mean(1);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(r.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(r),.9)),
        'fold_mse':[float(r[pf==f].mean()) for f in range(5)],
        'orientation_mse':[float(np.mean([((pred[o,p==g]-y[p==g])**2).mean() for g in np.unique(p)])) for o in (0,1)]}

def build(x,y,p,catalog,q,ix,full):
    plan=plan_panel_fast(x[ix],y[ix],p[ix],catalog);validate_plan(plan,catalog)
    a,b=[acquire(x[ix],plan,o) for o in ('A','B')]
    context=fit_prediction_context(a,b,y[ix],p[ix],plan,catalog.target_ids);base=CoveragePredictor(context,plan,.01)
    canonical=np.r_[a,b];z=(canonical-base.mean_x)/base.scale_x
    ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(len(ids)*count[inv]),2)/2
    owner=np.asarray(plan['coordinate_target_indices'],int);variants=[]
    for name,rank in zip(BASES,(None,0,4,12)):
        if rank is None:
            state=None;pa,pb=base.predict(a),base.predict(b)
        else:
            pop=fit_population(full['values'][ix],p[ix],full['owner'],rank)
            state=condition(pop,plan,q,full['query_to_full']);pa=conditional_predict(state,a,'A');pb=conditional_predict(state,b,'B')
        residual=np.r_[y[ix]-pa,y[ix]-pb]
        kernel=BandwidthAdditive(z,residual,w,owner,.7)
        coef=[np.zeros_like(residual)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
        variants.append({'name':name,'state':state,'kernel':kernel,'coefs':coef})
    return {'plan':plan,'base':base,'variants':variants}

def predict_all(x,ix,bundle):
    plan,base=bundle['plan'],bundle['base'];out=np.empty((40,2,len(ix),24))
    for oi,o in enumerate(('A','B')):
        paid=acquire(x[ix],plan,o);zq=(paid-base.mean_x)/base.scale_x
        for vi,v in enumerate(bundle['variants']):
            bp=base.predict(paid) if v['state'] is None else conditional_predict(v['state'],paid,o)
            cross=v['kernel'].centered_cross(zq)
            for k,c in enumerate(v['coefs']):out[10*vi+k,oi]=bp+cross@c
    return out

def payload(bundle,selected):
    vi,ci=divmod(selected,10);v=bundle['variants'][vi];base=bundle['base'];kernel=v['kernel'];plan=bundle['plan']
    result={'canonical_mean':base.mean_x,'canonical_scale':base.scale_x,'kernel_z':kernel.z,
       'kernel_owner':kernel.owner,'kernel_mean':kernel.train_mean,'kernel_grand':np.asarray(kernel.grand),
       'coef':v['coefs'][ci],'native_indices':np.asarray(plan['selected_native_indices']),
       'plate_A':np.asarray(plan['orientation_A_plate_indices']),'plate_B':np.asarray(plan['orientation_B_plate_indices']),
       'selected_index':np.asarray(selected)}
    for o in ('A','B'):
        if v['state'] is None:
            values={'mean_x':base.mean_x,'scale_x':base.scale_x,'beta':base.beta,'mean_y':base.mean_y}
        else:
            s=v['state']['orientations'][o]
            values={'mean_x':s['mean_x'],'scale_x':s['scale_x'],'beta':s['beta'],'mean_y':v['state']['mean_y']}
        result.update({k+'_'+o:val for k,val in values.items()})
    return result

def predict_payload(state,paid,o):
    paid=np.asarray(paid,float)
    if o not in ('A','B') or paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():raise ValueError('exactly 64 finite purchased cells required')
    base=state['mean_y_'+o]+((paid-state['mean_x_'+o])/state['scale_x_'+o])@state['beta_'+o]
    zq=(paid-state['canonical_mean'])/state['canonical_scale'];z=state['kernel_z']
    raw=zq@z.T
    for j in range(24):
        cols=np.flatnonzero(state['kernel_owner']==j);a,b=zq[:,cols],z[:,cols]
        dist=np.maximum(np.sum(a*a,1)[:,None]+np.sum(b*b,1)[None,:]-2*a@b.T,0.)
        raw+=len(cols)*np.exp(-dist/(2*len(cols)*.7**2))
    # Center with the fitting observation weights; stored separately in the payload.
    centered=raw-(raw@state['kernel_weights'])[:,None]-state['kernel_mean'][None,:]+state['kernel_grand']
    return base+centered@state['coef']

def select(x,y,p,catalog,q,outer_ix,f,full):
    inner,_=patient_folds(p[outer_ix],3,evaluate.SALT+f'|inner|{f}')
    oof=np.full((40,2,len(outer_ix),24),np.nan)
    for g in range(3):
        tr=outer_ix[inner!=g];va=outer_ix[inner==g]
        if set(p[tr])&set(p[va]):raise ValueError('inner patient overlap')
        pred=predict_all(x,va,build(x,y,p,catalog,q,tr,full))
        for k in range(40):
            for o in (0,1):oof[k,o,inner==g,:]=pred[k,o]
    if not np.isfinite(oof).all():raise ValueError('inner OOF incomplete')
    scores=[float(risks(pred,y[outer_ix],p[outer_ix]).mean()) for pred in oof]
    return int(np.argmin(scores)),int(np.argmin(scores[:10])),scores

def fit_outer(x_fit,y,p,catalog,q,folds,f,x_query,full):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer overlap')
    chosen,baseline,scores=select(x_fit,y,p,catalog,q,tr,f,full)
    bundle=build(x_fit,y,p,catalog,q,tr,full);pred=predict_all(x_query,te,bundle)
    state=payload(bundle,chosen);state['kernel_weights']=bundle['variants'][chosen//10]['kernel'].w.copy()
    max_replay=0.;max_poison=0.;plan=bundle['plan']
    for oi,o in enumerate(('A','B')):
        paid=acquire(x_query[te],plan,o)
        restored=predict_payload(state,paid,o)
        max_replay=max(max_replay,float(np.max(np.abs(restored-pred[chosen,oi]))))
        masked=np.full((len(te),x_query.shape[1],2),np.nan)
        native=state['native_indices'];plate=state['plate_'+o]
        masked[:,native,plate]=x_query[te][:,native,plate]
        poisoned=acquire(masked,plan,o)
        max_poison=max(max_poison,float(np.max(np.abs(predict_payload(state,poisoned,o)-restored))))
    if max_replay>1e-12 or max_poison>1e-12:raise ValueError('saved state or unpaid-cell invariant failed')
    rec={'fold':f,'selected_index':chosen,'selected':MENU[chosen],'baseline_index':baseline,'inner_mse':scores,
         'state_replay_maxdiff':max_replay,'unpaid_poison_maxdiff':max_poison,'treatment_wells':64,'per_plate':[32,32]}
    return pred[chosen],pred[baseline],rec,state,plan

def compare(c,r,y,p,folds,targets):
    a=risks(c,y,p);b=risks(r,y,p);d=a.mean(1)-b.mean(1);dt=a.mean(0)-b.mean(0)
    cm,rm=metrics(c,y,p,folds),metrics(r,y,p,folds)
    wins=int((d<-1e-15).sum());fw=sum(u<v-1e-15 for u,v in zip(cm['fold_mse'],rm['fold_mse']))
    tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    rng=np.random.default_rng(SEED);boot=d[rng.integers(len(d),size=(100000,len(d)))].mean(1)
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'patient_losses':int((d>1e-15).sum()),
       'patient_ties':int((np.abs(d)<=1e-15).sum()),'fold_wins':fw,'p90_nonworse':tail,
       'target_wins':int((dt<-1e-15).sum()),'regressing_targets':[str(targets[j]) for j in range(24) if dt[j]>1e-15],
       'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
       'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}

def check_freeze(curves,catalog,scientific):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for k,p in {'curves':curves,'catalog':catalog,'scientific64':scientific}.items():
        if sha(p)!=fr['inputs'][k]:raise ValueError('input hash mismatch '+k)
    for rel,h in fr['files'].items():
        if sha(ROOT/rel)!=h:raise ValueError('source hash mismatch '+rel)
    return fr

def execute(curves,catalog_path,scientific_path,out):
    fr=check_freeze(curves,catalog_path,scientific_path);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'python':sys.version,
       'numpy':np.__version__,'platform':platform.platform(),'protected22_access':False})
    try:
        data,feat,_=load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=catalog_from_features(feat)
        full=full_training_curves(curves,data,feat,catalog,read_catalog(catalog_path));q=full['q']
        quadrature_diff=full['quadrature_maxdiff']
        if quadrature_diff>1e-12:raise ValueError('exact physical endpoint map failed')
        folds,_=patient_folds(p,5,evaluate.SALT+'|outer')
        with np.load(scientific_path,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity mismatch')
            scientific=z['candidate'].copy()
        if abs(metrics(scientific,y,p,folds)['mse']-EXPECTED_SCI)>1e-15:raise ValueError('retained score mismatch')
        candidate=np.full((2,*y.shape),np.nan);baseline=candidate.copy();records=[]
        first_state=None
        with threadpool_limits(limits=1):
            for f in range(5):
                c,b,r,state,plan=fit_outer(x,y,p,catalog,q,folds,f,x,full)
                candidate[:,folds==f]=c;baseline[:,folds==f]=b;records.append(r)
                dump(out/f'fold_{f}_selection.json',r);dump(out/f'fold_{f}_plan.json',plan)
                np.savez_compressed(out/f'fold_{f}_model_private.npz',**state)
                if f==0:first_state={k:np.asarray(v).copy() for k,v in state.items()}
                print(json.dumps({'event':'outer_complete','fold':f,'selected':r['selected']}),flush=True)
            altered_x=x.copy();altered_y=y.copy();altered_x[folds==0]+=37.;altered_y[folds==0]+=np.arange(24)[None,:]+71.
            altered_full=dict(full);altered_full['values']=full['values'].copy();altered_full['values'][folds==0]-=137.
            sentinel,_,sr,ss,_=fit_outer(altered_x,altered_y,p,catalog,q,folds,0,x,altered_full)
        mutation=float(np.max(np.abs(sentinel-candidate[:,folds==0])))
        state_difference=max(float(np.max(np.abs(np.asarray(ss[k])-first_state[k]))) for k in first_state)
        if mutation>1e-12 or state_difference>1e-12 or sr['selected_index']!=records[0]['selected_index']:
            raise ValueError('outer-test training path detected')
        bm=metrics(baseline,y,p,folds)
        if abs(bm['mse']-EXPECTED_BASE)>1e-12:raise ValueError('operating reference reconstruction failed')
        cm=metrics(candidate,y,p,folds);cb=compare(candidate,baseline,y,p,folds,data['drug_ids']);cs=compare(candidate,scientific,y,p,folds,data['drug_ids'])
        np.savez_compressed(out/'predictions_private.npz',candidate=candidate,baseline64=baseline,scientific64=scientific,
             y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.global_conditional_curve64.result.v1','status':'COMPLETE','candidate':cm,'operating64':bm,
           'scientific64':metrics(scientific,y,p,folds),'candidate_vs_operating64':cb,'candidate_vs_scientific64':cs,
           'selections':records,'treatment_wells':64,'per_plate':[32,32],'half_error_target':HALF_TARGET,
           'half_error_target_met':bool(cm['mse']<=HALF_TARGET and cs['p90_nonworse']),
           'decision':'ELIGIBLE_FOR_FULL_REPLAY' if cb['gate_pass'] and cs['gate_pass'] else 'REJECT_FOR_PROMOTION',
           'quadrature_maxdiff':quadrature_diff,'full_training_physical_cells':full['full_physical_cells'],
           'eligible_physical_cells':full['eligible_physical_cells'],'new_inference_actions_added':False,
           'outer_label_and_curve_mutation_maxdiff':mutation,
           'outer_label_and_curve_state_maxdiff':state_difference,'baseline_mse_difference':abs(bm['mse']-EXPECTED_BASE),
           'prediction_sha256':sha(out/'predictions_private.npz'),'freeze_sha256':sha(HERE/'FREEZE.json'),
           'protected22_access':False,'independent_validation':False,'selection_adjusted':False,
           'automatic_promotion':False,'kaggle_entry_changed':False,'finished_utc':utc()}
        dump(out/'RESULT.json',result);print(json.dumps(result,indent=2),flush=True);return result
    except BaseException as exc:
        dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--scientific64',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.scientific64,a.out)
