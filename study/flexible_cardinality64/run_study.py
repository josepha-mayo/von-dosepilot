#!/usr/bin/env python3
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
import argparse,datetime,hashlib,importlib.metadata,json,platform,sys,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration'),str(STUDY/'hybrid_residual')]
from compact_train import load_prepared
from coverage_methods import catalog_from_features
from fast_coverage import plan_panel_fast
from methods import patient_folds
import evaluate
import methods_flexible as flex
OPTIONS=[('identity',0.)]+[(f,l) for f in (.1,.3,.6) for l in (.1,1.,10.)]
POLICIES=('incumbent','flexible_min2','flexible_min1')
MENU=[{'policy':p,'fraction':f,'ridge':l} for p in POLICIES for f,l in OPTIONS]
EXPECTED_BASE=.0010582750420801538;EXPECTED_SCI=.001042745722096212
SEED=202610071213

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def risks(q,y,p):
    e=((q[0]-y)**2+(q[1]-y)**2)/2
    return np.stack([e[p==g].mean(0) for g in np.unique(p)])
def metrics(q,y,p,folds):
    r=risks(q,y,p);per=r.mean(1);pf=np.asarray([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(per.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(per),.9)),
            'fold_mse':[float(per[pf==f].mean()) for f in range(5)],
            'orientation_mse':[float(np.mean([((q[o,p==g]-y[p==g])**2).mean() for g in np.unique(p)])) for o in (0,1)]}

def build(x,y,p,catalog,ix):
    original=plan_panel_fast(x[ix],y[ix],p[ix],catalog)
    table=flex.fitting_subset_table(x[ix],y[ix],p[ix],catalog)
    plans=[original,flex.make_plan(table,catalog,2),flex.make_plan(table,catalog,1)]
    ids,inv,count=np.unique(p[ix],return_inverse=True,return_counts=True);w=np.tile(1./(2*len(ids)*count[inv]),2)
    bundles=[]
    for plan in plans:
        a,b=[flex.acquire(x[ix],plan,o) for o in ('A','B')]
        base=flex.OwnDrugBase(a,b,y[ix],p[ix],plan,catalog.target_ids)
        z=(np.r_[a,b]-base.mean_x)/base.scale_x
        residual=np.r_[y[ix]-base.predict(a),y[ix]-base.predict(b)]
        kernel=flex.FlexibleKernel(z,residual,w,plan['coordinate_target_indices'],.7)
        coefs=[np.zeros_like(residual)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
        bundles.append((plan,base,kernel,coefs))
    return bundles

def predict_all(x,ix,bundles):
    out=np.empty((30,2,len(ix),24))
    for pi,(plan,base,kernel,coefs) in enumerate(bundles):
        for oi,o in enumerate(('A','B')):
            paid=flex.acquire(x[ix],plan,o);z=(paid-base.mean_x)/base.scale_x
            cross=kernel.centered_cross(z);bp=base.predict(paid)
            for ri,c in enumerate(coefs):out[10*pi+ri,oi]=bp+cross@c
    return out

def fit_outer(x,y,p,catalog,folds,f):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=patient_folds(p[tr],3,evaluate.SALT+f'|inner|{f}')
    oof=np.full((30,2,len(tr),24),np.nan)
    for g in range(3):
        fit=tr[inner!=g];val=tr[inner==g]
        if set(p[fit])&set(p[val]):raise ValueError('inner patient overlap')
        q=predict_all(x,val,build(x,y,p,catalog,fit))
        for k in range(30):
            for o in (0,1):oof[k,o,inner==g,:]=q[k,o]
    if not np.isfinite(oof).all():raise ValueError('inner predictions incomplete')
    scores=[float(risks(q,y[tr],p[tr]).mean()) for q in oof]
    chosen=int(np.argmin(scores));base_choice=int(np.argmin(scores[:10]))
    bundles=build(x,y,p,catalog,tr);pred=predict_all(x,te,bundles)
    plan,base,kernel,coefs=bundles[chosen//10];c=coefs[chosen%10]
    poison=0.
    for oi,o in enumerate(('A','B')):
        masked=np.full_like(x[te],np.nan);native=np.asarray(plan['selected_native_indices']);plate=np.asarray(plan[f'orientation_{o}_plate_indices'])
        masked[:,native,plate]=x[te][:,native,plate]
        paid=flex.acquire(masked,plan,o);pp=base.predict(paid)+kernel.centered_cross((paid-base.mean_x)/base.scale_x)@c
        poison=max(poison,float(np.max(np.abs(pp-pred[chosen,oi]))))
    if poison>1e-12:raise ValueError('unpaid query dependence')
    sizes=np.bincount(plan['coordinate_target_indices'],minlength=24)
    record={'fold':f,'selected_index':chosen,'selected':MENU[chosen],'baseline_index':base_choice,'inner_mse':scores,
            'target_cardinalities':sizes.tolist(),'unpaid_poison_maxdiff':poison,'treatment_wells':64,'per_plate':[32,32],
            'all_policy_cardinalities':[np.bincount(b[0]['coordinate_target_indices'],minlength=24).tolist() for b in bundles]}
    return pred[chosen],pred[base_choice],record,plan

def compare(q,ref,y,p,folds,targets):
    c,r=risks(q,y,p),risks(ref,y,p);d=c.mean(1)-r.mean(1);t=c.mean(0)-r.mean(0)
    cm,rm=metrics(q,y,p,folds),metrics(ref,y,p,folds)
    rng=np.random.default_rng(SEED);boot=d[rng.integers(0,len(d),size=(100000,len(d)))].mean(1)
    wins=int((d<-1e-15).sum());fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']))
    tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'patient_losses':int((d>1e-15).sum()),
            'patient_ties':int((np.abs(d)<=1e-15).sum()),'fold_wins':fw,'p90_nonworse':tail,
            'target_wins':int((t<-1e-15).sum()),'regressing_targets':[str(targets[i]) for i in range(24) if t[i]>1e-15],
            'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
            'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}

def check_freeze(curves,catalog,scientific):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    if fr['state']!='FROZEN_BEFORE_FIRST_CANDIDATE_OUTCOME':raise ValueError('freeze state')
    for k,p in {'curves':curves,'catalog':catalog,'scientific64':scientific}.items():
        if sha(p)!=fr['inputs'][k]:raise ValueError('input hash '+k)
    for rel,h in fr['files'].items():
        if sha(ROOT/rel)!=h:raise ValueError('source hash '+rel)
    return fr

def execute(curves,catalog_path,scientific_path,out):
    fr=check_freeze(curves,catalog_path,scientific_path)
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'python':sys.version,'numpy':np.__version__,
         'platform':platform.platform(),'deps':{k:importlib.metadata.version(k) for k in ('numpy','scipy','scikit-learn')},'protected22_access':False})
    try:
        data,feat,_=load_prepared(curves,catalog_path)
        x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str);catalog=catalog_from_features(feat)
        folds,_=patient_folds(p,5,evaluate.SALT+'|outer')
        with np.load(scientific_path,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('scientific comparator identity')
            scientific=z['candidate'].copy()
        if abs(metrics(scientific,y,p,folds)['mse']-EXPECTED_SCI)>1e-15:raise ValueError('scientific comparator metric')
        candidate=np.full((2,*y.shape),np.nan);baseline=candidate.copy();records=[]
        with threadpool_limits(limits=1):
            for f in range(5):
                c,b,r,plan=fit_outer(x,y,p,catalog,folds,f)
                candidate[:,folds==f]=c;baseline[:,folds==f]=b;records.append(r)
                dump(out/f'fold_{f}_selection.json',r);dump(out/f'fold_{f}_plan.json',plan)
                np.savez_compressed(out/f'fold_{f}_private.npz',candidate=c,baseline=b)
                print(json.dumps({'event':'outer_complete','fold':f,'selected':r['selected'],'cardinalities':r['target_cardinalities']}),flush=True)
            changed=y.copy();changed[folds==0]+=np.arange(24)[None,:]+31
            sentinel,_,sr,_=fit_outer(x,changed,p,catalog,folds,0)
        if not np.isfinite(candidate).all() or not np.isfinite(baseline).all():raise ValueError('incomplete outer predictions')
        mutation=float(np.max(np.abs(sentinel-candidate[:,folds==0])))
        if mutation>1e-12 or sr['selected_index']!=records[0]['selected_index']:raise ValueError('outer label isolation')
        cm,bm=metrics(candidate,y,p,folds),metrics(baseline,y,p,folds)
        if abs(bm['mse']-EXPECTED_BASE)>1e-12:raise ValueError('incumbent numerical replay')
        cb=compare(candidate,baseline,y,p,folds,data['drug_ids']);cs=compare(candidate,scientific,y,p,folds,data['drug_ids'])
        np.savez_compressed(out/'predictions_private.npz',candidate=candidate,baseline=baseline,scientific64=scientific,
              y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.flexible_cardinality64.result.v1','status':'COMPLETE','candidate':cm,'baseline64':bm,
                'scientific64':metrics(scientific,y,p,folds),'candidate_vs_baseline':cb,'candidate_vs_scientific64':cs,
                'selections':records,'treatment_wells':64,'per_plate':[32,32],'outer_label_mutation_maxdiff':mutation,
                'baseline_mse_difference':abs(bm['mse']-EXPECTED_BASE),'halved_mse_target':EXPECTED_SCI/2,
                'halved_mse_target_met':bool(cm['mse']<=EXPECTED_SCI/2),'decision':'ELIGIBLE_FOR_REPLAY' if cb['gate_pass'] and cs['gate_pass'] else 'REJECT_FOR_PROMOTION',
                'prediction_sha256':sha(out/'predictions_private.npz'),'freeze_sha256':sha(HERE/'FREEZE.json'),
                'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,
                'kaggle_entry_changed':False,'finished_utc':utc()}
        dump(out/'RESULT.json',result)
        print(json.dumps({k:result[k] for k in ('candidate','candidate_vs_baseline','candidate_vs_scientific64','decision','halved_mse_target_met','outer_label_mutation_maxdiff')},indent=2),flush=True)
        return result
    except BaseException as exc:
        dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False,'utc':utc()});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True)
    ap.add_argument('--scientific64',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.scientific64,a.out)
