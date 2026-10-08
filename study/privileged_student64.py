#!/usr/bin/env python3
"""Cross-fitted privileged training labels, strictly 64 values at inference."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,datetime,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import run_accuracy_tiers as parent
m=parent.m;core=parent.core
from sparse_methods import fit_sparse_context
from coverage_methods import catalog_from_features,validate_plan
ALPHAS=(0.,.25,.5,1.)
BASES=('raw','teacher25','teacher50','teacher100');ARMS=BASES+('nested_primary',)
TEACHER_OPTION=3

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def freeze():
    files=[HERE/n for n in ('privileged_student64.py','test_privileged_student64.py','PRIVILEGED_STUDENT64_PROTOCOL.md','accuracy_tiers.py','run_accuracy_tiers.py','run_crossplate64_20261008.py','compact_train.py')]
    for folder in ('engine','hybrid_residual','acceleration'):files+=sorted((HERE/folder).glob('*.py'))
    dump(HERE/'PRIVILEGED_STUDENT64_FREEZE.json',{'state':'FROZEN_BEFORE_BIOLOGICAL_FITTING','utc':utc(),'source':{str(p.relative_to(HERE)):sha(p) for p in files},'inputs':{str(p):sha(p) for p in (core.CURVES,core.CATALOG,core.BW,core.BEST)}})
def check():
    f=json.loads((HERE/'PRIVILEGED_STUDENT64_FREEZE.json').read_text())
    if f['state']!='FROZEN_BEFORE_BIOLOGICAL_FITTING':raise ValueError('freeze state')
    for p,h in f['source'].items():
        if sha(HERE/p)!=h:raise ValueError('source changed '+p)
    for p,h in f['inputs'].items():
        if sha(p)!=h:raise ValueError('input changed '+p)

def teacher_labels(x,y,p,catalog):
    folds,_=core.patient_folds(p,3,'dosepilot.privileged_student64.v1|teacher')
    labels=np.full((2,len(y),24),np.nan);receipts=[]
    for k in range(3):
        tr=folds!=k;va=~tr
        if set(p[tr])&set(p[va]):raise ValueError('teacher patient overlap')
        teacher=m.fit_models(x[tr],y[tr],p[tr],catalog)[128]
        labels[:,va]=m.predict_options(x[va],teacher)[TEACHER_OPTION]
        receipts.append({'teacher_fold':k,'fit_patients':sorted(set(p[tr])),'soft_label_patients':sorted(set(p[va])),'teacher_wells_training_only':128})
    if not np.isfinite(labels).all():raise ValueError('incomplete cross-fitted teacher labels')
    return labels,receipts

def fit_students(x,y,p,catalog):
    soft,receipts=teacher_labels(x,y,p,catalog)
    plan=core.plan_panel_fast(x,y,p,catalog);plan['treatment_wells']=64;validate_plan(plan,catalog)
    a,b=m.paid(x,plan,'A'),m.paid(x,plan,'B');xx=np.r_[a,b];pp=np.r_[p,p]
    w=np.tile(m.patient_weights(p),2)/2;students={}
    for name,alpha in zip(BASES,ALPHAS):
        yy=np.r_[(1-alpha)*y+alpha*soft[0],(1-alpha)*y+alpha*soft[1]]
        ctx=fit_sparse_context(xx,yy,pp,plan['selected_native_ids'],catalog.target_ids);base=m.Ridge(ctx,plan)
        z=(xx-base.mean_x)/base.scale_x;res=yy-base.predict(xx)
        kernel=m.Additive(z,res,w,plan['coordinate_target_indices'])
        coefs=[np.zeros_like(res)]+[kernel.coefficients(l,f)[0] for f,l in m.OPTIONS[1:]]
        students[name]=(plan,base,kernel,coefs)
    return students,receipts

def outer(x,y,p,catalog,folds,f,query):
    tr=np.flatnonzero(folds!=f);te=np.flatnonzero(folds==f)
    if set(p[tr])&set(p[te]):raise ValueError('outer patient overlap')
    inner,_=core.patient_folds(p[tr],3,core.evaluate.SALT+f'|inner|{f}')
    oof={a:np.full((10,2,len(tr),24),np.nan) for a in BASES};inner_teachers=[]
    for k in range(3):
        fi=tr[inner!=k];vi=tr[inner==k]
        if set(p[fi])&set(p[vi]):raise ValueError('inner patient overlap')
        students,receipts=fit_students(x[fi],y[fi],p[fi],catalog)
        inner_teachers.append({'inner':k,'student_train_patients':sorted(set(p[fi])),'student_validation_patients':sorted(set(p[vi])),'teachers':receipts})
        for a in BASES:oof[a][:,:,inner==k]=m.predict_options(x[vi],students[a])
    if any(not np.isfinite(v).all() for v in oof.values()):raise ValueError('incomplete inner predictions')
    scores={a:[core.metric(q,y[tr],p[tr],inner)[0]['mse'] for q in oof[a]] for a in BASES}
    selected={a:int(np.argmin(scores[a])) for a in BASES}
    primary=min(((scores[a][i],j,i) for j,a in enumerate(BASES) for i in range(10)))
    primary_base=BASES[primary[1]];primary_option=int(primary[2])
    students,receipts=fit_students(x[tr],y[tr],p[tr],catalog)
    pred={a:m.predict_options(query[te],students[a])[selected[a]] for a in BASES}
    states={a:m.payload(students[a],selected[a]) for a in BASES}
    pred['nested_primary']=m.predict_options(query[te],students[primary_base])[primary_option]
    states['nested_primary']=m.payload(students[primary_base],primary_option)
    plan=students['raw'][0];maxdiff=0.;isolation=0.
    for a in ARMS:
        for oi,o in enumerate(('A','B')):
            paid=m.paid(query[te],plan,o);restored=m.replay(states[a],paid)
            maxdiff=max(maxdiff,float(np.max(abs(restored-pred[a][oi]))))
            masked=np.full_like(query[te],np.nan);masked[:,states[a]['native'],states[a]['plate_'+o]]=paid
            isolation=max(isolation,float(np.max(abs(m.replay(states[a],m.paid(masked,plan,o))-restored))))
    if maxdiff>1e-12 or isolation>1e-12:raise ValueError('student replay or hidden-input dependency')
    rec={'fold':f,'selected':selected,'primary_base':primary_base,'primary_option':primary_option,'scores':scores,'replay_maxdiff':maxdiff,'unpaid_isolation_maxdiff':isolation,'train_patients':sorted(set(p[tr])),'test_patients':sorted(set(p[te])),'inner_teachers':inner_teachers,'outer_teachers':receipts}
    return pred,states,plan,rec

def execute(out):
    check();out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    dump(out/'STARTED.json',{'utc':utc(),'python':sys.version,'numpy':np.__version__})
    try:
        data,feat,_=core.load_prepared(core.CURVES,core.CATALOG)
        x=feat['x_replicates'];y=data['y'];p=data['patient_ids'].astype(str);catalog=catalog_from_features(feat)
        folds,_=core.patient_folds(p,5,core.evaluate.SALT+'|outer')
        rz=np.load(core.BW,allow_pickle=False);bz=np.load(core.BEST,allow_pickle=False)
        for ref in (rz,bz):
            if not np.array_equal(ref['y'],y) or not np.array_equal(ref['patients'].astype(str),p) or not np.array_equal(ref['folds'],folds):raise ValueError('reference identity')
        pred={a:np.full((2,len(y),24),np.nan) for a in ARMS};records=[];state0=None
        for f in range(5):
            vals,states,plan,r=outer(x,y,p,catalog,folds,f,x);te=folds==f
            for a in ARMS:
                pred[a][:,te]=vals[a];np.savez_compressed(out/f'fold_{f}_{a}_model.npz',**states[a])
            np.savez_compressed(out/f'fold_{f}_paid.npz',A=m.paid(x[te],plan,'A'),B=m.paid(x[te],plan,'B'),indices=np.flatnonzero(te))
            dump(out/f'fold_{f}_plan.json',plan);dump(out/f'fold_{f}_record.json',r);records.append(r)
            if f==0:state0=states
            print(json.dumps({'fold_finished':f,'primary':r['primary_base'],'options':r['selected']}),flush=True)
        changed_x=x.copy();changed_y=y.copy();changed_x[folds==0]+=63.;changed_y[folds==0]-=49.
        altered,states,_,rr=outer(changed_x,changed_y,p,catalog,folds,0,x)
        mutation=max(float(np.max(abs(altered[a]-pred[a][:,folds==0]))) for a in ARMS)
        state_diff=max(float(np.max(abs(states[a][k]-state0[a][k]))) for a in ARMS for k in states[a])
        if mutation>1e-12 or state_diff>1e-12 or rr['primary_base']!=records[0]['primary_base'] or rr['selected']!=records[0]['selected']:raise ValueError('outer-patient training dependency')
        control=float(np.max(abs(pred['raw']-rz['bandwidth07'])))
        if control>1e-12:raise ValueError('alpha0 control mismatch')
        best=core.metric(bz['candidate'],y,p,folds);op=core.metric(rz['bandwidth07'],y,p,folds)
        if abs(best[0]['mse']-core.EXPECTED_BEST)>1e-13 or abs(op[0]['mse']-core.EXPECTED_BW)>1e-13:raise ValueError('reference metrics')
        results={}
        for a in ARMS:
            met=core.metric(pred[a],y,p,folds);vs=core.compare(met,best);vo=core.compare(met,op)
            gate=lambda v:v['relative_gain']>0 and v['patient_wins']>=30 and v['fold_wins']==5 and v['p90_nonworse']
            results[a]={'metrics':met[0],'vs_best':vs,'vs_operating':vo,'gate':bool(a!='raw' and gate(vs) and gate(vo)),'same_budget_2x':bool(met[0]['mse']<=core.TWOX and met[0]['p90']<=best[0]['p90'])}
        np.savez_compressed(out/'predictions_private.npz',**pred,y=y,patients=p,folds=folds,scientific64=bz['candidate'],operating64=rz['bandwidth07'],sample_ids=data['sample_ids'],drug_ids=data['drug_ids'])
        result={'schema':'dosepilot.privileged_student64.result.v1','status':'COMPLETE','role':'REPEATED_ADAPTIVE_DEVELOPMENT','primary':'nested_primary','arms':results,'student_wells_at_inference':64,'teacher_wells_per_alternative_training_only':128,'teacher_option':TEACHER_OPTION,'target_mse_2x':core.TWOX,'control_maxdiff':control,'outer_mutation_maxdiff':mutation,'outer_state_maxdiff':state_diff,'independent_validation':False,'no_protected22':True,'submission_changed':False,'freeze_sha256':sha(HERE/'PRIVILEGED_STUDENT64_FREEZE.json'),'prediction_sha256':sha(out/'predictions_private.npz'),'finished_utc':utc(),'seconds':time.monotonic()-start}
        dump(out/'RESULT.json',result)
        print(json.dumps({a:{'mse':v['metrics']['mse'],'p90':v['metrics']['p90'],'gain_vs_best':v['vs_best']['relative_gain'],'patients':v['vs_best']['patient_wins'],'folds':v['vs_best']['fold_wins'],'same_budget_2x':v['same_budget_2x'],'gate':v['gate']} for a,v in results.items()},indent=2),flush=True)
    except BaseException as e:
        dump(out/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'utc':utc()});raise

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--out',type=Path);args=ap.parse_args()
    if args.freeze:freeze()
    elif args.out:execute(args.out)
    else:ap.error('use --freeze or --out')
