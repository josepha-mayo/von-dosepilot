#!/usr/bin/env python3
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
import argparse,csv,datetime,hashlib,importlib.metadata,json,socket,sys,time,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
sys.path[:0]=[str(HERE),str(STUDY),str(STUDY/'engine'),str(STUDY/'acceleration'),str(STUDY/'global_conditional_curve64')]
from model import fit_population,condition,predict
from compact_train import load_prepared,read_catalog
from full_curves import full_training_curves
from coverage_methods import acquire,catalog_from_features,validate_plan
from fast_coverage import plan_panel_fast
from methods import patient_folds
ARMS=('mixture','gaussian_control');SEED=202610072102;HALF=.000521372861048106
NETWORK=[]
def deny(*a,**kw):NETWORK.append('blocked');raise RuntimeError('network forbidden during biological work')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def target_risks(pred,y,p):
    error=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return np.stack([error[p==patient].mean(0) for patient in np.unique(p)])
def metrics(pred,y,p,folds):
    r=target_risks(pred,y,p).mean(1);pf=np.array([folds[np.flatnonzero(p==patient)[0]] for patient in np.unique(p)])
    return {'mse':float(r.mean()),'p90_patient_rmse':float(np.quantile(np.sqrt(r),.9)),
       'fold_mse':[float(r[pf==f].mean()) for f in range(5)]}
def compare(candidate,reference,y,p,folds,names):
    c=target_risks(candidate,y,p);r=target_risks(reference,y,p);d=c.mean(1)-r.mean(1);dt=c.mean(0)-r.mean(0)
    cm,rm=metrics(candidate,y,p,folds),metrics(reference,y,p,folds)
    wins=int((d<-1e-15).sum());losses=int((d>1e-15).sum());fw=sum(a<b-1e-15 for a,b in zip(cm['fold_mse'],rm['fold_mse']))
    tail=cm['p90_patient_rmse']<=rm['p90_patient_rmse']+1e-15
    boot=d[np.random.default_rng(SEED).integers(len(d),size=(100000,len(d)))].mean(1)
    return {'relative_mse_gain':1-cm['mse']/rm['mse'],'patient_wins':wins,'patient_losses':losses,'fold_wins':fw,
       'p90_nonworse':bool(tail),'target_wins':int((dt<-1e-15).sum()),
       'regressing_targets':[str(names[j]) for j in range(24) if dt[j]>1e-15],
       'descriptive_bootstrap_95_ci':np.quantile(boot,[.025,.975]).tolist(),
       'gate_pass':bool(cm['mse']<rm['mse']-1e-15 and wins>=30 and fw==5 and tail)}

def metadata(curves,full,catalog):
    dose_sets={str(t):set() for t in catalog.target_ids}
    with Path(curves).open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):dose_sets[row['drug_id']].add(float(row['dose_nM']))
    records=[]
    for j,target in enumerate(catalog.target_ids):
        columns=np.flatnonzero(full['owner']==j);doses=np.asarray(sorted(dose_sets[str(target)]))
        if len(columns)!=len(doses):raise ValueError('full grid identity mismatch')
        positions=(np.log(doses)-np.log(doses[0]))/(np.log(doses[-1])-np.log(doses[0]))
        physical=np.column_stack([2*columns,2*columns+1]).ravel();q=full['q'][physical,j]
        if abs(q.sum()-1)>1e-12:raise ValueError('endpoint weights mismatch')
        records.append({'columns':columns,'positions':positions,'quadrature':q})
    return records

def fit_outer(xfit,fullfit,yfit,p,catalog,meta,folds,f,xquery):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('patient overlap')
    plan=plan_panel_fast(xfit[tr],yfit[tr],p[tr],catalog);validate_plan(plan,catalog)
    paid={o:acquire(xquery[te],plan,o) for o in ('A','B')}
    owner=np.asarray(plan['coordinate_target_indices']);native=np.asarray(plan['selected_native_indices'])
    arms={arm:np.empty((2,len(te),24)) for arm in ARMS};states=[];maxpoison=0.
    for o in ('A','B'):
        pi=np.asarray(plan[f'orientation_{o}_plate_indices']);masked=np.full((len(te),xquery.shape[1],2),np.nan)
        masked[:,native,pi]=xquery[te][:,native,pi]
        again=acquire(masked,plan,o);maxpoison=max(maxpoison,float(np.max(np.abs(again-paid[o]))))
    if maxpoison!=0.:raise ValueError('unpaid input dependence')
    for j in range(24):
        columns=meta[j]['columns'];population=fit_population(fullfit['values'][tr][:,columns,:],meta[j]['positions'],p[tr])
        positions=np.flatnonzero(owner==j);chosen_full=fullfit['query_to_full'][native[positions]]
        local_doses=np.searchsorted(columns,chosen_full)
        if not np.array_equal(columns[local_doses],chosen_full):raise ValueError('eligible dose mapping mismatch')
        state={'paid_columns':positions,'full_quadrature':meta[j]['quadrature']}
        for oi,o in enumerate(('A','B')):
            plates=np.asarray(plan[f'orientation_{o}_plate_indices'])[positions];physical=2*local_doses+plates
            state['physical_indices_'+o]=physical
            for arm in ARMS:
                fitted=condition(population,physical,meta[j]['quadrature'],arm)
                arms[arm][oi,:,j]=predict(fitted,paid[o][:,positions])
                for k,v in fitted.items():state[arm+'_'+o+'_'+k]=np.asarray(v)
        states.append(state)
    rec={'fold':f,'training_patients':len(set(p[tr])),'test_patients':len(set(p[te])),
         'training_organoids':len(tr),'treatment_wells':64,'per_plate':[32,32],'unpaid_poison_maxdiff':maxpoison}
    return arms,states,plan,rec

def check(curves,catalog,reference):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    if fr['state']!='FROZEN_BEFORE_FIRST_CANDIDATE_OUTCOME':raise ValueError('freeze state')
    for k,p in {'curves':curves,'catalog':catalog,'reference':reference}.items():
        if sha(p)!=fr['inputs'][k]:raise ValueError('input changed '+k)
    for rel,h in fr['source_sha256'].items():
        if sha(ROOT/rel)!=h:raise ValueError('source changed '+rel)
    for package,version in fr['runtime_versions'].items():
        if importlib.metadata.version(package)!=version:raise ValueError('runtime changed '+package)
    return fr

def execute(curves,catalog_path,reference_path,out):
    freeze=check(curves,catalog_path,reference_path);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'FREEZE.json'),'python':sys.version,'runtime_versions':freeze['runtime_versions']})
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny;start=time.perf_counter()
    try:
        data,features,_=load_prepared(curves,catalog_path);x,y,p=features['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=catalog_from_features(features);full=full_training_curves(curves,data,features,catalog,read_catalog(catalog_path))
        meta=metadata(curves,full,catalog);folds,_=patient_folds(p,5,'von-organoid-sentinel-v1|outer')
        with np.load(reference_path,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identity')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        if abs(metrics(retained,y,p,folds)['mse']-.001042745722096212)>1e-15 or abs(metrics(operating,y,p,folds)['mse']-.0010582750420801538)>1e-15:raise ValueError('reference metric')
        predictions={arm:np.full((2,*y.shape),np.nan) for arm in ARMS};records=[];first_states=None
        with threadpool_limits(limits=1):
            for f in range(5):
                arms,states,plan,rec=fit_outer(x,full,y,p,catalog,meta,folds,f,x)
                for arm in ARMS:predictions[arm][:,folds==f]=arms[arm]
                for j,state in enumerate(states):np.savez_compressed(out/f'fold_{f}_target_{j}_model_private.npz',**state)
                dump(out/f'fold_{f}_plan.json',plan);dump(out/f'fold_{f}_COMPLETE.json',rec);records.append(rec)
                if f==0:first_states=states
                print(json.dumps({'event':'outer_complete','fold':f,'arms_complete':list(ARMS),'seconds':time.perf_counter()-start}),flush=True)
            xx=x.copy();yy=y.copy();ff=dict(full);ff['values']=full['values'].copy()
            xx[folds==0]+=137;yy[folds==0]-=71;ff['values'][folds==0]+=211
            mutant,mutant_states,_,_=fit_outer(xx,ff,yy,p,catalog,meta,folds,0,x)
        state_difference=max(float(np.max(np.abs(first_states[j][key]-mutant_states[j][key]))) for j in range(24) for key in first_states[j])
        prediction_difference={arm:float(np.max(np.abs(predictions[arm][:,folds==0]-mutant[arm]))) for arm in ARMS}
        if state_difference>1e-12 or any(d>1e-12 for d in prediction_difference.values()) or NETWORK:raise ValueError('isolation or network check')
        if any(not np.isfinite(a).all() for a in predictions.values()):raise ValueError('incomplete predictions')
        results={}
        for arm,pred in predictions.items():
            cm=metrics(pred,y,p,folds);cr=compare(pred,retained,y,p,folds,data['drug_ids']);co=compare(pred,operating,y,p,folds,data['drug_ids'])
            results[arm]={'metrics':cm,'vs_retained64':cr,'vs_operating64':co,
                'half_error_point_and_tail_met':bool(cm['mse']<=HALF and cr['p90_nonworse']),
                'decision':'ELIGIBLE_FOR_FULL_REPLAY' if cr['gate_pass'] and co['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        np.savez_compressed(out/'predictions_private.npz',**predictions,retained64=retained,operating64=operating,
             y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.empirical_shape_mixture64.result.v1','status':'COMPLETE','primary_arm':'mixture','arms':results,
            'fold_records':records,'treatment_wells':64,'per_plate':[32,32],'half_error_target':HALF,
            'quadrature_maxdiff':full['quadrature_maxdiff'],'outer_label_curve_mutation_maxdiff':prediction_difference,
            'outer_state_mutation_maxdiff':state_difference,'network_attempts':len(NETWORK),
            'prediction_sha256':sha(out/'predictions_private.npz'),'freeze_sha256':sha(HERE/'FREEZE.json'),
            'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,
            'kaggle_entry_changed':False,'seconds':time.perf_counter()-start,'finished_utc':utc()}
        dump(out/'RESULT.json',result);print(json.dumps({'status':'COMPLETE','arms':results,'seconds':result['seconds']},indent=2),flush=True)
        return result
    except BaseException as exc:dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc(),'automatic_retry':False});raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--curves',type=Path,required=True);parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();execute(args.curves,args.catalog,args.reference,args.out)
