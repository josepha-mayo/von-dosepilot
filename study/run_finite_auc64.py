#!/usr/bin/env python3
"""Nested fixed-budget finite AUC study. Never changes a submission."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,datetime,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_crossplate64_20261008 as core
if os.name=='nt':
    core.DATA=Path('D:/von-dosepilot-data')
    core.CURVES=core.DATA/'reconstructed_train'/'train_curves.csv'
    core.BW=core.DATA/'bandwidth_replay_pc_20261004'/'predictions_private.npz'
    core.BEST=core.DATA/'orientation_specific_control_quality_rank1_20261006_run1'/'predictions_private.npz'
from compact_train import read_catalog
from coverage_methods import catalog_from_features,validate_plan
from sparse_methods import fit_sparse_context
from full_curves import full_training_curves
from finite_auc64 import POOLING,fit_population,condition,predict,exact_paid_weights
OPTIONS=core.OPTIONS
BASES=('original','observed_anchor','smooth_local','smooth_halfpool','smooth_pool')
ARMS=BASES+('nested_primary',)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def freeze():
    sources=[HERE/n for n in ('run_finite_auc64.py','finite_auc64.py','test_finite_auc64.py','FINITE_AUC64_PROTOCOL.md','run_crossplate64_20261008.py','compact_train.py','conditional.py','full_curves.py')]
    for name in ('engine','hybrid_residual','acceleration'):sources+=sorted((HERE/name).glob('*.py'))
    dump(HERE/'FINITE_AUC64_FREEZE.json',{'state':'FROZEN_BEFORE_BIOLOGICAL_FIT','utc':utc(),'source':{str(p.relative_to(HERE)):sha(p) for p in sources},'inputs':{str(p):sha(p) for p in (core.CURVES,core.CATALOG,core.BW,core.BEST)}})
def check():
    f=json.loads((HERE/'FINITE_AUC64_FREEZE.json').read_text())
    if f['state']!='FROZEN_BEFORE_BIOLOGICAL_FIT':raise ValueError('unfrozen')
    for p,h in f['source'].items():
        if sha(HERE/p)!=h:raise ValueError('source changed '+p)
    for p,h in f['inputs'].items():
        if sha(p)!=h:raise ValueError('input changed '+p)

def fit_bundle(x,y,p,catalog,full,ix):
    plan=core.plan_panel_fast(x[ix],y[ix],p[ix],catalog);validate_plan(plan,catalog)
    a,b=core.paid(x[ix],plan,'A'),core.paid(x[ix],plan,'B')
    xx=np.r_[a,b];yy=np.r_[y[ix],y[ix]];pp=np.r_[p[ix],p[ix]]
    ctx=fit_sparse_context(xx,yy,pp,plan['selected_native_ids'],catalog.target_ids)
    original=core.Ridge(ctx,plan,.01)
    raw_beta=original.beta/original.scale_x[:,None]
    raw_int=original.mean_y-original.mean_x@raw_beta
    old={o:{'beta_raw':raw_beta,'intercept':raw_int} for o in ('A','B')}
    known=exact_paid_weights(plan,full,'A')
    if not np.array_equal(known,exact_paid_weights(plan,full,'B')):raise ValueError('endpoint plate symmetry')
    anchor_ctx=fit_sparse_context(xx,yy-xx@known,pp,plan['selected_native_ids'],catalog.target_ids)
    anchor=core.Ridge(anchor_ctx,plan,.01)
    extra=anchor.beta/anchor.scale_x[:,None]
    anchored={o:{'beta_raw':extra+known,'intercept':anchor.mean_y-anchor.mean_x@extra} for o in ('A','B')}
    local_full=dict(full);local_full['values']=full['values'][ix]
    population=fit_population(local_full,p[ix])
    states=[old,anchored]+[condition(population,plan,full,v) for v in POOLING]
    z=(xx-original.mean_x)/original.scale_x
    w=np.tile(core.patient_weights(p[ix]),2)/(2*len(np.unique(p[ix])))
    variants=[]
    for state in states:
        res=np.r_[y[ix]-predict(state,a,'A'),y[ix]-predict(state,b,'B')]
        kernel=core.BandwidthAdditive(z,res,w,np.asarray(plan['coordinate_target_indices'],int),.7)
        coefs=[np.zeros_like(res)]+[kernel.coefficients(l,f)[0] for f,l in OPTIONS[1:]]
        variants.append({'state':state,'kernel':kernel,'coef':coefs})
    return {'plan':plan,'original':original,'variants':variants,'covariance_coefficients':[(s['local_coef'].tolist(),s['pooled_coef'].tolist()) for s in population]}

def predict_all(x,bundle):
    out=np.empty((50,2,len(x),24));plan=bundle['plan'];original=bundle['original']
    for oi,o in enumerate(('A','B')):
        paid=core.paid(x,plan,o);z=(paid-original.mean_x)/original.scale_x
        for j,v in enumerate(bundle['variants']):
            bp=predict(v['state'],paid,o);K=v['kernel'].centered_cross(z)
            for k,c in enumerate(v['coef']):out[10*j+k,oi]=bp+K@c
    if not np.isfinite(out).all():raise ValueError('prediction values')
    return out

def payload(bundle,index):
    j,k=divmod(index,10);v=bundle['variants'][j];kernel=v['kernel'];base=bundle['original'];plan=bundle['plan']
    s={'mean_x':base.mean_x,'scale_x':base.scale_x,'z':kernel.z,'owner':kernel.owner,'weights':kernel.w,'kernel_mean':kernel.train_mean,'grand':np.asarray(kernel.grand),'coef':v['coef'][k],'native':np.asarray(plan['selected_native_indices'],int),'plate_A':np.asarray(plan['orientation_A_plate_indices'],int),'plate_B':np.asarray(plan['orientation_B_plate_indices'],int)}
    for o in ('A','B'):
        s['beta_raw_'+o]=v['state'][o]['beta_raw'];s['intercept_'+o]=v['state'][o]['intercept']
    return s

def replay(s,paid,o):
    paid=np.asarray(paid,float)
    if o not in ('A','B') or paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():raise ValueError('64 finite purchased inputs only')
    z=(paid-s['mean_x'])/s['scale_x'];t=s['z'];raw=z@t.T
    for j in range(24):
        idx=np.flatnonzero(s['owner']==j);a=z[:,idx];b=t[:,idx]
        distance=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0.)
        raw+=len(idx)*np.exp(-distance/(2*len(idx)*.7**2))
    K=raw-(raw@s['weights'])[:,None]-s['kernel_mean'][None,:]+s['grand']
    return s['intercept_'+o]+paid@s['beta_raw_'+o]+K@s['coef']

def outer(x,y,p,catalog,full,folds,f,query):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer overlap')
    inner,_=core.patient_folds(p[tr],3,core.evaluate.SALT+f'|inner|{f}')
    oof=np.full((50,2,len(tr),24),np.nan)
    for k in range(3):
        fi=tr[inner!=k];vi=tr[inner==k]
        if set(p[fi])&set(p[vi]):raise ValueError('inner overlap')
        oof[:,:,inner==k]=predict_all(x[vi],fit_bundle(x,y,p,catalog,full,fi))
    if not np.isfinite(oof).all():raise ValueError('incomplete inner OOF')
    scores=[core.metric(q,y[tr],p[tr],inner)[0]['mse'] for q in oof]
    selected={name:10*j+int(np.argmin(scores[10*j:10*j+10])) for j,name in enumerate(BASES)}
    selected['nested_primary']=int(np.argmin(scores))
    bundle=fit_bundle(x,y,p,catalog,full,tr);allpred=predict_all(query[te],bundle)
    preds={name:allpred[index] for name,index in selected.items()};states={name:payload(bundle,index) for name,index in selected.items()}
    maxdiff=0.;isolation=0.;plan=bundle['plan']
    for name in ARMS:
        for oi,o in enumerate(('A','B')):
            paid=core.paid(query[te],plan,o);restored=replay(states[name],paid,o)
            maxdiff=max(maxdiff,float(np.max(abs(restored-preds[name][oi]))))
            masked=np.full_like(query[te],np.nan);masked[:,states[name]['native'],states[name]['plate_'+o]]=paid
            isolation=max(isolation,float(np.max(abs(replay(states[name],core.paid(masked,plan,o),o)-restored))))
    if maxdiff>1e-12 or isolation>1e-12:raise ValueError('saved replay or paid isolation')
    rec={'fold':f,'selected':selected,'primary_base':BASES[selected['nested_primary']//10],'scores':scores,'replay_maxdiff':maxdiff,'unpaid_isolation_maxdiff':isolation,'training_patients':sorted(set(p[tr])),'test_patients':sorted(set(p[te])),'covariance_coefficients':bundle['covariance_coefficients']}
    return preds,states,plan,rec

def execute(out):
    check();out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    dump(out/'STARTED.json',{'utc':utc(),'python':sys.version,'numpy':np.__version__})
    try:
        data,feat,_=core.load_prepared(core.CURVES,core.CATALOG)
        x=feat['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);cat=catalog_from_features(feat)
        full=full_training_curves(core.CURVES,data,feat,cat,read_catalog(core.CATALOG))
        if full['full_physical_cells']!=416 or full['eligible_physical_cells']!=328:raise ValueError('source/candidate catalog mismatch')
        folds,_=core.patient_folds(p,5,core.evaluate.SALT+'|outer')
        rz=np.load(core.BW,allow_pickle=False);bz=np.load(core.BEST,allow_pickle=False)
        for ref in (rz,bz):
            if not np.array_equal(ref['y'],y) or not np.array_equal(ref['patients'].astype(str),p) or not np.array_equal(ref['folds'],folds):raise ValueError('reference identity')
        pred={a:np.full((2,len(y),24),np.nan) for a in ARMS};records=[];state0=None
        for f in range(5):
            guesses,states,plan,record=outer(x,y,p,cat,full,folds,f,x);te=folds==f
            for name in ARMS:
                pred[name][:,te]=guesses[name];np.savez_compressed(out/f'fold_{f}_{name}_model.npz',**states[name])
            np.savez_compressed(out/f'fold_{f}_paid.npz',A=core.paid(x[te],plan,'A'),B=core.paid(x[te],plan,'B'),indices=np.flatnonzero(te))
            dump(out/f'fold_{f}_plan.json',plan);dump(out/f'fold_{f}_record.json',record);records.append(record)
            if f==0:state0=states
            print(json.dumps({'fold_finished':f,'selected':{name:OPTIONS[index%10] for name,index in record['selected'].items()},'primary':record['primary_base']}),flush=True)
        changed_x=x.copy();changed_y=y.copy();changed_full=dict(full);changed_full['values']=full['values'].copy()
        changed_x[folds==0]+=55.;changed_y[folds==0]-=93.;changed_full['values'][folds==0]-=173.
        mutated,states,_,rec=outer(changed_x,changed_y,p,cat,changed_full,folds,0,x)
        mutation=max(float(np.max(abs(mutated[a]-pred[a][:,folds==0]))) for a in ARMS)
        state_diff=max(float(np.max(abs(states[a][k]-state0[a][k]))) for a in ARMS for k in states[a])
        if mutation>1e-12 or state_diff>1e-12 or rec['selected']!=records[0]['selected']:raise ValueError('outer-label dependency')
        control=float(np.max(abs(pred['original']-rz['bandwidth07'])))
        if control>1e-12:raise ValueError('original pipeline mismatch '+str(control))
        op=core.metric(rz['bandwidth07'],y,p,folds);best=core.metric(bz['candidate'],y,p,folds)
        if abs(op[0]['mse']-core.EXPECTED_BW)>1e-13 or abs(best[0]['mse']-core.EXPECTED_BEST)>1e-13:raise ValueError('comparator metrics')
        results={}
        for a in ARMS:
            if not np.isfinite(pred[a]).all():raise ValueError('incomplete predictions')
            m=core.metric(pred[a],y,p,folds);vs=core.compare(m,best);vo=core.compare(m,op)
            gate=lambda v:v['relative_gain']>0 and v['patient_wins']>=30 and v['fold_wins']==5 and v['p90_nonworse']
            results[a]={'metrics':m[0],'vs_best':vs,'vs_operating':vo,'gate':bool(a!='original' and gate(vs) and gate(vo)),'two_x':bool(m[0]['mse']<=core.TWOX and m[0]['p90']<=best[0]['p90'])}
        np.savez_compressed(out/'predictions_private.npz',**pred,y=y,patients=p,folds=folds,sample_ids=data['sample_ids'],drug_ids=data['drug_ids'],operating64=rz['bandwidth07'],best64=bz['candidate'])
        result={'schema':'dosepilot.finite_auc64.result.v1','status':'COMPLETE','role':'REPEATED_ADAPTIVE_DEVELOPMENT','primary_arm':'nested_primary','arms':results,'control_maxdiff':control,'outer_mutation_maxdiff':mutation,'outer_state_maxdiff':state_diff,'quadrature_maxdiff':full['quadrature_maxdiff'],'physical_wells':64,'distinct_native_doses':64,'per_plate':[32,32],'target_mse_2x':core.TWOX,'no_protected22':True,'independent_validation':False,'submission_changed':False,'freeze_sha256':sha(HERE/'FINITE_AUC64_FREEZE.json'),'prediction_sha256':sha(out/'predictions_private.npz'),'seconds':time.monotonic()-start,'finished_utc':utc()}
        dump(out/'RESULT.json',result)
        print(json.dumps({a:{'mse':v['metrics']['mse'],'p90':v['metrics']['p90'],'gain_vs_best':v['vs_best']['relative_gain'],'patient_wins':v['vs_best']['patient_wins'],'fold_wins':v['vs_best']['fold_wins'],'gate':v['gate'],'two_x':v['two_x']} for a,v in results.items()},indent=2),flush=True)
    except BaseException as e:
        dump(out/'FAILURE.json',{'error':repr(e),'utc':utc(),'traceback':traceback.format_exc()});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--out',type=Path);args=ap.parse_args()
    if args.freeze:freeze()
    elif args.out:execute(args.out)
    else:ap.error('use --freeze or --out')
