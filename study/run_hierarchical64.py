#!/usr/bin/env python3
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,datetime,hashlib,json,sys,traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE))
import run_crossplate64_20261008 as core
from compact_train import read_catalog
from coverage_methods import catalog_from_features,validate_plan
from sparse_methods import fit_sparse_context
from full_curves import full_training_curves
from hierarchical64 import CONFIGS,fit_populations,condition_population,predict as conditional_predict
OPTIONS=core.OPTIONS
BASES=['own_drug']+[f'm{m}_d{d}_cross{g}' for m,d,g in CONFIGS]
ARMS=BASES+['nested_primary']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')

def check_freeze():
    fr=json.loads((HERE/'HIERARCHICAL64_FREEZE.json').read_text())
    if fr['state']!='FROZEN_BEFORE_FIRST_CANDIDATE_FIT':raise ValueError('freeze state')
    for p,h in fr['inputs'].items():
        if sha(Path(p))!=h:raise ValueError('input hash changed '+p)
    for p,h in fr['source'].items():
        if sha(ROOT/p)!=h:raise ValueError('source hash changed '+p)
    return fr

def fit_bundle(x,y,p,catalog,full,indices):
    ix=np.asarray(indices,int)
    plan=core.plan_panel_fast(x[ix],y[ix],p[ix],catalog);validate_plan(plan,catalog)
    a,b=core.paid(x[ix],plan,'A'),core.paid(x[ix],plan,'B')
    px=np.r_[a,b];py=np.r_[y[ix],y[ix]];pp=np.r_[p[ix],p[ix]]
    ctx=fit_sparse_context(px,py,pp,plan['selected_native_ids'],catalog.target_ids)
    base=core.Ridge(ctx,plan,.01);z=(px-base.mean_x)/base.scale_x
    w=np.tile(core.patient_weights(p[ix]),2)/(2*len(np.unique(p[ix])))
    populations=fit_populations(full['values'][ix],p[ix],full['owner'])
    states=[None]+[condition_population(pop,plan,full['q'],full['query_to_full']) for pop in populations]
    variants=[]
    for state in states:
        pa=base.predict(a) if state is None else conditional_predict(state,a,'A')
        pb=base.predict(b) if state is None else conditional_predict(state,b,'B')
        res=np.r_[y[ix]-pa,y[ix]-pb]
        kernel=core.BandwidthAdditive(z,res,w,np.asarray(plan['coordinate_target_indices'],int),.7)
        coefs=[np.zeros_like(res)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
        variants.append({'state':state,'kernel':kernel,'coefs':coefs})
    return {'plan':plan,'base':base,'variants':variants}

def predict_all(query_x,bundle):
    plan,base=bundle['plan'],bundle['base'];out=np.empty((70,2,len(query_x),24))
    for oi,o in enumerate(('A','B')):
        paid=core.paid(query_x,plan,o);zq=(paid-base.mean_x)/base.scale_x
        for j,v in enumerate(bundle['variants']):
            bp=base.predict(paid) if v['state'] is None else conditional_predict(v['state'],paid,o)
            cross=v['kernel'].centered_cross(zq)
            for k,coef in enumerate(v['coefs']):out[10*j+k,oi]=bp+cross@coef
    if not np.isfinite(out).all():raise ValueError('nonfinite predictions')
    return out

def state_payload(bundle,index):
    j,k=divmod(int(index),10);v=bundle['variants'][j];base=bundle['base'];kernel=v['kernel'];plan=bundle['plan']
    state={'canonical_mean':base.mean_x,'canonical_scale':base.scale_x,
        'kernel_z':kernel.z,'kernel_owner':kernel.owner,'kernel_weights':kernel.w,
        'kernel_mean':kernel.train_mean,'kernel_grand':np.asarray(kernel.grand),'coef':v['coefs'][k],
        'native_indices':np.asarray(plan['selected_native_indices'],int),
        'plate_A':np.asarray(plan['orientation_A_plate_indices'],int),
        'plate_B':np.asarray(plan['orientation_B_plate_indices'],int)}
    for o in ('A','B'):
        if v['state'] is None:
            parts={'mean_x':base.mean_x,'scale_x':base.scale_x,'mean_y':base.mean_y,'beta':base.beta}
        else:
            parts=dict(v['state']['orientations'][o]);parts['mean_y']=v['state']['mean_y']
        for key,value in parts.items():state[key+'_'+o]=np.asarray(value)
    return state

def predict_payload(state,paid,o):
    paid=np.asarray(paid,float)
    if o not in ('A','B') or paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():raise ValueError('64 finite paid values only')
    base=state['mean_y_'+o]+((paid-state['mean_x_'+o])/state['scale_x_'+o])@state['beta_'+o]
    q=(paid-state['canonical_mean'])/state['canonical_scale'];z=state['kernel_z'];raw=q@z.T
    for j in range(24):
        ix=np.flatnonzero(state['kernel_owner']==j);a,b=q[:,ix],z[:,ix]
        distance=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
        raw+=len(ix)*np.exp(-distance/(2*len(ix)*.7**2))
    centered=raw-(raw@state['kernel_weights'])[:,None]-state['kernel_mean'][None,:]+state['kernel_grand']
    return base+centered@state['coef']

def outer_fold(x,y,p,catalog,full,folds,f,query_x):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=core.patient_folds(p[tr],3,core.evaluate.SALT+f'|inner|{f}')
    inner_predictions=np.full((70,2,len(tr),24),np.nan)
    for g in range(3):
        fit=tr[inner!=g];val=tr[inner==g]
        if set(p[fit])&set(p[val]):raise ValueError('inner patient overlap')
        predictions=predict_all(x[val],fit_bundle(x,y,p,catalog,full,fit))
        inner_predictions[:,:,inner==g,:]=predictions
    if not np.isfinite(inner_predictions).all():raise ValueError('incomplete inner predictions')
    scores=[core.metric(pred,y[tr],p[tr],inner)[0]['mse'] for pred in inner_predictions]
    selected={name:10*j+int(np.argmin(scores[10*j:10*(j+1)])) for j,name in enumerate(BASES)}
    selected['nested_primary']=int(np.argmin(scores))
    bundle=fit_bundle(x,y,p,catalog,full,tr);raw=predict_all(query_x[te],bundle)
    states={name:state_payload(bundle,index) for name,index in selected.items()}
    output={name:raw[index] for name,index in selected.items()}
    plan=bundle['plan'];maxdiff=0.;unpaid_diff=0.
    for oidx,o in enumerate(('A','B')):
        paid=core.paid(query_x[te],plan,o)
        masked=np.full_like(query_x[te],np.nan)
        native=np.asarray(plan['selected_native_indices'],int);plate=np.asarray(plan[f'orientation_{o}_plate_indices'],int)
        masked[:,native,plate]=paid
        for name in ARMS:
            replay=predict_payload(states[name],paid,o)
            maxdiff=max(maxdiff,float(np.max(abs(replay-output[name][oidx]))))
            unpaid_diff=max(unpaid_diff,float(np.max(abs(predict_payload(states[name],core.paid(masked,plan,o),o)-replay))))
    if maxdiff>1e-12 or unpaid_diff>1e-12:raise ValueError('replay/input isolation failed')
    record={'fold':f,'selected':selected,'selected_primary_base':BASES[selected['nested_primary']//10],
        'inner_mse':scores,'state_replay_maxdiff':maxdiff,'unpaid_values_maxdiff':unpaid_diff,
        'training_patients':len(set(p[tr])),'test_patients':len(set(p[te]))}
    return output,record,states,plan

def execute(out):
    fr=check_freeze();out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'freeze_sha256':sha(HERE/'HIERARCHICAL64_FREEZE.json'),'python':sys.version,'numpy':np.__version__})
    try:
        data,feat,_=core.load_prepared(core.CURVES,core.CATALOG)
        x=feat['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);catalog=catalog_from_features(feat)
        full=full_training_curves(core.CURVES,data,feat,catalog,read_catalog(core.CATALOG))
        if full['full_physical_cells']!=416 or full['eligible_physical_cells']!=328:raise ValueError('historical/query catalog sizes')
        folds,_=core.patient_folds(p,5,core.evaluate.SALT+'|outer')
        rz=np.load(core.BW,allow_pickle=False);bz=np.load(core.BEST,allow_pickle=False)
        for ref in (rz,bz):
            if not np.array_equal(ref['y'],y) or not np.array_equal(ref['patients'].astype(str),p) or not np.array_equal(ref['folds'],folds):raise ValueError('reference identity')
        baseline=rz['bandwidth07'];scientific=bz['candidate']
        bm=core.metric(baseline,y,p,folds);sm=core.metric(scientific,y,p,folds)
        if abs(bm[0]['mse']-core.EXPECTED_BW)>1e-13 or abs(sm[0]['mse']-core.EXPECTED_BEST)>1e-13:raise ValueError('control scores')
        predictions={name:np.full((2,len(y),24),np.nan) for name in ARMS};records=[];state0=None
        for f in range(5):
            result,record,states,plan=outer_fold(x,y,p,catalog,full,folds,f,x)
            records.append(record);dump(out/f'fold_{f}_record.json',record);dump(out/f'fold_{f}_plan.json',plan)
            te=folds==f
            for name in ARMS:
                predictions[name][:,te]=result[name]
                np.savez_compressed(out/f'fold_{f}_{name}_model.npz',**states[name])
            np.savez_compressed(out/f'fold_{f}_paid.npz',paid_A=core.paid(x[te],plan,'A'),paid_B=core.paid(x[te],plan,'B'),indices=np.flatnonzero(te))
            if f==0:state0=states
            print(json.dumps({'fold_complete':f,'primary_base':record['selected_primary_base']}),flush=True)
        changed_x=x.copy();changed_y=y.copy();changed_full=dict(full)
        changed_full['values']=full['values'].copy()
        changed_x[folds==0]+=123.;changed_y[folds==0]+=71.
        changed_full['values'][folds==0]-=57.
        altered,ar,ast,_=outer_fold(changed_x,changed_y,p,catalog,changed_full,folds,0,x)
        mutation=max(float(np.max(abs(altered[name]-predictions[name][:,folds==0]))) for name in ARMS)
        state_diff=max(float(np.max(abs(ast[name][k]-state0[name][k]))) for name in ARMS for k in state0[name])
        if mutation>1e-12 or state_diff>1e-12 or ar['selected']!=records[0]['selected']:raise ValueError('outer-label dependency')
        control=float(np.max(abs(predictions['own_drug']-baseline)))
        if control>1e-12:raise ValueError('original pipeline reproduction failed')
        results={}
        for name in ARMS:
            if not np.isfinite(predictions[name]).all():raise ValueError('incomplete final predictions')
            met=core.metric(predictions[name],y,p,folds);vsb=core.compare(met,bm);vss=core.compare(met,sm)
            gate=lambda v:bool(v['relative_gain']>0 and v['patient_wins']>=30 and v['fold_wins']==5 and v['p90_nonworse'])
            results[name]={'metrics':met[0],'vs_operating':vsb,'vs_scientific':vss,
                'two_x':bool(met[0]['mse']<=core.TWOX and met[0]['p90']<=sm[0]['p90']),
                'numeric_gate':bool(name!='own_drug' and gate(vsb) and gate(vss))}
        np.savez_compressed(out/'predictions_private.npz',y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'],operating64=baseline,scientific64=scientific,**predictions)
        result={'schema':'dosepilot.hierarchical64.result.v1','status':'COMPLETE','role':'REPEATED_ADAPTIVE_TRAIN_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION',
            'arms':results,'primary_arm':'nested_primary','target_mse_2x':core.TWOX,'physical_wells':64,'distinct_native_doses':64,'per_plate':[32,32],
            'outer_label_mutation_maxdiff':mutation,'outer_state_mutation_maxdiff':state_diff,'original_control_maxdiff':control,
            'quadrature_maxdiff':full['quadrature_maxdiff'],'fold_records':records,
            'independent_validation':False,'protected22_access':False,'official_score':None,'submission_changed':False,
            'freeze_sha256':sha(HERE/'HIERARCHICAL64_FREEZE.json'),'prediction_sha256':sha(out/'predictions_private.npz'),'finished_utc':utc()}
        dump(out/'RESULT.json',result)
        print(json.dumps({name:{'mse':v['metrics']['mse'],'p90':v['metrics']['p90'],'gain':v['vs_scientific']['relative_gain'],'folds':v['vs_scientific']['fold_wins'],'patients':v['vs_scientific']['patient_wins'],'two_x':v['two_x'],'gate':v['numeric_gate']} for name,v in results.items()},indent=2),flush=True)
    except BaseException as exc:
        dump(out/'FAILURE.json',{'error':repr(exc),'traceback':traceback.format_exc(),'utc':utc()});raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);a=parser.parse_args();execute(a.out)
