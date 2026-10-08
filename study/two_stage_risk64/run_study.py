#!/usr/bin/env python3
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
import argparse,csv,datetime,hashlib,importlib.util,importlib.metadata,json,socket,sys,time,traceback
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];STUDY=ROOT/'study'
spec=importlib.util.spec_from_file_location('frozen_dosepilot_helpers',STUDY/'global_conditional_curve64/run_study.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
sys.path.insert(0,str(HERE));import policy
ARMS=('static_ridge','adaptive_ridge','static_mixture','adaptive_mixture')
SEED=202610080930;NETWORK=[]
def deny(*a,**kw):NETWORK.append('blocked');raise RuntimeError('network forbidden during biological replay')

class PaidOracle:
    """One hypothetical deployment per evaluated organoid. Rejects repeat/extra reads."""
    def __init__(self,eligible_values):
        self._values=np.asarray(eligible_values,float);self.reads=[[] for _ in self._values];self.first_complete=False
    def initial(self,bank,seed):
        if self.first_complete:raise ValueError('initial measurements already purchased')
        out=np.empty((len(self._values),24,2))
        for j in range(24):
            native=bank[f't{j}_initial_native'];plates=(seed,1-seed)
            out[:,j,:]=self._values[:,native,plates]
            for row in self.reads:row.extend(zip(native.tolist(),plates))
        if not np.isfinite(out).all() or any(len(set(row))!=48 for row in self.reads):raise ValueError('invalid initial budget or value')
        self.first_complete=True;return out
    def followup(self,bank,actions,seed):
        if not self.first_complete or any(len(r)!=48 for r in self.reads):raise ValueError('follow-up before 48 initial measurements or repeated follow-up')
        policy.validate_actions(bank,actions,seed);out=np.full(actions.shape,np.nan)
        for i,row in enumerate(actions):
            for j,option in enumerate(row):
                if option:
                    pre=f't{j}_s{seed}_';native=int(bank[pre+'option_native'][option]);plate=int(bank[pre+'option_plate'][option])
                    if (native,plate) in self.reads[i]:raise ValueError('duplicate purchase')
                    self.reads[i].append((native,plate));out[i,j]=self._values[i,native,plate]
        for row in self.reads:
            if len(row)!=64 or len(set(row))!=64 or len({n for n,p in row})!=64 or [sum(p==v for n,p in row) for v in (0,1)]!=[32,32]:raise ValueError('physical budget exceeded')
        if not np.isfinite(out[actions>0]).all():raise ValueError('missing purchased follow-up response')
        return out

def metadata(curves,catalog,full):
    grids={str(t):set() for t in catalog.target_ids}
    with Path(curves).open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            if row['library_id']!='lib1' or row['drug_id'] not in grids:raise ValueError('unauthorized metadata')
            grids[row['drug_id']].add(float(row['dose_nM']))
    out=[]
    for j,t in enumerate(catalog.target_ids):
        doses=np.asarray(sorted(grids[str(t)]));assert len(doses)==sum(full['owner']==j)
        d=np.log(doses);out.append((d-d[0])/(d[-1]-d[0]))
    return out

def build_fold(x,y,p,catalog,full,positions,folds,f):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('patient overlap')
    original=g.plan_panel_fast(x[tr],y[tr],p[tr],catalog);g.validate_plan(original,catalog)
    bank=policy.build_bank(full['values'][tr],y[tr],p[tr],catalog,full['owner'],full['query_to_full'],full['q'],positions,original)
    return bank,original

def apply(bank,x_query,poison_check=True):
    outputs={a:np.full((2,len(x_query),24),np.nan) for a in ARMS};traces={};statistics={};maxpoison=0.
    for seed in (0,1):
        for adaptive,name in ((False,'static'),(True,'adaptive')):
            oracle=PaidOracle(x_query);first=oracle.initial(bank,seed)
            actions,modeled_risk=policy.choose_actions(bank,first,seed,adaptive)
            later=oracle.followup(bank,actions,seed)
            predictions={est:policy.infer(bank,first,actions,later,seed,est) for est in ('ridge','mixture')}
            for est in predictions:outputs[name+'_'+est][seed]=predictions[est]
            key=f'{name}_s{seed}'
            traces[key+'_initial']=first;traces[key+'_actions']=actions;traces[key+'_final']=later
            traces[key+'_physical_cells']=np.asarray(oracle.reads,int);traces[key+'_predicted_risk']=modeled_risk
            statistics[key]={'samples':len(actions),'wells_each':64,'first_round':48,'second_round':16,'per_plate':[32,32],
                'unique_followup_plans':len(set(tuple(row) for row in actions))}
            if poison_check:
                masked=np.full_like(x_query,np.nan)
                for i,row in enumerate(oracle.reads):
                    for native,plate in row:masked[i,native,plate]=x_query[i,native,plate]
                other=PaidOracle(masked);initial=other.initial(bank,seed);again,_=policy.choose_actions(bank,initial,seed,adaptive)
                if not np.array_equal(again,actions):raise ValueError('unbought values altered requests')
                followup=other.followup(bank,again,seed)
                for estimator in ('ridge','mixture'):
                    pp=policy.infer(bank,initial,again,followup,seed,estimator)
                    maxpoison=max(maxpoison,float(np.max(abs(pp-predictions[estimator]))))
    if maxpoison>1e-12:raise ValueError('unbought values altered predictions')
    for seed in (0,1):
        a=traces[f'adaptive_s{seed}_physical_cells'][:,48:,:];b=traces[f'static_s{seed}_physical_cells'][:,48:,:]
        counts=[]
        for ar,br in zip(a,b):counts.append(len(set(map(tuple,ar))-set(map(tuple,br))))
        statistics[f'adaptive_s{seed}']['mean_changed_followup_cells_vs_static']=float(np.mean(counts))
    return outputs,traces,statistics,maxpoison

def check(curves,catalog,reference):
    fr=json.loads((HERE/'FREEZE.json').read_text(encoding='utf-8'))
    for k,path in {'curves':curves,'catalog':catalog,'reference':reference}.items():
        if g.sha(path)!=fr['inputs'][k]:raise ValueError('input changed '+k)
    for p,h in fr['source_sha256'].items():
        if g.sha(ROOT/p)!=h:raise ValueError('source changed '+p)
    for name,version in fr['runtime_versions'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('runtime changed '+name)
    return fr

def execute(curves,catalog_path,reference,out):
    fr=check(curves,catalog_path,reference);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    g.dump(out/'STARTED.json',{'utc':g.utc(),'freeze_sha256':g.sha(HERE/'FREEZE.json'),'network_denied':True,'runtime_versions':fr['runtime_versions']})
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny;began=time.perf_counter()
    try:
        data,feat,_=g.load_prepared(curves,catalog_path);x,y,p=feat['x_replicates'],data['y'],data['patient_ids'].astype(str)
        catalog=g.catalog_from_features(feat);full=g.full_training_curves(curves,data,feat,catalog,g.read_catalog(catalog_path));pos=metadata(curves,catalog,full)
        folds,_=g.patient_folds(p,5,g.evaluate.SALT+'|outer')
        with np.load(reference,allow_pickle=False) as z:
            if not np.array_equal(z['y'],y) or not np.array_equal(z['patients'].astype(str),p) or not np.array_equal(z['folds'],folds):raise ValueError('reference identities')
            retained=z['candidate'].copy();operating=z['bandwidth07'].copy()
        if abs(g.metrics(retained,y,p,folds)['mse']-g.EXPECTED_SCI)>1e-15 or abs(g.metrics(operating,y,p,folds)['mse']-g.EXPECTED_BASE)>1e-15:raise ValueError('reference metrics')
        predictions={name:np.full((2,*y.shape),np.nan) for name in ARMS};records=[];firstbank=None;firsttraces=None
        with threadpool_limits(limits=1):
            for f in range(5):
                bank,original=build_fold(x,y,p,catalog,full,pos,folds,f);ix=np.flatnonzero(folds==f)
                pred,traces,stats,poison=apply(bank,x[ix])
                for name in ARMS:predictions[name][:,ix]=pred[name]
                np.savez_compressed(out/f'fold_{f}_bank_private.npz',**bank)
                np.savez_compressed(out/f'fold_{f}_trace_private.npz',**traces)
                g.dump(out/f'fold_{f}_original_plan.json',original)
                rec={'fold':f,'statistics':stats,'unpaid_poison_maxdiff':poison,'test_samples':len(ix),'test_patients':len(set(p[ix]))}
                records.append(rec);g.dump(out/f'fold_{f}_COMPLETE.json',rec)
                if f==0:firstbank={k:np.asarray(v).copy() for k,v in bank.items()};firsttraces={k:np.asarray(v).copy() for k,v in traces.items()}
                print(json.dumps({'event':'outer_complete','fold':f,'adaptive_plans_A':stats['adaptive_s0']['unique_followup_plans'],'elapsed_seconds':time.perf_counter()-began}),flush=True)
            altered_x=x.copy();altered_y=y.copy();altered_full=dict(full);altered_full['values']=full['values'].copy()
            altered_x[folds==0]+=71.;altered_y[folds==0]-=103.;altered_full['values'][folds==0]+=137.
            b,_=build_fold(altered_x,altered_y,p,catalog,altered_full,pos,folds,0)
            state_delta=max(float(np.max(abs(b[k]-firstbank[k]))) for k in b)
            sent,tr,_,_=apply(b,x[folds==0],False)
        prediction_delta=max(float(np.max(abs(sent[name]-predictions[name][:,folds==0]))) for name in ARMS)
        action_equal=all(np.array_equal(tr[k],firsttraces[k]) for k in tr if k.endswith('_actions'))
        if state_delta>1e-12 or prediction_delta>1e-12 or not action_equal:raise ValueError('held-out training path')
        if NETWORK or any(not np.isfinite(v).all() for v in predictions.values()):raise ValueError('network attempt or missing predictions')
        g.SEED=SEED;arms={}
        for name in ARMS:
            m=g.metrics(predictions[name],y,p,folds);vr=g.compare(predictions[name],retained,y,p,folds,data['drug_ids']);vo=g.compare(predictions[name],operating,y,p,folds,data['drug_ids'])
            arms[name]={'metrics':m,'vs_retained64':vr,'vs_operating64':vo,'half_error_numeric_target_met':bool(m['mse']<=g.HALF_TARGET and vr['p90_nonworse']),
               'numerical_gate_pass':bool(vr['gate_pass'] and vo['gate_pass']),
               'decision':'NUMERICALLY_ELIGIBLE_BUT_NEW_WORKFLOW_REQUIRES_REVIEW' if vr['gate_pass'] and vo['gate_pass'] else 'REJECT_FOR_PROMOTION'}
        direct={est:g.compare(predictions['adaptive_'+est],predictions['static_'+est],y,p,folds,data['drug_ids']) for est in ('ridge','mixture')}
        np.savez_compressed(out/'predictions_private.npz',**predictions,retained64=retained,operating64=operating,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.two_stage_risk64.result.v1','status':'COMPLETE','primary_arm':'adaptive_ridge','arms':arms,
           'adaptive_vs_matched_static':direct,'fold_records':records,'outer_label_and_curve_state_maxdiff':state_delta,
           'outer_label_and_curve_prediction_maxdiff':prediction_delta,'outer_mutation_actions_equal':action_equal,
           'treatment_wells':64,'per_plate':[32,32],'rounds':2,'round_budgets':[48,16],'new_inference_doses_added':False,
           'final_alternative_layouts_forced_complementary':False,'single_round_operational_contract_preserved':False,
           'sequential_lab_feasibility_validated':False,'same_elapsed_lab_time_claimed':False,'half_error_target':g.HALF_TARGET,
           'network_attempts':len(NETWORK),'prediction_sha256':g.sha(out/'predictions_private.npz'),'freeze_sha256':g.sha(HERE/'FREEZE.json'),
           'protected22_access':False,'independent_validation':False,'selection_adjusted':False,'automatic_promotion':False,'kaggle_entry_changed':False,
           'elapsed_seconds':time.perf_counter()-began,'finished_utc':g.utc()}
        g.dump(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k!='fold_records'},indent=2),flush=True);return result
    except BaseException as exc:g.dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':g.utc(),'automatic_retry':False});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();execute(a.curves,a.catalog,a.reference,a.out)
