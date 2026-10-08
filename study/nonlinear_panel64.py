#!/usr/bin/env python3
"""Nonlinear predictor-aware discrete acquisition. Research only; never submits."""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import argparse,copy,hashlib,json,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_crossplate64_20261008 as core
if os.name == 'nt':
    core.DATA=Path('D:/von-dosepilot-data')
    core.CURVES=core.DATA/'reconstructed_train'/'train_curves.csv'
    core.BW=core.DATA/'bandwidth_replay_pc_20261004'/'predictions_private.npz'
    core.BEST=core.DATA/'orientation_specific_control_quality_rank1_20261006_run1'/'predictions_private.npz'
from coverage_methods import catalog_from_features,validate_plan
from sparse_methods import fit_sparse_context
ARMS=('original','nonlinear_panel')
OPTIONS=core.OPTIONS
MIN_GAIN=1e-8
PROTOCOL='''# Nonlinear predictor-aware 64-well panel search
Frozen specification, 8 October 2026. Objective: MSE <=0.000521372861048106 and p90 <=0.037419695944064885. Same 64 distinct native doses, 32 physical wells per plate, 119 samples, 59 whole patients and 24 original AUCs. Retained scientific MSE 0.001042745722096212.
Previous patient-deleted acquisition optimized linear own-drug risk; previous global acquisition optimized a linear covariance proxy. This study instead evaluates alternative panels using the actual own-drug ridge plus bandwidth0.7 nonlinear spectral predictor.
Start from the fitting-only R13 64-well plan. Keep target cardinalities and plate positions. In lexicographic target order, consider the current subset plus two best alternative subsets of that cardinality under the original fitting-only moment proxy. Score each WHOLE panel with three deterministic patient planning splits and the actual predictor: own-drug ridge0.01, bandwidth0.7, spectral fraction0.1, kernel ridge1.0. Accept a change only for planning MSE reduction >1e-8. One forward sweep. No extra rounds or post-outcome tuning.
The shortlist uses all patients supplied to its planning call. Planning CV is a selection objective, not an unbiased estimate. The complete planner is rebuilt on each actual fitting partition. Five unchanged outer patient folds; three inner patient folds choose one of the original ten global spectral options per arm. Each inner fit runs its own three-way planning selection using only its fitting patients. Final inference uses only one chosen 64-well panel. A/B are alternatives: average squared losses, NEVER predictions or measurements across layouts.
Arms: original planner with nonlinear prediction (numeric control), nonlinear-aware planner with identical prediction (primary). No fallback or target splicing. Compare vs operating0.0010582750420801538 and scientific0.001042745722096212. Promotion needs lower mean, >=30 patient wins, 5/5 favorable folds, nonworse p90 vs BOTH. Half-error also needs the absolute threshold. All results are repeated adaptive development, not independent biological validation.
Freeze code/dependencies/input hashes before biological fitting. Test synthetic accounting and saved model replay. Save outer plans, numeric models, membership and purchased query values. Independently replay final predictions and test unpurchased-input invariance. Rebuild outerfold0 after changing all its excluded values/labels and require the same selected models and predictions. No Protected22/Lib2, expanded query catalog, external responses, extra measurements, public raw-data upload or automatic submission. Preserve original accepted entry.
Reference: https://scikit-learn.org/stable/modules/cross_validation.html . Established nested selection principles, not a new theorem or guarantee of global optimality.
'''

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def dump(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def risk(pred,y,p):
    loss=((pred[0]-y)**2+(pred[1]-y)**2)/2
    return float(np.mean([loss[p==g].mean() for g in np.unique(p)]))

def fit_model(x,y,p,plan,options=OPTIONS):
    a,b=core.paid(x,plan,'A'),core.paid(x,plan,'B')
    xx=np.r_[a,b]; yy=np.r_[y,y]; pp=np.r_[p,p]
    ctx=fit_sparse_context(xx,yy,pp,plan['selected_native_ids'],np.arange(24).astype(str))
    base=core.Ridge(ctx,plan,.01)
    z=(xx-base.mean_x)/base.scale_x
    residual=yy-base.predict(xx)
    weights=np.tile(core.patient_weights(p),2)/(2*len(np.unique(p)))
    kernel=core.BandwidthAdditive(z,residual,weights,np.asarray(plan['coordinate_target_indices'],int),.7)
    coefs=[np.zeros_like(residual) if f=='identity' else kernel.coefficients(l,f)[0] for f,l in options]
    return plan,base,kernel,coefs

def predict_options(x,model):return core.predict_options(x,model) if len(model[3])==10 else predict_single(x,model)[None]
def predict_single(x,model):
    plan,base,kernel,coefs=model
    return np.stack([base.predict(core.paid(x,plan,o))+kernel.centered_cross((core.paid(x,plan,o)-base.mean_x)/base.scale_x)@coefs[0] for o in ('A','B')])

def replan(plan,target,subset,catalog):
    out=copy.deepcopy(plan);own=np.asarray(plan['coordinate_target_indices'],int)
    indices=np.asarray(plan['selected_native_indices'],int).copy()
    pos=np.flatnonzero(own==target)
    if len(pos)!=len(subset):raise ValueError('cardinality changed')
    indices[pos]=subset
    out['selected_native_indices']=indices.tolist()
    out['selected_native_ids']=[str(catalog.native_ids[v]) for v in indices]
    out['selected_concentrations_nM']=[str(catalog.concentrations[v]) for v in indices]
    validate_plan(out,catalog)
    return out

def score_plan(x,y,p,plan,folds):
    prediction=np.full((2,len(y),24),np.nan)
    for f in range(3):
        tr=folds!=f;va=~tr
        if set(p[tr])&set(p[va]):raise ValueError('planning overlap')
        model=fit_model(x[tr],y[tr],p[tr],plan,[(.1,1.0)])
        prediction[:,va]=predict_single(x[va],model)
    if not np.isfinite(prediction).all():raise ValueError('planning incomplete')
    return risk(prediction,y,p)

def optimize(x,y,p,catalog,start):
    folds,_=core.patient_folds(p,3,'dosepilot.nonlinear_panel.v1|planning')
    cache={}
    def score(plan):
        key=tuple(plan['selected_native_indices'])
        if key not in cache:cache[key]=score_plan(x,y,p,plan,folds)
        return cache[key]
    plan=copy.deepcopy(start);initial=score(plan);current=initial;trace=[]
    for target in sorted(range(24),key=lambda j:str(catalog.target_ids[j])):
        positions=np.flatnonzero(np.asarray(plan['coordinate_target_indices'])==target)
        current_subset=tuple(np.asarray(plan['selected_native_indices'])[positions].tolist())
        rows=[r for r in start['all_subset_scores'] if r['target_index']==target and r['size']==len(positions) and tuple(r['native_indices'])!=current_subset]
        rows.sort(key=lambda r:(r['residual_proxy'],tuple(r['native_ids'])))
        candidates=[plan]+[replan(plan,target,r['native_indices'],catalog) for r in rows[:2]]
        scores=[score(c) for c in candidates]
        choice=int(np.argmin(scores))
        if scores[0]-scores[choice]<=MIN_GAIN:choice=0
        if scores[choice]>current+1e-12:raise ValueError('nonmonotonic selection objective')
        trace.append({'target':str(catalog.target_ids[target]),'scores':scores,'chosen':choice,'candidate_subsets':[np.asarray(c['selected_native_indices'])[positions].tolist() for c in candidates]})
        plan=candidates[choice];current=scores[choice]
    for name in ('choices','all_subset_scores'):
        if name in plan:plan['starting_r13_'+name]=plan.pop(name)
    plan['acquisition_kind']='nonlinear_patient_cv_one_sweep'
    plan['nonlinear_selection']={'initial':initial,'final':current,'panels_scored':len(cache),'predictor_fits':len(cache)*3,'changed_targets':sum(t['chosen']!=0 for t in trace),'trace':trace}
    validate_plan(plan,catalog)
    return plan

def build(x,y,p,catalog):
    start=core.plan_panel_fast(x,y,p,catalog)
    changed=optimize(x,y,p,catalog,start)
    return {'original':fit_model(x,y,p,start),'nonlinear_panel':fit_model(x,y,p,changed)}

def payload(model,index):
    plan,b,k,coefs=model
    return {'mean_x':b.mean_x,'scale_x':b.scale_x,'mean_y':b.mean_y,'beta':b.beta,'z':k.z,'owner':k.owner,'weights':k.w,'kernel_mean':k.train_mean,'grand':np.asarray(k.grand),'coef':coefs[index],'native':np.asarray(plan['selected_native_indices'],int),'plate_A':np.asarray(plan['orientation_A_plate_indices'],int),'plate_B':np.asarray(plan['orientation_B_plate_indices'],int)}

def replay(s,paid):
    paid=np.asarray(paid,float)
    if paid.ndim!=2 or paid.shape[1]!=64 or not np.isfinite(paid).all():raise ValueError('64 finite paid values required')
    z=(paid-s['mean_x'])/s['scale_x'];t=s['z'];raw=z@t.T
    for j in range(24):
        ix=np.flatnonzero(s['owner']==j);a=z[:,ix];b=t[:,ix]
        dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0)
        raw+=len(ix)*np.exp(-dist/(2*len(ix)*.7**2))
    centered=raw-(raw@s['weights'])[:,None]-s['kernel_mean'][None,:]+s['grand']
    return s['mean_y']+z@s['beta']+centered@s['coef']

def outer(x,y,p,catalog,folds,f,query_x):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=core.patient_folds(p[tr],3,core.evaluate.SALT+f'|inner|{f}')
    oof={a:np.full((10,2,len(tr),24),np.nan) for a in ARMS}
    for k in range(3):
        fi=tr[inner!=k];vi=tr[inner==k]
        if set(p[fi])&set(p[vi]):raise ValueError('inner patient overlap')
        models=build(x[fi],y[fi],p[fi],catalog)
        for a in ARMS:oof[a][:,:,inner==k]=predict_options(x[vi],models[a])
        print(json.dumps({'event':'inner_finished','outer':f,'inner':k}),flush=True)
    scores={a:[risk(q,y[tr],p[tr]) for q in oof[a]] for a in ARMS}
    selected={a:int(np.argmin(scores[a])) for a in ARMS}
    models=build(x[tr],y[tr],p[tr],catalog)
    predictions={a:predict_options(query_x[te],models[a])[selected[a]] for a in ARMS}
    states={a:payload(models[a],selected[a]) for a in ARMS}
    maxdiff=0.;unpaid=0.
    for a in ARMS:
        plan=models[a][0]
        for oi,o in enumerate(('A','B')):
            purchased=core.paid(query_x[te],plan,o)
            q=replay(states[a],purchased)
            maxdiff=max(maxdiff,float(np.max(abs(q-predictions[a][oi]))))
            missing=np.full_like(query_x[te],np.nan)
            missing[:,states[a]['native'],states[a]['plate_'+o]]=purchased
            unpaid=max(unpaid,float(np.max(abs(replay(states[a],core.paid(missing,plan,o))-q))))
    if maxdiff>1e-12 or unpaid>1e-12:raise ValueError('replay/isolation failure')
    rec={'fold':f,'selected':selected,'scores':scores,'replay_maxdiff':maxdiff,'unpaid_maxdiff':unpaid,'changed_targets':models['nonlinear_panel'][0]['nonlinear_selection']['changed_targets'],'planning_predictor_fits':models['nonlinear_panel'][0]['nonlinear_selection']['predictor_fits'],'train_patients':sorted(set(p[tr])),'test_patients':sorted(set(p[te]))}
    return predictions,states,{a:models[a][0] for a in ARMS},rec

def freeze():
    if (HERE/'NONLINEAR_PANEL64_FREEZE.json').exists():raise ValueError('already frozen')
    (HERE/'NONLINEAR_PANEL64_PROTOCOL.md').write_text(PROTOCOL,encoding='utf-8')
    paths=[Path(__file__),HERE/'NONLINEAR_PANEL64_PROTOCOL.md',HERE/'run_crossplate64_20261008.py',HERE/'compact_train.py']
    for folder in ('engine','hybrid_residual','acceleration'):paths+=sorted((HERE/folder).glob('*.py'))
    dump(HERE/'NONLINEAR_PANEL64_FREEZE.json',{'state':'FROZEN_BEFORE_BIOLOGICAL_FITTING','utc':utc(),'source':{str(p.relative_to(HERE)):sha(p) for p in paths},'inputs':{str(p):sha(p) for p in (core.CURVES,core.CATALOG,core.BW,core.BEST)}})

def check_freeze():
    f=json.loads((HERE/'NONLINEAR_PANEL64_FREEZE.json').read_text())
    for p,h in f['source'].items():
        if sha(HERE/p)!=h:raise ValueError('source changed '+p)
    for p,h in f['inputs'].items():
        if sha(p)!=h:raise ValueError('input changed '+p)

def execute(out):
    check_freeze();out.mkdir(parents=True,exist_ok=False)
    dump(out/'STARTED.json',{'utc':utc(),'numpy':np.__version__,'python':sys.version})
    started=time.monotonic()
    try:
        data,features,_=core.load_prepared(core.CURVES,core.CATALOG)
        x=features['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);cat=catalog_from_features(features)
        folds,_=core.patient_folds(p,5,core.evaluate.SALT+'|outer')
        rz=np.load(core.BW,allow_pickle=False);bz=np.load(core.BEST,allow_pickle=False)
        for ref in (rz,bz):
            if not np.array_equal(ref['y'],y) or not np.array_equal(ref['patients'].astype(str),p) or not np.array_equal(ref['folds'],folds):raise ValueError('reference identity')
        pred={a:np.full((2,len(y),24),np.nan) for a in ARMS};records=[];state0=None
        for f in range(5):
            vals,states,plans,r=outer(x,y,p,cat,folds,f,x);te=folds==f
            for a in ARMS:
                pred[a][:,te]=vals[a];np.savez_compressed(out/f'fold_{f}_{a}_model.npz',**states[a])
                dump(out/f'fold_{f}_{a}_plan.json',plans[a])
                np.savez_compressed(out/f'fold_{f}_{a}_paid.npz',A=core.paid(x[te],plans[a],'A'),B=core.paid(x[te],plans[a],'B'),indices=np.flatnonzero(te))
            records.append(r);dump(out/f'fold_{f}_record.json',r)
            if f==0:state0=states
            print(json.dumps({'event':'outer_finished','fold':f,'changed_targets':r['changed_targets']}),flush=True)
        altered_x=x.copy();altered_y=y.copy();altered_x[folds==0]+=51.;altered_y[folds==0]-=33.
        altered,st,_,rr=outer(altered_x,altered_y,p,cat,folds,0,x)
        sentinel=max(float(np.max(abs(altered[a]-pred[a][:,folds==0]))) for a in ARMS)
        state_diff=max(float(np.max(abs(st[a][k]-state0[a][k]))) for a in ARMS for k in st[a])
        if sentinel>1e-12 or state_diff>1e-12 or rr['selected']!=records[0]['selected']:raise ValueError('held-patient training dependency')
        control=float(np.max(abs(pred['original']-rz['bandwidth07'])))
        if control>1e-12:raise ValueError('original control mismatch')
        op=core.metric(rz['bandwidth07'],y,p,folds);best=core.metric(bz['candidate'],y,p,folds)
        if abs(op[0]['mse']-core.EXPECTED_BW)>1e-13 or abs(best[0]['mse']-core.EXPECTED_BEST)>1e-13:raise ValueError('comparator metric mismatch')
        result={}
        for a in ARMS:
            if not np.isfinite(pred[a]).all():raise ValueError('incomplete predictions')
            met=core.metric(pred[a],y,p,folds);vb=core.compare(met,best);vo=core.compare(met,op)
            gate=lambda v:v['relative_gain']>0 and v['patient_wins']>=30 and v['fold_wins']==5 and v['p90_nonworse']
            result[a]={'metrics':met[0],'vs_best':vb,'vs_operating':vo,'gate':bool(a!='original' and gate(vb) and gate(vo)),'two_x':bool(met[0]['mse']<=core.TWOX and met[0]['p90']<=best[0]['p90'])}
        np.savez_compressed(out/'predictions_private.npz',**pred,y=y,patients=p,folds=folds,operating=rz['bandwidth07'],best=bz['candidate'],sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        receipt={'schema':'dosepilot.nonlinear_panel64.v1','status':'COMPLETE','role':'REPEATED_ADAPTIVE_DEVELOPMENT','arms':result,'fold_records':records,'control_maxdiff':control,'outer_mutation_maxdiff':sentinel,'outer_state_maxdiff':state_diff,'seconds':time.monotonic()-started,'physical_wells':64,'distinct_native_doses':64,'per_plate':[32,32],'target_mse_2x':core.TWOX,'protected22_access':False,'submission_changed':False,'independent_validation':False,'freeze_sha256':sha(HERE/'NONLINEAR_PANEL64_FREEZE.json'),'prediction_sha256':sha(out/'predictions_private.npz'),'finished_utc':utc()}
        dump(out/'RESULT.json',receipt);print(json.dumps({'RESULT':result,'seconds':receipt['seconds']},indent=2),flush=True)
    except BaseException as e:
        dump(out/'FAILURE.json',{'utc':utc(),'error':repr(e),'traceback':traceback.format_exc()});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    if args.freeze:freeze()
    elif args.out:execute(args.out)
    else:ap.error('use --freeze or --out')
