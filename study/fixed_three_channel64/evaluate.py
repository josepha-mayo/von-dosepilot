#!/usr/bin/env python3
from pathlib import Path
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,datetime,hashlib,json,sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'study'),str(ROOT/'study/engine'),str(ROOT/'study/acceleration')]
from compact_train import load_prepared
from coverage_methods import catalog_from_features,validate_plan
from fast_coverage import plan_panel_fast
SEED=202610071730

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def combine(kernel,direct,exact):
    arrays=[np.asarray(v,float) for v in (kernel,direct,exact)]
    if any(v.shape!=arrays[0].shape or not np.isfinite(v).all() for v in arrays):raise ValueError('aligned finite component predictions required')
    return sum(arrays)/3.0

def risks(q,y,p):
    errors=((q[0]-y)**2+(q[1]-y)**2)/2
    return np.stack([errors[p==g].mean(0) for g in np.unique(p)])
def metrics(q,y,p,folds):
    losses=risks(q,y,p).mean(1);pf=np.array([folds[np.flatnonzero(p==g)[0]] for g in np.unique(p)])
    return {'mse':float(losses.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(losses),.9)),
      'fold_mse':[float(losses[pf==f].mean()) for f in range(5)]}
def comparison(c,r,y,p,folds,names):
    cr,rr=risks(c,y,p),risks(r,y,p);d=cr.mean(1)-rr.mean(1);dt=cr.mean(0)-rr.mean(0)
    cm,rm=metrics(c,y,p,folds),metrics(r,y,p,folds);wins=int((d<-1e-15).sum());fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']))
    tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    boot=d[np.random.default_rng(SEED).integers(len(d),size=(100000,len(d)))].mean(1)
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'patient_losses':int((d>1e-15).sum()),'fold_wins':fw,'p90_nonworse':tail,
      'target_wins':int((dt<-1e-15).sum()),'regressing_targets':[str(names[j]) for j in range(24) if dt[j]>1e-15],
      'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}

def evaluate(direct_run,exact_run,curves,catalog_path,out):
    freeze_path=HERE/'FREEZE.json';fr=json.loads(freeze_path.read_text())
    for rel,h in fr['source_sha256'].items():assert sha(ROOT/rel)==h,rel
    assert sha(curves)==fr['inputs']['curves'] and sha(catalog_path)==fr['inputs']['catalog']
    producers={}
    for name,run in (('direct',direct_run),('exact',exact_run)):
        result=json.loads((run/'RESULT.json').read_text());assert result['status']=='COMPLETE'
        assert result['freeze_sha256']==fr['producer_freeze_sha256'][name]
        assert result['prediction_sha256']==sha(run/'predictions_private.npz') and result['network_attempts']==0
        assert not result['protected22_access'] and not result['kaggle_entry_changed']
        with np.load(run/'predictions_private.npz',allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
        producers[name]={'result':result,'arrays':arrays,'result_sha256':sha(run/'RESULT.json'),'prediction_sha256':sha(run/'predictions_private.npz')}
    a=producers['direct']['arrays'];b=producers['exact']['arrays']
    for key in ('y','patients','folds','sample_ids','drug_ids'):assert np.array_equal(a[key],b[key]),key
    for key in ('retained64','operating64'):assert np.array_equal(a[key],b[key]),key
    y,p,folds=a['y'],a['patients'].astype(str),a['folds']
    data,features,_=load_prepared(curves,catalog_path);catalog=catalog_from_features(features)
    assert np.array_equal(y,data['y']) and np.array_equal(p,data['patient_ids'].astype(str))
    assert y.shape==(119,24) and len(np.unique(p))==59
    layout_keys=('selected_native_indices','orientation_A_plate_indices','orientation_B_plate_indices','coordinate_target_indices')
    plan_hashes=[]
    for f in range(5):
        dplan=json.loads((direct_run/f'fold_{f}_plan.json').read_text());eplan=json.loads((exact_run/f'fold_{f}_plan.json').read_text())
        validate_plan(dplan,catalog);validate_plan(eplan,catalog)
        tr=folds!=f;regenerated=plan_panel_fast(features['x_replicates'][tr],y[tr],p[tr],catalog)
        for key in layout_keys:assert list(dplan[key])==list(eplan[key])==list(regenerated[key]),(f,key)
        plan_hashes.append({'fold':f,'direct_plan_sha256':sha(direct_run/f'fold_{f}_plan.json'),'exact_plan_sha256':sha(exact_run/f'fold_{f}_plan.json'),'physical_wells':64,'per_plate':[32,32]})
    candidate=combine(a['operating64'],a['full_context'],b['candidate']);cm=metrics(candidate,y,p,folds)
    vsret=comparison(candidate,a['retained64'],y,p,folds,a['drug_ids']);vsop=comparison(candidate,a['operating64'],y,p,folds,a['drug_ids'])
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(out/'predictions_private.npz',candidate=candidate,kernel=a['operating64'],direct=a['full_context'],exact=b['candidate'],retained64=a['retained64'],y=y,patients=p,folds=folds,sample_ids=a['sample_ids'],drug_ids=a['drug_ids'])
    result={'schema':'dosepilot.fixed_three_channel64.result.v1','status':'COMPLETE','model_name':'TabPFN-von-DosePilot-Three64','attribution':'Built with PriorLabs-TabPFN',
      'weights':[1/3,1/3,1/3],'components':['operating_kernel64','direct_TabPFN_full_context64','exact_contribution_TabPFN64'],
      'candidate':cm,'vs_retained64':vsret,'vs_operating64':vsop,'half_error_target':.000521372861048106,
      'half_error_point_and_tail_met':bool(cm['mse']<=.000521372861048106 and vsret['p90_nonworse']),
      'decision':'ELIGIBLE_FOR_FRESH_PRODUCER_REPLAY' if vsret['gate_pass'] and vsop['gate_pass'] else 'REJECT_FOR_PROMOTION',
      'treatment_wells':64,'per_plate':[32,32],'plan_checks':plan_hashes,'meta_training_performed':False,'weights_selected_from_outcomes':False,
      'producer_hashes':{name:{k:entry[k] for k in ('result_sha256','prediction_sha256')} for name,entry in producers.items()},
      'prediction_sha256':sha(out/'predictions_private.npz'),'freeze_sha256':sha(freeze_path),'protected22_access':False,'independent_validation':False,
      'selection_adjusted':False,'automatic_promotion':False,'kaggle_entry_changed':False,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (out/'RESULT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2),flush=True);return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--direct-run',type=Path,required=True);ap.add_argument('--exact-run',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();evaluate(a.direct_run,a.exact_run,a.curves,a.catalog,a.out)
